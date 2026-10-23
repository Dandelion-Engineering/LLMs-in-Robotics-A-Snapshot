"""Byte, transaction, locking and failure parity using disposable evidence only."""
from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, nullcontext
import gzip
import inspect
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import textwrap
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'Storage Retention Implementation 001' / 'future'))
from recorder import Recorder, ImagePolicy, RecordingFailure, Reader
from runtime_adapter import FutureEvidence, LiveSensorBridge
from instrumented_recorder import (InstrumentedRecorder, InstrumentedFutureEvidence,
    InstrumentedLiveSensorBridge, TimedConnection, TimedLock, PHASE_NAMES)
from timing import TimingCapture


def unmeasured(name):
    return nullcontext()


class PhaseLog:
    def __init__(self):
        self.events = []

    @contextmanager
    def __call__(self, name):
        if name not in PHASE_NAMES:
            raise AssertionError('Unexpected unbounded phase name: ' + name)
        self.events.append(('enter', name))
        try:
            yield
        finally:
            self.events.append(('exit', name))


class CommitFault:
    def __init__(self, connection, error):
        self.connection, self.error, self.calls = connection, error, 0

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def commit(self):
        self.calls += 1
        raise self.error


class RecorderInstrumentationTests(unittest.TestCase):
    def test_bridge_functional_ast_is_exact_original(self):
        class RemoveMeasurement(ast.NodeTransformer):
            def visit_With(self, node):
                self.generic_visit(node)
                if (len(node.items) == 1 and isinstance(node.items[0].context_expr, ast.Call)
                        and isinstance(node.items[0].context_expr.func, ast.Attribute)
                        and node.items[0].context_expr.func.attr == '_phase'):
                    return node.body
                return node
        original = ast.parse(textwrap.dedent(inspect.getsource(LiveSensorBridge.observe)))
        measured = ast.parse(textwrap.dedent(inspect.getsource(InstrumentedLiveSensorBridge.observe)))
        self.assertEqual(ast.dump(original, include_attributes=False),
                         ast.dump(RemoveMeasurement().visit(measured), include_attributes=False))

    def test_evidence_constructor_preserves_all_original_initialization(self):
        class RemoveAdapters(ast.NodeTransformer):
            def visit_FunctionDef(self, node):
                self.generic_visit(node)
                keep = [(arg, default) for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults)
                        if arg.arg != 'phase']
                node.args.kwonlyargs = [arg for arg, default in keep]
                node.args.kw_defaults = [default for arg, default in keep]
                return node

            def visit_Call(self, node):
                self.generic_visit(node)
                if isinstance(node.func, ast.Name) and node.func.id == 'TimedLock':
                    return node.args[0]
                if isinstance(node.func, ast.Name) and node.func.id == 'InstrumentedRecorder':
                    node.func.id = 'Recorder'
                    node.keywords = [item for item in node.keywords if item.arg != 'phase']
                return node
        original = ast.parse(textwrap.dedent(inspect.getsource(FutureEvidence.__init__)))
        measured = ast.parse(textwrap.dedent(inspect.getsource(InstrumentedFutureEvidence.__init__)))
        self.assertEqual(ast.dump(original, include_attributes=False),
                         ast.dump(RemoveAdapters().visit(measured), include_attributes=False))

    def test_live_rgb_depth_bytes_identity_and_phase_order(self):
        import numpy as np
        # Noncontiguous arrays and nonfinite depth exercise the actual encoder.
        result = SimpleNamespace(rgb=np.arange(72, dtype=np.uint8).reshape(4, 6, 3)[:, ::2],
            depth=np.array([[0., float('nan')], [float('inf'), -0.]], dtype=np.float32),
            camera='overhead', sequence=12, capture_sim_time_s=3.25)
        outputs = []
        log = PhaseLog()
        for measured in (False, True):
            images = []
            lock = TimedLock(threading.RLock(), log) if measured else threading.RLock()
            evidence = SimpleNamespace(lock=lock, store=SimpleNamespace(image=lambda *args: images.append(args)))
            bridge = InstrumentedLiveSensorBridge(evidence, phase=log) if measured else LiveSensorBridge(evidence)
            self.assertIs(bridge.observe(result), result)
            outputs.append(images)
        self.assertEqual(outputs[0], outputs[1])
        encoded = outputs[1][0]
        self.assertEqual(encoded[:2], ('overhead:12', 3.25))
        self.assertTrue(encoded[2].startswith(b'\x89PNG\r\n\x1a\n'))
        with np.load(io.BytesIO(encoded[3])) as archive:
            np.testing.assert_array_equal(archive['depth_m'], result.depth)
        self.assertEqual([name for event, name in log.events if event == 'enter'],
            ['bridge.rgb_encode', 'bridge.depth_encode', 'recorder.lock_acquire',
             'bridge.recorder_image', 'recorder.lock_release'])

    def test_invalid_rgb_and_encoding_failure_never_acquire_lock_or_write(self):
        import numpy as np
        for measured in (False, True):
            with self.subTest(measured=measured):
                lock, store = mock.MagicMock(), mock.Mock()
                evidence = SimpleNamespace(lock=lock, store=store)
                bridge = InstrumentedLiveSensorBridge(evidence, phase=unmeasured) if measured else LiveSensorBridge(evidence)
                result = SimpleNamespace(rgb=np.zeros((2, 2, 3), dtype=np.float32), depth=np.zeros((2, 2)))
                with self.assertRaisesRegex(ValueError, 'Expected uint8 RGB'):
                    bridge.observe(result)
                result.rgb = np.zeros((2, 2, 3), dtype=np.uint8)
                error = OSError('injected encoder failure')
                with mock.patch('numpy.savez_compressed', side_effect=error):
                    with self.assertRaises(OSError) as raised:
                        bridge.observe(result)
                self.assertIs(raised.exception, error)
                lock.__enter__.assert_not_called()
                store.image.assert_not_called()

    def test_sql_operation_order_durability_retention_and_final_bytes_match(self):
        policy = ImagePolicy(sparse_period_s=10., pre_s=.2, post_s=.2, ring_frames=4,
                             ring_bytes=80, image_quota_bytes=32, maximum_trigger_windows=1)
        with tempfile.TemporaryDirectory() as temporary:
            root, outputs = Path(temporary), []
            for measured in (False, True):
                path = root / str(measured)
                kwargs = dict(policy=policy, clock=lambda: 100., physics_dt=.002)
                evidence = (InstrumentedFutureEvidence(path, 'same', phase=unmeasured, **kwargs) if measured
                            else FutureEvidence(path, 'same', **kwargs))
                evidence.store.flush_rows = 2
                sql = []
                evidence.store.db.set_trace_callback(sql.append)
                self.assertEqual(evidence.store.db.execute('PRAGMA journal_mode').fetchone()[0], 'delete')
                self.assertEqual(evidence.store.db.execute('PRAGMA synchronous').fetchone()[0], 2)
                for index in range(7):
                    evidence.motion.write(json.dumps({'sim_time_s': index * .01, 'q': [index, -0., None]}) + '\n')
                    evidence.store.image(str(index), index * .1, b'rgb', b'depth')
                first_trigger = evidence.trigger(.6, 1, 'diagnostic')
                second_trigger = evidence.trigger(.6, 2, 'quota')
                for index in range(7, 12):
                    evidence.store.image(str(index), index * .1, b'rgb', b'depth')
                evidence.emit('observation', {'exact': [1, 'utf8 é', -0.]}, 1.)
                evidence.document('note', {'text': 'retained'})
                ring = list(evidence.store.ring)
                rows = evidence.store.db.execute('SELECT id,status,reason,rgb,depth FROM images ORDER BY id').fetchall()
                fsync_sizes = []
                import os
                real_sync = os.fsync
                def sync(fd):
                    fsync_sizes.append(os.fstat(fd).st_size)
                    return real_sync(fd)
                with mock.patch('recorder.os.fsync', side_effect=sync):
                    evidence.close()
                outputs.append((sql, ring, rows, first_trigger, second_trigger, fsync_sizes,
                    {file.name: file.read_bytes() for file in path.iterdir()}))
                self.assertFalse((path / 'evidence.sqlite').exists())
                self.assertTrue(any(row[2] == 'image_quota_exhausted' for row in rows))
                self.assertTrue(any(row[1] == 'unavailable_by_policy' for row in rows))
            self.assertEqual(outputs[0], outputs[1])
            self.assertGreater(sum(statement == 'COMMIT' for statement in outputs[0][0]), 10)
            self.assertGreater(len(gzip.decompress(outputs[0][-1]['evidence.sqlite.gz'])), 0)

    def test_commit_failure_is_same_exception_once_with_same_pending_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            outputs = []
            for measured in (False, True):
                cls = InstrumentedRecorder if measured else Recorder
                rec = cls(Path(temporary) / str(measured), run_id='same',
                          **({'phase': unmeasured} if measured else {}))
                native = rec.db._connection if measured else rec.db
                error = sqlite3.OperationalError('injected commit failure')
                faulty = CommitFault(native, error)
                rec.db = TimedConnection(faulty, unmeasured) if measured else faulty
                with self.assertRaises(sqlite3.OperationalError) as raised:
                    rec.image('frame', 0., b'rgb', b'depth')
                self.assertIs(raised.exception, error)
                self.assertEqual(faulty.calls, 1)
                outputs.append((native.in_transaction, list(rec.ring), rec.image_bytes, rec.pending_bytes,
                    native.execute('SELECT * FROM images').fetchall(), rec.stopped))
                native.rollback(); native.close()
            self.assertEqual(outputs[0], outputs[1])

    def test_representative_quota_failure_and_marker_match(self):
        with tempfile.TemporaryDirectory() as temporary:
            outputs = []
            for measured in (False, True):
                path = Path(temporary) / str(measured)
                cls = InstrumentedRecorder if measured else Recorder
                rec = cls(path, run_id='same', representative=True, policy=ImagePolicy(image_quota_bytes=1),
                          **({'phase': unmeasured} if measured else {}))
                with self.assertRaises(RecordingFailure) as raised:
                    rec.image('frame', 0., b'rgb', b'depth')
                rec.close()
                outputs.append((str(raised.exception), rec.stopped, rec.pending_bytes, rec.image_bytes,
                    (path / 'RECORDING_FAILED.json').read_bytes(), (path / 'evidence.sqlite').read_bytes()))
                self.assertFalse((path / 'container-manifest.json').exists())
            self.assertEqual(outputs[0], outputs[1])

    def test_connection_native_cursor_attributes_context_and_error_semantics(self):
        native = sqlite3.connect(':memory:')
        connection = TimedConnection(native, unmeasured)
        try:
            connection.executescript('CREATE TABLE data(value INTEGER UNIQUE);')
            cursor = connection.execute('INSERT INTO data VALUES(?)', (1,))
            self.assertIs(cursor.connection, native)
            self.assertIs(type(cursor), sqlite3.Cursor)
            connection.commit()
            connection.row_factory = sqlite3.Row
            self.assertIs(native.row_factory, sqlite3.Row)
            self.assertEqual(connection.execute('SELECT value FROM data').fetchone()['value'], 1)
            with self.assertRaises(sqlite3.IntegrityError):
                with connection as entered:
                    self.assertIs(entered, connection)
                    connection.executemany('INSERT INTO data VALUES(?)', [(2,), (1,)])
            self.assertFalse(native.in_transaction)
            self.assertEqual([row[0] for row in native.execute('SELECT value FROM data')], [1])
        finally:
            connection.close()
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute('SELECT 1')

    def test_lock_reentrancy_exception_release_and_concurrent_event_serialization(self):
        lock = TimedLock(threading.RLock(), unmeasured)
        self.assertTrue(lock.acquire(blocking=False))
        with lock:
            self.assertTrue(lock.acquire(blocking=False))
            lock.release()
        lock.release()
        error = RuntimeError('injected protected operation failure')
        with self.assertRaises(RuntimeError) as raised:
            with lock:
                raise error
        self.assertIs(raised.exception, error)
        with ThreadPoolExecutor(max_workers=1) as pool:
            def check_released():
                acquired = lock.acquire(blocking=False)
                if acquired: lock.release()
                return acquired
            self.assertTrue(pool.submit(check_released).result())
        with tempfile.TemporaryDirectory() as temporary:
            evidence = InstrumentedFutureEvidence(Path(temporary) / 'threads', 'threads', phase=unmeasured)
            with ThreadPoolExecutor(max_workers=2) as pool:
                ids = list(pool.map(lambda value: evidence.emit('worker', {'value': value}, 0.), range(12)))
            evidence.close()
            reader = Reader(Path(temporary) / 'threads')
            try:
                events = list(reader.events())
                self.assertEqual(sorted(ids), list(range(1, 13)))
                self.assertEqual([row['event_id'] for row in events], list(range(1, 13)))
                self.assertEqual(sorted(row['payload']['value'] for row in events), list(range(12)))
            finally:
                reader.close()

    def test_commit_wait_is_localized_and_counted_in_complete_interval(self):
        with tempfile.TemporaryDirectory() as temporary:
            wall = [10.]
            capture = TimingCapture(10., 1., max_samples=10, clock=lambda: wall[0],
                                    cpu_clock=lambda: 0., process_cpu_clock=lambda: 0.)
            def phase(name):
                return nullcontext() if capture.terminal is not None else capture.phase(name, lambda: 1.)
            rec = InstrumentedRecorder(Path(temporary) / 'wait', run_id='wait', phase=phase)
            native = rec.db._connection
            class WaitingConnection:
                def __getattr__(self, name): return getattr(native, name)
                def commit(self):
                    wall[0] += .12
                    return native.commit()
            rec.db = TimedConnection(WaitingConnection(), phase)
            with capture.phase('adapter.bridge_observe', lambda: 1.):
                rec.image('frame', 0., b'rgb', b'depth')
            capture.finish(1., 'infrastructure_error')
            before = {name: dict(value) for name, value in capture.phases.items()}
            rec.close()  # Cleanup is deliberately outside the measured interval.
            self.assertEqual(capture.phases, before)
            self.assertAlmostEqual(capture.terminal['wall_elapsed_s'], .12)
            for name in ('adapter.bridge_observe', 'recorder.image', 'recorder.sqlite.commit'):
                row = capture.slow_by_phase[name][0][2]
                self.assertAlmostEqual(row['wall_duration_s'], .12)
                self.assertEqual(row['thread_cpu_duration_s'], 0.)
                self.assertEqual(row['process_cpu_duration_s'], 0.)
            self.assertLessEqual(len(PHASE_NAMES), 32)


if __name__ == '__main__':
    unittest.main()
