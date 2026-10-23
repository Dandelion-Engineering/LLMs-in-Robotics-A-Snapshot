"""Queue-owned, bounded Windows sharing diagnosis on fresh owned files only.

No queue service/worker/status API is called. The sole installed queue access is
an ownership snapshot using its existing state lock and close-before-release.
All native replacement probes and the writer use output/sandbox exclusively.
This is a diagnostic, not adoption or permission to run an evaluation episode.
"""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[2]
RECOVERY = EXPERIMENT / 'Runtime Recovery 001'
QUEUE = EXPERIMENT.parent.parent / 'tools' / 'compute_queue' / 'compute_queue.py'
QUEUE_SHA256 = '31997fc851494df62c2466cf189b5e945a6a933464f5cd43e69b3d877c029829'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def retain(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')
        stream.flush(); os.fsync(stream.fileno())


def load_queue():
    if digest(QUEUE) != QUEUE_SHA256:
        raise RuntimeError('Installed queue differs from explicitly verified liveness-patched source')
    spec = importlib.util.spec_from_file_location('_sharing_diagnostic_queue', QUEUE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module; spec.loader.exec_module(module)
    return module


def owner(queue):
    sys.path.insert(0, str(RECOVERY))
    import recovery_runner as runner
    if Path(runner.__file__).resolve() != RECOVERY / 'recovery_runner.py':
        raise RuntimeError('Unexpected recovery runner module')
    if Path(sys.argv[0]).resolve() != Path(__file__).resolve():
        raise RuntimeError('Not the direct diagnostic entrypoint')
    # The lock is released before CIM validation, sleeping or any diagnostic.
    for _ in range(30):
        with queue.ExclusiveFileLock(runner.original.QUEUE_STATE.with_name('state.lock'), timeout=3):
            state = runner.read_shared_json(runner.original.QUEUE_STATE)
        matches = [j for j in state.get('jobs', []) if j.get('state') == 'running'
                   and type(j.get('child_pid')) is int and j['child_pid'] in (os.getpid(), os.getppid())]
        if len(matches) > 1:
            raise RuntimeError('Ambiguous queue ownership')
        if matches:
            job = matches[0]
            if runner.original.python_entrypoint(job.get('argv'), job.get('cwd')) != Path(__file__).resolve():
                raise RuntimeError('Queue entrypoint differs')
            if job['child_pid'] != os.getpid():
                runner.original.verify_windows_venv_parent(job, os.getpid(), os.getppid())
            return {'job_id': job['id'], 'child_pid': job['child_pid'], 'actual_pid': os.getpid(),
                    'reader': 'existing installed ExclusiveFileLock; share7 read; handle closed before lock release'}
        time.sleep(.05)
    raise RuntimeError('Installed queue does not own this diagnostic')


class Native:
    def __init__(self):
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.create = self.kernel.CreateFileW
        self.create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
        self.create.restype = wintypes.HANDLE
        self.close = self.kernel.CloseHandle
        self.close.argtypes = (wintypes.HANDLE,); self.close.restype = wintypes.BOOL
        self.read = self.kernel.ReadFile
        self.read.argtypes = (wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                             ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p)
        self.read.restype = wintypes.BOOL

    def open(self, path, *, access=0x80000000, sharing=7):
        handle = self.create(str(path), access, sharing, None, 3, 0x80, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        return handle

    def bytes(self, handle):
        buffer = ctypes.create_string_buffer(4096); count = wintypes.DWORD()
        if not self.read(handle, buffer, len(buffer), ctypes.byref(count), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return buffer.raw[:count.value]


def observation(operation):
    start = time.perf_counter()
    try:
        value = operation()
        return {'succeeded': True, 'value': value, 'elapsed_s': time.perf_counter() - start}
    except Exception as error:
        return {'succeeded': False, 'error_type': type(error).__name__, 'error': str(error),
                'winerror': getattr(error, 'winerror', None), 'elapsed_s': time.perf_counter() - start}


def native_case(native, sandbox, sharing):
    folder = sandbox / ('sharing-' + str(sharing)); folder.mkdir()
    target = folder / 'target.json'; source = folder / 'replacement.json'
    retain(target, {'generation': 1}); retain(source, {'generation': 2})
    handle = native.open(target, sharing=sharing)
    try:
        def open_delete():
            extra = native.open(target, access=0x10000, sharing=7)
            native.close(extra)
        delete = observation(open_delete)
        replacement = observation(lambda: os.replace(source, target))
        held_bytes = native.bytes(handle).decode('utf-8')
    finally:
        native.close(handle)
    after_close = observation(lambda: os.replace(source, target)) if source.exists() else {
        'not_run_reason': 'Open-handle replacement already succeeded'}
    return {'sharing': sharing, 'desired_access': 'GENERIC_READ', 'subsequent_delete_access_open': delete,
            'replace_while_destination_open': replacement, 'bytes_from_original_handle': held_bytes,
            'same_replacement_after_close': after_close, 'final_target': json.loads(target.read_text(encoding='utf-8'))}


def serialized_case(queue, native, sandbox):
    store = queue.QueueStore(sandbox / 'queue-fixture')
    with store.locked_state(save=True) as state:
        state['diagnostic_generation'] = 1
    entered = threading.Event(); acquired = threading.Event(); done = threading.Event(); events = []
    def writer():
        entered.set(); events.append({'event': 'writer_waiting', 'time': time.perf_counter()})
        try:
            with queue.ExclusiveFileLock(store.state_lock_path, timeout=3):
                acquired.set(); events.append({'event': 'writer_acquired', 'time': time.perf_counter()})
                state = store.load(); state['diagnostic_generation'] = 2; store.save(state)
            events.append({'event': 'writer_finished', 'time': time.perf_counter()})
        except Exception as error:
            events.append({'event': 'writer_failed', 'error': repr(error)})
        finally:
            done.set()
    worker = None
    try:
        with queue.ExclusiveFileLock(store.state_lock_path, timeout=3):
            handle = native.open(store.state_path, sharing=7)
            try:
                worker = threading.Thread(target=writer, name='owned-temporary-state-writer', daemon=True)
                worker.start()
                if not entered.wait(1):
                    raise RuntimeError('Temporary writer did not reach lock attempt')
                writer_blocked = not acquired.wait(.1)
                before = json.loads(native.bytes(handle))
            finally:
                native.close(handle); events.append({'event': 'reader_handle_closed', 'time': time.perf_counter()})
        events.append({'event': 'reader_lock_released', 'time': time.perf_counter()})
    finally:
        if worker is not None:
            worker.join(4)
    if not done.is_set():
        raise RuntimeError('Owned temporary writer exceeded bounded lock timeout')
    with store.locked_state() as state:
        after = dict(state)
    return {'writer_blocked_while_reader_open': writer_blocked, 'before_generation': before['diagnostic_generation'],
            'after_generation': after['diagnostic_generation'], 'events': events,
            'passed': writer_blocked and before['diagnostic_generation'] == 1
                      and after['diagnostic_generation'] == 2 and not any(e['event'] == 'writer_failed' for e in events)}


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if os.name != 'nt':
        raise RuntimeError('Windows-native diagnostic only')
    queue = load_queue(); ownership = owner(queue)
    output = args.output.resolve()
    if output.parent != HERE or output.exists():
        raise RuntimeError('Output must be one fresh immediate child of this diagnostic directory')
    output.mkdir(); sandbox = output / 'sandbox'; sandbox.mkdir()
    sources = {str(p): digest(p) for p in (Path(__file__), QUEUE, RECOVERY / 'recovery_runner.py')}
    retain(output / 'started.json', {'ownership': ownership, 'sources': sources, 'python': sys.version,
                                    'executable': sys.executable, 'argv': sys.argv, 'sandbox': str(sandbox)})
    result = {'schema': 'queue-file-sharing-diagnostic-1', 'ownership': ownership, 'sources_before': sources,
              'scope': 'Owned files only; no episode, no installed state mutation, no adoption conclusion'}
    try:
        native = Native(); result['native_cases'] = []
        for sharing in (3, 7):
            case = native_case(native, sandbox, sharing); result['native_cases'].append(case)
            retain(output / ('native-' + str(sharing) + '.json'), case)
        result['serialized_case'] = serialized_case(queue, native, sandbox)
        result['completed'] = True
    except BaseException as error:
        result['completed'] = False; result['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        result['sources_after'] = {path: digest(path) for path in sources}
        result['sources_unchanged'] = result['sources_after'] == sources
        retain(output / 'diagnostic.json', result)


if __name__ == '__main__':
    main()
