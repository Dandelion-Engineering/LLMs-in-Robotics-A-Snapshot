"""Settle the original failed Smoke026 queue once; never assess or retry it."""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE.parent
spec = importlib.util.spec_from_file_location('smoke026_journal', C / 'qualification/run_final_qualification_v28.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
RUN = 'RCI001-C02-smoke-026'
JOB = '20260929T050327589414Z-e2cffb4f'
REV = 'RCI001-C02-dev-090'
ANALYSIS_SHA = '2611904daa2ce67fef888e426f1d9af7fb1309d5bc8c9a4d087cf8858effe35b'


def main():
    records = C / 'qualification' / RUN
    analysis = HERE / 'smoke026-queue-failure-diagnosis-001/analysis.json'
    job = c.official(JOB)
    c.require(job['id'] == JOB and job['state'] == 'failed'
              and type(job['exit_status']) is int and job['exit_status'] == 1,
              'Fresh failed/integer-one official status required')
    c.require(job == c.read(C / 'qualification/smoke-026-queue.json'), 'Official receipt changed')
    c.require(not (C / 'qualification/smoke-026-assessment.json').exists(),
              'Failed queue must have no empirical assessment')
    c.admission.artifact({'path': str(analysis), 'sha256': ANALYSIS_SHA})
    diagnosis = c.read(analysis)
    c.require(diagnosis.get('run_id') == RUN and diagnosis.get('queue_job_id') == JOB,
              'Wrong retained diagnosis identity')
    failure = records / 'queue-failure.json'
    target = c.MAP / 'releases' / REV / ('result-' + RUN)
    c.require(not failure.exists() and not target.exists() and not (records / 'settle').exists(),
              'Existing settlement state; reconcile without retry')
    c.save_exact(records / 'official-status.json', job)
    reason = ('Official smoke queue failed with integer1 after planned interruption. '
              'The first retained transport fault is channel_ConnectionAbortedError; '
              'source/state evidence points to an upload socket read, but exact OS error and cause are unknown. '
              'One channel lacks genuine client EOF and upload-drained evidence, so drain and namespace '
              'completion were unqualified. Observed byte equality and successful bounded native cleanup '
              'do not establish EOF. Resume, both pilots and scoring were not attempted. No task outcome assessed.')
    c.save_exact(failure, {'schema': 'campaign002-unassessed-queue-failure-1',
        'run_id': RUN, 'framework_revision': REV, 'assessment_state': 'not_assessed',
        'scorable': False, 'task_outcome': 'unknown', 'ended_at': job['ended_at'],
        'queue': c.identity(records / 'official-status.json'), 'reason': reason,
        'diagnosis': c.identity(analysis),
        'scope': 'Failed smoke infrastructure disposition; diagnosis is not qualification or task-performance evidence.'})
    receipt = c.command_once(records / 'settle', 'finish', c.python(C / 'registry.py', 'finish',
        '--run-id', RUN, '--result', failure, '--queue-receipt', records / 'official-status.json',
        '--execution', 'failed', '--validity', 'invalid', '--outcome', 'unknown', '--reason', reason),
        inputs=[failure, records / 'official-status.json', analysis, Path(__file__)],
        outputs=[target / 'result-record.json', target / 'result.json', target / 'queue.json'],
        absent=[target])
    print(json.dumps({'run_id': RUN, 'settlement': c.identity(target / 'result-record.json'),
                      'receipt_exit': receipt['exit_code'], 'failure': c.identity(failure)}))


if __name__ == '__main__':
    main()
