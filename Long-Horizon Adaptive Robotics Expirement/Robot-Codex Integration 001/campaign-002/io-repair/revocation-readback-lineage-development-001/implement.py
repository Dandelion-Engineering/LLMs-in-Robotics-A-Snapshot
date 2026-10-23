"""Mechanical additive V26 orchestration and V18 inventory; never prepare/launch."""
from pathlib import Path
import re

C = Path(__file__).resolve().parents[2]
Q = C/'qualification'
BASE = Path(__file__).resolve().parent/'before'

def fresh(path, text):
    with path.open('x', encoding='utf-8', newline='\n') as f: f.write(text)

def replace_once(text, old, new):
    assert text.count(old) == 1, (old, text.count(old))
    return text.replace(old, new)

replacements = {'v25':'v26', 'V25':'V26', 'prepare_model_v17.py':'prepare_model_v18.py',
    'inventory_v17':'inventory_v18', 'final-qualification-025':'final-qualification-026',
    'native-024':'native-025', 'boundary-025':'boundary-026', 'smoke-023':'smoke-024',
    'pilot-stock-022':'pilot-stock-023', 'pilot-home-022':'pilot-home-023',
    'host-probe-025':'host-probe-026','raw-preflight-015':'raw-preflight-016','transport-probe-018':'transport-probe-019',
    'dev-075':'dev-079','dev-076':'dev-080','dev-077':'dev-081','dev-078':'dev-082',
    'dev075':'dev079','dev076':'dev080','dev077':'dev081','dev078':'dev082',
    '[76, 77, 78, 78, 78]':'[80, 81, 82, 82, 82]',
    '(76, 77, 78, 78, 78)':'(80, 81, 82, 82, 82)',
    'anchor_number == 75':'anchor_number == 79',
    "revision_number(readiness['stages'][0][2]) == 76":"revision_number(readiness['stages'][0][2]) == 80"}
pattern = re.compile('|'.join(re.escape(k) for k in sorted(replacements,key=len,reverse=True)))
def route(text): return pattern.sub(lambda m:replacements[m.group()],text)

text = route((Q/'run_final_qualification_v25.py').read_text())
text = text.replace('after prepared startup-file result-segment evidence repair.',
                    'after epoch-revocation, index-shorthand and canary-readback repairs.')
line = "PREPARED_STARTUP_SEGMENTS_METHOD = CAMPAIGN / 'io-repair/PREPARED_STARTUP_SEGMENTS_V1.md'"
text = replace_once(text,line,line+"\nEPOCH_REVOCATION_INDEX_METHOD = CAMPAIGN / 'io-repair/EPOCH_REVOCATION_AND_INDEX_SHORTHAND_V1.md'\nCANARY_READBACK_EXCLUSIVITY_METHOD = CAMPAIGN / 'io-repair/CANARY_READBACK_EXCLUSIVITY_V1.md'")
text = text.replace(', PREPARED_STARTUP_SEGMENTS_METHOD)', ', PREPARED_STARTUP_SEGMENTS_METHOD, EPOCH_REVOCATION_INDEX_METHOD, CANARY_READBACK_EXCLUSIVITY_METHOD)')
point = '    core = admission.runtime_identities(frozen)'
gates = ''.join("    require(frozen['sources'].get("+name+".relative_to(REPO).as_posix()) == {\n"
               "                'sha256': sha("+name+"), 'bytes': "+name+".stat().st_size},\n"
               "            'Repaired source anchor must bind the exact "+label+" declaration')\n"
               for name,label in [('EPOCH_REVOCATION_INDEX_METHOD','epoch-revocation/index-shorthand'),
                                  ('CANARY_READBACK_EXCLUSIVITY_METHOD','canary-readback-exclusivity')])
