"""Synthetic operator/stop counterexamples; never submit jobs or write real maps."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import operate
import settle


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


class OperatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registration = self.root / 'registration.json'
        write(self.registration, {})
        self.attempt = {'ordinal': 1, 'run_id': 'synthetic-1', 'family': 'misplaced-stock',
                        'manifest': {'path': str(self.root / 'manifest.json')},
                        **{key: str(self.root / key) for key in ('workspace', 'evidence', 'host_evidence')}}
        self.cert = {'attempts': [self.attempt], 'artifacts': {
            name: {'path': str(self.root / (name + '.json'))}
            for name in ('storage_policy', 'storage_baseline')}}
        self.args = SimpleNamespace(run_id='synthetic-1', registration=self.registration, dry_run=False)
        self.folder = self.root / 'execution/synthetic-1'
        self.addCleanup(patch.stopall)
        patch.object(operate, 'HERE', self.root).start()
        patch.object(operate, 'current_attempt', return_value=(self.cert, {'certificate_sha256': 'seal'}, self.attempt)).start()

    def test_existing_launch_intent_never_resubmits(self):
        write(self.folder / 'launch-intent.json', {'run_id': 'synthetic-1'})
        with patch.object(operate, 'queue') as queue:
            with self.assertRaisesRegex(ValueError, 'reconcile retained intent'):
                operate.start(self.args)
            queue.assert_not_called()

    def test_ready_receipt_does_not_override_storage_stop_latch(self):
        def guard(*args, **kwargs):
            write(self.folder / 'storage/ready.json', {'ready': True})
            write(self.folder / 'storage/admission-stop.json', {'reason': 'reserve threatened'})
            return SimpleNamespace(pid=123, poll=lambda: None)
        with patch.object(operate.subprocess, 'Popen', side_effect=guard), \
             patch.object(operate, 'queue', return_value={'id': 'never-submit', 'state': 'queued'}) as queue, \
             redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, 'guard|stop|ready'):
                operate.start(self.args)
            queue.assert_not_called()

    def test_ready_receipt_does_not_override_dead_monitor(self):
        def guard(*args, **kwargs):
            write(self.folder / 'storage/ready.json', {'ready': True})
            return SimpleNamespace(pid=123, poll=lambda: 1)
        with patch.object(operate.subprocess, 'Popen', side_effect=guard), \
             patch.object(operate, 'queue', return_value={'id': 'never-submit', 'state': 'queued'}) as queue, \
             redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, 'guard|stop|ready'):
                operate.start(self.args)
            queue.assert_not_called()

    def test_failed_queue_is_retained_without_consuming_outcomes(self):
        write(self.folder / 'queue-submit.json', {'id': 'failed-job'})
        write(self.folder / 'storage/receipt.json', {})
        job = {'id': 'failed-job', 'state': 'failed', 'exit_status': 1}
        with patch.object(operate, 'queue', return_value=job), \
             patch.object(operate, 'current_attempt', side_effect=AssertionError('Outcome admission must not run')), \
             redirect_stdout(io.StringIO()):
            operate.collect(self.args)
        self.assertEqual(operate.read(self.folder / 'official-status.json'), job)
        self.assertFalse((self.folder / 'assessment.json').exists())


class AdmissionStopTests(unittest.TestCase):
    def test_full_admitted_threshold_failure_is_ordinary(self):
        # This is the pair of checks emitted by admitted_assess, unlike the
        # preparation-only shape. A numerical threshold failure is not corrupt
        # timing evidence and must consume one ordinary-invalid count.
        assessment = {'validity': 'invalid', 'task_outcome': 'unknown', 'scorable': False,
            'failed_checks': ['complete_retained_timing_replayed_and_passed',
                              'current_episode_frozen_full_sample_timing_and_scheduling'],
            'campaign_timing': {'schema': 'rci-campaign-independent-timing-2',
                'passed': False, 'scheduling_pass': True,
                'sample_count': 4, 'metadata_sha256': 'a' * 64, 'sample_sha256': 'b' * 64,
                'replayed_timing': {'actual_host_timing_pass': False,
                                   'maximum_lag_s': .11, 'complete_wall_windows': 1,
                                   'outside_rtf_tolerance_fraction': 0.}},
            'verification_errors': {}}
        self.assertEqual(settle.classify(assessment, 0)[:2], (False, 1))
        self.assertEqual(settle.classify(assessment, 1)[:2], (True, 2))

    def test_corrupt_timing_is_an_immediate_stop(self):
        assessment = {'validity': 'invalid', 'task_outcome': 'unknown', 'scorable': False,
            'failed_checks': ['complete_retained_timing_replayed_and_passed',
                              'current_episode_frozen_full_sample_timing_and_scheduling'],
            'campaign_timing': None, 'verification_errors': {'timing': 'Timing sample hash mismatch'}}
        self.assertTrue(settle.classify(assessment, 0)[0])


if __name__ == '__main__':
    unittest.main()
