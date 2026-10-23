"""Protected artifact loader and absence facts; no simulator or inferred bounds.

Only the protected release/development operator calls this loader. Artifact byte
verification establishes identity, not that an engineering qualification is
sound. Existing measured-cell and contemporaneous physical checks still apply.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from restart_compatibility import SPEC_SCHEMA, digest, finite, sha, vector
from restart_qualification import QUALIFICATION_SCHEMA, actual_absence_coverage

_AUTHORITY = object()
SOURCE_KEYS = ('cell.py', 'actuation.py', 'evaluator.py', 'sensor_worker.py')
ENDPOINTS = ('restart_ready', 'recover_held_admitted')
TIMEBASES = ('simulation', 'wall')
SELECTION_RULE = 'unique_bilateral_payload_template'
SUPPORTS = {'carry_state', 'absence_survival', 'whole_arm_payload_route', 'settled_placement', 'development_validation'}


class CalibrationInputError(ValueError):
    pass


def _utc(value):
    if not isinstance(value, str):
        raise CalibrationInputError('qualification timestamp missing')
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as error:
        raise CalibrationInputError('qualification timestamp malformed') from error
    if stamp.tzinfo is None:
        raise CalibrationInputError('qualification timestamp lacks timezone')
    return stamp.astimezone(timezone.utc)


def _reference(ref, base, *, parse=False):
    if not isinstance(ref, dict) or not isinstance(ref.get('path'), str) or not sha(ref.get('sha256')):
        raise CalibrationInputError('malformed protected artifact reference')
    path = Path(ref['path'])
    path = (path if path.is_absolute() else base / path).resolve()
    if 'candidate_state' in (part.casefold() for part in path.parts):
        raise CalibrationInputError('qualification artifact cannot come from candidate state')
    try:
        if parse:
            raw = path.read_bytes()
            actual = hashlib.sha256(raw).hexdigest()
        else:
            with path.open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != ref['sha256']:
            raise CalibrationInputError('protected artifact bytes differ: ' + str(path))
        if not parse:
            return path, None
        value = json.loads(raw, parse_constant=lambda v: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
    except (OSError, ValueError, UnicodeError) as error:
        raise CalibrationInputError('cannot verify protected artifact: ' + str(path)) from error
    if not isinstance(value, dict):
        raise CalibrationInputError('protected artifact must be a JSON object')
    return path, value


@dataclass(frozen=True)
class VerifiedRestartQualification:
    """Process-local development provenance; release context serializes a copy."""
    payload_json: str
    _authority: object = field(repr=False, compare=False, default=None)

    def as_dict(self):
        if self._authority is not _AUTHORITY:
            raise CalibrationInputError('qualification was not issued by the protected byte verifier')
        return json.loads(self.payload_json)


def load_restart_qualification(freeze, freeze_path):
    """Load a frozen template-to-cell map or None for legacy exact mode.

    freeze.restart_qualification contains path, file-byte sha256,
    bundle_sha256 (canonical), class_spec_sha256 (canonical), selection_rule,
    payload_template_to_cell (one cell per supported kind:family),
    prospective_absence_bound_s, absence_timebase and absence_endpoint.
    bundle.artifact_files contains artifact_id/path/sha256 references.
    This function generates no seeds, reads no queue state and changes no files.
    """
    if not isinstance(freeze, dict):
        raise CalibrationInputError('freeze is not an object')
    mode = freeze.get('restart_matching_mode', 'exact_configuration')
    ref = freeze.get('restart_qualification')
    if mode == 'exact_configuration' and ref is None:
        return None
    if mode != 'qualified_class':
        raise CalibrationInputError('class qualification requires explicit qualified_class mode')
    freeze_path = Path(freeze_path).resolve()
    try:
        freeze_bytes = freeze_path.read_bytes()
        if digest(json.loads(freeze_bytes)) != digest(freeze):
            raise CalibrationInputError('loaded freeze differs from retained freeze bytes')
    except (OSError, ValueError, TypeError, UnicodeError) as error:
        raise CalibrationInputError('cannot bind retained freeze bytes') from error
    freeze_time = _utc(freeze.get('frozen_at'))
    path, bundle = _reference(ref, freeze_path.parent, parse=True)
    if (bundle.get('schema_version') != QUALIFICATION_SCHEMA or bundle.get('status') != 'measured_development'
            or not isinstance(bundle.get('empirical_transfer_rule'), str) or not bundle['empirical_transfer_rule'].strip()):
        raise CalibrationInputError('unsupported or unmeasured qualification bundle')
    if not sha(ref.get('bundle_sha256')) or digest(bundle) != ref['bundle_sha256']:
        raise CalibrationInputError('canonical bundle digest differs from independent freeze')
    spec = bundle.get('class_spec')
    if (not isinstance(spec, dict) or spec.get('schema_version') != SPEC_SCHEMA
            or not sha(ref.get('class_spec_sha256')) or digest(spec) != ref['class_spec_sha256']):
        raise CalibrationInputError('canonical class digest differs from independent freeze')
    if not _utc(bundle.get('accepted_at_utc')) < freeze_time:
        raise CalibrationInputError('qualification acceptance must predate freeze')
    if not finite(ref.get('prospective_absence_bound_s')) or ref['prospective_absence_bound_s'] <= 0:
        raise CalibrationInputError('measured prospective absence bound missing')
    if ref.get('absence_timebase') not in TIMEBASES or ref.get('absence_endpoint') not in ENDPOINTS:
        raise CalibrationInputError('absence timebase/endpoint must be explicit and supported')
    sources = spec.get('required_source_hashes')
    if not isinstance(sources, dict) or any(not sha(sources.get(key)) for key in SOURCE_KEYS):
        raise CalibrationInputError('class lacks protected capture source identities')
    cells = bundle.get('cells')
    if not isinstance(cells, list) or not cells or any(not isinstance(c, dict) or not isinstance(c.get('cell_id'), str) for c in cells):
        raise CalibrationInputError('measured cells missing')
    if len({c['cell_id'] for c in cells}) != len(cells):
        raise CalibrationInputError('duplicate measured cell identity')
    mapping = ref.get('payload_template_to_cell')
    if (ref.get('selection_rule') != SELECTION_RULE or not isinstance(mapping, dict) or not mapping
            or any(not isinstance(key, str) or key not in spec.get('templates', {})
                   or not isinstance(value, str) or not value for key, value in mapping.items())):
        raise CalibrationInputError('freeze lacks the supported deterministic template-to-cell mapping')
    files = bundle.get('artifact_files')
    if not isinstance(files, list) or not files:
        raise CalibrationInputError('qualification artifact file index missing')
    verified, artifact_files = {}, {}
    for artifact in files:
        identity = artifact.get('artifact_id') if isinstance(artifact, dict) else None
        if not isinstance(identity, str) or not identity or identity in verified:
            raise CalibrationInputError('artifact identity missing or duplicated')
        artifact_path, _ = _reference(artifact, path.parent)
        verified[identity] = artifact['sha256']
        artifact_files[identity] = {'path': str(artifact_path), 'sha256': artifact['sha256']}
    by_id = {cell['cell_id']: cell for cell in cells}
    calibrations = {}
    for template_key, cell_id in mapping.items():
        if cell_id not in by_id:
            raise CalibrationInputError('freeze selects an unknown measured cell')
        calibrations[template_key] = _cell_calibration(by_id[cell_id], template_key, spec, ref, freeze_time, verified)
    destinations = {value['routes'][0]['envelope']['destination'] for value in calibrations.values()}
    if len(destinations) != 1:
        raise CalibrationInputError('frozen mapped cells must share one declared recovery destination')
    context = {'bundle': bundle, 'frozen_bundle_sha256': ref['bundle_sha256'],
               'frozen_class_sha256': ref['class_spec_sha256'], 'freeze_utc': freeze['frozen_at'],
               'prospective_absence_bound_s': ref['prospective_absence_bound_s'], 'verified_artifacts': verified}
    payload = {'qualification_context': context, 'calibration_by_template': calibrations,
               'selection_rule': SELECTION_RULE, 'payload_template_to_cell': mapping,
               'destination': next(iter(destinations)),
               'absence': {key: ref[key] for key in ('prospective_absence_bound_s', 'absence_timebase', 'absence_endpoint')},
               'identity': {'freeze_manifest': {'path': str(freeze_path), 'sha256': hashlib.sha256(freeze_bytes).hexdigest()},
                            'bundle_file': {'path': str(path), 'sha256': ref['sha256']},
                            'bundle_sha256': ref['bundle_sha256'], 'class_spec_sha256': ref['class_spec_sha256'],
                            'selection_rule': SELECTION_RULE, 'payload_template_to_cell': mapping,
                            'artifact_files': artifact_files},
               'scope': 'protected byte-verified input; no physical success or readiness inferred'}
    return VerifiedRestartQualification(json.dumps(payload, sort_keys=True, allow_nan=False), _AUTHORITY)


def _cell_calibration(cell, template_key, spec, ref, freeze_time, verified):
    """Validate each frozen mapped cell before any episode can select it."""
    if (cell.get('envelope_basis') != 'measured_before_this_intervention'
            or not finite(cell.get('maximum_qualified_absence_s'))
            or cell['maximum_qualified_absence_s'] < ref['prospective_absence_bound_s']
            or cell.get('absence_timebase') != ref['absence_timebase']
            or cell.get('absence_endpoint') != ref['absence_endpoint']):
        raise CalibrationInputError('selected cell does not support this absence convention/bound')
    for name in ('grip_envelope', 'route_envelope'):
        if not isinstance(cell.get(name), dict) or not cell[name]:
            raise CalibrationInputError('selected cell has no ' + name)
    grip, route = cell['grip_envelope'], cell['route_envelope']
    def box(value):
        return isinstance(value, dict) and vector(value.get('min')) and vector(value.get('max')) and all(a < b for a, b in zip(value['min'], value['max']))
    def pairs(value, count):
        return isinstance(value, list) and len(value) == count and all(vector(pair, 2) and pair[0] <= pair[1] for pair in value)
    if (not vector(grip.get('jaw_width_m'), 2) or not grip['jaw_width_m'][0] < grip['jaw_width_m'][1]
            or not vector(grip.get('finger_normal_force_N'), 2) or not 0 < grip['finger_normal_force_N'][0] < grip['finger_normal_force_N'][1]
            or not box(grip.get('relative_position_m')) or not isinstance(grip.get('relative_rotation'), list)
            or len(grip['relative_rotation']) != 3 or not all(vector(row) for row in grip['relative_rotation'])
            or any(not finite(grip.get(key)) or grip[key] < 0 for key in
                   ('maximum_rotation_error_rad', 'maximum_linear_speed_m_s', 'maximum_angular_speed_rad_s', 'minimum_payload_bottom_z_m'))):
        raise CalibrationInputError('selected measured grip envelope is incomplete or malformed')
    if (not box(route.get('tcp_start_m')) or not box(route.get('destination_region_m'))
            or not pairs(route.get('joint_start_ranges_rad'), 7) or not pairs(route.get('joint_velocity_ranges_rad_s'), 7)
            or not finite(route.get('maximum_abs_finger_velocity_m_s')) or route['maximum_abs_finger_velocity_m_s'] < 0
            or not isinstance(route.get('clearance_corridors_m'), list) or not route['clearance_corridors_m']
            or not all(box(corridor) for corridor in route['clearance_corridors_m'])):
        raise CalibrationInputError('selected measured route envelope is incomplete or malformed')
    if (route.get('operation') != 'recover_held' or not isinstance(route.get('destination'), str)
            or (grip.get('kind'), grip.get('family')) != (route.get('payload_kind'), route.get('payload_family'))):
        raise CalibrationInputError('selected grip and recovery route do not share a payload')
    if template_key != str(grip.get('kind')) + ':' + str(grip.get('family')):
        raise CalibrationInputError('mapped template differs from measured cell payload')
    template = spec.get('templates', {}).get(template_key)
    if template is None or digest(template) != cell.get('payload_template_sha256'):
        raise CalibrationInputError('selected cell payload template does not match class')
    for key in ('measured_state_cell_basis', 'source_scope', 'route_coverage_method', 'untested_combinations'):
        if not isinstance(cell.get(key), str) or not cell[key].strip():
            raise CalibrationInputError('selected cell lacks measured support: ' + key)
    if not finite(cell.get('route_sampling_clearance_allowance_m')) or cell['route_sampling_clearance_allowance_m'] < 0:
        raise CalibrationInputError('selected cell lacks measured route allowance')
    points = cell.get('measured_points')
    if not isinstance(points, list) or not points or any(not isinstance(p, dict) or any(not sha(p.get(key)) for key in
            ('snapshot_sha256', 'physical_configuration_sha256', 'physical_class_observation_sha256')) for p in points):
        raise CalibrationInputError('selected cell lacks measured point identities')
    references = cell.get('evidence_refs')
    if not isinstance(references, list) or not references:
        raise CalibrationInputError('selected cell has no prior physical references')
    support = set()
    for artifact in references:
        if (not isinstance(artifact, dict) or artifact.get('kind') != 'prior_physical_calibration'
                or not isinstance(artifact.get('artifact_id'), str) or not sha(artifact.get('sha256'))
                or verified.get(artifact.get('artifact_id')) != artifact.get('sha256')
                or artifact.get('bytes_verified_by_operator') is not True
                or not _utc(artifact.get('recorded_at_utc')) < freeze_time
                or not isinstance(artifact.get('supports'), list)
                or any(not isinstance(purpose, str) for purpose in artifact['supports'])):
            raise CalibrationInputError('selected cell evidence identity/timing/support not verified')
        support.update(artifact['supports'])
    if not SUPPORTS <= support:
        raise CalibrationInputError('selected cell lacks retained support for the required physical facts')
    sources = spec['required_source_hashes']
    def entry(role):
        return {'match_mode': 'qualified_class', 'qualification_cell_id': cell['cell_id'], 'qualification_role': role,
                'envelope_basis': cell['envelope_basis'], 'envelope': cell[role + '_envelope'],
                'evidence_refs': references, 'source_hashes': {key: sources[key] for key in SOURCE_KEYS}}
    return {'grip': entry('grip'), 'routes': [entry('route')]}


def select_restart_calibration(protected_input, snapshot):
    """Assess the one frozen template mapping; never search alternate cells.

    Call only with input from the protected loader/release authority and a rich
    protected snapshot. Selection supplies evidence for classification; it does
    not choose a candidate action, intervention, destination or time of cut.
    """
    result = {'state': 'unknown', 'reason': 'protected qualification unavailable',
              'selection_rule': SELECTION_RULE, 'calibration': None}
    if not isinstance(protected_input, dict):
        return result
    try:
        if protected_input['selection_rule'] != SELECTION_RULE:
            raise ValueError('unsupported selection rule')
        contacts = snapshot['contacts']['by_object']
        touched = [key for key, value in contacts.items() if value['hand_contact']]
        held = [key for key, value in contacts.items() if value['bilateral_force_bearing']]
        if len(touched) != 1 or touched != held:
            raise ValueError('snapshot lacks one unique bilateral payload')
        identity = held[0]
        observed = snapshot['physical_class_observation']
        if observed.get('export_state') != 'pass':
            raise ValueError('source-bound class observation unavailable')
        objects = [obj for obj in snapshot['geometry']['objects'] if obj['id'] == identity]
        rows = [obj for obj in observed['objects'] if obj['id'] == identity]
        if len(objects) != 1 or len(rows) != 1:
            raise ValueError('unique payload identity missing from protected observations')
        template_key = str(objects[0]['kind']) + ':' + str(objects[0]['family'])
        if template_key != str(rows[0]['kind']) + ':' + str(rows[0]['family']):
            raise ValueError('payload identity differs between protected observations')
        mapped = protected_input['payload_template_to_cell'].get(template_key)
        if mapped is None:
            raise ValueError('payload template has no frozen measured cell')
        calibration = protected_input['calibration_by_template'][template_key]
        template = protected_input['qualification_context']['bundle']['class_spec']['templates'][template_key]
        if rows[0].get('template_sha256') != digest(template):
            raise ValueError('observed payload template differs from the frozen class')
        if (calibration['grip']['qualification_cell_id'] != mapped
                or len(calibration['routes']) != 1 or calibration['routes'][0]['qualification_cell_id'] != mapped):
            raise ValueError('grip and route do not use the exact frozen mapped cell')
        result.update(state='pass', reason='unique payload selects its frozen measured cell',
                      object_id=identity, payload_template=template_key, payload_template_sha256=digest(template),
                      qualification_cell_id=mapped, calibration=json.loads(json.dumps(calibration)))
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        result['reason'] = str(error)
    return result


def absence_observation(start, end, endpoint, settings=None):
    """Append-only duration facts. A ready worker need not have admitted recovery."""
    result = {'schema_version': 'restart-absence-observation-1', 'observed_endpoint': endpoint,
              'start': start, 'end': end, 'wall_duration_s': None, 'simulation_duration_s': None,
              'coverage': {'state': 'unknown', 'reason': 'qualification settings unavailable'},
              'physical_recovery_success': 'not_assessed'}
    if (not isinstance(start, dict) or not isinstance(end, dict) or any(not finite(record.get(key))
            for record in (start, end) for key in ('wall_s', 'sim_s'))):
        result['coverage']['reason'] = 'absence clock landmark missing/nonfinite'
        return result
    wall, sim = end['wall_s'] - start['wall_s'], end['sim_s'] - start['sim_s']
    if wall < 0 or sim < 0:
        result['coverage']['reason'] = 'absence clock landmarks are reversed'
        return result
    result.update(wall_duration_s=wall, simulation_duration_s=sim)
    if not isinstance(settings, dict):
        return result
    required = settings.get('absence_endpoint'); timebase = settings.get('absence_timebase')
    result.update(qualified_endpoint=required, qualified_timebase=timebase)
    if required not in ENDPOINTS or timebase not in TIMEBASES:
        result['coverage']['reason'] = 'unsupported qualification clock/endpoint'
        return result
    measured = sim if timebase == 'simulation' else wall
    coverage = actual_absence_coverage(measured, settings.get('prospective_absence_bound_s'))
    if endpoint != required:
        result['coverage'] = {'state': 'unknown', 'reason': 'qualified endpoint has not been observed',
                              'observed_elapsed_lower_bound_s': measured, 'elapsed_bound_check': coverage}
    else:
        result['coverage'] = coverage
    return result


def first_control_endpoint(action, feedback, *, incarnation, expected_destination):
    """Classify a post-restart admission without changing it or waiting for success.

    Passive observations/waits do not end the guarded hold. The first other
    admitted action ends this measurement opportunity, even if it is a different
    recovery destination or control operation. Later actions cannot repair it.
    """
    if (not isinstance(action, dict) or not isinstance(feedback, dict)
            or feedback.get('status') != 'accepted' or feedback.get('duplicate_suppressed')
            or action.get('incarnation') != incarnation):
        return None
    op = action.get('operation')
    if op in ('wait', 'help', 'done') or (op == 'observe' and action.get('clear_view') is not True):
        return None
    matches = op == 'recover_held' and isinstance(expected_destination, str) and action.get('destination') == expected_destination
    return {'endpoint': 'recover_held_admitted' if matches else 'other_control_admitted',
            'operation': op, 'destination': action.get('destination'), 'request_id': action.get('request_id'),
            'route_scope_matches': matches, 'physical_recovery_success': 'not_assessed'}
