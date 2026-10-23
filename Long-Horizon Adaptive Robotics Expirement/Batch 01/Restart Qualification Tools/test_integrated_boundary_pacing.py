"""Installed scheduler tested with fake clocks/stub operations only."""
import ast
from types import SimpleNamespace
import unittest

import test_boundary_catchup_fragment as fragment_tests
from test_pending_boundary_timing import StubRun, functions
import pending_boundary_timing as timing


class IntegratedPacingTests(unittest.TestCase):
    def call(self, loop, timeout=.2, report=None):
        source = timing.TARGET.read_text(encoding='utf-8')
        namespace = {'time': SimpleNamespace(perf_counter=loop.clock)}
        functions(source, ['wait_recovery_boundary_ready'], namespace)
        loop.dt = .002
        loop.hold_window = SimpleNamespace(data={'physics_tick_checks': 7})
        original_step = loop.step
        def counted_step():
            original_step()
            loop.hold_window.data['physics_tick_checks'] += 1
        loop.step = counted_step
        report = namespace['wait_recovery_boundary_ready'](loop, timeout, report)
        self.assertEqual(report['entry_hold_tick_checks'], 7)
        self.assertEqual(report['exit_hold_tick_checks'], 7 + loop.steps)
        self.assertEqual(report['hold_tick_checks_added'], loop.steps)
        return report

    def test_feedback_catches_new_work_to_at_most_one_tick_debt(self):
        loop = fragment_tests.FakeLoop(work=.001)
        report = self.call(loop)
        self.assertTrue(report['success'])
        self.assertEqual(report['readiness_lag_limit_s'], loop.dt)
        self.assertLessEqual(report['last_predicate_lag_s'], loop.dt)
        self.assertLessEqual(report['residual_lag_s'], loop.dt)
        self.assertAlmostEqual(report['fixed_entry_target_reference_sim_s'], .06)
        self.assertGreater(loop.elapsed, report['fixed_entry_target_reference_sim_s'])
        self.assertGreater(loop.steps, 40)
        self.assertEqual(loop.timeouts, [.2])
        self.assertEqual(loop.start, 100.)

    def test_monitor_history_and_every_ordinary_hold_geometry_tick_preserved(self):
        loop = fragment_tests.FakeLoop(); loop.observations.append((.01, .01))
        report = self.call(loop)
        self.assertEqual(loop.observations[0], (.01, .01))
        self.assertAlmostEqual(loop.observations[1][0], .06)
        self.assertEqual(loop.observations[1][1], 0.)
        self.assertEqual(loop.observations[-1], (report['exit_wall_elapsed_s'], report['exit_sim_elapsed_s']))
        self.assertEqual(loop.steps, loop.hold_checks)
        self.assertEqual(loop.steps, loop.geometry_samples)
        self.assertEqual(report['predicate_observations'], loop.steps)
        self.assertEqual(loop.audit, ['ordinary_step'] * loop.steps)

    def test_fresh_sensing_work_precedes_fresh_lag_measurement(self):
        loop = fragment_tests.FakeLoop(wall=.004, sim=0., work=.0001, ready_after=5)
        original = loop.public_ready
        def slow_public_ready():
            loop.wall += .0015
            return original()
        loop.public_ready = slow_public_ready
        report = self.call(loop)
        self.assertGreater(loop.steps, 5)
        self.assertLessEqual(report['residual_lag_s'], loop.dt)
        self.assertAlmostEqual(report['last_predicate_wall_elapsed_s'], loop.wall)

    def test_already_current_keeps_original_at_least_one_step(self):
        loop = fragment_tests.FakeLoop(wall=.005, sim=.01)
        report = self.call(loop)
        self.assertEqual(loop.steps, 1)
        self.assertLessEqual(report['residual_lag_s'], loop.dt)
        self.assertEqual(loop.start, 100.)

    def test_persistent_overload_propagates_original_timeout_and_cap_with_partial_report(self):
        for loop, timeout, expected in [
                (fragment_tests.FakeLoop(wall=.06, work=.002), .008, 'original phase timeout'),
                (fragment_tests.FakeLoop(wall=.06, cap=.061, work=.001), .2, 'ordinary cap')]:
            with self.subTest(expected=expected):
                report = {}
                with self.assertRaisesRegex(fragment_tests.LimitReached, expected):
                    self.call(loop, timeout, report)
                self.assertFalse(report['success'])
                self.assertIn(expected, report['error'])
                self.assertEqual(loop.timeouts, [timeout])
                self.assertEqual(report['hold_tick_checks_added'], loop.steps)
                self.assertEqual(loop.observations[-1], (report['exit_wall_elapsed_s'], report['exit_sim_elapsed_s']))
                self.assertGreater(report['residual_lag_s'], loop.dt)
                self.assertEqual(loop.start, 100.)

    def test_trial_only_replaces_one_existing_wait_preserving_all_boundary_operations(self):
        source = timing.TARGET.read_text(encoding='utf-8')
        archive = timing.HERE / 'source-archive/run_screen.7af9eb67b5b367b545682785069859cb9a7cb9a9f2f670d25ebd6894a70ade11.py'
        previous = archive.read_text(encoding='utf-8')
        old, new = StubRun(), StubRun()
        scheduler_calls = []
        token = {'synthetic_pacing_metadata': True}
        def scheduler(loop, timeout, report):
            scheduler_calls.append((new.details['stage'], timeout, loop.hold_window is not None))
            loop.until(loop.public_ready, timeout)
            report.update(token)
            return report
        new.namespace['wait_recovery_boundary_ready'] = scheduler
        old.run(previous, True)
        new.run(source, True)
        self.assertEqual(scheduler_calls, [('fresh_sensing_before_recovery', 8., True)])
        self.assertEqual(old.log, new.log)
        self.assertEqual(new.details.pop('recovery_boundary_pacing'), token)
        self.assertEqual(old.details, new.details)
        # All other functions/classes, including child caps, trial selector and
        # every ordinary hold/geometry/monitor step, remain structurally exact.
        before = ast.parse(previous)
        after = ast.parse(source)
        old_nodes = {n.name: n for n in before.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        new_nodes = {n.name: n for n in after.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        self.assertEqual(set(new_nodes) - set(old_nodes), {'wait_recovery_boundary_ready'})
        for name in old_nodes:
            if name != 'trial_body':
                self.assertEqual(ast.dump(old_nodes[name]), ast.dump(new_nodes[name]), name)


if __name__ == '__main__':
    unittest.main()
