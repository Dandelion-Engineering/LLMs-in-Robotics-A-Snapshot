"""Guard immutable source provenance and failed-attempt evidence in a temp map."""
import argparse
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('readiness_registration', Path(__file__).with_name('register.py'))
reg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reg)


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='robot-codex-registration-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'map'
        self.root.mkdir()
        for filename in reg.am.KINDS.values():
            (self.root / filename).write_text('', encoding='utf-8')
        architecture = {**reg.common(reg.ARCHITECTURE), 'title': 'Synthetic', 'summary': 'Synthetic registry test'}
        _, raw, _ = reg.am.read_store(self.root)
        reg.am.append_record(self.root, 'architecture', architecture, reg.am.store_digest(raw))
        self.source = self.base / 'loaded.py'
        self.source.write_bytes(b'print("loaded snapshot")\n')
        self.manifest = self.base / 'manifest.json'
        self.manifest.write_text(json.dumps({'run_id': 'run-one', 'stage': 'development-only',
                                            'qualification_stage': 'A', 'limits': {'seconds': 30}}), encoding='utf-8')
        self.args = argparse.Namespace(map_root=self.root, revision='revision-one', run_id='run-one',
            manifest=self.manifest, mechanism=None, expected_sha256=None)

    def prepare(self):
        with patch.object(reg, 'capture_sources', return_value={'loaded.py': self.source.read_bytes()}), redirect_stdout(io.StringIO()):
            return reg.prepare(self.args)

    def finish_args(self, queue_state, exit_status):
        result = self.base / 'attempt-result.json'
        result.write_text(json.dumps({'run_id': 'run-one', 'terminal': 'intentional test'}), encoding='utf-8')
        queue = self.base / 'queue.json'
        queue.write_text(json.dumps({'job': {'id': 'test-job', 'state': queue_state, 'exit_status': exit_status}}), encoding='utf-8')
        return argparse.Namespace(map_root=self.root, run_id='run-one', result=result, queue_receipt=queue,
            execution_status='failed', validity='invalid', outcome='unknown', reason='Synthetic transport failure',
            termination='Bounded fixture ended', evidence=[], expected_sha256=None)

    def test_snapshot_exact_bytes_and_original_prefix_preserved(self):
        before = {p.name: p.read_bytes() for p in self.root.glob('*.jsonl')}
        outcome = self.prepare()
        snapshot = reg.read_json(outcome['snapshot'])
        self.assertEqual(snapshot['sources']['loaded.py']['sha256'], reg.digest(self.source.read_bytes()))
        with zipfile.ZipFile(Path(outcome['snapshot']).with_name('code.zip')) as archive:
            self.assertEqual(archive.read('loaded.py'), self.source.read_bytes())
        for name, raw in before.items():
            self.assertTrue((self.root / name).read_bytes().startswith(raw))
        with self.assertRaises(ValueError):
            self.prepare()

    def test_stale_store_rejected_without_revision_directory(self):
        self.args.expected_sha256 = '0' * 64
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse((self.root / 'releases').exists())

    def test_source_changes_fail_verification(self):
        outcome = self.prepare()
        with patch.object(reg, 'REPO', self.base):
            self.assertTrue(reg.verify(argparse.Namespace(snapshot=Path(outcome['snapshot'])))['verified'])
            self.source.write_bytes(b'changed after registration\n')
            with self.assertRaises(ValueError):
                reg.verify(argparse.Namespace(snapshot=Path(outcome['snapshot'])))

    def test_failed_queue_preserved_only_as_invalid_unassessed_diagnostic(self):
        self.prepare()
        args = self.finish_args('failed', 1)
        args.outcome, args.validity = 'success', 'valid'
        with self.assertRaises(ValueError):
            reg.finish(args)
        self.assertFalse((self.root / 'releases/revision-one/result-run-one').exists())
        args.outcome, args.validity = 'unknown', 'invalid'
        with redirect_stdout(io.StringIO()):
            reg.finish(args)
        data, _, errors = reg.am.read_store(self.root)
        self.assertFalse(errors)
        self.assertEqual(data['result'][0]['outcome'], 'unknown')
        self.assertFalse(data['result'][0]['details']['queue_success_verified'])
        self.assertEqual((self.root / 'releases/revision-one/result-run-one/queue.json').read_bytes(), args.queue_receipt.read_bytes())

    def test_successful_queue_does_not_force_task_success(self):
        self.prepare()
        args = self.finish_args('succeeded', 0)
        args.execution_status, args.validity, args.outcome = 'completed', 'valid', 'failure'
        with redirect_stdout(io.StringIO()):
            reg.finish(args)
        data, _, _ = reg.am.read_store(self.root)
        self.assertEqual(data['result'][0]['outcome'], 'failure')
        self.assertTrue(data['result'][0]['details']['queue_success_verified'])


if __name__ == '__main__':
    unittest.main()
