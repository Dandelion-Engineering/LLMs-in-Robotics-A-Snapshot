"""Fresh terminal authentication, finite metadata, and conditional full proof."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'single-interrupt-diagnostic-v6'))
import common

JOB = '20260930T173803658874Z-55d739f8'
NAMES = ('sequence-result.json', 'process-drain-overlay.json', 'interrupt/stage-result.json',
    'interrupt/cleanup.json', 'interrupt/client/native-quiescence.json',
    'interrupt/client/native-shutdown-order.json', 'interrupt/codehost-owner-bridge-v3.json',
    'interrupt/codehost-transport-v3.jsonl', 'interrupt/codehost-process-prepare.json',
    'interrupt/codehost-process-finish.json', 'interrupt/client/native-process-prepare.json',
    'interrupt/client/native-process-finish.json')

def binding(path): return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': common.sha(path)}

def authenticate():
    argv = [sys.executable, '-X', 'utf8', '-B', str(common.QUEUE), 'status', JOB]
    result = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0
    job = json.loads(result.stdout)
    assert job['id'] == JOB and type(job['exit_status']) is int
    assert (job['state'], job['exit_status']) in {('succeeded', 0), ('failed', 1)}
    assert job['ended_at'] is not None
    assert job['argv'] == common.runner_argv(common.MANIFEST, common.SNAPSHOT)
    _, frozen = common.validate(common.MANIFEST, common.SNAPSHOT)
    common.save(HERE/'authentication.json', {'authenticated_at': datetime.now(timezone.utc).isoformat(),
        'official_job': job, 'argv': argv, 'status_command_exit': result.returncode,
        'manifest': binding(common.MANIFEST), 'snapshot': binding(common.SNAPSHOT),
        'reader': binding(Path(__file__)), 'declaration': binding(HERE/'DECLARATION.md')})
    common.save(HERE/'official-status.json', job)
    return job, frozen

def collect(job, frozen):
    filter_path = HERE.parent/'smoke027-queue-failure-diagnosis-001/collect.py'
    prior = common.load(filter_path, 'retained_finite_projector')
    prior.KEYS.update({'orchestrator_completed', 'resume_attempted', 'host_exit_code', 'failures',
        'injected_interruption', 'old_token_denied_after_retirement', 'all_namespaces_retired',
        'durable_retention_verified', 'watchdog_errors', 'start_monotonic_s', 'graceful_deadline_monotonic_s',
        'hard_deadline_monotonic_s', 'handshake_qualified', 'finishing_recorded', 'stdin_closed',
        'forced_job_close', 'lifecycle', 'begin_perf_counter_ns', 'end_perf_counter_ns', 'returned_normally',
        'request', 'bridge', 'frontiers', 'ledger_prefix', 'sha256', 'bytes', 'received_perf_counter_ns',
        'completed_perf_counter_ns', 'cleanup_request_sha256', 'owner_receipt_sha256', 'prepare_sha256',
        'preface_complete', 'settings_complete', 'native_exit_monotonic_s', 'finish_frontier',
        'seal_frontier', 'client_finishing', 'abort_set', 'cleanup_active', 'scope', 'overrides',
        'bootstrap_module', 'bridge_module', 'error', 'goaway', 'upload', 'download'})
    prior.EVENTS.update({'client_eof', 'upload_drained', 'owner_drain_begin', 'owner_drain_ack',
        'owner_finishing', 'channel_finish_frontier', 'channel_seal_frontier', 'retirement_started', 'closed'})
    bindings, missing, metadata, total = [binding(filter_path)], [], {}, 0
    for name in NAMES:
        path = common.EVIDENCE/name
        if not path.is_file(): missing.append(name); continue
        assert not path.is_symlink() and 0 < path.stat().st_size <= 8*1024*1024
        raw = path.read_bytes(); total += len(raw); assert total <= 48*1024*1024
        bindings.append(binding(path))
        if path.suffix == '.jsonl':
            rows = [json.loads(line, object_pairs_hook=common.pairs) for line in raw.decode('utf-8').splitlines()]
            previous = None
            for number, row in enumerate(rows, 1):
                assert type(row['sequence']) is int and row['sequence'] == number
                assert row['previous_sha256'] == previous
                body = dict(row); previous = body.pop('record_sha256')
                assert prior.digest(prior.canonical(body)) == previous
            selected = [prior.project(r) for r in rows if r['kind'] in prior.EVENTS or 'fail' in r['kind']]
            metadata[name] = {'row_count': len(rows), 'chain_verified': True,
                'kind_counts': {k: sum(r['kind'] == k for r in rows) for k in sorted({r['kind'] for r in rows})},
                'lifecycle': selected[-128:]}
        else:
            value = common.read(path)
            metadata[name] = prior.project(value)
            if name == 'process-drain-overlay.json':
                for source, identity in value['sources'].items():
                    fixed = common.CANDIDATE/source
                    assert identity == frozen['sources'][fixed.relative_to(common.REPO).as_posix()]
                metadata[name]['sources_match_freeze'] = True
    for item in bindings: assert binding(Path(item['path'])) == item
    result = {'schema': 'campaign002-graceful-process-diagnostic-assessment-1', 'run_id': common.RUN,
        'revision': common.REVISION, 'job_id': JOB, 'queue_state': job['state'], 'queue_exit': job['exit_status'],
        'scorable': False, 'qualification_claim': False, 'task_outcome': 'unknown',
        'bounded_metadata_bytes': total, 'input_bindings': bindings, 'missing_optional': missing, 'metadata': metadata,
        'full_transport_proof': {'attempted': False, 'reason': 'requires official succeeded integer0'}}
    if job['state'] == 'succeeded':
        for path in (common.CAMPAIGN/'harness', common.CAMPAIGN/'assessment', common.CANDIDATE):
            sys.path.insert(0, str(path))
        import candidate_transport
        try:
            proof = candidate_transport.verify_transport_integrity(common.EVIDENCE/'interrupt', frozen)
            common.save(HERE/'transport-proof.json', proof)
            result['full_transport_proof'] = {'attempted': True, 'passed': proof.get('passed') is True,
                'binding': binding(HERE/'transport-proof.json')}
        except Exception as error:
            result['full_transport_proof'] = {'attempted': True, 'passed': False,
                'error_type': type(error).__name__, 'error': str(error)[:1000]}
    common.save(HERE/'analysis.json', result)
    q = metadata.get('interrupt/client/native-quiescence.json', {})
    b = metadata.get('interrupt/codehost-owner-bridge-v3.json', {})
    print(json.dumps({'queue_state': job['state'], 'exit': job['exit_status'],
        'native': {k:q.get(k) for k in ('qualified', 'handshake_qualified', 'forced_job_close', 'native_exit_code', 'failures')},
        'bridge': {k:b.get(k) for k in ('qualified', 'failures')},
        'missing': missing, 'full_transport_proof': result['full_transport_proof']}, indent=2))

if __name__ == '__main__': collect(*authenticate())
