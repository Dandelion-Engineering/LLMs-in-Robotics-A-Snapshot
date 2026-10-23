"""Run the fully declared V33 coordinator once; retain launch and completion."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
C=HERE.parents[1]
REPO=HERE.parents[4]
Q=C/'qualification'

def identity(path):
    path=Path(path).resolve()
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

def save(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2);f.write('\n');f.flush()

def main():
    preflight=json.loads((C/'io-repair/print-recipe-qualification-001/readiness-preflight-001.json').read_text(encoding='utf-8'))
    script=Q/'run_final_qualification_v33.py'
    readiness=Q/'final-qualification-033-readiness.json'
    assert preflight['passed'] is True and preflight['coordinator']==identity(script) and preflight['readiness']==identity(readiness)
    assert identity(readiness)['sha256']=='4c13a48649db3eb210b3db281a4890e6b070e762b10a8a4faca83fe4244d4a91'
    assert not (Q/'final-qualification-033').exists()
    assert not any((HERE/name).exists() for name in ('launch-intent.json','process.json','completion.json','coordinator.stdout','coordinator.stderr'))
    command=[sys.executable,'-X','utf8','-B',str(script),'--readiness',str(readiness),'--readiness-sha256',identity(readiness)['sha256']]
    save(HERE/'launch-intent.json',{'argv':command,'cwd':str(REPO),'runner':identity(__file__),'readiness':identity(readiness),'coordinator':identity(script),'created_at':datetime.now(timezone.utc).isoformat(),'scope':'Qualification only; all empirical children use the shared queue; no scored launch.'})
    with (HERE/'coordinator.stdout').open('x',encoding='utf-8') as stdout,(HERE/'coordinator.stderr').open('x',encoding='utf-8') as stderr:
        process=subprocess.Popen(command,cwd=REPO,stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        save(HERE/'process.json',{'pid':process.pid,'argv':command,'launched_at':datetime.now(timezone.utc).isoformat(),'launch_intent':identity(HERE/'launch-intent.json')})
        print(json.dumps({'coordinator_pid':process.pid,'state':'running'}),flush=True)
        code=process.wait()
    save(HERE/'completion.json',{'exit_code':code,'ended_at':datetime.now(timezone.utc).isoformat(),'stdout':identity(HERE/'coordinator.stdout'),'stderr':identity(HERE/'coordinator.stderr'),'launch_intent':identity(HERE/'launch-intent.json')})
    print(json.dumps({'state':'completed','exit_code':code}),flush=True)
    return code

if __name__=='__main__':raise SystemExit(main())
