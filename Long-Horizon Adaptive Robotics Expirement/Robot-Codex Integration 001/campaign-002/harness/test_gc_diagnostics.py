"""GC observation fault tests without model/simulation or collector policy changes."""
from pathlib import Path
import tempfile
import unittest

from gc_diagnostics import GcDiagnostics, read_gc
from timing import TimingCapture


class FakeGc:
    def __init__(self):
        self.callbacks = []
        self.enabled = True
        self.thresholds = (700, 10, 10)
    def isenabled(self): return self.enabled
    def get_threshold(self): return self.thresholds
    def get_debug(self): return 0
    def get_freeze_count(self): return 0
    def get_count(self): return (10, 2, 1)
    def get_stats(self): return [dict(collections=0, collected=0, uncollectable=0) for _ in range(3)]
    def disable(self): raise AssertionError('GC policy mutation forbidden')
    def enable(self): raise AssertionError('GC policy mutation forbidden')
    def collect(self): raise AssertionError('GC policy mutation forbidden')
    def set_threshold(self, *args): raise AssertionError('GC policy mutation forbidden')
    def freeze(self): raise AssertionError('GC policy mutation forbidden')
    def emit(self, phase, generation, collected=0, uncollectable=0):
        for callback in list(self.callbacks):
            callback(phase, dict(generation=generation, collected=collected, uncollectable=uncollectable))


class GcDiagnosticsTests(unittest.TestCase):
    def make(self, capacity=10):
        api = FakeGc()
        clocks = dict(wall=100., cpu=10., process=20., sim=50., thread=17, phase='evaluator')
        capture = GcDiagnostics(lambda: clocks['phase'], lambda: clocks['sim'], capacity=capacity, api=api,
                                clock=lambda: clocks['wall'], thread_clock=lambda: clocks['cpu'],
                                process_clock=lambda: clocks['process'], thread_id=lambda: clocks['thread'])
        return capture, api, clocks

    def test_overlapping_evaluator_gc_is_bound_and_replayable(self):
        capture, api, clocks = self.make()
        capture.attach()
        api.emit('start', 2)
        clocks.update(wall=100.093, cpu=10.093, process=20.093)
        api.emit('stop', 2, collected=21)
        self.assertTrue(capture.detach())
        with tempfile.TemporaryDirectory() as directory:
            binding = capture.persist(directory, 100., 50.)
            rows = read_gc(directory, binding)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['host_phase'], 'evaluator')
            self.assertEqual(rows[0]['generation'], 2)
            self.assertEqual(rows[0]['collected'], 21)
            self.assertAlmostEqual(rows[0]['wall_end_s'], .093)
            self.assertAlmostEqual(rows[0]['thread_cpu_duration_s'], .093)
            self.assertEqual(rows[0]['on_host_thread'], 1)
            self.assertEqual(rows[0]['sim_end_s'], 0.)
            self.assertEqual(binding['collector_policy_mutations'], [])
        self.assertEqual(api.callbacks, [])
        self.assertTrue(api.enabled)
        self.assertEqual(api.thresholds, (700, 10, 10))

    def test_other_thread_identity_prevents_false_host_attribution(self):
        capture, api, clocks = self.make()
        capture.attach()
        clocks['thread'] = 99
        api.emit('start', 0)
        clocks['wall'] += .01
        api.emit('stop', 0)
        capture.detach()
        with tempfile.TemporaryDirectory() as directory:
            rows = read_gc(directory, capture.persist(directory, 100., 50.))
            self.assertEqual(rows[0]['on_host_thread'], 0)
            self.assertEqual(rows[0]['collecting_native_thread_id'], 99)

    def test_capacity_overflow_and_incomplete_callbacks_fail_closed(self):
        for mode in ('overflow', 'unfinished', 'mismatch', 'missing_start'):
            with self.subTest(mode=mode):
                capture, api, clocks = self.make(capacity=1)
                capture.attach()
                if mode == 'missing_start':
                    api.emit('stop', 1)
                else:
                    api.emit('start', 1)
                    if mode != 'unfinished':
                        api.emit('stop', 2 if mode == 'mismatch' else 1)
                    if mode == 'overflow':
                        api.emit('start', 1)
                        api.emit('stop', 1)
                self.assertFalse(capture.detach())
                self.assertEqual(api.callbacks, [])
                with tempfile.TemporaryDirectory() as directory:
                    with self.assertRaisesRegex(ValueError, 'diagnostic evidence failed'):
                        capture.persist(directory, 100., 50.)

    def test_other_callbacks_preserved_and_external_changes_rejected(self):
        capture, api, clocks = self.make()
        unrelated = lambda phase, info: None
        api.callbacks.append(unrelated)
        capture.attach()
        api.thresholds = (701, 10, 10)
        self.assertFalse(capture.detach())
        self.assertEqual(api.callbacks, [unrelated])
        self.assertIn('policy changed', capture.error)
        # Detach is idempotent and never removes another observer.
        self.assertFalse(capture.detach())
        self.assertEqual(api.callbacks, [unrelated])

    def test_empty_ledger_and_boundary_before_origin_are_explicit(self):
        capture, api, clocks = self.make()
        capture.attach()
        api.emit('start', 1)
        clocks['wall'] = 100.001
        api.emit('stop', 1)
        clocks['wall'] = 102.
        capture.detach()
        with tempfile.TemporaryDirectory() as directory:
            binding = capture.persist(directory, 100.01, 50.)
            rows = read_gc(directory, binding)
            self.assertLess(rows[0]['wall_end_s'], 0.)
            self.assertLess(binding['attached_wall_elapsed_s'], 0.)
        capture, api, clocks = self.make()
        capture.attach(); capture.detach()
        with tempfile.TemporaryDirectory() as directory:
            binding = capture.persist(directory, 100., 50.)
            self.assertEqual(read_gc(directory, binding), [])
            self.assertEqual(binding['byte_count'], 0)

    def test_corrupt_ledger_is_rejected(self):
        capture, api, clocks = self.make()
        capture.attach(); api.emit('start', 0); api.emit('stop', 0); capture.detach()
        with tempfile.TemporaryDirectory() as directory:
            binding = capture.persist(directory, 100., 50.)
            path = Path(directory) / binding['sample_file']
            path.write_bytes(path.read_bytes()[:-1])
            with self.assertRaisesRegex(ValueError, 'byte count'):
                read_gc(directory, binding)

    def test_host_phase_restores_through_nested_exception(self):
        capture = TimingCapture(0., 0., max_samples=2, clock=lambda: 0., cpu_clock=lambda: 0.,
                                process_cpu_clock=lambda: 0.)
        self.assertIsNone(capture.active_phase)
        with capture.phase('adapter', lambda: 0.):
            self.assertEqual(capture.active_phase, 'adapter')
            with self.assertRaises(RuntimeError):
                with capture.phase('publication', lambda: 0.):
                    self.assertEqual(capture.active_phase, 'publication')
                    raise RuntimeError('injected')
            self.assertEqual(capture.active_phase, 'adapter')
        self.assertIsNone(capture.active_phase)


