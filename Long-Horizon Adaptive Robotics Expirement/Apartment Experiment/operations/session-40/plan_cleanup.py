"""Select demonstrably disposable caches and empty project temp directories."""
import csv
import gzip
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from storage_audit import HERE, REPO, allocation, now, save, sha

def main():
    report=json.loads((HERE/'census001/result.json').read_bytes());assert report['passed']
    before=json.loads((HERE/'parallel002/preservation-before/result.json').read_bytes());assert before['passed']
    records={}
    lib=REPO/'venv/Lib/site-packages'
    for p in lib.glob('*.dist-info/RECORD'):
        with p.open(encoding='utf-8',newline='') as f:
            for row in csv.reader(f):
                if len(row)>=3:records[str((lib/row[0]).resolve()).lower()]=row[1:]
    tracked=set(subprocess.check_output(['git','ls-files','-z'],cwd=REPO).decode('utf-8').split('\0'))
    selected=[];skipped=[];source_rows={};total=0
    with gzip.open(HERE/'census001/files.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            row=json.loads(line)
            if row['root']!=str(REPO) or not row['path'].startswith('venv/Lib/') or '/__pycache__/' not in row['path'] or not row['path'].endswith('.pyc'):continue
            p=REPO/row['path'];source=Path(importlib.util.source_from_cache(str(p)))
            reason=None
            if not source.is_file():reason='No surviving Python source'
            elif row['links']!=1:reason='Multiple hardlinks'
            elif records.get(str(p).lower(),['',''])!=['','']:reason='Package RECORD binds bytecode content'
            elif row['path'] in tracked:reason='Tracked cache is preserved'
            if reason:skipped.append(dict(path=str(p),reason=reason));continue
            source_hash=sha(source);cache_hash=sha(p);st=p.stat()
            assert st.st_size==row['bytes'] and st.st_mtime_ns==row['mtime_ns']
            assert not p.lstat().st_file_attributes&0x400
            assert p.read_bytes()[:4]==importlib.util.MAGIC_NUMBER
            source_rows[str(source)]=dict(bytes=source.stat().st_size,sha256=source_hash)
            selected.append(dict(path=str(p),kind='file',classification='regenerable_environment_bytecode',bytes=row['bytes'],allocated=row['allocated'],mtime_filetime=st.st_mtime_ns//100+116444736000000000,sha256=cache_hash,source=str(source),source_sha256=source_hash,reason='Untracked installed-package cache; Python source survives, package RECORD does not bind cached content. Python -B works directly from source. No scientific/guest/evidence cache is included.'))
    for entry in report['roots']:
        root=Path(entry['root'])
        if root.parent!=Path(os.environ['TEMP']) or entry['files'] or entry['errors'] or entry['skipped']:continue
        descendants=list(root.rglob('*'))
        assert all(p.is_dir() and not p.lstat().st_file_attributes&0x400 for p in [root,*descendants])
        selected.append(dict(path=str(root),kind='empty_tree',classification='empty_project_temporary_directory',bytes=0,allocated=None,directories=1+len(descendants),reason='Only empty directories remain. Project-specific sandbox/schema/qualification prefix and source provenance were inspected; no receipt, journal, source or data is present.'))
    save(HERE/'cleanup-plan.json',dict(created_at=now(),targets=selected,skipped=skipped,totals=dict(files=sum(r['kind']=='file' for r in selected),empty_trees=sum(r['kind']=='empty_tree' for r in selected),logical_bytes=sum(r['bytes'] for r in selected),file_allocated_bytes=sum(r['allocated'] or 0 for r in selected)),authority='authority-original.md',protected_check='parallel002/preservation-before/result.json',notes='No D: or historical evidence deletion is selected. Empty directory allocation is not included in file allocation totals.'))
    save(HERE/'cache-source-proof.json',source_rows)
    print(json.dumps(dict(targets=len(selected),skipped=skipped,logical_bytes=sum(r['bytes'] for r in selected),allocated=sum(r['allocated'] or 0 for r in selected))))
if __name__=='__main__':main()
