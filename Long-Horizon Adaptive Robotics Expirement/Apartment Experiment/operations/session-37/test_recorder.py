"""Bounded real-physics and scheduling checks frozen before execution."""
from fractions import Fraction
import importlib.util
import json
import math
from pathlib import Path
import traceback
import hashlib
import numpy as np
from endpoint_schedule import Sampling
from physics_matrix import simulate

HERE=Path(__file__).resolve().parent
def save(p,d):p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def main():
    out=HERE/'output';out.mkdir(exist_ok=False);checks={};results=[];errors=[]
    try:
        manifest=json.loads((HERE/'manifest.json').read_bytes())
        for n,row in manifest['files'].items():assert hashlib.sha256((HERE/n).read_bytes()).hexdigest()==row['sha256'],n
        source=dict(np.load(HERE/'initial.npz'))
        for case in manifest['cases']:
            r=simulate(case,source,out);z=np.load(out/(case['id']+'.npz'));steps=z['sample_steps'];a=z['samples'];rec=r['recording']
            dt=rec['timestep_seconds'];duration=case['seconds'];interval=case.get('sample_interval',.04)
            n=math.ceil(Fraction(str(duration))/Fraction(str(dt)))
            expected=sorted({0,n}|{math.ceil(k*Fraction(str(interval))/Fraction(str(dt))) for k in range(1,math.floor(n*Fraction(str(dt))/Fraction(str(interval)))+1)})
            assert steps.tolist()==expected and len(steps)==len(set(steps.tolist()))
            assert n==rec['integration_steps'] and rec['terminal_simulation_time']==float(z['terminal_time'])==float(a[-1,0])
            assert abs(a[-1,0]-n*dt)<1e-10 and n*dt>=duration-1e-12 and n*dt-duration<dt+1e-12
            assert np.array_equal(a[-1,1:8],z['terminal_qpos']) and np.array_equal(a[-1,8:14],z['terminal_qvel'])
            assert (z['sample_flags'][-1]&2) and sum(bool(x&2) for x in z['sample_flags'])==1
            assert np.all(np.diff(a[:,0])>0) and np.all(np.diff(steps)>0)
            checks[case['id']]=True;results.append(r)
        # Full two-hour schedule for exact, non-grid and undersampled intervals,
        # independently derived using rational target times. Real long physics is next.
        for interval in (.04,.037,.003):
            schedule=Sampling(7200,.004,interval)
            actual=[i for i in range(schedule.steps+1) if schedule.retain(i)]
            ratio=Fraction(str(interval))/Fraction('.004')
            expected=sorted({0,schedule.steps}|{math.ceil(k*ratio) for k in range(1,math.floor(Fraction(7200)/Fraction(str(interval)))+1)})
            assert actual==expected and actual[-1]==1800000
            checks['two_hour_schedule_'+str(interval)]=True
        # Record-only change: bit-exact equality to the old real-physics samples
        # on a short aligned run, including the terminal state and work integral.
        spec=importlib.util.spec_from_file_location('legacy_matrix',HERE/'legacy_matrix.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
        oldout=out/'legacy';oldout.mkdir()
        case={'id':'legacy_equivalence','seconds':2.0}
        old.simulate(case,source,oldout);simulate(case,source,out)
        assert np.array_equal(np.load(oldout/'legacy_equivalence.npz')['samples'],np.load(out/'legacy_equivalence.npz')['samples'])
        checks['short_physics_bit_exact_against_legacy']=True
    except Exception as e:errors.append({'error':repr(e),'traceback':traceback.format_exc()})
    result={'passed':not errors and all(checks.values()),'checks':checks,'errors':errors,'real_cases':results,'model_calls':0,'official_writes':False}
    save(out/'result.json',result);print(json.dumps({k:v for k,v in result.items() if k!='real_cases'}),flush=True)
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
