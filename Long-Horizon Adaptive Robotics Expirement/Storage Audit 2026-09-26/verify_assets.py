"""Queued read-only content/physical-allocation check of model asset copies.

Does not compress anything or modify source data. Output is exclusive-create.
"""
import ctypes
from ctypes import wintypes
import hashlib
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / 'Long-Horizon Adaptive Robotics Expirement'
OUT = Path(__file__).parent / 'asset-verification.json'
if OUT.exists():
    raise SystemExit('Refusing to replace output')

class Standard(ctypes.Structure):
    _fields_ = [('AllocationSize', ctypes.c_longlong), ('EndOfFile', ctypes.c_longlong),
                ('NumberOfLinks', wintypes.DWORD), ('DeletePending', ctypes.c_ubyte), ('Directory', ctypes.c_ubyte)]

kernel = ctypes.WinDLL('kernel32', use_last_error=True)
create = kernel.CreateFileW
create.argtypes = [wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
create.restype = wintypes.HANDLE
info = kernel.GetFileInformationByHandleEx
info.argtypes = [wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
info.restype = wintypes.BOOL
close = kernel.CloseHandle
close.argtypes = [wintypes.HANDLE]
close.restype = wintypes.BOOL

def physical(path):
    handle = create(str(path), 0, 7, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        st = Standard()
        if not info(handle, 1, ctypes.byref(st), ctypes.sizeof(st)):
            raise ctypes.WinError(ctypes.get_last_error())
        return dict(allocated_bytes=st.AllocationSize, hardlinks=st.NumberOfLinks)
    finally:
        close(handle)

started = time.time()
records=[]
for runtime in ('Runtime','Runtime Release 002','Runtime 004'):
    folder = EXP/runtime/'vendor/model'
    for path in sorted(folder.rglob('*')):
        if path.is_file() and path.suffix.lower() in ('.gguf','.zip','.dll','.exe'):
            before = path.stat()
            h=hashlib.sha256()
            with path.open('rb') as f:
                while chunk := f.read(8*1024*1024):
                    h.update(chunk)
            after=path.stat()
            if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
                raise RuntimeError('Source changed during read: '+str(path))
            row=dict(path=path.relative_to(ROOT).as_posix(),bytes=before.st_size,sha256=h.hexdigest(),
                     device=before.st_dev,file_id=before.st_ino,**physical(path))
            records.append(row)
            print(json.dumps(row),flush=True)
groups={}
for row in records:
    groups.setdefault(row['sha256'],[]).append(row)
extra=sum(sum(x['bytes'] for x in rows[1:]) for rows in groups.values())
result=dict(started_unix=started,finished_unix=time.time(),source_bytes_read=sum(x['bytes'] for x in records),
            identical_extra_logical_bytes=extra,records=records,
            caveat='Identical bytes only. Canonicalization requires path-reference compatibility; this job performs no cleanup.')
with OUT.open('x',encoding='utf-8') as f:
    json.dump(result,f,indent=2)
print(json.dumps({k:v for k,v in result.items() if k!='records'}),flush=True)
