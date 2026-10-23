"""Queued derived Home01 adapter. Reads immutable evidence; never runs retained commands."""
from __future__ import annotations
import argparse
import base64
from collections import Counter
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[2]
INTEGRATION = CAMPAIGN.parent
EXPERIMENT = INTEGRATION.parent
REPO = EXPERIMENT.parent
TOOLS = REPO / 'Tools/synchronized_replay'
sys.path.insert(0, str(TOOLS))
from core import sha, clock_bracket, validate_anchors, diff_text, script_json

RUN = 'RCI001-C02-home-01'
JOB = '20260930T214446477570Z-e5c34e42'
SNAPSHOT = EXPERIMENT / 'Architecture Map/releases/RCI001-C02-dev-114/snapshot.json'
QUEUE = REPO.parent / 'tools/compute_queue/compute_queue.py'


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


class Inputs:
    def __init__(self, output):
        self.output, self.rows = output, {}

    def raw(self, path, role, expected=None, size=None):
        path = Path(path).resolve()
        raw = path.read_bytes()
        digest = sha(raw)
        if expected is not None and digest != expected or size is not None and len(raw) != size:
            raise ValueError('Input identity differs: ' + str(path))
        self.rows[str(path)] = {'path': str(path), 'sha256': digest, 'bytes': len(raw), 'role': role}
        return raw

    def json(self, path, role, expected=None, size=None):
        return json.loads(self.raw(path, role, expected, size))

    def ref(self, path, line=None, label=None):
        result = {'href': quote(Path(os.path.relpath(path, self.output)).as_posix(), safe='/.'),
                  'label': label or Path(path).name}
        if line is not None:
            result['line'] = line
        return result


