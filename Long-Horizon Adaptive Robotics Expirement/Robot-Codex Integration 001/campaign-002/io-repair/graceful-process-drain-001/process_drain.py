"""Prospective two-phase process retirement; no EOF inference or socket mutation."""
import asyncio
import json
from pathlib import Path
import threading
import time

import native_cleanup_protocol as cleanup
import native_exit_drain as retained

REQUEST = 'campaign002-process-drain-request-1'
BRIDGE = 'campaign002-process-drain-bridge-1'
NATIVE = 'campaign002-process-drain-client-1'
require = retained.require
save = retained.save
CORE = ('cleanup_request_sha256', 'owner_receipt_sha256', 'start_monotonic_s',
        'graceful_deadline_monotonic_s')

def request_for(complete, phase, prepare_sha256=None):
    old = retained.request_for(complete)
    value = {'schema': REQUEST, **{k: old[k] for k in CORE},
             'phase': phase, 'prepare_sha256': prepare_sha256}
    return validate_request(value)

def validate_request(value):
    require(isinstance(value, dict) and set(value) == {'schema', *CORE, 'phase', 'prepare_sha256'}
            and value['schema'] == REQUEST and value['phase'] in ('prepare', 'finish'), 'process request')
    retained.validate_request({'schema': retained.REQUEST, **{k: value[k] for k in CORE}})
    require(value['prepare_sha256'] is None if value['phase'] == 'prepare'
            else cleanup.digest(value['prepare_sha256']), 'prepare receipt binding')
    return value

def validate_bridge(request, value):
    validate_request(request)
    require(isinstance(value, dict) and set(value) == {'schema', 'request', 'qualified', 'channels',
            'ledger_prefix', 'completed_monotonic_s', 'completed_perf_counter_ns', 'frontiers'}
            and value['schema'] == BRIDGE and value['request'] == request, 'process bridge shape')
    # Reuse only the established bounded scalar/type/deadline validator.
    old_request = {'schema': retained.REQUEST, **{k: request[k] for k in CORE}}
    retained.validate_bridge(old_request, {**{k: v for k, v in value.items() if k != 'frontiers'},
                             'schema': retained.BRIDGE, 'request': old_request})
    frontiers = value['frontiers']
    require(isinstance(frontiers, list), 'frontier list')
    if request['phase'] == 'finish':
        require(frontiers == [], 'finish frontier shape')
    else:
        require([r.get('channel_id') for r in frontiers] == value['channels'], 'frontier identities')
        for row in frontiers:
            require(set(row) == {'channel_id', 'h2', 'meters'} and
                    set(row['h2']) == {'error', 'preface_complete', 'settings_complete',
                    'frames_complete', 'headers_complete', 'open_streams'}, 'frontier shape')
            h2 = row['h2']
            require(h2['error'] is None and type(h2['open_streams']) is int and h2['open_streams'] == 0
                    and all(h2[k] is True for k in ('preface_complete', 'settings_complete',
                    'frames_complete', 'headers_complete')), 'incomplete application frontier')
            meters = row['meters']
            require(set(meters) == {'client_read', 'upload', 'download', 'client_written'}, 'meter keys')
            for meter in meters.values():
                require(set(meter) == {'bytes', 'sha256'} and type(meter['bytes']) is int
                        and meter['bytes'] >= 0 and cleanup.digest(meter['sha256']), 'meter shape')
            require(meters['client_read'] == meters['upload'] and
                    meters['download'] == meters['client_written'], 'unforwarded frontier bytes')
    require(len(cleanup.canonical(value)) <= retained.MAX_BYTES, 'process completion bound')
    return value

def native_phase(controller, phase):
    client = controller.client
    prepare = getattr(controller, 'process_prepare', None)
    if phase == 'finish':
        require(prepare is not None and controller.result['stdin_closed'] is True, 'finish before stdin close')
    request = request_for(controller.result['cleanup_barrier'], phase,
                          cleanup.sha(cleanup.canonical(prepare)) if phase == 'finish' else None)
    require(request['start_monotonic_s'] == controller.started and
            request['graceful_deadline_monotonic_s'] == controller.graceful, 'native deadline differs')
    callback = getattr(client.args, 'native_exit_barrier', None)
    require(callable(callback), 'protected process callback absent')
    begin = time.perf_counter_ns()
    value = callback(json.loads(cleanup.canonical(request)))
    received = time.perf_counter_ns()
    validate_bridge(request, value)
    require(begin <= value['completed_perf_counter_ns'] <= received and
            time.monotonic() < controller.graceful, 'late or stale process completion')
    save(Path(client.args.evidence)/('native-process-'+phase+'.json'),
         {'schema': NATIVE, 'request': request, 'bridge': value,
          'begin_perf_counter_ns': begin, 'received_perf_counter_ns': received})
    require(time.monotonic() < controller.graceful, 'receipt retention exceeded deadline')
    if phase == 'prepare': controller.process_prepare = value
    return value

