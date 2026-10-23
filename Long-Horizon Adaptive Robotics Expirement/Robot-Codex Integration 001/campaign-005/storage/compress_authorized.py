"""Only the four director-approved paths; transparent lossless NTFS storage."""
import ctypes
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import traceback

AREA = Path(__file__).resolve().parent.parent
ROOT = AREA.parents[2]


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def save(path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2)


def allocation(path):
    high=ctypes.c_uint32()
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.GetCompressedFileSizeW.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_uint32)]
    api.GetCompressedFileSizeW.restype=ctypes.c_uint32
    ctypes.set_last_error(0)
    low=api.GetCompressedFileSizeW(str(path),ctypes.byref(high))
    if low==0xffffffff and ctypes.get_last_error():raise ctypes.WinError(ctypes.get_last_error())
    return (high.value<<32)|low


def main():
    plan=json.loads((AREA/'storage-plan.json').read_text())
    out=AREA/'storage/compression-001';out.mkdir(exist_ok=False)
    result={'passed':False,'authority':'Randy direct session reply: Approve lossless compression',
            'free_before':shutil.disk_usage(ROOT).free,'files':[]}
    try:
        assert len(plan['items'])==4
        for n,item in enumerate(plan['items'],1):
            path=Path(item['path']).resolve()
            assert path.is_relative_to(ROOT/'Long-Horizon Adaptive Robotics Expirement/Evidence/releases/batch01-eval-r4/attempts')
            assert path.name=='events.jsonl'
            info=path.stat()
            assert info.st_size==item['bytes'] and sha(path)==item['expected_sha256']
            before={'path':str(path),'bytes':info.st_size,'mtime_ns':info.st_mtime_ns,
                    'sha256':item['expected_sha256'],'physical_bytes':allocation(path),'attributes':info.st_file_attributes}
            save(out/f'{n}-before.json',before)
            command=subprocess.run(['compact.exe','/C','/I','/Q',str(path)],capture_output=True,text=True)
            save(out/f'{n}-command.json',dict(argv=command.args,returncode=command.returncode,stdout=command.stdout,stderr=command.stderr))
            after=path.stat()
            assert command.returncode==0
            assert after.st_size==before['bytes'] and after.st_mtime_ns==before['mtime_ns'] and sha(path)==before['sha256']
            row={**before,'physical_after':allocation(path),'attributes_after':after.st_file_attributes,'exact_bytes_and_mtime_preserved':True}
            result['files'].append(row);save(out/f'{n}-verified.json',row)
        result['free_after']=shutil.disk_usage(ROOT).free
        result['physical_bytes_recovered']=sum(r['physical_bytes']-r['physical_after'] for r in result['files'])
        result['launch_reserve_available']=result['free_after']>=plan['required_launch_free_bytes']
        result['passed']=True
    except Exception as error:result.update(error=str(error),traceback=traceback.format_exc())
    save(out/'receipt.json',result)
    print(json.dumps(result),flush=True)
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
