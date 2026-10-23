"""Read-only post-cleanup identity, absence, source and entrypoint checks."""
import gzip
import json
import itertools
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
import traceback
from storage_audit import HERE,REPO,now,save,sha,volumes

def main():
    r=dict(passed=False,started=now(),checks={})
    try:
        plan=json.loads((HERE/'cleanup-plan.json').read_bytes());deleted={x['path'] for x in plan['targets']}
        outcome=json.loads((HERE/'cleanup-result.json').read_text(encoding='utf-8-sig'));assert outcome['passed']
        assert outcome['plan_sha256']==sha(HERE/'cleanup-plan.json')
        for p in deleted:assert not Path(p).exists(),p
        r['checks']['all_planned_paths_absent']=len(deleted)
        sources=json.loads((HERE/'cache-source-proof.json').read_bytes())
        for p,row in sources.items():assert sha(Path(p))==row['sha256'],p
        r['checks']['all_cache_sources_unchanged']=len(sources)
        errors=[];mutable=[];count=0;size=0;absent=[]
        def metadata(row):
            p=Path(row['root'])/row['path']
            if str(p) in deleted:return 'deleted',str(p),0,[]
            if row['root']==str(REPO) and (row['path'].startswith('Tools/.state/') or row['path'] in ('.git/index','.git/FETCH_HEAD')):
                return 'mutable',str(p),0,[]
            try:
                st=p.stat();issues=[]
                if st.st_size!=row['bytes'] or st.st_mtime_ns!=row['mtime_ns']:issues.append(dict(path=str(p),reason='size_or_mtime_changed'))
                if st.st_file_attributes&0x400:issues.append(dict(path=str(p),reason='became_reparse_point'))
                return 'retained',str(p),st.st_size,issues
            except OSError as e:return 'error',str(p),0,[dict(path=str(p),error=repr(e))]
        with gzip.open(HERE/'census001/files.jsonl.gz','rt',encoding='utf-8') as f,ThreadPoolExecutor(max_workers=8) as pool:
            rows=(json.loads(line) for line in f)
            while batch:=list(itertools.islice(rows,4096)):
                for state,path,n,issues in pool.map(metadata,batch):
                    if state=='deleted':absent.append(path)
                    elif state=='mutable':mutable.append(path)
                    elif state=='retained':count+=1;size+=n
                    errors.extend(issues)
        r['checks']['retained_census_metadata']=dict(files=count,bytes=size,expected_file_absences=len(absent),operational_mutable_exclusions=mutable,errors=errors)
        assert not errors,errors[:5]
        # Full protected-byte rehash completed before the strictly C-cache-only mutation.
        before=json.loads((HERE/'parallel002/preservation-before/result.json').read_bytes());assert before['passed']
        r['checks']['full_hash_baseline']=dict(receipt_sha256=sha(HERE/'parallel002/preservation-before/result.json'),scope=before['checks'],postcheck='Every retained censused path checked for unchanged size/mtime; no D mutation was admitted or performed. Critical identities are rehashed below. This postcheck is not a second whole-history byte rehash.')
        base=Path('D:/Dandelion-Apartment-Experiment/engineering/commissioning-session39')
        cert=base/'audit003/output/certificate.json';manifest=base/'release002/manifest.json'
        assert sha(cert)=='49ac8e59a7af7b0e7b14c9c66eb3a5007984762c33e9382761cd44346d64054f'
        assert sha(manifest)=='d7d28df30a01ff7ee11bfa2f8025ccc1499856d3ba6e6e76fabb44735d979d3a'
        files=json.loads(manifest.read_bytes())['files'];syntax=0
        for name,row in files.items():
            for p in [base/'release002/frozen_repository'/name,REPO/name]:assert sha(p)==row['sha256'],str(p)
            if name.endswith('.py'):compile((REPO/name).read_bytes(),name,'exec');syntax+=1
        critical={}
        old=json.loads((base/'preservation002/output/protected-inventory.json').read_bytes())
        for name,checkpoint in [('apartment-v2','baseline/checkpoints/session-00036/manifest.json'),('apartment-v2','maps/checkpoints/session-00022/manifest.json'),('apartment-v3','baseline/checkpoints/session-00014/manifest.json')]:
            root=Path('D:/Dandelion-Apartment-Experiment/official')/name
            for rel in [checkpoint,'hidden-schedule.json','prepared.json']:
                p=root/rel;assert sha(p)==old[str(root)][rel]['sha256'];critical[str(p)]=sha(p)
        r['checks']['critical_hashes_after']=dict(certificate_sha256=sha(cert),release_manifest_sha256=sha(manifest),source_files=2*len(files),python_sources_compiled_without_execution=syntax,official=critical)
        # Import installed packages only; no simulator construction, native/model calls or experiment helpers.
        code='import json,numpy,mujoco,websockets; print(json.dumps({"numpy":numpy.__version__,"mujoco":mujoco.__version__,"websockets":websockets.__version__}))'
        r['checks']['environment_imports']=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B','-c',code],text=True,encoding='utf-8'))
        pinned=json.loads(cert.read_bytes())['environment']
        for name in ('mujoco','numpy'):assert r['checks']['environment_imports'][name]==pinned[name],name
        assert sha(Path(sys.executable))==pinned['python_sha256']
        r['checks']['python_and_primary_package_identity_match_certificate']=True
        check=subprocess.run(['git','fsck','--connectivity-only','--no-dangling'],cwd=REPO,capture_output=True,text=True,encoding='utf-8')
        assert check.returncode==0,check.stderr
        r['checks']['git_connectivity']=dict(exit_status=check.returncode,output=check.stdout,stderr=check.stderr)
        assert not Path('D:/Dandelion-Apartment-Experiment/official/apartment-v4').exists()
        r['checks']['v4_absent']=True
        r['passed']=True
    except BaseException as e:r.update(error=repr(e),traceback=traceback.format_exc())
    r.update(finished=now(),volumes=volumes());save(HERE/'verification.json',r);print(json.dumps(r),flush=True)
    return 0 if r['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
