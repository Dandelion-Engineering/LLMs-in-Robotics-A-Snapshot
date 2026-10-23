"""Complete ordering projection of the same authenticated finite input set."""
import json
from pathlib import Path
import subprocess
import sys
import collect_assess as a


def main():
    earlier = a.common.read(a.HERE / 'analysis.json')
    job = json.loads(subprocess.check_output([sys.executable, '-X', 'utf8', '-B',
        str(a.common.QUEUE), 'status', a.JOB], text=True, encoding='utf-8'))
    assert job['state'] == 'failed' and type(job['exit_status']) is int and job['exit_status'] == 1
    assert job == a.common.read(a.HERE / 'authentication.json')['official_job']
    index = {Path(v['path']).name: v for v in earlier['native']['inputs']}
    used = []
    def read(name):
        item = index[name]
        path = Path(item['path'])
        assert a.binding(path) == item
        used.append(item)
        return a.common.read(path)
    order = read('native-shutdown-order.json')
    quiet = read('native-quiescence.json')
    bridge = read('codehost-owner-bridge-v3.json')
    stage = read('stage-result.json')
    phases = {r['phase']: r['observed_perf_counter_ns'] for r in order['lifecycle']}
    faults = [r for r in earlier['native']['metadata']['interrupt/codehost-transport-v3.jsonl']['lifecycle']
              if r['kind'] == 'socket_failure']
    first = min(earlier['trace']['native_events'], key=lambda r: r['perf_counter_ns'])
    timeline = [{'kind': 'native_' + r['phase'], 'perf_counter_ns': r['observed_perf_counter_ns']}
                for r in order['lifecycle']]
    for e in earlier['trace']['native_events']:
        timeline.append({'kind': 'tcpip_' + str(e['id']), 'perf_counter_ns': e['perf_counter_ns'],
            'status_hex': hex(e['fields']['Status']), 'payload_pid': e['fields']['ProcessId'],
            'local_port': e['fields']['LocalAddress']['port'], 'remote_port': e['fields']['RemoteAddress']['port']})
    timeline.extend({'kind': 'socket_failure', 'perf_counter_ns': e['observed_perf_counter_ns'],
        'channel_id': e['channel_id'], 'exception_class': e['exception_class'], 'winerror': e['winerror']} for e in faults)
    timeline.sort(key=lambda r: r['perf_counter_ns'])
    for row in timeline:
        row['ms_after_thread_closed'] = (row['perf_counter_ns'] - phases['thread_closed']) / 1e6
    h2_keys = ('error', 'preface_complete', 'settings_complete', 'frames_complete', 'headers_complete',
               'upload_complete', 'open_streams', 'active_stream_ids', 'closed_streams', 'reset_streams', 'goaway')
    value = {'run_id': a.common.RUN, 'job_id': a.JOB, 'ended_at': job['ended_at'],
        'task_outcome': 'unknown', 'qualification_claim': False, 'inputs': used,
        'prior_projection': a.binding(a.HERE / 'analysis.json'), 'reader': a.binding(Path(__file__)),
        'native_order': order, 'timeline': timeline,
        'native_cleanup': {k: quiet.get(k) for k in ('start_monotonic_s', 'graceful_deadline_monotonic_s',
            'hard_deadline_monotonic_s', 'handshake_qualified', 'finishing_recorded', 'stdin_closed',
            'forced_job_close', 'native_exit_code', 'qualified', 'failures')},
        'stage': {k: stage.get(k) for k in ('injected_interruption', 'old_token_denied_after_retirement',
            'cleanup_clean', 'durable_retention_verified', 'watchdog_errors')},
        'bridge_failures': bridge['failures'],
        'channels': [{'channel_id': c['channel_id'], 'meters': c['meters'],
            'h2': {k: c['h2'].get(k) for k in h2_keys},
            'parent_eof': c['parent_eof'], 'upload_drained': c['upload_drained'],
            'namespace_closed': {k: (c.get('namespace_closed') or {}).get(k) for k in
                ('reason', 'error_type', 'upload_eof', 'download_eof', 'upload', 'download')}} for c in bridge['channels']],
        'first_matching_os_event_after_forced_job_ms': (first['perf_counter_ns'] - phases['job_forced']) / 1e6,
        'first_matching_os_event_after_stdin_close_ms': (first['perf_counter_ns'] - order['stdin_close'][0]['end_perf_counter_ns']) / 1e6,
        'trace_arm_latency_ms': (earlier['native']['metadata']['sequence-result.json']['trace_arming'][0]['after_perf_counter_ns'] -
            earlier['native']['metadata']['sequence-result.json']['trace_arming'][0]['before_perf_counter_ns']) / 1e6,
    }
    a.save(a.HERE / 'ordered-analysis.json', value)
    print(json.dumps({k: value[k] for k in ('first_matching_os_event_after_forced_job_ms',
        'first_matching_os_event_after_stdin_close_ms', 'trace_arm_latency_ms', 'timeline')}, indent=2))


if __name__ == '__main__':
    main()
