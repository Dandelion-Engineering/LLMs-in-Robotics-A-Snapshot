"""Single-use guarded queue submission for the fixed diagnostic, never scoring."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

import common
sys.path.insert(0,str(common.PACKET))
import collect_window
import trace_control


def observer_ready(config_sha256):
    value=trace_control.config(expected_sha=common.control_digest(config_sha256))
    trace_control.verify_sources(value,collect_window.source_paths())
    message=trace_control.receive(trace_control.CONTROL,'helper-ready',value)
    if (not message or message['payload'].get('session')!=trace_control.SESSION or
            message['payload'].get('simulated') is not False):
        raise RuntimeError('Live authenticated observer must be ready before queue submission')
    if any((trace_control.CONTROL/(phase+'.json')).exists() for phase in ('start','started','stop','finished')):
        raise RuntimeError('Observer transaction already used; no submission')
    peer=trace_control.RetainedProcess(message['payload']['identity'],value)
    try:
        if peer.exited(): raise RuntimeError('Observer exited before queue submission')
    finally: peer.close()
    return value['_sha256']


def guard_alive(monitor, records, *, require_ready=True):
    if monitor.poll() is not None or (records / 'storage/admission-stop.json').exists():
        raise RuntimeError('Storage monitor exited or latched admission stop; no queue submission')
    if require_ready and not (records / 'storage/ready.json').is_file():
        raise RuntimeError('Storage monitor has no readiness receipt')


def launch(manifest, snapshot, observer_config_sha256):
    common.validate(manifest, snapshot)
    common.output_paths(common.EVIDENCE, common.HOST, common.WORKSPACE)
    observer_ready(observer_config_sha256)
    if common.RECORDS.exists():
        raise ValueError('Existing intent footprint; never resubmit')
    common.RECORDS.mkdir(parents=True, exist_ok=False)
    argv = common.runner_argv(manifest, snapshot, observer_config_sha256)
    common.save(common.RECORDS / 'launch-intent.json', {
        'run_id': common.RUN, 'framework_revision': common.REVISION,
        'created_at': datetime.now(timezone.utc).isoformat(), 'diagnostic_only': True,
        'qualifier_claim': False, 'scorable': False, 'task_outcome': 'unknown', 'argv': argv,
        'snapshot': str(Path(snapshot).resolve()), 'snapshot_sha256': common.sha(snapshot),
        'manifest_sha256': common.sha(manifest), 'launcher_sha256': common.sha(__file__),
        'observer_config_sha256':observer_config_sha256,
        'queue_source_sha256': common.sha(common.QUEUE), 'storage_guard_sha256': common.sha(common.GUARD),
        'records': str(common.RECORDS), 'evidence': str(common.EVIDENCE),
        'host_evidence': str(common.HOST), 'workspace': str(common.WORKSPACE)})
    guard_argv = [sys.executable, '-X', 'utf8', '-B', str(common.GUARD), 'monitor',
        '--config', str(common.STORAGE_POLICY), '--baseline', str(common.STORAGE_BASELINE),
        '--output', str(common.RECORDS / 'storage'), '--job-file', str(common.RECORDS / 'queue-submit.json'),
        '--run-id', common.RUN, '--manifest', str(Path(manifest).resolve()),
        '--evidence', str(common.EVIDENCE), '--host-evidence', str(common.HOST), '--workspace', str(common.WORKSPACE)]
    with (common.RECORDS / 'monitor.stdout').open('x', encoding='utf-8') as out, \
         (common.RECORDS / 'monitor.stderr').open('x', encoding='utf-8') as err:
        monitor = subprocess.Popen(guard_argv, cwd=common.REPO, stdout=out, stderr=err,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
    common.save(common.RECORDS / 'monitor-process.json', {'pid': monitor.pid, 'argv': guard_argv})
    deadline = time.monotonic() + 45
    while not (common.RECORDS / 'storage/ready.json').exists():
        guard_alive(monitor, common.RECORDS, require_ready=False)
        if time.monotonic() > deadline:
            raise RuntimeError('Storage monitor readiness deadline')
        time.sleep(.2)
    # Revalidate all source and policy bytes after waiting, then make the fresh
    # alive/stop-latch check immediately before the sole queue mutation.
    common.validate(manifest, snapshot)
    common.output_paths(common.EVIDENCE, common.HOST, common.WORKSPACE)
    guard_alive(monitor, common.RECORDS)
    observer_ready(observer_config_sha256)
    raw = subprocess.check_output([sys.executable, '-X', 'utf8', '-B', str(common.QUEUE),
        'submit', '--project', 'LLMs-in-Robotics', '--cwd', str(common.REPO), '--', *argv],
        cwd=common.REPO, text=True, encoding='utf-8')
    job = json.loads(raw)
    common.save(common.RECORDS / 'queue-submit.json', job)
    print(json.dumps({'run_id': common.RUN, 'job_id': job['id'], 'state': job['state'],
                      'diagnostic_only': True, 'records': str(common.RECORDS)}))
    return job


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--observer-config-sha256',required=True)
    args = parser.parse_args(argv)
    launch(args.manifest, args.snapshot,args.observer_config_sha256)


if __name__ == '__main__':
    main()
