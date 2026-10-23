"""Acquire only the pinned, licensed Panda assets. Run via the compute queue."""
from pathlib import Path
import hashlib
import json
import urllib.request

REV = '822c2d8f877dd166c5b7d3c9f7e3c3b6589473b7'
ROOT = Path(__file__).resolve().parent / 'vendor' / 'panda'
BASE = f'https://raw.githubusercontent.com/google-deepmind/mujoco_menagerie/{REV}/'

def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(f'https://api.github.com/repos/google-deepmind/mujoco_menagerie/git/trees/{REV}?recursive=1', headers={'User-Agent':'Dandelion-robotics-research'})
    tree = json.load(urllib.request.urlopen(req, timeout=60))
    assert not tree.get('truncated'), 'Incomplete asset inventory'
    files = []
    for item in tree['tree']:
        path = item['path']
        if item['type'] != 'blob' or not path.startswith('franka_emika_panda/'):
            continue
        relative = Path(path).relative_to('franka_emika_panda')
        dest = ROOT / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            with urllib.request.urlopen(BASE + path, timeout=120) as r:
                content = r.read()
            assert len(content) == item['size'], path
            dest.write_bytes(content)
        content = dest.read_bytes()
        git_hash = hashlib.sha1(f'blob {len(content)}\0'.encode() + content).hexdigest()
        assert git_hash == item['sha'], f'Git object mismatch: {path}'
        files.append({'path':str(relative.as_posix()),'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest(),'source':BASE+path})
    assert hashlib.sha256((ROOT/'LICENSE').read_bytes()).hexdigest() == 'a6cba85bc92e0cff7a450b1d873c0eaa2e9fc96bf472df0247a26bec77bf3ff9'
    manifest = {'revision':REV,'source':'https://github.com/google-deepmind/mujoco_menagerie','files':files}
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'assets':len(files),'bytes':sum(f['bytes'] for f in files),'manifest':str(ROOT/'manifest.json')}))

if __name__ == '__main__':
    main()
