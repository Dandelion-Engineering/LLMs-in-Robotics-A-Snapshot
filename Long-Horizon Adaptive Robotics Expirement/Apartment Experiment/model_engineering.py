"""Fresh throwaway native sessions in both conditions; never official data."""
import argparse
import json
from pathlib import Path
import traceback
from common import save,canonical,read,inventory
from schedule import build
from run import prepare,execute
from recording import verify_checkpoint

def run(out):
    out.mkdir(parents=True,exist_ok=False)
    result=dict(passed=False,stage='throwaway-model-engineering',checks={},conditions={},official_sessions=0)
    try:
        for condition in ('baseline','maps'):
            root=out/condition;schedule=build(92214)
            config=dict(normal_work_s=45,throw_work_s=90,reserve_s=1800,model_wall_s=1200)
            prepare(root,condition,'engineering',schedule,config)
            first=execute(root,fixture_pose=[1,1,1.15],hibernate_after_s=15,engineering_sessions=1)
            result['conditions'][condition]={'first':first}
            save(out/'progress.json',result)
            if not first['passed']:raise ValueError(condition+' first engineering session failed: '+str(first.get('error')))
            receipt=verify_checkpoint(read(root/'latest-checkpoint.json')['path'])
            result['checks'][condition+'_deferred_checkpoint']=receipt['passed']
            position=read(Path(read(root/'latest-checkpoint.json')['path'])/'state.json')['position']
            second=execute(root,resume=True,engineering_sessions=1)
            result['conditions'][condition]['second']=second
            if not second['passed']:raise ValueError(condition+' resume engineering session failed: '+str(second.get('error')))
            receipt=verify_checkpoint(read(root/'latest-checkpoint.json')['path'])
            result['checks'][condition+'_fresh_resume']=receipt['passed']
            reports=[p for p in (root/'filesystem/SessionReports').iterdir() if p.name!='SessionReportTemplate.md']
            result['checks'][condition+'_two_reports']=len(reports)==2
            if condition=='maps':
                rooms=[p for p in (root/'filesystem/Maps/Rooms').glob('*.md') if p.name!='README.md']
                result['checks']['maps_created_from_experience']=bool(rooms)
            save(out/'progress.json',result)
        result['passed']=all(result['checks'].values())
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
    save(out/'result.json',result);print(canonical(result).decode());return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.output) else 1)
