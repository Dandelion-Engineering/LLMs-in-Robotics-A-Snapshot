"""Original-plan selector/metadata checks with AST-only imports and no physics."""
import ast
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parent / 'Recovery Qualification'


def load_functions(path, names, namespace):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    if {n.name for n in nodes} != set(names):
        raise AssertionError('Expected pure functions missing')
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path) + ' [pure functions only]', 'exec'), namespace)


class DiagnosticSelectionTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((FIXTURE / 'plan-001.json').read_bytes())
        self.namespace = {}
        load_functions(FIXTURE / 'measurement.py', ['selected_trials'], self.namespace)
        load_functions(FIXTURE / 'run_screen.py', ['execution_selection', 'manifest_execution'], self.namespace)
        self.select = self.namespace['execution_selection']
        self.verify = self.namespace['manifest_execution']
        self.identity = 'parking1-corner-B-5'

    def test_one_exact_original_trial_all_other_ids_deferred_without_plan_mutation(self):
        before = copy.deepcopy(self.plan)
        trials, deferred, metadata = self.select(self.plan, 'parking1', 'construction', self.identity)
        self.assertEqual(self.plan, before)
        self.assertEqual(len(self.plan['trials']), 40)
        self.assertEqual(len(trials), 1)
        self.assertIs(trials[0], next(t for t in self.plan['trials'] if t['id'] == self.identity))
        self.assertEqual(len(deferred), 39)
        self.assertEqual(deferred, [t['id'] for t in self.plan['trials'] if t['id'] != self.identity])
        self.assertEqual({k: trials[0][k] for k in ('population', 'world_seed', 'layout_seed', 'family', 'expected_payload_id')},
                         {'population': 10, 'world_seed': 901001, 'layout_seed': 901001, 'family': 'B', 'expected_payload_id': 'B10'})
        self.assertTrue(metadata['diagnostic_only'])
        self.assertFalse(metadata['is_full_phase_screen'])
        self.assertFalse(metadata['qualification_evidence_eligible'])
        self.assertEqual(metadata['diagnostic_trial_id'], self.identity)

    def test_rejects_validation_wrong_destination_unknown_independent_and_duplicate(self):
        independent = next(t['id'] for t in self.plan['trials'] if t['fixture'] == 'independent_generator')
        for destination, phase, identity in [('parking1', 'validation', self.identity),
                ('parking2', 'construction', self.identity), ('all', 'construction', independent),
                ('all', 'construction', 'missing'), ('all', 'construction', '')]:
            with self.subTest(destination=destination, phase=phase, identity=identity):
                with self.assertRaises(ValueError): self.select(self.plan, destination, phase, identity)
        self.plan['trials'].append(copy.deepcopy(next(t for t in self.plan['trials'] if t['id'] == self.identity)))
        with self.assertRaises(ValueError): self.select(self.plan, 'all', 'construction', self.identity)

    def test_manifest_scope_guard_and_normal_selection_unchanged(self):
        for destination, expected, deferred_count in [('parking1', 14, 6), ('all', 28, 12)]:
            rows, deferred, metadata = self.select(self.plan, destination, 'construction')
            self.assertEqual(rows, self.namespace['selected_trials'](self.plan, destination, 'construction'))
            self.assertEqual((len(rows), len(deferred)), (expected, deferred_count))
            self.assertFalse(metadata['diagnostic_only'])
            self.assertTrue(metadata['is_full_phase_screen'])
        trials, deferred, metadata = self.select(self.plan, 'parking1', 'construction', self.identity)
        manifest = {'destination_selection': 'parking1', 'execution_phase': 'construction',
            'modes': [self.identity], 'phase_deferred_trial_ids': deferred, **metadata}
        self.assertEqual(self.verify(self.plan, manifest), (trials, deferred, metadata))
        for key, value in [('diagnostic_only', False), ('is_full_phase_screen', True),
                ('qualification_evidence_eligible', True), ('modes', []), ('phase_deferred_trial_ids', deferred[:-1]),
                ('diagnostic_trial_id', None), ('execution_scope', 'declared_phase_screen')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.verify(self.plan, {**manifest, key: value})

    def test_existing_extractor_and_assessor_full_phase_guards_reject_diagnostic(self):
        modes = [self.identity]
        extractor = ast.parse((FIXTURE / 'extract_screen.py').read_text(encoding='utf-8'))
        call = next(n for n in ast.walk(extractor) if isinstance(n, ast.Call) and len(n.args) > 1
                    and isinstance(n.args[1], ast.Constant) and n.args[1].value == 'Declared destination/phase selection mismatch')
        scope = {'selection': 'parking1', 'modes': modes, 'plan': self.plan, 'fixture': 'construction'}
        self.assertFalse(eval(compile(ast.Expression(body=call.args[0]), '<unchanged extractor guard>', 'eval'), scope))
        assessor = ast.parse((HERE / 'assess_validation.py').read_text(encoding='utf-8'))
        call = next(n for n in ast.walk(assessor) if isinstance(n, ast.Call) and len(n.args) > 1
                    and isinstance(n.args[1], ast.Constant) and n.args[1].value == 'Declared selection differs')
        selected = [t['id'] for t in self.namespace['selected_trials'](self.plan, 'parking1', 'construction')]
        scope = {'self': SimpleNamespace(manifest={'modes': modes}, selected=selected)}
        self.assertFalse(eval(compile(ast.Expression(body=call.args[0]), '<unchanged assessor guard>', 'eval'), scope))


if __name__ == '__main__':
    unittest.main()
