"""Deferred source-only regression checks; no native compilation or actual evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent


def diagnostic_module():
    spec = importlib.util.spec_from_file_location('_compiled_identity_test', HERE/'compiled_identity.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class VersionedBindingTests(unittest.TestCase):
    def test_real_archive_paths_and_unchanged_physical_keys(self):
        assessor = (HERE/'Restart Qualification Tools/assess_validation.py').read_text(encoding='utf-8')
        self.assertIn("SOURCE_KEYS = ('cell.py', 'actuation.py', 'evaluator.py', 'sensor_worker.py')", assessor)
        self.assertIn("'Runtime 004/restart_state.py'", assessor)
        member = 'Batch 01/Release Lifecycle Repair 001/qualification-tools/Recovery Qualification/extract_screen.py'
        self.assertIn(member, assessor)
        self.assertTrue((HERE.parents[2]/member).is_file())
        self.assertNotIn("'Runtime/restart_state.py'", assessor)

    def test_exact_historical_plan_and_explicit_repeated_world_scope(self):
        original = HERE.parents[2]/'Batch 01/Recovery Profile Qualification/plan-001.json'
        current = HERE/'Recovery Profile Qualification/plan-001.json'
        self.assertEqual(current.read_bytes(), original.read_bytes())
        declaration = json.loads((HERE/'Recovery Profile Qualification/relocation-declaration-001.json').read_bytes())
        self.assertTrue(declaration['worlds_previously_inspected'])
        self.assertFalse(declaration['held_out_evidence'])
        self.assertEqual(declaration['runtime_directory'], 'Runtime 004')

    def test_descriptive_xml_equality_does_not_turn_class_mismatch_into_equality(self):
        module = diagnostic_module()
        old = {'inputs_before': {'cell.py': {'sha256': 'a', 'bytes': 1}},
            'sources_before': {'robot_assets': 'assets', 'mujoco_build': 'native'},
            'compiled_surface_sha256': 'surface', 'class_spec': {'component_sha256': {'geometry': 'old'}},
            'actual_compiler_meshdir': 'old/assets'}
        new = copy.deepcopy(old); new['class_spec']['component_sha256']['geometry'] = 'new'
        new['actual_compiler_meshdir'] = 'new/assets'
        report = module.compare(old, new, '<compiler meshdir="old"/>', '<compiler meshdir="new"/>', 'descriptive', 'descriptive')
        self.assertTrue(report['descriptive_path_normalized_xml_equal'])
        self.assertFalse(report['exact_xml_equal'])
        self.assertFalse(report['class_spec_equal'])
        self.assertTrue(report['compiled_surface_equal'])
        self.assertEqual(report['component_differences']['geometry'], {'original': 'old', 'relocated': 'new'})

    def test_compare_retains_source_asset_additions_and_mutations(self):
        module = diagnostic_module()
        old = {'inputs_before': {'cell.py': {'sha256': 'a', 'bytes': 1}},
            'sources_before': {'robot_assets': 'assets', 'mujoco_build': 'native'},
            'compiled_surface_sha256': 'surface', 'class_spec': {'component_sha256': {'geometry': 'old'}},
            'actual_compiler_meshdir': 'old/assets'}
        new = copy.deepcopy(old); new['inputs_before']['cell.py']['sha256'] = 'changed'
        new['inputs_before']['vendor/panda/extra'] = {'sha256': 'extra', 'bytes': 2}
        new['sources_before']['robot_assets'] = 'different'
        report = module.compare(old, new, 'same', 'same', 'same', 'same')
        self.assertEqual([row['path'] for row in report['source_and_asset_differences']], ['cell.py', 'vendor/panda/extra'])
        self.assertFalse(report['source_hashes_equal'])
        self.assertFalse(report['asset_bytes_equal'])


if __name__ == '__main__': unittest.main()
