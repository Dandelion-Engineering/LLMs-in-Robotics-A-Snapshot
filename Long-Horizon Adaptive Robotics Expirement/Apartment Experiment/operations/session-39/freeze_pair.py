"""Prepare the certified pristine v4 pair only after successful fresh audit."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
REPO=Path('C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics')
APPREL=Path('Long-Horizon Adaptive Robotics Expirement/Apartment Experiment')
OPS=REPO/APPREL/'operations/session-39'
PAIR=Path('D:/Dandelion-Apartment-Experiment/official/apartment-v4')
# Preserve the operator helper alongside this immutable attempt and verify
# correspondence before importing the live map-writing location.
assert hashlib.sha256((HERE/'operator-attempts.py').read_bytes()).digest()==hashlib.sha256((OPS/'attempts.py').read_bytes()).digest()
sys.path.insert(0,str(OPS))
from attempts import read,sha,save,inventory,append,base,ref,QUEUE

def main():
    own_manifest=read(HERE/'manifest.json')
    assert own_manifest['official_writes'] is True and own_manifest['model_calls_planned']==0
    for name,row in own_manifest['files'].items():assert sha(HERE/name)==row['sha256'],name
    audit=BASE/'audit003';certificate=read(audit/'output/certificate.json');proof=read(audit/'output/result.json')
    q=read(OPS/'audit003-queue.json')
    actual=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',q['id']],text=True,encoding='utf-8'))
    assert actual['state']=='succeeded' and type(actual['exit_status']) is int and actual['exit_status']==0
    assert proof['passed'] is True and len(proof['checks'])==10 and all(proof['checks'].values())
    release=BASE/'release002';manifest=read(release/'manifest.json')
    assert certificate['release_manifest_sha256']==sha(release/'manifest.json')
    assert certificate['source_identity']==manifest['source_identity'] and certificate['config']==manifest['config']
    assert inventory(release/'frozen_repository')==manifest['files']
    assert not PAIR.exists(),'The new official root must be unused'
    assert shutil.disk_usage(PAIR.parent).free>=50*1024**3,'Insufficient prelaunch storage margin'
    shutil.copytree(release/'frozen_repository',PAIR/'frozen_repository')
    license_relative=Path('Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-005/vendor/LICENSE')
    old_frozen=PAIR.parent/'apartment-v3/frozen_repository'
    assert sha(old_frozen/license_relative)==read(old_frozen/'source-manifest.json')[license_relative.as_posix()]['sha256']
    shutil.copyfile(old_frozen/license_relative,PAIR/'frozen_repository'/license_relative)
    code=PAIR/'frozen_repository'/APPREL
    save(code/'commissioning.json',certificate);save(code/'commissioning-audit.json',proof)
    save(PAIR/'frozen_repository/source-manifest.json',inventory(PAIR/'frozen_repository'))
    original=PAIR.parent/'apartment-v2'
    shutil.copyfile(original/'hidden-schedule.json',PAIR/'hidden-schedule.json')
    assert sha(PAIR/'hidden-schedule.json')==read(original/'prepared.json')['schedule_sha256']
    assert sha(PAIR/'hidden-schedule.json')==read(PAIR.parent/'apartment-v3/prepared.json')['schedule_sha256']
    program="""import json,sys
from pathlib import Path
from run import prepare,source_identity
from common import read,save,inventory
from revision_config import CONFIG
from environment import identity
pair=Path(sys.argv[1]);cert=read(Path.cwd()/'commissioning.json')
assert source_identity()==cert['source_identity'] and identity()==cert['environment'] and CONFIG==cert['config']
for condition in ('baseline','maps'):
 root=pair/condition;prepare(root,condition,'official',read(pair/'hidden-schedule.json'),CONFIG)
 assert inventory(root/'filesystem')==read(pair.parent/'apartment-v2'/condition/'initial-filesystem.json')
 run=read(root/'run.json');run.update(official_pair_root=str(pair),revision_id='APARTMENT-v4-integrated-repair-frozen',run_id='APARTMENT-v4-'+condition);save(root/'run.json',run)
 save(pair/(condition+'-lineage.json'),dict(active_root=str(root),history=[],policy=CONFIG['recovery_policy']))
