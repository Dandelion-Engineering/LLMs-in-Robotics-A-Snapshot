"""Read-only v4 endpoint supplement; submit through the shared compute queue.

Reconstruct retained states with mj_forward, never step or command the run.
Writes exclusively to a new operator output directory. Failed readback is retained.
"""
import argparse
import bisect
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import runpy
import socket
import statistics
import subprocess
import sys
import traceback

PAIR = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v4')
ROOT = PAIR / 'baseline'
CODE = PAIR / 'frozen_repository/Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'
sys.path.insert(0, str(CODE))
import mujoco
import numpy as np
from common import read, sha
from audit import chain
from recovery import terminal
from scene import xml, TOYS


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def geometry(model, data, assignment):
    def obj(name):
        address = model.joint(name + '_free').dofadr[0]
        return dict(position=data.body(name).xpos.tolist(),
                    speed_m_s=float(np.linalg.norm(data.qvel[address:address + 3])))
    if assignment['kind'] == 'bedroom':
        objects = {name: obj(name) for name, _, _ in TOYS}
        for item in objects.values():
            x, y, z = item['position']
            item['passes'] = abs(x - 4.8) < .49 and abs(y - 8) < .34 and .08 < z < .42 and item['speed_m_s'] < .08
        return dict(passed=all(v['passes'] for v in objects.values()), objects=objects)
    name = 'drawer' + assignment['drawer']
    drawer = data.body(name).xpos
    cup = obj('cup')
    c = cup['position']
    opening = float(data.qpos[model.joint(name).qposadr[0]])
    passed = bool(opening > .32 and abs(c[0] - drawer[0]) < .34 and abs(c[1] - drawer[1]) < .31
                  and drawer[2] < c[2] < drawer[2] + .25 and cup['speed_m_s'] < .08)
    return dict(passed=passed, cup=cup, drawer_position=drawer.tolist(), drawer_opening_m=opening)


LINUX_PROBE = r'''import json,os,pathlib,sys
claims=json.load(sys.stdin);boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
anc={os.getpid()};pid=os.getpid()
while pid>1:
 try:pid=int(pathlib.Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[1]);anc.add(pid)
 except (OSError,ValueError):break
matches=[];unreadable=[];mounts=[];identities=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name) in anc:continue
 try:
  raw=(p/'cmdline').read_bytes()
  found=[c['session'] for c in claims if c['run'].encode() in raw]
  if found:matches.append(dict(pid=int(p.name),sessions=found))
 except (FileNotFoundError,ProcessLookupError):pass
 except PermissionError:unreadable.append(int(p.name))
for line in pathlib.Path('/proc/self/mountinfo').read_text().splitlines():
 found=[c['session'] for c in claims if c['run'] in line]
 if found:mounts.append(dict(mount=line.split()[4],sessions=found))
for c in claims:
 for role in ('filesystem','native'):
  old=c[role];p=pathlib.Path('/proc',str(old['pid']),'stat')
  try:fields=p.read_text().rsplit(')',1)[1].split();actual=fields[19];state=fields[0]
  except (FileNotFoundError,ProcessLookupError):actual=None;state='absent'
  same=boot==c['boot_id'] and actual==str(old['start_ticks'])
  identities.append(dict(session=c['session'],role=role,pid=old['pid'],expected_start_ticks=str(old['start_ticks']),actual_start_ticks=actual,state=state,same_original_process=same))
print(json.dumps(dict(boot_id=boot,process_matches=matches,mounts=mounts,unreadable_cmdlines=unreadable,identities=identities)))
'''


