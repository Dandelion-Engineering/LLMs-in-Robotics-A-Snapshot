"""Fixed A-only raw-to-fixture profiles; no native imports or seed search."""
from __future__ import annotations

import copy
import math

SCHEMA = 'recovery-development-screen-1'
PROFILE_REVISION = 'raw-fixture-profile-screen-1'
HIGH = {'clearance': .25, 'speed_scale': 1., 'approach': 'vertical', 'avoid_zones': []}
BASELINE = {'clearance': .16, 'speed_scale': .8, 'approach': 'vertical', 'avoid_zones': []}
POINTS = ((.09, 1.1), (.09, 1.3), (.11, 1.1), (.11, 1.3), (.10, 1.2))
VALIDATION_SEEDS = ((3, 931301), (6, 931302), (10, 931303))


def declared_plan():
    trials = []
    def row(identity, population, fixture, seed, mass, friction, profile, role):
        return {'id': identity, 'destination': 'parking1', 'population': population,
            'family': 'A', 'fixture': fixture, 'world_seed': seed, 'layout_seed': seed,
            'noise_seed': 0, 'main_geom_mass_kg': mass, 'main_geom_sliding_friction': friction,
            'expected_payload_id': 'A1', 'transport_destination': 'fixture',
            'transport_objective': copy.deepcopy(HIGH if profile == 'high' else BASELINE),
            'transport_profile': profile, 'evidence_role': role}
    for index, (mass, friction) in enumerate(POINTS, 1):
        trials.append(row(f'parking1-high-corner-A-{index}', 10, 'construction', 931201,
                          mass, friction, 'high', 'cell_construction'))
    for n in (3, 6):
        trials.append(row(f'parking1-high-center-n{n}-A', n, 'construction', 931201,
                          .10, 1.2, 'high', 'cell_construction'))
    # The same three complete independent worlds compare profiles; they are
    # three worlds, not six independent worlds. Neither profile fits a rule here.
    for n, seed in VALIDATION_SEEDS:
        for profile, role in (('high', 'core_validation'), ('baseline', 'baseline_transfer_check')):
            trials.append(row(f'parking1-{profile}-validation-n{n}-A', n,
                              'independent_generator', seed, None, None, profile, role))
    return {'schema_version': SCHEMA, 'profile_revision': PROFILE_REVISION,
        'stage': 'development_only', 'trials': trials,
        'absence_s': 5., 'simulation_cap_s': 180., 'child_hard_cap_s': 240.,
        'geometry_interval_s': .02,
        'construction_nonpayload_main_geom_mass_kg': .10,
        'construction_nonpayload_main_geom_sliding_friction': 1.2,
        'construction_world_and_layout_seed': 931201,
        'cut': {'phase_in': [4, 5], 'public_tcp_z_gte_m': .08,
            'jaw_width_lt_m': .065, 'timeout_s': 75.,
            'basis': 'first public milestone of the selected first raw transport; no protected grip, pose, route or classifier gating',
            'observation_cadence': 'every ordinary physical-loop tick; runtime supervisor may batch up to 50 ticks, so exact cut-state equivalence is not asserted'},
        'public_selection': 'lexically first fresh image-derived visible raw A workpiece in raw zone, required to be A1; no protected substitution',
        'boundary_scope': 'Exact .11 kg or 1.3 friction fixtures are outside the half-open generator domain; retain as development physical boundary trials only.',
        'runtime_binding': 'All executable/helper/robot-asset bytes are bound in the immutable queued parent manifest before any child.',
        'qualification_claimed': False, 'swept_envelopes_inferred': False,
        'absence_status': 'Five simulation seconds requested; actual before-cancel to admission clocks measured independently; no established duration guarantee.',
        'fixed_rule_policy': 'Only high-profile construction may derive the A-only rule. All six validation/transfer rows consume that same predeclared rule unchanged. No baseline widening or union.',
        'validation_world_count': 3,
        'supported_payload_template_proposal': 'part:A',
        'unsupported_scope': ['part:B and inserts as held payloads', 'other raw/source slots',
            'clearance .08 / speed .3', 'unmeasured intermediate objectives', 'unmatched joint/grip/route starts'],
        'existing_baseline_competence': 'C0-012 remains retained task competence evidence; this is a separate carry-coverage check.'}


def validate_plan(value):
    if value != declared_plan():
        raise ValueError('Plan differs from the fixed prospective thirteen-trial profile declaration')
    return value


def transport_action(trial, part_id):
    return {'operation': 'transport', 'part_id': part_id,
            'destination': trial['transport_destination'],
            'objective': copy.deepcopy(trial['transport_objective'])}


def public_cut_matches(active_request, segment, request_id, *, width, tcp_z):
    """Public milestone only; there is deliberately no snapshot argument."""
    finite = lambda x: type(x) in (int, float) and math.isfinite(x)
    return bool(isinstance(active_request, dict) and active_request.get('request_id') == request_id
        and active_request.get('operation') == 'transport' and isinstance(segment, dict)
        and segment.get('phase') in (4, 5) and finite(width) and 0 <= width < .065
        and finite(tcp_z) and tcp_z >= .08)


def profile_rule_identity(rule):
    """Reject broader/template-substituted launch rules; not physical acceptance."""
    mapping, cells = rule.get('payload_template_to_cell'), rule.get('cells')
    if (not isinstance(mapping, dict) or set(mapping) != {'part:A'}
            or not isinstance(cells, list) or len(cells) != 1
            or not isinstance(cells[0], dict) or not isinstance(mapping['part:A'], str)
            or cells[0].get('cell_id') != mapping['part:A']):
        raise ValueError('Profile screen requires exactly one part:A cell; B remains unknown')
    cell = cells[0]
    if (cell.get('grip_envelope', {}).get('kind') != 'part'
            or cell.get('grip_envelope', {}).get('family') != 'A'
            or cell.get('route_envelope', {}).get('payload_kind') != 'part'
            or cell.get('route_envelope', {}).get('payload_family') != 'A'
            or cell.get('route_envelope', {}).get('destination') != 'parking1'):
        raise ValueError('Profile rule must retain part:A recovery to parking1')
    return rule
