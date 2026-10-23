"""Synthetic-only packaging regressions; production execution is queue-gated."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import trace_package as package


class TracePackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)

    def roundtrip(self, value):
        before = copy.deepcopy(value)
        ref = package.write_value(value, self.output)
        self.assertEqual(package.read_value(ref, self.output), before)
        self.assertEqual(value, before)
        for path in (self.output / "data").iterdir():
            limit = package.MAX_UTF8_BYTES if path.suffix == ".utf8" else package.MAX_JSON_BYTES
            self.assertLessEqual(path.stat().st_size, limit)
        return ref

    def fixture(self):
        payload = {"message": {"packet": {"sequence": 17, "detections": []}},
                   "text": "Actual fixture text only. " * 1800}
        original_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                                  allow_nan=False).encode()).hexdigest()
        return {"run_id": "synthetic-fixture-only", "manifest": {"architecture": "fixture"},
                "result": {"execution_status": "failed", "outcome": "unknown"},
                "trace_availability": {"state": "available"},
                "selection_entry": {"run_id": "synthetic-fixture-only", "reason": "Fixed fixture slot"},
                "source_files": [{"name": "events.jsonl", "sha256": "e" * 64, "bytes": 321,
                                  "href": "../../original/events.jsonl"}],
                "sampling": {"observation_target_hz": 2, "motion_target_hz": 5,
                             "event_gaps": [{"after_event_id": 1, "before_event_id": 3}]},
                "events": [{"event_id": 3, "event_type": "candidate_input", "payload": payload,
                            "payload_sha256": original_hash, "parent_ids": [1], "sim_time_s": .5,
                            "wall_elapsed_s": .6, "wall_clock_scope": "task",
                            "artifact_refs": {"rgb": {"state": "available", "href": "../../frames/actual.png",
                                                      "sha256": "f" * 64, "bytes": 123}}}],
                "motion": [{"sim_time_s": .2, "q": [0, 1.25], "tcp": [0, 0, .1]},
                           {"sim_time_s": .4, "q": [1, 2.5], "tcp": [0, 0, .2]}]}

    def test_scalar_nested_and_reserved_keys_roundtrip(self):
        self.roundtrip({"format": package.VALUE_FORMAT, "node": ["r", {"href": "malicious"}],
                        "payload_ref": None, "cues": {"tag": "S"}, "empty": [{}, [], ""],
                        "values": [None, False, True, 42, -3, 1.25, -0.0],
                        "special": "</script> & Ω \u2028 \u2029"})

    def test_large_unicode_strings_keys_and_escaped_surrogates(self):
        value = {"Ω🙂" * 12000: "A🙂Ωé" * 30000,
                 "surrogate": "before\ud800after" * 4000}
        self.roundtrip(value)
        chunks = list((self.output / "data").glob("*.utf8"))
        self.assertTrue(chunks)
        for path in chunks:
            path.read_bytes().decode("utf-8", errors="strict")

    def test_large_containers_split_recursively_without_loss(self):
        value = {"array": list(range(1000)),
                 "object": {"key-" + str(index): [index, "value-" + str(index)] for index in range(500)}}
        with patch.object(package, "MAX_JSON_BYTES", 2048), patch.object(package, "INLINE_NODE_BYTES", 256):
            self.roundtrip(value)
        documents = [json.loads(path.read_text(encoding="utf-8")) for path in (self.output / "data").glob("*.json")]
        tags = {document["node"][0] for document in documents}
        self.assertTrue(tags.intersection(("A", "O")))

    def test_exact_trace_roundtrip_keeps_sampling_headers_and_source_links(self):
        run = self.fixture()
        before = copy.deepcopy(run)
        descriptor = package.write_trace(run, self.output, 4)
        result = package.verify_trace(run, descriptor, self.output)
        self.assertEqual(result["state"], "verified")
        self.assertEqual(run, before)
        self.assertNotIn("events", descriptor)
        self.assertNotIn("motion", descriptor)
        self.assertEqual(descriptor["sampling"]["observation_target_hz"], run["sampling"]["observation_target_hz"])
        self.assertEqual(descriptor["sampling"]["motion_target_hz"], run["sampling"]["motion_target_hz"])
        self.assertEqual(descriptor["sampling"]["event_gap_count"], len(run["sampling"]["event_gaps"]))
        self.assertNotIn("event_gaps", descriptor["sampling"])
        self.assertEqual(descriptor["source_files"], run["source_files"])
        manifest = package.read_manifest(descriptor, self.output)
        self.assertEqual(manifest["ordinal"], 4)
        self.assertEqual(manifest["format"], "robot-trace-manifest-2.0")
        self.assertEqual(manifest["metadata_ref"], descriptor["package"]["metadata_ref"])
        self.assertEqual(package.read_value(manifest["metadata_ref"], self.output),
                         {key: value for key, value in run.items() if key not in ("events", "motion")})
        header = manifest["event_headers"][0]
        self.assertNotIn("payload", header)
        self.assertEqual(header["payload_sha256"], run["events"][0]["payload_sha256"])
        self.assertEqual(header["artifact_refs"], run["events"][0]["artifact_refs"])
        self.assertEqual(header["cues"]["packet_sequence"], 17)
        self.assertTrue(header["cues"]["has_packet"])
        stats = descriptor["package"]["stats"]
        paths = list((self.output / "data").iterdir())
        self.assertEqual(stats["artifact_count"], len(paths))
        self.assertEqual(stats["artifact_bytes"], sum(path.stat().st_size for path in paths))

    def test_unavailable_administrative_slot_stays_unavailable_unknown(self):
        run = self.fixture()
        run.update(events=[], motion=[], result=None, sampling=None,
                   trace_availability={"state": "unavailable", "reason_code": "administrative_interruption"},
                   administrative_projection={"outcome": "unknown", "physical_end": None})
        descriptor = package.write_trace(run, self.output, 0)
        package.verify_trace(run, descriptor, self.output)
        self.assertIsNone(descriptor["result"])
        self.assertEqual(descriptor["administrative_projection"], run["administrative_projection"])
        self.assertEqual(descriptor["trace_availability"], run["trace_availability"])

    def test_cues_preserve_packet_and_nested_event_identity(self):
        event = {"event_type": "candidate_reply", "payload": {
            "request_id": "request-3", "packet": {}, "message": {"packet": {"sequence": 9}},
            "events": [{"type": "context_read", "path": "memory/a.md"}, "not-an-object", {"type": "write"}],
            "stale": True, "after_episode_end": False}}
        cues = package.event_cues(event)
        self.assertEqual(cues, {"request_id": "request-3", "has_packet": True, "packet_sequence": None,
                                "candidate_events": [{"index": 0, "type": "context_read", "path": "memory/a.md"},
                                                     {"index": 2, "type": "write", "path": None}],
                                "stale": True, "after_episode_end": False})
        self.assertEqual(package.event_cues({"event_type": "scenario_exposure", "payload": []})["candidate_events"], [])

    def test_deterministic_content_addressing_deduplicates(self):
        run = self.fixture()
        first = package.write_trace(run, self.output, 2)
        paths = set((self.output / "data").iterdir())
        second = package.write_trace(run, self.output, 2)
        self.assertEqual(first, second)
        self.assertEqual(paths, set((self.output / "data").iterdir()))
        package.verify_trace(run, second, self.output)

    def test_existing_content_addressed_file_is_never_overwritten(self):
        ref = package.write_value({"safe": "original"}, self.output)
        path = self.output / ref["href"]
        corrupt = b"x" * ref["bytes"]
        path.write_bytes(corrupt)
        with self.assertRaisesRegex(ValueError, "Existing content-addressed artifact differs"):
            package.write_value({"safe": "original"}, self.output)
        self.assertEqual(path.read_bytes(), corrupt)

    def test_ref_hash_size_path_and_corrupt_content_are_rejected(self):
        ref = package.write_value({"safe": "original"}, self.output)
        for changes in ({"bytes": ref["bytes"] + 1}, {"bytes": True}, {"sha256": "0" * 64},
                        {"href": "../outside.json"}, {"href": "https://example.invalid/value.json"},
                        {"href": "data/../outside.json"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                package.read_value({**ref, **changes}, self.output)
        path = self.output / ref["href"]
        path.write_bytes(b"x" * ref["bytes"])
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            package.read_value(ref, self.output)

    def test_reserved_envelope_keys_and_non_json_values_refuse(self):
        for key in ("payload_ref", "cues"):
            run = self.fixture()
            run["events"][0][key] = {"original": True}
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "collides"):
                package.write_trace(run, self.output, 0)
        run = self.fixture()
        run["package"] = {"original": True}
        with self.assertRaisesRegex(ValueError, "collides"):
            package.write_trace(run, self.output, 0)
        for value in (float("nan"), float("inf"), {1: "non-string key"}, {1, 2}, (1, 2)):
            with self.subTest(kind=type(value).__name__), self.assertRaises(ValueError):
                package.write_value(value, self.output)

    def test_descriptor_and_manifest_overflow_refuse_without_downsampling(self):
        run = self.fixture()
        before = copy.deepcopy(run)
        with patch.object(package, "MAX_DESCRIPTOR_BYTES", 2100):
            with self.assertRaisesRegex(ValueError, "descriptor byte limit"):
                package.write_trace(run, self.output, 0)
        with patch.object(package, "MAX_MANIFEST_BYTES", 100):
            with self.assertRaisesRegex(ValueError, "byte limit"):
                package.write_trace(run, self.output, 0)
        self.assertEqual(run, before)

    def test_changed_descriptor_and_roundtrip_input_are_rejected(self):
        run = self.fixture()
        descriptor = package.write_trace(run, self.output, 0)
        changed_descriptor = copy.deepcopy(descriptor)
        changed_descriptor["run_id"] = "wrong-run"
        with self.assertRaisesRegex(ValueError, "identity or metadata"):
            package.read_manifest(changed_descriptor, self.output)
        changed = copy.deepcopy(run)
        changed["events"][0]["payload"]["text"] += "changed"
        with self.assertRaisesRegex(ValueError, "payload differs"):
            package.verify_trace(changed, descriptor, self.output)

    def test_metadata_over_256k_is_lossless_and_summary_stays_bounded(self):
        run = self.fixture()
        run["sampling"]["event_gaps"] = [
            {"after_event_id": index * 3, "before_event_id": index * 3 + 2, "missing_count": 1}
            for index in range(8000)]
        run["sampling"]["motion_intervals_over_30ms"] = [
            {"from_s": index / 5, "to_s": index / 5 + .04} for index in range(4000)]
        run["manifest"]["configuration"] = {"source_bound_description": "unchanged full configuration " * 16000}
        run["result"]["resource_windows"] = [{"index": index, "rtf": .98} for index in range(3000)]
        run["result"]["camera_gap_samples"] = [
            {"from_s": index / 2, "to_s": index / 2 + .6, "gap_s": .6}
            for index in range(6000)]
        run["result"]["timing"] = {"windows": [{"wall_s": index, "sim_s": index * .99}
                                                 for index in range(2000)]}
        run["metadata_projection"] = {"format": "ordinary original metadata key", "must_remain": True}
        before = copy.deepcopy(run)
        metadata = {key: value for key, value in run.items() if key not in ("events", "motion")}
        self.assertGreater(len(json.dumps(metadata).encode("utf-8")), package.MAX_DESCRIPTOR_BYTES)
        descriptor = package.write_trace(run, self.output, 5)
        verification = package.verify_trace(run, descriptor, self.output)
        self.assertTrue(verification["full_metadata_roundtrip_equal"])
        self.assertEqual(run, before)
        self.assertLessEqual(len(json.dumps(descriptor).encode("utf-8")), package.MAX_DESCRIPTOR_BYTES)
        self.assertEqual(descriptor["metadata_projection"]["format"], package.SUMMARY_FORMAT)
        self.assertFalse(descriptor["metadata_projection"]["full_metadata_included"])
        self.assertEqual(descriptor["sampling"]["event_gap_count"], 8000)
        self.assertEqual(descriptor["sampling"]["motion_intervals_over_30ms_count"], 4000)
        self.assertNotIn("configuration", descriptor["manifest"])
        self.assertNotIn("resource_windows", descriptor["result"])
        self.assertNotIn("camera_gap_samples", descriptor["result"])
        self.assertNotIn("timing", descriptor["result"])
        self.assertNotIn("event_gaps", descriptor["sampling"])
        self.assertIn("/sampling/event_gaps", descriptor["metadata_projection"]["deferred_fields"])
        self.assertEqual(package.read_value(descriptor["package"]["metadata_ref"], self.output), metadata)
        manifest_path = self.output / descriptor["package"]["manifest"]["href"]
        self.assertLessEqual(manifest_path.stat().st_size, package.MAX_MANIFEST_BYTES)
        for path in (self.output / "data").iterdir():
            if path == manifest_path:
                continue
            self.assertLessEqual(path.stat().st_size,
                                 package.MAX_UTF8_BYTES if path.suffix == ".utf8" else package.MAX_JSON_BYTES)

    def test_long_display_fields_and_source_lists_are_deferred_not_truncated(self):
        run = self.fixture()
        run["selection_entry"]["reason"] = "exact declared reason " * 200
        run["result"]["validity_reason"] = "exact validity explanation " * 200
        run["source_files"] = [{"name": "source-" + str(index), "href": "../../source-" + str(index),
                                "sha256": "a" * 64, "bytes": index + 1}
                               for index in range(package.MAX_SUMMARY_SOURCE_FILES + 1)]
        descriptor = package.write_trace(run, self.output, 0)
        self.assertNotIn("reason", descriptor["selection_entry"])
        self.assertNotIn("validity_reason", descriptor["result"])
        self.assertNotIn("source_files", descriptor)
        self.assertEqual(descriptor["source_file_count"], len(run["source_files"]))
        deferred = descriptor["metadata_projection"]["deferred_fields"]
        for path in ("/selection_entry/reason", "/result/validity_reason", "/source_files"):
            self.assertIn(path, deferred)
        metadata = package.read_value(descriptor["package"]["metadata_ref"], self.output)
        for key in ("selection_entry", "result", "source_files"):
            self.assertEqual(metadata[key], run[key])
        package.verify_trace(run, descriptor, self.output)

    def test_metadata_reference_tampering_and_wrong_full_metadata_refuse(self):
        run = self.fixture()
        descriptor = package.write_trace(run, self.output, 0)
        replacement = package.write_value({"run_id": run["run_id"], "wrong": "metadata"}, self.output)
        changed_descriptor = copy.deepcopy(descriptor)
        changed_descriptor["package"]["metadata_ref"] = replacement
        with self.assertRaisesRegex(ValueError, "identity or metadata"):
            package.read_manifest(changed_descriptor, self.output)
        changed_manifest = package.read_manifest(descriptor, self.output)
        changed_manifest["metadata_ref"] = replacement
        raw = json.dumps(changed_manifest, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("ascii")
        digest = hashlib.sha256(raw).hexdigest()
        forged_ref = {"href": "data/" + digest + ".json", "sha256": digest, "bytes": len(raw)}
        (self.output / forged_ref["href"]).write_bytes(raw)
        changed_descriptor["package"]["manifest"] = forged_ref
        with self.assertRaisesRegex(ValueError, "full trace metadata differs"):
            package.verify_trace(run, changed_descriptor, self.output)
        original_metadata_path = self.output / descriptor["package"]["metadata_ref"]["href"]
        original_metadata_path.write_bytes(b"x" * descriptor["package"]["metadata_ref"]["bytes"])
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            package.verify_trace(run, descriptor, self.output)

    def test_full_metadata_change_outside_summary_is_detected(self):
        run = self.fixture()
        run["manifest"]["configuration"] = {"frozen_setting": "original"}
        descriptor = package.write_trace(run, self.output, 0)
        changed = copy.deepcopy(run)
        changed["manifest"]["configuration"]["frozen_setting"] = "changed"
        self.assertEqual(package.metadata_summary({key: value for key, value in run.items() if key not in ("events", "motion")}),
                         package.metadata_summary({key: value for key, value in changed.items() if key not in ("events", "motion")}))
        with self.assertRaisesRegex(ValueError, "full trace metadata differs"):
            package.verify_trace(changed, descriptor, self.output)


if __name__ == "__main__":
    unittest.main()
