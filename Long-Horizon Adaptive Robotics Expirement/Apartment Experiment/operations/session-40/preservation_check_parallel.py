"""Full fresh read-only pass with eight bounded I/O workers; unchanged gates.

The earlier serial pass was canceled for execution cost and is not accepted as
completed evidence. This pass rehashes every file from the beginning. It makes
no source/evidence change and imports no experiment runtime.
"""
from concurrent.futures import ThreadPoolExecutor
import itertools
import os
from pathlib import Path
import preservation_check as checks
from storage_audit import HERE,sha

def file_row(p,root):
    before=p.stat();digest=sha(p);after=p.stat()
    assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),str(p)
    return p.relative_to(root).as_posix(),dict(bytes=after.st_size,sha256=digest)

def inventory(root):
    def paths():
        for directory,children,files in os.walk(root,followlinks=False):
            for name in children+files:
                p=Path(directory)/name
                assert not (p.lstat().st_file_attributes&0x400),('reparse',str(p))
            for name in files:yield Path(directory)/name
    result={};items=iter(paths())
    with ThreadPoolExecutor(max_workers=8) as pool:
        while batch:=list(itertools.islice(items,4096)):
            result.update(pool.map(lambda p:file_row(p,root),batch))
    return result

if __name__=='__main__':
    destination=HERE/'parallel002';destination.mkdir(exist_ok=False)
    checks.HERE=destination;checks.inventory=inventory
    raise SystemExit(checks.main('preservation-before'))
