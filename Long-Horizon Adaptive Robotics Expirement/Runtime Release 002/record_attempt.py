"""Immutable development registration before execution; terminal result after it."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import platform
import zipfile

HERE=Path(__file__).resolve().parent
from development_storage import location as development_location, registered_location, safe_run_id
MAP=HERE.parent/'Architecture Map'
spec=importlib.util.spec_from_file_location('architecture_map',MAP/'map.py')
am=importlib.util.module_from_spec(spec);spec.loader.exec_module(am)

def now():return datetime.now(timezone.utc).isoformat()
def ref(label,path,locator=None):
    path=Path(path).resolve()
    import os
    try:uri=Path(os.path.relpath(path,MAP)).as_posix()
    except ValueError:uri=path.as_posix()  # Local absolute path when Windows drives differ.
    return {'label':label,'uri':uri,'sha256':hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None,'state':'available' if path.exists() else 'missing','access':'operator','locator':locator}
def common(rid,tags):return {'schema_version':'architecture-map-1.0','id':rid,'recorded_at':now(),'author':'Codex session 4','tags':tags,'details':{}}
def append(kind,record):
    data,raw,errors=am.read_store(MAP)
    if errors:raise ValueError(errors)
    if any(r['id']==record['id'] for r in data[kind]):raise ValueError('Immutable record already exists: '+record['id'])
    am.append_record(MAP,kind,record,am.store_digest(raw))
def state(reference):return {'state':'recorded','refs':[reference],'reason':None}
def none(reason):return {'state':'none','refs':[],'reason':reason}

def prepare(args):
    run_id=safe_run_id(args.run_id);aid='B01-C0' if args.kind=='baseline' else 'B01-'+args.kind
    storage=development_location(run_id,getattr(args,'development_raw_root',None),require_fresh=True)
    qualification_path=getattr(args,'development_restart_freeze',None)
    qualification_input=None
    if qualification_path is not None:
        from restart_calibration_loader import load_restart_qualification
        qualification_path=Path(qualification_path).resolve()
        qualification_bytes=qualification_path.read_bytes()
        qualification=load_restart_qualification(json.loads(qualification_bytes),qualification_path)
        if qualification is None:raise ValueError('Development qualification must explicitly select qualified_class mode')
        qualification_input={'path':str(qualification_path),'sha256':hashlib.sha256(qualification_bytes).hexdigest(),
                             'verified_identity':qualification.as_dict()['identity']}
    data,raw,errors=am.read_store(MAP)
    if errors:raise ValueError(errors)
    if not any(a['id']==aid for a in data['architecture']):
        append('architecture',{**common(aid,['batch-01','conventional-baseline','continuity']),'title':'Durable Conventional Sequencer','summary':'Fixed job eligibility/recovery rules, durable observed transactions and the same public sensing and physical execution services. No language model.'})
    rid=run_id+'-revision';snapshot=MAP/'releases'/run_id;snapshot.mkdir(parents=True,exist_ok=False)
    bundle=snapshot/'runtime.zip'
    with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(HERE.glob('*.py')):archive.write(path,path.name)
    project=HERE.parents[1]
    manifest={'scope':'immutable implemented development snapshot; not scored-ready','run_id':run_id,'kind':args.kind,'runtime_files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.glob('*.py'))},'python':platform.python_version(),'platform':platform.platform(),'dependencies':{name:importlib.metadata.version(name) for name in ('mujoco','numpy')},'requirements':(project/'requirements.txt').read_text(),'panda':json.loads((HERE/'vendor/panda/manifest.json').read_text()),'model':None if args.kind=='baseline' else json.loads((HERE/'vendor/model/asset_manifest.json').read_text()),'condition':args.condition,'scenario':args.scenario,'part_count':args.parts,'world_seed':args.seed,'policy_noise_seed':args.policy_noise_seed,'cap_s':args.cap,'timing_track':'actual_host','readiness':'development only; calibration incomplete'}
    manifest['development_storage']=storage
    manifest['development_restart_qualification']=qualification_input
    manifest_path=snapshot/'manifest.json';manifest_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    prior=[r for r in data['revision'] if r['architecture_id']==aid]
    mechanism='Public image-derived tagged positions and device I/O feed candidate reconciliation. '
    mechanism+= {'baseline':'A fixed durable sequencer selects eligible tending operations.','A1':'An actual local LLM selects each next typed task.','A2':'An actual local LLM generates a finite guarded procedure interpreted between calls.','A3':'A durable conventional scheduler selects operations and an actual local LLM supplies transport clearance, speed and avoidance objectives.'}[args.kind]
    mechanism+=' Shared IK, quintic joint trajectories and contact-based Panda grasping execute motions. Candidate code runs inside WSL bubblewrap through JSON IPC. World/evaluator and local model gateway remain outside. Every consequential action is durably recorded and current observations reconcile outcomes. These implementations are under calibration; sensor/trajectory/isolation unit checks do not establish full readiness or comparative benefit.'
    append('revision',{**common(rid,['batch-01','development','implemented','continuity']),'architecture_id':aid,'parent_revision_id':prior[-1]['id'] if prior else None,'status':'implemented','title':args.kind+' development snapshot '+run_id,'summary':'Exact source and resource snapshot registered before this development attempt.','mechanism':mechanism,'attachments':[ref('Executable source snapshot',bundle),ref('Exact environment and attempt configuration',manifest_path)],'details':{'batch_id':'B01','role':'comparator' if args.kind=='baseline' else 'main_candidate','implementation_status':'Implemented development candidate; physical workcell readiness incomplete','limitations':['Not frozen evaluation','No full physical task completion claimed before attempt','Current source bundle is authoritative over intended proposed-design features']}})
    append('run',{**common(run_id,['batch-01','development',args.kind]),'revision_id':rid,'stage':'development','condition_id':args.condition,'protocol_id':'B01-development-physical-v1','scenario_id':f'dev-{args.scenario}-n{args.parts}-s{args.seed}','paired_block_id':f'dev-{args.scenario}-n{args.parts}-s{args.seed}','replicate':1,'started_at':None,'rerun_of_run_id':None,'condition_details':{'kind':args.kind,'part_count':args.parts,'cap_s':args.cap,'timing_track':'actual_host','controls':'development attempt; no scored comparison','planned_command':['experiment.py','--kind',args.kind,'--parts',str(args.parts),'--seed',str(args.seed),'--policy-noise-seed',str(args.policy_noise_seed),'--cap',str(args.cap),'--scenario',args.scenario,'--condition',args.condition,'--run-id',run_id,'--development-raw-root',storage['raw_root']]+(['--development-restart-freeze',str(qualification_path)] if qualification_path else [])},'seeds':state(ref('Development world seed',manifest_path,'world_seed')),'frozen_refs':{'code':state(ref('Executable snapshot',bundle)),'environment':state(ref('Dependency and Panda asset identity',manifest_path)),'models':none('Conventional baseline has no model') if args.kind=='baseline' else state(ref('Model and inference artifact identity',manifest_path,'model')),'protocol':state(ref('Development configuration and limits',manifest_path)),'scenario':state(ref('Development scenario',manifest_path))},'evidence':[ref('Pre-run snapshot',manifest_path)]})
    am.main(['build']);am.main(['validate','--output','validation.json'])
    print('Registered before execution:',run_id)

def registered_storage(run_id):
    """Resolve the location only through the immutable registered development manifest."""
    safe_run_id(run_id)
    data,_,errors=am.read_store(MAP)
    if errors:raise ValueError(errors)
    runs=[row for row in data['run'] if row['id']==run_id]
    if len(runs)!=1 or runs[0].get('stage')!='development':
        raise ValueError('Finish requires one registered development run')
    source=(MAP/'releases'/run_id/'manifest.json').resolve()
    if not source.is_relative_to(MAP.resolve()):raise ValueError('Registration manifest escaped map')
    payload=source.read_bytes();digest=hashlib.sha256(payload).hexdigest()
    references=runs[0].get('frozen_refs',{}).get('protocol',{}).get('refs',[])
    matching=[item for item in references if isinstance(item.get('uri'),str)
              and (MAP/item['uri']).resolve()==source and item.get('sha256')==digest
              and item.get('state')=='available']
    if len(matching)!=1:raise ValueError('Registration manifest lacks an exact immutable map binding')
    manifest=json.loads(payload)
    if manifest.get('run_id')!=run_id:raise ValueError('Registration manifest run identity mismatch')
    legacy='development_storage' not in manifest
    if not legacy and manifest['development_storage'] is None:
        raise ValueError('Registered development location cannot be null')
    storage=registered_location(run_id,manifest.get('development_storage'))
    return storage,legacy,{'path':str(source),'sha256':digest,'bytes':len(payload)}


def verify_raw_identity(value,run_id,storage,legacy):
    if not isinstance(value,dict) or value.get('run_id')!=run_id:
        raise ValueError('Raw development run identity mismatch')
    if value.get('stage')!='development' and not (legacy and value.get('stage') is None):
        raise ValueError('Raw evidence does not identify the registered development stage')
    if not legacy and value.get('development_storage')!=storage:
        raise ValueError('Raw development evidence location differs from registration')


def finish(args):
    storage,legacy,registration=registered_storage(args.run_id)
    raw=Path(storage['evidence_dir'])
    source=raw/'result.json';d=json.loads(source.read_text(encoding='utf-8'))
    verify_raw_identity(d,args.run_id,storage,legacy)
    if (raw/'manifest.json').is_file():
        verify_raw_identity(json.loads((raw/'manifest.json').read_text(encoding='utf-8')),args.run_id,storage,legacy)
    evidence_ref=ref('Actual protected development result',source)
    metrics=[]
    for name,key,unit in [('accepted_parts','accepted_count','count'),('completion_time','completion_time_s','s'),('duration','wall_duration_s','s'),('model_calls','model_calls','count'),('false_completion_claims','false_done_assertions','count'),('end_effector_path','motion_path_m','m')]:
        value=(d.get('independent_outcome') or {}).get(key) if key=='accepted_count' else d.get(key)
        metrics.append({'name':name,'value':value,'unit':unit,'denominator':None,'denominator_description':'Single development attempt; not a population estimate','missing_reason':'Not measured or task did not complete; inspect terminal result' if value is None else None,'evidence':[evidence_ref] if value is not None else []})
    append('result',{**common(args.run_id+'-result',['batch-01','development']),'run_id':args.run_id,'supersedes_result_id':None,'execution_status':d['execution_status'],'validity':d.get('validity','unknown'),'validity_reason':d.get('validity_reason','Development readiness incomplete'),'outcome':d['outcome'],'ended_at':d['ended_at'],'termination_reason':d['termination_reason'],'metrics':metrics,'evidence':[evidence_ref,ref('Actual event stream',raw/'events.jsonl'),ref('Actual motion samples',raw/'motion.jsonl')],'details':{'scope':'Development only; no comparative inference','queue_job_id':args.queue_job_id,'development_storage':storage,'registration_manifest':registration,'legacy_missing_raw_stage':legacy and d.get('stage') is None,'limitations':d.get('limits',[]),'timing':{k:v for k,v in d.items() if 'lag' in k or 'timing' in k},'failed_attempt_retained':d['outcome']!='success'}})
    am.main(['build']);am.main(['validate','--output','validation.json'])

if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='command',required=True)
    prep=s.add_parser('prepare');prep.add_argument('--kind',choices=['baseline','A1','A2','A3'],required=True);prep.add_argument('--run-id',required=True);prep.add_argument('--parts',type=int,default=3);prep.add_argument('--seed',type=int,default=0);prep.add_argument('--policy-noise-seed',type=int,default=0);prep.add_argument('--cap',type=float,default=300);prep.add_argument('--scenario',default='nominal');prep.add_argument('--condition',default='persistent');prep.add_argument('--development-restart-freeze',type=Path);prep.add_argument('--development-raw-root',type=Path)
    fin=s.add_parser('finish');fin.add_argument('--run-id',required=True);fin.add_argument('--queue-job-id',required=True)
    a=p.parse_args();prepare(a) if a.command=='prepare' else finish(a)
