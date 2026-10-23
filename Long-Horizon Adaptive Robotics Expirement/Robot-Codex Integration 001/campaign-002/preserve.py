"""Capture/verify immutable Campaign 001 and original framework bytes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
RCI = HERE.parent
REPO = RCI.parents[1]
MAP = RCI.parent / 'Architecture Map'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def capture(output):
    original = MAP / 'releases/RCI001-wsl-010d/snapshot.json'
    snapshot = json.loads(original.read_text(encoding='utf-8'))
    for name, value in snapshot['sources'].items():
        if sha(REPO / name) != value['sha256']:
            raise ValueError('Original framework changed: ' + name)
    tracked = subprocess.check_output(['git', 'ls-files', '-z', '--', str((RCI / 'campaign-001').relative_to(REPO))], cwd=REPO).decode().split('\0')
    names = sorted(set(filter(None, tracked)) | set(snapshot['sources']))
    record = {'created_at': datetime.now(timezone.utc).isoformat(),
              'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
              'original_framework_count': len(snapshot['sources']),
              'files': {name: {'sha256': sha(REPO/name), 'bytes': (REPO/name).stat().st_size} for name in names},
              'map_prefixes': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in MAP.glob('*.jsonl')},
              'scope': 'Every original qualified source and tracked Campaign001 artifact; raw evidence separately remains retained.'}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(record, stream, indent=2); stream.write('\n')
    print(json.dumps({'captured': len(names), 'original_sources':len(snapshot['sources'])}))

def verify(path):
    record = json.loads(path.read_text(encoding='utf-8'))
    bad = [name for name, value in record['files'].items() if not (REPO/name).is_file() or sha(REPO/name) != value['sha256']]
    for name, value in record['map_prefixes'].items():
        with (MAP/name).open('rb') as stream:
            raw = stream.read(value['bytes'])
        if len(raw) != value['bytes'] or hashlib.sha256(raw).hexdigest() != value['sha256']:
            bad.append('map historical prefix: ' + name)
    if bad: raise ValueError('Preservation failed: ' + repr(bad))
    print(json.dumps({'preserved':len(record['files']), 'map_prefixes':len(record['map_prefixes'])}))

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['capture','verify']);p.add_argument('path',type=Path)
    args=p.parse_args();(capture if args.action=='capture' else verify)(args.path)
