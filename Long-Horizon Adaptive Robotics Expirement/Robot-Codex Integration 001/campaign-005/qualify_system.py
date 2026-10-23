"""Operator-only deterministic three-session system witness. No model calls.

This file and the private contact witness are NEVER included in the guest mount.
"""
import argparse
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from types import SimpleNamespace
from common import HERE,REPO,inherited_paths,canonical,save,sha
inherited_paths()
from workspace_block import WorkspaceBlock,linux,wsl
from scheduler import Schedule
# Explicit load avoids the inherited modules named runtime/run_host.
from common import load_module
runtime=load_module('campaign005_runtime_system',HERE/'runtime.py')

def run(output,extended_envelope=False):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    result={'passed':False,'model_calls':0,'sessions':[],'stage_events':[]};block=guest=host=None;log=None
    try:
        from qualify_order_boundary import check as check_order_boundary
        result['order_boundary_checks']=check_order_boundary()
        from qualify_continuation import fixture,negative_tests
        result['continuation_negative_tests']=negative_tests()
        from qualify_stack import run as qualify_stack
        if qualify_stack(out/'stack')!=0:raise RuntimeError('Authority/image/terminal stack qualification failed')
        negative_root='/var/tmp/campaign005-negative-'+hashlib.sha256(str(out).encode('utf-8')).hexdigest()[:20]
        negative=json.loads(linux("import sys,json;sys.path.insert(0,sys.argv[1]);from journal_negative_checks import run;print(json.dumps(run(sys.argv[2])))",wsl(HERE),negative_root))
        save(out/'journal-negative-checks.json',negative)
        assert negative['passed'],negative
        manifest={'run_id':out.name,'seed':173,'noise_seed':33001,'schedule_seed':330031,'encounters':3,
                  'initial_order':Schedule(330031).current,'sim_cap_s':600,'wall_cap_s':700,'storage_cap_bytes':512*1024**2,'mode':'serve'}
        if extended_envelope:
            from runtime_limits import apply_limits
            manifest=apply_limits(manifest,'development')
        save(out/'manifest.json',manifest)
        log=(out/'host-console.log').open('wb')
        host=subprocess.Popen([sys.executable,'-X','utf8','-B',str(HERE/'apparatus.py'),'--manifest',str(out/'manifest.json'),
            '--evidence',str(out/'host'),'--runtime-workspace',str(out/'public')],stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
        end=time.monotonic()+90;endpoint_path=out/'host/operator-endpoint.json'
        while not endpoint_path.is_file():
            if host.poll() is not None:raise RuntimeError('Host exited during initialization')
            if time.monotonic()>end:raise RuntimeError('Host initialization deadline')
            time.sleep(.1)
        ep=json.loads(endpoint_path.read_text());url=ep['url'];token=ep['capability']
        def op(path,body=None):
            code,value=runtime.request(url,token,'GET' if body is None else 'POST','/operator/'+path,body,operator=True)
            if code!=200 or not value.get('ok') or value.get('command',{}).get('status')=='rejected':raise RuntimeError(str(value))
            return value
        def wait(predicate,timeout=90):
            stop=time.monotonic()+timeout
            while time.monotonic()<stop:
                if host.poll() is not None:raise RuntimeError('Host exited during deterministic episode')
                value=op('status')
                if predicate(value):return value
                time.sleep(.05)
            raise RuntimeError('Deterministic state deadline')
        block=WorkspaceBlock.__new__(WorkspaceBlock)
        from archive_location import PUBLIC_EXPORT_ROOT
        block.__init__(out/'workspace-block',runtime.template(),manifest['run_id'],os.environ['C005_REVISION_ID'],os.environ['C005_SOURCE_SNAPSHOT_SHA256'],archive_root=PUBLIC_EXPORT_ROOT)
        count=0
        while True:
            status=op('status');order=status['packet']['order']
            if order['kind']=='C-placement':
                status=wait(lambda s:s['owner']=='robot')
                if count==0:
                    result['safe_unresolved_fixtures']=[fixture(runtime,out,block,manifest,op,wait,i) for i in (1,2)]
                    status=op('status')
                count+=1;sid=f'deterministic-session-{count}'
                started=op('start-invocation',{'request_id':'start-'+sid,'authority_epoch':status['authority_epoch'],'invocation_id':sid})
                robot_ep=started['endpoint'];session_root=out/sid
                status=op('status');files=runtime.template()
                files.update({'live/state.json':json.dumps(status),'live/activation.json':json.dumps(status['activation']),
                              'live/observations/latest.json':json.dumps(status['packet'])})
                guest=runtime.Runtime.__new__(runtime.Runtime)
                guest.__init__(session_root,files,robot_ep,block,sid,host_workspace=out/'public')
                guest.qualify()
                async def executor_check(url):await runtime.prior.executor_probe(url,guest)
                asyncio.run(runtime.captured_executor.bridge_executor(guest,executor_check))
                # Independent fresh process sees the actual same mounted bytes.
                script="""import subprocess,sys,json
w,probe,n=sys.argv[1:];cmd=['bwrap','--unshare-all','--unshare-user','--disable-userns','--assert-userns-disabled','--die-with-parent','--new-session','--cap-drop','ALL','--clearenv','--setenv','PATH','/usr/bin:/bin','--setenv','HOME','/workspace','--ro-bind','/usr','/usr','--symlink','usr/bin','/bin','--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--ro-bind',w,'/workspace']
for area in ('notes','programs','.continuity'):cmd+=['--bind',w+'/'+area,'/workspace/'+area]
cmd+=['--ro-bind',probe,'/probe.py','--chdir','/workspace','--remount-ro','/','/usr/bin/python3','-I','-B','/probe.py',n]
p=subprocess.run(cmd,capture_output=True,text=True,timeout=20);print(p.stdout);assert p.returncode==0,p.stderr+p.stdout
"""
                probe=json.loads(linux(script,block.workspace,wsl(HERE/'fs_guest_probe.py'),count));save(session_root/'fresh-process.json',probe)
                before=block.checkpoint('before-physical-witness',op('status')['packet']['sim_time'])
                def robot(path,body=None):
                    code,value=runtime.request(robot_ep['url'],robot_ep['capability'],'GET' if body is None else 'POST',path,body)
                    if code!=200 or not value.get('ok') or value.get('command',{}).get('status')=='rejected':raise RuntimeError(str(value))
                    return value
                def envelope(rid,action=None):
                    s=wait(lambda v:v['observation_age_s']<=.2)
                    v={'request_id':rid,'authority_epoch':s['authority_epoch'],'order_version':s['order_version'],'observation_sequence':s['observation_sequence']}
                    if action is not None:v['action']=action
                    return v
                observed=robot('/observe',envelope('observe-'+sid))
                obs=observed['command']['request_id']
                wait(lambda s:op('command/'+obs)['command']['status']=='completed')
                events=[json.loads(x) for x in (out/'host/public-history.jsonl').read_text().splitlines()]
                image_event=next(e for e in reversed(events) if e['type']=='requested_image_available')
                from image_sensor import ImageSensor
                sensor=ImageSensor(out/'public',SimpleNamespace(events=events,root=out/'host'),manifest['run_id'],sid,robot_ep['authority_epoch'])
                sensor.bind('offline-'+sid,'offline-turn-'+sid)
                image=sensor.call({'threadId':sensor.thread_id,'turnId':sensor.turn_id,'callId':'image-'+sid,'tool':'robot_image','arguments':{'observation_sequence':image_event['payload']['observation_sequence']}})
                pixels=base64.b64decode(image['contentItems'][1]['imageUrl'].split(',',1)[1]);(session_root/'model-interface-image.png').write_bytes(pixels)
                status=op('status');c=next(d for d in status['packet']['detections'] if d['id']=='C1');x,y,z=c['pos'];z=max(z,.018)
                # Private operator witness only: all requests traverse the same
                # authenticated, fenced public gateway and native low-level API.
                points=[([x,y,.22],255),([x,y,.11],255),([x,y,z],255),([x,y,z],0),([x,y,.11],0),([x,y,.22],0),
                        ([.52,-.13,.22],0),([.52,-.13,.11],0),([.52,-.13,.021],0),([.52,-.13,.021],255),([.52,-.13,.14],255)]
                for number,(position,gripper) in enumerate(points,1):
                    rid=f'{sid}-motion-{number}'
                    action={'operation':'cartesian_target','position':position,'duration_s':1.9,'gripper':gripper}
                    reply=robot('/command',envelope(rid,action));assert reply['command']['status']=='accepted'
                    wait(lambda s:op('command/'+rid)['command']['phase']=='terminal')
                    terminal=op('command/'+rid)['command'];assert terminal['status']=='completed',terminal
                rid=sid+'-clear-view'
                robot('/command',envelope(rid,{'operation':'joint_command','mode':'position','values':[.8,-.5,0,-2.2,0,1.7,.7854],'duration_s':1.9,'gripper':255}))
                wait(lambda s:op('command/'+rid)['command']['phase']=='terminal')
                assert op('command/'+rid)['command']['status']=='completed'
                wait(lambda s:op('outcome')['outcome']['success'])
                from controller import public_c_complete
                wait(lambda s:public_c_complete(s['packet']))
                hb='handback-'+sid;handback=robot('/handback',{**envelope(hb),'reason':'Deterministic public-interface contact witness complete'})
                assert handback['command']['status']=='completed'
                wait(lambda s:op('terminal/'+hb)['resumed'] is not None)
                receipts=op('terminal/'+hb)
                sensor.retired=True
                clean=guest.close();assert clean
                retire_files=list(session_root.glob('executor-*-retirement.json'))
                assert retire_files and not guest.abort_event.is_set()
                retirement={'run_id':manifest['run_id'],'session_id':sid,'all_namespaces_retired':True,
                            'evidence_sha256':hashlib.sha256(canonical({p.name:sha(p) for p in [*retire_files,session_root/'cleanup.json',session_root/'fresh-process.json']})).hexdigest()}
                save(session_root/'retirement-bound.json',retirement)
                current=op('status');op('retire-invocation',{'request_id':'retire-'+sid,'authority_epoch':current['authority_epoch'],'invocation_id':sid,'reason':'All deterministic runtime processes exited'})
                appended=block.terminal(receipts['accepted'],receipts['resumed'],retirement)
                note=linux("import pathlib,sys;sys.stdout.write(pathlib.Path(sys.argv[1]).read_text())",block.workspace+'/.continuity/Continuity.md')
                assert note.startswith('Agent-authored test continuity.') and note.count('Machine-authored terminal record')==count
                op('framework-terminal',{'receipt':appended,'content':note})
                after=block.checkpoint('session-retired',op('status')['packet']['sim_time'])
                result['sessions'].append({'session_id':sid,'actions':len(points)+1,'independent_success':True,'accepted_handback':hb,
                    'resumption':receipts['resumed'],'terminal_append':appended,'fresh_process':probe,'before':before,'after':after,
                    'image_sha256':hashlib.sha256(pixels).hexdigest(),'clean_retirement':True})
                guest=None
                if count==1:
                    current=op('status')
                    code,denied=runtime.request(url,token,'POST','/operator/start-invocation',
                        {'request_id':'forbidden-fourth','authority_epoch':current['authority_epoch'],'invocation_id':'forbidden-fourth'},operator=True)
                    assert code!=200 and denied['error']['code']=='admission_unavailable',denied
                    save(out/'fourth-session-refusal.json',denied)
                    result['fourth_session_refused']=True
            wait(lambda s:s['owner']=='conventional' and not s['active_command'] and op('outcome')['outcome']['success'])
            version=op('status')['order_version'];next_job=op('stage-next',{'request_id':'stage-after-'+str(version),'order_version':version})
            result['stage_events'].append(next_job)
            if next_job['block_complete']:break
            wait(lambda s:s['order_version']==next_job['order_version'])
        assert count==3
        assert len({(f['probe']['pid_namespace'],f['probe']['process_start_ticks']) for f in result['safe_unresolved_fixtures']})==2
        status=op('status');op('stop',{'request_id':'deterministic-finished','authority_epoch':status['authority_epoch'],'reason':'Three-session mechanical qualification complete'})
        assert host.wait(timeout=30)==0
        result['filesystem']=block.close();block=None
        host_result=json.loads((out/'host/result.json').read_text());result['host']=host_result
        from timing import verify_timing
        result['independent_timing_replay']=verify_timing(out/'host')
        result['passed']=host_result['execution_completed'] and host_result['timing_v2']['passed'] and result['filesystem']['passed']
    except Exception as e:result.update(error=str(e),traceback=traceback.format_exc())
    finally:
        if guest:
            try:result['failed_session_cleanup']=guest.close()
            except Exception as e:result['cleanup_error']=str(e)
        if host and host.poll() is None:
            try:
                status=op('status');op('stop',{'request_id':'qualification-abort','authority_epoch':status['authority_epoch'],'reason':'Deterministic qualification failed'})
                host.wait(timeout=30)
            except Exception as e:host.terminate();host.wait(timeout=10);result['host_forced_stop']=str(e)
        if block:
            try:result['failed_block_replay']=block.close()
            except Exception as e:result['block_cleanup_error']=str(e)
        if log:log.close()
        save(out/'receipt.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('host','sessions')}),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--extended-envelope',action='store_true');a=p.parse_args();raise SystemExit(run(a.output,a.extended_envelope))
