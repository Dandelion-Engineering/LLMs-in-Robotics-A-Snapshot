"""Bounded read-only observation of the explicitly accepted recovery branch."""
import argparse
from collections import Counter
import time
import traceback
import urllib.request
import uuid
from common63 import *
from observe_maps import prefix
sys.path.insert(0,str(HERE.parent/'session-60'))
from read_progress import owner_status

def main(label,checkpoints=False):
    out=BASE/'observations'/(label+'-'+uuid.uuid4().hex+'.json')
    result=dict(observed_utc=now(),observational_only=True,passed=False,checks={},root=str(DEST),abandoned_original_model_calls=1,
        assessment_scope='Bounded observation integrity; passed is not scientific success or endpoint acceptance',endpoint_independently_accepted=False)
    try:
        route=read(HERE/'continuation-route.json')
        assert Path(route['active_root']).resolve()==DEST.resolve()
        assert Path(read(PAIR/'maps-lineage.json')['active_root']).resolve()==DEST.resolve()
        for key in ('source_manifest','certificate','parent_run','run','claim','readiness','checkpoint','state','schedule','configuration','prior_lineage','prior_c_storage_route','qualification','audit','authority'):
            row=route[key];assert sha(row['uri'])==row['sha256'],key
        result['route']=ref(HERE/'continuation-route.json')
        source=read(FROZEN/'source-manifest.json')
        for name,row in source.items():assert sha(FROZEN/name)==row['sha256'],name
        result['checks']['unchanged_sources_and_bound_recovery_identity']=True
        result['queue']=queue('status',read(HERE/'official-queue-submission.json')['id'])
        result['scientific_queue_healthy']=result['queue']['state'] in ('running','queued') or (result['queue']['state']=='succeeded' and type(result['queue']['exit_status']) is int and result['queue']['exit_status']==0)
        result['capacity']=dict(C=legacy.volume('C:\\'),D=legacy.volume('D:\\'),reserve_bytes=50*GIB)
        result['checks']['full_storage_reserves']=all(result['capacity'][v]['free_bytes']>=50*GIB for v in ('C','D'))
        rows,result['events_prefix']=prefix(DEST/'events.jsonl')
        previous='0'*64;epoch_times={}
        for number,event in enumerate(rows,1):
            payload=dict(event);digest=payload.pop('sha256')
            assert payload['sequence']==number and payload['previous']==previous and hashlib.sha256(canonical(payload)).hexdigest()==digest
            previous=digest
        result['checks']['event_chain']=True
        result['event_counts']=dict(Counter(row['kind'] for row in rows))
        result['last_event']=rows[-1]
        result['lifecycle_tail']=[r for r in rows if r['kind'] in ('resumed','session_started','session_closed','boundary_checkpoint','task_success')][-8:]
        assert sum(r['kind']=='resumed' for r in rows)==1
        for name in ('completed.json','controller-failure.json','latest-execution.json'):
            if (DEST/name).exists():result[name]=read(DEST/name)
        if 'latest-execution.json' in result:
            pointer=result['latest-execution.json'];assert Path(pointer['path']).parent.resolve()==DEST.resolve() and sha(pointer['path'])==pointer['sha256']
            result['execution']=read(pointer['path'])
        result['checks']['no_controller_failure']=not (DEST/'controller-failure.json').exists()
        pointer=read(DEST/'latest-checkpoint.json');cp=Path(pointer['path'])
        assert cp.resolve().is_relative_to(DEST.resolve())
        state=read(cp/'state.json')
        assert sha(cp/'manifest.json')==pointer['manifest_sha256'] and sha(cp/'state.json')==pointer['state_sha256']
        result['progress']=dict(accepted_sessions=state['sessions'],closed_advancements=state['position'],
            newly_accepted_sessions=state['sessions']-5,abandoned_original_model_calls=1,completed_by_kind=dict(Counter(x['kind'] for x in state['completed'])))
        result['latest_checkpoint']=pointer
        if checkpoints:
            from recording import verify_checkpoint,verify_prefix
            result['checkpoint_readbacks']=[]
            for n in range(6,state['sessions']+1):
                p=DEST/'checkpoints'/('session-'+str(n).zfill(5))
                receipt=verify_checkpoint(p);proof=verify_prefix(DEST,p)
                result['checkpoint_readbacks'].append(dict(session=n,receipt=receipt,prefix=proof))
            result['checks']['all_new_checkpoints']=True
        if (DEST/'viewer.json').exists():
            url=read(DEST/'viewer.json')['url'];assert url.startswith('http://127.0.0.1:');result['viewer_url']=url
            try:
                with urllib.request.urlopen(url+'/frame',timeout=10) as response:frame=json.load(response)
                result['frame']={k:v for k,v in frame.items() if k not in ('geoms','activity')};result['geometry_count']=len(frame['geoms'])
                time.sleep(.3)
                with urllib.request.urlopen(url+'/frame',timeout=10) as response:after=json.load(response)
                result['viewer_http_freshness']=dict(first_time=frame['sim_time'],second_time=after['sim_time'],advancing=after['sim_time']>frame['sim_time'],rendered_ui_checked=False)
            except Exception as error:result['viewer_error']=repr(error)
        new_native=[]
        parent_threads={read(p)['thread_id'] for p in (PARENT/'sessions').glob('*/native/client/result.json')}
        for session in sorted((DEST/'sessions').glob('session-*')):
            number=int(session.name.split('-')[-1])
            if number<=5:continue
            native=session/'native';pre=native/'client/preflight.json'
            if not pre.exists():
                new_native.append(dict(session=number,state='startup_preflight_pending'));continue
            n=read(pre);assert n['preflight_passed'] and n['model_effective']=='gpt-6-astra' and n['effort_effective']=='max'
            assert n['thread_id'] not in parent_threads
            for name in ('canary.json','codehost-canary.json'):
                canary=read(native/name);assert canary['exit_status']==0 and json.loads(canary['stdout'])['qualified']
            events,nativeprefix=prefix(native/'client/events.jsonl')
            counts=Counter(r.get('method',r.get('kind','unknown')) for r in events)
            owners=[owner_status(p) for name in ('native-owner.json','codehost-native-owner-v3.json') for p in native.rglob(name)]
            row=dict(session=number,thread_id=n['thread_id'],preflight=ref(pre),owners=owners,event_counts=dict(counts),native_prefix=nativeprefix,
                model_call_started=bool(counts['turn/started']),tools_seen=bool(counts['item/tool/call'] or counts['public_tool_call']))
            journal,jprefix=prefix(session/'workspace/journal/mutations.jsonl');row['journal_prefix']=jprefix
            if number<=state['sessions']:
                import journal_reader
                from run import validate_closeout
                w=session/'workspace';loc=read(w/'location.json');client=read(native/'client/result.json');cleanup=read(w/'cleanup-001.json')
                assert client['success'] and client['turn_status']=='completed'
                assert cleanup['normal_requested'] and cleanup['retired'] and not cleanup['mounted'] and cleanup['service_exit']==0 and not cleanup['errors']
                assert len(owners)==2 and all(o['retired'] for o in owners)
                assert validate_closeout(DEST/('filesystem-before-'+session.name),w/'final-filesystem')==read(session/'closeout.json')
                proof=journal_reader.verify(w/'journal',loc['run_id'])
                row['closed_journal']={k:v for k,v in proof.items() if k not in ('state','states','read_events')}
            new_native.append(row)
        result['new_native']=new_native
        result['new_model_calls_started']=sum(n.get('model_call_started',False) for n in new_native)
        result['total_model_calls_including_abandoned_parent']=6+result['new_model_calls_started']
        result['checks']['fresh_native_identity_and_closed_session_readback']=all(n.get('thread_id') for n in new_native) if new_native else False
        sensors=[r for r in rows if r['kind']=='sensor_capture' and r['sequence']>1287]
        images=[r for r in rows if r['kind']=='image_delivered' and r['sequence']>1287]
        if sensors:
            sensor=sensors[-1];p=DEST/'sensors'/('frame-'+str(sensor['payload']['sequence']).zfill(7)+'.png')
            assert sha(p)==sensor['payload']['image_sha256'];result['latest_sensor']=dict(event_sequence=sensor['sequence'],image=ref(p))
        result['new_sensor_count']=len(sensors);result['new_image_deliveries']=len(images)
        replay=read(DEST/'replay/index.json');assert sha(DEST/'replay'/replay[-1]['file'])==replay[-1]['sha256']
        result['latest_replay']=replay[-1]
        result['checks']['original_d_maps_preserved']=inventory(PAIR/'maps')==read(QUAL/'maps-before.json')
        result['passed']=all(result['checks'].values()) and result['scientific_queue_healthy']
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
    result['reader']=ref(__file__);save(out,result)
    print(json.dumps(dict(evidence=ref(out),passed=result['passed'],checks=result['checks'],queue=result.get('queue',{}).get('state'),
        progress=result.get('progress'),viewer_url=result.get('viewer_url'),frame=result.get('frame'),new_model_calls=result.get('new_model_calls_started'),
        error=result.get('error'),traceback=result.get('traceback'))),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--label',default='observation');parser.add_argument('--checkpoints',action='store_true');args=parser.parse_args()
    raise SystemExit(main(args.label,args.checkpoints))
