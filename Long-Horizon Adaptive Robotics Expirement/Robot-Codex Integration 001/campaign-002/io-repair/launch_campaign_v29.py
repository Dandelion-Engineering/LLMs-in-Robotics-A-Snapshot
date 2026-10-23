"""Retain one sealed Campaign 002 launch after the complete V29 admission chain.

This operator wrapper is outside the frozen runtime inventory. It invokes the
existing operator/coordinator and never implements an experiment or retries a
slot. Existing launch intent requires explicit reconciliation, not another call.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

IO = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sealed_campaign_control_v29',
                                            IO / 'control_campaign_admission_v29.py')
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)
c = control.c


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('dry-run', 'launch'))
    parser.add_argument('--readiness-sha256', required=True)
    args = parser.parse_args()
    basis = control.admission_basis(args.readiness_sha256)
    for action in control.ACTIONS:
        control.recorded(action, basis)
    digest = c.read(control.SEAL)['certificate_sha256']
    cert = c.admission.verify_certificate(control.CERTIFICATE, digest)
    registration = control.RELEASE / 'registration.json'
    c.admission.verify_registration(registration, cert, digest)
    dry_argv = c.python(control.C / 'operate.py', 'start', '--run-id', 'RCI001-C02-stock-01',
                        '--registration', registration, '--dry-run')
    dry_inputs = [Path(__file__), registration, control.CERTIFICATE, control.SEAL, control.READINESS]
    if args.action == 'launch':
        c.require((control.RECORDS / 'first-slot-dry-run-intent.json').is_file()
                  and (control.RECORDS / 'first-slot-dry-run-receipt.json').is_file(),
                  'Retained successful first-slot dry run required before launch')
    dry = c.command_once(control.RECORDS, 'first-slot-dry-run', dry_argv, inputs=dry_inputs)
    c.require(json.loads(dry['stdout']).get('dry_run') is True, 'Dry run did not confirm admission')
    if args.action == 'dry-run':
        print(json.dumps({'dry_run': True, 'receipt': c.identity(control.RECORDS / 'first-slot-dry-run-receipt.json')}))
        return 0
    records = IO / 'campaign-execution-v29-001'
    c.require(not records.exists() and not (control.C / 'execution').exists(),
              'Existing execution or outer launch record; reconcile without restart')
    coordinator = control.C / 'run_campaign.py'
    argv = c.python(coordinator, '--registration', registration)
    intent = records / 'launch-intent.json'
    output = records / 'output.jsonl'
    receipt = records / 'launch-receipt.json'
    c.save(intent, {'argv': argv, 'cwd': str(c.REPO), 'registration': c.identity(registration),
        'certificate': c.identity(control.CERTIFICATE), 'seal': c.identity(control.SEAL),
        'readiness': c.identity(control.READINESS), 'coordinator': c.identity(coordinator),
        'launcher': c.identity(Path(__file__)),
        'scope': 'Execute the sealed twenty-slot campaign with its existing no-replacement and stopping rules.'})
    with output.open('x', encoding='utf-8') as stream:
        process = subprocess.Popen(argv, cwd=c.REPO, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding='utf-8',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        for line in process.stdout:
            stream.write(line)
            stream.flush()
            print(line, end='', flush=True)
        result = process.wait()
    c.save(receipt, {'intent_sha256': c.sha(intent), 'exit_code': result,
                     'output': c.identity(output)})
    print(json.dumps({'launch_receipt': c.identity(receipt), 'exit_code': result}), flush=True)
    return result


if __name__ == '__main__':
    sys.exit(main())
