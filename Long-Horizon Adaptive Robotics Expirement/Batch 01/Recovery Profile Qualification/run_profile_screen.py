"""Queued fixed raw-fixture profile screen; no qualification grant or policy change.

Versioned from the unchanged Recovery Qualification/run_screen.py, SHA256
281e0e44d81af0258f5bad36f541432635319c016b757df5899038120b77cdd3.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
import uuid
import zipfile

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
RUNTIME = PROJECT / 'Runtime'
CALIBRATION = HERE.parent / 'Calibration Tools'
RECOVERY = HERE.parent / 'Recovery Qualification'
sys.path.insert(0, str(RECOVERY))
from fixture import (SCHEMA, canonical, construct_xml, physical_snapshot_sources,
                     physical_trial_pass, retained_hold_check, select_public)
from profile_fixture import (PROFILE_REVISION, validate_plan, transport_action,
                             public_cut_matches, profile_rule_identity)
sys.path.insert(0, str(CALIBRATION))
import physical_calibration as base
from calibration_authority import child_authority, child_command, parent_authority
from measurement import EXECUTION_REVISION, HoldWindow, provisional_identity, selected_trials


def utc():
    return datetime.now(timezone.utc).isoformat()


def sources():
    paths = set(base.source_files())
    # Original extractor/fixture/measurement bytes remain in the archive at
    # their original paths, as required by unchanged downstream verification.
    for directory in (HERE, RECOVERY):
        paths.update(p.resolve() for p in directory.iterdir()
                     if p.is_file() and p.suffix in ('.py', '.md', '.json'))
    return sorted(paths)


def hashes():
    return {str(path): base.sha(path) for path in sources()}


def execution_selection(plan, destination, phase, diagnostic_trial=None):
    """A diagnostic may run one unchanged construction row, never validation."""
    trials = selected_trials(plan, destination, phase)
    diagnostic = diagnostic_trial is not None
    if diagnostic:
        if phase != 'construction' or not isinstance(diagnostic_trial, str) or not diagnostic_trial:
            raise ValueError('A diagnostic trial requires construction phase and one original trial ID')
        matches = [t for t in plan['trials'] if t['id'] == diagnostic_trial]
        if len(matches) != 1 or matches[0] not in trials:
            raise ValueError('Diagnostic trial is not one declared construction row at this destination')
        trials = matches
    deferred = [t['id'] for t in plan['trials'] if t not in trials
                and (diagnostic or destination == 'all' or t['destination'] == destination)]
    metadata = {'diagnostic_only': diagnostic, 'diagnostic_trial_id': diagnostic_trial,
                'is_full_phase_screen': not diagnostic,
                'execution_scope': 'single_original_construction_trial_diagnostic' if diagnostic else 'declared_phase_screen'}
    if diagnostic:
        metadata['qualification_evidence_eligible'] = False
    return trials, deferred, metadata


def manifest_execution(plan, manifest):
    trials, deferred, metadata = execution_selection(plan, manifest['destination_selection'],
        manifest['execution_phase'], manifest.get('diagnostic_trial_id'))
    if (manifest['modes'] != [t['id'] for t in trials] or manifest['phase_deferred_trial_ids'] != deferred
            or any(manifest.get(key) != value for key, value in metadata.items())):
        raise ValueError('Manifest execution selection or diagnostic scope differs from the original plan')
    return trials, deferred, metadata


class QualificationLoop(base.PhysicalLoop):
    def __init__(self, *args, **kwargs):
        self.geometry_trace = None
        self.hold_window = None
        super().__init__(*args, **kwargs)

    def step(self):
        super().step()
        if self.hold_window is not None:
            self.hold_window.record(self.hold_window.native_snapshot(self.cells[0]), float(self.cells[0].data.time),
                                    time.perf_counter() - self.start, tick=True)
        if self.geometry_trace is not None:
            self.geometry_trace.sample()
            self.monitor.observe(time.perf_counter() - self.start, self.elapsed)


def compiled_properties(cell, construction):
    import mujoco
    rows = {}
    for identity in sorted(cell.registry):
        body = mujoco.mj_name2id(cell.model, mujoco.mjtObj.mjOBJ_BODY, identity)
        geom = mujoco.mj_name2id(cell.model, mujoco.mjtObj.mjOBJ_GEOM, 'part_' + identity)
        actual = construction['realized_xml_properties'][identity]
        rows[identity] = {**actual, 'compiled_body_mass_kg': float(cell.model.body_mass[body]),
            'compiled_principal_inertia_kg_m2': cell.model.body_inertia[body].tolist(),
            'compiled_center_of_mass_local_m': cell.model.body_ipos[body].tolist(),
            'compiled_inertial_quaternion': cell.model.body_iquat[body].tolist(),
            'compiled_main_friction': cell.model.geom_friction[geom].tolist(),
            'compiled_main_half_size_m': cell.model.geom_size[geom].tolist(),
            'compiled_main_contact_dimension': int(cell.model.geom_condim[geom]),
            'compiled_main_solref': cell.model.geom_solref[geom].tolist(),
            'compiled_main_solimp': cell.model.geom_solimp[geom].tolist(),
            'expected_mass_includes_tag_and_mark_kg': actual['main_geom_mass_kg'] + .0002}
        if abs(rows[identity]['compiled_body_mass_kg'] - rows[identity]['expected_mass_includes_tag_and_mark_kg']) > 1e-10:
            raise base.CalibrationFailure('Compiled body mass differs from declared box/tag/mark construction: ' + identity)
    return {'objects': rows, 'all_objects_generator_domain_members': all(r['generator_half_open_domain_member'] for r in rows.values()),
            'restart_compile_export_error': getattr(cell, 'restart_physical_export_error', None),
            'boundary_export_failure_is_not_physical_trial_failure': True}


def make_loop(records, trial, construction):
    sys.path.insert(0, str(RUNTIME))
    import cell as cell_module
    original = cell_module.build_scene
    calls = []
    def fixture_builder(n, seed, layout_seed=None):
        if calls or n != trial['population'] or seed != trial['world_seed'] or layout_seed != trial['layout_seed']:
            raise ValueError('Fixture constructor called outside the one declared world')
        calls.append(True)
        xml, registry = original(n, seed, layout_seed)
        (records.root / 'generator-world.xml').write_text(xml, encoding='utf-8')
        fixed, details = construct_xml(xml, registry, trial)
        (records.root / 'fixture-world.xml').write_text(fixed, encoding='utf-8')
        construction.update(details)
        base.save(records.root / 'construction.json', details)
        return fixed, registry
    cell_module.build_scene = fixture_builder
    try:
        loop = QualificationLoop(records, 'held-recovery', trial['world_seed'],
                                 world_specs=[(trial['population'], trial['world_seed'])])
    finally:
        cell_module.build_scene = original
    if len(calls) != 1:
        loop.close(); raise RuntimeError('Fixture did not build exactly one world')
    return loop


def wait_recovery_boundary_ready(loop, timeout_s, report=None):
    """Ordinary steps until fresh lag is at most one tick and sensing is ready.

    The pacing resolution is loop.dt; TimingMonitor thresholds/history are
    unchanged. Persistent overload still reaches the original until/step caps.
    """
    report = {} if report is None else report
    hold_window = getattr(loop, 'hold_window', None)
    entry_hold_ticks = None if hold_window is None else hold_window.data['physics_tick_checks']
    entry_wall = time.perf_counter() - loop.start
    entry_sim = loop.elapsed
    loop.monitor.observe(entry_wall, entry_sim)
    report.update(entry_hold_tick_checks=entry_hold_ticks,
        rule='ordinary_steps_until_fresh_wall_minus_sim_lag_at_most_one_tick_and_public_ready',
        readiness_lag_limit_s=float(loop.dt), timeout_s=timeout_s,
        entry_wall_elapsed_s=entry_wall, entry_sim_elapsed_s=entry_sim,
        entry_lag_s=entry_wall-entry_sim, fixed_entry_target_reference_sim_s=max(entry_sim, entry_wall),
        predicate_observations=0, success=False, error=None,
        scope='Prospective pacing only; unchanged TimingMonitor/caps and every ordinary hold/geometry step. Fixed entry target is descriptive only.')
    def ready():
        public_ready = loop.public_ready()
        wall = time.perf_counter() - loop.start
        sim = loop.elapsed
        lag = wall - sim
        loop.monitor.observe(wall, sim)
        report.update(predicate_observations=report['predicate_observations'] + 1,
                      last_predicate_wall_elapsed_s=wall, last_predicate_sim_elapsed_s=sim,
                      last_predicate_lag_s=lag)
        return lag <= loop.dt and public_ready
    try:
        loop.until(ready, timeout_s)
        report['success'] = True
        return report
    except BaseException as exc:
        report['error'] = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        exit_wall = time.perf_counter() - loop.start
        exit_sim = loop.elapsed
        loop.monitor.observe(exit_wall, exit_sim)
        exit_hold_ticks = None if hold_window is None else hold_window.data['physics_tick_checks']
        report.update(exit_hold_tick_checks=exit_hold_ticks,
            hold_tick_checks_added=None if entry_hold_ticks is None else exit_hold_ticks-entry_hold_ticks,
            exit_wall_elapsed_s=exit_wall, exit_sim_elapsed_s=exit_sim,
            advanced_sim_s=exit_sim-entry_sim, elapsed_wall_s=exit_wall-entry_wall,
            residual_lag_s=exit_wall-exit_sim)


def boundary_operation(loop, details, label, operation, *args, **kwargs):
    """Observe an existing boundary call in place; no new timing pass gate."""
    stage = details.get('stage')
    start_wall = time.perf_counter() - loop.start
    start_sim = float(loop.cells[0].data.time)
    success = False
    try:
        value = operation(*args, **kwargs)
        success = True
        return value
    finally:
        end_wall = time.perf_counter() - loop.start
        end_sim = float(loop.cells[0].data.time)
        details['boundary_operation_timings'].append({
            'stage': stage, 'label': label, 'wall_start_s': start_wall, 'wall_end_s': end_wall,
            'wall_cost_s': end_wall - start_wall, 'sim_start_s': start_sim, 'sim_end_s': end_sim,
            'success': success})


def trial_body(loop, trial, plan, details):
    from restart_state import capture_restart_state, classify_restart
    from geometry_trace import GeometryTrace
    cell = loop.cells[0]
    details['stage'] = 'public_pick_selection'
    loop.until(loop.public_ready, 8.)
    try:
        part_id = select_public(cell.last_detections, trial['family'], float(cell.data.time - cell.detection_time))
    except ValueError as error:
        raise base.CalibrationFailure(str(error)) from error
    details['picked_visible_part_id'] = part_id
    selected = {'part_id': part_id, 'requested_family': trial['family'],
        'source_sequence': loop.latest[0].sequence, 'source_capture_sim_time_s': cell.detection_time,
        'public_detections': cell.last_detections, 'rule': plan['public_selection'],
        'expected_construction_payload_id': trial['expected_payload_id']}
    loop.records.event('public_pick_selection', selected, float(cell.data.time))
    if trial['expected_payload_id'] is not None and part_id != trial['expected_payload_id']:
        raise base.CalibrationFailure('Fresh public selection differs from declared fixture payload; no protected substitution made')
    loop.geometry_trace = GeometryTrace(loop, part_id, plan['geometry_interval_s'])
    boundary_operation(loop, details, 'GeometryTrace.sample:before_transport',
                       loop.geometry_trace.sample, force=True)
    action = transport_action(trial, part_id)
    rid = loop.submit(action)
    exposure = {'configured_cut': 'closed_grip_transfer', 'actual_cut': 'closed_grip_transfer',
        'configured_milestone_exercised': True, 'fallback_used': False, 'active_request_id': rid,
        'part_id': part_id, 'destination': trial['transport_destination'],
        'transport_objective': action['objective'], 'transport_profile': trial['transport_profile'],
        'evidence_role': trial['evidence_role'], 'development_fixture_id': trial['id'],
        'public_opportunity_tcp_threshold_m': .08,
        'cut_observation_cadence': plan['cut']['observation_cadence'],
        'protected_predicates_used_to_delay_cut': False}
    details['stage'] = 'awaiting_actual_carry_cut'
    cut = {}
    def carrying():
        width = float(sum(cell.data.qpos[7:9]))
        tcp_z = float(cell.data.site_xpos[cell.tcp, 2])
        if not public_cut_matches(cell.active_request, cell.segment, rid, width=width, tcp_z=tcp_z):
            return False
        # The first public match is captured even if grip/route predicates fail.
        # No physics advances during snapshot capture and classification.
        snapshot = loop.snapshot()
        protected = boundary_operation(loop, details, 'capture_restart_state:first_public_cut',
            capture_restart_state, cell, zones=loop.zones, zone_half=loop.zone_half,
            exposure=exposure, source_hashes=loop.physical_source_hashes)
        cut.update(snapshot=snapshot, phase=cell.segment['phase'], sim_time_s=float(cell.data.time),
                   public_tcp_z_m=tcp_z, measured_gripper_width_m=width,
                   protected_restart_state=protected)
        return True
    loop.until(carrying, plan['cut']['timeout_s'])
    def capture(kind):
        value = boundary_operation(loop, details, 'capture_restart_state:' + kind,
            capture_restart_state, cell, zones=loop.zones, zone_half=loop.zone_half,
                                      exposure=exposure, source_hashes=loop.physical_source_hashes)
        identity = loop.records.event(kind, value, float(cell.data.time))
        return identity, value
    protected = cut.pop('protected_restart_state')
    event_id = loop.records.event('protected_carry_state_before_cut', protected, float(cell.data.time))
    details.update(verified_cut=True, verified_cut_scope='first public opportunity captured; physical admissibility independently assessed',
                   cut_event_id=event_id, cut_sim_time_s=float(cell.data.time),
                   cut_restart_admissibility=boundary_operation(
                       loop, details, 'classify_restart:cut', classify_restart, protected))
    loop.records.event('verified_carry_authority_cut', {'request_id': rid, 'part_id': part_id, **cut,
        'rich_snapshot_event_id': event_id, 'intervention': 'Normal Cell.cancel; no candidate, weld or object-state intervention'}, float(cell.data.time))
    loop.geometry_trace.phase = 'absence'
    boundary_operation(loop, details, 'GeometryTrace.sample:before_cancel',
                       loop.geometry_trace.sample, force=True)
    window = HoldWindow(part_id, float(cell.data.time), time.perf_counter() - loop.start)
    window.record(loop.snapshot(), float(cell.data.time), time.perf_counter() - loop.start, tick=False)
    loop.hold_window = window
    details['cut_to_recovery_admission'] = window.data
    details['absence'] = window.data
    cell.cancel('five-second recovery development authority interruption')
    loop.incarnation += 1
    start_sim, start_wall = float(cell.data.time), time.perf_counter()
    capture('protected_state_immediately_after_cancel')
    boundary_operation(loop, details, 'GeometryTrace.sample:after_cancel',
                       loop.geometry_trace.sample, force=True)
    details['stage'] = 'authority_absence'
    while float(cell.data.time) - start_sim < plan['absence_s'] - 1e-9:
        loop.step()
    absence = dict(window.data)
    absence.update(requested_s=plan['absence_s'], observed_sim_s=float(cell.data.time) - start_sim,
                   observed_wall_s=time.perf_counter() - start_wall)
    details['absence'] = absence
    event_id, after = capture('protected_held_state_after_absence')
    details.update(after_absence_event_id=event_id, held_at_absence_end=retained_hold_check(after['geometry'], part_id),
        all_absence_tick_hold_checks_pass=absence['ticks_with_hold_predicate_false'] == 0)
    boundary_operation(loop, details, 'GeometryTrace.sample:after_absence',
                       loop.geometry_trace.sample, force=True)
    details['stage'] = 'fresh_sensing_before_recovery'
    details['recovery_boundary_pacing'] = {}
    wait_recovery_boundary_ready(loop, 8., details['recovery_boundary_pacing'])
    capture('protected_state_before_recovery_dispatch')
    boundary_operation(loop, details, 'GeometryTrace.sample:before_recovery_dispatch',
                       loop.geometry_trace.sample, force=True)
    details['stage'] = 'recover_held'
    recovery = loop.submit({'operation': 'recover_held', 'destination': trial['destination']})
    admission_event_id = loop.records.sequence
    window.record(loop.snapshot(), float(cell.data.time), time.perf_counter() - loop.start, tick=False)
    window.data.update(accepted_recovery_request_id=recovery, accepted_admission_event_id=admission_event_id,
                       endpoint='successful normal recover_held action_admission, before next physics tick')
    loop.hold_window = None
    details['all_cut_to_admission_hold_checks_pass'] = window.data['all_recorded_hold_checks_pass']
    details['after_recovery_admission_event_id'] = capture('protected_state_after_recovery_admission')[0]
    loop.geometry_trace.phase = 'recovery'
    boundary_operation(loop, details, 'GeometryTrace.sample:after_recovery_admission',
                       loop.geometry_trace.sample, force=True)
    details['recovery_request_id'] = recovery
    loop.terminal(recovery, timeout=60.)
    loop.geometry_trace.phase = 'settling'
    details['stage'] = 'independent_settled_placement'
    stable, last_check = base.StablePredicate(), {}
    def placed():
        result = base.placement_check(loop.snapshot(), part_id, trial['destination'], float(sum(cell.data.qpos[7:9])))
        last_check.clear(); last_check.update(result)
        return stable.update(float(cell.data.time), result['passed_now'])
    loop.until(placed, 15.)
    details['independent_final_check'] = last_check
    details['placement_stable_since_sim_s'] = stable.since
    loop.records.event('independent_raw_placement_check', {'check': last_check, 'dwell_s': .5,
        'stable_since_sim_s': stable.since, 'checked_every_physics_tick': True}, float(cell.data.time))
    details['final_rich_state_event_id'] = capture('protected_state_after_settled_placement')[0]
    boundary_operation(loop, details, 'GeometryTrace.sample:after_settled_placement',
                       loop.geometry_trace.sample, force=True)
    details['physical_predicates_passed'] = details['all_cut_to_admission_hold_checks_pass'] and physical_trial_pass(
        held_at_absence_end=details['held_at_absence_end'],
        all_absence_tick_hold_checks_pass=details['all_absence_tick_hold_checks_pass'],
        placement_passed=last_check['passed_now'])
    details['stage'] = 'complete'


def child(trial_id, output, seed, parent_manifest, parent_sha):
    # Join only this parent's named process job before authority CIM or physics
    # imports. The immutable manifest hash identifies the parent-owned name.
    raw = Path(parent_manifest).read_bytes()
    if hashlib.sha256(raw).hexdigest() != parent_sha:
        raise RuntimeError('Parent manifest hash mismatch before containment join')
    manifest = json.loads(raw)
    from process_caps import join_job
    join_job(manifest['probe_job_names'][trial_id])
    authority = child_authority(__file__, trial_id, output, seed, parent_manifest, parent_sha)
    plan = validate_plan(manifest['prospective_plan'])
    trials, deferred, execution = manifest_execution(plan, manifest)
    trial = next(t for t in trials if t['id'] == trial_id)
    before = hashes()
    if before != manifest['source_hashes']:
        raise RuntimeError('Source identity changed before child construction')
    records = base.Records(output)
    loop = None
    details = {'stage': 'construction', 'physical_predicates_passed': False, 'verified_cut': False,
               'qualification_granted': False, 'trial': trial, 'boundary_operation_timings': []}
    construction = {}
    status, error, timing, geometry_report = 'failed', None, None, None
    base.save(records.root / 'probe-manifest.json', {'schema_version': SCHEMA, 'trial': trial, 'queue': authority,
        **execution, 'phase_deferred_trial_ids': deferred,
        'parent_manifest_sha256': parent_sha, 'created_at': utc(), 'source_hashes': before,
        'simulation_cap_s': plan['simulation_cap_s'], 'hard_process_cap_s': plan['child_hard_cap_s'],
        'absence_s': plan['absence_s'], 'prospective_plan_sha256': hashlib.sha256(canonical(plan)).hexdigest()})
    try:
        loop = make_loop(records, trial, construction)
        loop.cap = plan['simulation_cap_s']
        loop.physical_source_hashes = physical_snapshot_sources(before, RUNTIME)
        properties = compiled_properties(loop.cells[0], construction)
        base.save(records.root / 'compiled-properties.json', properties)
        from restart_physical_class import class_spec_from_seal
        seal = getattr(loop.cells[0], 'restart_physical_seal', None)
        if seal is not None:
            base.save(records.root / 'protected-class-spec.json', class_spec_from_seal(seal))
            details['protected_class_spec_status'] = 'recorded'
        else:
            details['protected_class_spec_status'] = 'unavailable: ' + str(properties['restart_compile_export_error'])
        details['all_objects_generator_domain_members'] = properties['all_objects_generator_domain_members']
        details['restart_compile_export_error'] = properties['restart_compile_export_error']
        trial_body(loop, trial, plan, details)
        status = 'passed' if details['physical_predicates_passed'] else 'failed'
    except BaseException as exc:
        status = 'failed' if isinstance(exc, base.CalibrationFailure) else 'infrastructure_failure'
        error = type(exc).__name__ + ': ' + str(exc)
        records.event('probe_failure', {'error': error, 'stage': details['stage'], 'traceback': traceback.format_exc()},
                      None if loop is None else float(loop.cells[0].data.time))
    finally:
        if loop is not None:
            loop.hold_window = None
            timing = loop.monitor.report()
            if loop.geometry_trace is not None:
                try:
                    loop.geometry_trace.close()
                    geometry_report = loop.geometry_trace.report()
                except Exception as exc:
                    error = (error + '; ' if error else '') + 'geometry cleanup: ' + str(exc)
                    status = 'infrastructure_failure'
            try:
                loop.close()
            except Exception as exc:
                error = (error + '; ' if error else '') + 'cleanup: ' + str(exc); status = 'infrastructure_failure'
        after = hashes()
        if after != before:
            status = 'infrastructure_failure'; error = (error + '; ' if error else '') + 'source changed'
        result = {'schema_version': SCHEMA, 'trial_id': trial_id, 'trial': trial, 'status': status,
            **execution, 'phase_deferred_trial_ids': deferred,
            'error': error, 'details': details, 'timing': timing, 'geometry_sampling': geometry_report,
            'source_hashes_before': before, 'source_hashes_after': after, 'sources_unchanged': before == after,
            'finished_at': utc(), 'qualification_granted': False, 'continuous_swept_envelope': None,
            'candidate_or_task_performance_claimed': False}
        records.event('probe_terminal', result)
        records.close()
        base.save(Path(output) / 'result.json', result)
    return 0


def parent(args):
    authority = parent_authority(__file__)
    plan_path = Path(args.plan).resolve()
    plan = validate_plan(json.loads(plan_path.read_text(encoding='utf-8')))
    trials, deferred, selection_metadata = execution_selection(plan, args.destination, args.phase, args.diagnostic_trial)
    execution_path = HERE / 'execution-plan-001.json'
    execution = json.loads(execution_path.read_text(encoding='utf-8'))
    if execution['schema_version'] != EXECUTION_REVISION or execution['original_plan_sha256'] != base.sha(plan_path):
        raise ValueError('Execution declaration does not identify the exact new profile trial plan')
    provisional, provisional_ref = None, None
    if args.phase == 'validation':
        if not args.provisional_rule or args.destination == 'all':
            raise ValueError('Validation requires one destination and its previously fixed --provisional-rule')
        rule_path = Path(args.provisional_rule).resolve()
        provisional = json.loads(rule_path.read_text(encoding='utf-8'))
        provisional_identity(provisional, args.destination)
        profile_rule_identity(provisional)
        provisional_ref = {'path': str(rule_path), 'sha256': base.sha(rule_path)}
    elif args.provisional_rule:
        raise ValueError('Construction does not consume a later provisional rule')
    root = Path(args.output).resolve(); root.mkdir(parents=True, exist_ok=False)
    if provisional is not None:
        (root / 'provisional-rule.json').write_bytes(rule_path.read_bytes())
        if base.sha(root / 'provisional-rule.json') != provisional_ref['sha256']:
            raise ValueError('Provisional rule changed while copying')
    before = hashes()
    with zipfile.ZipFile(root / 'source-bundle.zip', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sources():
            archive.write(path, path.relative_to(PROJECT).as_posix())
    manifest = {'schema_version': SCHEMA, 'created_at': utc(), 'queue': authority,
        'modes': [t['id'] for t in trials], 'seed': 0, 'authority_seed_meaning': 'fixed dispatch token; actual world seeds are in each immutable trial',
        'source_hashes': before, 'source_bundle_sha256': base.sha(root / 'source-bundle.zip'),
        'prospective_plan': plan, 'prospective_plan_file_sha256': base.sha(plan_path),
        'execution_revision': execution, 'execution_revision_file_sha256': base.sha(execution_path),
        'profile_revision': PROFILE_REVISION,
        **selection_metadata,
        'execution_phase': args.phase, 'provisional_rule': provisional, 'provisional_rule_ref': provisional_ref,
        'phase_deferred_trial_ids': deferred,
        'destination_selection': args.destination, 'sum_child_hard_caps_s': len(trials) * plan['child_hard_cap_s'],
        'parent_archival_and_indexing_time_excluded_from_child_caps': True,
        'probe_job_names': {t['id']: 'Local\\CodexRoboticsRecovery_' + uuid.uuid4().hex for t in trials},
        'environment': {'python': platform.python_version(), 'platform': platform.platform(),
            'mujoco': importlib.metadata.version('mujoco'), 'numpy': importlib.metadata.version('numpy')},
        'qualification_granted': False, 'evaluation_seeds_created': False}
    path = root / 'manifest.json'
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(manifest, stream, sort_keys=True, indent=2, allow_nan=False); stream.write('\n')
        stream.flush(); os.fsync(stream.fileno())
    manifest_sha = base.sha(path)
    from process_caps import JobCap
    results = []
    stop_reason = None
    for trial in trials:
        if hashes() != before:
            stop_reason = 'source changed before next declared trial'; break
        identity = trial['id']; output = root / identity
        command = child_command(sys.executable, Path(__file__).resolve(), identity, output, 0, path, manifest_sha)
        cap = JobCap(manifest['probe_job_names'][identity])
        timed_out = False
        process = None
        code = None
        launch_error = None
        try:
            with (root / (identity + '-stdout.log')).open('wb') as stdout, (root / (identity + '-stderr.log')).open('wb') as stderr:
                process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                try:
                    code = process.wait(timeout=plan['child_hard_cap_s'])
                except subprocess.TimeoutExpired:
                    timed_out = True; cap.terminate()
                    if process.poll() is None:
                        process.kill()
                    code = process.wait(timeout=10.)
        except Exception as exc:
            launch_error = type(exc).__name__ + ': ' + str(exc)
            if process is not None and process.poll() is None:
                cap.terminate(); process.kill(); process.wait(timeout=10.)
        finally:
            cap.close()  # Also terminates any owned probe descendants left after a failed cleanup.
        result_path = output / 'result.json'
        if code == 0 and not timed_out and result_path.exists():
            outcome = json.loads(result_path.read_text(encoding='utf-8'))
            result = {'trial_id': identity, 'status': outcome['status'], 'error': outcome['error'], **selection_metadata,
                'result_path': result_path.relative_to(root).as_posix(), 'result_sha256': base.sha(result_path),
                'actual_host_timing_pass': (outcome.get('timing') or {}).get('actual_host_timing_pass'),
                'verified_cut': outcome['details']['verified_cut'],
                'generator_domain_member': outcome['details'].get('all_objects_generator_domain_members')}
        else:
            result = {'trial_id': identity, 'status': 'infrastructure_failure', 'exit_status': code, **selection_metadata,
                'hard_timeout': timed_out, 'error': launch_error or 'No complete terminal child result; partial evidence retained',
                'partial_evidence_path': output.relative_to(root).as_posix()}
        results.append(result)
        base.save(root / 'progress.json', {'finished': results, 'remaining': [t['id'] for t in trials[len(results):]]})
        print(json.dumps(result), flush=True)
    unchanged = hashes() == before
    all_executed_physical = unchanged and len(results) == len(trials) and all(r['status'] == 'passed' for r in results)
    all_executed_timing = len(results) == len(trials) and all(r.get('actual_host_timing_pass') is True for r in results)
    summary = {'schema_version': SCHEMA, 'queue_job_id': authority['job_id'], 'finished_at': utc(),
        **selection_metadata,
        'execution_phase': args.phase, 'phase_deferred_trial_ids': manifest['phase_deferred_trial_ids'],
        'attempts': results, 'not_started': [t['id'] for t in trials[len(results):]], 'stop_reason': stop_reason,
        'sources_unchanged': unchanged,
        'all_declared_physical_checks_passed': selection_metadata['is_full_phase_screen'] and all_executed_physical,
        'all_host_timing_checks_passed': selection_metadata['is_full_phase_screen'] and all_executed_timing,
        'all_executed_physical_checks_passed': all_executed_physical,
        'all_executed_host_timing_checks_passed': all_executed_timing,
        'qualification_granted': False, 'cell_envelopes_created': False, 'scored_ready_claimed': False,
        'absence_scope': 'Five-second trial plus measured full before-cancel to accepted recovery admission interval, including sensing; later process-restart measurements determine adequacy.'}
    base.save(root / 'summary.json', summary)
    inventory = [{'path': p.relative_to(root).as_posix(), 'bytes': p.stat().st_size, 'sha256': base.sha(p)}
                 for p in sorted(root.rglob('*')) if p.is_file()]
    base.save(root / 'evidence-index.json', {'schema_version': SCHEMA, 'files': inventory})
    print(json.dumps(summary, indent=2)); return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', default=str(HERE / 'plan-001.json'))
    parser.add_argument('--destination', choices=('parking1',), default='parking1')
    parser.add_argument('--phase', choices=('construction', 'validation'))
    parser.add_argument('--diagnostic-trial', help='Run exactly one original construction trial as nonqualification diagnostic evidence')
    parser.add_argument('--provisional-rule')
    parser.add_argument('--output', required=True)
    parser.add_argument('--_child', help=argparse.SUPPRESS)
    parser.add_argument('--seed', type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument('--parent-manifest', help=argparse.SUPPRESS)
    parser.add_argument('--parent-manifest-sha256', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args._child:
        if args.diagnostic_trial is not None:
            parser.error('Child diagnostic selection must come only from its immutable parent manifest')
        if args.seed != 0 or not args.parent_manifest or not args.parent_manifest_sha256:
            parser.error('Child requires the exact parent manifest and authority dispatch token')
        return child(args._child, args.output, args.seed, args.parent_manifest, args.parent_manifest_sha256)
    if not args.phase:
        parser.error('Declare --phase construction or validation; phases cannot run together')
    return parent(args)


if __name__ == '__main__':
    raise SystemExit(main())
