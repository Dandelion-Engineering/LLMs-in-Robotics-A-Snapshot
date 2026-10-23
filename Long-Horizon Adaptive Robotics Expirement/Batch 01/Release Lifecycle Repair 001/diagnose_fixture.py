"""Queue-only metadata diagnostic for the two failed synthetic timeout tests."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent.parent / 'Runtime 004'
sys.path.insert(0, str(RUNTIME))
import release_runner


def main():
    job = release_runner.queued_job(Path(__file__))
    from test_model_lifecycle import SupervisorTimeoutTests
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in RUNTIME.glob('*.py')}
    rows = []
    for ordering in ('watchdog_first', 'future_first'):
        result, events, future = SupervisorTimeoutTests().run_fixture(ordering)
        fields = ('failure_class', 'termination_reason', 'validity', 'infrastructure_invalid',
                  'cleanup_errors', 'actual_host_timing_pass', 'timing', 'timing_failed',
                  'error', 'model_calls', 'model_responses', 'model_failed_calls', 'unknown_token_calls')
        rows.append({'ordering': ordering, 'result': {key: result.get(key) for key in fields},
                     'timing_fields': {key: value for key, value in result.items() if 'timing' in key or 'lag' in key},
                     'future_result_calls': future.result_calls,
                     'errors': [e for e in events if e['event_type'] in ('terminal_error', 'cleanup_error', 'timing_failure')]})
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in RUNTIME.glob('*.py')}
    assert before == after
    output = HERE / 'fixture-diagnostic-001.json'
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump({'queue_job_id': job['id'], 'runtime_sources': before, 'sources_unchanged': True, 'cases': rows}, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'output': str(output), 'cases': rows}))


if __name__ == '__main__':
    main()
