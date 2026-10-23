"""Settle Smoke027 once as failed execution and unknown task outcome."""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE.parent.parent
spec = importlib.util.spec_from_file_location('smoke027_registry_control', C / 'qualification/run_final_qualification_v29.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
RUN = 'RCI001-C02-smoke-027'
JOB = '20260929T182650537335Z-49496959'


def main():
    job = c.official(JOB)
    c.require(job['id'] == JOB and job['state'] == 'failed' and type(job['exit_status']) is int and job['exit_status'] == 1,
              'Fresh exact failed integer1 required')
    c.require(job == c.read(HERE / 'official-status.json'), 'Terminal official identity changed')
    records = C / 'qualification' / RUN
    target = c.MAP / 'releases/RCI001-C02-dev-096' / ('result-' + RUN)
    result_path = records / 'queue-failure.json'
    c.require(not target.exists() and not result_path.exists() and not (records / 'failure-settle-intent.json').exists(),
              'Existing settlement state; reconcile without retry')
    reason = ('Official queue failed with integer1 during the interruption stage. Bounded diagnosis records '
        'channel1 upload ConnectionAbortedError/10053 before actual stdin closure; the pre-exit barrier '
        'failed closed and both channels lack genuine EOF. Owned cleanup and durable retention remain '
        'recorded, but no empirical qualification or task outcome is assessed. Resume, both pilots and scoring unlaunched.')
    c.save_exact(records / 'official-status.json', job)
    c.save_exact(result_path, {'schema': 'campaign002-failed-queue-diagnostic-1', 'run_id': RUN,
        'framework_revision': 'RCI001-C02-dev-096', 'assessment_state': 'not_assessed', 'diagnostic_only': True,
        'scorable': False, 'task_outcome': 'unknown', 'ended_at': job['ended_at'],
        'queue': c.identity(records / 'official-status.json'), 'reason': reason,
        'diagnosis': c.identity(HERE / 'ordered-analysis.json'), 'findings': c.identity(HERE / 'FINDINGS.md')})
    spec2 = importlib.util.spec_from_file_location('smoke027_registry', C / 'registry_session15.py')
    registry = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(registry)
    c.save_exact(records / 'failure-settle-intent.json', {'run_id': RUN, 'job_id': JOB,
        'result': c.identity(result_path), 'execution': 'failed', 'validity': 'invalid', 'outcome': 'unknown'})
    result = registry.finish(RUN, result_path, records / 'official-status.json', 'invalid', 'unknown', reason, 'failed')
    c.save_exact(records / 'failure-settle-receipt.json', {'result': result, 'record': c.identity(target / 'result-record.json')})
    print(json.dumps(result))


if __name__ == '__main__':
    main()
