"""Independent policy/ledger rejection tests; no native policy mutation."""
import copy
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

import resource_integrity as r


def resource_fixture(root, origin=200., terminal=2.):
    root = Path(root)
    mib = 1024**2
    config = {'enabled': True, 'thresholds': [700, 10, 10], 'debug_flags': 0, 'freeze_count': 0}
    state = {**config, 'counts': [0, 0, 0], 'callback_count': 0,
             'statistics': [{'collections': 0, 'collected': 0, 'uncollectable': 0} for _ in range(3)]}
    policy = {'name': 'bounded-automatic-cyclic-gc-deferral-1', 'disable_start_wall_elapsed_s': -.02,
              'disable_end_wall_elapsed_s': -.01, 'restore_start_wall_elapsed_s': terminal + .01,
              'restore_end_wall_elapsed_s': terminal + .02, 'restoration_attempted': True,
              'configuration_restored': True, 'verification_count': 10, 'full_configuration_verification_count': 3,
              'unexpected_collection_count': 0, 'error': None, 'restore_errors': [], 'restored_configuration': config}
    gc = {'schema': 'rci-gc-diagnostics-2', 'sample_file': 'gc-collections.bin',
          'encoding': 'little-endian float64 rows', 'fields': r.GC_FIELDS,
          'sha256': r.digest(b''), 'byte_count': 0, 'collection_count': 0, 'maximum_collection_capacity': 8192,
          'phase_names': {'0': None, '1': 'cleanup'}, 'host_native_thread_id': 7,
          'attached_wall_elapsed_s': -.03, 'detached_wall_elapsed_s': terminal + .2,
          'initial': copy.deepcopy(state), 'final': copy.deepcopy(state), 'policy': policy,
          'overflow': 0, 'error': None, 'passed': True, 'policy_unchanged': False,
          'measured_terminal_wall_elapsed_s': terminal, 'measured_interval_collection_count': 0,
          'collector_policy_mutations': [
              {'operation': 'disable_automatic_gc', 'wall_elapsed_s': -.015},
              {'operation': 'restore_thresholds', 'wall_elapsed_s': terminal + .011},
              {'operation': 'restore_debug_flags', 'wall_elapsed_s': terminal + .012},
              {'operation': 'restore_enabled_state', 'wall_elapsed_s': terminal + .013}]}
    (root / 'gc-collections.bin').write_bytes(b'')
    readback = {'process_is_member': True, 'limit_flags': 256, 'process_memory_limit_bytes': r.HARD,
                'returned_structure_bytes': 144, 'expected_structure_bytes': 144,
                'assigned_process_count': 1, 'listed_process_count': 1, 'process_ids': [1234],
                'peak_process_memory_used_bytes': 300 * mib, 'peak_job_memory_used_bytes': 300 * mib}
    counters = {'private_commit_bytes': 128 * mib, 'working_set_bytes': 64 * mib,
                'peak_private_commit_bytes': 300 * mib, 'peak_working_set_bytes': 100 * mib}
    job = {'schema': 'rci-host-memory-1', 'platform': 'win32', 'pid': 1234,
           'hard_process_commit_limit_bytes': r.HARD, 'applied': True, 'final_readback_verified': True,
           'handle_closed': True, 'membership_detached': False,
           'initial_readback': copy.deepcopy(readback), 'final_readback': copy.deepcopy(readback),
           'post_cleanup_memory': {**counters, 'read_start_qpc_s': origin + terminal + .1,
                                   'read_end_qpc_s': origin + terminal + .11}}
    ends = [.001]
    while ends[-1] + .1 < terminal - .001:
        ends.append(ends[-1] + .1)
    ends.append(terminal - .001)
    rows = [(end - .0001, end, 256 * mib, 64 * mib, 300 * mib, 100 * mib,
             1 if index == 0 else 2 if index == len(ends) - 1 else 0) for index, end in enumerate(ends)]
    raw = b''.join(struct.pack('<7d', *row) for row in rows)
    (root / 'memory-samples.bin').write_bytes(raw)
    memory = {'schema': 'rci-host-memory-1', 'sample_file': 'memory-samples.bin', 'sha256': r.digest(raw),
              'byte_count': len(raw), 'sample_count': len(rows), 'maximum_sample_capacity': 12000,
              'encoding': 'little-endian float64 rows', 'fields': r.MEMORY_FIELDS,
              'kind_codes': {'periodic': 0, 'origin': 1, 'terminal': 2},
              'sampling_interval_s': .1, 'maximum_permitted_sample_gap_s': .2,
              'baseline_private_commit_limit_bytes': r.BASELINE, 'soft_absolute_limit_bytes': r.SOFT,
              'soft_growth_limit_bytes': r.GROWTH, 'soft_limit_bytes': 128 * mib + r.GROWTH,
              'baseline': {**counters, 'read_start_qpc_s': origin - .1, 'read_end_qpc_s': origin - .09},
              'loop_origin_qpc_s': origin, 'terminal_wall_elapsed_s': terminal,
              'native_job': job, 'complete': True, 'error': None, 'passed': True}
    sources = {}
    for path in [r.CAMPAIGN / 'harness' / name for name in ('gc_diagnostics.py', 'memory_guard.py', 'timing.py', 'run_host.py')] + [Path(r.__file__)]:
        raw = path.read_bytes()
        sources[path.relative_to(r.REPO).as_posix()] = {'sha256': r.digest(raw), 'bytes': len(raw)}
    return {'garbage_collection': gc, 'host_memory': memory}, {'native_memory_job': job}, sources


class ResourceIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.metadata, self.host, sources = resource_fixture(self.root)
        self.metadata.update(terminal={'wall_elapsed_s': 2.}, loop_origin={'monotonic_s': 200.})
        self.frozen = {'sources': sources}

    def verify(self):
        return r.verify_resources(self.root, self.metadata, self.host, self.frozen)

    def replace_rows(self, key, rows, width):
        binding = self.metadata[key]
        raw = b''.join(struct.pack('<' + 'd' * width, *row) for row in rows)
        (self.root / binding['sample_file']).write_bytes(raw)
        binding.update(sha256=r.digest(raw), byte_count=len(raw))
        binding['sample_count' if key == 'host_memory' else 'collection_count'] = len(rows)

    def test_complete_bounded_resource_evidence_passes(self):
        result = self.verify()
        self.assertTrue(result['resource_integrity_pass'])
        self.assertEqual(result['garbage_collection']['measured_interval_collection_count'], 0)
        self.assertLessEqual(result['host_memory']['maximum_sample_gap_s'], .2)

    def test_missing_or_diagnostic_only_gc_is_not_a_qualified_policy(self):
        for value in (None, {}, {**self.metadata['garbage_collection'], 'schema': 'rci-gc-diagnostics-1'}):
            with self.subTest(value=value):
                self.metadata['garbage_collection'] = value
                with self.assertRaisesRegex(ValueError, 'Resource ledger schema'):
                    self.verify()

    def test_rehashed_collection_inside_measured_interval_is_rejected(self):
        self.replace_rows('garbage_collection', [(.5, .6, .01, .01, 2, 3, 0, 7, 1, 0, .5, .5)], 12)
        with self.assertRaisesRegex(ValueError, 'overlaps the measured physics'):
            self.verify()

    def test_deferred_collection_after_terminal_is_retained_and_allowed(self):
        self.replace_rows('garbage_collection', [(2.04, 2.06, .01, .01, 2, 3, 0, 7, 1, 1, 2, 2)], 12)
        self.metadata['garbage_collection']['final']['statistics'][2].update(collections=1, collected=3)
        self.assertEqual(self.verify()['garbage_collection']['collection_count'], 1)

    def test_collector_restore_and_mutation_boundaries_are_mandatory(self):
        original = copy.deepcopy(self.metadata['garbage_collection'])
        for change in ({'restore_start_wall_elapsed_s': 1.99}, {'disable_end_wall_elapsed_s': .01},
                       {'configuration_restored': False}, {'restore_errors': ['failure']}):
            with self.subTest(change=change):
                self.metadata['garbage_collection'] = copy.deepcopy(original)
                self.metadata['garbage_collection']['policy'].update(change)
                with self.assertRaises(ValueError):
                    self.verify()

    def test_changed_threshold_or_freeze_configuration_fails(self):
        for key, value in (('thresholds', [701, 10, 10]), ('freeze_count', 1), ('enabled', False)):
            with self.subTest(key=key):
                original = self.metadata['garbage_collection']['final'][key]
                self.metadata['garbage_collection']['final'][key] = value
                with self.assertRaisesRegex(ValueError, 'restored exactly'):
                    self.verify()
                self.metadata['garbage_collection']['final'][key] = original

    def test_memory_hash_corruption_is_rejected(self):
        path = self.root / 'memory-samples.bin'
        raw = bytearray(path.read_bytes()); raw[-1] ^= 1; path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'ledger hash'):
            self.verify()

    def test_memory_rehashed_soft_limit_crossing_is_rejected(self):
        rows = list(struct.iter_unpack('<7d', (self.root / 'memory-samples.bin').read_bytes()))
        row = list(rows[2]); row[2] = self.metadata['host_memory']['soft_limit_bytes']; row[4] = row[2]
        rows[2] = row
        self.replace_rows('host_memory', rows, 7)
        with self.assertRaisesRegex(ValueError, 'reached a ceiling'):
            self.verify()

    def test_missing_origin_terminal_or_sampling_gap_cannot_pass(self):
        original = list(struct.iter_unpack('<7d', (self.root / 'memory-samples.bin').read_bytes()))
        for rows in (original[1:], original[:-1], original[:1] + original[4:]):
            with self.subTest(rows=len(rows)):
                self.replace_rows('host_memory', rows, 7)
                with self.assertRaises(ValueError):
                    self.verify()

    def test_native_job_extra_process_or_unclosed_handle_is_rejected(self):
        original = copy.deepcopy(self.metadata['host_memory']['native_job'])
        for mode in ('another-process', 'unclosed', 'different-limit', 'wrong-structure-size'):
            with self.subTest(mode=mode):
                job = copy.deepcopy(original)
                if mode == 'another-process':
                    job['final_readback'].update(assigned_process_count=2, listed_process_count=2, process_ids=[1234, 5678])
                elif mode == 'unclosed':
                    job['handle_closed'] = False
                elif mode == 'different-limit':
                    job['final_readback']['process_memory_limit_bytes'] += 1
                else:
                    job['final_readback']['returned_structure_bytes'] -= 1
                self.metadata['host_memory']['native_job'] = job
                self.host['native_memory_job'] = job
                with self.assertRaisesRegex(ValueError, 'JobObject'):
                    self.verify()

    def test_resource_policy_sources_must_be_in_same_freeze(self):
        name = next(name for name in self.frozen['sources'] if name.endswith('/memory_guard.py'))
        del self.frozen['sources'][name]
        with self.assertRaisesRegex(ValueError, 'source differs from freeze'):
            self.verify()

    def test_native_receipt_cannot_disagree_with_host_result(self):
        self.host['native_memory_job'] = {}
        with self.assertRaisesRegex(ValueError, 'closure receipt differs'):
            self.verify()

    @unittest.skipUnless(sys.platform == 'win32', 'Native Windows host policy')
    def test_actual_disposable_host_writers_match_independent_resource_reader(self):
        code = '''import json,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path.cwd().parent/'assessment'))
from memory_guard import MemoryGuard
from gc_diagnostics import GcDiagnostics
from timing import TimingCapture
import resource_integrity as r
memory=MemoryGuard(1.);memory.apply();memory.admit()
observer=GcDiagnostics(lambda:None,lambda:0.);observer.attach();observer.defer()
origin=time.perf_counter();timing=TimingCapture(origin,0.,max_samples=4)
try:
    memory.start(origin);time.sleep(.02);observer.verify_deferred(full=True)
    memory.finish();timing.finish(0.,'unit_only')
finally:
    observer.restore();observer.detach();memory.close()
with tempfile.TemporaryDirectory() as directory:
    metadata={'loop_origin':{'monotonic_s':origin},'terminal':timing.terminal,
        'garbage_collection':observer.persist(directory,origin,0.,timing.terminal),
        'host_memory':memory.persist(directory,timing.terminal)}
    paths=[r.CAMPAIGN/'harness'/name for name in ('gc_diagnostics.py','memory_guard.py','timing.py','run_host.py')]+[Path(r.__file__)]
    sources={p.relative_to(r.REPO).as_posix():{'sha256':r.digest(p.read_bytes()),'bytes':p.stat().st_size} for p in paths}
    result=r.verify_resources(directory,metadata,{'native_memory_job':memory.receipt},{'sources':sources})
    print(json.dumps({key:result[key] for key in ('resource_integrity_pass','garbage_collection_pass','host_memory_pass')}))
'''
        result = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-c', code],
            cwd=r.CAMPAIGN / 'harness', capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode, 0, result.stderr)
        import json
        self.assertEqual(json.loads(result.stdout), {'resource_integrity_pass': True,
            'garbage_collection_pass': True, 'host_memory_pass': True})


if __name__ == '__main__':
    unittest.main()