print(json.dumps({'passed':True,'source_identity':source_identity(),'conditions':['baseline','maps'],'official_starts':0}))
"""
    response=subprocess.check_output([sys.executable,'-X','utf8','-B','-c',program,str(PAIR)],cwd=code,text=True,encoding='utf-8')
    readback=json.loads(response);assert readback['passed'] and readback['official_starts']==0
    authority=code/'operations/session-39/authority-original.md'
    prepared=dict(passed=True,root=str(PAIR),frozen_apparatus=str(code),revision_id='APARTMENT-v4-integrated-repair-frozen',official_launched=False,official_assignments_consumed=0,
        source_manifest_sha256=sha(PAIR/'frozen_repository/source-manifest.json'),certificate_sha256=sha(code/'commissioning.json'),schedule_sha256=sha(PAIR/'hidden-schedule.json'),config=certificate['config'],
        initial={c:read(PAIR/c/'initial-filesystem.json') for c in ('baseline','maps')},pristine_initial_bytes_equal_original=True,
        human_authority=ref('October 9 ordered commissioning and Baseline launch authority',authority),validation=ref('Fresh integrated independent audit',audit/'output/result.json'),maps_requires_explicit_later_instruction=True)
    save(PAIR/'prepared.json',prepared)
    evaluation=PAIR/'evaluation';evaluation.mkdir();shutil.copyfile(code/'ANALYSIS.md',evaluation/'ANALYSIS.md');shutil.copyfile(code/'operations/session-39/PROTOCOL.md',evaluation/'PROTOCOL.md')
    save(PAIR/'analysis-freeze.json',dict(schema='apartment-analysis-freeze-5',passed=True,analysis_path=str(evaluation/'ANALYSIS.md'),analysis_sha256=sha(evaluation/'ANALYSIS.md'),protocol_sha256=sha(evaluation/'PROTOCOL.md'),prepared_sha256=sha(PAIR/'prepared.json'),certificate_sha256=sha(code/'commissioning.json'),frozen_before_official_launch=True,official_assignments_consumed=0,run_ids=['APARTMENT-v4-baseline','APARTMENT-v4-maps'],scope='Fresh matched pair, unchanged v3 scientific apparatus and schedule, repaired workspace reliability; no prior or pilot learning transfer. Baseline only; no automatic recovery or Maps launch.'))
    revision='APARTMENT-v4-integrated-repair-frozen'
    append('revision',base()|dict(id=revision,architecture_id='APARTMENT-001',parent_revision_id='APARTMENT-s39-release002',status='frozen',title='Pristine apartment v4 integrated repaired pair',summary='Fresh matched Baseline/Maps roots from the independently commissioned exact cup/workspace repaired release.',mechanism='Unchanged v3 scientific apparatus, tasks, original hidden schedule, actual templates, native model and 360/600-second windows; Session 38 startup repair and Session 39 cooperative journal retirement, fully recommissioned with four fresh native pilot calls. Normal session checkpoints and all old histories retained.',attachments=[],details={'prepared':ref('Pristine pair preparation',PAIR/'prepared.json'),'certificate':ref('Fresh integrated commissioning certificate',code/'commissioning.json')}))
    for condition in ('baseline','maps'):
        schedule=ref('Original authenticated matched hidden schedule',PAIR/'hidden-schedule.json');schedule['access']='evaluator_only'
        known=lambda r:dict(state='recorded',refs=[r],reason=None)
        cert=ref('Frozen release and environment certificate',code/'commissioning.json')
        append('run',base()|dict(id='APARTMENT-v4-'+condition,revision_id=revision,stage='evaluation',condition_id=condition,protocol_id='APARTMENT-v4',scenario_id='apartment-procedural-2',paired_block_id='APARTMENT-pair-004',replicate=1,started_at=None,rerun_of_run_id=None,
            condition_details=dict(official_launched=False,assignments_consumed=0,condition=condition,battery=certificate['config'],failed_or_engineering_state_carried_forward=False),seeds=known(schedule),
            frozen_refs=dict(code=known(ref('Frozen source manifest',PAIR/'frozen_repository/source-manifest.json')),environment=known(cert),models=known(cert),protocol=known(ref('Current ordered commissioning and launch protocol',code/'operations/session-39/PROTOCOL.md')),scenario=known(schedule),initial_filesystem=known(ref('Pristine template inventory',PAIR/condition/'initial-filesystem.json'))),evidence=[ref('Pristine pair preparation',PAIR/'prepared.json'),ref('Prospective analysis freeze',PAIR/'analysis-freeze.json')]))
    out=HERE/'output';out.mkdir();save(out/'result.json',dict(passed=True,pair=str(PAIR),checks=dict(certified_release=True,both_pristine=True,original_schedule=True,zero_starts=True),official_launched=False,prepared_sha256=sha(PAIR/'prepared.json')))
    print(json.dumps(dict(passed=True,pair=str(PAIR),official_launched=False)))
if __name__=='__main__':main()
