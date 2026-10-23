"""Operator-only Campaign 003 paths and exact-byte evidence helpers."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
INTEGRATION = HERE.parent
EXPERIMENT = INTEGRATION.parent
REPO = EXPERIMENT.parent
RUNTIME = EXPERIMENT / 'Runtime 004'
C02 = INTEGRATION / 'campaign-002'
MAP = EXPERIMENT / 'Architecture Map'
QUEUE = REPO.parent / 'tools/compute_queue/compute_queue.py'

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def save(path, value, *, exclusive=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb' if exclusive else 'wb') as stream:
        stream.write(canonical(value) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def inherited_paths():
    for path in (RUNTIME, EXPERIMENT/'Storage Retention Implementation 001/future',
                 INTEGRATION/'host', C02/'harness'):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

def clock(run_id, session_id=None, sim_time_s=None, *, source='windows-qpc'):
    return dict(run_id=run_id, session_id=session_id, wall_unix_ns=time.time_ns(),
                monotonic_ns=time.perf_counter_ns(), clock_source=source, sim_time_s=sim_time_s)

