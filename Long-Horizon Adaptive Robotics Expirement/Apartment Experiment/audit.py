"""Independent readback of commissioning receipts; never runs an official model."""
import argparse
import ast
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
import traceback
from common import HERE,REPO,DEFAULT_ROOT,read,save,sha,canonical,inventory
from run import source_identity
from recording import verify_checkpoint

ENGINEERING=DEFAULT_ROOT/'engineering'

def require(ok,message):
    if not ok:raise ValueError(message)

def chain(path):
    previous='0'*64;sequence=0;rows=[]
    for line in Path(path).read_bytes().splitlines():
        row=json.loads(line);expected=row.pop('sha256')
        require(row['sequence']==sequence+1 and row['previous']==previous and hashlib.sha256(canonical(row)).hexdigest()==expected,'Invalid event chain: '+str(path))
        row['sha256']=expected;previous=expected;sequence+=1;rows.append(row)
    return rows

def receipt(identifier):
    root=ENGINEERING/identifier;status=read(root/'queue-status.json');result=read(root/'output/result.json')
    require(status['state']=='succeeded' and type(status['exit_status']) is int and status['exit_status']==0,identifier+' queue did not succeed')
    require(result['passed'] is True and result.get('checks') and all(x is True for x in result['checks'].values()),identifier+' task-specific gates did not pass')
    require(result['official_sessions']==0,identifier+' was not throwaway')
    require(inventory(root/'source')==read(root/'source-manifest.json'),identifier+' archived source changed')
    return dict(run=identifier,result_sha256=sha(root/'output/result.json'),queue_status_sha256=sha(root/'queue-status.json'),checks=result['checks'])

def components(identifier,names):
    for name in names:require(sha(HERE/name)==sha(ENGINEERING/identifier/'source'/name),'Qualified component changed: '+identifier+'/'+name)

def native(condition_root):
    import journal_reader as reader
    evidence=[];threads=[];prior=None
    for session in sorted((condition_root/'sessions').iterdir()):
        n=session/'native';w=session/'workspace';c=read(n/'client/result.json')
        require(c['success'] is True and c['preflight_passed'] is True and c['turn_status']=='completed','Native model completion missing')
        require(c['model_effective']=='gpt-6-astra' and c['effort_effective']=='max' and c['auth_type']=='chatgpt','Model/auth identity mismatch')
        require(c['native_quiescence']['qualified'] is True and c['native_quiescence']['native_exit_code']==0,'Native model process did not retire normally')
        stream=read(n/'client/native-stream.json')
        require(stream['passed'] is True and stream['readers_retired'] is True and not stream['reader_errors'],'Native notification readers did not retire normally')
        require(stream['retained_event_bytes']==(n/'client/events.jsonl').stat().st_size<=stream['retained_event_limit'],'Native event accounting differs')
        require(stream['raw_consumed_bytes']<=stream['raw_stream_limit']+stream['cleanup_extra_bytes'] and stream['pending_terminal_peak']<=4,'Native stream bound differs')
        require(stream['queue_peak_bytes']<=max(stream['queue_byte_limit'],stream['per_message_limit']) and stream['queue_peak_items']<=stream['queue_item_limit'],'Native queue accounting differs')
        for name in ('codehost-owner-bridge-v3.json','codehost-owner-retirement-v3.json'):
            require(read(n/name)['qualified'] is True,'Codehost qualification failed')
        import native_runtime
        from h2_readback import paired
        for channel in read(n/'codehost-owner-bridge-v3.json')['channels']:
            paired(channel['h2'],channel['namespace_closed']['h2'])
        require(read(n/'cleanup.json')['clean'] is True and read(session/'closeout.json')['passed'] is True,'Session closeout failed')
        for name in ('canary.json','codehost-canary.json'):
            r=read(n/name);require(type(r['exit_status']) is int and r['exit_status']==0 and json.loads(r['stdout'])['qualified'] is True,'Namespace probe failed')
        location=read(w/'location.json');proof=reader.verify(w/'journal',location['run_id'],retain_reads=True)
        require(proof['passed'] is True and proof['state']==read(w/'final-namespace.json'),'Independent namespace replay differs')
        initial=json.loads((w/'journal/mutations.jsonl').read_bytes().splitlines()[0])['state']
        if prior is not None:
            require(initial==prior,'Fresh-session inode/content state changed')
            if condition_root.name=='maps':
                require(any(x['path'].startswith('/Maps/Rooms/') and not x['path'].endswith('/README.md') and x['bytes']>0 for x in proof['read_events']),'Fresh Maps session did not read a room map')
        prior=proof['state'];threads.append(c['thread_id'])
        clocks=chain(w/'clock-bridge.jsonl');require(len(clocks)>1,'Missing clock alignment')
        require(all(x['payload']['before']['sim_time']<=x['payload']['after']['sim_time'] for x in clocks),'Reversed clock interval')
        evidence.append(dict(session=session.name,client_sha256=sha(n/'client/result.json'),journal_sha256=sha(w/'journal/mutations.jsonl'),final_namespace_sha256=sha(w/'final-namespace.json'),clock_sha256=sha(w/'clock-bridge.jsonl'),clock_brackets=len(clocks),reads=proof['reads'],mutations=proof['mutations'],native_stream=stream))
    require(len(threads)==len(set(threads)),'Model thread reused between fresh sessions')
    events=chain(condition_root/'events.jsonl')
    captures=[r for r in events if r['kind']=='sensor_capture'];deliveries=[r for r in events if r['kind']=='image_delivered']
    require(captures and deliveries,'Image interface not exercised')
    for row in captures:
        p=row['payload'];require(sha(condition_root/'sensors'/('frame-'+str(p['sequence']).zfill(7)+'.png'))==p['image_sha256'],'Sensor capture changed')
    for part in read(condition_root/'replay/index.json'):require(sha(condition_root/'replay'/part['file'])==part['sha256'],'Replay chunk changed')
    checkpoint=verify_checkpoint(read(condition_root/'latest-checkpoint.json')['path'])
    return dict(sessions=evidence,events=len(events),images_delivered=len(deliveries),checkpoint=checkpoint)

