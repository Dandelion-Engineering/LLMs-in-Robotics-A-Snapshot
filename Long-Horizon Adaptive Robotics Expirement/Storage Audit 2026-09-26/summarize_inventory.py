"""Compact this audit's own metadata scratch; never mutate inventoried sources.

Windows DirEntry.stat does not provide file identity/link count. The preliminary
GetCompressedFileSizeW column is NOT a cluster-allocation census. Discard those
columns; separately inspect ordinary os.stat identities for all >=1MB files and
two images per frame directory. Final totals deliberately use logical bytes.
"""
import collections
import ctypes
from ctypes import wintypes
import json
from pathlib import Path

HERE=Path(__file__).parent.resolve()
ROOT=HERE.parents[1]
M=HERE/'measurement'
summary=json.loads((M/'summary.json').read_text())
groups=collections.defaultdict(lambda:[0,0])
roles=collections.defaultdict(lambda:[0,0])
areas=collections.defaultdict(lambda:[0,0])
large=[]
samples={}
total=count=0

def role(path):
    name=path.name
    if '/frames/' in path.as_posix(): return 'depth_npz' if path.suffix=='.npz' else 'rgb_png' if path.suffix=='.png' else 'other_frame'
    if name in ('events.jsonl','motion.jsonl'):return name
    if path.suffix=='.gguf':return 'model_weights'
    if path.suffix=='.log':return 'logs'
    if '__pycache__' in path.parts:return 'bytecode_cache'
    return 'other'

with (M/'files.tsv').open(encoding='utf-8') as f:
    next(f)
    for line in f:
        p,s,*_=line.rstrip('\n').split('\t')
        s=int(s); path=Path(p);count+=1;total+=s
        k=(path.parent.as_posix(),path.suffix.lower() or '(none)')
        groups[k][0]+=1;groups[k][1]+=s
        r=role(path);roles[r][0]+=1;roles[r][1]+=s
        area='/'.join(path.parts[:3]) if len(path.parts)>3 and path.parts[0].startswith('Long-') else path.parts[0]
        areas[area][0]+=1;areas[area][1]+=s
        if s>=1_000_000:large.append((p,s,r))
        if r in ('depth_npz','rgb_png'):
            k=(path.parent.as_posix(),r)
            if k not in samples:samples[k]=(p,s,r)

assert count==summary['total_files'] and total==summary['logical_bytes']
with (M/'file-groups.tsv').open('x',encoding='utf-8') as f:
    f.write('directory\textension\tfiles\tlogical_bytes\n')
    for (d,e),(n,s) in sorted(groups.items()):f.write(f'{d}\t{e}\t{n}\t{s}\n')
with (M/'large-files.tsv').open('x',encoding='utf-8') as f:
    f.write('path\tlogical_bytes\trole\n')
    for p,s,r in sorted(large,key=lambda x:x[1],reverse=True):f.write(f'{p}\t{s}\t{r}\n')

class Standard(ctypes.Structure):
    _fields_=[('AllocationSize',ctypes.c_longlong),('EndOfFile',ctypes.c_longlong),('NumberOfLinks',wintypes.DWORD),('DeletePending',ctypes.c_ubyte),('Directory',ctypes.c_ubyte)]
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
k.CreateFileW.restype=wintypes.HANDLE
k.GetFileInformationByHandleEx.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
k.CloseHandle.argtypes=[wintypes.HANDLE]
physical=[];seen=set();repeated=0
for p,s,r in large+list(samples.values()):
    path=ROOT/p;st=path.stat()
    handle=k.CreateFileW(str(path),0,7,None,3,0,None)
    if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    try:
        info=Standard()
        if not k.GetFileInformationByHandleEx(handle,1,ctypes.byref(info),ctypes.sizeof(info)):raise ctypes.WinError(ctypes.get_last_error())
    finally:k.CloseHandle(handle)
    ident=(st.st_dev,st.st_ino)
    if ident in seen:repeated+=s
    seen.add(ident)
    physical.append(dict(path=p,logical_bytes=s,allocated_bytes=info.AllocationSize,links=info.NumberOfLinks,file_id=st.st_ino,device=st.st_dev,role=r))
with (M/'physical-checks.json').open('x',encoding='utf-8') as f:json.dump(physical,f,indent=2)

for key in ('allocated_bytes','unique_file_allocated_bytes','duplicate_hardlink_paths'):
    summary.pop(key,None)
for row in summary['largest_files']:row.pop('allocated_bytes',None)
summary.update(roles=dict(roles),areas=dict(areas),verified_repeated_hardlink_logical_bytes=repeated,
               known_hardlink_adjusted_logical_bytes=total-repeated,
               physical_checks=len(physical),frame_sample_count=len(samples),
               limitations='Complete logical-path metadata census; not physical allocated-space census. Hardlinks verified for all >=1 MB files and one RGB/one depth per frames directory only. Smaller unsampled hardlinks, allocation slack and NTFS metadata are not fully measured. Preliminary DirEntry identity and GetCompressedFileSizeW fields were discarded. No original contents modified. No entire raw-evidence hash scan.')
(M/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
lines=(M/'directories.tsv').read_text().splitlines()
(M/'directories.tsv').write_text('\n'.join('\t'.join(line.split('\t')[:3]) for line in lines)+'\n',encoding='utf-8')
# Remove ONLY the metadata scratch created by this audit, after count/byte equality.
# No pre-existing project artifact is eligible for this operation.
scratch=(M/'files.tsv').resolve()
assert scratch.parent==M.resolve() and scratch.name=='files.tsv'
scratch.unlink()
print(json.dumps({k:summary[k] for k in ('total_files','logical_bytes','known_hardlink_adjusted_logical_bytes','verified_repeated_hardlink_logical_bytes','physical_checks','frame_sample_count','roles','volumes','errors','skipped')},indent=2))
