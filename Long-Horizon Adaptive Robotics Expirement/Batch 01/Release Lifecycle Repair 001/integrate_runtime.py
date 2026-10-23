"""Root integration of reviewed staged code into the independent Runtime 004."""
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
EXP = HERE.parent.parent
OLD = EXP / 'Runtime'
NEW = EXP / 'Runtime 004'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(path):
    return {'path': str(path), 'sha256': digest(path)}


def write(path, value, mode='x'):
    with path.open(mode, encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def main():
    output = HERE / 'runtime-integration-001.json'
    if output.exists():
        raise ValueError('Integration record already exists')
    manifest_path = HERE / 'change-inventory.json'
    manifest = json.loads(manifest_path.read_text())
    before = {p.name: digest(p) for p in OLD.glob('*.py')}
    copied = json.loads((HERE / 'runtime-base-copy-001.json').read_text())
    assert before == copied['source_files_before'] == copied['source_files_after']
    assert {p.name: digest(p) for p in NEW.glob('*.py')} == before
    allowed = {'experiment.py', 'model_runtime.py', 'test_model_lifecycle.py', 'test_model_runtime.py'}
    assert set(manifest['runtime_delta_allowlist']) == allowed
    assert {row['name'] for row in manifest['runtime_delta']} == allowed
    prior_manifest_ref = reference(manifest_path)
    for row in manifest['runtime_delta']:
        name = row['name']
        if row['original'] is not None:
            assert digest(OLD / name) == row['original']['sha256'] == before[name]
        else:
            assert name not in before and not (NEW / name).exists()
        assert digest(Path(row['staged']['path'])) == row['staged']['sha256']
        row['target_path'] = str(NEW / name)
    manifest['installation_target_note'] = 'Root corrected proposal target metadata to independent Runtime 004 before installation; original-source refs and all staged bytes remain unchanged.'
    manifest['prior_proposal_manifest'] = prior_manifest_ref
    # Preserve the exact prior proposal rather than invalidating its historical ref.
    prior = HERE / 'change-inventory-proposal-001.json'
    with prior.open('xb') as stream:
        stream.write(manifest_path.read_bytes())
    manifest['prior_proposal_manifest']['path'] = str(prior)
    write(manifest_path, manifest, 'w')
    for row in manifest['runtime_delta']:
        target = NEW / row['name']
        target.write_bytes(Path(row['staged']['path']).read_bytes())
    after = {p.name: digest(p) for p in NEW.glob('*.py')}
    expected = {**before, **{row['name']: row['staged']['sha256'] for row in manifest['runtime_delta']}}
    assert after == expected and {p.name: digest(p) for p in OLD.glob('*.py')} == before
    narrative_path = EXP / 'Engineering Investigation 004/current-implementation-narrative.json'
    narrative = json.loads(narrative_path.read_text(encoding='utf-8'))
    line_changes = []
    for row in narrative['source_refs']:
        name = row['member']
        row['sha256'] = after[name]
        row['source'] = 'Runtime 004/' + name
        old_lines = (OLD / name).read_text(encoding='utf-8').splitlines()
        new_lines = (NEW / name).read_text(encoding='utf-8').splitlines()
        mapping = {}
        for tag, a, b, c, d in difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False).get_opcodes():
            if tag == 'equal':
                mapping.update({i + 1: c + (i-a) + 1 for i in range(a,b)})
        old_range = row['lines']
        mapped = []
        for token in old_range.split(', '):
            match = re.fullmatch(r'(\d+)(?:-(\d+))?', token)
            assert match, token
            start, end = int(match[1]), int(match[2] or match[1])
            # Existing narrative cites unchanged implementation text. Fail if a
            # claim's old endpoint was replaced rather than guessing a new line.
            assert start in mapping and end in mapping, (name, token)
            first, last = mapping[start], mapping[end]
            mapped.append(str(first) if first == last else f'{first}-{last}')
        row['lines'] = ', '.join(mapped)
        line_changes.append({'member': name, 'before': old_range, 'after': row['lines']})
    narrative['recorded_at'] = datetime.now(timezone.utc).isoformat()
    narrative['scope'] = "Source-bound description of implemented Runtime 004 Batch 01 mechanisms. Display only when every named source hash matches the selected revision's immutable ZIP. Original designs and historical records are unchanged. The timeout lifecycle change preserves model, prompt, policy and numerical budgets; this description itself makes no performance, qualification or readiness claim."
    write(narrative_path, narrative, 'w')
    result = {'schema_version': 'runtime-lifecycle-integration-1',
        'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
        'patch_manifest': reference(manifest_path), 'base_copy': reference(HERE / 'runtime-base-copy-001.json'),
        'original_runtime': str(OLD), 'new_runtime': str(NEW),
        'original_before': before, 'original_after': {p.name: digest(p) for p in OLD.glob('*.py')},
        'new_runtime_sources': after, 'original_sources_unchanged': True,
        'runtime_delta': [row['name'] for row in manifest['runtime_delta']],
        'narrative': reference(narrative_path), 'narrative_line_map': line_changes,
        'tests_executed': False, 'qualification_granted': False, 'readiness_granted': False}
    write(output, result)
    print(json.dumps({'integration': reference(output), 'patch_manifest': reference(manifest_path),
                      'runtime_files': len(after), 'narrative_line_map': line_changes}))


if __name__ == '__main__':
    main()
