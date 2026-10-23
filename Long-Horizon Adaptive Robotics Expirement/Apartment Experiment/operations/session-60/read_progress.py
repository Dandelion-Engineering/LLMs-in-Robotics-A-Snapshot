"""Bounded operator readback; never sends a command to the scientific run."""
import argparse
from collections import Counter
import ctypes
from ctypes import wintypes as W
import json
from pathlib import Path
import subprocess
import sys
import tomllib
import traceback
import urllib.request
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'session-59'))
import support as s
from observe_maps import prefix


def owner_status(path):
    owner = s.read(path)
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.OpenProcess.argtypes = (W.DWORD, W.BOOL, W.DWORD)
    k.OpenProcess.restype = W.HANDLE
    k.GetProcessTimes.argtypes = (W.HANDLE, *([ctypes.POINTER(W.FILETIME)] * 4))
    k.GetProcessTimes.restype = W.BOOL
    k.GetExitCodeProcess.argtypes = (W.HANDLE, ctypes.POINTER(W.DWORD))
    k.GetExitCodeProcess.restype = W.BOOL
    k.CloseHandle.argtypes = (W.HANDLE,)
    k.CloseHandle.restype = W.BOOL
    value = dict(record=s.ref(path), pid=owner['pid'])
    handle = k.OpenProcess(0x1000, False, owner['pid'])
    if not handle:
        error = ctypes.get_last_error()
        assert error == 87, error
        return value | dict(state='absent', active=False, retired=True, exit_status=None)
    try:
        times = [W.FILETIME() for _ in range(4)]
        code = W.DWORD()
        assert k.GetProcessTimes(handle, *[ctypes.byref(t) for t in times])
        assert k.GetExitCodeProcess(handle, ctypes.byref(code))
        same = ((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime) == owner['process_creation_filetime']
        active = same and code.value == 259
        return value | dict(state='active' if active else ('exited' if same else 'pid_reused'), active=active,
                            retired=not active, exit_status=code.value if same and not active else None)
    finally:
        k.CloseHandle(handle)


def main(observation):
    result = dict(observed_utc=s.now(),observational_only=True,passed=False,checks={},heartbeat=s.ref(observation))
    try:
        o = s.read(observation)
        assert o['passed'] and o['checkpoint_readback']['receipt']['passed'] and o['checkpoint_readback']['prefix']['passed']
        result['checks']['heartbeat_and_checkpoint_readback'] = True
        route = s.read(s.HERE/'storage-route.json')
        for key in ('source_manifest','certificate','original_pair_manifest','initial_manifest'):
            record=route[key]; assert s.sha(record['uri']) == record['sha256']
        source = s.read(route['source_manifest']['uri'])
        for name,record in source.items():
            p=s.FROZEN/name
            assert s.sha(p)==record['sha256'] and p.stat().st_size==record['bytes'],name
        expected=s.read(s.PAIR/'maps/run.json'); expected['launched']=True
        assert s.read(s.RUN/'run.json')==expected
        result['source_files_verified']=len(source)
        result['checks']['frozen_sources_and_run_identity']=True
        cp=Path(o['checkpoint_readback']['pointer']['path'])
        state=s.read(cp/'state.json')
        result['checkpoint']=o['checkpoint_readback']
        result['progress']=dict(position=state['position'],closed_sessions=state['sessions'],completed=state['completed'],completed_by_kind=dict(Counter(x['kind'] for x in state['completed'])))
        rows,result['events_prefix']=prefix(s.RUN/'events.jsonl')
        result['event_counts']=dict(Counter(r['kind'] for r in rows))
        result['closed_sessions']=[dict(sequence=r['sequence'],sim_time=r['sim_time'],**r['payload']) for r in rows if r['kind']=='session_closed']
        result['task_success_events']=[dict(sequence=r['sequence'],session=r['payload'].get('session')) for r in rows if r['kind']=='task_success']
        result['event_records_since_heartbeat']=len(rows)-o['events_prefix']['records']
        result['checks']['no_controller_failure']=not (s.RUN/'controller-failure.json').exists()
        assert result['checks']['no_controller_failure']
        native_number=o['frame']['session']
        session=s.RUN/'sessions'/f'session-{native_number:05d}'
        preflight=s.read(session/'native/client/preflight.json')
        result['native']={k:preflight.get(k) for k in ('thread_id','preflight_passed','model_effective','effort_effective','auth_type')}
        result['native']['session']=native_number
        assert preflight['preflight_passed'] and preflight['model_effective']=='gpt-6-astra' and preflight['effort_effective']=='max' and preflight['auth_type']=='chatgpt'
        threads=[s.read(p)['thread_id'] for p in sorted((s.RUN/'sessions').glob('*/native/client/preflight.json'))]
        assert len(threads)==len(set(threads));result['distinct_threads']=threads
        result['checks']['actual_native_identity_and_distinct_threads']=True
        for name in ('canary.json','codehost-canary.json'):
            canary=s.read(session/'native'/name)
            assert canary['exit_status']==0 and json.loads(canary['stdout'])['qualified']
        native_events,result['native_prefix']=prefix(session/'native/client/events.jsonl')
        counts=Counter(r.get('method',r.get('kind','unknown')) for r in native_events)
        result['native_counts']=dict(counts)
        assert counts['turn/started'] and (counts['item/tool/call'] or counts['public_tool_call'])
        result['checks']['native_turn_tools_and_canaries']=True
        owners=[owner_status(p) for name in ('native-owner.json','codehost-native-owner-v3.json') for p in session.rglob(name)]
        assert len(owners)==2
        result['native_owners']=owners
        if all(x['active'] for x in owners):result['native_lifecycle']='active'
        else:
            assert all(x['retired'] for x in owners)
            client=s.read(session/'native/client/result.json')
            assert client['success'] and client['turn_status']=='completed'
            result['native_lifecycle']='completed during observation'
        result['checks']['native_owner_identity_and_lifecycle']=True
        journal,result['journal_prefix']=prefix(session/'workspace/journal/mutations.jsonl')
        assert len(journal)>1
        result['checks']['current_native_journal_records_present']=True
        sensors=[r for r in rows if r['kind']=='sensor_capture']
        sensor=sensors[-1]; sensor_path=s.RUN/'sensors'/f"frame-{sensor['payload']['sequence']:07d}.png"
        assert s.sha(sensor_path)==sensor['payload']['image_sha256']
        replay=s.read(s.RUN/'replay/index.json'); latest=replay[-1]
        assert s.sha(s.RUN/'replay'/latest['file'])==latest['sha256']
        result['recording']=dict(sensor_event_sequence=sensor['sequence'],sensor_sim_time=sensor['sim_time'],sensor=s.ref(sensor_path),replay_chunks=len(replay),latest_replay=latest)
        result['checks']['latest_sensor_and_replay_hashes']=True
        with urllib.request.urlopen(o['viewer_url']+'/frame',timeout=12) as response:frame=json.load(response)
        result['frame']={k:v for k,v in frame.items() if k not in ('activity','geoms')}
        assert frame['sim_time']>o['frame']['sim_time'] and len(frame['geoms'])>0
        result['checks']['viewer_and_advancing_simulation']=True
        monitor=s.read(s.HERE/'monitoring.json'); path=Path(monitor['automation_file']['uri'])
        actual=tomllib.loads(path.read_text(encoding='utf-8'))
        for key in ('id','status','rrule','prompt','target_thread_id'):assert actual[key]==monitor['automation'][key]
        result['monitor']=dict(id=actual['id'],status=actual['status'],rrule=actual['rrule'],configuration=s.ref(path))
        result['older_monitors']=[]
        for older in monitor['older_unchanged_paused']:
            path=path.parent.parent/older['id']/'automation.toml'
            assert s.sha(path)==older['sha256'] and tomllib.loads(path.read_text(encoding='utf-8'))['status']=='PAUSED'
            result['older_monitors'].append(older)
        result['checks']['current_active_and_four_unchanged_paused_monitors']=True
        result['capacity']=dict(C=s.volume('C:\\'),D=s.volume('D:\\'))
        result['checks']['full_storage_reserves']=all(x['free_bytes']>=50*s.GIB for x in result['capacity'].values())
        result['checks']['full_original_admission_headroom_still_available']=result['capacity']['C']['free_bytes']>=int(409.9755859375*s.GIB) and result['capacity']['D']['free_bytes']>=52*s.GIB
        result['limitations']=['No independent physical scoring or scientific comparison performed.','Full raw-journal validation, full environment census and actual Linux retirement are endpoint work; normal closeout receipts are read below.','The checkpoint and active native/frame snapshots have distinct recorded times.']
        closed=s.RUN/'sessions'/f"session-{state['sessions']:05d}"
        client=s.read(closed/'native/client/result.json'); cleanup=s.read(closed/'workspace/cleanup-001.json'); closeout=s.read(closed/'closeout.json'); native_exit=s.read(closed/'workspace/journal/native-exit.json')
        assert client['success'] and client['turn_status']=='completed' and closeout['passed']
        assert cleanup['normal_requested'] and cleanup['retired'] and not cleanup['mounted'] and cleanup['log_closed'] and cleanup['service_exit']==0 and not cleanup['errors']
        assert native_exit['libfuse_main_return']==0 and native_exit['requested_sigterm'] is False
        retired=[owner_status(p) for name in ('native-owner.json','codehost-native-owner-v3.json') for p in closed.rglob(name)]
        assert len(retired)==2 and all(x['retired'] for x in retired)
        result['latest_closed_session']=dict(session=state['sessions'],client=s.ref(closed/'native/client/result.json'),cleanup=s.ref(closed/'workspace/cleanup-001.json'),closeout=s.ref(closed/'closeout.json'),native_exit=s.ref(closed/'workspace/journal/native-exit.json'),windows=retired)
        result['checks']['latest_closed_native_receipts_and_actual_windows_retirement']=True
        result['passed']=all(result['checks'].values())
    except BaseException as e:
        result.update(error=repr(e),traceback=traceback.format_exc())
    result['reader']=s.ref(Path(__file__))
    path=s.DATA/'operator/observations'/('session60-progress-'+uuid.uuid4().hex+'.json')
    s.save(path,result)
    print(json.dumps(dict(evidence=str(path),passed=result['passed'],checks=result['checks'],progress=result.get('progress'),native=result.get('native'),native_lifecycle=result.get('native_lifecycle'),frame=result.get('frame'),error=result.get('error'),traceback=result.get('traceback'))),flush=True)
    return 0 if result['passed'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('observation',type=Path)
    raise SystemExit(main(parser.parse_args().observation))
