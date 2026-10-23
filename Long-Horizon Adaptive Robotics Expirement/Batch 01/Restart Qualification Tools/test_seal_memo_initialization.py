"""Synthetic native-surface tests; no MuJoCo compilation, physics or queue."""
import ast
import copy
import gc
import hashlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
import weakref

import numpy as np

from prepare_seal_memo_patch import HERE, TARGET, ORIGINAL_SHA256
from test_descriptor import fixture


PROPOSED_SHA256 = '18c6106b09729230a38878225ee1a654f13c93ae7e21d40271cc250c494d6553'


def retained_sources():
    """Test the reviewed immutable pair without re-running the apply guard."""
    manifest = json.loads((HERE / 'seal-memo-initialization.manifest.json').read_text(encoding='utf-8'))
    sources = []
    for name, expected, key in (
            ('original.py', ORIGINAL_SHA256, 'staged_original_lf_sha256'),
            ('proposed.py', PROPOSED_SHA256, 'proposed_lf_sha256')):
        raw = (HERE / 'seal-memo-stage' / name).read_bytes()
        if manifest[key] != expected or hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('Retained seal-memo source differs from the reviewed pair: ' + name)
        sources.append(raw.decode('utf-8'))
    return sources


def modules():
    original, proposed = retained_sources()
    if str(TARGET.parent) not in sys.path:
        sys.path.insert(0, str(TARGET.parent))
    result = []
    for name, source in (('_seal_original', original), ('_seal_proposed', proposed)):
        module = types.ModuleType(name); module.__file__ = str(TARGET)
        exec(compile(source, str(TARGET), 'exec'), module.__dict__)
        result.append(module)
    return result


class TrackedArray(np.ndarray):
    reads = 0

    def tobytes(self, *args, **kwargs):
        type(self).reads += 1
        return super().tobytes(*args, **kwargs)


class SealInitializationTests(unittest.TestCase):
    def test_only_seal_initialization_changes_and_returned_evidence_is_identical(self):
        old, new = modules()
        integration_path = HERE / 'seal-memo-initialization.integration.json'
        if integration_path.exists():
            integration = json.loads(integration_path.read_text(encoding='utf-8'))
            self.assertTrue(integration['applied_at_utc'])
            self.assertEqual(Path(integration['target']).resolve(), TARGET.resolve())
            self.assertEqual(integration['old_sha256'], ORIGINAL_SHA256)
            self.assertEqual(integration['new_sha256'], PROPOSED_SHA256)
            self.assertEqual(hashlib.sha256(TARGET.read_bytes()).hexdigest(), PROPOSED_SHA256)
        sources = [ast.parse(source) for source in retained_sources()]
        for tree in sources:
            tree.body = [node for node in tree.body if not isinstance(node, ast.FunctionDef) or node.name != 'seal_model']
        self.assertEqual(ast.dump(sources[0]), ast.dump(sources[1]))
        for count in (3, 6, 10):
            xml, registry, model, bindings = fixture(count)
            baseline = old.seal_model(model, xml, registry, bindings)
            self.assertNotIn(model, old._SURFACE_MEMOS)
            proposed = new.seal_model(model, xml, registry, bindings)
            self.assertEqual(baseline, proposed)
            self.assertIn(model, new._SURFACE_MEMOS)
            args = (model, xml, registry, baseline)
            self.assertEqual(old.export_observation(*args, physical_configuration_sha256='a' * 64),
                             new.export_observation(*args, physical_configuration_sha256='a' * 64))

    def test_every_capture_still_reads_current_array_bytes_and_native_properties(self):
        _, new = modules(); xml, registry, model, sources = fixture()
        model.geom_size = model.geom_size.view(TrackedArray)
        seal = new.seal_model(model, xml, registry, sources)
        previous = TrackedArray.reads
        for _ in range(3):
            with patch.object(new, '_observed_surface', wraps=new._observed_surface) as observed:
                output = new.export_observation(model, xml, registry, seal, physical_configuration_sha256='b' * 64)
                self.assertEqual(output['export_state'], 'pass')
                self.assertGreater(observed.call_count, 10)
                self.assertGreater(TrackedArray.reads, previous)
                previous = TrackedArray.reads

    def test_first_capture_mutations_and_mark_transitions_match_original(self):
        for change in ('solver', 'array', 'nested', 'new_field', 'nonfinite', 'allowed_mark', 'invalid_mark'):
            with self.subTest(change=change):
                old, new = modules(); xml, registry, model, sources = fixture()
                baseline = old.seal_model(model, xml, registry, sources)
                eager = new.seal_model(model, xml, registry, sources)
                if change == 'solver': model.opt.iterations += 1
                if change == 'array': model.actuator_gainprm[0, 0] += 1
                if change == 'nested': model.opt.gravity = np.array([0., 0., -9.8])
                if change == 'new_field': model.unhandled = object()
                if change == 'nonfinite': model.geom_size[0, 0] = np.nan
                if change == 'allowed_mark': model.geom_rgba[eager['mark_indices'][0]] = [1., 1., 1., 1.]
                if change == 'invalid_mark': model.geom_rgba[eager['mark_indices'][0]] = [.5, .5, .5, 1.]
                outputs = [module.export_observation(model, xml, registry, seal, physical_configuration_sha256='c' * 64)
                           for module, seal in ((old, baseline), (new, eager))]
                self.assertEqual(outputs[0], outputs[1])
                self.assertEqual(outputs[1]['export_state'], 'pass' if change == 'allowed_mark' else 'unknown')

    def test_mutation_during_initialization_fails_closed_instead_of_sealing_new_baseline(self):
        _, new = modules(); xml, registry, model, sources = fixture()
        original = new._model_surface_sha
        def changed(model, seal):
            model.opt.iterations += 1
            return original(model, seal)
        with patch.object(new, '_model_surface_sha', side_effect=changed):
            with self.assertRaisesRegex(new.UnsupportedEvidence, 'changed during seal initialization'):
                new.seal_model(model, xml, registry, sources)
        self.assertNotIn(model, new._SURFACE_MEMOS)

    def test_eager_memo_does_not_keep_retired_model_alive_or_accept_tampered_seal(self):
        _, new = modules(); xml, registry, model, sources = fixture()
        seal = new.seal_model(model, xml, registry, sources)
        altered = copy.deepcopy(seal); altered['source_hashes']['cell.py'] = 'f' * 64
        self.assertEqual(new.export_observation(model, xml, registry, altered,
            physical_configuration_sha256='d' * 64)['export_state'], 'unknown')
        retained = weakref.ref(model); del model; gc.collect()
        self.assertIsNone(retained())
        self.assertEqual(len(new._SURFACE_MEMOS), 0)

    def test_nonweak_provider_keeps_original_full_read_fallback(self):
        _, new = modules(); xml, registry, model, sources = fixture()
        with patch.object(new._SURFACE_MEMOS, 'get', side_effect=TypeError('synthetic nonweak provider')):
            seal = new.seal_model(model, xml, registry, sources)
            self.assertEqual(new.export_observation(model, xml, registry, seal,
                physical_configuration_sha256='e' * 64)['export_state'], 'pass')
            model.opt.iterations += 1
            self.assertEqual(new.export_observation(model, xml, registry, seal,
                physical_configuration_sha256='e' * 64)['export_state'], 'unknown')


if __name__ == '__main__': unittest.main()
