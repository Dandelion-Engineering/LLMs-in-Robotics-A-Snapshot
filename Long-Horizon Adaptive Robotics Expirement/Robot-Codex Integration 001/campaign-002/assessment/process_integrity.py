"""Independent additional process-drain proof after the full transport reader.

No runtime/producer import. Existing native, H2, byte, ownership, namespace and
retirement verification remains mandatory in candidate_transport.py.
"""
from pathlib import Path

from pre_exit_integrity import canonical, digest, finite, ns, read

PREFIX = 'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/'
METHOD = PREFIX+'io-repair/GRACEFUL_PROCESS_DRAIN_V1.md'
HELPER = PREFIX+'harness/process_drain.py'
CONTROLLER = PREFIX+'harness/native_process_quiescence.py'
ASSESSOR = PREFIX+'assessment/process_integrity.py'
EXCLUSIVE = (METHOD, HELPER, CONTROLLER, ASSESSOR)
SOURCE_NAMES = EXCLUSIVE+tuple(PREFIX+n for n in (
    'harness/bootstrap_client_v4.py', 'harness/runtime.py', 'harness/codehost_bridge_v3.py',
    'harness/native_quiescence.py', 'harness/native_exit_drain.py',
    'assessment/transport_integrity_v3.py', 'assessment/pre_exit_integrity.py'))

def require(value, message):
    if value is not True: raise ValueError('Process drain: '+message)

def enabled(frozen):
    present = [name in frozen.get('sources', {}) for name in EXCLUSIVE]
    require(all(present) or not any(present), 'incomplete process-drain source lineage')
    return all(present)

def verify(root, frozen, rows, channels, quiescence, *, repo):
    try: return _verify(root, frozen, rows, channels, quiescence, repo=repo)
    except (KeyError, IndexError, TypeError, AttributeError, UnicodeError) as error:
        raise ValueError('Process drain: malformed evidence') from error

