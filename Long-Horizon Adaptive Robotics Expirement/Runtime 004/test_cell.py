"""Bounded synthetic regression tests; no renderer, physics run, or scored evidence.

Cell construction is bypassed. Tick tests replace mj_step with a clock increment;
planner tests use an event-controlled thread or manually completed Future. Sensor
tests use explicitly synthetic arrays. No fixtures enter the evidence store.
"""
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
import sys
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cell as runtime_cell


def fake_cell():
    value = runtime_cell.Cell.__new__(runtime_cell.Cell)
    value.data = SimpleNamespace(time=0., qpos=np.zeros(9), ctrl=np.zeros(8),
                                 qvel=np.zeros(9),actuator_force=np.zeros(8),
                                 site_xpos=np.array([[.4, 0., .4]]), ncon=0)
    value.model = SimpleNamespace(geom=lambda name: SimpleNamespace(id=0),
                                  geom_rgba=np.array([[.03, .03, .03, 1.]]))
    value.tcp = 0
    value.registry = {'A1': {'family': 'A', 'half': [.021, .021, .018],
                             'kind': 'part', 'hue': 0.}}
    value.last_detections = [{'id': 'A1', 'kind': 'part', 'family': 'A',
                              'zone': 'raw', 'pos': [.32, -.31, .02]}]
    value.detection_time = 0.
    value.plan_future = None
    value.pending_plan_generation = None
    value.plan_generation = 0
    value.motion = []
    value.segment = None
    value.active_request = None
    value.lease_deadline = None
    value.feedback = []
    value.events = []
    value.station = {'busy': False, 'ready': True, 'fault': False, 'cycle_id': 0,
                     'completed_cycle_id': None, 'guard_closed': False,
                     'clamped': False}
    value.truth = {'A1': {'recipe': None, 'cycles': 0, 'inspection': None,
                           'cycle_history': [], 'inspection_history': []}}
    value.process_duration_s = 8.
    value.cycle = None
    value.inspection = None
    value.inspection_due = None
    value.rework_part_id = None
    value.total_path = 0.
    value.last_tcp = value.data.site_xpos[0].copy()
    value.contact_peak = 0.
    value.collision_impulse = 0.
    return value


def fake_step(model, data):
    data.time += runtime_cell.DT


def segment():
    return {'q': np.ones(7), 'grip': 255, 'duration': 1., 'phase': 0}


