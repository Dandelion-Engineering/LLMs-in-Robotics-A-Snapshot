"""Prepared synthetic counterexamples; no source/evidence mutation outside temp dirs.

Collector authority is tested by Release Analysis 005. Processor tests here mock
only its already-verified return to test unavailable-report handling separately.
"""
import copy
import json
import importlib.util
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import administrative_projection as a
import derivative_adapter as d
import process_evaluation as p
import selected_trace
import analysis_adapter
import analysis_provenance
from test_derivative_adapter import receipt, write
from test_process_evaluation import ReleaseFixture
from test_evidence_adapter import event


def fixture_projection(root, rid="synthetic-admin"):
    note = {"id": rid + "-decision", "target_ids": [rid], "claim_type": "decision",
            "supersedes_note_id": None, "recorded_at": "2026-09-24T00:00:00+00:00",
            "details": {"provenance_kind": a.ADMINISTRATIVE}}
    result = {"run_id": rid, "stage": "evaluation", "execution_status": "aborted",
              "validity": "invalid", "invalidity_class": "infrastructure", "infrastructure_invalid": True,
              "outcome": "unknown", "ended_at": None, "physical_ended_at": None,
              "provenance_kind": a.ADMINISTRATIVE, "selected_canonical_note_id": note["id"],
              "administratively_recorded_at": "2026-09-24T00:00:00+00:00",
              "post_run_integrity": {"state": "missing"}, "official_queue_state": "interrupted",
              "official_queue_exit_status": None, **{key: None for key in a.NULL_MEASUREMENTS}}
    refs = {}
    for name in ("administrative_disposition", "recovery_annex_ref", "official_queue_receipt", "source_index"):
        file = root / (rid + "-" + name + ".json")
        p.write_once(file, {"scope": "SYNTHETIC TEST ONLY", "name": name})
        refs[name] = p.ref(file)
    provenance = {"run_id": rid, "provenance_kind": a.ADMINISTRATIVE, "selected_note": note,
                  "supervisor_terminal": None, "original_post_run_integrity": {"state": "missing"},
                  **{key: refs[key] for key in ("administrative_disposition", "recovery_annex_ref", "official_queue_receipt")}}
    return result, provenance, refs


def selection(result, provenance, refs):
    return {"schema_version": a.SCHEMA, "results": [result], "provenance": [provenance], "missing": [],
            "counts": {"planned": 1, "original_finalized": 0, "annex_finalized": 0,
                       "administrative_interruption": 1, "selected_for_analysis": 1, "missing_disposition": 0},
            "complete_disposition_accounting": True, "control_sources": list(refs.values()),
            "recovery_annex_ref": refs["recovery_annex_ref"], "recovery_source_index_ref": refs["source_index"]}


class AdministrativeProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-administrative-view-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.result, self.provenance, self.refs = fixture_projection(self.root)

    def test_administrative_disposition_is_not_a_terminal_or_measurement(self):
        selected = selection(self.result, self.provenance, self.refs)
        before = copy.deepcopy(selected)
        counts = a.selection_accounting(selected)
        self.assertEqual(counts["selected_for_analysis"], 1)
        self.assertEqual(counts["original_finalized"] + counts["annex_finalized"], 0)
        self.assertEqual(selected, before)
        for key in a.NULL_MEASUREMENTS:
            self.assertIsNone(self.result[key])

    def test_fabricated_end_integrity_outcome_or_counter_is_rejected(self):
        for key, value in (("ended_at", "2026-09-24T00:00:00Z"), ("physical_ended_at", "invented"),
                           ("post_run_integrity", {"passed": True}), ("outcome", "success"),
                           ("completion_time_s", 0), ("wall_duration_s", 5), ("model_calls", 0),
                           ("total_tokens", 0), ("official_queue_exit_status", 0)):
            with self.subTest(key=key):
                result = {**self.result, key: value}
                with self.assertRaises(ValueError): a.validate_administrative(result, self.provenance)

    def test_fake_terminal_or_note_substitution_is_rejected(self):
        for change in ({"supervisor_terminal": {}}, {"terminal": self.refs["administrative_disposition"]},
                       {"original_post_run_integrity": {"passed": True}}, {"selected_note": {"id": "other"}}):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    a.validate_administrative(self.result, {**self.provenance, **change})

    def test_binary_accounting_cannot_label_administrative_as_completed(self):
        selected = selection(self.result, self.provenance, self.refs)
        for change in (lambda s: s["counts"].update(original_finalized=1, administrative_interruption=0),
                       lambda s: s.update(complete_terminal_accounting=True),
                       lambda s: s.update(complete_disposition_accounting=False)):
            invalid = copy.deepcopy(selected); change(invalid)
            with self.assertRaises(ValueError): a.selection_accounting(invalid)

    def test_partial_but_parseable_stream_does_not_become_administrative_playback(self):
        root = self.root / "attempt" / "evidence"; root.mkdir(parents=True)
        p.write_once(root / "manifest.json", {"run_id": self.result["run_id"], "stage": "evaluation"})
        item = event(1, "world_snapshot", 1, {"objects": {}}); item["run_id"] = self.result["run_id"]
        (root / "events.jsonl").write_text(json.dumps(item) + "\n", encoding="utf-8")
        with patch.object(selected_trace, "read_run", side_effect=AssertionError("Must not parse administrative raw streams")):
            run = selected_trace.read_selected_trace({"run_id": self.result["run_id"]}, root, self.root / "view.html",
                selected_result=self.result, selection_provenance=self.provenance)
        self.assertEqual(run["trace_availability"]["reason_code"], a.ADMINISTRATIVE)
        self.assertEqual(run["events"], []); self.assertEqual(run["motion"], [])
        self.assertIsNone(run["sampling"]); self.assertIsNone(run["result"])
        self.assertEqual(run["administrative_projection"], self.result)

    def test_ordinary_evaluation_raw_result_still_needs_its_protected_terminal(self):
        root = self.root / "partial" / "evidence"; root.mkdir(parents=True)
        p.write_once(root / "manifest.json", {"run_id": "ordinary", "stage": "evaluation"})
        p.write_once(root / "result.json", {"run_id": "ordinary", "execution_status": "failed"})
        (root / "events.jsonl").write_text('{}\n', encoding="utf-8")
        with patch.object(selected_trace, "read_run", side_effect=AssertionError("No protected terminal")):
            run = selected_trace.read_selected_trace({"run_id": "ordinary"}, root, self.root / "view.html")
        self.assertEqual(run["trace_availability"]["reason_code"], "missing_protected_terminal")
        self.assertEqual(run["events"], [])

    def test_processor_does_not_dispatch_admin_reports_and_preserves_normal_result(self):
        fixture = ReleaseFixture(self.root, count=2)
        fixture.add(0, outcome="failure")
        rid = fixture.plans[1]["run_id"]
        result, provenance, refs = fixture_projection(self.root, rid)
        fixture.notes.append(provenance["selected_note"])
        original_collect = fixture.collector.collect
        original_selected = []
        def collected(*args, **kwargs):
            report = original_collect(*args, **{**kwargs, "notes": []})
            original_selected.extend(copy.deepcopy(report["results"]))
            report["results"].append(result); report["provenance"].append(provenance)
            report["missing"] = []
            report["counts"].update(administrative_interruption=1, selected_for_analysis=2, missing_disposition=0)
            report["complete_disposition_accounting"] = True
            report["control_sources"].extend(refs.values())
            report["recovery_annex_ref"] = refs["recovery_annex_ref"]
            report["recovery_source_index_ref"] = refs["source_index"]
            return report
        with patch.object(fixture.collector, "collect", side_effect=collected):
            index = fixture.process()
        self.assertEqual(index["runs"][0]["selected_result"], original_selected[0])
        self.assertEqual(index["status"], "completed")  # Processing/accounting, not task success.
        self.assertTrue(index["complete_disposition_accounting"])
        self.assertNotIn("complete_terminal_accounting", index)
        self.assertEqual(index["counts"]["selected_terminal"], 1)
        self.assertEqual(index["counts"]["administrative_interruption"], 1)
        admin = index["runs"][1]
        self.assertEqual(admin["source_integrity"], "not_processed")
        self.assertEqual(admin["errors"], [])
        for kind, keys in (("diagnostics", p.METRICS), ("continuity", p.COVERAGE)):
            self.assertEqual(admin["derived"][kind]["status"], "unavailable")
            self.assertEqual(admin["derived"][kind]["compact"], dict.fromkeys(keys))
            self.assertFalse(admin["primary_derivative_eligible"][kind])
        self.assertEqual(fixture.calls, [(fixture.plans[0]["run_id"], "diagnostics"),
                                         (fixture.plans[0]["run_id"], "continuity")])
        selected = json.loads((fixture.output / "selected-results.json").read_text(encoding="utf-8"))
        for key in ("canonical_results_source", "canonical_notes_source", "legacy_implementation"):
            self.assertTrue(selected[key]["sha256"])


    def test_reader_keeps_admin_nulls_exact_links_and_all_264_slots(self):
        fixture = ReleaseFixture(self.root, count=264)
        fixture.add(0, outcome="failure")
        rid = fixture.plans[1]["run_id"]
        result, provenance, refs = fixture_projection(self.root, rid)
        original_collect = fixture.collector.collect
        def collected(*args, **kwargs):
            report = original_collect(*args, **kwargs)
            report["results"].append(result); report["provenance"].append(provenance)
            report["missing"] = [row for row in report["missing"] if row["run_id"] != rid]
            report["counts"].update(administrative_interruption=1, selected_for_analysis=2, missing_disposition=262)
            report["control_sources"].extend(refs.values())
            report["recovery_annex_ref"] = refs["recovery_annex_ref"]
            report["recovery_source_index_ref"] = refs["source_index"]
            return report
        with patch.object(fixture.collector, "collect", side_effect=collected):
            index = fixture.process()
        path = fixture.output / "index.json"; receipt_path = self.root / "receipt.json"
        receipt(receipt_path, "synthetic-derivation", fixture.output, Path(p.__file__), completed=False)
        read = lambda: d.read_derivatives(path, receipt_path, self.root / "view.html")
        view = read()
        self.assertEqual(len(view["runs"]), 264)
        self.assertEqual(view["counts"]["selected_terminal"], 1)
        self.assertEqual(view["counts"]["administrative_interruption"], 1)
        self.assertEqual(view["counts"]["missing_disposition"], 262)
        self.assertEqual(view["counts"]["missing_terminal"], 263)
        self.assertFalse(view["complete_disposition_accounting"])
        self.assertEqual(view["runs"][0]["primary_disposition"], "paired_block_infrastructure_invalid")
        admin = view["runs"][1]
        self.assertEqual(admin["status"], a.ADMINISTRATIVE)
        self.assertEqual(admin["selection_provenance"], provenance)
        self.assertEqual(len(admin["selection_sources"]), 3)
        self.assertTrue(all(item["source"]["href"] for item in admin["selection_sources"]))
        self.assertEqual(len(view["supplemental_sources"]), 2)
        for kind in ("diagnostics", "continuity"):
            self.assertTrue(all(value is None for value in admin["derived"][kind]["compact"].values()))
        changes = [lambda x: x["counts"].update(selected_terminal=2),
                   lambda x: x["runs"][1]["derived"]["diagnostics"]["compact"].update(tcp_path_m=0),
                   lambda x: x["runs"][1].update(status="completed"),
                   lambda x: x["runs"][1]["selection_provenance"].update(supervisor_terminal={}),
                   lambda x: x.update(complete_terminal_accounting=True)]
        for change in changes:
            invalid = copy.deepcopy(index); change(invalid); write(path, invalid)
            with self.assertRaises(ValueError): read()
        write(path, index)
        Path(refs["recovery_annex_ref"]["path"]).write_text("changed synthetic authority", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Artifact bytes differ"): read()

    def test_actual005_wrapper_binds_admin_annex_and_canonical_sources(self):
        # Load exact versioned helpers without colliding with the legacy wrapper
        # fixture's conventional module names in the same discovery process.
        tools = Path(__file__).parent.parent / "Batch 01" / "Release Analysis 005"
        def module(name, path):
            spec = importlib.util.spec_from_file_location(name, path)
            value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
            return value
        analyzer = module("synthetic_investigation005_analyzer", tools / "analyze_results.py")
        with patch.dict(sys.modules, {"collect_results": analyzer.collector}):
            fixtures = module("synthetic_investigation005_fixtures", tools / "synthetic_fixtures.py")
        fixture = fixtures.Fixture(self.root)
        canonical_sources = fixture.write_canonical()
        with patch.object(analyzer.collector, "verify_annex", side_effect=fixture.fake_verify):
            selected = analyzer.collector.collect(fixture.root, fixture.records, notes=fixture.notes, annex_path=fixture.annex_path)
        selected.update(canonical_sources)
        selected_path = self.root / "selected.json"; fixture.write(selected_path, selected)
        output = self.root / "analysis"
        with patch.object(analyzer, "MAP", self.root / "canonical"), \
             patch.object(analyzer.collector, "verify_annex", side_effect=fixture.fake_verify), \
             patch.object(analyzer.queue_authority, "queued_job", return_value={"id": "synthetic-analysis-job"}), \
             patch.object(analyzer.protocol, "_entropy", side_effect=AssertionError("No seed drawing")):
            provenance = analyzer.analyze_results(fixture.root, selected_path, output)
        page = self.root / "view.html"
        report = analysis_adapter.read_analysis(output / "analysis.json", page)
        receipt_path = self.root / "analysis-receipt.json"
        receipt(receipt_path, "synthetic-analysis-job", output, tools / "analyze_results.py", completed=True)
        sidecar = output / "analysis-provenance.json"
        bound = analysis_provenance.bind_analysis(report, sidecar, receipt_path, page)
        self.assertEqual(bound["report"], report["report"])
        self.assertEqual(Path(provenance["queue_authorization_implementation"]["path"]).resolve(), p.QUEUE_AUTHORIZATION.resolve())
        self.assertEqual(bound["binding"]["disposition_counts"]["administrative_interruption"], 1)
        self.assertEqual(len(bound["binding"]["supplemental_sources"]), 2)
        for change in (lambda x: x["disposition_counts"].update(administrative_interruption=0),
                       lambda x: x["inputs_before"].pop("canonical_notes_source"),
                       lambda x: x.update(recovery_annex_ref=None)):
            invalid = copy.deepcopy(provenance); change(invalid); write(sidecar, invalid)
            with self.assertRaises(ValueError): analysis_provenance.bind_analysis(report, sidecar, receipt_path, page)


if __name__ == "__main__":
    unittest.main()
