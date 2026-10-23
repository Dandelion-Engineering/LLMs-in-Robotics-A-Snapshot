"""Bounded synthetic XML/models. Never instantiate Cell/MjModel or step physics."""
import copy
import colorsys
import math
import unittest
import xml.etree.ElementTree as ET

import numpy as np

from compatibility import box_aggregate, digest, verify_class_compatibility
from descriptor import (UnsupportedEvidence, _mass_properties, _surface, class_spec_from_seal,
                        export_observation, normalize_scene, seal_model)


class Surface:
    __module__ = 'mujoco.synthetic'
    def __init__(self, **values):
        self.__dict__.update(values)


class Model(Surface):
    __module__ = 'mujoco.synthetic'
    def body(self, name):
        return Surface(id=self.body_names.index(name))
    def geom(self, name):
        return Surface(id=self.geom_names.index(name))


def fixture(count=3, mass=.1, friction=1.2, layout_shift=0., hue_shift=0.):
    root = ET.Element('mujoco')
    ET.SubElement(root, 'option', timestep='.002', iterations='80', cone='elliptic')
    asset = ET.SubElement(root, 'asset')
    world = ET.SubElement(root, 'worldbody')
    ET.SubElement(world, 'geom', name='table', type='plane', size='1 1 .1')
    ET.SubElement(world, 'geom', name='zone_fixture', pos='.57 0 -.001')
    ET.SubElement(world, 'geom', name='zone_insert_home_B', pos='.18 -.34 -.001')
    registry = {}
    names = [f'{"A" if i % 2 == 0 else "B"}{i+1}' for i in range(count)] + ['insert_A', 'insert_B']
    for index, name in enumerate(names):
        kind = 'insert' if name.startswith('insert') else 'part'
        family = name[-1] if kind == 'insert' else name[0]
        half = [.025, .025, .008] if kind == 'insert' else [.021, .021, .018]
        hue = ((index + .25) / len(names) + hue_shift) % 1.
        registry[name] = {'kind': kind, 'family': family, 'half': half, 'hue': hue}
        ET.SubElement(asset, 'material', name='tagmat_' + name, rgba=' '.join(map(str, [*colorsys.hsv_to_rgb(hue, .95, .35), 1.])), emission='.7')
        row, col = divmod(index, 3)
        pos = ([.57, 0., .009] if name == 'insert_A' else [.18, -.34, .009]) if kind == 'insert' else [.32 + .085 * col + layout_shift, -.373 + .095 * row, .021]
        body = ET.SubElement(world, 'body', name=name, pos=' '.join(map(str, pos)))
        ET.SubElement(body, 'freejoint', name='free_' + name)
        ET.SubElement(body, 'geom', name='part_' + name, type='box', size=' '.join(map(str, half)), mass=str(mass), friction=f'{friction} .015 .001', condim='4')
        ET.SubElement(body, 'geom', name='tag_' + name, type='box', size='.014 .014 .0003', pos=f'0 0 {half[2]+.0004}', material='tagmat_' + name, mass='.0001', contype='0', conaffinity='0')
        ET.SubElement(body, 'geom', name='mark_' + name, type='box', size='.004 .014 .0003', pos=f'.018 0 {half[2]+.0004}', mass='.0001', contype='0', conaffinity='0')
    xml = ET.tostring(root, encoding='unicode')
    scene = normalize_scene(xml, registry)
    model = Model(body_names=names, geom_names=[p + n for n in names for p in ('part_', 'tag_', 'mark_')],
                  body_mass=[], body_ipos=[], body_inertia=[], body_iquat=[], geom_bodyid=[], geom_friction=[],
                  geom_rgba=[], opt=Surface(timestep=.002, iterations=80, cone=1),
                  actuator_gainprm=np.array([[1., 2., 3.]]), geom_size=np.array([[.021, .021, .018]]))
    for index, obs in enumerate(scene['objects']):
        properties = box_aggregate(scene['templates'][obs['kind'] + ':' + obs['family']], mass)
        # These templates have only x/z coupling; independently diagonalize the
        # 2x2 inertia block with a y-axis rotation (no simulator routines).
        tensor = properties['inertia_tensor_body_kg_m2']
        angle = .5 * math.atan2(2 * tensor[0][2], tensor[2][2] - tensor[0][0])
        r = np.array([[math.cos(angle), 0., math.sin(angle)], [0., 1., 0.], [-math.sin(angle), 0., math.cos(angle)]])
        diagonal = np.diag(r.T @ np.array(tensor) @ r)
        model.body_mass.append(properties['mass_kg']); model.body_ipos.append(properties['center_of_mass_body_m'])
        model.body_inertia.append(diagonal); model.body_iquat.append([math.cos(angle/2), 0., math.sin(angle/2), 0.])
        model.geom_bodyid.extend([index] * 3); model.geom_friction.extend([[friction, .015, .001], [1., .01, .001], [1., .01, .001]])
        model.geom_rgba.extend([[.6, .61, .62, 1.], [1., 1., 1., 1.], [.03, .03, .03, 1.]])
    for name in ('body_mass', 'body_ipos', 'body_inertia', 'body_iquat', 'geom_bodyid', 'geom_friction', 'geom_rgba'):
        setattr(model, name, np.array(getattr(model, name), dtype=np.float32 if name == 'geom_rgba' else None))
    sources = {name: digest(name) for name in ('descriptor_exporter', 'cell.py', 'actuation.py', 'evaluator.py', 'sensor_worker.py',
               'restart_state.py', 'restart_compatibility.py', 'restart_qualification.py', 'robot_assets', 'mujoco_build')}
    return xml, registry, model, sources


