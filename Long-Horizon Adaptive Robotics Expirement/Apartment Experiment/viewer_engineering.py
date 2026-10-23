"""Bounded detached replay preview for browser qualification through the shared queue."""
import argparse
from pathlib import Path
import time
import traceback
from common import HERE,DEFAULT_ROOT,save,read,sha,canonical
from viewer import serve,Files

def run(out):
    out.mkdir(parents=True,exist_ok=False)
    root=DEFAULT_ROOT/'engineering/APARTMENT-live003/output/baseline'
    result=dict(passed=False,stage='private-viewer-engineering',checks={},official_sessions=0,model_calls=0)
    server=replay=None
    try:
        # Read-only renderer upgrade over the identical recorded geometry definition.
        source=DEFAULT_ROOT/'engineering/APARTMENT-live003/source'
        if sha(source/'scene.py')!=sha(HERE/'scene.py'):raise ValueError('Replay geometry differs from recorded source')
        server,replay=serve(root,port=8818)
        frame=replay.frame(1e9);files=Files(root)
        result['checks']['recorded_states']=frame['range'][1]>frame['range'][0]
        result['checks']['aligned_files']=bool(files.listing(frame['range'][1])['files'])
        result['checks']['future_files_withheld']=not files.listing(-1)['files']
        save(out/'ready.json',dict(url='http://127.0.0.1:8818',root=str(root),range=frame['range'],expires_after_s=600))
        print('Bounded observer preview: http://127.0.0.1:8818 (600 seconds)',flush=True)
        end=time.monotonic()+600
        while time.monotonic()<end and not (out/'qa-complete.json').exists():time.sleep(.2)
        if not (out/'qa-complete.json').exists():raise ValueError('Browser QA did not complete during bounded preview')
        result['checks']['browser_checks']=read(out/'qa-complete.json')['passed'] is True
        result['passed']=all(result['checks'].values())
    except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
    finally:
        if server:server.shutdown();server.server_close()
        if replay:replay.close()
        save(out/'result.json',result)
    print(canonical(result).decode());return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.output) else 1)
