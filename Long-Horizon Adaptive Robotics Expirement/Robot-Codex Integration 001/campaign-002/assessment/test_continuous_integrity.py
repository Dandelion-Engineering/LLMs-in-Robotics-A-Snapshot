"""Synthetic retained-evidence tests; no worker, model or simulator starts."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import continuous_integrity as c


class ContinuousIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        sources = {}
        for path in (c.WORKER, c.CAMPAIGN / 'harness/continuous_adapter.py', c.CAMPAIGN / 'harness/run_host.py',
                     Path(c.__file__), c.RECORDER, c.RCI / 'host/supervisor.py'):
            sources[path.relative_to(c.REPO).as_posix()] = c.identity(path)
        self.frozen = {'sources': sources}
        self.metadata = {'sample_count': 22, 'terminal': {'reason': 'task_success'}}
        counts = {'motion': 2, 'capture': 2, 'feedback': 1, 'event': 1}
        self.receipt = {'schema': 'rci-continuous-physics-1', 'error': None, 'owner_finished': True,
                        'terminal': 'task_success', 'queue_count': 4096, 'queue_bytes': 67108864,
                        'rpc_count': 32, 'heartbeat_timeout_s': 2,
                        'metrics': {'ticks': 10, 'published': 6, 'drained': 6,
                            'published_by_kind': counts, 'drained_by_kind': copy.deepcopy(counts),
                            'peak_messages': 6, 'peak_message_bytes': 600, 'maximum_message_bytes': 100,
                            'rpc_started': 1, 'rpc_completed': 1, 'rpc_abandoned': 0,
                            'terminal_frozen': True, 'owner_closed': True}}
        self.result = {'terminal': 'task_success', 'continuous_physics': self.receipt}
        recorder = c.load_recorder().Recorder(self.root / 'native-recording', run_id='synthetic')
        for i in range(2):
            recorder.motion({'sim_time_s': 1.01 + .01 * i, 'q': [0.] * 7})
            recorder.image('overhead:' + str(i + 1), 1.1 + .1 * i, b'fixture-rgb', b'fixture-depth')
        recorder.close()
        self.history = [{'type': 'observation', 'event_id': i + 1,
                         'payload': {'sequence': i, 'capture_sim_time_s': 1 + .1 * i}} for i in range(3)]
        envelope = {'request_id': 'r1', 'authority_epoch': 3, 'order_version': 1,
                    'observation_sequence': 1, 'action': {'operation': 'cancel', 'target_request_id': 'prior'}}
        fingerprint = hashlib.sha256(json.dumps({'kind': 'command', 'actor': 'robot', 'body': envelope},
                     sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        dispatch = {'request_id': 'r1', 'fingerprint': fingerprint, 'epoch': 3, 'order_version': 1,
                    'observation_sequence': 1, 'capture_sim_time_s': 1.1, 'dispatch_sim_time_s': 1.25,
                    'durable_intent_before_rpc': True, 'fence_passed': True, 'rejection_reasons': []}
        feedback = {'request_id': 'r1', 'status': 'accepted', 'continuous_dispatch': dispatch}
        record = {'request_id': 'r1', 'kind': 'command', 'actor': 'robot', 'fingerprint': fingerprint,
                  'envelope': envelope, 'admission': feedback}
        self.registry = {'r1': record}
        self.history += [{'type': 'command_dispatched', 'event_id': 4, 'authority_epoch': 3,
                          'payload': {**copy.deepcopy(record), 'phase': 'dispatched'}},
                         {'type': 'command_admission', 'event_id': 5, 'authority_epoch': 3,
                          'payload': {'request_id': 'r1', 'feedback': copy.deepcopy(feedback)}}]
        self.write_history()

    def write_history(self):
        (self.root / 'public-history.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in self.history), encoding='utf-8')
        (self.root / 'command-registry.json').write_text(json.dumps(self.registry), encoding='utf-8')

    def verify(self):
        return c.verify_continuous_physics(self.root, self.metadata, self.result, self.frozen)

    def test_finalized_synthetic_reader_counts_and_native_dispatch_pass(self):
        result = self.verify()
        self.assertTrue(result['passed'])
        self.assertEqual((result['motion_rows'], result['image_rows'], result['journal_observations']), (2, 2, 3))
        self.assertEqual(result['dispatch_integrity']['accepted_native_commands'], 1)
        self.assertEqual(result['minimum_timing_sample_count'], 22)
        self.assertEqual(len(result['source_bindings']), 6)

    def test_historical_dev013_archive_remains_not_applicable_without_outcome_reads(self):
        path = c.RCI.parent / 'Architecture Map/releases/RCI001-C02-dev-013/snapshot.json'
        frozen = json.loads(path.read_text(encoding='utf-8'))
        with patch.object(c, 'source_bindings') as sources, patch.object(c, 'recorder_counts') as recording:
            result = c.verify_continuous_physics(self.root / 'nonexistent', {}, {}, frozen)
            self.assertEqual(result['status'], 'not_applicable')
            sources.assert_not_called()
            recording.assert_not_called()

    def test_omitting_both_helpers_cannot_bypass_new_frozen_runner(self):
        del self.frozen['sources'][c.WORKER_NAME]
        del self.frozen['sources'][c.ADAPTER_NAME]
        self.assertTrue(c.applies(self.frozen))
        with self.assertRaisesRegex(ValueError, 'source differs'):
            self.verify()

    def test_authenticated_archived_runner_also_triggers_missing_helper_gate(self):
        raw = b'from continuous_adapter import ContinuousAdapter as PhysicalAdapter\n'
        revision = 'synthetic-revision'
        archive = self.root / 'Architecture Map/releases' / revision / 'code.zip'
        archive.parent.mkdir(parents=True)
        with zipfile.ZipFile(archive, 'w') as store:
            store.writestr(c.RUNNER_NAME, raw)
        frozen = {'revision': revision, 'sources': {c.RUNNER_NAME:
                  {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}}}
        with patch.object(c, 'RCI', self.root / 'fake-rci'):
            self.assertTrue(c.applies(frozen))
            frozen['sources'][c.RUNNER_NAME]['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'archive source hash'):
                c.applies(frozen)

    def test_missing_or_changed_independent_source_is_rejected(self):
        for name in list(self.frozen['sources']):
            with self.subTest(name=name):
                saved = self.frozen['sources'].pop(name)
                with self.assertRaisesRegex(ValueError, 'source differs'):
                    self.verify()
                self.frozen['sources'][name] = saved
        self.frozen['sources'][c.WORKER_NAME]['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'source differs'):
            self.verify()

    def test_unfinished_error_or_wrong_terminal_receipts_fail(self):
        for key, value in (('schema', 'other'), ('error', {'message': 'lost'}), ('owner_finished', False),
                           ('owner_finished', 1), ('terminal', 'other')):
            with self.subTest(key=key, value=value):
                saved = self.receipt[key]
                self.receipt[key] = value
                with self.assertRaises(ValueError): self.verify()
                self.receipt[key] = saved
        del self.result['continuous_physics']
        with self.assertRaisesRegex(ValueError, 'completion receipt'): self.verify()

    def test_all_integer_counters_reject_bool_float_negative_and_missing(self):
        metrics = self.receipt['metrics']
        for name in c.COUNTERS:
            saved = metrics[name]
            for bad in (True, 1., -1, None):
                with self.subTest(name=name, bad=bad):
                    metrics[name] = bad
                    with self.assertRaisesRegex(ValueError, 'counters'): self.verify()
            metrics[name] = saved

    def test_owner_close_terminal_freeze_and_zero_ticks_fail(self):
        for name, bad in (('owner_closed', False), ('terminal_frozen', 1), ('ticks', 0)):
            saved = self.receipt['metrics'][name]
            self.receipt['metrics'][name] = bad
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'counters'): self.verify()
            self.receipt['metrics'][name] = saved

    def test_bounds_and_heartbeat_cannot_be_relaxed(self):
        for name in ('queue_count', 'queue_bytes', 'rpc_count', 'heartbeat_timeout_s'):
            saved = self.receipt[name]
            for bad in (True, None, saved + 1):
                with self.subTest(name=name, bad=bad):
                    self.receipt[name] = bad
                    with self.assertRaises(ValueError): self.verify()
            self.receipt[name] = saved

    def test_unmatched_drained_totals_and_per_kind_counts_fail(self):
        metrics = self.receipt['metrics']
        metrics['drained'] -= 1
        with self.assertRaisesRegex(ValueError, 'completely drained'): self.verify()
        metrics['drained'] += 1
        metrics['drained_by_kind']['capture'] -= 1
        with self.assertRaisesRegex(ValueError, 'per-kind'): self.verify()
        metrics['drained_by_kind']['capture'] += 1
        metrics['published_by_kind']['motion'] = True
        with self.assertRaisesRegex(ValueError, 'per-kind'): self.verify()

    def test_bound_excess_and_abandoned_rpc_are_rejected(self):
        metrics = self.receipt['metrics']
        for name, bad in (('peak_messages', 4097), ('peak_message_bytes', 67108865),
                           ('maximum_message_bytes', 601), ('rpc_abandoned', 1), ('rpc_completed', 2)):
            saved = metrics[name]
            metrics[name] = bad
            with self.subTest(name=name), self.assertRaises(ValueError): self.verify()
            metrics[name] = saved

    def test_timing_ledger_must_cover_every_tick_entry_and_exit(self):
        for count in (21, True, 22.):
            self.metadata['sample_count'] = count
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, 'tick entry/exit'): self.verify()

    def test_missing_motion_or_capture_rows_are_rejected_independently(self):
        counts = c.recorder_counts(self.root)
        for motion, capture, message in ((1, 2, 'motion'), (2, 1, 'image')):
            with self.subTest(message=message), patch.object(c, 'recorder_counts', return_value=(motion, capture, counts[2])):
                with self.assertRaisesRegex(ValueError, message): self.verify()

    def test_missing_duplicate_and_reordered_observations_fail(self):
        saved = copy.deepcopy(self.history)
        for action in ('missing', 'duplicate', 'reordered'):
            self.history = copy.deepcopy(saved)
            if action == 'missing': self.history.pop(2)
            elif action == 'duplicate': self.history.insert(2, copy.deepcopy(self.history[1]))
            else: self.history[1], self.history[2] = self.history[2], self.history[1]
            self.write_history()
            with self.subTest(action=action), self.assertRaisesRegex(ValueError, 'observation'): self.verify()

    def test_corrupt_finalized_container_is_rejected(self):
        path = self.root / 'native-recording/evidence.sqlite.gz'
        path.write_bytes(path.read_bytes() + b'changed')
        with self.assertRaisesRegex(Exception, 'manifest byte/hash'): self.verify()

    def mutate_dispatch(self, key, value):
        self.registry['r1']['admission']['continuous_dispatch'][key] = value
        self.history[-1]['payload']['feedback'] = copy.deepcopy(self.registry['r1']['admission'])
        self.write_history()

    def test_accepted_native_command_requires_durable_matching_fresh_fence(self):
        saved_registry, saved_history = copy.deepcopy(self.registry), copy.deepcopy(self.history)
        for key, value in (('fingerprint', '0' * 64), ('request_id', 'different'), ('durable_intent_before_rpc', False),
                           ('fence_passed', False), ('rejection_reasons', ['stale']), ('epoch', 2),
                           ('order_version', 2), ('observation_sequence', 2), ('capture_sim_time_s', 1.0),
                           ('dispatch_sim_time_s', 1.451), ('dispatch_sim_time_s', 1.0), ('epoch', 3.)):
            self.registry, self.history = copy.deepcopy(saved_registry), copy.deepcopy(saved_history)
            self.mutate_dispatch(key, value)
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): self.verify()

    def test_dispatch_must_be_durable_before_admission_and_follow_referenced_observation(self):
        for index, event_id in ((3, 6), (3, 1), (4, 4)):
            saved = self.history[index]['event_id']
            self.history[index]['event_id'] = event_id
            self.write_history()
            with self.subTest(index=index, event_id=event_id), self.assertRaisesRegex(ValueError, 'earlier protected'): self.verify()
            self.history[index]['event_id'] = saved

    def test_registry_or_history_cannot_hide_accepted_native_command(self):
        self.registry.clear()
        self.write_history()
        with self.assertRaisesRegex(ValueError, 'registry and protected admission'): self.verify()

    def test_bounded_idle_diagnostic_can_have_no_native_admissions(self):
        self.history = self.history[:3]
        self.registry.clear()
        self.write_history()
        self.assertEqual(self.verify()['dispatch_integrity']['accepted_native_commands'], 0)


if __name__ == '__main__':
    unittest.main()
