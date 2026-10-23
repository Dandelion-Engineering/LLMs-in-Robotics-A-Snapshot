#!/usr/bin/env python3
"""A single-slot, project-fair compute queue for this desktop."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from typing import Any, Callable, Iterator, Sequence


STATE_VERSION = 1
PROJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
TERMINAL_STATES = {
    "succeeded",
    "failed",
    "canceled",
    "interrupted",
    "worker_start_failed",
}
KNOWN_STATES = TERMINAL_STATES | {"queued", "running", "cancel_requested"}


class QueueError(RuntimeError):
    """A user-facing queue error."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def pid_alive(pid: int | None) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        # Windows os.kill(pid, 0) terminates a process; a zero-time handle wait
        # queries its state without requesting termination rights.
        if pid > 0xFFFFFFFF:
            return True  # Do not truncate an unrepresentable PID to another PID.
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            open_process = kernel32.OpenProcess
            open_process.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
            open_process.restype = wintypes.HANDLE
            wait = kernel32.WaitForSingleObject
            wait.argtypes = (wintypes.HANDLE, wintypes.DWORD)
            wait.restype = wintypes.DWORD
            close = kernel32.CloseHandle
            close.argtypes = (wintypes.HANDLE,)
            close.restype = wintypes.BOOL
            handle = open_process(0x00100000, False, pid)  # SYNCHRONIZE only.
        except (OSError, OverflowError):
            return True  # Unknown is not permission to recover a live owner.
        if not handle:
            return ctypes.get_last_error() != 87  # ERROR_INVALID_PARAMETER: absent PID.
        try:
            try:
                return wait(handle, 0) != 0  # Only WAIT_OBJECT_0 proves exit.
            except (OSError, OverflowError):
                return True
        finally:
            close(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as stream:
            value = json.load(stream)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return value if isinstance(value, dict) else None


def unreadable_file_is_recent(path: Path, grace_seconds: float = 30.0) -> bool:
    try:
        return time.time() - path.stat().st_mtime < grace_seconds
    except FileNotFoundError:
        return False


def unlink_with_retry(path: Path, timeout: float = 2.0) -> bool:
    """Remove a marker despite short Windows reader holds, without spinning."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return True
        except PermissionError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.05)


class ExclusiveFileLock:
    """Cross-process lock using exclusive creation and dead-owner recovery."""

    def __init__(self, path: Path, timeout: float = 10.0) -> None:
        self.path = path
        self.timeout = timeout
        self.token = uuid.uuid4().hex
        self.owned = False

    def acquire(self) -> None:
        deadline = time.monotonic() + self.timeout
        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            payload = {
                "pid": os.getpid(),
                "thread": threading.get_ident(),
                "created_at": utc_now(),
                "token": self.token,
            }
            try:
                descriptor = os.open(
                    self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
                )
            except PermissionError as exc:
                if time.monotonic() >= deadline:
                    raise QueueError(
                        f"Timed out acquiring lock after access denial: {self.path}"
                    ) from exc
                time.sleep(0.05)
                continue
            except FileExistsError:
                owner_value = read_json(self.path)
                if owner_value is None and unreadable_file_is_recent(self.path):
                    if time.monotonic() >= deadline:
                        raise QueueError(f"Timed out waiting for lock: {self.path}")
                    time.sleep(0.05)
                    continue
                owner = owner_value or {}
                if not pid_alive(owner.get("pid")):
                    try:
                        self.path.unlink()
                    except FileNotFoundError:
                        continue
                    except PermissionError:
                        if time.monotonic() >= deadline:
                            raise QueueError(
                                f"Timed out recovering stale lock: {self.path}"
                            )
                        time.sleep(0.05)
                    continue
                if time.monotonic() >= deadline:
                    raise QueueError(f"Timed out waiting for lock: {self.path}")
                time.sleep(0.05)
                continue
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                    json.dump(payload, stream, sort_keys=True)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            except BaseException:
                unlink_with_retry(self.path)
                raise
            self.owned = True
            return

    def release(self) -> None:
        if not self.owned:
            return
        owner = read_json(self.path) or {}
        if owner.get("token") == self.token:
            if not unlink_with_retry(self.path):
                self.owned = False
                raise QueueError(f"Timed out releasing lock: {self.path}")
        self.owned = False

    def __enter__(self) -> "ExclusiveFileLock":
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.release()


class QueueStore:
    def __init__(self, home: Path) -> None:
        self.home = home.resolve()
        self.runtime = self.home / "runtime"
        self.logs = self.runtime / "logs"
        self.state_path = self.runtime / "state.json"
        self.state_lock_path = self.runtime / "state.lock"
        self.worker_path = self.runtime / "worker.json"
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(parents=True, exist_ok=True)

    def new_state(self) -> dict[str, Any]:
        return {
            "version": STATE_VERSION,
            "jobs": [],
            "project_last_started": {},
        }

    def load(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return self.new_state()
        state = read_json(self.state_path)
        if state is None:
            raise QueueError(f"Queue state is unreadable: {self.state_path}")
        if state.get("version") != STATE_VERSION:
            raise QueueError(f"Unsupported queue state version: {state.get('version')!r}")
        if not isinstance(state.get("jobs"), list) or not isinstance(
            state.get("project_last_started"), dict
        ):
            raise QueueError("Queue state has an invalid shape")
        return state

    def save(self, state: dict[str, Any]) -> None:
        atomic_write_json(self.state_path, state)

    @contextlib.contextmanager
    def locked_state(self, *, save: bool = False) -> Iterator[dict[str, Any]]:
        with ExclusiveFileLock(self.state_lock_path):
            state = self.load()
            yield state
            if save:
                self.save(state)


class WorkerLease:
    def __init__(self, store: QueueStore, timeout: float = 5.0) -> None:
        self.store = store
        self.timeout = timeout
        self.token = uuid.uuid4().hex
        self.owned = False

    def acquire(self) -> bool:
        deadline = time.monotonic() + self.timeout
        self.store.worker_path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            payload = {
                "pid": os.getpid(),
                "started_at": utc_now(),
                "status": "running",
                "token": self.token,
            }
            try:
                descriptor = os.open(
                    self.store.worker_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
            except PermissionError:
                if time.monotonic() >= deadline:
                    return False
                time.sleep(0.05)
                continue
            except FileExistsError:
                owner_value = read_json(self.store.worker_path)
                if owner_value is None and unreadable_file_is_recent(
                    self.store.worker_path
                ):
                    return False
                owner = owner_value or {}
                if pid_alive(owner.get("pid")):
                    return False
                try:
                    self.store.worker_path.unlink()
                except FileNotFoundError:
                    continue
                except PermissionError:
                    if time.monotonic() >= deadline:
                        return False
                    time.sleep(0.05)
                continue
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(payload, stream, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            self.owned = True
            return True

    def set_status(self, status: str) -> None:
        if not self.owned:
            raise QueueError("Cannot update a worker lease not owned by this process")
        current = read_json(self.store.worker_path) or {}
        if current.get("token") != self.token:
            raise QueueError("Worker lease identity changed unexpectedly")
        current["status"] = status
        current["updated_at"] = utc_now()
        atomic_write_json(self.store.worker_path, current)

    def release(self) -> None:
        if not self.owned:
            return
        current = read_json(self.store.worker_path) or {}
        if current.get("token") == self.token:
            if not unlink_with_retry(self.store.worker_path):
                self.owned = False
                raise QueueError(
                    f"Timed out releasing worker lease: {self.store.worker_path}"
                )
        self.owned = False


def select_next_job_id(state: dict[str, Any]) -> str | None:
    queued = [job for job in state["jobs"] if job.get("state") == "queued"]
    if not queued:
        return None
    by_project: dict[str, list[dict[str, Any]]] = {}
    for job in queued:
        by_project.setdefault(job["submitting_project"], []).append(job)
    for jobs in by_project.values():
        # State order is lock-serialized submission order. A stable timestamp-only
        # sort preserves FIFO even when two submissions share a microsecond.
        jobs.sort(key=lambda item: item["submitted_at"])
    last_started = state.get("project_last_started", {})
    project = min(
        by_project,
        key=lambda name: (
            last_started.get(name, ""),
            by_project[name][0]["submitted_at"],
            name,
        ),
    )
    return by_project[project][0]["id"]


class QueueService:
    def __init__(
        self,
        home: Path,
        script_path: Path,
        worker_launcher: Callable[[], Any] | None = None,
    ) -> None:
        self.store = QueueStore(home)
        self.script_path = script_path.resolve()
        self.worker_launcher = worker_launcher or self._spawn_detached_worker

    @staticmethod
    def _find_job(state: dict[str, Any], job_id: str) -> dict[str, Any]:
        for job in state["jobs"]:
            if job.get("id") == job_id:
                return job
        raise QueueError(f"Unknown job: {job_id}")

    def _resolve_command(self, cwd: Path, argv: Sequence[str]) -> tuple[Path, list[str]]:
        if not argv or any(not isinstance(part, str) or "\x00" in part for part in argv):
            raise QueueError("A command and valid string arguments are required")
        requested = argv[0]
        candidate: str | None
        if os.path.isabs(requested) or os.sep in requested or (
            os.altsep and os.altsep in requested
        ):
            path = Path(requested)
            if not path.is_absolute():
                path = cwd / path
            candidate = str(path.resolve())
        else:
            candidate = shutil.which(requested)
        if not candidate:
            raise QueueError(f"Executable was not found: {requested}")
        executable = Path(candidate).resolve(strict=True)
        if not executable.is_file():
            raise QueueError(f"Executable is not a file: {executable}")
        return executable, list(argv)

    def submit(
        self,
        project: str,
        cwd_value: str | Path,
        argv: Sequence[str],
        *,
        auto_start: bool = True,
    ) -> dict[str, Any]:
        if not PROJECT_RE.fullmatch(project):
            raise QueueError(
                "Project must match [A-Za-z0-9][A-Za-z0-9._-]{0,63}"
            )
        requested_cwd = Path(cwd_value)
        if not requested_cwd.is_absolute():
            raise QueueError("Working directory must be an absolute path")
        try:
            cwd = requested_cwd.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise QueueError(
                f"Working directory does not exist or cannot be resolved: {cwd_value}"
            ) from exc
        if not cwd.is_dir():
            raise QueueError(f"Working directory is not a directory: {cwd}")
        executable, exact_argv = self._resolve_command(cwd, argv)
        submitted = utc_now()
        job_id = (
            dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            + "-"
            + uuid.uuid4().hex[:8]
        )
        job = {
            "id": job_id,
            "state": "queued",
            "submitting_project": project,
            "submitted_at": submitted,
            "resolved_executable": str(executable),
            "argv": exact_argv,
            "cwd": str(cwd),
            "started_at": None,
            "ended_at": None,
            "worker_pid": None,
            "child_pid": None,
            "exit_status": None,
            "cancel_requested_at": None,
            "log_path": str((self.store.logs / f"{job_id}.log").resolve()),
            "error": None,
        }
        with self.store.locked_state(save=True) as state:
            state["jobs"].append(job)
        if auto_start and not self.ensure_worker(job_id):
            rejected = False
            with self.store.locked_state(save=True) as state:
                current = self._find_job(state, job_id)
                if current["state"] == "queued":
                    current["state"] = "worker_start_failed"
                    current["ended_at"] = utc_now()
                    current["error"] = "No live worker could be established"
                    rejected = True
                elif current["state"] == "worker_start_failed":
                    rejected = True
            if rejected:
                raise QueueError(
                    "Job was not accepted: no live worker could be established"
                )
        return self.status(job_id)

    def _worker_info(self) -> dict[str, Any] | None:
        return read_json(self.store.worker_path)

    def ensure_worker(self, related_job_id: str | None = None) -> bool:
        deadline = time.monotonic() + 8.0
        launched = False
        while time.monotonic() < deadline:
            if related_job_id:
                with self.store.locked_state() as state:
                    current = self._find_job(state, related_job_id)
                    if current["state"] == "worker_start_failed":
                        return False
                    # A worker must hold the queue lease to claim a job. Once the
                    # job has left "queued", that durable transition is stronger
                    # acceptance evidence than a fallible cross-process PID probe.
                    if current["state"] != "queued":
                        return True
            info = self._worker_info()
            if info and pid_alive(info.get("pid")):
                if info.get("status") != "stopping":
                    return True
                time.sleep(0.05)
                continue
            if info and not pid_alive(info.get("pid")):
                with contextlib.suppress(FileNotFoundError, PermissionError):
                    self.store.worker_path.unlink()
            if not launched:
                try:
                    self.worker_launcher()
                except (OSError, subprocess.SubprocessError):
                    return False
                launched = True
            time.sleep(0.05)
        if related_job_id:
            with self.store.locked_state() as state:
                current = self._find_job(state, related_job_id)
                return current["state"] not in {"queued", "worker_start_failed"}
        return False

    def _spawn_detached_worker(self) -> subprocess.Popen[bytes]:
        command = [sys.executable, "-B", str(self.script_path), "worker"]
        options: dict[str, Any] = {
            "cwd": str(self.store.home),
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "close_fds": True,
        }
        if os.name == "nt":
            options["creationflags"] = (
                subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.CREATE_NO_WINDOW
            )
        else:
            options["start_new_session"] = True
        return subprocess.Popen(command, **options)

    def status(self, job_id: str) -> dict[str, Any]:
        with self.store.locked_state() as state:
            return dict(self._find_job(state, job_id))

    def list_jobs(
        self, state_filter: str | None = None, project: str | None = None
    ) -> list[dict[str, Any]]:
        if state_filter and state_filter not in KNOWN_STATES:
            raise QueueError(f"Unknown state filter: {state_filter}")
        with self.store.locked_state() as state:
            jobs = [dict(job) for job in state["jobs"]]
        if state_filter:
            jobs = [job for job in jobs if job["state"] == state_filter]
        if project:
            jobs = [job for job in jobs if job["submitting_project"] == project]
        return jobs

    def cancel(self, job_id: str) -> dict[str, Any]:
        must_wake_worker = False
        with self.store.locked_state(save=True) as state:
            job = self._find_job(state, job_id)
            if job["state"] == "queued":
                job["state"] = "canceled"
                job["cancel_requested_at"] = utc_now()
                job["ended_at"] = job["cancel_requested_at"]
            elif job["state"] == "running":
                job["state"] = "cancel_requested"
                job["cancel_requested_at"] = utc_now()
                must_wake_worker = True
            elif job["state"] == "cancel_requested":
                must_wake_worker = True
            else:
                raise QueueError(f"Job is already terminal: {job['state']}")
        if must_wake_worker:
            self.ensure_worker()
        return self.status(job_id)

    def _terminate_tree(self, pid: int | None) -> None:
        if not pid_alive(pid):
            return
        assert pid is not None
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                shell=False,
            )
        else:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(pid, signal.SIGTERM)

    def _repair_orphaned_jobs(self) -> int:
        repaired = 0
        child_pids: list[int] = []
        with self.store.locked_state(save=True) as state:
            for job in state["jobs"]:
                if job.get("state") not in {"running", "cancel_requested"}:
                    continue
                child_pid = job.get("child_pid")
                if isinstance(child_pid, int):
                    child_pids.append(child_pid)
                was_cancel = job["state"] == "cancel_requested"
                job["state"] = "canceled" if was_cancel else "interrupted"
                job["ended_at"] = utc_now()
                job["exit_status"] = None
                job["error"] = (
                    "Cancellation recovered after worker loss"
                    if was_cancel
                    else "Worker disappeared; job was not retried"
                )
                repaired += 1
        for child_pid in child_pids:
            self._terminate_tree(child_pid)
        return repaired

    def _claim_next(self) -> dict[str, Any] | None:
        with self.store.locked_state(save=True) as state:
            job_id = select_next_job_id(state)
            if job_id is None:
                return None
            job = self._find_job(state, job_id)
            now = utc_now()
            job["state"] = "running"
            job["started_at"] = now
            job["worker_pid"] = os.getpid()
            state["project_last_started"][job["submitting_project"]] = now
            return dict(job)

    def _execute(self, job: dict[str, Any]) -> None:
        log_path = Path(job["log_path"])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        command = [job["resolved_executable"], *job["argv"][1:]]
        process: subprocess.Popen[str] | None = None
        canceled = False
        with log_path.open("a", encoding="utf-8", newline="\n", buffering=1) as log:
            log.write(json.dumps({"queue_job": job}, sort_keys=True) + "\n")
            try:
                options: dict[str, Any] = {
                    "cwd": job["cwd"],
                    "stdin": subprocess.DEVNULL,
                    "stdout": log,
                    "stderr": subprocess.STDOUT,
                    "text": True,
                    "shell": False,
                }
                if os.name == "nt":
                    options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
                else:
                    options["start_new_session"] = True
                process = subprocess.Popen(command, **options)
                with self.store.locked_state(save=True) as state:
                    current = self._find_job(state, job["id"])
                    current["child_pid"] = process.pid
                    canceled = current["state"] == "cancel_requested"
                while process.poll() is None:
                    if canceled:
                        self._terminate_tree(process.pid)
                    time.sleep(0.1)
                    with self.store.locked_state() as state:
                        current = self._find_job(state, job["id"])
                        canceled = current["state"] == "cancel_requested"
                exit_status = process.wait()
                with self.store.locked_state(save=True) as state:
                    current = self._find_job(state, job["id"])
                    canceled = canceled or current["state"] == "cancel_requested"
                    current["state"] = (
                        "canceled"
                        if canceled
                        else ("succeeded" if exit_status == 0 else "failed")
                    )
                    current["ended_at"] = utc_now()
                    current["exit_status"] = exit_status
                    current["error"] = None
            except BaseException as exc:
                if process is not None and process.poll() is None:
                    self._terminate_tree(process.pid)
                with self.store.locked_state(save=True) as state:
                    current = self._find_job(state, job["id"])
                    current["state"] = "interrupted"
                    current["ended_at"] = utc_now()
                    current["exit_status"] = process.poll() if process else None
                    current["error"] = f"{type(exc).__name__}: {exc}"
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise

    def run_worker(self) -> int:
        lease = WorkerLease(self.store)
        if not lease.acquire():
            return 0
        try:
            self._repair_orphaned_jobs()
            while True:
                job = self._claim_next()
                if job is not None:
                    self._execute(job)
                    continue
                # This status transition is made while holding the state lock.
                # A submit either lands before this check and is seen, or lands
                # after it and observes "stopping" before starting a successor.
                with self.store.locked_state() as state:
                    if select_next_job_id(state) is not None:
                        continue
                    lease.set_status("stopping")
                return 0
        finally:
            lease.release()

    def doctor(self, repair: bool = False) -> dict[str, Any]:
        issues: list[str] = []
        repairs: list[str] = []
        worker = self._worker_info()
        if worker and not pid_alive(worker.get("pid")):
            issues.append("stale worker marker")
            if repair:
                if unlink_with_retry(self.store.worker_path):
                    repairs.append("removed stale worker marker")
                    issues.remove("stale worker marker")
                    worker = None
        try:
            with self.store.locked_state() as state:
                jobs = [dict(job) for job in state["jobs"]]
        except QueueError as exc:
            return {"healthy": False, "issues": [str(exc)], "repairs": repairs}
        active = [job for job in jobs if job.get("state") in {"running", "cancel_requested"}]
        if len(active) > 1:
            issues.append(f"more than one running job: {len(active)}")
        worker_live = bool(worker and pid_alive(worker.get("pid")))
        if active and not worker_live:
            issues.append("active job exists without a live worker")
        for job in jobs:
            if job.get("state") not in KNOWN_STATES:
                issues.append(f"{job.get('id')}: unknown state {job.get('state')!r}")
            cwd_value = job.get("cwd")
            if not isinstance(cwd_value, str):
                issues.append(f"{job.get('id')}: cwd is missing")
            elif not Path(cwd_value).is_absolute():
                issues.append(f"{job.get('id')}: cwd is not absolute")
            else:
                try:
                    cwd = Path(cwd_value).resolve(strict=True)
                except (OSError, RuntimeError):
                    issues.append(f"{job.get('id')}: cwd is missing")
                else:
                    if not cwd.is_dir():
                        issues.append(f"{job.get('id')}: cwd is not a directory")
            executable = Path(str(job.get("resolved_executable", "")))
            if not executable.is_file():
                issues.append(f"{job.get('id')}: executable is missing")
        if repair and not worker:
            count = self._repair_orphaned_jobs()
            if count:
                repairs.append(f"marked {count} orphaned job(s) terminal")
                issues = [
                    item
                    for item in issues
                    if "running job" not in item and "without a live worker" not in item
                ]
        return {
            "healthy": not issues,
            "issues": issues,
            "repairs": repairs,
            "worker": worker,
            "job_count": len(jobs),
        }


def production_paths() -> tuple[Path, Path]:
    script = Path(__file__).resolve()
    home = script.parent
    if (
        home.name != "compute_queue"
        or home.parent.name.lower() != "tools"
        or home.parent.parent.name != "Dandelion Engineering"
    ):
        raise QueueError(
            "Run the installed copy under Dandelion Engineering\\tools\\compute_queue"
        )
    return home, script


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    submit = commands.add_parser("submit", help="queue one command and ensure a worker is live")
    submit.add_argument("--project", required=True)
    submit.add_argument(
        "--cwd",
        required=True,
        help="existing absolute working directory (may be anywhere accessible)",
    )
    submit.add_argument("argv", nargs=argparse.REMAINDER)

    listing = commands.add_parser("list", help="list jobs")
    listing.add_argument("--state", choices=sorted(KNOWN_STATES))
    listing.add_argument("--project")

    status = commands.add_parser("status", help="show one job")
    status.add_argument("job_id")

    cancel = commands.add_parser("cancel", help="cancel a queued or running job")
    cancel.add_argument("job_id")

    commands.add_parser("worker", help="run the drain-and-exit worker manually")

    doctor = commands.add_parser("doctor", help="check queue state and worker health")
    doctor.add_argument("--repair", action="store_true")
    return parser


def print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        home, script = production_paths()
        service = QueueService(home, script)
        if args.command == "submit":
            command = list(args.argv)
            if command and command[0] == "--":
                command = command[1:]
            print_json(service.submit(args.project, args.cwd, command))
            return 0
        if args.command == "list":
            print_json(service.list_jobs(args.state, args.project))
            return 0
        if args.command == "status":
            print_json(service.status(args.job_id))
            return 0
        if args.command == "cancel":
            print_json(service.cancel(args.job_id))
            return 0
        if args.command == "worker":
            return service.run_worker()
        if args.command == "doctor":
            result = service.doctor(args.repair)
            print_json(result)
            return 0 if result["healthy"] else 1
        parser.error("unknown command")
    except QueueError as exc:
        print(f"compute_queue: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
