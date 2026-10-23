"""Prospective native host memory ceiling and bounded measured-loop receipts."""
from array import array
import ctypes
from ctypes import wintypes
import hashlib
import math
import os
from pathlib import Path
import sys
import time

SCHEMA = 'rci-host-memory-1'
FILE = 'memory-samples.bin'
HARD_LIMIT = 2 * 1024**3
BASELINE_LIMIT = 1024**3
SOFT_ABSOLUTE = 1536 * 1024**2
SOFT_GROWTH = 512 * 1024**2
INTERVAL = .1
MAX_GAP = .2
FIELDS = ('wall_read_start_s', 'wall_read_end_s', 'private_commit_bytes', 'working_set_bytes',
          'peak_private_commit_bytes', 'peak_working_set_bytes', 'kind')


class MemoryPolicyError(RuntimeError):
    pass


class BasicLimits(ctypes.Structure):
    _fields_ = [('PerProcessUserTimeLimit', ctypes.c_longlong), ('PerJobUserTimeLimit', ctypes.c_longlong),
                ('LimitFlags', wintypes.DWORD), ('MinimumWorkingSetSize', ctypes.c_size_t),
                ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', wintypes.DWORD),
                ('Affinity', ctypes.c_size_t), ('PriorityClass', wintypes.DWORD), ('SchedulingClass', wintypes.DWORD)]


class IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in ('ReadOperationCount', 'WriteOperationCount',
                 'OtherOperationCount', 'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [('BasicLimitInformation', BasicLimits), ('IoInfo', IoCounters),
                ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]


class MemoryCounters(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize',
        'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
        'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage', 'PrivateUsage')]


class SingleProcessList(ctypes.Structure):
    _fields_ = [('NumberOfAssignedProcesses', wintypes.DWORD), ('NumberOfProcessIdsInList', wintypes.DWORD),
                ('ProcessIdList', ctypes.c_size_t * 1)]


