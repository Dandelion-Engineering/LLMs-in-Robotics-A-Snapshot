"""Both actual templates: real work, clean checkpoint, injected stop, fresh recovery.

Only the disposable deployments receive an IO-only stress instruction. No
private geometry, charger accessibility hint or task solution is supplied.
"""
import argparse
import hashlib
from pathlib import Path
import traceback
from unittest.mock import patch
from common import canonical,inventory,read,save,sha
from revision_config import CONFIG
from repair_model_engineering import STRESS
from run import prepare,execute
from schedule import build
from recording import verify_checkpoint


def run(out):
    out.mkdir(parents=True,exist_ok=False)
    result=dict(passed=False,stage='throwaway-revised-native-recovery',official_sessions=0,real_model_calls=0,injected_starts=0,checks={},conditions={})
    try:
        from native_runtime import Guest
        from recovery import prepare_recovery
        for condition in ('baseline','maps'):
            root=out/'failed'/condition;seed=0
            while build(seed)['assignments'][0]['kind']!='throwing' or build(seed)['assignments'][1]['kind']=='throwing':seed+=1
            prepare(root,condition,'engineering',build(seed),CONFIG)
            (root/'filesystem/commissioning_io.py').write_text(STRESS,encoding='utf-8')
            with (root/'filesystem/ProjectDetails.md').open('a',encoding='utf-8') as stream:
                stream.write('\n## Disposable engineering commissioning only\n\nAt the start of your first session, run `python3 commissioning_io.py` once. This is an IO stress test, not a robot skill. After it prints completion, perform your ordinary current assignment through the ordinary low-battery warning, navigate and dock, write normal closeout, then end. In later sessions, retain the file/results but do not rerun it.\n')
            initial=inventory(root/'filesystem');save(root/'initial-filesystem.json',initial)
            run_record=read(root/'run.json');run_record['template']=initial;save(root/'run.json',run_record)
            original=Guest.model;calls=0
            async def fail_second(guest,*args,**kwargs):
                nonlocal calls
                calls+=1
                if calls==2:
                    result['injected_starts']+=1
                    detail=dict(schema='apartment-native-failure-1',phase='injected-empty-start',native_error=dict(codexErrorInfo='serverOverloaded',message='INJECTED commissioning capacity failure; no provider request sent'),automatic_retry=False,synthetic_fixture=True)
                    save(guest.evidence/'client/result.json',dict(success=False,model_started=False,turn_status='failed',error=detail['native_error']['message'],structured_failure=detail))
                    raise RuntimeError('INJECTED empty-start failure after prior normal boundary')
                result['real_model_calls']+=1
                return await original(guest,*args,**kwargs)
            with patch.object(Guest,'model',fail_second):first=execute(root)
            result['conditions'][condition]=dict(first=first);save(out/'progress.json',result)
            if first['passed'] or calls!=2 or len(first['sessions'])!=1 or not first.get('retirement',{}).get('all_retired'):
                raise ValueError(condition+' did not reach the intended qualified injection: '+str(first.get('error')))
            checkpoint=read(root/'latest-checkpoint.json');state=read(Path(checkpoint['path'])/'state.json')
            assert checkpoint['reason']=='normal-session-boundary' and state['sessions']==1 and state['position']==1
            assert verify_checkpoint(checkpoint['path'])['passed']
            result['checks'][condition+'_normal_boundary_checkpoint']=True
            receipt=read(root/'filesystem/CommissioningIO/receipt.json');raw=(root/'filesystem/CommissioningIO/append.jsonl').read_bytes()
            assert receipt==dict(records=4096,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) and len(raw.splitlines())==4096
            result['checks'][condition+'_high_write']=True
            branch=out/'recovered'/condition
            recovery=prepare_recovery(root,branch,'Injected commissioning-only empty start after the first real normal session')
            result['conditions'][condition]['recovery']=recovery
            assert recovery['source_unchanged'] and recovery['cumulative_interrupted_sessions']==1
            second=execute(branch,resume=True,engineering_sessions=1,hibernate_after_s=10)
            result['real_model_calls']+=second['model_calls']
            result['conditions'][condition].update(second=second,root=str(branch));save(out/'progress.json',result)
            if not second['passed']:raise ValueError(condition+' recovery native session failed: '+str(second.get('error')))
            assert second['sessions'][0]['ending']['hibernated']
            assert verify_checkpoint(read(branch/'latest-checkpoint.json')['path'])['passed']
            assert sha(branch/'filesystem/CommissioningIO/append.jsonl')==receipt['sha256']
            assert len([p for p in (branch/'filesystem/SessionReports').glob('*.md') if p.name!='SessionReportTemplate.md'])==2
            result['checks'][condition+'_native_recovery_and_hibernation']=True
        result['passed']=all(result['checks'].values())
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
    save(out/'result.json',result);print(canonical({k:v for k,v in result.items() if k!='conditions'}).decode());return result['passed']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.output) else 1)
