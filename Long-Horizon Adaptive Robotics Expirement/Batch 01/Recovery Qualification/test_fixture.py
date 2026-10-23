import copy
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from fixture import (POINTS, SamplingGaps, construct_xml, cut_eligible, declared_plan, expected_payload,
                     generator_domain, physical_snapshot_sources, physical_trial_pass,
                     retained_hold_check, select_public, transformed_box, validate_plan)


class DeclarationTests(unittest.TestCase):
    def test_exact_twenty_per_destination_and_independent_worlds(self):
        plan = declared_plan()
        self.assertEqual(len(plan['trials']), 40)
        self.assertEqual(len({t['id'] for t in plan['trials']}), 40)
        for destination in ('parking1', 'parking2'):
            rows = [t for t in plan['trials'] if t['destination'] == destination]
            self.assertEqual(len(rows), 20)
            self.assertEqual(len([t for t in rows if t['fixture'] == 'construction']), 14)
            validation = [t for t in rows if t['fixture'] == 'independent_generator']
            self.assertEqual({(t['population'], t['family']) for t in validation},
                             {(n, f) for n in (3, 6, 10) for f in ('A', 'B')})
        independent = [t['world_seed'] for t in plan['trials'] if t['fixture'] == 'independent_generator']
        self.assertEqual(len(set(independent)), 12)

    def test_every_corner_and_center_for_each_family(self):
        for destination in ('parking1', 'parking2'):
            for family in ('A', 'B'):
                points = {(t['main_geom_mass_kg'], t['main_geom_sliding_friction']) for t in declared_plan()['trials']
                          if t['destination'] == destination and t['family'] == family and t['population'] == 10
                          and t['fixture'] == 'construction'}
                self.assertEqual(points, set(POINTS))

    def test_saved_declaration_matches_and_mutations_rejected(self):
        saved = json.loads((Path(__file__).parent / 'plan-001.json').read_text())
        validate_plan(saved)
        for key, value in (('absence_s', 1.), ('geometry_interval_s', .2)):
            changed = copy.deepcopy(saved); changed[key] = value
            with self.assertRaises(ValueError):
                validate_plan(changed)
        changed = copy.deepcopy(saved); changed['trials'][0]['world_seed'] += 1
        with self.assertRaises(ValueError):
            validate_plan(changed)

    def test_exact_upper_endpoints_are_outside_half_open_domain(self):
        self.assertTrue(generator_domain(.09, 1.1))
        self.assertTrue(generator_domain(.109999, 1.299999))
        self.assertFalse(generator_domain(.11, 1.2))
        self.assertFalse(generator_domain(.1, 1.3))
        self.assertFalse(generator_domain(.0899, 1.2))

    def test_lexical_b10_is_declared_not_numerical_b2(self):
        self.assertEqual(expected_payload(10, 'B'), 'B10')
        self.assertEqual(expected_payload(6, 'B'), 'B2')


class XmlTests(unittest.TestCase):
    def setUp(self):
        self.registry = {'A1': {'family': 'A', 'kind': 'part'}, 'B2': {'family': 'B', 'kind': 'part'},
                         'insert_A': {'family': 'A', 'kind': 'insert'}}
        self.xml = '<mujoco><option timestep=".002"/><worldbody>' + ''.join(
            f'<body name="{name}" pos=".2 .3 .02"><freejoint/><geom name="part_{name}" type="box" mass=".097" friction="1.17 .015 .001" size=".021 .021 .018"/><geom name="tag_{name}" mass=".0001" contype="0"/></body>'
            for name in self.registry) + '</worldbody></mujoco>'
        self.trial = copy.deepcopy(declared_plan()['trials'][2])
        self.trial['expected_payload_id'] = 'A1'

    def test_only_main_mass_and_friction_change(self):
        result, details = construct_xml(self.xml, self.registry, self.trial)
        old = list(ET.fromstring(self.xml).iter()); new = list(ET.fromstring(result).iter())
        self.assertEqual(len(old), len(new))
        for a, b in zip(old, new):
            self.assertEqual(a.tag, b.tag)
            changes = {key for key in set(a.attrib) | set(b.attrib) if a.attrib.get(key) != b.attrib.get(key)}
            self.assertTrue(changes <= {'mass', 'friction'})
            if changes:
                self.assertTrue(a.attrib['name'].startswith('part_'))
        actual = details['realized_xml_properties']
        self.assertEqual(actual['A1']['main_geom_mass_kg'], .11)
        self.assertFalse(actual['A1']['generator_half_open_domain_member'])
        self.assertEqual(actual['B2']['main_geom_mass_kg'], .1)
        self.assertEqual(actual['insert_A']['main_geom_friction'], [1.2, .015, .001])

    def test_independent_world_bytes_untouched(self):
        trial = next(t for t in declared_plan()['trials'] if t['fixture'] == 'independent_generator')
        result, details = construct_xml(self.xml, self.registry, trial)
        self.assertEqual(result, self.xml)
        self.assertEqual(details['generator_xml_sha256'], details['fixture_xml_sha256'])

    def test_missing_declared_payload_is_error(self):
        self.trial['expected_payload_id'] = 'A99'
        with self.assertRaises(ValueError):
            construct_xml(self.xml, self.registry, self.trial)