class PlannerTests(unittest.TestCase):
    def test_submission_returns_and_tick_advances_while_planner_is_blocked(self):
        value = fake_cell()
        started, release = Event(), Event()
        snapshots = []

        def blocked_plan(snapshot, generation):
            snapshots.append(snapshot)
            started.set()
            if not release.wait(2):
                raise TimeoutError('test failed to release synthetic planner')
            return generation, [segment()]

        value._plan_snapshot = blocked_plan
        value.planner = ThreadPoolExecutor(max_workers=1)
        caller = ThreadPoolExecutor(max_workers=1)
        try:
            action = {'operation': 'transport', 'part_id': 'A1',
                      'destination': 'fixture', 'request_id': 'synthetic-1'}
            submission = caller.submit(value.submit, action)
            self.assertTrue(started.wait(1), 'planner was not started')
            # A synchronous-planner regression fails this deadline; finally
            # releases the worker so the test never leaves a blocked thread.
            self.assertEqual(submission.result(timeout=.5)['status'], 'accepted')
            self.assertFalse(value.plan_future.done())
            value.last_detections[0]['pos'][0] = 99
            value.data.qpos[0] = 99
            self.assertEqual(snapshots[0]['observed']['pos'][0], .32)
            self.assertEqual(snapshots[0]['configuration'][0], 0)
            with patch.object(runtime_cell.mujoco, 'mj_step', side_effect=fake_step):
                value.tick()
            self.assertEqual(value.data.time, runtime_cell.DT)
            self.assertEqual(value.motion, [])
            self.assertIsNone(value.segment)
            self.assertFalse(any(e['type'] == 'trajectory_dispatched' for e in value.events))
        finally:
            release.set()
            caller.shutdown(wait=True, cancel_futures=True)
            value.planner.shutdown(wait=True, cancel_futures=True)

    def pending(self):
        value = fake_cell()
        value.active_request = {'request_id': 'synthetic-old'}
        value.lease_deadline = 2.
        future = Future()
        value.plan_future = future
        value.pending_plan_generation = value.plan_generation
        return value, future

    def test_current_plan_dispatches_only_when_complete(self):
        value, future = self.pending()
        future.set_result((value.plan_generation, [segment()]))
        with patch.object(runtime_cell.mujoco, 'mj_step', side_effect=fake_step):
            value.tick()
        dispatched = [e for e in value.events if e['type'] == 'trajectory_dispatched']
        self.assertEqual([e['request_id'] for e in dispatched], ['synthetic-old'])
        self.assertIsNotNone(value.segment)
        self.assertIsNone(value.plan_future)

    def cancel_then_begin_inspection(self):
        value, future = self.pending()
        value.cancel('synthetic revocation')
        value._physical_zone = Mock(return_value=True)
        new_action = {'operation': 'inspect', 'part_id': 'A1',
                      'request_id': 'synthetic-new'}
        self.assertEqual(value.submit(new_action)['status'], 'accepted')
        return value, future

    def test_cancelled_plan_cannot_dispatch_for_a_new_active_request(self):
        value, future = self.cancel_then_begin_inspection()
        future.set_result((0, [segment()]))
        with patch.object(runtime_cell.mujoco, 'mj_step', side_effect=fake_step):
            value.tick()
        self.assertEqual(value.motion, [])
        self.assertIsNone(value.segment)
        self.assertEqual(value.active_request['request_id'], 'synthetic-new')
        self.assertEqual(value.events[-1]['type'], 'stale_plan_discarded')
        self.assertFalse(any(e['type'] == 'trajectory_dispatched' for e in value.events))
        self.assertEqual(value.feedback[0]['status'], 'cancelled')

    def test_cancelled_planner_exception_cannot_fail_a_new_request(self):
        value, future = self.cancel_then_begin_inspection()
        future.set_exception(ValueError('synthetic old planner failure'))
        with patch.object(runtime_cell.mujoco, 'mj_step', side_effect=fake_step):
            value.tick()
        self.assertEqual(value.active_request['request_id'], 'synthetic-new')
        self.assertFalse(any(e.get('status') == 'failed' for e in value.feedback))


