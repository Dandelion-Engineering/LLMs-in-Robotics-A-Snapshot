"""Persist one bounded external guard test/real-preflight qualification."""
import argparse
import contextlib
import io
from pathlib import Path
import unittest

import storage_guard as guard
import test_storage_guard


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--preflight', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Qualification record immutable; select a fresh output')
    capture = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_storage_guard)
    with contextlib.redirect_stdout(capture):
        result = unittest.TextTestRunner(stream=capture, verbosity=2).run(suite)
    preflight = guard.read_json(args.preflight)
    value = {'schema': 'campaign001-storage-qualification-1', 'created_utc': guard.utc(),
        'tests_passed': result.wasSuccessful(), 'tests_run': result.testsRun,
        'source_sha256': guard.digest(guard.__file__),
        'test_source_sha256': guard.digest(test_storage_guard.__file__),
        'qualification_source_sha256': guard.digest(__file__),
        'policy_sha256': preflight['config_sha256'],
        'preflight': {'path': str(args.preflight.resolve()), 'sha256': guard.digest(args.preflight)},
        'preflight_passed': preflight['preflight_passed'],
        'preflight_same_monitor_source': preflight['monitor_source_sha256'] == guard.digest(guard.__file__),
        'qualification_scope': 'Non-model external accounting, actual native/WSL scans, synthetic loopback safe-stop endpoint, mocked official queue interval boundaries. No simulator/model launched; no real capacity stop or scientific timing claim.',
        'test_output': capture.getvalue()}
    value['qualified'] = value['tests_passed'] and value['preflight_passed'] and value['preflight_same_monitor_source']
    guard.write_json(args.output, value)
    print(capture.getvalue())
    print('qualified=' + str(value['qualified']))
    return 0 if value['qualified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
