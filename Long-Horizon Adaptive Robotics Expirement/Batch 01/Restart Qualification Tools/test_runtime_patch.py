"""Execute proposed classifier in memory; Runtime remains byte-for-byte untouched."""
import copy
import io
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import descriptor
import qualification
from build_integration_patch import proposed_restart_state
from compatibility import digest
from test_qualification import fixture as qualification_fixture

RUNTIME = Path(__file__).resolve().parents[2] / 'Runtime'


def modules():
    proposed = types.ModuleType('proposed_restart_state')
    with patch.dict(sys.modules, {'restart_physical_class': descriptor, 'restart_qualification': qualification}):
        exec(compile(proposed_restart_state((RUNTIME / 'restart_state.py').read_text(encoding='utf-8')), 'proposed_restart_state.py', 'exec'), proposed.__dict__)
    fixtures = types.ModuleType('runtime_restart_fixtures')
    with patch.dict(sys.modules, {'restart_state': proposed}):
        exec(compile((RUNTIME / 'test_restart_state.py').read_text(encoding='utf-8'), 'test_restart_state.py', 'exec'), fixtures.__dict__)
    return proposed, fixtures


def case(fixtures):
    snapshot = fixtures.snapshot(); calibration = fixtures.calibration(snapshot)
    entry, protected, context = qualification_fixture()
    snapshot.update({k: copy.deepcopy(protected[k]) for k in ('physical_configuration_sha256', 'scene_xml_sha256', 'source_hashes', 'physical_class_observation', 'expected_object_ids')})
    snapshot['expected_object_ids'].sort()
    for index, row in enumerate(protected['geometry']['objects'][1:]):
        center = [.45 + .06 * (index % 3), -.30 + .1 * (index // 3), .018]
        obj = {'id': row['id'], 'kind': row['kind'], 'family': row['family'], 'position': center,
               'bounds': {'min': [center[0]-.02, center[1]-.02, 0.], 'max': [center[0]+.02, center[1]+.02, .036]},
               'linear_velocity': [0., 0., 0.], 'angular_velocity': [0., 0., 0.]}
        snapshot['geometry']['objects'].append(obj)
        contact = copy.deepcopy(snapshot['contacts']['by_object']['A1'])
        contact.update(hand_contact=False, bilateral_force_bearing=False, left_finger_contact=False, right_finger_contact=False,
                       left_normal_force_N=0., right_normal_force_N=0., support_upward_force_N=1.)
        snapshot['contacts']['by_object'][row['id']] = contact
    cell = context['bundle']['cells'][0]
    cell['grip_envelope'] = copy.deepcopy(calibration['grip']['envelope'])
    cell['route_envelope'] = copy.deepcopy(calibration['routes'][0]['envelope'])
    for role, target in (('grip', calibration['grip']), ('route', calibration['routes'][0])):
        target.update({k: copy.deepcopy(entry[k]) for k in ('match_mode', 'qualification_cell_id', 'evidence_refs', 'source_hashes')})
        target['qualification_role'] = role
        target.pop('physical_configuration_sha256')
    context['frozen_bundle_sha256'] = digest(context['bundle'])
    return snapshot, calibration, context


class RuntimePatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime, cls.fixtures = modules()

    def test_existing_exact_configuration_and_capture_regressions(self):
        suite = unittest.defaultTestLoader.loadTestsFromModule(self.fixtures)
        output = io.StringIO()
        result = unittest.TextTestRunner(stream=output).run(suite)
        self.assertGreaterEqual(result.testsRun, 15)
        self.assertTrue(result.wasSuccessful(), output.getvalue())

    def test_explicit_class_mode_can_reach_unchanged_physical_predicates(self):
        snapshot, calibration, context = case(self.fixtures)
        result = self.runtime.classify_restart(snapshot, calibration=calibration, qualification_context=context)
        self.assertEqual(result['state'], 'admissible', result)
        self.assertEqual(len(result['qualified_class_evidence']), 2)
        self.assertTrue(all(r['evidence_basis'] == 'empirical_transfer' and not r['instance_previously_calibrated'] for r in result['qualified_class_evidence']))
        self.assertFalse(any(result['effects'].values()))

    def test_missing_qualification_or_mode_cannot_silently_broaden_exact_match(self):
        snapshot, calibration, context = case(self.fixtures)
        self.assertEqual(self.runtime.classify_restart(snapshot, calibration=calibration)['state'], 'unknown')
        calibration['grip'].pop('match_mode'); calibration['routes'][0].pop('match_mode')
        self.assertEqual(self.runtime.classify_restart(snapshot, calibration=calibration, qualification_context=context)['state'], 'unknown')

    def test_class_pass_does_not_override_force_clearance_state_or_route_failure(self):
        for change in ('unilateral', 'clearance', 'joint_start', 'blocked_route'):
            snapshot, calibration, context = case(self.fixtures)
            if change == 'unilateral': snapshot['contacts']['by_object']['A1'].update(right_normal_force_N=0., bilateral_force_bearing=False)
            if change == 'clearance': snapshot['geometry']['objects'][0]['bounds']['min'][2] = .05
            if change == 'joint_start': snapshot['robot']['joint_position_rad'][0] = .5
            if change == 'blocked_route': snapshot['geometry']['objects'][1]['bounds'] = {'min': [.2, -.02, .11], 'max': [.24, .02, .15]}
            with self.subTest(change=change):
                self.assertEqual(self.runtime.classify_restart(snapshot, calibration=calibration, qualification_context=context)['state'], 'inadmissible')

    def test_route_cannot_mix_a_different_measured_cell_with_passed_grip(self):
        snapshot, calibration, context = case(self.fixtures)
        other = copy.deepcopy(context['bundle']['cells'][0]); other['cell_id'] = 'other_cell'
        context['bundle']['cells'].append(other); context['frozen_bundle_sha256'] = digest(context['bundle'])
        calibration['routes'][0]['qualification_cell_id'] = 'other_cell'
        result = self.runtime.classify_restart(snapshot, calibration=calibration, qualification_context=context)
        self.assertEqual(result['state'], 'unknown')
        self.assertEqual(self.fixtures.predicate(result, 'measured_recovery_route')['state'], 'unknown')


if __name__ == '__main__': unittest.main()
