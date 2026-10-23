"""Bounded failed-queue infrastructure diagnosis; no qualification verdict."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
C = HERE.parents[1]
REPO = HERE.parents[4]
JOB = '20260930T194104177341Z-36f033a5'

def identity(path):
    p = Path(path).resolve(); raw = p.read_bytes()
    return {'path': str(p), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}

def save(name, value):
    with (HERE/name).open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2); f.write('\n')

def main():
    queue = REPO.parent/'tools/compute_queue/compute_queue.py'
    proc = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(queue), 'status', JOB],
                          cwd=REPO, capture_output=True, text=True, encoding='utf-8', check=True)
    status = json.loads(proc.stdout)
    assert status['id'] == JOB and status['state'] == 'failed'
    assert type(status['exit_status']) is int and status['exit_status'] == 1
    submitted = json.loads((C/'qualification/boundary-031-submit.json').read_text(encoding='utf-8'))
    assert status['argv'] == submitted['argv'] and status['cwd'] == str(REPO)
    save('official-status.json', status)
    ledger = C/'qualification/final-qualification-031/boundary-031'
    refs = []
    for name in ['prepare-receipt.json', 'register-receipt.json']:
        receipt = json.loads((ledger/name).read_text(encoding='utf-8'))
        assert type(receipt['exit_code']) is int and receipt['exit_code'] == 0
        for entry in receipt['outputs']:
            bound = identity(entry['path']); assert bound['sha256'] == entry['sha256']; refs.append(bound)
    save('authentication.json', {'checked_at': datetime.now(timezone.utc).isoformat(),
        'status': identity(HERE/'official-status.json'), 'sources': refs,
        'scope': 'Failed queue: bounded infrastructure diagnostics only; task outcome unknown.'})
    root = Path(status['argv'][-1]); path = root/'suite-result.json'
    result = json.loads(path.read_text(encoding='utf-8'))
    selected = {k: result.get(k) for k in ['model_calls', 'physical_simulation', 'qualified', 'checks',
                'error', 'cleanup_error', 'pre_close_export_error', 'post_close_export_error']}
    selected['input'] = identity(path)
    save('observations.json', selected)
    print(json.dumps(selected, indent=2))

if __name__ == '__main__': main()
