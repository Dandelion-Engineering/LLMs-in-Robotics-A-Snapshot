"""Queue-only serial synthetic qualification regressions; no physical execution.

Usage: run_qualification_checks.py --output <fresh qualification-tests-001 folder>
Each suite uses a separately owned Windows job and a 120-second cap. Exact raw
stdout/stderr and actual unittest counts are retained, including failed suites.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
import uuid

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
QUALIFICATION = HERE/'qualification-tools'
RUNTIME = PROJECT/'Runtime 004'
ORIGINAL_FIXTURES = PROJECT/'Batch 01/Restart Qualification Tools'
SUITES = (
    ('versioned_bindings', QUALIFICATION, 'test_versioned_bindings.py', 4),
    ('profile_screen', QUALIFICATION/'Recovery Profile Qualification', 'test_profile_screen.py', 12),
    ('materializer', QUALIFICATION/'Recovery Profile Assembly Tools', 'test_materialize_profile_rule.py', 5),
)
FIXTURE_FILES = ('test_calibration_loader.py', 'calibration_loader.py', 'test_qualification.py',
                 'test_compatibility.py', 'qualification.py', 'compatibility.py', 'descriptor.py')
sys.path.insert(0, str(QUALIFICATION/'Calibration Tools'))
sys.path.insert(0, str(QUALIFICATION/'Recovery Qualification'))
from calibration_authority import parent_authority, child_authority, child_command
from process_caps import JobCap, join_job


def utc():
    return datetime.now(timezone.utc).isoformat()


def ref(path):
    path = Path(path).resolve()
    with path.open('rb') as stream:
        checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'path': str(path), 'sha256': checksum, 'bytes': path.stat().st_size}


def inventory():
    # Everything in the versioned tool tree, not just imported modules; binary
    # robot assets are not exercised by these synthetic suites. Runtime source
    # files and the old immutable synthetic fixture closure are separately bound.
    paths = {p.resolve() for p in QUALIFICATION.rglob('*') if p.is_file()
             and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    paths.update(p.resolve() for p in RUNTIME.glob('*.py'))
    paths.update((ORIGINAL_FIXTURES/name).resolve() for name in FIXTURE_FILES)
    paths.add(Path(__file__).resolve())
    if not (RUNTIME/'restart_calibration_loader.py').is_file():
        raise ValueError('Complete Runtime 004 required before regressions')
    return {str(path): ref(path) for path in sorted(paths)}


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def child(args):
    raw = Path(args.parent_manifest).read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.parent_manifest_sha256:
        raise ValueError('Exact parent manifest hash differs')
    manifest = json.loads(raw)
    join_job(manifest['probe_job_names'][args._child])
    child_authority(__file__, args._child, args.output, args.seed,
                    args.parent_manifest, args.parent_manifest_sha256)
    if inventory() != manifest['source_files_before']:
        raise ValueError('Regression sources changed before suite discovery')
    identity, directory, pattern, expected = next(row for row in SUITES if row[0] == args._child)
    output = Path(args.output).resolve(); output.mkdir(parents=True, exist_ok=False)
    loader = unittest.TestLoader()
    suite = loader.discover(str(directory), pattern=pattern)
    started = utc(); begin = time.monotonic()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    record = {'suite_id': identity, 'discovery_directory': str(directory), 'pattern': pattern,
        'started_at': started, 'completed_at': utc(), 'elapsed_wall_s': time.monotonic()-begin,
        'expected_test_count': expected, 'actual_test_count': result.testsRun,
        'failures': [{'test': str(test), 'traceback': trace} for test, trace in result.failures],
        'errors': [{'test': str(test), 'traceback': trace} for test, trace in result.errors],
        'skipped': [{'test': str(test), 'reason': reason} for test, reason in result.skipped],
        'expected_failures': [{'test': str(test), 'traceback': trace} for test, trace in result.expectedFailures],
        'unexpected_successes': [str(test) for test in result.unexpectedSuccesses],
        'loader_errors': list(loader.errors), 'unittest_successful': result.wasSuccessful()}
    record['passed'] = (result.wasSuccessful() and result.testsRun == expected
        and not result.skipped and not result.expectedFailures and not loader.errors)
    write(output/'result.json', record)
    return 0 if record['passed'] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--_child', choices=[row[0] for row in SUITES], help=argparse.SUPPRESS)
    parser.add_argument('--seed', type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument('--parent-manifest', help=argparse.SUPPRESS)
    parser.add_argument('--parent-manifest-sha256', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args._child:
        if args.seed != 0 or not args.parent_manifest or not args.parent_manifest_sha256:
            parser.error('Child requires exact parent authority and dispatch token')
        return child(args)
    authority = parent_authority(__file__)
    output = Path(args.output).resolve()
    for protected in (QUALIFICATION, RUNTIME, ORIGINAL_FIXTURES):
        protected = protected.resolve()
        if output == protected or protected in output.parents or output in protected.parents:
            raise ValueError('Output must not overlap a checked source directory')
    before = inventory(); started = utc()
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'schema_version': 'runtime004-qualification-regression-inputs-1',
        'queue': authority, 'modes': [row[0] for row in SUITES], 'seed': 0,
        'source_files_before': before,
        'probe_job_names': {row[0]: 'Local\\CodexRoboticsQualificationTests_'+uuid.uuid4().hex for row in SUITES}}
    manifest_path = output/'manifest.json'; write(manifest_path, manifest)
    rows = []
    for identity, directory, pattern, expected in SUITES:
        command = child_command(sys.executable, Path(__file__).resolve(), identity,
                                output/identity, 0, manifest_path, ref(manifest_path)['sha256'])
        row = {'id': identity, 'expected_test_count': expected, 'actual_test_count': None,
               'argv': command, 'exit_status': None, 'passed': False, 'error': None,
               'result_ref': None, 'result': None}
        stdout_path, stderr_path = output/(identity+'-stdout.log'), output/(identity+'-stderr.log')
        begin = time.monotonic(); cap = JobCap(manifest['probe_job_names'][identity]); process = None
        print('Running deferred synthetic suite: '+identity, flush=True)
        try:
            with stdout_path.open('xb') as stdout, stderr_path.open('xb') as stderr:
                process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                try:
                    row['exit_status'] = process.wait(timeout=120)
                except subprocess.TimeoutExpired:
                    cap.terminate()
                    if process.poll() is None: process.kill()
                    row['exit_status'] = process.wait(timeout=10)
                    row['error'] = 'Owned synthetic suite exceeded 120 seconds; partial logs retained'
        except OSError as error:
            row['error'] = type(error).__name__+': '+str(error)
        finally:
            cap.close()
        row['elapsed_wall_s'] = time.monotonic()-begin
        for label, path in (('stdout', stdout_path), ('stderr', stderr_path)):
            row[label] = path.read_bytes().decode('utf-8', errors='replace') if path.exists() else None
            row[label+'_ref'] = ref(path) if path.exists() else None
        result_path = output/identity/'result.json'
        if result_path.is_file():
            row['result_ref'] = ref(result_path); result = json.loads(result_path.read_bytes())
            row['result'] = result; row['actual_test_count'] = result['actual_test_count']
            row['passed'] = (row['error'] is None and row['exit_status'] == 0 and result['passed'] is True
                and result['suite_id'] == identity and result['expected_test_count'] == expected
                and result['actual_test_count'] == expected)
        rows.append(row)
        print(json.dumps({'suite': identity, 'passed': row['passed'], 'actual_test_count': row['actual_test_count']}), flush=True)
    after_error = None
    try:
        after = inventory()
    except OSError as error:
        after = None; after_error = type(error).__name__+': '+str(error)
    stable = before == after
    passed = stable and len(rows) == len(SUITES) and all(row['passed'] for row in rows)
    actual = [row['actual_test_count'] for row in rows]
    report = {'schema_version': 'runtime004-qualification-regression-1', 'status': 'passed' if passed else 'failed',
        'all_required_checks_passed': passed, 'queue_job_id': authority['job_id'], 'queue': authority,
        'started_at': started, 'completed_at': utc(), 'source_files_before': before, 'source_files_after': after,
        'sources_unchanged': stable, 'source_inventory_error': after_error, 'manifest_ref': ref(manifest_path),
        'suites': rows, 'total_expected_tests': sum(row[3] for row in SUITES),
        'total_actual_tests': sum(actual) if all(type(value) is int for value in actual) else None,
        'official_completion_receipt_verified': False, 'physics_executed': False, 'qualification_granted': False,
        'scope': 'Synthetic/source regression evidence only. The official completion receipt is retained externally after natural exit.'}
    write(output/'validation.json', report)
    print(json.dumps({'validation_ref': ref(output/'validation.json'), 'status': report['status'],
                      'total_actual_tests': report['total_actual_tests']}), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
