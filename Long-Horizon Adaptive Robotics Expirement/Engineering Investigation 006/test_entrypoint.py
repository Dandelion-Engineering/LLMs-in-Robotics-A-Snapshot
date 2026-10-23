"""Presentation integration checks; temporary stores only, no experiment runs."""
import base64
import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("investigation006_builder_test", HERE / "build_workspace.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PresentationEntrypointTests(unittest.TestCase):
    def test_producer_helpers_keep_their_original_identity(self):
        self.assertEqual(Path(builder.read_derivatives.__code__.co_filename).resolve(),
                         builder.UPSTREAM / "derivative_adapter.py")
        self.assertEqual(Path(builder.bind_analysis.__code__.co_filename).resolve(),
                         HERE / "analysis_provenance.py")
        self.assertEqual(Path(builder.read_selected_trace.__code__.co_filename).resolve(),
                         builder.UPSTREAM / "selected_trace.py")

    def test_changed_upstream_binding_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            bindings = json.loads((HERE / "upstream-source-bindings.json").read_text(encoding="utf-8"))
            bindings["files"][0]["sha256"] = "0" * 64
            path = Path(temporary) / "changed-bindings.json"
            path.write_text(json.dumps(bindings), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Upstream source bytes differ"):
                builder.verify_upstream(path)

    def test_nested_output_links_and_embedded_presentation_provenance(self):
        output = HERE / "site-test" / "index.html"
        snapshot = {"presentation_implementation": {"version": "synthetic presentation fixture"}}
        html = builder.render(snapshot, output)
        self.assertIn('href="../../README.md"', html)
        self.assertIn('href="../../Architecture%20Map/README.md"', html)
        self.assertIn('href="../../Long-Horizon%20Adaptive%20Robotics%20Experiment%20Design/Contract.md"', html)
        self.assertIn("presentation_implementation:snapshot.presentation_implementation", html)
        encoded = html.split('<script id="map-data" type="application/json">', 1)[1].split("</script>", 1)[0]
        envelope = json.loads(encoded)
        decoded = json.loads(gzip.decompress(base64.b64decode(envelope["data"])))
        self.assertEqual(decoded, snapshot)


if __name__ == "__main__":
    unittest.main()
