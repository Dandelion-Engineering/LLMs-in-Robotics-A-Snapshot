"""Queue-only, fixed A3-009/010 development pair after common lifecycle repair.

Preparation does not register anything. Execution verifies named prerequisites,
then delegates immutable snapshots/registration to Runtime 004 development_batch.
No retries, canonical result finalization, evaluation seeds or readiness grant.
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
REPAIR = HERE.parent
EXP = HERE.parents[2]
ORIGINAL = EXP / 'Runtime'
RUNTIME = EXP / 'Runtime 004'
PLAN = HERE / 'A3-lifecycle-revalidation-plan.json'
PROSPECTIVE = HERE / 'prospective-plan.json'
BASE = EXP / 'Batch 01/Release Environment Repair 001'
PRIOR_PLAN = BASE / 'validation-tools/A3-environment-revalidation-plan.json'
PRIOR_WRAPPER = BASE / 'validation-tools/run_environment_pair.py'
CODE_INDEX = EXP / 'Evidence/prepared-artifacts/batch01-eval-r3-final/code.json'
RETIREMENT = REPAIR / 'retirement-r3-and-r4-decision-001.json'
INSTALLED = EXP / 'Evidence/runtime-environments/candidate-installed-001/manifest.json'
DISTRIBUTION = 'LLMs-Robotics-Candidate-001'
NOTE_ID = 'B01-lifecycle-revalidation-plan-001'
RUN_IDS = ('B01-dev-A3-009', 'B01-dev-A3-010')
DELTA = {'experiment.py', 'model_runtime.py', 'test_model_lifecycle.py', 'test_model_runtime.py'}
DEFAULT_OUTPUT = Path('D:/CodexEvidence/LLMs-in-Robotics/A3-lifecycle-revalidation-001')
DEFAULT_RAW = Path('D:/CodexEvidence/LLMs-in-Robotics/development-raw')


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def ref(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': digest(path)}


def save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


class Inputs:
    def __init__(self):
        self.refs = {}

    def verify(self, item, base=None):
        path = Path(item['path'])
        path = (path if path.is_absolute() else Path(base) / path).resolve()
        actual = ref(path)
        require(actual['sha256'] == item['sha256'], 'Artifact bytes differ: ' + str(path))
        require(str(path) not in self.refs or self.refs[str(path)] == actual,
                'Conflicting artifact identities: ' + str(path))
        self.refs[str(path)] = actual
        return path

    def read(self, path):
        path = self.verify(ref(path))
        return load(path)

    def mapping(self, values):
        require(isinstance(values, dict) and values, 'Nonempty source identities required')
        for path, value in values.items():
            self.verify({'path': path, 'sha256': value} if isinstance(value, str) else value)

    def changes(self):
        return [path for path, item in self.refs.items() if digest(path) != item['sha256']]


def argument(receipt, flag):
    argv = receipt['argv']
    require(argv.count(flag) == 1, 'Receipt must contain exactly one ' + flag)
    index = argv.index(flag) + 1
    require(index < len(argv), 'Missing receipt argument: ' + flag)
    return argv[index]


def receipt_path(receipt, flag):
    path = Path(argument(receipt, flag))
    return (path if path.is_absolute() else Path(receipt['cwd']) / path).resolve()


def official(runner, inputs, path, job_id, entrypoint, output_flag=None, output=None):
    receipt = inputs.read(path)
    require(receipt.get('id') == job_id and type(receipt.get('exit_status')) is int
            and receipt['exit_status'] == 0 and receipt.get('state') == 'succeeded',
            'Named report requires its successful official receipt')
    runner.verify_queue_receipt(job_id, path)
    require(runner.python_entrypoint(receipt['argv'], receipt['cwd']) == entrypoint.resolve(),
            'Prerequisite receipt executed a different entrypoint')
    if output_flag:
        require(receipt_path(receipt, output_flag) == output.resolve(), 'Receipt output differs from report')
    return receipt


def verify_runtime(inputs, args):
    expected = {Path(row['path']).name: row['sha256'] for row in inputs.read(CODE_INDEX)['files']
                if Path(row['path']).parent.resolve() == ORIGINAL.resolve()}
    original = {p.name: digest(p) for p in ORIGINAL.glob('*.py')}
    current = {p.name: digest(p) for p in RUNTIME.glob('*.py')}
    require(expected and original == expected, 'Original Runtime differs from retired R3 code index')
    require(args.change_inventory.resolve().parent == REPAIR and args.runtime_integration.resolve().parent == REPAIR,
            'Lifecycle manifests must be versioned files in the repair directory')
    patch = inputs.read(args.change_inventory)
    require(patch['schema_version'] == 'model-lifecycle-staging-patch-1', 'Unexpected patch schema')
    rows = patch['runtime_delta']
    require(len(rows) == len(DELTA) and {r['name'] for r in rows} == DELTA
            and set(patch['runtime_delta_allowlist']) == DELTA, 'Unexpected lifecycle change allowlist')
    amended = dict(expected)
    for row in rows:
        name = row['name']
        require(Path(row['target_path']).resolve() == RUNTIME / name, 'Patch target is not Runtime 004')
        inputs.verify(row['staged'])
        if name in expected:
            require(row['operation'] == 'modify' and row['original']['sha256'] == expected[name]
                    and Path(row['original']['path']).resolve() == ORIGINAL / name,
                    'Patch original identity mismatch')
            inputs.verify(row['original'])
        else:
            require(name == 'test_model_lifecycle.py' and row['operation'] == 'add'
                    and row['original'] is None, 'Unexpected added source')
        amended[name] = row['staged']['sha256']
    require(current == amended, 'Runtime 004 does not exactly implement the four-file lifecycle delta')
    integration = inputs.read(args.runtime_integration)
    require(integration['schema_version'] == 'runtime-lifecycle-integration-1'
            and integration['original_sources_unchanged'] is True
            and integration['original_before'] == integration['original_after'] == original
            and integration['new_runtime_sources'] == current
            and set(integration['runtime_delta']) == DELTA, 'Integration evidence differs')
    require(inputs.verify(integration['patch_manifest']) == args.change_inventory.resolve(), 'Integration binds a different patch')
    for root, files in ((ORIGINAL, original), (RUNTIME, current)):
        inputs.mapping({str(root / name): checksum for name, checksum in files.items()})
    return current


def verify_tests(runner, inputs, args, current):
    report = inputs.read(args.runtime_test_report)
    require(report['schema_version'] == 'runtime004-integrated-validation-1'
            and report['all_required_checks_passed'] is True and report['sources_unchanged'] is True
            and report['inputs_before'] == report['inputs_after']
            and report['runtime_sources'] == current and Path(report['runtime_root']).resolve() == RUNTIME,
            'Runtime 004 validation is incomplete or belongs to different sources')
    require(args.runtime_test_entrypoint.resolve().parent == REPAIR
            and args.runtime_test_entrypoint.name.startswith('run_validation')
            and args.runtime_test_entrypoint.suffix == '.py', 'Unexpected integrated validation driver')
    suffix = args.runtime_test_entrypoint.stem.removeprefix('run_validation')
    require(suffix == '' or (suffix.startswith('_') and len(suffix) == 4 and suffix[1:].isdigit()),
            'Unexpected validation driver revision')
    output_name = 'integrated-validation-' + (suffix[1:] if suffix else '001')
    require(args.runtime_test_report.resolve() == REPAIR / output_name / 'validation.json',
            'Report path does not match the named validation driver output')
    official(runner, inputs, args.runtime_test_receipt, report['queue_job_id'], args.runtime_test_entrypoint)
    require(inputs.verify(report['integration']) == args.runtime_integration.resolve(), 'Test integration identity differs')
    inputs.mapping(report['inputs_before'])
    require(report['inputs_before'].get(str(args.runtime_test_entrypoint.resolve())) == digest(args.runtime_test_entrypoint),
            'Report does not bind its actual validation driver')
    checks = report['checks']
    require(len(checks) == 4 and {r['name'] for r in checks} == {'runtime', 'investigation', 'analysis', 'coordinator'}
            and all(r['passed'] is True and type(r['exit_status']) is int and r['exit_status'] == 0 for r in checks),
            'Missing or failed integrated check group')
    for row in checks:
        inputs.verify(row['stdout']); inputs.verify(row['stderr'])


def verify_environment(runner, inputs, args):
    report = inputs.read(args.environment_report)
    require(report['schema_version'] == 'installed-userland-verification-receipt-1'
            and report['status'] == 'passed' and report['distribution'] == DISTRIBUTION
            and report['inputs_unchanged'] is True and report['inputs_before'] == report['inputs_after'],
            'Installed userland verification is incomplete')
    receipt = official(runner, inputs, args.environment_receipt, report['queue_job_id'],
                       BASE / 'installation-tools/verify_installed.py', '--output-dir', args.environment_report.parent)
    require(inputs.verify(report['manifest']) == INSTALLED and receipt_path(receipt, '--manifest') == INSTALLED
            and argument(receipt, '--manifest-sha256') == report['manifest']['sha256'],
            'Installed environment identity differs')
    inputs.mapping(report['inputs_before'])
    installed = inputs.read(INSTALLED)
    require(installed['config']['target_distribution'] == DISTRIBUTION, 'Installed distribution differs')
    expected = {'identity': 'installed-candidate-native-identity-1', 'probe': 'installed-candidate-userland-verification-1'}
    require(set(report['observations']) == set(expected), 'Missing native or complete-tree observation')
    for mode, schema in expected.items():
        observation = report['observations'][mode]
        value = observation['value']
        require(type(observation['returncode']) is int and observation['returncode'] == 0
                and value['schema_version'] == schema and value['verified'] is True
                and json.loads(observation['stdout']) == value, 'Invalid installed observation')
    require(report['observations']['probe']['value']['tree_sha256'] == installed['tree_sha256'],
            'Installed tree identity differs')
    return report['manifest']


def verify_compilation(runner, inputs, args):
    report = inputs.read(args.compiled_identity_report)
    require(report['schema_version'] == 'runtime-relocation-compiled-identity-1'
            and report['status'] == 'complete' and report['source_inputs_unchanged'] is True
            and report['inputs_before'] == report['inputs_after'] and report['physics_steps'] == 0,
            'Incomplete compiled identity report')
    official(runner, inputs, args.compiled_identity_receipt, report['queue']['job_id'],
             REPAIR / 'qualification-tools/compiled_identity.py', '--output', args.compiled_identity_report.parent)
    inputs.mapping(report['helper_sources']); inputs.verify(report['manifest'])
    for key in ('source_hashes_equal', 'asset_bytes_equal', 'native_build_equal', 'compiled_surface_equal',
                'descriptive_path_normalized_xml_equal'):
        require(report['comparison'][key] is True, 'Compiled comparison differs: ' + key)
    # Actual class/XML identity may differ with the absolute mesh directory.
    # Never normalize the qualification itself; require its new actual class below.
    for label, runtime in (('original', ORIGINAL), ('relocated', RUNTIME)):
        inventory = report['inputs_before'][label]
        actual = {p.relative_to(runtime).as_posix(): {'sha256': digest(p), 'bytes': p.stat().st_size}
                  for p in [*runtime.glob('*.py'), *(p for p in (runtime / 'vendor/panda').rglob('*') if p.is_file())]}
        require(actual == inventory, 'Compiled runtime/asset inventory differs: ' + label)
        inputs.mapping({str(runtime / name): entry['sha256'] for name, entry in inventory.items()})
        result_path = inputs.verify(report['runtime_results'][label])
        result = inputs.read(result_path)
        require(Path(result['runtime']).resolve() == runtime and result['inputs_unchanged'] is True
                and result['physics_steps'] == 0 and result['renderer_created'] is False,
                'Compiled child identity differs')
        for value in result['files'].values():
            inputs.verify(value, result_path.parent)
        if label == 'relocated':
            relocated = result
    return relocated['class_spec']


def verify_qualification(runner, inputs, args, class_spec):
    from restart_calibration_loader import load_restart_qualification
    from restart_compatibility import digest as canonical_digest
    report = inputs.read(args.qualification_report)
    require(report['schema_version'] == 'restart-qualification-assembly-1' and report['status'] == 'complete'
            and report['operator_acceptance_present'] is True and report['loader_validation'] == 'pass'
            and report['inputs_unchanged'] is True, 'Fresh accepted qualification assembly required')
    receipt = official(runner, inputs, args.qualification_receipt, report['assembly_queue']['id'],
        REPAIR / 'qualification-tools/Restart Qualification Tools/assemble_qualification.py',
        '--output', args.qualification_report.parent)
    require('--acceptance' in receipt['argv'], 'Qualification was assembled without explicit acceptance')
    require(Path(report['development_freeze_path']).resolve() == args.qualification_freeze.resolve(),
            'Assembly does not bind the supplied development freeze')
    for item in report['input_refs']:
        inputs.verify(item, args.qualification_report.parent)
    freeze = inputs.read(args.qualification_freeze)
    require(freeze['schema_version'] == 'development-restart-qualification-freeze-1'
            and freeze['stage'] == 'development' and freeze['restart_matching_mode'] == 'qualified_class'
            and freeze['scored_ready_claimed'] is False and freeze['evaluation_seeds_created'] is False,
            'Expected a qualified development freeze without scored readiness')
    qualification = load_restart_qualification(freeze, args.qualification_freeze)
    require(qualification is not None, 'Qualification loader did not verify a qualified class')
    verified = qualification.as_dict()
    require(verified['identity']['class_spec_sha256'] == canonical_digest(class_spec),
            'Accepted qualification does not bind the actual Runtime 004 compiled class')
    require(inputs.verify(verified['identity']['bundle_file']) == Path(report['bundle_path']).resolve(),
            'Assembly and loader bundle identities differ')
    for item in verified['identity']['artifact_files'].values():
        inputs.verify(item)
    return verified['identity']


def main(args):
    sys.path.insert(0, str(RUNTIME))
    import release_runner as runner
    job = runner.queued_job(expected_script=Path(__file__).resolve())
    # All checks below run under actual queue ownership; no preparation-time probes.
    import development_batch
    import record_attempt
    import sandbox
    for module in (runner, development_batch, record_attempt, sandbox):
        require(Path(module.__file__).resolve().parent == RUNTIME, 'Wrong Runtime module imported')
    inputs = Inputs()
    prospective = inputs.read(PROSPECTIVE)
    planned_at = datetime.fromisoformat(prospective['recorded_at_utc'].replace('Z', '+00:00'))
    job_started_at = datetime.fromisoformat(job['started_at'].replace('Z', '+00:00'))
    require(prospective['schema_version'] == 'lifecycle-development-pair-prospective-plan-1'
            and prospective['run_ids'] == list(RUN_IDS) and planned_at.tzinfo is not None
            and planned_at < job_started_at, 'The exact pair requires an earlier prospective plan')
    for item in prospective['source_refs']:
        inputs.verify(item)
    plan = development_batch.validate(inputs.read(PLAN))
    prior = inputs.read(PRIOR_PLAN)
    require(len(plan) == len(prior) == 2, 'Exactly two fixed development runs required')
    for row, old, new_id in zip(plan, prior, RUN_IDS):
        require(row == {**old, 'run_id': new_id}, 'Only the prior pair run IDs may change')
    require(inspect.signature(sandbox.CandidateSandbox).parameters['distribution'].default == DISTRIBUTION,
            'Candidate distribution default changed')
    inputs.verify(ref(Path(__file__))); inputs.verify(ref(RETIREMENT)); inputs.verify(ref(PRIOR_WRAPPER))
    current = verify_runtime(inputs, args)
    verify_tests(runner, inputs, args, current)
    environment = verify_environment(runner, inputs, args)
    class_spec = verify_compilation(runner, inputs, args)
    qualification = verify_qualification(runner, inputs, args, class_spec)
    data, _, errors = record_attempt.am.read_store(record_attempt.MAP)
    require(not errors, 'Canonical Map errors: ' + repr(errors))
    ids = {row['id'] for kind in data.values() for row in kind}
    require(NOTE_ID not in ids and not any(identity in ids for identity in RUN_IDS),
            'Earlier registration exists; preserve it and do not rerun')
    require(args.raw_root.resolve() == DEFAULT_RAW.resolve(), 'Use the existing development raw root')
    for identity in RUN_IDS:
        development_batch.development_location(identity, args.raw_root, require_fresh=True)
        require(not (record_attempt.MAP / 'releases' / identity).exists(), 'Attempt snapshot already exists')
    output = args.output.resolve()
    require(output == DEFAULT_OUTPUT.resolve() and not output.exists(), 'Fixed fresh lifecycle pair output required')
    require(not inputs.changes(), 'Prerequisite inputs changed before registration')
    output.mkdir(parents=True, exist_ok=False)
    header = {'schema_version': 'post-closure-lifecycle-revalidation-1',
        'recorded_at_utc': datetime.now(timezone.utc).isoformat(), 'queue_job_id': job['id'],
        'prospective_plan': ref(PROSPECTIVE), 'plan': plan, 'runtime_root': str(RUNTIME),
        'runtime_sha256': current, 'candidate_distribution': DISTRIBUTION,
        'input_refs': list(inputs.refs.values()), 'installed_environment_manifest': environment,
        'qualification_identity': qualification,
        'prerequisite_reports': {name: ref(getattr(args, name + '_report')) for name in
            ('qualification', 'compiled_identity', 'runtime_test', 'environment')},
        'official_receipts': {name: ref(getattr(args, name + '_receipt')) for name in
            ('qualification', 'compiled_identity', 'runtime_test', 'environment')},
        'prior_runs': ['B01-dev-A3-007', 'B01-dev-A3-008'], 'automatic_retries': 0,
        'scope': 'Post-closure common infrastructure revalidation, with unchanged policies and fixed development inputs',
        'canonical_results_recorded': False, 'original_closed_selection_modified': False,
        'queue_success_is_not_physical_success': True, 'readiness_granted': False}
    header_path = output / 'lifecycle-revalidation.json'
    save(header_path, header)
    record_attempt.append('note', {
        **record_attempt.common(NOTE_ID, ['batch-01', 'development', 'infrastructure-revalidation', 'post-selection-closure']),
        'target_ids': ['B01-C0', 'B01-A1', 'B01-A2', 'B01-A3', 'B01-dev-A3-007', 'B01-dev-A3-008'],
        'claim_type': 'decision', 'supersedes_note_id': None,
        'body': 'Prospective common model-lifecycle repair validation: A3-009 persistent and A3-010 no-persistence retain the exact A3-007/008 public development inputs. Runtime 004 changes only common experiment/model timeout lifecycle handling and its declared tests; all entrant policies, physical mechanisms, model and resource budgets remain unchanged. These are additional infrastructure development attempts after selection closure, with no tuning, replacement of previous episodes, evaluation retries, or inferred qualification/readiness. Preserve all earlier failures and retired releases. Existing APIs register immutable snapshots before each episode; canonical results require subsequent official queue verification.',
        'evidence': [record_attempt.ref('Exact lifecycle pair prerequisites', header_path),
                     record_attempt.ref('Fixed development pair', PLAN),
                     record_attempt.ref('Retired R3 lifecycle incident decision', RETIREMENT)],
        'details': {'planned_run_ids': list(RUN_IDS), 'prior_run_ids': header['prior_runs'],
                    'scope': header['scope'], 'automatic_retries': 0}})
    try:
        result = development_batch.run(PLAN, output / 'batch', args.qualification_freeze, args.raw_root)
    except BaseException as error:
        save(output / 'wrapper-failure.json', {'queue_job_id': job['id'], 'error_type': type(error).__name__,
            'error': str(error), 'canonical_results_recorded': False,
            'interpretation': 'Retain all partial outputs and registrations; no automatic retry'})
        raise
    changes = inputs.changes()
    save(output / 'wrapper-completion.json', {'schema_version': 'lifecycle-pair-wrapper-completion-1',
        'queue_job_id': job['id'], 'input_changes': changes, 'attempts': result['attempts'],
        'not_started': result['not_started'], 'stop_reason': result['stop_reason'],
        'canonical_results_recorded': False, 'readiness_granted': False,
        'interpretation': 'Retained observations only; official receipt and separate physical/absence/timing review required'})
    require(not changes, 'Validation inputs changed; retained attempt is invalid: ' + repr(changes))
    print(json.dumps({'output': str(output), 'attempted': len(result['attempts']),
                      'not_started': result['not_started'], 'canonical_results_recorded': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qualification-freeze', type=Path, required=True)
    parser.add_argument('--change-inventory', type=Path, required=True)
    parser.add_argument('--runtime-integration', type=Path, required=True)
    parser.add_argument('--runtime-test-entrypoint', type=Path, required=True)
    for name in ('qualification', 'compiled-identity', 'runtime-test', 'environment'):
        parser.add_argument('--' + name + '-report', type=Path, required=True)
        parser.add_argument('--' + name + '-receipt', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--raw-root', type=Path, default=DEFAULT_RAW)
    main(parser.parse_args())
