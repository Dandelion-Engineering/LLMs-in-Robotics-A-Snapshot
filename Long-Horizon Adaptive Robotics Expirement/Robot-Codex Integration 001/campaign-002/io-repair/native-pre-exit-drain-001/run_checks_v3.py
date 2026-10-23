"""Reuse unchanged passing H/A suites; recheck changed qualification/admission."""
import json
from pathlib import Path
import subprocess
import control

c=control.c
HERE=Path(__file__).resolve().parent

def identity(path):
    value=c.identity(path);value['bytes']=Path(path).stat().st_size;return value

def main():
    prior=c.read(HERE/'production-state-002.json')
    c.require(prior['sources_unchanged'] is True,'Previous source state changed during full tests')
    tests=c.read(control.CHECKS/'test-execution.json')
    c.require(tests['passed'] is True and prior['tests']==c.identity(control.CHECKS/'test-execution.json'),
              'Passing full H/A receipt missing or changed')
    tested={str(path.resolve()) for folder in ('harness','assessment') for path in (control.C/folder).glob('*.py')}
    old={row['path']:row for row in prior['sources'] if row['path'] in tested}
    c.require(set(old)==tested and all(identity(path)==row for path,row in old.items()),
              'Passing H/A source set changed; fresh full checks required')
    for command in tests['commands']:
        for key in ('stdout','stderr'):c.admission.artifact(command[key])
        for item in command['test_inputs']:c.admission.artifact(item)
    paths={path for folder in ('harness','assessment','qualification','admission')
           for path in (control.C/folder).glob('*.py')}
    paths.update(control.C.glob('*.py'))
    before=[identity(path) for path in sorted(paths)]
    checked=[path for path in HERE.glob('*.py')]+[HERE/'DECLARATION.md']
    source_before={path.relative_to(control.C).as_posix():{'sha256':c.sha(path),'bytes':path.stat().st_size}
                   for path in [*sorted(paths),*checked]}
    out=control.LINEAGE_CHECKS.parent
    c.require(not control.SOURCE_STATE.exists() and not out.exists(),'Existing check state; never repeat')
    out.mkdir()
    commands=[('qualification',control.Q,[str(c.PYTHON),'-X','utf8','-B','-m','unittest',
        'test_prepare_model_v21','test_prepare_native','test_prepare_model_v20',
        'test_prepare_boundary_v3','test_boundary_suite_v3','test_run_final_qualification_v29','-v']),
        ('admission',control.C/'admission',[str(c.PYTHON),'-X','utf8','-B','-m','unittest','test_prepare_admission','-v'])]
    executions=[]
    for label,cwd,command in commands:
        with (out/(label+'.stdout')).open('x',encoding='utf-8') as stdout,(out/(label+'.stderr')).open('x',encoding='utf-8') as stderr:
            result=subprocess.run(command,cwd=cwd,stdout=stdout,stderr=stderr)
        executions.append({'label':label,'argv':command,'exit_code':result.returncode,
                           'stdout':c.identity(out/(label+'.stdout')),'stderr':c.identity(out/(label+'.stderr'))})
    after=[identity(path) for path in sorted(paths)]
    source_after={path.relative_to(control.C).as_posix():{'sha256':c.sha(path),'bytes':path.stat().st_size}
                  for path in [*sorted(paths),*checked]}
    unchanged=before==after and source_before==source_after
    passed=all(item['exit_code']==0 for item in executions) and unchanged
    c.save(control.LINEAGE_CHECKS,{'schema':'campaign002-pre-exit-lineage-checks-2','passed':passed,
        'source_bindings':source_after,'executions':executions,
        'unchanged_passing_harness_assessment':{'source_state':c.identity(HERE/'production-state-002.json'),
            'tests':c.identity(control.CHECKS/'test-execution.json'),'verified_source_count':len(tested)}})
    c.save(control.SOURCE_STATE,{'schema':'campaign002-full-production-source-state-1','passed':passed,
        'sources_unchanged':unchanged,'sources':after,'tests':c.identity(control.CHECKS/'test-execution.json')})
    print(json.dumps({'passed':passed,'sources':len(after),'executions':[(x['label'],x['exit_code']) for x in executions]}))
    raise SystemExit(0 if passed else 1)

if __name__=='__main__':main()
