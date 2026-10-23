"""Read-only current capacity, apartment runtime and scheduler checks."""
import ctypes
from ctypes import wintypes as W
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

REPO = Path('C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics')
APPREL = Path('Long-Horizon Adaptive Robotics Expirement/Apartment Experiment')
OLD = Path('D:/Dandelion-Apartment-Experiment/engineering/commissioning-session39')
QUEUE = REPO.parent/'tools/compute_queue/compute_queue.py'
PAIR = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v4')

def read(p): return json.loads(Path(p).read_bytes())
def sha(p):
    with Path(p).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()
def inventory(root):
    return {p.relative_to(root).as_posix():dict(sha256=sha(p),bytes=p.stat().st_size)
            for p in sorted(root.rglob('*')) if p.is_file()}
def output(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True, encoding='utf-8')
def queue(*args): return json.loads(output(sys.executable,'-X','utf8','-B',str(QUEUE),*args))

def storage():
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.GetDiskFreeSpaceExW.argtypes=(W.LPCWSTR,*([ctypes.POINTER(ctypes.c_ulonglong)]*3))
    k.GetDiskFreeSpaceExW.restype=W.BOOL
    available,total,free=[ctypes.c_ulonglong() for _ in range(3)]
    assert k.GetDiskFreeSpaceExW('D:\\',ctypes.byref(available),ctypes.byref(total),ctypes.byref(free))
    k.GetDiskFreeSpaceW.argtypes=(W.LPCWSTR,*([ctypes.POINTER(W.DWORD)]*4))
    k.GetDiskFreeSpaceW.restype=W.BOOL
    sectors,bytes_per_sector,free_clusters,total_clusters=[W.DWORD() for _ in range(4)]
    assert k.GetDiskFreeSpaceW('D:\\',*[ctypes.byref(x) for x in (sectors,bytes_per_sector,free_clusters,total_clusters)])
    allocation=sectors.value*bytes_per_sector.value
    census=REPO/APPREL/'operations/session-40/census001/root-1-directories.json'
    rows=read(census)
    baselines={n:rows['official/'+n+'/baseline'] for n in ('apartment-v2','apartment-v3')}
    envelope=3*max(v['allocated'] for v in baselines.values())+2*1024**3
    required=50*1024**3
    return dict(free_bytes=available.value,free_gib=available.value/1024**3,
        allocation_unit_bytes=allocation,total_bytes=total.value,
        minimum_bytes=required,minimum_gate=available.value>=required,
        census_path=str(census),census_sha256=sha(census),historical_baselines=baselines,
        expected_run_and_preparation_envelope_bytes=envelope,
        planning_basis='Three times the larger retained Baseline physical allocation plus 2 GiB operator/preparation allowance; not a hard bound or scientific session limit.',
        reserve_after_envelope_bytes=available.value-envelope,
        headroom_gate=available.value-envelope>=required,
        independent_api='GetDiskFreeSpaceExW and GetDiskFreeSpaceW',
        shutil_free_bytes=shutil.disk_usage('D:/').free)

def quiescence():
    script="Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and ($_.CommandLine -match 'Dandelion-Apartment-Experiment|LLMs in Robotics|robot-codex-session10') } | Select-Object ProcessId,ParentProcessId,Name,CreationDate,CommandLine | ConvertTo-Json -Depth 3 -Compress"
    raw=output('powershell.exe','-NoProfile','-NonInteractive','-Command',script)
    windows=json.loads(raw) if raw.strip() else []
    if isinstance(windows,dict):windows=[windows]
    allowed=('operations/session-41/','operations\\session-41\\','engineering/launch-session41/','engineering\\launch-session41\\','compute_queue.py')
    unexpected=[p for p in windows if not any(s in (p['CommandLine'] or '') for s in allowed)]
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
    linux=json.loads(output('wsl.exe','-d','Ubuntu-24.04','--','python3','-B','-c',code))
    jobs=queue('list','--state','running')+queue('list','--state','queued')
    conflicts=[j for j in jobs if any('official' in str(a).lower() and 'apartment' in str(a).lower() for a in j['argv'])]
    monitors=[]
    for p in sorted(Path('C:/Users/cresp/.codex/automations').glob('*/automation.toml')):
        row=tomllib.loads(p.read_text(encoding='utf-8'))
        if 'apartment' in json.dumps(row).lower():
            monitors.append(dict(id=row.get('id',p.parent.name),status=row.get('status'),name=row.get('name'),sha256=sha(p)))
    locks=[str(p) for p in PAIR.parent.glob('*/**/running.lock')]
    return dict(windows=windows,unexpected_windows=unexpected,linux=linux,
        jobs=jobs,conflicting_jobs=conflicts,monitors=monitors,locks=locks,
        passed=not(unexpected or conflicts or linux['processes'] or linux['mounts'] or locks)
            and all(m['status']=='PAUSED' for m in monitors))
