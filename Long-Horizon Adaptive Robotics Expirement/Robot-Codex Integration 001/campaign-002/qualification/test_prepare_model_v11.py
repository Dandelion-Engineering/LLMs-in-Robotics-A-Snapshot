"""Manifest-only temporary fixtures; compare against unchanged preparer source."""
from contextlib import ExitStack, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import prepare_model as original
import prepare_model_v11 as prospective


class ModelManifestV10Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='model-manifest-v11-test-')
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.rci = self.repo / 'experiment/integration'
        self.campaign = self.rci / 'campaign-002'
        self.here = self.campaign / 'qualification'
        self.here.mkdir(parents=True)
        self.original_source_hash = hashlib.sha256(Path(original.__file__).read_bytes()).hexdigest()
        # Actual predeclared templates, copied into a temporary fixture only.
        for relative in ('readiness-session-10/records/smoke-002-manifest.json',
                         'campaign-001/predeclared-v1/RCI001-C01-stock-01.json',
                         'campaign-001/predeclared-v1/RCI001-C01-home-01.json'):
            target = self.rci / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((original.RCI / relative).read_bytes())
        for relative in ('campaign-002/harness/runtime.py', 'campaign-002/harness/additional_source.py',
                         'campaign-002/assessment/assess.py', 'campaign-002/assessment/test_assess.py',
                         'readiness-session-10/assessment/assess_bootstrap.py',
                         'campaign-002/qualification/native_suite.py',
                         'campaign-002/transport-repair.md', 'campaign-002/timing-repair.md',
                         'campaign-002/qualification/smoke-001-read-diagnosis.md',
                         'campaign-002/qualification/prepare_model.py',
                         'campaign-002/qualification/prepare_model_v2.py',
                         'campaign-002/qualification/test_prepare_model_v2.py',
                         'campaign-002/qualification/prepare_model_v3.py',
                         'campaign-002/qualification/test_prepare_model_v3.py',
                         'campaign-002/qualification/prepare_model_v4.py',
                         'campaign-002/qualification/test_prepare_model_v4.py',
                         'campaign-002/qualification/prepare_model_v5.py',
                         'campaign-002/qualification/test_prepare_model_v5.py',
                         'campaign-002/qualification/prepare_model_v6.py',
                         'campaign-002/qualification/test_prepare_model_v6.py',
                         'campaign-002/qualification/prepare_model_v7.py',
                         'campaign-002/qualification/test_prepare_model_v7.py',
                         'campaign-002/qualification/prepare_model_v8.py',
                         'campaign-002/qualification/test_prepare_model_v8.py',
                         'campaign-002/qualification/prepare_model_v9.py',
                         'campaign-002/qualification/test_prepare_model_v9.py',
                         'campaign-002/qualification/prepare_model_v10.py',
                         'campaign-002/qualification/test_prepare_model_v10.py',
                         'campaign-002/qualification/prepare_model_v11.py',
                         'campaign-002/qualification/test_prepare_model_v11.py',
                         *('campaign-002/' + name for name in prospective.METHOD_FILES)):
            target = self.rci / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('Source fixture: ' + relative, encoding='utf-8')
        evidence = self.campaign / prospective.SOURCE_EVIDENCE
        evidence.mkdir(parents=True)
        for name in ('source-evidence.json', 'native.rs'):
            (evidence / name).write_text('Fixture ' + name, encoding='utf-8')
        channel = self.campaign / prospective.CHANNEL_EVIDENCE
        channel.mkdir(parents=True)
        for name in ('source-evidence.json', 'native.rs'):
            (channel / name).write_text('Fixture ' + name, encoding='utf-8')
        schema = self.rci / prospective.RAW_SCHEMA
        schema.parent.mkdir(parents=True, exist_ok=True)
        schema.write_text('{}', encoding='utf-8')
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for module in (original, prospective):
            for name, value in (('REPO', self.repo), ('RCI', self.rci), ('CAMPAIGN', self.campaign), ('HERE', self.here)):
                self.stack.enter_context(patch.object(module, name, value))
        self.stack.enter_context(patch.dict(os.environ, {'LOCALAPPDATA': str(self.repo / 'local-appdata')}))

    def arguments(self, kind, output):
        return ['--kind', kind, '--revision', 'dev-future', '--run-id', 'fixture-' + kind,
                '--seed', '31973', '--output', str(output)]

    def compare_kind(self, kind):
        old_path, new_path = self.here / (kind + '-original.json'), self.here / (kind + '-prospective.json')
        old_log, new_log = io.StringIO(), io.StringIO()
        with patch('sys.argv', ['prepare_model.py', *self.arguments(kind, old_path)]), redirect_stdout(old_log):
            original.main()
        with redirect_stdout(new_log):
            prospective.main(self.arguments(kind, new_path))
        old, new = json.loads(old_path.read_bytes()), json.loads(new_path.read_bytes())
        old_inputs, new_inputs = old.pop('runtime_input_files'), new.pop('runtime_input_files')
        self.assertEqual(old, new)  # Every policy/model/noise/path field, not a sampled subset.
        self.assertEqual(json.loads(old_log.getvalue()), json.loads(new_log.getvalue()))
        additions = [self.here / name for name in ('prepare_model.py', 'prepare_model_v2.py', 'test_prepare_model_v2.py', 'prepare_model_v3.py', 'test_prepare_model_v3.py', 'prepare_model_v4.py', 'test_prepare_model_v4.py', 'prepare_model_v5.py', 'test_prepare_model_v5.py', 'prepare_model_v6.py', 'test_prepare_model_v6.py', 'prepare_model_v7.py', 'test_prepare_model_v7.py', 'prepare_model_v8.py', 'test_prepare_model_v8.py', 'prepare_model_v9.py', 'test_prepare_model_v9.py', 'prepare_model_v10.py', 'test_prepare_model_v10.py', 'prepare_model_v11.py', 'test_prepare_model_v11.py')]
        additions += [self.campaign / name for name in prospective.METHOD_FILES]
        additions += list((self.campaign / prospective.SOURCE_EVIDENCE).iterdir())
        additions += [self.rci / prospective.RAW_SCHEMA]
        additions += list((self.campaign / prospective.CHANNEL_EVIDENCE).iterdir())
        expected = set(old_inputs) | {path.relative_to(self.repo).as_posix() for path in additions}
        self.assertEqual(set(new_inputs), expected)
        self.assertEqual(len(new_inputs), len(set(new_inputs)))
        self.assertEqual(new_inputs, sorted(new_inputs))
        self.assertTrue(all((self.repo / name).is_file() for name in new_inputs))
        self.assertEqual(hashlib.sha256(Path(original.__file__).read_bytes()).hexdigest(), self.original_source_hash)

    def test_smoke_manifest_preserves_every_original_policy_field(self):
        self.compare_kind('smoke')

    def test_stock_manifest_preserves_every_original_policy_field(self):
        self.compare_kind('stock')

    def test_home_manifest_preserves_every_original_policy_field(self):
        self.compare_kind('home')

    def test_each_method_document_is_required_before_output_creation(self):
        for name in prospective.METHOD_FILES:
            with self.subTest(name=name):
                path = self.campaign / name
                raw = path.read_bytes()
                path.unlink()
                output = self.here / 'missing-method-output.json'
                with self.assertRaisesRegex(ValueError, 'Required runtime/method source'):
                    prospective.prepare('smoke', 'dev-future', 'fixture', 31973, output)
                self.assertFalse(output.exists())
                path.write_bytes(raw)

    def test_preparer_and_test_sources_are_required(self):
        for name in ('prepare_model.py', 'prepare_model_v2.py', 'test_prepare_model_v2.py', 'prepare_model_v3.py', 'test_prepare_model_v3.py', 'prepare_model_v4.py', 'test_prepare_model_v4.py', 'prepare_model_v5.py', 'test_prepare_model_v5.py', 'prepare_model_v6.py', 'test_prepare_model_v6.py', 'prepare_model_v7.py', 'test_prepare_model_v7.py', 'prepare_model_v8.py', 'test_prepare_model_v8.py', 'prepare_model_v9.py', 'test_prepare_model_v9.py', 'prepare_model_v10.py', 'test_prepare_model_v10.py', 'prepare_model_v11.py', 'test_prepare_model_v11.py'):
            with self.subTest(name=name):
                path = self.here / name
                raw = path.read_bytes()
                path.unlink()
                output = self.here / 'missing-source-output.json'
                with self.assertRaisesRegex(ValueError, 'Required runtime/method source'):
                    prospective.prepare('home', 'dev-future', 'fixture', 31973, output)
                self.assertFalse(output.exists())
                path.write_bytes(raw)

    def test_empty_existing_source_group_is_rejected(self):
        path = self.rci / 'readiness-session-10/assessment/assess_bootstrap.py'
        path.unlink()
        output = self.here / 'missing-original-group.json'
        with self.assertRaisesRegex(ValueError, 'source directory absent or empty'):
            prospective.prepare('stock', 'dev-future', 'fixture', 31973, output)
        self.assertFalse(output.exists())

    def test_exclusive_output_preserves_preexisting_bytes(self):
        output = self.here / 'existing.json'
        original_bytes = b'Existing immutable attempt manifest\r\n'
        output.write_bytes(original_bytes)
        with self.assertRaises(FileExistsError):
            prospective.prepare('smoke', 'dev-future', 'fixture', 31973, output)
        self.assertEqual(output.read_bytes(), original_bytes)

    def test_missing_native_evidence_and_schema_are_rejected(self):
        for path in (self.campaign / prospective.SOURCE_EVIDENCE / 'native.rs', self.rci / prospective.RAW_SCHEMA,
                     self.campaign / prospective.CHANNEL_EVIDENCE / 'native.rs',
                     self.campaign / prospective.CHANNEL_EVIDENCE / 'source-evidence.json'):
            with self.subTest(path=path):
                raw = path.read_bytes()
                path.unlink()
                output = self.here / 'missing-evidence-output.json'
                with self.assertRaises(ValueError):
                    prospective.prepare('home', 'dev-future', 'fixture', 31973, output)
                self.assertFalse(output.exists())
                path.write_bytes(raw)

    def test_invalid_kind_creates_no_file(self):
        output = self.here / 'invalid.json'
        with self.assertRaisesRegex(ValueError, 'Unknown model qualification kind'):
            prospective.prepare('other', 'dev-future', 'fixture', 31973, output)
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
