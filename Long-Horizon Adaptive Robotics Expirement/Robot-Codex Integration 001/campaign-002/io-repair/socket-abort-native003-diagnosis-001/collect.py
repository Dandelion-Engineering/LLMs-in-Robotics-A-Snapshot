"""Single-use, bounded failed-job metadata projection; no empirical assessor."""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

OUT = Path(__file__).resolve().parent
C = OUT.parent.parent
R = C.parent
REPO = R.parents[1]
RUN = 'RCI001-C02-shutdown-diagnostic-003'
JOB = '20260929T060538760771Z-877e2765'
RAW = R / 'local-evidence/campaign002/io-repair' / RUN / 'orchestrator'
STAGE = RAW / 'interrupt'
REL = R.parent / 'Architecture Map/releases/RCI001-C02-dev-091'
SNAPSHOT_SHA = '43af3b1952053fe24d6a8c3a49ea73407f1dc5aeaef7d24024dc35c51ff5f034'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(path):
    raw = path.read_bytes()
    return {'path': str(path.resolve()), 'bytes': len(raw), 'sha256': digest(raw)}


def save(name, value):
    with (OUT / name).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')


def scalars(value, names):
    return {k: value[k] for k in names if k in value and
            (value[k] is None or type(value[k]) in (bool, int, float))}


