"""Small orchestration tests: no queue submit, models, native/WSL or simulation."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('final_coordinator_v3', HERE / 'run_final_qualification_v3.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def job(self, state='succeeded', status=0):
        return {'id': c.PROBE_JOB, 'state': state, 'exit_status': status,
                'argv': ['fixed'], 'cwd': str(c.REPO), 'resolved_executable': str(c.PYTHON)}

    def test_probe_failed_queue_precedes_every_outcome_read(self):
        for state, code in [('running', None), ('failed', 1), ('succeeded', False), ('succeeded', '0')]:
            with self.subTest(state=state, code=code), patch.object(c, 'official', return_value=self.job(state, code)), \
                 patch.object(c, 'read') as reader, patch.object(c, 'assert_sources') as sources:
                with self.assertRaisesRegex(ValueError, 'Official queue'):
                    c.preflight(self.root / 'queue', self.root / 'assessment')
                reader.assert_not_called()
                sources.assert_not_called()

    def test_probe_retained_queue_mismatch_stops_before_assessment(self):
        with patch.object(c, 'official', return_value=self.job()), patch.object(c, 'read', return_value={}) as reader, \
             patch.object(c, 'sha', return_value=c.PROBE_QUEUE_SHA), \
             patch.object(c, 'assert_sources') as sources:
            with self.assertRaisesRegex(ValueError, 'retained receipt'):
                c.preflight(c.PROBE_QUEUE, c.PROBE_ASSESSMENT)
            reader.assert_called_once_with(c.PROBE_QUEUE)
            sources.assert_not_called()

    def test_pinned_probe_receipt_cannot_be_replaced(self):
        with patch.object(c, 'official', return_value=self.job()), patch.object(c, 'sha', return_value='changed'), \
             patch.object(c, 'read') as reader, patch.object(c, 'assert_sources') as sources:
            with self.assertRaisesRegex(ValueError, 'official receipt path/hash changed'):
                c.preflight(c.PROBE_QUEUE, c.PROBE_ASSESSMENT)
            reader.assert_not_called()
            sources.assert_not_called()

    def test_pinned_probe_assessment_cannot_be_replaced(self):
        hashes = {c.PROBE_QUEUE: c.PROBE_QUEUE_SHA, c.PROBE_MANIFEST: c.PROBE_MANIFEST_SHA,
                  c.PROBE_ASSESSMENT: 'changed'}
        with patch.object(c, 'official', return_value=self.job()), patch.object(c, 'read', return_value=self.job()) as reader, \
             patch.object(c, 'assert_sources', return_value={}), patch.object(c, 'sha', side_effect=lambda p: hashes[p]):
            with self.assertRaisesRegex(ValueError, 'assessment path/hash changed'):
                c.preflight(c.PROBE_QUEUE, c.PROBE_ASSESSMENT)
            reader.assert_called_once_with(c.PROBE_QUEUE)

    def test_v3_fixed_allocation_preserves_seed_plan_with_fresh_revisions(self):
        self.assertEqual(c.BASE_REVISION, 'RCI001-C02-dev-009')
        self.assertEqual(c.PROBE_JOB, '20260927T230552620519Z-60d9eea8')
        self.assertEqual(c.LEDGER.name, 'final-qualification-003')
        self.assertEqual(c.STAGES, (
            ('native-003', 'native', 'RCI001-C02-dev-013', 24000),
            ('boundary-004', 'boundary', 'RCI001-C02-dev-014', None),
            ('smoke-002', 'smoke', 'RCI001-C02-dev-015', 24101),
            ('pilot-stock-001', 'stock', 'RCI001-C02-dev-015', 24102),
            ('pilot-home-001', 'home', 'RCI001-C02-dev-015', 24103)))

    def test_probe_changed_source_anchor_is_rejected(self):
        with patch.object(c, 'sha', return_value='changed'), patch.object(c, 'read') as reader:
            with self.assertRaisesRegex(ValueError, 'trust anchor'):
                c.assert_sources()
            reader.assert_not_called()

    def test_failed_terminal_queue_retained_without_outcome_read(self):
        job = self.job('failed', 1)
        receipt = self.root / 'queue.json'
        with patch.object(c, 'official', return_value=job), patch.object(c, 'read') as reader:
            with self.assertRaisesRegex(ValueError, 'Official queue'):
                c.await_success(job, receipt, ['fixed'])
            reader.assert_not_called()
        self.assertEqual(json.loads(receipt.read_text()), job)

    def test_wrong_official_command_stops_without_terminal_receipt(self):
        submitted = self.job()
        official = dict(submitted, argv=['other'])
        receipt = self.root / 'queue.json'
        with patch.object(c, 'official', return_value=official):
            with self.assertRaisesRegex(ValueError, 'command changed'):
                c.await_success(submitted, receipt, ['fixed'])
        self.assertFalse(receipt.exists())

    def test_active_poll_uses_fifteen_seconds_and_then_retains_success(self):
        submitted = self.job('queued', None)
        final = self.job()
        with patch.object(c, 'official', side_effect=[self.job('running', None), final]), patch.object(c.time, 'sleep') as sleep:
            self.assertEqual(c.await_success(submitted, self.root / 'queue.json', ['fixed']), final)
            sleep.assert_called_once_with(15)

    def test_unresolved_intent_never_invokes_command_twice(self):
        with patch.object(c, 'invoke', side_effect=RuntimeError('interrupted')) as command:
            with self.assertRaisesRegex(RuntimeError, 'interrupted'):
                c.command_once(self.root, 'submit', ['queue'])
            with self.assertRaisesRegex(ValueError, 'Unresolved command intent'):
                c.command_once(self.root, 'submit', ['queue'])
            command.assert_called_once()

    def test_failed_command_receipt_is_never_retried(self):
        result = subprocess.CompletedProcess(['queue'], 1, '', 'failure')
        with patch.object(c, 'invoke', return_value=result) as command:
            for _ in range(2):
                with self.assertRaisesRegex(ValueError, 'Command failed; no retry'):
                    c.command_once(self.root, 'submit', ['queue'])
            command.assert_called_once()

    def test_existing_output_prevents_first_invocation(self):
        target = self.root / 'existing.json'
        target.write_text('{}')
        with patch.object(c, 'invoke') as command:
            with self.assertRaisesRegex(ValueError, 'Existing output'):
                c.command_once(self.root, 'prepare', ['prepare'], outputs=[target])
            command.assert_not_called()

    def test_completed_action_resumes_only_identical_outputs(self):
        target = self.root / 'result.json'
        def execute(argv):
            target.write_text('{}')
            return subprocess.CompletedProcess(argv, 0, 'done', '')
        with patch.object(c, 'invoke', side_effect=execute) as command:
            first = c.command_once(self.root, 'prepare', ['prepare'], outputs=[target])
            self.assertEqual(c.command_once(self.root, 'prepare', ['prepare'], outputs=[target]), first)
            target.write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                c.command_once(self.root, 'prepare', ['prepare'], outputs=[target])
            command.assert_called_once()

    def test_changed_intent_cannot_redirect_a_completed_action(self):
        with patch.object(c, 'invoke', return_value=subprocess.CompletedProcess([], 0, '', '')) as command:
            c.command_once(self.root, 'submit', ['queue', 'fixed'])
            with self.assertRaisesRegex(ValueError, 'Changed command intent'):
                c.command_once(self.root, 'submit', ['queue', 'replacement'])
            command.assert_called_once()

    def test_absent_final_storage_stops_after_official_end_grace(self):
        job = dict(self.job(), ended_at='2026-09-27T00:00:00Z')
        with patch.object(c.time, 'time', return_value=c.admission.stamp(job['ended_at']) + 61), \
             patch.object(c, 'read') as reader, patch.object(c.time, 'sleep') as sleep:
            with self.assertRaisesRegex(ValueError, 'Final storage receipt missing'):
                c.wait_storage(self.root, job, self.root / 'manifest', self.root / 'evidence', self.root / 'host', self.root / 'workspace')
            reader.assert_not_called()
            sleep.assert_not_called()

    def test_storage_failure_is_retained_and_never_retried(self):
        paths = {key: self.root / key for key in ('records', 'manifest', 'evidence', 'host', 'queue')}
        paths['run_id'] = 'fixed-run'
        paths['queue'].write_text(json.dumps(self.job()))
        with patch.object(c, 'wait_storage', side_effect=ValueError('coverage failed')) as wait:
            with self.assertRaisesRegex(ValueError, 'coverage failed'):
                c.storage_gate(self.root, paths, {'runtime_workspace': str(self.root / 'workspace')}, self.job())
            with self.assertRaisesRegex(ValueError, 'Prior storage failure'):
                c.storage_gate(self.root, paths, {'runtime_workspace': str(self.root / 'workspace')}, self.job())
            wait.assert_called_once()
        stop = json.loads((self.root / 'storage-stop.json').read_text())
        self.assertFalse(stop['outcomes_read'])
        self.assertNotIn('task_outcome', stop)
        self.assertEqual(stop['error'], 'coverage failed')


if __name__ == '__main__':
    unittest.main()
