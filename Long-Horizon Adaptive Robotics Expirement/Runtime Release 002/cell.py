"""Physical Panda workcell. Candidate observations are estimated from RGB/depth.

The supervisor/evaluator owns this module. Never import it into a candidate.
No transport modifies object qpos or welds objects to the gripper.
"""
from __future__ import annotations
import colorsys
from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import mujoco
import numpy as np
from evaluator import IndependentEvaluator
from restart_physical_class import source_binding,seal_model
from actuation import AffineServoAdapter, ARM_OPERATIONS
from sensor_worker import SensorWorker, apply_readout_noise, camera_calibration, derive_detections

HERE = Path(__file__).resolve().parent
ZONES = {'fixture':(.57,0), 'inspection':(.34,.20),
         'parking1':(.34,.04), 'parking2':(.46,.12),
         'tray1':(.40,.33), 'tray2':(.61,.33), 'tray3':(.65,-.29),
         'quarantine':(.20,.29), 'insert_home_A':(.18,-.25), 'insert_home_B':(.18,-.34)}
PART_HALF = np.array([.021,.021,.018])
# Common observation posture selected by the preregistered 18-posture screen.
# This changes only the robot's initial/return setpoint, never an object pose.
HOME = np.array([.8,-.5,0,-2.2,0,1.7,.7854])
DT = .002
INSERT_TCP_OFFSET_M = .004  # Common unverified contact calibration; applies at grasp and release.
FIXTURE_JAW_SLOT_HALF_M = .020  # Public 40 mm access slots in the jaw-direction walls.
SETUP_RETURN_WAIT_S = 2.0
RECOVERY_DESTINATIONS = ('parking1','parking2','inspection','quarantine')
MAX_CARTESIAN_STEP_M = .01
IK_MAX_ITERATIONS = 480  # Fixed diagnostic003 budget; convergence tolerances unchanged.

def zone_half(name): return np.array([.092,.065]) if name.startswith('tray') else np.array([.053,.053])

def _sub(parent,tag,**attrs):
    return ET.SubElement(parent,tag,{k:str(v) for k,v in attrs.items()})

def build_scene(n=3, seed=0, layout_seed=None):
    """Generated geometry; Menagerie Panda rigid body/actuators preserved."""
    source = HERE/'vendor'/'panda'/'panda.xml'
    root = ET.parse(source).getroot()
    root.find('compiler').set('meshdir',str(source.parent/'assets'))
    root.find('option').set('timestep',str(DT))
    root.find('option').set('iterations','80')
    root.find('option').set('cone','elliptic')
    for key in root.findall('keyframe'):
        root.remove(key)
    visual = _sub(root,'visual')
    _sub(visual,'global',offwidth=640,offheight=480)
    _sub(visual,'headlight',ambient='.65 .65 .65',diffuse='.45 .45 .45',specular='0 0 0')
    world = root.find('worldbody')
    _sub(world,'geom',name='table',type='plane',size='1 1 .1',rgba='.24 .27 .30 1',friction='1 .01 .001')
    _sub(world,'camera',name='overhead',pos='.43 0 1.25',xyaxes='1 0 0 0 1 0',fovy='48')
    _sub(world,'camera',name='oblique',pos='1.05 -.85 .95',xyaxes='.80 .60 0 -.36 .48 .80',fovy='48')
    hand = root.find(".//body[@name='hand']")
    _sub(hand,'site',name='tcp',pos='0 0 .1034',size='.004',rgba='1 0 0 1')
    _sub(hand,'camera',name='wrist',pos='.06 0 .05',xyaxes='1 0 0 0 -1 0',fovy='70')
    # Pad friction is an explicit common calibration parameter, never a weld.
    for geom in root.findall('.//geom'):
        if geom.get('class','').startswith('fingertip_pad'):
            geom.set('friction','1.5 .02 .001')
    for name,(x,y) in ZONES.items():
        half=zone_half(name)
        _sub(world,'geom',name='zone_'+name,type='box',pos=f'{x} {y} -.001',size=f'{half[0]} {half[1]} .001',rgba='.36 .39 .41 1',contype='0',conaffinity='0')
        if name == 'fixture':
            # Retain the 12 mm containment walls, with jaw access at x in (-.020,.020).
            # Finger collision half-width <=10.502 mm plus 4 mm sensor uncertainty
            # leaves >=5.498 mm lateral allowance inside each 20 mm half-slot.
            edge_half=(.053-FIXTURE_JAW_SLOT_HALF_M)/2
            edge_center=(.053+FIXTURE_JAW_SLOT_HALF_M)/2
            walls=[(.049,0,.004,.053),(-.049,0,.004,.053)]
            walls.extend((dx,dy,edge_half,.004) for dx in (-edge_center,edge_center) for dy in (-.049,.049))
            for dx,dy,sx,sy in walls:
                _sub(world,'geom',name=f'fixture_wall_{dx}_{dy}',type='box',pos=f'{x+dx} {y+dy} .006',size=f'{sx} {sy} .006',rgba='.5 .5 .5 1')
    asset = root.find('asset')
    rng = np.random.default_rng(seed)
    layout_rng = np.random.default_rng(seed if layout_seed is None else layout_seed)
    registry = {}
    # Public identification palette; only rendered pixels establish presence.
    names = [f'{"A" if i%2==0 else "B"}{i+1}' for i in range(n)] + ['insert_A','insert_B']
    for i,name in enumerate(names):
        hue = ((i+.25)/len(names)+rng.uniform(-.004,.004))%1
        # Keep saturated pigments below clipping under the calibrated lights.
        color = colorsys.hsv_to_rgb(hue,.95,.35)
        rgb = ' '.join(str(v) for v in color)
        _sub(asset,'material',name='tagmat_'+name,rgba=rgb+' 1',emission='.7',specular='0',shininess='0')
        if name.startswith('insert'):
            x,y = ZONES['fixture'] if name=='insert_A' else ZONES['insert_home_B']
            half = [.025,.025,.008]
            z = .009
        else:
            row,col = divmod(i,3)
            x,y = .32 + .085*col, -.373 + .095*row
            x,y = x+layout_rng.uniform(-.003,.003),y+layout_rng.uniform(-.003,.003)
            half = PART_HALF
            z = .021
        body = _sub(world,'body',name=name,pos=f'{x} {y} {z}')
        _sub(body,'freejoint',name='free_'+name)
        size = ' '.join(map(str,half))
        mass=float(rng.uniform(.09,.11));friction=float(rng.uniform(1.1,1.3))
        _sub(body,'geom',name='part_'+name,type='box',size=size,mass=mass,rgba='.60 .61 .62 1',friction=f'{friction} .015 .001',condim='4')
        _sub(body,'geom',name='tag_'+name,type='box',size='.014 .014 .0003',pos=f'0 0 {half[2]+.0004}',material='tagmat_'+name,contype='0',conaffinity='0',mass='.0001')
        # Binary process mark: dark raw, white after a valid machine cycle.
        _sub(body,'geom',name='mark_'+name,type='box',size='.004 .014 .0003',pos=f'.018 0 {half[2]+.0004}',rgba='.03 .03 .03 1',contype='0',conaffinity='0',mass='.0001')
        registry[name]={'family':name[-1] if name.startswith('insert') else name[0], 'hue':hue,'half':list(map(float,half)),'kind':'insert' if name.startswith('insert') else 'part'}
    return ET.tostring(root,encoding='unicode'),registry

