"""Prospective loop timing; never alters or reinterprets Campaign 001 evidence."""
from __future__ import annotations

from array import array
import ast
from contextlib import contextmanager
import ctypes
import hashlib
import heapq
import json
import math
import os
from pathlib import Path
import struct
import sys
import time

SCHEMA = "rci-prospective-timing-2"
REPO = Path(__file__).resolve().parents[4]
MONITOR_SOURCE = REPO / "Long-Horizon Adaptive Robotics Expirement/Runtime 004/experiment.py"
SAMPLE_FILE = "timing-samples.bin"
METADATA_FILE = "timing-v2.json"


def qpc_clock_context():
    """Retain primary/legacy clock identities and a bounded cross-clock bracket."""
    before = time.perf_counter()
    auxiliary = time.monotonic()
    unix = time.time()
    after = time.perf_counter()
    frequency = None
    if sys.platform == 'win32':
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.QueryPerformanceFrequency.argtypes = [ctypes.POINTER(ctypes.c_longlong)]
        kernel.QueryPerformanceFrequency.restype = ctypes.c_int
        value = ctypes.c_longlong()
        if not kernel.QueryPerformanceFrequency(ctypes.byref(value)) or value.value <= 0:
            raise RuntimeError('QueryPerformanceFrequency unavailable')
        frequency = value.value
    return {'primary_clock_name': 'perf_counter', 'primary_clock': vars(time.get_clock_info('perf_counter')),
            'qpc_frequency_hz': frequency, 'auxiliary_clock_name': 'monotonic',
            'auxiliary_clock': vars(time.get_clock_info('monotonic')),
            'cross_clock_sample': {'perf_counter_before_s': before, 'monotonic_s': auxiliary, 'unix_s': unix,
                                   'perf_counter_after_s': after},
            'scope': 'Prospective QPC pacing and measurement. The auxiliary clock bracket relates journal chronology; no retrospective correction or claim of eliminating actual stalls.'}


def load_monitor(source=MONITOR_SOURCE):
    source = Path(source)
    raw = source.read_bytes()
    text = raw.decode("utf-8")
    tree = ast.parse(text)
    nodes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TimingMonitor"]
    if len(nodes) != 1:
        raise ValueError("Exactly one frozen TimingMonitor required")
    code = ast.get_source_segment(text, nodes[0])
    namespace = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace)
    return namespace["TimingMonitor"], {
        "path": source.relative_to(REPO).as_posix(),
        "file_sha256": hashlib.sha256(raw).hexdigest(),
        "class_sha256": hashlib.sha256(code.encode()).hexdigest(),
    }


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


