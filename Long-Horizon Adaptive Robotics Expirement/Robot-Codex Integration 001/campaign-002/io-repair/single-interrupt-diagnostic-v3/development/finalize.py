"""Retain exact source parity and local test evidence; no runtime invocation."""
import ast
import copy
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

DEV = Path(__file__).resolve().parent
HERE = DEV.parent
OLD = HERE.parent / 'single-interrupt-diagnostic-v2'
CAMPAIGN = HERE.parents[1]
def bind(path, absolute=True):
    raw = path.read_bytes()
    result = {'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
    if absolute: result['path'] = str(path)
    return result
def read(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2);stream.write('\n')

before = read(DEV/'before.json')['sources']
for name,item in before.items():
    assert bind(OLD/name) == item
    assert (DEV/'before'/name).read_bytes() == (OLD/name).read_bytes()
for name in ('run.py','launch.py'):
    assert (HERE/name).read_bytes() == (OLD/name).read_bytes()

# Exact byte reversal: eight declared constant/message substitutions and the
# fixed required-input function with its explicit provenance tuple only.
old = (OLD/'common.py').read_bytes()
new = (HERE/'common.py').read_bytes()
original_start = old.index(b'def required_inputs():')
original_end = old.index(b'\n\ndef validate_manifest', original_start)
new_start = new.index(b'# Fixed provenance files, never discovered')
new_end = new.index(b'\n\ndef validate_manifest', new_start)
reversed_bytes = new[:new_start] + old[original_start:original_end] + new[new_end:]
for original,current in (
    (b'RCI001-C02-shutdown-diagnostic-002',b'RCI001-C02-shutdown-diagnostic-003'),
    (b'RCI001-C02-dev-062',b'RCI001-C02-dev-091'),
    (b'RCI001-Campaign002-single-interrupt-diagnostic-v2',b'RCI001-Campaign002-single-interrupt-diagnostic-v3'),
    (b'io-repair/shutdown-diagnostic-002',b'io-repair/shutdown-diagnostic-003'),
    (b'qualification/smoke-019-manifest.json',b'qualification/smoke-026-manifest.json'),
    (b'827e96a429b50ede8594cf57ca7d4f6c30542520ea47ad1fc13cbc3bc20f3f7d',b'0d6bfb4a1180f53dba8e784cdd4ef68d7d1fedef4ca7d74015b424a66380f142'),
    (b'io-repair/RESET_REJECTION_DIAGNOSTIC_V1.md',b'io-repair/SOCKET_ABORT_NATIVE_DIAGNOSTIC_V1.md'),
    (b'Original Smoke019 policy basis changed',b'Original Smoke026 policy basis changed'),
):
    assert reversed_bytes.count(current) == 1
    reversed_bytes = reversed_bytes.replace(current,original)
assert reversed_bytes == old

def methods(path):
    return {item.name:item for node in ast.parse(path.read_bytes()).body if isinstance(node,ast.ClassDef)
            for item in node.body if isinstance(item,ast.FunctionDef)}
old_methods = methods(OLD/'test_diagnostic.py')
new_methods = methods(HERE/'test_diagnostic.py')
for name,node in old_methods.items():
    original = copy.deepcopy(node)
    for item in ast.walk(original):
        if isinstance(item,ast.Constant) and item.value == 'RCI001-C02-smoke-019':
            item.value = 'RCI001-C02-smoke-026'
    assert ast.dump(original) == ast.dump(new_methods[name]), name
assert set(new_methods)-set(old_methods) == {'test_changed_or_ambiguous_provenance_binding_rejected_before_assessor'}

spec = importlib.util.spec_from_file_location('wrapper_parity_common',HERE/'common.py')
common = importlib.util.module_from_spec(spec);spec.loader.exec_module(common)
source_bindings = {path.relative_to(CAMPAIGN).as_posix():bind(path,False) for path in sorted(HERE.glob('*.py'))}
provenance = {name:bind(common.REPO/name,False) for name in common.required_inputs()}
assert not common.ROOT.exists(), 'Real diagnostic preparation must remain absent'
assert not common.RAW.exists() and not common.WORKSPACE.exists()
assert not common.SNAPSHOT.exists(), 'Actual dev091 freeze must remain absent'

command = read(DEV/'final-checks-002/receipt.json')
assert type(command['exit_code']) is int and command['exit_code'] == 0 and command['sources_unchanged'] is True
assert command['argv'] == [sys.executable,'-X','utf8','-B','-m','unittest','discover','-s',str(HERE),'-p','test_*.py','-v']
for key in ('stdout','stderr'):
    assert bind(Path(command[key]['path'])) == command[key]
assert 'Ran 33 tests' in Path(command['stderr']['path']).read_text(encoding='utf-8')
assert read(DEV/'red-001/receipt.json')['exit_code'] == 1

diff = ''.join(difflib.unified_diff(old.decode().splitlines(True),new.decode().splitlines(True),
                                  fromfile='v2/common.py',tofile='v3/common.py'))
with (DEV/'source.diff').open('x',encoding='utf-8',newline='\n') as stream:stream.write(diff)
parity = {'schema':'campaign002-single-interrupt-v3-source-parity-1','passed':True,
    'source_bindings':source_bindings,'original_bindings':before,
    'v2_originals_unchanged':True,'run_and_launch_byte_identical':True,
    'common_exact_reversal_equals_v2':True,
    'common_changes':['declared identities and immutable Smoke026 basis','diagnostic method','fixed required source/provenance inventory','basis error label'],
    'all_other_common_functions_unchanged':True,'load_physical_lazy_import_environment_unchanged':True,
    'existing_diagnostic_test_methods_preserved_except_basis_label':len(old_methods),
    'added_diagnostic_test_methods':sorted(set(new_methods)-set(old_methods)),
    'test_controls_scope':'Replaces stale v2 preparer/control tests with fixed v3 wrapper contract; additive top-level control tests are separately owned.',
    'input_bindings':provenance,'source_diff':bind(DEV/'source.diff')}
save(DEV/'source-parity.json',parity)
receipt = {'schema':'campaign002-single-interrupt-v3-development-1','passed':True,
    'scope':'Local mocked validation and read-only lazy imports only; no native/model/socket/queue/prepare/freeze action.',
    'run_id':common.RUN,'framework_revision':common.REVISION,
    'source_bindings':source_bindings,'commands':[command],'tests_run':33,
    'source_parity':bind(DEV/'source-parity.json'),'method':bind(common.METHOD),'basis':bind(common.REFERENCE),
    'red':bind(DEV/'red-001/receipt.json'),'red_result':'8 contract tests on copied v2 common rejected old identity/inventory; 22 subtest failures and one missing-new-tuple error retained.',
    'previous_green':bind(DEV/'green-001/receipt.json'),
    'previous_discovery':bind(DEV/'final-checks/receipt.json'),
    'discovery_command_note':'Previous discovery passed with forward-slash path spelling; final-checks-002 uses exact native absolute argv required by control gate. Sources unchanged.',
    'preparation_outputs_absent':True,'qualification_claim':False,'historical_verdict_changed':False}
save(DEV/'receipt.json',receipt)
print(json.dumps({'receipt':bind(DEV/'receipt.json'),'parity':bind(DEV/'source-parity.json'),
                  'source_bindings':source_bindings,'inputs':len(provenance),'tests':33}))
