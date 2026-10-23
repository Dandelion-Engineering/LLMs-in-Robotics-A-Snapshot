"""Retain source-only parity and completed focused checks; no qualification action."""
from pathlib import Path
import ast
import datetime
import difflib
import hashlib
import json
import re

HERE=Path(__file__).resolve().parent
C=HERE.parents[1]

def bind(path):
    raw=path.read_bytes()
    return {'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}

def identity(path): return {'path':str(path),**bind(path)}
def save(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2);f.write('\n')
    return identity(path)
def tree(text): return ast.dump(ast.parse(text),include_attributes=False)
def text(path): return path.read_text(encoding='utf-8')

baseline=json.loads((HERE/'before-and-absence.json').read_text(encoding='utf-8'))
names=baseline['owned_existing_files']+baseline['new_files']
assert len(names)==11 and len(set(names))==11
bindings={n:bind(C/n) for n in names}
preserved={n:bind(C/n) for n in baseline['historical_files']}
assert all(preserved[n]==baseline['source_bindings'][n] for n in preserved)
parity={}
for relative in ('qualification/prepare_native.py','qualification/host_probe.py',
                 'qualification/boundary_suite_v3.py','harness/raw_event_preflight_v2.py'):
    original=text(HERE/'before'/relative)
    restored=text(C/relative).replace('prepare_model_v20.py','prepare_model_v19.py').replace(
        'extra.pilot_retirement_inputs()','extra.index_label_inputs()')
    if relative.endswith('prepare_native.py'):
        restored=restored.replace("'io-repair/PREPARED_INDEX_LABELS_V1.md',\n              'io-repair/PILOT_RETIREMENT_INVENTORY_V1.md')",
                                  "'io-repair/PREPARED_INDEX_LABELS_V1.md')")
    assert restored==original and tree(restored)==tree(original),relative
    parity[relative]={'declared_reversal_text_equal':True,'declared_reversal_ast_equal':True,
                     'scope':'Inventory supplier selector/API and, for native only, one additive method input.'}

coordinator=text(C/'qualification/run_final_qualification_v28.py')
restored=coordinator.replace("PILOT_RETIREMENT_INVENTORY_METHOD = CAMPAIGN / 'io-repair/PILOT_RETIREMENT_INVENTORY_V1.md'\n",'')
gate="\n    require(frozen['sources'].get(PILOT_RETIREMENT_INVENTORY_METHOD.relative_to(REPO).as_posix()) == {\n                'sha256': sha(PILOT_RETIREMENT_INVENTORY_METHOD), 'bytes': PILOT_RETIREMENT_INVENTORY_METHOD.stat().st_size},\n            'Repaired source anchor must bind the exact pilot-retirement-inventory declaration')"
assert gate in restored
restored=restored.replace(gate,'').replace(', PILOT_RETIREMENT_INVENTORY_METHOD)',')')
restored=restored.replace('source-bound pilot retirement receipt inventory.','source-bound prepared-result index labels.')
mapping={'run_final_qualification_v28':'run_final_qualification_v27','final_raw_preflight_v28':'final_raw_preflight_v27',
    'final-qualification-028':'final-qualification-027','prepare_model_v20':'prepare_model_v19',
    'dev-087':'dev-083','dev-088':'dev-084','dev-089':'dev-085','dev-090':'dev-086',
    'dev087':'dev083','dev088':'dev084','dev089':'dev085','dev090':'dev086',
    'raw-preflight-018':'raw-preflight-017','transport-probe-021':'transport-probe-020','host-probe-028':'host-probe-027',
    'native-027':'native-026','boundary-028':'boundary-027','smoke-026':'smoke-025',
    'pilot-stock-025':'pilot-stock-024','pilot-home-025':'pilot-home-024'}
pattern=re.compile('|'.join(map(re.escape,mapping)))
restored=pattern.sub(lambda m:mapping[m.group()],restored)
restored=re.sub(r'\b(87|88|89|90)\b',lambda m:str(int(m.group())-4),restored)
original=text(HERE/'before/qualification/run_final_qualification_v27.py')
assert restored==original and tree(restored)==tree(original),'Coordinator has undeclared behavior changes'
parity['qualification/run_final_qualification_v28.py']={'declared_reversal_text_equal':True,
    'declared_reversal_ast_equal':True,'scope':'Fresh identities, V20 preparer routing, new frozen-method gate/core/preflight binding only; all control/queue/storage/assessment/seeds/budgets preserved.'}

relative='admission/prepare_certificate.py'
restored=text(C/relative).replace('run_final_qualification_v28.py','run_final_qualification_v27.py').replace('final-qualification-028','final-qualification-027')
lines=["        'pilot_retirement_inventory_method': CAMPAIGN / 'io-repair/PILOT_RETIREMENT_INVENTORY_V1.md',\n",
       "        'pilot_stock024_lifecycle_diagnosis': CAMPAIGN / 'io-repair/pilot-stock024-lifecycle-diagnosis-001/diagnosis.json',\n",
       "        'pilot_stock024_lifecycle_diagnosis_report': CAMPAIGN / 'io-repair/pilot-stock024-lifecycle-diagnosis-001/diagnosis.md',\n"]
for line in lines:
    assert restored.count(line)==1;restored=restored.replace(line,'')
original=text(HERE/'before'/relative)
assert restored==original and tree(restored)==tree(original),'Certificate changes exceed routing/provenance'
parity[relative]={'declared_reversal_text_equal':True,'declared_reversal_ast_equal':True,
                 'scope':'Current V28 coordinator/readiness/preflight/completion routing and three additive method/diagnosis bindings only.'}

module=ast.parse(text(C/'qualification/prepare_model_v20.py'))
inputs=next(ast.literal_eval(n.value) for n in module.body if isinstance(n,ast.Assign)
            and any(isinstance(t,ast.Name) and t.id=='PILOT_RETIREMENT_INPUTS' for t in n.targets))
packet='io-repair/pilot-stock024-lifecycle-diagnosis-001/'
declared={n for n in inputs if n.startswith(packet)}
actual={p.relative_to(C).as_posix() for p in (C/packet).iterdir() if p.is_file()}
assert actual==declared and len(actual)==11
provenance={n:bind(C/n) for n in inputs if n.startswith('io-repair/')}
methods={n.targets[0].id:ast.literal_eval(n.value.right) for n in ast.parse(coordinator).body
         if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)
         and n.targets[0].id.endswith('_METHOD')}
