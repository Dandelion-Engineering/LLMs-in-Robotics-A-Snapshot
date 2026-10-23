"""Append exact development integration snapshots and outcomes to the existing map.

Does not launch work, grant evaluation authority, or edit historical records.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import zipfile

HERE = Path(__file__).resolve().parent
MAP = HERE.parent / 'Architecture Map'
spec = importlib.util.spec_from_file_location('integration_architecture_map', MAP/'map.py')
am = importlib.util.module_from_spec(spec)
spec.loader.exec_module(am)
AID = 'RCI001'

def now(): return datetime.now(timezone.utc).isoformat()
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x',encoding='utf-8') as f:
        json.dump(value,f,indent=2); f.write('\n')
def ref(label, path, access='operator'):
    path=Path(path).resolve()
    return {'label':label,'uri':Path(os.path.relpath(path,MAP)).as_posix(),
            'sha256':sha(path),'state':'available','access':access,'locator':None}
def state(reference): return {'state':'recorded','refs':[reference],'reason':None}
def none(reason): return {'state':'none','refs':[],'reason':reason}
def common(identifier):
    return {'schema_version':'architecture-map-1.0','id':identifier,'recorded_at':now(),
            'author':'Development Codex session 8','tags':['robot-codex-integration-001','development-only'], 'details':{}}
def append(kind, record):
    data,raw,errors=am.read_store(MAP)
    if errors: raise ValueError(errors)
    am.append_record(MAP,kind,record,am.store_digest(raw))
def rebuild():
    if am.main(['build']) or am.main(['validate','--output','validation.json']):
        raise ValueError('Map rebuild/validation failed')

def prepare(args):
    data,_,errors=am.read_store(MAP)
    if errors: raise ValueError(errors)
    manifests=[json.loads(p.read_text(encoding='utf-8')) for p in args.manifest]
    run_ids=[m['run_id'] for m in manifests]
    if len(run_ids)!=len(set(run_ids)): raise ValueError('Duplicate run IDs')
    known={row['id'] for rows in data.values() for row in rows}
    if any(r in known for r in [args.revision,*run_ids]): raise ValueError('Immutable IDs already registered')
    directory=MAP/'releases'/args.revision
    directory.mkdir(parents=True,exist_ok=False)
    sources=[]
    for folder in (['host'] if args.host_only else ['host','launch','runtime-template']):
        sources.extend(p for p in (HERE/folder).rglob('*') if p.is_file()
                       and not any(part in ('__pycache__','records','probes','local-evidence') for part in p.parts)
                       and p.suffix not in ['.pyc','.log'])
    sources.extend([HERE/'provenance.py',HERE/'register.py'])
    for p in (HERE.parent/'Runtime 004').glob('*.py'): sources.append(p)
    for p in (HERE.parent/'Storage Retention Implementation 001/future').glob('*.py'): sources.append(p)
    sources.extend([HERE.parent/'Runtime 004/vendor/panda/manifest.json',HERE.parents[1]/'requirements.txt'])
    source_map={str(p.relative_to(HERE.parent).as_posix()) if p.is_relative_to(HERE.parent)
                else '../'+p.name:sha(p) for p in sources}
    bundle=directory/'code.zip'
    with zipfile.ZipFile(bundle,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sources:
            arc=p.relative_to(HERE.parent).as_posix() if p.is_relative_to(HERE.parent) else 'project-'+p.name
            z.write(p,arc)
    snapshot={'revision':args.revision,'recorded_at':now(),'scope':'development integration; no scored comparisons',
              'sources':source_map,'python':platform.python_version(),'platform':platform.platform(),
              'dependencies':{n:importlib.metadata.version(n) for n in ['mujoco','numpy']},
              'model':args.model,'reasoning':'max' if args.model else None,'host_only':args.host_only,
              'manifests':manifests,'run_ids':run_ids}
    snapshot_path=directory/'snapshot.json'; write_new(snapshot_path,snapshot)
    if AID not in known:
        append('architecture',{**common(AID),'title':'On-demand filesystem-native Robot-Codex recovery',
            'summary':'Frozen conventional automation works normally; protected public-evidence monitor transfers exclusive authority to a fresh Astra Max filesystem agent for bounded recovery and independently checked handback.'})
    previous=[r for r in data['revision'] if r['architecture_id']==AID]
    append('revision',{**common(args.revision),'architecture_id':AID,
        'parent_revision_id':previous[-1]['id'] if previous else None,'status':'implemented',
        'title':'Robot-Codex development integration '+args.revision,
        'summary':'Exact implementation snapshot for bounded infrastructure/reference checks; readiness and physics outcomes remain unestablished until recorded.',
        'mechanism':'The host imports immutable Runtime 004 body, sensing, task controller and actuator protections. A separate owner-thread supervisor evolves physics during client latency, records public evidence independently, fences action identities/generations/task revisions, exposes a restricted interface, and checks handback. The intended fresh Robot-Codex reads its populated generic-derived filesystem using the fixed RobotAgentPrompt bootstrap; actual launch qualification is separate. Conventional and developer-reference modes qualify challenge mechanics without a model; their results are not Robot-Codex performance. A dedicated pinned per-program runner is not implemented; a shell with Python remains programmable if launched. No complete collision/contact safety or scored readiness is claimed.',
        'attachments':[ref('Exact source bundle',bundle),ref('Exact manifests and environment',snapshot_path)],
        'details':{'development_only':True,'frozen_baseline_unchanged':True,'model':args.model,
                   'scope':'Individual bounded integration conditions; no population effect, held-out comparison, or performance claim.'}})
    for source,manifest in zip(args.manifest,manifests):
        stored=directory/(manifest['run_id']+'.json'); write_new(stored,manifest)
        append('run',{**common(manifest['run_id']),'revision_id':args.revision,'stage':'development',
            'condition_id':manifest.get('mode','infrastructure'),'protocol_id':'RCI001-development-v1',
            'scenario_id':manifest.get('family',manifest.get('challenge','nominal')),'paired_block_id':'unpaired-'+manifest['run_id'],
            'replicate':1,'started_at':None,'rerun_of_run_id':manifest.get('rerun_of'),
            'condition_details':{'manifest':manifest,'scope':'Development-only infrastructure/reference evidence; not scored'},
            'seeds':state(ref('Protected development manifest',stored,'evaluator_only')),
            'frozen_refs':{'code':state(ref('Source bundle',bundle)),
                'environment':state(ref('Environment snapshot',snapshot_path)),
                'models':state(ref('Requested client/model configuration; actual use requires run receipt',snapshot_path)) if args.model else none('No model in conventional/reference infrastructure qualification'),
                'protocol':state(ref('Development manifest',stored)),
                'scenario':state(ref('Protected challenge configuration',stored,'evaluator_only'))},
            'evidence':[ref('Registered manifest',stored,'evaluator_only')]})
    rebuild()
    print(json.dumps({'revision':args.revision,'runs':run_ids,'snapshot':str(snapshot_path)},indent=2))

def finish(args):
    receipt=json.loads(args.queue_receipt.read_text(encoding='utf-8'))
    # Queue status may wrap its job record. Require actual success rather than a log string.
    job=receipt.get('job',receipt)
    if job.get('state')!='succeeded' or job.get('exit_status')!=0:
        raise ValueError('Queue output not eligible for normal result consumption')
    result=json.loads(args.result.read_text(encoding='utf-8'))
    result_ref=ref('Protected native development result',args.result,'evaluator_only')
    append('result',{**common(args.run_id+'-result'),'run_id':args.run_id,
        'supersedes_result_id':None,'execution_status':'completed','validity':args.validity,
        'validity_reason':args.reason,'outcome':args.outcome,'ended_at':result.get('ended_at',now()),
        'termination_reason':result.get('termination_reason',result.get('terminal','Bounded development fixture ended; see result')),
        'metrics':[],'evidence':[result_ref,ref('Successful shared queue receipt',args.queue_receipt)],
        'details':{'source_result':result,'scope':'No comparative/general performance inference'}})
    rebuild()

if __name__=='__main__':
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare'); a.add_argument('--revision',required=True); a.add_argument('--manifest',type=Path,nargs='+',required=True); a.add_argument('--model'); a.add_argument('--host-only',action='store_true')
    b=sub.add_parser('finish'); b.add_argument('--run-id',required=True); b.add_argument('--result',type=Path,required=True); b.add_argument('--queue-receipt',type=Path,required=True)
    b.add_argument('--outcome',choices=['success','partial','failure','unknown','not_assessed'],required=True); b.add_argument('--validity',choices=['valid','invalid','unknown'],required=True); b.add_argument('--reason',required=True)
    args=p.parse_args(); prepare(args) if args.command=='prepare' else finish(args)
