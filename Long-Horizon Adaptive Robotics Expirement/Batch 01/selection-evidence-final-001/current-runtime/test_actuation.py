"""Synthetic adapter/authority checks, not physical robot experiments.

The tiny MuJoCo force-law fixture calls mj_forward only (no integration,
renderer, model inference, compute queue or canonical experiment evidence).
"""
from pathlib import Path
from concurrent.futures import Future
from types import SimpleNamespace
import unittest
from unittest.mock import patch,Mock
import xml.etree.ElementTree as ET

import mujoco
import numpy as np

from actuation import AffineServoAdapter
from test_cell import fake_cell,fake_step
import cell as runtime_cell


def panda_spec():
    root=ET.parse(Path(__file__).parent/'vendor'/'panda'/'panda.xml').getroot()
    default=root.find("./default/default[@class='panda']/general").attrib
    default_joint=root.find("./default/default[@class='panda']/joint").attrib
    gain=[];bias=[];ctrl=[];force=[];joints=[]
    for act in root.findall('./actuator/general')[:7]:
        attrs={**default,**act.attrib};joint=root.find(".//joint[@name='"+attrs['joint']+"']")
        gain.append(float(attrs['gainprm'].split()[0]));bias.append(list(map(float,attrs['biasprm'].split())))
        ctrl.append(list(map(float,attrs['ctrlrange'].split())));force.append(list(map(float,attrs['forcerange'].split())))
        joints.append(list(map(float,joint.get('range',default_joint['range']).split())))
    return AffineServoAdapter(gain,bias,ctrl,force,joints)


