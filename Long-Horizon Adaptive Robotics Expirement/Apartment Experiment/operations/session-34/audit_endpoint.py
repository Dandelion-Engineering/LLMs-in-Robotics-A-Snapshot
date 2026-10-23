"""Submit one independent completed-endpoint audit with frozen runtime readers."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

CODE = Path(__file__).resolve().parents[2]
REPO = CODE.parents[1]
sys.path.insert(0, str(CODE))
from common import read, save, canonical

pair = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v2')
root = Path(read(pair / 'baseline-lineage.json')['active_root']).resolve()
assert root == (pair / 'baseline').resolve()
assert not (root / 'running.lock').exists()
assert read(root / 'completed.json')['assignments'] == 21
queue = REPO.parent / 'tools/compute_queue/compute_queue.py'
status = json.loads(subprocess.check_output([sys.executable, '-X', 'utf8', '-B', str(queue),
    'status', '20261008T141622993171Z-1784089b'], text=True, encoding='utf-8'))
assert status['state'] == 'succeeded' and type(status['exit_status']) is int and status['exit_status'] == 0
out = pair / 'operator/endpoint-audit-session34-001'
out.mkdir(parents=True, exist_ok=False)
save(out / 'official-queue-status.json', status)
frozen = pair / 'frozen_repository'
argv = [sys.executable, '-X', 'utf8', '-B', str(queue), 'submit', '--project', 'LLMs-in-Robotics', '--cwd', str(frozen), '--',
    sys.executable, '-X', 'utf8', '-B', str(CODE / 'operations/session-33/audit_terminal.py'), '--root', str(root),
    '--code', str(frozen / 'Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'),
    '--queue-status', str(out / 'official-queue-status.json'), '--output', str(out / 'output'), '--expect', 'completed']
save(out / 'submission-intent.json', dict(created_utc=datetime.now(timezone.utc).isoformat(), argv=argv, automatic_retry=False))
response = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8')
save(out / 'submission-response.json', dict(exit_status=response.returncode, stdout=response.stdout, stderr=response.stderr))
assert response.returncode == 0, 'Audit submission uncertain; inspect queue and retained response before any next step'
submitted = json.loads(response.stdout)
save(out / 'queue-submission.json', submitted)
save(Path(__file__).with_name('endpoint-audit-queue.json'), submitted)
print(canonical(dict(job=submitted['id'], state=submitted['state'], evidence=str(out))).decode())
