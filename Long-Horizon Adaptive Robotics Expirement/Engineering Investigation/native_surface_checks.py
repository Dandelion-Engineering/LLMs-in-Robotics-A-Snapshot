"""Bounded static equivalence/mutation checks; no mj_step, Cell or real evidence."""
import copy
from concurrent.futures import Future
import gc
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import weakref
import xml.etree.ElementTree as ET

import mujoco
import numpy as np

from stage_native_surface import BASE_SHA, HERE, PROJECT, STAGE, RELATIVE, sha

sys.path[:0] = [str(PROJECT / 'Runtime'), str(PROJECT / 'Batch 01/Restart Qualification Tools')]
from evaluator import IndependentEvaluator
import restart_state
from test_descriptor import fixture as synthetic_fixture, Surface


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


ORIGINAL = load('original_native_export', STAGE / 'original' / RELATIVE)
MANIFEST = json.loads((STAGE / 'manifest.json').read_text())
TARGET = PROJECT / RELATIVE if sha(PROJECT / RELATIVE) == MANIFEST['changed'][0]['staged_sha256'] else STAGE / RELATIVE
PROPOSED = load('proposed_native_export', TARGET)


def native_fixture(count=3):
    xml, registry, _, sources = synthetic_fixture(count)
    root = ET.fromstring(xml)
    for geom in root.findall('.//geom'):
        if geom.get('name', '').startswith('zone_'):
            geom.set('type', 'box'); geom.set('size', '.053 .053 .001')
        if geom.get('name', '').startswith('mark_'):
            geom.set('rgba', '.03 .03 .03 1')
    hand = ET.SubElement(root.find('worldbody'), 'body', name='hand', pos='0 0 .2')
    ET.SubElement(hand, 'site', name='tcp', size='.001')
    for name in ('left_finger', 'right_finger'):
        ET.SubElement(hand, 'body', name=name)
    xml = ET.tostring(root, encoding='unicode')
    model = mujoco.MjModel.from_xml_string(xml)
    seal = ORIGINAL.seal_model(model, xml, registry, sources)
    data = mujoco.MjData(model); mujoco.mj_forward(model, data)
    cell = SimpleNamespace(model=model, data=data, xml=xml, registry=registry,
        restart_physical_seal=seal, evaluator=IndependentEvaluator(), truth={}, station={},
        active_request=None, motion=[], segment=None, cycle=None, inspection_due=None,
        inspection=None, tcp=model.site('tcp').id, plan_generation=1, lease_deadline=None,
        direct_command=None, plan_future=None, pending_plan_generation=None,
        direct_plan_future=None, direct_plan_generation=None, _setup_wait=None,
        detection_time=0., last_sensor_result=None)
    return cell, sources


def export(module, cell, **overrides):
    values = dict(model=cell.model, xml=cell.xml, registry=cell.registry,
                  seal=cell.restart_physical_seal, physical_configuration_sha256='1' * 64)
    values.update(overrides)
    return module.export_observation(**values)


