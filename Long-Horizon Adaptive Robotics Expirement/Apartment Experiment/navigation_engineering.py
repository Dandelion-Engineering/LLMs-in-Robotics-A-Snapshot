"""Physical charger approaches and conservative apartment route bound."""
import argparse
import math
from pathlib import Path
import traceback
import numpy as np
from common import save,canonical
from scene import CHARGERS
from world import World
from engineering import move,relocate_for_fixture
from task_engineering import travel,turn,stow

def run(out):
    out.mkdir(parents=True,exist_ok=False);result=dict(passed=False,checks={},measurements={},official_sessions=0,model_calls=0,stage='private-navigation-engineering');w=None
    try:
        for i,(x,y) in enumerate(CHARGERS):
            w=World();relocate_for_fixture(w,x+.55,y,math.pi);stow(w);w.begin_session(.01,3600)
            start=w.time;move(w,'base',forward=.55);move(w,'dock')
            result['checks']['charger_'+str(i)+'_physical_approach']=w.docked and np.linalg.norm(w.base_pose()[:2]-[x,y])<.04
            result['measurements']['charger_'+str(i)+'_approach_s']=w.time-start;w.close();w=None
        # Widely spaced safe room-to-room route: living -> bedroom -> bathroom -> kitchen.
        w=World();stow(w);started=w.time
        for x,y in [(3.7,3.1),(3.55,4.65),(3.0,5.65),(3.3,6.8),(5.1,7.1),(6.8,7.1),(9.1,7.5),(9.1,5.6),(9.1,4.05),(9.85,4.05),(9.85,2.0),(9.85,.5),(7.5,.5),(7.5,1.0),(7.0,1.0)]:travel(w,x,y)
        turn(w,math.pi);w.begin_session(.01,3600);move(w,'wait',duration=.1);move(w,'dock')
        result['checks']['four_rooms_route_docks']=w.docked
        result['measurements']['four_rooms_route_sim_s']=w.time-started
        result['measurements']['reserve_s']=3600
        result['checks']['reserve_exceeds_full_apartment_tour_by_10x']=3600>10*(w.time-started)
        result['passed']=all(result['checks'].values())
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
    finally:
        if w:w.close()
        save(out/'result.json',result)
    print(canonical(result).decode());return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.output) else 1)
