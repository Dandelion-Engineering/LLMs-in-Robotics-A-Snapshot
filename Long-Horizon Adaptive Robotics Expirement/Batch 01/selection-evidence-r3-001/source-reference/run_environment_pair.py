"""Queue-only fixed development pair after common candidate-userland repair.

This wrapper registers an infrastructure-purpose note, then delegates exact
pre-run snapshots/registration and both episodes to development_batch.run.
It does not finalize map results, create evaluation seeds, or grant readiness.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
EXP = HERE.parents[2]
RUNTIME = EXP / 'Runtime'
PLAN = HERE / 'A3-environment-revalidation-plan.json'
PRIOR_PLAN = EXP / 'Batch 01/Recovery Profile Qualification/A3-profile-validation-development-plan.json'
QUALIFICATION_FREEZE = EXP / 'Evidence/derived/recovery-profile-qualification-001/development-freeze.json'
RETIREMENT = HERE.parent / 'retirement-r2-and-r3-decision-001.json'
R2_CODE_INDEX = EXP / 'Evidence/prepared-artifacts/batch01-eval-r2-final/code.json'
DISTRIBUTION = 'LLMs-Robotics-Candidate-001'
DEFAULT_OUTPUT = Path('D:/CodexEvidence/LLMs-in-Robotics/A3-environment-revalidation-001')
DEFAULT_RAW = Path('D:/CodexEvidence/LLMs-in-Robotics/development-raw')
NOTE_ID = 'B01-environment-revalidation-plan-001'
# These mechanics, policies and resource rules must match the retired release.
# Only sandbox/freezer integration and its tests may change for this repair.
UNCHANGED = ('candidates.py', 'candidate_worker.py', 'model_runtime.py', 'model_setup.py',
             'cell.py', 'actuation.py', 'evaluator.py', 'sensor_worker.py', 'sensors.py',
             'restart_state.py', 'restart_compatibility.py', 'restart_qualification.py',
             'restart_physical_class.py', 'restart_calibration_loader.py', 'experiment.py',
             'initial_conditions.py', 'scenarios.py', 'resources.py', 'protocol.py')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def reference(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': digest(path)}


def save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def main(args):
    sys.path.insert(0, str(RUNTIME))
    import release_runner as runner
    job = runner.queued_job(expected_script=str(Path(__file__).resolve()))
    # No registration, native probes, model or physics before queue ownership.
    import development_batch
    import record_attempt
    from sandbox import CandidateSandbox
    plan = development_batch.validate(load(PLAN))
    prior = load(PRIOR_PLAN)
    if len(plan) != 2 or len(prior) != 2:
        raise ValueError('Exactly the predeclared two-run pair is required')
    for row, old, new_id in zip(plan, prior, ('B01-dev-A3-007', 'B01-dev-A3-008')):
        if row != {**old, 'run_id': new_id}:
            raise ValueError('Environment check must retain all prior inputs except new run ID')
    if inspect.signature(CandidateSandbox).parameters['distribution'].default != DISTRIBUTION:
        raise ValueError('The project-owned candidate distribution is not the default')
    expected = {Path(row['path']).name: row['sha256'] for row in load(R2_CODE_INDEX)['files']
                if Path(row['path']).parent.resolve() == RUNTIME.resolve()}
    for name in UNCHANGED:
        if expected.get(name) != digest(RUNTIME / name):
            raise ValueError('Unapproved policy/physical/common behavior change: ' + name)
    receipt_refs = []
    prerequisite_receipts = [('runtime_and_packager_checks', path) for path in args.runtime_test_receipt]
    prerequisite_receipts.append(('pinned_environment_preparation', args.environment_receipt))
    for label, path in prerequisite_receipts:
        receipt = load(path)
        if type(receipt.get('exit_status')) is not int or receipt['exit_status'] != 0:
            raise ValueError('Successful integer-exit-zero prerequisite receipt required')
        runner.verify_queue_receipt(receipt['id'], path)
        receipt_refs.append({'purpose': label, **reference(path)})
    # These are provenance references, not an inference that arbitrary successful
    # commands prove their named purpose. Root reviews exact argv/results first.
    environment_ref = reference(args.environment_manifest)
    data, _, errors = record_attempt.am.read_store(record_attempt.MAP)
    if errors:
        raise ValueError(errors)
    ids = {row['id'] for kind in data.values() for row in kind}
    if NOTE_ID in ids or any(row['run_id'] in ids for row in plan):
        raise ValueError('Prior registration exists; retain it and do not rerun')
    for row in plan:
        development_batch.development_location(row['run_id'], args.raw_root, require_fresh=True)
        if (record_attempt.MAP / 'releases' / row['run_id']).exists():
            raise ValueError('Existing immutable attempt snapshot prevents reuse')
    output = args.output.resolve()
    if output.exists():
        raise ValueError('Fresh evidence output required; preserve earlier failures')
    refs = [reference(p) for p in (PLAN, PRIOR_PLAN, QUALIFICATION_FREEZE, RETIREMENT,
                                   R2_CODE_INDEX, Path(__file__))]
    output.mkdir(parents=True, exist_ok=False)
    header = {'schema_version': 'post-closure-environment-revalidation-1',
              'recorded_at_utc': datetime.now(timezone.utc).isoformat(), 'queue_job_id': job['id'],
              'scope': 'Additional development infrastructure validation after selection closure; no tuning or scored inference',
              'candidate_distribution': DISTRIBUTION, 'plan': plan, 'input_refs': refs,
              'prerequisite_receipts': receipt_refs, 'pinned_environment_manifest': environment_ref,
              'runtime_sha256': development_batch.hashes(), 'prior_runs': ['B01-dev-A3-005', 'B01-dev-A3-006'],
              'original_closed_selection_modified': False, 'automatic_retries': 0,
              'queue_success_is_not_physical_success': True}
    header_path = output / 'environment-revalidation.json'
    save(header_path, header)
    record_attempt.append('note', {
        **record_attempt.common(NOTE_ID, ['batch-01', 'development', 'infrastructure-revalidation', 'post-selection-closure']),
        'target_ids': ['B01-C0', 'B01-A1', 'B01-A2', 'B01-A3', 'B01-dev-A3-005', 'B01-dev-A3-006'],
        'claim_type': 'decision', 'supersedes_note_id': None,
        'body': 'Prospective common Linux-environment repair validation: run only A3-007 persistent and A3-008 no-persistence with the exact A3-005/006 public development inputs. All entrant policy/model/physical sources remain unchanged. These are additional post-closure infrastructure attempts, not score-driven development, replacements for earlier episodes, qualified recovery assertions, or evaluation retries. Preserve the retired r1/r2 releases and original closed development accounting. Standard immutable snapshots and run records are registered before each episode; results require later official queue verification.',
        'evidence': [record_attempt.ref('Exact environment-validation execution prerequisites', header_path),
                     record_attempt.ref('Fixed two-run development plan', PLAN),
                     record_attempt.ref('Retired r2 and common environment repair decision', RETIREMENT)],
        'details': {'planned_run_ids': [r['run_id'] for r in plan], 'scope': header['scope'],
                    'prior_run_ids': header['prior_runs'], 'automatic_retries': 0}})
    result = development_batch.run(PLAN, output / 'batch', QUALIFICATION_FREEZE, args.raw_root)
    changed = [r['path'] for r in [*refs, environment_ref, *receipt_refs]
               if digest(r['path']) != r['sha256']]
    save(output / 'wrapper-completion.json', {'queue_job_id': job['id'],
         'input_changes': changed, 'attempts': result['attempts'], 'not_started': result['not_started'],
         'stop_reason': result['stop_reason'], 'canonical_results_recorded': False,
         'interpretation': 'Retained observations only; requires external official receipt and separate source/absence/timing assessment'})
    if changed:
        raise RuntimeError('Validation inputs changed; preserve this failed attempt: ' + repr(changed))
    print(json.dumps({'output': str(output), 'attempted': len(result['attempts']),
                      'not_started': result['not_started'], 'canonical_results_recorded': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-test-receipt', required=True, type=Path, action='append',
                        help='Repeat for separate actual Runtime/packager validation receipts')
    parser.add_argument('--environment-receipt', required=True, type=Path)
    parser.add_argument('--environment-manifest', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--raw-root', type=Path, default=DEFAULT_RAW)
    main(parser.parse_args())