def _verify(root, frozen, rows, channels, quiescence, *, repo):
    require(enabled(frozen), 'process-drain method absent')
    sources = {}
    for name in SOURCE_NAMES:
        path = Path(repo)/name
        require(path.is_file() and not path.is_symlink(), 'source unavailable')
        raw = path.read_bytes(); identity = {'sha256': digest(raw), 'bytes': len(raw)}
        require(frozen['sources'].get(name) == identity, 'source differs from freeze: '+name)
        sources[name] = identity
    require(quiescence.get('passed') is True, 'native proof absent')
    bindings = {}
    receipt = read(root, 'client/native-quiescence.json', 262144, bindings)
    order = read(root, 'client/native-shutdown-order.json', 65536, bindings)
    require(quiescence['input_bindings'].get('client/native-quiescence.json') ==
            bindings['client/native-quiescence.json'], 'native receipt changed')
    require(receipt.get('qualified') is True and receipt.get('forced_job_close') is False,
            'native completion not graceful')
    cleanup = quiescence['cleanup_barrier']
    start, deadline = quiescence['start_monotonic_s'], quiescence['graceful_deadline_monotonic_s']
    require(finite(start) and finite(deadline) and deadline == start+5, 'original graceful deadline')
    base = {'schema': 'campaign002-process-drain-request-1',
            'cleanup_request_sha256': digest(canonical(cleanup['request'])),
            'owner_receipt_sha256': cleanup['request']['owner_receipt_sha256'],
            'start_monotonic_s': start, 'graceful_deadline_monotonic_s': deadline}
    require(cleanup['request_sha256'] == base['cleanup_request_sha256'], 'cleanup identity')
    joined = {}
    for phase in ('prepare', 'finish'):
        native = read(root, 'client/native-process-'+phase+'.json', 16384, bindings)
        bridge = read(root, 'codehost-process-'+phase+'.json', 16384, bindings)
        expected = {**base, 'phase': phase, 'prepare_sha256':
                    digest(canonical(joined['prepare']['bridge'])) if phase == 'finish' else None}
        require(set(native) == {'schema', 'request', 'bridge', 'begin_perf_counter_ns', 'received_perf_counter_ns'}
                and native['schema'] == 'campaign002-process-drain-client-1'
                and native['request'] == expected and native['bridge'] == bridge, 'native join identity')
        require(set(bridge) == {'schema', 'request', 'qualified', 'channels', 'ledger_prefix', 'frontiers',
                'completed_monotonic_s', 'completed_perf_counter_ns'}
                and bridge['schema'] == 'campaign002-process-drain-bridge-1'
                and bridge['request'] == expected and bridge['qualified'] is True, 'bridge identity')
        require(type(bridge['channels']) is list and all(type(c) is int for c in bridge['channels'])
                and bridge['channels'] == list(channels), 'channel set differs')
        prefix = bridge['ledger_prefix']
        require(set(prefix) == {'sequence', 'sha256'} and type(prefix['sequence']) is int
                and 1 <= prefix['sequence'] <= len(rows)
                and rows[prefix['sequence']-1]['record_sha256'] == prefix['sha256'], 'ledger prefix differs')
        witnessed = rows[:prefix['sequence']]
        require(not any(r['kind'] in ('failure', 'socket_failure', 'channel_denied') for r in witnessed),
                'failed ledger prefix')
        required = ('owner_drain_begin', 'owner_drain_ack') if phase == 'prepare' else ('owner_finishing', 'namespace_finished')
        for kind in required:
            require(sum(r['kind'] == kind for r in witnessed) == 1, 'prefix lacks '+kind)
        if phase == 'prepare':
            frontiers = bridge['frontiers']
            require(type(frontiers) is list and [f['channel_id'] for f in frontiers] == list(channels),
                    'frontier identities')
            for frontier in frontiers:
                require(set(frontier) == {'channel_id', 'h2', 'meters'}, 'frontier shape')
                h2, meters, cid = frontier['h2'], frontier['meters'], frontier['channel_id']
                require(set(h2) == {'error', 'preface_complete', 'settings_complete', 'frames_complete',
                        'headers_complete', 'open_streams'} and h2['error'] is None
                        and type(h2['open_streams']) is int and h2['open_streams'] == 0
                        and all(h2[k] is True for k in ('preface_complete', 'settings_complete',
                        'frames_complete', 'headers_complete')), 'incomplete application frontier')
                require(set(meters) == {'client_read', 'upload', 'download', 'client_written'}
                        and meters['client_read'] == meters['upload']
                        and meters['download'] == meters['client_written'], 'unforwarded frontier bytes')
                for name, direction in (('upload', 'outgoing'), ('download', 'incoming')):
                    value = meters[name]
                    require(set(value) == {'bytes', 'sha256'} and type(value['bytes']) is int and value['bytes'] >= 0
                            and isinstance(value['sha256'], str) and len(value['sha256']) == 64
                            and all(c in '0123456789abcdef' for c in value['sha256']), 'meter shape')
                    count = sum(r['payload_bytes'] for r in witnessed if r['kind'] == 'frame'
                                and r['frame_type'] == 3 and r['channel_id'] == cid and r['direction'] == direction)
                    require(value['bytes'] == count, 'frontier bytes differ from protected frame ledger')
        else:
            require(bridge['frontiers'] == [], 'finish frontier shape')
            require(prefix['sequence'] >= joined['prepare']['bridge']['ledger_prefix']['sequence'], 'reversed prefix')
            for cid in channels:
                for kind in ('client_eof', 'upload_drained', 'channel_closed'):
                    require(sum(r['kind'] == kind and r.get('channel_id') == cid for r in witnessed) == 1,
                            'prefix lacks genuine channel '+kind)
        completed = bridge['completed_monotonic_s']
        require(finite(completed) and start <= completed < deadline
                and rows[prefix['sequence']-1]['monotonic_s'] <= completed, 'late or stale prefix')
        observed = [native['begin_perf_counter_ns'], bridge['completed_perf_counter_ns'], native['received_perf_counter_ns']]
        require(all(ns(v) for v in observed) and observed == sorted(observed), 'phase observation order')
        joined[phase] = native
    require(set(order) == {'schema', 'lifecycle', 'stdin_close'} and
            order['schema'] == 'campaign002-native-shutdown-order-1', 'ordering sidecar')
    events, lifecycle = receipt['events'], order['lifecycle']
    require(type(lifecycle) is list and len(lifecycle) == len(events) <= 24, 'lifecycle count')
    for observed, event in zip(lifecycle, events):
        require(set(observed) == {'sequence', 'phase', 'observed_perf_counter_ns'}
                and type(observed['sequence']) is int and observed['sequence'] == event['sequence']
                and observed['phase'] == event['phase'] and ns(observed['observed_perf_counter_ns']), 'lifecycle identity')
    require(all(a['observed_perf_counter_ns'] <= b['observed_perf_counter_ns']
                for a,b in zip(lifecycle, lifecycle[1:])), 'nonmonotonic observations')
    require(type(order['stdin_close']) is list and len(order['stdin_close']) == 1, 'stdin close cardinality')
    close = order['stdin_close'][0]
    require(set(close) == {'begin_perf_counter_ns', 'end_perf_counter_ns', 'returned_normally'}
            and close['returned_normally'] is True, 'stdin close shape')
    def observed(phase):
        values = [r['observed_perf_counter_ns'] for r in lifecycle if r['phase'] == phase]
        require(len(values) == 1, 'lifecycle phase count'); return values[0]
    p, f = joined['prepare'], joined['finish']
    ordered = [observed('finishing'), p['begin_perf_counter_ns'], p['bridge']['completed_perf_counter_ns'],
        p['received_perf_counter_ns'], close['begin_perf_counter_ns'], close['end_perf_counter_ns'],
        observed('stdin_closed'), f['begin_perf_counter_ns'], f['bridge']['completed_perf_counter_ns'],
        f['received_perf_counter_ns'], observed('native_exit')]
    require(all(ns(v) for v in ordered) and ordered == sorted(ordered), 'process drain phase order')
    for name, identity in bindings.items():
        raw = (Path(root)/name).read_bytes()
        require(identity == {'bytes': len(raw), 'sha256': digest(raw)}, 'input changed during verification')
    return {'schema': 'campaign002-native-process-drain-proof-1', 'passed': True,
        'channels': list(channels), 'prepare_prefix': p['bridge']['ledger_prefix'],
        'finish_prefix': f['bridge']['ledger_prefix'], 'source_bindings': sources, 'input_bindings': bindings,
        'scope': 'Additional two-phase ordering only; complete native and transport proofs remain required.'}
