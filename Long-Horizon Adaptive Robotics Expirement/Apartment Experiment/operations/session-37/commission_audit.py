"""Independent source, numerical-output and preserved-history commissioning readback."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET
from fractions import Fraction
import math
import numpy as np

HERE=Path(__file__).resolve().parent
REPO=Path('C:/Users/cresp/Documents/Dandelion Engineering/LLMs in Robotics')
APP=REPO/'Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'
OPS=APP/'operations/session-37'
OLDOPS=APP/'operations/session-36'
ROOT=HERE.parent
PRIOR=Path('D:/Dandelion-Apartment-Experiment/engineering/cup-physics-session36')
PAIR=Path('D:/Dandelion-Apartment-Experiment/official/apartment-v2')
QUEUE=REPO.parent/'tools/compute_queue/compute_queue.py'
def read(p):return json.loads(p.read_bytes())
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,d):p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def module(p,n):
 spec=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def main():
 out=HERE/'output';out.mkdir(exist_ok=False);result=dict(passed=False,checks={})
 try:
  for n,v in read(HERE/'manifest.json')['files'].items():assert sha(HERE/n)==v['sha256']
  for name in ['matrix001','matrix002','history001','history002','verification001']:
   q=read(OLDOPS/(name+'-queue.json'))
   q=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',q['id']],text=True,encoding='utf-8'))
   save(out/(name+'-queue.json'),q)
   assert q['state']=='succeeded' and type(q['exit_status']) is int and q['exit_status']==0,name
   manifest=read(PRIOR/name/'manifest.json')
   for f,v in manifest['files'].items():assert sha(PRIOR/name/f)==v['sha256'],(name,f)
  result['checks']['five_completed_immutable_attempts']=True
  old_failed=read(OLDOPS/'commissioning001-terminal.json')
  assert old_failed['state']=='failed' and type(old_failed['exit_status']) is int and old_failed['exit_status']==1
  failed=read(PRIOR/'commissioning001/output/result.json');assert failed['passed'] is False
  for ref in read(OLDOPS/'map-APARTMENT-cup-commissioning001-result.json')['evidence']:
   assert sha(Path(ref['uri']))==ref['sha256']
  result['checks']['previous_failed_commissioning_preserved_as_failed']=True
  for name in ['recorder001','verification001']:
   q=read(OPS/(name+'-queue.json'))
   q=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',q['id']],text=True,encoding='utf-8'))
   save(out/('s37-'+name+'-queue.json'),q)
   assert q['state']=='succeeded' and type(q['exit_status']) is int and q['exit_status']==0,name
   for f,v in read(ROOT/name/'manifest.json')['files'].items():assert sha(ROOT/name/f)==v['sha256'],(name,f)
  recorder=read(ROOT/'recorder001/output/result.json');assert recorder['passed'] and len(recorder['checks'])==14 and all(recorder['checks'].values())
  result['checks']['new_recorder_and_physics_attempts_completed_immutable']=True
  vroot=ROOT/'verification001';v=read(vroot/'output/result.json');assert v['passed'] and len(v['checks'])==30 and all(v['checks'].values())
  cases=read(vroot/'manifest.json')['cases']
  assert cases[:-1]==read(PRIOR/'verification001/manifest.json')['cases']
  assert cases[-1]==dict(id='recorded_long_non_grid_sampling',seconds=7200,sample_interval=.037)
  numerical=[]
  for case in cases:
   z=np.load(vroot/'output'/(case['id']+'.npz'));a=z['samples'];late=a[:,0]>=case.get('seconds',120)-30
   metrics=read(vroot/'output'/(case['id']+'.json'));recording=metrics['recording']
   steps=z['sample_steps'];dt=Fraction(str(recording['timestep_seconds']));interval=Fraction(str(case.get('sample_interval',.04)))
   n=math.ceil(Fraction(str(case.get('seconds',120)))/dt);ratio=interval/dt
   slots=np.arange(1,math.floor(n*dt/interval)+1,dtype=np.int64)
   expected=np.unique(np.concatenate(([0],(slots*ratio.numerator+ratio.denominator-1)//ratio.denominator,[n])))
   assert np.array_equal(steps,expected) and np.all(np.diff(steps)>0)
   assert np.all(np.diff(a[:,0])>0) and np.max(np.abs(a[:,0]-steps*float(dt)))<1e-5
   assert recording['integration_steps']==recording['planned_integration_steps']==n==int(steps[-1])
   assert a[-1,0]==float(z['terminal_time'])==recording['terminal_simulation_time']
   assert np.array_equal(a[-1,1:8],z['terminal_qpos']) and np.array_equal(a[-1,8:14],z['terminal_qvel'])
   assert sum(bool(f&2) for f in z['sample_flags'])==1 and (z['sample_flags'][-1]&2)
   energy=a[:,14]+a[:,15];gain=float(np.max(energy-energy[0]));drift=float(np.linalg.norm(np.ptp(a[late,1:3],axis=0)))
   assert abs(a[-1,0]-case.get('seconds',120))<1e-5
   assert np.isfinite(a).all() and drift<.002 and np.linalg.norm(a[late,8:11],axis=1).max()<.001
   assert gain<max(1e-5,.02*abs(float(energy[0])) if case.get('drop') else 1e-5)
   numerical.append(dict(case=case['id'],seconds=float(a[-1,0]),integration_steps=n,samples=len(a),terminal_flags=int(z['sample_flags'][-1]),max_energy_gain_J=gain,late_drift_m=drift))
  for p in [vroot/'output/geometry/geometry.json',vroot/'output/integrated/result.json',vroot/'output/throwing/result.json']:
   r=read(p);assert r['passed'] and all(r['checks'].values())
  save(out/'independent-numerical-readback.json',numerical)
  result['checks']['fixed_physics_and_integrated_verification']=True
  result['checks']['actual_terminal_state_and_exact_step_accounting']=True
  sys.path.insert(0,str(APP))
  from run import source_identity
  from environment import identity
  from revision_config import CONFIG
  current=source_identity();old=read(PAIR/'frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/commissioning.json')
  for mode in ['live','offline']:
   inherited=PAIR.parents[1]/'engineering'/old[mode+'_run']
   inherited_result=inherited/'output/result.json'
   assert sha(inherited_result)==old[mode+'_result_sha256']
   inherited_output=read(inherited_result);assert inherited_output['passed'] is True and all(inherited_output['checks'].values())
   prior_status=read(inherited/'queue-status.json')
   actual_status=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',prior_status['id']],text=True,encoding='utf-8'))
   assert actual_status['state']=='succeeded' and type(actual_status['exit_status']) is int and actual_status['exit_status']==0
   save(out/('inherited-'+mode+'-queue.json'),actual_status)
  result['checks']['inherited_live_and_offline_qualification_authenticated']=True
  assert current.keys()==old['source_identity'].keys()
  differences=[k for k in current if current[k]!=old['source_identity'][k]]
  assert differences==['apartment/scene.py'],differences
  for p in vroot.glob('*.py'):
   if p.name not in ['verify_candidate.py','physics_matrix.py','endpoint_schedule.py']:
    assert sha(p)==sha(APP/p.name),p.name
  a=ET.fromstring(module(PAIR/'frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/scene.py','old_scene').xml())
  b=ET.fromstring(module(APP/'scene.py','new_scene').xml())
  assert b.find('option').attrib.pop('ccd_tolerance')=='1e-10'
  assert b.find(".//geom[@name='cup_geom']").attrib.pop('condim')=='6'
  assert ET.tostring(a)==ET.tostring(b)
  env=identity();assert env==old['environment'],{'expected':old['environment'],'actual':env}
  assert current==read(vroot/'manifest.json')['apparatus_source_identity']
  assert env==read(vroot/'manifest.json')['environment']
  assert CONFIG==old['config']
  result['checks']['only_two_physics_attributes_changed']=True
  result['checks']['qualified_native_runtime_and_configuration_unchanged']=True
  frozen=PAIR/'frozen_repository'
  for n,v in read(frozen/'source-manifest.json').items():assert sha(frozen/n)==v['sha256'],n
  files=read(PRIOR/'history001/output/protected-v2-files.json')
  before={r['path']:r for r in files}
  actual=set(str(p) for c in ['baseline','maps'] for p in (PAIR/c).rglob('*') if p.is_file())
  assert actual==set(before)
  for r in files:
   p=Path(r['path']);assert p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],str(p)
  for n,v in read(OLDOPS/'protected-anchors.json').items():assert sha(Path(n))==v['sha256'],n
  result['checks']['original_histories_and_frozen_sources_unchanged']=True
  publication=read(OPS/'publication-pushed.json');assert publication['passed'] and publication['same_corpus_as_independently_verified_git_tree']
  assert not any(k.startswith('apartment/evidence/') or 'original-v2-filesystems' in k for k in current)
  result['checks']['original_filesystems_published_before_recommissioning_and_excluded_from_guest_inputs']=True
  certificate=dict(schema='apartment-commissioning-physics-1',passed=True,source_identity=current,environment=env,config=CONFIG,
   previous_certificate_sha256=sha(frozen/'Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/commissioning.json'),
   source_differences=differences,protocol_sha256={n:sha(APP/n) for n in ['COMPARISON.md','ANALYSIS.md','CUP-PHYSICS-REVISION.md']},
   qualification_composition='Only scene.py changes from v2: two MJCF attributes. Session 37 verifies 14 recorder gates, repeats all 29 earlier physics/integrated groups with actual terminal-state retention, and adds a 7200-second non-grid-sampling case. Independent numerical/step readback, source/environment/config and complete original preservation all pass. All inherited native, transport, filesystem, recovery, model and template source identities and installed binaries remain exactly those previously live-qualified; native namespace canaries still run before every official model turn. No new native model pilot is claimed.',
   physics_attempt=str(vroot),physics_result_sha256=sha(vroot/'output/result.json'),
   prior_live_run=old['live_run'],prior_live_result_sha256=old['live_result_sha256'],
   scope='Pristine matched v3 pair; original v2 and v1 histories preserved, no prior learning.')
  save(out/'certificate.json',certificate)
  result.update(passed=True,certificate=certificate,protected_files=len(files),numerical_cases=len(numerical),new_native_calls=0)
 except BaseException as e:result.update(error=repr(e),traceback=traceback.format_exc())
 save(out/'result.json',result);print(json.dumps({k:v for k,v in result.items() if k!='certificate'}),flush=True)
 return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
