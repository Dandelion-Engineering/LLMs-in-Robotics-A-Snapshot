"""Source-only dev082 -> dev083 verification; run only after the root freeze notice.

No queue, runtime, model, simulator or assessor is imported or executed.
The pinned V26 helper supplies only bounded file/archive/receipt utilities.
Outputs are exclusive; a failed command must be retained, never overwritten.
"""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import types
import zipfile

IO = Path(__file__).resolve().parent
C = IO.parent
REPO = C.parents[2]
OUTPUT = IO / 'v27-source-change-inventory-001.json'
REPORT = OUTPUT.with_suffix('.md')
UTILITY_SHA = '365fa3e9609333e6e78a7ea51b09a19ed0b78ba65526befac7c6b727bd38cc80'
OLD_SHA = 'ad4bf759df9dc2c7559ae2317b2633c701f53a44584286270625880e1121d7d3'
PRIOR_HOST_SHA = '299e8a03e54b1ac983a91b04f1670dfe557625d3eb06b6a8c5fa30f9456da884'
METHOD = 'io-repair/PREPARED_INDEX_LABELS_V1.md'
METHOD_SHA = '202f9ec2d4be550c9bf327a0263efeb73e0fa0c058922322b22a50b92eb84db2'
ASSESSMENT = {'assessment/prepared_result_segments.py',
              'assessment/test_prepared_result_segments.py',
              'assessment/test_prepared_startup_segments.py'}
SUPPLIERS = {'harness/raw_event_preflight_v2.py', 'qualification/prepare_native.py',
             'qualification/boundary_suite_v3.py', 'qualification/host_probe.py'}
LINEAGE_EXISTING = SUPPLIERS | {'qualification/test_prepare_native.py',
    'admission/prepare_certificate.py', 'admission/test_prepare_admission.py'}
LINEAGE_NEW = {'qualification/prepare_model_v19.py', 'qualification/test_prepare_model_v19.py',
              'qualification/run_final_qualification_v27.py',
              'qualification/test_run_final_qualification_v27.py'}
DIAGNOSIS_EXECUTABLES = {
    'io-repair/smoke-024-read-diagnosis-001/diagnose.py',
    'io-repair/smoke-024-read-diagnosis-001/execution-001/diagnose-failed.py',
}


def utilities():
    path = IO / 'compare_v26_sources.py'
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != UTILITY_SHA:
        raise ValueError('Pinned source utility changed')
    module = types.ModuleType('_pinned_source_inventory_utilities')
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def name(relative):
    return (C / relative).relative_to(REPO).as_posix()


def relative(source):
    prefix = C.relative_to(REPO).as_posix() + '/'
    return source[len(prefix):] if source.startswith(prefix) else None


def declared_diagnosis_sources(u, snapshot, archive, lineage_path):
    """Join only two retained diagnostic scripts; never execute their code."""
    lineage, lineage_binding = u.document(Path(lineage_path).resolve())
    u.require(lineage.get('schema') == 'campaign002-index-label-lineage-final-checks-1'
              and lineage.get('passed') is True, 'Unknown/unpassed lineage receipt')
    supplier = 'qualification/prepare_model_v19.py'
    with zipfile.ZipFile(archive['identity']['path']) as frozen:
        source = frozen.read(name(supplier))
        u.require(u.source_identity(source) == snapshot['sources'][name(supplier)]
                  == lineage['source_bindings'].get(supplier), 'Frozen supplier identity differs')
        assignments = [node for node in ast.parse(source.decode('utf-8-sig')).body
                       if isinstance(node, ast.Assign) and any(
                           isinstance(t, ast.Name) and t.id == 'INDEX_LABEL_INPUTS' for t in node.targets)]
        u.require(len(assignments) == 1 and isinstance(assignments[0].value, ast.Tuple)
                  and all(isinstance(x, ast.Constant) and isinstance(x.value, str)
                          for x in assignments[0].value.elts), 'Nonliteral/ambiguous index-label inputs')
        inputs = [x.value for x in assignments[0].value.elts]
        u.require(len(inputs) == len(set(inputs)), 'Duplicate index-label inputs')
        declared = {x for x in inputs if x.startswith('io-repair/') and x.endswith('.py')}
        u.require(declared == DIAGNOSIS_EXECUTABLES, 'Unexpected diagnostic executable inventory')
        members = {}
        for rel in sorted(declared):
            key = name(rel)
            observed = u.source_identity(frozen.read(key))
            u.require(observed == snapshot['sources'].get(key)
                      == lineage['provenance_bindings'].get(rel),
                      'Diagnostic snapshot/archive/provenance identity differs: ' + rel)
            members[key] = observed
    return {'supplier': {'path': name(supplier), **snapshot['sources'][name(supplier)]},
            'literal_inventory_name': 'INDEX_LABEL_INPUTS', 'lineage_receipt': lineage_binding,
            'exact_diagnostic_executable_members': members,
            'scope': 'Declared historical diagnostic code retained as source input only; never executed.'}


