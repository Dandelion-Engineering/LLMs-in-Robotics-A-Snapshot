"""Authenticate the completed inventory behind a retained bookkeeping failure.

The first attempt hashes every byte and saves its full inventory before the
mistyped historical-reference lookup fails. This independent reader validates
that complete inventory, present file sets/sizes and the correct historical
baselines. It does not relabel the failed attempt. The final audit performs a
second complete byte rehash against this exact before-work inventory.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import traceback

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
REPO=Path('C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics')
OPS=REPO/'Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/operations/session-39'
def read(p):return json.loads(p.read_bytes())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,indent=2);f.write('\n')
def main():
    out=HERE/'output';out.mkdir();result=dict(passed=False,checks={})
    try:
        first=BASE/'preservation001';failure=read(first/'output/result.json')
        assert failure['passed'] is False and 'FileNotFoundError' in failure['error']
        assert 'protected-before.json' in failure['traceback']
        q=read(OPS/'preservation001-queue.json')
        actual=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(REPO.parent/'tools/compute_queue/compute_queue.py'),'status',q['id']],text=True,encoding='utf-8'))
        assert actual['state']=='failed' and type(actual['exit_status']) is int and actual['exit_status']==1
        for n,row in read(first/'manifest.json')['files'].items():assert sha(first/n)==row['sha256'],n
        assert 'save(out/\'protected-inventory.json\',rows)' in (first/'preserve.py').read_text(encoding='utf-8')
        result['checks']['failed_attempt_and_complete_inventory_provenance']=True
        base=Path('D:/Dandelion-Apartment-Experiment')
        roots=[*sorted((base/'official').iterdir()),*sorted((base/'engineering').iterdir()),base/'failed-launches']
        roots=[p for p in roots if p.is_dir() and p.name!='commissioning-session39']
        rows=read(first/'output/protected-inventory.json');assert set(rows)==set(map(str,roots))
        total=0;size=0
        for root in roots:
            expected=rows[str(root)]
            metadata={p.relative_to(root).as_posix():p.stat().st_size for p in sorted(root.rglob('*')) if p.is_file() and not p.is_symlink()}
            assert metadata=={n:r['bytes'] for n,r in expected.items()},root
            assert all(re.fullmatch('[0-9a-f]{64}',r['sha256']) for r in expected.values())
            total+=len(expected);size+=sum(metadata.values())
        result['checks']['complete_live_file_sets_and_sizes']=True
        for name in ('apartment-v2','apartment-v3'):
            old=read(base/'engineering/workspace-session38/profile001/output'/(name+'-before.json'))
            assert rows[str(base/'official'/name)]==old,name
        result['checks']['fresh_full_hashes_equal_session38_official_baselines']=True
        release=BASE/'release001';manifest=read(release/'manifest.json')
        assert sha(release/'manifest.json')==read(HERE/'manifest.json')['release_manifest_sha256']
        for n,row in manifest['files'].items():assert sha(release/'frozen_repository'/n)==row['sha256'],n
        result['checks']['release_source_exact']=True
        shutil.copyfile(first/'output/protected-inventory.json',out/'protected-inventory.json')
        assert sha(first/'output/protected-inventory.json')==sha(out/'protected-inventory.json')
        result.update(passed=True,roots=len(rows),files=total,bytes=size,inventory_sha256=sha(out/'protected-inventory.json'),
            full_byte_hash_origin=str(first/'output/protected-inventory.json'),previous_attempt_remains_failed=True,
            verification='Independent completeness, live metadata and historical baseline verification of fresh full hashes; final audit rehashes all bytes again.')
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
    save(out/'result.json',result);print(json.dumps(result),flush=True);return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
