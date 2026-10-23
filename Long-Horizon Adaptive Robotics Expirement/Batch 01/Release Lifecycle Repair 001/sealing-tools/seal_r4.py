"""Queue-only r4 sealing from explicit, byte-bound root decisions; no seeds."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import zipfile

HERE = Path(__file__).resolve().parent
REPAIR = HERE.parent
BATCH = REPAIR.parent
ENVIRONMENT_REPAIR = BATCH / 'Release Environment Repair 001'
EXP = BATCH.parent
RUNTIME = EXP / 'Runtime 004'
ORIGINAL_RUNTIME = EXP / 'Runtime'
INVESTIGATION = EXP / 'Engineering Investigation 004'
ANALYSIS = BATCH / 'Release Analysis 004'
RELEASE = 'batch01-eval-r4'
DISTRIBUTION = 'LLMs-Robotics-Candidate-001'
QUEUE_STATE = Path(r'C:\Users\cresp\Documents\Dandelion Engineering\tools\compute_queue\runtime\state.json')
sys.path.insert(0, str(RUNTIME))
import release_runner as runner
import protocol

REQUIRED_FILES = {
    'prepared', 'prepared_receipt', 'previous_prepared', 'previous_selection',
    'previous_freeze', 'previous_controls', 'retirement', 'accounting', 'accounting_receipt', 'ledger',
    'retention', 'retention_receipt', 'trace_selection', 'probe_spec',
    'userland_manifest', 'userland_archive', 'userland_build_invocation',
    'userland_build_receipt', 'installed_userland_manifest', 'installed_integration_decision',
    'installed_userland_verification', 'installed_userland_receipt',
    'postclosure_userland_verification', 'postclosure_userland_receipt',
    'runtime_copy', 'runtime_copy_receipt', 'patch_manifest', 'runtime_integration', 'retirement_receipt',
    'reader_copy_manifest', 'qualification_assembly', 'qualification_assembly_receipt',
    'qualification_freeze', 'qualification_plan', 'prior_qualification_plan',
    'qualification_choices', 'pair_plan', 'pair_wrapper',
}
SOURCES: dict[Path, str] = {}
VERIFIED_RECEIPTS: dict[Path, dict] = {}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def ref(path):
    path = Path(path).resolve()
    require(path.is_file(), 'Missing actual file: ' + str(path))
    require(not any(p.casefold() == 'candidate_state' for p in path.parts), 'Candidate-private input refused')
    value = digest(path)
    require(path not in SOURCES or SOURCES[path] == value, 'Input changed: ' + str(path))
    SOURCES[path] = value
    return {'path': str(path), 'sha256': value}


def bound(item, base):
    require(isinstance(item, dict) and isinstance(item.get('path'), str), 'Actual path/hash reference required')
    path = Path(item['path'])
    actual = ref(path if path.is_absolute() else Path(base) / path)
    require(actual['sha256'] == item.get('sha256'), 'Reference hash differs: ' + actual['path'])
    return Path(actual['path'])


def mounted_reference(item):
    """Map only the explicit /mnt/<Windows-drive> form emitted by the builder."""
    value = item['path']
    if value.startswith('/mnt/') and len(value) > 7 and value[5].isalpha() and value[6] == '/':
        value = value[5] + ':/' + value[7:]
    return bound({**item, 'path': value}, HERE)


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def official(path):
    ref(path)
    receipt = load(path)
    require(receipt.get('state') == 'succeeded' and type(receipt.get('exit_status')) is int
            and receipt['exit_status'] == 0, 'Successful official receipt required: ' + str(path))
    matches = [row for row in load(QUEUE_STATE)['jobs'] if row['id'] == receipt.get('id')]
    require(len(matches) == 1 and matches[0] == receipt, 'Receipt differs from installed queue record')
    require(receipt.get('submitting_project') == 'LLMs-in-Robotics'
            and Path(receipt['cwd']).resolve().is_relative_to(EXP.parent.resolve()), 'Receipt project/cwd differs')
    VERIFIED_RECEIPTS[Path(path).resolve()] = ref(path)
    return receipt


def argument(receipt, flag):
    argv = receipt['argv']
    require(argv.count(flag) == 1 and argv.index(flag) + 1 < len(argv), 'Receipt lacks exact argument: ' + flag)
    return argv[argv.index(flag) + 1]


def argument_path(receipt, flag):
    path = Path(argument(receipt, flag))
    return (path if path.is_absolute() else Path(receipt['cwd']) / path).resolve()


def entrypoint(receipt, path):
    require(runner.python_entrypoint(receipt['argv'], receipt['cwd']) == Path(path).resolve(), 'Receipt entrypoint differs')


def utc(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.utcoffset() is not None, 'Timestamp must include timezone')
    return parsed


def verification_report(item, base):
    """Reuse the ordinary reviewed receipt/source report shape used for r2."""
    path = bound(item, base); report = load(path)
    require(report.get('all_required_checks_passed') is True, 'Actual verification report is not passed')
    receipts = report.get('official_receipts')
    if receipts is None: receipts = [report['official_receipt']] if report.get('official_receipt') else []
    require(isinstance(receipts, list), 'Verification receipt list is malformed')
    receipts = list(receipts)
    if item.get('receipt') is not None: receipts.append(item['receipt'])
    require(receipts, 'Verification report lacks actual receipts')
    verified_receipts = [official(bound(receipt, path.parent)) for receipt in receipts]
    if report.get('queue_job_id'):
        require(report['queue_job_id'] in {receipt['id'] for receipt in verified_receipts}, 'Verification report job lacks its actual official receipt')
    sources = report.get('source_files')
    if sources is None and 'source_files_before' in report:
        require(report['source_files_before'] == report['source_files_after'], 'Verification source inventories differ')
        sources = report['source_files_before']
        if isinstance(sources, dict):
            sources = [{'path': name, 'sha256': checksum} if isinstance(checksum, str) else checksum
                       for name, checksum in sources.items()]
    if sources is None and isinstance(report.get('inputs_before'), dict):
        require(report['inputs_before'] == report['inputs_after'], 'Verification before/after source inventory differs')
        sources = [{'path': name, 'sha256': checksum} for name, checksum in report['inputs_before'].items()]
    require(isinstance(sources, list) and sources, 'Verification report lacks tested source identities')
    for source in sources: bound(source, path.parent)
    require(report.get('sources_unchanged', True) is True, 'Verification sources changed')
    return ref(path)


def snapshot_accounting(path, receipt_path):
    report = load(path); receipt = official(receipt_path)
    entrypoint(receipt, REPAIR / 'accounting-tools/snapshot_selection.py')
    require(argument_path(receipt, '--output') == path.parent, 'Accounting receipt output differs')
    require(not (path.parent / 'snapshot-failure.json').exists(), 'Accounting has a retained failure marker')
    require(report.get('status') == 'complete_non_authorizing' and report.get('queue_job_id') == receipt['id'],
            'Completed officially bound development accounting required')
    require(report.get('canonical_store_unchanged_before_after') is True
            and report.get('source_files_unchanged_before_after') is True, 'Accounting inputs changed')
    development = report['development']
    require(development['attempt_count'] == 33 and development['result_record_count'] == 34
            and len(set(development['attempt_ids'])) == 33, 'Require 33 development attempts/34 result records')
    require({'B01-dev-A3-009', 'B01-dev-A3-010'} <= set(development['attempt_ids']), 'Common post-closure pair missing')
    retired = report['retired_evaluation']['attempt_ids']
    require(len(retired) == len(set(retired)) == 7
            and {p: sum(r.startswith(p + '-') for r in retired) for p in ('batch01-eval-r1', 'batch01-eval-r2', 'batch01-eval-r3')} == {'batch01-eval-r1': 1, 'batch01-eval-r2': 1, 'batch01-eval-r3': 5}
            and not set(report['retired_evaluation']['attempt_ids']) & set(development['attempt_ids']),
            'Retired evaluation attempts must remain separate')
    require({key: len(value['attempt_ids']) for key, value in report['entrants'].items()}
            == {'C0': 13, 'A1': 6, 'A2': 4, 'A3': 10}, 'Unexpected opportunity accounting')
    for item in report['canonical_files']:
        retained = bound({'path': item['snapshot_path'], 'sha256': item['sha256']}, path.parent)
        require(not retained.is_relative_to(EXP / 'Architecture Map'), 'Use immutable Map snapshots')
        require(digest(EXP / 'Architecture Map' / item['name']) == item['sha256'], 'Accounting snapshot is stale')
    require(report['current_runtime_files'] == {p.name: digest(p) for p in RUNTIME.glob('*.py')},
            'Accounting source snapshot differs from final Runtime')
    # The queued accountant, rather than this sealer, proves current-result chains.
    inventory = path.parent / 'snapshot-files.json'; ref(inventory)
    inventory_body = load(inventory)
    require(inventory_body['queue_job_id'] == receipt['id'], 'Accounting inventory job differs')
    for item in inventory_body['files']: bound(item, inventory.parent)
    return {'snapshot': ref(path), 'receipt': ref(receipt_path), 'development': development,
            'entrants': report['entrants'], 'retired_evaluation': report['retired_evaluation'],
            'scope': '33 completed development attempts; retired scored attempts excluded; all-stage revision totals remain as observed'}


def archive_sources(prepared, base, runtime_root):
    require(prepared['code_sha256'] == prepared['artifacts']['code']['sha256'], 'Code index identity differs')
    code_path = bound(prepared['artifacts']['code'], base)
    code = load(code_path)
    require(Path(code['runtime_root']).resolve() == runtime_root.resolve(), 'Physical Runtime path changed')
    bundle = bound(code['bundle'], code_path.parent)
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)) and all(Path(name).name == name and name.endswith('.py') for name in names), 'Unexpected source ZIP members')
        return {name: archive.read(name) for name in names}


def installed_manifest(files, archive_manifest):
    """Bind the exact prospective installed layer without laundering failed import."""
    path = files['installed_userland_manifest']; installed = load(path)
    decision_path = files['installed_integration_decision']; decision = load(decision_path)
    integration = installed['installed_integration']
    require(bound(decision['base_manifest'], decision_path.parent) == files['userland_manifest']
            and bound(integration['base_manifest'], path.parent) == files['userland_manifest']
            and bound(decision['installed_manifest'], decision_path.parent) == path, 'Installed/base decision identities differ')
    require(utc(decision['recorded_at_utc']) <= datetime.now(timezone.utc) and decision.get('decision'), 'Actual installed-layer decision required')
    require(all(installed.get(k) == value for k, value in archive_manifest.items() if k not in ('entries', 'tree_sha256', 'limitations')),
            'Installed layer altered base archive metadata or scope')
    require(installed['limitations'][:len(archive_manifest['limitations'])] == archive_manifest['limitations'], 'Base limitations were discarded')
    base_entries = archive_manifest['entries']; entries = installed['entries']
    require(all(entries.get(k) == value for k, value in base_entries.items()), 'Base tree has missing/changed paths')
    extras = {k: value for k, value in entries.items() if k not in base_entries}
    require(extras == integration['extra_entries'] and set(extras) == set(decision['exact_extra_paths']), 'Installed extras differ from exact declared layer')
    require(hashlib.sha256(protocol.canonical(entries)).hexdigest() == installed['tree_sha256'], 'Installed tree digest differs')
    require(integration.get('base_entries_unchanged') is True and integration.get('no_paths_excluded') is True
            and integration.get('runtime_files_modified') is False and integration.get('required_absence_violations') == {}
            and decision.get('base_missing_or_modified') is False and decision.get('required_absence_violations') == {}, 'Installed-layer boundary failed')
    require(integration['init'] == decision['external_init'] and integration['uname'] == decision['kernel'], 'Installed init/kernel decision differs')
    diagnostic_path = bound(integration['diagnostic'], path.parent)
    require(bound(decision['diagnostic'], decision_path.parent) == diagnostic_path, 'Installed diagnostic differs')
    diagnostic = load(diagnostic_path)
    receipt_path = bound(integration['diagnostic_receipt'], path.parent); receipt = official(receipt_path)
    require(bound(decision['official_receipt'], decision_path.parent) == receipt_path
            and diagnostic['queue_job_id'] == installed['identity_capture_queue_job_id'] == receipt['id'], 'Installed diagnostic receipt differs')
    require(diagnostic.get('status') == 'complete' and diagnostic.get('inputs_unchanged') is True
            and diagnostic.get('missing') == {} and diagnostic.get('changed') == {}
            and diagnostic.get('required_absence_violations') == {}, 'Installed diagnostic is incomplete or changes base paths')
    require(diagnostic['counts'] == decision['counts'] == {'actual': len(entries), 'changed': 0,
            'expected': len(base_entries), 'extra': len(extras), 'missing': 0}, 'Installed path accounting differs')
    for name in ('tree_before', 'tree_after'): bound(integration[name], path.parent)
    failed = load(bound(decision['failed_import_retained'], decision_path.parent))
    require(failed.get('state') == 'failed' and failed.get('exit_status') != 0, 'Original failed import must remain a failure')
    return installed


def installed_verification(path, receipt_path, manifest_path, manifest):
    report = load(path); receipt = official(receipt_path)
    verifier = ENVIRONMENT_REPAIR / 'installation-tools/verify_installed.py'
    entrypoint(receipt, verifier)
    require(argument_path(receipt, '--output-dir') == path.parent
            and argument_path(receipt, '--manifest') == manifest_path
            and argument(receipt, '--manifest-sha256') == digest(manifest_path), 'Installed verification arguments differ')
    require(report.get('schema_version') == 'installed-userland-verification-receipt-1'
            and report.get('status') == 'passed' and report.get('queue_job_id') == receipt['id']
            and report.get('distribution') == DISTRIBUTION
            and bound(report['manifest'], path.parent) == manifest_path
            and report.get('inputs_unchanged') is True and report['inputs_before'] == report['inputs_after'], 'Installed verification failed or changed')
    expected = {verifier.resolve(), (ENVIRONMENT_REPAIR / 'userland-tools/userland.py').resolve(), manifest_path}
    require({Path(p).resolve() for p in report['inputs_before']} == expected, 'Installed verification source inventory differs')
    for original, item in report['inputs_before'].items():
        require(bound(item, path.parent) == Path(original).resolve(), 'Installed verification source reference differs')
    observations = report['observations']
    require(set(observations) == {'identity', 'probe'} and all(type(r.get('returncode')) is int and r['returncode'] == 0
            and r.get('value', {}).get('verified') is True and json.loads(r['stdout']) == r['value'] for r in observations.values()), 'Installed native/tree observations failed')
    identity, probe = observations['identity']['value'], observations['probe']['value']
    require(probe['tree_sha256'] == manifest['tree_sha256'] and probe['init'] == manifest['installed_integration']['init']
            and probe['uname'] == manifest['installed_integration']['uname'], 'Installed tree/init/kernel differs')
    require(identity['account'] == {k: manifest['installed_integration']['default_user'][k] for k in ('username', 'uid', 'gid', 'home', 'shell')}
            and identity.get('bubblewrap_version') and set(identity['native_files']) == {'python', 'bubblewrap', 'seccomp'}, 'Candidate account/native evidence differs')
    require(all(item['identity'] == manifest['entries'].get(item['path']) for item in identity['native_files'].values()), 'Native binary bytes differ from installed tree')
    return receipt


def source_delta(files, old_sources, new_sources):
    """Require exact manifest bytes, not a wildcard permission for lifecycle edits."""
    old = {name: hashlib.sha256(value).hexdigest() for name, value in old_sources.items()}
    new = {name: hashlib.sha256(value).hexdigest() for name, value in new_sources.items()}
    require(len(old) == 57 and old == {p.name: ref(p)['sha256'] for p in ORIGINAL_RUNTIME.glob('*.py')},
            'Original r3 Runtime source inventory/bytes changed')
    require(new == {p.name: ref(p)['sha256'] for p in RUNTIME.glob('*.py')}, 'Prepared Runtime004 ZIP differs from current source')
    copied = load(files['runtime_copy']); receipt = official(files['runtime_copy_receipt'])
    entrypoint(receipt, REPAIR / 'copy_runtime.py')
    require(copied.get('status') == 'complete_base_only' and copied.get('queue_job_id') == receipt['id']
            and copied.get('sources_unchanged') is True and copied['source_files_before'] == copied['source_files_after'] == old
            and Path(copied['source_root']).resolve() == ORIGINAL_RUNTIME.resolve()
            and Path(copied['destination_root']).resolve() == RUNTIME.resolve(), 'Base copy provenance differs')
    patch = load(files['patch_manifest'])
    require(patch.get('schema_version') == 'model-lifecycle-staging-patch-1', 'Exact staged lifecycle patch manifest required')
    rows = patch['runtime_delta']; names = [r['name'] for r in rows]
    allowed = {'experiment.py', 'model_runtime.py', 'test_model_lifecycle.py', 'test_model_runtime.py'}
    changed = {name for name in old.keys() | new.keys() if old.get(name) != new.get(name)}
    require(len(names) == len(set(names)) and set(names) == set(patch['runtime_delta_allowlist']) == changed == allowed,
            'Final source delta differs from the explicit four-file patch')
    require(old.keys() <= new.keys(), 'Removal of original Runtime source is forbidden')
    for row in rows:
        name = row['name']; original = row['original']; staged = row['staged']
        require(Path(row['target_path']).resolve() == (RUNTIME / name).resolve(), 'Patch installation target must be Runtime004')
        bound(staged, files['patch_manifest'].parent)
        require(staged['sha256'] == new[name], 'Final source differs from exact staged patch: ' + name)
        if original is None:
            require(name not in old and row['operation'] == 'add', 'Unexpected added source')
        else:
            require(row['operation'] == 'modify' and bound(original, files['patch_manifest'].parent) == (ORIGINAL_RUNTIME/name).resolve()
                    and original['sha256'] == old[name], 'Patch original differs from retained r3 source')
    for key in ('original_sources', 'proposed_patch', 'design'):
        if key in patch: bound(patch[key], files['patch_manifest'].parent)
    integration = load(files['runtime_integration'])
    require(integration['schema_version'] == 'runtime-lifecycle-integration-1'
            and bound(integration['patch_manifest'], files['runtime_integration'].parent) == files['patch_manifest']
            and bound(integration['base_copy'], files['runtime_integration'].parent) == files['runtime_copy']
            and integration['original_before'] == integration['original_after'] == old
            and integration['new_runtime_sources'] == new, 'Installed source integration differs from actual patch/source bytes')
    return {'manifest': ref(files['patch_manifest']), 'changed_files': sorted(changed),
            'before': {name: old.get(name) for name in sorted(changed)},
            'after': {name: new[name] for name in sorted(changed)}, 'original_57_sources_unchanged': True}


def relocate_paths(value, old, new):
    """Only an exact absolute Runtime prefix; no substring or metadata elision."""
    if isinstance(value, dict): return {key: relocate_paths(item, old, new) for key, item in value.items()}
    if isinstance(value, list): return [relocate_paths(item, old, new) for item in value]
    if isinstance(value, str):
        if value == old: return new
        for sep in ('/', '\\'):
            if value.startswith(old + sep): return new + value[len(old):]
    return value


def compare_relocated_indexes(inputs, files, previous, prepared):
    expected = [{'from': str(ORIGINAL_RUNTIME.resolve()), 'to': str(RUNTIME.resolve())}]
    require(inputs.get('path_relocations') == expected, 'Exact original Runtime to Runtime004 relocation map required')
    for role in ('model', 'environment'):
        before = load(bound(previous['artifacts'][role], files['previous_prepared'].parent))
        after = load(bound(prepared['artifacts'][role], files['prepared'].parent))
        require(relocate_paths(before, expected[0]['from'], expected[0]['to']) == after,
                role + ' index changed beyond exact Runtime path relocation')


def fresh_qualification(files, prior_freeze, inputs, base):
    """Fresh measured class; unchanged declared rules, not identical measurements."""
    from restart_calibration_loader import load_restart_qualification
    freeze_path = files['qualification_freeze']; freeze = load(freeze_path)
    qualification = freeze['restart_qualification']
    require(inputs['restart_qualification'] == qualification and freeze.get('stage') == 'development', 'Actual accepted development qualification required')
    load_restart_qualification(freeze, freeze_path)
    bundle_path = bound(qualification, freeze_path.parent); bundle = load(bundle_path)
    assembly = load(files['qualification_assembly']); receipt = official(files['qualification_assembly_receipt'])
    entrypoint(receipt, REPAIR / 'qualification-tools/Restart Qualification Tools/assemble_qualification.py')
    require(assembly.get('schema_version') == 'restart-qualification-assembly-1' and assembly.get('status') == 'complete'
            and assembly.get('operator_acceptance_present') is True and assembly.get('loader_validation') == 'pass'
            and assembly.get('inputs_unchanged') is True and assembly['assembly_queue']['id'] == receipt['id']
            and Path(assembly['development_freeze_path']).resolve() == freeze_path
            and Path(assembly['bundle_path']).resolve() == bundle_path
            and argument_path(receipt, '--output') == files['qualification_assembly'].parent, 'Accepted assembly/receipt identity differs')
    for item in assembly['input_refs']: bound(item, files['qualification_assembly'].parent)
    for item in bundle['artifact_files']: bound(item, bundle_path.parent)
    old_ref = prior_freeze['restart_qualification']; old_bundle_path = bound(old_ref, files['previous_freeze'].parent)
    old_bundle = load(old_bundle_path)
    for key in ('selection_rule', 'prospective_absence_bound_s', 'absence_timebase', 'absence_endpoint'):
        require(qualification[key] == old_ref[key], 'Qualification convention widened: ' + key)
    mapping = qualification['payload_template_to_cell']
    require(set(mapping) == set(old_ref['payload_template_to_cell']) == {'part:A'}
            and qualification['prospective_absence_bound_s'] == 5.0
            and len(bundle['cells']) == 1 and mapping['part:A'] == bundle['cells'][0]['cell_id']
            and bundle['cells'][0]['route_envelope']['destination'] == 'parking1', 'Only original A-only parking1 scope is supported')
    require(qualification['class_spec_sha256'] != old_ref['class_spec_sha256'], 'Relocated Runtime needs a freshly measured physical class')
    for key in ('templates', 'declared_domain'):
        require(bundle['class_spec'][key] == old_bundle['class_spec'][key], 'Physical template/domain changed')
    choices_path = files['qualification_choices']; choices = load(choices_path)
    rule_path = bound(bundle['provisional_rule_ref'], bundle_path.parent); rule = load(rule_path)
    require(bound(rule['root_choices_ref'], rule_path.parent) == choices_path, 'Qualification is not bound to the prospective root choices')
    old_rule_path = bound(old_bundle['provisional_rule_ref'], old_bundle_path.parent)
    old_rule = load(old_rule_path)
    old_choices_path = bound(old_rule['root_choices_ref'], old_rule_path.parent); old_choices = load(old_choices_path)
    policy_keys = ('schema_version', 'destination', 'payload_template', 'construction_group', 'reference_trial_id',
        'construction_trial_ids', 'construction_profile', 'construction_evidence_role', 'center_rule', 'unchanged_A1_policy',
        'physical_parameter_domain', 'cover_bin_width_m', 'uniform_materialized_corridor_padding_m',
        'additional_sampling_clearance_allowance_m', 'prospective_absence_bound_s', 'absence_timebase',
        'absence_start', 'absence_endpoint', 'envelope_basis', 'validation_outcomes_used_for_fitting')
    require(all(choices[key] == old_choices[key] for key in policy_keys), 'Prospective numerical/construction policy differs')
    require(bound(choices['base_choices_ref'], choices_path.parent).read_bytes()
            == bound(old_choices['base_choices_ref'], old_choices_path.parent).read_bytes(), 'Original numerical allowance declaration changed')
    require(files['qualification_plan'] == (REPAIR/'qualification-tools/Recovery Profile Qualification/plan-001.json').resolve()
            and files['prior_qualification_plan'] == (BATCH/'Recovery Profile Qualification/plan-001.json').resolve()
            and files['qualification_plan'].read_bytes() == files['prior_qualification_plan'].read_bytes(),
            'Thirteen original declared development worlds changed')
    plan = load(files['qualification_plan']); ids = [row['id'] for row in plan['trials']]
    require(len(ids) == len(set(ids)) == 13 and plan.get('stage') == 'development_only', 'Require exactly thirteen development trials')
    assessment_path = bound(bundle['assessment_ref'], bundle_path.parent); assessment = load(assessment_path)
    construction_ids = choices['construction_trial_ids']; validation_ids = assessment['selected_validation_ids']
    require(len(construction_ids) == 7 and len(validation_ids) == 6
            and set(construction_ids).isdisjoint(validation_ids) and set(construction_ids + validation_ids) == set(ids),
            'All seven construction and six validation worlds must remain represented')
    for names, rows in ((construction_ids, assessment['construction_trials']), (validation_ids, assessment['trials'])):
        selected = [row for row in rows if row['trial_id'] in names]
        require(len(selected) == len(names) and all(isinstance(row.get('child_status'), str)
                and row.get('execution_status') not in ('unstarted', 'not_started', 'deferred_to_other_phase') for row in selected),
                'Fresh physical trial missing; failed/out-of-scope rows must remain retained')
    # Numerical assessment and actual support remain those of the bound assessor
    # and explicit operator acceptance; no all-world pass or held-out claim here.
    return qualification


def main(args):
    job = runner.queued_job(Path(__file__))  # Before hashes, probes, or writes.
    inputs_path = args.inputs.resolve(); ref(inputs_path); inputs = load(inputs_path); base = inputs_path.parent
    require(inputs.get('schema_version') == 'batch01-r4-seal-inputs-1' and inputs.get('release_id') == RELEASE
            and inputs.get('accepted') is True and inputs.get('root_note'), 'Concrete root-authored r4 inputs required')
    require(utc(inputs['recorded_at_utc']) <= datetime.now(timezone.utc), 'Future root acceptance refused')
    require(REQUIRED_FILES <= set(inputs['files']), 'Missing actual prerequisite file references')
    files = {key: bound(item, base) for key, item in inputs['files'].items()}
    retirement = load(files['retirement']); retired_receipt = official(files['retirement_receipt'])
    entrypoint(retired_receipt, REPAIR / 'record_retirement.py')
    require(retirement.get('schema_version') == 'batch01-lifecycle-incident-retirement-1'
            and retirement.get('queue_job_id') == retired_receipt['id'] and retirement.get('decision')
            and retirement.get('attempted_count') == 5 and retirement.get('unlaunched_count') == 259,
            'Actual r3 retirement and retained disposition required')
    required_checks = {'timeout_diagnostic', 'runtime_tests', 'readers_tests', 'coordinator_tests', 'relocation_identity', 'qualification_validation', 'pair_validation'}
    require(isinstance(inputs.get('verification_reports'), dict) and required_checks <= set(inputs['verification_reports']), 'Actual named reviewed verification reports required')
    checks = {name: verification_report(item, base) for name, item in inputs['verification_reports'].items()}
    require(set(inputs['gates']) == set(protocol.REQUIRED_GATES), 'Explicit eleven gate decisions required')
    require(all(value is True for value in inputs['gates'].values()), 'Root has not accepted every gate')
    require(set(inputs['gate_details']) == set(protocol.REQUIRED_GATES) and all(inputs['gate_details'].values()), 'Concrete gate bases required')
    prepared, previous = load(files['prepared']), load(files['previous_prepared'])
    receipt = official(files['prepared_receipt'])
    require(receipt['id'] == prepared['queue_job_id'], 'Prepared receipt/job differs')
    entrypoint(receipt, RUNTIME / 'freeze_artifacts.py')
    require(argument_path(receipt, '--probe-spec') == files['probe_spec']
            and argument_path(receipt, '--output-dir') == files['prepared'].parent, 'Preparation output/probe spec differs')
    runner.verify_artifacts(prepared, files['prepared'])
    require(prepared['protocol_sha256'] == previous['protocol_sha256'], 'Protocol source changed')
    old_sources = archive_sources(previous, files['previous_prepared'].parent, ORIGINAL_RUNTIME)
    new_sources = archive_sources(prepared, files['prepared'].parent, RUNTIME)
    source_change = source_delta(files, old_sources, new_sources)
    compare_relocated_indexes(inputs, files, previous, prepared)
    tested = load(Path(checks['runtime_tests']['path']))
    tested_sources = tested.get('inputs_before') or {r['path']: r['sha256'] for r in tested.get('source_files', [])}
    require(all(tested_sources.get(str((RUNTIME/name).resolve())) == hashlib.sha256(payload).hexdigest()
                for name, payload in new_sources.items()), 'Current complete Runtime inventory lacks source-bound test evidence')
    environment_path = bound(prepared['artifacts']['environment'], files['prepared'].parent)
    environment = load(environment_path); probes = {p['name']: p for p in environment['probes']}
    require({'candidate_python', 'candidate_isolation', 'candidate_userland_tree', 'gpu_driver', 'candidate_kernel'} <= set(probes), 'Required r4 environment probes missing')
    require(load(files['probe_spec'])['probes'] == [{k: p[k] for k in ('name', 'argv', 'timeout_s')} for p in environment['probes']], 'Prepared probes differ from declared spec')
    for name in ('candidate_python', 'candidate_isolation', 'candidate_userland_tree', 'candidate_kernel'):
        require(DISTRIBUTION in probes[name]['argv'], 'Probe does not target the fixed distro: ' + name)
    manifest = load(files['userland_manifest']); build = load(files['userland_build_invocation'])
    build_receipt = official(files['userland_build_receipt'])
    entrypoint(build_receipt, ENVIRONMENT_REPAIR / 'userland-tools/package_userland.py')
    require('build' in build_receipt['argv'] and argument_path(build_receipt, '--output-dir') == files['userland_manifest'].parent, 'Build output differs')
    config_path = argument_path(build_receipt, '--config'); ref(config_path)
    require(digest(config_path) == manifest['config_sha256'] and load(config_path) == manifest['config'], 'Build config differs')
    require(manifest.get('schema_version') == 'project-candidate-userland-1' and manifest.get('status') == 'complete'
            and manifest.get('inputs_unchanged') is True, 'Incomplete userland build')
    require(manifest['queue_job_id'] == build['queue_job_id'] == build_receipt['id'], 'Userland build receipt binding differs')
    require(build.get('mode') == 'build' and build.get('returncode') == 0 and build.get('sources_unchanged') is True
            and build['source_files_before'] == build['source_files_after'], 'Userland build sources/status changed')
    current_tools = {p.name: digest(p) for p in (ENVIRONMENT_REPAIR / 'userland-tools').glob('*.py')}
    require(build['source_files_before'] == current_tools, 'Current userland tools differ from actual build')
    require(manifest['source_before_sha256'] == manifest['source_after_sha256'], 'Userland build input identity changed')
    for item in manifest.get('optional_locale_evidence', {}).values(): mounted_reference(item)
    if manifest.get('optional_locale_evidence'):
        official(mounted_reference(manifest['optional_locale_evidence']['official_receipt']))
    require(manifest['archive']['sha256'] == ref(files['userland_archive'])['sha256']
            and manifest['archive']['bytes'] == files['userland_archive'].stat().st_size, 'Userland archive differs')
    require(manifest['tree_sha256'] == hashlib.sha256(protocol.canonical(manifest['entries'])).hexdigest(), 'Userland manifest tree digest differs')
    installed = installed_manifest(files, manifest)
    installed_verification(files['installed_userland_verification'], files['installed_userland_receipt'], files['installed_userland_manifest'], installed)
    verify_receipt = installed_verification(files['postclosure_userland_verification'], files['postclosure_userland_receipt'], files['installed_userland_manifest'], installed)
    require(ref(files['installed_userland_manifest'])['sha256'] in probes['candidate_userland_tree']['argv']
            and '--linux-probe' in probes['candidate_userland_tree']['argv'], 'Frozen tree probe lacks exact installed manifest/probe')
    accounting = snapshot_accounting(files['accounting'], files['accounting_receipt'])
    require({r for r in accounting['retired_evaluation']['attempt_ids'] if r.startswith('batch01-eval-r3-')}
            == set(retirement['attempted_run_ids']), 'Accounting and retirement disagree about actual r3 attempts')
    pair_plan = load(files['pair_plan'])
    old_pair_path = ENVIRONMENT_REPAIR / 'validation-tools/A3-environment-revalidation-plan.json'; ref(old_pair_path)
    expected_pair = load(old_pair_path)
    for row, identity in zip(expected_pair, ('B01-dev-A3-009', 'B01-dev-A3-010')): row['run_id'] = identity
    require(pair_plan == expected_pair, 'A3 pair differs from the same declared persistent/no-persistence world inputs')
    pair = inputs.get('a3_pair')
    require(isinstance(pair, list) and {row['run_id'] for row in pair} == {'B01-dev-A3-009', 'B01-dev-A3-010'} and len(pair) == 2, 'Require both declared post-closure A3 attempts')
    for row in pair:
        result_path = bound(row['result'], base); result = load(result_path)
        attempt = next(a for a in load(files['accounting'])['attempts'] if a['run_id'] == row['run_id'])
        canonical_refs = [r['reference'] for r in attempt['raw_result_refs'] if r['result_record_id'] == attempt['canonical_current_result_id']]
        require(any((EXP / 'Architecture Map' / r['uri']).resolve() == result_path and r['sha256'] == row['result']['sha256'] for r in canonical_refs), 'A3 result is not the accounted current canonical result')
        require(result['run_id'] == row['run_id'] and result['stage'] == 'development'
                and result['execution_status'] == 'completed' and result['outcome'] == 'success'
                and result.get('actual_host_timing_pass') is True and result.get('restart_exercised') is True,
                'Actual A3 completion/restart/timing prerequisite failed')
        require(result['restart_exposure']['restart_admissibility']['state'] == 'admissible', 'Actual A3 cut not admissible')
        attempt_manifest = load(bound(row['manifest'], base))
        require(attempt_manifest['run_id'] == row['run_id'] and attempt_manifest['runtime_files'] == {k: hashlib.sha256(v).hexdigest() for k, v in new_sources.items()}, 'A3 checkpoint differs from final Runtime')
        require(row['manifest']['sha256'] == attempt['manifest']['sha256'], 'A3 manifest differs from accounting')
        require(bound(attempt_manifest['development_restart_qualification'], result_path.parent) == files['qualification_freeze'],
                'A3 pair did not use the new accepted physical qualification')
        require(utc(verify_receipt['started_at']) >= utc(result['ended_at']), 'Userland verification predates the completed A3 pair')
    retention = load(files['retention']); retention_receipt = official(files['retention_receipt'])
    require(retention.get('derivation_queue_job_id') == retention_receipt['id'] and retention.get('reserve_bytes') == 50 * 1024**3
            and retention.get('full_unstarted_release_maximum_task_seconds') == 156600, 'Retention receipt/caps/reserve differ')
    require(len(retention['runs']) == 33 and not retention.get('registered_without_completed_result'), 'Fresh33-development-bundle inventory required')
    require({row['run_id'] for row in retention['runs']} == set(accounting['development']['attempt_ids']),
            'Retention inventory is not the exact accounted development set')
    rate = retention['planning_rate_mib_per_task_second']; maximum = retention['maximum_measured_mib_per_task_second']
    require(type(rate) in (int, float) and math.isfinite(rate) and rate >= max(3.0, maximum), 'Invalid planning rate')
    required = math.ceil(rate * 1024**2 * 156600) + 50 * 1024**3
    capacity = shutil.disk_usage(EXP).free
    capacity_at = datetime.now(timezone.utc).isoformat()
    require(retention['full_release_planning_requirement_bytes'] == required and capacity >= required, 'Insufficient current full-release capacity')
    prior_freeze = load(files['previous_freeze'])
    require(prior_freeze['release_id'] == 'batch01-eval-r3' and load(files['previous_selection'])['release_id'] == 'batch01-eval-r3', 'Predecessor is not r3')
    qualification = fresh_qualification(files, prior_freeze, inputs, base)
    narrative_path = INVESTIGATION / 'current-implementation-narrative.json'; narrative = load(narrative_path); ref(narrative_path)
    require(len(narrative['source_refs']) == 9 and all(row['sha256'] == hashlib.sha256(new_sources[row['member']]).hexdigest() for row in narrative['source_refs']), 'Narrative source identities differ')
    trace = load(files['trace_selection']); prior_trace = bound(trace['prior_fixed_slot_declaration'], files['trace_selection'].parent)
    restored = copy.deepcopy(trace['runs'])
    for row in restored:
        for key in ('run_id', 'path'): row[key] = row[key].replace(RELEASE, 'batch01-eval-r3')
    require(len(restored) == 12 and restored == load(prior_trace)['runs'], 'Fixed public trace slots changed')
    require(utc(trace['declared_at']) < datetime.now(timezone.utc), 'Trace declaration time invalid')
    output = args.output_dir.resolve()
    require(output.is_relative_to(BATCH) and not output.exists() and output.parent.is_dir(), 'Fresh output under Batch01 required')
    require(not (EXP / 'Evidence/releases' / RELEASE).exists(), 'R4 already exists; never reseal after seeds')
    output.mkdir()
    now = datetime.now(timezone.utc).isoformat()
    write(output / 'started.json', {'queue_job_id': job['id'], 'started_at_utc': now, 'creates_seeds': False})
    selected = load(files['previous_selection'])
    selected.update(schema_version='batch01-development-selection-r4-1', release_id=RELEASE, recorded_at_utc=now,
        predecessor_selection=ref(files['previous_selection']), release_supersession=ref(files['retirement']),
        decision=inputs['root_note'], episode_accounting=accounting, common_postclosure_validation=pair,
        historical_effort={'active_engineering_hours': None, 'measurement_state': 'unmeasured', 'initial_time_ceiling_compliance': 'unknown'},
        changes_since_r3={'source_delta': source_change, 'change': 'Explicit timeout lifecycle repair in separate Runtime 004; fresh physical qualification under unchanged numerical policy',
                         'candidate_model_geometry_policy_tuning': False, 'previous_environment_sha256': previous['environment_sha256'], 'environment_sha256': prepared['environment_sha256']},
        verification_checks=checks, environment_manifest=ref(files['installed_userland_manifest']),
        base_userland_manifest=ref(files['userland_manifest']), installed_integration_decision=ref(files['installed_integration_decision']),
        final_restart_qualification=qualification,
        current_capacity={'path': str(EXP), 'measured_at_utc': capacity_at, 'free_bytes': capacity,
                          'full_release_requirement_bytes': required, 'inventory': ref(files['retention']),
                          'inventory_receipt': ref(files['retention_receipt'])},
        verification_receipts=[VERIFIED_RECEIPTS[p] for p in sorted(VERIFIED_RECEIPTS)])
    require({c['architecture_id'] for c in selected['selected_checkpoints']} == {'B01-C0', 'B01-A1', 'B01-A2', 'B01-A3'}, 'All four selected mechanisms required')
    for checkpoint in selected['selected_checkpoints']:
        historical_path = bound(checkpoint['historical_manifest'], files['previous_selection'].parent)
        historical_hashes = load(historical_path)['runtime_files']
        final_hashes = {name: hashlib.sha256(value).hexdigest() for name, value in new_sources.items()}
        if 'latest_development_revision_id' in checkpoint:
            checkpoint['original_closure_revision_id'] = checkpoint.pop('latest_development_revision_id')
        checkpoint.pop('source_changes_after_latest_attempt', None)
        checkpoint['source_changes_since_original_closure'] = sorted(
            name for name in historical_hashes.keys() | final_hashes.keys()
            if historical_hashes.get(name) != final_hashes.get(name))
        checkpoint['checkpoint_reference_scope'] = ('Historical checkpoint at the original selection closure. '
            'The final_code_index identifies r4 execution bytes; separately recorded A3-009/010 are common post-closure lifecycle checks.')
        checkpoint.update(final_code_index=prepared['artifacts']['code'], final_environment_index=prepared['artifacts']['environment'],
            final_model_index=None if checkpoint['kind'] == 'baseline' else prepared['artifacts']['model'],
            common_postclosure_validation_ids=['B01-dev-A3-009', 'B01-dev-A3-010'],
            change_disposition='Mechanism/prompt/model/geometry source bytes retained. Common timeout lifecycle repair and relocation use actual source-bound checks, fresh physical qualification and the A3 pair; fixed userland identity is retained. Historical episodes retain original bytes.')
    selected_path = output / 'development-selection-decision-r4-001.json'; write(selected_path, selected)
    ledger_path = output / 'development-ledger-closed-r4-001.md'
    with ledger_path.open('xb') as stream:
        stream.write(files['ledger'].read_bytes())
        stream.write(('\n\n## R4 lifecycle-repair selection — ' + now + '\n\nRoot retained all four mechanisms and the full264-attempt comparison after retiring r3 for a common timeout lifecycle defect. The33 completed development attempts include the two predeclared common post-closure A3 lifecycle validations; seven retired evaluation attempts are excluded from that accounting. Fresh physical qualification repeats the same thirteen previously inspected development worlds under unchanged numerical rules; it is not held-out evidence. Historical and later active effort remains unmeasured. This closed copy binds the concrete r4 decision and actual verification evidence; no prior ledger or retired result is rewritten.\n').encode())
    paths = {Path(item['path']).resolve() for item in load(files['previous_controls'])['artifact_files']}
    mapped = set()
    for path in paths:
        for old, new in ((EXP/'Engineering Investigation 003', INVESTIGATION), (BATCH/'Release Analysis 003', ANALYSIS), (ENVIRONMENT_REPAIR/'coordinator', REPAIR/'coordinator')):
            if path.is_relative_to(old) and (new/path.relative_to(old)).is_file(): path = new/path.relative_to(old); break
        if path == BATCH/'evaluation-trace-selection-r3.json': path = files['trace_selection']
        if path == BATCH/'Development Ledger.md': path = ledger_path
        require(not (path.parent == EXP/'Architecture Map' and path.suffix == '.jsonl'), 'Live Map JSONL cannot be frozen')
        mapped.add(path)
    for directory in (INVESTIGATION, ANALYSIS, REPAIR/'coordinator', HERE, REPAIR/'accounting-tools', ENVIRONMENT_REPAIR/'userland-tools', ENVIRONMENT_REPAIR/'installation-tools'):
        mapped.update(p.resolve() for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name != 'index.html')
    mapped.update(SOURCES); mapped.update((selected_path, ledger_path, Path(__file__).resolve()))
    mapped.discard(files['ledger'])  # Freeze the closed copy; keep the original only as snapshot provenance.
    artifacts = [{'id': 'file-'+hashlib.sha256(str(p).encode()).hexdigest()[:16], **ref(p)} for p in sorted(mapped)]
    settings = load(files['previous_controls'])['settings']
    index_path = output/'release-control-index-batch01-eval-r4.json'
    write(index_path, {'schema_version': 'batch01-release-control-index-4', 'release_id': RELEASE, 'recorded_at_utc': now,
        'settings': settings, 'artifact_files': artifacts, 'selected_runtime': str(RUNTIME), 'selected_coordinator': str(REPAIR/'coordinator/run_release_series.ps1'),
        'selected_investigation': str(INVESTIGATION), 'selected_analysis': str(ANALYSIS), 'queued_materialization_job': job['id'],
        'scope': 'Fresh lifecycle-repair release; retained r1/r2/r3 provenance is historical, not a claim of live replayability'})
    freeze = copy.deepcopy(prior_freeze)
    freeze.update(release_id=RELEASE, frozen_at=datetime.now(timezone.utc).isoformat(),
        **{k: prepared[k] for k in ('code_sha256', 'environment_sha256', 'model_sha256', 'protocol_sha256', 'artifacts')},
        selection_criteria=selected['selection_rule']+' Full unchanged264-run lifecycle-repair replacement; no score-based policy tuning. Exact selection '+digest(selected_path)+'; controls '+digest(index_path)+'.',
        development_selection=ref(selected_path), control_index=ref(index_path), restart_qualification=qualification)
    freeze_path=output/'freeze-batch01-eval-r4.json'; write(freeze_path,freeze)
    for path, checksum in list(SOURCES.items()): require(digest(path)==checksum, 'Input changed before final readiness: '+str(path))
    ready={'schema_version':'batch01-final-readiness-4','release_id':RELEASE,'recorded_at_utc':freeze['frozen_at'],
        'freeze_sha256':digest(freeze_path),'scored_ready':True,'gates':inputs['gates'],
        'gate_details':inputs['gate_details'],'root_acceptance':ref(inputs_path),'evidence_refs':[ref(index_path), *[{k:r[k] for k in ('path','sha256')} for r in artifacts]],
        'scope':'Only explicit root decisions and actual bound prerequisites; no seeds or scored success created'}
    ready_path=output/'readiness-batch01-eval-r4.json';write(ready_path,ready)
    from restart_calibration_loader import load_restart_qualification
    load_restart_qualification(freeze, freeze_path)
    protocol.validate_release_gates(freeze_path,ready_path)
    result={'schema_version':'batch01-r4-sealing-result-1','status':'complete','queue_job_id':job['id'],
        'selection':ref(selected_path),'control_index':ref(index_path),'freeze':ref(freeze_path),'readiness':ref(ready_path),
        'closed_ledger':ref(ledger_path),'direct_files':len(ready['evidence_refs']),'inputs_unchanged':True,'seeds_created':False,
        'official_queue_completion_verified':False}
    write(output/'sealed.json',result);print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True,help='Actual root-authored references, prerequisite acceptances and gates')
    parser.add_argument('--output-dir',type=Path,required=True,help='Fresh operator output directory under Batch01')
    main(parser.parse_args())
