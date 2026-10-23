"""Bounded convenience runner INSIDE the already-enforced invocation namespace.

It executes a sealed snapshot of one workspace Python file, retains evidence,
and retires descendants. It is not a separate privilege boundary: ordinary
executor shell access has the same confined filesystem and robot capability.
"""
import argparse
import base64
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import selectors
import signal
import stat
import subprocess
import sys
import time
import uuid

MAX_SOURCE = 65536
MAX_OUTPUT = 1048576
MEMORY_BYTES = 512 * 1048576


def durable_new_record(path, value):
    """Append-once runner record: fsync both contents and new directory entry.

    Runtime notes remain agent-writable; trusted parent retention must preserve
    these files. Mode 0400 avoids accidental edits, not same-identity tampering.
    """
    encoded = (json.dumps(value, indent=2) + '\n').encode('utf-8')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return hashlib.sha256(encoded).hexdigest()


def descendants():
    """Only descendants of this exact runner, never a process-name inventory."""
    pending, result = [os.getpid()], {}
    while pending:
        parent = pending.pop()
        try:
            numbers = (Path('/proc') / str(parent) / 'task' / str(parent) / 'children').read_text().split()
        except FileNotFoundError:
            continue
        for value in numbers:
            pid = int(value)
            if pid in result:
                continue
            if len(result) >= 256:
                raise RuntimeError('descendant inventory bound exceeded; retire entire invocation')
            try:
                ticks = (Path('/proc') / value / 'stat').read_text().rsplit(')', 1)[1].split()[19]
                result[pid] = ticks
                pending.append(pid)
            except FileNotFoundError:
                continue
    return result


