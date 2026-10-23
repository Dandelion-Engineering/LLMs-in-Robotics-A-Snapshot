"""Focused timing contract tests; no simulation, models or scheduling mutation."""
from array import array
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

from timing import TimingCapture, load_monitor, verify_timing, qpc_clock_context


class Clock:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value


class TimingTests(unittest.TestCase):
    def capture(self, origin=100., sim_origin=50., capacity=1000):
        clock = Clock(origin)
        capture = TimingCapture(origin, sim_origin, max_samples=capacity, clock=clock)
        return capture, clock

    def persist(self, root, capture):
        return capture.persist(root, {"applied": True, "restored": True})

    def test_common_origin_and_terminal_replay(self):
        capture, clock = self.capture()
        clock.value = 101.
        capture.sample(51.)
        clock.value = 101.4
        capture.finish(51.4, "task_success")
        # Cleanup advances wall time but must not enter the ended interval.
        clock.value = 900.
        with tempfile.TemporaryDirectory() as directory:
            binding = self.persist(directory, capture)
            result = verify_timing(directory)
            self.assertTrue(binding["passed"])
            self.assertEqual(result["complete_wall_windows"], 1)
            self.assertAlmostEqual(result["trailing_partial_window_s"], .4)
            self.assertEqual(binding["loop_origin"]["monotonic_s"], 100.)
            self.assertEqual(binding["loop_origin"]["initial_sim_s"], 50.)
            self.assertEqual(Path(directory, "timing-samples.bin").stat().st_size, 3 * 16)

    def test_lag_equality_fails(self):
        monitor_type, _ = load_monitor()
        monitor = monitor_type()
        monitor.observe(.1, 0.)
        monitor.observe(1., 1.)
        self.assertEqual(monitor.report()["maximum_lag_s"], .1)
        self.assertFalse(monitor.report()["actual_host_timing_pass"])

    def test_fraction_equality_fails_then_below_passes(self):
        monitor_type, _ = load_monitor()
        monitor = monitor_type()
        for wall in range(1, 101):
            monitor.observe(float(wall), wall - .06)
        self.assertEqual(monitor.report()["outside_rtf_tolerance_fraction"], .01)
        self.assertFalse(monitor.report()["actual_host_timing_pass"])
        monitor.observe(101., 100.94)
        self.assertTrue(monitor.report()["actual_host_timing_pass"])

    def test_rtf_endpoints_remain_inclusive(self):
        monitor_type, _ = load_monitor()
        for sim in (.95, 1.05):
            monitor = monitor_type()
            monitor.observe(1., sim)
            self.assertTrue(monitor.report()["actual_host_timing_pass"])

    def test_entry_sample_catches_lag_before_catchup(self):
        capture, clock = self.capture(origin=0., sim_origin=0.)
        clock.value = .12
        capture.sample(0.)
        capture.sample(.12)
        clock.value = 1.
        capture.finish(1., "task_success")
        self.assertFalse(capture.monitor.report()["actual_host_timing_pass"])
        self.assertEqual(capture.maximum_sample["lag_s"], .12)

    def test_capacity_and_terminal_are_fail_closed(self):
        capture, clock = self.capture(capacity=2)
        clock.value = 101.
        capture.finish(51., "task_success")
        with self.assertRaises(ValueError):
            capture.sample(51.)
        capture, clock = self.capture(capacity=2)
        capture.sample(50.)
        with self.assertRaises(ValueError):
            capture.sample(50.)

    def test_nan_and_regression_rejected(self):
        capture, _ = self.capture()
        with self.assertRaises(ValueError):
            capture.observe_relative(float("nan"), 0.)
        capture.observe_relative(1., 1.)
        with self.assertRaises(ValueError):
            capture.observe_relative(.9, 1.)

    def test_corruption_and_metadata_tampering_rejected(self):
        capture, clock = self.capture(origin=0., sim_origin=0.)
        clock.value = 1.
        capture.finish(1., "task_success")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.persist(root, capture)
            binary = root / "timing-samples.bin"
            metadata = root / "timing-v2.json"
            original = binary.read_bytes()
            info = json.loads(metadata.read_text())
            binary.write_bytes(original[:-1])
            with self.assertRaisesRegex(ValueError, "length"):
                verify_timing(root)
            corrupted = struct.pack("<dddd", 0., 0., float("nan"), 1.)
            binary.write_bytes(corrupted)
            info["sha256"] = hashlib.sha256(corrupted).hexdigest()
            metadata.write_text(json.dumps(info))
            with self.assertRaisesRegex(ValueError, "Invalid retained"):
                verify_timing(root)
            binary.write_bytes(original)
            info["sha256"] = hashlib.sha256(original).hexdigest()
            info["report"]["maximum_lag_s"] = .01
            metadata.write_text(json.dumps(info))
            with self.assertRaisesRegex(ValueError, "differs"):
                verify_timing(root)

    def test_phase_diagnostics_are_bounded(self):
        capture, clock = self.capture(origin=0., sim_origin=0.)
        for _ in range(200):
            with capture.phase("host_work", lambda: 0.):
                clock.value += .01
        self.assertEqual(capture.phases["host_work"]["count"], 200)
        self.assertEqual(len(capture.slow), 64)
        self.assertEqual(len(capture.slow_by_phase['host_work']), 8)
        self.assertIsInstance(capture.values, array)

    def test_nested_waits_retain_cpu_and_rare_phase(self):
        wall, thread, process = Clock(100.), Clock(10.), Clock(20.)
        capture = TimingCapture(100., 0., max_samples=10, clock=wall,
                                cpu_clock=thread, process_cpu_clock=process)
        for _ in range(100):
            with capture.phase('busy', lambda: 0.):
                wall.value += .2
        with capture.phase('publication', lambda: 0.):
            with capture.phase('publication.fsync', lambda: 0.):
                wall.value += .03
                process.value += .002
        # A smaller I/O wait survives its own bounded bucket after larger rows.
        self.assertNotIn('publication.fsync', [row[2]['phase'] for row in capture.slow])
        retained = capture.slow_by_phase['publication.fsync'][0][2]
        self.assertAlmostEqual(retained['wall_duration_s'], .03)
        self.assertEqual(retained['thread_cpu_duration_s'], 0.)
        self.assertAlmostEqual(retained['process_cpu_duration_s'], .002)
        self.assertAlmostEqual(capture.phases['publication']['wall_total_s'], .03)

    def test_phase_name_capacity_is_bounded(self):
        capture, clock = self.capture()
        for index in range(128):
            with capture.phase(str(index), lambda: 50.):
                pass
        with self.assertRaisesRegex(ValueError, 'phase-name capacity'):
            with capture.phase('overflow', lambda: 50.):
                pass

    def test_dual_clock_unix_anchor_and_qpc_default(self):
        # Real read-only clock metadata: no priority/timer or simulator changes.
        context = qpc_clock_context()
        self.assertEqual(context['primary_clock_name'], 'perf_counter')
        self.assertTrue(context['primary_clock']['monotonic'])
        anchor = context['cross_clock_sample']
        self.assertLessEqual(anchor['perf_counter_before_s'], anchor['perf_counter_after_s'])
        self.assertGreater(anchor['unix_s'], 0.)
        if context['primary_clock']['implementation'] == 'QueryPerformanceCounter()':
            self.assertGreater(context['qpc_frequency_hz'], 0)
        clock = Clock(10.)
        capture = TimingCapture(10., 0., max_samples=10, clock=clock,
                                clock_info=context['primary_clock'], clock_context=context)
        clock.value = 11.
        capture.finish(1., 'simulation_time_cap')
        with tempfile.TemporaryDirectory() as directory:
            result = self.persist(directory, capture)
            self.assertEqual(result['loop_origin']['clock_context'], context)
            self.assertEqual(result['loop_origin']['clock_name'], 'perf_counter')
            self.assertTrue(verify_timing(directory)['actual_host_timing_pass'])


if __name__ == "__main__":
    unittest.main()
