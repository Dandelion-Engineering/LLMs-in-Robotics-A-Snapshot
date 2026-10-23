"""Disposable PERSIST/FULL feasibility candidate; never a production host import."""
from __future__ import annotations
from array import array
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[3]
sys.path.insert(0, str(EXPERIMENT / 'Storage Retention Implementation 001' / 'future'))
from recorder import Recorder, ImagePolicy, RecordingFailure
from runtime_adapter import FutureEvidence, MotionSink

SPACE_POLICY = dict(host_cap_bytes=536870912, native_reserve_bytes=67108864,
    database_limit_bytes=2097152, journal_limit_bytes=33554432,
    publication_limit_bytes=8388608, metadata_allowance_bytes=1048576)
POLICY = ImagePolicy(sparse_period_s=2., pre_s=.5, post_s=.5, ring_frames=20,
    ring_bytes=262144, image_quota_bytes=262144, maximum_trigger_windows=1)
CORE_QUOTA = 1048576


def hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''): digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')
        stream.flush(); os.fsync(stream.fileno())


class SpaceLimitError(RecordingFailure):
    pass


class SpaceAccount:
    """Observed boundaries, plus a declared reserve; no transient hard-cap claim."""
    def __init__(self, directory, policy):
        if policy != SPACE_POLICY:
            raise ValueError('Unexpected predeclared space policy')
        self.path, self.policy = Path(directory), dict(policy)
        components = sum(policy[key] for key in ('database_limit_bytes', 'journal_limit_bytes',
                         'publication_limit_bytes', 'metadata_allowance_bytes'))
        if not components <= policy['native_reserve_bytes'] <= policy['host_cap_bytes']:
            raise ValueError('Declared reserve does not cover component allowances')
        self.count = 0; self.maxima = dict(database=0, journal=0, publication=0, metadata=0, total=0)
        self.largest = {}; self.last = None; self.errors = []

    def observe(self, boundary):
        files = {p.name: p.stat().st_size for p in self.path.iterdir() if p.is_file()}
        allowed = {'evidence.sqlite', 'evidence.sqlite-journal', 'evidence.sqlite.gz',
                   'evidence.sqlite.gz.partial', 'container-manifest.json',
                   'container-manifest.json.partial', 'RECORDING_FAILED.json'}
        groups = dict(database=files.get('evidence.sqlite', 0), journal=files.get('evidence.sqlite-journal', 0),
            publication=sum(files.get(name, 0) for name in ('evidence.sqlite.gz', 'evidence.sqlite.gz.partial',
                            'container-manifest.json', 'container-manifest.json.partial')),
            metadata=files.get('RECORDING_FAILED.json', 0), total=sum(files.values()))
        row = dict(boundary=boundary, files=files, **groups)
        self.count += 1; self.last = row
        for key, amount in groups.items():
            if amount > self.maxima[key]: self.maxima[key] = amount; self.largest[key] = row
        problems = []
        if files.keys() - allowed: problems.append('Unexpected sidecar or file')
        for category, key in [('database', 'database_limit_bytes'), ('journal', 'journal_limit_bytes'),
                              ('publication', 'publication_limit_bytes'), ('metadata', 'metadata_allowance_bytes'),
                              ('total', 'native_reserve_bytes')]:
            if groups[category] > self.policy[key]: problems.append(category + ' observed limit exceeded')
        if problems:
            self.errors.append(dict(boundary=boundary, problems=problems))
            raise SpaceLimitError('; '.join(problems))
        return row

    def receipt(self):
        return dict(policy=self.policy, observation_count=self.count, observed_maxima=self.maxima,
            largest_observations=self.largest, final_observation=self.last, errors=self.errors,
            coverage='Pre/post SQL operations, mode boundaries, SQLite close and completed finalization. '
                     'Declared allowance includes DB+journal and overlapping publication files. Within-call '
                     'transient peaks are not directly observed or enforced by an OS quota; journal_size_limit '
                     'is not used as a peak guarantee. This prototype alone does not qualify production reserve.')


