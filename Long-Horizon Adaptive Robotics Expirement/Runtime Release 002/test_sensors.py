"""Synthetic raw sensor boundary tests; no MuJoCo construction or renderer."""
import base64
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import zlib
import zipfile

import numpy as np
from sensors import CAMERAS, MAX_LINE_BYTES, RawSensorGateway, encode_response, _depth_npz_lzma


class Clock:
    def __init__(self):
        self.value = 10.

    def __call__(self):
        return self.value


def fake_cell():
    rgb = np.arange(12 * 16 * 3, dtype=np.uint8).reshape(12, 16, 3)
    depth = np.full((12, 16), 1.25, dtype=np.float32)
    data = SimpleNamespace(time=2., qpos=np.arange(9, dtype=float)/100,
                           qvel=np.arange(9, dtype=float)/10,
                           actuator_force=np.arange(8, dtype=float),
                           cam_xmat=np.tile(np.eye(3).ravel(), (3, 1)),
                           cam_xpos=np.array([[.43, 0., 1.25], [1.05, -.85, .95], [.1, .2, .3]]))
    model = SimpleNamespace(camera=lambda name: SimpleNamespace(id=CAMERAS.index(name)),
                            cam_fovy=np.array([48., 48., 70.]))
    return SimpleNamespace(data=data, model=model, last_rgb=rgb, last_depth=depth,
                           detection_time=2., render=Mock(return_value=(rgb.copy(), depth.copy())))


def decode_our_png(content):
    """Small independent decoder for the emitted PNG subset; also checks CRCs."""
    assert content[:8] == b'\x89PNG\r\n\x1a\n'
    offset, blocks, shape = 8, [], None
    while offset < len(content):
        length = struct.unpack('!I', content[offset:offset+4])[0]
        tag = content[offset+4:offset+8]
        data = content[offset+8:offset+8+length]
        crc = struct.unpack('!I', content[offset+8+length:offset+12+length])[0]
        assert zlib.crc32(tag+data) == crc
        if tag == b'IHDR':
            width, height = struct.unpack('!2I', data[:8])
            shape = height, width, 3
        if tag == b'IDAT':
            blocks.append(data)
        offset += length+12
    height, width, _ = shape
    rows = np.frombuffer(zlib.decompress(b''.join(blocks)), np.uint8).reshape(height, 1+width*3)
    assert not rows[:, 0].any()
    return rows[:, 1:].reshape(shape)


class SensorGatewayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cell = fake_cell()
        self.clock = Clock()
        self.gateway = RawSensorGateway(self.cell, self.root, clock=self.clock)

    def request(self, camera='overhead', **extra):
        return {'type': 'sensor_request', 'request_id': 'synthetic request', 'camera': camera, **extra}

    def test_exact_native_bytes_metadata_and_server_owned_artifacts(self):
        capture = self.gateway.cache_overhead(capture_wall_elapsed_s=1.7)
        expected_rgb = self.cell.last_rgb.copy()
        expected_depth = self.cell.last_depth.copy()
        # Mutating live state after registration cannot backdate telemetry or
        # alter the registered image. Current telemetry is separately exposed.
        self.cell.last_rgb[:] = 0
        self.cell.last_depth[:] = 3.
        self.cell.data.cam_xpos[0] = [9, 9, 9]
        self.cell.data.qpos[0] = .75
        self.cell.data.time = 2.2
        response = self.gateway.handle(self.request(), wall_elapsed_s=1.9)
        self.assertEqual(response['status'], 'ok')
        self.assertEqual(response['origin'], 'cached')
        self.assertEqual(response['freshness'], 'prior_capture')
        self.assertAlmostEqual(response['age_sim_s'], .2)
        self.assertEqual(response['capture_id'], capture)
        self.assertEqual(response['capture_sim_tick'], 1000)
        self.assertEqual(response['capture_wall_elapsed_s'], 1.7)
        self.assertEqual(response['capture_telemetry']['joint_position_rad'][0], 0.)
        self.assertEqual(response['current_telemetry']['joint_position_rad'][0], .75)
        self.assertEqual(response['calibration']['camera_position_world_m'], [.43, 0., 1.25])
        matrix = response['calibration']['intrinsics_px']
        self.assertAlmostEqual(matrix[0][0], 12/(2*np.tan(np.deg2rad(48)/2)))
        self.assertEqual((matrix[0][2], matrix[1][2]), (7.5, 5.5))
        self.assertNotIn('registry', response)
        self.assertNotIn('objects', response)
        for name, image in response['images'].items():
            raw = base64.b64decode(image['data'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), image['sha256'])
            ref = self.gateway.last_evidence['artifacts'][name]
            self.assertTrue(ref['relative_path'].startswith('raw-sensors/'))
            self.assertEqual((self.root/ref['relative_path']).read_bytes(), raw)
        np.testing.assert_array_equal(decode_our_png(base64.b64decode(response['images']['rgb']['data'])), expected_rgb)
        with np.load(io.BytesIO(base64.b64decode(response['images']['depth']['data'])), allow_pickle=False) as archive:
            self.assertEqual(archive.files, ['depth_m'])
            np.testing.assert_array_equal(archive['depth_m'], expected_depth)
        line = self.gateway.encode_response(response)
        self.assertLess(len(line), 1024*1024)
        self.assertEqual(json.loads(line), response)
        self.cell.render.assert_not_called()

    def test_overhead_requires_simultaneous_registered_metadata(self):
        response = self.gateway.handle(self.request())
        self.assertEqual(response['status'], 'unavailable')
        self.cell.data.time += .002
        with self.assertRaisesRegex(ValueError, 'immediately after sense'):
            self.gateway.cache_overhead()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_on_demand_camera_uses_own_pose_and_explicit_noise_metadata(self):
        response = self.gateway.handle(self.request('wrist', modalities=['depth']), wall_elapsed_s=1.5)
        self.cell.render.assert_called_once_with('wrist')
        self.assertEqual(response['status'], 'ok')
        self.assertEqual(response['origin'], 'on_demand')
        self.assertEqual(response['freshness'], 'same_sim_tick')
        self.assertEqual(response['calibration']['camera_position_world_m'], [.1, .2, .3])
        self.assertEqual(response['calibration']['vertical_fov_deg'], 70.)
        self.assertIn('no additional readout noise', response['readout'])
        self.assertEqual(list(response['images']), ['depth'])

    def test_rate_limit_is_per_camera_and_uses_host_monotonic_clock(self):
        first = self.gateway.handle(self.request('wrist'))
        self.assertEqual(first['status'], 'ok')
        self.cell.data.time += 100
        self.clock.value += .099
        denied = self.gateway.handle(self.request('wrist'), wall_elapsed_s=9999.)
        self.assertEqual(denied['status'], 'rate_limited')
        self.assertNotIn('images', denied)
        self.assertIsNone(self.gateway.last_evidence)
        self.assertEqual(self.cell.render.call_count, 1)
        self.assertEqual(self.gateway.handle(self.request('oblique'))['status'], 'ok')
        self.clock.value += .002
        self.assertEqual(self.gateway.handle(self.request('wrist'))['status'], 'ok')
        self.assertEqual(self.cell.render.call_count, 3)

    def test_unknown_paths_urls_cameras_and_bad_modalities_are_rejected(self):
        for request in [self.request(path='../sentinel'), self.request(url='file:///secret'),
                        self.request('unknown'), self.request(modalities=[]),
                        self.request(modalities=['rgb', 'rgb']), self.request(modalities=[{}]),
                        self.request(modalities='rgb'), {**self.request(), 'request_id': 'x'*129}, None]:
            with self.subTest(request=request):
                response = self.gateway.handle(request)
                self.assertEqual(response['status'], 'invalid_request')
                self.assertLess(len(self.gateway.encode_response(response)), MAX_LINE_BYTES)
        self.cell.render.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_incompressible_native_capture_fails_explicitly_under_line_cap(self):
        rng = np.random.default_rng(41)
        rgb = rng.integers(0, 256, size=(480, 640, 3), dtype=np.uint8)
        depth = rng.uniform(.1, 10., size=(480, 640)).astype(np.float32)
        self.cell.render.return_value = (rgb, depth)
        response = self.gateway.handle(self.request('oblique'))
        self.assertEqual(response['status'], 'payload_too_large')
        self.assertNotIn('images', response)
        self.assertIsNone(self.gateway.last_evidence)
        self.assertLess(len(self.gateway.encode_response(response)), MAX_LINE_BYTES)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_response_encoder_counts_unicode_and_newline_and_rejects_nonfinite(self):
        with self.assertRaisesRegex(ValueError, 'exceeds'):
            encode_response({'text': 'Ω'*1000}, 4096)
        with self.assertRaises(ValueError):
            encode_response({'value': float('nan')})
        self.assertTrue(encode_response({'ok': True}).endswith(b'\n'))

    def test_repeated_cached_capture_reuses_immutable_artifact_paths(self):
        self.gateway.cache_overhead()
        first = self.gateway.handle(self.request())
        refs = self.gateway.last_evidence['artifacts']
        self.clock.value += .11
        second = self.gateway.handle(self.request())
        self.assertEqual(first['capture_id'], second['capture_id'])
        self.assertEqual(refs, self.gateway.last_evidence['artifacts'])
        self.assertEqual(len(list((self.root/'raw-sensors').iterdir())), 2)

    def test_backend_failure_cannot_expose_paths_or_return_unrecorded_images(self):
        self.cell.render.side_effect = RuntimeError('private C:/project/evaluator/sentinel')
        response = self.gateway.handle(self.request('wrist'))
        self.assertEqual(response['status'], 'unavailable')
        self.assertNotIn('sentinel', json.dumps(response))
        self.assertNotIn('images', response)
        self.assertIsNone(self.gateway.last_evidence)

    def completed_result(self, camera='wrist', artifacts=None):
        # Explicitly synthetic SensorResult-shaped fixture; no camera executes.
        capture = self.gateway._capture(camera, self.cell.last_rgb, self.cell.last_depth,
                                         1.4, 'test-only fixture')
        return SimpleNamespace(camera=camera, sequence=12, rgb=capture.rgb, depth=capture.depth,
                               capture_sim_time_s=2., capture_wall_elapsed_s=1.4,
                               calibration=capture.metadata['calibration'],
                               capture_telemetry=capture.metadata['capture_telemetry'],
                               artifacts=artifacts or {})

    def test_async_cache_preserves_pose_and_encodes_without_cell_or_render_access(self):
        result = self.completed_result()
        expected_calibration = json.loads(json.dumps(result.calibration))
        self.gateway.cache_result(result, readout='synthetic test offset')
        result.calibration['camera_position_world_m'][0] = 99
        result.rgb[:] = 0
        current = {'sim_time_s': 2.25, 'joint_position_rad': [.5]*7}
        class ForbiddenCell:
            def __getattribute__(self, name):
                raise AssertionError('encoding accessed live Cell: '+name)
        self.gateway.cell = ForbiddenCell()
        request = self.request('wrist')
        self.assertEqual(self.gateway.admit_request(request, wall_elapsed_s=1.5)['status'], 'accepted')
        response = json.loads(self.gateway.encode_cached_request(request, wall_elapsed_s=1.8,
                                                                  current_telemetry=current))
        self.assertEqual(response['status'], 'ok')
        self.assertEqual(response['calibration'], expected_calibration)
        self.assertEqual(response['capture_telemetry']['sim_time_s'], 2.)
        self.assertEqual(response['current_telemetry'], current)
        self.assertEqual(response['origin'], 'cached_async')
        self.assertEqual(response['age_sim_s'], .25)
        self.assertAlmostEqual(response['age_wall_s_at_delivery'], .4)
        self.assertEqual(response['request_wall_elapsed_s'], 1.5)
        self.assertEqual(response['capture_sequence'], 12)
        self.assertEqual(self.gateway._admissions, {})
        self.assertTrue(decode_our_png(base64.b64decode(response['images']['rgb']['data'])).any())
        self.cell.render.assert_not_called()

    def test_delivery_telemetry_is_explicitly_unknown_when_not_supplied(self):
        self.gateway.cache_result(self.completed_result('oblique'))
        response = json.loads(self.gateway.encode_cached_request(self.request('oblique'), wall_elapsed_s=1.8))
        self.assertEqual(response['status'], 'ok')
        self.assertIsNone(response['current_telemetry'])
        self.assertIsNone(response['age_sim_s'])
        self.assertEqual(response['freshness'], 'delivery_age_unknown')
        self.assertIn('unrecorded', response['readout'])
        self.assertEqual(response['capture_telemetry']['sim_time_s'], 2.)

    def test_admission_caps_apply_before_scheduling_and_are_not_charged_twice(self):
        request = self.request('wrist')
        self.assertEqual(self.gateway.admit_request(request)['status'], 'accepted')
        self.assertEqual(self.gateway.admit_request(request)['status'], 'rate_limited')
        self.clock.value += .11
        self.assertEqual(self.gateway.admit_request({**request, 'request_id': 'new'})['status'], 'busy')
        self.gateway.cache_result(self.completed_result())
        response = json.loads(self.gateway.encode_cached_request(request))
        self.assertEqual(response['status'], 'ok')
        self.assertEqual(self.gateway.admit_request({**request, 'request_id': 'new'})['status'], 'rate_limited')
        self.clock.value += .11
        self.assertEqual(self.gateway.admit_request({**request, 'request_id': 'new'})['status'], 'accepted')
        cancelled = self.gateway.cancel_admission('new')
        self.assertEqual(cancelled['status'], 'unavailable')
        self.assertEqual(self.gateway._admissions, {})
        self.cell.render.assert_not_called()

    def test_admission_cannot_be_reused_with_a_different_camera_or_modalities(self):
        request = self.request('wrist', modalities=['rgb'])
        self.gateway.admit_request(request)
        changed = json.loads(self.gateway.encode_cached_request({**request, 'modalities': ['depth']}))
        self.assertEqual(changed['status'], 'invalid_request')
        self.assertEqual(len(self.gateway._admissions), 1)
        self.gateway.cancel_admission(request['request_id'])

    def test_existing_worker_evidence_is_reused_and_hash_checked(self):
        from sensor_worker import write_sensor_evidence
        result = self.completed_result()
        result.artifacts = write_sensor_evidence(result.rgb, result.depth,
                                                 self.root/'source.png', self.root/'source-depth.npz')
        self.gateway.cache_result(result)
        response = json.loads(self.gateway.encode_cached_request(self.request('wrist')))
        self.assertEqual(response['status'], 'ok')
        self.assertEqual(self.gateway.last_evidence['artifacts']['rgb']['relative_path'], 'source.png')
        self.assertFalse((self.root/'raw-sensors').exists())
        result.artifacts['rgb']['sha256'] = '0'*64
        self.gateway.cache_result(result)
        self.clock.value += .11
        rejected = json.loads(self.gateway.encode_cached_request(self.request('wrist')))
        self.assertEqual(rejected['status'], 'unavailable')
        self.assertIsNone(self.gateway.last_evidence)

    def test_cache_rejects_bad_metadata_and_artifact_escape(self):
        result = self.completed_result()
        result.capture_telemetry['sim_time_s'] = 3.
        with self.assertRaisesRegex(ValueError, 'clock'):
            self.gateway.cache_result(result)
        result = self.completed_result()
        result.artifacts = {'rgb': {'path': str(self.root.parent/'outside.png'), 'bytes': 10, 'sha256': '0'*64}}
        with self.assertRaises(ValueError):
            self.gateway.cache_result(result)

    def test_cached_encoding_reports_missing_camera_and_preserves_size_cap(self):
        response = json.loads(self.gateway.encode_cached_request(self.request('oblique')))
        self.assertEqual(response['status'], 'unavailable')
        self.assertEqual(self.gateway._admissions, {})
        rng = np.random.default_rng(17)
        self.cell.last_rgb = rng.integers(0, 256, size=(480, 640, 3), dtype=np.uint8)
        self.cell.last_depth = rng.uniform(.1, 10., size=(480, 640)).astype(np.float32)
        result = self.completed_result()
        self.gateway.cache_result(result)
        raw = self.gateway.encode_cached_request(self.request('wrist'))
        self.assertLess(len(raw), 1024*1024)
        self.assertEqual(json.loads(raw)['status'], 'payload_too_large')
        self.cell.render.assert_not_called()

    def test_lossless_npz_fallback_keeps_native_bytes_and_distinct_wire_artifact(self):
        from sensor_worker import write_sensor_evidence
        self.gateway=RawSensorGateway(self.cell,self.root,clock=self.clock,max_line_bytes=30000)
        self.cell.last_rgb=np.zeros((128,128,3),dtype=np.uint8)
        self.cell.last_depth=(np.arange(128*128,dtype=np.float32)*np.float32(.00001)+np.float32(.4)).reshape(128,128)
        result=self.completed_result()
        result.artifacts=write_sensor_evidence(result.rgb,result.depth,self.root/'original.png',self.root/'original-depth.npz')
        original=(self.root/'original-depth.npz').read_bytes()
        capture_id=self.gateway.cache_result(result)
        response=json.loads(self.gateway.encode_cached_request(self.request('wrist')))
        self.assertEqual(response['status'],'ok')
        self.assertLess(len(encode_response(response,30000)),30000)
        self.assertEqual(response['capture_id'],capture_id)
        self.assertEqual(response['capture_sim_time_s'],result.capture_sim_time_s)
        self.assertEqual(response['calibration'],result.calibration)
        self.assertEqual(response['images']['depth']['npz_compression'],'lzma')
        packed=base64.b64decode(response['images']['depth']['data'])
        with zipfile.ZipFile(io.BytesIO(packed)) as archive:
            self.assertEqual(archive.getinfo('depth_m.npy').compress_type,zipfile.ZIP_LZMA)
            wire_npy=archive.read('depth_m.npy')
        with zipfile.ZipFile(io.BytesIO(original)) as archive:
            self.assertEqual(wire_npy,archive.read('depth_m.npy'))
        with np.load(io.BytesIO(packed),allow_pickle=False) as archive:
            self.assertEqual(archive['depth_m'].tobytes(),result.depth.tobytes())
        evidence=self.gateway.last_evidence
        self.assertEqual(evidence['source_artifacts']['depth']['relative_path'],'original-depth.npz')
        self.assertNotEqual(evidence['source_artifacts']['depth']['sha256'],evidence['artifacts']['depth']['sha256'])
        self.assertEqual((self.root/evidence['artifacts']['depth']['relative_path']).read_bytes(),packed)
        self.assertEqual((self.root/'original-depth.npz').read_bytes(),original)
        fixture_path=Path(__file__).resolve().parent.parent/'Batch 01'/'Calibration Tools'/'raw_camera_fixture.py'
        spec=importlib.util.spec_from_file_location('synthetic_raw_camera_decoder',fixture_path)
        fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
        decoded=fixture.inspect_response(response)
        self.assertEqual(decoded['images']['depth']['decoded_sha256'],hashlib.sha256(result.depth.tobytes()).hexdigest())
        self.clock.value+=.11
        repeated=json.loads(self.gateway.encode_cached_request(self.request('wrist')))
        self.assertEqual(repeated['images']['depth']['sha256'],response['images']['depth']['sha256'])
        self.assertEqual(len(list((self.root/'raw-sensors').iterdir())),1)
        self.cell.render.assert_not_called()

    def test_lzma_npz_is_deterministic_and_does_not_quantize_float_bits(self):
        depth=np.array([[.123456789,1.0000001],[30.125,1000.]],dtype=np.float32)
        first=_depth_npz_lzma(depth);self.assertEqual(first,_depth_npz_lzma(depth))
        with np.load(io.BytesIO(first),allow_pickle=False) as archive:
            self.assertEqual(archive['depth_m'].tobytes(),depth.tobytes())


if __name__ == '__main__':
    unittest.main()
