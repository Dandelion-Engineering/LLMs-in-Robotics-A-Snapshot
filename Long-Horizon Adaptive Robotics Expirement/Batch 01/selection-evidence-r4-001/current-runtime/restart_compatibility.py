"""Protected physical-class compatibility only; no recovery authorization.

Stdlib, no simulator import, filesystem access, seed generation or execution.
Inputs must come from a frozen protected exporter, never a candidate. The
exporter's coverage of compiled physical settings remains an integration duty.
An in-domain instance is not thereby measured, gripped, clear, or recoverable.
"""
from __future__ import annotations

import hashlib
import json
import math
import re


SPEC_SCHEMA = 'restart-physical-class-compatibility-1'
OBS_SCHEMA = 'restart-physical-class-observation-1'
COMPONENTS = frozenset({
    'robot_geometry_and_joints', 'native_actuators', 'fixed_static_geometry',
    'contact_solver_and_integration', 'recovery_controller',
    'perception_and_registry', 'compiled_canonicalization_rules',
})
TEMPLATES = frozenset({'part:A', 'part:B', 'insert:A', 'insert:B'})
# Serialization/compiled roundoff only. These do not enlarge grip/route limits.
ABS_NUMERIC_TOLERANCE = 1e-10
REL_NUMERIC_TOLERANCE = 1e-9


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
        allow_nan=False, separators=(',', ':')).encode('ascii')).hexdigest()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def vector(value, length=3):
    return isinstance(value, list) and len(value) == length and all(finite(v) for v in value)


def close(left, right):
    return math.isclose(left, right, rel_tol=REL_NUMERIC_TOLERANCE,
                        abs_tol=ABS_NUMERIC_TOLERANCE)


def box_aggregate(template, main_mass):
    """Mass, COM and full body-frame inertia for this declared box-only template.

    Only one box mass may vary. Rotated/non-box elements are deliberately
    unsupported; an exporter must not silently coerce them into this rule.
    Every other template property remains bound by the template's exact digest.
    """
    if not finite(main_mass) or main_mass <= 0:
        raise ValueError('invalid sampled main-geom mass')
    if not isinstance(template, dict) or template.get('inertia_rule') != 'axis-aligned-box-aggregate-1':
        raise ValueError('unsupported inertia construction rule')
    boxes = template.get('mass_boxes')
    if not isinstance(boxes, list) or not boxes:
        raise ValueError('missing mass-contributing boxes')
    parts, variable_count = [], 0
    for box in boxes:
        if not isinstance(box, dict) or set(box) != {'half_size_m', 'position_m', 'mass_kg'}:
            raise ValueError('box rule has missing or unexplained fields')
        half, position, mass = box['half_size_m'], box['position_m'], box['mass_kg']
        if not vector(half) or any(v <= 0 for v in half) or not vector(position):
            raise ValueError('invalid axis-aligned box geometry')
        if mass == 'sampled_main_geom_mass':
            variable_count += 1
            mass = main_mass
        if not finite(mass) or mass <= 0:
            raise ValueError('invalid fixed geom mass')
        parts.append((mass, half, position))
    if variable_count != 1:
        raise ValueError('exactly one sampled main-geom mass is required')
    total = sum(m for m, _, _ in parts)
    com = [sum(m * p[i] for m, _, p in parts) / total for i in range(3)]
    inertia = [[0.0] * 3 for _ in range(3)]
    for mass, half, position in parts:
        offset = [position[i] - com[i] for i in range(3)]
        square = sum(v * v for v in offset)
        for i in range(3):
            for j in range(3):
                inertia[i][j] += mass * ((square if i == j else 0.0) - offset[i] * offset[j])
            inertia[i][i] += mass / 3.0 * sum(half[j] ** 2 for j in range(3) if j != i)
    return {'mass_kg': total, 'center_of_mass_body_m': com, 'inertia_tensor_body_kg_m2': inertia}


def interval_state(value, interval):
    if not finite(value):
        return 'unknown', 'nonfinite or missing realized parameter'
    if (not isinstance(interval, dict) or set(interval) != {'min', 'max', 'max_exclusive'}
            or not finite(interval['min']) or not finite(interval['max'])
            or interval['min'] <= 0 or interval['min'] >= interval['max']
            or type(interval['max_exclusive']) is not bool):
        return 'unknown', 'malformed frozen generator interval'
    inside = interval['min'] <= value and (value < interval['max'] if interval['max_exclusive'] else value <= interval['max'])
    return ('pass', 'within declared generator domain; not measured range') if inside else ('fail', 'realized value outside declared generator domain')


