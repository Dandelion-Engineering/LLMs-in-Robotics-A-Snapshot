"""Synthetic regressions for outcome/validity separation; no robot or model calls."""
from pathlib import Path
import ast
import copy
import importlib.util
import json
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import assess
from test_resource_integrity import resource_fixture


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
               'argv': [interpreter, '-X', 'utf8', '-B', str(assess.LAUNCHER),
                        '--manifest', 'm.json', '--evidence', 'e', '--host-evidence', 'h', '--workspace', 'w', '--mode', 'pilot']}
        self.assertTrue(assess.queue_paths_match(job, root/'m.json', root/'e', root/'h', root/'w'))
        self.assertFalse(assess.queue_paths_match(job, root/'different.json', root/'e', root/'h', root/'w'))
        self.assertFalse(assess.queue_paths_match(job, root/'m.json', root/'e', root/'h', None))
        job['argv'][4] = 'arbitrary_successful_worker.py'
        self.assertFalse(assess.queue_paths_match(job, root/'m.json', root/'e', root/'h', root/'w'))


def write_json(path, value):
    path.write_text(json.dumps(value, allow_nan=False), encoding='utf-8')


def write_jsonl(path, values):
    path.write_text(''.join(json.dumps(value) + '\n' for value in values), encoding='utf-8')


class PilotRetirementInventoryTests(unittest.TestCase):
    """Exercise the real pilot wrapper, legacy inspector and retirement predicate."""

    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (self.root / 'client').mkdir()
        for name, value in {
            'runtime-before-close.json': {'files': {}, 'total_bytes': 0},
            'runtime-after-close.json': {'files': {}, 'total_bytes': 0},
            'stage-result.json': {'cleanup_clean': True, 'durable_retention_verified': True},
            'client/result.json': {}, 'client/launch.json': {}, 'canary-stdout.json': {},
        }.items():
            write_json(self.root / name, value)
        for name in ('client/events.jsonl', 'broker-events.jsonl'):
            write_jsonl(self.root / name, [])
        self.put('executor-1-retirement.json')
        self.put('executor-2-retirement.json')

    def put(self, name, *, qualified=True, **final_changes):
        final = {'retired': True, 'namespace_evidence_available': True,
                 'namespace_ids': [101], 'namespace_members': [], 'outer_same_process': False}
        final.update(final_changes)
        write_json(self.root / name, {'qualified': qualified, 'observations': [final]})

    def inspect(self):
        # No patched entry point, file reader, retirement predicate or stage upgrader.
        return assess.inspect_stage(self.root)

    def test_versioned_and_legacy_host_layouts_are_accepted_by_actual_pilot(self):
        for name in ('codehost-1-retirement.json', 'codehost-owner-retirement-v3.json'):
            with self.subTest(name=name):
                self.put(name)
                stage = self.inspect()
                self.assertEqual(set(stage['retirements']),
                                 {'executor-1-retirement.json', 'executor-2-retirement.json', name})
                self.assertTrue(stage['checks']['all_namespace_retirements_observed'])
                (self.root / name).unlink()

    def test_legacy_only_stage_is_byte_value_equivalent_to_original_upgrade(self):
        self.put('codehost-1-retirement.json')
        prior = assess.upgrade_stage(self.root, assess.original_inspect_stage(self.root))
        self.assertEqual(self.inspect(), prior)

    def test_versioned_addition_changes_only_inventory_and_namespace_check(self):
        self.put('codehost-owner-retirement-v3.json')
        prior = assess.upgrade_stage(self.root, assess.original_inspect_stage(self.root))
        actual = self.inspect()
        self.assertFalse(prior['checks']['all_namespace_retirements_observed'])
        self.assertTrue(actual['checks']['all_namespace_retirements_observed'])
        actual['checks']['all_namespace_retirements_observed'] = prior['checks']['all_namespace_retirements_observed']
        actual['retirements'].pop('codehost-owner-retirement-v3.json')
        self.assertEqual(actual, prior)

    def test_missing_host_and_unknown_version_do_not_complete_inventory(self):
        self.assertFalse(self.inspect()['checks']['all_namespace_retirements_observed'])
        self.put('codehost-owner-retirement-v4.json')
        stage = self.inspect()
        self.assertFalse(stage['checks']['all_namespace_retirements_observed'])
        self.assertNotIn('codehost-owner-retirement-v4.json', stage['retirements'])

    def test_every_unchanged_retirement_predicate_still_rejects(self):
        changes = [{'qualified': False}, {'retired': False}, {'namespace_evidence_available': False},
                   {'namespace_ids': []}, {'namespace_members': [{'pid': 9}]}, {'outer_same_process': True}]
        for change in changes:
            with self.subTest(change=change):
                self.put('codehost-owner-retirement-v3.json', **change)
                stage = self.inspect()
                self.assertIn('codehost-owner-retirement-v3.json', stage['retirements'])
                self.assertFalse(stage['checks']['all_namespace_retirements_observed'])

    def test_malformed_versioned_json_is_not_ignored_even_with_valid_legacy_host(self):
        self.put('codehost-1-retirement.json')
        (self.root / 'codehost-owner-retirement-v3.json').write_text('{', encoding='utf-8')
        with self.assertRaises(json.JSONDecodeError):
            self.inspect()

    def test_missing_observations_and_unknown_record_do_not_pass(self):
        for record in ({}, {'qualified': True}, {'qualified': True, 'observations': []}):
            with self.subTest(record=record):
                write_json(self.root / 'codehost-owner-retirement-v3.json', record)
                self.assertFalse(self.inspect()['checks']['all_namespace_retirements_observed'])

    def test_insufficient_inventory_stays_false(self):
        self.put('codehost-owner-retirement-v3.json')
        (self.root / 'executor-2-retirement.json').unlink()
        self.assertFalse(self.inspect()['checks']['all_namespace_retirements_observed'])

    def test_bad_extra_legacy_receipt_is_not_replaced_by_good_versioned_receipt(self):
        self.put('codehost-owner-retirement-v3.json')
        self.put('codehost-1-retirement.json', namespace_members=[{'pid': 99}])
        stage = self.inspect()
        self.assertEqual(len(stage['retirements']), 4)
        self.assertFalse(stage['checks']['all_namespace_retirements_observed'])

    def test_actual_inventory_feeds_unchanged_honest_terminal_closure(self):
        self.put('codehost-owner-retirement-v3.json')
        host, registry, history, _, sequence = fixture(terminal_closure=True)
        outcome = assess.classify_outcome(host, registry, history)
        lifecycle = assess.lifecycle_disposition(self.inspect(), sequence, host, history, outcome)
        self.assertEqual(lifecycle['branch'], 'successful_terminal_host_closure')
        self.assertFalse(lifecycle['explicit_retirement_receipt_observed'])
        self.assertFalse(lifecycle['late_old_token_http403_observed'])
        self.assertEqual(set(lifecycle['missing_receipts']), {'explicit_retirement', 'late_old_token_http403'})
        self.put('codehost-owner-retirement-v3.json', qualified=False)
        self.assertFalse(assess.lifecycle_disposition(self.inspect(), sequence, host, history, outcome)['valid'])