class WindowsScheduling:
    """Bounded local process policy, restored even on failures; never real time."""
    def __init__(self):
        self.receipt = {"schema": "rci-windows-scheduling-1", "platform": sys.platform,
                        "requested_priority": "ABOVE_NORMAL_PRIORITY_CLASS", "timer_period_ms": 1,
                        "applied": False, "restored": False}
        self.kernel = self.winmm = None
        self.handle = None
        self.previous = None
        self.timer_started = False
        self.priority_changed = False

    def apply(self):
        if sys.platform != "win32":
            self.receipt["error"] = "Prospective deployment requires Windows scheduling qualification"
            return self.receipt
        try:
            self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            self.kernel.GetCurrentProcess.restype = ctypes.c_void_p
            self.kernel.GetPriorityClass.argtypes = [ctypes.c_void_p]
            self.kernel.GetPriorityClass.restype = ctypes.c_uint32
            self.kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            self.kernel.SetPriorityClass.restype = ctypes.c_int
            self.handle = self.kernel.GetCurrentProcess()
            self.previous = self.kernel.GetPriorityClass(self.handle)
            if not self.previous:
                raise ctypes.WinError(ctypes.get_last_error())
            self.receipt["previous_priority_class"] = self.previous
            if not self.kernel.SetPriorityClass(self.handle, 0x8000):
                raise ctypes.WinError(ctypes.get_last_error())
            self.priority_changed = True
            self.receipt["observed_priority_class"] = self.kernel.GetPriorityClass(self.handle)
            if self.receipt["observed_priority_class"] != 0x8000:
                raise RuntimeError("Process priority did not match requested AboveNormal")
            self.winmm = ctypes.WinDLL("winmm", use_last_error=True)
            self.winmm.timeBeginPeriod.argtypes = [ctypes.c_uint]
            self.winmm.timeBeginPeriod.restype = ctypes.c_uint
            self.winmm.timeEndPeriod.argtypes = [ctypes.c_uint]
            self.winmm.timeEndPeriod.restype = ctypes.c_uint
            status = self.winmm.timeBeginPeriod(1)
            self.receipt["time_begin_period_status"] = int(status)
            if status:
                raise RuntimeError("timeBeginPeriod(1) failed: " + str(status))
            self.timer_started = True
            self.receipt["applied"] = True
        except Exception as error:
            self.receipt["error"] = type(error).__name__ + ": " + str(error)
        return self.receipt

    def restore(self):
        errors = []
        if self.timer_started:
            status = int(self.winmm.timeEndPeriod(1))
            self.receipt["time_end_period_status"] = status
            if status:
                errors.append("timeEndPeriod failed: " + str(status))
            self.timer_started = False
        if self.priority_changed:
            if not self.kernel.SetPriorityClass(self.handle, self.previous):
                errors.append("Priority restoration failed: " + str(ctypes.get_last_error()))
            actual = int(self.kernel.GetPriorityClass(self.handle))
            self.receipt["restored_priority_class"] = actual
            if actual != self.previous:
                errors.append("Restored priority differs from original")
            self.priority_changed = False
        self.receipt["restore_errors"] = errors
        self.receipt["restored"] = not errors and bool(self.receipt["applied"])
        return self.receipt