class DescriptorTests(unittest.TestCase):
    def test_current_six_and_ten_part_grid_accepts_planar_jitter_edges(self):
        row_centers = [-.373, -.278, -.183, -.088]
        for count in (6, 10):
            for x_offset in (-.003, .003):
                for y_offset in (-.003, .003):
                    with self.subTest(count=count, x_offset=x_offset, y_offset=y_offset):
                        xml, registry, _, _ = fixture(count, layout_shift=x_offset)
                        tree = ET.fromstring(xml)
                        for index in range(count):
                            identity = f'{"A" if index % 2 == 0 else "B"}{index+1}'
                            body = tree.find(f".//body[@name='{identity}']")
                            position = list(map(float, body.get('pos').split()))
                            position[1] += y_offset
                            body.set('pos', ' '.join(map(str, position)))
                        scene = normalize_scene(ET.tostring(tree, encoding='unicode'), registry)
                        for index, observed in enumerate(scene['objects'][:count]):
                            self.assertAlmostEqual(observed['initial_position_world_m'][1],
                                                   row_centers[index // 3] + y_offset)

    def test_six_and_ten_part_old_grid_or_old_pitch_is_rejected(self):
        for count in (6, 10):
            # The second case keeps the new first row: rejection must also
            # check later rows, not merely recognize the updated origin.
            for old_origin in (-.31, -.373):
                with self.subTest(count=count, old_origin=old_origin):
                    xml, registry, _, _ = fixture(count)
                    tree = ET.fromstring(xml)
                    for index in range(count):
                        identity = f'{"A" if index % 2 == 0 else "B"}{index+1}'
                        body = tree.find(f".//body[@name='{identity}']")
                        position = list(map(float, body.get('pos').split()))
                        position[1] = old_origin + .074 * (index // 3)
                        body.set('pos', ' '.join(map(str, position)))
                    with self.assertRaisesRegex(UnsupportedEvidence, 'raw stock outside declared initial slot jitter'):
                        normalize_scene(ET.tostring(tree, encoding='unicode'), registry)

    def test_declared_world_variation_preserves_class_but_exact_identity_changes(self):
        seals = []
        for count in (3, 6, 10):
            for mass, friction, offset in ((.0901, 1.101, -.002), (.1099, 1.299, .002)):
                xml, registry, model, sources = fixture(count, mass, friction, offset, offset)
                seal = seal_model(model, xml, registry, sources); seals.append(seal)
                spec = class_spec_from_seal(seals[0])
                obs = export_observation(model, xml, registry, seal, physical_configuration_sha256=digest([count, mass]))
                self.assertEqual(obs['export_state'], 'pass', obs)
                self.assertEqual(verify_class_compatibility(spec, obs, frozen_spec_sha256=digest(spec))['compatibility_state'], 'pass')
        self.assertEqual(len({s['scene_xml_sha256'] for s in seals}), 6)
        self.assertEqual(len({digest(s['component_sha256']) for s in seals}), 1)

    def test_new_fixed_xml_attribute_is_not_erased(self):
        xml, registry, _, _ = fixture()
        tree = ET.fromstring(xml); tree.find('option').set('noslip_iterations', '4')
        self.assertNotEqual(digest(normalize_scene(xml, registry)['fixed_xml']), digest(normalize_scene(ET.tostring(tree, encoding='unicode'), registry)['fixed_xml']))

    def test_new_entity_contact_setting_changes_template(self):
        xml, registry, _, _ = fixture()
        tree = ET.fromstring(xml)
        for geom in tree.findall(".//geom[@name='part_A1']") + tree.findall(".//geom[@name='part_A3']"):
            geom.set('solref', '.05 1')
        self.assertNotEqual(digest(normalize_scene(xml, registry)['templates']['part:A']), digest(normalize_scene(ET.tostring(tree, encoding='unicode'), registry)['templates']['part:A']))

    def test_out_of_domain_layout_palette_mass_and_population_reject(self):
        for params in ({'layout_shift': .004}, {'hue_shift': .005}, {'mass': .11}, {'friction': 1.3}, {'count': 9}):
            with self.subTest(params=params), self.assertRaises(UnsupportedEvidence):
                fixture(**params)

    def test_mass_construction_shape_rotation_or_extra_geom_is_unsupported(self):
        for case in ('rotate', 'shape', 'extra', 'missing'):
            xml, registry, _, _ = fixture(); tree = ET.fromstring(xml)
            body = tree.find(".//body[@name='A1']"); geom = body.find('geom')
            if case == 'rotate': geom.set('quat', '1 0 0 0')
            if case == 'shape': geom.set('type', 'sphere')
            if case == 'extra': ET.SubElement(body, 'geom', type='sphere')
            if case == 'missing': body.remove(geom)
            with self.subTest(case=case), self.assertRaises(UnsupportedEvidence):
                normalize_scene(ET.tostring(tree, encoding='unicode'), registry)

    def test_inertia_uses_principal_frame_rotation(self):
        model = Surface(body_mass=np.array([2.]), body_ipos=np.array([[.1, .2, .3]]),
                        body_inertia=np.array([[1., 2., 3.]]), body_iquat=np.array([[math.sqrt(.5), 0., 0., math.sqrt(.5)]]))
        got = _mass_properties(model, 0)
        self.assertTrue(np.allclose(got['inertia_tensor_body_kg_m2'], np.diag([2., 1., 3.])))
        self.assertEqual(got['center_of_mass_body_m'], [.1, .2, .3])

    def test_wrong_compiled_mass_or_friction_rejects_seal(self):
        for field in ('body_mass', 'geom_friction', 'body_ipos', 'body_inertia'):
            xml, registry, model, sources = fixture(); getattr(model, field).flat[0] += .001
            with self.subTest(field=field), self.assertRaises(UnsupportedEvidence): seal_model(model, xml, registry, sources)

    def test_each_post_compile_physical_change_is_unknown(self):
        for case in ('solver', 'actuator', 'geometry', 'mass', 'new_field'):
            xml, registry, model, sources = fixture(); seal = seal_model(model, xml, registry, sources)
            if case == 'solver': model.opt.iterations += 1
            if case == 'actuator': model.actuator_gainprm[0, 0] += 1
            if case == 'geometry': model.geom_size[0, 0] += .001
            if case == 'mass': model.body_mass[0] += .001
            if case == 'new_field': model.unlisted_new_solver_setting = 1
            with self.subTest(case=case):
                self.assertEqual(export_observation(model, xml, registry, seal, physical_configuration_sha256='1'*64)['export_state'], 'unknown')

    def test_process_mark_binary_visual_change_is_the_only_post_compile_exception(self):
        xml, registry, model, sources = fixture(); seal = seal_model(model, xml, registry, sources)
        model.geom_rgba[2] = [1., 1., 1., 1.]
        self.assertEqual(export_observation(model, xml, registry, seal, physical_configuration_sha256='1'*64)['export_state'], 'pass')
        model.geom_rgba[2] = [.5, .5, .5, 1.]
        self.assertEqual(export_observation(model, xml, registry, seal, physical_configuration_sha256='1'*64)['export_state'], 'unknown')

    def test_missing_changed_seal_xml_registry_or_hash_is_unknown(self):
        for case in ('missing', 'changed', 'xml', 'registry', 'exact_hash'):
            xml, registry, model, sources = fixture(); seal = seal_model(model, xml, registry, sources); exact = '1'*64
            if case == 'missing': seal = None
            if case == 'changed': seal['source_hashes']['cell.py'] = 'f'*64
            if case == 'xml': xml += ' '
            if case == 'registry': registry['A1']['hue'] += .001
            if case == 'exact_hash': exact = None
            with self.subTest(case=case): self.assertEqual(export_observation(model, xml, registry, seal, physical_configuration_sha256=exact)['export_state'], 'unknown')

    def test_nonfinite_array_or_unhandled_model_property_is_unsupported(self):
        for case in ('nan', 'object'):
            xml, registry, model, sources = fixture()
            if case == 'nan': model.actuator_gainprm[0, 0] = float('nan')
            else: model.unhandled = object()
            with self.subTest(case=case), self.assertRaises(UnsupportedEvidence): seal_model(model, xml, registry, sources)

    def test_vectorized_check_preserves_finite_empty_scalar_and_strided_arrays(self):
        for dtype in (np.float32, np.float64):
            for values in (np.array([], dtype=dtype), np.array(1., dtype=dtype),
                           np.array([0., -1., 2., 3.], dtype=dtype)[::2]):
                with self.subTest(dtype=dtype, shape=values.shape):
                    self.assertEqual(_surface(values)['shape'], list(values.shape))
            for bad in (float('nan'), float('inf'), -float('inf')):
                values = np.array([0., 1., bad, 2.], dtype=dtype)[::2]
                with self.subTest(dtype=dtype, bad=bad), self.assertRaises(UnsupportedEvidence):
                    _surface(values)

    def test_asset_source_or_binary_change_changes_class(self):
        xml, registry, model, sources = fixture(); initial = class_spec_from_seal(seal_model(model, xml, registry, sources))
        for key in sources:
            changed = copy.deepcopy(sources); changed[key] = 'f' * 64
            other = class_spec_from_seal(seal_model(model, xml, registry, changed))
            self.assertNotEqual(digest(initial), digest(other))


if __name__ == '__main__': unittest.main()
