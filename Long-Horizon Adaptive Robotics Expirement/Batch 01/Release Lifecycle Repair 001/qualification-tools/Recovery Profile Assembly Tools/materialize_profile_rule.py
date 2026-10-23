"""Queue-only A1 profile rule materialization from construction, never validation.

Reuses the existing bound extraction, dossier, compact-cover and mathematical
adapters. Only the prospectively declared reference q/qd/rotation may change.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
TOOLS = HERE.parent / 'Restart Qualification Tools'
RUNTIME = PROJECT / 'Runtime 004'
sys.path.insert(0, str(TOOLS))
import assemble_provisional_rules as shared
from bundle_construction import GEOMETRY_SCOPE, PROVISIONAL_SCHEMA, SELECTION_RULE, validate_provisional_rule
from compatibility import digest

require = shared.require


def validate_choices(choices, identity, base_choices, base_identity, expected_sha256):
    require(isinstance(expected_sha256, str) and len(expected_sha256) == 64
            and all(c in '0123456789abcdef' for c in expected_sha256)
            and identity['sha256'] == expected_sha256, 'Prospective root-pinned profile choice bytes changed')
    shared.validate_choices(base_choices, base_identity['sha256'])
    require(base_identity['sha256'] == choices['base_choices_ref']['sha256'], 'Original allowance policy identity differs')
    require(choices['schema_version'] == 'root-provisional-profile-choices-1'
        and choices['destination'] == 'parking1' and choices['cell_id'] == 'runtime004-profile-A1-root-001'
        and choices['payload_template'] == 'part:A' and choices['construction_group'] == 'A1'
        and choices['reference_trial_id'] == 'parking1-high-corner-A-5'
        and choices['validation_outcomes_used_for_fitting'] is False, 'Unsupported prospective profile selection')
    policy = choices['unchanged_A1_policy']
    expected_keys = set(base_choices['cell_choices']['A1']) - {
        'template', 'reference_trial_suffix', 'joint_start_center_rad', 'joint_velocity_center_rad_s'}
    require(set(policy) == expected_keys and all(policy[k] == base_choices['cell_choices']['A1'][k] for k in policy),
            'An original scalar/TCP/grip allowance changed')
    for key in ('cover_bin_width_m', 'uniform_materialized_corridor_padding_m', 'prospective_absence_bound_s',
                'absence_timebase', 'absence_endpoint', 'envelope_basis'):
        require(choices[key] == base_choices[key], 'Original geometry/absence policy changed: ' + key)
    require(choices['additional_sampling_clearance_allowance_m'] == 0.
            and choices['absence_start'] == 'before_cancel', 'Unsupported extra allowance or absence origin')


def check_selection(source, choices):
    require(source.manifest['execution_phase'] == 'construction'
            and source.manifest['destination_selection'] in ('all', 'parking1'), 'Construction-only input required')
    require(source.summary['sources_unchanged'] is True and not source.summary['not_started'], 'Construction incomplete or sources changed')
    require(source.selected == choices['construction_trial_ids'] and len(source.selected) == 7,
            'All seven exact prospective construction IDs are required in order')
    require(shared.stamp(choices['created_at']) < shared.stamp(source.receipt['started_at']),
            'Choices were not declared before construction started')
    deferred = []
    for identity, declaration in source.declared.items():
        require(declaration['destination'] == 'parking1' and declaration['family'] == 'A'
                and declaration['expected_payload_id'] == 'A1', 'Unexpected destination/payload declaration')
        if identity in source.selected:
            require(declaration['fixture'] == 'construction' and declaration['transport_profile'] == 'high'
                    and declaration['evidence_role'] == 'cell_construction'
                    and declaration['transport_destination'] == 'fixture'
                    and declaration['transport_objective'] == {'clearance': .25, 'speed_scale': 1, 'approach': 'vertical', 'avoid_zones': []},
                    'Prospective high construction declaration differs')
        else:
            require(declaration['fixture'] == 'independent_generator'
                    and source.entries[identity]['execution_status'] == 'deferred_to_other_phase',
                    'Validation is not untouched/deferred in this construction source')
            deferred.append(identity)
    expected_deferred = [f'parking1-{profile}-validation-n{n}-A'
                         for n in (3, 6, 10) for profile in ('high', 'baseline')]
    require(deferred == expected_deferred and len(source.declared) == 13,
            'Complete fixed 13-trial plan and six untouched validation declarations required')


def resolved_choices(choices, base_choices, reference, functions):
    """Copy the one declared measured tuple; never compute extrema or averages."""
    require(reference['trial_id'] == choices['reference_trial_id'], 'Different center reference forbidden')
    snapshot = reference['states']['cut']['payload']; robot = snapshot['robot']
    rotation = snapshot['object_poses']['A1']['relative_to_tcp']['rotation']
    require(functions['vector'](robot['joint_position_rad'], 7)
            and functions['vector'](robot['joint_velocity_rad_s'], 7)
            and functions['proper_rotation'](rotation), 'Incomplete exact reference q/qd/rotation')
    result = copy.deepcopy(base_choices)
    result['cell_choices'] = {'A1': copy.deepcopy(base_choices['cell_choices']['A1'])}
    result['cell_choices']['A1']['joint_start_center_rad'] = copy.deepcopy(robot['joint_position_rad'])
    result['cell_choices']['A1']['joint_velocity_center_rad_s'] = copy.deepcopy(robot['joint_velocity_rad_s'])
    for key in ('empirical_transfer_rule', 'untested_combinations'):
        result[key] = choices[key]
    return result


def numerical_preflight(rule, snapshot, functions):
    """Original numeric formulas, separate from class admission at boundary points."""
    try:
        require(not snapshot.get('capture_errors'), 'Incomplete protected capture')
        contacts = snapshot['contacts']['by_object']
        touched = [key for key, row in contacts.items() if row['hand_contact']]
        held = [key for key, row in contacts.items() if row['bilateral_force_bearing']]
        require(touched == held == ['A1'], 'Construction lacks its declared unique bilateral A1 payload')
        objects = snapshot['geometry']['objects']; identities = [o['id'] for o in objects]
        require(len(set(identities)) == len(identities) and sorted(identities) == sorted(snapshot['expected_object_ids'])
                and all(functions['valid_box'](o['bounds']) for o in objects), 'Protected object inventory incomplete')
        obj = next(o for o in objects if o['id'] == 'A1')
        require(obj['kind'] == 'part' and obj['family'] == 'A', 'Wrong construction payload template')
        require(all(functions['vector'](snapshot['robot'][key], count) for key, count in
                    (('joint_position_rad', 7), ('joint_velocity_rad_s', 7), ('finger_velocity_m_s', 2))), 'Incomplete arm/finger vectors')
        cell = rule['cells'][0]
        available = [name for name in functions['policy']['recovery_destinations'] if name in snapshot['geometry']['zones']
                     and not any(functions['overlaps'](o['bounds'], snapshot['geometry']['zones'][name]) for o in objects)]
        grip = functions['_grip']({'envelope': cell['grip_envelope']}, snapshot, obj, functions['policy'])
        route = functions['_route']([{'envelope': cell['route_envelope']}], snapshot, obj, available)
        state = 'fail' if 'fail' in (grip[0], route[0]) else 'pass' if grip[0] == route[0] == 'pass' else 'unknown'
        return {'state': state, 'payload_id': obj['id'],
                'grip': {'state': grip[0], 'reason': grip[1], 'observed': grip[2]},
                'route': {'state': route[0], 'reason': route[1], 'observed': route[2]},
                'scope': 'Unchanged archived physical numeric formulas only; no class export is synthesized and no qualification is granted'}
    except (KeyError, ValueError, TypeError, StopIteration) as error:
        return {'state': 'unknown', 'reason': str(error)}


def enforce_cut(numerical, class_membership, compatibility, in_domain):
    require(numerical['state'] == 'pass', 'A selected construction cut contradicts the unchanged numerical allowances')
    if in_domain is True:
        require(class_membership['state'] == 'pass' and compatibility['compatibility_state'] == 'pass',
                'In-domain class/membership support is incomplete')
        return 'included_numerical_cut'
    require(in_domain is False and compatibility['compatibility_state'] != 'pass', 'Ambiguous boundary class exclusion')
    return 'class_excluded_numeric_preflight_pass'


def prepare(args, assessment, runner):
    output = Path(args.output).resolve(); require(not output.exists(), 'Fresh immutable output required')
    for name in ('screen_receipt', 'extraction_receipt', 'dossier_receipt', 'compact_receipt'):
        path = Path(getattr(args, name)).resolve(); receipt = json.loads(path.read_bytes())
        require(receipt.get('state') == 'succeeded' and type(receipt.get('exit_status')) is int and receipt['exit_status'] == 0,
                'Successful official input receipt required: ' + name)
        require(runner.verify_queue_receipt(receipt['id'], str(path)) == receipt, 'Installed official receipt differs: ' + name)
    source = assessment.CompletedExtraction(args.construction_extraction, args.screen_receipt, args.extraction_receipt)
    choices, choices_ref = source.evidence.external(args.choices)
    prospective_ref = source.manifest.get('relocation_declaration', {}).get('prospective_choices_ref') or {}
    require(prospective_ref.get('sha256') == choices_ref['sha256'] == args.choices_sha256
            and Path(prospective_ref.get('path', '')).resolve() == Path(args.choices).resolve()
            and source.manifest['source_hashes'].get(str(Path(args.choices).resolve())) == args.choices_sha256,
            'Choices were not pinned in the original prospective construction manifest')
    base_path = (Path(args.choices).resolve().parent / choices['base_choices_ref']['path']).resolve()
    base_choices, base_ref = source.evidence.external(base_path)
    validate_choices(choices, choices_ref, base_choices, base_ref, args.choices_sha256); check_selection(source, choices)
    for folder in (source.base, source.evidence.root, PROJECT/'Runtime 004', PROJECT/'Batch 01',
                   Path(args.dossier).resolve().parent, Path(args.compact).resolve().parent):
        folder = folder.resolve()
        require(output != folder and folder not in output.parents and output not in folder.parents, 'Output overlaps input or source')
    require('candidate_state' not in [p.casefold() for p in output.parts], 'Candidate state output forbidden')
    numeric, numeric_ref = source.source('Runtime 004/restart_state.py')
    fixture, fixture_ref = source.source('Batch 01/Release Lifecycle Repair 001/qualification-tools/Recovery Qualification/fixture.py')
    functions = assessment.numeric_functions(numeric, fixture)
    compat_code, compat_ref = source.source('Runtime 004/restart_compatibility.py')
    compatible = shared.load_compatibility(compat_code)
    runtime_refs = []
    for path, checksum in source.manifest['source_hashes'].items():
        path = Path(path).resolve()
        if path.is_relative_to(RUNTIME.resolve()):
            reference = shared.file_ref(path); require(reference['sha256'] == checksum, 'Current/archived Runtime source differs')
            runtime_refs.append(reference)
    report = {'schema_version': 'profile-provisional-rule-construction-1', 'created_at': shared.utc(),
        'choices_ref': choices_ref, 'base_choices_ref': base_ref, 'construction_extraction_ref': source.ref,
        'screen_receipt_ref': source.receipt_ref, 'extraction_receipt_ref': source.extraction_receipt_ref,
        'numeric_source_ref': numeric_ref, 'fixture_source_ref': fixture_ref, 'compatibility_source_ref': compat_ref,
        'current_runtime_refs': runtime_refs, 'trials': [], 'errors': [], 'qualification_granted': False,
        'readiness_granted': False, 'validation_outcomes_used_for_fitting': False}
    rows = {}; items = {}; rule = None; spec_raw = None
    for identity, declaration in source.declared.items():
        item = {'trial_id': identity, 'declaration': declaration, 'execution_status': source.entries[identity]['execution_status'],
                'selected_construction': identity in source.selected}
        report['trials'].append(item); items[identity] = item
        if identity not in source.selected:continue  # Never open a validation trial artifact.
        try:
            row = source.trial(identity); rows[identity] = row; child = row.get('child_result') or {}; details = child.get('details') or {}
            item.update(payload_id=details.get('picked_visible_part_id'), child_status=child.get('status'), child_error=child.get('error'),
                physical_predicates_passed=details.get('physical_predicates_passed'), timing=child.get('timing'),
                generator_domain_member=(row.get('compiled_properties') or {}).get('all_objects_generator_domain_members'),
                trial_ref=row['consumed_ref'], cut_ref=shared.thin_point(row))
            require(not row['unparsed_events'] and item['payload_id'] == 'A1', 'Incomplete raw events or different selected payload')
        except (ValueError, KeyError, TypeError, OSError) as error:
            item.update(binding_state='unknown', reason=str(error)); report['errors'].append(identity + ': ' + str(error))
    try:
        require(not report['errors'], 'Selected construction binding failed')
        _, dossier_refs = shared.bind_dossier(source, 'parking1', args.dossier, args.dossier_receipt, runner)
        compact, compact_refs = shared.bind_compact(source, 'parking1', args.compact, args.compact_receipt, assessment, runner)
        reference = rows[choices['reference_trial_id']]; spec = reference['protected_class_spec']
        require(spec is not None and reference['compiled_properties']['all_objects_generator_domain_members'] is True,
                'Declared exact center reference lacks an in-domain protected class')
        resolved = resolved_choices(choices, base_choices, reference, functions)
        corridors, geometry_refs = shared.cover_for(source, resolved, compact, 'A1', source.selected, functions)
        spec_path = source.evidence.path(reference['trial_id'] + '/protected-class-spec.json')
        original_class_ref = source.evidence.stream(reference['trial_id'] + '/protected-class-spec.json')
        spec_raw = spec_path.read_bytes(); require(hashlib.sha256(spec_raw).hexdigest() == original_class_ref['sha256'], 'Class bytes changed')
        class_ref = {'path': str(output/'class-spec.json'), 'sha256': original_class_ref['sha256'], 'canonical_sha256': digest(spec)}
        points = [shared.thin_point(rows[i]) for i in source.selected if items[i]['generator_domain_member'] is True]
        require(points, 'No in-domain measured coupled points')
        cell = shared.make_cell(resolved, 'parking1', 'A1', spec, reference, corridors, points, geometry_refs)
        cell['cell_id'] = choices['cell_id']; cell['joint_center_reference'] = shared.thin_point(reference)
        rule = {'schema_version': PROVISIONAL_SCHEMA, 'status': 'provisional_development_rule', 'created_at': shared.utc(),
            'destination': 'parking1', 'construction_extraction': source.ref, 'class_spec': class_ref,
            'selection_rule': SELECTION_RULE, 'geometry_scope': GEOMETRY_SCOPE,
            'payload_template_to_cell': {'part:A': choices['cell_id']}, 'cells': [cell],
            'root_choices_ref': choices_ref, 'base_allowance_choices_ref': base_ref,
            'empirical_transfer_rule': choices['empirical_transfer_rule'], 'untested_combinations': choices['untested_combinations'],
            'absence': {key: choices[key] for key in ('prospective_absence_bound_s', 'absence_timebase', 'absence_endpoint')},
            'validation_outcomes_used_for_fitting': False, 'qualification_granted': False, 'readiness_granted': False,
            'measured_cut_class_exclusions': [], 'numerically_excluded_construction_cuts': [],
            'construction_dossier_refs': dossier_refs, 'construction_compact_refs': compact_refs}
        report['exact_joint_center_reference'] = {'cut_ref': shared.thin_point(reference),
            'q_rad': resolved['cell_choices']['A1']['joint_start_center_rad'],
            'qd_rad_s': resolved['cell_choices']['A1']['joint_velocity_center_rad_s'],
            'relative_rotation': cell['grip_envelope']['relative_rotation']}
        compact_rows = {row['trial_id']: row for row in compact['trials']}
        for identity in source.selected:
            row = rows[identity]; item = items[identity]; snapshot = row['states']['cut']['payload']
            support = shared.construction_support(assessment, rule, row, compact_rows[identity]['statistics']['physics_timestep_s'], functions)
            compatibility = compatible(spec, snapshot['physical_class_observation'], frozen_spec_sha256=digest(spec))
            class_membership = assessment.numeric_membership(rule, spec, snapshot, functions)
            numerical = numerical_preflight(rule, snapshot, functions)
            item.update(construction_hold_support=support, class_compatibility=compatibility,
                        numerical_cut_membership=class_membership, all_points_numeric_preflight=numerical)
            try:
                require(support['required_checks_pass'], 'Unchanged cut-to-admission hold/timing support failed')
                if item['generator_domain_member'] is True:require(row['protected_class_spec'] == spec, 'Protected class differs')
                classification = enforce_cut(numerical, class_membership, compatibility, item['generator_domain_member'])
                item['construction_cut_classification'] = classification
                if classification == 'class_excluded_numeric_preflight_pass':
                    rule['measured_cut_class_exclusions'].append({'trial_id': identity, 'cut_ref': item['cut_ref'],
                        'class_compatibility': compatibility, 'generator_domain_member': False,
                        'numerical_preflight_only': True, 'qualification_granted': False})
            except (ValueError, KeyError, TypeError) as error:
                item['contradiction'] = str(error); report['errors'].append(identity + ': ' + str(error))
        rule['complete_original_trial_status_index'] = [{key: item[key] for key in ('trial_id', 'execution_status', 'selected_construction')}
                                                       for item in report['trials']]
        validate_provisional_rule(rule, expected_destination='parking1')
        report.update(original_class_ref=original_class_ref, construction_dossier_refs=dossier_refs,
                      construction_compact_refs=compact_refs, proposed_rule_canonical_sha256=digest(rule))
    except (ValueError, KeyError, TypeError, OSError, StopIteration) as error:
        report['errors'].append(str(error))
    source.evidence.stable(); report['consumed_files'] = list(source.evidence.consumed.values())
    report['completed_at'] = shared.utc()
    report['state'] = 'ready_for_prospective_validation_only' if not report['errors'] and rule is not None else 'stopped_without_rule'
    report['limitations'] = ['No validation artifacts consumed; every declared trial/status is retained.',
        'All seven construction numerical preflights are required; out-of-domain points still confer no class admission.',
        'Only exact declared center q/qd/rotation changes; all original fixed scalar allowances remain.',
        'Existing preflight does not independently rescan settled dwell; the final assessor must check it.',
        'Compact native-state geometry plus explicit transfer padding is not a continuous clearance guarantee.']
    return source, report, rule, spec_raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('choices', 'choices-sha256', 'construction-extraction', 'screen-receipt', 'extraction-receipt',
                 'dossier', 'dossier-receipt', 'compact', 'compact-receipt', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args(argv)
    sys.path.insert(0, str(RUNTIME)); import release_runner
    authority = release_runner.queued_job(expected_script=__file__)
    import assess_validation as assessment
    dependencies = [Path(__file__), Path(shared.__file__), Path(assessment.__file__), Path(assessment.reader.__file__),
        TOOLS/'bundle_construction.py', TOOLS/'compatibility.py', Path(release_runner.__file__),
        HERE.parent/'Engineering Investigation/compact_construction_corridors.py', Path(args.choices),
        TOOLS/'root-provisional-choices-001.json']
    before = {str(path.resolve()): shared.file_ref(path) for path in dependencies}
    source, report, rule, spec_raw = prepare(args, assessment, release_runner)
    after = {str(path.resolve()): shared.file_ref(path) for path in dependencies}
    require(before == after, 'Materializer/dependencies/choice source hold failed')
    for reference in report['current_runtime_refs']:require(shared.file_ref(reference['path']) == reference, 'Runtime changed')
    source.evidence.stable(); report.update(queue=authority, source_before=before, source_after=after, source_inputs_unchanged=True)
    output = Path(args.output).resolve(); output.mkdir(parents=True, exist_ok=False)
    report['written_rule'] = None
    if report['state'] == 'ready_for_prospective_validation_only':
        with (output/'class-spec.json').open('xb') as stream:stream.write(spec_raw)
        assessment.reader.write(output/'provisional-rule.json', rule)
        report['written_rule'] = shared.file_ref(output/'provisional-rule.json')
    assessment.reader.write(output/'construction-membership.json', report)
    require(report['state'] == 'ready_for_prospective_validation_only', 'Contradiction/unknown retained; no provisional rule written')
    print(json.dumps({'output': str(output), 'rule': report['written_rule'], 'qualification_granted': False}))


if __name__ == '__main__':main()
