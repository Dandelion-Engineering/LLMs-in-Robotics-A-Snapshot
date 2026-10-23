"""Small synthetic tests only; execution deferred while physical jobs run."""
import copy
import json
import math
from types import SimpleNamespace
import unittest

import materialize_profile_rule as materializer


def vector(values, count):
    return isinstance(values, list) and len(values) == count and all(type(v) in (int, float) and math.isfinite(v) for v in values)


def reference():
    return {'trial_id': 'parking1-high-corner-A-5', 'consumed_ref': {'path': 'synthetic/trial.json', 'sha256': 'c'*64},
        'measured_states_consumed_ref': {'path': 'synthetic/states.json', 'sha256': 'd'*64},
        'states': {'cut': {'source_ref': {'path': 'synthetic/events.jsonl', 'sha256': 'e'*64}, 'payload': {
            'snapshot_sha256': 'a'*64, 'physical_configuration_sha256': 'b'*64,
            'physical_class_observation': {'synthetic_only': True},
            'robot': {'joint_position_rad': [.12345678901234567, .44, -.77, -2.39, .63, 2.62, -.527],
                      'joint_velocity_rad_s': [.4691234567890123, -.454, -.588, -.128, -.622, -.265, .438]},
            'object_poses': {'A1': {'relative_to_tcp': {'rotation': [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]}}},
            'geometry': {'zones': {'parking1': {'min': [.2, -.1, 0.], 'max': [.4, .1, .1]}}}}}}}


