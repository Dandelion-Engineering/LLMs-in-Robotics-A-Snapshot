"""HTTP and filesystem boundary tests. No simulator, hardware or model needed."""
from contextlib import redirect_stdout
import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("robot_client", ROOT / "runtime-template/robot.py")
robot = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = robot
SPEC.loader.exec_module(robot)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    def handle_request(self):
        self.close_connection = True
        data = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.server.requests.append((self.command, self.path, dict(self.headers), json.loads(data) if data else None))
        if self.path == "/status" and self.server.status_override is not None:
            wire = json.dumps(self.server.status_override).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Length", str(len(wire)))
            self.end_headers()
            self.wfile.write(wire)
            return
        mode = self.server.mode
        if mode == "lost":
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()
            return
        if mode == "slow":
            time.sleep(.2)
        if mode == "redirect":
            self.send_response(302)
            self.send_header("Location", self.server.redirect)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        reply = self.server.reply
        if mode == "oversized":
            wire = b"x" * (robot.MAX_REPLY + 1)
        elif mode == "malformed":
            wire = b'{"ok":true,"value":NaN}'
        else:
            wire = json.dumps(reply).encode("utf-8")
        self.send_response(504 if mode == "reply-timeout" else 409 if mode == "reject" else 200)
        self.send_header("Content-Type", "application/json")
        if mode != "oversized-no-length":
            self.send_header("Content-Length", str(len(wire) + (50 if mode == "truncated" else 0)))
        else:
            wire = b"x" * (robot.MAX_REPLY + 1)
            self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(wire)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.server.requests = []
        self.server.mode = "ok"
        self.server.reply = {"ok": True, "status": "accepted"}
        self.server.status_override = None
        self.server.redirect = "http://203.0.113.1:80/steal"
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        (self.workspace / "live").mkdir()
        (self.workspace / "notes").mkdir()
        (self.workspace / "programs").mkdir()
        self.endpoint = {"schema": "robot-codex-host-1.0", "url": "http://127.0.0.1:" + str(self.server.server_port), "capability": "test-capability-do-not-print"}
        self.state = {"authority_epoch": 7, "order_version": 3, "observation_sequence": 11}
        self.server.status_override = {"ok": True, **self.state}
        self.write_json("live/endpoint.json", self.endpoint)
        self.write_json("live/activation.json", self.state)
        self.write_json("live/state.json", self.state)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(1)
        self.temp.cleanup()

    def write_json(self, path, value):
        (self.workspace / path).write_text(json.dumps(value), encoding="utf-8")

    def client(self, **kwargs):
        return robot.Client(self.workspace, **kwargs)

    def test_endpoint_allows_only_literal_loopback_origin(self):
        urls = ["https://127.0.0.1:8000", "http://example.com:80", "http://localhost:80", "http://127.0.0.1",
                "http://127.0.0.1:0", "http://127.0.0.1:65536", "http://127.0.0.1:80/path",
                "http://127.0.0.1:80/?x=1", "http://127.0.0.1:80/#fragment", "http://u:p@127.0.0.1:80",
                "http://127.0.0.1:80/?", "http://127.0.0.1:80/#",
                "http://127.0.0.1:80\r\nHeader:bad", "http://[::1%bad]:80", "http://192.168.1.1:80"]
        for url in urls:
            with self.subTest(url=url), self.assertRaises(robot.ClientError):
                robot.Endpoint.parse({**self.endpoint, "url": url})
        self.assertEqual(robot.Endpoint.parse({**self.endpoint, "url": "http://[::1]:8000/"}).host, "::1")
        self.assertEqual(robot.Endpoint.parse(self.endpoint).host, "127.0.0.1")

    def test_bad_capability_never_gets_sent(self):
        for capability in [None, "short", "valid-looking-token\r\nInjected: yes", "x" * 513]:
            self.write_json("live/endpoint.json", {**self.endpoint, "capability": capability})
            with self.assertRaises(robot.ClientError):
                self.client()
        self.assertEqual(self.server.requests, [])

    def test_fence_is_pinned_even_after_status_and_file_updates(self):
        client = self.client()
        client.command("stable-0", {"operation": "wait"})
        updated = {"authority_epoch": 8, "order_version": 4, "observation_sequence": 12}
        self.write_json("live/state.json", updated)
        self.write_json("live/activation.json", updated)
        self.server.status_override = {"ok": True, **updated}
        client.status()
        client.command("stable-1", {"operation": "wait"})
        method, path, headers, body = self.server.requests[-1]
        self.assertEqual((method, path), ("POST", "/command"))
        self.assertEqual(headers["X-Robot-Capability"], self.endpoint["capability"])
        self.assertEqual(body, {**self.state, "request_id": "stable-1", "action": {"operation": "wait"}})
        self.assertEqual(self.client().fence.authority_epoch, 8)

    def test_refreshes_only_observation_and_refuses_new_authority(self):
        client = self.client()
        self.server.status_override = {"ok": True, **self.state, "observation_sequence": 99}
        client.command("fresh-1", {"operation": "wait"})
        self.assertEqual(self.server.requests[-1][-1]["observation_sequence"], 99)
        stale_client = self.client()
        self.server.status_override = {"ok": True, **self.state, "authority_epoch": 8}
        before = len(self.server.requests)
        with self.assertRaises(robot.ClientError) as caught:
            stale_client.command("stale-1", {"operation": "wait"})
        self.assertEqual(caught.exception.code, "stale_activation")
        self.assertEqual([r[0] for r in self.server.requests[before:]], ["GET"])

    def test_launch_pinned_epoch_rejects_newly_written_activation(self):
        with patch.dict(os.environ, {"ROBOT_AUTHORITY_EPOCH": "6", "ROBOT_ORDER_VERSION": "3"}):
            with self.assertRaises(robot.ClientError):
                self.client()
        self.assertEqual(self.server.requests, [])

    def test_lost_reply_is_unknown_without_automatic_retry_or_refresh(self):
        client = self.client()
        self.server.mode = "lost"
        with self.assertRaises(robot.ClientError) as caught:
            client.command("uncertain-1", {"operation": "wait"})
        self.assertTrue(caught.exception.unknown)
        self.assertEqual(caught.exception.request_id, "uncertain-1")
        self.assertEqual(len(self.server.requests), 2)
        self.write_json("live/state.json", {**self.state, "authority_epoch": 8})
        self.server.mode = "ok"
        client.query("uncertain-1")
        self.assertEqual(self.server.requests[-1][1], "/command/uncertain-1")
        self.assertEqual(client.fence.authority_epoch, 7)

    def test_inactivity_timeout_reports_unknown_and_does_not_poll(self):
        self.server.mode = "slow"
        with self.assertRaises(robot.ClientError) as caught:
            self.client(timeout=.05).observe("capture-timeout")
        self.assertTrue(caught.exception.unknown)
        self.assertEqual(caught.exception.code, "transport_unknown")
        self.assertEqual(len(self.server.requests), 1)

    def test_redirect_never_follows_or_forwards_capability(self):
        self.server.mode = "redirect"
        self.server.status_override = None
        with self.assertRaises(robot.ClientError) as caught:
            self.client().status()
        self.assertEqual(caught.exception.code, "redirect_refused")
        self.assertEqual(len(self.server.requests), 1)

    def test_declared_and_streamed_oversize_replies_rejected(self):
        self.server.status_override = None
        for mode in ("oversized", "oversized-no-length"):
            self.server.mode = mode
            with self.subTest(mode=mode), self.assertRaises(robot.ClientError) as caught:
                self.client().status()
            self.assertEqual(caught.exception.code, "reply_too_large")

    def test_malformed_reply_after_action_is_unknown(self):
        self.server.mode = "malformed"
        with self.assertRaises(robot.ClientError) as caught:
            self.client().observe("bad-reply")
        self.assertTrue(caught.exception.unknown)
        self.assertEqual(caught.exception.code, "invalid_response")

    def test_valid_json_with_truncated_declared_body_is_unknown(self):
        self.server.mode = "truncated"
        with self.assertRaises(robot.ClientError) as caught:
            self.client().observe("short-body")
        self.assertTrue(caught.exception.unknown)
        self.assertEqual(caught.exception.code, "invalid_response")

    def test_host_queue_reply_timeout_is_unknown_not_rejection(self):
        self.server.mode = "reply-timeout"
        self.server.reply = {"ok": False, "error": {"code": "reply_timeout", "message": "Receipt unknown"}}
        output = io.StringIO()
        with redirect_stdout(output):
            result = robot.main(["observe", "--request-id", "queued-1"], workspace=self.workspace)
        self.assertEqual(result, 4)
        self.assertEqual(json.loads(output.getvalue())["outcome"], "unknown")
        self.assertEqual(len(self.server.requests), 1)

    def test_query_identifier_cannot_change_http_route(self):
        client = self.client()
        for value in ("../status", "abc?limit=0", "abc#x", "abc/../../", "", "a%2fb", "a\r\nHeader:x"):
            with self.subTest(value=value), self.assertRaises(robot.ClientError):
                client.query(value)
        self.assertEqual(self.server.requests, [])

    def test_physical_identity_cannot_be_overridden_in_action(self):
        for field in ("request_id", "incarnation", "authority_epoch", "order_version", "observation_sequence"):
            with self.subTest(field=field), self.assertRaises(robot.ClientError):
                self.client().command("stable-id", {"operation": "wait", field: 20})
        self.assertEqual(self.server.requests, [])

    def test_continuity_is_exact_atomic_host_request(self):
        content = "# Continuity\n\nLast reviewed event: 11\nUnresolved: uncertain-1\n"
        (self.workspace / "notes/new-note.md").write_bytes(content.encode("utf-8"))
        original = "last-good remains until host replacement"
        (self.workspace / "Continuity.md").write_text(original, encoding="utf-8")
        output = io.StringIO()
        with redirect_stdout(output):
            result = robot.main(["continuity", "--file", "notes/new-note.md"], workspace=self.workspace)
        self.assertEqual(result, 0)
        self.assertEqual(self.server.requests[-1][1:2], ("/continuity",))
        self.assertEqual(self.server.requests[-1][-1], {"content": content})
        self.assertEqual((self.workspace / "Continuity.md").read_text(encoding="utf-8"), original)

    def test_note_input_does_not_read_protected_or_external_paths(self):
        client = self.client()
        for name in ("../secret.txt", "live/endpoint.json", "Tasks.md", str(self.workspace / "Continuity.md")):
            with self.subTest(name=name), self.assertRaises(robot.ClientError):
                client.read_workspace_file(name)
        with self.assertRaises(robot.ClientError):
            client.continuity("a" * (robot.MAX_CONTINUITY + 1))
        self.assertEqual(self.server.requests, [])

    def test_world_motion_bounds_and_duration_checked_before_request(self):
        client = self.client()
        action = {"operation": "move_relative", "delta": [0, 0, .01], "frame": "world", "duration_s": .5}
        for change in ({"delta": [0, 0, .051]}, {"frame": "tool"}, {"duration_s": 5}, {"delta": [0, 0, float("nan")]}, {"duration_s": True}):
            with self.subTest(change=change), self.assertRaises(robot.ClientError):
                client.command("move-1", {**action, **change})
        self.assertEqual(self.server.requests, [])
        client.command("move-1", action)
        self.assertEqual(self.server.requests[-1][-1]["action"], action)

    def test_server_rejection_remains_nonzero_with_original_reason(self):
        self.server.mode = "reject"
        self.server.reply = {"ok": False, "error": {"code": "stale_epoch", "message": "current authority required"}}
        output = io.StringIO()
        with redirect_stdout(output):
            result = robot.main(["observe", "--request-id", "stale-1"], workspace=self.workspace)
        self.assertEqual(result, 3)
        document = json.loads(output.getvalue())
        self.assertEqual(document["server_reply"], self.server.reply)
        self.assertNotIn(self.endpoint["capability"], output.getvalue())

    def test_success_http_rejected_action_is_nonzero(self):
        self.server.reply = {"ok": True, "command": {"status": "rejected", "reason": "busy"}}
        with redirect_stdout(io.StringIO()):
            result = robot.main(["skill", "wait", "--request-id", "busy-1"], workspace=self.workspace)
        self.assertEqual(result, 3)

    def test_history_bounds_and_bad_fence_fail_closed(self):
        with self.assertRaises(robot.ClientError):
            self.client().history(limit=201)
        with self.assertRaises(robot.ClientError):
            self.client().history(after=-1)
        for bad in (None, True, -1, 2.0):
            self.write_json("live/state.json", {**self.state, "authority_epoch": bad})
            with self.subTest(bad=bad), self.assertRaises(robot.ClientError):
                self.client()
        self.assertEqual(self.server.requests, [])

    def test_proposed_read_only_example_uses_one_status_request(self):
        spec = importlib.util.spec_from_file_location("observe_once", ROOT / "runtime-template/programs/observe_once.py")
        example = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(example)
        reply = example.inspect_public_state(self.client())
        self.assertEqual(reply["observation_sequence"], 11)
        self.assertEqual([(r[0], r[1]) for r in self.server.requests], [("GET", "/status")])


if __name__ == "__main__":
    unittest.main()
