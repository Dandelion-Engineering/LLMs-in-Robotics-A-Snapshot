"""Prospective live attempts and immutable results, separate from development."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from common import HERE, REPO, MAP, QUEUE, canonical, sha, save
from register import mapcmd, append, ref, state
from scheduler import Schedule

CHAT='chats/Codex-Human/Robot-Codex Campaign 005/Robot-Codex Campaign 005 - Active.md'

def now():return datetime.now(timezone.utc).isoformat()
def fields(identity,stage):
    return dict(schema_version='architecture-map-1.0',id=identity,recorded_at=now(),
                author='Codex session 27',tags=['campaign-005',stage],details={})

def prepare(identity,stage,description,seed=173,noise_seed=34001,schedule_seed=340031,prerequisite_audit=None):
    if stage not in ('live_qualification','pilot'):raise ValueError('Final scoring uses a separately predeclared allocation')
    folder=MAP/'releases/RCI001-C05-live'/identity;folder.mkdir(parents=True,exist_ok=False)
    source={}
    paths=list(HERE.glob('*.py'))+list(HERE.glob('*.md'))
    for area in ('template','vendor','protocol'):
        paths += [p for p in (HERE/area).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
    paths += [HERE/'runtime-revision-001'/name for name in ('runtime-envelope.json','freeze-receipt.json','additional-authorization.json')]
    for p in sorted(set(paths)):source[p.relative_to(REPO).as_posix()]={'sha256':sha(p),'bytes':p.stat().st_size}
    inherited=json.loads((MAP/'releases/RCI001-C02-dev-114/snapshot.json').read_text(encoding='utf-8'))['sources']
    for name,value in inherited.items():
        if sha(REPO/name)!=value['sha256']:raise ValueError('Changed inherited source '+name)
    with zipfile.ZipFile(folder/'source.zip','x',zipfile.ZIP_DEFLATED) as archive:
        for name in source:archive.write(REPO/name,name)
    save(folder/'snapshot.json',dict(schema='campaign005-live-snapshot-1',source=source,inherited=inherited,
        base_snapshot_sha256=sha(MAP/'releases/RCI001-C02-dev-114/snapshot.json')))
    raw=(REPO/CHAT).read_bytes()
    if b'2026-10-03 17:44 PDT' not in raw or b'next phase all the way through completion of Campaign 005' not in raw:
        raise ValueError('Expected director authorization is absent')
    import hashlib
    authority={'path':CHAT,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
               'reference':'Randy, 2026-10-03 17:44 and 18:52 PDT, plus direct Codex reply approving 120 actions / 256 MiB core / 2 GiB host; recorded in additional-authorization.json'}
    save(folder/'authorization.json',authority)
    run_id=identity+'-attempt'
    output=HERE/'live-evidence'/run_id
    manifest=dict(stage=stage,run_id=run_id,revision_id=identity,description=description,created_at=now(),
        human_approval_reference=authority['reference'],authority=authority,
        source_snapshot_path='snapshot.json',source_snapshot_sha256=sha(folder/'snapshot.json'),
        encounter_limit=1 if stage=='live_qualification' else 3,
        model={'name':'gpt-6-astra','effort':'max','auth':'chatgpt','bootstrap':'Follow the instructions in RobotAgentPrompt.md.','fallback':False},
        apparatus_manifest=dict(run_id=run_id,seed=seed,noise_seed=noise_seed,schedule_seed=schedule_seed,encounters=3,
            initial_order=Schedule(schedule_seed).current,sim_cap_s=1000 if stage=='live_qualification' else 3000,
            wall_cap_s=1200 if stage=='live_qualification' else 3600,storage_cap_bytes=512*1024**2,mode='serve',stage=stage),
        output=str(output),no_replacement=True,scientific_prompt_unchanged=True)
    from runtime_limits import apply_limits,AUTHORITY,ENVELOPE
    manifest['apparatus_manifest']=apply_limits(manifest['apparatus_manifest'],stage)
    manifest['additional_budget_authority']={'path':str(AUTHORITY.relative_to(REPO)),'sha256':sha(AUTHORITY)}
    manifest['runtime_envelope']={'path':str(ENVELOPE.relative_to(REPO)),'sha256':sha(ENVELOPE)}
    if stage=='pilot':
        if prerequisite_audit is None:raise ValueError('Pilot requires the independent live infrastructure audit')
        audit=Path(prerequisite_audit).resolve();value=json.loads(audit.read_text())
        job=audit.parent.parent/'official-status.json';official=json.loads(job.read_text())
        if not (value['passed'] and value['qualification_complete'] and value['measurements']['actual_image_deliveries']>0
                and official['state']=='succeeded' and type(official['exit_status']) is int and official['exit_status']==0):
            raise ValueError('Full live qualification audit including handback must pass with succeeded/int0 before the pilot')
        manifest['prerequisite_audit']={'path':str(audit),'sha256':sha(audit),'official_status_path':str(job),'official_status_sha256':sha(job),
            'positive_terminal_branch_pending':not value['qualification_complete']}
    save(folder/'manifest.json',manifest)
    revision={**fields(identity,stage),'architecture_id':'RCI001','parent_revision_id':'RCI001-C05-pilot-001','status':'implemented',
        'title':'Campaign 005 '+stage+': '+description,'summary':'Authorized real-model apparatus evidence; not scored campaign evidence.',
        'mechanism':(HERE/'CONTRACT.md').read_text(encoding='utf-8')+'\n\n'+(HERE/'PHASE2.md').read_text(encoding='utf-8')+'\n\nProspective Session25 revision overrides only the approved time/count/evidence budgets: '+json.dumps(manifest['apparatus_manifest'])+'\nTime selection and separate approval: '+sha(ENVELOPE)+' / '+sha(AUTHORITY)+'. Historical review stops and 600-second limits above remain historical; new manifest controls this attempt. All remaining criteria and model-visible task content are unchanged.',
        'attachments':[ref(folder/'source.zip','Exact Campaign 005 sources'),ref(folder/'snapshot.json','New and inherited source identities'),
                       ref(folder/'manifest.json','Prospective live declaration'),ref(folder/'authorization.json','Human authorization prefix identity')]}
    append('revision',revision,folder/'revision-record.json')
    run={**fields(run_id,stage),'revision_id':identity,'stage':'calibration','condition_id':'fresh-conversation-persistent-filesystem',
        'protocol_id':'Campaign003-live-qualification-and-pilot','scenario_id':'C-placement-known-workcell',
        'paired_block_id':run_id,'replicate':1,'started_at':None,'rerun_of_run_id':None,
        'condition_details':{'stage':stage,'encounters':manifest['encounter_limit'],'not_scored':True,'description':description},
        'seeds':state(folder/'manifest.json','Protected seeds and schedule policy'),
        'frozen_refs':{role:state(folder/filename,label) for role,filename,label in (
            ('code','snapshot.json','Exact sources'),('environment','snapshot.json','Pinned inherited environment sources'),
            ('models','manifest.json','Fixed model effort and sole bootstrap'),('protocol','manifest.json','Prospective gates'),('scenario','manifest.json','Workcell seed and schedule'))},
        'evidence':[ref(folder/'manifest.json','Pre-run declaration')]}
    append('run',run,folder/'run-record.json');mapcmd('build');mapcmd('validate','--output','validation.json')
    print(json.dumps({'prepared':identity,'manifest':str(folder/'manifest.json'),'output':str(output)}),flush=True)

def record(identity,job_id):
    folder=MAP/'releases/RCI001-C05-live'/identity
    manifest=json.loads((folder/'manifest.json').read_text())
    job=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',job_id],text=True,encoding='utf-8'))
    if job['state'] not in ('succeeded','failed','cancelled'):raise ValueError('Queue attempt has no terminal state')
    save(folder/'official-status.json',job)
    receipt_path=Path(manifest['output'])/'receipt.json'
    observed=json.loads(receipt_path.read_text()) if receipt_path.is_file() else None
    if observed is not None:save(folder/'receipt.json',observed)
    valid=bool(job['state']=='succeeded' and type(job['exit_status']) is int and job['exit_status']==0 and observed and observed.get('infrastructure_valid'))
    passed=bool(valid and observed.get('passed'))
    record={**fields(identity+'-result',manifest['stage']),'run_id':manifest['run_id'],'supersedes_result_id':None,
        'execution_status':'completed' if job['state']=='succeeded' else 'failed','validity':'valid' if valid else 'invalid',
        'validity_reason':'Coordinator infrastructure checks passed; separate independent qualification audit required.' if valid else 'Live qualification infrastructure failed or remains unqualified; all captured evidence retained.',
        'outcome':('success' if passed else 'failure') if valid else 'unknown','ended_at':job['ended_at'],
        'termination_reason':'bounded_live_sequence_complete' if passed else 'task_failure' if valid else 'infrastructure_failure',
        'metrics':[],'evidence':[ref(folder/'official-status.json','Authenticated queue state')]+([ref(folder/'receipt.json','Retained coordinator receipt')] if observed else [])}
    record['details']={'job_id':job_id,'not_scored':True,'independent_audit_required':True,'local_evidence':manifest['output']}
    append('result',record,folder/'result-record.json');mapcmd('build');mapcmd('validate','--output','validation.json')
    print(json.dumps({'recorded':identity,'valid':valid,'passed':passed}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('prepare');a.add_argument('id');a.add_argument('stage');a.add_argument('description')
    a.add_argument('--seed',type=int,default=173);a.add_argument('--noise-seed',type=int,default=34001);a.add_argument('--schedule-seed',type=int,default=340031)
    a.add_argument('--prerequisite-audit')
    a=sub.add_parser('result');a.add_argument('id');a.add_argument('job')
    a=p.parse_args()
    if a.action=='prepare':prepare(a.id,a.stage,a.description,a.seed,a.noise_seed,a.schedule_seed,a.prerequisite_audit)
    else:record(a.id,a.job)