class Cell:
    def __init__(self,n=3,seed=0,noise_seed=0,layout_seed=None):
        self.evaluator=IndependentEvaluator()
        self._eval_order=None
        self._acceptance_open=False
        self.xml,self.registry=build_scene(n,seed,layout_seed)
        self.model=mujoco.MjModel.from_xml_string(self.xml)
        # Protected compile-site attestation. Missing evidence cannot admit
        # class transfer, but does not manufacture a physics task failure.
        self.restart_physical_seal=None;self.restart_physical_export_error=None
        try:
            self.restart_physical_seal=seal_model(self.model,self.xml,self.registry,source_binding(HERE,mujoco))
        except (ValueError,TypeError,KeyError,AttributeError,OSError) as error:
            self.restart_physical_export_error=str(error)
        self.arm_adapter=AffineServoAdapter.from_model(self.model)
        self.data=mujoco.MjData(self.model)
        self.ikdata=mujoco.MjData(self.model)
        self.planner=ThreadPoolExecutor(max_workers=1,thread_name_prefix='public-geometry-planner')
        self.plan_future=None
        self.pending_plan_generation=None
        self.direct_command=None
        self.direct_plan_future=None
        self.direct_plan_generation=None
        self.last_direct_admission=-float('inf')
        self.plan_generation=0
        self.noise_rng=np.random.default_rng(noise_seed)
        self.process_duration_s=float(np.random.default_rng(seed+1701).uniform(8.,10.))
        self.data.qpos[:7]=HOME
        self.data.qpos[7:9]=.04
        self.data.ctrl[:7]=HOME
        self.data.ctrl[7]=255
        mujoco.mj_forward(self.model,self.data)
        self.sensor_worker=SensorWorker(self.model,self.registry,ZONES,{name:zone_half(name) for name in ZONES})
        self.sensor_missed_captures=0
        self.sensor_completed_captures=0
        self.last_sensor_result=None
        self._setup_wait=None
        self.tcp=mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_SITE,'tcp')
        self.jacp=np.zeros((3,self.model.nv)); self.jacr=self.jacp.copy()
        self.part_ids=[k for k,v in self.registry.items() if v['kind']=='part']
        self.truth={name:{'recipe':None,'cycles':0,'inspection':None,'cycle_history':[],'inspection_history':[]} for name in self.part_ids}
        self.rework_part_id=None  # Protected scenario configuration, never a candidate observation.
        self.station={'busy':False,'ready':True,'fault':False,'cycle_id':0,'completed_cycle_id':None,'fixture_insert':'A','guard_closed':False,'clamped':False}
        self.cycle=None
        self.inspection=None
        self.inspection_due=None
        self.last_detections=[]
        self.last_rgb=None
        self.last_depth=None
        self.detection_time=0.
        self.motion=[]
        self.segment=None
        self.active_request=None
        self.lease_deadline=None
        self.feedback=[]
        self.events=[]
        self.contact_peak=0.
        self.collision_impulse=0.
        self.total_path=0.
        self.last_tcp=self.data.site_xpos[self.tcp].copy()

    def close(self):
        self.planner.shutdown(wait=True,cancel_futures=True)
        self.sensor_worker.close()

    def actual_pos(self,name):
        return self.data.xpos[mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_BODY,name)].copy()

    def _physical_zone(self,name,zone,tolerance=.039):
        pos=self.actual_pos(name)
        half=np.array(self.registry[name]['half'])
        body=mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_BODY,name)
        bounds=np.abs(self.data.xmat[body].reshape(3,3))@half
        xy=np.array(ZONES[zone])
        return bool(np.all(np.abs(pos[:2]-xy)+bounds[:2]<zone_half(zone)) and pos[2]<.07 and np.linalg.norm(self.data.cvel[body,3:])<.05)

    def _insert_overlaps_fixture(self,name):
        # Protected PLC occupancy interlock only. This Boolean is not a planner input.
        pos=self.actual_pos(name)
        body=mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_BODY,name)
        bounds=np.abs(self.data.xmat[body].reshape(3,3))@np.asarray(self.registry[name]['half'])
        return bool(np.all(np.abs(pos[:2]-ZONES['fixture'])<=zone_half('fixture')+bounds[:2])
                    and pos[2]+bounds[2]>=0. and pos[2]-bounds[2]<=.08)

    def _physical_insert_interlock(self,family):
        required='insert_'+family
        occupied=[name for name,tag in self.registry.items()
                  if tag['kind']=='insert' and self._insert_overlaps_fixture(name)]
        return occupied==[required] and self._physical_zone(required,'fixture')

    def truth_snapshot(self):
        return {'sim_time':float(self.data.time),'objects':{n:{'pos':self.actual_pos(n).tolist(),**self.truth.get(n,{})} for n in self.registry},'station':dict(self.station),'qpos':self.data.qpos.tolist(),'qvel':self.data.qvel.tolist(),'ctrl':self.data.ctrl.tolist()}

    def prepare_sensor(self):
        """Warm the renderer before episode timing; GL stays on its owner thread."""
        self.sensor_worker.prepare()

    def render(self,camera='overhead'):
        """Synchronous calibration/raw camera helper; not for timed physics."""
        if self.sensor_worker.busy:
            raise RuntimeError('sensor capture already pending; poll before synchronous render')
        self.sensor_worker.request(self.model,self.data,sequence=-1,camera=camera)
        result=self.sensor_worker.wait()
        return result.rgb,result.depth

    def sense(self):
        """Synchronous calibration convenience; production uses request/poll."""
        rgb,depth=self.render()
        rgb,depth=apply_readout_noise(rgb,depth,self.noise_rng.integers(-1,2,size=(1,1,3)),self.noise_rng.normal(0,.0005))
        calibration=camera_calibration(self.model,self.data)
        detections=derive_detections(rgb,depth,calibration,self.registry,ZONES,{name:zone_half(name) for name in ZONES})
        self.last_detections=detections;self.last_rgb=rgb;self.last_depth=depth
        self.detection_time=float(self.data.time)
        self.resume_setup_if_fresh()
        return detections,rgb,depth

    def request_sense(self,*,sequence,capture_wall_elapsed_s=None,rgb_path=None,depth_path=None):
        """One copied capture, or an explicit rejected nominal camera slot."""
        record={'sequence':sequence,'capture_sim_time_s':float(self.data.time),
                'capture_wall_elapsed_s':capture_wall_elapsed_s,'camera':'overhead'}
        if self.sensor_worker.busy:
            self.sensor_missed_captures+=1
            record.update(accepted=False,reason='previous sensor or evidence job still pending')
            self.events.append({'type':'sensor_capture_missed',**record,'sim_time':float(self.data.time)})
            return record
        self.sensor_worker.request(self.model,self.data,sequence=sequence,
            capture_wall_elapsed_s=capture_wall_elapsed_s,
            rgb_offset=self.noise_rng.integers(-1,2,size=(1,1,3)),
            depth_offset=float(self.noise_rng.normal(0,.0005)),rgb_path=rgb_path,depth_path=depth_path)
        record['accepted']=True
        return record

    def poll_sense(self):
        """Nonblocking application of a complete immutable sensor/evidence job."""
        result=self.sensor_worker.poll()
        if result is None:return None
        # An on-demand wrist/oblique result belongs to its requesting channel;
        # it must not silently replace the calibrated overhead tag service.
        if result.camera=='overhead':
            self.last_detections=result.detections
            self.last_rgb=result.rgb;self.last_depth=result.depth
            self.detection_time=result.capture_sim_time_s
            self.last_sensor_result=result
            self.sensor_completed_captures+=1
        return result

    def resume_setup_if_fresh(self):
        """Require a fresh public return-home witness before inserting the replacement."""
        waiting=getattr(self,'_setup_wait',None)
        if not waiting or not self.active_request:return False
        if self.active_request.get('request_id')!=waiting['request_id']:return False
        pending=self.active_request.get('setup_pending')
        returning=self.active_request.get('setup_returning')
        if not pending or not returning:
            self.finish('failed','setup lacks its old-insert return record');return False
        if self.data.time>=waiting['deadline_sim_s']:
            self.finish('failed','old insert return not established before observation deadline');return False
        age=self.data.time-self.detection_time
        if self.detection_time<waiting['capture_after_sim_s'] or not 0<=age<=.35:return False
        matches=[d for d in self.last_detections if d['id']==returning['id']]
        if not matches:return False  # Unseen is unknown; wait only to the fixed deadline.
        old=matches[0];home=returning['home'];pos=np.asarray(old.get('pos',[]),dtype=float)
        half=np.asarray(self.registry[returning['id']]['half']);uncertainty=old.get('uncertainty_m',.004)
        supported=(len(matches)==1 and old.get('kind')=='insert' and old.get('zone')==home
                   and pos.shape==(3,) and np.all(np.isfinite(pos))
                   and isinstance(uncertainty,(int,float)) and np.isfinite(uncertainty) and 0<=uncertainty<=.01)
        supported=(supported and np.all(np.abs(pos[:2]-ZONES[home])+half[:2]+uncertainty<=zone_half(home))
                   and abs(pos[2]-half[2])<=uncertainty+.003)
        if not supported:
            self.finish('failed','old insert is not freshly observed returned within its home bounds');return False
        if any(d['zone']=='fixture' and d['kind'] in ('part','insert') for d in self.last_detections):
            self.finish('failed','fixture is not observably empty after old-insert return');return False
        if float(sum(self.data.qpos[7:9]))<.065:return False
        self._setup_wait=None
        try:
            self.plan_transport(pending,'fixture')
            self.events.append({'type':'setup_return_observed','request_id':self.active_request['request_id'],
                                'old_insert_id':returning['id'],'home':home,'capture_sim_time_s':self.detection_time,
                                'sim_time':float(self.data.time),'basis':'fresh public image-derived position and measured open jaws',
                                'independent_physical_success':False})
            self.active_request.pop('setup_pending');self.active_request.pop('setup_returning')
            return True
        except ValueError as error:
            self.finish('failed',str(error));return False

    def public_packet(self,order,run_id,incarnation,sequence):
        detections=[{**d,'age_s':float(self.data.time)-self.detection_time} for d in self.last_detections]
        fixture=next((d['id'] for d in detections if d['zone']=='fixture' and d['kind']=='part'),None)
        insert=next((d['family'] for d in detections if d['zone']=='fixture' and d['kind']=='insert'),None)
        station={**self.station,'occupied_visible_id':fixture,'fixture_insert':insert}
        # Public installed insert comes from observed tag; no private inventory.
        tcp=self.data.site_xpos[self.tcp]
        holding=next((d['id'] for d in detections if np.linalg.norm(np.array(d['pos'])-tcp)<.055 and d['pos'][2]>.075),None)
        recent=self.feedback[-1] if self.feedback and self.data.time-self.feedback[-1]['sim_time']<=60. else None
        return {'run_id':run_id,'incarnation':incarnation,'sequence':sequence,'sim_time':float(self.data.time),'sim_tick':round(self.data.time/DT),'capture_sim_time_s':self.detection_time,'calibration_version':'B01-tag-rgbd-004','sensor_quality':{'source':'rendered_rgbd','depth_noise_sd_m':.0005,'rgb_channel_offset_DN':1,'missing_tags':'unobserved; not inferred absent'},'order':order,'process_contract':{'family_recipes':{'A':'A','B':'B'},'processed_mark_requires_eligible_cycle':True},'detections':detections,'station':station,'gripper':{'holding_visible_id':holding,'width':float(sum(self.data.qpos[7:9]))},'inspection':self.inspection,'joints':self.data.qpos[:7].tolist(),'joint_velocities':self.data.qvel[:7].tolist(),'commanded_efforts':self.data.actuator_force[:7].tolist(),'last_feedback':recent}

    @property
    def direct_control_active(self):
        return getattr(self,'direct_command',None) is not None

    def _planning_busy(self):
        return self.plan_future is not None or getattr(self,'direct_plan_future',None) is not None

    def public_arm_interfaces(self):
        return {'interfaces':self.arm_adapter.public_spec(),
                'resource':{'active_request_id':self.active_request.get('request_id') if self.active_request else None,
                            'direct_control_active':self.direct_control_active,'lease_deadline_s':self.lease_deadline}}

    def ik(self,xyz,initial=None,configuration=None):
        d=self.ikdata
        d.qpos[:]=self.data.qpos if configuration is None else configuration
        d.qpos[:7]=d.qpos[:7] if initial is None else initial
        target_rotation=np.diag([1.,-1.,-1.])
        for _ in range(IK_MAX_ITERATIONS):
            mujoco.mj_forward(self.model,d)
            current=d.site_xmat[self.tcp].reshape(3,3)
            # Spatial orientation error, sum of basis cross products.
            rot_error=.5*sum((np.cross(current[:,i],target_rotation[:,i]) for i in range(3)),start=np.zeros(3))
            pos_error=np.array(xyz)-d.site_xpos[self.tcp]
            if np.linalg.norm(pos_error)<.001 and np.linalg.norm(rot_error)<.01: return d.qpos[:7].copy()
            mujoco.mj_jacSite(self.model,d,self.jacp,self.jacr,self.tcp)
            jac=np.vstack((self.jacp[:,:7],self.jacr[:,:7]*.4))
            error=np.r_[pos_error,rot_error*.4]
            dq=jac.T@np.linalg.solve(jac@jac.T+np.eye(6)*.002,error)
            d.qpos[:7]+=np.clip(dq,-.15,.15)
            ranges=self.model.jnt_range[:7]
            d.qpos[:7]=np.clip(d.qpos[:7],ranges[:,0]+.015,ranges[:,1]-.015)
        raise ValueError(f'IK did not converge at {xyz}, error={pos_error}')

    def plan_transport(self,part_id,destination,objective=None):
        observed=next((d for d in self.last_detections if d['id']==part_id),None)
        if observed is None or self.data.time-self.detection_time>.35: raise ValueError('fresh visible part required')
        if destination not in ZONES: raise ValueError('unknown destination')
        if self.station['busy'] and (observed['zone']=='fixture' or destination=='fixture'):raise ValueError('machine guard interlock is closed')
        occupied=[d for d in self.last_detections if d['id']!=part_id and d['zone']==destination
                  and (d['kind']=='part' or (self.registry[part_id]['kind']=='insert' and d['kind']=='insert'))]
        if occupied and not destination.startswith('tray'): raise ValueError('destination occupied')
        obj=objective or {}
        clearance=float(obj.get('clearance',.16)); speed=float(obj.get('speed_scale',.8))
        if not np.isfinite(clearance) or not .08<=clearance<=.25 or not .3<=speed<=1: raise ValueError('invalid geometric objective')
        if obj.get('approach','vertical')!='vertical':raise ValueError('unsupported approach constraint')
        avoid=obj.get('avoid_zones',[])
        if not isinstance(avoid,list) or any(z not in ZONES for z in avoid):raise ValueError('unknown avoidance region')
        if self._planning_busy():raise ValueError('geometry planner busy')
        # Only public observations and fixed public geometry enter the planner.
        # Planning consumes real wall time while the protected physics keeps
        # advancing; the returned plan owns no actuator authority by itself.
        snapshot={'observed':copy.deepcopy(observed),'occupied':copy.deepcopy(occupied),
                  'configuration':self.data.qpos.copy(),'tcp':self.data.site_xpos[self.tcp].copy(),
                  'half':self.registry[part_id]['half'],'kind':self.registry[part_id]['kind'],
                  'destination':destination,'clearance':clearance,'speed':speed,'avoid':list(avoid)}
        generation=self.plan_generation
        self.pending_plan_generation=generation
        self.plan_future=self.planner.submit(self._plan_snapshot,snapshot,generation)

    def _plan_snapshot(self,snapshot,generation):
        observed=snapshot['observed'];occupied=snapshot['occupied'];destination=snapshot['destination']
        clearance=snapshot['clearance'];speed=snapshot['speed'];avoid=snapshot['avoid']
        configuration=snapshot['configuration']
        source=np.array(observed['pos']); source[2]=max(source[2],snapshot['half'][2])
        dest=np.r_[ZONES[destination],snapshot['half'][2]+.003]
        if destination.startswith('tray'):
            slots=[np.array(ZONES[destination])+[dx,dy] for dy in (-.028,.028) for dx in (-.055,0,.055)]
            free=[p for p in slots if not any(np.linalg.norm(p-np.array(d['pos'][:2]))<.043 for d in occupied)]
            if not free: raise ValueError('delivery tray full')
            dest[:2]=free[0]
        if destination=='fixture' and snapshot['kind']=='part': dest[2]+=.017
        if snapshot['kind']=='insert':
            # Same public grasp offset at both endpoints preserves the intended
            # body release height. Do not modify object state or infer a grasp.
            source[2]+=INSERT_TCP_OFFSET_M;dest[2]+=INSERT_TCP_OFFSET_M
        above=max(source[2],dest[2])+clearance
        tcp=snapshot['tcp']
        points=[(np.r_[tcp[:2],max(tcp[2],above)],255),
                (np.r_[source[:2],above],255),(source,255),(source,0),
                (np.r_[source[:2],above],0),(np.r_[dest[:2],above],0),
                (dest,0),(dest,255),(np.r_[dest[:2],above],255),
                (None,255)]  # Return to a calibrated clear-view rest posture.
        return generation,self._task_segments(configuration,tcp,points,speed,
                                               dwell_phases=(3,7),avoid=avoid)

    def _task_segments(self,configuration,tcp,points,speed,*,phase_offset=0,dwell_phases=(),avoid=()):
        """Continue public Cartesian waypoints without adding a dwell per subdivision.

        Joint interpolation between distant Cartesian endpoints bowed into the
        insert during the retained pickup failure. These bounded segments keep
        each intended straight leg close to its public path. They are not a
        collision-free or successful-grasp certificate.
        """
        q=configuration[:7].copy();position=np.asarray(tcp,dtype=float).copy();segments=[]
        for index,(point,grip) in enumerate(points):
            origin=position.copy()
            count=1 if point is None or index in dwell_phases else max(
                1,int(np.ceil(np.linalg.norm(np.asarray(point)-origin)/MAX_CARTESIAN_STEP_M)))
            phase_floor=.5 if index in dwell_phases else .65
            for substep in range(1,count+1):
                target=None if point is None else origin+(np.asarray(point)-origin)*substep/count
                if target is None:qnext=HOME.copy()
                elif index in dwell_phases:qnext=q.copy()
                else:qnext=self.ik(target,q,configuration)
                # Retain requested public exclusion-column checks on every
                # actual joint-interpolation segment, including the HOME leg.
                for fraction in (np.linspace(0,1,21) if avoid else []):
                    self.ikdata.qpos[:]=configuration
                    self.ikdata.qpos[:7]=q+(qnext-q)*fraction
                    mujoco.mj_forward(self.model,self.ikdata)
                    projected=self.ikdata.site_xpos[self.tcp,:2]
                    if any(np.all(np.abs(projected-ZONES[z])<zone_half(z)+.04) for z in avoid):
                        raise ValueError('planned path conflicts with requested avoidance constraint')
                duration=max(phase_floor/count,float(np.max(np.abs(qnext-q)))/.7)/speed
                segments.append({'q':qnext,'grip':grip,'duration':duration,'phase':phase_offset+index,
                                 'cartesian_target':None if target is None else target.copy()})
                q=qnext
            if point is not None:position=np.asarray(point,dtype=float).copy()
        return segments

    def plan_clear_view(self):
        """Candidate-requested empty-jaw lift and rest; no task completion claim."""
        if self.data.time-self.detection_time>.35:raise ValueError('fresh public view required')
        if float(sum(self.data.qpos[7:9]))<=.065:raise ValueError('clear view requires measured open jaws')
        tcp=self.data.site_xpos[self.tcp]
        if any(d['pos'][2]>.075 and np.linalg.norm(np.array(d['pos'])-tcp)<.055 for d in self.last_detections):
            raise ValueError('clear view requires no visibly held object')
        if self._planning_busy():raise ValueError('geometry planner busy')
        snapshot={'configuration':self.data.qpos.copy(),'tcp':tcp.copy()}
        self.pending_plan_generation=self.plan_generation
        self.plan_future=self.planner.submit(self._plan_clear_view_snapshot,snapshot,self.plan_generation)

    def _plan_clear_view_snapshot(self,snapshot,generation):
        configuration=snapshot['configuration'];tcp=snapshot['tcp']
        raised=tcp.copy();raised[2]=max(.18,float(tcp[2])+.16)
        return generation,self._task_segments(configuration,tcp,[(raised,255),(None,255)],.8,phase_offset=10)

    def plan_recover_held(self,destination):
        """Place a possible unknown payload without first opening the jaws.

        This common recovery motion makes no claim that an object is held or
        identifies it. It uses current robot telemetry, fresh public detections
        and the declared maximum payload height. Identity/outcome must be
        reobserved after release. No evaluator pose/contact/held-ID is read.
        """
        if destination not in RECOVERY_DESTINATIONS:raise ValueError('recovery requires a parking, inspection or quarantine pad')
        if self.data.time-self.detection_time>.35:raise ValueError('fresh public view required for recovery')
        width=float(sum(self.data.qpos[7:9]))
        if not np.isfinite(width) or not 0<=width<.065:raise ValueError('recovery requires jaws not fully open')
        grip=float(self.data.ctrl[7])
        if not np.isfinite(grip) or grip!=0.:raise ValueError('recovery requires an existing closing-grip command; await opening completion otherwise')
        tcp=self.data.site_xpos[self.tcp].copy()
        if self.station['busy'] and np.all(np.abs(tcp[:2]-ZONES['fixture'])<zone_half('fixture')+.05):
            raise ValueError('machine guard interlock is closed')
        # A visible tag moving with the tool is possible payload, not an
        # independent occupant. Missing tags never reveal hidden occupancy.
        occupied=[d for d in self.last_detections if d['zone']==destination
                  and not (d['pos'][2]>.075 and np.linalg.norm(np.array(d['pos'])-tcp)<.055)]
        if occupied:raise ValueError('recovery destination visibly occupied')
        if self._planning_busy():raise ValueError('geometry planner busy')
        snapshot={'configuration':self.data.qpos.copy(),'tcp':tcp,
                  'destination':destination,'grip':grip,
                  'release_height_m':float(max(PART_HALF[2],.008)+.003)}
        self.pending_plan_generation=self.plan_generation
        self.plan_future=self.planner.submit(self._plan_recovery_snapshot,snapshot,self.plan_generation)

    def _plan_recovery_snapshot(self,snapshot,generation):
        configuration=snapshot['configuration'];tcp=snapshot['tcp']
        dest=np.r_[ZONES[snapshot['destination']],snapshot['release_height_m']]
        above=max(float(tcp[2]),float(dest[2])+.16)
        grip=snapshot['grip']
        points=[(np.r_[tcp[:2],above],grip),(np.r_[dest[:2],above],grip),
                (dest,grip),(dest,255),(np.r_[dest[:2],above],255),(None,255)]
        return generation,self._task_segments(configuration,tcp,points,.8,phase_offset=20,dwell_phases=(3,))

    def _plan_cartesian_target(self,position,configuration,generation):
        # Same public numerical IK as task motions; no hidden collision query.
        return generation,self.ik(position,configuration[:7].copy(),configuration)

    def _prepare_arm_command(self,action):
        if self.data.time-getattr(self,'last_direct_admission',-float('inf'))<.01-1e-9:raise ValueError('direct command admission exceeds 100 Hz')
        if self.station['busy']:raise ValueError('direct arm command unavailable while machine guard is closed')
        if self._planning_busy():raise ValueError('geometry planner busy')
        command=self.arm_adapter.admit(copy.deepcopy(action),float(self.data.time),self.data.qpos[:7])
        if not self.arm_adapter.workspace_contains(self.data.site_xpos[self.tcp]):raise ValueError('tool outside public workspace; hold for recovery')
        return command

    def _begin_arm_command(self,command):
        self.direct_command=command
        self.last_direct_admission=float(self.data.time)
        self.lease_deadline=min(float(self.data.time)+2.,command['deadline'])
        self.active_request={**self.active_request,'start_time_s':command['start'],'deadline_s':command['deadline'],
                             'resource':'arm','adapter':'bounded-arm-adapters-1.0'}
        if command['mode']=='cartesian':
            self.direct_plan_generation=self.plan_generation
            self.direct_plan_future=self.planner.submit(self._plan_cartesian_target,command['values'].copy(),
                                                        self.data.qpos.copy(),self.plan_generation)
        self.events.append({'type':'direct_control_admitted','request_id':self.active_request['request_id'],
                            'mode':command['mode'],'start_time_s':command['start'],'deadline_s':command['deadline'],
                            'sim_time':float(self.data.time),'physical_outcome_verified':False})

    def submit(self,action):
        op=action.get('operation');request_id=action.get('request_id')
        if op=='cancel':
            if (self.active_request is None or action.get('target_request_id')!=self.active_request.get('request_id')
                    or action.get('incarnation')!=self.active_request.get('incarnation')):
                return {'status':'rejected','request_id':request_id,'reason':'cancellation target or authority mismatch'}
            target=self.active_request['request_id'];self.cancel('candidate cancellation acknowledged')
            self._record_feedback(request_id,'completed','cancellation boundary acknowledged',target_request_id=target)
            return {'status':'accepted','request_id':request_id}
        prepared=None
        if self.active_request is not None:
            if (op not in ARM_OPERATIONS or action.get('replace_request_id')!=self.active_request.get('request_id')
                    or action.get('incarnation')!=self.active_request.get('incarnation')):
                return {'status':'rejected','request_id':request_id,'reason':'arm resource busy'}
            try:prepared=self._prepare_arm_command(action)
            except ValueError as error:return {'status':'rejected','request_id':request_id,'reason':str(error)}
            self.cancel('explicit same-incarnation supersession acknowledged')
        op=action['operation']; request_id=action['request_id']
        part=action.get('part_id'); self.active_request=action
        self.lease_deadline=float(self.data.time)+2.
        try:
            if op in ARM_OPERATIONS:
                self._begin_arm_command(prepared or self._prepare_arm_command(action))
            elif op=='transport':
                self.plan_transport(part,action['destination'],action.get('objective'))
            elif op=='recover_held':
                self.plan_recover_held(action['destination'])
            elif op=='setup':
                if self.station['busy']:raise ValueError('machine guard interlock is closed')
                family=action['family']; insert='insert_'+family
                if any(d['kind']=='part' and d['zone']=='fixture' for d in self.last_detections): raise ValueError('fixture occupied')
                observed_inserts=[d for d in self.last_detections if d['kind']=='insert' and d['zone']=='fixture']
                if len(observed_inserts)>1:raise ValueError('multiple inserts visibly occupy fixture')
                current=observed_inserts[0] if observed_inserts else None
                if current and current['id']==insert: self.finish('completed','requested insert already visibly seated')
                elif current:
                    self.plan_transport(current['id'],'insert_home_'+current['family'])
                    self.active_request={**action,'setup_pending':insert,
                                         'setup_returning':{'id':current['id'],'home':'insert_home_'+current['family']}}
                else:
                    self.plan_transport(insert,'fixture')
            elif op=='cycle':
                if self.station['busy'] or self.station['fault']: raise ValueError('machine unavailable')
                if part not in self.truth or not self._physical_zone(part,'fixture'): raise ValueError('seating interlock not satisfied')
                family=self.registry[part]['family']
                if not self._physical_insert_interlock(family): raise ValueError('unique seated insert interlock not satisfied')
                if action['recipe']!=family: raise ValueError('recipe incompatible')
                prior=self.truth[part];rework_authorization=None
                if prior['cycles']:
                    inspection=prior['inspection_history'][-1] if prior['inspection_history'] else None
                    latest_cycle=prior['cycle_history'][-1]
                    if prior['cycles']>=2 or not inspection or inspection['status']!='rework' or inspection['cycle_id']!=latest_cycle['cycle_id'] or not latest_cycle['completed']:
                        raise ValueError('part not eligible for another cycle')
                    rework_authorization=inspection['inspection_id']
                self.station['cycle_id']+=1; self.station['busy']=True; self.station['ready']=False;self.station['guard_closed']=True;self.station['clamped']=True
                self.cycle={'part_id':part,'recipe':family,'due':float(self.data.time)+self.process_duration_s,'cycle_id':self.station['cycle_id']}
                self.truth[part]['cycle_history'].append({'cycle_id':self.station['cycle_id'],'part_id':part,'recipe':family,'accepted':True,'completed':False,'accepted_at':float(self.data.time)})
                if rework_authorization is not None:self.truth[part]['cycle_history'][-1]['rework_authorization_inspection_id']=rework_authorization
                self.truth[part]['inspection']=None
                self.finish('completed','cycle accepted',cycle_id=self.station['cycle_id'])
            elif op=='inspect':
                if part not in self.truth or not self._physical_zone(part,'inspection'): raise ValueError('inspection pad placement required')
                self.inspection_due={'part_id':part,'due':float(self.data.time)+2.,'request_id':request_id}
            elif op=='observe' and action.get('clear_view') is True:
                self.plan_clear_view()
            elif op in ('observe','wait','done','help'):
                self.finish('completed',op)
            else: raise ValueError('unknown operation')
            return {'status':'accepted','request_id':request_id}
        except (KeyError,ValueError) as e:
            self.active_request=None; self.motion=[]; self.segment=None;self.lease_deadline=None;self.direct_command=None
            return {'status':'rejected','request_id':request_id,'reason':str(e)}

    def _record_feedback(self,request_id,status,reason,**extra):
        event={'request_id':request_id,'status':status,'reason':reason,'sim_time':float(self.data.time),**extra}
        self.feedback.append(event); self.events.append({'type':'feedback',**event})

    def finish(self,status,reason,**extra):
        if self.active_request is None: return
        self._record_feedback(self.active_request['request_id'],status,reason,**extra)
        self._setup_wait=None
        self.active_request=None
        self.lease_deadline=None

    def renew_authority(self,order_version,incarnation):
        """Fixed executor renews only the same currently lawful operation."""
        if self.active_request and self.data.time-self.detection_time<=.35 and self.active_request.get('order_version')==order_version and self.active_request.get('incarnation')==incarnation:
            direct=getattr(self,'direct_command',None)
            self.lease_deadline=min(float(self.data.time)+2.,direct['deadline']) if direct else float(self.data.time)+2.
            return True
        return False

    def cancel(self,reason='incarnation revoked'):
        # Freeze an already dispatched task trajectory at its last issued native
        # position target. Resetting that target to measured q removed the servo
        # load offset and lowered a held part during calibration004's absence.
        # Direct effort/velocity/other adapters keep the measured-position stop;
        # an effort-equivalent control must never become a held position target.
        hold_task_target=getattr(self,'direct_command',None) is None and (self.segment is not None or bool(self.motion))
        self.plan_generation+=1
        self.motion=[];self.segment=None
        self.direct_command=None
        self._setup_wait=None
        timer=self.inspection_due
        self.inspection_due=None
        if timer is not None:
            self.events.append({'type':'inspection_cancelled','request_id':timer['request_id'],
                                'part_id':timer['part_id'],'reason':reason,'sim_time':float(self.data.time)})
            if not self.active_request or self.active_request['request_id']!=timer['request_id']:
                self._record_feedback(timer['request_id'],'cancelled',reason)
        if not hold_task_target:self.data.ctrl[:7]=self.data.qpos[:7]
        self.finish('cancelled',reason)

    def tick(self):
        direct_future=getattr(self,'direct_plan_future',None)
        if direct_future is not None and direct_future.done():
            self.direct_plan_future=None
            expected_direct_generation=self.direct_plan_generation;self.direct_plan_generation=None
            try:
                generation,target=direct_future.result()
                direct=getattr(self,'direct_command',None)
                if generation==self.plan_generation and direct and direct['mode']=='cartesian' and self.active_request is not None:
                    # Planning consumes authority time; never jump ahead to a
                    # target that would have been reached during planning.
                    direct['start']=max(float(self.data.time),direct['start'])
                    direct['points']=[(direct['start'],self.data.qpos[:7].copy()),(direct['end'],target)]
                    self.arm_adapter.validate_path(direct['points'])
                else:self.events.append({'type':'stale_plan_discarded','sim_time':float(self.data.time)})
            except Exception as exc:
                if expected_direct_generation==self.plan_generation and getattr(self,'direct_command',None) is not None:
                    self.cancel('Cartesian planning failed: '+str(exc))
        if self.plan_future is not None and self.plan_future.done():
            future=self.plan_future;self.plan_future=None
            expected_generation=self.pending_plan_generation;self.pending_plan_generation=None
            try:
                generation,segments=future.result()
                if generation==self.plan_generation and self.active_request is not None:
                    self.motion=segments;self.segment=None
                    self.events.append({'type':'trajectory_dispatched','request_id':self.active_request['request_id'],'sim_time':float(self.data.time)})
                else:self.events.append({'type':'stale_plan_discarded','sim_time':float(self.data.time)})
            except Exception as exc:
                if expected_generation==self.plan_generation:self.finish('failed','geometry planning failed: '+str(exc))
        direct=getattr(self,'direct_command',None)
        if direct is not None and self.active_request is not None:
            if self.data.time>=direct['end']:
                if direct['mode']=='cartesian' and not direct['points']:
                    self.cancel('Cartesian planning exhausted bounded command interval')
                else:
                    if direct['mode']=='effort':
                        self.data.ctrl[:7]=self.data.qpos[:7]
                    else:
                        # Retain the completed native position target. Replacing
                        # it with measured q would add another gravity-deflection
                        # error after every otherwise completed interval.
                        controls,_=self.arm_adapter.control(direct,direct['end'],self.data.qpos[:7],self.data.qvel[:7])
                        self.data.ctrl[:7]=controls
                    self.direct_command=None
                    self.finish('completed','bounded servo interval ended; physical outcome requires observation')
            elif not self.arm_adapter.workspace_contains(self.data.site_xpos[self.tcp]):
                self.cancel('public workspace boundary crossed; servo hold entered')
            elif direct['mode']!='cartesian' or direct['points']:
                controls,report=self.arm_adapter.control(direct,float(self.data.time),self.data.qpos[:7],self.data.qvel[:7])
                self.data.ctrl[:7]=controls
                if direct['gripper'] is not None and self.data.time>=direct['start']:self.data.ctrl[7]=direct['gripper']
                if report is not None and self.data.time-direct.get('last_report_s',-1.)>=.01-1e-9:
                    self.events.append({'type':'direct_control_limits','request_id':self.active_request['request_id'],
                                        'sim_time':float(self.data.time),'mode':direct['mode'],**report})
                    direct['last_report_s']=float(self.data.time)
        if self.active_request and self.lease_deadline is not None and self.data.time>=self.lease_deadline:
            self.cancel('bounded command authority expired')
        waiting=getattr(self,'_setup_wait',None)
        if (waiting and self.active_request and self.active_request['request_id']==waiting['request_id']
                and self.data.time>=waiting['deadline_sim_s']):
            self.finish('failed','old insert return not established before observation deadline')
        if self.motion or self.segment:
            if self.segment is None:
                self.segment=self.motion.pop(0)
                self.segment.update(start=float(self.data.time),q0=self.data.ctrl[:7].copy())
            s=self.segment
            u=np.clip((self.data.time-s['start'])/s['duration'],0,1)
            blend=u*u*u*(10+u*(-15+6*u))
            self.data.ctrl[:7]=s['q0']+(s['q']-s['q0'])*blend
            self.data.ctrl[7]=s['grip']
            if u>=1:
                self.segment=None
                if not self.motion:
                    pending=self.active_request.get('setup_pending') if self.active_request else None
                    if pending:
                        self._setup_wait={'request_id':self.active_request['request_id'],
                                          'capture_after_sim_s':float(self.data.time),
                                          'deadline_sim_s':float(self.data.time)+SETUP_RETURN_WAIT_S}
                        self.events.append({'type':'setup_waiting_for_fresh_capture',
                                            'request_id':self.active_request['request_id'],
                                            'sim_time':float(self.data.time)})
                    else:self.finish('completed','trajectory ended; physical outcome requires observation')
        mujoco.mj_step(self.model,self.data)
        if self.cycle and (not self._physical_zone(self.cycle['part_id'],'fixture') or not self._physical_insert_interlock(self.cycle['recipe'])):
            self.station.update(busy=False,ready=False,fault=True,guard_closed=False,clamped=False)
            self.truth[self.cycle['part_id']]['cycle_history'][-1].update(status='failed',failed_at=float(self.data.time))
            self.events.append({'type':'cycle_fault','cycle_id':self.cycle['cycle_id'],'reason':'seating or unique-insert interlock lost during accepted process','sim_time':float(self.data.time)})
            self.cycle=None
        position=self.data.site_xpos[self.tcp].copy()
        self.total_path+=float(np.linalg.norm(position-self.last_tcp));self.last_tcp=position
        for i in range(self.data.ncon):
            force=np.zeros(6);mujoco.mj_contactForce(self.model,self.data,i,force)
            self.contact_peak=max(self.contact_peak,float(np.linalg.norm(force[:3])))
            self.collision_impulse+=float(np.linalg.norm(force[:3]))*DT
        if self.cycle and self.data.time>=self.cycle['due']:
            c=self.cycle; record=self.truth[c['part_id']]
            if not self._physical_zone(c['part_id'],'fixture') or not self._physical_insert_interlock(c['recipe']):
                self.station.update(busy=False,ready=False,fault=True,guard_closed=False,clamped=False)
                record['cycle_history'][-1].update(status='failed',failed_at=float(self.data.time))
                self.events.append({'type':'cycle_fault','cycle_id':c['cycle_id'],'reason':'seating or unique-insert interlock lost during accepted process','sim_time':float(self.data.time)})
                self.cycle=None
                return
            record['recipe']=c['recipe'];record['cycles']+=1
            record['cycle_history'][-1].update(completed=True,completed_at=float(self.data.time))
            geom=self.model.geom('mark_'+c['part_id']).id
            self.model.geom_rgba[geom]=[1,1,1,1]
            self.station.update(busy=False,ready=True,completed_cycle_id=c['cycle_id'],guard_closed=False,clamped=False)
            self.events.append({'type':'cycle_complete','sim_time':float(self.data.time),'cycle_id':c['cycle_id']})
            self.cycle=None
        if self.inspection_due and self.data.time>=self.inspection_due['due']:
            timer=self.inspection_due
            self.inspection_due=None
            if not self.active_request or self.active_request['request_id']!=timer['request_id']:
                # A stale asynchronous completion cannot finish a replacement
                # command, remove its lease, or invent a new public inspection.
                self._record_feedback(timer['request_id'],'cancelled','inspection request no longer owns its resource')
            else:
                part=timer['part_id']
                status='pass' if self.truth[part]['recipe']==self.registry[part]['family'] and self._physical_zone(part,'inspection') else 'fail'
                if status=='pass' and part==self.rework_part_id and self.truth[part]['cycles']==1:status='rework'
                self.truth[part]['inspection']=status
                self.inspection={'part_id':part,'status':status,'inspection_id':timer['request_id']}
                cycles=self.truth[part]['cycle_history']
                self.truth[part]['inspection_history'].append({**self.inspection,'cycle_id':cycles[-1]['cycle_id'] if cycles else None,'observed_at':float(self.data.time)})
                self.finish('completed','inspection returned',inspection=self.inspection)
        # Once all terminal predicates might hold, inspect every physics tick
        # throughout the final dwell. A brief contact or boundary excursion must
        # not disappear between the supervisor's ordinary 10 Hz snapshots.
        evaluator=getattr(self,'evaluator',None)
        if evaluator is not None and evaluator._stable_since is not None and self._eval_order is not None:
            evaluator.evaluate_cell(self,self._eval_order,zones=ZONES,zone_half=zone_half,acceptance_open=self._acceptance_open)

    def outcome(self,order,acceptance_open=False):
        self._eval_order=copy.deepcopy(order)
        self._acceptance_open=acceptance_open
        return self.evaluator.evaluate_cell(self,order,zones=ZONES,zone_half=zone_half,acceptance_open=acceptance_open)


