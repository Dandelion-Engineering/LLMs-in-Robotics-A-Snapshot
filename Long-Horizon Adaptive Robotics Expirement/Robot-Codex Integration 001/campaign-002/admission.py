"""Independent sealed Campaign 002 admission; read-only, with no model calls.

External certificate hashes are caller-held trust anchors. Qualification snapshots
can have distinct metadata/external drivers, but their actual runtime source
identities must match the final frozen runtime. All scored results remain subject
to current per-attempt timing, transport, lifecycle and external storage checks.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import importlib.metadata
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'assessment'))
import assess as base

REPO = base.REPO
INTEGRATION = HERE.parent
MAP = INTEGRATION.parent / 'Architecture Map'
CAMPAIGN_ID = 'RCI001-Campaign002'
RELEASE_REVISION = 'RCI001-C02-frozen-001'
BASELINE_SNAPSHOT = MAP / 'releases/RCI001-wsl-010d/snapshot.json'
BASELINE_SHA256 = 'd84c510ee923a395417944e70a90ab1fa3759bc0061c2b6a4a714fb708f25581'
ASSET_BASELINE = INTEGRATION / 'campaign-001/admission/asset-refresh-session12.json'
ASSET_BASELINE_SHA256 = '5b6963a30e5a3a9fd5eb905fa2f8df8c686f1ec733066147461e118db63450c5'
PLANNING_BYTES = 33_093_545_600
REQUIRED_HARNESS_MODULES = {'physical.py', 'runtime.py', 'run_host.py', 'timing.py',
                            'instrumented_journal.py', 'executor_capture.py', 'gc_diagnostics.py', 'memory_guard.py'}
REQUIRED_ARTIFACTS = ('protocol', 'schedule', 'source_snapshot', 'source_archive', 'approval',
                      'base_assessor', 'smoke_assessor', 'admission_verifier', 'operator', 'registry',
                      'settlement', 'storage_policy', 'storage_monitor', 'storage_baseline', 'qualification_index',
                      'asset_refresh', 'asset_verifier')
NATIVE_CHECKS = {'execution_exit_zero', 'execution_inside_queue', 'manifest_exact', 'reference_only',
                 'host_clean', 'independent_success', 'baseline_help_and_handback', 'reserve_preserved',
                 'frozen_runtime_loaded', 'frozen_recorder_loaded', 'strict_fresh_timing'}
BOUNDARY_CHECKS = {'unit_suites_passed', 'linux_boundary_tests_passed', 'runtime_canaries_passed',
                   'protected_control_continuity_and_handback_passed', 'codehost_transport_probe_passed',
                   'all_five_namespaces_retired', 'detached_descendants_retired', 'transport_abort_unset',
                   'runtime_cleanup_clean', 'durable_retention_verified', 'sources_unchanged',
                   'trusted_executor_capture_roundtrip'}
BOUNDARY_UNIT_SUITES = {'protected-host', 'robot-client', 'transport', 'timing', 'executor-capture-reader',
                        'gc-policy', 'host-memory', 'qualification-protocol', 'boundary-policy-windows',
                        'journal-instrumentation', 'recorder-instrumentation'}
SMOKE_CHECKS = {'official_queue_succeeded_exit0', 'frozen_manifest_matches_two_turn_smoke',
                'new_frozen_source_and_archive_integrity', 'explicit_host_manifest_and_run_match',
                'exact_smoke_direct_command_matches', 'sequence_and_host_completed', 'two_fresh_model_threads',
                'first_model_interrupted_after_action', 'second_model_completed_and_native_exit0',
                'one_safe_gripper_action_admitted', 'invalid_command_host_rejected_without_dispatch',
                'no_action_replay_or_extra_motion', 'old_owner_retired_before_new_owner_started',
                'all_first_namespaces_retired_before_successor_path',
                'continuity_commits_protected_and_locally_visible', 'fresh_invocation_receives_committed_prior_note',
                'protected_handback_rejects_unresolved_stock_once', 'no_fabricated_recovery_or_owner_transfer',
                'both_models_read_fixed_startup_and_initial_continuity_bytes',
                'model_requested_live_source_reads_match_protected_episode_invocation_observations',
                'bounded_host_memory_and_collector_integrity',
                'complete_retained_timing_replayed_and_passed', 'transport_revocation_and_reply_provenance',
                'complete_codehost_lifecycle_and_safe_metadata',
                'interrupt:all_namespace_retirements_observed', 'resume:all_namespace_retirements_observed',
                'interrupt:old_invocation_token_denied', 'resume:old_invocation_token_denied'}
PILOT_CHECKS = {'official_queue_succeeded_exit0', 'frozen_source_and_archive_integrity',
                'campaign_manifest_exact_predeclared_bytes', 'campaign_manifest_exact_predeclared_revision',
                'one_uninterrupted_orchestrated_invocation', 'protected_host_completed_cleanly',
                'model_disposition_recognized', 'qualified_lifecycle_end_observed', 'all_45_outer_boundary_canaries',
                'codehost_ambient_capabilities_denied', 'all_namespace_retirements_observed',
                'protected_continuity_receipts_match', 'independent_evaluator_well_formed_consistent',
                'queue_attempt_times_match', 'queue_exact_direct_attempt_command_matches',
                'complete_retained_timing_replayed_and_passed', 'transport_revocation_and_reply_provenance',
                'complete_codehost_lifecycle_and_safe_metadata'}
PILOT_CHECKS.add('bounded_host_memory_and_collector_integrity')

require = base.require
finite = base.finite


def stamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None, 'Timestamp must have a timezone')
    return parsed.timestamp()


def same_path(left, right):
    return Path(left).resolve() == Path(right).resolve()


def artifact(record):
    path = Path(record['path'])
    require(path.is_absolute() and path.is_file() and not path.is_symlink(),
            'Artifact must be an existing absolute ordinary file: ' + str(path))
    require(base.hash_file(path) == record['sha256'], 'Artifact SHA256 mismatch: ' + str(path))
    return path


def all_checks(checks, required, label):
    require(isinstance(checks, dict) and bool(checks) and required <= set(checks)
            and all(value is True for value in checks.values()), label + ' required checks absent or failed')


def exact_binding(binding, expected, label):
    artifact(binding)
    require(same_path(binding['path'], expected['path']) and binding['sha256'] == expected['sha256'],
            label + ' artifact binding differs')


def listed_hash(mapping, record, label):
    matches = [value for key, value in mapping.items() if same_path(key, record['path'])]
    require(matches == [record['sha256']], label + ' retained input hash differs or is absent')


def harness_sources(sources):
    """Select every production Python module, including future nested helpers."""
    prefix = (HERE / 'harness').relative_to(REPO).as_posix() + '/'
    return {name for name in sources if name.startswith(prefix)
            and Path(name).suffix == '.py' and not Path(name).name.startswith('test')}


def runtime_identities(frozen):
    """Original 624 dependencies plus the exact complete production harness."""
    require(base.hash_file(BASELINE_SNAPSHOT) == BASELINE_SHA256, 'Original runtime identity baseline changed')
    baseline = base.read_json(BASELINE_SNAPSHOT)
    require(len(baseline['sources']) == 624, 'Original runtime identity baseline incomplete')
    original = baseline['sources']
    require(all(frozen.get('sources', {}).get(name) == value for name, value in original.items()),
            'Final snapshot changes or omits an original protected runtime source')
    harness = harness_sources(frozen.get('sources', {}))
    required = {(HERE / 'harness' / name).relative_to(REPO).as_posix() for name in REQUIRED_HARNESS_MODULES}
    require(required <= harness, 'Final snapshot omits a required executable runtime source')
    current = harness_sources(path.relative_to(REPO).as_posix() for path in (HERE / 'harness').rglob('*.py')
                              if path.is_file())
    require(harness == current, 'Final snapshot production harness module set differs from current runtime')
    names = set(original) | harness
    return {name: frozen['sources'][name] for name in sorted(names)}


def verify_runtime_lineage(core, qualification):
    require(bool(core) and all(qualification.get('sources', {}).get(name) == value for name, value in core.items()),
            'Qualification runtime sources differ from final frozen runtime')
    require(harness_sources(core) == harness_sources(qualification.get('sources', {})),
            'Qualification production harness module set differs from final frozen runtime')


def verify_assessor_helpers(frozen):
    for name in ('retained_reads.py', 'resource_integrity.py'):
        path = HERE / 'assessment' / name
        expected = {'sha256': base.hash_file(path), 'bytes': path.stat().st_size}
        require(frozen.get('sources', {}).get(path.relative_to(REPO).as_posix()) == expected,
                'Snapshot omits or changes retained-read or resource assessment helper: ' + name)


def verify_qualifier_snapshot(entry, core, seal_time):
    path = artifact(entry['snapshot'])
    frozen = base.read_json(path)
    require(not base.source_integrity(frozen, path.with_name('code.zip')), 'Qualification source archive differs')
    verify_runtime_lineage(core, frozen)
    require(stamp(frozen['created_at']) <= seal_time, 'Qualification source freeze postdates certificate')
    return frozen


def strict_timing_summary(value, label):
    require(isinstance(value, dict) and value.get('schema') == 'rci-campaign-independent-timing-2'
            and value.get('passed') is True and value.get('scheduling_pass') is True,
            label + ' strict timing or scheduling qualification absent/failed')
    require(all(value.get(key) is True for key in ('resource_integrity_pass', 'garbage_collection_pass', 'host_memory_pass'))
            and value.get('garbage_collection', {}).get('passed') is True
            and value.get('host_memory', {}).get('passed') is True,
            label + ' bounded host memory or collector integrity absent/failed')
    report = value.get('replayed_timing', {})
    windows = report.get('complete_wall_windows')
    outside = report.get('outside_rtf_tolerance_windows')
    require(type(windows) is int and windows > 0 and type(outside) is int and 0 <= outside <= windows
            and finite(report.get('maximum_lag_s')) and 0 <= report['maximum_lag_s'] < .1
            and report.get('outside_rtf_tolerance_fraction') == outside / windows
            and outside / windows < .01 and report.get('actual_host_timing_pass') is True
            and type(value.get('sample_count')) is int and value['sample_count'] >= 2,
            label + ' strict timing thresholds are not met')
    rows = report.get('timing')
    require(isinstance(rows, list) and len(rows) == windows
            and all(finite(row.get('real_time_factor')) and row.get('within_tolerance') is
                    (.95 <= row['real_time_factor'] <= 1.05) for row in rows)
            and sum(row['within_tolerance'] is False for row in rows) == outside,
            label + ' one-second timing window summary differs')
    strict_clock_provenance(value.get('loop_origin', {}), label)


def strict_clock_provenance(origin, label):
    clock = origin.get('clock', {})
    context = origin.get('clock_context', {})
    frequency = context.get('qpc_frequency_hz')
    auxiliary = context.get('auxiliary_clock', {})
    bracket = context.get('cross_clock_sample', {})
    require(origin.get('clock_name') == context.get('primary_clock_name') == 'perf_counter'
            and context.get('primary_clock') == clock
            and clock.get('implementation') == 'QueryPerformanceCounter()'
            and clock.get('monotonic') is True and clock.get('adjustable') is False
            and type(frequency) is int and frequency > 0
            and finite(clock.get('resolution')) and clock['resolution'] == 1 / frequency
            and finite(origin.get('monotonic_s')) and finite(origin.get('initial_sim_s')),
            label + ' prospective QPC clock provenance absent or inconsistent')
    require(context.get('auxiliary_clock_name') == 'monotonic'
            and auxiliary.get('monotonic') is True and auxiliary.get('adjustable') is False
            and isinstance(auxiliary.get('implementation'), str) and bool(auxiliary['implementation'])
            and finite(auxiliary.get('resolution')) and auxiliary['resolution'] > 0
            and all(finite(bracket.get(key)) for key in
                    ('perf_counter_before_s', 'perf_counter_after_s', 'monotonic_s', 'unix_s'))
            and bracket['perf_counter_before_s'] <= bracket['perf_counter_after_s'] <= origin['monotonic_s']
            and bracket['unix_s'] > 0,
            label + ' cross-clock chronology bracket absent or inconsistent')


def direct_qualification_command(job, script, arguments):
    interpreter = REPO / 'venv/Scripts/python.exe'
    argv = job.get('argv', [])
    expected = [str(interpreter), '-X', 'utf8', '-B', str(script), *arguments]
    require(len(argv) == len(expected) and same_path(job.get('cwd', ''), REPO)
            and same_path(job.get('resolved_executable', ''), interpreter), 'Wrong qualification direct command')
    for index, (actual, wanted) in enumerate(zip(argv, expected)):
        is_path = index in (0, 4) or index > 4 and expected[index - 1] in ('--manifest', '--output', '--evidence')
        require(same_path(Path(job['cwd']) / actual, wanted) if is_path else actual == wanted,
                'Wrong qualification direct command argument')


def qualifier_entry(entry, kind, core, seal_time):
    """Authenticate queue completion before opening any retained assessment."""
    queue_path = artifact(entry['queue'])
    job = base.queue_gate(base.read_json(queue_path))
    require(stamp(job['started_at']) < stamp(job['ended_at']) <= seal_time,
            'Qualification must complete before certificate seal')
    frozen = verify_qualifier_snapshot(entry, core, seal_time)
    require(stamp(frozen['created_at']) <= stamp(job['started_at']), 'Qualification source frozen after execution began')
    manifest_path = artifact(entry['manifest'])
    manifest = base.read_json(manifest_path)
    require(manifest.get('framework_revision') == frozen.get('revision'), 'Qualification manifest/revision mismatch')
    evidence = Path(entry['evidence'])
    require(evidence.is_absolute(), 'Absolute qualification evidence path required')
    if kind in ('native', 'boundary'):
        require(frozen.get('run_id') == manifest.get('run_id')
                and frozen.get('manifest_sha256') == entry['manifest']['sha256'], 'Qualification frozen manifest mismatch')
        arguments = ['--manifest', str(manifest_path), '--output', str(evidence)] if kind == 'native' else ['--output', str(evidence)]
        from transport_dispatch import V3_METHOD
        suite = ('boundary_suite_v3.py' if kind == 'boundary' and V3_METHOD in frozen.get('sources', {})
                 else kind + '_suite.py')
        direct_qualification_command(job, HERE / 'qualification' / suite, arguments)
    else:
        require(base.queue_paths_match(job, manifest_path, evidence, Path(entry['host_evidence']),
                                       Path(manifest['runtime_workspace']), mode='smoke' if kind == 'smoke' else 'pilot'),
                'Qualification model direct command/paths differ')
    value = base.read_json(artifact(entry['assessment']))
    if kind != 'boundary':
        require(value.get('run_id') == manifest.get('run_id') and value.get('queue_job_id') == job.get('id')
                and value.get('framework_revision') == frozen.get('revision'), 'Qualification assessment identity differs')
    return value, manifest, frozen, job


def verify_native(entry, core, seal_time, artifacts):
    value, manifest, frozen, job = qualifier_entry(entry, 'native', core, seal_time)
    require(value.get('schema') == 'campaign002-native-assessment-1' and value.get('qualification_passed') is True,
            'Native qualification assessment failed')
    require(manifest.get('model_turns_max') == 0 and len(manifest.get('slots', [])) == 6
            and len(value.get('rows', [])) == 6, 'Exactly six no-model native reference episodes required')
    require(value.get('source_snapshot_sha256') == entry['snapshot']['sha256'], 'Native source snapshot binding differs')
    for key in ('manifest', 'queue', 'snapshot'):
        exact_binding(value['bindings'][key], entry[key], 'Native ' + key)
    artifact(entry['assessor'])
    require(same_path(entry['assessor']['path'], HERE / 'qualification/assess_native.py')
            and value['bindings'].get('assessor_sha256') == entry['assessor']['sha256']
            and value['bindings'].get('base_assessor_sha256') == artifacts['base_assessor']['sha256'],
            'Native assessor implementation binding differs')
    families = Counter()
    ids = set()
    for index, (slot, row) in enumerate(zip(manifest['slots'], value['rows']), 1):
        candidate = slot['manifest']
        require(row.get('run_id') == slot.get('run_id') == candidate.get('run_id')
                and row['run_id'] not in ids and row.get('family') == candidate.get('family')
                and candidate.get('mode') == 'reference' and candidate.get('seed') == 173
                and candidate.get('noise_seed') == 24000 + index and row.get('passed') is True
                and row.get('terminal') == 'task_success' and not row.get('errors'), 'Native fixed reference slot failed')
        ids.add(row['run_id']); families[row['family']] += 1
        all_checks(row.get('checks'), NATIVE_CHECKS, 'Native')
        require(row.get('independent_outcome', {}).get('independent_task_outcome') == 'success',
                'Native protected independent outcome is not success')
        strict_timing_summary(row.get('timing'), 'Native')
    require(families == {'misplaced-stock': 3, 'blocked-insert-home': 3}, 'Native family coverage incomplete')


def verify_boundary_suites(suites):
    require({row.get('name') for row in suites} == BOUNDARY_UNIT_SUITES
            and len(suites) == len(BOUNDARY_UNIT_SUITES)
            and all(type(row.get('exit_code')) is int and row['exit_code'] == 0 for row in suites),
            'Boundary original and repaired unit suites incomplete')


def verify_boundary(entry, core, seal_time):
    value, manifest, frozen, job = qualifier_entry(entry, 'boundary', core, seal_time)
    require(value.get('schema') == 'campaign002-boundary-suite-1' and value.get('qualified') is True
            and type(value.get('model_calls')) is int and value['model_calls'] == 0
            and value.get('physical_simulation') is False and not value.get('error'), 'Boundary qualification failed')
    all_checks(value.get('checks'), BOUNDARY_CHECKS, 'Boundary')
    require(stamp(job['started_at']) <= value['started_wall_unix_s'] <= value['finished_wall_unix_s'] <= stamp(job['ended_at']),
            'Boundary evidence timestamps outside queue window')
    require(same_path(entry['assessment']['path'], Path(entry['evidence']) / 'suite-result.json'),
            'Boundary assessment must be direct suite result')
    before = base.read_json(Path(entry['evidence']) / 'source-binding-before.json')
    after = base.read_json(Path(entry['evidence']) / 'source-binding-after.json')
    require(bool(before) and before == after and all(frozen.get('sources', {}).get(name, {}).get('sha256') == digest
                                                    for name, digest in before.items()), 'Boundary source receipt differs from snapshot')
    require(bool(harness_sources(core)) and harness_sources(core) == harness_sources(before),
            'Boundary receipt omits or changes complete production harness module set')
    verify_boundary_suites(value.get('unit_suites', []))
    require(len(value.get('canary_processes', [])) == 2
            and all(type(row.get('exit_code')) is int and row['exit_code'] == 0 for row in value['canary_processes']),
            'Boundary actual canary processes incomplete')
    require(len(value.get('retirement_receipts', {})) == 5
            and all(item is True for item in value['retirement_receipts'].values()), 'Boundary namespace receipts incomplete')
    from transport_dispatch import V3_METHOD
    if V3_METHOD in frozen.get('sources', {}):
        from transport_integrity_v3 import verify_transport_integrity
        proof = verify_transport_integrity(Path(entry['evidence']) / 'runtime', frozen, owner_kind='transport_probe')
        require(proof.get('passed') is True and proof == value.get('codehost_transport_proof'),
                'Boundary authenticated channel transport proof failed or differs')
    required = {'control': {'wrong_token_denied', 'operator_route_denied', 'continuity_committed_and_mirrored',
                            'oversize_note_denied_and_prior_preserved', 'stale_command_rejected',
                            'valid_command_accepted', 'duplicate_receipt_stable'},
                'handback': {'handback_accepted', 'late_continuity_denied', 'late_read_denied', 'continuity_unchanged'}}
    for phase, checks in required.items():
        all_checks(value.get('control', {}).get(phase, {}).get('checks'), checks, 'Boundary ' + phase)


def verify_model_qualifier(entry, kind, core, seal_time, artifacts):
    value, manifest, frozen, job = qualifier_entry(entry, kind, core, seal_time)
    for name in ('base_assessor', 'smoke_assessor'):
        source_name = Path(artifacts[name]['path']).relative_to(REPO).as_posix()
        require(frozen.get('sources', {}).get(source_name, {}).get('sha256') == artifacts[name]['sha256'],
                'Model qualification snapshot omits or changes its frozen assessment code')
    verify_assessor_helpers(frozen)
    require(manifest.get('model') == 'gpt-6-astra' and manifest.get('effort') == 'max'
            and manifest.get('bootstrap') == 'Follow the instructions in RobotAgentPrompt.md.',
            'Qualification model/bootstrap differs')
    strict_timing_summary(value.get('campaign_timing'), kind)
    if kind == 'smoke':
        require(value.get('schema') == 'robot-codex-physical-smoke-assessment-2' and value.get('smoke_passed') is True
                and manifest.get('model_turns_max') == 2 and manifest.get('noise_seed') == 24101,
                'Actual-model interruption/resume smoke qualification missing/failed')
        all_checks(value.get('checks'), SMOKE_CHECKS, 'Smoke')
        require(value.get('manifest_sha256') == entry['manifest']['sha256']
                and value.get('frozen_snapshot_sha256') == entry['snapshot']['sha256']
                and value.get('frozen_archive_sha256') == base.hash_file(Path(entry['snapshot']['path']).with_name('code.zip'))
                and value.get('assessment_code_sha256') == artifacts['smoke_assessor']['sha256']
                and value.get('base_assessment_sha256') == artifacts['base_assessor']['sha256'], 'Smoke code/input binding differs')
        for key in ('queue', 'manifest', 'snapshot'):
            listed_hash(value['evidence_sha256'], entry[key], 'Smoke ' + key)
    else:
        require(value.get('schema') == 'robot-codex-campaign-assessment-2' and value.get('validity') == 'valid'
                and value.get('failed_checks') == [] and value.get('task_evidence_valid') is True
                and value.get('task_outcome') in ('success', 'failure') and value.get('scorable') is False
                and value.get('family') == manifest.get('family') == entry.get('family')
                and manifest.get('model_turns_max') == 1 and manifest.get('interruption_trigger') is None
                and manifest.get('noise_seed') == {'misplaced-stock': 24102, 'blocked-insert-home': 24103}[entry['family']],
                'One-invocation family pilot qualification missing/failed')
        all_checks(value.get('checks'), PILOT_CHECKS, 'Pilot')
        require(value['bindings'].get('manifest_sha256') == entry['manifest']['sha256']
                and value['bindings'].get('framework_snapshot_sha256') == entry['snapshot']['sha256']
                and value['bindings'].get('framework_archive_sha256') == base.hash_file(Path(entry['snapshot']['path']).with_name('code.zip'))
                and value['bindings'].get('queue_receipt_sha256') == entry['queue']['sha256']
                and value['bindings'].get('assessment_sha256') == artifacts['base_assessor']['sha256'], 'Pilot code/input binding differs')


def verify_qualification_index(index, frozen, seal_time, artifacts):
    require(index.get('schema') == 'campaign002-qualification-index-1', 'Wrong qualification index schema')
    require(all(name in index for name in ('native', 'boundary', 'smoke', 'pilots')),
            'Qualification index incomplete')
    pilots = index['pilots']
    require(len(pilots) == 2 and {entry.get('family') for entry in pilots} == {'misplaced-stock', 'blocked-insert-home'},
            'Exactly one qualification pilot per family required')
    core = runtime_identities(frozen)
    verify_native(index['native'], core, seal_time, artifacts)
    verify_boundary(index['boundary'], core, seal_time)
    verify_model_qualifier(index['smoke'], 'smoke', core, seal_time, artifacts)
    for entry in pilots:
        verify_model_qualifier(entry, 'pilot', core, seal_time, artifacts)


def verify_schedule(schedule, attempts, source_revision):
    require(schedule.get('schema') == 'campaign002-fixed-schedule-1'
            and schedule.get('campaign_id') == CAMPAIGN_ID and schedule.get('source_revision') == source_revision
            and schedule.get('attempt_count') == 20 and schedule.get('replacements_allowed') == 0,
            'Wrong fixed Campaign 002 schedule')
    slots = schedule.get('slots', [])
    require(len(slots) == len(attempts) == 20, 'Exactly 20 immutable attempts required')
    seen_paths = set()
    fixed_fields = ('schema', 'stage', 'mode', 'sim_cap_s', 'wall_cap_s', 'storage_cap_bytes', 'physics_dt_s',
                    'clock_mode', 'activation_policy', 'operator_only_fixture', 'model', 'effort', 'bootstrap',
                    'model_turns_max', 'invocation_wall_cap_s', 'action_request_budget', 'observation_request_budget',
                    'interruption_trigger', 'prior_attempt')
    templates = {family: base.read_json(INTEGRATION / 'campaign-001/predeclared-v1' / filename)
                 for family, filename in [('misplaced-stock', 'RCI001-C01-stock-01.json'),
                                           ('blocked-insert-home', 'RCI001-C01-home-01.json')]}
    for index, (slot, planned) in enumerate(zip(slots, attempts), 1):
        pair = (index - 1) // 2
        family = ('misplaced-stock', 'blocked-insert-home')[(index - 1) % 2 ^ (pair % 2)]
        replicate = pair + 1
        run_id = 'RCI001-C02-' + ('stock' if family == 'misplaced-stock' else 'home') + f'-{replicate:02d}'
        require(slot.get('ordinal') == planned.get('ordinal') == index
                and slot.get('run_id') == planned.get('run_id') == run_id
                and slot.get('family') == planned.get('family') == family
                and slot.get('within_family_replicate') == replicate and slot.get('world_seed') == 173
                and slot.get('noise_seed') == 23000 + index and slot.get('maximum_model_invocations') == 1,
                'Fixed order/identity/seed violation')
        manifest_path = artifact(planned['manifest'])
        require(planned['manifest']['sha256'] == slot.get('sha256') and manifest_path.name == slot.get('manifest'),
                'Attempt manifest differs from predeclared slot')
        manifest = base.read_json(manifest_path)
        require(manifest.get('run_id') == run_id and manifest.get('family') == family
                and manifest.get('framework_revision') == source_revision
                and manifest.get('seed') == 173 and manifest.get('noise_seed') == 23000 + index
                and all(key in manifest and manifest[key] == templates[family][key] for key in fixed_fields),
                'Campaign manifest changes frozen fixture/model/prompt/controller limits or identity')
        require(same_path(planned['workspace'], slot['runtime_workspace'])
                and same_path(planned['workspace'], manifest['runtime_workspace']), 'Workspace differs from fixed schedule')
        for name in ('workspace', 'evidence', 'host_evidence', 'storage_receipt'):
            path = Path(planned[name])
            require(path.is_absolute(), 'Absolute attempt path required')
            identity = str(path.resolve()).casefold()
            require(identity not in seen_paths, 'All attempt paths must be unique')
            seen_paths.add(identity)
            if name == 'workspace':
                require(not path.resolve().is_relative_to(REPO.resolve()), 'Robot workspace must be external to repository')


def verify_storage_policy(cert, paths):
    policy = base.read_json(paths['storage_policy'])
    require(policy.get('schema') == 'campaign001-storage-guard-1' and policy.get('campaign_id') == CAMPAIGN_ID
            and policy.get('reserve_bytes') == 100_000_000_000
            and policy.get('retirement_headroom_bytes') == 2_000_000_000
            and policy.get('planning_allowance_bytes') == PLANNING_BYTES
            and policy.get('large_growth_notice_bytes') == 8_000_000_000
            and policy.get('safe_stop') is True and finite(policy.get('interval_s')) and 1 <= policy['interval_s'] <= 10
            and finite(policy.get('max_sample_gap_s')) and 0 < policy['max_sample_gap_s'] <= 30
            and bool(policy.get('native_roots')) and bool(policy.get('wsl_roots'))
            and bool(policy.get('native_free_paths')) and bool(policy.get('wsl_free_paths')),
            'Invalid sealed Campaign 002 storage policy')
    roots = [Path(row['path']).resolve() for row in policy['native_roots']]
    require(HERE.resolve() in roots, 'Storage policy does not cover Campaign 002 records')
    for attempt in cert['attempts']:
        require(all(any(Path(attempt[key]).resolve().is_relative_to(root) for root in roots)
                    for key in ('workspace', 'evidence', 'host_evidence', 'storage_receipt')),
                'Storage policy does not cover an admitted native attempt path')
    baseline = base.read_json(paths['storage_baseline'])
    require(baseline.get('schema') == 'campaign001-storage-guard-1' and baseline.get('preflight_passed') is True
            and baseline.get('monitor_source_sha256') == cert['artifacts']['storage_monitor']['sha256']
            and baseline.get('config_sha256') == cert['artifacts']['storage_policy']['sha256'],
            'External storage baseline does not bind passed source and policy')
    require(stamp(baseline['created_utc']) <= stamp(cert['created_at']), 'Storage baseline postdates admission')
    for scope in ('native', 'wsl'):
        free = baseline.get('sample', {}).get(scope, {}).get('free_bytes', {})
        require(bool(free) and all(type(value) is int and value >= 102_000_000_000 for value in free.values()),
                'Storage baseline protected reserve/headroom unavailable')


def verify_assets(refresh, verifier_sha256, seal_time):
    require(base.hash_file(ASSET_BASELINE) == ASSET_BASELINE_SHA256, 'Original qualified asset baseline changed')
    original = base.read_json(ASSET_BASELINE)
    require(refresh.get('schema') == 'rci-campaign-asset-refresh-1' and refresh.get('qualified') is True
            and refresh.get('source_sha256') == verifier_sha256
            and refresh.get('prior_qualification_sha256') == ASSET_BASELINE_SHA256
            and stamp(refresh['created_at']) <= seal_time, 'Asset refresh source, baseline or timing binding differs')
    assets, packages = refresh.get('assets', []), refresh.get('packages', [])
    require(len(assets) == len(original.get('assets', [])) == 80
            and len(packages) == len(original.get('packages', [])) == 10, 'Asset or package inventory incomplete')
    expected_assets = {str(Path(row['path']).resolve()).casefold(): (row['bytes'], row['sha256']) for row in original['assets']}
    actual_assets = {str(Path(row['path']).resolve()).casefold(): (row['bytes'], row['sha256']) for row in assets}
    require(len(expected_assets) == len(actual_assets) == 80 and actual_assets == expected_assets,
            'Physical asset set or expected identities changed')
    for row in assets:
        path = artifact(row)
        require(row.get('matched') is True and type(row.get('bytes')) is int and path.stat().st_size == row['bytes'],
                'Physical asset bytes changed')
    expected_packages = {row['name']: row['expected_version'] for row in original['packages']}
    actual_packages = {row['name']: row['expected_version'] for row in packages}
    require(len(expected_packages) == len(actual_packages) == 10 and actual_packages == expected_packages,
            'Qualified package set or expected versions changed')
    for row in packages:
        require(row.get('matched') is True
                and importlib.metadata.version(row['name']) == row.get('expected_version') == row.get('actual_version'),
                'Installed runtime package version changed: ' + row['name'])


def verify_certificate(certificate_path, certificate_sha256):
    require(base.hash_file(certificate_path) == certificate_sha256, 'Certificate does not match external seal')
    cert = base.read_json(certificate_path)
    require(cert.get('schema') == 'campaign002-admission-1' and cert.get('campaign_id') == CAMPAIGN_ID
            and cert.get('release_revision') == RELEASE_REVISION
            and isinstance(cert.get('source_revision'), str) and cert['source_revision'].startswith('RCI001-C02-dev-'),
            'Wrong Campaign 002 admission identity')
    seal_time = stamp(cert['created_at'])
    require(all(name in cert.get('artifacts', {}) for name in REQUIRED_ARTIFACTS), 'Missing required admission artifact')
    paths = {name: artifact(record) for name, record in cert['artifacts'].items()}
    expected = {'protocol': HERE / 'PLAN.md', 'base_assessor': HERE / 'assessment/assess.py',
                'smoke_assessor': HERE / 'assessment/assess_smoke_v2.py', 'admission_verifier': Path(__file__),
                'operator': HERE / 'operate.py', 'registry': HERE / 'registry.py',
                'settlement': HERE / 'settle.py',
                'asset_verifier': HERE / 'admission/verify_assets.py',
                'storage_monitor': INTEGRATION / 'campaign-001/admission/storage-guard/storage_guard.py'}
    require(all(same_path(paths[name], path) for name, path in expected.items()), 'Certificate binds wrong implementation artifact')
    require(same_path(paths['source_archive'], paths['source_snapshot'].with_name('code.zip')),
            'Source archive is not the exact snapshot sibling')
    frozen = base.read_json(paths['source_snapshot'])
    require(not base.frozen_problems(paths['source_snapshot'], frozen, cert['source_revision']),
            'Final frozen source/archive integrity failed')
    verify_assessor_helpers(frozen)
    require(stamp(frozen['created_at']) <= seal_time, 'Final frozen source snapshot postdates admission')
    schedule = base.read_json(paths['schedule'])
    require(schedule.get('plan_sha256') == cert['artifacts']['protocol']['sha256']
            and schedule.get('source_snapshot_sha256') == cert['artifacts']['source_snapshot']['sha256'],
            'Schedule plan/final source snapshot binding differs')
    verify_schedule(schedule, cert.get('attempts', []), cert['source_revision'])
    verify_storage_policy(cert, paths)
    verify_assets(base.read_json(paths['asset_refresh']), cert['artifacts']['asset_verifier']['sha256'], seal_time)
    verify_qualification_index(base.read_json(paths['qualification_index']), frozen, seal_time, cert['artifacts'])
    return cert


def verify_registration(registration_path, cert, certificate_sha256):
    registration = base.read_json(registration_path)
    snapshot_sha = cert['artifacts']['source_snapshot']['sha256']
    require(registration.get('schema') == 'campaign002-registration-1'
            and registration.get('certificate_sha256') == certificate_sha256
            and registration.get('release_revision') == cert['release_revision']
            and registration.get('source_snapshot_sha256') == snapshot_sha, 'Registration binding mismatch')
    for key, expected in (('release_snapshot', snapshot_sha), ('release_archive', cert['artifacts']['source_archive']['sha256'])):
        artifact(registration[key])
        require(registration[key]['sha256'] == expected, 'Registration changed frozen implementation')
    release = base.read_json(artifact(registration['release_record']))
    map_root = Path(registration['map_root'])
    require(same_path(map_root, MAP), 'Wrong canonical map root')
    revisions, runs = base.jsonl(map_root / 'revisions.jsonl'), base.jsonl(map_root / 'runs.jsonl')
    require([row for row in revisions if row.get('id') == cert['release_revision']] == [release],
            'Frozen revision not uniquely registered in canonical map')
    require(release.get('id') == cert['release_revision']
            and release.get('details', {}).get('certificate_sha256') == certificate_sha256,
            'Registered release does not bind admission')
    require(stamp(release['recorded_at']) >= stamp(cert['created_at']), 'Release predates admission')
    require(len(registration.get('attempts', [])) == 20, 'Incomplete immutable attempt registration')
    for expected, registered in zip(cert['attempts'], registration['attempts']):
        require(registered.get('run_id') == expected['run_id']
                and registered.get('manifest_sha256') == expected['manifest']['sha256'], 'Registered attempt differs')
        record = base.read_json(artifact(registered['run_record']))
        require([row for row in runs if row.get('id') == expected['run_id']] == [record],
                'Attempt not uniquely registered in canonical map')
        require(record.get('id') == expected['run_id'] and record.get('revision_id') == cert['release_revision']
                and record.get('condition_details', {}).get('manifest_sha256') == expected['manifest']['sha256']
                and record.get('details', {}).get('certificate_sha256') == certificate_sha256
                and record['condition_details'].get('manifest') == base.read_json(expected['manifest']['path'])
                and stamp(record['recorded_at']) >= stamp(release['recorded_at']),
                'Immutable map run record does not bind campaign attempt')
    return registration


def verify_storage(receipt_path, cert, attempt, queue_path, job):
    """Retained Campaign 001 guard checks, with the explicit C02 baseline key.

