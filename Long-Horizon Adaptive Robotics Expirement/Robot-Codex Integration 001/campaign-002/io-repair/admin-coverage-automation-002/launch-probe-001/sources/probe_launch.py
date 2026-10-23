"""Live no-model, no-capture venv identity and retirement probe."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

from owned_process import OwnedProcess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
FIXTURE = HERE.parent / 'smoke027-os-trace-readiness-001/coverage_fixture.py'


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def probe(out, case):
    out.mkdir()
    fixture_out = out / 'fixture'
    child = None
    receipt = {'case': case, 'capture_started': False, 'model_calls': 0,
               'fixture_sha256': hashlib.sha256(FIXTURE.read_bytes()).hexdigest()}
    try:
        child = OwnedProcess([sys.executable, '-X', 'utf8', '-B', str(FIXTURE),
                              '--output', str(fixture_out)], ROOT, out/'stdout.txt', out/'stderr.txt')
        deadline = time.monotonic() + 8
        while True:
            if child.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError('Fixture failed to become ready')
            try:
                ready = json.loads((fixture_out/'ready.json').read_text(encoding='utf-8'))
                break
            except (FileNotFoundError, json.JSONDecodeError):
                time.sleep(.025)
        receipt['observed_ready'] = ready
        receipt['identity'] = child.validate_ready(ready, [sys.executable, sys._base_executable], fixture_out)
        save(out/'identity.json', receipt['identity'])
        if case == 'release':
            save(fixture_out/'release.json', {'release': True})
            receipt['exit_code'] = child.wait(8)
            receipt['fixture_result'] = json.loads((fixture_out/'result.json').read_text(encoding='utf-8'))
            assert receipt['exit_code'] == 0 and receipt['fixture_result']['passed'] is True
        elif case == 'interruption':
            raise KeyboardInterrupt('Declared local interruption before release')
        elif case == 'foreign_pid':
            import os
            wrong = dict(ready, pid=os.getpid())
            try:
                child.validate_ready(wrong, [sys.executable, sys._base_executable], fixture_out)
            except RuntimeError as exc:
                receipt['foreign_identity_rejected'] = str(exc)
            else:
                raise AssertionError('Foreign PID accepted')
        elif case == 'malformed_port':
            try:
                child.validate_ready(dict(ready, port=True), [sys.executable, sys._base_executable], fixture_out)
            except RuntimeError as exc:
                receipt['malformed_identity_rejected'] = str(exc)
            else:
                raise AssertionError('Boolean port accepted')
        else:
            raise ValueError(case)
        receipt['passed'] = True
    except KeyboardInterrupt as exc:
        receipt['interruption'] = str(exc)
        receipt['passed'] = case == 'interruption'
    except BaseException as exc:
        receipt['passed'] = False
        receipt['error'] = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        if child:
            try:
                receipt['retirement'] = child.retire()
            except BaseException as exc:
                receipt['passed'] = False
                receipt['retirement_error'] = str(exc)
            finally:
                child.close()
        save(out/'receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir()
    results = [probe(args.output / case, case) for case in ('release', 'interruption', 'foreign_pid', 'malformed_port')]
    summary = {'passed': all(x['passed'] for x in results), 'cases': results,
               'sources': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__), HERE/'owned_process.py', FIXTURE)}}
    save(args.output/'receipt.json', summary)
    print(json.dumps({'passed': summary['passed'], 'cases': [
        {k:v for k,v in x.items() if k in ('case','passed','error','retirement','retirement_error','identity')} for x in results]}, indent=2))
    sys.exit(0 if summary['passed'] else 1)
