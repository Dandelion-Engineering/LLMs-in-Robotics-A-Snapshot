"""Policy parity and cross-stage closure of prepared-startup source inputs."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


V17 = load('quiescence_model_v17_test', HERE / 'prepare_model_v17.py')


class InventoryTests(unittest.TestCase):
    def test_all_model_policies_equal_v16_except_additive_inventory(self):
        with tempfile.TemporaryDirectory(prefix='rci-quiescence-policy-') as folder:
            root = Path(folder).resolve()
            for kind in ('smoke', 'stock', 'home'):
                old = V17.prior.prepare(kind, 'RCI001-test', 'fixture-' + kind, 24101, root / (kind + '-old.json'))
                new = V17.prepare(kind, 'RCI001-test', 'fixture-' + kind, 24101, root / (kind + '-new.json'))
                before, after = old.pop('runtime_input_files'), new.pop('runtime_input_files')
                self.assertEqual(old, new)
                self.assertTrue(set(before) <= set(after))
                self.assertTrue(set(V17.prepared_startup_inputs()) <= set(after))

    def test_constructor_refuses_overwrite_and_restores_prior_supplier(self):
        original = V17.prior.runtime_inputs
        with tempfile.TemporaryDirectory(prefix='rci-quiescence-exclusive-') as folder:
            path = Path(folder).resolve() / 'manifest.json'; path.write_text('retained', encoding='utf-8')
            with self.assertRaises(FileExistsError):
                V17.prepare('smoke', 'test', 'fixture', 24101, path)
            self.assertEqual(path.read_text(encoding='utf-8'), 'retained')
            self.assertIs(V17.prior.runtime_inputs, original)

    def test_prepared_startup_inputs_and_prior_lifecycle_contract_are_required(self):
        names = V17.prepared_startup_inputs()
        for name in ('PREPARED_STARTUP_SEGMENTS_V1.md', 'smoke-022-read-proof-diagnosis.json', 'smoke-022-read-proof-diagnosis.md'):
            self.assertIn((V17.CAMPAIGN / 'io-repair' / name).relative_to(V17.REPO).as_posix(), names)
        self.assertIn((V17.CAMPAIGN / 'io-repair/NATIVE_THREAD_QUIESCENCE_V1.md').relative_to(V17.REPO).as_posix(), names)
        self.assertIn((V17.CAMPAIGN / 'io-repair/NATIVE_THREAD_UNLOAD_SCHEDULING_V1.md').relative_to(V17.REPO).as_posix(), names)
        self.assertEqual(6, sum('/app-server-schema/v2/' in name for name in names))
        self.assertEqual(2, sum('/native-shutdown-source-001/' in name and name.endswith('.rs') for name in names))
        self.assertEqual(names, sorted(set(names)))

    def test_missing_method_or_schema_is_rejected(self):
        original = Path.is_file
        for name in ('prepared_result_segments.py', 'prepared_startup_segments.py', 'test_prepared_result_segments.py', 'PREPARED_STARTUP_SEGMENTS_V1.md', 'smoke-022-read-proof-diagnosis.json', 'smoke-022-read-proof-diagnosis.md', 'source-evidence-003.json', 'native_cleanup_protocol.py', 'ThreadClosedNotification.json'):
            with self.subTest(name=name), patch.object(Path, 'is_file', lambda path: False if path.name == name else original(path)):
                with self.assertRaises(ValueError):
                    V17.prepared_startup_inputs()

    def test_each_new_input_is_bound_and_symlink_is_rejected(self):
        names = set(V17.prepared_startup_inputs())
        for relative in V17.PREPARED_STARTUP_INPUTS:
            self.assertIn((V17.CAMPAIGN / relative).relative_to(V17.REPO).as_posix(), names)
        target = V17.CAMPAIGN / 'assessment/prepared_result_segments.py'
        original = Path.is_symlink
        with patch.object(Path, 'is_symlink', lambda path: path == target or original(path)):
            with self.assertRaisesRegex(ValueError, 'Missing or linked prepared-startup input'):
                V17.prepared_startup_inputs()

    def test_complete_native_packet_and_prior_inventory_are_bound(self):
        names = set(V17.prepared_startup_inputs())
        packet = V17.CAMPAIGN / 'io-repair/native-output-source-003'
        declared = {V17.CAMPAIGN / name for name in V17.PREPARED_STARTUP_INPUTS
                    if name.startswith('io-repair/native-output-source-003/')}
        self.assertEqual(declared, {p for p in packet.iterdir() if p.is_file()})
        self.assertEqual(len(declared), 18)
        self.assertTrue(set(V17.prior.read_evidence_inputs()) <= names)
        self.assertTrue({p.relative_to(V17.REPO).as_posix() for p in declared} <= names)

    def test_native_inventory_binds_complete_quiescence_inputs(self):
        native = load('quiescence_native_inventory_test', HERE / 'prepare_native.py')
        names = {p.relative_to(V17.REPO).as_posix() for p in native.inventory()}
        self.assertTrue(set(V17.prepared_startup_inputs()) <= names)

    def test_host_inventory_binds_inputs_without_changing_original_caps(self):
        host = load('quiescence_host_inventory_test', HERE / 'host_probe.py')
        with tempfile.TemporaryDirectory(prefix='rci-quiescence-host-') as folder:
            path = Path(folder).resolve() / 'manifest.json'
            host.prepare(SimpleNamespace(manifest=path, run_id='fixture-host', revision='test', sim_cap_s=240,
                purpose='continuous-physics-during-durable-io'))
            value = json.loads(path.read_text(encoding='utf-8'))
            self.assertTrue(set(V17.prepared_startup_inputs()) <= set(value['runtime_input_files']))
            self.assertEqual((240, 300, 0, 24201), (value['sim_cap_s'], value['wall_cap_s'], value['model_turns_max'], value['noise_seed']))

    def test_raw_and_boundary_inventory_include_declared_method_and_inputs(self):
        import sys
        previous = sys.path[:]
        try:
            sys.path.insert(0, str(V17.CAMPAIGN / 'harness')); sys.path.insert(0, str(HERE))
            raw = load('quiescence_raw_inventory_test', V17.CAMPAIGN / 'harness/raw_event_preflight_v2.py')
            boundary = load('quiescence_boundary_inventory_test', HERE / 'boundary_suite_v3.py')
            required = set(V17.prepared_startup_inputs())
            self.assertTrue(required <= set(raw.required_sources()))
            self.assertTrue(required <= set(boundary.sources()))
        finally:
            sys.path[:] = previous


if __name__ == '__main__':
    unittest.main()
