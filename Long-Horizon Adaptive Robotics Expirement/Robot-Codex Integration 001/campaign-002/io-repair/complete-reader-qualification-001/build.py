"""Derive V31 source inventory and one-shot coordinator; no runs or allocation."""
import difflib
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent;IO=HERE.parent;C=IO.parent;Q=C/'qualification'
PAIRS={'v30':'v31','V30':'V31','final-qualification-030':'final-qualification-031',
       'host-probe-031':'host-probe-032','host-probe-030':'host-probe-031',
       'native-029':'native-030','boundary-030':'boundary-031','smoke-028':'smoke-029',
       'pilot-stock-027':'pilot-stock-028','pilot-home-027':'pilot-home-028',
       'raw-preflight-020':'raw-preflight-021','transport-probe-023':'transport-probe-024',
       'dev-099':'dev-103','dev-100':'dev-104','dev-101':'dev-105','dev-102':'dev-106',
       'dev099':'dev103','dev100':'dev104','dev101':'dev105','dev102':'dev106',
       '100, 101, 102, 102, 102':'104, 105, 106, 106, 106',
       'anchor_number == 99':'anchor_number == 103',"[0][2]) == 100":"[0][2]) == 104",
       'prepare_model_v22.py':'prepare_model_v23.py'}

def changed(text):return re.sub('|'.join(re.escape(k) for k in sorted(PAIRS,key=len,reverse=True)),lambda m:PAIRS[m.group()],text)
def identity(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,text):
    with p.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
def replace_once(text,old,new):
    assert text.count(old)==1,(old,text.count(old));return text.replace(old,new)

