"""Read-only project storage census. Outputs are new, exclusive audit files."""
import collections
import ctypes
from ctypes import wintypes as W
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ROOTS = [REPO, Path('D:/Dandelion-Apartment-Experiment'), Path('D:/CodexEvidence/LLMs-in-Robotics'),
         Path('D:/Dandelion-Campaign004-Exports'), Path('D:/Dandelion-Campaign005-Exports')]
K = ctypes.WinDLL('kernel32', use_last_error=True)
K.CreateFileW.argtypes = (W.LPCWSTR,W.DWORD,W.DWORD,ctypes.c_void_p,W.DWORD,W.DWORD,W.HANDLE)
K.CreateFileW.restype = W.HANDLE
K.CloseHandle.argtypes = (W.HANDLE,)
K.GetFileInformationByHandleEx.argtypes = (W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD)
K.GetFileInformationByHandleEx.restype = W.BOOL
class Standard(ctypes.Structure):
    _fields_ = [('allocation',ctypes.c_longlong),('size',ctypes.c_longlong),('links',W.DWORD),('delete',ctypes.c_byte),('directory',ctypes.c_byte)]
def allocation(p):
    h=K.CreateFileW('\\\\?\\'+str(p),0,7,None,3,0,None)
    if h==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    try:
        s=Standard()
        if not K.GetFileInformationByHandleEx(h,1,ctypes.byref(s),ctypes.sizeof(s)):raise ctypes.WinError(ctypes.get_last_error())
        return s.allocation,s.links
    finally:K.CloseHandle(h)
def save(p,v):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,indent=2);f.write('\n')
def now():return datetime.datetime.now().astimezone().isoformat()
def volumes():return {v:dict(zip(('total','used','free'),shutil.disk_usage(v+':/'))) for v in ('C','D')}
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def census(out):
    out.mkdir(exist_ok=False)
    start=now();before=volumes();summary=[];all_errors=[];all_skipped=[]
    # Only project-specific names; generic tmp and other Dandelion project paths are not traversed.
    temp=Path(os.environ['TEMP'])
    roots=ROOTS+[p for p in temp.iterdir() if p.is_dir() and p.name.startswith(('robot-codex-session9-','robot-codex-isolation-schema-','robot-candidate-'))]
    save(out/'roots.json',[str(p) for p in roots])
    with gzip.open(out/'files.jsonl.gz','xt',encoding='utf-8',newline='\n',compresslevel=5) as f:
        for root in roots:
            dirs=collections.defaultdict(lambda:[0,0,0]);count=0;errors=[];skipped=[];stack=[root];started=time.monotonic()
            if not root.exists():continue
            while stack:
                directory=stack.pop()
                try:entries=list(os.scandir(directory))
                except OSError as e:errors.append([str(directory),repr(e)]);continue
                for entry in entries:
                    p=Path(entry.path)
                    if p==HERE:continue
                    try:
                        st=entry.stat(follow_symlinks=False)
                        if st.st_file_attributes & 0x400:skipped.append([str(p),'reparse point']);continue
                        if entry.is_dir(follow_symlinks=False):stack.append(p);continue
                        if not entry.is_file(follow_symlinks=False):continue
                        alloc,links=allocation(p)
                        rel=p.relative_to(root).as_posix()
                        row=dict(root=str(root),path=rel,bytes=st.st_size,allocated=alloc,links=links,mtime_ns=st.st_mtime_ns,attributes=st.st_file_attributes)
                        f.write(json.dumps(row,separators=(',',':'))+'\n')
                        for parent in [Path('.'),*Path(rel).parents[:-1]]:
                            d=dirs[parent.as_posix()];d[0]+=1;d[1]+=st.st_size;d[2]+=alloc
                        count+=1
                        if count%50000==0:print(json.dumps(dict(root=str(root),files=count,elapsed_s=round(time.monotonic()-started,1))),flush=True)
                    except OSError as e:errors.append([str(p),repr(e)])
            tag='root-'+str(len(summary))
            save(out/(tag+'-directories.json'),{k:dict(files=v[0],bytes=v[1],allocated=v[2]) for k,v in sorted(dirs.items(),key=lambda item:item[1][2],reverse=True)})
            row=dict(root=str(root),files=count,logical_bytes=dirs['.'][1],allocated_path_bytes=dirs['.'][2],directories_file=tag+'-directories.json',errors=errors,skipped=skipped)
            summary.append(row);all_errors+=errors;all_skipped+=skipped;print(json.dumps(row),flush=True)
    save(out/'result.json',dict(passed=not all_errors,started=start,finished=now(),volumes_before=before,volumes_after=volumes(),roots=summary,errors=all_errors,skipped=all_skipped,inventory_sha256=sha(out/'files.jsonl.gz'),allocation_method='FILE_STANDARD_INFO AllocationSize for every regular file; path sums double-count hardlinks; directories/filesystem metadata are excluded. Not an atomic snapshot.'))

if __name__=='__main__':census(HERE/sys.argv[1])