def calibration(output):
    """One true contact transport; measured errors decide readiness."""
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    cell=Cell(3,0)
    try:
        for _ in range(250):cell.tick()
        detections,rgb,depth=cell.sense()
        from png import write_png
        write_png(output/'initial.png',rgb)
        measured=[]
        for detection in detections:
            measured.append({'id':detection['id'],'error_m':float(np.linalg.norm(np.array(detection['pos'])-cell.actual_pos(detection['id']))),'observed':detection['pos'],'actual':cell.actual_pos(detection['id']).tolist()})
        response=cell.submit({'operation':'transport','part_id':'A1','destination':'inspection','request_id':'calibration-grasp-1','order_version':1,'incarnation':1})
        trace=[]
        for tick in range(12500):
            if tick%50==0:
                cell.sense();cell.renew_authority(1,1)
            cell.tick()
            if tick%50==0:trace.append({'time':float(cell.data.time),'tcp':cell.data.site_xpos[cell.tcp].tolist(),'part':cell.actual_pos('A1').tolist(),'q':cell.data.qpos[:7].tolist(),'finger':cell.data.qpos[7:9].tolist()})
            if not cell.active_request:break
        for _ in range(250):cell.tick()
        detections,rgb,depth=cell.sense();write_png(output/'final.png',rgb)
        result={'scope':'physical-contact calibration; not an architecture experiment','response':response,'feedback':cell.feedback,'perception':measured,'transport_in_zone':cell._physical_zone('A1','inspection'),'part_final':cell.actual_pos('A1').tolist(),'trace':trace,'contact_peak_N':cell.contact_peak,'xml_sha256':hashlib.sha256(cell.xml.encode()).hexdigest()}
        (output/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='trace'},indent=2))
        if not result['transport_in_zone']:raise SystemExit(2)
    finally:cell.close()

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--calibrate',required=True)
    calibration(parser.parse_args().calibrate)
