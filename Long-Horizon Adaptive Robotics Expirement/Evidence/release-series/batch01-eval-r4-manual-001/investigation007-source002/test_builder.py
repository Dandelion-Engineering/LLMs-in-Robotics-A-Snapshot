"""Presentation integration boundaries; no physical or analysis reruns."""
from pathlib import Path
import gzip
import base64
import importlib.util
import json
import re
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('bounded007_builder_test', HERE / 'build_workspace.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BuilderBoundaryTests(unittest.TestCase):
    def fixture(self):
        return {'records': {k: [] for k in ('architecture', 'revision', 'run', 'result', 'note')},
                'evidence_runs': [{'run_id': 'fixed-slot', 'package': {'manifest': {'href': 'data/identity.json'}}}],
                'store_sha256': '0' * 64}

    def test_original_producer_and_verified_reader_paths(self):
        self.assertEqual(Path(builder.original.read_selected_trace.__code__.co_filename).parent,
                         builder.UPSTREAM)
        self.assertEqual(Path(builder.original.bind_analysis.__code__.co_filename).parent,
                         builder.READER)
        builder.verify_upstream()
        builder.original.verify_upstream()

    def test_compact_snapshot_roundtrip_and_lazy_boot(self):
        snapshot = self.fixture()
        html, archive = builder.render(snapshot, HERE / 'test-output' / 'index.html')
        packed = json.loads(re.search(r'<script id="map-data" type="application/json">(.*?)</script>', html, re.S)[1])
        decoded = json.loads(gzip.decompress(base64.b64decode(packed['data'])))
        self.assertEqual(decoded, snapshot)
        self.assertNotIn('__MAP_SNAPSHOT__', html)
        self.assertIn("if(state.tab==='playback'&&typeof renderPlayback", html)
        self.assertIn('playbackDeactivate()', html)
        self.assertIn('source-available bundles', html)
        self.assertIn('33554432', html)
        self.assertGreater(archive['uncompressed_bytes'], 0)

    def test_snapshot_and_html_overflow_are_refused(self):
        with patch.object(builder, 'MAX_SNAPSHOT_BYTES', 1):
            with self.assertRaisesRegex(ValueError, 'snapshot exceeds'):
                builder.render(self.fixture(), HERE / 'test-output' / 'index.html')
        with patch.object(builder, 'MAX_HTML_BYTES', 1):
            with self.assertRaisesRegex(ValueError, 'HTML exceeds'):
                builder.render(self.fixture(), HERE / 'test-output' / 'index.html')

    def test_nested_links_rebased_to_source(self):
        html, _ = builder.render(self.fixture(), HERE / 'test-output' / 'index.html')
        self.assertIn('href="../../Architecture%20Map/README.md"', html)
        self.assertIn('href="../../README.md"', html)


if __name__ == '__main__':
    unittest.main()
