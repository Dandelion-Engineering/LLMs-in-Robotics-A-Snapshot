"""Independent protected-metadata verification for the declared transport v3.

No runtime implementation is imported. This reader does not open sockets, replay
RPCs or infer model/task success. Its caller must first authenticate the official
queue success. Legacy transport verdicts remain the responsibility of v2.
"""
from __future__ import annotations

import hashlib
import json
import math
import ntpath
from pathlib import Path
import re

import client_quiescence
import pre_exit_integrity
import process_integrity
import cleanup_transport


REPO = Path(__file__).resolve().parents[4]
INTEGRATION = 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/'
CAMPAIGN = INTEGRATION + 'campaign-002/'
TRANSPORT_SCHEMA = 'campaign002-codehost-transport-3'
NAMESPACE_SCHEMA = 'campaign002-codehost-namespace-3'
MAX_METADATA_BYTES = 1024 * 1024
MAX_RECEIPT_BYTES = 8 * 1024 * 1024
MAX_CHANNELS = 16
MAX_FRAME_PAYLOAD = 65536
MAX_CHANNEL_QUEUE_BYTES = 1024 * 1024
MAX_AGGREGATE_QUEUE_BYTES = 4 * 1024 * 1024
PARENT_KINDS = frozenset({
    'open', 'namespace_started', 'frame', 'listening', 'owner_registered',
    'channel_authenticated', 'client_eof', 'channel_closed', 'channel_finish_frontier',
    'owner_drain_begin', 'owner_drain_ack', 'owner_drain_completed', 'channel_seal_frontier', 'upload_drained',
    'owner_finishing', 'owner_input_closed', 'namespace_finished', 'namespace_output_closed',
    'retirement_started', 'closed',
    'native_cleanup_begin', 'native_cleanup_ack', 'native_cleanup_channel',
})
PROBE_SOURCE_NAME = CAMPAIGN + 'harness/codehost_transport_probe_v3.py'
PREFLIGHT_SOURCE_NAME = CAMPAIGN + 'harness/raw_event_preflight_v2.py'
BOUNDARY_SOURCE_NAME = CAMPAIGN + 'qualification/boundary_suite_v3.py'
SOURCE_NAMES = tuple(CAMPAIGN + name for name in (
    'harness/codehost_bridge_v3.py', 'harness/codehost_owner.py',
    'harness/codehost_inside_v3.py', 'harness/codehost_entry_v3.py',
    'harness/codehost_mux_protocol.py', 'harness/bootstrap_client_v4.py',
    'harness/runtime.py', 'harness/transport_stderr.py',
    'assessment/transport_integrity_v3.py', 'assessment/transport_dispatch.py',
    'assessment/assess.py', 'assessment/assess_smoke_v2.py',
    'io-repair/CODEHOST_CHANNEL_TRANSPORT_V3.md',
    'io-repair/CHANNEL_FINISH_FRONTIER_VALIDATION_V1.md',
    'io-repair/CHANNEL_OWNER_DRAIN_V1.md',
    'io-repair/NORMAL_CLOSED_CANCEL_V1.md',
)) + tuple(INTEGRATION + 'readiness-session-10/boundary/' + name for name in (
    'linux_entry.py', 'namespace.py', 'inside.py', 'gateway_policy.py', 'retirement.py',
))
BRIDGE_SOURCE_NAMES = tuple(CAMPAIGN + 'harness/' + name for name in (
    'codehost_bridge_v3.py', 'codehost_owner.py', 'codehost_mux_protocol.py',
    'codehost_entry_v3.py', 'codehost_inside_v3.py',
)) + tuple(INTEGRATION + 'readiness-session-10/boundary/' + name
           for name in ('linux_entry.py', 'namespace.py'))


