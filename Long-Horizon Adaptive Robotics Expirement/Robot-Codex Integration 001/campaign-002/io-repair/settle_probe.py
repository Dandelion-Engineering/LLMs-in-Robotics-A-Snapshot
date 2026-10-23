"""Authenticate one new host probe, retain its independent verdict, never retry."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
CAMPAIGN=HERE.parent
RCI=CAMPAIGN.parent
REPO=RCI.parents[1]
QUEUE=Path('C:/Users/cresp/Documents/Dandelion Engineering/tools/compute_queue/compute_queue.py')

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,v):
    if Path(p).exists():
        if read(p)!=v:raise ValueError('Changed retained receipt: '+str(p))
        return
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2);f.write('\n')
def load(p,n):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def main():
    p=argparse.ArgumentParser();p.add_argument('--number',required=True);p.add_argument('--revision',required=True);a=p.parse_args()
    name='host-probe-'+a.number;run_id='RCI001-C02-'+name
    records=CAMPAIGN/'qualification'/run_id
    submit=read(records/'queue-submit.json')
    job=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',submit['id']],text=True,encoding='utf-8'))
    job=job.get('job',job)
    if job['state'] in ('queued','running','cancel_requested'):
        print(json.dumps({'state':job['state'],'job_id':job['id']}));return
    save(records/'official-status.json',job)
    if job['state']!='succeeded' or type(job['exit_status']) is not int or job['exit_status']!=0:
        raise ValueError('Official queue failed; no scientific outcome consumption')
    manifest=CAMPAIGN/'qualification'/(name+'-manifest.json')
    snapshot=RCI.parent/'Architecture Map/releases'/a.revision/'snapshot.json'
    assessor=load(CAMPAIGN/'qualification/assess_host_probe.py','probe_assessor')
    value=assessor.evaluate(manifest,RCI/'local-evidence/campaign002/qualification'/run_id,records/'official-status.json',snapshot)
    target=CAMPAIGN/'qualification'/(name+'-assessment.json')
    if target.exists():raise ValueError('Existing assessment; reconcile, never register twice')
    save(target,value)
    registry=load(CAMPAIGN/'registry.py','probe_registry')
    print(json.dumps(registry.finish(run_id,target,records/'official-status.json',
        'valid' if value['diagnostic_passed'] else 'invalid','unknown',
        'Fixed continuous-physics infrastructure diagnostic '+('passed' if value['diagnostic_passed'] else 'failed')+'; no model, no scored recovery.')))
    print(json.dumps({'run_id':run_id,'diagnostic_passed':value['diagnostic_passed'],'checks':value['checks'],'errors':value['errors']}))

if __name__=='__main__':main()
