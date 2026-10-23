"""Queued native integration runner. This file never launches Robot-Codex."""
from __future__ import annotations
import argparse
import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import secrets
import sys
import threading
import time
import traceback
import uuid

from supervisor import Supervisor, Journal, GatewayError, atomic_json, canonical, MAX_BYTES, ATOMIC_REPLACE_RETRIES
from challenges import validate_manifest, source_binding, apply_initial_fixture, write_manifests

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
RUNTIME = EXPERIMENT / "Runtime 004"
RECORDER = EXPERIMENT / "Storage Retention Implementation 001" / "future"


class Mail:
    def __init__(self, method, path, body, authenticated_epoch, scope="robot"):
        self.method, self.path, self.body = method, path, body
        # Authentication happened on the HTTP thread; authority may change
        # before the physics thread reaches this request (including note writes).
        self.authenticated_epoch = authenticated_epoch
        self.scope = scope
        self.result = queue.Queue(maxsize=1)


class HttpGateway:
    """Loopback only, bounded JSON, capability required even for status reads."""
    def __init__(self, workspace, protected_root=None):
        self.requests = queue.Queue(maxsize=32)
        # Tuple replacement is atomic: a request must not combine an old token
        # with a newly assigned epoch during a concurrent rotation.
        self.credentials = (None, secrets.token_urlsafe(32))
        self.workspace = Path(workspace)
        self.protected_root = Path(protected_root) if protected_root is not None else None
        self.operator_capability = secrets.token_urlsafe(32) if self.protected_root is not None else None
        self.robot_enabled = self.protected_root is None
        self._published_endpoint = None
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass  # Never copy capabilities into console/access logs.

            def do_GET(self):
                self.handle_request("GET")

            def do_POST(self):
                self.handle_request("POST")

            def handle_request(self, method):
                status, response = 200, None
                try:
                    self.connection.settimeout(5.)
                    authenticated_epoch, capability = owner.credentials
                    scope = "operator" if self.path.startswith("/operator/") else "robot"
                    if scope == "operator":
                        capability = owner.operator_capability
                        received = self.headers.get("X-Robot-Operator-Capability", "")
                    else:
                        received = self.headers.get("X-Robot-Capability", "")
                    if (self.client_address[0] != "127.0.0.1" or not capability or
                            (scope == "robot" and not owner.robot_enabled) or
                            not secrets.compare_digest(received, capability)):
                        raise GatewayError("unauthorized", "Missing or invalid local robot capability", 403)
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 <= length <= 65536:
                        raise GatewayError("body_limit", "Body must be at most 65536 bytes", 413)
                    if self.headers.get("Transfer-Encoding"):
                        raise GatewayError("body_format", "Chunked requests are unsupported", 400)
                    body = json.loads(self.rfile.read(length)) if length else {}
                    if not isinstance(body, dict):
                        raise GatewayError("body_format", "JSON object required", 400)
                    mail = Mail(method, self.path, body, authenticated_epoch, scope)
                    owner.requests.put_nowait(mail)
                    try:
                        status, response = mail.result.get(timeout=5.)
                    except queue.Empty:
                        raise GatewayError("reply_timeout", "Receipt unknown; query the same request ID before any new action", 504)
                except GatewayError as error:
                    status, response = error.status, {"ok": False, "error": {"code": error.code, "message": str(error)}}
                except (ValueError, UnicodeError):
                    status, response = 400, {"ok": False, "error": {"code": "invalid_json", "message": "Invalid bounded JSON request"}}
                except queue.Full:
                    status, response = 429, {"ok": False, "error": {"code": "queue_full", "message": "Host request queue is full"}}
                raw = canonical(response)
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError, TimeoutError):
                    pass  # Lost reply does not undo or repeat the command.

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True, name="robot-local-http")

    @property
    def epoch(self):
        return self.credentials[0]

    @property
    def capability(self):
        return self.credentials[1]

    def rotate(self, epoch):
        if epoch != self.epoch:
            self.credentials = (epoch, secrets.token_urlsafe(32))
        publication = (epoch, self.robot_enabled)
        if publication != self._published_endpoint:
            value = {"schema": "robot-codex-host-1.0", "authority_epoch": epoch}
            if self.robot_enabled:
                value.update(url="http://127.0.0.1:" + str(self.server.server_port), capability=self.capability)
            else:
                value["retired"] = True
            atomic_json(self.workspace / "live" / "endpoint.json", value)
            self._published_endpoint = publication

    def start(self):
        if self.protected_root is not None:
            atomic_json(self.protected_root / "operator-endpoint.json",
                        {"schema": "robot-codex-operator-1.0",
                         "url": "http://127.0.0.1:" + str(self.server.server_port),
                         "capability": self.operator_capability})
        self.thread.start()

    def synchronize(self, supervisor):
        self.robot_enabled = (self.protected_root is None or
                              bool(supervisor.invocation and supervisor.invocation["state"] == "active"))
        self.rotate(supervisor.epoch)

    def operator_request(self, supervisor, mail):
        require_path = mail.path.removeprefix("/operator/")
        if mail.method == "GET" and require_path == "status":
            return supervisor.status()
        if mail.method == "GET" and require_path.startswith("command/"):
            return supervisor.request("GET", "/" + require_path)
        if mail.method == "GET" and require_path == "continuity":
            return supervisor.journal.read_continuity()
        if mail.method == "POST" and require_path in ("start-invocation", "retire-invocation", "stop"):
            result = supervisor.lifecycle(require_path, mail.body)
            self.synchronize(supervisor)
            # A retry of a historical start must never yield a later token.
            if (require_path == "start-invocation" and result["command"]["status"] == "completed"
                    and supervisor.invocation and supervisor.invocation["state"] == "active"
                    and supervisor.invocation["invocation_id"] == mail.body.get("invocation_id")
                    and result.get("authority_epoch") == supervisor.epoch):
                result["endpoint"] = {"schema": "robot-codex-host-1.0",
                                      "url": "http://127.0.0.1:" + str(self.server.server_port),
                                      "capability": self.capability, "authority_epoch": self.epoch}
            return result
        raise GatewayError("unknown_endpoint", "Unknown protected operator endpoint", 404)

    def process(self, supervisor):
        for _ in range(4):
            try:
                mail = self.requests.get_nowait()
            except queue.Empty:
                break
            try:
                # Every endpoint is fenced, including continuity and reads.
                # Enqueue-time authentication alone cannot authorize a delayed
                # write after an earlier queued restart or handback completed.
                self.synchronize(supervisor)
                if mail.scope == "operator":
                    if self.protected_root is None:
                        raise GatewayError("operator_disabled", "Protected operator interface is not enabled", 403)
                    result = self.operator_request(supervisor, mail)
                else:
                    if type(mail.authenticated_epoch) is not int or mail.authenticated_epoch != supervisor.epoch:
                        raise GatewayError("stale_authentication", "Request was authenticated before the current authority generation", 409)
                    if not self.robot_enabled:
                        raise GatewayError("invocation_retired", "Robot invocation no longer owns a gateway capability", 403)
                    result = supervisor.request(mail.method, mail.path, mail.body)
                self.synchronize(supervisor)
                mail.result.put_nowait((200, result))
            except GatewayError as error:
                mail.result.put_nowait((error.status, {"ok": False, "error": {"code": error.code, "message": str(error)}}))
            except (ValueError, KeyError, TypeError):
                mail.result.put_nowait((400, {"ok": False, "error": {"code": "invalid_request", "message": "Malformed request"}}))
        self.synchronize(supervisor)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        # A saved stopped workspace is inspectable but carries no live capability.
        path = self.workspace / "live" / "endpoint.json"
        if path.exists():
            atomic_json(path, {"schema": "robot-codex-host-1.0", "stopped": True})
        if self.protected_root is not None:
            atomic_json(self.protected_root / "operator-endpoint.json",
                        {"schema": "robot-codex-operator-1.0", "stopped": True})


