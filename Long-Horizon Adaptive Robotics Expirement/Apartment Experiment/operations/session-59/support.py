"""Operator-only storage routing evidence. Never imported by Robot Codex."""
from datetime import datetime, timezone
import ctypes
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PAIR = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v4')
FROZEN = PAIR / 'frozen_repository'
APPREL = Path('Long-Horizon Adaptive Robotics Expirement/Apartment Experiment')
CODE = FROZEN / APPREL
DATA = REPO / 'Local Experiment Data/apartment-v4-maps'
RUN = DATA / 'run'
QUAL = DATA / 'qualification001'
DQUAL = PAIR / 'operator/storage-qualification-session59'
QUEUE = REPO.parent / 'tools/compute_queue/compute_queue.py'
GIB = 1024 ** 3


def now(): return datetime.now(timezone.utc).isoformat()
def read(p): return json.loads(Path(p).read_bytes())
def sha(p):
    with Path(p).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()
def save(p, value):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, indent=2, allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
def ref(p): return dict(uri=str(p), sha256=sha(p), bytes=Path(p).stat().st_size)
def output(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True, encoding='utf-8')
def queue(*args): return json.loads(output(sys.executable, '-X', 'utf8', '-B', str(QUEUE), *args))
def inventory(root):
    result = {}
    for p in sorted(Path(root).rglob('*')):
        assert not p.is_symlink() and not p.is_junction(), str(p)
        if p.is_file(): result[p.relative_to(root).as_posix()] = dict(sha256=sha(p), bytes=p.stat().st_size)
    return result
def namespace(root):
    result = {}
    for p in [Path(root), *sorted(Path(root).rglob('*'))]:
        assert not p.is_symlink() and not p.is_junction(), str(p)
        s = p.stat()
        result[p.relative_to(root).as_posix()] = dict(kind='directory' if p.is_dir() else 'file', mode=s.st_mode, mtime_ns=s.st_mtime_ns)
    return result
def volume(drive):
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.GetDiskFreeSpaceExW.argtypes = (W.LPCWSTR, *([ctypes.POINTER(ctypes.c_ulonglong)] * 3))
    k.GetDiskFreeSpaceExW.restype = W.BOOL
    available, total, free = [ctypes.c_ulonglong() for _ in range(3)]
    assert k.GetDiskFreeSpaceExW(drive, *[ctypes.byref(x) for x in (available, total, free)])
    k.GetDiskFreeSpaceW.argtypes = (W.LPCWSTR, *([ctypes.POINTER(W.DWORD)] * 4))
    k.GetDiskFreeSpaceW.restype = W.BOOL
    sectors, sector_bytes, free_clusters, total_clusters = [W.DWORD() for _ in range(4)]
    assert k.GetDiskFreeSpaceW(drive, *[ctypes.byref(x) for x in (sectors, sector_bytes, free_clusters, total_clusters)])
    python_free = shutil.disk_usage(drive).free
    return dict(drive=drive, free_bytes=available.value, total_bytes=total.value,
                allocation_unit_bytes=sectors.value*sector_bytes.value, shutil_free_bytes=python_free,
                observed_utc=now(), api='GetDiskFreeSpaceExW/GetDiskFreeSpaceW; independent shutil reading')