def audit(output):
    output.mkdir(parents=True, exist_ok=False)
    result = dict(passed=False, observational_only=True, observed_utc=datetime.now(timezone.utc).isoformat(),
                  checks={}, evidence={}, reader_revision=dict(
                      prior_reader='audit_physical_retirement.py',
                      prior_output='physical-retirement001/result.json',
                      reason='The initial supplemental audit incorrectly required success geometry both at the first sampled post-event state and at closeout. The frozen protocol requires a latched success event, not uninterrupted persistence of that predicate. This readback preserves both snapshot outcomes and timing offsets without changing the primary completion definition or scientific evidence.'), limitations=[
                      'Physical readback reconstructs original simulated states; it is not real-world validation.',
                      'Replay omits pickup and grip flags; those flags are checked in authenticated advancing checkpoints. Geometry and velocity are checked at the first retained sample at or after each success event, with the time offset reported.',
                      'Throwing advancement measures completion of the fixed working window, not mastery or a complete throwing-attempt census.',
                      'One dependent Baseline history; no Maps launch, condition comparison or independent replicate.'])
    checks = result['checks']
    try:
        events = chain(ROOT / 'events.jsonl')
        state = read(Path(read(ROOT / 'latest-checkpoint.json')['path']) / 'state.json')
        execution = terminal(ROOT)
        lineage = read(PAIR / 'baseline-lineage.json')
        assert Path(lineage['active_root']).resolve() == ROOT.resolve() and lineage['history'] == []
        starts = [r for r in events if r['kind'] == 'session_started']
        closes = [r for r in events if r['kind'] == 'session_closed']
        successes = [r for r in events if r['kind'] == 'task_success']
        n = state['sessions']
        assert [r['payload']['session'] for r in starts] == [r['payload']['session'] for r in closes] == list(range(1, n + 1))
        assert len(state['completed']) == state['position'] == 21
        assert execution['model_calls'] == execution['official_sessions'] == n
        assert len({r['clock_epoch'] for r in events}) == 1
        assert sum(r['kind'] == 'initialized' for r in events) == 1
        assert not any(r['kind'] == 'resumed' for r in events)
        assert not any((ROOT / name).exists() for name in ('hibernate-requested.json', 'recovery-ready.json', 'controller-failure.json', 'running.lock'))
        assert all(b['sim_time'] >= a['sim_time'] and b['monotonic_ns'] >= a['monotonic_ns'] for a, b in zip(events, events[1:]))
        table = []
        for completed in state['completed']:
            pos = completed['position']
            members = [r for r in starts if r['payload']['assignment_position'] == pos]
            advancing = [r for r in closes if r['payload']['assignment_advanced'] and r['payload']['next_position'] == pos + 1]
            assert len(advancing) == 1 and advancing[0]['payload']['session'] == completed['session'] == members[-1]['payload']['session']
            assert advancing[0]['sim_time'] == completed['sim_time']
            assert all(r['payload']['task'] == completed['kind'] for r in members)
            table.append(dict(position=pos, task=completed['kind'], sessions=len(members), first_session=members[0]['payload']['session'], advancing_session=completed['session']))
        checks['continuous_history_and_assignment_accounting'] = True
        result['accounting'] = dict(started=n, closed=n, unclosed=0, assignments=21, model_calls=execution['model_calls'],
                                    recovery_branches=0, hibernations=0, resumes=0, clock_epochs=1, assignment_table=table,
                                    nonadvancing_sessions=[r['payload']['session'] for r in closes if not r['payload']['assignment_advanced']],
                                    event_counts=dict(Counter(r['kind'] for r in events)))
        result['task_summary'] = {}
        for task in ('bedroom', 'kitchen', 'throwing'):
            counts = [r['sessions'] for r in table if r['task'] == task]
            assert len(counts) == 7
            result['task_summary'][task] = dict(assignments=7, sessions=sum(counts), recurrence_sessions=counts, median=statistics.median(counts), range=[min(counts), max(counts)])

        model = mujoco.MjModel.from_xml_string(xml())
        data = mujoco.MjData(model)
        index = read(ROOT / 'replay/index.json')
        previous = None
        samples = 0
        min_dt = float('inf')
        max_dt = 0.
        wall_backward = 0
        max_wall_gap = 0
        for part in index:
            path = ROOT / 'replay' / part['file']
            assert sha(path) == part['sha256']
            with np.load(path, allow_pickle=False) as z:
                assert set(z.files) == {'t', 'qpos', 'qvel', 'wall_ns', 'monotonic_ns'}
                size = part['samples']
                assert z['t'].shape == z['wall_ns'].shape == z['monotonic_ns'].shape == (size,)
                assert z['qpos'].shape == (size, model.nq) and z['qvel'].shape == (size, model.nv)
                assert all(np.isfinite(z[k]).all() for k in z.files)
                assert float(z['t'][0]) == part['first'] and float(z['t'][-1]) == part['last']
                ts = z['t'] if previous is None else np.r_[previous[0], z['t']]
                ms = z['monotonic_ns'] if previous is None else np.r_[previous[1], z['monotonic_ns']]
                ws = z['wall_ns'] if previous is None else np.r_[previous[2], z['wall_ns']]
                dt = np.diff(ts)
                assert np.all(dt >= 0) and np.all(np.diff(ms) >= 0)
                if len(dt):min_dt = min(min_dt, float(dt.min()));max_dt = max(max_dt, float(dt.max()))
                wall_delta = np.diff(ws)
                wall_backward += int(np.sum(wall_delta < 0))
                if len(wall_delta):max_wall_gap = max(max_wall_gap, int(wall_delta.max()))
                previous = (float(z['t'][-1]), int(z['monotonic_ns'][-1]), int(z['wall_ns'][-1]))
                samples += size
        assert index[-1]['last'] == state['world']['sim_time']
        assert len({p['clock_epoch'] for p in index}) == 1 and index[0]['clock_epoch'] == state['clock_epoch']
        result['replay'] = dict(chunks=len(index), samples=samples, min_sim_delta_s=min_dt, max_sim_delta_s=max_dt,
                                wall_backward_steps=wall_backward, max_wall_gap_s=max_wall_gap / 1e9,
                                final_sim_time=previous[0], all_arrays_decoded=True)
        checks['full_replay_content_and_monotonic_continuity'] = True

        physical = []
        firsts = [p['first'] for p in index]
        for completed in state['completed']:
            if completed['kind'] == 'throwing':continue
            sid = completed['session']
            found = [e for e in successes if e['payload']['session'] == sid and e['payload']['position'] == completed['position']]
            assert len(found) == 1
            event = found[0]
            checkpoint = ROOT / 'checkpoints' / f'session-{sid:05}'
            cp = read(checkpoint / 'state.json')
            w = cp['world']
            assignment = w['assignment']
            assert assignment['position'] == completed['position'] and assignment['kind'] == completed['kind']
            ci = max(0, bisect.bisect_right(firsts, event['sim_time']) - 1)
            with np.load(ROOT / 'replay' / index[ci]['file'], allow_pickle=False) as z:
                k = int(np.searchsorted(z['t'], event['sim_time']))
                if k == len(z['t']):ci += 1;k = 0
            with np.load(ROOT / 'replay' / index[ci]['file'], allow_pickle=False) as z:
                data.qpos[:] = z['qpos'][k];data.qvel[:] = z['qvel'][k];data.time = float(z['t'][k])
                mujoco.mj_forward(model, data)
                near = geometry(model, data, assignment)
                offset = data.time - event['sim_time']
                assert 0 <= offset <= .04
            mujoco.mj_setState(model, data, np.array(w['physics']), mujoco.mjtState.mjSTATE_INTEGRATION)
            mujoco.mj_forward(model, data)
            boundary = geometry(model, data, assignment)
            objects = [t[0] for t in TOYS] if completed['kind'] == 'bedroom' else ['cup']
            flags = all(w['pickups'][name] and w['grip_candidate'] != name for name in objects)
            assert flags and w['docked'] and w['active'] is None
            physical.append(dict(position=completed['position'], task=completed['kind'], session=sid, event_sequence=event['sequence'],
                                 event_sim_time=event['sim_time'], replay_file=index[ci]['file'], sample=k, offset_s=offset,
                                 near_event=near, boundary=boundary, pickup_and_release_flags=True,
                                 checkpoint_state_sha256=sha(checkpoint / 'state.json')))
        assert len(physical) == len(successes) == 14
        result['physical_household_readback'] = physical
        result['physical_corroboration'] = dict(
            trusted_latched_successes=len(successes),
            first_retained_sample_passes=sum(r['near_event']['passed'] for r in physical),
            close_boundary_passes=sum(r['boundary']['passed'] for r in physical),
            corroborated_at_either_observed_time=sum(r['near_event']['passed'] or r['boundary']['passed'] for r in physical),
            exact_event_sample_count=sum(r['offset_s'] == 0 for r in physical),
            maximum_post_event_offset_s=max(r['offset_s'] for r in physical),
            interpretation='The frozen completion rule uses the trusted physical success latch. Snapshot predicate failures are reported rather than promoted to failed original assignments or hidden by a requirement that every later state remain successful.')
        checks['readback_of_fourteen_latched_household_outcomes'] = True

        admitted = {r['payload']['request_id'] for r in events if r['kind'] == 'command_admitted'}
        docks = []
        for start, close in zip(starts, closes):
            sid = start['payload']['session'];work = start['payload']['work_s']
            assert work == (600 if start['payload']['task'] == 'throwing' else 360)
            requested = [r for r in events if r['kind'] == 'command_requested' and r['payload']['session'] == sid
                         and r['payload']['request']['kind'] == 'dock' and r['payload']['request']['request_id'] in admitted]
            assert requested
            dock = requested[-1]
            assert dock['sim_time'] - start['sim_time'] >= work
            finished = [r for r in events if r['kind'] == 'command_terminal' and r['payload'].get('kind') == 'dock'
                        and r['payload'].get('request_id') == dock['payload']['request']['request_id']]
            assert len(finished) == 1 and finished[0]['payload']['status'] == 'completed'
            docks.append(dict(session=sid, task=start['payload']['task'], work_window_s=work,
                              dock_requested_after_s=dock['sim_time']-start['sim_time'], close_after_s=close['sim_time']-start['sim_time']))
        result['docking_and_timed_windows'] = docks
        checks['fixed_windows_and_normal_docking'] = True

        helper = Path(__file__).parents[1] / 'session-42/capture_health.py'
        identity = runpy.run_path(str(helper))['windows_identity']
        windows = []
        claims = []
        for session in sorted((ROOT / 'sessions').iterdir()):
            location = read(session / 'workspace/location.json')
            clean = read(session / 'workspace/cleanup-001.json')
            native = read(session / 'workspace/journal/native-exit.json')
            ret = read(session / 'native/codehost-owner-retirement-v3.json')
            assert clean['normal_requested'] and clean['retired'] and clean['log_closed'] and not clean['mounted'] and not clean['errors'] and clean['service_exit'] == 0
            assert native['libfuse_main_return'] == 0 and not native['requested_sigterm']
            assert ret['qualified'] and ret['windows_exit_code'] == 0 and not ret['normal_wait_timed_out'] and not ret['windows_wrapper_killed_after_linux_retired']
            assert ret['observations'] and all(o['retired'] and not o['kill_sent'] and not o['outer_same_process'] and not o['namespace_members'] and o['namespace_evidence_available'] for o in ret['observations'])
            owners = [p for name in ('native-owner.json', 'codehost-native-owner-v3.json') for p in session.rglob(name)]
            assert len(owners) == 2
            for path in owners:
                observed = identity(read(path))
                assert observed['state'] in ('absent', 'exited', 'pid_reused'), observed
                windows.append(dict(session=session.name, owner=str(path.relative_to(session)), observation=observed))
            claims.append(dict(session=session.name, run=location['run'], boot_id=clean['identity']['boot_id'],
                               filesystem=clean['identity'], native=ret['observations'][0]['identity']))
        probe = subprocess.run(['wsl.exe', '-d', 'Ubuntu-24.04', '--', 'python3', '-B', '-c', LINUX_PROBE],
                               input=json.dumps(claims), capture_output=True, text=True, encoding='utf-8', timeout=60,
                               creationflags=subprocess.CREATE_NO_WINDOW)
        result['linux_probe_execution'] = dict(exit_status=probe.returncode, stderr=probe.stderr)
        assert probe.returncode == 0, probe.stderr
        linux = json.loads(probe.stdout)
        result['linux_retirement'] = linux
        result['windows_retirement'] = windows
        assert not linux['process_matches'] and not linux['mounts'] and not linux['unreadable_cmdlines']
        assert not any(v['same_original_process'] for v in linux['identities'])
        viewer = read(ROOT / 'viewer.json')
        original_status = read(output.parent / 'official-queue-status.json')
        ended = datetime.fromisoformat(original_status['ended_at'].replace('Z', '+00:00')).timestamp()
        host = []
        for role, pid in [('controller', original_status['child_pid']), ('viewer', viewer['pid'])]:
            obs = identity(dict(pid=pid, process_creation_filetime=0))
            if obs['state'] == 'pid_reused':
                creation_unix = obs['actual_creation_filetime'] / 1e7 - 11644473600
                assert obs['exit_code'] != 259 or creation_unix > ended, (role, obs)
                obs['retirement_basis'] = 'observed exited' if obs['exit_code'] != 259 else 'PID created after original job ended'
            else:assert obs['state'] == 'absent', (role, obs)
            host.append(dict(role=role, observation=obs))
        port = int(viewer['url'].rsplit(':', 1)[1])
        with socket.socket() as sock:
            sock.settimeout(2);viewer_listening = sock.connect_ex(('127.0.0.1', port)) == 0
        assert not viewer_listening
        result['host_retirement'] = dict(processes=host, viewer_url=viewer['url'], viewer_listening=viewer_listening)
        checks['fresh_windows_linux_and_viewer_retirement'] = True
        result['evidence'] = dict(event_sha256=sha(ROOT / 'events.jsonl'), replay_index_sha256=sha(ROOT / 'replay/index.json'),
                                  final_checkpoint_state_sha256=sha(ROOT / 'checkpoints/session-00035/state.json'),
                                  reader_sha256=sha(Path(__file__)), windows_reader_sha256=sha(helper),
                                  frozen_scene_sha256=sha(CODE / 'scene.py'), frozen_world_sha256=sha(CODE / 'world.py'))
        result['passed'] = all(checks.values())
    except BaseException as error:
        result.update(error=repr(error), traceback=traceback.format_exc())
    result['finished_utc'] = datetime.now(timezone.utc).isoformat()
    write(output / 'result.json', result)
    print(json.dumps({k:result[k] for k in ('passed','checks','finished_utc')}), flush=True)
    return result['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if audit(args.output.resolve()) else 1)