def supplier_parity(u, old, prior, new, archives):
    result = {}
    for rel in sorted(SUPPLIERS):
        key = name(rel)
        reference = '082' if key in old['sources'] else '079'
        expected = (old if reference == '082' else prior)['sources'].get(key)
        u.require(expected is not None and key in new['sources'], 'Missing supplier baseline: ' + rel)
        with zipfile.ZipFile(archives[reference]['identity']['path']) as archive:
            before = archive.read(key)
        after = u.read_bytes(C / rel)
        tree = ast.parse(before.decode('utf-8-sig'))
        counts = {'supplier': 0, 'inputs': 0, 'method_tuple': 0}
        class InventoryOnly(ast.NodeTransformer):
            def visit_Constant(self, node):
                if node.value == 'prepare_model_v18.py':
                    counts['supplier'] += 1
                    node.value = 'prepare_model_v19.py'
                return node
            def visit_Attribute(self, node):
                self.generic_visit(node)
                if node.attr == 'revocation_readback_inputs':
                    u.require(isinstance(node.value, ast.Name) and node.value.id == 'extra',
                              'Unexpected source supplier receiver')
                    counts['inputs'] += 1
                    node.attr = 'index_label_inputs'
                return node
            def visit_Assign(self, node):
                self.generic_visit(node)
                if rel == 'qualification/prepare_native.py' and any(
                        isinstance(t, ast.Name) and t.id == 'METHOD_FILES' for t in node.targets):
                    u.require(isinstance(node.value, ast.Tuple) and all(
                        isinstance(x, ast.Constant) and isinstance(x.value, str) for x in node.value.elts),
                        'Unexpected native method inventory')
                    u.require(METHOD not in [x.value for x in node.value.elts], 'Method already in baseline')
                    node.value.elts.append(ast.Constant(METHOD))
                    counts['method_tuple'] += 1
                return node
        transformed = InventoryOnly().visit(tree)
        u.require(counts == {'supplier': 1, 'inputs': 1,
                            'method_tuple': int(rel == 'qualification/prepare_native.py')},
                  'Supplier rewrite cardinality differs: ' + rel)
        u.require(ast.dump(transformed, include_attributes=False) ==
                  ast.dump(ast.parse(after.decode('utf-8-sig')), include_attributes=False),
                  'Non-inventory supplier AST changed: ' + rel)
        result[rel] = {'reference_revision': 'dev' + reference, 'before': expected,
                      'after': new['sources'][key], 'only_declared_inventory_ast_changes': True,
                      'rewrite_counts': counts}
    return result