def allocation_census(root, unit):
    rows = {}; logical = allocated = projected = 0
    for p in sorted(Path(root).rglob('*')):
        assert not p.is_symlink() and not p.is_junction(), str(p)
        if p.is_file():
            s = p.stat(); assert not (s.st_file_attributes & (0x200 | 0x800)), 'Sparse/compressed file requires separate allocation measurement'
            size = s.st_size; allocation = ((size + unit - 1)//unit)*unit
            rows[p.relative_to(root).as_posix()] = dict(bytes=size, allocated_cluster_bytes=allocation)
            logical += size; allocated += allocation; projected += ((size+4095)//4096)*4096
    return dict(files=len(rows), logical_bytes=logical, allocated_file_bytes=allocated,
                projected_4096_byte_allocation=projected, allocation_unit_bytes=unit,
                method='Cluster rounding on verified noncompressed nonsparse exFAT regular files; directory/volume overhead excluded', files_detail=rows)
def capacity(census):
    c, d = volume('C:\\'), volume('D:\\')
    inherited = read(HERE.parent/'session-58/admission-blocker.json')['capacity']['expected_run_and_preparation_envelope_bytes']
    # Retain the historical whole-volume decline as another conservative input;
    # it is not attributed exclusively to Baseline. Do not scale down for NTFS.
    decline = int(119.3251953125*GIB)
    allowance = max(inherited, 3*max(census['allocated_file_bytes'], decline)+2*GIB)
    return dict(C=c, D=d, minimum_reserve_bytes=50*GIB, maps_allowance_bytes=allowance,
                inherited_allowance_bytes=inherited, baseline_file_allocation_bytes=census['allocated_file_bytes'],
                historical_volume_decline_bytes=decline, d_operator_allowance_bytes=2*GIB,
                required_c_free_bytes=allowance+50*GIB, c_headroom_pass=c['free_bytes']>=allowance+50*GIB,
                d_headroom_pass=d['free_bytes']>=52*GIB,
                planning_basis='Maximum of inherited allowance and three times the larger of actual v4 Baseline exFAT file allocation or historical whole-volume decline, plus 2 GiB; retain full 50 GiB reserve. NTFS savings not credited. Not a session limit or guaranteed bound.')
def quiescence():
    script = "Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and ($_.CommandLine -match 'Dandelion-Apartment-Experiment|Local Experiment Data|robot-codex-session10') } | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Depth 3 -Compress"
    raw = output('powershell.exe','-NoProfile','-NonInteractive','-Command',script)
    windows = json.loads(raw) if raw.strip() else []
    if isinstance(windows, dict): windows=[windows]
    allowed = ('operations/session-59/', 'operations\\session-59\\', 'compute_queue.py')
    unexpected = [p for p in windows if not any(s in (p['CommandLine'] or '') for s in allowed)]
    code = r'''import os,json,pathlib
anc={os.getpid()};pid=os.getpid()
while pid>1:
 try:pid=int(pathlib.Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[1]);anc.add(pid)
 except (OSError,ValueError):break
processes=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name) in anc:continue
 try:
  args=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  if any(s in args for s in ('/var/tmp/robot-codex-session10','/tmp/robot-codex-session9','Dandelion-Apartment-Experiment','Local Experiment Data','journal_service.py','runtime_helper.py')):processes.append({'pid':int(p.name),'args':args})
 except (FileNotFoundError,PermissionError,ProcessLookupError):pass
mounts=[r for r in pathlib.Path('/proc/self/mountinfo').read_text().splitlines() if 'robot-codex-session' in r]
print(json.dumps({'processes':processes,'mounts':mounts}))'''
    linux = json.loads(output('wsl.exe','-d','Ubuntu-24.04','--','python3','-B','-c',code))
    jobs = sum((queue('list','--state',s) for s in ('running','queued','cancel_requested')), [])
    conflicts = [j for j in jobs if any('run.py' in str(a) for a in j['argv']) and any(str(a)=='--official' for a in j['argv'])]
    monitors = []
    for p in sorted(Path('C:/Users/cresp/.codex/automations').glob('*/automation.toml')):
        row=tomllib.loads(p.read_text(encoding='utf-8'))
        if 'apartment' in json.dumps(row).lower(): monitors.append(dict(id=row.get('id',p.parent.name),status=row['status'],sha256=sha(p)))
    locks=[str(p) for p in PAIR.parent.glob('*/**/running.lock')]
    if (RUN/'running.lock').exists(): locks.append(str(RUN/'running.lock'))
    return dict(windows=windows, unexpected_windows=unexpected, linux=linux, jobs=jobs, conflicting_jobs=conflicts,
                monitors=monitors, locks=locks, passed=not(unexpected or conflicts or linux['processes'] or linux['mounts'] or locks) and all(m['status']=='PAUSED' for m in monitors))
