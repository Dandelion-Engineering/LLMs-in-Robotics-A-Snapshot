"""Read-only project process, queue and Linux mount observations."""
import json
import ctypes
from ctypes import wintypes as W
from pathlib import Path
import subprocess
import sys
from storage_audit import HERE,REPO,now,save,volumes

def inspect():
    script="Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and ($_.CommandLine -match 'Dandelion-Apartment-Experiment|LLMs in Robotics|robot-codex-session10|Dandelion-Campaign00[45]') } | Select-Object ProcessId,ParentProcessId,Name,CreationDate,CommandLine | ConvertTo-Json -Depth 3 -Compress"
    p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,encoding='utf-8',check=True)
    windows=json.loads(p.stdout) if p.stdout.strip() else []
    if isinstance(windows,dict):windows=[windows]
    code=r'''import os,json,pathlib
anc={os.getpid()};pid=os.getpid()
while pid>1:
 try:pid=int(pathlib.Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[1]);anc.add(pid)
 except (OSError,ValueError):break
processes=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name) in anc:continue
 try:
  args=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  if any(s in args for s in ('/var/tmp/robot-codex-session10','/tmp/robot-codex-session9','Dandelion-Apartment-Experiment','journal_service.py','runtime_helper.py')):processes.append({'pid':int(p.name),'args':args})
 except (FileNotFoundError,PermissionError,ProcessLookupError):pass
mounts=[r for r in pathlib.Path('/proc/self/mountinfo').read_text().splitlines() if 'robot-codex-session' in r]
print(json.dumps({'processes':processes,'mounts':mounts}))'''
    linux=json.loads(subprocess.check_output(['wsl.exe','-d','Ubuntu-24.04','--','python3','-B','-c',code],text=True,encoding='utf-8'))
    queue=REPO.parent/'tools/compute_queue/compute_queue.py';jobs=[]
    for state in ('running','queued'):
        jobs+=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(queue),'list','--state',state,'--project','LLMs-in-Robotics'],text=True,encoding='utf-8'))
    allowed=('operations/session-40/','operations\\session-40\\','compute_queue.py','quiescence.py')
    unexpected=[p for p in windows if not any(s in (p['CommandLine'] or '') for s in allowed)]
    foreign_jobs=[j for j in jobs if not any('session-40/' in a or 'session-40\\' in a for a in j['argv'])]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=(W.DWORD,W.BOOL,W.DWORD);kernel.OpenProcess.restype=W.HANDLE
    kernel.GetProcessTimes.argtypes=(W.HANDLE,*([ctypes.POINTER(W.FILETIME)]*4));kernel.GetProcessTimes.restype=W.BOOL
    kernel.GetExitCodeProcess.argtypes=(W.HANDLE,ctypes.POINTER(W.DWORD));kernel.GetExitCodeProcess.restype=W.BOOL
    kernel.CloseHandle.argtypes=(W.HANDLE,)
    owners=json.loads(Path('D:/Dandelion-Apartment-Experiment/engineering/commissioning-session39/audit003/output/actual-native-retirement.json').read_bytes())['native_windows_identities']
    native=[]
    for owner in owners:
        handle=kernel.OpenProcess(0x1000,False,owner['pid'])
        if not handle:
            error=ctypes.get_last_error();native.append(dict(pid=owner['pid'],state='absent' if error==87 else 'unreadable',win_error=error,retired=error==87));continue
        try:
            times=[W.FILETIME() for _ in range(4)];exit_code=W.DWORD()
            assert kernel.GetProcessTimes(handle,*[ctypes.byref(t) for t in times])
            assert kernel.GetExitCodeProcess(handle,ctypes.byref(exit_code))
            actual=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime
            same=actual==owner['creation_filetime'];retired=not same or exit_code.value!=259
            native.append(dict(pid=owner['pid'],state='pid_reused' if not same else ('exited' if retired else 'active_original'),retired=retired))
        finally:kernel.CloseHandle(handle)
    return dict(time=now(),volumes=volumes(),windows=windows,linux=linux,project_jobs=jobs,unexpected_windows=unexpected,unexpected_jobs=foreign_jobs,
                native_windows_identities=native,passed=not (unexpected or foreign_jobs or linux['processes'] or linux['mounts']) and all(x['retired'] for x in native))

if __name__=='__main__':
    r=inspect();save(HERE/sys.argv[1],r);print(json.dumps(r,indent=2));raise SystemExit(0 if r['passed'] else 1)