def run(out):
    out.mkdir(parents=True,exist_ok=False);result=dict(passed=False,stage='independent-commissioning-readback',checks={},official_sessions=0,model_calls=0,evidence={})
    try:
        inputs=read(HERE/'audit-inputs.json')
        for gate,identifier in inputs['runs'].items():result['evidence'][gate]=receipt(identifier);result['checks'][gate]=True
        suite=inputs['runs']['physical_and_lifecycle'];model=inputs['runs']['native_fresh_resume'];bundle=inputs['runs']['frozen_bundle'];viewer=inputs['runs']['final_viewer']
        components(suite,['common.py','scene.py','world.py','controller.py','recording.py','schedule.py','deployment.py','journal_service.py','native_runtime.py','robot_client.py'])
        components(model,['common.py','scene.py','controller.py','native_runtime.py','journal_service.py','transport.py','broker.py','guest_entry.py','guest_probe.py','image_sensor.py','robot_client.py','deployment.py'])
        trees=[ast.parse(p.read_text()) for p in (HERE/'recording.py',ENGINEERING/model/'source/recording.py')]
        preserved=lambda tree:{n.name:ast.dump(n) for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in ('Recorder','verify_checkpoint','geoms')}
        require(preserved(trees[0])==preserved(trees[1]),'Native-tested recording/checkpoint functions changed')
        # Two prospectively strengthened task-boundary branches are covered by the
        # final deterministic suite. All other native-tested world methods are exact.
        current_world=ast.parse((HERE/'world.py').read_text());model_world=ast.parse((ENGINEERING/model/'source/world.py').read_text())
        method_map=lambda tree:{n.name:ast.dump(n) for c in tree.body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name not in ('setup_assignment','evaluate')}
        require(method_map(current_world)==method_map(model_world),'Native-tested world runtime changed outside qualified task boundaries')
        result['evidence']['prospective_task_boundary_repairs']=dict(methods=['setup_assignment','evaluate'],covered_by=suite,reason='Household success excludes still-held objects; external next-assignment ball reset permits a previous held ball while public reset still requires release.')
        components(bundle,['freeze.py','run.py','environment.py'])
        components(viewer,['viewer.py','viewer.html'])
        current=source_identity();qualified=read(ENGINEERING/model/'full-source-identity.json')
        require(all(qualified.get(k)==v for k,v in current.items() if k.startswith(('inherited/','template/'))),'Inherited runtime or template changed')
        for key,digest in current.items():
            if key.startswith('repository/'):
                relative=key.removeprefix('repository/')
                original=subprocess.check_output(['git','show','HEAD:'+relative],cwd=REPO)
                require(hashlib.sha256(original).hexdigest()==digest,'Additional imported dependency differs from unchanged repository source')
                result['evidence']['additional_import_pin']=dict(path=relative,sha256=digest,reason='Unchanged synthetic fixture type imported by inherited qualification; now explicitly pinned and included in the independently exercised frozen bundle. No Candidate policy is instantiated.')
        current_tree=ast.parse((HERE/'run.py').read_text());prior_tree=ast.parse((ENGINEERING/model/'source/run.py').read_text())
        for name in ('execute','validate_closeout','prepare'):
            get=lambda tree:ast.dump(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name))
            require(get(current_tree)==get(prior_tree),'Qualified native execution logic changed: '+name)
        result['checks']['qualified_component_identity']=True
        for identifier in (inputs['runs']['calibrated_sessions'],model):
            result['evidence'][identifier]={c:native(ENGINEERING/identifier/'output'/c) for c in ('baseline','maps')}
        result['checks']['independent_native_and_replay_readback']=True
        for label,path in inputs['reviews'].items():
            value=read(path);require(value['passed'] is True,'Incomplete review: '+label)
            result['evidence'][label]=dict(path=path,sha256=sha(path));result['checks'][label]=True
        calibration=read(HERE/'calibration.json')
        config={k:calibration[k] for k in ('normal_work_s','throw_work_s','reserve_s','model_wall_s')}
        require(config==read(ENGINEERING/inputs['runs']['calibrated_sessions']/'output/baseline/config.json'),'Calibrated windows changed')
        from environment import identity
        result['certificate']=dict(schema='apartment-commissioning-1',passed=True,scope='Apparatus readiness only; no official data or learned throwing skill',source_identity=current,environment=identity(),config=config,calibration_sha256=sha(HERE/'calibration.json'),audit_inputs_sha256=sha(HERE/'audit-inputs.json'))
        result['passed']=all(result['checks'].values())
    except BaseException as e:result.update(error=repr(e),traceback=traceback.format_exc())
    save(out/'result.json',result)
    print(canonical({k:v for k,v in result.items() if k not in ('evidence','certificate')}).decode());return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.output) else 1)
