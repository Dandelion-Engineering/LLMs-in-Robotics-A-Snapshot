"""Authenticate current admission without repeating commissioning or launching."""
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
import traceback
from admission_checks import *

HERE=Path(__file__).resolve().parent

def main():
    out=HERE/'output';out.mkdir(exist_ok=False)
    result=dict(passed=False,observed_utc=datetime.now(timezone.utc).isoformat(),checks={},official_starts=0)
    try:
        for name,row in read(HERE/'manifest.json')['files'].items():assert sha(HERE/name)==row['sha256'],name
        assert not PAIR.exists(),'The selected official pair path is already used'
        result['checks']['pair_path_unused']=True
        release=OLD/'release002';cert_path=OLD/'audit003/output/certificate.json'
        assert sha(release/'manifest.json')=='d7d28df30a01ff7ee11bfa2f8025ccc1499856d3ba6e6e76fabb44735d979d3a'
        assert sha(cert_path)=='49ac8e59a7af7b0e7b14c9c66eb3a5007984762c33e9382761cd44346d64054f'
        manifest=read(release/'manifest.json');cert=read(cert_path);proof=read(OLD/'audit003/output/result.json')
        q=queue('status','20261010T011547899365Z-58dc1abf')
        assert q['state']=='succeeded' and type(q['exit_status']) is int and q['exit_status']==0
        assert cert==proof['certificate'] and proof['passed'] and len(proof['checks'])==10 and all(proof['checks'].values())
        assert cert['passed'] and cert['release_manifest_sha256']==sha(release/'manifest.json')
        assert inventory(release/'frozen_repository')==manifest['files']
        for name,row in manifest['files'].items():assert sha(REPO/name)==row['sha256'],name
        for name,digest in cert['attempt_results'].items():
            assert sha(OLD/name/'output/result.json')==digest,name
            receipt=read(REPO/APPREL/'operations/session-39'/(name+'-queue.json'))
            status=queue('status',receipt['id'])
            assert status['state']=='succeeded' and type(status['exit_status']) is int and status['exit_status']==0,name
        result['certificate']=dict(sha256=sha(cert_path),path=str(cert_path),release_manifest_sha256=sha(release/'manifest.json'),source_files=len(manifest['files']),audit_queue=q)
        result['checks']['certificate_and_frozen_working_sources']=True
        program='import json;from run import source_identity;from environment import identity;from revision_config import CONFIG;print(json.dumps(dict(source=source_identity(),environment=identity(),config=CONFIG)))'
        identities=[]
        for source in (REPO/APPREL,release/'frozen_repository'/APPREL):
            actual=json.loads(output(sys.executable,'-X','utf8','-B','-c',program,cwd=source))
            assert actual['source']==cert['source_identity'] and actual['environment']==cert['environment'] and actual['config']==cert['config'],str(source)
            identities.append(dict(path=str(source),source_components=len(actual['source']),environment=actual['environment'],config=actual['config']))
        result['identities']=identities;result['checks']['current_and_frozen_environment_source_config']=True
        previous=read(REPO/APPREL/'operations/session-40/verification.json')['checks']['critical_hashes_after']['official']
        for path,digest in previous.items():assert sha(path)==digest,path
        schedule=sha(PAIR.parent/'apartment-v2/hidden-schedule.json')
        for name in ('apartment-v1','apartment-v2','apartment-v3'):
            assert read(PAIR.parent/name/'prepared.json')['schedule_sha256']==schedule
        from collections import Counter
        sys.path.insert(0,str(release/'frozen_repository'/APPREL))
        from schedule import validate
        validate(read(PAIR.parent/'apartment-v2/hidden-schedule.json'))
        result['critical_historical_hashes']=previous
        result['schedule_sha256']=schedule
        result['failed_freeze001_inventory']=inventory(OLD/'freeze001')
        failure=queue('status','20261010T014859761097Z-2776dac0')
        assert failure['state']=='failed' and type(failure['exit_status']) is int and failure['exit_status']==1
        assert not (OLD/'freeze001/output/result.json').exists()
        result['checks']['original_schedule_critical_history_failed_attempt_preserved']=True
        result['storage']=storage()
        assert result['storage']['minimum_gate'] and result['storage']['headroom_gate']
        assert result['storage']['allocation_unit_bytes']==1048576
        result['checks']['original_gate_and_physical_allocation_headroom']=True
        result['quiescence']=quiescence()
        assert result['quiescence']['passed'],'Conflicting process, queue, mount, lock or monitor'
        result['checks']['runtime_queue_mount_monitor_quiescence']=True
        result['passed']=True
    except BaseException as e:
        result.update(error=repr(e),traceback=traceback.format_exc())
    result['finished_utc']=datetime.now(timezone.utc).isoformat()
    with (out/'result.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:result.get(k) for k in ('passed','checks','storage','error','traceback')}),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
