"""Operator CLI. Official launch requires a current commissioning certificate."""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
import traceback
import webbrowser
import uuid
from common import HERE,REPO,DEFAULT_ROOT,save,read,sha,inventory,canonical
from deployment import instantiate
from schedule import build,validate

def source_identity():
    value={'apartment/'+p.name:sha(p) for p in sorted(HERE.iterdir()) if p.is_file() and p.suffix in ('.py','.html')}
    integration=REPO/'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001'
    # Frozen imports and the supplied condition templates are comparison inputs too.
    for directory in ('campaign-005','campaign-002/harness','readiness-session-10/boundary','isolation-session-9/wsl','host','launch'):
        for p in sorted((integration/directory).rglob('*.py')):
            value['inherited/'+p.relative_to(integration).as_posix()]=sha(p)
    # Imported by the inherited qualification module's synthetic fixture types.
    # No Candidate policy is instantiated by the apartment runtime.
    relative='Long-Horizon Adaptive Robotics Expirement/Runtime 004/candidates.py'
    value['repository/'+relative]=sha(REPO/relative)
    relative='campaign-002/assessment/cleanup_transport.py'
    value['inherited/'+relative]=sha(integration/relative)
    for condition in ('Robot Agent Filesystem Draft v0.2','Robot Agent Filesystem Draft v0.2 Maps Edition'):
        for name,item in inventory(REPO/condition).items():value['template/'+condition+'/'+name]=item['sha256']
    return value

def prepare(root,condition,stage,schedule,config):
    root=Path(root).resolve()
    if root.drive.upper()!='D:':raise ValueError('Run artifacts require the external D: evidence root')
    if root.exists():raise ValueError('Refusing to overwrite an existing run')
    validate(schedule)
    if stage=='official':
        certificate=read(HERE/'commissioning.json')
        if not certificate['passed'] or certificate['source_identity']!=source_identity():raise ValueError('Commissioning certificate is absent or stale')
    root.mkdir(parents=True)
    instantiate(condition,root/'filesystem')
    save(root/'schedule.json',schedule);save(root/'config.json',config)
    save(root/'run.json',dict(schema='apartment-run-1',condition=condition,stage=stage,prepared=True,launched=False,
                            branch_id=uuid.uuid4().hex,source_identity=source_identity(),template=inventory(root/'filesystem'),schedule_sha256=sha(root/'schedule.json'),config_sha256=sha(root/'config.json')))
    save(root/'initial-filesystem.json',inventory(root/'filesystem'))
    return root

def verify_run(root,official_allowed=False):
    root=Path(root);run=read(root/'run.json')
    from recovery import check_branch_authority
    check_branch_authority(root,run)
    if run['source_identity']!=source_identity():raise ValueError('Run source changed after preparation')
    if sha(root/'schedule.json')!=run['schedule_sha256']:raise ValueError('Matched schedule changed')
    if sha(root/'config.json')!=run['config_sha256']:raise ValueError('Frozen run configuration changed')
    if run['stage']=='official':
        if not official_allowed:raise ValueError('Explicit --official authorization required; commissioning never supplies it')
        c=read(HERE/'commissioning.json')
        if not c['passed'] or c['source_identity']!=source_identity():raise ValueError('Commissioning certificate mismatch')
        from environment import identity
        if c['environment']!=identity():raise ValueError('Frozen installed runtime changed; requalification is required')
        if read(root/'config.json')!=c['config']:raise ValueError('Run battery/session parameters differ from commissioning')
        if run['condition']=='maps':
            from recovery import completed_baseline
            completed_baseline(Path(run.get('official_pair_root',root.parent)),run)
    return run

def validate_closeout(initial,final):
    before=inventory(initial);after=inventory(final)
    historical=[p for p in before if p.startswith('SessionReports/')]
    if any(after.get(p)!=before[p] for p in historical):raise ValueError('Historical session report changed')
    # The report template specifies one Markdown report in SessionReports/.
    # Attached evidence below that directory is preserved too, but is not a
    # second report (the actual native commissioning trace includes JSON trials).
    new_reports=[p for p in after if p not in before and p.startswith('SessionReports/')
                 and len(Path(p).parts)==2 and Path(p).suffix.lower()=='.md']
    if len(new_reports)!=1 or after[new_reports[0]]['bytes']<120:raise ValueError('Exactly one substantive new session report required')
    if before['SummaryOfOnlyNecessaryContext.md']==after['SummaryOfOnlyNecessaryContext.md']:raise ValueError('Session continuity was not updated')
    for p in before:
        if p in ('RobotAgentPrompt.md','RobotDetails.md','ProjectDetails.md') or p.startswith(('Programs/Default/','Playbooks/Default/')):
            if after.get(p)!=before[p]:raise ValueError('Deployment contract or default capability changed')
    return dict(passed=True,report=new_reports[0],initial=before,final=after)

