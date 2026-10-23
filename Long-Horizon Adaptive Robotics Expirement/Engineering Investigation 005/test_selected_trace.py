"""Declared missing/failed inspection slots: synthetic temporary files only."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import analysis_adapter
import build_workspace as builder
import selected_trace
from test_evidence_adapter import event
from test_workspace import ScriptCollector, unpack_snapshot


class SelectedTraceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="synthetic-selected-traces-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.raw = self.root / "raw"
        self.raw.mkdir()
        self.map = self.root / "map"
        self.map.mkdir()
        for name in builder.load_map_module().KINDS.values():
            (self.map / name).write_bytes(b"")
        self.output = self.root / "view.html"
        self.selection = self.root / "selection.json"

    def declare(self, ids):
        value = {"schema_version": "investigation-trace-selection-1.0",
                 "declared_at": "2026-01-01T00:00:00Z",
                 "selection_basis": "Synthetic fixed slots; outcomes do not select replacements.",
                 "runs": [{"run_id": identity, "path": "raw/" + identity + "/evidence",
                           "reason": "Predeclared synthetic slot " + str(i)} for i, identity in enumerate(ids)]}
        self.selection.write_text(json.dumps(value), encoding="utf-8")
        return value

    def bundle(self, identity, *, outcome="failure", events=True):
        directory = self.raw / identity / "evidence"
        directory.mkdir(parents=True)
        (directory / "manifest.json").write_text(json.dumps({"run_id": identity,
            "architecture": "A1", "stage": "evaluation"}), encoding="utf-8")
        result = {"run_id": identity, "execution_status": "failed", "outcome": outcome,
                  "validity": "invalid", "completion_time_s": None, "wall_duration_s": 1.}
        (directory / "result.json").write_text(json.dumps(result), encoding="utf-8")
        (directory.parent / "terminal.json").write_text(json.dumps({"run_id":identity,"result":result,
            "supervisor_result_ref":{"path":str((directory / "result.json").resolve()),
                                     "sha256":hashlib.sha256((directory / "result.json").read_bytes()).hexdigest()}}),encoding="utf-8")
        if events:
            record = event(1, "final_world", 1., {"objects": {}})
            record["run_id"] = identity
            (directory / "events.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
        return directory

    def build(self):
        result = builder.build(self.map, self.output, metadata_root=self.raw, trace_selection=self.selection)
        parsed = ScriptCollector()
        parsed.feed(self.output.read_text(encoding="utf-8"))
        return result, unpack_snapshot(parsed.data)

    def test_all_twelve_slots_and_all_metadata_survive_missing_failed_traces_without_replacement(self):
        ids = [f"synthetic-selected-{i}" for i in range(12)]
        declared = self.declare(ids)
        before = self.selection.read_bytes()
        for i, identity in enumerate(ids[1:], 1):
            self.bundle(identity, events=i == 1)
        for i in range(3):
            self.bundle(f"synthetic-unselected-success-{i}", outcome="success")
        result, snapshot = self.build()
        self.assertEqual(snapshot["trace_selection"]["runs"], declared["runs"])
        self.assertEqual(self.selection.read_bytes(), before)
        self.assertEqual([r["run_id"] for r in snapshot["evidence_runs"]], ids)
        self.assertEqual(result["evidence_runs"], ids)
        self.assertEqual(len(result["unavailable_evidence_runs"]), 11)
        self.assertEqual(len(snapshot["run_metadata"]["runs"]), 14)
        self.assertFalse(snapshot["trace_selection"]["selection_is_statistical_denominator"])
        missing, failed, no_events = snapshot["evidence_runs"][:3]
        self.assertIsNone(missing["manifest"])
        self.assertIsNone(missing["result"])
        self.assertIsNone(missing["sampling"])
        self.assertEqual(missing["trace_availability"]["missing_required_files"], ["manifest.json", "events.jsonl", "result.json"])
        self.assertEqual(failed["trace_availability"]["state"], "available")
        self.assertEqual(failed["result"]["outcome"], "failure")
        self.assertEqual(failed["result"]["validity"], "invalid")
        self.assertEqual(len(failed["events"]), 1)
        self.assertEqual(no_events["trace_availability"]["state"], "unavailable")
        self.assertEqual(no_events["result"]["outcome"], "failure")
        self.assertEqual({r["name"] for r in no_events["source_files"]}, {"manifest.json", "result.json"})

    def test_protected_terminal_identity_and_result_hash_cannot_be_substituted(self):
        self.declare(["synthetic-protected"])
        root = self.bundle("synthetic-protected")
        path = root.parent / "terminal.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        changes = [lambda x: x.update(run_id="other"),
                   lambda x: x["result"].update(outcome="success"),
                   lambda x: x["supervisor_result_ref"].update(sha256="0" * 64)]
        for change in changes:
            changed = json.loads(json.dumps(original)); change(changed)
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "protected terminal/result binding"):
                self.build()

    def test_truncated_stream_retains_original_hash_but_no_partial_playback(self):
        self.declare(["synthetic-truncated"])
        directory = self.bundle("synthetic-truncated")
        stream = directory / "events.jsonl"
        with stream.open("ab") as handle:
            handle.write(b'{"event_id":2')
        original = stream.read_bytes()
        _, snapshot = self.build()
        run = snapshot["evidence_runs"][0]
        self.assertEqual(run["trace_availability"]["reason_code"], "incomplete_stream")
        self.assertEqual(run["events"], [])
        self.assertEqual(run["motion"], [])
        self.assertIsNone(run["sampling"])
        ref = next(r for r in run["source_files"] if r["name"] == "events.jsonl")
        self.assertEqual(ref["sha256"], hashlib.sha256(original).hexdigest())
        self.assertEqual(stream.read_bytes(), original)

    def test_empty_event_stream_is_unavailable_not_a_zero_event_performance_claim(self):
        self.declare(["synthetic-empty"])
        directory = self.bundle("synthetic-empty")
        (directory / "events.jsonl").write_bytes(b"")
        _, snapshot = self.build()
        run = snapshot["evidence_runs"][0]
        self.assertEqual(run["trace_availability"]["reason_code"], "empty_event_stream")
        self.assertIsNone(run["sampling"])
        self.assertEqual(run["result"]["outcome"], "failure")

    def test_identity_corruption_with_missing_events_refuses_build_and_preserves_old_page(self):
        self.declare(["synthetic-wrong"])
        directory = self.bundle("synthetic-wrong", events=False)
        self.output.write_text("previous verified page", encoding="utf-8")
        for name in ("manifest.json", "result.json"):
            original = (directory / name).read_bytes()
            record = json.loads(original)
            record["run_id"] = "another-run"
            (directory / name).write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "identity differs"):
                self.build()
            self.assertEqual(self.output.read_text(encoding="utf-8"), "previous verified page")
            (directory / name).write_bytes(original)

    def test_corrupt_hash_before_truncated_tail_still_refuses_instead_of_unavailable(self):
        self.declare(["synthetic-corrupt"])
        directory = self.bundle("synthetic-corrupt")
        stream = directory / "events.jsonl"
        record = json.loads(stream.read_text(encoding="utf-8"))
        record["payload_sha256"] = "0" * 64
        stream.write_text(json.dumps(record) + '\n{"unfinished":', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "payload hash mismatch"):
            self.build()

    def test_changed_sources_cannot_be_published_as_available_or_unavailable(self):
        declared = self.declare(["synthetic-changing"])
        directory = self.bundle("synthetic-changing")
        original = selected_trace.read_run

        def changing(*args):
            run = original(*args)
            (directory / "events.jsonl").write_bytes(b"")
            return run

        with patch.object(selected_trace, "read_run", side_effect=changing):
            with self.assertRaisesRegex(ValueError, "changed during"):
                selected_trace.read_selected_trace(declared["runs"][0], directory, self.output)

    def test_unidentified_legacy_path_stays_strict_and_duplicate_declared_ids_refuse(self):
        with self.assertRaises(FileNotFoundError):
            builder.build(self.map, self.output, [self.raw / "missing"])
        declared = self.declare(["synthetic-duplicate", "synthetic-other"])
        declared["runs"][1]["run_id"] = declared["runs"][0]["run_id"]
        self.selection.write_text(json.dumps(declared), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate selected trace run identity"):
            analysis_adapter.select_traces(self.selection)


if __name__ == "__main__":
    unittest.main()
