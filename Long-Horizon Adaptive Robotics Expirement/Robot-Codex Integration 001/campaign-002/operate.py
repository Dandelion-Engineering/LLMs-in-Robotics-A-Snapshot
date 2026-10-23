"""Campaign 002 sealed direct queue submissions; never retries a scored slot."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
RCI = HERE.parent
REPO = RCI.parents[1]
PYTHON = REPO / 'venv/Scripts/python.exe'
QUEUE = Path('C:/Users/cresp/Documents/Dandelion Engineering/tools/compute_queue/compute_queue.py')
GUARD = RCI / 'campaign-001/admission/storage-guard/storage_guard.py'
CERT = HERE / 'admission/sealed-v1/certificate.json'
REGISTRATION = RCI.parent / 'Architecture Map/releases/RCI001-C02-frozen-001/registration.json'
TERMINAL_QUEUE_STATES = {'succeeded', 'failed', 'canceled', 'interrupted', 'worker_start_failed'}

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    temporary = path.with_name(path.name + '.pending')
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')
        stream.flush(); os.fsync(stream.fileno())
    os.rename(temporary, path)

def save_exact(path, value):
    """Reconcile only an identical committed/pending record; never overwrite."""
    path = Path(path)
    if path.exists():
        if read(path) != value:
            raise ValueError('Conflicting immutable record: ' + str(path))
        return
    temporary = path.with_name(path.name + '.pending')
    if temporary.exists():
        if read(temporary) != value:
            raise ValueError('Conflicting pending immutable record: ' + str(temporary))
        with temporary.open('r+b') as stream:
            os.fsync(stream.fileno())
        os.rename(temporary, path)
        return
    save(path, value)

def queue_succeeded(job):
    return job.get('state') == 'succeeded' and type(job.get('exit_status')) is int and job['exit_status'] == 0

def guard_ready(monitor, folder):
    if monitor.poll() is not None or (Path(folder) / 'storage/admission-stop.json').exists():
        raise RuntimeError('Storage guard exited or latched admission stop; no queue submission')
    if not (Path(folder) / 'storage/ready.json').exists():
        raise RuntimeError('Storage guard has no readiness receipt; no queue submission')

def diagnostic(folder, run_id, job, kind, error):
    """Queue/assessor failure metadata only: never open host/model outcomes."""
    folder = Path(folder)
    if job.get('state') not in TERMINAL_QUEUE_STATES:
        raise ValueError('Diagnostic settlement requires an official terminal queue state')
    path = folder / 'diagnostic.json'
    binding = sha(folder / 'official-status.json')
    if path.exists():
        value = read(path)
        if (value.get('schema') != 'campaign002-diagnostic-1' or value.get('run_id') != run_id
                or value.get('queue_job_id') != job['id'] or value.get('bindings', {}).get('queue_receipt_sha256') != binding):
            raise ValueError('Conflicting diagnostic identity or official queue receipt')
        return value
    value = {'schema': 'campaign002-diagnostic-1', 'run_id': run_id, 'queue_job_id': job['id'],
             'recorded_at': job.get('ended_at'), 'diagnostic_kind': kind, 'error': str(error),
             'execution_status': 'completed' if queue_succeeded(job) else 'failed',
             'validity': 'invalid', 'task_outcome': 'unknown', 'observed_task_outcome': 'unknown',
             'scorable': False, 'immediate_stop': True,
             'failed_checks': ['unassessed_infrastructure_or_evidence_failure'],
             'boundary_status': 'unverified', 'evidence_status': 'unverified', 'retirement_status': 'unverified',
             'bindings': {'queue_receipt_sha256': binding, 'operator_source_sha256': sha(__file__),
                 'launch_intent_sha256': sha(folder / 'launch-intent.json') if (folder / 'launch-intent.json').is_file() else None,
                 'partial_assessment_sha256': sha(folder / 'assessment.json') if (folder / 'assessment.json').is_file() else None},
             'scope': 'Diagnostic metadata only. No host/model outcome was consumed. Unverified boundaries, evidence and retirement require immediate stop; this attempt cannot support a task score.'}
    save_exact(path, value)
    return value

def command(argv):
    result = subprocess.run([str(x) for x in argv], cwd=REPO, capture_output=True,
                            text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout or 'Command failed')
    return result.stdout

def queue(*args):
    return json.loads(command([PYTHON, '-X', 'utf8', '-B', QUEUE, *args]))

def current_attempt(run_id, registration):
    sys.path.insert(0, str(HERE))
    import admission as admitted
    seal = read(CERT.with_name('seal.json'))
    cert = admitted.verify_certificate(CERT, seal['certificate_sha256'])
    admitted.verify_registration(registration, cert, seal['certificate_sha256'])
    attempt = next(x for x in cert['attempts'] if x['run_id'] == run_id)
    return cert, seal, attempt

def start(args):
    cert, seal, attempt = current_attempt(args.run_id, args.registration)
    ordinal = attempt['ordinal']
    for prior in cert['attempts'][:ordinal - 1]:
        disposition = HERE / 'execution' / prior['run_id'] / 'disposition.json'
        if not disposition.exists() or read(disposition).get('allow_next') is not True:
            raise ValueError('Earlier slot is unfinished or campaign has stopped: ' + prior['run_id'])
    for name in ('workspace', 'evidence', 'host_evidence'):
        if Path(attempt[name]).exists():
            raise ValueError('Existing attempt path prevents resubmission: ' + name)
    folder = HERE / 'execution' / args.run_id
    if folder.exists():
        raise ValueError('Existing execution directory; reconcile retained intent, never resubmit')
    argv = [str(PYTHON), '-X', 'utf8', '-B', str(HERE / 'harness/physical.py'),
            '--manifest', attempt['manifest']['path'], '--evidence', attempt['evidence'],
            '--host-evidence', attempt['host_evidence'], '--workspace', attempt['workspace'], '--mode', 'pilot']
    if args.dry_run:
        print(json.dumps({'run_id': args.run_id, 'ordinal': ordinal, 'argv': argv, 'dry_run': True})); return
    folder.mkdir(parents=True)
    save(folder / 'launch-intent.json', {'created_at': datetime.now(timezone.utc).isoformat(),
         'run_id': args.run_id, 'ordinal': ordinal, 'argv': argv, 'certificate_sha256': seal['certificate_sha256'],
         'operator_source_sha256': sha(__file__), 'registration_sha256': sha(args.registration)})
    guard_argv = [str(PYTHON), '-X', 'utf8', '-B', str(GUARD), 'monitor',
                  '--config', cert['artifacts']['storage_policy']['path'],
                  '--baseline', cert['artifacts']['storage_baseline']['path'],
                  '--output', str(folder / 'storage'), '--job-file', str(folder / 'queue-submit.json'),
                  '--run-id', args.run_id, '--manifest', attempt['manifest']['path'],
                  '--evidence', attempt['evidence'], '--host-evidence', attempt['host_evidence'],
                  '--workspace', attempt['workspace']]
    with (folder / 'monitor.stdout').open('x', encoding='utf-8') as out, (folder / 'monitor.stderr').open('x', encoding='utf-8') as err:
        monitor = subprocess.Popen(guard_argv, cwd=REPO, stdout=out, stderr=err,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
    save(folder / 'monitor-process.json', {'pid': monitor.pid, 'argv': guard_argv})
    deadline = time.monotonic() + 45
    while not (folder / 'storage/ready.json').exists():
        if monitor.poll() is not None or (folder / 'storage/admission-stop.json').exists():
            raise RuntimeError('External storage guard did not become ready; no queue submission')
        if time.monotonic() > deadline:
            raise RuntimeError('Storage guard readiness deadline; no queue submission')
        time.sleep(.2)
    guard_ready(monitor, folder)
    submit = queue('submit', '--project', 'LLMs-in-Robotics', '--cwd', str(REPO), '--', *argv)
    save(folder / 'queue-submit.json', submit)
    print(json.dumps({'run_id': args.run_id, 'job_id': submit['id'], 'state': submit['state'], 'monitor_pid': monitor.pid}))

def collect(args):
    folder = HERE / 'execution' / args.run_id
    submitted = read(folder / 'queue-submit.json')
    job = queue('status', submitted['id'])
    if job.get('id') != submitted['id']:
        raise ValueError('Official queue identity differs from submitted receipt')
    if job['state'] in ('running', 'queued', 'cancel_requested'):
        print(json.dumps({'run_id': args.run_id, 'job_id': job['id'], 'state': job['state']})); return
    if job['state'] not in TERMINAL_QUEUE_STATES:
        raise ValueError('Unrecognized official queue state')
    save_exact(folder / 'official-status.json', job)
    if (folder / 'diagnostic.json').exists() or not queue_succeeded(job):
        value = diagnostic(folder, args.run_id, job, 'official_queue_failure',
                           'Official terminal queue state ' + job['state'] + ', exit status ' + str(job.get('exit_status')))
        print(json.dumps(value)); return
    storage = folder / 'storage/receipt.json'
    if not storage.exists():
        print(json.dumps({'run_id': args.run_id, 'state': 'waiting_for_final_storage_receipt', 'queue': job['state']})); return
    output = folder / 'assessment.json'
    try:
        cert, seal, attempt = current_attempt(args.run_id, args.registration)
        if not output.exists():
            text = command([PYTHON, '-X', 'utf8', '-B', HERE / 'admission.py',
                            '--certificate', CERT, '--certificate-sha256', seal['certificate_sha256'],
                            '--registration', args.registration, '--run-id', args.run_id,
                            '--queue-receipt', folder / 'storage/queue-receipt.json', '--job-id', job['id'], '--output', output])
            print(text.strip())
        else:
            result = read(output)
            print(json.dumps({k: result.get(k) for k in ('run_id', 'validity', 'task_outcome', 'scorable', 'failed_checks')}))
    except (RuntimeError, ValueError, KeyError, TypeError, OSError) as error:
        value = diagnostic(folder, args.run_id, job, 'admission_or_assessment_exception',
                           type(error).__name__ + ': ' + str(error))
        print(json.dumps(value))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('start', 'collect'))
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--registration', type=Path, default=REGISTRATION)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    (start if args.action == 'start' else collect)(args)

if __name__ == '__main__':
    main()
