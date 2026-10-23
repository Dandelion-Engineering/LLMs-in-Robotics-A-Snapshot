"""Private controller/namespace continuation tests, separate from model performance."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import traceback
from common import canonical,save,read,sha,inventory
from schedule import build,validate
from controller import Controller
from deployment import instantiate
from recording import verify_checkpoint,Replay

def reject(fn):
    try:fn()
    except (ValueError,RuntimeError,AssertionError,KeyError):return True
    return False

def dock(c):
    c.ask('fixture',[1,1,1.2]);c.ask('fixture_advance_time',3)
    return c.ask('public',('POST','/command',dict(kind='dock',parameters={},request_id='dock')))

def run(out):
    out.mkdir(parents=True,exist_ok=False);result=dict(passed=False,stage='throwaway-lifecycle-engineering',checks={},official_sessions=0,model_calls=0)
    c=space=None
    try:
        schedule=build(81920);config=dict(normal_work_s=1,throw_work_s=2,reserve_s=1800)
        result['checks']['seven_each']=validate(schedule)==validate(copy.deepcopy(schedule))
        root=out/'continuation';instantiate('maps',root/'filesystem')
        c=Controller(root,schedule,config,'maps');c.start();c.ask('start')
        # Pending hibernation is invisible to Robot Codex and changes neither task nor profile.
        before=c.ask('private');save(root/'hibernate-requested.json',{'private_fixture':True})
        public=c.ask('public',('GET','/status',{}))
        result['checks']['pending_not_public']='hibernate' not in json.dumps(public)
        result['checks']['pending_not_interrupt']=c.ask('private')['phase']=='active'
        result['checks']['early_finish_rejected']=reject(lambda:c.ask('finish',dict(normal_model_completion=True,filesystem_closeout=True,runtime_retired=True)))
        dock(c)
        result['checks']['bad_retirement_rejected']=reject(lambda:c.ask('finish',dict(normal_model_completion=True,filesystem_closeout=True,runtime_retired=False)))
        result['checks']['physical_commands_closed']=reject(lambda:c.ask('public',('POST','/command',dict(kind='base',parameters={'forward':.1},request_id='after-dock'))))
        ended=c.ask('finish',dict(normal_model_completion=True,filesystem_closeout=True,runtime_retired=True,source='private-controller-fixture'))
        c.close();c=None
        checkpoint=Path(ended['checkpoint']['path']);saved=read(checkpoint/'state.json')
        result['checks']['deferred_checkpoint']=verify_checkpoint(checkpoint)['passed']
        bad=out/'corrupt-checkpoint';shutil.copytree(checkpoint,bad)
        with (bad/'filesystem/SummaryOfOnlyNecessaryContext.md').open('a') as f:f.write('CORRUPTED')
        result['checks']['corruption_rejected']=reject(lambda:verify_checkpoint(bad))
        (root/'hibernate-requested.json').rename(root/'processed-request.json')
        c=Controller(root,schedule,config,'maps',checkpoint=checkpoint);c.start()
        actual=c.ask('private')
        result['checks']['resume_world_exact']=actual['world']['physics']==saved['world']['physics']
        result['checks']['resume_rng_exact']=actual['world']['rng']==saved['world']['rng']
        result['checks']['resume_position_exact']=actual['position']==saved['position']
        result['checks']['unfinished_kept']=saved['position']==(1 if schedule['assignments'][0]['kind']=='throwing' else 0)
        c.ask('start');fresh=c.ask('private')
        result['checks']['fresh_session_recharged']=fresh['sessions']==saved['sessions']+1 and not fresh['world']['docked']
        dock(c);c.ask('fixture_success_latch')
        c.ask('finish',dict(normal_model_completion=True,filesystem_closeout=True,runtime_retired=True,source='private-controller-fixture'))
        # Complete remaining schedule with explicit controller success fixtures.
        # Physical success mechanisms are tested separately; these latches test only scheduling.
        while not c.stop.is_set():
            s=c.ask('private')
            if s['position']>=21:break
            c.ask('start');c.ask('fixture_success_latch');dock(c)
            c.ask('finish',dict(normal_model_completion=True,filesystem_closeout=True,runtime_retired=True,source='private-controller-fixture'))
        c.close();c=None
        end=read(root/'boundary-state.json')
        result['checks']['exact_21_endpoint']=end['position']==21 and [r['position'] for r in end['completed']]==list(range(21))
        result['checks']['completed_checkpoint']=verify_checkpoint(read(root/'completed.json')['checkpoint']['path'])['passed']
        replay=Replay(root);frame=replay.frame(100);result['checks']['recorded_replay']=frame['provenance']['kind']=='reconstruction from original sampled physics state';replay.close()
        # Preserve inode metadata, hard links, symbolic links and empty directories across fresh native mounts.
        from native_runtime import Workspace,linux
        nroot=out/'namespace';instantiate('baseline',nroot/'filesystem')
        c=Controller(nroot,build(178),config,'baseline');c.start()
        space=Workspace(nroot/'sessions/session-00001/workspace',nroot/'filesystem','metadata-1');space.start_clock_bridge(c)
        linux("import os,pathlib,sys;p=pathlib.Path(sys.argv[1]);(p/'empty-directory').mkdir();x=p/'program.py';x.write_bytes(b'print(7)\\n');x.chmod(0o751);os.link(x,p/'hard.py');os.symlink('program.py',p/'symbolic.py')",space.workspace)
        final,proof=space.close();evidence=space.evidence;space=None
        expected=read(evidence/'final-namespace.json')
        (nroot/'filesystem').rename(nroot/'original-filesystem');shutil.copytree(final,nroot/'filesystem')
        shutil.copy2(evidence/'final-namespace.json',nroot/'filesystem-namespace.json');shutil.copytree(evidence/'final-objects',nroot/'filesystem-objects')
        space=Workspace(nroot/'sessions/session-00002/workspace',nroot/'filesystem','metadata-2');space.start_clock_bridge(c)
        initial=json.loads((space.evidence/'journal/mutations.jsonl').read_bytes().splitlines()[0])['state']
        result['checks']['inode_namespace_exact']=initial==expected
        observed=json.loads(linux("import pathlib,os,json,sys;p=pathlib.Path(sys.argv[1]);print(json.dumps(dict(mode=(p/'program.py').stat().st_mode&0o777,link=os.readlink(p/'symbolic.py'),hard=(p/'hard.py').stat().st_ino==(p/'program.py').stat().st_ino,empty=list((p/'empty-directory').iterdir())==[],bytes=(p/'symbolic.py').read_bytes()==b'print(7)\\n')))",space.workspace))
        result['checks']['metadata_round_trip']=observed==dict(mode=0o751,link='program.py',hard=True,empty=True,bytes=True)
        space.close();space=None;c.close();c=None
        from viewer import Files
        files=Files(nroot)
        result['checks']['replay_no_future_files']=not files.listing(-1)['files']
        result['checks']['aligned_fs_available']='/program.py' in files.listing(1e10)['files']
        result['checks']['live_fs_available']='/program.py' in files.listing()['files']
        result['passed']=all(result['checks'].values())
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
    finally:
        if space:
            try:space.close()
            except BaseException as e:result['namespace_cleanup_error']=repr(e)
        if c:c.close()
        save(out/'result.json',result)
    print(canonical(result).decode());return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.output) else 1)
