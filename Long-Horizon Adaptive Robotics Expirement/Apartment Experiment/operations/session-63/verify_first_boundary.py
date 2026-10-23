"""Bounded read-only audit of the replacement session-6 clean boundary."""
import traceback
from common63 import *
sys.path.insert(0,str(HERE.parent/'session-60'))
from read_progress import owner_status

def main():
    out=BASE/'first-boundary';out.mkdir(exist_ok=False)
    result=dict(passed=False,checks={},observed_utc=now(),observational_only=True,session=6)
    try:
        cp=DEST/'checkpoints/session-00006';session=DEST/'sessions/session-00006';workspace=session/'workspace'
        from recording import verify_checkpoint,verify_prefix
        result['checkpoint']=dict(path=str(cp),receipt=verify_checkpoint(cp),prefix=verify_prefix(DEST,cp))
        state=read(cp/'state.json');assert state['sessions']==6
        result['progress']=dict(accepted_sessions=6,closed_advancements=state['position'],completed=state['completed'],abandoned_original_model_calls=1)
        result['checks']['replacement_session6_checkpoint_and_prefix']=True
        from run import validate_closeout
        closeout=validate_closeout(DEST/'filesystem-before-session-00006',workspace/'final-filesystem')
        assert closeout==read(session/'closeout.json')
        result['closeout']=dict(report=closeout['report'],record=ref(session/'closeout.json'))
        client=read(session/'native/client/result.json');original=read(PARENT/'sessions/session-00006/native/client/result.json')
        assert client['success'] and client['turn_status']=='completed' and client['model_effective']=='gpt-6-astra' and client['effort_effective']=='max'
        assert client['thread_id']!=original['thread_id']
        assert client['native_quiescence']['qualified'] and client['native_quiescence']['native_exit_code']==0
        cleanup=read(workspace/'cleanup-001.json');native_exit=read(workspace/'journal/native-exit.json')
        assert cleanup['normal_requested'] and cleanup['retired'] and not cleanup['mounted'] and cleanup['log_closed']
        assert type(cleanup['service_exit']) is int and cleanup['service_exit']==0 and not cleanup['errors']
        assert native_exit['libfuse_main_return']==0 and not native_exit['requested_sigterm']
        import journal_reader
        location=read(workspace/'location.json');proof=journal_reader.verify(workspace/'journal',location['run_id'])
        assert proof['records']==native_exit['final_sequence'] and proof['final_state_sha256']==native_exit['final_state_sha256']
        result['journal']={k:v for k,v in proof.items() if k not in ('state','states','read_events')}
        result['new_thread']=client['thread_id'];result['abandoned_original_thread']=original['thread_id']
        result['checks']['normal_native_closeout_single_immutable_report_and_full_journal']=True
        owners=[owner_status(p) for name in ('native-owner.json','codehost-native-owner-v3.json') for p in session.rglob(name)]
        assert len(owners)==2 and all(x['retired'] for x in owners);result['windows']=owners
        probe=r'''import os,json,pathlib,sys
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
        result['linux']=json.loads(output('wsl.exe','-d','Ubuntu-24.04','--','python3','-B','-c',probe,location['run']))
        assert not result['linux']['processes'] and not result['linux']['mounts']
        result['checks']['actual_completed_session_windows_linux_and_mount_retirement']=True
        assert inventory(PARENT)==read(QUAL/'parent-before.json')
        for name,row in read(FROZEN/'source-manifest.json').items():assert sha(FROZEN/name)==row['sha256']
        assert inventory(PAIR/'maps')==read(QUAL/'maps-before.json')
        result['checks']['failed_parent_pristine_maps_and_frozen_sources_unchanged']=True
        result['passed']=True
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
    result['reader']=ref(__file__);save(out/'result.json',result);save(HERE/'first-boundary-result.json',result)
    print(json.dumps(result),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
