"""Bounded, fail-closed launcher for the first Robot-Codex binding.

The development process invokes this file. It is never copied into the robot
workspace. No authentication file is opened, parsed, copied, or modified.
"""
from __future__ import annotations

import argparse
import base64
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

CODEX = Path(r"C:\Users\cresp\.codex\packages\app-server-daemon\releases\0.157.1-x86_64-pc-windows-msvc\bin\codex.exe")
MODEL = "gpt-6-astra"
EFFORT = "max"
BOOTSTRAP = "Follow the instructions in RobotAgentPrompt.md."
REQUIRED_FILES = ("RobotAgentPrompt.md", "AGENTS.md", "Tasks.md", "Robot.md", "Tools.md", "Continuity.md", "live/activation.json", "live/state.json")
DISABLED_FEATURES = (
    "multi_agent", "multi_agent_v2", "apps", "plugins", "hooks", "memories",
    "external_agent_memory_import", "browser_use", "browser_use_external",
    "browser_use_full_cdp_access", "in_app_browser", "computer_use",
    "recommended_plugins", "skill_search", "skill_mcp_dependency_install",
    "shell_snapshot", "shell_snapshot_v2", "code_mode", "code_mode_host",
    "code_mode_only", "code_mode_prewarm",
)
MAX_OUTPUT = 32 * 1024 * 1024
BASE_PYTHON = Path(r"C:\Users\cresp\AppData\Local\Programs\Python\Python312\python.exe")
WINDOWS_POWERSHELL = Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")
PWSH_DIRECTORY = Path(r"C:\Users\cresp\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell")


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inside(child: Path, parent: Path) -> bool:
    return child.resolve().is_relative_to(parent.resolve())


def checked_paths(workspace: Path, evidence: Path, repo: Path, codex_home: Path) -> None:
    if not workspace.is_dir():
        raise ValueError("The configured external workspace does not exist")
    for protected in (repo, codex_home):
        if inside(workspace, protected) or inside(protected, workspace):
            raise ValueError("Workspace must be disjoint from the research repository and CODEX_HOME")
    if inside(evidence, workspace) or inside(workspace, evidence):
        raise ValueError("Evidence and workspace must be disjoint")
    for name in REQUIRED_FILES:
        candidate = workspace / name
        if not candidate.is_file() or not inside(candidate, workspace):
            raise ValueError(f"Missing or escaping configured workspace file: {name}")
    for directory in (workspace, workspace / "notes", workspace / "programs", workspace / "live"):
        if not directory.is_dir() or directory.is_symlink() or directory.is_junction():
            raise ValueError(f"Workspace directories must be real directories: {directory}")
    # A project-local config could supersede parts of the chosen runtime policy.
    if (workspace / ".codex").exists() or (workspace / ".git").exists():
        raise ValueError("Runtime workspace must not contain .codex or .git configuration")
    for candidate in workspace.rglob("*"):
        if candidate.is_symlink() or candidate.is_junction():
            raise ValueError("Runtime workspace must not contain symlinks or junctions")


def prepare_workspace(template: Path, workspace: Path, repo: Path, codex_home: Path) -> None:
    if workspace.exists():
        raise ValueError("Refusing to overwrite an existing runtime workspace")
    for protected in (repo, codex_home):
        if inside(workspace, protected) or inside(protected, workspace):
            raise ValueError("Runtime copy must be disjoint from the repository and CODEX_HOME")
    for candidate in template.rglob("*"):
        if candidate.is_symlink() or candidate.is_junction() or candidate.name in (".codex", ".git"):
            raise ValueError("Template contains forbidden config or linked paths")
    shutil.copytree(template, workspace)


def clean_environment(codex_home: Path | None = None) -> dict[str, str]:
    # Filter names only. Values are neither logged nor inspected.
    result = {key: value for key, value in os.environ.items()
              if not re.search(r"KEY|TOKEN|SECRET|PASSWORD|^OPENAI|^CODEX|^PYTHON(PATH|HOME)$", key, re.I)}
    if codex_home is not None:
        result["CODEX_HOME"] = str(codex_home)
    return result


def toml_string(value: str) -> str:
    # JSON basic strings are compatible with TOML for the strings used here.
    return json.dumps(value, ensure_ascii=False)


