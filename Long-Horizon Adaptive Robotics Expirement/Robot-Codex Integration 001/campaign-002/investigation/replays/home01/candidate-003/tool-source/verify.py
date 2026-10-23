"""Independent derived-replay audit. Does not import the builder, viewer or clock helper."""
from __future__ import annotations
import argparse
import base64
from bisect import bisect_right
import difflib
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[2]
REPO = CAMPAIGN.parents[2]
RUN = 'RCI001-C02-home-01'
JOB = '20260930T214446477570Z-e5c34e42'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def lines(path):
    return {i: json.loads(s) for i, s in enumerate(Path(path).read_text(encoding='utf-8').splitlines(), 1) if s.strip()}


def audit(output):
    assertions = 0

    def check(ok, label):
        nonlocal assertions
        if not ok:
            raise ValueError(label)
        assertions += 1

    guard = read(output / 'inputs.json')
    official = read(output / 'original-official-status.json')
    queue = REPO.parent / 'tools/compute_queue/compute_queue.py'
    current = json.loads(subprocess.run([sys.executable, '-X', 'utf8', '-B', str(queue), 'status', JOB],
        capture_output=True, encoding='utf-8', check=True).stdout)
    check(current['id'] == JOB and current['state'] == 'succeeded' and type(current['exit_status']) is int and current['exit_status'] == 0,
          'Authentic original queue is not successful integer0')
    for key in ('id', 'argv', 'cwd', 'started_at', 'ended_at', 'exit_status', 'state'):
        check(current[key] == official[key], 'Original queue binding changed: ' + key)
    for record in guard['inputs']:
        raw = Path(record['path']).read_bytes()
        check(len(raw) == record['bytes'] and digest(raw) == record['sha256'], 'Original input changed: ' + record['path'])
    build = read(output / 'build.json')
    for record in build['outputs']:
        raw = (output / record['path']).read_bytes()
        check(len(raw) == record['bytes'] and digest(raw) == record['sha256'], 'Derived output changed: ' + record['path'])
    plan = read(CAMPAIGN / 'execution-plan.json')
    attempt = next(r for r in plan['attempts'] if r['run_id'] == RUN)
    host, orch = Path(attempt['host_evidence']), Path(attempt['evidence'])
    slot = CAMPAIGN / 'execution' / RUN
    disposition, assessment = read(slot / 'disposition.json'), read(slot / 'assessment.json')
    check(digest((slot / 'assessment.json').read_bytes()) == disposition['assessment_sha256'], 'Disposition assessment binding')
    check(assessment['run_id'] == RUN and assessment['queue_job_id'] == JOB, 'Original run/job identity')
    data = read(output / 'data.json')
    check(data['schema'] == 'synchronized-experiment-replay-1', 'Normalized contract')
    history = lines(host / 'public-history.jsonl')
    raw_anchors = [{'id': r['event_id'], 'sim': r['sim_time_s'], 'wall': r['wall_unix_s'], 'line': i} for i, r in history.items()]
    check(data['anchors'] == raw_anchors, 'Clock anchors differ from original protected receipts')
    for left, right in zip(raw_anchors, raw_anchors[1:]):
        check(right['wall'] > left['wall'] and right['sim'] >= left['sim'], 'Clock ordering/reset')
    walls = [a['wall'] for a in raw_anchors]
    client = lines(orch / 'pilot/client/events.jsonl')
    executor = {n: lines(orch / f'pilot/executor-{n}-capture.jsonl') for n in (1, 2)}
    broker = lines(orch / 'pilot/broker-events.jsonl')
    bracket_widths, terminal_counts = [], {}
    for e in data['events']:
        check(e['kind'] != 'reasoning' and not e['kind'].startswith('rawResponse'), 'Private reasoning leak')
        if e['id'].startswith('world-'):
            raw = next(r for r in history.values() if str(r['event_id']) == e['id'][6:])
            check(e['sim'] == e['at'] == raw['sim_time_s'] and e['wall'] == raw['wall_unix_s'], 'World event clock')
            check(e['owner'] == raw['owner'] and e['authority_epoch'] == raw['authority_epoch'], 'World owner/epoch')
            if raw['type'] != 'observation':
                check(e['detail'] == raw['payload'], 'Protected receipt detail changed')
        else:
            wall, timing = e['wall'], e['timing']
            if e['id'].startswith('client-'):
                raw = client[int(e['id'].split('-')[1])]
                check(wall == raw['emittedAtMs'] / 1000, 'Client receipt clock')
                if raw.get('method') == 'item/agentMessage/delta':
                    check(e['detail']['delta'] == raw['params']['delta'], 'Public message fragment')
                else:
                    item = raw['params']['item']
                    check(item['type'] in {'agentMessage', 'commandExecution', 'sleep', 'fileChange', 'mcpToolCall', 'dynamicToolCall'}, 'Client allowlist')
                    check(e['detail']['item'] == {k: v for k, v in item.items() if k != 'source_base64'}, 'Public item changed')
                check('client/events.jsonl' not in e['source']['href'], 'Viewer link exposes raw private response source')
            elif e['id'].startswith('gateway-'):
                check(wall == broker[int(e['id'].split('-')[1])]['wall_unix_s'], 'Broker receipt clock')
            elif e['id'].startswith('executor-'):
                _, number, line = e['id'].split('-')
                raw = executor[int(number)][int(line)]
                check(wall == raw['wall_unix_s'], 'Executor receipt clock')
                if e['kind'] == 'process_output':
                    value = base64.b64decode(raw['message']['params']['chunk'], validate=True)
                    check(e['detail']['sha256'] == digest(value) and e['detail']['bytes'] == len(value)
                          and e['detail']['text'] == value.decode('utf-8', errors='replace'), 'Trusted output identity')
            i = bisect_right(walls, wall)
            if i == len(walls) and wall > walls[-1]:
                check(e['at'] is None and timing['kind'] == 'after-stop' and timing['after_stop_wall_s'] == wall - walls[-1], 'After-stop extrapolation')
                terminal_counts[e['lane']] = terminal_counts.get(e['lane'], 0) + 1
            elif i == 0:
                check(e['at'] is None and timing['kind'] == 'before-recording', 'Before-recording extrapolation')
            elif wall == walls[i - 1]:
                a = raw_anchors[i - 1]
                check(e['at'] == a['sim'] and timing['left'] == timing['right'] == a['id'], 'Exact anchor mapping')
            else:
                a, b = raw_anchors[i - 1:i + 1]
                check(e['at'] == b['sim'] and timing['sim_min'] == a['sim'] and timing['sim_max'] == b['sim']
                      and timing['left'] == a['id'] and timing['right'] == b['id'], 'Adjacent measured clock bracket')
                estimate = a['sim'] + (wall-a['wall'])/(b['wall']-a['wall'])*(b['sim']-a['sim'])
                check(abs(timing['estimate'] - estimate) < 1e-9, 'Navigation estimate')
                bracket_widths.append(b['sim'] - a['sim'])

    # Full observation inventory, not a selection pretending to be a complete state stream.
    observation_rows = [(i, r) for i, r in history.items() if r['type'] == 'observation']
    check(len(data['observations']) == len(observation_rows), 'Observation coverage')
    for shown, (line, raw) in zip(data['observations'], observation_rows):
        check(shown['sim'] == raw['sim_time_s'] and shown['capture_sim_time_s'] == raw['payload']['capture_sim_time_s']
              and shown['sequence'] == raw['payload']['sequence'] and shown['detections'] == raw['payload']['detections']
              and shown['station'] == raw['payload']['station'] and shown['source']['line'] == line, 'Observation identity/clock')

    # Independently open the exact compressed SQLite envelope; no original reader code is executed here.
    recording = host / 'native-recording'
    manifest = read(recording / 'container-manifest.json')
    packed = (recording / manifest['database']).read_bytes()
    check(digest(packed) == manifest['sha256'] and len(packed) == manifest['bytes'], 'Recording envelope')
    db_raw = gzip.decompress(packed)
    check(digest(db_raw) == manifest['uncompressed_sha256'] and len(db_raw) == manifest['uncompressed_bytes'], 'Original SQLite bytes')
    db = sqlite3.connect(':memory:')
    db.deserialize(db_raw)
    db.execute('PRAGMA query_only=ON')
    image_rows = db.execute('SELECT id,time,status,reason,rgb,depth,rgb_sha,depth_sha FROM images ORDER BY time,id').fetchall()
    check(len(image_rows) == len(data['availability']), 'Availability coverage')
    frames = {r['id']: r for r in data['frames']}
    for original, available in zip(image_rows, data['availability']):
        ident, time, status, reason, rgb, depth, rgb_hash, depth_hash = original
        check((ident, time, status, reason, rgb_hash, depth_hash) == (available['id'], available['capture_time_s'],
              available['status'], available['reason'], available['rgb_sha256'], available['depth_sha256']), 'Availability record differs')
        if status != 'available':
            check(ident not in frames, 'Unavailable camera pixels invented')
            continue
        shown = frames[ident]
        exported = (output / shown['href']).read_bytes()
        check(rgb == exported and digest(rgb) == rgb_hash and digest(depth) == depth_hash, 'Original image/depth identity')
        pubs = [(i, r) for i, r in observation_rows if r['payload']['capture_sim_time_s'] == time]
        line, pub = pubs[0]
        check(shown['capture_time_s'] == time and shown['published_sim'] == pub['sim_time_s'] and shown['publication_event'] == pub['event_id']
              and shown['source']['line'] == line and shown['capture_wall'] is None, 'Capture/publication join or invented capture clock')
    db.close()
    check(len(frames) == sum(r[2] == 'available' for r in image_rows), 'All retained RGB exported')

    final = read(orch / 'pilot/runtime-after-close.json')
    files = {f['path']: f for f in data['files']}
    expected_final = set(final['files']) | {'Continuity.md'}
    actual_final = {p for p, f in files.items() if any(v['final_only'] and v['timing']['kind'] == 'untimed-final-snapshot' for v in f['versions'])}
    check(actual_final == expected_final, 'Final tree incomplete or fabricated')
    initial = read(orch / 'pilot/runtime-input-hashes.json')
    for path, file in files.items():
        prior = None
        for v in file['versions']:
            if v['text'] is not None:
                raw = v['text'].encode('utf-8')
                check(digest(raw) == v['sha256'] and len(raw) == v['bytes'], 'Displayed file bytes/hash differ')
                expected_diff = None if prior is None or prior['text'] is None else ''.join(difflib.unified_diff(
                    prior['text'].splitlines(keepends=True), v['text'].splitlines(keepends=True),
                    fromfile=path + ' (previous evidenced)', tofile=path + ' (selected evidenced)'))
                check(v['diff'] == expected_diff, 'Diff does not compare adjacent evidenced versions')
            if v['timing']['kind'] == 'untimed-final-snapshot':
                check(v['at'] is None and v['final_only'], 'Final snapshot backdated')
                record = final['files']['.continuity/Continuity.md' if path == 'Continuity.md' else path]
                check(v['sha256'] == record['sha256'] and v['text'].encode('utf-8') == base64.b64decode(record['base64']), 'Final bytes do not match snapshot')
            elif v['evidence'].startswith('Initial hash'):
                check(path in initial and v['sha256'] == initial[path], 'Initial filesystem hash invented')
            elif v['evidence'] == 'Protected atomic continuity commit':
                matches = [r for r in history.values() if r['type'] == 'continuity_committed' and r['payload']['sha256'] == v['sha256']]
                check(len(matches) == 1 and v['at'] == matches[0]['sim_time_s'], 'Protected continuity mapping')
            elif v['evidence'] == 'Exact content read by trusted executor':
                ref = v['read_request_source']
                capture = lines((output / unquote(ref['href'])).resolve())
                request = capture[ref['line']]
                pid = request['message']['params']['processId']
                chunks = [base64.b64decode(r['message']['params']['chunk']) for r in capture.values()
                    if r['kind'] == 'response' and r.get('message', {}).get('method') == 'process/output'
                    and r['message']['params']['processId'] == pid and r['message']['params']['stream'] == 'stdout']
                text, offset = b''.join(chunks).decode('utf-8'), 0
                recovered = {}
                for name in ('live/activation.json', 'live/state.json'):
                    _, length = json.JSONDecoder().raw_decode(text[offset:])
                    recovered[name] = text[offset:offset + length]
                    offset += length
                check(path in recovered and v['text'] == recovered[path], 'Exact startup read bytes')
                check(v['matches_initial_hash'] == (v['sha256'] == initial[path]), 'Read vs initial identity distinction')
            elif v['evidence'].startswith('Derived literal write'):
                request_ref = v['write_request_source']
                source_path = (output / unquote(request_ref['href'])).resolve()
                request = lines(source_path)[request_ref['line']]
                exit_ref = v['source']
                exit_path = (output / unquote(exit_ref['href'])).resolve()
                exit_row = lines(exit_path)[exit_ref['line']]
                check(request['kind'] == 'request' and request['message']['method'] == 'process/start'
                      and exit_row['message']['method'] == 'process/exited' and exit_row['message']['params']['exitCode'] == 0
                      and request['message']['params']['processId'] == exit_row['message']['params']['processId'], 'Successful write process correlation')
                check(v['timing']['write_request_wall'] == request['wall_unix_s'] and v['timing']['write_exit_wall'] == exit_row['wall_unix_s'], 'Write interval')
                if path == 'notes/next-continuity.md':
                    raw = (host / ('continuity-history/' + v['sha256'] + '.md')).read_bytes()
                    check(raw == v['text'].encode('utf-8'), 'Derived note lacks independent retained bytes')
                if v['at'] is not None:
                    i = bisect_right(walls, exit_row['wall_unix_s'])
                    check(v['at'] == raw_anchors[i]['sim'], 'Draft write visible before trusted exit upper bound')
            prior = v
    committed = [r for r in history.values() if r['type'] == 'continuity_committed']
    check(len([v for v in files['Continuity.md']['versions'] if v['evidence'] == 'Protected atomic continuity commit']) == len(committed) == 6, 'Continuity version coverage')
    expected_times = [1.684, 94.768, 189.072, 233.112, 302.358, 302.446, 348.850]
    for milestone, expected in zip(data['milestones'], expected_times):
        check(abs(milestone['at'] - expected) < 1e-6, 'Reference semantic jump clock')
        raw = next(r for r in history.values() if 'world-' + str(r['event_id']) == milestone['event_id'])
        check(raw['sim_time_s'] == milestone['at'], 'Milestone source identity')
    check(len(data['milestones']) == 7, 'Reference milestones missing')
    for reference in data['meta']['links']:
        check((output / unquote(reference['href'])).resolve().is_file(), 'Broken source link')
    for e in data['events']:
        check((output / unquote(e['source']['href'])).resolve().is_file(), 'Broken event evidence link')
    for file in data['files']:
        for v in file['versions']:
            check((output / unquote(v['source']['href'])).resolve().is_file(), 'Broken file evidence link')
    result = {'schema': 'synchronized-replay-independent-verification-1', 'passed': True, 'assertions': assertions,
        'original_inputs_unchanged': len(guard['inputs']), 'original_frozen_sources_unchanged': sum(r['role'] == 'frozen source immutability guard' for r in guard['inputs']),
        'world_events': len(history), 'clock_anchors': len(raw_anchors), 'maximum_sim_bracket_width_s': max(bracket_widths),
        'after_stop_events_by_lane': terminal_counts, 'original_rgb_frames': len(frames),
        'last_rgb_capture_sim_s': max(r['capture_time_s'] for r in frames.values()), 'unavailable_captures': len(image_rows) - len(frames),
        'complete_final_snapshot_regular_files': len(final['files']), 'public_continuity_alias': True,
        'protected_continuity_versions': 6, 'data_sha256': digest((output / 'data.json').read_bytes()),
        'scope': 'Independent original-byte, clock-bracket, publication, observable-channel, final-tree and version/diff checks; browser QA is separate.'}
    (output / 'verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    audit(a.output.resolve())
