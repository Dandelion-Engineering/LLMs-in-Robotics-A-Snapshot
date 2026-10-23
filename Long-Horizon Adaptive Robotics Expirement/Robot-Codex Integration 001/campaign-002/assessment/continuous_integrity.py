"""Independent completion and retained-evidence checks for the continuous owner.

Only the original frozen recorder Reader is imported. No worker, adapter,
simulator, queue, model or host execution is performed by this verifier.
"""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
import zipfile

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
RCI = CAMPAIGN.parent
REPO = RCI.parents[1]
RECORDER = RCI.parent / 'Storage Retention Implementation 001/future/recorder.py'
WORKER = CAMPAIGN / 'harness/physics_worker.py'
WORKER_NAME = WORKER.relative_to(REPO).as_posix()
ADAPTER_NAME = (CAMPAIGN / 'harness/continuous_adapter.py').relative_to(REPO).as_posix()
RUNNER_NAME = (CAMPAIGN / 'harness/run_host.py').relative_to(REPO).as_posix()
COUNTERS = ('ticks', 'published', 'drained', 'peak_messages', 'peak_message_bytes',
            'maximum_message_bytes', 'rpc_started', 'rpc_completed', 'rpc_abandoned')
KINDS = {'motion', 'capture', 'feedback', 'event'}


def require(value, message):
    if value is not True:
        raise ValueError(message)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def identity(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'Continuous source/evidence is not an ordinary file: ' + str(path))
    raw = path.read_bytes()
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def source_bindings(frozen):
    paths = (WORKER, CAMPAIGN / 'harness/continuous_adapter.py', CAMPAIGN / 'harness/run_host.py',
             Path(__file__).resolve(), RECORDER, RCI / 'host/supervisor.py')
    bound = {}
    for path in paths:
        name = path.relative_to(REPO).as_posix()
        expected = identity(path)
        require(frozen.get('sources', {}).get(name) == expected,
                'Continuous owner, recorder or verifier source differs from freeze: ' + name)
        bound[name] = expected
    return bound


