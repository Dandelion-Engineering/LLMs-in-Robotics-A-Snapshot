"""One queued source-bound full regression checkpoint; preserve all outcomes."""
import json
from pathlib import Path
import subprocess
import sys
import control

HERE=Path(__file__).resolve().parent;c=control.c

def identity(p):
    value=c.identity(p);value['bytes']=Path(p).stat().st_size;return value

def main():
    if len(sys.argv)>1 and sys.argv[1]=='submit':
        c.require(not (HERE/'checks-submit-002.json').exists() and not control.CHECKS.exists(),'Existing check footprint')
        command=c.python(Path(__file__).resolve(),'run')
        c.save(HERE/'checks-intent-002.json',{'argv':command,'runner':c.identity(__file__),'scope':'No-model full H/A/Q/admission regression tests'})
        job=json.loads(subprocess.check_output(c.python(c.QUEUE,'submit','--project','LLMs-in-Robotics','--cwd',c.REPO,'--',*command),text=True,encoding='utf-8'))
        c.save(HERE/'checks-submit-002.json',job);print(json.dumps({'job_id':job['id'],'state':job['state']}));return
    intent=c.read(HERE/'checks-intent-002.json');c.require(intent['runner']==c.identity(__file__),'Runner changed')
    paths={p for folder in ('harness','assessment','qualification','admission') for p in (control.C/folder).glob('*.py')}
    paths.update(control.C.glob('*.py'))
    before=[identity(p) for p in sorted(paths)]
    checked=[*HERE.glob('*.py'),HERE/'DECLARATION.md',control.IO/'COMPLETE_PROCESS_AND_LITERAL_READS_V2.md']
    source_before={p.relative_to(control.C).as_posix():{'sha256':c.sha(p),'bytes':p.stat().st_size} for p in [*sorted(paths),*checked]}
    result=subprocess.run(c.python(control.IO/'record_checks.py','run','--directory',control.CHECKS),cwd=c.REPO)
    tests=c.read(control.CHECKS/'test-execution.json')
    out=control.LINEAGE_CHECKS.parent;c.require(not out.exists(),'Existing lineage output');out.mkdir()
    executions=[]
    for label in ('qualification','admission'):
        directory=control.C/label
        command=[str(c.PYTHON),'-X','utf8','-B','-m','unittest','discover','-s',str(directory),'-p','test_*.py','-v']
        with (out/(label+'.stdout')).open('x',encoding='utf-8') as so,(out/(label+'.stderr')).open('x',encoding='utf-8') as se:
            run=subprocess.run(command,cwd=c.REPO,stdout=so,stderr=se)
        executions.append({'label':label,'argv':command,'exit_code':run.returncode,'stdout':c.identity(out/(label+'.stdout')),'stderr':c.identity(out/(label+'.stderr'))})
    after=[identity(p) for p in sorted(paths)]
    source_after={p.relative_to(control.C).as_posix():{'sha256':c.sha(p),'bytes':p.stat().st_size} for p in [*sorted(paths),*checked]}
    unchanged=before==after and source_before==source_after
    passed=result.returncode==0 and tests['passed'] is True and all(type(x['exit_code']) is int and x['exit_code']==0 for x in executions) and unchanged
    c.save(control.LINEAGE_CHECKS,{'schema':'campaign002-complete-reader-lineage-checks-1','passed':passed,'source_bindings':source_after,'executions':executions,'full_repair_tests':identity(control.CHECKS/'test-execution.json')})
    c.save(control.SOURCE_STATE,{'schema':'campaign002-full-production-source-state-1','passed':passed,'sources_unchanged':unchanged,'sources':after,'tests':c.identity(control.CHECKS/'test-execution.json')})
    print(json.dumps({'passed':passed,'source_count':len(after),'executions':[(x['label'],x['exit_code']) for x in executions]}),flush=True)
    raise SystemExit(0 if passed else 1)

if __name__=='__main__':main()
