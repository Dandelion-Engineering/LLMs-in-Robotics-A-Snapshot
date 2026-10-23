"""Windows sharing fault injection; no simulation or model invocation."""
import errno
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import supervisor


class AtomicReplaceChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.target = Path(self.temp.name) / "state.json"
        self.target.write_bytes(b"old committed bytes")
        self.original_stats = dict(supervisor.ATOMIC_REPLACE_RETRIES)
        supervisor.ATOMIC_REPLACE_RETRIES.update(retries=0, exhausted=0, requested_wait_s=0.)

    def tearDown(self):
        supervisor.ATOMIC_REPLACE_RETRIES.update(self.original_stats)
        self.temp.cleanup()

    def windows_error(self, code=5):
        error = PermissionError(errno.EACCES, "synthetic Windows sharing denial")
        error.winerror = code
        return error

    def test_transient_windows_denial_replaces_once_without_rewriting_stage(self):
        original = supervisor.os.replace
        calls = []
        def replace(source, destination):
            calls.append((Path(source), Path(destination)))
            self.assertEqual(Path(source).read_bytes(), b"new bytes")
            self.assertEqual(self.target.read_bytes(), b"old committed bytes")
            if len(calls) <= 2:
                raise self.windows_error(32 if len(calls) == 1 else 5)
            return original(source, destination)
        with patch.object(supervisor.os, "replace", side_effect=replace), patch.object(supervisor.time, "sleep") as sleep:
            supervisor.atomic_bytes(self.target, b"new bytes")
        self.assertEqual(self.target.read_bytes(), b"new bytes")
        self.assertEqual(len(calls), 3)
        self.assertEqual([x.args[0] for x in sleep.call_args_list], [.005, .01])
        self.assertEqual(supervisor.ATOMIC_REPLACE_RETRIES["retries"], 2)
        self.assertFalse(self.target.with_name("state.json.next").exists())

    def test_permanent_windows_denial_is_bounded_and_keeps_last_good(self):
        with patch.object(supervisor.os, "replace", side_effect=self.windows_error()) as replace, patch.object(supervisor.time, "sleep") as sleep:
            with self.assertRaises(PermissionError):
                supervisor.atomic_bytes(self.target, b"new bytes")
        self.assertEqual(replace.call_count, 5)
        self.assertEqual(sleep.call_count, 4)
        self.assertAlmostEqual(sum(x.args[0] for x in sleep.call_args_list), .075)
        self.assertEqual(supervisor.ATOMIC_REPLACE_RETRIES["exhausted"], 1)
        self.assertEqual(self.target.read_bytes(), b"old committed bytes")
        self.assertEqual(self.target.with_name("state.json.next").read_bytes(), b"new bytes")

    def test_other_permission_and_io_errors_propagate_without_retry(self):
        for error in (PermissionError(errno.EACCES, "plain permission denial"),
                      self.windows_error(1314), OSError(errno.ENOSPC, "disk full")):
            with self.subTest(error=error), patch.object(supervisor.os, "replace", side_effect=error) as replace, patch.object(supervisor.time, "sleep") as sleep:
                with self.assertRaises(OSError):
                    supervisor.atomic_bytes(self.target, b"new bytes")
                self.assertEqual(replace.call_count, 1)
                sleep.assert_not_called()
                self.assertEqual(self.target.read_bytes(), b"old committed bytes")

    def test_fsync_failure_never_attempts_replace(self):
        with patch.object(supervisor.os, "fsync", side_effect=OSError(errno.ENOSPC, "disk full")), patch.object(supervisor.os, "replace") as replace:
            with self.assertRaises(OSError):
                supervisor.atomic_bytes(self.target, b"new bytes")
            replace.assert_not_called()
        self.assertEqual(self.target.read_bytes(), b"old committed bytes")

    @unittest.skipUnless(os.name == "nt", "Actual Windows file-sharing semantics")
    def test_actual_windows_reader_without_delete_sharing_recovers_after_close(self):
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        # A real read handle permits other readers/writers but denies delete
        # sharing, just as the failed smoke's external live-file inspection did.
        handle = kernel.CreateFileW(str(self.target), 0x80000000, 3, None, 3, 0x80, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        closed = False
        errors = []
        original = supervisor.os.replace
        def release(_delay):
            nonlocal closed
            if not closed:
                self.assertTrue(kernel.CloseHandle(handle))
                closed = True
        def replace(source, destination):
            try:
                return original(source, destination)
            except PermissionError as error:
                errors.append(error.winerror)
                raise
        try:
            with patch.object(supervisor.os, "replace", side_effect=replace), patch.object(supervisor.time, "sleep", side_effect=release):
                supervisor.atomic_bytes(self.target, b"new bytes")
            self.assertTrue(closed)
            self.assertEqual(len(errors), 1)
            self.assertIn(errors[0], (5, 32, 33))
            self.assertEqual(self.target.read_bytes(), b"new bytes")
        finally:
            if not closed:
                kernel.CloseHandle(handle)


if __name__ == "__main__":
    unittest.main()
