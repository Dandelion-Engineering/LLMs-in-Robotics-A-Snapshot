"""Settle the terminal Native003 diagnostic once; never assess or retry it."""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE.parent
spec = importlib.util.spec_from_file_location('native003_journal', C / 'qualification/run_final_qualification_v28.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
RUN = 'RCI001-C02-shutdown-diagnostic-003'
JOB = '20260929T060538760771Z-877e2765'
REV = 'RCI001-C02-dev-091'
ANALYSIS_SHA = '4cb48a11a34de625bbd3678b54e9af82edfcfa23f1e20a1505fbd62b8b83bbe4'


def main():
    records = HERE / 'shutdown-diagnostic-003/records'
    analysis = HERE / 'socket-abort-native003-diagnosis-002/analysis.json'
    job = c.official(JOB)
    c.require(job['id'] == JOB and job['state'] == 'failed'
              and type(job['exit_status']) is int and job['exit_status'] == 1,
              'Fresh failed/integer-one official status required')
    c.require(job == c.read(HERE / 'socket-abort-native003-diagnosis-002/official-status.json'), 'Official receipt changed')
    c.require(not (HERE / 'shutdown-diagnostic-003/assessment.json').exists(),
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
    reason = ('The one-shot diagnostic failed with integer1 after the model turn reported usageLimitExceeded, '
              'before its prescribed action/interruption trigger. No socket_failure was recorded. '
              'The sole channel retained genuine EOF and upload drain; retained native, host and namespace '
              'cleanup completed. This is inconclusive for the original Smoke026 abort. '
              'No empirical qualification, task outcome, retry or scored launch is admitted.')
    c.save_exact(failure, {'schema': 'campaign002-unassessed-queue-failure-1',
        'run_id': RUN, 'framework_revision': REV, 'assessment_state': 'not_assessed',
        'scorable': False, 'task_outcome': 'unknown', 'ended_at': job['ended_at'],
        'queue': c.identity(records / 'official-status.json'), 'reason': reason,
        'diagnosis': c.identity(analysis),
        'scope': 'Failed one-shot diagnostic disposition; diagnosis is not qualification or task-performance evidence.'})
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
