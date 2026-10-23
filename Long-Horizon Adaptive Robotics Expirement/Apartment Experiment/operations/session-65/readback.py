"""Read-only lifecycle and preservation supplement for the Session 65 wake."""
from datetime import datetime
import json
from pathlib import Path
import sys
import traceback
import tomllib

OPS = Path(__file__).resolve().parent
sys.path.insert(0, str(OPS.parent / 'session-63'))
import common63 as c
from observe_maps import prefix
sys.path.insert(0, str(OPS.parent / 'session-60'))
from read_progress import owner_status

PROBE = r'''import os,json,pathlib,sys
needle=sys.argv[1];anc={os.getpid()};pid=os.getpid()
while pid>1:
 try:pid=int(pathlib.Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[1]);anc.add(pid)
 except (OSError,ValueError):break
processes=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name) in anc:continue
 try:
  if needle.encode() in (p/'cmdline').read_bytes():processes.append(int(p.name))
 except (FileNotFoundError,PermissionError,ProcessLookupError):pass
mounts=[r.split()[4] for r in pathlib.Path('/proc/self/mountinfo').read_text().splitlines() if needle in r]
print(json.dumps(dict(processes=processes,mounts=mounts)))'''


def main():
    initial = c.BASE / 'observations/session-65-ce17fc42a2d241319e23aed2322ca141.json'
    source = c.BASE / 'observations/session-65-transition-followup-e56ef3aae9634d00af0eab67534c95b2.json'
    result = dict(passed=False, checks={}, observed_utc=c.now(), initial_observation=c.ref(initial),
                  observation=c.ref(source), closed_sessions=[], scientific_writes=0)
    try:
        assert c.sha(initial) == '9a68623795bce07d86388b6f713a028694543c1e898865663d4fa6659c1b0527'
        assert c.sha(source) == '3431e9d49280b7de1351e3635eeacec83f6714d6de043ecfc60b94c3b0da8c9a'
        pending, observation = c.read(initial), c.read(source)
        assert not pending['passed'] and pending['scientific_queue_healthy']
        assert [k for k, v in pending['checks'].items() if not v] == ['fresh_native_identity_and_closed_session_readback']
        assert pending['new_native'][-1] == dict(session=12, state='startup_preflight_pending')
        assert observation['passed'] and all(observation['checks'].values())
        assert observation['progress']['accepted_sessions'] == 11
        assert pending['queue'] == observation['queue'] and observation['queue']['state'] == 'running'
        boundary = next(r for r in observation['lifecycle_tail'] if r['kind'] == 'boundary_checkpoint' and r['payload']['session'] == 11)
        first_time = datetime.fromisoformat(pending['observed_utc']).timestamp()
        later_time = datetime.fromisoformat(observation['observed_utc']).timestamp()
        assert first_time < boundary['wall_ns'] / 1e9 < later_time
        result['transition'] = dict(initial_passed=False, later_passed=True, checkpoint_11_boundary=boundary,
            classification='Non-atomic session-boundary observation; startup pending resolved in a later read.',
            original_observation_preserved=True, scientific_retry=False, intervention=False)
        result['checks']['pending_startup_resolved_by_independent_later_observation'] = True

        for number in (9, 10, 11):
            session = c.DEST / 'sessions' / f'session-{number:05d}'
            workspace = session / 'workspace'
            native = c.read(session / 'native/client/result.json')
            cleanup = c.read(workspace / 'cleanup-001.json')
            end = c.read(workspace / 'journal/native-exit.json')
            location = c.read(workspace / 'location.json')
            prior = next(n for n in observation['new_native'] if n['session'] == number)
            assert native['success'] and native['turn_status'] == 'completed'
            assert native['model_effective'] == 'gpt-6-astra' and native['effort_effective'] == 'max'
            assert native['thread_id'] == prior['thread_id']
            assert native['native_quiescence']['qualified']
            assert type(native['native_quiescence']['native_exit_code']) is int and native['native_quiescence']['native_exit_code'] == 0
            assert cleanup['normal_requested'] and cleanup['retired'] and not cleanup['mounted'] and cleanup['log_closed']
            assert type(cleanup['service_exit']) is int and cleanup['service_exit'] == 0 and not cleanup['errors']
            assert end['libfuse_main_return'] == 0 and not end['requested_sigterm']
            journal = prior['closed_journal']
            assert journal['records'] == end['final_sequence'] and journal['final_state_sha256'] == end['final_state_sha256']
            assert c.sha(workspace / 'journal/mutations.jsonl') == prior['journal_prefix']['sha256']
            owners = [owner_status(p) for name in ('native-owner.json', 'codehost-native-owner-v3.json') for p in session.rglob(name)]
            assert len(owners) == 2 and all(o['retired'] for o in owners)
            linux = json.loads(c.output('wsl.exe', '-d', 'Ubuntu-24.04', '--', 'python3', '-B', '-c', PROBE, location['run']))
            assert not linux['processes'] and not linux['mounts']
            result['closed_sessions'].append(dict(session=number, thread_id=native['thread_id'],
                report=c.read(session / 'closeout.json')['report'], journal=journal, windows=owners, linux=linux,
                evidence={k: c.ref(p) for k, p in dict(native=session / 'native/client/result.json',
                    cleanup=workspace / 'cleanup-001.json', native_exit=workspace / 'journal/native-exit.json',
                    closeout=session / 'closeout.json').items()}))
        result['checks']['new_closed_sessions_normal_and_actually_retired'] = True

        all_threads = [n['thread_id'] for n in observation['new_native']]
        all_threads += [c.read(p)['thread_id'] for p in (c.PARENT / 'sessions').glob('*/native/client/result.json')]
        assert len(all_threads) == 13 and len(set(all_threads)) == 13
        result['snapshot_model_calls'] = dict(original_accepted=5, original_abandoned=1, continuation=7,
                                              total=13, distinct_threads=all_threads)
        result['checks']['all_thirteen_snapshot_invocations_have_distinct_native_threads'] = True
        active = next(n for n in observation['new_native'] if n['session'] == 12)
        active_root = c.DEST / 'sessions/session-00012'
        events, eventref = prefix(active_root / 'native/client/events.jsonl')
        journal, journalref = prefix(active_root / 'workspace/journal/mutations.jsonl')
        result['activity_since_observation'] = dict(session=12, thread_id=active['thread_id'],
            native_before=active['native_prefix'], native_after=eventref,
            journal_before=active['journal_prefix'], journal_after=journalref,
            closeout_present=(active_root / 'closeout.json').exists(),
            windows=[owner_status(p) for name in ('native-owner.json', 'codehost-native-owner-v3.json') for p in active_root.rglob(name)])
        assert eventref['records'] > active['native_prefix']['records'] and journalref['records'] > active['journal_prefix']['records']
        result['checks']['native_and_journal_growth_observed'] = True
        rows, event_prefix = prefix(c.DEST / 'events.jsonl')
        epochs = {}
        for row in rows:
            previous = epochs.get(row['clock_epoch'])
            if previous:
                assert row['monotonic_ns'] >= previous['monotonic_ns'] and row['sim_time'] >= previous['sim_time']
            epochs[row['clock_epoch']] = row
        result['event_clock_readback'] = dict(prefix=event_prefix, epochs=len(epochs), wall_clock_not_used_as_monotonic_clock=True)
        result['checks']['per_epoch_monotonic_and_simulation_order'] = True

        parent = c.inventory(c.PARENT)
        assert parent == c.read(c.QUAL / 'parent-before.json')
        result['parent_preservation'] = dict(files=len(parent), inventory_sha256=c.hashlib.sha256(c.canonical(parent)).hexdigest())
        endpoint = c.read(OPS.parent / 'session-57/endpoint.json')
        for name, row in endpoint['evidence'].items():
            assert c.sha(row['uri']) == row['sha256'], name
        result['checks']['complete_failed_parent_and_baseline_endpoint_anchors_preserved'] = True
        monitors = c.read(OPS.parent / 'session-63/monitoring.json')
        readbacks = []
        for item in [dict(record=monitors['automation_file'], status='ACTIVE')] + monitors['older_unchanged_paused']:
            row = item['record']
            assert c.sha(row['uri']) == row['sha256']
            current = tomllib.loads(Path(row['uri']).read_text(encoding='utf-8'))
            assert current['status'] == item['status']
            readbacks.append(dict(id=current['id'], status=current['status'], record=c.ref(row['uri'])))
        result['monitors'] = readbacks
        result['checks']['dedicated_monitor_active_five_older_unchanged_paused'] = True
        result['capacity_gib_at_observation'] = {drive: observation['capacity'][drive]['free_bytes'] / c.GIB for drive in ('C', 'D')}
        result['passed'] = True
    except BaseException as error:
        result.update(error=repr(error), traceback=traceback.format_exc())
    result['reader'] = c.ref(__file__)
    result['completed_utc'] = c.now()
    c.save(OPS / 'readback.json', result)
    print(json.dumps(result), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
