"""Full protected-history inventory, kept outside every prior evidence root."""
import hashlib
import json
from pathlib import Path
import sys
import traceback

HERE=Path(__file__).resolve().parent
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,indent=2);f.write('\n')
def main():
    out=HERE/'output';out.mkdir();result=dict(passed=False,checks={})
    try:
        base=Path('D:/Dandelion-Apartment-Experiment')
        roots=[*sorted((base/'official').iterdir()),*sorted((base/'engineering').iterdir()),base/'failed-launches']
        roots=[p for p in roots if p.is_dir() and p.name!='commissioning-session39']
        rows={}
        for root in roots:
            rows[str(root)]={p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(root.rglob('*')) if p.is_file() and not p.is_symlink()}
            print(json.dumps(dict(root=str(root),files=len(rows[str(root)]))),flush=True)
        save(out/'protected-inventory.json',rows)
        manifest=json.loads((HERE/'manifest.json').read_bytes());release=Path(manifest['release'])
        assert sha(release/'manifest.json')==manifest['release_manifest_sha256']
        for n,row in json.loads((release/'manifest.json').read_bytes())['files'].items():assert sha(release/'frozen_repository'/n)==row['sha256'],n
        result['checks']['frozen_release_exact']=True
        for name in ('apartment-v2','apartment-v3'):
            old=json.loads((base/'engineering/workspace-session38/profile001/output'/(name+'-before.json')).read_bytes())
            assert rows[str(base/'official'/name)]==old,'Official root differs from Session 38 baseline: '+name
        result['checks']['official_roots_equal_session38']=True
        result.update(passed=True,roots=len(rows),files=sum(map(len,rows.values())),bytes=sum(v['bytes'] for r in rows.values() for v in r.values()),inventory_sha256=sha(out/'protected-inventory.json'))
    except BaseException as e:result.update(error=repr(e),traceback=traceback.format_exc())
    save(out/'result.json',result);print(json.dumps(result),flush=True);return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
