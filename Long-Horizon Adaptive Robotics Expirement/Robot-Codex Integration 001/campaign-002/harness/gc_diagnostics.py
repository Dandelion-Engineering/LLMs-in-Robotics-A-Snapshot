"""Bounded collection diagnostics and explicit measured-loop cyclic GC deferral."""
from array import array
import gc
import hashlib
import math
import os
from pathlib import Path
import struct
import sys
import threading
import time

SCHEMA = 'rci-gc-diagnostics-1'
DEFERRAL_SCHEMA = 'rci-gc-diagnostics-2'
SAMPLE_FILE = 'gc-collections.bin'
FIELDS = ('wall_start_s', 'wall_end_s', 'thread_cpu_duration_s', 'process_cpu_duration_s',
          'generation', 'collected', 'uncollectable', 'collecting_native_thread_id',
          'on_host_thread', 'host_phase_code', 'sim_start_s', 'sim_end_s')
WIDTH = len(FIELDS)


class GcDiagnostics:
    def __init__(self, phase_provider, sim_clock, *, capacity=8192, api=gc,
                 clock=time.perf_counter, thread_clock=time.thread_time,
                 process_clock=time.process_time, thread_id=threading.get_native_id):
        if type(capacity) is not int or capacity < 1:
            raise ValueError('Positive bounded GC collection capacity required')
        self.api, self.clock = api, clock
        self.thread_clock, self.process_clock, self.thread_id = thread_clock, process_clock, thread_id
        self.phase_provider, self.sim_clock = phase_provider, sim_clock
        self.host_thread_id = thread_id()
        self.capacity, self.count = capacity, 0
        self.values = array('d', [0.]) * (capacity * WIDTH)
        self.phases = {None: 0}
        self.pending = None
        self.error = None
        self.overflow = 0
        self.attached = False
        self.callback = self._callback
        self.initial = self.snapshot()
        self.final = None
        self.attach_clock = self.detach_clock = None
        self.policy = None
        self.mutations = []
        self.deferring = False

    @property
    def reserved_bytes(self):
        return self.capacity * WIDTH * 8 + 16_384

    def snapshot(self):
        return {'enabled': self.api.isenabled(), 'thresholds': list(self.api.get_threshold()),
                'debug_flags': self.api.get_debug(), 'counts': list(self.api.get_count()),
                'statistics': self.api.get_stats(), 'callback_count': len(self.api.callbacks),
                'freeze_count': self.api.get_freeze_count()}

    def defer(self):
        if not self.attached or self.policy is not None:
            raise ValueError('GC observer must be attached exactly once before deferral')
        self.policy = {'name': 'bounded-automatic-cyclic-gc-deferral-1',
                       'disable_start_qpc_s': self.clock(), 'disable_end_qpc_s': None,
                       'restore_start_qpc_s': None, 'restore_end_qpc_s': None,
                       'restoration_attempted': False, 'configuration_restored': False,
                       'verification_count': 0, 'full_configuration_verification_count': 0,
                       'unexpected_collection_count': 0, 'error': None}
        self.deferring = True
        try:
            self.api.disable()
            self.mutations.append({'operation': 'disable_automatic_gc', 'qpc_s': self.clock()})
            self.policy['disable_end_qpc_s'] = self.clock()
            self.verify_deferred(full=True)
        except Exception as exc:
            self.error = self.error or 'GC deferral failed: ' + str(exc)
            raise

    def verify_deferred(self, *, full=False):
        if not self.deferring or self.api.isenabled():
            self.error = self.error or 'GC automatic collection unexpectedly enabled during deferral'
        self.policy['verification_count'] += 1
        if full:
            self.policy['full_configuration_verification_count'] += 1
            for key, current in (('thresholds', list(self.api.get_threshold())),
                                 ('debug_flags', self.api.get_debug()), ('freeze_count', self.api.get_freeze_count())):
                if current != self.initial[key]:
                    self.error = self.error or 'GC configuration changed during deferral: ' + key
        if self.error:
            raise RuntimeError(self.error)

    def restore(self):
        if self.policy is None or self.policy['restoration_attempted']:
            return self.error is None
        self.policy['restoration_attempted'] = True
        self.policy['restore_start_qpc_s'] = self.clock()
        # Check violations but independently attempt every original setting.
        try:
            self.verify_deferred(full=True)
        except Exception as exc:
            self.error = self.error or str(exc)
        self.deferring = False
        operations = [
            ('restore_thresholds', lambda: self.api.set_threshold(*self.initial['thresholds'])
                if list(self.api.get_threshold()) != self.initial['thresholds'] else None),
            ('restore_debug_flags', lambda: self.api.set_debug(self.initial['debug_flags'])
                if self.api.get_debug() != self.initial['debug_flags'] else None),
            ('restore_enabled_state', self.api.enable if self.initial['enabled'] else self.api.disable),
        ]
        restore_errors = []
        for name, operation in operations:
            try:
                operation()
                self.mutations.append({'operation': name, 'qpc_s': self.clock()})
            except Exception as exc:
                restore_errors.append(name + ': ' + str(exc))
        self.policy['restore_end_qpc_s'] = self.clock()
        try:
            current = {'enabled': self.api.isenabled(), 'thresholds': list(self.api.get_threshold()),
                       'debug_flags': self.api.get_debug(), 'freeze_count': self.api.get_freeze_count()}
            self.policy['restored_configuration'] = current
            self.policy['configuration_restored'] = not restore_errors and all(current[key] == self.initial[key] for key in current)
        except Exception as exc:
            restore_errors.append('configuration_readback: ' + str(exc))
        if restore_errors or not self.policy['configuration_restored']:
            self.error = self.error or 'Collector restoration failed: ' + str(restore_errors)
        self.policy['restore_errors'] = restore_errors
        self.policy['error'] = self.error
        return self.error is None

    def attach(self):
        if self.attached or self.final is not None:
            raise ValueError('GC observer already attached or finalized')
        self.attach_clock = self.clock()
        self.api.callbacks.append(self.callback)
        self.attached = True

    def _callback(self, phase, info):
        # CPython ignores callback exceptions. Retain errors and reject the
        # diagnostic outside the callback instead of silently losing evidence.
        try:
            if phase == 'start':
                if self.deferring:
                    self.policy['unexpected_collection_count'] += 1
                    self.error = self.error or 'Collection occurred during declared deferral'
                if self.pending is not None:
                    raise ValueError('Overlapping GC callback intervals')
                if self.count >= self.capacity:
                    self.overflow += 1
                    self.error = self.error or 'Bounded GC collection capacity exceeded'
                    return
                name = self.phase_provider()
                if name not in self.phases:
                    if len(self.phases) >= 129:
                        raise ValueError('Bounded GC phase-name capacity exceeded')
                    self.phases[name] = len(self.phases)
                self.pending = (self.clock(), self.thread_clock(), self.process_clock(),
                                info['generation'], self.thread_id(), self.phases[name], self.sim_clock())
            elif phase == 'stop':
                if self.pending is None:
                    if self.overflow:
                        return
                    raise ValueError('GC stop without start')
                end = self.clock()
                start, thread_cpu, process_cpu, generation, thread_id, phase_code, sim_start = self.pending
                if generation != info['generation'] or thread_id != self.thread_id():
                    raise ValueError('GC callback generation/thread mismatch')
                row = (start, end, self.thread_clock() - thread_cpu, self.process_clock() - process_cpu,
                       generation, info['collected'], info['uncollectable'], thread_id,
                       int(thread_id == self.host_thread_id), phase_code, sim_start, self.sim_clock())
                if not all(math.isfinite(value) for value in row) or end < start:
                    raise ValueError('Invalid GC callback clocks')
                offset = self.count * WIDTH
                for index, value in enumerate(row):
                    self.values[offset + index] = value
                self.count += 1
                self.pending = None
            else:
                raise ValueError('Unknown GC callback phase')
        except Exception as exc:
            self.error = self.error or type(exc).__name__ + ': ' + str(exc)

    def detach(self):
        if self.attached:
            self.detach_clock = self.clock()
            try:
                self.api.callbacks.remove(self.callback)
            except ValueError:
                self.error = self.error or 'GC callback removed externally'
            self.attached = False
            self.final = self.snapshot()
            if self.pending is not None:
                self.error = self.error or 'GC callback interval unfinished at detach'
            for key in ('enabled', 'thresholds', 'debug_flags', 'freeze_count'):
                if self.initial[key] != self.final[key]:
                    self.error = self.error or 'GC policy changed during observed interval: ' + key
        return self.error is None

    def persist(self, directory, origin, sim_origin, terminal=None):
        if self.attached or self.final is None:
            raise ValueError('GC observer must be detached before publication')
        if self.error and self.policy is None:
            raise ValueError('GC diagnostic evidence failed: ' + self.error)
        values = self.values[:self.count * WIDTH]
        for offset in range(0, len(values), WIDTH):
            values[offset] -= origin
            values[offset + 1] -= origin
            values[offset + 10] -= sim_origin
            values[offset + 11] -= sim_origin
        if values.itemsize != 8:
            raise ValueError('GC ledger requires float64')
        if sys.byteorder != 'little':
            values.byteswap()
        path = Path(directory) / SAMPLE_FILE
        with path.open('xb') as stream:
            values.tofile(stream)
            stream.flush()
            os.fsync(stream.fileno())
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        result = {'schema': DEFERRAL_SCHEMA if self.policy is not None else SCHEMA, 'sample_file': SAMPLE_FILE, 'sha256': digest,
                'byte_count': path.stat().st_size, 'collection_count': self.count,
                'maximum_collection_capacity': self.capacity, 'overflow': self.overflow,
                'encoding': 'little-endian float64 rows', 'fields': list(FIELDS),
                'phase_names': {str(code): name for name, code in self.phases.items()},
                'host_native_thread_id': self.host_thread_id,
                'attached_wall_elapsed_s': self.attach_clock - origin,
                'detached_wall_elapsed_s': self.detach_clock - origin,
                'initial': self.initial, 'final': self.final,
                'policy_unchanged': self.policy is None, 'collector_policy_mutations': self.mutations,
                'scope': 'Automatic GC callback intervals; QPC and simulation origins match timing-v2. Observation attaches before loop origin and detaches after its final sample, so boundary intervals may lie outside the measured loop. Host phase is correlation only when another thread collects. No collection is requested, disabled, frozen, or retuned. Callback overhead remains included in live timing.'}
        if self.policy is not None:
            policy = dict(self.policy)
            for stem in ('disable_start', 'disable_end', 'restore_start', 'restore_end'):
                value = policy.pop(stem + '_qpc_s')
                policy[stem + '_wall_elapsed_s'] = None if value is None else value - origin
            result['collector_policy_mutations'] = [{'operation': row['operation'], 'wall_elapsed_s': row['qpc_s'] - origin} for row in self.mutations]
            result['policy'] = policy
            result['error'] = self.error
            overlap = sum(self.values[offset] < origin + terminal['wall_elapsed_s'] and self.values[offset + 1] > origin
                          for offset in range(0, self.count * WIDTH, WIDTH)) if terminal else None
            result['measured_interval_collection_count'] = overlap
            result['measured_terminal_wall_elapsed_s'] = terminal['wall_elapsed_s'] if terminal else None
            result['passed'] = (self.error is None and policy['configuration_restored'] and overlap == 0
                                and policy['disable_end_wall_elapsed_s'] <= 0
                                and policy['restore_start_wall_elapsed_s'] >= terminal['wall_elapsed_s'])
            result['scope'] = ('Declared automatic cyclic-GC deferral spans only the bounded measured physics interval, with boundary setup/restoration explicitly timed. '
                'Normal reference counting, thresholds and debug flags remain unchanged. Original collector configuration is restored after the final timing sample '
                'and before cancellation/cleanup. Callbacks retain any deferred collections through cleanup; their outside-loop cost is not relabeled as physics. '
                'No explicit collection or freeze is requested. Host-phase labels for another collecting thread are temporal context only.')
        return result


