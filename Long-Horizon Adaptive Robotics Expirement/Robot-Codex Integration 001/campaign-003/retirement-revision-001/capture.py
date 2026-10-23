"""Byte-preserving postmortem copy; never repairs the original attempt."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import HERE,save,sha
from workspace_block import linux,wsl
from probe import RUN

CODE=r'''
import hashlib,json,pathlib,sys,tarfile,time
run=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2])
def inventory():
 files=[run/'initial.json',run/'identity.json']
 for folder in ('journal','terminal'):
  files.extend(p for p in (run/folder).rglob('*') if p.is_file() and not p.is_symlink())
 return {str(p.relative_to(run)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)}
before=inventory();started=time.time_ns()
with tarfile.open(out/'journal.tar.gz','x:gz') as archive:
 for name in before:archive.add(run/name,arcname=name,recursive=False)
after=inventory()
result={'before':before,'after':after,'unchanged':before==after,'started_wall_ns':started,'ended_wall_ns':time.time_ns()}
(out/'linux-preservation.json').write_text(json.dumps(result,sort_keys=True)+'\n',encoding='utf-8')
assert before==after,'Live source changed during postmortem capture'
print(json.dumps({'unchanged':True,'files':len(before),'source_bytes':sum(x['bytes'] for x in before.values())}))
'''
if __name__=='__main__':
 out=Path(sys.argv[1]).resolve();out.mkdir(exist_ok=False)
 assert shutil.disk_usage(out).free>=104*1024**3,'Export capacity admission'
 episode=HERE/'live-evidence/RCI001-C03-pilot-002-attempt'
 ids=json.loads((HERE/'qualification/pilot-audit-002/assessment/input-identities.json').read_text())
 # Postmortem signaling appended the captured native return8 traceback to
 # exactly the original daemon log. Retain its before/after identity; never
 # require or pretend that this log stayed at its pre-shutdown empty value.
 allowed=json.loads((Path(__file__).resolve().parent/'postmortem-windows-change.json').read_text())['changed']
 expected={n:(allowed[n]['after'] if n in allowed else v) for n,v in ids.items()}
 assert set(allowed)=={'workspace-block/fuse-server.log'}
 assert all(sha(episode/n)==v['sha256'] for n,v in expected.items())
 p=subprocess.run(['wsl.exe','-d','Ubuntu-24.04','--','python3','-B','-c',CODE,RUN,wsl(out)],capture_output=True,text=True,encoding='utf-8',timeout=120)
 if p.returncode:raise RuntimeError(p.stderr)
 assert all(sha(episode/n)==v['sha256'] for n,v in expected.items())
 save(out/'receipt.json',dict(passed=True,model_calls=0,original_pilot_disposition='infrastructure-invalid; task outcome unknown',
     scope='Postmortem archive only; missing original retirement remains unqualified.',original_windows_files_unchanged=len(ids)-len(allowed),postmortem_changed_files=allowed,
     linux=json.loads(p.stdout),archive_sha256=sha(out/'journal.tar.gz'),archive_bytes=(out/'journal.tar.gz').stat().st_size))
 print((out/'receipt.json').read_text())
