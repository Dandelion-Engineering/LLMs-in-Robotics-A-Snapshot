"""Proposed common adapter checks using synthetic public packets, not physics."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from candidates import Candidate, MAX_AGE_S, MAX_RECENT_RESOLUTIONS
from test_candidates import PacketFixture

KINDS = ("baseline", "A1", "A2", "A3")


class LoopFixChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def candidate(self, kind="A1", name=None, persistent=True):
        return Candidate(kind, self.root / (name or kind), persistent)

    def fresh_packet(self, fixture):
        packet = fixture.next()
        packet["capture_sim_time_s"] = packet["sim_time"] - .1
        return packet

    def resolve_setup(self, candidate, fixture, family):
        candidate._ingest(self.fresh_packet(fixture))
        action = {"operation": "setup", "family": family}
        self.assertIsNone(candidate._validate(action))
        issued = candidate._issue(action)["action"]
        feedback = fixture.apply_symbolic(issued)
        feedback["reason"] = "synthetic public setup receipt"
        candidate.accept_feedback(feedback)
        candidate._ingest(self.fresh_packet(fixture))
        candidate._reconcile()
        candidate._persist()
        self.assertIsNone(candidate.state["pending"])
        return issued

    def test_same_fresh_noop_guard_for_every_kind_without_selecting_next_action(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                candidate = self.candidate(kind)
                candidate._ingest(self.fresh_packet(PacketFixture(3)))
                candidate.state["fixture_belief"] = {"family": "B", "sim_time": -100.}
                self.assertIn("already freshly observed", candidate._validate({"operation": "setup", "family": "A"}))
                self.assertIsNone(candidate._validate({"operation": "setup", "family": "B"}))
                menu = candidate._admissible_actions()
                self.assertNotIn({"operation": "setup", "family": "A"}, menu)
                self.assertIn({"operation": "setup", "family": "B"}, menu)
                self.assertEqual({a["part_id"] for a in menu if a["operation"] == "transport" and a["destination"] == "fixture"}, {"A0", "A1", "A2"})
                self.assertIn({"operation": "wait"}, menu)
                self.assertIsNone(candidate.state["pending"])

    def test_unknown_capture_or_old_retained_belief_does_not_block_setup(self):
        for kind in KINDS:
            candidate = self.candidate(kind)
            fixture = PacketFixture(1)
            for observed, age in ((None, .1), ("A", MAX_AGE_S + .1), ("A", None), ("A", -.1)):
                with self.subTest(kind=kind, observed=observed, age=age):
                    packet = fixture.next()
                    packet["station"]["fixture_insert"] = observed
                    if age is not None: packet["capture_sim_time_s"] = packet["sim_time"] - age
                    candidate._ingest(packet)
                    candidate.state["fixture_belief"] = {"family": "A", "sim_time": -100.}
                    self.assertIsNone(candidate._validate({"operation": "setup", "family": "A"}))

    def test_a2_accepts_future_setup_syntax_then_revalidates_at_dispatch(self):
        candidate = self.candidate("A2")
        fixture = PacketFixture(1)
        self.assertEqual(candidate.step(self.fresh_packet(fixture))["type"], "model")
        candidate.accept_model(json.dumps({"steps": [
            {"guards": [{"predicate": "station_idle"}], "action": {"operation": "setup", "family": "B"}},
            {"guards": [{"predicate": "station_idle"}], "action": {"operation": "setup", "family": "A"}},
        ]}))
        self.assertEqual(len(candidate.state["program"]["steps"]), 2)
        first = candidate.step(self.fresh_packet(fixture))["action"]
        self.assertEqual(first["family"], "B")
        candidate.accept_feedback(fixture.apply_symbolic(first))
        second = candidate.step(self.fresh_packet(fixture))
        self.assertEqual(second["type"], "action")
        self.assertEqual(second["action"]["family"], "A")
        self.assertEqual(candidate.state["program"]["completed"], [0])

    def test_a2_known_noop_node_waits_and_can_become_eligible_later(self):
        candidate = self.candidate("A2")
        fixture = PacketFixture(1)
        candidate.step(self.fresh_packet(fixture))
        candidate.accept_model(json.dumps({"steps": [{"guards": [], "action": {"operation": "setup", "family": "A"}}]}))
        first = candidate.step(self.fresh_packet(fixture))
        self.assertEqual(first["action"]["operation"], "observe")
        self.assertIsNone(candidate.state["pending"])
        fixture.packet["station"]["fixture_insert"] = "B"
        second = candidate.step(self.fresh_packet(fixture))
        self.assertEqual(second["action"]["operation"], "setup")
        self.assertEqual(second["action"]["family"], "A")

    def test_a1_noop_output_is_rejected_without_scheduler_fallback(self):
        candidate = self.candidate("A1")
        fixture = PacketFixture(1)
        candidate.step(self.fresh_packet(fixture))
        candidate.accept_model(json.dumps({"action": {"operation": "setup", "family": "A"}}))
        reply = candidate.step(self.fresh_packet(fixture))
        self.assertEqual(reply["type"], "model")
        self.assertIsNone(candidate.state["pending"])
        self.assertIn("already freshly observed", candidate.state["last_error"])

    def test_eight_resolutions_are_durable_public_claims_in_all_contexts(self):
        self.assertEqual(MAX_RECENT_RESOLUTIONS, 8)
        for kind in KINDS:
            with self.subTest(kind=kind):
                candidate = self.candidate(kind)
                fixture = PacketFixture(1)
                actions = [self.resolve_setup(candidate, fixture, "B" if i % 2 == 0 else "A") for i in range(10)]
                rows = candidate.state["recent_resolutions"]
                self.assertEqual([r["request_id"] for r in rows], [a["request_id"] for a in actions[-8:]])
                self.assertTrue(all(r["grading_authority"] is False for r in rows))
                self.assertTrue(all(r["candidate_resolved"] is True for r in rows))
                self.assertEqual(rows[-1]["public_feedback"]["reason"], "synthetic public setup receipt")
                self.assertEqual(rows[-1]["action"]["order_version"], 1)
                self.assertEqual(rows[-1]["resolution_incarnation"], "inc1")
                self.assertNotIn("physical_success", rows[-1])
                restarted = self.candidate(kind)
                self.assertEqual(restarted.state["recent_resolutions"], rows)
                restarted._ingest(self.fresh_packet(fixture))
                context = restarted._context()
                self.assertEqual(context["recent_resolutions"], rows)
                context["recent_resolutions"].clear()
                self.assertEqual(len(restarted.state["recent_resolutions"]), 8)

    def test_receipt_without_physical_reconciliation_adds_no_success(self):
        candidate = self.candidate("baseline")
        fixture = PacketFixture(1)
        action = candidate.step(self.fresh_packet(fixture))["action"]
        candidate.accept_feedback({"request_id": action["request_id"], "status": "completed"})
        candidate.step(self.fresh_packet(fixture))
        self.assertIsNotNone(candidate.state["pending"])
        self.assertEqual(candidate.state["recent_resolutions"], [])

    def test_failed_resolution_retained_and_duplicate_feedback_does_not_duplicate_history(self):
        candidate = self.candidate("baseline")
        fixture = PacketFixture(1)
        action = candidate.step(self.fresh_packet(fixture))["action"]
        receipt = {"request_id": action["request_id"], "status": "failed", "reason": "synthetic failure"}
        candidate.accept_feedback(receipt)
        candidate._ingest(self.fresh_packet(fixture)); candidate._reconcile(); candidate._persist()
        self.assertEqual(len(candidate.state["recent_resolutions"]), 1)
        row = candidate.state["recent_resolutions"][0]
        self.assertFalse(row["candidate_resolved"])
        self.assertFalse(row["grading_authority"])
        candidate.accept_feedback(receipt); candidate._reconcile()
        self.assertEqual(candidate.state["recent_resolutions"], [row])

    def test_no_persistence_keeps_live_history_but_fresh_restart_namespace_has_none(self):
        fixture = PacketFixture(1)
        candidate = self.candidate("A1", "ephemeral-before", persistent=False)
        self.resolve_setup(candidate, fixture, "B")
        self.assertEqual(len(candidate._context()["recent_resolutions"]), 1)
        # The supervisor replaces the private namespace at a no-persistence cut.
        # A separate empty directory models that boundary; the public packet survives.
        replacement = self.candidate("A1", "ephemeral-after", persistent=False)
        fixture.packet["incarnation"] = "inc2"
        replacement._ingest(self.fresh_packet(fixture))
        self.assertEqual(replacement._context()["recent_resolutions"], [])
        self.assertEqual(replacement._station()["fixture_insert"], "B")
        replacement._persist()
        self.assertEqual(self.candidate("A1", "ephemeral-before", persistent=False).state["recent_resolutions"], candidate.state["recent_resolutions"])


if __name__ == "__main__":
    unittest.main()
