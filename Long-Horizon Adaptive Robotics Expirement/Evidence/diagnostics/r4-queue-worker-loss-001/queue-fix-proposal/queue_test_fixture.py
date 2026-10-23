"""Private disposable-store fixtures. Never invoke the shared queue CLI."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
PATCHED = HERE / 'compute_queue.proposed.py'


def forbidden(*args, **kwargs):
    raise AssertionError('Production CLI/default launcher forbidden in proposal tests')


def load_queue(root):
    root = Path(root).resolve()
    if not root.is_relative_to(Path(tempfile.gettempdir()).resolve()):
        raise AssertionError('Fixture store must be beneath the OS temporary directory')
    scope = json.loads((root / 'test-scope.json').read_text(encoding='utf-8'))
    if (Path(scope['root']).resolve() != root or scope['patched_source'] != str(PATCHED)
            or scope['patched_sha256'] != hashlib.sha256(PATCHED.read_bytes()).hexdigest()):
        raise AssertionError('Disposable scope/source identity differs')
    spec = importlib.util.spec_from_file_location('queue_proposal_only', PATCHED)
    queue = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(queue)
    original_store = queue.QueueStore

    class TemporaryStoreOnly(original_store):
        def __init__(self, home):
            if Path(home).resolve() != root / 'queue':
                raise AssertionError('Any non-fixture store is forbidden')
            super().__init__(home)

    queue.QueueStore = TemporaryStoreOnly
    queue.production_paths = forbidden
    queue.main = forbidden
    queue.QueueService._spawn_detached_worker = forbidden
    return queue


def write_once(root, name, value):
    target = root / name
    descriptor, temporary = tempfile.mkstemp(prefix='.fixture-', dir=root)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(value, stream); stream.flush(); os.fsync(stream.fileno())
        if target.exists():
            raise FileExistsError(target)
        # Windows rename refuses an existing target; completed JSON becomes
        # visible at once, and duplicate task completion cannot overwrite it.
        os.rename(temporary, target)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()


def wait_release(root, name, limit=30):
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        if (root / f'{name}.release').exists():
            write_once(root, f'{name}.done.json', {'pid': os.getpid(), 'normal_completion': True})
            return
        time.sleep(.02)
    raise TimeoutError(f'Bounded fixture {name} was never released')


def command(root, token, mode, name):
    # Base interpreter avoids the Windows venv launcher/base-PID ambiguity.
    return [getattr(sys, '_base_executable', sys.executable), '-X', 'utf8', '-B',
            str(Path(__file__).resolve()), '--root', str(root), '--token', token,
            '--mode', mode, '--name', name]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--token', required=True)
    parser.add_argument('--mode', choices=['worker', 'holder', 'task', 'task-tree', 'submit'], required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    scope = json.loads((root / 'test-scope.json').read_text(encoding='utf-8'))
    if args.token != scope['token'] or not args.name.replace('-', '').isalnum():
        raise AssertionError('Wrong fixture token or unsafe name')
    queue = load_queue(root)
    service = queue.QueueService(root / 'queue', PATCHED, worker_launcher=forbidden)
    if args.mode == 'worker':
        write_once(root, f'{args.name}.ready.json', {'pid': os.getpid()})
        result = service.run_worker()
        write_once(root, f'{args.name}.done.json', {'pid': os.getpid(), 'normal_completion': True})
        return result
    if args.mode == 'submit':
        job = service.submit(args.name, root,
            command(root, args.token, 'task', args.name), auto_start=True)
        write_once(root, f'{args.name}.submission.json', job)
        return 0
    if args.mode == 'holder':
        lease = queue.WorkerLease(service.store)
        if not lease.acquire():
            raise AssertionError('Fresh fixture lease unavailable')
        try:
            with queue.ExclusiveFileLock(service.store.state_lock_path, timeout=1):
                write_once(root, f'{args.name}.ready.json', {'pid': os.getpid()})
                wait_release(root, args.name)
        finally:
            lease.release()
        return 0
    child = None
    try:
        if args.mode == 'task-tree':
            child = subprocess.Popen(command(root, args.token, 'task', args.name + '-grandchild'),
                                     creationflags=subprocess.CREATE_NO_WINDOW)
        write_once(root, f'{args.name}.ready.json', {'pid': os.getpid()})
        wait_release(root, args.name)
        return 0
    finally:
        if child is not None and child.poll() is None:
            child.terminate(); child.wait(timeout=5)


if __name__ == '__main__':
    raise SystemExit(main())
