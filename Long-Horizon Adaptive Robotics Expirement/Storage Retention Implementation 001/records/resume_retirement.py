"""Explicit continuation of one authenticated, reconciled interrupted retirement.

Old receipts are immutable. This program records only its actual remaining
unlinks in a separate directory, with global original-manifest ordinals.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('retention', HERE / 'retention.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def authenticated_job(path, fragment, state='succeeded'):
    saved = r.read(path)
    queue = r.ROOT.parent / 'tools/compute_queue/compute_queue.py'
    live = json.loads(subprocess.check_output([sys.executable, '-X', 'utf8', '-B', str(queue), 'status', saved['id']]))
    if saved != live or saved['state'] != state or (state == 'succeeded' and saved['exit_status'] != 0):
        raise ValueError('Official queue receipt does not authenticate completed state')
    if Path(saved['cwd']).resolve() != r.ROOT or not any(fragment in item for item in saved['argv']):
        raise ValueError('Wrong source job')
    return saved


def inputs(args):
    part_path = HERE / 'records/r4-policy-001-partition.json'
    part = r.read(part_path)
    proof = r.read(args.reconciliation)
    receipt = authenticated_job(args.reconciliation_receipt, 'reconcile_retirement_receipts.py')
    if (proof['status'] != 'passed' or proof['queue_job_id'] != receipt['id'] or
            proof['partition_sha256'] != r.sha(part_path) or
            proof['deletion_manifest_sha256'] != part['manifests']['deletion']['sha256'] or
            proof['all_retained_hashes_verified'] is not True or
            proof['protected_nonframe_metadata_checked'] != 3323):
        raise ValueError('Incomplete interruption reconciliation')
    old_receipt = HERE / 'records/queue-20260927T021811180808Z-32339c6c-interrupted.json'
    old_job = authenticated_job(old_receipt, 'delete', state='interrupted')
    if proof['original_retirement_job_id'] != old_job['id']:
        raise ValueError('Wrong interrupted predecessor')
    a, b, c = proof['completed_prefix'], proof['interrupted_intent_absences'], proof['remaining']
    if a['files'] + b['files'] != proof['first_remaining_ordinal']:
        raise ValueError('Noncontiguous reconciled prefix')
    for key in ('files', 'logical_bytes'):
        if a[key] + b[key] + c[key] != part['manifests']['deletion'][key]:
            raise ValueError('Reconciled partition totals differ')
    original_gate_path = HERE / 'records/pre-deletion-completion-001.json'
    original_gate = r.read(original_gate_path)
    if (original_gate['status'] != 'passed' or original_gate['partition_sha256'] != r.sha(part_path) or
            original_gate['deletion_manifest_sha256'] != part['manifests']['deletion']['sha256'] or
            set(original_gate['checks']) != r.GATES or any(value is not True for value in original_gate['checks'].values())):
        raise ValueError('Original gate partition differs')
    for item in original_gate['evidence_refs']:
        path = (r.ROOT / item['path']).resolve()
        if not path.is_relative_to(HERE) or r.sha(path) != item['sha256']:
            raise ValueError('Original passed gate evidence changed')
    return part, proof, receipt, original_gate


def prepare(args):
    part, proof, receipt, original_gate = inputs(args)
    if (r.ROOT / '.codex-session.lock').read_text().strip() != '2026-09-26T17:44:17.7987520-07:00':
        raise ValueError('Session ownership changed')
    writer_check = r.read(args.writer_check)
    if writer_check['status'] != 'passed' or writer_check['affected_original_writers_observed'] != 0:
        raise ValueError('Affected writer check not passed')
    refs = []
    for path in [Path(__file__), HERE / 'retention.py', Path(args.reconciliation), Path(args.reconciliation_receipt), Path(args.writer_check),
                 HERE / 'records/pre-deletion-completion-001.json',
                 HERE / 'records/queue-20260927T021811180808Z-32339c6c-interrupted.json']:
        refs.append(dict(path=path.resolve().relative_to(r.ROOT).as_posix(), sha256=r.sha(path)))
    r.emit(Path(args.gate), dict(
        status='passed', created=r.now(), schema='retirement-continuation-gate-1',
        partition_sha256=r.sha(HERE / 'records/r4-policy-001-partition.json'),
        deletion_manifest_sha256=part['manifests']['deletion']['sha256'],
        first_remaining_ordinal=proof['first_remaining_ordinal'], checks=original_gate['checks'],
        reconciliation_queue_job_id=receipt['id'], evidence_refs=refs,
        authority='Continue only the still-present remainder of the already authorized exact manifest after successful independent reconciliation. No new paths or policy expansion.',
        failure_preservation='Original interrupted receipt and incomplete batch remain unchanged. Observed absence within the issued intent is recorded separately from completed original batches and new unlinks.',
        disk_observation=r.shutil.disk_usage(r.ROOT.anchor)._asdict()))
    print(json.dumps(dict(status='passed', first_remaining_ordinal=proof['first_remaining_ordinal'])))


def execute(args):
    if (r.ROOT / '.codex-session.lock').read_text().strip() != '2026-09-26T17:44:17.7987520-07:00':
        raise ValueError('Session ownership changed')
    part, proof, receipt, original_gate = inputs(args)
    gate = r.read(args.gate)
    if (gate['status'] != 'passed' or gate['first_remaining_ordinal'] != proof['first_remaining_ordinal'] or
            gate['partition_sha256'] != r.sha(HERE / 'records/r4-policy-001-partition.json') or
            gate['deletion_manifest_sha256'] != part['manifests']['deletion']['sha256'] or
            set(gate['checks']) != r.GATES or any(value is not True for value in gate['checks'].values())):
        raise ValueError('Continuation gate differs')
    for item in gate['evidence_refs']:
        path = (r.ROOT / item['path']).resolve()
        if not path.is_relative_to(HERE) or r.sha(path) != item['sha256']:
            raise ValueError('Continuation evidence changed')
    sys.path.insert(0, str(r.EXP / 'Runtime Recovery 001'))
    import recovery_runner
    own_job = recovery_runner.queued_job(expected_script=__file__)
    source_hash = r.sha(__file__)
    ref = part['manifests']['deletion']
    manifest = r.ROOT / ref['path']
    if r.sha(manifest) != ref['sha256']:
        raise ValueError('Deletion manifest changed')
    out = HERE / 'records/r4-policy-001-continuation-001-receipts'
    out.mkdir(exist_ok=False)
    start = r.now()
    before = shutil.disk_usage(r.ROOT.anchor)._asdict()
    n = logical_bytes = 0
    first = proof['first_remaining_ordinal']

    def commit_batch(batch):
        nonlocal n, logical_bytes
        r.checked_directory.cache_clear()
        index = n // 2000
        base = dict(manifest_sha256=ref['sha256'], first_ordinal=first+n,
                    count=len(batch), logical_bytes=sum(row['logical_bytes'] for row in batch))
        r.emit(out / f'{index:05d}-intent.json', dict(**base, created=r.now()))
        removed = []
        try:
            for row in batch:
                path = r.safe_frame(row['path'])
                st = path.stat()
                if (st.st_size, st.st_mtime_ns) != (row['logical_bytes'], row['mtime_ns']):
                    raise ValueError('Identity mismatch: ' + row['path'])
                path.unlink()
                removed.append(row['path'])
                n += 1
                logical_bytes += row['logical_bytes']
        except Exception:
            r.emit(out / f'{index:05d}-failure.json', dict(removed=removed, created=r.now()))
            raise
        r.emit(out / f'{index:05d}-complete.json', dict(**base, finished=r.now(),
               removed_paths_sha256=hashlib.sha256(('\n'.join(removed)+'\n').encode()).hexdigest()))
        if index % 25 == 0:
            print(json.dumps(dict(newly_removed_files=n, total_absent_files=first+n,
                                  newly_removed_logical_bytes=logical_bytes)), flush=True)

    batch = []
    for ordinal, row in enumerate(r.rows(manifest)):
        if ordinal < first:
            continue
        batch.append(row)
        if len(batch) == 2000:
            commit_batch(batch)
            batch = []
    if batch:
        commit_batch(batch)
    if (n, logical_bytes) != (proof['remaining']['files'], proof['remaining']['logical_bytes']):
        raise ValueError('Continuation totals differ')
    if r.sha(__file__) != source_hash:
        raise ValueError('Continuation source changed')
    after = shutil.disk_usage(r.ROOT.anchor)._asdict()
    # The interrupted worker had no final disk observation. Use a named,
    # authenticated earlier census baseline rather than inventing that value.
    baseline_path = HERE / 'records/preflight-001/summary.json'
    baseline = r.read(baseline_path)['disk_before']
    r.emit(HERE / 'records/r4-policy-001-deletion-complete.json', dict(
        status='completed', policy=r.POLICY, started=original_gate['created'], finished=r.now(),
        manifest_sha256=ref['sha256'], files=ref['files'], logical_bytes=ref['logical_bytes'],
        disk_before=baseline, disk_after=after,
        disk_baseline_source=dict(path=baseline_path.relative_to(r.ROOT).as_posix(), sha256=r.sha(baseline_path), field='disk_before'),
        disk_observation_scope='Preflight census to completion of the reconciled continuation, including intervening prototype/code writes and unrelated host activity; not the unavailable first worker start observation.',
        observed_free_space_increase_bytes=after['free']-baseline['free'],
        interrupted_original_job_id=proof['original_retirement_job_id'],
        reconciliation_job_id=receipt['id'], successful_continuation_job_id=own_job['id'],
        original_completed_prefix=proof['completed_prefix'],
        observed_absent_within_interrupted_intent=proof['interrupted_intent_absences'],
        continuation=dict(first_ordinal=first, files=n, logical_bytes=logical_bytes, started=start,
                          disk_before=before, disk_after=after,
                          observed_free_space_increase_bytes=after['free']-before['free'],
                          receipt_directory=out.relative_to(r.ROOT).as_posix()),
        interruption_reconciliation=dict(path=Path(args.reconciliation).resolve().relative_to(r.ROOT).as_posix(), sha256=r.sha(args.reconciliation)),
        continuation_gate=dict(path=Path(args.gate).resolve().relative_to(r.ROOT).as_posix(), sha256=r.sha(args.gate)),
        limitations='Exact logical bytes and path coverage are reconciled across distinct execution records. Interrupted-job outputs alone are not accepted as successful evidence. Volume free-space deltas include host activity and allocation/metadata effects.'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('command', choices=['prepare', 'execute'])
    ap.add_argument('--reconciliation', required=True)
    ap.add_argument('--reconciliation-receipt', required=True)
    ap.add_argument('--gate', required=True)
    ap.add_argument('--writer-check', required=True)
    args = ap.parse_args()
    globals()[args.command](args)


if __name__ == '__main__':
    main()