def fixed_drive_roots() -> list[str]:
    if os.name != "nt":
        return []
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetDriveTypeW.argtypes = [ctypes.c_wchar_p]
    kernel.GetDriveTypeW.restype = ctypes.c_uint
    return [f"{chr(code)}:/" for code in range(ord("A"), ord("Z") + 1)
            if kernel.GetDriveTypeW(f"{chr(code)}:\\") == 3]


def profile(workspace: Path, repo: Path, codex_home: Path, evidence: Path, loopback: bool = False, boundary: str = "root-deny") -> dict[str, Any]:
    paths = {
        ":root": "deny" if boundary == "root-deny" else "read", ":minimal": "read", ":tmpdir": "deny", ":slash_tmp": "deny",
        workspace.resolve().as_posix(): "read",
        (workspace / "Continuity.md").resolve().as_posix(): "write",
        (workspace / "notes").resolve().as_posix(): "write",
        (workspace / "programs").resolve().as_posix(): "write",
        repo.resolve().as_posix(): "deny",
        codex_home.resolve().as_posix(): "deny",
        evidence.resolve().as_posix(): "deny",
        BASE_PYTHON.parent.resolve().as_posix(): "read",
    }
    if boundary == "users-deny":
        paths["C:/Users"] = "deny"
        paths[PWSH_DIRECTORY.resolve().as_posix()] = "read"
        paths.update({drive: "deny" for drive in fixed_drive_roots() if drive.lower() != "c:/"})
    if boundary == "bootstrap-diagnostic":
        paths[(workspace.parent / "fake-protected").resolve().as_posix()] = "deny"
    return {"filesystem": paths, "network": {"enabled": loopback, **({"domains": {"127.0.0.1": "allow"}} if loopback else {})}}


