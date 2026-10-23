"""Read exact process identities, mounts and queue state; never retire anything."""
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
PAIR=Path('D:/Dandelion-Apartment-Experiment/official/apartment-v3');ROOT=PAIR/'baseline'
OP=PAIR/'operator/failure-audit-session37-001'
def read(p):return json.loads(p.read_bytes())
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
kernel.GetProcessTimes.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
kernel.CloseHandle.argtypes=[wintypes.HANDLE]
def inspect(pid,expected=None):
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:return dict(pid=pid,handle_opened=False,winerror=ctypes.get_last_error(),expected_creation_filetime=expected)
    try:
        values=[wintypes.FILETIME() for _ in range(4)]
        ok=bool(kernel.GetProcessTimes(handle,*[ctypes.byref(x) for x in values]))
        creation=(values[0].dwHighDateTime<<32)|values[0].dwLowDateTime if ok else None
        return dict(pid=pid,handle_opened=True,observed_creation_filetime=creation,expected_creation_filetime=expected,same_recorded_process=creation==expected if expected else None)
    finally:kernel.CloseHandle(handle)

def main(label):
    rows=[]
    for session in sorted((ROOT/'sessions').iterdir()):
        row=dict(session=session.name)
        owner=session/'native/client/native-owner.json';service=session/'workspace/journal/service-identity.json'
        if owner.exists():
            identity=read(owner);row['windows']=inspect(identity['pid'],identity['process_creation_filetime'])
        if service.exists():row['service']=read(service)
        rows.append(row)
    code="""import json,os,pathlib,sys
rows=json.load(sys.stdin);out=[]
for row in rows:
 if 'service' not in row:continue
 x=row['service'];p=pathlib.Path('/proc')/str(x['pid']);v=dict(session=row['session'],identity=x,mounted=os.path.ismount(x['mount']),pid_present=p.exists(),same_recorded_service=False)
 if p.exists():
  try:
   fields=(p/'stat').read_text().rsplit(')',1)[1].split();cmd=(p/'cmdline').read_bytes().replace(bytes([0]),b' ').decode(errors='replace')
   v.update(start_ticks=fields[19],command=cmd,process_state=fields[0],same_recorded_service=fields[19]==x['start_ticks'] and x['mount'] in cmd)
  except (OSError,PermissionError) as e:v['error']=repr(e)
 out.append(v)
matches=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name)==os.getpid():continue
 try:
  command=(p/'cmdline').read_bytes().replace(bytes([0]),b' ').decode(errors='replace')
  if 'apartment-v3' in command or 'apartment-8fa2585eb8a44d11bc6a64a2867d60f1' in command:matches.append(dict(pid=int(p.name),command=command))
 except (OSError,PermissionError):pass
print(json.dumps(dict(recorded_services=out,current_matches=matches)))
"""
    response=subprocess.run(['wsl.exe','-d','Ubuntu-24.04','--','python3','-B','-c',code],input=json.dumps(rows),capture_output=True,text=True,encoding='utf-8',timeout=30)
    assert response.returncode==0,response.stderr
    linux=json.loads(response.stdout)
    windows=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',"ConvertTo-Json -Compress -InputObject @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(python|pythonw|wsl|node|codex)(\\.exe)?$' } | Select-Object ProcessId,ParentProcessId,Name,CommandLine)"],text=True,encoding='utf-8'))
    windows=[row for row in windows if row['ProcessId']!=os.getpid() and any(x in (row.get('CommandLine') or '') for x in ('apartment-v3','apartment-8fa2585eb8a44d11bc6a64a2867d60f1'))]
    queue=REPO.parent/'tools/compute_queue/compute_queue.py'
    active=[]
    for state in ('running','queued','cancel_requested'):
        records=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(queue),'list','--state',state],text=True,encoding='utf-8'))
        active.extend(row for row in records if 'apartment-v3' in json.dumps(row) and row['id']!='audit-observation')
    with socket.socket() as client:
        client.settimeout(2);connect_result=client.connect_ex(('127.0.0.1',50062))
    result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),label=label,observational_only=True,
                native_processes=rows,linux=linux,windows_matches=windows,active_pair_queue=active,
                viewer_port=50062,viewer_connect_result=connect_result,running_lock=(ROOT/'running.lock').exists())
    result['all_runtime_retired']=not linux['current_matches'] and not windows and not any(x['mounted'] or x['same_recorded_service'] for x in linux['recorded_services']) and not any(x.get('windows',{}).get('same_recorded_process') for x in rows) and not result['running_lock'] and connect_result!=0
    path=OP/('runtime-'+label+'.json')
    with path.open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(evidence=str(path),all_runtime_retired=result['all_runtime_retired'],linux_matches=linux['current_matches'],windows_matches=windows,viewer_connect_result=connect_result,active_pair_queue=[r['id'] for r in active])))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);args=parser.parse_args();main(args.label)
