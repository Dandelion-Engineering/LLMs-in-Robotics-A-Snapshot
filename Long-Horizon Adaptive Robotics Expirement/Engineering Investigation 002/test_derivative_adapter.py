"""Synthetic complete-denominator and source-binding checks; no real run reads."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import analysis_adapter
import analysis_provenance
import build_workspace
import derivative_adapter as adapter
from test_process_evaluation import ReleaseFixture


def write(path, value):
    path.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")


def receipt(path, job, output, script, *, completed):
    write(path, {"id": job, "state": "succeeded" if completed else "failed", "exit_status": 0 if completed else 1,
        "ended_at": "synthetic-completed", "argv": [sys.executable, str(script), "--output-dir", str(output)]})


class DerivativeAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "view.html"

    def fixture(self, *, failing=False):
        f = ReleaseFixture(self.root, 264)
        f.add(0, infra=True, corrected=True, outcome="partial")
        f.add(1)
        f.add(2, outcome="failure")
        if failing: f.diagnostics.diagnose_directory.side_effect = ValueError("synthetic malformed motion")
        self.index = f.process()
        self.path = f.output / "index.json"
        self.receipt = self.root / "receipt.json"
        receipt(self.receipt, "synthetic-derivation", f.output, Path(adapter.__file__).parent / "process_evaluation.py", completed=False)
        return f

    def read(self, **kwargs):
        return adapter.read_derivatives(self.path, self.receipt, self.output, **kwargs)

    def test_all_264_slots_corrections_unknowns_and_whole_block_exclusion(self):
        f = self.fixture()
        result = self.read(canonical_files=self.index["canonical_map"]["files"])
        self.assertEqual(len(result["runs"]), 264)
        self.assertEqual(result["counts"]["missing_terminal"], 261)
        self.assertEqual(result["runs"][0]["selected_result"]["outcome"], "partial")
        self.assertEqual(result["runs"][1]["primary_disposition"], "paired_block_infrastructure_invalid")
        self.assertTrue(result["runs"][2]["primary_derivative_eligible"]["diagnostics"])
        self.assertIsNone(result["runs"][3]["selected_result"])
        self.assertEqual(result["runs"][3]["derived"]["continuity"]["status"], "unavailable")
        group = result["descriptive_groups"][0]["subsets"]["primary_eligible"]
        self.assertEqual(group["continuity"]["coverage"]["unknown_admissibility"]["observed_total"], 1)
        self.assertIsNone(group["diagnostics"]["measurements"]["model_tokens"]["mean"])
        self.assertNotIn("huge_trace_not_for_index", json.dumps(result))
        self.assertIn("href", result["runs"][0]["derived"]["diagnostics"]["artifact"])
        self.assertFalse((f.release / "analysis.json").exists())

    def test_partial_failures_remain_distinct_and_only_reports_are_hashed(self):
        self.fixture(failing=True)
        with patch.object(adapter, "read_object", wraps=adapter.read_object) as reader:
            result = self.read()
        files = {Path(call.args[0]).name for call in reader.call_args_list}
        self.assertNotIn("events.jsonl", files)
        self.assertNotIn("diagnostics-failure.json", files)
        self.assertNotIn("continuity.json", files)
        first = result["runs"][0]["derived"]
        self.assertEqual(first["diagnostics"]["status"], "failed")
        self.assertEqual(first["continuity"]["status"], "completed")
        self.assertIn("synthetic malformed motion", first["diagnostics"]["message"])

    def test_missing_or_altered_report_and_changed_manifest_refuse(self):
        f = self.fixture()
        for file in (f.output / "synthetic-000" / "diagnostics.json", f.release / "synthetic-000.json"):
            original = file.read_bytes()
            for mode in ("missing", "changed"):
                if mode == "missing": file.unlink()
                else: file.write_bytes(original + b" ")
                with self.assertRaisesRegex(ValueError, "Artifact bytes differ"): self.read()
                file.write_bytes(original)

    def test_duplicate_omitted_false_eligibility_summary_and_receipt_rejected(self):
        self.fixture()
        mutations = [lambda x: x["runs"].pop(),
            lambda x: x["runs"].__setitem__(1, copy.deepcopy(x["runs"][0])),
            lambda x: x["runs"][1]["primary_derivative_eligible"].update(diagnostics=True),
            lambda x: x["runs"][0]["selected_result"].update(outcome="success"),
            lambda x: x["descriptive_groups"][0]["subsets"]["primary_eligible"].update(denominator_runs=99),
            lambda x: x["counts"].update(missing_terminal=0)]
        for mutate in mutations:
            invalid = copy.deepcopy(self.index); mutate(invalid); write(self.path, invalid)
            with self.assertRaises(ValueError): self.read()
        write(self.path, self.index)
        with self.assertRaisesRegex(ValueError, "Canonical map changed"): self.read(canonical_files={})
        receipt(self.receipt, "wrong-job", self.path.parent, Path(adapter.__file__).parent / "process_evaluation.py", completed=False)
        with self.assertRaisesRegex(ValueError, "receipt"): self.read()

    def test_global_integrity_failure_cannot_restore_primary_measurements(self):
        self.fixture()
        from process_evaluation import summarize
        self.index.update(status="integrity_failed", global_integrity_errors=[{"message": "synthetic authority changed"}])
        for row in self.index["runs"]:
            row["source_integrity"] = "unverified"
            row["primary_derivative_eligible"] = {"diagnostics": False, "continuity": False}
        self.index["counts"].update(primary_diagnostic_eligible=0, primary_continuity_eligible=0)
        self.index["descriptive_groups"] = summarize(self.index["runs"])
        write(self.path, self.index)
        result = self.read(canonical_files={})
        self.assertEqual(result["status"], "integrity_failed")
        self.assertEqual(result["canonical_snapshot_state"], "changed; historical index only")
        self.assertIsNone(result["descriptive_groups"][0]["subsets"]["primary_eligible"]["diagnostics"]["measurements"]["tcp_path_m"]["mean"])

    def test_absence_is_explicit_and_builder_keeps_twelve_slots(self):
        self.assertEqual(adapter.read_derivatives(None, None, self.output)["state"], "unavailable")
        with self.assertRaises(ValueError): adapter.read_derivatives(None, self.root / "receipt.json", self.output)
        self.fixture()
        selection = self.root / "traces.json"
        slots = [{"run_id": "synthetic-%03d" % i, "path": "never-existed/%d" % i, "reason": "Fixed synthetic declaration"} for i in range(12)]
        write(selection, {"schema_version": "investigation-trace-selection-1.0", "declared_at": "synthetic", "selection_basis": "Synthetic fixed slots", "runs": slots})
        snapshot = {"file_sha256": self.index["canonical_map"]["files"], "store_sha256": "synthetic", "records": {}}
        with patch.object(build_workspace, "load_snapshot", return_value=snapshot), patch.object(build_workspace, "render", return_value="synthetic") as render:
            result = build_workspace.build(self.root, self.output, evaluation_index=self.path,
                evaluation_receipt=self.receipt, trace_selection=selection)
        retained = render.call_args.args[0]
        self.assertEqual(result["evaluation_derivative_runs"], 264)
        self.assertEqual(result["evidence_runs"], [s["run_id"] for s in slots])
        self.assertEqual(result["unavailable_evidence_runs"], result["evidence_runs"])
        self.assertEqual(retained["trace_selection"]["runs"], slots)


class AnalysisBindingTests(unittest.TestCase):
    def test_real_wrapper_output_binds_and_tampering_refuses_with_legacy_preserved(self):
        release_tools = Path(__file__).parent.parent / "Batch 01" / "Release Analysis 002"
        sys.path.insert(0, str(release_tools)); self.addCleanup(lambda: sys.path.remove(str(release_tools)))
        from test_analyze_results import AnalysisLineageTests
        fixture = AnalysisLineageTests("test_exact_protocol_output_and_complete_input_lineage")
        fixture.setUp(); self.addCleanup(fixture.tearDown)
        provenance = fixture.run_wrapper()
        output = fixture.base / "view.html"
        report = analysis_adapter.read_analysis(fixture.output / "analysis.json", output)
        source = fixture.output / "analysis-provenance.json"
        completed = fixture.base / "analysis-receipt.json"
        receipt(completed, "synthetic-analysis-job", fixture.output, release_tools / "analyze_results.py", completed=True)
        verified = analysis_provenance.bind_analysis(report, source, completed, output)
        self.assertEqual(verified["binding"]["state"], "verified")
        self.assertEqual(verified["report"], report["report"])
        self.assertEqual(analysis_provenance.bind_analysis(report, None, None, output), report)
        changes = [lambda p: p.update(status="failed"), lambda p: p.update(inputs_unchanged=False),
                   lambda p: p["inputs_after"].pop("readiness"), lambda p: p["protected_manifest_refs"].pop(),
                   lambda p: p["analysis_settings"].update(analysis_seed=99),
                   lambda p: p["analysis"].update(sha256="0" * 64)]
        for change in changes:
            invalid = copy.deepcopy(provenance); change(invalid); write(source, invalid)
            with self.assertRaises(ValueError): analysis_provenance.bind_analysis(report, source, completed, output)
        write(source, provenance)
        with self.assertRaisesRegex(ValueError, "bind different"):
            analysis_provenance.bind_analysis(report, source, completed, output, derivatives={"state": "available",
                "selected_results_source": {"sha256": "another"}, "release_source": {}})
        fixture.selected.write_text(fixture.selected.read_text(encoding="utf-8") + " ", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Artifact bytes differ"):
            analysis_provenance.bind_analysis(report, source, completed, output)


if __name__ == "__main__": unittest.main()
