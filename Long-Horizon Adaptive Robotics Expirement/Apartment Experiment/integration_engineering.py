"""Private two-condition namespace, native preflight and lifecycle tests."""
import argparse
import asyncio
from pathlib import Path
import traceback
from common import save,canonical,read,inventory
from deployment import instantiate
from schedule import build
from controller import Controller

def run(out):
    out.mkdir(parents=True,exist_ok=False);result=dict(passed=False,stage='throwaway-runtime-engineering',checks={},model_calls=0,official_sessions=0)
    control=guest=workspace=None
    try:
        from native_runtime import Workspace,Guest
        for condition in ('baseline','maps'):
            root=out/condition;instantiate(condition,root/'filesystem')
            control=Controller(root,build(4321),dict(normal_work_s=90,throw_work_s=240,reserve_s=1800),condition)
            endpoint=control.start()
            workspace=Workspace(root/'namespace',root/'filesystem','engineering-preflight-'+condition)
            guest=Guest(root/'native',workspace,endpoint,control)
            guest.qualify();result['checks'][condition+'_namespace']=True
            asyncio.run(guest.model(timeout=120,preflight=True))
            native=read(root/'native/client/result.json')
            result['checks'][condition+'_native_preflight']=bool(native.get('success') and native.get('preflight_passed') and not native.get('model_started'))
            result['checks'][condition+'_guest_retired']=guest.close();guest=None
            final,proof=workspace.close();workspace=None
            result['checks'][condition+'_journal_retired']=proof['passed']
            result['checks'][condition+'_filesystem_unchanged']=inventory(root/'filesystem')==inventory(final)
            control.close();control=None
        result['passed']=all(result['checks'].values())
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
    finally:
        if guest:
            try:guest.close()
            except Exception as e:result['guest_cleanup_error']=repr(e)
        if workspace:
            try:workspace.close()
            except Exception as e:result['workspace_cleanup_error']=repr(e)
        if control:control.close()
        save(out/'result.json',result)
    print(canonical(result).decode());return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.output) else 1)
