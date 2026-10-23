"""One queued development smoke sequence or one unretried recovery pilot."""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid
from runtime import Runtime, template, write_json, request, INTEGRATION, SESSION

def operator(endpoint,method,path,body=None):
    status,value=request(endpoint['url'],endpoint['capability'],method,'/operator/'+path,body,operator=True)
    if status!=200 or not value.get('ok'):raise RuntimeError('Operator '+path+' failed: '+str(value))
    return value

def transition(endpoint,operation,invocation_id=None,reason='readiness qualification'):
    state=operator(endpoint,'GET','status')
    body={'request_id':'operator-'+operation+'-'+uuid.uuid4().hex,'authority_epoch':state['authority_epoch'],'reason':reason}
    if invocation_id:body['invocation_id']=invocation_id
    value=operator(endpoint,'POST',operation,body)
    if value.get('command',{}).get('status')!='completed':raise RuntimeError('Lifecycle rejected: '+str(value))
    return value

def public_files(state,kind):
    files=template('physical')
    files.update({'live/state.json':json.dumps(state),'live/activation.json':json.dumps(state['activation']),
                  'live/observations/latest.json':json.dumps(state['packet'])})
    files['Tasks.md']=(SESSION/'templates'/('Tasks-'+kind+'.md')).read_text(encoding='utf-8')
    files['Tools.md']=(SESSION/'templates/Tools.md').read_text(encoding='utf-8')
    files['AGENTS.md']=(SESSION/'templates/AGENTS.md').read_text(encoding='utf-8')
    # Do not accidentally expose staging examples as tested model programs.
    files.pop('programs/observe_once.py',None)
    return files

