"""Synthetic scheduling regression with the original supervisor and journal.

No physical Cell, model, archived run, or modified baseline policy is used.
The decision stub represents an already observed transport effect and the
next inspection intent; real supervisor admission and feedback remain intact.
"""
from contextlib import nullcontext
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("admission_order_run_host", HERE / "run_host.py")
run_host = importlib.util.module_from_spec(spec)
original_path = sys.path[:]
try:
    spec.loader.exec_module(run_host)
finally:
    sys.path[:] = original_path
from supervisor import Journal, Supervisor


class Adapter:
    def __init__(self):
        self.now = 1.
        self.active = False
        self.submissions = []
        self.cancellations = []

    def busy(self):
        return self.active

    def tcp_position(self):
        return [.4, 0., .2]

    def joints(self):
        return [0.] * 7

    def submit(self, action):
        self.submissions.append(copy.deepcopy(action))
        self.active = True
        return {"request_id": action["request_id"], "status": "accepted"}

    def cancel(self, reason):
        self.cancellations.append(reason)
        self.active = False  # Physical idle does not invent terminal feedback.


class DecisionStub:
    def __init__(self):
        self.steps = []
        self.pending = None
        self.feedback = []

    def step(self, packet):
        self.steps.append(copy.deepcopy(packet))
        if self.pending is not None:
            return {"type": "wait"}
        action = {"request_id": "next-inspection", "operation": "inspect", "part_id": "B2"}
        self.pending = {"action": copy.deepcopy(action), "feedback": None}
        return {"type": "action", "action": action}

    def accept_feedback(self, feedback):
        self.feedback.append(copy.deepcopy(feedback))
        if self.pending and feedback["request_id"] == self.pending["action"]["request_id"]:
            self.pending["feedback"] = copy.deepcopy(feedback)

    def drain_events(self):
        return []


class Capture:
    def __init__(self):
        self.phases = []

    def phase(self, name, sim_clock):
        self.phases.append((name, sim_clock()))
        return nullcontext()


class ConventionalAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.adapter = Adapter()
        self.baseline = DecisionStub()
        self.journal = Journal(self.root / "protected", self.root / "public", "synthetic-admission")
        self.host = Supervisor(self.adapter, self.baseline, self.journal)
        self.capture = Capture()
        self.sequence = 0
        self.observe()

    def observe(self, capture_time=None):
        self.sequence += 1
        self.host.update_observation({
            "sequence": self.sequence, "sim_time": self.adapter.now,
            "capture_sim_time_s": self.adapter.now if capture_time is None else capture_time,
            "order": {"version": 1},
            "detections": [{"id": "B2", "zone": "inspection"}],
            "station": {"busy": False, "fault": False},
            "gripper": {"width": .08, "holding_visible_id": None},
        })

    def outstanding_transport(self):
        result = self.host.command(self.host.envelope("previous-transport", {
            "operation": "transport", "part_id": "B2", "destination": "inspection",
        }), "conventional")
        self.assertEqual(result["command"]["status"], "accepted")
        self.assertEqual(self.host.active_command, "previous-transport")
        # Independent physics has finished, but its feedback is not yet drained.
        self.adapter.active = False
        self.observe()

    def retire_transport(self, status="completed"):
        self.host.native_feedback({"request_id": "previous-transport", "status": status,
                                   "sim_time": self.adapter.now})

    def decide(self, next_decision=0.):
        return run_host.conventional_decision(self.host, next_decision, self.capture)

    def test_old_idle_pending_path_advances_and_loses_rejection_feedback(self):
        self.outstanding_transport()
        self.host.conventional_step()  # Actual pre-repair scheduling behavior.
        self.assertEqual(len(self.baseline.steps), 1)
        self.assertEqual(self.host.commands["next-inspection"]["error"]["code"], "resource_busy")
        self.assertEqual(self.host.commands["next-inspection"]["status"], "rejected")
        self.assertIsNone(self.baseline.pending["feedback"])
        self.assertEqual([a["request_id"] for a in self.adapter.submissions], ["previous-transport"])

    def test_waits_for_durable_terminal_then_admits_next_action_exactly_once(self):
        self.outstanding_transport()
        for now in (1., 1.1, 1.3):
            self.adapter.now = now
            self.observe()  # Observations still drain while decisions wait.
            self.assertEqual(self.decide(.5), .5)
        self.assertEqual(self.baseline.steps, [])
        self.assertIsNone(self.baseline.pending)
        self.assertNotIn("next-inspection", self.host.commands)
        self.assertEqual(self.capture.phases, [])
        self.retire_transport()
        original_submit = self.adapter.submit

        def checked_submit(action):
            registry = json.loads((self.journal.root / "command-registry.json").read_bytes())
            self.assertEqual(registry["previous-transport"]["status"], "completed")
            self.assertEqual(registry["next-inspection"]["phase"], "dispatched")
            return original_submit(action)

        with patch.object(self.adapter, "submit", side_effect=checked_submit):
            next_decision = self.decide(.5)
        self.assertEqual(next_decision, self.adapter.now + .2)
        self.assertEqual(self.capture.phases, [("conventional_decision", 1.3)])
        self.assertEqual(self.host.active_command, "next-inspection")
        self.assertEqual(self.baseline.pending["feedback"]["status"], "accepted")
        for now in (1.31, 1.5, 1.7):
            self.adapter.now = now
            self.observe()
            self.assertEqual(self.decide(next_decision), next_decision)
        self.assertEqual(len(self.baseline.steps), 1)
        self.assertEqual([a["request_id"] for a in self.adapter.submissions],
                         ["previous-transport", "next-inspection"])

    def test_nonterminal_feedback_does_not_open_admission(self):
        self.outstanding_transport()
        self.retire_transport("accepted")
        self.assertEqual(self.decide(), 0.)
        self.assertEqual(self.host.active_command, "previous-transport")
        self.assertEqual(self.baseline.steps, [])

    def test_missing_terminal_keeps_guard_and_existing_cancellation_deadline(self):
        self.outstanding_transport()
        self.adapter.now = 92.
        self.observe()
        self.host.housekeeping()
        self.assertEqual(self.adapter.cancellations, ["maximum independent skill interval reached"])
        for now in (92., 93., 241.):
            self.adapter.now = now
            self.observe()
            self.assertEqual(self.decide(), 0.)
        self.assertEqual(self.host.active_command, "previous-transport")
        self.assertEqual(self.host.commands["previous-transport"]["status"], "accepted")
        self.assertEqual(self.baseline.steps, [])
        self.assertNotIn("next-inspection", self.host.commands)

    def test_authority_and_physical_busy_checks_remain_in_original_supervisor(self):
        for owner, busy in (("robot", False), ("conventional", True)):
            with self.subTest(owner=owner, busy=busy):
                self.host.owner, self.adapter.active = owner, busy
                self.assertEqual(self.decide(), self.adapter.now + .2)
                self.assertEqual(self.baseline.steps, [])
                self.assertEqual(self.adapter.submissions, [])
        self.host.owner, self.adapter.active = "conventional", False
        self.decide()
        self.assertEqual(len(self.adapter.submissions), 1)
        self.assertEqual(self.adapter.submissions[0]["incarnation"], self.host.epoch)

    def test_physical_busy_still_defers_after_supervisor_terminal(self):
        self.outstanding_transport()
        self.retire_transport()
        self.adapter.active = True
        next_decision = self.decide()
        self.assertEqual(self.baseline.steps, [])
        self.adapter.active = False
        self.adapter.now = next_decision
        self.observe()
        self.decide(next_decision)
        self.assertEqual(len(self.baseline.steps), 1)
        self.assertEqual(self.host.commands["next-inspection"]["status"], "accepted")

    def test_cadence_is_unchanged_including_exact_due_boundary(self):
        self.assertEqual(self.decide(1.2), 1.2)
        self.assertEqual(self.baseline.steps, [])
        self.adapter.now = 1.2
        self.observe()
        self.assertEqual(self.decide(1.2), 1.4)
        self.assertEqual(len(self.baseline.steps), 1)

    def test_observation_age_limit_and_missing_packet_remain_unchanged(self):
        self.host.packet = None
        self.assertEqual(self.decide(), 0.)
        self.adapter.now = .350001
        self.observe(capture_time=0.)
        self.assertEqual(self.decide(), 0.)
        self.assertEqual(self.baseline.steps, [])
        self.adapter.now = .35
        self.observe(capture_time=0.)
        self.assertEqual(self.decide(), .55)
        self.assertEqual(len(self.baseline.steps), 1)
        self.assertEqual(self.host.commands["next-inspection"]["status"], "accepted")


if __name__ == "__main__":
    unittest.main()
