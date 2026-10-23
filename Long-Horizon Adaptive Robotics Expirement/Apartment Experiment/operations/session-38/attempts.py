"""Once-only frozen engineering attempts; no experiment/model entry point."""
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
ROOT = Path('D:/Dandelion-Apartment-Experiment/engineering/workspace-session38')
MAP = REPO/'Long-Horizon Adaptive Robotics Expirement/Architecture Map/map.py'
QUEUE = REPO.parent/'tools/compute_queue/compute_queue.py'

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
    return dict(schema_version='architecture-map-1.0', recorded_at=datetime.now(timezone.utc).isoformat(), author='Codex session 38', tags=['apartment','workspace','startup','cleanup','engineering'], details={})
def append(kind, record):
    path=HERE/('map-'+record['id']+'.json');save(path,record)
    print(invoke('append',kind,'--input',str(path),'--expected-sha256',read_status()['store_sha256']))
def read_status(): return json.loads(invoke('status','--json'))

def register(name, entry, purpose, cases, prior=None):
    root=ROOT/name;root.mkdir(parents=True,exist_ok=False)
    (root/'source').mkdir()
    for path in APP.glob('*.py'): shutil.copyfile(path,root/'source'/path.name)
    save(root/'source/source-origin.json',dict(repository=str(REPO)))
    for path in HERE.glob('*.py'):
        if path.name!='attempts.py':shutil.copyfile(path,root/path.name)
    inherited=REPO/'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001'
    files={p.relative_to(root).as_posix():dict(sha256=sha(p),bytes=p.stat().st_size) for p in root.rglob('*') if p.is_file()}
    dependency={p.relative_to(REPO).as_posix():sha(p) for p in inherited.rglob('*.py') if not any(part in ('evidence','inspection','qualification','investigation') for part in p.parts)}
    manifest=dict(id='APARTMENT-s38-'+name, purpose=purpose, cases=cases, files=files, inherited_python=dependency,
        repository=str(REPO), python=sys.executable, python_version=sys.version, base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
        official_writes=False,model_calls=0, created_at=datetime.now(timezone.utc).isoformat(), rerun_of=prior,
        authority=ref('Randy focused engineering authorization',HERE/'authority-original.md'))
    save(root/'manifest.json',manifest)
    ident=manifest['id']; rid=ident+'-revision'; fref=ref('Immutable engineering manifest',root/'manifest.json')
    append('revision',base()|dict(id=rid,architecture_id='APARTMENT-001',parent_revision_id='APARTMENT-v3-cup-physics-frozen',status='implemented',title='Workspace engineering '+name,summary=purpose,mechanism=purpose+' Isolated workspace services only. No official condition, physics, scoring, sensors, model, guest template or recovery guard is changed by this attempt.',attachments=[],details={'manifest':fref}))
    known=dict(state='recorded',refs=[fref],reason=None);none=dict(state='none',refs=[],reason='Deterministic engineering only; no model or stochastic task')
    append('run',base()|dict(id=ident,revision_id=rid,stage='diagnostic',condition_id='isolated-workspace-engineering',protocol_id=ident,scenario_id='checkpoint14-filesystem-startup',paired_block_id='unpaired-engineering',replicate=1,started_at=None,rerun_of_run_id=prior,condition_details={'purpose':purpose},seeds=none,frozen_refs={k:known for k in ('code','environment','protocol','scenario')}|{'models':none},evidence=[fref]))
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
    if output.exists():
        shutil.copyfile(output,HERE/(name+'-result.json'));refs.append(ref('Retained engineering result',output))
    append('result',base()|dict(id='APARTMENT-s38-'+name+'-result',run_id='APARTMENT-s38-'+name,supersedes_result_id=None,execution_status='completed' if passed else 'failed',validity='valid' if passed else 'invalid',validity_reason=explanation,outcome='success' if passed else 'not_assessed',ended_at=q['ended_at'],termination_reason='Fixed engineering checks passed' if passed else 'Attempt failed; evidence retained',metrics=[],evidence=refs,details={'queue_id':q['id'],'exit_status':q['exit_status']}))
    print(json.dumps(dict(name=name,passed=passed,queue_state=q['state'])));return passed
