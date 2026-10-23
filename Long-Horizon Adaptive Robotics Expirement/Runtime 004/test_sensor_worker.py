"""Synthetic thread/snapshot/backpressure tests, no real rendering or physics."""
import copy
from dataclasses import FrozenInstanceError
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

import numpy as np
import sensor_worker as sw
from cell import Cell, build_scene
from test_cell import fake_cell, fake_step


class Model:
    def __init__(self):
        self.geom_rgba = np.array([[.03, .03, .03, 1.]])
        self.mat_rgba = np.array([[.2, .3, .4, 1.]])
        self.cam_fovy = np.array([48.])

    def __copy__(self):
        result = Model()
        for key, value in vars(self).items():
            setattr(result, key, value.copy())
        return result

    def camera(self, name):
        return SimpleNamespace(id=0)


def data():
    return SimpleNamespace(time=2., qpos=np.arange(9, dtype=float)/100,
                           qvel=np.zeros(9), actuator_force=np.zeros(8),
                           cam_xmat=np.array([np.eye(3).ravel()]),
                           cam_xpos=np.array([[.43, 0., 1.25]]))


class SensorWorkerTests(unittest.TestCase):
    def setUp(self):
        self.model, self.data = Model(), data()
        self.threads, self.seen = [], []
        self.entered, self.release = threading.Event(), threading.Event()
        self.release.set()
        self.render_fail = False
        owner = self

        class Renderer:
            def __init__(self, model, height, width):
                self.model = model
                self.depth = False
                owner.threads.append(('create', threading.get_ident()))

            def disable_depth_rendering(self):
                owner.threads.append(('disable', threading.get_ident()))
                self.depth = False

            def enable_depth_rendering(self):
                owner.threads.append(('enable', threading.get_ident()))
                self.depth = True

            def update_scene(self, snapshot, camera):
                owner.threads.append(('scene', threading.get_ident()))
                owner.entered.set()
                if not owner.release.wait(2):
                    raise TimeoutError('synthetic renderer release missing')
                owner.seen.append((copy.deepcopy(snapshot), self.model.geom_rgba.copy()))
                if owner.render_fail:
                    raise RuntimeError('synthetic render failure')

            def render(self):
                owner.threads.append(('render', threading.get_ident()))
                if self.depth:
                    return np.ones((480, 640), np.float32)
                rgb = np.zeros((480, 640, 3), np.uint8)
                rgb[239:243, 318:322, 0] = 102
                return rgb

            def close(self):
                owner.threads.append(('close', threading.get_ident()))

        self.registry = {'A1': {'family': 'A', 'hue': 0., 'half': [.021, .021, .018], 'kind': 'part'}}
        self.worker = sw.SensorWorker(self.model, self.registry, {}, {}, renderer_factory=Renderer)
        self.addCleanup(self.worker.close)
        self.copy_patch = patch.object(sw, '_copy_data', side_effect=lambda model, source: copy.deepcopy(source))
        self.copy_patch.start()
        self.addCleanup(self.copy_patch.stop)

    def request(self, **kwargs):
        return self.worker.request(self.model, self.data, sequence=7, capture_wall_elapsed_s=1.5,
                                   rgb_offset=np.array([[[1, -1, 0]]]), depth_offset=.0005, **kwargs)

    def test_worker_owns_gl_and_io_and_result_is_an_isolated_snapshot(self):
        self.release.clear()
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        original_write = sw.write_sensor_evidence

        def tracked_write(*args):
            self.threads.append(('write', threading.get_ident()))
            return original_write(*args)

        with patch.object(sw, 'write_sensor_evidence', side_effect=tracked_write):
            try:
                self.assertTrue(self.request(rgb_path=root/'frame.png', depth_path=root/'depth.npz'))
                self.assertTrue(self.entered.wait(1))
                self.assertIsNone(self.worker.poll())
                self.assertFalse(self.request())
                self.data.time = 5.
                self.data.qpos[0] = 99
                self.data.cam_xpos[0] = [9, 9, 9]
                self.model.geom_rgba[:] = 1
                self.release.set()
                result = self.worker.wait()
            finally:
                self.release.set()
        self.worker.close()
        self.assertEqual(len({thread for _, thread in self.threads}), 1)
        self.assertNotEqual(self.threads[0][1], threading.get_ident())
        self.assertEqual(self.threads[-1][0], 'close')
        self.assertTrue(any(kind == 'write' for kind, _ in self.threads))
        snapshot, colours = self.seen[0]
        self.assertEqual(snapshot.time, 2.)
        self.assertEqual(snapshot.qpos[0], 0.)
        np.testing.assert_array_equal(colours, [[.03, .03, .03, 1.]])
        self.assertEqual(result.capture_sim_time_s, 2.)
        self.assertEqual(result.capture_wall_elapsed_s, 1.5)
        self.assertEqual(result.calibration['camera_position_world_m'], [.43, 0., 1.25])
        self.assertEqual(result.capture_telemetry['joint_position_rad'][0], 0.)
        self.assertEqual(result.detections[0]['pixels'], 16)
        self.assertEqual(result.rgb[239, 318, 0], 103)
        self.assertEqual(result.depth[240, 319], np.float32(1.0005))
        with self.assertRaises(ValueError):
            result.rgb.setflags(write=True)
        with self.assertRaises(FrozenInstanceError):
            result.sequence = 99
        mutated = result.detections
        mutated[0]['pos'][0] = 999
        self.assertNotEqual(result.detections[0]['pos'][0], 999)
        for artifact in result.artifacts.values():
            self.assertTrue(Path(artifact['path']).is_file())
        with np.load(root/'depth.npz', allow_pickle=False) as archive:
            np.testing.assert_array_equal(archive['depth_m'], result.depth)

    def test_completed_unpolled_capture_still_applies_backpressure(self):
        self.assertTrue(self.request())
        self.worker._future.result(timeout=2)
        self.assertFalse(self.request())
        self.assertIsNotNone(self.worker.poll())
        self.assertTrue(self.request())
        self.assertIsNotNone(self.worker.wait())

    def test_failed_job_is_explicit_and_close_remains_on_render_thread(self):
        self.render_fail = True
        self.request()
        with self.assertRaisesRegex(RuntimeError, 'synthetic render failure'):
            self.worker.wait()
        self.assertFalse(self.worker.busy)
        self.worker.close()
        self.assertEqual(len({thread for _, thread in self.threads}), 1)
        self.assertEqual(self.threads[-1][0], 'close')

    def test_cell_reports_missed_capture_without_noise_or_copy_work(self):
        value = fake_cell()
        value.sensor_worker = SimpleNamespace(busy=True)
        value.sensor_missed_captures = 0
        value.noise_rng = Mock()
        status = value.request_sense(sequence=13, capture_wall_elapsed_s=2.)
        self.assertFalse(status['accepted'])
        self.assertEqual(status['sequence'], 13)
        self.assertEqual(value.sensor_missed_captures, 1)
        self.assertEqual(value.events[-1]['type'], 'sensor_capture_missed')
        value.noise_rng.integers.assert_not_called()

    def test_cell_applies_original_capture_age_and_not_current_time(self):
        self.request()
        result = self.worker.wait()
        value = fake_cell()
        value.data.time = 5.
        value.sensor_worker = SimpleNamespace(poll=Mock(return_value=result))
        value.sensor_completed_captures = 0
        self.assertIs(value.poll_sense(), result)
        self.assertEqual(value.detection_time, 2.)
        self.assertEqual(value.data.time-value.detection_time, 3.)
        self.assertIs(value.last_rgb, result.rgb)
        self.assertEqual(value.sensor_completed_captures, 1)

    def test_setup_end_does_not_sense_and_requires_post_motion_fresh_capture(self):
        value = fake_cell()
        value.data.time = 1.
        value.active_request = {'request_id': 'setup-synthetic', 'setup_pending': 'insert_B',
                                'setup_returning': {'id': 'insert_A', 'home': 'insert_home_A'}}
        value.registry['insert_A'] = {'family': 'A', 'half': [.025,.025,.008], 'kind': 'insert'}
        value.last_detections = [{'id':'insert_A','family':'A','kind':'insert',
                                 'zone':'insert_home_A','pos':[.18,-.25,.008],'uncertainty_m':.004}]
        value.data.qpos[7:9] = .04
        value.lease_deadline = 4.
        value.segment = {'q': np.zeros(7), 'q0': np.zeros(7), 'grip': 255,
                         'duration': .5, 'phase': 9, 'start': 0.}
        value.sense = Mock(side_effect=AssertionError('blocking sense in tick'))
        value.plan_transport = Mock()
        with patch('cell.mujoco.mj_step', side_effect=fake_step):
            value.tick()
        value.sense.assert_not_called()
        value.plan_transport.assert_not_called()
        self.assertEqual(value.events[-1]['type'], 'setup_waiting_for_fresh_capture')
        value.detection_time = .9
        self.assertFalse(value.resume_setup_if_fresh())
        value.detection_time = 1.001
        self.assertTrue(value.resume_setup_if_fresh())
        value.plan_transport.assert_called_once_with('insert_B', 'fixture')
        self.assertNotIn('setup_pending', value.active_request)

    def test_layout_seed_changes_layout_without_world_material_or_palette_changes(self):
        a, registry_a = build_scene(3, seed=9, layout_seed=17)
        b, registry_b = build_scene(3, seed=9, layout_seed=18)
        root_a, root_b = ET.fromstring(a), ET.fromstring(b)
        self.assertEqual(registry_a, registry_b)
        self.assertNotEqual(root_a.find(".//body[@name='A1']").get('pos'),
                            root_b.find(".//body[@name='A1']").get('pos'))
        for name in ('A1', 'B2', 'A3'):
            self.assertEqual(root_a.find(".//geom[@name='part_"+name+"']").attrib,
                             root_b.find(".//geom[@name='part_"+name+"']").attrib)

    def test_clear_view_is_candidate_requested_async_and_publicly_guarded(self):
        value = fake_cell()
        value.data.qpos[7:9] = .04
        value.planner = Mock()
        action = {'operation': 'observe', 'clear_view': True, 'request_id': 'clear-synthetic',
                  'order_version': 1, 'incarnation': 2}
        response = value.submit(action)
        self.assertEqual(response['status'], 'accepted')
        self.assertEqual(value.active_request, action)
        self.assertEqual(value.feedback, [])
        value.planner.submit.assert_called_once()
        _, snapshot, generation = value.planner.submit.call_args.args
        self.assertEqual(set(snapshot), {'configuration', 'tcp'})
        self.assertEqual(generation, 0)
        self.assertEqual(value.lease_deadline, 2.)
        for reason in ('closed', 'visible_holding', 'stale'):
            candidate = fake_cell()
            candidate.data.qpos[7:9] = .04
            candidate.planner = Mock()
            if reason == 'closed':candidate.data.qpos[7:9] = .01
            if reason == 'visible_holding':candidate.last_detections[0]['pos'] = [.4, 0., .4]
            if reason == 'stale':candidate.data.time = 1.
            self.assertEqual(candidate.submit(action)['status'], 'rejected')
            candidate.planner.submit.assert_not_called()

    def test_clear_view_plan_lifts_then_returns_home_with_open_jaws(self):
        value = fake_cell()
        value.ik = Mock(return_value=np.ones(7)*.1)
        snapshot = {'configuration': np.zeros(9), 'tcp': np.array([.57, 0., .19])}
        generation, segments = value._plan_clear_view_snapshot(snapshot, 7)
        self.assertEqual(generation, 7)
        np.testing.assert_allclose(value.ik.call_args.args[0], [.57, 0., .35])
        self.assertEqual(sorted(set(s['phase'] for s in segments)), [10, 11])
        self.assertTrue(all(s['grip']==255 for s in segments))
        lift=[s for s in segments if s['phase']==10]
        self.assertTrue(all(np.allclose(s['cartesian_target'][:2],[.57,0.]) for s in lift))
        np.testing.assert_allclose(lift[-1]['cartesian_target'],[.57,0.,.35])
        from cell import HOME
        np.testing.assert_array_equal(segments[-1]['q'], HOME)


if __name__ == '__main__':
    unittest.main()
