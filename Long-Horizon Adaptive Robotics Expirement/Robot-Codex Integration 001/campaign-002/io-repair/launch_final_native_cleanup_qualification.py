"""Retain the single V23 coordinator invocation and its streamed native output."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

IO = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('native_cleanup_prerequisite_control', IO / 'control_native_cleanup_qualification.py')
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)
c = control.c


def main():
    control.bound_declaration()
    readiness = control.Q / 'final-qualification-023-readiness.json'
    passed = c.read(IO / 'v23-readiness-preflight-001.json')
    c.require(passed.get('passed') is True and passed['readiness'] == c.identity(readiness),
              'Missing or changed prerequisite preflight')
    coordinator = control.Q / 'run_final_qualification_v23.py'
    c.require(passed['coordinator'] == c.identity(coordinator), 'Coordinator changed after preflight')
    argv = c.python(coordinator, '--readiness', readiness, '--readiness-sha256', c.sha(readiness))
    intent = c.LEDGER / 'coordinator-launch-intent.json'
    output = c.LEDGER / 'coordinator-output.jsonl'
    receipt = c.LEDGER / 'coordinator-launch-receipt.json'
    c.require(not c.LEDGER.exists(), 'Existing qualifier ledger; reconcile without restart')
    c.save(intent, {'argv': argv, 'cwd': str(c.REPO), 'readiness': c.identity(readiness),
        'coordinator': c.identity(coordinator), 'launcher': c.identity(Path(__file__)),
        'scope': 'Full five-stage fresh qualification only; no scored launch.'})
    with output.open('x', encoding='utf-8') as stream:
        process = subprocess.Popen(argv, cwd=c.REPO, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding='utf-8',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        for line in process.stdout:
            stream.write(line); stream.flush()
            print(line, end='', flush=True)
        result = process.wait()
    value = {'intent_sha256': c.sha(intent), 'exit_code': result,
             'output': c.identity(output)}
    c.save(receipt, value)
    print(json.dumps({'coordinator_receipt': c.identity(receipt), 'exit_code': result}), flush=True)
    return result


if __name__ == '__main__':
    sys.exit(main())
