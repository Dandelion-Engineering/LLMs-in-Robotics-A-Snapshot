"""Reuse exact passing H/A sources and run fresh full Q/admission tests once."""
import json
from pathlib import Path
import subprocess
import sys
import control

c=control.c
HERE=Path(__file__).resolve().parent
PRIOR=control.IO/'graceful-process-integration-001'

def identity(path):
    value=c.identity(path);value['bytes']=Path(path).stat().st_size;return value

def main():
    if len(sys.argv)>1 and sys.argv[1]=='submit':
        c.require(not (HERE/'lineage-submit-002.json').exists() and not control.LINEAGE_CHECKS.parent.exists(),'Existing check footprint')
        command=c.python(Path(__file__).resolve(),'run')
        c.save(HERE/'lineage-intent-002.json',{'argv':command,'runner':c.identity(__file__),'scope':'No-model full qualification/admission regression tests'})
        job=json.loads(subprocess.check_output(c.python(c.QUEUE,'submit','--project','LLMs-in-Robotics','--cwd',c.REPO,'--',*command),text=True,encoding='utf-8'))
        c.save(HERE/'lineage-submit-002.json',job)
        print(json.dumps({'job_id':job['id'],'state':job['state']}));return
    intent=c.read(HERE/'lineage-intent-002.json')
    c.require(intent['runner']==c.identity(__file__),'Check runner changed')
    job=c.admission.base.queue_gate(c.official('20260930T180834895340Z-3fc48ff6'),'20260930T180834895340Z-3fc48ff6')
    c.require(job==c.read(PRIOR/'full-check-terminal-003.json'),'Full check official receipt changed')
    prior=c.read(PRIOR/'full-check-source-state-003.json')
    c.require(prior['passed'] is True and prior['sources_unchanged'] is True,'Previous full tests failed or changed sources')
    tests=c.read(control.CHECKS/'test-execution.json')
    c.require(tests['passed'] is True and prior['tests']==identity(control.CHECKS/'test-execution.json'),'Passing H/A receipt changed')
    tested={str(path.resolve()) for folder in ('harness','assessment') for path in (control.C/folder).glob('*.py')}
    old={row['path']:row for row in prior['sources'] if row['path'] in tested}
    c.require(set(old)==tested and all(identity(path)==row for path,row in old.items()),'H/A source set changed since full tests')
    for command in tests['commands']:
        for key in ('stdout','stderr'):c.admission.artifact(command[key])
        for item in command['test_inputs']:c.admission.artifact(item)
    paths={path for folder in ('harness','assessment','qualification','admission') for path in (control.C/folder).glob('*.py')}
    paths.update(control.C.glob('*.py'))
    before=[identity(path) for path in sorted(paths)]
    checked=[*HERE.glob('*.py'),HERE/'DECLARATION.md',control.IO/'GRACEFUL_PROCESS_DRAIN_V1.md']
    source_before={path.relative_to(control.C).as_posix():{'sha256':c.sha(path),'bytes':path.stat().st_size} for path in [*sorted(paths),*checked]}
    out=control.LINEAGE_CHECKS.parent
    c.require(not control.SOURCE_STATE.exists() and not out.exists(),'Existing output; no rerun')
    out.mkdir()
    executions=[]
    for label in ('qualification','admission'):
        cwd=control.C/label
        command=[str(c.PYTHON),'-X','utf8','-B','-m','unittest','discover','-s',str(cwd),'-p','test_*.py','-v']
        with (out/(label+'.stdout')).open('x',encoding='utf-8') as stdout,(out/(label+'.stderr')).open('x',encoding='utf-8') as stderr:
            result=subprocess.run(command,cwd=c.REPO,stdout=stdout,stderr=stderr)
        executions.append({'label':label,'argv':command,'exit_code':result.returncode,'stdout':c.identity(out/(label+'.stdout')),'stderr':c.identity(out/(label+'.stderr'))})
    after=[identity(path) for path in sorted(paths)]
    source_after={path.relative_to(control.C).as_posix():{'sha256':c.sha(path),'bytes':path.stat().st_size} for path in [*sorted(paths),*checked]}
    unchanged=before==after and source_before==source_after
    passed=all(type(x['exit_code']) is int and x['exit_code']==0 for x in executions) and unchanged
    c.save(control.LINEAGE_CHECKS,{'schema':'campaign002-graceful-process-lineage-checks-1','passed':passed,'source_bindings':source_after,'executions':executions,
        'unchanged_passing_harness_assessment':{'source_state':c.identity(PRIOR/'full-check-source-state-003.json'),'tests':c.identity(control.CHECKS/'test-execution.json'),'official_queue':c.identity(PRIOR/'full-check-terminal-003.json'),'verified_source_count':len(tested)}})
    c.save(control.SOURCE_STATE,{'schema':'campaign002-full-production-source-state-1','passed':passed,'sources_unchanged':unchanged,'sources':after,'tests':c.identity(control.CHECKS/'test-execution.json')})
    print(json.dumps({'passed':passed,'source_count':len(after),'executions':[(x['label'],x['exit_code']) for x in executions]}))
    raise SystemExit(0 if passed else 1)

if __name__=='__main__':main()
