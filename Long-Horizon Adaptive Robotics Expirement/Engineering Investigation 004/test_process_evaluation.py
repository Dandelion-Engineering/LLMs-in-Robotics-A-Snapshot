"""Bounded synthetic release/control files only; no queue or real evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import process_evaluation as p
from test_continuity import Fixture


class ReleaseFixture:
    def __init__(self, root, count=4):
        self.root = root; self.release = root / "release"; self.release.mkdir()
        self.map = root / "map"; self.map.mkdir(); self.output = root / "derived"
        self.collector = p.collector_module()
        freeze = self.root / "freeze.json"; p.write_once(freeze, {"restart_matching_mode": "exact_configuration"})
        self.plans = [{"run_id": "synthetic-%03d" % index, "architecture": "A1", "condition": "persistent",
            "horizon": 3, "scenario": "restart", "paired_block_id": "block-%03d" % (index // 2),
            "case_id": "case-%03d" % index, "replicate": 1, "stage": "evaluation", "freeze_sha256": p.ref(freeze)["sha256"]} for index in range(count)]
        self.assessments = []; refs = []
        for plan in self.plans:
            file = self.release / (plan["run_id"] + ".json"); p.write_once(file, plan)
            refs.append({"run_id": plan["run_id"], "path": file.name, "sha256": p.ref(file)["sha256"]})
        p.write_once(self.release / "release.json", {"manifest_refs": refs, "freeze_manifest": p.ref(freeze)})
        self.release_hash = p.ref(self.release / "release.json")["sha256"]
        self.authority = SimpleNamespace(queued_job=Mock(return_value={"id": "synthetic-derivation"}))
        self.calls = []
        self.diagnostics = SimpleNamespace(diagnose_directory=Mock(side_effect=self.diagnose),
                                           write_report=lambda report, path: p.write_once(path, report))
        self.continuity = Mock(side_effect=self.extract)

    def add(self, index=0, *, outcome="failure", validity="valid", infra=False, corrected=False, evidence=True):
        plan = self.plans[index]; rid = plan["run_id"]
        attempt = self.release / "attempts" / rid; attempt.mkdir(parents=True)
        manifest_hash = p.ref(self.release / (rid + ".json"))["sha256"]
        job = "job-" + rid; batch = self.release / "batches" / job; batch.mkdir(parents=True)
        raw = {"run_id": rid, "stage": "evaluation", "execution_status": "completed", "outcome": "success" if corrected else outcome,
               "validity": "valid", "wall_duration_s": 12., "ended_at": "synthetic", "termination_reason": "synthetic",
               "independent_outcome": {"success": True if corrected else outcome == "success"}}
        terminal = {"run_id": rid, "queue_job_id": job, "release_sha256": self.release_hash,
                    "manifest_sha256": manifest_hash, "post_run_integrity": {"passed": True},
                    "result": raw, "supervisor_result_ref": None}
        if evidence:
            directory = attempt / "evidence"; directory.mkdir()
            manifest = {**plan, "evaluation_authorization": {k: terminal[k] for k in ("release_sha256", "manifest_sha256", "queue_job_id")}}
            p.write_once(directory / "manifest.json", manifest); p.write_once(directory / "result.json", raw)
            for name in ("events.jsonl", "motion.jsonl"): (directory / name).write_text("", encoding="utf-8")
            terminal["supervisor_result_ref"] = p.ref(directory / "result.json")
        p.write_once(attempt / "terminal.json", terminal)
        p.write_once(batch / "planned.json", {"queue_job_id": job, "release_sha256": self.release_hash, "selected_run_ids": [rid]})
        p.write_once(batch / "finished.json", {"queue_job_id": job, "terminal_run_ids": [rid],
                    "terminal_refs": [{"run_id": rid, **p.ref(attempt / "terminal.json")}]})
        p.write_once(batch / "official-queue-status.json", {"id": job, "state": "succeeded", "exit_status": 0})
        p.write_once(batch / "finalized.json", {"queue_job_id": job, "run_ids": [rid],
                     "official_queue_receipt_sha256": p.ref(batch / "official-queue-status.json")["sha256"]})
        row = {"id": rid + "-original", "run_id": rid, "supersedes_result_id": None, "execution_status": "completed",
               "outcome": raw["outcome"], "validity": validity, "metrics": [],
               "details": {"terminal_sha256": p.ref(attempt / "terminal.json")["sha256"], "infrastructure_invalid": infra}}
        self.assessments.append(row)
        if corrected:
            row = copy.deepcopy(row); row.update(id=rid + "-correction", supersedes_result_id=row["id"], outcome=outcome)
            self.assessments.append(row)
        return attempt / "evidence"

    def diagnose(self, directory):
        self.calls.append((directory.parent.name, "diagnostics"))
        return {"run_id": directory.parent.name, "integrity_findings": [],
                "motion": {"tcp_path_m": {"value": 2.}}, "models": {"total_tokens": {"value": None}},
                "events": [{"huge_trace_not_for_index": True}]}

    def extract(self, directory, **_kwargs):
        self.calls.append((directory.parent.name, "continuity"))
        return {"run_id": directory.parent.name, "integrity_findings": [], "rows": [{"huge_trace_not_for_index": True}],
                "coverage": dict(zip(p.COVERAGE, (3, 1, 2, 1, 0, 1, 0, 1)))}

    def process(self, output=None):
        map_file = self.map / "results.jsonl"
        map_file.write_text("".join(json.dumps(row) + "\n" for row in self.assessments), encoding="utf-8")
        snapshot = {"root": str(self.map), "files": {map_file.name: p.ref(map_file)["sha256"]}}
        with patch.object(p, "runtime_module", side_effect=lambda name: {"release_runner": self.authority, "diagnostics": self.diagnostics}[name]), \
             patch.object(p, "collector_module", return_value=self.collector), \
             patch.object(self.collector.protocol, "load_release", return_value=self.plans), \
             patch.object(p, "read_map", return_value=({"result": self.assessments}, snapshot)), \
             patch.object(p.continuity, "extract_directory", self.continuity), \
             patch.object(p.continuity, "write_report", side_effect=lambda report, path, _root: p.write_once(path, report)):
            return p.process(self.release, output or self.output, map_root=self.map)


class EvaluationProcessorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def fixture(self, count=4): return ReleaseFixture(self.root, count)

    def test_ownership_precedes_any_selection_or_writing(self):
        authority = SimpleNamespace(queued_job=Mock(side_effect=ValueError("not queue owner")))
        with patch.object(p, "runtime_module", return_value=authority), patch.object(p, "collector_module") as collect:
            with self.assertRaisesRegex(ValueError, "not queue owner"): p.process(self.root, self.root / "out")
            collect.assert_not_called()
        authority.queued_job.assert_called_once_with(expected_script=p.__file__)
        self.assertFalse((self.root / "out").exists())

    def test_full_264_denominator_with_one_failed_selected_run_and_no_replacement(self):
        f = self.fixture(264); episode = f.add(corrected=True, outcome="partial", validity="invalid")
        before = {name: p.ref(episode / name) for name in p.CORE}
        index = f.process()
        self.assertEqual(index["counts"]["planned"], 264)
        self.assertEqual(index["counts"]["missing_terminal"], 263)
        self.assertEqual(len(index["runs"]), 264)
        self.assertFalse(index["complete_terminal_accounting"])
        self.assertEqual(index["status"], "partial_failure")
        selected = index["runs"][0]
        self.assertEqual(selected["selected_result"]["outcome"], "partial")
        self.assertEqual(selected["selected_result"]["validity"], "invalid")
        self.assertNotIn("independent_outcome", selected["selected_result"])
        self.assertFalse(selected["primary_derivative_eligible"]["diagnostics"])
        self.assertEqual(f.calls, [("synthetic-000", "diagnostics"), ("synthetic-000", "continuity")])
        self.assertEqual(before, {name: p.ref(episode / name) for name in p.CORE})
        self.assertNotIn("huge_trace_not_for_index", json.dumps(index))
        self.assertEqual(len((f.output / "progress.jsonl").read_text().splitlines()), 264)
        group = index["descriptive_groups"][0]["subsets"]["all_planned_descriptive"]
        self.assertEqual(group["denominator_runs"], 264)
        self.assertEqual(group["continuity"]["coverage"]["unknown_admissibility"]["observed_total"], 1)
        self.assertEqual(group["continuity"]["recovery"]["known_admissible_exercised_opportunities"], 1)
        self.assertEqual(group["continuity"]["recovery"]["missing_report_count"], 263)
        self.assertIsNone(group["diagnostics"]["measurements"]["model_tokens"]["mean"])

    def test_whole_paired_block_exclusion_includes_valid_counterpart_and_missing(self):
        f = self.fixture(); f.add(0, infra=True); f.add(1); f.add(2, outcome="failure")
        index = f.process(); rows = index["runs"]
        self.assertEqual([r["primary_disposition"] for r in rows],
                         ["paired_block_infrastructure_invalid", "paired_block_infrastructure_invalid", "eligible", "unrun"])
        self.assertEqual(rows[1]["selected_result"]["validity"], "valid")
        self.assertFalse(rows[1]["primary_derivative_eligible"]["diagnostics"])
        self.assertTrue(rows[2]["primary_derivative_eligible"]["diagnostics"])  # valid failure is retained
        primary = index["descriptive_groups"][0]["subsets"]["primary_eligible"]
        self.assertEqual(primary["denominator_runs"], 1)
        self.assertEqual(primary["diagnostics"]["measurements"]["tcp_path_m"]["observed_runs"], 1)

    def test_empty_and_carry_counters_remain_distinct_with_legacy_missingness(self):
        f = self.fixture(4)
        for index in range(3): f.add(index)
        def extract(directory, **_kwargs):
            run_id = directory.parent.name
            coverage = {"known_admissible": 1, "established_recoveries": 0}
            if run_id != "synthetic-002":
                empty = run_id == "synthetic-000"
                coverage.update(known_admissible_qualified_context=1,
                    independently_verified_restart_exposures=1, qualified_restart_exposures=1,
                    known_admissible_empty_instantaneous=int(empty), known_admissible_carry_qualified=int(not empty),
                    qualified_carry_exposures=int(not empty), qualified_absence_coverage_pass=int(not empty),
                    qualified_absence_coverage_unknown=0, qualified_absence_coverage_not_applicable=int(empty),
                    qualification_scope_unknown=0)
            return {"run_id": run_id, "integrity_findings": [], "coverage": coverage, "rows": []}
        f.continuity.side_effect = extract
        report = f.process(); runs = report["runs"]
        empty, carry, legacy = [row["derived"]["continuity"]["compact"] for row in runs[:3]]
        self.assertEqual(empty["known_admissible_empty_instantaneous"], 1)
        self.assertEqual(empty["qualified_absence_coverage_pass"], 0)
        self.assertEqual(carry["known_admissible_carry_qualified"], 1)
        self.assertEqual(carry["qualified_absence_coverage_not_applicable"], 0)
        self.assertIsNone(legacy["known_admissible_empty_instantaneous"])
        self.assertIsNone(legacy["qualified_absence_coverage_pass"])
        group = report["descriptive_groups"][0]["subsets"]["all_planned_descriptive"]["continuity"]
        self.assertEqual(group["recovery"]["known_admissible_exercised_opportunities"], 3)
        self.assertEqual(group["recovery"]["established_recoveries"], 0)
        for name in ("known_admissible_empty_instantaneous", "known_admissible_carry_qualified", "qualified_absence_coverage_pass"):
            self.assertEqual(group["coverage"][name], {"observed_total": 1, "report_denominator": 2, "missing_report_count": 2})

    def test_missing_evidence_and_independent_derivation_failure_retained(self):
        f = self.fixture(3); f.add(0, evidence=False); f.add(1)
        f.diagnostics.diagnose_directory.side_effect = ValueError("synthetic broken motion")
        index = f.process()
        self.assertEqual([r["status"] for r in index["runs"]], ["missing_evidence", "partial_failure", "missing_terminal"])
        second = index["runs"][1]
        self.assertEqual(second["derived"]["continuity"]["status"], "completed")
        self.assertEqual(second["derived"]["diagnostics"]["status"], "failed")
        self.assertTrue(Path(second["derived"]["diagnostics"]["artifact"]["path"]).exists())
        self.assertTrue(second["primary_derivative_eligible"]["continuity"])
        self.assertEqual(index["runs"][0]["missing_evidence_files"], list(p.CORE))

    def test_derivative_findings_exclude_measurements_without_rewriting_validity(self):
        f = self.fixture(1); f.add()
        f.diagnostics.diagnose_directory.side_effect = lambda root: {**f.diagnose(root), "integrity_findings": ["synthetic mismatch"]}
        index = f.process(); row = index["runs"][0]
        self.assertEqual(index["status"], "completed")
        self.assertEqual(row["selected_result"]["validity"], "valid")
        self.assertFalse(row["primary_derivative_eligible"]["diagnostics"])
        self.assertTrue(row["primary_derivative_eligible"]["continuity"])
        summary = index["descriptive_groups"][0]["subsets"]["primary_eligible"]["diagnostics"]
        self.assertEqual(summary["reports_with_unverified_integrity"], 1)
        self.assertIsNone(summary["measurements"]["tcp_path_m"]["mean"])

    def test_changed_original_invalidates_derivatives_and_blocks_next_reader(self):
        f = self.fixture(1); f.add()
        def mutate(root):
            (root / "motion.jsonl").write_text("changed synthetic source", encoding="utf-8")
            return f.diagnose(root)
        f.diagnostics.diagnose_directory.side_effect = mutate
        index = f.process(); row = index["runs"][0]
        self.assertEqual(row["status"], "integrity_failed")
        f.continuity.assert_not_called()
        self.assertFalse(any(row["primary_derivative_eligible"].values()))
        self.assertEqual(row["selected_result"]["validity"], "valid")

    def test_changed_global_map_invalidates_earlier_rows_in_final_index(self):
        f = self.fixture(2); f.add(0); f.add(1)
        def mutate(root, **_kwargs):
            if root.parent.name == "synthetic-001":
                with (f.map / "results.jsonl").open("a", encoding="utf-8") as stream: stream.write(" ")
            return f.extract(root)
        f.continuity.side_effect = mutate
        index = f.process()
        self.assertEqual(index["status"], "integrity_failed")
        self.assertFalse(any(r["primary_derivative_eligible"]["diagnostics"] for r in index["runs"]))
        self.assertEqual(index["descriptive_groups"][0]["subsets"]["primary_eligible"]["diagnostics"]["accepted_reports"], 0)

    def test_unfinalized_selection_refuses_before_output(self):
        f = self.fixture(1); f.add()
        next((f.release / "batches").glob("*/finalized.json")).unlink()
        with self.assertRaises(ValueError): f.process()
        self.assertFalse(f.output.exists()); f.diagnostics.diagnose_directory.assert_not_called()

    def test_wrong_episode_authorization_never_derived(self):
        f = self.fixture(1); directory = f.add()
        manifest = p.object_file(directory / "manifest.json"); manifest["evaluation_authorization"]["manifest_sha256"] = "wrong"
        (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        index = f.process()
        self.assertEqual(index["runs"][0]["status"], "verification_failed")
        f.diagnostics.diagnose_directory.assert_not_called(); f.continuity.assert_not_called()

    def test_output_is_fresh_and_outside_original_authority(self):
        f = self.fixture(1)
        for output in (f.release / "derived", f.map / "derived", self.root / "candidate_state" / "derived"):
            with self.assertRaisesRegex(ValueError, "outside"): f.process(output)
        f.process()
        with self.assertRaisesRegex(ValueError, "fresh"): f.process()

    def test_actual_derivation_functions_on_tiny_synthetic_episode(self):
        f = self.fixture(1); directory = f.add()
        fixture = Fixture(); fixture.restart(); fixture.step()
        manifest = p.object_file(directory / "manifest.json")
        fixture.manifest.update(manifest); fixture.result = p.object_file(directory / "result.json")
        for event in fixture.events: event["run_id"] = manifest["run_id"]
        (directory / "manifest.json").write_text(json.dumps(fixture.manifest), encoding="utf-8")
        (directory / "events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in fixture.events), encoding="utf-8")
        spec = importlib.util.spec_from_file_location("actual_synthetic_evaluation_diagnostics", p.RUNTIME / "diagnostics.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        f.diagnostics = module
        extract = p.continuity.extract_directory
        f.continuity.side_effect = extract
        index = f.process(); row = index["runs"][0]
        self.assertEqual(row["status"], "completed", row["errors"])
        self.assertEqual(row["derived"]["continuity"]["compact"]["unknown_admissibility"], 1)
        self.assertIsNone(row["derived"]["diagnostics"]["compact"]["tcp_path_m"])


if __name__ == "__main__": unittest.main()
