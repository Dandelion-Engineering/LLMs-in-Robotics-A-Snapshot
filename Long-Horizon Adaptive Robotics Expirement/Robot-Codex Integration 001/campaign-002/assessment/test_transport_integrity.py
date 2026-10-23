"""Adversarial retained-receipt tests, with no model, socket or physics process."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import transport_integrity as subject


def raw_json(value):
    return json.dumps(value, indent=2).encode() + b'\n'


class Fixture:
    def __init__(self, root):
        self.repo, self.stage = root / 'repo', root / 'stage'
        self.stage.mkdir()
        (self.stage / 'client').mkdir()
        self.frozen = {'sources': {}}
        for name in subject.SOURCE_NAMES + (subject.PROBE_SOURCE_NAME,):
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = ('test source: ' + name).encode()
            path.write_bytes(raw)
            self.frozen['sources'][name] = {'sha256': subject.digest(raw), 'bytes': len(raw)}
        self.sources = {name: self.frozen['sources'][name] for name in subject.BRIDGE_SOURCE_NAMES}
        self.client = [
            {'kind': 'stderr', 'schema': 'campaign002-stderr-metadata-1', 'bytes': 12,
             'sha256': 'a' * 64, 'wall_unix_s': 102., 'monotonic_s': 502.,
             'markers': ['grpc'], 'text_retained': False,
             'scope': 'Fixed lexical markers only; no error message or causal diagnosis.'},
            {'kind': 'client_finishing_before_close', 'schema': 'campaign002-client-finishing-1',
             'wall_unix_s': 104., 'monotonic_s': 504.},
            {'kind': 'client_shutdown', 'exit_code': 0},
        ]
        self.namespace = [
            {'kind': 'open'}, {'kind': 'child_started', 'child_pid': 42}, {'kind': 'connected'},
            {'kind': 'child_diagnostic', 'stream': 'stdout', 'bytes': 0,
             'sha256': subject.digest(b''), 'truncated': False},
            {'kind': 'child_diagnostic', 'stream': 'stderr', 'bytes': 0,
             'sha256': subject.digest(b''), 'truncated': False},
            {'kind': 'stdin_eof', 'to_host': 50, 'from_host': 70},
            {'kind': 'channel_end', 'reason': 'stdin_eof', 'stdin_eof': True,
             'child_exit_before_cleanup': None, 'error_type': None, 'to_host': 50, 'from_host': 70},
            {'kind': 'closed', 'qualified': True, 'reason': 'owner_input_eof', 'stdin_eof': True,
             'child_exit_before_cleanup': None, 'child_exit_code': -15, 'terminate_sent': True,
             'kill_sent': False, 'error_type': None, 'to_host': 50, 'from_host': 70,
             'stdin_eof_at_channel_end': True, 'owner_input_wait_bound_s': .5,
             'diagnostic_streams_complete': True},
        ]
        for index, row in enumerate(self.namespace, 1):
            row.update(schema='campaign002-codehost-namespace-2', sequence=index,
                       wall_unix_s=100. + index, monotonic_s=1000. + index)
        self.retirement = {
            'qualified': True, 'normal_wait_timed_out': False,
            'windows_wrapper_killed_after_linux_retired': False, 'windows_exit_code': 0,
            'observations': [{'retired': True, 'namespace_evidence_available': True,
                              'outer_same_process': False, 'namespace_members': [],
                              'namespace_ids': [1234]}],
        }
        self.rows = [
            {'kind': 'open', 'sources': self.sources, 'max_connections': 16,
             'max_ledger_bytes': 1024 * 1024, 'max_stderr_bytes': 1024 * 1024},
            {'kind': 'listening'}, {'kind': 'connection_accepted', 'connection_id': 1},
            {'kind': 'child_started', 'connection_id': 1},
            {'kind': 'pump_end', 'connection_id': 1, 'pump': 'upload', 'reason': 'eof',
             'client_finishing': True, 'exception_type': None},
            {'kind': 'pump_end', 'connection_id': 1, 'pump': 'download', 'reason': 'cancelled',
             'client_finishing': True, 'exception_type': None},
            {'kind': 'retirement_started', 'connection_id': 1,
             'client_finishing': True, 'exit_code_before': None},
            {'kind': 'connection_closed', 'connection_id': 1, 'qualified': True},
            {'kind': 'closed', 'failures': [], 'accepted': 1, 'denied': 0},
        ]
        for index, row in enumerate(self.rows):
            row.update(wall_unix_s=100. + index * 2, monotonic_s=500. + index * 2)
        self.receipt = {'schema': 'campaign002-codehost-bridge-2', 'connection_id': 1,
                        'qualified': True, 'sources': self.sources, 'to_host': 50, 'from_host': 70,
                        'client_finishing_at_first_end': True, 'pump_errors': [], 'exit_code': 0,
                        'expected_client_shutdown_resets': 0}
        self.stderr_overrides = {}
        self.align_first = self.align_namespace = True

    def bind(self, name, raw):
        (self.stage / name).write_bytes(raw)
        return {'path': name, 'sha256': subject.digest(raw), 'bytes': len(raw)}

    def seal(self):
        previous = None
        for index, row in enumerate(self.rows, 1):
            row.pop('record_sha256', None)
            row.update(schema=subject.TRANSPORT_SCHEMA, sequence=index, previous_sha256=previous)
            row['record_sha256'] = subject.digest(subject.canonical(row))
            previous = row['record_sha256']

    def write(self):
        self.bind('client/events.jsonl', b''.join(subject.canonical(row) + b'\n' for row in self.client))
        stderr = b''.join(
            b'RCI_CODEHOST_V2 ' + subject.canonical(row) + b'\n' for row in self.namespace)
        bound = self.bind('codehost-1-stderr.txt', stderr)
        self.receipt['stderr'] = {**bound, 'raw_bytes': len(stderr), 'raw_sha256': subject.digest(stderr),
                                  'truncated': False, 'redacted': False, **self.stderr_overrides}
        self.receipt['retirement'] = self.bind('codehost-1-retirement.json', raw_json(self.retirement))
        if self.align_namespace:
            self.receipt['namespace_records'] = copy.deepcopy(self.namespace)
            self.receipt['namespace_record_count'] = len(self.namespace)
        self.seal()
        if self.align_first:
            self.receipt['first_pump_end'] = copy.deepcopy(self.rows[4])
        self.rows[7]['receipt'] = self.bind('codehost-1-bridge.json', raw_json(self.receipt))
        self.seal()
        self.bind('codehost-transport-v2.jsonl', b''.join(subject.canonical(row) + b'\n' for row in self.rows))


class TransportIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.f = Fixture(Path(self.temp.name))
        self.repo = patch.object(subject, 'REPO', self.f.repo)
        self.repo.start()
        self.addCleanup(self.repo.stop)

    def verify(self, **kwargs):
        return subject.verify_transport_integrity(self.f.stage, self.f.frozen, **kwargs)

    def fails(self, phrase):
        self.f.write()
        with self.assertRaisesRegex(ValueError, phrase):
            self.verify()

    def test_complete_owner_close_with_deliberate_sigterm(self):
        self.f.write()
        result = self.verify()
        self.assertTrue(result['passed'])
        self.assertEqual(result['namespace']['child_exit_code'], -15)
        self.assertEqual(result['connection_count'], 1)

    def test_owner_reset_after_finishing_is_explicitly_counted(self):
        self.f.rows[4].update(reason='error', exception_type='ConnectionResetError')
        self.f.receipt['expected_client_shutdown_resets'] = 1
        self.f.write()
        self.assertEqual(self.verify()['expected_client_shutdown_resets'], 1)

    def test_natural_zero_child_exit_after_owner_eof(self):
        self.f.namespace[-2]['child_exit_before_cleanup'] = 0
        self.f.namespace[-1].update(child_exit_before_cleanup=0, child_exit_code=0, terminate_sent=False)
        self.f.write()
        self.assertTrue(self.verify()['passed'])

    def test_missing_v2_receipt_cannot_use_legacy_success_summary(self):
        self.f.write()
        (self.f.stage / 'codehost-transport-v2.jsonl').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing ordinary transport file'):
            self.verify()

    def test_truncated_transport_tail(self):
        self.f.write()
        path = self.f.stage / 'codehost-transport-v2.jsonl'
        path.write_bytes(path.read_bytes()[:-1])
        with self.assertRaisesRegex(ValueError, 'truncated transport stream'):
            self.verify()

    def test_ledger_content_edit_without_rehash(self):
        self.f.write()
        path = self.f.stage / 'codehost-transport-v2.jsonl'
        path.write_bytes(path.read_bytes().replace(b'"pump":"upload"', b'"pump":"download"', 1))
        with self.assertRaisesRegex(ValueError, 'ledger hash differs'):
            self.verify()

    def test_clean_eof_before_owner_cannot_be_repaired_by_later_final_flag(self):
        self.f.rows[4]['client_finishing'] = False
        self.f.receipt['client_finishing_at_first_end'] = True
        self.fails('Unexpected transport pump')

    def test_late_owner_marker_rejected_even_when_all_final_flags_true(self):
        self.f.client[-2].update(wall_unix_s=109., monotonic_s=509.)
        self.fails('Owner finishing was absent or recorded after')

    def test_missing_owner_receipt(self):
        self.f.client.pop(-2)
        self.fails('unique owner-finishing')

    def test_owner_marker_boolean_clock_is_not_a_timestamp(self):
        self.f.client[-2]['monotonic_s'] = True
        self.fails('Owner-finishing receipt malformed')

    def test_unexpected_clean_namespace_eof_rejected(self):
        self.f.namespace[-2]['reason'] = 'unexpected_channel_eof'
        self.f.namespace[-1]['reason'] = 'unexpected_channel_eof'
        self.fails('Namespace ended before owner input EOF')

    def test_masked_nonzero_native_child_fails_despite_wrapper_zero(self):
        self.f.namespace[-2]['child_exit_before_cleanup'] = 17
        self.f.namespace[-1].update(child_exit_before_cleanup=17, child_exit_code=17)
        self.fails('native child failure')

    def test_boolean_child_exit_not_zero(self):
        self.f.namespace[-1]['child_exit_code'] = False
        self.fails('Namespace native child exit')

    def test_missing_native_precleanup_status_not_null(self):
        del self.f.namespace[-2]['child_exit_before_cleanup']
        self.fails('Namespace ended before owner input EOF')

    def test_killed_native_child_fails(self):
        self.f.namespace[-1]['kill_sent'] = True
        self.fails('Namespace native child exit')

    def test_namespace_missing_stdin_eof_even_if_closed_claims_success(self):
        self.f.namespace = [row for row in self.f.namespace if row['kind'] != 'stdin_eof']
        self.fails('Namespace lifecycle')

    def test_channel_eof_after_owner_marker_can_precede_bounded_stdin_handoff(self):
        self.f.namespace[5], self.f.namespace[6] = self.f.namespace[6], self.f.namespace[5]
        self.f.namespace[5].update(reason='channel_eof', stdin_eof=False)
        self.f.namespace[-1]['stdin_eof_at_channel_end'] = False
        for index, row in enumerate(self.f.namespace, 1):
            row.update(sequence=index, monotonic_s=1000. + index)
        self.f.write()
        self.assertTrue(self.verify()['passed'])

    def test_handoff_without_prospective_bound_rejected(self):
        del self.f.namespace[-1]['owner_input_wait_bound_s']
        self.fails('bounded handoff evidence')

    def test_missing_child_diagnostic_is_not_complete(self):
        self.f.namespace.pop(3)
        self.fails('child diagnostic streams')

    def test_child_diagnostics_cannot_exceed_aggregate_bound(self):
        self.f.namespace[3].update(bytes=700000, sha256='a' * 64)
        self.f.namespace[4].update(bytes=700000, sha256='b' * 64)
        self.fails('child diagnostic streams')

    def test_child_diagnostics_truncation_fails(self):
        self.f.namespace[3]['truncated'] = True
        self.fails('child diagnostic streams')

    def test_child_streams_must_be_distinct(self):
        self.f.namespace[3]['stream'] = 'stderr'
        self.fails('child diagnostic streams')

    def test_child_diagnostic_cannot_smuggle_unframed_text_field(self):
        self.f.namespace[3]['text'] = 'forged status-shaped child data'
        self.fails('child diagnostic streams')

    def test_claimed_diagnostics_complete_without_join_is_rejected(self):
        self.f.namespace[-1]['diagnostic_streams_complete'] = False
        self.fails('bounded handoff evidence')

    def test_probe_owner_requires_real_probe_closed_and_frozen_driver(self):
        self.f.client[-1] = {'kind': 'probe_client_closed', 'schema': 'campaign002-h2-probe-client-1',
                             'closed': True, 'wall_unix_s': 109., 'monotonic_s': 509.}
        self.f.write()
        result = self.verify(owner_kind='transport_probe')
        self.assertEqual(result['owner_kind'], 'transport_probe')
        self.assertIn(subject.PROBE_SOURCE_NAME, result['source_bindings'])
        with self.assertRaisesRegex(ValueError, 'unique owner-finishing'):
            self.verify()
        del self.f.frozen['sources'][subject.PROBE_SOURCE_NAME]
        with self.assertRaisesRegex(ValueError, 'Transport source differs from freeze'):
            self.verify(owner_kind='transport_probe')

    def test_model_client_cannot_substitute_for_probe_close(self):
        self.f.write()
        with self.assertRaisesRegex(ValueError, 'unique owner-finishing'):
            self.verify(owner_kind='transport_probe')

    def test_namespace_projection_cannot_substitute_for_actual_stderr(self):
        self.f.write()
        self.f.align_namespace = False
        self.f.receipt['namespace_records'][-1]['child_exit_code'] = 0
        self.fails('Namespace projection differs')

    def test_stderr_truncated_flag_fails_even_with_complete_retained_suffix(self):
        self.f.stderr_overrides['truncated'] = True
        self.fails('stderr was missing, redacted or truncated')

    def test_bridge_first_end_must_match_original_ledger(self):
        self.f.write()
        self.f.align_first = False
        self.f.receipt['first_pump_end']['monotonic_s'] += 1
        self.fails('Bridge summary differs')

    def test_wrapper_nonzero_failure(self):
        self.f.receipt['exit_code'] = 1
        self.fails('Bridge summary differs')

    def test_denied_overlap_is_not_a_healthy_single_client(self):
        self.f.rows[-1]['denied'] = 1
        self.fails('rejected overlap')

    def test_extra_summary_cannot_escape_ledger_accounting(self):
        self.f.write()
        (self.f.stage / 'codehost-2-bridge.json').write_bytes(raw_json(self.f.receipt))
        with self.assertRaisesRegex(ValueError, 'extra codehost connection'):
            self.verify()

    def test_wrong_source_revision_fails_before_receipt_acceptance(self):
        self.f.frozen['sources'][subject.SOURCE_NAMES[0]]['sha256'] = '0' * 64
        self.fails('Transport source differs from freeze')

    def test_retirement_requires_observed_empty_namespace(self):
        self.f.retirement['observations'][-1]['namespace_members'] = [17]
        self.fails('Final retirement lacks empty retired namespace')

    def test_boolean_connection_count_rejected(self):
        self.f.rows[-1]['accepted'] = True
        self.fails('unexpected connection count')

    def test_raw_stderr_or_unknown_marker_cannot_enter_metadata(self):
        self.f.client[0]['markers'] = ['arbitrary_dynamic_error_text']
        self.fails('outside fixed vocabulary')

    def test_client_scope_cannot_be_used_as_raw_stderr_field(self):
        self.f.client[0]['scope'] = 'unbounded dynamic stderr content'
        self.fails('outside fixed vocabulary')

    def test_duplicate_json_keys_rejected(self):
        self.f.write()
        path = self.f.stage / 'client/events.jsonl'
        path.write_bytes(path.read_bytes().replace(b'"exit_code":0', b'"exit_code":0,"exit_code":1'))
        with self.assertRaisesRegex(ValueError, 'Malformed transport JSON'):
            self.verify()


if __name__ == '__main__':
    unittest.main()