def main():
    assert not any((OUT / n).exists() for n in ('official-status.json', 'observations.json', 'execution.json'))
    spec = importlib.util.spec_from_file_location('native003_terminal_auth', C / 'qualification/run_final_qualification_v28.py')
    control = importlib.util.module_from_spec(spec); spec.loader.exec_module(control)
    job = control.official(JOB)
    assert job['id'] == JOB and job['state'] == 'failed'
    assert type(job['exit_status']) is int and job['exit_status'] == 1
    save('official-status.json', job)
    save('authentication.json', {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'scope': 'Failed terminal metadata diagnostic only; no task assessment.',
        'official': identity(OUT / 'official-status.json'), 'exit_code': 0})
    # No failed-run bytes are accessed before the live official gate above.
    before, missing, total = {}, [], 0
    def read(path, lines=False):
        nonlocal total
        if not path.exists():
            missing.append(str(path)); return [] if lines else {}
        assert path.is_file() and not path.is_symlink()
        limit = (16 if lines else 4) * 1024 * 1024
        assert path.stat().st_size <= limit
        raw = path.read_bytes(); total += len(raw)
        assert len(raw) <= limit and total <= 64 * 1024 * 1024
        before[str(path)] = {'path': str(path.resolve()), 'bytes': len(raw), 'sha256': digest(raw)}
        if lines:
            rows = raw.decode('utf-8').splitlines()
            assert len(rows) <= 20000 and all(len(x) <= 65536 for x in rows)
            return [json.loads(x) for x in rows]
        return json.loads(raw)
    sequence = read(RAW / 'sequence-result.json')
    stage = read(STAGE / 'stage-result.json')
    client = read(STAGE / 'client/result.json')
    quiet = read(STAGE / 'client/native-quiescence.json')
    bridge = read(STAGE / 'codehost-owner-bridge-v3.json')
    ledger = read(STAGE / 'codehost-transport-v3.jsonl', True)
    events = read(STAGE / 'client/events.jsonl', True)
    previous = None
    for i, row in enumerate(ledger, 1):
        assert row['sequence'] == i
        if previous is not None:
            assert row['previous_sha256'] == previous
        record = dict(row); recorded = record.pop('record_sha256')
        assert digest(json.dumps(record, sort_keys=True, separators=(',', ':')).encode()) == recorded
        previous = recorded
    snapshot = json.loads((REL / 'snapshot.json').read_text(encoding='utf-8'))
    assert identity(REL / 'snapshot.json')['sha256'] == SNAPSHOT_SHA
    sources = {}
    with zipfile.ZipFile(REL / 'code.zip') as archive:
        for name in ('harness/codehost_bridge_v3.py', 'harness/codehost_inside_v3.py',
                     'harness/codehost_mux_protocol.py', 'harness/native_quiescence.py',
                     'harness/bootstrap_client_v4.py', 'harness/physical.py', 'harness/runtime.py',
                     'io-repair/single-interrupt-diagnostic-v3/run.py'):
            path = C / name; key = path.relative_to(REPO).as_posix()
            bound = identity(path); archived = archive.read(key)
            assert snapshot['sources'][key] == {'bytes': bound['bytes'], 'sha256': bound['sha256']}
            assert len(archived) == bound['bytes'] and digest(archived) == bound['sha256']
            sources[name] = {**bound, 'archive_member': key, 'current_equals_frozen': True}
    failures = []
    for row in ledger:
        if row['kind'] != 'socket_failure':
            continue
        assert row['diagnostic_schema'] == 'campaign002-socket-failure-1'
        assert row['operation'] in ('upload_read', 'download_write')
        assert row['exception_class'] in ('OSError', 'ConnectionError', 'ConnectionAbortedError',
            'ConnectionRefusedError', 'ConnectionResetError', 'BrokenPipeError', 'TimeoutError',
            'BlockingIOError', 'InterruptedError', 'OtherOSError')
        assert all(row[k] is None or type(row[k]) is int and -(2**31) <= row[k] < 2**31 for k in ('errno', 'winerror'))
        value = scalars(row, ('sequence', 'wall_unix_s', 'monotonic_s', 'channel_id', 'errno', 'winerror',
            'cleanup_active', 'client_finishing', 'owner_draining', 'owner_sealed'))
        value.update({k: row[k] for k in ('diagnostic_schema', 'operation', 'exception_class')})
        value['byte_counters'] = scalars(row['byte_counters'], ('client_read', 'upload', 'download', 'client_written'))
        failures.append(value)
    assert len({x['channel_id'] for x in failures}) == len(failures)
    channels = []
    for ch in bridge.get('channels', []):
        remote, h2 = ch.get('namespace_closed') or {}, ch.get('h2') or {}
        channels.append({'channel_id': ch['channel_id'],
            'parent_eof_sequence': (ch.get('parent_eof') or {}).get('sequence'),
            'upload_drained_sequence': (ch.get('upload_drained') or {}).get('sequence'),
            'meters': {k: scalars(v, ('bytes',)) for k, v in ch.get('meters', {}).items()},
            'namespace': scalars(remote, ('qualified', 'upload_eof', 'upload_drained', 'download_eof')),
            'h2': {**scalars(h2, ('frames_complete', 'headers_complete', 'upload_complete')),
                   'error_present': h2.get('error') is not None,
                   'first_rejection_present': h2.get('first_rejection') is not None,
                   'active_stream_count': len(h2.get('active_stream_ids', []))}})
    retirements = []
    for name in ('executor-1-retirement.json', 'executor-2-retirement.json', 'codehost-owner-retirement-v3.json'):
        value = read(STAGE / name)
        last = (value.get('observations') or [{}])[-1]
        retirements.append({'file': name, 'present': bool(value),
            **scalars(value, ('qualified', 'windows_exit_code')),
            'last': {**scalars(last, ('retired', 'namespace_evidence_available', 'outer_same_process')),
                     'namespace_member_count': len(last['namespace_members']) if isinstance(last.get('namespace_members'), list) else None}})
    metadata_text = json.dumps([client, events]).lower()
    error_classes = {name: {'present': bool(value.get('error')),
        'usage_limit_phrase': 'usage limit' in str(value.get('error', '')).lower(),
        'rate_limit_phrase': 'rate limit' in str(value.get('error', '')).lower(),
        'interruption_gate_failure': value.get('error') == 'Interruption stage failed its gate; diagnostic ends without restart'}
        for name, value in (('sequence', sequence), ('stage', stage), ('client', client))}
    observations = {'schema': 'campaign002-native003-terminal-observations-1', 'run_id': RUN, 'queue_job_id': JOB,
        'diagnostic_only': True, 'task_outcome': 'unknown', 'qualification_assessed': False,
        'official_status': identity(OUT / 'official-status.json'), 'authentication': identity(OUT / 'authentication.json'),
        'orchestrator': {**scalars(sequence, ('orchestrator_completed', 'resume_attempted', 'host_exit_code', 'forced_host_exit')),
                         'stage_count': len(sequence.get('stages', []))},
        'stage': {**scalars(stage, ('injected_interruption', 'all_namespaces_retired', 'old_token_denied_after_retirement',
                    'cleanup_clean', 'durable_retention_verified')),
                  'command_trigger_record_present': bool(stage.get('command_at_interruption')),
                  'watchdog_error_count': len(stage.get('watchdog_errors', []))},
        'client': {**scalars(client, ('model_started', 'success')),
                   'turn_status': client.get('turn_status') if client.get('turn_status') in ('completed', 'failed', 'interrupted', 'inProgress') else None,
                   'source': before.get(str(STAGE / 'client/result.json'))},
        'error_classification': error_classes,
        'client_metadata_usage_limit_phrase': 'usage limit' in metadata_text,
        'client_metadata_rate_limit_phrase': 'rate limit' in metadata_text,
        'native_quiescence': scalars(quiet, ('qualified', 'handshake_qualified', 'forced_job_close', 'native_exit_code')),
        'transport': {**scalars(bridge, ('qualified', 'exit_code', 'attempts', 'accepted', 'denied', 'queued_bytes_at_close')),
            'ledger_rows_verified': len(ledger), 'first_failure_sequence': next((r['sequence'] for r in ledger if r['kind'] == 'failure'), None),
            'socket_failures': failures, 'channels': channels},
        'retirements': retirements, 'missing_optional_files': missing, 'source_bindings': sources,
        'input_bindings': list(before.values()), 'selected_input_bytes': total,
        'limits': 'Absence of trigger/fault is inconclusive. Observed starts are a lower bound, not billed generations. Historical retirement metadata is not a present OS census.'}
    assert all(identity(Path(path)) == value for path, value in before.items())
    save('observations.json', observations)
    save('execution.json', {'collector': identity(Path(__file__)), 'method': identity(OUT / 'METHOD.md'),
        'observations': identity(OUT / 'observations.json'), 'original_inputs_unchanged': True,
        'empirical_input_count': len(before), 'ledger_rows_verified': len(ledger), 'source_count': len(sources)})
    print(json.dumps({k: observations[k] for k in ('orchestrator', 'stage', 'client', 'error_classification',
        'client_metadata_usage_limit_phrase', 'client_metadata_rate_limit_phrase', 'native_quiescence', 'transport', 'retirements', 'missing_optional_files')}))


if __name__ == '__main__':
    main()
