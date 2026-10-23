"""Temporary manifests only: exact native policy parity and method closure."""
import ast
from contextlib import ExitStack, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch
import zipfile

import prepare_native as candidate
import prepare_boundary_v3 as boundary
import prepare_model_v18 as model

BASELINE_SOURCE_SHA256 = 'a5ac5185e5e53486899bd118bc1f63fe7578a5b65aeca1ab137848ab50f8e10c'
BASELINE_ARCHIVE = candidate.RCI.parent / 'Architecture Map/releases/RCI001-C02-dev-039/code.zip'
QUIESCENCE_CAMPAIGN_INPUTS = (
    'qualification/prepare_model_v14.py', 'qualification/test_prepare_model_v14.py',
    'io-repair/shutdown-diagnostic-002-failure-analysis.json',
    'io-repair/shutdown-diagnostic-002-failure-analysis.md',
    'harness/codehost_mux_protocol.py', 'harness/test_codehost_mux_protocol.py',
    'assessment/transport_integrity_v3.py', 'assessment/test_transport_integrity_v3.py',
    'io-repair/PREFLIGHT_V3_LIFECYCLE_JOIN_V1.md',
    'qualification/prepare_model_v13.py', 'qualification/test_prepare_model_v13.py',
    'io-repair/codehost-channel-source-001/codex-rs__core__src__config__mod.rs',
    'io-repair/native-output-source-002/codex-rs__app-server__src__request_processors__thread_lifecycle.rs',
    'io-repair/native-unsubscribe-source-001/codex-rs__app-server__src__lib.rs',
    'io-repair/native-unsubscribe-source-001/codex-rs__app-server__src__outgoing_message.rs',
    'io-repair/native-unsubscribe-source-001/codex-rs__app-server__src__request_processors__thread_processor.rs',
    'io-repair/native-unsubscribe-source-001/source-evidence.json',
    'io-repair/native-unsubscribe-source-001/analysis.md',
    'io-repair/native-unsubscribe-source-001/analysis.json',
    'io-repair/native-unsubscribe-source-001/codex-rs__app-server__src__transport.rs',
    'io-repair/native-unsubscribe-source-001/codex-rs__config__src__config_toml.rs',
    'qualification/prepare_model_v12.py', 'qualification/test_prepare_model_v12.py',
    'io-repair/native-shutdown-source-001/codex-rs__core__src__codex_thread.rs',
    'io-repair/native-shutdown-source-001/codex-rs__core__src__session__handlers.rs',
    'io-repair/native-shutdown-source-001/source-evidence.json',
    'io-repair/native-shutdown-source-001/analysis.md',
) + model.prior.prior.prior.CLEANUP_INPUTS + model.prior.prior.READ_EVIDENCE_INPUTS + model.prior.PREPARED_STARTUP_INPUTS + model.REVOCATION_READBACK_INPUTS
QUIESCENCE_SCHEMA_INPUTS = tuple('isolation-session-9/native/app-server-schema/v2/' + name for name in (
    'ThreadUnsubscribeParams.json', 'ThreadUnsubscribeResponse.json', 'ThreadClosedNotification.json',
    'TurnInterruptParams.json', 'TurnInterruptResponse.json', 'TurnCompletedNotification.json'))


def baseline():
    """Load only the hash-pinned historical preparer, never an outcome file."""
    name = Path(candidate.__file__).relative_to(candidate.REPO).as_posix()
    with zipfile.ZipFile(BASELINE_ARCHIVE) as archive:
        source = archive.read(name)
    if hashlib.sha256(source).hexdigest() != BASELINE_SOURCE_SHA256:
        raise ValueError('Historical native preparer source changed')
    module = ModuleType('native_inventory_policy_baseline')
    module.__file__ = candidate.__file__
    exec(compile(source, name, 'exec'), module.__dict__)
    return module


