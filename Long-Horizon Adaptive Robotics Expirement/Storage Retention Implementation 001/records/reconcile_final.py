"""Reconcile authenticated post-retirement records without changing old evidence."""
from pathlib import Path
import argparse
import importlib.util
import json

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('retention', HERE / 'retention.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--census-receipt', type=Path, required=True)
    ap.add_argument('--analysis-receipt', type=Path, required=True)
    ap.add_argument('--retirement-receipt', type=Path, required=True)
    ap.add_argument('--postcheck-receipt', type=Path, required=True)
    ap.add_argument('--reader-receipt', type=Path, required=True)
    ap.add_argument('--batch-receipt', type=Path, required=True)
    ap.add_argument('--batch-report', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    refs = []

    def get(path):
        path = Path(path)
        refs.append(dict(path=path.relative_to(r.ROOT).as_posix(), sha256=r.sha(path)))
        return r.read(path)

    official = {}
    for label, path, required_fragment in [('census', args.census_receipt, 'postflight-001'),
                                     ('analysis', args.analysis_receipt, 'analysis-post-001'),
                                     ('retirement', args.retirement_receipt, 'resume_retirement.py'),
                                     ('postcheck', args.postcheck_receipt, 'post-001'),
                                     ('readers', args.reader_receipt, 'post-policy-001'),
                                     ('batches', args.batch_receipt, 'reconcile_retirement_chain.py')]:
        q = get(path.resolve())
        assert q['state'] == 'succeeded' and q['exit_status'] == 0
        assert any(required_fragment in item for item in q['argv'])
        assert Path(q['cwd']).resolve() == r.ROOT
        official[label] = q
    pre = get(HERE / 'records/preflight-001/summary.json')
    post = get(HERE / 'records/postflight-001/summary.json')
    part = get(HERE / 'records/r4-policy-001-partition.json')
    done = get(HERE / 'records/r4-policy-001-deletion-complete.json')
    validation = get(HERE / 'records/r4-policy-001-post-001-validation.json')
    readers = get(HERE / 'records/post-policy-001/validation.json')
    batches = get(args.batch_report.resolve())
    assert validation['status'] == readers['status'] == 'passed'
    assert readers['queue_job_id'] == official['readers']['id']
    assert batches['status'] == 'passed' and batches['queue_job_id'] == official['batches']['id']
    assert batches['successful_continuation_job_id'] == official['retirement']['id']
    assert batches['all_manifest_ordinals_accounted_exactly_once'] is True
    assert '--after' in official['postcheck']['argv']
    assert len(readers['actual_reader_traces']) == 12
    assert not pre['errors'] and not post['errors'] and not post['skipped']
    removed = part['manifests']['deletion']
    retained = part['manifests']['retained']
    assert done['status'] == 'completed'
    assert done['manifest_sha256'] == removed['sha256']
    assert (done['files'], done['logical_bytes']) == (removed['files'], removed['logical_bytes'])
    assert (batches['files'], batches['logical_bytes']) == (removed['files'], removed['logical_bytes'])
    assert validation['partition_sha256'] == r.sha(HERE / 'records/r4-policy-001-partition.json')
    assert post['counts']['r4_frames'] == [retained['files'], retained['logical_bytes']]
    for index, key in enumerate(['files', 'logical_bytes']):
        assert post['counts']['r4'][index] == pre['counts']['r4'][index] - removed[key]
    evidence_key = r.EXP.relative_to(r.ROOT).as_posix() + '/Evidence'
    assert post['counts'][evidence_key][1] == pre['counts'][evidence_key][1] - removed['logical_bytes']
    assert post['counts'][evidence_key][0] == pre['counts'][evidence_key][0] - removed['files']
    original = r.EXP / 'Evidence/derived/evaluation-r4-analysis005-001/analysis.json'
    before = HERE / 'records/analysis-pre-001/analysis.json'
    after = HERE / 'records/analysis-post-001/analysis.json'
    assert original.read_bytes() == before.read_bytes() == after.read_bytes()
    for path in [original, before, after]:
        refs.append(dict(path=path.relative_to(r.ROOT).as_posix(), sha256=r.sha(path)))
    baseline = get(HERE / 'records/source-baseline.json')
    for item in baseline['audit_sources']:
        p = r.ROOT / item['path']
        assert p.stat().st_size == item['bytes'] and r.sha(p) == item['sha256']
    prefix = r.EXP.relative_to(r.ROOT).as_posix() + '/'
    whole_exp = sum(value[1] for key, value in post['counts'].items() if key.startswith(prefix))
    evidence = post['counts'][evidence_key][1]
    audit = get(r.EXP / 'Storage Audit 2026-09-26/measurement/summary.json')
    result = dict(
        schema='storage-final-reconciliation-1', status='passed', created=r.now(),
        original_audit_project_logical_bytes=audit['logical_bytes'],
        original_audit_c_free_bytes=audit['volumes']['C:/']['free'],
        preflight_project_logical_bytes=pre['counts']['.'][1],
        preflight_c_free_bytes=pre['disk_before']['free'],
        retained=retained, retired=removed,
        retired_logical_bytes_exact=removed['logical_bytes'],
        observed_preflight_to_retirement_completion_c_free_increase_bytes=done['observed_free_space_increase_bytes'],
        free_space_measurement_interval=done.get('disk_observation_scope', 'retirement command start to completion'),
        post_project_logical_bytes=post['counts']['.'][1],
        post_evidence_subtree_bytes=evidence,
        post_whole_experiment_logical_bytes=whole_exp,
        evidence_subtree_excess_over_150GB_bytes=max(0, evidence-150000000000),
        conservative_whole_experiment_excess_over_150GB_bytes=max(0, whole_exp-150000000000),
        post_c_free_bytes=post['disk_after']['free'],
        project_nonretirement_growth_between_snapshots_bytes=(post['counts']['.'][1]-pre['counts']['.'][1]+removed['logical_bytes']),
        r4_nonframe_counts_and_bytes_unchanged=True,
        entire_evidence_subtree_change_equals_exact_retirement=True,
        aggregate_original_pre_post_exact_bytes_equal=True,
        aggregate_sha256=r.sha(after), preserved_audit_sources_verified=len(baseline['audit_sources']),
        current_reader_traces_verified=12, records=refs,
        original_completed_batches_reconciled=batches['original_completed_prefix']['batches'],
        interrupted_intent_absences_reconciled=batches['observed_absent_within_interrupted_intent']['files'],
        continuation_batches_reconciled=batches['continuation']['batches'],
        ordered_removed_paths_sha256=batches['ordered_manifest_paths_sha256'],
        official_queue_jobs={key:value['id'] for key,value in official.items()},
        limitations=[
            'Census is a timed logical-pathname snapshot, not a volume allocation census.',
            'Postflight precedes final handoff metadata and Git closeout; final Git objects add repository bytes after this snapshot.',
            'Observed volume free-space changes include unrelated host writes and filesystem allocation/metadata effects.',
            'Whole experiment admission scope conservatively includes runtime/model hardlinks, code and all presentation/prototype artifacts.',
            'Known repeated runtime model hardlink bytes from the audit are 25535928636; no new full physical deduplication census is claimed.',
            'Arbitrary original pixel/depth reassessment outside retained selection is intentionally unavailable by policy.'
        ])
    r.emit(args.output, result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('records','limitations','retained','retired')},indent=2))


if __name__ == '__main__':
    main()
