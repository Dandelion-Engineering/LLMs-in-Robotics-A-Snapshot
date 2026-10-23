"""Native commitment enforcement and bounded memory evidence; no physics/model."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from memory_guard import MemoryGuard, MemoryPolicyError, HARD_LIMIT, BASELINE_LIMIT, SOFT_GROWTH, FIELDS


class Backend:
    def __init__(self):
        self.private = 100 * 1024**2
        self.peak = self.private
        self.applied = self.closed = False
        self.fail_read = self.fail_readback = self.fail_close = False
    def readback(self):
        if self.fail_readback: raise OSError('injected readback failure')
        return {'process_is_member': True, 'limit_flags': 256, 'process_memory_limit_bytes': HARD_LIMIT,
                'peak_process_memory_used_bytes': self.peak, 'peak_job_memory_used_bytes': self.peak,
                'returned_structure_bytes': 144, 'expected_structure_bytes': 144,
                'assigned_process_count': 1, 'listed_process_count': 1, 'process_ids': [os.getpid()]}
    def apply(self): self.applied = True; return self.readback()
    def memory(self):
        if self.fail_read: raise OSError('injected memory query failure')
        self.peak = max(self.peak, self.private)
        return self.private, self.private, self.peak, self.peak
    def close(self):
        if self.fail_close: raise OSError('injected handle failure')
        self.closed = True; return True


class MemoryGuardTests(unittest.TestCase):
    def make(self, duration=10.):
        clocks = [100.]
        backend = Backend()
        guard = MemoryGuard(duration, backend=backend, clock=lambda: clocks[0])
        guard.apply(); guard.admit()
        return guard, backend, clocks

    def test_origin_periodic_terminal_and_hash_bound_native_receipts(self):
        guard, backend, clocks = self.make()
        guard.start(100.)
        clocks[0] = 100.05; self.assertFalse(guard.poll())
        clocks[0] = 100.11; self.assertTrue(guard.poll())
        clocks[0] = 100.15; guard.finish()
        clocks[0] = 101.; guard.close()
        with tempfile.TemporaryDirectory() as directory:
            binding = guard.persist(directory, {'wall_elapsed_s': .16})
            raw = (Path(directory) / binding['sample_file']).read_bytes()
            rows = list(struct.iter_unpack('<7d', raw))
            self.assertEqual([row[-1] for row in rows], [1., 0., 2.])
            self.assertEqual(len(raw), binding['sample_count'] * len(FIELDS) * 8)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), binding['sha256'])
            self.assertEqual(binding['soft_limit_bytes'], backend.private + SOFT_GROWTH)
            self.assertTrue(binding['passed'])
            self.assertTrue(binding['native_job']['final_readback_verified'])
            self.assertTrue(binding['native_job']['handle_closed'])
            self.assertFalse(binding['native_job']['membership_detached'])
            self.assertGreater(binding['native_job']['post_cleanup_memory']['read_end_qpc_s'] - 100., .16)

    def test_baseline_and_soft_equality_fail(self):
        backend = Backend(); backend.private = BASELINE_LIMIT
        guard = MemoryGuard(10., backend=backend, clock=lambda: 100.)
        guard.apply()
        with self.assertRaisesRegex(MemoryPolicyError, 'baseline'): guard.admit()
        guard.close(); self.assertTrue(backend.closed)
        guard, backend, clocks = self.make(); guard.start(100.)
        backend.private = guard.soft_limit; clocks[0] = 100.1
        with self.assertRaisesRegex(MemoryPolicyError, 'soft ceiling'): guard.sample()
        self.assertEqual(guard.count, 2)  # Breach evidence itself is retained.
        guard.close()
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(guard.persist(directory, {'wall_elapsed_s': .1})['passed'])

    def test_missing_samples_query_readback_and_handle_fail_closed(self):
        for failure in ('gap', 'query', 'readback', 'close'):
            with self.subTest(failure=failure):
                guard, backend, clocks = self.make(); guard.start(100.)
                if failure == 'gap':
                    clocks[0] = 100.21
                    with self.assertRaisesRegex(MemoryPolicyError, 'gap'): guard.sample()
                elif failure == 'query':
                    backend.fail_read = True
                    with self.assertRaisesRegex(MemoryPolicyError, 'query failed'): guard.sample()
                else:
                    clocks[0] = 100.1; guard.finish()
                    if failure == 'readback': backend.fail_readback = True
                    else: backend.fail_close = True
                guard.close()
                self.assertIsNotNone(guard.error)
                with tempfile.TemporaryDirectory() as directory:
                    self.assertFalse(guard.persist(directory, {'wall_elapsed_s': .25})['passed'])

    def test_capacity_overflow_does_not_drop_samples(self):
        guard, backend, clocks = self.make(duration=.1); guard.start(100.)
        for index in range(guard.capacity - 1):
            clocks[0] += .01; guard.sample()
        with self.assertRaisesRegex(MemoryPolicyError, 'capacity'): guard.sample()
        self.assertEqual(guard.count, guard.capacity)
        guard.close()

    @unittest.skipUnless(sys.platform == 'win32', 'Native Windows job API')
    def test_native_limit_membership_and_readback_in_disposable_child(self):
        # Assign only this disposable child to a new bounded job; the test runner
        # and shared compute worker never join it. No large allocations occur.
        code = ('import json; from memory_guard import NativeJobMemory; '
                'p=NativeJobMemory(); a=p.apply(); m=p.memory(); b=p.readback(); c=p.close(); '
                'print(json.dumps(dict(initial=a, memory=m, final=b, closed=c)))')
        result = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-c', code],
            cwd=Path(__file__).resolve().parent, capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertTrue(receipt['initial']['process_is_member'])
        self.assertTrue(receipt['final']['process_is_member'])
        self.assertEqual(receipt['initial']['process_memory_limit_bytes'], HARD_LIMIT)
        self.assertEqual(receipt['initial']['limit_flags'], 256)
        self.assertEqual(receipt['initial']['assigned_process_count'], 1)
        self.assertEqual(receipt['initial']['listed_process_count'], 1)
        self.assertEqual(len(receipt['initial']['process_ids']), 1)
        self.assertLess(receipt['memory'][0], BASELINE_LIMIT)
        self.assertTrue(receipt['closed'])

    @unittest.skipUnless(sys.platform == 'win32', 'Native Windows resource policy')
    def test_native_policy_lifecycle_and_published_evidence_in_disposable_child(self):
        code = '''import gc,json,tempfile,time
from memory_guard import MemoryGuard
from gc_diagnostics import GcDiagnostics,read_gc
from timing import TimingCapture
original=(gc.isenabled(),gc.get_threshold(),gc.get_debug())
memory=MemoryGuard(1.); memory.apply(); memory.admit()
observer=GcDiagnostics(lambda: None,lambda: 0.); observer.attach(); observer.defer()
origin=time.perf_counter(); timing=TimingCapture(origin,0.,max_samples=4)
try:
    memory.start(origin); time.sleep(.02); observer.verify_deferred(full=True)
    memory.finish(); timing.finish(0.,'unit_only')
finally:
    observer.restore(); observer.detach(); memory.close()
with tempfile.TemporaryDirectory() as directory:
    g=observer.persist(directory,origin,0.,timing.terminal)
    m=memory.persist(directory,timing.terminal)
    rows=read_gc(directory,g)
    print(json.dumps(dict(gc_passed=g['passed'],memory_passed=m['passed'],samples=m['sample_count'],
        restored=original==(gc.isenabled(),gc.get_threshold(),gc.get_debug()),collections=len(rows))))
'''
        result = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-c', code],
            cwd=Path(__file__).resolve().parent, capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertTrue(receipt['gc_passed'])
        self.assertTrue(receipt['memory_passed'])
        self.assertTrue(receipt['restored'])
        self.assertEqual(receipt['samples'], 2)


if __name__ == '__main__': unittest.main()
