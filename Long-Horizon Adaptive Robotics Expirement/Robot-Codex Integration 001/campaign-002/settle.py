"""Reconcile immutable dispositions and map records; never launch or resubmit."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import registry
import operate

HERE = Path(__file__).resolve().parent
TIMING_CHECKS = {'complete_retained_timing_replayed_and_passed',
                 'current_episode_frozen_full_sample_timing_and_scheduling'}


def numerical_timing_failure(value, errors):
    """Only a structurally replayed threshold failure can be ordinary."""
    if not isinstance(value, dict) or errors.get('timing'):
        return False
    report = value.get('replayed_timing', {})
    maximum = report.get('maximum_lag_s')
    windows = report.get('complete_wall_windows')
    fraction = report.get('outside_rtf_tolerance_fraction')
    rows = report.get('timing')
    outside = report.get('outside_rtf_tolerance_windows')
    return (value.get('schema') == 'rci-campaign-independent-timing-2'
            and value.get('passed') is False and value.get('scheduling_pass') is True
            and all(value.get(key) is True for key in ('resource_integrity_pass', 'garbage_collection_pass', 'host_memory_pass'))
            and value.get('garbage_collection', {}).get('passed') is True
            and value.get('host_memory', {}).get('passed') is True
            and type(value.get('sample_count')) is int and value['sample_count'] >= 2
            and all(isinstance(value.get(key), str) and re.fullmatch('[0-9a-f]{64}', value[key])
                    for key in ('metadata_sha256', 'sample_sha256'))
            and report.get('actual_host_timing_pass') is False
            and type(maximum) in (int, float) and math.isfinite(maximum) and maximum >= 0
            and type(windows) is int and windows >= 0
            and type(outside) is int and 0 <= outside <= windows
            and isinstance(rows, list) and len(rows) == windows
            and all(type(row.get('real_time_factor')) in (int, float) and math.isfinite(row['real_time_factor'])
                    and row.get('within_tolerance') is (.95 <= row['real_time_factor'] <= 1.05) for row in rows)
            and sum(row['within_tolerance'] is False for row in rows) == outside
            and (fraction == outside / windows if windows else fraction is None)
            and (maximum >= .1 or windows == 0 or
                 type(fraction) in (int, float) and math.isfinite(fraction) and fraction >= .01))


def classify(assessment, prior_invalid):
    if type(prior_invalid) is not int or prior_invalid < 0:
        raise ValueError('Invalid prior ordinary-invalid counter')
    failed = set(assessment.get('failed_checks', []))
    if assessment.get('validity') == 'valid':
        if failed or assessment.get('scorable') is not True or assessment.get('task_outcome') not in ('success', 'failure'):
            raise ValueError('Inconsistent scored valid disposition')
        return False, 0, 'All declared gates passed; protected independent evaluator ' + assessment['task_outcome'] + '.'
    if assessment.get('validity') != 'invalid' or assessment.get('scorable', False) is not False or assessment.get('task_outcome', 'unknown') != 'unknown':
        raise ValueError('Invalid attempts require an unknown unscored task outcome')
    ordinary = {'model_disposition_recognized', 'transport_revocation_and_reply_provenance'} | TIMING_CHECKS
    errors = assessment.get('verification_errors', {})
    ordinary_timing = not (failed & TIMING_CHECKS) or numerical_timing_failure(assessment.get('campaign_timing'), errors)
    ordinary_transport = ('transport_revocation_and_reply_provenance' not in failed or
                          str(errors.get('transport', '')).startswith('Unresolved transport failure:'))
    severe = (assessment.get('immediate_stop') is True or not failed or bool(failed - ordinary)
              or not ordinary_timing or not ordinary_transport)
    consecutive = prior_invalid + 1 if not severe else prior_invalid
    reason = ('Immediate infrastructure/evidence stop: ' if severe else 'Ordinary infrastructure-invalid attempt: ') + ', '.join(sorted(failed))
    if consecutive >= 2:
        reason = 'Predeclared stop after two consecutive ordinary infrastructure-invalid attempts. ' + reason
    return severe or consecutive >= 2, consecutive, reason


def settlement_context(run_id, folder, job):
    try:
        return operate.current_attempt(run_id, operate.REGISTRATION)
    except (ValueError, KeyError, TypeError, OSError) as error:
        # A changed live source must still permit diagnostic stop accounting.
        # This path authorizes no launch and consumes no host/model outcome.
        intent = operate.read(folder / 'launch-intent.json')
        seal = operate.read(operate.CERT.with_name('seal.json'))
        if (operate.sha(operate.CERT) != intent.get('certificate_sha256')
                or seal.get('certificate_sha256') != intent.get('certificate_sha256')
                or operate.sha(operate.REGISTRATION) != intent.get('registration_sha256')):
            raise ValueError('Cannot reconcile diagnostic stop: original admission identities conflict') from error
        cert = operate.read(operate.CERT)
        registration = operate.read(operate.REGISTRATION)
        attempts = cert.get('attempts', [])
        if (cert.get('schema') != 'campaign002-admission-1' or len(attempts) != 20
                or registration.get('certificate_sha256') != seal['certificate_sha256']
                or registration.get('release_revision') != cert.get('release_revision')
                or [(row.get('run_id'), row.get('manifest_sha256')) for row in registration.get('attempts', [])]
                != [(row.get('run_id'), row.get('manifest', {}).get('sha256')) for row in attempts]
                or [row.get('ordinal') for row in attempts] != list(range(1, 21))
                or len({row.get('run_id') for row in attempts}) != 20):
            raise ValueError('Cannot reconcile diagnostic stop: sealed allocation differs') from error
        matches = [row for row in attempts if row.get('run_id') == run_id]
        if len(matches) != 1 or intent.get('run_id') != run_id or intent.get('ordinal') != matches[0]['ordinal']:
            raise ValueError('Cannot reconcile diagnostic stop: launch/slot identity differs') from error
        operate.diagnostic(folder, run_id, job, 'admission_reverification_exception', str(error))
        return cert, seal, matches[0]


def exact_bytes(path, payload):
    path = Path(path)
    if path.exists():
        if not path.is_file() or path.read_bytes() != payload:
            raise ValueError('Conflicting immutable evidence copy: ' + str(path))
        return
    with path.open('xb') as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def reconcile_map_result(run_id, source_path, queue_path, validity, outcome, reason, execution, recorded_at):
    """Complete missing writes around an append, checking exact existing content."""
    source_path = Path(source_path)
    result = operate.read(source_path)
    if result.get('run_id') != run_id:
        raise ValueError('Map result source identity differs')
    job = operate.read(queue_path) if queue_path else None
    if execution == 'not_run':
        if validity != 'unknown' or outcome != 'not_assessed' or job is not None:
            raise ValueError('Invalid not-run map accounting')
    elif not operate.queue_succeeded(job or {}) and not (validity == 'invalid' and outcome == 'unknown'):
        raise ValueError('Unsuccessful queue cannot support a scored map outcome')
    data, _, _ = registry.prior.store(registry.MAP)
    runs = [row for row in data['run'] if row['id'] == run_id]
    if len(runs) != 1:
        raise ValueError('Map run identity absent or ambiguous')
    directory = registry.MAP / 'releases' / runs[0]['revision_id'] / ('result-' + run_id)
    directory.mkdir(parents=True, exist_ok=True)
    exact_bytes(directory / 'result.json', source_path.read_bytes())
    refs = [registry.prior.reference(registry.MAP, 'Retained campaign result', directory / 'result.json', 'evaluator_only')]
    if queue_path:
        exact_bytes(directory / 'queue.json', Path(queue_path).read_bytes())
        refs.append(registry.prior.reference(registry.MAP, 'Original shared queue terminal receipt', directory / 'queue.json'))
    record = {**registry.common(run_id + '-result'), 'recorded_at': recorded_at, 'run_id': run_id,
        'supersedes_result_id': None, 'execution_status': execution, 'validity': validity,
        'validity_reason': reason, 'outcome': outcome,
        'ended_at': None if execution == 'not_run' else (job.get('ended_at') or recorded_at),
        'termination_reason': reason, 'metrics': [], 'evidence': refs}
    record['details'] = {'source_result': result, 'queue_success_verified': operate.queue_succeeded(job or {}),
        'scope': 'Prospective Campaign 002 fixed-slot accounting. Invalid and unrun outcomes are not task scores.'}
    operate.save_exact(directory / 'result-record.json', record)
    # Refresh the canonical read after staging files. The append enforces its
    # observed prefix digest and the canonical store's own writer lock.
    data, raw, errors = registry.am.read_store(registry.MAP)
    if errors:
        raise ValueError(errors)
    matches = [row for row in data['result'] if row.get('run_id') == run_id]
    if matches:
        if matches != [record]:
            raise ValueError('Existing canonical map result conflicts with settlement intent')
    else:
        registry.am.append_record(registry.MAP, 'result', record, registry.am.store_digest(raw))
    registry.prior.refresh(registry.MAP)


def settle(run_id):
    folder = HERE / 'execution' / run_id
    job_path = folder / 'official-status.json'
    job = operate.read(job_path)
    if job.get('state') not in operate.TERMINAL_QUEUE_STATES:
        raise ValueError('Settlement requires an official terminal queue receipt')
    submitted = operate.read(folder / 'queue-submit.json')
    if submitted.get('id') != job.get('id'):
        raise ValueError('Official queue identity differs from submitted attempt')
    cert, seal, attempt = settlement_context(run_id, folder, job)
    ordinal = attempt['ordinal']
    prior_invalid = 0
    if ordinal > 1:
        previous = operate.read(HERE / 'execution' / cert['attempts'][ordinal - 2]['run_id'] / 'disposition.json')
        if previous['allow_next'] is not True:
            raise ValueError('Earlier terminal stop forbids settlement of later launch')
        prior_invalid = previous['consecutive_ordinary_infrastructure_invalid']
    if not operate.queue_succeeded(job):
        operate.diagnostic(folder, run_id, job, 'official_queue_failure', 'Official queue did not succeed with integer exit0')
    diagnostic_path = folder / 'diagnostic.json'
    diagnostic = diagnostic_path.exists()
    source = diagnostic_path if diagnostic else folder / 'assessment.json'
    assessment = operate.read(source)
    if assessment.get('run_id') != run_id or assessment.get('queue_job_id') != job['id']:
        raise ValueError('Assessment/diagnostic identity mismatch')
    if diagnostic:
        if (assessment.get('schema') != 'campaign002-diagnostic-1' or assessment.get('immediate_stop') is not True
                or assessment.get('bindings', {}).get('queue_receipt_sha256') != operate.sha(job_path)
                or any(assessment.get(key) != 'unknown' for key in ('task_outcome', 'observed_task_outcome'))):
            raise ValueError('Diagnostic receipt or unknown-outcome boundary differs')
    stop, consecutive, reason = classify(assessment, prior_invalid)
    execution = assessment['execution_status'] if diagnostic else 'completed'
    disposition = {key: attempt[key] for key in ('ordinal', 'run_id', 'family')}
    disposition.update(execution_status=execution, validity=assessment['validity'], task_outcome=assessment['task_outcome'],
        observed_task_outcome=assessment.get('observed_task_outcome'), scorable=assessment['scorable'], reason=reason,
        allow_next=not stop and ordinal < len(cert['attempts']), consecutive_ordinary_infrastructure_invalid=consecutive,
        assessment_sha256=None if diagnostic else operate.sha(source))
    if diagnostic:
        disposition.update(diagnostic_file='diagnostic.json', diagnostic_sha256=operate.sha(source))
    intent_path = folder / 'settlement-intent.json'
    pending_intent = intent_path.with_name(intent_path.name + '.pending')
    recorded_at = (operate.read(intent_path)['recorded_at'] if intent_path.exists()
                   else operate.read(pending_intent)['recorded_at'] if pending_intent.exists()
                   else datetime.now(timezone.utc).isoformat())
    intent = {'schema': 'campaign002-settlement-intent-1', 'recorded_at': recorded_at, 'run_id': run_id,
              'certificate_sha256': seal['certificate_sha256'], 'queue_receipt_sha256': operate.sha(job_path),
              'source_file': source.name, 'source_sha256': operate.sha(source), 'disposition': disposition,
              'stop': stop, 'consecutive': consecutive}
    operate.save_exact(intent_path, intent)
    reconcile_map_result(run_id, source, job_path, assessment['validity'], assessment['task_outcome'], reason, execution, recorded_at)
    operate.save_exact(folder / 'disposition.json', disposition)
    if stop or ordinal == len(cert['attempts']):
        final_reason = reason if stop else 'All twenty predeclared attempts are terminal; stop for Randy review.'
        for pending in cert['attempts'][ordinal:]:
            target = HERE / 'execution' / pending['run_id']
            # A partial not-run disposition can resume. Actual launch receipts
            # or runtime artifacts can never be relabeled as not run.
            if any((target / name).exists() for name in ('launch-intent.json', 'queue-submit.json', 'official-status.json', 'assessment.json', 'diagnostic.json')):
                raise ValueError('Pending slot has actual execution evidence; cannot mark not run')
            if any(Path(pending[name]).exists() for name in ('workspace', 'evidence', 'host_evidence') if name in pending):
                raise ValueError('Pending slot has runtime artifacts; cannot mark not run')
            target.mkdir(parents=True, exist_ok=True)
            unrun = {key: pending[key] for key in ('ordinal', 'run_id', 'family')}
            unrun.update(execution_status='not_run', validity='unknown', task_outcome='not_assessed', scorable=False,
                         reason=final_reason, allow_next=False, consecutive_ordinary_infrastructure_invalid=consecutive)
            operate.save_exact(target / 'disposition.json', unrun)
            reconcile_map_result(pending['run_id'], target / 'disposition.json', None,
                                 'unknown', 'not_assessed', final_reason, 'not_run', recorded_at)
        rows = [operate.read(HERE / 'execution' / row['run_id'] / 'disposition.json') for row in cert['attempts']]
        summary = {'schema': 'campaign002-stop-1', 'recorded_utc': recorded_at,
            'stop_after_ordinal': ordinal, 'reason': final_reason, 'planned': len(rows),
            'started': sum(row['execution_status'] != 'not_run' for row in rows),
            'valid_successes': sum(row['validity'] == 'valid' and row['task_outcome'] == 'success' for row in rows),
            'valid_failures': sum(row['validity'] == 'valid' and row['task_outcome'] == 'failure' for row in rows),
            'infrastructure_invalid': sum(row['validity'] == 'invalid' for row in rows),
            'not_run': sum(row['execution_status'] == 'not_run' for row in rows),
            'scored_outcome_of_invalid': 'unknown', 'remaining_admission_authorized': False}
        operate.save_exact(HERE / 'execution/campaign-stop.json', summary)
    print(json.dumps(disposition))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    settle(parser.parse_args().run_id)
