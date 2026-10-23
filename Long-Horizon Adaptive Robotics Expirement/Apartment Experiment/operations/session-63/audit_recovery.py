"""Independent no-model readback of the qualified branch, from original bytes."""
import stat
import traceback
from common63 import *

def main():
    AUDIT.mkdir(parents=True,exist_ok=False)
    result=dict(passed=False,checks={},started_utc=now(),model_calls=0,official_launches=0)
    try:
        assert_manifest('audit');assert_manifest('qualification')
        q=queue('status',read(HERE/'qualification-queue.json')['id'])
        assert q['state']=='succeeded' and type(q['exit_status']) is int and q['exit_status']==0
        qualified=read(QUAL/'result.json');assert qualified['passed'] and all(v is True for v in qualified['checks'].values())
        assert sha(QUAL/'result.json')==sha(HERE/'qualification-result.json')
        result['qualification_queue']=q;result['qualification_result']=ref(QUAL/'result.json')
        result['checks']['exact_qualification_sources_and_terminal_receipts']=True
        branch=QUAL/'candidate';cp=branch/'checkpoints/session-00005'
        state=read(CP/'state.json')
        parent=inventory(PARENT);assert parent==read(QUAL/'parent-before.json')
        baseline=inventory(PAIR/'baseline');assert baseline==read(QUAL/'baseline-before.json')==read(legacy.QUAL/'baseline-before.json')
        assert inventory(PAIR/'maps')==read(QUAL/'maps-before.json')==read(legacy.QUAL/'maps-before.json')
        assert read(PAIR/'maps-lineage.json')==read(QUAL/'maps-lineage-before.json')
        result['preservation']=dict(parent_files=len(parent),parent_inventory_sha256=hashlib.sha256(canonical(parent)).hexdigest(),
            baseline_files=len(baseline),baseline_inventory_sha256=hashlib.sha256(canonical(baseline)).hexdigest())
        result['checks']['full_parent_baseline_and_pristine_start_preserved']=True
        # Construct expected data-bearing branch inventory independently of the
        # preparer and verify that no extra file can carry abandoned learning.
        actual=inventory(branch);expected={}
        for name in ('schedule.json','config.json','initial-filesystem.json'):expected[name]=parent[name]
        for name,row in inventory(CP).items():
            if name.startswith(('filesystem/','filesystem-objects/')) or name=='filesystem-namespace.json':expected[name]=row
        for n in range(1,6):
            sid='session-'+str(n).zfill(5)
            for prefix in ('sessions/'+sid+'/','filesystem-before-'+sid+'/','checkpoints/'+sid+'/'):
                expected.update({name:row for name,row in parent.items() if name.startswith(prefix)})
        raw=(PARENT/'events.jsonl').read_bytes()[:state['log_bytes']]
        expected['events.jsonl']=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        replay_index=read(CP/'replay-index.json')
        for row in replay_index:expected['replay/'+row['file']]=parent['replay/'+row['file']]
        expected['replay/index.json']=dict(bytes=(CP/'replay-index.json').stat().st_size,sha256=sha(CP/'replay-index.json'))
        events=[json.loads(line) for line in raw.splitlines()]
        for row in events:
            if row['kind']=='sensor_capture':
                name='sensors/frame-'+str(row['payload']['sequence']).zfill(7)+'.png'
                assert parent[name]['sha256']==row['payload']['image_sha256'];expected[name]=parent[name]
        metadata={'run.json','recovery-ready.json','latest-checkpoint.json'}
        assert set(actual)==set(expected)|metadata,'Unexpected branch file could leak abandoned tail'
        assert {name:row for name,row in actual.items() if name not in metadata}==expected
        result['checks']['exact_independent_prefix_inventory_no_session6_leakage']=True
        namespace=read(CP/'filesystem-namespace.json');assert namespace==read(branch/'filesystem-namespace.json')
        for name,inode in namespace['paths'].items():
            node=namespace['nodes'][str(inode)]
            assert name.startswith('/') and '..' not in Path(name).parts
            if stat.S_ISREG(node['mode']):
                p=branch/'filesystem-objects'/node['sha256']
                assert p.stat().st_size==node['size'] and sha(p)==node['sha256']
                assert (branch/'filesystem'/name.lstrip('/')).read_bytes()==p.read_bytes()
        from recording import verify_checkpoint,verify_prefix
        cpchecks=[]
        for n in range(1,6):
            folder=branch/'checkpoints'/('session-'+str(n).zfill(5))
            cpchecks.append(dict(session=n,receipt=verify_checkpoint(folder),prefix=verify_prefix(branch,folder)))
        assert cpchecks[-1]['receipt']['manifest_sha256']==EXPECTED_CP and cpchecks[-1]['receipt']['state_sha256']==EXPECTED_STATE
        from world import World
        world=World()
        try:world.restore(state['world']);assert canonical(world.snapshot())==canonical(state['world'])
        finally:world.close()
        restored=read(QUAL/'actual-controller-restore.json')
        for key in ('world','position','sessions','completed','session_success','config','condition','phase','schedule_sha256'):assert restored[key]==state[key]
        result['checkpoints']=cpchecks;result['checks']['checkpoint_manifest_inodes_physics_rng_task_and_battery_exact']=True
        result['native_history']=native_history()
        import journal_reader
        w=QUAL/'actual-workspace';loc=read(w/'location.json')
        with (w/'journal/mutations.jsonl').open('rb') as f:mounted=json.loads(f.readline())['state']
        assert mounted==namespace
        proof=journal_reader.verify(w/'journal',loc['run_id'])
        end=read(w/'journal/native-exit.json');cleanup=read(w/'cleanup-001.json')
        assert proof['records']==end['final_sequence'] and proof['final_state_sha256']==end['final_state_sha256']
        assert cleanup['retired'] and cleanup['normal_requested'] and not cleanup['mounted'] and cleanup['service_exit']==0 and not cleanup['errors']
        native=read(QUAL/'actual-native/client/result.json')
        assert native['success'] and native['preflight_passed'] and not native.get('model_started')
        fresh=read(QUAL/'fresh-session6-fixture.json')['state']
        assert fresh['sessions']==6 and fresh['position']==2 and not fresh['session_success'] and fresh['completed']==state['completed']
        result['checks']['actual_native_mount_journal_isolation_preflight_and_fresh_session6']=True
        rejections={p.stem:read(p) for p in (QUAL/'rejections').glob('*.json')}
        assert len(rejections)==8 and all(r['expected_rejection'] for r in rejections.values())
        assert 'Recovery evidence must remain on D:' in rejections['frozen-c-destination-guard']['error']
        assert not (QUAL/'forbidden-frozen-command').exists() and not (QUAL/'duplicate').exists() and not (QUAL/'partial-retry').exists()
        assert not (QUAL/'partial/recovery-ready.json').exists() and (QUAL/'partial/recovery-preparation-failure.json').exists()
        for name in ('filesystem-corruption','event-tail-leakage','inode-namespace-corruption','claim-destination-mismatch'):
            case=QUAL/'rejections'/name;assert sha(case/'before.bin')!=sha(case/'rejected.bin')
        result['checks']['retained_success_and_eight_expected_rejections']=True
        from run import verify_run
        branch_run=verify_run(branch,True)
        original=read(PARENT/'run.json')
        for key,value in original.items():
            if key!='branch_id':assert branch_run[key]==value,key
        assert branch_run['branch_id']!=original['branch_id']
        binding=branch_run['recovery'];claim=read(binding['claim']);ready=read(branch/'recovery-ready.json')
        assert Path(claim['destination']).resolve()==branch.resolve() and claim['branch_id']==branch_run['branch_id']
        assert ready['claim_sha256']==sha(binding['claim']) and ready['parent_inventory_sha256']==result['preservation']['parent_inventory_sha256']
        assert ready['completed_sessions_preserved']==5 and ready['assignments_preserved']==2 and ready['cumulative_interrupted_sessions']==1
        result['checks']['unmodified_official_runner_accepts_genuine_bound_candidate']=True
        result['source']=frozen_identity();result['parent_checkpoint']=parent_checkpoint()
        # Full original abandoned tail remains independently readable.
        from observe_maps import prefix
        all_events,eventproof=prefix(PARENT/'events.jsonl')
        previous='0'*64
        for sequence,event in enumerate(all_events,1):
            payload=dict(event);digest=payload.pop('sha256')
            assert payload['sequence']==sequence and payload['previous']==previous
            assert hashlib.sha256(canonical(payload)).hexdigest()==digest
            previous=digest
        for row in all_events:
            if row['kind']=='sensor_capture':assert sha(PARENT/'sensors'/('frame-'+str(row['payload']['sequence']).zfill(7)+'.png'))==row['payload']['image_sha256']
        all_replay=read(PARENT/'replay/index.json')
        for row in all_replay:assert sha(PARENT/'replay'/row['file'])==row['sha256']
        result['original_recordings']=dict(events=len(all_events),replay_chunks=len(all_replay),event_proof=eventproof)
        result['checks']['failed_parent_entire_tail_and_frozen_identity_reauthenticated']=True
        result['quiescence']=quiet();assert result['quiescence']['passed']
        result['capacity']=capacity();assert result['capacity']['c_headroom_pass'] and result['capacity']['d_headroom_pass']
        result['checks']['actual_retirement_and_full_unchanged_storage_allowance']=True
        result['passed']=True
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
    result['finished_utc']=now();save(AUDIT/'result.json',result);save(HERE/'audit-result.json',result)
    print(json.dumps({k:result.get(k) for k in ('passed','checks','error','traceback')}),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
