"""Complete finite ordering/counter projection of the already declared inputs."""
import json
from pathlib import Path
import subprocess
import sys
import collect as c


def main():
    result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(c.QUEUE), 'status', c.JOB], capture_output=True, text=True, encoding='utf-8')
    c.save('order-authentication.json', {'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
    assert result.returncode == 0
    job = json.loads(result.stdout)
    assert job['id'] == c.JOB and job['state'] == 'failed' and type(job['exit_status']) is int and job['exit_status'] == 1
    prior = json.loads((c.OUT / 'analysis.json').read_bytes())
    index = {Path(v['path']).relative_to(c.RAW).as_posix(): v for v in prior['inputs']}
    def read(name):
        item = index[name]; raw = Path(item['path']).read_bytes()
        assert len(raw) == item['bytes'] and c.digest(raw) == item['sha256']
        return json.loads(raw)
    order = read('interrupt/client/native-shutdown-order.json')
    quiet = read('interrupt/client/native-quiescence.json')
    bridge = read('interrupt/codehost-owner-bridge-v3.json')
    stage = read('interrupt/stage-result.json')
    ledger = prior['metadata']['interrupt\\codehost-transport-v3.jsonl']
    socket_fault = next(x for x in ledger['lifecycle'] if x.get('kind') == 'socket_failure')
    value = {'schema': 'campaign002-smoke027-ordered-diagnosis-1', 'queue_job_id': c.JOB,
        'task_outcome': 'unknown', 'assessment_state': 'not_assessed', 'scorable': False,
        'source_bindings': [index[k] for k in ('interrupt/client/native-shutdown-order.json', 'interrupt/client/native-quiescence.json', 'interrupt/codehost-owner-bridge-v3.json', 'interrupt/stage-result.json')],
        'high_resolution_order': order, 'first_socket_fault': socket_fault,
        'native_cleanup': {k: quiet.get(k) for k in ('start_monotonic_s', 'graceful_deadline_monotonic_s', 'hard_deadline_monotonic_s', 'handshake_qualified', 'finishing_recorded', 'stdin_closed', 'forced_job_close', 'native_exit_code', 'failures')},
        'stage': {k: stage.get(k) for k in ('injected_interruption', 'old_token_denied_after_retirement', 'cleanup_clean', 'durable_retention_verified', 'watchdog_errors')},
        'bridge_failures': bridge['failures'],
        'channels': [{k: channel.get(k) for k in ('channel_id', 'meters', 'parent_eof', 'upload_drained', 'finish_frontier', 'seal_frontier', 'namespace_closed')} for channel in bridge['channels']]}
    c.save('ordered-analysis.json', value)
    print(json.dumps({k:v for k,v in value.items() if k not in ('source_bindings','channels')},indent=2))


if __name__ == '__main__':
    main()
