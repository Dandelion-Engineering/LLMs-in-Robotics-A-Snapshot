"""Queue source-bound report regressions followed by historical row staging."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent;I=HERE.parent;C=I.parent;REPO=C.parents[2]
QUEUE=REPO.parent/'tools/compute_queue/compute_queue.py'
FILES=[I/'qualification_report.py',I/'qualification_qa.py',I/'test_qualification_report.py',
       I/'test_session19_history_contracts.py',HERE/'stage_rows.py',Path(__file__)]

def source_bindings():return {str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in FILES}
def save(p,x):
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,indent=2);f.write('\n')

def main():
    if sys.argv[1:] == ['submit']:
        assert not (HERE/'stage-submit-001.json').exists()
        save(HERE/'stage-intent-001.json',{'sources':source_bindings(),'scope':'Tests and eighteen already-terminal history rows only; no canonical write.'})
        argv=[sys.executable,'-X','utf8','-B',str(QUEUE),'submit','--project','LLMs-in-Robotics','--cwd',str(REPO),
              '--',sys.executable,'-X','utf8','-B',str(Path(__file__).resolve()),'run']
        job=json.loads(subprocess.check_output(argv,text=True,encoding='utf-8'))
        save(HERE/'stage-submit-001.json',job);print(json.dumps({'id':job['id'],'state':job['state']}));return
    assert sys.argv[1:]==['run']
    before=source_bindings();assert before==json.loads((HERE/'stage-intent-001.json').read_text(encoding='utf-8'))['sources']
    out=HERE/'queued-001';out.mkdir(exist_ok=False);receipts=[]
    for label,args in [
        ('existing-tests',['-m','unittest','discover','-s',str(I),'-p','test_qualification_report.py','-v']),
        ('new-tests',['-m','unittest','discover','-s',str(I),'-p','test_session19_history_contracts.py','-v']),
        ('stage',[str(HERE/'stage_rows.py')])]:
        cmd=[sys.executable,'-X','utf8','-B',*args]
        with (out/(label+'.stdout')).open('x',encoding='utf-8') as so,(out/(label+'.stderr')).open('x',encoding='utf-8') as se:
            p=subprocess.run(cmd,cwd=REPO,stdout=so,stderr=se)
        item={'label':label,'argv':cmd,'exit_code':p.returncode};receipts.append(item)
        save(out/(label+'-receipt.json'),item)
        if p.returncode!=0:
            save(out/'result.json',{'passed':False,'stopped_at':label,'executions':receipts,'sources':before});raise SystemExit(p.returncode)
    assert source_bindings()==before
    save(out/'result.json',{'passed':True,'executions':receipts,'sources':before,'sources_unchanged':True})
    print(json.dumps({'passed':True,'staged_rows':18}))

if __name__=='__main__':main()
