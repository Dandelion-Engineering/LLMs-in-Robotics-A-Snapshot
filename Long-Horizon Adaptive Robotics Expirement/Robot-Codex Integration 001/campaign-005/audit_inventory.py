"""Independent journal-state comparison for every published inventory."""
import copy
import hashlib
import json
from pathlib import Path
import stat


def verify_inventory(journal):
    journal = Path(journal)
    state = None
    prior = None
    prior_hash = None
    snapshots = []
    for line in (journal/'mutations.jsonl').read_bytes().splitlines():
        row = json.loads(line)
        if row['type'] == 'initial':
            state = copy.deepcopy(row['state'])
        elif row['type'] == 'mutation':
            for area in ('paths', 'nodes'):
                for key in row['delta'][area]['remove']:
                    del state[area][key]
                state[area].update(row['delta'][area]['set'])
            if row['operation'] != 'rename' or row['arguments']['new'] != '/ArtifactInventory.json':
                continue
            node = state['nodes'][str(state['paths']['/ArtifactInventory.json'])]
            content = (journal/'objects'/node['sha256']).read_bytes()
            value = json.loads(content)
            assert value['schema'] == 'campaign005-artifact-inventory-1'
            assert value['author'] == 'framework'
            assert value['observed_before_session'] == row['session_id']
            assert row['process']['namespace_role'] == 'outer-runtime'
            assert value['previous_inventory_sha256'] == prior_hash
            expected = {}
            for path, inode in state['paths'].items():
                if not path.startswith(('/notes/', '/programs/', '/.continuity/')):
                    continue
                item = state['nodes'][str(inode)]
                if stat.S_ISDIR(item['mode']):
                    continue
                if stat.S_ISREG(item['mode']):
                    identity = {'kind': 'file', 'bytes': item['size'], 'sha256': item['sha256']}
                else:
                    assert stat.S_ISLNK(item['mode'])
                    identity = {'kind': 'symlink', 'target': item['target'],
                                'sha256': hashlib.sha256(item['target'].encode('utf-8')).hexdigest()}
                public_path = 'Continuity.md' if path == '/.continuity/Continuity.md' else path[1:]
                expected[public_path] = identity
            entries = {e['path']: e for e in value['entries']}
            assert len(entries) == len(value['entries'])
            assert {p:e['identity'] for p,e in entries.items()} == expected
            old_entries = {e['path']:e for e in prior['entries']} if prior else {}
            for path, entry in entries.items():
                old = old_entries.get(path)
                changed = old is None or old['identity'] != entry['identity']
                assert entry['snapshot_version'] == (old['snapshot_version'] if old else 0) + int(changed)
                assert entry['first_observed_before_session'] == (old['first_observed_before_session'] if old else row['session_id'])
                assert entry['last_change_observed_before_session'] == (row['session_id'] if changed else old['last_change_observed_before_session'])
                assert entry['change_since_previous_snapshot'] == ('added' if old is None else 'changed' if changed else 'unchanged')
            assert value['removed_since_previous_snapshot'] == sorted(set(old_entries)-set(entries))
            snapshots.append({'sequence':row['sequence'],'session_id':row['session_id'],
                              'sha256':node['sha256'],'inventory':value})
            prior = value
            prior_hash = node['sha256']
    assert snapshots, 'No structural inventory publication'
    return {'passed':True, 'snapshots':snapshots, 'count':len(snapshots)}
