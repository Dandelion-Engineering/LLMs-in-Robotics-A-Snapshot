"""Clean, uncoached household sessions with the calibrated deployment windows."""
import argparse
from pathlib import Path
import traceback
from common import save,read,canonical,sha
from schedule import build
from run import prepare,execute

def run(out):
    out.mkdir(parents=True,exist_ok=False)
    result=dict(passed=False,stage='private-calibrated-native-sessions',conditions={},checks={},official_sessions=0)
    try:
        schedule=build(96150)
        k=next(i for i,r in enumerate(schedule['assignments']) if r['kind']=='kitchen')
        rows=schedule['assignments'];rows[0],rows[k]=rows[k],rows[0]
        for i,row in enumerate(rows):row['position']=i
        # This private reordered schedule is not used for either official condition.
        config=dict(normal_work_s=240,throw_work_s=1800,reserve_s=3600,model_wall_s=7200)
        for condition in ('baseline','maps'):
            root=out/condition;prepare(root,condition,'engineering',schedule,config)
            outcome=execute(root,engineering_sessions=1,hibernate_after_s=20)
            result['conditions'][condition]=outcome
            save(out/'progress.json',result)
            if not outcome['passed']:raise ValueError(condition+' calibrated session failed: '+str(outcome.get('error')))
            result['checks'][condition+'_normal_session']=True
            result['checks'][condition+'_native_clock_bridges']=all((p/'workspace/clock-bridge.jsonl').is_file() for p in (root/'sessions').iterdir())
            state=read(Path(read(root/'latest-checkpoint.json')['path'])/'state.json')
            result['checks'][condition+'_docked_checkpoint']=state['world']['docked']
            result['checks'][condition+'_namespace_preserved']=(root/'filesystem-namespace.json').is_file()
            if condition=='maps':
                rooms=[p.name for p in (root/'filesystem/Maps/Rooms').glob('*.md') if p.name!='README.md']
                result['room_maps']=rooms
                result['checks']['maps_room_transition_exercised']=len(rooms)>=2
        result['passed']=all(result['checks'].values())
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
    save(out/'result.json',result);print(canonical(result).decode());return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.output) else 1)