class OperationLog:
    FIELDS = ['operation_code', 'wall_start_s', 'wall_end_s', 'thread_cpu_s', 'process_cpu_s', 'success']
    CODES = {'execute': 1, 'executemany': 2, 'executescript': 3, 'commit': 4, 'rollback': 5, 'close': 6,
             'image': 7, 'motion_write': 8, 'trigger': 9, 'event': 10, 'document': 11}

    def __init__(self, maximum=20000):
        self.origin = time.perf_counter(); self.maximum = maximum; self.values = array('d')
        self.summaries = {}; self.measured = False

    def call(self, name, function, *args, **kwargs):
        start = time.perf_counter(); cpu = time.thread_time(); process = time.process_time(); success = False
        try:
            result = function(*args, **kwargs); success = True; return result
        finally:
            end = time.perf_counter(); thread = time.thread_time() - cpu; process = time.process_time() - process
            if self.measured:
                if len(self.values) // 6 >= self.maximum: raise RuntimeError('Operation log capacity exceeded')
                self.values.extend((self.CODES[name], start-self.origin, end-self.origin, thread, process, int(success)))
                row = self.summaries.setdefault(name, dict(count=0, failures=0, wall_total_s=0., wall_max_s=0.))
                row['count'] += 1; row['failures'] += int(not success)
                row['wall_total_s'] += end-start; row['wall_max_s'] = max(row['wall_max_s'], end-start)

    def persist(self, directory):
        path = Path(directory) / 'operations.bin'
        if self.values.itemsize != 8 or sys.byteorder != 'little': raise RuntimeError('Little-endian float64 required')
        with path.open('xb') as stream: self.values.tofile(stream); stream.flush(); os.fsync(stream.fileno())
        return dict(schema='rci-recorder-operation-timing-1', sample_file=path.name, sha256=hash_file(path),
            bytes=path.stat().st_size, count=len(self.values)//6, capacity=self.maximum, fields=self.FIELDS,
            operation_codes=self.CODES, encoding='little-endian float64 rows', summaries=self.summaries,
            scope='Inclusive API/SQL timings with accounting overhead. Parent/child timings must not be summed.')


class ObservedConnection:
    def __init__(self, native, owner):
        object.__setattr__(self, '_native', native); object.__setattr__(self, '_owner', owner)

    def __getattr__(self, name): return getattr(self._native, name)
    def __setattr__(self, name, value): setattr(self._native, name, value)

    def invoke(self, name, *args, **kwargs):
        if self._owner.failure_exception is not None:
            raise self._owner.failure_exception
        try:
            self._owner.space.observe('before_' + name)
            value = self._owner.log.call(name, getattr(self._native, name), *args, **kwargs)
            self._owner.space.observe('after_' + name)
        except Exception as error:
            self._owner.latch(error, name)
            try: self._owner.space.observe('failed_' + name)
            except Exception: pass  # Preserve the original database error and retained matching files.
            raise
        if name == 'close' and self._owner.finalizing:
            remaining = [name for name in ('evidence.sqlite-journal', 'evidence.sqlite-wal', 'evidence.sqlite-shm')
                         if (self._owner.path / name).exists()]
            if remaining:
                error = RecordingFailure('SQLite did not retire sidecars before finalization: '+str(remaining))
                self._owner.latch(error, 'close'); raise error
            self._owner.finalization_steps.append('sqlite_closed_no_sidecars_before_original_compression')
        return value

    def execute(self, *args, **kwargs): return self.invoke('execute', *args, **kwargs)
    def executemany(self, *args, **kwargs): return self.invoke('executemany', *args, **kwargs)
    def executescript(self, *args, **kwargs): return self.invoke('executescript', *args, **kwargs)
    def commit(self, *args, **kwargs): return self.invoke('commit', *args, **kwargs)
    def rollback(self, *args, **kwargs): return self.invoke('rollback', *args, **kwargs)
    def close(self, *args, **kwargs): return self.invoke('close', *args, **kwargs)


