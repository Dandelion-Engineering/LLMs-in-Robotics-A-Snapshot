"""Exercise native-wrapper failure paths without WSL, ETW, queue or models."""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
WRAPPER=HERE.parent/'single-interrupt-diagnostic-v5'
sys.path.insert(0,str(WRAPPER))
import common
import trace_control


def load(name):
    spec=importlib.util.spec_from_file_location('diagnostic_test_'+name,WRAPPER/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def case(root,mode,runner):
    root.mkdir();calls=[];host_created=[];captures=[]
    args=SimpleNamespace(manifest=root/'manifest.json',snapshot=root/'snapshot.json',
        evidence=root/'evidence',host_evidence=root/'host',workspace=root/'workspace',
        observer_config_sha256='a'*64)
    class Host:
        returncode=None
        def poll(self): return self.returncode
        def wait(self,timeout):
            calls.append(('wait',timeout))
            if mode=='forced-host' and timeout==25: raise subprocess.TimeoutExpired('fake',timeout)
            self.returncode=0;return 0
        def terminate(self): calls.append(('terminate',))
    def popen(*a,**kw):
        host=Host();host_created.append(host);args.host_evidence.mkdir()
        (args.host_evidence/'operator-endpoint.json').write_text('{}',encoding='utf-8')
        return host
    class Capture:
        def __init__(self,**kw):
            calls.append(('capture',kw['expected_sha']))
            if mode=='not-ready': raise RuntimeError('simulated unavailable observer')
            self.armed=False;self.events=[];captures.append(self)
        def start(self):
            calls.append(('arm',))
            if mode=='arm-failed': raise RuntimeError('simulated arm failure')
            self.armed=True
        def finish(self):
            calls.append(('finish',))
            if mode=='finish-failed': raise RuntimeError('simulated stop failure')
            return {'collection_completed':True}
    def transition(endpoint,operation,*a,**kw):
        calls.append(('transition',operation))
        if mode=='stop-failed' and operation=='stop': raise RuntimeError('simulated host stop failure')
        return {'ok':True}
    physical=SimpleNamespace(transition=transition,write_json=common.save,
        operator=lambda *a: {'owner':'robot','active_command':None})
    def invocation(operation,*a):
        calls.append(('invocation',operation))
        physical.transition({},'retire-invocation')
        if mode=='double-retire': physical.transition({},'retire-invocation')
        calls.append(('original-cleanup',))
        if mode=='runtime-failed': raise RuntimeError('simulated original runtime failure')
        return {'injected_interruption':True,'durable_retention_verified':True,
            'old_token_denied_after_retirement':True,'all_namespaces_retired':True,
            'cleanup_clean':mode!='stage-failed'}
    physical.run_invocation=invocation
    with contextlib.ExitStack() as stack:
        for name,value in [('validate',lambda *a:None),('output_paths',lambda *a:None),('load_physical',lambda:physical)]:
            stack.enter_context(patch.object(common,name,value))
        stack.enter_context(patch.object(runner.trace_control,'Client',Capture))
        stack.enter_context(patch.object(runner.subprocess,'Popen',popen))
        stack.enter_context(patch.object(runner.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=0,stdout='{"ready":true}')))
        with contextlib.redirect_stdout(io.StringIO()): code=runner.execute(args)
    result=common.read(args.evidence/'sequence-result.json')
    success=mode in {'success','double-retire','forced-host','stop-failed'}
    checks={'expected_exit':code==(0 if success else 1),'transition_restored':physical.transition is transition,
        'never_resume':result['resume_attempted'] is False,'unknown_not_scored':result['task_outcome']=='unknown' and not result['scorable'],
        'single_invocation':sum(c[0]=='invocation' for c in calls)==(0 if mode=='not-ready' else 1),
        'single_arm':sum(c[0]=='arm' for c in calls)==(0 if mode=='not-ready' else 1),
        'original_cleanup':('original-cleanup',) in calls if mode!='not-ready' else not host_created,
        'host_wait_preserved':('wait',25) in calls if mode!='not-ready' else not host_created,
        'capture_bound':('capture','a'*64) in calls,
        'finish_attempted':sum(c[0]=='finish' for c in calls)==(0 if mode=='not-ready' else 1)}
    if mode=='arm-failed': checks['arm_failure_recorded']=bool(result['trace_arming'][0]['error'])
    if mode=='finish-failed': checks['finish_failure_recorded']=bool(result.get('trace_error'))
    if mode=='forced-host': checks['original_forced_exit_path']=('terminate',) in calls and ('wait',10) in calls
    return {'mode':mode,'passed':all(checks.values()),'checks':checks,'calls':calls,'exit_code':code}


def launch_checks(root,launcher):
    checks={};digest='a'*64
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(common,'validate',lambda *a:None))
        stack.enter_context(patch.object(common,'output_paths',lambda *a:None))
        stack.enter_context(patch.object(common,'RECORDS',root/'never-created'))
        stack.enter_context(patch.object(launcher,'observer_ready',side_effect=RuntimeError('not ready')))
        with patch.object(launcher.subprocess,'Popen') as proc,patch.object(launcher.subprocess,'check_output') as queue:
            try: launcher.launch(root/'m',root/'s',digest)
            except RuntimeError: pass
            checks['no_ready_no_intent_guard_or_queue']=not common.RECORDS.exists() and not proc.called and not queue.called
    argv=common.runner_argv(root/'m',root/'s',digest)
    checks['queue_argv_binds_observer']=argv[-2:]==['--observer-config-sha256',digest]
    for value in ('', 'a'*63,'A'*64,'../config','f'*64+';'):
        try: common.control_digest(value);checks['bad_digest_'+repr(value)]=False
        except ValueError: checks['bad_digest_'+repr(value)]=True
    # Authenticate/configure before model work: mismatched actual file must fail.
    bad=root/'bad-config';bad.mkdir();(bad/'config.json').write_text('{}',encoding='utf-8')
    try: trace_control.Client(root=bad,ready_timeout=.01,expected_sha=digest);checks['wrong_config_rejected']=False
    except ValueError: checks['wrong_config_rejected']=True
    return checks


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    root=args.output.resolve();root.mkdir();(root/'sources').mkdir()
    sources=sorted(WRAPPER.glob('*.py'))+[Path(__file__).resolve(),HERE/'trace_control.py']
    bindings=[]
    for i,path in enumerate(sources):
        raw=path.read_bytes();copy=root/'sources'/f'{i:02d}-{path.name}';copy.write_bytes(raw)
        bindings.append({'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'copy':str(copy)})
    runner=load('run');launcher=load('launch')
    rows=[case(root/mode,mode,runner) for mode in ('success','not-ready','arm-failed','finish-failed',
        'runtime-failed','stage-failed','double-retire','forced-host','stop-failed')]
    checks=launch_checks(root,launcher)
    receipt={'passed':all(row['passed'] for row in rows) and all(checks.values()),'cases':rows,
        'checks':checks,'sources':bindings,'model_calls':0,'etw_calls':0,'queue_submissions':0,
        'external_processes_mocked':True}
    common.save(root/'receipt.json',receipt)
    print(json.dumps({'passed':receipt['passed'],'cases':[(r['mode'],r['passed']) for r in rows],'checks':checks},indent=2))
    return 0 if receipt['passed'] else 1


if __name__=='__main__': raise SystemExit(main())
