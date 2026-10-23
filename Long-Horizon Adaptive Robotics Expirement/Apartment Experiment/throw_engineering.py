"""PRIVATE actuator/physics feasibility. Never mounted in a robot filesystem.

These bounded sanity trials do not evaluate whether Robot Codex learns a throw.
Their parameters, trajectories and results are withheld from both clean starts.
"""
import argparse
from pathlib import Path
import traceback
import numpy as np
from common import save,canonical
from world import World
from engineering import move,relocate_for_fixture

def run(out):
    out.mkdir(parents=True,exist_ok=False)
    result=dict(passed=False,stage='private-throw-feasibility',checks={},trials=[],official_sessions=0,model_calls=0)
    w=None
    try:
        for duration in (.12,.20,.32,.50):
            for lateral in (0.,.12):
                w=World();w.setup_assignment(dict(kind='throwing',position=0,drawer='A',sensor_seed=20,toys=[]))
                relocate_for_fixture(w,2.3,1.4)
                start=w.time
                move(w,'position_grasp',x=.7,y=0,z=.945)
                move(w,'gripper',width=.055)
                move(w,'arm',x=.7,y=0,z=1.22)
                secure=bool(w.pickups['ball'])
                move(w,'arm',x=.30,y=0,z=1.0)
                command=dict(kind='trajectory',request_id='private-trial',parameters=dict(points=[
                    dict(x=.75,y=lateral,z=1.32,width=.055,duration=duration),
                    dict(x=1.03,y=lateral,z=1.35,width=.15,duration=.07)]))
                w.command(command)
                trajectory=[]
                for k in range(1250):
                    w.step()
                    if k%5==0:
                        j=w.model.joint('ball_free').dofadr[0]
                        trajectory.append([w.time,*w.body('ball').tolist(),*w.data.qvel[j:j+3].tolist()])
                peak=max(x[1] for x in trajectory)
                feedback=w.throw_feedback
                before=w.sequence;move(w,'reset_object');reset=w.body('ball').copy()
                row=dict(duration=duration,lateral=lateral,secure_pickup=secure,forward_peak=peak,
                    clears_front=any(x[1]>=4.4 and x[3]>.44 for x in trajectory),feedback=feedback,
                    reset_near_pedestal=bool(np.linalg.norm(reset[:2]-[3,1.4])<.02),cycle_sim_s=w.time-start,
                    trajectory=trajectory)
                result['trials'].append(row)
                w.close();w=None
        result['checks']['all_contact_lifts']=all(t['secure_pickup'] for t in result['trials'])
        result['checks']['ballistic_reach']=any(t['clears_front'] and t['forward_peak']>=4.8 for t in result['trials'])
        result['checks']['controlled_outcomes']=max(t['forward_peak'] for t in result['trials'])-min(t['forward_peak'] for t in result['trials'])>.2
        result['checks']['all_landing_feedback']=all(t['feedback'] is not None for t in result['trials'])
        result['checks']['all_resets']=all(t['reset_near_pedestal'] for t in result['trials'])
        result['measurements']=dict(max_cycle_sim_s=max(t['cycle_sim_s'] for t in result['trials']),
            physically_inside=sum(bool(t['feedback'] and t['feedback']['inside_bin']) for t in result['trials']))
        result['passed']=all(result['checks'].values())
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
    finally:
        if w:w.close()
        save(out/'result.json',result)
    print(canonical({k:v for k,v in result.items() if k!='trials'}).decode());return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.output) else 1)
