"""Frozen-source, no-model native raw-notification option preflight.

The unchanged Runtime owns canaries, namespace construction and bounded cleanup.
This accepts metadata only: neither a model read nor a tool-result payload path
is proved. Invoke assess only after the external official queue-success gate.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
INTEGRATION = CAMPAIGN.parent
REPO = HERE.parents[3]
SCHEMA = 'campaign002-raw-event-preflight-2'
TIMEOUT = 90
MAX_READ_BYTES = 256 * 1024 * 1024


def require(value, message):
    if value is not True:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def exact(left, right):
    """JSON identity preserves boolean/integer distinctions lost by dict ==."""
    return json.dumps(left, sort_keys=True, separators=(',', ':'), allow_nan=False) == json.dumps(
        right, sort_keys=True, separators=(',', ':'), allow_nan=False)


def binding(path):
    raw = Path(path).read_bytes()
    return {'sha256': digest(raw), 'bytes': len(raw)}


def dependency(name):
    for directory in (HERE, CAMPAIGN / 'assessment'):
        if str(directory) not in sys.path:
            sys.path.insert(0, str(directory))
    return importlib.import_module(name)


def required_sources():
    paths = [HERE / name for name in (
        'raw_event_preflight.py', 'test_raw_event_preflight.py', 'raw_event_preflight_v2.py',
        'test_raw_event_preflight_v2.py', 'runtime.py',
        'bootstrap_client_v2.py', 'bootstrap_client_v3.py', 'bootstrap_client_v4.py',
        'native_quiescence.py', 'test_client_quiescence.py',
        'test_native_owner_bootstrap.py', 'test_raw_event_capture.py',
        'executor_capture.py', 'transport_stderr.py', 'codehost_bridge_v2.py',
        'codehost_entry_v2.py', 'codehost_inside_v2.py', 'codehost_bridge_v3.py',
        'codehost_entry_v3.py', 'codehost_inside_v3.py', 'codehost_owner.py', 'codehost_mux_protocol.py')]
    paths += [CAMPAIGN / 'assessment' / name for name in
              ('assess.py', 'retained_reads.py', 'transport_integrity.py', 'transport_integrity_v3.py', 'transport_dispatch.py',
               'client_quiescence.py', 'test_client_quiescence.py')]
    paths += [CAMPAIGN / 'io-repair/PREFLIGHT_V3_LIFECYCLE_JOIN_V1.md',
              CAMPAIGN / 'io-repair/RAW_TOOL_RESULT_EVIDENCE_V1.md',
              CAMPAIGN / 'io-repair/CODEHOST_CHANNEL_TRANSPORT_V3.md',
              CAMPAIGN / 'io-repair/CHANNEL_TRANSPORT_V3_QUALIFICATION_001.md',
              INTEGRATION / 'launch/robot_codex_launcher.py',
              INTEGRATION / 'isolation-session-9/wsl/qualification.py',
              INTEGRATION / 'isolation-session-9/native/schema-evidence.json']
    paths += [INTEGRATION / 'readiness-session-10/boundary' / name for name in
              ('linux_entry.py', 'namespace.py', 'retirement.py', 'canary.py', 'codehost_canary.py')]
    paths += [CAMPAIGN / 'io-repair/native-output-source-002' / name for name in (
        'codex-rs__app-server__src__bespoke_event_handling.rs',
        'codex-rs__app-server__src__request_processors__thread_lifecycle.rs',
        'codex-rs__core__src__session__session.rs')]
    spec = importlib.util.spec_from_file_location('raw_quiescence_inventory', CAMPAIGN / 'qualification/prepare_model_v24.py')
    extra = importlib.util.module_from_spec(spec); spec.loader.exec_module(extra)
    return sorted({path.relative_to(REPO).as_posix() for path in paths} | set(extra.reader_inputs()))


def validate_snapshot(snapshot, revision=None):
    snapshot = Path(snapshot).resolve()
    require(snapshot.is_file() and not snapshot.is_symlink(), 'Ordinary snapshot required')
    frozen = dependency('transport_integrity').decode(snapshot.read_bytes(), 'snapshot')
    revision = revision if revision is not None else frozen.get('revision')
    require(not dependency('assess').frozen_problems(snapshot, frozen, revision),
            'Frozen source/archive verification failed')
    for name in required_sources():
        path = REPO / name
        require(path.is_file() and not path.is_symlink()
                and frozen.get('sources', {}).get(name) == binding(path),
                'Required preflight source absent or changed: ' + name)
    return frozen


def save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


class Reader:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.inputs = {}
        self.bytes = 0

    def raw(self, name, maximum=32 * 1024 * 1024):
        path = self.root / name
        require(path.resolve().is_relative_to(self.root) and path.is_file()
                and not path.is_symlink() and path.stat().st_size <= maximum,
                'Missing, linked or oversized preflight input: ' + name)
        raw = path.read_bytes()
        self.bytes += len(raw)
        require(self.bytes <= MAX_READ_BYTES, 'Preflight input byte bound exceeded')
        current = {'sha256': digest(raw), 'bytes': len(raw)}
        require(name not in self.inputs or self.inputs[name] == current, 'Preflight input changed while assessed: ' + name)
        self.inputs[name] = current
        return raw

    def json(self, name):
        raw = self.raw(name)
        require(raw.endswith(b'\n'), 'Incomplete preflight document: ' + name)
        return dependency('transport_integrity').decode(raw, name)


def current_owner_lifecycle(reader, frozen, native_owner, events):
    """Join original protected files; do not filter or manufacture an event log."""
    legacy = dependency('transport_integrity')
    # Preserve the exact legacy stderr vocabulary/schema/bounds independently of
    # its obsolete penultimate-marker layout. Both consume the original rows.
    for row in events:
        if row.get('kind') != 'stderr':
            continue
        require(row.get('schema') == 'campaign002-stderr-metadata-1'
                and legacy.integer(row.get('bytes'), 1) and row['bytes'] <= 32 * 1024 * 1024
                and isinstance(row.get('sha256'), str)
                and re.fullmatch('[0-9a-f]{64}', row['sha256']) is not None
                and legacy.finite(row.get('wall_unix_s')) and legacy.finite(row.get('monotonic_s'))
                and row.get('text_retained') is False and isinstance(row.get('markers'), list)
                and row.get('scope') == 'Fixed lexical markers only; no error message or causal diagnosis.'
                and all(isinstance(item, str) and item in legacy.STDERR_MARKERS for item in row['markers'])
                and len(row['markers']) == len(set(row['markers']))
                and set(row) == {'kind', 'schema', 'bytes', 'sha256', 'wall_unix_s', 'monotonic_s',
                                 'markers', 'text_retained', 'scope'},
                'Client stderr metadata malformed, incomplete or outside fixed vocabulary')
    inputs = {}
    marker = dependency('transport_integrity_v3').client_owner(
        reader.root / 'runtime', inputs, native_owner, 'model_client', allow_empty=True)
    require(set(inputs) == {'native-owner.json', 'events.jsonl', 'launch.json', 'result.json'},
            'Current owner proof consumed an unexpected input set')
    proof = dependency('client_quiescence').verify_client_quiescence(reader.root / 'runtime', frozen)
    require(isinstance(proof, dict) and proof.get('passed') is True,
            'Independent native client quiescence proof failed')
    expected_inputs = {'client/native-quiescence.json', 'client/events.jsonl',
                       'client/result.json', 'client/launch.json', 'client/preflight.json'}
    if 'cleanup_barrier' in proof:
        expected_inputs.update({'codehost-transport-v3.jsonl', 'codehost-owner-stderr-v3.txt',
                                'codehost-owner-bridge-v3.json'})
        if proof['cleanup_barrier'] is not None:
            expected_inputs.update({'codehost-native-owner-v3.json', 'client/native-owner.json'})
    require(set(proof.get('input_bindings', {})) == expected_inputs,
            'Native quiescence proof lacks complete original input bindings')
    joined = {'client/' + name: value for name, value in inputs.items()}
    for name, value in proof['input_bindings'].items():
        require(name not in joined or exact(joined[name], value), 'Owner and quiescence inputs differ: ' + name)
        joined[name] = value
    for name, value in joined.items():
        raw = reader.raw('runtime/' + name)
        require(exact({'sha256': digest(raw), 'bytes': len(raw)}, value),
                'Dependent owner/quiescence input changed: ' + name)
    return marker, proof


def client_evidence(reader, source, frozen):
    bootstrap = dependency('bootstrap_client_v4')
    launch = reader.json('runtime/client/launch.json')
    preflight = reader.json('runtime/client/preflight.json')
    result = reader.json('runtime/client/result.json')
    raw = reader.raw('runtime/client/events.jsonl')
    require(bool(raw) and raw.endswith(b'\n'), 'Incomplete native event stream')
    events = [dependency('transport_integrity').decode(line, 'native event') for line in raw.splitlines()]
    require(all(isinstance(row, dict) for row in events), 'Malformed native event')
    requests = [row for row in events if row.get('kind') == 'request']
    methods = [row.get('method') for row in requests]
    expected = ['initialize', 'config/read', 'account/read', 'environment/status',
                'environment/add', 'environment/info', 'thread/start',
                'mcpServerStatus/list', 'environment/status', 'environment/status']
    require(methods == expected and [row.get('id') for row in requests] == list(range(1, 11))
            and all(type(row.get('id')) is int for row in requests),
            'Metadata RPC sequence changed or model/tool RPC present')
    public_ids = (1, 4, 6, 7, 9, 10)
    public = [row for row in events if row.get('kind') == 'response']
    require([row.get('id') for row in public] == list(public_ids)
            and all(type(row.get('id')) is int for row in public), 'Missing, duplicate or reordered public RPC response')
    for response_row in public:
        request_row = requests[response_row['id'] - 1]
        request_index, response_index = events.index(request_row), events.index(response_row)
        require(response_row.get('method') == request_row['method'] and 'error' not in response_row
                and isinstance(response_row.get('result'), dict) and request_index < response_index
                and not any(row.get('kind') == 'request' for row in events[request_index + 1:response_index]),
                'RPC result identity or synchronous request ordering differs')
    by_id = {row['id']: row['result'] for row in public}
    require(by_id[4].get('status') == by_id[10].get('status') == 'unknown'
            and by_id[9].get('status') == 'ready' and by_id[6].get('cwd') == 'file:///workspace'
            and by_id[6].get('shell', {}).get('path', '').startswith('/'),
            'Local or qualified remote environment status differs')
    require(not any(row.get('kind') in ('rpc_error', 'unexpected_server_request', 'config_warning')
                    or row.get('method', '').startswith(('turn/', 'item/', 'rawResponseItem/'))
                    for row in events), 'Preflight has error or model/tool activity')
    thread = requests[6]
    require(exact(thread['params'], {
        'cwd': str(reader.root / 'runtime/control'), 'model': bootstrap.LAUNCH.MODEL,
        'modelProvider': 'openai', 'approvalPolicy': 'never', 'sandbox': 'danger-full-access',
        'developerInstructions': '', 'environments': [{'environmentId': 'robot-qualified',
            'cwd': '/workspace', 'runtimeWorkspaceRoots': ['/workspace']}],
        'ephemeral': True, 'dynamicTools': [], 'selectedCapabilityRoots': [],
        'allowProviderModelFallback': False, 'experimentalRawEvents': True}),
        'Thread option, authority, environment or model policy changed')
    responses = [row for row in events if row.get('kind') == 'response' and row.get('method') == 'thread/start']
    require(len(responses) == 1 and responses[0].get('id') == thread['id']
            and events.index(responses[0]) > events.index(thread), 'Unique accepted thread response required')
    response = responses[0].get('result', {})
    tid = response.get('thread', {}).get('id')
    require(isinstance(tid, str) and bool(tid) and response.get('model') == bootstrap.LAUNCH.MODEL
            and response.get('modelProvider') == 'openai'
            and response.get('reasoningEffort') == bootstrap.LAUNCH.EFFORT
            and response.get('instructionSources') == [], 'Native thread policy differs')
    for document in (preflight, result):
        require(document.get('model_started') is False and document.get('preflight_passed') is True
                and document.get('thread_id') == tid and document.get('auth_type') == 'chatgpt'
                and document.get('model_effective') == bootstrap.LAUNCH.MODEL
                and document.get('effort_effective') == bootstrap.LAUNCH.EFFORT
                and document.get('instruction_sources') == [] and document.get('mcp_active_servers') == []
                and 'error' not in document and 'turn_status' not in document,
                'Preflight/client result lacks unchanged successful metadata policy')
    require(result.get('success') is True and preflight.get('success') is False
            and preflight.get('experimental_raw_events_requested') is True
            and preflight.get('experimental_raw_events_thread_start_accepted') is True,
            'Native raw-event acceptance receipt missing')
    effective = result.get('effective_config', {})
    require(exact(preflight.get('effective_config'), effective), 'Effective config receipts differ')
    names = effective.get('disabled_mcp_names')
    require(isinstance(names, list) and all(isinstance(name, str) for name in names)
            and len(names) == len(set(names)), 'Disabled MCP name inventory malformed')
    header_names = sorted(launch.get('config_overrides', {}).get('mcp_servers', {}))
    require(all(isinstance(name, str) for name in header_names)
            and set(header_names) <= set(names), 'MCP header inventory differs from disabled effective config')
    expected_effective = {'mcp_count': len(names), 'mcp_all_disabled': True,
        'disabled_mcp_names': sorted(names), 'header_names_count': len(header_names),
        'disabled_feature_count': len(bootstrap.DISABLED - {'code_mode_host'}),
        'remote_code_mode_host_configured': True, 'automatic_project_documents': False,
        'custom_instructions': False, 'provider': 'openai', 'web_search': 'disabled', 'thread_unload_delay_secs': 0}
    require(exact(effective, expected_effective) and exact(launch.get('config_overrides'), bootstrap.overrides(header_names, True))
            and launch.get('mcp_headers_disabled') == len(header_names),
            'Strict effective configuration or overrides differ')
    inventories = [row for row in events if row.get('kind') == 'mcp_inventory_summary']
    catalog = result.get('mcp_catalog')
    require(isinstance(catalog, list) and len(inventories) == 1
            and inventories[0].get('has_more') is False
            and exact(inventories[0].get('entries'), catalog) and exact(preflight.get('mcp_catalog'), catalog)
            and all(row.get('name') in names and row.get('runtimeStatus') == 'disabled'
                    and all(type(row.get(key)) is int and row[key] == 0
                            for key in ('tools_count', 'resources_count', 'resource_templates_count')) for row in catalog),
            'Native disabled MCP inventory incomplete')
    require(launch.get('bootstrap') == bootstrap.BOOTSTRAP and launch.get('bootstrap_requested') is False
            and launch.get('experimental_raw_events_requested') is True
            and launch.get('remote_cwd') == 'file:///workspace'
            and launch.get('host_cwd') == str(reader.root / 'runtime/control')
            and type(launch.get('timeout_seconds')) in (int, float) and launch['timeout_seconds'] == TIMEOUT
            and launch.get('model_requested') == bootstrap.LAUNCH.MODEL
            and launch.get('reasoning_effort_requested') == bootstrap.LAUNCH.EFFORT
            and launch.get('outer_namespace_authoritative') is True
            and launch.get('remote_code_mode_host_configured') is True
            and launch.get('executor_url_recorded') is False
            and launch.get('binary') == source['native_binary']['path']
            and launch.get('binary_sha256') == source['native_binary']['sha256'],
            'Native launch metadata differs from the declared preflight')
    native_owner = reader.json('runtime/client/native-owner.json')
    bridge_owner = reader.json('runtime/codehost-native-owner-v3.json')
    require(exact(native_owner, bridge_owner), 'Bootstrap and bridge owner identity differ')
    require(native_owner.get('schema') == 'campaign002-native-owner-1'
            and native_owner.get('owner_kind') == 'model_client'
            and type(native_owner.get('pid')) is int and native_owner['pid'] > 0
            and type(native_owner.get('process_creation_filetime')) is int
            and native_owner['process_creation_filetime'] > 0,
            'Missing concrete native process identity')
    executable = native_owner.get('executable', {})
    require(all(executable.get(key) == source['native_binary'][key] for key in ('path', 'sha256', 'bytes')),
            'Owner executable differs from the exact native binary')
    registrations = [(i, row) for i, row in enumerate(events)
                     if row.get('kind') == 'native_process_owner_registered']
    require(len(registrations) == 1 and registrations[0][0] < events.index(requests[0]),
            'Durable owner receipt must precede initialize')
    receipt = registrations[0][1]
    require(exact({'sha256': receipt.get('receipt_sha256'), 'bytes': receipt.get('receipt_bytes')},
                  reader.inputs['runtime/client/native-owner.json']), 'Native owner log binding differs')
    owner, quiescence = current_owner_lifecycle(reader, frozen, native_owner, events)
    require(events[-1].get('exit_code') == 0 and type(events[-1].get('exit_code')) is int,
            'Native client did not exit integer zero')
    return {'thread_id': tid, 'thread_start_count': 1, 'turn_start_count': 0,
            'raw_events_option_accepted': True, 'owner_finishing': owner,
            'native_quiescence': quiescence}


def runtime_evidence(reader):
    outer = reader.json('runtime/orchestration-result.json')
    cleanup = reader.json('runtime/cleanup.json')
    require(outer.get('success') is True and outer.get('model_started') is False
            and outer.get('cleanup_clean') is True and outer.get('durable_retention_verified') is True
            and not any('error' in key for key in outer)
            and exact(cleanup, {'clean': True, 'errors': []}), 'Runtime or cleanup did not finish cleanly')
    before = reader.json('runtime/runtime-before-close.json')
    after = reader.json('runtime/runtime-after-close.json')
    require(before == after, 'Retained runtime files changed during cleanup')
    location = reader.json('runtime/runtime-location.json')
    setup = location.get('setup', {})
    require(location.get('durable_backing') is True
            and re.fullmatch('/var/tmp/robot-codex-session10/[0-9a-f]{32}', location.get('run', '')) is not None
            and location.get('workspace') == location['run'] + '/workspace'
            and len(setup.get('protected_exist', {})) == 4
            and all(value is True for value in setup['protected_exist'].values())
            and setup.get('outside_loopback_control') is True, 'Qualified namespace controls absent')
    canary = reader.json('runtime/canary-stdout.json')
    require(canary.get('qualified') is True and len(canary.get('checks', {})) == 45
            and all(value is True for value in canary['checks'].values()), 'Unchanged 45 boundary checks failed')
    host = reader.json('runtime/codehost-canary-stdout.json')
    checks = host.get('checks', {})
    require(host.get('host_qualified') is True and type(host.get('model_calls')) is int and host['model_calls'] == 0
            and host.get('enabled_tools') == [] and checks.get('tools') == []
            and type(checks.get('all_tools_count')) is int and checks['all_tools_count'] == 0
            and checks.get('constructor_process_type') == 'undefined'
            and set(checks.get('apis', {})) == {'process', 'require', 'fetch', 'Deno', 'Bun', 'WebSocket', 'XMLHttpRequest'}
            and all(value == 'undefined' for value in checks['apis'].values())
            and set(checks.get('imports', {})) == {'node:fs', 'file:///etc/passwd', 'https://example.invalid/'}
            and all(value == 'denied' for value in checks['imports'].values()), 'Code-host boundary canary failed')
    security = reader.json('runtime/bridge-security.json')
    require(exact(security, {'wrong_path_denied': True, 'second_active_connection_denied': True}),
            'Exclusive executor bridge canaries failed')
    file_probe = reader.json('runtime/executor-file-probe.json')
    require(file_probe.get('qualified') is True, 'Executor file canary failed')
    writes = reader.json('runtime/executor-write-probe.json')
    require('result' in writes.get('allowed', {}) and 'error' in writes.get('protected', {}),
            'Executor write split failed')
    probe = reader.json('runtime/executor-process-probe.json')
    require(probe.get('stderr') == '' and len(probe.get('exit', [])) == 1
            and type(probe['exit'][0].get('exitCode')) is int and probe['exit'][0]['exitCode'] == 0,
            'Executor canary process did not exit integer zero')
    process_canary = dependency('transport_integrity').decode(probe.get('stdout', ''), 'process canary')
    require(process_canary.get('qualified') is True
            and set(process_canary.get('checks', {})) == set(canary['checks'])
            and all(value is True for value in process_canary['checks'].values()), 'Executor canary checks incomplete')
    calls = reader.json('runtime/gateway-calls.json')
    require(isinstance(calls, list) and bool(calls) and all(row.get('method') == 'GET' for row in calls),
            'Unexpected mutating gateway activity')
    return {'cleanup_clean': True, 'boundary_checks': 45, 'namespace_run': location['run']}


def lifecycle_evidence(reader, frozen, namespace_run):
    transport = dependency('transport_integrity')
    root = reader.root / 'runtime'
    transport_proof = dependency('transport_integrity_v3').verify_transport_integrity(
        root, frozen, owner_kind='model_client', allow_empty=True)
    require(isinstance(transport_proof, dict) and transport_proof.get('passed') is True,
            'Independent single-host owner/channel lifecycle proof failed')
    count = transport_proof.get('accepted_count')
    require(type(count) is int and 0 <= count <= 16, 'Invalid authenticated channel count')
    for name, expected_input in transport_proof.get('input_bindings', {}).items():
        raw = reader.raw('runtime/' + name)
        require(exact({'sha256': digest(raw), 'bytes': len(raw)}, expected_input),
                'Dependent transport proof input changed: ' + name)
    captures = sorted(root.glob('executor-*-capture.jsonl'))
    require(len(captures) == 2 and [path.name for path in captures] ==
            ['executor-1-capture.jsonl', 'executor-2-capture.jsonl'], 'Canary and native executor captures required')
    expected_retirements = {f'executor-{number}-retirement.json' for number in (1, 2)}
    expected_retirements.add('codehost-owner-retirement-v3.json')
    require({path.name for path in root.glob('*retirement*.json')} == expected_retirements,
            'Namespace retirement set differs from actual captured connections')
    for number, path in enumerate(captures, 1):
        reader.raw('runtime/' + path.name, 64 * 1024 * 1024)
        records, delivered, _ = dependency('retained_reads').load_capture(path)
        require(records[0].get('connection_id') == str(number)
                and {r['sequence'] for r in records if r.get('kind') == 'response'} == delivered
                and all(r.get('original_message_sha256') == r.get('retained_message_sha256')
                        for r in records if 'message' in r),
                'Executor capture has missing delivery or wrong connection')
        starts = [r for r in records if r.get('kind') == 'request' and r.get('message', {}).get('method') == 'process/start']
        require((number == 1 and len(starts) == 1
                 and starts[0]['message'].get('params', {}).get('argv') == ['/usr/bin/python3', '-I', '-B', '/canary.py'])
                or number == 2 and not starts, 'Unexpected executor process beyond the qualified canary')
        if number == 1:
            start = starts[0]['message']
            params = start['params']
            require(params.get('processId') == 'canary' and params.get('cwd') == 'file:///workspace'
                    and params.get('tty') is False, 'Canary process identity or workspace changed')
            responses = [r['message'] for r in records if r.get('kind') == 'response']
            accepted = [r for r in responses if r.get('id') == start.get('id')]
            process = [r for r in responses if r.get('method', '').startswith('process/')]
            exits = [r['params'] for r in process if r['method'] == 'process/exited']
            require(len(accepted) == 1 and 'error' not in accepted[0]
                    and accepted[0].get('result', {}).get('processId') == 'canary'
                    and bool(process) and process[-1]['method'] == 'process/closed'
                    and sum(r['method'] == 'process/closed' for r in process) == 1
                    and len(exits) == 1 and type(exits[0].get('exitCode')) is int and exits[0]['exitCode'] == 0
                    and all(r.get('params', {}).get('processId') == 'canary' for r in process),
                    'Qualified canary process lacks accepted/exited/closed lifecycle')
            seqs = [r['params'].get('seq') for r in process]
            output_seqs = [r['params'].get('seq') for r in process if r['method'] == 'process/output']
            require(all(type(value) is int for value in seqs)
                    and set(seqs) == set(range(1, len(process) + 1)) and seqs[-1] == len(process)
                    and all(a < b for a, b in zip(output_seqs, output_seqs[1:])),
                    'Canary native process sequence incomplete')
            stdout, stderr = bytearray(), bytearray()
            for row in process:
                if row['method'] == 'process/output':
                    stream = row['params'].get('stream')
                    require(stream in ('stdout', 'stderr'), 'Unknown canary output stream')
                    (stdout if stream == 'stdout' else stderr).extend(base64.b64decode(row['params']['chunk'], validate=True))
            probe = reader.json('runtime/executor-process-probe.json')
            require(bytes(stdout).decode('utf-8') == probe['stdout'] and not stderr
                    and exits == probe['exit'], 'Canary projected result differs from complete native bytes')
        exit_receipt = reader.json(f'runtime/executor-{number}-exit.json')
        require(type(exit_receipt.get('exit_code')) is int and exit_receipt['exit_code'] == 0,
                'Executor wrapper did not exit integer zero')
    for name in sorted(expected_retirements):
        retirement = reader.json('runtime/' + name)
        transport.retirement_integrity(retirement)
        identity = retirement.get('identity_path', '')
        require(identity.startswith(namespace_run + '/') and identity.endswith('.json')
                and '/' not in identity[len(namespace_run) + 1:], 'Retirement belongs to another runtime')
    return {'executor_connections': 2, 'codehost_connections': count,
            'codehost_transport_proof': transport_proof,
            'namespace_retirements': sorted(expected_retirements),
            'raw_tool_payload_path_tested': False,
            'scope': 'Native option acceptance and actual namespace closure only; no model or prepared tool payload.'}


def assess(output, snapshot):
    reader = Reader(output)
    result = {'schema': SCHEMA, 'passed': False, 'run_id': None, 'framework_revision': None,
              'snapshot_sha256': binding(snapshot)['sha256'], 'model_calls': 0,
              'physical_simulation': False, 'checks': {}, 'inputs': reader.inputs, 'errors': {},
              'scope': 'No-model native raw-event option acceptance. No raw tool payload, model-read or task-performance claim.'}
    try:
        frozen = validate_snapshot(snapshot)
        source = reader.json('source-binding.json')
        execution = reader.json('execution.json')
        result.update(run_id=source.get('run_id'), framework_revision=source.get('framework_revision'))
        require(source.get('schema') == 'campaign002-raw-preflight-source-2'
                and source.get('framework_revision') == frozen['revision']
                and source.get('snapshot_sha256') == result['snapshot_sha256']
                and source.get('sources') == frozen['sources']
                and isinstance(source.get('run_id'), str) and bool(source['run_id']), 'Source receipt differs from freeze')
        bootstrap = dependency('bootstrap_client_v4')
        require(source.get('native_binary') == {'path': str(bootstrap.LAUNCH.CODEX), **binding(bootstrap.LAUNCH.CODEX)},
                'Native binary differs from preflight source receipt')
        require(execution.get('run_id') == source['run_id'] and execution.get('preflight') is True
                and execution.get('timeout_seconds') == TIMEOUT and execution.get('completed') is True
                and type(execution.get('exit_status')) is int and execution['exit_status'] == 0
                and execution.get('error_type') is None, 'Runtime invocation failed or remained incomplete')
        result['checks']['frozen_source_and_completed_invocation'] = True
        result['client'] = client_evidence(reader, source, frozen)
        result['checks']['one_raw_enabled_thread_zero_model_turns'] = True
        result['runtime'] = runtime_evidence(reader)
        result['checks']['unchanged_canaries_and_clean_runtime'] = True
        result['lifecycle'] = lifecycle_evidence(reader, frozen, result['runtime']['namespace_run'])
        result['checks']['all_actual_namespaces_retired'] = True
        result['passed'] = True
    except Exception as error:
        result['checks']['complete_preflight'] = False
        result['errors']['preflight'] = {'type': type(error).__name__, 'message': str(error)}
    return result


def run(args):
    frozen = validate_snapshot(args.snapshot, args.framework_revision)
    require(isinstance(args.run_id, str) and bool(re.fullmatch(r'[A-Za-z0-9_.-]+', args.run_id)), 'Invalid run identity')
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    bootstrap = dependency('bootstrap_client_v4')
    save(output / 'source-binding.json', {'schema': 'campaign002-raw-preflight-source-2',
        'run_id': args.run_id, 'framework_revision': args.framework_revision,
        'snapshot_sha256': binding(args.snapshot)['sha256'], 'sources': frozen['sources'],
        'native_binary': {'path': str(bootstrap.LAUNCH.CODEX), **binding(bootstrap.LAUNCH.CODEX)}})
    execution = {'run_id': args.run_id, 'preflight': True, 'timeout_seconds': TIMEOUT,
                 'completed': False, 'exit_status': None, 'error_type': None}
    started = time.monotonic()
    try:
        execution['exit_status'] = dependency('runtime').run_bootstrap(output / 'runtime', preflight=True, timeout=TIMEOUT)
        execution['completed'] = True
    except Exception as error:
        execution['error_type'] = type(error).__name__
    finally:
        execution['elapsed_seconds'] = time.monotonic() - started
        save(output / 'execution.json', execution)
    result = assess(output, args.snapshot)
    save(output / 'result.json', result)
    print(json.dumps({'passed': result['passed'], 'result': str(output / 'result.json'),
                      'runtime_exit_status': execution['exit_status'], 'model_calls': 0}))
    return 0 if result['passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, type=Path)
    parser.add_argument('--framework-revision', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--output', required=True, type=Path)
    return run(parser.parse_args())


if __name__ == '__main__':
    raise SystemExit(main())
