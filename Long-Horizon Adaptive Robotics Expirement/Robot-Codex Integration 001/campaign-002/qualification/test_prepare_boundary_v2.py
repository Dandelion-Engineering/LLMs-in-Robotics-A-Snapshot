"""Regression for boundary004's actual omitted measured markdown source."""
from pathlib import Path
import unittest
from unittest.mock import patch

import prepare_boundary_v2 as prepare


class InventoryTests(unittest.TestCase):
    def test_all_measured_sources_are_declared_including_actual_missing_readme(self):
        declared = prepare.inventory()
        measured = prepare.boundary_suite.sources()
        missing_readme = (prepare.CAMPAIGN / 'assessment/README.md').relative_to(prepare.REPO).as_posix()
        self.assertIn(missing_readme, measured)
        self.assertIn(missing_readme, declared)
        self.assertTrue(set(measured) <= set(declared))
        self.assertEqual(declared, sorted(set(declared)))

    def test_measured_nested_markdown_cannot_be_silently_omitted(self):
        path = prepare.REPO / 'Project Details/Project Lead.md'
        self.assertTrue(path.is_file())
        name = path.relative_to(prepare.REPO).as_posix()
        with patch.object(prepare.boundary_suite, 'sources', return_value={name: 'bound-digest'}):
            self.assertIn(name, prepare.inventory())

    def test_missing_measured_source_prevents_declaration(self):
        with patch.object(prepare.boundary_suite, 'sources', return_value={'does-not-exist.py': '0' * 64}):
            with self.assertRaisesRegex(ValueError, 'missing file'):
                prepare.inventory()


if __name__ == '__main__':
    unittest.main()
