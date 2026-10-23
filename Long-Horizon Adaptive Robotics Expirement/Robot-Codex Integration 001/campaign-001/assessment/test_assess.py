"""Synthetic regressions for outcome/validity separation; no robot or model calls."""
from pathlib import Path
import unittest
from unittest.mock import patch

import assess


def fixture(success=True, terminal_closure=False):
    independent = {'schema_version': 'robot-independent-outcome-1.0', 'success': success,
                   'order_version': 1, 'sim_time': 10.0, 'immediate_ready': success,
                   'violations': [] if success else [{'code': 'unmet_quantity'}],
                   'settling': {'observed_s': .5 if success else 0, 'required_s': .5},
                   'first_success': {'order_version': 1, 'snapshot_sha256': 'a' * 64,
                                     'sim_time_s': 10.0, 'required_dwell_s': .5} if success else None}
    host = {'execution_completed': True, 'error': None, 'terminal': 'task_success' if success else 'operator_stop',
            'independent_outcome': independent, 'handbacks': 1 if success else 0}
    registry = ({'h1': {'actor': 'robot', 'kind': 'handback', 'request_id': 'h1', 'phase': 'terminal',
                       'status': 'completed', 'envelope': {'authority_epoch': 3},
                       'verification': {'state': 'public_resumption_conditions', 'next_operation': 'transport'}},
                 'c1': {'actor': 'conventional', 'kind': 'command', 'request_id': 'c1', 'request_event_id': 4,
                       'phase': 'terminal', 'status': 'completed', 'admission': {'status': 'accepted'},
                       'envelope': {'authority_epoch': 4, 'action': {'operation': 'transport'}}}}
                if success else {})
    history = [{'event_id': 1, 'type': 'invocation_start-invocation'}]
    if success:
        history += [{'event_id': 2, 'type': 'control_owner_changed', 'owner': 'conventional', 'authority_epoch': 4,
                     'payload': {'request_id': 'h1', 'supported_next_action': {'operation': 'transport'}}},
                    {'event_id': 5, 'type': 'command_dispatched', 'payload': {'request_id': 'c1'}}]
    if not terminal_closure:
        history.append({'event_id': 6, 'type': 'invocation_retire-invocation'})
    history.append({'event_id': 7, 'type': 'episode_stopped', 'payload': {'reason': host['terminal']}})
    stage = {'checks': {'all_namespace_retirements_observed': True},
             'result': {'old_token_denied_after_retirement': not terminal_closure}}
    sequence = {'host_exit_code': 0}
    return host, registry, history, stage, sequence


