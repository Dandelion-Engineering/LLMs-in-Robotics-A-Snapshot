"""Bounded prospective V28/V20 source construction; no runtime execution."""
from pathlib import Path
import re

C = Path(__file__).resolve().parents[2]
Q = C / 'qualification'
PACKET = C / 'io-repair/pilot-stock024-lifecycle-diagnosis-001'
PACKET_FILES = ('authentication.json', 'collect-exit.json', 'collect.py', 'collect.stderr',
                'collect.stdout', 'diagnosis.json', 'diagnosis.md', 'execution.json',
                'official-status.json', 'official.stderr', 'official.stdout')
assert {p.name for p in PACKET.iterdir() if p.is_file()} == set(PACKET_FILES)

def put(path, value, new=False):
    if new:
        with path.open('x', encoding='utf-8', newline='\n') as f: f.write(value)
    else:
        path.write_text(value, encoding='utf-8', newline='\n')

def exact(text, old, new, count=None):
    assert old in text, old
    if count is not None: assert text.count(old) == count, (old,text.count(old),count)
    return text.replace(old,new)

mapping = {'run_final_qualification_v27':'run_final_qualification_v28', 'final_coordinator_v27':'final_coordinator_v28',
    'final_raw_preflight_v27':'final_raw_preflight_v28', 'final-qualification-027':'final-qualification-028',
    'prepare_model_v19':'prepare_model_v20', 'dev-083':'dev-087','dev-084':'dev-088','dev-085':'dev-089','dev-086':'dev-090',
    'dev083':'dev087','dev084':'dev088','dev085':'dev089','dev086':'dev090',
    'raw-preflight-017':'raw-preflight-018','transport-probe-020':'transport-probe-021','host-probe-027':'host-probe-028',
    'native-026':'native-027','boundary-027':'boundary-028','smoke-025':'smoke-026',
    'pilot-stock-024':'pilot-stock-025','pilot-home-024':'pilot-home-025',
    'declared_v27':'declared_v28'}
pattern = re.compile('|'.join(map(re.escape,mapping)))
def allocate(text):
    text = pattern.sub(lambda m:mapping[m.group()],text)
    return re.sub(r'\b(83|84|85|86)\b',lambda m:str(int(m.group())+4),text)

# Additive model wrapper delegates all policy construction to unchanged V19.
model = (Q/'prepare_model_v19.py').read_text(encoding='utf-8')
model = exact(model,'"""Preserve model policy; bind literal prepared-result index labels."""',
              '"""Preserve model policy; bind the exact pilot retirement inventory repair."""',1)
model = exact(model,"'model_inventory_v18'", "'model_inventory_v19'",1)
model = exact(model,"HERE / 'prepare_model_v18.py'", "HERE / 'prepare_model_v19.py'",1)
start=model.index('INDEX_LABEL_INPUTS = (');end=model.index('\n)\n',start)+3
inputs=['qualification/prepare_model_v20.py','qualification/test_prepare_model_v20.py',
        'io-repair/PILOT_RETIREMENT_INVENTORY_V1.md',
        *['io-repair/pilot-stock024-lifecycle-diagnosis-001/'+name for name in PACKET_FILES],
        'assessment/assess.py','assessment/test_assess.py']
model=model[:start]+'PILOT_RETIREMENT_INPUTS = (\n'+''.join('    '+repr(name)+',\n' for name in inputs)+')\n'+model[end:]
model=model.replace('index_label_inputs','pilot_retirement_inputs').replace('INDEX_LABEL_INPUTS','PILOT_RETIREMENT_INPUTS')
model=model.replace('prior.revocation_readback_inputs()','prior.index_label_inputs()')
model=model.replace('prepared-index-label input','pilot-retirement input')
put(Q/'prepare_model_v20.py',model,True)

