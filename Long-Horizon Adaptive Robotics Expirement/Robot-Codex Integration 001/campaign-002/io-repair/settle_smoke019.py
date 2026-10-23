"""Settle the failed Smoke019 queue once, without scientific assessment."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE.parent
spec = importlib.util.spec_from_file_location('smoke019_journal', C / 'qualification/run_final_qualification_v21.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
RUN = 'RCI001-C02-smoke-019'
JOB = '20260928T210749155181Z-d083eeb7'
REV = 'RCI001-C02-dev-061'
records = C / 'qualification' / RUN
analysis = HERE / 'smoke-019-transport-failure-analysis.json'

job = c.official(JOB)
c.require(job['id'] == JOB and job['state'] == 'failed'
          and type(job['exit_status']) is int and job['exit_status'] == 1,
          'Fresh failed/integer-one official status required')
c.require(job == c.read(C / 'qualification/smoke-019-queue.json'), 'Official queue receipt changed')
c.save_exact(records / 'official-status.json', job)
c.require(analysis.is_file(), 'Retained infrastructure diagnosis required')
diagnosis = c.read(analysis)
c.require(diagnosis.get('run_id') == RUN and diagnosis.get('queue_job_id') == JOB,
          'Wrong retained diagnosis identity')
reason = ('Official smoke queue failed with integer1 before its planned interruption: '
          'the parent transport rejected an HTTP2 reset on an unavailable stream. '
          'Stream identity and reset code were not retained. Native cleanup then completed, '
          'but transport and namespace qualification failed; restart was not attempted. '
          'No task outcome assessed.')
failure = records / 'queue-failure.json'
c.save_exact(failure, {'schema': 'campaign002-unassessed-queue-failure-1',
    'run_id': RUN, 'framework_revision': REV, 'assessment_state': 'not_assessed',
    'scorable': False, 'task_outcome': 'unknown', 'ended_at': job['ended_at'],
    'queue': c.identity(records / 'official-status.json'), 'reason': reason,
    'diagnosis': c.identity(analysis),
    'scope': 'Failed smoke infrastructure disposition; no qualification or task-performance evidence.'})
target = c.MAP / 'releases' / REV / ('result-' + RUN)
receipt = c.command_once(records / 'settle', 'finish', c.python(C / 'registry.py', 'finish',
    '--run-id', RUN, '--result', failure, '--queue-receipt', records / 'official-status.json',
    '--execution', 'failed', '--validity', 'invalid', '--outcome', 'unknown', '--reason', reason),
    inputs=[failure, records / 'official-status.json', analysis],
    outputs=[target / 'result-record.json', target / 'result.json', target / 'queue.json'],
    absent=[target])
print(json.dumps({'run_id': RUN, 'settlement': c.identity(target / 'result-record.json'),
                  'receipt_exit': receipt['exit_code'], 'failure': c.identity(failure)}))
