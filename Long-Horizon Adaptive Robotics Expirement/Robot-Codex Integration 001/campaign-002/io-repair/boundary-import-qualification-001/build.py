"""Bounded import fix and fresh V32 derivation; never launch an attempt."""
import difflib
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

HERE=Path(__file__).resolve().parent; IO=HERE.parent; C=IO.parent; Q=C/'qualification'
PAIRS={'v31':'v32','V31':'V32','final-qualification-031':'final-qualification-032',
    'host-probe-032':'host-probe-033','host-probe-031':'host-probe-032',
    'native-030':'native-031','boundary-031':'boundary-032','smoke-029':'smoke-030',
    'pilot-stock-028':'pilot-stock-029','pilot-home-028':'pilot-home-029',
    'raw-preflight-021':'raw-preflight-022','transport-probe-024':'transport-probe-025',
    'dev-103':'dev-107','dev-104':'dev-108','dev-105':'dev-109','dev-106':'dev-110',
    'dev103':'dev107','dev104':'dev108','dev105':'dev109','dev106':'dev110',
    '104, 105, 106, 106, 106':'108, 109, 110, 110, 110',
    'anchor_number == 103':'anchor_number == 107', '[0][2]) == 104':'[0][2]) == 108'}

def changed(text):
    return re.sub('|'.join(re.escape(k) for k in sorted(PAIRS,key=len,reverse=True)),lambda m:PAIRS[m.group()],text)

def identity(p):
    raw=p.read_bytes();return {'path':str(p.resolve()),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}

def write(p, text):
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
    # Isolated process reproduces the actual standalone loader environment.
    code="import sys, importlib.util; sys.path.insert(0, sys.argv[1]); import boundary_suite_v3 as b; s=importlib.util.spec_from_file_location('cold_capture_reader', b.CAMPAIGN/'assessment/retained_reads.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); assert callable(m.terminal_process_order); print('exact boundary reader loaded')"
    argv=[sys.executable,'-I','-B','-c',code,str(Q)]
    before=subprocess.run(argv,capture_output=True,text=True,encoding='utf-8')
    write(HERE/'cold-before.json',json.dumps({'argv':argv,'exit_code':before.returncode,'stdout':before.stdout,'stderr':before.stderr},indent=2)+'\n')
    assert before.returncode==1 and "No module named 'completion_chronology'" in before.stderr
    p=Q/'boundary_suite_v3.py';text=p.read_text(encoding='utf-8')
    anchor='sys.path.insert(0,str(HARNESS))\n';assert text.count(anchor)==1
    derive(p,p,text.replace(anchor,anchor+"sys.path.insert(0,str(CAMPAIGN/'assessment'))\n"))
    after=subprocess.run(argv,capture_output=True,text=True,encoding='utf-8')
    write(HERE/'cold-after.json',json.dumps({'argv':argv,'exit_code':after.returncode,'stdout':after.stdout,'stderr':after.stderr},indent=2)+'\n')
    assert after.returncode==0 and 'exact boundary reader loaded' in after.stdout
    p=Q/'test_boundary_suite_v3.py';text=p.read_text(encoding='utf-8')
    text=text.replace('import unittest\n','import unittest\nimport subprocess\nimport sys\n')
    marker="if __name__=='__main__':unittest.main()"
    extra='''class FreshBoundaryImport(unittest.TestCase):
    def test_standalone_boundary_loads_exact_reader_and_sibling_dependency(self):
        # -I discards PYTHONPATH and the invoking discovery process's imports.
        code = """import sys, importlib.util
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import boundary_suite_v3 as boundary
spec=importlib.util.spec_from_file_location('cold_capture_reader',boundary.CAMPAIGN/'assessment/retained_reads.py')
reader=importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
import completion_chronology
assert Path(completion_chronology.__file__).resolve()==(boundary.CAMPAIGN/'assessment/completion_chronology.py').resolve()
assert reader.terminal_process_order is completion_chronology.terminal_process_order
print('exact boundary reader loaded')
"""
        result=subprocess.run([sys.executable,'-I','-B','-c',code,str(candidate.CAMPAIGN/'qualification')],
                              capture_output=True,text=True,encoding='utf-8',timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),'exact boundary reader loaded')


'''
    assert text.count(marker)==1;derive(p,p,text.replace(marker,extra+marker))
    for name in ('run_final_qualification_v31.py','test_run_final_qualification_v31.py'):
        p=Q/name;derive(p,Q/name.replace('v31','v32'),changed(p.read_text(encoding='utf-8')))
    old=IO/'complete-reader-qualification-001'
    p=old/'control.py';text=changed(p.read_text(encoding='utf-8')).replace('complete-reader-qualification-001','boundary-import-qualification-001')
    text=text.replace('full-checks-002','full-checks-001').replace('lineage-checks-002','lineage-checks-001').replace('production-state-002','production-state-001')
    text=text.replace("'raw-preflight-020', 'transport': 'transport-probe-023'","'raw-preflight-021', 'transport': 'transport-probe-024'")
    text=text.replace("'--number', '031'","'--number', '032'")
    derive(p,HERE/'control.py',text)
    p=old/'settle_host.py';derive(p,HERE/'settle_host.py',p.read_text(encoding='utf-8'))
    p=old/'checks_v2.py';text=p.read_text(encoding='utf-8').replace('-002.json','-001.json');derive(p,HERE/'checks.py',text)
    for p in (C/'admission/prepare_certificate.py',C/'admission/test_prepare_admission.py'):
        derive(p,p,changed(p.read_text(encoding='utf-8')))
    write(HERE/'derivation.json',json.dumps({'changes':edits,'scope':'Standalone import path only; fresh V32 identities, same predicates and V23 source supplier.'},indent=2)+'\n')
    print(json.dumps({'files':len(edits),'cold_before':before.returncode,'cold_after':after.returncode}))

if __name__=='__main__':main()
