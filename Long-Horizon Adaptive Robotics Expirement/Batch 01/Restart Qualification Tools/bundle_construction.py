"""Non-authorizing dossier/draft from a completed extraction; no inferred bounds.

No simulator, queue, seed generator, Runtime import or successful-subset fitting.
The input completion marker belongs to extract_screen.py. This tool hashes the
extracted bytes it uses; it does not replace that extractor's raw-byte/receipt
verification or the protected loader's later independent evidence verification.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from compatibility import digest, finite, sha

PROVISIONAL_SCHEMA = 'provisional-restart-class-rule-1'
GEOMETRY_SCOPE = 'discrete_native_evaluated_states_empirical_transfer'
SELECTION_RULE = 'unique_bilateral_payload_template'
RICH_LANDMARKS = ('cut', 'after_cancel', 'after_hold', 'before_recovery',
                  'after_recovery_admission', 'after_placement')


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _read(path):
    raw = Path(path).read_bytes()
    return json.loads(raw), {'path': str(Path(path).resolve()), 'sha256': hashlib.sha256(raw).hexdigest()}


def _child(base, relative):
    _require(isinstance(relative, str), 'missing extracted artifact path')
    path = (base / relative).resolve()
    _require(base in path.parents, 'extracted artifact escapes its completed output directory')
    return path


def _point(state, label, trial, trial_ref):
    """Keep one coupled observed tuple; never project it into a success box."""
    if not isinstance(state, dict) or state.get('status') != 'recorded':
        return None
    snapshot = state.get('payload', {})
    _require(isinstance(snapshot, dict) and sha(snapshot.get('snapshot_sha256')),
             'recorded measured state lacks protected snapshot identity')
    identity = (trial.get('child_result') or {}).get('details', {}).get('picked_visible_part_id')
    if identity is None:identity = snapshot.get('exposure', {}).get('part_id')
    objects = [obj for obj in snapshot.get('geometry', {}).get('objects', []) if obj.get('id') == identity]
    point = {'landmark': label, 'trial_id': trial['trial_id'], 'trial_ref': trial_ref,
             'event_ref': state.get('source_ref'), 'event_id': state.get('event_id'),
             'snapshot_sha256': snapshot.get('snapshot_sha256'),
             'physical_configuration_sha256': snapshot.get('physical_configuration_sha256'),
             'physical_class_observation_sha256': digest(snapshot['physical_class_observation'])
                 if isinstance(snapshot.get('physical_class_observation'),dict) else None,
             'source_hashes': snapshot.get('source_hashes'), 'sim_time_s': snapshot.get('capture_sim_time_s'),
             'payload_id': identity, 'payload': objects[0] if len(objects) == 1 else None,
             'robot': snapshot.get('robot'), 'contact': snapshot.get('contacts', {}).get('by_object', {}).get(identity),
             'payload_pose': snapshot.get('object_poses', {}).get(identity),
             'class_export_state': snapshot.get('physical_class_observation', {}).get('export_state'),
             'exposure': snapshot.get('exposure'), 'measured_range_created': False}
    _require(digest({key:value for key,value in snapshot.items() if key != 'snapshot_sha256'}) == snapshot.get('snapshot_sha256'),
             'extracted snapshot digest changed: ' + trial['trial_id'] + '/' + label)
    return point


def construction_dossier(extraction_path, destination):
    """Read only the completed extraction. Retain every declared trial status."""
    extraction_path = Path(extraction_path).resolve(); base = extraction_path.parent
    extraction, extraction_ref = _read(extraction_path)
    _require(extraction.get('schema_version') == 'recovery-screen-extraction-1', 'unsupported completed extraction')
    _require(isinstance(extraction.get('completed_at'), str), 'extraction is not complete')
    _require(destination in ('parking1', 'parking2'), 'unsupported declared destination')
    seen, rows, groups = set(), [], {}
    for entry in extraction.get('trials', []):
        identity = entry['trial_id']
        _require(identity not in seen, 'duplicate extracted trial identity'); seen.add(identity)
        trial, trial_ref = _read(_child(base, entry['path']))
        _require(trial['trial_id'] == identity and trial['execution_status'] == entry['execution_status'], 'extracted trial index differs')
        declaration = trial['declaration']; child = trial.get('child_result') or {}; details = child.get('details', {})
        row = {'trial_id':identity, 'declaration':declaration, 'execution_status':trial['execution_status'],
               'trial_ref':trial_ref, 'parent_attempt':trial.get('parent_attempt'), 'child_status':child.get('status'),
               'physical_predicates_passed':details.get('physical_predicates_passed'),
               'sources_unchanged':child.get('sources_unchanged'), 'timing':child.get('timing'),
               'payload_id':details.get('picked_visible_part_id'), 'absence':details.get('absence'),
               'artifact_refs':trial.get('artifact_refs', {}), 'coupled_points':[],
               'selected_destination':declaration.get('destination') == destination,
               'construction_fixture':declaration.get('fixture') == 'construction'}
        states_ref = trial.get('measured_states', {}).get('output_path')
        if states_ref:
            states, ref = _read(_child(base, states_ref)); row['measured_states_ref'] = ref
            records = states.get('states', {})
            row['rich_capture_status'] = {label: records.get(label, {}).get('status', 'not_recorded')
                                          for label in RICH_LANDMARKS}
            for label in RICH_LANDMARKS:
                state = records.get(label)
                point = _point(state, label, trial, trial_ref)
                if point is not None:row['coupled_points'].append(point)
            admission = records.get('recovery_admission', {'status':'not_recorded'})
            if admission.get('status') == 'recorded':
                payload = admission.get('payload')
                _require(admission.get('event_type') == 'action_admission' and isinstance(payload,dict)
                         and payload.get('action',{}).get('operation') == 'recover_held'
                         and isinstance(payload.get('response'),dict)
                         and sha(admission.get('payload_sha256'))
                         and digest(payload) == admission['payload_sha256'],
                         'recorded recovery admission identity/payload changed: ' + identity)
            # This event records action/response and exact admission clocks; it
            # is not a protected state and must never masquerade as a snapshot.
            row['recovery_admission'] = admission
            row['other_state_records'] = {label:state for label,state in records.items()
                if label not in RICH_LANDMARKS and label != 'recovery_admission'}
        geometry_ref = trial.get('geometry', {}).get('output_path')
        if geometry_ref:
            geometry, ref = _read(_child(base, geometry_ref)); row['geometry_ref'] = ref
            row['geometry_status'] = geometry.get('status')
            row['geometry_limitation'] = geometry.get('limitation')
        # A group is an index of actual locations, not a calibrated cell or map.
        if row['selected_destination']:
            key = (str(declaration.get('family')), str(row['payload_id']))
            groups.setdefault(key, []).append(identity)
        rows.append(row)
    _require(rows, 'completed extraction contains no declared trial rows')
    dossier = {'schema_version':'restart-construction-dossier-1', 'construction_extraction':extraction_ref,
        'destination':destination, 'extraction_receipt_ref':extraction.get('receipt_ref'),
        'source_manifest_ref':extraction.get('manifest_ref'), 'trials':rows,
        'family_pickup_groups':[{'family':family,'observed_payload_id':payload,'trial_ids':ids}
                                for (family,payload),ids in sorted(groups.items())],
        'qualification_granted':False,'numerical_envelopes_created':False,'continuous_bound_created':False,
        'scope':'exact coupled observations and all declared outcomes; no automatic min/max, successful-subset selection or validation claim'}
    draft = {'schema_version':PROVISIONAL_SCHEMA,'status':'incomplete_provisional_rule',
        'created_at':None,'destination':destination,'construction_extraction':extraction_ref,
        'class_spec':None,'selection_rule':SELECTION_RULE,'payload_template_to_cell':{},'cells':[],
        'absence':{'prospective_absence_bound_s':None,'absence_timebase':None,'absence_endpoint':None},
        'geometry_scope':GEOMETRY_SCOPE,'empirical_transfer_rule':None,'untested_combinations':None,
        'qualification_granted':False,'validation_outcomes_used_for_fitting':False}
    return dossier, draft


def validate_provisional_rule(rule, *, expected_destination=None):
    """Identity/completeness guard only, never numerical or physical qualification.

    Fixture launchers additionally hash/copy the exact rule before validation
    and require its creation time to precede that screen. A separately measured
    engineering judgment must supply the numerical values and transfer scope.
    """
    _require(isinstance(rule, dict) and rule.get('schema_version') == PROVISIONAL_SCHEMA, 'unsupported provisional rule')
    _require(rule.get('status') == 'provisional_development_rule', 'provisional rule is still incomplete')
    stamp = datetime.fromisoformat(str(rule.get('created_at')).replace('Z', '+00:00'))
    _require(stamp.tzinfo is not None, 'provisional rule time requires timezone')
    destination = rule.get('destination')
    _require(destination in ('parking1','parking2') and (expected_destination is None or destination == expected_destination), 'provisional destination differs')
    for name in ('construction_extraction','class_spec'):
        ref = rule.get(name)
        _require(isinstance(ref, dict) and isinstance(ref.get('path'), str) and sha(ref.get('sha256')), 'missing provisional '+name+' reference')
    _require(sha(rule['class_spec'].get('canonical_sha256')), 'canonical class identity missing')
    _require(rule.get('selection_rule') == SELECTION_RULE and rule.get('geometry_scope') == GEOMETRY_SCOPE, 'unsupported provisional selection/geometry scope')
    _require(isinstance(rule.get('empirical_transfer_rule'), str) and rule['empirical_transfer_rule'].strip(), 'empirical coupled-cell assumption missing')
    _require(isinstance(rule.get('untested_combinations'), (str,list)) and bool(rule['untested_combinations']), 'untested scope missing')
    _require(rule.get('validation_outcomes_used_for_fitting') is False, 'validation outcomes cannot fit the provisional rule')
    absence = rule.get('absence', {})
    _require(finite(absence.get('prospective_absence_bound_s')) and absence['prospective_absence_bound_s'] > 0
             and absence.get('absence_timebase') in ('simulation','wall')
             and absence.get('absence_endpoint') in ('restart_ready','recover_held_admitted'), 'provisional absence convention missing')
    cells, mapping = rule.get('cells'), rule.get('payload_template_to_cell')
    _require(isinstance(cells,list) and cells and isinstance(mapping,dict) and mapping, 'provisional cells/map missing')
    _require(all(isinstance(c,dict) and isinstance(c.get('cell_id'),str) for c in cells), 'provisional cells malformed')
    by_id = {c['cell_id']:c for c in cells}; _require(len(by_id) == len(cells), 'duplicate provisional cell')
    for template, identity in mapping.items():
        _require(template in ('part:A','part:B') and identity in by_id, 'unsupported mapped provisional cell')
        cell = by_id[identity]; grip, route = cell.get('grip_envelope',{}), cell.get('route_envelope',{})
        grip_fields=('kind','family','jaw_width_m','relative_position_m','relative_rotation','maximum_rotation_error_rad',
                     'finger_normal_force_N','maximum_linear_speed_m_s','maximum_angular_speed_rad_s','minimum_payload_bottom_z_m')
        route_fields=('operation','destination','tcp_start_m','destination_region_m','joint_start_ranges_rad',
                      'joint_velocity_ranges_rad_s','maximum_abs_finger_velocity_m_s','clearance_corridors_m','payload_kind','payload_family')
        _require(all(grip.get(key) is not None for key in grip_fields) and all(route.get(key) is not None for key in route_fields),
                 'provisional physical envelopes are incomplete')
        _require(template == str(grip.get('kind'))+':'+str(grip.get('family'))
                 == str(route.get('payload_kind'))+':'+str(route.get('payload_family'))
                 and route.get('destination') == destination and route.get('operation') == 'recover_held', 'provisional cell payload/route differ')
        for key in ('measured_state_cell_basis','source_scope','route_coverage_method','untested_combinations'):
            _require(isinstance(cell.get(key),str) and cell[key].strip(), 'provisional cell missing '+key)
        _require(sha(cell.get('payload_template_sha256')) and isinstance(cell.get('measured_points'),list) and cell['measured_points'], 'measured cell identity absent')
        _require(finite(cell.get('route_sampling_clearance_allowance_m')) and cell['route_sampling_clearance_allowance_m'] >= 0,
                 'observed discrete sampling allowance missing')
    return {'state':'complete_for_prospective_validation','qualification_granted':False,
            'numerical_and_physical_support_assessed':False,'canonical_rule_sha256':digest(rule)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--construction-extraction',required=True)
    parser.add_argument('--destination',choices=('parking1','parking2'),required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args(argv); output=Path(args.output).resolve()
    _require(not output.exists(),'output must be fresh')
    dossier,draft=construction_dossier(args.construction_extraction,args.destination)
    output.mkdir(parents=True,exist_ok=False)
    for name,value in (('construction-dossier.json',dossier),('provisional-rule.draft.json',draft)):
        with (output/name).open('x',encoding='utf-8',newline='\n') as stream:
            json.dump(value,stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')
    print(json.dumps({'output':str(output),'declared_trials':len(dossier['trials']),'qualification_granted':False}))


if __name__=='__main__':main()
