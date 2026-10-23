"""Prospective nested measurements of the unchanged synchronous recorder.

Original recorder/runtime_adapter sources remain immutable. Native connection,
cursor, encoding, transaction, retention and failure operations are delegated;
only fixed-name phase scopes surround them. Measurements are inclusive, so a
parent and its children must never be summed. The host supplies a null scope
outside its measured interval, including recorder construction/finalization.
"""
from __future__ import annotations

from dataclasses import replace
import io
from pathlib import Path
import struct
import threading
import time
import zlib

from recorder import Recorder, ImagePolicy
from runtime_adapter import FutureEvidence, LiveSensorBridge, MotionSink


PHASE_NAMES = (
    'bridge.rgb_encode', 'bridge.depth_encode', 'bridge.recorder_image',
    'recorder.lock_acquire', 'recorder.lock_release',
    'recorder.sqlite.execute', 'recorder.sqlite.executemany',
    'recorder.sqlite.executescript', 'recorder.sqlite.commit',
    'recorder.sqlite.rollback', 'recorder.sqlite.close',
    'recorder.sqlite.enter', 'recorder.sqlite.exit',
    'recorder.quota_guard', 'recorder.physical_guard',
    'recorder.image', 'recorder.persist', 'recorder.motion',
    'recorder.flush_motion', 'recorder.document', 'recorder.event',
    'recorder.trigger', 'recorder.close',
)


class TimedConnection:
    """Delegate the existing connection without replacing cursors or SQL."""
    def __init__(self, connection, phase):
        object.__setattr__(self, '_connection', connection)
        object.__setattr__(self, '_phase', phase)

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def __setattr__(self, name, value):
        setattr(self._connection, name, value)

    def execute(self, *args, **kwargs):
        with self._phase('recorder.sqlite.execute'):
            return self._connection.execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        with self._phase('recorder.sqlite.executemany'):
            return self._connection.executemany(*args, **kwargs)

    def executescript(self, *args, **kwargs):
        with self._phase('recorder.sqlite.executescript'):
            return self._connection.executescript(*args, **kwargs)

    def commit(self, *args, **kwargs):
        with self._phase('recorder.sqlite.commit'):
            return self._connection.commit(*args, **kwargs)

    def rollback(self, *args, **kwargs):
        with self._phase('recorder.sqlite.rollback'):
            return self._connection.rollback(*args, **kwargs)

    def close(self, *args, **kwargs):
        with self._phase('recorder.sqlite.close'):
            return self._connection.close(*args, **kwargs)

    def __enter__(self):
        with self._phase('recorder.sqlite.enter'):
            result = self._connection.__enter__()
        return self if result is self._connection else result

    def __exit__(self, *args):
        with self._phase('recorder.sqlite.exit'):
            return self._connection.__exit__(*args)


class TimedLock:
    """One original RLock; acquisition and release retain its return/errors."""
    def __init__(self, lock, phase):
        self._lock, self._phase = lock, phase

    def __getattr__(self, name):
        return getattr(self._lock, name)

    def acquire(self, *args, **kwargs):
        with self._phase('recorder.lock_acquire'):
            return self._lock.acquire(*args, **kwargs)

    def release(self, *args, **kwargs):
        with self._phase('recorder.lock_release'):
            return self._lock.release(*args, **kwargs)

    def __enter__(self):
        with self._phase('recorder.lock_acquire'):
            return self._lock.__enter__()

    def __exit__(self, *args):
        with self._phase('recorder.lock_release'):
            return self._lock.__exit__(*args)


class InstrumentedRecorder(Recorder):
    def __init__(self, *args, phase, **kwargs):
        self._phase = phase
        super().__init__(*args, **kwargs)
        # All native SQLite setup, including DELETE journal/FULL synchronous,
        # has already run through the exact original constructor.
        self.db = TimedConnection(self.db, phase)

    def _guard(self, *args, **kwargs):
        with self._phase('recorder.quota_guard'):
            return super()._guard(*args, **kwargs)

    def _physical_guard(self, *args, **kwargs):
        with self._phase('recorder.physical_guard'):
            return super()._physical_guard(*args, **kwargs)

    def image(self, *args, **kwargs):
        with self._phase('recorder.image'):
            return super().image(*args, **kwargs)

    def _persist(self, *args, **kwargs):
        with self._phase('recorder.persist'):
            return super()._persist(*args, **kwargs)

    def motion(self, *args, **kwargs):
        with self._phase('recorder.motion'):
            return super().motion(*args, **kwargs)

    def flush_motion(self, *args, **kwargs):
        with self._phase('recorder.flush_motion'):
            return super().flush_motion(*args, **kwargs)

    def document(self, *args, **kwargs):
        with self._phase('recorder.document'):
            return super().document(*args, **kwargs)

    def event(self, *args, **kwargs):
        with self._phase('recorder.event'):
            return super().event(*args, **kwargs)

    def trigger(self, *args, **kwargs):
        with self._phase('recorder.trigger'):
            return super().trigger(*args, **kwargs)

    def close(self, *args, **kwargs):
        with self._phase('recorder.close'):
            return super().close(*args, **kwargs)


class InstrumentedFutureEvidence(FutureEvidence):
    def __init__(self, directory, run_id, *, phase, policy=ImagePolicy(), core_quota_bytes=200_000_000,
                 representative=False, clock=time.perf_counter, physics_dt=.002, allocation=None):
        if allocation is not None:
            if allocation['run_id'] != run_id: raise ValueError('Campaign allocation identifies another run')
            core_quota_bytes = allocation['core_quota_bytes']
            policy = replace(policy, image_quota_bytes=allocation['image_quota_bytes'],
                             maximum_trigger_windows=allocation['maximum_trigger_windows'])
        self.store = InstrumentedRecorder(directory, run_id=run_id, policy=policy, core_quota_bytes=core_quota_bytes,
                                          representative=representative, phase=phase)
        self.path = Path(directory); self.run_id = run_id; self.clock = clock; self.start = clock()
        self.physics_dt = physics_dt; self.sequence = 0; self.lock = TimedLock(threading.RLock(), phase)
        self.motion = MotionSink(self.store, self.lock)


class InstrumentedLiveSensorBridge(LiveSensorBridge):
    def __init__(self, evidence, *, phase):
        super().__init__(evidence)
        self._phase = phase

    def observe(self, result):
        import numpy as np
        rgb = result.rgb; depth = result.depth
        if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3: raise ValueError('Expected uint8 RGB')
        def chunk(tag, value):
            return struct.pack('!I', len(value)) + tag + value + struct.pack('!I', zlib.crc32(tag + value))
        with self._phase('bridge.rgb_encode'):
            raw = b''.join(b'\0' + row.tobytes() for row in rgb)
            png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', rgb.shape[1], rgb.shape[0], 8, 2, 0, 0, 0))
                   + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))
        with self._phase('bridge.depth_encode'):
            stream = io.BytesIO(); np.savez_compressed(stream, depth_m=depth)
        ident = f'{result.camera}:{result.sequence}'
        with self.evidence.lock:
            with self._phase('bridge.recorder_image'):
                self.evidence.store.image(ident, result.capture_sim_time_s, png, stream.getvalue())
        return result
