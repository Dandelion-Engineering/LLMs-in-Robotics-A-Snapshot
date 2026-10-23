"""Authenticate and replay the disposable recorder feasibility evidence.

This external diagnostic assessor neither adopts a recorder configuration nor
admits physics/model runs. It never opens an interrupted source database: SQLite
reads are limited to already recovered copies and original Reader containers.
"""
from __future__ import annotations

import argparse
from collections import OrderedDict
from datetime import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sqlite3
import struct
import sys

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
REPO = CAMPAIGN.parents[2]
PROTOTYPE = HERE / 'persist-feasibility'
ORIGINAL = REPO / 'Long-Horizon Adaptive Robotics Expirement/Storage Retention Implementation 001/future'
sys.path.insert(0, str(CAMPAIGN / 'assessment'))
import assess as base

ORDER = ['DELETE', 'PERSIST', 'PERSIST', 'DELETE', 'DELETE', 'PERSIST', 'PERSIST', 'DELETE']
SPACE_POLICY = dict(host_cap_bytes=536870912, native_reserve_bytes=67108864,
    database_limit_bytes=2097152, journal_limit_bytes=33554432,
    publication_limit_bytes=8388608, metadata_allowance_bytes=1048576)
FIELDS = ['operation_code', 'wall_start_s', 'wall_end_s', 'thread_cpu_s', 'process_cpu_s', 'success']
CODES = dict(execute=1, executemany=2, executescript=3, commit=4, rollback=5, close=6,
             image=7, motion_write=8, trigger=9, event=10, document=11)
EXPECTED_COUNTS = dict(image=600, motion_write=6000, event=6, trigger=1, document=1, commit=614)
CAPACITY = 15424
FINAL_STEPS = ['sqlite_delete_mode_selected', 'sqlite_closed_no_sidecars_before_original_compression',
               'original_exact_byte_gzip_manifest_publication_completed']
SOURCE_PATHS = [PROTOTYPE / name for name in ('candidate.py', 'benchmark.py', 'test_candidate.py')]
SOURCE_PATHS += [ORIGINAL / name for name in ('recorder.py', 'runtime_adapter.py')]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def stamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None, 'Timestamp lacks timezone')
    return parsed.timestamp()


def safe_path(root, name):
    root = Path(root).resolve()
    relative = Path(name)
    require(not relative.is_absolute() and '..' not in relative.parts, 'Unsafe relative evidence path')
    path = root / relative
    require(path.resolve().is_relative_to(root) and not path.is_symlink(), 'Evidence path escapes its root')
    return path


def inventory(directory):
    root = Path(directory)
    require(root.is_dir() and not root.is_symlink(), 'Evidence directory absent or linked')
    values = {}
    for path in sorted(root.rglob('*')):
        require(not path.is_symlink(), 'Linked evidence entry')
        if path.is_file():
            require(path.resolve().is_relative_to(root.resolve()), 'Evidence entry escapes directory')
            values[path.relative_to(root).as_posix()] = dict(bytes=path.stat().st_size, sha256=base.hash_file(path))
    return values


def validate_manifest(value):
    expected = dict(schema='rci-recorder-journal-feasibility-1', seed=173, mode_order=ORDER,
        frames_per_round=600, motion_rows_per_frame=10, width=64, height=48, wall_cap_s=300,
        space_policy=SPACE_POLICY)
    for name, target in expected.items():
        require(type(value.get(name)) is type(target) and value[name] == target,
                'Fixed declaration differs: ' + name)
    for name in ('run_id', 'framework_revision'):
        require(isinstance(value.get(name), str) and bool(value[name]), 'Missing identity: ' + name)
    return value


