"""Queued actual sandbox checks on a fresh development-storage scratch root."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import tempfile
import unittest

RUNTIME = Path(__file__).resolve().parents[2] / 'Runtime'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scratch-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(RUNTIME))
    import release_runner
    job = release_runner.queued_job(expected_script=__file__)
    scratch, output = args.scratch_root.resolve(), args.output.resolve()
    if scratch.exists() or output.exists() or scratch == output:
        raise ValueError('Both directories must be distinct and fresh')
    if not scratch.parent.is_dir() or not output.parent.is_dir():
        raise ValueError('Explicit storage parents must already exist')
    sources = [Path(__file__), *(RUNTIME / name for name in ('sandbox.py', 'candidate_worker.py', 'test_sandbox.py'))]
    def hashes():
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    before = hashes()
    scratch.mkdir(); output.mkdir()
    # Existing tests delete only TemporaryDirectory children allocated under this
    # resolved, fresh scratch directory; no previous evidence is moved or erased.
    old_tempdir = tempfile.tempdir
    tempfile.tempdir = str(scratch)
    tests = ['test_sandbox.SandboxTests.' + name for name in (
        'test_actual_filesystem_network_process_and_environment_boundary',
        'test_persistence_and_ephemeral_channels_across_real_restarts')]
    try:
        suite = unittest.defaultTestLoader.loadTestsFromNames(tests)
        with (output / 'checks.log').open('w', encoding='utf-8') as stream:
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    finally:
        tempfile.tempdir = old_tempdir
    after = hashes()
    report = {'scope': 'Actual candidate mount and persistence checks on the declared storage drive; no robot task or disk throughput claim',
              'queue_job_id': job['id'], 'scratch_root': str(scratch), 'tests': tests,
              'tests_run': result.testsRun, 'passed': result.wasSuccessful(),
              'errors': len(result.errors), 'failures': len(result.failures),
              'source_hashes_before': before, 'source_hashes_after': after,
              'sources_unchanged': before == after}
    (output / 'summary.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))
    return 0 if result.wasSuccessful() and before == after else 1


if __name__ == '__main__':
    raise SystemExit(main())
