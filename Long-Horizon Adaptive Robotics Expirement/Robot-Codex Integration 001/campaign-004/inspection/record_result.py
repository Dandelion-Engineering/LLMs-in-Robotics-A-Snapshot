"""Append the sole block disposition, preserving actual, invalid and not-run counts."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from common import QUEUE,sha,save
from register import append,mapcmd,ref

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))

def record(manifest_path,job_id,audit_root):
    manifest_path=Path(manifest_path).resolve();m=read(manifest_path);folder=manifest_path.parent
    audit_root=Path(audit_root).resolve();a=read(audit_root/'assessment/receipt.json');q=read(audit_root/'official-status.json')
    job=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',job_id],text=True,encoding='utf-8'))
    assert job['state'] in ('succeeded','failed','cancelled') and q['state'] in ('succeeded','failed','cancelled')
    assert (Path(job['cwd'])/job['argv'][-1]).resolve()==manifest_path
    assert a['source_manifest_sha256']==sha(manifest_path)
    r=read(Path(m['output'])/'receipt.json');save(folder/'official-status.json',job);save(folder/'receipt.json',r)
    valid=bool(job['state']=='succeeded' and type(job['exit_status']) is int and job['exit_status']==0
        and q['state']=='succeeded' and type(q['exit_status']) is int and q['exit_status']==0 and r['infrastructure_valid'] and a['passed'])
    passed=valid and r['passed'] and a['qualification_complete']
    occurrences=[]
    for number in range(1,4):
        attempts=[s for s in r['attempted_sessions'] if s['occurrence']==number]
        success=any(s['task_outcome']=='success' for s in attempts)
        occurrences.append(dict(occurrence=number,sessions=[s['session_id'] for s in attempts],
            status='not_run' if not attempts else 'success' if valid and success else 'failure' if valid else 'invalid_unknown',
            unused_opportunities=3-len(attempts)))
    result=dict(schema_version='architecture-map-1.0',id=m['run_id']+'-result',recorded_at=datetime.now(timezone.utc).isoformat(),
        author='Codex session 26',tags=['campaign-004','completed-block'],run_id=m['run_id'],supersedes_result_id=None,
        execution_status='completed' if job['state']=='succeeded' else 'failed',validity='valid' if valid else 'invalid',
        validity_reason='Original worker and independent reader succeeded with integer exit 0 and complete infrastructure checks.' if valid else 'Evidence or execution is invalid; retain all observations and do not replace the block.',
        outcome=('success' if passed else 'failure') if valid else 'unknown',ended_at=job['ended_at'],
        termination_reason='three_C_occurrences_complete' if passed else 'valid_task_failure' if valid else 'infrastructure_stop',metrics=[],
        evidence=[ref(folder/'official-status.json','Original queue disposition'),ref(folder/'receipt.json','Coordinator evidence'),
            ref(audit_root/'official-status.json','Independent reader queue disposition'),ref(audit_root/'assessment/receipt.json','Independent evidence audit')],
        details=dict(source_job=job_id,audit_job=q['id'],declared_occurrences=3,declared_max_sessions=9,
            actual_sessions=r['model_calls_requested'],accepted_occurrences=len(r['sessions']),
            not_run_occurrences=sum(o['status']=='not_run' for o in occurrences),occurrences=occurrences,
            allocation=m['allocation_reference'],scope='One descriptive persistent block; sessions and occurrences are not independent replicates.'))
    append('result',result,folder/'result-record.json');mapcmd('build');print(mapcmd('validate','--output','validation.json'))
    print(json.dumps(dict(valid=valid,passed=passed,occurrences=occurrences)),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('job');p.add_argument('audit');a=p.parse_args();record(a.manifest,a.job,a.audit)
