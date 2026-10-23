"""One-shot elevated ETW observer; accepts only authenticated start and stop."""
import argparse
import ctypes as C
import json
from pathlib import Path
import sys
import time
import trace_control as control

HERE=Path(__file__).resolve().parent
IO=HERE.parent
QUALIFIED=IO/'tcp-event-coverage-003'
sys.path.insert(0,str(QUALIFIED))
import etw_session as etw
sys.path.insert(0,str(IO/'admin-coverage-automation-002'))
import run_coverage as base


def source_paths():
    return [HERE/n for n in ('collect_window.py','trace_control.py','DECLARATION.md')]+[
        QUALIFIED/n for n in ('etw_session.py','schema.json','read_etl.py','assessment-001.json','launch-source-manifest-001.json')]+[
        IO/'admin-coverage-automation-002'/n for n in ('owned_process.py','run_coverage.py')]


def clock_pair():
    before=time.perf_counter_ns();utc=time.time_ns();after=time.perf_counter_ns()
    return {'perf_before_ns':before,'utc_ns':utc,'perf_after_ns':after}


def run(root,expected_sha,*,require_admin=True,api=None,commands_type=base.Commands,wait_limit=900,active_limit=25):
    root=Path(root).resolve()
    if require_admin:
        if root!=control.CONTROL or Path(sys.executable).resolve()!=base.PYTHON.resolve() or not C.windll.shell32.IsUserAnAdmin():
            raise RuntimeError('Exact declared output and project Python through one-shot UAC required')
        if api is not None or wait_limit!=900 or active_limit!=25:
            raise ValueError('Production observer bounds/backend cannot be overridden')
    elif api is None:
        raise ValueError('Unelevated development requires simulated ETW APIs')
    if {p.name for p in root.iterdir()}!={'config.json'}:
        raise FileExistsError('Fresh control root containing only frozen config required')
    value=control.config(root,expected_sha)
    control.verify_sources(value,source_paths())
    qualified=json.loads((QUALIFIED/'assessment-001.json').read_text(encoding='utf-8'))
    if qualified.get('qualified_for_six_type_closure_metadata') is not True:
        raise ValueError('Passing synthetic event-scope qualification required')
    commands=commands_type(root)
    errors=[];cleanup_errors=[];session=filters=peer=None;begin=end=None;stop_reason=None
    control.save(root/'intent.json',{'run':control.RUN,'revision':control.REVISION,'guid':value['guid'],
        'config_sha256':value['_sha256'],'active_capture_limit_s':30,'pre_capture_wait_limit_s':wait_limit,
        'collection_scope':'host six-event closure metadata','model_calls_by_helper':0,'simulated_etw':api is not None})
    try:
        base.validate_preflight(commands.pktmon('status'),commands.pktmon('filter','list'),commands.call(base.NETSH,['trace','show','status']))
        control.emit(root,'helper-ready',{'identity':control.own_identity(),'session':control.SESSION,'simulated':api is not None},value)
        deadline=time.monotonic()+wait_limit
        start=None
        while time.monotonic()<deadline:
            if control.receive(root,'stop',value):
                raise RuntimeError('Worker requested retirement before trace start')
            start=control.receive(root,'start',value)
            if start: break
            time.sleep(.01)
        if start is None: raise TimeoutError('No authenticated worker start within idle bound')
        if set(start['payload'])!={'identity'} or not 0<=time.perf_counter_ns()-start['observed_perf_counter_ns']<=3_000_000_000:
            raise ValueError('Stale or malformed trace-start message')
        peer=control.RetainedProcess(start['payload']['identity'],value)
        control.verify_sources(value,source_paths())
        control.save(root/'worker-identity.json',peer.identity)
        filters=etw.EventFilters([peer.identity['pid']])
        control.save(root/'clock-before.json',clock_pair())
        begin=time.perf_counter_ns()
        session=etw.Session(control.SESSION,root/'closure.etl',value['guid'],filters,api)
        session.start()
        control.emit(root,'started',{'active':True,'guid':value['guid'],'trace_begin_perf_counter_ns':begin},value)
        deadline=begin+int(active_limit*1e9)
        while time.perf_counter_ns()<deadline:
            stop=control.receive(root,'stop',value)
            if stop:
                if set(stop['payload'])!={'identity'} or stop['payload']['identity']!=peer.identity:
                    raise ValueError('Stop message worker identity differs')
                stop_reason='authenticated_worker_stop';break
            if peer.exited():
                stop_reason='worker_exit';raise RuntimeError('Worker exited before stop handshake')
            time.sleep(.005)
        else:
            stop_reason='automatic_deadline'
            raise TimeoutError('Bounded capture stopped before full worker retirement acknowledgment')
    except BaseException as exc:
        errors.append({'type':type(exc).__name__,'message':str(exc)[:500]})
    finally:
        if session:
            try:
                session.stop()
                if session.stopped: end=time.perf_counter_ns()
            except BaseException as exc:
                cleanup_errors.append('ETW:'+str(exc)[:500])
            control.save(root/'etw-api.json',session.records)
        if filters: filters.close()
        if peer: peer.close()
    control.save(root/'clock-after.json',clock_pair())
    elapsed=None if begin is None or end is None else (end-begin)/1e9
    if session and session.started and (elapsed is None or not 0<elapsed<=30):
        errors.append({'type':'BoundsFailure','message':'Complete trace retirement within30seconds not established'})
    etl=root/'closure.etl'
    if session and session.stopped and (not etl.is_file() or not 0<etl.stat().st_size<=16*1024*1024):
        errors.append({'type':'FileBoundsFailure','message':'Terminal ETL outside declared bounds'})
    try:
        if not base.idle_status(commands.pktmon('status')) or not base.empty_filters(commands.pktmon('filter','list')):
            raise RuntimeError('Packet Monitor state changed; no mutation attempted')
    except BaseException as exc:
        cleanup_errors.append('FINAL STATE:'+str(exc)[:500])
    receipt={'collection_completed':not errors and not cleanup_errors and bool(session and session.stopped),
        'coverage_qualified':False,'native_qualified':False,'run':control.RUN,'revision':control.REVISION,
        'trace_started':bool(session and session.started),'trace_stopped':bool(session and session.stopped),
        'trace_elapsed_s':elapsed,'stop_reason':stop_reason,'errors':errors,'cleanup_errors':cleanup_errors,
        'simulated_etw':api is not None,'model_calls_by_helper':0,'config_sha256':value['_sha256']}
    control.save(root/'receipt.json',receipt)
    control.emit(root,'finished',{'collection_completed':receipt['collection_completed'],'trace_stopped':receipt['trace_stopped']},value)
    print(json.dumps(receipt),flush=True)
    return 0 if receipt['collection_completed'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control',type=Path,required=True)
    parser.add_argument('--config-sha256',required=True)
    args=parser.parse_args()
    raise SystemExit(run(args.control,args.config_sha256))
