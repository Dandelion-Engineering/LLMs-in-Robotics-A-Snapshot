"""One source-bound host-scope synthetic ETW diagnostic; no model launch."""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import uuid
import etw_session as etw

HERE=Path(__file__).resolve().parent
PREPARED=HERE.parent/'admin-coverage-automation-002'
sys.path.insert(0,str(PREPARED))
import run_coverage as base

SESSION='C02TcpClosureCoverage003'
OUTPUT_ROOT=base.OUTPUT_ROOT
LIMIT=16*1024*1024


def clock_pair():
    before=time.perf_counter_ns();utc=time.time_ns();after=time.perf_counter_ns()
    return {'perf_before_ns':before,'utc_ns':utc,'perf_after_ns':after}


def source_paths():
    return {name:HERE/name for name in ('run_direct_coverage.py','etw_session.py','read_etl.py','schema.json','DECLARATION.md')} | {
        'run_coverage.py':PREPARED/'run_coverage.py','owned_process.py':PREPARED/'owned_process.py','coverage_fixture.py':base.FIXTURE}


def validate_output(out):
    out=Path(out).resolve()
    if out.parent!=OUTPUT_ROOT or not re.fullmatch(r'host-coverage-\d{8}-\d{3}',out.name):
        raise ValueError('Unexpected output path')
    if out.exists():
        raise FileExistsError('Fresh output required')
    return out


def validate_binding(path,out):
    binding=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if binding['output']!=str(out) or binding['session']!=SESSION or set(binding['sources'])!=set(source_paths()):
        raise ValueError('Binding scope differs')
    uuid.UUID(binding['guid'])
    for name,source in source_paths().items():
        if hashlib.sha256(source.read_bytes()).hexdigest()!=binding['sources'][name]:
            raise ValueError('Source changed: '+name)
    return binding


