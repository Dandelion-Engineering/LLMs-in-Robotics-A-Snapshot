"""Synthetic gateway checks only; never import or instantiate a physical Cell."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from supervisor import Supervisor, Journal, GatewayError, canonical
from challenges import make_manifest, validate_manifest, source_binding
from run_host import RUNTIME
sys.path.insert(0, str(RUNTIME))
from candidates import Candidate


class FakeAdapter:
    def __init__(self):
        self.now = 1.
        self.active = False
        self.submissions = []
        self.cancels = []
        self.observation_requests = 0

    def tcp_position(self): return [.4, 0., .2]
    def joints(self): return [0.] * 7
    def busy(self): return self.active
    def submit(self, action):
        self.submissions.append(copy.deepcopy(action)); self.active = True
        return {"request_id": action["request_id"], "status": "accepted"}
    def cancel(self, reason): self.cancels.append(reason); self.active = False
    def request_observation(self): self.observation_requests += 1


def packet(zone="quarantine", *, family="A", sequence=1, sim=1.):
    return {"run_id": "synthetic-only", "incarnation": 1, "restart_generation": 0,
            "sequence": sequence, "sim_time": sim, "capture_sim_time_s": sim,
            "order": {"version": 1, "closed": True, "requirements": [
                {"family": family, "recipe": family, "count": 1, "tray": "tray1"}]},
            "process_contract": {"family_recipes": {"A": "A", "B": "B"}, "processed_mark_requires_eligible_cycle": True},
            "detections": [{"id": family + "1", "family": family, "kind": "part", "pos": [.2, .29, .018],
                            "zone": zone, "visible_mark": "raw", "age_s": 0.}],
            "station": {"busy": False, "ready": True, "fault": False, "cycle_id": 0,
                        "completed_cycle_id": None, "fixture_insert": "A", "occupied_visible_id": None},
            "gripper": {"holding_visible_id": None, "width": .08}, "inspection": None, "last_feedback": None}


class SupervisorChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.adapter = FakeAdapter()
        self.journal = Journal(self.path / "protected", self.path / "runtime", "synthetic-only")
        self.baseline = Candidate("baseline", self.path / "baseline", True)
        self.host = Supervisor(self.adapter, self.baseline, self.journal)
        self.host.update_observation(packet())
        self.host.activate("Synthetic test activation")

    def tearDown(self): self.temp.cleanup()

    def body(self, rid="test-action", action=None):
        return self.host.envelope(rid, action or {"operation": "transport", "part_id": "A1", "destination": "parking1"})

    def test_log_and_registry_are_durable_before_dispatch(self):
        original = self.adapter.submit
        def submit(action):
            rows = [json.loads(line) for line in self.journal.events_path.read_text().splitlines()]
            registry = json.loads((self.journal.root / "command-registry.json").read_text())
            self.assertEqual(rows[-1]["type"], "command_dispatched")
            self.assertEqual(registry[action["request_id"]]["phase"], "dispatched")
            return original(action)
        self.adapter.submit = submit
        self.host.command(self.body())
        self.assertEqual(len(self.adapter.submissions), 1)

    def test_failed_logging_prevents_any_dispatch(self):
        with patch.object(self.journal, "event", side_effect=OSError("synthetic disk full")):
            with self.assertRaises(OSError): self.host.command(self.body())
        self.assertEqual(self.adapter.submissions, [])

    def test_duplicate_lost_ack_never_redispatches(self):
        body = self.body()
        first = self.host.command(body)
        second = self.host.command(body)
        self.assertEqual(first["command"]["status"], "accepted")
        self.assertTrue(second["duplicate"])
        self.assertEqual(len(self.adapter.submissions), 1)
        body["action"]["destination"] = "parking2"
        with self.assertRaises(GatewayError): self.host.command(body)

    def test_wrong_owner_old_epoch_and_task_are_rejected(self):
        for key, value in (("authority_epoch", 0), ("order_version", 99)):
            body = self.body(key); body[key] = value
            result = self.host.command(body)
            self.assertEqual(result["command"]["status"], "rejected")
        self.host.owner = "conventional"
        self.assertEqual(self.host.command(self.body("wrong-owner"))["command"]["error"]["code"], "wrong_owner")
        self.assertEqual(self.adapter.submissions, [])

    def test_stale_observation_rejected_but_observe_can_refresh(self):
        self.adapter.now += 1.
        self.assertEqual(self.host.command(self.body())["command"]["error"]["code"], "stale_observation")
        body = self.host.envelope("refresh")
        self.assertEqual(self.host.observe(body)["command"]["status"], "accepted")
        self.host.update_observation(packet(sequence=2, sim=2.))
        self.assertEqual(self.host.commands["refresh"]["status"], "completed")

    def test_observation_deadline_is_explicit(self):
        self.host.observe(self.host.envelope("refresh"))
        self.adapter.now += 4.
        self.host.housekeeping()
        self.assertEqual(self.host.commands["refresh"]["status"], "expired")

    def test_receipt_and_terminal_do_not_invent_physical_success(self):
        self.host.command(self.body())
        self.host.native_feedback({"request_id": "test-action", "status": "completed"})
        record = self.host.commands["test-action"]
        self.assertEqual(record["verification"]["state"], "unknown")
        self.adapter.now = 1.1
        self.host.update_observation(packet(sequence=2, sim=1.1))
        self.assertEqual(record["verification"]["state"], "unknown")
        self.adapter.now = 1.2
        self.host.update_observation(packet("parking1", sequence=3, sim=1.2))
        self.assertEqual(record["verification"]["state"], "public_observation_support")

    def test_relative_motion_and_gripper_use_same_native_gate(self):
        result = self.host.command(self.body("relative", {"operation": "move_relative", "frame": "world", "delta": [.01, 0., 0.], "duration_s": 1.}))
        native = self.adapter.submissions[0]
        self.assertEqual(native["operation"], "cartesian_target")
        self.assertAlmostEqual(native["position"][0], .41)
        self.assertEqual(native["incarnation"], self.host.epoch)
        self.assertEqual(result["command"]["status"], "accepted")

    def test_relative_step_bound_and_unknown_fields_fail(self):
        bad = {"operation": "move_relative", "frame": "world", "delta": [.06, 0, 0], "duration_s": 1.}
        self.assertEqual(self.host.command(self.body("bad", bad))["command"]["error"]["code"], "relative_bound")
        bad = {"operation": "wait", "simulator_state": {}}
        self.assertEqual(self.host.command(self.body("bad2", bad))["command"]["status"], "rejected")
        self.assertEqual(self.adapter.submissions, [])

    def test_action_budget_survives_agent_generation_restart(self):
        self.host.robot_action_count = 20
        self.host.restart_agent(self.host.envelope("restart"))
        self.assertEqual(self.host.command(self.body())["command"]["error"]["code"], "action_budget")

    def test_restart_fences_old_command_and_updates_activation(self):
        old = self.body()
        self.host.restart_agent({**self.host.envelope("restart"), "reason": "synthetic interruption"})
        self.assertEqual(self.host.command(old)["command"]["error"]["code"], "stale_authority")
        activation = json.loads((self.journal.live / "activation.json").read_text())
        self.assertEqual(activation["authority_epoch"], self.host.epoch)
        self.assertEqual(activation["order_version"], 1)

    def test_denied_handback_does_not_mutate_baseline_or_checkpoint(self):
        self.baseline.state["halted"] = True
        self.baseline._persist()
        state, checkpoint = copy.deepcopy(self.baseline.__dict__), self.baseline.state_path.read_bytes()
        result = self.host.handback(self.host.envelope("handback"))
        self.assertEqual(result["command"]["status"], "rejected")
        self.assertEqual(self.baseline.__dict__, state)
        self.assertEqual(self.baseline.state_path.read_bytes(), checkpoint)
        self.assertEqual(self.host.owner, "robot")
        self.assertEqual(self.host.assistance, [])

    def test_supported_handback_preserves_failure_counts_and_changes_owner(self):
        self.host.update_observation(packet("parking1"))
        self.baseline.state["failure_counts"] = {"unrelated": 2}
        result = self.host.handback(self.host.envelope("handback"))
        self.assertEqual(result["command"]["status"], "completed")
        self.assertEqual(self.host.owner, "conventional")
        self.assertEqual(self.host.baseline.state["failure_counts"], {"unrelated": 2})

    def test_continuity_backup_atomic_replace_and_size_limit(self):
        path = self.journal.workspace / "Continuity.md"; path.write_text("old", encoding="utf-8")
        result = self.host.request("POST", "/continuity", {"content": "new"})
        self.assertEqual(path.read_text(), "new")
        self.assertEqual((self.journal.root / "continuity-history" / (result["previous_sha256"] + ".md")).read_text(), "old")
        with self.assertRaises(GatewayError): self.host.request("POST", "/continuity", {"content": "x" * 32769})
        self.assertEqual(path.read_text(), "new")

    def test_program_runner_explicitly_disabled(self):
        with self.assertRaises(GatewayError) as caught:
            self.host.request("POST", "/run-program", {})
        self.assertEqual(caught.exception.status, 403)

    def test_frozen_stock_rule_never_selects_quarantine(self):
        self.baseline._ingest(packet())
        self.assertIsNone(self.baseline._baseline_action(visibility_fallback=False))
        self.baseline._ingest(packet("parking1"))
        self.assertEqual(self.baseline._baseline_action()["operation"], "transport")

    def test_unknown_named_insert_home_is_not_candidate_stock(self):
        self.baseline._ingest(packet("insert_home_A"))
        self.assertEqual(self.baseline._visible, {})

    def test_manifest_validation_is_development_only(self):
        value = make_manifest("misplaced-stock", "reference", "test")
        self.assertEqual(validate_manifest(value), value)
        value["stage"] = "evaluation"
        with self.assertRaises(ValueError): validate_manifest(value)

    def test_frozen_sources_still_match_release(self):
        hashes = source_binding(RUNTIME)
        self.assertEqual(hashes["candidates.py"], "4ba2aa0980ca36ae2748fc06c44b5fe5208f3fbf2666c650a54874e45874f8bc")


if __name__ == "__main__": unittest.main()
