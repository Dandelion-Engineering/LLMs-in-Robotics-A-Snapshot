"""Tiny pure source/data tests; never run during physical timing experiments."""
import copy
import json
from types import SimpleNamespace
import unittest

import assemble_provisional_rules as assembly


def reference(group='A1'):
    snapshot = {'snapshot_sha256': 'a'*64, 'physical_configuration_sha256': 'b'*64,
        'physical_class_observation': {'synthetic_only': True},
        'object_poses': {group: {'relative_to_tcp': {'rotation': [[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]]}}},
        'geometry': {'zones': {'parking1': {'min': [.3,.1,0.], 'max': [.4,.2,.1]}}}}
    return {'trial_id': 'parking1-corner-A-5', 'states': {'cut': {'payload': snapshot,
        'source_ref': {'path': 'synthetic/events.jsonl', 'sha256': 'c'*64}}},
        'consumed_ref': {'path': 'synthetic/trial.json', 'sha256': 'd'*64},
        'measured_states_consumed_ref': {'path': 'synthetic/measured-states.json', 'sha256': 'e'*64}}


class ProvisionalAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.choices = json.loads((assembly.HERE/'root-provisional-choices-001.json').read_bytes())

    def test_exact_choices_and_cells_copy_without_fitting_or_mutation(self):
        before = copy.deepcopy(self.choices); ref = reference(); selected = self.choices['cell_choices']['A1']
        corridors = [{'min': [.1,.2,.3], 'max': [.4,.5,.6]}]
        cell = assembly.make_cell(self.choices, 'parking1', 'A1', {'templates': {'part:A': {'synthetic': True}}},
                                  ref, corridors, [assembly.thin_point(ref)], {'synthetic': 'external refs'})
        self.assertEqual(self.choices, before)
        self.assertEqual(cell['grip_envelope']['relative_position_m'], selected['relative_position_m'])
        self.assertEqual(cell['grip_envelope']['relative_rotation'], ref['states']['cut']['payload']['object_poses']['A1']['relative_to_tcp']['rotation'])
        self.assertEqual(cell['route_envelope']['destination_region_m'], ref['states']['cut']['payload']['geometry']['zones']['parking1'])
        self.assertEqual(cell['route_envelope']['joint_start_ranges_rad'][0],
                         [selected['joint_start_center_rad'][0]-.03, selected['joint_start_center_rad'][0]+.03])
        self.assertEqual(cell['route_envelope']['clearance_corridors_m'], corridors)
        self.assertEqual(cell['route_sampling_clearance_allowance_m'], 0.)
        self.assertEqual(cell['uniform_materialized_corridor_padding_m'], .01)
        self.assertEqual(cell['maximum_qualified_absence_s'], 5.)
        self.assertEqual(cell['absence_timebase'], 'wall')
        self.assertEqual(cell['evidence_refs'], [])
        self.assertIsNone(cell['observed_coarse_sampling_deficit']['value'])

    def test_thin_point_keeps_exact_identities_and_external_witness_only(self):
        ref = reference(); point = assembly.thin_point(ref)
        self.assertEqual(point['snapshot_sha256'], 'a'*64)
        self.assertEqual(point['physical_configuration_sha256'], 'b'*64)
        self.assertEqual(point['source_ref'], ref['states']['cut']['source_ref'])
        self.assertEqual(point['measured_states_ref'], ref['measured_states_consumed_ref'])
        self.assertNotIn('object_poses', point)
        self.assertNotIn('robot', point)

    def test_selected_contradiction_stops_and_b2_needs_actual_start_predicate(self):
        self.assertEqual(assembly.numerical_expectation('A1', True, {'state': 'pass'}), 'included_numerical_cut')
        for group in ('A1', 'B10'):
            with self.assertRaises(ValueError): assembly.numerical_expectation(group, True, {'state': 'fail'})
        membership = {'state': 'fail', 'template': 'part:B', 'grip': {'state': 'pass'},
            'route': {'state': 'fail', 'observed': [{'checks': {'tcp_start': False, 'joint_start': True}}]}}
        self.assertEqual(assembly.numerical_expectation('B2', True, membership), 'numerically_excluded_B2')
        membership['route']['observed'][0]['checks']['tcp_start'] = True
        with self.assertRaises(ValueError): assembly.numerical_expectation('B2', True, membership)
        with self.assertRaises(ValueError): assembly.numerical_expectation('B2', True, {'state': 'unknown'})
        self.assertEqual(assembly.numerical_expectation('B10', False, {'state': 'unknown'}), 'class_excluded')

    def test_unassessed_dwell_remains_explicit_and_no_other_unknown_is_ignored(self):
        checks = {'recorded_hold': True, 'measured_duration_supports_declared_bound': True, 'settled_dwell_event': None}
        fake = SimpleNamespace(hold_assessment=lambda *args: {'checks': copy.deepcopy(checks),
            'actual_duration_to_accepted_dispatch_s': 5.01})
        result = assembly.construction_support(fake, {}, {}, .002, {})
        self.assertTrue(result['required_checks_pass'])
        self.assertIsNone(result['full_assessment_with_unassessed_dwell']['checks']['settled_dwell_event'])
        checks['recorded_hold'] = None
        self.assertFalse(assembly.construction_support(fake, {}, {}, .002, {})['required_checks_pass'])
        checks['recorded_hold'] = True; checks['measured_duration_supports_declared_bound'] = False
        self.assertFalse(assembly.construction_support(fake, {}, {}, .002, {})['required_checks_pass'])

    def test_choice_byte_guard_and_receipt_argument_ambiguity(self):
        assembly.validate_choices(self.choices, assembly.CHOICES_SHA256)
        with self.assertRaises(ValueError): assembly.validate_choices(self.choices, '0'*64)
        self.assertEqual(assembly.argument(['python','--destination','parking1'], '--destination', '.', path=False), 'parking1')
        with self.assertRaises(ValueError): assembly.argument(['--output','one','--output','two'], '--output', '.')

    def test_dossier_requires_actual_installed_receipt_identity_and_equal_bytes(self):
        receipt = {'state': 'succeeded', 'exit_status': 0}
        calls = []
        source = SimpleNamespace(evidence=SimpleNamespace(external=lambda path: (receipt if path == 'receipt' else {}, {})))
        runner = SimpleNamespace(verify_queue_receipt=lambda identity, path: calls.append((identity, path)) or dict(receipt))
        with self.assertRaisesRegex(ValueError, 'installed queue identity'):
            assembly.bind_dossier(source, 'parking1', 'dossier', 'receipt', runner)
        self.assertEqual(calls, [])
        receipt['id'] = 'synthetic-installed-job'
        runner.verify_queue_receipt = lambda identity, path: calls.append((identity, path)) or {**receipt, 'child_pid': 123}
        with self.assertRaisesRegex(ValueError, 'installed queue record or consumed bytes'):
            assembly.bind_dossier(source, 'parking1', 'dossier', 'receipt', runner)
        self.assertEqual(calls, [('synthetic-installed-job', 'receipt')])
        receipt['exit_status'] = False
        with self.assertRaisesRegex(ValueError, 'Successful official dossier receipt'):
            assembly.bind_dossier(source, 'parking1', 'dossier', 'receipt', runner)


if __name__ == '__main__':
    unittest.main()
