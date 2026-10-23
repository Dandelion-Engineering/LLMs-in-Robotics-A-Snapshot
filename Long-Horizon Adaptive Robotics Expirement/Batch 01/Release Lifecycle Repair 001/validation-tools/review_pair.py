"""Queue-only metadata assessment of actual A3-009/010 recovery admission.

Required CLI: --pair-receipt --finish-report --finish-receipt --derived-index
--derivation-receipt --qualification-freeze --output (a fresh JSON file).
Reads compact metadata and Python source identities only. Never reads event,
motion or geometry streams, launches a trial, changes a result, or grants global
readiness. A completed assessment may explicitly fail or retain unknown checks.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys

from run_lifecycle_pair import (DEFAULT_OUTPUT, DEFAULT_RAW, EXP, HERE, PLAN,
    RUNTIME, RUN_IDS, Inputs, argument, digest, official, receipt_path, ref, require, save)

REQUIRED_PREDICATES = {
    'finite_snapshot', 'object_identity_integrity', 'objects_in_declared_envelope',
    'robot_configuration', 'contact_penetration', 'supported_actual_cut',
    'action_generation_ownership', 'phase_matches_current_action', 'current_action_lease',
    'station_safe_state', 'fresh_public_capture', 'unheld_bodies_supported_and_slow',
    'finite_buffer_capacity', 'recovery_buffer_inventory', 'phase_contact_consistency',
    'measured_grip_envelope', 'measured_recovery_route'}
PRIOR_REVIEW = EXP / 'Batch 01/Release Environment Repair 001/pair-validation-001.json'
TERMINAL = {'completed', 'failed', 'timed_out', 'aborted'}


def get(value, *keys):
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def close(a, b):
    return finite(a) and finite(b) and math.isclose(a, b, rel_tol=0, abs_tol=1e-8)


def stamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def compact_identity(value):
    return {k: v for k, v in (value or {}).items() if k != 'artifact_files'}


def compact_absence(value):
    return {k: compact_identity(v) if k == 'qualification_identity' else v for k, v in (value or {}).items()}


def expected_values(receipt, flag):
    argv = receipt['argv']
    return [argv[i + 1] for i, value in enumerate(argv[:-1]) if value == flag]


def evidence_matches(rows, path, sha, base):
    for row in rows:
        if row.get('state') != 'available' or row.get('sha256') != sha:
            continue
        value = Path(row.get('uri', ''))
        if (value if value.is_absolute() else base / value).resolve() == path.resolve():
            return True
    return False


def assess_run(rid, expected, header, completion, index_row, finish_row, inputs, qualification,
               bundle, runtime_hashes, pair_id, canonical_data):
    checks, details = {}, {}
    def check(name, condition, observed=None):
        checks[name] = condition is True
        details[name] = {'state': 'unknown' if condition is None else 'pass' if condition is True else 'fail',
                         'observed': observed}
    check('derivation_completed_without_integrity_findings', index_row.get('status') == 'completed'
          and index_row.get('errors') == [] and index_row.get('requires_operator_review') is False)
    sources = {}
    for name in ('result.json', 'manifest.json'):
        item = index_row['sources'][name]
        path = inputs.verify(item)
        require(path == DEFAULT_RAW / rid / name, 'Unexpected raw metadata path')
        sources[name] = ref(path)
    result = inputs.read(sources['result.json']['path'])
    manifest = inputs.read(sources['manifest.json']['path'])
    canonical_path = inputs.verify(index_row['canonical_assessment'])
    assessment = inputs.read(canonical_path)
    canonical = assessment['current_result']
    run_record = assessment['run']
    finished = inputs.read(inputs.verify(finish_row['result']))
    live_results = [r for r in canonical_data['result'] if r.get('run_id') == rid]
    superseded = {r.get('supersedes_result_id') for r in live_results}
    current = [r for r in live_results if r['id'] not in superseded]
    check('unique_canonical_finish_matches_derived_record', len(current) == 1 and current[0] == canonical == finished
          and canonical.get('id') == finish_row.get('canonical_result_id') == index_row.get('canonical_result_id'))
    registration_ref = canonical['details']['registration_manifest']
    registration_path = inputs.verify(registration_ref)
    require(registration_path == EXP / 'Architecture Map/releases' / rid / 'manifest.json',
            'Unexpected registered manifest path')
    registration = inputs.read(registration_path)
    sources.update(canonical_assessment=ref(canonical_path), registration_manifest=ref(registration_path),
                   finished_canonical_result=finish_row['result'])
    check('canonical_raw_result_and_registration_bytes_match',
          evidence_matches(canonical.get('evidence', []), Path(sources['result.json']['path']),
                           sources['result.json']['sha256'], EXP / 'Architecture Map')
          and evidence_matches(run_record.get('evidence', []), registration_path, registration_ref['sha256'],
                               EXP / 'Architecture Map')
          and get(canonical, 'details', 'queue_job_id') == pair_id == index_row.get('execution_queue_job_id'))
    attempt = [r for r in completion.get('attempts', []) if r.get('run_id') == rid]
    check('wrapper_raw_result_identity_matches', len(attempt) == 1
          and attempt[0].get('result_sha256') == sources['result.json']['sha256'])
    check('fixed_development_configuration_and_condition_match',
          all(d.get('run_id') == rid for d in (result, manifest, registration))
          and result.get('stage') == manifest.get('stage') == run_record.get('stage') == 'development'
          and result.get('execution_status') in TERMINAL and canonical.get('execution_status') in TERMINAL
          and manifest.get('architecture') == registration.get('kind') == expected['kind'] == 'A3'
          and manifest.get('condition') == registration.get('condition') == expected['condition']
          and manifest.get('scenario') == registration.get('scenario') == 'restart'
          and manifest.get('part_count') == registration.get('part_count') == 3
          and manifest.get('world_seed') == registration.get('world_seed') == result.get('world_seed') == 2
          and manifest.get('policy_noise_seed') == registration.get('policy_noise_seed') == result.get('policy_noise_seed') == 11
          and manifest.get('cap_s') == registration.get('cap_s') == 300)
    check('all_58_runtime_source_identities_match', len(runtime_hashes) == 58
          and manifest.get('code_sha256') == registration.get('runtime_files') == header['runtime_sha256'] == runtime_hashes)
    check('fresh_qualification_identity_matches', manifest.get('restart_qualification_identity') == qualification
          and get(registration, 'development_restart_qualification', 'verified_identity') == qualification
          and get(registration, 'development_restart_qualification', 'path') == qualification['freeze_manifest']['path']
          and get(registration, 'development_restart_qualification', 'sha256') == qualification['freeze_manifest']['sha256'])

    derived = {}
    for name in ('continuity', 'diagnostics'):
        row = index_row['derived'][name]
        path = inputs.verify(row['artifact'])
        require(path == canonical_path.parent / (name + '.json'), 'Unexpected derived report path')
        value = inputs.read(path)
        derived[name] = value
        sources[name] = ref(path)
        check(name + '_derived_integrity', row.get('status') == 'completed' and row.get('integrity_findings') == []
              and value.get('run_id') == rid and value.get('integrity_findings') == [])
    exposure = result.get('restart_exposure') or {}
    admissibility = exposure.get('restart_admissibility') or {}
    check('actual_configured_carry_cut_without_fallback', result.get('restart_exercised') is True
          and exposure.get('configured_cut') == exposure.get('actual_cut') == 'closed_grip_transfer'
          and exposure.get('configured_transport_ordinal') == 1 and exposure.get('fallback_used') is False
          and exposure.get('configured_milestone_exercised') is True
          and exposure.get('actual_segment_phase') in (4, 5)
          and close(exposure.get('closed_grip_min_tcp_z_m'), .08)
          and finite(exposure.get('measured_tcp_z_m')) and exposure['measured_tcp_z_m'] >= .08
          and finite(exposure.get('measured_gripper_width_m')) and exposure['measured_gripper_width_m'] < .065
          and exposure.get('tcp_height_qualified') is True)
    predicates = admissibility.get('predicates') or []
    required = [p for p in predicates if p.get('required') is True]
    check('all_17_required_cut_predicates_pass', len(required) == 17
          and {p.get('name') for p in required} == REQUIRED_PREDICATES
          and all(p.get('state') == 'pass' for p in required),
          [{'name': p.get('name'), 'state': p.get('state')} for p in required])
    check('recorded_admissibility_is_admissible', admissibility.get('state') == 'admissible'
          and admissibility.get('configured_phase_reached') is True
          and admissibility.get('fallback_used') is False
          and admissibility.get('snapshot_sha256') == exposure.get('protected_restart_state_sha256'))
    rows = exposure.get('absence_observations') or []
    ready_rows = [r for r in rows if r.get('observed_endpoint') == 'restart_ready']
    admitted_rows = [r for r in rows if r.get('observed_endpoint') == 'recover_held_admitted']
    ready = ready_rows[0] if len(ready_rows) == 1 else {}
    admitted = admitted_rows[0] if len(admitted_rows) == 1 else {}
    before = get(exposure, 'authority_revocation', 'before_cancel') or {}
    after = get(exposure, 'authority_revocation', 'after_cancel') or {}
    start, end = admitted.get('start') or {}, admitted.get('end') or {}
    duration = end['wall_s'] - before['wall_s'] if finite(end.get('wall_s')) and finite(before.get('wall_s')) else None
    check('actual_endpoint_correlated_with_cancellation', len(admitted_rows) == 1
          and type(exposure.get('event_id')) is int and admitted.get('restart_event_id') == exposure.get('event_id')
          and start == before and finite(after.get('wall_s')) and finite(before.get('wall_s'))
          and after['wall_s'] >= before['wall_s']
          and admitted.get('qualified_endpoint') == 'recover_held_admitted' and admitted.get('qualified_timebase') == 'wall')
    check('duration_recomputed_from_before_cancel_wall_clock', None if duration is None else
          duration >= 0 and close(duration, admitted.get('wall_duration_s')),
          {'recomputed_wall_s': duration, 'recorded_wall_s': admitted.get('wall_duration_s')})
    check('actual_admission_within_unchanged_5_second_bound', None if duration is None else 0 <= duration <= 5,
          {'duration_s': duration, 'bound_s': 5.0})
    check('recorded_actual_absence_coverage_pass', get(admitted, 'coverage', 'state') == 'pass'
          and close(get(admitted, 'coverage', 'prospective_absence_bound_s'), 5)
          and close(get(admitted, 'coverage', 'actual_absence_s'), duration))
    mapping = qualification['payload_template_to_cell']
    cell_ids = set(mapping.values())
    evidence = admissibility.get('qualified_class_evidence') or []
    selected_ids = {row.get('cell_id') for row in evidence}
    cells = [c for c in bundle['cells'] if c['cell_id'] in selected_ids]
    check('selected_new_cell_covers_actual_wall_absence', bool(evidence) and len(selected_ids) == 1
          and selected_ids <= cell_ids and len(cells) == 1 and finite(duration)
          and all(row.get('state') == 'pass' and row.get('class_spec_sha256') == qualification['class_spec_sha256']
                  and row.get('qualification_sha256') == qualification['bundle_sha256']
                  and close(row.get('prospective_absence_bound_s'), 5)
                  and close(row.get('maximum_qualified_absence_s'), 5) for row in evidence)
          and close(cells[0].get('maximum_qualified_absence_s'), 5)
          and cells[0].get('absence_timebase') == 'wall' and cells[0].get('absence_endpoint') == 'recover_held_admitted'
          and 0 <= duration <= cells[0]['maximum_qualified_absence_s'], {'selected_cell_ids': sorted(str(x) for x in selected_ids)})
    control = admitted.get('control_admission') or {}
    check('admitted_recovery_route_matches_selected_cell', control.get('operation') == 'recover_held'
          and control.get('endpoint') == 'recover_held_admitted' and control.get('route_scope_matches') is True
          and isinstance(control.get('request_id'), str) and bool(control['request_id'])
          and len(cells) == 1 and control.get('destination') == get(cells[0], 'route_envelope', 'destination'))
    check('endpoint_qualification_identities_match', len(ready_rows) == len(admitted_rows) == 1
          and ready.get('qualification_identity') == admitted.get('qualification_identity') == qualification)
    check('preliminary_restart_ready_remains_unknown', len(ready_rows) == 1
          and get(ready, 'coverage', 'state') == 'unknown' and ready.get('restart_event_id') == exposure.get('event_id')
          and ready.get('qualified_endpoint') == 'recover_held_admitted' and ready.get('start') == before)
    check('physical_recovery_success_remains_not_assessed', ready.get('physical_recovery_success') ==
          admitted.get('physical_recovery_success') == control.get('physical_recovery_success') == 'not_assessed')
    check('actual_host_timing_check_passed', result.get('actual_host_timing_pass') is True
          and get(canonical, 'details', 'timing', 'actual_host_timing_pass') is True)
    check('no_recorded_infrastructure_or_cleanup_failure', result.get('infrastructure_invalid') is False
          and result.get('cleanup_errors') == [] and result.get('failure_class') != 'infrastructure_failure')
    check('development_validity_not_upgraded', result.get('validity') == canonical.get('validity') == 'unknown')
    return {'run_id': rid, 'condition': expected['condition'], 'sources': sources,
        'required_checks': checks, 'check_details': details, 'all_required_checks_passed': all(checks.values()),
        'canonical_result_id': canonical.get('id'), 'canonical_validity': canonical.get('validity'),
        'canonical_validity_reason': canonical.get('validity_reason'), 'raw_validity': result.get('validity'),
        'recorded_task_outcome': result.get('outcome'), 'failure_class': result.get('failure_class'),
        'task_outcome_used_to_establish_recovery': False,
        'actual_cut': {k: v for k, v in exposure.items() if k not in ('restart_admissibility', 'absence_observations')},
        'recorded_cut_predicates': predicates, 'required_cut_predicate_count': len(required),
        'recorded_admissibility_state': admissibility.get('state'),
        'recorded_calibration_input_sha256': admissibility.get('calibration_input_sha256'),
        'recorded_qualified_class_evidence': evidence, 'selected_cell_ids': sorted(str(x) for x in selected_ids),
        'authority_revocation': exposure.get('authority_revocation'),
        'preliminary_restart_ready': compact_absence(ready), 'actual_recovery_admission': compact_absence(admitted),
        'before_cancel_to_recover_held_admitted_wall_s': duration, 'qualified_wall_bound_s': 5.0,
        'actual_host_timing_pass': result.get('actual_host_timing_pass'), 'maximum_lag_s': result.get('maximum_lag_s'),
        'physical_recovery_success': admitted.get('physical_recovery_success', 'not_assessed'),
        'derived_continuity_limit': {'coverage': derived['continuity'].get('coverage'),
            'rows': [{k: r.get(k) for k in ('opportunity_id', 'qualified_restart', 'recovery', 'admissibility')}
                     for r in derived['continuity'].get('rows', [])]},
        'raw_streams_read': False}


def main(args):
    sys.path.insert(0, str(RUNTIME))
    import release_runner
    job = release_runner.queued_job(expected_script=Path(__file__).resolve())
    import record_attempt
    from restart_compatibility import digest as canonical_digest
    output = args.output.resolve()
    require(output.suffix == '.json' and not output.exists() and output.parent.is_dir()
            and not any(output.is_relative_to(p) for p in (RUNTIME, record_attempt.MAP, DEFAULT_RAW)),
            'Fresh operator report path outside source/raw/Map required')
    inputs, receipts, pair = Inputs(), [], []
    report = {'schema_version': 'lifecycle-recovery-endpoint-pair-validation-1',
        'queue_job_id': job['id'], 'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'incomplete', 'all_required_checks_passed': False, 'root_review_required': True,
        'pair': pair, 'official_receipts': receipts, 'preliminary_readiness': 'unknown',
        'physical_recovery_success': 'not_assessed', 'scored_ready': False, 'development_validity_upgraded': False,
        'scope': 'Observed carry-cut predicates and before-cancel to recovery-admission wall endpoint only; no task or physical recovery success inference'}
    try:
        for path in (Path(__file__), HERE / 'finish_pair.py', HERE / 'run_lifecycle_pair.py', PLAN, PRIOR_REVIEW):
            inputs.verify(ref(path))
        prior = inputs.read(PRIOR_REVIEW)
        require(all({p['name'] for p in row['recorded_cut_predicates'] if p['required']} == REQUIRED_PREDICATES
                    for row in prior['pair']), 'Required predicate contract differs from prior assessment')
        header = inputs.read(DEFAULT_OUTPUT / 'lifecycle-revalidation.json')
        completion = inputs.read(DEFAULT_OUTPUT / 'wrapper-completion.json')
        pair_id = header['queue_job_id']
        execution = official(release_runner, inputs, args.pair_receipt, pair_id, HERE / 'run_lifecycle_pair.py')
        require(header['schema_version'] == 'post-closure-lifecycle-revalidation-1'
                and completion['queue_job_id'] == pair_id and completion['input_changes'] == []
                and completion['not_started'] == [] and [r['run_id'] for r in completion['attempts']] == list(RUN_IDS),
                'Exact complete pair and unchanged wrapper inputs required')
        plan = inputs.read(PLAN)
        require(header['plan'] == plan and [r['run_id'] for r in plan] == list(RUN_IDS), 'Pair plan differs')
        # Verify small wrapper inputs, not its large qualification raw-stream closure.
        bound = {str(Path(r['path']).resolve()): r for r in header['input_refs']}
        for path in (HERE / 'run_lifecycle_pair.py', PLAN):
            inputs.verify(bound[str(path.resolve())])
        require(receipt_path(execution, '--qualification-freeze') == args.qualification_freeze.resolve(),
                'Execution used a different qualification freeze')
        runtime_hashes = {p.name: digest(p) for p in RUNTIME.glob('*.py')}
        require(len(runtime_hashes) == 58 and runtime_hashes == header['runtime_sha256'], 'Final Runtime 004 source identities differ')
        inputs.mapping({str(RUNTIME / name): sha for name, sha in runtime_hashes.items()})
        qualification = header['qualification_identity']
        require(inputs.verify(qualification['freeze_manifest']) == args.qualification_freeze.resolve(), 'Freeze reference differs')
        freeze = inputs.read(args.qualification_freeze)
        bundle = inputs.read(inputs.verify(qualification['bundle_file']))
        require(freeze['restart_matching_mode'] == 'qualified_class'
                and canonical_digest(bundle) == qualification['bundle_sha256'] == freeze['restart_qualification']['bundle_sha256']
                and canonical_digest(bundle['class_spec']) == qualification['class_spec_sha256'] == freeze['restart_qualification']['class_spec_sha256']
                and bundle['status'] == 'measured_development'
                and stamp(bundle['accepted_at_utc']) < stamp(freeze['frozen_at']) < stamp(execution['started_at'])
                and freeze['restart_qualification']['prospective_absence_bound_s'] == 5
                and freeze['restart_qualification']['absence_endpoint'] == 'recover_held_admitted'
                and freeze['restart_qualification']['absence_timebase'] == 'wall', 'Fresh qualification identity or unchanged bound differs')
        finish = inputs.read(args.finish_report)
        finished_receipt = official(release_runner, inputs, args.finish_receipt, finish['queue_job_id'],
                                   HERE / 'finish_pair.py', '--output', args.finish_report.parent)
        require(argument(finished_receipt, '--queue-job-id') == pair_id
                and receipt_path(finished_receipt, '--pair-receipt') == args.pair_receipt.resolve()
                and finish['schema_version'] == 'lifecycle-pair-canonical-finish-1'
                and finish['status'] == 'complete' and finish['all_required_checks_passed'] is True
                and finish['execution_queue_job_id'] == pair_id and finish['input_changes'] == []
                and finish['run_ids'] == list(RUN_IDS), 'Canonical finish report is incomplete or mismatched')
        inputs.verify(finish['pair_receipt'])
        for item in finish['source_files']:
            inputs.verify(item)
        index = inputs.read(args.derived_index)
        derive_receipt = official(release_runner, inputs, args.derivation_receipt, index['derivation_queue_job_id'],
            EXP / 'Engineering Investigation 004/process_development.py', '--output-dir', args.derived_index.parent)
        require(expected_values(derive_receipt, '--run-id') == list(RUN_IDS)
                and receipt_path(derive_receipt, '--receipt') == args.pair_receipt.resolve()
                and receipt_path(derive_receipt, '--evidence-root') == DEFAULT_RAW
                and index['schema_version'] == 'development-derived-batch-1.0'
                and index['status'] == 'completed' and index['selected_run_ids'] == list(RUN_IDS)
                and index['counts']['with_integrity_findings'] == 0,
                'Derivation receipt/report does not bind the exact completed pair')
        require(stamp(execution['ended_at']) < stamp(finished_receipt['started_at'])
                and stamp(finished_receipt['ended_at']) < stamp(derive_receipt['started_at']),
                'Execution, canonical finish and derivation order differs')
        for purpose, receipt, path in (('execution', execution, args.pair_receipt),
                ('canonical_finish', finished_receipt, args.finish_receipt), ('derivation', derive_receipt, args.derivation_receipt)):
            receipts.append({**ref(path), 'purpose': purpose, 'job_id': receipt['id'], 'state': receipt['state'],
                'exit_status': receipt['exit_status'], 'argv': receipt['argv'],
                'started_at': receipt['started_at'], 'ended_at': receipt['ended_at']})
        for item in index['implementation'].values():
            inputs.verify(item)
        canonical_data, _, errors = record_attempt.am.read_store(record_attempt.MAP)
        require(not errors, 'Current canonical records cannot be read')
        require([r['run_id'] for r in index['runs']] == [r['run_id'] for r in finish['finished']] == list(RUN_IDS),
                'Exact finalization/derivation pair required')
        for expected, row, finished in zip(plan, index['runs'], finish['finished']):
            try:
                pair.append(assess_run(expected['run_id'], expected, header, completion, row, finished,
                    inputs, qualification, bundle, runtime_hashes, pair_id, canonical_data))
            except Exception as error:
                pair.append({'run_id': expected['run_id'], 'all_required_checks_passed': False,
                    'required_checks': {'complete_source_bound_metadata': False},
                    'error_type': type(error).__name__, 'error': str(error), 'physical_recovery_success': 'not_assessed'})
        report.update(qualification_identity=compact_identity(qualification), candidate_distribution=header['candidate_distribution'],
                      pinned_environment_manifest=header['installed_environment_manifest'], runtime_root=str(RUNTIME),
                      runtime_source_count=len(runtime_hashes), required_checks={r['run_id']: r['required_checks'] for r in pair})
        changes = inputs.changes()
        report['input_changes'] = changes
        report['reviewed_small_inputs_unchanged_before_after'] = not changes
        report['all_required_checks_passed'] = len(pair) == 2 and all(r['all_required_checks_passed'] for r in pair) and not changes
        report['status'] = 'passed_scoped_checks' if report['all_required_checks_passed'] else 'failed_or_unknown_scoped_checks'
    except Exception as error:
        report.update(status='metadata_verification_failed', error_type=type(error).__name__, error=str(error))
    report['source_refs'] = list(inputs.refs.values())
    report['source_files'] = [r for r in inputs.refs.values() if Path(r['path']).suffix == '.py']
    report['limitations'] = [
        'Scoped assessment only; task completion does not establish physical recovery success or scored readiness.',
        'Preliminary restart_ready is retained separately from the qualified recover_held_admitted endpoint.',
        'Recorded protected predicate states are checked; this helper does not reconstruct geometry or infer a safe route.',
        'No event, motion or geometry stream is read or rehashed; official derivation retains its exact stream references.',
        'Qualification bundle/freeze bytes are checked here; full calibration artifact closure remains bound by the prior wrapper and final sealer.',
        'Raw/canonical validity and independent derived continuity uncertainty are retained without upgrading development denominators.']
    save(output, report)
    print(json.dumps({'report': str(output), 'status': report['status'],
                      'all_required_checks_passed': report['all_required_checks_passed']}))
    return 2 if report['status'] == 'metadata_verification_failed' else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('pair-receipt', 'finish-report', 'finish-receipt', 'derived-index',
                 'derivation-receipt', 'qualification-freeze', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    raise SystemExit(main(parser.parse_args()))