test=(Q/'test_prepare_model_v19.py').read_text(encoding='utf-8').replace('V19','V20').replace('v19','v20').replace('v18_except','v19_except')
test=test.replace('index_label_inputs','pilot_retirement_inputs').replace('INDEX_LABEL_INPUTS','PILOT_RETIREMENT_INPUTS')
test=test.replace('V20.prior.prior.PREPARED_STARTUP_INPUTS','V20.prior.prior.prior.PREPARED_STARTUP_INPUTS')
test=test.replace('V20.prior.revocation_readback_inputs()','V20.prior.index_label_inputs()')
test=test.replace("('PREPARED_INDEX_LABELS_V1.md',", "('PILOT_RETIREMENT_INVENTORY_V1.md', 'PREPARED_INDEX_LABELS_V1.md',")
test=test.replace("'io-repair/smoke-024-read-diagnosis-001/analysis.json'", "'io-repair/pilot-stock024-lifecycle-diagnosis-001/diagnosis.json'")
test=test.replace('prepared-index-label input','pilot-retirement input')
test=test.replace("'io-repair/smoke-024-read-diagnosis-001'", "'io-repair/pilot-stock024-lifecycle-diagnosis-001'")
test=test.replace("'/smoke-024-read-diagnosis-001/'", "'/pilot-stock024-lifecycle-diagnosis-001/'")
test=test.replace("packet / 'analysis.json'", "packet / 'diagnosis.json'").replace("packet / 'analysis.md'", "packet / 'diagnosis.md'")
test=test.replace("'analysis.md', 'canary_readback_proof.py'", "'diagnosis.md', 'collect.py', 'canary_readback_proof.py'")
put(Q/'test_prepare_model_v20.py',test,True)

coordinator=allocate((Q/'run_final_qualification_v27.py').read_text(encoding='utf-8'))
coordinator=coordinator.replace('source-bound prepared-result index labels.','source-bound pilot retirement receipt inventory.')
line="PREPARED_INDEX_LABELS_METHOD = CAMPAIGN / 'io-repair/PREPARED_INDEX_LABELS_V1.md'"
coordinator=exact(coordinator,line,line+"\nPILOT_RETIREMENT_INVENTORY_METHOD = CAMPAIGN / 'io-repair/PILOT_RETIREMENT_INVENTORY_V1.md'",1)
needle="            'Repaired source anchor must bind the exact prepared-index-labels declaration')"
gate="\n    require(frozen['sources'].get(PILOT_RETIREMENT_INVENTORY_METHOD.relative_to(REPO).as_posix()) == {\n                'sha256': sha(PILOT_RETIREMENT_INVENTORY_METHOD), 'bytes': PILOT_RETIREMENT_INVENTORY_METHOD.stat().st_size},\n            'Repaired source anchor must bind the exact pilot-retirement-inventory declaration')"
coordinator=exact(coordinator,needle,needle+gate,1)
coordinator=coordinator.replace('CANARY_READBACK_EXCLUSIVITY_METHOD, PREPARED_INDEX_LABELS_METHOD)',
    'CANARY_READBACK_EXCLUSIVITY_METHOD, PREPARED_INDEX_LABELS_METHOD, PILOT_RETIREMENT_INVENTORY_METHOD)')
put(Q/'run_final_qualification_v28.py',coordinator,True)
test=allocate((Q/'test_run_final_qualification_v27.py').read_text(encoding='utf-8'))
test=test.replace('c.PREPARED_INDEX_LABELS_METHOD)', 'c.PREPARED_INDEX_LABELS_METHOD, c.PILOT_RETIREMENT_INVENTORY_METHOD)')
# The malformed-host negative must remain different from the newly allocated Host028.
test=test.replace("value['diagnostic']['run_id'] = 'RCI001-C02-host-probe-028'", "value['diagnostic']['run_id'] = 'RCI001-C02-host-probe-029'")
put(Q/'test_run_final_qualification_v28.py',test,True)

