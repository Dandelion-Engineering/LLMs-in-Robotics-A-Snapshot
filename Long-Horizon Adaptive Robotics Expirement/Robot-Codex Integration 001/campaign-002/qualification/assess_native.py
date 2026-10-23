"""Authenticate and independently replay all six no-model reference outcomes."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

CAMPAIGN=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(CAMPAIGN/'assessment'))
import assess as base
REPO=base.REPO

def stamp(value):return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()

def evaluate(manifest_path,receipt_path,output,snapshot_path,expected_revision):
    job=base.queue_gate(base.read_json(receipt_path))
    manifest_path,output,snapshot_path=map(Path,(manifest_path,output,snapshot_path))
    argv=job.get('argv',[])
    expected=[str(REPO/'venv/Scripts/python.exe'),'-X','utf8','-B',str(CAMPAIGN/'qualification/native_suite.py'),
              '--manifest',str(manifest_path),'--output',str(output)]
    base.require(len(argv)==len(expected),'Wrong native suite command length')
    for i,(actual,wanted) in enumerate(zip(argv,expected)):
        base.require((Path(job['cwd'])/actual).resolve()==Path(wanted).resolve() if i in (0,4,6,8) else actual==wanted,
                     'Wrong direct native suite command')
    base.require(Path(job['cwd']).resolve()==REPO.resolve() and Path(job['resolved_executable']).resolve()==Path(expected[0]).resolve(),
                 'Wrong native suite cwd/interpreter')
    frozen=base.read_json(snapshot_path)
    # This no-model apparatus was sealed before the external assessment existed.
    # Authenticate its complete implementation; separately retain assessor hashes.
    # Scored/model consumers additionally require their assessors in the seal.
    base.require(frozen.get('revision')==expected_revision and not base.source_integrity(frozen,snapshot_path.with_name('code.zip')),
                 'Native qualification archive/revision mismatch')
    base.require(all((REPO/name).is_file() and base.hash_file(REPO/name)==row['sha256']
                     for name,row in frozen['sources'].items()),'Native qualification source mismatch')
    plan=base.read_json(manifest_path)
    base.require(base.hash_file(manifest_path)==frozen['manifest_sha256'] and plan['run_id']==frozen['run_id']
                 and plan['framework_revision']==expected_revision and len(plan['slots'])==6,'Wrong frozen native manifest')
    summary=base.read_json(output/'suite-result.json')
    base.require(summary['run_id']==plan['run_id'] and len(summary['rows'])==6 and summary['model_calls']==0,
                 'Native suite missing dispositions')
    rows=[]
    for slot in plan['slots']:
        root=output/slot['run_id'];host=root/'host';checks={};errors={}
        execution=base.read_json(root/'execution.json');result=base.read_json(host/'result.json')
        registry=base.read_json(host/'command-registry.json');history=base.jsonl(host/'public-history.jsonl')
        outcome=base.classify_outcome(result,registry,history)
        checks.update(execution_exit_zero=type(execution['exit_code']) is int and execution['exit_code']==0,
            execution_inside_queue=stamp(job['started_at'])<=execution['started_unix_s']<=execution['ended_unix_s']<=stamp(job['ended_at']),
            manifest_exact=base.read_json(root/'manifest.json')==slot['manifest']==base.read_json(host/'manifest.json'),
            reference_only=result['reference_recovery'] is True and result['robot_invocations']==0,
            host_clean=result['execution_completed'] is True and result.get('error') is None,
            independent_success=outcome['independent_task_outcome']=='success' and not outcome['independent_outcome_evidence_problems'],
            baseline_help_and_handback=result['baseline_help_observed'] is True and result['handbacks']==1,
            reserve_preserved=min(execution['free_before'],execution['free_after'])>=102_000_000_000,
            frozen_runtime_loaded=base.source_receipt_matches(base.read_json(host/'frozen-source-verification.json'),frozen,
                'Long-Horizon Adaptive Robotics Expirement/Runtime 004'),
            frozen_recorder_loaded=base.source_receipt_matches(base.read_json(host/'recorder-source-verification.json'),frozen,
                'Long-Horizon Adaptive Robotics Expirement/Storage Retention Implementation 001/future'))
        timing=None
        try:
            timing=base.verify_timing(host,result,frozen);checks['strict_fresh_timing']=timing['passed'] is True
        except Exception as error:checks['strict_fresh_timing']=False;errors['timing']=str(error)
        rows.append({'run_id':slot['run_id'],'family':slot['manifest']['family'],'checks':checks,'errors':errors,
            'passed':all(value is True for value in checks.values()),'terminal':result['terminal'],
            'timing':timing,'independent_outcome':outcome,'host_result_sha256':base.hash_file(host/'result.json'),
            'history_sha256':base.hash_file(host/'public-history.jsonl')})
    return {'schema':'campaign002-native-assessment-1','run_id':plan['run_id'],'queue_job_id':job['id'],
        'framework_revision':expected_revision,'source_snapshot_sha256':base.hash_file(snapshot_path),
        'qualification_passed':all(row['passed'] for row in rows),'rows':rows,
        'bindings':{'manifest':{'path':str(manifest_path.resolve()),'sha256':base.hash_file(manifest_path)},
          'queue':{'path':str(Path(receipt_path).resolve()),'sha256':base.hash_file(receipt_path)},
          'snapshot':{'path':str(snapshot_path.resolve()),'sha256':base.hash_file(snapshot_path)},
          'assessor_sha256':base.hash_file(__file__),'base_assessor_sha256':base.hash_file(CAMPAIGN/'assessment/assess.py')},
        'scope':'Strict apparatus and protected reference-control qualification; no model or recovery-behavior score'}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('manifest','queue-receipt','evidence','snapshot','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--framework-revision',required=True);a=p.parse_args()
    value=evaluate(a.manifest,a.queue_receipt,a.evidence,a.snapshot,a.framework_revision)
    with a.output.open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    print(json.dumps({'qualification_passed':value['qualification_passed'],
      'rows':[{'run_id':r['run_id'],'passed':r['passed'],'failed':[k for k,v in r['checks'].items() if not v]} for r in value['rows']]}))
