"""Read-only accounting of the failed first launch; never a scientific endpoint."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil
from common import save, read, inventory, canonical, sha

FAILED = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v1')

def run(out):
    out.mkdir(parents=True, exist_ok=False)
    manifest = inventory(FAILED)
    save(out/'preserved-manifest.json', manifest)
    root = FAILED/'baseline'
    session = root/'sessions/session-00001'
    journal = session/'workspace/journal'
    stats = defaultdict(lambda: Counter())
    kinds = Counter(); previous = '0'*64; state = None; seen = set()
    first = last = None; rejected = []
    for line in (journal/'mutations.jsonl').open('rb'):
        row = json.loads(line); digest = row.pop('record_sha256')
        assert hashlib.sha256(canonical(row)).hexdigest() == digest
        assert row['previous_record_sha256'] == previous
        previous = digest; kinds[row['type']] += 1
        first = first or row['monotonic_ns']; last = row['monotonic_ns']
        if row['type'] == 'initial':
            state = row['state']
            seen.update(n.get('sha256') for n in state['nodes'].values())
        if row['type'] == 'mutation':
            args = row['arguments']; path = args.get('path', args.get('old', '(metadata)'))
            s = stats[path]; s[row['operation']+'_count'] += 1
            s['input_bytes'] += args.get('bytes', 0)
            s['record_bytes'] += len(line)
            for node in row['delta']['nodes']['set'].values():
                key = node.get('sha256')
                if key and key not in seen:
                    seen.add(key); s['new_full_objects'] += 1; s['new_full_object_bytes'] += node['size']
            for area in ('paths', 'nodes'):
                for key in row['delta'][area]['remove']: del state[area][key]
                state[area].update(row['delta'][area]['set'])
            assert hashlib.sha256(canonical(state)).hexdigest() == row['after_state_sha256']
        if row['type'] == 'rejected_mutation': rejected.append(row)
    save(out/'last-retained-namespace.json', state)
    objects = list((journal/'objects').iterdir())
    for path, s in stats.items():
        node = state['nodes'].get(str(state['paths'].get(path)), {})
        s['last_retained_size'] = node.get('size', 0)
    top = sorted((dict(path=p, **s) for p,s in stats.items()), key=lambda s:s.get('new_full_object_bytes',0), reverse=True)
    ledger = session/'native/codehost-transport-v3.jsonl'
    ledger_kinds = Counter(); ledger_bytes = Counter(); prev = None; count = 0
    for line in ledger.open('rb'):
        row = json.loads(line); digest = row.pop('record_sha256'); count += 1
        assert hashlib.sha256(canonical(row)).hexdigest() == digest
        assert row['previous_sha256'] == prev and row['sequence'] == count
        prev = digest; ledger_kinds[row['kind']] += 1; ledger_bytes[row['kind']] += len(line)
    input_bytes = sum(s['input_bytes'] for s in stats.values())
    object_bytes = sum(p.stat().st_size for p in objects)
    summary = dict(passed=True, stage='read-only-failed-launch-diagnosis', official_sessions=0,
        original_root=str(FAILED), original_files=len(manifest), original_bytes=sum(v['bytes'] for v in manifest.values()),
        preserved_manifest_sha256=sha(out/'preserved-manifest.json'), journal_records=dict(kinds),
        journal_bytes=(journal/'mutations.jsonl').stat().st_size, object_count=len(objects), object_bytes=object_bytes,
        input_bytes=input_bytes, object_to_input_ratio=object_bytes/input_bytes,
        elapsed_retained_s=(last-first)/1e9, workspace_last_bytes=sum(n['size'] for n in state['nodes'].values()),
        top_paths=top, rejected_mutations=rejected, transport_records=count, transport_bytes=ledger.stat().st_size,
        transport_kinds=dict(ledger_kinds), transport_bytes_by_kind=dict(ledger_bytes),
        execution=read(next(root.glob('execution-result-*.json'))),
        free_D_bytes=shutil.disk_usage('D:/').free,
        schedule_sha256=sha(FAILED/'hidden-schedule.json'),
        maps_pristine=inventory(FAILED/'maps/filesystem')==read(FAILED/'maps/initial-filesystem.json') and not (FAILED/'maps/sessions').exists())
    save(out/'result.json',summary)
    print(canonical({k:v for k,v in summary.items() if k not in ('top_paths','execution','rejected_mutations')}).decode())
    print(canonical(top[:8]).decode())
    return True

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output)