def authenticate(manifest_path, evidence, queue_path, snapshot_path):
    """No outcome directory or result is accessed until all admission gates pass."""
    job = base.queue_gate(base.read_json(queue_path))
    expected = [str(REPO / 'venv/Scripts/python.exe'), '-X', 'utf8', '-B',
                str(PROTOTYPE / 'benchmark.py'), 'run', '--manifest', str(manifest_path.resolve()),
                '--output', str(evidence.resolve())]
    require(job.get('argv') == expected and Path(job.get('cwd', '')).resolve() == REPO.resolve()
            and Path(job.get('resolved_executable', '')).resolve() == Path(expected[0]).resolve(),
            'Wrong direct feasibility queue command')
    require(isinstance(job.get('id'), str) and bool(job['id'])
            and stamp(job['started_at']) <= stamp(job['ended_at']), 'Invalid official execution interval')
    frozen = base.read_json(snapshot_path)
    require(not base.source_integrity(frozen, snapshot_path.with_name('code.zip')),
            'Frozen feasibility source archive mismatch')
    sources = frozen['sources']
    required = SOURCE_PATHS + [Path(__file__).resolve(), Path(base.__file__).resolve()]
    require(all(path.relative_to(REPO).as_posix() in sources for path in required),
            'Frozen source set omits assessor or feasibility source')
    for name, row in sources.items():
        path = safe_path(REPO, name)
        require(path.is_file() and base.hash_file(path) == row['sha256']
                and (row.get('bytes') is None or path.stat().st_size == row['bytes']),
                'Current frozen source differs: ' + name)
    manifest = validate_manifest(base.read_json(manifest_path))
    require(base.hash_file(manifest_path) == frozen['manifest_sha256']
            and manifest['framework_revision'] == frozen['revision']
            and manifest['run_id'] == frozen['run_id'], 'Feasibility manifest not frozen')
    return manifest, frozen, job


