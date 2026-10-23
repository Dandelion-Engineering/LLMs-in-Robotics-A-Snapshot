"""Probe orchestration tests using fake compilation, no actual MuJoCo model."""
import contextlib
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import descriptor_probe as probe
from test_descriptor import fixture


class ProbeTests(unittest.TestCase):
    def test_fresh_directory_is_required_before_import_or_compilation(self):
        with TemporaryDirectory(dir=probe.HERE) as directory, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                probe.main(['--output', directory])
            self.assertEqual(error.exception.code, 2)

    def test_fake_compilation_retains_three_exports_and_both_mutations(self):
        xml, registry, model, sources = fixture()
        cell = SimpleNamespace(build_scene=lambda **kwargs: (xml, registry))
        mujoco = SimpleNamespace(MjModel=SimpleNamespace(from_xml_string=lambda _: model))
        with TemporaryDirectory(dir=probe.HERE) as directory, patch.object(probe, 'physical_configuration_hash', return_value='a'*64):
            report, reference = probe.run_case(Path(directory), 3, 0, cell, mujoco, sources, None)
            self.assertTrue(report['descriptor_checks_passed'], report)
            self.assertEqual(len(report['exports']), 3)
            self.assertTrue(all(r['wall_s'] >= 0 for r in report['exports']))
            self.assertTrue(all(r['restored'] for r in report['mutation_checks'].values()))
            self.assertIsNotNone(reference)
            self.assertEqual(report['physical_success'], 'not_assessed')
            self.assertTrue((Path(directory) / 'n3-development-seed0' / 'result.json').exists())

    def test_unsupported_model_property_is_retained_not_called_physical_failure(self):
        xml, registry, model, sources = fixture(); model.unhandled = object()
        cell = SimpleNamespace(build_scene=lambda **kwargs: (xml, registry))
        mujoco = SimpleNamespace(MjModel=SimpleNamespace(from_xml_string=lambda _: model))
        with TemporaryDirectory(dir=probe.HERE) as directory, patch.object(probe, 'physical_configuration_hash', return_value='a'*64):
            report, reference = probe.run_case(Path(directory), 3, 0, cell, mujoco, sources, None)
            self.assertFalse(report['descriptor_checks_passed'])
            self.assertEqual(report['seal_error']['category'], 'unsupported_model_property')
            self.assertEqual(len(report['exports']), 3)
            self.assertTrue(all(r['observation']['export_state'] == 'unknown' for r in report['exports']))
            self.assertEqual(report['mutation_checks']['state'], 'not_run_unusable_baseline')
            self.assertEqual(report['physical_success'], 'not_assessed')
            self.assertIsNone(reference)


if __name__ == '__main__': unittest.main()
