"""MuJoCo owner, sensor boundary and nonsemantic actuator controls."""
from __future__ import annotations
import base64
import json
import math
import struct
import zlib
import numpy as np
import mujoco
from scene import xml, TOYS, CHARGERS

JOINTS = ['base_x','base_y','base_yaw','head_pan','head_tilt','lift','reach','lateral','wrist_pitch','finger_left','finger_right']
OBJECTS = [x[0] for x in TOYS] + ['cup','ball']

def png(rgb):
    h,w,_ = rgb.shape
    def chunk(kind, raw):
        return struct.pack('>I',len(raw))+kind+raw+struct.pack('>I',zlib.crc32(kind+raw)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(b'\0'+r.tobytes() for r in rgb),3))+chunk(b'IEND',b'')

class World:
    def __init__(self, seed=1):
        self.model = mujoco.MjModel.from_xml_string(xml())
        self.data = mujoco.MjData(self.model)
        self.rng = np.random.default_rng(seed)
        self.joints = {n:self.model.joint(n).qposadr[0] for n in JOINTS}
        self.act = {n:self.model.actuator(n).id for n in JOINTS}
        self.target = dict(base_x=0.,base_y=0.,base_yaw=0.,head_pan=0.,head_tilt=.22,
                           lift=.35,reach=.36,lateral=0.,wrist_pitch=0.,finger_left=.07,finger_right=.07)
        for n,v in self.target.items():
            self.data.qpos[self.joints[n]]=v
            self.data.ctrl[self.act[n]]=v
        self.active = None
        self.last_action = None
        self.latch_released = False
        self.handle_grip = None
        self.pickups = {x:False for x in OBJECTS}
        self.grip_candidate = None
        self.renderer = None
        self.sequence = 0
        self.observations = {}
        self.assignment = None
        self.assignment_start = 0.
        self.session_start = 0.
        self.working_window = 120.
        self.reserve_window = 1800.
        self.docked = False
        self.throw_feedback = None
        self.throw_airborne = False
        self.throw_previous_z = None
        self.throw_rest_since = None
        self.odom = np.zeros(3)
        self.previous_base = self.base_pose()
        self.last_contacts = {}
        self.step(100)

    @property
    def time(self): return float(self.data.time)

    def base_pose(self):
        return np.array([3+self.data.qpos[self.joints['base_x']],2+self.data.qpos[self.joints['base_y']],self.data.qpos[self.joints['base_yaw']]])

    def body(self, name): return self.data.body(name).xpos.copy()

    def _object_set(self, name, xyz):
        j = self.model.joint(name+'_free')
        self.data.qpos[j.qposadr[0]:j.qposadr[0]+7] = [*xyz,1,0,0,0]
        self.data.qvel[j.dofadr[0]:j.dofadr[0]+6] = 0

    def setup_assignment(self, row):
        if self.active: raise ValueError('Cannot change assignment during an action')
        self.assignment = dict(row)
        self.assignment_start = self.time
        self.pickups = {x:False for x in OBJECTS}
        self.rng = np.random.default_rng(row['sensor_seed'])
        if row['kind'] == 'bedroom':
            for (name,size,_),(x,y) in zip(TOYS,row['toys']): self._object_set(name,[x,y,size[2]+.02])
        if row['kind'] == 'kitchen':
            self._object_set('cup',[10.8,2.,.95])
            for n in ('A','B'):
                j=self.model.joint('drawer'+n)
                self.data.qpos[j.qposadr[0]]=0
                self.data.qvel[j.dofadr[0]]=0
            self.latch_released=False
            self.handle_grip=None
        if row['kind'] == 'throwing':
            # Between assignments the external task setter resets its exercise object,
            # including a ball still held at the previous ordinary docking boundary.
            # Public within-assignment reset retains the release requirement.
            self.grip_candidate=None
            self.reset_throw()
        mujoco.mj_forward(self.model,self.data)

    def reset_throw(self):
        if self.active: raise ValueError('Wait for the current action')
        if self.grip_candidate == 'ball': raise ValueError('Release the object before requesting reset')
        self._object_set('ball',[3.,1.4,.96])
        self.throw_feedback=None
        self.throw_airborne=False
        self.throw_previous_z=None
        self.throw_rest_since=None
        mujoco.mj_forward(self.model,self.data)

    def begin_session(self, work, reserve):
        self.working_window=float(work)
        self.reserve_window=float(reserve)
        self.session_start=self.time
        self.docked=False
        # Captured observation handles are session-local in both uninterrupted
        # execution and checkpoint recovery. Learned filesystem content persists.
        self.observations.clear()

    def battery(self):
        age=0. if self.docked else max(0.,self.time-self.session_start)
        total=self.working_window+self.reserve_window
        return dict(percent=round(max(0.,100*(1-age/total)),3), low_warning=age>=self.working_window,
                    work_seconds_remaining=max(0.,round(self.working_window-age,2)),
                    return_seconds_remaining=round(max(0.,total-age),2), docked=self.docked)

    def task_text(self):
        if not self.assignment:return 'Await the current external assignment.'
        kind=self.assignment['kind']
        if kind=='bedroom':return 'Pick up the four toys (red, blue, green, yellow) in the bedroom and put all four inside the fixed toy chest.'
        if kind=='kitchen':return 'Find the cup on one of the three kitchen countertop mats and put it inside drawer '+self.assignment['drawer']+'.'
        return 'Use this working window to learn to throw the orange object into the bin in the living room. Experiment with the ordinary arm and gripper controls; landing feedback and object reset are available. Dock when the battery warning occurs.'

    def evaluate(self):
        if not self.assignment:return False
        kind=self.assignment['kind']
        if kind=='bedroom':
            return all(self.pickups[n] and self.grip_candidate!=n and abs(self.body(n)[0]-4.8)<.49 and abs(self.body(n)[1]-8)<.34 and .08<self.body(n)[2]<.42
                       and np.linalg.norm(self.data.qvel[self.model.joint(n+'_free').dofadr[0]:self.model.joint(n+'_free').dofadr[0]+3])<.08 for n,_,_ in TOYS)
        if kind=='kitchen':
            n='drawer'+self.assignment['drawer']; c=self.body('cup'); d=self.body(n)
            return bool(self.pickups['cup'] and self.grip_candidate!='cup' and self.data.qpos[self.model.joint(n).qposadr[0]]>.32 and
                        abs(c[0]-d[0])<.34 and abs(c[1]-d[1])<.31 and d[2]<c[2]<d[2]+.25 and
                        np.linalg.norm(self.data.qvel[self.model.joint('cup_free').dofadr[0]:self.model.joint('cup_free').dofadr[0]+3])<.08)
        return False

    def public_status(self):
        enc={n:round(float(self.data.qpos[a])+float(self.rng.normal(0,.0004)),5) for n,a in self.joints.items() if not n.startswith('base_')}
        secure=self.grip_candidate is not None and self.body(self.grip_candidate)[2]>(.98 if self.grip_candidate in ('cup','ball') else .10)
        return dict(sim_time=round(self.time,3), battery=self.battery(), assignment=self.task_text(),
                    task_success=self.evaluate(), action=self.active['id'] if self.active else None, last_action=self.last_action,
                    odometry=dict(frame='session-independent dead-reckoned start frame; not a surveyed apartment frame',x=round(self.odom[0],3),y=round(self.odom[1],3),yaw=round(self.odom[2],4)),
                    imu=dict(yaw=round(self.odom[2]+float(self.rng.normal(0,.003)),4)),
                    joint_encoders=enc, gripper=dict(width=round(enc['finger_left']+enc['finger_right'],4),
                      effort=float(sum(abs(self.data.actuator_force[self.act[n]]) for n in ('finger_left','finger_right'))),
                      bilateral_contact=bool(self.grip_candidate), secure_lift_confirmed=secure),
                    throw_feedback=self.throw_feedback)

    def command(self, request):
        if self.active:raise ValueError('Action in progress; poll status before another command')
        kind=request['kind']; p=request.get('parameters',{}); rid=request['request_id']
        if self.docked and kind!='dock':raise ValueError('Docked session is closing; physical commands are closed')
        values={}
        duration=1.
        if kind=='base':
            distance=float(p.get('forward',0)); angle=float(p.get('turn',0))
            if not abs(distance)<=1.5 or not abs(angle)<=math.pi:raise ValueError('Base segment limit: 1.5 m, pi rad')
            if abs(distance)>0 and abs(angle)>0:raise ValueError('Use one straight or turning segment')
            pose=self.base_pose()
            if abs(distance)>0 and self.target['reach']>.48:raise ValueError('Retract arm reach to at most .48 m before driving')
            values={'base_x':float(pose[0]-3+distance*math.cos(pose[2])), 'base_y':float(pose[1]-2+distance*math.sin(pose[2])), 'base_yaw':float(pose[2]+angle)}
            if not (.35<=values['base_x']+3<=11.65 and .35<=values['base_y']+2<=9.65):raise ValueError('Boundary stop')
            duration=max(abs(distance)/.22,abs(angle)/.6,.25)
        elif kind in ('arm','position_grasp'):
            x,y,z=[float(p[k]) for k in ('x','y','z')]
            pitch=float(p.get('pitch',0))
            if not (.20<=x<=1.03 and -.45<=y<=.45 and .02<=z<=1.35 and abs(pitch)<=1.4):raise ValueError('Arm Cartesian limit')
            values={'reach':x-.08,'lateral':y,'lift':z-.43,'wrist_pitch':pitch}
            duration=max(.3,float(p.get('duration',max(abs(values[n]-self.target[n]) for n in values)/.10)))
            if kind=='position_grasp':
                # Generic open, rise, translate, descend. Never choose closure.
                # A direct diagonal approach can sweep an object out of reach.
                ceiling=max(z+.15,self.target['lift']+.43)
                ceiling=min(1.35,ceiling)
                stages=[(.7,dict(finger_left=.075,finger_right=.075)),
                        (max(.3,abs(ceiling-.43-self.target['lift'])/.1),dict(lift=ceiling-.43)),
                        (max(.3,abs(x-.08-self.target['reach'])/.1,abs(y-self.target['lateral'])/.1),dict(reach=x-.08,lateral=y,wrist_pitch=pitch)),
                        (max(.3,(ceiling-z)/.1),dict(lift=z-.43))]
                duration,values=stages.pop(0)
                self.active=dict(id=rid,kind=kind,start=self.time,duration=duration,from_values=dict(self.target),values=values,remaining=stages)
                return
        elif kind=='gripper':
            width=float(p['width'])
            if not 0<=width<=.15:raise ValueError('Gripper width 0 to .15 m')
            values={'finger_left':width/2,'finger_right':width/2};duration=max(.15,float(p.get('duration',.6)))
        elif kind=='head':
            pan=float(p.get('pan',self.target['head_pan']));tilt=float(p.get('tilt',self.target['head_tilt']))
            if abs(pan)>3.14 or abs(tilt)>1.2:raise ValueError('Camera pan/tilt limit')
            values={'head_pan':pan,'head_tilt':tilt};duration=.5
        elif kind=='trajectory':
            points=p['points']
            if not isinstance(points,list) or not 1<=len(points)<=64:raise ValueError('One to 64 bounded waypoints required')
            # General Cartesian+aperture trajectory; no throwing preset or release parameters.
            validated=[]
            for point in points:
                if set(point)-{'x','y','z','pitch','width','duration'}:raise ValueError('Unexpected waypoint field')
                x,y,z=[float(point[k]) for k in ('x','y','z')];dt=float(point['duration']);pitch=float(point.get('pitch',0))
                if not (.20<=x<=1.03 and -.45<=y<=.45 and .02<=z<=1.35 and abs(pitch)<=1.4 and .05<=dt<=30):raise ValueError('Waypoint limit')
                v={'reach':x-.08,'lateral':y,'lift':z-.43,'wrist_pitch':pitch}
                if 'width' in point:
                    width=float(point['width'])
                    if not 0<=width<=.15:raise ValueError('Aperture limit')
                    v.update(finger_left=width/2,finger_right=width/2)
                validated.append((dt,v))
            duration,values=validated.pop(0)
            self.active=dict(id=rid,kind=kind,start=self.time,duration=duration,from_values=dict(self.target),values=values,remaining=validated)
            return
        elif kind=='dock':
            if not self.battery()['low_warning']:raise ValueError('Docking session close begins after the battery warning')
            pose=self.base_pose()
            if not any(math.hypot(pose[0]-x,pose[1]-y)<.24 for x,y in CHARGERS):raise ValueError('No charging contact: navigate onto the visible green pad first')
            if np.linalg.norm([self.data.qvel[self.model.joint(n).dofadr[0]] for n in ('base_x','base_y','base_yaw')])>.08:raise ValueError('Stop the robot before docking')
            self.docked=True;self.last_action={'request_id':rid,'status':'completed','kind':'dock','sim_time':self.time};return
        elif kind=='reset_object':
            if not self.assignment or self.assignment['kind']!='throwing':raise ValueError('Reset is available only for the throwing exercise')
            self.reset_throw();self.last_action={'request_id':rid,'status':'completed','kind':kind,'sim_time':self.time};return
        elif kind=='wait': duration=float(p.get('duration',1))
        else:raise ValueError('Unknown primitive')
        if not .05<=duration<=60:raise ValueError('Action duration must be .05 to 60 seconds')
        if any(not np.isfinite(x) for x in values.values()):raise ValueError('Nonfinite action')
        self.active=dict(id=rid,kind=kind,start=self.time,duration=duration,from_values=dict(self.target),values=values,remaining=[])

    def _mechanics(self):
        # Resolve contact observations without exposing geom/body IDs publicly.
        touched={};left=self.model.geom('finger_left_geom').id;right=self.model.geom('finger_right_geom').id
        fingers={left,right}
        force=np.zeros(6)
        for i,c in enumerate(self.data.contact):
            a,b=int(c.geom1),int(c.geom2)
            if a not in fingers and b not in fingers:continue
            other=b if a in fingers else a; finger=a if a in fingers else b
            touched.setdefault(other,set()).add(finger)
            if other==self.model.geom('latchB').id:
                mujoco.mj_contactForce(self.model,self.data,i,force)
                if force[0]>.5:self.latch_released=True
        self.grip_candidate=None
        for n in OBJECTS:
            if touched.get(self.model.geom(n+'_geom').id)==fingers:
                self.grip_candidate=n
                floor=.88 if n=='cup' else (.88 if n=='ball' else 0)
                if self.body(n)[2]>floor+.10:self.pickups[n]=True
        # The latch is an ideal mechanical lock; contact with its orange button releases it.
        j=self.model.joint('drawerB')
        if not self.latch_released:
            self.data.qpos[j.qposadr[0]]=0;self.data.qvel[j.dofadr[0]]=0
        self.last_contacts={int(k):list(v) for k,v in touched.items()}
        if self.assignment and self.assignment['kind']=='throwing':
            pos=self.body('ball');dj=self.model.joint('ball_free').dofadr[0];speed=np.linalg.norm(self.data.qvel[dj:dj+3])
            if self.grip_candidate=='ball':self.throw_airborne=True;self.throw_feedback=None;self.throw_rest_since=None
            elif self.throw_airborne:
                ball=self.model.geom('ball_geom').id
                support=any(ball in (int(c.geom1),int(c.geom2)) and
                    not self.model.body(int(self.model.geom_bodyid[int(c.geom2) if int(c.geom1)==ball else int(c.geom1)])).name.startswith(('base','arm','wrist','finger','head'))
                    for c in self.data.contact)
                if speed<.05 and support:
                    if self.throw_rest_since is None:self.throw_rest_since=self.time
                else:self.throw_rest_since=None
            if self.throw_airborne and self.throw_rest_since is not None and self.time-self.throw_rest_since>=.2:
                self.throw_feedback=dict(inside_bin=bool(abs(pos[0]-4.8)<.34 and abs(pos[1]-1.4)<.34 and .05<pos[2]<.4),
                    displacement_m=dict(forward=round(float(pos[0]-4.8),3),left=round(float(pos[1]-1.4),3)),
                    frame='target bin: forward along room throwing axis, left perpendicular', landed_sim_time=self.time)
                self.throw_airborne=False

    def step(self, count=1):
        for _ in range(count):
            if self.active:
                a=self.active;t=min(1.,max(0.,(self.time-a['start'])/a['duration']))
                for n,v in a['values'].items():self.target[n]=(1-t)*a['from_values'][n]+t*v
                if t>=1:
                    if a['remaining']:
                        duration,values=a['remaining'].pop(0)
                        self.active={**a,'start':self.time,'duration':duration,'values':values,'from_values':dict(self.target)}
                    else:
                        self.last_action=dict(request_id=a['id'],kind=a['kind'],status='completed',sim_time=self.time)
                        if a['kind']=='base':
                            error=max(abs(self.data.qpos[self.joints[n]]-v) for n,v in a['values'].items())
                            if error>.08:
                                self.last_action.update(status='blocked',reason='Base did not reach requested target; inspect obstacles')
                                for n in a['values']:self.target[n]=float(self.data.qpos[self.joints[n]])
                        self.active=None
            for n,v in self.target.items():self.data.ctrl[self.act[n]]=v
            mujoco.mj_step(self.model,self.data)
            self._mechanics()
        pose=self.base_pose();delta=pose-self.previous_base
        if np.linalg.norm(delta)>0:
            self.odom+=delta+self.rng.normal(0,1e-4,3)*np.linalg.norm(delta)
        self.previous_base=pose

    def capture(self, camera='head_rgbd'):
        if camera not in ('head_rgbd','wrist_rgb'):raise ValueError('Camera name')
        if self.renderer is None:self.renderer=mujoco.Renderer(self.model,height=360,width=480)
        self.renderer.disable_depth_rendering();self.renderer.update_scene(self.data,camera=camera)
        rgb=self.renderer.render().copy()
        rgb=np.clip(rgb.astype(float)+self.rng.normal(0,1.3,rgb.shape),0,255).astype(np.uint8)
        self.renderer.enable_depth_rendering();self.renderer.update_scene(self.data,camera=camera)
        depth=self.renderer.render().copy();self.renderer.disable_depth_rendering()
        depth=np.clip(depth+self.rng.normal(0,.003+.001*depth,depth.shape),.05,12)
        cid=self.model.camera(camera).id
        self.sequence+=1
        entry=dict(sequence=self.sequence,sim_time=self.time,camera=camera,rgb=png(rgb),depth=depth,
                   cam_xpos=self.data.cam_xpos[cid].copy(),cam_xmat=self.data.cam_xmat[cid].reshape(3,3).copy(),
                   base_pose=self.base_pose().copy())
        self.observations[self.sequence]=entry
        while len(self.observations)>24:del self.observations[min(self.observations)]
        return entry

    def sensor_packet(self, entry):
        lidar=[];base=self.base_pose();geom=np.array([-1],dtype=np.int32);groups=np.ones(6,dtype=np.uint8)
        for angle in np.linspace(-np.pi,np.pi,72,endpoint=False):
            direction=np.array([math.cos(base[2]+angle),math.sin(base[2]+angle),0.])
            origin=np.array([base[0]+.32*direction[0],base[1]+.32*direction[1],.22])
            distance=mujoco.mj_ray(self.model,self.data,origin,direction,groups,1,self.model.body('base').id,geom)
            lidar.append(round(float(np.clip((distance if distance>=0 else 10)+self.rng.normal(0,.007),0,10)),3))
        depth=entry['depth'][10::20,10::20]
        return dict(**self.public_status(),observation_sequence=entry['sequence'],camera=entry['camera'],width=480,height=360,
                    fovy_degrees=72 if entry['camera']=='head_rgbd' else 80,depth_m=np.round(depth,3).tolist(),
                    depth_grid=dict(first_pixel=[10,10],stride=20),lidar_m=lidar,lidar_angles=dict(start=-math.pi,step=2*math.pi/72),
                    image_tool='robot_image',noise='RGB, depth, lidar, encoders, IMU and dead-reckoning noise enabled; no semantic object labels')

    def sensed_point(self, sequence, u, v):
        entry=self.observations[int(sequence)]
        if self.time-entry['sim_time']>30:raise ValueError('Observation older than 30 simulated seconds')
        u=int(u);v=int(v)
        if not (2<=u<478 and 2<=v<358):raise ValueError('Pixel out of bounds')
        d=float(np.median(entry['depth'][v-2:v+3,u-2:u+3]));fovy=72 if entry['camera']=='head_rgbd' else 80
        focal=180/math.tan(math.radians(fovy/2))
        local=np.array([(u-239.5)*d/focal,-(v-179.5)*d/focal,-d])
        world=entry['cam_xpos']+entry['cam_xmat']@local
        pose=entry['base_pose'];dx,dy=world[:2]-pose[:2];c,s=math.cos(pose[2]),math.sin(pose[2])
        return dict(x=round(c*dx+s*dy,4),y=round(-s*dx+c*dy,4),z=round(float(world[2]),4),
                    frame='base-relative estimate from noisy depth and calibrated camera extrinsics',observation_sequence=sequence)

    def snapshot(self):
        flags=mujoco.mjtState.mjSTATE_INTEGRATION
        state=np.zeros(mujoco.mj_stateSize(self.model,flags));mujoco.mj_getState(self.model,self.data,state,flags)
        return dict(physics=state.tolist(),sim_time=self.time,target=self.target,active=self.active,last_action=self.last_action,
                    latch_released=self.latch_released,pickups=self.pickups,assignment=self.assignment,
                    assignment_start=self.assignment_start,session_start=self.session_start,working_window=self.working_window,
                    reserve_window=self.reserve_window,docked=self.docked,rng=self.rng.bit_generator.state,
                    odom=self.odom.tolist(),previous_base=self.previous_base.tolist(),sequence=self.sequence,
                    throw_feedback=self.throw_feedback,throw_airborne=self.throw_airborne,throw_rest_since=self.throw_rest_since,
                    grip_candidate=self.grip_candidate,handle_grip=self.handle_grip,
                    throw_previous_z=self.throw_previous_z,last_contacts=self.last_contacts)

    def restore(self, value):
        mujoco.mj_setState(self.model,self.data,np.array(value['physics']),mujoco.mjtState.mjSTATE_INTEGRATION)
        for n in ('target','active','last_action','latch_released','pickups','assignment','assignment_start','session_start','working_window','reserve_window','docked','sequence','throw_feedback','throw_airborne','throw_rest_since'):
            setattr(self,n,value[n])
        for n in ('grip_candidate','handle_grip','throw_previous_z','last_contacts'):
            if n in value:setattr(self,n,value[n])
        self.observations.clear()
        self.rng.bit_generator.state=value['rng'];self.odom=np.array(value['odom']);self.previous_base=np.array(value['previous_base'])
        mujoco.mj_forward(self.model,self.data)

    def close(self):
        if self.renderer:self.renderer.close()
