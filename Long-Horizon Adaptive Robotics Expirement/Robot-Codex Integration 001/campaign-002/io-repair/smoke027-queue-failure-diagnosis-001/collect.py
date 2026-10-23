"""One-shot bounded failed-queue metadata diagnosis; no scientific assessment."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
C = OUT.parent.parent
R = C.parent
REPO = R.parents[1]
RUN = 'RCI001-C02-smoke-027'
JOB = '20260929T182650537335Z-49496959'
RAW = R / 'local-evidence/campaign002/qualification' / RUN / 'orchestrator'
QUEUE = Path('C:/Users/cresp/Documents/Dandelion Engineering/tools/compute_queue/compute_queue.py')
NAMES = ('stage-result.json', 'client/result.json', 'client/native-quiescence.json',
    'client/native-shutdown-order.json', 'client/native-pre-exit-drain.json',
    'codehost-pre-exit-drain.json', 'codehost-owner-bridge-v3.json',
    'codehost-native-owner-v3.json', 'cleanup.json', 'authority-revocation.json',
    'executor-1-retirement.json', 'executor-2-retirement.json', 'codehost-owner-retirement-v3.json',
    'codehost-transport-v3.jsonl', 'client/events.jsonl')
KEYS = {'schema', 'run_id', 'family', 'mode', 'completed', 'passed', 'qualified', 'success',
    'model_started', 'error', 'error_type', 'error_code', 'reason', 'phase', 'triggered',
    'interrupted', 'exit_code', 'returncode', 'native_exit_code', 'windows_exit_code',
    'forced_termination', 'forced_owned_job', 'cleanup_clean', 'retired', 'native_quiescence',
    'codehost_transport', 'native_transport_cleanup', 'stdin_close', 'native_close',
    'started_at', 'ended_at', 'requested_at', 'completed_at', 'started_monotonic_s',
    'completed_monotonic_s', 'deadline_monotonic_s', 'observations', 'events', 'stages',
    'requested_perf_counter_ns', 'completed_perf_counter_ns', 'observed_perf_counter_ns',
    'stdin_close_started_perf_counter_ns', 'stdin_close_completed_perf_counter_ns',
    'sequence', 'kind', 'wall_unix_s', 'monotonic_s', 'channel_id', 'operation', 'errno', 'winerror',
    'exception_class', 'failure', 'socket_failure', 'finishing', 'finished', 'finished_message',
    'all_channels_eof', 'all_channels_drained', 'all_channels_closed', 'all_handlers_completed',
    'channels', 'meters', 'parent_eof', 'upload_drained', 'namespace_closed', 'h2',
    'client_read', 'upload', 'download', 'client_written', 'upload_eof', 'download_eof',
    'active_stream_ids', 'open_streams', 'closed_streams', 'reset_streams', 'first_rejection',
    'headers_complete', 'frames_complete', 'upload_complete', 'seal_qualified', 'seal_error_code',
    'after_finish_drain', 'after_finished', 'result', 'failed', 'retired_all', 'observed_monotonic_s'}
EVENTS = {'failure', 'socket_failure', 'channel_parent_eof', 'parent_eof', 'channel_upload_drained',
    'channel_closed', 'namespace_finished', 'finished', 'native_quiescence',
    'client_finishing_before_close', 'shutdown', 'client_shutdown', 'namespace_quiescing',
    'channel_upload_eof', 'channel_namespace_closed', 'transport_pre_exit_drain', 'channel_socket_error'}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')


def save(name, value):
    with (OUT / name).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False); stream.write('\n')


def project(value, depth=0):
    if depth > 7: return '[depth limit]'
    if isinstance(value, dict):
        return {k: project(v, depth + 1) for k, v in value.items() if k in KEYS}
    if isinstance(value, list): return [project(v, depth + 1) for v in value[:128]]
    if isinstance(value, str): return value[:1000]
    return value


def main():
    argv = [sys.executable, '-X', 'utf8', '-B', str(QUEUE), 'status', JOB]
    result = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8')
    save('authentication.json', {'argv': argv, 'exit_code': result.returncode,
         'stdout': result.stdout, 'stderr': result.stderr, 'at': datetime.datetime.now(datetime.timezone.utc).isoformat()})
    assert result.returncode == 0
    job = json.loads(result.stdout)
    assert job['id'] == JOB and job['state'] == 'failed' and type(job['exit_status']) is int and job['exit_status'] == 1
    save('official-status.json', job)
    inputs, missing, projected, total = [], [], {}, 0
    paths = [RAW / 'sequence-result.json'] + [RAW / stage / name for stage in ('interrupt', 'resume') for name in NAMES]
    for path in paths:
        name = str(path.relative_to(RAW))
        if not path.is_file():
            missing.append(name); continue
        assert not path.is_symlink() and path.stat().st_size <= 8 * 1024 * 1024
        raw = path.read_bytes(); total += len(raw)
        assert total <= 48 * 1024 * 1024
        inputs.append({'path': str(path), 'sha256': digest(raw), 'bytes': len(raw)})
        if path.suffix == '.jsonl':
            rows = [json.loads(line) for line in raw.decode('utf-8').splitlines()]
            if path.name == 'codehost-transport-v3.jsonl':
                previous = None
                for number, row in enumerate(rows, 1):
                    assert row['sequence'] == number
                    if previous is not None: assert row['previous_sha256'] == previous
                    body = dict(row); previous = body.pop('record_sha256')
                    assert digest(canonical(body)) == previous
            selected = [project(row) for row in rows if row.get('kind') in EVENTS or 'fail' in row.get('kind', '')]
            projected[name] = {'row_count': len(rows), 'kind_counts': {kind: sum(r.get('kind') == kind for r in rows) for kind in sorted({r.get('kind', '') for r in rows})}, 'lifecycle': selected[-128:]}
        else:
            value = json.loads(raw)
            projected[name] = {'top_level_fields': list(value) if isinstance(value, dict) else [], 'metadata': project(value)}
    for item in inputs:
        assert digest(Path(item['path']).read_bytes()) == item['sha256']
    value = {'schema': 'campaign002-smoke027-bounded-diagnosis-1', 'run_id': RUN, 'queue_job_id': JOB,
        'assessment_state': 'not_assessed', 'task_outcome': 'unknown', 'scorable': False,
        'scope': 'Declared failed-job infrastructure metadata only; no replay, task assessment or qualification verdict.',
        'total_input_bytes': total, 'inputs': inputs, 'missing_optional': missing, 'metadata': projected}
    save('analysis.json', value)
    print(json.dumps({'files': len(inputs), 'bytes': total, 'missing': missing, 'metadata': projected}, indent=2))


if __name__ == '__main__':
    main()
