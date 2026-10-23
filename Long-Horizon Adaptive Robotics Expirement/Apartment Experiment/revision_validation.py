"""Read back the successful revised fixtures and actual native histories."""
import argparse
import ast
import copy
import json
from pathlib import Path
import subprocess
import sys
import traceback
from common import HERE,REPO,DEFAULT_ROOT,canonical,inventory,read,save,sha
from revision_config import CONFIG,RUNTIME
from run import source_identity

OFFLINE='APARTMENT-reliability-offline007'
LIVE='APARTMENT-reliability-live002'
ENG=DEFAULT_ROOT/'engineering'


def viewer_readback(root):
    """Reconstruct inode deltas independently at sampled clock boundaries."""
    from viewer import Files
    from content_store import Store
    from recording import Replay
    work=root/'sessions/session-00001/workspace';journal=work/'journal'
    records=[json.loads(line) for line in (journal/'mutations.jsonl').open('rb')]
    clocks=[json.loads(line)['payload'] for line in (work/'clock-bridge.jsonl').open('rb')]
    mutations=[r for r in records if r['type']=='mutation']
    chosen=[mutations[i] for i in (0,1,31,32,len(mutations)//2,len(mutations)-2,len(mutations)-1)]
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
                    assert files.file(path,t)['content']==(raw.decode('utf-8',errors='replace') if len(raw)<256*1024 else '[Large file: contents omitted from compact viewer]')
            checked+=1
    assert not files.listing(-1)['files']
    import numpy as np
    index=read(root/'replay/index.json');chunk=index[len(index)//2]
    with np.load(root/'replay'/chunk['file']) as recorded:
        k=min(len(recorded['t'])//2,len(recorded['t'])-2)
        assert k>=0
        sample_time=float(recorded['t'][k]);next_time=float(recorded['t'][k+1])
        assert next_time>sample_time
        pose=recorded['qpos'][k].copy();velocity=recorded['qvel'][k].copy()
    replay=Replay(root)
    try:
        for requested in (sample_time,(sample_time+next_time)/2):
            frame=replay.frame(requested)
            assert frame['sim_time']==sample_time and frame['sample_age']==requested-sample_time
            assert frame['provenance']['sha256']==chunk['sha256']==sha(frame['provenance']['file'])
            assert np.array_equal(replay.world.data.qpos,pose) and np.array_equal(replay.world.data.qvel,velocity)
    finally:replay.close()
    return dict(passed=True,boundary_queries=checked,sample_time=sample_time,sample_gap=next_time-sample_time,
        exact_recorded_pose=True,exact_sample_age=True,original_replay=True)


def engineering_ast(path):
    """Prove the live-tested engineering path unchanged after official routing.

    Only the explicit `run['stage']=='official'` blocks in the two known route
    functions may differ. All imports, other functions and engineering behavior
    must have identical syntax trees. Offline tests exercise those official
    blocks for both original and recovered Baseline/Maps roots.
    """
    tree=ast.parse(path.read_text(encoding='utf-8'))
    names={'run.py':('verify_run',1),'recovery.py':('prepare_recovery',2)}
    target,expected=names[path.name];guard=ast.dump(ast.parse("run['stage']=='official'",mode='eval').body)
    count=0
    class Mask(ast.NodeTransformer):
        def visit_If(self,node):
            nonlocal count
            if ast.dump(node.test)==guard:
                assert not node.orelse;count+=1;return ast.Pass()
            return self.generic_visit(node)
    for function in tree.body:
        if isinstance(function,ast.FunctionDef) and function.name==target:Mask().visit(function)
    assert count==expected,(path.name,count)
    return ast.dump(tree,include_attributes=False)


def receipt(identifier,out,official_route_delta=False):
    root=ENG/identifier;job=read(root/'queue-submission.json')['id']
    status=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(REPO.parent/'tools/compute_queue/compute_queue.py'),'status',job],text=True,encoding='utf-8'))
    save(out/(identifier+'-queue.json'),status)
    assert status['state']=='succeeded' and type(status['exit_status']) is int and status['exit_status']==0,identifier+' execution failed'
    result=read(root/'output/result.json');assert result['passed'] is True and all(result['checks'].values())
    assert inventory(root/'source')==read(root/'source-manifest.json'),'Attempt source snapshot changed'
    current=source_identity();tested=read(root/'full-source-identity.json')
    correspondence={}
    for name in RUNTIME:
        if current['apartment/'+name]==tested['apartment/'+name]:continue
        assert official_route_delta and name in ('run.py','recovery.py'),'Tested runtime changed: '+identifier+'/'+name
        assert engineering_ast(HERE/name)==engineering_ast(root/'source'/name),'Live engineering path changed: '+name
        correspondence[name]=dict(tested_sha256=tested['apartment/'+name],current_sha256=current['apartment/'+name],
            engineering_syntax_identical=True,changed_scope='Explicit official-only routing blocks; qualified independently for both conditions in offline007')
    save(out/(identifier+'-source-correspondence.json'),dict(passed=True,byte_identical_components=len(RUNTIME)-len(correspondence),official_only=correspondence))
    return result


def run(out):
    out.mkdir(parents=True,exist_ok=False);result=dict(passed=False,stage='revised-apparatus-readback',official_sessions=0,model_calls=0,checks={},evidence={})
    try:
        offline=receipt(OFFLINE,out);live=receipt(LIVE,out,official_route_delta=True)
        assert offline['checks']['paired_official_routes'] is True
        assert live['real_model_calls']==4 and live['injected_starts']==2
        assert offline['official_sessions']==live['official_sessions']==0
        result['checks']['successful_declared_fixture_and_native_runs']=True
        from audit import native,chain
        from repair_validation import transport_readback
        from recording import verify_checkpoint,verify_prefix
        for condition in ('baseline','maps'):
            root=Path(live['conditions'][condition]['root'])
            assert read(root/'config.json')==CONFIG
            evidence=native(root)
            evidence['transport']={s.name:transport_readback(s/'native') for s in sorted((root/'sessions').iterdir())}
            events=chain(root/'events.jsonl');starts=[r for r in events if r['kind']=='session_started'];closed=[r for r in events if r['kind']=='session_closed']
            assert len(starts)==len(closed)==2
            assert [r['payload']['work_s'] for r in starts]==[600,360]
            checkpoints=list((root/'checkpoints').iterdir());assert len(checkpoints)==2
            for checkpoint in checkpoints:verify_checkpoint(checkpoint);verify_prefix(root,checkpoint)
            failed=ENG/LIVE/'output/failed'/condition;recovery=read(root/'recovery-ready.json')
            assert inventory(failed)==recovery['parent_inventory'] and recovery['cumulative_interrupted_sessions']==1
            assert read(failed/'latest-execution.json')['passed'] is False
            admitted={r['payload']['request_id'] for r in events if r['kind']=='command_admitted'}
            docks=[]
            for start in starts:
                sid=start['payload']['session'];warning=start['sim_time']+start['payload']['work_s']
                commands=[r for r in events if r['kind']=='command_requested' and r['payload']['session']==sid and r['payload']['request']['request_id'] in admitted]
                dock=next(r for r in commands if r['payload']['request']['kind']=='dock');assert dock['sim_time']>=warning
                docks.append(dict(session=sid,warning_sim_time=warning,dock_sim_time=dock['sim_time'],return_base_commands=sum(r['payload']['request']['kind']=='base' and warning<=r['sim_time']<=dock['sim_time'] for r in commands)))
            evidence['normal_warning_and_docking']=docks
            assert not (root/'running.lock').exists() and not (failed/'running.lock').exists()
            evidence['viewer']=viewer_readback(root)
            result['evidence'][condition]=evidence
        result['checks']['native_world_inode_transport_checkpoint_readback']=True
        result['checks']['observable_replay_and_filesystem_alignment']=True
        import bundle_engineering
        result['checks']['frozen_bundle_preflight']=bundle_engineering.run(out/'bundle')
        protected=read(ENG/OFFLINE/'output/protected-before.json')
        actual={p:inventory(p) for p in protected};save(out/'protected-final.json',actual)
        assert actual==protected
        result['checks']['all_prior_evidence_unchanged']=True
        current=source_identity()
        old=read(DEFAULT_ROOT/'official/apartment-v1-restart001/frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/commissioning.json')
        for key,value in old['source_identity'].items():
            if not key.startswith('apartment/'):assert current[key]==value,'Inherited runtime/template changed: '+key
        for key in ('deployment.py','robot_client.py','schedule.py','image_sensor.py','broker.py','guest_probe.py'):
            assert current['apartment/'+key]==old['source_identity']['apartment/'+key],key
        from environment import identity
        installed=identity();assert installed==old['environment']
        result['checks']['model_sensors_templates_hidden_schedule_boundary_unchanged']=True
        result['certificate']=dict(schema='apartment-commissioning-3',passed=True,
            scope='Prospective APARTMENT-v2 reliability, explicit clocks and wider kitchen geometry; throwaway evidence only',
            source_identity=current,environment=installed,config=CONFIG,
            protocol_sha256={n:sha(HERE/n) for n in ('COMPARISON.md','ANALYSIS.md')},
            offline_run=OFFLINE,offline_result_sha256=sha(ENG/OFFLINE/'output/result.json'),
            live_run=LIVE,live_result_sha256=sha(ENG/LIVE/'output/result.json'),
            qualification_composition='Current runtime offline, including both official recovery routes and the real 21-assignment gate. Four live engineering sessions; all runtime bytes identical except syntax-proven official-only routing blocks in run.py/recovery.py.',
            source_correspondence_sha256=sha(out/(LIVE+'-source-correspondence.json')),
            previous_certificate_sha256=sha(DEFAULT_ROOT/'official/apartment-v1-restart001/frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment/commissioning.json'))
        result['passed']=all(result['checks'].values())
        if not result['passed']:result.pop('certificate',None)
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc());result.pop('certificate',None)
    save(out/'result.json',result);print(canonical({k:v for k,v in result.items() if k not in ('certificate','evidence')}).decode());return result['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.output) else 1)