def timing_fixture(root, samples=None):
    samples = samples if samples is not None else [(0., 0.), (.5, .5), (1., 1.), (1.5, 1.5), (2., 2.)]
    source = assess.REPO / assess.TIMING_SOURCE
    raw = source.read_bytes()
    text = raw.decode('utf-8')
    node = next(node for node in ast.parse(text).body if isinstance(node, ast.ClassDef) and node.name == 'TimingMonitor')
    source_record = {'path': assess.TIMING_SOURCE, 'file_sha256': assess.sha(raw),
                     'class_sha256': assess.sha(ast.get_source_segment(text, node).encode())}
    frozen = {'sources': {assess.TIMING_SOURCE: {'sha256': assess.sha(raw), 'bytes': len(raw)}}}
    monitor_type, _ = assess.timing_monitor(frozen, source_record)
    monitor = monitor_type()
    for wall, sim in samples:
        monitor.observe(wall, sim)
    report = monitor.report()
    raw_samples = b''.join(struct.pack('<dd', *sample) for sample in samples)
    (root / 'timing-samples.bin').write_bytes(raw_samples)
    origin = {'monotonic_s': 200., 'initial_sim_s': 2.,
              'clock': {'implementation': 'synthetic monotonic clock', 'monotonic': True,
                        'adjustable': False, 'resolution': 1e-7}}
    scheduling = {'schema': 'rci-windows-scheduling-1', 'platform': 'win32',
                  'requested_priority': 'ABOVE_NORMAL_PRIORITY_CLASS', 'timer_period_ms': 1,
                  'applied': True, 'restored': True, 'observed_priority_class': 0x8000,
                  'previous_priority_class': 0x20, 'restored_priority_class': 0x20,
                  'time_begin_period_status': 0, 'time_end_period_status': 0, 'restore_errors': []}
    metadata = {'schema': 'rci-prospective-timing-2', 'sample_file': 'timing-samples.bin',
                'sha256': assess.sha(raw_samples), 'byte_count': len(raw_samples), 'sample_count': len(samples),
                'loop_origin': origin, 'monitor_source': source_record, 'report': report, 'scheduling': scheduling,
                'terminal': {'wall_elapsed_s': samples[-1][0], 'sim_elapsed_s': samples[-1][1], 'reason': 'task_success'}}
    host = {'terminal': 'task_success', 'scheduling': scheduling,
            'timing': {'maximum_wall_minus_sim_s': report['maximum_lag_s'],
                                                  'samples': len(samples)},
            'timing_v2': {'schema': metadata['schema'], 'metadata_file': 'timing-v2.json',
                          'sample_file': 'timing-samples.bin', 'sample_sha256': metadata['sha256'],
                          'sample_count': len(samples), 'passed': report['actual_host_timing_pass'],
                          'loop_origin': origin, 'scheduling': scheduling}}
    resources, resource_host, resource_sources = resource_fixture(root, origin['monotonic_s'], samples[-1][0])
    metadata.update(resources)
    host.update(resource_host)
    frozen['sources'].update(resource_sources)
    write_timing_metadata(root, metadata, host)
    return host, metadata, frozen