text = replace_once(text,point,gates+point)
fresh(Q/'run_final_qualification_v26.py',text)
test = route((Q/'test_run_final_qualification_v25.py').read_text())
test = test.replace(', c.PREPARED_STARTUP_SEGMENTS_METHOD)', ', c.PREPARED_STARTUP_SEGMENTS_METHOD, c.EPOCH_REVOCATION_INDEX_METHOD, c.CANARY_READBACK_EXCLUSIVITY_METHOD)')
addition = '''
    def test_preserved_v25_allocation_cannot_be_reused(self):
        value = self.declaration()
        value['stages'] = [['native-024', 'native', 'RCI001-C02-dev-076', 24000],
                           ['boundary-025', 'boundary', 'RCI001-C02-dev-077', None],
                           ['smoke-023', 'smoke', 'RCI001-C02-dev-078', 24101],
                           ['pilot-stock-022', 'stock', 'RCI001-C02-dev-078', 24102],
                           ['pilot-home-022', 'home', 'RCI001-C02-dev-078', 24103]]
        with self.assertRaisesRegex(ValueError, 'Qualifier identities'):
            self.load(value)

    def test_both_new_methods_are_required_and_remain_exact_in_later_stages(self):
        methods = [value for name, value in vars(c).items() if name.endswith('_METHOD')]
        originals = {p.relative_to(c.REPO).as_posix(): {'sha256': c.sha(p), 'bytes': p.stat().st_size}
                     for p in methods}
        for method in (c.EPOCH_REVOCATION_INDEX_METHOD, c.CANARY_READBACK_EXCLUSIVITY_METHOD):
            name = method.relative_to(c.REPO).as_posix()
            for bad in (None, {'sha256': '0'*64, 'bytes': 1}):
                with self.subTest(method=method.name, bad=bad):
                    sources = dict(originals)
                    if bad is None: sources.pop(name)
                    else: sources[name] = bad
                    value = self.declaration()
                    path = self.save('releases/RCI001-C02-dev-079/snapshot.json',
                                     {'revision': 'RCI001-C02-dev-079', 'sources': sources})
                    value['source_snapshot'] = c.identity(path)
                    with patch.object(c, 'MAP', self.root), \\
                         patch.object(c.admission.base, 'frozen_problems', return_value=[]), \\
                         patch.object(c.admission, 'runtime_identities') as runtime:
                        with self.assertRaisesRegex(ValueError, 'declaration'):
                            c.assert_sources(value)
                        runtime.assert_not_called()
            value = self.declaration()
            path = self.save('releases/RCI001-C02-dev-079/snapshot.json',
                             {'revision': 'RCI001-C02-dev-079', 'sources': originals})
            value['source_snapshot'] = c.identity(path)
            changed = dict(originals); changed[name] = {'sha256': '0'*64, 'bytes': 1}
            later = self.save('releases/RCI001-C02-dev-080/snapshot.json',
                              {'revision': 'RCI001-C02-dev-080', 'sources': changed})
            with patch.object(c, 'MAP', self.root), \\
                 patch.object(c.admission.base, 'frozen_problems', return_value=[]), \\
                 patch.object(c.admission, 'runtime_identities', return_value={}), \\
                 patch.object(Path, 'rglob', return_value=[]):
                with self.assertRaisesRegex(ValueError, 'changed|differs'):
                    c.assert_sources(value, later)

'''
test = replace_once(test,"\nif __name__ == '__main__':",'\n'+addition+"if __name__ == '__main__':")
fresh(Q/'test_run_final_qualification_v26.py',test)

model = (Q/'prepare_model_v17.py').read_text()
model = model.replace('Preserve model policy; bind prepared startup-file result segments.',
                      'Preserve model policy; bind epoch revocation and canary readback evidence.')
model = model.replace('model_inventory_v16','model_inventory_v17').replace("HERE / 'prepare_model_v16.py'","HERE / 'prepare_model_v17.py'")
start = model.index('PREPARED_STARTUP_INPUTS = ('); end = model.index('\n\n\ndef prepared_startup_inputs',start)
new_inputs = ('qualification/prepare_model_v18.py','qualification/test_prepare_model_v18.py',
              'io-repair/EPOCH_REVOCATION_AND_INDEX_SHORTHAND_V1.md','io-repair/CANARY_READBACK_EXCLUSIVITY_V1.md',
              'io-repair/smoke-023-read-proof-diagnosis.json','io-repair/smoke-023-read-proof-diagnosis.md',
              'io-repair/smoke-023-transport-diagnosis.json','io-repair/smoke-023-transport-diagnosis.md',
              'io-repair/smoke-023-canary-diagnosis.json',
              'assessment/canary_readback_proof.py','assessment/test_canary_readback_proof.py')
model = model[:start]+'REVOCATION_READBACK_INPUTS = (\n'+''.join('    '+repr(s)+',\n' for s in new_inputs)+')'+model[end:]
model = model.replace('PREPARED_STARTUP_INPUTS','REVOCATION_READBACK_INPUTS').replace('def prepared_startup_inputs','def revocation_readback_inputs').replace('set(prepared_startup_inputs())','set(revocation_readback_inputs())')
model = model.replace('prior.read_evidence_inputs()','prior.prepared_startup_inputs()').replace('Missing or linked prepared-startup input','Missing or linked revocation/readback input')
fresh(Q/'prepare_model_v18.py',model)

test = (Q/'test_prepare_model_v17.py').read_text().replace('V17','V18').replace('model_v17','model_v18').replace('equal_v16','equal_v17')
test = test.replace('prepared_startup_inputs','revocation_readback_inputs').replace('PREPARED_STARTUP_INPUTS','REVOCATION_READBACK_INPUTS')
test = test.replace("for name in ('PREPARED_STARTUP_SEGMENTS_V1.md', 'smoke-022-read-proof-diagnosis.json', 'smoke-022-read-proof-diagnosis.md'):",
                    "for name in ('EPOCH_REVOCATION_AND_INDEX_SHORTHAND_V1.md', 'CANARY_READBACK_EXCLUSIVITY_V1.md', 'smoke-023-read-proof-diagnosis.json', 'smoke-023-canary-diagnosis.json', 'smoke-023-transport-diagnosis.json'):")
