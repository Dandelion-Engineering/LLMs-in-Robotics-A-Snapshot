"""WSL/bubblewrap candidate process with bounded JSON-line IPC.

This is a tested local permission boundary, not a claim of resistance to kernel
vulnerabilities. Only copied candidate code and its selected episode directory
are mounted. No evaluator, model, project, home, environment secrets or network
are supplied. Linux rlimits reset at restart; the experiment must also account
for aggregate resources. Ordinary per-file limits are not a filesystem quota.

References: https://github.com/containers/bubblewrap and
https://man7.org/linux/man-pages/man2/getrlimit.2.html
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import base64
import binascii
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import zlib


HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class SandboxLimits:
    cpu_seconds: int = 1200
    memory_bytes: int = 256 * 1024 * 1024
    file_bytes: int = 16 * 1024 * 1024
    open_files: int = 64
    line_bytes: int = 1024 * 1024
    output_bytes: int = 32 * 1024 * 1024
    wall_seconds: float = 1800
    startup_seconds: float = 20

    def __post_init__(self):
        for name, value in asdict(self).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(name + " must be positive")


class SandboxError(RuntimeError):
    pass


def _strict_json(payload):
    def constant(value):
        raise ValueError("Non-JSON numeric constant: " + value)

    def number(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("Nonfinite number")
        return result

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate object key: " + key)
            result[key] = value
        return result

    return json.loads(payload, parse_constant=constant, parse_float=number, object_pairs_hook=pairs)


def restore_context_transport(message,line_bytes):
    """Bounded, hash-checked restoration before any existing evidence consumer.

    This restores only trusted-wrapper context carriers, never arbitrary pickle,
    files or imports. Legacy uncompressed replies remain compatible. The original
    complete reply line cap also applies after restoration, not only on the wire.
    """
    events=message.get('events')
    if not isinstance(events,list):return message
    restored=[];changed=False;remaining=min(line_bytes,8*1024*1024)
    for event in events:
        if not isinstance(event,dict) or '_context_transport' not in event:
            restored.append(event);continue
        carrier=event['_context_transport']
        if (event.get('type') not in ('context_read','context_write') or 'content_utf8' in event
                or not isinstance(carrier,dict) or set(carrier)!={'codec','decoded_bytes','sha256','data'}
                or carrier.get('codec')!='zlib-base64-v1'):
            raise ValueError('Invalid compressed context carrier')
        size=carrier['decoded_bytes']
        if type(size) is not int or not 0<=size<=remaining:
            raise ValueError('Compressed contexts exceed the decoded reply budget')
        if type(event.get('byte_count')) is not int or event['byte_count']!=size or event.get('sha256')!=carrier['sha256']:
            raise ValueError('Compressed context metadata differs from original event')
        try:
            compressed=base64.b64decode(carrier['data'],validate=True)
            inflater=zlib.decompressobj()
            raw=inflater.decompress(compressed,size+1)
            if len(raw)!=size or not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
                raise ValueError('Compressed context length/stream boundary mismatch')
            if hashlib.sha256(raw).hexdigest()!=carrier['sha256']:
                raise ValueError('Compressed context hash mismatch')
            text=raw.decode('utf-8')
        except (TypeError,binascii.Error,zlib.error,UnicodeError) as exc:
            raise ValueError('Invalid compressed UTF-8 context data') from exc
        remaining-=size
        restored.append({**{key:value for key,value in event.items() if key!='_context_transport'},'content_utf8':text})
        changed=True
    if not changed:return message
    result={**message,'events':restored}
    if len(json.dumps(result,ensure_ascii=True,allow_nan=False,separators=(',',':')).encode('ascii'))+1>line_bytes:
        raise ValueError('Restored candidate response exceeds the original line limit')
    return result


def _windows_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _clean_host_environment() -> dict:
    # WSLENV and model/provider credentials are intentionally not inherited.
    allowed = ("SystemRoot", "WINDIR", "SYSTEMDRIVE", "TEMP", "TMP", "PATH", "PATHEXT")
    return {key: os.environ[key] for key in allowed if key in os.environ}


def _wsl_path(path: Path) -> str:
    absolute = path.resolve()
    if os.name != "nt":
        return str(absolute)
    drive = absolute.drive
    if len(drive) != 2 or drive[1] != ":":
        raise ValueError("Only local Windows drive paths are supported")
    return "/mnt/" + drive[0].lower() + absolute.as_posix()[2:]


# The control file is outside /code and /work. PID plus kernel start time guards
# against killing a recycled Linux process ID. Each sandbox has its own session.
_BOOTSTRAP = r'''
import json, os, sys
code, work, control, kind, persistent, limits = sys.argv[1:]
if os.getsid(0) != os.getpid():
    os.setsid()
pid = os.getpid()
stat = open('/proc/self/stat').read().rsplit(')', 1)[1].split()
with open(control, 'w', encoding='utf-8') as stream:
    json.dump({'pid': pid, 'start_ticks': stat[19], 'pgid': os.getpgrp()}, stream)
args = ['/usr/bin/bwrap', '--unshare-all', '--die-with-parent', '--new-session',
        '--cap-drop', 'ALL', '--clearenv', '--setenv', 'PATH', '/usr/bin',
        '--setenv', 'HOME', '/work', '--setenv', 'LANG', 'C.UTF-8',
        '--ro-bind', '/usr', '/usr', '--symlink', 'usr/bin', '/bin',
        '--symlink', 'usr/lib', '/lib', '--symlink', 'usr/lib64', '/lib64',
        '--proc', '/proc', '--dev', '/dev', '--size', '16777216', '--tmpfs', '/tmp',
        '--ro-bind', code, '/code', '--bind', work, '/work', '--chdir', '/work',
        '/usr/bin/python3', '-I', '-B', '/code/candidate_worker.py',
        '--kind', kind, '--persistent', persistent, '--limits', limits]
os.execv('/usr/bin/bwrap', args)
'''

_KILL_GROUP = r'''
import json, os, signal, sys, time
control = json.loads(sys.argv[1]); pid = int(control['pid'])
try:
    stat = open('/proc/%d/stat' % pid).read().rsplit(')', 1)[1].split()
except FileNotFoundError:
    print('already_exited'); raise SystemExit(0)
if stat[19] != str(control['start_ticks']) or int(stat[2]) != int(control['pgid']):
    raise SystemExit('Process identity no longer matches; no process killed')
os.killpg(int(control['pgid']), signal.SIGKILL)
for _ in range(100):
    try:
        stat = open('/proc/%d/stat' % pid).read().rsplit(')', 1)[1].split()
        if stat[19] != str(control['start_ticks']) or stat[0] == 'Z': break
    except FileNotFoundError: break
    time.sleep(.01)
else: raise SystemExit('Linux sandbox did not terminate')
print('terminated')
'''


class CandidateSandbox:
    """Own one candidate process. ``poll`` never waits on candidate inference.

    start consumes the ready handshake and stores it in ``ready``. Every request
    receives {type, response, events}; the response is populated for step only.
    Candidate event objects and model strings pass unchanged through JSON.
    """

    def __init__(self, kind: str, episode_dir: Path, persistent: bool = True,
                 candidate_path: Path | None = None, limits: SandboxLimits | None = None,
                 distribution: str = "Ubuntu-24.04"):
        self.kind = str(kind)
        self.episode_dir = Path(episode_dir).resolve()
        self.persistent = bool(persistent)
        self.candidate_path = Path(candidate_path or HERE / "candidates.py").resolve()
        self.limits = limits or SandboxLimits()
        self.distribution = distribution
        self.process = None
        self.ready = None
        self.work_dir = None
        self.failure = None
        self.termination = None
        self._temporary = None
        self._messages = queue.Queue(maxsize=256)
        self._stop = threading.Event()
        self._stdout_done = threading.Event()
        self._close_lock = threading.RLock()
        self._count_lock = threading.Lock()
        self._output_count = 0
        self._stderr = bytearray()
        self._threads = []
        self._started = None
        self._control = None

    def _linux_command(self, *args) -> list[str]:
        if os.name == "nt":
            return ["wsl.exe", "--distribution", self.distribution, "--exec", *args]
        return list(args)

    def start(self):
        if self.process is not None or self._temporary is not None:
            raise SandboxError("Sandbox instances cannot be restarted; create a fresh instance")
        if not self.candidate_path.is_file():
            raise SandboxError("Candidate file is absent: " + str(self.candidate_path))
        self._temporary = tempfile.TemporaryDirectory(prefix="robot-candidate-")
        private = Path(self._temporary.name).resolve()
        code = private / "code"
        code.mkdir()
        shutil.copyfile(self.candidate_path, code / "candidates.py")
        shutil.copyfile(HERE / "candidate_worker.py", code / "candidate_worker.py")
        if self.persistent:
            self.episode_dir.mkdir(parents=True, exist_ok=True)
            self.work_dir = self.episode_dir
        else:
            self.work_dir = private / "ephemeral-episode"
            self.work_dir.mkdir()
        self._control_path = private / "linux-process.json"
        command = self._linux_command("/usr/bin/python3", "-I", "-B", "-c", _BOOTSTRAP,
                                      _wsl_path(code), _wsl_path(self.work_dir),
                                      _wsl_path(self._control_path), self.kind,
                                      "1" if self.persistent else "0",
                                      json.dumps(asdict(self.limits), separators=(",", ":")))
        try:
            self._started = time.monotonic()
            self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE, bufsize=0, env=_clean_host_environment(),
                                            creationflags=_windows_flags())
            for pipe, is_error in ((self.process.stdout, False), (self.process.stderr, True)):
                thread = threading.Thread(target=self._read_pipe, args=(pipe, is_error), daemon=True)
                thread.start()
                self._threads.append(thread)
            monitor = threading.Thread(target=self._monitor, daemon=True)
            monitor.start()
            self._threads.append(monitor)
            deadline = time.monotonic() + self.limits.startup_seconds
            while time.monotonic() < deadline:
                if self._control_path.exists():
                    try:
                        self._control = json.loads(self._control_path.read_text(encoding="utf-8"))
                        break
                    except (ValueError, OSError):
                        pass
                if self.process.poll() is not None:
                    raise SandboxError("Sandbox launcher exited: " + self.stderr)
                time.sleep(.01)
            if self._control is None:
                raise SandboxError("Sandbox process identity was not established")
            self.ready = self.receive(max(.01, deadline - time.monotonic()))
            if self.ready.get("type") != "ready":
                raise SandboxError("Sandbox startup failed: " + json.dumps(self.ready))
            return self
        except BaseException:
            self.close()
            raise

    @property
    def stderr(self) -> str:
        return bytes(self._stderr).decode("utf-8", errors="replace")

    @property
    def alive(self) -> bool:
        return self.process is not None and self.process.poll() is None and not self._stop.is_set()

    @property
    def output_bytes(self) -> int:
        return self._output_count

    def _fail(self, message: str) -> None:
        if self.failure is None:
            self.failure = message
        self._stop.set()

    def _read_pipe(self, pipe, is_error: bool) -> None:
        pending = bytearray()
        try:
            while True:
                chunk = pipe.read(4096)
                if not chunk:
                    if pending and not is_error:
                        self._fail("Candidate emitted an incomplete JSON line")
                    return
                with self._count_lock:
                    self._output_count += len(chunk)
                    if self._output_count > self.limits.output_bytes:
                        self._fail("Candidate exceeded the combined output cap")
                        return
                if is_error:
                    self._stderr.extend(chunk)
                    del self._stderr[:-8192]
                    continue
                pending.extend(chunk)
                while b"\n" in pending:
                    line, _, remainder = pending.partition(b"\n")
                    pending = bytearray(remainder)
                    if len(line) + 1 > self.limits.line_bytes:
                        self._fail("Candidate exceeded the JSON line cap")
                        return
                    try:
                        message = _strict_json(line)
                        if not isinstance(message, dict):
                            raise ValueError("response is not an object")
                        message = restore_context_transport(message,self.limits.line_bytes)
                        self._messages.put_nowait(message)
                    except (ValueError, UnicodeError, queue.Full) as exc:
                        self._fail("Candidate IPC violation: " + str(exc))
                        return
                if len(pending) > self.limits.line_bytes:
                    self._fail("Candidate exceeded the unterminated line cap")
                    return
        except (OSError, ValueError) as exc:
            if not self._stop.is_set():
                self._fail("Candidate pipe failed: " + str(exc))
        finally:
            if not is_error:
                self._stdout_done.set()

    def _monitor(self) -> None:
        while not self._stop.wait(.05):
            if self.process.poll() is not None:
                return
            if time.monotonic() - self._started >= self.limits.wall_seconds:
                self._fail("Candidate exceeded wall timeout")
        # Only this instance's checked Linux process group is terminated.
        try:
            self._terminate()
        except Exception as exc:
            self.failure = (self.failure or "Sandbox shutdown") + "; " + str(exc)

    def send(self, message: dict) -> None:
        if not self.alive:
            raise SandboxError(self.failure or "Candidate is not running")
        payload = (json.dumps(message, ensure_ascii=True, allow_nan=False, separators=(",", ":")) + "\n").encode("ascii")
        if len(payload) > self.limits.line_bytes:
            raise SandboxError("Request exceeds JSON line cap")
        try:
            self.process.stdin.write(payload)
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise SandboxError("Candidate input closed: " + self.stderr) from exc

    def poll(self) -> dict | None:
        if self.failure:
            raise SandboxError(self.failure)
        try:
            return self._messages.get_nowait()
        except queue.Empty:
            if self.process is not None and self.process.poll() is not None and self._stdout_done.is_set():
                raise SandboxError("Candidate exited without a response: " + self.stderr)
            return None

    def receive(self, timeout: float = 20) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = self.poll()
            if value is not None:
                return value
            time.sleep(.005)
        raise TimeoutError("No candidate response before deadline")

    def _terminate(self) -> None:
        with self._close_lock:
            if self.termination is not None:
                return
            if self._control is None and getattr(self, "_control_path", None) and self._control_path.exists():
                try:
                    self._control = json.loads(self._control_path.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    pass
            if self._control is not None:
                command = self._linux_command("/usr/bin/python3", "-I", "-B", "-c", _KILL_GROUP,
                                              json.dumps(self._control, separators=(",", ":")))
                result = subprocess.run(command, capture_output=True, timeout=10,
                                        env=_clean_host_environment(), creationflags=_windows_flags())
                if result.returncode != 0:
                    raise SandboxError("Cannot verify Linux process termination: " + result.stderr.decode("utf-8", "replace"))
                self.termination = result.stdout.decode("utf-8", "replace").strip()
            elif self.process is not None and self.process.poll() is None:
                # Fail closed: an unidentified late Linux launch must not be
                # reported as successfully terminated.
                self.failure = (self.failure or "Startup failed") + "; Linux process identity unavailable"
            if self.process is not None:
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    if os.name == "nt":
                        subprocess.run(["taskkill.exe", "/PID", str(self.process.pid), "/T", "/F"],
                                       capture_output=True, timeout=5, creationflags=_windows_flags())
                    else:
                        self.process.kill()
                    self.process.wait(timeout=3)

    def close(self) -> None:
        self._stop.set()
        if self.process is not None:
            try:
                if self.process.stdin:
                    self.process.stdin.close()
            except OSError:
                pass
            self._terminate()
        for thread in self._threads:
            if thread is not threading.current_thread():
                thread.join(timeout=1)
        if self.process is not None:
            for pipe in (self.process.stdout, self.process.stderr):
                if pipe:
                    pipe.close()
        if self._temporary is not None:
            self._temporary.cleanup()

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc, traceback):
        self.close()
