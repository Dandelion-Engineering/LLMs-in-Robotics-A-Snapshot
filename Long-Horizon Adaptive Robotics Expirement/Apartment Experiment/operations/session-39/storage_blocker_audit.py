"""Independent read-only storage-blocker disposition; no launch or cleanup."""
import ast
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import sys
import traceback

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
REPO=Path('C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics')
OPS=REPO/'Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/operations/session-39'
QUEUE=REPO.parent/'tools/compute_queue/compute_queue.py'
PAIR=Path('D:/Dandelion-Apartment-Experiment/official/apartment-v4')
sys.path.insert(0,str(HERE/'source'))
from common import read,save,sha,inventory

def status(name):
    return json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',read(OPS/(name+'-queue.json'))['id']],text=True,encoding='utf-8'))

def main():
    out=HERE/'output';out.mkdir(exist_ok=False)
    result=dict(passed=False,checks={},official_prepared=False,official_model_calls=0,automatic_retry=False)
    try:
        for name,row in read(HERE/'manifest.json')['files'].items():assert sha(HERE/name)==row['sha256']
        before=inventory(BASE/'freeze001');save(out/'freeze001-before.json',before)
        failure=status('freeze001')
        assert failure['state']=='failed' and type(failure['exit_status']) is int and failure['exit_status']==1
        for name,row in read(BASE/'freeze001/manifest.json')['files'].items():assert sha(BASE/'freeze001'/name)==row['sha256']
        log=Path(failure['log_path']);raw=log.read_bytes()
        assert b'Insufficient prelaunch storage margin' in raw
        (out/'freeze001-original-queue.log').write_bytes(raw)
        assert sha(log)==sha(out/'freeze001-original-queue.log')
        save(out/'freeze001-terminal.json',failure)
        assert not (BASE/'freeze001/output/result.json').exists()
        tree=ast.parse((BASE/'freeze001/freeze_pair.py').read_text(encoding='utf-8'))
        body=next(n.body for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        gate=next(i for i,n in enumerate(body) if isinstance(n,ast.Assert) and isinstance(n.msg,ast.Constant) and n.msg.value=='Insufficient prelaunch storage margin')
        create=next(i for i,n in enumerate(body) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and ast.unparse(n.value.func)=='shutil.copytree')
        assert gate<create and ast.unparse(body[gate].test)=='shutil.disk_usage(PAIR.parent).free >= 50 * 1024 ** 3'
        assert not PAIR.exists() and not (OPS/'official-queue-submission.json').exists()
        result['checks']['immutable_failed_preparation_before_any_official_creation']=True

        audit=status('audit003');assert audit['state']=='succeeded' and type(audit['exit_status']) is int and audit['exit_status']==0
        proof=read(BASE/'audit003/output/result.json');certificate=read(BASE/'audit003/output/certificate.json')
        assert proof['passed'] and len(proof['checks'])==10 and all(proof['checks'].values())
        assert certificate==proof['certificate'] and certificate['passed']
        assert certificate['release_manifest_sha256']==sha(BASE/'release002/manifest.json')
        from run import source_identity
        from environment import identity
        assert source_identity()==certificate['source_identity'] and identity()==certificate['environment']
        preserved=read(BASE/'audit003/output/preservation-readback.json')
        assert preserved['passed'] and (preserved['roots'],preserved['files'],preserved['bytes'])==(75,344286,15390037785)
        assert preserved['v3_original_false_retirement_unchanged']
        assert sha(BASE/'preservation002/output/protected-inventory.json')==preserved['before_sha256']
        result['checks']['fresh_certificate_and_completed_full_preservation_audit']=True
        result['preservation']=dict(**preserved,verification='Full rehash completed after all qualification and audit writes. Subsequent failed preparation stopped before copying or creating any official root; no protected-root writes followed.')
        result['certificate_sha256']=sha(BASE/'audit003/output/certificate.json')

        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.GetDiskFreeSpaceExW.argtypes=(wintypes.LPCWSTR,*([ctypes.POINTER(ctypes.c_ulonglong)]*3))
        kernel.GetDiskFreeSpaceExW.restype=wintypes.BOOL
        available=ctypes.c_ulonglong();total=ctypes.c_ulonglong();free=ctypes.c_ulonglong()
        assert kernel.GetDiskFreeSpaceExW('D:\\',ctypes.byref(available),ctypes.byref(total),ctypes.byref(free))
        required=50*1024**3
        assert 0<available.value<required
        result['storage']=dict(free_available_bytes=available.value,free_available_gib=available.value/1024**3,required_bytes=required,required_gib=50,shortfall_bytes=required-available.value,shortfall_gib=(required-available.value)/1024**3,independent_api='GetDiskFreeSpaceExW')
        result['checks']['storage_gate_remains_failed_without_relaxation']=True

        jobs=[]
        for state in ('queued','running'):
            jobs+=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'list','--state',state],text=True,encoding='utf-8'))
        assert not [j for j in jobs if 'apartment-v4' in ' '.join(j['argv']).lower()]
        import native_runtime as nr
        live=json.loads(nr.linux(r'''import os,pathlib,json
processes=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name)==os.getpid():continue
 try:
  args=(p/'cmdline').read_bytes().split(b'\0')
  if any(b'/var/tmp/robot-codex-session10/apartment-' in a for a in args):processes.append(int(p.name))
 except (FileNotFoundError,PermissionError,ProcessLookupError):pass
mounts=[r.split()[4] for r in pathlib.Path('/proc/self/mountinfo').read_text().splitlines() if '/robot-codex-session10/apartment-' in r]
print(json.dumps({'processes':processes,'mounts':mounts}))
'''))
        assert not live['processes'] and not live['mounts']
        result['runtime']=live
        kernel.OpenProcess.argtypes=(wintypes.DWORD,wintypes.BOOL,wintypes.DWORD);kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.GetProcessTimes.argtypes=(wintypes.HANDLE,*([ctypes.POINTER(wintypes.FILETIME)]*4));kernel.GetProcessTimes.restype=wintypes.BOOL
        kernel.GetExitCodeProcess.argtypes=(wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD));kernel.GetExitCodeProcess.restype=wintypes.BOOL
        kernel.CloseHandle.argtypes=(wintypes.HANDLE,);kernel.CloseHandle.restype=wintypes.BOOL
        identities=read(BASE/'audit003/output/actual-native-retirement.json')['native_windows_identities']
        observed=[]
        for owner in identities:
            pid=owner['pid'];created=owner['creation_filetime'];handle=kernel.OpenProcess(0x1000,False,pid)
            if not handle:
                assert ctypes.get_last_error()==87
                observed.append(dict(pid=pid,state='absent'));continue
            try:
                times=[wintypes.FILETIME() for _ in range(4)];code=wintypes.DWORD()
                assert kernel.GetProcessTimes(handle,*[ctypes.byref(t) for t in times]) and kernel.GetExitCodeProcess(handle,ctypes.byref(code))
                actual=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime
                assert actual!=created or code.value!=259
                observed.append(dict(pid=pid,state='pid_reused' if actual!=created else 'exited'))
            finally:kernel.CloseHandle(handle)
        result['native_process_readback']=observed
        result['checks']['no_official_job_or_active_apartment_runtime']=True
        assert inventory(BASE/'freeze001')==before
        result['checks']['failed_preparation_bytes_unchanged']=True
        result.update(passed=True,disposition='blocked_storage_before_official_creation',scientific_result='not_run',next_dependency='Provide sufficient authorized D: capacity while preserving all evidence, then recheck certificate/source/environment, capacity and fresh pristine-pair admission under renewed human direction. No automatic retry.')
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
    save(out/'result.json',result);print(json.dumps(result),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
