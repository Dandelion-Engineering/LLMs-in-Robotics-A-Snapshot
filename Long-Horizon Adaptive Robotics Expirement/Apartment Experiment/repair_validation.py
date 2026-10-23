"""Final repair gates, independent readback and prospective certificate."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
from common import HERE,REPO,DEFAULT_ROOT,save,read,sha,inventory,canonical
from run import source_identity
from failure_audit import FAILED

LIVE='APARTMENT-repair-live004'
ENG=DEFAULT_ROOT/'engineering'

def transport_readback(folder):
    from frame_digest import projection
    rows=[];previous=None
    for i,line in enumerate((folder/'codehost-transport-v3.jsonl').open('rb'),1):
        row=json.loads(line);key=row.pop('record_sha256')
        assert hashlib.sha256(canonical(row)).hexdigest()==key and row['previous_sha256']==previous and row['sequence']==i
        previous=key;rows.append(row)
    receipt=read(folder/'codehost-owner-bridge-v3.json')
    assert receipt['qualified'] is True and not receipt['failures']
    assert receipt['queued_bytes_at_close']==0 and receipt['drain']['seal_qualified'] is True
    for d,opposite in [('incoming','outgoing'),('outgoing','incoming')]:
        assert projection(rows,d)==projection(receipt['namespace_records'],opposite)
    return dict(parent_bytes=(folder/'codehost-transport-v3.jsonl').stat().st_size,
                incoming=projection(rows,'incoming'),outgoing=projection(rows,'outgoing'))

def viewer_readback(root):
    from viewer import Files
    from content_store import Store
    from recording import Replay
    work=root/'sessions/session-00001/workspace';journal=work/'journal'
    records=[json.loads(l) for l in (journal/'mutations.jsonl').open('rb')]
    clocks=[json.loads(l)['payload'] for l in (work/'clock-bridge.jsonl').open('rb')]
    mutations=[r for r in records if r['type']=='mutation'];chosen=[mutations[i] for i in (0,1,31,32,len(mutations)//2,len(mutations)-2,len(mutations)-1)]
    bounds=sorted(set(next(c['after']['sim_time'] for c in clocks if c['linux']['linux_monotonic_ns']>=r['monotonic_ns']) for r in chosen))
    files=Files(root);store=Store(journal);checked=0
    for bound in bounds:
        for t in (bound-1e-7,bound,bound+1e-7):
            state=dict(paths={},nodes={})
            for row in records:
                clock=next((c for c in clocks if c['linux']['linux_monotonic_ns']>=row['monotonic_ns']),None)
                if clock is None or clock['after']['sim_time']>t:continue
                if row['type']=='initial':state=copy.deepcopy(row['state'])
                elif row['type']=='mutation':
                    for area in ('paths','nodes'):
                        for key in row['delta'][area]['remove']:state[area].pop(key,None)
                        state[area].update(row['delta'][area]['set'])
            wanted=sorted(p for p,i in state['paths'].items() if state['nodes'][str(i)].get('sha256'))
            assert files.material(t)[0]==wanted
            for path in ('/CommissioningIO/append.jsonl','/SummaryOfOnlyNecessaryContext.md'):
                if path in wanted:
                    node=state['nodes'][str(state['paths'][path])];raw=store.get(node['sha256'])
                    actual=files.file(path,t)['content']
                    assert actual==(raw.decode('utf-8',errors='replace') if len(raw)<256*1024 else '[Large file: contents omitted from compact viewer]')
            checked+=1
    assert not files.listing(-1)['files']
    replay=Replay(root)
    try:
        frame=replay.frame(1800);assert 0<=frame['sample_age']<.05
        assert sha(frame['provenance']['file'])==frame['provenance']['sha256']
    finally:replay.close()
    return dict(passed=True,boundary_queries=checked,original_replay=True)

def run(out):
    out.mkdir(parents=True,exist_ok=False)
    result=dict(passed=False,stage='repair-independent-validation',official_sessions=0,model_calls=0,checks={},evidence={})
    try:
        job=read(ENG/LIVE/'queue-submission.json')['id']
        status=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(REPO.parent/'tools/compute_queue/compute_queue.py'),'status',job],text=True,encoding='utf-8'))
        save(ENG/LIVE/'queue-status.json',status)
        assert status['state']=='succeeded' and type(status['exit_status']) is int and status['exit_status']==0,'Live repair run did not complete successfully'
        live=read(ENG/LIVE/'output/result.json')
        assert live['passed'] is True and all(live['checks'].values()) and live['official_sessions']==0
        import storage_engineering,repair_lifecycle_engineering,bundle_engineering,flow_engineering,native_stream_engineering,h2_engineering
        for label,module in [('storage',storage_engineering),('flow',flow_engineering),('native_stream',native_stream_engineering),('h2',h2_engineering),('lifecycle',repair_lifecycle_engineering),('bundle',bundle_engineering)]:
            result['checks'][label]=module.run(out/label)
            save(out/'progress.json',result)
            if not result['checks'][label]:raise ValueError(label+' repair gate failed')
        status=read(ENG/LIVE/'queue-status.json');live=read(ENG/LIVE/'output/result.json')
        assert status['state']=='succeeded' and type(status['exit_status']) is int and status['exit_status']==0
        assert live['passed'] is True and all(live['checks'].values()) and live['official_sessions']==0
        assert inventory(ENG/LIVE/'source')==read(ENG/LIVE/'source-manifest.json')
        from audit import native,chain
        for condition in ('baseline','maps'):
            root=ENG/LIVE/'output'/condition
            result['evidence'][condition]=native(root)
            result['evidence'][condition]['transport']={s.name:transport_readback(s/'native') for s in sorted((root/'sessions').iterdir())}
            events=chain(root/'events.jsonl')
            result['evidence'][condition]['lifecycle_events']=[dict(kind=r['kind'],sim_time=r['sim_time'],payload=r['payload']) for r in events if r['kind'] in ('session_started','session_closed','boundary_checkpoint','resumed')]
            admitted={r['payload']['request_id'] for r in events if r['kind']=='command_admitted'}
            starts=[r for r in events if r['kind']=='session_started'];docks=[]
            for start in starts:
                sid=start['payload']['session'];warning=start['sim_time']+start['payload']['work_s']
                commands=[r for r in events if r['kind']=='command_requested' and r['payload']['session']==sid and r['payload']['request']['request_id'] in admitted]
                dock=next(r for r in commands if r['payload']['request']['kind']=='dock')
                assert dock['sim_time']>=warning,'Dock before ordinary battery warning'
                returning=[r for r in commands if r['payload']['request']['kind']=='base' and warning<=r['sim_time']<=dock['sim_time']]
                docks.append(dict(session=sid,warning_sim_time=warning,dock_sim_time=dock['sim_time'],return_base_commands=len(returning)))
            assert len(docks)==2
            result['evidence'][condition]['normal_warning_and_docking']=docks
            assert not (root/'running.lock').exists()
        result['checks']['independent_native_checkpoint_transport']=True
        result['evidence']['viewer']=viewer_readback(ENG/LIVE/'output/baseline')
        result['checks']['repaired_content_replay']=True
        current=source_identity();tested=read(ENG/LIVE/'full-source-identity.json')
        runtime=('common.py','content_store.py','journal_reader.py','journal_service.py','native_runtime.py','native_stream.py','transport.py','frame_digest.py','flow_control.py','h2_runtime.py','h2_readback.py','transport_inside.py','guest_entry.py','run.py','scene.py','world.py','controller.py','recording.py','schedule.py','deployment.py','broker.py','guest_probe.py','image_sensor.py','robot_client.py','viewer.py','viewer.html')
        assert all(current['apartment/'+n]==tested['apartment/'+n] for n in runtime),'Native-tested component changed'
        old=read(FAILED/'frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/commissioning.json')
        allowed={'journal_service.py','native_runtime.py','transport.py','guest_entry.py','run.py','viewer.py','audit.py','freeze.py'}
        changed=[k for k,v in old['source_identity'].items() if current[k]!=v]
        assert all(k.startswith('apartment/') and k.split('/',1)[1] in allowed for k in changed),changed
        result['evidence']['changed_original_components']=changed
        result['checks']['original_physics_interfaces_templates_unchanged']=True
        from environment import identity
        installed=identity();assert installed==old['environment']
        assert read(ENG/LIVE/'output/baseline/config.json')==old['config']
        result['checks']['full_original_work_window_and_runtime']=True
        original=read(ENG/'APARTMENT-repair-audit001/output/preserved-manifest.json');now=inventory(FAILED)
        changed_files=[p for p in original if original[p]!=now.get(p)]
        console='baseline/sessions/session-00001/workspace/fuse-console.log'
        assert changed_files==[console] and set(now)==set(original),changed_files
        archived=DEFAULT_ROOT/'failed-launches/APARTMENT-v1-baseline-launch-001'
        assert sha(archived/'fuse-console-before-cleanup.log')==original[console]['sha256']
        assert sha(archived/'fuse-console-after-cleanup.log')==now[console]['sha256']
        save(out/'failed-launch-after-cleanup-manifest.json',now)
        result['checks']['failed_launch_bytes_preserved']=True
        result['certificate']=dict(schema='apartment-commissioning-2',passed=True,
            scope='Prospective storage/lifecycle repair, throwaway evidence only; no official restart launched',
            source_identity=current,environment=installed,config=old['config'],
            calibration_sha256=sha(HERE/'calibration.json'),previous_certificate_sha256=sha(FAILED/'frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/commissioning.json'),
            live_run=LIVE,live_result_sha256=sha(ENG/LIVE/'output/result.json'),live_queue_status_sha256=sha(ENG/LIVE/'queue-status.json'))
        result['passed']=all(result['checks'].values())
    except BaseException as e:result.update(error=repr(e),traceback=traceback.format_exc())
    save(out/'result.json',result);print(canonical({k:v for k,v in result.items() if k not in ('evidence','certificate')}).decode());return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.output) else 1)
