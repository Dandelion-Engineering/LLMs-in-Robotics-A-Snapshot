"""Retain bounded development checks; no native process or model invocation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

IO = Path(__file__).resolve().parent
H = IO.parent / 'harness'
REPO = IO.parents[3]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=False)
    sources = [Path(__file__), IO / 'NATIVE_CLEANUP_CANCELLATION_V1.md'] + [H / name for name in (
        'native_cleanup_protocol.py', 'native_quiescence.py', 'runtime.py', 'codehost_entry_v3.py',
        'bootstrap_client_v4.py', 'test_native_cleanup_protocol.py', 'test_client_quiescence.py',
        'test_native_owner_bootstrap.py', 'test_codehost_entry_v3.py')]
    bindings = {p.relative_to(REPO).as_posix(): {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                                            'bytes': p.stat().st_size} for p in sources}
    checks = []
    for module in ('test_native_cleanup_protocol', 'test_client_quiescence',
                   'test_native_owner_bootstrap', 'test_codehost_entry_v3'):
        command = [sys.executable, '-X', 'utf8', '-B', '-m', 'unittest', module, '-v']
        started = time.time()
        completed = subprocess.run(command, cwd=H, capture_output=True, timeout=60)
        for label in ('stdout', 'stderr'):
            (args.directory / (module + '.' + label + '.txt')).write_bytes(getattr(completed, label))
        checks.append({'module': module, 'argv': command, 'cwd': str(H), 'started_unix_s': started,
                       'ended_unix_s': time.time(), 'exit_code': completed.returncode})
    unchanged = all({'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}
                    == bindings[p.relative_to(REPO).as_posix()] for p in sources)
    value = {'schema': 'campaign002-cleanup-controller-checks-1', 'scope': 'Development only; no native/model launch',
             'source_bindings': bindings, 'checks': checks, 'sources_unchanged': unchanged,
             'passed': unchanged and all(c['exit_code'] == 0 for c in checks)}
    (args.directory / 'receipt.json').write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'passed': value['passed'], 'directory': str(args.directory),
                      'exit_codes': [c['exit_code'] for c in checks]}))
    return 0 if value['passed'] else 1


if __name__ == '__main__': raise SystemExit(main())
