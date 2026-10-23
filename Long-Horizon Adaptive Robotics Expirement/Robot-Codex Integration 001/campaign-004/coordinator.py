"""Source-bound live qualification, pilot and scored block coordinator.

No developer motion policy. Default invocation stops before any host/model
process; each launch requires its prospectively registered authorized manifest.
"""
import argparse
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import time
import traceback
import uuid
from types import SimpleNamespace
from common import HERE,REPO,inherited_paths,canonical,save,sha
inherited_paths()
from workspace_block import WorkspaceBlock,linux,wsl
from scheduler import Schedule
# Explicit load avoids the inherited modules named runtime/run_host.
from common import load_module
runtime=load_module('campaign004_runtime_system',HERE/'runtime.py')

class JournalView:
    def __init__(self,root):self.root=Path(root)
    @property
    def events(self):
        raw=(self.root/'public-history.jsonl').read_bytes()
        return [json.loads(line) for line in raw.splitlines(keepends=True) if line.endswith(b'\n')]

class TaskFailure(RuntimeError):
    """A bounded model invocation ended without the required task acceptance."""

def model_completion(client):
    """Separate a clean budget stop from a broken or unqualified runtime."""
    if not (client.get('native_quiescence',{}).get('qualified') is True
            and client.get('preflight_passed') is True and client.get('model_started') is True
            and client.get('auth_type')=='chatgpt' and client.get('model_effective')=='gpt-6-astra'
            and client.get('effort_effective')=='max'):
        return 'invalid'
    if client.get('success') is True and client.get('turn_status')=='completed':return 'completed'
    if (client.get('error')=='Bounded app-server deadline exceeded'
            and client['native_quiescence'].get('terminal_turn',{}).get('status')=='interrupted'):
        return 'bounded_deadline'
    return 'invalid'

def approved_manifest(path):
    if path is None:raise RuntimeError('Campaign 004 awaits human review and final registration')
    path=Path(path);manifest=json.loads(path.read_text(encoding='utf-8'))
    if manifest.get('stage') not in ('live_qualification','pilot','reviewed_campaign') or not manifest.get('human_approval_reference'):
        raise RuntimeError('Campaign 004 awaits human review and final registration')
    authority=manifest['authority']
    with (REPO/authority['path']).open('rb') as stream: prefix=stream.read(authority['bytes'])
    if hashlib.sha256(prefix).hexdigest()!=authority['sha256']:
        raise ValueError('Human authorization transcript prefix changed')
    if manifest['stage']=='reviewed_campaign' and not manifest.get('allocation_reference'):
        raise ValueError('Scored allocation must be predeclared')
    if manifest['stage']=='reviewed_campaign':
        for gate in manifest['qualification_gates']:
            if sha(gate['receipt'])!=gate['receipt_sha256'] or sha(gate['status'])!=gate['status_sha256']:
                raise ValueError('Qualification evidence changed')
            receipt=json.loads(Path(gate['receipt']).read_text());status=json.loads(Path(gate['status']).read_text())
            if not (receipt['passed'] and status['state']=='succeeded' and type(status['exit_status']) is int and status['exit_status']==0):
                raise ValueError('Required qualification gate did not pass')
    if manifest['stage']=='pilot':
        gate=manifest['prerequisite_audit']
        if sha(gate['path'])!=gate['sha256'] or sha(gate['official_status_path'])!=gate['official_status_sha256']:
            raise ValueError('Pilot prerequisite audit identity changed')
        audit=json.loads(Path(gate['path']).read_text());job=json.loads(Path(gate['official_status_path']).read_text())
        if not (audit['passed'] and audit['qualification_complete'] and audit['measurements']['actual_image_deliveries']>0
                and job['state']=='succeeded' and type(job['exit_status']) is int and job['exit_status']==0):
            raise ValueError('Pilot infrastructure prerequisite is not qualified')
    limit=manifest.get('encounter_limit',manifest['apparatus_manifest']['encounters'])
    from runtime_limits import validate_limits
    validate_limits(manifest['apparatus_manifest'])
    if limit!=manifest['apparatus_manifest']['encounters'] and not (manifest['stage']=='live_qualification' and limit==1):
        raise ValueError('Only the declared single-encounter live qualification may truncate a block')
    snapshot=path.parent/manifest['source_snapshot_path']
    if sha(snapshot)!=manifest['source_snapshot_sha256']:raise ValueError('Final source snapshot identity mismatch')
    identities=json.loads(snapshot.read_text(encoding='utf-8'))
    for area in ('source','inherited'):
        for name,identity in identities[area].items():
            if sha(REPO/name)!=identity['sha256']:raise ValueError('Final source changed: '+name)
    return manifest

