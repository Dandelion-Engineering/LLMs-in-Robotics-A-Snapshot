"""Queued preparation and validation of an explicit administrative annex.

prepare creates prospective records only. validate cannot execute an episode.
Adoption is a separate root decision after the official validation receipt.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import importlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import recovery_contract as contract

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
ORIGINAL = EXPERIMENT / 'Runtime 004'
ROOT = EXPERIMENT.parent
sys.path.insert(0, str(ORIGINAL))
import release_runner as original


def utc():
    return datetime.now(timezone.utc).isoformat()


def old_collector():
    path = EXPERIMENT / 'Batch 01' / 'Release Analysis 004' / 'collect_results.py'
    spec = importlib.util.spec_from_file_location('_recovery_original_collector', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def canonical_records(kind):
    path = EXPERIMENT / 'Architecture Map' / (kind + 's.jsonl')
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def queued_identity():
    # New runner supplies the delete-sharing reader; original remains unchanged.
    import recovery_runner
    return recovery_runner.queued_job(HERE / 'prepare_recovery.py')


def prepare(release_dir, output, source_review):
    job = queued_identity(); output = output.resolve()
    contract.require(not output.exists(), 'Preparation output must be fresh')
    output.mkdir(parents=True)
    verified = original.verify_release(release_dir)
    contract.require(verified['release_sha256'] == contract.RELEASE_HASH, 'Wrong r4 release')
    root = verified['root']; release_ref = contract.ref(root / 'release.json')
    release = verified['release']; schedule = sorted(release['manifest_refs'], key=lambda r: r['scheduled_index'])
    by_id = {r['run_id']: {'path': str((root / r['path']).resolve()), 'sha256': r['sha256']} for r in schedule}
    records = canonical_records('result'); runs = {r['id']: r for r in canonical_records('run')}
    collector = old_collector(); retained = []; remaining = []
    selected = collector.collect(root, records)
    contract.require(selected['counts'] == {'planned': 264, 'selected_terminal': 132, 'missing_terminal': 132},
                     'Original collector accounting differs from reviewed interruption')
    for entry in schedule:
        rid = entry['run_id']; attempt = root / 'attempts' / rid
        if (attempt / 'terminal.json').is_file():
            terminal, provenance = collector.verified_terminal(root, rid, release_ref['sha256'], entry['sha256'])
            result, history = collector.current_result(records, rid)
            contract.require(len(history) == 1, 'Original result correction requires fresh assessment')
            batch = root / 'batches' / terminal['queue_job_id']
            protected = [contract.ref(attempt / name) for name in ('claimed.json', 'registered.json', 'started.json')]
            protected += [contract.ref(batch / name) for name in ('planned.json', 'finished.json', 'finalized.json', 'official-queue-status.json')]
            if terminal.get('supervisor_result_ref'):
                protected.append(contract.ref(original.reference(terminal['supervisor_result_ref'], attempt)))
            retained.append({'run_id': rid, 'manifest_ref': by_id[rid], 'terminal_ref': contract.ref(attempt / 'terminal.json'),
                'protected_refs': protected, 'canonical_result_sha256': contract.semantic_hash(result),
                'canonical_run_sha256': contract.semantic_hash(runs[rid])})
        elif rid != contract.ADMIN_RUN:
            contract.require(not attempt.exists() and rid not in runs, 'Remaining original already claimed/registered')
            contract.require(not (EXPERIMENT / 'Evidence' / 'raw' / rid).exists(), 'Remaining original has raw evidence')
            remaining.append({'run_id': rid, 'manifest_ref': by_id[rid]})
    contract.require(len(retained) == 132 and len(remaining) == 131, 'Unexpected original partition')
    raw_root = root / 'attempts' / contract.ADMIN_RUN / 'evidence'
    contract.require(raw_root.is_dir() and not (raw_root / 'result.json').exists(), 'Interrupted raw disposition differs')
    inventory = {'schema_version': 'partial-interrupted-evidence-inventory-1', 'run_id': contract.ADMIN_RUN,
                 'root': str(raw_root), 'recorded_at': utc(), 'queue_job_id': job['id'],
                 'complete_raw_result_present': False,
                 'files': [{**contract.ref(path), 'bytes': path.stat().st_size} for path in sorted(raw_root.rglob('*')) if path.is_file()]}
    original.write_once(output / 'partial-evidence-inventory.json', inventory)
    incident = EXPERIMENT / 'Evidence' / 'diagnostics' / 'r4-queue-worker-loss-001'
    receipt_path = EXPERIMENT / 'Evidence' / 'queue-receipts' / (contract.ADMIN_BATCH + '.json')
    receipt = contract.read(receipt_path); attempt = root / 'attempts' / contract.ADMIN_RUN
    disposition = {'schema_version': 'administrative-interruption-1', 'annex_id': contract.ANNEX_ID,
        'run_id': contract.ADMIN_RUN, 'release': release_ref, 'manifest': by_id[contract.ADMIN_RUN],
        'original_queue_job_id': contract.ADMIN_BATCH, 'official_receipt': contract.ref(receipt_path),
        'execution_disposition': 'interrupted', 'validity': 'invalid', 'invalidity_class': 'infrastructure',
        'task_outcome': 'unknown', 'physical_ended_at': None, 'administratively_recorded_at': utc(),
        'queue_reconciled_at': receipt['ended_at'], 'post_run_integrity': {'state': 'missing'},
        'supervisor_terminal': {'state': 'missing'}, 'metrics': {},
        'canonical_run_sha256': contract.semantic_hash(runs[contract.ADMIN_RUN]),
        'partial_evidence_inventory': contract.ref(output / 'partial-evidence-inventory.json'),
        'evidence': [contract.ref(attempt / name) for name in ('claimed.json', 'registered.json', 'started.json')]
            + [contract.ref(root / 'batches' / contract.ADMIN_BATCH / 'planned.json'), contract.ref(incident / 'incident.json'),
               contract.ref(attempt / 'model-server.log')],
        'interpretation': 'Administrative infrastructure interruption, not a measured task failure or successful terminal. '
            'Queue reconciliation time is not the physical end. Historical post-run integrity is unknown. '
            'Keep C24 replicate 2 excluded as already specified; never rerun this attempt.'}
    original.write_once(output / 'administrative-interruption.json', disposition)
    sources = sorted(HERE.glob('*.py'))
    with zipfile.ZipFile(output / 'administration.zip', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sources:
            archive.write(path, path.name)
    source_index = {'schema_version': 'recovery-source-index-1', 'runtime_root': str(HERE),
        'files': [{**contract.ref(path), 'archive_path': path.name} for path in sources],
        'bundle': contract.ref(output / 'administration.zip')}
    original.write_once(output / 'administration-index.json', source_index)
    analysis_root = EXPERIMENT / 'Batch 01' / 'Release Analysis 005'
    original.write_once(output / 'analysis-index.json', {'schema_version': 'recovery-analysis-source-index-1',
        'root': str(analysis_root), 'files': [contract.ref(p) for p in sorted(analysis_root.rglob('*')) if p.is_file()]})
    revisions = {r['id']: r for r in canonical_records('revision')}
    parents = {a: 'batch01-eval-r4-' + a + '-frozen' for a in ('baseline', 'A1', 'A2', 'A3')}
    annex = {'schema_version': contract.SCHEMA, 'annex_id': contract.ANNEX_ID, 'status': 'prepared',
        'created_at': utc(), 'preparation_queue_job_id': job['id'], 'release': release_ref,
        'original_runtime_root': str(ORIGINAL), 'installed_queue': contract.ref(original.QUEUE_HOME / 'compute_queue.py'),
        'queue_repair_verification': contract.ref(incident / 'queue-fix-proposal' / 'installation-001' / 'verification.json'),
        'serialized_read_decision': contract.ref(output.parent / 'serialized-ownership-read-decision.json'),
        'superseded_failed_validation': contract.ref(output.parent / 'validation-001' / 'failure.json'),
        'source_index': contract.ref(output / 'administration-index.json'), 'source_change_review': contract.ref(source_review),
        'analysis_source_index': contract.ref(output / 'analysis-index.json'),
        'retained_originals': retained, 'remaining_originals': remaining,
        'administrative_dispositions': [{'run_id': contract.ADMIN_RUN,
            'disposition_ref': contract.ref(output / 'administrative-interruption.json'),
            'expected_canonical_note_id': contract.ADMIN_RUN + '-administrative-interruption-001'}],
        'administrative_batch_ids': [contract.ADMIN_BATCH],
        'revision_ids': {a: contract.ANNEX_ID + '-' + a for a in parents}, 'parent_revision_ids': parents,
        'protected_canonical_revisions': [{'id': rid, 'sha256': contract.semantic_hash(revisions[rid])} for rid in parents.values()],
        'original_reviews': [contract.ref(path) for path in sorted((root / 'reviews').glob('*.json'))],
        'invariants': {'automatic_retries': 0, 'bootstrap_draws': 2000, 'bootstrap_seed': 0,
            'policy_physics_model_budgets_scoring_unchanged': True, 'stored_order_preserved': True,
            'fixed_trace_count': 12, 'administrative_outcome': 'unknown'}}
    original.write_once(output / 'prepared-annex.json', annex)
    contract.verify_annex(output / 'prepared-annex.json', root, require_adopted=False)
    original.write_once(output / 'preparation.json', {'queue_job_id': job['id'], 'prepared_annex': contract.ref(output / 'prepared-annex.json'),
        'retained': 132, 'administrative': 1, 'untouched': 131, 'policy_episode_launched': False})
    return {'prepared_annex': str(output / 'prepared-annex.json'), 'counts': [132, 1, 131]}


def validate(annex_path, output):
    job = queued_identity(); output = output.resolve()
    contract.require(not output.exists(), 'Validation output must be fresh')
    output.mkdir(parents=True)
    checked = contract.verify_annex(annex_path, require_adopted=False); annex = checked['annex']
    original.verify_release(checked['root'])
    for disposition in checked['dispositions'].values():
        contract.verify_partial_inventory(disposition)
    source_review = contract.read(contract.reference(annex['source_change_review']))
    contract.require(source_review.get('reviewed') is True and source_review.get('scope') == 'authority-and-provenance-only',
                     'Root source change review missing')
    contract.require(source_review.get('original_supervisor') == contract.ref(ORIGINAL / 'experiment.py')
                     and source_review.get('recovery_supervisor') == contract.ref(HERE / 'experiment_recovery.py'),
                     'Reviewed supervisor bytes differ')
    contract.reference(source_review['diff'])
    modules = ['cell', 'actuation', 'sandbox', 'model_runtime', 'initial_conditions', 'resources', 'scenarios',
               'sensors', 'evaluator', 'sensor_worker', 'restart_state', 'restart_physical_class',
               'restart_compatibility', 'restart_calibration_loader', 'candidates']
    locations = {}
    for name in modules:
        module = importlib.import_module(name); path = Path(module.__file__).resolve()
        contract.require(path == ORIGINAL / (name + '.py'), 'Relocated physical/policy dependency: ' + name)
        locations[name] = contract.ref(path)
    # candidate_worker uses Linux-only resource/seccomp inside WSL; never import
    # it on the Windows host. Original artifact/environment verification covers
    # its bytes and installed sandbox. The parent sandbox remains the original.
    locations['candidate_worker_source_not_host_imported'] = contract.ref(ORIGINAL / 'candidate_worker.py')
    # Import the actual recovery supervisor and check its class/source objects
    # resolve to those same modules. Importing does not start an episode/model.
    supervisor = importlib.import_module('experiment_recovery')
    import cell
    contract.require(supervisor.Cell is cell.Cell, 'Supervisor uses a different Cell class')
    original.write_once(output / 'module-locations.json', locations)
    analysis_path = EXPERIMENT / 'Batch 01' / 'Release Analysis 005' / 'collect_results.py'
    spec = importlib.util.spec_from_file_location('_preflight_analysis005', analysis_path)
    analysis005 = importlib.util.module_from_spec(spec); spec.loader.exec_module(analysis005)
    records = canonical_records('result')
    legacy_selected = old_collector().collect(checked['root'], records)
    administrative_reader_originals = analysis005.collect(checked['root'], records)
    contract.require(legacy_selected['results'] == administrative_reader_originals['results']
                     and len(legacy_selected['results']) == 132,
                     'Actual132 original selected results changed in new reader')
    original.write_once(output / 'retained-selection-differential.json', {
        'original_collector': contract.ref(EXPERIMENT / 'Batch 01' / 'Release Analysis 004' / 'collect_results.py'),
        'administrative_collector': contract.ref(analysis_path), 'exact_selected_results_equal': True,
        'count': 132, 'selected_results_semantic_sha256': contract.semantic_hash(legacy_selected['results'])})
    tests = [HERE, EXPERIMENT / 'Batch 01' / 'Release Analysis 005']
    executions = []
    for index, directory in enumerate(tests):
        cmd = [sys.executable, '-X', 'utf8', '-B', '-m', 'unittest', 'discover', '-s', str(directory), '-p', 'test_*.py', '-v']
        reply = subprocess.run(cmd, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               timeout=600, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        (output / ('tests-' + str(index) + '.stdout')).write_bytes(reply.stdout)
        (output / ('tests-' + str(index) + '.stderr')).write_bytes(reply.stderr)
        executions.append({'argv': cmd, 'exit_status': reply.returncode,
            'stdout': contract.ref(output / ('tests-' + str(index) + '.stdout')),
            'stderr': contract.ref(output / ('tests-' + str(index) + '.stderr'))})
        contract.require(reply.returncode == 0 and b'Ran 0 tests' not in reply.stderr,
                         'Recovery test suite failed; evidence retained')
    contract.verify_annex(annex_path, require_adopted=False)
    report = {'schema_version': 'administrative-recovery-preflight-1', 'recorded_at': utc(), 'queue_job_id': job['id'],
        'queued_argv': job['argv'], 'prepared_annex': contract.ref(annex_path), 'source_index': annex['source_index'],
        'analysis_source_index': annex['analysis_source_index'],
        'passed': True, 'checks': {'original_release_verified': True, 'same_physical_source_locations': True,
            'partial_inventory_verified': True, 'retained_originals_verified': True, 'source_diff_restricted': True,
            'retained_selection_exactly_equal': True, 'tests_passed': True}, 'executions': executions,
        'retained_selection_differential': contract.ref(output / 'retained-selection-differential.json'),
        'module_locations': contract.ref(output / 'module-locations.json'),
        'policy_episode_launched': False, 'limitation': 'No claim of repaired GPU sampler or measured historical physical end/post-check.'}
    original.write_once(output / 'validation.json', report)
    return {'passed': True, 'report': str(output / 'validation.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare'); prep.add_argument('--release-dir', type=Path, required=True)
    prep.add_argument('--output', type=Path, required=True); prep.add_argument('--source-review', type=Path, required=True)
    val = sub.add_parser('validate'); val.add_argument('--annex', type=Path, required=True); val.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = prepare(args.release_dir, args.output, args.source_review) if args.command == 'prepare' else validate(args.annex, args.output)
    print(json.dumps(value))


if __name__ == '__main__':
    main()
