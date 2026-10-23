"""Native static regression checks for the applied hold patch and exact archived original.

No mj_step, Cell construction, production evidence, queue calls or performance
claims. mj_forward is used only to populate tiny native static test fixtures.
"""
import importlib.util
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import mujoco
import numpy as np

from stage_hold_observation import BASES, PROJECT, STAGE, digest, staged_sources

ARCHIVE = STAGE / 'original'
import json
INTEGRATION = json.loads((STAGE / 'integration.json').read_text())
sys.path[:0] = [str(PROJECT / "Runtime"), str(PROJECT / "Batch 01" / "Recovery Qualification")]
from evaluator import IndependentEvaluator, EvaluationError


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


ORIGINAL = load("original_hold_measurement", ARCHIVE / "Batch 01/Recovery Qualification/measurement.py")
PROPOSED = load("proposed_hold_measurement", PROJECT / "Batch 01/Recovery Qualification/measurement.py")


class NativeFixture:
    def __init__(self, population=3):
        extras = ''.join(f'<body name="extra{i}" pos="{.25 + .06 * i} -.3 .1"><freejoint/><geom name="extra_geom{i}" type="box" size=".012 .012 .012" mass=".03"/></body>' for i in range(population-1))
        xml = f'''<mujoco><option gravity="0 0 0"/><worldbody>
        <geom name="floor" type="plane" size="2 2 .01"/>
        <body name="hand" pos="0 0 .1"><geom name="hand_geom" pos="0 .3 0" type="box" size=".01 .01 .01"/>
          <body name="finger"><geom name="finger_geom" pos=".032 0 0" type="box" size=".014 .03 .035"/>
            <body name="finger_descendant"><geom name="finger_tip" pos="-.064 0 0" type="box" size=".014 .03 .035"/></body>
          </body></body>
        <body name="arm"><geom name="arm_geom" pos="0 .4 .1" type="box" size=".01 .01 .01"/></body>
        <body name="payload" pos="0 0 .1"><freejoint/>
          <geom name="payload_main" type="box" size=".02 .018 .015" mass=".04"/>
          <geom name="payload_second" pos="0 0 .017" type="box" size=".012 .01 .011" mass=".005"/>
          <geom name="noncollision_marker" pos="0 0 -.05" type="box" size=".003 .003 .003" mass="0" contype="0" conaffinity="0"/>
          <body name="payload_child" pos="0 0 -.04"><geom name="child_geom" type="box" size=".003 .003 .003" mass=".001"/></body>
        </body>{extras}</worldbody></mujoco>'''
        model = mujoco.MjModel.from_xml_string(xml); data = mujoco.MjData(model)
        mujoco.mj_forward(model, data)
        registry = {'payload': {'kind': 'part', 'family': 'A'},
                    **{f'extra{i}': {'kind': 'part', 'family': 'B'} for i in range(population-1)}}
        self.cell = SimpleNamespace(model=model, data=data, registry=registry, evaluator=IndependentEvaluator(),
            truth={}, station={}, active_request=None, motion=[], segment=None, cycle=None, inspection_due=None)
        self.sampler = PROPOSED.PayloadHoldSampler(self.cell, 'payload')
        self.geometry = {name: model.geom(name).id for name in ('payload_main', 'payload_second', 'finger_geom',
            'finger_tip', 'hand_geom', 'arm_geom', 'floor', 'noncollision_marker', 'child_geom')}
        if data.ncon == 0: raise AssertionError('Native static fixture must create real contact slots')

    def full(self):
        return self.cell.evaluator.snapshot_cell(self.cell, zones={'parking1': [.5, .2]}, zone_half=lambda _zone: [.1, .1])

    def contact(self, name='finger_geom', *, distance=0., reversed=False, active=False):
        data = self.cell.data
        for c in data.contact: c.dist = 1.
        target = data.contact[0]
        pair = [self.geometry['payload_main'], self.geometry[name]]
        if reversed: pair.reverse()
        target.geom1, target.geom2 = pair
        target.dist = distance
        target.efc_address = 0 if active else -1

    def pose(self, z=.1, rotation=(1., 0., 0., 0.)):
        self.cell.data.qpos[:3] = [0., 0., z]
        self.cell.data.qpos[3:7] = rotation
        mujoco.mj_forward(self.cell.model, self.cell.data)


