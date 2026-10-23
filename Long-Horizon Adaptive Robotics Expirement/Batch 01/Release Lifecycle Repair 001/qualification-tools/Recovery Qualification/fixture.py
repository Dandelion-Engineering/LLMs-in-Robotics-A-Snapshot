"""Pure prospective fixture rules; no MuJoCo imports, execution or seed search."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

SCHEMA = 'recovery-development-screen-1'
POINTS = ((.09, 1.1), (.09, 1.3), (.11, 1.1), (.11, 1.3), (.10, 1.2))
VALIDATION_SEEDS = {'parking2': (907301, 907302, 907303, 907304, 907305, 907306),
                    'parking1': (907311, 907312, 907313, 907314, 907315, 907316)}
PHYSICAL_SNAPSHOT_SOURCES = ('cell.py', 'actuation.py', 'evaluator.py', 'sensor_worker.py')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def expected_payload(n, family):
    return min(f'{"A" if i % 2 == 0 else "B"}{i + 1}' for i in range(n)
               if ('A' if i % 2 == 0 else 'B') == family)


def declared_plan():
    trials = []
    for destination in ('parking2', 'parking1'):
        for family in ('A', 'B'):
            for index, (mass, friction) in enumerate(POINTS, 1):
                trials.append({'id': f'{destination}-corner-{family}-{index}', 'destination': destination,
                    'population': 10, 'family': family, 'fixture': 'construction', 'world_seed': 901001,
                    'layout_seed': 901001, 'noise_seed': 0, 'main_geom_mass_kg': mass,
                    'main_geom_sliding_friction': friction, 'expected_payload_id': expected_payload(10, family)})
        for n in (3, 6):
            for family in ('A', 'B'):
                trials.append({'id': f'{destination}-center-n{n}-{family}', 'destination': destination,
                    'population': n, 'family': family, 'fixture': 'construction', 'world_seed': 901001,
                    'layout_seed': 901001, 'noise_seed': 0, 'main_geom_mass_kg': .10,
                    'main_geom_sliding_friction': 1.2, 'expected_payload_id': expected_payload(n, family)})
        for index, (n, family) in enumerate((n, family) for n in (3, 6, 10) for family in ('A', 'B')):
            seed = VALIDATION_SEEDS[destination][index]
            trials.append({'id': f'{destination}-validation-n{n}-{family}', 'destination': destination,
                'population': n, 'family': family, 'fixture': 'independent_generator', 'world_seed': seed,
                'layout_seed': seed, 'noise_seed': 0, 'main_geom_mass_kg': None,
                'main_geom_sliding_friction': None, 'expected_payload_id': None})
    return {'schema_version': SCHEMA, 'stage': 'development_only', 'trials': trials,
        'absence_s': 5., 'simulation_cap_s': 180., 'child_hard_cap_s': 240.,
        'geometry_interval_s': .02, 'construction_nonpayload_main_geom_mass_kg': .10,
        'construction_nonpayload_main_geom_sliding_friction': 1.2,
        'construction_world_and_layout_seed': 901001,
        'cut': {'phase_in': [4, 5], 'public_tcp_z_gte_m': .08, 'payload_center_z_gt_m': .075,
                'payload_bottom_clearance_gt_m': 0., 'requires_bilateral_force_bearing': True,
                'jaw_width_open_interval_m': [.005, .065], 'requires_gripper_contact': True,
                'timeout_s': 75., 'basis': 'first public restart-height opportunity with independent bilateral grip and payload clearance; differs from earlier lower-TCP primitive cuts'},
        'public_selection': 'lexically first fresh image-derived visible raw workpiece in the requested family and raw zone',
        'boundary_scope': 'Exact .11 kg or 1.3 friction fixtures lie outside the half-open generator domain; they remain development physics trials only.',
        'runtime_binding': 'All executable/helper/robot-asset bytes are bound in the immutable queued parent manifest before any child.',
        'qualification_claimed': False, 'swept_envelopes_inferred': False,
        'absence_status': 'declared initial engineering trial; not an established duration guarantee'}


def validate_plan(value):
    # A changed design needs a new fixture version rather than an unnoticed CLI sweep.
    if value != declared_plan():
        raise ValueError('Plan differs from the fixed prospective forty-trial declaration')
    return value


def generator_domain(mass, friction):
    return .09 <= mass < .11 and 1.1 <= friction < 1.3


def construct_xml(xml, registry, trial):
    """Modify only declared main-geom mass/friction before model compilation."""
    tree = ET.fromstring(xml)
    before = hashlib.sha256(xml.encode()).hexdigest()
    originals = {}
    for identity in sorted(registry):
        geom = tree.find(f'.//geom[@name="part_{identity}"]')
        if geom is None:
            raise ValueError('Missing semantic main geom: ' + identity)
        originals[identity] = {'mass_kg': float(geom.attrib['mass']),
                               'friction': [float(v) for v in geom.attrib['friction'].split()]}
    if trial['fixture'] == 'construction':
        target = trial['expected_payload_id']
        if target not in registry or registry[target]['family'] != trial['family'] or registry[target]['kind'] != 'part':
            raise ValueError('Declared construction payload is absent or wrong family')
        for identity in sorted(registry):
            geom = tree.find(f'.//geom[@name="part_{identity}"]')
            mass = trial['main_geom_mass_kg'] if identity == target else .10
            friction = trial['main_geom_sliding_friction'] if identity == target else 1.2
            other = geom.attrib['friction'].split()[1:]
            if len(other) != 2:
                raise ValueError('Expected original three-component friction')
            geom.set('mass', repr(mass))
            geom.set('friction', ' '.join([repr(friction), *other]))
        result = ET.tostring(tree, encoding='unicode')
    elif trial['fixture'] == 'independent_generator':
        result = xml  # Preserve the generator's complete bytes and sampled scene.
    else:
        raise ValueError('Unknown fixture kind')
    actual = {}
    root = ET.fromstring(result)
    for identity in sorted(registry):
        geom = root.find(f'.//geom[@name="part_{identity}"]')
        mass = float(geom.attrib['mass'])
        friction = [float(v) for v in geom.attrib['friction'].split()]
        actual[identity] = {'main_geom_mass_kg': mass, 'main_geom_friction': friction,
            'generator_half_open_domain_member': generator_domain(mass, friction[0]),
            'main_geom_is_not_complete_body_mass': True}
    return result, {'generator_xml_sha256': before, 'fixture_xml_sha256': hashlib.sha256(result.encode()).hexdigest(),
        'original_generator_properties': originals, 'realized_xml_properties': actual,
        'changes_occur_before_compile_and_settle': True, 'runtime_source_modified': False,
        'post_compile_object_state_writes': 0, 'trial': trial}


def select_public(detections, family, capture_age_s):
    if not isinstance(capture_age_s, (int, float)) or not math.isfinite(capture_age_s) or not 0 <= capture_age_s <= .35:
        raise ValueError('Fresh image-derived capture is required')
    visible = sorted(d['id'] for d in detections if d.get('kind') == 'part' and d.get('family') == family
                     and d.get('visible_mark') == 'raw' and d.get('zone') == 'raw')
    if not visible:
        raise ValueError('No fresh public raw workpiece of requested family')
    return visible[0]


def retained_hold_check(snapshot, part_id):
    item = next((o for o in snapshot['objects'] if o['id'] == part_id), None)
    return bool(item and item.get('gripper_contact') and item['position'][2] > .075)


def physical_snapshot_sources(full_source_hashes, runtime_dir):
    """Match shared capture identity keys; the complete archive stays separate."""
    return {name: full_source_hashes[str((Path(runtime_dir) / name).resolve())]
            for name in PHYSICAL_SNAPSHOT_SOURCES}


def physical_trial_pass(*, held_at_absence_end, all_absence_tick_hold_checks_pass, placement_passed):
    return (held_at_absence_end is True and all_absence_tick_hold_checks_pass is True
            and placement_passed is True)


def cut_eligible(snapshot, part_id, *, phase, tcp_z, jaw_width, bilateral):
    item = next((o for o in snapshot['objects'] if o['id'] == part_id), None)
    return bool(phase in (4, 5) and math.isfinite(tcp_z) and tcp_z >= .08
                and .005 < jaw_width < .065 and bilateral is True
                and retained_hold_check(snapshot, part_id) and item['bounds']['min'][2] > 0.)


def transformed_box(local_center, local_half, position, rotation):
    center = [position[i] + sum(rotation[i][j] * local_center[j] for j in range(3)) for i in range(3)]
    extent = [sum(abs(rotation[i][j]) * local_half[j] for j in range(3)) for i in range(3)]
    return {'min': [a - b for a, b in zip(center, extent)], 'max': [a + b for a, b in zip(center, extent)]}


class SamplingGaps:
    def __init__(self):
        self.count = 0
        self.first = self.last = None
        self.maximum_sim_s = self.maximum_wall_s = None

    def record(self, sim, wall):
        if not all(math.isfinite(v) for v in (sim, wall)):
            raise ValueError('Nonfinite sampling clock')
        if self.last is not None:
            ds, dw = sim - self.last[0], wall - self.last[1]
            if ds < 0 or dw < 0:
                raise ValueError('Geometry sampling clock reversed')
            self.maximum_sim_s = max(self.maximum_sim_s or 0., ds)
            self.maximum_wall_s = max(self.maximum_wall_s or 0., dw)
        if self.first is None:
            self.first = [sim, wall]
        self.last = [sim, wall]
        self.count += 1

    def report(self):
        return {'sample_count': self.count, 'first_sim_wall_s': self.first, 'last_sim_wall_s': self.last,
                'maximum_sim_gap_s': self.maximum_sim_s, 'maximum_wall_gap_s': self.maximum_wall_s,
                'continuous_sweep_error_bound_m': None, 'bound_missing_reason': 'Raw geometry only; no between-sample sweep bound has been derived.'}
