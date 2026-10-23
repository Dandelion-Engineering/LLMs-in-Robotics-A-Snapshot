"""Named Windows job owned by this driver, joined by its declared probe only."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os


def api():
    if os.name != 'nt':
        raise RuntimeError('Recovery qualification uses the declared Windows job containment')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    for name, args, result in (
        ('CreateJobObjectW', [ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
        ('OpenJobObjectW', [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE),
        ('AssignProcessToJobObject', [wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
        ('SetInformationJobObject', [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
        ('TerminateJobObject', [wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
        ('GetCurrentProcess', [], wintypes.HANDLE),
        ('CloseHandle', [wintypes.HANDLE], wintypes.BOOL)):
        function = getattr(kernel, name); function.argtypes = args; function.restype = result
    return kernel


class JobCap:
    def __init__(self, name):
        kernel = api()
        self.kernel = kernel
        ctypes.set_last_error(0)
        self.handle = kernel.CreateJobObjectW(None, name)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == 183:
            kernel.CloseHandle(self.handle); self.handle = None
            raise RuntimeError('Unique probe job name already exists')
        class Basic(ctypes.Structure):
            _fields_ = [('ProcessTime', ctypes.c_int64), ('JobTime', ctypes.c_int64), ('LimitFlags', wintypes.DWORD),
                ('MinimumWorkingSet', ctypes.c_size_t), ('MaximumWorkingSet', ctypes.c_size_t),
                ('ActiveProcessLimit', wintypes.DWORD), ('Affinity', ctypes.c_size_t),
                ('PriorityClass', wintypes.DWORD), ('SchedulingClass', wintypes.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in ('ReadOperations', 'WriteOperations', 'OtherOperations',
                                                           'ReadBytes', 'WriteBytes', 'OtherBytes')]
        class Extended(ctypes.Structure):
            _fields_ = [('Basic', Basic), ('IO', IO), ('ProcessMemory', ctypes.c_size_t), ('JobMemory', ctypes.c_size_t),
                        ('PeakProcessMemory', ctypes.c_size_t), ('PeakJobMemory', ctypes.c_size_t)]
        info = Extended(); info.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            error = ctypes.get_last_error(); self.close(); raise ctypes.WinError(error)

    def terminate(self):
        if self.handle and not self.kernel.TerminateJobObject(self.handle, 124):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle); self.handle = None


def join_job(name):
    kernel = api()
    handle = kernel.OpenJobObjectW(1, False, name)  # ASSIGN_PROCESS; cannot open an unrelated process.
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not kernel.AssignProcessToJobObject(handle, kernel.GetCurrentProcess()):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.CloseHandle(handle)
