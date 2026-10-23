"""One guarded diagnostic model submission; never retries or admits scored slots."""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

CAMPAIGN=Path(__file__).resolve().parents[1]
RCI=CAMPAIGN.parent
REPO=RCI.parents[1]
QUEUE=Path('C:/Users/cresp/Documents/Dandelion Engineering/tools/compute_queue/compute_queue.py')
GUARD=RCI/'campaign-001/admission/storage-guard/storage_guard.py'
sys.path.insert(0,str(CAMPAIGN/'assessment'))
import assess

def save(path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2);stream.write('\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--mode',choices=['smoke','pilot','host-probe'],required=True);a=p.parse_args()
    manifest=json.loads(a.manifest.read_text(encoding='utf-8'));snapshot=json.loads(a.snapshot.read_text(encoding='utf-8'))
    if not str(manifest.get('qualification_stage','')).startswith('campaign002-'):raise ValueError('Qualification only')
    if assess.frozen_problems(a.snapshot,snapshot,manifest['framework_revision']):raise ValueError('Frozen source mismatch')
    run_id=manifest['run_id'];records=CAMPAIGN/'qualification'/run_id
    root=RCI/'local-evidence/campaign002/qualification'/run_id
    evidence=root if a.mode=='host-probe' else root/'orchestrator'
    host=root/'host';workspace=Path(manifest['runtime_workspace'])
    for path in (records,evidence,host,workspace):
        if path.exists():raise ValueError('Existing intent/output refuses resubmission: '+str(path))
    records.mkdir()
    if a.mode=='host-probe':
        if manifest.get('qualification_stage')!='campaign002-host-probe-qualification' or manifest.get('model_turns_max')!=0:
            raise ValueError('Host diagnostic must declare no model calls')
        argv=[sys.executable,'-X','utf8','-B',str(CAMPAIGN/'qualification/host_probe.py'),'run',
              '--manifest',str(a.manifest.resolve()),'--output',str(evidence)]
    else:
        argv=[sys.executable,'-X','utf8','-B',str(CAMPAIGN/'harness/physical.py'),'--manifest',str(a.manifest.resolve()),
              '--evidence',str(evidence),'--host-evidence',str(host),'--workspace',str(workspace),'--mode',a.mode]
    intent={'run_id':run_id,'created_at':datetime.now(timezone.utc).isoformat(),'argv':argv,
            'snapshot':str(a.snapshot.resolve()),'snapshot_sha256':assess.hash_file(a.snapshot),
            'manifest_sha256':assess.hash_file(a.manifest),'records':str(records),
            'evidence':str(evidence),'host_evidence':str(host),'workspace':str(workspace)}
    save(records/'launch-intent.json',intent)
    guard_argv=[sys.executable,'-X','utf8','-B',str(GUARD),'monitor',
                '--config',str(CAMPAIGN/'admission/storage-policy.json'),
                '--baseline',str(CAMPAIGN/'admission/storage-baseline-001.json'),
                '--output',str(records/'storage'),'--job-file',str(records/'queue-submit.json'),
                '--run-id',run_id,'--manifest',str(a.manifest.resolve()),'--evidence',str(evidence),
                '--host-evidence',str(host),'--workspace',str(workspace)]
    with (records/'monitor.stdout').open('x',encoding='utf-8') as out,(records/'monitor.stderr').open('x',encoding='utf-8') as err:
        monitor=subprocess.Popen(guard_argv,cwd=REPO,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
    save(records/'monitor-process.json',{'pid':monitor.pid,'argv':guard_argv})
    deadline=time.monotonic()+45
    while not (records/'storage/ready.json').exists():
        if monitor.poll() is not None or (records/'storage/admission-stop.json').exists():raise RuntimeError('Storage monitor not ready')
        if time.monotonic()>deadline:raise RuntimeError('Storage monitor readiness deadline')
        time.sleep(.2)
    # A prior ready receipt does not authorize submission after a monitor exit
    # or a later stop latch. Recheck immediately before the queue mutation.
    if monitor.poll() is not None or (records/'storage/admission-stop.json').exists():
        raise RuntimeError('Storage monitor exited or latched admission stop; no queue submission')
    raw=subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'submit','--project','LLMs-in-Robotics',
                                 '--cwd',str(REPO),'--',*argv],cwd=REPO,text=True,encoding='utf-8')
    job=json.loads(raw);save(records/'queue-submit.json',job)
    print(json.dumps({'run_id':run_id,'job_id':job['id'],'state':job['state'],'records':str(records)}))

if __name__=='__main__':main()
