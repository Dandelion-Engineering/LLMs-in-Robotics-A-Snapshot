"""Run full affected report/QA regressions after the output-location correction."""
import json
from pathlib import Path
import subprocess
import sys
import stage_rows as base

HERE=Path(__file__).resolve().parent
FILES=[Path(__file__),base.I/'qualification_report.py',base.I/'qualification_qa.py',
    base.I/'test_qualification_report.py',base.I/'test_qualification_qa.py',base.I/'test_session19_history_contracts.py']
def bindings():return {str(p.resolve()):base.digest(p) for p in FILES}

def main():
    intent=HERE/'report-checks-intent-001.json';submit=HERE/'report-checks-submit-001.json';out=HERE/'report-checks-001'
    if sys.argv[1:]==['submit']:
        assert not out.exists()
        base.save(intent,{'sources':bindings()})
        job=json.loads(subprocess.check_output([sys.executable,'-X','utf8','-B',str(base.QUEUE),'submit','--project','LLMs-in-Robotics',
            '--cwd',str(base.REPO),'--',sys.executable,'-X','utf8','-B',str(Path(__file__).resolve()),'run'],text=True,encoding='utf-8'))
        base.save(submit,job);print(json.dumps({'job_id':job['id'],'state':job['state']}));return
    assert sys.argv[1:]==['run'];before=bindings();assert before==base.read(intent)['sources']
    out.mkdir(exist_ok=False);executions=[]
    for name in ('test_qualification_report.py','test_qualification_qa.py','test_session19_history_contracts.py'):
        cmd=[sys.executable,'-X','utf8','-B','-m','unittest','discover','-s',str(base.I),'-p',name,'-v']
        with (out/(name+'.stdout')).open('x',encoding='utf-8') as so,(out/(name+'.stderr')).open('x',encoding='utf-8') as se:
            r=subprocess.run(cmd,cwd=base.REPO,stdout=so,stderr=se)
        executions.append({'test':name,'argv':cmd,'exit_code':r.returncode})
    passed=all(x['exit_code']==0 for x in executions) and before==bindings()
    base.save(out/'result.json',{'passed':passed,'sources_unchanged':before==bindings(),'sources':before,'executions':executions})
    print(json.dumps({'passed':passed}));raise SystemExit(0 if passed else 1)

if __name__=='__main__':main()
