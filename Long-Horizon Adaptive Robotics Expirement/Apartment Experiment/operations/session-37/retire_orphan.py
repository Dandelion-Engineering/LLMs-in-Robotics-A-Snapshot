"""One bounded retirement of the preserved, identified session-15 filesystem.

This sends no robot command, invokes no model, and never rewrites the failed
execution receipt. Only normal unmount and the existing retirement protocol are
used. Failure is retained; this script has no force-kill or retry branch.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import traceback

HERE=Path(__file__).resolve().parent;REPO=HERE.parents[3]
PAIR=Path('D:/Dandelion-Apartment-Experiment/official/apartment-v3')
ROOT=PAIR/'baseline';OP=PAIR/'operator/failure-audit-session37-001'
W=ROOT/'sessions/session-00015/workspace'
def read(p):return json.loads(p.read_bytes())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,d):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(d,f,indent=2);f.write('\n')

def main():
    queue=REPO.parent/'tools/compute_queue/compute_queue.py'
    submission=read(OP/'preservation/queue-submission.json')
    status=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(queue),'status',submission['id']],text=True,encoding='utf-8'))
    assert status['state']=='succeeded' and type(status['exit_status']) is int and status['exit_status']==0
    assert read(OP/'preservation/output/result.json')['passed'] is True
    save(OP/'preservation/queue-terminal.json',status)
    expected=read(OP/'preservation/output/partial-before.json')
    actual={p.relative_to(W).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in W.rglob('*') if p.is_file()}
    assert actual==expected,'Partial startup changed since the complete preservation copy'
    identity=read(W/'journal/service-identity.json')
    assert identity['run_id']=='apartment-8fa2585eb8a44d11bc6a64a2867d60f1'
    assert identity==read(OP/'preservation/output/session-00015-before-cleanup/journal/service-identity.json')
    execution_pointer=read(ROOT/'latest-execution.json')
    save(OP/'operator-retirement-intent.json',dict(created_utc=datetime.now(timezone.utc).isoformat(),identity=identity,
         preservation_result_sha256=sha(OP/'preservation/output/result.json'),execution_pointer=execution_pointer,
         actions=['Existing filesystem control checkpoint to require zero open handles','Normal fusermount3 -u on exact recorded mount','Existing authenticated retire request only if service remains alive'],
         no_model_call=True,no_robot_command=True,no_resume=True,no_repair=True,no_forced_unmount_or_kill=True))
    code="""import json,os,pathlib,socket,subprocess,sys,time,traceback
x=json.load(sys.stdin);p=pathlib.Path('/proc')/str(x['pid']);result=dict(passed=False,identity=x,actions=[])
def same():
 if not p.exists():return False
 fields=(p/'stat').read_text().rsplit(')',1)[1].split();cmd=(p/'cmdline').read_bytes()
 return fields[19]==x['start_ticks'] and x['mount'].encode() in cmd
def request(value):
 with socket.socket(socket.AF_UNIX) as client:
  client.settimeout(5);client.connect(str(pathlib.Path(x['mount']).parent/'journal-control.sock'))
  client.sendall((json.dumps(value)+'\\n').encode());reply=json.loads(client.makefile().readline())
  if reply.get('error'):raise RuntimeError(reply['error'])
  return reply
try:
 assert same(),'Recorded service identity no longer matches'
 assert os.path.ismount(x['mount']),'Recorded mount no longer present; inspect without repeating cleanup'
 before=request({'label':'operator-retirement-session37-preflight'})
 result['checkpoint']=before;assert before['open_handles']==0 and before['healthy'] is True
 result['actions'].append('Authenticated checkpoint confirms zero open handles')
 unmount=subprocess.run(['fusermount3','-u',x['mount']],capture_output=True,text=True,timeout=10)
 result['unmount']=dict(returncode=unmount.returncode,stdout=unmount.stdout,stderr=unmount.stderr)
 assert unmount.returncode==0,unmount.stderr
 assert not os.path.ismount(x['mount'])
 result['actions'].append('Normal unmount completed')
 if same():
  try:result['retire_response']=request({'command':'retire','run_id':x['run_id']})
  except (FileNotFoundError,ConnectionRefusedError):
   if same():raise
   result['retire_response']={'already_closed':True}
 end=time.monotonic()+20
 while same() and time.monotonic()<end:time.sleep(.1)
 assert not same(),'Identified service remains alive after bounded retirement wait'
 result.update(passed=True,recorded_service_retired=True,mounted=os.path.ismount(x['mount']))
except BaseException as error:result.update(error=repr(error),traceback=traceback.format_exc())
print(json.dumps(result));sys.exit(0 if result['passed'] else 1)
"""
    response=subprocess.run(['wsl.exe','-d','Ubuntu-24.04','--','python3','-B','-c',code],input=json.dumps(identity),capture_output=True,text=True,encoding='utf-8',timeout=45)
    result=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),exit_status=response.returncode,stdout=response.stdout,stderr=response.stderr,
                original_execution_receipt_unchanged=read(ROOT/'latest-execution.json')==execution_pointer and sha(Path(execution_pointer['path']))==execution_pointer['sha256'],
                experiment_outcome='failed; never changed by operator retirement')
    try:result['cleanup']=json.loads(response.stdout)
    except ValueError:result['cleanup']={'passed':False,'error':'No structured retirement response'}
    result['native_exit']=read(W/'journal/native-exit.json') if (W/'journal/native-exit.json').exists() else None
    result['passed']=response.returncode==0 and result['cleanup'].get('passed') is True and result['original_execution_receipt_unchanged'] and result['native_exit'] is not None
    save(OP/'operator-retirement.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('stdout','stderr')}))
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
