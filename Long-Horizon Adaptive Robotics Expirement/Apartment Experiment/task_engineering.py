"""Private physical task feasibility and calibration; no trajectory enters runtime files."""
import argparse
import math
from pathlib import Path
import time
import traceback
import numpy as np
from common import save,canonical
from engineering import move,relocate_for_fixture
from scene import TOYS
from world import World

def turn(w,yaw):
    delta=(yaw-w.base_pose()[2]+math.pi)%(2*math.pi)-math.pi
    if abs(delta)>.001:move(w,'base',turn=delta)

def travel(w,x,y):
    pose=w.base_pose();dx=x-pose[0];dy=y-pose[1];distance=math.hypot(dx,dy)
    if distance<.02:return
    turn(w,math.atan2(dy,dx))
    while distance>.02:
        move(w,'base',forward=min(1.3,distance));pose=w.base_pose();distance=math.hypot(x-pose[0],y-pose[1])
        if distance>15:raise ValueError('Navigation diverged')
        if abs(pose[0]-x)+abs(pose[1]-y)<.025:break
        # No hidden route planner. Every listed engineering waypoint is manually chosen free space.
        if w.time>4000:raise ValueError('Engineering navigation deadline')

def stow(w):
    high=max(.60,float(w.data.site('tcp').xpos[2]))
    move(w,'arm',x=.3,y=0,z=high)
    move(w,'arm',x=.3,y=0,z=.60)

def pickup(w,x,y,z,width=.0):
    move(w,'position_grasp',x=x,y=y,z=z)
    move(w,'gripper',width=width)
    move(w,'arm',x=x,y=y,z=min(z+.20,1.28))

def run(out):
    out.mkdir(parents=True,exist_ok=False);result=dict(passed=False,stage='private-task-engineering',checks={},measurements={},official_sessions=0)
    w=None
    try:
        w=World();w.setup_assignment(dict(kind='bedroom',position=0,sensor_seed=10,drawer='A',toys=[[2.7,6.1],[3.6,6.4],[4.5,6.1],[4.6,7.2]]))
        started=w.time
        # Arrival at the bedroom and four complete pick/carry/release cycles use real controls.
        stow(w);travel(w,3.7,3.1);travel(w,3.65,4.65);travel(w,3,5.75)
        for name,_,_ in TOYS:
            point=w.body(name).copy()
            if name=='red':travel(w,float(point[0]-.65),5.55)
            travel(w,float(point[0]-.65),float(point[1]));turn(w,0)
            # Navigation can make physical contact; locate again before choosing an approach.
            point=w.body(name).copy()
            pose=w.base_pose();delta=point[:2]-pose[:2];co,si=math.cos(pose[2]),math.sin(pose[2])
            pickup(w,float(co*delta[0]+si*delta[1]),float(-si*delta[0]+co*delta[1]),max(.055,float(point[2])),.045 if name=='red' else .0)
            save(out/('pickup-'+name+'.json'),dict(base=w.base_pose().tolist(),object=w.body(name).tolist(),tcp=w.data.site('tcp').xpos.tolist(),public=w.public_status(),target=w.target))
            result['checks']['pickup_'+name]=bool(w.pickups[name])
            if not w.pickups[name]:raise ValueError('No secure pickup for '+name)
            stow(w)
            if name=='red':travel(w,float(w.base_pose()[0]),5.55);travel(w,3.1,5.55);travel(w,3.1,7.3)
            travel(w,3.55,7.75);travel(w,3.82,8);turn(w,0)
            move(w,'arm',x=.98,y=0,z=.62);move(w,'gripper',width=.15);move(w,'wait',duration=1)
            result['measurements'][name+'_ending']=w.body(name).tolist();stow(w)
            result['checks'][name+'_contained']=bool(abs(w.body(name)[0]-4.8)<.49 and abs(w.body(name)[1]-8)<.34)
        result['checks']['bedroom_complete']=bool(w.evaluate());result['measurements']['bedroom_competent_sim_s']=w.time-started
        result['measurements']['bedroom_control_calls']=w.engineering_control_calls
        save(out/'bedroom.json',result)
        w.close();w=None
        for drawer in ('A','B'):
            w=World();w.setup_assignment(dict(kind='kitchen',position=0,sensor_seed=11,drawer=drawer,toys=[[2.7,6.1]]*4))
            y=1.4 if drawer=='A' else 3.15
            relocate_for_fixture(w,7.73,y-.65,math.pi/2);started=w.time
            # A physical force at the visible latch for B; no semantic unlock command exists.
            if drawer=='B':
                relocate_for_fixture(w,7.7,y+.26,0)
                move(w,'gripper',width=.07)
                move(w,'arm',x=.70,y=0,z=.91)
                result['checks']['latch_contact_releases']=bool(w.latch_released)
                stow(w);relocate_for_fixture(w,7.73,y-.65,math.pi/2)
            # Fingers close across the round handle cross-section; lateral arm motion pulls it.
            move(w,'position_grasp',x=.65,y=-.45,z=.78)
            move(w,'arm',x=.65,y=-.45,z=.78)
            move(w,'gripper',width=.0)
            save(out/('handle-'+drawer+'.json'),dict(drawer=w.body('drawer'+drawer).tolist(),tcp=w.data.site('tcp').xpos.tolist(),contacts=w.last_contacts))
            move(w,'arm',x=.65,y=.05,z=.78,duration=8)
            opening=float(w.data.qpos[w.model.joint('drawer'+drawer).qposadr[0]])
            result['measurements']['drawer_'+drawer+'_opening']=opening
            result['checks']['drawer_'+drawer+'_physical_pull']=opening>.32
            move(w,'gripper',width=.15);stow(w)
            # Counter access; set up the base only, then all cup manipulation uses real controls.
            relocate_for_fixture(w,9.9,2,0)
            pickup(w,.9,0,.941,.0)
            result['checks']['cup_pickup_'+drawer]=bool(w.pickups['cup'])
            stow(w);travel(w,9.85,2);travel(w,9.85,.5);travel(w,7.35,.5);travel(w,7.35,y);turn(w,0)
            drawer_pos=w.body('drawer'+drawer)
            move(w,'arm',x=.4,y=0,z=1.18)
            move(w,'arm',x=float(drawer_pos[0]-.14-w.base_pose()[0]),y=0,z=1.18)
            move(w,'gripper',width=.15);move(w,'wait',duration=2)
            result['checks']['kitchen_'+drawer+'_complete']=bool(w.evaluate())
            result['measurements']['kitchen_'+drawer+'_fixture_sim_s']=w.time-started
            result['measurements']['kitchen_'+drawer+'_control_calls']=w.engineering_control_calls
            result['measurements']['cup_'+drawer+'_ending']=w.body('cup').tolist()
            save(out/('kitchen-'+drawer+'.json'),result)
            w.close();w=None
        result['passed']=all(result['checks'].values())
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
    finally:
        if w:w.close()
        save(out/'result.json',result)
    print(canonical(result).decode());return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.output) else 1)
