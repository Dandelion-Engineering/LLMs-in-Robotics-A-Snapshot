"""Artificial boundary sentinels only; never reads secret/host content."""
import json
from pathlib import Path
import socket

checks={}
checks['prompt_visible']=Path('/workspace/RobotAgentPrompt.md').is_file()
checks['host_roots_absent']=not Path('/mnt').exists() and not Path('/proc/1/root/mnt').exists()
checks['scheduler_absent']=not Path('/workspace/schedule.json').exists()
probe=Path('/workspace/.boundary-probe')
probe.write_text('artificial boundary probe');checks['workspace_writable']=probe.read_text()=='artificial boundary probe';probe.unlink()
try:
    with Path('/workspace/RobotDetails.md').open('ab') as out:out.write(b'')
    checks['contract_readonly']=False
except OSError:checks['contract_readonly']=True
try:
    sock=socket.create_connection(('1.1.1.1',443),.2);sock.close();checks['internet_denied']=False
except OSError:checks['internet_denied']=True
print(json.dumps(dict(qualified=all(checks.values()),host_qualified=all(checks.values()),checks=checks)))
raise SystemExit(0 if all(checks.values()) else 1)
