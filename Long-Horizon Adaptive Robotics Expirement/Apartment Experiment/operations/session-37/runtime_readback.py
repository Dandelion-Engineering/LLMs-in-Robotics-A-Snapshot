"""Read-only closeout process, queue and monitor status; no runtime starts."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from attempts import HERE, QUEUE, save

windows = json.loads(subprocess.check_output(['powershell', '-NoProfile', '-Command',
    "ConvertTo-Json -Compress -InputObject @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(python|pythonw|wsl|node|codex)(\\.exe)?$' } | Select-Object ProcessId,Name,CommandLine)"], text=True, encoding='utf-8'))
windows = [r for r in windows if r['ProcessId'] != os.getpid()
    and 'apartment' in (r.get('CommandLine') or '').lower()]
probe_launchers = [r for r in windows if 'operations/session-37/runtime_readback.py' in (r.get('CommandLine') or '').replace('\\', '/')]
windows = [r for r in windows if r not in probe_launchers]
probe = """import os,json,pathlib
items=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name)==os.getpid(): continue
 try:
  args=(p/'cmdline').read_bytes().replace(b'\\0',b' ').decode(errors='replace')
  if 'apartment' in args.lower(): items.append({'pid':int(p.name),'command':args})
 except (FileNotFoundError,PermissionError): pass
print(json.dumps(items))
"""
linux = json.loads(subprocess.check_output(['wsl.exe','-d','Ubuntu-24.04','--','python3','-B','-c',probe],text=True,encoding='utf-8'))
queues = {state:json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'list','--state',state],text=True,encoding='utf-8')) for state in ['running','queued']}
monitors=[]
automation_root=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'automations'
for p in automation_root.glob('*/automation.toml'):
    r=tomllib.loads(p.read_text(encoding='utf-8'))
    if p.parent.name in ['apartment-v2-baseline-observations','apartment-v2-maps-observations']:
        monitors.append(dict(id=p.parent.name,status=r.get('status'),path=str(p)))
result=dict(recorded_at=datetime.now(timezone.utc).isoformat(),windows_matches=windows,
    linux_matches=linux,queues=queues,monitors=monitors,
    new_official_launches=0,new_monitors=0,excluded_probe_launchers=probe_launchers,
    probe_scope='Only this current read-only probe and its Windows venv launcher are excluded. No simulator or native-runtime process is excluded.')
result['passed']=not windows and not linux and not any(queues.values()) and len(monitors)==2 and all(r['status']=='PAUSED' for r in monitors)
assert not (HERE/'runtime-prelaunch-002.json').exists()
save(HERE/'runtime-prelaunch-002.json',result)
print(json.dumps(result,indent=2))
raise SystemExit(0 if result['passed'] else 1)
