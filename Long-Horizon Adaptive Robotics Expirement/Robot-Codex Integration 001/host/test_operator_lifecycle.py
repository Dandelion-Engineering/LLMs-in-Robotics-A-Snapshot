"""Protected lifecycle integration with real loopback HTTP, synthetic physics.

No model or Cell is invoked. These tests establish authority mechanics only.
"""
from __future__ import annotations
import base64
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from run_host import HttpGateway, Mail
from supervisor import Supervisor, Journal, GatewayError
from test_supervisor import Candidate, FakeAdapter, packet
from challenges import make_manifest, validate_manifest


class OperatorLifecycleChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.journal = Journal(self.path / "protected", self.path / "runtime", "synthetic-lifecycle")
        self.adapter = FakeAdapter()
        self.baseline = Candidate("baseline", self.path / "baseline", True)
        self.host = Supervisor(self.adapter, self.baseline, self.journal)
        self.host.lifecycle_required = True
        self.host.update_observation(packet())
        self.host.activate("Synthetic conventional activation")
        self.gateway = HttpGateway(self.journal.workspace, self.journal.root)
        self.gateway.synchronize(self.host)
        self.gateway.start()

    def tearDown(self):
        self.gateway.close()
        self.temp.cleanup()

    def operator(self, path, body=None, method="POST"):
        """Exercise HTTP authentication then dispatch on this physics-owner thread."""
        result = {}
        def request():
            req = urllib.request.Request("http://127.0.0.1:" + str(self.gateway.server.server_port) + "/operator/" + path,
                data=json.dumps(body).encode() if body is not None else None, method=method,
                headers={"X-Robot-Operator-Capability": self.gateway.operator_capability})
            try:
                with urllib.request.urlopen(req, timeout=3.) as response:
                    result.update(status=response.status, body=json.load(response))
            except urllib.error.HTTPError as error:
                result.update(status=error.code, body=json.load(error))
        thread = threading.Thread(target=request)
        thread.start()
        mail = self.gateway.requests.get(timeout=2.)
        self.assertEqual(mail.scope, "operator")
        self.gateway.requests.put_nowait(mail)
        self.gateway.process(self.host)
        thread.join(3.)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result["status"], 200)
        return result["body"]

    def body(self, request_id, invocation_id="invocation-a"):
        return {"request_id": request_id, "invocation_id": invocation_id,
                "authority_epoch": self.host.epoch, "reason": "synthetic qualification"}

    def start(self, name="invocation-a"):
        return self.operator("start-invocation", self.body("start-" + name, name))

    def denied_http(self, path, headers):
        request = urllib.request.Request("http://127.0.0.1:" + str(self.gateway.server.server_port) + path,
                                        headers=headers)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=2.)
        self.assertEqual(caught.exception.code, 403)
        self.assertEqual(self.gateway.requests.qsize(), 0)

    def test_operator_secret_outside_runtime_and_never_in_public_history(self):
        endpoint = json.loads((self.journal.root / "operator-endpoint.json").read_text())
        self.assertEqual(endpoint["capability"], self.gateway.operator_capability)
        before = json.loads((self.journal.live / "endpoint.json").read_text())
        self.assertTrue(before["retired"])
        started = self.start()
        self.assertEqual(started["command"]["status"], "completed")
        for path in self.journal.live.rglob("*"):
            if path.is_file():
                self.assertNotIn(self.gateway.operator_capability, path.read_text())
        registry = (self.journal.root / "command-registry.json").read_text()
        self.assertNotIn(started["endpoint"]["capability"], registry)
        self.assertNotIn(self.gateway.operator_capability, registry)
        self.denied_http("/operator/status", {"X-Robot-Capability": started["endpoint"]["capability"]})
        self.denied_http("/status", {"X-Robot-Operator-Capability": self.gateway.operator_capability})

    def test_retirement_revokes_queued_and_new_calls_and_restart_reconciles(self):
        started = self.start()
        old_epoch, old_token = self.gateway.credentials
        action = self.host.envelope("lost-ack", {"operation": "wait"})
        self.host.command(action)
        self.host.robot_action_count = 19
        retired = self.operator("retire-invocation", self.body("retire-a"))
        self.assertEqual(retired["command"]["status"], "completed")
        self.assertEqual(self.adapter.cancels, ["isolated invocation retired"])
        stale = Mail("POST", "/continuity", {"content": "stale overwrite"}, old_epoch)
        self.gateway.requests.put_nowait(stale)
        self.gateway.process(self.host)
        self.assertEqual(stale.result.get_nowait()[1]["error"]["code"], "stale_authentication")
        self.denied_http("/status", {"X-Robot-Capability": old_token})
        blocked = self.operator("start-invocation", self.body("start-too-early", "invocation-b"))
        self.assertEqual(blocked["command"]["error"]["code"], "resource_busy")
        self.host.native_feedback({"request_id": "lost-ack", "status": "cancelled"})
        fresh = self.start("invocation-b")
        self.assertEqual(fresh["command"]["status"], "completed")
        self.assertNotEqual(fresh["endpoint"]["capability"], old_token)
        self.assertEqual(self.host.robot_action_count, 19)
        status = self.operator("status", method="GET")
        self.assertEqual(status["invocation_count"], 2)
        unresolved = status["unresolved_commands"]
        self.assertEqual(unresolved[0]["request_id"], "lost-ack")
        self.assertEqual(unresolved[0]["status"], "cancelled")
        self.assertEqual(unresolved[0]["verification"]["state"], "unknown")
        duplicate = self.host.command(action)
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(len(self.adapter.submissions), 1)
        self.denied_http("/status", {"X-Robot-Capability": old_token})

    def test_lifecycle_lost_reply_retry_is_idempotent_and_historical_start_has_no_token(self):
        body = self.body("stable-start")
        first = self.operator("start-invocation", body)
        second = self.operator("start-invocation", body)
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["endpoint"], second["endpoint"])
        retire_body = self.body("stable-retire")
        self.operator("retire-invocation", retire_body)
        retry = self.operator("retire-invocation", retire_body)
        self.assertTrue(retry["duplicate"])
        self.assertEqual(len(self.adapter.cancels), 1)
        self.start("invocation-b")
        historical = self.operator("start-invocation", body)
        self.assertTrue(historical["duplicate"])
        self.assertNotIn("endpoint", historical)
        self.assertEqual(self.host.invocation["invocation_id"], "invocation-b")
        wrong = self.operator("retire-invocation", self.body("wrong-retire", "invocation-a"))
        self.assertEqual(wrong["command"]["error"]["code"], "wrong_invocation")
        self.assertEqual(self.host.invocation["state"], "active")

    def test_handback_revokes_token_and_late_retirement_preserves_conventional_motion(self):
        self.start()
        old_epoch, old_token = self.gateway.credentials
        self.host.update_observation(packet("parking1"))
        handback = Mail("POST", "/handback", self.host.envelope("handback"), old_epoch)
        self.gateway.requests.put_nowait(handback)
        self.gateway.process(self.host)
        self.assertEqual(handback.result.get_nowait()[1]["command"]["status"], "completed")
        conventional_epoch = self.host.epoch
        self.adapter.active = True
        self.operator("retire-invocation", self.body("finally-retire"))
        self.assertEqual(self.host.epoch, conventional_epoch)
        self.assertTrue(self.adapter.active)
        self.assertEqual(self.adapter.cancels, [])
        self.denied_http("/status", {"X-Robot-Capability": old_token})
        self.assertEqual(self.host.owner, "conventional")

    def test_robot_cannot_dispatch_without_started_invocation(self):
        result = self.host.command(self.host.envelope("premature", {"operation": "wait"}))
        self.assertEqual(result["command"]["error"]["code"], "invocation_retired")
        self.assertEqual(self.adapter.submissions, [])

    def test_extended_caps_are_explicit_and_serve_only(self):
        manifest = make_manifest("misplaced-stock", "serve", "synthetic-cap-validation")
        manifest.update(sim_cap_s=1800, wall_cap_s=1800, storage_cap_bytes=512 * 1024 * 1024)
        self.assertEqual(validate_manifest(manifest), manifest)
        manifest["mode"] = "reference"
        with self.assertRaises(ValueError):
            validate_manifest(manifest)
        manifest["mode"] = "serve"
        manifest["sim_cap_s"] += 1
        with self.assertRaises(ValueError):
            validate_manifest(manifest)

    def test_operator_stop_revokes_and_is_queryable(self):
        self.start()
        token = self.gateway.capability
        result = self.operator("stop", self.body("stop"))
        self.assertEqual(result["command"]["status"], "completed")
        self.assertTrue(self.host.stop_requested)
        self.assertEqual(self.host.invocation["state"], "retired")
        self.denied_http("/status", {"X-Robot-Capability": token})
        query = self.operator("command/stop", method="GET")
        self.assertEqual(query["command"], result["command"])

    def test_note_commit_retains_new_hash_and_failed_replace_keeps_last_good(self):
        self.journal.continuity("last good")
        original = self.journal.read_continuity()
        import supervisor
        replace = supervisor.os.replace
        def fail_note(source, destination):
            if Path(destination).name == "Continuity.md":
                raise OSError("synthetic interruption before commit")
            return replace(source, destination)
        with patch.object(supervisor.os, "replace", side_effect=fail_note):
            with self.assertRaises(OSError):
                self.journal.continuity("new candidate")
        self.assertEqual(self.journal.read_continuity(), original)
        committed = self.journal.continuity("new committed")
        retained = self.journal.root / "continuity-history" / (committed["sha256"] + ".md")
        self.assertEqual(retained.read_text(), "new committed")
        self.assertEqual(self.operator("continuity", method="GET")["content"], "new committed")

    def test_image_transfer_is_named_bounded_public_artifact(self):
        path = self.journal.live / "observations" / "overhead-1.png"
        raw = b"\x89PNG\r\n\x1a\nsynthetic bytes; not an image quality test"
        path.write_bytes(raw)
        reply = self.host.request("GET", "/observation/overhead-1.png")
        self.assertEqual(base64.b64decode(reply["base64"]), raw)
        self.assertEqual(reply["sha256"], hashlib.sha256(raw).hexdigest())
        for name in ("../public-history.jsonl", "overhead-1.png?x=1", "%2e%2e%2fsecret", "other.png", "overhead-01.png"):
            with self.subTest(name=name), self.assertRaises(GatewayError):
                self.host.request("GET", "/observation/" + name)
        path.write_bytes(b"x" * 750001)
        with self.assertRaises(GatewayError) as caught:
            self.host.request("GET", "/observation/overhead-1.png")
        self.assertEqual(caught.exception.code, "image_limit")


if __name__ == "__main__":
    unittest.main()