class SensorTests(unittest.TestCase):
    def test_non_overhead_capture_does_not_replace_overhead_public_state(self):
        value=fake_cell()
        value.last_rgb='old-rgb';value.last_depth='old-depth'
        value.last_sensor_result='old-result';value.sensor_completed_captures=7
        before=value.last_detections
        result=SimpleNamespace(camera='wrist',detections=['wrist-only'],rgb='wrist-rgb',
                               depth='wrist-depth',capture_sim_time_s=2.)
        value.sensor_worker=SimpleNamespace(poll=Mock(return_value=result))
        self.assertIs(value.poll_sense(),result)
        self.assertIs(value.last_detections,before)
        self.assertEqual(value.last_rgb,'old-rgb')
        self.assertEqual(value.last_depth,'old-depth')
        self.assertEqual(value.detection_time,0.)
        self.assertEqual(value.last_sensor_result,'old-result')
        self.assertEqual(value.sensor_completed_captures,7)

    def test_overhead_capture_updates_only_its_complete_result(self):
        value=fake_cell();value.sensor_completed_captures=0
        result=SimpleNamespace(camera='overhead',detections=['new'],rgb='rgb',depth='depth',capture_sim_time_s=3.)
        value.sensor_worker=SimpleNamespace(poll=Mock(return_value=result))
        self.assertIs(value.poll_sense(),result)
        self.assertEqual(value.last_detections,['new'])
        self.assertEqual(value.detection_time,3.)
        self.assertIs(value.last_sensor_result,result)
        self.assertEqual(value.sensor_completed_captures,1)

    def sensor(self, visible=True):
        value = fake_cell()
        rgb = np.zeros((480, 640, 3), dtype=np.uint8)
        if visible:
            # Exactly 0.4 before noise fails the >0.4 detector threshold.
            rgb[239:243, 318:322, 0] = 102
        depth = np.ones((480, 640), dtype=np.float32)
        value.render = Mock(return_value=(rgb, depth))
        value.noise_rng = SimpleNamespace(
            integers=Mock(return_value=np.array([[[1, -1, 0]]])),
            normal=Mock(return_value=.0005))
        value.model.camera = lambda name: SimpleNamespace(id=0)
        value.model.cam_fovy = np.array([48.])
        value.data.cam_xmat = np.array([np.eye(3).ravel()])
        value.data.cam_xpos = np.array([[.43, 0., 1.25]])
        value.actual_pos = Mock(side_effect=AssertionError('privileged truth read'))
        return value, rgb, depth

    def test_detector_uses_exact_retained_noisy_rgb_and_depth(self):
        value, raw_rgb, raw_depth = self.sensor()
        found, rgb, depth = value.sense()
        self.assertEqual([d['id'] for d in found], ['A1'])
        self.assertEqual(found[0]['pixels'], 16)
        self.assertEqual(raw_rgb[239, 318, 0], 102)
        self.assertEqual(rgb[239, 318, 0], 103)
        np.testing.assert_array_equal(depth, raw_depth + np.float32(.0005))
        self.assertIs(value.last_rgb, rgb)
        self.assertIs(value.last_depth, depth)
        focal = 480 / (2 * np.tan(np.deg2rad(48.) / 2))
        z = float(depth[240, 319])
        expected = [.43, -z / focal, 1.25-z-.0187]
        np.testing.assert_allclose(found[0]['pos'], expected, atol=1e-8)
        value.actual_pos.assert_not_called()

    def test_registry_does_not_create_a_detection_without_visible_pixels(self):
        value, _, _ = self.sensor(visible=False)
        found, _, _ = value.sense()
        self.assertEqual(found, [])
        value.actual_pos.assert_not_called()


class ProcessTests(unittest.TestCase):
    def accepted_cycle(self):
        value = fake_cell()
        value.registry.update({name:{'kind':'insert','family':name[-1],'half':[.025,.025,.008]}
                               for name in ('insert_A','insert_B')})
        value._insert_overlaps_fixture=Mock(side_effect=lambda name:name=='insert_A')
        value._physical_zone = Mock(return_value=True)
        response = value.submit({'operation': 'cycle', 'part_id': 'A1',
                                 'recipe': 'A', 'request_id': 'synthetic-cycle'})
        self.assertEqual(response['status'], 'accepted')
        self.assertTrue(value.station['busy'])
        self.assertFalse(value.truth['A1']['cycle_history'][0]['completed'])
        return value

    def test_interrupted_part_or_insert_seating_cannot_gain_processed_mark(self):
        for interrupted in ('A1', 'insert_A'):
            with self.subTest(interrupted=interrupted):
                value = self.accepted_cycle()
                original_mark = value.model.geom_rgba.copy()
                value._physical_zone.side_effect = lambda part, zone: part != interrupted
                value.data.time = 1.
                with patch.object(runtime_cell.mujoco, 'mj_step', side_effect=fake_step):
                    value.tick()
                    self.assertIsNone(value.cycle)
                    self.assertTrue(value.station['fault'])
                    self.assertFalse(value.station['busy'])
                    self.assertFalse(value.station['ready'])
                    # Restoring the seat later does not resurrect the process.
                    value._physical_zone.side_effect = None
                    value._physical_zone.return_value = True
                    value.data.time = 9.
                    value.tick()
                record = value.truth['A1']
                self.assertIsNone(record['recipe'])
                self.assertEqual(record['cycles'], 0)
                self.assertFalse(record['cycle_history'][0]['completed'])
                np.testing.assert_array_equal(value.model.geom_rgba, original_mark)
                self.assertEqual(len([e for e in value.events if e['type'] == 'cycle_fault']), 1)
                self.assertFalse(any(e['type'] == 'cycle_complete' for e in value.events))

    def test_uninterrupted_eligible_cycle_does_complete_and_change_mark(self):
        value = self.accepted_cycle()
        value.data.time = 8.
        with patch.object(runtime_cell.mujoco, 'mj_step', side_effect=fake_step):
            value.tick()
        record = value.truth['A1']
        self.assertEqual(record['recipe'], 'A')
        self.assertEqual(record['cycles'], 1)
        self.assertTrue(record['cycle_history'][0]['completed'])
        np.testing.assert_array_equal(value.model.geom_rgba[0], [1, 1, 1, 1])
        self.assertTrue(value.station['ready'])
        self.assertFalse(value.station['fault'])


