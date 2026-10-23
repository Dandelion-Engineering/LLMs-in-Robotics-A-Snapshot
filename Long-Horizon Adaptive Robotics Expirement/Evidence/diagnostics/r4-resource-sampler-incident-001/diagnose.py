"""Outcome-blind, read-only derivation of the first R4 stale-sampler stop."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
EXP = ROOT / 'Long-Horizon Adaptive Robotics Expirement'
RELEASE = EXP / 'Evidence/releases/batch01-eval-r4'
OUT = Path(__file__).with_name('diagnostic.json')
RUN = 'batch01-eval-r4-C24-rep2-A3-no-persistence'
JOB = '20260924T172624113609Z-88f8fc4d'
FINALIZER = '20260924T174559666907Z-9caeae57'
RELEASE_SHA = 'ed65f8b33e16daaa081031cfe7ccc7ac65644af3522546aad0d2fa76a1d72fe1'
TERMINAL_SHA = 'a7aa9b9801d004374eb37af64b9cb1f8a38bbcfd6344c958a65c2405032d46c5'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def ref(path):
    path = Path(path)
    return {'path': str(path), 'sha256': digest(path), 'bytes': path.stat().st_size}


def receipt(job):
    p = EXP / 'Evidence/queue-receipts' / (job + '.json')
    r = load(p)
    assert r['id'] == job and r['state'] == 'succeeded'
    assert type(r['exit_status']) is int and r['exit_status'] == 0
    return ref(p)


assert not OUT.exists()
assert digest(RELEASE / 'release.json') == RELEASE_SHA
release = load(RELEASE / 'release.json')
for key in ('freeze_manifest', 'readiness'):
    assert digest(release[key]['path']) == release[key]['sha256']
batch = RELEASE / 'batches' / JOB
planned, finished, finalized = [load(batch / name) for name in ('planned.json', 'finished.json', 'finalized.json')]
assert finalized['run_ids'] == finished['terminal_run_ids'] == [RUN]
assert planned['selected_run_ids'] == [RUN] + finished['unlaunched_selected_run_ids']
assert len(finished['unlaunched_selected_run_ids']) == 3 and finished['stop_reason']
assert planned['schedule_order_preserved'] is True
assert load(batch / 'official-queue-status.json') == load(EXP / 'Evidence/queue-receipts' / (JOB + '.json'))
assert digest(batch / 'official-queue-status.json') == finalized['official_queue_receipt_sha256']

rows = [json.loads(line) for line in (EXP / 'Architecture Map/results.jsonl').read_text().splitlines() if line.strip()]
rows = [r for r in rows if r.get('run_id', '').startswith('batch01-eval-r4-')]
canonical = {r['run_id']: r for r in rows}
assert len(rows) == len(canonical) == 127
attempts = sorted(p for p in (RELEASE / 'attempts').iterdir() if p.is_dir())
assert {p.name for p in attempts} == set(canonical)
invalid, resource_stops = [], []
for p in attempts:
    t = load(p / 'terminal.json')
    d = canonical[p.name]['details']
    assert digest(p / 'terminal.json') == d['terminal_sha256']
    assert t['run_id'] == p.name and t['release_sha256'] == RELEASE_SHA
    assert t['integrity_breach'] is False and t['post_run_integrity']['passed'] is True
    assert t['queue_job_id'] == d['queue_job_id']
    assert canonical[p.name]['validity'] == t['result']['validity']
    assert canonical[p.name]['execution_status'] == t['result']['execution_status']
    assert d['official_queue_status'] == 'succeeded' and type(d['official_queue_exit_status']) is int and d['official_queue_exit_status'] == 0
    if t['result']['validity'] != 'valid':
        invalid.append(p.name)
    if t['result']['resource_watchdog_events']:
        resource_stops.append(p.name)
assert invalid == ['batch01-eval-r4-C02-rep2-A2-persistent', RUN]
assert resource_stops == [RUN]

terminal_path = RELEASE / 'attempts' / RUN / 'terminal.json'
assert digest(terminal_path) == TERMINAL_SHA
terminal = load(terminal_path)
result = terminal['result']
assert result['validity'] == 'invalid' and result['infrastructure_invalid'] is True
assert result['actual_host_timing_pass'] is True and result['cleanup_errors'] == []
assert digest(terminal['supervisor_result_ref']['path']) == terminal['supervisor_result_ref']['sha256']
watchdog = result['resource_watchdog_events']
assert len(watchdog) == 1 and len(watchdog[0]['breaches']) == 1
assert watchdog[0]['breaches'][0]['reason'] == 'latest completed resource sample is stale'
assert watchdog[0]['breaches'][0]['maximum_age_s'] == 7.0

evidence = terminal_path.parent / 'evidence'
resources_path = evidence / 'resources.jsonl'
resources = [json.loads(line) for line in resources_path.read_text().splitlines() if line.strip()]
assert len(resources) == result['resources']['sample_count']
assert digest(resources_path) == result['resources']['sha256']
compact_samples = []
for index, r in enumerate(resources):
    compact_samples.append({
        'index': index, 'captured_at': r['captured_at'], 'capture_monotonic_s': r['capture_monotonic_s'],
        'capture_duration_s': r['capture_duration_s'],
        'capture_start_interval_s': None if index == 0 else r['capture_monotonic_s'] - resources[index - 1]['capture_monotonic_s'],
        'capture_finish_lower_bound_monotonic_s': r['capture_monotonic_s'] + r['capture_duration_s'],
        'harness_missing_reason': r['harness']['missing_reason'], 'model_missing_reason': r['model']['missing_reason'],
        'gpu_missing_reason': r['gpu']['missing_reason'],
        'harness_rss_bytes': r['harness']['rss_bytes'], 'model_private_commit_bytes': r['model']['private_commit_bytes'],
        'budget_observations': r['budget_observations'],
        'gpu_devices': r['gpu']['devices'],
    })

events_path = evidence / 'events.jsonl'
h = hashlib.sha256()
clock = None
event_count = 0
prior = None
max_gap = None
near_stop = []
stop_monotonic = watchdog[0]['checked_monotonic_s']
for line in events_path.open('rb'):
    h.update(line)
    event = json.loads(line)
    event_count += 1
    envelope = {k: event[k] for k in ('event_id', 'event_type', 'source', 'wall_elapsed_s', 'sim_time_s')}
    if event['event_type'] == 'episode_clock_started':
        clock = {k: event['payload'][k] for k in ('monotonic_s', 'resource_sampler_wall_offset_s', 'base_sim_time_s')}
    if clock:
        absolute = clock['monotonic_s'] + event['wall_elapsed_s']
        if stop_monotonic - 8 <= absolute <= stop_monotonic + 5:
            near_stop.append(envelope)
        if prior and event['wall_elapsed_s'] <= result['wall_duration_s']:
            gap = event['wall_elapsed_s'] - prior['wall_elapsed_s']
            if max_gap is None or gap > max_gap['gap_s']:
                max_gap = {'gap_s': gap, 'before': prior, 'after': envelope}
        prior = envelope

run_rows = [json.loads(line) for line in (EXP / 'Architecture Map/runs.jsonl').read_text().splitlines() if line.strip()]
run_record = next(r for r in run_rows if r.get('id') == RUN)
pair = run_record.get('paired_block_id') or run_record.get('details', {}).get('paired_block_id')
assert pair == 'batch01-eval-r4-C24-rep2'
summary = {
    'schema_version': 'r4-resource-sampler-incident-diagnostic-1', 'captured_at_utc': datetime.now(timezone.utc).isoformat(),
    'scope': 'Resource observation freshness, timing and immutable identity only; no task-performance comparison or policy adaptation.',
    'run_id': RUN, 'paired_block_id': pair, 'release_sha256': RELEASE_SHA,
    'source': ref(Path(__file__).resolve()), 'terminal': ref(terminal_path),
    'run_receipt': receipt(JOB), 'finalize_receipt': receipt(FINALIZER),
    'batch_records': {n: ref(batch / n) for n in ('planned.json', 'finished.json', 'finalized.json', 'official-queue-status.json')},
    'verified_canonical_attempts': 127, 'valid_attempt_count': 125, 'invalid_run_ids': invalid,
    'resource_watchdog_stop_run_ids': resource_stops, 'post_run_integrity_passed_all_attempts': True,
    'unlaunched_selected_run_ids': finished['unlaunched_selected_run_ids'],
    'original_validity': result['validity'], 'original_validity_reason': result['validity_reason'], 'error': result['error'],
    'resource_policy': result['resource_policy'], 'resource_watchdog_events': watchdog,
    'cleanup_errors': result['cleanup_errors'], 'resource_summary': result['resources'], 'resource_ref': ref(resources_path),
    'resource_samples_compact': compact_samples,
    'event_ref': {'path': str(events_path), 'sha256': h.hexdigest(), 'bytes': events_path.stat().st_size},
    'event_count': event_count, 'episode_clock': clock, 'maximum_event_envelope_gap_during_episode': max_gap,
    'event_envelopes_near_stop': near_stop,
    'timing': {k: result[k] for k in ('actual_host_timing_pass', 'maximum_lag_s', 'maximum_timing_sample_gap_s', 'outside_rtf_tolerance_fraction')},
    'attribution': 'Immediate failure is stale latest completed observation. Underlying capture/publication delay source is unassigned.',
    'limits': ['Capture duration omits subsequent resource-stream write/flush and latest publication.',
               'Per-call process/GPU/flush timings and retrospective all-process scheduling/disk traces were not recorded.',
               'Resource peaks are sampled lower bounds; whole-device GPU measurements are not candidate attribution.',
               'Passing episode timing does not prove sampler responsiveness.'],
    'os_event_review': {'reviewer': 'Codex hdmi_power_evidence helper', 'window_utc': ['2026-09-24T17:27:30Z', '2026-09-24T17:29:15Z'],
                        'channels': ['System', 'Application'], 'levels': ['Critical', 'Error', 'Warning'], 'matching_count': 0,
                        'query_result': 'Both NoMatchingEventsFound; no access errors', 'limits': 'Informational events, other channels, other times and performance traces were not queried; absence does not exclude a stall.'},
    'all_primary_inputs_unchanged': digest(terminal_path) == TERMINAL_SHA and digest(resources_path) == result['resources']['sha256'] and digest(RELEASE / 'release.json') == RELEASE_SHA,
}
assert summary['all_primary_inputs_unchanged']
with OUT.open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(summary, stream, indent=2, allow_nan=False)
    stream.write('\n')
print(json.dumps({'output': str(OUT), 'sha256': digest(OUT), 'resource_samples': len(resources), 'invalid_run_ids': invalid, 'pair': pair}))
