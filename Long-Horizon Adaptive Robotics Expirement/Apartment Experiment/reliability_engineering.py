"""Isolated failure, geometry, clock and headroom commissioning. No model calls."""
import argparse
import asyncio
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import traceback
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from common import HERE,DEFAULT_ROOT,Events,canonical,inventory,read,save,sha
from revision_config import CONFIG


def rejected(call):
    try:call()
    except Exception:return True
    return False


def closeout_artifacts(out):
    """Use the retained real failed trace, without editing or importing its state."""
    from run import validate_closeout
    out.mkdir(parents=True)
    source=DEFAULT_ROOT/'engineering/APARTMENT-reliability-live001/output/failed/baseline'
    before=source/'filesystem';final=source/'sessions/session-00001/workspace/final-filesystem'
    protected=inventory(source)
    proof=validate_closeout(before,final)
    assert proof['report']=='SessionReports/2026-10-07T195826Z-session-001.md'
    assert (final/'SessionReports/Artifacts/session-001-throw-trials.json').is_file()
    missing=out/'missing-report';shutil.copytree(final,missing)
    report=missing/proof['report'];report.rename(report.with_suffix('.withheld'))
    assert rejected(lambda:validate_closeout(before,missing))
    duplicate=out/'duplicate-report';shutil.copytree(final,duplicate)
    shutil.copy2(duplicate/proof['report'],duplicate/'SessionReports/second-report.md')
    assert rejected(lambda:validate_closeout(before,duplicate))
    history=out/'changed-history';shutil.copytree(final,history)
    (history/proof['report']).write_bytes((history/proof['report']).read_bytes()+b'\nChanged prior report.\n')
    shutil.copy2(final/proof['report'],history/'SessionReports/next-report.md')
    with (history/'SummaryOfOnlyNecessaryContext.md').open('ab') as stream:stream.write(b'\nNext session.\n')
    assert rejected(lambda:validate_closeout(final,history))
    assert inventory(source)==protected
    result=dict(passed=True,actual_trace_report=proof['report'],companion_evidence_preserved=True,
        missing_report_refused=True,duplicate_report_refused=True,historical_change_refused=True,failed_source_unchanged=True)
    save(out/'result.json',result);return result


def clean_fixture(c):
    c.ask('start');c.ask('fixture',[1,1,1.2]);c.ask('fixture_advance_time',3)
    c.ask('public',('POST','/command',dict(kind='dock',parameters={},request_id='dock')))


PROOF=dict(normal_model_completion=True,filesystem_closeout=True,runtime_retired=True,source='private-controller-fixture-no-native-model')


def create_controller(root,condition='baseline'):
    from run import prepare
    from schedule import build
    from controller import Controller
    config={**CONFIG,'normal_work_s':1,'throw_work_s':2}
    prepare(root,condition,'engineering',build(881),config)
    c=Controller(root,read(root/'schedule.json'),config,condition);c.start()
    return c


