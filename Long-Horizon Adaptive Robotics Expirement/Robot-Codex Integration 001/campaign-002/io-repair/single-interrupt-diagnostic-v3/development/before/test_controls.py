"""Prospective reset wrapper checks; no real prepare, freeze, queue or native run."""
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import common

PREP = common.load(common.HERE.parent / 'prepare_reset_diagnostic.py', 'reset_preparer_test')
CONTROL = common.load(common.HERE.parent / 'control_reset_diagnostic.py', 'reset_control_test')

class ControlTests(unittest.TestCase):
    def test_runner_and_launcher_are_byte_identical_to_original(self):
        old = common.HERE.parent / 'single-interrupt-diagnostic'
        for name in ('run.py', 'launch.py'):
            self.assertEqual((common.HERE/name).read_bytes(), (old/name).read_bytes())

    def test_fixed_identity_method_and_check_inventory(self):
        self.assertEqual(common.RUN, 'RCI001-C02-shutdown-diagnostic-002')
        self.assertEqual(common.REVISION, 'RCI001-C02-dev-062')
        self.assertEqual(common.PROTOCOL, 'RCI001-Campaign002-single-interrupt-diagnostic-v2')
        self.assertEqual(common.REFERENCE.name, 'smoke-019-manifest.json')
        self.assertEqual(common.METHOD.name, 'RESET_REJECTION_DIAGNOSTIC_V1.md')
        required = set(common.required_inputs())
        for path in (Path(PREP.__file__), Path(CONTROL.__file__), Path(__file__)):
            self.assertIn(path.relative_to(common.REPO).as_posix(), required)

    def test_preparer_preserves_smoke_policy_and_rejects_existing_output(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            target = Path(folder)/'diagnostic/manifest.json'
            with patch.object(PREP, 'OUTPUT', target):
                PREP.main()
                manifest = common.read(target)
                basis = common.read(common.REFERENCE)
                self.assertEqual(common.sha(common.REFERENCE), common.REFERENCE_SHA256)
                common.validate_manifest(manifest)
                changed = sorted(k for k in manifest if manifest[k] != basis.get(k))
                self.assertEqual(changed, ['framework_revision', 'model_turns_max', 'outer_campaign_protocol',
                    'qualification_stage', 'run_id', 'runtime_input_files', 'runtime_workspace'])
                self.assertTrue(set(basis['runtime_input_files']) <= set(manifest['runtime_input_files']))
                receipt = common.read(target.with_name('preparation-receipt.json'))
                self.assertEqual(receipt['basis']['sha256'], common.REFERENCE_SHA256)
                self.assertFalse(receipt['resume_allowed']); self.assertFalse(receipt['retry_allowed'])
                with self.assertRaises(FileExistsError): PREP.main()

    def test_preparer_rejects_changed_basis_before_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); basis = root/'basis.json'; target = root/'unused/manifest.json'
            value = common.read(common.REFERENCE); value['invocation_wall_cap_s'] = 601
            basis.write_text(json.dumps(value), encoding='utf-8')
            with patch.object(PREP, 'BASIS', basis), patch.object(PREP, 'OUTPUT', target):
                with self.assertRaisesRegex(ValueError, 'policy basis changed'): PREP.main()
            self.assertFalse(target.parent.exists())

    def fake_control(self, *, changed=None, passed=True, wrong_snapshot=False):
        mux = (common.CAMPAIGN/'harness/codehost_mux_protocol.py').relative_to(common.REPO).as_posix()
        before = {mux:{'sha256':'a'*64,'bytes':1}}
        after = copy.deepcopy(before)
        for name in changed if changed is not None else [mux]:
            if name not in before: before[name] = {'sha256':'a'*64,'bytes':1}
            after[name] = {'sha256':'b'*64,'bytes':2}
        snapshot_id = {'path':str(CONTROL.SNAPSHOT.resolve()),'sha256':'f'*64}
        def read(path):
            text = str(path)
            if text.endswith('source-change-inventory.json'): return {'after':snapshot_id}
            if text.endswith('repair-test-receipt.json'):
                return {'passed':passed,'source_snapshot':{} if wrong_snapshot else snapshot_id}
            return {'sources': before if 'dev-061' in text else after}
        return SimpleNamespace(REPO=common.REPO, read=Mock(side_effect=read), identity=Mock(return_value=snapshot_id),
            save_exact=Mock(), python=lambda *args:[str(x) for x in args],
            command_once=Mock(return_value={'exit_code':0,'stdout':''}),
            admission=SimpleNamespace(artifact=Mock()))

    def control_action(self, action, fake, folder):
        with patch.object(CONTROL, 'c', fake), patch.object(CONTROL, 'JOURNAL', Path(folder)/'journal'), \
             patch('sys.argv', ['control_reset_diagnostic.py',action]), redirect_stdout(io.StringIO()):
            CONTROL.main()

    def test_control_journals_exact_fresh_prepare_and_launch(self):
        with tempfile.TemporaryDirectory() as folder:
            fake=self.fake_control(); self.control_action('prepare',fake,folder)
            call=fake.command_once.call_args
            self.assertIn(str(common.HERE.parent/'prepare_reset_diagnostic.py'), call.args[2])
            self.assertEqual(call.kwargs['absent'], [CONTROL.MANIFEST.parent])
            fake=self.fake_control(); self.control_action('launch',fake,folder)
            call=fake.command_once.call_args
            self.assertIn(str(common.HERE/'launch.py'),call.args[2])
            self.assertIn(common.HERE.parent/'checks-022/repair-test-receipt.json',call.kwargs['inputs'])
            self.assertEqual(call.kwargs['absent'], [CONTROL.MANIFEST.parent/'records',common.RAW])
            fake.admission.artifact.assert_called_once()

    def test_control_refuses_unbound_or_failed_checks_before_launch_command(self):
        for passed,wrong in ((False,False),(True,True)):
            with self.subTest(passed=passed,wrong=wrong),tempfile.TemporaryDirectory() as folder:
                fake=self.fake_control(passed=passed,wrong_snapshot=wrong)
                with self.assertRaisesRegex(ValueError,'Bound diagnostic checks missing'):
                    self.control_action('launch',fake,folder)
                fake.command_once.assert_not_called()

    def test_control_inventory_rejects_unrelated_changed_source(self):
        bad=(common.CAMPAIGN/'harness/runtime.py').relative_to(common.REPO).as_posix()
        with tempfile.TemporaryDirectory() as folder:
            fake=self.fake_control(changed=[bad])
            with self.assertRaisesRegex(ValueError,'Unexpected diagnostic source changes'):
                self.control_action('freeze',fake,folder)
            fake.save_exact.assert_not_called()
        with tempfile.TemporaryDirectory() as folder:
            fake=self.fake_control();self.control_action('freeze',fake,folder)
            self.assertTrue(fake.save_exact.call_args.args[1]['diagnostic_only'])

if __name__=='__main__': unittest.main()
