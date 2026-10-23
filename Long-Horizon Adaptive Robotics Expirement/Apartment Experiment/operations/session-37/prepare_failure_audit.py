"""Declare the terminal preservation task; this cannot submit an experiment."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[3]
PAIR=Path('D:/Dandelion-Apartment-Experiment/official/apartment-v3')
OP=PAIR/'operator/failure-audit-session37-001'
QUEUE=REPO.parent/'tools/compute_queue/compute_queue.py'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(d,f,indent=2);f.write('\n')
OP.mkdir(parents=True,exist_ok=False)
status=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status','20261009T010627656726Z-71e4ed51'],text=True,encoding='utf-8'))
assert status['state']=='failed' and type(status['exit_status']) is int and status['exit_status']==1
save(OP/'official-queue-status.json',status);save(HERE/'official-terminal.json',status)
cfg_path=Path('C:/Users/cresp/.codex/automations/apartment-v3-baseline-observations/automation.toml')
cfg=tomllib.loads(cfg_path.read_text(encoding='utf-8'));assert cfg['status']=='PAUSED'
paused=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),automation_id=cfg['id'],status=cfg['status'],
            kind=cfg['kind'],target_thread=cfg['target_thread_id'],interval_minutes=30,queue_job=status['id'],
            endpoint_complete=False,reason='Terminal workspace-startup FUSE mount deadline at session 15; audit and normal Session37 closeout in progress.',
            config_sha256=sha(cfg_path))
save(OP/'monitoring-paused.json',paused);save(HERE/'monitoring-paused.json',paused)
frozen=OP/'preservation';frozen.mkdir()
shutil.copyfile(HERE/'preserve_failure.py',frozen/'preserve_failure.py')
save(frozen/'manifest.json',dict(source=str(HERE/'preserve_failure.py'),sha256=sha(frozen/'preserve_failure.py'),
     scope='Only read condition files and copy failed startup to operator evidence; no runtime action.'))
argv=[sys.executable,'-X','utf8','-B',str(QUEUE),'submit','--project','LLMs-in-Robotics','--cwd',str(frozen),'--',sys.executable,'-X','utf8','-B',str(frozen/'preserve_failure.py')]
save(frozen/'submission-intent.json',dict(argv=argv,created_utc=datetime.now(timezone.utc).isoformat()))
response=subprocess.run(argv,text=True,capture_output=True,encoding='utf-8')
save(frozen/'submission-response.json',dict(exit_status=response.returncode,stdout=response.stdout,stderr=response.stderr))
assert response.returncode==0,'Inspect retained submission before any next action'
submitted=json.loads(response.stdout);save(frozen/'queue-submission.json',submitted);save(HERE/'failure-preservation-queue.json',submitted)
print(json.dumps(dict(job=submitted['id'],state=submitted['state'],output=str(frozen/'output'))))