def write_timing_metadata(root, metadata, host):
    write_json(root / 'timing-v2.json', metadata)
    host['timing_v2']['metadata_sha256'] = assess.hash_file(root / 'timing-v2.json')


def transport_fixture(root):
    host, registry, history, _, _ = fixture()
    request = {'request_id': 'h1', 'authority_epoch': 3}
    body = {'ok': True, 'owner': 'conventional', 'authority_epoch': 4,
            'command': {'request_id': 'h1', 'kind': 'handback', 'phase': 'terminal', 'status': 'completed'}}
    requests = [{'trace_id': 't1', 'received_wall_unix_s': 9., 'method': 'POST', 'path': '/handback',
                 'request_id': 'h1', 'request': json.dumps(request)},
                {'trace_id': 't2', 'received_wall_unix_s': 12., 'method': 'POST', 'path': '/continuity',
                 'request_id': None, 'request': '{}'}]
    events = [{**requests[0], 'wall_unix_s': 11., 'origin': 'protected_host', 'status': 200, 'response': body},
              {**requests[1], 'wall_unix_s': 13., 'origin': 'local_revocation_fence', 'status': 403,
               'response': {'ok': False, 'error': {'code': 'invocation_capability_denied'}}}]
    revocation = {'wall_unix_s': 10., 'reason': 'accepted_handback', 'source': 'broker', 'trace_id': 't1',
                  'method': 'POST', 'path': '/handback', 'status': 200, 'pinned_authority_epoch': 3, 'response': body}
    write_jsonl(root / 'broker-requests.jsonl', requests)
    write_jsonl(root / 'broker-events.jsonl', events)
    write_json(root / 'authority-revocation.json', revocation)
    return registry, history, requests, events, revocation


