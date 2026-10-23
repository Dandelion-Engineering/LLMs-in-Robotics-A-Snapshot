"""Small, explicit registration/queue helper for immutable session-36 diagnostics."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[3]
PAIR=Path('D:/Dandelion-Apartment-Experiment/official/apartment-v2')
ROOT=Path('D:/Dandelion-Apartment-Experiment/engineering/cup-physics-session36')
MAP=REPO/'Long-Horizon Adaptive Robotics Expirement/Architecture Map/map.py'
QUEUE=REPO.parent/'tools/compute_queue/compute_queue.py'
def read(p):return json.loads(p.read_bytes())
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,d):p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def invoke(*a):return subprocess.check_output([sys.executable,'-X','utf8','-B',str(MAP),*a],text=True,encoding='utf-8')
def ref(label,p):return dict(label=label,uri=str(p),sha256=sha(p),state='available',access='operator',locator=None)
def append(kind,d):
 p=HERE/('map-'+d['id']+'.json')
 assert not p.exists();save(p,d)
 print(invoke('append',kind,'--input',str(p),'--expected-sha256',json.loads(invoke('status','--json'))['store_sha256']))
def base():return dict(schema_version='architecture-map-1.0',recorded_at=datetime.now(timezone.utc).isoformat(),author='Codex session 36',tags=['apartment','cup','physics','engineering'],details={})
def register(name,script,purpose,cases=None,extra_files=None):
 out=ROOT/name;out.mkdir(exist_ok=False)
 for source,dest in [(HERE/script,script),(PAIR/'frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/scene.py','scene.py')]+(extra_files or []):
  shutil.copyfile(source,out/dest)
 manifest=dict(id='APARTMENT-cup-'+name,created_at=datetime.now(timezone.utc).isoformat(),purpose=purpose,cases=cases,
  files={p.name:dict(sha256=sha(p),bytes=p.stat().st_size) for p in out.iterdir()},official_writes=False)
 save(out/'manifest.json',manifest)
 rid=manifest['id']+'-revision'
 append('revision',base()|dict(id=rid,architecture_id='APARTMENT-001',parent_revision_id='APARTMENT-v2-reliability-frozen',status='implemented',title='Cup engineering '+name,summary=purpose,mechanism=purpose+' Exact source and protocol are hash-bound in the external manifest. Original v2 conditions are read-only. No Robot Codex condition is launched by this diagnostic.',attachments=[],details={'manifest':ref('Frozen attempt',out/'manifest.json')}))
 recorded=dict(state='recorded',refs=[ref('Frozen attempt',out/'manifest.json')],reason=None)
 none=dict(state='none',refs=[],reason='No stochastic inputs or language model call')
 append('run',base()|dict(id=manifest['id'],revision_id=rid,stage='diagnostic',condition_id='isolated-engineering',protocol_id='cup-'+name,scenario_id='frozen-v2-cup',paired_block_id='same-original-lineage',replicate=1,started_at=None,rerun_of_run_id=None,condition_details={'purpose':purpose},seeds=none,frozen_refs={k:recorded for k in ['code','environment','protocol','scenario']}|{'models':none},evidence=[ref('Frozen attempt',out/'manifest.json')]))
 q=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'submit','--project','LLMs-in-Robotics','--cwd',str(out),'--',sys.executable,'-X','utf8','-B',str(out/script)],text=True,encoding='utf-8'))
 save(HERE/(name+'-queue.json'),q);print(json.dumps(q));return out
def complete(name,interpretation,validity='valid',outcome='not_assessed'):
 q0=read(HERE/(name+'-queue.json'))
 q=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',q0['id']],text=True,encoding='utf-8'))
 assert q['state'] not in ['running','queued']
 save(HERE/(name+'-terminal.json'),q)
 passed=q['state']=='succeeded' and type(q['exit_status']) is int and q['exit_status']==0
 refs=[ref('Terminal queue receipt',HERE/(name+'-terminal.json'))]
 p=ROOT/name/'output/result.json'
 if p.exists():refs.append(ref('Retained diagnostic output',p))
 append('result',base()|dict(id='APARTMENT-cup-'+name+'-result',run_id='APARTMENT-cup-'+name,supersedes_result_id=None,execution_status='completed' if passed else 'failed',validity=validity if passed else 'invalid',validity_reason=interpretation, outcome=outcome if passed else 'not_assessed',ended_at=q['ended_at'],termination_reason='Fixed diagnostic completed' if passed else str(q.get('error') or 'Nonzero exit'),metrics=[],evidence=refs,details={'queue_id':q['id'],'exit_status':q['exit_status']}))
def build():print(invoke('build'));print(invoke('validate','--output',str(MAP.parent/'validation.json')))
