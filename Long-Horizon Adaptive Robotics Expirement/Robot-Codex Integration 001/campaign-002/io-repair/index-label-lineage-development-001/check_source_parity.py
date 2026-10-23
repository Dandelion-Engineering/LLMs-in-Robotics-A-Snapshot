"""Source-only bounded parity for the V27 external lineage and suppliers."""
from pathlib import Path
import ast
import difflib
import hashlib
import json

D = Path(__file__).resolve().parent
C = D.parents[1]
B = D / 'before'
METHOD = 'io-repair/PREPARED_INDEX_LABELS_V1.md'


def binding(path):
    raw = path.read_bytes()
    return {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def dump(source):
    return ast.dump(ast.parse(source), include_attributes=False)


def main():
    before = json.loads((D / 'before-and-absence.json').read_bytes())
    checks = {}
    for name in before['historical_files']:
        checks['historical_bytes:' + name] = (C / name).read_bytes() == (B / name).read_bytes()
    for name in ('qualification/prepare_native.py', 'qualification/host_probe.py',
                 'qualification/boundary_suite_v3.py', 'harness/raw_event_preflight_v2.py'):
        current = (C / name).read_text(encoding='utf-8')
        reverse = current.replace('prepare_model_v19.py', 'prepare_model_v18.py').replace(
            'extra.index_label_inputs()', 'extra.revocation_readback_inputs()')
        if name.endswith('prepare_native.py'):
            reverse = reverse.replace(",\n              '" + METHOD + "'", '')
        checks['supplier_AST_only:' + name] = dump(reverse) == dump((B / name).read_bytes())

    replacements = {
        'v27': 'v26', 'V27': 'V26', 'prepare_model_v19': 'prepare_model_v18',
        'final-qualification-027': 'final-qualification-026',
        'raw-preflight-017': 'raw-preflight-016', 'transport-probe-020': 'transport-probe-019',
        'host-probe-027': 'host-probe-026', 'native-026': 'native-025',
        'boundary-027': 'boundary-026', 'smoke-025': 'smoke-024',
        'pilot-stock-024': 'pilot-stock-023', 'pilot-home-024': 'pilot-home-023',
        'dev-083': 'dev-079', 'dev-084': 'dev-080', 'dev-085': 'dev-081', 'dev-086': 'dev-082',
        'dev083': 'dev079', 'dev084': 'dev080', 'dev085': 'dev081', 'dev086': 'dev082'}
    import re
    pattern = re.compile('|'.join(map(re.escape, sorted(replacements, key=len, reverse=True))))

    class Reverse(ast.NodeTransformer):
        def visit_Constant(self, node):
            if isinstance(node.value, str):
                node.value = pattern.sub(lambda match: replacements[match.group()], node.value)
            elif type(node.value) is int and node.value in (83, 84, 85, 86):
                node.value -= 4
            return node

        def visit_Expr(self, node):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return None  # Documentation only; complete source diff is retained.
            if 'PREPARED_INDEX_LABELS_METHOD' in ast.dump(node):
                # Exactly the new require call; preflight is inside a function return expression,
                # so it is not skipped and its list is normalized below.
                if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) \
                        and node.value.func.id == 'require':
                    return None
            return self.generic_visit(node)

        def visit_Assign(self, node):
            if any(isinstance(target, ast.Name) and target.id == 'PREPARED_INDEX_LABELS_METHOD'
                   for target in node.targets):
                return None
            return self.generic_visit(node)

        def visit_Tuple(self, node):
            node.elts = [item for item in node.elts if not
                         (isinstance(item, ast.Name) and item.id == 'PREPARED_INDEX_LABELS_METHOD')]
            return self.generic_visit(node)

        def visit_Dict(self, node):
            omit = {'prepared_index_labels_method', 'smoke024_read_diagnosis', 'smoke024_read_diagnosis_report'}
            pairs = [(key, value) for key, value in zip(node.keys, node.values)
                     if not (isinstance(key, ast.Constant) and key.value in omit)]
            node.keys = [p[0] for p in pairs]
            node.values = [p[1] for p in pairs]
            return self.generic_visit(node)

    class RemoveDoc(ast.NodeTransformer):
        def visit_Expr(self, node):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return None
            return self.generic_visit(node)

    for old, new in (('qualification/run_final_qualification_v26.py', 'qualification/run_final_qualification_v27.py'),
                     ('admission/prepare_certificate.py', 'admission/prepare_certificate.py')):
        left = ast.dump(RemoveDoc().visit(ast.parse((B / old).read_bytes())), include_attributes=False)
        right = ast.dump(Reverse().visit(ast.parse((C / new).read_bytes())), include_attributes=False)
        checks['production_AST_identity_inventory_only:' + new] = left == right
    tree = ast.parse((C / 'qualification/run_final_qualification_v27.py').read_bytes())
    methods = [node.value.right.value for node in tree.body if isinstance(node, ast.Assign)
               and isinstance(node.value, ast.BinOp) and any(isinstance(t, ast.Name)
               and t.id.endswith('_METHOD') for t in node.targets)]
    checks['new_method_once'] = methods.count(METHOD) == 1
    checks['fixed_PLAN_seed_guard_present'] = "('native-026', 'native', 24000)" in (
        C / 'qualification/run_final_qualification_v27.py').read_text(encoding='utf-8')
    files = before['owned_existing_files'] + before['new_files']
    diff = []
    old_names = {'qualification/prepare_model_v19.py': 'qualification/prepare_model_v18.py',
                 'qualification/test_prepare_model_v19.py': 'qualification/test_prepare_model_v18.py',
                 'qualification/run_final_qualification_v27.py': 'qualification/run_final_qualification_v26.py',
                 'qualification/test_run_final_qualification_v27.py': 'qualification/test_run_final_qualification_v26.py'}
    for name in files:
        old = old_names.get(name, name)
        diff.extend(difflib.unified_diff((B / old).read_text(encoding='utf-8').splitlines(True),
                    (C / name).read_text(encoding='utf-8').splitlines(True), fromfile='before/' + old, tofile=name))
    diff_path = D / 'source-parity-001.diff'
    with diff_path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(''.join(diff))
    result = {'schema': 'campaign002-lineage-source-parity-1', 'passed': all(checks.values()),
              'checks': checks, 'coordinator_method_count': len(methods),
              'shared_methods_with_transport_base': len(methods) + 1,
              'source_bindings': {name: {k: binding(C / name)[k] for k in ('sha256', 'bytes')} for name in files},
              'before': binding(D / 'before-and-absence.json'), 'diff': binding(diff_path),
              'scope': 'Source and deterministic policy parity only; no runtime, outcome, model, queue or registry action.'}
    with (D / 'source-parity-001.json').open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': result['passed'], 'checks': checks,
                      'method_count': len(methods), 'shared_count': len(methods) + 1}, indent=2))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