class TimingTests(unittest.TestCase):
    def setUp(self):
        # These synthetic cases isolate clock/scheduling/resource replay. The
        # complete new owner, recorder and dispatch gate has dedicated tests in
        # test_continuous_integrity and physical qualification integration.
        continuous = patch.object(assess, 'verify_continuous_physics',
                                  return_value={'applicable': False, 'passed': True})
        continuous.start()
        self.addCleanup(continuous.stop)
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.host, self.metadata, self.frozen = timing_fixture(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def verify(self):
        return assess.verify_timing(self.root, self.host, self.frozen)

    def test_exact_retained_samples_replay(self):
        result = self.verify()
        self.assertTrue(result['passed'])
        self.assertEqual(result['sample_count'], 5)
        self.assertEqual(result['replayed_timing']['complete_wall_windows'], 2)
        self.assertNotIn('continuous_physics_integrity', result)

    def test_continuous_integrity_failure_blocks_otherwise_valid_timing(self):
        with patch.object(assess, 'verify_continuous_physics', side_effect=ValueError('owner evidence incomplete')):
            with self.assertRaisesRegex(ValueError, 'owner evidence incomplete'):
                self.verify()

    def test_current_host_writer_matches_independent_reader(self):
        spec = importlib.util.spec_from_file_location('campaign002_timing_writer', assess.CAMPAIGN / 'harness/timing.py')
        writer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(writer)
        clock = [100.]
        capture = writer.TimingCapture(100., 50., max_samples=10, clock=lambda: clock[0])
        clock[0] = 101.
        capture.sample(51.)
        clock[0] = 102.
        capture.finish(52., 'task_success')
        directory = self.root / 'writer'
        directory.mkdir()
        scheduling = self.metadata['scheduling']
        binding = capture.persist(directory, scheduling)
        host = {'terminal': 'task_success', 'timing_v2': binding, 'scheduling': scheduling,
                'timing': {'maximum_wall_minus_sim_s': capture.monitor.maximum_lag, 'samples': capture.sample_count}}
        resources, resource_host, sources = resource_fixture(directory, 100., 2.)
        metadata = json.loads((directory / 'timing-v2.json').read_bytes())
        metadata.update(resources); host.update(resource_host); self.frozen['sources'].update(sources)
        write_timing_metadata(directory, metadata, host)
        self.assertTrue(assess.verify_timing(directory, host, self.frozen)['passed'])

    def test_binary_corruption_fails_hash(self):
        path = self.root / 'timing-samples.bin'
        raw = bytearray(path.read_bytes()); raw[-1] ^= 1; path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.verify()

    def test_truncated_samples_fail_count(self):
        path = self.root / 'timing-samples.bin'
        path.write_bytes(path.read_bytes()[:-1])
        with self.assertRaisesRegex(ValueError, 'length/count'):
            self.verify()

    def test_rehashed_nonfinite_sample_still_fails(self):
        path = self.root / 'timing-samples.bin'
        raw = path.read_bytes()[:16] + struct.pack('<dd', float('nan'), .5) + path.read_bytes()[32:]
        path.write_bytes(raw); self.metadata['sha256'] = assess.sha(raw)
        write_timing_metadata(self.root, self.metadata, self.host)
        with self.assertRaisesRegex(ValueError, 'Non-finite'):
            self.verify()

    def test_rehashed_backwards_sample_still_fails(self):
        path = self.root / 'timing-samples.bin'
        raw = path.read_bytes()[:32] + struct.pack('<dd', .25, 1.) + path.read_bytes()[48:]
        path.write_bytes(raw); self.metadata['sha256'] = assess.sha(raw)
        write_timing_metadata(self.root, self.metadata, self.host)
        with self.assertRaisesRegex(ValueError, 'backwards'):
            self.verify()

    def test_matching_metadata_cannot_hide_wrong_terminal(self):
        self.metadata['terminal']['reason'] = 'operator_stop'
        write_timing_metadata(self.root, self.metadata, self.host)
        with self.assertRaisesRegex(ValueError, 'terminal'):
            self.verify()

    def test_modified_report_fails_independent_replay(self):
        self.metadata['report']['maximum_lag_s'] = .01
        write_timing_metadata(self.root, self.metadata, self.host)
        with self.assertRaisesRegex(ValueError, 'independent replay'):
            self.verify()

    def test_host_common_origin_must_equal_sample_origin(self):
        self.host['timing_v2']['loop_origin'] = copy.deepcopy(self.metadata['loop_origin'])
        self.host['timing_v2']['loop_origin']['monotonic_s'] += 1
        with self.assertRaisesRegex(ValueError, 'common loop origin'):
            self.verify()

    def test_monitor_source_must_match_frozen_hash(self):
        self.frozen['sources'][assess.TIMING_SOURCE]['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'frozen bytes'):
            self.verify()

    def test_scheduling_policy_failure_is_not_a_timing_pass(self):
        self.metadata['scheduling']['observed_priority_class'] = 0x20
        write_timing_metadata(self.root, self.metadata, self.host)
        result = self.verify()
        self.assertTrue(result['replayed_timing']['actual_host_timing_pass'])
        self.assertFalse(result['scheduling_pass'])
        self.assertFalse(result['passed'])

    def test_failed_scheduling_restore_is_not_a_timing_pass(self):
        self.metadata['scheduling']['restored'] = False
        self.host['timing_v2']['passed'] = False
        write_timing_metadata(self.root, self.metadata, self.host)
        self.assertFalse(self.verify()['passed'])

    def test_monitor_class_source_cannot_be_substituted(self):
        self.metadata['monitor_source']['class_sha256'] = '0' * 64
        write_timing_metadata(self.root, self.metadata, self.host)
        with self.assertRaisesRegex(ValueError, 'class hash'):
            self.verify()

    def test_strict_lag_failure_stays_failure_after_replay(self):
        self.host, self.metadata, self.frozen = timing_fixture(
            self.root, [(0., 0.), (.1, 0.), (1., 1.), (2., 2.)])
        self.assertFalse(self.verify()['passed'])
        self.assertEqual(self.verify()['replayed_timing']['maximum_lag_s'], .1)

    def test_rtf_failure_stays_failure_after_replay(self):
        self.host, self.metadata, self.frozen = timing_fixture(self.root, [(0., 0.), (1., 1.1), (2., 2.2)])
        self.assertFalse(self.verify()['passed'])

    def test_no_complete_wall_window_is_not_a_pass(self):
        self.host, self.metadata, self.frozen = timing_fixture(self.root, [(0., 0.), (.2, .2)])
        self.assertFalse(self.verify()['passed'])


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.registry, self.history, self.requests, self.events, self.revocation = transport_fixture(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def verify(self):
        return assess.verify_transport(self.root, self.registry, self.history)

    def test_late_local_continuity_denial_keeps_provenance(self):
        result = self.verify()
        self.assertTrue(result['passed'])
        self.assertEqual(result['local_denial_count'], 1)

    def test_local_success_cannot_become_a_continuity_receipt(self):
        self.events[1].update(status=200, response={'ok': True})
        write_jsonl(self.root / 'broker-events.jsonl', self.events)
        with self.assertRaisesRegex(ValueError, 'never successful host evidence'):
            self.verify()

    def test_local_reply_cannot_establish_revocation(self):
        self.events[0]['origin'] = 'local_capability_fence'
        write_jsonl(self.root / 'broker-events.jsonl', self.events)
        with self.assertRaisesRegex(ValueError, 'protected host reply'):
            self.verify()

    def test_missing_protected_transfer_is_not_accepted_handback(self):
        self.history = [event for event in self.history if event.get('type') != 'control_owner_changed']
        with self.assertRaisesRegex(ValueError, 'registry/owner-transfer'):
            self.verify()

    def test_late_forwarding_fails(self):
        self.events[1]['origin'] = 'protected_host'
        write_jsonl(self.root / 'broker-events.jsonl', self.events)
        with self.assertRaisesRegex(ValueError, 'forwarded a new request'):
            self.verify()

    def test_request_without_reply_is_unknown_transport(self):
        write_jsonl(self.root / 'broker-events.jsonl', self.events[:1])
        with self.assertRaisesRegex(ValueError, 'counts differ'):
            self.verify()

    def test_abort_failure_record_is_not_suppressed(self):
        write_json(self.root / 'broker-failure.json', {'type': 'TimeoutError'})
        with self.assertRaisesRegex(ValueError, 'Unresolved transport failure'):
            self.verify()

    def test_nonfatal_mirror_exception_requires_prior_host_revocation(self):
        closure = {'authority_revocation_established': True, 'method': 'GET', 'path': '/status',
                   'phase': 'upstream_request', 'type': 'URLError', 'wall_unix_s': 12.}
        write_json(self.root / 'mirror-after-revocation.json', closure)
        self.assertTrue(self.verify()['passed'])
        closure['wall_unix_s'] = 8.
        write_json(self.root / 'mirror-after-revocation.json', closure)
        with self.assertRaisesRegex(ValueError, 'Nonfatal mirror closure'):
            self.verify()

    def epoch_fixture(self):
        body={'ok':False,'error':{'code':'stale_authentication','message':'Old generation'}}
        raw=json.dumps(body,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        self.mirror_request={'schema':'campaign002-mirror-request-1','request_id':'a'*32,
            'method':'GET','path':'/status','origin':'protected_host','pinned_invocation_id':'interrupt-a',
            'pinned_authority_epoch':3,'initial_state_sha256':'b'*64,'request_wall_unix_s':9.}
        self.mirror_reply={**self.mirror_request,'schema':'campaign002-mirror-reply-1',
            'response_wall_unix_s':10.5,'status':409,'response_bytes':len(raw),
            'response_sha256':assess.sha(raw),'response_retained':True,'response':body}
        self.revocation={'wall_unix_s':11.,'reason':'host_epoch_denied','source':'public_mirror',
            'trace_id':None,'method':'GET','path':'/status','status':409,'pinned_authority_epoch':3,
            'response':body,'mirror_context':self.mirror_reply}
        invocation={'invocation_id':'interrupt-a','authority_epoch':3,'state':'active'}
        transition={'authority_epoch':4,'owner':'robot','active_command':None,
                    'invocation':{**invocation,'state':'retired'}}
        self.history=[{'event_id':1,'type':'invocation_start-invocation','wall_unix_s':1.,
                       'authority_epoch':3,'payload':{'authority_epoch':3,'invocation':invocation}},
                      {'event_id':2,'type':'invocation_retire-invocation','wall_unix_s':10.,
                       'authority_epoch':4,'payload':{'request_id':'retire-a',**transition}}]
        self.registry={'retire-a':{'actor':'operator','kind':'retire-invocation','phase':'terminal',
            'status':'completed','request_id':'retire-a','transition':transition,
            'envelope':{'authority_epoch':3,'invocation_id':'interrupt-a'}}}
        write_json(self.root/'stage-result.json',{'invocation_id':'interrupt-a'})
        write_json(self.root/'runtime-input-hashes.json',{'live/state.json':'b'*64})
        self.write_epoch()

    def write_epoch(self):
        write_jsonl(self.root/'mirror-requests.jsonl',[self.mirror_request])
        write_jsonl(self.root/'mirror-replies.jsonl',[self.mirror_reply])
        write_json(self.root/'authority-revocation.json',self.revocation)

    def test_source_bound_409_proves_only_loss_of_pinned_authority(self):
        self.epoch_fixture()
        result=self.verify()
        self.assertTrue(result['passed'])
        proof=result['mirror_epoch_denial']
        self.assertEqual(proof['retirement_event_id'],2)
        self.assertEqual(proof['invocation_id'],'interrupt-a')
        self.assertIn('no successful operation',proof['scope'])

    def test_generic_or_untyped_409_and_wrong_codes_remain_rejected(self):
        for status,code in [(409.,'stale_authentication'),(True,'stale_authentication'),
                            (400,'stale_authentication'),(429,'stale_authentication'),
                            (504,'stale_authentication'),(409,'invalid_action'),
                            (409,'unsupported_resumption')]:
            with self.subTest(status=status,code=code):
                self.epoch_fixture();self.mirror_reply['status']=status;self.revocation['status']=status
                body={'ok':False,'error':{'code':code}}
                raw=json.dumps(body,sort_keys=True,separators=(',',':')).encode()
                self.mirror_reply.update(response=body,response_bytes=len(raw),response_sha256=assess.sha(raw))
                self.revocation['response']=body;self.write_epoch()
                with self.assertRaises(ValueError):self.verify()

    def test_request_reply_latch_order_and_transition_window_are_strict(self):
        changes=[('request_wall_unix_s',10.25),('request_wall_unix_s',.5),
                 ('response_wall_unix_s',9.5),('response_wall_unix_s',12.),
                 ('response_wall_unix_s',float('nan'))]
        for field,value in changes:
            with self.subTest(field=field,value=value):
                self.epoch_fixture();self.mirror_reply[field]=value
                if field in self.mirror_request:self.mirror_request[field]=value
                if not assess.finite(value):
                    # Deliberately malformed raw evidence bypasses the normal fixture writer.
                    (self.root/'mirror-replies.jsonl').write_text(json.dumps(self.mirror_reply)+'\n')
                    (self.root/'authority-revocation.json').write_text(json.dumps(self.revocation))
                else:self.write_epoch()
                with self.assertRaises(ValueError):self.verify()

    def test_missing_ambiguous_or_mismatched_protected_transition_fails(self):
        for mutation in ['missing','duplicate','wrong_id','wrong_epoch','wrong_state','bad_registry']:
            with self.subTest(mutation=mutation):
                self.epoch_fixture()
                if mutation=='missing':self.history.pop()
                if mutation=='duplicate':self.history.append(copy.deepcopy(self.history[-1]))
                if mutation=='wrong_id':self.history[-1]['payload']['invocation']['invocation_id']='another'
                if mutation=='wrong_epoch':self.history[-1]['authority_epoch']=5
                if mutation=='wrong_state':self.history[-1]['payload']['invocation']['state']='active'
                if mutation=='bad_registry':self.registry['retire-a']['status']='rejected'
                with self.assertRaises(ValueError):self.verify()

    def test_wrong_stage_invocation_initial_hash_or_pin_cannot_be_substituted(self):
        for mutation in ['stage','initial','pin','boolean_epoch','missing_epoch']:
            with self.subTest(mutation=mutation):
                self.epoch_fixture()
                if mutation=='stage':write_json(self.root/'stage-result.json',{'invocation_id':'other'})
                if mutation=='initial':write_json(self.root/'runtime-input-hashes.json',{'live/state.json':'c'*64})
                if mutation=='pin':
                    self.mirror_request['pinned_invocation_id']='other';self.mirror_reply['pinned_invocation_id']='other'
                if mutation in ['boolean_epoch','missing_epoch']:
                    value=True if mutation=='boolean_epoch' else None
                    self.mirror_request['pinned_authority_epoch']=value
                    self.mirror_reply['pinned_authority_epoch']=value
                    self.revocation['pinned_authority_epoch']=value
                self.write_epoch()
                with self.assertRaises(ValueError):self.verify()

    def test_reply_context_hash_identity_and_origin_tampering_fail(self):
        for mutation in ['hash','bytes','body','request_id','origin','missing_context','unretained']:
            with self.subTest(mutation=mutation):
                self.epoch_fixture()
                if mutation=='hash':self.mirror_reply['response_sha256']='0'*64
                if mutation=='bytes':self.mirror_reply['response_bytes']+=1
                if mutation=='body':self.mirror_reply['response']['error']['code']='other'
                if mutation=='request_id':self.mirror_reply['request_id']='c'*32
                if mutation=='origin':self.mirror_reply['origin']='local_revocation_fence'
                if mutation=='missing_context':self.revocation.pop('mirror_context')
                if mutation=='unretained':self.mirror_reply.update(response_retained=False,response=None)
                self.write_epoch()
                with self.assertRaises(ValueError):self.verify()

    def test_missing_duplicate_or_truncated_mirror_records_fail(self):
        for mutation in ['missing','duplicate','truncated','duplicate_field']:
            with self.subTest(mutation=mutation):
                self.epoch_fixture();path=self.root/'mirror-replies.jsonl'
                if mutation=='missing':path.unlink()
                if mutation=='duplicate':write_jsonl(path,[self.mirror_reply,self.mirror_reply])
                if mutation=='truncated':path.write_bytes(path.read_bytes().rstrip(b'\n'))
                if mutation=='duplicate_field':path.write_text(path.read_text().replace('{','{"status":200,',1))
                with self.assertRaises(ValueError):self.verify()

    def test_new_requests_after_epoch_latch_and_old_mirror_errors_still_fail(self):
        self.epoch_fixture()
        request={**self.mirror_request,'request_id':'c'*32,'request_wall_unix_s':12.}
        reply={**self.mirror_reply,**request,'schema':'campaign002-mirror-reply-1','response_wall_unix_s':13.}
        write_jsonl(self.root/'mirror-requests.jsonl',[self.mirror_request,request])
        write_jsonl(self.root/'mirror-replies.jsonl',[self.mirror_reply,reply])
        with self.assertRaises(ValueError):self.verify()
        self.write_epoch();write_json(self.root/'mirror-error.json',{'phase':'reply_validation'})
        with self.assertRaisesRegex(ValueError,'Unresolved transport failure'):self.verify()

    def test_earlier_failed_response_cannot_be_laundered_by_later_valid_denial(self):
        self.epoch_fixture()
        request={**self.mirror_request,'request_id':'c'*32,'request_wall_unix_s':8.}
        reply={**self.mirror_reply,**request,'schema':'campaign002-mirror-reply-1',
               'response_wall_unix_s':8.5,'status':429}
        write_jsonl(self.root/'mirror-requests.jsonl',[request,self.mirror_request])
        write_jsonl(self.root/'mirror-replies.jsonl',[reply,self.mirror_reply])
        with self.assertRaisesRegex(ValueError,'Earlier mirror reply'):self.verify()


class FrozenBindingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def queue(self):
        interpreter = str(assess.REPO / 'venv/Scripts/python.exe')
        return {'state': 'succeeded', 'exit_status': 0, 'id': 'job', 'cwd': str(assess.REPO),
                'resolved_executable': interpreter,
                'argv': [interpreter, '-X', 'utf8', '-B', str(assess.LAUNCHER),
                         '--manifest', str(self.root / 'manifest.json'), '--evidence', str(self.root / 'e'),
                         '--host-evidence', str(self.root / 'h'), '--workspace', str(self.root / 'w'), '--mode', 'pilot']}

    def invoke(self, manifest_hash):
        return assess.assess(self.root / 'manifest.json', self.root / 'e', self.root / 'h',
                             self.root / 'queue.json', self.root / 'snapshot.json', manifest_hash,
                             'job', expected_workspace=self.root / 'w', expected_revision='new-revision')

    def test_wrong_launcher_fails_before_manifest_or_outcome_reads(self):
        job = self.queue(); job['argv'][4] = str(assess.INTEGRATION / 'readiness-session-10/orchestrator/physical.py')
        with patch.object(assess, 'read_json', return_value=job) as reader, patch.object(assess, 'inspect_stage') as stage:
            with self.assertRaisesRegex(ValueError, 'exact Campaign 002 direct launcher'):
                self.invoke('0' * 64)
            reader.assert_called_once_with(self.root / 'queue.json')
            stage.assert_not_called()

    def test_manifest_bytes_fail_before_outcome_reads(self):
        write_json(self.root / 'manifest.json', {'framework_revision': 'new-revision'})
        with patch.object(assess, 'read_json', return_value=self.queue()), patch.object(assess, 'inspect_stage') as stage:
            with self.assertRaisesRegex(ValueError, 'predeclared SHA256'):
                self.invoke('0' * 64)
            stage.assert_not_called()

    def test_manifest_revision_fails_before_outcome_reads(self):
        write_json(self.root / 'manifest.json', {'framework_revision': 'old-revision'})
        digest = assess.hash_file(self.root / 'manifest.json')
        with patch.object(assess, 'read_json', side_effect=[self.queue(), {}]), patch.object(assess, 'inspect_stage') as stage:
            with self.assertRaisesRegex(ValueError, 'Manifest framework revision'):
                self.invoke(digest)
            stage.assert_not_called()

    def test_source_or_revision_integrity_fails_before_outcome_reads(self):
        write_json(self.root / 'manifest.json', {'framework_revision': 'new-revision'})
        digest = assess.hash_file(self.root / 'manifest.json')
        with patch.object(assess, 'read_json', side_effect=[self.queue(), {}]), \
                patch.object(assess, 'frozen_problems', return_value=['Changed source']), \
                patch.object(assess, 'inspect_stage') as stage:
            with self.assertRaisesRegex(ValueError, 'Frozen source/archive/revision integrity'):
                self.invoke(digest)
            stage.assert_not_called()

    def test_archive_and_live_source_hashes_must_match(self):
        source = assess.TIMING_SOURCE
        raw = (assess.REPO / source).read_bytes()
        frozen = {'revision': 'new-revision', 'sources': {source: {'sha256': assess.sha(raw), 'bytes': len(raw)}}}
        with zipfile.ZipFile(self.root / 'code.zip', 'w') as archive:
            archive.writestr(source, raw)
        problems = assess.frozen_problems(self.root / 'snapshot.json', frozen, 'old-revision')
        self.assertIn('Wrong frozen framework revision', problems)
        self.assertTrue(any('Required source absent' in problem for problem in problems))
        self.assertIn('Required source absent from frozen inventory: ' +
                      (assess.HERE/'canary_readback_proof.py').relative_to(assess.REPO).as_posix(), problems)
        frozen['sources'][source]['sha256'] = '0' * 64
        problems = assess.frozen_problems(self.root / 'snapshot.json', frozen, 'new-revision')
        self.assertIn('Changed source: ' + source, problems)

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
