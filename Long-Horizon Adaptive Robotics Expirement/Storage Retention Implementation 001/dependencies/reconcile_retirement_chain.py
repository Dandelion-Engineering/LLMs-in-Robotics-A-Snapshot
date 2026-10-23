"""Read-only exact-path reconciliation across interrupted and continued retirement.

The original interrupted job is failure context. A separately successful
interruption proof authenticates the observed absent prefix. A separately
successful continuation authenticates only its new unlinks. No camera or
scientific source file is opened by this final receipt-chain check.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from reconcile_retirement_receipts import (
    BATCH_SIZE, GATES, IMP, POLICY, ROOT, argument, lexical_identity, positive_integer,
    read, repo_path, require, sha, source, timestamp,
)


def receipt_names(directory, batches, outstanding=False):
    expected = {f'{i:05d}-{suffix}.json' for i in range(batches) for suffix in ('intent', 'complete')}
    if outstanding:
        expected.add(f'{batches:05d}-intent.json')
    entries = list(Path(directory).iterdir())
    require(all(p.is_file() for p in entries), 'Unexpected non-file in receipt directory')
    actual = {p.name for p in entries}
    require(actual == expected, 'Missing/extra/failure receipts: ' + json.dumps(
        {'directory': str(directory), 'missing': sorted(expected-actual), 'extra': sorted(actual-expected)}))
    return expected


def batch_receipt(directory, index, rows, first, manifest_sha, *, intent_only=False):
    expected = {'manifest_sha256': manifest_sha, 'first_ordinal': first,
                'count': len(rows), 'logical_bytes': sum(row['logical_bytes'] for row in rows)}
    require(0 < len(rows) <= BATCH_SIZE, 'Invalid batch length')
    encoded = ('\n'.join(row['path'] for row in rows) + '\n').encode('utf-8')
    paths_sha = hashlib.sha256(encoded).hexdigest()
    sources, values = [], {}
    for suffix in (('intent',) if intent_only else ('intent', 'complete')):
        leaf = Path(directory) / f'{index:05d}-{suffix}.json'
        raw = leaf.read_bytes()
        value = json.loads(raw)
        keys = set(expected) | ({'created'} if suffix == 'intent' else {'finished', 'removed_paths_sha256'})
        require(set(value) == keys, 'Unexpected receipt schema: ' + str(leaf))
        for key, wanted in expected.items():
            if key != 'manifest_sha256':
                positive_integer(value[key], leaf.name + ' ' + key)
            require(value[key] == wanted, 'Receipt field differs: ' + str(leaf) + ' ' + key)
        sources.append({'name': leaf.name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
        values[suffix] = value
    created = timestamp(values['intent']['created'])
    result = {'batch': index, **expected, 'ordered_paths_sha256': paths_sha, 'receipt_sources': sources,
              'created': values['intent']['created']}
    if not intent_only:
        require(values['complete']['removed_paths_sha256'] == paths_sha, 'Exact removed-path SHA differs: ' + str(directory) + ' batch ' + str(index))
        require(created <= timestamp(values['complete']['finished']), 'Complete precedes intent')
        result['finished'] = values['complete']['finished']
    return result


def receipt_set_digest(sources):
    h = hashlib.sha256()
    for record in sources:
        h.update((record['name'] + '\t' + record['sha256'] + '\n').encode('utf-8'))
    return h.hexdigest()


def reconcile_chain_stream(manifest, reference, proof, original_dir, continuation_dir):
    """Stream original ordinals once; verify both receipt generations exactly."""
    manifest_source = source(manifest)
    require(manifest_source['sha256'] == reference['sha256'], 'Original deletion manifest digest differs')
    prefix = proof['completed_prefix']
    interrupted = proof['interrupted_intent_absences']
    remaining = proof['remaining']
    first = proof['first_remaining_ordinal']
    positive_integer(prefix['files'], 'original prefix files')
    require(prefix['files'] % BATCH_SIZE == 0, 'Original completed prefix ends inside a batch')
    original_batches = prefix['files'] // BATCH_SIZE
    positive_integer(interrupted['files'], 'interrupted absences')
    require(interrupted['first_ordinal'] == prefix['files'], 'Interrupted absence range does not follow completed prefix')
    require(first == prefix['files'] + interrupted['files'], 'Continuation does not begin immediately after observed absence')
    require(first + remaining['files'] == reference['files'], 'Remaining count does not cover manifest suffix')
    require(prefix['logical_bytes'] + interrupted['logical_bytes'] + remaining['logical_bytes'] == reference['logical_bytes'], 'Proof bytes do not partition original manifest')
    old_names = receipt_names(original_dir, original_batches, outstanding=True)
    new_batches = (remaining['files'] + BATCH_SIZE - 1) // BATCH_SIZE
    new_names = receipt_names(continuation_dir, new_batches)
    outstanding_value = read(Path(original_dir) / f'{original_batches:05d}-intent.json')
    intent_count = outstanding_value['count']
    require(type(intent_count) is int and 0 < intent_count <= BATCH_SIZE, 'Invalid outstanding original intent length')
    require(interrupted['files'] <= intent_count, 'Observed interrupted absences extend outside issued intent')
    require(prefix['files'] + intent_count <= reference['files'], 'Outstanding intent exceeds original manifest')
    original_checks, continuation_checks, outstanding_rows = [], [], []
    prefix_rows, continuation_rows = [], []
    seen = defaultdict(set)
    hashes = {name: hashlib.sha256() for name in ('whole', 'prefix', 'interrupted', 'continuation')}
    counts = {name: {'files': 0, 'logical_bytes': 0} for name in ('whole', 'prefix', 'interrupted', 'continuation')}
    with gzip.open(manifest, 'rt', encoding='utf-8') as f:
        for ordinal, line in enumerate(f):
            require(bool(line.strip()), 'Blank deletion-manifest line')
            row = json.loads(line)
            run_id, identity = lexical_identity(row)
            require(identity not in seen[run_id], 'Duplicate manifest frame identity')
            seen[run_id].add(identity)
            group = 'prefix' if ordinal < prefix['files'] else 'interrupted' if ordinal < first else 'continuation'
            encoded = (row['path'] + '\n').encode('utf-8')
            for name in ('whole', group):
                hashes[name].update(encoded)
                counts[name]['files'] += 1
                counts[name]['logical_bytes'] += row['logical_bytes']
            if prefix['files'] <= ordinal < prefix['files'] + intent_count:
                outstanding_rows.append(row)
            if group == 'prefix':
                prefix_rows.append(row)
                if len(prefix_rows) == BATCH_SIZE:
                    index = len(original_checks)
                    original_checks.append(batch_receipt(original_dir, index, prefix_rows, index * BATCH_SIZE, reference['sha256']))
                    prefix_rows = []
            elif group == 'continuation':
                continuation_rows.append(row)
                if len(continuation_rows) == BATCH_SIZE:
                    index = len(continuation_checks)
                    continuation_checks.append(batch_receipt(continuation_dir, index, continuation_rows, first + index * BATCH_SIZE, reference['sha256']))
                    continuation_rows = []
    require(not prefix_rows, 'Incomplete original completed-prefix batch')
    if continuation_rows:
        index = len(continuation_checks)
        continuation_checks.append(batch_receipt(continuation_dir, index, continuation_rows, first + index * BATCH_SIZE, reference['sha256']))
    outstanding_check = batch_receipt(original_dir, original_batches, outstanding_rows, prefix['files'], reference['sha256'], intent_only=True)
    require(len(original_checks) == original_batches and len(continuation_checks) == new_batches, 'Receipt batch coverage differs')
    for name, wanted in (('whole', reference), ('prefix', prefix), ('interrupted', interrupted), ('continuation', remaining)):
        require(all(counts[name][key] == wanted[key] for key in ('files', 'logical_bytes')), name + ' counts/bytes differ')
        if name != 'whole':
            require(hashes[name].hexdigest() == wanted['ordered_paths_sha256'], name + ' exact ordered-path digest differs from successful interruption proof')
    old_sources = [record for batch in original_checks for record in batch['receipt_sources']] + outstanding_check['receipt_sources']
    new_sources = [record for batch in continuation_checks for record in batch['receipt_sources']]
    require(receipt_set_digest(old_sources) == proof['original_receipt_set_sha256'], 'Original receipts differ from authenticated interruption proof')
    if 'receipt_sources' in proof:
        require(old_sources == proof['receipt_sources'], 'Original per-file receipt identities differ from interruption proof')
    previous = None
    for batch in original_checks + [outstanding_check]:
        require(previous is None or previous <= timestamp(batch['created']), 'Original batch chronology differs')
        previous = timestamp(batch.get('finished', batch['created']))
    previous = None
    for batch in continuation_checks:
        require(previous is None or previous <= timestamp(batch['created']), 'Continuation batch chronology differs')
        previous = timestamp(batch['finished'])
    require(sha(manifest) == manifest_source['sha256'], 'Manifest changed during final chain reconciliation')
    for directory, records, names in ((original_dir, old_sources, old_names), (continuation_dir, new_sources, new_names)):
        require({p.name for p in Path(directory).iterdir()} == names, 'Receipt directory changed during reconciliation')
        for record in records:
            require(sha(Path(directory) / record['name']) == record['sha256'], 'Receipt changed during reconciliation')
    return {'status': 'passed', 'manifest': manifest_source,
            'files': counts['whole']['files'], 'logical_bytes': counts['whole']['logical_bytes'],
            'ordered_manifest_paths_sha256': hashes['whole'].hexdigest(),
            'original_completed_prefix': {**counts['prefix'], 'ordered_paths_sha256': hashes['prefix'].hexdigest(), 'batches': original_batches},
            'observed_absent_within_interrupted_intent': {**counts['interrupted'], 'ordered_paths_sha256': hashes['interrupted'].hexdigest(), 'first_ordinal': prefix['files']},
            'continuation': {**counts['continuation'], 'ordered_paths_sha256': hashes['continuation'].hexdigest(), 'first_ordinal': first, 'batches': new_batches},
            'original_receipt_set_sha256': receipt_set_digest(old_sources), 'continuation_receipt_set_sha256': receipt_set_digest(new_sources),
            'original_receipt_count': len(old_sources), 'continuation_receipt_count': len(new_sources),
            'original_completed_batches': original_checks, 'original_outstanding_intent': outstanding_check,
            'continuation_completed_batches': continuation_checks,
            'scope': 'Disjoint exact coverage of the original deletion manifest by completed original receipts, independently observed interrupted-intent absences, and completed new continuation receipts. No original incomplete receipt is replaced or relabeled successful; no camera-file access is performed by this check.'}


def official(path, state='succeeded'):
    saved = read(path)
    queue = ROOT.parent / 'tools/compute_queue/compute_queue.py'
    live = json.loads(subprocess.check_output([sys.executable, '-X', 'utf8', '-B', str(queue), 'status', saved['id']]))
    require(saved == live and saved['state'] == state, 'Saved receipt differs from official terminal state')
    if state == 'succeeded':
        require(saved['exit_status'] == 0, 'Source job did not succeed with exit 0')
    require(Path(saved['cwd']).resolve() == ROOT, 'Source job working directory differs')
    return saved


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--continuation-receipt', type=Path, required=True)
    p.add_argument('--partition', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    sys.path.insert(0, str(IMP.parent / 'Runtime Recovery 001'))
    import recovery_runner
    own_job = recovery_runner.queued_job(expected_script=__file__)
    job = official(a.continuation_receipt)
    argv = job['argv']
    require(argv.count('execute') == 1 and repo_path(argv[argv.index('execute')-1]) == IMP / 'records/resume_retirement.py', 'Unexpected continuation program/command')
    proof_path = repo_path(argument(argv, '--reconciliation'))
    proof_receipt_path = repo_path(argument(argv, '--reconciliation-receipt'))
    gate_path = repo_path(argument(argv, '--gate'))
    proof, gate, partition = read(proof_path), read(gate_path), read(a.partition)
    proof_job = official(proof_receipt_path)
    require(any(repo_path(v) == IMP / 'dependencies/reconcile_retirement_receipts.py' for v in proof_job['argv'] if v.endswith('.py')), 'Unexpected interruption-proof program')
    require(repo_path(argument(proof_job['argv'], '--output')) == proof_path, 'Interruption proof output argument differs')
    require(repo_path(argument(proof_job['argv'], '--partition')) == a.partition.resolve(), 'Interruption proof partition argument differs')
    old_receipt_path = repo_path(argument(proof_job['argv'], '--interrupted-receipt'))
    old_job = official(old_receipt_path, 'interrupted')
    old_argv = old_job['argv']
    require(old_argv.count('delete') == 1 and repo_path(old_argv[old_argv.index('delete')-1]) == IMP / 'retention.py', 'Unexpected interrupted original program/command')
    require(proof['status'] == 'passed' and proof['queue_job_id'] == proof_job['id'] and proof['original_retirement_job_id'] == old_job['id'], 'Interruption proof job identities differ')
    require(proof['all_retained_hashes_verified'] is True and proof['protected_nonframe_metadata_checked'] == 3323, 'Interruption proof is incomplete')
    require(proof['partition_sha256'] == sha(a.partition) and gate['partition_sha256'] == sha(a.partition), 'Proof/gate partition digest differs')
    reference = partition['manifests']['deletion']
    require(proof['deletion_manifest_sha256'] == reference['sha256'] and gate['deletion_manifest_sha256'] == reference['sha256'], 'Proof/gate deletion digest differs')
    require(gate['status'] == 'passed' and gate['first_remaining_ordinal'] == proof['first_remaining_ordinal'] and gate['reconciliation_queue_job_id'] == proof_job['id'], 'Continuation gate identity differs')
    require(set(gate['checks']) == GATES and all(v is True for v in gate['checks'].values()), 'Continuation gate checks differ')
    for identity in gate['evidence_refs']:
        path = repo_path(identity['path'])
        require(path.is_relative_to(IMP) and sha(path) == identity['sha256'], 'Continuation gate evidence changed')
    manifest = repo_path(reference['path'])
    name = a.partition.name.removesuffix('-partition.json')
    require(argument(old_argv, '--name') == name, 'Original retirement partition name differs')
    require(a.partition.resolve() == IMP / 'records' / (name + '-partition.json'), 'Unexpected partition location')
    completion_path = IMP / 'records' / (name + '-deletion-complete.json')
    completion = read(completion_path)
    require(completion['status'] == 'completed' and completion['policy'] == POLICY, 'Final completion status/policy differs')
    require(completion['manifest_sha256'] == reference['sha256'], 'Final completion manifest differs')
    require(all(completion[k] == reference[k] for k in ('files', 'logical_bytes')), 'Final completion totals differ')
    require(completion['interrupted_original_job_id'] == old_job['id'] and completion['reconciliation_job_id'] == proof_job['id'] and completion['successful_continuation_job_id'] == job['id'], 'Final completion chain job identities differ')
    require(completion['original_completed_prefix'] == proof['completed_prefix'] and completion['observed_absent_within_interrupted_intent'] == proof['interrupted_intent_absences'], 'Final completion prior ranges differ from interruption proof')
    for key, path in (('interruption_reconciliation', proof_path), ('continuation_gate', gate_path)):
        require(repo_path(completion[key]['path']) == path and sha(path) == completion[key]['sha256'], 'Final completion source differs: ' + key)
    continuation = completion['continuation']
    require(continuation['first_ordinal'] == proof['first_remaining_ordinal'] and all(continuation[k] == proof['remaining'][k] for k in ('files', 'logical_bytes')), 'Final continuation range/counts differ')
    original_dir = IMP / 'records' / (name + '-deletion-receipts')
    continuation_dir = repo_path(continuation['receipt_directory'])
    require(continuation_dir == IMP / 'records' / (name + '-continuation-001-receipts'), 'Unexpected continuation receipt directory')
    require(timestamp(old_job['ended_at']) <= timestamp(proof_job['started_at']) <= timestamp(proof_job['ended_at']) <= timestamp(job['started_at']) <= timestamp(continuation['started']) <= timestamp(completion['finished']) <= timestamp(job['ended_at']), 'Official interruption/proof/continuation chronology differs')
    baseline_ref = completion['disk_baseline_source']
    baseline_path = repo_path(baseline_ref['path'])
    require(baseline_ref['field'] == 'disk_before' and sha(baseline_path) == baseline_ref['sha256'], 'Disk baseline identity differs')
    require(read(baseline_path)['disk_before'] == completion['disk_before'], 'Final disk baseline is not the authenticated preflight observation')
    require(completion['disk_after'] == continuation['disk_after'], 'Final and continuation disk endpoints differ')
    for value in (completion, continuation):
        require(value['observed_free_space_increase_bytes'] == value['disk_after']['free']-value['disk_before']['free'], 'Free-space delta arithmetic differs')
    sources = {key: source(path) for key, path in {
        'continuation_official_receipt': a.continuation_receipt, 'proof': proof_path, 'proof_official_receipt': proof_receipt_path,
        'interrupted_original_official_receipt': old_receipt_path, 'gate': gate_path, 'partition': a.partition,
        'completion': completion_path, 'disk_baseline': baseline_path, 'reconciler': Path(__file__),
        'shared_reconciler_helpers': IMP / 'dependencies/reconcile_retirement_receipts.py'}.items()}
    result = reconcile_chain_stream(manifest, reference, proof, original_dir, continuation_dir)
    for batch in result['original_completed_batches'] + [result['original_outstanding_intent']]:
        require(timestamp(old_job['started_at']) <= timestamp(batch['created']) <= timestamp(batch.get('finished', batch['created'])) <= timestamp(old_job['ended_at']), 'Original receipt outside original execution')
    for batch in result['continuation_completed_batches']:
        require(timestamp(continuation['started']) <= timestamp(batch['created']) <= timestamp(batch['finished']) <= timestamp(completion['finished']), 'Continuation receipt outside continuation execution')
    for identity in sources.values():
        require(sha(identity['path']) == identity['sha256'], 'Authenticated chain input changed during reconciliation')
    result.update({'format': 'retirement-receipt-chain-reconciliation-1', 'queue_job_id': own_job['id'],
                   'created_at': datetime.now(timezone.utc).isoformat(), 'sources': sources,
                   'original_retirement_job_id': old_job['id'], 'interruption_proof_job_id': proof_job['id'],
                   'successful_continuation_job_id': job['id'], 'all_manifest_ordinals_accounted_exactly_once': True,
                   'disk_observation_scope': completion['disk_observation_scope']})
    with a.output.open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    print(json.dumps({k: result[k] for k in ('status', 'files', 'logical_bytes', 'original_completed_prefix', 'observed_absent_within_interrupted_intent', 'continuation')}))


if __name__ == '__main__':
    main()
