"""Synthetic local path handling; no D-drive writes or browser-policy changes."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import analysis_adapter
import build_workspace
import evidence_adapter
import process_development
import selected_trace
from test_process_development import BatchFixture


class CrossVolumeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_local_drive_reference_binds_exact_assigned_source(self):
        f = BatchFixture(self.root); rid = f.add()
        for evidence in f.data["result"][0]["evidence"]:
            evidence["uri"] = (f.map / evidence["uri"]).resolve().as_posix()
        result = f.process([rid])
        self.assertEqual(result["runs"][0]["status"], "completed")
        self.assertEqual(f.diagnostics.diagnose_directory.call_args.args[0], (f.raw / rid).resolve())

    def test_nonlocal_schemes_unc_and_drive_relative_paths_are_rejected(self):
        for uri in ("file:///D:/raw/result.json", "https://example.test/data", "//server/share/x",
                    "\\\\server\\share\\x", "D:relative.json", "D:/raw/../result.json", "D:/raw/\nresult.json"):
            self.assertIsNone(process_development.canonical_local_path(uri, self.root), uri)
        self.assertEqual(process_development.canonical_local_path("../result.json", self.root),
                         (self.root.parent / "result.json").resolve())

    def test_absolute_wrong_location_or_hash_still_fails_original_binding(self):
        f = BatchFixture(self.root); rid = f.add()
        f.data["result"][0]["evidence"][0]["uri"] = (self.root / "wrong-result.json").as_posix()
        result = f.process([rid])
        self.assertEqual(result["runs"][0]["status"], "verification_failed")

    def test_volume_detection_is_drive_sensitive_and_case_insensitive(self):
        self.assertTrue(evidence_adapter.cross_volume("D:/raw/run", "C:/view.html"))
        self.assertFalse(evidence_adapter.cross_volume("C:/raw/run", "c:/view.html"))

    def test_cross_drive_selected_playback_retains_metadata_without_reading_streams(self):
        f = BatchFixture(self.root); rid = f.add(); run = f.raw / rid
        (run / "events.jsonl").write_bytes(b"MALFORMED STREAM MUST NOT BE READ")
        (run / "motion.jsonl").write_bytes(b"MALFORMED MOTION MUST NOT BE READ")
        actual_digest = selected_trace.digest_file
        def metadata_digest(path):
            self.assertIn(Path(path).name, ("manifest.json", "result.json"))
            return actual_digest(path)
        with patch.object(selected_trace, "cross_volume", return_value=True), \
             patch.object(analysis_adapter, "cross_volume", return_value=True), \
             patch.object(selected_trace, "digest_file", side_effect=metadata_digest), \
             patch.object(selected_trace, "read_run", side_effect=AssertionError("Must not read trace")):
            data = selected_trace.read_selected_trace({"run_id": rid, "reason": "Fixed test slot"}, run, self.root / "view.html")
            metadata = analysis_adapter.read_run_metadata(f.raw, self.root / "view.html")
        self.assertEqual(data["trace_availability"]["reason_code"], "cross_volume_playback_unavailable")
        self.assertEqual(data["trace_availability"]["missing_required_files"], [])
        self.assertEqual(data["events"], [])
        self.assertEqual(data["result"]["outcome"], "success")
        self.assertTrue(all(s["href"] is None and s["link_state"] == "unavailable" for s in data["source_files"]))
        self.assertEqual(metadata["runs"][0]["run_id"], rid)
        self.assertIsNone(metadata["runs"][0]["result_source"]["href"])

    def test_explicit_cross_drive_run_uses_same_unavailable_adapter(self):
        f = BatchFixture(self.root); rid = f.add(); run = f.raw / rid
        with patch.object(build_workspace, "cross_volume", return_value=True), \
             patch.object(selected_trace, "cross_volume", return_value=True), \
             patch.object(analysis_adapter, "cross_volume", return_value=True):
            data = build_workspace.read_display_run(run, self.root / "view.html", 2., 5.)
        self.assertEqual(data["run_id"], rid)
        self.assertEqual(data["trace_availability"]["state"], "unavailable")


if __name__ == "__main__": unittest.main()