def inline_toml(value: Any) -> str:
    if isinstance(value, dict):
        return "{" + ",".join(toml_string(key) + "=" + inline_toml(item) for key, item in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ",".join(inline_toml(item) for item in value) + "]"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return toml_string(value)


def configuration(workspace: Path, repo: Path, codex_home: Path, evidence: Path, loopback: bool, boundary: str = "root-deny") -> dict[str, Any]:
    return {
        "default_permissions": "robot_runtime",
        "permissions.robot_runtime": profile(workspace, repo, codex_home, evidence, loopback, boundary),
        "approval_policy": "never", "windows.sandbox": "elevated",
        "windows.sandbox_private_desktop": True,
        "model": MODEL, "model_reasoning_effort": EFFORT,
        "web_search": "disabled", "features.network_proxy": loopback,
        "features.skip_host_skill_discovery": True,
        "project_doc_max_bytes": 0,
        "developer_instructions": "",
        "shell_environment_policy.inherit": "core",
        "shell_environment_policy.ignore_default_excludes": False,
        "shell_environment_policy.experimental_use_profile": False,
        "shell_environment_policy.filters": {
            "CODEX*": "exclude", "OPENAI*": "exclude", "*TOKEN*": "exclude",
            "*SECRET*": "exclude", "*PASSWORD*": "exclude", "*KEY*": "exclude",
            "PYTHONPATH": "exclude", "PYTHONHOME": "exclude",
        },
        # Image observation must be separately qualified and bound by the host.
        "tools.view_image": False,
        "history.persistence": "none",
        **{f"features.{name}": False for name in DISABLED_FEATURES},
    }


def config_args(config: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for key, value in config.items():
        result.extend(("-c", key + "=" + inline_toml(value)))
    return result


def residual_read_scope(boundary: str) -> str:
    if boundary == "users-deny":
        return "System drive paths outside denied Users/protected trees remain readable"
    if boundary == "bootstrap-diagnostic":
        return "Other user and system files remain potentially readable; NOT adequate robot or scored isolation"
    return "Codex minimal runtime plus explicit base Python directory"


class WindowsJob:
    """Close kills all owned children, including tools surviving their parent."""

    def __init__(self, process: subprocess.Popen[bytes]):
        self.handle = None
        if os.name != "nt":
            return
        from ctypes import wintypes
        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount", "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]
        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", IO), ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.kernel.SetInformationJobObject.restype = wintypes.BOOL
        self.kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        handle = self.kernel.CreateJobObjectW(None, None)
        if not handle:
            raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
        limits = Extended()
        limits.BasicLimitInformation.LimitFlags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)) or not self.kernel.AssignProcessToJobObject(handle, int(process._handle)):
            error = ctypes.get_last_error()
            self.kernel.CloseHandle(handle)
            raise OSError(error, "Cannot contain the launcher process in a kill-on-close job")
        self.handle = handle

    def close(self) -> None:
        if self.handle is not None:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def resume_suspended_process(process: subprocess.Popen[bytes]) -> None:
    """Resume only after Job Object assignment; Popen closes its thread handle."""
    if os.name != "nt":
        return
    from ctypes import wintypes
    class ThreadEntry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ThreadID", wintypes.DWORD), ("th32OwnerProcessID", wintypes.DWORD),
                    ("tpBasePri", wintypes.LONG), ("tpDeltaPri", wintypes.LONG), ("dwFlags", wintypes.DWORD)]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry)]
    kernel.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry)]
    kernel.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenThread.restype = wintypes.HANDLE
    kernel.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel.ResumeThread.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(0x00000004, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(), "Cannot find suspended process thread")
    resumed = 0
    try:
        entry = ThreadEntry()
        entry.dwSize = ctypes.sizeof(entry)
        found = kernel.Thread32First(snapshot, ctypes.byref(entry))
        while found:
            if entry.th32OwnerProcessID == process.pid:
                thread = kernel.OpenThread(0x0002, False, entry.th32ThreadID)
                if not thread:
                    raise OSError(ctypes.get_last_error(), "Cannot open suspended process thread")
                try:
                    if kernel.ResumeThread(thread) == 0xFFFFFFFF:
                        raise OSError(ctypes.get_last_error(), "Cannot resume contained process")
                    resumed += 1
                finally:
                    kernel.CloseHandle(thread)
            found = kernel.Thread32Next(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    if resumed != 1:
        raise RuntimeError(f"Expected one suspended primary thread; found {resumed}")


def bounded_process(command: list[str], cwd: Path, evidence: Path, timeout: float, *, stdin: str | None = None, env: dict[str, str] | None = None, max_output: int = MAX_OUTPUT) -> dict[str, Any]:
    evidence.mkdir(parents=True, exist_ok=False)
    write_json(evidence / "command.json", {"argv": command, "cwd": str(cwd), "started_utc": utc(), "timeout_seconds": timeout})
    started = time.monotonic()
    process = subprocess.Popen(command, cwd=cwd, env=env if env is not None else clean_environment(), stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000004) if os.name == "nt" else 0,
                               start_new_session=os.name != "nt")
    try:
        job = WindowsJob(process)
        resume_suspended_process(process)
    except BaseException:
        process.kill()
        process.wait(timeout=5)
        raise
    overflow = threading.Event()
    readers: list[threading.Thread] = []
    def drain(stream: Any, destination: Path) -> None:
        total = 0
        with destination.open("wb") as target:
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    break
                remaining = max_output - total
                target.write(chunk[:max(remaining, 0)])
                total += len(chunk)
                if total > max_output:
                    overflow.set()
        stream.close()
    for stream, filename in ((process.stdout, "stdout.txt"), (process.stderr, "stderr.txt")):
        reader = threading.Thread(target=drain, args=(stream, evidence / filename), daemon=True)
        reader.start()
        readers.append(reader)
    if stdin is not None:
        assert process.stdin is not None
        process.stdin.write(stdin.encode("utf-8"))
        process.stdin.close()
    reason = None
    try:
        while process.poll() is None:
            if overflow.is_set():
                reason = "output_limit"
                break
            if time.monotonic() - started > timeout:
                reason = "timeout"
                break
            time.sleep(0.05)
    finally:
        if os.name == "nt":
            job.close()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        for reader in readers:
            reader.join(timeout=5)
    if overflow.is_set() and reason is None:
        reason = "output_limit"
    result = {"exit_code": process.returncode, "termination_reason": reason, "elapsed_seconds": round(time.monotonic() - started, 3), "finished_utc": utc(), "process_tree_cleanup": True}
    write_json(evidence / "result.json", result)
    return result


