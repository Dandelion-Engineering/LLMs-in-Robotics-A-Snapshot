"""Actual unprivileged FUSE + three fresh bubblewrap processes; no model client."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from verify_journal import verify

HERE=Path(__file__).resolve().parent
def save(path,value):
    temp=Path(str(path)+'.next');temp.write_text(json.dumps(value,sort_keys=True)+'\n');os.replace(temp,path)

def run(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    mount=root/'workspace';mount.mkdir()
    initial={'notes':None,'programs':None,'.continuity':None,'.continuity/Continuity.md':'',
             'Continuity.md':{'symlink':'.continuity/Continuity.md'},'Tasks.md':'Neutral filesystem qualification only.\n'}
    save(root/'initial.json',initial)
    identity={'run_id':root.name,'session_id':'setup','source_revision':'development','phase':'initialization'}
    save(root/'identity.json',identity)
    log=(root/'server.log').open('wb')
    process=subprocess.Popen([sys.executable,'-B',str(HERE/'journal_fs.py'),'--mount',str(mount),
        '--evidence',str(root/'journal'),'--initial',str(root/'initial.json'),'--identity',str(root/'identity.json')],stdout=log,stderr=log)
    receipt={'actual_model_calls':0,'sessions':[],'passed':False}
    try:
        deadline=time.monotonic()+15
        while not os.path.ismount(mount):
            if process.poll() is not None:raise RuntimeError('FUSE stopped: '+(root/'server.log').read_text())
            if time.monotonic()>deadline:raise RuntimeError('FUSE mount deadline')
            time.sleep(.02)
        for session in (1,2,3):
            save(root/'identity.json',{**identity,'session_id':f'session-{session}','phase':'guest'})
            command=['bwrap','--unshare-all','--unshare-user','--disable-userns','--assert-userns-disabled','--die-with-parent','--new-session','--cap-drop','ALL','--clearenv',
                '--setenv','PATH','/usr/bin:/bin','--setenv','LANG','C.UTF-8','--setenv','HOME','/workspace',
                '--ro-bind','/usr','/usr','--symlink','usr/bin','/bin','--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64',
                '--proc','/proc','--dev','/dev','--tmpfs','/tmp','--ro-bind',str(mount),'/workspace']
            for area in ('notes','programs','.continuity'):command+=['--bind',str(mount/area),'/workspace/'+area]
            command+=['--ro-bind',str(HERE/'fs_guest_probe.py'),'/probe.py','--chdir','/workspace','--remount-ro','/',
                      '/usr/bin/python3','-I','-B','/probe.py',str(session)]
            result=subprocess.run(command,capture_output=True,text=True,timeout=25)
            receipt['sessions'].append(dict(session=session,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
            save(root/'receipt.json',receipt)
            if result.returncode:raise RuntimeError('Guest qualification failed: '+result.stderr+result.stdout)
        receipt['passed']=True
    except Exception as e:
        receipt['error']=str(e)
    finally:
        save(root/'identity.json',{**identity,'session_id':'cleanup','phase':'cleanup'})
        if os.path.ismount(mount):
            unmount=subprocess.run(['fusermount3','-u',str(mount)],capture_output=True,text=True,timeout=5)
            receipt['unmount_returncode']=unmount.returncode
        try:receipt['server_returncode']=process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.terminate();receipt['server_returncode']=process.wait(timeout=5);receipt['passed']=False
        log.close()
        receipt['unmounted']=not os.path.ismount(mount)
        try:
            replay=verify(root/'journal',root.name)
            receipt['replay']={k:v for k,v in replay.items() if k not in ('state','states','read_events')}
            transient=[state for _,state in replay['states'] if '/notes/transient' in state['paths']]
            assert transient,'missed short lived file'
            receipt['short_lived_state_reconstructed']=True
        except Exception as e:receipt['replay_error']=str(e);receipt['passed']=False
        receipt['passed']=receipt['passed'] and receipt['unmounted'] and receipt['server_returncode']==0
        save(root/'receipt.json',receipt)
    print(json.dumps(receipt),flush=True)
    return 0 if receipt['passed'] else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');a=p.parse_args();raise SystemExit(run(a.root))
