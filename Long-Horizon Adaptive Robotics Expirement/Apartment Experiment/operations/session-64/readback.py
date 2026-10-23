"""Bounded read-only supplement to the Session 63 recovery observer."""
import json
from pathlib import Path
import sys
import traceback
import tomllib

OPS = Path(__file__).resolve().parent
sys.path.insert(0, str(OPS.parent/'session-63'))
import common63 as c
from observe_maps import prefix
sys.path.insert(0, str(OPS.parent/'session-60'))
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
    source=c.BASE/'observations/session-64-d8a049797cbf4762a0e946fd3df26de0.json'
    result=dict(passed=False,checks={},observed_utc=c.now(),observation=c.ref(source),closed_sessions=[],scientific_writes=0)
    try:
        observation=c.read(source)
        assert observation['passed'] and observation['progress']['accepted_sessions']==8
        for number in (7,8):
            session=c.DEST/'sessions'/f'session-{number:05d}';workspace=session/'workspace'
            native=c.read(session/'native/client/result.json');cleanup=c.read(workspace/'cleanup-001.json')
            end=c.read(workspace/'journal/native-exit.json');location=c.read(workspace/'location.json')
            prior=next(n for n in observation['new_native'] if n['session']==number)
            assert native['success'] and native['turn_status']=='completed'
            assert native['model_effective']=='gpt-6-astra' and native['effort_effective']=='max'
            assert native['thread_id']==prior['thread_id']
            assert native['native_quiescence']['qualified'] and type(native['native_quiescence']['native_exit_code']) is int and native['native_quiescence']['native_exit_code']==0
            assert cleanup['normal_requested'] and cleanup['retired'] and not cleanup['mounted'] and cleanup['log_closed']
            assert type(cleanup['service_exit']) is int and cleanup['service_exit']==0 and not cleanup['errors']
            assert end['libfuse_main_return']==0 and not end['requested_sigterm']
            journal=prior['closed_journal'];assert journal['records']==end['final_sequence'] and journal['final_state_sha256']==end['final_state_sha256']
            assert c.sha(workspace/'journal/mutations.jsonl')==prior['journal_prefix']['sha256']
            owners=[owner_status(p) for name in ('native-owner.json','codehost-native-owner-v3.json') for p in session.rglob(name)]
            assert len(owners)==2 and all(o['retired'] for o in owners)
            linux=json.loads(c.output('wsl.exe','-d','Ubuntu-24.04','--','python3','-B','-c',PROBE,location['run']))
            assert not linux['processes'] and not linux['mounts']
            result['closed_sessions'].append(dict(session=number,thread_id=native['thread_id'],report=c.read(session/'closeout.json')['report'],
                journal=journal,windows=owners,linux=linux,evidence={k:c.ref(p) for k,p in dict(native=session/'native/client/result.json',
                    cleanup=workspace/'cleanup-001.json',native_exit=workspace/'journal/native-exit.json',closeout=session/'closeout.json').items()}))
        result['checks']['new_closed_sessions_normal_and_actually_retired']=True
        all_threads=[n['thread_id'] for n in observation['new_native']]
        all_threads += [c.read(p)['thread_id'] for p in (c.PARENT/'sessions').glob('*/native/client/result.json')]
        assert len(all_threads)==10 and len(set(all_threads))==10
        result['checks']['all_ten_invocations_have_distinct_native_threads']=True
        active=next(n for n in observation['new_native'] if n['session']==9)
        active_root=c.DEST/'sessions/session-00009'
        events,eventref=prefix(active_root/'native/client/events.jsonl');journal,journalref=prefix(active_root/'workspace/journal/mutations.jsonl')
        result['active_activity']=dict(session=9,thread_id=active['thread_id'],native_before=active['native_prefix'],native_after=eventref,
            journal_before=active['journal_prefix'],journal_after=journalref,
            windows=[owner_status(p) for name in ('native-owner.json','codehost-native-owner-v3.json') for p in active_root.rglob(name)])
        assert eventref['records']>active['native_prefix']['records'] and journalref['records']>active['journal_prefix']['records']
        result['checks']['native_and_journal_growth_observed']=True
        rows,event_prefix=prefix(c.DEST/'events.jsonl');epochs={}
        for row in rows:
            previous=epochs.get(row['clock_epoch'])
            if previous:
                assert row['monotonic_ns']>=previous['monotonic_ns'] and row['sim_time']>=previous['sim_time']
            epochs[row['clock_epoch']]=row
        result['event_clock_readback']=dict(prefix=event_prefix,epochs=len(epochs),wall_clock_not_used_as_monotonic_clock=True)
        result['checks']['per_epoch_monotonic_and_simulation_order']=True
        parent=c.inventory(c.PARENT);assert parent==c.read(c.QUAL/'parent-before.json')
        result['parent_preservation']=dict(files=len(parent),inventory_sha256=c.hashlib.sha256(c.canonical(parent)).hexdigest())
        endpoint=c.read(OPS.parent/'session-57/endpoint.json')
        for name,row in endpoint['evidence'].items():assert c.sha(row['uri'])==row['sha256'],name
        result['checks']['complete_failed_parent_and_baseline_endpoint_anchors_preserved']=True
        monitors=c.read(OPS.parent/'session-63/monitoring.json');readbacks=[]
        for item in [dict(record=monitors['automation_file'],status='ACTIVE')]+monitors['older_unchanged_paused']:
            row=item['record'];assert c.sha(row['uri'])==row['sha256']
            current=tomllib.loads(Path(row['uri']).read_text(encoding='utf-8'));assert current['status']==item['status']
            readbacks.append(dict(id=current['id'],status=current['status'],record=c.ref(row['uri'])))
        result['monitors']=readbacks;result['checks']['dedicated_monitor_active_five_older_unchanged_paused']=True
        result['capacity_gib']={drive:observation['capacity'][drive]['free_bytes']/c.GIB for drive in ('C','D')}
        result['passed']=True
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
    result['reader']=c.ref(__file__);c.save(OPS/'readback.json',result)
    print(json.dumps(result),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