def main():
    assert not (HERE/'derivation.json').exists()
    edits=[]
    def derive(source,target,after):
        before=source.read_text(encoding='utf-8')
        if target==source:
            backup=HERE/(target.parent.name+'-'+target.name+'.before')
            backup.write_bytes(source.read_bytes());old=identity(backup)
            target.write_text(after,encoding='utf-8',newline='\n')
        else:old=identity(source);write(target,after)
        edits.append({'before':old,'after':identity(target)})
        write(HERE/(target.parent.name+'-'+target.name+'.diff'),''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile=str(source),tofile=str(target))))
    p=Q/'prepare_model_v22.py';text=p.read_text(encoding='utf-8')
    text=text.replace('model_inventory_v21','model_inventory_v22').replace("HERE/'prepare_model_v21.py'","HERE/'prepare_model_v22.py'")
    begin=text.index('PROCESS_DRAIN_INPUTS=(');end=text.index('\n\n\ndef process_drain_inputs',begin)
    text=text[:begin]+"READER_INPUTS=(\n    'qualification/prepare_model_v23.py','qualification/test_prepare_model_v23.py',\n    'io-repair/COMPLETE_PROCESS_AND_LITERAL_READS_V1.md',\n    'assessment/retained_reads.py','assessment/completion_chronology.py',\n    'assessment/canary_readback_proof.py','assessment/initial_read_composition.py',\n    'assessment/test_smoke028_reader_forms.py',\n)"+text[end:]
    text=text.replace('PROCESS_DRAIN_INPUTS','READER_INPUTS').replace('def process_drain_inputs','def reader_inputs')
    text=text.replace('prior.pre_exit_inputs()','prior.process_drain_inputs()').replace('set(process_drain_inputs())','set(reader_inputs())')
    text=text.replace('graceful process-drain source','complete-process/read source')
    text=text.replace('add the graceful process-drain source closure','add the finite read-recognition source closure')
    derive(p,Q/'prepare_model_v23.py',text)
    p=Q/'test_prepare_model_v22.py';text=p.read_text(encoding='utf-8').replace('prepare_model_v22 as subject','prepare_model_v23 as subject').replace('PROCESS_DRAIN_INPUTS','READER_INPUTS').replace('process_drain_inputs()','reader_inputs()')
    derive(p,Q/'test_prepare_model_v23.py',text)
    for p in (Q/'prepare_native.py',Q/'host_probe.py',Q/'boundary_suite_v3.py',C/'harness/raw_event_preflight_v2.py'):
        text=p.read_text(encoding='utf-8').replace('prepare_model_v22.py','prepare_model_v23.py').replace('extra.process_drain_inputs()','extra.reader_inputs()')
        derive(p,p,text)
    p=Q/'test_prepare_native.py';text=p.read_text(encoding='utf-8')
    text=replace_once(text,'import prepare_model_v22 as process_drain','import prepare_model_v22 as process_drain\nimport prepare_model_v23 as complete_reads')
    text=replace_once(text,'QUIESCENCE_CAMPAIGN_INPUTS += process_drain.PROCESS_DRAIN_INPUTS','QUIESCENCE_CAMPAIGN_INPUTS += process_drain.PROCESS_DRAIN_INPUTS\nQUIESCENCE_CAMPAIGN_INPUTS += complete_reads.READER_INPUTS')
    text=replace_once(text,"for name in ('prepare_model_v22.py',","for name in ('prepare_model_v23.py', 'prepare_model_v22.py',")
    derive(p,p,text)
    for name in ('run_final_qualification_v30.py','test_run_final_qualification_v30.py'):
        p=Q/name;text=changed(p.read_text(encoding='utf-8'))
        if name.startswith('run_'):
            anchor="GRACEFUL_PROCESS_DRAIN_METHOD = CAMPAIGN / 'io-repair/GRACEFUL_PROCESS_DRAIN_V1.md'\n"
            text=replace_once(text,anchor,anchor+"COMPLETE_READER_METHOD = CAMPAIGN / 'io-repair/COMPLETE_PROCESS_AND_LITERAL_READS_V1.md'\n")
            text=replace_once(text,'    core = admission.runtime_identities(frozen)\n',
                "    require(frozen['sources'].get(COMPLETE_READER_METHOD.relative_to(REPO).as_posix()) == {\n"
                "                'sha256': sha(COMPLETE_READER_METHOD), 'bytes': COMPLETE_READER_METHOD.stat().st_size},\n"
                "            'Repaired source anchor must bind the exact complete-process/read declaration')\n"
                '    core = admission.runtime_identities(frozen)\n')
            text=text.replace('PRE_EXIT_DRAIN_METHOD, GRACEFUL_PROCESS_DRAIN_METHOD)',
                              'PRE_EXIT_DRAIN_METHOD, GRACEFUL_PROCESS_DRAIN_METHOD, COMPLETE_READER_METHOD)')
        else:
            anchor='    def test_graceful_method_is_required_before_runtime_validation(self):\n'
            extra='''    def test_complete_reader_method_is_required_before_runtime_validation(self):
        value=self.declaration()
        methods=[v for k,v in vars(c).items() if k.endswith('_METHOD')]
        sources={m.relative_to(c.REPO).as_posix():{'sha256':c.sha(m),'bytes':m.stat().st_size}
                 for m in methods if m!=c.COMPLETE_READER_METHOD}
        path=self.save('releases/RCI001-C02-dev-103/snapshot.json',{'revision':'RCI001-C02-dev-103','sources':sources})
        value['source_snapshot']=c.identity(path)
        with patch.object(c,'MAP',self.root),patch.object(c.admission.base,'frozen_problems',return_value=[]),\\
                patch.object(c.admission,'runtime_identities') as runtime:
            with self.assertRaisesRegex(ValueError,'complete-process/read declaration'):c.assert_sources(value)
            runtime.assert_not_called()

    def test_stopped_v30_identities_cannot_be_reused(self):
        value=self.declaration()
        value['stages']=[['native-029','native','RCI001-C02-dev-100',24000],
            ['boundary-030','boundary','RCI001-C02-dev-101',None],
            ['smoke-028','smoke','RCI001-C02-dev-102',24101],
            ['pilot-stock-027','stock','RCI001-C02-dev-102',24102],
            ['pilot-home-027','home','RCI001-C02-dev-102',24103]]
        with self.assertRaisesRegex(ValueError,'Qualifier identities'):self.load(value)

'''
            text=replace_once(text,anchor,extra+anchor)
        derive(p,Q/name.replace('v30','v31'),text)
    p=IO/'graceful-process-qualification-001/control.py';text=changed(p.read_text(encoding='utf-8'))
    text=text.replace('graceful-process-qualification-001','complete-reader-qualification-001')
    text=text.replace("IO / 'graceful-process-integration-001/full-checks-003'","IO / 'complete-reader-qualification-001/full-checks-001'")
    text=text.replace('lineage-checks-002','lineage-checks-001').replace('production-state-002','production-state-001')
    text=replace_once(text,"'graceful_process_diagnostic_terminal'):","'graceful_process_diagnostic_terminal', 'complete_reader_method', 'complete_reader_diagnostic'):")
    text=replace_once(text,"'raw-preflight-019', 'transport': 'transport-probe-022'","'raw-preflight-020', 'transport': 'transport-probe-023'")
    text=replace_once(text,"'--number', '030'","'--number', '031'")
    text=text.replace('prospective graceful-process-drain lineage','prospective complete-process/read lineage with unchanged graceful drainage')
    derive(p,HERE/'control.py',text)
    p=IO/'graceful-process-qualification-001/settle_host.py';derive(p,HERE/'settle_host.py',p.read_text(encoding='utf-8'))
    for p in (C/'admission/prepare_certificate.py',C/'admission/test_prepare_admission.py'):
        text=changed(p.read_text(encoding='utf-8'))
        if p.name=='prepare_certificate.py':
            anchor="        'native_process_drain_method': CAMPAIGN / 'io-repair/GRACEFUL_PROCESS_DRAIN_V1.md',\n"
            text=replace_once(text,anchor,anchor+"        'complete_process_readers_method': CAMPAIGN / 'io-repair/COMPLETE_PROCESS_AND_LITERAL_READS_V1.md',\n"
                "        'complete_process_readers_diagnostic': CAMPAIGN / 'io-repair/complete-process-readers-001/diagnostic-replay-001.json',\n")
        derive(p,p,text)
    write(HERE/'derivation.json',json.dumps({'changes':edits,'scope':'Fresh V31; preserve all old attempts, model policy and gates.'},indent=2)+'\n')
    print(json.dumps({'prepared_files':len(edits)}))

if __name__=='__main__':main()