def paired_official_routes(out):
    """Private controller fixtures exercise both official routes without a model.

    The certificate read alone is replaced by an explicitly labeled local test
    certificate. Real pristine conditions, checkpoint/prefix validation, the
    21-assignment baseline gate and exclusive branch routing all run normally.
    No path is under the actual official evidence directory.
    """
    from run import verify_run,source_identity
    from recovery import prepare_recovery
    from environment import identity
    results={}
    def terminal_fixture(root,passed):
        path=root/'execution-result-private-fixture.json'
        save(path,dict(passed=passed,retirement=dict(all_retired=True),source='private-controller-route-fixture-no-native-model'))
        save(root/'latest-execution.json',dict(path=str(path),sha256=sha(path),passed=passed))
    for condition in ('baseline','maps'):
        pair=out/condition;root=pair/condition;c=create_controller(root,condition)
        try:
            clean_fixture(c);c.ask('finish',PROOF);c.ask('start');c.ask('fixture_advance_time',1)
        finally:c.close()
        run=read(root/'run.json');run.update(stage='official',official_pair_root=str(pair.resolve()),launched=True,private_controller_fixture=True)
        save(root/'run.json',run);terminal_fixture(root,False)
        lineage=pair/(condition+'-lineage.json')
        save(lineage,dict(active_root=str(root.resolve()),history=[],policy=CONFIG['recovery_policy']))
        certificate=dict(passed=True,source_identity=source_identity(),environment=identity(),config=read(root/'config.json'),scope='PRIVATE ROUTING FIXTURE; NO MODEL OR OFFICIAL LAUNCH')
        def fixture_read(path):return certificate if Path(path)==HERE/'commissioning.json' else read(path)
        with patch('run.read',fixture_read):
            assert rejected(lambda:verify_run(root,False))
            if condition=='maps':
                assert rejected(lambda:verify_run(root,True))
                baseline=pair/'baseline';b=create_controller(baseline)
                try:
                    for _ in range(21):
                        clean_fixture(b);b.ask('fixture_success_latch');b.ask('finish',PROOF)
                finally:b.close()
                terminal_fixture(baseline,True)
                save(pair/'baseline-lineage.json',dict(active_root=str(baseline.resolve()),history=[]))
            before=inventory(root)
            assert verify_run(root,True)['condition']==condition
            assert rejected(lambda:prepare_recovery(root,pair/'outside-recovery','Private destination guard check',True))
            branch=pair/'recoveries'/(condition+'-001')
            proof=prepare_recovery(root,branch,'Private paired official-route regression; no provider invocation',True)
            assert verify_run(branch,True)['condition']==condition
            assert Path(read(lineage)['active_root']).resolve()==branch.resolve()
            assert inventory(root)==before and proof['source_unchanged']
            assert rejected(lambda:prepare_recovery(root,pair/'recoveries'/'duplicate','Duplicate route must fail',True))
            if condition=='maps':assert not read(pair/'baseline-lineage.json')['history']
        results[condition]=dict(explicit_authorization_required=True,original_and_recovered_roots_verified=True,
            correct_condition_pointer=True,source_unchanged=True,duplicate_and_external_destination_refused=True)
    return dict(passed=True,model_calls=0,official_model_sessions=0,private_certificate_substitution=True,
        real_21_assignment_gate=True,conditions=results)


def checkpoint_faults(out):
    from recording import publish_checkpoint,verify_checkpoint,verify_prefix
    phases=('created','filesystem_copied','state_written','manifest_written','verified','renamed','published')
    observations=[]
    for phase in phases:
        root=out/phase;c=create_controller(root)
        try:
            clean_fixture(c);c.ask('finish',PROOF)
            old=read(root/'latest-checkpoint.json')
            clean_fixture(c)
            def fault(where):
                if where==phase:raise RuntimeError('Injected checkpoint publication interruption: '+where)
            def interrupted(root,state,reason):return publish_checkpoint(root,state,reason,fault=fault)
            with patch('controller.publish_checkpoint',interrupted):
                assert rejected(lambda:c.ask('finish',PROOF))
        finally:c.close()
        pointer=read(root/'latest-checkpoint.json');verify_checkpoint(pointer['path']);verify_prefix(root,pointer['path'])
        assert (pointer==old)==(phase!='published')
        from recovery import best_checkpoint
        chosen,_,state,invalid=best_checkpoint(root)
        assert state['sessions']==(2 if phase in ('manifest_written','verified','renamed','published') else 1)
        observations.append(dict(injected_after=phase,pointer_still_verified=True,selected_session=state['sessions'],invalid_candidates=len(invalid)))
    return dict(passed=True,cases=observations)