class TimingCapture:
    """Two float64 clocks per sample; bounded memory, file I/O after timing ends.

    Exact start precedes the first gateway/physics work. Loop-entry samples catch
    scheduler delay before physics catch-up; loop-exit includes all host work.
    Phase intervals describe wall/CPU association, not a causal scheduler trace.
    """
    def __init__(self, origin, sim_origin, *, max_samples, clock=time.perf_counter,
                 cpu_clock=time.thread_time, process_cpu_clock=time.process_time,
                 clock_info=None, monitor_bundle=None, clock_context=None):
        if not finite(origin) or not finite(sim_origin) or type(max_samples) is not int or max_samples < 2:
            raise ValueError("Invalid clock origin or bounded sample capacity")
        monitor_type, self.monitor_source = monitor_bundle or load_monitor()
        self.monitor = monitor_type()
        self.origin, self.sim_origin = origin, sim_origin
        self.clock, self.cpu_clock = clock, cpu_clock
        self.process_cpu_clock = process_cpu_clock
        self.max_samples = max_samples
        self.values = array("d")
        self.terminal = None
        self.active_phase = None
        self.garbage_collection = None
        self.host_memory = None
        self.phases = {}
        self.slow = []
        self.slow_by_phase = {}
        self.slow_id = 0
        self.maximum_sample = {"index": 0, "wall_elapsed_s": 0., "sim_elapsed_s": 0., "lag_s": 0.}
        info = clock_info or vars(time.get_clock_info("perf_counter"))
        self.loop_origin = {"monotonic_s": origin, "initial_sim_s": sim_origin, "clock": info}
        if clock_context is not None:
            self.loop_origin.update(clock_name='perf_counter', clock_context=clock_context)
        self.observe_relative(0., 0.)

    @property
    def sample_count(self):
        return len(self.values) // 2

    def observe_relative(self, wall, sim):
        if self.terminal is not None:
            raise ValueError("Timing interval already ended")
        if not finite(wall) or not finite(sim) or wall < 0 or sim < 0:
            raise ValueError("Invalid timing sample")
        if self.sample_count >= self.max_samples:
            raise ValueError("Bounded timing sample capacity exceeded")
        self.monitor.observe(wall, sim)
        self.values.extend((wall, sim))
        lag = wall - sim
        if lag > self.maximum_sample["lag_s"]:
            self.maximum_sample = {"index": self.sample_count - 1, "wall_elapsed_s": wall,
                                   "sim_elapsed_s": sim, "lag_s": lag}

    def sample(self, sim):
        self.observe_relative(self.clock() - self.origin, sim - self.sim_origin)

    def finish(self, sim, reason):
        self.sample(sim)
        self.terminal = {"wall_elapsed_s": self.values[-2], "sim_elapsed_s": self.values[-1], "reason": reason}

    @contextmanager
    def phase(self, name, sim_clock, details=None):
        previous_phase = self.active_phase
        self.active_phase = name
        start = self.clock()
        sim_start = sim_clock()
        cpu_start = self.cpu_clock()
        process_cpu_start = self.process_cpu_clock()
        try:
            yield
        finally:
            process_cpu_elapsed = self.process_cpu_clock() - process_cpu_start
            cpu_elapsed = self.cpu_clock() - cpu_start
            end = self.clock()
            self.active_phase = previous_phase
            duration = end - start
            if name not in self.phases and len(self.phases) >= 128:
                raise ValueError('Bounded phase-name capacity exceeded')
            entry = self.phases.setdefault(name, {"count": 0, "wall_total_s": 0., "cpu_total_s": 0.,
                                                  "wall_max_s": 0., "cpu_max_s": 0.,
                                                  "process_cpu_total_s": 0., "process_cpu_max_s": 0.})
            entry["count"] += 1
            entry["wall_total_s"] += duration
            entry["cpu_total_s"] += cpu_elapsed
            entry["process_cpu_total_s"] += process_cpu_elapsed
            entry["wall_max_s"] = max(entry["wall_max_s"], duration)
            entry["cpu_max_s"] = max(entry["cpu_max_s"], cpu_elapsed)
            entry["process_cpu_max_s"] = max(entry["process_cpu_max_s"], process_cpu_elapsed)
            # Preserve eight slow rows per phase as well as 64 overall, so
            # repeated adapter rows cannot hide rarer state-publication stalls.
            heap = self.slow_by_phase.setdefault(name, [])
            if duration >= .005 and (len(heap) < 8 or duration > heap[0][0] or
                                    len(self.slow) < 64 or duration > self.slow[0][0]):
                self.slow_id += 1
                record = {"phase": name, "wall_start_s": start - self.origin, "wall_end_s": end - self.origin,
                          "sim_start_s": sim_start - self.sim_origin, "sim_end_s": sim_clock() - self.sim_origin,
                          "wall_duration_s": duration, "thread_cpu_duration_s": cpu_elapsed,
                          "process_cpu_duration_s": process_cpu_elapsed}
                if details is not None:
                    record['details'] = details
                value = (duration, self.slow_id, record)
                if len(heap) < 8:
                    heapq.heappush(heap, value)
                elif duration > heap[0][0]:
                    heapq.heapreplace(heap, value)
                if len(self.slow) < 64:
                    heapq.heappush(self.slow, value)
                elif duration > self.slow[0][0]:
                    heapq.heapreplace(self.slow, value)

    def persist(self, directory, scheduling):
        if self.terminal is None:
            raise ValueError("Timing interval has no explicit terminal boundary")
        directory = Path(directory)
        samples = directory / SAMPLE_FILE
        # array.tofile streams compact data without a second full Python copy.
        if self.values.itemsize != 8:
            raise ValueError("Float64 array required")
        if sys.byteorder != "little":
            self.values.byteswap()
        try:
            with samples.open("xb") as stream:
                self.values.tofile(stream)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            if sys.byteorder != "little":
                self.values.byteswap()
        with samples.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        report = self.monitor.report()
        metadata = {"schema": SCHEMA, "sample_file": SAMPLE_FILE, "encoding": "little-endian float64 wall/sim pairs",
                    "sha256": digest, "byte_count": samples.stat().st_size, "sample_count": self.sample_count,
                    "maximum_sample_capacity": self.max_samples, "loop_origin": self.loop_origin,
                    "terminal": self.terminal, "monitor_source": self.monitor_source, "report": report,
                    "maximum_sample": self.maximum_sample, "phases": self.phases,
                    "slow_phases": [row[2] for row in sorted(self.slow, reverse=True)],
                    "slow_phases_by_name": {name: [row[2] for row in sorted(heap, reverse=True)]
                                            for name, heap in sorted(self.slow_by_phase.items())},
                    "phase_accounting": "Nested durations are inclusive and overlap; do not sum parent and child phases. Bounded top rows are selected diagnostics, not a continuous CPU/scheduler trace.",
                    "scheduling": scheduling,
                    "scope": "Prospective full loop interval. Initialization precedes origin; final sample precedes cancellation and cleanup. Samples at every loop entrance and after host work, including storage census. Full-second boundaries use the unchanged frozen monitor; trailing partial window retained. Phase CPU/wall deltas do not identify which external process or I/O operation caused a wait."}
        if self.garbage_collection is not None:
            metadata['garbage_collection'] = self.garbage_collection
        if self.host_memory is not None:
            metadata['host_memory'] = self.host_memory
        raw = (json.dumps(metadata, indent=2, allow_nan=False) + "\n").encode()
        with (directory / METADATA_FILE).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        return {"schema": SCHEMA, "metadata_file": METADATA_FILE, "metadata_sha256": hashlib.sha256(raw).hexdigest(),
                "sample_file": SAMPLE_FILE, "sample_sha256": digest, "sample_count": self.sample_count,
                "loop_origin": self.loop_origin, "scheduling": scheduling,
                "passed": report["actual_host_timing_pass"] and scheduling.get("applied") is True and scheduling.get("restored") is True}


