"""Queue-only r3 sealing from explicit, byte-bound root decisions; no seeds."""
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
BATCH = HERE.parent
EXP = BATCH.parent
RUNTIME = EXP / 'Runtime'
INVESTIGATION = EXP / 'Engineering Investigation 003'
ANALYSIS = BATCH / 'Release Analysis 003'
RELEASE = 'batch01-eval-r3'
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
    if receipts is None: receipts = [report.get('official_receipt')]
    require(isinstance(receipts, list) and receipts, 'Verification report lacks actual receipts')
    for receipt in receipts: official(bound(receipt, path.parent))
    sources = report.get('source_files')
    require(isinstance(sources, list) and sources, 'Verification report lacks tested source identities')
    for source in sources: bound(source, path.parent)
    require(report.get('sources_unchanged', True) is True, 'Verification sources changed')
    return ref(path)


def snapshot_accounting(path, receipt_path):
    report = load(path); receipt = official(receipt_path)
    entrypoint(receipt, HERE / 'accounting-tools/snapshot_selection.py')
    require(not (path.parent / 'snapshot-failure.json').exists(), 'Accounting has a retained failure marker')
    require(report.get('status') == 'complete_non_authorizing' and report.get('queue_job_id') == receipt['id'],
            'Completed officially bound development accounting required')
    require(report.get('canonical_store_unchanged_before_after') is True
            and report.get('source_files_unchanged_before_after') is True, 'Accounting inputs changed')
    development = report['development']
    require(development['attempt_count'] == 31 and development['result_record_count'] == 32
            and len(set(development['attempt_ids'])) == 31, 'Require 31 development attempts/32 result records')
    require({'B01-dev-A3-007', 'B01-dev-A3-008'} <= set(development['attempt_ids']), 'Common post-closure pair missing')
    require(set(report['retired_evaluation']['attempt_ids']) == {'batch01-eval-r1-C24-rep2-A1-persistent', 'batch01-eval-r2-C24-rep2-A1-persistent'}
            and not set(report['retired_evaluation']['attempt_ids']) & set(development['attempt_ids']),
            'Retired evaluation attempts must remain separate')
    require({key: len(value['attempt_ids']) for key, value in report['entrants'].items()}
            == {'C0': 13, 'A1': 6, 'A2': 4, 'A3': 8}, 'Unexpected opportunity accounting')
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
            'scope': '31 completed development attempts; retired scored attempts excluded; all-stage revision totals remain as observed'}


def archive_sources(prepared, base):
    require(prepared['code_sha256'] == prepared['artifacts']['code']['sha256'], 'Code index identity differs')
    code_path = bound(prepared['artifacts']['code'], base)
    code = load(code_path)
    require(Path(code['runtime_root']).resolve() == RUNTIME.resolve(), 'Physical Runtime path changed')
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
    verifier = HERE / 'installation-tools/verify_installed.py'
    entrypoint(receipt, verifier)
    require(argument_path(receipt, '--output-dir') == path.parent
            and argument_path(receipt, '--manifest') == manifest_path
            and argument(receipt, '--manifest-sha256') == digest(manifest_path), 'Installed verification arguments differ')
    require(report.get('schema_version') == 'installed-userland-verification-receipt-1'
            and report.get('status') == 'passed' and report.get('queue_job_id') == receipt['id']
            and report.get('distribution') == DISTRIBUTION
            and bound(report['manifest'], path.parent) == manifest_path
            and report.get('inputs_unchanged') is True and report['inputs_before'] == report['inputs_after'], 'Installed verification failed or changed')
    expected = {verifier.resolve(), (HERE / 'userland-tools/userland.py').resolve(), manifest_path}
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


