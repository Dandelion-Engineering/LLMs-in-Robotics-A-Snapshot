"""Deferred source-only clock/state tests of retained original and proposed files."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent


def module_at(label, path):
    spec = importlib.util.spec_from_file_location(label, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AfterReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
        for item in manifest["files"]:
            for side in ("original", "proposed"):
                path = HERE / item[side + "_path"]
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
                if actual != item[side + "_sha256"]:
                    raise AssertionError("Retained stage identity changed: " + str(path))
        cls.original = module_at("original_opportunity", HERE / "original/Runtime/initial_conditions.py")
        cls.proposed = module_at("proposed_opportunity", HERE / "proposed/Runtime/initial_conditions.py")

    def tracker(self, cut="after_release", module=None, **kwargs):
        module = module or self.proposed
        seed = next(i for i in range(100) if module.RestartOpportunity(i).configuration()["cut"] == cut)
        tracker = module.RestartOpportunity(seed, **kwargs)
        ordinal = tracker.configuration()["transport_ordinal"]
        for prior in range(1, ordinal):
            self.assertIsNone(tracker.observe(0., {"operation": "transport", "request_id": str(prior)},
                                             {"phase": 0}, width=.04))
        request = {"operation": "transport", "request_id": str(ordinal)}
        return tracker, request

    def release_tracker(self, **kwargs):
        tracker, request = self.tracker(**kwargs)
        # Register the selected request without entering its release/open window.
        self.assertIsNone(tracker.observe(0., request, {"phase": 6}, width=.04))
        return tracker, request

    def test_configuration_versions_only_the_public_dwell_without_reselecting_cuts(self):
        for seed in range(40):
            old = self.original.RestartOpportunity(seed).configuration()
            new = self.proposed.RestartOpportunity(seed).configuration()
            self.assertEqual(new.pop("schema_version"), "robot-restart-opportunity-1.2")
            old.pop("schema_version")
            self.assertEqual(new.pop("after_release_open_dwell_s"), .10)
            self.assertEqual(new.pop("after_release_dwell_timebase"), "simulation_elapsed_s")
            self.assertEqual(new, old)

    def test_no_early_cut_and_exact_duration_is_sufficient_once(self):
        tracker, request = self.release_tracker()
        for elapsed in (0., 0., .05, .099999):
            self.assertIsNone(tracker.observe(elapsed, request, {"phase": 7}, width=.065))
        event = tracker.observe(.10, request, {"phase": 7}, width=.065)
        self.assertEqual(event["observed_after_release_open_duration_s"], .10)
        self.assertEqual(event["after_release_open_dwell_s"], .10)
        self.assertEqual(event["actual_cut"], "after_release")
        self.assertTrue(event["configured_milestone_exercised"])
        self.assertFalse(event["fallback_used"])
        self.assertIsNone(tracker.observe(.2, request, {"phase": 7}, width=.08))
        json.dumps(event, allow_nan=False)

    def test_later_sample_reports_actual_duration_not_the_configured_minimum(self):
        tracker, request = self.release_tracker()
        self.assertIsNone(tracker.observe(1., request, {"phase": 7}, width=.08))
        event = tracker.observe(1.137, request, {"phase": 7}, width=.08)
        self.assertAlmostEqual(event["observed_after_release_open_duration_s"], .137)
        self.assertGreaterEqual(event["observed_after_release_open_duration_s"], .10)

    def test_request_operation_phase_or_width_departure_restarts_the_window(self):
        for change in ("other_request", "missing_request", "operation", "phase", "missing_phase", "width"):
            with self.subTest(change=change):
                tracker, request = self.release_tracker()
                self.assertIsNone(tracker.observe(0., request, {"phase": 7}, width=.08))
                other, segment, width = copy.deepcopy(request), {"phase": 7}, .08
                if change == "other_request": other["request_id"] = "different-request"
                elif change == "missing_request": other = None
                elif change == "operation": other["operation"] = "observe"
                elif change == "phase": segment["phase"] = 8
                elif change == "missing_phase": segment = None
                else: width = .064999
                self.assertIsNone(tracker.observe(.06, other, segment, width=width))
                self.assertIsNone(tracker.observe(.11, request, {"phase": 7}, width=.08))
                self.assertIsNone(tracker.observe(.209999, request, {"phase": 7}, width=.08))
                event = tracker.observe(.211, request, {"phase": 7}, width=.08)
                self.assertAlmostEqual(event["observed_after_release_open_duration_s"], .101)

    def test_nonselected_request_time_cannot_supply_selected_request_dwell(self):
        tracker, request = self.release_tracker()
        other = {"operation": "transport", "request_id": "unselected"}
        self.assertIsNone(tracker.observe(.2, other, {"phase": 7}, width=.08))
        self.assertIsNone(tracker.observe(2., other, {"phase": 7}, width=.08))
        self.assertIsNone(tracker.observe(2.01, request, {"phase": 7}, width=.08))
        self.assertIsNone(tracker.observe(2.05, request, {"phase": 7}, width=.08))
        event = tracker.observe(2.12, request, {"phase": 7}, width=.08)
        self.assertAlmostEqual(event["observed_after_release_open_duration_s"], .11)

    def test_monotonic_clock_and_invalid_public_sample_guards_remain(self):
        tracker, request = self.release_tracker()
        tracker.observe(.05, request, {"phase": 7}, width=.08)
        with self.assertRaisesRegex(ValueError, "cannot move backwards"):
            tracker.observe(.04, request, {"phase": 7}, width=.08)
        for elapsed, width in ((float("nan"), .08), (float("inf"), .08), (-1., .08),
                               (.06, float("nan")), (.06, -1.), (True, .08)):
            with self.subTest(elapsed=elapsed, width=width):
                with self.assertRaises(ValueError): tracker.observe(elapsed, request, {"phase": 7}, width=width)

    def test_sixty_second_fallback_does_not_wait_for_release_dwell(self):
        tracker, request = self.release_tracker()
        self.assertEqual(tracker.configuration()["fallback_s"], 60.)
        self.assertIsNone(tracker.observe(59.99, request, {"phase": 7}, width=.08))
        event = tracker.observe(60., request, {"phase": 7}, width=.08)
        self.assertEqual(event["actual_cut"], "deadline_fallback")
        self.assertTrue(event["fallback_used"])
        self.assertFalse(event["configured_milestone_exercised"])
        self.assertLess(event["observed_after_release_open_duration_s"], .10)
        tracker, request = self.release_tracker()
        event = tracker.observe(60., None, None, width=.08)
        self.assertTrue(event["fallback_used"])
        self.assertEqual(event["observed_after_release_open_duration_s"], 0.)

    def test_matured_release_wins_over_fallback_and_disabled_counterpart_stays_off(self):
        tracker, request = self.release_tracker()
        self.assertIsNone(tracker.observe(59.8, request, {"phase": 7}, width=.08))
        event = tracker.observe(60., request, {"phase": 7}, width=.08)
        self.assertFalse(event["fallback_used"])
        tracker, request = self.release_tracker(enabled=False)
        self.assertIsNone(tracker.observe(0., request, {"phase": 7}, width=.08))
        self.assertIsNone(tracker.observe(100., request, {"phase": 7}, width=.08))

    def test_after_release_does_not_use_tcp_or_hidden_object_facts(self):
        for height in (None, .01, float("nan")):
            with self.subTest(height=height):
                tracker, request = self.release_tracker()
                request.update(hidden_pose="unsupported", contact_force=None, angular_velocity=999.)
                self.assertIsNone(tracker.observe(0., request, {"phase": 7}, width=.08, tcp_z=height))
                event = tracker.observe(.10, request, {"phase": 7}, width=.08, tcp_z=height)
                self.assertTrue(event["configured_milestone_exercised"])
                self.assertNotIn("recovered", event)
                self.assertNotIn("admissible", event)

    def test_other_three_cut_families_retain_original_trigger_and_exposure(self):
        fields = {"after_release_open_dwell_s", "after_release_dwell_timebase",
                  "observed_after_release_open_duration_s"}
        for cut, segment, width, height in (("after_acceptance", None, .08, None),
                ("closed_grip_transfer", {"phase": 5}, .042, .08),
                ("before_outcome", {"phase": 9}, .08, None)):
            with self.subTest(cut=cut):
                old, old_request = self.tracker(cut, self.original)
                new, request = self.tracker(cut)
                old_event = old.observe(1., old_request, segment, width=width, tcp_z=height)
                new_event = new.observe(1., request, segment, width=width, tcp_z=height)
                self.assertEqual({k: v for k, v in new_event.items() if k not in fields}, old_event)
                self.assertIsNone(new_event["observed_after_release_open_duration_s"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
