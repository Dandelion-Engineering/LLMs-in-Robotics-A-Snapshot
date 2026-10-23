"""Bounded Windows app-server client for the qualified external Linux executor.

Default invocation is metadata/thread preflight only. --run-bootstrap is the
sole model-call gate. The caller owns and must already qualify the outer WSL
boundary. No authentication file is opened or copied by this program.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import time
import tomllib
from urllib.parse import unquote, urlsplit


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("rci_launcher", HERE.parents[1] / "launch" / "robot_codex_launcher.py")
assert SPEC and SPEC.loader
LAUNCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LAUNCH)
MAX_BYTES = 32 * 1024 * 1024
BOOTSTRAP = "Follow the instructions in RobotAgentPrompt.md."
DISABLED = set(LAUNCH.DISABLED_FEATURES) | {
    "remote_plugin", "image_generation", "view_image", "tool_suggest",
    "workspace_dependencies", "network_proxy", "enable_mcp_apps",
    "codex_apps_mcp_2026_07_28", "mcp_2026_07_28", "standalone_web_search",
    "request_permissions_tool", "agent_message_board", "use_agent_identity",
}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def mcp_header_names(codex_home: Path) -> list[str]:
    """Read only table-header metadata; never parse configuration values.

    A top-level inline assignment cannot be safely enumerated by this method.
    Managed/project entries are independently checked through filtered effective
    config before any thread is created.
    """
    path = codex_home / "config.toml"
    if not path.is_file():
        return []
    names: set[str] = set()
    with path.open(encoding="utf-8-sig") as source:
        for line in source:
            if re.match(r"\s*mcp_servers\s*=", line):
                raise RuntimeError("Inline MCP configuration requires separate review")
            if not re.match(r"\s*\[\s*mcp_servers(?:\s*\.|\s*\])", line):
                continue
            header = line.split("#", 1)[0].strip()
            parsed = tomllib.loads(header)
            names.update(parsed.get("mcp_servers", {}))
    return sorted(names)


def overrides(names: list[str], remote_code_mode_host: bool = False) -> dict:
    # Empty tables merge recursively; explicitly disable each known MCP name.
    return {
        "model": LAUNCH.MODEL,
        "model_reasoning_effort": LAUNCH.EFFORT,
        "model_provider": "openai",
        "forced_login_method": "chatgpt",
        "approval_policy": "never",
        "default_permissions": ":danger-full-access",
        "developer_instructions": "",
        "project_doc_max_bytes": 0,
        "project_doc_fallback_filenames": [],
        "notify": [],
        "web_search": "disabled",
        "features.skip_host_skill_discovery": True,
        "skills.include_instructions": False,
        "skills.bundled.enabled": False,
        "skills.config": [],
        "cloud.skills.enabled": False,
        "orchestrator.mcp.enabled": False,
        "mcp_servers": {name: {"enabled": False} for name in names},
        "history.persistence": "none",
        "analytics.enabled": False,
        "shell_environment_policy.inherit": "none",
        "shell_environment_policy.ignore_default_excludes": False,
        "shell_environment_policy.experimental_use_profile": False,
        **{f"features.{name}": False for name in sorted(DISABLED)},
        **({"features.code_mode_host": True} if remote_code_mode_host else {}),
    }


class Client:
    def __init__(self, args, command: list[str], env: dict[str, str]):
        self.args = args
        self.events = (args.evidence / "events.jsonl").open("x", encoding="utf-8")
        self.next_id = 0
        self.messages: queue.Queue = queue.Queue()
        self.pending_events: list[dict] = []
        self.bytes_seen = 0
        self.deadline = time.monotonic() + args.timeout
        flags = subprocess.CREATE_NO_WINDOW | 0x00000004 if os.name == "nt" else 0
        self.process = subprocess.Popen(command, cwd=args.host_cwd, env=env,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, creationflags=flags)
        try:
            self.job = LAUNCH.WindowsJob(self.process)
            LAUNCH.resume_suspended_process(self.process)
        except BaseException:
            self.process.kill()
            self.process.wait(timeout=5)
            raise
        for label, stream in (("stdout", self.process.stdout), ("stderr", self.process.stderr)):
            threading.Thread(target=self._drain, args=(label, stream), daemon=True).start()

    def _drain(self, label, stream):
        try:
            while True:
                data = stream.readline(MAX_BYTES + 1)
                if not data:
                    self.messages.put((label, None))
                    return
                self.messages.put((label, data))
        except Exception:
            self.messages.put((label, None))

    def log(self, value):
        serialized = json.dumps(value, ensure_ascii=False)
        for token in getattr(self.args, "redact_tokens", []):
            if token:
                serialized = serialized.replace(token, "[REDACTED_EPHEMERAL_CAPABILITY]")
        self.events.write(serialized + "\n")
        self.events.flush()
        os.fsync(self.events.fileno())

    def send(self, message):
        self.process.stdin.write((json.dumps(message) + "\n").encode())
        self.process.stdin.flush()

    def receive(self, *, return_notifications=False):
        while True:
            abort = getattr(self.args, 'abort_event', None)
            require(abort is None or not abort.is_set(), 'Qualified execution transport failed; stopping invocation')
            remaining = self.deadline - time.monotonic()
            require(remaining > 0, "Bounded app-server deadline exceeded")
            try:
                label, data = self.messages.get(timeout=min(remaining, 1))
            except queue.Empty:
                continue
            if data is None:
                require(label != "stdout", "App-server stdout closed")
                continue
            self.bytes_seen += len(data)
            require(self.bytes_seen <= MAX_BYTES, "App-server output limit exceeded")
            if label == "stderr":
                # Do not persist ambient diagnostics: they can contain config values.
                self.log({"kind": "stderr", "bytes": len(data)})
                continue
            msg = json.loads(data)
            if "method" in msg and "id" in msg:
                self.log({"kind": "unexpected_server_request", "method": msg["method"]})
                self.send({"id": msg["id"], "error": {"code": -32601, "message": "Host requests are disabled"}})
                raise RuntimeError("Unexpected app-server host/approval request")
            if "method" in msg:
                if msg["method"] == "configWarning":
                    params = msg.get("params", {})
                    safe = {key: params[key] for key in ("summary", "title", "message")
                            if isinstance(params.get(key), str)}
                    self.log({"kind": "config_warning", "field_names": sorted(params), **safe})
                    raise RuntimeError("App-server emitted a configuration warning")
                self.pending_events.append(msg)
                self.log({"kind": "notification", **msg})
                if return_notifications:
                    return msg
                continue
            return msg

    def call(self, method, params, *, private=False):
        self.next_id += 1
        request_id = self.next_id
        self.log({"kind": "request", "method": method, "id": request_id,
                  **({} if private else {"params": params})})
        self.send({"id": request_id, "method": method, "params": params})
        while True:
            msg = self.receive()
            require(msg.get("id") == request_id, "Unexpected app-server response id")
            if "error" in msg:
                self.log({"kind": "rpc_error", "method": method, "code": msg["error"].get("code"),
                          **({} if private else {"message": str(msg["error"].get("message", ""))[:4000]})})
                raise RuntimeError(f"App-server rejected {method}; code {msg['error'].get('code')}")
            if not private:
                self.log({"kind": "response", "method": method, **msg})
            return msg["result"]

    def wait_turn(self, turn_id: str):
        while True:
            for event in self.pending_events:
                if event.get("method") == "turn/completed" and event.get("params", {}).get("turn", {}).get("id") == turn_id:
                    return event["params"]["turn"]
            # Notifications are accumulated by receive; send no extra inference.
            self.receive(return_notifications=True)

    def close(self):
        finishing = getattr(self.args, 'client_finishing', None)
        if finishing is not None:
            finishing.set()
        try:
            self.process.stdin.close()
        except OSError:
            pass
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.job.close()
            self.process.wait(timeout=5)
        self.job.close()
        self.log({'kind': 'client_shutdown', 'exit_code': self.process.returncode})
        self.events.close()


def inspect_config(config: dict, names: list[str], remote_code_mode_host: bool = False) -> dict:
    mcp = config.get("mcp_servers", {})
    require(isinstance(mcp, dict), "Unexpected effective MCP representation")
    require(all(isinstance(v, dict) and v.get("enabled") is False for v in mcp.values()),
            "Effective configuration still contains an enabled MCP server")
    require(not config.get("model_instructions_file"), "Ambient model instructions file is configured")
    require(not config.get("experimental_instructions_file"), "Ambient experimental instructions file is configured")
    require(not config.get("instructions"), "Ambient base instructions are configured")
    require(not config.get("developer_instructions"), "Effective developer instructions are nonempty")
    require(not config.get("model_providers", {}).get("openai"), "OpenAI provider has an ambient override")
    features = config.get("features", {})
    disabled = DISABLED - {"code_mode_host"} if remote_code_mode_host else DISABLED
    require(all(features.get(name) is False or isinstance(features.get(name), dict) and features[name].get("enabled") is False for name in disabled),
            "A disabled capability is not disabled in effective config")
    if remote_code_mode_host:
        require(features.get("code_mode_host") is True or isinstance(features.get("code_mode_host"), dict)
                and features["code_mode_host"].get("enabled") is True, "Remote code-mode host is disabled")
    require(config.get("model_provider") == "openai", "Effective provider mismatch")
    require(config.get("web_search") == "disabled", "Web search is enabled")
    require(config.get("project_doc_max_bytes") == 0, "Automatic document discovery is enabled")
    return {"mcp_count": len(mcp), "mcp_all_disabled": True, "disabled_mcp_names": sorted(mcp),
            "header_names_count": len(names), "disabled_feature_count": len(disabled),
            "remote_code_mode_host_configured": remote_code_mode_host,
            "automatic_project_documents": False, "custom_instructions": False,
            "provider": "openai", "web_search": "disabled"}


def run(args):
    require(os.name == "nt", "This client is for the trusted Windows parent")
    parsed = urlsplit(args.exec_server_url)
    require(parsed.scheme == "ws" and parsed.hostname == "127.0.0.1" and parsed.port and not parsed.username and not parsed.password,
            "Executor must be an explicit IPv4 loopback WebSocket")
    remote_uri = urlsplit(args.remote_cwd)
    require(remote_uri.scheme == "file" and not remote_uri.netloc and remote_uri.path.startswith("/"),
            "Remote metadata cwd must be a canonical POSIX file URI")
    remote_path = unquote(remote_uri.path)
    code_mode_host_url = getattr(args, "code_mode_host_url", None)
    if code_mode_host_url:
        code_host = urlsplit(code_mode_host_url)
        require(code_host.scheme == "http" and code_host.hostname == "127.0.0.1" and code_host.port
                and not code_host.username and not code_host.password and code_host.path in ("", "/")
                and not code_host.query and not code_host.fragment,
                "Code-mode host must be an explicit IPv4 loopback HTTP endpoint without path/query/credentials")
    require(args.host_cwd.is_dir(), "Host cwd must exist")
    require(not (args.host_cwd / ".codex").exists(), "Host cwd contains project configuration")
    require(not (args.codex_home / "environments.toml").exists(), "Ambient environments.toml prevents remote-only startup")
    args.evidence.mkdir(parents=True, exist_ok=False)
    names = mcp_header_names(args.codex_home)
    config = overrides(names, bool(code_mode_host_url))
    command = [str(LAUNCH.CODEX), "app-server", "--stdio", "--strict-config", *LAUNCH.config_args(config)]
    if code_mode_host_url:
        command.extend(("--code-mode-host", code_mode_host_url))
    env = LAUNCH.clean_environment(args.codex_home)
    env["CODEX_EXEC_SERVER_URL"] = "none"
    LAUNCH.write_json(args.evidence / "launch.json", {
        "started_utc": LAUNCH.utc(), "binary": str(LAUNCH.CODEX),
        "binary_sha256": LAUNCH.sha256(LAUNCH.CODEX), "host_cwd": str(args.host_cwd),
        "remote_cwd": args.remote_cwd, "timeout_seconds": args.timeout,
        "model_requested": LAUNCH.MODEL, "reasoning_effort_requested": LAUNCH.EFFORT,
        "bootstrap_requested": args.run_bootstrap, "bootstrap": BOOTSTRAP,
        "mcp_headers_disabled": len(names), "config_overrides": config,
        "remote_code_mode_host_configured": bool(code_mode_host_url),
        "executor_url_recorded": False, "outer_namespace_authoritative": True})
    client = None
    result = {"success": False, "model_started": False}
    try:
        client = Client(args, command, env)
        client.call("initialize", {"clientInfo": {"name": "robot-isolation-session9", "version": "1"},
                                  "capabilities": {"experimentalApi": True}})
        client.send({"method": "initialized", "params": {}})
        effective = client.call("config/read", {"includeLayers": False, "cwd": str(args.host_cwd)}, private=True)
        result["effective_config"] = inspect_config(effective["config"], names, bool(code_mode_host_url))
        del effective
        account = client.call("account/read", {"refreshToken": False}, private=True)
        result["auth_type"] = (account.get("account") or {}).get("type")
        require(result["auth_type"] == "chatgpt", "ChatGPT login is not available; no API fallback")
        del account
        local = client.call("environment/status", {"environmentId": "local"})
        require(local.get("status") == "unknown", "A local execution environment is configured")
        client.call("environment/add", {"environmentId": "robot-qualified", "execServerUrl": args.exec_server_url, "connectTimeoutMs": 15000}, private=True)
        remote = client.call("environment/info", {"environmentId": "robot-qualified"})
        require(remote.get("shell", {}).get("path", "").startswith("/"), "Executor did not report a POSIX shell")
        require(remote.get("cwd") == args.remote_cwd, "Executor cwd differs from qualified workspace")
        # environment/info returns a URI; thread/turn selection accepts native
        # absolute path syntax and creates its own PathUri internally.
        environments = [{"environmentId": "robot-qualified", "cwd": remote_path, "runtimeWorkspaceRoots": [remote_path]}]
        thread = client.call("thread/start", {"cwd": str(args.host_cwd), "model": LAUNCH.MODEL,
            "modelProvider": "openai", "approvalPolicy": "never", "sandbox": "danger-full-access",
            "developerInstructions": "", "environments": environments,
            "ephemeral": True, "dynamicTools": [], "selectedCapabilityRoots": [],
            "allowProviderModelFallback": False})
        require(thread.get("model") == LAUNCH.MODEL, "Model fallback detected")
        require(thread.get("modelProvider") == "openai", "Provider fallback detected")
        require(thread.get("reasoningEffort") == LAUNCH.EFFORT, "Reasoning effort fallback detected")
        require(thread.get("instructionSources") == [], "Automatic instruction sources were loaded")
        thread_id = thread["thread"]["id"]
        mcp_status = client.call("mcpServerStatus/list", {"threadId": thread_id, "limit": 100}, private=True)
        require(isinstance(mcp_status.get("data"), list), "Unexpected MCP inventory representation")
        mcp_summary = [{"field_names": sorted(entry), "name": entry.get("name"),
                        **{key: entry[key] for key in ("enabled", "status", "runtimeStatus") if key in entry},
                        "tools_count": len(entry.get("tools", {})),
                        "resources_count": len(entry.get("resources", [])),
                        "resource_templates_count": len(entry.get("resourceTemplates", []))}
                       for entry in mcp_status["data"]]
        client.log({"kind": "mcp_inventory_summary", "entries": mcp_summary,
                    "has_more": bool(mcp_status.get("nextCursor"))})
        disabled_names = result["effective_config"]["disabled_mcp_names"]
        # The status endpoint deliberately includes configured disabled servers;
        # an entry is not evidence of a usable tool. Require explicit disabled
        # thread-runtime state plus the independently disabled effective config.
        require(not mcp_status.get("nextCursor") and all(
            entry.get("name") in disabled_names and entry.get("runtimeStatus") == "disabled"
            and entry.get("tools") == {} and entry.get("resources") == []
            and entry.get("resourceTemplates") == [] and entry.get("toolsError") is None
            and entry.get("serverInfo") is None and entry.get("serverCapabilities") is None
            for entry in mcp_status["data"]), "Thread has an active or unverified MCP server inventory")
        ready = client.call("environment/status", {"environmentId": "robot-qualified"})
        require(ready.get("status") == "ready", "Qualified executor is not ready")
        require(client.call("environment/status", {"environmentId": "local"}).get("status") == "unknown", "Local executor appeared")
        result.update(preflight_passed=True, thread_id=thread_id, model_effective=thread["model"],
                      effort_effective=thread["reasoningEffort"], instruction_sources=[],
                      mcp_active_servers=[], mcp_catalog=mcp_summary)
        LAUNCH.write_json(args.evidence / "preflight.json", result)
        if args.run_bootstrap:
            # The only call that starts a model. No repair or fallback call exists.
            turn = client.call("turn/start", {"threadId": thread_id,
                "input": [{"type": "text", "text": BOOTSTRAP, "text_elements": []}],
                "model": LAUNCH.MODEL, "effort": LAUNCH.EFFORT,
                "approvalPolicy": "never", "environments": environments,
                "sandboxPolicy": {"type": "externalSandbox", "networkAccess": "enabled"}})
            result["model_started"] = True
            completed = client.wait_turn(turn["turn"]["id"])
            result["turn_status"] = completed.get("status")
            require(completed.get("status") == "completed", "Bootstrap turn did not complete")
        result["success"] = True
    except Exception as error:
        result["error"] = str(error)
    finally:
        if client:
            client.close()
        result["finished_utc"] = LAUNCH.utc()
        LAUNCH.write_json(args.evidence / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exec-server-url", required=True)
    parser.add_argument("--host-cwd", required=True, type=Path)
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--remote-cwd", default="file:///workspace")
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--run-bootstrap", action="store_true")
    parser.add_argument("--code-mode-host-url", help="Qualified namespace code-host gRPC bridge; never a local-host fallback")
    args = parser.parse_args()
    require(1 <= args.timeout <= 900, "Timeout must be between 1 and 900 seconds")
    result = run(args)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