class ObservationTests(unittest.TestCase):
    def test_physical_snapshot_uses_only_shared_identity_subset(self):
        runtime = Path('synthetic-runtime').resolve()
        names = ('cell.py', 'actuation.py', 'evaluator.py', 'sensor_worker.py', 'experiment.py', 'restart_qualification.py')
        all_sources = {str(runtime / name): 'hash-' + name for name in names}
        original = copy.deepcopy(all_sources)
        result = physical_snapshot_sources(all_sources, runtime)
        self.assertEqual(set(result), {'cell.py', 'actuation.py', 'evaluator.py', 'sensor_worker.py'})
        self.assertEqual(all_sources, original)
        self.assertEqual(result['cell.py'], 'hash-cell.py')
        del all_sources[str(runtime / 'cell.py')]
        with self.assertRaises(KeyError):
            physical_snapshot_sources(all_sources, runtime)

    def test_transient_absence_loss_cannot_be_erased_by_final_recovery(self):
        self.assertTrue(physical_trial_pass(held_at_absence_end=True,
            all_absence_tick_hold_checks_pass=True, placement_passed=True))
        self.assertFalse(physical_trial_pass(held_at_absence_end=True,
            all_absence_tick_hold_checks_pass=False, placement_passed=True))
        self.assertFalse(physical_trial_pass(held_at_absence_end=True,
            all_absence_tick_hold_checks_pass=None, placement_passed=True))
        self.assertFalse(physical_trial_pass(held_at_absence_end=False,
            all_absence_tick_hold_checks_pass=True, placement_passed=True))
        self.assertFalse(physical_trial_pass(held_at_absence_end=True,
            all_absence_tick_hold_checks_pass=True, placement_passed=False))

    def test_public_selection_is_fresh_family_raw_lexical(self):
        detections = [{'id': name, 'kind': 'part', 'family': name[0], 'visible_mark': 'raw', 'zone': 'raw'}
                      for name in ('A1', 'B2', 'B10')]
        self.assertEqual(select_public(detections, 'B', .1), 'B10')
        detections[-1]['visible_mark'] = 'processed'
        self.assertEqual(select_public(detections, 'B', .1), 'B2')
        for age in (.351, -1., math.nan):
            with self.assertRaises(ValueError):
                select_public(detections, 'B', age)
        with self.assertRaises(ValueError):
            select_public([], 'A', .1)

    def test_original_hold_threshold_not_relaxed(self):
        row = {'objects': [{'id': 'A1', 'position': [0., 0., .075], 'gripper_contact': True}]}
        self.assertFalse(retained_hold_check(row, 'A1'))
        row['objects'][0]['position'][2] = .075001
        self.assertTrue(retained_hold_check(row, 'A1'))
        row['objects'][0]['gripper_contact'] = False
        self.assertFalse(retained_hold_check(row, 'A1'))

    def test_cut_aligns_public_height_and_requires_bilateral_clearance(self):
        snapshot = {'objects': [{'id': 'A1', 'position': [0., 0., .081], 'bounds': {'min': [0., 0., .06]}, 'gripper_contact': True}]}
        args = dict(phase=4, tcp_z=.08, jaw_width=.042, bilateral=True)
        self.assertTrue(cut_eligible(snapshot, 'A1', **args))
        for key, value in (('phase', 3), ('tcp_z', .079999), ('bilateral', False), ('jaw_width', .005), ('jaw_width', .065)):
            altered = dict(args); altered[key] = value
            self.assertFalse(cut_eligible(snapshot, 'A1', **altered))
        snapshot['objects'][0]['bounds']['min'][2] = 0.
        self.assertFalse(cut_eligible(snapshot, 'A1', **args))

    def test_rotated_outer_box_contains_transformed_corners(self):
        a = .42; rotation = [[math.cos(a), -math.sin(a), 0.], [math.sin(a), math.cos(a), 0.], [0., 0., 1.]]
        center, half, position = [.1, -.2, .3], [.02, .04, .06], [1., 2., 3.]
        bounds = transformed_box(center, half, position, rotation)
        import itertools
        for signs in itertools.product((-1, 1), repeat=3):
            local = [center[i] + signs[i] * half[i] for i in range(3)]
            world = [position[i] + sum(rotation[i][j] * local[j] for j in range(3)) for i in range(3)]
            self.assertTrue(all(bounds['min'][i] - 1e-12 <= world[i] <= bounds['max'][i] + 1e-12 for i in range(3)))

    def test_sampling_reports_actual_gaps_and_rejects_reversal(self):
        gaps = SamplingGaps(); gaps.record(1., 4.); gaps.record(1.02, 4.023); gaps.record(1.05, 4.07)
        self.assertAlmostEqual(gaps.report()['maximum_sim_gap_s'], .03)
        self.assertAlmostEqual(gaps.report()['maximum_wall_gap_s'], .047)
        self.assertIsNone(gaps.report()['continuous_sweep_error_bound_m'])
        with self.assertRaises(ValueError):
            gaps.record(1.049, 4.08)


class ProcessJoinTests(unittest.TestCase):
    def test_join_assigns_only_current_process_and_closes_open_handle(self):
        import process_caps
        calls = []
        class Kernel:
            def OpenJobObjectW(self, access, inherit, name):
                calls.append(('open', access, inherit, name)); return 51
            def GetCurrentProcess(self): return 99
            def AssignProcessToJobObject(self, job, process):
                calls.append(('assign', job, process)); return True
            def CloseHandle(self, handle): calls.append(('close', handle)); return True
        with patch.object(process_caps, 'api', return_value=Kernel()):
            process_caps.join_job('declared-parent-job')
        self.assertEqual(calls, [('open', 1, False, 'declared-parent-job'), ('assign', 51, 99), ('close', 51)])


if __name__ == '__main__':
    unittest.main()
