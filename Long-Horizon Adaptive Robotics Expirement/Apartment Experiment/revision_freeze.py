"""Freeze the commissioned v2 revision and create its pristine matched pair."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from common import HERE,REPO,DEFAULT_ROOT,canonical,inventory,read,save,sha
from freeze import copy_sources
from run import source_identity,prepare
from revision_config import CONFIG,REVISION,PREFIX
from register import ARCH,append,base,ref
from register_frozen import recorded


def create(root,validation):
    root=Path(root).resolve();validation=Path(validation).resolve()
    if root.drive.upper()!='D:' or root.exists():raise ValueError('A new D: pair is required')
    status=read(validation/'queue-status.json');proof=read(validation/'output/result.json')
    assert status['state']=='succeeded' and type(status['exit_status']) is int and status['exit_status']==0
    assert proof['passed'] is True and all(proof['checks'].values())
    certificate=proof['certificate'];assert certificate['source_identity']==source_identity() and certificate['config']==CONFIG
    assert all(sha(HERE/name)==value for name,value in certificate['protocol_sha256'].items())
    from environment import identity
    assert certificate['environment']==identity()
    save(HERE/'commissioning.json',certificate);save(HERE/'commissioning-audit.json',proof)
    root.mkdir(parents=True);frozen=copy_sources(root/'frozen_repository')
    for name in ('RELIABILITY-REVISION.md','ANALYSIS.md','SECOND-FAILURE-INVESTIGATION.md'):
        shutil.copy2(HERE/name,frozen/name)
    authority=HERE/'operations/session-33/launch-authority.json'
    authority_target=frozen/'operations/session-33/launch-authority.json'
    authority_target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(authority,authority_target)
    assert sha(authority_target)==sha(authority)
    target=root/'frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Long-Lived Robot Experiment Design.md'
    shutil.copy2(HERE.parent/'Apartment Long-Lived Robot Experiment Design.md',target)
    save(root/'frozen_repository/source-manifest.json',{k:v for k,v in inventory(root/'frozen_repository').items() if k!='source-manifest.json'})
    original=DEFAULT_ROOT/'official/apartment-v1';previous=DEFAULT_ROOT/'official/apartment-v1-restart001'
    shutil.copy2(original/'hidden-schedule.json',root/'hidden-schedule.json')
    assert sha(root/'hidden-schedule.json')==read(original/'prepared.json')['schedule_sha256']
    schedule=read(root/'hidden-schedule.json')
    for condition in ('baseline','maps'):
        prepare(root/condition,condition,'official',schedule,CONFIG)
        assert inventory(root/condition/'filesystem')==read(original/condition/'initial-filesystem.json')
        r=read(root/condition/'run.json');r.update(official_pair_root=str(root),revision_id=REVISION,run_id=PREFIX+'-'+condition)
        save(root/condition/'run.json',r)
        assert not (root/condition/'sessions').exists() and not (root/condition/'latest-checkpoint.json').exists()
    for condition in ('baseline','maps'):
        save(root/(condition+'-lineage.json'),dict(active_root=str(root/condition),history=[],policy=CONFIG['recovery_policy']))
    evidence=dict(passed=True,official_launched=False,official_assignments_consumed=0,root=str(root),frozen_apparatus=str(frozen),revision_id=REVISION,
        schedule_sha256=sha(root/'hidden-schedule.json'),source_manifest_sha256=sha(root/'frozen_repository/source-manifest.json'),
        certificate_sha256=sha(frozen/'commissioning.json'),config=CONFIG,initial={c:read(root/c/'initial-filesystem.json') for c in ('baseline','maps')},
        pristine_initial_bytes_equal_original=True,prior_histories_engineering_only=[str(original),str(previous)],
        human_authority=ref('October 7 11:50 PDT prospective amendment and launch instruction',authority_target),
        validation=ref('Independent revised-apparatus validation',validation/'output/result.json'),maps_requires_explicit_later_instruction=True)
    save(root/'prepared.json',evidence);save(HERE/'prepared.json',evidence)
    evaluation=root/'evaluation';evaluation.mkdir();shutil.copy2(HERE/'ANALYSIS.md',evaluation/'ANALYSIS.md')
    analysis=dict(schema='apartment-analysis-freeze-3',passed=True,analysis_path=str(evaluation/'ANALYSIS.md'),analysis_sha256=sha(evaluation/'ANALYSIS.md'),
        prepared_sha256=sha(root/'prepared.json'),certificate_sha256=sha(frozen/'commissioning.json'),frozen_before_official_launch=True,
        official_assignments_consumed=0,run_ids=[PREFIX+'-'+c for c in ('baseline','maps')],
        scope='Fresh matched revision; total starts include abandoned recovery tails once; no old learned/scored state or engineering state carried forward.')
    save(root/'analysis-freeze.json',analysis);save(HERE/'analysis-freeze.json',analysis)
    actual=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B','-c','import run,json; print(json.dumps(run.source_identity()))'],cwd=frozen,text=True,encoding='utf-8'))
    assert actual==source_identity()
    out=root/'registration';out.mkdir()
    append('revision',{**base(REVISION),'tags':['apartment','frozen','reliability','recovery','revised-geometry'],
        'architecture_id':ARCH,'parent_revision_id':'APARTMENT-v1-storage2-frozen','status':'frozen',
        'title':'Apartment v2 verified session boundaries and revised shared environment',
        'summary':'Pristine actual filesystem pair; 360/600-second windows, wider kitchen access, deliberately unreachable bedroom port, structured errors and explicit immutable clean-boundary recovery.',
        'mechanism':'Continuous MuJoCo perception-only embodied tasks, unchanged gpt-6-astra/max and sensors; verified world/RNG/inode/replay checkpoints at every normal boundary, clock epochs and failed-tail preserving recovery branches. No native retries or model fallback.',
        'attachments':[],'details':{'commissioning':ref('Frozen commissioning certificate',frozen/'commissioning.json'),'prepared':ref('Pristine revised pair',root/'prepared.json')}},out)
    for condition in ('baseline','maps'):
        schedule_ref=ref('Original matched hidden schedule and variations',root/'hidden-schedule.json','evaluator_only');cert=ref('Frozen runtime and revised windows',frozen/'commissioning.json')
        append('run',{**base(PREFIX+'-'+condition),'tags':['apartment','evaluation','prepared','fresh-revision'],
            'revision_id':REVISION,'stage':'evaluation','condition_id':condition,'protocol_id':'APARTMENT-v2','scenario_id':'apartment-procedural-2',
            'paired_block_id':'APARTMENT-pair-002','replicate':1,'started_at':None,'rerun_of_run_id':None,
            'condition_details':dict(official_launched=False,assignments_consumed=0,condition=condition,battery=CONFIG,prior_failed_histories='engineering evidence only',failed_or_engineering_state_carried_forward=False),
            'seeds':recorded(schedule_ref),'frozen_refs':dict(code=recorded(ref('Frozen source manifest',root/'frozen_repository/source-manifest.json')),
                environment=recorded(cert),models=recorded(cert),protocol=recorded(ref('Frozen comparison',frozen/'COMPARISON.md')),scenario=recorded(schedule_ref),
                initial_filesystem=recorded(ref('Pristine initial inventory',root/condition/'initial-filesystem.json'))),
            'evidence':[ref('Pristine preparation',root/'prepared.json'),ref('Prospective evaluation',root/'analysis-freeze.json')]},out)
    append('note',{**base(PREFIX+'-prospective-scope'),'tags':['apartment','fresh-revision','not-performance'],
        'target_ids':[REVISION,PREFIX+'-baseline',PREFIX+'-maps','APARTMENT-v1-baseline','APARTMENT-v1-restart001-baseline'],
        'claim_type':'observation','supersedes_note_id':None,
        'body':'Randy explicitly authorized this pristine revised pair, 360/600-second windows and shared environment changes. Both prior failed official histories are now engineering evidence only and contribute no learned or scored state. The original hidden schedule and pristine template bytes are retained. Every normal session boundary checkpoints; explicit immutable recovery preserves and counts failed tails. Baseline launch and 30-minute monitoring are authorized after commissioning; Maps requires a later human instruction. Preparation is not a scientific result.',
        'evidence':[ref('Human prospective amendment',authority_target),ref('Prospective evaluation',root/'analysis-freeze.json'),ref('Commissioning readback',validation/'output/result.json')]},out)
    receipt=dict(passed=True,root=str(root),prepared_sha256=sha(root/'prepared.json'),baseline_pristine=True,maps_pristine=True,
        zero_assignments=True,original_schedule_matched=True,initial_bytes_equal_original=True,official_launched=False,frozen_source_readback=True)
    save(root/'preparation-readback.json',receipt);save(HERE/'preparation-readback.json',receipt)
    print(canonical({k:v for k,v in evidence.items() if k!='initial'}).decode())


if __name__=='__main__':
    import json
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--validation',type=Path,required=True);a=p.parse_args();create(a.root,a.validation)
