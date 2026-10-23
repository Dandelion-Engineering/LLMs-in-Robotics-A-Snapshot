"""Exact prospective development snapshots; never freezes/adopts a campaign."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from common import HERE, REPO, MAP, C02, canonical, sha, save

def now():return datetime.now(timezone.utc).isoformat()
def mapcmd(*args):
    return subprocess.check_output([sys.executable,'-X','utf8','-B',str(MAP/'map.py'),*map(str,args)],text=True,encoding='utf-8')
def common(identity):return dict(schema_version='architecture-map-1.0',id=identity,recorded_at=now(),author='Codex session 25',tags=['campaign-003','development-only','no-model'],details={})
def ref(path,label,access='operator'):
    path=Path(path)
    return dict(label=label,uri=str(path.relative_to(MAP)) if path.is_relative_to(MAP) else str(path),sha256=sha(path),state='available',access=access,locator=None)
def state(path,label):return dict(state='recorded',refs=[ref(path,label)],reason=None)
def absent(reason):return dict(state='none',refs=[],reason=reason)
def append(kind,record,path):
    save(path,record)
    status=json.loads(mapcmd('status','--json'))
    print(mapcmd('append',kind,'--input',path,'--expected-sha256',status['store_sha256']),flush=True)

def prepare(identity,description,argv):
    folder=MAP/'releases/RCI001-C03-dev'/identity;folder.mkdir(parents=True,exist_ok=False)
    source={}
    paths=list(HERE.glob('*.py'))+list(HERE.glob('*.md'))
    for area in ('template','vendor','protocol'):
        paths.extend(p for p in (HERE/area).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
    paths.extend(HERE/'runtime-revision-001'/name for name in ('runtime-envelope.json','freeze-receipt.json','additional-authorization.json'))
    for p in sorted(set(paths)):
        source[p.relative_to(REPO).as_posix()]=dict(sha256=sha(p),bytes=p.stat().st_size)
    inherited=json.loads((MAP/'releases/RCI001-C02-dev-114/snapshot.json').read_text(encoding='utf-8'))['sources']
    for name,value in inherited.items():
        if sha(REPO/name)!=value['sha256']:raise ValueError('Changed inherited source '+name)
    with zipfile.ZipFile(folder/'source.zip','x',zipfile.ZIP_DEFLATED) as archive:
        for name in source:archive.write(REPO/name,name)
    save(folder/'snapshot.json',dict(schema='campaign003-development-snapshot-1',source=source,
        inherited=inherited,base_snapshot_sha256=sha(MAP/'releases/RCI001-C02-dev-114/snapshot.json')))
    save(folder/'manifest.json',dict(run_id=identity+'-attempt',revision_id=identity,description=description,
        actual_model_invocations=0,stage='development',command=argv,created_at=now(),
        source_snapshot_sha256=sha(folder/'snapshot.json'),final_campaign_authorized=False))
    revision={**common(identity),'architecture_id':'RCI001','parent_revision_id':'RCI001-C02-dev-114','status':'implemented',
        'title':'Campaign 003 no-model development: '+description,
        'summary':'Prospective apparatus qualification only; no model, pilot, scored result or final campaign freeze.',
        'mechanism':(HERE/'CONTRACT.md').read_text(encoding='utf-8'),
        'attachments':[ref(folder/'source.zip','Exact new development sources'),ref(folder/'snapshot.json','Exact new and inherited identities'),ref(folder/'manifest.json','Pre-run deterministic attempt')]}
    append('revision',revision,folder/'revision-record.json')
    run={**common(identity+'-attempt'),'revision_id':identity,'stage':'development','condition_id':'deterministic-no-model',
        'protocol_id':'Campaign003-candidate-development','scenario_id':description,'paired_block_id':'unpaired-mechanical-check',
        'replicate':1,'started_at':None,'rerun_of_run_id':None,'condition_details':{'model_calls':0,'command':argv},
        'seeds':absent('Deterministic fixture; any fixed scene seeds are source-bound, not sampled model runs.'),
        'frozen_refs':{'code':state(folder/'snapshot.json','Development sources'),
                       'environment':dict(state='unknown',refs=[],reason='Measured environment is retained in execution evidence.'),
                       'models':absent('No model process or inference is invoked.'),
                       'protocol':state(folder/'manifest.json','Deterministic check contract'),
                       'scenario':state(folder/'manifest.json','Mechanical scenario')},
        'evidence':[ref(folder/'manifest.json','Attempt declaration')]}
    append('run',run,folder/'run-record.json')
    mapcmd('build');mapcmd('validate','--output','validation.json')
    print(json.dumps({'prepared':identity,'manifest':str(folder/'manifest.json')}),flush=True)

def result(identity,job_id,receipt):
    folder=MAP/'releases/RCI001-C03-dev'/identity
    from common import QUEUE
    job=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',job_id],text=True,encoding='utf-8'))
    if job['state'] not in ('succeeded','failed','cancelled'):raise ValueError('No terminal queue outcome')
    save(folder/'official-status.json',job)
    evidence=[ref(folder/'official-status.json','Official shared queue state')]
    observed=None
    if receipt and Path(receipt).is_file():
        observed=json.loads(Path(receipt).read_text(encoding='utf-8'));evidence.append(ref(Path(receipt).resolve(),'Mechanical receipt'))
    passed=(job['state']=='succeeded' and type(job['exit_status']) is int and job['exit_status']==0 and observed is not None and observed.get('passed') is True)
    record={**common(identity+'-result'),'run_id':identity+'-attempt','supersedes_result_id':None,
            'execution_status':'completed' if job['state']=='succeeded' else 'failed',
            'validity':'valid' if passed else 'invalid','validity_reason':'Authenticated deterministic qualification passed.' if passed else 'Development qualification failed or remains unqualified; retain diagnostic evidence.',
            'outcome':'success' if passed else 'unknown','ended_at':job['ended_at'],
            'termination_reason':'deterministic_qualification_complete' if passed else 'development_failure',
            'metrics':[],'evidence':evidence}
    record['details']={'scope':'Apparatus mechanical check only, not Robot-Codex performance','job_id':job_id,'qualification_passed':passed}
    append('result',record,folder/'result-record.json');mapcmd('build');mapcmd('validate','--output','validation.json')
    print(json.dumps({'recorded':identity,'passed':passed}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='action',required=True)
    q=s.add_parser('prepare');q.add_argument('id');q.add_argument('description');q.add_argument('argv',nargs=argparse.REMAINDER)
    q=s.add_parser('result');q.add_argument('id');q.add_argument('job');q.add_argument('receipt')
    a=p.parse_args();prepare(a.id,a.description,a.argv) if a.action=='prepare' else result(a.id,a.job,a.receipt)
