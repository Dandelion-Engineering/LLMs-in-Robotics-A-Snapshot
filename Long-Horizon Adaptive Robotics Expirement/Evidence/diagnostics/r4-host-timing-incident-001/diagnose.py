"""Read-only, outcome-blind incident derivation; no episode or frozen-source edits."""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
EXP = ROOT / 'Long-Horizon Adaptive Robotics Expirement'
RELEASE = EXP / 'Evidence/releases/batch01-eval-r4'
OUT = Path(__file__).with_name('diagnostic.json')
RUN = 'batch01-eval-r4-C02-rep2-A2-persistent'
JOB = '20260924T114851750615Z-709753d9'
FINALIZER = '20260924T121712145071Z-70b65f7e'
RELEASE_SHA = 'ed65f8b33e16daaa081031cfe7ccc7ac65644af3522546aad0d2fa76a1d72fe1'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def ref(path):
    return {'path': str(path), 'sha256': digest(path), 'bytes': path.stat().st_size}


def receipt(job):
    path = EXP / 'Evidence/queue-receipts' / (job + '.json')
    value = load(path)
    assert value['id'] == job and value['state'] == 'succeeded'
    assert type(value['exit_status']) is int and value['exit_status'] == 0
    return ref(path)


def envelope(event):
    return {key: event[key] for key in ('event_id', 'event_type', 'source', 'wall_elapsed_s', 'sim_time_s')}


assert not OUT.exists()
assert digest(RELEASE / 'release.json') == RELEASE_SHA
release = load(RELEASE / 'release.json')
for key in ('freeze_manifest', 'readiness'):
    assert digest(release[key]['path']) == release[key]['sha256']
batch = RELEASE / 'batches' / JOB
planned, finished, finalized = [load(batch / name) for name in ('planned.json', 'finished.json', 'finalized.json')]
assert finalized['run_ids'] == finished['terminal_run_ids'] == planned['selected_run_ids'][:2]
assert finished['unlaunched_selected_run_ids'] == planned['selected_run_ids'][2:]
assert planned['schedule_order_preserved'] is True
assert load(batch / 'official-queue-status.json') == load(EXP / 'Evidence/queue-receipts' / (JOB + '.json'))
assert digest(batch / 'official-queue-status.json') == finalized['official_queue_receipt_sha256']

rows = [json.loads(line) for line in (EXP / 'Architecture Map/results.jsonl').read_text().splitlines() if line.strip()]
canonical = {row['run_id']: row for row in rows if row.get('run_id', '').startswith('batch01-eval-r4-')}
assert len(canonical) == 102
attempts = sorted(path for path in (RELEASE / 'attempts').iterdir() if path.is_dir())
assert {path.name for path in attempts} == set(canonical)
invalid = []
for path in attempts:
    terminal = load(path / 'terminal.json')
    details = canonical[path.name]['details']
    assert digest(path / 'terminal.json') == details['terminal_sha256']
    assert terminal['run_id'] == path.name and terminal['release_sha256'] == RELEASE_SHA
    assert terminal['integrity_breach'] is False and terminal['post_run_integrity']['passed'] is True
    assert terminal['queue_job_id'] == details['queue_job_id']
    assert details['official_queue_status'] == 'succeeded'
    assert type(details['official_queue_exit_status']) is int and details['official_queue_exit_status'] == 0
    if terminal['result']['validity'] != 'valid':
        invalid.append(path.name)
assert invalid == [RUN]

terminal_path = RELEASE / 'attempts' / RUN / 'terminal.json'
terminal_ref = ref(terminal_path)
terminal = load(terminal_path)
result = terminal['result']
assert result['validity'] == 'invalid' and result['infrastructure_invalid'] is True
assert result['actual_host_timing_pass'] is False
assert result['error'] is None and result['cleanup_errors'] == [] and result['resource_watchdog_events'] == []
assert digest(terminal['supervisor_result_ref']['path']) == terminal['supervisor_result_ref']['sha256']
evidence = terminal_path.parent / 'evidence'
resources_path = evidence / 'resources.jsonl'
resources = [json.loads(line) for line in resources_path.read_text().splitlines() if line.strip()]
resource_summary = {
    'samples': len(resources),
    'first_at': resources[0]['captured_at'], 'last_at': resources[-1]['captured_at'],
    'max_capture_duration_s': max(row['capture_duration_s'] for row in resources),
    'max_interval_s': max(b['capture_monotonic_s'] - a['capture_monotonic_s'] for a, b in zip(resources, resources[1:])),
    'harness_observed_rss_exceedances': sum(row['budget_observations']['harness_observed_rss_exceeds_budget'] for row in resources),
    'model_observed_commit_exceedances': sum(row['budget_observations']['model_observed_private_commit_exceeds_budget'] for row in resources),
    'max_harness_rss_bytes': max(row['harness']['rss_bytes'] for row in resources if row['harness']['rss_bytes'] is not None),
    'max_model_private_commit_bytes': max(row['model']['private_commit_bytes'] for row in resources if row['model']['private_commit_bytes'] is not None),
    'max_gpu_temperature_c': max(device['temperature_c'] for row in resources for device in row['gpu']['devices'] if device['temperature_c'] is not None),
    'limits': ['Approximately five-second samples cannot resolve subsecond scheduling or disk stalls.', 'GPU samples describe the entire device and cannot attribute activity to a process.', 'No retrospective all-process CPU, disk, or thermal-throttling trace was recorded.'],
}