class AdapterTests(unittest.TestCase):
    def setUp(self):self.adapter=panda_spec();self.q=runtime_cell.HOME.copy()

    def test_inverse_uses_position_servo_bias_and_reports_reachable_torque(self):
        velocity=np.array([.2,-.1,.05,0.,.1,.02,-.2]);requested=np.array([12.,-10,5,0,2,-2,3])
        controls,report=self.adapter.effort(requested,self.q,velocity)
        np.testing.assert_allclose(self.adapter.force(controls,self.q,velocity),requested,atol=1e-9)
        self.assertFalse(np.allclose(controls,requested))
        self.assertFalse(any(report['clipped']))
        self.assertEqual(len(report['reachable_effort_range_Nm']),7)

    def test_effort_clips_to_native_force_and_ctrl_envelope(self):
        q=self.adapter.position_range[:,1].copy();velocity=np.full(7,-3.)
        controls,report=self.adapter.effort(np.full(7,10000.),q,velocity)
        self.assertTrue(all(report['clipped']))
        self.assertTrue(np.all(controls>=self.adapter.ctrl_range[:,0]))
        self.assertTrue(np.all(controls<=self.adapter.ctrl_range[:,1]))
        actual=self.adapter.force(controls,q,velocity)
        self.assertTrue(np.all(actual<=self.adapter.force_range[:,1]))
        np.testing.assert_allclose(actual,report['predicted_clipped_effort_Nm'])

    def test_native_mujoco_affine_force_matches_the_inverse_without_stepping(self):
        a=self.adapter;parts=[];actuators=[]
        for i in range(8):
            range_text=' '.join(map(str,a.joint_range[i])) if i<7 else '-1 1'
            parts.append(f'<body pos="{i*.1} 0 0"><joint name="j{i}" type="hinge" limited="true" range="{range_text}"/><geom type="sphere" size=".01" mass=".1"/></body>')
            if i<7:
                pair=lambda x:' '.join(map(str,x))
                actuators.append(f'<general joint="j{i}" dyntype="none" gaintype="fixed" biastype="affine" gainprm="{a.gain[i]}" biasprm="{pair(a.bias[i])}" ctrllimited="true" ctrlrange="{pair(a.ctrl_range[i])}" forcelimited="true" forcerange="{pair(a.force_range[i])}"/>')
            else:actuators.append('<motor joint="j7"/>')
        model=mujoco.MjModel.from_xml_string('<mujoco><compiler angle="radian"/><worldbody>'+''.join(parts)+'</worldbody><actuator>'+''.join(actuators)+'</actuator></mujoco>')
        compiled=AffineServoAdapter.from_model(model)
        np.testing.assert_array_equal(compiled.gain,a.gain)
        np.testing.assert_array_equal(compiled.bias,a.bias)
        data=mujoco.MjData(model);data.qpos[:7]=self.q;data.qvel[:7]=[.1,-.1,.2,0,.1,-.2,.3]
        requested=[20,-20,7,10,100,-100,3]
        controls,report=a.effort(requested,data.qpos[:7],data.qvel[:7]);data.ctrl[:7]=controls
        mujoco.mj_forward(model,data)
        np.testing.assert_allclose(data.actuator_force[:7],report['predicted_clipped_effort_Nm'],atol=1e-8)
        self.assertEqual(data.time,0.)
        model.actuator_gear[0,0]=2.
        with self.assertRaisesRegex(ValueError,'unit-gear'):AffineServoAdapter.from_model(model)

    def test_position_path_and_timestamped_trajectory_share_speed_bounds(self):
        target=self.q+.1
        a=self.adapter.admit({'operation':'joint_command','mode':'position','values':target.tolist(),'duration_s':1.},10.,self.q)
        b=self.adapter.admit({'operation':'trajectory','waypoints':[{'time_s':11.,'positions':target.tolist()}]},10.,self.q)
        for time in (10.,10.2,10.5,10.9,11.):
            qa,_=self.adapter.control(a,time,self.q,np.zeros(7));qb,_=self.adapter.control(b,time,self.q,np.zeros(7))
            np.testing.assert_allclose(qa,qb)

    def test_duration_over_two_seconds_and_excess_speed_are_refused(self):
        for action in ({'operation':'joint_command','mode':'position','values':self.q.tolist(),'duration_s':2.01},
                       {'operation':'joint_command','mode':'position','values':(self.q+.2).tolist(),'duration_s':.01},
                       {'operation':'trajectory','waypoints':[{'time_s':-.1,'positions':self.q.tolist()}]}):
            with self.assertRaises(ValueError):self.adapter.admit(action,0.,self.q)

    def test_velocity_is_bounded_and_integrates_under_same_position_limits(self):
        command=self.adapter.admit({'operation':'joint_command','mode':'velocity','values':[100.]*7,'duration_s':2.},0.,self.q)
        target,report=self.adapter.control(command,1.,self.q,np.zeros(7))
        np.testing.assert_allclose(target,self.adapter.position(self.q+.7))
        self.assertEqual(report['bounded_velocity_rad_s'],[.7]*7)

    def test_cartesian_workspace_and_nonfinite_inputs_are_refused(self):
        for target in ([2.,0.,.3],[.4,float('nan'),.2]):
            with self.assertRaises(ValueError):self.adapter.admit({'operation':'cartesian_target','position':target,'duration_s':1.},0.,self.q)


