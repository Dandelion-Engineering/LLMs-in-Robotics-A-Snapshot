"""Retain each bounded lineage test command and exact owned source identities."""
from pathlib import Path
import datetime
import hashlib
import json
import re
import subprocess
import sys

HERE=Path(__file__).resolve().parent
C=HERE.parents[1]
REPO=C.parents[2]

def bind(path):
    raw=path.read_bytes()
    return {'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()

name,area=sys.argv[1:]
before=json.loads((HERE/'before-and-absence.json').read_text(encoding='utf-8'))
names=before['owned_existing_files']+before['new_files']
sources={n:bind(C/n) for n in names}
if area=='qualification':
    modules=['test_run_final_qualification_v28','test_prepare_model_v20','test_prepare_native','test_prepare_boundary_v3']
elif area=='admission': modules=['test_prepare_admission']
else: raise ValueError('Only bounded focused test groups are permitted')
command=[str(REPO/'venv/Scripts/python.exe'),'-X','utf8','-B','-m','unittest','-v',*modules]
started=now()
result=subprocess.run(command,cwd=C/area,capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
for suffix,raw in [('stdout',result.stdout),('stderr',result.stderr)]:
    with (HERE/(name+'.'+suffix)).open('xb') as f:f.write(raw)
after={n:bind(C/n) for n in names}
tests=re.findall(rb'Ran (\d+) tests? in ',result.stderr)
value={'schema':'campaign002-lineage-focused-check-1','command':command,'cwd':str(C/area),
       'started_at':started,'ended_at':now(),'exit_code':result.returncode,
       'passed':result.returncode==0 and sources==after,'tests_run':int(tests[-1]) if tests else None,
       'source_bindings_before':sources,'source_bindings_after':after,'sources_unchanged':sources==after,
       'stdout':{'path':str(HERE/(name+'.stdout')),**bind(HERE/(name+'.stdout'))},
       'stderr':{'path':str(HERE/(name+'.stderr')),**bind(HERE/(name+'.stderr'))}}
with (HERE/(name+'.json')).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2);f.write('\n')
print(json.dumps({'receipt':str(HERE/(name+'.json')),'exit_code':result.returncode,'tests_run':value['tests_run'],
                  'passed':value['passed']}))
if result.returncode:print(result.stderr.decode('utf-8',errors='replace'))
raise SystemExit(0 if value['passed'] else 1)
