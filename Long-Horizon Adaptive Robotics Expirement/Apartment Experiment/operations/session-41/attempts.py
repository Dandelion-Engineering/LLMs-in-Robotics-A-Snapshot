"""Once-only Session 41 attempts and append-only map records."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
APP = HERE.parents[1]
REPO = HERE.parents[3]
ROOT = Path('D:/Dandelion-Apartment-Experiment/engineering/launch-session41')
RELEASE = Path('D:/Dandelion-Apartment-Experiment/engineering/commissioning-session39/release002')
MAP = REPO/'Long-Horizon Adaptive Robotics Expirement/Architecture Map/map.py'
QUEUE = REPO.parent/'tools/compute_queue/compute_queue.py'
RID = 'APARTMENT-s39-release002'

def read(p): return json.loads(Path(p).read_bytes())
def sha(p):
    with Path(p).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()
def save(p, value):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, indent=2, allow_nan=False); f.write('\n')
def ref(label, p): return dict(label=label, uri=str(p), sha256=sha(p), state='available', access='operator', locator=None)
def invoke(*args):
    return subprocess.check_output([sys.executable, '-X', 'utf8', '-B', str(MAP), *args], text=True, encoding='utf-8')
def base():
    return dict(schema_version='architecture-map-1.0', recorded_at=datetime.now(timezone.utc).isoformat(), author='Codex session 41', tags=['apartment','certified-release-launch','engineering'], details={})
def append(kind, record):
    path=HERE/('map-'+record['id']+'.json'); save(path,record)
    print(invoke('append',kind,'--input',str(path),'--expected-sha256',json.loads(invoke('status','--json'))['store_sha256']))
def inventory(root):
    return {p.relative_to(root).as_posix():dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(Path(root).rglob('*')) if p.is_file() and not p.is_symlink()}

def register(name, entry, purpose, files=(), cases=(), prior=None, model_calls=0, official_writes=False):
    root=ROOT/name;root.mkdir(parents=True,exist_ok=False)
    for source,dest in [(HERE/entry,entry),*files]:
        target=root/dest;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    release=read(RELEASE/'manifest.json')
    manifest=dict(id='APARTMENT-s41-'+name,purpose=purpose,cases=list(cases),files=inventory(root),release=str(RELEASE),
        release_manifest_sha256=sha(RELEASE/'manifest.json'),source_identity=release['source_identity'],environment=release['environment'],config=release['config'],
        repository=str(REPO),python=sys.executable,model_calls_planned=model_calls,official_writes=official_writes,created_at=datetime.now(timezone.utc).isoformat(),rerun_of=prior)
    save(root/'manifest.json',manifest)
    fref=ref('Immutable commissioning attempt manifest',root/'manifest.json');known=dict(state='recorded',refs=[fref],reason=None)
    no_model=dict(state='none',refs=[],reason='No provider invocation in this deterministic engineering attempt')
    append('run',base()|dict(id=manifest['id'],revision_id=RID,stage='diagnostic',condition_id='certified-release-admission',protocol_id='APARTMENT-s41-commissioning',scenario_id=name,paired_block_id='unpaired-engineering',replicate=1,started_at=None,rerun_of_run_id=prior,condition_details={'purpose':purpose,'model_calls_planned':model_calls},seeds=known,frozen_refs={k:known for k in ('code','environment','protocol','scenario')}|{'models':known if model_calls else no_model},evidence=[fref]))
    q=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'submit','--project','LLMs-in-Robotics','--cwd',str(root),'--',sys.executable,'-X','utf8','-B',str(root/entry)],text=True,encoding='utf-8'))
    save(HERE/(name+'-queue.json'),q);print(json.dumps(q));return root

def complete(name, explanation):
    initial=read(HERE/(name+'-queue.json'))
    q=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',initial['id']],text=True,encoding='utf-8'))
    assert q['state'] not in ('queued','running','cancel_requested'),q['state']
    save(HERE/(name+'-terminal.json'),q)
    output=ROOT/name/'output/result.json'
    passed=q['state']=='succeeded' and type(q['exit_status']) is int and q['exit_status']==0 and output.exists() and read(output).get('passed') is True
    refs=[ref('Terminal queue receipt',HERE/(name+'-terminal.json'))]
    if output.exists():refs.append(ref('Retained admission or preparation result',output))
    append('result',base()|dict(id='APARTMENT-s41-'+name+'-result',run_id='APARTMENT-s41-'+name,supersedes_result_id=None,execution_status='completed' if passed else 'failed',validity='valid' if passed else 'invalid',validity_reason=explanation,outcome='success' if passed else 'not_assessed',ended_at=q['ended_at'],termination_reason='Declared admission or preparation checks passed' if passed else 'Attempt failed; exact evidence retained',metrics=[],evidence=refs,details={'queue_id':q['id'],'exit_status':q['exit_status']}))
    print(json.dumps(dict(name=name,passed=passed,queue_state=q['state'])));return passed

def build():
    print(invoke('build'));print(invoke('validate','--output',str(MAP.parent/'validation.json')))
