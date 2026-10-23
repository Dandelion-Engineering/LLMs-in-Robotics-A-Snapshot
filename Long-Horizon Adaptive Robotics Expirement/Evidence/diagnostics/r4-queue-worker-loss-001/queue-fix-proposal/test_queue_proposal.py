"""Unexecuted proposal tests. All queue stores/processes are disposable fixtures."""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest import mock
import uuid

import queue_test_fixture as fixture


class ScopedTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='queue-proposal-')
        self.root = Path(self.temp.name).resolve()
        self.token = uuid.uuid4().hex
        fixture.write_once(self.root, 'test-scope.json', {
            'root': str(self.root), 'token': self.token,
            'patched_source': str(fixture.PATCHED),
            'patched_sha256': hashlib.sha256(fixture.PATCHED.read_bytes()).hexdigest()})
        self.queue = fixture.load_queue(self.root)
        self.processes = []; self.logs = []; self.owned_handles = {}
        self.service = self.queue.QueueService(self.root / 'queue', fixture.PATCHED,
                                               worker_launcher=fixture.forbidden)

    def tearDown(self):
        # Retained process handles cannot retarget a reused PID. No pid_alive.
        errors = []
        if os.name == 'nt':
            kernel = self.native_api()
            for handle in self.owned_handles.values():
                try:
                    state = kernel.WaitForSingleObject(handle, 0)
                    if state == 258:
                        if not kernel.TerminateProcess(handle, 9):
                            raise OSError(ctypes.get_last_error(), 'Test-owned process cleanup failed')
                        self.assertEqual(kernel.WaitForSingleObject(handle, 5000), 0)
                    elif state != 0:
                        raise OSError('Unknown retained-handle cleanup state')
                except Exception as exc:
                    errors.append(repr(exc))
                finally:
                    if not kernel.CloseHandle(handle):
                        errors.append('CloseHandle failed during fixture cleanup')
        for process in reversed(self.processes):
            try:
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=5)
            except Exception as exc:
                errors.append(repr(exc))
        for stream in self.logs:
            try:
                stream.close()
            except Exception as exc:
                errors.append(repr(exc))
        # Check the exact resolved controlled target immediately before the
        # TemporaryDirectory implementation performs recursive removal.
        try:
            scope = json.loads((self.root / 'test-scope.json').read_text(encoding='utf-8'))
            self.assertEqual(self.root, Path(self.temp.name).resolve())
            self.assertEqual(self.root.parent, Path(tempfile.gettempdir()).resolve())
            self.assertTrue(self.root.name.startswith('queue-proposal-'))
            self.assertEqual(scope['root'], str(self.root))
            self.assertEqual(scope['token'], self.token)
        except Exception as exc:
            errors.append(repr(exc))
        result = self._outcome.result
        test_failed = any(test is self for test, _ in result.failures + result.errors)
        if errors or test_failed:
            self.temp._finalizer.detach()  # Retain scoped failure evidence for root review.
            print(f'Preserved proposal-test fixture: {self.root}', file=sys.stderr)
            if errors:
                self.fail('Cleanup errors: ' + '; '.join(errors))
            return
        self.temp.cleanup()

    @staticmethod
    def native_api():
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        for name, args, result in (
            ('OpenProcess', (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD), wintypes.HANDLE),
            ('WaitForSingleObject', (wintypes.HANDLE, wintypes.DWORD), wintypes.DWORD),
            ('TerminateProcess', (wintypes.HANDLE, wintypes.UINT), wintypes.BOOL),
            ('CloseHandle', (wintypes.HANDLE,), wintypes.BOOL)):
            function = getattr(kernel, name); function.argtypes = args; function.restype = result
        return kernel

    def start(self, mode, name):
        log = (self.root / f'{name}.log').open('xb'); self.logs.append(log)
        process = subprocess.Popen(fixture.command(self.root, self.token, mode, name),
            stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        self.processes.append(process)
        return process

    def wait(self, check, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = check()
            if value:
                return value
            time.sleep(.02)
        self.fail('Bounded fixture condition did not occur')

    def ready(self, name):
        path = self.root / f'{name}.ready.json'
        self.wait(path.exists)
        value = json.loads(path.read_text(encoding='utf-8'))
        if os.name == 'nt' and value['pid'] not in self.owned_handles:
            # Retain a handle while this handshake identifies the live fixture.
            # Finished fixtures need no cleanup and must not be reopened by PID.
            if not (self.root / f'{name}.done.json').exists():
                handle = self.native_api().OpenProcess(0x00100001, False, value['pid'])
                if not handle:
                    raise OSError(ctypes.get_last_error(), 'Cannot retain fixture cleanup handle')
                self.owned_handles[value['pid']] = handle
        return value['pid']

    def release(self, name):
        (self.root / f'{name}.release').touch(exist_ok=False)

    def finished(self, name):
        path = self.root / f'{name}.done.json'
        self.wait(path.exists)
        self.assertIs(json.loads(path.read_text(encoding='utf-8'))['normal_completion'], True)

    def enqueue(self, name, mode='task'):
        return self.service.submit(name, self.root,
            fixture.command(self.root, self.token, mode, name), auto_start=False)

    def status(self, job, expected):
        return self.wait(lambda: (record if (record := self.service.status(job['id']))['state'] in expected else None))


class HandleContractTests(ScopedTest):
    def windows_call(self, *, handle=123, wait_result=258, error=0, wait_error=None, open_error=None, pid=456):
        kernel = types.SimpleNamespace(OpenProcess=mock.Mock(return_value=handle, side_effect=open_error),
            WaitForSingleObject=mock.Mock(return_value=wait_result, side_effect=wait_error),
            CloseHandle=mock.Mock(return_value=True))
        fake_os = types.SimpleNamespace(name='nt', getpid=lambda: 999,
            kill=mock.Mock(side_effect=AssertionError('Windows os.kill is forbidden')))
        original = self.queue.pid_alive
        function = types.FunctionType(original.__code__, dict(original.__globals__, os=fake_os),
                                      original.__name__, original.__defaults__)
        with mock.patch.object(ctypes, 'WinDLL', return_value=kernel, create=True), \
             mock.patch.object(ctypes, 'get_last_error', return_value=error, create=True):
            result = function(pid)
        fake_os.kill.assert_not_called()
        return result, kernel

    def test_handle_state_and_release(self):
        for status, expected in ((0, False), (258, True), (0xFFFFFFFF, True), (128, True), (19, True)):
            with self.subTest(status=status):
                result, kernel = self.windows_call(wait_result=status)
                self.assertIs(result, expected)
                kernel.OpenProcess.assert_called_once_with(0x00100000, False, 456)
                self.assertIs(kernel.OpenProcess.restype, wintypes.HANDLE)
                self.assertEqual(kernel.WaitForSingleObject.argtypes, (wintypes.HANDLE, wintypes.DWORD))
                kernel.WaitForSingleObject.assert_called_once_with(123, 0)
                kernel.CloseHandle.assert_called_once_with(123)

    def test_absent_denied_and_unknown_open_failure(self):
        for error, expected in ((87, False), (5, True), (0, True), (6, True), (299, True)):
            with self.subTest(error=error):
                result, kernel = self.windows_call(handle=None, error=error)
                self.assertIs(result, expected)
                kernel.WaitForSingleObject.assert_not_called()
                kernel.CloseHandle.assert_not_called()

    def test_wait_exception_is_conservative_and_closes(self):
        result, kernel = self.windows_call(wait_error=OSError('synthetic wait failure'))
        self.assertTrue(result)
        kernel.CloseHandle.assert_called_once_with(123)

    def test_open_exception_is_conservative(self):
        result, kernel = self.windows_call(open_error=OSError('synthetic open failure'))
        self.assertTrue(result)
        kernel.WaitForSingleObject.assert_not_called()
        kernel.CloseHandle.assert_not_called()

    def test_invalid_self_and_unrepresentable_pid(self):
        for pid, expected in ((None, False), (0, False), (-1, False), ('123', False), (999, True), (2**40, True)):
            result, kernel = self.windows_call(pid=pid)
            self.assertIs(result, expected)
            kernel.OpenProcess.assert_not_called()

    def test_unix_behavior_unchanged(self):
        for exception, expected in ((None, True), (ProcessLookupError(), False), (PermissionError(), True), (OSError(), False)):
            with self.subTest(exception=type(exception).__name__):
                kill = mock.Mock(side_effect=exception)
                original = self.queue.pid_alive
                function = types.FunctionType(original.__code__, dict(original.__globals__,
                    os=types.SimpleNamespace(name='posix', getpid=lambda: 999, kill=kill)),
                    original.__name__, original.__defaults__)
                self.assertIs(function(456), expected)
                kill.assert_called_once_with(456, 0)

    def test_scope_guards_reject_nonfixture_store_and_cli(self):
        with self.assertRaises(AssertionError):
            self.queue.QueueStore(self.root / 'wrong-store')
        with self.assertRaises(AssertionError):
            self.queue.production_paths()
        with self.assertRaises(AssertionError):
            self.service._spawn_detached_worker()


@unittest.skipUnless(os.name == 'nt', 'Actual Windows process semantics required')
class NativeProcessTests(ScopedTest):
    def test_actual_live_child_survives_and_completes_normally(self):
        child = self.start('task', 'survivor'); pid = self.ready('survivor')
        for _ in range(8):
            self.assertTrue(self.queue.pid_alive(pid))
            self.assertIsNone(child.poll())
        self.release('survivor'); self.finished('survivor')
        self.assertEqual(child.wait(timeout=5), 0)
        self.assertFalse(self.queue.pid_alive(pid))

    def test_cross_process_lease_and_lock_preserve_live_owner(self):
        holder = self.start('holder', 'holder'); pid = self.ready('holder')
        store = self.service.store
        before_lease = store.worker_path.read_bytes()
        before_lock = store.state_lock_path.read_bytes()
        self.assertFalse(self.queue.WorkerLease(store, timeout=.2).acquire())
        with self.assertRaises(self.queue.QueueError):
            self.queue.ExclusiveFileLock(store.state_lock_path, timeout=.2).acquire()
        self.assertEqual(store.worker_path.read_bytes(), before_lease)
        self.assertEqual(store.state_lock_path.read_bytes(), before_lock)
        self.assertTrue(self.service.ensure_worker())
        self.assertTrue(self.queue.pid_alive(pid)); self.assertIsNone(holder.poll())
        self.release('holder'); self.finished('holder')
        self.assertEqual(holder.wait(timeout=5), 0)
        self.assertFalse(store.worker_path.exists()); self.assertFalse(store.state_lock_path.exists())

    def test_concurrent_submit_preserves_worker_and_single_slot(self):
        first = self.enqueue('first')
        worker = self.start('worker', 'worker'); worker_pid = self.ready('worker')
        first_pid = self.ready('first'); self.status(first, {'running'})
        lease = self.service.store.worker_path.read_bytes()
        submitters = [self.start('submit', name) for name in ('second', 'third')]
        for submitter in submitters:
            self.assertEqual(submitter.wait(timeout=8), 0)
        jobs = [json.loads((self.root / f'{name}.submission.json').read_text(encoding='utf-8'))
                for name in ('second', 'third')]
        self.assertEqual(len({first['id'], *(job['id'] for job in jobs)}), 3)
        self.assertEqual(self.service.store.worker_path.read_bytes(), lease)
        self.assertIsNone(worker.poll())
        self.assertTrue(self.queue.pid_alive(worker_pid)); self.assertTrue(self.queue.pid_alive(first_pid))
        for name in ('second', 'third'):
            self.assertFalse((self.root / f'{name}.ready.json').exists())
        self.release('first'); self.finished('first')
        active = self.wait(lambda: next((name for name in ('second', 'third')
            if (self.root / f'{name}.ready.json').exists()), None))
        waiting = 'third' if active == 'second' else 'second'
        self.ready(active)
        self.assertFalse((self.root / f'{waiting}.ready.json').exists())
        self.release(active); self.finished(active)
        self.ready(waiting); self.release(waiting); self.finished(waiting)
        records = [self.status(job, {'succeeded'}) for job in (first, *jobs)]
        self.assertEqual(worker.wait(timeout=8), 0)
        self.finished('worker')
        ordered = sorted(records, key=lambda row: row['started_at'])
        for previous, following in zip(ordered, ordered[1:]):
            self.assertLessEqual(previous['ended_at'], following['started_at'])
        self.assertEqual(len(self.service.list_jobs()), 3)
        self.assertTrue(all(row['exit_status'] == 0 for row in records))

    def test_genuine_worker_loss_reconciles_without_retry(self):
        job = self.enqueue('orphan')
        worker = self.start('worker', 'worker'); self.ready('worker')
        child_pid = self.ready('orphan')
        original = self.wait(lambda: (record if
            (record := self.service.status(job['id']))['state'] == 'running'
            and record['child_pid'] == child_pid else None))
        worker.terminate(); worker.wait(timeout=5)
        self.assertTrue(self.queue.pid_alive(child_pid))
        report = self.service.doctor(repair=True)
        self.assertTrue(report['healthy'], report)
        final = self.status(job, {'interrupted'})
        self.assertEqual(final['child_pid'], original['child_pid'])
        self.assertEqual(final['started_at'], original['started_at'])
        self.assertIsNone(final['exit_status'])
        self.assertEqual(final['error'], 'Worker disappeared; job was not retried')
        self.wait(lambda: not self.queue.pid_alive(child_pid))
        self.assertFalse((self.root / 'orphan.done.json').exists())
        self.assertEqual(len(self.service.list_jobs()), 1)
        self.assertFalse(self.service.store.worker_path.exists())

    def test_queued_and_running_tree_cancellation(self):
        queued = self.enqueue('never-started')
        self.assertEqual(self.service.cancel(queued['id'])['state'], 'canceled')
        self.assertFalse((self.root / 'never-started.ready.json').exists())
        job = self.enqueue('cancel-tree', 'task-tree')
        worker = self.start('worker', 'worker'); self.ready('worker')
        child_pid = self.ready('cancel-tree'); grandchild_pid = self.ready('cancel-tree-grandchild')
        self.status(job, {'running'})
        self.service.cancel(job['id'])
        final = self.status(job, {'canceled'})
        self.assertIsNotNone(final['cancel_requested_at'])
        self.assertEqual(worker.wait(timeout=8), 0)
        self.finished('worker')
        self.wait(lambda: not self.queue.pid_alive(child_pid) and not self.queue.pid_alive(grandchild_pid))
        self.assertFalse((self.root / 'cancel-tree.done.json').exists())
        self.assertFalse((self.root / 'cancel-tree-grandchild.done.json').exists())
        self.assertEqual(len(self.service.list_jobs()), 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