class AuthorityTests(unittest.TestCase):
    def inspection(self):
        value=fake_cell();value._physical_zone=Mock(return_value=True)
        self.assertEqual(value.submit({'operation':'inspect','part_id':'A1','request_id':'inspection-old'})['status'],'accepted')
        return value

    def test_cancelled_inspection_never_finishes_a_replacement_motion(self):
        value=self.inspection()
        value.cancel('synthetic incarnation revoked')
        self.assertIsNone(value.inspection_due)
        value.active_request={'request_id':'motion-new'};value.lease_deadline=10.
        value.motion=[segment()];value.data.time=3.
        with patch.object(runtime_cell.mujoco,'mj_step',side_effect=fake_step):value.tick()
        self.assertEqual(value.active_request['request_id'],'motion-new')
        self.assertEqual(value.lease_deadline,10.)
        self.assertIsNotNone(value.segment)
        self.assertIsNone(value.inspection)
        self.assertEqual(value.truth['A1']['inspection_history'],[])
        self.assertEqual([(e['request_id'],e['status']) for e in value.feedback],[('inspection-old','cancelled')])

    def test_orphaned_timer_cannot_remove_new_request_or_lease(self):
        value=self.inspection()
        value.active_request={'request_id':'motion-new'};value.lease_deadline=10.
        value.data.time=3.
        with patch.object(runtime_cell.mujoco,'mj_step',side_effect=fake_step):value.tick()
        self.assertEqual(value.active_request['request_id'],'motion-new')
        self.assertEqual(value.lease_deadline,10.)
        self.assertIsNone(value.inspection_due)
        self.assertIsNone(value.inspection)
        self.assertEqual(value.feedback[-1]['request_id'],'inspection-old')
        self.assertEqual(value.feedback[-1]['status'],'cancelled')

    def test_normal_inspection_finishes_its_own_request(self):
        value=self.inspection()
        value.truth['A1'].update(recipe='A',cycles=1,cycle_history=[{'cycle_id':4}])
        value.data.time=1.999
        with patch.object(runtime_cell.mujoco,'mj_step',side_effect=fake_step):value.tick()
        self.assertIsNone(value.active_request)
        self.assertIsNone(value.lease_deadline)
        self.assertEqual(value.inspection,{'part_id':'A1','status':'pass','inspection_id':'inspection-old'})
        self.assertEqual(value.feedback[-1]['request_id'],'inspection-old')
        self.assertEqual(value.feedback[-1]['status'],'completed')
        self.assertEqual(value.truth['A1']['inspection_history'][-1]['cycle_id'],4)

    def test_cancel_keeps_grip_and_physical_velocity_unchanged(self):
        value=fake_cell();value.active_request={'request_id':'held-motion'}
        value.data.qpos[:7]=.3;value.data.qvel[:7]=.12;value.data.ctrl[7]=0.
        value.data.qpos[7:9]=.021
        value.cancel()
        np.testing.assert_array_equal(value.data.ctrl[:7],value.data.qpos[:7])
        np.testing.assert_array_equal(value.data.qvel[:7],np.full(7,.12))
        self.assertEqual(value.data.ctrl[7],0.)
        np.testing.assert_array_equal(value.data.qpos[7:9],[.021,.021])

    def test_cancelled_task_holds_last_issued_setpoint_and_discards_future_motion(self):
        value=fake_cell();value.active_request={'request_id':'held-motion'}
        value.data.qpos[:7]=.3;value.data.ctrl[:7]=.315;value.data.ctrl[7]=0.
        value.data.qvel[:7]=.12
        value.segment={'phase':4,'q':np.full(7,.6)}
        value.motion=[{'phase':5,'q':np.full(7,.9)}]
        value.cancel()
        np.testing.assert_array_equal(value.data.ctrl[:7],np.full(7,.315))
        np.testing.assert_array_equal(value.data.qvel[:7],np.full(7,.12))
        self.assertEqual(value.data.ctrl[7],0.)
        self.assertIsNone(value.segment);self.assertEqual(value.motion,[])
        self.assertIsNone(value.active_request)
        with patch.object(runtime_cell.mujoco,'mj_step',side_effect=fake_step):value.tick()
        np.testing.assert_array_equal(value.data.ctrl[:7],np.full(7,.315))

    def test_direct_effort_cancellation_does_not_retain_effort_equivalent_target(self):
        value=fake_cell();value.active_request={'request_id':'effort'}
        value.direct_command={'mode':'effort'}
        value.data.qpos[:7]=.3;value.data.ctrl[:7]=2.
        value.cancel()
        np.testing.assert_array_equal(value.data.ctrl[:7],value.data.qpos[:7])
        self.assertIsNone(value.direct_command)

    def test_public_receipt_window_uses_terminal_not_admission_time(self):
        value=fake_cell();value.active_request={'request_id':'long-transport'}
        value.data.time=55.;value.finish('completed','synthetic trajectory ended')
        value.data.time=114.99
        packet=value.public_packet({'version':1},'synthetic',1,1)
        self.assertEqual(packet['last_feedback']['request_id'],'long-transport')
        self.assertEqual(packet['last_feedback']['sim_time'],55.)
        value.data.time=115.01
        self.assertIsNone(value.public_packet({'version':1},'synthetic',1,1)['last_feedback'])

    def test_busy_rejection_preserves_request_correlation(self):
        value=fake_cell();value.active_request={'request_id':'old'}
        result=value.submit({'operation':'wait','request_id':'new'})
        self.assertEqual(result['request_id'],'new')
        self.assertEqual(result['status'],'rejected')
        self.assertEqual(value.active_request['request_id'],'old')


