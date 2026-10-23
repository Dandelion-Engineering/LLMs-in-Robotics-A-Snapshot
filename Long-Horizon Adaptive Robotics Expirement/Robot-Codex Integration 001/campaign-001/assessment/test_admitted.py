"""Tamper and strict-boundary tests; no model, simulator or queue submission."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import admitted as a


def write(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')
    return {'path': str(path.resolve()), 'sha256': a.base.hash_file(path)}


class AdmissionTests(unittest.TestCase):
    def test_failed_queue_does_not_read_certificate_or_outcomes(self):
        for status in ({'state': 'failed', 'exit_status': 0}, {'state': 'succeeded', 'exit_status': False},
                       {'state': 'running', 'exit_status': None}):
            with patch.object(a.base, 'read_json', return_value=status) as reader:
                with self.assertRaisesRegex(ValueError, 'Official queue'):
                    a.admitted_assess('absent-cert', '0' * 64, 'absent-registration', 'run', 'receipt', 'job')
                reader.assert_called_once_with('receipt')

    def test_certificate_cannot_supply_its_own_trust_anchor(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'certificate.json'
            write(path, {'admitted': True, 'certificate_sha256': 'f' * 64})
            with self.assertRaisesRegex(ValueError, 'external seal'):
                a.verify_certificate(path, 'f' * 64)

    def test_artifact_changed_after_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'artifact.json'
            binding = write(path, {'source': 'frozen'})
            write(path, {'source': 'changed'})
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                a.artifact(binding)

    def test_fixed_real_schedule_and_manifests_pass(self):
        schedule = a.base.read_json(a.CAMPAIGN / 'predeclared-v1/schedule.json')
        attempts = a.base.read_json(a.CAMPAIGN / 'execution-plan.json')['attempts']
        a.verify_schedule(schedule, attempts)

    def test_replacement_and_seed_swap_fail_even_with_resealed_outer_plan(self):
        schedule = a.base.read_json(a.CAMPAIGN / 'predeclared-v1/schedule.json')
        attempts = a.base.read_json(a.CAMPAIGN / 'execution-plan.json')['attempts']
        swapped = copy.deepcopy(schedule)
        swapped['slots'][0]['noise_seed'], swapped['slots'][1]['noise_seed'] = 22002, 22001
        with self.assertRaisesRegex(ValueError, 'seed violation'):
            a.verify_schedule(swapped, attempts)
        with self.assertRaisesRegex(ValueError, 'Exactly 24'):
            a.verify_schedule(schedule, attempts + [attempts[0]])

    def timing_fixture(self, folder, simulation, lag=.041):
        root = Path(folder)
        history = root / 'history.jsonl'
        rows = [{'event_id': i + 1, 'type': 'episode_started' if i == 0 else
                 'episode_stopped' if i == len(simulation) - 1 else 'observation',
                 'wall_elapsed_s': float(i), 'sim_time_s': sim} for i, sim in enumerate(simulation)]
        history.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
        host = root / 'result.json'
        write(host, {'timing': {'maximum_wall_minus_sim_s': lag, 'samples': 100}})
        source = a.REPO / 'Long-Horizon Adaptive Robotics Expirement/Runtime 004/experiment.py'
        return history, host, source

    def test_per_tick_lag_equal_point_one_fails_strictly(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = self.timing_fixture(folder, [0., 1., 2.], lag=.1)
            result = a.reconstruct_timing(*paths)
            self.assertTrue(result['derived_journal_timing']['actual_host_timing_pass'])
            self.assertFalse(result['original_per_tick_lag_pass'])
            self.assertFalse(result['passed'])

    def test_exactly_one_percent_bad_windows_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = self.timing_fixture(folder, [0.] + [i + .06 for i in range(1, 101)])
            result = a.reconstruct_timing(*paths)
            self.assertEqual(result['derived_journal_timing']['outside_rtf_tolerance_fraction'], .01)
            self.assertFalse(result['passed'])

    def test_zero_window_and_nonfinite_samples_cannot_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = self.timing_fixture(folder, [0., float('nan')])
            with self.assertRaisesRegex(ValueError, 'Non-finite'):
                a.reconstruct_timing(*paths)
            paths = self.timing_fixture(folder, [0., .05])
            rows = a.base.jsonl(paths[0]); rows[-1]['wall_elapsed_s'] = .05
            paths[0].write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
            self.assertFalse(a.reconstruct_timing(*paths)['passed'])

    def test_reordered_or_duplicate_journal_ids_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = self.timing_fixture(folder, [0., 1., 2.])
            rows = a.base.jsonl(paths[0]); rows[1]['event_id'] = rows[0]['event_id']
            paths[0].write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'strictly increase'):
                a.reconstruct_timing(*paths)

    def test_exact_prior_pilot_reproduces_retained_windows_without_relaxing_old_failure(self):
        retained = a.base.read_json(a.CAMPAIGN / 'admission/census-002/retained-timing.json')
        for row in retained['attempts']:
            result = a.reconstruct_timing(row['journal']['path'], row['host_result']['path'], row['timing_monitor']['path'])
            self.assertEqual(result['derived_journal_timing'], row['derived_journal_timing'])
            if row['attempt'] == 'pilot-001':
                self.assertTrue(result['passed'])
                self.assertEqual(result['derived_journal_timing']['complete_wall_windows'], 237)
            else:
                self.assertFalse(result['original_per_tick_lag_pass'])
                self.assertFalse(result['passed'])

    def storage_fixture(self, folder):
        root = Path(folder)
        policy = {'max_sample_gap_s': 30, 'retirement_headroom_bytes': 2_000_000_000, 'accounting_scope': 'native and WSL'}
        policy_binding = write(root / 'policy.json', policy)
        baseline = write(root / 'baseline.json', {'baseline': True})
        cert = {'artifacts': {'storage_monitor': {'sha256': 'a' * 64},
                             'storage_policy': policy_binding, 'preflight_capacity': baseline}}
        job = {'id': 'job1', 'state': 'succeeded', 'exit_status': 0,
               'started_at': '2026-09-27T00:00:01Z', 'ended_at': '2026-09-27T00:00:04Z'}
        queue = root / 'queue.json'; queue_binding = write(queue, job)
        samples = [{'started_utc': f'2026-09-27T00:00:0{i}Z', 'finished_utc': f'2026-09-27T00:00:0{i+1}Z',
                    'native': {'free_bytes': {'C:': 200_000_000_000}},
                    'wsl': {'free_bytes': {'/var/tmp': 200_000_000_000}}, 'aggregate_additional_bytes': i}
                   for i in (0, 4)]
        samples_path = root / 'samples.jsonl'
        samples_path.write_text(''.join(json.dumps(row) + '\n' for row in samples), encoding='utf-8')
        attempt = {'run_id': 'run1', 'manifest': {'path': str(root / 'manifest.json')},
                   'evidence': str(root / 'evidence'), 'host_evidence': str(root / 'host'), 'workspace': str(root / 'workspace')}
        receipt = {'schema': 'campaign001-storage-guard-1', 'run_id': 'run1', 'job_id': 'job1',
                   'monitor_source_sha256': 'a' * 64, 'config_sha256': policy_binding['sha256'], 'baseline': baseline,
                   'paths': {key: attempt['manifest']['path'] if key == 'manifest' else attempt[key]
                             for key in ('manifest', 'evidence', 'host_evidence', 'workspace')},
                   'official_queue_receipt': queue_binding,
                   'official_queue_state': 'succeeded', 'official_queue_exit_status': 0,
                   'samples': {'path': str(samples_path), 'sha256': a.base.hash_file(samples_path)},
                   'sample_count': 2, 'state': 'completed', 'coverage_complete': True,
                   'first_sample_utc': samples[0]['started_utc'], 'last_sample_utc': samples[-1]['finished_utc'],
                   'admission_stop_latched': False, 'reserve_bytes': 100_000_000_000,
                   'minimum_free_bytes': {'native': 200_000_000_000, 'wsl': 200_000_000_000},
                   'peak_aggregate_additional_bytes': 4, 'max_sample_gap_s': 4, 'accounting_scope': 'native and WSL'}
        return root / 'receipt.json', receipt, cert, attempt, queue, job

    def test_storage_authenticated_complete_receipt_passes(self):
        with tempfile.TemporaryDirectory() as folder:
            path, receipt, *args = self.storage_fixture(folder)
            write(path, receipt)
            self.assertEqual(a.verify_storage(path, *args), receipt)

    def test_storage_false_coverage_summary_and_stop_latch_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path, receipt, *args = self.storage_fixture(folder)
            for field, value in (('last_sample_utc', '2026-09-27T00:00:03Z'),
                                 ('admission_stop_latched', True), ('peak_aggregate_additional_bytes', 0),
                                 ('minimum_free_bytes', {'native': 300_000_000_000, 'wsl': 200_000_000_000})):
                bad = copy.deepcopy(receipt); bad[field] = value
                write(path, bad)
                with self.assertRaises(ValueError, msg=field):
                    a.verify_storage(path, *args)

    def test_storage_wrong_job_baseline_or_samples_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path, receipt, *args = self.storage_fixture(folder)
            bad = copy.deepcopy(receipt); bad['job_id'] = 'other'
            write(path, bad)
            with self.assertRaisesRegex(ValueError, 'identity'):
                a.verify_storage(path, *args)
            write(path, receipt)
            Path(receipt['samples']['path']).write_text('{}\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'SHA256'):
                a.verify_storage(path, *args)


if __name__ == '__main__':
    unittest.main()
