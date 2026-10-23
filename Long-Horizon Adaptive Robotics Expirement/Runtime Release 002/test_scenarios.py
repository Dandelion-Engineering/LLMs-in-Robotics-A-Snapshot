"""Synthetic scenario/order-service checks; no physics or scored runs.

Seed integers here are explicit unit fixtures, not generated held-out manifests.
"""
import copy
import hashlib
import json
import random
import unittest

from scenarios import ScenarioError, ScenarioService, derive_event_seed, initial_order, public_rules


def cycles(part_ids):
    return [{"cycle_id": i + 1, "part_id": name, "recipe": name[0], "accepted": True, "completed": True,
             "accepted_at": i * 8., "completed_at": i * 8. + 8.} for i, name in enumerate(part_ids)]


def requirement(order, item_id):
    return next(row for row in order["requirements"] if row["order_item_id"] == item_id)


class ScenarioUnitChecks(unittest.TestCase):
    def assert_text_matches(self, order):
        self.assertIn("Order version " + str(order["version"]) + ".", order["text"])
        for row in order["requirements"]:
            count, family, recipe, tray = (row[k] for k in ("count", "family", "recipe", "tray"))
            noun = "part" if count == 1 else "parts"
            self.assertIn(f"{count} distinct {family} {noun} using recipe {recipe}; deliver them to {tray}.", order["text"])
            self.assertEqual(row["max_rework_cycles"], 1)
        self.assertIn("The order stream is closed." if order["closed"] else "The order stream remains open;", order["text"])

    def test_short_and_standard_initial_counts_match_existing_jobs(self):
        for n, counts in ((3, (2, 1)), (6, (3, 3))):
            for scenario in ("nominal", "restart", "order_change", "mixed"):
                with self.subTest(n=n, scenario=scenario):
                    order = initial_order(n, scenario)
                    self.assertEqual([r["count"] for r in order["requirements"]], list(counts))
                    self.assertEqual([r["tray"] for r in order["requirements"]], ["tray1", "tray2"])
                    self.assertEqual(order["closed"], scenario in ("nominal", "restart"))
                    self.assert_text_matches(order)

    def test_extended_initial_order_is_seven_parts_then_three_later(self):
        service = ScenarioService(10)
        order = service.initial_order()
        self.assertEqual(sum(r["count"] for r in order["requirements"]), 7)
        self.assertEqual(requirement(order, "initial-A")["count"], 2)
        self.assertEqual(requirement(order, "initial-B")["count"], 5)
        self.assertFalse(order["closed"])
        config = service.private_config()
        self.assertEqual(len(config["stock"]), 10)
        self.assertEqual(list(config["stock"].values()).count("A"), 5)
        self.assertEqual(list(config["stock"].values()).count("B"), 5)
        self.assert_text_matches(order)

    def test_exact_forty_second_reroute_and_text_update(self):
        service = ScenarioService(6, "order_change")
        before = service.advance(39.999, [])
        self.assertFalse(before["changed"])
        self.assertFalse(before["order"]["closed"])
        after = service.advance(40., [])
        self.assertTrue(after["changed"])
        self.assertTrue(after["order"]["closed"])
        self.assertEqual(after["order"]["version"], 2)
        self.assertEqual(requirement(after["order"], "initial-B")["tray"], "tray3")
        self.assertEqual(after["exposures"][0]["delivery_delay_s"], 0.)
        self.assert_text_matches(after["order"])

    def test_reroute_delivery_delay_is_recorded_without_backdating_event(self):
        service = ScenarioService(3, "mixed")
        result = service.advance(42.5, [])
        self.assertEqual(result["events"][0]["sim_elapsed_s"], 42.5)
        self.assertEqual(result["exposures"][0]["scheduled_elapsed_s"], 40.)
        self.assertEqual(result["exposures"][0]["delivery_delay_s"], 2.5)

    def test_five_distinct_completed_B_parts_release_later_A(self):
        service = ScenarioService(10, "nominal")
        four = cycles(["B2", "B4", "B6", "B8"])
        self.assertFalse(service.advance(100., four)["changed"])
        after = service.advance(110., cycles(["B10"]))
        self.assertTrue(after["changed"])
        self.assertTrue(after["order_events_resolved"])
        self.assertTrue(after["order"]["closed"])
        self.assertEqual(sum(r["count"] for r in after["order"]["requirements"]), 10)
        late = requirement(after["order"], "late-A")
        self.assertEqual((late["family"], late["count"], late["tray"]), ("A", 3, "tray3"))
        self.assertFalse(after["exposures"][0]["fallback_used"])
        self.assertEqual(after["exposures"][0]["distinct_completed_B_count"], 5)
        self.assert_text_matches(after["order"])

    def test_duplicate_rework_cycles_do_not_count_as_distinct_B_parts(self):
        service = ScenarioService(10)
        records = cycles(["B2"] * 12 + ["B4", "B6", "B8"])
        result = service.advance(419.9, records)
        self.assertFalse(result["changed"])
        self.assertEqual(len(service._completed_b), 4)
        after = service.advance(420., records)
        self.assertTrue(after["exposures"][0]["fallback_used"])
        self.assertEqual(after["exposures"][0]["distinct_completed_B_count"], 4)

    def test_unaccepted_and_unfinished_cycles_do_not_trigger_milestone(self):
        service = ScenarioService(10)
        records = cycles(["B2", "B4", "B6", "B8", "B10"])
        records[0]["accepted"] = False
        records[1]["completed"] = False
        self.assertFalse(service.advance(200., records)["changed"])
        self.assertEqual(len(service._completed_b), 3)

    def test_fallback_releases_even_without_candidate_progress(self):
        service = ScenarioService(10)
        self.assertFalse(service.advance(419.999, [])["changed"])
        result = service.advance(420., [])
        self.assertEqual(result["exposures"][0]["trigger"], "fixed_deadline_fallback")
        self.assertFalse(result["exposures"][0]["milestone_satisfied"])
        self.assertTrue(result["order"]["closed"])
        self.assertEqual(result["exposures"][0]["delivery_delay_after_fallback_s"], 0.)

    def test_late_first_poll_records_fallback_instead_of_inventing_earlier_milestone(self):
        service = ScenarioService(10)
        result = service.advance(430., cycles(["B2", "B4", "B6", "B8", "B10"]))
        exposure = result["exposures"][0]
        self.assertTrue(exposure["fallback_used"])
        self.assertTrue(exposure["milestone_satisfied"])
        self.assertEqual(exposure["milestone_first_observed_at_s"], 430.)
        self.assertEqual(exposure["delivery_delay_after_fallback_s"], 10.)

    def test_extended_mixed_closes_only_after_both_order_events(self):
        service = ScenarioService(10, "mixed")
        rerouted = service.advance(40., [])
        self.assertEqual(rerouted["order"]["version"], 2)
        self.assertFalse(rerouted["order"]["closed"])
        self.assertFalse(rerouted["order_events_resolved"])
        released = service.advance(110., cycles(["B2", "B4", "B6", "B8", "B10"]))
        self.assertEqual(released["order"]["version"], 3)
        self.assertTrue(released["order"]["closed"])
        self.assertEqual(requirement(released["order"], "initial-B")["tray"], "tray3")
        self.assertEqual(requirement(released["order"], "late-A")["tray"], "tray2")
        self.assert_text_matches(released["order"])

    def test_early_late_A_does_not_force_sequence_and_later_reroute_stays_consistent(self):
        service = ScenarioService(10, "mixed")
        early = service.advance(20., cycles(["B2", "B4", "B6", "B8", "B10"]))
        self.assertEqual(requirement(early["order"], "late-A")["tray"], "tray3")
        self.assertFalse(early["order"]["closed"])
        amended = service.advance(40., [])
        self.assertTrue(amended["order"]["closed"])
        self.assertEqual(requirement(amended["order"], "initial-B")["tray"], "tray3")
        self.assertEqual(requirement(amended["order"], "late-A")["tray"], "tray2")
        self.assert_text_matches(amended["order"])

    def test_simultaneously_due_events_have_separate_versions_and_public_text(self):
        service = ScenarioService(10, "mixed")
        result = service.advance(420., [])
        self.assertEqual(len(result["events"]), 2)
        self.assertEqual([e["order_version"] for e in result["events"]], [2, 3])
        self.assertFalse(result["events"][0]["order"]["closed"])
        self.assertTrue(result["events"][1]["order"]["closed"])
        for event in result["events"]:
            self.assert_text_matches(event["order"])

    def test_repeated_advance_never_duplicates_an_order_release(self):
        service = ScenarioService(10, "mixed")
        service.advance(420., [])
        for elapsed in (420., 500., 900.):
            result = service.advance(elapsed, cycles(["B2", "B4", "B6", "B8", "B10"]))
            self.assertFalse(result["changed"])
            self.assertEqual(result["events"], [])
            self.assertEqual(result["exposures"], [])
            self.assertEqual(result["order"]["version"], 3)
        self.assertEqual(len(service.protected_history()), 2)

    def test_public_payload_has_no_seed_stock_or_private_rework_target(self):
        service = ScenarioService(10, "mixed", event_seed=123456)
        public = [service.initial_order(), service.advance(420., [])["events"], service.order]
        serialized = json.dumps(public)
        for secret_key in ("event_seed", "rework_part_id", "stock", "distinct_completed_B_ids"):
            self.assertNotIn(secret_key, serialized)
        self.assertNotIn("123456", serialized)
        self.assertIn("event_seed", service.private_config())
        self.assertEqual(service.private_config()["audience"], "evaluator/operator only")

    def test_private_rework_selection_is_seeded_repeatable_and_confined_to_A_stock(self):
        chosen = set()
        for seed in range(20):
            a = ScenarioService(10, event_seed=seed).private_config()
            b = ScenarioService(10, event_seed=seed).private_config()
            self.assertEqual(a, b)
            self.assertEqual(a["stock"][a["rework_part_id"]], "A")
            self.assertTrue(a["rework_once"])
            chosen.add(a["rework_part_id"])
        self.assertGreater(len(chosen), 1)
        self.assertIsNone(ScenarioService(3).private_config()["rework_part_id"])

    def test_supplied_event_seed_does_not_modify_global_random_state(self):
        random.seed(77)
        before = random.getstate()
        ScenarioService(10, event_seed=12)
        self.assertEqual(before, random.getstate())
        self.assertEqual(derive_event_seed(42), derive_event_seed(42))
        self.assertNotEqual(derive_event_seed(42), derive_event_seed(43))

    def test_explicit_frozen_parameter_override_is_recorded_privately(self):
        service = ScenarioService(10, "mixed", event_seed=17,
                                  event_params={"reroute_time_s": 45., "late_release_fallback_s": 410., "rework_part_id": "A1"})
        self.assertFalse(service.advance(40., [])["changed"])
        self.assertEqual(service.advance(45., [])["exposures"][0]["scheduled_elapsed_s"], 45.)
        self.assertTrue(service.advance(410., [])["exposures"][0]["fallback_used"])
        self.assertEqual(service.private_config()["rework_part_id"], "A1")

    def test_actual_cell_style_registry_excludes_inserts_and_truth_mapping_is_supported(self):
        registry = {f'{"A" if i % 2 == 0 else "B"}{i + 1}': {"kind": "part", "family": "A" if i % 2 == 0 else "B"}
                    for i in range(10)}
        registry.update({"insert_A": {"kind": "insert", "family": "A"}, "insert_B": {"kind": "insert", "family": "B"}})
        service = ScenarioService(10, stock_ids=registry)
        truth = {record["part_id"]: {"cycle_history": [record]} for record in cycles(["B2", "B4", "B6", "B8", "B10"])}
        result = service.advance(120., truth)
        self.assertTrue(result["changed"])
        self.assertEqual(len(service.private_config()["stock"]), 10)

    def test_malformed_or_wrong_stock_fails_before_fake_progress(self):
        for stock in (["A1"] * 10, ["A" + str(i) for i in range(10)], ["A1", "B2"],
                      [{"id": [], "family": "A"}] * 10):
            with self.subTest(stock=str(stock)[:20]):
                with self.assertRaises(ScenarioError):
                    ScenarioService(10, stock_ids=stock)
        service = ScenarioService(10)
        malformed = cycles(["B2", "B4"])
        malformed.append({"part_id": "B999", "recipe": "B", "accepted": True, "completed": True})
        with self.assertRaises(ScenarioError):
            service.advance(100., malformed)
        self.assertEqual(service._completed_b, set())
        self.assertIsNone(service._last_elapsed)

    def test_scalar_cycle_count_and_wrong_recipe_are_not_distinct_completion_evidence(self):
        service = ScenarioService(10)
        with self.assertRaises(ScenarioError):
            service.advance(100., 5)
        records = cycles(["B2"])
        records[0]["recipe"] = "A"
        with self.assertRaises(ScenarioError):
            service.advance(100., records)

    def test_time_cannot_reset_with_candidate_restart(self):
        service = ScenarioService(10, "mixed")
        service.advance(50., [])
        with self.assertRaises(ScenarioError):
            service.advance(0., [])
        self.assertEqual(service.order["version"], 2)

    def test_returned_records_cannot_mutate_supervisor_state(self):
        service = ScenarioService(10, "mixed")
        public = service.initial_order()
        public["requirements"][0]["count"] = 99
        private = service.private_config()
        private["stock"].clear()
        result = service.advance(420., [])
        result["order"]["requirements"][0]["count"] = 99
        result["events"][0]["order"]["version"] = 99
        result["exposures"][0]["fallback_used"] = True
        self.assertEqual(service.order["requirements"][0]["count"], 2)
        self.assertEqual(service.initial_order()["version"], 1)
        self.assertEqual(service.public_history()[0]["order"]["version"], 2)
        self.assertFalse(service.protected_history()[0]["fallback_used"])
        self.assertEqual(len(service.private_config()["stock"]), 10)

    def test_restart_opportunity_is_not_claimed_resolved_by_closed_order(self):
        service = ScenarioService(3, "restart")
        result = service.advance(0., [])
        self.assertTrue(result["order"]["closed"])
        self.assertTrue(result["order_events_resolved"])
        self.assertIn("restart/intervention", result["acceptance_limit"])
        self.assertNotIn("restart_exercised", result)

    def test_public_rules_hash_and_exposure_hash_are_reproducible(self):
        service = ScenarioService(10)
        expected = hashlib.sha256(json.dumps(public_rules(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        self.assertEqual(service.private_config()["public_rules_sha256"], expected)
        update = service.advance(420., [])
        actual_order_hash = hashlib.sha256(json.dumps(update["order"], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        self.assertEqual(update["exposures"][0]["order_sha256"], actual_order_hash)
        self.assertIn("not a guaranteed", public_rules()["sequence_limit"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
