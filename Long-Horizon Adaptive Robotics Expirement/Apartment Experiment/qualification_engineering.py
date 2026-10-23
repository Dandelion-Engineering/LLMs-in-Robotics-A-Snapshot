"""Final bounded apparatus suite; every component has separately inspectable evidence."""
import argparse
import importlib
from pathlib import Path
import traceback
from common import save,canonical

def run(out):
    out.mkdir(parents=True,exist_ok=False)
    result=dict(passed=False,stage='private-final-apparatus-suite',checks={},official_sessions=0,model_calls=0)
    try:
        for name in ('engineering','task_engineering','throw_engineering','navigation_engineering','boundary_engineering','lifecycle_engineering'):
            result['checks'][name]=importlib.import_module(name).run(out/name) is True
            save(out/'progress.json',result)
        result['passed']=all(result['checks'].values())
    except BaseException as e:result.update(error=repr(e),traceback=traceback.format_exc())
    save(out/'result.json',result);print(canonical(result).decode());return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.output) else 1)
