"""Declared, synchronous, source-bound C: durability workload; no physics/model."""
from __future__ import annotations
import argparse
from array import array
from contextlib import contextmanager
from datetime import datetime, timezone
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import sqlite3
import sys
import time

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
INTEGRATION = CAMPAIGN.parent
EXPERIMENT = INTEGRATION.parent
REPO = EXPERIMENT.parent
FUTURE = EXPERIMENT / 'Storage Retention Implementation 001/future'
for directory in (INTEGRATION / 'host', FUTURE, CAMPAIGN / 'harness'):
    sys.path.insert(0, str(directory))
from instrumented_journal import InstrumentedJournal
from instrumented_recorder import InstrumentedFutureEvidence
from recorder import ImagePolicy, Reader

FIELDS = ['sequence','parent','phase','tick','wall_start_s','wall_end_s',
          'thread_cpu_start_s','thread_cpu_end_s','process_cpu_start_s','process_cpu_end_s','failed']
MAX_ROWS = 250000
EXPECTED = dict(schema='rci-c02-protected-io-diagnostic-1', duration_s=120, tick_hz=100,
                sensor_every_ticks=10, state_every_ticks=50, wall_cap_s=180,
                output_cap_bytes=134217728, model_turns_max=0, physics_steps_max=0,
                image_quota_bytes=12000000, core_quota_bytes=50000000,
                sparse_period_s=2, maximum_timing_rows=MAX_ROWS)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''): h.update(block)
    return h.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def bind(path):
    path=Path(path)
    return {'path':path.relative_to(REPO).as_posix(),'bytes':path.stat().st_size,'sha256':sha(path)}


def source_paths():
    return [HERE/name for name in ('benchmark.py','assess.py','test_diagnostic.py','README.md')]+[
        INTEGRATION/'host/supervisor.py', CAMPAIGN/'harness/instrumented_journal.py',
        CAMPAIGN/'harness/instrumented_recorder.py', FUTURE/'recorder.py', FUTURE/'runtime_adapter.py']


def validate_manifest(value):
    for key, expected in EXPECTED.items():
        if type(value.get(key)) is not type(expected) or value[key] != expected:
            raise ValueError('Fixed declaration mismatch: '+key)
    if not value.get('run_id') or not value.get('framework_revision'):
        raise ValueError('Run and frozen revision identities required')
    return value


class Ledger:
    """Every entered operation, including failures; inclusive nesting, no truncation."""
    def __init__(self, maximum=MAX_ROWS):
        self.origin=time.perf_counter(); self.values=array('d'); self.names={}; self.stack=[]
        self.sequence=0; self.tick=-1; self.terminal=None; self.maximum=maximum

    @contextmanager
    def phase(self, name, sim_clock=None, details=None):
        if self.sequence >= self.maximum: raise RuntimeError('Full timing ledger bound reached')
        code=self.names.setdefault(name,len(self.names)+1)
        self.sequence+=1; sequence=self.sequence; parent=self.stack[-1] if self.stack else 0
        self.stack.append(sequence)
        start=time.perf_counter()-self.origin; cpu=time.thread_time(); proc=time.process_time(); failed=0
        try: yield
        except BaseException:
            failed=1
            raise
        finally:
            end=time.perf_counter()-self.origin; cpu_end=time.thread_time(); proc_end=time.process_time()
            self.stack.pop()
            self.values.extend((sequence,parent,code,self.tick,start,end,cpu,cpu_end,proc,proc_end,failed))

    def persist(self, output):
        path=output/'operations.bin'
        with path.open('wb') as stream: self.values.tofile(stream)
        return dict(path=path.name,sha256=sha(path),bytes=path.stat().st_size,
                    rows=len(self.values)//len(FIELDS),fields=FIELDS,format='native float64',
                    byteorder=sys.byteorder,phase_codes=self.names,
                    scope='Complete inclusive operation intervals. Parent and child durations overlap.')


