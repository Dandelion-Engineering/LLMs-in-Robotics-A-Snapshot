"""Complete the preserved first audit after diagnosing a recovery-epoch reader assumption.
No scientific rerun. Five authenticated first-stage gates plus four remaining gates,
with a new full immutable-root hash pass and fresh actual retirement census.
"""
from audit_endpoint import *


def audit_completion(out):
    out.mkdir(parents=True,exist_ok=False)
    r=dict(passed=False,checks={})
    try:
        manifest=c.read(OPS/'audit-completion-manifest.json')
        for row in manifest['readers']+manifest['prior_evidence']:
            assert c.sha(row['uri'])==row['sha256'],row['uri']
        original=c.read(c.BASE/'endpoint-session74/audit001/result.json')
        first_queue=c.queue('status','20261011T003930977976Z-2a7d4e8b')
        assert first_queue['state']=='failed' and first_queue['exit_status']==1
        assert not original['passed'] and original['error']=='AssertionError()'
        assert len(original['checks'])==5 and all(x is True for x in original['checks'].values())
        assert "len(ends)==1" in original['traceback']
        r=dict(original)
        r['first_stage_failure']=dict(queue=first_queue,error=r.pop('error'),traceback=r.pop('traceback'),finished_utc=r.pop('finished_utc'),result=c.ref(c.BASE/'endpoint-session74/audit001/result.json'))
        r['completion_started_utc']=c.now()
        before={}
        for label,row in r['preservation_before'].items():
            assert c.sha(row['inventory']['uri'])==row['inventory']['sha256']
            before[label]=c.read(row['inventory']['uri'])
        q=c.queue('status','20261010T185932431096Z-5e6874a0')
        assert q==r['scientific_queue'] and q['state']=='succeeded' and type(q['exit_status']) is int and q['exit_status']==0
        assert c.frozen_identity()==r['source']
        latest=Path(c.read(c.DEST/'latest-checkpoint.json')['path'])
        assert latest==c.DEST/'checkpoints/session-00034'
        state=c.read(latest/'state.json');events=chain(c.DEST/'events.jsonl')
        assert c.sha(c.DEST/'events.jsonl')==r['recordings']['accepted']['event_sha256']
        sessions=[(f'accepted-{n:05d}',c.DEST/'sessions'/f'session-{n:05d}') for n in range(1,35)]
        sessions.append(('abandoned-original-00006',c.PARENT/'sessions/session-00006'))
        model=mujoco.MjModel.from_xml_string(xml());data=mujoco.MjData(model)
        print('Authenticated preserved first stage and failed-reader diagnosis; completing remaining four gates.',flush=True)
        starts = [e for e in events if e['kind']=='session_started']; closes = [e for e in events if e['kind']=='session_closed']; successes = [e for e in events if e['kind']=='task_success']
        assert [e['payload']['session'] for e in starts] == [e['payload']['session'] for e in closes] == list(range(1,35))
        assert sum(e['kind']=='resumed' for e in events)==1 and len(successes)==14
        table = []; docks = []
        for completed in state['completed']:
            pos = completed['position']; members = [e for e in starts if e['payload']['assignment_position']==pos]
            adv = [e for e in closes if e['payload']['assignment_advanced'] and e['payload']['next_position']==pos+1]
            assert len(adv)==1 and adv[0]['payload']['session']==completed['session']==members[-1]['payload']['session']
            assert adv[0]['sim_time']==completed['sim_time'] and all(e['payload']['task']==completed['kind'] for e in members)
            table.append(dict(position=pos, task=completed['kind'], sessions=[e['payload']['session'] for e in members], advancing_session=completed['session']))
        assert [x['position'] for x in table] == list(range(21)) and Counter(x['task'] for x in table)==dict(bedroom=7,kitchen=7,throwing=7)
        admitted = {e['payload']['request_id'] for e in events if e['kind']=='command_admitted'}
        for start,close in zip(starts,closes):
            sid=start['payload']['session']; work=start['payload']['work_s']; assert work==(600 if start['payload']['task']=='throwing' else 360)
            requested=[e for e in events if e['kind']=='command_requested' and e['payload']['session']==sid and e['payload']['request']['kind']=='dock' and e['payload']['request']['request_id'] in admitted]
            assert requested; dock=requested[-1]; assert dock['sim_time']-start['sim_time']>=work
            ends=[e for e in events if e['kind']=='command_terminal' and e['payload'].get('kind')=='dock' and e['payload'].get('request_id')==dock['payload']['request']['request_id']]
            within = [e for e in ends if start['sequence'] < e['sequence'] < close['sequence']]
            assert len(within)==1 and within[0]['payload']['status']=='completed', (sid,within)
            extra = [e for e in ends if e not in within]
            if extra:
                assert sid==5 and len(extra)==1
                resumed = next(e for e in events if e['kind']=='resumed')
                first_new_request = next(e for e in events if e['sequence']>resumed['sequence'] and e['kind']=='command_requested')
                assert resumed['sequence'] < extra[0]['sequence'] < first_new_request['sequence']
                assert extra[0]['clock_epoch']!=within[0]['clock_epoch']
                assert extra[0]['payload']==within[0]['payload']==c.read(c.DEST/'checkpoints/session-00005/state.json')['world']['last_action']
                assert sum(e['kind']=='command_requested' and e['payload']['request']['request_id']==dock['payload']['request']['request_id'] for e in events)==1
                r['restored_terminal_reemission']=dict(original=within[0],after_resume=extra[0],single_request=True,identical_checkpoint_payload=True)
            boundary=c.read(c.DEST/'checkpoints'/f'session-{sid:05d}'/'state.json')['world']
            assert boundary['docked'] and boundary['active'] is None and boundary['last_action']['request_id']==dock['payload']['request']['request_id']
            docks.append(dict(session=sid,task=start['payload']['task'],work_window_s=work,dock_requested_after_s=dock['sim_time']-start['sim_time'],closed_after_s=close['sim_time']-start['sim_time']))
        r['accounting']=dict(accepted_closed=34,original_accepted_calls=5,continuation_calls=29,abandoned_original_calls=1,total_calls=35,unclosed=0,advancements=21,household_latches=14,timed_throwing_advancements=7,assignment_table=table,nonadvancing_sessions=[e['payload']['session'] for e in closes if not e['payload']['assignment_advanced']],event_counts=dict(Counter(e['kind'] for e in events)))
        r['docking_and_timed_windows']=docks
        finish_check(r,'accepted_assignment_accounting_fixed_windows_and_normal_docking')

        physical=[]; index=c.read(c.DEST/'replay/index.json'); firsts=[p['first'] for p in index]
        for completed in state['completed']:
            if completed['kind']=='throwing': continue
            sid=completed['session']; found=[e for e in successes if e['payload']['session']==sid and e['payload']['position']==completed['position']]; assert len(found)==1
            event=found[0]; cp=c.read(c.DEST/'checkpoints'/f'session-{sid:05d}'/'state.json'); w=cp['world']; assignment=w['assignment']
            assert assignment['position']==completed['position'] and assignment['kind']==completed['kind']
            ci=max(0,bisect.bisect_right(firsts,event['sim_time'])-1)
            with np.load(c.DEST/'replay'/index[ci]['file'],allow_pickle=False) as z:
                k=int(np.searchsorted(z['t'],event['sim_time']))
                if k==len(z['t']): ci+=1;k=0
            with np.load(c.DEST/'replay'/index[ci]['file'],allow_pickle=False) as z:
                data.qpos[:]=z['qpos'][k];data.qvel[:]=z['qvel'][k];data.time=float(z['t'][k]);mujoco.mj_forward(model,data)
                near=phys.geometry(model,data,assignment);offset=data.time-event['sim_time'];assert 0<=offset<=.04
            mujoco.mj_setState(model,data,np.array(w['physics']),mujoco.mjtState.mjSTATE_INTEGRATION);mujoco.mj_forward(model,data)
            boundary=phys.geometry(model,data,assignment)
            objects=[t[0] for t in TOYS] if completed['kind']=='bedroom' else ['cup']
            assert all(w['pickups'][name] and w['grip_candidate']!=name for name in objects)
            assert w['docked'] and w['active'] is None
            physical.append(dict(position=completed['position'],task=completed['kind'],session=sid,event_sequence=event['sequence'],event_sim_time=event['sim_time'],replay_file=index[ci]['file'],sample=k,offset_s=offset,near_event=near,boundary=boundary,pickup_and_release_flags=True))
        assert len(physical)==14
        r['physical_household_readback']=physical
        r['physical_corroboration']=dict(trusted_latched_successes=14,first_retained_sample_passes=sum(x['near_event']['passed'] for x in physical),close_boundary_passes=sum(x['boundary']['passed'] for x in physical),corroborated_at_either_observed_time=sum(x['near_event']['passed'] or x['boundary']['passed'] for x in physical),exact_event_sample_count=sum(x['offset_s']==0 for x in physical),maximum_post_event_offset_s=max(x['offset_s'] for x in physical))
        finish_check(r,'physical_readback_of_fourteen_latches_with_snapshot_offsets_preserved')

        r['retirement']=retirement(sessions,[q,r['parent_checkpoint']['parent_queue']],[c.DEST,c.PARENT])
        finish_check(r,'actual_native_filesystem_controller_and_viewer_retirement')
        r['capacity_after']=c.capacity(); assert r['capacity_after']['c_headroom_pass'] and r['capacity_after']['d_headroom_pass']
        for label,root in [('accepted',c.DEST),('failed_parent',c.PARENT),('baseline',c.PAIR/'baseline'),('pristine_maps',c.PAIR/'maps')]:
            print('Checking unchanged full inventory: '+label,flush=True)
            after=c.inventory(root); assert before[label]==after,label
            c.save(out/(label+'-after.json'),after)
            r.setdefault('preservation_after',{})[label]=dict(files=len(after),inventory=c.ref(out/(label+'-after.json')))
            print('Preserved: '+label+' ('+str(len(after))+' files)',flush=True)
        r['evidence'].update(readers=manifest['readers'],observation=c.ref(c.BASE/'observations/session-74-4145cec682d64668b1408c5047a0af6a.json'),route=c.ref(c.HERE/'continuation-route.json'),execution=c.ref(c.read(c.DEST/'latest-execution.json')['path']),final_checkpoint=c.ref(latest/'manifest.json'),final_state=c.ref(latest/'state.json'))
        finish_check(r,'all_four_full_inventories_unchanged_and_full_storage_reserves')
        r['limitations']=[
            'Recovered checkpoint-5 history has two clock epochs and one abandoned original session-6 model invocation; never uninterrupted.',
            'Fourteen household successes use the frozen physical latch. Later geometry persistence is not an additional completion rule; replay snapshot offsets and predicate failures remain visible.',
            'Seven throwing advancements certify timed working windows, not mastery or a complete throwing-attempt census.',
            'Sensor content hashes and all transport streams are authenticated; no new model input, physics stepping or robot commands were issued.',
            'Baseline full byte preservation is checked without recomputing its scientific outcomes; retain its session-7 drawer persistence and session-16 +16 ms toy-speed snapshot caveats.',
            'C: versus D: storage and host/recovery timing remain part of provenance. No Baseline-versus-Maps comparison, independent replicate, cost analysis or causal memory claim is made.'
        ]
        r['passed']=all(r['checks'].values())
    except BaseException as error:r.update(passed=False,error=repr(error),traceback=traceback.format_exc())
    r['finished_utc']=c.now();c.save(out/'result.json',r)
    print(json.dumps({k:r.get(k) for k in ('passed','checks','error','traceback','finished_utc')}),flush=True)
    return r['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    raise SystemExit(0 if audit_completion(a.output.resolve()) else 1)