def bridge_join(bridge, request):
    pending = None
    try:
        validate_request(request)
        request = json.loads(cleanup.canonical(request))
        require(threading.get_ident() != bridge.loop_thread, 'callback on owner loop')
        phase = request['phase']
        with bridge.failure_lock:
            require(not bridge.failures and bridge.fixture.client_finishing.is_set(), 'unavailable transport')
            prepare = getattr(bridge, 'process_prepare', None)
            require(request == request_for(bridge.cleanup_complete, phase,
                    cleanup.sha(cleanup.canonical(prepare)) if phase == 'finish' and prepare else None),
                    'foreign process cleanup request')
            claimed = getattr(bridge, 'process_phase_claimed', [])
            require(claimed == ([] if phase == 'prepare' else ['prepare']), 'duplicate or unordered phase')
            bridge.process_phase_claimed = [*claimed, phase]
        remaining = request['graceful_deadline_monotonic_s']-time.monotonic()
        require(remaining > 0, 'process join deadline')
        operation = prepare_bridge if phase == 'prepare' else finish_bridge
        pending = asyncio.run_coroutine_threadsafe(operation(bridge, request), bridge.loop)
        value = pending.result(timeout=remaining)
        with bridge.failure_lock:
            require(not bridge.failures and time.monotonic() < request['graceful_deadline_monotonic_s'],
                    'process completion late or failed')
        return json.loads(cleanup.canonical(validate_bridge(request, value)))
    except BaseException as error:
        bridge.fail('native_process_drain_'+type(error).__name__)
        if pending is not None: pending.cancel()
        raise

def retain_bridge(bridge, request, frontiers):
    with bridge.ledger.lock:
        prefix = {'sequence': len(bridge.ledger.events), 'sha256': bridge.ledger.previous}
    value = {'schema': BRIDGE, 'request': request, 'qualified': True,
             'channels': list(bridge.channels), 'ledger_prefix': prefix, 'frontiers': frontiers,
             'completed_monotonic_s': time.monotonic(), 'completed_perf_counter_ns': time.perf_counter_ns()}
    validate_bridge(request, value)
    save(Path(bridge.fixture.evidence)/('codehost-process-'+request['phase']+'.json'), value)
    require(time.monotonic() < request['graceful_deadline_monotonic_s'] and not bridge.failures,
            'late retained process completion')
    return value

async def prepare_bridge(bridge, request):
    deadline = request['graceful_deadline_monotonic_s']
    async with asyncio.timeout_at(bridge.loop.time()+max(0, deadline-time.monotonic())):
        require(bridge.fixture.client_finishing.is_set() and not bridge.failures, 'finish not healthy')
        bridge.begin_finish()
        require(bridge.server is not None and bridge.drain_task is not None, 'drain unavailable')
        await bridge.server.wait_closed()
        await asyncio.shield(bridge.drain_ack)
        # Admission is closed. Flush currently admitted output without waiting
        # for a pool's future TCP EOF. Pending reads remain real socket reads.
        await bridge.outgoing.join()
        while any(c.meters['download'].summary() != c.meters['client_written'].summary()
                  for c in bridge.channels.values()):
            require(not bridge.failures, 'failed while forwarding response frontier')
            await asyncio.sleep(.001)
        require(not bridge.failures and bridge.attempts == len(bridge.channels), 'incomplete admissions')
        frontiers = []
        for channel in bridge.channels.values():
            summary = channel.h2.summary()
            channel.h2.validate_reset_scope()
            frontiers.append({'channel_id': channel.id,
                'h2': {k: summary[k] for k in ('error', 'preface_complete', 'settings_complete',
                                             'frames_complete', 'headers_complete', 'open_streams')},
                'meters': {k: v.summary() for k, v in channel.meters.items()}})
        # No yield between the final frontier check, hash prefix and receipt.
        value = retain_bridge(bridge, request, frontiers)
        bridge.process_prepare = value
        return value

async def finish_bridge(bridge, request):
    deadline = request['graceful_deadline_monotonic_s']
    async with asyncio.timeout_at(bridge.loop.time()+max(0, deadline-time.monotonic())):
        require(list(bridge.channels) == bridge.process_prepare['channels'], 'new channel after prepare')
        await asyncio.shield(bridge.drain_task)
        require(bridge.drain['seal_qualified'] is True and bridge.sealed and not bridge.failures,
                'drain unqualified')
        await asyncio.shield(bridge.finished)
        require(bridge.finished_metadata.get('qualified') is True, 'namespace finish unqualified')
        if bridge.handlers: await asyncio.gather(*list(bridge.handlers))
        await bridge.outgoing.join()
        require(not bridge.failures and not bridge.handlers and bridge.budget.total == 0,
                'incomplete accepted handlers or queued bytes')
        for channel in bridge.channels.values():
            require(channel.parent_eof is not None and channel.upload_drained is not None
                    and channel.closed.done() and not channel.closed.cancelled()
                    and channel.closed.result() is True and channel.state == 'closed',
                    'missing genuine EOF or channel closure')
            meters = {k: v.summary() for k, v in channel.meters.items()}
            require(meters['client_read'] == meters['upload'] == channel.namespace_closed.get('upload')
                    and meters['download'] == meters['client_written'] == channel.namespace_closed.get('download'),
                    'endpoint byte mismatch')
        return retain_bridge(bridge, request, [])
