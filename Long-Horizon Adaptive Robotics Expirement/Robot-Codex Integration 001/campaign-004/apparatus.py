"""Prospective Campaign 002 native host; immutable Campaign 001 dependencies."""
from __future__ import annotations
import native_environment
import argparse
import copy
from contextlib import nullcontext
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import secrets
import shutil
import sys
import threading
import time
import traceback
import uuid

HERE = Path(__file__).resolve().parent
ORIGINAL_HOST = HERE.parent / "host"
sys.path.insert(0,str(HERE.parent / "campaign-002/harness"))
sys.path.insert(0, str(ORIGINAL_HOST))
from supervisor import GatewayError, atomic_json, canonical, MAX_BYTES, ATOMIC_REPLACE_RETRIES
from challenges import source_binding, apply_initial_fixture, write_manifests
from supervisor_c import Supervisor
from gateway_c import extend_gateway, validate_manifest
from timing import TimingCapture, WindowsScheduling, load_monitor, qpc_clock_context
from journal_c import Journal as InstrumentedJournal
from gc_diagnostics import GcDiagnostics
from memory_guard import MemoryGuard
from runtime_limits import encounter_stop

EXPERIMENT = HERE.parent.parent
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


HttpGateway = extend_gateway(HttpGateway)


def conventional_decision(supervisor, next_decision, capture):
    """Wait for supervisor retirement even when independent physics is idle."""
    adapter = supervisor.adapter
    if supervisor.packet and supervisor.packet['capture_sim_time_s']<=getattr(adapter,'order_capture_boundary',float('-inf')):
        return next_decision
    # Campaign 002 terminated its host at task completion. A persistent block
    # instead holds a completed job until the protected scheduler releases the
    # next one; repeated done requests must not race the stage boundary.
    if any(c['actor']=='conventional' and c['envelope']['order_version']==adapter.order['version']
           and c.get('native_action',{}).get('operation')=='done' and c.get('status')=='completed'
           for c in supervisor.commands.values()):return next_decision
    if (not supervisor.active_command and adapter.now >= next_decision and supervisor.packet
            and supervisor.packet["order"]["version"]==adapter.order["version"]
            and adapter.now - supervisor.packet["capture_sim_time_s"] <= .35):
        with capture.phase("conventional_decision", lambda: adapter.now):
            supervisor.conventional_step()
        return adapter.now + .2
    return next_decision


