"""Append scored and not-run dispositions without replacing any prior evidence."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

AREA=Path(__file__).resolve().parent
sys.path.insert(0,str(AREA.parent))
from common import QUEUE,sha,save
from register import append,mapcmd,ref
from freeze import fields


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def record(manifest_path,job_id,audit_root):
    manifest_path=Path(manifest_path).resolve();manifest=read(manifest_path);folder=manifest_path.parent
    assert manifest['stage']=='reviewed_campaign'
    job=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',job_id],text=True,encoding='utf-8'))
    assert job['state'] in ('succeeded','failed','canceled','interrupted','worker_start_failed')
    assert (Path(job['cwd'])/job['argv'][-1]).resolve()==manifest_path
    save(folder/'official-status.json',job)
    evidence=[ref(folder/'official-status.json','Original authenticated queue disposition')]
    source_receipt=Path(manifest['output'])/'receipt.json'
    observed=read(source_receipt) if source_receipt.exists() else None
    if observed is not None:
        save(folder/'receipt.json',observed);evidence.append(ref(folder/'receipt.json','Original coordinator evidence'))
    audit=official=None
    if audit_root is not None:
        audit_root=Path(audit_root).resolve();official=read(audit_root/'official-status.json')
        assert official['state'] in ('succeeded','failed','canceled','interrupted','worker_start_failed')
        evidence.append(ref(audit_root/'official-status.json','Original independent-reader queue disposition'))
        if (audit_root/'assessment/receipt.json').exists():
            audit=read(audit_root/'assessment/receipt.json')
            assert audit['source_manifest_sha256']==sha(manifest_path)
            assert read(audit_root/'assessment/source-job.json')['id']==job_id
            evidence.append(ref(audit_root/'assessment/receipt.json','Independent evidence assessment'))
    source_ok=job['state']=='succeeded' and type(job['exit_status']) is int and job['exit_status']==0
    reader_ok=official is not None and official['state']=='succeeded' and type(official['exit_status']) is int and official['exit_status']==0
    valid=bool(source_ok and observed and observed['infrastructure_valid'] and reader_ok and audit and audit['passed'])
    passed=bool(valid and observed['passed'] and audit['qualification_complete'])
    if valid:assert bool(observed['passed'])==bool(audit['qualification_complete'])
    result={**fields(manifest['run_id']+'-result'),'run_id':manifest['run_id'],'supersedes_result_id':None,
        'execution_status':'completed' if job['state']=='succeeded' else 'aborted' if job['state']=='canceled' else 'failed',
        'validity':'valid' if valid else 'invalid','validity_reason':
            'Original worker and independent evidence reader succeeded/int0 and all infrastructure checks passed.' if valid else
            'Infrastructure failed or remains unqualified; preserve the original evidence and stop scored admission.',
        'outcome':('success' if passed else 'failure') if valid else 'unknown','ended_at':job['ended_at'],
        'termination_reason':'three_C_encounters_complete' if passed else 'valid_task_failure' if valid else 'infrastructure_stop',
        'metrics':[],'evidence':evidence}
    result['details']=dict(not_scored=False,source_job_id=job_id,independent_audit_job_id=official['id'] if official else None,
        declared_encounters=3,attempted_encounters=len(observed.get('attempted_sessions',[])) if observed else None,
        accepted_terminals=len(observed.get('sessions',[])) if observed else None,
        not_run_encounters=3-len(observed.get('attempted_sessions',[])) if observed else None,
        allocation=manifest['allocation_reference'],local_evidence=manifest['output'])
    append('result',result,folder/'result-record.json');mapcmd('build');print(mapcmd('validate','--output','validation.json'))
    print(json.dumps(dict(recorded=manifest['run_id'],valid=valid,passed=passed)),flush=True)


def not_run(manifest_path,reason,stop_evidence):
    manifest_path=Path(manifest_path).resolve();manifest=read(manifest_path);folder=manifest_path.parent
    assert manifest['stage']=='reviewed_campaign' and not Path(manifest['output']).exists()
    assert not (folder/'queue-submission.json').exists(), 'Not-run accounting requires no queued launch'
    result={**fields(manifest['run_id']+'-result'),'run_id':manifest['run_id'],'supersedes_result_id':None,
        'execution_status':'not_run','validity':'unknown','validity_reason':reason,'outcome':'not_assessed',
        'ended_at':None,'termination_reason':'predeclared_campaign_stop','metrics':[],
        'evidence':[ref(Path(stop_evidence).resolve(),'Retained campaign stopping evidence')]}
    result['details']=dict(not_scored=False,declared_encounters=3,attempted_encounters=0,not_run_encounters=3,
        allocation=manifest['allocation_reference'])
    append('result',result,folder/'result-record.json');mapcmd('build');print(mapcmd('validate','--output','validation.json'))


if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    q=sub.add_parser('record');q.add_argument('manifest');q.add_argument('job');q.add_argument('--audit')
    q=sub.add_parser('not-run');q.add_argument('manifest');q.add_argument('reason');q.add_argument('stop_evidence')
    a=p.parse_args()
    record(a.manifest,a.job,a.audit) if a.action=='record' else not_run(a.manifest,a.reason,a.stop_evidence)