def run_invocation(kind,root,control,host_workspace,prior_snapshot=None):
    invocation_id=kind+'-'+uuid.uuid4().hex[:12]
    started=transition(control,'start-invocation',invocation_id)
    runtime=None; watchdog=None; result={'kind':kind,'invocation_id':invocation_id,'success':False}
    interrupted=threading.Event();finished=threading.Event();watch_errors=[]
    old_endpoint=started['endpoint']
    try:
        files=public_files(operator(control,'GET','status'),kind)
        note=operator(control,'GET','continuity')
        if hashlib.sha256(note['content'].encode()).hexdigest()!=note['sha256']:raise RuntimeError('Protected continuity hash mismatch')
        files['Continuity.md']=note['content']
        runtime=Runtime.__new__(Runtime)
        runtime.__init__(root,files,old_endpoint,host_workspace,prior_snapshot)
        runtime.tokens.append(control['capability'])
        runtime.qualify()
        if kind=='interrupt':
            def watch():
                while not finished.wait(.1):
                    try:
                        state=operator(control,'GET','status')
                        matching=[c for c in state.get('commands_recent',[]) if c.get('request_id')=='smoke-open-001' and c.get('kind')=='command']
                        if matching and matching[-1].get('status')!='rejected':
                            result['command_at_interruption']=matching[-1]
                            result['retirement_transition']=transition(control,'retire-invocation',invocation_id,'Injected interruption after actual model action receipt')
                            interrupted.set();runtime.abort_event.set();return
                    except Exception as error:
                        watch_errors.append(str(error));runtime.abort_event.set();return
            watchdog=threading.Thread(target=watch,daemon=True);watchdog.start()
        asyncio.run(runtime.model(timeout=600))
        result['all_namespaces_retired']=True
        result['client']=json.loads((root/'client/result.json').read_text())
        result['success']=result['client'].get('success',False)
    except Exception as error:
        result['error']=str(error)
        if (root/'client/result.json').exists():result['client']=json.loads((root/'client/result.json').read_text())
    finally:
        finished.set()
        if watchdog:watchdog.join(timeout=10)
        result['injected_interruption']=interrupted.is_set()
        result['watchdog_errors']=watch_errors
        try:
            state=operator(control,'GET','status')
            if state.get('invocation',{}).get('state')!='retired':
                result['retirement_transition']=transition(control,'retire-invocation',invocation_id)
        except Exception as error:result['retirement_error']=str(error)
        try:
            status,body=request(old_endpoint['url'],old_endpoint['capability'],'GET','/status')
            result['old_token_denied_after_retirement']=status==403
        except Exception as error:result['old_token_check_error']=str(error)
        if runtime:
            # Stop mirror before byte-identity checks; robot physics continues.
            runtime.stop.set()
            if runtime.mirror_thread:runtime.mirror_thread.join(timeout=12)
            try:before=runtime.export('runtime-before-close')
            except Exception as error:result['export_error']=str(error);before=None
            try:result['cleanup_clean']=runtime.close()
            except Exception as error:result['cleanup_clean']=False;result['cleanup_error']=str(error)
            try:
                after=runtime.export('runtime-after-close')
                result['durable_retention_verified']=before==after
            except Exception as error:result['post_close_export_error']=str(error)
        write_json(root/'stage-result.json',result)
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--host-evidence',type=Path,required=True)
    parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--mode',choices=['smoke','pilot'],required=True)
    args=parser.parse_args()
    args.evidence.mkdir(parents=True,exist_ok=False)
    args.workspace.mkdir(parents=True,exist_ok=False)
    stdout=(args.evidence/'host.stdout').open('w',encoding='utf-8')
    stderr=(args.evidence/'host.stderr').open('w',encoding='utf-8')
    host=subprocess.Popen([sys.executable,'-X','utf8','-B',str(INTEGRATION/'host/run_host.py'),
        '--manifest',str(args.manifest),'--evidence',str(args.host_evidence),'--runtime-workspace',str(args.workspace)],
        stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
    control=None;result={'mode':args.mode,'stages':[],'orchestrator_completed':False}
    try:
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            if host.poll() is not None:raise RuntimeError('Host exited before activation')
            endpoint_path=args.host_evidence/'operator-endpoint.json'
            if endpoint_path.exists():
                control=json.loads(endpoint_path.read_text())
                state=operator(control,'GET','status')
                if state['owner']=='robot' and not state.get('active_command'):break
            time.sleep(.2)
        else:raise RuntimeError('Host activation deadline')
        if args.mode=='smoke':
            first=run_invocation('interrupt',args.evidence/'interrupt',control,args.workspace)
            result['stages'].append(first)
            if not(first.get('injected_interruption') and first.get('durable_retention_verified') and first.get('old_token_denied_after_retirement') and first.get('all_namespaces_retired') and first.get('cleanup_clean')):
                raise RuntimeError('Interruption stage failed its gate; restart not attempted')
            deadline=time.monotonic()+20
            while operator(control,'GET','status').get('active_command'):
                if time.monotonic()>deadline:raise RuntimeError('Cancellation did not settle')
                time.sleep(.1)
            second=run_invocation('resume',args.evidence/'resume',control,args.workspace,args.evidence/'interrupt/runtime-after-close.json')
            result['stages'].append(second)
        else:
            stage=run_invocation('pilot',args.evidence/'pilot',control,args.workspace)
            result['stages'].append(stage)
            # After handback, allow the conventional controller its bounded
            # completion window; one pilot only, no restart or adaptive retry.
            deadline=time.monotonic()+150
            while host.poll() is None and time.monotonic()<deadline:
                try:
                    state=operator(control,'GET','status')
                except (OSError, RuntimeError):
                    try:host.wait(timeout=5)
                    except subprocess.TimeoutExpired:raise
                    terminal_path=args.host_evidence/'result.json'
                    if host.returncode==0 and terminal_path.exists():
                        terminal=json.loads(terminal_path.read_text())
                        if terminal.get('execution_completed') and terminal.get('terminal')=='task_success':break
                    raise
                if state['owner']!='conventional':break
                time.sleep(.5)
        result['orchestrator_completed']=True
    except Exception as error:
        result['error']=str(error)
    finally:
        if control and host.poll() is None:
            try:transition(control,'stop',reason='Bounded readiness '+args.mode+' complete')
            except Exception as error:result['stop_error']=str(error)
        try:host.wait(timeout=25)
        except subprocess.TimeoutExpired:host.terminate();host.wait(timeout=10);result['forced_host_exit']=True
        stdout.close();stderr.close()
        result['host_exit_code']=host.returncode
        write_json(args.evidence/'sequence-result.json',result)
    print(json.dumps({'orchestrator_completed':result['orchestrator_completed'],'error':result.get('error'),'stages':len(result['stages'])}))
    # A diagnostic can complete while the model/robot fails. The separate
    # assessment determines qualification; exit0 authenticates artifact creation.
    return 0 if result['orchestrator_completed'] and host.returncode==0 else 1

if __name__=='__main__':raise SystemExit(main())
