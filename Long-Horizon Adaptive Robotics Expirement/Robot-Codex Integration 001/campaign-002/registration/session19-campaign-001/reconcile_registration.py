"""Complete rejected Map metadata with exact internal copies, preserving the seal."""
from datetime import datetime,timezone
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import control as base

HERE=Path(__file__).resolve().parent
OUT=HERE/'registration-reconciliation-001'
PLAN=base.C/'PLAN.md'
FIXED=base.RELEASE/'revision-record-reconciled.json'

def sources():
    return [base.identity(p) for p in [Path(__file__),HERE/'control.py',HERE/'RECONCILIATION.md',
        base.C/'registry.py',base.C/'registry_session19.py',base.C/'admission.py',base.CERT,PLAN]]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['submit','run']);args=parser.parse_args()
    if args.action=='submit':
        assert not OUT.exists() and not base.REG.exists() and not FIXED.exists()
        base.save(HERE/'reconciliation-intent.json',{'sources':sources(),'created_at':datetime.now(timezone.utc).isoformat()})
        job=json.loads(subprocess.check_output(base.py(base.QUEUE,'submit','--project','LLMs-in-Robotics','--cwd',base.REPO,'--',*base.py(Path(__file__).resolve(),'run')),text=True,encoding='utf-8'))
        base.save(HERE/'reconciliation-submit.json',job);print(json.dumps({'job_id':job['id'],'state':job['state']}));return
    assert base.read(HERE/'reconciliation-intent.json')['sources']==sources()
    assert not OUT.exists() and not base.REG.exists() and not FIXED.exists()
    failed=json.loads(subprocess.check_output(base.py(base.QUEUE,'status','20260930T213516694391Z-f3e7ae9c'),text=True,encoding='utf-8'))
    assert failed['state']=='failed' and type(failed['exit_status'])is int and failed['exit_status']==1
    base.successful('20260930T213232853263Z-51ed84f8')
    admission=load('reconciled_admission',base.C/'admission.py')
    cert=admission.verify_certificate(base.CERT,base.DIGEST)
    registry=load('original_metadata_schema',base.C/'registry.py')
    data,raw,errors=registry.am.read_store(base.MAP)
    assert not errors
    ids={x['id'] for kind in ['revision','run'] for x in data[kind]}
    assert cert['release_revision'] not in ids and all(a['run_id'] not in ids for a in cert['attempts'])
    assert all(not (base.C/'execution'/a['run_id']).exists() and not any(Path(a[k]).exists() for k in ['workspace','evidence','host_evidence']) for a in cert['attempts'])
    before=[base.identity(base.RELEASE/n) for n in ['snapshot.json','code.zip','admission-certificate.json','revision-record.json']]
    assert before[0]['sha256']==cert['artifacts']['source_snapshot']['sha256']
    assert before[1]['sha256']==cert['artifacts']['source_archive']['sha256']
    assert before[2]['sha256']==base.DIGEST
    OUT.mkdir()
    base.save(OUT/'before.json',{'failed_job':failed,'preserved_release_files':before,'map_store_sha256':registry.am.store_digest(raw),
        'release_and_twenty_runs_absent':True,'scored_footprints_absent':True,'sources':sources()})
    copies=base.RELEASE/'map-local-inputs';copies.mkdir()
    copied=[]
    def retain(source,target,expected):
        assert base.identity(source)['sha256']==expected
        with target.open('xb') as f:f.write(Path(source).read_bytes())
        assert base.identity(target)['sha256']==expected
        copied.append({'source':base.identity(source),'retained':base.identity(target)})
        return target
    plan=retain(PLAN,copies/'PLAN.md',cert['artifacts']['protocol']['sha256'])
    original=base.read(base.RELEASE/'revision-record.json')
    corrected=copy.deepcopy(original)
    assert len(corrected['attachments'])==4 and corrected['attachments'][3]['sha256']==base.identity(plan)['sha256']
    corrected['attachments'][3]['uri']=plan.relative_to(base.MAP).as_posix()
    compare=copy.deepcopy(corrected);compare['attachments'][3]['uri']=original['attachments'][3]['uri'];assert compare==original
    base.save(FIXED,corrected)
    registry.append('revision',corrected)
    attempts=[]
    run_dir=base.RELEASE/'runs';run_dir.mkdir()
    for attempt in cert['attempts']:
        manifest=retain(attempt['manifest']['path'],copies/(attempt['run_id']+'.json'),attempt['manifest']['sha256'])
        value=base.read(manifest);run_id=attempt['run_id']
        manifest_ref=registry.prior.reference(base.MAP,'Immutable attempt manifest',manifest,'evaluator_only')
        record={**registry.common(run_id),'author':'Codex session 19','revision_id':cert['release_revision'],'stage':'evaluation',
            'condition_id':value.get('qualification_stage','known-fixture-repeatability'),'protocol_id':'RCI001-Campaign002-v1',
            'scenario_id':value.get('family','two-fixture-harness'),'paired_block_id':'unpaired-'+run_id,'replicate':value.get('replicate',1),
            'started_at':None,'rerun_of_run_id':value.get('rerun_of_run_id'),
            'condition_details':{'manifest':value,'manifest_sha256':attempt['manifest']['sha256']},
            'seeds':registry.prior.recorded(manifest_ref),
            'frozen_refs':{k:registry.prior.recorded(ref) for k,ref in {
                'code':registry.prior.reference(base.MAP,'Frozen source archive',base.RELEASE/'code.zip'),
                'environment':registry.prior.reference(base.MAP,'Exact source/environment snapshot',base.RELEASE/'snapshot.json'),
                'models':registry.prior.reference(base.MAP,'Exact requested model',base.RELEASE/'snapshot.json'),
                'protocol':registry.prior.reference(base.MAP,'Prospective plan',plan),'scenario':manifest_ref}.items()},
            'evidence':[manifest_ref],'details':{'certificate_sha256':base.DIGEST}}
        target=run_dir/(run_id+'.json');base.save(target,record);registry.append('run',record)
        attempts.append({'run_id':run_id,'manifest_sha256':attempt['manifest']['sha256'],'run_record':base.identity(target)})
    registration={'schema':'campaign002-registration-1','certificate_sha256':base.DIGEST,'release_revision':cert['release_revision'],
        'source_snapshot_sha256':cert['artifacts']['source_snapshot']['sha256'],'map_root':str(base.MAP),
        'release_snapshot':base.identity(base.RELEASE/'snapshot.json'),'release_archive':base.identity(base.RELEASE/'code.zip'),
        'release_record':base.identity(FIXED),'attempts':attempts}
    base.save(base.REG,registration)
    registry.prior.refresh(base.MAP)
    admission.verify_registration(base.REG,admission.verify_certificate(base.CERT,base.DIGEST),base.DIGEST)
    assert base.read(HERE/'reconciliation-intent.json')['sources']==sources()
    assert all(base.identity(x['path'])==x for x in before)
    base.save(OUT/'verified.json',{'registered':20,'registration':base.identity(base.REG),'certificate':base.identity(base.CERT),
        'copies':copied,'corrected_record':base.identity(FIXED),'preserved_release_files':before,'sources_unchanged':True,
        'original_failed_release_preserved':True,'existing_certificate_and_registration_verifiers_passed':True,
        'scored_started':False,'scope':'Map reference localization only; exact qualified sources and sealed twenty slots unchanged.'})
    print(json.dumps({'registered':20,'scored_started':False,'registration':base.identity(base.REG),'original_rejected_record_preserved':True}))

if __name__=='__main__':main()