def selected_catalog(catalog: Any) -> dict[str, Any]:
    models = catalog if isinstance(catalog, list) else catalog.get("models", catalog.get("data", []))
    selected = [entry for entry in models if entry.get("slug", entry.get("id")) == MODEL]
    if len(selected) != 1:
        raise ValueError("Pinned model missing or ambiguous in the installed catalog")
    entry = selected[0]
    keys = ("slug", "id", "display_name", "supported_reasoning_levels", "default_reasoning_level", "context_window", "effective_context_window_percent", "supports_reasoning_summaries", "supported_in_api")
    metadata = {key: entry[key] for key in keys if key in entry}
    levels = entry.get("supported_reasoning_levels", [])
    level_names = [level.get("effort") if isinstance(level, dict) else level for level in levels]
    if EFFORT not in level_names:
        raise ValueError("Pinned reasoning effort is unavailable in the installed catalog")
    return metadata


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def verify_header(stdout: str, stderr: str) -> dict[str, Any]:
    """Only the CLI's startup preamble qualifies, never model prose."""
    # Standard exec writes its human startup/interaction stream to stderr and
    # its final model answer to stdout. Never accept an apparent stdout header.
    for stream_name, text in (("stderr", stderr),):
        user_boundary = re.search(r"(?m)^user\r?$", text)
        if not user_boundary:
            continue
        text = text[:user_boundary.end()]
        match = re.search(r"(?m)^OpenAI Codex v([^\r\n]+)\r?$", text)
        if not match:
            continue
        end = re.search(r"(?m)^user\r?$", text[match.end():])
        if not end:
            continue
        header = text[match.start():match.end() + end.start()]
        model = re.search(r"(?m)^model:\s*(\S+)\s*$", header)
        effort = re.search(r"(?m)^reasoning effort:\s*(\S+)\s*$", header)
        sandbox = re.search(r"(?m)^sandbox:\s*(.+)$", header)
        if not model or not effort:
            continue
        evidence = {"source": "cli_startup_header", "stream": stream_name, "version": match.group(1), "model": model.group(1), "reasoning_effort": effort.group(1), "sandbox_header": sandbox.group(1).strip() if sandbox else None}
        evidence["matches_pinned_model"] = evidence["model"] == MODEL and evidence["reasoning_effort"] == EFFORT and evidence["version"].startswith("0.157.1")
        return evidence
    return {"source": None, "matches_pinned_model": False, "error": "No independently verifiable CLI startup model/effort header was captured"}


def preflight(args: argparse.Namespace) -> dict[str, Any]:
    checked_paths(args.workspace, args.evidence, args.repo, args.codex_home)
    if not CODEX.is_file():
        raise ValueError("The pinned Codex 0.157.1 binary is unavailable")
    manifest = {name: sha256(args.workspace / name) for name in REQUIRED_FILES}
    manifest.update({"robot.py": sha256(args.workspace / "robot.py")} if (args.workspace / "robot.py").is_file() else {})
    config = configuration(args.workspace, args.repo, args.codex_home, args.evidence, args.loopback, args.boundary_profile)
    args.evidence.mkdir(parents=True, exist_ok=True)
    write_json(args.evidence / "launch_policy.json", {"created_utc": utc(), "binary": str(CODEX), "binary_sha256": sha256(CODEX), "model": MODEL, "effort": EFFORT, "bootstrap": BOOTSTRAP, "bootstrap_sha256": hashlib.sha256(BOOTSTRAP.encode()).hexdigest(), "workspace": str(args.workspace), "workspace_files": manifest, "config": config, "boundary_profile": args.boundary_profile, "residual_read_scope": residual_read_scope(args.boundary_profile), "generated_program_execution": "Dedicated program runner unavailable; advisory no-program instruction; sandboxed shell remains programmable", "network_limit": "127.0.0.1 host only; domain policy does not distinguish ports" if args.loopback else "disabled", "auth_handling": "Codex login status only; no credential file access", "qualification": "preflight metadata only; sentinel and actual startup evidence required"})
    environment = clean_environment(args.codex_home)
    version = bounded_process([str(CODEX), "--version"], args.workspace, args.evidence / "version", 15, env=environment)
    if version["exit_code"] != 0 or "codex-cli 0.157.1" not in read_text(args.evidence / "version/stdout.txt"):
        raise ValueError("Pinned binary version check failed")
    auth = bounded_process([str(CODEX), "login", "status"], args.workspace, args.evidence / "auth_status", 20, env=environment)
    status = read_text(args.evidence / "auth_status/stdout.txt") + read_text(args.evidence / "auth_status/stderr.txt")
    if auth["exit_code"] != 0 or "Logged in using ChatGPT" not in status:
        raise ValueError("Existing ChatGPT authorization was not confirmed; no login or credential copy attempted")
    catalog = bounded_process([str(CODEX), "debug", "models", "--bundled"], args.workspace, args.evidence / "catalog", 20, env=environment)
    if catalog["exit_code"] != 0:
        raise ValueError("Bundled model catalog failed")
    metadata = selected_catalog(json.loads(read_text(args.evidence / "catalog/stdout.txt")))
    write_json(args.evidence / "model_catalog_metadata.json", metadata)
    # Default shipped model instructions are public product data, but do not retain
    # the whole catalog on success when the narrow metadata suffices.
    (args.evidence / "catalog/stdout.txt").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return {"preflight": "passed", "model": MODEL, "effort": EFFORT, "auth": "existing ChatGPT login", "config": config, "workspace_files": manifest}


