"""Throwaway apparatus tests. Never opens or advances official condition state."""
import argparse
import json
from pathlib import Path
import time
import traceback
import numpy as np
from common import save, sha, canonical
from schedule import build, validate
from scene import TOYS, xml
from world import World

def move(w, kind, **parameters):
    w.engineering_control_calls=getattr(w,'engineering_control_calls',0)+1
    w.command(dict(request_id='engineering-'+str(w.time),kind=kind,parameters=parameters))
    limit=w.time+65
    while w.active and w.time<limit:w.step(10)
    assert not w.active, 'Action completion deadline'
    w.step(80)
    if w.last_action and w.last_action['status']=='blocked':raise ValueError('Physical action blocked: '+repr(w.last_action)+' at '+repr(w.base_pose().tolist()))

def relocate_for_fixture(w,x,y,yaw=0):
    """Protected fixture setup, never an available robot command."""
    for n,v in [('base_x',x-3),('base_y',y-2),('base_yaw',yaw)]:
        w.data.qpos[w.joints[n]]=v;w.target[n]=v
    w.data.qvel[:]=0
    w.step(100)

def run(out):
    out.mkdir(parents=True,exist_ok=False)
    result=dict(passed=False,stage='throwaway_engineering',official_sessions=0,checks={},measurements={})
    w=None
    try:
        start=time.perf_counter();w=World()
        result['checks']['startup']=bool(np.isfinite(w.data.qpos).all())
        schedule=build(70103);validate(schedule)
        result['checks']['schedule']=len(schedule['assignments'])==21
        save(out/'private-engineering-schedule.json',schedule)
        e=w.capture();(out/'head.png').write_bytes(e['rgb']);save(out/'packet.json',w.sensor_packet(e))
        result['checks']['camera']=len(e['rgb'])>1000 and e['depth'].shape==(360,480)
        packet=w.sensor_packet(e)
        result['checks']['no_semantic_metadata']=all(n not in json.dumps(packet) for n in ['room_id','object_pose','drawer_position','sensor_seed','toys'])
        # The word "toys" occurs legitimately in the current assignment only; no current assignment here.
        start_pose=w.base_pose().copy();move(w,'base',forward=.5)
        result['checks']['physical_base']=abs(w.base_pose()[0]-start_pose[0]-.5)<.03
        result['measurements']['base_displacement']=(w.base_pose()-start_pose).tolist()
        # Positive pickup control through finger contacts and actual lift, no weld or pose transfer.
        w.setup_assignment(dict(kind='bedroom',sensor_seed=3,toys=[[3.3,6],[4,6.5],[4.5,7],[3.5,7.5]],drawer='A'))
        relocate_for_fixture(w,2.7,6)
        red=w.body('red').copy();move(w,'position_grasp',x=.6,y=0,z=.055)
        move(w,'gripper',width=.045)
        save(out/'grasp-before-lift.json',dict(public=w.public_status(),red=w.body('red').tolist(),contacts=w.last_contacts,
          tcp=w.data.site('tcp').xpos.tolist(),target=w.target,all_contacts=[dict(a=w.model.geom(int(c.geom1)).name,b=w.model.geom(int(c.geom2)).name,dist=float(c.dist)) for c in w.data.contact]))
        move(w,'arm',x=.6,y=0,z=.25)
        result['checks']['contact_lift']=w.pickups['red'] and w.body('red')[2]>.15
        result['measurements']['red_lift_m']=float(w.body('red')[2]-red[2])
        e=w.capture('wrist_rgb');(out/'wrist.png').write_bytes(e['rgb'])
        # Detector must reject touching/moving without all four pickups inside chest.
        result['checks']['partial_cleanup_rejected']=not w.evaluate()
        # Exact integration-state and RNG resume comparison in a fresh model.
        saved=w.snapshot();save(out/'checkpoint-fixture.json',saved)
        clone=World();clone.restore(saved)
        before=np.max(np.abs(clone.data.qpos-w.data.qpos))
        for _ in range(50):w.step(10);clone.step(10)
        result['checks']['physics_resume']=before<1e-13 and np.max(np.abs(w.data.qpos-clone.data.qpos))<1e-10
        result['checks']['rng_resume']=np.array_equal(w.rng.random(8),clone.rng.random(8))
        clone.close()
        w.begin_session(2,1800);w.step(600)
        result['checks']['time_only_warning']=w.battery()['low_warning'] and w.battery()['return_seconds_remaining']>1799
        # Identical initial geometry is reconstructed from original procedural source.
        (out/'scene.xml').write_text(xml(),encoding='utf-8')
        result['measurements']['wall_s']=time.perf_counter()-start
        result['measurements']['sim_s']=w.time
        result['passed']=all(result['checks'].values())
    except BaseException as error:
        result.update(error=repr(error),traceback=traceback.format_exc())
    finally:
        if w:w.close()
        save(out/'result.json',result)
    print(canonical(result).decode())
    return result['passed']

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    raise SystemExit(0 if run(args.output) else 1)
