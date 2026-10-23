"""Preserve check001 and correct missing additive source closure in its fixture."""
import difflib
import json
from pathlib import Path
import subprocess
import sys
from build import identity,write

HERE=Path(__file__).resolve().parent;C=HERE.parents[1]

def main():
    q=C.parents[2].parent/'tools/compute_queue/compute_queue.py'
    j=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(q),'status','20260930T203850324350Z-e5f5e800'],text=True,encoding='utf-8'))
    assert j['state']=='failed' and type(j['exit_status']) is int and j['exit_status']==1
    write(HERE/'checks-terminal-001.json',json.dumps(j,indent=2)+'\n')
    edits=[]
    def change(p,text):
        before=p.read_text(encoding='utf-8');backup=HERE/('check001-'+p.name+'.before')
        with backup.open('xb') as f:f.write(p.read_bytes())
        p.write_text(text,encoding='utf-8',newline='\n')
        edits.append({'before':identity(backup),'after':identity(p)})
        write(HERE/('check002-'+p.name+'.diff'),''.join(difflib.unified_diff(before.splitlines(True),text.splitlines(True))))
    p=C/'qualification/test_prepare_native.py';t=p.read_text(encoding='utf-8')
    t=t.replace('import prepare_model_v23 as complete_reads\n','import prepare_model_v23 as complete_reads\nimport prepare_model_v24 as plain_print\n')
    t=t.replace('QUIESCENCE_CAMPAIGN_INPUTS += complete_reads.READER_INPUTS\n','QUIESCENCE_CAMPAIGN_INPUTS += complete_reads.READER_INPUTS\nQUIESCENCE_CAMPAIGN_INPUTS += plain_print.READER_INPUTS\n')
    t=t.replace("for name in ('prepare_model_v23.py',", "for name in ('prepare_model_v24.py', 'prepare_model_v23.py',")
    change(p,t)
    p=HERE/'control.py';t=p.read_text(encoding='utf-8').replace('full-checks-001','full-checks-002').replace('lineage-checks-001','lineage-checks-002').replace('production-state-001','production-state-002');change(p,t)
    p=HERE/'allocate.py';t=p.read_text(encoding='utf-8').replace('checks-submit-001','checks-submit-002').replace('checks-terminal-001','checks-terminal-002');change(p,t)
    write(HERE/'checks_v2.py',(HERE/'checks.py').read_text(encoding='utf-8').replace('-001.json','-002.json'))
    write(HERE/'fixture-correction.json',json.dumps({'original_official':identity(HERE/'checks-terminal-001.json'),
        'changes':edits,'cause':'Synthetic native fixture omitted new V24 module and declared inputs;21 errors before its predicates executed.',
        'production_predicates_changed':False,'preserved_check001':True},indent=2)+'\n')
    print(json.dumps({'corrected_fixture':True,'checkpoint002_ready':True}))

if __name__=='__main__':main()