class DirectAuthorityTests(unittest.TestCase):
    def runtime(self):
        value=fake_cell();value.arm_adapter=panda_spec();value.data.qpos[:7]=runtime_cell.HOME
        value.data.ctrl[:7]=runtime_cell.HOME;value.direct_command=None;value.direct_plan_future=None
        return value

    def action(self,rid='direct',**extra):
        return {'operation':'joint_command','mode':'effort','values':[0.]*7,'duration_s':1.,
                'request_id':rid,'incarnation':1,'order_version':1,**extra}

    def test_direct_effort_uses_inverse_and_deadline_ends_in_servo_hold(self):
        value=self.runtime();action=self.action(values=[1.]*7)
        self.assertEqual(value.submit(action)['status'],'accepted')
        self.assertTrue(value.direct_control_active)
        with patch.object(runtime_cell.mujoco,'mj_step',side_effect=fake_step):value.tick()
        np.testing.assert_allclose(value.arm_adapter.force(value.data.ctrl[:7],value.data.qpos[:7],value.data.qvel[:7]),np.ones(7),atol=1e-8)
        self.assertTrue(any(e['type']=='direct_control_limits' for e in value.events))
        value.data.time=1.
        with patch.object(runtime_cell.mujoco,'mj_step',side_effect=fake_step):value.tick()
        self.assertFalse(value.direct_control_active)
        np.testing.assert_array_equal(value.data.ctrl[:7],value.data.qpos[:7])
        self.assertEqual(value.feedback[-1]['status'],'completed')

    def test_invalid_supersession_never_revokes_old_authority(self):
        value=self.runtime();value.submit(self.action());value.data.time=.02
        self.assertEqual(value.submit(self.action('new',replace_request_id='wrong'))['status'],'rejected')
        self.assertEqual(value.active_request['request_id'],'direct')
        self.assertEqual(value.submit(self.action('new',replace_request_id='direct',duration_s=10.))['status'],'rejected')
        self.assertEqual(value.active_request['request_id'],'direct')

    def test_explicit_supersession_and_cancel_keep_one_authority(self):
        value=self.runtime();value.submit(self.action());value.data.time=.02
        self.assertEqual(value.submit(self.action('new',replace_request_id='direct'))['status'],'accepted')
        self.assertEqual(value.active_request['request_id'],'new')
        self.assertEqual(value.feedback[-1]['request_id'],'direct')
        self.assertEqual(value.feedback[-1]['status'],'cancelled')
        result=value.submit({'operation':'cancel','request_id':'cancel-new','target_request_id':'new','incarnation':1})
        self.assertEqual(result['status'],'accepted')
        self.assertIsNone(value.active_request);self.assertFalse(value.direct_control_active)
        self.assertEqual([r['request_id'] for r in value.feedback],['direct','new','cancel-new'])

    def test_renewal_never_extends_direct_deadline(self):
        value=self.runtime();value.submit(self.action());value.data.time=.2;value.detection_time=.2
        self.assertTrue(value.renew_authority(1,1));self.assertEqual(value.lease_deadline,1.)

    def test_admission_rate_is_bounded_to_one_hundred_hz(self):
        value=self.runtime();value.submit(self.action())
        result=value.submit(self.action('new',replace_request_id='direct'))
        self.assertEqual(result['status'],'rejected');self.assertIn('100 Hz',result['reason'])

    def test_cartesian_planning_consumes_time_without_jumping_ahead(self):
        value=self.runtime();future=Future();value.planner=SimpleNamespace(submit=Mock(return_value=future))
        result=value.submit({'operation':'cartesian_target','position':[.4,0,.4],'duration_s':1.,
                             'request_id':'cartesian','incarnation':1,'order_version':1})
        self.assertEqual(result['status'],'accepted')
        value.data.time=.2
        future.set_result((value.plan_generation,runtime_cell.HOME+.1))
        with patch.object(runtime_cell.mujoco,'mj_step',side_effect=fake_step):value.tick()
        self.assertEqual(value.direct_command['start'],.2)
        np.testing.assert_allclose(value.data.ctrl[:7],runtime_cell.HOME)
        self.assertIsNone(value.direct_plan_future)

    def test_unfinished_cartesian_plan_at_deadline_is_cancelled_not_completed(self):
        value=self.runtime();value.planner=SimpleNamespace(submit=Mock(return_value=Future()))
        value.submit({'operation':'cartesian_target','position':[.4,0,.4],'duration_s':1.,
                      'request_id':'cartesian','incarnation':1,'order_version':1})
        value.data.time=1.
        with patch.object(runtime_cell.mujoco,'mj_step',side_effect=fake_step):value.tick()
        self.assertEqual(value.feedback[-1]['status'],'cancelled')
        self.assertFalse(value.direct_control_active)

    def test_new_incarnation_cannot_cancel_or_replace_old_authority(self):
        value=self.runtime();value.submit(self.action());value.data.time=.02
        result=value.submit(self.action('new',replace_request_id='direct',incarnation=2))
        self.assertEqual(result['status'],'rejected')
        result=value.submit({'operation':'cancel','request_id':'cancel','target_request_id':'direct','incarnation':2})
        self.assertEqual(result['status'],'rejected')
        self.assertEqual(value.active_request['request_id'],'direct')


if __name__=='__main__':unittest.main(verbosity=2)
