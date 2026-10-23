"""Exercise the frozen directory layout and native preflight without a model turn."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import traceback
from common import save,canonical,read
from freeze import copy_sources
from run import source_identity

def run(out):
    out.mkdir(parents=True,exist_ok=False);r=dict(passed=False,checks={},official_sessions=0,model_calls=0,stage='private-frozen-bundle-preflight')
    try:
        frozen=copy_sources(out/'frozen_repository')
        actual=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B','-c','import run,json;print(json.dumps(run.source_identity()))'],cwd=frozen,text=True,encoding='utf-8'))
        r['checks']['all_frozen_inputs_identical']=actual==source_identity()
        process=subprocess.run([sys.executable,'-X','utf8','-B',str(frozen/'integration_engineering.py'),'--output',str(out/'preflight')],cwd=frozen,capture_output=True,text=True,encoding='utf-8',timeout=600)
        (out/'preflight-console.txt').write_text(process.stdout+process.stderr,encoding='utf-8')
        r['checks']['frozen_native_preflight']=process.returncode==0 and read(out/'preflight/result.json')['passed'] is True
        r['passed']=all(r['checks'].values())
    except BaseException as e:r.update(error=repr(e),traceback=traceback.format_exc())
    save(out/'result.json',r);print(canonical(r).decode());return r['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.output) else 1)
