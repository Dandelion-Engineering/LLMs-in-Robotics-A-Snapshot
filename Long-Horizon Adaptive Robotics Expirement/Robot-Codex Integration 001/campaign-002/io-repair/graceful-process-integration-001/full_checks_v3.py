"""One queued full harness/assessment check, preserving failures and source state."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
C = HERE.parents[1]
REPO = HERE.parents[4]
OUT = HERE/'full-checks-003'
QUEUE = Path('C:/Users/cresp/Documents/Dandelion Engineering/tools/compute_queue/compute_queue.py')

def identity(path):
    path = Path(path).resolve(); raw = path.read_bytes()
    return {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}

def save(path, value):
    with path.open('x', encoding='utf-8') as stream: json.dump(value, stream, indent=2); stream.write('\n')

def sources():
    paths = {p for d in ('harness', 'assessment', 'qualification', 'admission') for p in (C/d).glob('*.py')}
    paths.update(C.glob('*.py')); paths.add(C/'io-repair/GRACEFUL_PROCESS_DRAIN_V1.md')
    return [identity(p) for p in sorted(paths)]

def main():
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=('submit', 'run'))
    args = parser.parse_args()
    if args.action == 'submit':
        if OUT.exists() or (HERE/'full-check-intent-003.json').exists(): raise ValueError('Existing check footprint')
        command = [sys.executable, '-X', 'utf8', '-B', str(Path(__file__).resolve()), 'run']
        save(HERE/'full-check-intent-003.json', {'argv': command, 'sources': sources(), 'runner': identity(__file__),
            'scope': 'No-model unit and source-contract regression tests only'})
        job = json.loads(subprocess.check_output([sys.executable, '-X', 'utf8', '-B', str(QUEUE),
            'submit', '--project', 'LLMs-in-Robotics', '--cwd', str(REPO), '--', *command], text=True, encoding='utf-8'))
        save(HERE/'full-check-submit-003.json', job)
        print(json.dumps({'job_id': job['id'], 'state': job['state']})); return 0
    intent = json.loads((HERE/'full-check-intent-003.json').read_text(encoding='utf-8'))
    assert intent['runner'] == identity(__file__) and intent['sources'] == sources()
    command = [sys.executable, '-X', 'utf8', '-B', str(C/'io-repair/record_checks.py'), 'run', '--directory', str(OUT)]
    result = subprocess.run(command, cwd=REPO)
    execution = json.loads((OUT/'test-execution.json').read_text(encoding='utf-8'))
    unchanged = intent['sources'] == sources()
    passed = result.returncode == 0 and execution['passed'] is True and unchanged
    save(HERE/'full-check-source-state-003.json', {'passed': passed, 'sources_unchanged': unchanged,
        'sources': intent['sources'], 'tests': identity(OUT/'test-execution.json')})
    print(json.dumps({'passed': passed, 'source_count': len(intent['sources'])}))
    return 0 if passed else 1

if __name__ == '__main__': raise SystemExit(main())
