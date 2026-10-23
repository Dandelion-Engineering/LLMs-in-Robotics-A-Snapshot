"""Retain compact, immutable terminal evidence; never modify the experiment."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PAIR = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v3')
OP = PAIR / 'operator/failure-audit-session37-001'
QUEUE = REPO.parent / 'tools/compute_queue/compute_queue.py'

def read(path):
    return json.loads(path.read_bytes())

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    raw = (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
    with path.open('xb') as stream:
        stream.write(raw)

def copy(source, destination):
    raw = source.read_bytes()
    with destination.open('xb') as stream:
        stream.write(raw)
    assert destination.read_bytes() == raw
    return dict(path=str(source), retained_path=str(destination), bytes=len(raw), sha256=digest(source))

def main():
    audit_status = json.loads(subprocess.check_output(
        [sys.executable, '-X', 'utf8', '-B', str(QUEUE), 'status', '20261009T045015412900Z-efafe052'],
        text=True, encoding='utf-8'))
    assert audit_status['state'] == 'succeeded' and type(audit_status['exit_status']) is int and audit_status['exit_status'] == 0
    audit = read(OP / 'audit/output/result.json')
    assert audit['passed'] and len(audit['checks']) == 11 and all(audit['checks'].values())
    assert audit['official_outcome'] == 'failed' and audit['endpoint_complete'] is False
    runtime = read(OP / 'runtime-final.json')
    assert runtime['all_runtime_retired'] and not runtime['active_pair_queue']
    save(OP / 'audit/queue-terminal.json', audit_status)
    pairs = [
        (OP / 'audit/queue-terminal.json', 'failure-audit-terminal.json'),
        (OP / 'audit/output/result.json', 'failure-audit-result.json'),
        (OP / 'preservation/queue-terminal.json', 'failure-preservation-terminal.json'),
        (OP / 'preservation/output/result.json', 'failure-preservation-result.json'),
        (OP / 'operator-retirement.json', 'operator-retirement-failed.json'),
        (OP / 'runtime-final.json', 'runtime-final.json'),
        (OP / 'runtime-after-cleanup.json', 'runtime-after-cleanup.json'),
    ]
    refs = [copy(source, HERE / name) for source, name in pairs]
    execution = Path(read(PAIR / 'baseline/latest-execution.json')['path'])
    refs.append(copy(execution, HERE / 'failed-execution.json'))
    for label, status in [('official', read(OP / 'official-queue-status.json')), ('audit', audit_status)]:
        source = Path(status['log_path'])
        refs.append(copy(source, OP / (label + '-queue.log')))
    automations = []
    codex_root = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
    for path in sorted((codex_root / 'automations').glob('*/automation.toml')):
        config = tomllib.loads(path.read_text(encoding='utf-8'))
        if path.parent.name in ('apartment-v3-baseline-observations', 'apartment-v2-baseline-observations', 'apartment-v2-maps-observations'):
            assert config['status'] == 'PAUSED', path
            automations.append(dict(id=path.parent.name, status=config['status'], config_sha256=digest(path)))
    assert any(row['id'] == 'apartment-v3-baseline-observations' for row in automations)
    result = dict(recorded_utc=datetime.now(timezone.utc).isoformat(), official_job='20261009T010627656726Z-71e4ed51',
                  official_execution='failed', official_exit_status=1, endpoint_complete=False,
                  assignments_completed=9, assignment_denominator=21, normal_closed_sessions=14,
                  actual_native_turns=14, failed_workspace_startups=1, failed_workspace_session=15,
                  checkpoint='session-00014', checkpoint_manifest_sha256=audit['checkpoint_manifest_sha256'],
                  independent_audit_passed=True, independent_audit_checks=audit['checks'],
                  official_recorded_retirement_complete=False, operator_retirement_command_passed=False,
                  later_runtime_retirement_verified=True, active_pair_queue=[], viewer_closed=True,
                  viewer_evidence='CUA tab 1 at http://127.0.0.1:50062/ closed during terminal handling; browser 2 tab inventory then returned []. Final independent socket/process/mount check is runtime-final.json.',
                  automations=automations, disk_free_gib={drive: shutil.disk_usage(drive + ':/').free / 2**30 for drive in ('C', 'D')},
                  no_resume_or_relaunch=True, maps_pristine_unlaunched=True, original_v2_preserved=True,
                  scientific_comparison_performed=False, evidence=refs)
    save(OP / 'terminal-summary.json', result)
    copy(OP / 'terminal-summary.json', HERE / 'terminal-summary.json')
    print(json.dumps({key: result[key] for key in ('official_execution', 'assignments_completed', 'independent_audit_passed', 'later_runtime_retirement_verified', 'automations', 'disk_free_gib')}))

if __name__ == '__main__':
    main()