class PhysicalAdapter:
    """Only this protected host imports simulator classes and evaluator truth."""
    def __init__(self, manifest, evidence, workspace, public_id):
        sys.path.insert(0, str(RUNTIME))
        sys.path.insert(0, str(RECORDER))
        from cell import Cell
        from candidates import Candidate
        from runtime_adapter import FutureEvidence, LiveSensorBridge
        from recorder import ImagePolicy
        self.manifest, self.workspace, self.public_id = manifest, Path(workspace), public_id
        self.source_hashes = source_binding(RUNTIME)
        self.recorder_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                               for path in RECORDER.glob("*.py")}
        expected_recorder = manifest.get("recorder_source_sha256")
        if expected_recorder is not None and expected_recorder != self.recorder_hashes:
            raise ValueError("Recorder source differs from registered manifest")
        self.cell = Cell(manifest["operator_only_fixture"]["part_count"], manifest["seed"], noise_seed=manifest["noise_seed"])
        apply_initial_fixture(self.cell, manifest)
        # All manipulated object qpos belongs to declared initial state, never recovery.
        for _ in range(500):
            self.cell.tick()
        self.initial_sim = self.now
        self.cell.prepare_sensor()
        self.cell.sense()
        self.recording = FutureEvidence(Path(evidence) / "native-recording", manifest["run_id"],
                                       policy=ImagePolicy(sparse_period_s=2., image_quota_bytes=12_000_000),
                                       core_quota_bytes=50_000_000)
        self.bridge = LiveSensorBridge(self.recording)
        self.baseline = Candidate("baseline", Path(evidence) / "baseline-workspace", True)
        self.order = copy.deepcopy(manifest["operator_only_fixture"]["order"])
        self.cell._eval_order = self.order
        self.cell._acceptance_open = True
        self.sequence = 0
        self.capture = 0
        self.feedback_cursor = 0
        self.events_cursor = 0
        self.next_camera = self.now
        self.next_image = self.now
        self.physics_ticks = 0
        self.save_requested_image = False
        self.explicit_images = 0
        self.force_observe = False
        self.captured_count = 0

    @property
    def now(self):
        return float(self.cell.data.time)

    def tcp_position(self):
        return self.cell.data.site_xpos[self.cell.tcp].tolist()

    def joints(self):
        return self.cell.data.qpos[:7].tolist()

    def busy(self):
        return self.cell.active_request is not None or self.cell._planning_busy()

    def submit(self, action):
        return self.cell.submit(action)

    def cancel(self, reason):
        self.cell.cancel(reason)

    def request_observation(self):
        self.force_observe = True
        self.save_requested_image = True

    def packet(self, epoch):
        packet = self.cell.public_packet(self.order, self.public_id, epoch, self.sequence)
        packet.update(arm=self.cell.public_arm_interfaces(), tcp_position_m=self.tcp_position(), restart_generation=0)
        return packet

    def step(self, supervisor, wall):
        # Supervisor renews only already accepted bounded skill execution. Direct
        # commands retain their original <=2 s horizon regardless of renewal.
        self.cell.renew_authority(self.order["version"], supervisor.epoch)
        self.cell.tick()
        self.physics_ticks += 1
        if self.physics_ticks % 5 == 0:
            self.recording.motion.write(json.dumps({"sim_time_s": self.now, "q": self.joints(),
                "dq": self.cell.data.qvel[:7].tolist(), "tcp": self.tcp_position(),
                "effort": self.cell.data.actuator_force[:7].tolist(),
                "gripper_width_m": float(sum(self.cell.data.qpos[7:9])),
                "target": self.cell.data.ctrl[:7].tolist()}, separators=(",", ":")) + "\n")
        captured = self.cell.poll_sense()
        if captured is not None:
            self.sequence += 1
            self.captured_count += 1
            self.cell.resume_setup_if_fresh()
            self.bridge.observe(captured)  # Existing recorder ring decides sparse persistence.
            if self.save_requested_image and self.explicit_images < 50:
                from png import write_png
                path = self.workspace / "live" / "observations" / ("overhead-" + str(self.sequence) + ".png")
                path.parent.mkdir(parents=True, exist_ok=True)
                write_png(path, captured.rgb)
                image_ref = {"path": "live/observations/" + path.name, "bytes": path.stat().st_size,
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "camera": "overhead",
                             "capture_sim_time_s": captured.capture_sim_time_s, "observation_sequence": self.sequence}
                supervisor.journal.bytes += path.stat().st_size
                supervisor.emit("requested_image_available", image_ref)
                self.explicit_images += 1
                self.save_requested_image = False
            supervisor.update_observation(self.packet(supervisor.epoch))
        for feedback in self.cell.feedback[self.feedback_cursor:]:
            supervisor.native_feedback(feedback)
        self.feedback_cursor = len(self.cell.feedback)
        for event in self.cell.events[self.events_cursor:]:
            supervisor.native_event(event)
        self.events_cursor = len(self.cell.events)
        if self.now >= self.next_camera or self.force_observe:
            if not self.cell.sensor_worker.busy:
                self.capture += 1
                self.cell.request_sense(sequence=self.capture, capture_wall_elapsed_s=wall, rgb_path=None, depth_path=None)
                self.force_observe = False
                self.next_camera = self.now + .1
        # Public device/timer state advances between image acquisitions.
        if supervisor.packet:
            supervisor.packet = self.packet(supervisor.epoch)

    def outcome(self):
        return self.cell.outcome(self.order, acceptance_open=True)

    def close(self):
        self.cell.close()
        self.recording.close()