class DeferralGc(FakeGc):
    def __init__(self):
        super().__init__()
        self.debug = 0
        self.calls = []
    def get_debug(self): return self.debug
    def disable(self): self.calls.append('disable'); self.enabled = False
    def enable(self): self.calls.append('enable'); self.enabled = True
    def set_threshold(self, *values): self.calls.append('set_threshold'); self.thresholds = tuple(values)
    def set_debug(self, value): self.calls.append('set_debug'); self.debug = value


class CollectorDeferralTests(unittest.TestCase):
    def make(self, enabled=True):
        api = DeferralGc(); api.enabled = enabled
        clocks = {'wall': 10., 'sim': 1.}
        capture = GcDiagnostics(lambda: 'evaluator', lambda: clocks['sim'], api=api,
            clock=lambda: clocks['wall'], thread_clock=lambda: 0., process_clock=lambda: 0., thread_id=lambda: 17)
        capture.attach()
        return capture, api, clocks

    def test_deferral_restores_and_retains_collection_after_terminal(self):
        capture, api, clocks = self.make()
        capture.defer()
        self.assertFalse(api.enabled)
        clocks.update(wall=11., sim=2.)
        capture.verify_deferred(full=True)
        self.assertTrue(capture.restore())
        self.assertTrue(api.enabled)
        api.emit('start', 2)
        clocks['wall'] += .09
        api.emit('stop', 2, collected=12)
        capture.detach()
        with tempfile.TemporaryDirectory() as directory:
            binding = capture.persist(directory, 10., 1., {'wall_elapsed_s': 1.})
            self.assertTrue(binding['passed'])
            self.assertEqual(binding['schema'], 'rci-gc-diagnostics-2')
            self.assertEqual(binding['measured_interval_collection_count'], 0)
            row = read_gc(directory, binding)[0]
            self.assertEqual(row['wall_start_s'], 1.)
            self.assertAlmostEqual(row['wall_end_s'], 1.09)
            self.assertEqual(binding['policy']['restore_start_wall_elapsed_s'], 1.)
        self.assertEqual(api.calls, ['disable', 'enable'])
        self.assertEqual(api.callbacks, [])

    def test_original_disabled_state_is_restored(self):
        capture, api, clocks = self.make(enabled=False)
        capture.defer(); clocks['wall'] = 11.
        self.assertTrue(capture.restore()); capture.detach()
        self.assertFalse(api.enabled)
        self.assertEqual(api.calls, ['disable', 'disable'])

    def test_exception_and_external_mutation_restore_all_original_settings(self):
        capture, api, clocks = self.make()
        try:
            capture.defer()
            api.thresholds = (701, 11, 12); api.debug = 8
            raise RuntimeError('injected host failure')
        except RuntimeError:
            clocks['wall'] = 11.
        finally:
            self.assertFalse(capture.restore())
            capture.detach()
        self.assertTrue(api.enabled)
        self.assertEqual(api.thresholds, (700, 10, 10))
        self.assertEqual(api.debug, 0)
        self.assertTrue(capture.policy['configuration_restored'])
        self.assertIn('configuration changed', capture.error)

    def test_unexpected_collection_and_enable_are_invalid(self):
        for failure in ('collection', 'enabled'):
            capture, api, clocks = self.make()
            capture.defer(); clocks['wall'] = 10.5
            if failure == 'collection':
                api.emit('start', 0); clocks['wall'] += .01; api.emit('stop', 0)
            else:
                api.enable()
            with self.assertRaises(RuntimeError): capture.verify_deferred()
            clocks['wall'] = 11.
            self.assertFalse(capture.restore()); capture.detach()
            with tempfile.TemporaryDirectory() as directory:
                self.assertFalse(capture.persist(directory, 10., 1., {'wall_elapsed_s': 1.})['passed'])

    def test_restoration_attempts_enabled_state_after_threshold_restore_failure(self):
        capture, api, clocks = self.make()
        capture.defer(); api.thresholds = (701, 10, 10)
        def failure(*values): raise OSError('injected threshold restoration failure')
        api.set_threshold = failure
        clocks['wall'] = 11.
        self.assertFalse(capture.restore()); capture.detach()
        self.assertTrue(api.enabled)
        self.assertFalse(capture.policy['configuration_restored'])
        self.assertEqual(len(capture.policy['restore_errors']), 1)


if __name__ == '__main__':
    unittest.main()
