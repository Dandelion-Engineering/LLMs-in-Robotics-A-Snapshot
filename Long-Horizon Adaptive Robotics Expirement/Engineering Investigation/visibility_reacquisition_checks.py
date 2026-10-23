"""Public-packet tests of unapplied proposal; no physics or evidence processing."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from propose_visibility_reacquisition import BASE_SHA256, SOURCE, load_proposal

POLICY = load_proposal()


def packet(sequence=100, *, mark="unknown", present=True):
    return {"run_id": "synthetic-visibility", "incarnation": "initial", "sequence": sequence,
        "sim_time": sequence / 10, "capture_sim_time_s": sequence / 10,
        "order": {"version": 1, "closed": True, "requirements": [
            {"family": "B", "recipe": "recipeB", "count": 1, "tray": "tray2"}]},
        "detections": [{"id": "public-part", "family": "B", "pos": [.4, -.2, .03],
            "zone": "raw", "visible_mark": mark, "age_s": 0.}] if present else [],
        "station": {"busy": False, "ready": True, "fault": False, "fixture_insert": "B",
            "occupied_visible_id": None, "cycle_id": 0, "completed_cycle_id": 0},
        "gripper": {"holding_visible_id": None, "width": .08},
        "inspection": None, "last_feedback": None}


def operation(reply):
    return reply.get("action", {}).get("operation", reply["type"])


class VisibilityProposalTests(unittest.TestCase):
    def setUp(self):
        for mock in (patch.object(Path, "mkdir", return_value=None),
                     patch.object(Path, "exists", return_value=False),
                     patch.object(POLICY.Candidate, "_persist", return_value=None)):
            mock.start()
            self.addCleanup(mock.stop)

    def candidate(self, kind="baseline"):
        return POLICY.Candidate(kind, Path("synthetic-no-write"), True)

    def first_help(self, candidate, start=100):
        replies = [candidate.step(packet(i, present=False)) for i in range(start, start + 5)]
        self.assertEqual([operation(r) for r in replies], ["observe"] * 4 + ["help"])
        return replies[-1]["action"]

    def test_repeated_frame_does_not_spend_capture_budget(self):
        c = self.candidate()
        self.assertEqual(operation(c.step(packet())), "observe")
        for i in range(12):
            repeated = packet()
            repeated["sim_time"] += i / 10
            repeated["detections"][0]["age_s"] = i / 10
            self.assertEqual(operation(c.step(repeated)), "wait")
        self.assertEqual(c.state["visibility_reacquisition"]["captures"], 0)
        self.assertFalse(c.state["halted"])
        self.assertEqual(operation(c.step(packet(113, mark="raw"))), "transport")

    def test_only_delivered_distinct_fresh_capture_counts(self):
        c = self.candidate()
        c.step(packet())
        for p in (packet(), packet(99), packet(101), packet(102), packet(103)):
            if p["sequence"] == 101:
                p["capture_sim_time_s"] = p["sim_time"] - 2
            if p["sequence"] == 102:
                p.pop("capture_sim_time_s")
            if p["sequence"] == 103:
                p["capture_sim_time_s"] = 10.  # new sequence with same capture time
            self.assertEqual(operation(c.step(p)), "wait")
        self.assertEqual(c.state["visibility_reacquisition"]["captures"], 0)
        self.assertEqual(operation(c.step(packet(104))), "observe")
        self.assertEqual(c.state["visibility_reacquisition"]["captures"], 1)

    def test_machine_waits_do_not_spend_future_visibility_budget(self):
        c = self.candidate()
        for i in range(100, 112):
            p = packet(i)
            p["station"]["busy"] = True
            self.assertEqual(operation(c.step(p)), "wait")
        self.assertNotIn("visibility_reacquisition", c.state)
        self.assertEqual(operation(c.step(packet(112))), "observe")

    def test_one_correlated_assisted_round_then_no_repeated_help(self):
        c = self.candidate()
        help_action = self.first_help(c)
        answer = {"answer_id": "answer-one", "request_id": help_action["request_id"]}
        replies = []
        for i in range(105, 130):
            p = packet(i, present=False)
            p["human_answers"] = [answer]
            replies.append(c.step(p))
        self.assertEqual([operation(r) for r in replies[:5]], ["observe"] * 4 + ["wait"])
        self.assertTrue(all(operation(r) == "wait" for r in replies[4:]))
        events = c.drain_events()
        self.assertEqual(sum(e["type"] == "action_intent" and e["action"]["operation"] == "help" for e in events), 1)
        self.assertEqual(sum(e["type"] == "public_human_answer_received" for e in events), 1)
        self.assertTrue(c.state["halted"])
        self.assertTrue(c.state["visibility_reacquisition"]["assisted"])
        self.assertIsNone(c.state["pending"])
        # Even a different duplicate answer ID for that request cannot re-arm.
        p = packet(130, present=False)
        p["human_answers"] = [{**answer, "answer_id": "answer-duplicate-content"}]
        self.assertEqual(operation(c.step(p)), "wait")
        self.assertEqual(c.state["visibility_reacquisition"]["captures"], 4)

    def test_unrelated_answer_does_not_rearm_visibility(self):
        c = self.candidate()
        self.first_help(c)
        p = packet(105, present=False)
        p["human_answers"] = [{"answer_id": "other", "request_id": "another-request"}]
        self.assertEqual(operation(c.step(p)), "wait")
        self.assertFalse(c.state["visibility_reacquisition"]["assisted"])

    def test_fresh_supported_action_can_resume_visibility_pause(self):
        c = self.candidate()
        self.first_help(c)
        stale = packet(105, mark="raw")
        stale["capture_sim_time_s"] -= 2
        self.assertEqual(operation(c.step(stale)), "wait")
        action = c.step(packet(106, mark="raw"))["action"]
        self.assertEqual((action["operation"], action["part_id"], action["destination"]),
                         ("transport", "public-part", "fixture"))
        self.assertFalse(c.state["halted"])

    def test_a3_resume_preserves_model_objective_step(self):
        c = self.candidate("A3")
        self.first_help(c)
        result = c.step(packet(105, mark="raw"))
        self.assertEqual(result["type"], "model")
        self.assertIsNone(c.state["pending"])

    def test_a1_a2_keep_model_choice_and_no_visibility_fallback(self):
        for kind in ("A1", "A2"):
            c = self.candidate(kind)
            self.assertEqual(c.step(packet(present=False))["type"], "model")
            self.assertNotIn("visibility_reacquisition", c.state)

    def test_pending_recovery_and_nonvisibility_halts_are_not_cleared(self):
        for blocked in ("pending", "recovery_blocked", "recovery_pending", "other_help"):
            with self.subTest(blocked=blocked):
                c = self.candidate()
                self.first_help(c)
                if blocked == "pending":
                    c._issue({"operation": "transport", "part_id": "public-part", "destination": "fixture"})
                    c.state["pending"]["unresolved_timeout"] = True
                elif blocked == "recovery_blocked":
                    c.state[blocked] = True
                elif blocked == "recovery_pending":
                    c.state[blocked] = {"request_id": "unknown-recovery", "issued_time": 10., "feedback": None}
                else:
                    c._issue({"operation": "help", "reason": "unresolved process provenance"})
                self.assertEqual(operation(c.step(packet(105, mark="raw"))), "wait")
                self.assertTrue(c.state["halted"])

    def test_model_failure_and_physical_failure_limits_still_block(self):
        c = self.candidate()
        self.first_help(c)
        c.state["model_failures"] = POLICY.MAX_MODEL_FAILURES
        result = c.step(packet(105, mark="raw"))
        self.assertEqual(operation(result), "help")
        self.assertIn("model failed", result["action"]["reason"])
        self.assertFalse(c.state["visibility_reacquisition"]["paused"])
        c = self.candidate()
        self.first_help(c)
        proposed = {"operation": "transport", "part_id": "public-part", "destination": "fixture"}
        c.state["failure_counts"][c._action_signature(proposed)] = POLICY.MAX_FAILURES
        self.assertEqual(operation(c.step(packet(105, mark="raw"))), "wait")
        self.assertTrue(c.state["halted"])

    def test_public_success_rearms_but_receipt_alone_does_not(self):
        c = self.candidate()
        self.first_help(c)
        action = c.step(packet(105, mark="raw"))["action"]
        c.accept_feedback({"request_id": action["request_id"], "status": "completed"})
        self.assertEqual(operation(c.step(packet(106, mark="raw"))), "wait")
        self.assertIsNotNone(c.state["pending"])
        self.assertIn("visibility_reacquisition", c.state)
        p = packet(107, mark="raw")
        p["detections"][0]["zone"] = "fixture"
        p["station"]["occupied_visible_id"] = "public-part"
        c._ingest(p)
        c._reconcile()
        self.assertIsNone(c.state["pending"])
        self.assertNotIn("visibility_reacquisition", c.state)

    def test_persisted_episode_does_not_rearm_on_incarnation_change(self):
        c = self.candidate()
        first = self.first_help(c)
        restored = self.candidate()
        restored.state = json.loads(json.dumps(c.state))
        p = packet(1, present=False)
        p["incarnation"] = "restarted"
        self.assertEqual(operation(restored.step(p)), "wait")
        self.assertEqual(restored.state["visibility_reacquisition"]["help_request_id"], first["request_id"])

    def test_order_amendment_uses_normal_scheduler_and_wait_does_not_rearm(self):
        c = self.candidate()
        self.first_help(c)
        p = packet(105, present=False)
        p["order"]["version"] = 2
        self.assertEqual(operation(c.step(p)), "wait")
        self.assertTrue(c.state["visibility_reacquisition"]["help_request_id"])
        p = packet(106, mark="raw")
        p["order"]["version"] = 2
        result = c.step(p)
        self.assertEqual(operation(result), "transport")
        self.assertEqual(result["action"]["order_version"], 2)

    def test_runtime_source_remains_exact(self):
        self.assertEqual(hashlib.sha256(SOURCE.read_bytes()).hexdigest(), BASE_SHA256)


if __name__ == "__main__":
    if "--with-existing" in sys.argv:
        sys.path.insert(0, str(SOURCE.parent))
        sys.modules["candidates"] = POLICY
        tempfile.tempdir = str(Path(__file__).resolve().parent)
        suite = unittest.TestSuite([
            unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]),
            unittest.defaultTestLoader.loadTestsFromName("test_candidates"),
            unittest.defaultTestLoader.loadTestsFromName("test_candidate_loop_fix"),
        ])
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        sys.exit(not result.wasSuccessful())
    unittest.main()