def read_gc(directory, binding):
    """Verify the bound diagnostic before examining collection associations."""
    if (binding.get('schema') not in (SCHEMA, DEFERRAL_SCHEMA) or binding.get('sample_file') != SAMPLE_FILE
            or binding.get('fields') != list(FIELDS) or binding.get('overflow') != 0
            or (binding.get('schema') == SCHEMA and (binding.get('policy_unchanged') is not True or binding.get('collector_policy_mutations') != []))):
        raise ValueError('Invalid GC diagnostic binding')
    count, capacity = binding.get('collection_count'), binding.get('maximum_collection_capacity')
    if type(count) is not int or type(capacity) is not int or not 0 <= count <= capacity:
        raise ValueError('Invalid GC diagnostic capacity/count')
    for key in ('enabled', 'thresholds', 'debug_flags'):
        if binding['initial'][key] != binding['final'][key]:
            raise ValueError('GC diagnostic policy changed')
    raw = (Path(directory) / SAMPLE_FILE).read_bytes()
    if len(raw) != count * WIDTH * 8 or len(raw) != binding['byte_count']:
        raise ValueError('GC diagnostic byte count differs')
    if hashlib.sha256(raw).hexdigest() != binding['sha256']:
        raise ValueError('GC diagnostic hash differs')
    previous = None
    rows = []
    for values in struct.iter_unpack('<' + 'd' * WIDTH, raw):
        row = dict(zip(FIELDS, values))
        if not all(math.isfinite(value) for value in values):
            raise ValueError('Nonfinite GC diagnostic value')
        if values[1] < values[0] or (previous is not None and values[0] < previous):
            raise ValueError('Regressing GC diagnostic clock')
        if any(value < 0 for value in values[2:10]) or any(value != int(value) for value in values[4:10]):
            raise ValueError('Invalid GC diagnostic counters')
        if values[4] not in (0., 1., 2.) or values[8] not in (0., 1.) or str(int(values[9])) not in binding['phase_names']:
            raise ValueError('Invalid GC diagnostic generation/phase')
        if values[8] != int(values[7] == binding['host_native_thread_id']):
            raise ValueError('GC collecting-thread attribution differs')
        if values[0] < binding['attached_wall_elapsed_s'] or values[1] > binding['detached_wall_elapsed_s']:
            raise ValueError('GC collection outside observer boundary')
        row['host_phase'] = binding['phase_names'][str(int(values[9]))]
        previous = values[1]
        rows.append(row)
    return rows
