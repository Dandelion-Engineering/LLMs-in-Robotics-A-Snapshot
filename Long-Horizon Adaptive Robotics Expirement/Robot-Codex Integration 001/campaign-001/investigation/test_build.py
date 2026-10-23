"""Evidence-boundary and denominator checks; synthetic inputs never reach report."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('investigation_build', Path(__file__).with_name('build.py'))
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='rci-investigation-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.execution = self.root / 'execution'
        self.output = self.root / 'output'
        self.output.mkdir()
        self.attempt = {'ordinal': 1, 'run_id': 'RCI001-C01-test', 'family': 'misplaced-stock',
            'manifest': {'path': str(self.root / 'manifest.json'), 'sha256': 'a' * 64},
            'host_evidence': str(self.root / 'host'), 'evidence': str(self.root / 'orchestrator'),
            'storage_receipt': str(self.execution / 'RCI001-C01-test/storage/receipt.json')}
        self.folder = self.execution / self.attempt['run_id']
        (self.folder / 'storage').mkdir(parents=True)
        report.READS.clear()

    def save(self, path, value):
        path.write_text(json.dumps(value), encoding='utf-8')

    def receipt(self, state, exit_status):
        path = self.folder / 'storage/queue-receipt.json'
        self.save(path, {'id': 'synthetic-job', 'state': state, 'exit_status': exit_status})
        return path

    def record(self):
        return report.run_record(self.attempt, self.execution, self.output)

    def test_wilson_exact_all_success_and_no_trials(self):
        self.assertIsNone(report.wilson(0, 0))
        low, high = report.wilson(12, 12)
        self.assertAlmostEqual(low, .7575059933447592)
        self.assertEqual(high, 1)
        low, high = report.wilson(0, 12)
        self.assertAlmostEqual(low, 0)
        self.assertAlmostEqual(high, .2424940066552408)

    def test_failed_queue_never_opens_assessment_or_traces(self):
        self.receipt('failed', 1)
        (self.folder / 'assessment.json').write_bytes(b'invalid JSON must never be opened')
        row = self.record()
        self.assertFalse(row['scorable'])
        self.assertEqual(row['task_outcome'], 'unknown')
        self.assertEqual(row['events'], [])
        self.assertEqual([x['role'] for x in report.READS], ['official queue receipt'])

    def test_boolean_zero_and_running_queue_do_not_open_outcomes(self):
        for state, code in [('succeeded', False), ('running', 0)]:
            self.receipt(state, code)
            (self.folder / 'assessment.json').write_bytes(b'invalid JSON must never be opened')
            self.assertFalse(self.record()['scorable'])

    def test_unfinished_is_pending_until_explicit_not_run_disposition(self):
        self.assertEqual(self.record()['execution_status'], 'pending')
        self.save(self.folder / 'disposition.json', {'run_id': self.attempt['run_id'],
            'execution_status': 'not_run', 'reason': 'Synthetic predeclared stop'})
        row = self.record()
        self.assertEqual((row['execution_status'], row['validity'], row['task_outcome']),
                         ('not_run', 'unknown', 'not_assessed'))

    def test_admitted_assessment_must_bind_official_queue_bytes(self):
        self.receipt('succeeded', 0)
        self.save(self.folder / 'assessment.json', {'schema': 'robot-codex-campaign-admitted-assessment-1',
            'run_id': self.attempt['run_id'], 'queue_job_id': 'synthetic-job',
            'bindings': {'manifest_sha256': 'a' * 64, 'queue_receipt_sha256': 'b' * 64}})
        with self.assertRaisesRegex(ValueError, 'identity/queue/manifest'):
            self.record()

    def test_all_planned_bounds_retain_invalid_and_unrun_slots(self):
        runs = [{'family': 'misplaced-stock', 'scorable': True, 'task_outcome': 'success',
                 'validity': 'valid', 'execution_status': 'completed'},
                {'family': 'misplaced-stock', 'scorable': True, 'task_outcome': 'failure',
                 'validity': 'valid', 'execution_status': 'completed'},
                {'family': 'blocked-insert-home', 'scorable': False, 'task_outcome': 'unknown',
                 'validity': 'invalid', 'execution_status': 'failed'},
                {'family': 'blocked-insert-home', 'scorable': False, 'task_outcome': 'not_assessed',
                 'validity': 'unknown', 'execution_status': 'not_run'}]
        result = report.aggregate(runs)['all scheduled slots']
        self.assertEqual((result['planned'], result['valid'], result['successes'], result['invalid'], result['not_run']), (4, 2, 1, 1, 1))
        self.assertEqual(result['all_planned_bounds'], [.25, .75])

    def test_preselected_examples_do_not_depend_on_outcomes(self):
        runs = [{'run_id': str(i), 'family': 'misplaced-stock' if i % 2 else 'blocked-insert-home',
                 'examples': [], 'validity': 'unknown', 'scorable': False} for i in range(1, 25)]
        report.select_examples(runs)
        self.assertEqual([r['run_id'] for r in runs if r['examples']], ['1', '2', '23', '24'])

    def test_changed_trace_hash_is_refused(self):
        path = self.root / 'history.jsonl'
        path.write_bytes(b'{"type":"test"}\n')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            report.trace(path, 'protected_host:history.jsonl',
                         {('protected_host', 'history.jsonl'): {'sha256': '0' * 64, 'bytes': path.stat().st_size}}, self.output)

    def test_observed_invalid_completion_is_visible_but_never_scored(self):
        receipt = self.receipt('succeeded', 0)
        queue = json.loads(receipt.read_text())
        queue.update(started_at='2026-09-27T19:00:00+00:00', ended_at='2026-09-27T19:01:00+00:00')
        self.save(receipt, queue)
        self.save(self.folder / 'assessment.json', {'schema': 'robot-codex-campaign-admitted-assessment-1',
            'run_id': self.attempt['run_id'], 'queue_job_id': 'synthetic-job',
            'bindings': {'manifest_sha256': 'a' * 64, 'queue_receipt_sha256': report.digest(receipt.read_bytes())},
            'validity': 'invalid', 'task_outcome': 'unknown', 'observed_task_outcome': 'success',
            'scorable': False, 'failed_checks': ['strict_timing'], 'evidence_inventory': []})
        with patch.object(report, 'extract_events', return_value={'events': [], 'untimed': []}), \
                patch.object(report, 'load_frames', return_value={'frames': []}):
            row = self.record()
        self.assertEqual(row['observed_task_outcome'], 'success')
        self.assertEqual(row['task_outcome'], 'unknown')
        self.assertFalse(row['scorable'])
        self.assertTrue(row['started'])
        counts = report.aggregate([row])['all scheduled slots']
        self.assertEqual((counts['observed_evaluator_successes'], counts['observed_successes_among_invalid'],
                          counts['authenticated_assessments'], counts['started']), (1, 1, 1, 1))
        self.assertEqual((counts['successes'], counts['valid']), (0, 0))
        self.assertIsNone(counts['wilson95'])
        self.assertEqual(counts['all_planned_bounds'], [0., 1.])

    def test_failed_queue_cannot_contribute_observed_completion(self):
        receipt = self.receipt('failed', 1)
        queue = json.loads(receipt.read_text())
        queue['started_at'] = None
        self.save(receipt, queue)
        self.save(self.folder / 'assessment.json', {'observed_task_outcome': 'success'})
        row = self.record()
        counts = report.aggregate([row])['all scheduled slots']
        self.assertEqual(row['observed_task_outcome'], 'not_assessed')
        self.assertEqual(counts['observed_evaluator_successes'], 0)
        self.assertEqual(counts['authenticated_assessments'], 0)
        self.assertEqual(counts['started'], 0)

    def test_stopped_allocation_keeps_unrun_preselected_examples(self):
        runs = [{'ordinal': i, 'run_id': str(i), 'execution_status': 'completed' if i <= 10 else 'not_run',
                 'started': i <= 10, 'reason': 'Two consecutive infrastructure-invalid attempts',
                 'family': 'misplaced-stock' if i % 2 else 'blocked-insert-home',
                 'examples': [], 'validity': 'unknown', 'scorable': False} for i in range(1, 25)]
        report.select_examples(runs)
        stop = report.stop_summary(runs)
        self.assertEqual((stop['not_run_count'], stop['first_unrun_ordinal'], stop['last_started_ordinal']), (14, 11, 10))
        self.assertEqual(stop['preselected_unrun_ids'], ['23', '24'])
        self.assertEqual(stop['reason'], 'Two consecutive infrastructure-invalid attempts')

    def test_program_invocation_count_deduplicates_admission_and_final_receipts(self):
        source = '5ed894a33d7555ee5c4e5533885841e903b2ae210fdce69d6369226c66d0876e'
        runs = [{'run_id': 'synthetic', 'family': 'misplaced-stock', 'examples': [],
                 'validity': 'valid', 'scorable': True, 'task_outcome': 'success',
                 'programs': {'one.admitted.json': {'run_id': 'one', 'record_kind': 'admission',
                    'source_sha256': source, 'final_record': 'one.json'},
                    'one.json': {'run_id': 'one', 'record_kind': 'final', 'source_sha256': source}}}]
        report.select_examples(runs)
        summary = runs[0]['program_summary']
        self.assertEqual((summary['unique_invocation_count'], summary['receipt_count']), (1, 2))
        self.assertIn('no robot actuation calls', summary['scope'])
        self.assertIn('Outcome-selected first behavior: bounded program invocation', runs[0]['examples'])
        self.assertNotIn('program admission without retained final receipt', runs[0]['inspection_categories'])


if __name__ == '__main__':
    unittest.main()