class NativeJobMemory:
    """An unnamed job contains only this dedicated native host and its lifetime.

    The job has no kill-on-close flag and membership is not detached/restored.
    The process commitment limit continues for the host process lifetime.
    """
    def __init__(self):
        if sys.platform != 'win32':
            raise MemoryPolicyError('Windows native process commitment limit required')
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        specs = {
            'GetCurrentProcess': ([], ctypes.c_void_p),
            'CreateJobObjectW': ([ctypes.c_void_p, wintypes.LPCWSTR], ctypes.c_void_p),
            'SetInformationJobObject': ([ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
            'QueryInformationJobObject': ([ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
            'AssignProcessToJobObject': ([ctypes.c_void_p, ctypes.c_void_p], wintypes.BOOL),
            'IsProcessInJob': ([ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL)], wintypes.BOOL),
            'K32GetProcessMemoryInfo': ([ctypes.c_void_p, ctypes.POINTER(MemoryCounters), wintypes.DWORD], wintypes.BOOL),
            'CloseHandle': ([ctypes.c_void_p], wintypes.BOOL),
        }
        for name, (arguments, result) in specs.items():
            function = getattr(self.kernel, name)
            function.argtypes, function.restype = arguments, result
        self.process = self.kernel.GetCurrentProcess()
        self.job = None

    def checked(self, value, operation):
        if not value:
            raise MemoryPolicyError(operation + ' failed: ' + str(ctypes.get_last_error()))
        return value

    def apply(self):
        self.job = self.checked(self.kernel.CreateJobObjectW(None, None), 'CreateJobObjectW')
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x100
        limits.ProcessMemoryLimit = HARD_LIMIT
        self.checked(self.kernel.SetInformationJobObject(self.job, 9, ctypes.byref(limits), ctypes.sizeof(limits)), 'SetInformationJobObject')
        self.checked(self.kernel.AssignProcessToJobObject(self.job, self.process), 'AssignProcessToJobObject')
        return self.readback()

    def readback(self):
        member = wintypes.BOOL()
        limits, returned = ExtendedLimits(), wintypes.DWORD()
        self.checked(self.kernel.IsProcessInJob(self.process, self.job, ctypes.byref(member)), 'IsProcessInJob')
        self.checked(self.kernel.QueryInformationJobObject(self.job, 9, ctypes.byref(limits), ctypes.sizeof(limits), ctypes.byref(returned)), 'QueryInformationJobObject')
        processes = SingleProcessList()
        self.checked(self.kernel.QueryInformationJobObject(self.job, 3, ctypes.byref(processes), ctypes.sizeof(processes), None), 'QueryInformationJobObject(process list)')
        result = {'process_is_member': bool(member.value), 'limit_flags': int(limits.BasicLimitInformation.LimitFlags),
                  'process_memory_limit_bytes': int(limits.ProcessMemoryLimit),
                  'peak_process_memory_used_bytes': int(limits.PeakProcessMemoryUsed),
                  'peak_job_memory_used_bytes': int(limits.PeakJobMemoryUsed),
                  'returned_structure_bytes': returned.value, 'expected_structure_bytes': ctypes.sizeof(limits),
                  'assigned_process_count': int(processes.NumberOfAssignedProcesses),
                  'listed_process_count': int(processes.NumberOfProcessIdsInList),
                  'process_ids': [int(processes.ProcessIdList[0])]}
        if (not result['process_is_member'] or result['limit_flags'] != 0x100
                or result['process_memory_limit_bytes'] != HARD_LIMIT
                or result['returned_structure_bytes'] != result['expected_structure_bytes']
                or result['assigned_process_count'] != 1 or result['listed_process_count'] != 1
                or result['process_ids'] != [os.getpid()]
                or result['peak_process_memory_used_bytes'] > HARD_LIMIT):
            raise MemoryPolicyError('Native JobObject memory limit readback differs')
        return result

    def memory(self):
        counters = MemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        self.checked(self.kernel.K32GetProcessMemoryInfo(self.process, ctypes.byref(counters), counters.cb), 'K32GetProcessMemoryInfo')
        return (int(counters.PrivateUsage), int(counters.WorkingSetSize),
                int(counters.PeakPagefileUsage), int(counters.PeakWorkingSetSize))

    def close(self):
        if self.job is not None:
            self.checked(self.kernel.CloseHandle(self.job), 'CloseHandle(job)')
            self.job = None
        return True


class MemoryGuard:
    def __init__(self, wall_cap_s, *, backend=None, clock=time.perf_counter):
        if not math.isfinite(wall_cap_s) or wall_cap_s <= 0:
            raise ValueError('Finite bounded memory sampling duration required')
        self.backend, self.clock = backend, clock
        self.capacity = math.ceil(wall_cap_s / INTERVAL) + 16
        self.values = array('d', [0.]) * (self.capacity * len(FIELDS))
        self.count = 0
        self.origin = self.next_due = None
        self.baseline = None
        self.soft_limit = None
        self.error = None
        self.finished = False
        self.receipt = {'schema': SCHEMA, 'platform': sys.platform, 'pid': os.getpid(),
                        'hard_process_commit_limit_bytes': HARD_LIMIT,
                        'scope': 'Dedicated native host process commitment; no WSL/model-process limit and no new watchdog.',
                        'applied': False, 'final_readback_verified': False, 'handle_closed': False,
                        'membership_detached': False,
                        'membership_scope': 'Job membership/limit persists for this bounded host process lifetime; only our job handle closes.'}

    @property
    def reserved_bytes(self):
        return self.capacity * len(FIELDS) * 8 + 32768

    def fail(self, message):
        self.error = self.error or message
        raise MemoryPolicyError(message)

    def apply(self):
        try:
            self.backend = self.backend or NativeJobMemory()
            self.receipt['initial_readback'] = self.backend.apply()
            self.receipt['applied'] = True
        except Exception as exc:
            self.fail(type(exc).__name__ + ': ' + str(exc))

    def read(self):
        start = self.clock()
        try:
            data = self.backend.memory()
        except Exception as exc:
            self.fail('Native memory query failed: ' + str(exc))
        end = self.clock()
        if len(data) != 4 or any(type(value) is not int or value < 0 for value in data) or end < start:
            self.fail('Invalid native memory counters or read clocks')
        return start, end, data

    def admit(self):
        if not self.receipt['applied']:
            self.fail('Native memory ceiling not established')
        start, end, data = self.read()
        self.baseline = {'read_start_qpc_s': start, 'read_end_qpc_s': end,
                         'private_commit_bytes': data[0], 'working_set_bytes': data[1],
                         'peak_private_commit_bytes': data[2], 'peak_working_set_bytes': data[3]}
        if data[0] >= BASELINE_LIMIT:
            self.fail('Host baseline private commitment reaches admission ceiling')
        self.soft_limit = min(SOFT_ABSOLUTE, data[0] + SOFT_GROWTH)

    def start(self, origin):
        if self.baseline is None or self.origin is not None:
            self.fail('Memory admission missing or measurement already started')
        self.origin = origin
        self.sample(1)

    def sample(self, kind=0):
        if self.finished or self.origin is None or self.count >= self.capacity:
            self.fail('Memory sample interval/capacity invalid')
        start, end, data = self.read()
        row = (start - self.origin, end - self.origin, *data, kind)
        offset = self.count * len(FIELDS)
        for index, value in enumerate(row):
            self.values[offset + index] = value
        self.count += 1
        self.next_due = end + INTERVAL
        if row[0] < 0 or (self.count > 1 and row[1] - self.values[offset - len(FIELDS) + 1] > MAX_GAP):
            self.fail('Memory sampling boundary or maximum gap violated')
        if self.count == 1 and row[1] > MAX_GAP:
            self.fail('Origin memory sample delayed beyond maximum gap')
        if data[0] >= self.soft_limit:
            self.fail('Host private commitment reaches declared soft ceiling')
        if data[2] > HARD_LIMIT:
            self.fail('Host lifetime peak private commitment exceeds hard ceiling')

    def poll(self):
        if self.clock() >= self.next_due:
            self.sample()
            return True
        return False

    def finish(self):
        if not self.finished and self.origin is not None:
            self.sample(2)
            self.finished = True

    def close(self):
        if self.backend is not None:
            try:
                if self.receipt['applied']:
                    self.receipt['final_readback'] = self.backend.readback()
                    self.receipt['final_readback_verified'] = True
                    start, end, data = self.read()
                    self.receipt['post_cleanup_memory'] = {'read_start_qpc_s': start, 'read_end_qpc_s': end,
                        'private_commit_bytes': data[0], 'working_set_bytes': data[1],
                        'peak_private_commit_bytes': data[2], 'peak_working_set_bytes': data[3]}
            except Exception as exc:
                self.error = self.error or 'Final native memory readback failed: ' + str(exc)
            finally:
                try:
                    self.receipt['handle_closed'] = self.backend.close() is True
                    if not self.receipt['handle_closed']:
                        self.error = self.error or 'Native job handle closure unverified'
                except Exception as exc:
                    self.error = self.error or 'Native job handle closure failed: ' + str(exc)

    def persist(self, directory, terminal):
        if self.finished and self.count >= 2:
            final_end = self.values[(self.count - 1) * len(FIELDS) + 1]
            tail_gap = terminal['wall_elapsed_s'] - final_end
            if not 0 <= tail_gap <= MAX_GAP:
                self.error = self.error or 'Terminal memory sample does not cover final timing boundary'
        path = Path(directory) / FILE
        values = self.values[:self.count * len(FIELDS)]
        if values.itemsize != 8:
            raise MemoryPolicyError('Memory ledger requires float64')
        if sys.byteorder != 'little':
            values.byteswap()
        with path.open('xb') as stream:
            values.tofile(stream); stream.flush(); os.fsync(stream.fileno())
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        passed = (self.error is None and self.finished and self.count >= 2 and self.receipt['applied']
                  and self.receipt['final_readback_verified'] and self.receipt['handle_closed'])
        return {'schema': SCHEMA, 'sample_file': FILE, 'sha256': digest, 'byte_count': path.stat().st_size,
                'sample_count': self.count, 'maximum_sample_capacity': self.capacity,
                'encoding': 'little-endian float64 rows', 'fields': list(FIELDS),
                'kind_codes': {'periodic': 0, 'origin': 1, 'terminal': 2},
                'sampling_interval_s': INTERVAL, 'maximum_permitted_sample_gap_s': MAX_GAP,
                'baseline_private_commit_limit_bytes': BASELINE_LIMIT,
                'soft_absolute_limit_bytes': SOFT_ABSOLUTE, 'soft_growth_limit_bytes': SOFT_GROWTH,
                'soft_limit_bytes': self.soft_limit, 'baseline': self.baseline,
                'loop_origin_qpc_s': self.origin, 'terminal_wall_elapsed_s': terminal['wall_elapsed_s'],
                'native_job': self.receipt, 'complete': self.finished, 'error': self.error, 'passed': bool(passed),
                'scope': 'Origin and terminal memory reads occur inside the measured loop; periodic reads target 100ms QPC cadence. Soft ceiling applies to observed current private commitment; the native job ceiling covers allocations between samples. Lifetime peaks can include initialization. Cleanup memory is separate; job membership is not detached.'}
