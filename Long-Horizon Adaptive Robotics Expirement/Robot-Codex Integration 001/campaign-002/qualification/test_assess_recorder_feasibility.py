"""Short temporary-fixture checks; never run the feasibility benchmark."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import struct
import tempfile
import unittest
from unittest import mock
import zlib

import assess_recorder_feasibility as assessor


def write_json(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')


class AuthenticationTests(unittest.TestCase):
    def test_failed_or_noninteger_queue_never_reads_outcomes(self):
        for state, code in [('failed', 0), ('running', 0), ('succeeded', False), ('succeeded', '0'), ('succeeded', 1)]:
            with self.subTest(state=state, code=code), mock.patch.object(assessor.base, 'read_json', return_value=dict(state=state, exit_status=code)) as read:
                with self.assertRaisesRegex(ValueError, 'queue succeeded'):
                    assessor.evaluate(Path('manifest'), Path('absent-evidence'), Path('queue'), Path('snapshot'))
                self.assertEqual(read.call_args_list, [mock.call(Path('queue'))])

    def job(self, manifest, evidence):
        return dict(id='fixture-job', state='succeeded', exit_status=0,
            argv=[str(assessor.REPO / 'venv/Scripts/python.exe'), '-X', 'utf8', '-B',
                  str(assessor.PROTOTYPE / 'benchmark.py'), 'run', '--manifest', str(manifest.resolve()), '--output', str(evidence.resolve())],
            cwd=str(assessor.REPO), resolved_executable=str(assessor.REPO / 'venv/Scripts/python.exe'),
            started_at='2026-09-27T00:00:00Z', ended_at='2026-09-27T00:05:00Z')

    def test_successful_shell_wrapper_is_rejected_before_snapshot_or_outcomes(self):
        job = self.job(Path('manifest'), Path('evidence')); job['argv'] = ['powershell', '-Command', 'benchmark']
        with mock.patch.object(assessor.base, 'read_json', return_value=job) as read:
            with self.assertRaisesRegex(ValueError, 'direct feasibility'):
                assessor.evaluate(Path('manifest'), Path('evidence'), Path('queue'), Path('snapshot'))
            self.assertEqual(read.call_count, 1)

    def test_source_archive_failure_precedes_manifest_and_outcomes(self):
        with mock.patch.object(assessor.base, 'read_json', side_effect=[self.job(Path('manifest'), Path('evidence')), {}]) as read, \
             mock.patch.object(assessor.base, 'source_integrity', return_value=['changed archive']):
            with self.assertRaisesRegex(ValueError, 'source archive mismatch'):
                assessor.evaluate(Path('manifest'), Path('evidence'), Path('queue'), Path('snapshot'))
            self.assertEqual(read.call_count, 2)

    def test_current_source_failure_precedes_manifest_and_outcomes(self):
        paths = assessor.SOURCE_PATHS + [Path(assessor.__file__).resolve(), Path(assessor.base.__file__).resolve()]
        frozen = {'sources': {path.relative_to(assessor.REPO).as_posix(): {'sha256': '0'*64} for path in paths}}
        with mock.patch.object(assessor.base, 'read_json', side_effect=[self.job(Path('manifest'), Path('evidence')), frozen]) as read, \
             mock.patch.object(assessor.base, 'source_integrity', return_value=[]):
            with self.assertRaisesRegex(ValueError, 'Current frozen source differs'):
                assessor.evaluate(Path('manifest'), Path('evidence'), Path('queue'), Path('snapshot'))
            self.assertEqual(read.call_count, 2)

    def test_fixed_order_and_bool_wall_cap_cannot_change_declaration(self):
        value = dict(schema='rci-recorder-journal-feasibility-1', seed=173, mode_order=assessor.ORDER,
            frames_per_round=600, motion_rows_per_frame=10, width=64, height=48, wall_cap_s=300,
            space_policy=assessor.SPACE_POLICY, run_id='fixture', framework_revision='fixture-revision')
        self.assertEqual(assessor.validate_manifest(value), value)
        for key, replacement in [('mode_order', list(reversed(assessor.ORDER))[1:]), ('wall_cap_s', True), ('seed', 174)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                assessor.validate_manifest(dict(value, **{key: replacement}))


class OperationReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def fixture(self, rows):
        raw = b''.join(struct.pack('<6d', *row) for row in rows)
        (self.root / 'operations.bin').write_bytes(raw)
        summaries, durations = {}, {}
        names = {v: k for k, v in assessor.CODES.items()}
        for code, start, end, thread, process, success in rows:
            if code not in names:
                continue
            name, elapsed = names[code], end-start
            durations.setdefault(name, []).append(elapsed)
            summary = summaries.setdefault(name, dict(count=0, failures=0, wall_total_s=0., wall_max_s=0.))
            summary['count'] += 1; summary['failures'] += int(success == 0)
            summary['wall_total_s'] += elapsed; summary['wall_max_s'] = max(summary['wall_max_s'], elapsed)
        binding = dict(schema='rci-recorder-operation-timing-1', sample_file='operations.bin', fields=assessor.FIELDS,
            operation_codes=assessor.CODES, encoding='little-endian float64 rows', capacity=assessor.CAPACITY,
            count=len(rows), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), summaries=summaries)
        latency = {name: assessor.distribution(durations.get(name, [])) for name in ('image', 'commit', 'execute')}
        return binding, latency

    def test_nested_start_regression_and_quantized_cpu_are_valid(self):
        binding, latency = self.fixture([(1, .1, .11, .015625, .015625, 1), (7, 0, .12, .015625, .03125, 1)])
        replay = assessor.verify_operations(self.root, binding, latency)
        self.assertEqual(replay['sample_count'], 2)
        self.assertEqual(replay['latency']['execute']['count'], 1)

    def test_hash_and_count_corruption_are_rejected(self):
        binding, latency = self.fixture([(4, 0, .1, 0, 0, 1)])
        for key, wrong in [('sha256', '0'*64), ('count', 2), ('bytes', 47), ('capacity', True)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                assessor.verify_operations(self.root, dict(binding, **{key: wrong}), latency)

    def test_invalid_codes_nonfinite_or_completion_regression_are_rejected(self):
        examples = [[(99, 0, 1, 0, 0, 1)], [(1, 0, 1, float('nan'), 0, 1)],
            [(1, .2, .3, 0, 0, 1), (7, 0, .1, 0, 0, 1)], [(1, 0, .1, -.01, 0, 1)], [(1, 0, .1, 0, 0, .5)]]
        for rows in examples:
            with self.subTest(rows=rows):
                binding, latency = self.fixture(rows)
                with self.assertRaises(ValueError):
                    assessor.verify_operations(self.root, binding, latency)

    def test_fabricated_distribution_or_summary_is_rejected(self):
        binding, latency = self.fixture([(4, 0, .1, 0, 0, 1), (4, .2, .5, 0, 0, 1)])
        changed = copy.deepcopy(latency); changed['commit']['p95_s'] = .5
        with self.assertRaisesRegex(ValueError, 'Latency distribution'):
            assessor.verify_operations(self.root, binding, changed)
        changed = copy.deepcopy(binding); changed['summaries']['commit']['failures'] = 1
        with self.assertRaisesRegex(ValueError, 'summaries'):
            assessor.verify_operations(self.root, changed, latency)

    def test_failed_operation_remains_replayable_for_diagnosis(self):
        binding, latency = self.fixture([(1, 0, .01, 0, 0, 0)])
        self.assertEqual(assessor.verify_operations(self.root, binding, latency)['summaries']['execute']['failures'], 1)

    def test_failed_round_preserves_verified_timing_without_fabricating_container_pass(self):
        binding, latency = self.fixture([(1, 0, .01, 0, 0, 0)])
        round_root = self.root / 'round-00-delete'; round_root.mkdir()
        shutil.move(str(self.root / 'operations.bin'), round_root / 'operations.bin')
        row = dict(ordinal=0, mode='DELETE', status='failed', passed=False,
            error={'message': 'injected native failure'}, operation_timing=binding, latency=latency, retained_files={})
        write_json(round_root / 'result.json', row)
        row['result_binding'] = dict(path='round-00-delete/result.json', sha256=assessor.base.hash_file(round_root / 'result.json'))
        with mock.patch.object(assessor, 'reader_fingerprint', side_effect=AssertionError('Incomplete container must not be read')):
            report = assessor.verify_round(self.root, row, 0, 'DELETE', None, sqlite3.sqlite_version)
        self.assertFalse(report['passed'])
        self.assertEqual(report['timing']['summaries']['execute']['failures'], 1)
        self.assertNotIn('reader', report)


class ContainerAndRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = assessor.original_recorder()

    def test_original_reader_replay_normalizes_json_and_detects_container_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'recording'
            recorder = self.original.Recorder(path, run_id='fixture')
            recorder.document('stable', {'value': -0.0}); recorder.close()
            replay = assessor.reader_fingerprint(path, self.original)
            self.assertEqual(json.loads(json.dumps(replay)), replay)
            self.assertEqual(replay['counts']['documents'], 1)
            container = path / 'evidence.sqlite.gz'
            container.write_bytes(container.read_bytes() + b'corruption')
            with self.assertRaises(Exception):
                assessor.reader_fingerprint(path, self.original)

    def test_unrun_round_is_failed_without_opening_any_outcome_file(self):
        row = dict(ordinal=0, mode='DELETE', status='unrun_wall_cap', passed=False)
        with mock.patch.object(assessor.base, 'read_json', side_effect=AssertionError('Unexpected read')):
            report = assessor.verify_round(Path('absent'), row, 0, 'DELETE', self.original, sqlite3.sqlite_version)
        self.assertFalse(report['passed']); self.assertIsNone(report['timing'])

    def test_recovered_copy_read_is_nonmutating_and_changed_source_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory); root = evidence / 'crash-delete-after_commit'
            source = root / 'interrupted'; recovered = root / 'recovery-copy'; source.mkdir(parents=True)
            db = sqlite3.connect(source / 'evidence.sqlite')
            stable = self.original.pack({'committed': True, 'value': 'before interruption'})
            pending = self.original.pack({'pending': True,
                'data': ''.join(hashlib.sha256(str(index).encode()).hexdigest() for index in range(4000))})
            pending_key = hashlib.sha256(pending).digest()
            db.execute('CREATE TABLE documents(name TEXT,payload BLOB)')
            db.execute('CREATE TABLE objects(hash BLOB,payload BLOB)')
            db.execute('INSERT INTO objects VALUES(?,?)', (pending_key, zlib.compress(pending)))
            db.executemany('INSERT INTO documents VALUES(?,?)', [('stable', stable), ('pending', b'R'+pending_key)])
            db.commit(); db.close(); shutil.copytree(source, recovered)
            readback = dict(stage='crash_fixture', journal_mode='DELETE', synchronous=2, in_transaction=False,
                sqlite_version=sqlite3.sqlite_version, database_list=[[0, 'main', str(source / 'evidence.sqlite')]], page_size=4096)
            ready = dict(mode='DELETE', stage='after_commit', cache_pages=8, stable_payload_sha256=hashlib.sha256(stable).hexdigest(),
                readback=readback, journal_present=False, journal_bytes=0, first_journal_header_hex=None, in_transaction=False)
            write_json(root / 'crash-ready.json', ready)
            row = dict(mode='DELETE', stage='after_commit', passed=True, expected_child_exit=23, actual_child_exit=23,
                argv=[str(assessor.REPO / 'venv/Scripts/python.exe'), '-X', 'utf8', '-B', str(assessor.PROTOTYPE / 'benchmark.py'),
                      'crash-child', '--directory', str(source), '--mode', 'DELETE', '--stage', 'after_commit'],
                started_unix_s=assessor.stamp('2026-09-27T00:00:01Z'), ended_unix_s=assessor.stamp('2026-09-27T00:00:02Z'),
                wall_s=1., ready=ready, source_files=assessor.inventory(source), recovered_files=assessor.inventory(recovered),
                source_pair_preserved=True, committed_document_names=['pending', 'stable'])
            job = dict(started_at='2026-09-27T00:00:00Z', ended_at='2026-09-27T00:05:00Z')
            before = assessor.inventory(evidence)
            report = assessor.verify_recovery(evidence, row, 'DELETE', 'after_commit', self.original, sqlite3.sqlite_version, job)
            self.assertTrue(report['passed'], report)
            self.assertTrue(report['exact_committed_payloads_verified'])
            self.assertEqual(before, assessor.inventory(evidence))
            db = sqlite3.connect(recovered / 'evidence.sqlite')
            wrong_pending = self.original.pack({'pending': True, 'data': 'wrong committed content'})
            wrong_key = hashlib.sha256(wrong_pending).digest()
            db.execute('UPDATE objects SET hash=?,payload=?', (wrong_key, zlib.compress(wrong_pending)))
            db.execute("UPDATE documents SET payload=? WHERE name='pending'", (b'R'+wrong_key,))
            db.commit(); db.close()
            row['recovered_files'] = assessor.inventory(recovered)
            report = assessor.verify_recovery(evidence, row, 'DELETE', 'after_commit', self.original, sqlite3.sqlite_version, job)
            self.assertFalse(report['passed']); self.assertIn('pending payload differs', report['error'])
            db = sqlite3.connect(recovered / 'evidence.sqlite')
            db.execute('UPDATE objects SET payload=?', (zlib.compress(b'wrong object under existing hash'),))
            db.commit(); db.close()
            row['recovered_files'] = assessor.inventory(recovered)
            report = assessor.verify_recovery(evidence, row, 'DELETE', 'after_commit', self.original, sqlite3.sqlite_version, job)
            self.assertFalse(report['passed']); self.assertIn('Object hash mismatch', report['error'])
            (source / 'evidence.sqlite').write_bytes((source / 'evidence.sqlite').read_bytes() + b'altered')
            with mock.patch.object(assessor.sqlite3, 'connect', side_effect=AssertionError('Should stop before opening copy')):
                report = assessor.verify_recovery(evidence, row, 'DELETE', 'after_commit', self.original, sqlite3.sqlite_version, job)
            self.assertFalse(report['passed']); self.assertIn('files differ', report['error'])


if __name__ == '__main__':
    unittest.main()
