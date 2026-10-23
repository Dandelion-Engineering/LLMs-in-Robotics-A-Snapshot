"""Bounded metadata for one native cleanup barrier; no native RPC or payload I/O.

Consumers must also join actual protected ledgers and exact original frames.
Shape and digest checks alone do not authenticate an endpoint acknowledgment.
"""
import hashlib
import json
import math
import re

REQUEST_SCHEMA = 'campaign002-native-cleanup-request-1'
COMPLETE_SCHEMA = 'campaign002-native-cleanup-complete-1'
SEED_KEYS = {'schema', 'nonce', 'thread_id', 'turn_id', 'control_event',
             'start_monotonic_s', 'graceful_deadline_monotonic_s'}
COMPLETE_KEYS = {'schema', 'request', 'request_sha256',
    'parent_barrier_record_sha256', 'namespace_barrier_record_sha256',
    'begin_payload_sha256', 'ack_payload_sha256', 'parent_ack_record_sha256',
    'parent_ack_sequence', 'completed_monotonic_s'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(value, message):
    if value is not True:
        raise ValueError('Native cleanup barrier: ' + message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def digest(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def identity(value):
    return isinstance(value, str) and re.fullmatch('[A-Za-z0-9_-]{1,256}', value) is not None


def validate_seed(seed):
    require(isinstance(seed, dict) and set(seed) == SEED_KEYS
            and seed['schema'] == REQUEST_SCHEMA, 'request shape')
    require(isinstance(seed['nonce'], str)
            and re.fullmatch('[0-9a-f]{32}', seed['nonce']) is not None, 'nonce')
    require(identity(seed['thread_id'])
            and (seed['turn_id'] is None or identity(seed['turn_id'])), 'native identity')
    start, deadline = seed['start_monotonic_s'], seed['graceful_deadline_monotonic_s']
    # A shorter local bound is safe, including bounded deterministic tests.
    # The independent campaign reader additionally requires exactly start+5.
    require(finite(start) and finite(deadline) and start < deadline <= start+5, 'deadline')
    event = seed['control_event']
    keys = {'kind', 'schema', 'sequence', 'phase', 'wall_unix_s', 'monotonic_s',
            'method', 'request_id', 'thread_id', 'turn_id', 'wire_bytes', 'wire_sha256'}
    require(isinstance(event, dict) and set(event) == keys
            and event['kind'] == 'native_quiescence'
            and event['schema'] == 'campaign002-native-quiescence-event-1'
            and event['phase'] == 'request'
            and type(event['sequence']) is int and 2 <= event['sequence'] <= 24
            and finite(event['wall_unix_s']) and finite(event['monotonic_s'])
            and start <= event['monotonic_s'] < deadline, 'control event')
    require(event['method'] in ('turn/interrupt', 'thread/unsubscribe')
            and type(event['request_id']) is int and event['request_id'] > 0
            and event['thread_id'] == seed['thread_id'], 'control identity')
    params = {'threadId': seed['thread_id']}
    if event['method'] == 'turn/interrupt':
        require(identity(seed['turn_id']) and event['turn_id'] == seed['turn_id'], 'interrupt turn')
        params['turnId'] = seed['turn_id']
    else:
        require(event['turn_id'] is None, 'unsubscribe turn')
    wire = (json.dumps({'id': event['request_id'], 'method': event['method'], 'params': params})+'\n').encode()
    require(type(event['wire_bytes']) is int and event['wire_bytes'] == len(wire)
            and event['wire_sha256'] == sha(wire), 'original control bytes')
    require(len(canonical(seed)) <= 4096, 'request bound')
    return seed


def bind_request(seed, owner_sha):
    validate_seed(seed)
    require(digest(owner_sha), 'owner receipt hash')
    return {**json.loads(canonical(seed)), 'owner_receipt_sha256': owner_sha}


def validate_request(request):
    require(isinstance(request, dict) and set(request) == SEED_KEYS | {'owner_receipt_sha256'},
            'authenticated request shape')
    validate_seed({key: request[key] for key in SEED_KEYS})
    require(digest(request['owner_receipt_sha256']), 'owner receipt hash')
    return request


def validate_complete(seed, complete):
    validate_seed(seed)
    require(isinstance(complete, dict) and set(complete) == COMPLETE_KEYS
            and complete['schema'] == COMPLETE_SCHEMA, 'completion shape')
    request = validate_request(complete['request'])
    require({key: request[key] for key in SEED_KEYS} == seed, 'completion request differs')
    for key in COMPLETE_KEYS:
        if key.endswith('_sha256'):
            require(digest(complete[key]), 'completion digest')
    require(complete['request_sha256'] == sha(canonical(request)), 'request digest differs')
    require(type(complete['parent_ack_sequence']) is int and complete['parent_ack_sequence'] > 0,
            'ACK sequence')
    completed = complete['completed_monotonic_s']
    require(finite(completed)
            and seed['control_event']['monotonic_s'] <= completed < seed['graceful_deadline_monotonic_s'],
            'completion deadline')
    require(len(canonical(complete)) <= 8192, 'completion bound')
    return complete
