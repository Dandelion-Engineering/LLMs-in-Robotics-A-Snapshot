"""Small Windows-only owner for the bounded synthetic fixture; no elevation."""
import ctypes as C
from ctypes import wintypes as W
import msvcrt
import os
from pathlib import Path
import subprocess
import time


class BasicLimits(C.Structure):
    _fields_ = [('process_time', C.c_longlong), ('job_time', C.c_longlong),
                ('flags', W.DWORD), ('min_ws', C.c_size_t), ('max_ws', C.c_size_t),
                ('active_limit', W.DWORD), ('affinity', C.c_size_t),
                ('priority', W.DWORD), ('scheduling', W.DWORD)]


class ExtendedLimits(C.Structure):
    _fields_ = [('basic', BasicLimits), ('io', C.c_ulonglong * 6),
                ('process_memory', C.c_size_t), ('job_memory', C.c_size_t),
                ('peak_process_memory', C.c_size_t), ('peak_job_memory', C.c_size_t)]


class Startup(C.Structure):
    _fields_ = [('cb', W.DWORD), ('reserved', W.LPWSTR), ('desktop', W.LPWSTR),
                ('title', W.LPWSTR)] + [(n, W.DWORD) for n in
                ('x', 'y', 'xsize', 'ysize', 'xchars', 'ychars', 'fill', 'flags')] + [
                ('show', W.WORD), ('reserved2_size', W.WORD), ('reserved2', C.c_void_p),
                ('stdin', W.HANDLE), ('stdout', W.HANDLE), ('stderr', W.HANDLE)]


class StartupEx(C.Structure):
    _fields_ = [('startup', Startup), ('attributes', C.c_void_p)]


class ProcessInfo(C.Structure):
    _fields_ = [('process', W.HANDLE), ('thread', W.HANDLE), ('pid', W.DWORD), ('tid', W.DWORD)]


class ProcessEntry(C.Structure):
    _fields_ = [('size', W.DWORD), ('usage', W.DWORD), ('pid', W.DWORD),
                ('heap', C.c_size_t), ('module', W.DWORD), ('threads', W.DWORD),
                ('parent', W.DWORD), ('priority', W.LONG), ('flags', W.DWORD),
                ('exe', W.WCHAR * 260)]


class ProcessList(C.Structure):
    _fields_ = [('assigned', W.DWORD), ('count', W.DWORD), ('pids', C.c_size_t * 32)]


