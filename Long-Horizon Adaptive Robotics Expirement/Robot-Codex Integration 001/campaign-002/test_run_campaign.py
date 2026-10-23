"""Mock coordinator resumption and refusal tests; no queue or model execution."""
import copy
from contextlib import nullcontext, redirect_stdout
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_campaign as c


class FakeClock:
    def __init__(self):
        self.wall = 1_800_000_000.
        self.elapsed = 10.
        self.sleeps = []
        self.on_sleep = None

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.wall += seconds
        self.elapsed += seconds
        if self.on_sleep:
            self.on_sleep()


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registration = self.root / 'registration.json'
        self.certificate = self.root / 'sealed/certificate.json'
        self.clock = FakeClock()
        self.started, self.collected, self.settled, self.calls = [], [], [], []
        self.jobs = {}
        self.stop_after = 20
        self.make_storage = True
        self.attempts = []
        for ordinal in range(1, 21):
            pair = (ordinal - 1) // 2
            family = ('misplaced-stock', 'blocked-insert-home')[(ordinal - 1) % 2 ^ (pair % 2)]
            suffix = 'stock' if family == 'misplaced-stock' else 'home'
            run_id = f'RCI001-C02-{suffix}-{pair + 1:02d}'
            self.attempts.append({'ordinal': ordinal, 'run_id': run_id, 'family': family,
                'manifest': {'path': str(self.root / 'manifests' / (run_id + '.json')), 'sha256': f'{ordinal:064x}'},
                **{name: str(self.root / name / run_id) for name in ('workspace', 'evidence', 'host_evidence')}})
        self.cert = {'schema': 'campaign002-admission-1', 'campaign_id': 'RCI001-Campaign002',
            'release_revision': 'RCI001-C02-frozen-001', 'attempts': self.attempts,
            'artifacts': {'campaign_coordinator': {'path': c.__file__, 'sha256': c.operate.sha(c.__file__)}}}
        self.seal()
        self.patch(c, 'HERE', self.root)
        self.patch(c.operate, 'HERE', self.root)
        self.patch(c.settle, 'HERE', self.root)
        self.patch(c.operate, 'CERT', self.certificate)
        self.patch(c.operate, 'REGISTRATION', self.registration)
        self.patch(c, 'coordinator_lock', side_effect=lambda: nullcontext())
        self.start_mock = self.patch(c.operate, 'start', side_effect=self.fake_start)
        self.collect_mock = self.patch(c.operate, 'collect', side_effect=self.fake_collect)
        self.settle_mock = self.patch(c.settle, 'settle', side_effect=self.fake_settle)
        self.queue_mock = self.patch(c.operate, 'queue', side_effect=self.fake_queue)
        self.patch(c.time, 'time', side_effect=lambda: self.clock.wall)
        self.patch(c.time, 'monotonic', side_effect=lambda: self.clock.elapsed)
        self.patch(c.time, 'sleep', side_effect=self.clock.sleep)

    def patch(self, obj, name, *args, **kwargs):
        value = patch.object(obj, name, *args, **kwargs)
        self.addCleanup(value.stop)
        return value.start()

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')

    def seal(self):
        self.write(self.certificate, self.cert)
        self.digest = c.operate.sha(self.certificate)
        self.write(self.certificate.with_name('seal.json'), {'certificate_sha256': self.digest})
        self.write(self.registration, {'schema': 'campaign002-registration-1',
            'certificate_sha256': self.digest, 'release_revision': self.cert['release_revision'],
            'attempts': [{'run_id': row['run_id'], 'manifest_sha256': row['manifest']['sha256']} for row in self.attempts]})

    def folder(self, index=0):
        return self.root / 'execution' / self.attempts[index]['run_id']

    def create_submission(self, index=0, storage=True):
        attempt = self.attempts[index]
        folder = self.folder(index)
        argv = [str(c.operate.PYTHON), '-X', 'utf8', '-B', str(self.root / 'harness/physical.py'),
                '--manifest', attempt['manifest']['path'], '--evidence', attempt['evidence'],
                '--host-evidence', attempt['host_evidence'], '--workspace', attempt['workspace'], '--mode', 'pilot']
        self.write(folder / 'launch-intent.json', {'run_id': attempt['run_id'], 'ordinal': attempt['ordinal'],
            'argv': argv, 'certificate_sha256': self.digest, 'registration_sha256': c.operate.sha(self.registration)})
        job = {'id': f'job-{index + 1}', 'state': 'succeeded', 'exit_status': 0,
               'ended_at': datetime.fromtimestamp(self.clock.wall, timezone.utc).isoformat()}
        self.write(folder / 'queue-submit.json', job)
        self.jobs[job['id']] = [job]
        if storage:
            self.storage(index)
        return job

    def storage(self, index=0):
        self.write(self.folder(index) / 'storage/receipt.json', {'synthetic': True})
        self.write(self.folder(index) / 'storage/queue-receipt.json', self.jobs[f'job-{index + 1}'][-1])

    def fake_start(self, args):
        self.started.append(args.run_id)
        self.calls.append(('start', args.run_id))
        index = next(i for i, row in enumerate(self.attempts) if row['run_id'] == args.run_id)
        self.assertFalse(self.folder(index).exists())
        self.create_submission(index, self.make_storage)

    def fake_queue(self, action, job_id):
        self.assertEqual(action, 'status')
        self.calls.append(('queue', job_id))
        values = self.jobs[job_id]
        return copy.deepcopy(values.pop(0) if len(values) > 1 else values[0])

    def fake_collect(self, args):
        self.collected.append(args.run_id)
        self.calls.append(('collect', args.run_id))
        path = self.root / 'execution' / args.run_id / 'assessment.json'
        if not path.exists():
            self.write(path, {'synthetic': True})

    def fake_settle(self, run_id):
        self.settled.append(run_id)
        self.calls.append(('settle', run_id))
        row = next(row for row in self.attempts if row['run_id'] == run_id)
        folder = self.root / 'execution' / run_id
        stopped = (folder / 'diagnostic.json').exists() or row['ordinal'] >= self.stop_after
        c.operate.save_exact(folder / 'disposition.json', {key: row[key] for key in ('ordinal', 'run_id', 'family')}
                            | {'allow_next': not stopped})
        if stopped:
            c.operate.save_exact(self.root / 'execution/campaign-stop.json', {
                'schema': 'campaign002-stop-1', 'planned': 20, 'stop_after_ordinal': row['ordinal'],
                'remaining_admission_authorized': False, 'reason': 'synthetic terminal stop'})

    def run_coordinator(self):
        with redirect_stdout(io.StringIO()):
            return c.run(self.registration)

    def test_all_twenty_exact_slots_use_existing_operator_once(self):
        result = self.run_coordinator()
        expected = [row['run_id'] for row in self.attempts]
        self.assertEqual(self.started, expected)
        self.assertEqual(self.collected, expected)
        self.assertEqual(self.settled, expected)
        self.assertEqual(result['stop_after_ordinal'], 20)
        self.assertEqual(self.clock.sleeps, [])

    def test_resume_existing_submission_never_resubmits(self):
        self.create_submission()
        self.stop_after = 1
        self.run_coordinator()
        self.start_mock.assert_not_called()
        self.assertEqual(self.collected, [self.attempts[0]['run_id']])

    def test_existing_disposition_is_reconciled_before_next_launch(self):
        self.create_submission()
        self.fake_collect(type('Args', (), {'run_id': self.attempts[0]['run_id']})())
        self.fake_settle(self.attempts[0]['run_id'])
        self.calls.clear()
        self.stop_after = 2
        self.run_coordinator()
        first, second = (row['run_id'] for row in self.attempts[:2])
        self.assertEqual(self.started, [second])
        self.assertLess(self.calls.index(('settle', first)), self.calls.index(('start', second)))

    def test_existing_stop_is_reconciled_and_no_future_slot_launches(self):
        self.create_submission()
        self.stop_after = 1
        self.run_coordinator()
        self.run_coordinator()
        self.start_mock.assert_not_called()
        self.assertEqual(self.settled, [self.attempts[0]['run_id']] * 2)

    def test_intent_without_committed_queue_receipt_requires_reconciliation(self):
        self.create_submission()
        (self.folder() / 'queue-submit.json').unlink()
        with self.assertRaisesRegex(ValueError, 'unsubmitted intent'):
            self.run_coordinator()
        self.start_mock.assert_not_called()
        self.queue_mock.assert_not_called()
        self.collect_mock.assert_not_called()

    def test_pending_submission_is_never_automatically_promoted_or_resubmitted(self):
        self.create_submission()
        path = self.folder() / 'queue-submit.json'
        path.rename(path.with_name('queue-submit.json.pending'))
        with self.assertRaisesRegex(ValueError, 'unsubmitted intent'):
            self.run_coordinator()
        self.start_mock.assert_not_called()

    def test_existing_output_without_execution_intent_prevents_launch(self):
        Path(self.attempts[0]['evidence']).mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'runtime output prevents resubmission'):
            self.run_coordinator()
        self.start_mock.assert_not_called()

    def test_later_slot_footprint_beyond_gap_prevents_launch(self):
        self.create_submission(1)
        with self.assertRaisesRegex(ValueError, 'beyond an unfinished gap'):
            self.run_coordinator()
        self.start_mock.assert_not_called()

    def test_changed_manifest_or_path_in_retained_intent_is_rejected(self):
        self.create_submission()
        path = self.folder() / 'launch-intent.json'
        intent = c.operate.read(path)
        intent['argv'][-1] = 'smoke'
        self.write(path, intent)
        with self.assertRaisesRegex(ValueError, 'launch intent conflicts'):
            self.run_coordinator()
        self.queue_mock.assert_not_called()

    def test_polling_is_modest_and_no_outcome_collected_while_active(self):
        final = self.create_submission()
        self.jobs['job-1'] = [{**final, 'state': state, 'exit_status': None} for state in ('queued', 'running')] + [final]
        self.stop_after = 1
        self.run_coordinator()
        self.assertEqual(self.clock.sleeps, [15., 15.])
        self.assertEqual([kind for kind, _ in self.calls[:4]], ['queue', 'queue', 'queue', 'collect'])

    def test_wrong_official_job_identity_halts_without_collection(self):
        final = self.create_submission()
        self.jobs['job-1'] = [{**final, 'id': 'different'}]
        with self.assertRaisesRegex(ValueError, 'queue identity differs'):
            self.run_coordinator()
        self.collect_mock.assert_not_called()
        self.settle_mock.assert_not_called()

    def test_unknown_queue_state_halts_without_collection(self):
        final = self.create_submission()
        self.jobs['job-1'] = [{**final, 'state': 'unrecognized'}]
        with self.assertRaisesRegex(ValueError, 'Unrecognized official queue state'):
            self.run_coordinator()
        self.collect_mock.assert_not_called()

    def test_nonzero_or_boolean_exit_only_creates_unknown_stop_diagnostic(self):
        for state, code in (('failed', 1), ('succeeded', False), ('succeeded', 1)):
            with self.subTest(state=state, code=code):
                # Each case uses a separate attempt folder under a fresh fixture.
                final = self.create_submission()
                self.jobs['job-1'] = [{**final, 'state': state, 'exit_status': code}]
                (self.folder() / 'assessment.json').write_text('POISON: do not read as an outcome')
                self.run_coordinator()
                diagnostic = c.operate.read(self.folder() / 'diagnostic.json')
                self.assertTrue(diagnostic['immediate_stop'])
                self.assertEqual(diagnostic['task_outcome'], 'unknown')
                self.assertFalse(diagnostic['scorable'])
                self.collect_mock.assert_not_called()
                # Remove only synthetic committed records so the next subcase
                # can authenticate a different terminal job in this fixture.
                for name in ('official-status.json', 'diagnostic.json', 'disposition.json'):
                    (self.folder() / name).unlink()
                (self.root / 'execution/campaign-stop.json').unlink()

    def test_missing_guard_final_receipt_stops_after_sixty_seconds(self):
        self.create_submission(storage=False)
        self.run_coordinator()
        self.assertEqual(self.clock.sleeps, [15.] * 4)
        value = c.operate.read(self.folder() / 'diagnostic.json')
        self.assertEqual(value['diagnostic_kind'], 'final_storage_receipt_deadline')
        self.assertTrue(value['immediate_stop'])
        self.assertEqual(value['task_outcome'], 'unknown')
        self.collect_mock.assert_not_called()
        self.start_mock.assert_not_called()

    def test_restart_does_not_restart_storage_deadline(self):
        self.create_submission(storage=False)
        self.clock.wall += 61.
        self.run_coordinator()
        self.assertEqual(self.clock.sleeps, [])
        self.collect_mock.assert_not_called()

    def test_late_but_bounded_storage_receipts_allow_collection(self):
        self.create_submission(storage=False)
        self.stop_after = 1
        self.clock.on_sleep = lambda: self.storage()
        self.run_coordinator()
        self.assertEqual(self.clock.sleeps, [15.])
        self.assertEqual(len(self.collected), 1)
        self.assertFalse((self.folder() / 'diagnostic.json').exists())

    def test_storage_receipt_without_its_queue_receipt_cannot_enable_collection(self):
        self.create_submission()
        (self.folder() / 'storage/queue-receipt.json').unlink()
        self.run_coordinator()
        self.assertEqual(sum(self.clock.sleeps), 60.)
        self.collect_mock.assert_not_called()

    def test_collection_exception_never_advances(self):
        self.create_submission()
        self.collect_mock.side_effect = RuntimeError('injected collection failure')
        with self.assertRaisesRegex(RuntimeError, 'injected collection failure'):
            self.run_coordinator()
        self.start_mock.assert_not_called()
        self.settle_mock.assert_not_called()

    def test_collection_without_artifact_never_advances(self):
        self.create_submission()
        self.collect_mock.side_effect = lambda args: None
        with self.assertRaisesRegex(ValueError, 'no terminal assessment or diagnostic'):
            self.run_coordinator()
        self.settle_mock.assert_not_called()

    def test_settlement_exception_never_advances(self):
        self.create_submission()
        self.settle_mock.side_effect = OSError('injected settlement interruption')
        with self.assertRaisesRegex(OSError, 'settlement interruption'):
            self.run_coordinator()
        self.start_mock.assert_not_called()

    def test_start_exception_cannot_trigger_retry_or_next_slot(self):
        def interrupted(args):
            self.create_submission()
            (self.folder() / 'queue-submit.json').unlink()
            raise RuntimeError('submit result unknown')
        self.start_mock.side_effect = interrupted
        with self.assertRaisesRegex(RuntimeError, 'submit result unknown'):
            self.run_coordinator()
        self.assertEqual(self.start_mock.call_count, 1)
        with self.assertRaisesRegex(ValueError, 'unsubmitted intent'):
            self.run_coordinator()
        self.assertEqual(self.start_mock.call_count, 1)

    def test_existing_conflicting_official_receipt_is_not_overwritten(self):
        final = self.create_submission()
        path = self.folder() / 'official-status.json'
        self.write(path, {**final, 'exit_status': 1})
        original = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Conflicting immutable'):
            self.run_coordinator()
        self.assertEqual(path.read_bytes(), original)
        self.collect_mock.assert_not_called()

    def test_changed_coordinator_cannot_be_used_under_an_old_seal(self):
        self.cert['artifacts']['campaign_coordinator']['sha256'] = '0' * 64
        self.seal()
        with self.assertRaisesRegex(ValueError, 'Coordinator source is not bound'):
            self.run_coordinator()
        self.start_mock.assert_not_called()

    def test_allocation_cannot_add_replace_or_reorder_slots(self):
        self.cert['attempts'][0], self.cert['attempts'][1] = self.cert['attempts'][1], self.cert['attempts'][0]
        self.seal()
        with self.assertRaisesRegex(ValueError, 'slot order, identity or family'):
            self.run_coordinator()
        self.start_mock.assert_not_called()

    def test_registration_must_preserve_every_slot(self):
        registration = c.operate.read(self.registration)
        registration['attempts'].pop()
        self.write(self.registration, registration)
        with self.assertRaisesRegex(ValueError, 'preserve all immutable slots'):
            self.run_coordinator()
        self.start_mock.assert_not_called()

    def test_coordinator_and_settler_cannot_use_different_registrations(self):
        with self.assertRaisesRegex(ValueError, 'same registered release'):
            c.run(self.root / 'other-registration.json')
        self.start_mock.assert_not_called()


if __name__ == '__main__':
    unittest.main()