native=ast.parse(text(C/'qualification/prepare_native.py'))
native_methods=set(next(ast.literal_eval(n.value) for n in native.body if isinstance(n,ast.Assign)
                  and any(isinstance(t,ast.Name) and t.id=='METHOD_FILES' for t in n.targets)))
assert set(methods.values())|{'io-repair/CODEHOST_CHANNEL_TRANSPORT_V3.md'}==native_methods
stages=next(ast.literal_eval(n.value) for n in ast.parse(coordinator).body if isinstance(n,ast.Assign)
            and any(isinstance(t,ast.Name) and t.id=='STAGE_IDENTITIES' for t in n.targets))
assert [v[2] for v in stages]==[24000,None,24101,24102,24103]
diff=[]
for relative in names:
    source=relative
    if relative.endswith(('prepare_model_v20.py','test_prepare_model_v20.py')):source=relative.replace('v20','v19')
    if relative.endswith(('run_final_qualification_v28.py','test_run_final_qualification_v28.py')):source=relative.replace('v28','v27')
    diff.extend(difflib.unified_diff(text(HERE/'before'/source).splitlines(True),text(C/relative).splitlines(True),
                                   fromfile=source,tofile=relative))
with (HERE/'source-parity-001.diff').open('x',encoding='utf-8') as f:f.write(''.join(diff))
parity_receipt=save(HERE/'source-parity-001.json',{'schema':'campaign002-pilot-retirement-lineage-source-parity-1',
    'passed':True,'source_bindings':bindings,'preserved_historical_sources':preserved,'production_parity':parity,
    'complete_diagnosis_packet_count':len(declared),'coordinator_method_count':len(methods),
    'shared_method_count':len(native_methods),'fixed_stage_identities':stages,
    'model_policy_parity':'All three bounded V20 manifest constructions equal V19 after removing only additive runtime_input_files; check-001.',
    'diff':identity(HERE/'source-parity-001.diff'),'before':identity(HERE/'before-and-absence.json')})
checks=[json.loads((HERE/name).read_text(encoding='utf-8')) for name in ('check-001.json','check-002.json')]
assert all(x['passed'] and x['source_bindings_before']==bindings==x['source_bindings_after'] for x in checks)
repair=C/'io-repair/pilot-retirement-inventory-development-001/receipt.json'
repair_sources={n:bind(C/n) for n in ('assessment/assess.py','assessment/test_assess.py')}
assert repair_sources['assessment/assess.py']['sha256']=='9e44069df05bd20cc418ade9858a651854da0a2c0666904181c1dceb5750e1bf'
assert repair_sources['assessment/test_assess.py']['sha256']=='657bfd7e065cffd9244224b90e47d3b7b05a704610b9a3b6a92f2b03938c8b44'
folder=HERE/'final-checks';folder.mkdir()
final=save(folder/'receipt.json',{'schema':'campaign002-pilot-retirement-lineage-final-checks-1','passed':True,
    'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'tests_run':sum(x['tests_run'] for x in checks),'source_bindings':bindings,'provenance_bindings':provenance,
    'repair_lane_source_bindings':repair_sources,'repair_lane_final_receipt':identity(repair),
    'passing_checks':[identity(HERE/name) for name in ('check-001.json','check-002.json')],
    'preserved_failed_checks':[],'before':identity(HERE/'before-and-absence.json'),'parity':parity_receipt,
    'source_diff':identity(HERE/'source-parity-001.diff'),'coordinator_method_count':len(methods),
    'shared_method_count':len(native_methods),'fixed_seeds':{'native_seed_base':24000,'smoke':24101,'stock':24102,'home':24103},
    'scope':'Prospective lineage/inventory/certificate deterministic validation only. No queue/model/native launch, freeze, registry/map write, empirical reassessment or canonical history publication. Temporary manifests only in bounded tests.'})
print(json.dumps(final,indent=2))