def process_io():
    """Read-only Windows counters. They do not identify device/filter/scheduler causes."""
    if os.name != 'nt': return {'available':False,'reason':'Windows GetProcessIoCounters unavailable'}
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[(name,ctypes.c_ulonglong) for name in
                  ('read_operations','write_operations','other_operations','read_bytes','write_bytes','other_bytes')]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    kernel.GetProcessIoCounters.argtypes=(wintypes.HANDLE,ctypes.POINTER(Counters))
    counters=Counters()
    if not kernel.GetProcessIoCounters(kernel.GetCurrentProcess(),ctypes.byref(counters)):
        return {'available':False,'winerror':ctypes.get_last_error()}
    return dict(available=True,**{name:getattr(counters,name) for name,_ in counters._fields_})


def load_inputs(manifest):
    for binding in manifest['input_bindings']:
        if bind(REPO/binding['path']) != binding: raise ValueError('Retained input changed: '+binding['path'])
    host=REPO/manifest['input_host']
    journal=[json.loads(line) for line in (host/'public-history.jsonl').read_text(encoding='utf-8').splitlines()]
    observations=[row for row in journal if row['type']=='observation']
    reader=Reader(host/'native-recording')
    try:
        motion=list(reader.motion())
        pairs=[]
        for row in reader.images():
            if row['status']=='available':
                image=reader.image(row['id'])
                pairs.append((row['id'],image['rgb'],image['depth']))
        policy=json.loads(reader.meta['policy'])
        if len(list(reader.events())) != 0: raise ValueError('Expected authentic zero SQL event rows')
    finally: reader.close()
    if len(observations)!=588 or len(motion)!=5912 or len(pairs)!=30:
        raise ValueError('Native003 stock1 input cardinalities changed')
    if policy['sparse_period_s']!=2 or policy['image_quota_bytes']!=12000000:
        raise ValueError('Source policy differs')
    return dict(observations=observations,motion=motion,pairs=pairs,
        state=json.loads((host/'public-state.json').read_text()),
        registry=json.loads((host/'command-registry.json').read_text()))


def apply_tick(tick, inputs, journal, evidence, ledger):
    """Same public methods and persistence order; synthetic monotonically increasing clocks."""
    ledger.tick=tick
    sim=tick/100
    # Native host samples motion every five .002s physics ticks: 100Hz.
    row=dict(inputs['motion'][tick % len(inputs['motion'])]); row['sim_time_s']=sim
    with ledger.phase('workload.motion'):
        evidence.motion.write(json.dumps(row,separators=(',',':'))+'\n')
    if tick % 50 == 0:
        with ledger.phase('workload.state'): journal.state(inputs['state'])
    if tick % 10 == 0:
        frame=tick//10
        _,rgb,depth=inputs['pairs'][(frame//20) % len(inputs['pairs'])]
        # Exact native encoded pairs enter the same SQLite image method. Encoding/
        # physics are intentionally absent; no placeholder or random image bytes.
        with ledger.phase('workload.image'):
            with evidence.lock: evidence.store.image('overhead:'+str(frame+1),sim,rgb,depth)
        observation=inputs['observations'][frame % len(inputs['observations'])]
        with ledger.phase('workload.event'):
            returned=journal.event(observation['type'],observation['payload'],sim,
                observation['authority_epoch'],observation['owner'],source=observation['source'])
            if returned != frame+1: raise RuntimeError('Journal completion sequence differs')
        with ledger.phase('workload.registry'): journal.registry(inputs['registry'])


def inventory(root):
    return {p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p))
            for p in sorted(root.rglob('*')) if p.is_file() and p.name!='result.json'}