def policy_digest(config: dict[str, Any], evidence: Path) -> str:
    normalized = json.loads(json.dumps(config))
    # Evidence paths differ per run, are disjoint from workspace, and already
    # denied by :root. Exclude only that redundant entry from binding.
    normalized["permissions.robot_runtime"]["filesystem"].pop(evidence.resolve().as_posix(), None)
    return hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()


def sentinel(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    if args.loopback:
        raise ValueError("This sentinel qualifies only the no-network bootstrap; loopback requires a separate gateway/network probe")
    scratch = (args.workspace.parent / "fake-protected" / uuid.uuid4().hex) if args.boundary_profile == "bootstrap-diagnostic" else args.workspace.parent / ("denied-synthetic-" + uuid.uuid4().hex)
    scratch.mkdir(parents=True)
    denied_paths = []
    for area in ("home", "developer", "credentials"):
        (scratch / area).mkdir()
        canary = scratch / area / "artificial_canary.txt"
        canary.write_text("ARTIFICIAL-DENIED-CONTENT", encoding="utf-8")
        denied_paths.append(canary)
    public = args.workspace / "live" / "sandbox_probe_public.txt"
    public.write_text("ARTIFICIAL-PUBLIC-CONTENT", encoding="utf-8")
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    def ps_literal(path: Path) -> str:
        return "'" + str(path).replace("'", "''") + "'"
    script = f"""
$ErrorActionPreference = 'Stop'
$checks = [ordered]@{{}}
try {{ $checks['workspace_read'] = [IO.File]::ReadAllText({ps_literal(public)}) -eq 'ARTIFICIAL-PUBLIC-CONTENT' }} catch {{ $checks['workspace_read'] = $false }}
{''.join("try { [IO.File]::ReadAllText(" + ps_literal(canary) + ") | Out-Null; $checks['" + canary.parent.name + "_canary_denied'] = $false } catch [UnauthorizedAccessException] { $checks['" + canary.parent.name + "_canary_denied'] = $true } catch { $checks['" + canary.parent.name + "_canary_denied'] = $false }\n" for canary in denied_paths)}
try {{ $handle = [IO.File]::Open({ps_literal(args.workspace / 'Tools.md')}, 'Open', 'Write', 'ReadWrite'); $handle.Close(); $checks['trusted_write_denied'] = $false }} catch [UnauthorizedAccessException] {{ $checks['trusted_write_denied'] = $true }} catch {{ $checks['trusted_write_denied'] = $false }}
try {{ $handle = [IO.File]::Open({ps_literal(args.workspace / 'Continuity.md')}, 'Open', 'Write', 'ReadWrite'); $handle.Close(); $checks['continuity_write'] = $true }} catch {{ $checks['continuity_write'] = $false }}
foreach ($area in @('notes', 'programs')) {{
  $target = [IO.Path]::Combine({ps_literal(args.workspace)}, $area, '_synthetic_probe.txt')
  try {{ [IO.File]::WriteAllText($target, 'ARTIFICIAL-WRITE'); $checks[$area + '_write'] = [IO.File]::ReadAllText($target) -eq 'ARTIFICIAL-WRITE'; [IO.File]::Delete($target) }} catch {{ $checks[$area + '_write'] = $false }}
}}
$client = [Net.Sockets.TcpClient]::new()
try {{ $pending = $client.BeginConnect('127.0.0.1', {port}, $null, $null); if ($pending.AsyncWaitHandle.WaitOne(1500)) {{ $client.EndConnect($pending); $checks['loopback_denied'] = $false }} else {{ $checks['loopback_denied'] = $true }} }} catch {{ $checks['loopback_denied'] = $true }} finally {{ $client.Close() }}
$checks | ConvertTo-Json -Compress
"""
    encoded = base64.b64encode(script.encode("utf-16-le")).decode()
    executable = [str(WINDOWS_POWERSHELL), "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]
    if args.boundary_profile == "bootstrap-diagnostic":
        # Open directory handles with LIST_DIRECTORY permission, without listing
        # names or reading any protected content. No PowerShell Add-Type/temp DLL.
        python_script = '''import ctypes,json,socket
from pathlib import Path
from ctypes import wintypes
workspace=Path(WORKSPACE)
checks={}
checks['workspace_read']=(workspace/'live/sandbox_probe_public.txt').read_text()=='ARTIFICIAL-PUBLIC-CONTENT'
for label,path in CANARIES:
    try:
        Path(path).read_bytes()
        checks[label+'_canary_denied']=False
    except PermissionError:
        checks[label+'_canary_denied']=True
    except OSError:
        checks[label+'_canary_denied']=False
try:
    with (workspace/'Tools.md').open('r+b'): pass
    checks['trusted_write_denied']=False
except PermissionError:
    checks['trusted_write_denied']=True
try:
    with (workspace/'Continuity.md').open('r+b'): pass
    checks['continuity_write']=True
except OSError:
    checks['continuity_write']=False
for area in ['notes','programs']:
    target=workspace/area/'_synthetic_probe.txt'
    try:
        target.write_text('ARTIFICIAL-WRITE')
        checks[area+'_write']=target.read_text()=='ARTIFICIAL-WRITE'
        target.unlink()
    except OSError:
        checks[area+'_write']=False
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
kernel.CreateFileW.restype=wintypes.HANDLE
kernel.CloseHandle.argtypes=[wintypes.HANDLE]
for label,path in PROTECTED:
    handle=kernel.CreateFileW(path,1,7,None,3,0x02000000,None)
    if handle==ctypes.c_void_p(-1).value:
        checks[label+'_list_handle_denied']=ctypes.get_last_error()==5
    else:
        kernel.CloseHandle(handle)
        checks[label+'_list_handle_denied']=False
try:
    with socket.create_connection(('127.0.0.1',PORT),timeout=1.5): pass
    checks['loopback_denied']=False
except OSError:
    checks['loopback_denied']=True
print(json.dumps(checks))
'''.replace('WORKSPACE', repr(str(args.workspace))).replace('CANARIES', repr([(path.parent.name, str(path)) for path in denied_paths])).replace('PROTECTED', repr([('repository', str(args.repo)), ('codex_home', str(args.codex_home))])).replace('PORT', str(port))
        executable = [str(BASE_PYTHON), "-X", "utf8", "-B", "-c", python_script]
    # -P selects the explicit profile even when the ambient user's legacy
    # sandbox_mode exists. No model session or setup command is involved.
    command = [str(CODEX), "sandbox", "-P", "robot_runtime", "-C", str(args.workspace), *config_args(config), "--", *executable]
    try:
        run = bounded_process(command, args.workspace, args.evidence / "sentinel", 30, env=clean_environment(args.codex_home))
    finally:
        listener.close()
        # Delete only these exact task-created files, never recursively.
        public.unlink(missing_ok=True)
        for canary in denied_paths:
            canary.unlink(missing_ok=True)
            canary.parent.rmdir()
        scratch.rmdir()
    output = read_text(args.evidence / "sentinel/stdout.txt")
    try:
        checks = json.loads(output.strip())
    except json.JSONDecodeError:
        checks = {}
    expected = ("workspace_read", "home_canary_denied", "developer_canary_denied", "credentials_canary_denied", "trusted_write_denied", "continuity_write", "notes_write", "programs_write", "loopback_denied")
    if args.boundary_profile == "bootstrap-diagnostic":
        expected += ("repository_list_handle_denied", "codex_home_list_handle_denied")
    qualified = run["exit_code"] == 0 and run["termination_reason"] is None and all(checks.get(name) is True for name in expected)
    result = {"qualified": qualified, "workspace": str(args.workspace), "loopback": args.loopback, "boundary_profile": args.boundary_profile, "policy_sha256": policy_digest(config, args.evidence), "binary_sha256": sha256(CODEX), "checks": checks, "process": run, "probe_scope": "Artificial public/denied files only; no repository, evaluator, or credential contents were read", "setup_boundary": "Used existing ready native sandbox; no setup API, manual account or ACL operation requested; sandbox may apply its normal permission boundaries", "limitations": ["Bounded sentinel evidence, not proof against every OS escape", "Actual protected file contents deliberately unprobed", "Dedicated program runner unavailable; advisory no-program instruction; sandboxed shell remains programmable", residual_read_scope(args.boundary_profile)]}
    write_json(args.evidence / "sentinel_qualification.json", result)
    return result


def execution_command(args: argparse.Namespace, config: dict[str, Any]) -> list[str]:
    return [str(CODEX), "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral", "--strict-config", "--skip-git-repo-check", "--color", "never", "-C", str(args.workspace), "-m", MODEL, *config_args(config), "-"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "preflight", "sentinel", "run"))
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True, help="Fresh operator-owned evidence directory outside the robot workspace")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))))
    parser.add_argument("--loopback", action="store_true", help="Permit only 127.0.0.1 through Codex's network proxy; port separation is not claimed")
    parser.add_argument("--boundary-profile", choices=("root-deny", "users-deny", "bootstrap-diagnostic"), default="root-deny", help="Alternatives must be selected explicitly; bootstrap-diagnostic leaves other user/system files readable and is not adequate robot isolation")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--sentinel-evidence", type=Path, help="Required for run: successful same-policy sentinel result")
    parser.add_argument("--template", type=Path, help="Required for prepare: configured source template, copied once without modifying it")
    args = parser.parse_args()
    args.workspace, args.evidence, args.repo, args.codex_home = [path.resolve() for path in (args.workspace, args.evidence, args.repo, args.codex_home)]
    if args.evidence.exists():
        parser.error("Use a fresh evidence directory; previous successful and failed checks are retained")
    try:
        if args.mode == "prepare":
            if args.template is None:
                raise ValueError("Prepare requires --template")
            prepare_workspace(args.template.resolve(), args.workspace, args.repo, args.codex_home)
        result = preflight(args)
        config = result.pop("config")
        command = execution_command(args, config)
        write_json(args.evidence / "proposed_exec_command.json", command)
        if args.mode == "sentinel":
            result["sentinel"] = sentinel(args, config)
            result["passed"] = result["sentinel"]["qualified"]
        if args.mode == "run":
            if args.boundary_profile != "root-deny":
                if args.loopback or "bootstrap-smoke-001" not in read_text(args.workspace / "Tasks.md") or "NO-ACTUATOR-BOOTSTRAP-173" not in read_text(args.workspace / "Robot.md"):
                    raise ValueError("Development alternative is restricted to the explicitly configured no-actuator bootstrap fixture")
            if args.sentinel_evidence is None:
                raise ValueError("Run requires a successful independently recorded sentinel probe")
            qualification = json.loads(args.sentinel_evidence.read_text(encoding="utf-8"))
            if qualification.get("qualified") is not True or qualification.get("workspace") != str(args.workspace) or qualification.get("loopback") != args.loopback:
                raise ValueError("Sentinel result does not qualify this workspace/network policy")
            if qualification.get("policy_sha256") != policy_digest(config, args.evidence) or qualification.get("binary_sha256") != sha256(CODEX):
                raise ValueError("Policy or installed binary changed after the sentinel qualification")
            run = bounded_process(command, args.workspace, args.evidence / "exec", args.timeout, stdin=BOOTSTRAP + "\n", env=clean_environment(args.codex_home))
            model_evidence = verify_header(read_text(args.evidence / "exec/stdout.txt"), read_text(args.evidence / "exec/stderr.txt"))
            write_json(args.evidence / "effective_model_evidence.json", model_evidence)
            result["exec"] = run
            result["effective_model"] = model_evidence
            result["passed"] = run["exit_code"] == 0 and run["termination_reason"] is None and model_evidence["matches_pinned_model"]
        write_json(args.evidence / "summary.json", result)
        print(json.dumps({key: value for key, value in result.items() if key != "workspace_files"}, indent=2))
        return 0 if result.get("passed", True) else 1
    except Exception as error:
        args.evidence.mkdir(parents=True, exist_ok=True)
        write_json(args.evidence / "failure.json", {"utc": utc(), "error": str(error), "exception_type": type(error).__name__})
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
