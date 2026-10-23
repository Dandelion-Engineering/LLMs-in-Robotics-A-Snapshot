"""Fault-injected durability parity; temporary files only, no simulator/model."""
from pathlib import Path
import ast
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'host'))
from supervisor import Journal, GatewayError, ATOMIC_REPLACE_RETRIES
from instrumented_journal import InstrumentedJournal
from timing import TimingCapture


class JournalInstrumentationTests(unittest.TestCase):
    def make(self, root, cls, name):
        return cls(root / name / 'protected', root / name / 'workspace', 'same-run')

    def test_adapter_control_ast_is_original_after_removing_measurement_scopes(self):
        here = Path(__file__).resolve().parent
        def step(path):
            module = ast.parse(path.read_text(encoding='utf-8'))
            adapter = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == 'PhysicalAdapter')
            return next(node for node in adapter.body if isinstance(node, ast.FunctionDef) and node.name == 'step')
        class RemoveMeasurement(ast.NodeTransformer):
            def visit_With(self, node):
                self.generic_visit(node)
                if (len(node.items) == 1 and isinstance(node.items[0].context_expr, ast.Call)
                        and isinstance(node.items[0].context_expr.func, ast.Attribute)
                        and isinstance(node.items[0].context_expr.func.value, ast.Name)
                        and node.items[0].context_expr.func.value.id == 'self'
                        and node.items[0].context_expr.func.attr == 'phase'):
                    return node.body
                return node
        original = step(here.parents[1] / 'host' / 'run_host.py')
        prospective = RemoveMeasurement().visit(step(here / 'run_host.py'))
        self.assertEqual(ast.dump(original, include_attributes=False), ast.dump(prospective, include_attributes=False))

    def test_original_and_instrumented_bytes_and_fsync_order_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outputs = []
            for name, cls in [('original', Journal), ('instrumented', InstrumentedJournal)]:
                journal = self.make(root, cls, name)
                journal.start = 100.
                fsync_sizes = []
                with mock.patch('time.monotonic', return_value=101.), mock.patch('time.time', return_value=200.), \
                     mock.patch('os.fsync', side_effect=lambda fd: fsync_sizes.append(os.fstat(fd).st_size)):
                    self.assertEqual(journal.event('observation', {'values': [1, 2]}, 50., 2, 'robot'), 1)
                    journal.state({'phase': 'waiting'})
                    journal.registry({'a': {'status': 'completed'}})
                    journal.continuity('retained note')
                outputs.append((journal.events, journal.bytes, fsync_sizes,
                                {str(path.relative_to(root / name)): path.read_bytes()
                                 for path in (root / name).rglob('*') if path.is_file()}))
            self.assertEqual(outputs[0], outputs[1])
            self.assertEqual(len(outputs[0][2]), 8)  # Two event, two state, registry, three note.

    def test_second_mirror_fsync_failure_preserves_original_failure_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, cls in [('original', Journal), ('instrumented', InstrumentedJournal)]:
                journal = self.make(root, cls, name)
                with mock.patch('os.fsync', side_effect=[None, OSError('injected mirror fsync failure')]):
                    with self.assertRaisesRegex(OSError, 'mirror fsync'):
                        journal.event('observation', {}, 1., 1, 'conventional')
                self.assertEqual(journal.events, [])
                self.assertEqual(journal.bytes, 0)
                self.assertEqual(journal.events_path.read_bytes(), journal.mirror_path.read_bytes())

    def test_storage_limit_rejects_before_any_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            journal = self.make(root, InstrumentedJournal, 'instrumented')
            journal.limit = 2 * 1024 * 1024
            with mock.patch('os.fsync') as sync:
                with self.assertRaises(GatewayError):
                    journal.event('observation', {}, 1., 1, 'conventional')
                sync.assert_not_called()
            self.assertFalse(journal.events_path.exists())
            self.assertFalse(journal.mirror_path.exists())

    def test_fsync_stall_is_nested_and_cleanup_not_measured(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            journal = self.make(root, InstrumentedJournal, 'instrumented')
            wall = [10.]
            capture = TimingCapture(10., 1., max_samples=10, clock=lambda: wall[0],
                                    cpu_clock=lambda: 0., process_cpu_clock=lambda: 0.)
            journal.capture, journal.sim_clock = capture, lambda: 1.
            def stall(fd):
                wall[0] += .03
            with mock.patch('os.fsync', side_effect=stall):
                journal.state({'value': 'safe'})
                capture.finish(1., 'operator_stop')
                journal.state({'value': 'stopped'})
            self.assertEqual(capture.phases['journal.state.protected.fsync']['count'], 1)
            self.assertEqual(capture.phases['journal.state.public.fsync']['count'], 1)
            self.assertAlmostEqual(capture.terminal['wall_elapsed_s'], .06)
            row = capture.slow_by_phase['journal.state.protected.fsync'][0][2]
            self.assertEqual(row['thread_cpu_duration_s'], 0.)
            self.assertAlmostEqual(row['wall_duration_s'], .03)

    def test_replace_retry_and_nonretryable_failure_remain_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            journal = self.make(root, InstrumentedJournal, 'instrumented')
            path = journal.root / 'test.json'
            path.write_bytes(b'old')
            denied = PermissionError('injected sharing denial')
            denied.winerror = 32
            real_replace = os.replace
            before = dict(ATOMIC_REPLACE_RETRIES)
            try:
                with mock.patch('os.replace', side_effect=[denied, None]) as replace, \
                     mock.patch('time.sleep') as sleep:
                    journal.atomic_bytes(path, b'new', 'test')
                    self.assertEqual(path.read_bytes(), b'old')
                    sleep.assert_called_once_with(.005)
                    self.assertEqual(replace.call_count, 2)
                    self.assertEqual(path.with_name(path.name + '.next').read_bytes(), b'new')
                self.assertEqual(ATOMIC_REPLACE_RETRIES['retries'], before['retries'] + 1)
                # Complete the mocked successful replacement and check exact staged bytes.
                real_replace(path.with_name(path.name + '.next'), path)
                self.assertEqual(path.read_bytes(), b'new')
                with mock.patch('os.replace', side_effect=OSError('nonretryable')), mock.patch('time.sleep') as sleep:
                    with self.assertRaisesRegex(OSError, 'nonretryable'):
                        journal.atomic_bytes(path, b'pending', 'test')
                    sleep.assert_not_called()
                self.assertEqual(path.read_bytes(), b'new')
            finally:
                ATOMIC_REPLACE_RETRIES.clear()
                ATOMIC_REPLACE_RETRIES.update(before)


if __name__ == '__main__':
    unittest.main()
