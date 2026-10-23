"""Register the sealed allocation once, then launch its existing coordinator."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
C=HERE.parents[1]
REPO=C.parents[2]
QUEUE=REPO.parent/'tools/compute_queue/compute_queue.py'
MAP=C.parent.parent/'Architecture Map'
CERT=C/'admission/sealed-v1/certificate.json'
DIGEST='47e8430b60edd5289f318eaa9ed576e2d6d1ce59dda1b13505e15f6fca0f4244'
RELEASE=MAP/'releases/RCI001-C02-frozen-001'
REG=RELEASE/'registration.json'

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def identity(p):return {'path':str(Path(p).resolve()),'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()}
def save(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2);f.write('\n');f.flush()
def py(*args):return [sys.executable,'-X','utf8','-B',*map(str,args)]
def successful(job_id):
    job=json.loads(subprocess.check_output(py(QUEUE,'status',job_id),text=True,encoding='utf-8'))
    assert job['id']==job_id and job['state']=='succeeded' and type(job['exit_status'])is int and job['exit_status']==0
    return job
def sources():return [identity(p) for p in [Path(__file__),CERT,C/'registry.py',C/'registry_session19.py',C/'run_campaign.py']]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['submit-release','run-release','launch']);args=parser.parse_args()
    assert identity(CERT)['sha256']==DIGEST
    if args.action=='submit-release':
        assert not RELEASE.exists()
        prepared=successful('20260930T213232853263Z-51ed84f8')
        proof=read(C/'registration/session19-admission-001/verified-preparation.json')
        assert proof['prepared']is True and proof['certificate']==identity(CERT)
        save(HERE/'release-intent.json',{'sources':sources(),'preparation_job':prepared,'created_at':datetime.now(timezone.utc).isoformat()})
        job=json.loads(subprocess.check_output(py(QUEUE,'submit','--project','LLMs-in-Robotics','--cwd',REPO,'--',*py(Path(__file__).resolve(),'run-release')),text=True,encoding='utf-8'))
        save(HERE/'release-submit.json',job);print(json.dumps({'job_id':job['id'],'state':job['state']}));return
    if args.action=='run-release':
        assert not RELEASE.exists() and read(HERE/'release-intent.json')['sources']==sources()
        successful('20260930T213232853263Z-51ed84f8')
        argv=py(C/'registry_session19.py','release','--certificate',CERT,'--certificate-sha256',DIGEST)
        with (HERE/'release.stdout').open('x',encoding='utf-8') as out,(HERE/'release.stderr').open('x',encoding='utf-8') as err:
            result=subprocess.run(argv,cwd=REPO,stdout=out,stderr=err)
        save(HERE/'release-command.json',{'exit_code':result.returncode,'argv':argv,'stdout':identity(HERE/'release.stdout'),'stderr':identity(HERE/'release.stderr')})
        if result.returncode:raise RuntimeError('Release failed; preserve records and reconcile, never repeat registration blindly')
        reg=read(REG);cert=read(CERT)
        assert len(reg['attempts'])==20 and [r['run_id'] for r in reg['attempts']]==[r['run_id'] for r in cert['attempts']]
        assert reg['certificate_sha256']==DIGEST
        for r in reg['attempts']:assert identity(r['run_record']['path'])==r['run_record']
        assert read(HERE/'release-intent.json')['sources']==sources()
        save(HERE/'verified-release.json',{'registered':20,'registration':identity(REG),'certificate':identity(CERT),'sources_unchanged':True,'scored_started':False})
        print(json.dumps({'registered':20,'scored_started':False}));return
    job=successful(read(HERE/'release-submit.json')['id'])
    release=read(HERE/'verified-release.json')
    assert release['registered']==20 and release['registration']==identity(REG) and release['certificate']==identity(CERT)
    cert=read(CERT);coordinator=C/'run_campaign.py'
    assert cert['artifacts']['campaign_coordinator']==identity(coordinator)
    assert all(not (HERE/n).exists() for n in ['launch-intent.json','process.json','completion.json','coordinator.stdout','coordinator.stderr'])
    assert all(not (C/'execution'/r['run_id']).exists() for r in cert['attempts'])
    argv=py(coordinator,'--registration',REG)
    save(HERE/'launch-intent.json',{'argv':argv,'cwd':str(REPO),'runner':identity(__file__),'coordinator':identity(coordinator),
        'certificate':identity(CERT),'registration':identity(REG),'release_job':job,'created_at':datetime.now(timezone.utc).isoformat(),
        'scope':'Existing authorized fixed twenty-slot campaign; unchanged guarded operator and stopping rules.'})
    with (HERE/'coordinator.stdout').open('x',encoding='utf-8') as out,(HERE/'coordinator.stderr').open('x',encoding='utf-8') as err:
        process=subprocess.Popen(argv,cwd=REPO,stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        save(HERE/'process.json',{'pid':process.pid,'argv':argv,'launched_at':datetime.now(timezone.utc).isoformat(),'launch_intent':identity(HERE/'launch-intent.json')})
        print(json.dumps({'coordinator_pid':process.pid,'state':'running'}),flush=True)
        code=process.wait()
    save(HERE/'completion.json',{'exit_code':code,'ended_at':datetime.now(timezone.utc).isoformat(),'stdout':identity(HERE/'coordinator.stdout'),
        'stderr':identity(HERE/'coordinator.stderr'),'launch_intent':identity(HERE/'launch-intent.json')})
    print(json.dumps({'state':'completed','exit_code':code}),flush=True)
    return code

if __name__=='__main__':raise SystemExit(main())