def run(manifest_path, evidence, workspace):
    manifest_path, evidence, workspace = Path(manifest_path), Path(evidence), Path(workspace)
    manifest = validate_manifest(json.loads(manifest_path.read_text(encoding="utf-8")))
    evidence.mkdir(parents=True, exist_ok=False)
    workspace.mkdir(parents=True, exist_ok=True)
    atomic_json(evidence / "manifest.json", manifest)
    public_id = "episode-" + uuid.uuid4().hex[:16]
    adapter = None; gateway = None; supervisor = None
    terminal = "not_started"; outcome = None; error = None
    timing = {"maximum_wall_minus_sim_s": 0., "samples": 0}
    started = time.monotonic()
    try:
        adapter = PhysicalAdapter(manifest, evidence, workspace, public_id)
        atomic_json(evidence / "frozen-source-verification.json", adapter.source_hashes)
        atomic_json(evidence / "recorder-source-verification.json", adapter.recorder_hashes)
        journal = Journal(evidence, workspace, public_id, limit=manifest["storage_cap_bytes"] - 65_000_000)
        supervisor = Supervisor(adapter, adapter.baseline, journal)
        supervisor.update_observation(adapter.packet(supervisor.epoch))
        supervisor.emit("episode_started", {"stage": "development-only", "order": adapter.order,
                                             "clock": "wall-paced live physics; no pause while reasoning"})
        supervisor.publish()
        if manifest["mode"] == "serve":
            supervisor.lifecycle_required = True
            gateway = HttpGateway(workspace, evidence); gateway.synchronize(supervisor); gateway.start()
        reference_index = 0; reference_pending = None; handed_back = False
        reference = manifest["operator_only_fixture"]["reference_actions"]
        start = time.monotonic(); next_decision = adapter.now
        total_size_due = adapter.now + 5.
        while adapter.now - adapter.initial_sim < manifest["sim_cap_s"]:
            wall = time.monotonic() - start
            if wall > manifest["wall_cap_s"]:
                terminal = "wall_time_cap"; break
            if gateway:
                gateway.process(supervisor)
            adapter.step(supervisor, wall)
            supervisor.housekeeping()
            if supervisor.stop_requested:
                terminal = "operator_stop"; break
            if adapter.now >= next_decision and supervisor.packet and adapter.now - supervisor.packet["capture_sim_time_s"] <= .35:
                supervisor.conventional_step()
                next_decision = adapter.now + .2
            if supervisor.owner == "robot":
                if manifest["mode"] == "baseline":
                    terminal = "baseline_requested_assistance"; break
                if manifest["mode"] == "reference":
                    if reference_pending:
                        record = supervisor.commands[reference_pending]
                        if record["phase"] == "terminal":
                            if record["status"] != "completed":
                                terminal = "reference_action_failed"; break
                            if record["verification"]["state"] == "public_observation_support":
                                reference_index += 1; reference_pending = None
                    elif reference_index < len(reference) and not adapter.busy() and adapter.now - supervisor.packet["capture_sim_time_s"] <= .30:
                        rid = "reference-action-" + str(reference_index + 1)
                        supervisor.command(supervisor.envelope(rid, reference[reference_index]))
                        reference_pending = rid
                    elif reference_index >= len(reference) and not handed_back and adapter.now - supervisor.packet["capture_sim_time_s"] <= .30:
                        result = supervisor.handback({**supervisor.envelope("reference-handback"), "reason": "Observed recovery actions complete"})
                        if result.get("command", {}).get("status") != "completed":
                            terminal = "reference_handback_rejected"; break
                        handed_back = True
            outcome = adapter.outcome()
            if outcome["success"]:
                terminal = "task_success"; break
            sim_elapsed = adapter.now - adapter.initial_sim
            lag = time.monotonic() - start - sim_elapsed
            timing["maximum_wall_minus_sim_s"] = max(timing["maximum_wall_minus_sim_s"], lag)
            timing["samples"] += 1
            if adapter.now >= total_size_due:
                total_bytes = sum(p.stat().st_size for p in evidence.rglob("*") if p.is_file()) + sum(p.stat().st_size for p in (workspace / "live").rglob("*") if p.is_file())
                if total_bytes > manifest["storage_cap_bytes"]:
                    terminal = "storage_cap"; break
                total_size_due = adapter.now + 5.
            delay = start + sim_elapsed - time.monotonic()
            if delay > 0:
                time.sleep(min(delay, .002))
        else:
            terminal = "simulation_time_cap"
        adapter.cancel("development episode terminal: " + terminal)
        # Cancellation feedback remains public and retained even at the boundary.
        for feedback in adapter.cell.feedback[adapter.feedback_cursor:]:
            supervisor.native_feedback(feedback)
        outcome = adapter.outcome()
        supervisor.stopped = True
        supervisor.emit("episode_stopped", {"reason": terminal})
        supervisor.publish()
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
        terminal = "infrastructure_error"
        if adapter:
            adapter.cancel("host exception; authority revoked")
        if supervisor:
            supervisor.stopped = True
            try:
                supervisor.emit("host_failed", {"type": type(exc).__name__, "reason": "Protected host error; outcome uncertain"})
                supervisor.publish()
            except Exception:
                pass
    finally:
        if gateway:
            gateway.close()
        if adapter:
            adapter.close()
    result = {"schema": "robot-codex-development-result-1.0", "stage": "development-only",
              "run_id": manifest["run_id"], "public_episode_id": public_id, "mode": manifest["mode"],
              "terminal": terminal, "execution_completed": error is None,
              "independent_outcome": outcome, "error": error, "timing": timing,
              "wall_elapsed_s": time.monotonic() - started,
              "atomic_replace_retry": dict(ATOMIC_REPLACE_RETRIES),
              "sim_elapsed_s": adapter.now - adapter.initial_sim if adapter else None,
              "baseline_help_observed": bool(supervisor and supervisor.activation),
              "handbacks": supervisor.handoffs if supervisor else 0,
              "robot_invocations": supervisor.invocation_count if supervisor else 0,
              "reference_recovery": manifest["mode"] == "reference",
              "limits": ["Code-path/reference development evidence only", "No Robot-Codex inference invoked by host",
                         "No claims of real-time equivalence; observed clock lag retained", "No whole-arm collision protection",
                         "No complete supervisor/computer restart recovery", "Native recorder sparse images; all public action/observation events retained"]}
    atomic_json(evidence / "result.json", result)
    print(json.dumps({key: result[key] for key in ("run_id", "terminal", "execution_completed", "handbacks")}))
    return 1 if error else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--runtime-workspace", type=Path)
    parser.add_argument("--write-manifests", type=Path)
    args = parser.parse_args()
    if args.write_manifests:
        print(json.dumps(write_manifests(args.write_manifests), indent=2)); return 0
    if not all((args.manifest, args.evidence, args.runtime_workspace)):
        parser.error("--manifest, --evidence and --runtime-workspace are required")
    return run(args.manifest, args.evidence, args.runtime_workspace)


if __name__ == "__main__":
    raise SystemExit(main())
