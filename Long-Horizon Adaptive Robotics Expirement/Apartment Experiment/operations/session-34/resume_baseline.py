"""Operator-only, one-shot audit and clean resume of the existing v2 baseline."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

CODE = Path(__file__).resolve().parents[2]
REPO = CODE.parents[1]
sys.path.insert(0, str(CODE))
from common import read, save, sha, canonical

PAIR = Path('D:/Dandelion-Apartment-Experiment/official/apartment-v2')
FROZEN = PAIR / 'frozen_repository'
FROZEN_CODE = FROZEN / 'Long-Horizon Adaptive Robotics Expirement/Apartment Experiment'
OP = PAIR / 'operator/resume-session34-001'
QUEUE = REPO.parent / 'tools/compute_queue/compute_queue.py'
OLD_JOB = '20261007T212505834217Z-26039466'
EXPECTED_CHECKPOINT = '09d4e72c95198337567e567bf3431293ea9ab64087bb4dfcef90306e79d53b9c'


def queue(*args):
    return json.loads(subprocess.check_output(
        [sys.executable, '-X', 'utf8', '-B', str(QUEUE), *args], text=True, encoding='utf-8'))


def idle(label):
    lineage = read(PAIR / 'baseline-lineage.json')
    root = Path(lineage['active_root']).resolve()
    assert root == (PAIR / 'baseline').resolve() and lineage['history'] == []
    assert not (root / 'running.lock').exists() and not (root / 'completed.json').exists()
    checkpoint = read(root / 'latest-checkpoint.json')
    assert checkpoint['session'] == 23 and checkpoint['manifest_sha256'] == EXPECTED_CHECKPOINT
    assert sha(Path(checkpoint['path']) / 'manifest.json') == EXPECTED_CHECKPOINT
    jobs = sum((queue('list', '--state', state) for state in ('queued', 'running', 'cancel_requested')), [])
    assert not any(str(PAIR).lower() in json.dumps(job).replace('\\\\', '\\').lower()
                   or 'apartment-v2' in json.dumps(job).lower() for job in jobs)
    script = "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|wsl|codex|node' -and $_.CommandLine -match 'apartment-v2|journal_service.py|guest_entry.py|broker.py' } | Select-Object ProcessId,ParentProcessId,Name,CreationDate,CommandLine | ConvertTo-Json -Depth 4"
    windows = subprocess.check_output(['powershell.exe', '-NoProfile', '-Command', script], text=True, encoding='utf-8').strip()
    assert not windows, 'Apartment runtime processes are still present: ' + windows
    probe = "import pathlib,json,os; rows=[]\nfor p in pathlib.Path('/proc').iterdir():\n if p.name.isdigit() and int(p.name)!=os.getpid():\n  try:\n   c=(p/'cmdline').read_bytes().replace(bytes([0]),b' ').decode(errors='replace')\n   if any(t in c for t in ('apartment-v2','journal_service.py','guest_entry.py','Apartment Experiment/broker.py')): rows.append(dict(pid=int(p.name),command=c))\n  except (OSError,PermissionError): pass\nprint(json.dumps(rows))"
    linux = json.loads(subprocess.check_output(['wsl.exe', '-d', 'Ubuntu-24.04', '--', 'python3', '-B', '-c', probe], text=True, encoding='utf-8'))
    assert not linux, 'Apartment Linux processes are still present'
    status = queue('status', OLD_JOB)
    assert status['state'] == 'succeeded' and type(status['exit_status']) is int and status['exit_status'] == 0
    proof = dict(observed_utc=datetime.now(timezone.utc).isoformat(), lineage=lineage,
                 checkpoint=checkpoint, old_queue=status, active_queue=jobs,
                 windows_matches=[], linux_matches=linux, running_lock_absent=True)
    save(OP / (label + '-idle.json'), proof)
    save(OP / 'official-queue-status.json', status)
    return root


def submit(label, argv):
    intent = OP / (label + '-intent.json')
    assert not intent.exists(), 'Submission already attempted; inspect its retained response'
    save(intent, dict(created_utc=datetime.now(timezone.utc).isoformat(), argv=argv, automatic_retry=False))
    response = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8')
    save(OP / (label + '-response.json'), dict(exit_status=response.returncode, stdout=response.stdout, stderr=response.stderr))
    assert response.returncode == 0, 'Queue outcome needs inspection; do not resubmit'
    status = json.loads(response.stdout)
    save(OP / (label + '-queue.json'), status)
    save(Path(__file__).with_name(label + '-queue.json'), status)
    print(canonical(dict(action=label, job=status['id'], state=status['state'], evidence=str(OP))).decode())


def main(action):
    if action == 'audit':
        OP.mkdir(parents=True, exist_ok=False)
        transcript = REPO / 'chats/Codex-Human/Apartment Simulation Commissioning/Apartment Simulation Commissioning - Active.md'
        header = '**Randy (2026-10-08 07:08 PDT):**'
        text = transcript.read_text(encoding='utf-8')
        assert text.count(header) == 1
        authority = dict(header=header, message=text.split(header, 1)[1].strip(),
                         source=str(transcript), source_sha256=sha(transcript), captured_utc=datetime.now(timezone.utc).isoformat())
        save(OP / 'authority.json', authority)
        save(Path(__file__).with_name('resume-authority.json'), authority)
        root = idle('preaudit')
        argv = [sys.executable, '-X', 'utf8', '-B', str(QUEUE), 'submit', '--project', 'LLMs-in-Robotics', '--cwd', str(FROZEN), '--',
                sys.executable, '-X', 'utf8', '-B', str(CODE / 'operations/session-33/audit_terminal.py'),
                '--root', str(root), '--code', str(FROZEN_CODE), '--queue-status', str(OP / 'official-queue-status.json'),
                '--output', str(OP / 'audit'), '--expect', 'hibernated']
        submit('audit', argv)
    else:
        audit_status = queue('status', read(OP / 'audit-queue.json')['id'])
        save(OP / 'audit-terminal-queue.json', audit_status)
        assert audit_status['state'] == 'succeeded' and type(audit_status['exit_status']) is int and audit_status['exit_status'] == 0
        result = read(OP / 'audit/result.json')
        assert result['passed'] is True and len(result['checks']) == 5 and all(v is True for v in result['checks'].values())
        root = idle('preresume')
        argv = [sys.executable, '-X', 'utf8', '-B', str(QUEUE), 'submit', '--project', 'LLMs-in-Robotics', '--cwd', str(FROZEN), '--',
                sys.executable, '-X', 'utf8', '-B', str(FROZEN_CODE / 'run.py'), 'launch', '--root', str(root), '--official', '--resume']
        submit('resume', argv)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('audit', 'resume'))
    main(parser.parse_args().action)
