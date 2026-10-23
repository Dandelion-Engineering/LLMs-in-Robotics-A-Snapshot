"""Bounded raw camera replies for the supervisor; never import in a candidate.

Integration: create RawSensorGateway on the physics/render owning thread. Call
cache_overhead immediately after Cell.sense(), before physics advances. Handle
candidate sensor_request dictionaries here, then send encode_response(reply).
The encoded line includes its newline and is at most MAX_LINE_BYTES. If native
lossless data cannot fit, the reply is payload_too_large (no silent resampling).

On-demand rendering is synchronous on that same thread; its measured wall cost
must count toward the supervisor timing gate. This helper does not establish a
render-time bound, readiness, model image consumption, or candidate authority.
Camera axes follow https://mujoco.readthedocs.io/en/stable/programming/visualization.html

Timed integration: admit_request before scheduling -> cache_result after shared
SensorWorker completion -> encode_cached_request in a bounded, serial encoding
worker. Cached encoding performs compression/IO but never reads Cell or renders.
Pass current_telemetry copied on the owner thread if delivery-time joint state
and simulation age are required; otherwise these are explicitly unavailable.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import time
from typing import Callable
import uuid
import zipfile
import zlib

import numpy as np

MAX_LINE_BYTES = 1024 * 1024 - 1
CAMERAS = ('overhead', 'oblique', 'wrist')
SENSOR_REQUEST_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['type', 'request_id', 'camera'],
    'properties': {
        'type': {'const': 'sensor_request'},
        'request_id': {'type': 'string', 'minLength': 1, 'maxLength': 128},
        'camera': {'enum': list(CAMERAS)},
        'modalities': {'type': 'array', 'minItems': 1, 'maxItems': 2,
                       'uniqueItems': True, 'items': {'enum': ['rgb', 'depth']}},
    },
}


def validate_request(request):
    if not isinstance(request, dict):
        raise ValueError('request must be an object')
    if set(request) - {'type', 'request_id', 'camera', 'modalities'}:
        raise ValueError('unknown request fields; paths and URLs are not accepted')
    if request.get('type') != 'sensor_request':
        raise ValueError('type must be sensor_request')
    request_id = request.get('request_id')
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128:
        raise ValueError('request_id must contain 1 to 128 characters')
    if request.get('camera') not in CAMERAS:
        raise ValueError('camera must be overhead, oblique or wrist')
    modalities = request.get('modalities', ['rgb', 'depth'])
    if (not isinstance(modalities, list) or not 1 <= len(modalities) <= 2
            or any(not isinstance(m, str) or m not in ('rgb', 'depth') for m in modalities)
            or len(set(modalities)) != len(modalities)):
        raise ValueError('modalities must be a unique nonempty list of rgb and/or depth')
    return request_id, request['camera'], modalities


def encode_response(response, max_line_bytes=MAX_LINE_BYTES):
    """Return the exact UTF-8 JSON IPC line, enforcing its complete byte budget."""
    if not 4096 <= max_line_bytes <= MAX_LINE_BYTES:
        raise ValueError('line limit must be between 4096 bytes and 1 MiB')
    line = (json.dumps(response, separators=(',', ':'), ensure_ascii=True,
                       allow_nan=False) + '\n').encode('utf-8')
    if len(line) > max_line_bytes:
        raise ValueError('encoded sensor response exceeds IPC line budget')
    return line


def _png(rgb):
    height, width, _ = rgb.shape
    def chunk(tag, data):
        return (struct.pack('!I', len(data)) + tag + data
                + struct.pack('!I', zlib.crc32(tag + data)))
    scanlines = b''.join(b'\0' + row.tobytes() for row in rgb)
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(scanlines)) + chunk(b'IEND', b''))


def _depth_npz_lzma(depth):
    """Same native float32 NPY bytes, standard lossless NPZ ZIP-LZMA codec."""
    array = io.BytesIO(); np.save(array, depth, allow_pickle=False)
    packed = io.BytesIO()
    entry = zipfile.ZipInfo('depth_m.npy', date_time=(1980, 1, 1, 0, 0, 0))
    entry.compress_type = zipfile.ZIP_LZMA
    with zipfile.ZipFile(packed, 'w') as archive:
        archive.writestr(entry, array.getvalue())
    return packed.getvalue()


@dataclass
class _Capture:
    capture_id: str
    camera: str
    rgb: np.ndarray
    depth: np.ndarray
    metadata: dict
    artifacts: dict = field(default_factory=dict)


class RawSensorGateway:
    def __init__(self, cell, evidence_root, *, sim_timestep_s=.002,
                 max_line_bytes=MAX_LINE_BYTES, clock: Callable[[], float] = time.monotonic):
        if not math.isfinite(sim_timestep_s) or sim_timestep_s <= 0:
            raise ValueError('positive finite simulation timestep required')
        if not 4096 <= max_line_bytes <= MAX_LINE_BYTES:
            raise ValueError('line limit must be between 4096 bytes and 1 MiB')
        self.cell = cell
        # Only the supervisor supplies this path. Request data never participates
        # in path construction; no sensor request invokes a filesystem read.
        self.evidence_root = Path(evidence_root).resolve()
        self.evidence_root.mkdir(parents=True, exist_ok=True)
        self.sim_timestep_s = sim_timestep_s
        self.max_line_bytes = max_line_bytes
        self.clock = clock
        self._overhead = None
        self._cached = {}
        self._admissions = {}
        self._last_attempt = {}
        self.last_evidence = None

    def _telemetry(self):
        data = self.cell.data
        return {'sim_time_s': float(data.time),
                'sim_tick': round(float(data.time) / self.sim_timestep_s),
                'joint_position_rad': np.asarray(data.qpos[:7]).tolist(),
                'joint_velocity_rad_s': np.asarray(data.qvel[:7]).tolist(),
                'actuator_effort_Nm': np.asarray(data.actuator_force[:7]).tolist(),
                'measured_gripper_width_m': float(sum(data.qpos[7:9]))}

    def _capture(self, camera, rgb, depth, wall_elapsed_s, readout):
        rgb, depth = np.asarray(rgb), np.asarray(depth)
        if (rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3
                or rgb.shape[:2] != depth.shape or depth.dtype != np.float32
                or rgb.shape[0] < 1 or rgb.shape[1] < 1
                or rgb.shape[0] > 480 or rgb.shape[1] > 640):
            raise ValueError('expected native RGB uint8 and depth float32 arrays up to 640 x 480')
        height, width = depth.shape
        camera_id = self.cell.model.camera(camera).id
        fovy = float(self.cell.model.cam_fovy[camera_id])
        if not math.isfinite(fovy) or not 0 < fovy < 180:
            raise ValueError('invalid camera field of view')
        focal = height / (2 * math.tan(math.radians(fovy) / 2))
        # Current workcell cameras use fovy with square pixels and no principal
        # point override, exactly as Cell.sense. No object pose/registry is read.
        calibration = {
            'version': 'B01-raw-camera-fovy-001', 'width_px': width, 'height_px': height,
            'vertical_fov_deg': fovy,
            'intrinsics_px': [[focal, 0., (width-1)/2],
                              [0., focal, (height-1)/2], [0., 0., 1.]],
            'world_from_camera_rotation': np.asarray(
                self.cell.data.cam_xmat[camera_id]).reshape(3, 3).tolist(),
            'camera_position_world_m': np.asarray(self.cell.data.cam_xpos[camera_id]).tolist(),
            'camera_axes': '+X right, +Y up, -Z forward',
            'pixel_axes': 'origin at top-left pixel centre; u right, v down',
            'unprojection': 'world = position + rotation @ [(u-cx)*depth/fx, -(v-cy)*depth/fy, -depth]',
            'depth_units': 'metres along camera forward axis',
        }
        metadata = {'capture_sim_time_s': float(self.cell.data.time),
                    'capture_sim_tick': round(float(self.cell.data.time)/self.sim_timestep_s),
                    'capture_wall_elapsed_s': wall_elapsed_s, 'readout': readout,
                    'calibration': calibration, 'capture_telemetry': self._telemetry()}
        # Reject non-finite calibration/telemetry before any artifact write.
        json.dumps(metadata, allow_nan=False)
        return _Capture(camera + '-' + uuid.uuid4().hex, camera,
                        rgb.copy(), depth.copy(), metadata)

    def cache_overhead(self, *, capture_wall_elapsed_s=None):
        """Register existing noisy Cell.sense frames before the next physics tick.

        If the caller cannot capture metadata at that point, overhead requests
        remain explicitly unavailable. Current poses are never backdated onto
        an older image. Wall time may be omitted and is then explicitly unknown.
        """
        if (self.cell.last_rgb is None or self.cell.last_depth is None
                or abs(float(self.cell.data.time)-float(self.cell.detection_time)) > 1e-9):
            raise ValueError('register overhead immediately after sense, before physics advances')
        if capture_wall_elapsed_s is not None and (
                not math.isfinite(capture_wall_elapsed_s) or capture_wall_elapsed_s < 0):
            raise ValueError('capture wall time must be nonnegative and finite')
        self._overhead = self._capture(
            'overhead', self.cell.last_rgb, self.cell.last_depth, capture_wall_elapsed_s,
            'cached Cell.sense output: bounded RGB channel offset and correlated depth noise')
        self._cached['overhead'] = self._overhead
        return self._overhead.capture_id

    def cache_result(self, result, *, readout=None):
        """Cache a trusted SensorResult without reading live Cell state.

        At most one result per camera is retained. Result metadata is copied
        exactly; missing readout provenance is labelled unknown, not inferred
        from an empty/nonempty detection list. Existing evidence refs are used
        only inside this gateway's supervisor-assigned evidence directory.
        """
        camera = result.camera
        if camera not in CAMERAS:
            raise ValueError('unsupported result camera')
        rgb, depth = np.asarray(result.rgb), np.asarray(result.depth)
        if (rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3
                or rgb.shape[:2] != depth.shape or depth.dtype != np.float32
                or not 1 <= rgb.shape[0] <= 480 or not 1 <= rgb.shape[1] <= 640):
            raise ValueError('invalid native result arrays')
        calibration = result.calibration
        if (calibration.get('camera', camera) != camera
                or calibration.get('width_px') != rgb.shape[1]
                or calibration.get('height_px') != rgb.shape[0]):
            raise ValueError('capture calibration does not match native frame')
        captured = float(result.capture_sim_time_s)
        wall = result.capture_wall_elapsed_s
        if not math.isfinite(captured) or captured < 0 or (wall is not None and
                (not math.isfinite(wall) or wall < 0)):
            raise ValueError('invalid result capture clocks')
        metadata = {'capture_sim_time_s': captured,
                    'capture_sim_tick': round(captured/self.sim_timestep_s),
                    'capture_wall_elapsed_s': wall, 'capture_sequence': result.sequence,
                    'readout': readout or 'SensorWorker result; readout-noise configuration unrecorded',
                    'calibration': calibration, 'capture_telemetry': result.capture_telemetry}
        metadata = json.loads(json.dumps(metadata, allow_nan=False))
        if abs(float(metadata['capture_telemetry']['sim_time_s'])-captured) > 1e-9:
            raise ValueError('capture telemetry clock does not match frame')
        artifacts = {}
        for modality, reference in result.artifacts.items():
            if modality not in ('rgb', 'depth'):
                raise ValueError('unexpected sensor artifact')
            path = Path(reference['path']).resolve()
            relative = path.relative_to(self.evidence_root)
            artifacts[modality] = {'relative_path': relative.as_posix(),
                                   'sha256': reference['sha256'], 'bytes': reference['bytes']}
        # SensorResult uses immutable bytes-backed arrays. Synthetic/writable
        # callers are defensively copied into equivalent immutable backing.
        if rgb.flags.writeable:
            rgb = np.frombuffer(rgb.tobytes(), dtype=rgb.dtype).reshape(rgb.shape)
        if depth.flags.writeable:
            depth = np.frombuffer(depth.tobytes(), dtype=depth.dtype).reshape(depth.shape)
        capture = _Capture(camera+'-'+uuid.uuid4().hex, camera, rgb, depth, metadata, artifacts)
        self._cached[camera] = capture
        if camera == 'overhead':
            self._overhead = capture
        return capture.capture_id

    def admit_request(self, request, *, wall_elapsed_s=None):
        """Validate/rate-admit before scheduling; no rendering, IO, or Cell read.

        A maximum of one pending admission per camera is retained. Materialize
        it once using the identical request; cancel if no capture is scheduled.
        Accepted attempts consume bandwidth even if later capture fails.
        """
        base = {'type': 'sensor_response', 'schema': 'robot-raw-sensor-1.0'}
        try:
            request_id, camera, modalities = validate_request(request)
        except ValueError as error:
            return {**base, 'status': 'invalid_request', 'reason': str(error)}
        base.update(request_id=request_id, camera=camera)
        if wall_elapsed_s is not None and (not math.isfinite(wall_elapsed_s) or wall_elapsed_s < 0):
            return {**base, 'status': 'unavailable', 'reason': 'invalid supervisor wall clock'}
        now = self.clock()
        since = now-self._last_attempt.get(camera, -math.inf)
        if since < .1:
            return {**base, 'status': 'rate_limited', 'maximum_hz_per_camera': 10,
                    'retry_after_wall_s': max(0., .1-since)}
        self._last_attempt[camera] = now
        if request_id in self._admissions or any(a['camera'] == camera for a in self._admissions.values()):
            return {**base, 'status': 'busy', 'reason': 'camera already has an admitted request'}
        self._admissions[request_id] = {'camera': camera, 'modalities': list(modalities),
                                        'request_wall_elapsed_s': wall_elapsed_s}
        return {**base, 'status': 'accepted', 'maximum_hz_per_camera': 10}

    def cancel_admission(self, request_id, *, reason='sensor capture not scheduled'):
        admission = self._admissions.pop(request_id, None)
        return {'type': 'sensor_response', 'schema': 'robot-raw-sensor-1.0',
                'request_id': request_id, 'camera': admission['camera'] if admission else None,
                'status': 'unavailable', 'reason': str(reason)[:256]}

    def encode_cached_request(self, request, *, wall_elapsed_s=None, current_telemetry=None):
        """Return the final IPC bytes using cached frames only.

        Run compression/IO on the supervisor's bounded serial encoding worker.
        No sleep, wait, render, or live Cell state access occurs here. Without a
        supplied owner-thread telemetry snapshot, delivery simulation age is
        explicitly unknown; capture clocks/telemetry remain exact.
        """
        response = self.materialize_cached_request(request, wall_elapsed_s=wall_elapsed_s,
                                                    current_telemetry=current_telemetry)
        return self.encode_response(response)

    def materialize_cached_request(self, request, *, wall_elapsed_s=None, current_telemetry=None):
        """JSON-ready counterpart to encode_cached_request, for evidence logging."""
        self.last_evidence = None
        base = {'type': 'sensor_response', 'schema': 'robot-raw-sensor-1.0'}
        try:
            request_id, camera, modalities = validate_request(request)
        except ValueError as error:
            return {**base, 'status': 'invalid_request', 'reason': str(error)}
        base.update(request_id=request_id, camera=camera)
        admission = self._admissions.get(request_id)
        if admission is None:
            decision = self.admit_request(request, wall_elapsed_s=wall_elapsed_s)
            if decision['status'] != 'accepted':
                return decision
            admission = self._admissions[request_id]
        if admission['camera'] != camera or admission['modalities'] != modalities:
            return {**base, 'status': 'invalid_request', 'reason': 'request differs from its admission'}
        self._admissions.pop(request_id)
        capture = self._cached.get(camera)
        if capture is None:
            return {**base, 'status': 'unavailable', 'reason': 'no completed cached capture for this camera'}
        try:
            current = None if current_telemetry is None else json.loads(json.dumps(current_telemetry, allow_nan=False))
            if current is not None and not isinstance(current.get('sim_time_s'), (int, float)):
                raise ValueError('delivery telemetry has no simulation clock')
            if wall_elapsed_s is not None and (not math.isfinite(wall_elapsed_s) or wall_elapsed_s < 0):
                raise ValueError('invalid delivery wall clock')
            capture_wall = capture.metadata['capture_wall_elapsed_s']
            wall_age = None if wall_elapsed_s is None or capture_wall is None else wall_elapsed_s-capture_wall
            if wall_age is not None and wall_age < -1e-9:
                raise ValueError('capture wall clock follows delivery')
            extra = {'delivery_wall_elapsed_s': wall_elapsed_s,
                     'request_wall_elapsed_s': admission['request_wall_elapsed_s'],
                     'age_wall_s_at_delivery': wall_age,
                     'telemetry_basis': ('owner-thread delivery snapshot supplied' if current is not None
                                         else 'capture only; delivery telemetry unavailable')}
            return self._materialize(base, capture, modalities, current, 'cached_async', extra)
        except (ValueError, OSError, RuntimeError) as error:
            self.last_evidence = None
            return {**base, 'status': 'unavailable', 'reason': 'cached sensor materialization failed',
                    'error_class': type(error).__name__}

    def _write_artifact(self, capture, modality, content, *, variant=None):
        key = modality if variant is None else modality + ':' + variant
        if key in capture.artifacts:
            if capture.artifacts[key]['sha256'] != hashlib.sha256(content).hexdigest():
                raise ValueError('registered artifact bytes do not match this encoding')
            return capture.artifacts[key]
        directory = self.evidence_root / 'raw-sensors'
        directory.mkdir(exist_ok=True)
        if directory.resolve() != self.evidence_root / 'raw-sensors':
            raise ValueError('sensor evidence directory must not redirect outside its assigned root')
        suffix = '.png' if modality == 'rgb' else ('-depth.npz' if variant is None else '-depth-' + variant + '.npz')
        path = directory / (capture.capture_id + suffix)
        with path.open('xb') as stream:
            stream.write(content)
        record = {'relative_path': path.relative_to(self.evidence_root).as_posix(),
                  'sha256': hashlib.sha256(content).hexdigest(), 'bytes': len(content)}
        capture.artifacts[key] = record
        return record

    def _materialize(self, base, capture, modalities, current, origin, extra=None):
        age = None if current is None else current['sim_time_s']-capture.metadata['capture_sim_time_s']
        if age is not None and age < -1e-9:
            return {**base, 'status': 'unavailable', 'reason': 'capture belongs to a later simulation clock'}
        blobs = {}
        if 'rgb' in modalities:
            blobs['rgb'] = _png(capture.rgb)
        if 'depth' in modalities:
            stream = io.BytesIO()
            np.savez_compressed(stream, depth_m=capture.depth)
            blobs['depth'] = stream.getvalue()
        native_blobs = dict(blobs)
        depth_codec = 'deflate'
        def images_for_blobs():
            return {name: {'encoding': 'png-base64' if name == 'rgb' else 'npz-base64',
                         'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob),
                         'data': base64.b64encode(blob).decode('ascii'),
                         **({'npz_compression': depth_codec} if name == 'depth' else {})}
                  for name, blob in blobs.items()}
        response = {**base, 'status': 'ok', 'capture_id': capture.capture_id,
                    'origin': origin, 'age_sim_s': None if age is None else max(0., age),
                    'freshness': ('delivery_age_unknown' if age is None else
                                  'same_sim_tick' if abs(age) < 1e-9 else 'prior_capture'),
                    **capture.metadata, 'current_telemetry': current,
                    'maximum_hz_per_camera': 10, 'images': images_for_blobs()}
        response.update(extra or {})
        try:
            encode_response(response, self.max_line_bytes)
        except ValueError:
            # Bound the fallback to the same one native frame and one standard
            # codec. No quantization, resizing, chunking or raised line quota.
            if 'depth' in blobs:
                fallback = _depth_npz_lzma(capture.depth)
                if len(fallback) < len(blobs['depth']):
                    blobs['depth'] = fallback; depth_codec = 'lzma'
                    response['images'] = images_for_blobs()
            try:
                encode_response(response, self.max_line_bytes)
            except ValueError:
                return {**base, 'status': 'payload_too_large',
                        'reason': 'native lossless modalities exceed IPC line budget; no resampling performed',
                        'max_line_bytes': self.max_line_bytes,
                        'compression_attempts': ['deflate', 'lzma'] if 'depth' in blobs else ['png'],
                        'compressed_bytes': {name: len(blob) for name, blob in blobs.items()}}
        source_artifacts = {name: self._write_artifact(capture, name, blob) for name, blob in native_blobs.items()}
        artifacts = dict(source_artifacts)
        if depth_codec == 'lzma':
            artifacts['depth'] = self._write_artifact(capture, 'depth', blobs['depth'], variant='lzma')
        self.last_evidence = {'capture_id': capture.capture_id, 'request_id': base['request_id'],
                              'camera': capture.camera, **capture.metadata, 'artifacts': artifacts,
                              'source_artifacts': source_artifacts, 'depth_wire_compression': depth_codec if 'depth' in blobs else None}
        return response

    def handle(self, request, *, wall_elapsed_s=None):
        """Return a bounded JSON-ready reply. Call only on the render owning thread.

        Rate is based on a supervisor monotonic clock, not candidate timestamps.
        last_evidence is operator-only metadata for a successful reply; it must
        be logged separately. Nothing here calls an LLM or infers object states.
        """
        self.last_evidence = None
        base = {'type': 'sensor_response', 'schema': 'robot-raw-sensor-1.0'}
        try:
            request_id, camera, modalities = validate_request(request)
        except ValueError as error:
            return {**base, 'status': 'invalid_request', 'reason': str(error)}
        base.update(request_id=request_id, camera=camera)
        if wall_elapsed_s is not None and (not math.isfinite(wall_elapsed_s) or wall_elapsed_s < 0):
            return {**base, 'status': 'unavailable', 'reason': 'invalid supervisor wall clock'}
        now = self.clock()
        since = now - self._last_attempt.get(camera, -math.inf)
        if since < .1:
            return {**base, 'status': 'rate_limited', 'maximum_hz_per_camera': 10,
                    'retry_after_wall_s': max(0., .1-since)}
        self._last_attempt[camera] = now
        try:
            if camera == 'overhead':
                capture = self._overhead
                if capture is None:
                    return {**base, 'status': 'unavailable',
                            'reason': 'no overhead capture with simultaneous calibration registered'}
                origin = 'cached'
            else:
                rgb, depth = self.cell.render(camera)
                captured_wall = None if wall_elapsed_s is None else wall_elapsed_s+self.clock()-now
                capture = self._capture(camera, rgb, depth, captured_wall,
                                        'on-demand Cell.render output; no additional readout noise applied')
                origin = 'on_demand'
            current = self._telemetry()
            return self._materialize(base, capture, modalities, current, origin)
        except (ValueError, OSError, RuntimeError) as error:
            # No raw paths or backend exception strings cross the boundary.
            return {**base, 'status': 'unavailable', 'reason': 'sensor capture or evidence recording failed',
                    'error_class': type(error).__name__}

    def encode_response(self, response):
        return encode_response(response, self.max_line_bytes)
