"""Queued integrated Runtime 004 and reader/coordinator regressions."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
EXP = HERE.parent.parent
PROJECT = EXP.parent
RUNTIME = EXP / 'Runtime 004'
sys.path.insert(0, str(RUNTIME))
import release_runner


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    files = list((EXP / 'Runtime').glob('*.py')) + list(RUNTIME.glob('*.py'))
    for folder in (EXP / 'Engineering Investigation 004', HERE.parent / 'Release Analysis 004', HERE / 'coordinator'):
        files.extend(p for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    files.extend([Path(__file__), HERE / 'change-inventory.json', HERE / 'runtime-integration-001.json'])
    return {str(path.resolve()): sha(path) for path in sorted(set(files))}


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def main():
    job = release_runner.queued_job(Path(__file__))
    output = HERE / 'integrated-validation-001'
    output.mkdir(exist_ok=False)
    before = sources()
    integration = json.loads((HERE / 'runtime-integration-001.json').read_text())
    assert {p.name: sha(p) for p in RUNTIME.glob('*.py')} == integration['new_runtime_sources']
    assert {p.name: sha(p) for p in (EXP / 'Runtime').glob('*.py')} == integration['original_before']
    env = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
    groups = [
        ('runtime', [sys.executable, '-X', 'utf8', '-B', '-m', 'unittest', 'discover', '-s', str(RUNTIME), '-p', 'test_*.py', '-v'], 439),
        ('investigation', [sys.executable, '-X', 'utf8', '-B', '-m', 'unittest', 'discover', '-s', str(EXP / 'Engineering Investigation 004'), '-p', 'test_*.py', '-v'], 147),
        ('analysis', [sys.executable, '-X', 'utf8', '-B', '-m', 'unittest', 'discover', '-s', str(HERE.parent / 'Release Analysis 004'), '-p', 'test_*.py', '-v'], 25),
        ('coordinator', [sys.executable, '-X', 'utf8', '-B', str(HERE / 'coordinator/run_regressions.py')], None),
    ]
    results = []
    for name, argv, minimum in groups:
        out, err = output / (name + '.stdout.log'), output / (name + '.stderr.log')
        started = time.monotonic()
        with out.open('xb') as stdout, err.open('xb') as stderr:
            completed = subprocess.run(argv, cwd=PROJECT, env=env, stdout=stdout, stderr=stderr,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        text = err.read_text(encoding='utf-8', errors='replace')
        matches = re.findall(r'^Ran (\d+) tests? in ', text, re.M)
        count = int(matches[-1]) if matches else None
        coordinator = None
        if name == 'coordinator':
            rows = [json.loads(line) for line in out.read_text(encoding='utf-8').splitlines() if line.startswith('{')]
            coordinator = rows[-1] if rows else None
        passed = completed.returncode == 0
        if minimum is not None:
            passed = passed and count is not None and count >= minimum and bool(re.search(r'^OK(?: \(.*\))?$', text, re.M))
        else:
            passed = passed and coordinator is not None and coordinator.get('passed') is True and coordinator.get('sources_unchanged') is True
        result = {'name': name, 'argv': argv, 'cwd': str(PROJECT), 'exit_status': completed.returncode,
                  'test_count': count, 'passed': passed, 'elapsed_wall_s': time.monotonic() - started,
                  'stdout': {'path': str(out), 'sha256': sha(out)}, 'stderr': {'path': str(err), 'sha256': sha(err)},
                  'coordinator_summary': coordinator}
        results.append(result)
        print(json.dumps({'group': name, 'passed': passed, 'test_count': count, 'exit_status': completed.returncode}), flush=True)
    after = sources()
    passed = before == after and all(row['passed'] for row in results)
    report = {'schema_version': 'runtime004-integrated-validation-1', 'queue_job_id': job['id'],
              'completed_at_utc': datetime.now(timezone.utc).isoformat(),
              'all_required_checks_passed': passed, 'sources_unchanged': before == after,
              'inputs_before': before, 'inputs_after': after, 'checks': results,
              'runtime_root': str(RUNTIME), 'runtime_sources': integration['new_runtime_sources'],
              'integration': {'path': str(HERE / 'runtime-integration-001.json'), 'sha256': sha(HERE / 'runtime-integration-001.json')},
              'scope': 'Integrated regression evidence; no physical trial, model inference, qualification or readiness claim.'}
    save(output / 'validation.json', report)
    print(json.dumps({'report': str(output / 'validation.json'), 'sha256': sha(output / 'validation.json'), 'passed': passed}), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
