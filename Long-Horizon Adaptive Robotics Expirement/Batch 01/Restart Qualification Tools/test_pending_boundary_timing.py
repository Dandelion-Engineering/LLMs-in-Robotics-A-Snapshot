"""Bounded source/stub checks only; no Runtime import, physics or queue."""
import ast
import copy
import hashlib
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import pending_boundary_timing as proposal


class MarkerError(BaseException):
    pass


def functions(source, names, namespace):
    tree = ast.parse(source)
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in nodes} != set(names):
        raise AssertionError('Requested source functions are missing')
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<source-only timing test>', 'exec'), namespace)
    return namespace


class StubRun:
    def __init__(self, *, failing=None, cut_attempts=1):
        self.log = []
        self.wall = 100.
        self.failing = failing
        self.error = MarkerError('exact original boundary failure')
        self.calls = {}
        self.cut_attempts = cut_attempts
        self.capture_count = 0
        self.details = {'stage': 'construction', 'physical_predicates_passed': False,
                        'verified_cut': False, 'qualification_granted': False, 'trial': {},
                        'boundary_operation_timings': []}
        self.cell = SimpleNamespace(data=SimpleNamespace(time=1., qpos=[0.] * 7 + [.025, .025],
                         site_xpos={(0, 2): .081}), tcp=0, segment={'phase': 4},
                         last_detections={'A1': {'family': 'A'}}, detection_time=1.)
        self.cell.cancel = lambda reason: self.operation('cancel', reason)
        self.loop = SimpleNamespace(cells=[self.cell], start=100., zones={}, zone_half=.05,
            latest=[SimpleNamespace(sequence=3)], incarnation=1, physical_source_hashes={'fake': 'source'})
        self.loop.records = SimpleNamespace(sequence=0, event=self.event)
        self.loop.public_ready = self.public_ready
        self.loop.until = self.until
        self.loop.step = self.step
        self.loop.snapshot = self.snapshot
        self.loop.submit = self.submit
        self.loop.terminal = lambda rid, timeout: self.operation('terminal', rid, timeout)
        self.restart = ModuleType('restart_state')
        self.restart.capture_restart_state = self.capture
        self.restart.classify_restart = lambda value: self.operation('classify', value, cost=.02) or {'state': 'unknown'}
        self.geometry = ModuleType('geometry_trace')
        outer = self

        class Trace:
            def __init__(self, loop, identity, interval):
                self.phase = 'approach'
                outer.operation('trace_init', identity, interval)

            def sample(self, force=False):
                return outer.operation('sample', self.phase, force, cost=.03)

        class Window:
            def __init__(self, identity, sim, wall):
                outer.operation('window_init', identity, sim, wall)
                self.data = {'ticks_with_hold_predicate_false': 0, 'all_recorded_hold_checks_pass': True}

            def record(self, snapshot, sim, wall, tick):
                outer.operation('window_record', snapshot, sim, wall, tick)

        class Stable:
            since = None

            def update(self, sim, passed):
                self.since = sim
                return passed

        self.geometry.GeometryTrace = Trace
        self.namespace = {'time': SimpleNamespace(perf_counter=lambda: self.wall),
            'base': SimpleNamespace(CalibrationFailure=RuntimeError, StablePredicate=Stable,
                placement_check=lambda *args: {'passed_now': True}),
            'HoldWindow': Window, 'select_public': lambda *args: 'A1',
            'retained_hold_check': lambda *args: True,
            'cut_eligible': lambda *args, **kwargs: self.capture_count >= self.cut_attempts,
            'physical_trial_pass': lambda **kwargs: all(kwargs.values())}

    def operation(self, name, *args, cost=0.):
        self.calls[name] = self.calls.get(name, 0) + 1
        self.log.append((name, copy.deepcopy(args)))
        self.wall += cost
        if self.failing == (name, self.calls[name]):
            raise self.error

    def capture(self, cell, **kwargs):
        self.operation('capture', kwargs, cost=.01)
        self.capture_count += 1
        return {'contacts': {'by_object': {'A1': {'bilateral_force_bearing': True}}},
                'geometry': {'fixture_only': True}, 'capture': self.capture_count}

    def event(self, kind, payload, sim=None):
        self.operation('event', kind, payload, sim)
        self.loop.records.sequence += 1
        return self.loop.records.sequence

    def snapshot(self):
        self.operation('snapshot')
        return {'fixture_only': True}

    def public_ready(self):
        self.operation('public_ready')
        return True

    def until(self, predicate, timeout):
        self.operation('until', predicate.__name__, timeout)
        for _ in range(3):
            if predicate():
                return
            self.step()
        raise AssertionError('Synthetic predicate exceeded its bounded attempts')

    def step(self):
        self.operation('step')
        self.wall += .002
        self.cell.data.time += .002
        if getattr(self.loop, 'hold_window', None):
            self.loop.hold_window.record(self.snapshot(), self.cell.data.time, self.wall - self.loop.start, tick=True)
        if getattr(self.loop, 'geometry_trace', None):
            self.loop.geometry_trace.sample()

    def submit(self, action):
        self.operation('submit', action)
        self.event('action_admission', action, self.cell.data.time)
        return 'request-' + str(self.loop.records.sequence)

    def run(self, source, instrumented):
        names = ['trial_body'] + (['boundary_operation'] if instrumented else [])
        functions(source, names, self.namespace)
        trial = {'family': 'A', 'id': 'synthetic', 'expected_payload_id': 'A1', 'destination': 'parking1'}
        plan = {'public_selection': 'synthetic', 'geometry_interval_s': .02,
                'cut': {'timeout_s': 1.}, 'absence_s': .004}
        with patch.dict('sys.modules', {'restart_state': self.restart, 'geometry_trace': self.geometry}):
            return self.namespace['trial_body'](self.loop, trial, plan, self.details)


class BoundaryTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.target_initial = proposal.TARGET.read_bytes()
        archive = proposal.HERE / 'source-archive' / ('run_screen.' + proposal.BASE_SHA256 + '.py')
        cls.raw = archive.read_bytes() if archive.exists() else cls.target_initial
        cls.original = cls.raw.decode('utf-8')
        cls.candidate = proposal.candidate_source(cls.original)

    def test_full_trial_call_order_outputs_and_repeat_capture_preserved(self):
        before = hashlib.sha256(proposal.TARGET.read_bytes()).hexdigest()
        original, changed = StubRun(cut_attempts=2), StubRun(cut_attempts=2)
        self.assertIsNone(original.run(self.original, False))
        self.assertIsNone(changed.run(self.candidate, True))
        self.assertEqual(original.log, changed.log)
        timings = changed.details.pop('boundary_operation_timings')
        original.details.pop('boundary_operation_timings')
        self.assertEqual(original.details, changed.details)
        self.assertEqual(len(timings), 15)  # Two candidate captures, five landmarks, one classifier, seven forced samples.
        self.assertEqual(sum(r['label'] == 'capture_restart_state:cut_candidate' for r in timings), 2)
        self.assertEqual([r['label'].split(':', 1)[1] for r in timings if r['label'].startswith('GeometryTrace.sample:')],
                         list(proposal.FORCED_LABELS))
        for row in timings:
            self.assertTrue(row['success'])
            self.assertEqual(row['sim_start_s'], row['sim_end_s'])
            expected = .03 if row['label'].startswith('GeometryTrace') else .02 if row['label'].startswith('classify') else .01
            self.assertAlmostEqual(row['wall_cost_s'], expected)
            self.assertAlmostEqual(row['wall_end_s'] - row['wall_start_s'], expected)
            self.assertGreaterEqual(row['wall_start_s'], 0.)
            self.assertIsInstance(row['stage'], str)
        self.assertEqual(hashlib.sha256(proposal.TARGET.read_bytes()).hexdigest(), before)

    def test_exception_identity_partial_outputs_and_call_order_preserved(self):
        for failing in [('capture', 1), ('capture', 3), ('classify', 1), ('sample', 1), ('sample', 4)]:
            with self.subTest(failing=failing):
                original, changed = StubRun(failing=failing), StubRun(failing=failing)
                for run, source, instrumented in ((original, self.original, False), (changed, self.candidate, True)):
                    with self.assertRaises(MarkerError) as raised:
                        run.run(source, instrumented)
                    self.assertIs(raised.exception, run.error)
                self.assertEqual(original.log, changed.log)
                timings = changed.details.pop('boundary_operation_timings')
                original.details.pop('boundary_operation_timings')
                self.assertEqual(original.details, changed.details)
                if failing == ('sample', 4):
                    # This is an ordinary per-tick sample: unchanged and not
                    # relabeled as a timed boundary operation.
                    self.assertTrue(all(r['success'] for r in timings))
                else:
                    self.assertFalse(timings[-1]['success'])
                    self.assertEqual(sum(r['success'] is False for r in timings), 1)

    def test_wrapper_exact_return_and_exception_at_nonzero_sim_interval(self):
        run = StubRun()
        wrapper = functions(self.candidate, ['boundary_operation'], run.namespace)['boundary_operation']
        token = object()
        def operation(arg, *, named):
            self.assertIs(arg, token)
            self.assertEqual(named, 'untouched')
            run.wall += .012
            run.cell.data.time += .004
            return token
        self.assertIs(wrapper(run.loop, run.details, 'stub', operation, token, named='untouched'), token)
        row = run.details['boundary_operation_timings'][0]
        self.assertAlmostEqual(row['wall_cost_s'], .012)
        self.assertEqual(row['sim_start_s'], 1.)
        self.assertEqual(row['sim_end_s'], 1.004)

    def test_exact_source_guard_and_no_per_tick_geometry_instrumentation(self):
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), proposal.BASE_SHA256)
        with self.assertRaises(ValueError): proposal.candidate_source(self.original + '\n')
        old, new = ast.parse(self.original), ast.parse(self.candidate)
        old_loop = next(n for n in old.body if isinstance(n, ast.ClassDef) and n.name == 'QualificationLoop')
        new_loop = next(n for n in new.body if isinstance(n, ast.ClassDef) and n.name == 'QualificationLoop')
        self.assertEqual(ast.dump(old_loop), ast.dump(new_loop))
        self.assertEqual(proposal.TARGET.read_bytes(), self.target_initial)
        if self.target_initial != self.raw:
            installed_source = self.target_initial.decode('utf-8')
            scheduler = "    details['stage'] = 'fresh_sensing_before_recovery'\n    details['recovery_boundary_pacing'] = wait_recovery_boundary_ready(loop, 8.)\n"
            feedback = "    details['stage'] = 'fresh_sensing_before_recovery'\n    details['recovery_boundary_pacing'] = {}\n    wait_recovery_boundary_ready(loop, 8., details['recovery_boundary_pacing'])\n"
            original_wait = "    details['stage'] = 'fresh_sensing_before_recovery'\n    loop.until(loop.public_ready, 8.)\n"
            if feedback in installed_source:
                self.assertEqual(installed_source.count(feedback), 1)
                installed_source = installed_source.replace(feedback, original_wait, 1)
            if scheduler in installed_source:
                self.assertEqual(installed_source.count(scheduler), 1)
                # The separately authorized scheduler is the sole permitted
                # trial-body difference; all instrumentation remains exact.
                installed_source = installed_source.replace(scheduler, original_wait, 1)
            installed = ast.parse(installed_source)
            for name in ('boundary_operation', 'trial_body'):
                expected = next(n for n in new.body if isinstance(n, ast.FunctionDef) and n.name == name)
                actual = next(n for n in installed.body if isinstance(n, ast.FunctionDef) and n.name == name)
                self.assertEqual(ast.dump(actual), ast.dump(expected))


if __name__ == '__main__':
    unittest.main()
