"""Read-only reconciliation of exact manifest paths and completed deletion receipts.

Only implementation manifests, receipts and source files are read. Original
evidence paths are parsed lexically and are never resolved, statted or opened.
This records what the authenticated receipts say; the separate filesystem
postcheck establishes the actual remaining/absent files.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
IMP = HERE.parent
ROOT = IMP.parent.parent
PREFIX = 'Long-Horizon Adaptive Robotics Expirement/Evidence/releases/batch01-eval-r4/attempts/'
POLICY = 'r4-selected-imagery-retention-001'
GATES = {'no_writers', 'audit_consistent', 'retained_dependencies', 'retained_hashes',
         'staged_investigation', 'explorer', 'aggregate', 'diagnostics_continuity',
         'windows_complete', 'reconciled_bytes'}
BATCH_SIZE = 2000
LEAF = re.compile(r'^(\d{6})(-depth\.npz|\.png)$')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def source(path):
    p = Path(path)
    return {'path': str(p.resolve()), 'bytes': p.stat().st_size, 'sha256': sha(p)}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def timestamp(value):
    t = datetime.fromisoformat(value)
    require(t.tzinfo is not None, 'Receipt timestamp lacks timezone')
    return t


def positive_integer(value, label, minimum=0):
    require(type(value) is int and value >= minimum, 'Invalid integer ' + label)


def lexical_identity(row):
    """Validate exact approved leaf syntax without accessing an evidence path."""
    path = row['path']
    require(isinstance(path, str) and path.startswith(PREFIX), 'Path outside r4 frame prefix')
    require('\\' not in path and '\n' not in path and '\r' not in path, 'Invalid path delimiter')
    parts = PurePosixPath(path[len(PREFIX):]).parts
    require(len(parts) == 4 and parts[1:3] == ('evidence', 'frames'), 'Not an exact frame leaf')
    require('/'.join(parts) == path[len(PREFIX):] and '..' not in parts, 'Noncanonical manifest path')
    match = LEAF.fullmatch(parts[-1])
    require(match is not None and row['run_id'] == parts[0], 'Run/leaf identity mismatch')
    kind = 'depth' if match[2] == '-depth.npz' else 'rgb'
    positive_integer(row['frame_id'], 'frame_id')
    require(row['frame_id'] == int(match[1]) and row['artifact_type'] == kind, 'Frame type/id mismatch')
    positive_integer(row['logical_bytes'], 'logical_bytes')
    require(row['policy'] == POLICY, 'Manifest policy mismatch')
    return row['run_id'], row['frame_id'] * 2 + (kind == 'depth')


def reconcile(manifest, reference, receipts, completion):
    """Reconcile one immutable manifest against its complete batch receipts."""
    manifest, receipts = Path(manifest), Path(receipts)
    manifest_source = source(manifest)
    require(manifest_source['sha256'] == reference['sha256'], 'Deletion manifest digest differs from partition')
    positive_integer(reference['files'], 'manifest files', 1)
    positive_integer(reference['logical_bytes'], 'manifest bytes')
    batch_count = (reference['files'] + BATCH_SIZE - 1) // BATCH_SIZE
    expected_names = {f'{i:05d}-{suffix}.json' for i in range(batch_count) for suffix in ('intent', 'complete')}
    entries = list(receipts.iterdir())
    require(all(p.is_file() for p in entries), 'Unexpected non-file in receipt directory')
    actual_names = {p.name for p in entries}
    require(actual_names == expected_names,
            'Missing/extra/failure receipts: ' + json.dumps({'missing': sorted(expected_names-actual_names),
                                                          'extra': sorted(actual_names-expected_names)}))
    require(completion['status'] == 'completed' and completion['policy'] == POLICY, 'Final completion status/policy mismatch')
    require(completion['manifest_sha256'] == reference['sha256'], 'Final completion manifest mismatch')
    begin, end = timestamp(completion['started']), timestamp(completion['finished'])
    require(begin <= end, 'Invalid final completion chronology')
    for key in ('files', 'logical_bytes'):
        positive_integer(completion[key], 'completion ' + key)
        require(completion[key] == reference[key], 'Final completion totals differ from partition')
    for key in ('disk_before', 'disk_after'):
        for metric in ('total', 'used', 'free'):
            positive_integer(completion[key][metric], key + ' ' + metric)
    require(completion['observed_free_space_increase_bytes'] == completion['disk_after']['free']-completion['disk_before']['free'],
            'Recorded free-space delta arithmetic differs')

    n = logical_bytes = 0
    batch = []
    reports = []
    seen = defaultdict(set)
    paths_hash = hashlib.sha256()
    receipt_set_hash = hashlib.sha256()
    previous_end = begin

    def check_batch(rows):
        nonlocal n, logical_bytes, previous_end
        index = n // BATCH_SIZE
        count = len(rows)
        size = sum(row['logical_bytes'] for row in rows)
        expected = {'manifest_sha256': reference['sha256'], 'first_ordinal': n,
                    'count': count, 'logical_bytes': size}
        path_bytes = ('\n'.join(row['path'] for row in rows) + '\n').encode('utf-8')
        path_hash = hashlib.sha256(path_bytes).hexdigest()
        paths_hash.update(path_bytes)
        sources = {}
        pair = {}
        for suffix in ('intent', 'complete'):
            p = receipts / f'{index:05d}-{suffix}.json'
            raw = p.read_bytes()
            value = json.loads(raw)
            keys = set(expected) | ({'created'} if suffix == 'intent' else {'finished', 'removed_paths_sha256'})
            require(set(value) == keys, 'Unexpected receipt schema: ' + p.name)
            for key, wanted in expected.items():
                if key != 'manifest_sha256':
                    positive_integer(value[key], p.name + ' ' + key)
                require(value[key] == wanted, 'Receipt ' + key + ' differs: ' + p.name)
            digest = hashlib.sha256(raw).hexdigest()
            sources[suffix] = {'name': p.name, 'bytes': len(raw), 'sha256': digest}
            receipt_set_hash.update((p.name + '\t' + digest + '\n').encode('utf-8'))
            pair[suffix] = value
        require(pair['complete']['removed_paths_sha256'] == path_hash, 'Exact removed-path SHA differs for batch ' + str(index))
        created, finished = timestamp(pair['intent']['created']), timestamp(pair['complete']['finished'])
        require(previous_end <= created <= finished <= end, 'Batch chronology differs for batch ' + str(index))
        previous_end = finished
        reports.append({'batch': index, **expected, 'removed_paths_sha256': path_hash, 'receipt_sources': sources})
        n += count
        logical_bytes += size

    with gzip.open(manifest, 'rt', encoding='utf-8') as f:
        for line in f:
            require(bool(line.strip()), 'Blank manifest line')
            row = json.loads(line)
            run_id, identity = lexical_identity(row)
            require(identity not in seen[run_id], 'Duplicate exact manifest frame identity')
            seen[run_id].add(identity)
            batch.append(row)
            if len(batch) == BATCH_SIZE:
                check_batch(batch)
                batch = []
    if batch:
        check_batch(batch)
    require(n == reference['files'] and logical_bytes == reference['logical_bytes'], 'Manifest stream totals differ from partition/completion')
    require(len(reports) == batch_count, 'Batch count differs')
    require(sha(manifest) == manifest_source['sha256'], 'Manifest changed during reconciliation')
    require({p.name for p in receipts.iterdir()} == expected_names, 'Receipt directory changed during reconciliation')
    for report in reports:
        for record in report['receipt_sources'].values():
            require(sha(receipts / record['name']) == record['sha256'], 'Receipt changed during reconciliation')
    return {'status': 'passed', 'manifest': manifest_source, 'files': n, 'logical_bytes': logical_bytes,
            'batch_size': BATCH_SIZE, 'batch_count': batch_count, 'receipt_count': len(entries),
            'final_batch_files': reports[-1]['count'], 'run_count': len(seen),
            'ordered_removed_paths_sha256': paths_hash.hexdigest(),
            'receipt_set_sha256': receipt_set_hash.hexdigest(),
            'receipt_set_hash_encoding': 'For each batch in ordinal order, intent then complete: UTF-8 filename + tab + SHA256 + newline.',
            'batches': reports,
            'scope': 'Exact path/order/count/byte reconciliation of authenticated completion receipts. No deleted evidence path is accessed. This does not substitute for the independent filesystem absence and retained-content postcheck.'}


def repo_path(value):
    p = Path(value)
    return p.resolve() if p.is_absolute() else (ROOT / p).resolve()


def argument(argv, flag):
    require(argv.count(flag) == 1, 'Ambiguous/missing official argument ' + flag)
    return argv[argv.index(flag) + 1]


def inspect_interrupted(manifest, reference, receipts, retained_manifest, retained_reference, filesystem_checker):
    """Prove the exact absent prefix and intact suffix after one interrupted batch.

    filesystem_checker(row, hash_content) returns absent/present after validating
    path safety and, when present, original metadata and optional content hash.
    It is injected to make the boundary rules testable without original evidence.
    """
    manifest, receipts = Path(manifest), Path(receipts)
    manifest_source = source(manifest)
    retained_source = source(retained_manifest)
    require(manifest_source['sha256'] == reference['sha256'], 'Interrupted deletion manifest digest mismatch')
    require(retained_source['sha256'] == retained_reference['sha256'], 'Retained manifest digest mismatch')
    names = {p.name for p in receipts.iterdir()}
    require(all(p.is_file() for p in receipts.iterdir()), 'Non-file interrupted receipt entry')
    complete_count = sum(name.endswith('-complete.json') for name in names)
    expected_names = {f'{i:05d}-{suffix}.json' for i in range(complete_count) for suffix in ('intent', 'complete')}
    expected_names.add(f'{complete_count:05d}-intent.json')
    require(names == expected_names, 'Interrupted receipts must be a complete prefix plus exactly one outstanding intent')
    outstanding = read(receipts / f'{complete_count:05d}-intent.json')
    prefix_files = complete_count * BATCH_SIZE
    require(outstanding['first_ordinal'] == prefix_files and outstanding['manifest_sha256'] == reference['sha256'], 'Outstanding intent prefix identity differs')
    require(type(outstanding['count']) is int and 0 < outstanding['count'] <= BATCH_SIZE, 'Invalid interrupted intent count')
    intent_end = prefix_files + outstanding['count']
    require(intent_end <= reference['files'], 'Interrupted intent extends beyond manifest')
    receipt_sources = []
    receipt_set_hash = hashlib.sha256()
    prefix_hash, absent_hash, interrupted_absent_hash, remaining_hash = (hashlib.sha256() for _ in range(4))
    prefix_bytes = absent_bytes = interrupted_absent_bytes = remaining_bytes = 0
    absent_files = remaining_files = n = total_bytes = 0
    seen = defaultdict(set)
    first_present = None
    last_finished = None
    completed_checks = []

    def check_receipts(batch, ordinal):
        nonlocal prefix_bytes, last_finished
        index = ordinal // BATCH_SIZE
        if index > complete_count:
            return
        common = {'manifest_sha256': reference['sha256'], 'first_ordinal': ordinal,
                  'count': len(batch), 'logical_bytes': sum(row['logical_bytes'] for row in batch)}
        values = {}
        for suffix in (('intent', 'complete') if index < complete_count else ('intent',)):
            leaf = receipts / f'{index:05d}-{suffix}.json'
            raw = leaf.read_bytes()
            value = json.loads(raw)
            keys = set(common) | ({'created'} if suffix == 'intent' else {'finished', 'removed_paths_sha256'})
            require(set(value) == keys, 'Interrupted receipt schema differs: ' + leaf.name)
            for key, expected in common.items():
                if key != 'manifest_sha256':
                    positive_integer(value[key], leaf.name + ' ' + key)
                require(value[key] == expected, 'Interrupted receipt field differs: ' + leaf.name + ' ' + key)
            record = {'name': leaf.name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            receipt_sources.append(record)
            receipt_set_hash.update((leaf.name + '\t' + record['sha256'] + '\n').encode())
            values[suffix] = value
        created = timestamp(values['intent']['created'])
        require(last_finished is None or last_finished <= created, 'Interrupted receipt chronology differs')
        if index < complete_count:
            data = ('\n'.join(row['path'] for row in batch) + '\n').encode()
            digest = hashlib.sha256(data).hexdigest()
            require(values['complete']['removed_paths_sha256'] == digest, 'Interrupted completed-prefix path SHA differs')
            last_finished = timestamp(values['complete']['finished'])
            require(created <= last_finished, 'Interrupted complete precedes intent')
            prefix_hash.update(data)
            prefix_bytes += common['logical_bytes']
            completed_checks.append({'batch': index, **common, 'removed_paths_sha256': digest})

    def inspect_batch(batch, pool):
        nonlocal n, total_bytes, absent_files, absent_bytes, interrupted_absent_bytes, first_present, remaining_files, remaining_bytes
        check_receipts(batch, n)
        statuses = pool.map(lambda row: filesystem_checker(row, False), batch)
        for row, state in zip(batch, statuses):
            data = (row['path'] + '\n').encode()
            require(state in ('absent', 'present'), 'Unexpected filesystem state')
            if n < prefix_files:
                require(state == 'absent', 'Receipted completed-prefix file is present at ordinal ' + str(n))
            if state == 'absent':
                require(n < intent_end, 'Absent path outside issued interrupted intent at ordinal ' + str(n))
                require(first_present is None, 'Interrupted absences are not a contiguous prefix at ordinal ' + str(n))
                absent_files += 1
                absent_bytes += row['logical_bytes']
                absent_hash.update(data)
                if n >= prefix_files:
                    interrupted_absent_bytes += row['logical_bytes']
                    interrupted_absent_hash.update(data)
            else:
                if first_present is None:
                    first_present = n
                remaining_files += 1
                remaining_bytes += row['logical_bytes']
                remaining_hash.update(data)
            n += 1
            total_bytes += row['logical_bytes']

    with ThreadPoolExecutor(max_workers=8) as pool:
        batch = []
        with gzip.open(manifest, 'rt', encoding='utf-8') as f:
            for line in f:
                require(bool(line.strip()), 'Blank interrupted manifest line')
                row = json.loads(line)
                run_id, identity = lexical_identity(row)
                require(identity not in seen[run_id], 'Duplicate interrupted manifest frame identity')
                seen[run_id].add(identity)
                batch.append(row)
                if len(batch) == BATCH_SIZE:
                    inspect_batch(batch, pool)
                    batch = []
        if batch:
            inspect_batch(batch, pool)
        require(n == reference['files'] and total_bytes == reference['logical_bytes'], 'Interrupted manifest totals differ')
        require(absent_files + remaining_files == n and absent_bytes + remaining_bytes == total_bytes, 'Absent/present accounting differs')
        if first_present is None:
            first_present = n
        require(first_present == absent_files, 'No exact remaining suffix established')
        retained_files = retained_bytes = 0
        def check_retained(rows):
            nonlocal retained_files, retained_bytes
            for row, state in zip(rows, pool.map(lambda row: filesystem_checker(row, True), rows)):
                require(state == 'present', 'Retained artifact is absent')
                retained_files += 1
                retained_bytes += row['logical_bytes']
        batch = []
        with gzip.open(retained_manifest, 'rt', encoding='utf-8') as f:
            for line in f:
                row = json.loads(line)
                run_id, identity = lexical_identity(row)
                require(identity not in seen[run_id], 'Retained/deletion identity overlap or duplicate')
                seen[run_id].add(identity)
                batch.append(row)
                if len(batch) == BATCH_SIZE:
                    check_retained(batch)
                    batch = []
        if batch:
            check_retained(batch)
    require(retained_files == retained_reference['files'] and retained_bytes == retained_reference['logical_bytes'], 'Retained manifest totals differ')
    require(sha(manifest) == manifest_source['sha256'] and sha(retained_manifest) == retained_source['sha256'], 'Manifest changed during interrupted inspection')
    require({p.name for p in receipts.iterdir()} == names, 'Interrupted receipt directory changed')
    for record in receipt_sources:
        require(sha(receipts / record['name']) == record['sha256'], 'Interrupted receipt changed')
    return {'status': 'passed', 'manifest': manifest_source, 'retained_manifest': retained_source,
            'manifest_files': n, 'manifest_logical_bytes': total_bytes,
            'completed_receipt_prefix': {'batches': complete_count, 'files': prefix_files, 'logical_bytes': prefix_bytes,
                                         'ordered_paths_sha256': prefix_hash.hexdigest()},
            'interrupted_intent': {**outstanding, 'absent_files': absent_files-prefix_files,
                                   'absent_logical_bytes': interrupted_absent_bytes,
                                   'absent_ordered_paths_sha256': interrupted_absent_hash.hexdigest(),
                                   'interpretation': 'Observed absent within issued interrupted intent; no historical complete receipt is fabricated.'},
            'observed_absent_prefix': {'files': absent_files, 'logical_bytes': absent_bytes, 'ordered_paths_sha256': absent_hash.hexdigest()},
            'first_remaining_ordinal': first_present,
            'remaining': {'first_ordinal': first_present, 'end_ordinal_exclusive': n, 'files': remaining_files,
                          'logical_bytes': remaining_bytes, 'ordered_paths_sha256': remaining_hash.hexdigest()},
            'retained_content_verification': {'status': 'passed', 'files': retained_files, 'logical_bytes': retained_bytes, 'workers': 8},
            'receipt_count': len(names), 'receipt_set_sha256': receipt_set_hash.hexdigest(),
            'receipt_sources': receipt_sources, 'completed_batch_checks': completed_checks,
            'checks': {'all_completed_prefix_paths_absent': True, 'interrupted_absence_is_contiguous_prefix': True,
                       'all_following_paths_present_with_exact_original_size_mtime': True, 'all_retained_content_sha256_unchanged': True,
                       'receipts_and_manifests_unchanged': True},
            'scope': 'Queued read-only interruption reconciliation. Original interrupted job is failure context; this proof becomes usable only after this checker itself officially succeeds. No source or receipt was changed.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--retirement-receipt', type=Path)
    mode.add_argument('--interrupted-receipt', type=Path)
    p.add_argument('--partition', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    sys.path.insert(0, str(IMP.parent / 'Runtime Recovery 001'))
    import recovery_runner
    own_job = recovery_runner.queued_job(expected_script=__file__)
    receipt_path = a.interrupted_receipt or a.retirement_receipt
    saved = read(receipt_path)
    if a.interrupted_receipt:
        require(saved['state'] == 'interrupted' and saved['ended_at'] is not None, 'Original retirement is not officially interrupted')
    else:
        require(saved['state'] == 'succeeded' and saved['exit_status'] == 0, 'Retirement has not officially succeeded')
    queue = ROOT.parent / 'tools/compute_queue/compute_queue.py'
    live = json.loads(subprocess.check_output([sys.executable, '-X', 'utf8', '-B', str(queue), 'status', saved['id']]))
    require(saved == live, 'Saved retirement receipt differs from official queue status')
    argv = saved['argv']
    require(Path(saved['cwd']).resolve() == ROOT and argv.count('delete') == 1, 'Not a project retirement job')
    i = argv.index('delete')
    require(repo_path(argv[i-1]) == IMP / 'retention.py', 'Unexpected retirement program')
    name = argument(argv, '--name')
    require(a.partition.resolve() == IMP / 'records' / (name + '-partition.json'), 'Partition differs from official retirement name')
    gate_path = repo_path(argument(argv, '--gate'))
    gate, partition = read(gate_path), read(a.partition)
    require(gate['status'] == 'passed' and gate['partition_sha256'] == sha(a.partition), 'Gate does not authenticate partition')
    require(set(gate['checks']) == GATES and all(v is True for v in gate['checks'].values()), 'Gate checks differ from required passed checks')
    reference = partition['manifests']['deletion']
    require(gate['deletion_manifest_sha256'] == reference['sha256'], 'Gate deletion digest differs')
    manifest = repo_path(reference['path'])
    require(manifest == IMP / 'manifests' / (name + '-deletion.jsonl.gz'), 'Unexpected deletion manifest path')
    receipt_dir = IMP / 'records' / (name + '-deletion-receipts')
    completion_path = IMP / 'records' / (name + '-deletion-complete.json')
    sources = {'retirement_official_receipt': source(receipt_path), 'partition': source(a.partition),
               'gate': source(gate_path), 'reconciler': source(__file__)}
    if a.interrupted_receipt:
        require(not completion_path.exists(), 'Interrupted job has an unexpected final completion record')
        spec = importlib.util.spec_from_file_location('retention_readonly_path_checks', IMP / 'retention.py')
        retention = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(retention)
        sources['retention_path_checker'] = source(IMP / 'retention.py')
        def filesystem_checker(row, hash_content):
            leaf = retention.safe_frame(row['path'], check_exists=False)
            try:
                st = leaf.stat()
            except FileNotFoundError:
                return 'absent'
            require((st.st_size, st.st_mtime_ns) == (row['logical_bytes'], row['mtime_ns']), 'Surviving file metadata differs: ' + row['path'])
            if hash_content:
                require(sha(leaf) == row['sha256'], 'Retained SHA differs: ' + row['path'])
                after = leaf.stat()
                require((after.st_size, after.st_mtime_ns) == (st.st_size, st.st_mtime_ns), 'Retained file changed during hash')
            return 'present'
        retained_reference = partition['manifests']['retained']
        retained_manifest = repo_path(retained_reference['path'])
        result = inspect_interrupted(manifest, reference, receipt_dir, retained_manifest, retained_reference, filesystem_checker)
        for record in result['receipt_sources']:
            value = read(receipt_dir / record['name'])
            t = timestamp(value.get('created', value.get('finished')))
            require(timestamp(saved['started_at']) <= t <= timestamp(saved['ended_at']), 'Original receipt time outside interrupted execution')
        protected_path = IMP / 'records' / partition['census'] / 'protected-metadata.json'
        sources['protected_metadata'] = source(protected_path)
        protected = read(protected_path)
        require(len(protected) == 3323, 'Protected non-frame inventory count differs')
        def check_protected(row):
            path = ROOT / row['path']
            require(path.resolve().is_relative_to(ROOT), 'Protected path outside repository')
            st = path.stat()
            require((st.st_size, st.st_mtime_ns) == (row['logical_bytes'], row['mtime_ns']), 'Protected non-frame metadata differs: ' + row['path'])
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(check_protected, protected))
        result.update({'format': 'interrupted-retirement-reconciliation-1',
                       'partition_sha256': sources['partition']['sha256'], 'deletion_manifest_sha256': reference['sha256'],
                       'original_retirement_job_id': saved['id'], 'original_receipt_set_sha256': result['receipt_set_sha256'],
                       'completed_prefix': result['completed_receipt_prefix'],
                       'interrupted_intent_absences': {'files': result['interrupted_intent']['absent_files'],
                           'logical_bytes': result['interrupted_intent']['absent_logical_bytes'],
                           'ordered_paths_sha256': result['interrupted_intent']['absent_ordered_paths_sha256'],
                           'first_ordinal': result['interrupted_intent']['first_ordinal']},
                       'all_retained_hashes_verified': True, 'protected_nonframe_metadata_checked': len(protected),
                       'disk_baseline': None, 'disk_baseline_scope': 'Original delete process recorded its volume baseline only in memory; no baseline receipt survived. Use explicitly labeled preflight census baseline for a wider-interval free-space comparison.'})
    else:
        sources['completion'] = source(completion_path)
        completion = read(completion_path)
        require(timestamp(saved['started_at']) <= timestamp(completion['started']) <= timestamp(completion['finished']) <= timestamp(saved['ended_at']),
                'Completion times are outside the official retirement execution')
        result = reconcile(manifest, reference, receipt_dir, completion)
        result['format'] = 'retirement-receipt-reconciliation-1'
    for identity in sources.values():
        require(sha(identity['path']) == identity['sha256'], 'Authenticated input changed during reconciliation')
    result.update({'queue_job_id': own_job['id'],
                   'retirement_queue_job_id': saved['id'], 'created_at': datetime.now(timezone.utc).isoformat(),
                   'sources': sources, 'official_retirement_receipt': saved})
    with a.output.open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    if a.interrupted_receipt:
        print(json.dumps({k: result[k] for k in ('status', 'first_remaining_ordinal', 'observed_absent_prefix', 'remaining', 'retained_content_verification')}))
    else:
        print(json.dumps({k: result[k] for k in ('status', 'files', 'logical_bytes', 'batch_count', 'receipt_count', 'final_batch_files')}))


if __name__ == '__main__':
    main()
