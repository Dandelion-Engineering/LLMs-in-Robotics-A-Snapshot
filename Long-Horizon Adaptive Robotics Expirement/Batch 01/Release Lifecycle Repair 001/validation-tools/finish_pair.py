"""Queue-only canonical finish for exactly the retained A3-009/010 pair.

No trial or retry. Uses unchanged record_attempt.finish after the actual pair's
official receipt is verified. Partial canonical writes are retained on failure.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from types import SimpleNamespace

from run_lifecycle_pair import (DEFAULT_OUTPUT, DEFAULT_RAW, EXP, HERE, RUNTIME,
                                RUN_IDS, Inputs, official, ref, require, save)


def main(args):
    sys.path.insert(0, str(RUNTIME))
    import release_runner
    job = release_runner.queued_job(expected_script=Path(__file__).resolve())
    import record_attempt
    require(Path(record_attempt.__file__).resolve().parent == RUNTIME, 'Wrong Runtime imported')
    output = args.output.resolve()
    require(not output.exists() and output.parent.is_dir()
            and not any(output.is_relative_to(p) for p in (RUNTIME, record_attempt.MAP, DEFAULT_RAW)),
            'Fresh operator output outside Runtime/Map/raw evidence required')
    output.mkdir()
    inputs = Inputs()
    finished = []
    report = {'schema_version': 'lifecycle-pair-canonical-finish-1', 'queue_job_id': job['id'],
              'execution_queue_job_id': args.queue_job_id, 'run_ids': list(RUN_IDS),
              'status': 'incomplete', 'automatic_retries': 0, 'finished': finished}
    try:
        inputs.verify(ref(Path(__file__))); inputs.verify(ref(HERE / 'run_lifecycle_pair.py'))
        header = inputs.read(DEFAULT_OUTPUT / 'lifecycle-revalidation.json')
        completion = inputs.read(DEFAULT_OUTPUT / 'wrapper-completion.json')
        require(header['queue_job_id'] == completion['queue_job_id'] == args.queue_job_id,
                'Pair execution identity mismatch')
        official(release_runner, inputs, args.pair_receipt, args.queue_job_id, HERE / 'run_lifecycle_pair.py')
        require(completion['input_changes'] == [] and completion['not_started'] == []
                and [r['run_id'] for r in completion['attempts']] == list(RUN_IDS),
                'The exact complete pair with unchanged inputs is required')
        current = {p.name: ref(p)['sha256'] for p in RUNTIME.glob('*.py')}
        require(len(current) == 58 and current == header['runtime_sha256'], 'Final Runtime 004 source set differs')
        inputs.mapping({str(RUNTIME / name): sha for name, sha in header['runtime_sha256'].items()})
        inputs.verify(ref(record_attempt.MAP / 'map.py'))
        data, _, errors = record_attempt.am.read_store(record_attempt.MAP)
        require(not errors, 'Canonical records cannot be read: ' + repr(errors))
        require(not any(r.get('run_id') in RUN_IDS for r in data['result']),
                'Result already registered; preserve it and do not rerun this finisher')
        for rid in RUN_IDS:
            rows = [r for r in data['run'] if r['id'] == rid]
            require(len(rows) == 1 and rows[0]['stage'] == 'development', 'Missing exact development registration')
            inputs.read(record_attempt.MAP / 'releases' / rid / 'manifest.json')
            raw_result = inputs.read(DEFAULT_RAW / rid / 'result.json')
            inputs.read(DEFAULT_RAW / rid / 'manifest.json')
            require(raw_result['run_id'] == rid and raw_result['stage'] == 'development'
                    and raw_result['execution_status'] in ('completed', 'failed', 'timed_out', 'aborted'),
                    'Pair result is not a retained terminal development result')
            attempt = next(row for row in completion['attempts'] if row['run_id'] == rid)
            require(attempt['result_sha256'] == ref(DEFAULT_RAW / rid / 'result.json')['sha256'],
                    'Wrapper result bytes differ')
        save(output / 'started.json', {**report, 'started_at_utc': datetime.now(timezone.utc).isoformat(),
                                     'input_refs': list(inputs.refs.values())})
        for rid in RUN_IDS:
            require(not inputs.changes(), 'Inputs changed before canonical finish')
            record_attempt.finish(SimpleNamespace(run_id=rid, queue_job_id=args.queue_job_id))
            data, _, errors = record_attempt.am.read_store(record_attempt.MAP)
            require(not errors, 'Canonical records invalid after finish')
            rows = [r for r in data['result'] if r.get('run_id') == rid]
            require(len(rows) == 1 and rows[0]['details']['queue_job_id'] == args.queue_job_id,
                    'Finish did not create exactly one matching canonical result')
            path = output / (rid + '-canonical-result.json')
            save(path, rows[0])
            finished.append({'run_id': rid, 'canonical_result_id': rows[0]['id'], 'result': ref(path)})
            save(output / (rid + '-finished.json'), finished[-1])
        report['input_changes'] = inputs.changes()
        require(not report['input_changes'], 'Source/input bytes changed during canonical finish')
        report['status'] = 'complete'
        report['all_required_checks_passed'] = True
    except BaseException as error:
        report.update(status='failed_partial_preserved', all_required_checks_passed=False,
                      error_type=type(error).__name__, error=str(error))
        raise
    finally:
        report['completed_at_utc'] = datetime.now(timezone.utc).isoformat()
        report['input_refs'] = list(inputs.refs.values())
        report['source_files'] = [r for r in inputs.refs.values() if Path(r['path']).suffix == '.py']
        report['pair_receipt'] = ref(args.pair_receipt) if args.pair_receipt.is_file() else None
        report['scope'] = 'Canonical accounting only; preserves raw outcomes/validity and grants no readiness'
        save(output / 'finish.json', report)
    print(json.dumps({'report': str(output / 'finish.json'), 'finished': list(RUN_IDS)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queue-job-id', required=True, help='Actual completed pair execution queue ID')
    parser.add_argument('--pair-receipt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='Fresh metadata output directory')
    main(parser.parse_args())
