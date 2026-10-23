"""Prepare temporary declarations only: no archive, registry, queue or runtime."""
import ast
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import prepare_boundary
import prepare_model
import prepare_native

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
REPO = CAMPAIGN.parent.parents[1]
PRIOR = CAMPAIGN.parent / 'readiness-session-10/assessment'
sys.path.insert(0, str(CAMPAIGN / 'assessment'))
import assess


def local_assessor_imports():
    """Follow actual local imports, rather than copy the preparers' source list."""
    modules = {path.stem: path for directory in (PRIOR, CAMPAIGN / 'assessment')
               for path in directory.glob('*.py')}
    pending = [CAMPAIGN / 'assessment/assess.py', CAMPAIGN / 'assessment/assess_smoke_v2.py']
    found = set()
    while pending:
        path = pending.pop()
        if path in found:
            continue
        found.add(path)
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            names = ([alias.name for alias in node.names] if isinstance(node, ast.Import) else
                     [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            pending.extend(modules[name] for name in names if name in modules)
    return {path.relative_to(REPO).as_posix() for path in found}


class PreparationClosureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def prepare(self, kind):
        module = {'native': prepare_native, 'boundary': prepare_boundary}.get(kind, prepare_model)
        output = self.root / (kind + '-manifest.json')
        argv = [str(Path(module.__file__)), '--revision', 'fixture-unregistered', '--run-id', 'fixture-' + kind,
                '--output', str(output)]
        if kind not in ('native', 'boundary'):
            argv += ['--kind', kind, '--seed', '24101']
        with mock.patch.object(sys, 'argv', argv), mock.patch.dict(os.environ, {'LOCALAPPDATA': str(self.root / 'local-app-data')}), redirect_stdout(io.StringIO()):
            module.main()
        return output, json.loads(output.read_text(encoding='utf-8'))

    def snapshot_view(self, manifest):
        # Existing registry contributes the old core TimingMonitor source. Only
        # a dictionary is assembled here; no snapshot/archive is written.
        names = set(manifest['runtime_input_files']) | {assess.TIMING_SOURCE}
        return {'revision': manifest['framework_revision'], 'sources':
                {name: {'sha256': assess.hash_file(REPO / name)} for name in names}}

    def test_all_preparers_cover_actual_assessor_import_closure_and_source_gate(self):
        required = local_assessor_imports()
        for kind in ('native', 'boundary', 'smoke', 'stock', 'home'):
            with self.subTest(kind=kind):
                output, manifest = self.prepare(kind)
                sources = manifest['runtime_input_files']
                self.assertEqual(len(sources), len(set(sources)))
                self.assertTrue(required <= set(sources), sorted(required - set(sources)))
                with mock.patch.object(assess, 'source_integrity', return_value=[]):
                    self.assertEqual(assess.frozen_problems(self.root / 'unused-snapshot.json',
                        self.snapshot_view(manifest), manifest['framework_revision']), [])
                self.assertTrue(output.is_file())
        self.assertFalse((self.root / 'local-app-data').exists())
        self.assertEqual({p.name for p in self.root.iterdir()},
                         {kind + '-manifest.json' for kind in ('native', 'boundary', 'smoke', 'stock', 'home')})

    def test_each_missing_legacy_import_reproduces_source_gate_failure_before_freeze(self):
        for kind in ('native', 'boundary'):
            _, manifest = self.prepare(kind)
            for filename in ('assess_bootstrap.py', 'assess_smoke.py', 'assess_pilot.py'):
                with self.subTest(kind=kind, missing=filename):
                    missing = (PRIOR / filename).relative_to(REPO).as_posix()
                    frozen = self.snapshot_view(manifest)
                    del frozen['sources'][missing]
                    with mock.patch.object(assess, 'source_integrity', return_value=[]):
                        problems = assess.frozen_problems(self.root / 'unused-snapshot.json', frozen,
                                                         manifest['framework_revision'])
                    self.assertIn('Required source absent from frozen inventory: ' + missing, problems)

    def test_existing_manifest_cannot_be_overwritten(self):
        for kind in ('native', 'boundary', 'smoke', 'stock', 'home'):
            with self.subTest(kind=kind):
                output, _ = self.prepare(kind)
                before = output.read_bytes()
                with self.assertRaises(FileExistsError):
                    self.prepare(kind)
                self.assertEqual(output.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
