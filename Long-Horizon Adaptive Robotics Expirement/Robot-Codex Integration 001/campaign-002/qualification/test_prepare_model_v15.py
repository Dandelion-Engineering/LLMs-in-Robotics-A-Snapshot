"""Policy parity and cross-stage closure of prospective cleanup source inputs."""
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


V15 = load('quiescence_model_v15_test', HERE / 'prepare_model_v15.py')


class InventoryTests(unittest.TestCase):
    def test_all_model_policies_equal_v14_except_additive_inventory(self):
        with tempfile.TemporaryDirectory(prefix='rci-quiescence-policy-') as folder:
            root = Path(folder).resolve()
            for kind in ('smoke', 'stock', 'home'):
                old = V15.prior.prepare(kind, 'RCI001-test', 'fixture-' + kind, 24101, root / (kind + '-old.json'))
                new = V15.prepare(kind, 'RCI001-test', 'fixture-' + kind, 24101, root / (kind + '-new.json'))
                before, after = old.pop('runtime_input_files'), new.pop('runtime_input_files')
                self.assertEqual(old, new)
                self.assertTrue(set(before) <= set(after))
                self.assertTrue(set(V15.cleanup_inputs()) <= set(after))

    def test_constructor_refuses_overwrite_and_restores_prior_supplier(self):
        original = V15.prior.runtime_inputs
        with tempfile.TemporaryDirectory(prefix='rci-quiescence-exclusive-') as folder:
            path = Path(folder).resolve() / 'manifest.json'; path.write_text('retained', encoding='utf-8')
            with self.assertRaises(FileExistsError):
                V15.prepare('smoke', 'test', 'fixture', 24101, path)
            self.assertEqual(path.read_text(encoding='utf-8'), 'retained')
            self.assertIs(V15.prior.runtime_inputs, original)

    def test_method_and_six_lifecycle_schemas_required(self):
        names = V15.cleanup_inputs()
        for name in ('NATIVE_CLEANUP_CANCELLATION_V1.md', 'smoke-020-transport-failure-analysis.json', 'smoke-020-transport-failure-analysis.md'):
            self.assertIn((V15.CAMPAIGN / 'io-repair' / name).relative_to(V15.REPO).as_posix(), names)
        self.assertIn((V15.CAMPAIGN / 'io-repair/NATIVE_THREAD_QUIESCENCE_V1.md').relative_to(V15.REPO).as_posix(), names)
        self.assertIn((V15.CAMPAIGN / 'io-repair/NATIVE_THREAD_UNLOAD_SCHEDULING_V1.md').relative_to(V15.REPO).as_posix(), names)
        self.assertEqual(6, sum('/app-server-schema/v2/' in name for name in names))
        self.assertEqual(2, sum('/native-shutdown-source-001/' in name and name.endswith('.rs') for name in names))
        self.assertEqual(names, sorted(set(names)))

    def test_missing_method_or_schema_is_rejected(self):
        original = Path.is_file
        for name in ('native_cleanup_protocol.py', 'cleanup_transport.py', 'NATIVE_CLEANUP_CANCELLATION_V1.md', 'smoke-020-transport-failure-analysis.json', 'NATIVE_THREAD_UNLOAD_SCHEDULING_V1.md', 'NATIVE_THREAD_QUIESCENCE_V1.md', 'ThreadClosedNotification.json', 'codex-rs__app-server__src__outgoing_message.rs'):
            with self.subTest(name=name), patch.object(Path, 'is_file', lambda path: False if path.name == name else original(path)):
                with self.assertRaises(ValueError):
                    V15.cleanup_inputs()

    def test_native_inventory_binds_complete_quiescence_inputs(self):
        native = load('quiescence_native_inventory_test', HERE / 'prepare_native.py')
        names = {p.relative_to(V15.REPO).as_posix() for p in native.inventory()}
        self.assertTrue(set(V15.cleanup_inputs()) <= names)

    def test_host_inventory_binds_inputs_without_changing_original_caps(self):
        host = load('quiescence_host_inventory_test', HERE / 'host_probe.py')
        with tempfile.TemporaryDirectory(prefix='rci-quiescence-host-') as folder:
            path = Path(folder).resolve() / 'manifest.json'
            host.prepare(SimpleNamespace(manifest=path, run_id='fixture-host', revision='test', sim_cap_s=240,
                purpose='continuous-physics-during-durable-io'))
            value = json.loads(path.read_text(encoding='utf-8'))
            self.assertTrue(set(V15.cleanup_inputs()) <= set(value['runtime_input_files']))
            self.assertEqual((240, 300, 0, 24201), (value['sim_cap_s'], value['wall_cap_s'], value['model_turns_max'], value['noise_seed']))

    def test_raw_and_boundary_inventory_include_declared_method_and_inputs(self):
        import sys
        previous = sys.path[:]
        try:
            sys.path.insert(0, str(V15.CAMPAIGN / 'harness')); sys.path.insert(0, str(HERE))
            raw = load('quiescence_raw_inventory_test', V15.CAMPAIGN / 'harness/raw_event_preflight_v2.py')
            boundary = load('quiescence_boundary_inventory_test', HERE / 'boundary_suite_v3.py')
            required = set(V15.cleanup_inputs())
            self.assertTrue(required <= set(raw.required_sources()))
            self.assertTrue(required <= set(boundary.sources()))
        finally:
            sys.path[:] = previous


if __name__ == '__main__':
    unittest.main()
