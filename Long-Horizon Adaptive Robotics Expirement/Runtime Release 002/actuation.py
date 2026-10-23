"""Public bounded arm adapters; no world truth or hidden collision queries.

Effort is inverted through the existing fixed-gain affine position servo. No
body, actuator, ctrl range, force range, damping or gear is changed. Supported
force law: p = gain*ctrl + b0 + b1*length + b2*velocity, with native clipping.
See https://mujoco.readthedocs.io/en/stable/computation/index.html#force-generation
Numerical algebra checks are not physical controller-equivalence experiments.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import math

import numpy as np


ARM_OPERATIONS=('joint_command','trajectory','cartesian_target')


@dataclass(frozen=True)
class ArmLimits:
    max_horizon_s:float=2.
    min_interval_s:float=.01
    max_target_speed_rad_s:float=1.4
    max_velocity_command_rad_s:float=.7
    maximum_waypoints:int=200
    workspace_min:tuple=(.05,-.55,-.005)
    workspace_max:tuple=(.85,.55,.80)


def number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def vector(value,size=7):
    if not isinstance(value,(list,tuple,np.ndarray)) or len(value)!=size or not all(number(x) for x in value):
        raise ValueError('expected a finite vector of length '+str(size))
    return np.array(value,dtype=float)


class AffineServoAdapter:
    """Exact unit-gear, fixed-gain, stateless affine actuator inverse only."""
    def __init__(self,gain,bias,ctrl_range,force_range,joint_range,limits=None):
        self.gain=np.array(gain,dtype=float);self.bias=np.array(bias,dtype=float)
        self.ctrl_range=np.array(ctrl_range,dtype=float);self.force_range=np.array(force_range,dtype=float)
        self.joint_range=np.array(joint_range,dtype=float);self.limits=limits or ArmLimits()
        arrays=(self.gain,self.bias,self.ctrl_range,self.force_range,self.joint_range)
        if (self.gain.shape!=(7,) or self.bias.shape!=(7,3)
                or any(a.shape!=(7,2) for a in arrays[2:]) or any(not np.all(np.isfinite(a)) for a in arrays)
                or np.any(self.gain<=0) or any(np.any(a[:,0]>=a[:,1]) for a in arrays[2:])):
            raise ValueError('unsupported or nonfinite affine servo specification')
        self.position_range=np.c_[np.maximum(self.ctrl_range[:,0],self.joint_range[:,0]),
                                 np.minimum(self.ctrl_range[:,1],self.joint_range[:,1])]
        if np.any(self.position_range[:,0]>=self.position_range[:,1]):raise ValueError('empty public position range')

    @classmethod
    def from_model(cls,model,limits=None):
        import mujoco
        arm=slice(0,7)
        expected=((model.actuator_dyntype[arm],mujoco.mjtDyn.mjDYN_NONE),
                  (model.actuator_gaintype[arm],mujoco.mjtGain.mjGAIN_FIXED),
                  (model.actuator_biastype[arm],mujoco.mjtBias.mjBIAS_AFFINE),
                  (model.actuator_trntype[arm],mujoco.mjtTrn.mjTRN_JOINT))
        if model.nu<8 or any(np.any(values!=int(kind)) for values,kind in expected):
            raise ValueError('effort inverse requires seven stateless fixed-gain affine joint actuators')
        if (not np.array_equal(model.actuator_trnid[:7,0],np.arange(7))
                or not np.allclose(model.actuator_gear[:7],np.tile([1.,0,0,0,0,0],(7,1)),rtol=0,atol=0)
                or not np.all(model.actuator_ctrllimited[:7]) or not np.all(model.actuator_forcelimited[:7])
                or not np.array_equal(model.jnt_qposadr[:7],np.arange(7))
                or not np.array_equal(model.jnt_dofadr[:7],np.arange(7))):
            raise ValueError('effort inverse requires one unit-gear limited actuator per first seven scalar joints')
        if hasattr(model,'jnt_actfrclimited') and np.any(model.jnt_actfrclimited[:7]):
            raise ValueError('additional aggregate joint actuator-force limits require an explicit adapter')
        disabled=int(model.opt.disableflags)
        if disabled & (int(mujoco.mjtDisableBit.mjDSBL_CLAMPCTRL)|int(mujoco.mjtDisableBit.mjDSBL_ACTUATION)):
            raise ValueError('native control clamping and actuation must remain enabled')
        return cls(model.actuator_gainprm[:7,0],model.actuator_biasprm[:7,:3],
                   model.actuator_ctrlrange[:7],model.actuator_forcerange[:7],model.jnt_range[:7],limits)

    def public_spec(self):
        return {'version':'bounded-arm-adapters-1.0','operations':list(ARM_OPERATIONS),
                'limits':asdict(self.limits),'position_range_rad':self.position_range.tolist(),
                'native_ctrl_range':self.ctrl_range.tolist(),'native_force_range_Nm':self.force_range.tolist(),
                'effort_adapter':'inverse of unchanged stateless affine unit-gear position servo; state-dependent reachable range',
                'affine_gain':self.gain.tolist(),'affine_bias':self.bias.tolist(),
                'permission':'same optional interfaces for all candidates; task macros remain available',
                'collision_limit':'public kinematics/workspace/guard checks, not a hidden object-contact oracle'}

    def position(self,requested):
        values=vector(requested)
        return np.clip(values,self.position_range[:,0],self.position_range[:,1])

    def force(self,controls,qpos,qvel):
        controls=np.clip(vector(controls),self.ctrl_range[:,0],self.ctrl_range[:,1])
        bias=self.bias[:,0]+self.bias[:,1]*vector(qpos)+self.bias[:,2]*vector(qvel)
        return np.clip(self.gain*controls+bias,self.force_range[:,0],self.force_range[:,1])

    def effort(self,requested,qpos,qvel):
        requested=vector(requested);qpos=vector(qpos);qvel=vector(qvel)
        offset=self.bias[:,0]+self.bias[:,1]*qpos+self.bias[:,2]*qvel
        reachable=np.stack([self.force(self.ctrl_range[:,0],qpos,qvel),
                            self.force(self.ctrl_range[:,1],qpos,qvel)],axis=1)
        target=np.clip(requested,reachable[:,0],reachable[:,1])
        raw=(target-offset)/self.gain
        controls=np.clip(raw,self.ctrl_range[:,0],self.ctrl_range[:,1])
        achieved=self.force(controls,qpos,qvel)
        return controls,{'requested_effort_Nm':requested.tolist(),'reachable_effort_range_Nm':reachable.tolist(),
                         'predicted_clipped_effort_Nm':achieved.tolist(),
                         'clipped':(np.abs(achieved-requested)>1e-8).tolist(),
                         'ctrl':controls.tolist(),'basis':'same native affine servo and original ctrl/force bounds'}

    def workspace_contains(self,position):
        point=vector(position,3)
        return bool(np.all(point>=self.limits.workspace_min) and np.all(point<=self.limits.workspace_max))

    def validate_path(self,points):
        for (ta,qa),(tb,qb) in zip(points,points[1:]):
            duration=tb-ta
            if duration<self.limits.min_interval_s-1e-9:raise ValueError('trajectory samples exceed 100 Hz or have unordered times')
            # Quintic smoothstep has maximum derivative 1.875.
            if np.max(np.abs(qb-qa))*1.875/duration>self.limits.max_target_speed_rad_s+1e-9:
                raise ValueError('trajectory would exceed the shared target-speed bound')

    def admit(self,action,now,qpos):
        op=action.get('operation');qpos=vector(qpos)
        if op not in ARM_OPERATIONS:raise ValueError('unknown arm interface')
        if not number(now):raise ValueError('invalid simulator time')
        start=action.get('start_time_s',now)
        if not number(start) or not now-1e-9<=start<=now+self.limits.max_horizon_s:raise ValueError('start must be current or bounded future simulation time')
        grip=action.get('gripper')
        if grip is not None and (not number(grip) or grip not in (0,255)):raise ValueError('gripper is close=0, open=255, or omitted to retain')
        if op=='trajectory':
            raw=action.get('waypoints')
            if not isinstance(raw,list) or not 1<=len(raw)<=self.limits.maximum_waypoints:raise ValueError('bounded waypoints required')
            points=[(float(start),qpos)]
            for item in raw:
                if not isinstance(item,dict) or set(item)!={'time_s','positions'} or not number(item['time_s']):raise ValueError('waypoint requires time_s and positions')
                original=vector(item['positions']);bounded=self.position(original)
                if not np.array_equal(original,bounded):raise ValueError('trajectory joint position outside native bounds')
                points.append((float(item['time_s']),bounded))
            end=points[-1][0]
            self.validate_path(points)
            mode='trajectory';values=None
        else:
            duration=action.get('duration_s')
            if not number(duration) or duration<self.limits.min_interval_s:raise ValueError('positive bounded duration_s required')
            end=float(start+duration);points=None
            mode=action.get('mode') if op=='joint_command' else 'cartesian'
            if mode not in ('position','velocity','effort','cartesian'):raise ValueError('joint mode must be position, velocity or effort')
            original=vector(action.get('position') if mode=='cartesian' else action.get('values'),3 if mode=='cartesian' else 7)
            values=original
            if mode=='position':
                values=self.position(original);points=[(float(start),qpos),(end,values)]
                self.validate_path(points)
            elif mode=='velocity':values=np.clip(original,-self.limits.max_velocity_command_rad_s,self.limits.max_velocity_command_rad_s)
            elif mode=='cartesian' and not self.workspace_contains(values):raise ValueError('Cartesian target outside public workspace')
        deadline=action.get('deadline_s',end)
        if not number(deadline) or not now<deadline<=now+self.limits.max_horizon_s+1e-9 or end>deadline+1e-9:
            raise ValueError('command end/deadline must fit two-second authority horizon')
        return {'mode':mode,'start':float(start),'end':float(end),'deadline':float(deadline),'points':points,
                'values':values,'q0':qpos,'gripper':grip,'admitted_at':float(now),
                'requested':action,'last_effort_report':None}

    def control(self,command,now,qpos,qvel):
        if now<command['start']:return self.position(command['q0']),None
        mode=command['mode']
        if mode=='effort':return self.effort(command['values'],qpos,qvel)
        if mode=='velocity':
            requested=command['q0']+command['values']*min(max(0.,now-command['start']),command['end']-command['start'])
            bounded=self.position(requested)
            return bounded,{'requested_velocity_rad_s':vector(command['requested']['values']).tolist(),
                            'bounded_velocity_rad_s':command['values'].tolist(),
                            'position_clipped':(np.abs(bounded-requested)>1e-8).tolist()}
        points=command['points']
        if not points:raise ValueError('Cartesian IK must resolve before control')
        for (ta,qa),(tb,qb) in zip(points,points[1:]):
            if now<=tb:
                u=np.clip((now-ta)/(tb-ta),0.,1.);blend=u*u*u*(10+u*(-15+6*u))
                return qa+(qb-qa)*blend,None
        return points[-1][1].copy(),None