def require(condition, message):
    if condition is not True:
        raise ValueError(message)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def hash_value(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def object_pairs(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'Duplicate transport JSON key: ' + key)
        value[key] = item
    return value


def decode(raw, label):
    try:
        return json.loads(raw, object_pairs_hook=object_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    except (ValueError, UnicodeError) as error:
        raise ValueError('Malformed transport JSON: ' + label) from error


def read_file(path, bindings, maximum=MAX_METADATA_BYTES):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'Missing ordinary transport file: ' + path.name)
    require(path.stat().st_size <= maximum, 'Transport file exceeds bound: ' + path.name)
    raw = path.read_bytes()
    require(len(raw) <= maximum, 'Transport file grew beyond bound: ' + path.name)
    bindings[path.name] = {'sha256': digest(raw), 'bytes': len(raw)}
    return raw


def document(path, bindings, maximum=MAX_METADATA_BYTES):
    raw = read_file(path, bindings, maximum)
    require(raw.endswith(b'\n'), 'Incomplete transport document tail: ' + Path(path).name)
    value = decode(raw, Path(path).name)
    require(isinstance(value, dict), 'Transport document must be an object')
    return value


def json_lines(path, bindings, maximum=MAX_METADATA_BYTES):
    raw = read_file(path, bindings, maximum)
    require(bool(raw) and raw.endswith(b'\n'), 'Missing or truncated transport stream tail')
    lines = raw.splitlines()
    require(all(lines), 'Empty transport record')
    values = [decode(line, Path(path).name) for line in lines]
    require(all(isinstance(row, dict) for row in values), 'Transport records must be objects')
    return values


def bound_document(root, item, name, bindings, *, raw=False, maximum=MAX_METADATA_BYTES):
    require(isinstance(item, dict) and set(item) >= {'path', 'bytes', 'sha256'}
            and item['path'] == name and integer(item['bytes']) and hash_value(item['sha256']),
            'Transport binding path or identity differs: ' + name)
    content = read_file(Path(root) / name, bindings, maximum)
    require(len(content) == item['bytes'] and digest(content) == item['sha256'],
            'Transport bound content differs: ' + name)
    if raw:
        return content
    require(content.endswith(b'\n'), 'Incomplete bound transport document')
    value = decode(content, name)
    require(isinstance(value, dict), 'Bound transport document must be an object')
    return value


def stream_identity(value, label):
    require(isinstance(value, dict) and set(value) == {'bytes', 'sha256'}
            and integer(value['bytes']) and hash_value(value['sha256'])
            and (value['bytes'] != 0 or value['sha256'] == digest(b'')),
            'Invalid byte stream identity: ' + label)
    return value


def queue_accounting(value, channels, *, namespace=False):
    headroom = 3 * MAX_FRAME_PAYLOAD if namespace else 10 * MAX_FRAME_PAYLOAD
    peak_key = 'queue_high_water_bytes' if namespace else 'queue_maximum_bytes'
    headroom_key = 'queue_headroom_bytes' if namespace else 'framing_headroom_bytes'
    require(type(value.get(headroom_key)) is int and value[headroom_key] == headroom
            and integer(value.get(peak_key)) and value[peak_key] + headroom <= MAX_AGGREGATE_QUEUE_BYTES,
            'Queue framing/read-ahead headroom or aggregate bound differs')
    peaks = value.get('per_channel_queue_maximum_bytes')
    require(isinstance(peaks, dict) and set(peaks) == {str(cid) for cid in channels}
            and all(integer(n) and n + headroom <= MAX_CHANNEL_QUEUE_BYTES for n in peaks.values()),
            'Per-channel queue plus finite framing headroom exceeds bound or is missing')
    if not namespace:
        require(type(value.get('queue_with_headroom_maximum_bytes')) is int
                and value['queue_with_headroom_maximum_bytes'] == value[peak_key] + headroom
                and value.get('per_channel_with_headroom_maximum_bytes')
                == {cid: peak + headroom for cid, peak in peaks.items()}
                and all(type(n) is int for n in value['per_channel_with_headroom_maximum_bytes'].values()),
                'Parent physical queue accounting differs from logical peak plus headroom')


def opening_bounds(value):
    for key, expected in (
        ('max_connections', MAX_CHANNELS), ('max_frame_bytes', MAX_FRAME_PAYLOAD),
        ('per_channel_queue_bytes', MAX_CHANNEL_QUEUE_BYTES),
        ('aggregate_queue_bytes', MAX_AGGREGATE_QUEUE_BYTES),
        ('framing_headroom_bytes', 10 * MAX_FRAME_PAYLOAD),
        ('subprocess_reader_limit', 32768), ('client_socket_read_ahead_bytes', 0)):
        require(type(value.get(key)) is int and value[key] == expected,
                'Parent declared resource/read-ahead bound differs: ' + key)


def metadata_sequence(rows, schema, *, hash_chain=False):
    previous, last = None, -1
    for index, row in enumerate(rows, 1):
        require(row.get('schema') == schema and type(row.get('sequence')) is int
                and row['sequence'] == index and finite(row.get('wall_unix_s'))
                and finite(row.get('monotonic_s')) and row['monotonic_s'] >= last,
                'Transport metadata sequence or clock differs')
        if hash_chain:
            require(row.get('previous_sha256') == previous
                    and digest(canonical({k: v for k, v in row.items() if k != 'record_sha256'}))
                    == row.get('record_sha256'), 'Transport ledger hash or chain differs')
            previous = row['record_sha256']
        last = row['monotonic_s']


def source_bindings(frozen, owner_kind, allow_empty=False):
    require(owner_kind in ('model_client', 'transport_probe'), 'Unknown transport owner kind')
    require(isinstance(frozen, dict) and isinstance(frozen.get('sources'), dict),
            'Frozen source snapshot is required')
    identities = {}
    names = SOURCE_NAMES + ((PROBE_SOURCE_NAME,) if owner_kind == 'transport_probe' else ())
    if cleanup_transport.METHOD in frozen['sources']:
        names = tuple(dict.fromkeys(names + cleanup_transport.SOURCE_NAMES))
    if owner_kind == 'model_client':
        names = tuple(dict.fromkeys(names + client_quiescence.SOURCE_NAMES))
    if allow_empty:
        require(owner_kind == 'model_client', 'Empty transport is restricted to native metadata preflight')
        names += (PREFLIGHT_SOURCE_NAME,)
    for name in names:
        path = REPO / name
        require(path.is_file() and not path.is_symlink(), 'Missing transport source: ' + name)
        raw = path.read_bytes()
        expected = {'bytes': len(raw), 'sha256': digest(raw)}
        declared = frozen['sources'].get(name)
        require(isinstance(declared, dict) and type(declared.get('bytes')) is int
                and declared == expected, 'Transport source differs from frozen snapshot: ' + name)
        identities[name] = expected
    return identities


def windows_path(value):
    return (isinstance(value, str) and bool(value) and '\x00' not in value
            and ntpath.isabs(value) and bool(ntpath.splitdrive(value)[0]))


def owner_identity(owner, owner_kind):
    require(isinstance(owner, dict) and set(owner) == {
        'schema', 'owner_kind', 'pid', 'process_creation_filetime', 'queried_executable_path',
        'executable', 'wall_unix_s', 'monotonic_s'}, 'Native owner fields differ')
    require(owner['schema'] == 'campaign002-native-owner-1' and owner['owner_kind'] == owner_kind
            and integer(owner['pid'], 1) and integer(owner['process_creation_filetime'], 1)
            and finite(owner['wall_unix_s']) and finite(owner['monotonic_s']),
            'Native owner identity or kind differs')
    executable = owner['executable']
    require(isinstance(executable, dict) and set(executable) == {
        'path', 'sha256', 'bytes', 'file_identity'} and windows_path(executable['path'])
        and windows_path(owner['queried_executable_path']) and hash_value(executable['sha256'])
        and integer(executable['bytes'], 1), 'Native owner executable identity missing')
    file_id = executable['file_identity']
    require(isinstance(file_id, list) and len(file_id) == 4
            and all(integer(n) for n in file_id) and file_id[2] == executable['bytes']
            and ntpath.normcase(ntpath.normpath(executable['path']))
            == ntpath.normcase(ntpath.normpath(owner['queried_executable_path'])),
            'Native owner queried executable or file identity differs')
    return owner


def tcp_endpoint(value):
    return (isinstance(value, list) and len(value) == 2 and value[0] == '127.0.0.1'
            and integer(value[1], 1) and value[1] < 65536)


def channel_owner(auth, owner):
    require(isinstance(auth, dict) and set(auth) == {
        'schema', 'owner_pid', 'process_creation_filetime', 'queried_executable_path',
        'executable_sha256', 'executable_file_identity', 'client', 'server', 'tcp_state',
        'lookup_attempts', 'lookup_elapsed_s', 'wall_unix_s', 'monotonic_s'},
        'Channel owner fields differ')
    require(auth['schema'] == 'campaign002-channel-owner-1'
            and type(auth['owner_pid']) is int and auth['owner_pid'] == owner['pid']
            and type(auth['process_creation_filetime']) is int
            and auth['process_creation_filetime'] == owner['process_creation_filetime']
            and auth['queried_executable_path'] == owner['queried_executable_path']
            and auth['executable_sha256'] == owner['executable']['sha256']
            and isinstance(auth['executable_file_identity'], list)
            and all(type(value) is int for value in auth['executable_file_identity'])
            and auth['executable_file_identity'] == owner['executable']['file_identity'],
            'Channel owner is foreign, reused or changed')
    require(tcp_endpoint(auth['client']) and tcp_endpoint(auth['server'])
            and auth['client'] != auth['server'] and type(auth['tcp_state']) is int
            and auth['tcp_state'] == 5 and integer(auth['lookup_attempts'], 1)
            and finite(auth['lookup_elapsed_s']) and auth['lookup_elapsed_s'] <= .250
            and finite(auth['wall_unix_s']) and finite(auth['monotonic_s'])
            and auth['monotonic_s'] >= owner['monotonic_s']
            and auth['wall_unix_s'] >= owner['wall_unix_s'],
            'Channel TCP owner lookup is unproven, late or malformed')
    return auth


def frame_identity(row):
    """Normalize source-bound metadata only; never reconstruct payload bytes."""
    kind, channel, size, checksum = (row.get(name) for name in
        ('frame_type', 'channel_id', 'payload_bytes', 'payload_sha256'))
    require(type(kind) is int and 1 <= kind <= 13 and integer(channel)
            and channel <= MAX_CHANNELS and integer(size) and size <= MAX_FRAME_PAYLOAD
            and hash_value(checksum), 'Framing type, channel, payload bound or identity differs')
    require((kind in (7, 8, 9, 10, 11, 12, 13)) == (channel == 0), 'Owner/channel frame scope differs')
    if kind in (1, 2, 4, 7, 10, 11):
        require(size == 0 and checksum == digest(b''), 'Control frame payload differs')
    else:
        require(size > 0, 'Missing nonempty framing payload')
    return (kind, channel, size, checksum)


def framing_integrity(parent, namespace, channel_metadata, ready, *, allow_empty=False):
    """Validate parent transitions and exact directional frame correspondence.

    DATA identities compare opaque frame metadata, and channel receipts compare
    independent whole-stream hashes. This reader never supplies missing bytes.
    """
    parent_projection = {'sent': [], 'received': []}
    namespace_projection = {'incoming': [], 'outgoing': []}
    state, totals, next_channel = {}, {}, 1
    ready_seen = finish_seen = drain_seen = ack_seen = False
    cleanup_seen = cleanup_ack_seen = False
    for row in parent:
        direction = row.get('direction')
        require(direction in parent_projection, 'Unknown parent framing direction')
        kind, channel, size, checksum = frame_identity(row)
        parent_projection[direction].append((kind, channel, size, checksum))
        if kind == 9:
            require(direction == 'received' and not ready_seen and not state and not finish_seen,
                    'Duplicate or late namespace READY')
            require(size == len(canonical(ready)) and checksum == digest(canonical(ready)),
                    'READY payload identity differs')
            ready_seen = True
        else:
            require(ready_seen, 'Channel framing before namespace READY')
            if kind == 1:
                require(direction == 'sent' and not drain_seen and not finish_seen and channel == next_channel
                        and channel not in state, 'Channel open reused, unordered or after FINISH')
                state[channel] = 'opening'
                totals[channel] = {'upload': 0, 'download': 0}
                next_channel += 1
            elif kind == 2:
                require(direction == 'received' and state.get(channel) == 'opening',
                        'Unexpected or duplicate OPENED')
                state[channel] = 'open'
            elif kind == 3:
                require((not finish_seen or direction == 'received') and state.get(channel) in ('open', 'half_closed'), 'DATA before OPENED, after CLOSED or after sealed FINISH')
                require(direction != 'sent' or state[channel] == 'open', 'DATA after upload HALF_CLOSE')
                totals[channel]['upload' if direction == 'sent' else 'download'] += size
            elif kind == 4:
                require(direction == 'sent' and state.get(channel) == 'open',
                        'Unexpected or duplicate HALF_CLOSE')
                state[channel] = 'half_closed'
            elif kind == 5:
                require(direction == 'received' and state.get(channel) in ('open', 'half_closed')
                        and channel in channel_metadata, 'Unexpected or duplicate CLOSED')
                payload = canonical(channel_metadata[channel])
                require(size == len(payload) and checksum == digest(payload), 'CLOSED payload identity differs')
                state[channel] = 'closed'
            elif kind == 6:
                raise ValueError('ERROR frame forbids ordinary transport qualification')
            elif kind == 7:
                require(direction == 'sent' and drain_seen and ack_seen and not finish_seen, 'FINISH before drain acknowledgment, duplicate or wrong direction')
                finish_seen = True
            elif kind == 10:
                require(direction == 'sent' and not drain_seen and not finish_seen, 'Duplicate or late DRAIN_BEGIN')
                drain_seen = True
            elif kind == 11:
                require(direction == 'received' and drain_seen and not ack_seen and not finish_seen, 'DRAIN_ACK absent, duplicate or out of phase')
                ack_seen = True
            elif kind == 12:
                require(direction == 'sent' and not cleanup_seen and not drain_seen and not finish_seen,
                        'Duplicate or late CLEANUP_BEGIN')
                cleanup_seen = True
            elif kind == 13:
                require(direction == 'received' and cleanup_seen and not cleanup_ack_seen
                        and not drain_seen and not finish_seen, 'CLEANUP_ACK absent, duplicate or late')
                cleanup_ack_seen = True
            elif kind == 8:
                raise ValueError('FINISHED requires its separate terminal delivery receipt')
    require(ready_seen and finish_seen and cleanup_seen == cleanup_ack_seen
            and (0 if allow_empty else 1) <= len(state) <= MAX_CHANNELS
            and set(state) == set(channel_metadata) and all(value == 'closed' for value in state.values()),
            'Incomplete owner/channel framing lifecycle')
    for row in namespace:
        direction = row.get('direction')
        require(direction in namespace_projection, 'Unknown namespace framing direction')
        namespace_projection[direction].append(frame_identity(row))
    require(parent_projection['sent'] == namespace_projection['incoming']
            and parent_projection['received'] == namespace_projection['outgoing'],
            'End-to-end directional frame identities/order differ')
    return totals


def h2_summary(value, *, complete=True):
    expected = {'schema', 'error', 'preface_complete', 'settings_complete', 'frames_complete',
                'headers_complete', 'open_streams', 'closed_streams', 'reset_streams',
                'active_stream_ids', 'reset_records', 'goaway', 'frames', 'bytes', 'max_streams',
                'last_stream_id', 'retiring', 'frame_complete', 'header_complete',
                'settings_by_direction', 'upload_complete', 'terminal_control_records'}
    if isinstance(value, dict) and ('cleanup_phase_nonce' in value or 'cleanup_cancel_records' in value):
        expected |= {'cleanup_phase_nonce', 'cleanup_cancel_records'}
    require(isinstance(value, dict) and set(value) == expected
            and value['schema'] == 'campaign002-passive-h2-3' and value['error'] is None
            and type(value['max_streams']) is int and value['max_streams'] == 1024,
            'HTTP2 witness schema, error or bound differs')
    for key in ('preface_complete', 'settings_complete', 'frames_complete', 'headers_complete'):
        require(type(value[key]) is bool and (not complete or value[key] is True),
                'HTTP2 preface/settings/frame/header completion is unproven')
    for detail, aggregate in (('frame_complete','frames_complete'), ('header_complete','headers_complete'),
                              ('settings_by_direction','settings_complete')):
        require(isinstance(value[detail], dict) and set(value[detail]) == {'upload','download'}
                and all(type(v) is bool for v in value[detail].values())
                and value[aggregate] is all(value[detail].values()), 'HTTP2 directional completion differs')
    require(type(value['upload_complete']) is bool and value['upload_complete'] is (
            value['error'] is None and value['preface_complete'] and value['settings_by_direction']['upload']
            and value['frame_complete']['upload'] and value['header_complete']['upload']),
            'HTTP2 upload completion differs')
    require(all(integer(value[key]) for key in ('open_streams', 'closed_streams', 'reset_streams')),
            'HTTP2 stream counters malformed')
    active = value['active_stream_ids']
    require(isinstance(active, list) and all(integer(n, 1) and n < 2**31 and n % 2 == 1 for n in active)
            and active == sorted(set(active)) and len(active) == value['open_streams']
            and len(active) <= 1024, 'HTTP2 active stream identities malformed')
    require(integer(value['last_stream_id']) and value['last_stream_id'] < 2**31
            and (value['last_stream_id'] == 0 or value['last_stream_id'] % 2 == 1)
            and all(n <= value['last_stream_id'] for n in active) and type(value['retiring']) is bool,
            'HTTP2 monotone stream frontier or retirement phase malformed')
    resets = value['reset_records']
    require(isinstance(resets, list) and len(resets) == value['reset_streams'] and len(resets) <= 1024
            and all(isinstance(row, dict) and set(row) == {'direction', 'stream_id', 'error_code'}
                    and row['direction'] in ('upload', 'download') and integer(row['stream_id'], 1)
                    and row['stream_id'] < 2**31 and row['stream_id'] % 2 == 1
                    and integer(row['error_code']) and row['error_code'] < 2**32 for row in resets)
            and len({row['stream_id'] for row in resets}) == len(resets),
            'HTTP2 reset identities missing, duplicate or malformed')
    for key in ('frames', 'bytes', 'goaway'):
        item = value[key]
        require(isinstance(item, dict) and set(item) == {'upload', 'download'},
                'HTTP2 directional witness missing')
        require(all((n is None or integer(n) and n < 2**31) if key == 'goaway' else integer(n)
                    for n in item.values()), 'HTTP2 directional counter malformed')
    terminal_controls(value)
    cleanup_transport.records(value)
    return value


def terminal_controls(value):
    """Validate the bounded proof for pre-retirement, normally closed CANCELs."""
    records = value['terminal_control_records']
    require(isinstance(records, list) and len(records) <= 64
            and len(records) <= value['closed_streams'], 'HTTP2 terminal control count differs')
    fields = {'direction', 'stream_id', 'error_code', 'frame', 'end_byte',
              'normal_close', 'opposite_observed_frames'}
    seen, previous_frame, previous_byte = set(), 0, 0
    unavailable = set(value['active_stream_ids']) | {row['stream_id'] for row in value['reset_records']}

    def position(item, direction):
        require(isinstance(item, dict) and set(item) == {'frame', 'end_byte'}
                and integer(item['frame'], 1) and integer(item['end_byte'], 1)
                and item['frame'] <= value['frames'][direction]
                and item['end_byte'] <= value['bytes'][direction]
                and item['end_byte'] >= 9 * item['frame'] + (24 if direction == 'upload' else 0),
                'HTTP2 terminal closure position is malformed or exceeds wire bounds')

    for row in records:
        require(isinstance(row, dict) and set(row) == fields
                and row['direction'] == 'upload' and type(row['error_code']) is int and row['error_code'] == 8
                and integer(row['stream_id'], 1) and row['stream_id'] % 2 == 1
                and row['stream_id'] <= value['last_stream_id'] and row['stream_id'] not in seen | unavailable,
                'HTTP2 terminal control identity, direction or code differs')
        position({key: row[key] for key in ('frame', 'end_byte')}, 'upload')
        close = row['normal_close']
        require(isinstance(close, dict) and set(close) == {'opened_upload', 'upload_closed', 'download_closed'},
                'HTTP2 terminal normal closure proof missing or malformed')
        for name, direction in (('opened_upload','upload'), ('upload_closed','upload'), ('download_closed','download')):
            position(close[name], direction)
        opened, upload, download = (close[name] for name in ('opened_upload','upload_closed','download_closed'))
        require(2 <= opened['frame'] <= upload['frame'] < row['frame']
                and opened['end_byte'] <= upload['end_byte'] <= row['end_byte'] - 13
                and (opened['frame'] != upload['frame'] or opened['end_byte'] == upload['end_byte'])
                and upload['end_byte'] - opened['end_byte'] >= 9 * (upload['frame'] - opened['frame'])
                and row['end_byte'] - upload['end_byte'] >= 13 + 9 * (row['frame'] - upload['frame'] - 1)
                and download['frame'] >= 2
                and integer(row['opposite_observed_frames'], download['frame'])
                and row['opposite_observed_frames'] <= value['frames']['download']
                and row['frame'] > previous_frame and row['end_byte'] > previous_byte,
                'HTTP2 terminal control closure order or local causal evidence differs')
        seen.add(row['stream_id']); previous_frame, previous_byte = row['frame'], row['end_byte']


def h2_facts(value):
    # Only retirement and this explicitly local causal count are not wire facts.
    if not isinstance(value, dict): return None
    return cleanup_transport.facts(value)


def idle_h2(value):
    h2_summary(value)
    require(value['open_streams'] == 0 and cleanup_transport.explained_resets(value),
            'Early channel EOF has unfinished or reset HTTP2 streams')


def channel_h2(value, frontier, *, complete=True):
    """Closure permits only CANCELs in the immutable original drain frontier."""
    h2_summary(value, complete=complete)
    h2_summary(frontier, complete=False)
    require(cleanup_transport.explained_resets(frontier), 'Earlier HTTP2 reset cannot be laundered by owner FINISH')
    cleanup_transport.progress(value, frontier)
    vi, vt = cleanup_transport.records(value); fi, ft = cleanup_transport.records(frontier)
    require([r for i,r in enumerate(value['terminal_control_records']) if i not in vt]
            == [r for i,r in enumerate(frontier['terminal_control_records']) if i not in ft],
            'HTTP2 terminal controls changed or appeared during retirement')
    require(frontier['retiring'] is False and value['last_stream_id'] == frontier['last_stream_id'],
            'Owner drain created a new stream or replaced its original frontier')
    active = set(frontier['active_stream_ids'])
    require(all(row['error_code'] == 8 and row['stream_id'] in active
                for i,row in enumerate(value['reset_records']) if i not in vi)
            and set(value['active_stream_ids']) <= active,
            'Owner finish contains an unexplained reset or new stream')
    for row in value.get('cleanup_cancel_records', [])[len(frontier.get('cleanup_cancel_records', [])):]:
        require(row['stream_id'] <= frontier['last_stream_id']
                and (row['local']['classification']=='normal_closed' or row['stream_id'] in active),
                'Cleanup cancellation extends the final original stream frontier')
        if row['local']['classification']=='active':
            require(row['cancel']['frame'] > frontier['frames']['upload']
                    and row['cancel']['start_byte'] >= frontier['bytes']['upload'],
                    'Active cleanup reset began before the final retirement frontier')
    require(value['closed_streams'] >= frontier['closed_streams']
            and all(value[key][direction] >= frontier[key][direction]
                    for key in ('bytes', 'frames') for direction in ('upload', 'download')),
            'HTTP2 witness reversed after owner FINISH')


def parent_finish_frontiers(rows, channels, auths, marker, finishing, *, diagnostic=False):
    """Bind each source-emitted parent frontier without equating endpoint clocks.

    A DATA frame receipt can precede feeding that payload into the parent H2
    witness. Conversely, an upload can enter that witness before its framed
    write drains. Exact directional prefixes preserve those producer orderings;
    no payload bytes or missing H2 observations are reconstructed here.
    """
    frontiers = [row for row in rows if row.get('kind') == 'channel_finish_frontier']
    require(all(type(row.get('channel_id')) is int for row in frontiers)
            and [row['channel_id'] for row in frontiers] == list(channels),
            'Parent finish frontier identity, order or multiplicity differs')
    expected_fields = {'schema', 'sequence', 'previous_sha256', 'record_sha256',
                       'kind', 'wall_unix_s', 'monotonic_s', 'channel_id', 'client_finishing', 'h2', 'upload_read_pending'}
    for row in frontiers:
        cid = row['channel_id']; channel = channels[cid]
        matches = [auth for auth in auths if auth.get('channel_id') == cid]
        require(set(row) == expected_fields and len(matches) == 1
                and row.get('client_finishing') is True and type(row.get('upload_read_pending')) is bool
                and matches[0]['sequence'] < row['sequence'] < finishing['sequence']
                and marker['monotonic_s'] <= row['monotonic_s'] <= finishing['monotonic_s']
                and marker['wall_unix_s'] <= row['wall_unix_s'] <= finishing['wall_unix_s'],
                'Parent finish frontier phase, fields, clock or causal order differs')
        frontier = h2_summary(row.get('h2'), complete=False)
        require(frontier == channel.get('finish_frontier'),
                'Parent finish frontier receipt projection differs')
        require(cleanup_transport.explained_resets(frontier),
                'Earlier HTTP2 reset cannot be laundered by parent finish frontier')
        final = channel.get('h2')
        channel_h2(final, frontier, complete=not diagnostic)
        meters = channel.get('meters')
        require(isinstance(meters, dict) and set(meters) == {
            'client_read', 'upload', 'download', 'client_written'}, 'Frontier byte meters missing')
        for name, value in meters.items(): stream_identity(value, 'frontier ' + name)
        require(final['bytes'] == {'upload': meters['client_read']['bytes'],
                                   'download': meters['download']['bytes']},
                'Parent frontier final byte counters differ from endpoint meters')
        for direction, transport_direction in (('upload', 'outgoing'), ('download', 'incoming')):
            data = [event for event in rows if event.get('kind') == 'frame'
                    and event.get('channel_id') == cid and event.get('frame_type') == 3
                    and event.get('direction') == transport_direction]
            total, prefixes = 0, {0}
            for event in data:
                require(integer(event.get('payload_bytes')), 'Frontier DATA byte counter malformed')
                total += event['payload_bytes']; prefixes.add(total)
            before = sum(event['payload_bytes'] for event in data if event['sequence'] < row['sequence'])
            observed = frontier['bytes'][direction]
            require(total == final['bytes'][direction] and observed in prefixes,
                    'Parent finish frontier is not an exact directional DATA prefix')
            if direction == 'upload':
                require(before <= observed <= total, 'Parent upload frontier precedes already drained DATA')
            else:
                # observe_finishing may run inside feed_h2 immediately after the
                # current incoming DATA receipt and before that payload is fed.
                preceding = next((event for event in reversed(rows[:row['sequence']-1])
                                  if event.get('kind') != 'channel_finish_frontier'), None)
                pending = (preceding['payload_bytes'] if preceding in data else 0)
                require(observed in (before, before-pending),
                        'Parent download frontier differs from its received DATA prefix')
        terminal = channel.get('namespace_closed')
        require(isinstance(terminal, dict) and h2_facts(terminal.get('h2')) == h2_facts(final),
                'Parent frontier final H2 differs from namespace terminal')
        if terminal.get('reason') == 'clean_idle_eof':
            require(terminal.get('finish_frontier') is None,
                    'Idle channel uses an invented namespace finish frontier')
            earlier_close = [event for event in rows if event.get('kind') == 'channel_closed'
                             and event.get('channel_id') == cid and event['sequence'] < row['sequence']]
            if earlier_close:
                require(frontier == final, 'Already closed idle channel parent frontier changed')
        elif not diagnostic or terminal.get('finish_frontier') is not None:
            # The namespace observes FINISH later, after its own framed input.
            # Both actual frontiers independently constrain final resets/streams.
            channel_h2(terminal['h2'], terminal.get('finish_frontier'), complete=not diagnostic)
    return len(frontiers)


def one_event(rows, kind):
    found = [row for row in rows if row.get('kind') == kind]
    require(len(found) == 1, 'Owner drain event missing or duplicated: ' + kind)
    return found[0]


def h2_progress(value, earlier, *, complete=False):
    """Monotone evidence after the original frontier; never create authority."""
    h2_summary(value, complete=complete); h2_summary(earlier, complete=False)
    cleanup_transport.progress(value, earlier)
    _, terminals = cleanup_transport.records(value)
    require(value['last_stream_id'] == earlier['last_stream_id']
            and value['closed_streams'] >= earlier['closed_streams']
            and value['reset_records'][:len(earlier['reset_records'])] == earlier['reset_records']
            and value['terminal_control_records'][:len(earlier['terminal_control_records'])]
                == earlier['terminal_control_records']
            and (not earlier['retiring'] or all(i in terminals
                 for i in range(len(earlier['terminal_control_records']),len(value['terminal_control_records']))))
            and all(value[key][direction] >= earlier[key][direction]
                    for key in ('bytes', 'frames') for direction in ('upload', 'download')),
            'Owner drain H2 progress reversed or created a new stream')


def terminal_control_progress(value, earlier):
    h2_summary(value, complete=False); h2_summary(earlier, complete=False)
    cleanup_transport.progress(value, earlier)
    _, terminals = cleanup_transport.records(value)
    records = earlier['terminal_control_records']
    require(value['terminal_control_records'][:len(records)] == records
            and (not earlier['retiring'] or all(i in terminals for i in range(len(records),len(value['terminal_control_records'])))),
            'HTTP2 terminal control evidence changed or disappeared after observation')


def owner_drain_integrity(rows, namespace, receipt, channels, marker, *, diagnostic=False):
    """Two independently ordered endpoints, one original parent 25-second bound.

    Distinct endpoint frontiers are not compared as simultaneous snapshots.
    Their exact ledger projections, stream authority and directional prefixes
    are checked instead. Diagnostic rejection never enters ordinary acceptance.
    """
    begin = one_event(rows, 'owner_drain_begin')
    ack = one_event(rows, 'owner_drain_ack')
    seal = one_event(rows, 'owner_finishing')
    terminal = one_event(rows, 'namespace_finished')
    output_closed = one_event(rows, 'namespace_output_closed')
    parent_frames = [r for r in rows if r.get('kind') == 'frame']
    controls = {kind: [r for r in parent_frames if r.get('frame_type') == kind]
                for kind in (10, 11, 7)}
    require(all(len(found) == 1 for found in controls.values()), 'Owner drain control multiplicity differs')
    sent, received, finished = (controls[k][0] for k in (10, 11, 7))
    require(begin['sequence'] < sent['sequence'] < received['sequence'] < ack['sequence']
            < seal['sequence'] < finished['sequence'] < terminal['sequence'] < output_closed['sequence']
            and sent.get('direction') == finished.get('direction') == 'outgoing'
            and received.get('direction') == 'incoming', 'Owner drain handshake/seal order differs')
    start = begin.get('start_monotonic_s'); deadline = begin.get('deadline_monotonic_s')
    require(finite(start) and start == marker['monotonic_s'] and finite(deadline)
            and deadline == start + 25 and type(begin.get('bound_s')) is int and begin['bound_s'] == 25
            and start <= begin['monotonic_s'] <= deadline,
            'Owner drain does not use the original durable 25-second deadline')
    drain = receipt.get('drain')
    require(isinstance(drain, dict) and set(drain) == {
        'start_monotonic_s', 'deadline_monotonic_s', 'bound_s', 'seal_qualified',
        'seal_error_code', 'completed_monotonic_s'} and drain['start_monotonic_s'] == start
        and drain['deadline_monotonic_s'] == deadline and type(drain['bound_s']) is int
        and drain['bound_s'] == 25 and type(drain['seal_qualified']) is bool
        and drain['seal_qualified'] == seal.get('seal_qualified')
        and drain['seal_error_code'] == seal.get('seal_error_code')
        and finite(drain['completed_monotonic_s'])
        and output_closed['monotonic_s'] <= drain['completed_monotonic_s'] <= deadline,
        'Owner drain completion/deadline or final seal projection differs')
    completed = one_event(rows, 'owner_drain_completed')
    require({key:completed.get(key) for key in drain} == drain and output_closed['sequence'] < completed['sequence']
            and completed['monotonic_s'] >= drain['completed_monotonic_s']
            and all(r['sequence'] < completed['sequence'] for r in rows if r.get('kind') == 'channel_closed'),
            'Owner drain completion receipt precedes observed closures or differs')
    require((drain['seal_qualified'] is True and drain['seal_error_code'] is None)
            or diagnostic and drain['seal_qualified'] is False
            and drain['seal_error_code'] == 'drain_invalid',
            'Owner drain sealing did not qualify')
    auths = [r for r in rows if r.get('kind') == 'channel_authenticated']
    require(all(r['sequence'] < begin['sequence'] for r in auths), 'New channel admitted during owner drain')
    seals = [r for r in rows if r.get('kind') == 'channel_seal_frontier']
    require([r.get('channel_id') for r in seals] == list(channels)
            and all(type(r.get('channel_id')) is int for r in seals),
            'Owner seal frontier identity or multiplicity differs')
    for cid, channel in channels.items():
        original = next(r for r in rows if r.get('kind') == 'channel_finish_frontier' and r.get('channel_id') == cid)
        sealed = next(r for r in seals if r['channel_id'] == cid)
        require(original['sequence'] < sent['sequence'] and received['sequence'] < sealed['sequence'] < seal['sequence']
                and sealed.get('h2') == channel.get('seal_frontier'), 'Owner original/seal frontier projection or order differs')
        frontier, final, snapshot = channel['finish_frontier'], channel['h2'], sealed['h2']
        channel_h2(snapshot, frontier, complete=False)
        require(diagnostic or snapshot['upload_complete'] is True, 'Partial upload at final seal')
        h2_progress(final, snapshot, complete=not diagnostic)
        idle = any(r.get('frame_type') == 5 and r.get('channel_id') == cid
                   and r['sequence'] < original['sequence'] for r in parent_frames)
        require(snapshot['retiring'] is (not idle) and final['retiring'] is (not idle),
                'Owner H2 retirement gate differs from its original phase')
        eof = [r for r in rows if r.get('kind') == 'client_eof' and r.get('channel_id') == cid]
        drained = [r for r in rows if r.get('kind') == 'upload_drained' and r.get('channel_id') == cid]
        half = [r for r in parent_frames if r.get('frame_type') == 4 and r.get('channel_id') == cid]
        require(len(eof) == len(drained) == len(half) == 1 and channel.get('parent_eof') == eof[0]
                and channel.get('upload_drained') == drained[0]
                and eof[0]['sequence'] < half[0]['sequence'] < drained[0]['sequence'] < sealed['sequence'],
                'Owner seal lacks genuine upload EOF and ordered drain')
        meters = drained[0].get('meters')
        require(isinstance(meters, dict) and set(meters) == set(channel['meters']), 'Upload drain byte meters missing')
        for name, identity in meters.items(): stream_identity(identity, 'upload drain ' + name)
        require(meters['client_read'] == meters['upload'] == channel['meters']['upload']
                and all(meters[name]['bytes'] <= channel['meters'][name]['bytes']
                        for name in ('download', 'client_written')), 'Upload drain lost or invented bytes')
        require(snapshot['bytes']['upload'] == final['bytes']['upload']
                and snapshot['frames']['upload'] == final['frames']['upload'], 'Upload progressed after final sealing')

    nsbegin = one_event(namespace, 'owner_drain_begin')
    nsack = one_event(namespace, 'owner_drain_ack')
    nsfinish = one_event(namespace, 'owner_finish')
    nsframes = [r for r in namespace if r.get('kind') == 'frame']
    nscontrols = {kind: one_event([dict(r, kind=str(r.get('frame_type'))) for r in nsframes], str(kind))
                  for kind in (10, 11, 7)}
    require(nscontrols[10]['sequence'] < nsbegin['sequence'] < nscontrols[11]['sequence']
            < nsack['sequence'] < nscontrols[7]['sequence'] < nsfinish['sequence'],
            'Namespace drain handshake/seal order differs')
    nsstart, nsdeadline = nsbegin.get('start_monotonic_s'), nsbegin.get('deadline_monotonic_s')
    require(finite(nsstart) and finite(nsdeadline) and nsdeadline == nsstart+25
            and type(nsbegin.get('bound_s')) is int and nsbegin['bound_s'] == 25
            and all(type(r.get('channels')) is int and r['channels'] == len(channels)
                    for r in (nsbegin, nsack, nsfinish)), 'Namespace drain bound or channel cardinality differs')
    nsfinal = namespace[-1]
    require(nsfinal.get('owner_drain_received') is True and nsfinal.get('owner_drain_acknowledged') is True
            and type(nsfinal.get('owner_drain_timeout_s')) is int and nsfinal['owner_drain_timeout_s'] == 25
            and finite(nsfinal.get('owner_drain_elapsed_s')) and nsfinal['owner_drain_elapsed_s'] <= 25
            and (nsfinal.get('drain_qualified') is True and nsfinal.get('drain_error_code') is None
                 or diagnostic and nsfinal.get('drain_qualified') is False
                 and nsfinal.get('drain_error_code') == 'owner_drain_unqualified'),
            'Namespace drain acknowledgment, completion or deadline unproven')
    require(nsstart <= nsbegin['monotonic_s'] <= nsfinish['monotonic_s'] <= nsdeadline
            and all(r['monotonic_s'] - nsstart <= nsfinal['owner_drain_elapsed_s']
                    for r in namespace if r.get('kind') == 'channel_closed'
                    and r['sequence'] > nsbegin['sequence']),
            'Namespace declared elapsed bound omits actual drain/closure observations')
    require(nsfinish.get('seal_qualified') is True and nsfinish.get('seal_error_code') is None,
            'Namespace seal never qualified')
    nsfronts = [r for r in namespace if r.get('kind') == 'channel_finish_frontier']
    require([r.get('channel_id') for r in nsfronts] == list(channels)
            and all(type(r.get('channel_id')) is int for r in nsfronts), 'Namespace original frontier multiplicity differs')
    for row in nsfronts:
        cid = row['channel_id']; channel = channels[cid]; end = channel['namespace_closed']
        original = h2_summary(row.get('h2'), complete=False)
        require(nsbegin['sequence'] < row['sequence'] < nsack['sequence'] and type(row.get('already_closed')) is bool,
                'Namespace original frontier phase differs')
        closed = one_event([dict(r, kind=str(r.get('receipt', {}).get('channel_id')))
                            for r in namespace if r.get('kind') == 'channel_closed'], str(cid))
        require(row['already_closed'] == (closed['sequence'] < row['sequence']), 'Namespace idle closure frontier changed')
        if row['already_closed']:
            require(original == end['h2'] and end.get('finish_frontier') is None and end.get('seal_frontier') is None,
                    'Namespace replaced immutable earlier idle closure')
        else:
            require(original == end.get('finish_frontier') and original['retiring'] is False,
                    'Namespace original frontier receipt differs')
            channel_h2(end.get('seal_frontier'), original, complete=False)
            require(diagnostic or end['seal_frontier']['upload_complete'] is True, 'Partial namespace upload at final seal')
            h2_progress(end['h2'], end['seal_frontier'], complete=not diagnostic)
            require(end['seal_frontier']['retiring'] is True and end['h2']['retiring'] is True,
                    'Namespace H2 retirement gate absent')
            require(end['seal_frontier']['bytes']['upload'] == end['h2']['bytes']['upload']
                    and end['seal_frontier']['frames']['upload'] == end['h2']['frames']['upload'],
                    'Namespace upload progressed after final seal')
        data = [r for r in nsframes if r.get('channel_id') == cid and r.get('frame_type') == 3]
        for direction, framed in (('upload', 'incoming'), ('download', 'outgoing')):
            seen = sum(r['payload_bytes'] for r in data if r.get('direction') == framed and r['sequence'] < row['sequence'])
            # Namespace upload is fed synchronously after its frame record;
            # download feed precedes the async framed write and can lead it.
            total, prefixes = 0, {0}
            for event in data:
                if event.get('direction') == framed:
                    total += event['payload_bytes']; prefixes.add(total)
            observed = original['bytes'][direction]
            require(observed in prefixes and (observed == seen if direction == 'upload' else seen <= observed <= total),
                    'Namespace original frontier is not its causal DATA prefix')
        eof = [r for r in namespace if r.get('kind') == 'channel_eof' and r.get('channel_id') == cid and r.get('direction') == 'upload']
        drains = [r for r in namespace if r.get('kind') == 'channel_upload_drained' and r.get('channel_id') == cid]
        require(len(eof) == len(drains) == 1 and eof[0]['sequence'] < drains[0]['sequence'] < nsfinish['sequence']
                and drains[0].get('upload') == end['upload'] and end.get('upload_eof') is True
                and end.get('upload_drained') is True and (diagnostic or end.get('download_eof') is True),
                'Namespace seal lacks genuine upload EOF and complete byte drain')
        require(type(drains[0].get('owner_finishing')) is bool
                and drains[0]['owner_finishing'] == (drains[0]['sequence'] > nsbegin['sequence']),
                'Namespace upload drain phase differs')
    return {'bound_s': 25, 'original_frontiers': len(channels), 'seal_qualified': drain['seal_qualified']}


def client_owner(root, bindings, owner, owner_kind, allow_empty=False):
    root = Path(root)
    retained = document(root / 'client/native-owner.json', bindings)
    require(retained == owner, 'Client and bridge native owner identities differ')
    owner_file_binding = dict(bindings['native-owner.json'])
    rows = json_lines(root / 'client/events.jsonl', bindings, 32 * 1024 * 1024)
    registration = [(i, row) for i, row in enumerate(rows)
                    if row.get('kind') == 'native_process_owner_registered']
    finish = [(i, row) for i, row in enumerate(rows) if row.get('kind') == 'client_finishing_before_close']
    shutdown_kind = 'client_shutdown' if owner_kind == 'model_client' else 'probe_client_closed'
    shutdown = [(i, row) for i, row in enumerate(rows) if row.get('kind') == shutdown_kind]
    require(len(registration) == len(finish) == len(shutdown) == 1
            and registration[0][0] < finish[0][0] < shutdown[0][0] == len(rows)-1
            and (owner_kind == 'model_client' or finish[0][0] == len(rows)-2),
            'Client owner registration/finishing/shutdown order or uniqueness differs')
    registered = registration[0][1]
    require(set(registered) == {'kind', 'receipt_sha256', 'receipt_bytes'}
            and type(registered['receipt_bytes']) is int
            and registered['receipt_bytes'] == owner_file_binding['bytes']
            and registered['receipt_sha256'] == owner_file_binding['sha256'],
            'Client durable owner registration receipt differs')
    marker = finish[0][1]
    require(set(marker) == {'kind', 'schema', 'wall_unix_s', 'monotonic_s'}
            and marker['schema'] == 'campaign002-client-finishing-1'
            and finite(marker['wall_unix_s']) and finite(marker['monotonic_s'])
            and marker['monotonic_s'] >= owner['monotonic_s'], 'Client owner-finishing marker malformed')
    ending = shutdown[0][1]
    if owner_kind == 'model_client':
        require(not any(row.get('kind') == 'probe_client_closed' for row in rows)
                and type(ending.get('exit_code')) is int and ending['exit_code'] == 0,
                'Native client did not exit normally or has diagnostic owner markers')
        launch = document(root / 'client/launch.json', bindings)
        require(launch.get('binary') == owner['executable']['path']
                and launch.get('binary_sha256') == owner['executable']['sha256'],
                'Registered owner differs from native client launch binary')
        if allow_empty:
            result = document(root / 'client/result.json', bindings)
            require(launch.get('bootstrap_requested') is False and result.get('model_started') is False
                    and result.get('success') is True, 'Empty transport requires completed zero-model preflight')
        # The bootstrap source records registration before sending initialize.
        initialize = [i for i, row in enumerate(rows)
                      if row.get('kind') == 'request' and row.get('method') == 'initialize']
        require(len(initialize) == 1 and initialize[0] > registration[0][0]
                and all(i > registration[0][0] for i, row in enumerate(rows) if row.get('kind') == 'request'),
                'Native initialization missing, duplicated or preceding owner registration')
    else:
        require(not any(row.get('kind') == 'client_shutdown' for row in rows)
                and ending.get('schema') == 'campaign002-h2-probe-client-1' and ending.get('closed') is True
                and finite(ending.get('wall_unix_s')) and finite(ending.get('monotonic_s'))
                and ending['monotonic_s'] >= marker['monotonic_s'], 'Diagnostic owner close receipt differs')
    return marker


def probe_records(root, bindings, owner, marker, case):
    """Bind a fixed diagnostic client's observations without claiming RPC use."""
    require(case in ('multi_channel', 'boundary_single_channel', 'foreign_owner', 'in_flight_eof'),
            'Undeclared diagnostic case')
    value = document(Path(root) / 'client-result.json', bindings)
    require(value.get('schema') == 'campaign002-channel-client-3' and value.get('case') == case
            and value.get('completed') is True and type(value.get('model_calls')) is int
            and value['model_calls'] == 0, 'Diagnostic client completion or zero-model scope differs')
    observed_owner = value.get('owner')
    require(observed_owner == {key: owner[key] for key in
        ('pid', 'process_creation_filetime', 'queried_executable_path', 'executable')},
        'Probe OS owner differs from registered native owner')
    roles = {'owner', 'foreign'} if case == 'foreign_owner' else {'owner'}
    exits = value.get('child_exit_codes')
    require(isinstance(exits, dict) and set(exits) == roles
            and all(type(code) is int and code == 0 for code in exits.values())
            and value.get('finish') == marker, 'Probe child exits or durable finish identity differs')
    result = value.get('result')
    require(isinstance(result, dict) and result.get('ready_to_finish') is True
            and isinstance(result.get('channels'), list), 'Probe result is incomplete')
    transcript = json_lines(Path(root) / 'client-transcript.jsonl', bindings)
    for row in transcript:
        require(set(row) == {'schema', 'role', 'event', 'received_wall_unix_s'}
                and row['schema'] == 'campaign002-channel-probe-transcript-3'
                and row['role'] in roles | {'controller'} and finite(row['received_wall_unix_s'])
                and isinstance(row['event'], dict) and isinstance(row['event'].get('kind'), str)
                and finite(row['event'].get('wall_unix_s')) and finite(row['event'].get('monotonic_s')),
                'Probe transcript schema, clock or role differs')
    controller = [row for row in transcript if row['role'] == 'controller']
    require(len(controller) == 1 and controller[0]['event'] == marker,
            'Probe transcript lacks unique identical controller finish')
    active_role = 'foreign' if case == 'foreign_owner' else 'owner'
    ready = [row for row in transcript if row['role'] == active_role
             and row['event']['kind'] == 'ready_to_finish']
    require(len(ready) == 1 and ready[0]['event'].get('result') == result
            and transcript.index(ready[0]) < transcript.index(controller[0]),
            'Probe result differs from actual child observation before finish')
    for role in roles:
        records = [row for row in transcript if row['role'] == role]
        first = [row for row in records if row['event']['kind'] == 'client_ready']
        ending = [row for row in records if row['event']['kind'] == 'client_closed']
        finishing = [row for row in records if row['event']['kind'] == 'client_finishing']
        identity = observed_owner if role == 'owner' else value.get('sibling')
        require(isinstance(identity, dict) and len(first) == len(ending) == len(finishing) == 1
                and type(first[0]['event'].get('pid')) is int
                and first[0]['event']['pid'] == identity.get('pid')
                and transcript.index(first[0]) < transcript.index(controller[0])
                < transcript.index(finishing[0]) < transcript.index(ending[0])
                and marker['monotonic_s'] <= finishing[0]['event']['monotonic_s'],
                'Probe child identity, finishing control or complete exit observation differs')
    return value, transcript


def probe_shutdown_phases(root, bindings, client, transcript, rows, channel, marker):
    """Join the fixed probe's ready snapshot and its later shutdown bytes.

    The child retains its sent meter before closing intent. The declared single
    GOAWAY follows the protected pending-read acknowledgment, so that earlier
    meter must not be compared directly with the final transport meter. Match
    every retained DATA slice against the independently known fixed workload;
    no missing payload or final child meter is reconstructed from metadata.
    """
    baseline = (b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'
                + bytes.fromhex('000000040000000000000000040100000000')
                + bytes.fromhex('000008060000000000') + b'C02V3H2!')
    shutdown = bytes.fromhex('0000080700000000000000000000000000')
    identity = lambda raw: {'bytes': len(raw), 'sha256': digest(raw)}
    proof = client.get('pending_read_shutdown')
    fields = {'schema', 'frontier', 'drain_begin', 'acknowledgment', 'retained_ledger_prefix',
              'grant_monotonic_s', 'control_sent_monotonic_s', 'deadline_monotonic_s',
              'shutdown_bytes', 'shutdown_sha256'}
    require(isinstance(proof, dict) and set(proof) == fields
            and proof['schema'] == 'campaign002-pending-read-shutdown-1'
            and type(proof['shutdown_bytes']) is int and proof['shutdown_bytes'] == len(shutdown)
            and proof['shutdown_sha256'] == digest(shutdown), 'Fixed probe shutdown proof or bytes differ')
    for key, kind in (('frontier', 'channel_finish_frontier'), ('drain_begin', 'owner_drain_begin'),
                      ('acknowledgment', 'owner_drain_ack')):
        row = proof[key]
        require(isinstance(row, dict) and row.get('kind') == kind and integer(row.get('sequence'), 1)
                and [r for r in rows if r.get('sequence') == row['sequence']] == [row],
                'Probe shutdown protected event differs')
    front, begin, ack = (proof[key] for key in ('frontier', 'drain_begin', 'acknowledgment'))
    require(type(front.get('channel_id')) is int and front['channel_id'] == 1
            and front.get('upload_read_pending') is True
            and front.get('h2') == channel.get('finish_frontier')
            and front['h2']['bytes']['upload'] == len(baseline)
            and front['sequence'] < begin['sequence'] < ack['sequence']
            and all(finite(proof[key]) for key in
                    ('grant_monotonic_s', 'control_sent_monotonic_s', 'deadline_monotonic_s'))
            and ack['monotonic_s'] <= proof['grant_monotonic_s']
            <= proof['control_sent_monotonic_s'] < proof['deadline_monotonic_s']
            <= marker['monotonic_s'] + 25, 'Probe shutdown pending read or chronology differs')
    declared = client['result']['channels'][0]
    stream_identity(declared.get('sent'), 'probe before-closing sent bytes')
    require(declared['sent'] == identity(baseline), 'Fixed probe before-closing baseline differs')
    data = [row for row in rows if row['kind'] == 'frame' and row.get('direction') == 'outgoing'
            and row.get('frame_type') == 3 and row.get('channel_id') == 1]
    before = [row for row in data if row['sequence'] < front['sequence']]
    after = [row for row in data if row['sequence'] > front['sequence']]
    for phase, expected, label in ((before, baseline, 'baseline'), (after, shutdown, 'shutdown')):
        offset = 0
        for row in phase:
            count = row.get('payload_bytes')
            require(integer(count, 1) and count <= MAX_FRAME_PAYLOAD,
                    'Probe ' + label + ' DATA size differs')
            part = expected[offset:offset + count]
            require(len(part) == count and row.get('payload_sha256') == digest(part),
                    'Probe ' + label + ' DATA slice differs')
            offset += count
        require(offset == len(expected), 'Probe ' + label + ' DATA incomplete or duplicated')
    eof = [row for row in rows if row['kind'] == 'client_eof' and row.get('channel_id') == 1]
    half = [row for row in rows if row['kind'] == 'frame' and row.get('direction') == 'outgoing'
            and row.get('frame_type') == 4 and row.get('channel_id') == 1]
    seal = [row for row in rows if row['kind'] == 'owner_finishing']
    require(len(eof) == len(half) == len(seal) == 1 and eof[0].get('client_finishing') is True
            and ack['sequence'] < eof[0]['sequence'] < half[0]['sequence'] < seal[0]['sequence']
            and all(ack['sequence'] < row['sequence'] < half[0]['sequence']
                    and proof['grant_monotonic_s'] <= row['monotonic_s']
                    < proof['deadline_monotonic_s'] for row in after),
            'Probe shutdown DATA, genuine EOF or seal ordering differs')
    prefix = proof['retained_ledger_prefix']
    require(isinstance(prefix, dict) and set(prefix) == {'path', 'bytes', 'sha256'}
            and prefix['path'] == 'codehost-transport-v3.jsonl' and integer(prefix['bytes'], 1)
            and hash_value(prefix['sha256']), 'Probe shutdown ledger prefix identity differs')
    # Read the actual bounded ledger bytes again, requiring the same complete
    # identity already admitted above; do not silently replace the input binding.
    ledger_identity = bindings['codehost-transport-v3.jsonl']
    raw = read_file(Path(root) / 'codehost-transport-v3.jsonl', {})
    require(identity(raw) == ledger_identity and prefix['bytes'] <= len(raw),
            'Probe shutdown ledger changed or prefix exceeds retained bytes')
    raw_prefix = raw[:prefix['bytes']]
    require(raw_prefix.endswith(b'\n') and digest(raw_prefix) == prefix['sha256'],
            'Probe shutdown ledger prefix bytes differ')
    prefix_rows = [decode(line, 'probe shutdown prefix') for line in raw_prefix.splitlines()]
    require(rows[:len(prefix_rows)] == prefix_rows
            and ack['sequence'] <= len(prefix_rows) < after[0]['sequence'],
            'Probe shutdown prefix omits ACK or already includes shutdown DATA')
    control = [row for row in transcript if row['event']['kind'] == 'channel_shutdown_control']
    owner_finish = [row for row in transcript if row['role'] == 'owner'
                    and row['event']['kind'] == 'client_finishing']
    owner_close = [row for row in transcript if row['role'] == 'owner'
                   and row['event']['kind'] == 'client_closed']
    require(len(control) == len(owner_finish) == len(owner_close) == 1
            and control[0]['role'] == 'owner'
            and set(control[0]['event']) == {'kind', 'channel_id', 'bytes', 'sha256', 'wall_unix_s', 'monotonic_s'}
            and type(control[0]['event'].get('channel_id')) is int and control[0]['event']['channel_id'] == 1
            and type(control[0]['event'].get('bytes')) is int and control[0]['event']['bytes'] == len(shutdown)
            and control[0]['event'].get('sha256') == digest(shutdown)
            and transcript.index(owner_finish[0]) < transcript.index(control[0]) < transcript.index(owner_close[0])
            and proof['grant_monotonic_s'] <= owner_finish[0]['event']['monotonic_s']
            <= control[0]['event']['monotonic_s'] <= owner_close[0]['event']['monotonic_s']
            < proof['deadline_monotonic_s'], 'Probe shutdown child control identity or order differs')
    # control_sent is sampled after the blocking pipe write returns. The child
    # and relay can already have processed it then; grant precedes that write
    # and is the source-supported lower bound on their observations.
    stream_identity(channel['meters'].get('client_read'), 'probe final sent bytes')
    require(channel['meters']['client_read'] == identity(baseline + shutdown),
            'Fixed probe final baseline plus shutdown bytes differ')


def retirement_integrity(value, *, expected_exit_code=0):
    require(value.get('qualified') is True and value.get('normal_wait_timed_out') is False
            and value.get('windows_wrapper_killed_after_linux_retired') is False
            and type(value.get('windows_exit_code')) is int and value['windows_exit_code'] == expected_exit_code,
            'Codehost retirement did not complete normally')
    observations = value.get('observations')
    require(isinstance(observations, list) and bool(observations)
            and all(isinstance(row, dict) for row in observations), 'Missing retirement observations')
    end = observations[-1]
    require(end.get('retired') is True and end.get('namespace_evidence_available') is True
            and end.get('outer_same_process') is False and end.get('namespace_members') == []
            and isinstance(end.get('namespace_ids'), list) and bool(end['namespace_ids'])
            and all(integer(item, 1) for item in end['namespace_ids']),
            'Final retirement lacks empty namespace and process identity evidence')
    return {'namespace_ids': end['namespace_ids'], 'windows_exit_code': value['windows_exit_code']}


def single_host_artifacts(root):
    root = Path(root)
    require({p.name for p in root.glob('codehost*retirement*.json')}
            == {'codehost-owner-retirement-v3.json'}
            and {p.name for p in root.glob('codehost*bridge*.json')}
            == {'codehost-owner-bridge-v3.json'},
            'Additional or missing codehost namespace/retirement artifacts')


def namespace_integrity(raw, receipt, sources, channels):
    require(bool(raw) and raw.endswith(b'\n'), 'Namespace stderr missing or truncated')
    try:
        lines = raw.decode('utf-8', errors='strict').splitlines()
    except UnicodeError as error:
        raise ValueError('Namespace metadata is not UTF8') from error
    prefix = 'RCI_CODEHOST_V3 '
    require(len(lines) <= 16384 and all(line.startswith(prefix) for line in lines),
            'Namespace metadata bound or unframed child output')
    rows = [decode(line[len(prefix):], 'namespace metadata') for line in lines]
    require(all(isinstance(row, dict) for row in rows), 'Namespace metadata must be objects')
    metadata_sequence(rows, NAMESPACE_SCHEMA)
    require(rows == receipt.get('namespace_records'), 'Namespace retained projection differs from stderr')
    kinds = [row.get('kind') for row in rows]
    allowed = {'open', 'child_started', 'ready', 'frame', 'channel_open', 'channel_eof',
               'channel_closed', 'owner_drain_begin', 'channel_finish_frontier', 'owner_drain_ack',
               'channel_upload_drained', 'owner_finish', 'child_diagnostic', 'closed'}
    if cleanup_transport.METHOD in sources:
        allowed |= {'native_cleanup_begin','native_cleanup_channel'}
    require(set(kinds) <= allowed and kinds[0] == 'open' and kinds[-1] == 'closed'
            and all(kinds.count(kind) == 1 for kind in ('open', 'child_started', 'ready', 'owner_drain_begin', 'owner_drain_ack', 'owner_finish', 'closed')),
            'Namespace has failure, duplicate host or incomplete lifecycle')
    inside_sources = {name: sources[CAMPAIGN + 'harness/' + name]
                      for name in ('codehost_inside_v3.py', 'codehost_mux_protocol.py')}
    if cleanup_transport.METHOD in sources:
        inside_sources['native_cleanup_protocol.py'] = sources[CAMPAIGN+'harness/native_cleanup_protocol.py']
    opening, final = rows[0], rows[-1]
    require(opening.get('sources') == final.get('sources') == inside_sources
            and type(opening.get('max_records')) is int and opening['max_records'] == 16384
            and type(opening.get('max_metadata_bytes')) is int
            and opening['max_metadata_bytes'] == MAX_METADATA_BYTES,
            'Namespace source identity or bounds differ')
    child = next(row for row in rows if row['kind'] == 'child_started')
    ready = next(row for row in rows if row['kind'] == 'ready')
    finish = next(row for row in rows if row['kind'] == 'owner_finish')
    drain_begin = next(row for row in rows if row['kind'] == 'owner_drain_begin')
    require(integer(child.get('child_pid'), 1) and ready.get('receipt') == receipt.get('ready')
            and ready['receipt'].get('child_pid') == child['child_pid'] == final.get('child_pid')
            and child['sequence'] < ready['sequence'] < finish['sequence'] < final['sequence'],
            'Shared native child identity or namespace order differs')
    require(final == receipt.get('finished') and final.get('qualified') is True
            and final.get('reason') == 'owner_finish' and final.get('owner_finish_received') is True
            and final.get('stdin_eof') is True
            and type(final.get('owner_input_wait_bound_s')) in (int, float)
            and final['owner_input_wait_bound_s'] == .5
            and final.get('error_type') is None and final.get('kill_sent') is False
            and final.get('diagnostic_streams_complete') is True
            and type(final.get('terminate_sent')) is bool
            and type(final.get('child_exit_code')) is int
            and (final['child_exit_code'] == 0 or final['terminate_sent'] is True and final['child_exit_code'] == -15)
            and (final.get('child_exit_before_cleanup') is None
                 or type(final['child_exit_before_cleanup']) is int and final['child_exit_before_cleanup'] == 0),
            'Shared native child or owner cleanup is unhealthy')
    require(all(type(final.get(key)) is int and final[key] == len(channels)
                for key in ('channel_count', 'channels_closed'))
            and type(finish.get('channels')) is int and finish['channels'] == len(channels)
            and type(final.get('queue_bytes_at_close')) is int and final['queue_bytes_at_close'] == 0
            and integer(final.get('queue_high_water_bytes'))
            and final['queue_high_water_bytes'] <= MAX_AGGREGATE_QUEUE_BYTES,
            'Namespace channel closure or queued-byte accounting differs')
    queue_accounting(final, channels, namespace=True)
    diagnostics = [row for row in rows if row['kind'] == 'child_diagnostic']
    require(len(diagnostics) == 2 and {row.get('stream') for row in diagnostics} == {'stdout', 'stderr'}
            and all(integer(row.get('bytes')) and hash_value(row.get('sha256'))
                    and row.get('truncated') is False
                    and (row['bytes'] != 0 or row['sha256'] == digest(b''))
                    and child['sequence'] < row['sequence'] < final['sequence'] for row in diagnostics)
            and sum(row['bytes'] for row in diagnostics) <= MAX_METADATA_BYTES,
            'Child diagnostic streams missing, malformed or truncated')
    opens = [row for row in rows if row['kind'] == 'channel_open']
    closes = [row for row in rows if row['kind'] == 'channel_closed']
    require(all(type(row.get('channel_id')) is int for row in opens)
            and all(isinstance(row.get('receipt'), dict)
                    and type(row['receipt'].get('channel_id')) is int for row in closes)
            and [row.get('channel_id') for row in opens] == list(channels)
            and len(closes) == len(channels)
            and {row['receipt']['channel_id'] for row in closes} == set(channels)
            and all(row.get('child_pid') == child['child_pid']
                    and ready['sequence'] < row['sequence'] < finish['sequence'] for row in opens),
            'Namespace channel allocation or shared child differs')
    for row in closes:
        cid = row['receipt']['channel_id']
        require(row.get('receipt') == channels[cid]['namespace_closed']
                and next(x['sequence'] for x in opens if x['channel_id'] == cid) < row['sequence'],
                'Namespace channel-close payload or ordering differs')
        if row['receipt']['reason'] == 'owner_finish':
            require(finish['sequence'] < row['sequence'], 'Owner-finish channel closed before FINISH')
    for row in rows:
        if row['kind'] != 'channel_eof':
            continue
        require(type(row.get('channel_id')) is int and row.get('channel_id') in channels
                and row.get('direction') in ('upload', 'download')
                and type(row.get('owner_finishing')) is bool, 'Namespace EOF observation malformed')
        h2_summary(row.get('h2'))
        if row['owner_finishing']:
            require(row['sequence'] > drain_begin['sequence'], 'Namespace EOF falsely claims earlier owner drain')
        else:
            require(row['sequence'] < drain_begin['sequence'], 'Namespace EOF phase contradicts DRAIN_BEGIN order')
            idle_h2(row['h2'])
        observed = channels[row['channel_id']]['namespace_closed'].get(row['direction'] + '_eof_h2')
        require(observed == row['h2'], 'Namespace EOF projection differs from its original observation')
        terminal_control_progress(channels[row['channel_id']]['namespace_closed']['h2'], observed)
    frames = [row for row in rows if row['kind'] == 'frame']
    require(isinstance(final.get('frame_counts'), dict)
            and all(type(value) is int for value in final['frame_counts'].values())
            and final.get('frame_counts') == {
        direction: sum(row.get('direction') == direction for row in frames)
        for direction in ('incoming', 'outgoing')}, 'Namespace frame counts differ')
    return rows, {'child_pid': child['child_pid'], 'child_exit_code': final['child_exit_code'],
                  'channels': len(channels), 'records': len(rows)}


def verify_transport_integrity(stage_root, frozen, *, owner_kind='model_client', allow_empty=False):
    """Read one complete v3 invocation after external official queue admission.

    allow_empty is exclusively the separately source-bound, zero-model native
    metadata preflight. It still requires one eager host/namespace and retirement.
    """
    require(type(allow_empty) is bool, 'Empty preflight flag must be a literal boolean')
    root, bindings = Path(stage_root), {}
    single_host_artifacts(root)
    sources = source_bindings(frozen, owner_kind, allow_empty)
    expected_sources = {name: sources[name] for name in BRIDGE_SOURCE_NAMES}
    if cleanup_transport.METHOD in sources:
        expected_sources[CAMPAIGN+'harness/native_cleanup_protocol.py'] = sources[CAMPAIGN+'harness/native_cleanup_protocol.py']
    rows = json_lines(root / 'codehost-transport-v3.jsonl', bindings)
    require(len(rows) <= 16384, 'Parent metadata record bound exceeded')
    metadata_sequence(rows, TRANSPORT_SCHEMA, hash_chain=True)
    kinds = [row.get('kind') for row in rows]
    if cleanup_transport.METHOD not in sources:
        require(not any(kind in ('native_cleanup_begin','native_cleanup_ack','native_cleanup_channel') for kind in kinds)
                and not any(r.get('kind')=='frame' and r.get('frame_type') in (12,13) for r in rows),
                'Cleanup barrier lacks declared frozen method')
    require(set(kinds) <= PARENT_KINDS and kinds[0] == 'open' and kinds[-1] == 'closed'
            and all(kinds.count(kind) == 1 for kind in (
                'open', 'namespace_started', 'listening', 'owner_registered', 'owner_drain_begin', 'owner_drain_ack',
                'owner_drain_completed', 'owner_finishing',
                'owner_input_closed', 'namespace_finished', 'namespace_output_closed', 'retirement_started', 'closed')),
            'Owner transport has failure, denial, duplicate namespace or incomplete lifecycle')
    opening, end = rows[0], rows[-1]
    require(opening.get('sources') == expected_sources, 'Bridge opening source identities differ')
    opening_bounds(opening)
    for key, expected in [('max_connections', MAX_CHANNELS), ('max_frame_bytes', MAX_FRAME_PAYLOAD),
                          ('per_channel_queue_bytes', MAX_CHANNEL_QUEUE_BYTES),
                          ('aggregate_queue_bytes', MAX_AGGREGATE_QUEUE_BYTES)]:
        require(type(opening.get(key)) is int and opening[key] == expected,
                'Bridge resource bound differs: ' + key)
    require(end.get('qualified') is True and end.get('failures') == []
            and type(end.get('denied')) is int and end['denied'] == 0
            and integer(end.get('accepted')) and end.get('attempts') == end['accepted']
            and type(end.get('attempts')) is int
            and (end['accepted'] == 0 if allow_empty else 1 <= end['accepted'] <= MAX_CHANNELS),
            'Unexpected or denied channel count, or unqualified transport')
    receipt = bound_document(root, end.get('receipt'), 'codehost-owner-bridge-v3.json', bindings,
                             maximum=MAX_RECEIPT_BYTES)
    require(receipt.get('schema') == 'campaign002-codehost-owner-bridge-3'
            and receipt.get('qualified') is True and receipt.get('failures') == []
            and receipt.get('sources') == expected_sources
            and type(receipt.get('exit_code')) is int and receipt['exit_code'] == 0,
            'Shared owner bridge receipt unqualified or source/status differs')
    for key in ('accepted', 'denied', 'attempts'):
        require(type(receipt.get(key)) is int and receipt[key] == end[key], 'Final channel count differs')
    require(integer(receipt.get('queue_maximum_bytes'))
            and receipt['queue_maximum_bytes'] <= MAX_AGGREGATE_QUEUE_BYTES
            and type(receipt.get('queued_bytes_at_close')) is int
            and receipt['queued_bytes_at_close'] == 0, 'Parent queued-byte accounting differs')
    owner = owner_identity(receipt.get('owner'), owner_kind)
    retained_owner = bound_document(root, receipt.get('owner_receipt'), 'codehost-native-owner-v3.json', bindings)
    registered = next(row for row in rows if row['kind'] == 'owner_registered')
    require(retained_owner == owner == registered.get('owner')
            and registered.get('receipt') == receipt['owner_receipt']
            and registered['monotonic_s'] >= owner['monotonic_s'], 'Durable parent owner registration differs')
    marker = client_owner(root, bindings, owner, owner_kind, allow_empty)
    quiescence = None
    if owner_kind == 'model_client':
        quiescence = client_quiescence.verify_client_quiescence(root, frozen, repo=REPO)
    if owner_kind == 'transport_probe':
        client_result = document(root / 'client-result.json', bindings)
        probe_case = client_result.get('case')
        require(probe_case in ('multi_channel', 'boundary_single_channel'),
                'Expected-failure diagnostics cannot use production transport acceptance')
        if probe_case == 'boundary_single_channel':
            path = REPO / BOUNDARY_SOURCE_NAME
            require(path.is_file() and not path.is_symlink(), 'Boundary transport source unavailable')
            raw_source = path.read_bytes(); identity = {'bytes': len(raw_source), 'sha256': digest(raw_source)}
            require(frozen['sources'].get(BOUNDARY_SOURCE_NAME) == identity
                    and type(frozen['sources'][BOUNDARY_SOURCE_NAME].get('bytes')) is int,
                    'Boundary transport source differs from frozen snapshot')
            sources[BOUNDARY_SOURCE_NAME] = identity
        probe_result, probe_transcript = probe_records(root, bindings, owner, marker, probe_case)
        require(end['accepted'] == (3 if probe_case == 'multi_channel' else 1),
                'Fixed diagnostic channel cardinality differs')
    finishing = next(row for row in rows if row['kind'] == 'owner_finishing')
    terminal = next(row for row in rows if row['kind'] == 'namespace_finished')
    output_closed = next(row for row in rows if row['kind'] == 'namespace_output_closed')
    input_closed = next(row for row in rows if row['kind'] == 'owner_input_closed')
    retirement_start = next(row for row in rows if row['kind'] == 'retirement_started')
    listening = next(row for row in rows if row['kind'] == 'listening')
    require(tcp_endpoint(listening.get('endpoint')), 'Bound listening TCP endpoint missing')
    require(finishing.get('client_finishing') is True
            and marker['monotonic_s'] <= finishing['monotonic_s']
            and marker['wall_unix_s'] <= finishing['wall_unix_s']
            and registered['sequence'] < finishing['sequence'] < input_closed['sequence'] < terminal['sequence']
            < retirement_start['sequence'] < end['sequence'], 'Owner finish/terminal/retirement ordering differs')
    require(input_closed.get('after_finish_drain') is True
            and output_closed.get('after_finished') is True
            and terminal['sequence'] < output_closed['sequence'] < end['sequence'],
            'Complete framing EOF after FINISH/FINISHED is unproven')
    require(type(finishing.get('authenticated_channels')) is int
            and finishing['authenticated_channels'] == end['accepted']
            and type(finishing.get('attempts')) is int and finishing['attempts'] == end['attempts'],
            'Owner-finishing channel cardinality differs')
    raw_channels = receipt.get('channels')
    require(isinstance(raw_channels, list) and len(raw_channels) == end['accepted']
            and all(isinstance(item, dict) and type(item.get('channel_id')) is int for item in raw_channels)
            and [item['channel_id'] for item in raw_channels] == list(range(1, end['accepted'] + 1)),
            'Channel identities absent, reused, unordered or unbounded')
    channels = {item['channel_id']: item for item in raw_channels}
    queue_accounting(receipt, channels)
    if owner_kind == 'transport_probe':
        declared_channels = probe_result['result']['channels']
        require(all(isinstance(item, dict) and type(item.get('channel_id')) is int for item in declared_channels)
                and [item['channel_id'] for item in declared_channels] == list(channels),
                'Fixed probe client channel identities differ')
        for item in declared_channels:
            channel = channels[item['channel_id']]
            require(item.get('client') == channel['authentication']['client']
                    and item.get('server') == channel['authentication']['server'],
                    'Fixed probe authenticated endpoint identity differs')
            if probe_case == 'multi_channel' and item['channel_id'] == 1:
                probe_shutdown_phases(root, bindings, probe_result, probe_transcript, rows, channel, marker)
            else:
                require(item.get('sent') == channel['meters']['client_read'],
                        'Fixed probe sent-byte identity differs')
    auths = [row for row in rows if row['kind'] == 'channel_authenticated']
    closed = [row for row in rows if row['kind'] == 'channel_closed']
    require(all(type(row.get('channel_id')) is int for row in auths + closed)
            and [row.get('channel_id') for row in auths] == list(channels)
            and len(closed) == len(channels) and {row.get('channel_id') for row in closed} == set(channels),
            'Channel authentication/closure multiplicity differs')
    for auth_row in auths:
        cid = auth_row['channel_id']; channel = channels[cid]
        auth = channel_owner(auth_row.get('authentication'), owner)
        require(auth == channel.get('authentication') and auth['server'] == listening['endpoint']
                and registered['sequence'] < auth_row['sequence'] < finishing['sequence']
                and listening['sequence'] < auth_row['sequence']
                and auth_row.get('owner_receipt') == receipt['owner_receipt']
                and auth['monotonic_s'] <= auth_row['monotonic_s'],
                'Channel authentication is late, foreign to listener or lacks durable owner')
        final = channel.get('namespace_closed')
        require(isinstance(final, dict) and final.get('schema') == 'campaign002-codehost-channel-3'
                and type(final.get('channel_id')) is int and final['channel_id'] == cid
                and final.get('qualified') is True and final.get('error_type') is None
                and final.get('reason') in ('clean_idle_eof', 'owner_finish'), 'Namespace channel terminal invalid')
        meters = channel.get('meters')
        require(isinstance(meters, dict) and set(meters) == {'client_read', 'upload', 'download', 'client_written'},
                'Independent parent byte meters missing')
        for name, value in meters.items(): stream_identity(value, name)
        stream_identity(final.get('upload'), 'namespace upload')
        stream_identity(final.get('download'), 'namespace download')
        require(meters['client_read'] == meters['upload'] == final['upload']
                and meters['download'] == meters['client_written'] == final['download'],
                'Channel original bytes differ between authenticated client and shared host')
        require(h2_facts(channel.get('h2')) == h2_facts(final.get('h2')), 'Independent HTTP2 endpoint witnesses differ')
        h2_summary(final['h2'])
        require(final['h2']['bytes'] == {d: final[d]['bytes'] for d in ('upload', 'download')},
                'HTTP2 witness byte totals differ from original stream meters')
        if final['reason'] == 'clean_idle_eof':
            idle_h2(final['h2'])
            require(final.get('finish_frontier') is None, 'Idle close improperly uses later owner FINISH')
        else:
            channel_h2(final['h2'], final.get('finish_frontier'))
        close_row = next(row for row in closed if row['channel_id'] == cid)
        require(close_row.get('namespace_closed') == final and close_row.get('meters') == meters
                and close_row.get('h2') == channel['h2'] and auth_row['sequence'] < close_row['sequence']
                < terminal['sequence'], 'Parent channel-close receipt differs or is late')
        if final['reason'] == 'owner_finish':
            require(finishing['sequence'] < close_row['sequence'], 'Channel owner closure preceded durable finishing')
        eof = [row for row in rows if row['kind'] == 'client_eof' and row.get('channel_id') == cid]
        require(len(eof) <= 1 and channel.get('parent_eof') == (eof[0] if eof else None),
                'Parent channel EOF projection missing, changed or duplicate')
        if eof:
            observed = eof[0]
            require(type(observed.get('client_finishing')) is bool, 'Parent EOF phase is malformed')
            if observed['client_finishing']:
                require(marker['monotonic_s'] <= observed['monotonic_s']
                        and marker['wall_unix_s'] <= observed['wall_unix_s'], 'Early EOF cannot claim later owner finishing')
                h2_summary(observed.get('h2'), complete=False)
                channel_h2(observed['h2'], channel.get('finish_frontier'), complete=False)
            else:
                idle_h2(observed.get('h2'))
            terminal_control_progress(channel['h2'], observed['h2'])
    require(all(type(row.get('channel_id')) is int and row.get('channel_id') in channels
                for row in rows if row['kind'] == 'client_eof'),
            'Parent EOF refers to unknown channel')
    ready = receipt.get('ready')
    inside_sources = {name: sources[CAMPAIGN + 'harness/' + name]
                      for name in ('codehost_inside_v3.py', 'codehost_mux_protocol.py')}
    if cleanup_transport.METHOD in sources:
        inside_sources['native_cleanup_protocol.py'] = sources[CAMPAIGN+'harness/native_cleanup_protocol.py']
    require(isinstance(ready, dict) and ready.get('schema') == 'campaign002-codehost-owner-ready-3'
            and integer(ready.get('child_pid'), 1) and ready['child_pid'] == listening.get('shared_child_pid')
            and ready.get('sources') == inside_sources, 'Shared host READY identity differs')
    for key in ('max_connections', 'max_frame_bytes', 'per_channel_queue_bytes', 'aggregate_queue_bytes'):
        require(type(ready.get(key)) is int and ready[key] == opening[key], 'Shared host resource cap differs')
    stderr = receipt.get('stderr')
    require(isinstance(stderr, dict) and stderr.get('truncated') is False and stderr.get('redacted') is False
            and type(stderr.get('raw_bytes')) is int and stderr['raw_bytes'] == stderr.get('bytes')
            and stderr.get('raw_sha256') == stderr.get('sha256'), 'Namespace stderr is truncated or redacted')
    raw = bound_document(root, stderr, 'codehost-owner-stderr-v3.txt', bindings, raw=True)
    ns_rows, namespace = namespace_integrity(raw, receipt, sources, channels)
    if cleanup_transport.METHOD in sources:
        require(owner_kind == 'model_client' or not any(r['kind'] in (
                'native_cleanup_begin','native_cleanup_ack','native_cleanup_channel') for r in rows),
                'Synthetic probe cannot invent native cleanup authorization')
        for channel in channels.values():
            for witness in (channel['h2'], channel['namespace_closed']['h2']):
                require('cleanup_phase_nonce' in witness and 'cleanup_cancel_records' in witness,
                        'Declared cleanup source lacks H2 phase schema')
                if owner_kind != 'model_client':
                    require(witness['cleanup_phase_nonce'] is None and witness['cleanup_cancel_records']==[],
                            'Synthetic probe cannot authorize model cleanup cancellation')
    else:
        require(all(w.get('cleanup_phase_nonce') is None and not w.get('cleanup_cancel_records')
                    for c in channels.values() for w in (c['h2'],c['namespace_closed']['h2'])),
                'Cleanup cancellation lacks declared frozen method')
    payload = canonical(receipt['finished'])
    require(terminal.get('finished') == receipt['finished']
            and terminal.get('payload_bytes') == len(payload) and type(terminal.get('payload_bytes')) is int
            and terminal.get('payload_sha256') == digest(payload), 'Observed FINISHED payload identity differs')
    parent_frames = [dict(row, direction={'outgoing': 'sent', 'incoming': 'received'}.get(row.get('direction')))
                     for row in rows if row['kind'] == 'frame']
    ns_frames = [row for row in ns_rows if row['kind'] == 'frame']
    totals = framing_integrity(parent_frames, ns_frames,
        {cid: item['namespace_closed'] for cid, item in channels.items()}, ready, allow_empty=allow_empty)
    for row in parent_frames:
        require(row['sequence'] < terminal['sequence'], 'Frame after observed FINISHED')
        if row['frame_type'] == 1:
            require(next(x['sequence'] for x in auths if x['channel_id'] == row['channel_id']) < row['sequence'],
                    'Channel OPEN preceded OS owner authentication')
        if row['frame_type'] == 7:
            require(finishing['sequence'] < row['sequence'] < input_closed['sequence'],
                    'FINISH frame preceded durable finishing or followed input EOF')
    for cid, counts in totals.items():
        require(counts == {d: channels[cid]['namespace_closed'][d]['bytes'] for d in ('upload', 'download')},
                'Framed DATA byte totals differ from end-to-end stream receipts')
    parent_finish_frontiers(rows, channels, auths, marker, finishing)
    drain_proof = owner_drain_integrity(rows, ns_rows, receipt, channels, marker)
    retired = bound_document(root, receipt.get('retirement'), 'codehost-owner-retirement-v3.json', bindings)
    retirement = retirement_integrity(retired)
    require(len(retirement['namespace_ids']) == 1, 'More than one shared namespace recorded')
    client_names = {'events.jsonl', 'native-owner.json', 'launch.json', 'result.json'}
    inputs = {('client/' + name if name in client_names else name): value for name, value in bindings.items()}
    if quiescence is not None:
        for name, binding in quiescence['input_bindings'].items():
            require(name not in inputs or inputs[name] == binding, 'Quiescence inputs changed during transport verification')
            inputs[name] = binding
    result = {'schema': 'campaign002-transport-integrity-3', 'passed': True, 'owner_kind': owner_kind,
            'allow_empty': allow_empty, 'accepted_count': len(channels), 'connection_count': len(channels),
            'denied_count': 0, 'owner': owner, 'owner_finishing': marker, 'namespace': namespace,
            'retirement': retirement, 'owner_drain': drain_proof, 'source_bindings': sources, 'input_bindings': inputs,
            'scope': 'Authenticated single owner and shared host, exact channel bytes, bounded lifecycle and retirement only.'}
    if quiescence is not None:
        result['client_quiescence'] = quiescence
    process_method = process_integrity.enabled(frozen)
    ordering_reader = process_integrity if process_method else pre_exit_integrity
    if ordering_reader.enabled(frozen) and owner_kind == 'model_client':
        ordering = ordering_reader.verify(root, frozen, rows, channels, quiescence, repo=REPO)
        for name, binding in ordering['input_bindings'].items():
            require(name not in inputs or inputs[name] == binding, 'Native ordering inputs changed during verification')
            inputs[name] = binding
        result['native_process_drain' if process_method else 'native_pre_exit_drain'] = ordering
    return result


def partial_drain_rejection(rows, namespace, receipt, channel, marker):
    """Fixed partial45 rejection: prove observed bytes and failed cleanup.

    The namespace rejects the pre-intent HALF_CLOSE and stops reading before
    DRAIN_BEGIN/FINISH. Those two empty cleanup controls can therefore be an
    explicitly unmatched parent suffix. No DATA is missing or reconstructed;
    this branch can never produce ordinary transport acceptance.
    """
    write_failures = [r for r in rows if r.get('kind') == 'failure' and r.get('reason') in (
        'frame_write_BrokenPipeError', 'frame_write_ConnectionResetError')]
    require(len(write_failures) <= 1 and type(receipt.get('exit_code')) is int
            and receipt['exit_code'] in (0, 1), 'Partial-stream cleanup write/status evidence differs')
    failures = ['channel_ValueError', 'namespace_finished_unqualified']
    if write_failures: failures.append(write_failures[0]['reason'])
    failures += ['drain_invalid']
    if receipt['exit_code'] == 1: failures.append('namespace_wrapper_nonzero')
    failures += ['namespace_receipt_ValueError']
    require(receipt['failures'] == failures
            and [r.get('reason') for r in rows if r.get('kind') == 'failure'] == failures,
            'Partial-stream rejection has unrelated or missing failures')
    require(not any(r.get('kind') in ('owner_drain_ack', 'channel_closed') for r in rows),
            'Partial-stream cleanup falsely claims acknowledged or qualified closure')
    begin = one_event(rows, 'owner_drain_begin'); seal = one_event(rows, 'owner_finishing')
    completed = one_event(rows, 'owner_drain_completed'); terminal = one_event(rows, 'namespace_finished')
    input_closed = one_event(rows, 'owner_input_closed'); output_closed = one_event(rows, 'namespace_output_closed')
    eof = one_event(rows, 'client_eof'); drained = one_event(rows, 'upload_drained')
    original = one_event(rows, 'channel_finish_frontier'); sealed = one_event(rows, 'channel_seal_frontier')
    reject = next(r for r in rows if r.get('reason') == 'channel_ValueError')
    require(eof['sequence'] < reject['sequence'] < original['sequence'] < begin['sequence']
            < seal['sequence'] < input_closed['sequence']
            and terminal['sequence'] < output_closed['sequence'] < completed['sequence']
            and eof['monotonic_s'] < marker['monotonic_s'],
            'Partial-stream rejection/closing chronology differs')
    retirement = one_event(rows, 'retirement_started')
    require(input_closed['sequence'] < retirement['sequence'], 'Partial-stream local pipe close follows retirement')
    if write_failures:
        require(input_closed.get('after_finish_drain') is False and input_closed.get('failed_cleanup') is True
                and output_closed['sequence'] < write_failures[0]['sequence'] < seal['sequence']
                and completed['sequence'] < input_closed['sequence'],
                'Partial-stream failed local close falsely claims delivered FINISH or precedes namespace failure')
    else:
        require(input_closed.get('after_finish_drain') is True
                and input_closed['sequence'] < completed['sequence'],
                'Partial-stream successful control write lacks its original input closure receipt')
    require(channel.get('parent_eof') == eof and channel.get('upload_drained') == drained
            and original.get('h2') == channel.get('finish_frontier')
            and sealed.get('h2') == channel.get('seal_frontier')
            and sealed.get('channel_id') == 1 and original.get('channel_id') == 1
            and drained.get('channel_id') == 1 and eof['sequence'] < drained['sequence'] < seal['sequence'],
            'Partial-stream actual EOF/drain/frontier projection differs')
    channel_h2(channel['h2'], channel['finish_frontier'], complete=False)
    closed_before_frontier = any(r.get('kind') == 'frame' and r.get('frame_type') == 5
                                 and r.get('channel_id') == 1 and r['sequence'] < original['sequence']
                                 for r in rows)
    require(channel['finish_frontier']['retiring'] is False
            and channel['seal_frontier']['retiring'] is (not closed_before_frontier)
            and channel['h2'] == channel['seal_frontier'], 'Partial-stream original failed frontier changed')
    drain = receipt.get('drain')
    require(isinstance(drain, dict) and set(drain) == {'start_monotonic_s','deadline_monotonic_s','bound_s',
            'seal_qualified','seal_error_code','completed_monotonic_s'}
            and drain['start_monotonic_s'] == marker['monotonic_s']
            and drain['deadline_monotonic_s'] == marker['monotonic_s']+25
            and type(drain['bound_s']) is int and drain['bound_s'] == 25
            and all(begin.get(key) == drain[key] for key in ('start_monotonic_s','deadline_monotonic_s','bound_s'))
            and drain['seal_qualified'] is False and drain['seal_error_code'] == 'drain_invalid'
            and seal.get('seal_qualified') is False and seal.get('seal_error_code') == 'drain_invalid'
            and {key:completed.get(key) for key in drain} == drain
            and finite(drain['completed_monotonic_s'])
            and max(seal['monotonic_s'],output_closed['monotonic_s'])
                <= drain['completed_monotonic_s'] <= drain['deadline_monotonic_s'],
            'Partial-stream bounded failed seal/cleanup receipt differs')
    nsfinal = namespace[-1]; nsend = channel['namespace_closed']
    require(not any(r.get('kind') in ('owner_drain_begin','owner_drain_ack','owner_finish','channel_finish_frontier')
                    for r in namespace)
            and nsfinal.get('owner_drain_received') is False and nsfinal.get('owner_drain_acknowledged') is False
            and nsfinal.get('drain_qualified') is False and nsfinal.get('drain_error_code') == 'owner_drain_unqualified'
            and nsfinal.get('owner_drain_elapsed_s') is None and nsfinal.get('owner_drain_timeout_s') == 25
            and nsfinal.get('qualified') is False and nsfinal.get('error_type') == 'ValueError'
            and nsend.get('qualified') is False and nsend.get('reason') == 'error'
            and nsend.get('error_type') == 'ValueError'
            and nsend.get('finish_frontier') is None and nsend.get('seal_frontier') is None,
            'Partial-stream namespace failed cleanup falsely claims a successful drain')
    allowed = {'open','child_started','ready','frame','channel_open','channel_eof','failure',
               'channel_upload_drained','channel_closed','child_diagnostic','closed'}
    require({r.get('kind') for r in namespace} <= allowed, 'Unknown partial-stream namespace event')
    nsclose = one_event(namespace,'channel_closed')
    nsfailure = one_event(namespace,'failure')
    nseof = [r for r in namespace if r.get('kind') == 'channel_eof' and r.get('direction') == 'upload']
    require(len(nseof) == 1 and nseof[0].get('channel_id') == 1 and nseof[0].get('owner_finishing') is False
            and nseof[0].get('h2') == nsend.get('upload_eof_h2')
            and nseof[0]['sequence'] < nsfailure['sequence'] < nsclose['sequence']
            and nsfailure.get('error_type') == 'ValueError' and nsclose.get('receipt') == nsend,
            'Partial-stream namespace EOF rejection or CLOSED projection differs')
    meters = channel['meters']
    for value in meters.values(): stream_identity(value,'partial stream meter')
    require(drained.get('meters',{}).get('client_read') == drained.get('meters',{}).get('upload')
            == meters['client_read'] == meters['upload'] == nsend.get('upload')
            and meters['download'] == meters['client_written'] == nsend.get('download')
            and h2_facts(channel['h2']) == h2_facts(nsend.get('h2'))
            and nsend.get('upload_eof') is True and nsend.get('upload_drained') is True,
            'Partial-stream observed endpoint bytes differ or remain undrained')
    nsdrained = one_event(namespace,'channel_upload_drained')
    require(nsdrained.get('channel_id') == 1 and nsdrained.get('upload') == meters['upload']
            and nsdrained.get('owner_finishing') is False
            and nseof[0]['sequence'] < nsdrained['sequence'] < nsclose['sequence'],
            'Partial-stream namespace upload drain missing')
    pframes = [r for r in rows if r.get('kind') == 'frame']
    nframes = [r for r in namespace if r.get('kind') == 'frame']
    sent = [frame_identity(r) for r in pframes if r.get('direction') == 'outgoing']
    received = [frame_identity(r) for r in pframes if r.get('direction') == 'incoming']
    consumed = [frame_identity(r) for r in nframes if r.get('direction') == 'incoming']
    emitted = [frame_identity(r) for r in nframes if r.get('direction') == 'outgoing']
    cleanup_controls = [(10,0,0,digest(b'')),(7,0,0,digest(b''))]
    suffix = sent[len(consumed):]
    require(sent[:len(consumed)] == consumed
            and (suffix == cleanup_controls if not write_failures else
                 len(suffix) < len(cleanup_controls) and suffix == cleanup_controls[:len(suffix)])
            and received == emitted
            and [r[0] for r in consumed] == [1]+[3]*(len(consumed)-2)+[4]
            and all(r[1] == 1 for r in consumed)
            and received[0] == (9,0,len(canonical(receipt['ready'])),digest(canonical(receipt['ready'])))
            and received[-1] == (5,1,len(canonical(nsend)),digest(canonical(nsend)))
            and [r[0] for r in received[1:-1]] == [2]+[3]*(len(received)-3),
            'Partial-stream unmatched framing is not exactly the observed cleanup controls')
    require(sum(r[2] for r in consumed if r[0] == 3) == meters['upload']['bytes']
            and sum(r[2] for r in emitted if r[0] == 3) == meters['download']['bytes']
            and nsfinal.get('frame_counts') == {d:sum(r.get('direction') == d for r in nframes)
                                                for d in ('incoming','outgoing')},
            'Partial-stream DATA accounting differs from exact captured endpoints')
    return {'seal_qualified': False, 'cleanup_controls_written': [row[0] for row in suffix],
            'cleanup_control_write_failed': bool(write_failures),
            'namespace_input_eof_proven': False,
            'scope': 'Fixed partial-stream rejection and local cleanup only; no delivered FINISH or peer input EOF inferred.'}


def verify_expected_failure(stage_root, frozen, *, case):
    """Verify only the two fixed no-model rejection experiments.

    This is not an option on production acceptance and never returns ``passed``.
    The caller still needs official diagnostic queue success before reading it.
    """
    require(case in ('foreign_owner', 'in_flight_eof'), 'Undeclared expected-failure diagnostic')
    root, bindings = Path(stage_root), {}
    single_host_artifacts(root)
    sources = source_bindings(frozen, 'transport_probe')
    expected_sources = {name: sources[name] for name in BRIDGE_SOURCE_NAMES}
    if cleanup_transport.METHOD in sources:
        expected_sources[CAMPAIGN+'harness/native_cleanup_protocol.py'] = sources[CAMPAIGN+'harness/native_cleanup_protocol.py']
    declaration = document(root / 'diagnostic-case.json', bindings)
    require(set(declaration) == {'schema', 'case', 'owner_kind', 'model_calls', 'physical_simulation',
                                 'expected_failure', 'injection', 'client_transcript', 'client_result'}
            and declaration['schema'] == 'campaign002-transport-v3-case-1'
            and declaration['case'] == case and declaration['owner_kind'] == 'transport_probe'
            and type(declaration['model_calls']) is int and declaration['model_calls'] == 0
            and declaration['physical_simulation'] is False and declaration['expected_failure'] is True,
            'Expected-failure declaration or non-model scope differs')
    bound_document(root, declaration['client_transcript'], 'client-transcript.jsonl', bindings, raw=True)
    bound_document(root, declaration['client_result'], 'client-result.json', bindings)
    rows = json_lines(root / 'codehost-transport-v3.jsonl', bindings)
    require(len(rows) <= 16384, 'Diagnostic metadata record bound exceeded')
    metadata_sequence(rows, TRANSPORT_SCHEMA, hash_chain=True)
    require({row.get('kind') for row in rows} <= PARENT_KINDS | {'failure', 'channel_denied'},
            'Unknown expected-failure transport event')
    require(rows[0].get('kind') == 'open' and rows[-1].get('kind') == 'closed'
            and rows[0].get('sources') == expected_sources,
            'Diagnostic transport opening/closing/source binding differs')
    opening_bounds(rows[0])
    end = rows[-1]
    receipt = bound_document(root, end.get('receipt'), 'codehost-owner-bridge-v3.json', bindings,
                             maximum=MAX_RECEIPT_BYTES)
    require(receipt.get('schema') == 'campaign002-codehost-owner-bridge-3'
            and receipt.get('qualified') is False and end.get('qualified') is False
            and isinstance(receipt.get('failures'), list) and bool(receipt['failures'])
            and all(isinstance(reason, str) and reason for reason in receipt['failures'])
            and end.get('failures') == receipt['failures'] and receipt.get('sources') == expected_sources,
            'Expected failure was not an actual source-bound production rejection')
    counts = (0, 1, 1) if case == 'foreign_owner' else (1, 0, 1)
    for key, expected in zip(('accepted', 'denied', 'attempts'), counts):
        require(type(receipt.get(key)) is int and receipt[key] == expected
                and type(end.get(key)) is int and end[key] == expected,
                'Expected-failure attempt/channel counters differ')
    owner = owner_identity(receipt.get('owner'), 'transport_probe')
    retained_owner = bound_document(root, receipt.get('owner_receipt'), 'codehost-native-owner-v3.json', bindings)
    registered = [row for row in rows if row.get('kind') == 'owner_registered']
    require(len(registered) == 1 and registered[0].get('owner') == owner == retained_owner
            and registered[0].get('receipt') == receipt['owner_receipt'], 'Diagnostic owner registration differs')
    marker = client_owner(root, bindings, owner, 'transport_probe')
    client, transcript = probe_records(root, bindings, owner, marker, case)
    finishing = [row for row in rows if row.get('kind') == 'owner_finishing']
    terminals = [row for row in rows if row.get('kind') == 'namespace_finished']
    input_closed = [row for row in rows if row.get('kind') == 'owner_input_closed']
    output_closed = [row for row in rows if row.get('kind') == 'namespace_output_closed']
    starts = [row for row in rows if row.get('kind') == 'namespace_started']
    require(len(finishing) == len(terminals) == len(input_closed) == len(output_closed) == len(starts) == 1
            and finishing[0].get('client_finishing') is True
            and marker['monotonic_s'] <= finishing[0]['monotonic_s']
            and marker['wall_unix_s'] <= finishing[0]['wall_unix_s']
            and finishing[0]['sequence'] < input_closed[0]['sequence'] < end['sequence']
            and terminals[0]['sequence'] < output_closed[0]['sequence'] < end['sequence']
            and (input_closed[0].get('after_finish_drain') is True or case == 'in_flight_eof'
                 and input_closed[0].get('after_finish_drain') is False and input_closed[0].get('failed_cleanup') is True)
            and output_closed[0].get('after_finished') is True,
            'Expected failure lacks complete owner finishing and framed shutdown')
    stderr = receipt.get('stderr')
    require(isinstance(stderr, dict) and stderr.get('truncated') is False and stderr.get('redacted') is False
            and type(stderr.get('raw_bytes')) is int and stderr['raw_bytes'] == stderr.get('bytes')
            and stderr.get('raw_sha256') == stderr.get('sha256'), 'Diagnostic namespace stream incomplete')
    raw = bound_document(root, stderr, 'codehost-owner-stderr-v3.txt', bindings, raw=True)
    prefix = b'RCI_CODEHOST_V3 '
    require(raw.endswith(b'\n') and all(line.startswith(prefix) for line in raw.splitlines()),
            'Diagnostic namespace metadata framing differs')
    namespace = [decode(line[len(prefix):], 'diagnostic namespace') for line in raw.splitlines()]
    require(len(namespace) <= 16384 and all(isinstance(row, dict) for row in namespace),
            'Diagnostic namespace bound or object format differs')
    metadata_sequence(namespace, NAMESPACE_SCHEMA)
    require(namespace == receipt.get('namespace_records') and namespace[0].get('kind') == 'open'
            and namespace[-1].get('kind') == 'closed'
            and all(sum(row.get('kind') == name for row in namespace) == 1
                    for name in ('open', 'child_started', 'ready', 'closed')),
            'Diagnostic namespace identity or complete single-host lifecycle differs')
    require(type(namespace[0].get('max_records')) is int and namespace[0]['max_records'] == 16384
            and type(namespace[0].get('max_metadata_bytes')) is int
            and namespace[0]['max_metadata_bytes'] == MAX_METADATA_BYTES,
            'Diagnostic namespace resource bound differs')
    final = namespace[-1]
    inside_sources = {name: sources[CAMPAIGN+'harness/'+name]
                      for name in ('codehost_inside_v3.py','codehost_mux_protocol.py')}
    if cleanup_transport.METHOD in sources:
        inside_sources['native_cleanup_protocol.py'] = sources[CAMPAIGN+'harness/native_cleanup_protocol.py']
    child = next(row for row in namespace if row['kind'] == 'child_started')
    ready = receipt.get('ready')
    require(isinstance(ready, dict) and ready.get('sources') == namespace[0].get('sources')
            == final.get('sources') == inside_sources and integer(child.get('child_pid'), 1)
            and child['child_pid'] == ready.get('child_pid') == final.get('child_pid')
            and next(row for row in namespace if row['kind']=='ready').get('receipt') == ready,
            'Diagnostic shared host or namespace source differs')
    require(final == receipt.get('finished') == terminals[0].get('finished')
            and terminals[0].get('payload_bytes') == len(canonical(final))
            and terminals[0].get('payload_sha256') == digest(canonical(final))
            and final.get('owner_finish_received') is (case == 'foreign_owner')
            and final.get('stdin_eof') is (case == 'foreign_owner')
            and final.get('owner_input_wait_bound_s') == .5
            and final.get('kill_sent') is False and final.get('diagnostic_streams_complete') is True
            and type(final.get('terminate_sent')) is bool and type(final.get('child_exit_code')) is int
            and (final.get('child_exit_before_cleanup') is None
                 or type(final['child_exit_before_cleanup']) is int and final['child_exit_before_cleanup'] == 0)
            and (final['child_exit_code'] == 0 or final['terminate_sent'] and final['child_exit_code'] == -15),
            'Diagnostic child status or terminal delivery/EOF unproven')
    diagnostics = [row for row in namespace if row.get('kind') == 'child_diagnostic']
    require(len(diagnostics) == 2 and {row.get('stream') for row in diagnostics} == {'stdout','stderr'}
            and all(integer(row.get('bytes')) and hash_value(row.get('sha256'))
                    and row.get('truncated') is False
                    and (row['bytes'] != 0 or row['sha256'] == digest(b''))
                    and child['sequence'] < row['sequence'] < final['sequence'] for row in diagnostics)
            and sum(row['bytes'] for row in diagnostics) <= MAX_METADATA_BYTES,
            'Expected failure lacks complete bounded child diagnostic streams')
    for key in ('channel_count', 'channels_closed'):
        require(type(final.get(key)) is int and final[key] == counts[0], 'Diagnostic namespace channel count differs')
    channels = receipt.get('channels')
    require(isinstance(channels, list) and len(channels) == counts[0]
            and all(isinstance(row, dict) and type(row.get('channel_id')) is int for row in channels)
            and [row['channel_id'] for row in channels] == list(range(1, counts[0]+1)),
            'Diagnostic channel receipt count or identities differ')
    channel_map = {row['channel_id']: row for row in channels}
    queue_accounting(receipt, channel_map);queue_accounting(final, channel_map, namespace=True)
    require(receipt.get('queued_bytes_at_close') == 0 and type(receipt.get('queued_bytes_at_close')) is int
            and final.get('queue_bytes_at_close') == 0 and type(final.get('queue_bytes_at_close')) is int,
            'Expected failure left unaccounted queued data')
    injection = declaration['injection']
    require(isinstance(injection, dict), 'Expected-failure injection missing')
    auths = [row for row in rows if row.get('kind') == 'channel_authenticated']
    denials = [row for row in rows if row.get('kind') == 'channel_denied']
    parent_finish_frontiers(rows, channel_map, auths, marker, finishing[0], diagnostic=True)
    if case == 'foreign_owner':
        sibling = injection.get('sibling_process')
        require(isinstance(sibling, dict) and set(sibling) == {
            'pid','process_creation_filetime','queried_executable_path','executable'}
            and integer(sibling['pid'],1) and sibling['pid'] != owner['pid']
            and integer(sibling['process_creation_filetime'],1)
            and sibling['queried_executable_path'] == owner['queried_executable_path']
            and sibling['executable'] == owner['executable'] and sibling == client.get('sibling'),
            'Foreign-owner injection is not a separately identified same-executable process')
        require(set(injection) == {'sibling_process','client','server','attempted_payload_bytes','denial_eof_observed'}
                and tcp_endpoint(injection['client']) and tcp_endpoint(injection['server'])
                and type(injection['attempted_payload_bytes']) is int and injection['attempted_payload_bytes'] == 0
                and injection['denial_eof_observed'] is True and len(denials) == 1 and auths == []
                and denials[0].get('reason') == 'foreign_tcp_owner'
                and denials[0].get('client') == injection['client']
                and denials[0].get('server') == injection['server']
                and registered[0]['sequence'] < denials[0]['sequence'] < finishing[0]['sequence']
                and receipt['failures'] == ['channel_OwnerError', 'drain_invalid'],
                'Foreign owner was not rejected before forwarding or has unrelated failures')
        for key in ('client','server','attempted_payload_bytes','denial_eof_observed'):
            require(client['result'].get(key) == injection[key], 'Foreign denial differs from child observation')
        require(final.get('qualified') is True and final.get('error_type') is None,
                'Foreign-owner rejection unexpectedly damaged shared host cleanup')
    else:
        partial = b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n' + b'\0\0\0\4\0\0\0\0\0' + b'\0\0\0\4\1\0\0\0\0' + b'\0\0\x08'
        require(set(injection) == {'channel_id','fixed_upload_bytes','fixed_upload_sha256',
                                  'partial_header_bytes','client_eof_before_owner_finish'}
                and type(injection['channel_id']) is int and injection['channel_id'] == 1
                and type(injection['fixed_upload_bytes']) is int and injection['fixed_upload_bytes'] == len(partial)
                and injection['fixed_upload_sha256'] == digest(partial)
                and type(injection['partial_header_bytes']) is int and injection['partial_header_bytes'] == 3
                and injection['client_eof_before_owner_finish'] is True and len(auths) == 1 and not denials,
                'In-flight injection differs from the fixed 45-byte partial-header case')
        channel_owner(auths[0].get('authentication'), owner)
        eof = [row for row in rows if row.get('kind') == 'client_eof']
        require(len(eof) == 1 and type(eof[0].get('channel_id')) is int and eof[0]['channel_id'] == 1
                and eof[0].get('client_finishing') is False
                and auths[0]['sequence'] < eof[0]['sequence'] < finishing[0]['sequence']
                and eof[0]['monotonic_s'] < marker['monotonic_s'], 'Partial stream EOF did not precede owner finishing')
        h2_summary(eof[0].get('h2'), complete=False)
        require(eof[0]['h2']['preface_complete'] is True and eof[0]['h2']['settings_complete'] is True
                and eof[0]['h2']['frames_complete'] is False and eof[0]['h2']['bytes']['upload'] == len(partial)
                and 'channel_ValueError' in receipt['failures'], 'Incomplete pre-finish HTTP2 stream was not rejected')
        require(channel_map[1]['meters']['client_read'] == channel_map[1]['meters']['upload']
                == {'bytes':len(partial),'sha256':digest(partial)}, 'Actual partial upload differs from fixed injection')
        client_channels = client['result']['channels']
        require(len(client_channels) == 1 and client_channels[0].get('channel_id') == 1
                and client_channels[0].get('sent') == {'bytes':len(partial),'sha256':digest(partial)}
                and client_channels[0].get('closed_before_finish') is True
                and client['result'].get('partial_header_bytes') == 3
                and client['result'].get('client_eof_before_owner_finish') is True,
                'Actual diagnostic client did not send and close the prescribed partial stream')
    parent_frames = [dict(row, direction={'outgoing':'sent','incoming':'received'}.get(row.get('direction')))
                     for row in rows if row.get('kind') == 'frame']
    ns_frames = [row for row in namespace if row.get('kind') == 'frame']
    if case == 'foreign_owner':
        framing_integrity(parent_frames, ns_frames, {}, ready, allow_empty=True)
    for row in parent_frames:
        require(case == 'in_flight_eof' or row['sequence'] < terminals[0]['sequence'],
                'Diagnostic frame after observed FINISHED')
        if row['frame_type'] == 7:
            require(finishing[0]['sequence'] < row['sequence'] < input_closed[0]['sequence'],
                    'Diagnostic FINISH precedes durable finishing or follows input EOF')
        if row['frame_type'] == 1:
            require(any(auth['channel_id'] == row['channel_id'] and auth['sequence'] < row['sequence']
                        for auth in auths), 'Diagnostic OPEN preceded OS owner authentication')
    if case == 'foreign_owner':
        namespace_integrity(raw, receipt, sources, channel_map)
        rejection_drain = owner_drain_integrity(rows, namespace, receipt, channel_map, marker, diagnostic=True)
    else:
        rejection_drain = partial_drain_rejection(rows, namespace, receipt, channel_map[1], marker)
    expected_exit = 0 if final.get('qualified') is True else 1
    require(type(receipt.get('exit_code')) is int and receipt['exit_code'] == expected_exit,
            'Diagnostic namespace wrapper status differs from retained terminal')
    retired = bound_document(root, receipt.get('retirement'), 'codehost-owner-retirement-v3.json', bindings)
    retirement = retirement_integrity(retired, expected_exit_code=expected_exit)
    require(len(retirement['namespace_ids']) == 1, 'Expected failure created multiple namespaces')
    client_names = {'events.jsonl','native-owner.json','launch.json','result.json'}
    inputs = {('client/'+name if name in client_names else name):value for name,value in bindings.items()}
    return {'schema':'campaign002-transport-expected-failure-3','case':case,'expected_failure_verified':True,
            'diagnostic_only':True,'ordinary_transport_passed':False,'model_calls':0,'physical_simulation':False,
            'retirement':retirement,'rejection_drain':rejection_drain,'source_bindings':sources,'input_bindings':inputs,
            'scope':'Fixed synthetic rejection and complete retirement only; never production qualification.'}