def verify_class_compatibility(spec, observation, *, frozen_spec_sha256):
    """Compare protected exported instance with the exact release-bound class.

    Returns pass/fail/unknown for compatibility, NEVER physical admissibility.
    The caller verifies exporter/source/artifact bytes and supplies this class's
    expected digest from the release freeze, not from the observation itself.
    Missing/malformed evidence is unknown; known contradictions are failures.
    Exact instance hashes are retained but are intentionally not class keys.
    """
    predicates = []

    def add(name, state, reason, observed=None):
        predicates.append({'name': name, 'state': state, 'reason': reason, 'observed': observed})

    def result():
        state = ('fail' if any(p['state'] == 'fail' for p in predicates) else
                 'unknown' if any(p['state'] == 'unknown' for p in predicates) else 'pass')
        return {'schema_version': SPEC_SCHEMA + '-assessment', 'audience': 'protected operator/evaluator only',
                'compatibility_state': state, 'predicates': predicates,
                'class_spec_sha256': frozen_spec_sha256,
                'exact_physical_configuration_sha256': observation.get('physical_configuration_sha256') if isinstance(observation, dict) else None,
                'scene_xml_sha256': observation.get('scene_xml_sha256') if isinstance(observation, dict) else None,
                'evidence_basis': 'frozen class/domain compatibility; no physical calibration inferred',
                'instance_previously_calibrated': None, 'recovery_admissibility': 'not_assessed',
                'safety_predicates_evaluated': False,
                'effects': {'authorize_restart': False, 'exclude_paired_block': False,
                            'change_candidate_information': False, 'generate_seed': False}}

    if not isinstance(spec, dict) or not isinstance(observation, dict):
        add('input_structure', 'unknown', 'class and observation must be objects')
        return result()
    try:
        actual_spec_hash = digest(spec)
        digest(observation)  # Reject nonfinite or non-JSON evidence anywhere.
    except (TypeError, ValueError, OverflowError):
        add('finite_json', 'unknown', 'input contains nonfinite or non-JSON evidence')
        return result()
    if not sha(frozen_spec_sha256):
        add('release_binding', 'unknown', 'release-bound class digest missing or malformed')
        return result()
    if actual_spec_hash != frozen_spec_sha256:
        add('release_binding', 'fail', 'class differs from the release-bound descriptor')
        return result()
    add('release_binding', 'pass', 'descriptor equals independently supplied frozen digest')
    if spec.get('schema_version') != SPEC_SCHEMA or observation.get('schema_version') != OBS_SCHEMA:
        add('schema_identity', 'unknown', 'unsupported class or observation schema')
        return result()
    for name in ('physical_configuration_sha256', 'scene_xml_sha256'):
        add(name, 'pass' if sha(observation.get(name)) else 'unknown', 'exact provenance retained; not an equality gate across instances')
    expected_sources, sources = spec.get('required_source_hashes'), observation.get('source_hashes')
    if (not isinstance(expected_sources, dict) or not expected_sources or 'descriptor_exporter' not in expected_sources
            or any(not isinstance(k, str) or not sha(v) for k, v in expected_sources.items()) or not isinstance(sources, dict)):
        add('source_identity', 'unknown', 'nonempty source identities including descriptor exporter are required')
    else:
        for key, expected in sorted(expected_sources.items()):
            actual = sources.get(key)
            add('source:' + key, 'unknown' if not sha(actual) else ('pass' if actual == expected else 'fail'),
                'protected exporter and causal source identities must match', actual)
    expected_fixed, actual_fixed = spec.get('component_sha256'), observation.get('component_sha256')
    if not isinstance(expected_fixed, dict) or set(expected_fixed) != COMPONENTS or any(not sha(v) for v in expected_fixed.values()):
        add('fixed_components', 'unknown', 'frozen class lacks the complete required component inventory')
    elif not isinstance(actual_fixed, dict):
        add('fixed_components', 'unknown', 'compiled component identity evidence absent')
    else:
        if set(actual_fixed) - COMPONENTS:
            add('fixed_component_inventory', 'fail', 'unexplained compiled component fields', sorted(set(actual_fixed) - COMPONENTS))
        for key in sorted(COMPONENTS):
            actual = actual_fixed.get(key)
            add('component:' + key, 'unknown' if not sha(actual) else ('pass' if actual == expected_fixed[key] else 'fail'),
                'exact fixed physics/controller/sensor component identity required', actual)
    domain, templates, objects = spec.get('declared_domain'), spec.get('templates'), observation.get('objects')
    if not isinstance(domain, dict) or not isinstance(templates, dict) or set(templates) != TEMPLATES:
        add('declared_domain', 'unknown', 'declared domain or four part/insert templates missing')
        return result()
    allowed, count = domain.get('allowed_part_counts'), observation.get('part_count')
    if not isinstance(allowed, list) or not allowed or any(type(n) is not int or n not in (3, 6, 10) for n in allowed) or len(set(allowed)) != len(allowed):
        add('population', 'unknown', 'invalid frozen population domain')
        return result()
    if type(count) is not int:
        add('population', 'unknown', 'actual population missing or not integer')
        return result()
    add('population', 'pass' if count in allowed else 'fail', 'declared population membership; not measured population coverage', count)
    if count not in allowed:
        return result()
    expected_ids = {f'{"A" if i % 2 == 0 else "B"}{i + 1}': ('part', 'A' if i % 2 == 0 else 'B') for i in range(count)}
    expected_ids.update({'insert_A': ('insert', 'A'), 'insert_B': ('insert', 'B')})
    if not isinstance(objects, list) or any(not isinstance(row, dict) or not isinstance(row.get('id'), str) for row in objects):
        add('object_inventory', 'unknown', 'actual semantic object inventory is malformed')
        return result()
    ids = [row['id'] for row in objects]
    if len(set(ids)) != len(ids) or set(ids) != set(expected_ids):
        add('object_inventory', 'fail', 'duplicate, missing or unrequested semantic entities', ids)
        return result()
    add('object_inventory', 'pass', 'exact family/tag registry shape and two inserts are present')
    for row in objects:
        identity = row['id']; kind, family = expected_ids[identity]
        if (row.get('kind'), row.get('family')) != (kind, family):
            add(identity + ':identity', 'fail', 'entity kind/family differs from generator')
            continue
        template = templates[kind + ':' + family]
        try:
            expected_template = digest(template)
        except (TypeError, ValueError):
            add(identity + ':template', 'unknown', 'template not canonical JSON')
            continue
        actual_template = row.get('template_sha256')
        add(identity + ':template', 'unknown' if not sha(actual_template) else ('pass' if actual_template == expected_template else 'fail'),
            'compiled semantic template must preserve all nonvarying entity fields')
        mass = row.get('main_geom_mass_kg')
        state, reason = interval_state(mass, domain.get('main_geom_mass_kg'))
        add(identity + ':main_mass', state, reason, mass)
        friction = row.get('main_geom_friction')
        if not vector(friction) or not isinstance(template, dict) or not vector(template.get('fixed_friction_tail'), 2):
            add(identity + ':friction', 'unknown', 'compiled full friction vector/template absent')
        else:
            state, reason = interval_state(friction[0], domain.get('main_geom_sliding_friction'))
            add(identity + ':sliding_friction', state, reason, friction[0])
            add(identity + ':other_friction', 'pass' if friction[1:] == template['fixed_friction_tail'] else 'fail',
                'torsional/rolling friction cannot vary silently', friction[1:])
        try:
            expected = box_aggregate(template, mass)
        except (TypeError, ValueError):
            add(identity + ':compiled_mass_properties', 'unknown', 'unsupported/missing construction evidence')
            continue
        actual = row.get('compiled_mass_properties')
        if (not isinstance(actual, dict) or set(actual) != set(expected) or not finite(actual.get('mass_kg'))
                or not vector(actual.get('center_of_mass_body_m')) or not isinstance(actual.get('inertia_tensor_body_kg_m2'), list)
                or len(actual['inertia_tensor_body_kg_m2']) != 3 or not all(vector(v) for v in actual['inertia_tensor_body_kg_m2'])):
            add(identity + ':compiled_mass_properties', 'unknown', 'complete finite compiled body-frame mass/COM/inertia required')
            continue
        values = [(actual['mass_kg'], expected['mass_kg'])]
        values += list(zip(actual['center_of_mass_body_m'], expected['center_of_mass_body_m']))
        values += [(actual['inertia_tensor_body_kg_m2'][i][j], expected['inertia_tensor_body_kg_m2'][i][j]) for i in range(3) for j in range(3)]
        add(identity + ':compiled_mass_properties', 'pass' if all(close(a, b) for a, b in values) else 'fail',
            'compiled mass, COM and full inertia must follow the frozen mass-construction rule')
    return result()
