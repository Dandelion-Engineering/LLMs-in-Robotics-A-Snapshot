"""Queue-only storage inventory of completed development bundles; no edits to evidence."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import stat
import sys

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parents[1]
RUNTIME = EXPERIMENT / 'Runtime'
MIB = 1024 ** 2
GIB = 1024 ** 3


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_stat(path):
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, 'st_file_attributes', 0) & 0x400:
        raise ValueError('Symlink/reparse path in evidence inventory: ' + str(path))
    return metadata


def checked_path(path, *, missing=False):
    """Check lexical ancestors before resolve can hide a junction or symlink."""
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Require an absolute local evidence path')
    for current in reversed((path, *path.parents)):
        try:
            checked_stat(current)
        except FileNotFoundError:
            if not missing:
                raise
    return path.resolve()


def inventory(root):
    """Retain sizes and relative identities; do not read or hash bulk frame bytes."""
    root = checked_path(root)
    rows = []
    pending = [root]
    while pending:
        directory = checked_path(pending.pop())
        for path in sorted(directory.iterdir()):
            metadata = checked_stat(path)
            if stat.S_ISDIR(metadata.st_mode):
                pending.append(path)
            elif stat.S_ISREG(metadata.st_mode):
                rows.append({'path': path.relative_to(root).as_posix(),
                             'bytes': metadata.st_size, 'mtime_ns': metadata.st_mtime_ns})
            else:
                raise ValueError('Unsupported evidence filesystem entry: ' + str(path))
    return sorted(rows, key=lambda row: row['path'])


def runtime_modules():
    if str(RUNTIME) not in sys.path:
        sys.path.insert(0, str(RUNTIME))
    import release_runner
    import record_attempt
    import development_storage
    return release_runner, record_attempt, development_storage


def registered_bundles(recorder, storage_api):
    """Discover only immutable registered development locations, never scan D."""
    checked_path(recorder.MAP)
    for name in recorder.am.KINDS.values():
        checked_path(recorder.MAP / name)
    data, raw, errors = recorder.am.read_store(recorder.MAP)
    if errors:
        raise ValueError('Cannot inventory an invalid registration store: ' + str(errors))
    runs = data['run']
    identities = [row['id'] for row in runs]
    if len(identities) != len(set(identities)):
        raise ValueError('Duplicate registered run identity')
    result_ids = [row['id'] for row in data['result']]
    if len(result_ids) != len(set(result_ids)):
        raise ValueError('Duplicate registered result identity')
    map_refs = [{'path': str((recorder.MAP / name).resolve()), 'sha256': hashlib.sha256(payload).hexdigest()}
                for name, payload in sorted(raw.items())]
    bundles, roots = [], set()
    for run in sorted(runs, key=lambda row: row['id']):
        if run.get('stage') != 'development':
            continue
        identity = recorder.safe_run_id(run['id'])
        registration_path = checked_path(recorder.MAP / 'releases' / identity / 'manifest.json')
        registration_bytes = registration_path.read_bytes()
        declaration = json.loads(registration_bytes)
        declared_storage = declaration.get('development_storage')
        if 'development_storage' not in declaration:
            checked_path(storage_api.DEFAULT_RAW_ROOT, missing=True)
        elif isinstance(declared_storage, dict) and isinstance(declared_storage.get('raw_root'), str):
            checked_path(declared_storage['raw_root'], missing=True)
        storage, legacy, registration = recorder.registered_storage(identity)
        if (Path(registration['path']) != registration_path
                or hashlib.sha256(registration_bytes).hexdigest() != registration['sha256']):
            raise ValueError('Registered manifest path or bytes changed')
        root = checked_path(storage['evidence_dir'], missing=True)
        if root in roots or root.name != identity or root.parent != Path(storage['raw_root']):
            raise ValueError('Duplicate or mismatched registered raw path')
        roots.add(root)
        bundles.append({'run_id': identity, 'root': root, 'storage': storage,
                        'legacy': legacy, 'registration_manifest': registration,
                        'result_records': [row for row in data['result'] if row.get('run_id') == identity]})
    return bundles, map_refs


def result_bindings(assigned, result_path, result_hash, map_root):
    """Bind recorded raw references without interpreting corrected outcomes."""
    bindings = []
    for record in assigned['result_records']:
        for ref in record.get('evidence', []):
            if not isinstance(ref.get('uri'), str):
                continue
            path = map_root / ref['uri']
            if path.resolve() != result_path:
                continue
            checked_path(path)
            if ref.get('sha256') != result_hash or ref.get('state') != 'available':
                raise ValueError('Registered raw result reference differs: ' + record['id'])
            bindings.append({'result_record_id': record['id'], 'run_id': assigned['run_id'],
                             'reference': ref})
    if assigned['result_records'] and not bindings:
        raise ValueError('Registered result history lacks its exact raw result reference')
    return bindings


def measure(output):
    release_runner, recorder, storage_api = runtime_modules()
    ownership = release_runner.queued_job(expected_script=__file__)
    output = checked_path(Path(output).absolute(), missing=True)
    raw = (EXPERIMENT / 'Evidence' / 'raw').resolve()
    bundles, map_refs = registered_bundles(recorder, storage_api)
    protected = {raw, *(Path(item['storage']['raw_root']) for item in bundles), recorder.MAP.resolve()}
    if output.exists() or any(output == path or path in output.parents or output in path.parents for path in protected):
        raise ValueError('Require a fresh output outside original raw evidence')
    source_hash = digest(Path(__file__))
    dependencies = [Path(recorder.__file__), Path(storage_api.__file__), Path(recorder.am.__file__), Path(release_runner.__file__)]
    source_refs = [{'path': str(path.resolve()), 'sha256': digest(path)} for path in dependencies]
    output.mkdir(parents=True, exist_ok=False)
    rows, skipped = [], []
    for assigned in bundles:
        root = assigned['root']; identity = assigned['run_id']
        result_path = root / 'result.json'
        checked_path(result_path, missing=True)
        if root.exists() and not root.is_dir():
            raise ValueError('Registered evidence directory is not a directory: ' + str(root))
        if not result_path.exists():
            skipped.append({'run_id': identity, 'development_storage': assigned['storage'],
                            'reason': 'No completed raw result at the registered location'})
            continue
        if not result_path.is_file():
            raise ValueError('Registered result is not a regular file: ' + str(result_path))
        result_hash = digest(result_path)
        result = json.loads(result_path.read_text(encoding='utf-8'))
        recorder.verify_raw_identity(result, identity, assigned['storage'], assigned['legacy'])
        if result.get('execution_status') not in ('completed', 'failed', 'timed_out', 'aborted'):
            raise ValueError('Raw result is not terminal: ' + str(result_path))
        bindings = result_bindings(assigned, result_path, result_hash, recorder.MAP)
        manifest_path = checked_path(root / 'manifest.json', missing=True)
        manifest_hash = None
        if manifest_path.exists():
            manifest_hash = digest(manifest_path)
            recorder.verify_raw_identity(json.loads(manifest_path.read_text(encoding='utf-8')),
                                         identity, assigned['storage'], assigned['legacy'])
        seconds = result.get('wall_duration_s')
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0:
            raise ValueError('Completed result has no positive measured duration: ' + str(result_path))
        files = inventory(root)
        if (digest(result_path) != result_hash or inventory(root) != files
                or (manifest_hash is not None and digest(manifest_path) != manifest_hash)):
            raise ValueError('Evidence metadata changed during inventory: ' + str(root))
        total = sum(row['bytes'] for row in files)
        index_path = output / (root.name + '-files.json')
        index_path.write_text(json.dumps({'root': str(root), 'files': files}, indent=2) + '\n', encoding='utf-8')
        rows.append({'run_id': identity, 'result': {'path': str(result_path), 'sha256': result_hash},
                     'result_run_id': result['run_id'], 'result_stage': result.get('stage'),
                     'raw_execution_status': result['execution_status'],
                     'registered_raw_result_bindings': bindings,
                     'map_result_binding_state': 'bound' if bindings else 'no_result_record_yet',
                     'development_storage': assigned['storage'], 'registration_manifest': assigned['registration_manifest'],
                     'legacy_missing_raw_stage': assigned['legacy'] and result.get('stage') is None,
                     'raw_manifest': None if manifest_hash is None else {'path': str(manifest_path), 'sha256': manifest_hash},
                     'outcome_as_recorded': result.get('outcome'),
                     'validity_as_recorded': result.get('validity'),
                     'wall_duration_s': seconds, 'retained_bytes': total, 'file_count': len(files),
                     'mib_per_task_second': total / MIB / seconds,
                     'file_inventory': {'path': str(index_path), 'sha256': digest(index_path)}})
    if not rows or digest(Path(__file__)) != source_hash:
        raise ValueError('No completed bundles or measurement source changed')
    registration_refs = [item['registration_manifest'] for item in bundles]
    for reference in map_refs + source_refs + registration_refs:
        path = checked_path(reference['path'])
        if digest(path) != reference['sha256']:
            raise ValueError('Registration or source identity changed during inventory: ' + str(path))
    maximum_rate = max(row['mib_per_task_second'] for row in rows)
    planning_rate = max(3.0, maximum_rate)
    remaining_max_seconds = 156600
    reserve_bytes = 50 * GIB
    free_bytes = shutil.disk_usage(EXPERIMENT).free
    required_bytes = math.ceil(planning_rate * MIB * remaining_max_seconds) + reserve_bytes
    summary = {'schema_version': 'robot-retention-inventory-1.0',
               'captured_at': datetime.now(timezone.utc).isoformat(),
               'derivation_queue_job_id': ownership['id'],
               'measurement_source': {'path': str(Path(__file__)), 'sha256': source_hash},
               'scope': 'Completed registered development raw bundles at exact pinned local locations, including failures; storage accounting only',
               'registered_without_completed_result': skipped,
               'registration_store_refs': map_refs, 'measurement_dependency_refs': source_refs,
               'capacity_volume_scope': 'Experiment/project volume only; alternate development storage grants no scored-storage authority',
               'capacity_path': str(EXPERIMENT.resolve()),
               'runs': rows, 'total_bytes': sum(row['retained_bytes'] for row in rows),
               'maximum_measured_mib_per_task_second': maximum_rate,
               'planning_rate_mib_per_task_second': planning_rate,
               'full_unstarted_release_maximum_task_seconds': remaining_max_seconds,
               'reserve_bytes': reserve_bytes, 'free_bytes': free_bytes,
               'full_release_planning_requirement_bytes': required_bytes,
               'current_headroom_satisfies_planning_estimate': free_bytes >= required_bytes,
               'limitations': ['Byte counts use stable file metadata, not a fresh hash of every frame',
                              'Raw historical outcome labels are not canonical corrected scientific results',
                              'Unregistered folders and non-development runs are not inventory inputs; no scored D-drive support is added',
                              'No claim that observed or planning rates bound future storage',
                              'Source archives, calibration and future derivatives are covered only by the explicit reserve',
                              'Recheck available capacity before each evaluation batch',
                              'Official completion receipt for this measurement is required separately']}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in summary.items() if key not in ('runs', 'limitations')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    measure(parser.parse_args().output)
