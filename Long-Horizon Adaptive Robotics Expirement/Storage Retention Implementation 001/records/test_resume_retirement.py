"""Continuation safeguards tested only inside newly created temporary roots.

Official queue I/O is stubbed; the real manifest, safe_frame, metadata checks,
write-ahead records, unlinks and completion accounting run on fixture files.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name('resume_retirement.py')
LOCK = '2026-09-26T17:44:17.7987520-07:00'


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        spec = importlib.util.spec_from_file_location('fixture_resumer', SOURCE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.r = self.m.r
        self.here = self.root / 'experiment/implementation'
        self.records = self.here / 'records'
        self.records.mkdir(parents=True)
        copied_source = self.records / SOURCE.name
        copied_source.write_bytes(SOURCE.read_bytes())
        (self.here / 'retention.py').write_bytes(Path(self.r.__file__).read_bytes())
        self.m.HERE = self.here
        self.m.__file__ = str(copied_source)
        self.r.ROOT = self.root
        self.r.EXP = self.root / 'experiment'
        self.r.HERE = self.here
        self.r.R4 = self.r.EXP / 'Evidence/releases/batch01-eval-r4'
        self.r.ATTEMPTS = self.r.R4 / 'attempts'
        self.r.checked_directory.cache_clear()
        (self.root / '.codex-session.lock').write_text(LOCK)
        self.old_path = list(sys.path)
        self.queue_stub = patch.object(self.m, 'authenticated_job', side_effect=self.fixture_job)
        self.queue_stub.start()
        self.runner_stub = patch.dict(sys.modules, {'recovery_runner': types.SimpleNamespace(
            queued_job=lambda **kwargs: {'id': 'fixture-continuation-job'})})
        self.runner_stub.start()

    def tearDown(self):
        self.runner_stub.stop()
        self.queue_stub.stop()
        self.r.checked_directory.cache_clear()
        sys.path[:] = self.old_path
        self.temp.cleanup()

    def fixture_job(self, path, fragment, state='succeeded'):
        value = self.r.read(path)
        if value['state'] != state or (state == 'succeeded' and value['exit_status'] != 0):
            raise ValueError('Fixture queue state failed')
        return value

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')

    def fixture(self, remaining=3):
        frames = self.r.ATTEMPTS / 'fixture-run/evidence/frames'
        frames.mkdir(parents=True)
        self.first = 3
        self.rows = []
        for ordinal in range(self.first + remaining):
            path = frames / f'{ordinal:06d}.png'
            payload = f'fixture-frame-{ordinal:06d}'.encode()
            if ordinal >= self.first:
                path.write_bytes(payload)
                mtime = path.stat().st_mtime_ns
            else:
                mtime = 123456
            self.rows.append({'path': path.relative_to(self.root).as_posix(),
                              'logical_bytes': len(payload), 'mtime_ns': mtime})
        manifest = self.here / 'manifests/deletion.jsonl.gz'
        writer = self.r.Writer(manifest)
        for row in self.rows:
            writer.put(row)
        writer.close()
        ref = {'path': manifest.relative_to(self.root).as_posix(), 'sha256': self.r.sha(manifest),
               'files': len(self.rows), 'logical_bytes': sum(row['logical_bytes'] for row in self.rows)}
        self.part_path = self.records / 'r4-policy-001-partition.json'
        self.write(self.part_path, {'manifests': {'deletion': ref}})
        self.proof_path = self.records / 'reconciliation.json'
        totals = lambda rows: {'files': len(rows), 'logical_bytes': sum(x['logical_bytes'] for x in rows)}
        self.proof = {'status': 'passed', 'queue_job_id': 'fixture-reconciliation-job',
                      'partition_sha256': self.r.sha(self.part_path), 'deletion_manifest_sha256': ref['sha256'],
                      'all_retained_hashes_verified': True, 'protected_nonframe_metadata_checked': 3323,
                      'original_retirement_job_id': 'fixture-original-job', 'first_remaining_ordinal': self.first,
                      'completed_prefix': totals(self.rows[:2]), 'interrupted_intent_absences': totals(self.rows[2:3]),
                      'remaining': totals(self.rows[3:])}
        self.write(self.proof_path, self.proof)
        receipt = self.records / 'reconciliation-receipt.json'
        self.write(receipt, {'id': 'fixture-reconciliation-job', 'state': 'succeeded', 'exit_status': 0})
        self.old_receipt = self.records / 'queue-20260927T021811180808Z-32339c6c-interrupted.json'
        self.write(self.old_receipt, {'id': 'fixture-original-job', 'state': 'interrupted', 'exit_status': None})
        earlier = self.records / 'earlier-check.json'
        self.write(earlier, {'status': 'passed'})
        self.old_gate = self.records / 'pre-deletion-completion-001.json'
        self.write(self.old_gate, {'status': 'passed', 'created': 'fixture-pre-interruption',
            'partition_sha256': self.r.sha(self.part_path), 'deletion_manifest_sha256': ref['sha256'],
            'checks': dict.fromkeys(self.r.GATES, True),
            'evidence_refs': [{'path': earlier.relative_to(self.root).as_posix(), 'sha256': self.r.sha(earlier)}]})
        self.old_intent = self.records / 'r4-policy-001-deletion-receipts/00446-intent.json'
        self.write(self.old_intent, {'status': 'original intent must remain immutable', 'first_ordinal': 2})
        self.old_bytes = {str(p): p.read_bytes() for p in (self.old_intent, self.old_receipt, self.old_gate)}
        self.write(self.records / 'preflight-001/summary.json', {'disk_before': self.r.shutil.disk_usage(self.root.anchor)._asdict()})
        writer_check = self.records / 'writer-check.json'
        self.write(writer_check, {'status': 'passed', 'affected_original_writers_observed': 0})
        self.args = argparse.Namespace(reconciliation=str(self.proof_path), reconciliation_receipt=str(receipt),
                                      gate=str(self.records / 'continuation-gate.json'), writer_check=str(writer_check))
        with contextlib.redirect_stdout(io.StringIO()):
            self.m.prepare(self.args)

    def execute(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.m.execute(self.args)

    def existing_remainder(self):
        return [self.root / row['path'] for row in self.rows[self.first:]]

    def test_global_ordinals_multibatch_totals_and_original_records_preserved(self):
        self.fixture(remaining=2001)
        self.execute()
        out = self.records / 'r4-policy-001-continuation-001-receipts'
        first = self.r.read(out / '00000-complete.json')
        second = self.r.read(out / '00001-complete.json')
        self.assertEqual((first['first_ordinal'], first['count']), (3, 2000))
        self.assertEqual((second['first_ordinal'], second['count']), (2003, 1))
        self.assertEqual(first['logical_bytes'] + second['logical_bytes'], self.proof['remaining']['logical_bytes'])
        expected_paths = [row['path'] for row in self.rows[3:2003]]
        self.assertEqual(first['removed_paths_sha256'], hashlib.sha256(('\n'.join(expected_paths)+'\n').encode()).hexdigest())
        complete = self.r.read(self.records / 'r4-policy-001-deletion-complete.json')
        self.assertEqual(complete['files'], len(self.rows))
        self.assertEqual(complete['continuation']['files'], 2001)
        self.assertEqual(complete['continuation']['first_ordinal'], 3)
        self.assertEqual(complete['observed_absent_within_interrupted_intent'], self.proof['interrupted_intent_absences'])
        self.assertFalse(any(path.exists() for path in self.existing_remainder()))
        for path, before in self.old_bytes.items():
            self.assertEqual(Path(path).read_bytes(), before)

    def test_metadata_failure_records_only_actual_unlinks_and_refuses_blind_rerun(self):
        self.fixture()
        paths = self.existing_remainder()
        paths[1].write_bytes(b'changed frame payload')
        with self.assertRaises(ValueError): self.execute()
        out = self.records / 'r4-policy-001-continuation-001-receipts'
        failed = self.r.read(out / '00000-failure.json')
        self.assertEqual(failed['removed'], [self.rows[3]['path']])
        self.assertEqual(self.r.read(out / '00000-intent.json')['first_ordinal'], 3)
        self.assertFalse(paths[0].exists())
        self.assertTrue(paths[1].exists()); self.assertTrue(paths[2].exists())
        self.assertFalse((self.records / 'r4-policy-001-deletion-complete.json').exists())
        with self.assertRaises(FileExistsError): self.execute()
        self.assertTrue(paths[1].exists()); self.assertTrue(paths[2].exists())

    def test_execute_refuses_changed_session_owner_before_any_unlink(self):
        self.fixture()
        (self.root / '.codex-session.lock').write_text('different session')
        with self.assertRaises(ValueError): self.execute()
        self.assertTrue(all(path.exists() for path in self.existing_remainder()))

    def test_execute_refuses_changed_imported_retention_source(self):
        self.fixture()
        with (self.here / 'retention.py').open('ab') as f: f.write(b'\n# modified fixture\n')
        with self.assertRaises(ValueError): self.execute()
        self.assertTrue(all(path.exists() for path in self.existing_remainder()))

    def test_reconciliation_totals_or_prefix_mismatch_refused_before_unlink(self):
        self.fixture()
        self.proof['remaining']['logical_bytes'] += 1
        self.write(self.proof_path, self.proof)
        with self.assertRaises(ValueError): self.execute()
        self.assertTrue(all(path.exists() for path in self.existing_remainder()))

    def test_original_failed_gate_refused_before_unlink(self):
        self.fixture()
        old = self.r.read(self.old_gate); old['status'] = 'failed'; self.write(self.old_gate, old)
        with self.assertRaises(ValueError): self.execute()
        self.assertTrue(all(path.exists() for path in self.existing_remainder()))

    def test_strict_frame_path_guard_reused_for_remaining_leaf(self):
        self.fixture()
        paths = self.existing_remainder()
        # A directory at an exact approved leaf cannot be unlinked as an image.
        self.assertTrue(paths[0].is_relative_to(self.root)); paths[0].unlink(); paths[0].mkdir()
        with self.assertRaises(ValueError): self.execute()
        self.assertTrue(paths[0].is_dir())
        self.assertTrue(paths[1].exists()); self.assertTrue(paths[2].exists())
        failed = self.r.read(self.records / 'r4-policy-001-continuation-001-receipts/00000-failure.json')
        self.assertEqual(failed['removed'], [])


if __name__ == '__main__':
    unittest.main()
