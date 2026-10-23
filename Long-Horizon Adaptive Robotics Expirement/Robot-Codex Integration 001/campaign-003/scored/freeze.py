"""Operator-only scored declaration, admitted only after the complete pilot audit."""
import argparse
import copy
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import shutil
import sys
import zipfile

AREA=Path(__file__).resolve().parent
sys.path.insert(0,str(AREA.parent))
from common import HERE,REPO,MAP,sha,save
from register import append,mapcmd,ref,state
from runtime_limits import apply_limits
from scheduler import Schedule


def now():return datetime.now(timezone.utc).isoformat()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def fields(identity):
    return dict(schema_version='architecture-map-1.0',id=identity,recorded_at=now(),
        author='Codex session 25',tags=['campaign-003','scored','frozen-allocation'],details={})


def validate_allocation(allocation):
    assert allocation['schema']=='campaign003-scored-allocation-1'
    assert allocation['encounters_per_block']==3 and type(allocation['encounters_per_block']) is int
    assert allocation['no_replacements'] is True
    assert allocation['task_failure_policy']=='stop_this_block_continue_next_independent_block'
    assert allocation['infrastructure_failure_policy']=='stop_campaign_remaining_slots_not_run'
    assert allocation['capacity_failure_policy']=='stop_admission_preserve_evidence_no_reserve_relaxation'
    assert allocation['independent_unit']=='persistent_block'
    blocks=allocation['blocks'];assert len(blocks)>=2
    assert len({b['id'] for b in blocks})==len(blocks)
    assert len({b['noise_seed'] for b in blocks})==len(blocks)
    assert len({b['schedule_seed'] for b in blocks})==len(blocks)
    for block in blocks:
        assert re.fullmatch(r'[A-Za-z0-9_-]+',block['id'])
        for key in ('seed','noise_seed','schedule_seed'):assert type(block[key]) is int
    assert allocation['rationale'] and allocation['runtime_storage_basis']


