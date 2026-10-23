"""Authenticate the bounded no-model host diagnostic before reading outcomes."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
RCI = CAMPAIGN.parent
REPO = RCI.parents[1]
sys.path.insert(0, str(CAMPAIGN / 'assessment'))
import assess as base


def evaluate(manifest_path, output, queue_path, snapshot_path):
    job = base.read_json(queue_path)
    base.require(job.get('state') == 'succeeded' and type(job.get('exit_status')) is int
                 and job['exit_status'] == 0, 'Official succeeded/int0 required before outcome reads')
    expected = [str(REPO / 'venv/Scripts/python.exe'), '-X', 'utf8', '-B', str(HERE / 'host_probe.py'),
                'run', '--manifest', str(manifest_path.resolve()), '--output', str(output.resolve())]
    base.require(job.get('argv') == expected and Path(job['cwd']).resolve() == REPO.resolve()
                 and Path(job['resolved_executable']).resolve() == Path(expected[0]).resolve(),
                 'Wrong direct diagnostic queue command')
    frozen = base.read_json(snapshot_path)
    base.require(not base.source_integrity(frozen, snapshot_path.with_name('code.zip')),
                 'Frozen diagnostic source archive mismatch')
    base.require(all((REPO / name).is_file() and base.hash_file(REPO / name) == row['sha256']
                     for name, row in frozen['sources'].items()), 'Current diagnostic sources changed')
    manifest = base.read_json(manifest_path)
    base.require(base.hash_file(manifest_path) == frozen['manifest_sha256']
                 and manifest['framework_revision'] == frozen['revision']
                 and manifest['run_id'] == frozen['run_id'], 'Diagnostic manifest not frozen')
    execution = base.read_json(output / 'execution.json')
    host = output / 'host'
    result = base.read_json(host / 'result.json')
    stamp = lambda text: datetime.fromisoformat(text.replace('Z', '+00:00')).timestamp()
    checks = {
        'host_exit_zero': type(execution.get('exit_code')) is int and execution['exit_code'] == 0,
        'queue_encloses_host': stamp(job['started_at']) <= execution['started_unix_s'] <= execution['ended_unix_s'] <= stamp(job['ended_at']),
        'exact_manifest': base.read_json(host / 'manifest.json') == manifest and execution['manifest_sha256'] == frozen['manifest_sha256'],
        'no_model_or_reference_recovery': execution.get('model_calls') == 0 and result.get('robot_invocations') == 0 and result.get('reference_recovery') is False,
        'host_completed': result.get('execution_completed') is True and result.get('error') is None,
        'declared_interval_completed': result.get('terminal') == 'simulation_time_cap' and result.get('sim_elapsed_s', 0) >= manifest['sim_cap_s'],
        'free_reserve_preserved': min(execution['free_before'], execution['free_after']) >= 102_000_000_000,
    }
    timing, errors = None, {}
    try:
        timing = base.verify_timing(host, result, frozen)
        checks['strict_fresh_timing'] = timing['passed'] is True
    except Exception as error:
        errors['timing'] = str(error)
        checks['strict_fresh_timing'] = False
    return {'schema': 'campaign002-host-probe-assessment-1', 'run_id': manifest['run_id'],
            'framework_revision': frozen['revision'], 'queue_job_id': job['id'], 'checks': checks,
            'diagnostic_passed': all(value is True for value in checks.values()), 'errors': errors,
            'timing': timing, 'model_calls': 0, 'scorable': False, 'task_outcome': 'unknown',
            'bindings': {name: {'path': str(path.resolve()), 'sha256': base.hash_file(path)}
                         for name, path in {'manifest': manifest_path, 'queue': queue_path,
                                            'snapshot': snapshot_path, 'host_result': host / 'result.json'}.items()},
            'scope': 'Long-running apparatus diagnostic, no recovery score. A passing idle host does not establish model-loaded timing or full qualification.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'evidence', 'queue-receipt', 'snapshot', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    value = evaluate(args.manifest, args.evidence, args.queue_receipt, args.snapshot)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'run_id': value['run_id'], 'diagnostic_passed': value['diagnostic_passed'],
                      'failed_checks': [name for name, passed in value['checks'].items() if passed is not True]}))
