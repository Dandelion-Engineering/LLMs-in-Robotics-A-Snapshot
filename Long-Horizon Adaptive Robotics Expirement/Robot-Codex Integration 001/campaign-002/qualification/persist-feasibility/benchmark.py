"""Fixed, counterbalanced, no-physics recorder feasibility experiment.

Execution is authorized only through the parent's separately declared queue job.
This CLI never installs or imports the candidate into the native robot host.
"""
from __future__ import annotations
import argparse
from array import array
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import shutil
import sqlite3
import struct
import subprocess
import sys
import time
from types import SimpleNamespace
import zlib

from candidate import (CandidateEvidence, CandidateRecorder, OperationLog, SPACE_POLICY, POLICY,
                       CORE_QUOTA, HERE, EXPERIMENT, hash_file, write_json)
from recorder import Reader, pack
from runtime_adapter import LiveSensorBridge

ORDER = ['DELETE', 'PERSIST', 'PERSIST', 'DELETE', 'DELETE', 'PERSIST', 'PERSIST', 'DELETE']
REPO = EXPERIMENT.parent


def validate_manifest(value):
    expected = dict(schema='rci-recorder-journal-feasibility-1', seed=173, mode_order=ORDER,
        frames_per_round=600, motion_rows_per_frame=10, width=64, height=48, wall_cap_s=300,
        space_policy=SPACE_POLICY)
    for name, target in expected.items():
        if value.get(name) != target or type(value.get(name)) is not type(target):
            raise ValueError('Manifest differs from fixed declaration: '+name)
    for name in ('run_id', 'framework_revision'):
        if not isinstance(value.get(name), str) or not value[name]: raise ValueError('Missing identity: '+name)
    return value


def inventory(directory):
    return {p.relative_to(directory).as_posix(): {'bytes': p.stat().st_size, 'sha256': hash_file(p)}
            for p in sorted(Path(directory).rglob('*')) if p.is_file()}


def tree_bytes(directory):
    return sum(p.stat().st_size for p in Path(directory).rglob('*') if p.is_file())


def reader_fingerprint(directory):
    reader = Reader(directory); hashes = {}; counts = {}
    try:
        for name, values in [('events', reader.events()), ('motion', reader.motion()), ('images', reader.images())]:
            digest=hashlib.sha256(); count=0
            for value in values:
                raw=pack(value); digest.update(struct.pack('<Q', len(raw))); digest.update(raw); count+=1
            hashes[name]=digest.hexdigest(); counts[name]=count
        digest=hashlib.sha256(); count=0
        for row in reader.images():
            image=reader.image(row['id'])
            if image['status']=='available':
                for raw in (row['id'].encode(), image['rgb'], image['depth']):
                    digest.update(struct.pack('<Q',len(raw)));digest.update(raw)
                count+=1
        hashes['available_image_pairs']=digest.hexdigest(); counts['available_image_pairs']=count
        documents={row[0]:reader.document(row[0]) for row in reader.db.execute('SELECT name FROM documents ORDER BY name')}
        hashes['documents']=hashlib.sha256(pack(documents)).hexdigest();counts['documents']=len(documents)
        check=reader.db.execute('PRAGMA integrity_check').fetchall()
        if check != [('ok',)]: raise RuntimeError('Reader integrity check failed')
        return dict(hashes=hashes, counts=counts, integrity_check=check,
                    journal_mode=reader.db.execute('PRAGMA journal_mode').fetchone()[0])
    finally:
        reader.close()