def main(args):
    job = runner.queued_job(Path(__file__))  # Before hashes, probes, or writes.
    inputs_path = args.inputs.resolve(); ref(inputs_path); inputs = load(inputs_path); base = inputs_path.parent
    require(inputs.get('schema_version') == 'batch01-r3-seal-inputs-1' and inputs.get('release_id') == RELEASE
            and inputs.get('accepted') is True and inputs.get('root_note'), 'Concrete root-authored r3 inputs required')
    require(utc(inputs['recorded_at_utc']) <= datetime.now(timezone.utc), 'Future root acceptance refused')
    require(REQUIRED_FILES <= set(inputs['files']), 'Missing actual prerequisite file references')
    files = {key: bound(item, base) for key, item in inputs['files'].items()}
    require(isinstance(inputs.get('verification_reports'), list) and inputs['verification_reports'], 'Actual reviewed verification reports required')
    checks = [verification_report(item, base) for item in inputs['verification_reports']]
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
    require(all(prepared[k] == previous[k] for k in ('protocol_sha256', 'model_sha256')), 'Protocol/model changed')
    require(prepared['environment_sha256'] != previous['environment_sha256'], 'New fixed environment index required')
    old_sources, new_sources = archive_sources(previous, files['previous_prepared'].parent), archive_sources(prepared, files['prepared'].parent)
    require(set(old_sources) == set(new_sources), 'Unexpected Runtime file inventory change')
    require([k for k in sorted(old_sources) if old_sources[k] != new_sources[k]] == ['sandbox.py'], 'Unexpected Runtime change beyond distro default')
    old_default = b'distribution: str = "Ubuntu-24.04"'
    new_default = ('distribution: str = "' + DISTRIBUTION + '"').encode()
    require(old_sources['sandbox.py'].count(old_default) == 1
            and old_sources['sandbox.py'].replace(old_default, new_default) == new_sources['sandbox.py'], 'Sandbox change exceeds declared one-line default')
    environment_path = bound(prepared['artifacts']['environment'], files['prepared'].parent)
    environment = load(environment_path); probes = {p['name']: p for p in environment['probes']}
    require({'candidate_python', 'candidate_isolation', 'candidate_userland_tree', 'gpu_driver', 'candidate_kernel'} <= set(probes), 'Required r3 environment probes missing')
    require(load(files['probe_spec'])['probes'] == [{k: p[k] for k in ('name', 'argv', 'timeout_s')} for p in environment['probes']], 'Prepared probes differ from declared spec')
    for name in ('candidate_python', 'candidate_isolation', 'candidate_userland_tree', 'candidate_kernel'):
        require(DISTRIBUTION in probes[name]['argv'], 'Probe does not target the fixed distro: ' + name)
    manifest = load(files['userland_manifest']); build = load(files['userland_build_invocation'])
    build_receipt = official(files['userland_build_receipt'])
    entrypoint(build_receipt, HERE / 'userland-tools/package_userland.py')
    require('build' in build_receipt['argv'] and argument_path(build_receipt, '--output-dir') == files['userland_manifest'].parent, 'Build output differs')
    config_path = argument_path(build_receipt, '--config'); ref(config_path)
    require(digest(config_path) == manifest['config_sha256'] and load(config_path) == manifest['config'], 'Build config differs')
    require(manifest.get('schema_version') == 'project-candidate-userland-1' and manifest.get('status') == 'complete'
            and manifest.get('inputs_unchanged') is True, 'Incomplete userland build')
    require(manifest['queue_job_id'] == build['queue_job_id'] == build_receipt['id'], 'Userland build receipt binding differs')
    require(build.get('mode') == 'build' and build.get('returncode') == 0 and build.get('sources_unchanged') is True
            and build['source_files_before'] == build['source_files_after'], 'Userland build sources/status changed')
    current_tools = {p.name: digest(p) for p in (HERE / 'userland-tools').glob('*.py')}
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
    pair = inputs.get('a3_pair')
    require(isinstance(pair, list) and {row['run_id'] for row in pair} == {'B01-dev-A3-007', 'B01-dev-A3-008'} and len(pair) == 2, 'Require both declared post-closure A3 attempts')
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
        require(utc(verify_receipt['started_at']) >= utc(result['ended_at']), 'Userland verification predates the completed A3 pair')
    retention = load(files['retention']); retention_receipt = official(files['retention_receipt'])
    require(retention.get('derivation_queue_job_id') == retention_receipt['id'] and retention.get('reserve_bytes') == 50 * 1024**3
            and retention.get('full_unstarted_release_maximum_task_seconds') == 156600, 'Retention receipt/caps/reserve differ')
    require(len(retention['runs']) == 31 and not retention.get('registered_without_completed_result'), 'Fresh31-development-bundle inventory required')
    rate = retention['planning_rate_mib_per_task_second']; maximum = retention['maximum_measured_mib_per_task_second']
    require(type(rate) in (int, float) and math.isfinite(rate) and rate >= max(3.0, maximum), 'Invalid planning rate')
    required = math.ceil(rate * 1024**2 * 156600) + 50 * 1024**3
    capacity = shutil.disk_usage(EXP).free
    capacity_at = datetime.now(timezone.utc).isoformat()
    require(retention['full_release_planning_requirement_bytes'] == required and capacity >= required, 'Insufficient current full-release capacity')
    prior_freeze = load(files['previous_freeze'])
    require(prior_freeze['release_id'] == 'batch01-eval-r2' and load(files['previous_selection'])['release_id'] == 'batch01-eval-r2', 'Predecessor is not r2')
    require(inputs['restart_qualification'] == prior_freeze['restart_qualification'], 'Geometric qualification/mapping/absence scope changed')
    narrative_path = INVESTIGATION / 'current-implementation-narrative.json'; narrative = load(narrative_path); ref(narrative_path)
    require(len(narrative['source_refs']) == 9 and all(row['sha256'] == hashlib.sha256(new_sources[row['member']]).hexdigest() for row in narrative['source_refs']), 'Narrative source identities differ')
    trace = load(files['trace_selection']); prior_trace = bound(trace['prior_fixed_slot_declaration'], files['trace_selection'].parent)
    restored = copy.deepcopy(trace['runs'])
    for row in restored:
        for key in ('run_id', 'path'): row[key] = row[key].replace(RELEASE, 'batch01-eval-r2')
    require(len(restored) == 12 and restored == load(prior_trace)['runs'], 'Fixed public trace slots changed')
    require(utc(trace['declared_at']) < datetime.now(timezone.utc), 'Trace declaration time invalid')
    output = args.output_dir.resolve()
    require(output.is_relative_to(BATCH) and not output.exists() and output.parent.is_dir(), 'Fresh output under Batch01 required')
    require(not (EXP / 'Evidence/releases' / RELEASE).exists(), 'R3 already exists; never reseal after seeds')
    output.mkdir()
    now = datetime.now(timezone.utc).isoformat()
    write(output / 'started.json', {'queue_job_id': job['id'], 'started_at_utc': now, 'creates_seeds': False})
    selected = load(files['previous_selection'])
    selected.update(schema_version='batch01-development-selection-r3-1', release_id=RELEASE, recorded_at_utc=now,
        predecessor_selection=ref(files['previous_selection']), release_supersession=ref(files['retirement']),
        decision=inputs['root_note'], episode_accounting=accounting, common_postclosure_validation=pair,
        historical_effort={'active_engineering_hours': None, 'measurement_state': 'unmeasured', 'initial_time_ceiling_compliance': 'unknown'},
        changes_since_r2={'runtime_changed_files': ['sandbox.py'], 'change': 'Fixed project-owned candidate distro default; physical Runtime path preserved',
                         'candidate_model_geometry_policy_tuning': False, 'previous_environment_sha256': previous['environment_sha256'], 'environment_sha256': prepared['environment_sha256']},
        verification_checks=checks, environment_manifest=ref(files['installed_userland_manifest']),
        base_userland_manifest=ref(files['userland_manifest']), installed_integration_decision=ref(files['installed_integration_decision']),
        final_restart_qualification=inputs['restart_qualification'],
        current_capacity={'path': str(EXP), 'measured_at_utc': capacity_at, 'free_bytes': capacity,
                          'full_release_requirement_bytes': required, 'inventory': ref(files['retention']),
                          'inventory_receipt': ref(files['retention_receipt'])},
        verification_receipts=[VERIFIED_RECEIPTS[p] for p in sorted(VERIFIED_RECEIPTS)])
    require({c['architecture_id'] for c in selected['selected_checkpoints']} == {'B01-C0', 'B01-A1', 'B01-A2', 'B01-A3'}, 'All four selected mechanisms required')
    for checkpoint in selected['selected_checkpoints']:
        historical_path = bound(checkpoint['historical_manifest'], files['previous_selection'].parent)
        historical_hashes = load(historical_path)['runtime_files']
        final_hashes = {name: hashlib.sha256(value).hexdigest() for name, value in new_sources.items()}
        checkpoint['original_closure_revision_id'] = checkpoint.pop('latest_development_revision_id')
        checkpoint.pop('source_changes_after_latest_attempt', None)
        checkpoint['source_changes_since_original_closure'] = sorted(
            name for name in historical_hashes.keys() | final_hashes.keys()
            if historical_hashes.get(name) != final_hashes.get(name))
        checkpoint['checkpoint_reference_scope'] = ('Historical checkpoint at the original selection closure. '
            'The final_code_index identifies r3 execution bytes; separately recorded A3-007/008 are common post-closure environment checks.')
        checkpoint.update(final_code_index=prepared['artifacts']['code'], final_environment_index=prepared['artifacts']['environment'],
            final_model_index=None if checkpoint['kind'] == 'baseline' else prepared['artifacts']['model'],
            common_postclosure_validation_ids=['B01-dev-A3-007', 'B01-dev-A3-008'],
            change_disposition='Mechanism/prompt/model/geometry retained. Project-owned fixed userland is a prospective common environment repair; actual source-bound checks and A3 pair support this change. Historical episodes retain original bytes.')
    selected_path = output / 'development-selection-decision-r3-001.json'; write(selected_path, selected)
    ledger_path = output / 'development-ledger-closed-r3-001.md'
    with ledger_path.open('xb') as stream:
        stream.write(files['ledger'].read_bytes())
        stream.write(('\n\n## R3 fixed-environment selection — ' + now + '\n\nRoot retained all four mechanisms and the full264-attempt comparison after retiring r2 for environment drift. The31 completed development attempts include the two predeclared common post-closure A3 validations; retired evaluation attempts are excluded from that accounting. Historical and later active effort remains unmeasured. This new closed copy binds the concrete r3 decision and actual verification evidence; no prior ledger or retired result is rewritten.\n').encode())
    paths = {Path(item['path']).resolve() for item in load(files['previous_controls'])['artifact_files']}
    mapped = set()
    for path in paths:
        for old, new in ((EXP/'Engineering Investigation 002', INVESTIGATION), (BATCH/'Release Analysis 002', ANALYSIS), (BATCH/'Release Infrastructure Repair 001/coordinator', HERE/'coordinator')):
            if path.is_relative_to(old) and (new/path.relative_to(old)).is_file(): path = new/path.relative_to(old); break
        if path == BATCH/'evaluation-trace-selection-r2.json': path = files['trace_selection']
        if path == BATCH/'Development Ledger.md': path = ledger_path
        require(not (path.parent == EXP/'Architecture Map' and path.suffix == '.jsonl'), 'Live Map JSONL cannot be frozen')
        mapped.add(path)
    for directory in (INVESTIGATION, ANALYSIS, HERE/'coordinator', HERE/'userland-tools', HERE/'validation-tools', HERE/'installation-tools', HERE/'accounting-tools'):
        mapped.update(p.resolve() for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name != 'index.html')
    mapped.update(SOURCES); mapped.update((selected_path, ledger_path, Path(__file__).resolve()))
    mapped.discard(files['ledger'])  # Freeze the closed copy; keep the original only as snapshot provenance.
    artifacts = [{'id': 'file-'+hashlib.sha256(str(p).encode()).hexdigest()[:16], **ref(p)} for p in sorted(mapped)]
    settings = load(files['previous_controls'])['settings']
    index_path = output/'release-control-index-batch01-eval-r3.json'
    write(index_path, {'schema_version': 'batch01-release-control-index-3', 'release_id': RELEASE, 'recorded_at_utc': now,
        'settings': settings, 'artifact_files': artifacts, 'selected_runtime': str(RUNTIME), 'selected_coordinator': str(HERE/'coordinator/run_release_series.ps1'),
        'selected_investigation': str(INVESTIGATION), 'selected_analysis': str(ANALYSIS), 'queued_materialization_job': job['id'],
        'scope': 'Fresh fixed-environment release; retained r1/r2 provenance is historical, not a claim of live replayability'})
    freeze = copy.deepcopy(prior_freeze)
    freeze.update(release_id=RELEASE, frozen_at=datetime.now(timezone.utc).isoformat(),
        **{k: prepared[k] for k in ('code_sha256', 'environment_sha256', 'model_sha256', 'protocol_sha256', 'artifacts')},
        selection_criteria=selected['selection_rule']+' Full unchanged264-run fixed-environment replacement; no score-based policy tuning. Exact selection '+digest(selected_path)+'; controls '+digest(index_path)+'.',
        development_selection=ref(selected_path), control_index=ref(index_path))
    freeze_path=output/'freeze-batch01-eval-r3.json'; write(freeze_path,freeze)
    for path, checksum in list(SOURCES.items()): require(digest(path)==checksum, 'Input changed before final readiness: '+str(path))
    ready={'schema_version':'batch01-final-readiness-3','release_id':RELEASE,'recorded_at_utc':freeze['frozen_at'],
        'freeze_sha256':digest(freeze_path),'scored_ready':True,'gates':inputs['gates'],
        'gate_details':inputs['gate_details'],'root_acceptance':ref(inputs_path),'evidence_refs':[ref(index_path), *[{k:r[k] for k in ('path','sha256')} for r in artifacts]],
        'scope':'Only explicit root decisions and actual bound prerequisites; no seeds or scored success created'}
    ready_path=output/'readiness-batch01-eval-r3.json';write(ready_path,ready)
    protocol.validate_release_gates(freeze_path,ready_path)
    result={'schema_version':'batch01-r3-sealing-result-1','status':'complete','queue_job_id':job['id'],
        'selection':ref(selected_path),'control_index':ref(index_path),'freeze':ref(freeze_path),'readiness':ref(ready_path),
        'closed_ledger':ref(ledger_path),'direct_files':len(ready['evidence_refs']),'inputs_unchanged':True,'seeds_created':False,
        'official_queue_completion_verified':False}
    write(output/'sealed.json',result);print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True,help='Actual root-authored references, prerequisite acceptances and gates')
    parser.add_argument('--output-dir',type=Path,required=True,help='Fresh operator output directory under Batch01')
    main(parser.parse_args())
