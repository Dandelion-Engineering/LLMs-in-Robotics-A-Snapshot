"""Negative physical evaluation controls and public comparison-boundary checks."""
import argparse
import json
import math
from pathlib import Path
import traceback
import numpy as np
import mujoco
from common import REPO,save,canonical,inventory,sha
from deployment import instantiate
from world import World
from scene import TOYS
from schedule import build,validate
from engineering import move,relocate_for_fixture

def run(out):
    out.mkdir(parents=True,exist_ok=False);r=dict(passed=False,checks={},stage='private-negative-boundaries',official_sessions=0,model_calls=0);w=None
    try:
        w=World();w.setup_assignment(dict(kind='bedroom',position=0,sensor_seed=1,drawer='A',toys=[[2.7,6.1],[3.6,6.4],[4.5,6.1],[4.6,7.2]]))
        for i,(n,size,_) in enumerate(TOYS):w._object_set(n,[4.6+.13*i,8,.145+size[2]])
        w.step(300)
        r['checks']['unpicked_containment_rejected']=not w.evaluate()
        w.pickups.update({n:True for n,_,_ in TOYS});w.grip_candidate='yellow'
        r['checks']['still_held_toy_rejected']=not w.evaluate()
        w.setup_assignment(dict(kind='kitchen',position=0,sensor_seed=2,drawer='A',toys=[]))
        for n in ('A','B'):w.data.qpos[w.model.joint('drawer'+n).qposadr[0]]=.5
        w.latch_released=True;w._object_set('cup',[8.3,3.15,.69]);w.pickups['cup']=True;w.step(300)
        r['checks']['wrong_drawer_rejected']=not w.evaluate()
        w._object_set('cup',[8.3,1.4,.69]);w.pickups['cup']=False;w.step(300)
        r['checks']['unpicked_cup_rejected']=not w.evaluate()
        w.pickups['cup']=True;w.grip_candidate='cup'
        r['checks']['still_held_cup_rejected']=not w.evaluate()
        w.grip_candidate='ball'
        try:w.reset_throw()
        except ValueError:r['checks']['within_assignment_held_reset_rejected']=True
        else:r['checks']['within_assignment_held_reset_rejected']=False
        w.setup_assignment(dict(kind='throwing',position=1,sensor_seed=9,drawer='A',toys=[]))
        r['checks']['next_throw_assignment_resets_held_ball']=w.grip_candidate is None and np.allclose(w.body('ball'),[3,1.4,.96])
        w.close();w=None
        w=World();w.setup_assignment(dict(kind='kitchen',position=0,sensor_seed=3,drawer='B',toys=[]))
        relocate_for_fixture(w,7.73,3.15-.65,math.pi/2)
        move(w,'position_grasp',x=.65,y=-.45,z=.78);move(w,'gripper',width=0);move(w,'arm',x=.65,y=.05,z=.78,duration=8)
        r['checks']['unreleased_latch_blocks_pull']=not w.latch_released and float(w.data.qpos[w.model.joint('drawerB').qposadr[0]])<.005
        entry=w.capture();packet=w.sensor_packet(entry)
        expected={'sim_time','battery','assignment','task_success','action','last_action','odometry','imu','joint_encoders','gripper','throw_feedback','observation_sequence','camera','width','height','fovy_degrees','depth_m','depth_grid','lidar_m','lidar_angles','image_tool','noise'}
        r['checks']['public_packet_allowlist']=set(packet)==expected
        r['checks']['private_truth_excluded']=not any(k in json.dumps(packet) for k in ('cam_xpos','cam_xmat','geom_id','body_id','room_id','sensor_seed','schedule_sha256'))
        try:w.command(dict(kind='set_pose',parameters={'x':0},request_id='forbidden'))
        except ValueError:r['checks']['pose_edit_denied']=True
        else:r['checks']['pose_edit_denied']=False
        w.close();w=None
        one=World();two=World();one.begin_session(240,3600);two.begin_session(240,3600)
        two.command(dict(kind='base',parameters={'forward':.5},request_id='motion'))
        one.step(750);two.step(750)
        r['checks']['time_only_battery']=one.battery()==two.battery() and np.linalg.norm(one.base_pose()-two.base_pose())>.1
        one.close();two.close()
        for c in ('baseline','maps'):instantiate(c,out/c)
        a,b=inventory(out/'baseline'),inventory(out/'maps')
        # These map-specific differences are present in Randy's actual templates.
        allowed={'RobotAgentPrompt.md','README.md','LongTermMemory.md','SessionReports/SessionReportTemplate.md'}
        differences={p for p in set(a)|set(b) if a.get(p)!=b.get(p)}
        r['checks']['controlled_initial_difference']=all(p in allowed or p.startswith('Maps/') for p in differences)
        r['checks']['supplied_condition_bytes_preserved']=all(sha(out/c/name)==sha(REPO/template/name)
            for c,template in (('baseline','Robot Agent Filesystem Draft v0.2'),('maps','Robot Agent Filesystem Draft v0.2 Maps Edition'))
            for name in ('RobotAgentPrompt.md','LongTermMemory.md','SessionReports/SessionReportTemplate.md'))
        r['checks']['baseline_no_supplied_maps']=not (out/'baseline/Maps').exists()
        schedule=build(47110);validate(schedule)
        r['checks']['matched_full_schedule']=sum(x['drawer']=='A' for x in schedule['assignments'] if x['kind']=='kitchen')==3
        save(out/'difference.json',dict(paths=sorted(differences),baseline=a,maps=b))
        r['passed']=all(r['checks'].values())
    except BaseException as e:r.update(error=repr(e),traceback=traceback.format_exc())
    finally:
        if w:w.close()
        save(out/'result.json',r)
    print(canonical(r).decode());return r['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.output) else 1)