def workload(evidence, frames, motion_rows, width, height, seed, log, deadline):
    import numpy as np
    generator=np.random.default_rng(seed)
    rgb_base=generator.integers(0,256,size=(height,width,3),dtype=np.uint8)
    depth_base=generator.random((height,width),dtype=np.float32)
    input_hash=hashlib.sha256(); bridge=LiveSensorBridge(evidence)
    log.measured=True
    started=time.perf_counter()
    for index in range(frames):
        if time.perf_counter() >= deadline: raise TimeoutError('Predeclared total wall cap exceeded')
        tick=index*.1
        rgb=(rgb_base.astype(np.uint16)+index).astype(np.uint8)
        depth=(depth_base+np.float32(index*.0001)).astype(np.float32)
        rgb.setflags(write=False);depth.setflags(write=False)
        input_hash.update(rgb.tobytes());input_hash.update(depth.tobytes())
        for offset in range(motion_rows):
            sample=dict(sim_time_s=tick+offset*.01,q=[index*.001,offset*.01,-0.],
                        dq=[0.,0.,0.],tcp=[.1,.2,.3],custom={'seed':seed})
            text=json.dumps(sample,separators=(',',':'))+'\n'
            log.call('motion_write',evidence.motion.write,text)
        result=SimpleNamespace(rgb=rgb,depth=depth,camera='synthetic',sequence=index,capture_sim_time_s=tick)
        returned=log.call('image',bridge.observe,result)
        if returned is not result: raise RuntimeError('Bridge changed live result identity')
        if index == frames//2:
            log.call('trigger',evidence.trigger,tick,1,'predeclared synthetic diagnostic')
        if index % 100 == 0:
            log.call('event',evidence.emit,'synthetic',{'index':index,'seed':seed},tick)
    log.call('document',evidence.document,'fixed-input',{'seed':seed,'frames':frames,'width':width,'height':height})
    elapsed=time.perf_counter()-started
    log.measured=False
    return dict(input_sha256=input_hash.hexdigest(), measured_workload_wall_s=elapsed,
                frames=frames,motion_rows=frames*motion_rows,
                scope='Synthetic timestamped inputs executed as fast as synchronous calls permit; not wall-paced physics.')


