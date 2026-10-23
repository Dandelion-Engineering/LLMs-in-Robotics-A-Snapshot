"""Materialize root's scoped r4 decisions from the actual completed prerequisites.

This records the operator decisions below; it does not create seeds or run a trial.
The separate sealer rechecks all bound sources and prerequisite identities.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

LIFE = Path(__file__).resolve().parent
BATCH = LIFE.parent
EXP = BATCH.parent
EV = EXP / 'Evidence'
ENV = BATCH / 'Release Environment Repair 001'
sys.path.insert(0, str(EXP / 'Runtime 004'))
import release_runner


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def ref(path):
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError('Missing actual input: ' + str(path))
    if path.stat().st_size > 10_000_000:
        raise ValueError('Large bytes must use prior reference and queued sealer recheck: ' + str(path))
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def receipt(identity):
    path = EV / 'queue-receipts' / (identity + '.json')
    value = read(path)
    if value['id'] != identity or value['state'] != 'succeeded' or type(value['exit_status']) is not int or value['exit_status'] != 0:
        raise ValueError('Actual successful official receipt required: ' + identity)
    return ref(path)


def main(args):
    job = release_runner.queued_job(expected_script=Path(__file__).resolve())
    output = LIFE / 'root-seal-inputs-001.json'
    if output.exists() or (EV / 'releases/batch01-eval-r4').exists():
        raise ValueError('Preserve existing decisions/releases; this authoring is once only')
    old = read(ENV / 'root-seal-inputs-001.json')
    retained = ['userland_manifest', 'userland_archive', 'userland_build_invocation',
                'userland_build_receipt', 'installed_userland_manifest',
                'installed_integration_decision', 'probe_spec', 'resource_policy']
    files = {key: old['files'][key] for key in retained}
    paths = {
        'prepared': EV / 'prepared-artifacts/batch01-eval-r4-final/prepared-artifacts.json',
        'previous_prepared': EV / 'prepared-artifacts/batch01-eval-r3-final/prepared-artifacts.json',
        'previous_selection': BATCH / 'release-seal-r3-001/development-selection-decision-r3-001.json',
        'previous_freeze': BATCH / 'release-seal-r3-001/freeze-batch01-eval-r3.json',
        'previous_controls': BATCH / 'release-seal-r3-001/release-control-index-batch01-eval-r3.json',
        'previous_readiness': BATCH / 'release-seal-r3-001/readiness-batch01-eval-r3.json',
        'retirement': LIFE / 'retirement-r3-and-r4-decision-001.json',
        'accounting': BATCH / 'selection-evidence-r4-001/accounting.json',
        'ledger': BATCH / 'Development Ledger.md',
        'retention': EV / 'derived/retention-development-r4-001/summary.json',
        'trace_selection': BATCH / 'evaluation-trace-selection-r4.json',
        'installed_userland_verification': EV / 'runtime-environments/installed-verification-003/verification.json',
        'postclosure_userland_verification': EV / 'runtime-environments/installed-verification-004/verification.json',
        'runtime_copy': LIFE / 'runtime-base-copy-001.json',
        'patch_manifest': LIFE / 'change-inventory-002.json',
        'runtime_integration': LIFE / 'runtime-integration-002.json',
        'reader_copy_manifest': LIFE / 'reader-copy-manifest-001.json',
        'qualification_assembly': EV / 'derived/runtime004-profile-qualification-001/assembly.json',
        'qualification_freeze': EV / 'derived/runtime004-profile-qualification-001/development-freeze.json',
        'qualification_plan': LIFE / 'qualification-tools/Recovery Profile Qualification/plan-001.json',
        'prior_qualification_plan': BATCH / 'Recovery Profile Qualification/plan-001.json',
        'qualification_choices': LIFE / 'qualification-tools/Recovery Profile Assembly Tools/root-profile-choices-001.json',
        'pair_plan': LIFE / 'validation-tools/A3-lifecycle-revalidation-plan.json',
        'pair_wrapper': LIFE / 'validation-tools/run_lifecycle_pair.py',
        'pair_completion': Path('D:/CodexEvidence/LLMs-in-Robotics/A3-lifecycle-revalidation-001/wrapper-completion.json'),
        'pair_prerequisites': Path('D:/CodexEvidence/LLMs-in-Robotics/A3-lifecycle-revalidation-001/lifecycle-revalidation.json'),
        'pair_finish': LIFE / 'pair-finish-001/finish.json',
        'pair_derived_index': EV / 'derived/development-A3-lifecycle-001/index.json',
        'pair_validation': LIFE / 'pair-validation-001.json',
        'root_input_author': Path(__file__),
    }
    files.update({key: ref(path) for key, path in paths.items()})
    ids = {
        'prepared_receipt': args.prepared_job,
        'accounting_receipt': args.accounting_job,
        'retention_receipt': args.retention_job,
        'installed_userland_receipt': '20260923T164356986495Z-ddea0940',
        'postclosure_userland_receipt': '20260923T165928931185Z-7fd3ece0',
        'runtime_copy_receipt': '20260923T160127885773Z-5109655b',
        'retirement_receipt': '20260923T160434302454Z-e598443a',
        'qualification_assembly_receipt': '20260923T164306313844Z-b225d732',
        'pair_execution_receipt': '20260923T164915655592Z-2410fca5',
        'pair_finalization_receipt': '20260923T165710349901Z-3623b171',
        'pair_derivation_receipt': '20260923T165747904067Z-86ed2bdf',
        'pair_validation_receipt': '20260923T165907911438Z-ebf857d2',
    }
    files.update({key: receipt(identity) for key, identity in ids.items()})
    reviewed = LIFE / 'reviewed-evidence'
    integrated = {**ref(LIFE / 'integrated-validation-002/validation.json'),
                  'receipt': receipt('20260923T161638519974Z-5a4dfe1b')}
    reports = {
        'timeout_diagnostic': ref(reviewed / 'timeout-retirement-verification-001.json'),
        'runtime_tests': integrated, 'readers_tests': integrated, 'coordinator_tests': integrated,
        'relocation_identity': ref(reviewed / 'compiled-relocation-verification-001.json'),
        'qualification_validation': ref(reviewed / 'qualification-validation-001.json'),
        'pair_validation': {**files['pair_validation'], 'receipt': files['pair_validation_receipt']},
        'sealer_tests': {**ref(EV / 'derived/sealing-tests-002/validation.json'),
                         'receipt': receipt('20260923T165949296300Z-f2a9e2a5')},
    }
    for name, item in reports.items():
        if read(item['path']).get('all_required_checks_passed') is not True:
            raise ValueError('Actual scoped verification has not passed: ' + name)
    pair = read(files['pair_validation']['path'])
    retention = read(files['retention']['path'])
    accounting = read(files['accounting']['path'])
    if len(retention['runs']) != 33 or accounting['development']['attempt_count'] != 33:
        raise ValueError('Need the exact completed 33-development inventory')
    bases = {
        'physical_workcell': 'Accept the retained MuJoCo/Panda task at n3/n6/n10 using unchanged physical sources and compiled surfaces, plus all13 fresh relocated qualification trials. Both actual A3-009/010 completed3/3. This is finite feasibility evidence, without a universal contact or continuous-state guarantee.',
        'public_perception': 'Accept unchanged tagged-image/device-I/O observations, retained75-center camera calibration and source-bound449 Runtime checks. Occluded, stale and unavailable observations stay explicit; no general dynamic-perception guarantee.',
        'independent_evaluator': 'Accept unchanged protected independent completion, partial-progress, error and settling predicates under449 actual Runtime checks. Preserve premature done assertions, C0-002 correction and every failed attempt; accepted count alone cannot establish completion.',
        'conventional_baseline': 'Retain the durable conventional scheduler and original C0-01210/10 and C0-013 after-release evidence. Its policy and physical mechanisms are byte-identical. Three fresh conventional-profile carry checks fail joint-position/velocity bounds and remain outside the accepted narrow class.',
        'candidate_implementations': 'Retain all three fixed14B mechanisms and matched persistence conditions with unchanged policy/prompt/model sources. The004 narrative binds final sources. Earlier A1/A2 failures remain; the A3-009/010 pair verifies common repaired infrastructure on declared old development inputs, without score-based tuning or winner selection.',
        'model_and_terms': 'Retain pinned Qwen3-14B Q4_K_M, llama.cpp and Panda terms evidence and exact effective configuration. Fresh queued preparation rehashes actual assets; the sealer compares exact indexes allowing only Runtime to Runtime004 path relocation. No spending or new external service.',
        'isolation': 'Accept449 actual Runtime checks including copied-code, clean environment, private proc, no host mounts, network/seccomp and actuator isolation in LLMs-Robotics-Candidate-001. The same5975-path installed tree, init/kernel and native identities pass before and after this pair. Historical base-import failure and explicit host-integration layer remain.',
        'timing_and_resources': 'Both actual A3-009/010 pass host timing while physics advances during inference. Typed intentional30s model timeout now terminates as budget failure only when other validity gates pass; genuine resource/stale/missing/PID/cleanup failures remain infrastructure failures. No grace, restart or budget increase. Five-second resource sampling, resource_caps_enforced=false, between-sample peaks, whole-GPU attribution and termination tails remain disclosed.',
        'evidence_retention': 'Accept the fresh33-bundle measured inventory and actual full264-run requirement for156600taskseconds plus50GiBreserve, conditional on the sealer live capacity check. No raw deletion, relocation, shortened caps, automatic retry or favorable trace replacement. Retain all seven retired scored attempts separately.',
        'disturbance_admissibility': 'Accept only fresh part:A/runtime004-profile-A1-root-001/parking1 qualification under the unchanged numerical policy and5.0-wall-second before_cancel to recover_held_admitted bound. Global qualification assessment retains3pass/3fail; only three declared high-profile checks support acceptance. Both A3 cuts pass17 required predicates without fallback and actual admission delays are0.43325219999678666/0.43214849999640137s. Preliminary readiness and development validity stay unknown; physical recovery success stays not_assessed. No B, insert, alternate-profile or continuous-state guarantee.',
        'equal_development_opportunity': 'Retain the symmetric prospective extension and60-episode ceiling for all entrants. Actual33development attempts/34results count C0/A1/A2/A3=13/6/4/10; seven retired scored attempts remain separate. Select all four unchanged mechanisms. Active engineering hours remain unmeasured, initial12-hour compliance unknown; no equal-realized-effort claim.',
    }
    if pair['all_required_checks_passed'] is not True or any(not row['all_required_checks_passed'] for row in pair['pair']):
        raise ValueError('Pair scoped checks failed')
    for key in ('installed_userland_verification', 'postclosure_userland_verification'):
        if read(files[key]['path'])['status'] != 'passed':
            raise ValueError('Installed environment did not verify')
    gate_evidence = [reports['runtime_tests'], reports['relocation_identity'],
                     reports['qualification_validation'], reports['pair_validation'],
                     files['accounting'], files['retention'], files['postclosure_userland_verification']]
    result = {
        'schema_version': 'batch01-r4-seal-inputs-1', 'release_id': 'batch01-eval-r4',
        'accepted': True, 'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
        'operator': 'Codex session4 root under Randy complete-experiment authorization',
        'materialization_queue_job_id': job['id'],
        'root_note': 'Retire r3 for its confirmed common timeout lifecycle defect and retain its five attempted outcomes plus259unlaunched. Accept the exact versioned Runtime004 common repair and fresh bounded physical qualification with actual source, environment, timing, restart and retention evidence. Preserve every prior failure and all unknowns. Select all four unchanged mechanisms for the complete fresh264-attempt comparison with the same budgets, protocol, twelve trace slots and fixed2000-draw analysis. No score-driven policy tuning or retries.',
        'files': files, 'verification_reports': reports,
        'gates': {key: True for key in bases},
        'gate_details': {key: {'decision': 'accept_declared_scope_with_stated_limits',
                              'basis': value, 'current_evidence': gate_evidence}
                         for key, value in bases.items()},
        'restart_qualification': read(files['qualification_freeze']['path'])['restart_qualification'],
        'path_relocations': [{'from': str((EXP / 'Runtime').resolve()), 'to': str((EXP / 'Runtime 004').resolve())}],
        'a3_pair': [{'run_id': rid,
                    'result': ref(Path('D:/CodexEvidence/LLMs-in-Robotics/development-raw') / rid / 'result.json'),
                    'manifest': ref(EXP / 'Architecture Map/releases' / rid / 'manifest.json')}
                   for rid in ('B01-dev-A3-009', 'B01-dev-A3-010')],
        'root_pair_review': 'Root reviewed actual scoped checks,17 predicates, wall durations and failures; preparer root_review_required is resolved only for the stated scope. No development validity or physical recovery-success upgrade.',
    }
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'output': ref(output), 'creates_seeds': False, 'runs_experiments': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared-job', required=True)
    parser.add_argument('--accounting-job', required=True)
    parser.add_argument('--retention-job', required=True)
    main(parser.parse_args())
