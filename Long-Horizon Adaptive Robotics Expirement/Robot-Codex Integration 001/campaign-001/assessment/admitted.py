"""Independent admission consumer for the unchanged Campaign 001 framework.

The certificate SHA256 is an external pre-outcome seal, not a field trusted from
the certificate itself. This module never launches a model, simulator or job.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import datetime
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path

import assess as base

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
REPO = base.REPO
CAMPAIGN_ID = 'RCI001-Campaign001'
SNAPSHOT_SHA256 = 'd84c510ee923a395417944e70a90ab1fa3759bc0061c2b6a4a714fb708f25581'
ARCHIVE_SHA256 = '0624a55d4e57de93ec8371843b390d031be114eb1f06df6f86c9d3c8742120bd'
TIMING = {'maximum_lag_s_exclusive': .1, 'rtf_min': .95, 'rtf_max': 1.05,
          'outside_fraction_exclusive': .01}
REQUIRED_ARTIFACTS = ('protocol', 'original_plan', 'schedule', 'snapshot', 'archive',
                      'assessor', 'admitted_assessor', 'timing_source', 'approval',
                      'storage_monitor', 'storage_policy', 'storage_tests',
                      'preflight_capacity', 'retained_timing', 'retained_timing_queue', 'asset_refresh')


def require(condition, message):
    if condition is not True:
        raise ValueError(message)


def stamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None, 'Timestamp must have a timezone')
    return parsed.timestamp()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def same_path(left, right):
    return Path(left).resolve() == Path(right).resolve()


def artifact(record):
    path = Path(record['path'])
    require(path.is_absolute() and path.is_file() and not path.is_symlink(),
            'Artifact must be an existing absolute ordinary file: ' + str(path))
    require(base.hash_file(path) == record['sha256'], 'Artifact SHA256 mismatch: ' + str(path))
    return path


def monitor_class(source):
    text = Path(source).read_text(encoding='utf-8')
    tree = ast.parse(text)
    nodes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'TimingMonitor']
    require(len(nodes) == 1, 'Exactly one frozen TimingMonitor required')
    code = ast.get_source_segment(text, nodes[0])
    namespace = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['TimingMonitor'], hashlib.sha256(code.encode()).hexdigest()


def reconstruct_timing(history_path, host_path, source):
    """Use the exact frozen monitor, preserving journal versus per-tick evidence."""
    monitor_type, class_sha = monitor_class(source)
    events = base.jsonl(Path(history_path))
    starts = [event for event in events if event.get('type') == 'episode_started']
    stops = [event for event in events if event.get('type') == 'episode_stopped']
    require(len(starts) == len(stops) == 1, 'Exactly one episode start and stop required for timing')
    start, stop = starts[0], stops[0]
    ids = [event['event_id'] for event in events]
    require(all(type(value) is int for value in ids) and all(a < b for a, b in zip(ids, ids[1:])),
            'Protected journal event IDs must strictly increase')
    require(start['event_id'] < stop['event_id'], 'Reversed episode boundaries')
    selected = [event for event in events if start['event_id'] <= event['event_id'] <= stop['event_id']]
    monitor = monitor_type()
    for event in selected:
        wall, sim = event['wall_elapsed_s'], event['sim_time_s']
        require(finite(wall) and finite(sim), 'Non-finite protected timing sample')
        monitor.observe(wall - start['wall_elapsed_s'], sim - start['sim_time_s'])
    derived = monitor.report()
    host = base.read_json(host_path)
    original = host.get('timing', {})
    lag = original.get('maximum_wall_minus_sim_s')
    per_tick_pass = finite(lag) and 0 <= lag < .1 and type(original.get('samples')) is int and original['samples'] > 0
    return {'schema': 'rci-campaign-journal-timing-1',
            'journal': {'path': str(Path(history_path).resolve()), 'sha256': base.hash_file(history_path)},
            'host_result': {'path': str(Path(host_path).resolve()), 'sha256': base.hash_file(host_path)},
            'timing_monitor': {'path': str(Path(source).resolve()), 'file_sha256': base.hash_file(source),
                               'class_source_sha256': class_sha},
            'sample_count': len(selected), 'sample_types': dict(Counter(event['type'] for event in selected)),
            'episode_started_event_id': start['event_id'], 'episode_stopped_event_id': stop['event_id'],
            'original_host_timing': original, 'original_per_tick_lag_pass': per_tick_pass,
            'derived_journal_timing': derived,
            'passed': derived['actual_host_timing_pass'] is True and per_tick_pass,
            'scope': 'Exact frozen TimingMonitor applied offline to protected journal samples. Episode-start origin precedes host loop clock initialization and terminal follows cancellation. Interpolated one-second windows are reconstructed, not retained per-tick windows. Maximum sample gap is reported without claiming unobserved sub-window precision; original per-tick maximum lag is tested separately.'}


def verify_schedule(schedule, attempts):
    require(schedule.get('source_revision') == base.REVISION and schedule.get('attempt_count') == 24
            and schedule.get('replacements_allowed') == 0, 'Wrong fixed campaign schedule')
    slots = schedule['slots']
    require(len(slots) == len(attempts) == 24, 'Exactly 24 immutable attempts required')
    seen_paths = {name: set() for name in ('workspace', 'evidence', 'host_evidence', 'storage_receipt')}
    for index, (slot, planned) in enumerate(zip(slots, attempts), 1):
        pair = (index - 1) // 2
        family = ('misplaced-stock', 'blocked-insert-home')[(index - 1) % 2 ^ (pair % 2)]
        replicate = pair + 1
        run_id = 'RCI001-C01-' + ('stock' if family == 'misplaced-stock' else 'home') + f'-{replicate:02d}'
        require(slot['ordinal'] == planned['ordinal'] == index and slot['run_id'] == planned['run_id'] == run_id
                and slot['family'] == family and slot['within_family_replicate'] == replicate
                and slot['world_seed'] == 173 and slot['noise_seed'] == 22000 + index
                and slot['maximum_model_invocations'] == 1, 'Fixed order/identity/seed violation')
        manifest_path = artifact(planned['manifest'])
        require(planned['manifest']['sha256'] == slot['sha256'] and manifest_path.name == slot['manifest'],
                'Attempt manifest differs from predeclared slot')
        manifest = base.read_json(manifest_path)
        require(manifest.get('run_id') == run_id and manifest.get('family') == family
                and manifest.get('seed') == 173 and manifest.get('noise_seed') == 22000 + index
                and manifest.get('model') == 'gpt-6-astra' and manifest.get('effort') == 'max'
                and manifest.get('bootstrap') == 'Follow the instructions in RobotAgentPrompt.md.'
                and manifest.get('model_turns_max') == 1 and manifest.get('interruption_trigger') is None
                and manifest.get('prior_attempt') is None, 'Wrong experiment manifest')
        require(same_path(planned['workspace'], slot['runtime_workspace'])
                and same_path(planned['workspace'], manifest['runtime_workspace']), 'Workspace differs from fixed schedule')
        for name in seen_paths:
            path = Path(planned[name])
            require(path.is_absolute(), 'Absolute attempt path required')
            value = str(path.resolve()).casefold()
            require(value not in seen_paths[name], 'Attempt paths must be unique')
            seen_paths[name].add(value)


def verify_certificate(certificate_path, certificate_sha256):
    require(base.hash_file(certificate_path) == certificate_sha256, 'Certificate does not match external seal')
    cert = base.read_json(certificate_path)
    require(cert.get('schema') == 'rci-campaign-scientific-admission-1'
            and cert.get('campaign_id') == CAMPAIGN_ID and cert.get('framework_revision') == base.REVISION
            and cert.get('release_revision') == 'RCI001-C01-frozen-001' and cert.get('source_count') == 624,
            'Wrong admission identity')
    stamp(cert['created_at'])
    require(cert.get('timing') == TIMING, 'Timing policy must retain strict frozen limits')
    require(cert.get('conditions') == {'maximum_attempts': 24, 'no_replacements': True,
                                     'no_injected_restart': True, 'no_tuning': True}, 'Wrong campaign conditions')
    storage = cert['storage']
    require(storage.get('free_reserve_bytes') == 100_000_000_000
            and storage.get('planning_peak_bytes') == 37_962_254_720
            and storage.get('planning_allowance_is_hard_limit') is False, 'Wrong authorized storage policy')
    require(all(name in cert['artifacts'] for name in REQUIRED_ARTIFACTS), 'Missing required admission artifact')
    paths = {name: artifact(record) for name, record in cert['artifacts'].items()}
    policy = base.read_json(paths['storage_policy'])
    require(policy.get('schema') == 'campaign001-storage-guard-1'
            and policy.get('reserve_bytes') == 100_000_000_000
            and policy.get('planning_allowance_bytes') == 37_962_254_720
            and policy.get('safe_stop') is True and 1 <= policy.get('interval_s', 0) <= 10
            and 0 < policy.get('max_sample_gap_s', 0) <= 30
            and bool(policy.get('native_roots')) and bool(policy.get('wsl_roots')), 'Invalid sealed storage policy')
    tests = base.read_json(paths['storage_tests'])
    require(tests.get('schema') == 'campaign001-storage-qualification-1' and tests.get('tests_passed') is True
            and type(tests.get('tests_run')) is int and tests['tests_run'] > 0
            and tests.get('source_sha256') == cert['artifacts']['storage_monitor']['sha256']
            and tests.get('policy_sha256') == cert['artifacts']['storage_policy']['sha256'],
            'External storage implementation lacks matching passed qualification')
    preflight = base.read_json(paths['preflight_capacity'])
    require(preflight.get('schema') == 'campaign001-storage-guard-1' and preflight.get('preflight_passed') is True
            and preflight.get('monitor_source_sha256') == cert['artifacts']['storage_monitor']['sha256']
            and preflight.get('config_sha256') == cert['artifacts']['storage_policy']['sha256'],
            'External storage preflight does not bind source and policy')
    for scope in ('native', 'wsl'):
        require(min(preflight['sample'][scope]['free_bytes'].values()) >= policy['reserve_bytes'] + policy['retirement_headroom_bytes'],
                'Preflight disk reserve unavailable')
    require(stamp(preflight['created_utc']) <= stamp(cert['created_at']), 'Preflight postdates admission')
    assets = base.read_json(paths['asset_refresh'])
    require(assets.get('schema') == 'rci-campaign-asset-refresh-1' and assets.get('qualified') is True
            and len(assets.get('assets', [])) == 80 and len(assets.get('packages', [])) == 10,
            'Required asset refresh not qualified')
    for row in assets['assets']:
        artifact(row)
    for row in assets['packages']:
        require(importlib.metadata.version(row['name']) == row['expected_version'] == row['actual_version'],
                'Declared runtime package version changed: ' + row['name'])
    require(cert['artifacts']['snapshot']['sha256'] == SNAPSHOT_SHA256
            and cert['artifacts']['archive']['sha256'] == ARCHIVE_SHA256, 'Not exact qualified 010d release')
    require(same_path(paths['assessor'], HERE / 'assess.py') and same_path(paths['admitted_assessor'], __file__)
            and same_path(paths['timing_source'], REPO / 'Long-Horizon Adaptive Robotics Expirement/Runtime 004/experiment.py'),
            'Certificate binds wrong assessor or timing source')
    frozen = base.read_json(paths['snapshot'])
    require(len(frozen['sources']) == 624 and not base.frozen_problems(paths['snapshot'], frozen),
            'Frozen source/archive integrity failed')
    timing_name = paths['timing_source'].relative_to(REPO).as_posix()
    require(frozen['sources'][timing_name]['sha256'] == cert['artifacts']['timing_source']['sha256'],
            'Timing implementation not frozen 010d source')
    schedule = base.read_json(paths['schedule'])
    require(schedule['plan_sha256'] == cert['artifacts']['original_plan']['sha256']
            and schedule['source_snapshot_sha256'] == SNAPSHOT_SHA256, 'Original plan/snapshot binding mismatch')
    verify_schedule(schedule, cert['attempts'])
    base.queue_gate(base.read_json(paths['retained_timing_queue']))
    retained = base.read_json(paths['retained_timing'])
    pilots = [row for row in retained['attempts'] if row['attempt'] == 'pilot-001']
    require(len(pilots) == 1, 'Exact prior 010d pilot qualification required')
    pilot = pilots[0]
    history, host = artifact(pilot['journal']), artifact(pilot['host_result'])
    reconstructed = reconstruct_timing(history, host, paths['timing_source'])
    require(reconstructed['passed'] is True and reconstructed['derived_journal_timing'] == pilot['derived_journal_timing']
            and reconstructed['original_host_timing'] == pilot['original_host_timing']
            and reconstructed['sample_count'] == pilot['sample_count'], 'Retained pilot timing cannot be reproduced')
    require(reconstructed['derived_journal_timing']['complete_wall_windows'] == 237
            and reconstructed['derived_journal_timing']['outside_rtf_tolerance_windows'] == 0,
            'Wrong exact prior timing evidence')
    return cert


def verify_registration(registration_path, cert, certificate_sha256):
    registration = base.read_json(registration_path)
    require(registration.get('schema') == 'rci-campaign-registration-1'
            and registration.get('certificate_sha256') == certificate_sha256
            and registration.get('release_revision') == cert['release_revision']
            and registration.get('source_snapshot_sha256') == SNAPSHOT_SHA256, 'Registration binding mismatch')
    for key, expected in (('release_snapshot', SNAPSHOT_SHA256), ('release_archive', ARCHIVE_SHA256)):
        artifact(registration[key])
        require(registration[key]['sha256'] == expected, 'Registration changed frozen implementation')
    release = base.read_json(artifact(registration['release_record']))
    map_root = Path(registration['map_root'])
    require(same_path(map_root, REPO / 'Long-Horizon Adaptive Robotics Expirement/Architecture Map'), 'Wrong canonical map root')
    canonical_revisions = base.jsonl(map_root / 'revisions.jsonl')
    canonical_runs = base.jsonl(map_root / 'runs.jsonl')
    require([row for row in canonical_revisions if row.get('id') == cert['release_revision']] == [release],
            'Frozen revision not uniquely registered in canonical map')
    require(release['id'] == cert['release_revision'] and release['details']['certificate_sha256'] == certificate_sha256,
            'Registered release does not bind admission')
    require(stamp(release['recorded_at']) >= stamp(cert['created_at']), 'Release predates admission')
    require(len(registration['attempts']) == 24, 'Incomplete immutable attempt registration')
    for expected, registered in zip(cert['attempts'], registration['attempts']):
        require(registered['run_id'] == expected['run_id']
                and registered['manifest_sha256'] == expected['manifest']['sha256'], 'Registered attempt differs')
        record = base.read_json(artifact(registered['run_record']))
        require([row for row in canonical_runs if row.get('id') == expected['run_id']] == [record],
                'Attempt not uniquely registered in canonical map')
        require(record['id'] == expected['run_id'] and record['revision_id'] == cert['release_revision']
                and record['condition_details']['runtime_manifest_sha256'] == expected['manifest']['sha256']
                and record['details']['certificate_sha256'] == certificate_sha256
                and record['condition_details']['manifest'] == base.read_json(expected['manifest']['path']),
                'Immutable map run record does not bind campaign attempt')
    return registration


def verify_storage(receipt_path, cert, attempt, queue_path, job):
    receipt = base.read_json(receipt_path)
    require(receipt.get('schema') == 'campaign001-storage-guard-1', 'Wrong external storage receipt schema')
    require(receipt.get('run_id') == attempt['run_id'] and receipt.get('job_id') == job['id'], 'Storage receipt identity differs')
    require(receipt.get('monitor_source_sha256') == cert['artifacts']['storage_monitor']['sha256']
            and receipt.get('config_sha256') == cert['artifacts']['storage_policy']['sha256'], 'Storage monitor/policy differs from seal')
    artifact(receipt['baseline'])
    require(receipt['baseline']['sha256'] == cert['artifacts']['preflight_capacity']['sha256'], 'Storage baseline differs from seal')
    for key in ('manifest', 'evidence', 'host_evidence', 'workspace'):
        expected = attempt['manifest']['path'] if key == 'manifest' else attempt[key]
        require(same_path(receipt['paths'][key], expected), 'Storage monitored wrong ' + key)
    queue_bound = artifact(receipt['official_queue_receipt'])
    require(same_path(queue_bound, queue_path) and receipt['official_queue_receipt']['sha256'] == base.hash_file(queue_path),
            'Storage official queue receipt differs')
    samples_path = artifact(receipt['samples'])
    samples = base.jsonl(samples_path)
    require(type(receipt.get('sample_count')) is int and len(samples) == receipt['sample_count'] and len(samples) >= 2,
            'Storage samples missing or count differs')
    require(receipt.get('state') == 'completed' and receipt.get('official_queue_state') == 'succeeded'
            and type(receipt.get('official_queue_exit_status')) is int and receipt['official_queue_exit_status'] == 0,
            'Storage guard did not observe official successful completion')
    require(samples[0]['started_utc'] == receipt['first_sample_utc']
            and samples[-1]['finished_utc'] == receipt['last_sample_utc'], 'Storage sample coverage summary differs')
    for sample in samples:
        require(stamp(sample['started_utc']) <= stamp(sample['finished_utc']), 'Reversed storage sample timestamps')
    require(all(stamp(a['finished_utc']) <= stamp(b['started_utc']) for a, b in zip(samples, samples[1:])),
            'Overlapping or reversed storage samples')
    require(receipt.get('coverage_complete') is True
            and stamp(receipt['first_sample_utc']) <= stamp(job['started_at'])
            and stamp(receipt['last_sample_utc']) >= stamp(job['ended_at']), 'Storage coverage does not enclose queue execution')
    require(receipt.get('admission_stop_latched') is False and receipt.get('reserve_bytes') == 100_000_000_000,
            'Storage guard stop/reserve violation')
    free = receipt['minimum_free_bytes']
    require(set(free) >= {'native', 'wsl'} and all(type(free[name]) is int and free[name] >= receipt['reserve_bytes']
                                                for name in ('native', 'wsl')), 'Observed disk reserve violated')
    for scope in ('native', 'wsl'):
        require(free[scope] == min(min(sample[scope]['free_bytes'].values()) for sample in samples),
                'Storage receipt free-space summary differs from retained samples')
    require(receipt['peak_aggregate_additional_bytes'] == max(sample['aggregate_additional_bytes'] for sample in samples),
            'Storage receipt peak summary differs from retained samples')
    policy = base.read_json(cert['artifacts']['storage_policy']['path'])
    require(all(free[scope] >= receipt['reserve_bytes'] + policy['retirement_headroom_bytes'] for scope in ('native', 'wsl')),
            'Storage samples crossed protected retirement headroom')
    require(finite(receipt.get('max_sample_gap_s')) and receipt['max_sample_gap_s'] >= 0,
            'Storage sample spacing is not retained')
    require(receipt['max_sample_gap_s'] <= policy['max_sample_gap_s']
            and all(stamp(b['started_utc']) - stamp(a['started_utc']) <= policy['max_sample_gap_s']
                    for a, b in zip(samples, samples[1:])), 'Storage sample gap exceeds frozen policy')
    require(receipt['accounting_scope'] == policy['accounting_scope'], 'Storage scope differs from policy')
    return receipt


def admitted_assess(certificate_path, certificate_sha256, registration_path, run_id, queue_receipt, job_id):
    # No attempt output is opened before official completion and pre-outcome bindings.
    job = base.queue_gate(base.read_json(queue_receipt), job_id)
    cert = verify_certificate(certificate_path, certificate_sha256)
    registration = verify_registration(registration_path, cert, certificate_sha256)
    matches = [row for row in cert['attempts'] if row['run_id'] == run_id]
    require(len(matches) == 1, 'Attempt not in sealed fixed schedule')
    attempt = matches[0]
    require(stamp(cert['created_at']) < stamp(job['started_at']), 'Admission must precede attempt start')
    release = base.read_json(registration['release_record']['path'])
    require(stamp(release['recorded_at']) < stamp(job['started_at']), 'Frozen release must precede attempt start')
    require(all(stamp(base.read_json(row['run_record']['path'])['recorded_at']) < stamp(job['started_at'])
                for row in registration['attempts']), 'All immutable attempts must be registered before execution')
    require(base.queue_paths_match(job, Path(attempt['manifest']['path']), Path(attempt['evidence']),
                                  Path(attempt['host_evidence']), Path(attempt['workspace'])),
            'Official queue direct command/paths differ from admitted attempt')
    result = base.assess(Path(attempt['manifest']['path']), Path(attempt['evidence']), Path(attempt['host_evidence']),
                         Path(queue_receipt), Path(cert['artifacts']['snapshot']['path']), attempt['manifest']['sha256'],
                         job_id, None, Path(attempt['workspace']))
    checks = {'pre_outcome_campaign_seal_and_frozen_registration': True}
    errors = {}
    storage = timing = None
    try:
        storage = verify_storage(attempt['storage_receipt'], cert, attempt, queue_receipt, job)
        checks['external_aggregate_storage_coverage_and_reserve'] = True
    except (ValueError, KeyError, TypeError, OSError) as exc:
        checks['external_aggregate_storage_coverage_and_reserve'] = False
        errors['storage'] = str(exc)
    try:
        timing = reconstruct_timing(Path(attempt['host_evidence']) / 'public-history.jsonl',
                                    Path(attempt['host_evidence']) / 'result.json', cert['artifacts']['timing_source']['path'])
        checks['current_episode_frozen_one_second_rtf_and_strict_per_tick_lag'] = timing['passed'] is True
    except (ValueError, KeyError, TypeError, OSError) as exc:
        checks['current_episode_frozen_one_second_rtf_and_strict_per_tick_lag'] = False
        errors['timing'] = str(exc)
    result['schema'] = 'robot-codex-campaign-admitted-assessment-1'
    result['episode_evidence_assessment_validity'] = result['validity']
    result['checks'].update(checks)
    result['failed_checks'] = [name for name, passed in result['checks'].items() if passed is not True]
    valid = not result['failed_checks']
    result['validity'] = 'valid' if valid else 'invalid'
    result['task_outcome'] = result['observed_task_outcome'] if valid else 'unknown'
    result['scorable'] = valid and result['task_outcome'] in ('success', 'failure')
    result['scientific_admission'] = {'qualified': True, 'admissible': valid,
        'certificate_sha256': certificate_sha256, 'registered_release_revision': cert['release_revision'],
        'registration_sha256': base.hash_file(registration_path), 'checks': checks, 'errors': errors,
        'scope': 'Prospective repeated known fixed fixtures, exactly 24 slots; no held-out geometry or framework superiority.'}
    result['campaign_timing'] = timing
    result['external_storage'] = storage
    result['bindings'].update(admitted_assessor_sha256=base.hash_file(__file__),
                              certificate_sha256=certificate_sha256,
                              registration_sha256=base.hash_file(registration_path),
                              storage_receipt_sha256=base.hash_file(attempt['storage_receipt'])
                              if Path(attempt['storage_receipt']).is_file() else None)
    result['limitations'].append('Storage is externally sampled; retained sample spacing does not establish exact between-sample peak usage.')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('certificate', 'registration', 'queue-receipt', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('certificate-sha256', 'run-id', 'job-id'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args(argv)
    result = admitted_assess(args.certificate, args.certificate_sha256, args.registration,
                             args.run_id, args.queue_receipt, args.job_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({key: result[key] for key in ('run_id', 'validity', 'task_outcome', 'scorable', 'failed_checks')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
