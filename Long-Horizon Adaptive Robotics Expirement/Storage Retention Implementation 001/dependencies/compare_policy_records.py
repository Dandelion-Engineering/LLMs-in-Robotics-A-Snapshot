"""Compare officially completed staged/post reader semantics and provenance.

This reads compact implementation records and their referenced implementation
manifests. It does not re-read scientific streams or inspect camera files.
"""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

from reconcile_retirement_receipts import IMP, ROOT, argument, read, repo_path, require, sha, source, timestamp


def authenticate_record(record_path, receipt_path, phase):
    record = read(record_path)
    saved = read(receipt_path)
    require(saved['state'] == 'succeeded' and saved['exit_status'] == 0, phase + ' job has not officially succeeded')
    queue = ROOT.parent / 'tools/compute_queue/compute_queue.py'
    live = json.loads(subprocess.check_output([sys.executable, '-X', 'utf8', '-B', str(queue), 'status', saved['id']]))
    require(saved == live, phase + ' receipt differs from official queue status')
    require(record['status'] == 'passed' and record['phase'] == phase and record['queue_job_id'] == saved['id'], phase + ' validation status/identity mismatch')
    argv = saved['argv']
    script = str(IMP / 'dependencies/validate_policy.py')
    require(any(repo_path(value) == Path(script) for value in argv if value.endswith('.py')), phase + ' program mismatch')
    require(Path(saved['cwd']).resolve() == ROOT, phase + ' job working directory mismatch')
    require(repo_path(argument(argv, '--output')) / 'validation.json' == record_path.resolve(), phase + ' output argument mismatch')
    require(argument(argv, '--phase') == phase and argument(argv, '--actual-reader') == 'all', phase + ' did not request all readers')
    required = repo_path(argument(argv, '--required'))
    require(source(required) == record['required_manifest'], phase + ' required manifest differs from actual input')
    windows = repo_path(argument(argv, '--windows'))
    checked_windows = record['diagnostic_window_completeness']
    require(source(windows) == checked_windows['windows'], phase + ' windows differ from actual input')
    require(checked_windows['required'] == record['required_manifest'], phase + ' windows checked a different retained input')
    require(timestamp(saved['started_at']) <= timestamp(record['started_at']) <= timestamp(record['ended_at']) <= timestamp(saved['ended_at']), phase + ' validation chronology differs from official execution')
    require(record['unexpected_policy_denials'] == [], phase + ' consumer requested a disallowed frame')
    guard = record['guard_self_test']
    expected_probe = 'existing candidate' if phase == 'staged' else 'absent synthetic path'
    require(guard['state'] == 'passed' and guard['denials'] == 3 and guard['probe_kind'] == expected_probe, phase + ' guard self-test differs')
    traces = record['actual_reader_traces']
    require(len(traces) == 12 and [t['ordinal'] for t in traces] == list(range(12)), phase + ' fixed twelve trace identities incomplete')
    require(len({t['run_id'] for t in traces}) == 12, phase + ' duplicated trace identity')
    for trace in traces:
        require(trace['state'] == 'passed' and trace['exact_historical_package_equal'] is True and
                trace['verification']['state'] == 'verified' and trace['verification']['full_metadata_roundtrip_equal'] is True,
                phase + ' historical package comparison failed')
    require(len(record['all12_trace_manifests']) == 12 and len(record['all12_and_saved_validation_dependencies']) == 13,
            phase + ' current/saved manifest dependency coverage differs')
    require(record['explorer']['state'] == 'passed', phase + ' Explorer failed')
    bound = record['source_bound_derivatives']
    require(bound['state'] == 'verified' and bound['planned_dispositions'] == 264 and bound['analysis_unchanged'] is True,
            phase + ' derivative/analysis verification differs')
    require(checked_windows['status'] == 'passed' and checked_windows['window_count'] == 899 and len(checked_windows['window_checks']) == 899,
            phase + ' diagnostic-window verification differs')
    return record, saved


def comparable(record):
    value = copy.deepcopy(record)
    # Only execution identity/time, the deliberately different retained-input
    # file, and the deliberately different guard probe are excluded. Every
    # other field (including complete semantic and source records) must match.
    for field in ('phase', 'queue_job_id', 'started_at', 'ended_at', 'required_manifest', 'guard_self_test'):
        value.pop(field)
    value['diagnostic_window_completeness'].pop('required')
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--staged', type=Path, required=True)
    p.add_argument('--staged-receipt', type=Path, required=True)
    p.add_argument('--post', type=Path, required=True)
    p.add_argument('--post-receipt', type=Path, required=True)
    p.add_argument('--partition', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    sources = {key: source(getattr(a, key)) for key in ('staged', 'staged_receipt', 'post', 'post_receipt', 'partition')}
    sources['comparator'] = source(__file__)
    sources['shared_authentication_helper'] = source(IMP / 'dependencies/reconcile_retirement_receipts.py')
    staged, staged_receipt = authenticate_record(a.staged, a.staged_receipt, 'staged')
    post, post_receipt = authenticate_record(a.post, a.post_receipt, 'post')
    partition = read(a.partition)
    final = partition['manifests']['retained']
    require(staged['required_manifest']['sha256'] == partition['required_input_sha256'], 'Staged input differs from authenticated partition requirement')
    require(repo_path(post['required_manifest']['path']) == repo_path(final['path']) and post['required_manifest']['sha256'] == final['sha256'],
            'Post reader did not use the final retained manifest')
    normalized_staged, normalized_post = comparable(staged), comparable(post)
    differences = sorted(k for k in set(normalized_staged) | set(normalized_post) if normalized_staged.get(k) != normalized_post.get(k))
    require(not differences, 'Staged/post semantic or provenance fields differ: ' + ', '.join(differences))
    for identity in sources.values():
        require(sha(identity['path']) == identity['sha256'], 'Input changed during comparison')
    report = {'format': 'staged-post-policy-comparison-1', 'status': 'passed',
              'created_at': datetime.now(timezone.utc).isoformat(), 'sources': sources,
              'staged_job': staged_receipt['id'], 'post_job': post_receipt['id'],
              'exactly_equal_fields': sorted(normalized_staged), 'actual_reader_traces': len(post['actual_reader_traces']),
              'diagnostic_windows': post['diagnostic_window_completeness']['window_count'],
              'source_bound_dispositions': post['source_bound_derivatives']['planned_dispositions'],
              'current_package': post['current_package'], 'explorer': post['explorer'],
              'required_inputs': {'staged': staged['required_manifest'], 'post': post['required_manifest']},
              'guard_self_tests': {'staged': staged['guard_self_test'], 'post': post['guard_self_test']},
              'scope': 'All reader semantic and provenance fields compare exactly. Only authenticated phase/job/time, required-manifest file identity and phase-specific guard probe differ. No scientific reinterpretation or original camera-file access occurs here.'}
    with a.output.open('x', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    print(json.dumps({k: report[k] for k in ('status', 'actual_reader_traces', 'diagnostic_windows', 'source_bound_dispositions')}))


if __name__ == '__main__':
    main()