K = C.WinDLL('kernel32', use_last_error=True)
for _name, _args, _result in [
    ('CreateJobObjectW', [C.c_void_p, W.LPCWSTR], W.HANDLE),
    ('SetInformationJobObject', [W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL),
    ('QueryInformationJobObject', [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p], W.BOOL),
    ('TerminateJobObject', [W.HANDLE, W.UINT], W.BOOL),
    ('InitializeProcThreadAttributeList', [C.c_void_p, W.DWORD, W.DWORD, C.POINTER(C.c_size_t)], W.BOOL),
    ('UpdateProcThreadAttribute', [C.c_void_p, W.DWORD, C.c_size_t, C.c_void_p, C.c_size_t, C.c_void_p, C.c_void_p], W.BOOL),
    ('DeleteProcThreadAttributeList', [C.c_void_p], None),
    ('CreateProcessW', [W.LPCWSTR, W.LPWSTR, C.c_void_p, C.c_void_p, W.BOOL,
                        W.DWORD, C.c_void_p, W.LPCWSTR, C.c_void_p, C.POINTER(ProcessInfo)], W.BOOL),
    ('OpenProcess', [W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
    ('IsProcessInJob', [W.HANDLE, W.HANDLE, C.POINTER(W.BOOL)], W.BOOL),
    ('QueryFullProcessImageNameW', [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)], W.BOOL),
    ('GetProcessTimes', [W.HANDLE, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p], W.BOOL),
    ('WaitForSingleObject', [W.HANDLE, W.DWORD], W.DWORD),
    ('GetExitCodeProcess', [W.HANDLE, C.POINTER(W.DWORD)], W.BOOL),
    ('CloseHandle', [W.HANDLE], W.BOOL),
    ('CreateToolhelp32Snapshot', [W.DWORD, W.DWORD], W.HANDLE),
    ('Process32FirstW', [W.HANDLE, C.POINTER(ProcessEntry)], W.BOOL),
    ('Process32NextW', [W.HANDLE, C.POINTER(ProcessEntry)], W.BOOL),
]:
    _fn = getattr(K, _name)
    _fn.argtypes, _fn.restype = _args, _result


def checked(value):
    if not value:
        raise C.WinError(C.get_last_error())
    return value


def process_parent(pid):
    snap = K.CreateToolhelp32Snapshot(2, 0)
    if snap == C.c_void_p(-1).value:
        raise C.WinError(C.get_last_error())
    try:
        row = ProcessEntry()
        row.size = C.sizeof(row)
        more = K.Process32FirstW(snap, C.byref(row))
        while more:
            if row.pid == pid:
                return int(row.parent)
            more = K.Process32NextW(snap, C.byref(row))
        raise RuntimeError('PID absent from process inventory')
    finally:
        checked(K.CloseHandle(snap))


def describe(handle, pid):
    size = W.DWORD(32768)
    image = C.create_unicode_buffer(size.value)
    checked(K.QueryFullProcessImageNameW(handle, 0, image, C.byref(size)))
    stamps = [C.c_ulonglong() for _ in range(4)]
    checked(K.GetProcessTimes(handle, *(C.byref(x) for x in stamps)))
    return {'pid': pid, 'image': image.value, 'creation_filetime': stamps[0].value,
            'parent_pid': process_parent(pid)}


class OwnedProcess:
    """Atomic job assignment prevents launcher/interpreter escape races."""
    def __init__(self, argv, cwd, stdout_path, stderr_path):
        self.job = self.process = self.ready_handle = None
        self.pid = None
        self.identity = None
        self.returncode = None
        self.retirement = None
        self.job = checked(K.CreateJobObjectW(None, None))
        try:
            limits = ExtendedLimits()
            limits.basic.flags = 0x2000  # KILL_ON_JOB_CLOSE; no breakaway flags.
            checked(K.SetInformationJobObject(self.job, 9, C.byref(limits), C.sizeof(limits)))
            with open(os.devnull, 'rb') as stdin, open(stdout_path, 'xb') as stdout, open(stderr_path, 'xb') as stderr:
                handles = [msvcrt.get_osfhandle(x.fileno()) for x in (stdin, stdout, stderr)]
                for handle in handles:
                    os.set_handle_inheritable(handle, True)
                attr_size = C.c_size_t()
                K.InitializeProcThreadAttributeList(None, 2, 0, C.byref(attr_size))
                attributes = C.create_string_buffer(attr_size.value)
                checked(K.InitializeProcThreadAttributeList(attributes, 2, 0, C.byref(attr_size)))
                try:
                    jobs = (W.HANDLE * 1)(self.job)
                    inherited = (W.HANDLE * 3)(*handles)
                    checked(K.UpdateProcThreadAttribute(attributes, 0, 0x2000D, jobs, C.sizeof(jobs), None, None))
                    checked(K.UpdateProcThreadAttribute(attributes, 0, 0x20002, inherited, C.sizeof(inherited), None, None))
                    startup = StartupEx()
                    startup.startup.cb = C.sizeof(startup)
                    startup.startup.flags = 0x100  # USESTDHANDLES
                    startup.startup.stdin, startup.startup.stdout, startup.startup.stderr = handles
                    startup.attributes = C.cast(attributes, C.c_void_p)
                    info = ProcessInfo()
                    command = C.create_unicode_buffer(subprocess.list2cmdline(list(map(str, argv))))
                    checked(K.CreateProcessW(str(argv[0]), command, None, None, True,
                        0x08080000, None, str(cwd), C.byref(startup), C.byref(info)))
                    self.process, self.pid = info.process, int(info.pid)
                    checked(K.CloseHandle(info.thread))
                finally:
                    K.DeleteProcThreadAttributeList(attributes)
                    for handle in handles:
                        os.set_handle_inheritable(handle, False)
            self.launch_identity = describe(self.process, self.pid)
            self.launch_argv = list(map(str, argv))
        except BaseException:
            self.close()
            raise

    def pids(self):
        rows = ProcessList()
        checked(K.QueryInformationJobObject(self.job, 3, C.byref(rows), C.sizeof(rows), None))
        if rows.count != rows.assigned or rows.count > 32:
            raise RuntimeError('Incomplete private job process inventory')
        return [int(x) for x in rows.pids[:rows.count]]

    def poll(self):
        state = K.WaitForSingleObject(self.process, 0)
        if state == 258:
            return None
        if state != 0:
            raise C.WinError(C.get_last_error())
        code = W.DWORD()
        checked(K.GetExitCodeProcess(self.process, C.byref(code)))
        self.returncode = int(code.value)
        return self.returncode

    def wait(self, timeout):
        deadline = time.monotonic() + timeout
        while self.poll() is None:
            if time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(self.launch_argv, timeout)
            time.sleep(.01)
        return self.returncode

    def validate_ready(self, ready, expected_images, fixture_out):
        pid, port = ready.get('pid'), ready.get('port')
        if (type(pid) is not int or pid <= 0 or type(port) is not int or not 1 <= port <= 65535
                or ready.get('address') != '127.0.0.1'
                or ready.get('schema') != 'campaign002-tcp-trace-coverage-ready-1'
                or ready.get('trace_started_by_fixture') is not False
                or ready.get('gate') != str(fixture_out / 'release.json')):
            raise RuntimeError('Invalid synthetic endpoint metadata')
        handle = checked(K.OpenProcess(0x101000, False, pid))  # SYNCHRONIZE | QUERY_LIMITED_INFORMATION
        try:
            member = W.BOOL()
            checked(K.IsProcessInJob(handle, self.job, C.byref(member)))
            identity = describe(handle, pid)
            if (not member.value or pid not in self.pids()
                    or Path(identity['image']).resolve() not in {Path(p).resolve() for p in expected_images}
                    or identity['creation_filetime'] < self.launch_identity['creation_filetime']
                    or (pid != self.pid and identity['parent_pid'] != self.pid)
                    or self.poll() is not None or K.WaitForSingleObject(handle, 0) != 258):
                raise RuntimeError('Ready process is not the live owned venv launch or direct interpreter child')
            self.ready_handle, handle = handle, None
            self.identity = {'launcher': self.launch_identity, 'ready_process': identity,
                             'same_pid': pid == self.pid, 'job_pids': self.pids(),
                             'membership': True, 'validated': True, 'launch_argv': self.launch_argv}
            return self.identity
        finally:
            if handle:
                checked(K.CloseHandle(handle))

    def retire(self):
        before = self.pids()
        forced = bool(before)
        if before:
            checked(K.TerminateJobObject(self.job, 125))
        deadline = time.monotonic() + 3
        while self.pids() and time.monotonic() < deadline:
            time.sleep(.01)
        after = self.pids()
        signaled = all(K.WaitForSingleObject(h, 0) == 0 for h in (self.process, self.ready_handle) if h)
        self.retirement = {'before_pids': before, 'after_pids': after, 'forced': forced,
                           'retained_handles_signaled': signaled, 'qualified': not after and signaled}
        if not self.retirement['qualified']:
            raise RuntimeError('Private fixture job did not retire completely')
        return self.retirement

    def close(self):
        # Closing the private job kills any remaining owned descendants.
        for name in ('job', 'ready_handle', 'process'):
            handle = getattr(self, name, None)
            if handle:
                checked(K.CloseHandle(handle))
                setattr(self, name, None)
