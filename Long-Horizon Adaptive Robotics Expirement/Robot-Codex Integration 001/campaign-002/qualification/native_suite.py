"""Six predeclared no-model reference episodes; each failure remains a result."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

CAMPAIGN=Path(__file__).resolve().parents[1]
RCI=CAMPAIGN.parent
REPO=RCI.parents[1]
spec=importlib.util.spec_from_file_location('c02_challenges',RCI/'host/challenges.py')
challenges=importlib.util.module_from_spec(spec);spec.loader.exec_module(challenges)

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream: json.dump(value,stream,indent=2);stream.write('\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();plan=json.loads(a.manifest.read_text(encoding='utf-8'))
    a.output.mkdir(parents=True,exist_ok=False)
    rows=[]
    for slot in plan['slots']:
        folder=a.output/slot['run_id'];folder.mkdir()
        manifest=slot['manifest'];mp=folder/'manifest.json';save(mp,manifest)
        free=shutil.disk_usage(REPO).free
        if free<102_000_000_000:raise RuntimeError('Free reserve threatened before reference episode')
        argv=[sys.executable,'-X','utf8','-B',str(CAMPAIGN/'harness/run_host.py'),
              '--manifest',str(mp),'--evidence',str(folder/'host'),'--runtime-workspace',slot['workspace']]
        first=time.time()
        with (folder/'stdout.txt').open('x',encoding='utf-8') as out,(folder/'stderr.txt').open('x',encoding='utf-8') as err:
            completed=subprocess.run(argv,cwd=REPO,stdout=out,stderr=err,timeout=1150,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
        row={'run_id':slot['run_id'],'exit_code':completed.returncode,'started_unix_s':first,'ended_unix_s':time.time(),
             'free_before':free,'free_after':shutil.disk_usage(REPO).free,'argv':argv,
             'manifest_sha256':hashlib.sha256(mp.read_bytes()).hexdigest()}
        # Diagnostic summary only; root consumes after official queue succeeded/0.
        host=folder/'host/result.json'
        if host.exists():
            value=json.loads(host.read_text(encoding='utf-8'))
            row.update(terminal=value.get('terminal'),execution_completed=value.get('execution_completed'),
                       independent_outcome=value.get('independent_outcome'),timing=value.get('timing'),timing_v2=value.get('timing_v2'))
        save(folder/'execution.json',row);rows.append(row)
    save(a.output/'suite-result.json',{'schema':'campaign002-native-suite-1','run_id':plan['run_id'],
         'completed_utc':datetime.now(timezone.utc).isoformat(),'rows':rows,'all_slots_executed':len(rows)==len(plan['slots']),
         'model_calls':0,'scope':'No-model apparatus qualification; separate assessment authenticates official queue completion.'})
    print(json.dumps({'completed':len(rows),'run_id':plan['run_id'],'model_calls':0}))

if __name__=='__main__':main()
