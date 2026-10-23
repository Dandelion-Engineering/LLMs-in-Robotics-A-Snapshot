"""Tiny fake clocks only; no Runtime, physics, native model, evidence or queue."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from boundary_catchup_fragment import wait_recovery_boundary_ready


class LimitReached(RuntimeError): pass


class FakeLoop:
    def __init__(self, *, wall=.06, sim=0., work=.0005, ready_after=0, cap=1.):
        self.start = 100.
        self.wall, self.elapsed, self.work, self.cap = wall, sim, work, cap
        self.steps = 0; self.ready_after = ready_after; self.observations = []
        self.audit = []; self.monitor = SimpleNamespace(observe=lambda wall, sim: self.observations.append((wall, sim)))
        self.timeouts = []; self.hold_checks = self.geometry_samples = 0

    def clock(self): return self.start + self.wall

    def public_ready(self): return self.steps >= self.ready_after

    def step(self):
        if self.wall >= self.cap or self.elapsed >= self.cap:
            raise LimitReached('ordinary cap')
        self.steps += 1; self.audit.append('ordinary_step')
        self.elapsed += .002; self.wall += self.work
        self.hold_checks += 1; self.geometry_samples += 1
        self.monitor.observe(self.wall, self.elapsed)

    def until(self, predicate, timeout):
        self.timeouts.append(timeout)
        limit = self.elapsed + timeout
        while self.elapsed < limit:
            self.step()
            if predicate(): return
        raise LimitReached('original phase timeout')


class BoundaryCatchupTests(unittest.TestCase):
    def call(self, loop, timeout=.2):
        with patch('boundary_catchup_fragment.time.perf_counter', side_effect=loop.clock):
            return wait_recovery_boundary_ready(loop, timeout)

    def test_target_is_fixed_even_if_new_work_keeps_wall_ahead(self):
        loop = FakeLoop(work=.002)
        report = self.call(loop)
        self.assertAlmostEqual(report['target_sim_elapsed_s'], .06)
        self.assertGreater(report['residual_lag_s'], .05)
        self.assertLess(loop.steps, 33)  # A moving wall<=sim target would never finish.
        self.assertAlmostEqual(loop.start, 100.)
        self.assertEqual(loop.timeouts, [.2])

    def test_peak_lag_is_recorded_before_any_catchup_and_history_is_preserved(self):
        loop = FakeLoop(); loop.observations.append((.01, .01))
        report = self.call(loop)
        self.assertEqual(loop.observations[0], (.01, .01))
        self.assertAlmostEqual(loop.observations[1][0], .06)
        self.assertEqual(loop.observations[1][1], 0.)
        self.assertEqual(loop.observations[-1], (report['exit_wall_elapsed_s'], report['exit_sim_elapsed_s']))
        self.assertEqual(loop.steps, loop.hold_checks)
        self.assertEqual(loop.steps, loop.geometry_samples)
        self.assertEqual(loop.audit, ['ordinary_step'] * loop.steps)

    def test_freshness_still_requires_ordinary_steps_after_target(self):
        loop = FakeLoop(wall=.004, ready_after=5)
        report = self.call(loop)
        self.assertEqual(loop.steps, 5)
        self.assertGreater(report['exit_sim_elapsed_s'], report['target_sim_elapsed_s'])

    def test_already_current_keeps_original_at_least_one_step_and_no_clock_reset(self):
        loop = FakeLoop(wall=.005, sim=.01)
        report = self.call(loop)
        self.assertEqual(loop.steps, 1)
        self.assertEqual(report['target_sim_elapsed_s'], .01)
        self.assertEqual(loop.start, 100.)

    def test_original_timeout_and_cap_are_not_extended_or_swallowed(self):
        loop = FakeLoop(wall=.06)
        with self.assertRaisesRegex(LimitReached, 'original phase timeout'): self.call(loop, .004)
        self.assertEqual(loop.timeouts, [.004])
        loop = FakeLoop(wall=.06, cap=.061, work=.001)
        with self.assertRaisesRegex(LimitReached, 'ordinary cap'): self.call(loop)
        self.assertGreater(len(loop.observations), 0)


if __name__ == '__main__': unittest.main()
