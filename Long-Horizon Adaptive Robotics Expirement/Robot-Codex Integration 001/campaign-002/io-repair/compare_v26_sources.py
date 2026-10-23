"""Compare dev078 -> dev079 sources only, after the new freeze is authorized.

No queue, model, simulator, assessor or operator module is imported or called.
Existing reports are never replaced. A validation failure creates no report;
retain the caller's failed command receipt instead of retrying unchanged work.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import zipfile


IO = Path(__file__).resolve().parent
C = IO.parent
RCI = C.parent
REPO = RCI.parents[1]
MAP = RCI.parent / 'Architecture Map'
OUTPUT = IO / 'v26-source-change-inventory-001.json'
REPORT = OUTPUT.with_suffix('.md')
MAX_FILE = 16 * 1024 * 1024
MAX_ARCHIVE = 128 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_SOURCES = 10000
BASELINE_SHA = 'd84c510ee923a395417944e70a90ab1fa3759bc0061c2b6a4a714fb708f25581'
OLD_SHA = '13375ee3c4a252406ce00f18cc0d211775763d00e6eff4dbb477516afb879df6'
PRIOR_HOST_SHA = '10bc9fea95804c0707264a608881cab94b67cac65582e4c57bdf8cbc9c877a0e'
POLICY = {'model_requested': 'gpt-6-astra', 'reasoning_requested': 'max',
          'authentication_requested': 'existing ChatGPT subscription; no API key',
          'bootstrap': 'Follow the instructions in RobotAgentPrompt.md.'}
UNCHANGED_HARNESS = ('physical.py', 'run_host.py', 'physics_worker.py',
    'continuous_adapter.py', 'bootstrap_client_v4.py', 'native_quiescence.py',
    'native_cleanup_protocol.py', 'codehost_owner.py', 'codehost_bridge_v3.py',
    'codehost_inside_v3.py', 'codehost_entry_v3.py', 'codehost_mux_protocol.py',
    'executor_capture.py')


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key: ' + str(key))
        result[key] = value
    return result


def checked_path(path, root=REPO):
    path = Path(path)
    require(path.is_absolute(), 'Input path must be absolute: ' + str(path))
    root = root.resolve()
    require(path.resolve().is_relative_to(root), 'Input outside permitted tree: ' + str(path))
    require(path.is_file(), 'Missing input: ' + str(path))
    for item in (path, *path.parents):
        require(not item.is_symlink(), 'Symlink input: ' + str(item))
        if item == root:
            break
    return path.resolve()


def read_bytes(path, limit=MAX_FILE):
    path = checked_path(path)
    require(path.stat().st_size <= limit, 'Input exceeds byte bound: ' + str(path))
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, 'Input grew beyond byte bound: ' + str(path))
    return raw


def identity(path, raw=None, *, limit=MAX_FILE):
    path = checked_path(path)
    if raw is None:
        raw = read_bytes(path, limit)
    return {'path': str(path), 'sha256': digest(raw), 'bytes': len(raw)}


def document(path):
    raw = read_bytes(path)
    value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique,
                       parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    return value, identity(path, raw)


def source_path(name):
    require(isinstance(name, str) and '\\' not in name and ':' not in name,
            'Invalid source path')
    parts = PurePosixPath(name)
    require(not parts.is_absolute() and parts.as_posix() == name
            and all(part not in ('', '.', '..') for part in name.split('/')),
            'Noncanonical source path: ' + name)
    return REPO / name


def source_identity(raw):
    return {'sha256': digest(raw), 'bytes': len(raw)}


def load_snapshot(revision, expected_sha=None, expected_run=None):
    path = MAP / 'releases' / revision / 'snapshot.json'
    value, binding = document(path)
    require(expected_sha is None or binding['sha256'] == expected_sha,
            'Historical snapshot identity changed: ' + revision)
    require(value.get('schema') == 'robot-codex-readiness-source-1'
            and value.get('revision') == revision, 'Wrong source snapshot: ' + revision)
    require(expected_run is None or value.get('run_id') == expected_run,
            'Wrong source role: ' + revision)
    sources = value.get('sources')
    require(isinstance(sources, dict) and 0 < len(sources) <= MAX_SOURCES,
            'Source inventory count bound')
    for name, item in sources.items():
        source_path(name)
        require(isinstance(item, dict) and set(item) == {'sha256', 'bytes'}
                and isinstance(item['sha256'], str)
                and re.fullmatch('[0-9a-f]{64}', item['sha256'])
                and type(item['bytes']) is int and 0 <= item['bytes'] <= MAX_FILE,
                'Invalid source binding: ' + name)
    require(sum(x['bytes'] for x in sources.values()) <= MAX_TOTAL, 'Source total byte bound')
    return value, binding


def verify_archive(snapshot, binding):
    path = Path(binding['path']).with_name('code.zip')
    archive_binding = identity(path, limit=MAX_ARCHIVE)
    observed = {}
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        names = [item.filename for item in members]
        require(len(names) == len(set(names)), 'Duplicate archive members')
        require(set(names) == set(snapshot['sources']), 'Archive member set differs from snapshot')
        require(sum(item.file_size for item in members) <= MAX_TOTAL, 'Archive expansion bound')
        for item in members:
            expected = snapshot['sources'][item.filename]
            require(not item.is_dir() and item.file_size == expected['bytes']
                    and item.file_size <= MAX_FILE, 'Archive member size differs: ' + item.filename)
            with archive.open(item) as stream:
                raw = stream.read(MAX_FILE + 1)
            observed[item.filename] = source_identity(raw)
            require(observed[item.filename] == expected, 'Archive member identity differs: ' + item.filename)
    require(identity(path, limit=MAX_ARCHIVE) == archive_binding, 'Archive changed during verification')
    return {'identity': archive_binding, 'source_count': len(observed),
            'listed_bytes': sum(x['bytes'] for x in observed.values()),
            'all_sources_match': True, 'errors': [], 'observed_members': observed,
            'observed_member_identity_map_sha256': digest(canonical(observed)),
            'exact_member_set': True, 'duplicate_member_count': 0}


def current_sources(sources):
    observed = {}
    for name, expected in sources.items():
        observed[name] = source_identity(read_bytes(source_path(name)))
        require(observed[name] == expected, 'Current source differs: ' + name)
    return observed


def checked_binding(item, root=REPO):
    require(isinstance(item, dict) and {'path', 'sha256'} <= set(item), 'Malformed receipt binding')
    path = checked_path(Path(item['path']), root)
    observed = identity(path)
    require(observed['sha256'] == item['sha256']
            and ('bytes' not in item or observed['bytes'] == item['bytes']),
            'Receipt input changed: ' + str(path))
    return observed


def development_check(path):
    path = checked_path(Path(path).resolve(), IO)
    value, binding = document(path)
    require(value.get('passed') is True, 'Development check did not pass: ' + str(path))
    if 'exit_code' in value:
        require(type(value['exit_code']) is int and value['exit_code'] == 0,
                'Development command exit differs')
    commands = value.get('commands', [])
    require(isinstance(commands, list), 'Malformed development commands')
    command_bindings = []
    for command in commands:
        require(type(command.get('exit_code')) is int and command['exit_code'] == 0,
                'Failed development command')
        for key in ('stdout', 'stderr'):
            command_bindings.append(checked_binding(command[key], IO))
    sources = value.get('source_bindings')
    require(isinstance(sources, (dict, list)) and sources, 'Missing development source bindings')
    if isinstance(sources, dict):
        inputs = [{'path': str(C / name), **item} for name, item in sources.items()]
    else:
        inputs = sources
    observed = [checked_binding(item) for item in inputs]
    require(len({x['path'] for x in observed}) == len(observed), 'Duplicate development source binding')
    return {'receipt': binding, 'passed': True, 'current_source_bindings': observed,
            'command_output_bindings': command_bindings}


def repair_checks(snapshot_binding, frozen_sources):
    path = IO / 'checks-029/repair-test-receipt.json'
    value, binding = document(path)
    require(value.get('schema') == 'campaign002-repair-test-receipt-1'
            and value.get('passed') is True, 'Bound full repair checks did not pass')
    require(value.get('source_snapshot') == {k: snapshot_binding[k] for k in ('path', 'sha256')},
            'Full repair checks bind a different freeze')
    execution, execution_binding = document(path.with_name('test-execution.json'))
    require(execution.get('passed') is True and execution.get('commands') == value.get('commands'),
            'Full repair test execution/receipt differs')
    commands = value.get('commands')
    require(isinstance(commands, list) and len(commands) == 2, 'Both full repair commands are required')
    inputs, outputs = [], []
    for command, directory in zip(commands, (C / 'harness', C / 'assessment')):
        expected_argv = [str(REPO / 'venv/Scripts/python.exe'), '-X', 'utf8', '-B',
                         '-m', 'unittest', 'discover', '-s', str(directory), '-p', 'test_*.py', '-v']
        require(type(command.get('exit_code')) is int and command['exit_code'] == 0
                and command.get('test_sources_unchanged') is True
                and command.get('argv') == expected_argv, 'Failed/changed full repair command')
        require(command.get('test_inputs'), 'Repair command omits inputs')
        actual = [checked_binding(item) for item in command['test_inputs']]
        require(len({x['path'] for x in actual}) == len(actual)
                and {x['path'] for x in actual} == {str(p.resolve()) for p in directory.glob('test_*.py') if p.is_file()},
                'Full repair test discovery set changed')
        for item in actual:
            name = Path(item['path']).relative_to(REPO).as_posix()
            require(frozen_sources.get(name) == {key: item[key] for key in ('sha256', 'bytes')},
                    'Full repair test input differs from freeze: ' + name)
        inputs.extend(actual)
        outputs.extend(checked_binding(command[k], IO) for k in ('stdout', 'stderr'))
    state, state_binding = document(IO / 'checks-029-source-state.json')
    require(state.get('passed') is True and state.get('sources_unchanged') is True
            and state.get('tests') == {key: execution_binding[key] for key in ('path', 'sha256')},
            'Full production source-state receipt differs from passing execution')
    require(isinstance(state.get('sources'), list) and state['sources'], 'Missing full production source state')
    production = [checked_binding(item) for item in state['sources']]
    expected = {str(p.resolve()) for folder in ('harness', 'assessment', 'qualification', 'admission')
                for p in (C / folder).glob('*.py')}
    expected.update(str(p.resolve()) for p in C.glob('*.py'))
    require(len({x['path'] for x in production}) == len(production)
            and {x['path'] for x in production} == expected, 'Full production source set changed')
    return {'receipt': binding, 'test_execution': execution_binding, 'passed': True,
            'current_test_inputs': inputs, 'output_bindings': outputs,
            'source_state': state_binding, 'current_production_inputs': production}


def runtime_parts(raw):
    tree = ast.parse(raw.decode('utf-8-sig'))
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Runtime']
    require(len(classes) == 1, 'Ambiguous Runtime class')
    methods = {node.name: node for node in classes[0].body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    mirror = methods['_mirror_loop']
    assignments = {name: [node for node in ast.walk(mirror) if isinstance(node, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)]
                   for name in ('script', 'files')}
    calls = [node for node in ast.walk(mirror) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == 'linux']
    require(all(len(items) == 1 for items in assignments.values()) and len(calls) == 1,
            'Mirror publication AST is ambiguous')
    script = assignments['script'][0].value
    require(isinstance(script, ast.Constant) and isinstance(script.value, str), 'Mirror script is not literal')
    return {'mirror_publish_script_sha256': digest(script.value.encode('utf-8')),
            'mirror_files_expression_ast_sha256': digest(ast.dump(assignments['files'][0].value).encode()),
            'mirror_linux_call_ast_sha256': digest(ast.dump(calls[0]).encode()),
            'init_ast_sha256': digest(ast.dump(methods['__init__']).encode())}


def publisher_parity(old, new, old_archive, new_archive):
    runtime_name = (C / 'harness/runtime.py').relative_to(REPO).as_posix()
    path = IO / 'epoch-mirror-source-binding-development-001/receipt.json'
    receipt, binding = document(path)
    declared, declared_binding = document(IO / 'epoch-revocation-development-001/source-parity.json')
    require(receipt.get('passed') is True and type(receipt.get('exit_code')) is int
            and receipt['exit_code'] == 0 and receipt.get('publisher_ast_equal') is True
            and receipt.get('literal_other_ast_equal') is True, 'Publisher parity check failed')
    require(receipt.get('old_runtime_sha256') == old['sources'][runtime_name]['sha256']
            and receipt.get('new_runtime_sha256') == new['sources'][runtime_name]['sha256'],
            'Publisher parity runtime identities differ')
    parts = []
    for archive in (old_archive, new_archive):
        with zipfile.ZipFile(archive['identity']['path']) as source:
            parts.append(runtime_parts(source.read(runtime_name)))
    require(parts[0] == parts[1], 'Successful mirror publication/restore setup AST changed')
    require(declared.get('publication_parts_identical') is True
            and declared.get('restore_and_prepare_workspace_unchanged_via_init_AST') is True,
            'Prior runtime parity report is not passing')
    for key in ('mirror_publish_script_sha256', 'mirror_files_expression_ast_sha256',
                'mirror_linux_call_ast_sha256'):
        require(declared.get(key) == parts[1][key], 'Actual publisher differs from retained parity: ' + key)
    literal_name = (C / 'assessment/literal_read_segments.py').relative_to(REPO).as_posix()
    require(receipt.get('literal_before_sha256') == old['sources'][literal_name]['sha256']
            and receipt.get('literal_after_sha256') == new['sources'][literal_name]['sha256'],
            'Literal source-pin checkpoint is stale')
    return {'receipt': binding, 'runtime_parity_receipt': declared_binding,
            'recomputed_parts': parts[1], 'publication_and_init_ast_equal': True,
            'runtime_whole_file_unchanged': old['sources'][runtime_name] == new['sources'][runtime_name],
            'scope': 'Only successful publication and Runtime.__init__ parity; request capture and revocation changed.'}


def classification(name):
    if Path(name).name.startswith('test_'):
        return 'test_fixture_or_regression'
    if name.endswith('/harness/runtime.py'):
        return 'protected_mirror_request_and_epoch_revocation_evidence'
    if '/assessment/' in name:
        return 'independent_assessment'
    if '/qualification/' in name or name.endswith('/harness/raw_event_preflight_v2.py'):
        return 'source_inventory_or_qualification'
    if '/io-repair/' in name:
        return 'declared_method_or_retained_source_evidence'
    return 'other_source_or_dependency'


def compare(args):
    require(not OUTPUT.exists() and not REPORT.exists(), 'Existing comparison output; reconcile without overwrite')
    baseline, baseline_id = load_snapshot('RCI001-wsl-010d', BASELINE_SHA)
    old, old_id = load_snapshot('RCI001-C02-dev-078', OLD_SHA, 'RCI001-C02-smoke-023')
    new, new_id = load_snapshot('RCI001-C02-dev-079', args.snapshot_sha256, 'RCI001-C02-host-probe-026')
    prior, prior_id = load_snapshot('RCI001-C02-dev-075', PRIOR_HOST_SHA, 'RCI001-C02-host-probe-025')
    require(len(baseline['sources']) == 624, 'Original source count differs')
    archives = {'078': verify_archive(old, old_id), '079': verify_archive(new, new_id)}
    old_sources, new_sources = old['sources'], new['sources']
    observed = current_sources(new_sources)
    originals = current_sources(baseline['sources'])
    for name, binding in baseline['sources'].items():
        require(old_sources.get(name) == new_sources.get(name) == binding,
                'Protected original source inventory changed: ' + name)
    unchanged = {name: old_sources[name] for name in sorted(old_sources.keys() & new_sources.keys())
                 if old_sources[name] == new_sources[name]}
    changed = {name: {'before': old_sources[name], 'after': new_sources[name],
                     'classification': classification(name)}
               for name in sorted(old_sources.keys() & new_sources.keys()) if name not in unchanged}
    added = {name: {**new_sources[name], 'classification': classification(name),
                    'new_to_snapshot_not_necessarily_new_file': True,
                    'in_prior_host_anchor_dev075': name in prior['sources'],
                    'prior_host_binding': prior['sources'].get(name)}
             for name in sorted(new_sources.keys() - old_sources.keys())}
    omitted = {}
    for name in sorted(old_sources.keys() - new_sources.keys()):
        now = source_identity(read_bytes(source_path(name)))
        require(now == old_sources[name], 'Omitted old source missing/changed: ' + name)
        omitted[name] = {'before': old_sources[name], 'current': now,
                         'still_present_and_byte_identical': True, 'classification': classification(name),
                         'scope': 'Omitted from host-anchor inventory; not deleted from disk.'}
    stable_harness = {}
    for filename in UNCHANGED_HARNESS:
        name = (C / 'harness' / filename).relative_to(REPO).as_posix()
        require(name in unchanged, 'Undeclared native/physical source change: ' + name)
        stable_harness[name] = unchanged[name]
    templates = {name: binding for name, binding in old_sources.items()
                 if any(part in name for part in ('/runtime-template/', '/smoke-template/', '/templates/',
                                                  'Robot Agent Filesystem v0.1/workspace/'))}
    require(templates and all(new_sources.get(name) == binding for name, binding in templates.items()),
            'Model/template source bytes changed')
    policy = {}
    for key, expected in POLICY.items():
        require(old.get(key) == new.get(key) == expected, 'Requested policy metadata changed: ' + key)
        policy[key] = {'before': old[key], 'after': new[key], 'equal': True}
    checks = {'publisher': publisher_parity(old, new, archives['078'], archives['079']),
              'lineage': development_check(args.lineage_checks),
              'root_integration': development_check(args.integration_checks),
              'operator': development_check(args.operator_checks),
              'full_repair': repair_checks(new_id, new_sources)}
    # Re-read all observed source inputs after the other bounded checks. A source
    # change during comparison must not produce a successful preservation claim.
    require(current_sources(new_sources) == observed and current_sources(baseline['sources']) == originals,
            'Current source changed during comparison')
    for name, item in omitted.items():
        require(source_identity(read_bytes(source_path(name))) == item['current'], 'Omitted source changed during check')
    for binding in (baseline_id, old_id, new_id, prior_id):
        require(identity(binding['path']) == binding, 'Snapshot changed during comparison')
    for archive in archives.values():
        require(identity(archive['identity']['path'], limit=MAX_ARCHIVE) == archive['identity'],
                'Archive changed during comparison')
    return {'schema': 'campaign002-v26-source-change-inventory-1',
        'created_utc': datetime.now(timezone.utc).isoformat(), 'verified': True, 'issues': [],
        'scope': 'Bounded source/archive comparison only; no empirical outcome reads, queue or model execution.',
        'comparison_script': identity(Path(__file__)),
        'snapshots': {'078': old_id, '079': new_id},
        'snapshot_roles': {'078': {'run_id': old['run_id'], 'revision': old['revision']},
                           '079': {'run_id': new['run_id'], 'revision': new['revision']}},
        'archives': archives,
        'counts': {'old': len(old_sources), 'new': len(new_sources), 'unchanged': len(unchanged),
                   'changed': len(changed), 'added_to_new_snapshot': len(added),
                   'removed_from_new_snapshot': len(omitted),
                   'omitted_still_on_disk_unchanged': len(omitted),
                   'additions_reintroduced_from_prior_host_anchor': sum(x['in_prior_host_anchor_dev075'] for x in added.values())},
        'changed_existing_sources': changed, 'added_source_inventory_entries': added,
        'omitted_from_host_anchor_snapshot': omitted,
        'prior_host_anchor_for_membership_context': prior_id,
        'unchanged_source_identity_map_sha256': digest(canonical(unchanged)),
        'current_frozen_sources': {'count': len(observed), 'all_match': True, 'errors': [],
                                   'observed_identity_map_sha256': digest(canonical(observed))},
        'protected624': {'baseline_snapshot': baseline_id, 'count': 624,
                         'identity_map_sha256': digest(canonical(baseline['sources'])),
                         'all_match_old_new_current': True, 'old_archive_all_match': True,
                         'new_archive_all_match': True, 'errors': [],
                         'observed_current_identity_map_sha256': digest(canonical(originals))},
        'snapshot_policy_metadata': policy,
        'snapshot_environment_identity': {'before_sha256': digest(canonical(old['environment'])),
            'after_sha256': digest(canonical(new['environment'])), 'equal': old['environment'] == new['environment'],
            'scope': 'Metadata comparison only; no native execution or attestation.'},
        'production_and_policy_preservation': {'unchanged_named_harness': stable_harness,
            'protected_template_count': len(templates), 'protected_templates_byte_identical': True,
            'template_sources': templates, 'runtime_publication_parity': checks['publisher']},
        'development_checks': checks,
        'limitations': ['Source membership additions/omissions do not establish file creation/deletion.',
            'The protected mirror runtime changed prospectively; only the explicitly compared publication/setup ASTs are equal.',
            'Passing development receipts are source-bound checks, not qualification or scientific outcomes.',
            'The separate preserve.py verify command owns the 1054 historical files and five canonical map prefixes.']}


def markdown(value):
    n = value['counts']
    lines = ['# V26 frozen source comparison', '',
        f"Source-only verification passed: dev078 ({n['old']} files) to dev079 ({n['new']} files). Both archives have exact member sets, no duplicates, and every member matches its snapshot. All new current sources and all {n['removed_from_new_snapshot']} omitted old entries were checked.", '',
        f"- {n['unchanged']} shared sources unchanged; {n['changed']} changed; {n['added_to_new_snapshot']} inventory additions.",
        '- All 624 original protected sources match both snapshots, both archives and current files.',
        '- The mirror runtime changed for request capture and epoch revocation. Its successful publication script, file mapping, Linux publication call and setup/restore method remain AST-identical.',
        '- Named native/physical sources, model templates and requested model/effort/authentication/bootstrap metadata remain unchanged.',
        '- Publisher parity, final lineage, root integration, operator checks and dev079-bound checks029 plus its complete production source state are separately bound.', '',
        'This is not qualification, a task outcome or an empirical reassessment. Inventory membership is not evidence of file creation or deletion. Historical artifact/prefix preservation remains a separate command.', '',
        '[Complete hash-bound receipt](v26-source-change-inventory-001.json)', '', 'Changed shared sources:', '']
    lines.extend('- `' + name + '` — ' + item['classification']
                 for name, item in value['changed_existing_sources'].items())
    return '\n'.join(lines) + '\n'


def write_new(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot-sha256', required=True, help='Caller-held exact new dev079 snapshot SHA256')
    parser.add_argument('--lineage-checks', type=Path,
        default=IO / 'revocation-readback-lineage-development-001/final-checks/receipt.json')
    parser.add_argument('--integration-checks', type=Path,
        default=IO / 'canary-readback-integration-development-001/check-001/receipt.json')
    parser.add_argument('--operator-checks', type=Path,
        default=IO / 'v26-operator-gates-development-002/receipt.json')
    args = parser.parse_args()
    require(re.fullmatch('[0-9a-f]{64}', args.snapshot_sha256), 'Exact new snapshot SHA256 required')
    value = compare(args)
    require(not OUTPUT.exists() and not REPORT.exists(), 'Output appeared during comparison')
    write_new(OUTPUT, (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8'))
    write_new(REPORT, markdown(value).encode('utf-8'))
    print(json.dumps({'verified': True, 'counts': value['counts'],
                      'json': identity(OUTPUT), 'report': identity(REPORT)}))


if __name__ == '__main__':
    main()
