"""Finite post-terminal infrastructure projection; never assess robot performance."""
import ctypes as C
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
IO = HERE.parent
sys.path.insert(0, str(IO / 'single-interrupt-diagnostic-v5'))
import common
sys.path.insert(0, str(common.PACKET))
import collect_window
import trace_control as tc
sys.path.insert(0, str(common.QUALIFIED))
import read_etl

JOB = '20260930T165659123517Z-cab77873'
NATIVE_NAMES = (
    'sequence-result.json', 'interrupt/stage-result.json',
    'interrupt/client/native-shutdown-order.json',
    'interrupt/client/native-quiescence.json',
    'interrupt/client/native-pre-exit-drain.json',
    'interrupt/codehost-pre-exit-drain.json',
    'interrupt/codehost-owner-bridge-v3.json',
    'interrupt/codehost-native-owner-v3.json',
    'interrupt/codehost-transport-v3.jsonl',
    'interrupt/cleanup.json', 'interrupt/authority-revocation.json',
    'interrupt/executor-1-retirement.json', 'interrupt/executor-2-retirement.json',
    'interrupt/codehost-owner-retirement-v3.json',
)


def save(path, value):
    common.save(path, value)


def binding(path):
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': common.sha(path)}


def authenticate():
    command = [sys.executable, '-X', 'utf8', '-B', str(common.QUEUE), 'status', JOB]
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0
    job = json.loads(result.stdout)
    assert job['id'] == JOB and type(job['exit_status']) is int
    assert (job['state'], job['exit_status']) in {('succeeded', 0), ('failed', 1)}
    assert job['ended_at'] is not None
    prepared = common.read(common.ROOT / 'observer-preparation.json')
    assert job['argv'] == common.runner_argv(common.MANIFEST, common.SNAPSHOT, prepared['config_sha256'])
    elevation = common.read(common.ROOT / 'observer-elevation-receipt.json')
    assert elevation['complete'] is True and elevation['launchReturned'] is True
    assert type(elevation['helperExitCode']) is int and elevation['helperExitCode'] in (0, 1)
    common.validate(common.MANIFEST, common.SNAPSHOT)
    value = tc.config(expected_sha=prepared['config_sha256'])
    tc.verify_sources(value, collect_window.source_paths())
    messages = {phase: tc.receive(tc.CONTROL, phase, value) for phase in sorted(tc.PHASES)}
    save(HERE / 'authentication.json', {
        'authenticated_at': datetime.now(timezone.utc).isoformat(),
        'command': command, 'queue_command_exit': result.returncode,
        'official_job': job, 'elevation': elevation,
        'manifest': binding(common.MANIFEST), 'snapshot': binding(common.SNAPSHOT),
        'config_sha256': prepared['config_sha256'], 'authenticated_control_messages': messages,
        'reader': binding(Path(__file__)), 'declaration': binding(HERE / 'DECLARATION.md'),
    })
    return job, elevation, messages


def native_projection():
    # Reuse the finite field filter from the prior prospectively bounded reader.
    path = IO / 'smoke027-queue-failure-diagnosis-001/collect.py'
    spec = importlib.util.spec_from_file_location('prior_finite_projection', path)
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    prior.KEYS.update({'trace_arming', 'trace_control_completion', 'trace_error',
        'orchestrator_completed', 'resume_attempted', 'host_exit_code',
        'before_perf_counter_ns', 'after_perf_counter_ns', 'injected_interruption',
        'old_token_denied_after_retirement', 'all_namespaces_retired',
        'durable_retention_verified', 'watchdog_errors', 'failures', 'cleanup_active',
        'client_finishing', 'abort_set', 'value', 'name', 'succeeded', 'result_received',
        'thread_id', 'start_monotonic_s', 'graceful_deadline_monotonic_s',
        'hard_deadline_monotonic_s', 'handshake_qualified', 'finishing_recorded',
        'stdin_closed', 'forced_job_close', 'scope', 'type', 'message', 'host_completed',
        'finish_frontier', 'seal_frontier', 'last_counter', 'final_counter'})
    inputs = [binding(path)]
    missing = []
    projected = {}
    endpoints = []
    ledger = []
    total = 0
    for name in NATIVE_NAMES:
        path = common.EVIDENCE / name
        if not path.is_file():
            missing.append(name)
            continue
        assert not path.is_symlink() and path.stat().st_size <= 8 * 1024 * 1024
        raw = path.read_bytes()
        total += len(raw)
        assert total <= 48 * 1024 * 1024
        inputs.append(binding(path))
        if path.suffix == '.jsonl':
            rows = [json.loads(line) for line in raw.decode('utf-8').splitlines()]
            previous = None
            for number, row in enumerate(rows, 1):
                assert row['sequence'] == number
                if previous is not None:
                    assert row['previous_sha256'] == previous
                body = dict(row)
                previous = body.pop('record_sha256')
                assert prior.digest(prior.canonical(body)) == previous
                if row['kind'] == 'channel_authenticated':
                    auth = row['authentication']
                    assert auth['client'][0] == auth['server'][0] == '127.0.0.1'
                    endpoints.append({'channel_id': row['channel_id'],
                        **{k: auth[k] for k in ('client', 'server', 'owner_pid',
                            'process_creation_filetime', 'monotonic_s')}})
                if row['kind'] in prior.EVENTS or 'fail' in row['kind']:
                    ledger.append(prior.project(row))
            projected[name] = {'row_count': len(rows), 'chain_verified': True,
                'lifecycle': ledger[-128:]}
        else:
            obj = json.loads(raw)
            projected[name] = prior.project(obj)
    return {'inputs': inputs, 'missing_optional': missing, 'total_bytes': total,
        'accepted_endpoints': endpoints, 'metadata': projected}