def freeze(identity,allocation_path,pilot_root):
    assert re.fullmatch(r'[A-Za-z0-9_-]+',identity)
    allocation_path=Path(allocation_path).resolve();pilot_root=Path(pilot_root).resolve()
    allocation=read(allocation_path);validate_allocation(allocation)
    audit=read(pilot_root/'assessment/receipt.json');official=read(pilot_root/'official-status.json')
    assert official['state']=='succeeded' and type(official['exit_status']) is int and official['exit_status']==0
    assert audit['passed'] and audit['qualification_complete']
    assert audit['measurements']['declared_encounters']==audit['measurements']['attempted_encounters']==audit['measurements']['terminal_appends']==3
    pilot_manifest_path=Path(read(pilot_root/'declaration.json')['source_manifest'])
    pilot=read(pilot_manifest_path)
    assert pilot['stage']=='pilot' and sha(pilot_manifest_path)==audit['source_manifest_sha256']
    assert allocation['pilot_audit_sha256']==sha(pilot_root/'assessment/receipt.json')
    pilot_sources=read(pilot_manifest_path.parent/pilot['source_snapshot_path'])
    # Every qualified executable/template/inherited file must still be exact.
    # New declaration wrappers below add no model-visible instructions or motion.
    for group in ('source','inherited'):
        for name,value in pilot_sources[group].items():assert sha(REPO/name)==value['sha256'],name
    if (AREA/'evidence').exists():
        assert not any((AREA/'evidence').iterdir()), 'Allocation cannot be selected again after any scored attempt'
    for block in allocation['blocks']:
        assert not (AREA/'evidence'/(identity+'-'+block['id']+'-attempt')).exists()
    folder=MAP/'releases/RCI001-C03-scored'/identity
    assert not folder.exists();folder.mkdir(parents=True)
    save(folder/'allocation.json',allocation)
    save(folder/'pilot-gate.json',dict(audit_path=str(pilot_root/'assessment/receipt.json'),
        audit_sha256=sha(pilot_root/'assessment/receipt.json'),official_path=str(pilot_root/'official-status.json'),
        official_sha256=sha(pilot_root/'official-status.json'),pilot_manifest=str(pilot_manifest_path),
        pilot_manifest_sha256=sha(pilot_manifest_path)))
    sources=copy.deepcopy(pilot_sources['source'])
    for path in sorted([*AREA.glob('*.py'),*AREA.glob('*.md'),allocation_path]):
        sources[path.relative_to(REPO).as_posix()]=dict(sha256=sha(path),bytes=path.stat().st_size)
    with zipfile.ZipFile(folder/'source.zip','x',zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(sources):archive.write(REPO/name,name)
    save(folder/'snapshot.json',dict(schema='campaign003-final-scored-snapshot-1',source=sources,
        inherited=pilot_sources['inherited'],qualified_pilot_snapshot_sha256=sha(pilot_manifest_path.parent/pilot['source_snapshot_path'])))
    revision={**fields(identity),'architecture_id':'RCI001','parent_revision_id':pilot['revision_id'],
        'status':'frozen','title':'Campaign 003 frozen scored allocation',
        'summary':'Independent persistent blocks with three declared fresh C sessions each; exact successfully qualified task/runtime, no replacements.',
        'mechanism':(HERE/'CONTRACT.md').read_text(encoding='utf-8')+'\n\n'+(AREA/'PROTOCOL.md').read_text(encoding='utf-8')+'\n\n'+json.dumps(allocation),
        'attachments':[ref(folder/'source.zip','Exact qualified runtime and declaration sources'),
            ref(folder/'snapshot.json','Qualified and inherited source identities'),ref(folder/'allocation.json','Pre-outcome fixed allocation'),
            ref(folder/'pilot-gate.json','Complete independent pilot prerequisite')]}
    append('revision',revision,folder/'revision-record.json')
    manifests={}
    for number,block in enumerate(allocation['blocks'],1):
        target=folder/'blocks'/block['id'];target.mkdir(parents=True)
        for name in ('source.zip','snapshot.json'):shutil.copyfile(folder/name,target/name)
        run_id=identity+'-'+block['id']+'-attempt'
        apparatus=apply_limits(dict(run_id=run_id,seed=block['seed'],noise_seed=block['noise_seed'],
            schedule_seed=block['schedule_seed'],encounters=3,initial_order=Schedule(block['schedule_seed'],3).current,
            mode='serve',stage='reviewed_campaign'),'reviewed_campaign')
        manifest=dict(stage='reviewed_campaign',run_id=run_id,revision_id=identity,created_at=now(),
            description='Predeclared scored persistent block '+block['id'],encounter_limit=3,
            human_approval_reference=pilot['human_approval_reference'],authority=pilot['authority'],
            model=pilot['model'],source_snapshot_path='snapshot.json',source_snapshot_sha256=sha(target/'snapshot.json'),
            apparatus_manifest=apparatus,output=str(AREA/'evidence'/run_id),no_replacement=True,
            scientific_prompt_unchanged=True,runtime_envelope=pilot['runtime_envelope'],
            additional_budget_authority=pilot['additional_budget_authority'],
            allocation_reference=dict(path=str(folder/'allocation.json'),sha256=sha(folder/'allocation.json'),
                block_id=block['id'],replicate=number),
            prerequisite_audit=dict(path=str(pilot_root/'assessment/receipt.json'),sha256=sha(pilot_root/'assessment/receipt.json'),
                official_status_path=str(pilot_root/'official-status.json'),official_status_sha256=sha(pilot_root/'official-status.json')))
        save(target/'manifest.json',manifest)
        record={**fields(run_id),'revision_id':identity,'stage':'evaluation',
            'condition_id':'fresh-conversation-persistent-filesystem','protocol_id':allocation['id'],
            'scenario_id':'C-placement-known-workcell','paired_block_id':run_id,'replicate':number,
            'started_at':None,'rerun_of_run_id':None,'condition_details':dict(not_scored=False,block=block['id'],declared_C_encounters=3),
            'seeds':state(target/'manifest.json','Protected fixed seeds'),
            'frozen_refs':{role:state(target/filename,label) for role,filename,label in (
                ('code','snapshot.json','Exact sources'),('environment','snapshot.json','Qualified inherited environment'),
                ('models','manifest.json','Fixed model and sole bootstrap'),('protocol','manifest.json','Exact allocation-bound block'),
                ('scenario','manifest.json','Fixed workcell and schedule'))},
            'evidence':[ref(target/'manifest.json','Pre-outcome scored declaration'),ref(folder/'allocation.json','Fixed complete allocation')]}
        append('run',record,target/'run-record.json')
        manifests[str((target/'manifest.json').relative_to(folder)).replace('\\','/')]=sha(target/'manifest.json')
    mapcmd('build');print(mapcmd('validate','--output','validation.json'))
    save(folder/'freeze-receipt.json',dict(created_at=now(),revision_id=identity,allocation_sha256=sha(folder/'allocation.json'),
        manifests=manifests,qualified_pilot_sources_unchanged=True,scored_model_calls_at_freeze=0))
    print(json.dumps(dict(frozen=identity,blocks=len(manifests),folder=str(folder))),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('identity');p.add_argument('allocation');p.add_argument('pilot_audit');a=p.parse_args()
    freeze(a.identity,a.allocation,a.pilot_audit)
