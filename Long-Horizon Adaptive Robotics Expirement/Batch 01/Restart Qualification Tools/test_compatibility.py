"""Synthetic descriptor counterexamples only; no simulator, jobs or run evidence."""
import copy
import unittest

from compatibility import (COMPONENTS, OBS_SCHEMA, SPEC_SCHEMA, box_aggregate,
                           digest, verify_class_compatibility)


def fixture(count=3, mass=.1, friction=1.2):
    templates = {}
    for kind in ('part', 'insert'):
        half = [.021, .021, .018] if kind == 'part' else [.025, .025, .008]
        for family in ('A', 'B'):
            templates[kind + ':' + family] = {'inertia_rule': 'axis-aligned-box-aggregate-1',
                'all_other_compiled_entity_fields': {'synthetic_marker': kind},
                'fixed_friction_tail': [.015, .001], 'mass_boxes': [
                    {'half_size_m': half, 'position_m': [0., 0., 0.], 'mass_kg': 'sampled_main_geom_mass'},
                    {'half_size_m': [.014, .014, .0003], 'position_m': [0., 0., half[2] + .0004], 'mass_kg': .0001},
                    {'half_size_m': [.004, .014, .0003], 'position_m': [.018, 0., half[2] + .0004], 'mass_kg': .0001}]}
    spec = {'schema_version': SPEC_SCHEMA,
            'required_source_hashes': {'descriptor_exporter': '1' * 64, 'cell.py': '2' * 64},
            'component_sha256': {key: digest(key) for key in COMPONENTS}, 'templates': templates,
            'declared_domain': {'allowed_part_counts': [3, 6, 10],
                               'main_geom_mass_kg': {'min': .09, 'max': .11, 'max_exclusive': True},
                               'main_geom_sliding_friction': {'min': 1.1, 'max': 1.3, 'max_exclusive': True}}}
    rows = []
    ids = [(f'{"A" if i % 2 == 0 else "B"}{i+1}', 'part', 'A' if i % 2 == 0 else 'B') for i in range(count)]
    ids += [('insert_A', 'insert', 'A'), ('insert_B', 'insert', 'B')]
    for identity, kind, family in ids:
        template = templates[kind + ':' + family]
        rows.append({'id': identity, 'kind': kind, 'family': family, 'template_sha256': digest(template),
                     'main_geom_mass_kg': mass, 'main_geom_friction': [friction, .015, .001],
                     'compiled_mass_properties': box_aggregate(template, mass)})
    observation = {'schema_version': OBS_SCHEMA, 'source_hashes': copy.deepcopy(spec['required_source_hashes']),
                   'component_sha256': copy.deepcopy(spec['component_sha256']), 'part_count': count, 'objects': rows,
                   'physical_configuration_sha256': digest(['synthetic', count, mass, friction]), 'scene_xml_sha256': '3' * 64}
    return spec, observation


