"""Seal the documented infrastructure-only r2 replacement; never create seeds."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
BATCH = HERE.parent
EXP = BATCH.parent
RUNTIME = EXP / 'Runtime'
PREP = EXP / 'Evidence/prepared-artifacts/batch01-eval-r2-final'
RECEIPTS = EXP / 'Evidence/queue-receipts'
sys.path.insert(0, str(RUNTIME))
import release_runner as runner
import protocol


def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def ref(p):
    p = Path(p).resolve()
    return {'path': str(p), 'sha256': runner.digest(p)}
def write(p, value):
    with Path(p).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
def official(job):
    p = RECEIPTS / (job + '.json')
    r = load(p)
    if r['id'] != job or r['state'] != 'succeeded' or type(r['exit_status']) is not int or r['exit_status'] != 0:
        raise ValueError('Actual successful receipt required: ' + job)
    state = load(Path(r'C:\Users\cresp\Documents\Dandelion Engineering\tools\compute_queue\runtime\state.json'))
    records = [row for row in state['jobs'] if row['id'] == job]
    if len(records) != 1 or records[0] != r:
        raise ValueError('Receipt differs from installed queue record: ' + job)
    return ref(p)


def main(coordinator_receipt):
    job = runner.queued_job(Path(__file__))
    selected_path = BATCH / 'development-selection-decision-r2-001.json'
    index_path = BATCH / 'release-control-index-batch01-eval-r2.json'
    freeze_path = BATCH / 'freeze-batch01-eval-r2.json'
    ready_path = BATCH / 'readiness-batch01-eval-r2.json'
    ledger_path = BATCH / 'development-ledger-closed-r2-001.md'
    if any(p.exists() for p in (selected_path, index_path, freeze_path, ready_path, ledger_path)):
        raise ValueError('Fresh final outputs required')
    prepared = load(PREP / 'prepared-artifacts.json')
    receipts = [official(prepared['queue_job_id']), official('20260923T132041767539Z-187f08d1'),
                official('20260923T132316632997Z-6a1692c4'), official(coordinator_receipt)]
    validation_path = HERE / 'coordinator-validation-001.json'
    validation = load(validation_path)
    if validation['official_receipt'] != receipts[-1] or validation['all_required_checks_passed'] is not True:
        raise ValueError('Coordinator verification is not bound to the successful receipt')
    for source in validation['source_files']:
        if ref(source['path']) != source:
            raise ValueError('Coordinator/test/fixture changed since verification')
    runner.verify_artifacts(prepared, PREP / 'not-a-freeze.json')
    original = load(EXP / 'Evidence/prepared-artifacts/batch01-eval-r1-final/prepared-artifacts.json')
    if any(prepared[k] != original[k] for k in ('protocol_sha256', 'model_sha256', 'environment_sha256')):
        raise ValueError('Unexpected protocol/model/environment change')
    before = {p.name: runner.digest(p) for p in (BATCH / 'selection-evidence-final-001/current-runtime').glob('*.py')}
    after = {p.name: runner.digest(p) for p in RUNTIME.glob('*.py')}
    changed = sorted(k for k in before if before[k] != after.get(k))
    if changed != ['release_runner.py'] or set(after) - set(before) != {'test_release_entrypoint.py'}:
        raise ValueError('Unexpected Runtime change beyond the documented entrypoint/test')
    retirement = load(HERE / 'retirement-r1-and-r2-decision-001.json')
    for key in ('original_release', 'original_terminal', 'original_batch_finalization', 'original_runtime_zip', 'original_source_accounting'):
        if ref(retirement[key]['path']) != retirement[key]:
            raise ValueError('Retired release evidence changed: ' + key)
    retained = EXP / 'Evidence/derived/retention-development-final-001/summary.json'
    retention = load(retained)
    capacity = shutil.disk_usage(EXP).free
    if capacity < retention['full_release_planning_requirement_bytes']:
        raise ValueError('Insufficient current full-release capacity')
    now = datetime.now(timezone.utc).isoformat()
    selected = load(BATCH / 'development-selection-decision-001.json')
    selected.update(schema_version='batch01-development-selection-r2-1', recorded_at_utc=now, release_id='batch01-eval-r2',
                    predecessor_selection=ref(BATCH / 'development-selection-decision-001.json'),
                    release_supersession=ref(HERE / 'retirement-r1-and-r2-decision-001.json'),
                    decision='Retain all four previously selected mechanisms and the complete matrix; replace only the failed CLI authorization entrypoint and external orchestration/reader bindings under a fresh release',
                    changes_since_r1={'changed_runtime_files': changed, 'added_runtime_files': ['test_release_entrypoint.py'],
                                      'old_hashes': {k: before[k] for k in changed}, 'new_hashes': {k: after[k] for k in changed + ['test_release_entrypoint.py']},
                                      'physical_source_and_absolute_mesh_path_changed': False, 'candidate_or_model_tuning': False},
                    current_capacity={'path': str(EXP), 'free_bytes': capacity, 'full_release_requirement_bytes': retention['full_release_planning_requirement_bytes'], 'inventory': ref(retained)},
                    verification_receipts=receipts)
    for checkpoint in selected['selected_checkpoints']:
        checkpoint.update(final_code_index=prepared['artifacts']['code'], final_environment_index=prepared['artifacts']['environment'],
                          final_model_index=None if checkpoint['kind'] == 'baseline' else prepared['artifacts']['model'],
                          additional_common_change_after_r1='Canonical direct-script module alias plus regression; all physical/candidate/model/prompt bytes and location unchanged. 439 Runtime tests passed, including old-error reproduction and preserved forged-token/argument rejection. Historical episodes retain their original bytes.')
    selected['evidence_refs'] += [ref(PREP / 'prepared-artifacts.json'), *receipts]
    write(selected_path, selected)
    ledger = BATCH / 'Development Ledger.md'
    old = ledger.read_bytes()
    addition = ('\n\n## Infrastructure-only r2 selection — ' + now + '\n\nThe first r1 evaluation launch failed before physical or policy execution because direct-script and imported runner classes differed. Its failed/invalid result and all263 unlaunched dispositions remain in the retirement record. Root retained all four selected mechanisms and all264 planned r2 attempts; no development score tuning or changed scientific question. [The r2 selection](development-selection-decision-r2-001.json) binds the minimal entrypoint repair, versioned coordinator/readers and passed checks. The simulator remains at its original path to preserve exact physical calibration identity. Original r1 sources survive in the immutable prepared ZIP and selection snapshot; r1 is retired and cannot resume against changed working sources. Development counts and unmeasured-effort limitations are unchanged.\n')
    ledger.write_bytes(old + addition.encode('utf-8'))
    if not ledger.read_bytes().startswith(old): raise ValueError('Ledger history changed')
    with ledger_path.open('xb') as stream: stream.write(ledger.read_bytes())
    paths = set()
    for item in load(BATCH / 'release-control-index-batch01-eval-r1.json')['artifact_files']:
        p = Path(item['path'])
        if p.name == 'evaluation-trace-selection.json': p = BATCH / 'evaluation-trace-selection-r2.json'
        for source, target in ((EXP / 'Engineering Investigation', EXP / 'Engineering Investigation 002'),
                               (BATCH / 'Release Analysis', BATCH / 'Release Analysis 002')):
            if p.is_relative_to(source) and (target / p.relative_to(source)).is_file():
                p = target / p.relative_to(source)
                break
        paths.add(p.resolve())
    for directory in (EXP / 'Engineering Investigation 002', BATCH / 'Release Analysis 002', HERE / 'coordinator'):
        paths.update(p.resolve() for p in directory.iterdir() if p.is_file())
    paths.update(p.resolve() for p in (HERE / 'coordinator/fixtures').iterdir() if p.is_file())
    paths.update([selected_path, ledger_path, Path(__file__), validation_path, HERE / 'retirement-r1-and-r2-decision-001.json',
                  HERE / 'release_runner-r1.py.txt', RUNTIME / 'test_release_entrypoint.py', PREP / 'prepared-artifacts.json',
                  *[Path(r['path']) for r in prepared['artifacts'].values()], *[Path(r['path']) for r in receipts]])
    artifacts = [{'id': 'file-' + hashlib.sha256(str(p).encode()).hexdigest()[:16], **ref(p)} for p in sorted(paths)]
    index = {'schema_version': 'batch01-release-control-index-2', 'release_id': 'batch01-eval-r2', 'recorded_at_utc': now,
             'settings': load(BATCH / 'release-control-index-batch01-eval-r1.json')['settings'], 'artifact_files': artifacts,
             'scope': 'r2 selected controls; retained r1 evidence is historical and the retired r1 live source bindings are not claimed to verify',
             'queued_materialization_job': job['id'], 'selected_runtime': str(RUNTIME),
             'selected_coordinator': str(HERE / 'coordinator/run_release_series.ps1'),
             'selected_investigation': str(EXP / 'Engineering Investigation 002'), 'selected_analysis': str(BATCH / 'Release Analysis 002')}
    write(index_path, index)
    freeze = load(BATCH / 'freeze-batch01-eval-r1.json')
    freeze.update(release_id='batch01-eval-r2', frozen_at=datetime.now(timezone.utc).isoformat(),
                  **{k: prepared[k] for k in ('code_sha256', 'environment_sha256', 'model_sha256', 'protocol_sha256', 'artifacts')},
                  selection_criteria=selected['selection_rule'] + ' Full unchanged264-run infrastructure replacement after r1 failed before physics/policy execution; no hidden retry or tuning. Exact r2 selection SHA256=' + runner.digest(selected_path) + ', control index SHA256=' + runner.digest(index_path) + '. Preserve the12 fixed public trace slots, family-cluster bootstrap2000/publicseed0 and all failures.',
                  development_selection=ref(selected_path), control_index=ref(index_path))
    write(freeze_path, freeze)
    ready = load(BATCH / 'readiness-batch01-eval-r1.json')
    ready.update(schema_version='batch01-final-readiness-2', release_id='batch01-eval-r2', recorded_at_utc=freeze['frozen_at'],
                 freeze_sha256=runner.digest(freeze_path), evidence_refs=[ref(index_path), *[{k: r[k] for k in ('path', 'sha256')} for r in artifacts]],
                 replacement_scope='Original engineering gate scopes remain; CLI authorization defect repaired and439 Runtime tests passed. Both versioned reader/analysis suites returned0; new coordinator passed separately recorded host-specific checks. Physics/model/policies/evaluator/qualification/matrix/statistics unchanged. Retired r1 failure and unlaunched dispositions explicitly preserved.')
    for detail in ready['gate_details'].values():
        detail['r2_source_and_verification_amendment'] = ref(selected_path)
    write(ready_path, ready)
    protocol.validate_release_gates(freeze_path, ready_path)
    print(json.dumps({'selection': ref(selected_path), 'control_index': ref(index_path), 'freeze': ref(freeze_path), 'readiness': ref(ready_path), 'direct_files': len(ready['evidence_refs']), 'seeds_created': False}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--coordinator-receipt', required=True)
    main(parser.parse_args().coordinator_receipt)
