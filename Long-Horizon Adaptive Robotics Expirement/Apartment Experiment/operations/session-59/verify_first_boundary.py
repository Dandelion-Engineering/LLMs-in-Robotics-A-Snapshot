"""Read-only first-boundary evidence and actual process retirement audit."""
import ctypes
from ctypes import wintypes as W
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
import traceback

PAIR=Path('D:/Dandelion-Apartment-Experiment/official/apartment-v4')
CODE=PAIR/'frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'
sys.path.insert(0,str(CODE))
from common import read,sha
import journal_reader

def main():
    out=Path('C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics/Local Experiment Data/apartment-v4-maps/operator/first-boundary-audit');out.mkdir(exist_ok=False)
    result=dict(passed=False,observed_utc=datetime.now(timezone.utc).isoformat(),checks={},observational_only=True)
    try:
        root=Path('C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics/Local Experiment Data/apartment-v4-maps/run');session=root/'sessions/session-00001';workspace=session/'workspace'
        from recording import verify_checkpoint,verify_prefix
        cp=root/'checkpoints/session-00001'
        receipt=verify_checkpoint(cp);prefix=verify_prefix(root,cp)
        result['checkpoint_readback']=dict(passed=receipt['passed'] and prefix['passed'],path=str(cp),receipt=receipt,prefix=prefix,state_sha256=sha(cp/'state.json'))
        assert result['checkpoint_readback']['passed']
        result['checks']['independent_checkpoint_and_prefix']=True
        client=read(session/'native/client/result.json');closeout=read(session/'closeout.json')
        assert client['success'] is True and client['turn_status']=='completed' and closeout['passed'] is True
        cleanup=read(workspace/'cleanup-001.json');native=read(workspace/'journal/native-exit.json')
        assert cleanup['normal_requested'] and cleanup['retired'] and not cleanup['mounted'] and cleanup['log_closed']
        assert type(cleanup['service_exit']) is int and cleanup['service_exit']==0 and not cleanup['errors']
        assert native['libfuse_main_return']==0 and native['requested_sigterm'] is False
        location=read(workspace/'location.json');proof=journal_reader.verify(workspace/'journal',location['run_id'])
        assert proof['passed'] and proof['records']==native['final_sequence'] and proof['final_state_sha256']==native['final_state_sha256']
        result['journal']=proof;result['checks']['normal_native_closeout_and_journal_fidelity']=True
        k=ctypes.WinDLL('kernel32',use_last_error=True)
        k.OpenProcess.argtypes=(W.DWORD,W.BOOL,W.DWORD);k.OpenProcess.restype=W.HANDLE
        k.GetProcessTimes.argtypes=(W.HANDLE,*([ctypes.POINTER(W.FILETIME)]*4));k.GetProcessTimes.restype=W.BOOL
        k.GetExitCodeProcess.argtypes=(W.HANDLE,ctypes.POINTER(W.DWORD));k.GetExitCodeProcess.restype=W.BOOL
        k.CloseHandle.argtypes=(W.HANDLE,);k.CloseHandle.restype=W.BOOL
        owners=[read(p) for n in ('native-owner.json','codehost-native-owner-v3.json') for p in session.rglob(n)]
        assert len(owners)==2
        result['windows']=[]
        for owner in owners:
            pid=owner['pid'];created=owner['process_creation_filetime'];handle=k.OpenProcess(0x1000,False,pid)
            if not handle:
                assert ctypes.get_last_error()==87
                result['windows'].append(dict(pid=pid,state='absent',retired=True));continue
            try:
                times=[W.FILETIME() for _ in range(4)];code=W.DWORD()
                assert k.GetProcessTimes(handle,*[ctypes.byref(t) for t in times]) and k.GetExitCodeProcess(handle,ctypes.byref(code))
                actual=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime
                assert actual!=created or code.value!=259
                result['windows'].append(dict(pid=pid,state='pid_reused' if actual!=created else 'exited',retired=True))
            finally:k.CloseHandle(handle)
        probe=r'''import os,json,pathlib,sys
needle=sys.argv[1];anc={os.getpid()};pid=os.getpid()
while pid>1:
 try:pid=int(pathlib.Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[1]);anc.add(pid)
 except (OSError,ValueError):break
processes=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name) in anc:continue
 try:
  if needle.encode() in (p/'cmdline').read_bytes():processes.append(int(p.name))
 except (FileNotFoundError,PermissionError,ProcessLookupError):pass
mounts=[r.split()[4] for r in pathlib.Path('/proc/self/mountinfo').read_text().splitlines() if needle in r]
print(json.dumps(dict(processes=processes,mounts=mounts)))'''
        result['linux']=json.loads(subprocess.check_output(['wsl.exe','-d','Ubuntu-24.04','--','python3','-B','-c',probe,location['run']],text=True,encoding='utf-8'))
        assert not result['linux']['processes'] and not result['linux']['mounts']
        result['checks']['actual_first_session_windows_linux_retirement']=True
        second=root/'sessions/session-00002/native'
        preflight=read(second/'client/preflight.json')
        assert preflight['preflight_passed'] and preflight['thread_id']!=client['thread_id']
        assert preflight['model_effective']=='gpt-6-astra' and preflight['effort_effective']=='max'
        for n in ('canary.json','codehost-canary.json'):
            c=read(second/n);assert c['exit_status']==0 and json.loads(c['stdout'])['qualified']
        result['first_thread']=client['thread_id'];result['second_thread']=preflight['thread_id']
        result['checks']['fresh_second_native_thread_and_canaries']=True
        result['passed']=True
    except BaseException as e:result.update(error=repr(e),traceback=traceback.format_exc())
    result['reader_sha256']=sha(Path(__file__))
    with (out/'result.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:result.get(k) for k in ('passed','checks','error','traceback','first_thread','second_thread','checkpoint_readback')}),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