class ProfileMaterializerTests(unittest.TestCase):
    def setUp(self):
        self.choices_path = materializer.HERE/'root-profile-choices-001.json'
        self.base_path = materializer.TOOLS/'root-provisional-choices-001.json'
        self.choices = json.loads(self.choices_path.read_bytes())
        self.base = json.loads(self.base_path.read_bytes())
        self.functions = {'vector': vector, 'proper_rotation': lambda r: r == [[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]]}

    def test_prospective_choices_bind_old_fixed_allowances_and_reject_tampering(self):
        identity = materializer.shared.file_ref(self.choices_path)
        base_identity = materializer.shared.file_ref(self.base_path)
        materializer.validate_choices(self.choices, identity, self.base, base_identity)
        changed = copy.deepcopy(self.choices); changed['unchanged_A1_policy']['joint_start_half_width_rad'] = .031
        with self.assertRaisesRegex(ValueError, 'allowance changed'):
            materializer.validate_choices(changed, identity, self.base, base_identity)
        with self.assertRaisesRegex(ValueError, 'choice bytes changed'):
            materializer.validate_choices(self.choices, {**identity, 'sha256': '0'*64}, self.base, base_identity)

    def test_exact_one_reference_tuple_and_rotation_no_mutation_or_widening(self):
        ref = reference(); before = copy.deepcopy((self.base, self.choices, ref))
        resolved = materializer.resolved_choices(self.choices, self.base, ref, self.functions)
        selected = resolved['cell_choices']['A1']; snapshot = ref['states']['cut']['payload']
        self.assertEqual(selected['joint_start_center_rad'], snapshot['robot']['joint_position_rad'])
        self.assertEqual(selected['joint_velocity_center_rad_s'], snapshot['robot']['joint_velocity_rad_s'])
        self.assertEqual(set(resolved['cell_choices']), {'A1'})
        for key, value in self.choices['unchanged_A1_policy'].items():self.assertEqual(selected[key], value)
        corridors = [{'min': [.1, .2, .3], 'max': [.4, .5, .6]}]
        cell = materializer.shared.make_cell(resolved, 'parking1', 'A1', {'templates': {'part:A': {'synthetic': True}}},
            ref, corridors, [materializer.shared.thin_point(ref)], {})
        self.assertEqual(cell['route_envelope']['joint_start_ranges_rad'][0],
                         [snapshot['robot']['joint_position_rad'][0]-.03, snapshot['robot']['joint_position_rad'][0]+.03])
        self.assertEqual(cell['route_envelope']['joint_velocity_ranges_rad_s'][0],
                         [snapshot['robot']['joint_velocity_rad_s'][0]-.10, snapshot['robot']['joint_velocity_rad_s'][0]+.10])
        self.assertEqual(cell['grip_envelope']['relative_rotation'], snapshot['object_poses']['A1']['relative_to_tcp']['rotation'])
        self.assertEqual(cell['route_sampling_clearance_allowance_m'], 0.)
        self.assertEqual(cell['maximum_qualified_absence_s'], 5.)
        self.assertEqual(cell['absence_timebase'], 'wall')
        self.assertEqual(cell['absence_endpoint'], 'recover_held_admitted')
        self.assertEqual((self.base, self.choices, ref), before)
        ref['trial_id'] = 'parking1-high-corner-A-1'
        with self.assertRaisesRegex(ValueError, 'Different center'):
            materializer.resolved_choices(self.choices, self.base, ref, self.functions)

    def synthetic_selection(self):
        declarations = {}
        for identity in self.choices['construction_trial_ids']:
            declarations[identity] = {'id': identity, 'destination': 'parking1', 'family': 'A', 'expected_payload_id': 'A1',
                'fixture': 'construction', 'transport_profile': 'high', 'evidence_role': 'cell_construction',
                'transport_destination': 'fixture', 'transport_objective': {'clearance': .25, 'speed_scale': 1, 'approach': 'vertical', 'avoid_zones': []}}
        for n in (3, 6, 10):
            for profile in ('high', 'baseline'):
                identity = f'parking1-{profile}-validation-n{n}-A'
                declarations[identity] = {'id': identity, 'destination': 'parking1', 'family': 'A', 'expected_payload_id': 'A1', 'fixture': 'independent_generator'}
        return SimpleNamespace(manifest={'execution_phase': 'construction', 'destination_selection': 'parking1'},
            summary={'sources_unchanged': True, 'not_started': []}, selected=list(self.choices['construction_trial_ids']),
            receipt={'started_at': '2026-09-23T13:00:00Z'}, declared=declarations,
            entries={identity: {'execution_status': 'deferred_to_other_phase' if row['fixture'] == 'independent_generator' else 'passed'}
                     for identity, row in declarations.items()})

    def test_all_seven_and_full_thirteen_declared_without_reading_validation(self):
        source = self.synthetic_selection()
        materializer.check_selection(source, self.choices)  # No trial()/artifact reader is supplied.
        source.selected.pop()
        with self.assertRaisesRegex(ValueError, 'All seven'):materializer.check_selection(source, self.choices)
        source = self.synthetic_selection(); source.entries['parking1-high-validation-n3-A']['execution_status'] = 'passed'
        with self.assertRaisesRegex(ValueError, 'untouched/deferred'):materializer.check_selection(source, self.choices)
        source = self.synthetic_selection(); source.manifest['execution_phase'] = 'validation'
        with self.assertRaisesRegex(ValueError, 'Construction-only'):materializer.check_selection(source, self.choices)
        source = self.synthetic_selection(); source.receipt['started_at'] = '2026-09-23T12:00:00Z'
        with self.assertRaisesRegex(ValueError, 'before construction'):materializer.check_selection(source, self.choices)

    def test_boundary_numeric_check_preserves_unknown_class_export(self):
        snapshot = {'capture_errors': [], 'expected_object_ids': ['A1'], 'physical_class_observation': {'export_state': 'unknown'},
            'contacts': {'by_object': {'A1': {'hand_contact': True, 'bilateral_force_bearing': True}}},
            'robot': {'joint_position_rad': [0.]*7, 'joint_velocity_rad_s': [0.]*7, 'finger_velocity_m_s': [0.,0.]},
            'geometry': {'objects': [{'id': 'A1', 'kind': 'part', 'family': 'A', 'bounds': {'min': [0.,0.,0.], 'max': [1.,1.,1.]}}],
                         'zones': {'parking1': {'min': [2.,2.,0.], 'max': [3.,3.,1.]}}}}
        calls = []
        def grip(entry, original, obj, policy):
            self.assertIs(original, snapshot);self.assertEqual(original['physical_class_observation']['export_state'], 'unknown')
            calls.append('grip');return ('pass', 'synthetic numeric only', {})
        def route(entries, original, obj, available):
            self.assertIs(original, snapshot);self.assertEqual(available, ['parking1'])
            calls.append('route');return ('pass', 'synthetic numeric only', {})
        functions = {'vector': vector, 'valid_box': lambda box: True, 'overlaps': lambda a,b: False,
            'policy': {'recovery_destinations': ['parking1']}, '_grip': grip, '_route': route}
        before = copy.deepcopy(snapshot)
        result = materializer.numerical_preflight({'cells': [{'grip_envelope': {}, 'route_envelope': {}}]}, snapshot, functions)
        self.assertEqual(result['state'], 'pass');self.assertEqual(calls, ['grip','route']);self.assertEqual(snapshot, before)
        self.assertEqual(materializer.enforce_cut(result, {'state': 'unknown'}, {'compatibility_state': 'unknown'}, False),
                         'class_excluded_numeric_preflight_pass')
        with self.assertRaisesRegex(ValueError, 'In-domain'):
            materializer.enforce_cut(result, {'state': 'unknown'}, {'compatibility_state': 'unknown'}, True)

    def test_any_selected_failure_or_unknown_stops_including_boundary_points(self):
        for in_domain in (True, False):
            for state in ('fail', 'unknown'):
                with self.subTest(in_domain=in_domain, state=state), self.assertRaisesRegex(ValueError, 'contradicts'):
                    materializer.enforce_cut({'state': state}, {'state': 'pass'}, {'compatibility_state': 'pass'}, in_domain)
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            materializer.enforce_cut({'state': 'pass'}, {'state': 'unknown'}, {'compatibility_state': 'pass'}, False)


if __name__ == '__main__':unittest.main()
