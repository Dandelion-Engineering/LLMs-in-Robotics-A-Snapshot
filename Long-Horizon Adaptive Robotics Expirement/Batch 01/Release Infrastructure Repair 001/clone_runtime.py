"""Preserve r1, copy its small runtime sources, and hard-link immutable vendor bytes."""
from pathlib import Path
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone

EXP = Path(__file__).resolve().parents[2]
SOURCE = EXP / 'Runtime'
TARGET = EXP / 'Runtime Release 002'


def main():
    if TARGET.exists():
        raise ValueError('Fresh runtime directory required')
    source_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.glob('*.py')}
    TARGET.mkdir()
    for p in SOURCE.iterdir():
        if p.is_file():
            shutil.copy2(p, TARGET / p.name)
    linked = 0
    for p in (SOURCE / 'vendor').rglob('*'):
        if p.is_symlink():
            raise ValueError('Unexpected vendor symlink')
        target = TARGET / p.relative_to(SOURCE)
        if p.is_dir():
            target.mkdir(exist_ok=True, parents=True)
        elif p.is_file():
            target.parent.mkdir(exist_ok=True, parents=True)
            os.link(p, target)
            if not os.path.samefile(p, target):
                raise ValueError('Vendor hardlink identity differs')
            linked += 1
    for name, sha in source_hashes.items():
        if hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() != sha or hashlib.sha256((TARGET / name).read_bytes()).hexdigest() != sha:
            raise ValueError('Source copy changed')
    record = {'schema_version': 'runtime-version-copy-1', 'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
              'source': str(SOURCE), 'target': str(TARGET), 'originals_unchanged': True, 'python_files': source_hashes,
              'vendor_hardlinks': linked, 'vendor_policy': 'Shared exact file identities, never write through either alias. Final prepared artifacts independently hash all selected assets.',
              'scored_or_physical_work': False}
    out = Path(__file__).with_name('runtime-copy-001.json')
    with out.open('x', encoding='utf-8') as stream:
        json.dump(record, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'copied_python_files': len(source_hashes), 'vendor_hardlinks': linked, 'originals_unchanged': True}))


if __name__ == '__main__':
    main()
