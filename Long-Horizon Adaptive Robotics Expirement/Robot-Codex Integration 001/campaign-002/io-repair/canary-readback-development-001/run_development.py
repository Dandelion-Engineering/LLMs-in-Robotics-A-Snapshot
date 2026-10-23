"""Local parser development only. No task launch, original evidence mutation or admission."""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess
import sys
import zipfile

D=Path(__file__).resolve().parent
C=D.parents[1]
REPO=C.parents[2]

def binding(path):
    raw=path.read_bytes()
    return {'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}

def save(name,value):
    with (D/name).open('x',encoding='utf-8') as stream:
        json.dump(value,stream,indent=2);stream.write('\n')

def main():
    label=sys.argv[1]
    sources=[C/'assessment'/name for name in ('canary_readback_proof.py','test_canary_readback_proof.py')]
    before=list(map(binding,sources))
    cmd=[sys.executable,'-X','utf8','-B','-m','unittest','test_canary_readback_proof','-v']
    result=subprocess.run(cmd,cwd=C/'assessment',capture_output=True)
    for suffix,raw in [('stdout.txt',result.stdout),('stderr.txt',result.stderr)]:
        with (D/(label+'-'+suffix)).open('xb') as stream:stream.write(raw)
    save(label+'.json',{'scope':'Synthetic only; no native/model/qualification launch','argv':cmd,
        'exit_code':result.returncode,'sources_before':before,'sources_after':list(map(binding,sources)),
        'stdout':binding(D/(label+'-stdout.txt')),'stderr':binding(D/(label+'-stderr.txt'))})
    print(result.stderr.decode());print('test_exit',result.returncode)
    if result.returncode or len(sys.argv)<3:return result.returncode
    replay=sys.argv[2]
    cmd=[sys.executable,'-X','utf8','-B',str(REPO.parent/'tools/compute_queue/compute_queue.py'),
         'status','20260929T014234165833Z-cba1e8b0']
    status=subprocess.run(cmd,capture_output=True);official=json.loads(status.stdout)
    save(replay+'-official-auth.json',{'argv':cmd,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                      'exit_code':status.returncode,'official':official})
    assert status.returncode==0 and official['state']=='succeeded' and type(official['exit_status']) is int and official['exit_status']==0
    original=C.parents[1]/'Architecture Map/releases/RCI001-C02-dev-078/code.zip'
    overlay=D/(replay+'-source-overlay.zip');changed=[];added=[]
    with zipfile.ZipFile(original) as old,zipfile.ZipFile(overlay,'x',zipfile.ZIP_DEFLATED) as new:
        names=set(old.namelist())
        for name in names:
            path=REPO/name;data=old.read(name)
            if '/campaign-002/assessment/' in name and path.is_file():
                current=path.read_bytes()
                if current!=data:changed.append({'path':name,'old_sha256':hashlib.sha256(data).hexdigest(),'new_sha256':hashlib.sha256(current).hexdigest()})
                data=current
            new.writestr(name,data)
        for path in [*sources,C/'io-repair/CANARY_READBACK_EXCLUSIVITY_V1.md']:
            name=path.relative_to(REPO).as_posix()
            if name not in names:new.writestr(name,path.read_bytes());added.append(binding(path))
    sys.path.insert(0,str(C/'assessment'));import canary_readback_proof as helper
    root=C.parent/'local-evidence/campaign002/qualification/RCI001-C02-smoke-023/orchestrator/resume'
    result=helper.canary_readback_evidence(root,overlay)
    save(replay+'.json',{'scope':'New assessor development only; original historical assessment unchanged',
        'executed_runtime':'Archived dev078 fac550bdd92e1ee35c98d21029408522c07ac8e956bdda24b8c5d4615c3d473b; never relabeled as current runtime',
        'original_archive':binding(original),'overlay':binding(overlay),'changed_assessors':changed,'added':added,
        'sources':list(map(binding,sources)),'result':result})
    print('development_verified',result['verified'],'errors',result['errors'])
    return 0

if __name__=='__main__':raise SystemExit(main())
