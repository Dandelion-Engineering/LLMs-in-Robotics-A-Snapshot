"""Real native model, high-write fixture, normal battery/dock and fresh resume.

The additive IO-only commissioning instruction exists solely in disposable
engineering deployments. It contains no motion, task solution or hidden state.
"""
import argparse
import hashlib
from pathlib import Path
import traceback
from common import save,canonical,read,inventory,sha
from schedule import build
from run import prepare,execute
from recording import verify_checkpoint

STRESS='''import hashlib,json,pathlib,random
p=pathlib.Path('CommissioningIO');p.mkdir(exist_ok=True)
r=random.Random(928571)
with (p/'append.jsonl').open('wb',buffering=0) as f:
 for i in range(4096):
  line=(json.dumps({'i':i,'payload':r.randbytes(480).hex()},separators=(',',':'))+'\\n').encode()
  f.write(line)
data=(p/'append.jsonl').read_bytes()
(p/'receipt.json').write_text(json.dumps({'records':4096,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}))
print('Commissioning IO finished; proceed with the ordinary assignment and battery/docking routine.')
'''

def run(out):
    out.mkdir(parents=True,exist_ok=False)
    result=dict(passed=False,stage='throwaway-high-write-native-lifecycle',official_sessions=0,checks={},conditions={})
    try:
        for condition in ('baseline','maps'):
            root=out/condition
            # Private fixed schedule; intentionally begins with throwing. It is
            # unrelated to the original matched hidden schedule.
            seed=0
            while build(seed)['assignments'][0]['kind']!='throwing' or build(seed)['assignments'][1]['kind']=='throwing':seed+=1
            config=dict(normal_work_s=240,throw_work_s=1800,reserve_s=3600,model_wall_s=7200)
            if condition=='maps':config['throw_work_s']=240
            prepare(root,condition,'engineering',build(seed),config)
            (root/'filesystem/commissioning_io.py').write_text(STRESS,encoding='utf-8')
            with (root/'filesystem/ProjectDetails.md').open('a',encoding='utf-8') as f:
                f.write('\n## Disposable engineering commissioning only\n\nAt the start of your first session, run `python3 commissioning_io.py` once. This is an IO stress test, not a robot skill. After it prints completion, perform your ordinary current assignment through the ordinary low-battery warning, navigate and dock, write normal closeout, then end. In later sessions, keep this file and its results but do not rerun it.\n')
            initial=inventory(root/'filesystem');save(root/'initial-filesystem.json',initial)
            run=read(root/'run.json');run['template']=initial;save(root/'run.json',run)
            first=execute(root,engineering_sessions=1,hibernate_after_s=10)
            result['conditions'][condition]=dict(first=first);save(out/'progress.json',result)
            if not first['passed']:raise ValueError(condition+' first failed: '+str(first.get('error')))
            proof=verify_checkpoint(read(root/'latest-checkpoint.json')['path'])
            result['checks'][condition+'_docked_checkpoint']=proof['passed']
            receipt=read(root/'filesystem/CommissioningIO/receipt.json')
            raw=(root/'filesystem/CommissioningIO/append.jsonl').read_bytes()
            result['checks'][condition+'_real_model_high_write']=receipt==dict(records=4096,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) and len(raw.splitlines())==4096
            # Fresh invocation under the same engineering config, with a shorter
            # second work window declared here before either session is run.
            # Keep baseline's original 30-minute first session; continuation is
            # tested on the next assignment, whose normal window is 240 seconds.
            second=execute(root,resume=True,engineering_sessions=1)
            result['conditions'][condition]['second']=second;save(out/'progress.json',result)
            if not second['passed']:raise ValueError(condition+' resume failed: '+str(second.get('error')))
            result['checks'][condition+'_fresh_resume']=verify_checkpoint(read(root/'latest-checkpoint.json')['path'])['passed']
            result['checks'][condition+'_stress_file_preserved']=sha(root/'filesystem/CommissioningIO/append.jsonl')==receipt['sha256']
            result['checks'][condition+'_two_reports']=len([p for p in (root/'filesystem/SessionReports').iterdir() if p.name!='SessionReportTemplate.md'])==2
        result['passed']=all(result['checks'].values())
    except BaseException as e:result.update(error=repr(e),traceback=traceback.format_exc())
    save(out/'result.json',result);print(canonical(result).decode());return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.output) else 1)
