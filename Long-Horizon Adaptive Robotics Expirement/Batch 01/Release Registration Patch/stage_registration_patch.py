"""Build an unapplied exact-base candidate; never edit Runtime or the Map."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_SHA256 = '8473087dfba3551fcc742dd6a45b8f0d6c0690a1cb5e804dc8acd30f99748ac6'

OLD = """    bundle=Path(artifacts['code_bundle']);manifest_path=root/'runs'/(m['run_id']+'.json')
    if not existing:
"""
NEW = """    bundle=Path(artifacts['code_bundle']);manifest_path=root/'runs'/(m['run_id']+'.json')
    code_index=reference(freeze['artifacts']['code'],freeze_path.parent);code=load(code_index)
    if reference(code['bundle'],code_index.parent)!=bundle.resolve():raise ReleaseError('Registered code bundle differs from frozen index')
    attachments=retained_revision_attachments(records.MAP,m['release_id'],bundle,code['bundle']['sha256'],freeze_path,m['freeze_sha256'])
    if existing and existing.get('attachments')!=attachments:raise ReleaseError('Frozen revision retained attachments differ')
    if not existing:
"""
OLD_ATTACHMENTS = "            'attachments':[map_reference('Immutable executable source bundle',bundle),map_reference('Frozen release',freeze_path,m['freeze_sha256'])],"
NEW_ATTACHMENTS = "            'attachments':attachments,"


def candidate_bytes(raw):
    if hashlib.sha256(raw).hexdigest() != BASE_SHA256:
        raise ValueError('Exact Runtime release_runner.py base differs; do not apply')
    newline = '\r\n' if b'\r\n' in raw else '\n'
    source = raw.decode('utf-8').replace('\r\n', '\n')
    fragment = (HERE / 'registration_fragment.py.txt').read_text(encoding='utf-8')
    for old, new in (('import re\n', 'import re\nimport stat\n'),
                     ('def register_attempt(context):\n', fragment + 'def register_attempt(context):\n'),
                     (OLD, NEW), (OLD_ATTACHMENTS, NEW_ATTACHMENTS)):
        if source.count(old) != 1:
            raise ValueError('Missing/ambiguous exact patch anchor')
        source = source.replace(old, new)
    return source.replace('\n', newline).encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.parent != HERE or output.exists():
        raise ValueError('Fresh direct staging directory required; Runtime cannot be a target')
    original = args.source.read_bytes(); candidate = candidate_bytes(original)
    output.mkdir()
    (output / 'release_runner.base.py').write_bytes(original)
    (output / 'release_runner.candidate.py').write_bytes(candidate)
    report = {'status': 'unapplied', 'base_sha256': BASE_SHA256,
        'candidate_sha256': hashlib.sha256(candidate).hexdigest(),
        'source': str(args.source.resolve()), 'tests_executed': False,
        'scope': 'Source staging only; no Runtime/Map edit, registration, runs, retries or seed changes'}
    (output / 'stage.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
