"""Retain portable protected event evidence, indexing local native bulk separately."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not (args.source / 'result.json').is_file():
        raise SystemExit('Only a terminal host evidence directory can be archived')
    args.output.mkdir(parents=True, exist_ok=False)
    files = []
    archive = args.output / 'protected-events.zip'
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as out:
        for path in sorted(args.source.rglob('*')):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(args.source).as_posix()
            # Operator endpoint state has no evidentiary role. Never publish
            # lifecycle credentials, including accidentally still-live values.
            if 'endpoint' in path.name:
                continue
            data = path.read_bytes()
            portable = not relative.startswith(('native-recording/', 'baseline-workspace/'))
            row = {'path': relative, 'bytes': len(data),
                   'sha256': hashlib.sha256(data).hexdigest(),
                   'availability': 'portable_archive' if portable else 'retained_local_bulk'}
            files.append(row)
            if portable:
                out.writestr(relative, data)
    with zipfile.ZipFile(archive) as check:
        for row in files:
            if row['availability'] == 'portable_archive':
                data = check.read(row['path'])
                assert len(data) == row['bytes']
                assert hashlib.sha256(data).hexdigest() == row['sha256']
    result = {'schema': 'robot-codex-protected-evidence-index-1',
              'source_directory': str(args.source.resolve()),
              'archive': archive.name,
              'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
              'files': files,
              'scope': 'Byte retention only; queue authentication and outcome assessment are separate. Native recorder bulk remains on this host; unavailable on a fresh clone until copied and hash-verified.'}
    (args.output / 'index.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'files': len(files), 'portable': sum(r['availability'] == 'portable_archive' for r in files),
                      'archive_bytes': archive.stat().st_size}))


if __name__ == '__main__':
    main()
