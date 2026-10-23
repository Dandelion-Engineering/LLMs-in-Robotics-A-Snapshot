"""Source-only operator admission controls; no process or queue launches."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

IO = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('v28_operator_under_test', IO / 'control_pilot_retirement_inventory_qualification.py')
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)
c = control.c


class OperatorGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='v28-source-only-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.checks = self.root / 'io-repair/checks-031'
        self.checks.mkdir(parents=True)
        self.lineage = self.root / 'io-repair/lineage.json'
        self.state = self.root / 'io-repair/source-state.json'
        self.snapshot = self.root / 'snapshot.json'
        self.patch = patch.multiple(control, C=self.root, CHECKS=self.checks,
                                    LINEAGE_CHECKS=self.lineage, SNAP=self.snapshot, SOURCE_STATE=self.state)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.repo_patch = patch.object(c, 'REPO', self.root)
        self.repo_patch.start()
        self.addCleanup(self.repo_patch.stop)
        commands, sources = [], {}
        for name in ('harness', 'assessment'):
            folder = self.root / name
            folder.mkdir()
            source = folder / 'test_fixture.py'
            source.write_text('import unittest\n', encoding='utf-8')
            out, err = self.checks / (name + '.out'), self.checks / (name + '.err')
            out.write_text('', encoding='utf-8')
            err.write_text('synthetic successful test receipt\n', encoding='utf-8')
            commands.append({'argv': [str(c.PYTHON), '-X', 'utf8', '-B', '-m', 'unittest',
                'discover', '-s', str(folder), '-p', 'test_*.py', '-v'], 'exit_code': 0,
                'test_sources_unchanged': True, 'test_inputs': [c.identity(source)],
                'stdout': c.identity(out), 'stderr': c.identity(err)})
            sources[source.relative_to(self.root).as_posix()] = {
                'sha256': c.sha(source), 'bytes': source.stat().st_size}
        self.tests = {'passed': True, 'commands': commands}
        self.write(self.checks / 'test-execution.json', self.tests)
        self.write(self.lineage, {'passed': True, 'source_bindings': sources})
        self.write(self.snapshot, {'sources': sources})
        self.write(self.state, {'passed': True, 'sources_unchanged': True,
            'tests': c.identity(self.checks / 'test-execution.json'),
            'sources': [c.identity(self.root / name) for name in sources]})
        self.declaration = {'development_checks': c.identity(self.checks / 'test-execution.json'),
            'lineage_checks': c.identity(self.lineage), 'development_source_state': c.identity(self.state),
            'stages': [['native-027', 'native', 'RCI001-C02-dev-088', 24000]]}
        self.repair = {'schema': c.TEST_RECEIPT_SCHEMA, 'passed': True,
            'source_snapshot': c.identity(self.snapshot), 'commands': copy.deepcopy(commands)}
        self.write(self.checks / 'repair-test-receipt.json', self.repair)

    @staticmethod
    def write(path, value):
        path.write_text(json.dumps(value), encoding='utf-8')

    def gate(self):
        with patch.object(control, 'bound_declaration', side_effect=self.bound), \
                patch.object(c, 'assert_sources', return_value={}) as source_gate:
            result = control.submission_gate()
            source_gate.assert_called_once()
            return result

    def bound(self):
        control.development_gate(self.declaration)
        return self.declaration

    def test_success_requires_declared_checks_and_same_bound_commands(self):
        self.assertEqual(self.gate(), self.declaration)

    def test_missing_bind_receipt_blocks_before_submission(self):
        (self.checks / 'repair-test-receipt.json').unlink()
        with self.assertRaises(FileNotFoundError):
            self.gate()

    def test_stale_declared_test_receipt_blocks(self):
        self.tests['commands'][0]['exit_code'] = 1
        self.write(self.checks / 'test-execution.json', self.tests)
        with self.assertRaises(ValueError):
            self.gate()

    def test_changed_lineage_source_blocks(self):
        (self.root / 'harness/test_fixture.py').write_text('# changed\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Lineage source changed'):
            self.gate()

    def test_new_unrun_test_is_not_silently_admitted(self):
        (self.root / 'assessment/test_late.py').write_text('import unittest\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'source set changed'):
            self.gate()

    def test_wrong_frozen_snapshot_blocks(self):
        self.repair['source_snapshot']['sha256'] = '0' * 64
        self.write(self.checks / 'repair-test-receipt.json', self.repair)
        with self.assertRaisesRegex(ValueError, 'not bound'):
            self.gate()

    def test_new_untested_production_module_blocks_before_freeze(self):
        (self.root / 'late_runtime.py').write_text('new_runtime = True\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'production source set changed'):
            self.gate()

    def test_source_change_during_test_run_blocks(self):
        state = c.read(self.state)
        state['sources_unchanged'] = False
        self.write(self.state, state)
        self.declaration['development_source_state'] = c.identity(self.state)
        with self.assertRaisesRegex(ValueError, 'not unchanged'):
            self.gate()

    def test_different_successful_bound_commands_do_not_replace_declared_tests(self):
        self.repair['commands'].reverse()
        self.write(self.checks / 'repair-test-receipt.json', self.repair)
        with self.assertRaisesRegex(ValueError, 'differs from declared'):
            self.gate()

    def test_corrupt_frozen_sources_propagate_before_submission(self):
        with patch.object(control, 'bound_declaration', side_effect=self.bound), \
                patch.object(c, 'assert_sources', side_effect=ValueError('frozen sources changed')):
            with self.assertRaisesRegex(ValueError, 'frozen sources changed'):
                control.submission_gate()

    def test_every_launch_checks_gate_before_any_mutation(self):
        for action in (lambda: control.launch_probe('raw'), lambda: control.launch_probe('transport'),
                       control.launch_host, lambda: control.submit(self.root, [], [], [])):
            with self.subTest(action=action), \
                    patch.object(control, 'submission_gate', side_effect=ValueError('not admitted')), \
                    patch.object(c, 'command_once') as command, patch.object(c, 'save') as save:
                with self.assertRaisesRegex(ValueError, 'not admitted'):
                    action()
                command.assert_not_called()
                save.assert_not_called()


if __name__ == '__main__':
    unittest.main()
