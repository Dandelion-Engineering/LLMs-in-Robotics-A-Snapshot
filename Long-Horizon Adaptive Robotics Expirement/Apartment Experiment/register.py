"""Declare exact new development attempts and append honest terminal results."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
from common import HERE, REPO, DEFAULT_ROOT, sha, read, save, inventory

MAP=REPO/'Long-Horizon Adaptive Robotics Expirement/Architecture Map'
TOOL=MAP/'map.py'
ARCH='APARTMENT-001'

def call(*args):
    return json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(TOOL),*args],text=True,encoding='utf-8'))

def base(identifier):
    return dict(schema_version='architecture-map-1.0',id=identifier,recorded_at=datetime.now(timezone.utc).isoformat(),author='Codex',tags=['apartment','commissioning','not-official'],details={})

def ref(label,path,access='operator'):
    return dict(label=label,uri=str(path),sha256=sha(path),state='available',access=access,locator=None)

def append(kind,value,out):
    path=out/(value['id']+'.json');save(path,value)
    status=call('status','--json')
    p=subprocess.run([sys.executable,'-X','utf8','-B',str(TOOL),'append',kind,'--input',str(path),'--expected-sha256',status['store_sha256']],capture_output=True,text=True,encoding='utf-8')
    if p.returncode:raise RuntimeError(p.stdout+p.stderr)

def declare(identifier,model=False):
    root=DEFAULT_ROOT/'engineering'/identifier
    root.mkdir(parents=True,exist_ok=False)
    code=root/'source';code.mkdir()
    for path in HERE.iterdir():
        if path.is_file() and path.suffix in ('.py','.json','.md','.html','.ps1'):shutil.copy2(path,code/path.name)
    save(code/'source-origin.json',{'repository':str(REPO)})
    save(root/'source-manifest.json',inventory(code))
    from run import source_identity
    save(root/'full-source-identity.json',source_identity())
    if not call('lookup',ARCH,'--kind','architecture','--json')['total']:
        append('architecture',{**base(ARCH), 'title':'Long-lived apartment Robot Codex',
            'summary':'Matched 21-assignment household/throwing schedule under ordinary v0.2 versus v0.2 Maps Edition; perception-only room inference, battery/dock session boundaries, isolated persistent files, D-drive replay and deferred hibernation.'},root)
    revision=identifier+'-revision'
    append('revision',{**base(revision),'architecture_id':ARCH,'parent_revision_id':None,'status':'implemented',
        'title':identifier+' apparatus candidate','summary':'Throwaway engineering source snapshot; no official experiment launch.',
        'mechanism':'MuJoCo apartment and mobile Cartesian arm, noisy RGB-D/lidar/proprioception without hidden labels; physical household tasks and generic dynamic arm/gripper trajectories. Exact development source retained outside both official conditions.',
        'attachments':[], 'details':{'source':ref('Immutable development source manifest',root/'source-manifest.json')}},root)
    absent=dict(state='none',refs=[],reason='No reasoning model used by this deterministic engineering attempt.')
    if model:
        launcher=REPO/'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/launch/robot_codex_launcher.py'
        absent=dict(state='recorded',refs=[ref('Existing native ChatGPT runtime model declaration',launcher)],reason='Authorized throwaway Robot Codex commissioning; gpt-6-astra/max, existing login, no API fallback. All turns remain outside official condition lineages.')
    unknown=dict(state='unknown',refs=[],reason='Development qualification records installed environment and fixture details in its result artifacts.')
    recorded=dict(state='recorded',refs=[ref('Exact source snapshot',root/'source-manifest.json')],reason=None)
    append('run',{**base(identifier),'revision_id':revision,'stage':'development','condition_id':'throwaway-apparatus',
        'protocol_id':'APARTMENT-commissioning-1','scenario_id':'private-engineering-fixtures','paired_block_id':'unpaired-engineering',
        'replicate':1,'started_at':None,'rerun_of_run_id':None,'condition_details':{'official_schedule_consumed':False},
        'seeds':unknown,'frozen_refs':dict(code=recorded,environment=unknown,models=absent,protocol=unknown,scenario=unknown),'evidence':[]},root)
    print(json.dumps({'run_id':identifier,'root':str(root),'source':str(code)}))

def finish(identifier,status_path):
    root=DEFAULT_ROOT/'engineering'/identifier;status=read(status_path)
    report=root/'output/result.json'
    result=read(report) if report.is_file() else {'passed':False,'error':'No terminal result emitted; raw queue log is authoritative for execution failure'}
    queue_ok=status['state']=='succeeded' and type(status['exit_status']) is int and status['exit_status']==0
    passed=result['passed'] and queue_ok
    append('result',{**base(identifier+'-result'),'run_id':identifier,'supersedes_result_id':None,
        'execution_status':'completed' if queue_ok else 'failed','validity':'valid' if queue_ok else 'invalid',
        'validity_reason':'Exact declared throwaway source; queue status and individual engineering checks retained. This is apparatus evidence, not official robot performance.',
        'outcome':'success' if passed else 'failure','ended_at':datetime.now(timezone.utc).isoformat(),
        'termination_reason':'Engineering checks passed' if passed else 'Engineering assertion or worker failed; retained for prospective repair',
        'metrics':[],'evidence':([ref('Engineering result',report)] if report.is_file() else [ref('Worker log',Path(status['log_path']))])+[ref('Queue status',status_path)]},root)
    print(json.dumps({'registered':identifier+'-result','passed':passed}))

def submit(identifier,entry,model=False):
    if Path(entry).name!=entry or not entry.endswith('.py') or not (HERE/entry).is_file():raise ValueError('Known local engineering entry required')
    declare(identifier,model)
    root=DEFAULT_ROOT/'engineering'/identifier
    queue_tool=REPO.parent/'tools/compute_queue/compute_queue.py'
    status=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(queue_tool),'submit','--project','LLMs-in-Robotics',
        '--cwd',str(REPO),'--',sys.executable,'-X','utf8','-B',str(root/'source'/entry),'--output',str(root/'output')],text=True,encoding='utf-8'))
    save(root/'queue-submission.json',status)
    print(json.dumps({'submitted':identifier,'queue_job':status['id']}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['declare','finish','submit']);p.add_argument('identifier');p.add_argument('--status',type=Path);p.add_argument('--entry');p.add_argument('--model',action='store_true');a=p.parse_args()
    if a.action=='declare':declare(a.identifier,a.model)
    elif a.action=='finish':finish(a.identifier,a.status)
    else:submit(a.identifier,a.entry,a.model)