def run(output,reviewed_manifest=None):
    approval=approved_manifest(reviewed_manifest)
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    result={'passed':False,'infrastructure_valid':False,'stage':approval['stage'],
            'model_calls_requested':0,'sessions':[],'attempted_sessions':[],'unresolved_sessions':[],'stage_events':[],
            'manifest_sha256':sha(reviewed_manifest)};block=guest=host=None;log=None
    encounter_limit=approval.get('encounter_limit',approval['apparatus_manifest']['encounters'])
    result['declared_encounters']=encounter_limit
    started_wall=time.time_ns()
    try:
        manifest=approval['apparatus_manifest']
        # Keep the native reserve plus retirement headroom, and admit enough
        # room for primary Windows evidence, WSL journal and retained export.
        if shutil.disk_usage(out).free<111*1024**3:raise RuntimeError('Native reserve plus 9 GiB primary evidence capacity unavailable before launch')
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
                if host.poll() is not None:raise RuntimeError('Host exited during reviewed block')
                value=op('status')
                if predicate(value):return value
                time.sleep(.05)
            raise RuntimeError('Bounded state deadline')
        block=WorkspaceBlock.__new__(WorkspaceBlock)
        block.__init__(out/'workspace-block',runtime.template(),manifest['run_id'],approval['revision_id'],approval['source_snapshot_sha256'],
                       archive_root=approval.get('public_archive_root'))
        count=0;occurrences={}
        while True:
            status=op('status');order=status['packet']['order']
            if order['kind']=='C-placement':
                status=wait(lambda s:s['owner']=='robot')
                count+=1;sid='robot-session-'+uuid.uuid4().hex[:16]
                version=order['version'];occurrences[version]=occurrences.get(version,0)+1
                if occurrences[version]>3:raise RuntimeError('Hidden session ceiling violated')
                attempt={'session_id':sid,'started_wall_unix_ns':time.time_ns(),'task_outcome':'unknown',
                         'order_version':version,'occurrence':len(occurrences),'session_within_occurrence':occurrences[version]}
                result['attempted_sessions'].append(attempt)
                started=op('start-invocation',{'request_id':'start-'+sid,'authority_epoch':status['authority_epoch'],'invocation_id':sid})
                robot_ep=started['endpoint'];session_root=out/sid
                status=op('status');files=runtime.template()
                files.update({'live/state.json':json.dumps(status),'live/activation.json':json.dumps(status['activation']),
                              'live/observations/latest.json':json.dumps(status['packet'])})
                guest=runtime.Runtime.__new__(runtime.Runtime)
                guest.__init__(session_root,files,robot_ep,block,sid,host_workspace=out/'public')
                from image_sensor import ImageSensor
                sensor=ImageSensor(out/'public',JournalView(out/'host'),manifest['run_id'],sid,robot_ep['authority_epoch'])
                guest.image_sensor=sensor
                guest.qualify()
                before=block.checkpoint('before-model-invocation',op('status')['packet']['sim_time'])
                result['model_calls_requested']+=1
                asyncio.run(guest.model(timeout=manifest['model_timeout_s'],reviewed_campaign_authority=True))
                client=json.loads((session_root/'client/result.json').read_text())
                save(session_root/'bound-client-result.json',client)
                attempt['client_result_sha256']=sha(session_root/'client/result.json')
                attempt['model_termination']=model_completion(client)
                if attempt['model_termination']=='invalid':
                    raise RuntimeError('Model invocation or native retirement unqualified; stop admission')
                save(session_root/'model-ending-state.json',{'public':op('status'),
                    'physical':op('continuation-state')['physical'],'session_id':sid,
                    'model_termination':attempt['model_termination'],'wall_unix_ns':time.time_ns()})
                registry=json.loads((out/'host/command-registry.json').read_text())
                accepted=[c for c in registry.values() if c['kind']=='handback' and c['status']=='completed'
                          and c['envelope']['authority_epoch']==robot_ep['authority_epoch']]
                if len(accepted)!=1:
                    if accepted:raise RuntimeError('Multiple accepted handbacks for one invocation')
                    sensor.retired=True
                    clean=guest.close();assert clean and not guest.abort_event.is_set()
                    retire_files=list(session_root.glob('executor-*-retirement.json'))
                    assert retire_files and all(json.loads(p.read_text())['qualified'] for p in retire_files)
                    retirement={'run_id':manifest['run_id'],'session_id':sid,'all_namespaces_retired':True,
                        'evidence_sha256':hashlib.sha256(canonical({p.name:sha(p) for p in [*retire_files,session_root/'cleanup.json',session_root/'client/result.json']})).hexdigest()}
                    save(session_root/'retirement-bound.json',retirement);guest=None
                    current=op('status')
                    op('retire-invocation',{'request_id':'retire-'+sid,'authority_epoch':current['authority_epoch'],
                        'invocation_id':sid,'reason':'Isolated runtime retired'})
                    prefix=block.verify_prefix();save(session_root/'continuation-journal-audit.json',prefix)
                    proof={'session_id':sid,'normal_completion':attempt['model_termination']=='completed','native_retirement':True,
                        'journal_verified':prefix['verified']['passed'],'open_handles':prefix['after']['linux']['open_handles'],
                        'journal_state_sha256':prefix['verified']['final_state_sha256'],
                        'journal_audit_sha256':sha(session_root/'continuation-journal-audit.json'),
                        'retirement_evidence_sha256':retirement['evidence_sha256'],'client_result_sha256':sha(session_root/'client/result.json')}
                    ending=op('authorize-continuation',proof);save(session_root/'ending.json',ending)
                    attempt['task_outcome']='safe_unresolved' if ending['safe_unresolved'] else 'failure'
                    attempt['finished_wall_unix_ns']=time.time_ns()
                    attempt['ending']=ending;result['unresolved_sessions'].append(attempt.copy())
                    if ending['admitted']:continue
                    invalid_checks=('retired_native_namespaces','durable_independent_journal','no_open_filesystem_handles',
                        'bound_session','robot_authority','clean_authority_retirement','no_unresolved_request',
                        'same_occurrence','no_accepted_handback','not_stopped')
                    if not all(ending['checks'][name] for name in invalid_checks):
                        raise RuntimeError('Ending evidence or authority does not support a valid occurrence result')
                    result['task_failure']='C occurrence unresolved after three sessions' if ending['safe_unresolved'] else 'Session ending does not support safe continuation'
                    raise TaskFailure(result['task_failure'])
                hb=accepted[0]['request_id']
                wait(lambda s:op('terminal/'+hb)['resumed'] is not None)
                if not op('outcome')['outcome']['success']:
                    result['task_failure']='Handback lacks independent placement acceptance'
                    attempt['task_outcome']='failure'
                    raise TaskFailure('Independent C task acceptance missing')
                receipts=op('terminal/'+hb)
                sensor.retired=True
                clean=guest.close();assert clean
                retire_files=list(session_root.glob('executor-*-retirement.json'))
                assert retire_files and not guest.abort_event.is_set()
                retirement={'run_id':manifest['run_id'],'session_id':sid,'all_namespaces_retired':True,
                            'evidence_sha256':hashlib.sha256(canonical({p.name:sha(p) for p in [*retire_files,session_root/'cleanup.json',session_root/'client/result.json']})).hexdigest()}
                save(session_root/'retirement-bound.json',retirement)
                current=op('status');op('retire-invocation',{'request_id':'retire-'+sid,'authority_epoch':current['authority_epoch'],'invocation_id':sid,'reason':'All prior runtime namespaces retired'})
                prior_note=linux("import pathlib,sys;sys.stdout.write(pathlib.Path(sys.argv[1]).read_text())",block.workspace+'/.continuity/Continuity.md')
                appended=block.terminal(receipts['accepted'],receipts['resumed'],retirement)
                note=linux("import pathlib,sys;sys.stdout.write(pathlib.Path(sys.argv[1]).read_text())",block.workspace+'/.continuity/Continuity.md')
                assert note.startswith(prior_note) and hashlib.sha256(note.encode()).hexdigest()==appended['after_sha256']
                op('framework-terminal',{'receipt':appended,'content':note})
                after=block.checkpoint('session-retired',op('status')['packet']['sim_time'])
                result['sessions'].append({'session_id':sid,'client_result_sha256':sha(session_root/'client/result.json'),'independent_success':True,'accepted_handback':hb,
                    'resumption':receipts['resumed'],'terminal_append':appended,'before':before,'after':after,
                    'image_deliveries_file':'host/image-views-'+sid+'.jsonl','clean_retirement':True})
                attempt.update(task_outcome='success',finished_wall_unix_ns=time.time_ns())
                guest=None
                if len(result['sessions'])==encounter_limit:break
            wait(lambda s:s['owner']=='conventional' and not s['active_command'] and op('outcome')['outcome']['success'])
            version=op('status')['order_version'];next_job=op('stage-next',{'request_id':'stage-after-'+str(version),'order_version':version})
            result['stage_events'].append(next_job)
            if next_job['block_complete']:break
            wait(lambda s:s['order_version']==next_job['order_version'])
        assert len(result['sessions'])==encounter_limit
        status=op('status');op('stop',{'request_id':'reviewed-block-finished','authority_epoch':status['authority_epoch'],'reason':'Reviewed block sequence complete'})
        assert host.wait(timeout=30)==0
        result['filesystem']=block.close();block=None
        host_result=json.loads((out/'host/result.json').read_text());result['host']=host_result
        from timing import verify_timing
        result['independent_timing_replay']=verify_timing(out/'host')
    except Exception as e:result.update(error=str(e),error_kind='task_failure' if isinstance(e,TaskFailure) else 'infrastructure',traceback=traceback.format_exc())
    finally:
        if guest:
            try:result['failed_session_cleanup']=guest.close()
            except Exception as e:result['cleanup_error']=str(e)
        if host and host.poll() is None:
            try:
                status=op('status');op('stop',{'request_id':'qualification-abort','authority_epoch':status['authority_epoch'],'reason':'Block stopped on failure'})
                host.wait(timeout=30)
            except Exception as e:host.terminate();host.wait(timeout=10);result['host_forced_stop']=str(e)
        if block:
            try:result['failed_block_replay']=block.close()
            except Exception as e:result['block_cleanup_error']=str(e)
        if log:log.close()
        # Always assess stopped attempts as well as successful sequences. A
        # queue exit alone never establishes task or infrastructure validity.
        try:
            host_result=json.loads((out/'host/result.json').read_text())
            result['host']=host_result
            from timing import verify_timing
            timing=verify_timing(out/'host');result['independent_timing_replay']=timing
            filesystem=result.get('filesystem',result.get('failed_block_replay',{}))
            clean=not any(k in result for k in ('cleanup_error','host_forced_stop','block_cleanup_error'))
            clean=clean and result.get('failed_session_cleanup',True) is True
            clients=[json.loads(p.read_text()) for p in out.glob('robot-session-*/client/result.json')]
            clean=clean and len(clients)==result['model_calls_requested'] and all(model_completion(c)!='invalid' for c in clients)
            result['infrastructure_valid']=bool(host_result['execution_completed'] and timing['actual_host_timing_pass']
                and filesystem.get('passed') and clean and result.get('error_kind')!='infrastructure')
            result['passed']=result['infrastructure_valid'] and len(result['sessions'])==encounter_limit
        except Exception as error:result['assessment_error']=str(error)
        result['wall_elapsed_s']=(time.time_ns()-started_wall)/1e9
        result['retained_windows_bytes']=sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
        save(out/'receipt.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('host','sessions')}),flush=True)
    return 0 if result['infrastructure_valid'] else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--reviewed-manifest',type=Path);a=p.parse_args();raise SystemExit(run(a.output,a.reviewed_manifest))
