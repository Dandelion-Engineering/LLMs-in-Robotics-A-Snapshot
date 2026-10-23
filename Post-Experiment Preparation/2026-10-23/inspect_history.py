"""Read historical v4 evidence only; write derived, allowlisted inspection outputs.

No controller, World, historical program, or dynamics step is executed.
Run through the shared queue. Paths are deliberately explicit and historical.
"""
from pathlib import Path
import bisect
import collections
import hashlib
import importlib.util
import json
import sys

OUT = Path(__file__).resolve().parent
SCRATCH = OUT / '.local'
REPO = OUT.parents[1]
APP = REPO / 'Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'
ROOTS = {
    'baseline': Path('D:/Dandelion Engineering/LLMs in Robotics/Dandelion-Apartment-Experiment/official/apartment-v4/baseline'),
    'maps': Path('C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics/Local Experiment Data/apartment-v4-maps/recovery-session63/recovered-run'),
}
inputs = {}

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def raw(path):
    path = Path(path)
    data = path.read_bytes()
    old = inputs.setdefault(str(path), {'sha256': sha(data), 'bytes': len(data)})
    assert old == {'sha256': sha(data), 'bytes': len(data)}, path
    return data

def read(path):
    return json.loads(raw(path))

def lines(path):
    return [json.loads(x) for x in raw(path).splitlines() if x]

