"""Independent verification of the prospectively declared transport-v2 receipts.

This module reads protected metadata only. It imports no runtime implementation,
does not execute a guest process, and does not reclassify an earlier assessment.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re


REPO = Path(__file__).resolve().parents[4]
INTEGRATION = 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/'
CAMPAIGN = INTEGRATION + 'campaign-002/'
SOURCE_NAMES = tuple(CAMPAIGN + name for name in (
    'harness/codehost_bridge_v2.py', 'harness/codehost_inside_v2.py',
    'harness/codehost_entry_v2.py', 'harness/runtime.py',
    'harness/bootstrap_client_v2.py', 'harness/transport_stderr.py',
    'assessment/transport_integrity.py', 'io-repair/TRANSPORT_EVIDENCE_V2.md',
)) + tuple(INTEGRATION + 'readiness-session-10/boundary/' + name for name in (
    'linux_entry.py', 'namespace.py', 'inside.py', 'gateway_policy.py', 'retirement.py',
))
BRIDGE_SOURCE_NAMES = tuple(CAMPAIGN + 'harness/' + name for name in (
    'codehost_bridge_v2.py', 'codehost_entry_v2.py', 'codehost_inside_v2.py',
)) + tuple(INTEGRATION + 'readiness-session-10/boundary/' + name
           for name in ('linux_entry.py', 'namespace.py'))
STDERR_MARKERS = frozenset((
    'code_mode_host', 'exec_server', 'grpc', 'transport', 'connection_closed',
    'connection_reset', 'disconnected', 'unavailable', 'timeout', 'refused',
    'broken_pipe', 'error_level', 'warning_level',
))
TRANSPORT_SCHEMA = 'campaign002-codehost-transport-2'
PROBE_SOURCE_NAME = CAMPAIGN + 'harness/codehost_probe.py'


def require(value, message):
    if value is not True:
        raise ValueError(message)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def object_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate transport JSON key: ' + key)
        result[key] = value
    return result


def decode(raw, label):
    try:
        return json.loads(raw, object_pairs_hook=object_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    except (ValueError, UnicodeError) as error:
        raise ValueError('Malformed transport JSON: ' + label) from error


def read_file(path, bindings, maximum=2 * 1024 * 1024):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'Missing ordinary transport file: ' + path.name)
    require(path.stat().st_size <= maximum, 'Transport file exceeds declared reader bound: ' + path.name)
    raw = path.read_bytes()
    bindings[path.name] = {'sha256': digest(raw), 'bytes': len(raw)}
    return raw


def json_document(path, bindings):
    raw = read_file(path, bindings)
    require(raw.endswith(b'\n'), 'Incomplete transport document tail: ' + Path(path).name)
    value = decode(raw, Path(path).name)
    require(isinstance(value, dict), 'Transport document must be an object')
    return value


def json_lines(path, bindings, maximum=2 * 1024 * 1024):
    raw = read_file(path, bindings, maximum)
    require(bool(raw) and raw.endswith(b'\n'), 'Missing or truncated transport stream tail: ' + Path(path).name)
    lines = raw.splitlines()
    require(all(lines), 'Empty record in transport stream')
    rows = [decode(line, Path(path).name) for line in lines]
    require(all(isinstance(row, dict) for row in rows), 'Transport records must be objects')
    return rows


def source_bindings(frozen, owner_kind):
    require(isinstance(frozen, dict) and isinstance(frozen.get('sources'), dict),
            'Transport source snapshot is required')
    result = {}
    for name in SOURCE_NAMES + ((PROBE_SOURCE_NAME,) if owner_kind == 'transport_probe' else ()):
        path = REPO / name
        require(path.is_file() and not path.is_symlink(), 'Transport source unavailable: ' + name)
        raw = path.read_bytes()
        expected = {'sha256': digest(raw), 'bytes': len(raw)}
        supplied = frozen['sources'].get(name)
        require(isinstance(supplied, dict) and type(supplied.get('bytes')) is int
                and supplied == expected, 'Transport source differs from freeze: ' + name)
        result[name] = expected
    return result


def transport_ledger(path, bindings):
    rows = json_lines(path, bindings)
    previous = None
    last_monotonic = -1
    for index, row in enumerate(rows, 1):
        require(row.get('schema') == TRANSPORT_SCHEMA and type(row.get('sequence')) is int
                and row['sequence'] == index and row.get('previous_sha256') == previous,
                'Transport ledger schema, sequence or chain differs')
        require(digest(canonical({key: value for key, value in row.items() if key != 'record_sha256'}))
                == row.get('record_sha256'), 'Transport ledger hash differs')
        require(finite(row.get('wall_unix_s')) and finite(row.get('monotonic_s'))
                and row['monotonic_s'] >= last_monotonic, 'Transport ledger clock malformed or reversed')
        previous = row['record_sha256']
        last_monotonic = row['monotonic_s']
    require(rows[0].get('kind') == 'open' and rows[-1].get('kind') == 'closed',
            'Transport stream lacks open/closed receipts')
    return rows


def client_finishing(root, bindings, owner_kind):
    rows = json_lines(Path(root) / 'client/events.jsonl', bindings, 32 * 1024 * 1024)
    finishing = [(i, row) for i, row in enumerate(rows)
                 if row.get('kind') == 'client_finishing_before_close']
    shutdown_kind = 'client_shutdown' if owner_kind == 'model_client' else 'probe_client_closed'
    shutdown = [(i, row) for i, row in enumerate(rows) if row.get('kind') == shutdown_kind]
    require(len(finishing) == 1 and len(shutdown) == 1
            and finishing[0][0] == len(rows) - 2 and shutdown[0][0] == len(rows) - 1,
            'Transport requires unique owner-finishing receipt before client shutdown')
    marker = finishing[0][1]
    require(marker.get('schema') == 'campaign002-client-finishing-1'
            and finite(marker.get('wall_unix_s')) and finite(marker.get('monotonic_s'))
            and set(marker) == {'kind', 'schema', 'wall_unix_s', 'monotonic_s'},
            'Owner-finishing receipt malformed')
    end = shutdown[0][1]
    if owner_kind == 'model_client':
        require(not any(row.get('kind') == 'probe_client_closed' for row in rows)
                and type(end.get('exit_code')) is int,
                'Client shutdown lacks integer native exit status or contains a probe marker')
    else:
        require(not any(row.get('kind') == 'client_shutdown' for row in rows)
                and end.get('schema') == 'campaign002-h2-probe-client-1' and end.get('closed') is True
                and finite(end.get('wall_unix_s')) and finite(end.get('monotonic_s'))
                and marker['monotonic_s'] <= end['monotonic_s']
                and marker['wall_unix_s'] <= end['wall_unix_s'],
                'Transport probe lacks its real source-bound close receipt')
    for row in rows:
        if row.get('kind') != 'stderr':
            continue
        require(row.get('schema') == 'campaign002-stderr-metadata-1'
                and integer(row.get('bytes'), 1) and row['bytes'] <= 32 * 1024 * 1024
                and isinstance(row.get('sha256'), str)
                and re.fullmatch('[0-9a-f]{64}', row['sha256']) is not None
                and finite(row.get('wall_unix_s')) and finite(row.get('monotonic_s'))
                and row.get('text_retained') is False and isinstance(row.get('markers'), list)
                and row.get('scope') == 'Fixed lexical markers only; no error message or causal diagnosis.'
                and all(isinstance(item, str) and item in STDERR_MARKERS for item in row['markers'])
                and len(row['markers']) == len(set(row['markers']))
                and set(row) == {'kind', 'schema', 'bytes', 'sha256', 'wall_unix_s', 'monotonic_s',
                                 'markers', 'text_retained', 'scope'},
                'Client stderr metadata malformed, incomplete or outside fixed vocabulary')
    return marker


def bound_document(root, item, name, bindings, *, raw=False):
    require(isinstance(item, dict) and item.get('path') == name
            and integer(item.get('bytes')), 'Transport receipt path/size binding differs: ' + name)
    content = read_file(Path(root) / name, bindings)
    require(len(content) == item['bytes'] and digest(content) == item.get('sha256'),
            'Transport receipt hash/size differs: ' + name)
    if raw:
        return content
    require(content.endswith(b'\n'), 'Incomplete bound transport document: ' + name)
    value = decode(content, name)
    require(isinstance(value, dict), 'Bound transport document must be an object: ' + name)
    return value


def namespace_integrity(raw, receipt):
    require(bool(raw) and raw.endswith(b'\n'), 'Namespace stderr is empty or truncated')
    try:
        lines = raw.decode('utf-8', errors='strict').splitlines()
    except UnicodeError as error:
        raise ValueError('Namespace stderr is not complete UTF-8') from error
    prefix = 'RCI_CODEHOST_V2 '
    require(all(line.startswith(prefix) for line in lines), 'Namespace contains unframed child or wrapper output')
    rows = [decode(line[len(prefix):], 'namespace record') for line in lines]
    require(all(isinstance(row, dict) for row in rows), 'Namespace metadata records must be objects')
    lifecycle = [row for row in rows if row.get('kind') != 'child_diagnostic']
    kinds = [row.get('kind') for row in lifecycle]
    require(kinds in (
        ['open', 'child_started', 'connected', 'stdin_eof', 'channel_end', 'closed'],
        ['open', 'child_started', 'connected', 'channel_end', 'stdin_eof', 'closed']),
            'Namespace lifecycle is missing, reordered, duplicated or unhealthy')
    diagnostics = [row for row in rows if row.get('kind') == 'child_diagnostic']
    require(len(diagnostics) == 2 and {row.get('stream') for row in diagnostics} == {'stdout', 'stderr'}
            and all(rows.index(lifecycle[1]) < rows.index(row) < rows.index(lifecycle[-1])
                    and integer(row.get('bytes')) and row.get('truncated') is False
                    and set(row) == {'kind', 'schema', 'sequence', 'wall_unix_s', 'monotonic_s',
                                     'stream', 'bytes', 'sha256', 'truncated'}
                    and isinstance(row.get('sha256'), str)
                    and re.fullmatch('[0-9a-f]{64}', row['sha256']) is not None
                    and (row['bytes'] != 0 or row['sha256'] == digest(b''))
                    for row in diagnostics)
            and sum(row['bytes'] for row in diagnostics) <= 1024 * 1024,
            'Namespace child diagnostic streams missing, duplicated, truncated or malformed')
    require(receipt.get('namespace_records') == rows
            and type(receipt.get('namespace_record_count')) is int
            and receipt['namespace_record_count'] == len(rows), 'Namespace projection differs from original stderr')
    last = -1
    for index, row in enumerate(rows, 1):
        require(row.get('schema') == 'campaign002-codehost-namespace-2'
                and type(row.get('sequence')) is int and row['sequence'] == index
                and finite(row.get('wall_unix_s')) and finite(row.get('monotonic_s'))
                and row['monotonic_s'] >= last, 'Namespace metadata sequence or clock differs')
        last = row['monotonic_s']
    require(integer(lifecycle[1].get('child_pid'), 1), 'Namespace child identity missing')
    counts = []
    for row in lifecycle[3:]:
        require(integer(row.get('to_host')) and integer(row.get('from_host')), 'Namespace byte counters malformed')
        counts.append((row['to_host'], row['from_host']))
    require(all(a <= b for a, b in zip(counts[0], counts[1])) and counts[1] == counts[2],
            'Namespace byte counters reversed or changed after the final EOF receipt')
    channel = next(row for row in lifecycle if row['kind'] == 'channel_end')
    end = lifecycle[-1]
    for row in (channel, end):
        before = row.get('child_exit_before_cleanup')
        require({'reason', 'stdin_eof', 'error_type', 'child_exit_before_cleanup'} <= row.keys()
                and row.get('error_type') is None
                and (before is None or type(before) is int and before == 0),
                'Namespace ended before owner input EOF or with a native child failure')
    require(type(channel.get('stdin_eof')) is bool
            and channel.get('reason') == ('stdin_eof' if channel['stdin_eof'] else 'channel_eof')
            and end.get('stdin_eof_at_channel_end') is channel['stdin_eof']
            and end.get('reason') == 'owner_input_eof' and end.get('stdin_eof') is True
            and type(end.get('owner_input_wait_bound_s')) in (int, float)
            and end['owner_input_wait_bound_s'] == .5
            and end.get('diagnostic_streams_complete') is True,
            'Namespace ended before owner input EOF or lacks complete bounded handoff evidence')
    if kinds[3] == 'stdin_eof':
        require(channel['stdin_eof'] is True, 'Namespace channel end contradicts earlier stdin EOF')
    require(end.get('qualified') is True and type(end.get('terminate_sent')) is bool
            and end.get('kill_sent') is False and type(end.get('child_exit_code')) is int
            and (end['child_exit_code'] == 0
                 or end['terminate_sent'] is True and end['child_exit_code'] == -15),
            'Namespace native child exit or cleanup is unhealthy')
    require(channel['child_exit_before_cleanup'] == end['child_exit_before_cleanup'],
            'Namespace pre-cleanup child status changed in final projection')
    return {'records': len(rows), 'child_exit_before_cleanup': end['child_exit_before_cleanup'],
            'child_exit_code': end['child_exit_code'], 'terminate_sent': end['terminate_sent'],
            'reason': end['reason']}


def retirement_integrity(value):
    require(value.get('qualified') is True and value.get('normal_wait_timed_out') is False
            and value.get('windows_wrapper_killed_after_linux_retired') is False
            and type(value.get('windows_exit_code')) is int and value['windows_exit_code'] == 0,
            'Codehost retirement did not complete normally')
    observations = value.get('observations')
    require(isinstance(observations, list) and bool(observations)
            and all(isinstance(row, dict) for row in observations), 'Missing namespace retirement observations')
    end = observations[-1]
    require(end.get('retired') is True and end.get('namespace_evidence_available') is True
            and end.get('outer_same_process') is False and end.get('namespace_members') == []
            and isinstance(end.get('namespace_ids'), list) and bool(end['namespace_ids'])
            and all(integer(item, 1) for item in end['namespace_ids']),
            'Final retirement lacks empty retired namespace and process identity evidence')


def verify_transport_integrity(stage_root, frozen, *, owner_kind='model_client'):
    """Require complete source-bound v2 owner/bridge/namespace lifecycle evidence.

    Call only after the existing official queue success gate. ValueError means
    this attempt lacks the new transport proof; it does not revise a prior run.
    """
    require(owner_kind in ('model_client', 'transport_probe'), 'Unknown transport owner kind')
    root, bindings = Path(stage_root), {}
    sources = source_bindings(frozen, owner_kind)
    bridge_sources = {name: sources[name] for name in BRIDGE_SOURCE_NAMES}
    owner = client_finishing(root, bindings, owner_kind)
    rows = transport_ledger(root / 'codehost-transport-v2.jsonl', bindings)
    require(bindings['codehost-transport-v2.jsonl']['bytes'] <= 1024 * 1024,
            'Transport ledger exceeds original producer bound')
    opening, end = rows[0], rows[-1]
    require(opening.get('sources') == bridge_sources
            and type(opening.get('max_connections')) is int and opening['max_connections'] == 16
            and type(opening.get('max_ledger_bytes')) is int and opening['max_ledger_bytes'] == 1024 * 1024
            and type(opening.get('max_stderr_bytes')) is int and opening['max_stderr_bytes'] == 1024 * 1024,
            'Bridge source identity or original metadata bounds differ')
    require(end.get('failures') == [] and type(end.get('accepted')) is int and end['accepted'] == 1
            and type(end.get('denied')) is int and end['denied'] == 0,
            'Transport has failure, rejected overlap or unexpected connection count')
    kinds = [row.get('kind') for row in rows]
    require(kinds == ['open', 'listening', 'connection_accepted', 'child_started',
                      'pump_end', 'pump_end', 'retirement_started', 'connection_closed', 'closed'],
            'Transport lifecycle is incomplete, reordered or contains extra connections')
    connection = rows[2].get('connection_id')
    require(type(connection) is int and connection == 1
            and all(type(row.get('connection_id')) is int and row['connection_id'] == connection
                    for row in rows[2:-1]), 'Transport connection identity differs')
    require(rows[2]['monotonic_s'] <= owner['monotonic_s'] <= rows[4]['monotonic_s']
            and rows[2]['wall_unix_s'] <= owner['wall_unix_s'] <= rows[4]['wall_unix_s'],
            'Owner finishing was absent or recorded after the first transport end')
    pumps = rows[4:6]
    require({row.get('pump') for row in pumps} == {'upload', 'download'}, 'Missing unique upload/download ends')
    for row in pumps:
        require('exception_type' in row and row.get('client_finishing') is True
                and (row.get('reason') in ('eof', 'cancelled') and row.get('exception_type') is None
                     or row.get('reason') == 'error' and row.get('exception_type') == 'ConnectionResetError'),
                'Unexpected transport pump EOF, exception or owner state')
    require(pumps[0]['reason'] != 'cancelled', 'First-ending pump cannot be cleanup cancellation')
    require('exit_code_before' in rows[6] and rows[6].get('client_finishing') is True
            and (rows[6].get('exit_code_before') is None
                 or type(rows[6].get('exit_code_before')) is int and rows[6]['exit_code_before'] == 0),
            'Retirement began with unexpected native wrapper failure or owner state')
    require(rows[7].get('qualified') is True, 'Transport connection was not healthy at close')
    name = 'codehost-1-bridge.json'
    require({path.name for path in root.glob('codehost-*-bridge.json')} == {name},
            'Missing or extra codehost connection summaries')
    receipt = bound_document(root, rows[7].get('receipt'), name, bindings)
    require(receipt.get('schema') == 'campaign002-codehost-bridge-2'
            and type(receipt.get('connection_id')) is int and receipt['connection_id'] == connection
            and receipt.get('qualified') is True and receipt.get('sources') == bridge_sources
            and receipt.get('first_pump_end') == pumps[0]
            and receipt.get('client_finishing_at_first_end') is True
            and receipt.get('pump_errors') == []
            and type(receipt.get('exit_code')) is int and receipt['exit_code'] == 0
            and integer(receipt.get('to_host'), 1) and integer(receipt.get('from_host'), 1),
            'Bridge summary differs from healthy source-bound lifecycle')
    resets = sum(row['reason'] == 'error' for row in pumps)
    require(type(receipt.get('expected_client_shutdown_resets')) is int
            and receipt['expected_client_shutdown_resets'] == resets, 'Expected reset count differs from pump receipts')
    stderr = receipt.get('stderr')
    require(isinstance(stderr, dict) and stderr.get('truncated') is False
            and stderr.get('redacted') is False and integer(stderr.get('raw_bytes'), 1)
            and stderr['raw_bytes'] == stderr.get('bytes') <= 1024 * 1024
            and stderr.get('raw_sha256') == stderr.get('sha256'),
            'Namespace stderr was missing, redacted or truncated')
    raw = bound_document(root, stderr, 'codehost-1-stderr.txt', bindings, raw=True)
    namespace = namespace_integrity(raw, receipt)
    retirement = bound_document(root, receipt.get('retirement'), 'codehost-1-retirement.json', bindings)
    retirement_integrity(retirement)
    return {'schema': 'rci-independent-codehost-transport-2', 'passed': True,
            'source_bindings': sources, 'input_bindings': bindings,
            'connection_count': 1, 'denied_count': 0, 'owner_kind': owner_kind, 'owner_finishing': owner,
            'first_pump_end': pumps[0], 'expected_client_shutdown_resets': resets,
            'namespace': namespace,
            'scope': 'Complete source-bound owner, bridge, native-child and retirement metadata. '
                     'No payload, task outcome, model-attention or historical-verdict inference.'}