class CompatibilityTests(unittest.TestCase):
    def state(self, spec, obs):
        return verify_class_compatibility(spec, obs, frozen_spec_sha256=digest(spec))['compatibility_state']

    def test_two_seed_like_configurations_and_all_populations_can_be_compatible(self):
        for count in (3, 6, 10):
            for mass, friction in ((.0901, 1.101), (.1099, 1.299)):
                spec, obs = fixture(count, mass, friction)
                self.assertEqual(self.state(spec, obs), 'pass')

    def test_compatible_never_means_measured_or_authorized_recovery(self):
        spec, obs = fixture(); result = verify_class_compatibility(spec, obs, frozen_spec_sha256=digest(spec))
        self.assertIsNone(result['instance_previously_calibrated'])
        self.assertEqual(result['recovery_admissibility'], 'not_assessed')
        self.assertFalse(result['safety_predicates_evaluated'])
        self.assertFalse(any(result['effects'].values()))

    def test_changed_fixed_components_fail_individually(self):
        for component in COMPONENTS:
            spec, obs = fixture(); obs['component_sha256'][component] = 'f' * 64
            with self.subTest(component=component): self.assertEqual(self.state(spec, obs), 'fail')

    def test_unexplained_component_fails_and_missing_component_is_unknown(self):
        spec, obs = fixture(); obs['component_sha256']['extra_solver_setting'] = 'f' * 64
        self.assertEqual(self.state(spec, obs), 'fail')
        spec, obs = fixture(); del obs['component_sha256']['native_actuators']
        self.assertEqual(self.state(spec, obs), 'unknown')

    def test_changed_source_fails_missing_exporter_is_unknown(self):
        spec, obs = fixture(); obs['source_hashes']['cell.py'] = 'f' * 64
        self.assertEqual(self.state(spec, obs), 'fail')
        spec, obs = fixture(); del obs['source_hashes']['descriptor_exporter']
        self.assertEqual(self.state(spec, obs), 'unknown')

    def test_changed_descriptor_cannot_authorize_broader_domain(self):
        spec, obs = fixture(); frozen = digest(spec); spec['declared_domain']['main_geom_mass_kg']['max'] = 1.
        result = verify_class_compatibility(spec, obs, frozen_spec_sha256=frozen)
        self.assertEqual(result['compatibility_state'], 'fail')

    def test_missing_independent_release_binding_is_unknown(self):
        spec, obs = fixture()
        self.assertEqual(verify_class_compatibility(spec, obs, frozen_spec_sha256=None)['compatibility_state'], 'unknown')

    def test_out_of_domain_or_open_upper_endpoint_fails(self):
        for mass, friction in ((.089, 1.2), (.11, 1.2), (.1, 1.3), (.1, 1.099)):
            spec, obs = fixture(mass=mass, friction=friction)
            with self.subTest(mass=mass, friction=friction): self.assertEqual(self.state(spec, obs), 'fail')

    def test_inserts_are_checked_too(self):
        spec, obs = fixture(); obs['objects'][-1]['main_geom_mass_kg'] = .5
        self.assertEqual(self.state(spec, obs), 'fail')

    def test_full_friction_vector_is_not_erased(self):
        spec, obs = fixture(); obs['objects'][0]['main_geom_friction'][1] += .001
        self.assertEqual(self.state(spec, obs), 'fail')

    def test_unknown_population_fails(self):
        spec, obs = fixture(); obs['part_count'] = 9
        self.assertEqual(self.state(spec, obs), 'fail')

    def test_wrong_family_duplicate_missing_or_extra_entities_fail(self):
        for case in ('family', 'duplicate', 'missing', 'extra'):
            spec, obs = fixture()
            if case == 'family': obs['objects'][0]['family'] = 'B'
            if case == 'duplicate': obs['objects'][0]['id'] = obs['objects'][1]['id']
            if case == 'missing': obs['objects'].pop()
            if case == 'extra': obs['objects'].append({**obs['objects'][0], 'id': 'unrequested'})
            with self.subTest(case=case): self.assertEqual(self.state(spec, obs), 'fail')

    def test_template_change_fails(self):
        spec, obs = fixture(); obs['objects'][0]['template_sha256'] = 'f' * 64
        self.assertEqual(self.state(spec, obs), 'fail')

    def test_tag_mass_is_not_lost_in_total_mass(self):
        spec, obs = fixture(); obs['objects'][0]['compiled_mass_properties']['mass_kg'] = .1
        self.assertEqual(self.state(spec, obs), 'fail')

    def test_com_diagonal_and_off_diagonal_inertia_mutations_fail(self):
        for case in ('com', 'diagonal', 'off_diagonal'):
            spec, obs = fixture(); mass = obs['objects'][0]['compiled_mass_properties']
            if case == 'com': mass['center_of_mass_body_m'][0] += .001
            if case == 'diagonal': mass['inertia_tensor_body_kg_m2'][0][0] += .0001
            if case == 'off_diagonal': mass['inertia_tensor_body_kg_m2'][0][1] += .0001
            with self.subTest(case=case): self.assertEqual(self.state(spec, obs), 'fail')

    def test_nonfinite_and_missing_mass_properties_are_unknown(self):
        spec, obs = fixture(); obs['objects'][0]['main_geom_mass_kg'] = float('nan')
        self.assertEqual(self.state(spec, obs), 'unknown')
        spec, obs = fixture(); del obs['objects'][0]['compiled_mass_properties']
        self.assertEqual(self.state(spec, obs), 'unknown')

    def test_missing_exact_provenance_is_unknown_not_silently_ignored(self):
        spec, obs = fixture(); del obs['physical_configuration_sha256']
        self.assertEqual(self.state(spec, obs), 'unknown')

    def test_box_aggregate_has_independent_hand_computed_reference(self):
        template = {'inertia_rule': 'axis-aligned-box-aggregate-1', 'mass_boxes': [
            {'half_size_m': [1., 2., 3.], 'position_m': [0., 0., 0.], 'mass_kg': 'sampled_main_geom_mass'},
            {'half_size_m': [1., 1., 1.], 'position_m': [3., 0., 0.], 'mass_kg': 1.}]}
        properties = box_aggregate(template, 2.)
        self.assertEqual(properties['mass_kg'], 3.)
        self.assertEqual(properties['center_of_mass_body_m'], [1., 0., 0.])
        # Box diagonals plus COM parallel-axis contribution diag(0,6,6).
        expected = [28. / 3., 40. / 3., 10.]
        for index in range(3): self.assertAlmostEqual(properties['inertia_tensor_body_kg_m2'][index][index], expected[index])

    def test_unsupported_mass_rule_does_not_invent_a_template(self):
        spec, obs = fixture(); spec['templates']['part:A']['inertia_rule'] = 'arbitrary_mesh'
        for row in obs['objects']:
            if row['kind'] == 'part' and row['family'] == 'A': row['template_sha256'] = digest(spec['templates']['part:A'])
        self.assertEqual(self.state(spec, obs), 'unknown')


if __name__ == '__main__': unittest.main()
