"""Synthetic map tests only: never launch/score a model or grant real admission."""
import argparse
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('campaign_registration_tested', Path(__file__).with_name('register.py'))
reg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reg)


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='campaign001-registration-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'map'
        self.root.mkdir()
        for name in reg.am.KINDS.values():
            (self.root / name).write_bytes(b'')
        stamp = reg.now()
        architecture = {**reg.common('RCI001', stamp), 'title': 'Synthetic only', 'summary': 'Test map'}
        self.add_record('architecture', architecture)
        original = self.root / 'releases' / reg.SOURCE
        original.mkdir(parents=True)
        reg.write_new(original / 'snapshot.json', {'revision': reg.SOURCE, 'sources': {}})
        (original / 'code.zip').write_bytes(b'synthetic archive; qualification verifier mocked in tests only')
        revision = {**reg.common(reg.SOURCE, stamp), 'architecture_id': 'RCI001', 'parent_revision_id': None,
            'status': 'implemented', 'title': 'Synthetic original', 'summary': 'Synthetic original',
            'mechanism': 'Synthetic unchanged mechanism',
            'attachments': [reg.reference(self.root, 'Synthetic source', original / 'snapshot.json'),
                            reg.reference(self.root, 'Synthetic code', original / 'code.zip')]}
        self.add_record('revision', revision)
        schedule_path = reg.CAMPAIGN / 'predeclared-v1/schedule.json'
        self.schedule = reg.read(schedule_path)
        protocol = self.base / 'protocol.md'
        protocol.write_text('Synthetic protocol\n', encoding='utf-8')
        attempts = []
        for slot in self.schedule['slots']:
            attempts.append({'run_id': slot['run_id'], 'ordinal': slot['ordinal'],
                'manifest': reg.identity(schedule_path.parent / slot['manifest']),
                'workspace': slot['runtime_workspace'], 'evidence': str(self.base / ('evidence-' + slot['run_id'])),
                'host_evidence': str(self.base / ('host-' + slot['run_id'])),
                'storage_receipt': str(self.base / ('storage-' + slot['run_id'] + '.json'))})
        self.cert = {'artifacts': {'protocol': reg.identity(protocol), 'schedule': reg.identity(schedule_path),
                    'snapshot': reg.identity(original / 'snapshot.json'), 'archive': reg.identity(original / 'code.zip')},
                    'attempts': attempts}
        self.cert_path = self.base / 'synthetic-certificate.json'
        reg.write_new(self.cert_path, self.cert)
        self.cert_hash = reg.sha(self.cert_path)
        self.mock = patch.object(reg, 'certificate', return_value=(self.cert, self.schedule))
        self.mock.start()
        self.addCleanup(self.mock.stop)
        self.args = argparse.Namespace(map_root=self.root, expected_sha256=self.store_hash(),
            certificate=self.cert_path, certificate_sha256=self.cert_hash, output=self.base / 'preview')

    def store_hash(self):
        return reg.am.store_digest(reg.am.read_store(self.root)[1])

    def add_record(self, kind, record):
        reg.am.append_record(self.root, kind, record, self.store_hash())

    def prepare(self):
        return reg.prepare(self.args)

    def append(self, preview):
        args = argparse.Namespace(map_root=self.root, expected_sha256=self.store_hash(),
            preview=Path(preview['preview']), preview_sha256=preview['preview_sha256'])
        with redirect_stdout(io.StringIO()):
            return reg.append(args)

    def finish_args(self, state='succeeded', exit_status=0, outcome='failure', validity='valid'):
        rid = self.schedule['slots'][0]['run_id']
        receipt = self.base / 'queue.json'
        reg.write_new(receipt, {'id': 'synthetic-queue', 'state': state, 'exit_status': exit_status,
                               'ended_at': reg.now()})
        assessment = self.base / 'assessment.json'
        reg.write_new(assessment, {'schema': 'robot-codex-campaign-admitted-assessment-1',
            'run_id': rid, 'queue_job_id': 'synthetic-queue',
            'bindings': {'manifest_sha256': self.schedule['slots'][0]['sha256'],
                         'queue_receipt_sha256': reg.sha(receipt)},
            'scientific_admission': {'certificate_sha256': self.cert_hash, 'registered_release_revision': reg.REVISION,
                'registration_sha256': reg.sha(self.root / 'releases' / reg.REVISION / 'registration.json')},
            'validity': validity, 'task_outcome': outcome, 'scorable': validity == 'valid', 'failed_checks': []})
        return argparse.Namespace(map_root=self.root, expected_sha256=self.store_hash(), run_id=rid,
            queue_receipt=receipt, assessment=assessment, execution_status='completed', reason='Synthetic check',
            termination='Synthetic terminal')

    def test_preview_does_not_mutate_map_and_preserves_manifest_labels(self):
        before = {p.name: p.read_bytes() for p in self.root.glob('*.jsonl')}
        preview = self.prepare()
        self.assertTrue(preview['map_unchanged'])
        self.assertFalse((self.root / 'releases' / reg.REVISION).exists())
        for name, raw in before.items():
            self.assertEqual((self.root / name).read_bytes(), raw)
        for slot in self.schedule['slots']:
            copied = self.args.output / 'payload/manifests' / (slot['run_id'] + '.json')
            self.assertEqual(reg.sha(copied), slot['sha256'])
            self.assertEqual(reg.read(copied)['stage'], 'development-only')

    def test_append_and_resume_preserve_prefix_and_full_fixed_allocation(self):
        before = {p.name: p.read_bytes() for p in self.root.glob('*.jsonl')}
        preview = self.prepare()
        result = self.append(preview)
        self.assertEqual(result['appended'], 25)
        data, _, errors = reg.am.read_store(self.root)
        self.assertFalse(errors + reg.am.validate_records(data, self.root))
        self.assertEqual([r['id'] for r in data['run']], [s['run_id'] for s in self.schedule['slots']])
        self.assertTrue(all(r['stage'] == 'evaluation' for r in data['run']))
        self.assertEqual(data['revision'][-1]['status'], 'frozen')
        self.assertEqual(data['revision'][-1]['parent_revision_id'], reg.SOURCE)
        for name, raw in before.items():
            self.assertTrue((self.root / name).read_bytes().startswith(raw))
        binding = reg.read(result['registration'])
        self.assertEqual(reg.read(reg.verify_identity(binding['release_snapshot']))['revision'], reg.SOURCE)
        self.assertEqual(self.append(preview)['appended'], 0)

    def test_stale_store_rejected_before_preview_write(self):
        self.args.expected_sha256 = '0' * 64
        with self.assertRaisesRegex(ValueError, 'store changed'):
            self.prepare()
        self.assertFalse(self.args.output.exists())

    def test_preview_asset_tamper_rejected_before_map_write(self):
        preview = self.prepare()
        (self.args.output / 'payload/protocol.md').write_text('changed', encoding='utf-8')
        before = self.store_hash()
        with self.assertRaisesRegex(ValueError, 'preview asset changed'):
            self.append(preview)
        self.assertEqual(before, self.store_hash())
        self.assertFalse((self.root / 'releases' / reg.REVISION).exists())

    def test_task_failure_is_valid_after_authenticated_queue(self):
        self.append(self.prepare())
        args = self.finish_args()
        with redirect_stdout(io.StringIO()):
            result = reg.finish(args)
        self.assertEqual((result['validity'], result['outcome']), ('valid', 'failure'))

    def test_failed_queue_does_not_open_assessment_and_records_unknown(self):
        self.append(self.prepare())
        args = self.finish_args(state='failed', exit_status=1)
        args.assessment = self.base / 'nonexistent-outcome-never-opened.json'
        with self.assertRaisesRegex(ValueError, 'Do not read outcomes'):
            reg.finish(args)
        args.assessment = None
        args.execution_status = 'failed'
        with redirect_stdout(io.StringIO()):
            result = reg.finish(args)
        self.assertEqual((result['validity'], result['outcome']), ('invalid', 'unknown'))

    def test_boolean_false_is_not_integer_exit_zero(self):
        self.append(self.prepare())
        args = self.finish_args(exit_status=False)
        with self.assertRaisesRegex(ValueError, 'Do not read outcomes'):
            reg.finish(args)

    def test_not_run_preserves_unknown_and_no_invented_measurements(self):
        self.append(self.prepare())
        args = self.finish_args()
        args.queue_receipt = args.assessment = None
        args.execution_status = 'not_run'
        with redirect_stdout(io.StringIO()):
            reg.finish(args)
        result = reg.am.read_store(self.root)[0]['result'][0]
        self.assertEqual((result['validity'], result['outcome']), ('unknown', 'not_assessed'))
        self.assertIsNone(result['ended_at'])
        self.assertEqual(result['metrics'], [])


if __name__ == '__main__':
    unittest.main()
