"""Read-only, exact-owned-run retirement probe. Does not signal processes."""
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import save

RUN='/var/tmp/robot-codex-session10/c03-1f2177d956dc4cb09df12dfe8288392f'
CODE=r'''
import json,os,pathlib,time
run=pathlib.Path(__import__('sys').argv[1]);workspace=str(run/'workspace')
def read(p):
 try:return p.read_text()
 except OSError as e:return str(e)
def link(p):
 try:return os.readlink(p)
 except OSError as e:return str(e)
def details(p):
 return {'pid':p.name,'comm':read(p/'comm').strip(),'namespace':link(p/'ns/mnt'),'status':read(p/'status'),
 'tasks':[{'tid':t.name,'wchan':read(t/'wchan'),'syscall':read(t/'syscall'),'stack':read(t/'stack')} for t in (p/'task').iterdir()],
 'fds':{f.name:link(f) for f in (p/'fd').iterdir()},'cwd':link(p/'cwd'),'root':link(p/'root')}
server=[];mounts=[];references=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdecimal():continue
 try:
  cmd=(p/'cmdline').read_bytes().split(b'\0')
  if any(x.endswith(b'/journal_fs.py') for x in cmd) and str(run).encode() in b' '.join(cmd):server.append(details(p))
  matching=[x for x in read(p/'mountinfo').splitlines() if workspace in x]
  if matching:mounts.append({'pid':p.name,'comm':read(p/'comm').strip(),'namespace':link(p/'ns/mnt'),'mounts':matching})
  refs={}
  for f in [p/'cwd',p/'root',*(p/'fd').iterdir()]:
   target=link(f)
   if target.startswith(workspace):refs[str(f)]=target
  if refs:references.append({'pid':p.name,'comm':read(p/'comm').strip(),'refs':refs})
 except (OSError,ProcessLookupError):pass
tail=(run/'journal/mutations.jsonl').read_bytes().splitlines()[-1]
print(json.dumps({'wall_unix_ns':time.time_ns(),'run':str(run),'is_mount':os.path.ismount(workspace),'servers':server,'mounts':mounts,'references':references,'last_record':json.loads(tail)}))
'''
if __name__=='__main__':
    p=subprocess.run(['wsl.exe','-d','Ubuntu-24.04','--','python3','-B','-c',CODE,RUN],capture_output=True,text=True,encoding='utf-8',timeout=25)
    if p.returncode:raise RuntimeError(p.stderr)
    data=json.loads(p.stdout);save(sys.argv[1],data)
    print(json.dumps(data,indent=2))
