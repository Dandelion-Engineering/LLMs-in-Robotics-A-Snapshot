"""Queued, read-only audit of the accepted Maps checkpoint-5 continuation.

Never launches or steps a world. mj_forward reconstructs retained states only.
All output is exclusive-create operator evidence outside the scientific roots.
"""
import argparse
import bisect
from collections import Counter
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import runpy
import socket
import subprocess
import sys
import traceback

OPS = Path(__file__).resolve().parent
sys.path.insert(0, str(OPS.parent / 'session-63'))
import common63 as c
from audit import chain, native
from recording import verify_checkpoint, verify_prefix
from recovery import terminal
from repair_validation import transport_readback
from run import verify_run, validate_closeout
import journal_reader
import mujoco
import numpy as np
from scene import xml, TOYS

PHYS = OPS.parent / 'session-57/audit_physical_retirement_v2.py'
spec = importlib.util.spec_from_file_location('retained_physical_reader57', PHYS)
phys = importlib.util.module_from_spec(spec)
spec.loader.exec_module(phys)


def finish_check(result, name):
    result['checks'][name] = True
    print('Passed: ' + name, flush=True)


def replay(root, model):
    index = c.read(root / 'replay/index.json')
    previous = None
    epochs = {}
    samples = 0
    min_dt, max_dt = float('inf'), 0.0
    wall_backwards, max_wall_gap = 0, 0
    transitions = []
    for part in index:
        p = root / 'replay' / part['file']
        assert c.sha(p) == part['sha256'], str(p)
        with np.load(p, allow_pickle=False) as z:
            assert set(z.files) == {'t', 'qpos', 'qvel', 'wall_ns', 'monotonic_ns'}
            n = part['samples']
            assert z['t'].shape == z['wall_ns'].shape == z['monotonic_ns'].shape == (n,)
            assert z['qpos'].shape == (n, model.nq) and z['qvel'].shape == (n, model.nv)
            assert all(np.isfinite(z[k]).all() for k in z.files)
            assert float(z['t'][0]) == part['first'] and float(z['t'][-1]) == part['last']
            epoch = part['clock_epoch']
            prior = epochs.get(epoch)
            ts = z['t'] if prior is None else np.r_[prior[0], z['t']]
            ms = z['monotonic_ns'] if prior is None else np.r_[prior[1], z['monotonic_ns']]
            assert np.all(np.diff(ts) >= 0) and np.all(np.diff(ms) >= 0)
            dt = np.diff(ts)
            if len(dt): min_dt, max_dt = min(min_dt, float(dt.min())), max(max_dt, float(dt.max()))
            ws = z['wall_ns'] if previous is None else np.r_[previous['wall_ns'], z['wall_ns']]
            delta = np.diff(ws)
            wall_backwards += int(np.sum(delta < 0))
            if len(delta): max_wall_gap = max(max_wall_gap, int(delta.max()))
            if previous and previous['epoch'] != epoch:
                transitions.append(dict(previous=previous, next=dict(epoch=epoch, sim_time=float(z['t'][0]),
                    wall_ns=int(z['wall_ns'][0]), monotonic_ns=int(z['monotonic_ns'][0]))))
                assert float(z['t'][0]) >= previous['sim_time']
            epochs[epoch] = (float(z['t'][-1]), int(z['monotonic_ns'][-1]))
            previous = dict(epoch=epoch, sim_time=float(z['t'][-1]), wall_ns=int(z['wall_ns'][-1]), monotonic_ns=int(z['monotonic_ns'][-1]))
            samples += n
    return dict(chunks=len(index), samples=samples, epochs=len(epochs), epoch_transitions=transitions,
        min_sim_delta_s=min_dt, max_sim_delta_s=max_dt, wall_backward_steps=wall_backwards,
        max_wall_gap_s=max_wall_gap / 1e9, final_sim_time=previous['sim_time'], all_arrays_decoded=True)


