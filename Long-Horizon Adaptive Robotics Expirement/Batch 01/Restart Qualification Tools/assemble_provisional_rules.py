"""Queue-only materialization of exact root choices before untouched validation.

No fitting, new numerical choices, source edits, physics or qualification.
Contradictions retain a report and prevent either provisional rule being written.
"""
from __future__ import annotations
import argparse
import ast
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from bundle_construction import (GEOMETRY_SCOPE, PROVISIONAL_SCHEMA, SELECTION_RULE,
                                 construction_dossier, validate_provisional_rule)
from compatibility import digest

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
RUNTIME = PROJECT/'Runtime'
CHOICES_SHA256 = '0dc4687822db5229e6d9fead06c39516facd06c6452f047d90e2e25b5ba406a5'
RUNTIME_SHA256 = 'd5f354c60af83c6f9d32f6b43a893c19486ddcb1f8d2f85c78f526fe48d0273c'
DESTINATIONS = ('parking1', 'parking2')
GROUPS = ('A1', 'B10')


def require(value, reason):
    if not value:
        raise ValueError(reason)


def utc():
    return datetime.now(timezone.utc).isoformat()


def stamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'Timezone-aware artifact time required')
    return result.astimezone(timezone.utc)


def file_ref(path):
    path = Path(path).resolve(); before = path.stat()
    with path.open('rb') as stream:
        checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    after = path.stat()
    require((before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
            (after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'Input changed while hashing: '+str(path))
    return {'path': str(path), 'sha256': checksum, 'bytes': after.st_size}


def same_ref(a, b):
    return a['sha256'] == b['sha256'] and Path(a['path']).resolve() == Path(b['path']).resolve()


def argument(argv, name, cwd, *, path=True):
    require(argv.count(name) == 1, 'Missing/ambiguous receipt argument: '+name)
    value = argv[argv.index(name)+1]
    if not path:
        return value
    result = Path(value)
    return (result if result.is_absolute() else Path(cwd)/result).resolve()


def validate_choices(choices, raw_sha):
    require(raw_sha == CHOICES_SHA256, 'Exact root choice bytes differ; never adapt the numbers')
    require(choices['schema_version'] == 'root-provisional-recovery-choices-1'
            and choices['status'] == 'root_authored_choices_pending_current_source_construction'
            and choices['destinations'] == list(DESTINATIONS)
            and set(choices['cell_choices']) == set(GROUPS)
            and choices['validation_outcomes_used_for_fitting'] is False, 'Unsupported root choice declaration')
    require(choices['cover_bin_width_m'] == .05 and choices['uniform_materialized_corridor_padding_m'] == .01
            and choices['prospective_absence_bound_s'] == 5. and choices['absence_timebase'] == 'wall'
            and choices['absence_endpoint'] == 'recover_held_admitted', 'Declared root geometry/absence choices differ')


def thin_point(row, label='cut'):
    state = row['states'][label]; snapshot = state['payload']
    return {'snapshot_sha256': snapshot['snapshot_sha256'],
        'physical_configuration_sha256': snapshot['physical_configuration_sha256'],
        'physical_class_observation_sha256': digest(snapshot['physical_class_observation']),
        'trial_id': row['trial_id'], 'landmark': label, 'source_ref': state['source_ref'],
        'trial_ref': row['consumed_ref'], 'measured_states_ref': row['measured_states_consumed_ref']}


def make_cell(choices, destination, group, spec, reference, corridors, points, geometry_refs):
    selected = choices['cell_choices'][group]
    snapshot = reference['states']['cut']['payload']
    kind, family = selected['template'].split(':')
    rotation = snapshot['object_poses'][group]['relative_to_tcp']['rotation']
    grip = {name: copy.deepcopy(selected[name]) for name in ('jaw_width_m', 'relative_position_m',
        'maximum_rotation_error_rad', 'finger_normal_force_N', 'maximum_linear_speed_m_s',
        'maximum_angular_speed_rad_s', 'minimum_payload_bottom_z_m')}
    grip.update(kind=kind, family=family, relative_rotation=copy.deepcopy(rotation))
    route = {'operation': 'recover_held', 'destination': destination, 'payload_kind': kind, 'payload_family': family,
        'tcp_start_m': copy.deepcopy(selected['tcp_start_m']),
        'destination_region_m': copy.deepcopy(snapshot['geometry']['zones'][destination]),
        'joint_start_ranges_rad': [[v-selected['joint_start_half_width_rad'], v+selected['joint_start_half_width_rad']]
                                  for v in selected['joint_start_center_rad']],
        'joint_velocity_ranges_rad_s': [[v-selected['joint_velocity_half_width_rad_s'], v+selected['joint_velocity_half_width_rad_s']]
                                       for v in selected['joint_velocity_center_rad_s']],
        'maximum_abs_finger_velocity_m_s': selected['maximum_abs_finger_velocity_m_s'],
        'clearance_corridors_m': corridors}
    return {'cell_id': destination+'-'+group+'-root-001', 'grip_envelope': grip, 'route_envelope': route,
        'payload_template_sha256': digest(spec['templates'][selected['template']]),
        'measured_points': points, 'evidence_refs': [],
        'envelope_basis': choices['envelope_basis'],
        'maximum_qualified_absence_s': choices['prospective_absence_bound_s'],
        'absence_timebase': choices['absence_timebase'], 'absence_endpoint': choices['absence_endpoint'],
        'measured_state_cell_basis': choices['empirical_transfer_rule'],
        'source_scope': 'Exact current protected physical class and completed current-source construction; no validation outcomes used.',
        'route_coverage_method': 'All original dense native per-geometry interval boxes contained in fixed 50 mm center-bin outer hulls, with root-selected 10 mm materialized transfer padding; discrete states only.',
        'route_sampling_clearance_allowance_m': 0.,
        'route_sampling_clearance_allowance_scope': 'No additional allowance beyond materialized coordinates; zero is not an observed coarse deficit or a continuous error bound.',
        'uniform_materialized_corridor_padding_m': choices['uniform_materialized_corridor_padding_m'],
        'geometry_support_refs': geometry_refs,
        'observed_coarse_sampling_deficit': {'value': None,
            'scope': 'Per-interval measured deficits remain in referenced original whole-geometry traces; no added scan or summary here.'},
        'relative_rotation_reference': thin_point(reference),
        'untested_combinations': choices['untested_combinations']}


def numerical_expectation(group, in_domain, membership):
    if not in_domain:
        return 'class_excluded'
    if group in GROUPS:
        require(membership['state'] == 'pass', 'Selected in-domain construction cut contradicts fixed numerical choices')
        return 'included_numerical_cut'
    require(group == 'B2', 'Unexpected construction payload group; no new cell may be inferred')
    require(membership['state'] == 'fail' and membership.get('template') == 'part:B'
            and membership.get('grip', {}).get('state') in ('pass', 'fail')
            and membership.get('route', {}).get('state') == 'fail', 'B2 is not demonstrably excluded by complete numerical predicates')
    routes = membership['route']['observed']
    require(len(routes) == 1 and (routes[0]['checks']['tcp_start'] is False or routes[0]['checks']['joint_start'] is False),
            'B2 needs an actual local-start predicate exclusion, not an ID label or missing evidence')
    return 'numerically_excluded_B2'


def construction_support(assessment, rule, row, timestep, functions):
    # All raw landmark/child bytes are rebound by CompletedExtraction. Avoid a
    # second event scan here; final assessment independently checks the dwell event.
    observed = assessment.hold_assessment(rule, row, timestep, None, functions)
    required = {key: value for key, value in observed['checks'].items() if key != 'settled_dwell_event'}
    return {'required_checks_pass': bool(required) and all(value is True for value in required.values()),
        'required_checks': required, 'full_assessment_with_unassessed_dwell': observed,
        'settled_dwell_event': 'not_reassessed_in_rule_preflight; raw event retained and required by final assessor',
        'qualification_granted': False}


def load_compatibility(source):
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            require(all(item.name in ('hashlib', 'json', 'math', 're') for item in node.names), 'Unsupported archived compatibility import')
        if isinstance(node, ast.ImportFrom):
            require(node.module == '__future__', 'Unsupported archived compatibility import')
    namespace = {'__name__': '_source_bound_provisional_compatibility'}
    exec(compile(source, '<archived compatibility>', 'exec'), namespace)
    return namespace['verify_class_compatibility']


def bind_dossier(source, destination, path, receipt_path, runner):
    dossier, dossier_ref = source.evidence.external(path)
    receipt, receipt_ref = source.evidence.external(receipt_path)
    require(receipt.get('state') == 'succeeded' and type(receipt.get('exit_status')) is int
            and receipt['exit_status'] == 0, 'Successful official dossier receipt required')
    require(isinstance(receipt.get('id'), str) and receipt['id'], 'Dossier receipt lacks installed queue identity')
    require(runner.verify_queue_receipt(receipt['id'], receipt_path) == receipt,
            'Dossier receipt differs from installed queue record or consumed bytes')
    require(stamp(source.data['completed_at']) <= stamp(receipt['started_at'])
            <= stamp(receipt['ended_at']) <= datetime.now(timezone.utc), 'Dossier receipt time does not follow completed extraction')
    require(runner.python_entrypoint(receipt['argv'], receipt['cwd']) == HERE/'bundle_construction.py', 'Dossier receipt entrypoint differs')
    require(argument(receipt['argv'], '--output', receipt['cwd'])/'construction-dossier.json' == Path(path).resolve()
            and argument(receipt['argv'], '--construction-extraction', receipt['cwd']) == source.path
            and argument(receipt['argv'], '--destination', receipt['cwd'], path=False) == destination,
            'Dossier receipt arguments/output differ')
    expected, _ = construction_dossier(source.path, destination)
    require(dossier == expected and same_ref(dossier['construction_extraction'], source.ref), 'Dossier differs from exact extraction regeneration')
    return dossier, {'dossier_ref': dossier_ref, 'receipt_ref': receipt_ref}


def bind_compact(source, destination, path, receipt_path, assessment, runner):
    compact, ref = source.evidence.external(path)
    receipt, receipt_ref = source.evidence.external(receipt_path)
    assessment.successful_receipt(receipt, compact.get('queue'), compact['completed_at'])
    require(compact.get('schema_version') == 'compact-construction-corridor-diagnostic-1'
            and compact.get('status') == 'complete' and compact['source_inputs_unchanged'] is True
            and compact['destination'] == destination and compact['all_selected_trials_processed'] is True,
            'Completed compact coverage/source status differs')
    require(runner.python_entrypoint(receipt['argv'], receipt['cwd']) == PROJECT/'Engineering Investigation/compact_construction_corridors.py'
            and argument(receipt['argv'], '--output', receipt['cwd'])/'compact-corridors.json' == Path(path).resolve(),
            'Compact receipt entrypoint/output differs')
    for name, expected in (('construction_extraction_ref', source.ref), ('screen_receipt_ref', source.receipt_ref),
                           ('extraction_receipt_ref', source.extraction_receipt_ref)):
        require(same_ref(compact[name], expected), 'Compact source identity differs: '+name)
    require(compact['inputs_before'] == compact['inputs_after'], 'Compact helper source hold failed')
    for expected in compact['inputs_after'].values():
        require(file_ref(expected['path']) == expected, 'Compact helper dependency changed')
    require([r['trial_id'] for r in compact['trials']] == list(source.declared), 'Compact dropped original trial IDs')
    return compact, {'compact_ref': ref, 'receipt_ref': receipt_ref}


def cover_for(source, choices, compact, group, expected_ids, functions):
    groups = [g for g in compact['payload_location_groups'] if g['payload_location_group'] == group]
    require(len(groups) == 1, 'Missing/ambiguous compact payload group')
    selected = groups[0]
    require(selected['all_declared_group_routes_included'] is True
            and selected['all_available_group_cut_scenes_included'] is True
            and selected['included_trial_ids'] == expected_ids and selected['cut_scene_trial_ids'] == expected_ids,
            'Compact group does not retain every actual same-group construction trial')
    candidates = [c for c in selected['candidates'] if c['bin_width_m'] == choices['cover_bin_width_m']]
    require(len(candidates) == 1, 'Declared compact bin width missing/ambiguous')
    candidate = candidates[0]; cover, ref = source.evidence.external(candidate['cover_ref']['path'])
    require(same_ref(ref, candidate['cover_ref']) and cover['payload_location_group'] == group
            and cover['bin_width_m'] == choices['cover_bin_width_m']
            and len(cover['covers']) == candidate['cover_box_count'], 'Compact cover identity/count differs')
    for containment in (selected['containment'], candidate['containment'], cover['containment']):
        require(containment['state'] == 'pass' and containment['failed_assignments'] == 0
                and containment['checked_assignments'] > 0 and containment['comparison_epsilon_m'] == 0.,
                'Declared compact cover lacks complete exact input containment')
    comparisons = candidate['actual_cut_scene_comparisons']
    require([r['cut_trial_id'] for r in comparisons] == expected_ids, 'Compact cut-scene comparisons incomplete')
    padding = choices['uniform_materialized_corridor_padding_m']
    for comparison in comparisons:
        records = [r for r in comparison['padding_comparisons'] if r['uniform_padding_m'] == padding]
        require(len(records) == 1 and records[0]['strict_interior_intersection_pairs'] == 0
                and records[0]['runtime_overlap_pairs'] == 0 and records[0]['runtime_blocker_ids'] == [],
                'Chosen materialized padding contradicts an actual construction cut scene')
        cut = source.trial(comparison['cut_trial_id'])['states']['cut']
        require(cut['source_ref'] == comparison['cut_source_ref']
                and cut['payload']['snapshot_sha256'] == comparison['cut_snapshot_sha256'], 'Compact/cut binding differs')
    corridors = []
    for record in cover['covers']:
        require(functions['valid_box'](record['box']), 'Malformed original compact box')
        corridors.append({'min': [v-padding for v in record['box']['min']],
                          'max': [v+padding for v in record['box']['max']]})
    require(corridors and all(functions['valid_box'](b) for b in corridors), 'Malformed materialized corridor')
    rows = [r for r in compact['trials'] if r['trial_id'] in expected_ids]
    return corridors, {'cover_ref': ref, 'containment': selected['containment'],
        'source_trace_refs': [{'trial_id': r['trial_id'], 'trace_ref': r['trace_ref'],
                              'input_audit_ref': r['input_audit_ref'], 'statistics': r['statistics']} for r in rows]}


def prepare(args, assessment, runner):
    output = Path(args.output).resolve()
    require(not output.exists(), 'Fresh immutable output directory required')
    source = assessment.CompletedExtraction(args.construction_extraction, args.screen_receipt, args.extraction_receipt)
    require(source.manifest['execution_phase'] == 'construction' and source.manifest['destination_selection'] == 'all',
            'Complete both-destination construction required')
    require(source.summary['sources_unchanged'] is True and not source.summary['not_started'], 'Construction incomplete or source changed')
    input_folders = [Path(getattr(args, destination+'_'+name)).resolve().parent
                     for destination in DESTINATIONS for name in ('dossier', 'compact')]
    for base in (source.base, source.evidence.root, PROJECT/'Runtime', PROJECT/'Batch 01', *input_folders):
        base = base.resolve()
        require(output != base and base not in output.parents and output not in base.parents, 'Output overlaps input or protected source')
    require('candidate_state' not in [p.casefold() for p in output.parts], 'Candidate output forbidden')
    choices, choices_ref = source.evidence.external(args.choices)
    validate_choices(choices, choices_ref['sha256'])
    numeric, numeric_ref = source.source('Runtime/restart_state.py')
    require(numeric_ref['sha256'] == RUNTIME_SHA256 == file_ref(RUNTIME/'restart_state.py')['sha256'], 'Fresh optimized-source construction required')
    fixture_code, fixture_ref = source.source('Batch 01/Recovery Qualification/fixture.py')
    functions = assessment.numeric_functions(numeric, fixture_code)
    compat_code, compat_ref = source.source('Runtime/restart_compatibility.py')
    compatible = load_compatibility(compat_code)
    current_runtime_refs = []
    for path, checksum in source.manifest['source_hashes'].items():
        path = Path(path).resolve()
        if path.is_relative_to(RUNTIME.resolve()):
            ref = file_ref(path); require(ref['sha256'] == checksum, 'Archived/current Runtime source differs: '+str(path))
            current_runtime_refs.append(ref)
    report = {'schema_version': 'root-provisional-rule-construction-1', 'created_at': utc(),
        'choices_ref': choices_ref, 'construction_extraction_ref': source.ref,
        'screen_receipt_ref': source.receipt_ref, 'extraction_receipt_ref': source.extraction_receipt_ref,
        'numeric_source_ref': numeric_ref, 'fixture_source_ref': fixture_ref, 'compatibility_source_ref': compat_ref,
        'current_runtime_refs': current_runtime_refs, 'trials': [], 'destinations': {}, 'errors': [],
        'qualification_granted': False, 'readiness_granted': False, 'validation_outcomes_used_for_fitting': False,
        'limitations': ['Root-selected numerical transfer assumptions are not fitted or qualified by this builder.',
            'Final independent settled dwell event is not rescanned in preflight; the unchanged final assessor requires it.',
            'Materialized padding is empirical transfer only; no continuous-sweep bound or extra sampling allowance.',
            'Boundary class exclusions and B2 numerical exclusions are retained; no object-ID admission gate.']}
    rows = {}
    for identity, declaration in source.declared.items():
        item = {'trial_id': identity, 'declaration': declaration, 'execution_status': source.entries[identity]['execution_status'],
                'selected_construction': identity in source.selected}
        report['trials'].append(item)
        if identity not in source.selected:
            continue
        try:
            row = source.trial(identity); rows[identity] = row
            child = row.get('child_result') or {}; details = child.get('details') or {}
            item.update(payload_id=details.get('picked_visible_part_id'), child_status=child.get('status'), child_error=child.get('error'),
                physical_predicates_passed=details.get('physical_predicates_passed'), timing=child.get('timing'),
                generator_domain_member=(row.get('compiled_properties') or {}).get('all_objects_generator_domain_members'),
                trial_ref=row['consumed_ref'], cut_ref=thin_point(row))
            require(not row['unparsed_events'], 'Unparsed raw event records retained')
        except (ValueError, KeyError, TypeError, OSError) as exc:
            item.update(binding_state='unknown', reason=str(exc)); report['errors'].append(identity+': '+str(exc))
    trial_reports = {r['trial_id']: r for r in report['trials']}
    rules, classes = {}, {}
    for destination in DESTINATIONS:
        try:
            dossier, dossier_refs = bind_dossier(source, destination, getattr(args, destination+'_dossier'),
                                                getattr(args, destination+'_dossier_receipt'), runner)
            compact, compact_refs = bind_compact(source, destination, getattr(args, destination+'_compact'),
                                                getattr(args, destination+'_compact_receipt'), assessment, runner)
            reference_id = destination+'-'+choices['cell_choices']['A1']['reference_trial_suffix']
            reference = rows[reference_id]; spec = reference['protected_class_spec']
            require(spec is not None, 'Reference cut lacks protected class bytes')
            spec_path = source.evidence.path(reference_id+'/protected-class-spec.json')
            spec_raw = spec_path.read_bytes(); original_ref = source.evidence.stream(reference_id+'/protected-class-spec.json')
            class_ref = {'path': str(output/destination/'class-spec.json'), 'sha256': hashlib.sha256(spec_raw).hexdigest(),
                         'canonical_sha256': digest(spec)}
            require(class_ref['sha256'] == original_ref['sha256'], 'Class bytes changed while copying')
            classes[destination] = spec_raw
            rule = {'schema_version': PROVISIONAL_SCHEMA, 'status': 'provisional_development_rule', 'created_at': utc(),
                'destination': destination, 'construction_extraction': source.ref, 'class_spec': class_ref,
                'selection_rule': SELECTION_RULE, 'geometry_scope': GEOMETRY_SCOPE,
                'payload_template_to_cell': {}, 'cells': [], 'root_choices_ref': choices_ref,
                'empirical_transfer_rule': choices['empirical_transfer_rule'], 'untested_combinations': choices['untested_combinations'],
                'absence': {k: choices[k] for k in ('prospective_absence_bound_s', 'absence_timebase', 'absence_endpoint')},
                'validation_outcomes_used_for_fitting': False, 'qualification_granted': False, 'readiness_granted': False,
                'measured_cut_class_exclusions': [], 'numerically_excluded_construction_cuts': [],
                'construction_dossier_refs': dossier_refs, 'construction_compact_refs': compact_refs}
            selected_ids = [i for i in source.selected if source.declared[i]['destination'] == destination]
            for group in GROUPS:
                ids = [i for i in selected_ids if trial_reports[i].get('payload_id') == group]
                require(ids, 'Selected construction payload group absent')
                reference = rows[destination+'-'+choices['cell_choices'][group]['reference_trial_suffix']]
                require((reference['child_result']['details']['picked_visible_part_id'] == group)
                        and reference['protected_class_spec'] == spec
                        and reference['compiled_properties']['all_objects_generator_domain_members'] is True,
                        'Exact center reference payload/class/domain differs')
                rotation = reference['states']['cut']['payload']['object_poses'][group]['relative_to_tcp']['rotation']
                require(functions['proper_rotation'](rotation), 'Reference relative rotation is not proper')
                corridors, geometry_refs = cover_for(source, choices, compact, group, ids, functions)
                points = [thin_point(rows[i]) for i in ids if trial_reports[i]['generator_domain_member'] is True]
                require(points, 'No in-domain coupled measured cut points')
                cell = make_cell(choices, destination, group, spec, reference, corridors, points, geometry_refs)
                rule['cells'].append(cell); rule['payload_template_to_cell'][choices['cell_choices'][group]['template']] = cell['cell_id']
            compact_rows = {r['trial_id']: r for r in compact['trials']}
            for identity in selected_ids:
                row = rows[identity]; item = trial_reports[identity]; snapshot = row['states']['cut']['payload']
                timestep = compact_rows[identity]['statistics']['physics_timestep_s']
                support = construction_support(assessment, rule, row, timestep, functions)
                item['construction_hold_support'] = support
                require(support['required_checks_pass'], identity+': full cut-to-admission hold/timing support contradicts choices')
                compatibility = compatible(spec, snapshot['physical_class_observation'], frozen_spec_sha256=digest(spec))
                membership = assessment.numeric_membership(rule, spec, snapshot, functions)
                item.update(class_compatibility=compatibility, numerical_cut_membership=membership)
                in_domain = item['generator_domain_member'] is True
                if in_domain:
                    require(row['protected_class_spec'] == spec and compatibility['compatibility_state'] == 'pass',
                            identity+': in-domain protected class contradicts chosen current spec')
                else:
                    require(item['generator_domain_member'] is False and compatibility['compatibility_state'] != 'pass',
                            identity+': class-domain exclusion is ambiguous')
                classification = numerical_expectation(item['payload_id'], in_domain, membership)
                item['construction_cut_classification'] = classification
                if classification == 'class_excluded':
                    rule['measured_cut_class_exclusions'].append({'trial_id': identity, 'cut_ref': item['cut_ref'],
                        'class_compatibility': compatibility, 'generator_domain_member': False})
                if classification == 'numerically_excluded_B2':
                    rule['numerically_excluded_construction_cuts'].append({'trial_id': identity, 'cut_ref': item['cut_ref'],
                        'reason': 'Actual mapped part:B numerical local-start predicate fails; no object-ID admission gate.'})
            require(rule['numerically_excluded_construction_cuts'], 'Original B2 construction exclusion not verified')
            validate_provisional_rule(rule, expected_destination=destination)
            rule['complete_original_trial_status_index'] = [{k: item[k] for k in ('trial_id', 'execution_status', 'selected_construction')}
                                                           for item in report['trials']]
            rules[destination] = rule
            report['destinations'][destination] = {'state': 'fixed_choices_supported_for_prospective_validation_only',
                **dossier_refs, **compact_refs, 'original_class_ref': original_ref,
                'class_spec_sha256': digest(spec), 'cell_ids': [c['cell_id'] for c in rule['cells']],
                'provisional_rule_canonical_sha256': digest(rule), 'qualification_granted': False}
        except (ValueError, KeyError, TypeError, OSError, StopIteration) as exc:
            report['destinations'][destination] = {'state': 'contradiction_or_unknown', 'reason': str(exc)}
            report['errors'].append(destination+': '+str(exc))
    source.evidence.stable()
    report['consumed_files'] = list(source.evidence.consumed.values())
    report['completed_at'] = utc()
    report['state'] = 'stopped_without_rules' if report['errors'] or set(rules) != set(DESTINATIONS) else 'ready_for_prospective_validation_only'
    return source, report, rules, classes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('choices', 'construction-extraction', 'screen-receipt', 'extraction-receipt', 'output'):
        parser.add_argument('--'+name, required=True)
    for destination in DESTINATIONS:
        for name in ('dossier', 'dossier-receipt', 'compact', 'compact-receipt'):
            parser.add_argument('--'+destination+'-'+name, required=True)
    args = parser.parse_args(argv)
    sys.path.insert(0, str(RUNTIME))
    import release_runner
    authority = release_runner.queued_job(expected_script=__file__)
    import assess_validation as assessment
    dependencies = [Path(__file__).resolve(), Path(assessment.__file__).resolve(), Path(assessment.reader.__file__).resolve(),
        HERE/'bundle_construction.py', HERE/'compatibility.py', Path(release_runner.__file__).resolve(),
        PROJECT/'Engineering Investigation/compact_construction_corridors.py', Path(args.choices).resolve()]
    before = {str(path): file_ref(path) for path in dependencies}
    source, report, rules, classes = prepare(args, assessment, release_runner)
    after = {str(path): file_ref(path) for path in dependencies}
    for ref in report['current_runtime_refs']:
        require(file_ref(ref['path']) == ref, 'Runtime source changed during materialization')
    require(before == after, 'Assembler/choice dependencies changed')
    source.evidence.stable()
    report.update(queue=authority, source_before=before, source_after=after, source_inputs_unchanged=True)
    output = Path(args.output).resolve(); output.mkdir(parents=True, exist_ok=False)
    written = {}
    if report['state'] == 'ready_for_prospective_validation_only':
        for destination in DESTINATIONS:
            folder = output/destination; folder.mkdir()
            with (folder/'class-spec.json').open('xb') as stream:
                stream.write(classes[destination])
            assessment.reader.write(folder/'provisional-rule.json', rules[destination])
            written[destination] = {'class_spec_ref': file_ref(folder/'class-spec.json'),
                                    'rule_ref': file_ref(folder/'provisional-rule.json')}
    report['written_rules'] = written
    assessment.reader.write(output/'construction-membership.json', report)
    require(report['state'] == 'ready_for_prospective_validation_only', 'Root choices contradicted or evidence unknown; no rules written')
    print(json.dumps({'output': str(output), 'rules': written, 'qualification_granted': False}))


if __name__ == '__main__':
    main()
