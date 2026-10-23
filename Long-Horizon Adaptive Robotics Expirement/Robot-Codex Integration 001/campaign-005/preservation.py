"""Read-only authentication of Campaign 002 and both frozen source lineages."""
import argparse
import json
from pathlib import Path
import subprocess
from common import HERE, REPO, C02, MAP, sha, save

def capture(output):
    roots=[HERE.parent/('campaign-'+str(i).zfill(3)) for i in (1,2,3,4)]
    roots += [p for p in (MAP/'releases').iterdir() if p.is_dir() and any(t in p.name for t in ('C01','C02','C03','C04'))]
    names={p.relative_to(REPO).as_posix() for root in roots for p in root.rglob('*')
           if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.lock')}
    frozen = {}
    for revision in ('RCI001-wsl-010d', 'RCI001-C02-dev-114'):
        path = MAP/'releases'/revision/'snapshot.json'
        snapshot = json.loads(path.read_text(encoding='utf-8'))
        for name, identity in snapshot['sources'].items():
            if sha(REPO/name) != identity['sha256']:
                raise ValueError('Frozen source mismatch: ' + name)
            names.add(name)
        frozen[revision] = dict(snapshot_sha256=sha(path), source_count=len(snapshot['sources']))
    value = dict(schema='campaign005-preservation-1',
                 head=subprocess.check_output(['git','rev-parse','HEAD'], cwd=REPO, text=True).strip(),
                 frozen=frozen, files={n:dict(sha256=sha(REPO/n), bytes=(REPO/n).stat().st_size) for n in sorted(names)},
                 roots=[p.relative_to(REPO).as_posix() for p in roots],
                 map_prefixes={p.name:dict(sha256=sha(p), bytes=p.stat().st_size) for p in MAP.glob('*.jsonl')})
    save(output,value)
    print(json.dumps(dict(captured=len(names), frozen=frozen)), flush=True)

def verify(source, output):
    value=json.loads(Path(source).read_text(encoding='utf-8'))
    bad=[n for n,v in value['files'].items() if not (REPO/n).is_file() or sha(REPO/n)!=v['sha256']]
    for root in value.get('roots',[]):
        current={p.relative_to(REPO).as_posix() for p in (REPO/root).rglob('*')
                 if p.is_file() and '__pycache__' not in p.parts and (p.suffix not in ('.pyc','.lock') or p.relative_to(REPO).as_posix() in value['files'])}
        expected={n for n in value['files'] if n.startswith(root+'/')}
        if current!=expected:bad.append('membership '+root)
    for name, v in value['map_prefixes'].items():
        import hashlib
        with (MAP/name).open('rb') as stream: raw=stream.read(v['bytes'])
        if len(raw)!=v['bytes'] or hashlib.sha256(raw).hexdigest()!=v['sha256']: bad.append('map prefix '+name)
    result=dict(passed=not bad, checked_files=len(value['files']), frozen=value['frozen'], failures=bad)
    save(output,result)
    print(json.dumps(result), flush=True)
    if bad: raise RuntimeError('Historical preservation failed: '+str(bad))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['capture','verify']);p.add_argument('path',type=Path);p.add_argument('--output',type=Path)
    a=p.parse_args(); capture(a.path) if a.action=='capture' else verify(a.path,a.output)
