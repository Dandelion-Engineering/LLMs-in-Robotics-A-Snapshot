"""Synthetic independent-evaluator counterexamples; NOT robot experiments.

All snapshots below are hand-authored protected-state fixtures. No simulator,
model or scored Architecture Map records are created by these unit checks.
"""
import copy
import math
import unittest

from evaluator import EvaluationError, IndependentEvaluator, ScoringConfig, box_bounds


def zone(x, y, half_x=0.05, half_y=0.05):
    return {"min": [x - half_x, y - half_y, -0.003], "max": [x + half_x, y + half_y, 0.08]}


def obj(name, x, y, *, family="A", kind="part", cycle_id=1):
    half = [.02, .02, .02] if kind == "part" else [.008, .008, .008]
    center = [x, y, half[2]]
    result = {
        "id": name, "family": family, "kind": kind, "position": center,
        "bounds": box_bounds(center, [1., 0., 0., 0., 1., 0., 0., 0., 1.], half),
        "linear_velocity": [0., 0., 0.], "angular_velocity": [0., 0., 0.], "gripper_contact": False,
        "recipe": family, "cycles": 1, "inspection": "pass",
        "cycle_history": [{"cycle_id": cycle_id, "part_id": name, "recipe": family,
                           "accepted": True, "completed": True, "accepted_at": 0., "completed_at": 1.}],
        "inspection_history": [{"inspection_id": "I-" + name, "part_id": name, "status": "pass",
                                "cycle_id": cycle_id, "observed_at": 2.}],
    }
    if kind != "part":
        result.update(recipe=None, cycles=None, inspection=None, cycle_history=None, inspection_history=None)
    return result


def fixture():
    snapshot = {
        "sim_time": 10.,
        "zones": {
            "fixture": zone(0., 0.), "parking1": zone(.2, 0.), "parking2": zone(.35, 0.),
            "inspection": zone(.5, 0.), "tray1": zone(.2, .3, .1, .1),
            "tray2": zone(.45, .3, .1, .1), "tray3": zone(.7, .3, .1, .1),
            "quarantine": zone(.7, -.2), "insert_home_A": zone(-.2, 0.), "insert_home_B": zone(-.2, -.2),
        },
        "objects": [obj("A1", .2, .3), obj("insert_A", 0., 0., kind="insert"),
                    obj("insert_B", -.2, -.2, family="B", kind="insert")],
        "station": {"busy": False, "ready": True, "fault": False, "guard_closed": False, "clamped": False},
        "pending": {"active_request": False, "queued_motion": False, "active_segment": False,
                    "machine_cycle": False, "inspection": False},
        "arm_velocity": [0.] * 7, "finger_velocity": [0., 0.],
        "return_locations": {"insert_A": ["fixture", "insert_home_A"], "insert_B": ["fixture", "insert_home_B"]},
    }
    order = {"version": 1, "closed": True, "requirements": [{"family": "A", "recipe": "A", "tray": "tray1", "count": 1}]}
    return snapshot, order


def move(item, xyz, half=None):
    if half is None:
        half = [(item["bounds"]["max"][i] - item["bounds"]["min"][i]) / 2 for i in range(3)]
    item["position"] = list(xyz)
    item["bounds"] = box_bounds(xyz, [1., 0., 0., 0., 1., 0., 0., 0., 1.], half)


