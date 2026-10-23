"""Freeze and register exactly one new prospective candidate diagnostic."""
import hashlib
import json
import common

def main():
    if common.MANIFEST.exists() or common.SNAPSHOT.parent.exists():
        raise ValueError('Existing declaration footprint; never prepare twice')
    for name, identity in common.read(common.PREVIOUS)['sources'].items():
        path = common.REPO/name
        if identity != {'bytes': path.stat().st_size, 'sha256': common.sha(path)}:
            raise ValueError('Prior source changed: '+name)
    value = common.read(common.REFERENCE)
    inputs = sorted(set(common.required_inputs()) | {
        (common.HERE/'tests-001.txt').relative_to(common.REPO).as_posix()})
    value.update(run_id=common.RUN, framework_revision=common.REVISION, qualification_stage=common.STAGE,
                 outer_campaign_protocol=common.PROTOCOL, model_turns_max=1,
                 runtime_workspace=str(common.WORKSPACE), runtime_input_files=inputs)
    common.validate_manifest(value)
    common.output_paths(common.EVIDENCE, common.HOST, common.WORKSPACE)
    common.save(common.MANIFEST, value)
    registry = common.load(common.CAMPAIGN/'registry.py', 'diagnostic006_registry')
    original = registry.common
    def stamp(identifier):
        value = original(identifier); value['author'] = 'Codex session 19'; return value
    registry.common = registry.prior.common = stamp
    map_root = common.SNAPSHOT.parents[2]
    previous = {name: (map_root/name).read_bytes() for name in
                ('architectures.jsonl', 'revisions.jsonl', 'runs.jsonl', 'results.jsonl', 'notes.jsonl')}
    frozen = registry.freeze(common.MANIFEST, common.REVISION)
    registered = registry.add_run(common.MANIFEST, common.REVISION)
    common.validate(common.MANIFEST, common.SNAPSHOT)
    preservation = {}
    for name, raw in previous.items():
        current = (map_root/name).read_bytes()
        assert current.startswith(raw)
        assert len(current[len(raw):].splitlines()) == (1 if name in ('revisions.jsonl', 'runs.jsonl') else 0)
        preservation[name] = {'prefix_bytes': len(raw), 'prefix_sha256': hashlib.sha256(raw).hexdigest(), 'preserved': True}
    receipt = {'run_id': common.RUN, 'revision': common.REVISION,
        'manifest_sha256': common.sha(common.MANIFEST), 'snapshot_sha256': common.sha(common.SNAPSHOT),
        'source_count': len(common.read(common.SNAPSHOT)['sources']), 'preserved_prior_inputs': 986,
        'freeze': frozen, 'registration': registered, 'canonical_prefixes': preservation, 'launched': False}
    common.save(common.ROOT/'preparation.json', receipt)
    print(json.dumps(receipt))

if __name__ == '__main__': main()
