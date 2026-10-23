"""Prospective nested timing of unchanged synchronous journal durability.

Original supervisor.py is untouched. Event/state/registry implementations below
retain its write, flush, fsync, replace, retry and evidence-budget ordering.
"""
from contextlib import nullcontext
import copy
import os
from pathlib import Path
import time

from supervisor import (Journal, SCHEMA, canonical, require,
                        ATOMIC_REPLACE_DELAYS, ATOMIC_REPLACE_RETRIES)


class InstrumentedJournal(Journal):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.capture = None
        self.sim_clock = lambda: 0.

    def phase(self, name, details=None):
        if self.capture is None or self.capture.terminal is not None:
            return nullcontext()
        return self.capture.phase(name, self.sim_clock, details=details)

    def atomic_bytes(self, path, raw, label):
        path = Path(path)
        with self.phase(label + '.prepare'):
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_name(path.name + '.next')
        with self.phase(label + '.open'):
            stream = temp.open('wb')
        try:
            with self.phase(label + '.write_flush'):
                stream.write(raw)
                stream.flush()
            with self.phase(label + '.fsync'):
                os.fsync(stream.fileno())
        finally:
            with self.phase(label + '.close'):
                stream.close()
        for attempt in range(len(ATOMIC_REPLACE_DELAYS) + 1):
            try:
                with self.phase(label + '.replace'):
                    os.replace(temp, path)
                return
            except PermissionError as error:
                if getattr(error, 'winerror', None) not in (5, 32, 33):
                    raise
                if attempt == len(ATOMIC_REPLACE_DELAYS):
                    ATOMIC_REPLACE_RETRIES['exhausted'] += 1
                    raise
                delay = ATOMIC_REPLACE_DELAYS[attempt]
                ATOMIC_REPLACE_RETRIES['retries'] += 1
                ATOMIC_REPLACE_RETRIES['requested_wait_s'] += delay
                with self.phase(label + '.retry_sleep'):
                    time.sleep(delay)

    def atomic_json(self, path, value, label):
        with self.phase(label + '.serialize'):
            raw = canonical(value) + b'\n'
        self.atomic_bytes(path, raw, label)

    def event(self, kind, payload, sim, epoch, owner, *, source='supervisor'):
        with self.phase('journal.event.serialize', {'event_type': kind}):
            item = {'schema': SCHEMA, 'event_id': len(self.events) + 1,
                    'run_id': self.run_id, 'authority_epoch': epoch, 'owner': owner,
                    'source': source, 'type': kind, 'sim_time_s': sim,
                    # Journal chronology retains its original clock origin;
                    # the separate full timing ledger uses the declared QPC.
                    'wall_elapsed_s': time.monotonic() - self.start,
                    'wall_unix_s': time.time(), 'payload': copy.deepcopy(payload)}
            raw = canonical(item) + b'\n'
            require(self.bytes + 2 * len(raw) < self.limit - 2 * 1024 * 1024,
                    'storage_limit', 'Evidence budget reached; new actuation refused', 507)
        for label, path in (('journal.event.protected', self.events_path), ('journal.event.public', self.mirror_path)):
            with self.phase(label + '.open'):
                stream = path.open('ab')
            try:
                with self.phase(label + '.write_flush'):
                    stream.write(raw)
                    stream.flush()
                with self.phase(label + '.fsync'):
                    os.fsync(stream.fileno())
            finally:
                with self.phase(label + '.close'):
                    stream.close()
        self.bytes += 2 * len(raw)
        self.events.append(item)
        return item['event_id']

    def state(self, value):
        self.atomic_json(self.root / 'public-state.json', value, 'journal.state.protected')
        self.atomic_json(self.live / 'state.json', value, 'journal.state.public')

    def registry(self, commands):
        self.atomic_json(self.root / 'command-registry.json', commands, 'journal.registry')

    def continuity(self, content):
        # Keep the protected byte/back-up contract in the original implementation.
        with self.phase('journal.continuity'):
            return super().continuity(content)
