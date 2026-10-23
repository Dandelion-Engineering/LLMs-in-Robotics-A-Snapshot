"""Queue-owned six synthetic sealer checks; no sealing, physics, or seeds.

Usage: run_sealing_checks.py --output <fresh directory outside checked sources>
The actual successful official queue receipt is supplied separately afterward.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback
import unittest

HERE = Path(__file__).resolve().parent
EXP = HERE.parent.parent
RUNTIME = EXP / 'Runtime 004'
SEALING = HERE / 'sealing-tools'
ACCOUNTING = HERE / 'accounting-tools'
EXPECTED = 6


def utc():
    return datetime.now(timezone.utc).isoformat()


def ref(path):
    path = Path(path).resolve()
    payload = path.read_bytes()
    return {'path': str(path), 'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload)}


def inventory():
    paths = {Path(__file__).resolve()}
    paths.update(path.resolve() for path in RUNTIME.glob('*.py'))
    for directory in (SEALING, ACCOUNTING):
        paths.update(path.resolve() for path in directory.rglob('*') if path.is_file()
                     and '__pycache__' not in path.parts and path.suffix != '.pyc')
    for required in (RUNTIME / 'release_runner.py', SEALING / 'seal_r4.py',
                     SEALING / 'test_seal_r4.py', ACCOUNTING / 'snapshot_selection.py'):
        if required.resolve() not in paths:
            raise ValueError('Missing required checked source: ' + str(required))
    return {str(path): ref(path) for path in sorted(paths)}


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    # Ownership is checked before hashing checked sources, discovery or writes.
    sys.path.insert(0, str(RUNTIME))
    import release_runner
    job = release_runner.queued_job(Path(__file__))
    output = args.output.resolve()
    for directory in (SEALING, ACCOUNTING, RUNTIME):
        protected = directory.resolve()
        if output == protected or output.is_relative_to(protected) or protected.is_relative_to(output):
            raise ValueError('Output must not overlap checked source directories')
    if output.exists() or not output.parent.is_dir():
        raise ValueError('Fresh output with an existing parent required')
    if any(part.casefold() == 'candidate_state' for part in output.parts):
        raise ValueError('Candidate-private output refused')
    before = inventory(); started = utc(); begin = time.monotonic()
    output.mkdir(exist_ok=False)
    write(output / 'started.json', {'queue_job_id': job['id'], 'started_at': started,
                                    'expected_test_count': EXPECTED, 'source_files_before': before})
    stdout_path, stderr_path = output / 'stdout.log', output / 'stderr.log'
    loader = unittest.TestLoader(); result = None; execution_error = None
    with stdout_path.open('x', encoding='utf-8', newline='\n') as stdout, \
            stderr_path.open('x', encoding='utf-8', newline='\n') as stderr:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                suite = loader.discover(str(SEALING), pattern='test_seal_r4.py')
                result = unittest.TextTestRunner(stream=stderr, verbosity=2).run(suite)
            except BaseException as error:
                execution_error = type(error).__name__ + ': ' + str(error)
                traceback.print_exc(file=stderr)
    after = None; inventory_error = None
    try:
        after = inventory()
    except (OSError, ValueError) as error:
        inventory_error = type(error).__name__ + ': ' + str(error)
    actual = result.testsRun if result is not None else 0
    stable = before == after
    passed = (execution_error is None and stable and result is not None
              and actual == EXPECTED and result.wasSuccessful() and not loader.errors
              and not result.skipped and not result.expectedFailures)
    report = {
        'schema_version': 'runtime004-sealing-regression-1', 'status': 'passed' if passed else 'failed',
        'queue_job_id': job['id'], 'started_at': started, 'completed_at': utc(),
        'elapsed_wall_s': time.monotonic() - begin, 'all_required_checks_passed': passed,
        'source_files_before': before, 'source_files_after': after, 'sources_unchanged': stable,
        'expected_test_count': EXPECTED, 'actual_test_count': actual,
        'test_pattern': 'test_seal_r4.py', 'execution_error': execution_error,
        'source_inventory_error': inventory_error, 'loader_errors': list(loader.errors),
        'failures': [{'test': str(test), 'traceback': trace} for test, trace in (result.failures if result else [])],
        'errors': [{'test': str(test), 'traceback': trace} for test, trace in (result.errors if result else [])],
        'skipped': [{'test': str(test), 'reason': reason} for test, reason in (result.skipped if result else [])],
        'expected_failures': [{'test': str(test), 'traceback': trace} for test, trace in (result.expectedFailures if result else [])],
        'unexpected_successes': [str(test) for test in (result.unexpectedSuccesses if result else [])],
        'stdout_ref': ref(stdout_path), 'stderr_ref': ref(stderr_path),
        'official_completion_receipt_verified': False, 'sealer_executed': False,
        'accountant_executed': False, 'physics_executed': False, 'readiness_granted': False,
        'scope': 'Six synthetic index-relocation regressions only. Official completion receipt remains external.'}
    write(output / 'validation.json', report)
    print(json.dumps({'report': ref(output / 'validation.json'), 'passed': passed, 'actual_test_count': actual}))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
