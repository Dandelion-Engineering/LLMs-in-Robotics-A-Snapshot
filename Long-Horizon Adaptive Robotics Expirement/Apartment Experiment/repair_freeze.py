"""Prepare a fresh pair after validated repair, retaining exact original starts."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
from common import HERE,DEFAULT_ROOT,save,read,sha,inventory,canonical
from failure_audit import FAILED
from freeze import copy_sources
from run import source_identity,prepare
from register import ARCH,base,ref,append
from register_frozen import recorded

REVISION='APARTMENT-v1-storage2-frozen'
PREFIX='APARTMENT-v1-restart001'

def create(root,validation):
    root=Path(root).resolve();validation=Path(validation)
    assert root.drive.upper()=='D:' and not root.exists()
    status=read(validation/'queue-status.json');proof=read(validation/'output/result.json')
    assert status['state']=='succeeded' and type(status['exit_status']) is int and status['exit_status']==0
    assert proof['passed'] is True and all(proof['checks'].values())
    certificate=proof['certificate'];assert certificate['source_identity']==source_identity()
    from environment import identity
    assert certificate['environment']==identity()
    save(HERE/'commissioning.json',certificate);save(HERE/'commissioning-audit.json',proof)
    root.mkdir(parents=True);frozen=copy_sources(root/'frozen_repository')
    shutil.copy2(FAILED/'hidden-schedule.json',root/'hidden-schedule.json')
    schedule=read(root/'hidden-schedule.json')
    original_prepared=read(FAILED/'prepared.json')
    assert sha(root/'hidden-schedule.json')==original_prepared['schedule_sha256']
    for condition in ('baseline','maps'):
        prepare(root/condition,condition,'official',schedule,certificate['config'])
        assert inventory(root/condition/'filesystem')==read(FAILED/condition/'initial-filesystem.json')
        assert read(root/condition/'run.json')['launched'] is False
        assert sha(root/condition/'schedule.json')==original_prepared['schedule_sha256']
        assert not (root/condition/'sessions').exists() and not (root/condition/'latest-checkpoint.json').exists()
    assert inventory(FAILED/'maps/filesystem')==read(FAILED/'maps/initial-filesystem.json')
    assert not (FAILED/'maps/sessions').exists() and read(FAILED/'maps/run.json')['launched'] is False
    evidence=dict(passed=True,official_launched=False,official_assignments_consumed=0,root=str(root),frozen_apparatus=str(frozen),
        schedule_sha256=sha(root/'hidden-schedule.json'),source_manifest_sha256=sha(root/'frozen_repository/source-manifest.json'),
        certificate_sha256=sha(HERE/'commissioning.json'),config=certificate['config'],
        initial={c:read(root/c/'initial-filesystem.json') for c in ('baseline','maps')},
        original_start_root=str(FAILED),initial_bytes_equal_original=True,original_maps_still_pristine=True,
        rejected_launch_preserved_at=str(FAILED/'baseline'),repair_validation=ref('Independent repair gates',validation/'output/result.json'))
    save(root/'prepared.json',evidence);save(HERE/'prepared.json',evidence)
    evaluation=root/'evaluation';evaluation.mkdir()
    shutil.copy2(FAILED/'evaluation/ANALYSIS.md',evaluation/'ANALYSIS.md')
    analysis=dict(schema='apartment-analysis-freeze-2',passed=True,analysis_path=str(evaluation/'ANALYSIS.md'),analysis_sha256=sha(evaluation/'ANALYSIS.md'),
        prepared_sha256=sha(root/'prepared.json'),certificate_sha256=sha(HERE/'commissioning.json'),
        frozen_before_official_launch=True,official_assignments_consumed=0,run_ids=[PREFIX+'-'+c for c in ('baseline','maps')],
        scope='Exact original evaluation text rebound to a pristine repaired pair. Failed original launch is excluded completely under director authorization.')
    save(root/'analysis-freeze.json',analysis);save(HERE/'analysis-freeze.json',analysis)
    out=root/'registration';out.mkdir()
    append('revision',{**base(REVISION),'tags':['apartment','frozen','storage-lifecycle-repair','unlaunched'],
        'architecture_id':ARCH,'parent_revision_id':'APARTMENT-v1-frozen','status':'frozen',
        'title':'Apartment v1 prospective storage and retirement repair',
        'summary':'Exact original sensors, physics, tasks, clocks, model, windows, templates and matched schedule; compact lossless filesystem history, constant-space frame commitments, bounded native notification memory and clean abnormal retirement.',
        'mechanism':'Unchanged embodied apparatus with bounded-depth content deltas, chunked immutable snapshots, independent journal reconstruction, ordered frame commitments, queue backpressure, finite native stream/event storage budgets and preserved native drain gates.',
        'attachments':[],'details':{'commissioning':ref('Frozen repair certificate',frozen/'commissioning.json'),'prepared':ref('Pristine paired restart',root/'prepared.json')}},out)
    for condition in ('baseline','maps'):
        schedule_ref=ref('Original matched hidden schedule',root/'hidden-schedule.json','evaluator_only');cert=ref('Frozen runtime and battery parameters',frozen/'commissioning.json')
        append('run',{**base(PREFIX+'-'+condition),'tags':['apartment','evaluation','prepared','unlaunched','fresh-start'],
            'revision_id':REVISION,'stage':'evaluation','condition_id':condition,'protocol_id':'APARTMENT-v1','scenario_id':'apartment-procedural-1',
            'paired_block_id':'APARTMENT-pair-001-restart001','replicate':1,'started_at':None,
            'rerun_of_run_id':'APARTMENT-v1-baseline' if condition=='baseline' else None,
            'condition_details':dict(official_launched=False,assignments_consumed=0,condition=condition,original_preparation='APARTMENT-v1-'+condition,failed_launch_state_carried_forward=False,battery=certificate['config']),
            'seeds':recorded(schedule_ref),'frozen_refs':dict(code=recorded(ref('Frozen source manifest',root/'frozen_repository/source-manifest.json')),
                environment=recorded(cert),models=recorded(cert),protocol=recorded(ref('Comparison',frozen/'COMPARISON.md')),scenario=recorded(schedule_ref),
                initial_filesystem=recorded(ref('Exact original initial file inventory',root/condition/'initial-filesystem.json'))),
            'evidence':[ref('Clean preparation',root/'prepared.json'),ref('Original evaluation text rebound to new pair',root/'analysis-freeze.json')]},out)
    save(HERE/'preparation-readback.json',dict(passed=True,root=str(root),prepared_sha256=sha(root/'prepared.json'),
        baseline_pristine=True,maps_pristine=True,zero_assignments=True,original_schedule_matched=True,initial_bytes_equal_original=True,official_launched=False))
    print(canonical({k:v for k,v in evidence.items() if k!='initial'}).decode())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--validation',type=Path,required=True);a=p.parse_args();create(a.root,a.validation)
