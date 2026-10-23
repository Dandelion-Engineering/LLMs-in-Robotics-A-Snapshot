"""Immutable Session 37 diagnostics, append-only map registration, shared queue."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
APP=HERE.parents[1]
REPO=HERE.parents[3]
ROOT=Path('D:/Dandelion-Apartment-Experiment/engineering/physics-recommission-session37')
PRIOR=Path('D:/Dandelion-Apartment-Experiment/engineering/cup-physics-session36')
PAIR=Path('D:/Dandelion-Apartment-Experiment/official/apartment-v2')
MAP=REPO/'Long-Horizon Adaptive Robotics Expirement/Architecture Map/map.py'
QUEUE=REPO.parent/'tools/compute_queue/compute_queue.py'
def read(p):return json.loads(p.read_bytes())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,d):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(d,f,indent=2,allow_nan=False);f.write('\n')
def invoke(*a):return subprocess.check_output([sys.executable,'-X','utf8','-B',str(MAP),*a],text=True,encoding='utf-8')
def ref(label,p):return dict(label=label,uri=str(p),sha256=sha(p),state='available',access='operator',locator=None)
def base():return dict(schema_version='architecture-map-1.0',recorded_at=datetime.now(timezone.utc).isoformat(),author='Codex session 37',tags=['apartment','cup','physics','endpoint-recording','engineering'],details={})
def append(kind,d):
    p=HERE/('map-'+d['id']+'.json');save(p,d)
    print(invoke('append',kind,'--input',str(p),'--expected-sha256',json.loads(invoke('status','--json'))['store_sha256']))
def register(name,script,purpose,cases,files,rerun=None):
    root=ROOT/name;root.mkdir(parents=True,exist_ok=False)
    for source,dest in [(HERE/script,script)]+files:
        assert not (root/dest).exists(),dest
        shutil.copyfile(source,root/dest)
    sys.path.insert(0,str(APP))
    from environment import identity
    from run import source_identity
    manifest=dict(id='APARTMENT-s37-'+name,purpose=purpose,cases=cases,
        created_at=datetime.now(timezone.utc).isoformat(),environment=identity(),apparatus_source_identity=source_identity(),
        files={p.name:dict(sha256=sha(p),bytes=p.stat().st_size) for p in root.iterdir()},
        official_writes=False,model_calls=False,stop_on_failed_gate=True,rerun_of=rerun,
        authority=ref('Randy ordered authorization',HERE/'authority-original.md'))
    save(root/'manifest.json',manifest)
    ident=manifest['id'];rid=ident+'-revision';fref=ref('Frozen diagnostic manifest',root/'manifest.json')
    append('revision',base()|dict(id=rid,architecture_id='APARTMENT-001',parent_revision_id='APARTMENT-cup-verification001-revision',status='implemented',title='Session 37 '+name,summary=purpose,mechanism=purpose+' Diagnostic sampling only is revised; the two-attribute cup candidate and all inherited native/task/sensor/template/runtime code remain unchanged. Original experiments and failed Session 36 audit stay immutable.',attachments=[],details={'manifest':fref}))
    known=dict(state='recorded',refs=[fref],reason=None);none=dict(state='none',refs=[],reason='No stochastic selection or model invocation by this diagnostic')
    append('run',base()|dict(id=ident,revision_id=rid,stage='diagnostic',condition_id='isolated-engineering',protocol_id=ident,scenario_id='fixed-cup-and-recorder',paired_block_id='original-v2-candidate',replicate=1,started_at=None,rerun_of_run_id=rerun,condition_details={'purpose':purpose},seeds=none,frozen_refs={k:known for k in ['code','environment','protocol','scenario']}|{'models':none},evidence=[fref]))
    q=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'submit','--project','LLMs-in-Robotics','--cwd',str(root),'--',sys.executable,'-X','utf8','-B',str(root/script)],text=True,encoding='utf-8'))
    save(HERE/(name+'-queue.json'),q);print(json.dumps(q));return root
def complete(name,interpretation):
    initial=read(HERE/(name+'-queue.json'))
    q=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',initial['id']],text=True,encoding='utf-8'))
    assert q['state'] not in ('queued','running','cancel_requested')
    save(HERE/(name+'-terminal.json'),q)
    result=ROOT/name/'output/result.json'
    passed=q['state']=='succeeded' and type(q['exit_status']) is int and q['exit_status']==0 and result.exists() and read(result).get('passed') is True
    refs=[ref('Terminal queue receipt',HERE/(name+'-terminal.json'))]
    if result.exists():refs.append(ref('Retained diagnostic outcome',result))
    append('result',base()|dict(id='APARTMENT-s37-'+name+'-result',run_id='APARTMENT-s37-'+name,supersedes_result_id=None,execution_status='completed' if passed else 'failed',validity='valid' if passed else 'invalid',validity_reason=interpretation,outcome='success' if passed else 'not_assessed',ended_at=q['ended_at'],termination_reason='All fixed diagnostic gates passed' if passed else 'Required gate failed; stop and preserve attempt',metrics=[],evidence=refs,details={'queue_id':q['id'],'exit_status':q['exit_status']}))
    return passed
def build():print(invoke('build'));print(invoke('validate','--output',str(MAP.parent/'validation.json')))