def recovery_fixture(out):
    from recording import verify_checkpoint
    from recovery import prepare_recovery
    from controller import Controller
    root=out/'failed';c=create_controller(root)
    try:
        clean_fixture(c);first=c.ask('finish',PROOF)
        snapshot=read(Path(first['checkpoint']['path'])/'state.json')
        # Explicit failed-start fixture after a real clean controller boundary.
        c.ask('start');c.ask('fixture_advance_time',2)
    finally:c.close()
    run=read(root/'run.json');run['launched']=True;save(root/'run.json',run)
    save(root/'execution-result-injected.json',dict(passed=False,error='Injected provider failure; no real model request',retirement=dict(all_retired=True,source='private-controller-fixture')))
    save(root/'latest-execution.json',dict(path=str(root/'execution-result-injected.json'),sha256=sha(root/'execution-result-injected.json'),passed=False))
    before=inventory(root);branch=out/'branch'
    proof=prepare_recovery(root,branch,'Private injected empty-start infrastructure failure')
    assert inventory(root)==before and proof['interrupted_sessions_in_parent_tail']==1
    assert rejected(lambda:prepare_recovery(root,out/'duplicate','Duplicate continuation must fail'))
    cp=read(branch/'latest-checkpoint.json')['path'];verify_checkpoint(cp)
    c=Controller(branch,read(branch/'schedule.json'),read(branch/'config.json'),'baseline',checkpoint=cp);c.start()
    try:
        restored=c.ask('private')
        assert canonical(restored['world'])==canonical(snapshot['world'])
        assert restored['position']==snapshot['position'] and restored['sessions']==snapshot['sessions']
        save(branch/'hibernate-requested.json',dict(source='private-deferred-hibernation-fixture'))
        clean_fixture(c);ending=c.ask('finish',PROOF)
        assert ending['hibernated'] and verify_checkpoint(ending['checkpoint']['path'])['passed']
    finally:c.close()
    assert inventory(root)==before
    bad=out/'corrupt';shutil.copytree(Path(cp),bad)
    with (bad/'filesystem/SummaryOfOnlyNecessaryContext.md').open('ab') as stream:stream.write(b'corrupt')
    assert rejected(lambda:verify_checkpoint(bad))
    return dict(passed=True,source_unchanged=True,exact_world_rng_position=True,duplicate_refused=True,corruption_refused=True,
        cumulative_interrupted_sessions=proof['cumulative_interrupted_sessions'],deferred_hibernation=True)


def error_fixture(out):
    from structured_errors import install
    out.mkdir(parents=True)
    error=dict(message='Selected model is at capacity. Please try a different model.',codexErrorInfo='serverOverloaded',additionalDetails=None,misalignment=None)
    done=dict(id='turn-test',status='failed',error=error,durationMs=2920)
    class Base:
        def __init__(self,args):pass
        def log(self,row):pass
        def wait_turn(self,tid):
            self.log(dict(kind='notification',method='error',params=dict(error=error,willRetry=False,threadId='thread-test',turnId=tid)))
            self.log(dict(kind='notification',method='turn/completed',params=dict(threadId='thread-test',turn=done)))
            return done
    module=SimpleNamespace(Client=Base)
    def original(args):
        c=module.Client(args);result=dict(success=False,model_started=True)
        try:
            turn=c.wait_turn('turn-test')
            if turn['status']!='completed':raise RuntimeError('Bootstrap turn did not complete')
        except Exception as exception:result['error']=str(exception)
        return result
    module.run=original;install(module)
    result=module.run(SimpleNamespace(evidence=out,redact_tokens=[]))
    detail=result['structured_failure']
    assert result['turn_status']=='failed' and detail['native_error']==error and detail['retry_disposition'] is False
    assert 'serverOverloaded' in result['error'] and detail['terminal']['durationMs']==2920
    assert detail['automatic_retry'] is False and detail['recorded_assistant_or_tool_activity'] is False
    return dict(passed=True,error=result['error'],structured_native_cause=True,automatic_retry=False)


