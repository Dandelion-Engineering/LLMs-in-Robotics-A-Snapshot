"""Retain full repaired-runtime checks and prospective qualification parity."""
import json
from pathlib import Path
import subprocess
import sys
import control

c=control.c
HERE=Path(__file__).resolve().parent

def identity(path):
    value=c.identity(path);value['bytes']=Path(path).stat().st_size;return value

def main():
    paths={path for folder in ('harness','assessment','qualification','admission')
           for path in (control.C/folder).glob('*.py')}
    paths.update(control.C.glob('*.py'))
    before=[identity(path) for path in sorted(paths)]
    checked=[path for path in HERE.glob('*.py')]+[HERE/'DECLARATION.md']
    checks_before={path.relative_to(control.C).as_posix():{'sha256':c.sha(path),'bytes':path.stat().st_size}
                   for path in [*sorted(paths),*checked]}
    c.require(not control.SOURCE_STATE.exists() and not control.LINEAGE_CHECKS.parent.exists(),
              'Existing check records; never repeat')
    result=subprocess.run(c.python(control.IO/'record_checks.py','run','--directory',control.CHECKS),cwd=c.REPO)
    execution=c.read(control.CHECKS/'test-execution.json')
    out=control.LINEAGE_CHECKS.parent;out.mkdir()
    command=[str(c.PYTHON),'-X','utf8','-B','-m','unittest',
        'test_prepare_model_v21','test_prepare_native','test_prepare_model_v20',
        'test_prepare_boundary_v3','test_boundary_suite_v3','test_run_final_qualification_v29','-v']
    with (out/'stdout.txt').open('x',encoding='utf-8') as stdout,(out/'stderr.txt').open('x',encoding='utf-8') as stderr:
        lineage=subprocess.run(command,cwd=control.Q,stdout=stdout,stderr=stderr)
    after=[identity(path) for path in sorted(paths)]
    checks_after={path.relative_to(control.C).as_posix():{'sha256':c.sha(path),'bytes':path.stat().st_size}
                  for path in [*sorted(paths),*checked]}
    passed=result.returncode==0 and execution['passed'] is True and lineage.returncode==0
    unchanged=before==after and checks_before==checks_after
    c.save(control.LINEAGE_CHECKS,{'schema':'campaign002-pre-exit-lineage-checks-1',
        'passed':lineage.returncode==0 and unchanged,'source_bindings':checks_after,
        'argv':command,'exit_code':lineage.returncode,'stdout':c.identity(out/'stdout.txt'),'stderr':c.identity(out/'stderr.txt')})
    c.save(control.SOURCE_STATE,{'schema':'campaign002-full-production-source-state-1',
        'passed':passed and unchanged,'sources_unchanged':unchanged,'sources':after,
        'tests':c.identity(control.CHECKS/'test-execution.json')})
    print(json.dumps({'passed':passed and unchanged,'sources':len(after),'lineage_exit':lineage.returncode}))
    raise SystemExit(0 if passed and unchanged else 1)

if __name__=='__main__':main()
