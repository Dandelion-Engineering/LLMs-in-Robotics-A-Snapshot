"""Record terminal operator retirement and the independently verified primary result.

One-shot documentation only: no model, simulator, launch, recovery or task writes.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tomllib

CODE = Path(__file__).resolve().parents[2]
REPO = CODE.parents[1]
sys.path.insert(0, str(CODE))
from common import read, save, canonical
from register import append, base, ref

PAIR = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v2')
OP = PAIR / 'operator/endpoint-audit-session34-001'
OUT = Path(__file__).parent


def main():
    endpoint = read(OP / 'verified-endpoint.json')
    audit = read(OP / 'output/result.json')
    assert endpoint['passed'] is True and endpoint['assignments_completed'] == 21
    assert audit['passed'] is True and len(audit['checks']) == 5 and all(audit['checks'].values())
    for status in (endpoint['official_queue'], endpoint['audit_queue']):
        assert status['state'] == 'succeeded' and type(status['exit_status']) is int and status['exit_status'] == 0
    assert not (OP / 'operator-retirement.json').exists(), 'Inspect prior receipt instead of repeating registration'
    automation_path = Path('C:/Users/cresp/.codex/automations/apartment-v2-baseline-observations/automation.toml')
    automation = tomllib.loads(automation_path.read_text(encoding='utf-8'))
    assert automation['status'] == 'PAUSED'
    assert automation['target_thread_id'] == '01a11bda-ab28-7290-842e-df267284ba99'
    root = Path(read(PAIR / 'baseline-lineage.json')['active_root'])
    assert root == PAIR / 'baseline' and read(PAIR / 'baseline-lineage.json')['history'] == []
    assert (root / 'completed.json').is_file() and not (root / 'running.lock').exists()
    script = "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|wsl|codex|node' -and $_.CommandLine -match 'apartment-v2|journal_service.py|guest_entry.py|broker.py' } | Select-Object ProcessId,ParentProcessId,Name,CreationDate,CommandLine | ConvertTo-Json -Depth 4"
    windows = subprocess.check_output(['powershell.exe', '-NoProfile', '-Command', script], text=True, encoding='utf-8').strip()
    assert not windows, 'Inspect remaining Windows process matches before closeout: ' + windows
    probe = "import pathlib,json,os; rows=[]\nfor p in pathlib.Path('/proc').iterdir():\n if p.name.isdigit() and int(p.name)!=os.getpid():\n  try:\n   c=(p/'cmdline').read_bytes().replace(bytes([0]),b' ').decode(errors='replace')\n   if any(t in c for t in ('apartment-v2','journal_service.py','guest_entry.py','Apartment Experiment/broker.py')): rows.append(dict(pid=int(p.name),command=c))\n  except (OSError,PermissionError): pass\nprint(json.dumps(rows))"
    linux = json.loads(subprocess.check_output(['wsl.exe', '-d', 'Ubuntu-24.04', '--', 'python3', '-B', '-c', probe], text=True, encoding='utf-8'))
    assert not linux, 'Inspect remaining Linux process matches before closeout'
    queue = REPO.parent / 'tools/compute_queue/compute_queue.py'
    active = []
    for state in ('queued', 'running', 'cancel_requested'):
        rows = json.loads(subprocess.check_output([sys.executable, '-X', 'utf8', '-B', str(queue), 'list', '--state', state], text=True, encoding='utf-8'))
        active.extend(row for row in rows if 'apartment-v2' in json.dumps(row).lower())
    assert not active, 'Apartment queue still active'
    now = datetime.now(timezone.utc).isoformat()
    retirement = dict(recorded_utc=now, windows_matches=[], linux_matches=[], active_apartment_queue=[],
                      running_lock_absent=True, runtime_retirement_audit=str(OP / 'output/result.json'),
                      browser=dict(url='http://127.0.0.1:51023', tab_id='1', closed=True,
                                   verification='CUA close succeeded; subsequent in-app browser tab inventory was empty.'),
                      passed=True)
    save(OP / 'operator-retirement.json', retirement)
    monitor = dict(automation_id=automation['id'], status=automation['status'], kind=automation['kind'],
                   target_thread=automation['target_thread_id'], interval_minutes=30, recorded_utc=now,
                   queue_job=endpoint['official_queue']['id'], pair=str(PAIR), endpoint_complete=True,
                   reason='Verified all-21-assignment Baseline endpoint and independent retirement audit passed.',
                   session_closeout='Session 34 ready for terminal Git closeout; no further observation scheduled')
    save(OP / 'monitoring-paused.json', monitor)
    save(OUT / 'monitoring.json', monitor)
    verified_ref = ref('Verified primary endpoint and assignment table', OP / 'verified-endpoint.json')

    def metric(name, value, unit, denominator=None, description='Absolute count for one complete Baseline history; no ratio denominator applies.'):
        return dict(name=name, value=value, unit=unit, denominator=denominator,
                    denominator_description=description, missing_reason=None, evidence=[verified_ref])

    result = {**base('APARTMENT-v2-baseline-result-001'), 'tags':['apartment','official','baseline','verified-endpoint'],
              'run_id':'APARTMENT-v2-baseline', 'supersedes_result_id':None,
              'execution_status':'completed', 'validity':'valid',
              'validity_reason':'Official queue succeeded with integer exit 0. Independent frozen-reader audit passed all five gates: exact completed checkpoint, source/model identity, inode/native/sensor/replay/transport history and retirement, retained attempt accounting, and pristine Maps. The primary lifecycle reader was checked on four retained engineering traces before official accounting.',
              'outcome':'success', 'ended_at':endpoint['official_queue']['ended_at'],
              'termination_reason':'All 21 assignments advanced; final normal docking/checkpoint and complete runtime retirement. Monitoring paused.',
              'metrics':[metric('endpoint_fresh_sessions',36,'sessions'), metric('normal_closed_sessions',36,'sessions'),
                         metric('abandoned_started_sessions',0,'sessions'), metric('failed_native_turns',0,'turns'),
                         metric('recovery_branches',0,'branches'),
                         metric('completed_assignments',21,'assignments',21,'The fixed 21-assignment condition schedule.'),
                         metric('successful_household_assignments',14,'assignments',14,'Seven bedroom and seven kitchen assignments with physical success.'),
                         metric('completed_throwing_windows',7,'practice windows',7,'Seven prescribed throwing practice windows; completion does not establish mastery.')],
              'evidence':[verified_ref, ref('Full independent frozen-reader audit',OP / 'output/result.json'),
                          ref('Official queue terminal',OP / 'official-queue-status.json'),
                          ref('Independent audit queue terminal',OP / 'queue-status.json'),
                          ref('Lifecycle reader engineering validation',OP / 'lifecycle-reader-validation.json'),
                          ref('Final checkpoint manifest',Path(endpoint['checkpoint']) / 'manifest.json'),
                          ref('Controller completed endpoint',root / 'completed.json'),
                          ref('Paused monitoring',OP / 'monitoring-paused.json'),
                          ref('Final process, queue and browser retirement',OP / 'operator-retirement.json')],
              'details':dict(condition_histories=1, independent_replicates=1, maps_status=endpoint['maps_status'],
                             clean_hibernations=1, clean_resumes=1, task_summary=endpoint['task_summary'],
                             assignment_table=endpoint['assignment_table'],
                             secondary_analysis_status=endpoint['secondary_analysis_status'],
                             limitations=endpoint['limitations'],
                             token_use_and_cost='unknown', throwing_attempt_census='unknown',
                             intervention='Authorized clean pause/resume only; no coaching, task reset, reroll, model retry or source/settings change.')}
    append('result', result, OUT)
    print(canonical(dict(registered=result['id'], monitoring=monitor['status'], retirement_passed=True)).decode())


if __name__ == '__main__':
    main()
