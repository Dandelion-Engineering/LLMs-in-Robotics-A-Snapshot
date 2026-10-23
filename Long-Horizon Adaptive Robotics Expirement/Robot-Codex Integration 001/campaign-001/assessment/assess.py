"""Read-only Campaign 001 assessment of the unchanged RCI001-wsl-010d runner.

The campaign manifest is independently bound; the original readiness manifest is
never relabeled. A bounded model failure is distinct from infrastructure validity.
No model, simulator, queue mutation, or credential endpoint is called here.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
INTEGRATION = HERE.parents[1]
REPO = INTEGRATION.parents[1]
PRIOR = INTEGRATION / 'readiness-session-10' / 'assessment'
sys.path.insert(0, str(PRIOR))
from assess_bootstrap import read_json, sha
from assess_smoke import inspect_stage, jsonl, continuity_commits
from assess_pilot import classify_outcome, public_support, source_integrity

REVISION = 'RCI001-wsl-010d'
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
                'reason': 'Episode evidence assessment only. Full timing, storage/accounting and frozen scientific-release admission require a separately verified external certificate; no certificate consumer is implemented here.'}}


def frozen_problems(snapshot_path, frozen):
    problems = source_integrity(frozen, snapshot_path.with_name('code.zip'))
    if frozen.get('revision') != REVISION:
        problems.append('Wrong frozen framework revision')
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


def queue_paths_match(job, manifest_path, evidence, host, workspace):
    """Bind exact direct launcher command; arbitrary outer-worker receipts fail."""
    argv = job.get('argv', [])
    if workspace is None or len(argv) != 15 or argv[1:4] != ['-X', 'utf8', '-B']:
        return False
    cwd = Path(job.get('cwd', REPO))
    interpreter = (REPO / 'venv/Scripts/python.exe').resolve()
    if (cwd.resolve() != REPO.resolve() or Path(argv[0]).resolve() != interpreter
            or Path(job.get('resolved_executable', '')).resolve() != interpreter
            or (cwd / argv[4]).resolve() != (INTEGRATION / 'readiness-session-10/orchestrator/physical.py').resolve()
            or argv[-2:] != ['--mode', 'pilot']):
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
           manifest_sha256, expected_job_id=None, timing_max_lag_s=None, expected_workspace=None):
    # Deliberately authenticate queue completion before any outcome access.
    job = queue_gate(read_json(queue_receipt), expected_job_id)
    manifest_path, root, host, frozen_path = map(Path, (manifest_path, evidence, host_evidence, snapshot_path))
    manifest_bytes = manifest_path.read_bytes()
    if sha(manifest_bytes) != manifest_sha256:
        raise ValueError('New campaign manifest differs from its predeclared SHA256')
    manifest, frozen = json.loads(manifest_bytes), read_json(frozen_path)
    source_problems = frozen_problems(frozen_path, frozen)
    sequence = read_json(root / 'sequence-result.json')
    stage = inspect_stage(root / 'pilot')
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
    })
    if timing_max_lag_s is not None:
        checks['predeclared_maximum_clock_lag'] = timing_observed and lag <= timing_max_lag_s
    paths_match = queue_paths_match(job, manifest_path, root, host, expected_workspace)
    checks['queue_exact_direct_attempt_command_matches'] = paths_match
    result = decision(checks, outcome, model)
    result.update(schema='robot-codex-campaign-assessment-1', framework_revision=REVISION,
        run_id=manifest['run_id'], queue_job_id=job.get('id'), checks=checks,
        family=manifest.get('family'), seed=manifest.get('seed'), noise_seed=manifest.get('noise_seed'),
        source_integrity_problems=source_problems, recovery_and_task_outcome=outcome,
        lifecycle=lifecycle, robot_commands=commands, robot_observation_requests=len(observations),
        continuity=notes, program_records=stage['programs'],
        model_canary_repetition_observed=stage['checks'].get('all_45_model_canaries_saved'),
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
                    'Timing is observed clock lag; no unmeasured real-time-equivalence claim.'])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'evidence', 'host-evidence', 'queue-receipt', 'snapshot', 'workspace', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--job-id', required=True)
    parser.add_argument('--timing-max-lag-s', type=float)
    args = parser.parse_args(argv)
    result = assess(args.manifest, args.evidence, args.host_evidence, args.queue_receipt,
                    args.snapshot, args.manifest_sha256, args.job_id, args.timing_max_lag_s, args.workspace)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(result, out, indent=2, allow_nan=False); out.write('\n')
    print(json.dumps({key: result[key] for key in ('run_id', 'validity', 'task_outcome', 'failed_checks')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
