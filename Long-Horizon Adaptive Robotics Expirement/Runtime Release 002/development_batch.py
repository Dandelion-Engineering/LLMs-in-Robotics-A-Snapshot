"""Bounded sequential development pilots inside one shared queue job.

Every episode is registered with exact source bytes before it starts. This
driver never records final Architecture Map results: the operator must first
verify the completed queue receipt and then run record_attempt.finish.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from datetime import datetime, timezone

HERE=Path(__file__).resolve().parent
from development_storage import location as development_location


def hashes():
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.glob('*.py'))}


def validate(plan):
    if not isinstance(plan,list) or not 1<=len(plan)<=8:raise ValueError('One to eight development episodes required')
    ids=set()
    for row in plan:
        if set(row)!={'run_id','kind','parts','seed','policy_noise_seed','cap','scenario','condition'}:raise ValueError('Unexpected plan fields')
        rid=row['run_id']
        if not isinstance(rid,str) or not rid.startswith('B01-dev-') or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in rid):raise ValueError('Invalid development run ID')
        if rid in ids:raise ValueError('Duplicate run ID')
        ids.add(rid)
        if row['kind'] not in ('baseline','A1','A2','A3') or row['parts'] not in (3,6,10):raise ValueError('Unknown entrant/horizon')
        if row['scenario'] not in ('nominal','order_change','restart','mixed') or row['condition'] not in ('persistent','no-persistence'):raise ValueError('Unknown scenario/condition')
        if any(type(row[k]) is not int or row[k]<0 for k in ('seed','policy_noise_seed')):raise ValueError('Explicit nonnegative development seeds required')
        if type(row['cap']) not in (int,float) or not 0<row['cap']<=900:raise ValueError('Cap outside bounded development allowance')
    return plan


def run(plan_path,output,development_restart_freeze=None,development_raw_root=None):
    import record_attempt
    raw=Path(plan_path).read_bytes();plan=validate(json.loads(raw));output=Path(output).resolve()
    locations={row['run_id']:development_location(row['run_id'],development_raw_root,require_fresh=True) for row in plan}
    output.mkdir(parents=True,exist_ok=False)
    source=hashes();attempts=[];stop=None
    qualification_path=Path(development_restart_freeze).resolve() if development_restart_freeze is not None else None
    qualification_hash=hashlib.sha256(qualification_path.read_bytes()).hexdigest() if qualification_path else None
    header={'scope':'development only; no scored inference','plan_sha256':hashlib.sha256(raw).hexdigest(),
            'runtime_sha256':source,'started_at':datetime.now(timezone.utc).isoformat(),'plan':plan,
            'development_storage':locations,
            'development_restart_freeze':({'path':str(qualification_path),'sha256':qualification_hash} if qualification_path else None)}
    (output/'plan.json').write_text(json.dumps(header,indent=2)+'\n',encoding='utf-8')
    for row in plan:
        if hashes()!=source:raise RuntimeError('Runtime changed during development batch')
        if qualification_path and hashlib.sha256(qualification_path.read_bytes()).hexdigest()!=qualification_hash:
            raise RuntimeError('Development qualification freeze changed')
        rid=row['run_id'];assigned=locations[rid]
        record_attempt.prepare(SimpleNamespace(**row,development_restart_freeze=qualification_path,development_raw_root=Path(assigned['raw_root'])))
        argv=[sys.executable,'-X','utf8','-B',str(HERE/'experiment.py')]
        for key,flag in (('kind','kind'),('parts','parts'),('seed','seed'),('policy_noise_seed','policy-noise-seed'),
                         ('cap','cap'),('scenario','scenario'),('condition','condition'),('run_id','run-id')):
            argv.extend(['--'+flag,str(row[key])])
        argv.extend(['--development-raw-root',assigned['raw_root']])
        if qualification_path:argv.extend(['--development-restart-freeze',str(qualification_path)])
        print(json.dumps({'starting':rid,'cap_s':row['cap']}),flush=True)
        with (output/(rid+'.log')).open('wb') as stream:
            proc=subprocess.Popen(argv,stdout=stream,stderr=subprocess.STDOUT,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            print(json.dumps({'episode_pid':proc.pid,'run_id':rid}),flush=True)
            code=proc.wait()
        if hashes()!=source:raise RuntimeError('Runtime changed during episode '+rid)
        if qualification_path and hashlib.sha256(qualification_path.read_bytes()).hexdigest()!=qualification_hash:
            raise RuntimeError('Development qualification freeze changed during episode '+rid)
        path=Path(assigned['evidence_dir'])/'result.json'
        if path.exists():
            result=json.loads(path.read_text(encoding='utf-8'))
            if result.get('run_id')!=rid or result.get('stage')!='development' or result.get('development_storage')!=assigned:
                raise ValueError('Development result differs from the pinned run identity/location')
            summary={k:result.get(k) for k in ('outcome','validity','failure_class','execution_status','wall_duration_s','maximum_lag_s','model_calls','total_tokens')}
            summary['accepted_count']=(result.get('independent_outcome') or {}).get('accepted_count')
            summary['result_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            summary['result_path']=str(path)
        else:summary={'missing_result':True}
        record={'run_id':rid,'exit_status':code,**summary};attempts.append(record)
        with (output/'attempts.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(record)+'\n')
        print(json.dumps(record),flush=True)
        if code or summary.get('missing_result') or summary.get('failure_class')=='infrastructure_failure':
            stop='Execution/infrastructure failure retained; remaining plan not started';break
    final={**header,'attempts':attempts,'stop_reason':stop,'ended_at':datetime.now(timezone.utc).isoformat(),
           'not_started':[r['run_id'] for r in plan[len(attempts):]],
           'queue_verification':'Pending external official succeeded/exit0 receipt; no final map results appended'}
    (output/'batch-result.json').write_text(json.dumps(final,indent=2)+'\n',encoding='utf-8')
    return final


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--development-restart-freeze',type=Path)
    p.add_argument('--development-raw-root',type=Path)
    args=p.parse_args();run(args.plan,args.output,args.development_restart_freeze,args.development_raw_root)
