"""Settle one successful diagnostic without promoting it to qualification."""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE.parent.parent
spec = importlib.util.spec_from_file_location('native004_journal', C/'qualification/run_final_qualification_v28.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
RUN = 'RCI001-C02-shutdown-diagnostic-004'
JOB = '20260929T172359627310Z-e9b8409e'
REV = 'RCI001-C02-dev-092'

def main():
    records = HERE.parent/'shutdown-diagnostic-004/records'
    job = c.official(JOB)
    c.require(job['id'] == JOB and job['state'] == 'succeeded'
              and type(job['exit_status']) is int and job['exit_status'] == 0, 'Fresh official success required')
    c.require(job == c.read(HERE/'official-status.json'), 'Official terminal receipt changed')
    observations = c.read(HERE/'observations.json')
    c.require(observations['run_id'] == RUN and observations['job_id'] == JOB
              and observations['original_inputs_unchanged'] is True, 'Wrong diagnostic inputs')
    for row in observations['inputs']:
        c.admission.artifact({'path':row['path'], 'sha256':row['sha256']})
    target = c.MAP/'releases'/REV/('result-'+RUN)
    result_path = records/'diagnostic-completion.json'
    c.require(not target.exists() and not result_path.exists() and not (records/'settle').exists(),
              'Existing settlement state; reconcile without retry')
    c.save_exact(records/'official-status.json', job)
    reason = ('One declared action/interruption diagnostic completed with genuine EOF, no socket error, '
              'native and host exit0, and qualified owned cleanup. The original abort was not reproduced, '
              'so the error-versus-stdin-close ordering question remains inconclusive. '
              'No full qualification, scored task outcome, replacement or unchanged retry is admitted.')
    c.save_exact(result_path, {'schema':'campaign002-unassessed-diagnostic-completion-1',
        'run_id':RUN, 'framework_revision':REV, 'assessment_state':'not_assessed',
        'diagnostic_only':True, 'scorable':False, 'task_outcome':'unknown', 'ended_at':job['ended_at'],
        'queue':c.identity(records/'official-status.json'), 'reason':reason,
        'diagnosis':c.identity(HERE/'observations.json'), 'findings':c.identity(HERE/'FINDINGS.md')})
    spec2 = importlib.util.spec_from_file_location('native004_registry', C/'registry.py')
    registry = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(registry)
    original = registry.common
    def session15(identifier):
        value = original(identifier); value['author']='Codex session 15'; return value
    registry.common = registry.prior.common = session15
    c.save_exact(records/'settle-intent.json', {'run_id':RUN,'job_id':JOB,
        'result':c.identity(result_path),'execution':'completed','validity':'unknown','outcome':'not_assessed'})
    result = registry.finish(RUN,result_path,records/'official-status.json','unknown','not_assessed',reason,'completed')
    c.save_exact(records/'settle-receipt.json', {'result':result,'record':c.identity(target/'result-record.json')})
    print(json.dumps(result))

if __name__ == '__main__': main()
