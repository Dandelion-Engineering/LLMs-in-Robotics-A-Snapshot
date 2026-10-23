"""Synthetic qualification, protected events and files only; no physics/queue."""
import copy
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import continuity as c
import qualified_restart as q
from test_continuity import Fixture, annotation

HELPERS = q.HERE.parent / "Batch 01" / "Restart Qualification Tools"


def test_apis():
    # The Runtime loader is a held proposal until root applies it. Test the
    # held loader directly without modifying Runtime or claiming integration.
    with patch.object(sys, "path", [str(HELPERS), str(q.RUNTIME), *sys.path]):
        loader = importlib.import_module("calibration_loader")
        helper_fixture = importlib.import_module("test_calibration_loader")
        cases = importlib.import_module("test_runtime_patch")
        classifier = importlib.import_module("restart_state")
        spec = importlib.util.spec_from_file_location("investigation_qualified_snapshot_fixture", q.RUNTIME / "test_restart_state.py")
        fixtures = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixtures)
    return loader, helper_fixture, cases, classifier, fixtures


class QualifiedFixture:
    def __init__(self, root, apis, *, required="recover_held_admitted", phase="closed_grip_transfer"):
        self.root = root; self.loader, helper, cases, self.classifier, fixtures = apis
        self.freeze, self.freeze_path, self.artifact, self.bundle_path = helper.write_fixture(root)
        self.freeze["restart_qualification"]["absence_endpoint"] = required
        bundle = q.object_file(self.bundle_path)
        for cell in bundle["cells"]: cell["absence_endpoint"] = required
        self.bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
        self.freeze["restart_qualification"].update(sha256=q.source(self.bundle_path)["sha256"], bundle_sha256=self.classifier.digest(bundle))
        self.freeze_path.write_text(json.dumps(self.freeze), encoding="utf-8")
        self.payload = self.loader.load_restart_qualification(self.freeze, self.freeze_path).as_dict()
        self.f = Fixture(); self.f.manifest.update(stage="evaluation", restart_qualification_identity=self.payload["identity"])
        self.f.manifest["restart_opportunity"]["cut"] = phase
        self.f.result["stage"] = "evaluation"
        self.snapshot, _, _ = cases.case(fixtures)
        if phase != "closed_grip_transfer":
            carry_snapshot = self.snapshot
            self.snapshot = fixtures.snapshot(phase)
            for key in ("physical_configuration_sha256", "scene_xml_sha256", "physical_class_observation"):
                self.snapshot[key] = copy.deepcopy(carry_snapshot[key])
        sources = bundle["class_spec"]["required_source_hashes"]
        self.snapshot["source_hashes"] = copy.deepcopy(sources)
        self.snapshot["physical_class_observation"]["source_hashes"] = copy.deepcopy(sources)
        # Match the loader fixture's explicitly measured destination envelope.
        self.snapshot["geometry"]["zones"]["parking2"] = copy.deepcopy(bundle["cells"][0]["route_envelope"]["destination_region_m"])
        self.snapshot["snapshot_sha256"] = self.classifier.digest({k: v for k, v in self.snapshot.items() if k != "snapshot_sha256"})
        self.selected = self.loader.select_restart_calibration(self.payload, self.snapshot)
        self.decision = self.classifier.classify_restart(self.snapshot, calibration=self.selected["calibration"],
                                                       qualification_context=self.payload["qualification_context"])
        if self.decision["state"] != "admissible": raise AssertionError(self.decision)
        self.release = root / "release"; self.release.mkdir()
        plan = {"run_id": self.f.manifest["run_id"], "stage": "evaluation", "freeze_sha256": q.source(self.freeze_path)["sha256"]}
        plan_path = self.release / "run.json"; plan_path.write_text(json.dumps(plan), encoding="utf-8")
        release = {"freeze_manifest": q.source(self.freeze_path), "manifest_refs": [{"run_id": plan["run_id"], **q.source(plan_path)}]}
        release_path = self.release / "release.json"; release_path.write_text(json.dumps(release), encoding="utf-8")
        self.f.manifest["evaluation_authorization"] = {"release_sha256": q.source(release_path)["sha256"],
                                                       "manifest_sha256": q.source(plan_path)["sha256"]}
        self.context = self.load()
        self.cut = self.f.add("restart_begin", {"incarnation": 1, "exposure": self.snapshot["exposure"],
            "protected_restart_state": self.snapshot, "restart_admissibility": self.decision,
            "restart_calibration": self.selected["calibration"], "restart_qualification_identity": self.payload["identity"],
            "restart_qualification_selection": {k: v for k, v in self.selected.items() if k != "calibration"},
            "capture_landmarks": {"start": {"wall_s": 910., "sim_s": 10.}, "finish": {"wall_s": 910.1, "sim_s": 10.},
                                  "classification_finish": {"wall_s": 910.2, "sim_s": 10.}}}, source="evaluator", t=10.)
        self.start = {"wall_s": 910.3, "sim_s": 10.}
        self.revoked = self.f.add("restart_authority_revoked", {"before_cancel": self.start,
            "after_cancel": {"wall_s": 910.4, "sim_s": 10.}}, source="evaluator", parents=[self.cut["event_id"]], t=10.)

    def load(self):
        with patch.object(q, "runtime_api", return_value=(self.loader, self.classifier)):
            return q.load_evaluation_context(self.release, self.f.manifest)

    def fact(self, endpoint, duration, *, parents=None, control=None):
        end = {"wall_s": 910.5 + duration, "sim_s": 10. + duration}
        fact = self.loader.absence_observation(self.start, end, endpoint, self.payload["absence"])
        fact.update(restart_event_id=self.cut["event_id"], qualification_identity=self.payload["identity"])
        if control is not None: fact["control_admission"] = control
        event = self.f.add("restart_absence", fact, source="evaluator", parents=parents or [self.cut["event_id"]], t=end["sim_s"])
        return event

    def ready(self, duration=.2):
        event = self.fact("restart_ready", duration)
        return self.f.add("restart_ready", {"incarnation": 2, "reply": {}, "absence": event["payload"]},
                          parents=[self.cut["event_id"]], t=event["sim_time_s"])

    def control(self, duration=.8, operation="recover_held", destination="parking2", *, suppressed=False):
        action = {"request_id": "control-" + str(len(self.f.events)), "incarnation": 2,
                  "operation": operation, "destination": destination}
        request = self.f.add("action_requested", action, source="candidate", t=10.+duration-.01)
        feedback = {"request_id": action["request_id"], "status": "accepted", "duplicate_suppressed": suppressed}
        admission = self.f.add("action_admission", feedback, source="gateway", parents=[request["event_id"]], t=10.+duration)
        control = self.loader.first_control_endpoint(action, feedback, incarnation=2, expected_destination="parking2")
        if control is not None:
            return self.fact(control["endpoint"], duration, parents=[self.cut["event_id"], admission["event_id"]], control=control)
        return admission

    def run(self, *, context=True, annotations=()):
        return c.extract(self.f.manifest, self.f.result, self.f.events, qualification_context=self.context if context else None,
                         annotations=annotations, rubric_sha256="synthetic-only")

    def rehash(self, event):
        event["payload_sha256"] = self.classifier.digest(event["payload"])

    def refresh_snapshot(self):
        self.snapshot["snapshot_sha256"] = self.classifier.digest({k: v for k, v in self.snapshot.items() if k != "snapshot_sha256"})
        self.selected = self.loader.select_restart_calibration(self.payload, self.snapshot)
        self.decision = self.classifier.classify_restart(self.snapshot, calibration=self.selected["calibration"],
                                                       qualification_context=self.payload["qualification_context"])
        self.cut["payload"].update(exposure=self.snapshot["exposure"], protected_restart_state=self.snapshot,
            restart_admissibility=self.decision, restart_calibration=self.selected["calibration"],
            restart_qualification_selection={k: v for k, v in self.selected.items() if k != "calibration"})
        self.rehash(self.cut)


class QualifiedReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.apis = test_apis()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def fixture(self, **kwargs): return QualifiedFixture(self.root, self.apis, **kwargs)

    def test_verified_loader_classifier_and_covered_exact_endpoint_establish_only_admissibility(self):
        f = self.fixture(); f.ready(); f.control()
        report = f.run(); row = report["rows"][0]
        self.assertEqual(row["admissibility"]["state"], "established")
        self.assertEqual(row["qualified_restart"]["absence"]["state"], "pass")
        self.assertEqual(report["coverage"]["known_admissible"], 1)
        self.assertEqual(report["coverage"]["known_admissible_qualified_context"], 1)
        self.assertEqual(report["coverage"]["known_admissible_carry_qualified"], 1)
        self.assertEqual(report["coverage"]["known_admissible_empty_instantaneous"], 0)
        self.assertEqual(report["coverage"]["qualified_carry_exposures"], 1)
        self.assertEqual(report["coverage"]["qualified_absence_coverage_pass"], 1)
        self.assertEqual(report["coverage"]["qualified_absence_coverage_not_applicable"], 0)
        self.assertEqual(report["coverage"]["known_admissible_recorded_or_annotated"], 0)
        self.assertEqual(report["coverage"]["established_recoveries"], 0)
        self.assertEqual(row["recovery"]["state"], "not_established")
        self.assertIn(str(f.artifact.resolve()), report["sources"])

    def test_embedded_qualification_flags_without_independent_context_stay_unknown(self):
        f = self.fixture(); f.ready(); f.control()
        row = f.run(context=False)["rows"][0]
        self.assertEqual(row["admissibility"]["state"], "unknown")
        self.assertEqual(row["admissibility"]["recorded_at_cut"]["state"], "admissible")
        self.assertEqual(row["recovery"]["state"], "unknown")

    def test_ready_is_lower_bound_when_first_recovery_admission_is_required(self):
        f = self.fixture(); f.ready()
        row = f.run()["rows"][0]
        self.assertEqual(row["admissibility"]["state"], "unknown")
        self.assertAlmostEqual(row["qualified_restart"]["absence"]["observed_elapsed_lower_bound_s"], .2)

    def test_exact_frozen_ready_convention_is_supported(self):
        f = self.fixture(required="restart_ready"); f.ready()
        self.assertEqual(f.run()["coverage"]["known_admissible"], 1)

    def test_exceeded_or_missing_endpoint_cannot_be_repaired_by_final_success(self):
        f = self.fixture(); f.ready(); f.control(duration=1.2)
        row = f.run()["rows"][0]
        self.assertEqual(row["admissibility"]["state"], "unknown")
        self.assertIn("exceeded", row["qualified_restart"]["absence"]["reason"])
        self.assertEqual(f.f.result["outcome"], "success")

    def test_episode_end_without_required_endpoint_retains_elapsed_lower_bound(self):
        f = self.fixture(); f.ready(); f.fact("episode_end_unobserved", 2.)
        row = f.run()["rows"][0]
        self.assertEqual(row["admissibility"]["state"], "unknown")
        self.assertEqual(row["qualified_restart"]["absence"]["observed_elapsed_lower_bound_s"], 2.)

    def test_wrong_first_control_cannot_be_replaced_by_later_favorable_action(self):
        f = self.fixture(); f.ready(); f.control(.5, destination="parking1"); f.control(.8)
        row = f.run()["rows"][0]
        self.assertEqual(row["admissibility"]["state"], "unknown")
        self.assertEqual(row["qualified_restart"]["absence"]["observation"]["observed_endpoint"], "other_control_admitted")

    def test_passive_or_duplicate_admission_does_not_end_hold_opportunity(self):
        f = self.fixture(); f.ready(); f.control(.3, operation="observe"); f.control(.4, suppressed=True); f.control(.8)
        self.assertEqual(f.run()["coverage"]["known_admissible"], 1)

    def test_annotation_cannot_waive_missing_independent_qualification(self):
        f = self.fixture(); f.ready(); f.control()
        marked = annotation("admissibility", [f.cut])
        row = f.run(context=False, annotations=[marked])["rows"][0]
        self.assertEqual(row["admissibility"]["state"], "unknown")
        self.assertEqual(row["annotated_admissibility"]["state"], "established")

    def test_forged_recorded_coverage_or_classifier_is_rejected(self):
        f = self.fixture(); f.ready(); absence = f.control()
        absence["payload"]["coverage"]["state"] = "unknown"; f.rehash(absence)
        with self.assertRaisesRegex(ValueError, "duration/coverage"): f.run()
        absence["payload"]["coverage"]["state"] = "pass"; f.rehash(absence)
        f.cut["payload"]["restart_admissibility"]["state"] = "unknown"; f.rehash(f.cut)
        with self.assertRaisesRegex(ValueError, "recomputation"): f.run()

    def test_external_bundle_artifact_and_release_bindings_are_reverified(self):
        f = self.fixture(); f.ready(); f.control()
        f.artifact.write_text("changed synthetic evidence", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "source changed"): f.run()
        with self.assertRaises(ValueError): f.load()

    def test_unbound_freeze_and_forged_context_cannot_supply_authority(self):
        f = self.fixture()
        f.f.manifest["evaluation_authorization"]["release_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "hash differs"): f.load()
        forged = q.VerifiedQualifiedContext(f.context.run_id, f.context.payload_json, f.context.sources_json, f.loader, f.classifier)
        with self.assertRaisesRegex(ValueError, "Unverified"): forged.payload()

    def test_missing_capture_revocation_or_endpoint_is_unknown_not_zero(self):
        f = self.fixture(); f.ready(); f.control()
        f.cut["payload"].pop("capture_landmarks"); f.rehash(f.cut)
        row = f.run()["rows"][0]
        self.assertEqual(row["admissibility"]["state"], "unknown")
        self.assertNotIn("actual_absence_s", row["qualified_restart"]["absence"])

    def test_production_api_refuses_unfrozen_or_missing_helper_before_import(self):
        f = self.fixture()
        with self.assertRaisesRegex(ValueError, "reference"):
            q.runtime_api(f.freeze, f.freeze_path, {})

    def test_simulation_advance_before_revocation_cannot_reuse_initial_snapshot(self):
        f = self.fixture(); f.ready(); f.control()
        f.revoked["payload"]["before_cancel"]["sim_s"] = 10.01
        f.revoked["payload"]["after_cancel"]["sim_s"] = 10.01
        f.rehash(f.revoked)
        row = f.run()["rows"][0]
        self.assertEqual(row["admissibility"]["state"], "unknown")
        self.assertIn("ordering", row["qualified_restart"]["absence"]["reason"])

    def test_manifest_class_identity_cannot_fall_back_to_legacy_recorded_predicates(self):
        f = self.fixture(); f.ready(); f.control()
        f.cut["payload"].pop("restart_qualification_identity")
        f.cut["payload"].pop("restart_calibration")
        f.cut["payload"]["restart_admissibility"].pop("qualified_class_evidence")
        f.rehash(f.cut)
        row = f.run(context=False)["rows"][0]
        self.assertEqual(row["admissibility"]["state"], "unknown")
        self.assertIn("qualified_restart", row)

    def test_physical_failure_remains_inadmissible_even_with_covered_absence(self):
        f = self.fixture()
        snapshot = f.cut["payload"]["protected_restart_state"]
        snapshot["geometry"]["objects"][0]["bounds"]["min"][2] = .05
        snapshot["snapshot_sha256"] = f.classifier.digest({k: v for k, v in snapshot.items() if k != "snapshot_sha256"})
        f.cut["payload"]["restart_admissibility"] = f.classifier.classify_restart(snapshot,
            calibration=f.selected["calibration"], qualification_context=f.payload["qualification_context"])
        f.rehash(f.cut); f.ready(); f.control()
        row = f.run()["rows"][0]
        self.assertEqual(row["admissibility"]["state"], "inadmissible")
        self.assertEqual(row["qualified_restart"]["absence"]["state"], "pass")
        self.assertEqual(row["recovery"]["state"], "unknown")

    def test_no_absence_record_remains_missing(self):
        f = self.fixture()
        row = f.run()["rows"][0]
        self.assertEqual(row["admissibility"]["state"], "unknown")
        self.assertIn("missing", row["qualified_restart"]["absence"]["reason"])
        self.assertNotIn("actual_absence_s", row["qualified_restart"]["absence"])

    def test_all_empty_cut_families_keep_verified_instantaneous_admissibility_without_recovery(self):
        for phase in ("after_acceptance", "after_release", "before_outcome"):
            with self.subTest(phase=phase):
                root = self.root / phase; root.mkdir()
                f = QualifiedFixture(root, self.apis, phase=phase)
                f.ready(); observation = f.control(.8, operation="transport")
                self.assertEqual(observation["payload"]["coverage"]["state"], "unknown")
                self.assertIsNone(f.selected["calibration"])
                self.assertEqual(f.decision["qualified_class_evidence"], [])
                original = copy.deepcopy(f.f.events)
                report = f.run(); row = report["rows"][0]; verified = row["qualified_restart"]
                self.assertEqual(verified["context_verification"], "verified")
                self.assertEqual(verified["admissibility_scope"], "instantaneous_empty")
                self.assertEqual(verified["state"], "established")
                self.assertEqual(verified["recomputed_at_cut"], f.decision)
                self.assertEqual(verified["absence"]["state"], "not_applicable")
                self.assertNotIn("actual_absence_s", verified["absence"])
                self.assertNotIn("observation", verified["absence"])
                self.assertEqual(row["recovery"]["state"], "not_established")
                coverage = report["coverage"]
                for name in ("known_admissible", "known_admissible_qualified_context", "known_admissible_empty_instantaneous",
                             "independently_verified_restart_exposures", "qualified_absence_coverage_not_applicable"):
                    self.assertEqual(coverage[name], 1, name)
                for name in ("known_admissible_carry_qualified", "qualified_carry_exposures", "qualified_absence_coverage_pass",
                             "qualified_absence_coverage_unknown", "qualification_scope_unknown", "established_recoveries"):
                    self.assertEqual(coverage[name], 0, name)
                self.assertEqual(f.f.events, original)

    def test_empty_cut_needs_no_absence_endpoint_and_does_not_claim_covered_duration(self):
        f = self.fixture(phase="after_acceptance")
        row = f.run()["rows"][0]
        self.assertEqual(row["admissibility"]["state"], "established")
        self.assertEqual(row["qualified_restart"]["absence"]["state"], "not_applicable")
        self.assertEqual(row["landmarks"]["runtime_return"]["state"], "unknown")
        self.assertEqual(row["recovery"]["state"], "not_established")

    def test_empty_physical_failure_remains_inadmissible(self):
        f = self.fixture(phase="after_release")
        f.snapshot["contacts"]["by_object"]["A1"]["support_upward_force_N"] = 0.
        f.refresh_snapshot(); self.assertEqual(f.decision["state"], "inadmissible")
        f.ready(); f.control()
        report = f.run(); row = report["rows"][0]
        self.assertEqual(row["admissibility"]["state"], "inadmissible")
        self.assertEqual(row["qualified_restart"]["absence"]["state"], "not_applicable")
        self.assertEqual(report["coverage"]["known_inadmissible"], 1)
        self.assertEqual(report["coverage"]["known_admissible"], 0)
        self.assertEqual(report["coverage"]["qualified_absence_coverage_pass"], 0)

    def test_empty_unknown_predicate_stays_unknown_despite_final_success(self):
        f = self.fixture(phase="before_outcome")
        f.snapshot["observation"]["last_capture_age_s"] = None
        f.refresh_snapshot(); self.assertEqual(f.decision["state"], "unknown")
        f.ready(); f.control(operation="transport")
        report = f.run(); row = report["rows"][0]
        self.assertEqual(row["admissibility"]["state"], "unknown")
        self.assertEqual(row["qualified_restart"]["absence"]["state"], "not_applicable")
        self.assertEqual(report["coverage"]["unknown_admissibility"], 1)
        self.assertEqual(report["coverage"]["known_admissible"], 0)
        self.assertEqual(f.f.result["outcome"], "success")

    def test_empty_cut_cannot_use_recorded_pass_without_independent_context(self):
        f = self.fixture(phase="after_acceptance")
        report = f.run(context=False); row = report["rows"][0]
        self.assertEqual(row["admissibility"]["state"], "unknown")
        self.assertEqual(row["qualified_restart"]["context_verification"], "unknown")
        self.assertEqual(row["qualified_restart"]["admissibility_scope"], "unverified")
        self.assertEqual(report["coverage"]["qualification_scope_unknown"], 1)
        self.assertEqual(report["coverage"]["qualified_absence_coverage_not_applicable"], 0)

    def test_empty_branch_cannot_bypass_snapshot_identity_selection_calibration_or_classifier_checks(self):
        for alteration, message in (("snapshot", "snapshot hash"), ("identity", "identity differs"),
                                    ("selection", "selection differs"), ("calibration", "calibration differs"),
                                    ("classifier", "recomputation")):
            with self.subTest(alteration=alteration):
                root = self.root / alteration; root.mkdir()
                f = QualifiedFixture(root, self.apis, phase="after_acceptance")
                payload = f.cut["payload"]
                if alteration == "snapshot": payload["protected_restart_state"]["robot"]["jaw_width_m"] = .079
                elif alteration == "identity": payload["restart_qualification_identity"] = {}
                elif alteration == "selection": payload["restart_qualification_selection"]["state"] = "pass"
                elif alteration == "calibration": payload["restart_calibration"] = {}
                else: payload["restart_admissibility"]["state"] = "unknown"
                f.rehash(f.cut)
                with self.assertRaisesRegex(ValueError, message): f.run()

    def test_empty_branch_reverifies_external_files(self):
        f = self.fixture(phase="after_acceptance")
        f.artifact.write_text("changed synthetic evidence", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "source changed"): f.run()

    def test_empty_cut_preserves_capture_and_revocation_guards(self):
        for alteration in ("missing_capture", "advanced_sim"):
            with self.subTest(alteration=alteration):
                root = self.root / alteration; root.mkdir()
                f = QualifiedFixture(root, self.apis, phase="after_acceptance")
                if alteration == "missing_capture":
                    f.cut["payload"].pop("capture_landmarks"); f.rehash(f.cut)
                else:
                    f.revoked["payload"]["before_cancel"]["sim_s"] = 10.01
                    f.revoked["payload"]["after_cancel"]["sim_s"] = 10.01
                    f.rehash(f.revoked)
                report = f.run(); row = report["rows"][0]
                self.assertEqual(row["admissibility"]["state"], "unknown")
                self.assertEqual(row["qualified_restart"]["cut_capture_state"], "unknown")
                self.assertEqual(row["qualified_restart"]["absence"]["state"], "not_applicable")
                self.assertEqual(report["coverage"]["known_admissible"], 0)

    def test_fallback_does_not_inherit_empty_cut_or_carry_coverage(self):
        f = self.fixture(phase="after_acceptance")
        f.snapshot["exposure"].update(actual_cut="deadline_fallback", fallback_used=True, configured_milestone_exercised=False)
        f.refresh_snapshot(); self.assertEqual(f.decision["state"], "unknown")
        report = f.run(); row = report["rows"][0]
        self.assertEqual(row["admissibility"]["state"], "unknown")
        self.assertEqual(row["qualified_restart"]["admissibility_scope"], "unsupported_cut")
        self.assertEqual(report["coverage"]["qualification_scope_unknown"], 1)
        self.assertEqual(report["coverage"]["qualified_absence_coverage_not_applicable"], 0)
        self.assertEqual(report["coverage"]["qualified_carry_exposures"], 0)

    def test_all_frozen_helper_hashes_verified_before_any_import(self):
        root = self.root / "synthetic-runtime"; root.mkdir()
        modules, refs = {}, []
        for name in q.MODULES:
            path = root / (name + ".py"); path.write_text("# synthetic, never executed\n", encoding="utf-8")
            modules[name] = SimpleNamespace(__file__=str(path)); refs.append(q.source(path))
        index = self.root / "code.json"; index.write_text(json.dumps({"files": refs}), encoding="utf-8")
        freeze = {"artifacts": {"code": q.source(index)}, "code_sha256": q.source(index)["sha256"]}
        with patch.object(q, "RUNTIME", root), patch.object(q.importlib, "import_module", side_effect=lambda name: modules[name]) as imported:
            sources = {}; q.runtime_api(freeze, self.root / "freeze.json", sources)
            self.assertEqual(imported.call_count, 5); self.assertEqual(len(sources), 6)
            imported.reset_mock()
            (root / "restart_state.py").write_text("# changed synthetic source\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash differs"): q.runtime_api(freeze, self.root / "freeze.json", {})
            imported.assert_not_called()


if __name__ == "__main__": unittest.main()