def bound_sources(u, value, field):
    sources = value.get(field)
    u.require(isinstance(sources, (dict, list)) and sources, 'Missing receipt source bindings')
    items = ([{'path': str(C / key), **item} for key, item in sources.items()]
             if isinstance(sources, dict) else sources)
    observed = [u.checked_binding(item) for item in items]
    u.require(len({x['path'] for x in observed}) == len(observed), 'Duplicate receipt source')
    return observed


def development(u, path, required, parser=False):
    path = u.checked_path(Path(path).resolve(), IO)
    value, binding = u.document(path)
    u.require(value.get('passed') is True, 'Development receipt is not passing')
    if 'exit_code' in value:
        u.require(type(value['exit_code']) is int and value['exit_code'] == 0, 'Nonzero receipt exit')
    historical = []
    if parser:
        u.require(value.get('schema') == 'campaign002-prepared-index-label-development-1',
                  'Unknown parser development schema')
        pairs = value.get('source_before_after')
        u.require(isinstance(pairs, list) and len(pairs) == len(ASSESSMENT), 'Parser source census differs')
        observed = [u.checked_binding(x['after']) for x in pairs]
        historical = [u.checked_binding(x['before'], IO) for x in pairs]
        u.require(len({x['path'] for x in observed}) == len(observed), 'Duplicate parser source')
    else:
        observed = bound_sources(u, value, 'source_bindings')
    u.require({str((C / rel).resolve()) for rel in required} <= {x['path'] for x in observed},
              'Development receipt omits required current sources')
    evidence = []
    for key in ('passing_checks',):
        for item in value.get(key, []):
            evidence.append(u.checked_binding(item, IO))
    for key in ('final_check', 'parity', 'source_parity', 'source_diff', 'declaration'):
        if isinstance(value.get(key), dict) and 'path' in value[key]:
            evidence.append(u.checked_binding(value[key], IO))
    parity_item = value.get('source_parity' if parser else 'parity')
    u.require(isinstance(parity_item, dict) and 'path' in parity_item, 'Missing source parity receipt')
    parity, _ = u.document(Path(parity_item['path']))
    u.require(parity.get('passed') is True, 'Source parity receipt did not pass')
    if parser:
        u.require(parity.get('all_other_module_nodes_ast_equal') is True,
                  'Undeclared parser AST change')
        green = u.checked_binding(value['tests']['green'], IO)
        test, _ = u.document(Path(green['path']))
        u.require(type(test.get('exit_code')) is int and test['exit_code'] == 0,
                  'Parser focused check did not pass')
        evidence.append(green)
    else:
        u.require(parity.get('checks') and all(x is True for x in parity['checks'].values()),
                  'A lineage policy/parity check failed')
        bound_sources(u, parity, 'source_bindings')
    return {'receipt': binding, 'passed': True, 'current_source_bindings': observed,
            'historical_source_bindings': historical, 'supporting_receipt_bindings': evidence,
            'scope': 'Retained development receipt, not qualification or outcome replay.'}