def verify_timing(directory):
    """Diagnostic replay; admitted assessment implements its independent reader."""
    directory = Path(directory)
    metadata = json.loads((directory / METADATA_FILE).read_text(encoding="utf-8"))
    if metadata.get("schema") != SCHEMA or metadata.get("sample_file") != SAMPLE_FILE:
        raise ValueError("Unexpected timing schema or sample file")
    raw = (directory / SAMPLE_FILE).read_bytes()
    if len(raw) != metadata["byte_count"] or len(raw) != metadata["sample_count"] * 16 or len(raw) < 32:
        raise ValueError("Timing sample length mismatch")
    if hashlib.sha256(raw).hexdigest() != metadata["sha256"]:
        raise ValueError("Timing sample hash mismatch")
    monitor_type, identity = load_monitor()
    if identity != metadata["monitor_source"]:
        raise ValueError("Frozen monitor identity mismatch")
    monitor = monitor_type()
    previous = None
    for i, (wall, sim) in enumerate(struct.iter_unpack("<dd", raw)):
        if not finite(wall) or not finite(sim) or wall < 0 or sim < 0:
            raise ValueError("Invalid retained clock sample")
        if i == 0 and (wall, sim) != (0., 0.):
            raise ValueError("Retained timing must begin at common origin")
        monitor.observe(wall, sim)
        previous = (wall, sim)
    terminal = metadata["terminal"]
    if previous != (terminal["wall_elapsed_s"], terminal["sim_elapsed_s"]):
        raise ValueError("Retained terminal clock mismatch")
    report = monitor.report()
    if report != metadata["report"]:
        raise ValueError("Retained timing report differs from replay")
    return report
