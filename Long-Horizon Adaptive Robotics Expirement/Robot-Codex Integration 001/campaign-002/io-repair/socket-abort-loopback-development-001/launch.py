"""Single-use, hidden-child Windows loopback launcher. No execution on import."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent.parent
H = CAMPAIGN / "harness"
RUN = HERE / "execution-001"
METHOD = HERE.parent / "SOCKET_ABORT_DIAGNOSTICS_V1.md"
METHOD_SHA = "ec46e6212cfc9b2844fd45715014a1a96b749d3764a2031fe4eec6d6076109d8"
CHILD_WORK_BOUND_S = 35.0
OUTER_BOUND_S = 40.0
STDIO_BOUND = 64 * 1024  # Per stream; arbitrary bytes are hashed and discarded.


def binding(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def save(name, value):
    raw = json.dumps(value, sort_keys=True, indent=2).encode() + b"\n"
    if len(raw) > 128 * 1024:
        raise ValueError()
    with (RUN / name).open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def unchanged_sources(sources):
    try:
        return all(binding(item["path"]) == item for item in sources)
    except BaseException:
        return False


class StdioDigest:
    """Retain no arbitrary text, messages, arguments, payloads or tracebacks."""
    def __init__(self, stream, child):
        self.stream, self.child = stream, child
        self.bytes = 0
        self.digest = hashlib.sha256()
        self.over_limit = self.read_error = False
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        try:
            while True:
                chunk = self.stream.read(4096)
                if not chunk:
                    break
                self.bytes += len(chunk)
                self.digest.update(chunk)
                if self.bytes > STDIO_BOUND:
                    self.over_limit = True
                    self.child.kill()  # Only this launcher's owned child.
                    break
        except BaseException:
            self.read_error = True

    def summary(self):
        return {"bytes_observed": self.bytes, "sha256_observed": self.digest.hexdigest(),
                "limit_bytes": STDIO_BOUND, "over_limit": self.over_limit,
                "read_error": self.read_error, "reader_finished": not self.thread.is_alive(),
                "raw_bytes_retained": False}


def source_paths():
    base = Path(sys.base_prefix)
    paths = [Path(__file__), HERE / "fixture.py", METHOD, Path(sys.executable)]
    paths += [H / name for name in ("codehost_bridge_v3.py", "codehost_owner.py", "codehost_mux_protocol.py", "native_cleanup_protocol.py")]
    paths += sorted((base / "Lib/asyncio").glob("*.py"))
    paths += [base / "Lib/socket.py", base / "Lib/selectors.py", base / "DLLs/_socket.pyd", base / "DLLs/_overlapped.pyd", base / ("python%d%d.dll" % sys.version_info[:2])]
    if not paths or any(not path.is_file() or path.is_symlink() for path in paths):
        raise ValueError()
    return list(dict.fromkeys(path.resolve() for path in paths))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewed-bridge-sha256", required=True)
    parser.add_argument("--reviewed-fixture-sha256", required=True)
    parser.add_argument("--reviewed-launcher-sha256", required=True)
    args = parser.parse_args()
    if sys.platform != "win32":
        return 2
    for path, expected in ((H / "codehost_bridge_v3.py", args.reviewed_bridge_sha256),
                           (HERE / "fixture.py", args.reviewed_fixture_sha256),
                           (Path(__file__), args.reviewed_launcher_sha256), (METHOD, METHOD_SHA)):
        if not re.fullmatch("[0-9a-f]{64}", expected) or binding(path)["sha256"] != expected:
            return 2
    sources = [binding(path) for path in source_paths()]
    RUN.mkdir(exist_ok=False)  # A second run, including after failure, is prohibited.
    manifest = {"schema": "campaign002-loopback-source-manifest-1", "sources": sources,
                "python_version": list(sys.version_info[:3]), "python_implementation": sys.implementation.name,
                "platform": "win32", "source_contract": "actual reader/writer and installed interpreter/asyncio; no installed native app server invoked"}
    save("source-manifest.json", manifest)
    argv = [sys.executable, "-X", "utf8", "-B", str(HERE / "fixture.py"),
            "--manifest", str(RUN / "source-manifest.json"), "--output", str(RUN / "child")]
    intent = {"schema": "campaign002-loopback-launch-intent-1", "argv": argv, "cwd": str(HERE),
              "source_manifest": binding(RUN / "source-manifest.json"),
              "fixed_cases": ["peer_graceful_send_shutdown", "peer_abortive_close", "local_close_pending_receive", "explicit_receive_task_cancel"],
              "per_case_observation_s": 5, "per_case_cleanup_s": 2,
              "child_work_bound_s": CHILD_WORK_BOUND_S, "outer_bound_s": OUTER_BOUND_S,
              "payload_bytes_per_case": 4096, "attempts_per_case": 1,
              "network": "127.0.0.1 only", "model_calls": 0, "native_app_server": False,
              "namespace": False, "physical_simulation": False, "queue_submission": False,
              "creation_flags": "CREATE_NO_WINDOW", "qualifies_production": False}
    save("intent.json", intent)
    start_mono, start_wall = time.monotonic(), time.time()
    child = None
    readers = []
    timeout = False
    kill_attempted = False
    launcher_error = None
    reaped = False
    # All setup before this point is metadata only. This is the sole subprocess launch.
    try:
        child = subprocess.Popen(argv, cwd=HERE, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        save("process-start.json", {"argv": argv, "owned_pid": child.pid,
                                    "started_monotonic_s": start_mono, "started_wall_unix_s": start_wall})
        readers = [StdioDigest(child.stdout, child), StdioDigest(child.stderr, child)]
        for reader in readers:
            reader.thread.start()
        try:
            child.wait(timeout=max(0.001, CHILD_WORK_BOUND_S - (time.monotonic() - start_mono)))
            reaped = True
        except subprocess.TimeoutExpired:
            timeout = True
            kill_attempted = True
            child.kill()
            child.wait(timeout=max(0.001, OUTER_BOUND_S - (time.monotonic() - start_mono)))
            reaped = True
    except BaseException as error:
        launcher_error = "TimeoutExpired" if isinstance(error, subprocess.TimeoutExpired) else "UnknownLauncherError"
    finally:
        if child is not None and child.poll() is None:
            kill_attempted = True
            try:
                child.kill()
                child.wait(timeout=max(0.001, OUTER_BOUND_S - (time.monotonic() - start_mono)))
                reaped = True
            except BaseException:
                launcher_error = "OwnedChildRetirementUnconfirmed"
        for reader in readers:
            reader.thread.join(timeout=max(0.0, OUTER_BOUND_S - (time.monotonic() - start_mono)))
        # Do not close a pipe while an outstanding reader thread holds its internal lock.
        for reader in readers:
            if not reader.thread.is_alive():
                reader.stream.close()
    elapsed = time.monotonic() - start_mono
    stdio = [reader.summary() for reader in readers]
    save("stdout-summary.json", stdio[0] if stdio else {"not_started": True})
    save("stderr-summary.json", stdio[1] if len(stdio) > 1 else {"not_started": True})
    result_path = RUN / "child/result.json"
    child_result = binding(result_path) if result_path.is_file() and result_path.stat().st_size <= 128 * 1024 else None
    events_path = RUN / "child/events.jsonl"
    events = binding(events_path) if events_path.is_file() and events_path.stat().st_size <= 512 * 1024 else None
    source_unchanged = unchanged_sources(sources)
    collected = (child is not None and child.returncode == 0 and reaped and not timeout and launcher_error is None
                 and elapsed <= OUTER_BOUND_S and all(not item["over_limit"] and not item["read_error"] and item["reader_finished"] for item in stdio)
                 and child_result is not None and events is not None and source_unchanged)
    receipt = {"schema": "campaign002-loopback-execution-receipt-1", "diagnostic_only": True,
               "collection_completed": collected, "qualifies_production": False,
               "started_wall_unix_s": start_wall, "finished_wall_unix_s": time.time(),
               "outer_elapsed_s": elapsed, "outer_bound_s": OUTER_BOUND_S,
               "child_exit_code": child.returncode if child else None, "timeout": timeout,
               "kill_attempted": kill_attempted, "owned_child_reaped": reaped, "launcher_error": launcher_error,
               "stdio": stdio, "child_result": child_result, "events": events,
               "sources_unchanged": source_unchanged, "source_manifest": binding(RUN / "source-manifest.json"),
               "limitations": ["Controlled adapter observations do not establish Smoke026 causality.",
                               "Unknown or unexpected case outcomes stay unknown; no numeric OS error is presumed.",
                               "The35-second child work cutoff reserves5seconds for retirement within the40-second outer acceptance bound; an overrun is retained as incomplete, never hidden."]}
    save("receipt.json", receipt)
    print(json.dumps({"collection_completed": collected, "receipt": binding(RUN / "receipt.json")}, sort_keys=True))
    return 0 if collected else 1


if __name__ == "__main__":
    try:
        status = main()
    except BaseException:
        # Never print arbitrary messages, exception args or traceback text.
        status = 2
    raise SystemExit(status)