def build(output):
    if output.exists():
        raise ValueError('Fresh candidate directory required; preserve earlier builds')
    output.mkdir(parents=True)
    inputs = Inputs(output)
    official = json.loads(subprocess.run([sys.executable, '-X', 'utf8', '-B', str(QUEUE), 'status', JOB],
        capture_output=True, encoding='utf-8', check=True).stdout)
    if official.get('id') != JOB or official.get('state') != 'succeeded' or type(official.get('exit_status')) is not int or official['exit_status'] != 0:
        raise ValueError('Original official queue success/int0 required before outcome reads')
    write(output / 'original-official-status.json', official)
    plan = inputs.json(CAMPAIGN / 'execution-plan.json', 'sealed campaign plan',
        'c62c43e60ce6b1be5f0fd0d8383b7c68d8779cf6baf0c1aa744bcaa235176bb5')
    attempt = next(a for a in plan['attempts'] if a['run_id'] == RUN)
    slot = CAMPAIGN / 'execution' / RUN
    disposition = inputs.json(slot / 'disposition.json', 'original disposition')
    if disposition.get('run_id') != RUN or disposition.get('execution_status') != 'completed':
        raise ValueError('Home01 completed disposition required')
    receipt_path = slot / 'storage/queue-receipt.json'
    receipt = inputs.json(receipt_path, 'original bound queue receipt')
    job = receipt.get('job', receipt)
    if job.get('id') != JOB or job.get('state') != 'succeeded' or type(job.get('exit_status')) is not int or job['exit_status'] != 0:
        raise ValueError('Bound receipt mismatch')
    for key in ('argv', 'cwd', 'started_at', 'ended_at', 'state', 'exit_status'):
        if official.get(key) != job.get(key):
            raise ValueError('Official status disagrees with bound receipt: ' + key)
    assessment = inputs.json(slot / 'assessment.json', 'bound admitted assessment', disposition['assessment_sha256'])
    bindings = assessment['bindings']
    if (assessment['run_id'] != RUN or assessment['queue_job_id'] != JOB
            or bindings['queue_receipt_sha256'] != sha(receipt_path.read_bytes())
            or bindings['manifest_sha256'] != attempt['manifest']['sha256']):
        raise ValueError('Assessment identity/receipt/manifest mismatch')
    inputs.raw(attempt['manifest']['path'], 'original immutable attempt manifest', bindings['manifest_sha256'])
    snapshot = inputs.json(SNAPSHOT, 'frozen revision snapshot', bindings['framework_snapshot_sha256'])
    inputs.raw(SNAPSHOT.with_name('code.zip'), 'frozen source archive', bindings['framework_archive_sha256'])
    for relative, record in snapshot['sources'].items():
        inputs.raw(REPO / relative, 'frozen source immutability guard', record['sha256'], record.get('bytes'))
    for a in plan['attempts']:
        inputs.raw(CAMPAIGN / 'execution' / a['run_id'] / 'disposition.json', 'twenty terminal dispositions guard')
    inputs.raw(CAMPAIGN / 'execution/campaign-stop.json', 'closed admission guard')
    for p in (EXPERIMENT / 'Architecture Map').glob('*.jsonl'):
        inputs.raw(p, 'canonical architecture map guard')
    host, orch = Path(attempt['host_evidence']), Path(attempt['evidence'])
    inventory = {(r['root'], r['path']): r for r in assessment['evidence_inventory']}
    roots = {'protected_host': host, 'orchestrator': orch}
    # Bind all admitted evidence, including records this replay does not display.
    for (root, relative), record in inventory.items():
        inputs.raw(roots[root] / relative, 'admitted evidence guard', record['sha256'], record['bytes'])

    def retained(root, relative):
        record = inventory[(root, relative)]
        return inputs.json(roots[root] / relative, 'replay content', record['sha256'], record['bytes'])

    def trace(root, relative):
        record = inventory[(root, relative)]
        raw = inputs.raw(roots[root] / relative, 'replay trace', record['sha256'], record['bytes'])
        return [(i, json.loads(s)) for i, s in enumerate(raw.decode('utf-8').splitlines(), 1) if s.strip()]

    history_path = host / 'public-history.jsonl'
    history = trace('protected_host', 'public-history.jsonl')
    anchors = [{'wall': r['wall_unix_s'], 'sim': r['sim_time_s'], 'id': r['event_id'], 'line': line} for line, r in history]
    validate_anchors(anchors)
    starts = [r for _, r in history if r['type'] == 'episode_started']
    stops = [r for _, r in history if r['type'] == 'episode_stopped']
    if len(starts) != 1 or len(stops) != 1:
        raise ValueError('Unique episode start/stop required')
    origin, end = anchors[0]['sim'], stops[0]['sim_time_s']
    events, observations = [], []

    def event(eid, lane, kind, title, wall, source, detail, exact=None):
        timing = clock_bracket(anchors, wall)
        if exact is not None:
            timing = {'kind': 'recorded-simulation', 'sim_min': exact, 'sim_max': exact, 'estimate': exact}
        e = {'id': str(eid), 'lane': lane, 'kind': kind, 'title': title, 'wall': wall,
             'sim': exact, 'at': timing.get('sim_max'), 'timing': timing, 'source': source, 'detail': detail}
        events.append(e)
        return e

    for line, row in history:
        p, kind = row.get('payload', {}), row['type']
        lane = 'observation' if kind == 'observation' else ('file' if kind == 'continuity_committed' else
            ('authority' if 'owner' in kind or 'invocation' in kind or 'assistance' in kind else 'action'))
        detail = p
        if kind == 'observation':
            detail = {k: p.get(k) for k in ('sequence', 'capture_sim_time_s', 'detections', 'station', 'gripper', 'inspection', 'last_feedback')}
            observations.append({'sim': row['sim_time_s'], 'wall': row['wall_unix_s'], 'event_id': row['event_id'],
                                 'source': inputs.ref(history_path, line), **detail})
        title = kind.replace('_', ' ')
        if 'request_id' in p:
            title += ' · ' + p['request_id']
        if kind == 'command_rejected':
            title += ' · ' + str(p.get('error', {}).get('code', p.get('reason', p.get('admission', {}).get('reason', 'rejected'))))
        observed = event('world-' + str(row['event_id']), lane, kind, title, row['wall_unix_s'],
              inputs.ref(history_path, line), detail, row['sim_time_s'])
        observed.update(owner=row.get('owner'), authority_epoch=row.get('authority_epoch'))

    broker_path = orch / 'pilot/broker-events.jsonl'
    for line, row in trace('orchestrator', 'pilot/broker-events.jsonl'):
        detail = {k: row.get(k) for k in ('origin', 'trace_id', 'method', 'path', 'status', 'request', 'response')}
        lane = 'mirror' if row.get('origin') == 'protected_host' else 'gateway'
        event('gateway-' + str(line), lane, 'broker', str(row.get('method')) + ' ' + str(row.get('path'))
              + ' · HTTP ' + str(row.get('status')), row.get('wall_unix_s'), inputs.ref(broker_path, line), detail)

    client_path = orch / 'pilot/client/events.jsonl'
    public_types = {'agentMessage', 'commandExecution', 'sleep', 'fileChange', 'mcpToolCall', 'dynamicToolCall'}
    excluded = Counter()
    for line, row in trace('orchestrator', 'pilot/client/events.jsonl'):
        method, params = row.get('method'), row.get('params') or {}
        item = params.get('item') or {}
        if method == 'item/agentMessage/delta':
            event('client-' + str(line), 'message-fragment', 'message_delta', 'Public message fragment',
                row.get('emittedAtMs', 0) / 1000 or None, inputs.ref(client_path, line),
                {k: params.get(k) for k in ('itemId', 'delta')})
        elif method in ('item/started', 'item/completed') and item.get('type') in public_types:
            phase = 'started' if method == 'item/started' else 'completed'
            lane = 'message' if item['type'] == 'agentMessage' else 'tool'
            safe = {k: v for k, v in item.items() if k not in ('source_base64',)}
            brief = item.get('command', '').splitlines()[0][:180] if item.get('command') else item.get('phase', item.get('id', ''))
            event('client-' + str(line), lane, item['type'], item['type'] + ' ' + phase + ' · ' + brief,
                row.get('emittedAtMs', 0) / 1000 or None, inputs.ref(client_path, line),
                {'phase': phase, 'item': safe, 'receipt_clock': 'client emittedAtMs; not a reasoning timestamp'})
        else:
            excluded[method or 'non-public response'] += 1

    captures = {}
    process_records = []
    for number in (1, 2):
        relative = f'pilot/executor-{number}-capture.jsonl'
        path = orch / relative
        rows = trace('orchestrator', relative)
        captures[number] = rows
        requests = {}
        for line, row in rows:
            m, wall = row.get('message', {}), row.get('wall_unix_s')
            p, method = m.get('params') or {}, m.get('method')
            if row['kind'] == 'request' and method == 'process/start':
                record = {'pid': p['processId'], 'command': p['argv'][-1], 'argv': p['argv'], 'request': row,
                          'line': line, 'source': inputs.ref(path, line), 'tool_id': p.get('metadata', {}).get('toolCallId'),
                          'outputs': [], 'exit': None, 'executor': number}
                requests[p['processId']] = record
                process_records.append(record)
                event(f'executor-{number}-{line}', 'executor', 'process_request', 'Executor process request · ' + p['processId'],
                      wall, inputs.ref(path, line), {'process_id': p['processId'], 'tool_id': record['tool_id'], 'argv': p['argv']})
            elif row['kind'] == 'response' and method in ('process/output', 'process/exited'):
                rec = requests.get(p.get('processId'))
                if method == 'process/output':
                    raw = base64.b64decode(p['chunk'], validate=True)
                    for blob in row.get('blobs', []):
                        if blob['path'] == ['params', 'chunk'] and (blob['raw_bytes'] != len(raw)
                                or blob['raw_sha256'] != sha(raw) or blob['retained_sha256'] != sha(raw)):
                            raise ValueError('Incomplete executor output blob')
                    detail = {'process_id': p['processId'], 'stream': p['stream'], 'seq': p['seq'],
                              'text': raw.decode('utf-8', errors='replace'), 'bytes': len(raw), 'sha256': sha(raw),
                              'scope': 'Trusted executor output; application/model receipt is separate'}
                    if rec is not None:
                        rec['outputs'].append((p['stream'], raw))
                else:
                    detail = p
                    if rec is not None:
                        rec['exit'] = {'wall': wall, 'code': p.get('exitCode'), 'source': inputs.ref(path, line)}
                event(f'executor-{number}-{line}', 'executor', method.replace('/', '_'),
                      method + ' · ' + p['processId'], wall, inputs.ref(path, line), detail)

    snapshot_path = orch / 'pilot/runtime-after-close.json'
    final = retained('orchestrator', 'pilot/runtime-after-close.json')
    before = retained('orchestrator', 'pilot/runtime-before-close.json')
    initial = retained('orchestrator', 'pilot/runtime-input-hashes.json')
    if final != before:
        raise ValueError('Reference expects identical before/after final workspace exports; do not merge different snapshots')
    content = {}
    for path, record in final['files'].items():
        raw = base64.b64decode(record['base64'], validate=True)
        if sha(raw) != record['sha256'] or len(raw) != record['bytes']:
            raise ValueError('Corrupt final snapshot contents: ' + path)
        content[path] = raw
    if sum(map(len, content.values())) != final['total_bytes']:
        raise ValueError('Final snapshot total mismatch')
    first_open = captures[2][0][1]['wall_unix_s']
    baseline_timing = clock_bracket(anchors, first_open)
    files = {}

    def version(path, raw, at, timing, evidence, source, final_only=False, digest=None, reason=None, extra=None):
        f = files.setdefault(path, {'path': path, 'versions': []})
        text = raw.decode('utf-8') if raw is not None else None
        earlier = f['versions'][-1] if f['versions'] else None
        diff = diff_text(earlier['text'] if earlier else None, text, path) if text is not None else None
        v = {'text': text, 'sha256': sha(raw) if raw is not None else digest,
             'bytes': len(raw) if raw is not None else None, 'at': at, 'timing': timing,
             'evidence': evidence, 'source': source, 'final_only': final_only,
             'reason': reason, 'diff': diff, 'diff_before_sha256': earlier['sha256'] if earlier else None}
        if extra:
            v.update(extra)
        f['versions'].append(v)
        return v

    initial_path = orch / 'pilot/runtime-input-hashes.json'
    for path, digest in initial.items():
        raw = content.get(path)
        if path == 'Continuity.md' and digest == sha(b''):
            raw = b''
        if raw is not None and sha(raw) != digest:
            raw = None
        version(path, raw, baseline_timing['sim_max'], baseline_timing,
            'Initial hash inventory; bytes matched by identity where available', inputs.ref(initial_path),
            digest=digest, reason='Only initial content hash retained; bytes at this time unavailable' if raw is None else None,
            extra={'scope': 'Baseline existed before first executor connection; exact setup snapshot time unrecorded'})

    # Exact startup read: split concatenated JSON without inventing file serialization.
    read_cmd = 'cat /workspace/live/activation.json /workspace/live/state.json /workspace/Continuity.md'
    for rec in process_records:
        if rec['command'] == read_cmd and rec['exit'] and rec['exit']['code'] == 0:
            raw = b''.join(b for stream, b in rec['outputs'] if stream == 'stdout')
            text, pos = raw.decode('utf-8'), 0
            for path in ('live/activation.json', 'live/state.json'):
                _, length = json.JSONDecoder().raw_decode(text[pos:])
                value = text[pos:pos + length].encode('utf-8')
                # A mirrored state file can change between setup and this read.
                # Its content is authenticated by executor output, not by the earlier input hash.
                if path == 'live/activation.json' and sha(value) != initial[path]:
                    raise ValueError('Fixed activation read differs from initial file hash')
                timing = clock_bracket(anchors, rec['exit']['wall'])
                version(path, value, timing['sim_max'], timing, 'Exact content read by trusted executor', rec['exit']['source'],
                    extra={'read_request_source': rec['source'], 'matches_initial_hash': sha(value) == initial[path]})
                pos += length

    commits = [r for _, r in history if r['type'] == 'continuity_committed']
    commit_by_sha = {r['payload']['sha256']: r for r in commits}
    note_versions = []
    for rec in process_records:
        if not rec['exit'] or rec['exit']['code'] != 0:
            continue
        cmd = rec['command']
        match = re.search(r"^cat > (notes/[A-Za-z0-9_.-]+) <<'EOF'\n([\s\S]*?)\nEOF(?:\n|$)", cmd)
        raw, path = None, None
        if match:
            path, raw = match.group(1), (match.group(2) + '\n').encode('utf-8')
        elif cmd.startswith("sed -i 's/") and note_versions:
            # Closed reference syntax, never a shell evaluator.
            match = re.fullmatch(r"sed -i 's/(.*)/(.*)/' notes/next-continuity\.md\npython3 -B robot\.py continuity --file notes/next-continuity\.md", cmd)
            if not match:
                raise ValueError('Unrecognized retained note edit; requires explicit adapter')
            old, new = match.group(1).replace('\\.', '.'), match.group(2)
            previous = note_versions[-1].decode('utf-8')
            if previous.count(old) != 1:
                raise ValueError('Ambiguous sed edit')
            path, raw = 'notes/next-continuity.md', previous.replace(old, new).encode('utf-8')
        if path is None:
            continue
        digest = sha(raw)
        if path == 'notes/next-continuity.md':
            if digest not in commit_by_sha:
                raise ValueError('Requested note bytes lack independent protected commit')
            retained_raw = inputs.raw(host / f'continuity-history/{digest}.md', 'protected continuity contents', digest, len(raw))
            if retained_raw != raw:
                raise ValueError('Literal note differs from independent retained content')
            note_versions.append(raw)
        elif content.get(path) != raw:
            raise ValueError('Requested final note differs from independently retained snapshot')
        timing = clock_bracket(anchors, rec['exit']['wall'])
        timing['write_request_wall'] = rec['request']['wall_unix_s']
        timing['write_exit_wall'] = rec['exit']['wall']
        start_timing = clock_bracket(anchors, rec['request']['wall_unix_s'])
        timing['write_sim_lower'] = start_timing.get('sim_min')
        version(path, raw, timing.get('sim_max'), timing,
            'Derived literal write; successful executor exit and independent content identity', rec['exit']['source'],
            final_only=timing['kind'] == 'after-stop', extra={'write_request_source': rec['source']})
        event('write-' + rec['pid'], 'file', 'file_write', 'File write · ' + path, rec['exit']['wall'],
              rec['exit']['source'], {'path': path, 'sha256': digest, 'bytes': len(raw), 'write_interval': timing,
                                     'request_source': rec['source'], 'tool_id': rec['tool_id']})

    # The protected Continuity endpoint is atomic; timestamp is the protected receipt, not the local draft write.
    for row in commits:
        digest = row['payload']['sha256']
        raw = inputs.raw(host / f'continuity-history/{digest}.md', 'protected continuity contents', digest, row['payload']['bytes'])
        version('Continuity.md', raw, row['sim_time_s'],
            {'kind': 'recorded-simulation', 'sim_min': row['sim_time_s'], 'sim_max': row['sim_time_s']},
            'Protected atomic continuity commit', inputs.ref(history_path, row['event_id']))
    for path, raw in content.items():
        version(path, raw, None, {'kind': 'untimed-final-snapshot'}, 'Exact retained final workspace snapshot',
                inputs.ref(snapshot_path), final_only=True)
    version('Continuity.md', content['.continuity/Continuity.md'], None, {'kind': 'untimed-final-snapshot'},
            'Public fixed-link alias to retained .continuity/Continuity.md', inputs.ref(snapshot_path), final_only=True)
    files['Continuity.md']['alias'] = '.continuity/Continuity.md (documented fixed public link; link metadata not exported)'

    reader_path = EXPERIMENT / 'Storage Retention Implementation 001/future/recorder.py'
    spec = importlib.util.spec_from_file_location('home01_original_recorder', reader_path)
    decoder = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = decoder
    spec.loader.exec_module(decoder)
    frames, availability = [], []
    publication = {}
    for line, row in history:
        if row['type'] == 'observation':
            publication.setdefault(row['payload']['capture_sim_time_s'], (line, row))
    image_dir = output / 'images'
    image_dir.mkdir()
    reader = decoder.Reader(host / 'native-recording')
    try:
        if reader.meta.get('run_id') != RUN:
            raise ValueError('Recording run differs')
        for image in reader.images():
            availability.append(image)
            if image['status'] != 'available':
                continue
            original = reader.image(image['id'])
            raw = original['rgb']
            if sha(raw) != image['rgb_sha256'] or not raw.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('Retained RGB identity differs')
            line, pub = publication[image['capture_time_s']]
            if pub['sim_time_s'] < image['capture_time_s']:
                raise ValueError('Frame published before capture')
            name = str(len(frames)).zfill(4) + '.png'
            (image_dir / name).write_bytes(raw)
            width, height = struct.unpack('!II', raw[16:24])
            frames.append({**image, 'href': 'images/' + name, 'bytes': len(raw), 'width': width, 'height': height,
                           'published_sim': pub['sim_time_s'], 'publication_event': pub['event_id'],
                           'source': inputs.ref(history_path, line), 'capture_wall': None})
    finally:
        reader.close()
    if sum(f['bytes'] for f in frames) > 24_000_000:
        raise ValueError('Derived RGB copy exceeded declared 24MB bound')

    milestones = []
    desired = [('conventional_assistance_requested', 'Conventional controller requests help'),
               ('command_requested', 'Move A1 to parking1'),
               ('command_rejected', 'First handback rejected'),
               ('command_requested', 'Protected setup B'),
               ('control_owner_changed', 'Second handback accepted'),
               ('command_requested', 'Conventional follow-through'),
               ('episode_stopped', 'Protected task success')]
    for kind, label in desired:
        candidates = [(line, r) for line, r in history if r['type'] == kind]
        if label == 'Move A1 to parking1':
            candidates = [(l, r) for l, r in candidates if r['payload'].get('actor') == 'robot' and r['payload'].get('envelope', {}).get('action', {}).get('operation') == 'transport']
        elif label == 'Protected setup B':
            candidates = [(l, r) for l, r in candidates if r['payload'].get('actor') == 'robot' and r['payload'].get('envelope', {}).get('action', {}).get('operation') == 'setup']
        elif label == 'Second handback accepted':
            candidates = [(l, r) for l, r in candidates if r['owner'] == 'conventional']
        elif label == 'Conventional follow-through':
            candidates = [(l, r) for l, r in candidates if r['payload'].get('actor') == 'conventional' and r['sim_time_s'] > 300]
        if not candidates:
            raise ValueError('Semantic milestone lacks original evidence: ' + label)
        _, row = candidates[0]
        milestones.append({'label': label, 'at': row['sim_time_s'], 'event_id': 'world-' + str(row['event_id'])})

    events.sort(key=lambda e: (e['at'] is None, e['at'] if e['at'] is not None else e['wall'] or 0, e['wall'] or 0, e['id']))
    data = {'schema': 'synchronized-experiment-replay-1', 'meta': {'run_id': RUN, 'title': 'Home01 · clearance, feedback, setup, handback',
        'start': origin, 'end': end, 'wall_start': starts[0]['wall_unix_s'], 'wall_stop': stops[0]['wall_unix_s'],
        'final_scope': final['scope'], 'final_retained_files': len(content), 'final_retained_bytes': final['total_bytes'],
        'assessment_outcome': 'Original admitted valid success; all 41 checks. No new scoring.',
        'limitations': ['69 retained RGB frames end at 138.778 s; no recorded pixels for either handback or conventional follow-through.',
            'Observation map uses held public detections, not reconstructed camera footage or fresh physics.',
            'Cross-clock tool/message events have measured brackets; navigation uses the upper bound, not an exact simulated timestamp.',
            'Intermediate workspace is last evidenced content, not an exact filesystem: no complete mutation journal was retained.',
            'Final export is untimed and omits endpoint credentials and symlink/directory metadata. 19 regular files plus the documented public Continuity alias.',
            'Final text and a local outcome note follow simulation stop; they are exposed only in the terminal view.',
            'No hidden reasoning or raw response envelopes are included. Public notes/messages remain the agent’s own claims.'],
        'links': [inputs.ref(slot / 'assessment.json', label='Original assessment'), inputs.ref(slot / 'disposition.json', label='Original disposition'),
                  inputs.ref(history_path, label='Protected world history'), inputs.ref(client_path, label='Original public event source (also contains excluded private items)'),
                  inputs.ref(snapshot_path, label='Retained final workspace snapshot'), inputs.ref(HERE / 'README.md', label='Replay evidence and rebuild guide'),
                  inputs.ref(REPO / 'Playbooks/Synchronized Experiment Replay.md', label='Reusable playbook')],
        'excluded_client_records': dict(excluded), 'frame_counts': dict(Counter(r['status'] for r in availability))},
        'anchors': anchors, 'events': events, 'observations': observations, 'frames': frames,
        'availability': availability, 'files': list(files.values()), 'milestones': milestones}
    # Do not give a direct link to a source containing hidden reasoning in the public viewer.
    data['meta']['links'] = [r for r in data['meta']['links'] if 'excluded private' not in r['label']]
    for e in events:
        if e['source']['href'] == inputs.ref(client_path)['href']:
            e['source']['label'] = 'Allowlisted public extraction · original line ' + str(e['source']['line'])
            e['source']['href'] = 'public-client.json'
    write(output / 'public-client.json', [e for e in events if e['id'].startswith('client-')])
    source_dir = output / 'tool-source'
    source_dir.mkdir()
    for path in [Path(__file__), HERE / 'verify.py', TOOLS / 'core.py', TOOLS / 'viewer.js', TOOLS / 'viewer.css', TOOLS / 'template.html']:
        inputs.raw(path, 'derived replay implementation source')
        shutil.copyfile(path, source_dir / path.name)
    write(output / 'data.json', data)
    (output / 'data.js').write_text('window.REPLAY_DATA=' + script_json(data) + ';\n', encoding='utf-8')
    for name in ('viewer.js', 'viewer.css'):
        shutil.copyfile(TOOLS / name, output / name)
    shutil.copyfile(TOOLS / 'template.html', output / 'index.html')
    source_inputs = list(inputs.rows.values())
    write(output / 'inputs.json', {'run_id': RUN, 'original_queue': official, 'inputs': source_inputs,
        'scope': 'Every frozen source and admitted evidence file, all dispositions/stop and canonical map; hash-bound read-only guards'})
    outputs = [{'path': p.relative_to(output).as_posix(), 'sha256': sha(p.read_bytes()), 'bytes': p.stat().st_size}
               for p in sorted(output.rglob('*')) if p.is_file()]
    summary = {'run_id': RUN, 'world_events': len(history), 'display_events': len(events),
               'frames': len(frames), 'frame_bytes': sum(f['bytes'] for f in frames), 'regular_final_files': len(content),
               'workspace_paths_with_alias': len(files), 'continuity_commits': len(commits),
               'source_guard_count': len(source_inputs), 'outputs': outputs}
    write(output / 'build.json', summary)
    print(json.dumps({k: v for k, v in summary.items() if k != 'outputs'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        build(args.output.resolve())
    except Exception as error:
        if args.output.exists():
            write(args.output / 'BUILD_FAILED.json', {'error': str(error), 'outputs_not_usable': True})
        raise
