"""Operator-only gates and exclusive submission of the original frozen Maps root."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

HERE = Path(__file__).resolve().parent
CODE = HERE.parents[1]
REPO = CODE.parents[1]
PAIR = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v2')
FROZEN = PAIR / 'frozen_repository'
FROZEN_CODE = FROZEN / 'Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'
OP = PAIR / 'operator/maps-session35-001'
QUEUE = REPO.parent / 'tools/compute_queue/compute_queue.py'
BASELINE_JOB = '20261008T141622993171Z-1784089b'
OLD_AUDIT_JOB = '20261008T172004542832Z-9771a5ef'
CHECKPOINT_SHA = 'db3541829b8ec8bd78a8138bf4a3b0ab84c7d3e4bf29eb7aaf4f58ce767d7933'
sys.path.insert(0, str(FROZEN_CODE))
from common import read, save, sha, inventory, canonical


def queue(*args):
    return json.loads(subprocess.check_output(
        [sys.executable, '-X', 'utf8', '-B', str(QUEUE), *args], text=True, encoding='utf-8'))


def succeeded(status):
    assert status['state'] == 'succeeded' and type(status['exit_status']) is int and status['exit_status'] == 0


def idle():
    jobs = sum((queue('list', '--state', s) for s in ('queued', 'running', 'cancel_requested')), [])
    matches = [j for j in jobs if 'apartment' in json.dumps(j).lower()]
    assert not matches, 'An apartment job is already active'
    script = "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|wsl|codex|node' -and $_.CommandLine -match 'apartment-v2|journal_service.py|guest_entry.py|broker.py' } | Select-Object ProcessId,ParentProcessId,Name,CreationDate,CommandLine | ConvertTo-Json -Depth 4"
    raw = subprocess.check_output(['powershell.exe', '-NoProfile', '-Command', script], text=True, encoding='utf-8').strip()
    windows = json.loads(raw) if raw else []
    if isinstance(windows, dict):
        windows = [windows]
    windows = [p for p in windows if p['ProcessId'] != os.getpid()]
    assert not windows, 'Matching Windows runtime remains active'
    probe = "import pathlib,json,os; rows=[]\nfor p in pathlib.Path('/proc').iterdir():\n if p.name.isdigit() and int(p.name)!=os.getpid():\n  try:\n   c=(p/'cmdline').read_bytes().replace(bytes([0]),b' ').decode(errors='replace')\n   if any(t in c for t in ('apartment-v2','journal_service.py','guest_entry.py','Apartment Experiment/broker.py')): rows.append(dict(pid=int(p.name),command=c))\n  except (OSError,PermissionError): pass\nprint(json.dumps(rows))"
    linux = json.loads(subprocess.check_output(['wsl.exe', '-d', 'Ubuntu-24.04', '--', 'python3', '-B', '-c', probe], text=True, encoding='utf-8'))
    assert not linux, 'Matching Linux runtime remains active'
    return dict(active_apartment_jobs=matches, other_active_jobs=jobs, windows_matches=windows, linux_matches=linux)


def preflight(label):
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), passed=False, checks={})
    try:
        prepared = read(PAIR / 'prepared.json')
        analysis = read(PAIR / 'analysis-freeze.json')
        assert prepared['passed'] is True and prepared['revision_id'] == 'APARTMENT-v2-reliability-frozen'
        assert analysis['passed'] is True and analysis['frozen_before_official_launch'] is True
        assert sha(PAIR / 'prepared.json') == analysis['prepared_sha256']
        assert sha(Path(analysis['analysis_path'])) == analysis['analysis_sha256']
        expected = read(FROZEN / 'source-manifest.json')
        actual = inventory(FROZEN)
        actual.pop('source-manifest.json')
        assert actual == expected and sha(FROZEN / 'source-manifest.json') == prepared['source_manifest_sha256']
        assert sha(FROZEN_CODE / 'commissioning.json') == prepared['certificate_sha256']
        result['checks']['original_frozen_source_and_evaluation'] = True
        baseline = PAIR / 'baseline'
        maps = PAIR / 'maps'
        for condition in ('baseline', 'maps'):
            lineage = read(PAIR / (condition + '-lineage.json'))
            assert Path(lineage['active_root']).resolve() == (PAIR / condition).resolve() and lineage['history'] == []
            assert not (PAIR / condition / 'running.lock').exists()
        run = read(maps / 'run.json')
        baseline_run = read(baseline / 'run.json')
        assert run['condition'] == 'maps' and run['stage'] == 'official' and run['launched'] is False
        assert set(p.name for p in maps.iterdir()) == {'filesystem', 'schedule.json', 'config.json', 'initial-filesystem.json', 'run.json'}
        assert inventory(maps / 'filesystem') == read(maps / 'initial-filesystem.json') == run['template'] == prepared['initial']['maps']
        assert sha(maps / 'initial-filesystem.json') == '2d55ad6837f8928464331be78b7a75b97495164284861e1dbb75299589e9784c'
        result['checks']['original_maps_pristine_and_unlaunched'] = True
        for key in ('source_identity', 'schedule_sha256', 'config_sha256'):
            assert run[key] == baseline_run[key]
        assert sha(maps / 'schedule.json') == sha(baseline / 'schedule.json') == sha(PAIR / 'hidden-schedule.json') == prepared['schedule_sha256']
        assert read(maps / 'config.json') == read(baseline / 'config.json') == prepared['config']
        from run import verify_run
        verify_run(maps, official_allowed=True)
        result['checks']['matched_schedule_model_runtime_configuration'] = True
        pointer = read(baseline / 'latest-checkpoint.json')
        assert pointer['session'] == 36 and pointer['manifest_sha256'] == CHECKPOINT_SHA
        assert sha(Path(pointer['path']) / 'manifest.json') == CHECKPOINT_SHA
        assert read(baseline / 'completed.json')['assignments'] == 21
        official = queue('status', BASELINE_JOB)
        old_audit = queue('status', OLD_AUDIT_JOB)
        succeeded(official)
        succeeded(old_audit)
        prior_result = PAIR / 'operator/endpoint-audit-session34-001/output/result.json'
        assert sha(prior_result) == '60eac582037157d0f7fd24b956d370430b2263cf568d271bb890d638d64dec0e'
        prior = read(prior_result)
        assert prior['passed'] is True and len(prior['checks']) == 5 and all(v is True for v in prior['checks'].values())
        result.update(baseline_queue=official, prior_audit_queue=old_audit, baseline_checkpoint=pointer)
        result['checks']['authenticated_baseline_endpoint_and_prior_audit'] = True
        result['idle'] = idle()
        result['checks']['no_duplicate_apartment_run'] = True
        result['frozen_source_files'] = len(expected)
        result['maps_initial_files'] = len(run['template'])
        result['source_manifest_sha256'] = prepared['source_manifest_sha256']
        result['schedule_sha256'] = prepared['schedule_sha256']
        result['certificate_sha256'] = prepared['certificate_sha256']
        result['maps_initial_inventory_sha256'] = sha(maps / 'initial-filesystem.json')
        result['baseline_identity'] = {name: sha(baseline / name) for name in (
            'run.json', 'config.json', 'schedule.json', 'completed.json', 'latest-checkpoint.json',
            'latest-execution.json', 'events.jsonl', 'filesystem-namespace.json', 'replay/index.json')}
        result['free_disk_gib'] = {d: shutil.disk_usage(d + ':/').free / 1024**3 for d in ('C', 'D')}
        result['passed'] = True
        save(OP / 'baseline-official-queue.json', official)
    except BaseException as error:
        result.update(error=repr(error), traceback=traceback.format_exc())
    save(OP / (label + '.json'), result)
    print(canonical({k: v for k, v in result.items() if k in ('passed', 'checks', 'error', 'traceback', 'free_disk_gib', 'maps_initial_files', 'frozen_source_files')}).decode())
    assert result['passed'], 'Prerequisite invalid; preserve evidence and stop without official repair'
    return result


def submit(label, command):
    intent = OP / (label + '-intent.json')
    with intent.open('xb') as stream:
        stream.write(canonical(dict(created_utc=datetime.now(timezone.utc).isoformat(), command=command,
                                    automatic_retry=False, authority_sha256=sha(OP / 'authority.json'))) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())
    response = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
    save(OP / (label + '-response.json'), dict(exit_status=response.returncode, stdout=response.stdout, stderr=response.stderr))
    assert response.returncode == 0, 'Submission uncertain; inspect preserved response and queue, never resubmit blindly'
    status = json.loads(response.stdout)
    save(OP / (label + '-queue.json'), status)
    save(HERE / (label + '-queue.json'), status)
    print(canonical(dict(action=label, job=status['id'], state=status['state'], evidence=str(OP))).decode())


def main(action):
    if action == 'audit':
        OP.mkdir(parents=True, exist_ok=False)
        transcript = REPO / 'chats/Codex-Human/Apartment Maps Launch and Monitoring/Apartment Maps Launch and Monitoring - Active.md'
        header = '**Randy (2026-10-08 10:41 PDT):**'
        body = transcript.read_text(encoding='utf-8')
        assert body.count(header) == 1
        authority = dict(header=header, message=body.split(header, 1)[1].strip(), source=str(transcript),
                         source_sha256=sha(transcript), captured_utc=datetime.now(timezone.utc).isoformat())
        save(OP / 'authority.json', authority)
        save(HERE / 'launch-authority.json', authority)
        preflight('preaudit')
        command = [sys.executable, '-X', 'utf8', '-B', str(QUEUE), 'submit', '--project', 'LLMs-in-Robotics', '--cwd', str(FROZEN), '--',
                   sys.executable, '-X', 'utf8', '-B', str(CODE / 'operations/session-33/audit_terminal.py'),
                   '--root', str(PAIR / 'baseline'), '--code', str(FROZEN_CODE),
                   '--queue-status', str(OP / 'baseline-official-queue.json'), '--output', str(OP / 'baseline-audit'), '--expect', 'completed']
        submit('baseline-audit', command)
    elif action == 'launch':
        status = queue('status', read(OP / 'baseline-audit-queue.json')['id'])
        save(OP / 'baseline-audit-terminal-queue.json', status)
        succeeded(status)
        audit = read(OP / 'baseline-audit/result.json')
        assert audit['passed'] is True and len(audit['checks']) == 5 and all(v is True for v in audit['checks'].values())
        preflight('prelaunch')
        command = [sys.executable, '-X', 'utf8', '-B', str(QUEUE), 'submit', '--project', 'LLMs-in-Robotics', '--cwd', str(FROZEN), '--',
                   sys.executable, '-X', 'utf8', '-B', str(FROZEN_CODE / 'run.py'), 'launch', '--root', str(PAIR / 'maps'), '--official']
        submit('maps-launch', command)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('audit', 'launch'))
    main(parser.parse_args().action)