class NativeHoldEquivalence(unittest.TestCase):
    def assert_snapshot_equal(self, fixture):
        old = next(row for row in fixture.full()['objects'] if row['id'] == 'payload')
        new = fixture.sampler.snapshot()['objects'][0]
        self.assertEqual(new, {key: old[key] for key in ('id', 'position', 'bounds', 'gripper_contact')})
        return old, new

    def test_native_all_fields_exact_for_3_and_10_object_models(self):
        for n in (3, 10):
            f = NativeFixture(n)
            old, new = self.assert_snapshot_equal(f)
            self.assertTrue(new['gripper_contact'])
            self.assertEqual(len(f.full()['objects']), n)
            self.assertEqual(len(f.sampler.snapshot()['objects']), 1)

    def test_contact_tolerance_is_inclusive_and_not_force_or_constraint_qualified(self):
        f = NativeFixture()
        tolerance = f.cell.evaluator.config.contact_tolerance_m
        for distance, expected in ((-1e-4, True), (0., True), (tolerance, True), (np.nextafter(tolerance, math.inf), False)):
            for active in (False, True):
                f.contact(distance=distance, active=active)
                with patch.object(mujoco, 'mj_contactForce', side_effect=AssertionError('Predicate must not query force')):
                    _, new = self.assert_snapshot_equal(f)
                self.assertIs(new['gripper_contact'], expected)

    def test_hand_and_any_descendant_single_contact_both_geom_orders(self):
        f = NativeFixture()
        for name in ('hand_geom', 'finger_geom', 'finger_tip'):
            for reverse in (False, True):
                f.contact(name, reversed=reverse)
                _, new = self.assert_snapshot_equal(f)
                self.assertTrue(new['gripper_contact'])
        for name in ('arm_geom', 'floor', 'child_geom'):
            f.contact(name)
            _, new = self.assert_snapshot_equal(f)
            self.assertFalse(new['gripper_contact'])

    def test_strict_center_threshold_and_bottom_is_logged_not_a_hold_predicate(self):
        f = NativeFixture()
        for height, expected in ((np.nextafter(.075, -math.inf), False), (.075, False), (np.nextafter(.075, math.inf), True)):
            f.pose(height); f.contact()
            old, new = self.assert_snapshot_equal(f)
            self.assertIs(ORIGINAL.retained_hold_check({'objects': [old]}, 'payload'), expected)
            self.assertIs(PROPOSED.retained_hold_check({'objects': [new]}, 'payload'), expected)
        f.pose(.08); f.contact()
        # A very tall native box gives a negative bottom at a valid center.
        f.cell.model.geom_size[f.geometry['payload_main'], 2] = .12
        _, new = self.assert_snapshot_equal(f)
        self.assertLess(new['bounds']['min'][2], 0.)
        self.assertTrue(PROPOSED.retained_hold_check({'objects': [new]}, 'payload'))

    def test_rotated_multi_geom_bounds_use_direct_collision_boxes_only(self):
        f = NativeFixture()
        for quaternion in ((1., 0., 0., 0.), (.5, .5, .5, .5), (math.cos(.31), math.sin(.31), 0., 0.)):
            f.pose(rotation=quaternion)
            self.assert_snapshot_equal(f)
        self.assertEqual(set(f.sampler.geometries), {f.geometry['payload_main'], f.geometry['payload_second']})

    def test_reads_native_cached_transforms_without_forwarding_integrated_qpos(self):
        f = NativeFixture()
        f.cell.data.qpos[2] += .2  # cached native transforms intentionally not forwarded
        with patch.object(mujoco, 'mj_forward', side_effect=AssertionError('No forwarding in observer')):
            _, new = self.assert_snapshot_equal(f)
        self.assertNotEqual(new['position'][2], float(f.cell.data.qpos[2]))

    def test_accumulated_tick_endpoint_gap_minima_and_failure_fields_match(self):
        f = NativeFixture(10)
        old = ORIGINAL.HoldWindow('payload', 0., 0.)
        new = PROPOSED.HoldWindow('payload', 0., 0.)
        sequence = [(0., 0., False, .1, True), (.002, .003, True, .09, True),
                    (.004, .007, True, .08, False), (.004, .008, False, .08, True),
                    (.006, .012, True, .075, True)]
        for sim, wall, tick, height, contact in sequence:
            f.pose(height); f.contact(distance=0. if contact else .1)
            old.record(f.full(), sim, wall, tick=tick)
            new.record(new.native_snapshot(f.cell), sim, wall, tick=tick)
            self.assertEqual(old.data, new.data)
        self.assertEqual(new.data['ticks_with_hold_predicate_false'], 2)
        self.assertEqual(new.data['physics_tick_checks'], 3)
        self.assertEqual(new.data['endpoint_checks'], 2)
        self.assertFalse(new.data['all_recorded_hold_checks_pass'])

    def test_missing_payload_preserves_failure_and_partial_accumulator_state(self):
        f = NativeFixture()
        old = ORIGINAL.HoldWindow('absent', 0., 0.)
        new = PROPOSED.HoldWindow('absent', 0., 0.)
        with self.assertRaises(StopIteration): old.record(f.full(), .002, .003, tick=True)
        with self.assertRaises(StopIteration): new.record(new.native_snapshot(f.cell), .002, .003, tick=True)
        self.assertEqual(old.data, new.data)
        self.assertEqual(new.data['ticks_with_hold_predicate_false'], 1)

    def test_missing_registered_body_or_collision_geometry_and_nonbox_refuse(self):
        f = NativeFixture(); f.cell.registry['ghost'] = {'kind': 'part'}
        with self.assertRaises(EvaluationError): f.full()
        with self.assertRaises(EvaluationError): PROPOSED.PayloadHoldSampler(f.cell, 'ghost')
        f = NativeFixture()
        for geom in f.sampler.geometries:
            f.cell.model.geom_contype[geom] = 0; f.cell.model.geom_conaffinity[geom] = 0
        with self.assertRaises(EvaluationError): f.full()
        with self.assertRaises(EvaluationError): PROPOSED.PayloadHoldSampler(f.cell, 'payload')
        f = NativeFixture()
        f.cell.model.geom_type[f.geometry['payload_main']] = mujoco.mjtGeom.mjGEOM_SPHERE
        with self.assertRaises(EvaluationError): f.full()
        with self.assertRaises(EvaluationError): f.sampler.snapshot()

    def test_new_tick_path_never_requests_other_objects_velocities_or_full_snapshot(self):
        f = NativeFixture(10)
        window = PROPOSED.HoldWindow('payload', 0., 0.)
        expected = f.sampler.snapshot()
        with patch.object(f.cell.evaluator, 'snapshot_cell', side_effect=AssertionError('No whole-world snapshot')), \
             patch.object(mujoco, 'mj_objectVelocity', side_effect=AssertionError('No unused velocity')):
            self.assertEqual(window.native_snapshot(f.cell), expected)
            window.record(window.native_snapshot(f.cell), .002, .003, tick=True)

    def test_model_or_physics_owner_replacement_refuses_cached_indices(self):
        f, other = NativeFixture(), NativeFixture()
        window = PROPOSED.HoldWindow('payload', 0., 0.); window.native_snapshot(f.cell)
        with self.assertRaises(ValueError): window.native_snapshot(other.cell)
        f.cell.model = other.cell.model
        with self.assertRaises(EvaluationError): f.sampler.snapshot()

    def test_applied_sources_and_archived_originals_match_exact_retained_guards(self):
        changed = {row['path']: row for row in INTEGRATION['changed']}
        for name, expected in BASES.items():
            if name in changed:
                self.assertEqual(digest(ARCHIVE / name), expected)
                self.assertEqual(digest(PROJECT / name), changed[name]['staged_sha256'])
            else:
                self.assertEqual(digest(PROJECT / name), expected)
        original_record = (ARCHIVE / 'Batch 01/Recovery Qualification/measurement.py').read_text(encoding='utf8').split('    def record(self, snapshot, sim, wall, *, tick):', 1)[1]
        applied_record = (PROJECT / 'Batch 01/Recovery Qualification/measurement.py').read_text(encoding='utf8').split('    def record(self, snapshot, sim, wall, *, tick):', 1)[1]
        self.assertEqual(original_record, applied_record)
        old = (ARCHIVE / 'Batch 01/Recovery Qualification/run_screen.py').read_text(encoding='utf8')
        new = (PROJECT / 'Batch 01/Recovery Qualification/run_screen.py').read_text(encoding='utf8')
        self.assertEqual(new.replace('self.hold_window.native_snapshot(self.cells[0])', 'self.snapshot()'), old)


if __name__ == '__main__': unittest.main()
