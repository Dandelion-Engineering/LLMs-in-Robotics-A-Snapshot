"""Guarded additive map registration for Campaign 002 qualification and scoring."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent
RCI=HERE.parent
REPO=RCI.parents[1]
MAP=RCI.parent/'Architecture Map'
spec=importlib.util.spec_from_file_location('c02_prior_registry',RCI/'readiness-session-10/registration/register.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
am=prior.am

def now(): return datetime.now(timezone.utc).isoformat()

def common(identifier):
    return {'schema_version':am.SCHEMA,'id':identifier,'recorded_at':now(),
            'author':'Codex session 14','tags':['robot-codex-integration-001','campaign-002'], 'details':{}}

prior.common=common

def append(kind, record):
    data,raw,errors=am.read_store(MAP)
    if errors: raise ValueError(errors)
    am.append_record(MAP,kind,record,am.store_digest(raw))

def freeze(manifest, revision):
    value=json.loads(manifest.read_text(encoding='utf-8'))
    if value.get('framework_revision')!=revision: raise ValueError('Manifest revision mismatch')
    # Capture the entire unchanged 624-source dependency set plus additive harness.
    return prior.prepare(SimpleNamespace(map_root=MAP,revision=revision,run_id=value['run_id'],
        manifest=manifest,mechanism=HERE/'PLAN.md',expected_sha256=None))

def add_run(manifest, revision, stage='development', certificate=None):
    value=json.loads(manifest.read_text(encoding='utf-8'))
    run_id=value['run_id']; directory=MAP/'releases'/revision
    snapshot=directory/'snapshot.json'; code=directory/'code.zip'
    source_revision=json.loads(snapshot.read_text(encoding='utf-8'))['revision']
    if value.get('framework_revision')!=source_revision: raise ValueError('Manifest source revision mismatch')
    manifest_ref=prior.reference(MAP,'Immutable attempt manifest',manifest,'evaluator_only')
    record={**common(run_id),'revision_id':revision,'stage':stage,
       'condition_id':value.get('qualification_stage','known-fixture-repeatability'),
       'protocol_id':'RCI001-Campaign002-v1','scenario_id':value.get('family','two-fixture-harness'),
       'paired_block_id':'unpaired-'+run_id,'replicate':value.get('replicate',1),'started_at':None,
       'rerun_of_run_id':value.get('rerun_of_run_id'),
       'condition_details':{'manifest':value,'manifest_sha256':prior.digest(manifest.read_bytes())},
       'seeds':prior.recorded(manifest_ref),
       'frozen_refs':{k:prior.recorded(ref) for k,ref in {
           'code':prior.reference(MAP,'Frozen source archive',code),
           'environment':prior.reference(MAP,'Exact source/environment snapshot',snapshot),
           'models':prior.reference(MAP,'Exact requested model',snapshot),
           'protocol':prior.reference(MAP,'Prospective plan',HERE/'PLAN.md'),
           'scenario':manifest_ref}.items()},'evidence':[manifest_ref]}
    if certificate: record['details']['certificate_sha256']=prior.digest(Path(certificate).read_bytes())
    target=directory/'runs'/(run_id+'.json');target.parent.mkdir(exist_ok=True)
    prior.write_new(target,record);append('run',record)
    return {'run_id':run_id,'record':str(target)}

def finish(run_id, result, queue, validity, outcome, reason, execution='completed'):
    return prior.finish(SimpleNamespace(map_root=MAP,run_id=run_id,result=result,queue_receipt=queue,
        validity=validity,outcome=outcome,reason=reason,execution_status=execution,
        termination=reason,evidence=[],expected_sha256=None))

def release(certificate_path,certificate_sha256):
    # The certificate precedes map registration; registration cannot self-admit.
    spec=importlib.util.spec_from_file_location('c02_release_admission',HERE/'admission.py')
    admission=importlib.util.module_from_spec(spec);spec.loader.exec_module(admission)
    cert=admission.verify_certificate(certificate_path,certificate_sha256)
    revision=cert['release_revision'];directory=MAP/'releases'/revision
    directory.mkdir(parents=True,exist_ok=False)
    source=cert['artifacts']['source_snapshot']['path'];archive=cert['artifacts']['source_archive']['path']
    shutil.copyfile(source,directory/'snapshot.json');shutil.copyfile(archive,directory/'code.zip')
    shutil.copyfile(certificate_path,directory/'admission-certificate.json')
    code_ref=prior.reference(MAP,'Exact qualified repaired framework bytes',directory/'code.zip')
    snap_ref=prior.reference(MAP,'Qualified source and environment identities',directory/'snapshot.json')
    cert_ref=prior.reference(MAP,'Prospective scientific admission',directory/'admission-certificate.json')
    record={**common(revision),'architecture_id':'RCI001','parent_revision_id':cert['source_revision'],
        'status':'frozen','title':'Campaign 002 exact repaired Robot-Codex framework',
        'summary':'Infrastructure-only revocation and timing repairs; unchanged recovery behavior and known fixtures.',
        'mechanism':(HERE/'PLAN.md').read_text(encoding='utf-8'),
        'attachments':[code_ref,snap_ref,cert_ref,prior.reference(MAP,'Prospective plan',HERE/'PLAN.md')]}
    record['details']={'certificate_sha256':certificate_sha256,'source_revision':cert['source_revision'],
        'source_snapshot_sha256':cert['artifacts']['source_snapshot']['sha256'],
        'scope':'Twenty fresh known-fixture repeats; no held-out/general reliability or architecture comparison'}
    prior.write_new(directory/'revision-record.json',record);append('revision',record)
    attempts=[]
    for planned in cert['attempts']:
        row=add_run(Path(planned['manifest']['path']),revision,'evaluation',certificate_path)
        attempts.append({'run_id':planned['run_id'],'manifest_sha256':planned['manifest']['sha256'],
                         'run_record':identity(row['record'])})
    registration={'schema':'campaign002-registration-1','certificate_sha256':certificate_sha256,
       'release_revision':revision,'source_snapshot_sha256':cert['artifacts']['source_snapshot']['sha256'],
       'map_root':str(MAP),'release_snapshot':identity(directory/'snapshot.json'),
       'release_archive':identity(directory/'code.zip'),'release_record':identity(directory/'revision-record.json'),
       'attempts':attempts}
    prior.write_new(directory/'registration.json',registration);prior.refresh(MAP)
    return registration

def identity(path):
    return {'path':str(Path(path).resolve()),'sha256':prior.digest(Path(path).read_bytes())}

if __name__=='__main__':
    p=argparse.ArgumentParser();subs=p.add_subparsers(dest='action',required=True)
    for name in ('freeze','add-run'):
        s=subs.add_parser(name);s.add_argument('--manifest',type=Path,required=True);s.add_argument('--revision',required=True)
    s=subs.add_parser('finish');s.add_argument('--run-id',required=True);s.add_argument('--result',type=Path,required=True)
    s.add_argument('--queue-receipt',type=Path);s.add_argument('--validity',required=True);s.add_argument('--outcome',required=True)
    s.add_argument('--reason',required=True);s.add_argument('--execution',default='completed')
    s=subs.add_parser('release');s.add_argument('--certificate',type=Path,required=True);s.add_argument('--certificate-sha256',required=True)
    a=p.parse_args()
    if a.action=='freeze':v=freeze(a.manifest,a.revision)
    elif a.action=='add-run':v=add_run(a.manifest,a.revision)
    elif a.action=='finish':v=finish(a.run_id,a.result,a.queue_receipt,a.validity,a.outcome,a.reason,a.execution)
    else:v=release(a.certificate,a.certificate_sha256)
    print(json.dumps(v,indent=2))
