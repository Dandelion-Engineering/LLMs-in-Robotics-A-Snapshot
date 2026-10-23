"""Synthetic protocol/analysis unit checks; no experiments or real held-out seeds.

All gate files and results are artificial fixtures under temporary directories.
The entropy source is replaced in creation tests. Nothing enters Architecture Map.
"""
import copy
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import protocol as p


class ProtocolUnitChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.slots = p.public_run_slots("unit-release")

    def tearDown(self):
        self.temp.cleanup()

    def gates(self, ready=True):
        evidence = self.root / "unit-readiness-evidence.txt"
        evidence.write_text("SYNTHETIC UNIT FIXTURE; NOT ACTUAL READINESS\n", encoding="utf-8")
        freeze = {
            "release_id": "unit-release", "frozen_at": "2000-01-01T00:00:00+00:00",
            "code_sha256": "1" * 64, "environment_sha256": "2" * 64,
            "model_sha256": "3" * 64, "protocol_sha256": p.protocol_sha256(),
            "selection_criteria": "Synthetic unit fixture only", "maximum_retries": 0,
        }
        freeze_path = self.root / "freeze.json"
        freeze_path.write_text(json.dumps(freeze), encoding="utf-8")
        readiness = {
            "release_id": "unit-release", "freeze_sha256": p.sha256_file(freeze_path), "scored_ready": ready,
            "gates": {gate: True for gate in p.REQUIRED_GATES},
            "evidence_refs": [{"path": evidence.name, "sha256": p.sha256_file(evidence)}],
        }
        readiness_path = self.root / "readiness.json"
        readiness_path.write_text(json.dumps(readiness), encoding="utf-8")
        return freeze_path, readiness_path

    def synthetic_results(self, success=True):
        return [{"run_id": r["run_id"], "execution_status": "completed", "validity": "valid",
                 "independent_outcome": {"success": success}, "completion_time_s": 10 if success else None,
                 "wall_duration_s": 10 if success else r["cap_s"]} for r in self.slots]

    def analyze(self, results):
        return p.analyze(self.slots, results, bootstrap_draws=100, analysis_seed=17)

    def comparison(self, report, left="baseline", right="A1", right_condition="persistent"):
        return next(c for c in report["comparisons"] if c["left"] == {"architecture": left, "condition": "persistent"}
                    and c["right"] == {"architecture": right, "condition": right_condition})

    def test_exact_matrix_and_horizon_counts(self):
        counts = p.validate_matrix(self.slots)
        self.assertEqual(counts, {"runs": 264, "main_runs": 192, "ablation_runs": 72,
                                  "case_units": 24, "scenario_families": 20, "paired_blocks": 48})
        self.assertEqual({r["parts"] for r in self.slots if r["horizon"] == "extended"}, {10})
        self.assertFalse(any(r["architecture"] == "baseline" and r["condition"] == "no-persistence" for r in self.slots))
        for architecture in p.LLM_ARCHITECTURES:
            self.assertEqual(sum(r["architecture"] == architecture and r["condition"] == "no-persistence" for r in self.slots), 24)

    def test_counterparts_are_four_pure_restart_cases_with_balanced_horizons(self):
        cases = {c["case_id"]: c for c in p.public_cases()}
        controls = [c for c in cases.values() if c["uninterrupted_counterpart"]]
        self.assertEqual(len(controls), 4)
        self.assertEqual(p.Counter(c["horizon"] for c in controls), {"short": 1, "standard": 2, "extended": 1})
        for control in controls:
            interrupted = cases[control["counterpart_case_id"]]
            self.assertEqual(control["scenario"], "nominal")
            self.assertEqual(interrupted["scenario"], "restart")
            self.assertEqual(control["scenario_family_id"], interrupted["scenario_family_id"])
            self.assertEqual(control["horizon"], interrupted["horizon"])

    def test_public_description_never_uses_entropy(self):
        with patch.object(p, "_entropy", side_effect=AssertionError("no seed generation")):
            value = p.describe()
        self.assertEqual(value["planned_wall_cap_s"], 156600)
        self.assertEqual(value["ordinary_evidence_allowance_gib_at_2_per_run"], 528)
        self.assertNotIn("world_seed", json.dumps(value))
        self.assertEqual(value["cross_tab"]["standard"], {"nominal": 2, "physical-or-order-change": 3, "continuity-or-mixed": 3})

    def test_matrix_refuses_reduction_duplicate_and_wrong_horizon(self):
        with self.assertRaises(p.ProtocolError):
            p.validate_matrix(self.slots[:-1])
        duplicate = copy.deepcopy(self.slots)
        duplicate[-1] = copy.deepcopy(duplicate[0])
        with self.assertRaises(p.ProtocolError):
            p.validate_matrix(duplicate)
        wrong = copy.deepcopy(self.slots)
        next(r for r in wrong if r["horizon"] == "extended")["parts"] = 9
        with self.assertRaises(p.ProtocolError):
            p.validate_matrix(wrong)

    def test_not_ready_refuses_before_entropy_or_output_creation(self):
        freeze, ready = self.gates(ready=False)
        output = self.root / "release"
        with patch.object(p, "_entropy", side_effect=AssertionError("must not generate seeds")):
            with self.assertRaises(p.ProtocolError):
                p.create_release(output, freeze, ready)
        self.assertFalse(output.exists())

    def test_readiness_requires_exact_freeze_and_all_gates(self):
        freeze, ready = self.gates()
        obj = json.loads(ready.read_text(encoding="utf-8"))
        obj["gates"]["public_perception"] = False
        ready.write_text(json.dumps(obj), encoding="utf-8")
        with self.assertRaises(p.ProtocolError):
            p.validate_release_gates(freeze, ready)
        obj["gates"]["public_perception"] = True
        obj["freeze_sha256"] = "0" * 64
        ready.write_text(json.dumps(obj), encoding="utf-8")
        with self.assertRaises(p.ProtocolError):
            p.validate_release_gates(freeze, ready)

    def test_readiness_evidence_hash_is_verified(self):
        freeze, ready = self.gates()
        (self.root / "unit-readiness-evidence.txt").write_text("changed", encoding="utf-8")
        with self.assertRaises(p.ProtocolError):
            p.validate_release_gates(freeze, ready)

    def test_generator_source_must_match_frozen_protocol(self):
        freeze, ready = self.gates()
        obj = json.loads(freeze.read_text(encoding="utf-8"))
        obj["protocol_sha256"] = "0" * 64
        freeze.write_text(json.dumps(obj), encoding="utf-8")
        with self.assertRaises(p.ProtocolError):
            p.validate_release_gates(freeze, ready)

    def create_synthetic_release(self):
        freeze, ready = self.gates()
        output = self.root / "synthetic-release"
        # Deterministic fake entropy, explicitly no real concealed evaluation.
        sequence = itertools.count(1)
        with patch.object(p, "_entropy", side_effect=lambda bits: next(sequence)):
            summary = p.create_release(output, freeze, ready)
        return output, summary

    def test_creation_preserves_all_seed_pairings_and_264_distinct_manifests(self):
        output, summary = self.create_synthetic_release()
        manifests = p.load_release(output)
        self.assertEqual(len(manifests), 264)
        self.assertEqual(len(list((output / "runs").glob("*.json"))), 264)
        self.assertNotIn("world_seed", json.dumps(summary))
        ordered = sorted(manifests, key=lambda r: r["scheduled_index"])
        self.assertEqual([r["scheduled_index"] for r in ordered], list(range(1, 265)))
        family = [r for r in manifests if r["scenario_family_id"] == "F01"]
        self.assertEqual(len({(r["seeds"]["world_seed"], r["seeds"]["layout_seed"]) for r in family}), 1)
        for replicate in (1, 2):
            self.assertEqual(len({(r["seeds"]["policy_seed"], r["seeds"]["noise_seed"]) for r in family if r["replicate"] == replicate}), 1)
        self.assertEqual(len({r["seeds"]["policy_seed"] for r in family}), 2)

    def test_seed_mismatch_across_entrant_is_rejected(self):
        output, _ = self.create_synthetic_release()
        manifests = p.load_release(output)
        manifests[0]["seeds"]["world_seed"] += 100000
        with self.assertRaises(p.ProtocolError):
            p.validate_matrix(manifests)

    def test_existing_release_and_changed_manifest_are_rejected(self):
        output, _ = self.create_synthetic_release()
        with self.assertRaises(p.ProtocolError):
            p.create_release(output, self.root / "freeze.json", self.root / "readiness.json")
        path = next((output / "runs").glob("*.json"))
        path.write_text("{}", encoding="utf-8")
        with self.assertRaises(p.ProtocolError):
            p.load_release(output)

    def test_unrun_is_not_failure_and_rates_are_missing(self):
        report = self.analyze([])
        self.assertEqual(report["dispositions"], {"unrun": 264})
        self.assertEqual(report["time_observations"], [])
        pair = self.comparison(report)
        self.assertEqual(pair["paired_run_count"], 0)
        self.assertIsNone(pair["paired_success_difference"])
        self.assertIsNone(pair["left_success_rate"])
        self.assertIsNone(pair["bootstrap"]["interval"])
        self.assertTrue(all(entry["success_rate"] is None for entry in report["entrants"]))

    def test_success_tables_keep_replicates_and_counterparts_clustered(self):
        report = self.analyze(self.synthetic_results())
        pair = self.comparison(report)
        self.assertEqual(pair["paired_table"], {"both_success": 48, "left_only": 0, "right_only": 0, "both_failure": 0})
        self.assertEqual(pair["case_units"], 24)
        self.assertEqual(pair["scenario_families"], 20)
        self.assertEqual(pair["bootstrap"]["cluster_count"], 20)
        self.assertEqual(pair["bootstrap"]["interval"], [0.0, 0.0])
        self.assertEqual(pair["strata"]["horizon"]["short"]["paired_run_count"], 16)
        self.assertEqual(pair["strata"]["horizon"]["standard"]["scenario_families"], 6)
        ablation = self.comparison(report, "A1", "A1", "no-persistence")
        self.assertEqual(ablation["paired_run_count"], 24)
        self.assertEqual(ablation["case_units"], 12)
        self.assertEqual(ablation["scenario_families"], 8)

    def test_exact_paired_disagreement_table_and_seeded_interval(self):
        results = self.synthetic_results()
        for result, manifest in zip(results, self.slots):
            result["independent_outcome"]["success"] = manifest["architecture"] != "A1" or manifest["horizon"] == "short"
        first, second = self.analyze(results), self.analyze(results)
        pair = self.comparison(first)
        self.assertEqual(pair["paired_table"], {"both_success": 16, "left_only": 32, "right_only": 0, "both_failure": 0})
        self.assertAlmostEqual(pair["paired_success_difference"], 2 / 3)
        self.assertEqual(pair["bootstrap"], self.comparison(second)["bootstrap"])

    def test_infrastructure_invalid_excludes_all_entrants_and_conditions_in_block(self):
        results = self.synthetic_results()
        index = next(i for i, m in enumerate(self.slots) if m["case_id"] == "C06" and m["replicate"] == 1
                     and m["architecture"] == "A1" and m["condition"] == "no-persistence")
        results[index].update(validity="invalid", invalidity_class="infrastructure", validity_reason="synthetic exposed oracle")
        report = self.analyze(results)
        self.assertEqual(report["dispositions"]["paired_block_infrastructure_invalid"], 7)
        self.assertEqual(report["dispositions"]["eligible"], 257)
        self.assertEqual(self.comparison(report)["paired_run_count"], 47)
        self.assertEqual(self.comparison(report, "A2", "A2", "no-persistence")["paired_run_count"], 23)
        self.assertEqual(len(report["excluded_paired_blocks"]), 1)

    def test_candidate_failure_remains_in_valid_denominator(self):
        results = self.synthetic_results()
        results[0].update(execution_status="failed", independent_outcome={"success": False}, completion_time_s=None)
        report = self.analyze(results)
        self.assertEqual(report["dispositions"], {"eligible": 264})
        self.assertEqual(self.comparison(report)["paired_table"]["right_only"], 1)

    def test_actual_supervisor_classification_excludes_whole_block_only_for_infrastructure(self):
        from experiment import result_validity
        index=next(i for i,m in enumerate(self.slots) if m['case_id']=='C06' and m['replicate']==1
                   and m['architecture']=='A1' and m['condition']=='no-persistence')
        for failure in ('infrastructure_failure','host_resource_invalid','candidate_contract_failure','candidate_transport_failure'):
            results=self.synthetic_results()
            results[index].update(result_validity(failure_class=failure,cleanup_errors=[],timing_failed=False,evaluation_authorized=True),
                                  failure_class=failure,execution_status='failed',independent_outcome={'success':False},completion_time_s=None)
            report=self.analyze(results)
            if failure in ('infrastructure_failure','host_resource_invalid'):
                self.assertEqual(report['dispositions']['paired_block_infrastructure_invalid'],7)
                self.assertEqual(report['dispositions']['eligible'],257)
            else:
                self.assertEqual(report['dispositions'],{'eligible':264})

    def test_unknown_validity_and_missing_outcome_stay_distinct(self):
        results = self.synthetic_results()
        results[0]["validity"] = "unknown"
        results[1].pop("independent_outcome")
        results[2]["execution_status"] = "not_run"
        report = self.analyze(results)
        self.assertEqual(report["dispositions"]["unknown_validity"], 1)
        self.assertEqual(report["dispositions"]["missing_outcome"], 1)
        self.assertEqual(report["dispositions"]["unrun"], 1)

    def test_censoring_keeps_actual_exposure_separate_from_failure_cap_marker(self):
        results = self.synthetic_results()
        results[0].update(execution_status="failed", independent_outcome={"success": False}, wall_duration_s=12,
                          completion_time_s=99)  # A failed run's spurious success time cannot become data.
        results[1].pop("completion_time_s")
        report = self.analyze(results)
        first = next(t for t in report["time_observations"] if t["run_id"] == results[0]["run_id"])
        second = next(t for t in report["time_observations"] if t["run_id"] == results[1]["run_id"])
        self.assertTrue(first["right_censored"])
        self.assertEqual(first["observed_censor_time_s"], 12)
        self.assertEqual(first["plot_time_s"], 300)
        self.assertIsNone(first["completion_time_s"])
        self.assertIsNone(second["plot_time_s"])
        self.assertIn("not measured", second["time_missing_reason"])

    def test_duplicate_and_unknown_results_require_explicit_resolution(self):
        result = self.synthetic_results()[0]
        with self.assertRaises(p.ProtocolError):
            self.analyze([result, result])
        with self.assertRaises(p.ProtocolError):
            self.analyze([{**result, "run_id": "unregistered"}])

    def test_optional_case_cluster_diagnostic_is_labeled(self):
        rows = self.comparison(self.analyze(self.synthetic_results()))["paired_rows"]
        diagnostic = p.cluster_bootstrap(rows, draws=100, seed=5, cluster_key="case_id")
        self.assertEqual(diagnostic["cluster_count"], 24)
        self.assertEqual(diagnostic["cluster_key"], "case_id")
        with self.assertRaises(p.ProtocolError):
            p.cluster_bootstrap(rows, draws=10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