test = test.replace("for name in ('prepared_result_segments.py',", "for name in ('canary_readback_proof.py', 'test_canary_readback_proof.py', 'EPOCH_REVOCATION_AND_INDEX_SHORTHAND_V1.md', 'CANARY_READBACK_EXCLUSIVITY_V1.md', 'prepared_result_segments.py',")
test = test.replace("target = V18.CAMPAIGN / 'assessment/prepared_result_segments.py'","target = V18.CAMPAIGN / 'assessment/canary_readback_proof.py'")
test = test.replace('Missing or linked prepared-startup input','Missing or linked revocation/readback input')
test = test.replace('for name in V18.REVOCATION_READBACK_INPUTS\n                    if', 'for name in V18.prior.PREPARED_STARTUP_INPUTS\n                    if')
test = test.replace('V18.prior.read_evidence_inputs()', 'V18.prior.prepared_startup_inputs()')
fresh(Q/'test_prepare_model_v18.py',test)

for rel in ('qualification/prepare_native.py','qualification/host_probe.py','qualification/boundary_suite_v3.py','harness/raw_event_preflight_v2.py'):
    path=C/rel; text=path.read_text().replace('prepare_model_v17.py','prepare_model_v18.py').replace('extra.prepared_startup_inputs()','extra.revocation_readback_inputs()')
    if rel=='qualification/prepare_native.py':
        text=replace_once(text,"'io-repair/PREPARED_STARTUP_SEGMENTS_V1.md')", "'io-repair/PREPARED_STARTUP_SEGMENTS_V1.md',\n              'io-repair/EPOCH_REVOCATION_AND_INDEX_SHORTHAND_V1.md',\n              'io-repair/CANARY_READBACK_EXCLUSIVITY_V1.md')")
    path.write_text(text,encoding='utf-8',newline='\n')
path=Q/'test_prepare_native.py';text=path.read_text().replace('import prepare_model_v17 as model','import prepare_model_v18 as model')
text=text.replace('model.prior.prior.CLEANUP_INPUTS + model.prior.READ_EVIDENCE_INPUTS + model.PREPARED_STARTUP_INPUTS',
                  'model.prior.prior.prior.CLEANUP_INPUTS + model.prior.prior.READ_EVIDENCE_INPUTS + model.prior.PREPARED_STARTUP_INPUTS + model.REVOCATION_READBACK_INPUTS')
text=text.replace("for name in ('prepare_model_v17.py',", "for name in ('prepare_model_v18.py', 'prepare_model_v17.py',")
text=text.replace('v25','v26').replace('(initial-read evidence|prepared-startup)', '(initial-read evidence|prepared-startup|revocation/readback)')
path.write_text(text,encoding='utf-8',newline='\n')

additional = {'epoch_revocation_index_shorthand_method':'io-repair/EPOCH_REVOCATION_AND_INDEX_SHORTHAND_V1.md',
              'canary_readback_exclusivity_method':'io-repair/CANARY_READBACK_EXCLUSIVITY_V1.md',
              'smoke023_read_proof_diagnosis':'io-repair/smoke-023-read-proof-diagnosis.json',
              'smoke023_read_proof_diagnosis_report':'io-repair/smoke-023-read-proof-diagnosis.md',
              'smoke023_transport_diagnosis':'io-repair/smoke-023-transport-diagnosis.json',
              'smoke023_transport_diagnosis_report':'io-repair/smoke-023-transport-diagnosis.md',
              'smoke023_canary_diagnosis':'io-repair/smoke-023-canary-diagnosis.json'}
path=C/'admission/prepare_certificate.py';text=route(path.read_text())
line="        'prepared_startup_segments_method': CAMPAIGN / 'io-repair/PREPARED_STARTUP_SEGMENTS_V1.md',"
text=replace_once(text,line,line+'\n'+''.join('        '+repr(key)+': CAMPAIGN / '+repr(value)+',\n' for key,value in additional.items()).rstrip())
path.write_text(text,encoding='utf-8',newline='\n')
path=C/'admission/test_prepare_admission.py';text=route(path.read_text())
line="            ('prepared_startup_segments_method','io-repair/PREPARED_STARTUP_SEGMENTS_V1.md'),"
text=replace_once(text,line,line+'\n'+''.join('            ('+repr(key)+','+repr(value)+'),\n' for key,value in additional.items()).rstrip())
line="        for relative in ('io-repair/PREPARED_STARTUP_SEGMENTS_V1.md',"
text=replace_once(text,line,line+'\n'+''.join('                         '+repr(value)+',\n' for value in additional.values()).rstrip())
path.write_text(text,encoding='utf-8',newline='\n')
print('Wrote four additive files and seven scoped supplier/certificate/test updates; no manifests prepared.')
