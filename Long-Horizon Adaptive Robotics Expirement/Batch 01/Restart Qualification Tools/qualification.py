"""Opt-in prior measured-cell identity for the unchanged physical predicates.

No evidence file is read here; the protected operator verifies artifact bytes.
Compatibility never supplies grip/route/absence limits. No default qualification,
trial count, readiness result, seed generation or candidate decision is present.
"""
from __future__ import annotations

from datetime import datetime, timezone

from compatibility import digest, finite, sha, verify_class_compatibility
from descriptor import EXPORT_SCHEMA

QUALIFICATION_SCHEMA = 'prior-restart-class-qualification-1'


def _utc(value):
    if not isinstance(value, str):
        raise ValueError('timestamp missing')
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('timestamp lacks timezone')
    return stamp.astimezone(timezone.utc)


def qualified_entry_identity(entry, snapshot, context):
    """Return pass/fail/unknown for one previously measured cell identity.

    context is independently supplied by the protected release loader:
      {bundle, frozen_bundle_sha256, frozen_class_sha256, freeze_utc,
       prospective_absence_bound_s, verified_artifacts: {artifact_id: sha256}}
    The expected hashes must not be copied from the untrusted entry/bundle.
    Existing _grip/_route retain all their actual-state numerical checks.
    """
    def result(state, reason, **details):
        return {'state': state, 'reason': reason, 'evidence_basis': 'empirical_transfer',
                'instance_previously_calibrated': False, 'physical_state_predicates_evaluated': False,
                **details}
    try:
        if not isinstance(context, dict) or not isinstance(entry, dict) or not isinstance(snapshot, dict):
            return result('unknown', 'independent protected qualification context missing')
        bundle = context.get('bundle')
        if not isinstance(bundle, dict) or bundle.get('schema_version') != QUALIFICATION_SCHEMA:
            return result('unknown', 'unsupported/missing qualification bundle')
        if not sha(context.get('frozen_bundle_sha256')) or not sha(context.get('frozen_class_sha256')):
            return result('unknown', 'independently frozen qualification/class identity absent')
        if digest(bundle) != context['frozen_bundle_sha256']:
            return result('fail', 'qualification bundle differs from release freeze')
        observation = snapshot.get('physical_class_observation')
        if (not isinstance(observation, dict) or observation.get('export_schema') != EXPORT_SCHEMA
                or observation.get('export_state') != 'pass'
                or not sha(observation.get('compile_seal_sha256'))
                or not sha(observation.get('compiled_surface_sha256'))):
            return result('unknown', 'source-bound protected compiled observation unavailable')
        if any(observation.get(k) != snapshot.get(k) for k in ('physical_configuration_sha256', 'scene_xml_sha256')):
            return result('fail', 'class observation belongs to a different physical snapshot')
        sources = snapshot.get('source_hashes')
        if not isinstance(sources, dict) or not sources:
            return result('unknown', 'snapshot source identities missing')
        if any(observation.get('source_hashes', {}).get(k) != v for k, v in sources.items()):
            return result('fail', 'class observation and state capture source identities differ')
        identities = sorted(row['id'] for row in observation.get('objects', []))
        if identities != sorted(snapshot.get('expected_object_ids', [])) or identities != sorted(row['id'] for row in snapshot.get('geometry', {}).get('objects', [])):
            return result('fail', 'class observation and state capture object inventories differ')
        compatibility = verify_class_compatibility(bundle.get('class_spec'), observation,
                                                    frozen_spec_sha256=context['frozen_class_sha256'])
        if compatibility['compatibility_state'] != 'pass':
            return result(compatibility['compatibility_state'], 'physical class/domain not matched', compatibility=compatibility)
        if bundle.get('status') != 'measured_development' or not isinstance(bundle.get('empirical_transfer_rule'), str) or not bundle['empirical_transfer_rule'].strip():
            return result('unknown', 'no supported prefreeze empirical-transfer rule')
        freeze = _utc(context.get('freeze_utc'))
        if not _utc(bundle.get('accepted_at_utc')) < freeze:
            return result('unknown', 'qualification acceptance does not predate release freeze')
        cells = bundle.get('cells')
        if not isinstance(cells, list) or not cells or any(not isinstance(c, dict) or not isinstance(c.get('cell_id'), str) for c in cells):
            return result('unknown', 'measured cells absent/malformed')
        if len({c['cell_id'] for c in cells}) != len(cells):
            return result('unknown', 'ambiguous duplicate cell identities')
        matches = [c for c in cells if c['cell_id'] == entry.get('qualification_cell_id')]
        if len(matches) != 1:
            return result('unknown', 'entry does not name one frozen measured cell')
        cell = matches[0]
        role = entry.get('qualification_role')
        if role not in ('grip', 'route') or entry.get('envelope') != cell.get(role + '_envelope'):
            return result('fail', 'entry envelope is not the frozen measured cell envelope')
        if not isinstance(cell.get('grip_envelope'), dict) or not isinstance(cell.get('route_envelope'), dict):
            return result('unknown', 'one joint grip/route cell is required')
        grip, route = cell['grip_envelope'], cell['route_envelope']
        if (grip.get('kind'), grip.get('family')) != (route.get('payload_kind'), route.get('payload_family')):
            return result('fail', 'grip and route belong to different payload templates')
        template_key = str(grip.get('kind')) + ':' + str(grip.get('family'))
        template = bundle['class_spec'].get('templates', {}).get(template_key)
        if template is None or not sha(cell.get('payload_template_sha256')) or digest(template) != cell['payload_template_sha256']:
            return result('unknown', 'measured payload template is unsupported')
        if cell.get('envelope_basis') != 'measured_before_this_intervention':
            return result('unknown', 'cell does not declare prior measured support')
        # Joint cell/route support must be documented; this verifier does not
        # pretend a set of unrelated marginal extrema proves a state box.
        for key in ('measured_state_cell_basis', 'source_scope', 'route_coverage_method', 'untested_combinations'):
            if not isinstance(cell.get(key), str) or not cell[key].strip():
                return result('unknown', 'missing measured scope/support: ' + key)
        coverage = cell.get('route_sampling_clearance_allowance_m')
        if not finite(coverage) or coverage < 0:
            return result('unknown', 'measured route sampling/clearance allowance absent')
        absence, proposed = cell.get('maximum_qualified_absence_s'), context.get('prospective_absence_bound_s')
        if not finite(absence) or absence <= 0 or not finite(proposed) or proposed <= 0:
            return result('unknown', 'measured and prospective absence bounds are required')
        if proposed > absence:
            return result('unknown', 'prospective absence exceeds this measured cell support')
        points = cell.get('measured_points')
        if not isinstance(points, list) or not points or any(not isinstance(p, dict) or
                any(not sha(p.get(key)) for key in ('snapshot_sha256', 'physical_configuration_sha256', 'physical_class_observation_sha256')) for p in points):
            return result('unknown', 'actual measured state/physical-property point references missing')
        verified, references = context.get('verified_artifacts'), cell.get('evidence_refs')
        if not isinstance(verified, dict) or not isinstance(references, list) or not references:
            return result('unknown', 'independently verified prior physical artifacts absent')
        purposes = set()
        for ref in references:
            if (not isinstance(ref, dict) or ref.get('kind') != 'prior_physical_calibration'
                    or not isinstance(ref.get('artifact_id'), str) or not sha(ref.get('sha256'))
                    or verified.get(ref['artifact_id']) != ref['sha256']
                    or ref.get('bytes_verified_by_operator') is not True
                    or not _utc(ref.get('recorded_at_utc')) < freeze):
                return result('unknown', 'artifact bytes/identity/prior timing not independently verified')
            if not isinstance(ref.get('supports'), list):
                return result('unknown', 'artifact support scope missing')
            purposes.update(ref['supports'])
        if not {'carry_state', 'absence_survival', 'whole_arm_payload_route', 'settled_placement', 'development_validation'} <= purposes:
            return result('unknown', 'required physical facts lack retained evidence')
        if entry.get('evidence_refs') != references:
            return result('fail', 'entry artifact references differ from its measured cell')
        phase = snapshot.get('exposure', {}).get('actual_cut')
        if phase != 'closed_grip_transfer':
            return result('unknown', 'this measured carry cell does not qualify other cut families')
        return result('pass', 'matched prior measured cell; unchanged grip/route predicates still required',
                      class_spec_sha256=context['frozen_class_sha256'], qualification_sha256=context['frozen_bundle_sha256'],
                      cell_id=cell['cell_id'], maximum_qualified_absence_s=absence,
                      prospective_absence_bound_s=proposed, actual_absence_coverage='not_yet_observed')
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        return result('unknown', 'incomplete/nonfinite qualification evidence: ' + str(error))


def actual_absence_coverage(actual_absence_s, prospective_bound_s):
    """Post-cut duration fact only; never use final task success as coverage."""
    if not finite(actual_absence_s) or actual_absence_s < 0 or not finite(prospective_bound_s) or prospective_bound_s <= 0:
        return {'state': 'unknown', 'reason': 'actual/prospective absence evidence unavailable'}
    return {'state': 'pass' if actual_absence_s <= prospective_bound_s else 'unknown',
            'actual_absence_s': actual_absence_s, 'prospective_absence_bound_s': prospective_bound_s,
            'reason': 'duration covered' if actual_absence_s <= prospective_bound_s else 'actual absence exceeded prospective qualification'}