class NativeManifestTests(unittest.TestCase):
    def setUp(self):
        self.old = baseline()
        self.temp = tempfile.TemporaryDirectory(prefix='native-inventory-test-')
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.rci = self.repo / 'experiment/integration'
        self.campaign = self.rci / 'campaign-002'
        self.here = self.campaign / 'qualification'
        self.here.mkdir(parents=True)
        for name in ('harness/runtime.py', 'assessment/assess.py',
                     'qualification/native_suite.py', 'qualification/assess_native.py',
                     'qualification/prepare_native.py', 'qualification/test_prepare_native.py',
                     *candidate.METHOD_FILES, *QUIESCENCE_CAMPAIGN_INPUTS):
            path = self.campaign / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Source fixture: ' + name, encoding='utf-8')
        # The new inventory supplier is loaded dynamically by the actual
        # preparer. Copy both real modules so this fixture exercises that import
        # and the real source enumeration, rather than mocking its output.
        for name in ('prepare_model_v18.py', 'prepare_model_v17.py', 'prepare_model_v16.py', 'prepare_model_v15.py', 'prepare_model_v14.py', 'prepare_model_v13.py', 'prepare_model_v12.py', 'prepare_model_v11.py'):
            (self.here / name).write_bytes((candidate.HERE / name).read_bytes())
        for name in QUIESCENCE_SCHEMA_INPUTS:
            path = self.rci / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Schema fixture: ' + name, encoding='utf-8')
        path = self.rci / 'readiness-session-10/assessment/assess.py'
        path.parent.mkdir(parents=True)
        path.write_text('Readiness fixture', encoding='utf-8')
        self.stack = self.enterContext(ExitStack())
        for module in (candidate, self.old):
            for key, value in (('HERE', self.here), ('CAMPAIGN', self.campaign),
                               ('RCI', self.rci), ('REPO', self.repo),
                               ('__file__', str(self.here / 'prepare_native.py'))):
                self.stack.enter_context(patch.object(module, key, value))
        self.stack.enter_context(patch.dict(os.environ, {'LOCALAPPDATA': str(self.repo / 'local')}))

    def run_preparer(self, module, path, extra=()):
        log = io.StringIO()
        with patch('sys.argv', ['prepare_native.py', '--revision', 'RCI001-C02-dev-046',
                               '--run-id', 'RCI001-C02-native-014', '--output', str(path), *extra]), \
             redirect_stdout(log):
            module.main()
        return json.loads(path.read_bytes()), json.loads(log.getvalue())

    def compare(self, extra=()):
        old, old_log = self.run_preparer(self.old, self.here / 'old.json', extra)
        new, new_log = self.run_preparer(candidate, self.here / 'new.json', extra)
        old_inputs, new_inputs = old.pop('runtime_input_files'), new.pop('runtime_input_files')
        self.assertEqual(old, new)  # Every episode, policy, limit and workspace field.
        self.assertEqual(old_log, new_log)
        additions = {str((self.campaign / name).relative_to(self.repo)).replace('\\', '/')
                     for name in (*candidate.METHOD_FILES, 'qualification/test_prepare_native.py',
                                  *QUIESCENCE_CAMPAIGN_INPUTS)}
        additions |= {str((self.rci / name).relative_to(self.repo)).replace('\\', '/')
                      for name in QUIESCENCE_SCHEMA_INPUTS}
        self.assertEqual(set(new_inputs), set(old_inputs) | additions)
        # The unchanged preparer sorts Path objects. Windows paths compare
        # without case, now visible with the added lowercase packet directory.
        self.assertEqual(new_inputs, [p.relative_to(self.repo).as_posix()
                                      for p in sorted({self.repo / name for name in new_inputs})])
        self.assertEqual([s['manifest']['seed'] for s in new['slots']], [173] * 6)
        self.assertEqual([s['manifest']['noise_seed'] for s in new['slots']],
                         list(range((int(extra[1]) if extra else 24000) + 1,
                                    (int(extra[1]) if extra else 24000) + 7)))
        self.assertEqual([s['manifest']['family'] for s in new['slots']],
                         ['misplaced-stock', 'blocked-insert-home'] * 3)
        self.assertEqual([(s['manifest']['sim_cap_s'], s['manifest']['wall_cap_s'],
                           s['manifest']['storage_cap_bytes']) for s in new['slots']],
                         [(240, 420, 209715200)] * 6)

    def test_default_six_episode_manifest_matches_pinned_old_preparer(self):
        self.compare()

    def test_explicit_seed_option_preserves_all_old_manifest_semantics(self):
        self.compare(('--seed-base', '25000'))

    def test_each_method_and_own_test_are_required_before_output_creation(self):
        for name in (*candidate.METHOD_FILES, 'qualification/test_prepare_native.py'):
            with self.subTest(name=name):
                path = self.campaign / name
                raw = path.read_bytes(); path.unlink()
                output = self.here / 'missing.json'
                try:
                    with self.assertRaisesRegex(ValueError, 'missing or linked source|Missing or linked quiescence input|Missing or linked unload scheduling input|Missing or linked terminal control input|Missing or linked native cleanup input|Missing or linked (initial-read evidence|prepared-startup|revocation/readback) input'):
                        self.run_preparer(candidate, output)
                    self.assertFalse(output.exists())
                finally:
                    path.write_bytes(raw)

    def test_linked_method_cannot_be_declared(self):
        selected = self.campaign / candidate.METHOD_FILES[-1]
        original = Path.is_symlink
        with patch.object(Path, 'is_symlink', lambda p: p == selected or original(p)):
            with self.assertRaisesRegex(ValueError, 'missing or linked source|Missing or linked quiescence input|Missing or linked unload scheduling input|Missing or linked terminal control input|Missing or linked native cleanup input|Missing or linked (initial-read evidence|prepared-startup|revocation/readback) input'):
                candidate.inventory()

    def test_existing_manifest_bytes_are_never_replaced(self):
        output = self.here / 'existing.json'
        raw = b'preserved native manifest\r\n'; output.write_bytes(raw)
        with self.assertRaises(FileExistsError):
            self.run_preparer(candidate, output)
        self.assertEqual(output.read_bytes(), raw)


class ActualSourceClosureTests(unittest.TestCase):
    def test_v26_method_core_is_measured_and_frozen_by_every_stage_preparer(self):
        tree = ast.parse((candidate.HERE / 'run_final_qualification_v26.py').read_bytes())
        methods = {candidate.CAMPAIGN / node.value.right.value for node in tree.body
                   if isinstance(node, ast.Assign) and isinstance(node.value, ast.BinOp)
                   and any(isinstance(t, ast.Name) and t.id.endswith('_METHOD')
                           for t in node.targets)}
        count = len(methods)
        self.assertIn(candidate.CAMPAIGN / 'io-repair/PREPARED_STARTUP_SEGMENTS_V1.md', methods)
        methods.add(candidate.CAMPAIGN / 'io-repair/CODEHOST_CHANNEL_TRANSPORT_V3.md')
        self.assertEqual(methods, {candidate.CAMPAIGN / name for name in candidate.METHOD_FILES})
        self.assertEqual(len(methods), count + 1)
        names = {p.relative_to(candidate.REPO).as_posix() for p in methods}
        native = {p.relative_to(candidate.REPO).as_posix() for p in candidate.inventory()}
        for kind, sources in (('native', native), ('boundary measured', boundary.boundary_suite.sources()),
                              ('boundary declared', boundary.inventory()), ('model', model.runtime_inputs())):
            with self.subTest(kind=kind):
                self.assertTrue(names <= set(sources), sorted(names - set(sources)))


if __name__ == '__main__':
    unittest.main()
