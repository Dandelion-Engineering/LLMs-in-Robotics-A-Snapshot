"""Read-only Campaign 002 assessment of an explicitly frozen new runner.

The campaign manifest is independently bound; the original readiness manifest is
never relabeled. A bounded model failure is distinct from infrastructure validity.
No model, simulator, queue mutation, or credential endpoint is called here.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
INTEGRATION = HERE.parents[1]
REPO = INTEGRATION.parents[1]
PRIOR = INTEGRATION / 'readiness-session-10' / 'assessment'
sys.path.insert(0, str(PRIOR))
from assess_bootstrap import read_json, sha
from assess_smoke import inspect_stage as original_inspect_stage, jsonl, continuity_commits
from assess_pilot import classify_outcome, public_support, source_integrity
from retained_reads import upgrade_stage
from resource_integrity import verify_resources
from continuous_integrity import verify_continuous_physics
from transport_dispatch import verify_transport_integrity


def inspect_stage(root, source_zip=None):
    return upgrade_stage(root, original_inspect_stage(root), source_zip=source_zip)

CAMPAIGN = HERE.parent
LAUNCHER = CAMPAIGN / 'harness/physical.py'
TIMING_SOURCE = 'Long-Horizon Adaptive Robotics Expirement/Runtime 004/experiment.py'
BOUNDED_CLIENT_ERRORS = {
    'Bounded app-server deadline exceeded': 'model_wall_deadline',
    'App-server output limit exceeded': 'model_output_budget',
}


def queue_gate(receipt, expected_job_id=None):
    job = receipt.get('job', receipt)
    if job.get('state') != 'succeeded' or type(job.get('exit_status')) is not int or job['exit_status'] != 0:
        raise ValueError('Official queue succeeded/exit_status 0 required before reading attempt outputs')
    if expected_job_id is not None and job.get('id') != expected_job_id:
        raise ValueError('Official queue ID differs from declared attempt')
    return job


def model_disposition(client, native_exit_code):
    """Do not remove model deadline/output-budget failures from denominators."""
    if client.get('success') is True and client.get('turn_status') == 'completed' and native_exit_code == 0:
        return {'recognized': True, 'kind': 'completed', 'error': None}
    if client.get('model_started') is True and type(native_exit_code) is int:
        reason = BOUNDED_CLIENT_ERRORS.get(client.get('error'))
        if reason:
            return {'recognized': True, 'kind': reason, 'error': client['error']}
        if (client.get('error') == 'Bootstrap turn did not complete'
                and client.get('turn_status') in ('failed', 'interrupted')):
            # Failed turns can represent provider/service failures. Preserve them
            # as unknown infrastructure rather than infer robot incompetence.
            return {'recognized': False, 'kind': 'unclassified_failed_turn', 'error': client.get('error')}
    return {'recognized': False, 'kind': 'unclassified_client_failure', 'error': client.get('error')}


def lifecycle_disposition(stage, sequence, host_result, history, outcome):
    """Preserve missing receipts when normal task completion closes the host."""
    starts = [e for e in history if e.get('type') == 'invocation_start-invocation']
    retires = [e for e in history if e.get('type') == 'invocation_retire-invocation']
    stops = [e for e in history if e.get('type') == 'episode_stopped']
    explicit_retirement = (len(starts) == 1 and len(retires) == 1
                           and starts[0].get('event_id', 0) < retires[0].get('event_id', -1))
    token_denied = stage['result'].get('old_token_denied_after_retirement') is True
    namespace_clear = stage['checks'].get('all_namespace_retirements_observed') is True
    clean_host = (sequence.get('host_exit_code') == 0 and not sequence.get('forced_host_exit')
                  and host_result.get('execution_completed') is True and not host_result.get('error'))
    terminal_closure = (len(starts) == 1 and clean_host and namespace_clear
                        and len(stops) == 1 and stops[0].get('payload', {}).get('reason') == 'task_success'
                        and host_result.get('terminal') == 'task_success'
                        and outcome.get('independent_task_outcome') == 'success'
                        and outcome.get('accepted_handback_corresponds_to_owner_transfer') is True
                        and stops[0].get('event_id', -1) > max(outcome.get('owner_transfer_event_ids', [10**30])))
    branch = ('explicit_retirement' if explicit_retirement and token_denied and namespace_clear
              else 'successful_terminal_host_closure' if terminal_closure else 'unestablished')
    return {'valid': branch != 'unestablished', 'branch': branch,
            'explicit_retirement_receipt_observed': explicit_retirement,
            'late_old_token_http403_observed': token_denied,
            'all_namespaces_retired': namespace_clear,
            'start_event_ids': [e.get('event_id') for e in starts],
            'retire_event_ids': [e.get('event_id') for e in retires],
            'terminal_events': [{'event_id': e.get('event_id'), 'reason': e.get('payload', {}).get('reason')}
                                for e in stops],
            'missing_receipts': [name for name, present in
                                 [('explicit_retirement', explicit_retirement), ('late_old_token_http403', token_denied)]
                                 if not present],
            'limitation': ('Successful terminal closure establishes ended host and retired namespaces; it does not manufacture an explicit retirement or late HTTP403 receipt.'
                           if branch == 'successful_terminal_host_closure' else None)}


def decision(checks, outcome, model):
    failed = [name for name, passed in checks.items() if passed is not True]
    return {'validity': 'valid' if not failed else 'invalid', 'failed_checks': failed,
            'task_outcome': outcome['independent_task_outcome'] if not failed else 'unknown',
            'observed_task_outcome': outcome['independent_task_outcome'],
            'model_disposition': model,
            'task_evidence_valid': not failed and outcome['independent_task_outcome'] in ('success', 'failure'),
            'scorable': False,
            'scientific_admission': {'qualified': False, 'admissible': False,
                'reason': 'Episode evidence assessment only. Storage/accounting and frozen scientific-release admission require a separately verified external certificate; timing replay alone does not admit scientific evidence.'}}


def frozen_problems(snapshot_path, frozen, expected_revision):
    problems = source_integrity(frozen, snapshot_path.with_name('code.zip'))
    if not isinstance(expected_revision, str) or not expected_revision.strip() or frozen.get('revision') != expected_revision:
        problems.append('Wrong frozen framework revision')
    required = [LAUNCHER, Path(__file__), REPO / TIMING_SOURCE,
                 *(CAMPAIGN / 'harness' / name for name in ('runtime.py', 'run_host.py', 'timing.py', 'executor_capture.py')),
                 HERE / 'retained_reads.py', HERE / 'canary_exit_proof.py', HERE / 'empty_startup_reads.py',
                 HERE / 'raw_tool_result_reads.py',
                *(PRIOR / name for name in ('assess_bootstrap.py', 'assess_smoke.py', 'assess_pilot.py'))]
    for path in required:
        name = path.relative_to(REPO).as_posix()
        if name not in frozen.get('sources', {}):
            problems.append('Required source absent from frozen inventory: ' + name)
    for name, expected in frozen.get('sources', {}).items():
        path = REPO / name
        if Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink() or not path.is_file():
            problems.append('Absent/invalid source: ' + name)
        elif sha(path.read_bytes()) != expected['sha256']:
            problems.append('Changed source: ' + name)
    return problems


def source_receipt_matches(receipt, frozen, directory):
    expected = {Path(name).name: row['sha256'] for name, row in frozen['sources'].items()
                if Path(name).parent.as_posix() == directory and name.endswith('.py')}
    return bool(expected) and receipt == expected


def queue_paths_match(job, manifest_path, evidence, host, workspace, mode='pilot'):
    """Bind exact direct launcher command; arbitrary outer-worker receipts fail."""
    argv = job.get('argv', [])
    if workspace is None or mode not in ('pilot', 'smoke') or len(argv) != 15 or argv[1:4] != ['-X', 'utf8', '-B']:
        return False
    cwd = Path(job.get('cwd', REPO))
    interpreter = (REPO / 'venv/Scripts/python.exe').resolve()
    if (cwd.resolve() != REPO.resolve() or Path(argv[0]).resolve() != interpreter
            or Path(job.get('resolved_executable', '')).resolve() != interpreter
            or (cwd / argv[4]).resolve() != LAUNCHER.resolve()
            or argv[-2:] != ['--mode', mode]):
        return False
    values = (('--manifest', manifest_path), ('--evidence', evidence), ('--host-evidence', host),
              ('--workspace', Path(workspace)))
    for pos, (name, path) in zip((5, 7, 9, 11), values):
        if argv[pos] != name or (cwd / argv[pos + 1]).resolve() != path.resolve():
            return False
    return True


def queue_time_matches(job, launch, client, history):
    """Bind observed attempt time to the authenticated queue execution window."""
    try:
        stamp = lambda value: datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
        first, last = stamp(job['started_at']), stamp(job['ended_at'])
        model_first, model_last = stamp(launch['started_utc']), stamp(client['finished_utc'])
        starts = [e['wall_unix_s'] for e in history if e.get('type') == 'episode_started']
        stops = [e['wall_unix_s'] for e in history if e.get('type') == 'episode_stopped']
        return (first < last and first <= model_first <= model_last <= last
                and len(starts) == len(stops) == 1 and first <= starts[0] <= stops[0] <= last)
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def require(condition, message):
    if condition is not True:
        raise ValueError(message)


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def timing_monitor(frozen, source_record):
    """Extract only the unchanged monitor from the independently frozen source."""
    require(source_record.get('path') == TIMING_SOURCE, 'Wrong TimingMonitor source path')
    path = REPO / TIMING_SOURCE
    raw = path.read_bytes()
    expected = frozen.get('sources', {}).get(TIMING_SOURCE, {})
    require(expected.get('sha256') == sha(raw) == source_record.get('file_sha256')
            and expected.get('bytes') == len(raw), 'TimingMonitor source differs from frozen bytes')
    source = raw.decode('utf-8')
    tree = ast.parse(source)
    nodes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'TimingMonitor']
    require(len(nodes) == 1, 'Exactly one frozen TimingMonitor required')
    class_sha = sha(ast.get_source_segment(source, nodes[0]).encode('utf-8'))
    require(source_record.get('class_sha256') == class_sha, 'TimingMonitor class hash mismatch')
    namespace = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['TimingMonitor'], class_sha


def verify_timing(host, host_result, frozen):
    """Independently replay every retained sample; never reconstruct sparse events."""
    host = Path(host)
    metadata_path, sample_path = host / 'timing-v2.json', host / 'timing-samples.bin'
    require(metadata_path.is_file() and sample_path.is_file()
            and not metadata_path.is_symlink() and not sample_path.is_symlink(),
            'Protected timing metadata and binary samples must be ordinary files')
    metadata_bytes, sample_bytes = metadata_path.read_bytes(), sample_path.read_bytes()
    metadata = json.loads(metadata_bytes)
    require(metadata.get('schema') == 'rci-prospective-timing-2'
            and metadata.get('sample_file') == sample_path.name, 'Wrong retained timing schema or sample path')
    count = metadata.get('sample_count')
    require(type(count) is int and count >= 2 and type(metadata.get('byte_count')) is int
            and len(sample_bytes) == metadata['byte_count'] == count * 16, 'Timing sample length/count mismatch')
    require(metadata.get('sha256') == sha(sample_bytes), 'Timing sample hash mismatch')
    origin = metadata.get('loop_origin', {})
    clock = origin.get('clock', {})
    require(finite(origin.get('monotonic_s')) and origin['monotonic_s'] >= 0
            and finite(origin.get('initial_sim_s')) and origin['initial_sim_s'] >= 0
            and clock.get('monotonic') is True and clock.get('adjustable') is False
            and finite(clock.get('resolution')) and clock['resolution'] > 0
            and isinstance(clock.get('implementation'), str) and bool(clock['implementation']),
            'Timing common loop origin or monotonic clock evidence malformed')
    monitor_type, class_sha = timing_monitor(frozen, metadata.get('monitor_source', {}))
    monitor, previous = monitor_type(), None
    for index, sample in enumerate(struct.iter_unpack('<dd', sample_bytes)):
        wall, sim = sample
        require(finite(wall) and finite(sim) and wall >= 0 and sim >= 0, 'Non-finite or negative timing sample')
        require(index != 0 or sample == (0., 0.), 'Timing samples must start at the common zero origin')
        require(previous is None or (wall >= previous[0] and sim >= previous[1]), 'Timing sample moved backwards')
        monitor.observe(wall, sim)
        previous = sample
    terminal = metadata.get('terminal', {})
    require(previous == (terminal.get('wall_elapsed_s'), terminal.get('sim_elapsed_s'))
            and terminal.get('reason') == host_result.get('terminal')
            and isinstance(terminal.get('reason'), str), 'Timing terminal sample or reason mismatch')
    derived = monitor.report()
    require(metadata.get('report') == derived, 'Retained timing report differs from independent replay')
    binding = host_result.get('timing_v2', {})
    scheduling = metadata.get('scheduling', {})
    require(binding.get('scheduling') == scheduling == host_result.get('scheduling'),
            'Host scheduling receipts differ from retained metadata')
    scheduling_pass = (scheduling.get('schema') == 'rci-windows-scheduling-1'
                       and scheduling.get('platform') == 'win32'
                       and scheduling.get('requested_priority') == 'ABOVE_NORMAL_PRIORITY_CLASS'
                       and scheduling.get('timer_period_ms') == 1
                       and scheduling.get('applied') is True and scheduling.get('restored') is True
                       and scheduling.get('observed_priority_class') == 0x8000
                       and type(scheduling.get('previous_priority_class')) is int
                       and scheduling['previous_priority_class'] > 0
                       and scheduling.get('restored_priority_class') == scheduling['previous_priority_class']
                       and type(scheduling.get('time_begin_period_status')) is int
                       and scheduling['time_begin_period_status'] == 0
                       and type(scheduling.get('time_end_period_status')) is int
                       and scheduling['time_end_period_status'] == 0
                       and scheduling.get('restore_errors') == [] and not scheduling.get('error'))
    captured_pass = derived['actual_host_timing_pass'] and scheduling.get('applied') is True and scheduling.get('restored') is True
    expected_binding = {'schema': 'rci-prospective-timing-2', 'metadata_file': metadata_path.name,
                        'metadata_sha256': sha(metadata_bytes), 'sample_file': sample_path.name,
                        'sample_sha256': sha(sample_bytes), 'sample_count': count,
                        'passed': captured_pass, 'loop_origin': origin}
    require(all(binding.get(name) == value for name, value in expected_binding.items())
            and type(binding.get('sample_count')) is int and type(binding.get('passed')) is bool,
            'Host timing binding differs from retained samples or common loop origin')
    original = host_result.get('timing', {})
    require(finite(original.get('maximum_wall_minus_sim_s'))
            and original['maximum_wall_minus_sim_s'] == derived['maximum_lag_s']
            and type(original.get('samples')) is int and original['samples'] == count,
            'Host maximum lag or sample count differs from independent replay')
    resources = verify_resources(host, metadata, host_result, frozen)
    continuous = verify_continuous_physics(host, metadata, host_result, frozen)
    return {'schema': 'rci-campaign-independent-timing-2',
            'passed': (derived['actual_host_timing_pass'] and scheduling_pass
                       and resources['resource_integrity_pass'] and continuous['passed']),
            **resources,
            **({'continuous_physics_integrity': continuous} if continuous['applicable'] else {}),
            'metadata_sha256': sha(metadata_bytes), 'sample_sha256': sha(sample_bytes),
            'sample_count': count, 'sample_bytes': len(sample_bytes), 'loop_origin': origin,
            'terminal': terminal, 'timing_monitor': {**metadata['monitor_source'], 'class_sha256': class_sha},
            'replayed_timing': derived, 'scheduling': scheduling, 'scheduling_pass': scheduling_pass,
            'scope': 'Complete retained before/after-tick and terminal samples share the live pacing origin. '
                     'The unchanged monitor uses interpolated one-second wall windows, strict lag <0.1 s, '
                     'RTF 0.95 through 1.05 and outside fraction <0.01. Initialization and cleanup are excluded.'}


def verify_transport(stage_root, registry, history):
    """Join pre-dispatch traces to replies and distinguish local from host denials."""
    root = Path(stage_root)
    for name in ('broker-failure.json', 'mirror-error.json'):
        require(not (root / name).exists(), 'Unresolved transport failure: ' + name)
    requests = jsonl(root / 'broker-requests.jsonl')
    events = jsonl(root / 'broker-events.jsonl')
    require(bool(requests) and len(requests) == len(events), 'Broker request/reply counts differ or are empty')
    traces = [row.get('trace_id') for row in requests]
    require(all(isinstance(value, str) and value for value in traces) and len(set(traces)) == len(traces),
            'Broker trace identities missing or duplicated')
    require([row.get('trace_id') for row in events] == traces, 'Broker reply order or trace identities differ')
    revocation_path = root / 'authority-revocation.json'
    revocation = read_json(revocation_path) if revocation_path.exists() else None
    latch_time = revocation.get('wall_unix_s') if revocation else None
    if revocation:
        require(finite(latch_time), 'Revocation time is missing or non-finite')
        response = revocation.get('response', {})
        require(isinstance(response, dict), 'Revocation response must be an object')
        source, reason = revocation.get('source'), revocation.get('reason')
        require(source in ('broker', 'public_mirror'), 'Unknown revocation source')
        if source == 'broker':
            matching = [row for row in events if row['trace_id'] == revocation.get('trace_id')]
            require(len(matching) == 1, 'Revocation has no unique broker reply')
            reply = matching[0]
            require(reply.get('origin') == 'protected_host'
                    and all(reply.get(key) == revocation.get(key) for key in ('method', 'path', 'status', 'response'))
                    and finite(reply.get('received_wall_unix_s')) and finite(reply.get('wall_unix_s'))
                    and reply['received_wall_unix_s'] <= latch_time <= reply['wall_unix_s'],
                    'Revocation must bind a protected host reply with matching provenance')
        else:
            require(revocation.get('trace_id') is None and revocation.get('method') == 'GET'
                    and revocation.get('path') == '/status', 'Mirror revocation source malformed')
        if reason == 'accepted_handback':
            require(source == 'broker' and revocation.get('method') == 'POST'
                    and revocation.get('path') == '/handback' and revocation.get('status') == 200,
                    'Accepted handback revocation requires protected POST /handback')
            request = json.loads(reply.get('request') or '{}')
            command = response.get('command', {})
            epoch = revocation.get('pinned_authority_epoch')
            require(type(epoch) is int and type(request.get('authority_epoch')) is int
                    and request['authority_epoch'] == epoch and type(response.get('authority_epoch')) is int
                    and response['authority_epoch'] == epoch + 1 and response.get('ok') is True
                    and response.get('owner') == 'conventional' and command.get('kind') == 'handback'
                    and command.get('phase') == 'terminal' and command.get('status') == 'completed'
                    and isinstance(request.get('request_id'), str) and bool(request['request_id'])
                    and command.get('request_id') == request['request_id'], 'Malformed accepted handback revocation')
            rid = request['request_id']
            protected = registry.get(rid, {})
            require(protected.get('actor') == 'robot' and protected.get('kind') == 'handback'
                    and protected.get('phase') == 'terminal' and protected.get('status') == 'completed'
                    and protected.get('envelope', {}).get('authority_epoch') == epoch
                    and any(event.get('type') == 'control_owner_changed' and event.get('owner') == 'conventional'
                            and event.get('authority_epoch') == epoch + 1
                            and event.get('payload', {}).get('request_id') == rid for event in history),
                    'Accepted handback revocation lacks protected registry/owner-transfer support')
        elif reason == 'host_capability_denied':
            require(revocation.get('status') == 403 and response.get('ok') is False
                    and response.get('error', {}).get('code') in ('unauthorized', 'invocation_retired'),
                    'Host revocation denial lacks explicit protected capability denial')
        else:
            raise ValueError('Unknown authority revocation reason')
    local_denials = 0
    for request, reply in zip(requests, events):
        require(all(request.get(key) == reply.get(key) for key in
                    ('trace_id', 'received_wall_unix_s', 'method', 'path', 'request_id', 'request')),
                'Broker reply differs from pre-dispatch request')
        received, completed = request.get('received_wall_unix_s'), reply.get('wall_unix_s')
        require(finite(received) and finite(completed) and received <= completed,
                'Broker receipt times invalid')
        origin = reply.get('origin')
        require(origin in ('protected_host', 'local_capability_fence', 'local_revocation_fence'),
                'Unknown broker reply origin')
        if origin != 'protected_host':
            local_denials += 1
            require(reply.get('status') == 403 and reply.get('response') ==
                    {'ok': False, 'error': {'code': 'invocation_capability_denied'}},
                    'Local capability fence must remain a denial, never successful host evidence')
            if origin == 'local_revocation_fence':
                require(revocation is not None and completed >= latch_time,
                        'Local revocation fence lacks prior established protected revocation')
        elif revocation:
            require(received <= latch_time, 'Broker forwarded a new request after established revocation')
    closure_path = root / 'mirror-after-revocation.json'
    closure = read_json(closure_path) if closure_path.exists() else None
    if closure:
        require(revocation is not None and closure.get('authority_revocation_established') is True
                and closure.get('method') == 'GET' and closure.get('path') == '/status'
                and closure.get('phase') == 'upstream_request'
                and closure.get('type') in ('URLError', 'TimeoutError', 'ConnectionError', 'ConnectionResetError',
                                            'ConnectionAbortedError', 'ConnectionRefusedError', 'BrokenPipeError')
                and finite(closure.get('wall_unix_s')) and closure['wall_unix_s'] >= latch_time,
                'Nonfatal mirror closure lacks established revocation or valid upstream failure provenance')
    return {'schema': 'rci-campaign-independent-transport-2', 'passed': True,
            'request_count': len(requests), 'local_denial_count': local_denials,
            'authority_revocation': revocation, 'nonfatal_mirror_closure': closure,
            'scope': 'Pre-dispatch broker traces bind reply origin. Local denials establish no host reply, '
                     'continuity commit, retirement receipt or task success.'}


def retained_inventory(roots):
    """Complete hashes, but no endpoint contents or ephemeral capabilities."""
    records = []
    for label, root in roots:
        for path in sorted(root.rglob('*')):
            if not path.is_file() or path.is_symlink() or 'endpoint' in path.name:
                continue
            records.append({'root': label, 'path': path.relative_to(root).as_posix(),
                            'bytes': path.stat().st_size, 'sha256': hash_file(path)})
    return records


def assess(manifest_path, evidence, host_evidence, queue_receipt, snapshot_path,
           manifest_sha256, expected_job_id=None, timing_max_lag_s=None, expected_workspace=None,
           *, expected_revision=None):
    # Deliberately authenticate queue completion before any outcome access.
    job = queue_gate(read_json(queue_receipt), expected_job_id)
    require(isinstance(expected_revision, str) and bool(expected_revision.strip()),
            'An explicit predeclared framework revision is required')
    manifest_path, root, host, frozen_path = map(Path, (manifest_path, evidence, host_evidence, snapshot_path))
    paths_match = queue_paths_match(job, manifest_path, root, host, expected_workspace)
    require(paths_match, 'Official queue exact Campaign 002 direct launcher and attempt paths required')
    manifest_bytes = manifest_path.read_bytes()
    if sha(manifest_bytes) != manifest_sha256:
        raise ValueError('New campaign manifest differs from its predeclared SHA256')
    manifest, frozen = json.loads(manifest_bytes), read_json(frozen_path)
    require(manifest.get('framework_revision') == expected_revision,
            'Manifest framework revision differs from predeclared revision')
    source_problems = frozen_problems(frozen_path, frozen, expected_revision)
    require(not source_problems, 'Frozen source/archive/revision integrity failed: ' + '; '.join(source_problems))
    sequence = read_json(root / 'sequence-result.json')
    stage = inspect_stage(root / 'pilot', frozen_path.with_name('code.zip'))
    host_result = read_json(host / 'result.json')
    registry, history = read_json(host / 'command-registry.json'), jsonl(host / 'public-history.jsonl')
    outcome = classify_outcome(host_result, registry, history)
    model = model_disposition(stage['client'], stage['native_exit_code'])
    lifecycle = lifecycle_disposition(stage, sequence, host_result, history, outcome)
    initial = read_json(root / 'pilot/canary-stdout.json')
    codehost = read_json(root / 'pilot/codehost-canary-stdout.json')
    location = read_json(root / 'pilot/runtime-location.json')
    code_checks = codehost.get('checks', {})
    notes = continuity_commits(stage, host)
    verifications, verification_errors = {}, {}
    for name, verifier in (
            ('timing', lambda: verify_timing(host, host_result, frozen)),
            ('transport', lambda: verify_transport(root / 'pilot', registry, history)),
            ('transport_lifecycle', lambda: verify_transport_integrity(root / 'pilot', frozen))):
        try:
            verifications[name] = verifier()
        except (ValueError, KeyError, TypeError, OSError, struct.error) as error:
            verifications[name] = None
            verification_errors[name] = str(error)
    actions = [row for row in registry.values() if row.get('actor') == 'robot' and row.get('kind') == 'command']
    observations = [row for row in registry.values() if row.get('actor') == 'robot' and row.get('kind') == 'observe']
    commands = []
    for row in actions:
        dispatched = [e['event_id'] for e in history if e.get('type') == 'command_dispatched'
                      and e.get('payload', {}).get('request_id') == row.get('request_id')]
        commands.append({'request_id': row.get('request_id'), 'action': row.get('envelope', {}).get('action'),
                         'status': row.get('status'), 'phase': row.get('phase'), 'admission': row.get('admission'),
                         'error': row.get('error'), 'dispatch_event_ids': dispatched,
                         'public_effect': public_support(row, history)})
    checks = {name: stage['checks'].get(name) is True for name in (
        'exact_sole_bootstrap', 'configured_astra_max_chatgpt', 'remote_runtime_no_ambient_context',
        'actual_model_started', 'native_client_shutdown_recorded', 'all_namespace_retirements_observed',
        'actual_file_bytes_durable_across_cleanup', 'cleanup_completed', 'program_source_records_hash_valid')}
    lag = host_result.get('timing', {}).get('maximum_wall_minus_sim_s')
    timing_observed = type(lag) in (float, int) and math.isfinite(lag) and lag >= 0
    host_clean = (host_result.get('execution_completed') is True and not host_result.get('error')
                  and sequence.get('host_exit_code') == 0 and not sequence.get('forced_host_exit'))
    checks.update({
        'official_queue_succeeded_exit0': True,
        'frozen_source_and_archive_integrity': not source_problems,
        'campaign_manifest_exact_predeclared_bytes': True,
        'campaign_manifest_exact_predeclared_revision': True,
        'host_manifest_exact_campaign_content': read_json(host / 'manifest.json') == manifest,
        'run_identity_matches': host_result.get('run_id') == manifest.get('run_id'),
        'host_mode_serve_fixed_qualified_limits': manifest.get('schema') == 'robot-codex-development-manifest-1.0'
            and manifest.get('stage') == 'development-only' and manifest.get('mode') == 'serve'
            and manifest.get('action_request_budget') == 20 and manifest.get('observation_request_budget') == 50
            and manifest.get('invocation_wall_cap_s') == 600 and manifest.get('model_turns_max') == 1,
        'one_uninterrupted_orchestrated_invocation': sequence.get('mode') == 'pilot'
            and sequence.get('orchestrator_completed') is True and len(sequence.get('stages', [])) == 1
            and stage['result'].get('injected_interruption') is False and host_result.get('robot_invocations') == 1,
        'protected_host_completed_cleanly': host_clean,
        'model_disposition_recognized': model['recognized'],
        'qualified_lifecycle_end_observed': lifecycle['valid'],
        'all_45_outer_boundary_canaries': initial.get('qualified') is True
            and len(initial.get('checks', {})) == 45 and all(v is True for v in initial['checks'].values()),
        'positive_controls_and_durable_workspace': len(location.get('setup', {}).get('protected_exist', {})) == 4
            and all(location['setup']['protected_exist'].values())
            and location.get('setup', {}).get('outside_loopback_control') is True
            and location.get('durable_backing') is True
            and location.get('run', '').startswith('/var/tmp/robot-codex-session10/'),
        'codehost_ambient_capabilities_denied': codehost.get('host_qualified') is True
            and code_checks.get('all_tools_count') == 0 and code_checks.get('tools') == []
            and bool(code_checks.get('apis')) and all(v == 'undefined' for v in code_checks.get('apis', {}).values())
            and bool(code_checks.get('imports')) and all(v == 'denied' for v in code_checks.get('imports', {}).values()),
        'frozen_native_runtime_loaded': source_receipt_matches(read_json(host / 'frozen-source-verification.json'), frozen,
            'Long-Horizon Adaptive Robotics Expirement/Runtime 004'),
        'frozen_recorder_loaded': source_receipt_matches(read_json(host / 'recorder-source-verification.json'), frozen,
            'Long-Horizon Adaptive Robotics Expirement/Storage Retention Implementation 001/future'),
        'no_repeated_dispatch_per_robot_request': all(len(row['dispatch_event_ids']) <= 1 for row in commands),
        'host_request_budgets_respected': sum(row.get('admission', {}).get('status') == 'accepted' for row in actions) <= 20
            and sum(row.get('status') in ('accepted', 'completed') for row in observations) <= 50,
        'claimed_public_effects_match': all(row['public_effect']['independently_matched'] is not False for row in commands)
            and all(row['independently_matched'] is not False for row in outcome['conventional_public_effects'].values()),
        'protected_continuity_receipts_match': not notes['problems'],
        'independent_evaluator_well_formed_consistent': not outcome['independent_outcome_evidence_problems']
            and outcome['task_success_terminal_consistent'] is True,
        'core_recording_not_exhausted': host_result.get('terminal') not in ('storage_cap', 'infrastructure_error'),
        'timing_observed': timing_observed,
        'queue_attempt_times_match': queue_time_matches(job, stage['launch'], stage['client'], history),
        'complete_retained_timing_replayed_and_passed': verifications['timing'] is not None
            and verifications['timing']['passed'] is True,
        'bounded_host_memory_and_collector_integrity': verifications['timing'] is not None
            and verifications['timing']['resource_integrity_pass'] is True,
        'transport_revocation_and_reply_provenance': verifications['transport'] is not None
            and verifications['transport']['passed'] is True,
        'complete_codehost_lifecycle_and_safe_metadata': verifications['transport_lifecycle'] is not None
            and verifications['transport_lifecycle']['passed'] is True,
    })
    if timing_max_lag_s is not None:
        checks['predeclared_maximum_clock_lag'] = timing_observed and lag <= timing_max_lag_s
    checks['queue_exact_direct_attempt_command_matches'] = paths_match
    result = decision(checks, outcome, model)
    result.update(schema='robot-codex-campaign-assessment-2', framework_revision=expected_revision,
        run_id=manifest['run_id'], queue_job_id=job.get('id'), checks=checks,
        family=manifest.get('family'), seed=manifest.get('seed'), noise_seed=manifest.get('noise_seed'),
        source_integrity_problems=source_problems, recovery_and_task_outcome=outcome,
        lifecycle=lifecycle, robot_commands=commands, robot_observation_requests=len(observations),
        continuity=notes, program_records=stage['programs'],
        campaign_timing=verifications['timing'], transport=verifications['transport'],
        transport_lifecycle=verifications['transport_lifecycle'],
        verification_errors=verification_errors,
        executor_capture=stage['executor_capture'],
        source_read_projection_evidence={item['id']:item['executor_provenance'] for item in stage['source_commands']},
        model_canary_repetition_observed=stage['checks'].get('all_45_model_canaries_saved'),
        actual_canary_retained_evidence=stage['canary_matches'],
        canary_check_values_audit=stage.get('canary_exit_proof'),
        time={'maximum_wall_minus_sim_s': lag, 'sim_elapsed_s': host_result.get('sim_elapsed_s'),
              'wall_elapsed_s': host_result.get('wall_elapsed_s'), 'predeclared_max_lag_s': timing_max_lag_s},
        bindings={'manifest_sha256': manifest_sha256, 'framework_snapshot_sha256': hash_file(frozen_path),
                  'framework_archive_sha256': hash_file(frozen_path.with_name('code.zip')),
                  'queue_receipt_sha256': hash_file(queue_receipt),
                  'assessment_sha256': hash_file(Path(__file__)),
                  'readiness_helpers_sha256': {name: hash_file(PRIOR / name) for name in
                      ('assess_bootstrap.py', 'assess_smoke.py', 'assess_pilot.py')},
                  'queue_direct_attempt_paths_match': paths_match},
        evidence_inventory=retained_inventory([('orchestrator', root), ('protected_host', host)]),
        model_calls_in_assessment=0,
        limitations=['Development-fixture repeated-attempt evidence; two fixed challenge families, not universal recovery.',
                    'Task success and protected handback are separate from host, model, and evidence validity.',
                    'Model-authored programs and continuity notes are corroborating artifacts, not evaluator authority.',
                    'Complete retained timing samples are independently replayed with unchanged thresholds; unobserved between-sample transients remain unknown.'])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'evidence', 'host-evidence', 'queue-receipt', 'snapshot', 'workspace', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--job-id', required=True)
    parser.add_argument('--framework-revision', required=True)
    parser.add_argument('--timing-max-lag-s', type=float)
    args = parser.parse_args(argv)
    result = assess(args.manifest, args.evidence, args.host_evidence, args.queue_receipt,
                    args.snapshot, args.manifest_sha256, args.job_id, args.timing_max_lag_s, args.workspace,
                    expected_revision=args.framework_revision)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(result, out, indent=2, allow_nan=False); out.write('\n')
    print(json.dumps({key: result[key] for key in ('run_id', 'validity', 'task_outcome', 'failed_checks')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