def repair_checks(u, snapshot, frozen):
    path = IO / 'checks-030/repair-test-receipt.json'
    value, binding = u.document(path)
    u.require(value.get('schema') == 'campaign002-repair-test-receipt-1' and value.get('passed') is True,
              'Full repair checks did not pass')
    u.require(value.get('source_snapshot') == {k: snapshot[k] for k in ('path', 'sha256')},
              'Repair checks bind a different freeze')
    execution, execution_binding = u.document(path.with_name('test-execution.json'))
    u.require(execution.get('passed') is True and execution.get('commands') == value.get('commands'),
              'Full execution/receipt differs')
    commands = value.get('commands')
    u.require(isinstance(commands, list) and len(commands) == 2, 'Both full commands required')
    inputs, outputs = [], []
    for command, directory in zip(commands, (C / 'harness', C / 'assessment')):
        argv = [str(REPO / 'venv/Scripts/python.exe'), '-X', 'utf8', '-B', '-m', 'unittest',
                'discover', '-s', str(directory), '-p', 'test_*.py', '-v']
        u.require(type(command.get('exit_code')) is int and command['exit_code'] == 0
                  and command.get('test_sources_unchanged') is True and command.get('argv') == argv,
                  'Failed/changed full repair command')
        actual = [u.checked_binding(item) for item in command['test_inputs']]
        u.require(len({x['path'] for x in actual}) == len(actual) and
                  {x['path'] for x in actual} == {str(p.resolve()) for p in directory.glob('test_*.py') if p.is_file()},
                  'Test discovery differs')
        for item in actual:
            key = Path(item['path']).relative_to(REPO).as_posix()
            u.require(frozen.get(key) == {k: item[k] for k in ('sha256', 'bytes')},
                      'Test input differs from freeze: ' + key)
        inputs.extend(actual)
        outputs.extend(u.checked_binding(command[k], IO) for k in ('stdout', 'stderr'))
    state, state_binding = u.document(IO / 'checks-030-source-state.json')
    u.require(state.get('passed') is True and state.get('sources_unchanged') is True
              and state.get('tests') == {k: execution_binding[k] for k in ('path', 'sha256')},
              'Source-state does not bind passing full checks')
    production = [u.checked_binding(item) for item in state['sources']]
    expected = {str(p.resolve()) for folder in ('harness', 'assessment', 'qualification', 'admission')
                for p in (C / folder).glob('*.py')} | {str(p.resolve()) for p in C.glob('*.py')}
    u.require(len({x['path'] for x in production}) == len(production)
              and {x['path'] for x in production} == expected, 'Production source census differs')
    for item in production:
        key = Path(item['path']).relative_to(REPO).as_posix()
        if key in frozen:
            u.require(frozen[key] == {k: item[k] for k in ('sha256', 'bytes')},
                      'Production source differs from freeze')
    return {'receipt': binding, 'execution': execution_binding, 'source_state': state_binding,
            'passed': True, 'test_inputs': inputs, 'output_bindings': outputs,
            'production_inputs': production}