def run(manifest_path, output):
    manifest_path=Path(manifest_path).resolve()
    manifest=validate_manifest(json.loads(manifest_path.read_text(encoding='utf-8')))
    output=Path(output).resolve()
    allowed=(INTEGRATION/'local-evidence/campaign002/io-repair').resolve()
    if output.drive.lower()!='c:' or not output.is_relative_to(allowed) or output==allowed:
        raise ValueError('Only a new child of the declared protected C: io-repair evidence root is permitted')
    output.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter(); sources=[bind(p) for p in source_paths()]
    write_json(output/'launch.json',dict(manifest=manifest,manifest_sha256=sha(manifest_path),
        sources=sources,created_at=datetime.now(timezone.utc).isoformat(),pid=os.getpid(),output=str(output)))
    inputs=load_inputs(manifest); ledger=Ledger(); journal=None; evidence=None
    completed=0; metrics=[]; schedules=[]; failure=None; pragmas=[]
    try:
        with ledger.phase('setup.journal'):
            journal=InstrumentedJournal(output/'protected',output/'public-workspace',manifest['run_id'])
            journal.capture=ledger
        with ledger.phase('setup.recorder'):
            evidence=InstrumentedFutureEvidence(output/'native-recording',manifest['run_id'],phase=ledger.phase,
                policy=ImagePolicy(sparse_period_s=2.,image_quota_bytes=12000000),core_quota_bytes=50000000)
        pragmas.append({'at':'before','journal_mode':evidence.store.db.execute('PRAGMA journal_mode').fetchone()[0],
            'synchronous':evidence.store.db.execute('PRAGMA synchronous').fetchone()[0]})
        origin=time.perf_counter(); measured_start=origin-ledger.origin
        for tick in range(12000):
            ledger.tick=tick
            deadline=origin+tick/100
            if time.perf_counter()-started >= 180: raise TimeoutError('Declared cooperative wall cap reached')
            delay=deadline-time.perf_counter()
            if delay>0: time.sleep(delay)
            entered=time.perf_counter()-origin
            if tick % 100 == 0:
                with ledger.phase('diagnostic.process_io'): metrics.append(dict(tick=tick,wall_s=entered,**process_io()))
            with ledger.phase('workload.tick'): apply_tick(tick,inputs,journal,evidence,ledger)
            completed+=1; schedules.append((tick,entered,time.perf_counter()-origin))
        delay=origin+120-time.perf_counter()
        if delay>0: time.sleep(delay)
        measured_end=time.perf_counter()-ledger.origin
        pragmas.append({'at':'after','journal_mode':evidence.store.db.execute('PRAGMA journal_mode').fetchone()[0],
            'synchronous':evidence.store.db.execute('PRAGMA synchronous').fetchone()[0]})
        with ledger.phase('finalize.recorder'): evidence.close()
        evidence=None
    except Exception as error:
        failure=dict(type=type(error).__name__,message=str(error))
        measured_end=time.perf_counter()-ledger.origin
        if evidence is not None:
            try: evidence.store.db.close()
            except Exception as close_error: failure['close_error']=str(close_error)
    ledger.terminal=True
    timing=ledger.persist(output)
    write_json(output/'process-io.json',metrics)
    write_json(output/'schedule.json',dict(fields=['tick','start_s','end_s'],rows=schedules))
    files=inventory(output); total_bytes=sum(row['bytes'] for row in files.values())
    elapsed=time.perf_counter()-started
    result=dict(schema='rci-c02-protected-io-result-1',run_id=manifest['run_id'],framework_revision=manifest['framework_revision'],
        manifest_sha256=sha(manifest_path),sources_before=sources,sources_after=[bind(p) for p in source_paths()],
        completed_ticks=completed,expected_ticks=12000,failure=failure,pragmas=pragmas,timing=timing,
        measured_start_s=locals().get('measured_start'),measured_end_s=measured_end,
        total_wall_s=elapsed,aggregate_output_bytes_before_result=total_bytes,files=files,
        completed=completed==12000 and failure is None and elapsed<=180 and total_bytes<manifest['output_cap_bytes']-1000000,
        environment=dict(python=sys.version,platform=platform.platform(),sqlite=sqlite3.sqlite_version),
        scorable=False,task_outcome='unknown',qualification_passed=False,
        limitations=manifest['limitations'])
    write_json(output/'result.json',result)
    print(json.dumps({'result':str(output/'result.json'),'completed':result['completed']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--validate',action='store_true')
    args=parser.parse_args()
    if args.validate:
        validate_manifest(json.loads(args.manifest.read_text(encoding='utf-8'))); print('Fixed declaration accepted')
    elif args.output is None: parser.error('--output is required for execution')
    else: run(args.manifest,args.output)
