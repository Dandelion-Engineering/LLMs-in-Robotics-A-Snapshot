"""Queued, fresh versioned runtime copy; preserve the frozen original bytes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys

HERE = Path(__file__).resolve().parent
EXP = HERE.parent.parent
SOURCE = EXP / 'Runtime'
DESTINATION = EXP / 'Runtime 004'
sys.path.insert(0, str(SOURCE))
import release_runner


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    job = release_runner.queued_job(Path(__file__))
    if DESTINATION.exists():
        raise ValueError('Destination already exists; never fill or overwrite a partial copy')
    record = HERE / 'runtime-base-copy-001.json'
    if record.exists():
        raise ValueError('Copy record already exists')
    files = [p for p in SOURCE.iterdir() if p.is_file()]
    files += [p for p in (SOURCE / 'vendor').rglob('*') if p.is_file()]
    for path in files:
        if any(stat.S_ISLNK(q.lstat().st_mode) or getattr(q.lstat(), 'st_file_attributes', 0) & 0x400
               for q in (path, *path.parents) if q == SOURCE or SOURCE in q.parents):
            raise ValueError('Reparse source refused: ' + str(path))
    sources = {p.name: digest(p) for p in SOURCE.glob('*.py')}
    index = json.loads((EXP / 'Evidence/prepared-artifacts/batch01-eval-r3-final/code.json').read_text())
    expected = {Path(r['path']).name: r['sha256'] for r in index['files'] if Path(r['path']).parent == SOURCE}
    if sources != expected:
        raise ValueError('Original Runtime differs from frozen r3')
    DESTINATION.mkdir()
    records = []
    for path in sorted(files):
        relative = path.relative_to(SOURCE)
        target = DESTINATION / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        before = digest(path)
        # Only pinned large vendor assets share storage. Runtime code and
        # metadata are independent copies. Neither alias may be edited.
        linked = relative.parts[0] == 'vendor' and path.stat().st_size >= 1024 * 1024
        if linked:
            os.link(path, target)
            if not os.path.samefile(path, target):
                raise ValueError('Hard-link identity failed')
        else:
            shutil.copy2(path, target)
        if digest(target) != before or digest(path) != before:
            raise ValueError('Bytes changed during versioned copy: ' + str(path))
        records.append({'source': str(path), 'target': str(target), 'relative_path': relative.as_posix(),
                        'sha256': before, 'bytes': path.stat().st_size,
                        'storage': 'hard_link_immutable_vendor' if linked else 'independent_copy'})
    after = {p.name: digest(p) for p in SOURCE.glob('*.py')}
    if sources != after:
        raise ValueError('Original source changed')
    value = {'schema_version': 'versioned-runtime-base-copy-1', 'queue_job_id': job['id'],
             'status': 'complete_base_only', 'source_root': str(SOURCE), 'destination_root': str(DESTINATION),
             'source_files_before': sources, 'source_files_after': after, 'sources_unchanged': True,
             'files': records, 'repair_applied': False,
             'limits': ['This is not readiness or geometric relocation equivalence',
                        'Hard-linked vendor assets are immutable aliases, not independent backups',
                        'Never run asset downloads or overwrite pinned vendor files at either path']}
    with record.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'record': str(record), 'sha256': digest(record), 'files': len(records),
                      'hard_linked_vendor_files': sum(r['storage'].startswith('hard_link') for r in records)}))


if __name__ == '__main__':
    main()
