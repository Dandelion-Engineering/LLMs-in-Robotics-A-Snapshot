import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import collect_results as c


def assessment(outcome='success', validity='valid'):
    return {'id': 'result-original', 'run_id': 'r1', 'supersedes_result_id': None,
            'execution_status': 'completed', 'outcome': outcome, 'validity': validity,
            'metrics': [{'name': 'completion_time_s', 'value': 24., 'unit': 's'}], 'details': {}}


def terminal():
    return {'run_id': 'r1', 'post_run_integrity': {'passed': True},
            'result': {'run_id': 'r1', 'stage': 'evaluation', 'outcome': 'success', 'validity': 'valid',
                       'execution_status': 'completed',
                       'independent_outcome': {'success': True}, 'wall_duration_s': 25., 'completion_time_s': 24.}}


class SelectionTests(unittest.TestCase):
    def test_development_or_nonterminal_cannot_become_evaluation(self):
        for field, value in (('stage', 'development'), ('execution_status', 'running')):
            row = terminal(); row['result'][field] = value
            with self.assertRaisesRegex(ValueError, 'terminal evaluation'):
                c.selected_flat(row, assessment())

    def test_correction_overrides_raw_independent_success_and_completion(self):
        row = assessment('partial'); row.update(id='correction', supersedes_result_id='result-original')
        flat = c.selected_flat(terminal(), row)
        self.assertFalse(c.protocol._success(flat))
        self.assertIsNone(flat['completion_time_s'])
        self.assertIsNone(flat['wall_duration_s'])
        self.assertNotIn('independent_outcome', flat)

    def test_unknown_correction_is_not_old_success(self):
        row = assessment('unknown'); row['supersedes_result_id'] = 'result-original'
        self.assertIsNone(c.protocol._success(c.selected_flat(terminal(), row)))

    def test_wrapper_integrity_invalidates_entire_analysis_pair(self):
        wrapper = terminal(); wrapper['integrity_breach'] = True
        flat = c.selected_flat(wrapper, assessment())
        self.assertTrue(c.protocol._infra_invalid(flat))
        self.assertEqual(flat['validity'], 'invalid')

    def test_missing_integrity_is_unknown(self):
        wrapper = terminal(); wrapper.pop('post_run_integrity')
        self.assertEqual(c.selected_flat(wrapper, assessment())['validity'], 'unknown')

    def test_raw_infrastructure_invalid_cannot_disappear(self):
        wrapper = terminal(); wrapper['result'].update(validity='invalid', invalidity_class='infrastructure')
        self.assertTrue(c.protocol._infra_invalid(c.selected_flat(wrapper, assessment())))

    def test_prior_review_retains_block_exclusion(self):
        wrapper = terminal(); wrapper['excluded_from_primary_by_prior_review'] = True
        flat = c.selected_flat(wrapper, assessment())
        self.assertTrue(c.protocol._infra_invalid(flat))
        self.assertEqual(flat['outcome'], 'success')

    def test_unmeasured_clocks_stay_missing_and_units_checked(self):
        row = assessment(); row['metrics'][0]['value'] = None
        self.assertIsNone(c.selected_flat(terminal(), row)['completion_time_s'])
        row['metrics'][0].update(value=24., unit='ms')
        with self.assertRaisesRegex(ValueError, 'seconds'):
            c.selected_flat(terminal(), row)

    def test_unambiguous_chain_only(self):
        old = assessment(); new = copy.deepcopy(old)
        new.update(id='new', supersedes_result_id=old['id'])
        selected, history = c.current_result([old, new], 'r1')
        self.assertEqual(selected['id'], 'new'); self.assertEqual(len(history), 2)
        branch = copy.deepcopy(new); branch['id'] = 'branch'
        with self.assertRaises(ValueError): c.current_result([old, new, branch], 'r1')

    def test_disconnected_cycle_rejected_even_with_one_leaf(self):
        old = assessment(); a = copy.deepcopy(old); b = copy.deepcopy(old)
        a.update(id='a', supersedes_result_id='b'); b.update(id='b', supersedes_result_id='a')
        with self.assertRaisesRegex(ValueError, 'Disconnected'):
            c.current_result([old, a, b], 'r1')


class FinalizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name).resolve()
        self.batch = self.root / 'batches' / 'job1'; self.batch.mkdir(parents=True)
        self.attempt = self.root / 'attempts' / 'r1'; self.attempt.mkdir(parents=True)
        self.wrapper = terminal()
        self.wrapper.update(queue_job_id='job1', release_sha256='a'*64, manifest_sha256='b'*64)
        self.write(self.attempt / 'terminal.json', self.wrapper)
        receipt = {'id': 'job1', 'state': 'succeeded', 'exit_status': 0}
        self.write(self.batch / 'official-queue-status.json', receipt)
        self.write(self.batch / 'planned.json', {'queue_job_id': 'job1', 'release_sha256': 'a'*64, 'selected_run_ids': ['r1']})
        terminal_ref = c.ref(self.attempt / 'terminal.json'); terminal_ref['run_id'] = 'r1'
        self.write(self.batch / 'finished.json', {'queue_job_id': 'job1', 'terminal_run_ids': ['r1'], 'terminal_refs': [terminal_ref]})
        self.final = {'queue_job_id': 'job1', 'run_ids': ['r1'],
                      'official_queue_receipt_sha256': c.ref(self.batch / 'official-queue-status.json')['sha256']}
        self.write(self.batch / 'finalized.json', self.final)

    def tearDown(self): self.temp.cleanup()
    def write(self, path, value): path.write_text(json.dumps(value), encoding='utf-8')
    def verify(self): return c.verified_terminal(self.root, 'r1', 'a'*64, 'b'*64)

    def test_finalized_terminal_verified(self):
        actual, provenance = self.verify()
        self.assertEqual(actual, self.wrapper)
        self.assertIn('official_queue_receipt', provenance)

    def test_unfinalized_terminal_rejected(self):
        (self.batch / 'finalized.json').unlink()
        with self.assertRaises(ValueError): self.verify()

    def test_changed_terminal_rejected(self):
        self.wrapper['result']['outcome'] = 'failure'
        self.write(self.attempt / 'terminal.json', self.wrapper)
        with self.assertRaises(ValueError): self.verify()

    def test_failed_queue_cannot_be_finalized_by_marker(self):
        self.write(self.batch / 'official-queue-status.json', {'id': 'job1', 'state': 'failed', 'exit_status': 1})
        self.final['official_queue_receipt_sha256'] = c.ref(self.batch / 'official-queue-status.json')['sha256']
        self.write(self.batch / 'finalized.json', self.final)
        with self.assertRaises(ValueError): self.verify()

    def test_missing_attempts_are_not_fabricated_results(self):
        manifest = {'run_id': 'never-ran'}
        self.write(self.root / 'never.json', manifest)
        reference = {'path': 'never.json', 'sha256': c.ref(self.root / 'never.json')['sha256']}
        self.write(self.root / 'release.json', {'manifest_refs': [reference]})
        with patch.object(c.protocol, 'load_release', return_value=[manifest]):
            partial = c.collect(self.root, [])
            self.assertEqual(partial['results'], [])
            self.assertEqual(partial['counts']['missing_terminal'], 1)
            self.assertFalse(partial['complete_terminal_accounting'])
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                c.collect(self.root, [], complete=True)


if __name__ == '__main__': unittest.main()
