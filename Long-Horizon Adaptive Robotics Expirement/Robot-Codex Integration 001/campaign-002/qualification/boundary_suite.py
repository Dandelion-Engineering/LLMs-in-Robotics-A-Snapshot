"""Queued no-model requalification of the unchanged boundary and repaired relay.

Uses only the original synthetic adapter. No simulator, app-server model turn,
credential handoff, or Robot-Codex inference is launched by this runner.
"""
from __future__ import annotations
import argparse
import asyncio
import base64
import hashlib
import importlib.util
import json
import shlex
from pathlib import Path
import subprocess
import sys
import time
import traceback
from unittest.mock import patch

CAMPAIGN = Path(__file__).resolve().parents[1]
INTEGRATION = CAMPAIGN.parent
REPO = INTEGRATION.parents[1]
HARNESS = CAMPAIGN/'harness'
sys.path.insert(0,str(HARNESS))
spec = importlib.util.spec_from_file_location('campaign002_boundary_runtime',HARNESS/'runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


GUEST_SOURCE = r'''
import hashlib,json,pathlib,sys,urllib.request,urllib.error
endpoint=json.loads(pathlib.Path('/workspace/live/endpoint.json').read_text())
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
rows={};checks={}
def call(label,method,path,payload=None,token=None):
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request(endpoint['url']+path,data=data,method=method,
        headers={'X-Robot-Capability':endpoint['capability'] if token is None else token,
                 'Content-Type':'application/json'})
    try:response=opener.open(req,timeout=8)
    except urllib.error.HTTPError as error:response=error
    with response:
        result={'status':response.code,'body':json.load(response)}
    rows[label]=result
    return result
def envelope(state,rid,action=None):
    body={name:state[name] for name in ('authority_epoch','order_version','observation_sequence')}
    body['request_id']=rid
    if action is not None:body['action']=action
    return body
phase=sys.argv[1]
state=call('initial_status','GET','/status')['body']
if phase=='control':
    wrong=call('wrong_token','GET','/status',token='deliberately-invalid')
    checks['wrong_token_denied']=wrong['status']==403
    operator=call('operator_route','GET','/operator/status')
    checks['operator_route_denied']=operator['status']==403
    note='Synthetic Campaign 002 boundary qualification continuity.\n'
    first=call('continuity_commit','POST','/continuity',{'content':note})
    local=pathlib.Path('/workspace/Continuity.md').read_bytes()
    checks['continuity_committed_and_mirrored']=(first['status']==200 and first['body'].get('ok') is True
        and first['body'].get('sha256')==hashlib.sha256(local).hexdigest() and local==note.encode())
    over=call('oversize_continuity','POST','/continuity',{'content':'x'*32769})
    checks['oversize_note_denied_and_prior_preserved']=(over['status'] in (400,413)
        and pathlib.Path('/workspace/Continuity.md').read_bytes()==local)
    stale=envelope(state,'boundary-stale',{'operation':'transport','part_id':'A1','destination':'parking1'})
    stale['authority_epoch']-=1
    bad=call('stale_command','POST','/command',stale)
    checks['stale_command_rejected']=(bad['status']==200 and bad['body'].get('command',{}).get('status')=='rejected'
        and bad['body']['command'].get('error',{}).get('code')=='stale_authority')
    body=envelope(state,'boundary-valid',{'operation':'transport','part_id':'A1','destination':'parking1'})
    valid=call('valid_command','POST','/command',body)
    repeat=call('duplicate_command','POST','/command',body)
    checks['valid_command_accepted']=valid['status']==200 and valid['body'].get('command',{}).get('status')=='accepted'
    checks['duplicate_receipt_stable']=(repeat['status']==200 and repeat['body'].get('duplicate') is True
        and repeat['body'].get('command')==valid['body'].get('command'))
    rows['continuity_bytes_sha256']=hashlib.sha256(local).hexdigest()
elif phase=='handback':
    before=pathlib.Path('/workspace/Continuity.md').read_bytes()
    returned=call('handback','POST','/handback',{**envelope(state,'boundary-handback'),'reason':'Synthetic completed dispatch and public observation only'})
    checks['handback_accepted']=(returned['status']==200 and returned['body'].get('owner')=='conventional'
        and returned['body'].get('command',{}).get('status')=='completed')
    late=call('late_continuity','POST','/continuity',{'content':'must never commit'})
    checks['late_continuity_denied']=late['status']==403 and late['body'].get('ok') is False
    status=call('late_status','GET','/status')
    checks['late_read_denied']=status['status']==403
    checks['continuity_unchanged']=pathlib.Path('/workspace/Continuity.md').read_bytes()==before
else:raise SystemExit('unknown fixed phase')
result={'phase':phase,'checks':checks,'receipts':rows}
pathlib.Path('/workspace/notes/boundary-'+phase+'.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result),flush=True)
raise SystemExit(0 if checks and all(value is True for value in checks.values()) else 1)
'''


def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:
        json.dump(value,stream,indent=2);stream.write('\n');stream.flush()
        import os
        os.fsync(stream.fileno())


def require(condition,message):
    if not condition:raise RuntimeError(message)


def sources():
    roots=[HARNESS,INTEGRATION/'host',INTEGRATION/'readiness-session-10/boundary',
           INTEGRATION/'readiness-session-10/orchestrator',INTEGRATION/'isolation-session-9/wsl',
           INTEGRATION/'runtime-template',INTEGRATION/'smoke-template',CAMPAIGN/'assessment']
    paths={Path(__file__).resolve(),Path(__file__).with_name('test_boundary_suite.py')}
    for root in roots:
        paths.update(p for p in root.rglob('*') if p.is_file() and p.suffix in ('.py','.md'))
    paths.add(REPO/'Robot Agent Filesystem v0.1/workspace/RobotAgentPrompt.md')
    return {p.relative_to(REPO).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def process_receipt(folder,argv,completed,started,error=None,redact=lambda value:value):
    folder.mkdir(parents=True,exist_ok=False)
    def decoded(value):return value.decode('utf-8',errors='replace') if isinstance(value,bytes) else (value or '')
    stdout=redact(decoded(getattr(completed,'stdout','')))
    stderr=redact(decoded(getattr(completed,'stderr','')))
    (folder/'stdout.txt').write_text(stdout,encoding='utf-8')
    (folder/'stderr.txt').write_text(stderr,encoding='utf-8')
    receipt={'argv':argv,'started_wall_unix_s':started,'finished_wall_unix_s':time.time(),
             'exit_code':getattr(completed,'returncode',None),'error':error,
             'stdout_sha256':hashlib.sha256((folder/'stdout.txt').read_bytes()).hexdigest(),
             'stderr_sha256':hashlib.sha256((folder/'stderr.txt').read_bytes()).hexdigest()}
    save(folder/'execution.json',receipt)
    return receipt


def unit_suites(output):
    targets=[('protected-host',INTEGRATION/'host','test_*.py'),
             ('robot-client',INTEGRATION/'client-tests','test_*.py'),
             ('transport',HARNESS,'test_transport.py'),('timing',HARNESS,'test_timing.py'),
             ('journal-instrumentation',HARNESS,'test_instrumented_journal.py'),
             ('recorder-instrumentation',HARNESS,'test_instrumented_recorder.py'),
             ('gc-policy',HARNESS,'test_gc_diagnostics.py'),('host-memory',HARNESS,'test_memory_guard.py'),
             ('executor-capture-reader',CAMPAIGN/'assessment','test_retained_reads.py'),
             ('qualification-protocol',CAMPAIGN/'qualification','test_boundary_suite.py'),
             ('boundary-policy-windows',INTEGRATION/'readiness-session-10/boundary','test_boundary.py')]
    rows=[]
    for name,path,pattern in targets:
        require(path.is_dir() and list(path.glob(pattern)),name+' test sources are missing')
        argv=[sys.executable,'-X','utf8','-B','-m','unittest','discover','-s',str(path),'-p',pattern,'-v']
        started=time.time()
        try:completed=subprocess.run(argv,cwd=REPO,capture_output=True,text=True,encoding='utf-8',timeout=180,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as error:
            process_receipt(output/name,argv,error,started,{'type':type(error).__name__,'message':str(error)})
            raise
        row=process_receipt(output/name,argv,completed,started)
        row['name']=name;rows.append(row)
    require(all(row['exit_code']==0 for row in rows),'A bounded unit suite failed; WSL qualification not entered')
    return rows


async def guest_phase(url,fixture,phase):
    from websockets.asyncio.client import connect
    process_id='boundary-'+phase
    events=[];counter=0
    async with connect(url,max_size=2*1024*1024,open_timeout=10,close_timeout=3,origin=None) as ws:
        async def call(method,params):
            nonlocal counter
            counter+=1;rid=counter
            await ws.send(json.dumps({'id':rid,'method':method,'params':params}))
            while True:
                event=json.loads(await asyncio.wait_for(ws.recv(),20))
                events.append(event)
                if event.get('id')==rid:
                    require('error' not in event,'Executor rejected '+method)
                    return event
        await call('initialize',{'clientName':'campaign002-fixed-boundary-qualification'})
        await ws.send(json.dumps({'method':'initialized','params':{}}))
        await call('process/start',{'processId':process_id,
            'argv':['/usr/bin/python3','-I','-B','-c',GUEST_SOURCE,phase],
            'metadata':{'toolCallId':'qualification-'+phase},
            'cwd':'file:///workspace','env':{'PATH':'/usr/bin:/bin','HOME':'/workspace'},
            'tty':False,'arg0':None,'sandbox':None})
        def own(event):return event.get('params',{}).get('processId')==process_id
        while not any(event.get('method')=='process/closed' and own(event) for event in events):
            events.append(json.loads(await asyncio.wait_for(ws.recv(),30)))
    stdout=b''.join(base64.b64decode(e['params']['chunk']) for e in events
                    if e.get('method')=='process/output' and own(e) and e['params']['stream']=='stdout')
    stderr=b''.join(base64.b64decode(e['params']['chunk']) for e in events
                    if e.get('method')=='process/output' and own(e) and e['params']['stream']=='stderr')
    exits=[e['params'] for e in events if e.get('method')=='process/exited' and own(e)]
    save(fixture.evidence/('guest-'+phase+'-execution.json'),{'process_id':process_id,'exit_receipts':exits,
        'stdout':fixture.redact(stdout.decode()),'stderr':fixture.redact(stderr.decode()),
        'source_sha256':hashlib.sha256(GUEST_SOURCE.encode()).hexdigest()})
    require(len(exits)==1 and exits[0].get('exitCode')==0,'Guest '+phase+' process did not exit successfully')
    result=json.loads(stdout)
    require(result.get('checks') and all(value is True for value in result['checks'].values()),'Guest '+phase+' check failed')
    return result


async def exercise_executor(fixture):
    from lifecycle_probe import exercise_disconnect
    from test_supervisor import packet
    async def callback(url):
        await runtime.prior.executor_probe(url,fixture)
        await asyncio.wait_for(fixture.bridge_idle.wait(),20)
        await exercise_disconnect(url,fixture.evidence,distribution=runtime.DISTRO)
        await asyncio.wait_for(fixture.bridge_idle.wait(),20)
        control=await guest_phase(url,fixture,'control')
        await asyncio.wait_for(fixture.bridge_idle.wait(),20)
        require(len(fixture.adapter.submissions)==1,'Valid request was not dispatched exactly once')
        require(fixture.host.commands['boundary-stale']['status']=='rejected','Stale command was not retained as rejected')
        note=fixture.journal.read_continuity()
        require(note['sha256']==control['receipts']['continuity_bytes_sha256'],'Protected and guest continuity differ')
        # Explicit synthetic completion, using the original FakeAdapter test
        # semantics. This is never reported as a physical recovery observation.
        fixture.adapter.active=False
        fixture.host.native_feedback({'request_id':'boundary-valid','status':'completed'})
        fixture.adapter.now=1.2
        fixture.host.update_observation(packet('parking1',sequence=2,sim=1.2))
        save(fixture.evidence/'synthetic-completion.json',{'scope':'FakeAdapter only; no physical simulation',
            'adapter_submissions':fixture.adapter.submissions,'command':fixture.host.commands['boundary-valid']})
        handback=await guest_phase(url,fixture,'handback')
        await asyncio.wait_for(fixture.bridge_idle.wait(),20)
        status,body=runtime.request(fixture.endpoint['url'],fixture.token,'GET','/status')
        save(fixture.evidence/'protected-old-token-denial.json',{'status':status,'body':body,
             'origin':'direct protected host; separate from local revocation fence'})
        require(status==403,'Protected host did not reject original capability after handback')
        require(fixture.journal.read_continuity()==note,'Late denied continuity changed protected note')
        require(len(fixture.adapter.submissions)==1,'Later phase dispatched another synthetic command')
        return {'control':control,'handback':handback,'protected_continuity':note,'submissions':len(fixture.adapter.submissions)}
    # bridge_executor deliberately owns the namespace lifecycle and evidence.
    result={}
    async def retain(url):result.update(await callback(url))
    await runtime.captured_executor.bridge_executor(fixture,retain)
    # Authenticate actual WSL messages against the independent receiver's exact
    # bytes. The later model smoke additionally joins metadata tool-call IDs.
    spec=importlib.util.spec_from_file_location('boundary_capture_reader',CAMPAIGN/'assessment/retained_reads.py')
    reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    captures=[reader.load_capture(path) for path in sorted(fixture.evidence.glob('executor-*-capture.jsonl'))]
    require(len(captures)==4,'Four trusted executor capture connections required')
    receipts=[]
    for phase in ('control','handback'):
        target='boundary-'+phase
        rows=[r for records,delivered,receipt in captures for r in records
              if r.get('kind')=='response' and r['sequence'] in delivered
              and r['message'].get('method')=='process/output'
              and r['message'].get('params',{}).get('processId')==target
              and r['message']['params'].get('stream')=='stdout']
        actual=b''.join(base64.b64decode(r['message']['params']['chunk'],validate=True) for r in rows)
        expected=json.loads((fixture.evidence/('guest-'+phase+'-execution.json')).read_text())['stdout'].encode()
        require(actual==expected,'Captured executor stdout differs from independent receiver bytes: '+phase)
        receipts.append({'phase':phase,'process_id':target,'stdout_bytes':len(actual),
                         'stdout_sha256':hashlib.sha256(actual).hexdigest(),'receiver_exact_match':True})
    result['executor_capture']={'connections':[receipt for records,delivered,receipt in captures],
                                'guest_roundtrips':receipts,'verified':True}
    synthetic_completions=[]
    for phase in ('control','handback'):
        actual=json.loads((fixture.evidence/('guest-'+phase+'-execution.json')).read_text())
        synthetic_completions.append({'method':'item/completed','params':{'item':{
            'type':'commandExecution','id':'qualification-'+phase,'exitCode':actual['exit_receipts'][0]['exitCode'],
            'command':shlex.join(['/usr/bin/python3','-I','-B','-c',GUEST_SOURCE,phase]),
            'aggregatedOutput':actual['stdout']}}})
    authenticated,audit=reader.authenticated_commands(fixture.evidence,synthetic_completions)
    require(audit['verified'] and len(authenticated)==2,
            'Actual executor sequence/start/exit/closed protocol failed independent reader qualification')
    result['executor_capture']['reader_protocol_checks']={item['id']:item['executor_provenance'] for item in authenticated}
    result['executor_capture']['protocol_scope']='Fixed nonmodel caller IDs and independent receiver; model metadata linkage still requires actual smoke'
    return result


def qualify(output):
    output.mkdir(parents=True,exist_ok=False)
    binding=sources();save(output/'source-binding-before.json',binding)
    result={'schema':'campaign002-boundary-suite-1','model_calls':0,'physical_simulation':False,
            'checks':{},'started_wall_unix_s':time.time()}
    fixture=None;before=None
    try:
        result['unit_suites']=unit_suites(output/'unit-tests')
        result['checks']['unit_suites_passed']=all(row['exit_code']==0 for row in result['unit_suites'])
        # Exercise the complete original Linux boundary test set, including
        # sealed source, detached descendants and continuity symlink controls.
        argv=['wsl.exe','-d',runtime.DISTRO,'--','/usr/bin/python3','-B','-m','unittest','discover',
              '-s',runtime.prior.wsl_path(runtime.BOUNDARY),'-p','test_boundary.py','-v']
        started=time.time()
        completed=subprocess.run(argv,cwd=REPO,capture_output=True,text=True,encoding='utf-8',timeout=180,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        receipt=process_receipt(output/'linux-boundary-tests',argv,completed,started)
        require(receipt['exit_code']==0,'Linux boundary tests failed')
        result['checks']['linux_boundary_tests_passed']=receipt['exit_code']==0
        fixture=runtime.Runtime.__new__(runtime.Runtime)
        fixture.__init__(output/'runtime',runtime.template('physical'))
        native_run=subprocess.run;canary_rows=[]
        def record_canary(*args,**kwargs):
            started=time.time();argv=list(args[0])
            completed=native_run(*args,**kwargs)
            canary_rows.append(process_receipt(output/('qualify-process-'+str(len(canary_rows)+1)),argv,completed,started,
                                               redact=fixture.redact))
            return completed
        # Transparent receipt capture: execute the real Runtime.qualify code,
        # returning each untouched CompletedProcess to its normal gates.
        with patch.object(runtime.subprocess,'run',side_effect=record_canary):fixture.qualify()
        result['canary_processes']=canary_rows
        canary=json.loads((fixture.evidence/'canary-stdout.json').read_text())
        codecanary=json.loads((fixture.evidence/'codehost-canary-stdout.json').read_text())
        result['checks']['runtime_canaries_passed']=(len(canary_rows)==2 and all(r['exit_code']==0 for r in canary_rows)
            and canary.get('qualified') is True and codecanary.get('host_qualified') is True)
        require(result['checks']['runtime_canaries_passed'],'Recorded Runtime canary checks failed')
        result['control']=asyncio.run(exercise_executor(fixture))
        result['checks']['trusted_executor_capture_roundtrip']=result['control']['executor_capture']['verified']
        result['checks']['protected_control_continuity_and_handback_passed']=all(
            value is True for phase in ('control','handback') for value in result['control'][phase]['checks'].values())
        from codehost_bridge import probe,run
        asyncio.run(run(fixture,lambda url:probe(url,fixture,reset=True)))
        codeprobe=json.loads((fixture.evidence/'codehost-http2-probe.json').read_text())
        result['checks']['codehost_transport_probe_passed']=codeprobe.get('qualified') is True
        retirements={path.name:json.loads(path.read_text()) for path in fixture.evidence.glob('*-retirement.json')}
        result['retirement_receipts']={name:value.get('qualified') for name,value in retirements.items()}
        result['checks']['all_five_namespaces_retired']=(len(retirements)==5 and all(r.get('qualified') is True for r in retirements.values()))
        disconnect=json.loads((fixture.evidence/'lifecycle-disconnect.json').read_text())
        result['checks']['detached_descendants_retired']=disconnect.get('qualified') is True and disconnect.get('positive_control_passed') is True
        result['checks']['transport_abort_unset']=not fixture.abort_event.is_set()
        before=fixture.export('runtime-before-close')
    except Exception as error:
        result['error']={'type':type(error).__name__,'message':str(error),'traceback':traceback.format_exc()}
    finally:
        if fixture is not None:
            try:
                if before is None and hasattr(fixture,'workspace'):before=fixture.export('runtime-before-close')
            except Exception as error:result['pre_close_export_error']=str(error)
            try:result['checks']['runtime_cleanup_clean']=fixture.close() is True
            except Exception as error:result['cleanup_error']=str(error)
            try:
                after=fixture.export('runtime-after-close')
                result['checks']['durable_retention_verified']=before is not None and before==after
            except Exception as error:result['post_close_export_error']=str(error)
        after_sources=sources();save(output/'source-binding-after.json',after_sources)
        result['checks']['sources_unchanged']=binding==after_sources
        required={'unit_suites_passed','linux_boundary_tests_passed','runtime_canaries_passed',
                  'protected_control_continuity_and_handback_passed','codehost_transport_probe_passed',
                  'all_five_namespaces_retired','detached_descendants_retired','transport_abort_unset','trusted_executor_capture_roundtrip',
                  'runtime_cleanup_clean','durable_retention_verified','sources_unchanged'}
        result['qualified']=not result.get('error') and set(result['checks'])==required and all(result['checks'].values())
        result['finished_wall_unix_s']=time.time()
        result['scope']='Synthetic native/WSL infrastructure only; no model recovery performance or complete campaign admission claim'
        save(output/'suite-result.json',result)
    print(json.dumps({'qualified':result['qualified'],'model_calls':0,'output':str(output)}))
    return 0 if result['qualified'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output','--evidence',dest='output',type=Path,required=True)
    args=parser.parse_args()
    raise SystemExit(qualify(args.output))
