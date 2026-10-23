"""Four fixed Windows loopback observations. Invoked only by the bounded launcher."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import os
from pathlib import Path
import socket
import struct
import sys
import time

HERE = Path(__file__).resolve().parent
H = HERE.parent.parent / "harness"
OUTPUT = HERE / "execution-001" / "child"
MANIFEST = HERE / "execution-001" / "source-manifest.json"
PAYLOAD = bytes(range(256)) * 16
CASES = ("peer_graceful_send_shutdown", "peer_abortive_close", "local_close_pending_receive", "explicit_receive_task_cancel")
OBSERVATION_S = 5.0
CLEANUP_S = 2.0
MAX_EVENT_BYTES = 512 * 1024
MAX_RESULT_BYTES = 128 * 1024
MAX_EVENTS = 256


class FixtureError(Exception):
    pass


class ObservationDeadline(Exception):
    pass


def sha(data):
    return hashlib.sha256(data).hexdigest()


def binding(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {"path": str(path), "sha256": sha(data), "bytes": len(data)}


def numeric_code(value):
    return value if type(value) is int and -(2 ** 31) <= value < 2 ** 31 else None


def error_metadata(error):
    # Exact finite classes; no dynamic class name, args, message or traceback.
    classes = {
        ConnectionAbortedError: "ConnectionAbortedError",
        ConnectionResetError: "ConnectionResetError",
        BrokenPipeError: "BrokenPipeError",
        ConnectionRefusedError: "ConnectionRefusedError",
        TimeoutError: "TimeoutError",
        OSError: "OSError",
        asyncio.CancelledError: "CancelledError",
        FixtureError: "FixtureError",
        ObservationDeadline: "ObservationDeadline",
    }
    return {"class": classes.get(type(error), "UnknownException"),
            "errno": numeric_code(getattr(error, "errno", None)),
            "winerror": numeric_code(getattr(error, "winerror", None))}


class Recorder:
    def __init__(self):
        self.path = OUTPUT / "events.jsonl"
        self.stream = self.path.open("xb")
        self.count = self.bytes = 0

    def emit(self, kind, **fields):
        value = {"schema": "campaign002-loopback-event-1", "sequence": self.count + 1,
                 "monotonic_s": time.monotonic(), "wall_unix_s": time.time(), "kind": kind, **fields}
        data = json.dumps(value, separators=(",", ":"), sort_keys=True).encode() + b"\n"
        if self.count >= MAX_EVENTS or self.bytes + len(data) > MAX_EVENT_BYTES:
            raise FixtureError()
        self.stream.write(data)
        self.stream.flush()
        self.count += 1
        self.bytes += len(data)
        return value["sequence"]

    def close(self):
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.stream.close()


def save_result(value):
    data = json.dumps(value, indent=2, sort_keys=True).encode() + b"\n"
    if len(data) > MAX_RESULT_BYTES:
        raise FixtureError()
    with (OUTPUT / "result.json").open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


async def run_case(index, name, bridge, recorder):
    start = time.monotonic()
    deadline = start + OBSERVATION_S
    sockets = []
    tasks = []
    read_task = None
    read_started = asyncio.Event()
    state = {"phase": "observation"}
    received = bytearray()
    fragment_hashes = []
    observation = {"kind": "unknown", "reason": "not_observed"}
    action_performed = False
    prefix_complete = False
    cleanup_complete = False
    action_sequence = None
    terminal_events = []
    recorder.emit("case_started", case=name, case_index=index, observation_bound_s=OBSERVATION_S)

    def own_socket():
        value = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sockets.append(value)
        value.setblocking(False)
        return value

    async def bounded(awaitable):
        task = asyncio.create_task(awaitable)
        tasks.append(task)
        done, _ = await asyncio.wait({task}, timeout=max(0.0, deadline - time.monotonic()))
        if not done:
            raise ObservationDeadline()
        return task.result()

    async def observe_pending(reader):
        read_started.set()
        recorder.emit("receive_entered", case=name, phase=state["phase"])
        try:
            data = await reader.read(4096)
            value = {"kind": "eof" if data == b"" else "data", "bytes": len(data), "sha256": sha(data)}
            if data:
                received.extend(data)
                fragment_hashes.append({"bytes": len(data), "sha256": sha(data)})
        except BaseException as error:
            value = {"kind": "cancelled" if isinstance(error, asyncio.CancelledError) else "error", "error": error_metadata(error)}
        value["phase"] = state["phase"]
        recorder.emit("receive_terminal", case=name, **value)
        terminal_events.append(value)
        return value

    try:
        loop = asyncio.get_running_loop()
        listener = own_socket()
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        peer = own_socket()
        await bounded(loop.sock_connect(peer, listener.getsockname()))
        local, _ = await bounded(loop.sock_accept(listener))
        sockets.append(local)
        local.setblocking(False)
        # Addresses and dynamically allocated port numbers are deliberately not retained.
        if (local.getpeername()[0] != "127.0.0.1" or peer.getpeername()[0] != "127.0.0.1"
                or local.getpeername() != peer.getsockname() or peer.getpeername() != local.getsockname()):
            raise FixtureError()
        listener.close()
        reader = bridge.SocketReader(local)
        local_writer = bridge.SocketWriter(local)
        peer_writer = bridge.SocketWriter(peer)
        peer_writer.write(PAYLOAD)
        await bounded(peer_writer.drain())
        recorder.emit("payload_send_completed", case=name, bytes=len(PAYLOAD), sha256=sha(PAYLOAD))
        while len(received) < len(PAYLOAD):
            data = await bounded(reader.read(len(PAYLOAD) - len(received)))
            recorder.emit("payload_fragment", case=name, bytes=len(data), sha256=sha(data))
            if not data:
                raise FixtureError()
            received.extend(data)
            fragment_hashes.append({"bytes": len(data), "sha256": sha(data)})
        prefix_complete = bytes(received) == PAYLOAD
        if not prefix_complete:
            raise FixtureError()
        read_task = asyncio.create_task(observe_pending(reader))
        tasks.append(read_task)
        await bounded(read_started.wait())
        # Allow the actual reader coroutine to enter its no-data overlapped await.
        # This is scheduling coordination, not a delay intended to change transport behavior.
        await asyncio.sleep(0)
        if read_task.done():
            raise FixtureError()
        recorder.emit("pending_receive_before_action", case=name, task_done=False, payload_complete=True)
        action_sequence = recorder.emit("synthetic_action_begin", case=name, action=name)
        if name == "peer_graceful_send_shutdown":
            peer.shutdown(socket.SHUT_WR)
        elif name == "peer_abortive_close":
            linger = struct.pack("HH", 1, 0)
            peer.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)
            observed_linger = peer.getsockopt(socket.SOL_SOCKET, socket.SO_LINGER, len(linger))
            if observed_linger != linger:
                raise FixtureError()
            recorder.emit("abortive_linger_confirmed", case=name, enabled=True, linger_seconds=0)
            peer_writer.close()
        elif name == "local_close_pending_receive":
            local_writer.close()
        elif name == "explicit_receive_task_cancel":
            cancelled = read_task.cancel()
            recorder.emit("explicit_cancel_requested", case=name, accepted=cancelled)
            if cancelled is not True:
                raise FixtureError()
        else:
            raise FixtureError()
        action_performed = True
        recorder.emit("synthetic_action_completed", case=name, action=name)
        done, _ = await asyncio.wait({read_task}, timeout=max(0.0, deadline - time.monotonic()))
        if done:
            observation = read_task.result()
        else:
            observation = {"kind": "timeout", "reason": "observation_deadline", "phase": "observation"}
            recorder.emit("observation_deadline", case=name, bound_s=OBSERVATION_S)
    except BaseException as error:
        observation = {"kind": "setup_or_action_error", "error": error_metadata(error), "phase": "observation"}
        recorder.emit("case_error", case=name, **observation)
    finally:
        observation_ended = time.monotonic()
        state["phase"] = "cleanup"
        cleanup_deadline = observation_ended + CLEANUP_S
        recorder.emit("cleanup_started", case=name, bound_s=CLEANUP_S)
        # Any cancellation below belongs to cleanup, never to the observation result.
        for task in tasks:
            if not task.done():
                recorder.emit("cleanup_task_cancel_requested", case=name, was_pending=True)
                task.cancel()
        for owned in sockets:
            owned.close()
        if tasks:
            done, pending = await asyncio.wait(set(tasks), timeout=max(0.0, cleanup_deadline - time.monotonic()))
            for task in done:
                if not task.cancelled():
                    # Retrieve every exception without rendering it.
                    task.exception()
            cleanup_complete = not pending and all(owned.fileno() == -1 for owned in sockets)
        else:
            cleanup_complete = all(owned.fileno() == -1 for owned in sockets)
        recorder.emit("cleanup_completed", case=name, all_tasks_done=all(task.done() for task in tasks),
                      all_owned_sockets_closed=all(owned.fileno() == -1 for owned in sockets), complete=cleanup_complete)

    observed_kind = observation["kind"]
    interpretation = "unknown"
    if prefix_complete and action_performed:
        if name == "peer_graceful_send_shutdown" and observed_kind == "eof":
            interpretation = "observed_graceful_payload_then_empty_read"
        elif name == "explicit_receive_task_cancel" and observed_kind == "cancelled":
            interpretation = "observed_explicit_task_cancellation"
        elif name in ("peer_abortive_close", "local_close_pending_receive") and observed_kind == "error":
            interpretation = "observed_error_after_declared_action"
    return {"case": name, "case_index": index, "action_performed": action_performed,
            "action_sequence": action_sequence, "observation": observation,
            "interpretation": interpretation, "clean_shutdown_claim": interpretation == "observed_graceful_payload_then_empty_read",
            "expected_payload": {"bytes": len(PAYLOAD), "sha256": sha(PAYLOAD)},
            "received": {"bytes": len(received), "sha256": sha(bytes(received)), "fragments": fragment_hashes},
            "payload_exact": prefix_complete, "receive_terminals": terminal_events,
            "observation_elapsed_s": observation_ended - start, "total_elapsed_s": time.monotonic() - start,
            "cleanup_complete": cleanup_complete}


async def matrix(bridge, recorder):
    loop = asyncio.get_running_loop()
    loop_kind = "ProactorEventLoop" if isinstance(loop, asyncio.ProactorEventLoop) else "OtherEventLoop"
    if loop_kind != "ProactorEventLoop":
        raise FixtureError()
    recorder.emit("matrix_started", platform="win32", loop_kind=loop_kind, cases=list(CASES))
    results = []
    for index, name in enumerate(CASES, 1):
        results.append(await run_case(index, name, bridge, recorder))
    return results, loop_kind


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if sys.platform != "win32" or Path(args.manifest).resolve() != MANIFEST or Path(args.output).resolve() != OUTPUT:
        return 2
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    OUTPUT.mkdir(exist_ok=False)
    recorder = Recorder()
    result = {"schema": "campaign002-windows-loopback-diagnostic-1", "diagnostic_only": True,
              "model_calls": 0, "native_app_server_started": False, "namespace_started": False,
              "qualification_evidence": False, "cases": [], "collection_complete": False,
              "source_manifest": binding(MANIFEST)}
    exit_code = 1
    try:
        if not all(binding(item["path"]) == item for item in manifest["sources"]):
            raise FixtureError()
        sys.path.insert(0, str(H))
        bridge = importlib.import_module("codehost_bridge_v3")
        if Path(bridge.__file__).resolve() != H / "codehost_bridge_v3.py":
            raise FixtureError()
        cases, loop_kind = asyncio.run(matrix(bridge, recorder))
        result.update(cases=cases, loop_kind=loop_kind, collection_complete=len(cases) == 4,
                      all_cleanup_complete=all(case["cleanup_complete"] for case in cases),
                      unknown_interpretations=sum(case["interpretation"] == "unknown" for case in cases))
        result["sources_unchanged"] = all(binding(item["path"]) == item for item in manifest["sources"])
        exit_code = 0 if result["collection_complete"] and result["all_cleanup_complete"] and result["sources_unchanged"] else 1
    except BaseException as error:
        result["collection_error"] = error_metadata(error)
        recorder.emit("matrix_error", error=error_metadata(error))
    finally:
        recorder.close()
        result["events"] = binding(recorder.path)
        result["native_exit_code"] = exit_code
        save_result(result)
    return exit_code


if __name__ == "__main__":
    # No arbitrary exception rendering, even on a launcher/source-contract failure.
    try:
        code = main()
    except BaseException:
        code = 2
    raise SystemExit(code)