def retirement(sessions, queues, roots):
    helper = OPS.parent / 'session-42/capture_health.py'
    identity = runpy.run_path(str(helper))['windows_identity']
    windows, claims, normal = [], [], []
    for label, session in sessions:
        location = c.read(session / 'workspace/location.json')
        clean = c.read(session / 'workspace/cleanup-001.json')
        end = c.read(session / 'workspace/journal/native-exit.json')
        ret = c.read(session / 'native/codehost-owner-retirement-v3.json')
        assert clean['normal_requested'] and clean['retired'] and clean['log_closed'] and not clean['mounted'] and not clean['errors']
        assert type(clean['service_exit']) is int and clean['service_exit'] == 0
        assert end['libfuse_main_return'] == 0 and not end['requested_sigterm']
        assert ret['qualified'] and ret['windows_exit_code'] == 0 and not ret['normal_wait_timed_out'] and not ret['windows_wrapper_killed_after_linux_retired']
        assert ret['observations'] and all(o['retired'] and not o['kill_sent'] and not o['outer_same_process'] and not o['namespace_members'] and o['namespace_evidence_available'] for o in ret['observations'])
        owners = [p for name in ('native-owner.json', 'codehost-native-owner-v3.json') for p in session.rglob(name)]
        assert len(owners) == 2
        for p in owners:
            obs = identity(c.read(p)); assert obs['state'] in ('absent', 'exited', 'pid_reused'), obs
            windows.append(dict(session=label, owner=c.ref(p), observation=obs))
        claims.append(dict(session=label, run=location['run'], boot_id=clean['identity']['boot_id'], filesystem=clean['identity'], native=ret['observations'][0]['identity']))
        normal.append(dict(session=label, cleanup=c.ref(session/'workspace/cleanup-001.json'), native_exit=c.ref(session/'workspace/journal/native-exit.json'), retirement=c.ref(session/'native/codehost-owner-retirement-v3.json')))
    probe = subprocess.run(['wsl.exe', '-d', 'Ubuntu-24.04', '--', 'python3', '-B', '-c', phys.LINUX_PROBE],
        input=json.dumps(claims), capture_output=True, text=True, encoding='utf-8', timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
    assert probe.returncode == 0, probe.stderr
    linux = json.loads(probe.stdout)
    assert not linux['process_matches'] and not linux['mounts'] and not linux['unreadable_cmdlines']
    assert not any(x['same_original_process'] for x in linux['identities'])
    hosts = []
    for label, q, root in zip(('continuation', 'failed_parent'), queues, roots):
        viewer = c.read(root / 'viewer.json')
        ended = datetime.fromisoformat(q['ended_at'].replace('Z', '+00:00')).timestamp()
        records = []
        for role, pid in [('controller', q['child_pid']), ('viewer', viewer['pid'])]:
            obs = identity(dict(pid=pid, process_creation_filetime=0))
            if obs['state'] == 'pid_reused':
                created = obs['actual_creation_filetime'] / 1e7 - 11644473600
                assert obs['exit_code'] != 259 or created > ended, (role, obs)
                obs['retirement_basis'] = 'exited' if obs['exit_code'] != 259 else 'PID created after original execution ended'
            else: assert obs['state'] == 'absent', (role, obs)
            records.append(dict(role=role, observation=obs))
        with socket.socket() as sock:
            sock.settimeout(2); listening = sock.connect_ex(('127.0.0.1', int(viewer['url'].rsplit(':', 1)[1]))) == 0
        assert not listening
        hosts.append(dict(branch=label, processes=records, viewer_url=viewer['url'], viewer_listening=listening))
    return dict(windows=windows, linux=linux, hosts=hosts, normal_receipts=normal, windows_reader=c.ref(helper), linux_reader=c.ref(PHYS))


def audit(out):
    out.mkdir(parents=True, exist_ok=False)
    r = dict(passed=False, observational_only=True, started_utc=c.now(), model_calls=0, scientific_writes=0, comparison_performed=False, checks={}, evidence={})
    try:
        manifest = c.read(OPS/'audit-manifest.json')
        for row in manifest['readers']: assert c.sha(row['uri']) == row['sha256']
        q = c.queue('status', '20261010T185932431096Z-5e6874a0')
        assert q['state'] == 'succeeded' and type(q['exit_status']) is int and q['exit_status'] == 0 and q['error'] is None and q['cancel_requested_at'] is None
        r['scientific_queue'] = q
        route = c.read(c.HERE/'continuation-route.json')
        for key, row in route.items():
            if isinstance(row, dict) and 'uri' in row and 'sha256' in row: assert c.sha(row['uri']) == row['sha256'], key
        r['source'] = c.frozen_identity()
        frozen = c.inventory(c.FROZEN); frozen.pop('source-manifest.json'); assert frozen == c.read(c.FROZEN/'source-manifest.json')
        r['frozen_files'] = len(frozen)
        run = verify_run(c.DEST, True); claim = c.read(route['claim']['uri'])
        assert run['condition'] == 'maps' and run['branch_id'] == claim['branch_id']
        assert Path(claim['destination']).resolve() == c.DEST.resolve()
        r['capacity_before'] = c.capacity(); assert r['capacity_before']['c_headroom_pass'] and r['capacity_before']['d_headroom_pass']
        finish_check(r, 'terminal_queue_frozen_source_environment_route_and_capacity')

        before = {}
        for label, root in [('accepted', c.DEST), ('failed_parent', c.PARENT), ('baseline', c.PAIR/'baseline'), ('pristine_maps', c.PAIR/'maps')]:
            before[label] = c.inventory(root); c.save(out/(label+'-before.json'), before[label])
        assert before['failed_parent'] == c.read(c.QUAL/'parent-before.json')
        assert before['baseline'] == c.read(c.QUAL/'baseline-before.json')
        assert before['pristine_maps'] == c.read(c.QUAL/'maps-before.json')
        r['preservation_before'] = {k:dict(files=len(v), inventory=c.ref(out/(k+'-before.json'))) for k,v in before.items()}
        ready = c.read(c.DEST/'recovery-ready.json')
        assert ready['parent_inventory_sha256'] == c.hashlib.sha256(c.canonical(before['failed_parent'])).hexdigest()
        for number in range(1, 6):
            sid = f'session-{number:05d}'
            for prefix in ('sessions/'+sid+'/', 'checkpoints/'+sid+'/', 'filesystem-before-'+sid+'/'):
                assert {k:v for k,v in before['accepted'].items() if k.startswith(prefix)} == {k:v for k,v in before['failed_parent'].items() if k.startswith(prefix)}
        cp5 = c.read(c.CP/'state.json')
        assert (c.DEST/'events.jsonl').read_bytes()[:cp5['log_bytes']] == (c.PARENT/'events.jsonl').read_bytes()[:cp5['log_bytes']]
        with (c.DEST/'sessions/session-00006/workspace/journal/mutations.jsonl').open('rb') as f: initial6 = json.loads(f.readline())['state']
        assert initial6 == c.read(c.CP/'filesystem-namespace.json')
        finish_check(r, 'accepted_original_prefix_and_abandoned_tail_separation')

        execution = terminal(c.DEST); assert execution['passed'] and execution['retirement']['all_retired']
        assert execution['model_calls'] == execution['official_sessions'] == 29
        assert not any((c.DEST/n).exists() for n in ('running.lock','controller-failure.json','hibernate-requested.json'))
        latest = Path(c.read(c.DEST/'latest-checkpoint.json')['path'])
        assert latest == c.DEST/'checkpoints/session-00034'
        state = c.read(latest/'state.json'); events = chain(c.DEST/'events.jsonl')
        assert state['sessions'] == 34 and state['position'] == len(state['completed']) == 21
        assert c.read(c.DEST/'completed.json')['sessions'] == 34
        assert state['event_sequence'] == len(events) and state['event_chain'] == events[-1]['sha256']
        assert c.inventory(c.DEST/'filesystem') == c.inventory(latest/'filesystem')
        assert c.sha(c.DEST/'filesystem-namespace.json') == c.sha(latest/'filesystem-namespace.json')
        assert c.sha(c.DEST/'replay/index.json') == state['replay_index_sha256']
        checkpoints = []
        for number in range(1,35):
            sid = f'session-{number:05d}'; p = c.DEST/'checkpoints'/sid
            checkpoints.append(dict(session=number, receipt=verify_checkpoint(p), prefix=verify_prefix(c.DEST,p)))
            close = validate_closeout(c.DEST/('filesystem-before-'+sid), c.DEST/'sessions'/sid/'workspace/final-filesystem')
            assert close == c.read(c.DEST/'sessions'/sid/'closeout.json')
        r['checkpoints'] = checkpoints
        finish_check(r, 'all_34_checkpoints_single_report_closeouts_and_terminal_filesystem')

        r['native'] = native(c.DEST)
        sessions = [(f'accepted-{n:05d}', c.DEST/'sessions'/f'session-{n:05d}') for n in range(1,35)]
        sessions.append(('abandoned-original-00006', c.PARENT/'sessions/session-00006'))
        r['original_history'] = c.native_history()
        r['parent_checkpoint'] = c.parent_checkpoint()
        threads = []; transports = {}; maps_reads = []
        for label, session in sessions:
            nr = c.read(session/'native/client/result.json')
            assert type(nr['native_quiescence']['native_exit_code']) is int and nr['native_quiescence']['native_exit_code'] == 0
            threads.append(dict(session=label, thread_id=nr['thread_id']))
            transports[label] = transport_readback(session/'native')
            loc = c.read(session/'workspace/location.json')
            proof = journal_reader.verify(session/'workspace/journal', loc['run_id'], retain_reads=True)
            end = c.read(session/'workspace/journal/native-exit.json')
            assert proof['records'] == end['final_sequence'] and proof['final_state_sha256'] == end['final_state_sha256']
            reads = [x for x in proof['read_events'] if x['path'].startswith('/Maps/Rooms/') and not x['path'].endswith('/README.md') and x['bytes'] > 0]
            maps_reads.append(dict(session=label, room_map_reads=len(reads), journal_records=proof['records'], reads=proof['reads'], mutations=proof['mutations']))
        assert len(threads) == len({x['thread_id'] for x in threads}) == 35
        r['native_threads'] = threads; r['transport'] = transports; r['journal_activity'] = maps_reads
        finish_check(r, 'all_35_distinct_native_calls_journals_inodes_isolation_and_transport')

        model = mujoco.MjModel.from_xml_string(xml()); data = mujoco.MjData(model)
        r['replay'] = replay(c.DEST, model); r['original_parent_replay'] = replay(c.PARENT, model)
        assert r['replay']['epochs'] == 2 and r['replay']['final_sim_time'] == state['world']['sim_time']
        recordings = {}
        for label, root in [('accepted',c.DEST),('failed_parent',c.PARENT)]:
            rows = chain(root/'events.jsonl'); captures = [e for e in rows if e['kind']=='sensor_capture']
            for e in captures:
                p = root/'sensors'/f"frame-{e['payload']['sequence']:07d}.png"
                assert c.sha(p) == e['payload']['image_sha256']
            epochs = {}
            for e in rows:
                prior = epochs.get(e['clock_epoch'])
                if prior: assert e['sim_time'] >= prior['sim_time'] and e['monotonic_ns'] >= prior['monotonic_ns']
                epochs[e['clock_epoch']] = e
            recordings[label] = dict(events=len(rows), sensor_captures=len(captures), image_deliveries=sum(e['kind']=='image_delivered' for e in rows), event_sha256=c.sha(root/'events.jsonl'), replay_index_sha256=c.sha(root/'replay/index.json'), epochs=len(epochs))
        r['recordings'] = recordings
        finish_check(r, 'complete_accepted_and_original_abandoned_sensor_replay_event_content')

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
            assert len(ends)==1 and ends[0]['payload']['status']=='completed'
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
            after=c.inventory(root); assert before[label]==after,label
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
    except BaseException as error: r.update(error=repr(error),traceback=traceback.format_exc())
    r['finished_utc']=c.now();c.save(out/'result.json',r)
    print(json.dumps({k:r.get(k) for k in ('passed','checks','error','traceback','finished_utc')}),flush=True)
    return r['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    raise SystemExit(0 if audit(a.output.resolve()) else 1)