def select_native_events(events, endpoints):
    projection = []
    for event in events:
        fields = event['fields']
        pair = sorted([(fields['LocalAddress']['ip'], fields['LocalAddress']['port']),
                       (fields['RemoteAddress']['ip'], fields['RemoteAddress']['port'])])
        matches = [e for e in endpoints if sorted([tuple(e['client']), tuple(e['server'])]) == pair
            and event['perf_counter_ns'] >= int(e['monotonic_s'] * 1e9)]
        if matches:
            projection.append({**event, 'matched_channels': [e['channel_id'] for e in matches]})
    return projection


def assess_trace(elevation, endpoints):
    root = tc.CONTROL
    receipt = common.read(root / 'receipt.json')
    etl = root / 'closure.etl'
    if not etl.is_file():
        return {'collection_checks_passed': False, 'receipt': receipt,
            'missing_etl': True, 'native_events': [], 'complete_kernel_history': False}
    decoded = read_etl.read(etl)
    save(root / 'decoded-assessment-001.json', decoded)
    before = common.read(root / 'clock-before.json')
    after = common.read(root / 'clock-after.json')
    api = common.read(root / 'etw-api.json')
    stops = [r for r in api if r['operation'] == 'owned_stop']
    counts = decoded['descriptor_counts']
    header = decoded['trace_header']
    events = decoded['allowed_events']
    metadata = {'68fdd900-4a3e-11d1-84f4-0000f80464e3/0/2/0',
                '68fdd900-4a3e-11d1-84f4-0000f80464e3/0/2/80'}
    schema = json.loads((common.QUALIFIED / 'schema.json').read_text(encoding='utf-8-sig'))
    allowed = {f"{read_etl.PROVIDER}/{e['id']}/{e['version']}/0" for e in schema['events']}
    unexpected = {k: v for k, v in counts.items() if k not in metadata | allowed}
    freq = C.c_longlong()
    assert C.windll.kernel32.QueryPerformanceFrequency(C.byref(freq))
    drift = abs((after['utc_ns'] - before['utc_ns']) -
        ((after['perf_before_ns'] + after['perf_after_ns'] -
          before['perf_before_ns'] - before['perf_after_ns']) // 2))
    checks = {
        'helper_exit_zero': elevation['helperExitCode'] == 0,
        'collection_completed': receipt['collection_completed'] is True,
        'owned_cleanup': receipt['trace_stopped'] is True and not receipt['cleanup_errors'],
        'duration_and_size': isinstance(receipt['trace_elapsed_s'], (float, int)) and
            0 < receipt['trace_elapsed_s'] <= 30 and 0 < etl.stat().st_size <= 16 * 1024 * 1024,
        'own_stop_and_absence': len(stops) == 1 and stops[0]['status'] == 0 and
            api[-1]['operation'] == 'post_stop_query' and api[-1]['status'] == 4201,
        'no_loss': len(stops) == 1 and all(stops[0]['properties'][k] == 0 for k in
            ('EventsLost', 'LogBuffersLost', 'RealTimeBuffersLost')) and
            header['EventsLost'] == header['BuffersLost'] == 0,
        'sequential_and_bounded': header['LogFileMode'] == 1 and header['MaximumFileSize'] == 16 and
            len(stops) == 1 and stops[0]['properties']['LogFileMode'] == 0x400001,
        'no_decode_errors_or_extensions': not decoded['decode_errors'] and not decoded['extended_data_counts'],
        'only_six_types_and_headers': not unexpected and sum(counts.get(k, 0) for k in metadata) <= 3 and
            counts.get('68fdd900-4a3e-11d1-84f4-0000f80464e3/0/2/0') == 1,
        'qpc_clock_correlated': header['ReservedFlags'] == 1 and header['PerfFreq'] == freq.value and
            drift <= 10_000_000 and all(before['perf_before_ns'] <= e.get('perf_counter_ns', -1) <=
                after['perf_after_ns'] for e in events),
        'real_etw': receipt['simulated_etw'] is False,
    }
    projection = select_native_events(events, endpoints)
    native_files = ['receipt.json', 'intent.json', 'clock-before.json', 'clock-after.json',
        'etw-api.json', 'closure.etl', 'decoded-assessment-001.json', 'worker-identity.json']
    return {'collection_checks_passed': all(checks.values()), 'checks': checks, 'receipt': receipt,
        'trace_header': header, 'descriptor_counts': counts, 'unexpected_descriptor_counts': unexpected,
        'utc_qpc_drift_ns': drift, 'allowed_event_count': len(events), 'native_event_count': len(projection),
        'other_event_count': len(events) - len(projection), 'native_events': projection,
        'complete_kernel_history': False, 'native_qualified': False,
        'inputs': [binding(root / n) for n in native_files if (root / n).is_file()]}


def main():
    job, elevation, messages = authenticate()
    native = native_projection()
    trace = assess_trace(elevation, native['accepted_endpoints'])
    result = {'schema': 'native-closure-diagnostic005-assessment-1', 'run_id': common.RUN,
        'job_id': JOB, 'queue_state': job['state'], 'queue_exit': job['exit_status'],
        'task_outcome': 'unknown', 'assessment_state': 'infrastructure_only',
        'scorable': False, 'qualification_claim': False, 'native': native, 'trace': trace}
    save(HERE / 'analysis.json', result)
    print(json.dumps({'queue_state': job['state'], 'helper_exit': elevation['helperExitCode'],
        'collection_checks': trace.get('checks'), 'endpoints': native['accepted_endpoints'],
        'native_event_count': trace.get('native_event_count'), 'other_event_count': trace.get('other_event_count'),
        'native_metadata': native['metadata']}, indent=2))


if __name__ == '__main__':
    main()