The original guard implementation/schema remains unchanged. This independent
consumer neither runs the monitor nor converts sampled peak usage into an exact
between-sample peak. Planning allowance is advisory, never an admission ceiling.
"""
    receipt = base.read_json(receipt_path)
    require(receipt.get('schema') == 'campaign001-storage-guard-1', 'Wrong external storage receipt schema')
    require(receipt.get('run_id') == attempt['run_id'] and receipt.get('job_id') == job['id'], 'Storage receipt identity differs')
    require(receipt.get('monitor_source_sha256') == cert['artifacts']['storage_monitor']['sha256']
            and receipt.get('config_sha256') == cert['artifacts']['storage_policy']['sha256'], 'Storage monitor/policy differs from seal')
    artifact(receipt['baseline'])
    require(receipt['baseline']['sha256'] == cert['artifacts']['storage_baseline']['sha256'], 'Storage baseline differs from seal')
    for key in ('manifest', 'evidence', 'host_evidence', 'workspace'):
        expected = attempt['manifest']['path'] if key == 'manifest' else attempt[key]
        require(same_path(receipt['paths'][key], expected), 'Storage monitored wrong ' + key)
    queue_bound = artifact(receipt['official_queue_receipt'])
    require(same_path(queue_bound, queue_path) and receipt['official_queue_receipt']['sha256'] == base.hash_file(queue_path),
            'Storage official queue receipt differs')
    samples_path = artifact(receipt['samples'])
    samples = base.jsonl(samples_path)
    require(type(receipt.get('sample_count')) is int and len(samples) == receipt['sample_count'] and len(samples) >= 2,
            'Storage samples missing or count differs')
    require(receipt.get('state') == 'completed' and receipt.get('official_queue_state') == 'succeeded'
            and type(receipt.get('official_queue_exit_status')) is int and receipt['official_queue_exit_status'] == 0,
            'Storage guard did not observe official successful completion')
    require(samples[0]['started_utc'] == receipt['first_sample_utc']
            and samples[-1]['finished_utc'] == receipt['last_sample_utc'], 'Storage sample coverage summary differs')
    for sample in samples:
        require(stamp(sample['started_utc']) <= stamp(sample['finished_utc']), 'Reversed storage sample timestamps')
    require(all(stamp(a['finished_utc']) <= stamp(b['started_utc']) for a, b in zip(samples, samples[1:])),
            'Overlapping or reversed storage samples')
    require(receipt.get('coverage_complete') is True
            and stamp(receipt['first_sample_utc']) <= stamp(job['started_at'])
            and stamp(receipt['last_sample_utc']) >= stamp(job['ended_at']), 'Storage coverage does not enclose queue execution')
    require(receipt.get('admission_stop_latched') is False and receipt.get('reserve_bytes') == 100_000_000_000,
            'Storage guard stop/reserve violation')
    free = receipt['minimum_free_bytes']
    require(set(free) >= {'native', 'wsl'} and all(type(free[name]) is int and free[name] >= receipt['reserve_bytes']
                                                for name in ('native', 'wsl')), 'Observed disk reserve violated')
    for scope in ('native', 'wsl'):
        require(all(bool(sample.get(scope, {}).get('free_bytes'))
                    and all(type(value) is int for value in sample[scope]['free_bytes'].values()) for sample in samples),
                'Storage free-space samples absent or malformed')
        require(free[scope] == min(min(sample[scope]['free_bytes'].values()) for sample in samples),
                'Storage receipt free-space summary differs from retained samples')
    require(all(type(sample.get('aggregate_additional_bytes')) is int and sample['aggregate_additional_bytes'] >= 0
                for sample in samples), 'Storage aggregate growth samples absent or malformed')
    require(receipt['peak_aggregate_additional_bytes'] == max(sample['aggregate_additional_bytes'] for sample in samples),
            'Storage receipt peak summary differs from retained samples')
    policy = base.read_json(cert['artifacts']['storage_policy']['path'])
    require(all(free[scope] >= receipt['reserve_bytes'] + policy['retirement_headroom_bytes'] for scope in ('native', 'wsl')),
            'Storage samples crossed protected retirement headroom')
    require(finite(receipt.get('max_sample_gap_s')) and receipt['max_sample_gap_s'] >= 0,
            'Storage sample spacing is not retained')
    require(receipt['max_sample_gap_s'] <= policy['max_sample_gap_s']
            and all(stamp(b['started_utc']) - stamp(a['started_utc']) <= policy['max_sample_gap_s']
                    for a, b in zip(samples, samples[1:])), 'Storage sample gap exceeds frozen policy')
    require(receipt['accounting_scope'] == policy['accounting_scope'], 'Storage scope differs from policy')
    return receipt


def admitted_assess(certificate_path, certificate_sha256, registration_path, run_id, queue_receipt, job_id):
    # Actual scored outcome files remain unread until this queue/authentication gate.
    job = base.queue_gate(base.read_json(queue_receipt), job_id)
    cert = verify_certificate(certificate_path, certificate_sha256)
    registration = verify_registration(registration_path, cert, certificate_sha256)
    matches = [row for row in cert['attempts'] if row['run_id'] == run_id]
    require(len(matches) == 1, 'Attempt not in sealed fixed schedule')
    attempt = matches[0]
    require(stamp(cert['created_at']) < stamp(job['started_at']), 'Admission must precede scored attempt start')
    release = base.read_json(registration['release_record']['path'])
    require(stamp(release['recorded_at']) < stamp(job['started_at']), 'Frozen release must precede scored attempt start')
    require(all(stamp(base.read_json(row['run_record']['path'])['recorded_at']) < stamp(job['started_at'])
                for row in registration['attempts']), 'All immutable attempts must be registered before execution')
    require(base.queue_paths_match(job, Path(attempt['manifest']['path']), Path(attempt['evidence']),
                                  Path(attempt['host_evidence']), Path(attempt['workspace'])),
            'Official queue direct command/paths differ from admitted attempt')
    result = base.assess(Path(attempt['manifest']['path']), Path(attempt['evidence']), Path(attempt['host_evidence']),
                         Path(queue_receipt), Path(cert['artifacts']['source_snapshot']['path']), attempt['manifest']['sha256'],
                         job_id, expected_workspace=Path(attempt['workspace']), expected_revision=cert['source_revision'])
    checks = {'pre_outcome_campaign_seal_and_frozen_registration': True}
    errors, storage = {}, None
    try:
        storage = verify_storage(attempt['storage_receipt'], cert, attempt, queue_receipt, job)
        checks['external_aggregate_storage_coverage_and_reserve'] = True
    except (ValueError, KeyError, TypeError, OSError) as error:
        checks['external_aggregate_storage_coverage_and_reserve'] = False
        errors['storage'] = str(error)
    try:
        strict_timing_summary(result.get('campaign_timing'), 'Scored episode')
        checks['current_episode_frozen_full_sample_timing_and_scheduling'] = True
    except (ValueError, KeyError, TypeError, OSError) as error:
        checks['current_episode_frozen_full_sample_timing_and_scheduling'] = False
        errors['timing'] = str(error)
    result['schema'] = 'robot-codex-campaign-admitted-assessment-2'
    result['episode_evidence_assessment_validity'] = result['validity']
    result['checks'].update(checks)
    result['failed_checks'] = [name for name, passed in result['checks'].items() if passed is not True]
    valid = not result['failed_checks']
    result['validity'] = 'valid' if valid else 'invalid'
    result['task_outcome'] = result['observed_task_outcome'] if valid else 'unknown'
    result['scorable'] = valid and result['task_outcome'] in ('success', 'failure')
    result['scientific_admission'] = {'qualified': True, 'admissible': valid,
        'certificate_sha256': certificate_sha256, 'registered_release_revision': cert['release_revision'],
        'registration_sha256': base.hash_file(registration_path), 'checks': checks, 'errors': errors,
        'scope': 'Prospective repeated known fixed fixtures, exactly 20 fresh slots; no held-out geometry or causal recovery-improvement claim.'}
    result['external_storage'] = storage
    result['bindings'].update(admitted_assessor_sha256=base.hash_file(__file__),
                              certificate_sha256=certificate_sha256, registration_sha256=base.hash_file(registration_path),
                              storage_receipt_sha256=base.hash_file(attempt['storage_receipt'])
                              if Path(attempt['storage_receipt']).is_file() else None)
    result['limitations'].append('Storage is externally sampled; retained spacing does not establish exact between-sample peak usage.')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('certificate', 'registration', 'queue-receipt', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('certificate-sha256', 'run-id', 'job-id'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args(argv)
    result = admitted_assess(args.certificate, args.certificate_sha256, args.registration,
                             args.run_id, args.queue_receipt, args.job_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({key: result[key] for key in ('run_id', 'validity', 'task_outcome', 'scorable', 'failed_checks')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