def signal_descendants(sig):
    sent = []
    for pid, ticks in descendants().items():
        handle = None
        try:
            handle = os.pidfd_open(pid)
            observed = (Path('/proc') / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()[19]
            if observed == ticks:
                signal.pidfd_send_signal(handle, sig)
                sent.append(pid)
        except (ProcessLookupError, FileNotFoundError):
            pass
        finally:
            if handle is not None:
                os.close(handle)
    return sent


def retire_children(process):
    evidence = {'term_pids': signal_descendants(signal.SIGTERM), 'kill_pids': []}
    time.sleep(.1)
    deadline = time.monotonic() + 2
    while True:
        evidence['kill_pids'].extend(signal_descendants(signal.SIGKILL))
        if process is not None:
            process.poll()
        while True:
            try:
                pid, _ = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    break
            except ChildProcessError:
                break
        remaining = descendants()
        if not remaining or time.monotonic() >= deadline:
            evidence['remaining'] = remaining
            evidence['qualified'] = not remaining
            return evidence
        time.sleep(.02)


def limits():
    for kind, value in ((resource.RLIMIT_AS, MEMORY_BYTES), (resource.RLIMIT_CORE, 0),
                        (resource.RLIMIT_FSIZE, 8 * 1048576), (resource.RLIMIT_NOFILE, 128),
                        (resource.RLIMIT_CPU, 60)):
        resource.setrlimit(kind, (value, value))


def execute(program, timeout, workspace=Path('/workspace')):
    if not 0 < timeout <= 60:
        raise ValueError('timeout must be >0 and <=60 seconds')
    relative = Path(program)
    if relative.is_absolute() or '..' in relative.parts or not relative.parts or relative.parts[0] != 'programs':
        raise ValueError('program must be beneath programs/')
    path = workspace / relative
    if path.resolve(strict=True) != path or not path.is_relative_to(workspace / 'programs'):
        raise ValueError('program path alias or escape')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
            raise ValueError('regular program file required')
        payload = source.read(MAX_SOURCE + 1)
    if len(payload) > MAX_SOURCE:
        raise ValueError('program source exceeds 65536 bytes')
    digest = hashlib.sha256(payload).hexdigest()
    run_id = digest[:12] + '-' + uuid.uuid4().hex[:12]
    destination = workspace / 'notes/program-runs'
    destination.mkdir(mode=0o700, exist_ok=True)
    if destination.resolve(strict=True) != destination:
        raise ValueError('program evidence directory alias')
    snapshot = os.memfd_create('robot-program-' + run_id, os.MFD_ALLOW_SEALING)
    os.write(snapshot, payload)
    os.lseek(snapshot, 0, os.SEEK_SET)
    fcntl.fcntl(snapshot, fcntl.F_ADD_SEALS,
                fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL)
    # Become subreaper so double-forked/session-detached descendants stay under
    # this runner and can be retired without touching other executor commands.
    if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
        os.close(snapshot)
        raise OSError(ctypes.get_errno(), 'subreaper setup failed')
    evidence = {'schema': 'bounded-program-1', 'run_id': run_id, 'program': str(relative),
                'source_sha256': digest, 'source_bytes': len(payload),
                'source_base64': base64.b64encode(payload).decode(), 'sealed_snapshot': True,
                'timeout_s': timeout, 'max_output_bytes': MAX_OUTPUT, 'memory_per_process_bytes': MEMORY_BYTES,
                'scope': 'inside invocation namespace; ordinary shell remains available; no separate privilege boundary',
                'exit_code': None, 'timed_out': False, 'output_limit': False, 'completed': False}
    admission_path = destination / (run_id + '.admitted.json')
    final_path = destination / (run_id + '.json')
    admission = {**evidence, 'record_kind': 'admission',
                 'disposition': 'admitted_execution_unknown_until_final_record',
                 'final_record': final_path.name,
                 'limits': {'source_bytes': MAX_SOURCE, 'output_bytes': MAX_OUTPUT,
                            'wall_seconds': timeout, 'cpu_seconds_per_process': 60,
                            'memory_bytes_per_process': MEMORY_BYTES,
                            'file_bytes_per_process': 8 * 1048576, 'descriptors_per_process': 128}}
    process = None
    started = time.monotonic()
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    try:
        # MUST precede Popen: SIGKILL/namespace retirement has no finally path.
        # An admission with no final record is an unknown interrupted outcome,
        # never proof that code ran, succeeded, or left no descendants.
        evidence['admission_sha256'] = durable_new_record(admission_path, admission)
        evidence['admission_record'] = admission_path.name
        process = subprocess.Popen(['/usr/bin/python3', '-I', '-B', '/proc/self/fd/' + str(snapshot)],
            cwd=workspace, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            pass_fds=(snapshot,), start_new_session=True, preexec_fn=limits,
            env={'PATH': '/usr/bin:/bin', 'HOME': str(workspace), 'LANG': 'C.UTF-8', 'TMPDIR': '/tmp'})
        os.close(snapshot)
        snapshot = None
        selector = selectors.DefaultSelector()
        for name in buffers:
            stream = getattr(process, name)
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        try:
            while selector.get_map():
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    evidence['timed_out'] = True
                    break
                for key, _ in selector.select(min(remaining, .05)):
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    available = MAX_OUTPUT - sum(len(value) for value in buffers.values())
                    buffers[key.data].extend(chunk[:available])
                    if len(chunk) > available:
                        evidence['output_limit'] = True
                        break
                if evidence['output_limit']:
                    break
                if process.poll() is not None:
                    # Keep draining the bounded output after main exit. Any
                    # detached pipe holders are our own subreaper descendants.
                    signal_descendants(signal.SIGKILL)
            if process.poll() is None and not evidence['timed_out'] and not evidence['output_limit']:
                try:
                    process.wait(timeout=max(.001, timeout - (time.monotonic() - started)))
                except subprocess.TimeoutExpired:
                    evidence['timed_out'] = True
            evidence['exit_code'] = process.poll()
        finally:
            selector.close()
        evidence['completed'] = evidence['exit_code'] == 0 and not evidence['timed_out'] and not evidence['output_limit']
    except BaseException as error:
        evidence['error'] = {'type': type(error).__name__, 'message': str(error)[:1000]}
    finally:
        if snapshot is not None:
            os.close(snapshot)
        try:
            evidence['retirement'] = retire_children(process)
        except Exception as error:
            evidence['retirement'] = {'qualified': False, 'error': str(error)}
        if process is not None:
            for name in ('stdout', 'stderr'):
                stream = getattr(process, name)
                if stream is not None:
                    stream.close()
        evidence['completed'] = evidence['completed'] and evidence['retirement']['qualified']
        evidence['elapsed_s'] = round(time.monotonic() - started, 4)
        evidence['output'] = {name: bytes(data).decode('utf-8', errors='replace') for name, data in buffers.items()}
        evidence['record_kind'] = 'final'
        evidence['disposition'] = 'completed' if evidence['completed'] else 'failed_or_interrupted'
        durable_new_record(final_path, evidence)
        evidence['evidence_path'] = str(final_path)
        evidence['admission_path'] = str(admission_path)
    return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('program')
    parser.add_argument('--timeout', type=float, default=30.)
    args = parser.parse_args()
    outcome = execute(args.program, args.timeout)
    print(json.dumps({key: value for key, value in outcome.items() if key != 'source_base64'}))
    raise SystemExit(0 if outcome['completed'] else 1)