def save(name, value):
    target = SCRATCH if name in ['file-receipts.json', 'public-process-requests.json', 'session-reports.json',
                                'baseline-physical-events.json', 'maps-physical-events.json'] else OUT
    target.mkdir(exist_ok=True)
    (target / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

def auth_chain(rows, digest_field, previous_field):
    previous = '0' * 64
    for i, r in enumerate(rows, 1):
        d = {k: v for k, v in r.items() if k != digest_field}
        encoded = json.dumps(d, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
        assert r['sequence'] == i and r[previous_field] == previous and sha(encoded) == r[digest_field], i
        previous = r[digest_field]

def bound(row, clocks):
    times = [x['payload']['linux']['linux_monotonic_ns'] for x in clocks]
    i = bisect.bisect_left(times, row['monotonic_ns'])
    if not 0 < i < len(clocks):
        return None
    a, b = clocks[i-1], clocks[i]
    if a['payload']['before']['clock_epoch'] != b['payload']['after']['clock_epoch']:
        return None
    return {'sim_time': [a['payload']['before']['sim_time'], b['payload']['after']['sim_time']],
            'clock_bridge_sequences': [a['sequence'], b['sequence']]}

def inspect():
    catalog = {}
    receipts = []
    commands = []
    reports = []
    for condition, root in ROOTS.items():
        run = read(root/'run.json')
        for name in ['scene.py', 'world.py', 'recording.py', 'viewer.py', 'viewer.html', 'controller.py']:
            assert sha(raw(APP/name)) == run['source_identity']['apartment/'+name], name
        events = lines(root/'events.jsonl')
        auth_chain(events, 'sha256', 'previous')
        session = 0
        for e in events:
            if e['kind'] == 'session_started':
                session = e['payload']['session']
            e['_session'] = session
        catalog[condition] = {'root': str(root), 'run_id': run['run_id'], 'revision_id': run['revision_id'],
                              'source_identity_verified': True,
                              'event_counts': dict(collections.Counter(e['kind'] for e in events)),
                              'boundaries': [{k: v for k, v in e.items() if k != 'previous'} for e in events
                                             if e['kind'] in ['session_started', 'session_closed', 'task_success']],
                              'images': [{ 'event': e['sequence'], 'session': e['_session'], 'sim_time': e['sim_time'],
                                           'camera': e['payload']['camera'], 'sequence': e['payload']['sequence'],
                                           'sha256': e['payload']['image_sha256']}
                                          for e in events if e['kind'] == 'sensor_capture']}
        public_events = []
        for e in events:
            if e['kind'] in ['command_requested', 'command_terminal', 'task_success']:
                public_events.append(e)
        save(condition+'-physical-events.json', public_events)
        for folder in sorted((root/'sessions').glob('session-*')):
            n = int(folder.name.split('-')[-1])
            jp = folder/'workspace/journal/mutations.jsonl'
            journal = lines(jp)
            auth_chain(journal, 'record_sha256', 'previous_record_sha256')
            clocks = lines(folder/'workspace/clock-bridge.jsonl')
            auth_chain(clocks, 'sha256', 'previous')
            paths = {}
            nodes = {}
            for r in journal:
                if r['type'] == 'initial':
                    paths = dict(r['state']['paths']); nodes = dict(r['state']['nodes'])
                if r['type'] == 'mutation':
                    for area, state in [('paths', paths), ('nodes', nodes)]:
                        for key in r['delta'][area]['remove']: state.pop(key, None)
                        state.update(r['delta'][area]['set'])
                path = r.get('path', r.get('arguments', {}).get('path', ''))
                if not (path.startswith(('/Maps/', '/Programs/Learned/', '/Playbooks/Learned/', '/Artifacts/', '/SessionReports/'))
                        or path in ['/SummaryOfOnlyNecessaryContext.md', '/LongTermMemory.md']):
                    continue
                if r['type'] not in ['read', 'mutation']: continue
                node = nodes.get(str(paths.get(path)), {})
                receipts.append({'condition': condition, 'session': n, 'journal': str(jp),
                    'sequence': r['sequence'], 'record_sha256': r['record_sha256'],
                    'operation': r.get('operation', r['type']), 'path': path,
                    'content_sha256': r.get('content_sha256', node.get('sha256')),
                    'returned_sha256': r.get('returned_sha256'), 'bytes': r.get('bytes', node.get('size')),
                    'offset': r.get('offset'), 'pid': r.get('pid'),
                    'monotonic_ns': r['monotonic_ns'], 'wall_unix_ns': r['wall_unix_ns'],
                    'clock_bound': bound(r, clocks)})
            req = folder/'native/executor-1-requests.jsonl'
            for r in lines(req):
                if r.get('method') != 'process/start': continue
                p = r['params']; argv = p['argv']
                if any(x in '\n'.join(argv) for x in ['Programs/Learned/', 'Maps/', 'SessionReports/', 'SummaryOfOnlyNecessaryContext.md']):
                    commands.append({'condition': condition, 'session': n, 'source': str(req), 'id': r['id'],
                                     'process_id': p['processId'], 'tool_call_id': p.get('metadata',{}).get('toolCallId'),
                                     'argv': argv})
            report = root/'filesystem/SessionReports'/f'2026-10-10-session-{n:03}.md'
            body = raw(report).decode('utf-8')
            reports.append({'condition': condition, 'session': n, 'source': str(report), 'sha256': sha(raw(report)), 'text': body})
        endpoint = read(root/'latest-checkpoint.json')
        # Relocated Baseline metadata intentionally retains original D: locators.
        cp = root/'checkpoints'/Path(endpoint['path']).name
        assert sha(raw(cp/'manifest.json')) == endpoint['manifest_sha256']
        assert sha(raw(cp/'state.json')) == endpoint['state_sha256']
        manifest = read(cp/'manifest.json')
        checked = 0
        for rel, identity in manifest['files'].items():
            p = cp/rel
            if rel.startswith('filesystem/') and p.suffix in ['.md', '.py', '.json', '.jsonl']:
                b = raw(p); assert len(b) == identity['bytes'] and sha(b) == identity['sha256'], p
                assert raw(root/rel) == b, p
                checked += 1
        catalog[condition]['final_checkpoint'] = {'folder': str(cp), 'state_sha256': endpoint['state_sha256'],
                                                 'manifest_sha256': endpoint['manifest_sha256'], 'files_authenticated': checked}
    save('history-catalog.json', catalog)
    save('file-receipts.json', receipts)
    save('public-process-requests.json', commands)
    save('session-reports.json', reports)
    save('inputs.json', inputs)
    print('Authenticated sources, event/journal/clock chains, final report/artifact exports:',
          len(reports), 'reports;', len(receipts), 'selected filesystem receipts;', len(commands), 'public process requests.')

if __name__ == '__main__':
    inspect()
