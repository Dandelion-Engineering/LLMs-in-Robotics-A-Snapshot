"""One no-model operator qualification; unexpected gate failure is terminal."""
import asyncio
import traceback
from common63 import *
from prepare_branch import prepare, verify_branch

def expect_rejection(name,call,expected):
    try:call()
    except Exception as error:
        assert isinstance(error,expected), repr(error)
        result=dict(name=name,expected_rejection=True,error=repr(error),traceback=traceback.format_exc())
        save(QUAL/'rejections'/(name+'.json'),result)
        return result
    raise AssertionError('Expected rejection was accepted: '+name)

def main():
    QUAL.mkdir(parents=True,exist_ok=False)
    result=dict(passed=False,checks={},started_utc=now(),provider_model_calls=0,official_launches=0)
    c=w=g=None
    try:
        assert_manifest('qualification')
        result['quiet_before']=quiet();assert result['quiet_before']['passed'],'Conflicting processes/mounts/jobs/monitors'
        result['capacity_before']=capacity();assert result['capacity_before']['c_headroom_pass'] and result['capacity_before']['d_headroom_pass']
        result['frozen_identity']=frozen_identity();result['checks']['unchanged_official_source_environment_certificate_baseline']=True
        result['checkpoint']=parent_checkpoint();result['native_history']=native_history()
        result['checks']['five_accepted_sessions_and_one_abandoned_invocation_authenticated']=True
        print('Official identity, checkpoint and six native histories authenticated.',flush=True)
        before=inventory(PARENT);save(QUAL/'parent-before.json',before)
        baseline=inventory(PAIR/'baseline');save(QUAL/'baseline-before.json',baseline)
        assert baseline==read(legacy.QUAL/'baseline-before.json'),'Baseline differs from previously authenticated complete inventory'
        save(QUAL/'maps-before.json',inventory(PAIR/'maps'))
        save(QUAL/'maps-lineage-before.json',read(PAIR/'maps-lineage.json'))
        result['checks']['complete_baseline_inventory_matches_prior_117885_file_readback']=True
        from recovery import prepare_recovery
        rejected=expect_rejection('frozen-c-destination-guard',lambda:prepare_recovery(PARENT,QUAL/'forbidden-frozen-command','explicit operator guard qualification',True),ValueError)
        assert 'Recovery evidence must remain on D:' in rejected['error']
        assert not (QUAL/'forbidden-frozen-command').exists()
        result['checks']['frozen_d_guard_still_rejects_c_without_mutation']=True
        branch=QUAL/'candidate';claim=QUAL/'claims/success'
        result['candidate']=prepare(branch,claim,qualification=True)
        result['checks']['separate_c_branch_normal_official_verification_passes']=True
        rejected=expect_rejection('duplicate-parent-claim',lambda:prepare(QUAL/'duplicate',claim,qualification=True),AssertionError)
        assert 'Parent already claimed' in rejected['error'] and not (QUAL/'duplicate').exists()
        def injected(phase):raise RuntimeError('Deliberate operator fixture interruption after exclusive claim')
        expect_rejection('partial-copy-failure',lambda:prepare(QUAL/'partial',QUAL/'claims/partial',qualification=True,fault=injected),RuntimeError)
        assert (QUAL/'partial/recovery-preparation-failure.json').exists() and not (QUAL/'partial/recovery-ready.json').exists()
        rejected=expect_rejection('partial-claim-cannot-be-reused',lambda:prepare(QUAL/'partial-retry',QUAL/'claims/partial',qualification=True),AssertionError)
        assert 'Parent already claimed' in rejected['error'] and not (QUAL/'partial-retry').exists()
        result['checks']['duplicate_and_partial_preparation_fail_closed']=True
        # Corrupt only a private fixture, retaining exact before/failed bytes and
        # rejection receipts. Restore the fixture after each declared test.
        for name,path,change in (
            ('filesystem-corruption',branch/'filesystem/SummaryOfOnlyNecessaryContext.md',lambda raw:raw+b'\nOPERATOR NEGATIVE FIXTURE\n'),
            ('event-tail-leakage',branch/'events.jsonl',lambda raw:raw+(PARENT/'events.jsonl').read_bytes()[len(raw):]),
            ('inode-namespace-corruption',branch/'filesystem-namespace.json',lambda raw:raw+b' '),
            ('claim-destination-mismatch',claim/'claim.json',lambda raw:json.dumps(dict(json.loads(raw),destination=str(QUAL/'wrong'))).encode()),
        ):
            original=path.read_bytes();bad=change(original);case=QUAL/'rejections'/name;case.mkdir()
            (case/'before.bin').write_bytes(original);(case/'rejected.bin').write_bytes(bad)
            path.write_bytes(bad)
            try:expect_rejection(name,lambda:verify_branch(branch),AssertionError)
            finally:path.write_bytes(original)
            assert path.read_bytes()==original
        result['checks']['content_event_inode_and_claim_corruption_rejected']=True
        assert verify_branch(branch)['passed']
        print('Branch creation and rejection fixtures passed; restoring real inode/physics state.',flush=True)
        actual=QUAL/'actual-restore'
        shutil.copytree(branch,actual)
        from controller import Controller
        from native_runtime import Workspace,Guest
        import journal_reader
        state=read(CP/'state.json')
        c=Controller(actual,read(actual/'schedule.json'),read(actual/'config.json'),'maps','official',actual/'checkpoints/session-00005')
        endpoint=c.start();restored=c.ask('private')
        for key in ('world','position','sessions','completed','session_success','config','condition','phase','schedule_sha256'):
            assert restored[key]==state[key],key
        assert restored['sessions']==5 and restored['position']==2
        save(QUAL/'actual-controller-restore.json',restored)
        w=Workspace(QUAL/'actual-workspace',actual/'filesystem','session63-checkpoint5-qualification')
        with (w.evidence/'journal/mutations.jsonl').open('rb') as f:initial=json.loads(f.readline())['state']
        assert initial==read(CP/'filesystem-namespace.json'),'Native inode namespace changed during actual mount'
        result['checks']['actual_controller_world_rng_pose_battery_task_and_native_inode_restore_exact']=True
        w.start_clock_bridge(c)
        g=Guest(QUAL/'actual-native',w,endpoint,c);g.qualify()
        asyncio.run(g.model(timeout=120,preflight=True))
        native=read(QUAL/'actual-native/client/result.json')
        assert native['success'] and native['preflight_passed'] and not native.get('model_started')
        assert g.close();g=None
        final,proof=w.close()
        reread=journal_reader.verify(w.evidence/'journal',w.run_id)
        assert proof['passed'] and reread['passed'] and inventory(final)==inventory(CP/'filesystem')
        assert w.closed and w.process.poll()==0
        result['actual_journal']={k:v for k,v in reread.items() if k not in ('state','states','read_events')}
        w=None
        fresh=c.ask('start');newstate=c.ask('private')
        assert newstate['sessions']==6 and newstate['position']==2 and newstate['completed']==state['completed']
        assert not newstate['session_success'] and not newstate['world']['docked']
        save(QUAL/'fresh-session6-fixture.json',dict(start=fresh,state=newstate,provider_calls=0))
        c.close();assert not c.owner.is_alive();c=None
        result['checks']['isolated_preflight_no_model_and_fresh_session6_at_same_assignment']=True
        result['quiet_after']=quiet();assert result['quiet_after']['passed']
        result['checks']['actual_runtime_mount_and_viewer_retirement']=True
        assert inventory(PARENT)==before
        assert inventory(PAIR/'baseline')==baseline
        assert inventory(PAIR/'maps')==read(QUAL/'maps-before.json')
        assert read(PAIR/'maps-lineage.json')==read(QUAL/'maps-lineage-before.json')
        result['identity_after']=frozen_identity()
        result['checks']['failed_parent_baseline_pristine_maps_and_source_preserved']=True
        result['capacity_after']=capacity();assert result['capacity_after']['c_headroom_pass'] and result['capacity_after']['d_headroom_pass']
        result['passed']=True
    except BaseException as error:
        result.update(error=repr(error),traceback=traceback.format_exc())
    finally:
        for name,obj,method in [('guest',g,'close'),('workspace',w,'close'),('controller',c,'close')]:
            if obj:
                try:getattr(obj,method)()
                except BaseException as error:result[name+'_cleanup_error']=repr(error)
        result['finished_utc']=now();save(QUAL/'result.json',result);save(HERE/'qualification-result.json',result)
    print(json.dumps({k:result.get(k) for k in ('passed','checks','error','traceback')}),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
