"""Finite parser addition and additive fresh source lineage; no launches."""
import difflib
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent;IO=HERE.parent;C=IO.parent;Q=C/'qualification'
PAIRS={'v32':'v33','V32':'V33','final-qualification-032':'final-qualification-033',
    'host-probe-033':'host-probe-034','host-probe-032':'host-probe-033',
    'native-031':'native-032','boundary-032':'boundary-033','smoke-030':'smoke-031',
    'pilot-stock-029':'pilot-stock-030','pilot-home-029':'pilot-home-030',
    'raw-preflight-022':'raw-preflight-023','transport-probe-025':'transport-probe-026',
    'dev-107':'dev-111','dev-108':'dev-112','dev-109':'dev-113','dev-110':'dev-114',
    'dev107':'dev111','dev108':'dev112','dev109':'dev113','dev110':'dev114',
    '108, 109, 110, 110, 110':'112, 113, 114, 114, 114',
    'anchor_number == 107':'anchor_number == 111','[0][2]) == 108':'[0][2]) == 112'}

def changed(text):
    return re.sub('|'.join(re.escape(k) for k in sorted(PAIRS,key=len,reverse=True)),lambda m:PAIRS[m.group()],text)

def identity(p):
    raw=p.read_bytes();return {'path':str(p.resolve()),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}

def write(p,text):
    with p.open('x',encoding='utf-8',newline='\n') as f:f.write(text)

def main():
    assert not (HERE/'derivation.json').exists()
    edits=[]
    def derive(source,target,after):
        before=source.read_text(encoding='utf-8')
        if target==source:
            backup=HERE/(target.parent.name+'-'+target.name+'.before')
            with backup.open('xb') as f:f.write(source.read_bytes())
            old=identity(backup);target.write_text(after,encoding='utf-8',newline='\n')
        else:old=identity(source);write(target,after)
        edits.append({'before':old,'after':identity(target)})
        write(HERE/(target.parent.name+'-'+target.name+'.diff'),''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile=str(source),tofile=str(target))))
    p=C/'assessment/initial_read_composition.py';t=p.read_text(encoding='utf-8')
    t=t.replace('Two finite, authenticated','Finite, authenticated')
    anchor='FILTERED_ROOT_PREFIXES = ROOT_PREFIXES + (b\'/workspace/live\',)\n'
    assert t.count(anchor)==1
    t=t.replace(anchor,anchor+"PRINT_FIND_SCRIPT = 'find /workspace/notes /workspace/programs -maxdepth 3 -type f -print'\n")
    anchor='\n\ndef find_prefix_roots(argv):'
    assert t.count(anchor)==1
    t=t.replace(anchor,"\n_PRINT_RECIPE = re.compile(r'[ \\t]*cat[ \\t]+' + _CAT_PATH + r'[ \\t]*&&[ \\t]*'\n                           + re.escape(PRINT_FIND_SCRIPT) + r'[ \\t]*')\n"+anchor)
    t=t.replace('one of the two complete finite recipes','one of the three complete finite recipes')
    t=t.replace('if _PREFIX_RECIPE.fullmatch(argv[2]):','if _PREFIX_RECIPE.fullmatch(argv[2]) or _PRINT_RECIPE.fullmatch(argv[2]):')
    derive(p,p,t)
    p=Q/'prepare_model_v23.py';t=p.read_text(encoding='utf-8')
    t=t.replace('model_inventory_v22','model_inventory_v23').replace("HERE/'prepare_model_v22.py'","HERE/'prepare_model_v23.py'")
    t=t.replace("'qualification/prepare_model_v23.py','qualification/test_prepare_model_v23.py'","'qualification/prepare_model_v24.py','qualification/test_prepare_model_v24.py'")
    t=t.replace('COMPLETE_PROCESS_AND_LITERAL_READS_V1.md','COMPLETE_PROCESS_AND_LITERAL_READS_V2.md')
    t=t.replace("'assessment/test_smoke028_reader_forms.py'","'assessment/test_smoke030_print_recipe.py'")
    t=t.replace('prior.process_drain_inputs()','prior.reader_inputs()')
    derive(p,Q/'prepare_model_v24.py',t)
    p=Q/'test_prepare_model_v23.py';derive(p,Q/'test_prepare_model_v24.py',p.read_text(encoding='utf-8').replace('import prepare_model_v23 as subject','import prepare_model_v24 as subject'))
    for p in (C/'harness/raw_event_preflight_v2.py',Q/'prepare_native.py',Q/'host_probe.py',Q/'boundary_suite_v3.py'):
        t=p.read_text(encoding='utf-8');assert t.count('prepare_model_v23.py')==1
        derive(p,p,t.replace('prepare_model_v23.py','prepare_model_v24.py'))
    for name in ('run_final_qualification_v32.py','test_run_final_qualification_v32.py'):
        p=Q/name;t=changed(p.read_text(encoding='utf-8')).replace('prepare_model_v23.py','prepare_model_v24.py').replace('COMPLETE_PROCESS_AND_LITERAL_READS_V1.md','COMPLETE_PROCESS_AND_LITERAL_READS_V2.md')
        derive(p,Q/name.replace('v32','v33'),t)
    old=IO/'boundary-import-qualification-001'
    p=old/'control.py';t=changed(p.read_text(encoding='utf-8')).replace('boundary-import-qualification-001','print-recipe-qualification-001')
    t=t.replace("'raw-preflight-021', 'transport': 'transport-probe-024'","'raw-preflight-022', 'transport': 'transport-probe-025'")
    t=t.replace("'--number', '032'","'--number', '033'")
    t=t.replace("'complete_reader_diagnostic'):","'complete_reader_diagnostic', 'print_recipe_method', 'print_recipe_diagnosis', 'print_recipe_replay'):")
    derive(p,HERE/'control.py',t)
    p=old/'settle_host.py';derive(p,HERE/'settle_host.py',p.read_text(encoding='utf-8'))
    p=old/'checks.py';t=p.read_text(encoding='utf-8').replace('COMPLETE_PROCESS_AND_LITERAL_READS_V1.md','COMPLETE_PROCESS_AND_LITERAL_READS_V2.md');derive(p,HERE/'checks.py',t)
    for p in (C/'admission/prepare_certificate.py',C/'admission/test_prepare_admission.py'):
        t=changed(p.read_text(encoding='utf-8'))
        if p.name=='prepare_certificate.py':
            anchor="        'complete_process_readers_diagnostic': CAMPAIGN / 'io-repair/complete-process-readers-001/diagnostic-replay-001.json',\n"
            assert t.count(anchor)==1
            t=t.replace(anchor,anchor+"        'print_recipe_method': CAMPAIGN / 'io-repair/COMPLETE_PROCESS_AND_LITERAL_READS_V2.md',\n        'print_recipe_diagnostic': CAMPAIGN / 'io-repair/smoke030-read-diagnosis-001/observations.json',\n        'print_recipe_replay': CAMPAIGN / 'io-repair/print-recipe-qualification-001/diagnostic-replay-001.json',\n")
        derive(p,p,t)
    write(HERE/'derivation.json',json.dumps({'changes':edits,'scope':'One finite recipe; unchanged byte proof and runtime policies; additive V24 source inventory and fresh V33 identities.'},indent=2)+'\n')
    print(json.dumps({'files':len(edits)}))

if __name__=='__main__':main()
