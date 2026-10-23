"""Official queue metadata only; never open log paths or attempt outputs."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

HERE=Path(__file__).resolve().parent
C=HERE.parents[1]; REPO=C.parents[2]
QUEUE=REPO.parent/'tools/compute_queue/compute_queue.py'
START='2026-09-30T16:54:00Z'

def stamp(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def save(p,x):
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,indent=2);f.write('\n')
def bind(p):
    raw=p.read_bytes();return {'path':str(p.resolve()),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--snapshot',required=True)
    args=parser.parse_args();assert re.fullmatch(r'[a-z0-9-]+',args.snapshot)
    folder=HERE/args.snapshot;folder.mkdir(exist_ok=False)
    argv=[sys.executable,'-X','utf8','-B',str(QUEUE),'list','--project','LLMs-in-Robotics']
    proc=subprocess.run(argv,cwd=REPO,capture_output=True,text=True,encoding='utf-8',check=True)
    value=json.loads(proc.stdout)
    jobs=value.get('jobs',[]) if isinstance(value,dict) else value
    assert isinstance(jobs,list) and jobs
    selected=sorted((j for j in jobs if j['cwd']==str(REPO) and stamp(j['submitted_at'])>=stamp(START)),key=lambda j:j['submitted_at'])
    assert selected and len({j['id'] for j in selected})==len(selected)
    states=Counter(j['state'] for j in selected)
    durations=[]
    for j in selected:
        if j.get('started_at') is not None and j.get('ended_at') is not None:
            seconds=(stamp(j['ended_at'])-stamp(j['started_at'])).total_seconds()
            assert seconds>=0
            durations.append({'id':j['id'],'state':j['state'],'seconds':seconds})
    save(folder/'official-jobs.json',{'queried_at':datetime.now(timezone.utc).isoformat(),'argv':argv,
         'exit_code':proc.returncode,'project': 'LLMs-in-Robotics','cwd':str(REPO),
         'submitted_at_lower_bound_inclusive':START,'jobs':selected})
    summary={'schema':'campaign002-session19-queue-metadata-1','as_of':datetime.now(timezone.utc).isoformat(),
        'official':bind(folder/'official-jobs.json'),'collector':bind(Path(__file__)),
        'job_count':len(selected),'states':dict(states),'completed_started_jobs':len(durations),
        'completed_started_occupancy_seconds':sum(x['seconds'] for x in durations),'durations':durations,
        'model_calls':None,'billing':None,'task_outcome':None,
        'scope':'Official metadata for project/cwd jobs submitted during Session19. Durations are queue child wall occupancy, not model time or concurrency-adjusted session time. Active durations excluded, never zero. Queue success is not qualification. No logs or empirical outputs read; no inference count or billing claim.'}
    save(folder/'summary.json',summary)
    print(json.dumps({k:summary[k] for k in ['as_of','job_count','states','completed_started_jobs','completed_started_occupancy_seconds','scope']}))

if __name__=='__main__':main()