class AssessmentTests(unittest.TestCase):
    def test_queue_gate_precedes_attempt_output_reads(self):
        for bad in ({'state': 'running', 'exit_status': None}, {'state': 'succeeded', 'exit_status': 1},
                    {'state': 'failed', 'exit_status': 0}, {'state': 'succeeded', 'exit_status': False}):
            with patch.object(assess, 'read_json', return_value=bad) as reader:
                with self.assertRaisesRegex(ValueError, 'Official queue'):
                    assess.assess('missing-manifest', 'missing-evidence', 'missing-host',
                                  'receipt-only', 'missing-snapshot', 'a' * 64)
                reader.assert_called_once_with('receipt-only')

    def test_wrong_queue_id_rejected(self):
        with self.assertRaisesRegex(ValueError, 'ID differs'):
            assess.queue_gate({'state': 'succeeded', 'exit_status': 0, 'id': 'other'}, 'declared')

    def test_success_requires_protected_independent_outcome(self):
        host, registry, history, stage, sequence = fixture()
        outcome = assess.classify_outcome(host, registry, history)
        lifecycle = assess.lifecycle_disposition(stage, sequence, host, history, outcome)
        self.assertTrue(outcome['protected_handback_accepted'])
        self.assertTrue(outcome['conventional_work_resumed'])
        self.assertEqual(outcome['independent_task_outcome'], 'success')
        self.assertEqual(lifecycle['branch'], 'explicit_retirement')
        host['independent_outcome']['settling']['observed_s'] = .1
        invalid = assess.classify_outcome(host, registry, history)
        self.assertEqual(invalid['independent_task_outcome'], 'unknown')
        self.assertTrue(invalid['independent_outcome_evidence_problems'])

    def test_clean_model_timeout_remains_valid_task_failure(self):
        host, registry, history, stage, sequence = fixture(success=False)
        outcome = assess.classify_outcome(host, registry, history)
        model = assess.model_disposition({'model_started': True, 'success': False,
                                         'error': 'Bounded app-server deadline exceeded'}, 0)
        lifecycle = assess.lifecycle_disposition(stage, sequence, host, history, outcome)
        result = assess.decision({'lifecycle': lifecycle['valid'], 'model': model['recognized']}, outcome, model)
        self.assertEqual(result['validity'], 'valid')
        self.assertEqual(result['task_outcome'], 'failure')
        self.assertTrue(result['task_evidence_valid'])
        self.assertFalse(result['scorable'])
        self.assertFalse(result['scientific_admission']['admissible'])
        self.assertEqual(model['kind'], 'model_wall_deadline')

    def test_provider_failure_is_not_silently_scored_as_robot_failure(self):
        model = assess.model_disposition({'model_started': True, 'success': False,
                                         'error': 'Bootstrap turn did not complete', 'turn_status': 'failed'}, 0)
        self.assertFalse(model['recognized'])

    def test_host_failure_preserves_observed_outcome_but_invalidates_score(self):
        host, registry, history, stage, sequence = fixture()
        outcome = assess.classify_outcome(host, registry, history)
        result = assess.decision({'host_clean': False}, outcome, {'recognized': True, 'kind': 'completed'})
        self.assertEqual(result['observed_task_outcome'], 'success')
        self.assertEqual(result['task_outcome'], 'unknown')
        self.assertEqual(result['validity'], 'invalid')
        self.assertFalse(result['scorable'])

    def test_terminal_host_closure_never_invents_retirement_or_403(self):
        host, registry, history, stage, sequence = fixture(terminal_closure=True)
        outcome = assess.classify_outcome(host, registry, history)
        lifecycle = assess.lifecycle_disposition(stage, sequence, host, history, outcome)
        self.assertTrue(lifecycle['valid'])
        self.assertEqual(lifecycle['branch'], 'successful_terminal_host_closure')
        self.assertFalse(lifecycle['explicit_retirement_receipt_observed'])
        self.assertFalse(lifecycle['late_old_token_http403_observed'])
        self.assertEqual(set(lifecycle['missing_receipts']), {'explicit_retirement', 'late_old_token_http403'})
        stage['checks']['all_namespace_retirements_observed'] = False
        self.assertFalse(assess.lifecycle_disposition(stage, sequence, host, history, outcome)['valid'])

    def test_terminal_closure_requires_corresponding_protected_handback(self):
        host, registry, history, stage, sequence = fixture(terminal_closure=True)
        outcome = assess.classify_outcome(host, registry, history)
        outcome['accepted_handback_corresponds_to_owner_transfer'] = False
        self.assertFalse(assess.lifecycle_disposition(stage, sequence, host, history, outcome)['valid'])

    def test_queue_arguments_bind_declared_attempt(self):
        root = assess.REPO
        interpreter = str(root / 'venv/Scripts/python.exe')
        job = {'cwd': str(root), 'resolved_executable': interpreter,
               'argv': [interpreter, '-X', 'utf8', '-B', str(assess.INTEGRATION / 'readiness-session-10/orchestrator/physical.py'),
                        '--manifest', 'm.json', '--evidence', 'e', '--host-evidence', 'h', '--workspace', 'w', '--mode', 'pilot']}
        self.assertTrue(assess.queue_paths_match(job, root/'m.json', root/'e', root/'h', root/'w'))
        self.assertFalse(assess.queue_paths_match(job, root/'different.json', root/'e', root/'h', root/'w'))
        self.assertFalse(assess.queue_paths_match(job, root/'m.json', root/'e', root/'h', None))
        job['argv'][4] = 'arbitrary_successful_worker.py'
        self.assertFalse(assess.queue_paths_match(job, root/'m.json', root/'e', root/'h', root/'w'))

    def test_copied_prior_timestamps_do_not_match_new_queue_receipt(self):
        job = {'started_at': '2026-09-27T18:00:00Z', 'ended_at': '2026-09-27T18:10:00Z'}
        launch, client = {'started_utc': '2026-09-27T18:00:10Z'}, {'finished_utc': '2026-09-27T18:09:00Z'}
        stamp = lambda text: assess.datetime.fromisoformat(text.replace('Z', '+00:00')).timestamp()
        history = [{'type': 'episode_started', 'wall_unix_s': stamp('2026-09-27T18:00:05Z')},
                   {'type': 'episode_stopped', 'wall_unix_s': stamp('2026-09-27T18:09:30Z')}]
        self.assertTrue(assess.queue_time_matches(job, launch, client, history))
        launch['started_utc'] = '2026-09-26T18:00:10Z'
        self.assertFalse(assess.queue_time_matches(job, launch, client, history))


if __name__ == '__main__':
    unittest.main()
