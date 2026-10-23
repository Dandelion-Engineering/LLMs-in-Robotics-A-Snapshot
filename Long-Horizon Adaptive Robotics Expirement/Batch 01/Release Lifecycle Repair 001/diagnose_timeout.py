"""Queued read-only extraction of the recorded model-timeout incident."""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent.parent
sys.path.insert(0, str(EXP / 'Runtime'))
import release_runner


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main(output):
    job = release_runner.queued_job(Path(__file__))
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Preserve earlier diagnostics; require a fresh output')
    run_id = 'batch01-eval-r3-C20-rep1-A2-persistent'
    attempt = EXP / 'Evidence/releases/batch01-eval-r3/attempts' / run_id
    events_path = attempt / 'evidence/events.jsonl'
    inputs = [attempt / 'terminal.json', attempt / 'evidence/result.json',
              attempt / 'evidence/resources.jsonl', attempt / 'model-server.log',
              EXP / 'Runtime/model_runtime.py', EXP / 'Runtime/experiment.py', Path(__file__)]
    before = {str(p): sha(p) for p in inputs}
    before_events = sha(events_path)
    terminal = json.loads(inputs[0].read_text(encoding='utf-8'))
    result = terminal['result']
    extracted = []
    counts = {}
    event_digest = hashlib.sha256()
    wanted = {'model_request', 'model_response', 'late_model_response', 'model_error',
              'stale_model_error_discarded', 'resource_watchdog_exceeded', 'terminal_error'}
    with events_path.open('rb') as stream:
        for line in stream:
            event_digest.update(line)
            event = json.loads(line)
            kind = event['event_type']
            counts[kind] = counts.get(kind, 0) + 1
            if kind not in wanted:
                continue
            payload = event['payload']
            row = {k: event[k] for k in ('event_id', 'event_type', 'source', 'sim_time_s', 'wall_elapsed_s', 'parent_ids', 'payload_sha256')}
            # Never copy prompt, policy, image, candidate-state or seed content.
            row['metadata'] = {k: payload[k] for k in ('error', 'classification', 'phase',
                'original_incarnation', 'current_incarnation', 'stale', 'after_episode_end',
                'post_episode_wall_s', 'wall_beyond_cap_s') if k in payload}
            if kind == 'resource_watchdog_exceeded':
                row['metadata']['breaches'] = payload['breaches']
            extracted.append(row)
    after = {str(p): sha(p) for p in inputs}
    events_unchanged = before_events == event_digest.hexdigest() == sha(events_path)
    if before != after or not events_unchanged:
        raise ValueError('Incident inputs changed during extraction')
    errors = [r for r in extracted if r['event_type'] in ('model_error', 'stale_model_error_discarded')]
    confirmed = any(r['metadata'].get('error') == 'Local inference timed out; owned server stopped' for r in errors)
    report = {'schema_version': 'model-timeout-incident-diagnostic-1',
              'recorded_at': datetime.now(timezone.utc).isoformat(), 'queue_job_id': job['id'],
              'run_id': run_id, 'inputs_before': before, 'inputs_after': after,
              'events': {'path': str(events_path), 'sha256': before_events, 'counts': counts},
              'inputs_unchanged': True, 'selected_events': extracted,
              'recorded_owned_inference_timeout_confirmed': confirmed,
              'result': {k: result.get(k) for k in ('execution_status', 'outcome', 'validity',
                 'failure_class', 'error', 'cleanup_errors', 'model_calls', 'model_responses',
                 'model_failures', 'unknown_token_calls', 'actual_host_timing_pass', 'wall_duration_s')},
              'post_run_integrity': terminal['post_run_integrity'],
              'scope': 'Read-only event extraction and exact recorded exception; no reclassification, rerun or continuation authorization'}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'output': str(output), 'sha256': sha(output),
                      'owned_inference_timeout_confirmed': confirmed, 'selected_events': len(extracted)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    main(parser.parse_args().output)