def compare(args):
    u = utilities()
    u.require(not OUTPUT.exists() and not REPORT.exists(), 'Existing report; reconcile, do not overwrite')
    baseline, baseline_id = u.load_snapshot('RCI001-wsl-010d', u.BASELINE_SHA)
    old, old_id = u.load_snapshot('RCI001-C02-dev-082', OLD_SHA, 'RCI001-C02-smoke-024')
    new, new_id = u.load_snapshot('RCI001-C02-dev-083', args.snapshot_sha256, 'RCI001-C02-host-probe-027')
    prior, prior_id = u.load_snapshot('RCI001-C02-dev-079', PRIOR_HOST_SHA, 'RCI001-C02-host-probe-026')
    u.require(len(baseline['sources']) == 624, 'Original source count differs')
    archives = {rev: u.verify_archive(snap, binding) for rev, snap, binding in
                [('082', old, old_id), ('083', new, new_id), ('079', prior, prior_id)]}
    for snap in (old, new, prior):
        keys = list(snap['sources'])
        u.require(len(keys) == len({key.casefold() for key in keys}), 'Case-alias source/archive paths')
    a, b = old['sources'], new['sources']
    observed = u.current_sources(b); originals = u.current_sources(baseline['sources'])
    u.require(all(a.get(k) == b.get(k) == v for k, v in baseline['sources'].items()),
              'Original624 differs in inventories')
    unchanged = {k: a[k] for k in sorted(a.keys() & b.keys()) if a[k] == b[k]}
    changed = {k: {'before': a[k], 'after': b[k]} for k in sorted(a.keys() & b.keys()) if a[k] != b[k]}
    added = {k: {'after': b[k], 'prior_host_binding': prior['sources'].get(k),
                 'reintroduced_from_prior_host': k in prior['sources']} for k in sorted(b.keys() - a.keys())}
    omitted = {}
    for key in sorted(a.keys() - b.keys()):
        item = u.source_identity(u.read_bytes(u.source_path(key)))
        u.require(item == a[key], 'Omitted source missing/changed: ' + key)
        omitted[key] = {'before': a[key], 'current': item, 'still_present_and_byte_identical': True}
    allowed = ASSESSMENT | LINEAGE_EXISTING
    u.require(all(relative(k) in allowed for k in changed), 'Undeclared shared source change')
    diagnosis = declared_diagnosis_sources(u, new, archives['083'], args.lineage_checks)
    for key, item in added.items():
        if key.endswith('.py'):
            u.require(relative(key) in LINEAGE_NEW or
                      key in diagnosis['exact_diagnostic_executable_members'] or
                      (item['prior_host_binding'] is not None and
                       (item['prior_host_binding'] == item['after'] or relative(key) in LINEAGE_EXISTING)),
                      'Undeclared added executable source: ' + key)
    for folder in ('harness', 'assessment'):
        old_set = {k for k in a if relative(k) and relative(k).startswith(folder + '/')}
        new_set = {k for k in b if relative(k) and relative(k).startswith(folder + '/')}
        u.require(old_set == new_set, 'Unexpected harness/assessment membership change')
    templates = {k: v for k, v in a.items() if any(part in k for part in
                 ('/runtime-template/', '/smoke-template/', '/templates/', 'Robot Agent Filesystem v0.1/workspace/'))}
    u.require(templates and all(b.get(k) == v for k, v in templates.items()), 'Protected templates changed')
    policy = {}
    for key, expected in u.POLICY.items():
        u.require(old.get(key) == new.get(key) == expected, 'Requested policy changed: ' + key)
        policy[key] = {'before': old[key], 'after': new[key], 'equal': True}
    method = u.identity(C / METHOD)
    u.require(method['sha256'] == METHOD_SHA and b.get(name(METHOD)) ==
              {k: method[k] for k in ('sha256', 'bytes')}, 'Declared method not frozen exactly')
    checks = {'lineage': development(u, args.lineage_checks, LINEAGE_EXISTING | LINEAGE_NEW),
              'parser': development(u, args.parser_checks, ASSESSMENT, parser=True),
              'full_repair': repair_checks(u, new_id, b)}
    for item in checks['parser']['historical_source_bindings']:
        key = name('assessment/' + Path(item['path']).name)
        u.require(a.get(key) == {k: item[k] for k in ('sha256', 'bytes')},
                  'Parser baseline differs from executed dev082 source')
    suppliers = supplier_parity(u, old, prior, new, archives)
    for key, item in changed.items():
        rel = relative(key)
        item['classification'] = ('assessment_regression' if rel in ASSESSMENT and Path(rel).name.startswith('test_')
            else 'prepared_result_label_parser' if rel in ASSESSMENT
            else 'inventory_only_supplier' if rel in SUPPLIERS else 'lineage_or_certificate_development')
    u.require(u.current_sources(b) == observed and u.current_sources(baseline['sources']) == originals,
              'Current source changed during comparison')
    for key, item in omitted.items():
        u.require(u.source_identity(u.read_bytes(u.source_path(key))) == item['current'], 'Omitted source changed')
    for item in (baseline_id, old_id, new_id, prior_id, method):
        u.require(u.identity(item['path']) == item, 'Input changed during comparison')
    for archive in archives.values():
        u.require(u.identity(archive['identity']['path'], limit=u.MAX_ARCHIVE) == archive['identity'],
                  'Archive changed during comparison')
    for check in (checks['lineage'], checks['parser']):
        for item in [check['receipt'], *check['current_source_bindings'],
                     *check['historical_source_bindings'], *check['supporting_receipt_bindings']]:
            u.require(u.identity(item['path']) == item, 'Development input changed during comparison')
    return {'schema': 'campaign002-v27-source-change-inventory-1', 'verified': True, 'issues': [],
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Source-only inventory and bounded AST comparison; no qualification or empirical replay.',
        'comparison_script': u.identity(Path(__file__)), 'pinned_utilities': u.identity(IO / 'compare_v26_sources.py'),
        'snapshots': {'082': old_id, '083': new_id}, 'prior_host_membership_context': prior_id,
        'archives': archives, 'method': method,
        'counts': {'old': len(a), 'new': len(b), 'unchanged': len(unchanged), 'changed': len(changed),
                   'added_to_new_snapshot': len(added), 'omitted_from_new_snapshot': len(omitted),
                   'omitted_still_on_disk_unchanged': len(omitted),
                   'reintroduced_from_prior_host': sum(x['reintroduced_from_prior_host'] for x in added.values())},
        'changed_existing_sources': changed, 'added_source_inventory_entries': added,
        'omitted_from_host_anchor_snapshot': omitted,
        'current_frozen_sources': {'count': len(observed), 'all_match': True,
                                  'identity_map_sha256': u.digest(u.canonical(observed))},
        'protected624': {'baseline_snapshot': baseline_id, 'count': 624,
                         'all_match_old_new_archives_current': True, 'identity_map_sha256': u.digest(u.canonical(originals))},
        'preservation': {'all_other_harness_runtime_bytes_unchanged': True,
                         'assessment_changes_limited_to_declared_parser_and_tests': True,
                         'supplier_ast_parity': suppliers, 'template_sources_unchanged': templates,
                         'requested_policy': policy,
                         'environment_metadata_equal': old['environment'] == new['environment']},
        'development_checks': checks, 'declared_diagnosis_executable_join': diagnosis,
        'limitations': ['Inventory addition/omission is not evidence of file creation/deletion.',
                       'Supplier AST parity excludes only the exact declared inventory rewrites.',
                       'Other lineage/certificate behavior is covered by bound development receipts, not a blanket AST-equivalence claim.',
                       'No native/model/physics execution, historical verdict revision or qualification claim.',
                       'Historical1054/map-prefix verification remains the separate preservation workflow.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot-sha256', required=True)
    parser.add_argument('--lineage-checks', type=Path, default=IO / 'index-label-lineage-development-001/final-checks/receipt.json')
    parser.add_argument('--parser-checks', type=Path,
                        default=IO / 'prepared-index-label-development-001/receipt.json')
    args = parser.parse_args()
    if not re.fullmatch('[0-9a-f]{64}', args.snapshot_sha256):
        raise ValueError('Exact dev083 snapshot SHA256 required')
    value = compare(args); u = utilities(); n = value['counts']
    lines = ['# V27 frozen source comparison', '',
        f"Source-only verification: dev082 ({n['old']} entries) to dev083 ({n['new']}). Exact archive members, bytes, current sources and all624 original sources match their identities.", '',
        f"{n['unchanged']} shared unchanged; {n['changed']} changed; {n['added_to_new_snapshot']} additions; {n['omitted_from_new_snapshot']} omitted entries remain on disk unchanged.", '',
        'Harness/runtime behavior is byte-identical except the exactly checked inventory supplier. Assessment changes are confined to the prepared-result label parser and declared tests. New lineage, method and checks030 receipts are bound separately. This is not qualification.', '',
        '[Complete receipt](v27-source-change-inventory-001.json)', '', 'Changed shared sources:', '']
    lines.extend('- `' + key + '` — ' + item['classification'] for key, item in value['changed_existing_sources'].items())
    u.require(not OUTPUT.exists() and not REPORT.exists(), 'Output appeared during comparison')
    u.write_new(OUTPUT, (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode())
    u.write_new(REPORT, ('\n'.join(lines) + '\n').encode())
    print(json.dumps({'verified': True, 'counts': n, 'json': u.identity(OUTPUT), 'report': u.identity(REPORT)}))


if __name__ == '__main__':
    main()