def original_recorder():
    """Load the hash-checked original implementation, never the candidate."""
    name = '_recorder_feasibility_original_reader'
    spec = importlib.util.spec_from_file_location(name, ORIGINAL / 'recorder.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def reader_fingerprint(directory, original):
    reader = original.Reader(directory)
    hashes, counts = {}, {}
    try:
        for name, values in (('events', reader.events()), ('motion', reader.motion()), ('images', reader.images())):
            hasher, count = hashlib.sha256(), 0
            for value in values:
                raw = original.pack(value)
                hasher.update(struct.pack('<Q', len(raw))); hasher.update(raw)
                count += 1
            hashes[name], counts[name] = hasher.hexdigest(), count
        hasher, count = hashlib.sha256(), 0
        for row in reader.images():
            image = reader.image(row['id'])
            if image['status'] == 'available':
                for raw in (row['id'].encode('utf-8'), image['rgb'], image['depth']):
                    hasher.update(struct.pack('<Q', len(raw))); hasher.update(raw)
                count += 1
        hashes['available_image_pairs'], counts['available_image_pairs'] = hasher.hexdigest(), count
        documents = {row[0]: reader.document(row[0])
                     for row in reader.db.execute('SELECT name FROM documents ORDER BY name')}
        hashes['documents'], counts['documents'] = hashlib.sha256(original.pack(documents)).hexdigest(), len(documents)
        check = [list(row) for row in reader.db.execute('PRAGMA integrity_check').fetchall()]
        require(check == [['ok']], 'Original Reader SQLite integrity failed')
        return dict(hashes=hashes, counts=counts, integrity_check=check,
                    journal_mode=reader.db.execute('PRAGMA journal_mode').fetchone()[0])
    finally:
        reader.close()


def distribution(values):
    values = sorted(values)
    if not values:
        return dict(count=0)
    count = len(values)
    return dict(count=count, minimum_s=values[0], median_s=values[(count-1)//2],
        p95_s=values[int(.95*(count-1))], p99_s=values[int(.99*(count-1))],
        maximum_s=values[-1], total_s=sum(values), quantile_method='lower order statistic')


def same_numbers(left, right):
    if isinstance(right, dict):
        return isinstance(left, dict) and left.keys() == right.keys() and all(same_numbers(left[k], v) for k, v in right.items())
    if isinstance(right, float):
        return number(left) and math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)
    return type(left) is type(right) and left == right


def verify_operations(root, binding, latency):
    require(binding.get('schema') == 'rci-recorder-operation-timing-1'
            and binding.get('sample_file') == 'operations.bin'
            and binding.get('fields') == FIELDS and binding.get('operation_codes') == CODES
            and binding.get('encoding') == 'little-endian float64 rows', 'Operation encoding differs')
    count = binding.get('count')
    require(type(count) is int and 0 <= count <= CAPACITY
            and type(binding.get('capacity')) is int and binding['capacity'] == CAPACITY,
            'Operation count/capacity differs')
    path = root / 'operations.bin'
    require(type(binding.get('bytes')) is int and binding['bytes'] == count*48 == path.stat().st_size
            and base.hash_file(path) == binding.get('sha256'), 'Operation binary length/hash differs')
    by_name, summaries, prior_end = {}, {}, -1.
    names = {code: name for name, code in CODES.items()}
    for code, start, end, thread, process, success in struct.iter_unpack('<6d', path.read_bytes()):
        require(all(math.isfinite(x) for x in (code, start, end, thread, process, success)), 'Nonfinite operation sample')
        require(code in names and success in (0., 1.) and 0 <= start <= end and end >= prior_end
                and thread >= 0 and process >= 0, 'Invalid operation code, success, or completion order')
        # Windows CPU counters are quantized; CPU <= wall is deliberately not a gate.
        prior_end = end
        name, duration = names[code], end-start
        by_name.setdefault(name, []).append(duration)
        row = summaries.setdefault(name, dict(count=0, failures=0, wall_total_s=0., wall_max_s=0.))
        row['count'] += 1; row['failures'] += int(success == 0)
        row['wall_total_s'] += duration; row['wall_max_s'] = max(row['wall_max_s'], duration)
    require(same_numbers(binding.get('summaries'), summaries), 'Operation summaries differ from binary replay')
    replay_latency = {name: distribution(by_name.get(name, [])) for name in ('image', 'commit', 'execute')}
    require(same_numbers(latency, replay_latency), 'Latency distribution differs from binary replay')
    return dict(sample_count=count, summaries=summaries, latency=replay_latency,
                last_completion_s=None if not count else prior_end,
                scope='Inclusive nested API/SQL timings; do not sum categories. No performance-win threshold.')


def verify_readback(row, stage, mode, database, sqlite_version):
    require(row.get('stage') == stage and row.get('journal_mode') == mode
            and type(row.get('synchronous')) is int and row['synchronous'] == 2
            and row.get('in_transaction') is False and row.get('sqlite_version') == sqlite_version,
            'Mode/FULL/transaction readback differs')
    databases = row.get('database_list')
    require(isinstance(databases, list) and len(databases) == 1 and len(databases[0]) == 3
            and databases[0][:2] == [0, 'main'] and Path(databases[0][2]).resolve() == database.resolve(),
            'Readback does not identify the single expected main database')
    size = row.get('page_size')
    require(type(size) is int and 512 <= size <= 65536 and size & (size-1) == 0, 'Invalid SQLite page size')


def space_groups(files):
    allowed = {'evidence.sqlite', 'evidence.sqlite-journal', 'evidence.sqlite.gz', 'evidence.sqlite.gz.partial',
               'container-manifest.json', 'container-manifest.json.partial', 'RECORDING_FAILED.json'}
    require(isinstance(files, dict) and not files.keys()-allowed
            and all(type(n) is int and n >= 0 for n in files.values()), 'Invalid observed recorder files')
    return dict(database=files.get('evidence.sqlite', 0), journal=files.get('evidence.sqlite-journal', 0),
        publication=sum(files.get(name, 0) for name in ('evidence.sqlite.gz', 'evidence.sqlite.gz.partial',
                        'container-manifest.json', 'container-manifest.json.partial')),
        metadata=files.get('RECORDING_FAILED.json', 0), total=sum(files.values()))


def verify_space(value, files):
    require(value.get('policy') == SPACE_POLICY and value.get('errors') == []
            and type(value.get('observation_count')) is int and value['observation_count'] > 0,
            'Observed space policy failed or absent')
    limits = dict(database=SPACE_POLICY['database_limit_bytes'], journal=SPACE_POLICY['journal_limit_bytes'],
        publication=SPACE_POLICY['publication_limit_bytes'], metadata=SPACE_POLICY['metadata_allowance_bytes'],
        total=SPACE_POLICY['native_reserve_bytes'])
    maxima, largest, final = value['observed_maxima'], value['largest_observations'], value['final_observation']
    require(maxima.keys() == limits.keys() and set(largest) == {k for k, v in maxima.items() if v > 0},
            'Space maxima or witnesses absent')
    for key, limit in limits.items():
        require(type(maxima[key]) is int and 0 <= maxima[key] <= limit, 'Observed space limit exceeded')
    for row in list(largest.values()) + [final]:
        groups = space_groups(row['files'])
        require(all(row.get(key) == amount <= maxima[key] for key, amount in groups.items()), 'Space witness differs')
    require(all(largest[key][key] == maxima[key] for key in largest), 'Space maximum lacks matching witness')
    require(final.get('boundary') == 'after_original_finalization'
            and final['files'] == {name: item['bytes'] for name, item in files.items()},
            'Final observed space differs from retained files')


def verify_round(evidence, row, ordinal, mode, original, sqlite_version):
    root = evidence / ('round-%02d-%s' % (ordinal, mode.lower()))
    report = dict(ordinal=ordinal, mode=mode, passed=False, checks={}, errors={}, timing=None)
    try:
        require(row.get('ordinal') == ordinal and row.get('mode') == mode, 'Round identity/order differs')
        if row.get('status') == 'unrun_wall_cap':
            require(row.get('passed') is False, 'Unrun round marked passed')
            report['errors']['completion'] = 'Fixed round was not run before the wall cap'
            return report
        binding = row['result_binding']
        result_path = safe_path(evidence, binding['path'])
        require(result_path.resolve() == (root / 'result.json').resolve()
                and base.hash_file(result_path) == binding['sha256']
                and base.read_json(result_path) == {k: v for k, v in row.items() if k != 'result_binding'},
                'Round result binding differs')
        report['checks']['retained_round_binding'] = True
        report['timing'] = verify_operations(root, row['operation_timing'], row['latency'])
        report['checks']['operation_binary_replayed'] = True
        files = inventory(root / 'native-recording') if (root / 'native-recording').exists() else {}
        require(files == row['retained_files'], 'Retained round file inventory differs')
        report['checks']['retained_files_bound'] = True
        require(row.get('status') == 'completed' and row.get('passed') is True and not row.get('error'),
                'Round failed or was incomplete; preserved without retry')
        summaries = report['timing']['summaries']
        require(all(summaries.get(name, {}).get('count') == count for name, count in EXPECTED_COUNTS.items())
                and all(value['failures'] == 0 for value in summaries.values())
                and not ({'rollback', 'close'} & summaries.keys()), 'Completed workload operation counts/failures differ')
        require(set(files) == {'container-manifest.json', 'evidence.sqlite.gz'}, 'Completed container has working files/sidecars')
        candidate = row['candidate']
        require(candidate.get('schema') == 'rci-recorder-journal-candidate-1' and candidate.get('mode') == mode
                and candidate.get('first_failure') is None and candidate.get('finalization_steps') == FINAL_STEPS
                and candidate.get('encoded_pair_count') == 600 and digest(candidate.get('encoded_pairs_sha256')),
                'Candidate failure, encoding count, or finalization differs')
        readbacks = candidate['readbacks']
        require(len(readbacks) == 3, 'Missing or extra candidate readback')
        for readback, stage, expected in zip(readbacks, ('before_work', 'before_finalization', 'delete_transition'), (mode, mode, 'DELETE')):
            verify_readback(readback, stage, expected, root / 'native-recording/evidence.sqlite', sqlite_version)
        verify_space(candidate['space'], files)
        report['checks']['full_single_database_finalization_space'] = True
        workload = row['workload']
        require(workload.get('frames') == 600 and workload.get('motion_rows') == 6000
                and digest(workload.get('input_sha256')) and number(workload.get('measured_workload_wall_s'))
                and 0 < workload['measured_workload_wall_s'] <= 300, 'Fixed input workload differs')
        fingerprint = reader_fingerprint(root / 'native-recording', original)
        require(fingerprint == row['reader'] and fingerprint['journal_mode'] == 'memory'
                and all(fingerprint['counts'][key] == count for key, count in dict(events=6, motion=6000, images=600, documents=2).items())
                and 0 < fingerprint['counts']['available_image_pairs'] <= 600, 'Original Reader payload replay differs')
        report['reader'] = fingerprint
        report['input_sha256'] = workload['input_sha256']
        report['encoded_pairs_sha256'] = candidate['encoded_pairs_sha256']
        report['observed_space_maxima'] = candidate['space']['observed_maxima']
        report['checks']['original_reader_replayed'] = True
        report['passed'] = True
    except Exception as error:
        report['errors']['verification'] = str(error)
    return report


def verify_recovery(evidence, row, mode, stage, original, sqlite_version, job):
    report = dict(mode=mode, stage=stage, passed=False)
    root = evidence / ('crash-' + mode.lower() + '-' + stage)
    source, recovered = root / 'interrupted', root / 'recovery-copy'
    try:
        require(row.get('mode') == mode and row.get('stage') == stage and row.get('passed') is True,
                'Recovery fixture failed, missing, or unrun')
        require(type(row.get('actual_child_exit')) is int and row['actual_child_exit'] == 23
                and type(row.get('expected_child_exit')) is int and row['expected_child_exit'] == 23,
                'Crash fixture exit differs')
        expected = [str(REPO / 'venv/Scripts/python.exe'), '-X', 'utf8', '-B', str(PROTOTYPE / 'benchmark.py'),
                    'crash-child', '--directory', str(source), '--mode', mode, '--stage', stage]
        require(row.get('argv') == expected and number(row.get('started_unix_s')) and number(row.get('ended_unix_s'))
                and stamp(job['started_at']) <= row['started_unix_s'] <= row['ended_unix_s'] <= stamp(job['ended_at'])
                and number(row.get('wall_s')) and 0 <= row['wall_s'] <= 300, 'Crash subprocess provenance differs')
        ready = base.read_json(root / 'crash-ready.json')
        require(ready == row.get('ready') and ready['mode'] == mode and ready['stage'] == stage
                and ready['cache_pages'] == 8 and digest(ready['stable_payload_sha256']), 'Crash-ready receipt differs')
        verify_readback(ready['readback'], 'crash_fixture', mode, source / 'evidence.sqlite', sqlite_version)
        source_files, recovered_files = inventory(source), inventory(recovered)
        require(source_files == row.get('source_files') and recovered_files == row.get('recovered_files')
                and row.get('source_pair_preserved') is True
                and 'evidence.sqlite' in source_files and 'evidence.sqlite' in recovered_files
                and not (set(source_files) | set(recovered_files)) - {'evidence.sqlite', 'evidence.sqlite-journal'},
                'Interrupted/recovered files differ or were published complete')
        journal = source / 'evidence.sqlite-journal'
        require(ready['journal_present'] is journal.exists()
                and ready['journal_bytes'] == (journal.stat().st_size if journal.exists() else 0)
                and ready['first_journal_header_hex'] == (journal.read_bytes()[:28].hex() if journal.exists() else None),
                'Retained interrupted journal differs from crash boundary')
        require(ready['in_transaction'] is (stage == 'before_commit'), 'Crash transaction boundary differs')
        if stage == 'before_commit':
            require(journal.is_file() and journal.stat().st_size > 28, 'Hot-journal fixture absent')
        names = ['pending', 'stable'] if stage == 'after_commit' else ['stable']
        # This copy was already recovered by the driver. Read-only mode must not
        # repair or mutate it, and the interrupted source is never opened here.
        connection = sqlite3.connect((recovered / 'evidence.sqlite').resolve().as_uri() + '?mode=ro', uri=True)
        try:
            connection.execute('PRAGMA query_only=ON')
            rows = connection.execute('SELECT name,payload FROM documents ORDER BY name').fetchall()
            require([name for name, _ in rows] == names == row.get('committed_document_names'),
                    'Recovered committed transaction set differs')
            stable = dict(rows)['stable']
            # Diagnostic decoding only: borrow the original object's recursive
            # hash checks on this read-only crash copy. No complete manifest or
            # state is fabricated, and this is not complete-container admission.
            decoder = original.Reader.__new__(original.Reader)
            decoder.db, decoder.cache, decoder.cache_bytes = connection, OrderedDict(), 0
            require(hashlib.sha256(stable).hexdigest() == ready['stable_payload_sha256']
                    and decoder.document('stable') == {'committed': True, 'value': 'before interruption'},
                    'Recovered committed payload differs')
            if stage == 'after_commit':
                expected_pending = {'pending': True,
                    'data': ''.join(hashlib.sha256(str(index).encode('utf-8')).hexdigest() for index in range(4000))}
                require(decoder.document('pending') == expected_pending, 'Recovered pending payload differs')
            require(connection.execute('PRAGMA integrity_check').fetchall() == [('ok',)], 'Recovered integrity check failed')
        finally:
            connection.close()
        require(inventory(source) == source_files and inventory(recovered) == recovered_files,
                'Assessor read changed source or recovered files')
        report.update(passed=True, source_files=source_files, recovered_files=recovered_files,
                      committed_document_names=names, exact_committed_payloads_verified=True,
                      decoding_scope='Diagnostic recovery-copy decoding with original object hash checks; not complete-container admission.')
    except Exception as error:
        report['error'] = str(error)
    return report


def evaluate(manifest_path, evidence, queue_path, snapshot_path):
    manifest_path, evidence, queue_path, snapshot_path = map(Path, (manifest_path, evidence, queue_path, snapshot_path))
    evidence = evidence.resolve()
    manifest, frozen, job = authenticate(manifest_path, evidence, queue_path, snapshot_path)
    result_path = evidence / 'result.json'
    result = base.read_json(result_path)
    checks, errors = {}, {}

    def check(name, function):
        try:
            require(function(), name)
            checks[name] = True
        except Exception as error:
            checks[name] = False; errors[name] = str(error)

    check('result_identity', lambda: result.get('schema') == 'rci-recorder-journal-feasibility-result-1'
          and result.get('run_id') == manifest['run_id'] and result.get('framework_revision') == frozen['revision']
          and result.get('manifest_sha256') == frozen['manifest_sha256'] and result.get('declared_mode_order') == ORDER)
    expected_sources = {p.relative_to(REPO).as_posix(): dict(bytes=p.stat().st_size, sha256=base.hash_file(p)) for p in SOURCE_PATHS}
    check('executed_source_bindings', lambda: result.get('source_bindings') == expected_sources)
    check('queue_encloses_result', lambda: stamp(job['started_at']) <= stamp(result['created_at']) <= stamp(job['ended_at']))
    check('declared_wall_cap', lambda: number(result.get('total_wall_s')) and 0 < result['total_wall_s'] <= 300)
    check('no_adoption_or_score', lambda: result.get('production_adopted') is False and result.get('scorable') is False
          and result.get('task_outcome') == 'unknown')
    retained = inventory(evidence)
    total = sum(item['bytes'] for item in retained.values())
    check('retained_aggregate_storage', lambda: type(result.get('aggregate_output_bytes')) is int
          and result['aggregate_output_bytes'] == total - result_path.stat().st_size
          and total <= SPACE_POLICY['host_cap_bytes'])
    original = original_recorder()
    rows, recovery_rows = result.get('rounds', []), result.get('recovery_checks', [])
    check('all_fixed_rounds_retained', lambda: isinstance(rows, list) and len(rows) == len(ORDER))
    rounds = [verify_round(evidence, rows[index] if index < len(rows) else {}, index, mode,
                           original, result.get('environment', {}).get('sqlite')) for index, mode in enumerate(ORDER)]
    checks['all_rounds_mechanically_valid'] = all(row['passed'] for row in rounds)
    parity = checks['all_rounds_mechanically_valid'] and all(
        all(row[name] == rounds[0][name] for name in ('reader', 'input_sha256', 'encoded_pairs_sha256')) for row in rounds)
    checks['original_reader_and_input_encoded_parity'] = parity
    check('producer_parity_agrees', lambda: type(result.get('exact_reader_input_encoded_parity')) is bool
          and result['exact_reader_input_encoded_parity'] == parity)
    combinations = [(mode, stage) for mode in ('DELETE', 'PERSIST') for stage in ('before_commit', 'after_commit')]
    check('all_recovery_fixtures_retained', lambda: isinstance(recovery_rows, list) and len(recovery_rows) == 4)
    recovery = [verify_recovery(evidence, recovery_rows[index] if index < len(recovery_rows) else {}, mode, stage,
                                original, result.get('environment', {}).get('sqlite'), job)
                for index, (mode, stage) in enumerate(combinations)]
    checks['all_recovery_fixtures_verified'] = all(row['passed'] for row in recovery)
    check('no_recorded_failures', lambda: result.get('failures') == [])
    computed = all(checks.values())
    check('producer_mechanical_result_agrees', lambda: type(result.get('mechanical_feasibility_passed')) is bool
          and result['mechanical_feasibility_passed'] == computed)
    return dict(schema='rci-recorder-journal-feasibility-assessment-1', run_id=manifest['run_id'],
        framework_revision=frozen['revision'], queue_job_id=job['id'], checks=checks, errors=errors,
        mechanical_feasibility_passed=all(checks.values()), rounds=rounds, recovery_checks=recovery,
        bindings={name: dict(path=str(path.resolve()), sha256=base.hash_file(path)) for name, path in
                  dict(manifest=manifest_path, queue=queue_path, snapshot=snapshot_path, result=result_path,
                       assessor=Path(__file__)).items()},
        model_calls=0, scorable=False, task_outcome='unknown', production_adopted=False,
        scope='Mechanical feasibility only; no performance-win threshold, physics timing qualification, or model score. '
              'All eight counterbalanced rounds remain separate; inclusive API/SQL latency categories must not be summed. '
              'Original Reader fingerprints are independently replayed. Full-input and all-encoded-pair digests are '
              'source-bound producer observations compared across rounds; discarded image bytes cannot be replayed. '
              'Observed boundary storage maxima do not establish continuous transient peaks or an OS quota. '
              'Abrupt-process recovery fixtures do not certify power-loss behavior or production adoption.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'evidence', 'queue-receipt', 'snapshot', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Assessment output already exists; refusing overwrite')
    require(not args.output.resolve().is_relative_to(args.evidence.resolve()), 'Assessment must be outside immutable evidence')
    value = evaluate(args.manifest, args.evidence, args.queue_receipt, args.snapshot)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps(dict(run_id=value['run_id'], mechanical_feasibility_passed=value['mechanical_feasibility_passed'],
                         failed_checks=[name for name, passed in value['checks'].items() if not passed])))


if __name__ == '__main__':
    main()
