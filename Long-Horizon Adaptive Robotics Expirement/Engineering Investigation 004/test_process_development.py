"""Synthetic temporary operator inputs only; no queue, simulator or real traces."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import process_development as p
from test_continuity import Fixture


class BatchFixture:
    def __init__(self, root):
        self.root = root
        self.map = root / "map"; self.map.mkdir()
        self.raw = root / "raw"; self.raw.mkdir()
        self.data = {"run": [], "result": []}
        self.receipts = []
        self.authority = SimpleNamespace(queued_job=Mock(return_value={"id": "synthetic-derivation-job"}),
                                         verify_queue_receipt=Mock(side_effect=lambda _id, path: p.object_file(path)))
        self.diagnostics = SimpleNamespace(
            diagnose_directory=Mock(side_effect=lambda root: {"run_id": root.name, "integrity_findings": []}),
            write_report=Mock(side_effect=lambda report, path: p.write_once(path, report)))

    def add(self, suffix="001", job="synthetic-execution-job", corrected=False):
        run_id = "B01-dev-TEST-" + suffix
        root = self.raw / run_id; root.mkdir()
        for filename, value in (("manifest.json", {"run_id": run_id, "stage": "development", "synthetic_test_only": True}),
                                ("result.json", {"run_id": run_id, "stage": "development", "execution_status": "completed", "outcome": "success", "validity": "unknown"})):
            p.write_once(root / filename, value)
        (root / "events.jsonl").write_text("", encoding="utf-8")
        (root / "motion.jsonl").write_text("", encoding="utf-8")
        self.data["run"].append({"id": run_id, "stage": "development"})
        result = {"id": run_id + "-result", "run_id": run_id, "execution_status": "completed", "outcome": "success", "validity": "unknown",
                  "details": {"queue_job_id": job}, "evidence": [{"state": "available", "uri": os.path.relpath(root / filename, self.map),
                          "sha256": p.digest_file(root / filename)} for filename in ("result.json", "events.jsonl", "motion.jsonl")]}
        self.data["result"].append(result)
        if corrected:
            corrected_result = copy.deepcopy(result)
            corrected_result.update(id=run_id + "-correction", supersedes_result_id=result["id"], outcome="partial", validity="invalid")
            corrected_result["details"]["correction"] = "Synthetic historical claim withdrawn"
            self.data["result"].append(corrected_result)
        path = self.root / (job + ".json")
        if not path.exists():
            p.write_once(path, {"id": job, "state": "succeeded", "exit_status": 0})
            self.receipts.append(path)
        return run_id

    def process(self, ids, output=None, receipts=None, continuity_error=None):
        def module(name):
            return {"release_runner": self.authority, "diagnostics": self.diagnostics}[name]
        def extract(root):
            if continuity_error: raise continuity_error
            return {"run_id": root.name, "integrity_findings": []}
        with patch.object(p, "runtime_module", side_effect=module), patch.object(p, "read_map", return_value=(self.data, {"store_sha256": "synthetic-only"})), \
             patch.object(p.continuity, "extract_directory", side_effect=extract), \
             patch.object(p.continuity, "write_report", side_effect=lambda report, path, _root: p.write_once(path, report)):
            return p.process(ids, self.receipts if receipts is None else receipts, output or self.root / "derived",
                             map_root=self.map, evidence_root=self.raw)


class DevelopmentProcessorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.f = BatchFixture(Path(self.temporary.name))

    def test_queue_ownership_is_required_before_reads_or_output(self):
        self.f.authority.queued_job.side_effect = ValueError("not queue owner")
        with patch.object(p, "runtime_module", return_value=self.f.authority), patch.object(p, "read_map") as read:
            with self.assertRaisesRegex(ValueError, "not queue owner"):
                p.process(["B01-dev-TEST-001"], [], self.f.root / "out")
            read.assert_not_called()
        self.assertFalse((self.f.root / "out").exists())
        self.f.authority.queued_job.assert_called_once_with(expected_script=p.__file__)

    def test_explicit_current_correction_survives_raw_success(self):
        run_id = self.f.add(corrected=True)
        before = {path: p.digest_file(path) for path in (self.f.raw / run_id).iterdir()}
        index = self.f.process([run_id]); row = index["runs"][0]
        self.assertEqual(index["status"], "completed")
        self.assertEqual(row["canonical_outcome"], "partial")
        self.assertEqual(row["canonical_validity"], "invalid")
        self.assertEqual(row["immutable_raw_outcome"], "success")
        self.assertTrue(row["canonical_result_id"].endswith("-correction"))
        self.assertEqual(set(row["derived"]), {"diagnostics", "continuity"})
        for artifact in row["derived"].values():
            self.assertEqual(p.digest_file(Path(artifact["artifact"]["path"])), artifact["artifact"]["sha256"])
        self.assertEqual(before, {path: p.digest_file(path) for path in before})
        self.assertEqual(p.object_file(self.f.root / "derived" / "index.json"), index)
        with self.assertRaisesRegex(ValueError, "fresh"):
            self.f.process([run_id])

    def test_distinct_older_execution_jobs_require_their_own_explicit_receipts(self):
        first = self.f.add("001", "job-old"); second = self.f.add("002", "job-new")
        index = self.f.process([first, second])
        self.assertEqual(index["counts"]["completed"], 2)
        self.assertEqual([r["execution_queue_job_id"] for r in index["runs"]], ["job-old", "job-new"])
        self.assertEqual(self.f.authority.verify_queue_receipt.call_count, 2)

    def test_unmatched_receipt_prevents_that_run_derivation_and_retains_other_run(self):
        first = self.f.add("001", "job-old"); second = self.f.add("002", "job-new")
        index = self.f.process([first, second], receipts=[self.f.receipts[0]])
        self.assertEqual([r["status"] for r in index["runs"]], ["completed", "verification_failed"])
        self.assertEqual(self.f.diagnostics.diagnose_directory.call_count, 1)
        self.assertEqual(index["runs"][1]["derived"], {})
        self.assertEqual(len((self.f.root / "derived" / "progress.jsonl").read_text().splitlines()), 2)

    def test_failed_diagnostics_preserves_independent_continuity_and_failure_hash(self):
        run_id = self.f.add()
        self.f.diagnostics.diagnose_directory.side_effect = ValueError("synthetic missing support")
        index = self.f.process([run_id]); row = index["runs"][0]
        self.assertEqual(index["status"], "partial_failure")
        self.assertEqual(row["derived"]["continuity"]["status"], "completed")
        failure = row["derived"]["diagnostics"]
        self.assertEqual(failure["status"], "failed")
        self.assertEqual(p.digest_file(Path(failure["artifact"]["path"])), failure["artifact"]["sha256"])
        self.assertIn("synthetic missing support", p.object_file(failure["artifact"]["path"])["traceback"])

    def test_integrity_findings_do_not_become_a_clean_scientific_assessment(self):
        run_id = self.f.add()
        self.f.diagnostics.diagnose_directory.side_effect = lambda root: {"run_id": root.name, "integrity_findings": ["synthetic conflict"]}
        index = self.f.process([run_id])
        self.assertEqual(index["status"], "completed")  # The derivation finished.
        self.assertTrue(index["runs"][0]["requires_operator_review"])
        self.assertEqual(index["counts"]["with_integrity_findings"], 1)

    def test_changed_original_during_processing_fails_integrity_and_blocks_next_derivation(self):
        run_id = self.f.add()
        def mutate(root):
            (root / "events.jsonl").write_text("synthetic change", encoding="utf-8")
            return {"run_id": run_id, "integrity_findings": []}
        self.f.diagnostics.diagnose_directory.side_effect = mutate
        index = self.f.process([run_id]); row = index["runs"][0]
        self.assertEqual(row["status"], "integrity_failed")
        self.assertEqual(row["derived"]["continuity"]["status"], "failed")
        self.assertIn("Original source changed", row["errors"][-1]["message"])

    def test_invalid_or_unverified_official_receipt_is_refused(self):
        path = self.f.root / "bad.json"
        for fields in ({"state": "running", "exit_status": 0}, {"state": "succeeded", "exit_status": 1},
                       {"state": "succeeded", "exit_status": False}, {"state": "succeeded"}):
            path.write_text(json.dumps({"id": "job", **fields}), encoding="utf-8")
            with self.assertRaises(ValueError):p.receipt_files([path], self.f.authority)
        path.write_text(json.dumps({"id": "job", "state": "succeeded", "exit_status": 0}), encoding="utf-8")
        self.f.authority.verify_queue_receipt.side_effect = ValueError("installed state differs")
        with self.assertRaisesRegex(ValueError, "installed state differs"):p.receipt_files([path], self.f.authority)

    def test_duplicate_receipt_and_changed_verified_object_are_refused(self):
        self.f.add(); path = self.f.receipts[0]
        with self.assertRaisesRegex(ValueError, "Duplicate"):p.receipt_files([path, path], self.f.authority)
        self.f.authority.verify_queue_receipt.side_effect = lambda _id, _path: {"id": "other"}
        with self.assertRaisesRegex(ValueError, "differ"):p.receipt_files([path], self.f.authority)

    def test_scored_ids_duplicates_empty_and_original_output_are_refused(self):
        run_id = self.f.add()
        for ids in ([], [run_id, run_id], ["B01-eval-001"], [[run_id]]):
            with self.assertRaises(ValueError):self.f.process(ids)
        for output in (self.f.raw / "new", self.f.map / "new", self.f.root / "candidate_state" / "new"):
            with self.assertRaises(ValueError):self.f.process([run_id], output=output)

    def test_canonical_result_and_exact_hash_binding_are_mandatory(self):
        run_id = self.f.add()
        receipts = p.receipt_files(self.f.receipts, self.f.authority)
        variants = []
        data = copy.deepcopy(self.f.data);data["result"] = [];variants.append(data)
        data = copy.deepcopy(self.f.data);data["run"][0]["stage"] = "evaluation";variants.append(data)
        data = copy.deepcopy(self.f.data);data["result"][0]["execution_status"] = "running";variants.append(data)
        data = copy.deepcopy(self.f.data);data["result"][0]["evidence"][0]["sha256"] = "0" * 64;variants.append(data)
        data = copy.deepcopy(self.f.data);other = copy.deepcopy(data["result"][0]);other["id"] += "-competing";data["result"].append(other);variants.append(data)
        for data in variants:
            with self.assertRaises(ValueError):p.verify_run(run_id, data, self.f.map, self.f.raw, receipts)

    def test_tiny_immutable_fixture_integrates_both_actual_derivation_apis(self):
        run_id = self.f.add(); root = self.f.raw / run_id
        episode = Fixture(); episode.restart(); episode.step()
        episode.manifest["run_id"] = episode.result["run_id"] = run_id
        episode.result["stage"] = "development"
        for event in episode.events: event["run_id"] = run_id
        (root / "manifest.json").write_text(json.dumps(episode.manifest), encoding="utf-8")
        (root / "result.json").write_text(json.dumps(episode.result), encoding="utf-8")
        (root / "events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in episode.events), encoding="utf-8")
        for evidence in self.f.data["result"][0]["evidence"]:
            evidence["sha256"] = p.digest_file((self.f.map / evidence["uri"]).resolve())
        spec = importlib.util.spec_from_file_location("synthetic_actual_diagnostics_api", p.RUNTIME / "diagnostics.py")
        diagnostics = importlib.util.module_from_spec(spec); spec.loader.exec_module(diagnostics)
        with patch.object(p, "runtime_module", side_effect=lambda name: {"release_runner": self.f.authority, "diagnostics": diagnostics}[name]), \
             patch.object(p, "read_map", return_value=(self.f.data, {"store_sha256": "synthetic-only"})):
            index = p.process([run_id], self.f.receipts, self.f.root / "derived", map_root=self.f.map, evidence_root=self.f.raw)
        self.assertEqual(index["status"], "completed", index["runs"][0]["errors"])
        row = index["runs"][0]
        continuity = p.object_file(row["derived"]["continuity"]["artifact"]["path"])
        self.assertEqual(continuity["rows"][0]["admissibility"]["state"], "unknown")
        diagnostic = p.object_file(row["derived"]["diagnostics"]["artifact"]["path"])
        self.assertIsNone(diagnostic["pauses"]["observed_low_motion_time_s"])


if __name__ == "__main__":
    unittest.main()
