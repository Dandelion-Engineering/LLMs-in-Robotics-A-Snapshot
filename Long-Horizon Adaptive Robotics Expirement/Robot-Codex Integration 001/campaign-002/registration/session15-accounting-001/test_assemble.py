import copy
import unittest
import assemble as a


class DiagnosticAccounting(unittest.TestCase):
    def fixture(self):
        jobs, docs, rows = {}, {}, []
        for jid, run, state, exit_code, relative, _ in a.OBSERVATIONS:
            jobs[jid] = {'id': jid, 'state': state, 'exit_status': exit_code, 'started_at': 'start', 'ended_at': 'end'}
            rows.append({'official_queue': {'id': jid}, 'known_model_invocations_started': None,
                         'qualification_or_diagnostic_status': 'outcome_not_consumed'})
            docs[str(a.C / 'io-repair' / relative)] = ({'job_id': jid, 'run_id': run, 'task_outcome': 'unknown',
                'diagnostic_only': True, 'client': {'model_started': True}} if exit_code == 0 else
                {'queue_job_id': jid, 'run_id': run, 'task_outcome': 'unknown', 'assessment_state': 'not_assessed',
                 'scorable': False, 'metadata': {'interrupt\\client\\result.json': {'metadata': {'model_started': True}}}})
        result = {'refresh_provenance': {'official_statuses': jobs, 'current_bindings': {}}, 'source_bindings': {},
                  'diagnostic_observed_model_starts': {}, 'rows': rows, 'limitations': [],
                  'totals': {'known_qualification_model_invocations_started': 19, 'known_scored_model_invocations_started': 0,
                    'diagnostic_only_observed_model_starts_lower_bound': 10,
                    'observed_model_starts_lower_bound_from_assessable_and_diagnostic_receipts': 29,
                    'observed_turn_start_requests_from_assessable_and_diagnostic_receipts': 20}}
        return result, docs

    def run_add(self, result, docs):
        return a.add_starts(result, lambda path: docs[str(path)],
                            lambda path: {'path': str(path), 'sha256': 'a' * 64, 'bytes': 1})

    def test_adds_two_lower_bounds_without_request_or_verdict_inference(self):
        result, docs = self.fixture(); self.run_add(result, docs)
        self.assertEqual(result['totals']['observed_model_starts_lower_bound_from_assessable_and_diagnostic_receipts'], 31)
        self.assertEqual(result['totals']['diagnostic_only_observed_model_starts_lower_bound'], 12)
        self.assertEqual(result['totals']['observed_turn_start_requests_from_assessable_and_diagnostic_receipts'], 20)
        self.assertTrue(all(r['qualification_or_diagnostic_status'] == 'outcome_not_consumed' and r['known_model_invocations_started'] is None for r in result['rows']))

    def test_rejects_active_wrong_exit_and_boolean_or_float_zero(self):
        for state, code in [('running', None), ('succeeded', False), ('succeeded', 0.0), ('failed', 1)]:
            result, docs = self.fixture(); result['refresh_provenance']['official_statuses'][a.OBSERVATIONS[0][0]].update(state=state, exit_status=code)
            with self.assertRaises(ValueError): self.run_add(result, docs)

    def test_rejects_wrong_failed_job_status(self):
        result, docs = self.fixture(); result['refresh_provenance']['official_statuses'][a.OBSERVATIONS[1][0]]['exit_status'] = 2
        with self.assertRaises(ValueError): self.run_add(result, docs)

    def test_rejects_nonboolean_observation(self):
        for value in (1, False, 'true', None):
            result, docs = self.fixture(); next(iter(docs.values()))['client']['model_started'] = value
            with self.assertRaises(ValueError): self.run_add(result, docs)

    def test_rejects_prior_or_new_duplicate_accounting(self):
        result, docs = self.fixture(); result['diagnostic_observed_model_starts'][a.OBSERVATIONS[0][0]] = {}
        with self.assertRaises(ValueError): self.run_add(result, docs)
        result, docs = self.fixture(); self.run_add(result, docs)
        with self.assertRaises(ValueError): self.run_add(result, docs)

    def test_rejects_diagnosis_identity_or_scope_promotion(self):
        for key, value in [('job_id', 'other'), ('run_id', 'other'), ('task_outcome', 'success'), ('diagnostic_only', False)]:
            result, docs = self.fixture(); next(iter(docs.values()))[key] = value
            with self.assertRaises(ValueError): self.run_add(result, docs)

    def test_rejects_missing_duplicate_and_already_counted_model_rows(self):
        for mode in ('missing', 'duplicate', 'counted'):
            result, docs = self.fixture()
            if mode == 'missing': result['rows'].pop(0)
            elif mode == 'duplicate': result['rows'].append(copy.deepcopy(result['rows'][0]))
            else: result['rows'][0]['known_model_invocations_started'] = 1
            with self.assertRaises(ValueError): self.run_add(result, docs)

    def test_rejects_inconsistent_prior_lower_bound(self):
        result, docs = self.fixture(); result['totals']['diagnostic_only_observed_model_starts_lower_bound'] = 11
        with self.assertRaises(ValueError): self.run_add(result, docs)


if __name__ == '__main__': unittest.main()
