"""Bind supplied generic framework and immutable legacy inputs without secrets."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'Robot Agent Filesystem v0.1'
ARCHIVE = Path.home() / 'Downloads/Robot_Agent_Filesystem_v0.1_RobotAgentPrompt.zip'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify():
    entries = []
    with zipfile.ZipFile(ARCHIVE) as archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            relative = Path(*Path(entry.filename).parts[1:])
            path = SOURCE / relative
            data = archive.read(entry)
            if path.read_bytes() != data:
                raise ValueError(f'Generic source differs from supplied archive: {relative}')
            entries.append({'path': relative.as_posix(), 'bytes': len(data),
                            'sha256': hashlib.sha256(data).hexdigest()})
    expected = {x['path'] for x in entries}
    actual = {p.relative_to(SOURCE).as_posix() for p in SOURCE.rglob('*') if p.is_file()}
    if expected != actual or 'workspace/RobotAgentPrompt.md' not in expected or 'workspace/AgentPrompt.md' in expected:
        raise ValueError('Generic source inventory mismatch')
    runtime = HERE.parent / 'Runtime 004'
    return {'schema': 'robot-codex-source-provenance-1',
            'recorded_at': datetime.now(timezone.utc).isoformat(),
            'archive_name': ARCHIVE.name, 'archive_sha256': digest(ARCHIVE),
            'source_root': SOURCE.relative_to(ROOT).as_posix(),
            'generic_revision': 'Robot Agent Filesystem v0.1, prepared 2026-09-26',
            'extraction': '16 files, unchanged bytes; ZIP wrapper renamed to spaced project directory',
            'files': entries,
            'legacy_inputs': [{'path': p.relative_to(ROOT).as_posix(), 'sha256': digest(p)}
                              for p in [runtime/'candidates.py', runtime/'cell.py', runtime/'actuation.py', runtime/'sensor_worker.py']],
            'session_start_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--record', type=Path)
    args = parser.parse_args()
    result = verify()
    if args.record:
        args.record.parent.mkdir(parents=True, exist_ok=True)
        with args.record.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
    print(json.dumps({'verified_files':len(result['files']), 'archive_sha256':result['archive_sha256'],
                      'legacy_inputs':result['legacy_inputs']}, indent=2))