class DirectCompletionHoldTests(unittest.TestCase):
    def finished_command(self,mode):
        value=fake_cell()
        target=runtime_cell.HOME.copy();target[0]+=.015
        # A loaded position servo may settle away from its native target.
        # Copying this measured pose into ctrl at completion adds another sag.
        value.data.qpos[:7]=target+np.array([-.0004,.003,0.,-.0064,0.,-.001,0.])
        value.data.qvel[:7]=.001
        value.data.ctrl[:7]=target-.00001
        value.data.ctrl[7]=255.
        value.data.time=1.004  # first owner tick may overshoot the endpoint
        value.active_request={'request_id':'direct-endpoint'}
        value.lease_deadline=1.
        value.direct_command={'mode':mode,'end':1.,'points':[(0.,runtime_cell.HOME.copy()),(1.,target.copy())]}
        value.arm_adapter=SimpleNamespace(control=Mock(return_value=(target.copy(),None)))
        return value,target

    def test_normal_position_intervals_keep_exact_final_target_despite_measured_sag(self):
        for mode in ('position','trajectory','cartesian','velocity'):
            with self.subTest(mode=mode):
                value,target=self.finished_command(mode)
                command=value.direct_command
                measured=value.data.qpos.copy();velocity=value.data.qvel.copy()
                with patch.object(runtime_cell.mujoco,'mj_step',side_effect=fake_step):value.tick()
                value.arm_adapter.control.assert_called_once()
                args=value.arm_adapter.control.call_args.args
                self.assertIs(args[0],command);self.assertEqual(args[1],1.)
                np.testing.assert_array_equal(value.data.ctrl[:7],target)
                np.testing.assert_array_equal(value.data.qpos,measured)
                np.testing.assert_array_equal(value.data.qvel,velocity)
                self.assertEqual(value.data.ctrl[7],255.)
                self.assertIsNone(value.direct_command);self.assertIsNone(value.active_request)
                self.assertEqual(value.feedback[-1]['status'],'completed')
                self.assertIn('physical outcome requires observation',value.feedback[-1]['reason'])

    def test_effort_interval_ends_in_measured_pose_hold_without_reissuing_effort(self):
        value,_=self.finished_command('effort')
        measured=value.data.qpos.copy();velocity=value.data.qvel.copy()
        with patch.object(runtime_cell.mujoco,'mj_step',side_effect=fake_step):value.tick()
        value.arm_adapter.control.assert_not_called()
        np.testing.assert_array_equal(value.data.ctrl[:7],measured[:7])
        np.testing.assert_array_equal(value.data.qpos,measured)
        np.testing.assert_array_equal(value.data.qvel,velocity)
        self.assertIsNone(value.direct_command);self.assertIsNone(value.active_request)
        self.assertEqual(value.feedback[-1]['status'],'completed')