def distribution(log, code):
    values=[row[2]-row[1] for row in zip(*[iter(log.values)]*6) if int(row[0])==code]
    if not values:return dict(count=0)
    values.sort()
    return dict(count=len(values),minimum_s=values[0],median_s=values[(len(values)-1)//2],
        p95_s=values[int(.95*(len(values)-1))],p99_s=values[int(.99*(len(values)-1))],
        maximum_s=values[-1],total_s=sum(values),quantile_method='lower order statistic')


def crash_child(directory, mode, stage):
    """Disposable process-crash fixture, intentionally exits without cleanup."""
    import os
    rec=CandidateRecorder(directory,run_id='crash-fixture',mode=mode,policy=POLICY,core_quota_bytes=CORE_QUOTA)
    rec.document('stable',{'committed':True,'value':'before interruption'})
    stable=rec.native.execute("SELECT payload FROM documents WHERE name='stable'").fetchone()[0]
    # Recovery fixture only: small cache forces a hot journal before the injected
    # commit boundary. Counterbalanced workload leaves the default cache intact.
    rec.native.execute('PRAGMA cache_size=8')
    rec.readback('crash_fixture',mode)
    original=rec.db.commit
    def interrupted_commit():
        if stage=='after_commit': original()
        journal=rec.path/'evidence.sqlite-journal'
        ready=dict(stage=stage,mode=mode,stable_payload_sha256=hashlib.sha256(stable).hexdigest(),
            journal_present=journal.exists(),journal_bytes=journal.stat().st_size if journal.exists() else 0,
            first_journal_header_hex=journal.read_bytes()[:28].hex() if journal.exists() else None,
            in_transaction=rec.native.in_transaction,readback=rec.readbacks[-1],cache_pages=8)
        write_json(rec.path.parent/'crash-ready.json',ready)
        os._exit(23)
    # Instance proxy injection leaves the original Recorder.document mutation
    # and commit-before-return path intact, stopping at its exact commit call.
    object.__setattr__(rec.db,'commit',interrupted_commit)
    payload={'pending':True,'data':''.join(hashlib.sha256(str(i).encode()).hexdigest() for i in range(4000))}
    rec.document('pending',payload)
    raise AssertionError('Crash hook did not fire')


def recovery_check(root, mode, stage, deadline):
    root.mkdir(parents=True,exist_ok=False); source=root/'interrupted'; recovered=root/'recovery-copy'
    started=time.perf_counter()
    command=[sys.executable,'-X','utf8','-B',str(HERE/'benchmark.py'),'crash-child',
             '--directory',str(source),'--mode',mode,'--stage',stage]
    started_unix_s=time.time()
    proc=subprocess.run(command,capture_output=True,text=True,timeout=max(.1,min(30.,deadline-time.perf_counter())))
    ended_unix_s=time.time()
    (root/'stdout.txt').write_text(proc.stdout,encoding='utf-8');(root/'stderr.txt').write_text(proc.stderr,encoding='utf-8')
    if proc.returncode!=23:raise RuntimeError('Crash fixture did not exit at its declared boundary')
    ready=json.loads((root/'crash-ready.json').read_text())
    if stage=='before_commit' and (not ready['journal_present'] or ready['journal_bytes']<=28 or
                                   not ready['in_transaction']):raise RuntimeError('Interrupted journal fixture absent')
    before=inventory(source);shutil.copytree(source,recovered)
    if inventory(recovered)!=before:raise RuntimeError('Recovery copy differs from retained interrupted pair')
    connection=sqlite3.connect(recovered/'evidence.sqlite')
    try:
        rows=connection.execute('SELECT name,payload FROM documents ORDER BY name').fetchall()
        names=[row[0] for row in rows]
        if names != (['pending','stable'] if stage=='after_commit' else ['stable']):
            raise RuntimeError('SQLite recovered wrong committed transaction set')
        stable=dict(rows)['stable']
        if hashlib.sha256(stable).hexdigest()!=ready['stable_payload_sha256']:raise RuntimeError('Committed payload changed')
        if connection.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:raise RuntimeError('Recovered DB integrity differs')
    finally:connection.close()
    if inventory(source)!=before:raise RuntimeError('Retained interrupted source pair was modified')
    if (source/'container-manifest.json').exists():raise RuntimeError('Interrupted recording was published complete')
    return dict(passed=True,mode=mode,stage=stage,expected_child_exit=23,actual_child_exit=proc.returncode,
        argv=command,started_unix_s=started_unix_s,ended_unix_s=ended_unix_s,
        wall_s=time.perf_counter()-started,ready=ready,source_files=before,recovered_files=inventory(recovered),
        source_pair_preserved=True,committed_document_names=names,
        scope='Abrupt process exit and SQLite recovery on an exact copy; not a power-loss or storage-device guarantee.')


def run(manifest_path, output):
    manifest_path=Path(manifest_path).resolve();manifest=validate_manifest(json.loads(manifest_path.read_text()))
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter(); deadline=start+manifest['wall_cap_s']
    source_paths=[HERE/'candidate.py',HERE/'benchmark.py',HERE/'test_candidate.py',
        EXPERIMENT/'Storage Retention Implementation 001/future/recorder.py',
        EXPERIMENT/'Storage Retention Implementation 001/future/runtime_adapter.py']
    sources={p.relative_to(REPO).as_posix():dict(sha256=hash_file(p),bytes=p.stat().st_size) for p in source_paths}
    rounds=[];recovery=[];failures=[]
    for index,mode in enumerate(manifest['mode_order']):
        root=output/('round-%02d-%s'%(index,mode.lower()));root.mkdir()
        if time.perf_counter()>=deadline:
            row=dict(ordinal=index,mode=mode,status='unrun_wall_cap',passed=False);rounds.append(row);continue
        row=dict(ordinal=index,mode=mode,status='started',passed=False)
        evidence=None;log=OperationLog(maximum=manifest['frames_per_round']*24+1024)
        try:
            if tree_bytes(output)+SPACE_POLICY['native_reserve_bytes']>SPACE_POLICY['host_cap_bytes']:
                raise RuntimeError('Completed outputs plus active native reserve exceed declared host cap')
            evidence=CandidateEvidence(root/'native-recording',manifest['run_id'],mode=mode,
                policy=POLICY,core_quota_bytes=CORE_QUOTA,clock=lambda:100.,operation_log=log)
            row['workload']=workload(evidence,manifest['frames_per_round'],manifest['motion_rows_per_frame'],
                manifest['width'],manifest['height'],manifest['seed'],log,deadline)
            evidence.close()
            row['reader']=reader_fingerprint(evidence.path)
            row.update(status='completed',passed=True)
        except Exception as error:
            row.update(status='failed',error=dict(type=type(error).__name__,message=str(error)))
            failures.append(dict(ordinal=index,mode=mode,error=row['error']))
            # No retry or forced finalization. SQLite owns any rollback/close;
            # all directory contents are retained with the failure receipt.
            if evidence is not None:
                try:evidence.store.native.close()
                except Exception as close_error:row['close_error']=str(close_error)
        finally:
            log.measured=False
            row['operation_timing']=log.persist(root)
            row['latency']={name:distribution(log,OperationLog.CODES[name]) for name in ('image','commit','execute')}
            if evidence is not None:row['candidate']=evidence.store.receipt()
            row['retained_files']=inventory(root/'native-recording') if (root/'native-recording').exists() else {}
            row['aggregate_output_bytes']=tree_bytes(output)
            if row['aggregate_output_bytes']>SPACE_POLICY['host_cap_bytes']:
                row.update(passed=False,status='failed',error={'message':'Observed aggregate host cap exceeded'})
            write_json(root/'result.json',row);row['result_binding']=dict(path=str((root/'result.json').relative_to(output)),sha256=hash_file(root/'result.json'))
            rounds.append(row)
    for mode in ('DELETE','PERSIST'):
        for stage in ('before_commit','after_commit'):
            if time.perf_counter()>=deadline:
                recovery.append(dict(mode=mode,stage=stage,passed=False,status='unrun_wall_cap'));continue
            try:recovery.append(recovery_check(output/('crash-'+mode.lower()+'-'+stage),mode,stage,deadline))
            except Exception as error:recovery.append(dict(mode=mode,stage=stage,passed=False,error=dict(type=type(error).__name__,message=str(error))))
    complete=[row for row in rounds if row['passed']]
    parity=(len(complete)==len(ORDER) and all(row['reader']==complete[0]['reader'] and
        row['workload']['input_sha256']==complete[0]['workload']['input_sha256'] and
        row['candidate']['encoded_pairs_sha256']==complete[0]['candidate']['encoded_pairs_sha256'] for row in complete))
    import numpy as np
    result=dict(schema='rci-recorder-journal-feasibility-result-1',run_id=manifest['run_id'],
        framework_revision=manifest['framework_revision'],manifest_sha256=hash_file(manifest_path),
        created_at=datetime.now(timezone.utc).isoformat(),declared_mode_order=ORDER,rounds=rounds,recovery_checks=recovery,
        exact_reader_input_encoded_parity=parity,failures=failures,
        mechanical_feasibility_passed=parity and all(row['passed'] for row in recovery),
        source_bindings=sources,environment=dict(python=sys.version,platform=platform.platform(),sqlite=sqlite3.sqlite_version,
            numpy=np.__version__,zlib=zlib.ZLIB_RUNTIME_VERSION),
        total_wall_s=time.perf_counter()-start,aggregate_output_bytes=tree_bytes(output),
        scope='All fixed counterbalanced rounds retained; no performance-win threshold, no discarded warmup or outliers. '
              'No physics/model execution or real-time qualification. Observed file limits and reserved allowance '
              'are not a measured continuous transient peak. Process-crash recovery is not a power-loss certificate.',
        production_adopted=False,scorable=False,task_outcome='unknown')
    if result['total_wall_s']>manifest['wall_cap_s'] or result['aggregate_output_bytes']>SPACE_POLICY['host_cap_bytes']:
        result['mechanical_feasibility_passed']=False
    write_json(output/'result.json',result)
    print(json.dumps({'result':str(output/'result.json'),'mechanical_feasibility_passed':result['mechanical_feasibility_passed']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('run');p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p=sub.add_parser('validate');p.add_argument('--manifest',type=Path,required=True)
    p=sub.add_parser('crash-child');p.add_argument('--directory',type=Path,required=True);p.add_argument('--mode',choices=('DELETE','PERSIST'),required=True);p.add_argument('--stage',choices=('before_commit','after_commit'),required=True)
    args=parser.parse_args()
    if args.command=='run':run(args.manifest,args.output)
    elif args.command=='validate':validate_manifest(json.loads(args.manifest.read_text()));print('Declared fixed workload accepted')
    else:crash_child(args.directory,args.mode,args.stage)