def run(out,*,manifest_path=None,require_admin=True,commands_type=base.Commands,api=None,interrupt_at=None):
    out=Path(out).resolve()
    if require_admin:
        validate_output(out)
        if Path(sys.executable).resolve()!=base.PYTHON.resolve() or not C.windll.shell32.IsUserAnAdmin():
            raise RuntimeError('Exact project Python through one-shot UAC required')
        binding=validate_binding(manifest_path,out)
        guid=binding['guid']
    else:
        if api is None:
            raise ValueError('Unelevated test requires an injected simulated API')
        guid=str(uuid.uuid4())
    out.mkdir()
    base.save(out/'intent.json',{'session':SESSION,'guid':guid,'packet_capture':False,'max_seconds':30,
        'max_etl_bytes':LIMIT,'model_calls':0,'simulated_etw':api is not None,
        'source_sha256':{n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in source_paths().items()}})
    cmd=commands_type(out);children=[];fixtures=[];filters=None;session=None
    errors=[];cleanup_errors=[];retirements=[];begin=end=None
    etl=out/'closure.etl'
    try:
        base.validate_preflight(cmd.pktmon('status'),cmd.pktmon('filter','list'),cmd.call(base.NETSH,['trace','show','status']))
        if hashlib.sha256(base.FIXTURE.read_bytes()).hexdigest()!=base.FIXTURE_SHA:
            raise RuntimeError('Original fixture changed')
        for label in ('included','excluded'):
            fixture=out/label
            child=base.OwnedProcess([str(base.PYTHON),'-X','utf8','-B',str(base.FIXTURE),'--output',str(fixture)],
                base.ROOT,out/(label+'-stdout.txt'),out/(label+'-stderr.txt'))
            children.append(child);base.save(out/(label+'-launch.json'),child.launch_identity)
            deadline=time.monotonic()+8
            while True:
                if child.poll() is not None or time.monotonic()>=deadline:
                    raise RuntimeError('Fixture readiness failed: '+label)
                try:
                    ready=json.loads((fixture/'ready.json').read_bytes());break
                except (FileNotFoundError,json.JSONDecodeError):
                    time.sleep(.025)
            identity=child.validate_ready(ready,[base.PYTHON,sys._base_executable],fixture)
            base.save(out/(label+'-identity.json'),identity)
            fixtures.append({'label':label,'ready':ready,'output':str(fixture)})
        if fixtures[0]['ready']['port']==fixtures[1]['ready']['port']:
            raise RuntimeError('Control port collision')
        base.save(out/'fixtures.json',fixtures)
        filters=etw.EventFilters([f['ready']['pid'] for f in fixtures])
        base.save(out/'filters.json',{'control_pids':filters.control_pids,'filter_count':1,'collection_scope':'all-processes',
            'event_ids':list(etw.IDS),'ignore_keyword_zero':True,'process_filter':False})
        if interrupt_at=='ready':
            raise KeyboardInterrupt('Declared pre-trace interruption')
        base.save(out/'clock-before.json',clock_pair())
        begin=time.perf_counter_ns()
        session=etw.Session(SESSION,etl,guid,filters,api)
        session.start()
        if interrupt_at=='capture':
            raise KeyboardInterrupt('Declared post-enable interruption')
        if time.perf_counter_ns()-begin>10_000_000_000:
            raise RuntimeError('Startup exceeded synthetic control time budget')
        for fixture in fixtures:
            base.save(Path(fixture['output'])/'release.json',{'release':True})
        for child in children:
            remaining=15-(time.perf_counter_ns()-begin)/1e9
            if remaining<=0 or child.wait(timeout=min(5,remaining))!=0:
                raise RuntimeError('Socket control failed')
    except BaseException as exc:
        errors.append({'type':type(exc).__name__,'message':str(exc)[:1200]})
    finally:
        if session is not None:
            try:
                session.stop()
                if session.stopped:
                    end=time.perf_counter_ns()
            except BaseException as exc:
                cleanup_errors.append('TRACE: '+str(exc)[:1000])
            base.save(out/'etw-api.json',session.records)
        if filters is not None:
            try:
                filters.close()
            except BaseException as exc:
                cleanup_errors.append('FILTERS: '+str(exc)[:1000])
        for child in children:
            try:
                retirements.append(child.retire())
            except BaseException as exc:
                retirements.append(child.retirement)
                cleanup_errors.append('FIXTURE: '+str(exc)[:1000])
            finally:
                child.close()
    elapsed=None if end is None else (end-begin)/1e9
    base.save(out/'clock-after.json',clock_pair())
    if session and session.started and (elapsed is None or elapsed>30):
        errors.append({'type':'BoundNotEstablished','message':'Complete trace retirement within30seconds not established'})
    if session and session.stopped:
        if not etl.is_file() or not 0<etl.stat().st_size<=LIMIT:
            errors.append({'type':'InvalidETL','message':'Terminal ETL missing or outside16MiB bound'})
    try:
        if not base.idle_status(cmd.pktmon('status')) or not base.empty_filters(cmd.pktmon('filter','list')):
            raise RuntimeError('Packet Monitor state changed; no mutation attempted')
    except BaseException as exc:
        cleanup_errors.append('FINAL STATE: '+str(exc)[:1000])
    receipt={'collection_completed':not errors and not cleanup_errors,'coverage_qualified':False,'model_calls':0,
        'packet_capture':False,'session':SESSION,'guid':guid,'trace_started':bool(session and session.started),
        'trace_stopped':bool(session and session.stopped),'trace_elapsed_s':elapsed,
        'errors':errors,'cleanup_errors':cleanup_errors,'fixture_retirements':retirements,'simulated_etw':api is not None}
    base.save(out/'receipt.json',receipt)
    print(json.dumps(receipt,indent=2),flush=True)
    return 0 if receipt['collection_completed'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source-manifest',type=Path,required=True)
    args=parser.parse_args()
    raise SystemExit(run(args.output,manifest_path=args.source_manifest))