def applies(frozen):
    sources = frozen.get('sources', {})
    if WORKER_NAME in sources or ADAPTER_NAME in sources:
        return True
    if RUNNER_NAME not in sources:
        return False
    expected = sources[RUNNER_NAME]
    live = REPO / RUNNER_NAME
    raw = live.read_bytes() if live.is_file() and not live.is_symlink() else b''
    if {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)} != expected:
        revision = frozen.get('revision')
        require(isinstance(revision, str) and re.fullmatch(r'[A-Za-z0-9_-]+', revision) is not None,
                'Frozen runner source unavailable and canonical archive identity is missing')
        archive = RCI.parent / 'Architecture Map/releases' / revision / 'code.zip'
        require(archive.is_file() and not archive.is_symlink(), 'Frozen runner source archive is absent or linked')
        with zipfile.ZipFile(archive) as store:
            raw = store.read(RUNNER_NAME)
        require({'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)} == expected,
                'Frozen runner archive source hash differs')
    # Gate activation uses authenticated frozen runner bytes, so omitting both
    # helpers cannot disguise a new runner as a historical revision.
    return b'from continuous_adapter import ContinuousAdapter' in raw


def load_recorder():
    # recorder.py imports only the standard library; it is already part of the
    # immutable original 624-source inventory. A distinct module name avoids a
    # cached production import or an unrelated recorder on sys.path.
    name = '_campaign002_continuous_evidence_reader'
    spec = importlib.util.spec_from_file_location(name, RECORDER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def recorder_counts(host):
    directory = Path(host) / 'native-recording'
    require(directory.is_dir() and not directory.is_symlink(), 'Final native recording directory is absent or linked')
    manifest_path = directory / 'container-manifest.json'
    manifest_identity = identity(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    require(manifest.get('database') == 'evidence.sqlite.gz', 'Continuous owner requires the unchanged finalized native recording')
    database_identity = identity(directory / manifest['database'])
    reader = load_recorder().Reader(directory)
    try:
        motion = sum(1 for _ in reader.motion())
        captures = sum(1 for _ in reader.images())
    finally:
        reader.close()
    return motion, captures, {'manifest': manifest_identity, 'database': database_identity}


def observations(host):
    path = Path(host) / 'public-history.jsonl'
    binding = identity(path)
    count, relevant = 0, []
    with path.open('r', encoding='utf-8') as stream:
        for line in stream:
            require(bool(line.strip()), 'Blank public-history row in continuous evidence')
            row = json.loads(line)
            require(isinstance(row, dict), 'Malformed public-history row in continuous evidence')
            if row.get('type') in ('observation', 'command_dispatched', 'command_admission'):
                relevant.append(row)
            if row.get('type') == 'observation':
                sequence = row.get('payload', {}).get('sequence')
                require(integer(sequence) and sequence == count,
                        'Continuous captured observation sequences are missing, repeated or reordered')
                count += 1
    return count, binding, relevant


def verify_dispatches(host, history):
    path = Path(host) / 'command-registry.json'
    binding = identity(path)
    registry = json.loads(path.read_text(encoding='utf-8'))
    require(isinstance(registry, dict), 'Continuous command registry must be an object')
    observations_by_sequence = {row['payload']['sequence']: row for row in history if row['type'] == 'observation'}
    admitted, dispatched = {}, {}
    for row in history:
        kind, payload = row['type'], row.get('payload', {})
        if kind == 'command_admission' and payload.get('feedback', {}).get('status') == 'accepted':
            rid = payload.get('request_id')
            require(isinstance(rid, str) and rid not in admitted, 'Duplicate or malformed accepted native admission')
            admitted[rid] = row
        elif kind == 'command_dispatched':
            rid = payload.get('request_id')
            require(isinstance(rid, str) and rid not in dispatched, 'Duplicate or malformed native dispatch intent')
            dispatched[rid] = row
    accepted = {rid: record for rid, record in registry.items()
                if isinstance(record, dict) and record.get('admission', {}).get('status') == 'accepted'}
    require(set(accepted) == set(admitted), 'Accepted native registry and protected admission history differ')
    for rid, record in accepted.items():
        envelope, feedback = record.get('envelope', {}), record['admission']
        fence = feedback.get('continuous_dispatch', {})
        require(record.get('kind') == 'command' and record.get('actor') in ('robot', 'conventional')
                and record.get('request_id') == envelope.get('request_id') == feedback.get('request_id') == rid,
                'Accepted continuous request identity or actor differs')
        fingerprint = hashlib.sha256(json.dumps({'kind': 'command', 'actor': record['actor'], 'body': envelope},
                    sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()
        require(record.get('fingerprint') == fence.get('fingerprint') == fingerprint
                and fence.get('request_id') == rid and fence.get('durable_intent_before_rpc') is True
                and fence.get('fence_passed') is True and fence.get('rejection_reasons') == [],
                'Accepted continuous dispatch lacks exact durable intent and native fence evidence')
        for original, native in (('authority_epoch', 'epoch'), ('order_version', 'order_version'),
                                 ('observation_sequence', 'observation_sequence')):
            require(integer(envelope.get(original)) and type(fence.get(native)) is int
                    and envelope[original] == fence[native], 'Accepted continuous dispatch changes ' + original)
        observation = observations_by_sequence.get(envelope['observation_sequence'])
        require(isinstance(observation, dict), 'Accepted continuous dispatch references an absent observation')
        capture, dispatch = fence.get('capture_sim_time_s'), fence.get('dispatch_sim_time_s')
        require(finite(capture) and finite(dispatch) and capture == observation['payload'].get('capture_sim_time_s')
                and 0 <= dispatch - capture <= .35,
                'Accepted continuous dispatch observation is stale or has a mismatched capture clock')
        intent, admission = dispatched.get(rid), admitted[rid]
        require(isinstance(intent, dict) and integer(intent.get('event_id'), 1)
                and integer(admission.get('event_id'), 1) and integer(observation.get('event_id'), 1)
                and observation['event_id'] < intent['event_id'] < admission['event_id'],
                'Accepted native admission lacks an earlier protected dispatch and observation')
        require(intent['payload'].get('fingerprint') == fingerprint and intent['payload'].get('envelope') == envelope
                and intent['payload'].get('phase') == 'dispatched'
                and intent.get('authority_epoch') == admission.get('authority_epoch') == fence['epoch']
                and admission['payload'].get('feedback') == feedback,
                'Accepted native admission differs from the protected intent or registry receipt')
    return {'passed': True, 'accepted_native_commands': len(accepted), 'registry': binding}


def verify_continuous_physics(host, metadata, host_result, frozen):
    # Historical snapshots predate this source and remain under their original
    # requirements. New snapshots cannot suppress the gate by dropping a receipt.
    if not applies(frozen):
        return {'schema': 'rci-independent-continuous-physics-1', 'status': 'not_applicable',
                'applicable': False, 'passed': True,
                'reason': 'Frozen source inventory predates the continuous physics worker.'}
    sources = source_bindings(frozen)
    receipt = host_result.get('continuous_physics')
    require(isinstance(receipt, dict) and receipt.get('schema') == 'rci-continuous-physics-1'
            and receipt.get('error') is None and receipt.get('owner_finished') is True,
            'Continuous owner completion receipt is missing, failed or unfinished')
    reason = metadata.get('terminal', {}).get('reason')
    require(isinstance(reason, str) and bool(reason)
            and receipt.get('terminal') == host_result.get('terminal') == reason,
            'Continuous owner terminal differs from host or retained timing terminal')
    for name, expected in (('queue_count', 4096), ('queue_bytes', 67108864), ('rpc_count', 32)):
        require(type(receipt.get(name)) is int and receipt[name] == expected,
                'Continuous owner queue/RPC bound differs: ' + name)
    heartbeat = receipt.get('heartbeat_timeout_s')
    require(type(heartbeat) in (int, float) and math.isfinite(heartbeat) and heartbeat == 2,
            'Continuous owner heartbeat lease differs from the two-second bound')
    metrics = receipt.get('metrics')
    require(isinstance(metrics, dict) and all(integer(metrics.get(name)) for name in COUNTERS)
            and metrics['ticks'] > 0 and metrics.get('terminal_frozen') is True
            and metrics.get('owner_closed') is True,
            'Continuous owner counters, timing finalization or close receipt are malformed')
    require(metrics['published'] == metrics['drained'], 'Continuous owner evidence was not completely drained')
    published, drained = metrics.get('published_by_kind'), metrics.get('drained_by_kind')
    for counts in (published, drained):
        require(isinstance(counts, dict) and set(counts) <= KINDS
                and all(integer(value) for value in counts.values()), 'Malformed continuous per-kind evidence counters')
    require(published == drained and sum(published.values()) == metrics['published']
            and sum(drained.values()) == metrics['drained'], 'Continuous per-kind evidence totals or drain differ')
    require(metrics['peak_messages'] <= min(receipt['queue_count'], metrics['published'])
            and metrics['maximum_message_bytes'] <= metrics['peak_message_bytes'] <= receipt['queue_bytes']
            and (metrics['published'] == 0 or metrics['peak_messages'] > 0 and metrics['maximum_message_bytes'] > 0),
            'Continuous evidence queue exceeded its bounded message or byte allowance')
    require(metrics['rpc_completed'] <= metrics['rpc_started'] and metrics['rpc_abandoned'] == 0,
            'Continuous RPC counters show an abandoned or impossible completion')
    minimum_samples = 2 * metrics['ticks'] + 2
    require(integer(metadata.get('sample_count'), minimum_samples),
            'Continuous owner timing ledger omits tick entry/exit or origin/terminal samples')
    motion, captures, recording = recorder_counts(host)
    observation_count, journal, history = observations(host)
    require(motion == published.get('motion', 0) == metrics['ticks'] // 5,
            'Final native motion rows differ from every-fifth-tick owner evidence')
    require(captures == published.get('capture', 0),
            'Final native image rows differ from captured owner evidence')
    require(observation_count == captures + 1,
            'Protected journal observations differ from captured owner evidence plus the initial observation')
    dispatches = verify_dispatches(host, history)
    return {'schema': 'rci-independent-continuous-physics-1', 'status': 'passed', 'applicable': True, 'passed': True,
            'source_bindings': sources, 'ticks': metrics['ticks'], 'published': metrics['published'],
            'drained': metrics['drained'], 'published_by_kind': published, 'drained_by_kind': drained,
            'minimum_timing_sample_count': minimum_samples, 'timing_sample_count': metadata['sample_count'],
            'motion_rows': motion, 'image_rows': captures, 'journal_observations': observation_count,
            'recording': recording, 'journal': journal, 'dispatch_integrity': dispatches, 'terminal': reason,
            'scope': 'Independent source, finalization, bounded queue and retained-record completeness checks. '
                     'Timing thresholds and memory/GC requirements remain independently mandatory.'}
