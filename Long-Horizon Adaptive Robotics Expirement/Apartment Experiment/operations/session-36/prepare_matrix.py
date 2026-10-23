"""Freeze and preregister the specified isolated diagnostic before queue submission."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import numpy as np
import mujoco

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[3]
PAIR=Path('D:/Dandelion-Apartment-Experiment/official/apartment-v2')
OUT=Path('D:/Dandelion-Apartment-Experiment/engineering/cup-physics-session36/matrix001')
MAP=REPO/'Long-Horizon Adaptive Robotics Expirement/Architecture Map/map.py'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
def invoke(*a):return subprocess.check_output([sys.executable,'-X','utf8','-B',str(MAP),*a],text=True,encoding='utf-8')
def ref(label,p):return dict(label=label,uri=str(p),sha256=sha(p),state='available',access='operator',locator=None)
def append(kind,d):
 p=HERE/('map-'+d['id']+'.json');save(p,d)
 print(invoke('append',kind,'--input',str(p),'--expected-sha256',read_status()['store_sha256']))
def read_status():return json.loads(invoke('status','--json'))

OUT.mkdir(parents=True,exist_ok=False)
frozen=PAIR/'frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'
shutil.copyfile(frozen/'scene.py',OUT/'scene.py')
shutil.copyfile(HERE/'physics_matrix.py',OUT/'physics_matrix.py')
spec=importlib.util.spec_from_file_location('source_scene',OUT/'scene.py');scene=importlib.util.module_from_spec(spec);spec.loader.exec_module(scene)
m=mujoco.MjModel.from_xml_string(scene.xml())
row=next(r for r in read(PAIR/'maps/replay/index.json') if r['first']<=9316.4320000629<=r['last'])
p=PAIR/'maps/replay'/row['file'];assert sha(p)==row['sha256']
with np.load(p) as z:
 i=int(np.argmin(abs(z['t']-9316.432)))
 qa=int(m.joint('cup_free').qposadr[0]);va=int(m.joint('cup_free').dofadr[0])
 np.savez_compressed(OUT/'initial.npz',qpos=z['qpos'][i],qvel=z['qvel'][i],cup_qpos=z['qpos'][i,qa:qa+7],cup_qvel=z['qvel'][i,va:va+6],original_t=z['t'][i])
cases=[dict(id='original_full',full=True),dict(id='original_isolated'),dict(id='zero_velocity',zero_velocity=True),
 dict(id='plane',plane=True),dict(id='plane_zero',plane=True,zero_velocity=True),
 dict(id='condim6',cup={'condim':6}),dict(id='condim6_zero',cup={'condim':6},zero_velocity=True),
 dict(id='condim6_no_rolling',cup={'condim':6,'friction':'1 .02 0'}),
 dict(id='smaller_dt',option={'timestep':'.001'}),dict(id='more_solver',option={'iterations':200,'tolerance':'1e-12'}),
 dict(id='no_warmstart',disable_warmstart=True),dict(id='legacy_ccd',disable_nativeccd=True),
 dict(id='pyramidal',option={'cone':'pyramidal'}),dict(id='implicit',option={'integrator':'implicit'}),
 dict(id='symmetric_com',symmetric_inertia=True),dict(id='frictionless',cup={'condim':1})]
manifest=dict(id='APARTMENT-cup-matrix001',created_at=datetime.now(timezone.utc).isoformat(),
 purpose='Distinguish unforced contact energy source, integration, solver, support shape, friction and mass asymmetry using identical original recorded state',
 cases=cases,original_replay=ref('Original replay chunk',p),original_sample_t=9316.432,
 environment={'python':sys.version,'mujoco':mujoco.__version__,'numpy':np.__version__},
 files={p.name:dict(sha256=sha(p),bytes=p.stat().st_size) for p in OUT.iterdir() if p.is_file()})
save(OUT/'manifest.json',manifest)
base=dict(schema_version='architecture-map-1.0',recorded_at=datetime.now(timezone.utc).isoformat(),author='Codex session 36',tags=['apartment','cup','physics','diagnostic','isolated'],details={})
rid=manifest['id']+'-revision'
append('revision',base|dict(id=rid,architecture_id='APARTMENT-001',parent_revision_id='APARTMENT-v2-reliability-frozen',status='implemented',
 title='Cup causal physics matrix 001',summary=manifest['purpose'],mechanism='Offline MuJoCo model compiled from untouched frozen v2 scene. Independent copies of one recorded near-reversal floor-contact state are stepped without Robot Codex. Full scene and reduced cup/floor models are compared; one-factor options are frozen in the external manifest. Contact work and rigid kinetic/potential energy are recorded. This is engineering evidence only, not a new scientific condition.',attachments=[],details={'manifest':ref('Exact diagnostic source, cases and environment',OUT/'manifest.json')}))
recorded=lambda refs:dict(state='recorded',refs=refs,reason=None)
none=lambda why:dict(state='none',refs=[],reason=why)
append('run',base|dict(id=manifest['id'],revision_id=rid,stage='diagnostic',condition_id='isolated-engineering',protocol_id='cup-causal-matrix-001',scenario_id='recorded-floor-only-reversal-9316',paired_block_id='same-original-state',replicate=1,started_at=None,rerun_of_run_id=None,condition_details={'cases':cases,'seconds_each':120,'official_writes':False},seeds=none('Deterministic physical states; no randomized inputs or model call'),frozen_refs={k:recorded([ref('Frozen matrix manifest',OUT/'manifest.json')]) for k in ['code','environment','protocol','scenario']}|{'models':none('No language model')},evidence=[ref('Frozen diagnostic manifest',OUT/'manifest.json')]))
save(HERE/'matrix001.json',{'root':str(OUT),'manifest_sha256':sha(OUT/'manifest.json')})
print(invoke('build'));print(invoke('validate','--output',str(MAP.parent/'validation.json')))
cmd=[sys.executable,'-X','utf8','-B',str(REPO.parent/'tools/compute_queue/compute_queue.py'),'submit','--project','LLMs-in-Robotics','--cwd',str(OUT),'--',sys.executable,'-X','utf8','-B',str(OUT/'physics_matrix.py')]
q=json.loads(subprocess.check_output(cmd,text=True,encoding='utf-8'));save(HERE/'matrix001-queue.json',q);print(json.dumps(q))
