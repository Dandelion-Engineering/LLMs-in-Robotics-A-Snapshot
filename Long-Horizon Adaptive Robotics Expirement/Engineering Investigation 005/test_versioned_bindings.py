"""Frozen helper paths at the selected Runtime 004 root; synthetic metadata only."""
import json
from pathlib import Path
import tempfile
import unittest

import qualified_restart as q


class FixedRuntimeBindingTests(unittest.TestCase):
    def indexed_freeze(self, directory, runtime):
        code = directory / "code.json"
        code.write_text(json.dumps({"runtime_root": str(runtime), "files": [
            q.source(runtime / (name + ".py")) for name in q.MODULES
        ]}), encoding="utf-8")
        code_ref = q.source(code)
        return {"artifacts": {"code": code_ref}, "code_sha256": code_ref["sha256"]}

    def test_frozen_index_imports_only_verified_selected_root_helpers(self):
        self.assertEqual(q.RUNTIME.resolve(), (q.HERE.parent / "Runtime 004").resolve())
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            freeze = self.indexed_freeze(root, q.RUNTIME)
            loader, classifier = q.runtime_api(freeze, root / "freeze.json", {})
            self.assertEqual(Path(loader.__file__).resolve(), (q.RUNTIME / "restart_calibration_loader.py").resolve())
            self.assertEqual(Path(classifier.__file__).resolve(), (q.RUNTIME / "restart_state.py").resolve())

    def test_identical_relocated_helpers_cannot_replace_frozen_paths(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); relocated = root / "other-runtime"; relocated.mkdir()
            for module in q.MODULES:
                source = q.RUNTIME / (module + ".py")
                (relocated / source.name).write_bytes(source.read_bytes())
                self.assertEqual(q.source(relocated / source.name)["sha256"], q.source(source)["sha256"])
            freeze = self.indexed_freeze(root, relocated)
            with self.assertRaisesRegex(ValueError, "Frozen code lacks qualified restart helper"):
                q.runtime_api(freeze, root / "freeze.json", {})


if __name__ == "__main__":
    unittest.main()