class CartesianContinuationTests(unittest.TestCase):
    def test_straight_leg_is_bounded_without_multiplying_the_duration_floor(self):
        value=fake_cell()
        value.ik=lambda target,q,configuration:np.zeros(7)
        start=np.array([.4,0.,.3]);end=np.array([.4,0.,.1])
        moves=value._task_segments(np.zeros(9),start,[(end,255)],1.)
        points=[start]+[m['cartesian_target'] for m in moves]
        self.assertGreater(len(moves),1)
        self.assertTrue(all(np.linalg.norm(b-a)<=.01+1e-12 for a,b in zip(points,points[1:])))
        self.assertTrue(all(np.allclose(p[:2],start[:2]) for p in points))
        np.testing.assert_allclose(points[-1],end)
        self.assertAlmostEqual(sum(m['duration'] for m in moves),.65)

    def test_intermediate_solver_failure_rejects_the_entire_plan(self):
        value=fake_cell();calls=[]
        def solve(target,q,configuration):
            calls.append(target.copy())
            if target[2]<.25:raise ValueError('unreachable intermediate point')
            return np.zeros(7)
        value.ik=solve
        with self.assertRaisesRegex(ValueError,'unreachable intermediate'):
            value._task_segments(np.zeros(9),np.array([.4,0.,.3]),[(np.array([.4,0.,.1]),255)],1.)
        self.assertGreater(len(calls),1)
        self.assertEqual(value.motion,[])

    def test_public_avoidance_still_checks_each_interpolated_leg(self):
        value=fake_cell()
        value.ikdata=SimpleNamespace(qpos=np.zeros(9),site_xpos=np.zeros((1,3)))
        value.ik=lambda target,q,configuration:np.r_[target,np.zeros(4)]
        def forward(model,data):data.site_xpos[0]=data.qpos[:3]
        configuration=np.zeros(9);configuration[:3]=[.1,.2,.3]
        with patch.object(runtime_cell.mujoco,'mj_forward',side_effect=forward):
            with self.assertRaisesRegex(ValueError,'avoidance constraint'):
                value._task_segments(configuration,np.array([.1,.2,.3]),[(np.array([.6,.2,.3]),0)],1.,avoid=['inspection'])


