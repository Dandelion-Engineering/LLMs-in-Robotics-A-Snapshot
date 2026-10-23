"""Retain the exact human amendment; never infer authority from old launch files."""
from pathlib import Path
import subprocess
import sys

CODE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(CODE))
from common import REPO,save,sha

path=REPO/'chats/Codex-Human/Apartment Simulation Commissioning/Apartment Simulation Commissioning - Active.md'
header='**Randy (2026-10-07 11:50 PDT):**'
text=path.read_text(encoding='utf-8')
assert text.count(header)==1
message=text.split(header,1)[1].split('\n**',1)[0].strip()
target=Path(__file__).with_name('launch-authority.json')
assert not target.exists()
save(target,dict(source=path.relative_to(REPO).as_posix(),source_sha256=sha(path),header=header,message=message,
    pulled_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
    scope='Reliability repair, disposable commissioning, pristine revised pair, baseline launch and live viewer, then observational monitoring every 30 minutes; requested hibernation takes priority; Maps requires a later human instruction.'))
print(str(target))
