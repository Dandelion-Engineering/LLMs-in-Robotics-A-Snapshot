"""One bounded sensor job; rendering, detection and evidence IO off physics.

Renderer construction/use/destruction happen on one dedicated thread. Each job
receives private copied MjData and visible material colours. The detector only
receives RGB/depth, camera calibration and the public tag/zone definitions.
There is no queue of captures: callers must poll before requesting another job.
Rejected nominal slots must be recorded by the supervisor, never replayed faster.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import copy
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import struct
import time
import zlib

import mujoco
import numpy as np


def apply_readout_noise(rgb, depth, rgb_offset, depth_offset):
    """Preserve the existing bounded RGB offset / correlated depth noise model."""
    return (np.clip(rgb.astype(np.int16)+rgb_offset, 0, 255).astype(np.uint8),
            (depth+depth_offset).astype(np.float32))


def camera_calibration(model, data, camera='overhead', width=640, height=480):
    cid = model.camera(camera).id
    fovy = float(model.cam_fovy[cid])
    focal = height/(2*np.tan(np.deg2rad(fovy)/2))
    return {'camera': camera, 'width_px': width, 'height_px': height,
            'vertical_fov_deg': fovy, 'focal_px': float(focal),
            'intrinsics_px': [[float(focal), 0., (width-1)/2],
                              [0., float(focal), (height-1)/2], [0., 0., 1.]],
            'world_from_camera_rotation': data.cam_xmat[cid].reshape(3, 3).tolist(),
            'camera_position_world_m': data.cam_xpos[cid].tolist(),
            'camera_axes': '+X right, +Y up, -Z forward',
            'pixel_axes': 'origin at top-left pixel centre; u right, v down',
            'depth_units': 'metres along camera forward axis'}


def classify_process_mark(crop_rgb, crop_depth, tag_depth):
    """Image-only mark evidence; occlusion/ambiguous appearance stays unknown.

    Inputs are normalized RGB and camera-forward metric depth. The marker and
    colored tag share a top plane; 4 mm tolerance allows the declared positional
    uncertainty. These thresholds are common calibration, not process truth.
    """
    if crop_rgb.shape != (7,5,3) or crop_depth.shape != (7,5):return 'unknown'
    if (not np.isfinite(tag_depth) or tag_depth <= 0 or not np.all(np.isfinite(crop_rgb))
            or np.any(crop_rgb < 0) or np.any(crop_rgb > 1)):return 'unknown'
    # The 8 mm mark spans about 3.55 pixels in the calibrated overhead image.
    # The five-column search crop also includes tag/body/background edge pixels.
    # Keep the central three columns; require depth agreement throughout this
    # core and two adjacent consistent columns, allowing one antialiased edge.
    core_rgb=crop_rgb[:,1:4];core_depth=crop_depth[:,1:4]
    same_surface=np.isfinite(core_depth) & (core_depth > 0) & (np.abs(core_depth-tag_depth) <= .004)
    if np.mean(same_surface) < .9:return 'unknown'
    maximum=core_rgb.max(2);minimum=core_rgb.min(2)
    # Count jointly supported pixels; do not borrow brightness from an occluder.
    white=same_surface & (minimum > .72) & (maximum-minimum <= .10)
    dark=same_surface & (maximum < .25)
    def supported_pair(pixels):
        columns=np.mean(pixels,axis=0) >= .9
        return bool(np.any(columns[:-1] & columns[1:]))
    if supported_pair(white) and not np.any(dark):return 'processed'
    if supported_pair(dark) and not np.any(white):return 'raw'
    return 'unknown'


def derive_detections(rgb, depth, calibration, registry, zones, zone_halves):
    """Image-only detector: no MjData, object positions or evaluator input."""
    pix = rgb.astype(np.float32)/255
    maximum = pix.max(2); minimum = pix.min(2); delta = maximum-minimum
    hue = np.zeros_like(maximum)
    valid = delta > .08
    red = valid & (pix[:, :, 0] == maximum)
    green = valid & (pix[:, :, 1] == maximum)
    blue = valid & (pix[:, :, 2] == maximum)
    hue[red] = ((pix[:, :, 1][red]-pix[:, :, 2][red])/delta[red]) % 6
    hue[green] = (pix[:, :, 2][green]-pix[:, :, 0][green])/delta[green]+2
    hue[blue] = (pix[:, :, 0][blue]-pix[:, :, 1][blue])/delta[blue]+4
    hue /= 6
    sat = delta/np.maximum(maximum, 1e-9)
    rotation = np.asarray(calibration['world_from_camera_rotation'])
    camera_pos = np.asarray(calibration['camera_position_world_m'])
    focal = calibration['focal_px']
    height, width = depth.shape
    detections = []
    for name, tag in registry.items():
        diff = np.abs(hue-tag['hue']); diff = np.minimum(diff, 1-diff)
        mask = (diff < .024) & (sat > .55) & (maximum > .4)
        yy, xx = np.where(mask)
        if len(xx) < 12:
            continue
        u, v = float(np.median(xx)), float(np.median(yy))
        z = float(np.median(depth[yy, xx]))
        local = np.array([(u-(width-1)/2)*z/focal, -(v-(height-1)/2)*z/focal, -z])
        surface = camera_pos+rotation@local
        center = surface-np.array([0, 0, tag['half'][2]+.0007])
        zone = 'raw'
        for key, xy in zones.items():
            if np.all(np.abs(center[:2]-xy) < zone_halves[key]):
                zone = key
                break
        mu = int(round(u+.018*focal/z)); mv = int(round(v))
        crop = pix[max(0, mv-3):min(height, mv+4), max(0, mu-2):min(width, mu+3)]
        crop_depth = depth[max(0, mv-3):min(height, mv+4), max(0, mu-2):min(width, mu+3)]
        mark = classify_process_mark(crop,crop_depth,z)
        detections.append({'id': name, 'family': tag['family'], 'pos': center.tolist(),
                           'zone': zone, 'visible_mark': mark,
                           'age_s': 0., 'pixels': len(xx), 'uncertainty_m': .004,
                           'kind': tag['kind']})
    return detections


def _json(value):
    return json.dumps(value, separators=(',', ':'), allow_nan=False)


def _readonly(array):
    # Immutable bytes backing also prevents setflags(write=True).
    return np.frombuffer(array.tobytes(), dtype=array.dtype).reshape(array.shape)


@dataclass(frozen=True)
class SensorResult:
    sequence: int
    camera: str
    capture_sim_time_s: float
    capture_wall_elapsed_s: float | None
    rgb: np.ndarray
    depth: np.ndarray
    detections_json: str
    calibration_json: str
    telemetry_json: str
    artifacts_json: str
    worker_started_monotonic_s: float
    worker_finished_monotonic_s: float

    @property
    def detections(self):
        return json.loads(self.detections_json)

    @property
    def calibration(self):
        return json.loads(self.calibration_json)

    @property
    def capture_telemetry(self):
        return json.loads(self.telemetry_json)

    @property
    def artifacts(self):
        return json.loads(self.artifacts_json)


@dataclass(frozen=True)
class _Snapshot:
    data: object
    colours: tuple
    capture_sim_time_s: float
    capture_wall_elapsed_s: float | None
    sequence: int
    camera: str
    calibration_json: str
    telemetry_json: str
    rgb_offset: np.ndarray | None
    depth_offset: float | None
    rgb_path: Path | None
    depth_path: Path | None


def _copy_data(model, data):
    result = mujoco.MjData(model)
    mujoco.mj_copyData(result, model, data)
    return result


def write_sensor_evidence(rgb, depth, rgb_path=None, depth_path=None):
    """Lossless evidence writer. Paths are supervisor supplied; no overwrite.

    Called on the single sensor thread after rendering/detection, so compression
    and disk IO share its one bounded future and cannot build a writer backlog.
    A failed partial write remains an explicit failed job, never a ready result.
    """
    artifacts = {}
    for modality, path in (('rgb', rgb_path), ('depth', depth_path)):
        if path is None:
            continue
        path = Path(path)
        if modality == 'rgb':
            h, w, _ = rgb.shape
            def chunk(tag, value):
                return struct.pack('!I', len(value))+tag+value+struct.pack('!I', zlib.crc32(tag+value))
            raw = b''.join(b'\0'+row.tobytes() for row in rgb)
            content = (b'\x89PNG\r\n\x1a\n'
                       + chunk(b'IHDR', struct.pack('!2I5B', w, h, 8, 2, 0, 0, 0))
                       + chunk(b'IDAT', zlib.compress(raw))+chunk(b'IEND', b''))
        else:
            stream = io.BytesIO()
            np.savez_compressed(stream, depth_m=depth)
            content = stream.getvalue()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(content)
        artifacts[modality] = {'path': str(path), 'bytes': len(content),
                               'sha256': hashlib.sha256(content).hexdigest()}
    return artifacts


class SensorWorker:
    """Owned by the physics thread; exactly one accepted job until poll()."""
    def __init__(self, model, registry, zones, zone_halves, *, width=640, height=480,
                 renderer_factory=None):
        self.model = copy.copy(model)
        self.registry = copy.deepcopy(registry)
        self.zones = copy.deepcopy(zones)
        self.zone_halves = copy.deepcopy(zone_halves)
        self.width, self.height = width, height
        self._renderer_factory = renderer_factory or mujoco.Renderer
        self._renderer = None
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='sensor-render-evidence')
        self._future = None
        self._closed = False

    @property
    def busy(self):
        # Even a completed but unconsumed result occupies the only slot.
        return self._future is not None

    def prepare(self):
        """Optional startup warmup before the timed episode; GL stays on worker."""
        if self._closed or self.busy:
            raise RuntimeError('sensor worker is closed or has a pending job')
        self._pool.submit(self._ensure_renderer).result()

    def _ensure_renderer(self):
        if self._renderer is None:
            self._renderer = self._renderer_factory(self.model, self.height, self.width)

    def request(self, model, data, *, sequence, capture_wall_elapsed_s=None,
                camera='overhead', rgb_offset=None, depth_offset=None,
                rgb_path=None, depth_path=None):
        if self._closed:
            raise RuntimeError('sensor worker is closed')
        if self.busy:
            return False
        if camera not in ('overhead', 'oblique', 'wrist'):
            raise ValueError('unsupported camera')
        if (rgb_offset is None) != (depth_offset is None):
            raise ValueError('both readout offsets must be supplied, or neither')
        # Copy occurs on the physics owner thread; worker never receives live
        # Cell/data/model references. Model colour changes are captured too.
        private_data = _copy_data(model, data)
        colours = tuple((name, getattr(model, name).copy())
                        for name in ('geom_rgba', 'mat_rgba') if hasattr(model, name))
        telemetry = {'sim_time_s': float(data.time), 'joint_position_rad': data.qpos[:7].tolist(),
                     'joint_velocity_rad_s': data.qvel[:7].tolist(),
                     'actuator_effort_Nm': data.actuator_force[:7].tolist(),
                     'measured_gripper_width_m': float(sum(data.qpos[7:9]))}
        snapshot = _Snapshot(private_data, colours, float(data.time), capture_wall_elapsed_s,
                             sequence, camera,
                             _json(camera_calibration(model, private_data, camera, self.width, self.height)),
                             _json(telemetry), None if rgb_offset is None else rgb_offset.copy(),
                             depth_offset, None if rgb_path is None else Path(rgb_path),
                             None if depth_path is None else Path(depth_path))
        self._future = self._pool.submit(self._process, snapshot)
        return True

    def _process(self, snapshot):
        started = time.monotonic()
        self._ensure_renderer()
        for name, colours in snapshot.colours:
            getattr(self.model, name)[:] = colours
        renderer = self._renderer
        renderer.disable_depth_rendering()
        renderer.update_scene(snapshot.data, camera=snapshot.camera)
        rgb = renderer.render().copy()
        renderer.enable_depth_rendering()
        try:
            depth = renderer.render().copy()
        finally:
            renderer.disable_depth_rendering()
        if snapshot.rgb_offset is not None:
            rgb, depth = apply_readout_noise(rgb, depth, snapshot.rgb_offset, snapshot.depth_offset)
        detections = (derive_detections(rgb, depth, json.loads(snapshot.calibration_json),
                                       self.registry, self.zones, self.zone_halves)
                      if snapshot.rgb_offset is not None and snapshot.camera == 'overhead' else [])
        artifacts = write_sensor_evidence(rgb, depth, snapshot.rgb_path, snapshot.depth_path)
        return SensorResult(snapshot.sequence, snapshot.camera, snapshot.capture_sim_time_s,
                            snapshot.capture_wall_elapsed_s, _readonly(rgb), _readonly(depth),
                            _json(detections), snapshot.calibration_json, snapshot.telemetry_json,
                            _json(artifacts), started, time.monotonic())

    def poll(self):
        if self._future is None or not self._future.done():
            return None
        future, self._future = self._future, None
        return future.result()

    def wait(self):
        """Synchronous calibration only; never call from the timed physics loop."""
        if self._future is None:
            return None
        future, self._future = self._future, None
        return future.result()

    def close(self):
        if self._closed:
            return
        self._closed = True
        def release():
            if self._renderer is not None:
                self._renderer.close()
                self._renderer = None
        try:
            # The release job follows any pending capture on this same thread.
            self._pool.submit(release).result()
        finally:
            self._pool.shutdown(wait=True, cancel_futures=True)
