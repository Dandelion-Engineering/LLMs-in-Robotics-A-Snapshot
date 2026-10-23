"""Stdlib client for the protected local robot service. Never imports a simulator.

Each Client pins its endpoint and fence once. A new observation or generation
requires a new invocation; no request is refreshed or retried automatically.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import http.client
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import socket
import sys
from urllib.parse import urlencode, urlsplit

MAX_REQUEST = 65536
MAX_REPLY = 1048576
MAX_CONTINUITY = 32768
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
SKILLS = {"transport", "recover_held", "setup", "cycle", "inspect", "observe", "wait", "cancel"}
MANUAL = {"cartesian_target", "joint_command", "trajectory", "move_relative", "gripper"}


class ClientError(Exception):
    def __init__(self, code, message, *, reply=None, request_id=None, unknown=False):
        super().__init__(message)
        self.code, self.message = code, message
        self.reply, self.request_id, self.unknown = reply, request_id, unknown

    def document(self):
        result = {"ok": False, "error": {"code": self.code, "message": self.message}}
        if self.reply is not None:
            result["server_reply"] = self.reply
        if self.request_id is not None:
            result["request_id"] = self.request_id
        if self.unknown:
            result["outcome"] = "unknown"
            result["next_step"] = ("Query this request ID before considering another action; no automatic retry occurred."
                                   if self.request_id is not None else
                                   "Read Continuity.md to reconcile the note before submitting a replacement; no automatic retry occurred.")
        return result


def _fail(message):
    raise ClientError("invalid_input", message)


def _json(data):
    def reject_constant(_):
        raise ValueError("non-finite JSON")
    try:
        return json.loads(data, parse_constant=reject_constant)
    except (ValueError, UnicodeError) as exc:
        raise ClientError("invalid_json", "Expected finite UTF-8 JSON.") from exc


def _bounded_file(path, limit):
    try:
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
    except OSError as exc:
        raise ClientError("file_unavailable", "Required workspace file is unavailable: " + path.name) from exc
    if len(data) > limit:
        _fail("Workspace file exceeds its byte limit: " + path.name)
    return data


def _identifier(value):
    if not isinstance(value, str) or IDENTIFIER.fullmatch(value) is None:
        _fail("Request/action IDs require 1-128 letters, digits, dots, underscores, colons or hyphens, beginning with a letter or digit.")
    return value


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        _fail(name + " must be an integer >= " + str(minimum) + ".")
    return value


def _number(value, name, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        _fail(name + " is outside its finite bounds.")
    return value


def _vector(value, count, name):
    if not isinstance(value, (list, tuple)) or len(value) != count:
        _fail(name + " requires " + str(count) + " finite numbers.")
    for number in value:
        _number(number, name, -1e6, 1e6)
    return list(value)


@dataclass(frozen=True)
class Endpoint:
    host: str
    port: int
    capability: str

    @classmethod
    def parse(cls, value):
        if not isinstance(value, dict) or value.get("schema") != "robot-codex-host-1.0":
            _fail("Endpoint requires schema robot-codex-host-1.0.")
        url, capability = value.get("url"), value.get("capability")
        if not isinstance(url, str) or any(c.isspace() for c in url):
            _fail("Endpoint URL must be a literal loopback HTTP origin.")
        try:
            parts = urlsplit(url)
            host, port = parts.hostname, parts.port
            address = ipaddress.ip_address(host)
        except (ValueError, TypeError) as exc:
            raise ClientError("invalid_input", "Endpoint must use a literal loopback IP and explicit port.") from exc
        if (parts.scheme != "http" or not address.is_loopback or port is None or not 1 <= port <= 65535
                or parts.username is not None or parts.password is not None or parts.path not in ("", "/")
                or "?" in url or "#" in url or "%" in host or "\\" in url):
            _fail("Endpoint must be a loopback HTTP origin without credentials, path, query or fragment.")
        if not isinstance(capability, str) or not 16 <= len(capability) <= 512 or any(ord(c) < 33 or ord(c) > 126 for c in capability):
            _fail("Endpoint capability is missing or malformed.")
        return cls(host, port, capability)


@dataclass(frozen=True)
class Fence:
    authority_epoch: int
    order_version: int
    observation_sequence: int

    @classmethod
    def parse(cls, value):
        if not isinstance(value, dict):
            _fail("Public state must be an object with current command fences.")
        return cls(*(_integer(value.get(key), key) for key in
                     ("authority_epoch", "order_version", "observation_sequence")))

    def envelope(self, request_id):
        return {"request_id": _identifier(request_id), "authority_epoch": self.authority_epoch,
                "order_version": self.order_version, "observation_sequence": self.observation_sequence}


class Client:
    """One endpoint/fence snapshot. Its HTTP methods each make one attempt only."""
    def __init__(self, workspace=None, *, timeout=5.0):
        self.workspace = Path(workspace or Path(__file__).resolve().parent).resolve()
        self.timeout = _number(timeout, "Socket inactivity timeout seconds", .05, 30.0)
        self.endpoint = Endpoint.parse(_json(_bounded_file(self.workspace / "live/endpoint.json", 4096)))
        # Read authority once. Live state may lag publication; it cannot confer a new epoch.
        activation = _json(_bounded_file(self.workspace / "live/activation.json", MAX_REPLY))
        if not isinstance(activation, dict):
            _fail("Activation must be an object.")
        epoch = _integer(activation.get("authority_epoch"), "activation authority_epoch")
        version = _integer(activation.get("order_version"), "activation order_version")
        for variable, expected in (("ROBOT_AUTHORITY_EPOCH", epoch), ("ROBOT_ORDER_VERSION", version)):
            pinned = os.environ.get(variable)
            if pinned is not None and pinned != str(expected):
                _fail("Activation conflicts with launch-pinned " + variable + "; start a newly authorized activation.")
        self._state = _json(_bounded_file(self.workspace / "live/state.json", MAX_REPLY))
        state_fence = Fence.parse(self._state)
        self.fence = Fence(epoch, version, state_fence.observation_sequence)
        self._dispatch_fence = None

    def _action_fence(self):
        if self._dispatch_fence is None:
            live = Fence.parse(self.status())
            if (live.authority_epoch, live.order_version) != (self.fence.authority_epoch, self.fence.order_version):
                raise ClientError("stale_activation", "Current authority or order differs from the pinned activation; no command was sent.")
            # Refresh observation once, never authority. Retries retain this exact fence.
            self._dispatch_fence = live
        return self._dispatch_fence

    def _request(self, method, path, body=None):
        payload = None if body is None else json.dumps(body, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        if payload is not None and len(payload) > MAX_REQUEST:
            _fail("Request exceeds 65536 UTF-8 bytes.")
        headers = {"X-Robot-Capability": self.endpoint.capability, "Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        connection = http.client.HTTPConnection(self.endpoint.host, self.endpoint.port, timeout=self.timeout)
        request_id = body.get("request_id") if body else None
        try:
            connection.request(method, path, body=payload, headers=headers)
            response = connection.getresponse()
            # http.client never follows redirects; reject rather than expose the capability elsewhere.
            if 300 <= response.status <= 399:
                raise ClientError("redirect_refused", "Robot service redirects are forbidden.", request_id=request_id, unknown=method != "GET")
            length = response.getheader("Content-Length")
            if length is not None:
                try:
                    declared = int(length)
                except ValueError as exc:
                    raise ClientError("invalid_response", "Invalid response length.", request_id=request_id, unknown=method != "GET") from exc
                if not 0 <= declared <= MAX_REPLY:
                    raise ClientError("reply_too_large", "Reply exceeds 1048576 bytes.", request_id=request_id, unknown=method != "GET")
            wire = response.read(MAX_REPLY + 1)
            if len(wire) > MAX_REPLY:
                raise ClientError("reply_too_large", "Reply exceeds 1048576 bytes.", request_id=request_id, unknown=method != "GET")
            if length is not None and len(wire) != declared:
                raise ClientError("invalid_response", "Response ended before its declared length.", request_id=request_id, unknown=method != "GET")
            try:
                reply = _json(wire)
            except ClientError as exc:
                raise ClientError("invalid_response", "Service did not return finite JSON.", request_id=request_id, unknown=method != "GET") from exc
            if not isinstance(reply, dict) or type(reply.get("ok")) is not bool:
                raise ClientError("invalid_response", "Service reply lacks an explicit ok boolean.", request_id=request_id, unknown=method != "GET")
            if not 200 <= response.status < 300 or not reply["ok"]:
                error_code = reply.get("error", {}).get("code") if isinstance(reply.get("error"), dict) else None
                if method != "GET" and (response.status >= 500 or error_code == "reply_timeout"):
                    raise ClientError("service_outcome_unknown", "The service did not confirm the mutating request's outcome.",
                                      reply=reply, request_id=request_id, unknown=True)
                raise ClientError("server_rejected", "Robot service did not accept the request.", reply=reply, request_id=request_id)
            return reply
        except (OSError, http.client.HTTPException, socket.timeout) as exc:
            raise ClientError("transport_unknown" if method != "GET" else "transport_unavailable",
                              "The service response was not received completely; physical completion is unconfirmed.",
                              request_id=request_id, unknown=method != "GET") from exc
        finally:
            connection.close()

    def status(self):
        return self._request("GET", "/status")

    def history(self, *, after=0, limit=50):
        _integer(after, "after")
        _integer(limit, "limit", 1)
        if limit > 200:
            _fail("History limit must be <= 200.")
        return self._request("GET", "/history?" + urlencode({"after": after, "limit": limit}))

    def query(self, request_id):
        return self._request("GET", "/command/" + _identifier(request_id))

    def observe(self, request_id):
        return self._request("POST", "/observe", self.fence.envelope(request_id))

    def command(self, request_id, action):
        if not isinstance(action, dict) or action.get("operation") not in SKILLS | MANUAL:
            _fail("Unsupported robot operation.")
        if set(action) & {"request_id", "incarnation", "authority_epoch", "order_version", "observation_sequence"}:
            _fail("Action identity is attached by the protected gateway; it cannot be overridden.")
        # Local validation improves errors; the host remains the admission authority.
        op = action["operation"]
        if op in {"cartesian_target", "move_relative", "joint_command", "gripper"}:
            _number(action.get("duration_s", .5 if op == "gripper" else None), "duration_s", .01, 2.)
        if op == "move_relative":
            delta = _vector(action.get("delta"), 3, "delta in metres")
            if action.get("frame") != "world" or math.sqrt(sum(v * v for v in delta)) > .05 + 1e-12:
                _fail("Relative movement requires frame world and Euclidean displacement <= 0.05 metres.")
        if op == "cartesian_target":
            _vector(action.get("position"), 3, "world position in metres")
        if op == "joint_command":
            _vector(action.get("values"), 7, "joint values")
            if action.get("mode") not in {"position", "velocity", "effort"}:
                _fail("Joint mode must be position, velocity or effort.")
        if op == "gripper" and action.get("state") not in {"open", "close"}:
            _fail("Gripper state must be open or close.")
        _identifier(request_id)
        envelope = self._action_fence().envelope(request_id)
        envelope["action"] = action.copy()
        return self._request("POST", "/command", envelope)

    def handback(self, request_id, reason):
        if not isinstance(reason, str) or not reason.strip() or len(reason.encode("utf-8")) > 2048:
            _fail("Handback requires a nonempty reason <= 2048 UTF-8 bytes.")
        _identifier(request_id)
        body = self._action_fence().envelope(request_id)
        body["reason"] = reason
        return self._request("POST", "/handback", body)

    def continuity(self, content):
        if not isinstance(content, str) or not content.strip() or len(content.encode("utf-8")) > MAX_CONTINUITY:
            _fail("Continuity requires nonempty UTF-8 text <= 32768 bytes.")
        return self._request("POST", "/continuity", {"content": content})

    def read_workspace_file(self, relative, limit=MAX_CONTINUITY):
        supplied = Path(relative)
        if supplied.is_absolute() or ".." in supplied.parts:
            _fail("Use a relative file within notes/, programs/, or Continuity.md.")
        path = (self.workspace / supplied).resolve()
        try:
            actual = path.relative_to(self.workspace)
        except ValueError as exc:
            raise ClientError("invalid_input", "File escapes the workspace.") from exc
        if actual != Path("Continuity.md") and (not actual.parts or actual.parts[0] not in {"notes", "programs"}):
            _fail("Only Continuity.md, notes/, and programs/ are readable through this input option.")
        try:
            return _bounded_file(path, limit).decode("utf-8")
        except UnicodeError as exc:
            raise ClientError("invalid_input", "File must contain UTF-8 text.") from exc


def parser():
    top = argparse.ArgumentParser(description=__doc__)
    top.add_argument("--timeout", type=float, default=5., help="socket inactivity timeout in seconds (0.05-30); not a physical-action deadline")
    commands = top.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    history = commands.add_parser("history")
    history.add_argument("--after", type=int, default=0)
    history.add_argument("--limit", type=int, default=50)
    query = commands.add_parser("query")
    query.add_argument("request_id")
    for name in ("observe", "handback"):
        command = commands.add_parser(name)
        command.add_argument("--request-id", required=True)
        if name == "handback":
            command.add_argument("--reason", required=True)
    continuity = commands.add_parser("continuity")
    continuity.add_argument("--file", required=True, help="UTF-8 note in workspace notes/, programs/, or Continuity.md")
    skill = commands.add_parser("skill")
    skill.add_argument("name", choices=sorted(SKILLS))
    skill.add_argument("--request-id", required=True)
    for name in ("part-id", "destination", "family", "recipe", "target-request-id"):
        skill.add_argument("--" + name)
    skill.add_argument("--clear-view", action="store_true", default=None)
    manual = commands.add_parser("manual")
    manual.add_argument("name", choices=["cartesian-target", "move-relative", "gripper", "joint-position", "joint-velocity", "joint-effort", "trajectory"])
    manual.add_argument("--request-id", required=True)
    manual.add_argument("--position", nargs=3, type=float, help="world TCP target x y z in metres")
    manual.add_argument("--delta", nargs=3, type=float, help="world TCP displacement dx dy dz in metres; norm <= .05")
    manual.add_argument("--frame", choices=["world"])
    manual.add_argument("--duration", type=float, help="simulation seconds; .01-2")
    manual.add_argument("--values", nargs=7, type=float)
    manual.add_argument("--state", choices=["open", "close"])
    manual.add_argument("--gripper", type=int, choices=[0, 255], help="0 close, 255 open; omit to retain")
    manual.add_argument("--waypoints-file", help="workspace JSON list of absolute simulation time_s and seven positions in radians")
    return top


def main(argv=None, *, workspace=None):
    args = parser().parse_args(argv)
    try:
        client = Client(workspace, timeout=args.timeout)
        name = args.command
        if name == "status":
            reply = client.status()
        elif name == "history":
            reply = client.history(after=args.after, limit=args.limit)
        elif name == "query":
            reply = client.query(args.request_id)
        elif name == "observe":
            reply = client.observe(args.request_id)
        elif name == "handback":
            reply = client.handback(args.request_id, args.reason)
        elif name == "continuity":
            reply = client.continuity(client.read_workspace_file(args.file))
        elif name == "skill":
            action = {"operation": args.name}
            for key in ("part_id", "destination", "family", "recipe", "target_request_id", "clear_view"):
                value = getattr(args, key)
                if value is not None:
                    action[key] = value
            reply = client.command(args.request_id, action)
        else:
            operation = "joint_command" if args.name.startswith("joint-") else args.name.replace("-", "_")
            action = {"operation": operation}
            if operation == "joint_command":
                action["mode"] = args.name.removeprefix("joint-")
            for key in ("position", "delta", "frame", "values", "state", "gripper"):
                value = getattr(args, key)
                if value is not None:
                    action[key] = value
            if args.duration is not None:
                action["duration_s"] = args.duration
            if args.waypoints_file:
                action["waypoints"] = _json(client.read_workspace_file(args.waypoints_file, MAX_REQUEST))
            reply = client.command(args.request_id, action)
        print(json.dumps(reply, ensure_ascii=False, allow_nan=False))
        # A successful HTTP exchange can still contain a truthful admission rejection.
        if reply.get("status") == "rejected" or (isinstance(reply.get("command"), dict) and reply["command"].get("status") == "rejected"):
            return 3
        return 0
    except ClientError as exc:
        print(json.dumps(exc.document(), ensure_ascii=False))
        return 4 if exc.unknown else 3
    except (ValueError, TypeError) as exc:
        print(json.dumps({"ok": False, "error": {"code": "invalid_input", "message": str(exc)}}))
        return 3


if __name__ == "__main__":
    sys.exit(main())