class CandidateRecorder(Recorder):
    def __init__(self, *args, mode, space_policy=SPACE_POLICY, operation_log=None, **kwargs):
        if mode not in ('DELETE', 'PERSIST'): raise ValueError('Unsupported candidate mode')
        self.mode = mode; self.log = operation_log or OperationLog(); self.finalizing = False
        self.readbacks = []; self.finalization_steps = []
        self.first_failure = None; self.failure_exception = None
        self.encoded_digest = hashlib.sha256(); self.encoded_count = 0
        super().__init__(*args, **kwargs)
        self.space = SpaceAccount(self.path, space_policy)
        self.native = self.db
        returned = self.native.execute('PRAGMA journal_mode=' + mode).fetchone()[0]
        if returned.upper() != mode: raise RecordingFailure('SQLite refused candidate journal mode')
        self.readback('before_work', mode)
        self.db = ObservedConnection(self.native, self)
        self.space.observe('configured')

    def image(self, frame_id, capture_time_s, rgb, depth):
        if self.failure_exception is not None:
            raise self.failure_exception
        # Hash every encoded pair, including ring-only images, identically in
        # both conditions; the original image method still owns all mutations.
        ident = frame_id.encode('utf-8')
        for data in (ident, struct.pack('<d', capture_time_s), bytes(rgb), bytes(depth)):
            self.encoded_digest.update(struct.pack('<Q', len(data))); self.encoded_digest.update(data)
        self.encoded_count += 1
        try:
            return super().image(frame_id, capture_time_s, rgb, depth)
        except Exception as error:
            self.latch(error, 'image'); raise

    def latch(self, error, boundary):
        if self.first_failure is None:
            self.first_failure = dict(boundary=boundary, type=type(error).__name__, message=str(error))
            self.failure_exception = error

    def readback(self, stage, expected):
        row = dict(stage=stage, journal_mode=self.native.execute('PRAGMA journal_mode').fetchone()[0].upper(),
            synchronous=self.native.execute('PRAGMA synchronous').fetchone()[0],
            database_list=self.native.execute('PRAGMA database_list').fetchall(),
            page_size=self.native.execute('PRAGMA page_size').fetchone()[0],
            sqlite_version=self.native.execute('SELECT sqlite_version()').fetchone()[0],
            in_transaction=self.native.in_transaction)
        self.readbacks.append(row)
        if row['journal_mode'] != expected or row['synchronous'] != 2 or row['in_transaction']:
            raise RecordingFailure('Candidate mode/FULL/transaction readback differs')
        if len(row['database_list']) != 1 or row['database_list'][0][1] != 'main':
            raise RecordingFailure('Only one main database is permitted')
        return row

    def close(self):
        if self.failure_exception is not None:
            raise self.failure_exception  # Failed work can never acquire a complete container later.
        try:
            return self._finalize()
        except Exception as error:
            self.latch(error, 'finalization'); raise

    def _finalize(self):
        if self.stopped:
            return super().close()
        # Flush under the declared mode; never discard pending motion to improve finalization.
        self.flush_motion()
        self.readback('before_finalization', self.mode)
        self.space.observe('before_sqlite_delete_transition')
        returned = self.native.execute('PRAGMA journal_mode=DELETE').fetchone()[0]
        if returned.upper() != 'DELETE': raise RecordingFailure('SQLite refused DELETE finalization mode')
        self.readback('delete_transition', 'DELETE')
        self.finalization_steps.append('sqlite_delete_mode_selected')
        self.finalizing = True
        # The original final-state UPDATE/commit is a DELETE-mode transaction.
        # Its original close then invokes the proxy's no-sidecar check BEFORE
        # hashing/compression. Never delete or alter a journal manually.
        super().close()
        self.finalization_steps.append('original_exact_byte_gzip_manifest_publication_completed')
        self.space.observe('after_original_finalization')

    def receipt(self):
        return dict(schema='rci-recorder-journal-candidate-1', mode=self.mode, readbacks=self.readbacks,
            first_failure=self.first_failure,
            encoded_pair_count=self.encoded_count, encoded_pairs_sha256=self.encoded_digest.hexdigest(),
            finalization_steps=self.finalization_steps, space=self.space.receipt(),
            source_contract='One original sqlite3 connection; original Recorder mutations inherited; '
                            'original FutureEvidence owner lock; FULL and all transaction boundaries retained.')


class CandidateEvidence(FutureEvidence):
    def __init__(self, directory, run_id, *, mode, space_policy=SPACE_POLICY, operation_log=None,
                 policy=ImagePolicy(), core_quota_bytes=200_000_000, representative=False,
                 clock=time.perf_counter, physics_dt=.002, allocation=None):
        if allocation is not None:
            if allocation['run_id'] != run_id: raise ValueError('Campaign allocation identifies another run')
            core_quota_bytes = allocation['core_quota_bytes']
            policy = replace(policy, image_quota_bytes=allocation['image_quota_bytes'],
                             maximum_trigger_windows=allocation['maximum_trigger_windows'])
        self.store = CandidateRecorder(directory, run_id=run_id, policy=policy, core_quota_bytes=core_quota_bytes,
            representative=representative, mode=mode, space_policy=space_policy, operation_log=operation_log)
        self.path=Path(directory); self.run_id=run_id; self.clock=clock; self.start=clock()
        self.physics_dt=physics_dt; self.sequence=0; self.lock=threading.RLock()
        self.motion=MotionSink(self.store,self.lock)
