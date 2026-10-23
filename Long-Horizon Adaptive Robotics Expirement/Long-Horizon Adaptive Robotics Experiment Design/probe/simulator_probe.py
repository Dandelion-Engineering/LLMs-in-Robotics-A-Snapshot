"""Bounded package/render/state smoke check; no robot policy or task experiment."""
from __future__ import annotations

import concurrent.futures
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import struct
import time
import zlib

import mujoco
import numpy as np

HERE = Path(__file__).resolve().parent
XML = """<mujoco model="design_probe">
  <option timestep="0.002"/>
  <visual><global offwidth="320" offheight="240"/></visual>
  <worldbody>
    <light pos="0 -1 3"/>
    <camera name="overview" pos="1 -1 1" xyaxes="0.707 0.707 0 -0.408 0.408 0.816"/>
    <geom type="plane" size="1 1 .1" rgba=".4 .4 .4 1"/>
    <body pos="0 0 .5"><freejoint/><geom type="box" size=".04 .04 .04" mass=".1" rgba=".1 .5 .8 1"/></body>
  </worldbody>
</mujoco>"""


def png_bytes(rgb):
    height, width, _ = rgb.shape
    def chunk(tag, data):
        return struct.pack('!I', len(data)) + tag + data + struct.pack('!I', zlib.crc32(tag + data))
    raw = b''.join(b'\x00' + row.tobytes() for row in rgb)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def main():
    model = mujoco.MjModel.from_xml_string(XML)
    data = mujoco.MjData(model)
    kind = mujoco.mjtState.mjSTATE_INTEGRATION
    size = mujoco.mj_stateSize(model, kind)
    def state():
        result = np.empty(size)
        mujoco.mj_getState(model, data, result, kind)
        return result
    for _ in range(60):
        mujoco.mj_step(model, data)
    saved = state()
    for _ in range(400):
        mujoco.mj_step(model, data)
    first = state()
    first_contacts = data.ncon
    mujoco.mj_setState(model, data, saved, kind)
    for _ in range(400):
        mujoco.mj_step(model, data)
    second = state()
    restore_error = float(np.max(np.abs(first - second)))
    assert restore_error < 1e-12, restore_error
    assert data.ncon > 0 and first_contacts > 0
    with mujoco.Renderer(model, height=240, width=320) as renderer:
        renderer.update_scene(data, camera='overview')
        rgb = renderer.render().copy()
        renderer.enable_depth_rendering()
        depth = renderer.render().copy()
    assert rgb.shape == (240, 320, 3) and rgb.std() > 1
    assert np.isfinite(depth).all() and depth.max() > depth.min()
    (HERE / 'probe-frame.png').write_bytes(png_bytes(rgb))
    start_sim = float(data.time)
    ticks = 0
    start_wall = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(time.sleep, 2.0)  # mock unavailable inference, not a model
        while not pending.done():
            mujoco.mj_step(model, data)
            ticks += 1
            remaining = start_wall + ticks * model.opt.timestep - time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)
    elapsed = time.perf_counter() - start_wall
    advanced = float(data.time - start_sim)
    assert ticks > 100 and advanced > 0.2
    result = {
        'scope': 'Minimal falling-box package, contact, RGB/depth, deterministic restore, and nonblocking mock-wait probe only.',
        'date': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'platform': platform.platform(), 'python': platform.python_version(),
        'mujoco': mujoco.__version__,
        'dependencies': {d.metadata['Name']: d.version for d in importlib.metadata.distributions()},
        'model_sha256': hashlib.sha256(XML.encode()).hexdigest(),
        'integration_state_size': size, 'restore_max_abs_error': restore_error,
        'contacts_after_branch': int(first_contacts),
        'rgb_shape': list(rgb.shape), 'rgb_std': float(rgb.std()),
        'depth_range_m': [float(depth.min()), float(depth.max())],
        'mock_wait_wall_seconds': elapsed, 'physics_ticks_during_wait': ticks,
        'simulation_seconds_during_wait': advanced, 'real_time_factor_tiny_probe': advanced / elapsed,
        'passed': True,
        'not_tested': ['Panda asset loading', 'full workcell or grasp fidelity', 'perception service',
                       'machine timers and application checkpointing', 'LLM inference',
                       'sandbox isolation', 'full-cell real-time performance', 'architecture benefit'],
    }
    (HERE / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