def execute(root,resume=False,official=False,engineering_sessions=None,fixture_pose=None,hibernate_after_s=None,preflight=False):
    from controller import Controller
    from native_runtime import Workspace,Guest
    from viewer import serve
    root=Path(root).resolve();run=verify_run(root,official)
    if (root/'completed.json').exists():raise ValueError('The 21-assignment run is complete; no additional session may launch')
    if run['stage']!='engineering' and any(x is not None for x in (engineering_sessions,fixture_pose,hibernate_after_s)):
        raise ValueError('Engineering controls cannot affect official runs')
    lock=root/'running.lock'
    with lock.open('x') as f:f.write(str(os.getpid()))
    controller=guest=workspace=viewer=None
    execution_id=uuid.uuid4().hex;begin=time.monotonic_ns();phase='initialization';session_root=None
    retired=dict(native=True,filesystem=True,controller=True,viewer=True)
    outcome=dict(passed=False,stage=run['stage'],condition=run['condition'],sessions=[],model_calls=0,official_sessions=0,
        execution_id=execution_id,branch_id=run.get('branch_id'),started_wall_ns=time.time_ns(),started_monotonic_ns=begin)
    try:
        checkpoint=None
        if resume:
            phase='resume-validation'
            checkpoint=read(root/'latest-checkpoint.json')['path']
            pending=root/'hibernate-requested.json'
            if pending.exists():pending.rename(root/('hibernate-processed-'+execution_id+'.json'))
        else:
            if run['launched'] or inventory(root/'filesystem')!=read(root/'initial-filesystem.json'):raise ValueError('Starting state is no longer pristine; use a validated resume')
            run['launched']=True;save(root/'run.json',run)
        controller=Controller(root,read(root/'schedule.json'),read(root/'config.json'),run['condition'],run['stage'],checkpoint)
        retired['controller']=False;endpoint=controller.start()
        if fixture_pose is not None:controller.ask('fixture',fixture_pose)
        viewer,_=serve(root,controller);retired['viewer']=False
        save(root/'viewer.json',dict(url='http://127.0.0.1:'+str(viewer.server_port),pid=os.getpid()))
        if hibernate_after_s is not None:
            def request_later():
                if not controller.stop.wait(hibernate_after_s):save(root/'hibernate-requested.json',dict(requested_wall_ns=time.time_ns(),source='engineering-deferred-hibernation-test'))
            threading.Thread(target=request_later,daemon=True).start()
        while not controller.stop.is_set():
            before=controller.ask('private')
            if before['sessions'] and (root/'hibernate-requested.json').exists():
                phase='boundary-hibernation';outcome['boundary_pause']=controller.ask('pause_boundary');break
            if shutil.disk_usage(root).free<20*1024**3:raise RuntimeError('Less than 20 GiB free on experiment evidence volume; refusing a new native session')
            sid='session-'+str(before['sessions']+1).zfill(5)
            session_root=root/'sessions'/sid
            phase='workspace-startup';outcome['current_session']=sid
            retired['filesystem']=False
            workspace=Workspace(session_root/'workspace',root/'filesystem',sid,start=False)
            workspace.start()
            workspace.start_clock_bridge(controller)
            phase='native-qualification'
            retired['native']=False
            guest=Guest(session_root/'native',workspace,endpoint,controller);guest.qualify()
            started=controller.ask('start')
            phase='native-model'
            outcome['model_calls']+=1
            if run['stage']=='official':outcome['official_sessions']+=1
            asyncio.run(guest.model(timeout=read(root/'config.json')['model_wall_s'],preflight=preflight))
            client=read(session_root/'native/client/result.json')
            if client.get('structured_failure'):outcome['structured_failure']=client['structured_failure']
            normal=client.get('success') is True and client.get('turn_status')=='completed'
            phase='native-retirement'
            if not guest.close():raise RuntimeError('Native guest retirement failed')
            retired['native']=True
            guest=None
            final,receipt=workspace.close();workspace=None
            retired['filesystem']=True
            if not normal:
                phase='native-model';raise RuntimeError('Model did not complete normally: '+str(client.get('error')))
            phase='filesystem-closeout'
            closeout=validate_closeout(root/'filesystem',final);save(session_root/'closeout.json',closeout)
            previous=root/('filesystem-before-'+sid)
            (root/'filesystem').rename(previous)
            shutil.copytree(final,root/'filesystem')
            shutil.copy2(session_root/'workspace/final-namespace.json',root/'filesystem-namespace.json')
            shutil.copytree(session_root/'workspace/final-objects',root/'filesystem-objects',dirs_exist_ok=True)
            if engineering_sessions and len(outcome['sessions'])+1>=engineering_sessions:
                save(root/'hibernate-requested.json',dict(requested_wall_ns=time.time_ns(),source='engineering-session-limit'))
            phase='normal-boundary-checkpoint'
            ending=controller.ask('finish',dict(normal_model_completion=normal,filesystem_closeout=closeout['passed'],runtime_retired=receipt['passed'],session=sid))
            outcome['sessions'].append(dict(session=sid,started=started,ending=ending,client_result_sha256=sha(session_root/'native/client/result.json')))
            save(root/('execution-'+execution_id+'-'+str(len(outcome['sessions'])).zfill(5)+'.json'),outcome)
            if ending.get('hibernated') or ending.get('complete'):break
        if controller.error:raise RuntimeError(controller.error)
        outcome['passed']=True
    except BaseException as error:
        outcome.update(error=repr(error),failure_phase=phase,traceback=traceback.format_exc())
    finally:
        if guest:
            try:
                retired['native']=guest.close() is True
                if not retired['native']:outcome['guest_cleanup_error']='Native retirement did not qualify'
            except Exception as e:outcome['guest_cleanup_error']=repr(e)
        if workspace:
            try:workspace.close();retired['filesystem']=True
            except Exception as e:
                outcome['workspace_cleanup_error']=repr(e)
                try:workspace.abort();retired['filesystem']=workspace.closed
                except Exception as cleanup:outcome['workspace_abort_error']=repr(cleanup)
        if viewer:
            try:viewer.shutdown();viewer.server_close();retired['viewer']=True
            except Exception as e:outcome['viewer_cleanup_error']=repr(e);outcome['passed']=False
        if controller:
            try:controller.close();retired['controller']=True
            except Exception as e:outcome['controller_cleanup_error']=repr(e);outcome['passed']=False
        if session_root and (session_root/'native/client/result.json').is_file():
            client=read(session_root/'native/client/result.json')
            if client.get('structured_failure'):outcome['structured_failure']=client['structured_failure']
        outcome.update(finished_wall_ns=time.time_ns(),elapsed_monotonic_ns=time.monotonic_ns()-begin)
        outcome['retirement']=dict(components=retired,all_retired=all(retired.values()))
        if not all(retired.values()):outcome['passed']=False
        if (root/'latest-checkpoint.json').exists():outcome['last_verified_checkpoint']=read(root/'latest-checkpoint.json')
        result_path=root/('execution-result-'+execution_id+'.json');save(result_path,outcome)
        save(root/'latest-execution.json',dict(path=str(result_path),sha256=sha(result_path),passed=outcome['passed'],execution_id=execution_id))
        lock.unlink(missing_ok=True)
    return outcome

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('launch');q.add_argument('--root',type=Path,required=True);q.add_argument('--resume',action='store_true');q.add_argument('--official',action='store_true')
    q=sub.add_parser('recover');q.add_argument('--root',type=Path,required=True);q.add_argument('--destination',type=Path,required=True);q.add_argument('--reason',required=True);q.add_argument('--official',action='store_true')
    q=sub.add_parser('hibernate');q.add_argument('--root',type=Path,required=True)
    q=sub.add_parser('status');q.add_argument('--root',type=Path,required=True)
    q=sub.add_parser('viewer');q.add_argument('--root',type=Path,required=True)
    q=sub.add_parser('replay');q.add_argument('--root',type=Path,required=True);q.add_argument('--port',type=int,default=8816)
    a=p.parse_args()
    if a.command=='recover':
        from recovery import prepare_recovery
        print(canonical(prepare_recovery(a.root,a.destination,a.reason,a.official)).decode())
    elif a.command=='hibernate':save(a.root/'hibernate-requested.json',dict(requested_wall_ns=time.time_ns(),source='operator'));print('Hibernation pending. The current Robot Codex session will finish normally before checkpoint and shutdown.')
    elif a.command=='status':print(canonical(dict(run=read(a.root/'run.json'),running=(a.root/'running.lock').exists(),hibernate_pending=(a.root/'hibernate-requested.json').exists(),checkpoint=read(a.root/'latest-checkpoint.json') if (a.root/'latest-checkpoint.json').exists() else None)).decode())
    elif a.command=='viewer':webbrowser.open(read(a.root/'viewer.json')['url'])
    elif a.command=='replay':
        from viewer import serve
        server,replay=serve(a.root,port=a.port);print('http://127.0.0.1:'+str(server.server_port),flush=True)
        try:threading.Event().wait()
        except KeyboardInterrupt:server.shutdown();server.server_close();replay.close()
    else:
        result=execute(a.root,resume=a.resume,official=a.official);print(canonical(result).decode());return 0 if result['passed'] else 1
    return 0

if __name__=='__main__':raise SystemExit(main())