def clock_fixture(out):
    out.mkdir(parents=True);events=Events(out/'events.jsonl','clock-fixture')
    with patch('common.time.time_ns',side_effect=[20_000_000_000,12_253_817_800]),patch('common.time.perf_counter_ns',side_effect=[100_000_000,131_666_200]):
        events.emit('before',1,{});events.emit('after',2,{})
    events.close();rows=[json.loads(x) for x in (out/'events.jsonl').read_bytes().splitlines()]
    assert rows[1]['wall_ns']<rows[0]['wall_ns'] and rows[1]['monotonic_ns']>rows[0]['monotonic_ns']
    assert rows[1]['wall_clock_discontinuity']['wall_delta_ns']==-7_746_182_200
    assert [r['sim_time'] for r in rows]==[1,2]
    check=Events(out/'events.jsonl');check.close()
    from recording import Recorder
    from world import World
    w=World()
    try:
        recorder=Recorder(out/'replay',w.model,'clock-fixture')
        with patch('recording.time.time_ns',side_effect=[20_000_000_000,12_253_817_800]):
            recorder.sample(w.data,force=True);w.step(10);recorder.sample(w.data,force=True);recorder.flush()
        with np.load(out/'replay/states-000000.npz') as data:
            assert data['wall_ns'][1]<data['wall_ns'][0] and data['monotonic_ns'][1]>data['monotonic_ns'][0] and data['t'][1]>data['t'][0]
    finally:w.close()
    return dict(passed=True,wall_regression_seconds=7.7461822,original_timestamps_preserved=True,monotonic_and_simulation_ordered=True)


def geometry_fixture(out):
    from world import World
    from scene import DRAWER_CENTERS,CHARGERS
    from engineering import move,relocate_for_fixture
    from task_engineering import travel,turn,stow,pickup
    out.mkdir(parents=True);result=dict(passed=False,checks={},measurements={});w=None
    try:
        aisle=10.42-(max(x for x,y in DRAWER_CENTERS)+.49)
        front_clearance=min(y for x,y in DRAWER_CENTERS)-.5-.645-.08
        diameter=2*math.hypot(.28,.24)
        assert front_clearance>2.2 and aisle>1.6 and aisle-diameter>.85
        result['measurements'].update(open_drawer_to_south_wall_m=front_clearance,counter_aisle_m=aisle,base_rotation_diameter_m=diameter)
        w=World();w.setup_assignment(dict(kind='kitchen',position=0,sensor_seed=919,drawer='A',toys=[[2.7,6.1]]*4));w.begin_session(360,3600)
        stow(w)
        for x,y in ((5.3,2.3),(9.9,2.3),(9.9,2)):
            travel(w,x,y);assert np.linalg.norm(w.base_pose()[:2]-[x,y])<.06
        result['checks']['ordinary_route_to_cup']=True
        w.close();w=None
        for drawer,(cx,cy) in zip(('A','B'),DRAWER_CENTERS):
            w=World();w.setup_assignment(dict(kind='kitchen',position=0,sensor_seed=922,drawer=drawer,toys=[[2.7,6.1]]*4))
            if drawer=='B':
                relocate_for_fixture(w,cx-.26,cy-1.1,math.pi/2);move(w,'gripper',width=.07);move(w,'arm',x=.70,y=0,z=.91)
                assert w.latch_released;stow(w)
            relocate_for_fixture(w,cx+.60,cy-1.07,math.pi)
            move(w,'position_grasp',x=.60,y=-.45,z=.78);move(w,'arm',x=.60,y=-.45,z=.78);move(w,'gripper',width=0)
            move(w,'arm',x=.60,y=.05,z=.78,duration=8)
            opening=float(w.data.qpos[w.model.joint('drawer'+drawer).qposadr[0]])
            assert opening>.32,(drawer,opening)
            move(w,'gripper',width=.15);stow(w)
            relocate_for_fixture(w,9.9,2,0);pickup(w,.9,0,.941,0);assert w.pickups['cup'];stow(w)
            for x,y in ((9.9,1.75),(cx,1.75),(cx,1.9)):travel(w,x,y)
            turn(w,math.pi/2);point=w.body('drawer'+drawer)
            move(w,'arm',x=.4,y=0,z=1.18);move(w,'arm',x=float(point[1]-.18-w.base_pose()[1]),y=0,z=1.18)
            move(w,'gripper',width=.15);move(w,'wait',duration=2)
            result['checks']['drawer_'+drawer+'_physical_task']=bool(w.evaluate())
            result['measurements']['drawer_'+drawer+'_opening_m']=opening
            save(out/('drawer-'+drawer+'.json'),dict(cup=w.body('cup').tolist(),drawer=point.tolist(),result=result))
            assert w.evaluate(),(drawer,w.body('cup').tolist(),point.tolist())
            w.close();w=None
        w=World();w.begin_session(.1,3600);relocate_for_fixture(w,4.05,9.1,0);stow(w)
        try:move(w,'base',forward=1)
        except ValueError:
            assert w.last_action and w.last_action['kind']=='base' and w.last_action['status']=='blocked'
        distance=float(np.linalg.norm(w.base_pose()[:2]-CHARGERS[1]));assert distance>.24
        assert rejected(lambda:w.command(dict(kind='dock',request_id='bedroom-dock',parameters={})))
        names=('charger_back1','bedroom_charger_east_guard','bedroom_charger_north_guard','bedroom_charger_south_guard')
        guards={n:dict(center=w.model.geom(n).pos.tolist(),half_size=w.model.geom(n).size.tolist()) for n in names}
        # Four overlapping, immobile bars form a closed planar obstacle. Their
        # height overlaps the base at every allowed pose; no semantic disable.
        assert all(g['half_size'][2]==.22 for g in guards.values())
        result['checks']['bedroom_port_physically_inaccessible']=True
        result['measurements']['bedroom_attempt_contact_distance_m']=distance;result['measurements']['bedroom_guards']=guards
        for i in (0,2):
            w.docked=False;relocate_for_fixture(w,CHARGERS[i][0]+.15,CHARGERS[i][1],0);w.begin_session(.1,3600);w.step(100)
            w.command(dict(kind='dock',request_id='usable-'+str(i),parameters={}));assert w.docked
        result['checks']['living_room_and_kitchen_dock']=True
        result['passed']=all(result['checks'].values())
        return result
    finally:
        if w:
            save(out/'last-world.json',w.snapshot())
            save(out/'last-contacts.json',[dict(a=w.model.geom(int(c.geom1)).name,b=w.model.geom(int(c.geom2)).name,distance=float(c.dist)) for c in w.data.contact])
            w.close()
        save(out/'geometry.json',result)


