"""Development-only protected gateway; no model client or evaluator output here.

All methods are called on the physics owner's thread. The HTTP thread uses a
queue, never Cell directly. Public files are mirrors, not trusted control input.
"""
from __future__ import annotations
import copy
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time

SCHEMA = "robot-codex-host-1.0"
MAX_BYTES = 200 * 1024 * 1024
MAX_AGE = .35
RID = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
TERMINAL = {"completed", "failed", "rejected", "cancelled", "expired", "error"}
ATOMIC_REPLACE_DELAYS = (.005, .01, .02, .04)
ATOMIC_REPLACE_RETRIES = {"retries": 0, "exhausted": 0, "requested_wait_s": 0.}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def atomic_json(path, value):
    atomic_bytes(path, canonical(value) + b"\n")


def atomic_bytes(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".next")
    with temp.open("wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    # Windows readers can briefly deny FILE_SHARE_DELETE while a public mirror
    # is inspected. Retry only replacement and only Windows access/sharing/lock
    # errors, preserving the fsynced staged bytes and last committed destination.
    # Never delete the destination, change ACLs, or retry open/fsync failures.
    # A persistent denial still propagates after at most 75 ms requested sleep.
    for attempt in range(len(ATOMIC_REPLACE_DELAYS) + 1):
        try:
            os.replace(temp, path)
            return
        except PermissionError as error:
            if getattr(error, "winerror", None) not in (5, 32, 33):
                raise
            if attempt == len(ATOMIC_REPLACE_DELAYS):
                ATOMIC_REPLACE_RETRIES["exhausted"] += 1
                raise
            delay = ATOMIC_REPLACE_DELAYS[attempt]
            ATOMIC_REPLACE_RETRIES["retries"] += 1
            ATOMIC_REPLACE_RETRIES["requested_wait_s"] += delay
            time.sleep(delay)


class GatewayError(ValueError):
    def __init__(self, code, message, status=409):
        super().__init__(message)
        self.code, self.status = code, status


def require(condition, code, message, status=409):
    if not condition:
        raise GatewayError(code, message, status)


class Journal:
    """Authoritative append/fsync outside agent mount; bounded public mirror."""
    def __init__(self, root, workspace, run_id, limit=MAX_BYTES):
        self.root, self.workspace = Path(root), Path(workspace)
        self.root.mkdir(parents=True, exist_ok=True)
        self.live = self.workspace / "live"
        self.live.mkdir(parents=True, exist_ok=True)
        self.events_path = self.root / "public-history.jsonl"
        self.mirror_path = self.live / "events.jsonl"
        require(not self.events_path.exists(), "existing_episode", "New evidence directory required")
        self.run_id, self.limit, self.bytes = run_id, limit, 0
        self.events = []
        self.start = time.monotonic()

    def event(self, kind, payload, sim, epoch, owner, *, source="supervisor"):
        item = {"schema": SCHEMA, "event_id": len(self.events) + 1,
                "run_id": self.run_id, "authority_epoch": epoch, "owner": owner,
                "source": source, "type": kind, "sim_time_s": sim,
                "wall_elapsed_s": time.monotonic() - self.start,
                "wall_unix_s": time.time(), "payload": copy.deepcopy(payload)}
        raw = canonical(item) + b"\n"
        # Count protected and mirrored records plus snapshots in the declared cap.
        require(self.bytes + 2 * len(raw) < self.limit - 2 * 1024 * 1024,
                "storage_limit", "Evidence budget reached; new actuation refused", 507)
        for path in (self.events_path, self.mirror_path):
            with path.open("ab") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        self.bytes += 2 * len(raw)
        self.events.append(item)
        return item["event_id"]

    def state(self, value):
        atomic_json(self.root / "public-state.json", value)
        atomic_json(self.live / "state.json", value)

    def registry(self, commands):
        atomic_json(self.root / "command-registry.json", commands)

    def continuity(self, content):
        require(isinstance(content, str), "invalid_note", "content must be a string", 400)
        raw = content.encode("utf-8")
        require(len(raw) <= 32768, "invalid_note", "Continuity exceeds 32768 UTF-8 bytes", 413)
        current = self.workspace / "Continuity.md"
        require(not current.is_symlink(), "invalid_note", "Continuity must not be a symbolic link", 400)
        previous = current.read_bytes() if current.exists() else b""
        require(len(previous) <= 32768, "invalid_note", "Existing note exceeds bounded backup size", 413)
        old_hash = hashlib.sha256(previous).hexdigest()
        backup = self.root / "continuity-history" / (old_hash + ".md")
        if not backup.exists():
            require(self.bytes + len(previous) + len(raw) < self.limit - 2 * 1024 * 1024,
                    "storage_limit", "Evidence budget reached", 507)
            atomic_bytes(backup, previous)
            self.bytes += len(previous)
        new_hash = hashlib.sha256(raw).hexdigest()
        retained = self.root / "continuity-history" / (new_hash + ".md")
        if not retained.exists():
            require(self.bytes + len(raw) < self.limit - 2 * 1024 * 1024,
                    "storage_limit", "Evidence budget reached", 507)
            atomic_bytes(retained, raw)
            self.bytes += len(raw)
        atomic_bytes(current, raw)
        return {"sha256": new_hash, "bytes": len(raw),
                "previous_sha256": old_hash}

    def read_continuity(self):
        current = self.workspace / "Continuity.md"
        require(not current.is_symlink(), "invalid_note", "Continuity must not be a symbolic link", 400)
        raw = current.read_bytes() if current.exists() else b""
        require(len(raw) <= 32768, "invalid_note", "Continuity exceeds bounded size", 413)
        return {"ok": True, "content": raw.decode("utf-8"), "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest()}


class Supervisor:
    def __init__(self, adapter, baseline, journal):
        self.adapter, self.baseline, self.journal = adapter, baseline, journal
        self.owner, self.epoch = "conventional", 1
        self.packet = None
        self.commands = {}
        self.observations = {}
        self.active_command = None
        self.activation = None
        self.assistance = []
        self.baseline_steps = 0
        self.handoffs = 0
        self.last_conventional_request = None
        self.command_counter = 0
        self.fresh_requests = []
        self.stopped = False
        self.publish_due = 0.
        self.robot_action_count = 0
        self.robot_observe_count = 0
        self.last_robot_request = -float("inf")
        self.lifecycle_required = False
        self.invocation = None
        self.invocation_count = 0
        self.stop_requested = None

    @property
    def now(self):
        return float(self.adapter.now)

    def emit(self, kind, payload, source="supervisor"):
        return self.journal.event(kind, payload, self.now, self.epoch, self.owner, source=source)

    def update_observation(self, packet):
        self.packet = copy.deepcopy(packet)
        seq = packet["sequence"]
        capture = packet["capture_sim_time_s"]
        new = seq not in self.observations
        self.observations[seq] = capture
        self.observations = {s: t for s, t in self.observations.items() if self.now - t < 3.}
        if new:
            self.emit("observation", packet, "public_camera_and_devices")
            atomic_json(self.journal.live / "observations" / "latest.json", packet)
            for rid in list(self.fresh_requests):
                record = self.commands[rid]
                if capture >= record["requested_sim_time_s"]:
                    record.update(phase="terminal", status="completed", observation_sequence=seq,
                                  terminal_sim_time_s=self.now,
                                  verification={"state": "not_applicable", "reason": "observation acquisition"})
                    self.fresh_requests.remove(rid)
                    self.emit("command_terminal", record)
            self.verify_public_outcomes()
            self.journal.registry(self.commands)

    def fresh(self, envelope):
        sequence = envelope.get("observation_sequence")
        require(type(sequence) is int and sequence in self.observations,
                "unknown_observation", "Use an observation sequence returned by this supervisor")
        require(0 <= self.now - self.observations[sequence] <= MAX_AGE,
                "stale_observation", "Observation is older than 0.35 simulation seconds")

    def fence(self, envelope, actor="robot", fresh=True):
        require(not self.stopped, "stopped", "Supervisor is stopped")
        require(self.owner == actor, "wrong_owner", "Caller does not own the arm")
        if actor == "robot" and self.lifecycle_required:
            require(self.invocation and self.invocation["state"] == "active",
                    "invocation_retired", "Trusted launcher must start a fresh invocation")
        require(type(envelope.get("authority_epoch")) is int and envelope["authority_epoch"] == self.epoch,
                "stale_authority", "Authority epoch changed; reconstruct current state")
        require(self.packet is not None, "no_observation", "No observation available")
        require(type(envelope.get("order_version")) is int and envelope["order_version"] == self.packet["order"]["version"],
                "stale_task", "Task revision changed")
        if fresh:
            self.fresh(envelope)

    def envelope(self, rid, action=None):
        result = {"request_id": rid, "authority_epoch": self.epoch,
                  "order_version": self.packet["order"]["version"],
                  "observation_sequence": self.packet["sequence"]}
        if action is not None:
            result["action"] = action
        return result

    def reserve(self, envelope, kind, actor):
        rid = envelope.get("request_id")
        require(isinstance(rid, str) and RID.fullmatch(rid), "invalid_id", "Invalid stable request_id", 400)
        fingerprint = hashlib.sha256(canonical({"kind": kind, "actor": actor, "body": envelope})).hexdigest()
        previous = self.commands.get(rid)
        if previous:
            require(previous["fingerprint"] == fingerprint, "id_conflict", "Request ID already used with a different payload")
            return previous, True
        require(len(self.commands) < 5000, "command_limit", "Episode command limit reached", 429)
        record = {"request_id": rid, "kind": kind, "actor": actor,
                  "fingerprint": fingerprint, "envelope": copy.deepcopy(envelope),
                  "phase": "requested", "status": "pending", "requested_sim_time_s": self.now,
                  "verification": {"state": "unknown", "reason": "No post-action evidence yet"}}
        record["request_event_id"] = self.emit("command_requested", record, actor)
        self.commands[rid] = record
        self.journal.registry(self.commands)  # Durable identity before any dispatch.
        return record, False

    def failed(self, record, error):
        record.update(phase="terminal", status="rejected", terminal_sim_time_s=self.now,
                      error={"code": error.code, "message": str(error)})
        self.emit("command_rejected", record)
        self.journal.registry(self.commands)
        return copy.deepcopy(record)

    def normalize(self, action):
        require(isinstance(action, dict), "invalid_action", "action must be an object", 400)
        action = copy.deepcopy(action)
        op = action.get("operation")
        allowed = {
            "transport": {"operation", "part_id", "destination", "objective", "reason"},
            "recover_held": {"operation", "destination", "reason"},
            "setup": {"operation", "family", "reason"},
            "cycle": {"operation", "part_id", "recipe", "reason"},
            "inspect": {"operation", "part_id", "reason"},
            "observe": {"operation", "clear_view", "reason"},
            "wait": {"operation", "reason"}, "done": {"operation", "reason"},
            "help": {"operation", "reason", "evidence", "requested_information_or_action"},
            "cancel": {"operation", "target_request_id", "reason"},
            "cartesian_target": {"operation", "position", "duration_s", "gripper", "reason"},
            "joint_command": {"operation", "mode", "values", "duration_s", "gripper", "reason"},
            "trajectory": {"operation", "waypoints", "gripper", "reason"},
            "move_relative": {"operation", "delta", "frame", "duration_s", "gripper", "reason"},
            "gripper": {"operation", "state", "duration_s", "reason"},
        }
        require(op in allowed and set(action) <= allowed[op], "invalid_action", "Unknown operation or fields", 400)
        for key in ("part_id", "family", "recipe", "destination", "target_request_id"):
            if key in action:
                require(isinstance(action[key], str) and len(action[key]) <= 128,
                        "invalid_action", key + " must be a bounded string", 400)
        if op == "move_relative":
            delta = action.pop("delta", None)
            require(action.pop("frame", None) == "world", "invalid_frame", "Only world frame is supported", 400)
            require(isinstance(delta, list) and len(delta) == 3 and
                    all(type(v) in (float, int) and math.isfinite(v) for v in delta),
                    "invalid_delta", "delta must contain three finite numbers", 400)
            require(sum(v*v for v in delta) <= .05**2 + 1e-12,
                    "relative_bound", "Relative step exceeds 0.05 m", 400)
            tcp = self.adapter.tcp_position()
            action.update(operation="cartesian_target", position=[a+b for a, b in zip(tcp, delta)])
        elif op == "gripper":
            state = action.pop("state", None)
            require(state in ("open", "close"), "invalid_gripper", "state must be open or close", 400)
            action.update(operation="joint_command", mode="position", values=self.adapter.joints(),
                          duration_s=action.get("duration_s", .5), gripper=255 if state == "open" else 0)
        return action

    def command(self, envelope, actor="robot"):
        record, duplicate = self.reserve(envelope, "command", actor)
        if duplicate:
            return {"ok": True, "duplicate": True, "command": copy.deepcopy(record)}
        try:
            self.fence(envelope, actor)
            action = self.normalize(envelope.get("action"))
            if actor == "robot":
                require(self.robot_action_count < 20, "action_budget", "Activation has reached its 20 action budget", 429)
                require(self.now - self.last_robot_request >= .1, "request_rate", "Robot commands require at least 0.1 simulation seconds between requests", 429)
                self.robot_action_count += 1
                self.last_robot_request = self.now
            require(not self.active_command or action["operation"] == "cancel",
                    "resource_busy", "Another command is outstanding")
            action.update(request_id=record["request_id"], incarnation=self.epoch,
                          order_version=envelope["order_version"])
            record.update(phase="dispatched", status="pending", native_action=action,
                          dispatched_sim_time_s=self.now)
            self.emit("command_dispatched", record)
            self.journal.registry(self.commands)
            feedback = self.adapter.submit(action)
            record["admission"] = copy.deepcopy(feedback)
            if feedback["status"] != "accepted":
                record.update(phase="terminal", status="rejected", terminal_sim_time_s=self.now)
            else:
                record.update(phase="admitted", status="accepted")
                if action["operation"] != "cancel":
                    self.active_command = record["request_id"]
            self.emit("command_admission", {"request_id": record["request_id"], "feedback": feedback})
            self.journal.registry(self.commands)
            if actor == "conventional":
                self.baseline.accept_feedback(feedback)
            return {"ok": True, "command": copy.deepcopy(record)}
        except GatewayError as error:
            return {"ok": True, "command": self.failed(record, error)}
        except (ValueError, KeyError, TypeError) as error:
            return {"ok": True, "command": self.failed(record, GatewayError("native_rejected", str(error), 400))}

    def native_feedback(self, feedback):
        rid = feedback.get("request_id")
        record = self.commands.get(rid)
        if not record:
            self.emit("unmatched_feedback", feedback)
            return
        record["feedback"] = copy.deepcopy(feedback)
        if feedback.get("status") in TERMINAL:
            record.update(phase="terminal", status=feedback["status"], terminal_sim_time_s=self.now)
            if self.active_command == rid:
                self.active_command = None
        self.emit("command_terminal" if record["phase"] == "terminal" else "command_feedback",
                  {"request_id": rid, "feedback": feedback, "verification": record["verification"]})
        self.journal.registry(self.commands)
        if record["actor"] == "conventional":
            self.baseline.accept_feedback(feedback)

    def native_event(self, event):
        # Whitelist public execution events; never copy truth or protected poses.
        if event.get("type") not in {"trajectory_dispatched", "direct_control_admitted", "setup_waiting_for_fresh_capture",
                                     "setup_return_observed", "cycle_complete", "cycle_fault", "stale_plan_discarded"}:
            return
        self.emit("native_" + event["type"], event, "robot_service")
        record = self.commands.get(event.get("request_id"))
        if record and event["type"] in {"trajectory_dispatched", "direct_control_admitted"} and record["phase"] != "terminal":
            record["phase"] = "executing"

    def verify_public_outcomes(self):
        if not self.packet:
            return
        for record in self.commands.values():
            if record["kind"] != "command" or record.get("status") != "completed" or record["verification"]["state"] != "unknown":
                continue
            terminal = record.get("terminal_sim_time_s", float("inf"))
            if self.packet["capture_sim_time_s"] <= terminal:
                continue
            action = record["envelope"]["action"]
            op = action["operation"]
            observed = False
            if op == "transport":
                observed = any(d["id"] == action["part_id"] and d["zone"] == action["destination"] for d in self.packet["detections"])
            elif op == "setup":
                observed = self.packet["station"].get("fixture_insert") == action["family"]
            elif op == "inspect":
                observed = (self.packet.get("inspection") or {}).get("inspection_id") == record["request_id"]
            elif op == "cycle":
                observed = (record.get("feedback", {}).get("cycle_id") is not None and
                            self.packet["station"].get("completed_cycle_id") == record["feedback"]["cycle_id"])
            if observed:
                record["verification"] = {"state": "public_observation_support", "observation_sequence": self.packet["sequence"],
                                          "capture_sim_time_s": self.packet["capture_sim_time_s"],
                                          "scope": "Observed effect only; independent evaluator result remains separate"}
                self.emit("public_effect_verification", {"request_id": record["request_id"], **record["verification"]})

    def activate(self, symptom, event_id=None):
        if self.owner == "robot":
            return
        require(not self.adapter.busy(), "unsafe_boundary", "Cannot transfer while arm command remains active")
        self.owner = "robot"
        self.epoch += 1
        self.robot_action_count = 0
        self.robot_observe_count = 0
        self.activation = {"activation_id": "activation-001", "reason": symptom, "trigger_event_id": event_id,
                           "authority_epoch": self.epoch, "sim_time_s": self.now,
                           "order_version": self.packet["order"]["version"],
                           "source": "public conventional feedback", "cause": "unknown"}
        self.emit("control_owner_changed", self.activation)
        atomic_json(self.journal.live / "activation.json", self.activation)
        self.publish()

    def conventional_step(self):
        if self.owner != "conventional" or self.adapter.busy() or not self.packet:
            return
        packet = copy.deepcopy(self.packet)
        packet.update(incarnation=self.epoch, restart_generation=0, human_answers=copy.deepcopy(self.assistance))
        reply = self.baseline.step(packet)
        self.baseline_steps += 1
        # Baseline file-content events stay in its protected checkpoint directory.
        self.baseline.drain_events()
        if reply.get("type") != "action":
            return
        action = copy.deepcopy(reply["action"])
        rid = action.pop("request_id")
        action.pop("incarnation", None)
        action.pop("order_version", None)
        action.pop("observation_sequence", None)
        if action["operation"] == "help":
            self.last_conventional_request = rid
            self.emit("conventional_assistance_requested", {"request_id": rid, "action": action})
            self.activate(action.get("reason", "Conventional controller requested assistance"))
            return
        if action["operation"] == "wait":
            # Expected process waiting is never interpreted as a failed recovery.
            if packet["station"].get("fault"):
                self.activate("Public station fault persists; conventional controller waits")
            return
        self.command(self.envelope(rid, action), "conventional")

    def observe(self, envelope):
        record, duplicate = self.reserve(envelope, "observe", "robot")
        if duplicate:
            return {"ok": True, "duplicate": True, "command": copy.deepcopy(record)}
        try:
            self.fence(envelope, fresh=False)
            require(self.robot_observe_count < 50, "observation_budget", "Activation has reached its 50 explicit observation budget", 429)
            self.robot_observe_count += 1
            record.update(phase="admitted", status="accepted", deadline_sim_time_s=self.now + 3.)
            self.fresh_requests.append(record["request_id"])
            self.adapter.request_observation()
            self.emit("observation_requested", record)
            self.journal.registry(self.commands)
            return {"ok": True, "command": copy.deepcopy(record)}
        except GatewayError as error:
            return {"ok": True, "command": self.failed(record, error)}

    def handback(self, envelope):
        record, duplicate = self.reserve(envelope, "handback", "robot")
        if duplicate:
            return {"ok": True, "duplicate": True, "command": copy.deepcopy(record)}
        try:
            self.fence(envelope)
            require(not self.active_command and not self.adapter.busy(), "resource_busy", "Outstanding motion must end before handback")
            require(not self.packet["station"].get("busy") and not self.packet["station"].get("fault"),
                    "device_unready", "Machine must be idle without a public fault")
            require(self.packet["gripper"]["width"] >= .065 and not self.packet["gripper"].get("holding_visible_id"),
                    "gripper_unresolved", "Fresh observation must support empty open jaws")
            packet = copy.deepcopy(self.packet)
            # Reconcile using an honest public assistance receipt through the frozen interface.
            answer = {"answer_id": "handback-" + record["request_id"],
                      "request_id": self.last_conventional_request or record["request_id"],
                      "text": "Recovery authority returned; reconcile all outcomes with current public observations."}
            packet.update(incarnation=self.epoch + 1, restart_generation=0, human_answers=self.assistance + [answer])
            # Preview on a detached instance. No checkpoint or retained state is
            # changed until every handback predicate is accepted.
            preview = copy.deepcopy(self.baseline)
            preview._ingest(packet)
            preview._reconcile()
            proposal = preview._baseline_action(visibility_fallback=False)
            require(proposal is not None and proposal.get("operation") in ("transport", "setup", "cycle", "inspect", "done")
                    and preview._validate(proposal) is None,
                    "unsupported_resumption", "Frozen conventional controller lacks a currently supported next action")
            require(preview.state.get("pending") is None,
                    "unknown_outcome", "Conventional controller retains an unresolved action")
            self.assistance.append(answer)
            self.baseline = preview
            self.baseline._persist()
            self.owner, self.epoch = "conventional", self.epoch + 1
            if self.invocation:
                self.invocation.update(state="handed_back", ended_sim_time_s=self.now)
            self.handoffs += 1
            record.update(phase="terminal", status="completed", terminal_sim_time_s=self.now,
                          verification={"state": "public_resumption_conditions", "next_operation": proposal["operation"]})
            self.emit("control_owner_changed", {"request_id": record["request_id"], "reason": envelope.get("reason"),
                                                "supported_next_action": proposal})
            self.journal.registry(self.commands)
            self.publish()
            return {"ok": True, "owner": self.owner, "authority_epoch": self.epoch, "command": copy.deepcopy(record)}
        except GatewayError as error:
            return {"ok": True, "command": self.failed(record, error)}

    def restart_agent(self, envelope):
        record, duplicate = self.reserve(envelope, "restart-agent", "robot")
        if duplicate:
            return {"ok": True, "duplicate": True, **copy.deepcopy(record.get("transition", {})),
                    "command": copy.deepcopy(record)}
        try:
            self.fence(envelope, fresh=False)
            self.emit("agent_generation_revocation_requested", {"request_id": record["request_id"], "reason": envelope.get("reason")})
            self.adapter.cancel("agent generation revoked")
            self.epoch += 1
            if self.activation:
                self.activation.update(authority_epoch=self.epoch, order_version=self.packet["order"]["version"],
                                       restart_reason=envelope.get("reason"), restart_sim_time_s=self.now)
                atomic_json(self.journal.live / "activation.json", self.activation)
            record.update(phase="terminal", status="completed", terminal_sim_time_s=self.now,
                          transition={"owner": self.owner, "authority_epoch": self.epoch},
                          verification={"state": "authority_generation_changed",
                                        "scope": "Control epoch only; interrupted physical outcomes remain independently unresolved"})
            self.emit("agent_generation_changed", {"request_id": record["request_id"], "authority_epoch": self.epoch,
                                                   "reason": envelope.get("reason"), "unresolved_command": self.active_command})
            self.journal.registry(self.commands)
            self.publish()
            return {"ok": True, **copy.deepcopy(record["transition"]), "command": copy.deepcopy(record)}
        except GatewayError as error:
            return {"ok": True, "command": self.failed(record, error)}

    def lifecycle(self, operation, envelope):
        """Protected launcher calls only. No robot token can reach this route.

        A retired namespace need not be trusted to have exited: token revocation
        happens first. The launcher must still tear it down before starting new
        code. Full-host restart recovery is intentionally outside this contract.
        """
        require(operation in ("start-invocation", "retire-invocation", "stop"),
                "unknown_endpoint", "Unknown protected lifecycle operation", 404)
        record, duplicate = self.reserve(envelope, operation, "operator")
        if duplicate:
            return {"ok": True, "duplicate": True, **copy.deepcopy(record.get("transition", {})),
                    "command": copy.deepcopy(record)}
        try:
            require(not self.stopped, "stopped", "Supervisor is stopped")
            require(not self.stop_requested, "stopping", "Supervisor is already stopping")
            require(type(envelope.get("authority_epoch")) is int and envelope["authority_epoch"] == self.epoch,
                    "stale_authority", "Re-read protected status before a new lifecycle intention")
            invocation_id = envelope.get("invocation_id")
            if operation != "stop":
                require(isinstance(invocation_id, str) and RID.fullmatch(invocation_id),
                        "invalid_invocation", "Bounded invocation_id required", 400)
            if operation == "start-invocation":
                require(self.owner == "robot", "wrong_owner", "Wait for conventional activation")
                require(not self.invocation or self.invocation["state"] != "active",
                        "invocation_active", "Retire the previous invocation before starting another")
                require(not self.active_command and not self.adapter.busy(),
                        "resource_busy", "Cancellation must reach a terminal receipt before restart")
                require(not any(c["kind"] == "start-invocation" and c["status"] == "completed"
                                and c["envelope"].get("invocation_id") == invocation_id
                                for c in self.commands.values()),
                        "invocation_reused", "Each invocation identity may start only once")
                self.epoch += 1
                self.invocation_count += 1
                self.invocation = {"invocation_id": invocation_id, "state": "active",
                                   "authority_epoch": self.epoch, "started_sim_time_s": self.now}
            elif operation == "retire-invocation":
                require(self.invocation and self.invocation["invocation_id"] == invocation_id,
                        "wrong_invocation", "Cannot retire another invocation")
                require(self.invocation["state"] != "retired", "invocation_retired", "Invocation already retired")
                # After handback, conventional work is allowed to continue. A
                # late launcher finally block must not cancel its new command.
                if self.invocation["state"] == "active":
                    self.adapter.cancel("isolated invocation retired")
                    self.epoch += 1
                self.invocation.update(state="retired", ended_sim_time_s=self.now,
                                       reason=envelope.get("reason"))
            else:
                self.adapter.cancel("trusted operator requested episode stop")
                self.epoch += 1
                self.stop_requested = envelope.get("reason") or "operator_stop"
                if self.invocation:
                    self.invocation.update(state="retired", ended_sim_time_s=self.now)
            if self.activation:
                self.activation.update(authority_epoch=self.epoch,
                                       order_version=self.packet["order"]["version"],
                                       invocation=copy.deepcopy(self.invocation))
                atomic_json(self.journal.live / "activation.json", self.activation)
            transition = {"owner": self.owner, "authority_epoch": self.epoch,
                          "invocation": copy.deepcopy(self.invocation),
                          "active_command": self.active_command}
            record.update(phase="terminal", status="completed", terminal_sim_time_s=self.now,
                          transition=transition,
                          verification={"state": "lifecycle_transition",
                                        "scope": "Authority fencing only; physical outcome requires reconciliation"})
            self.emit("invocation_" + operation, {"request_id": record["request_id"], **transition})
            self.journal.registry(self.commands)
            self.publish()
            return {"ok": True, **copy.deepcopy(transition), "command": copy.deepcopy(record)}
        except GatewayError as error:
            return {"ok": True, "command": self.failed(record, error)}

    def housekeeping(self):
        for rid in list(self.fresh_requests):
            record = self.commands[rid]
            if self.now > record["deadline_sim_time_s"]:
                record.update(phase="terminal", status="expired", terminal_sim_time_s=self.now)
                self.fresh_requests.remove(rid)
                self.emit("observation_timeout", {"request_id": rid})
                self.journal.registry(self.commands)
        if self.active_command:
            record = self.commands[self.active_command]
            if self.now - record["requested_sim_time_s"] > 90.:
                self.adapter.cancel("maximum independent skill interval reached")
        if self.now >= self.publish_due:
            self.publish()
            self.publish_due = self.now + .5

    def status(self):
        packet = copy.deepcopy(self.packet)
        if packet:
            packet.update(sim_time=self.now, tcp_position_m=self.adapter.tcp_position(),
                          joints=self.adapter.joints())
        return {"ok": True, "schema": SCHEMA, "owner": self.owner, "authority_epoch": self.epoch,
                "order_version": packet["order"]["version"] if packet else None,
                "observation_sequence": packet["sequence"] if packet else None,
                "observation_age_s": self.now - packet["capture_sim_time_s"] if packet else None,
                "packet": packet, "active_command": self.active_command,
                "history_high_water": len(self.journal.events), "activation": self.activation,
                "invocation": copy.deepcopy(self.invocation), "invocation_count": self.invocation_count,
                "unresolved_commands": copy.deepcopy([r for r in self.commands.values()
                    if r["actor"] == "robot" and r["kind"] == "command"
                    and r["verification"]["state"] == "unknown"][-30:]),
                "commands_recent": copy.deepcopy(list(self.commands.values())[-10:]),
                "program_execution": {"dedicated_service": False, "namespace_shell_available": True,
                                      "authority": "same gateway limits",
                                      "qualification": "external revision evidence"},
                "robot_action_budget": {"used": self.robot_action_count, "limit": 20},
                "protection_scope": "native actuator/workspace/interlock bounds; no collision safety certificate",
                "stopped": self.stopped}

    def publish(self):
        self.journal.state(self.status())

    def request(self, method, path, body=None):
        body = body or {}
        if method == "GET" and path == "/status":
            return self.status()
        if method == "GET" and path == "/continuity":
            return self.journal.read_continuity()
        if method == "GET" and path.startswith("/observation/"):
            name = path[len("/observation/"):]
            require(re.fullmatch(r"overhead-[1-9][0-9]*\.png", name),
                    "invalid_image", "Only a named overhead PNG is supported", 400)
            image = self.journal.live / "observations" / name
            require(image.is_file() and not image.is_symlink(), "unknown_image", "No such retained public image", 404)
            require(image.stat().st_size <= 750000, "image_limit", "Image exceeds bounded transfer size", 413)
            raw = image.read_bytes()
            require(len(raw) <= 750000, "image_limit", "Image exceeds bounded transfer size", 413)
            return {"ok": True, "name": name, "media_type": "image/png", "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(), "base64": base64.b64encode(raw).decode("ascii")}
        if method == "GET" and path.startswith("/command/"):
            rid = path[len("/command/"):]
            require(rid in self.commands, "unknown_command", "No such request ID in this episode", 404)
            return {"ok": True, "command": copy.deepcopy(self.commands[rid])}
        if method == "GET" and path.startswith("/history"):
            from urllib.parse import urlsplit, parse_qs
            query = parse_qs(urlsplit(path).query)
            after = int(query.get("after", [0])[0]); limit = min(200, max(1, int(query.get("limit", [100])[0])))
            require(after >= 0, "invalid_cursor", "after must be nonnegative", 400)
            events = [e for e in self.journal.events if e["event_id"] > after][:limit]
            return {"ok": True, "events": copy.deepcopy(events), "high_water": len(self.journal.events), "gaps": [], "incomplete_tail": False}
        if method == "POST" and path == "/command":
            return self.command(body)
        if method == "POST" and path == "/observe":
            return self.observe(body)
        if method == "POST" and path == "/handback":
            return self.handback(body)
        if method == "POST" and path == "/restart-agent":
            raise GatewayError("operator_only", "Agent lifecycle changes require trusted operator orchestration after terminating the old launcher job", 403)
        if method == "POST" and path == "/continuity":
            result = self.journal.continuity(body.get("content"))
            self.emit("continuity_committed", result, "robot")
            return {"ok": True, **result}
        if path == "/run-program":
            raise GatewayError("programs_disabled", "Generated program execution is disabled pending isolation qualification", 403)
        raise GatewayError("unknown_endpoint", "Unknown endpoint", 404)
