"""Single-use source-bound shared-I/O reproduction; no success-seeking retry."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
CAMPAIGN=HERE.parent
RCI=CAMPAIGN.parent
REPO=RCI.parents[1]
MAP=RCI.parent/'Architecture Map'
QUEUE=Path('C:/Users/cresp/Documents/Dandelion Engineering/tools/compute_queue/compute_queue.py')
RUN='RCI001-C02-protected-io-001'
REV='RCI001-C02-dev-014'
RECORDS=HERE/RUN
MANIFEST=HERE/'protected-io-001-manifest.json'
OUTPUT=RCI/'local-evidence/campaign002/io-repair'/RUN
SNAPSHOT=MAP/'releases'/REV/'snapshot.json'

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,v):
    with Path(p).open('x',encoding='utf-8') as f:
        json.dump(v,f,indent=2);f.write('\n');f.flush()
        import os
        os.fsync(f.fileno())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p,n):
    spec=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','launch','settle']);a=p.parse_args()
    registry=load(CAMPAIGN/'registry.py','io_registry')
    if a.action=='prepare':
        value=read(HERE/'diagnostic/plan.json')
        if (value['run_id'],value['framework_revision'])!=(RUN,REV):raise ValueError('Fixed identities changed')
        sources=list((HERE/'diagnostic').glob('*.py'))+[HERE/'diagnostic/README.md',HERE/'diagnostic/plan.json',Path(__file__),
          CAMPAIGN/'harness/instrumented_journal.py',CAMPAIGN/'harness/instrumented_recorder.py']
        value['runtime_input_files']=sorted(p.relative_to(REPO).as_posix() for p in sources)
        save(MANIFEST,value)
        print(json.dumps(registry.freeze(MANIFEST,REV)))
    elif a.action=='launch':
        snapshot=read(SNAPSHOT)
        for name,row in snapshot['sources'].items():
            if sha(REPO/name)!=row['sha256']:raise ValueError('Frozen input drift: '+name)
        if sha(MANIFEST)!=snapshot['manifest_sha256']:raise ValueError('Manifest drift')
        if RECORDS.exists() or OUTPUT.exists():raise ValueError('Existing run footprint; never resubmit')
        RECORDS.mkdir()
        argv=[sys.executable,'-X','utf8','-B',str(HERE/'diagnostic/benchmark.py'),'--manifest',str(MANIFEST),'--output',str(OUTPUT)]
        save(RECORDS/'intent.json',{'argv':argv,'manifest_sha256':sha(MANIFEST),'snapshot_sha256':sha(SNAPSHOT)})
        raw=subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'submit','--project','LLMs-in-Robotics','--cwd',str(REPO),'--',*argv],text=True,encoding='utf-8')
        job=json.loads(raw);save(RECORDS/'submit.json',job)
        print(json.dumps({'job_id':job['id'],'run_id':RUN,'state':job['state']}))
    else:
        submitted=read(RECORDS/'submit.json')
        raw=subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',submitted['id']],text=True,encoding='utf-8')
        job=json.loads(raw);job=job.get('job',job)
        if job['state']!='succeeded' or type(job['exit_status']) is not int or job['exit_status']!=0:
            raise ValueError('Official succeeded/integer zero required: '+job['state'])
        if job['argv']!=read(RECORDS/'intent.json')['argv']:raise ValueError('Queue argv drift')
        save(RECORDS/'official-status.json',job)
        assessor=load(HERE/'diagnostic/assess.py','io_assessor')
        try:value=assessor.assess(MANIFEST,OUTPUT)
        except Exception as e:value={'passed':False,'error':{'type':type(e).__name__,'message':str(e)},'task_outcome':'unknown'}
        value['official_queue']={'path':str(RECORDS/'official-status.json'),'sha256':sha(RECORDS/'official-status.json')}
        save(HERE/'protected-io-001-assessment.json',value)
        print(json.dumps(registry.finish(RUN,HERE/'protected-io-001-assessment.json',RECORDS/'official-status.json',
            'valid' if value['passed'] else 'invalid','unknown','Bounded non-physics shared-durability diagnostic; completion and parity only, no timing qualification.')))
        print(json.dumps({'passed':value['passed'],'error':value.get('error'),'assessment':str(HERE/'protected-io-001-assessment.json')}))

if __name__=='__main__':main()
