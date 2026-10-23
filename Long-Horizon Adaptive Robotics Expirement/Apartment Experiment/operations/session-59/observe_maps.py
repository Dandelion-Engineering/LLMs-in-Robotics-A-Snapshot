"""One read-only observation of the declared C: Maps storage instance."""
import argparse
from collections import Counter
import time
import urllib.request
import uuid
from support import *


def prefix(path):
    rows=[];digest=hashlib.sha256();size=0
    with Path(path).open('rb') as f:
        for line in f:
            if not line.endswith(b'\n'):break
            digest.update(line);size+=len(line);rows.append(json.loads(line))
    return rows,dict(path=str(path),bytes=size,sha256=digest.hexdigest(),records=len(rows))


def main(label,startup=False,checkpoint=False):
    route=read(HERE/'storage-route.json');assert Path(route['active_storage_root']).resolve()==RUN.resolve()
    assert route==read(PAIR/'operator/maps-storage-route-session59.json')
    job=read(HERE/'official-queue-submission.json')['id']
    value=dict(label=label,observed_utc=now(),observational_only=True,root=str(RUN),queue=queue('status',job),checks={},passed=False)
    try:
        value['running_lock']=(RUN/'running.lock').exists()
        value['capacity']=dict(C=volume('C:\\'),D=volume('D:\\'),reserve_bytes=50*GIB)
        value['reserve_ok']=all(value['capacity'][d]['free_bytes']>=50*GIB for d in ('C','D'))
        rows,value['events_prefix']=prefix(RUN/'events.jsonl')
        value['event_counts']=dict(Counter(r['kind'] for r in rows))
        lifecycle=[r for r in rows if r['kind'] in ('session_started','session_closed','boundary_checkpoint','task_success','resumed')]
        value['last_lifecycle_event']=lifecycle[-1] if lifecycle else None
        for name in ('latest-checkpoint.json','completed.json','controller-failure.json','hibernate-requested.json','recovery-ready.json'):
            if (RUN/name).exists():value[name]=read(RUN/name)
        if (RUN/'latest-execution.json').exists():
            pointer=read(RUN/'latest-execution.json');path=Path(pointer['path'])
            assert path.parent.resolve()==RUN.resolve() and sha(path)==pointer['sha256']
            value['execution']=read(path)
        if (RUN/'viewer.json').exists():
            url=read(RUN/'viewer.json')['url'];assert url.startswith('http://127.0.0.1:');value['viewer_url']=url
            try:
                with urllib.request.urlopen(url+'/frame',timeout=12) as response:frame=json.load(response)
                value['frame']={k:v for k,v in frame.items() if k not in ('geoms','activity')}
                value['geometry_count']=len(frame['geoms']);value['viewer_responding']=True
            except Exception as e:value.update(viewer_responding=False,viewer_error=repr(e))
        value['checks']['original_maps_preserved']=inventory(PAIR/'maps')==read(QUAL/'maps-before.json')
        basepoint=read(PAIR/'baseline/latest-checkpoint.json')
        value['checks']['baseline_endpoint_anchors']=basepoint['session']==35 and sha(Path(basepoint['path'])/'manifest.json')==basepoint['manifest_sha256'] and sha(Path(basepoint['path'])/'state.json')==basepoint['state_sha256']
        value['checks']['storage_reserve']=value['reserve_ok']
        if startup:
            value['checks']['queue_running']=value['queue']['state']=='running' and value['queue']['exit_status'] is None
            value['checks']['run_launched']=read(RUN/'run.json')['launched'] is True and value['running_lock']
            session=RUN/'sessions/session-00001';native=session/'native'
            preflight=read(native/'client/preflight.json')
            value['native']={k:preflight.get(k) for k in ('model_effective','effort_effective','auth_type','preflight_passed','thread_id')}
            value['checks']['native_identity']=preflight['preflight_passed'] and preflight['model_effective']=='gpt-6-astra' and preflight['effort_effective']=='max' and preflight['auth_type']=='chatgpt'
            value['checks']['namespace_canaries']=all(read(native/n)['exit_status']==0 and json.loads(read(native/n)['stdout'])['qualified'] for n in ('canary.json','codehost-canary.json'))
            events,value['native_prefix']=prefix(native/'client/events.jsonl');counts=Counter(r.get('method',r.get('kind','unknown')) for r in events)
            value['native_counts']=dict(counts)
            value['checks']['actual_native_turn']=counts['turn/started']>0
            value['checks']['actual_tools']=counts['item/tool/call']>0 or counts['public_tool_call']>0
            sensors=[r for r in rows if r['kind']=='sensor_capture'];images=[r for r in rows if r['kind']=='image_delivered']
            value['checks']['sensor_image_delivery']=bool(sensors and images)
            for r in sensors:
                p=RUN/'sensors'/('frame-'+str(r['payload']['sequence']).zfill(7)+'.png');assert sha(p)==r['payload']['image_sha256']
            journal,value['journal_prefix']=prefix(session/'workspace/journal/mutations.jsonl')
            value['checks']['journal_active']=len(journal)>1
            index=read(RUN/'replay/index.json');value['checks']['replay_recording']=bool(index) and sha(RUN/'replay'/index[-1]['file'])==index[-1]['sha256']
            time.sleep(.2)
            with urllib.request.urlopen(value['viewer_url']+'/frame',timeout=12) as response:after=json.load(response)
            value['checks']['live_simulation_advances']=after['sim_time']>value['frame']['sim_time'] and value['geometry_count']>0
        if checkpoint and (RUN/'latest-checkpoint.json').exists():
            sys.path.insert(0,str(CODE));from recording import verify_checkpoint,verify_prefix
            pointer=read(RUN/'latest-checkpoint.json');p=Path(pointer['path'])
            assert p.resolve().is_relative_to(RUN.resolve())
            value['checkpoint_readback']=dict(pointer=pointer,receipt=verify_checkpoint(p),prefix=verify_prefix(RUN,p))
            assert sha(p/'manifest.json')==pointer['manifest_sha256'] and sha(p/'state.json')==pointer['state_sha256']
            value['checks']['checkpoint_readback']=True
        value['passed']=all(value['checks'].values())
    except BaseException as e:value['error']=repr(e)
    path=DATA/'operator/observations'/(label+'-'+uuid.uuid4().hex+'.json');save(path,value)
    print(json.dumps(dict(evidence=str(path),passed=value['passed'],checks=value['checks'],queue_state=value['queue']['state'],
        exit_status=value['queue']['exit_status'],viewer_url=value.get('viewer_url'),frame=value.get('frame'),event_counts=value.get('event_counts'),
        checkpoint=value.get('latest-checkpoint.json'),C_free_gib=value['capacity']['C']['free_bytes']/GIB,D_free_gib=value['capacity']['D']['free_bytes']/GIB,error=value.get('error'))),flush=True)
    return 0 if value['passed'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--label',default='periodic');p.add_argument('--startup',action='store_true');p.add_argument('--checkpoint',action='store_true');a=p.parse_args()
    raise SystemExit(main(a.label,a.startup,a.checkpoint))
