"""Resume the sealed 20-slot campaign through the existing operator and settler.

This coordinator never implements a model or simulator launch. Only operate.start
may submit the existing direct shared-queue command. Ambiguous launch intent is
left for explicit operator reconciliation; it is never retried or replaced.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import operate
import settle

HERE = Path(__file__).resolve().parent
POLL_SECONDS = 15.
STORAGE_GRACE_SECONDS = 60.
ACTIVE_QUEUE_STATES = {'queued', 'running', 'cancel_requested'}
COORDINATOR_ARTIFACT = 'campaign_coordinator'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def notice(**value):
    print(json.dumps({'schema': 'campaign002-coordinator-status-1', **value}), flush=True)


def load_allocation(registration):
    """Authenticate allocation metadata; full admission remains in operate."""
    registration = Path(registration)
    require(registration.resolve() == operate.REGISTRATION.resolve(),
            'Coordinator and settlement must use the same registered release')
    seal = operate.read(operate.CERT.with_name('seal.json'))
    digest = seal.get('certificate_sha256')
    require(isinstance(digest, str) and operate.sha(operate.CERT) == digest,
            'Certificate does not match its external seal')
    cert = operate.read(operate.CERT)
    registered = operate.read(registration)
    require(cert.get('schema') == 'campaign002-admission-1'
            and cert.get('campaign_id') == 'RCI001-Campaign002'
            and cert.get('release_revision') == 'RCI001-C02-frozen-001'
            and registered.get('schema') == 'campaign002-registration-1'
            and registered.get('certificate_sha256') == digest
            and registered.get('release_revision') == cert['release_revision'],
            'Wrong sealed campaign or registration identity')
    artifact = cert.get('artifacts', {}).get(COORDINATOR_ARTIFACT, {})
    require(Path(artifact.get('path', '')).resolve() == Path(__file__).resolve()
            and artifact.get('sha256') == operate.sha(__file__),
            'Coordinator source is not bound by the sealed certificate')
    attempts = cert.get('attempts', [])
    require(isinstance(attempts, list) and len(attempts) == 20,
            'Exactly 20 sealed attempts are required')
    for ordinal, attempt in enumerate(attempts, 1):
        pair = (ordinal - 1) // 2
        family = ('misplaced-stock', 'blocked-insert-home')[(ordinal - 1) % 2 ^ (pair % 2)]
        suffix = 'stock' if family == 'misplaced-stock' else 'home'
        require(type(attempt.get('ordinal')) is int and attempt['ordinal'] == ordinal
                and attempt.get('family') == family
                and attempt.get('run_id') == f'RCI001-C02-{suffix}-{pair + 1:02d}',
                'Sealed slot order, identity or family differs')
    require([(row.get('run_id'), row.get('manifest_sha256')) for row in registered.get('attempts', [])]
            == [(row['run_id'], row.get('manifest', {}).get('sha256')) for row in attempts],
            'Registration does not preserve all immutable slots')
    return cert, digest


@contextmanager
def coordinator_lock():
    """OS-held lock: concurrent coordinators fail; process exit releases it."""
    path = HERE / 'execution/.coordinator.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b'\0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError('Another coordinator holds the campaign lock') from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def footprint(attempt):
    return ((HERE / 'execution' / attempt['run_id']).exists()
            or any(Path(attempt[name]).exists() for name in ('workspace', 'evidence', 'host_evidence')))


def submitted_identity(attempt, certificate_sha256, registration):
    folder = HERE / 'execution' / attempt['run_id']
    require(folder.is_dir() and not folder.is_symlink(), 'Execution folder is not an ordinary directory')
    for name in ('launch-intent.json', 'queue-submit.json'):
        require((folder / name).is_file() and not (folder / name).is_symlink()
                and not (folder / (name + '.pending')).exists(),
                'Existing attempt has ambiguous or unsubmitted intent; explicit operator reconciliation required: ' + name)
    intent = operate.read(folder / 'launch-intent.json')
    expected_argv = [str(operate.PYTHON), '-X', 'utf8', '-B', str(HERE / 'harness/physical.py'),
                     '--manifest', attempt['manifest']['path'], '--evidence', attempt['evidence'],
                     '--host-evidence', attempt['host_evidence'], '--workspace', attempt['workspace'], '--mode', 'pilot']
    require(intent.get('run_id') == attempt['run_id'] and intent.get('ordinal') == attempt['ordinal']
            and intent.get('certificate_sha256') == certificate_sha256
            and intent.get('registration_sha256') == operate.sha(registration)
            and intent.get('argv') == expected_argv,
            'Retained launch intent conflicts with the sealed slot')
    submitted = operate.read(folder / 'queue-submit.json')
    require(isinstance(submitted.get('id'), str) and bool(submitted['id'].strip()),
            'Committed queue submission has no job identity; explicit operator reconciliation required')
    return folder, submitted['id']


def official_terminal(run_id, job_id):
    while True:
        job = operate.queue('status', job_id)
        require(job.get('id') == job_id, 'Official queue identity differs from submitted receipt')
        state = job.get('state')
        if state in operate.TERMINAL_QUEUE_STATES:
            return job
        require(state in ACTIVE_QUEUE_STATES, 'Unrecognized official queue state; no collection or next slot')
        notice(run_id=run_id, job_id=job_id, state=state)
        time.sleep(POLL_SECONDS)


def wait_for_storage(folder, run_id, job):
    """Bound missing-guard wait by official end time, including after restart."""
    ended = datetime.fromisoformat(job['ended_at'].replace('Z', '+00:00'))
    require(ended.tzinfo is not None, 'Official queue end time must have a timezone')
    remaining = max(0., min(STORAGE_GRACE_SECONDS, ended.timestamp() + STORAGE_GRACE_SECONDS - time.time()))
    deadline = time.monotonic() + remaining
    required = (folder / 'storage/receipt.json', folder / 'storage/queue-receipt.json')
    while not all(path.is_file() for path in required):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            operate.diagnostic(folder, run_id, job, 'final_storage_receipt_deadline',
                'Final storage and official queue receipts absent 60 seconds after official queue completion')
            return False
        notice(run_id=run_id, job_id=job['id'], state='waiting_for_final_storage_receipt',
               remaining_seconds=remaining)
        time.sleep(min(POLL_SECONDS, remaining))
    return True


def reconcile_attempt(attempt, certificate_sha256, registration):
    run_id = attempt['run_id']
    folder, job_id = submitted_identity(attempt, certificate_sha256, registration)
    job = official_terminal(run_id, job_id)
    operate.save_exact(folder / 'official-status.json', job)
    if not operate.queue_succeeded(job):
        # No assessor or host/model outcome is opened on this path.
        operate.diagnostic(folder, run_id, job, 'official_queue_failure',
                           'Official terminal queue did not succeed with integer exit status 0')
    elif not (folder / 'diagnostic.json').exists():
        if wait_for_storage(folder, run_id, job):
            operate.collect(SimpleNamespace(run_id=run_id, registration=registration, dry_run=False))
            require((folder / 'assessment.json').is_file() or (folder / 'diagnostic.json').is_file(),
                    'Collection produced no terminal assessment or diagnostic; no next slot')
    settle.settle(run_id)
    disposition = operate.read(folder / 'disposition.json')
    require(all(disposition.get(key) == attempt[key] for key in ('ordinal', 'run_id', 'family'))
            and type(disposition.get('allow_next')) is bool,
            'Settled disposition differs from sealed slot')
    require(attempt['ordinal'] < 20 or disposition['allow_next'] is False,
            'Last immutable slot cannot authorize another attempt')
    return disposition


def run(registration=operate.REGISTRATION):
    registration = Path(registration)
    cert, digest = load_allocation(registration)
    attempts = cert['attempts']
    with coordinator_lock():
        for index, attempt in enumerate(attempts):
            folder = HERE / 'execution' / attempt['run_id']
            if not folder.exists():
                require(not (HERE / 'execution/campaign-stop.json').exists(),
                        'Campaign stop already exists; no new launch')
                require(not footprint(attempt), 'Existing runtime output prevents resubmission')
                require(not any(footprint(later) for later in attempts[index + 1:]),
                        'Later slot evidence exists beyond an unfinished gap; explicit operator reconciliation required')
                # All source, registration, runtime, prior disposition and guard
                # admission gates execute inside this existing operator entry.
                operate.start(SimpleNamespace(run_id=attempt['run_id'], registration=registration, dry_run=False))
            disposition = reconcile_attempt(attempt, digest, registration)
            notice(run_id=attempt['run_id'], ordinal=attempt['ordinal'], state='settled',
                   allow_next=disposition['allow_next'])
            if disposition['allow_next'] is False:
                stop = operate.read(HERE / 'execution/campaign-stop.json')
                require(stop.get('schema') == 'campaign002-stop-1' and stop.get('planned') == 20
                        and stop.get('stop_after_ordinal') == attempt['ordinal']
                        and stop.get('remaining_admission_authorized') is False,
                        'Terminal stop accounting is incomplete or conflicts with settlement')
                notice(state='terminal', stop_after_ordinal=attempt['ordinal'], reason=stop.get('reason'))
                return stop
    raise RuntimeError('All immutable slots traversed without terminal stop accounting')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registration', type=Path, default=operate.REGISTRATION)
    args = parser.parse_args(argv)
    try:
        run(args.registration)
    except KeyboardInterrupt:
        notice(state='coordinator_interrupted', action='Reconcile retained intent and queue state before resuming')
        return 130
    except Exception as error:
        notice(state='coordinator_halted', error_type=type(error).__name__, error=str(error),
               action='No next slot launched; explicit reconciliation is required')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
