"""Exact bounded barrier metadata; endpoint authentication is tested separately."""
import copy
import json
import unittest

import native_cleanup_protocol as protocol


def seed(method='turn/interrupt', *, start=10, deadline=15, event_time=10.1):
    params = {'threadId': 'thread-fixed'}
    if method == 'turn/interrupt': params['turnId'] = 'turn-fixed'
    wire = (json.dumps({'id': 41, 'method': method, 'params': params})+'\n').encode()
    return {'schema': protocol.REQUEST_SCHEMA, 'nonce': '1'*32,
        'thread_id': 'thread-fixed', 'turn_id': 'turn-fixed',
        'start_monotonic_s': start, 'graceful_deadline_monotonic_s': deadline,
        'control_event': {'kind': 'native_quiescence', 'schema': 'campaign002-native-quiescence-event-1',
            'sequence': 2, 'phase': 'request', 'wall_unix_s': 100, 'monotonic_s': event_time,
            'method': method, 'request_id': 41, 'thread_id': 'thread-fixed',
            'turn_id': 'turn-fixed' if method == 'turn/interrupt' else None,
            'wire_bytes': len(wire), 'wire_sha256': protocol.sha(wire)}}


def completion(request_seed, *, completed=None):
    request = protocol.bind_request(request_seed, '2'*64)
    return {'schema': protocol.COMPLETE_SCHEMA, 'request': request,
        'request_sha256': protocol.sha(protocol.canonical(request)),
        'parent_barrier_record_sha256': '3'*64, 'namespace_barrier_record_sha256': '4'*64,
        'begin_payload_sha256': '5'*64, 'ack_payload_sha256': '6'*64,
        'parent_ack_record_sha256': '7'*64, 'parent_ack_sequence': 9,
        'completed_monotonic_s': (request_seed['control_event']['monotonic_s']
                                 if completed is None else completed)}


class CleanupProtocolTests(unittest.TestCase):
    def test_exact_control_and_retained_turn_are_distinct_for_unsubscribe(self):
        for method in ('turn/interrupt', 'thread/unsubscribe'):
            request_seed = seed(method)
            self.assertIs(protocol.validate_seed(request_seed), request_seed)
            complete = completion(request_seed)
            self.assertIs(protocol.validate_complete(request_seed, complete), complete)
        self.assertIsNone(request_seed['control_event']['turn_id'])
        self.assertEqual(request_seed['turn_id'], 'turn-fixed')

    def test_request_binding_is_detached_from_retained_event(self):
        original = seed(); request = protocol.bind_request(original, '2'*64)
        request['control_event']['request_id'] = 99
        self.assertEqual(original['control_event']['request_id'], 41)

    def test_unknown_keys_wrong_wire_identity_and_unsafe_deadlines_fail(self):
        cases = [(['extra'], 1), (['nonce'], 'bad'), (['thread_id'], 'other'),
            (['turn_id'], None), (['control_event','request_id'], True),
            (['control_event','method'], 'turn/start'), (['control_event','wire_sha256'], '0'*64),
            (['control_event','wire_bytes'], True), (['control_event','sequence'], True),
            (['control_event','monotonic_s'], 9), (['control_event','monotonic_s'], 15),
            (['graceful_deadline_monotonic_s'], 15.01), (['start_monotonic_s'], float('nan'))]
        for keys, value in cases:
            with self.subTest(keys=keys, value=value):
                candidate = seed(); target = candidate
                for key in keys[:-1]: target = target[key]
                target[keys[-1]] = value
                with self.assertRaises(ValueError): protocol.validate_seed(candidate)

    def test_wrong_nonce_owner_request_ack_digest_and_late_completion_fail(self):
        original = seed()
        for key, value in [('request_sha256', 'f'*64), ('parent_ack_sequence', True),
                           ('completed_monotonic_s', 15), ('ack_payload_sha256', 'G'*64),
                           ('extra', 1)]:
            candidate = completion(original); candidate[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                protocol.validate_complete(original, candidate)
        for key, value in [('nonce','a'*32), ('owner_receipt_sha256','bad')]:
            candidate = completion(original); candidate['request'][key] = value
            candidate['request_sha256'] = protocol.sha(protocol.canonical(candidate['request']))
            with self.subTest(key=key), self.assertRaises(ValueError):
                protocol.validate_complete(original, candidate)


if __name__ == '__main__': unittest.main()
