"""Bounded dual-host regression launcher; never runs the coordinator or queue."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
HOSTS = (
    Path(r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'),
    Path(r'C:\Users\cresp\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe'),
)
FILES = ('run_release_series.ps1', 'test_run_release_series.ps1', 'run_regressions.py',
         'README.md', 'provenance.json', 'fixtures/original-official-receipt.json',
         'fixtures/official-queue-status.json', 'fixtures/finalized.json')


def inventory():
    result = {}
    for name in FILES:
        path = HERE / name
        raw = path.read_bytes()
        result[name] = {'path': str(path), 'bytes': len(raw),
                        'sha256': hashlib.sha256(raw).hexdigest()}
    return result


def main():
    before = inventory()
    results = []
    for host in HOSTS:
        modules = host.parent / 'Modules'
        # Build a child-only environment. Do not change user/machine settings or
        # reuse a pwsh-first module path in a Windows PowerShell process.
        env = {key: value for key, value in os.environ.items()
               if key.casefold() != 'psmodulepath'}
        env['PSModulePath'] = str(modules)
        command = [str(host), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                   '-File', str(HERE / 'test_run_release_series.ps1')]
        start = time.monotonic()
        row = {'host': str(host), 'module_path': str(modules), 'argv': command,
               'exit_status': None, 'stdout': '', 'stderr': '', 'error': None}
        try:
            completed = subprocess.run(command, cwd=HERE.parents[3], env=env,
                capture_output=True, text=True, errors='replace', timeout=180,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            row.update(exit_status=completed.returncode, stdout=completed.stdout,
                       stderr=completed.stderr)
            row['passed'] = (completed.returncode == 0
                and 'Passed 14 bounded coordinator checks on PowerShell ' in completed.stdout)
        except (OSError, subprocess.TimeoutExpired) as error:
            row.update(passed=False, error=type(error).__name__ + ': ' + str(error))
        row['elapsed_wall_s'] = time.monotonic() - start
        results.append(row)
        print(json.dumps({'host_result': row}, sort_keys=True), flush=True)
        # Never short-circuit: the second host's actual result is also required.
    after = inventory()
    passed = before == after and len(results) == 2 and all(row['passed'] for row in results)
    print(json.dumps({'schema_version': 'coordinator-regression-run-1',
        'passed': passed, 'source_files_before': before, 'source_files_after': after,
        'sources_unchanged': before == after, 'host_results': results,
        'coordinator_executed': False, 'queue_called': False}, sort_keys=True), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
