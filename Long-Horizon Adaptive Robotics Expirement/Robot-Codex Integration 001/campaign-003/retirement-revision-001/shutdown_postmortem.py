"""One owned-server graceful SIGTERM after authenticated pre-shutdown copy.

This is postmortem cleanup, not successful retirement of the original pilot.
No service or other process is signaled; no mount in another namespace is changed.
"""
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import save,QUEUE,sha
from probe import RUN

CODE=r'''
import json,os,pathlib,select,signal,sys,time
run=pathlib.Path(sys.argv[1]);p=pathlib.Path('/proc/374')
fd=os.pidfd_open(374)
assert (p/'stat').read_text().split()[21]=='318','PID identity changed'
cmd=(p/'cmdline').read_bytes().split(b'\0')
assert any(x.endswith(b'/journal_fs.py') for x in cmd) and str(run).encode() in b' '.join(cmd)
assert not os.path.ismount(run/'workspace')
before=json.loads((run/'journal/mutations.jsonl').read_bytes().splitlines()[-1])
start=time.time_ns();signal.pidfd_send_signal(fd,signal.SIGTERM)
poll=select.poll();poll.register(fd,select.POLLIN);ended=bool(poll.poll(10000));os.close(fd)
after=json.loads((run/'journal/mutations.jsonl').read_bytes().splitlines()[-1])
print(json.dumps({'signal':'SIGTERM','pid':374,'start_ticks':318,'sent_wall_unix_ns':start,'ended_within_10s':ended,
'before':{k:before[k] for k in ('sequence','type','record_sha256','state_sha256')},
'after':{k:after[k] for k in ('sequence','type','record_sha256','state_sha256')},'observed_wall_unix_ns':time.time_ns()}))
'''
if __name__=='__main__':
 home=Path(__file__).resolve().parent;capture=home/'capture-before-shutdown'
 status=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status','20261004T035524536033Z-88ece806'],encoding='utf-8'))
 assert status['state']=='succeeded' and type(status['exit_status']) is int and status['exit_status']==0
 save(capture/'official-status.json',status)
 receipt=json.loads((capture/'receipt.json').read_text());assert receipt['passed'] and sha(capture/'journal.tar.gz')==receipt['archive_sha256']
 save(home/'shutdown-declaration.json',dict(model_calls=0,scope=__doc__,run=RUN,pid=374,start_ticks=318,signal='SIGTERM',pre_shutdown_archive_sha256=receipt['archive_sha256']))
 result=subprocess.run(['wsl.exe','-d','Ubuntu-24.04','--','python3','-B','-c',CODE,RUN],capture_output=True,text=True,encoding='utf-8',timeout=20)
 save(home/'shutdown-result.json',dict(exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr,scope='Postmortem; original pilot remains invalid'))
 print(result.stdout,result.stderr);assert result.returncode==0
