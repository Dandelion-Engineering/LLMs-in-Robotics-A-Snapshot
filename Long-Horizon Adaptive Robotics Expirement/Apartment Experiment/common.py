"""Apartment apparatus utilities. All runtime evidence lives on the selected D: root."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if (HERE/'source-origin.json').is_file():
    REPO = Path(json.loads((HERE/'source-origin.json').read_text())['repository'])
DEFAULT_ROOT = Path('D:/Dandelion-Apartment-Experiment')

def canonical(value):
    def scalar(obj):
        if type(obj).__module__.startswith('numpy') and hasattr(obj,'item'):return obj.item()
        raise TypeError('Unsupported JSON value: '+str(type(obj)))
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False, default=scalar).encode('utf-8')

def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.next')
    with temporary.open('wb') as stream:
        stream.write(canonical(value) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def copy_durable(source, destination):
    """Copy immutable evidence bytes, then flush before publishing a manifest."""
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    with Path(source).open('rb') as incoming, destination.open('xb') as outgoing:
        for block in iter(lambda:incoming.read(1024*1024),b''):outgoing.write(block)
        outgoing.flush();os.fsync(outgoing.fileno())

def prefix_sha(path, size):
    if type(size) is not int or size<0:raise ValueError('Invalid prefix length')
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        remaining=size
        while remaining:
            block=stream.read(min(1024*1024,remaining))
            if not block:raise ValueError('Evidence prefix is truncated')
            digest.update(block);remaining-=len(block)
    return digest.hexdigest()

class Events:
    """Append-only events with exact state time, receipt time and a chained digest."""
    def __init__(self, path, clock_epoch=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.sequence = 0
        self.chain = '0' * 64
        self.clock_epoch=clock_epoch or uuid.uuid4().hex
        self.previous_clock=None
        if self.path.exists():
            for line in self.path.read_bytes().splitlines():
                value = json.loads(line)
                digest = value.pop('sha256')
                if value['sequence'] != self.sequence + 1 or value['previous'] != self.chain or hashlib.sha256(canonical(value)).hexdigest() != digest:
                    raise ValueError('Event chain corrupt')
                self.sequence, self.chain = value['sequence'], digest
        self.stream = self.path.open('ab', buffering=0)

    def emit(self, kind, sim_time, payload):
        wall=time.time_ns();monotonic=time.perf_counter_ns()
        value = dict(sequence=self.sequence + 1, previous=self.chain, kind=kind,
                     sim_time=float(sim_time), wall_ns=wall, monotonic_ns=monotonic,
                     clock_epoch=self.clock_epoch,payload=payload)
        if self.previous_clock is not None:
            dw=wall-self.previous_clock[0];dm=monotonic-self.previous_clock[1]
            if dm<0:raise ValueError('Monotonic clock regressed within one process epoch')
            if abs(dw-dm)>250_000_000:
                value['wall_clock_discontinuity']=dict(wall_delta_ns=dw,monotonic_delta_ns=dm,
                    ordering='event sequence and simulation time; wall clock is descriptive only')
        self.previous_clock=(wall,monotonic)
        self.chain = hashlib.sha256(canonical(value)).hexdigest()
        self.sequence += 1
        value['sha256'] = self.chain
        self.stream.write(canonical(value) + b'\n')
        return value

    def flush(self):
        self.stream.flush()
        os.fsync(self.stream.fileno())

    def close(self):
        self.flush()
        self.stream.close()

def inventory(root):
    root = Path(root)
    return {p.relative_to(root).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size}
            for p in sorted(root.rglob('*')) if p.is_file() and not p.is_symlink()}