class SurfaceChecks(unittest.TestCase):
    def setUp(self): PROPOSED._SURFACE_MEMOS.clear()

    def equal(self, cell, expected='pass', **overrides):
        old, new = export(ORIGINAL, cell, **overrides), export(PROPOSED, cell, **overrides)
        self.assertEqual(new, old); self.assertEqual(new['export_state'], expected)
        return new

    def test_archived_original_and_staged_guards(self):
        manifest = json.loads((STAGE / 'manifest.json').read_text())
        self.assertEqual(sha(STAGE / 'original' / RELATIVE), BASE_SHA)
        self.assertEqual(sha(STAGE / RELATIVE), manifest['changed'][0]['staged_sha256'])
        self.assertIn(sha(PROJECT / RELATIVE), (BASE_SHA, manifest['changed'][0]['staged_sha256']))

    def test_first_and_repeated_native_exports_exact_for_three_and_ten(self):
        for count in (3, 10):
            cell, _ = native_fixture(count)
            for _ in range(3): self.equal(cell)
            self.assertEqual(PROPOSED._observed_surface(cell.model).descriptor, ORIGINAL._surface(cell.model))

    def test_same_time_model_array_mutations_and_restoration(self):
        cell, _ = native_fixture(); self.equal(cell)
        for name, index in [('body_mass', 1), ('geom_friction', (1, 0)), ('geom_solref', (1, 0)),
                            ('body_pos', (1, 0)), ('geom_rgba', (0, 0))]:
            with self.subTest(field=name):
                array = getattr(cell.model, name); old = array[index].copy()
                array[index] += .001
                self.equal(cell, 'unknown')
                array[index] = old; self.equal(cell)
                self.assertEqual(cell.data.time, 0.)

    def test_nested_native_options_and_nonfinite_detected_without_step(self):
        cell, _ = native_fixture(); self.equal(cell)
        old = cell.model.opt.iterations
        cell.model.opt.iterations = old + 1; self.equal(cell, 'unknown')
        cell.model.opt.iterations = old; self.equal(cell)
        old = cell.model.opt.gravity[0].copy()
        for value in (float('nan'), float('inf')):
            cell.model.opt.gravity[0] = value; self.equal(cell, 'unknown')
        cell.model.opt.gravity[0] = old; self.equal(cell)

    def test_mark_allowance_checked_each_call_with_exact_normalization(self):
        cell, _ = native_fixture(); self.equal(cell)
        index = cell.restart_physical_seal['mark_indices'][0]
        for color, state in [([1., 1., 1., 1.], 'pass'), ([.03, .03, .03, 1.], 'pass'),
                              ([.1, .03, .03, 1.], 'unknown'), ([float('nan'), 0, 0, 1], 'unknown'),
                              ([1., 1., 1., 1.], 'pass')]:
            cell.model.geom_rgba[index] = color; self.equal(cell, state)

    def test_xml_registry_seal_and_configuration_checks_remain_fresh(self):
        cell, _ = native_fixture(); self.equal(cell)
        self.equal(cell, 'unknown', xml=cell.xml + ' ')
        changed = copy.deepcopy(cell.registry); changed['A1']['hue'] += .001
        self.equal(cell, 'unknown', registry=changed)
        changed = copy.deepcopy(cell.restart_physical_seal); changed['part_count'] = 6
        self.equal(cell, 'unknown', seal=changed)
        self.equal(cell, 'unknown', seal=None)
        self.equal(cell, 'unknown', physical_configuration_sha256='broken')
        self.equal(cell, physical_configuration_sha256='2' * 64)
        changed = copy.deepcopy(cell.restart_physical_seal)
        changed['mark_indices'] = changed['mark_indices'][:-1]
        changed['seal_sha256'] = ORIGINAL.digest({k: v for k, v in changed.items() if k != 'seal_sha256'})
        self.equal(cell, 'unknown', seal=changed)

    def test_new_missing_unsupported_fields_dtype_shape_and_signed_zero(self):
        xml, registry, model, sources = synthetic_fixture()
        seal = ORIGINAL.seal_model(model, xml, registry, sources)
        cell = SimpleNamespace(model=model, xml=xml, registry=registry, restart_physical_seal=seal)
        self.equal(cell)
        for value in (object(), Surface(novel=1), np.array([1.])):
            model.new_field = value; self.equal(cell, 'unknown')
            del model.new_field; self.equal(cell)
        old = model.geom_size
        for value in (old.astype(np.float32), old.reshape(-1), np.full(old.shape, float('nan'))):
            model.geom_size = value; self.equal(cell, 'unknown')
        del model.geom_size; self.equal(cell, 'unknown')
        model.geom_size = old; self.equal(cell)
        model.opt.signed = 0.
        cell.restart_physical_seal = ORIGINAL.seal_model(model, xml, registry, sources)
        self.equal(cell)
        model.opt.signed = -0.; self.equal(cell, 'unknown')
        model.opt.signed = 0.; self.equal(cell)

    def test_exact_array_match_skips_hashing_but_rewalks_current_fields(self):
        cell, _ = native_fixture(); self.equal(cell)
        previous = PROPOSED._SURFACE_MEMOS[cell.model][2]
        with patch.object(PROPOSED.np, 'isfinite', side_effect=AssertionError('unchanged arrays')):
            current = PROPOSED._observed_surface(cell.model, previous)
        self.assertIs(current, previous)
        cell.model.opt.iterations += 1
        self.assertIsNot(PROPOSED._observed_surface(cell.model, previous), previous)
        self.equal(cell, 'unknown')

    def test_replaced_model_gets_its_own_verification(self):
        first, _ = native_fixture(); other, _ = native_fixture(); self.equal(first)
        self.assertEqual(len(PROPOSED._SURFACE_MEMOS), 1)
        self.equal(other); self.assertEqual(len(PROPOSED._SURFACE_MEMOS), 2)
        other.model.opt.iterations += 1; self.equal(other, 'unknown')
        self.equal(first)

    def test_returned_payload_changes_do_not_mutate_cached_evidence(self):
        cell, _ = native_fixture(); report = self.equal(cell)
        report['objects'][0]['compiled_mass_properties']['mass_kg'] = 999
        report['source_hashes']['cell.py'] = '0' * 64
        self.equal(cell)

    def test_weak_memo_releases_native_models_and_byte_baselines(self):
        cell, _ = native_fixture(); self.equal(cell); reference = weakref.ref(cell.model)
        self.assertEqual(len(PROPOSED._SURFACE_MEMOS), 1)
        del cell; gc.collect()
        self.assertIsNone(reference()); self.assertEqual(len(PROPOSED._SURFACE_MEMOS), 0)

    def test_rich_capture_dynamic_authority_devices_observation_and_classification(self):
        cell, sources = native_fixture()
        kwargs = dict(zones={'parking1': [.3, .04]}, zone_half=lambda _: [.053, .053],
                      exposure={'actual_cut': 'synthetic'}, source_hashes=sources)
        def captures():
            with patch.object(restart_state, 'export_observation', ORIGINAL.export_observation):
                old = restart_state.capture_restart_state(cell, **kwargs)
            with patch.object(restart_state, 'export_observation', PROPOSED.export_observation):
                new = restart_state.capture_restart_state(cell, **kwargs)
            self.assertEqual(new, old)
            self.assertEqual(restart_state.classify_restart(new), restart_state.classify_restart(old))
            return new
        before = captures()
        cell.plan_generation += 1; cell.active_request = {'request_id': 'admission'}
        cell.station = {'busy': True}; cell.last_sensor_result = SimpleNamespace(sequence=7)
        cell.plan_future = Future(); cell.data.ctrl[:] = .2
        middle = captures()
        cell.plan_future.set_result(None); after = captures()
        self.assertEqual(before['capture_sim_time_s'], after['capture_sim_time_s'])
        self.assertNotEqual(before['authority'], middle['authority'])
        self.assertFalse(middle['authority']['planner']['done']); self.assertTrue(after['authority']['planner']['done'])
        self.assertEqual(after['observation']['sequence'], 7)
        self.assertNotEqual(before['snapshot_sha256'], after['snapshot_sha256'])


if __name__ == '__main__': unittest.main()
