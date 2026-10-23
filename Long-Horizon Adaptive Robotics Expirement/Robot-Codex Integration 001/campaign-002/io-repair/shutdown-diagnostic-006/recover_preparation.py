"""Authenticate the completed freeze after its redundant add_run was refused.

No map append, source edit, footprint removal, queue submission or native call.
"""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'single-interrupt-diagnostic-v6'))
import common

def binding(path): return {'bytes': path.stat().st_size, 'sha256': common.sha(path)}

def main():
    manifest, frozen = common.validate(common.MANIFEST, common.SNAPSHOT)
    common.output_paths(common.EVIDENCE, common.HOST, common.WORKSPACE)
    if common.RECORDS.exists(): raise ValueError('Unexpected launch footprint')
    root = common.SNAPSHOT.parents[2]
    run_bytes = (root/'runs.jsonl').read_bytes()
    revision_bytes = (root/'revisions.jsonl').read_bytes()
    runs = [json.loads(line) for line in run_bytes.splitlines()]
    revisions = [json.loads(line) for line in revision_bytes.splitlines()]
    matching = [r for r in runs if r['id'] == common.RUN]
    matching_revisions = [r for r in revisions if r['id'] == common.REVISION]
    assert len(matching) == len(matching_revisions) == 1
    assert matching[0] == common.read(common.SNAPSHOT.parent/'run-record.json')
    assert matching_revisions[0] == common.read(common.SNAPSHOT.parent/'revision-record.json')
    assert matching[0]['revision_id'] == common.REVISION
    assert matching[0]['condition_details']['manifest'] == manifest
    for name, identity in common.read(common.PREVIOUS)['sources'].items():
        assert frozen['sources'][name] == identity == binding(common.REPO/name)
    results = [json.loads(line) for line in (root/'results.jsonl').read_bytes().splitlines()]
    assert not any(r['run_id'] == common.RUN for r in results)
    unregistered = common.SNAPSHOT.parent/'runs'/(common.RUN+'.json')
    assert unregistered.is_file()
    value = {'schema': 'campaign002-preparation-recovery-1', 'run_id': common.RUN, 'revision': common.REVISION,
        'failure': {'stage': 'redundant add_run after freeze already registered the run',
            'type': 'MapError', 'message': 'runs.jsonl:474: duplicate global id '+common.RUN,
            'prepare_source': binding(HERE.parent/'single-interrupt-diagnostic-v6/prepare.py')},
        'resolution': 'Retain the one canonical frozen run; do not re-register or rerun prepare.',
        'unregistered_duplicate_file_preserved': {'path': str(unregistered), **binding(unregistered)},
        'manifest_sha256': common.sha(common.MANIFEST), 'snapshot_sha256': common.sha(common.SNAPSHOT),
        'source_count': len(frozen['sources']), 'preserved_prior_inputs': 986,
        'one_canonical_run_verified': True, 'one_canonical_revision_verified': True,
        'source_and_archive_validation_passed': True, 'launch_footprint_absent': True,
        'canonical': {'runs.jsonl': binding(root/'runs.jsonl'), 'revisions.jsonl': binding(root/'revisions.jsonl')}}
    common.save(HERE/'preparation-recovery.json', value)
    print(json.dumps({k:v for k,v in value.items() if k not in ('canonical', 'failure', 'unregistered_duplicate_file_preserved')}))

if __name__ == '__main__': main()
