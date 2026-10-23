"""Submit the independent terminal Maps audit only after its worker has retired."""
import argparse
from datetime import datetime, timezone
import os
import subprocess
import sys
import json

from launch_maps import HERE, PAIR, FROZEN, FROZEN_CODE, OP, QUEUE, queue, succeeded
from common import read, save, sha, canonical


def main(expect):
    validation = read(OP / 'reader-validation.json')
    assert validation['passed'] is True and validation['reader_sha256'] == sha(HERE / 'audit_maps_terminal.py')
    lineage = read(PAIR / 'maps-lineage.json')
    from pathlib import Path
    root = Path(lineage['active_root']).resolve()
    assert root.is_relative_to(PAIR.resolve())
    job = read(OP / 'maps-launch-queue.json')['id']
    assert not lineage['history'], 'An explicit recovery needs its authenticated continuation queue receipt'
    status = queue('status', job)
    succeeded(status)
    assert not (root / 'running.lock').exists()
    if expect == 'completed':
        assert read(root / 'completed.json')['assignments'] == 21
    else:
        assert (root / 'hibernate-requested.json').exists() and not (root / 'completed.json').exists()
    out = OP / ('terminal-' + expect + '-001')
    out.mkdir(exist_ok=False)
    save(out / 'official-queue.json', status)
    command = [sys.executable, '-X', 'utf8', '-B', str(QUEUE), 'submit', '--project', 'LLMs-in-Robotics', '--cwd', str(FROZEN), '--',
               sys.executable, '-X', 'utf8', '-B', str(HERE / 'audit_maps_terminal.py'), '--root', str(root),
               '--code', str(FROZEN_CODE), '--queue-status', str(out / 'official-queue.json'), '--output', str(out / 'output'),
               '--expect', expect, '--baseline-identity', str(OP / 'prelaunch.json')]
    save(out / 'intent.json', dict(created_utc=datetime.now(timezone.utc).isoformat(), command=command, automatic_retry=False))
    response = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
    save(out / 'submission-response.json', dict(exit_status=response.returncode, stdout=response.stdout, stderr=response.stderr))
    assert response.returncode == 0, 'Submission uncertain; inspect before further action'
    submitted = json.loads(response.stdout)
    save(out / 'audit-queue.json', submitted)
    save(HERE / ('terminal-' + expect + '-audit-queue.json'), submitted)
    print(canonical(dict(job=submitted['id'], state=submitted['state'], evidence=str(out))).decode())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--expect', choices=('completed', 'hibernated'), required=True)
    main(parser.parse_args().expect)
