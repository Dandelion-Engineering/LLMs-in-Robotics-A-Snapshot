"""Queue-only metadata/source accounting after the fixed A3 environment pair.

This never launches experiments, finalizes results, opens concealed evaluation
manifests, reads raw evidence, or makes a selection/readiness decision.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import zipfile

HERE = Path(__file__).resolve().parent
REPAIR = HERE.parent
BATCH = REPAIR.parent
EXP = BATCH.parent
RUNTIME = EXP / 'Runtime'
MAP = EXP / 'Architecture Map'
COLLECTOR = BATCH / 'Release Analysis 003' / 'collect_results.py'
PRIOR = BATCH / 'selection-evidence-final-001'
EXPECTED = {kind: [f'B01-dev-{kind}-{n:03}' for n in range(1, count + 1)]
            for kind, count in {'C0': 13, 'A1': 6, 'A2': 4, 'A3': 8}.items()}
RETIRED = ['batch01-eval-r1-C24-rep2-A1-persistent',
           'batch01-eval-r2-C24-rep2-A1-persistent']
TERMINAL = {'completed', 'failed', 'timed_out', 'aborted'}
KINDS = {'architecture': 'architectures.jsonl', 'revision': 'revisions.jsonl',
         'run': 'runs.jsonl', 'result': 'results.jsonl', 'note': 'notes.jsonl'}


def now():
    return datetime.now(timezone.utc).isoformat()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


class Inputs:
    """Only explicit metadata/source inputs; no recursive reference following."""
    def __init__(self):
        self.checked = {}

    def read(self, path):
        path = Path(path).resolve()
        payload = path.read_bytes()
        value = {'path': str(path), 'sha256': sha(payload), 'bytes': len(payload)}
        require(path not in self.checked or self.checked[path] == value,
                'Input changed while reading: ' + str(path))
        self.checked[path] = value
        return payload, dict(value)

    def copy(self, source, destination):
        payload, value = self.read(source)
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            stream.write(payload)
        require(destination.read_bytes() == payload, 'Snapshot copy differs')
        return {'source_path': value['path'], 'snapshot_path': str(destination),
                'sha256': value['sha256'], 'bytes': value['bytes']}

    def verify(self):
        for path, before in self.checked.items():
            after = path.read_bytes()
            require(len(after) == before['bytes'] and sha(after) == before['sha256'],
                    'Input changed during snapshot: ' + str(path))


def bound(refs, path, digest):
    matches = [ref for ref in refs if isinstance(ref, dict)
               and isinstance(ref.get('uri'), str)
               and (MAP / ref['uri']).resolve() == path.resolve()
               and ref.get('sha256') == digest and ref.get('state') == 'available']
    require(len(matches) == 1, 'Expected one exact canonical source binding: ' + str(path))


def raw_result_refs(history):
    # Preserve canonical assertions only. Deliberately do not open these paths.
    result = []
    for row in history:
        for ref in row.get('evidence', []):
            if isinstance(ref.get('uri'), str) and ref['uri'].replace('\\', '/').split('/')[-1] == 'result.json':
                result.append({'result_record_id': row['id'], 'reference': ref,
                               'verification': 'canonical metadata only; raw file not opened'})
    return result


def history_order(current, history):
    by_id = {row['id']: row for row in history}
    ordered = []
    while current is not None:
        ordered.append(current['id'])
        current = by_id.get(current.get('supersedes_result_id'))
    return list(reversed(ordered))


def snapshot(output, job):
    started = now()
    inputs = Inputs()
    source_refs = []
    sources = [(MAP / 'map.py', 'map.py'), (MAP / 'Schema.md', 'map-schema.md'),
               (COLLECTOR, 'collect_results.py'), (Path(__file__), 'snapshot_selection.py'),
               (HERE / 'README.md', 'snapshot-instructions.md'),
               (PRIOR / 'accounting.json', 'prior-accounting.json'),
               (PRIOR / 'snapshot-files.json', 'prior-snapshot-files.json'),
               (BATCH / 'development-opportunity-extension-001.json', 'development-opportunity-extension-001.json'),
               (BATCH / 'Release Infrastructure Repair 001' / 'retirement-r1-and-r2-decision-001.json', 'retirement-r1-and-r2-decision-001.json'),
               (REPAIR / 'retirement-r2-and-r3-decision-001.json', 'retirement-r2-and-r3-decision-001.json'),
               (REPAIR / 'validation-tools' / 'A3-environment-revalidation-plan.json', 'A3-environment-revalidation-plan.json'),
               (REPAIR / 'validation-tools' / 'run_environment_pair.py', 'run_environment_pair.py')]
    for source, name in sources:
        source_refs.append(inputs.copy(source, output / 'source-reference' / name))

    # Execute exactly the source function used by Release Analysis 003, without
    # importing its module (which would pull in the evaluation runner).
    collector_bytes, collector_ref = inputs.read(COLLECTOR)
    tree = ast.parse(collector_bytes.decode('utf-8-sig'), filename=str(COLLECTOR))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == 'current_result']
    require(len(functions) == 1, 'Ambiguous canonical selection function')
    namespace = {}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(COLLECTOR), 'exec'), namespace)
    current_result = namespace['current_result']

    spec = importlib.util.spec_from_file_location('snapshot_architecture_map', MAP / 'map.py')
    am = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(am)
    data, raw, errors = am.read_store(MAP)
    require(not errors, 'Canonical store parse errors: ' + repr(errors))
    canonical = []
    for kind, name in KINDS.items():
        payload, _ = inputs.read(MAP / name)
        require(payload == raw[name], 'Canonical input changed during initial read')
        prior_bytes, _ = inputs.read(PRIOR / 'canonical' / name)
        require(payload.startswith(prior_bytes), 'Historical canonical bytes no longer form unchanged prefix: ' + name)
        canonical.append({'name': name, 'records': len(data[kind]),
                          **inputs.copy(MAP / name, output / 'canonical' / name)})
    all_ids = [row['id'] for rows in data.values() for row in rows]
    require(len(all_ids) == len(set(all_ids)), 'Duplicate canonical record identity')
    runs = {row['id']: row for row in data['run']}
    revisions = {row['id']: row for row in data['revision']}
    require(all(row.get('run_id') in runs for row in data['result']), 'Result without registered run')
    require(all(row.get('revision_id') in revisions for row in data['run']), 'Run without registered revision')
    expected = {run_id for ids in EXPECTED.values() for run_id in ids}
    dev_ids = {row['id'] for row in data['run'] if row.get('stage') == 'development'}
    eval_ids = {row['id'] for row in data['run'] if row.get('stage') == 'evaluation'}
    require(dev_ids == expected, 'Need exactly the 31 planned development registrations, including A3-007/008')
    require(eval_ids == set(RETIRED), 'Unexpected evaluation registrations; this r3 snapshot plan needs review')
    require(set(runs) == expected | set(RETIRED), 'Unexpected registered stage; preserve and review before snapshot')
    dev_results = [row for row in data['result'] if row['run_id'] in expected]
    require(len(dev_results) == 32, 'Need 32 development result records, preserving the C0 correction')
    selected = {}
    histories = {}
    for run_id in runs:
        selected[run_id], histories[run_id] = current_result(data['result'], run_id)
        require(selected[run_id].get('execution_status') in TERMINAL,
                'Unrun or nonterminal attempt cannot satisfy snapshot: ' + run_id)

    runtime_paths = sorted(RUNTIME.glob('*.py'))
    require(runtime_paths, 'Missing current Runtime source files')
    current_runtime = [inputs.copy(path, output / 'current-runtime' / path.name)
                       for path in runtime_paths]
    runtime_hashes = {Path(ref['source_path']).name: ref['sha256'] for ref in current_runtime}
    attempts = []
    for entrant, run_ids in EXPECTED.items():
        for run_id in run_ids:
            run = runs[run_id]
            revision = revisions[run['revision_id']]
            require(revision['architecture_id'] == 'B01-' + entrant, 'Entrant/revision mismatch')
            manifest_path = MAP / 'releases' / run_id / 'manifest.json'
            archive_path = manifest_path.with_name('runtime.zip')
            manifest_bytes, manifest_ref = inputs.read(manifest_path)
            archive_bytes, archive_ref = inputs.read(archive_path)
            for ref, key in [(manifest_ref, 'protocol'), (archive_ref, 'code')]:
                bound(run.get('frozen_refs', {}).get(key, {}).get('refs', []), Path(ref['path']), ref['sha256'])
                bound(revision.get('attachments', []), Path(ref['path']), ref['sha256'])
            manifest = am.strict_json(manifest_bytes.decode('utf-8'))
            require(manifest.get('run_id') == run_id, 'Development manifest run mismatch')
            declared = manifest.get('runtime_files')
            require(isinstance(declared, dict) and declared, 'Missing historical source inventory')
            require(all(Path(name).name == name and name.endswith('.py') for name in declared), 'Unexpected ZIP member name')
            # Use the very bytes whose hash was canonically bound, not a reopened ZIP.
            import io
            with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
                names = archive.namelist()
                require(len(names) == len(set(names)) and set(names) == set(declared), 'ZIP inventory differs from manifest')
                for name, expected_hash in declared.items():
                    require(sha(archive.read(name)) == expected_hash, 'Historical ZIP member differs: ' + run_id + '/' + name)
            copied_manifest = inputs.copy(manifest_path, output / 'attempt-manifests' / (run_id + '.json'))
            current = selected[run_id]
            history = histories[run_id]
            attempts.append({
                'run_id': run_id, 'entrant': entrant, 'architecture_id': revision['architecture_id'],
                'revision_id': revision['id'], 'parent_revision_id': revision.get('parent_revision_id'),
                'revision_status': revision['status'], 'condition_id': run['condition_id'],
                'scenario_id': run['scenario_id'], 'condition_details': run['condition_details'],
                'run_recorded_at': run['recorded_at'],
                'purpose': 'post-closure common environment revalidation; no tuning' if run_id in EXPECTED['A3'][-2:] else 'retained original development',
                'canonical_current_result_id': current['id'], 'current_result': current,
                'result_history_oldest_to_current': history_order(current, history),
                'supersession_edges': [{'result_id': row['id'], 'supersedes_result_id': row.get('supersedes_result_id')} for row in history],
                'raw_result_refs': raw_result_refs(history),
                'manifest': {'path': manifest_ref['path'], **copied_manifest},
                'source_zip': {**archive_ref, 'all_manifest_member_hashes_verified': True, 'members': len(declared), 'copied': False},
                'historical_runtime_file_sha256': declared,
                'current_source_comparison': {
                    'same_named_files_differing': sorted(name for name in declared.keys() & runtime_hashes.keys() if declared[name] != runtime_hashes[name]),
                    'current_only_files': sorted(runtime_hashes.keys() - declared.keys()),
                    'historical_only_files': sorted(declared.keys() - runtime_hashes.keys()),
                    'candidates_py_matches_current': declared.get('candidates.py') == runtime_hashes.get('candidates.py'),
                    'limitation': 'Descriptive byte comparison; no checkpoint selection or historical rerun.'}})

    entrants = {}
    for entrant, ids in EXPECTED.items():
        rows = [row for row in attempts if row['entrant'] == entrant]
        record_ids = [row['id'] for row in dev_results if row['run_id'] in ids]
        current_ids = [selected[run_id]['id'] for run_id in ids]
        revision_ids = [row['id'] for row in data['revision'] if row.get('architecture_id') == 'B01-' + entrant]
        entrants[entrant] = {
            'architecture_id': 'B01-' + entrant, 'attempt_ids': ids,
            'attempt_count': len(ids), 'terminal_attempt_count': len(ids), 'result_record_count': len(record_ids),
            'episode_ceiling': 60, 'remaining_of_60': 60 - len(ids), 'remaining_episode_allowance': 60 - len(ids),
            'canonical_current_result_ids': current_ids, 'all_result_record_ids': record_ids,
            'superseded_result_ids': [record_id for record_id in record_ids if record_id not in current_ids],
            'revision_ids': revision_ids, 'revision_record_count': len(revision_ids),
            'development_revision_ids': [row['revision_id'] for row in rows],
            'development_revision_count': len({row['revision_id'] for row in rows}),
            'current_validity_counts': dict(Counter(selected[run_id]['validity'] for run_id in ids)),
            'current_outcome_counts': dict(Counter(selected[run_id]['outcome'] for run_id in ids))}

    # Check every metadata/source/archive input and Runtime membership before
    # publishing a complete accounting record. Failed partial folders are kept.
    require(sorted(RUNTIME.glob('*.py')) == runtime_paths, 'Runtime source inventory changed')
    inputs.verify()
    accounting = {
        'schema_version': 'development-selection-evidence-2', 'status': 'complete_non_authorizing',
        'queue_job_id': job['id'], 'snapshot_started_at_utc': started, 'snapshot_verified_at_utc': now(),
        'original_map_root': str(MAP),
        'canonical_uri_resolution': 'Original canonical URI strings resolve relative to original_map_root, not the copied canonical directory.',
        'counts': {'architectures': len(data['architecture']), 'revisions': len(data['revision']),
                   'registered_attempts': len(runs), 'terminal_attempts': len(selected),
                   'result_records': len(data['result']), 'canonical_current_results': len(selected),
                   'superseded_result_records': len(data['result']) - len(selected), 'notes': len(data['note'])},
        'development': {'attempt_count': len(expected), 'terminal_attempt_count': len(expected),
                        'result_record_count': len(dev_results), 'attempt_ids': sorted(expected),
                        'post_closure_infrastructure_attempt_ids': EXPECTED['A3'][-2:],
                        'superseded_result_record_count': len(dev_results) - len(expected)},
        'retired_evaluation': {'excluded_from_development_accounting': True, 'excluded_from_r3_inference': True,
                               'attempt_count': len(RETIRED), 'attempt_ids': RETIRED,
                               'attempts': [{'run_id': rid, 'revision_id': runs[rid]['revision_id'],
                                             'current_result': selected[rid],
                                             'result_history_oldest_to_current': history_order(selected[rid], histories[rid]),
                                             'raw_result_refs': raw_result_refs(histories[rid])} for rid in RETIRED],
                               'unlaunched_disposition': 'Retirement documents preserve each original schedule; unlaunched members are not fabricated results.'},
        'canonical_store_sha256': am.store_digest(raw), 'canonical_files': canonical,
        'canonical_store_unchanged_before_after': True, 'source_files_unchanged_before_after': True,
        'historical_canonical_prefix_preserved': True,
        'canonical_selection_semantics': {'source': collector_ref, 'function': 'current_result',
                                         'execution': 'Exact AST function from the retained source; no alternate selection logic'},
        'source_references': source_refs, 'verified_input_files': list(inputs.checked.values()),
        'entrants': entrants, 'attempts': attempts,
        'current_runtime_files': runtime_hashes, 'current_runtime': current_runtime,
        'history_and_limits': {'active_engineering_hours': None, 'measurement_state': 'unmeasured',
                               'original_active_engineering_hour_ceiling': 12, 'original_time_ceiling_compliance': 'unknown',
                               'equal_realized_effort_claimed': False, 'ledger_included': False,
                               'ledger_reason': 'Root binds the final opportunity ledger separately.',
                               'raw_evidence_verified': False, 'model_assets_verified': False,
                               'qualification_granted': False, 'scored_ready': False,
                               'selection_decision_created': False, 'selected_checkpoints': None,
                               'historical_results_preserved': True,
                               'limitation': 'Metadata/source accounting only. No validity upgrade, winner selection, concealed seed access, or freeze.'}}
    write(output / 'accounting.json', accounting)
    files = []
    for path in sorted(output.rglob('*')):
        if path.is_file():
            payload = path.read_bytes()
            files.append({'path': str(path), 'relative_path': path.relative_to(output).as_posix(),
                          'sha256': sha(payload), 'bytes': len(payload)})
    write(output / 'snapshot-files.json', {'schema_version': 'selection-evidence-files-1',
                                          'created_at_utc': now(), 'queue_job_id': job['id'], 'files': files})
    return {'status': accounting['status'], 'queue_job_id': job['id'], 'output': str(output),
            'development_attempts': len(expected), 'development_result_records': len(dev_results),
            'retired_evaluation_attempts': len(RETIRED), 'files': len(files),
            'accounting_sha256': sha((output / 'accounting.json').read_bytes())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=BATCH / 'selection-evidence-r3-001')
    args = parser.parse_args()
    sys.path.insert(0, str(RUNTIME))
    import release_runner
    job = release_runner.queued_job(expected_script=__file__)
    output = args.output.resolve()
    require(output.is_relative_to(BATCH.resolve()) and output.parent == BATCH.resolve(),
            'Use a fresh direct Batch 01 child directory')
    require(not output.exists(), 'Snapshot output already exists; never overwrite evidence')
    output.mkdir()
    try:
        print(json.dumps(snapshot(output, job), allow_nan=False))
    except BaseException as exc:
        write(output / 'snapshot-failure.json', {'status': 'failed', 'queue_job_id': job['id'],
                                                 'recorded_at_utc': now(), 'error': type(exc).__name__ + ': ' + str(exc),
                                                 'partial_evidence_preserved': True})
        raise


if __name__ == '__main__':
    main()
