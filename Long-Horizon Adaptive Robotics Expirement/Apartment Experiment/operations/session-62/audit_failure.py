"""Read-only audit of the preserved Maps failure; never launches or repairs a run."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import subprocess
import sys
import tomllib
import traceback
import urllib.request

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'session-59'))
import support as s
from observe_maps import prefix
sys.path.insert(0, str(HERE.parent / 'session-60'))
from read_progress import owner_status
sys.path.insert(0, str(s.CODE))
import journal_reader
from run import validate_closeout

OUT = s.DATA / 'operator/session-62'
OBSERVATION = s.DATA / 'operator/observations/session-62-a04ccfc88721411ba9d27725bb0e6281.json'


def main():
    result = dict(observed_utc=s.now(), observational_only=True, scientific_run_success=False,
                  diagnostic_audit_passed=False, checks={}, observation=s.ref(OBSERVATION), reader=s.ref(__file__))
    try:
        o = s.read(OBSERVATION)
        assert o['checkpoint_readback']['receipt']['passed'] and o['checkpoint_readback']['prefix']['passed']
        job = s.queue('status', '20261010T163419885117Z-d580bba0')
        result['scientific_queue'] = job
        assert job['state'] == 'failed' and type(job['exit_status']) is int and job['exit_status'] == 1
        pointer = s.read(s.RUN / 'latest-execution.json')
        assert s.sha(pointer['path']) == pointer['sha256']
        execution = s.read(pointer['path'])
        result['execution'] = s.ref(pointer['path'])
        result['failure'] = {k:execution.get(k) for k in ('failure_phase','error','current_session','finished_wall_ns','retirement')}
        assert execution['failure_phase'] == 'filesystem-closeout' and not execution['passed']
        result['checks']['terminal_failure_authenticated'] = True
        result['checkpoint'] = o['checkpoint_readback']
        cpstate = s.read(Path(result['checkpoint']['pointer']['path']) / 'state.json')
        result['durable_progress'] = dict(closed_sessions=cpstate['sessions'], position=cpstate['position'],
                                        completed=cpstate['completed'])
        assert cpstate['sessions'] == 5 and len(cpstate['completed']) == 2
        result['checks']['last_verified_checkpoint5'] = True

        session = s.RUN / 'sessions/session-00006'
        final = session / 'workspace/final-filesystem'
        before, after = s.inventory(s.RUN / 'filesystem'), s.inventory(final)
        reports = [p for p in after if p not in before and p.startswith('SessionReports/')
                   and len(Path(p).parts) == 2 and Path(p).suffix.lower() == '.md']
        result['new_reports'] = [dict(path=p, **after[p]) for p in reports]
        result['historical_reports_unchanged'] = all(after.get(p) == item for p,item in before.items() if p.startswith('SessionReports/'))
        result['continuity_changed'] = before['SummaryOfOnlyNecessaryContext.md'] != after['SummaryOfOnlyNecessaryContext.md']
        try:
            validate_closeout(s.RUN / 'filesystem', final)
            raise AssertionError('Original validator unexpectedly accepted failed closeout')
        except ValueError as error:
            result['reproduced_closeout_error'] = repr(error)
        assert len(reports) == 2 and result['reproduced_closeout_error'] == execution['error']
        assert all(after[p]['bytes'] >= 120 for p in reports)
        result['checks']['exact_two_report_failure_reproduced_read_only'] = True

        rows, result['events_prefix'] = prefix(s.RUN / 'events.jsonl')
        result['event_counts'] = dict(Counter(r['kind'] for r in rows))
        result['last_event'] = rows[-1]
        result['success_latches'] = [r for r in rows if r['kind'] == 'task_success']
        result['native_sessions'] = []
        locations = []
        for directory in sorted((s.RUN / 'sessions').glob('session-*')):
            workspace = directory / 'workspace'
            loc = s.read(workspace / 'location.json'); locations.append(loc['run'])
            native = s.read(directory / 'native/client/result.json')
            cleanup = s.read(workspace / 'cleanup-001.json')
            native_exit = s.read(workspace / 'journal/native-exit.json')
            proof = journal_reader.verify(workspace / 'journal', loc['run_id'])
            owners = [owner_status(p) for name in ('native-owner.json','codehost-native-owner-v3.json') for p in directory.rglob(name)]
            assert len(owners) == 2 and all(x['retired'] for x in owners)
            assert native['success'] and native['turn_status'] == 'completed'
            assert native['model_effective'] == 'gpt-6-astra' and native['effort_effective'] == 'max'
            assert native['native_quiescence']['qualified'] and native['native_quiescence']['native_exit_code'] == 0
            assert cleanup['normal_requested'] and cleanup['retired'] and not cleanup['mounted'] and cleanup['log_closed']
            assert type(cleanup['service_exit']) is int and cleanup['service_exit'] == 0 and not cleanup['errors']
            assert native_exit['libfuse_main_return'] == 0 and not native_exit['requested_sigterm']
            assert proof['passed'] and proof['records'] == native_exit['final_sequence']
            assert proof['final_state_sha256'] == native_exit['final_state_sha256']
            compact = {k:v for k,v in proof.items() if k not in ('state','states','read_events')}
            result['native_sessions'].append(dict(session=directory.name,thread_id=native['thread_id'],
                native_result=s.ref(directory / 'native/client/result.json'),cleanup=s.ref(workspace / 'cleanup-001.json'),
                native_exit=s.ref(workspace / 'journal/native-exit.json'),journal=compact,owners=owners))
        assert len(result['native_sessions']) == 6
        assert len({v['thread_id'] for v in result['native_sessions']}) == 6
        result['checks']['all_six_native_journals_and_windows_owners_verified'] = True

        linux_probe = r'''import os,json,pathlib,sys
needles=json.loads(sys.argv[1]);anc={os.getpid()};pid=os.getpid()
while pid>1:
 try:pid=int(pathlib.Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[1]);anc.add(pid)
 except (OSError,ValueError):break
processes=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name) in anc:continue
 try:
  args=(p/'cmdline').read_bytes()
  if any(n.encode() in args for n in needles):processes.append(int(p.name))
 except (FileNotFoundError,PermissionError,ProcessLookupError):pass
mounts=[r.split()[4] for r in pathlib.Path('/proc/self/mountinfo').read_text().splitlines() if any(n in r for n in needles)]
print(json.dumps(dict(processes=processes,mounts=mounts)))'''
        result['linux_retirement'] = json.loads(subprocess.check_output(
            ['wsl.exe','-d','Ubuntu-24.04','--','python3','-B','-c',linux_probe,json.dumps(locations)],text=True,encoding='utf-8',timeout=40))
        assert not result['linux_retirement']['processes'] and not result['linux_retirement']['mounts']
        viewer = s.read(s.RUN / 'viewer.json')
        pids = sorted({viewer['pid'],job['child_pid']})
        command = 'Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -in @(' + ','.join(map(str,pids)) + ') } | Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress'
        raw = s.output('powershell.exe','-NoProfile','-NonInteractive','-Command',command)
        result['runner_process_probe'] = dict(pids=pids,matches=json.loads(raw) if raw.strip() else [])
        assert not result['runner_process_probe']['matches']
        with socket.socket() as sock:
            sock.settimeout(2); result['viewer_connect_ex'] = sock.connect_ex(('127.0.0.1',59465))
        assert result['viewer_connect_ex'] != 0
        try:
            with urllib.request.urlopen(viewer['url']+'/frame',timeout=4) as response:
                result['viewer_http_status'] = response.status
            raise AssertionError('Retired viewer unexpectedly responded')
        except urllib.error.URLError as error: result['viewer_http_error'] = repr(error)
        assert not (s.RUN / 'running.lock').exists() and execution['retirement']['all_retired']
        result['checks']['actual_linux_and_runner_retirement_viewer_offline'] = True

        sensors = [r for r in rows if r['kind'] == 'sensor_capture']
        for r in sensors:
            p=s.RUN/'sensors'/('frame-'+str(r['payload']['sequence']).zfill(7)+'.png')
            assert s.sha(p) == r['payload']['image_sha256']
        index=s.read(s.RUN/'replay/index.json')
        for item in index: assert s.sha(s.RUN/'replay'/item['file']) == item['sha256']
        result['recordings'] = dict(sensor_images=len(sensors),replay_chunks=len(index),last_replay=index[-1],
                                    replay_index=s.ref(s.RUN/'replay/index.json'))
        result['checks']['all_recorded_sensors_and_replay_chunk_hashes'] = True
        route=s.read(s.HERE/'storage-route.json')
        for name in ('source_manifest','certificate','original_pair_manifest','initial_manifest'):
            record=route[name]; assert s.sha(record['uri']) == record['sha256']
        source=s.read(route['source_manifest']['uri'])
        for name,record in source.items():
            p=s.FROZEN/name
            assert s.sha(p) == record['sha256'] and p.stat().st_size == record['bytes'],name
        expected=s.read(s.PAIR/'maps/run.json');expected['launched']=True
        assert s.read(s.RUN/'run.json') == expected
        result['source_files_verified']=len(source)
        result['checks']['frozen_sources_and_active_run_identity'] = True
        result['capacity']=dict(C=s.volume('C:\\'),D=s.volume('D:\\'),reserve_bytes=50*s.GIB)
        assert all(result['capacity'][v]['free_bytes'] >= 50*s.GIB for v in ('C','D'))
        result['checks']['full_reserves_present'] = True
        monitors=[]
        for identifier in ('apartment-v4-maps-observations','apartment-v2-baseline-observations','apartment-v2-maps-observations','apartment-v3-baseline-observations','apartment-v4-baseline-observations'):
            p=Path('C:/Users/cresp/.codex/automations')/identifier/'automation.toml'
            c=tomllib.loads(p.read_text(encoding='utf-8'))
            monitors.append(dict(id=identifier,status=c['status'],record=s.ref(p)))
        assert all(m['status']=='PAUSED' for m in monitors)
        result['monitors']=monitors
        result['checks']['all_five_monitors_paused']=True
        result['ui_evidence']=[s.ref(OUT/n) for n in ('stalled-viewer-ax.txt','stalled-viewer.png')]
        result['diagnostic_audit_passed']=True
    except BaseException as error:
        result.update(error=repr(error),traceback=traceback.format_exc())
    s.save(OUT/'audit-result.json',result)
    print(json.dumps({k:result.get(k) for k in ('diagnostic_audit_passed','scientific_run_success','checks','error','new_reports','recordings')}),flush=True)
    return 0 if result['diagnostic_audit_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
