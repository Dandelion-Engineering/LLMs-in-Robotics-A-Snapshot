"""Derive fresh V30 orchestration; no launch, freeze, registration or scoring."""
from pathlib import Path
import difflib
import hashlib
import json
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
IO = HERE.parent
C = IO.parent
Q = C/'qualification'
QUEUE = Path('C:/Users/cresp/Documents/Dandelion Engineering/tools/compute_queue/compute_queue.py')
INTEGRATION = IO/'graceful-process-integration-001'

def save(path, value):
    with path.open('x', encoding='utf-8') as f: json.dump(value,f,indent=2);f.write('\n')

def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as f:f.write(value)

def identity(path):
    return {'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

def replace_all(text, pairs):
    return re.sub('|'.join(re.escape(k) for k in sorted(pairs,key=len,reverse=True)),
                  lambda m:pairs[m.group()],text)

def main():
    job=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(QUEUE),'status',
        '20260930T180834895340Z-3fc48ff6'],text=True,encoding='utf-8'))
    assert job['state']=='succeeded' and type(job['exit_status']) is int and job['exit_status']==0
    save(INTEGRATION/'full-check-terminal-003.json',job)
    tests=json.loads((INTEGRATION/'full-checks-003/test-execution.json').read_text(encoding='utf-8'))
    assert tests['passed'] is True
    pairs={'v29':'v30','V29':'V30','final-qualification-029':'final-qualification-030',
        'host-probe-030':'host-probe-031','host-probe-029':'host-probe-030',
        'native-028':'native-029','boundary-029':'boundary-030','smoke-027':'smoke-028',
        'pilot-stock-026':'pilot-stock-027','pilot-home-026':'pilot-home-027',
        'raw-preflight-019':'raw-preflight-020','transport-probe-022':'transport-probe-023',
        'dev-093':'dev-099','dev-094':'dev-100','dev-095':'dev-101','dev-096':'dev-102',
        'dev093':'dev099','dev094':'dev100','dev095':'dev101','dev096':'dev102',
        '94, 95, 96, 96, 96':'100, 101, 102, 102, 102',
        'anchor_number == 93':'anchor_number == 99',"[0][2]) == 94":"[0][2]) == 100",
        'prepare_model_v21.py':'prepare_model_v22.py','registry_session15.py':'registry_session19.py'}
    changes=[]
    for name in ('run_final_qualification_v29.py','test_run_final_qualification_v29.py'):
        source=Q/name; target=Q/name.replace('v29','v30')
        before=source.read_text(encoding='utf-8'); after=replace_all(before,pairs)
        if name.startswith('run_'):
            after=after.replace('Run five fresh qualifiers with native transport drainage before process exit.',
                'Run five fresh qualifiers with bounded graceful native process drainage.')
            anchor="PRE_EXIT_DRAIN_METHOD = CAMPAIGN / 'io-repair/native-pre-exit-drain-001/DECLARATION.md'\n"
            assert after.count(anchor)==1
            after=after.replace(anchor,anchor+"GRACEFUL_PROCESS_DRAIN_METHOD = CAMPAIGN / 'io-repair/GRACEFUL_PROCESS_DRAIN_V1.md'\n")
            anchor='    core = admission.runtime_identities(frozen)\n'
            after=after.replace(anchor,"    require(frozen['sources'].get(GRACEFUL_PROCESS_DRAIN_METHOD.relative_to(REPO).as_posix()) == {\n"
                "                'sha256': sha(GRACEFUL_PROCESS_DRAIN_METHOD), 'bytes': GRACEFUL_PROCESS_DRAIN_METHOD.stat().st_size},\n"
                "            'Repaired source anchor must bind the exact graceful-process-drain declaration')\n"+anchor)
            after=after.replace('PILOT_RETIREMENT_INVENTORY_METHOD, PRE_EXIT_DRAIN_METHOD)',
                'PILOT_RETIREMENT_INVENTORY_METHOD, PRE_EXIT_DRAIN_METHOD, GRACEFUL_PROCESS_DRAIN_METHOD)')
            after=after.replace('PREPARED_INDEX_LABELS_METHOD, PILOT_RETIREMENT_INVENTORY_METHOD)],',
                'PREPARED_INDEX_LABELS_METHOD, PILOT_RETIREMENT_INVENTORY_METHOD, PRE_EXIT_DRAIN_METHOD, GRACEFUL_PROCESS_DRAIN_METHOD)],')
        else:
            anchor='    def test_stopped_v28_identities_cannot_be_reused(self):\n'
            assert after.count(anchor)==1
            extra='''    def test_graceful_method_is_required_before_runtime_validation(self):
        value=self.declaration()
        methods=[v for k,v in vars(c).items() if k.endswith('_METHOD')]
        sources={m.relative_to(c.REPO).as_posix():{'sha256':c.sha(m),'bytes':m.stat().st_size}
                 for m in methods if m!=c.GRACEFUL_PROCESS_DRAIN_METHOD}
        path=self.save('releases/RCI001-C02-dev-099/snapshot.json',{'revision':'RCI001-C02-dev-099','sources':sources})
        value['source_snapshot']=c.identity(path)
        with patch.object(c,'MAP',self.root),patch.object(c.admission.base,'frozen_problems',return_value=[]),\\
                patch.object(c.admission,'runtime_identities') as runtime:
            with self.assertRaisesRegex(ValueError,'graceful-process-drain declaration'):c.assert_sources(value)
            runtime.assert_not_called()

    def test_stopped_v29_identities_cannot_be_reused(self):
        value=self.declaration()
        value['stages']=[['native-028','native','RCI001-C02-dev-094',24000],
            ['boundary-029','boundary','RCI001-C02-dev-095',None],
            ['smoke-027','smoke','RCI001-C02-dev-096',24101],
            ['pilot-stock-026','stock','RCI001-C02-dev-096',24102],
            ['pilot-home-026','home','RCI001-C02-dev-096',24103]]
        with self.assertRaisesRegex(ValueError,'Qualifier identities'):self.load(value)

'''
            after=after.replace(anchor,extra+anchor)
        write(target,after)
        changes.append({'before':identity(source),'after':identity(target)})
        write(HERE/(target.stem+'.diff'),''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile=name,tofile=target.name)))
    old=C/'registry_session15.py'; target=C/'registry_session19.py'
    write(target,old.read_text(encoding='utf-8').replace('Session 15','Session 19').replace('Codex session 15','Codex session 19'))
    changes.append({'before':identity(old),'after':identity(target)})
    source=IO/'native-pre-exit-drain-001/control.py'
    before=source.read_text(encoding='utf-8'); after=replace_all(before,pairs)
    replacements={"CHECKS = IO / 'checks-037'":"CHECKS = IO / 'graceful-process-integration-001/full-checks-003'",
        "DECLARATION = IO / 'v30-qualification-declaration.json'":"DECLARATION = IO / 'graceful-process-qualification-001/qualification-declaration.json'",
        "LINEAGE_CHECKS = IO / 'native-pre-exit-drain-001/lineage-checks-003/receipt.json'":"LINEAGE_CHECKS = IO / 'graceful-process-qualification-001/lineage-checks-001/receipt.json'",
        "SOURCE_STATE = IO / 'native-pre-exit-drain-001/production-state-004.json'":"SOURCE_STATE = IO / 'graceful-process-qualification-001/production-state-001.json'",
        "'pre_exit_method', 'pre_exit_diagnostic')":"'pre_exit_method', 'pre_exit_diagnostic',\n                 'graceful_process_method', 'graceful_process_diagnostic', 'graceful_process_diagnostic_terminal')",
        "'raw-preflight-018', 'transport': 'transport-probe-021'":"'raw-preflight-019', 'transport': 'transport-probe-022'",
        "manifest['scope'] += ' Fresh lineage enforces genuine transport EOF and complete byte drainage before native stdin closure within the original deadline; all model, task, timing, isolation, byte and retirement predicates remain required.'":"manifest['scope'] = ('Fresh no-model prerequisite for the prospective graceful-process-drain lineage. '\n        'Protocol quiescence precedes ordinary native stdin close; genuine EOF and complete byte drainage, '\n        'normal exit and final retirement remain required within the unchanged deadline. '\n        'No model, task, timing, isolation, byte or retirement predicate is relaxed.')",
        "IO / 'native-pre-exit-drain-001/settle_host.py'":"IO / 'graceful-process-qualification-001/settle_host.py'",
        "'--number', '029'":"'--number', '030'",
        "IO / 'v30-readiness-preflight-001.json'":"IO / 'graceful-process-qualification-001/readiness-preflight-001.json'"}
    for old,new in replacements.items():
        assert after.count(old)==1,(old,after.count(old))
        after=after.replace(old,new)
    write(HERE/'control.py',after)
    write(HERE/'control.diff',''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile=str(source),tofile='control.py')))
    source=IO/'native-pre-exit-drain-001/settle_host.py'
    write(HERE/'settle_host.py',source.read_text(encoding='utf-8').replace('session15','session19').replace('Codex session 15','Codex session 19'))
    for path in (C/'admission/prepare_certificate.py',C/'admission/test_prepare_admission.py'):
        before=path.read_text(encoding='utf-8'); after=replace_all(before,pairs)
        write(HERE/(path.name+'.before'),before)
        path.write_text(after,encoding='utf-8',newline='\n')
        write(HERE/(path.name+'.diff'),''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile=path.name,tofile=path.name)))
    save(HERE/'derivation.json',{'sources':changes,'scope':'Prospective V30 allocation and new method binding; old coordinator and old runs remain unchanged.'})
    print(json.dumps({'prepared':len(changes),'passed_HA_tests':tests['passed']}))

if __name__=='__main__':main()
