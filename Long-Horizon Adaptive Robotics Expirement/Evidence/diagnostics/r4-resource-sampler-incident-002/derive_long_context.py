"""Summarize one completed, fixed long-context infrastructure probe; no scoring."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json

BASE = Path(__file__).resolve().parent
EXP = BASE.parents[2]
RUN = BASE / 'stage-probe-long-context-001'
JOB = '20260924T200041535546Z-d5a173b5'

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def ref(path):
    path = Path(path)
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size)

receipt = EXP / 'Evidence' / 'queue-receipts' / (JOB + '.json')
official = load(receipt)
assert official['id'] == JOB and official['state'] == 'succeeded'
assert type(official['exit_status']) is int and official['exit_status'] == 0
report = load(RUN / 'report.json')
child = load(RUN / 'probe' / 'result.json')
assert report['queue_job_id'] == child['queue_job_id'] == JOB
assert report['sources_unchanged'] and child['sources_unchanged']
assert report['child_result']['sha256'] == ref(RUN / 'probe' / 'result.json')['sha256']
assert report['inputs_before'] == report['inputs_after']
for path, expected in report['inputs_before'].items():
    assert ref(path)['sha256'] == expected, path
metrics = defaultdict(list)
calls, traces = [], []
for path in sorted((RUN / 'probe' / 'stage-traces').glob('*.jsonl')):
    traces.append(ref(path))
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            event = json.loads(line)
            if 'duration_s' in event:
                metrics[event['event']].append(event['duration_s'])
            if event['event'] == 'generic_model_result':
                value = event['record']
                answer = value.get('response', {})
                calls.append(dict(index=value['index'], error=value['error'], prompt_tokens=answer.get('prompt_tokens'), completion_tokens=answer.get('completion_tokens'), latency_s=answer.get('latency_s'), timings=answer.get('timings')))
assert len(calls) == child['model_calls_recorded']
resource_refs, resource_count, gpu_missing, capture_durations = [], 0, [], []
for sampler in child['sampler_reports']:
    path = Path(sampler['path'])
    resource_refs.append(ref(path))
    count = 0
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            sample = json.loads(line)
            count += 1
            capture_durations.append(sample['capture_duration_s'])
            if sample['gpu']['missing_reason'] is not None:
                gpu_missing.append(dict(path=str(path), captured_at=sample['captured_at'], reason=sample['gpu']['missing_reason']))
    assert count == sampler['sample_count']
    resource_count += count
output = dict(
    schema_version='long-context-resource-stage-review-1',
    recorded_at_utc=datetime.now(timezone.utc).isoformat(), source=ref(__file__),
    report=ref(RUN / 'report.json'), child_result=ref(RUN / 'probe' / 'result.json'), official_receipt=ref(receipt),
    source_hashes_verified_current=True, phases=child['phases'], first_failure=child['first_failure'],
    unexpected_error=child['unexpected_error'], cleanup_errors=child['cleanup_errors'],
    all_phases_completed=child['all_phases_completed'], resource_sample_count=resource_count,
    max_capture_duration_s=max(capture_durations), gpu_missing=gpu_missing,
    stages={key:dict(count=len(values), min_s=min(values), max_s=max(values)) for key,values in sorted(metrics.items())},
    generic_calls=calls, trace_refs=traces, resource_refs=resource_refs,
    short_probe_and_incident_load_comparison=ref(BASE / 'stage-probe-and-load-review.json'),
    scored_continuation_authorized=False, nonrecurrence_established=False,
    limitations=[
        'One fixed synthetic long-context workload; no robot, sensing, policy prompt, held-out scenario or scored episode was run.',
        'Stage logging adds overhead. Timing and content differ from the original full workload.',
        'Passing collection and source checks does not assign the historical stall cause or establish scored readiness.',
        'No retries, source changes, threshold relaxation, token adjustment, episode exclusions or continuation review were performed by this derivation.',
        'All resource samples are repeated dependent measurements, not independent failure-rate trials.'
    ]
)
path = BASE / 'stage-probe-long-context-review.json'
with path.open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(output, stream, indent=2, allow_nan=False)
    stream.write('\n')
print(json.dumps(ref(path)))
