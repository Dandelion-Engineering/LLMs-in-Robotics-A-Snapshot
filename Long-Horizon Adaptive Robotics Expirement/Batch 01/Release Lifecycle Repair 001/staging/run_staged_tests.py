"""Queue-only deterministic staging checks; never execute a physical episode."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
REPAIR=HERE.parent
EXP=REPAIR.parents[1]
BASE=EXP/'Runtime'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=REPAIR/'staging-tests-001')
    args=parser.parse_args()
    # Guard before test/native dependency imports or evidence output creation.
    sys.path.insert(0,str(BASE))
    from release_runner import queued_job
    job=queued_job(expected_script=__file__)
    originals=json.loads((REPAIR/'original-source-references.json').read_text(encoding='utf-8'))
    for item in originals['source_files']:
        if digest(item['path'])!=item['sha256']:raise ValueError('Original source changed: '+item['path'])
    paths=sorted(BASE.glob('*.py'))+sorted(HERE.glob('*.py'))+[REPAIR/'original-source-references.json',REPAIR/'change-inventory.json',REPAIR/'README.md']
    before={str(path):digest(path) for path in paths}
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    report={'schema_version':'lifecycle-staging-tests-1','queue_job_id':job['id'],
            'started_at_utc':datetime.now(timezone.utc).isoformat(),'scope':'Synthetic regression checks, no robot/model/network execution',
            'source_files':[{'path':path,'sha256':value} for path,value in before.items()],
            'import_overlay':{'staging':str(HERE),'unmodified_dependency_runtime':str(BASE)},
            'all_required_checks_passed':False}
    try:
        sys.path.insert(0,str(HERE))
        for name in ('model_runtime','experiment'):
            if name in sys.modules:raise RuntimeError('Overlay module already imported before staging: '+name)
        model=importlib.import_module('model_runtime')
        supervisor=importlib.import_module('experiment')
        for module in (model,supervisor):
            if Path(module.__file__).resolve().parent!=HERE:raise RuntimeError('Staged overlay import not selected')
        # Legacy fake-cell fixtures enumerate the complete Runtime source set.
        # Point only this test process at its unchanged dependency directory;
        # no stage CLI episode, registration, source ZIP, model or Cell is run.
        supervisor.HERE=BASE
        modules=['test_model_runtime','test_experiment','test_model_lifecycle']
        suite=unittest.defaultTestLoader.loadTestsFromNames(modules)
        with (output/'unittest.log').open('x',encoding='utf-8',newline='\n') as log:
            result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
        report.update(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),
                      skipped=len(result.skipped),successful=result.wasSuccessful())
        after={str(path):digest(path) for path in paths}
        report['source_files_unchanged_before_after']=before==after
        report['source_inventory_unchanged']=sorted(BASE.glob('*.py'))==[p for p in paths if p.parent==BASE] and sorted(HERE.glob('*.py'))==[p for p in paths if p.parent==HERE]
        report['all_required_checks_passed']=result.wasSuccessful() and report['source_files_unchanged_before_after'] and report['source_inventory_unchanged']
    except BaseException as exc:
        report['error']=type(exc).__name__+': '+str(exc)
        raise
    finally:
        report['finished_at_utc']=datetime.now(timezone.utc).isoformat()
        (output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        print(json.dumps({'output':str(output),'all_required_checks_passed':report['all_required_checks_passed']}))
    if not report['all_required_checks_passed']:raise SystemExit(1)


if __name__=='__main__':main()
