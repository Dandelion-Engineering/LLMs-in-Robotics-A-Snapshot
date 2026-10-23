"""Run the two bounded unit suites once while retaining the complete source state."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

IO = Path(__file__).resolve().parent
C = IO.parent
REPO = C.parent.parents[1]
RECORDS = IO / 'checks-031-execution-001'
CHECKS = IO / 'checks-031'
STATE = IO / 'checks-031-source-state.json'


def identity(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')


def sources():
    files = set(C.glob('*.py'))
    for name in ('harness', 'assessment', 'qualification', 'admission'):
        files.update((C / name).glob('*.py'))
    return [identity(path) for path in sorted(files)]


def main():
    if any(path.exists() for path in (RECORDS, CHECKS, STATE)):
        raise ValueError('Existing checks031 execution; reconcile without repeating it')
    RECORDS.mkdir()
    before = sources()
    argv = [sys.executable, '-X', 'utf8', '-B', str(IO / 'record_checks.py'),
            'run', '--directory', str(CHECKS)]
    save(RECORDS / 'intent.json', {
        'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'argv': argv, 'sources': before, 'helper': identity(IO / 'record_checks.py'),
        'launcher': identity(Path(__file__))})
    with (RECORDS / 'stdout.txt').open('x', encoding='utf-8') as out, \
            (RECORDS / 'stderr.txt').open('x', encoding='utf-8') as err:
        process = subprocess.run(argv, cwd=REPO, stdout=out, stderr=err,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    after = sources()
    tests_path = CHECKS / 'test-execution.json'
    tests = json.loads(tests_path.read_text(encoding='utf-8')) if tests_path.is_file() else {}
    passed = process.returncode == 0 and tests.get('passed') is True and before == after
    save(STATE, {'passed': passed, 'sources_unchanged': before == after,
        'tests': identity(tests_path) if tests_path.is_file() else None, 'sources': after,
        'scope': 'Complete direct Python source set in harness,assessment,qualification,admission and campaign top-level held unchanged around both full suites.'})
    save(RECORDS / 'receipt.json', {
        'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'exit_code': process.returncode, 'passed': passed,
        'intent': identity(RECORDS / 'intent.json'), 'source_state': identity(STATE),
        'stdout': identity(RECORDS / 'stdout.txt'), 'stderr': identity(RECORDS / 'stderr.txt'),
        'sources_after': after})
    print(json.dumps({'passed': passed, 'source_count': len(after),
        'source_state': identity(STATE), 'receipt': identity(RECORDS / 'receipt.json')}), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