for relative in ('qualification/prepare_native.py','qualification/host_probe.py',
                 'qualification/boundary_suite_v3.py','harness/raw_event_preflight_v2.py'):
    path=C/relative;text=path.read_text(encoding='utf-8')
    text=exact(text,'prepare_model_v19.py','prepare_model_v20.py',1)
    text=exact(text,'extra.index_label_inputs()','extra.pilot_retirement_inputs()',1)
    if relative.endswith('prepare_native.py'):
        text=exact(text,"'io-repair/PREPARED_INDEX_LABELS_V1.md')", "'io-repair/PREPARED_INDEX_LABELS_V1.md',\n              'io-repair/PILOT_RETIREMENT_INVENTORY_V1.md')",1)
    put(path,text)
path=Q/'test_prepare_native.py';text=path.read_text(encoding='utf-8')
text=exact(text,'import prepare_model_v19 as model','import prepare_model_v20 as model',1)
text=text.replace('model.prior','model.prior.prior').replace('model.INDEX_LABEL_INPUTS','model.prior.INDEX_LABEL_INPUTS + model.PILOT_RETIREMENT_INPUTS')
text=text.replace("('prepare_model_v19.py',", "('prepare_model_v20.py', 'prepare_model_v19.py',")
text=text.replace('v27_method','v28_method').replace('run_final_qualification_v27.py','run_final_qualification_v28.py')
text=text.replace("self.assertIn(candidate.CAMPAIGN / 'io-repair/PREPARED_INDEX_LABELS_V1.md', methods)",
                  "self.assertIn(candidate.CAMPAIGN / 'io-repair/PREPARED_INDEX_LABELS_V1.md', methods)\n        self.assertIn(candidate.CAMPAIGN / 'io-repair/PILOT_RETIREMENT_INVENTORY_V1.md', methods)")
text=text.replace('prepared-index-label', 'pilot-retirement|prepared-index-label')
put(path,text)

path=C/'admission/prepare_certificate.py';text=path.read_text(encoding='utf-8')
text=text.replace('run_final_qualification_v27.py','run_final_qualification_v28.py').replace('final-qualification-027','final-qualification-028')
line="        'prepared_index_labels_method': CAMPAIGN / 'io-repair/PREPARED_INDEX_LABELS_V1.md',"
addition="\n        'pilot_retirement_inventory_method': CAMPAIGN / 'io-repair/PILOT_RETIREMENT_INVENTORY_V1.md',\n        'pilot_stock024_lifecycle_diagnosis': CAMPAIGN / 'io-repair/pilot-stock024-lifecycle-diagnosis-001/diagnosis.json',\n        'pilot_stock024_lifecycle_diagnosis_report': CAMPAIGN / 'io-repair/pilot-stock024-lifecycle-diagnosis-001/diagnosis.md',"
text=exact(text,line,line+addition,1);put(path,text)
path=C/'admission/test_prepare_admission.py';text=path.read_text(encoding='utf-8')
text=allocate(text)
line="            ('prepared_index_labels_method','io-repair/PREPARED_INDEX_LABELS_V1.md'),"
addition="\n            ('pilot_retirement_inventory_method','io-repair/PILOT_RETIREMENT_INVENTORY_V1.md'),\n            ('pilot_stock024_lifecycle_diagnosis','io-repair/pilot-stock024-lifecycle-diagnosis-001/diagnosis.json'),\n            ('pilot_stock024_lifecycle_diagnosis_report','io-repair/pilot-stock024-lifecycle-diagnosis-001/diagnosis.md'),"
text=exact(text,line,line+addition,1)
text=exact(text,"for relative in ('io-repair/PREPARED_INDEX_LABELS_V1.md',", "for relative in ('io-repair/PILOT_RETIREMENT_INVENTORY_V1.md',\n                         'io-repair/pilot-stock024-lifecycle-diagnosis-001/diagnosis.json',\n                         'io-repair/pilot-stock024-lifecycle-diagnosis-001/diagnosis.md',\n                         'io-repair/PREPARED_INDEX_LABELS_V1.md',",1)
put(path,text)
print('Wrote four new lineage files and seven owned selectors/fixtures; no runtime execution.')