def run(out):
    out.mkdir(parents=True,exist_ok=False);result=dict(passed=False,stage='throwaway-reliability-revision',official_sessions=0,model_calls=0,checks={},evidence={})
    try:
        protected=[DEFAULT_ROOT/'official/apartment-v1',DEFAULT_ROOT/'official/apartment-v1-restart001',DEFAULT_ROOT/'failed-launches/APARTMENT-v1-baseline-launch-001',DEFAULT_ROOT/'engineering/APARTMENT-reliability-live001']
        before={str(p):inventory(p) for p in protected};save(out/'protected-before.json',before)
        for name,call in [('real_closeout_artifacts',closeout_artifacts),('paired_official_routes',paired_official_routes),('checkpoint_faults',checkpoint_faults),('immutable_recovery',recovery_fixture),('structured_error',error_fixture),('clock_discontinuity',clock_fixture),('geometry',geometry_fixture)]:
            result['evidence'][name]=call(out/name);result['checks'][name]=result['evidence'][name]['passed'];save(out/'progress.json',result)
        import flow_engineering,h2_engineering,repair_lifecycle_engineering
        # Actual socket pressure reaches the original cap, with byte equality,
        # backpressure and cancellation release. Repeat independent transfers.
        result['evidence']['flow']=[asyncio.run(flow_engineering.exercise()) for _ in range(3)]
        result['checks']['queue_headroom']=all(r['passed'] for r in result['evidence']['flow'])
        result['checks']['h2_cancellation_retirement']=h2_engineering.run(out/'h2')
        result['checks']['native_inode_checkpoint_lifecycle']=repair_lifecycle_engineering.run(out/'lifecycle')
        after={str(p):inventory(p) for p in protected};save(out/'protected-after.json',after)
        result['checks']['prior_evidence_unchanged']=before==after
        result['passed']=all(result['checks'].values())
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
    save(out/'result.json',result);print(canonical({k:v for k,v in result.items() if k!='evidence'}).decode());return result['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.output) else 1)
