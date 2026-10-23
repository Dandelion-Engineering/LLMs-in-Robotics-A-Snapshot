"""Real owned control workers, simulated ETW; no elevated or model launches."""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import secrets
import shutil
import sys
import time
import uuid
import collect_window as collector
import trace_control as t

spec=importlib.util.spec_from_file_location('synthetic_etw_double',collector.QUALIFIED/'test_direct.py')
double=importlib.util.module_from_spec(spec);spec.loader.exec_module(double)


def configuration(root):
    root.mkdir()
    value={'run':t.RUN,'revision':t.REVISION,'control_root':str(root.resolve()),'session':t.SESSION,
        'guid':str(uuid.uuid4()),'key':secrets.token_hex(32),'created_filetime':time.time_ns()//100+116444736000000000,
        'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in collector.source_paths()}}
    t.save(root/'config.json',value)
    return hashlib.sha256((root/'config.json').read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    args.output=args.output.resolve();args.output.mkdir();(args.output/'sources').mkdir()
    sources=collector.source_paths()+[Path(__file__),collector.HERE/'control_fixture.py']
    bindings=[]
    for i,path in enumerate(sources):
        raw=path.read_bytes();copy=args.output/'sources'/f'{i:02d}-{path.name}';copy.write_bytes(raw)
        bindings.append({'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'copy':str(copy)})
    rows=[]
    modes=['success','no-start','stop-before-start','tamper-start','tamper-stop','worker-exit','automatic-deadline',
           'enable-failed','foreign-guid','foreign-path','stop-failed']
    for mode in modes:
        case=args.output/mode;case.mkdir();root=case/'control';digest=configuration(root)
        worker=collector.base.OwnedProcess([str(collector.base.PYTHON),'-X','utf8','-B',str(collector.HERE/'control_fixture.py'),
            '--control',str(root),'--mode',mode],collector.base.ROOT,case/'worker.stdout',case/'worker.stderr')
        api=double.API(mode)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                code=collector.run(root,digest,require_admin=False,api=api,commands_type=double.Commands,wait_limit=.8,active_limit=.2)
            worker.wait(timeout=5)
        finally:
            retirement=worker.retire();worker.close()
        receipt=json.loads((root/'receipt.json').read_text(encoding='utf-8'))
        stops=mode in {'success','tamper-stop','worker-exit','automatic-deadline','enable-failed','stop-failed'}
        passed=((code==0)==(mode=='success') and ('stop' in api.history)==stops and retirement['qualified'])
        rows.append({'mode':mode,'passed':passed,'exit_code':code,'api_history':api.history,'retirement':retirement})
        # Test-only authentication keys are not reusable operational credentials.
        # Keep all source/evidence bytes; no trace data was collected.
    guard_root=args.output/'protocol-guards';configuration(guard_root);value=t.config(guard_root)
    checks={}
    t.emit(guard_root,'start',{'identity':{'pid':123}},value)
    checks['signed_roundtrip']=t.receive(guard_root,'start',value)['payload']=={'identity':{'pid':123}}
    changed=dict(value);changed['_sha256']='f'*64
    try:t.receive(guard_root,'start',changed);checks['replay_rejected']=False
    except ValueError:checks['replay_rejected']=True
    (guard_root/'stop.json').write_text('{',encoding='utf-8')
    checks['partial_not_accepted']=t.receive(guard_root,'stop',value) is None
    calls=[];events=[]
    class BrokenCapture:
        def start(self):raise RuntimeError('simulated arming failure')
    def original(endpoint,operation,*a,**kw):calls.append(operation);return 'original-result'
    wrapped=t.wrap_transition(original,BrokenCapture(),events)
    checks['arm_failure_keeps_cleanup']=wrapped(None,'retire-invocation')=='original-result' and calls==['retire-invocation'] and bool(events[0]['error'])
    wrapped(None,'retire-invocation')
    checks['no_second_arm']=len(events)==1 and len(calls)==2
    def original_error(*a,**kw):raise ValueError('original cleanup failure')
    try:t.wrap_transition(original_error,BrokenCapture(),[])(None,'retire-invocation');checks['original_error_preserved']=False
    except ValueError as exc:checks['original_error_preserved']=str(exc)=='original cleanup failure'
    result={'passed':all(r['passed'] for r in rows) and all(checks.values()),'cases':rows,'checks':checks,
        'sources':bindings,'model_calls':0,'etw_apis_simulated':True,'real_owned_workers':True,'live_trace_coverage':False}
    t.save(args.output/'receipt.json',result)
    print(json.dumps({'passed':result['passed'],'cases':[(r['mode'],r['passed']) for r in rows],'checks':checks},indent=2))
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
