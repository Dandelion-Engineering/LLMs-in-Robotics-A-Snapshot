import unittest
import numpy as np

from fixture import declared_plan
from measurement import DenseBounds, HoldWindow, provisional_identity, selected_trials


class MeasurementTests(unittest.TestCase):
    def test_provisional_identity_rejects_missing_source_and_postfit_status(self):
        rule = {'schema_version': 'provisional-restart-class-rule-1', 'status': 'provisional_development_rule',
            'destination': 'parking1', 'created_at': '2026-01-01T00:00:00Z',
            'selection_rule': 'unique_bilateral_payload_template',
            'geometry_scope': 'discrete_native_evaluated_states_empirical_transfer',
            'validation_outcomes_used_for_fitting': False, 'payload_template_to_cell': {'part:A': 'A'},
            'cells': [{'cell_id': 'A'}], 'empirical_transfer_rule': 'synthetic finite assumption',
            'untested_combinations': ['other worlds'], 'absence': {'prospective_absence_bound_s': 5},
            'construction_extraction': {'path': 'synthetic', 'sha256': 'a' * 64},
            'class_spec': {'path': 'synthetic', 'sha256': 'b' * 64, 'canonical_sha256': 'c' * 64}}
        self.assertIs(provisional_identity(rule, 'parking1'), rule)
        with self.assertRaises(ValueError): provisional_identity(rule, 'parking2')
        rule['validation_outcomes_used_for_fitting'] = True
        with self.assertRaises(ValueError): provisional_identity(rule, 'parking1')
        rule['validation_outcomes_used_for_fitting'] = False
        rule['class_spec']['sha256'] = 'placeholder'
        with self.assertRaises(ValueError): provisional_identity(rule, 'parking1')

    def test_phase_selection_preserves_all_ids_without_new_worlds(self):
        plan = declared_plan()
        construction = selected_trials(plan, 'all', 'construction')
        validation = selected_trials(plan, 'all', 'validation')
        self.assertEqual(len(construction), 28)
        self.assertEqual(len(validation), 12)
        self.assertEqual({t['id'] for t in construction + validation}, {t['id'] for t in plan['trials']})
        self.assertEqual(len(selected_trials(plan, 'parking1', 'validation')), 6)
        with self.assertRaises(ValueError): selected_trials(plan, 'all', 'all')

    def test_hold_loss_during_sensing_cannot_disappear_at_admission(self):
        window = HoldWindow('A1', 1., 2.)
        good = {'objects': [{'id': 'A1', 'position': [0., 0., .08], 'bounds': {'min': [0., 0., .06]}, 'gripper_contact': True}]}
        window.record(good, 1., 2., tick=False)
        window.record(good, 6., 7., tick=True)
        five_second = dict(window.data)
        bad = {'objects': [{**good['objects'][0], 'gripper_contact': False}]}
        window.record(bad, 6.002, 7.003, tick=True)
        window.record(good, 6.004, 7.005, tick=False)
        self.assertTrue(five_second['all_recorded_hold_checks_pass'])
        self.assertFalse(window.data['all_recorded_hold_checks_pass'])
        self.assertEqual(window.data['ticks_with_hold_predicate_false'], 1)
        self.assertAlmostEqual(window.data['observed_sim_s'], 5.004)

    def test_dense_union_retains_between_coarse_sample_excursion(self):
        dense = DenseBounds()
        low = np.array([[0., 0., 0.], [-1., -1., -1.]])
        high = low + .1
        dense.add(0., 0., low, high)
        dense.add(.002, .003, low - .2, high + .3)
        dense.add(.02, .021, low, high)
        report = dense.report([4, 5], (low, high))
        self.assertEqual(report['distinct_sim_time_count'], 3)
        self.assertAlmostEqual(report['maximum_sim_gap_s'], .018)
        np.testing.assert_allclose(report['observed_coarse_endpoint_sampling_deficit_m']['lower_m'], .2)
        np.testing.assert_allclose(report['observed_coarse_endpoint_sampling_deficit_m']['upper_m'], .3)
        self.assertIsNone(report['continuous_sweep_error_bound_m'])
        self.assertIsNone(report['transfer_padding_m'])


if __name__ == '__main__':
    unittest.main()
