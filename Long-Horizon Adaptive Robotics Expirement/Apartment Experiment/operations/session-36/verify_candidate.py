"""Fixed prospective physics/real-control verification. Failures are retained."""
import hashlib
import json
import math
from pathlib import Path
import traceback
import mujoco
import numpy as np
from physics_matrix import simulate

HERE=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_bytes())
def save(p,d):p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def main():
 manifest=read(HERE/'manifest.json')
 for n,v in manifest['files'].items():assert hashlib.sha256((HERE/n).read_bytes()).hexdigest()==v['sha256'],n
 out=HERE/'output';out.mkdir(exist_ok=False)
 source=dict(np.load(HERE/'initial.npz'));results=[];checks={};errors=[]
 for case in manifest['cases']:
  try:
   r=simulate(case,source,out);a=np.load(out/(case['id']+'.npz'))['samples']
   late=a[:,0]>=case.get('seconds',120)-30
   gates=dict(finite=bool(np.all(np.isfinite(a))),no_engine_warnings=not any(r['warnings']),
    late_stopped=float(np.linalg.norm(a[late,8:11],axis=1).max())<.001,
    late_drift=float(np.linalg.norm(np.ptp(a[late,1:3],axis=0)))<.002,
    supported=.025<float(a[-1,3])<.065,
    no_unforced_energy_creation=r['energy_gain_max_J']<max(1e-5,.02*abs(float(a[0,14]+a[0,15])) if case.get('drop') else 1e-5),
    no_hidden_forces=not any(r['force_max_applied_passive_actuator_xfrc']),
    penetration_bound=r['min_contact_distance_m']>-.01)
   results.append(dict(id=case['id'],gates=gates,metrics=r));checks[case['id']]=all(gates.values())
  except Exception as e:
   checks[case['id']]=False;errors.append(dict(id=case['id'],error=repr(e),traceback=traceback.format_exc()))
 # These use the pre-existing private fixtures, ordinary gripper contacts and
 # physical controls. Fixture setup positions are never exported to Robot Codex.
 from reliability_engineering import geometry_fixture
 import engineering
 import throw_engineering
 for name,call in [('both_drawers_and_docks',lambda:geometry_fixture(out/'geometry')),
                   ('sensors_toy_grasp_continuation',lambda:engineering.run(out/'integrated')),
                   ('ball_throw_regression',lambda:throw_engineering.run(out/'throwing'))]:
  try:
   r=call();checks[name]=bool(r.get('passed')) if isinstance(r,dict) else bool(r)
  except Exception as e:
   checks[name]=False;errors.append(dict(id=name,error=repr(e),traceback=traceback.format_exc()))
  print(name,checks[name],flush=True)
 result=dict(passed=all(checks.values()),checks=checks,physics=results,errors=errors,
  official_launches=0,official_writes=0,model_calls=0,source_manifest_sha256=hashlib.sha256((HERE/'manifest.json').read_bytes()).hexdigest(),
  tolerances='Last 30 s: speed <1 mm/s and drift <2 mm; endpoint supported; <=10 uJ energy gain for floor starts, drops <=2% initial energy; penetration <10 mm; no engine warnings or uncommanded applied forces. Gates fixed before run.')
 save(out/'result.json',result);print(json.dumps({'passed':result['passed'],'checks':checks,'errors':errors}),flush=True)
 return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