def run(manifest_path, evidence, workspace):
    manifest_path, evidence, workspace = Path(manifest_path), Path(evidence), Path(workspace)
    manifest = validate_manifest(json.loads(manifest_path.read_text(encoding="utf-8")))
    evidence.mkdir(parents=True, exist_ok=False)
    workspace.mkdir(parents=True, exist_ok=True)
    atomic_json(evidence / "manifest.json", manifest)
    public_id = manifest["run_id"]
    adapter = None; gateway = None; supervisor = None; capture = None; timing_v2 = None; gc_diagnostics = None; memory = None
    supervisory_capture = None
    terminal = "not_started"; outcome = None; error = None
    timing = {"maximum_wall_minus_sim_s": 0., "samples": 0}
    scheduling = WindowsScheduling()
    started = time.perf_counter()
    try:
        if not scheduling.apply()["applied"]:
            raise RuntimeError("Prospective Windows scheduling setup failed: " + str(scheduling.receipt))
        memory = MemoryGuard(manifest['wall_cap_s'])
        memory.apply()
        from adapter import Adapter as ContinuousAdapter
        adapter = ContinuousAdapter(manifest, evidence, workspace, public_id)
        atomic_json(evidence / "frozen-source-verification.json", adapter.source_hashes)
        atomic_json(evidence / "recorder-source-verification.json", adapter.recorder_hashes)
        journal = InstrumentedJournal(evidence, workspace, public_id, limit=manifest["storage_cap_bytes"] - (manifest.get('native_core_cap_bytes',50_000_000)+3_000_000+12_000_000*manifest['encounters']))
        supervisor = Supervisor(adapter, adapter.baseline, journal)
        adapter.supervisor = supervisor
        supervisor.update_observation(adapter.packet(supervisor.epoch))
        supervisor.emit("episode_started", {"stage": manifest.get('stage','development-only'), "order": adapter.order,
                                             "clock": "wall-paced live physics; no pause while reasoning"})
        supervisor.publish()
        if manifest["mode"] == "serve":
            supervisor.lifecycle_required = True
            gateway = HttpGateway(workspace, evidence, manifest=manifest); gateway.synchronize(supervisor); gateway.start()
        reference_index = 0; reference_pending = None; handed_back = False
        reference = []
        # Load monitor source and resolve clock metadata during initialization.
        timing_monitor = load_monitor()
        gc_diagnostics = GcDiagnostics(lambda: capture.active_phase if capture is not None else None,
                                       lambda: adapter.now)
        gc_diagnostics.attach()
        clock_context = qpc_clock_context()
        clock_context['journal_origin_monotonic_s'] = journal.start
        clock_info = clock_context['primary_clock']
        memory.admit()
        gc_diagnostics.defer()
        start = time.perf_counter(); next_decision = adapter.now
        capture = TimingCapture(start, adapter.initial_sim,
            max_samples=2 * int(manifest["sim_cap_s"] / .002) + 16,
            monitor_bundle=timing_monitor, clock_info=clock_info, clock_context=clock_context)
        sim_clock = lambda: adapter.now
        supervisory_capture = TimingCapture(start, adapter.initial_sim, max_samples=4,
            monitor_bundle=timing_monitor, clock_info=clock_info, clock_context=clock_context)
        adapter.timing_capture = supervisory_capture
        journal.capture, journal.sim_clock = supervisory_capture, sim_clock
        adapter.worker.start(capture, memory, gc_diagnostics)
        total_size_due = adapter.now + 5.
        while adapter.now - adapter.initial_sim < manifest["sim_cap_s"]:
            # The owner samples complete physical time while this thread keeps
            # synchronous evidence ordering and durability.
            adapter.worker.heartbeat()
            if adapter.worker.terminal is not None:
                terminal = adapter.worker.terminal
                break
            wall = time.perf_counter() - start
            if wall > manifest["wall_cap_s"]:
                terminal = "wall_time_cap"; break
            if gateway:
                with supervisory_capture.phase("gateway", sim_clock):
                    gateway.process(supervisor)
            with supervisory_capture.phase("adapter_step", sim_clock):
                adapter.step(supervisor, wall)
            if adapter.worker.terminal is not None:
                terminal = adapter.worker.terminal
                break
            with supervisory_capture.phase("housekeeping", sim_clock):
                supervisor.housekeeping()
            if supervisor.stop_requested:
                terminal = "operator_stop"; break
            encounter_terminal=encounter_stop(manifest,supervisor.invocation,adapter.now,time.perf_counter(),supervisor.invocation_wall_started)
            if encounter_terminal:
                terminal=encounter_terminal;break
            next_decision = conventional_decision(supervisor, next_decision, supervisory_capture)
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
            with supervisory_capture.phase("evaluator", sim_clock):
                outcome = adapter.outcome()
            # Whole-block completion is decided by the protected scheduler,
            # after handback, resumption, retirement and terminal append. 
            sim_elapsed = adapter.now - adapter.initial_sim
            if adapter.now >= total_size_due:
                if shutil.disk_usage(evidence).free<102*1024**3:
                    terminal='native_free_reserve';break
                with supervisory_capture.phase("storage_census", sim_clock):
                    # Reserve the entire bounded timing ledger and metadata in
                    # the existing quota before its post-interval publication.
                    total_bytes = (sum(p.stat().st_size for p in evidence.rglob("*") if p.is_file())
                        + sum(p.stat().st_size for p in (workspace / "live").rglob("*") if p.is_file())
                        + capture.max_samples * 16 + 2_000_000 + gc_diagnostics.reserved_bytes + memory.reserved_bytes)
                if total_bytes > manifest["storage_cap_bytes"]:
                    terminal = "storage_cap"; break
                total_size_due = adapter.now + 5.
            with supervisory_capture.phase("supervisory_yield", sim_clock):
                time.sleep(.002)
        else:
            terminal = "simulation_time_cap"
        # This final sample includes terminal evaluator/control work while
        # cancellation, file publication and process cleanup are separate.
        adapter.worker.stop(terminal)
        terminal = adapter.worker.terminal
        if adapter.worker.error:
            raise RuntimeError('Physics owner failure: ' + str(adapter.worker.error))
        supervisory_capture.finish(adapter.now, terminal)
        if not gc_diagnostics.restore():
            raise RuntimeError('GC restoration failed: ' + str(gc_diagnostics.error))
        # Retain cancellation feedback and every pending captured record.
        # Failed drain/finalization is an infrastructure error, never success.
        adapter.step(supervisor, time.perf_counter()-start, final=True)
        outcome = adapter.outcome()
        supervisor.stopped = True
        supervisor.emit("episode_stopped", {"reason": terminal})
        supervisor.publish()
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
        terminal = "infrastructure_error"
        if adapter is not None:
            try:
                adapter.worker.stop(terminal)
            except Exception as worker_error:
                error['worker_finalization'] = str(worker_error)
        if capture is not None and capture.terminal is None and (adapter is None or adapter.worker.finished):
            try:
                if memory is not None and not memory.finished:
                    try:
                        memory.finish()
                    except Exception as memory_error:
                        error['memory_finalization'] = str(memory_error)
                capture.finish(adapter.now, terminal)
            except Exception as timing_error:
                error["timing_finalization"] = str(timing_error)
        elif capture is not None and capture.terminal is None:
            error['timing_finalization'] = 'Owner did not stop; terminal timing and memory remain incomplete, not finalized concurrently'
        if gc_diagnostics is not None:
            gc_diagnostics.restore()
        if supervisory_capture is not None and supervisory_capture.terminal is None:
            supervisory_capture.finish(adapter.now, terminal)
        if supervisor:
            supervisor.stopped = True
            try:
                supervisor.emit("host_failed", {"type": type(exc).__name__, "reason": "Protected host error; outcome uncertain"})
                supervisor.publish()
            except Exception:
                pass
    finally:
        cleanup = []
        if gc_diagnostics is not None:
            cleanup.append(('gc_restore', gc_diagnostics.restore))
        if gateway is not None:
            cleanup.append(('gateway_close', gateway.close))
        if adapter is not None:
            cleanup.append(('adapter_close', adapter.close))
        if gc_diagnostics is not None:
            cleanup.append(('gc_detach', gc_diagnostics.detach))
        if memory is not None:
            cleanup.append(('memory_close', memory.close))
        cleanup.append(('scheduling_restore', scheduling.restore))
        for name, operation in cleanup:
            try:
                operation()
            except Exception as cleanup_error:
                terminal = 'infrastructure_error'
                error = error or {'type': 'CleanupFailure', 'message': 'Protected terminal cleanup failed'}
                error.setdefault('cleanup', {})[name] = str(cleanup_error)
    resource_errors = [value for value in (gc_diagnostics.error if gc_diagnostics else None,
                                           memory.error if memory else None) if value]
    if resource_errors:
        terminal = 'infrastructure_error'
        error = error or {'type': 'ResourcePolicyFailure', 'message': '; '.join(resource_errors)}
        error['resource_policy'] = resource_errors
    if capture is not None and capture.terminal is not None:
        try:
            if gc_diagnostics is not None:
                capture.garbage_collection = gc_diagnostics.persist(evidence, capture.origin, capture.sim_origin, capture.terminal)
            if memory is not None:
                capture.host_memory = memory.persist(evidence, capture.terminal)
            timing_v2 = capture.persist(evidence, scheduling.receipt)
            if supervisory_capture is not None and supervisory_capture.terminal is not None:
                supervisory_root = evidence / 'supervisory-diagnostics'
                supervisory_root.mkdir()
                supervisory_capture.persist(supervisory_root, scheduling.receipt)
            timing = {"maximum_wall_minus_sim_s": capture.monitor.maximum_lag, "samples": capture.sample_count}
            if ((capture.garbage_collection is not None and capture.garbage_collection.get('passed') is not True)
                    or (capture.host_memory is not None and capture.host_memory.get('passed') is not True)):
                terminal = 'infrastructure_error'
                error = error or {'type': 'ResourceEvidenceFailure', 'message': 'GC or native memory evidence is incomplete or invalid'}
        except Exception as timing_error:
            terminal = "infrastructure_error"
            error = error or {"type": "TimingEvidenceFailure", "message": str(timing_error)}
            error["timing_publication"] = str(timing_error)
    result = {"schema": "robot-codex-development-result-1.0", "stage": manifest.get('stage','development-only'),
              "run_id": manifest["run_id"], "public_episode_id": public_id, "mode": manifest["mode"],
              "terminal": terminal, "execution_completed": error is None,
              "independent_outcome": outcome, "error": error, "timing": timing,
              "timing_v2": timing_v2, "scheduling": scheduling.receipt,
              'native_memory_job': memory.receipt if memory else None,
              'continuous_physics': {'schema': 'rci-continuous-physics-1',
                                     'terminal': adapter.worker.terminal, 'error': adapter.worker.error,
                                     'owner_finished': adapter.worker.finished,
                                     'queue_count': adapter.worker.queue_count, 'queue_bytes': adapter.worker.queue_bytes,
                                     'rpc_count': adapter.worker.rpc_count,
                                     'heartbeat_timeout_s': adapter.worker.heartbeat_timeout,
                                     'metrics': adapter.worker.metrics} if adapter else None,
              "wall_elapsed_s": time.perf_counter() - started,
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
