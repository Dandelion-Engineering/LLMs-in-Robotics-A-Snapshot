"""Immutable no-model diagnosis and guarded retirement regression matrix."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source'))
from common import read,save,sha,inventory
import native_runtime as nr
import journal_reader as reader

def clone(space,root):
    script=root/'clone.py'
    script.write_text('''import json,pathlib,sys,time,os
p=pathlib.Path(sys.argv[1]);ready=pathlib.Path(sys.argv[2]);release=pathlib.Path(sys.argv[3])
assert p.is_mount()
ready.write_text(json.dumps({'pid':os.getpid(),'mount_namespace':os.readlink('/proc/self/ns/mnt'),'mounted':True}))
end=time.monotonic()+80
while not release.exists() and time.monotonic()<end:time.sleep(.02)
''',encoding='utf-8')
    log=(root/'clone.log').open('wb')
    child=subprocess.Popen(['wsl.exe','-d',nr.DISTRO,'--','unshare','--user','--map-root-user','--mount','--propagation','private','python3','-B',nr.wsl(script),space.workspace,nr.wsl(root/'clone-ready.json'),nr.wsl(root/'clone-release')],stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    deadline=time.monotonic()+10
    while not (root/'clone-ready.json').exists() and child.poll() is None and time.monotonic()<deadline:time.sleep(.05)
    assert (root/'clone-ready.json').exists(),(child.poll(),(root/'clone.log').read_text())
    return child,log

def release_clone(child,log,root):
    (root/'clone-release').write_text('release',encoding='utf-8')
    code=child.wait(10);log.close();assert code==0,code

def control(space,value):
    return json.loads(nr.linux('import json,sys;sys.path.insert(0,sys.argv[1]);from workspace_lifecycle import request;print(json.dumps(request(sys.argv[2],json.loads(sys.argv[3]),2)))',nr.wsl(HERE/'source'),space.control,json.dumps(value)))

def case(out,name,kind):
    root=out/name;root.mkdir();initial=root/'initial';initial.mkdir();(initial/'probe').write_bytes(b'original\0bytes')
    space=nr.Workspace(root/'workspace',initial,name);child=log=None
    try:
        nr.linux("import pathlib,sys;p=pathlib.Path(sys.argv[1]);(p/'probe').write_bytes(b'changed\\0bytes')",space.workspace)
        if kind in ('clone','external','poison'):
            child,log=clone(space,root)
        # A live outer mount and a wrong owner must never admit shutdown.
        assert 'error' in control(space,dict(command='retire',run_id=space.run_id))
        assert 'error' in control(space,dict(command='retire',run_id='wrong-owner'))
        if kind=='external':
            nr.linux('import json,pathlib,os,signal,sys;p=json.loads(pathlib.Path(sys.argv[1]).read_text());os.kill(p["pid"],signal.SIGTERM)',space.owner)
            assert space.process.wait(10)==1
            assert not (space.evidence/'journal/native-exit.json').exists()
            space.abort()
            proof=reader.verify(space.evidence/'journal',space.run_id)
            result=dict(passed=True,unrequested_sigterm_rejected=True,journal_final_record_present=True,records=proof['records'])
        elif kind=='poison':
            nr.linux("import pathlib,sys;f=(pathlib.Path(sys.argv[1])/'oversize').open('wb');f.seek(16*1024**2)\ntry:f.write(b'x');f.flush()\nexcept OSError:pass\ntry:f.close()\nexcept OSError:pass",space.workspace)
            try:space.close();raise AssertionError('Poisoned journal promoted')
            except RuntimeError:pass
            space.abort()
            assert not (space.evidence/'journal/native-exit.json').exists()
            try:reader.verify(space.evidence/'journal',space.run_id);raise AssertionError('Poisoned final accepted')
            except AssertionError as e:assert str(e)=='missing final closure',repr(e)
            result=dict(passed=True,poison_refused=True,abnormal_retirement=True)
        else:
            begin=time.monotonic();final,_=space.close();elapsed=time.monotonic()-begin
            assert (final/'probe').read_bytes()==b'changed\0bytes'
            proof=reader.verify(space.evidence/'journal',space.run_id)
            receipt=read(space.evidence/'journal/native-exit.json')
            assert receipt['libfuse_main_return']==0 and not receipt['requested_sigterm']
            rows=[json.loads(x) for x in (space.evidence/'journal/mutations.jsonl').read_bytes().splitlines()]
            assert sum(x['type']=='final' for x in rows)==1 and rows[-1]['type']=='final'
            if kind=='clone':
                assert child.poll() is None,'Clone disappeared before retirement proof'
                assert receipt['requested_fuse_exit'] is True
                assert any(x.get('label')=='retirement-requested' for x in rows)
            result=dict(passed=True,elapsed_s=elapsed,records=proof['records'],native_exit=receipt,clone_alive_at_service_exit=kind=='clone')
        save(root/'result.json',result);return result
    finally:
        if child is not None:release_clone(child,log,root)
        if not space.closed:space.abort()
        assert space.process.poll() is not None and space.log.closed

def main():
    out=HERE/'output';out.mkdir();result=dict(passed=False,checks={},model_calls=0)
    try:
        manifest=read(HERE/'manifest.json')
        for n,row in manifest['files'].items():assert sha(HERE/n)==row['sha256'],n
        from run import source_identity
        from environment import identity
        assert source_identity()==manifest['source_identity'] and identity()==manifest['environment']
        failed=HERE.parent/'native001/output/failed/baseline/sessions/session-00001'
        proof=reader.verify(failed/'workspace/journal',read(failed/'workspace/location.json')['run_id'])
        assert proof['records']==7990 and proof['final_state_sha256']=='e0c8dbd504cb149c7adf2a196508c6db8963f251e1cfb7321c81dd154da60f51'
        assert not (failed/'workspace/journal/native-exit.json').exists()
        save(out/'native001-journal-readback.json',{k:v for k,v in proof.items() if k not in ('state','states','read_events')})
        save(out/'native001-before.json',inventory(HERE.parent/'native001'))
        result['checks']['failed_pilot_final_record_authenticated']=True
        for i in range(5):
            name='normal-'+str(i+1);print(name,flush=True);result['checks'][name]=case(out,name,'normal')
        for name,kind in [('retained-clone','clone'),('external-sigterm','external'),('poisoned-journal','poison')]:
            print(name,flush=True);result['checks'][name]=case(out,name,kind)
        assert inventory(HERE.parent/'native001')==read(out/'native001-before.json')
        result['checks']['failed_pilot_unchanged']=True
        result['passed']=True
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
    save(out/'result.json',result);print(json.dumps(dict(passed=result['passed'],error=result.get('error'))),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
