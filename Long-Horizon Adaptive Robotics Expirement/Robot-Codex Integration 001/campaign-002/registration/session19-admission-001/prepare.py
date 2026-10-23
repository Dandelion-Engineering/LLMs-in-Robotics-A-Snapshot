"""Prepare the authorized prospective admission once; never launch scored work."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
C=HERE.parents[1]
REPO=C.parents[2]
Q=C/'qualification'
A=C/'admission'
MAP=C.parent.parent/'Architecture Map'
QUEUE=REPO.parent/'tools/compute_queue/compute_queue.py'
SNAPSHOT=MAP/'releases/RCI001-C02-dev-114/snapshot.json'
COMPLETED=Q/'final-qualification-033/completed.json'

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def identity(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def save(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2);f.write('\n');f.flush()
def sources():
    return {str(p):sha(p) for p in [Path(__file__),C/'prepare_scored.py',A/'prepare_index.py',
        A/'prepare_certificate.py',C/'admission.py',C/'PLAN.md',COMPLETED,SNAPSHOT,
        Q/'final-qualification-033-readiness.json',Q/'run_final_qualification_v33.py']}
def command(args):return [sys.executable,'-X','utf8','-B',*map(str,args)]
def fresh(job):
    return json.loads(subprocess.check_output(command([QUEUE,'status',job]),text=True,encoding='utf-8'))
def absent():
    targets=[C/'predeclared-v1',C/'execution-plan.json',A/'qualification-index-v33.json',
        A/'certificate-candidate-v33.json',A/'sealed-v1',A/'sealed-v1.pending',
        MAP/'releases/RCI001-C02-frozen-001',C/'execution/campaign-stop.json']
    assert all(not p.exists() for p in targets), 'An admission or scored footprint already exists'
    return [str(p) for p in targets]
def step(name,args):
    save(HERE/(name+'-intent.json'),{'argv':command(args),'created_at':datetime.now(timezone.utc).isoformat()})
    with (HERE/(name+'.stdout')).open('x',encoding='utf-8') as out,(HERE/(name+'.stderr')).open('x',encoding='utf-8') as err:
        result=subprocess.run(command(args),cwd=REPO,stdout=out,stderr=err)
    save(HERE/(name+'-completion.json'),{'exit_code':result.returncode,'stdout':identity(HERE/(name+'.stdout')),'stderr':identity(HERE/(name+'.stderr'))})
    if result.returncode:raise RuntimeError(name+' failed; preserve all created paths and reconcile, never rerun unchanged')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['submit','run']);args=parser.parse_args()
    if args.action=='submit':
        save(HERE/'intent.json',{'sources':sources(),'absent_targets':absent(),'created_at':datetime.now(timezone.utc).isoformat(),
            'scope':'Prospective fixed twenty-slot admission only; no scored launch or new authorization.'})
        job=json.loads(subprocess.check_output(command([QUEUE,'submit','--project','LLMs-in-Robotics','--cwd',REPO,'--',
            sys.executable,'-X','utf8','-B',Path(__file__).resolve(),'run']),text=True,encoding='utf-8'))
        save(HERE/'submit.json',job);print(json.dumps({'job_id':job['id'],'state':job['state']}));return
    bound=read(HERE/'intent.json');assert bound['sources']==sources();absent()
    completed=read(COMPLETED)
    entries=[completed['native'],completed['boundary'],completed['smoke'],*completed['pilots']]
    assert len(entries)==5 and read(SNAPSHOT)['revision']=='RCI001-C02-dev-114'
    jobs=[]
    for entry in entries:
        saved=read(entry['queue']['path']);job=fresh(saved['id'])
        assert job['state']=='succeeded' and type(job['exit_status'])is int and job['exit_status']==0
        assert all(saved.get(k)==job.get(k) for k in ['id','state','exit_status','argv','cwd','started_at','ended_at'])
        jobs.append(job)
    assert len({j['id'] for j in jobs})==5
    save(HERE/'fresh-official-qualification.json',{'jobs':jobs,'completed':identity(COMPLETED)})
    index=A/'qualification-index-v33.json'
    argv=[A/'prepare_index.py','--snapshot',SNAPSHOT,'--output',index]
    for flag,entry in zip(['native','boundary','smoke','pilot-stock','pilot-home'],entries):
        argv+=['--'+flag,*[entry[k]['path'] for k in ['manifest','snapshot','queue','assessment']],entry['evidence']]
        if flag not in ['native','boundary']:argv.append(entry['host_evidence'])
    step('index',argv)
    step('allocation',[C/'prepare_scored.py','--snapshot',SNAPSHOT,'--output',C/'predeclared-v1'])
    step('certificate',[A/'prepare_certificate.py','--snapshot',SNAPSHOT,'--qualification-index',index,'--candidate',A/'certificate-candidate-v33.json'])
    assert bound['sources']==sources()
    seal=read(A/'sealed-v1/seal.json');certificate=A/'sealed-v1/certificate.json'
    assert seal['certificate_sha256']==sha(certificate) and len(read(certificate)['attempts'])==20
    save(HERE/'verified-preparation.json',{'prepared':True,'scored_started':False,'certificate':identity(certificate),
        'seal':identity(A/'sealed-v1/seal.json'),'index':identity(index),'schedule':identity(C/'predeclared-v1/schedule.json'),
        'execution_plan':identity(C/'execution-plan.json'),'source_snapshot':identity(SNAPSHOT),'sources_unchanged':True,
        'scope':'Prospective admission prepared; root must authenticate this queue job before consuming or releasing it.'})
    print(json.dumps({'prepared':True,'attempts':20,'certificate_sha256':sha(certificate),'scored_started':False}))

if __name__=='__main__':main()
