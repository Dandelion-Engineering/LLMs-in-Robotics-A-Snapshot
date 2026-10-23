"""Read-only preflight of retained public evidence; never starts a model or simulator."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
C = REPO / 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002'


def read(p):
    return json.loads(p.read_text('utf-8'))


def rows(p):
    return [json.loads(s) for s in p.read_text('utf-8').splitlines() if s.strip()]


def main(output):
    if output.exists():
        raise ValueError('Fresh preflight output required')
    result = []
    for a in read(C / 'execution-plan.json')['attempts']:
        slot = C / 'execution' / a['run_id']
        d = read(slot / 'disposition.json')
        if not (d.get('validity') == 'valid' and d.get('task_outcome') == 'success'):
            continue
        assessment = read(slot / 'assessment.json')
        host, orch = Path(a['host_evidence']), Path(a['evidence'])
        final = read(orch / 'pilot/runtime-after-close.json')
        keys = defaultdict(set)
        phases = Counter()
        for r in rows(orch / 'pilot/client/events.jsonl'):
            item = (r.get('params') or {}).get('item') or {}
            if r.get('method') in ('item/started', 'item/completed'):
                keys[item.get('type', 'unknown')].update(item)
                phases[(item.get('type', 'unknown'), item.get('phase'))] += 1
        commands, methods = [], {}
        for p in sorted((orch / 'pilot').glob('executor-*-capture.jsonl')):
            capture = rows(p)
            methods[p.name] = dict(Counter((r.get('kind'), r.get('message', {}).get('method')) for r in capture).__class__(
                {str(k):v for k,v in Counter((r.get('kind'), r.get('message', {}).get('method')) for r in capture).items()}))
            for line, r in enumerate(capture, 1):
                m = r.get('message') or {}
                params = m.get('params') or {}
                if r.get('kind') == 'request' and m.get('method') == 'process/start':
                    commands.append({'capture':p.name,'line':line,'process_id':params.get('processId'),
                                     'tool_id':params.get('metadata', {}).get('toolCallId'),
                                     'argv':params.get('argv'), 'wall':r.get('wall_unix_s')})
        h = rows(host / 'public-history.jsonl')
        broker = rows(orch / 'pilot/broker-events.jsonl')
        result.append({'run_id':a['run_id'],'ordinal':a['ordinal'],'family':a['family'],
            'seed':assessment['seed'],'noise_seed':assessment['noise_seed'],
            'job_id':assessment['queue_job_id'], 'disposition':d,
            'final_scope':final['scope'],'final_files':{k:{x:v.get(x) for x in ('bytes','sha256')} for k,v in final['files'].items()},
            'snapshots_equal':final==read(orch/'pilot/runtime-before-close.json'),
            'client_item_keys':{k:sorted(v) for k,v in keys.items()}, 'client_phases':{str(k):v for k,v in phases.items()},
            'capture_methods':methods,'processes':commands,
            'world_types':dict(Counter(r['type'] for r in h)),
            'world_payload_keys':{k: sorted(set().union(*(set(r.get('payload',{})) for r in h if r['type']==k))) for k in set(r['type'] for r in h)},
            'broker_paths':dict(Counter(r.get('path') for r in broker)),
            'broker_keys':sorted(set().union(*(set(r) for r in broker))),
            'program_records':assessment.get('program_records'),
            'inventory_files':[{k:r[k] for k in ('root','path','bytes')} for r in assessment['evidence_inventory']]})
    if len(result)!=10:
        raise ValueError(f'Expected ten existing valid successes, got {len(result)}')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n','utf-8')
    print(json.dumps({'runs':len(result),'families':dict(Counter(r['family'] for r in result)),
        'process_requests':sum(len(r['processes']) for r in result),
        'final_files':sum(len(r['final_files']) for r in result),'output_sha256':hashlib.sha256(output.read_bytes()).hexdigest()}))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output)
