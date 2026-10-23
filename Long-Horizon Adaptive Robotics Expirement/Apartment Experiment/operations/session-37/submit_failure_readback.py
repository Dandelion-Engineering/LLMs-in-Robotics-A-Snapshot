"""Freeze and submit one read-only terminal audit; never a model experiment."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import shutil,subprocess,sys

HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
PAIR=Path('D:/Dandelion-Apartment-Experiment/official/apartment-v3')
OP=PAIR/'operator/failure-audit-session37-001';FROZEN=OP/'audit'
def read(p):return json.loads(p.read_bytes())
def save(p,d):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(d,f,indent=2);f.write('\n')
assert read(OP/'runtime-after-cleanup.json')['all_runtime_retired'] is True
assert read(OP/'preservation/output/result.json')['passed'] is True
FROZEN.mkdir(exist_ok=False);shutil.copyfile(HERE/'audit_failure.py',FROZEN/'audit_failure.py')
save(FROZEN/'manifest.json',dict(created_utc=datetime.now(timezone.utc).isoformat(),sha256=hashlib.sha256((FROZEN/'audit_failure.py').read_bytes()).hexdigest(),
 purpose='Authenticate incomplete failed history, preserved pre-cleanup evidence and separate runtime retirement. Audit pass never changes official failure.',
 frozen_runtime=str(PAIR/'frozen_repository'),automatic_retry=False))
queue=REPO.parent/'tools/compute_queue/compute_queue.py'
argv=[sys.executable,'-X','utf8','-B',str(queue),'submit','--project','LLMs-in-Robotics','--cwd',str(FROZEN),'--',sys.executable,'-X','utf8','-B',str(FROZEN/'audit_failure.py')]
save(FROZEN/'submission-intent.json',dict(argv=argv))
response=subprocess.run(argv,capture_output=True,text=True,encoding='utf-8')
save(FROZEN/'submission-response.json',dict(exit_status=response.returncode,stdout=response.stdout,stderr=response.stderr))
assert response.returncode==0,'Inspect retained submission before another action'
submitted=json.loads(response.stdout);save(FROZEN/'queue-submission.json',submitted);save(HERE/'failure-audit-queue.json',submitted)
print(json.dumps(dict(job=submitted['id'],state=submitted['state'],output=str(FROZEN/'output'))))
