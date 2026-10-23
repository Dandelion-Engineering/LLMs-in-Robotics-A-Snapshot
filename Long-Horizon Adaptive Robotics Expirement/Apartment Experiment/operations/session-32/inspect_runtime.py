"""Read only exact recorded process identities, mounts and observer socket."""
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=Path('D:/Dandelion-Apartment-Experiment/official/apartment-v1-restart001/baseline')
def read(p):return json.loads(p.read_bytes())
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
kernel.GetProcessTimes.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
kernel.CloseHandle.argtypes=[wintypes.HANDLE]
def inspect(pid,expected=None):
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:return {'pid':pid,'handle_opened':False,'winerror':ctypes.get_last_error(),'expected_creation_filetime':expected}
    try:
        values=[wintypes.FILETIME() for _ in range(4)]
        ok=bool(kernel.GetProcessTimes(handle,*[ctypes.byref(x) for x in values]))
        creation=(values[0].dwHighDateTime<<32)|values[0].dwLowDateTime if ok else None
        return {'pid':pid,'handle_opened':True,'observed_creation_filetime':creation,'expected_creation_filetime':expected,'same_recorded_process':creation==expected if expected else None}
    finally:kernel.CloseHandle(handle)

rows=[]
for p in sorted((ROOT/'sessions').iterdir()):
    n=read(p/'native/client/native-owner.json');s=read(p/'workspace/journal/service-identity.json')
    rows.append({'session':p.name,'windows':inspect(n['pid'],n['process_creation_filetime']),'service':s})
code="""import json,os,pathlib,sys
out=[]
for row in json.load(sys.stdin):
 s=row['service'];p=pathlib.Path('/proc')/str(s['pid']);facts={'session':row['session'],'mounted':os.path.ismount(s['mount']),'pid_present':p.exists()}
 if p.exists():
  try:
   ticks=(p/'stat').read_text().rsplit(')',1)[1].split()[19];cmd=(p/'cmdline').read_bytes()
   facts.update(start_ticks=ticks,same_recorded_service=ticks==s['start_ticks'] and s['mount'].encode() in cmd)
  except OSError as e:facts['inspection_error']=str(e)
 else:facts['same_recorded_service']=False
 out.append(facts)
print(json.dumps(out))
"""
r=subprocess.run(['wsl.exe','-d','Ubuntu-24.04','--','python3','-B','-c',code],input=json.dumps(rows),text=True,capture_output=True,timeout=30)
with socket.socket() as s:
    s.settimeout(2);connection_code=s.connect_ex(('127.0.0.1',55582))
result={'observed_utc':datetime.now(timezone.utc).isoformat(),'native_processes':rows,'queue_child':inspect(51756),
    'viewer_port':55582,'viewer_connect_result':connection_code,'linux_returncode':r.returncode,'linux':json.loads(r.stdout) if r.returncode==0 else None,'linux_stderr':r.stderr}
path=HERE/'runtime-inspection.json'
with path.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(result))
