"""Temporary synthetic restart decisions only; never physical calibration data."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import unittest

import continuity as c
from test_continuity import Fixture


def rehash(event):
    event["payload_sha256"] = hashlib.sha256(c.canonical(event["payload"])).hexdigest()


def bind(event, state="pass"):
    snapshot = {"schema_version": "protected-restart-state-1.0", "capture_sim_time_s": event["sim_time_s"],
                "exposure": copy.deepcopy(event["payload"]["exposure"]), "geometry": {"synthetic_test_only": True},
                "source_hashes": {"cell.py": "1" * 64}, "physical_configuration_sha256": "2" * 64}
    snapshot["snapshot_sha256"] = hashlib.sha256(c.canonical(snapshot)).hexdigest()
    decision = {"schema_version": "restart-admissibility-1.0", "snapshot_sha256": snapshot["snapshot_sha256"],
                "actual_cut": snapshot["exposure"]["actual_cut"], "state": {"pass": "admissible", "fail": "inadmissible", "unknown": "unknown"}[state],
                "calibration_input_sha256": hashlib.sha256(c.canonical({})).hexdigest(),
                "predicates": [{"name": "synthetic_required_predicate", "state": state, "required": True,
                                "reason": "Synthetic explicit decision; this is not measured calibration", "observed": None, "domain": "physical_state"},
                               {"name": "infrastructure_evidence", "state": "unknown", "required": False, "reason": "Not supplied"}],
                "effects": {"paired_block_excluded": False, "episode_outcome_assigned": False}}
    event["payload"].update(protected_restart_state=snapshot, restart_admissibility=decision)
    rehash(event)
    return snapshot, decision


class RestartAdmissibilityReaderTests(unittest.TestCase):
    def test_explicit_decision_is_bound_to_containing_event_and_preserves_required_unknown(self):
        for predicate, expected in (("pass", "established"), ("fail", "inadmissible"), ("unknown", "unknown")):
            f = Fixture(); cut, _ = f.restart(); snapshot, decision = bind(cut, predicate)
            report = f.run(); mark = report["rows"][0]["admissibility"]
            self.assertEqual(mark["state"], expected)
            self.assertEqual(mark["evidence"][0]["event_id"], cut["event_id"])
            self.assertEqual(mark["evidence"][0]["sim_time_s"], snapshot["capture_sim_time_s"])
            self.assertEqual(mark["recorded_decision"], decision)
            self.assertEqual(mark["snapshot_source_hashes"], snapshot["source_hashes"])
            self.assertFalse(mark["infrastructure_exclusion_assigned"])
            self.assertIn(report["rows"][0]["recovery"]["state"], ("unknown", "not_established"))
            self.assertEqual(report["coverage"]["known_admissible"], int(predicate == "pass"))

    def test_optional_infrastructure_failure_is_preserved_without_assigning_block_exclusion(self):
        f = Fixture(); cut, _ = f.restart(); _, decision = bind(cut)
        decision["predicates"][1]["state"] = "fail"; rehash(cut)
        mark = f.run()["rows"][0]["admissibility"]
        self.assertEqual(mark["state"], "established")
        self.assertEqual(mark["recorded_decision"]["predicates"][1]["state"], "fail")
        self.assertFalse(mark["infrastructure_exclusion_assigned"])

    def test_snapshot_without_decision_unknown_schema_and_missing_snapshot_keep_exact_citation(self):
        for mode in ("snapshot_only", "future_schema", "decision_only"):
            f = Fixture(); cut, _ = f.restart(); bind(cut)
            if mode == "snapshot_only": del cut["payload"]["restart_admissibility"]
            elif mode == "future_schema": cut["payload"]["restart_admissibility"]["schema_version"] = "unknown-future-2"
            else: del cut["payload"]["protected_restart_state"]
            rehash(cut)
            mark = f.run()["rows"][0]["admissibility"]
            self.assertEqual(mark["state"], "unknown")
            self.assertEqual(mark["evidence"][0]["event_id"], cut["event_id"])

    def test_stale_snapshot_is_not_exact_cut_evidence(self):
        f = Fixture(); cut, _ = f.restart(); snapshot, decision = bind(cut)
        snapshot["capture_sim_time_s"] -= .01
        snapshot["snapshot_sha256"] = hashlib.sha256(c.canonical({k: v for k, v in snapshot.items() if k != "snapshot_sha256"})).hexdigest()
        decision["snapshot_sha256"] = snapshot["snapshot_sha256"]; rehash(cut)
        mark = f.run()["rows"][0]["admissibility"]
        self.assertEqual(mark["state"], "unknown")
        self.assertIn("exact cut", mark["reason"])

    def test_wrong_hash_cut_predicate_aggregate_and_duplicate_names_are_refused(self):
        mutations = [lambda s, d: s.update(snapshot_sha256="0" * 64),
                     lambda s, d: d.update(snapshot_sha256="0" * 64),
                     lambda s, d: d.update(actual_cut="before_outcome"),
                     lambda s, d: d.update(state="inadmissible"),
                     lambda s, d: d["predicates"].append(copy.deepcopy(d["predicates"][0])),
                     lambda s, d: d["predicates"][0].update(required="true")]
        for mutate in mutations:
            f = Fixture(); cut, _ = f.restart(); snapshot, decision = bind(cut); mutate(snapshot, decision); rehash(cut)
            with self.assertRaises(ValueError): f.run()

    def test_additional_protected_prior_refs_are_preserved_but_future_and_candidate_refs_refused(self):
        f = Fixture(); prior = f.world(); cut, ready = f.restart(); _, decision = bind(cut)
        decision["predicate_evidence_event_ids"] = [prior["event_id"], cut["event_id"], prior["event_id"]]; rehash(cut)
        mark = f.run()["rows"][0]["admissibility"]
        self.assertEqual([r["event_id"] for r in mark["evidence"]], [cut["event_id"], prior["event_id"]])
        for ids in ([ready["event_id"]], [999], [True]):
            decision["predicate_evidence_event_ids"] = ids; rehash(cut)
            with self.assertRaises(ValueError): f.run()
        f = Fixture(); candidate = f.add("candidate_reply", {}, source="candidate"); cut, _ = f.restart(); _, decision = bind(cut)
        decision["predicate_evidence_event_ids"] = [candidate["event_id"]]; rehash(cut)
        with self.assertRaises(ValueError): f.run()

    def test_candidate_cannot_supply_protected_decision(self):
        f = Fixture(); cut, _ = f.restart(); bind(cut); cut["source"] = "candidate"
        with self.assertRaisesRegex(ValueError, "protected"): f.run()

    def test_embedded_calibration_preserves_hash_source_matching_and_prior_refs(self):
        f = Fixture(); cut, _ = f.restart(); snapshot, decision = bind(cut)
        decision["predicates"][0]["name"] = "measured_grip_envelope"
        calibration = {"grip": {"source_hashes": snapshot["source_hashes"],
                                "physical_configuration_sha256": snapshot["physical_configuration_sha256"],
                                "envelope_basis": "measured_before_this_intervention",
                                "evidence_refs": [{"kind": "prior_physical_calibration", "artifact_id": "synthetic-prior-only",
                                                   "sha256": "3" * 64, "bytes_verified_by_operator": True}]}}
        cut["payload"]["restart_calibration"] = calibration
        decision["calibration_input_sha256"] = hashlib.sha256(c.canonical(calibration)).hexdigest(); rehash(cut)
        mark = f.run()["rows"][0]["admissibility"]; provenance = mark["calibration_provenance"]
        self.assertTrue(provenance["reference_checks"][0]["reference_compatible"])
        self.assertEqual(provenance["recorded_input"], calibration)
        self.assertFalse(provenance["artifact_bytes_verified_here"])
        self.assertFalse(provenance["physical_envelopes_recomputed"])
        self.assertEqual(mark["evidence"][0]["event_id"], cut["event_id"])
        calibration["grip"]["source_hashes"] = {"cell.py": "4" * 64}
        rehash(cut)
        with self.assertRaisesRegex(ValueError, "calibration input hash"): f.run()
        decision["calibration_input_sha256"] = hashlib.sha256(c.canonical(calibration)).hexdigest(); rehash(cut)
        with self.assertRaisesRegex(ValueError, "compatible embedded"): f.run()
        decision["state"] = "unknown"; decision["predicates"][0]["state"] = "unknown"; rehash(cut)
        mark = f.run()["rows"][0]["admissibility"]
        self.assertEqual(mark["state"], "unknown")
        self.assertFalse(mark["calibration_provenance"]["reference_checks"][0]["source_hashes_match"])

    def test_absent_calibration_is_explicitly_unavailable_not_reconstructed(self):
        f = Fixture(); cut, _ = f.restart(); bind(cut, "unknown")
        provenance = f.run()["rows"][0]["admissibility"]["calibration_provenance"]
        self.assertFalse(provenance["embedded_input_available"])
        self.assertNotIn("recorded_input", provenance)

    def test_exact_current_helper_shape_accepts_unknown_without_loading_physics(self):
        # The helper is pure at import; this never calls its live-Cell capture.
        path = Path(c.__file__).resolve().parent.parent / "Batch 01" / "Calibration Tools" / "restart_state.py"
        spec = importlib.util.spec_from_file_location("synthetic_classifier_compatibility", path)
        helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
        f = Fixture(); cut, _ = f.restart(); snapshot, _ = bind(cut)
        cut["payload"]["restart_admissibility"] = helper.classify_restart(snapshot); rehash(cut)
        mark = f.run()["rows"][0]["admissibility"]
        self.assertEqual(mark["state"], "unknown")
        self.assertIn("capture_completeness", [p["name"] for p in mark["recorded_decision"]["predicates"]])


if __name__ == "__main__":
    unittest.main()
