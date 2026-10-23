"""Real loopback HTTP plus synthetic host state; no physical Cell or model."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from run_host import HttpGateway, Mail
from supervisor import Supervisor, Journal, GatewayError
from test_supervisor import FakeAdapter, packet, Candidate


class HttpGenerationChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.journal = Journal(self.path / "protected", self.path / "runtime", "synthetic-only")
        self.adapter = FakeAdapter()
        self.baseline = Candidate("baseline", self.path / "baseline", True)
        self.host = Supervisor(self.adapter, self.baseline, self.journal)
        self.host.update_observation(packet())
        self.host.activate("Synthetic activation")
        self.gateway = HttpGateway(self.journal.workspace)
        self.gateway.rotate(self.host.epoch)
        self.gateway.start()

    def tearDown(self):
        self.gateway.close()
        self.temp.cleanup()

    def queued(self, method, path, body=None, epoch=None):
        mail = Mail(method, path, body or {}, self.host.epoch if epoch is None else epoch)
        self.gateway.requests.put_nowait(mail)
        return mail

    def test_http_authentication_captures_one_epoch(self):
        expected = self.gateway.epoch
        result = {}
        def read_status():
            request = urllib.request.Request("http://127.0.0.1:" + str(self.gateway.server.server_port) + "/status",
                                             headers={"X-Robot-Capability": self.gateway.capability})
            try:
                with urllib.request.urlopen(request, timeout=3.) as response:
                    result.update(json.load(response))
            except Exception as error:
                result["error"] = type(error).__name__
        thread = threading.Thread(target=read_status)
        thread.start()
        mail = self.gateway.requests.get(timeout=2.)
        self.assertEqual(mail.authenticated_epoch, expected)
        mail.result.put_nowait((200, {"ok": True, "authenticated_epoch": expected}))
        thread.join(timeout=3.)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result, {"ok": True, "authenticated_epoch": expected})

    def test_queued_old_continuity_cannot_write_after_restart(self):
        note = self.journal.workspace / "Continuity.md"
        note.write_text("retain current note", encoding="utf-8")
        old_epoch, old_token = self.gateway.credentials
        stale_note = self.queued("POST", "/continuity", {"content": "late stale overwrite"}, old_epoch)
        response = self.host.restart_agent(self.host.envelope("restart"))
        self.gateway.process(self.host)
        self.assertEqual(response["command"]["status"], "completed")
        status, response = stale_note.result.get_nowait()
        self.assertEqual((status, response["error"]["code"]), (409, "stale_authentication"))
        self.assertEqual(note.read_text(), "retain current note")
        self.assertNotEqual(self.gateway.capability, old_token)
        self.assertEqual(self.gateway.epoch, self.host.epoch)
        self.assertFalse(any(row["type"] == "continuity_committed" for row in self.journal.events))

    def test_queued_old_command_and_read_rejected_after_epoch_change(self):
        epoch = self.host.epoch
        body = self.host.envelope("late-action", {"operation": "wait"})
        command = self.queued("POST", "/command", body, epoch)
        read = self.queued("GET", "/status", epoch=epoch)
        self.host.restart_agent(self.host.envelope("restart"))
        self.gateway.process(self.host)
        for mail in (command, read):
            status, result = mail.result.get_nowait()
            self.assertEqual((status, result["error"]["code"]), (409, "stale_authentication"))
        self.assertEqual(self.adapter.submissions, [])
        self.assertNotIn("late-action", self.host.commands)

    def test_queued_old_continuity_rejected_after_handback(self):
        self.host.update_observation(packet("parking1"))
        old_epoch = self.host.epoch
        handback = self.queued("POST", "/handback", self.host.envelope("return-control"))
        stale_note = self.queued("POST", "/continuity", {"content": "stale"}, old_epoch)
        self.gateway.process(self.host)
        self.assertEqual(handback.result.get_nowait()[1]["command"]["status"], "completed")
        status, response = stale_note.result.get_nowait()
        self.assertEqual((status, response["error"]["code"]), (409, "stale_authentication"))
        self.assertFalse((self.journal.workspace / "Continuity.md").exists())

    def test_rotated_token_rejects_new_http_request_using_old_token(self):
        token = self.gateway.capability
        self.host.restart_agent(self.host.envelope("restart"))
        self.gateway.rotate(self.host.epoch)
        request = urllib.request.Request("http://127.0.0.1:" + str(self.gateway.server.server_port) + "/status",
                                         headers={"X-Robot-Capability": token})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=3.)
        self.assertEqual(caught.exception.code, 403)
        self.assertEqual(self.gateway.requests.qsize(), 0)

    def test_restart_retry_under_current_authentication_is_stable_and_queryable(self):
        body = self.host.envelope("restart-stable")
        original_epoch = self.host.epoch
        first_reply = self.host.restart_agent(body)
        retry_reply = self.host.restart_agent(body)
        query = self.queued("GET", "/command/restart-stable")
        self.gateway.process(self.host)
        query_reply = query.result.get_nowait()[1]
        self.assertTrue(retry_reply["duplicate"])
        self.assertEqual(self.host.epoch, original_epoch + 1)
        self.assertEqual(len(self.adapter.cancels), 1)
        self.assertEqual(first_reply["command"], retry_reply["command"])
        self.assertEqual(query_reply["command"], first_reply["command"])
        registry = json.loads((self.journal.root / "command-registry.json").read_text())
        self.assertEqual(registry["restart-stable"]["phase"], "terminal")
        self.assertEqual(registry["restart-stable"]["transition"]["authority_epoch"], self.host.epoch)

    def test_robot_http_cannot_invoke_operator_restart(self):
        original_epoch = self.host.epoch
        result = {}
        def try_restart():
            request = urllib.request.Request("http://127.0.0.1:" + str(self.gateway.server.server_port) + "/restart-agent",
                data=json.dumps(self.host.envelope("unauthorized-restart")).encode(), method="POST",
                headers={"X-Robot-Capability": self.gateway.capability, "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=3.) as response:
                    result.update(status=response.status, body=json.load(response))
            except urllib.error.HTTPError as error:
                result.update(status=error.code, body=json.load(error))
        thread = threading.Thread(target=try_restart)
        thread.start()
        mail = self.gateway.requests.get(timeout=2.)
        self.gateway.requests.put_nowait(mail)
        self.gateway.process(self.host)
        thread.join(timeout=3.)
        self.assertFalse(thread.is_alive())
        self.assertEqual((result["status"], result["body"]["error"]["code"]), (403, "operator_only"))
        self.assertEqual(self.host.epoch, original_epoch)
        self.assertEqual(self.adapter.cancels, [])
        self.assertNotIn("unauthorized-restart", self.host.commands)

    def test_restart_changed_payload_conflicts_and_rejected_restart_is_retained(self):
        body = self.host.envelope("restart-stable")
        self.host.restart_agent(body)
        changed = copy.deepcopy(body); changed["reason"] = "different request"
        with self.assertRaises(GatewayError) as caught:
            self.host.restart_agent(changed)
        self.assertEqual(caught.exception.code, "id_conflict")
        invalid = self.host.envelope("invalid-restart"); invalid["authority_epoch"] = 0
        reply = self.host.restart_agent(invalid)
        self.assertEqual(reply["command"]["status"], "rejected")
        self.assertEqual(self.host.request("GET", "/command/invalid-restart")["command"], reply["command"])
        self.assertEqual(len(self.adapter.cancels), 1)


if __name__ == "__main__": unittest.main()