class EvaluatorUnitChecks(unittest.TestCase):
    def settled(self, snapshot, order, *, acceptance_open=True, evaluator=None):
        evaluator = evaluator or IndependentEvaluator()
        start = snapshot["sim_time"]
        result = None
        for i in range(6):
            snapshot["sim_time"] = start + i * .1
            result = evaluator.evaluate_snapshot(snapshot, order, acceptance_open=acceptance_open)
        return result, evaluator

    def assert_failure(self, snapshot, order, code):
        result, _ = self.settled(snapshot, order)
        self.assertFalse(result["success"], result)
        self.assertIn(code, {v["code"] for v in result["violations"]}, result)
        return result

    def test_valid_physical_state_requires_half_second_dwell(self):
        snapshot, order = fixture()
        evaluator = IndependentEvaluator()
        initial = evaluator.evaluate_snapshot(snapshot, order, acceptance_open=True)
        self.assertTrue(initial["immediate_ready"])
        self.assertFalse(initial["success"])
        self.assertEqual(initial["accepted_count"], 0)
        for i in range(1, 5):
            snapshot["sim_time"] = 10. + .1 * i
            self.assertFalse(evaluator.evaluate_snapshot(snapshot, order, acceptance_open=True)["success"])
        snapshot["sim_time"] = 10.5
        final = evaluator.evaluate_snapshot(snapshot, order, acceptance_open=True)
        self.assertTrue(final["success"])
        self.assertEqual(final["accepted"], {"tray1": ["A1"]})
        self.assertEqual(final["accepted_count"], 1)

    def test_first_success_retains_exact_sample_and_wall_clock_without_interpolation(self):
        snapshot,order=fixture();evaluator=IndependentEvaluator()
        for i in range(251):
            snapshot['sim_time']=10.+i*.002
            result=evaluator.evaluate_snapshot(snapshot,order,acceptance_open=True,wall_monotonic_s=100.+i*.002)
        first=copy.deepcopy(evaluator.first_success)
        self.assertEqual(first['sim_time_s'],10.5)
        self.assertEqual(first['wall_monotonic_s'],100.5)
        self.assertEqual(first['protected_snapshot']['sim_time'],10.5)
        snapshot['sim_time']=10.6
        evaluator.evaluate_snapshot(snapshot,order,acceptance_open=True,wall_monotonic_s=100.6)
        self.assertEqual(first,evaluator.first_success)
        evaluator.reset();self.assertIsNone(evaluator.first_success)

    def test_transient_before_threshold_cannot_create_a_completion_landmark(self):
        snapshot,order=fixture();evaluator=IndependentEvaluator()
        for i in range(5):
            snapshot['sim_time']=10.+i*.1
            evaluator.evaluate_snapshot(snapshot,order,acceptance_open=True,wall_monotonic_s=100.+i*.1)
        evaluator.invalidate_settling(10.49,'synthetic inter-tick violation')
        snapshot['sim_time']=10.5
        self.assertFalse(evaluator.evaluate_snapshot(snapshot,order,acceptance_open=True,wall_monotonic_s=100.5)['success'])
        self.assertIsNone(evaluator.first_success)

    def test_centre_inside_tray_is_insufficient_when_collision_bounds_protrude(self):
        snapshot, order = fixture()
        move(snapshot["objects"][0], [.29, .3, .02])
        self.assert_failure(snapshot, order, "extra_or_invalid_delivery_occupancy")

    def test_below_rim_applies_to_full_collision_bounds_not_object_centre(self):
        snapshot, order = fixture()
        move(snapshot["objects"][0], [.2, .3, .065])
        self.assertLess(snapshot["objects"][0]["position"][2], .075)  # Old centre-only condition would pass.
        self.assert_failure(snapshot, order, "object_not_resting")

    def test_rotated_box_bounds_use_all_corners(self):
        c, s = math.cos(math.pi / 4), math.sin(math.pi / 4)
        bounds = box_bounds([0., 0., .02], [c, -s, 0., s, c, 0., 0., 0., 1.], [.02, .04, .02])
        self.assertAlmostEqual(bounds["max"][0], .06 / math.sqrt(2))
        self.assertAlmostEqual(bounds["min"][1], -.06 / math.sqrt(2))
        snapshot, order = fixture()
        part = snapshot["objects"][0]
        part["position"] = [.275, .3, .02]
        part["bounds"] = box_bounds(part["position"], [c, -s, 0., s, c, 0., 0., 0., 1.], [.02, .04, .02])
        self.assert_failure(snapshot, order, "quantity_or_qualification_mismatch")

    def test_extra_part_in_an_unrequested_tray_prevents_success(self):
        snapshot, order = fixture()
        snapshot["objects"].append(obj("B2", .7, .3, family="B", cycle_id=2))
        result = self.assert_failure(snapshot, order, "extra_or_invalid_delivery_occupancy")
        self.assertEqual(result["partial"]["extra_delivery_ids"], ["B2"])

    def test_extra_good_part_in_requested_tray_prevents_success(self):
        snapshot, order = fixture()
        snapshot["objects"].append(obj("A2", .25, .3, cycle_id=2))
        result = self.assert_failure(snapshot, order, "extra_or_invalid_delivery_occupancy")
        self.assertEqual(result["accepted_count"], 1)

    def test_unprocessed_part_with_fabricated_pass_summary_is_not_accepted(self):
        snapshot, order = fixture()
        snapshot["objects"][0].update(cycles=0, cycle_history=[])
        self.assert_failure(snapshot, order, "invalid_process_evidence")

    def test_transport_or_candidate_done_declarations_are_irrelevant(self):
        snapshot, order = fixture()
        snapshot["candidate_done"] = True
        snapshot["transport_status"] = "completed"
        move(snapshot["objects"][0], [.7, -.3, .02])
        self.assert_failure(snapshot, order, "quantity_or_qualification_mismatch")

    def test_wrong_recipe_and_wrong_family_do_not_count(self):
        for field, value in (("recipe", "B"), ("family", "B")):
            with self.subTest(field=field):
                snapshot, order = fixture()
                snapshot["objects"][0][field] = value
                self.assert_failure(snapshot, order, "quantity_or_qualification_mismatch")

    def test_inspection_for_another_part_cannot_fulfil_this_part(self):
        snapshot, order = fixture()
        snapshot["objects"][0]["inspection_history"][0]["part_id"] = "other-part"
        self.assert_failure(snapshot, order, "invalid_process_evidence")

    def test_old_cycle_inspection_is_not_current_pass(self):
        snapshot, order = fixture()
        snapshot["objects"][0]["inspection_history"][0]["cycle_id"] = 999
        self.assert_failure(snapshot, order, "quantity_or_qualification_mismatch")

    def test_inspection_before_cycle_completion_does_not_count(self):
        snapshot, order = fixture()
        snapshot["objects"][0]["inspection_history"][0]["observed_at"] = .5
        self.assert_failure(snapshot, order, "quantity_or_qualification_mismatch")

    def test_cycle_counters_cannot_replace_history(self):
        snapshot, order = fixture()
        snapshot["objects"][0]["cycles"] = 4
        self.assert_failure(snapshot, order, "invalid_process_evidence")

    def test_one_part_cannot_fulfil_two_requirements(self):
        snapshot, order = fixture()
        order["requirements"].append(copy.deepcopy(order["requirements"][0]))
        result = self.assert_failure(snapshot, order, "quantity_or_qualification_mismatch")
        self.assertEqual(result["accepted_count"], 1)

    def test_explicit_required_identity_is_respected(self):
        snapshot, order = fixture()
        order["requirements"][0]["part_ids"] = ["A2"]
        self.assert_failure(snapshot, order, "quantity_or_qualification_mismatch")

    def test_one_cycle_identity_cannot_process_two_distinct_parts(self):
        snapshot, order = fixture()
        snapshot["objects"].append(obj("B2", .45, .3, family="B", cycle_id=1))
        order["requirements"].append({"family": "B", "recipe": "B", "tray": "tray2", "count": 1})
        self.assert_failure(snapshot, order, "shared_cycle_identity")

    def test_unfinished_accepted_cycle_cannot_be_a_completion(self):
        snapshot, order = fixture()
        snapshot["objects"][0]["cycle_history"][0]["completed"] = False
        self.assert_failure(snapshot, order, "invalid_process_evidence")

    def test_preserved_failed_first_attempt_does_not_poison_later_valid_completion(self):
        snapshot, order = fixture()
        part = snapshot["objects"][0]
        failed = {"cycle_id": 99, "part_id": "A1", "recipe": "A", "accepted": True, "accepted_at": -2.,
                  "completed": False, "status": "failed", "failed_at": -1.}
        part["cycle_history"].insert(0, failed)
        result, _ = self.settled(snapshot, order)
        self.assertTrue(result["success"], result)

    def test_raw_failed_inspection_can_precede_later_valid_process_and_pass(self):
        snapshot, order = fixture()
        snapshot["objects"][0]["inspection_history"].insert(0, {
            "inspection_id": "raw-failure", "part_id": "A1", "status": "fail", "cycle_id": None, "observed_at": -.1})
        result, _ = self.settled(snapshot, order)
        self.assertTrue(result["success"], result)

    def test_rework_requires_explicit_allowance_and_correlated_authorization(self):
        snapshot, order = fixture()
        part = snapshot["objects"][0]
        part["cycle_history"].append({"cycle_id": 2, "part_id": "A1", "recipe": "A", "accepted": True,
                                      "completed": True, "accepted_at": 3., "completed_at": 4.,
                                      "rework_authorization_inspection_id": "rework-A1"})
        part["inspection_history"] = [
            {"inspection_id": "rework-A1", "part_id": "A1", "status": "rework", "cycle_id": 1, "observed_at": 2.},
            {"inspection_id": "pass-A1", "part_id": "A1", "status": "pass", "cycle_id": 2, "observed_at": 5.},
        ]
        part["cycles"] = 2
        self.assert_failure(copy.deepcopy(snapshot), order, "quantity_or_qualification_mismatch")
        order["requirements"][0]["max_rework_cycles"] = 1
        result, _ = self.settled(copy.deepcopy(snapshot), order)
        self.assertTrue(result["success"], result)
        part["cycle_history"][1].pop("rework_authorization_inspection_id")
        self.assert_failure(snapshot, order, "invalid_process_evidence")

    def test_parking_capacity_is_physical_and_finite(self):
        snapshot, order = fixture()
        snapshot["objects"].extend([obj("A2", .19, 0., cycle_id=2), obj("B3", .22, 0., family="B", cycle_id=3)])
        self.assert_failure(snapshot, order, "parking_capacity")

    def test_fixture_must_be_empty_even_when_workpiece_is_only_partly_inside(self):
        snapshot, order = fixture()
        snapshot["objects"].append(obj("A2", .06, 0., cycle_id=2))
        self.assert_failure(snapshot, order, "fixture_not_empty")

    def test_any_exact_gripper_contact_prevents_terminal_success(self):
        snapshot, order = fixture()
        snapshot["objects"][0]["gripper_contact"] = True
        self.assert_failure(snapshot, order, "gripper_contact")

    def test_angular_motion_matters_even_with_zero_translation(self):
        snapshot, order = fixture()
        snapshot["objects"][0]["angular_velocity"] = [0., 0., .5]
        self.assert_failure(snapshot, order, "object_moving")

    def test_all_arm_and_finger_velocities_are_checked(self):
        snapshot, order = fixture()
        snapshot["arm_velocity"][6] = .03
        self.assert_failure(snapshot, order, "arm_not_settled")
        snapshot, order = fixture()
        snapshot["finger_velocity"][1] = .02
        self.assert_failure(snapshot, order, "gripper_not_settled")

    def test_returnable_insert_cannot_be_left_at_an_arbitrary_location(self):
        snapshot, order = fixture()
        move(snapshot["objects"][2], [.6, -.3, .008])
        self.assert_failure(snapshot, order, "returnable_not_home")

    def test_two_installed_inserts_are_not_a_valid_resting_state(self):
        snapshot, order = fixture()
        move(snapshot["objects"][2], [.025, 0., .008])
        self.assert_failure(snapshot, order, "multiple_installed_inserts")

    def test_returnable_object_in_unrequested_delivery_tray_is_still_extra(self):
        snapshot, order = fixture()
        move(snapshot["objects"][2], [.7, .3, .008])
        self.assert_failure(snapshot, order, "extra_or_invalid_delivery_occupancy")

    def test_pending_and_delayed_operations_all_block_completion(self):
        for field in ("active_request", "queued_motion", "active_segment", "machine_cycle", "inspection"):
            with self.subTest(field=field):
                snapshot, order = fixture()
                snapshot["pending"][field] = True
                self.assert_failure(snapshot, order, "outstanding_work")

    def test_unknown_pending_state_does_not_become_false(self):
        snapshot, order = fixture()
        snapshot["pending"].pop("inspection")
        self.assert_failure(snapshot, order, "pending_state_unknown")

    def test_machine_fault_and_unsafe_terminal_clamp_prevent_success(self):
        snapshot, order = fixture()
        snapshot["station"]["fault"] = True
        self.assert_failure(snapshot, order, "station_not_safely_idle")
        snapshot, order = fixture()
        snapshot["station"]["clamped"] = True
        self.assert_failure(snapshot, order, "station_rest_state")

    def test_closed_order_is_not_enough_before_required_intervention_resolves(self):
        snapshot, order = fixture()
        result, _ = self.settled(snapshot, order, acceptance_open=False)
        self.assertFalse(result["success"])
        self.assertIn("required_opportunities_unresolved", {v["code"] for v in result["violations"]})
        self.assertEqual(result["accepted_count"], 1)  # Correct partial fulfillment remains visible.

    def test_open_order_never_finishes(self):
        snapshot, order = fixture()
        order["closed"] = False
        self.assert_failure(snapshot, order, "order_stream_open")

    def test_amendment_rechecks_current_destination_and_revokes_old_credit(self):
        snapshot, order = fixture()
        result, evaluator = self.settled(snapshot, order)
        self.assertTrue(result["success"])
        order["version"] = 2
        order["requirements"][0]["tray"] = "tray2"
        snapshot["sim_time"] += .1
        amended = evaluator.evaluate_snapshot(snapshot, order, acceptance_open=True)
        self.assertFalse(amended["success"])
        self.assertEqual(amended["accepted_count"], 0)

    def test_settling_gaps_and_detected_between_sample_transients_reset_dwell(self):
        snapshot, order = fixture()
        result, evaluator = self.settled(snapshot, order)
        self.assertTrue(result["success"])
        snapshot["sim_time"] += 1.
        after_gap = evaluator.evaluate_snapshot(snapshot, order, acceptance_open=True)
        self.assertFalse(after_gap["success"])
        self.assertTrue(after_gap["settling"]["sample_gap_reset"])
        evaluator.invalidate_settling(snapshot["sim_time"] + .05, "brief physics-rate gripper contact")
        snapshot["sim_time"] += .1
        after_contact = evaluator.evaluate_snapshot(snapshot, order, acceptance_open=True)
        self.assertFalse(after_contact["success"])
        self.assertEqual(after_contact["settling"]["last_external_invalidation"]["reason"], "brief physics-rate gripper contact")

    def test_time_reversal_is_not_a_candidate_restart(self):
        snapshot, order = fixture()
        _, evaluator = self.settled(snapshot, order)
        snapshot["sim_time"] = 1.
        with self.assertRaises(EvaluationError):
            evaluator.evaluate_snapshot(snapshot, order, acceptance_open=True)

    def test_duplicate_identity_nonfinite_state_and_missing_joint_evidence_fail(self):
        for mutation in ("duplicate", "nan", "joint_missing"):
            with self.subTest(mutation=mutation):
                snapshot, order = fixture()
                if mutation == "duplicate":
                    snapshot["objects"].append(copy.deepcopy(snapshot["objects"][0]))
                elif mutation == "nan":
                    snapshot["objects"][0]["position"][0] = float("nan")
                else:
                    snapshot["arm_velocity"] = [0.]
                with self.assertRaises(EvaluationError):
                    IndependentEvaluator().evaluate_snapshot(snapshot, order, acceptance_open=True)

    def test_configuration_exposes_virtual_rim_and_velocity_assumptions(self):
        snapshot, order = fixture()
        result, _ = self.settled(snapshot, order)
        self.assertEqual(result["calibration_assumptions"]["scoring_rim_z_m"], .08)
        self.assertIn("virtual", result["calibration_assumptions"]["rim_interpretation"])
        self.assertEqual(ScoringConfig().dwell_s, .5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