# Inspect event envelopes only: no candidate replies, policy payloads, or scores.
events_path = evidence / 'events.jsonl'
events_hash = hashlib.sha256()
prior = None
started = False
gaps = []
event_count = 0
clock = None
with events_path.open('rb') as stream:
    for line in stream:
        events_hash.update(line)
        event = json.loads(line)
        event_count += 1
        if event['event_type'] == 'episode_clock_started':
            started = True
            clock = {key: event['payload'][key] for key in ('monotonic_s', 'resource_sampler_wall_offset_s', 'base_sim_time_s')}
            prior = envelope(event)
            continue
        if not started:
            continue
        current = envelope(event)
        if prior is not None and current['wall_elapsed_s'] <= result['wall_duration_s']:
            gap = current['wall_elapsed_s'] - prior['wall_elapsed_s']
            if gap >= 0.1:
                gaps.append({'gap_s': gap, 'before': prior, 'after': current})
        prior = current

# Paired identity is taken from the existing canonical run record, not seed fields.
run_rows = [json.loads(line) for line in (EXP / 'Architecture Map/runs.jsonl').read_text().splitlines() if line.strip()]
run_row = next(row for row in run_rows if row.get('id') == RUN)
pair = run_row.get('paired_block_id') or run_row.get('details', {}).get('paired_block_id')
assert pair, 'No canonical paired identity'
timing_keys = ('maximum_lag_s', 'maximum_timing_sample_gap_s', 'outside_rtf_tolerance_fraction', 'outside_rtf_tolerance_windows', 'complete_wall_windows', 'trailing_partial_window_s', 'timing_boundary_method', 'wall_duration_s')
summary = {
    'schema_version': 'r4-host-timing-incident-diagnostic-1', 'captured_at_utc': datetime.now(timezone.utc).isoformat(),
    'run_id': RUN, 'paired_block_id': pair, 'release_sha256': RELEASE_SHA,
    'scope': 'Timing/infrastructure and evidence identity only. No task-performance comparison or policy adaptation.',
    'source': ref(Path(__file__).resolve()), 'terminal': terminal_ref,
    'run_receipt': receipt(JOB), 'finalize_receipt': receipt(FINALIZER),
    'batch_records': {name: ref(batch / name) for name in ('planned.json', 'finished.json', 'finalized.json', 'official-queue-status.json')},
    'verified_canonical_attempts': len(canonical), 'valid_attempt_count': len(canonical) - len(invalid), 'invalid_run_ids': invalid,
    'post_run_integrity_passed_all_attempts': True, 'unlaunched_selected_run_ids': finished['unlaunched_selected_run_ids'],
    'timing': {key: result[key] for key in timing_keys}, 'bad_windows': [row for row in result['timing'] if not row['within_tolerance']],
    'fixed_thresholds': {'maximum_lag_s_strictly_less_than': 0.1, 'outside_rtf_fraction_strictly_less_than': 0.01, 'per_window_rtf_inclusive': [0.95, 1.05]},
    'original_validity': result['validity'], 'original_validity_reason': result['validity_reason'],
    'error': result['error'], 'cleanup_errors': result['cleanup_errors'], 'resource_watchdog_events': result['resource_watchdog_events'],
    'resource_ref': ref(resources_path), 'resource_summary': resource_summary,
    'event_ref': {'path': str(events_path), 'sha256': events_hash.hexdigest(), 'bytes': events_path.stat().st_size},
    'event_count': event_count, 'episode_clock': clock, 'event_envelope_gaps_at_least_100ms': gaps,
    'attribution': 'Unassigned. Event adjacency is temporal correlation, not proof of a blocking call or host/candidate causation.',
    'source_readiness_evaluator_oracle_breach_observed': False,
    'all_primary_inputs_unchanged': digest(terminal_path) == terminal_ref['sha256'] and digest(RELEASE / 'release.json') == RELEASE_SHA,
    'os_event_review': {'reviewer': 'Codex batch_design_audit helper', 'window_utc': ['2026-09-24T11:54:30Z', '2026-09-24T12:00:30Z'], 'channels': ['System', 'Application'], 'levels': ['Critical', 'Error', 'Warning'], 'matching_count': 0, 'query_result': 'NoMatchingEventsFound for both channels; no access-denied error', 'limits': 'Does not identify timing cause or exclude unlogged stalls; informational events and other channels not checked.'},
}
assert summary['all_primary_inputs_unchanged']
with OUT.open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(summary, stream, indent=2, allow_nan=False)
    stream.write('\n')
print(json.dumps({'output': str(OUT), 'sha256': digest(OUT), 'invalid_run_ids': invalid, 'event_gap_count': len(gaps), 'pair': pair}))
