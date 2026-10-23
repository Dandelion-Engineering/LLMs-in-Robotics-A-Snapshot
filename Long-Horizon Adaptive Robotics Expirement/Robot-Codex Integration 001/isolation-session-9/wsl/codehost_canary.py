"""Nonmodel code-host canary; caller must place this inside the qualified namespace.

Fixed binary, source and empty tool inventory. No model, credentials, delegates,
filesystem tool, network tool or shell command is supplied to the V8 runtime.
"""
from __future__ import annotations

import hashlib
import json
import os
import queue
import signal
import struct
import subprocess
import threading
import time


SOURCE = r'''
const names = ["process", "require", "fetch", "Deno", "Bun", "WebSocket", "XMLHttpRequest"];
const apis = Object.fromEntries(names.map(name => [name, typeof globalThis[name]]));
const imports = {};
const import_errors = {};
for (const specifier of ["node:fs", "file:///etc/passwd", "https://example.invalid/"]) {
  try { await import(specifier); imports[specifier] = "unexpected_success"; }
  catch (error) { import_errors[specifier] = String(error); imports[specifier] = import_errors[specifier] === "unsupported import in exec" ? "denied" : "unexpected_error"; }
}
text(JSON.stringify({apis, imports, import_errors, tools: Object.keys(tools), all_tools_count: ALL_TOOLS.length,
  constructor_process_type: Function("return typeof process")()}));
'''
MAX_FRAME = 1024 * 1024


def main():
    result = {"host_qualified": False, "model_calls": 0, "enabled_tools": [],
              "binary": "/code-mode-host", "source_sha256": hashlib.sha256(SOURCE.encode()).hexdigest(),
              "source": SOURCE, "timeout_seconds": 20, "frames": [], "stderr_bytes": 0,
              "qualification_scope": "Code-host IPC and normal JavaScript API/import denials; caller owns OS namespace"}
    process = None
    messages = queue.Queue()
    deadline = time.monotonic() + 20

    def require(condition, reason):
        if not condition:
            raise RuntimeError(reason)

    def stop():
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def stdout_reader():
        try:
            while True:
                header = process.stdout.read(4)
                if not header:
                    messages.put({"reader_error": "host stdout closed"})
                    return
                require(len(header) == 4, "Incomplete IPC frame prefix")
                length, = struct.unpack("<I", header)
                require(length <= MAX_FRAME, "Oversized IPC frame")
                payload = process.stdout.read(length)
                require(len(payload) == length, "Incomplete IPC frame payload")
                messages.put(json.loads(payload))
        except Exception as error:
            messages.put({"reader_error": str(error)})

    def stderr_reader():
        while True:
            chunk = process.stderr.read(4096)
            if not chunk:
                return
            result["stderr_bytes"] += len(chunk)
            if result["stderr_bytes"] > MAX_FRAME:
                messages.put({"reader_error": "Host stderr bound exceeded"})
                return

    def send(message):
        payload = json.dumps(message, separators=(",", ":")).encode()
        process.stdin.write(struct.pack("<I", len(payload)) + payload)
        process.stdin.flush()

    def receive():
        remaining = deadline - time.monotonic()
        require(remaining > 0, "Code-host canary deadline exceeded")
        message = messages.get(timeout=remaining)
        require("reader_error" not in message, message.get("reader_error", ""))
        require(not str(message.get("type", "")).startswith("delegate/"), "Unexpected delegate request with empty tools")
        wire = message.get("result", {})
        result["frames"].append({"type": message.get("type"), "id": message.get("id"),
            "result_status": wire.get("status"),
            "value_keys": sorted(wire.get("value", {})) if isinstance(wire.get("value"), dict) else []})
        require(wire.get("status") != "error", "Code-host operation returned an error")
        return message

    def await_response(request_id):
        while True:
            message = receive()
            if message.get("type") == "operation/response" and message.get("id") == request_id:
                return message["result"]["value"]

    watchdog = threading.Timer(20, stop)
    watchdog.daemon = True
    try:
        process = subprocess.Popen(["/code-mode-host", "--listen", "stdio"], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
                                   env={"PATH": "/usr/bin:/bin", "HOME": "/tmp", "LANG": "C.UTF-8"})
        watchdog.start()
        threading.Thread(target=stdout_reader, daemon=True).start()
        threading.Thread(target=stderr_reader, daemon=True).start()
        send({"type": "connection/hello", "supportedVersions": [1], "requiredCapabilities": [], "optionalCapabilities": []})
        hello = receive()
        require(hello.get("type") == "connection/ready" and hello.get("selectedVersion") == 1, "Code-host handshake failed")
        result["protocol_version"] = hello["selectedVersion"]
        send({"type": "operation/request", "id": 1, "request": {"method": "session/open", "sessionId": "isolation-canary"}})
        require(await_response(1).get("type") == "session/ready", "Code-host session did not open")
        send({"type": "operation/request", "id": 2, "request": {"method": "session/execute", "sessionId": "isolation-canary",
            "request": {"tool_call_id": "isolation-canary", "enabled_tools": [], "source": SOURCE,
                        "yield_time_ms": 1000, "max_output_tokens": 1500}}})
        while True:
            message = receive()
            if message.get("type") == "execute/initialResponse" and message.get("id") == 2:
                runtime = message["result"]["value"]
                break
        require("Result" in runtime, "Canary did not complete within its initial cell deadline")
        completed = runtime["Result"]
        require(completed.get("error_text") is None, "Canary JavaScript execution failed")
        content = completed.get("content_items", [])
        require(len(content) == 1 and content[0].get("type") == "input_text", "Unexpected canary output structure")
        checks = json.loads(content[0]["text"])
        result["checks"] = checks
        require(set(checks.get("apis", {})) == {"process", "require", "fetch", "Deno", "Bun", "WebSocket", "XMLHttpRequest"}
                and all(value == "undefined" for value in checks["apis"].values()), "Host APIs exposed to JavaScript")
        require(checks.get("constructor_process_type") == "undefined", "Constructor exposed a process API")
        require(checks.get("tools") == [] and checks.get("all_tools_count") == 0, "Unexpected supplied tool")
        require(set(checks.get("imports", {})) == {"node:fs", "file:///etc/passwd", "https://example.invalid/"}
                and all(value == "denied" for value in checks["imports"].values()), "Module import was not denied")
        send({"type": "operation/request", "id": 3, "request": {"method": "session/shutdown", "sessionId": "isolation-canary"}})
        require(await_response(3).get("type") == "session/closed", "Code-host session did not close")
        result["host_qualified"] = True
    except Exception as error:
        result["error"] = str(error) or type(error).__name__
    finally:
        watchdog.cancel()
        stop()
        if process is not None:
            process.wait(timeout=2)
        result["elapsed_seconds"] = round(20 - (deadline - time.monotonic()), 3)
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["host_qualified"] else 1)


if __name__ == "__main__":
    main()
