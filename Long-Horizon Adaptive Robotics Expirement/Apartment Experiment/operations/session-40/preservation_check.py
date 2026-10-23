"""Independent read-only historical and qualified-source preservation check."""
import gzip
import json
import os
from pathlib import Path
import sys
import traceback
from storage_audit import HERE, REPO, now, save, sha, volumes

BASE=Path('D:/Dandelion-Apartment-Experiment/engineering/commissioning-session39')
OLD=BASE/'preservation002/output/protected-inventory.json'
APARTMENT=REPO/'Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'

def inventory(root):
    result={}
    for directory,children,files in os.walk(root,followlinks=False):
        for name in children+files:
            p=Path(directory)/name
            assert not (p.lstat().st_file_attributes & 0x400),('reparse',str(p))
        for name in files:
            p=Path(directory)/name
            result[p.relative_to(root).as_posix()]=dict(bytes=p.stat().st_size,sha256=sha(p))
    return result

def main(phase):
    out=HERE/phase;out.mkdir(exist_ok=False)
    r=dict(passed=False,started=now(),checks={},volumes=volumes())
    try:
        assert sha(OLD)=='8efe94ec769618c5f8658bf90f786cde2ef4d1222f8f928addcd73acc59e9c01'
        old=json.loads(OLD.read_bytes());count=0;size=0
        for path,expected in old.items():
            actual=inventory(Path(path));assert actual==expected,path
            count+=len(actual);size+=sum(v['bytes'] for v in actual.values())
            print(json.dumps(dict(root=path,files=len(actual),passed=True)),flush=True)
        r['checks']['historical_full_rehash']=dict(roots=len(old),files=count,bytes=size,inventory_sha256=sha(OLD))
        current=inventory(BASE)
        if phase=='preservation-before':
            with gzip.open(out/'session39-inventory.json.gz','xt',encoding='utf-8') as f:json.dump(current,f,separators=(',',':'))
        else:
            with gzip.open(HERE/'preservation-before/session39-inventory.json.gz','rt',encoding='utf-8') as f:expected=json.load(f)
            assert current==expected,'Session 39 evidence changed'
        r['checks']['session39_full_rehash']=dict(files=len(current),bytes=sum(v['bytes'] for v in current.values()))
        cert=BASE/'audit003/output/certificate.json';manifest=BASE/'release002/manifest.json'
        assert sha(cert)=='49ac8e59a7af7b0e7b14c9c66eb3a5007984762c33e9382761cd44346d64054f'
        assert sha(manifest)=='d7d28df30a01ff7ee11bfa2f8025ccc1499856d3ba6e6e76fabb44735d979d3a'
        c=json.loads(cert.read_bytes());m=json.loads(manifest.read_bytes())
        for name,row in m['files'].items():
            assert sha(BASE/'release002/frozen_repository'/name)==row['sha256'],name
            assert sha(REPO/name)==row['sha256'],('working_source',name)
        for name,expected in c['attempt_results'].items():assert sha(BASE/name/'output/result.json')==expected,name
        for name,expected in c['protocol_sha256'].items():assert sha(APARTMENT/name)==expected,name
        r['checks']['qualified_source_and_certificate']=dict(files=len(m['files']),certificate_sha256=sha(cert),manifest_sha256=sha(manifest),working_source_matches=True,attempt_results=len(c['attempt_results']))
        # Current published robot filesystem and templates, environment and Git identities.
        retained={}
        for name in ('Robot Agent Filesystem Draft v0.2','Robot Agent Filesystem Draft v0.2 Maps Edition','Robot Agent Filesystem v0.1','Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/evidence/original-v2-filesystems'):
            retained[name]=inventory(REPO/name)
        if phase=='preservation-before':save(out/'published-filesystems.json',retained)
        else:assert retained==json.loads((HERE/'preservation-before/published-filesystems.json').read_bytes())
        r['checks']['published_filesystems']=dict(files=sum(map(len,retained.values())))
        r['checks']['no_v4']=not Path('D:/Dandelion-Apartment-Experiment/official/apartment-v4').exists();assert r['checks']['no_v4']
        r['passed']=True
    except BaseException as e:r.update(error=repr(e),traceback=traceback.format_exc())
    r['finished']=now();save(out/'result.json',r);print(json.dumps(r),flush=True)
    return 0 if r['passed'] else 1
if __name__=='__main__':raise SystemExit(main(sys.argv[1]))