class HeldRecoveryTests(unittest.TestCase):
    def recovery(self):
        value=fake_cell();value.data.qpos[7:9]=.021
        value.last_detections=[]
        value.actual_pos=Mock(side_effect=AssertionError('protected object pose requested'))
        value.planner=SimpleNamespace(submit=Mock(return_value=Future()))
        return value

    def test_unknown_payload_recovery_uses_no_object_identity_or_truth(self):
        value=self.recovery();value.registry={};value.truth={}
        response=value.submit({'operation':'recover_held','destination':'parking1','request_id':'recover-unknown'})
        self.assertEqual(response['status'],'accepted')
        self.assertEqual(value.active_request['request_id'],'recover-unknown')
        _,snapshot,generation=value.planner.submit.call_args.args
        self.assertNotIn('part_id',snapshot)
        self.assertEqual(snapshot['grip'],0.)
        self.assertAlmostEqual(snapshot['release_height_m'],.021)
        self.assertEqual(generation,value.plan_generation)
        value.actual_pos.assert_not_called()

    def test_recovery_opens_only_after_transfer_and_lowering(self):
        value=self.recovery();points=[]
        def synthetic_ik(point,q,configuration):
            points.append(np.array(point));return np.zeros(7)
        value.ik=synthetic_ik
        snapshot={'configuration':value.data.qpos.copy(),'tcp':value.data.site_xpos[0].copy(),
                  'destination':'parking2','grip':0.,'release_height_m':.021}
        generation,moves=value._plan_recovery_snapshot(snapshot,9)
        self.assertEqual(generation,9)
        self.assertEqual(sorted(set(m['phase'] for m in moves)),list(range(20,26)))
        self.assertTrue(all(m['grip']==(0 if m['phase']<23 else 255) for m in moves))
        lowered=[m for m in moves if m['phase']==22][-1]
        released=[m for m in moves if m['phase']==23]
        self.assertEqual(len(released),1)
        np.testing.assert_allclose(lowered['cartesian_target'],np.r_[runtime_cell.ZONES['parking2'],.021])
        np.testing.assert_allclose(released[0]['q'],lowered['q'])
        np.testing.assert_allclose(moves[-1]['q'],runtime_cell.HOME)
        self.assertTrue(all(m['duration']>0 for m in moves))

    def test_recovery_requires_current_view_closed_command_and_empty_destination(self):
        conditions=[('stale',lambda v:setattr(v.data,'time',1.)),
                    ('open',lambda v:v.data.qpos.__setitem__(slice(7,9),.04)),
                    ('opening',lambda v:v.data.ctrl.__setitem__(7,255.)),
                    ('occupied',lambda v:v.last_detections.append({'id':'B2','zone':'parking1','pos':[.27,.05,.018]}))]
        for name,change in conditions:
            with self.subTest(name=name):
                value=self.recovery();change(value)
                result=value.submit({'operation':'recover_held','destination':'parking1','request_id':'recovery-invalid'})
                self.assertEqual(result['status'],'rejected')
                self.assertIsNone(value.active_request)
                value.planner.submit.assert_not_called()

    def test_recovery_cannot_deliver_directly_to_a_tray_or_busy_guard(self):
        value=self.recovery()
        result=value.submit({'operation':'recover_held','destination':'tray1','request_id':'bad-destination'})
        self.assertEqual(result['status'],'rejected')
        value.station['busy']=True;value.data.site_xpos[0,:2]=runtime_cell.ZONES['fixture']
        result=value.submit({'operation':'recover_held','destination':'parking1','request_id':'closed-guard'})
        self.assertEqual(result['status'],'rejected')
        value.planner.submit.assert_not_called()

    def test_visible_possible_payload_is_not_a_second_destination_occupant(self):
        value=self.recovery();value.data.site_xpos[0]=[.27,.05,.2]
        value.last_detections=[{'id':'unknown-visible','zone':'parking1','pos':[.27,.05,.2]}]
        result=value.submit({'operation':'recover_held','destination':'parking1','request_id':'recover-visible'})
        self.assertEqual(result['status'],'accepted')


if __name__ == '__main__':
    unittest.main()
