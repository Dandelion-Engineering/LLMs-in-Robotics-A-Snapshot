"""Join existing transport drainage before native process exit; no payload I/O."""
import asyncio
import json
import os
from pathlib import Path
import threading
import time

import native_cleanup_protocol as cleanup

REQUEST = 'campaign002-native-pre-exit-request-1'
BRIDGE = 'campaign002-native-pre-exit-bridge-1'
NATIVE = 'campaign002-native-pre-exit-client-1'
MAX_BYTES = 16384

def require(value, message):
    if value is not True: raise ValueError('Native pre-exit drain: ' + message)

def request_for(complete):
    require(isinstance(complete, dict), 'cleanup completion absent')
    request = cleanup.validate_request(complete['request'])
    cleanup.validate_complete({k:request[k] for k in cleanup.SEED_KEYS}, complete)
    return {'schema':REQUEST, 'cleanup_request_sha256':complete['request_sha256'],
            'owner_receipt_sha256':request['owner_receipt_sha256'],
            'start_monotonic_s':request['start_monotonic_s'],
            'graceful_deadline_monotonic_s':request['graceful_deadline_monotonic_s']}

def validate_request(request):
    require(isinstance(request, dict) and set(request) == {'schema','cleanup_request_sha256',
        'owner_receipt_sha256','start_monotonic_s','graceful_deadline_monotonic_s'}
        and request['schema'] == REQUEST, 'request shape')
    require(cleanup.digest(request['cleanup_request_sha256'])
            and cleanup.digest(request['owner_receipt_sha256']), 'request identity')
    start, deadline = request['start_monotonic_s'], request['graceful_deadline_monotonic_s']
    require(cleanup.finite(start) and cleanup.finite(deadline) and start < deadline <= start+5,
            'original deadline')
    return request

def validate_bridge(request, value):
    validate_request(request)
    require(isinstance(value, dict) and set(value) == {'schema','request','qualified','channels',
        'ledger_prefix','completed_monotonic_s','completed_perf_counter_ns'}
        and value['schema'] == BRIDGE and value['qualified'] is True and value['request'] == request,
        'bridge completion shape or identity')
    channels = value['channels']
    require(isinstance(channels, list) and len(channels) <= 16
            and all(type(c) is int for c in channels)
            and channels == list(range(1,len(channels)+1)), 'complete channel identities')
    prefix = value['ledger_prefix']
    require(isinstance(prefix, dict) and set(prefix) == {'sequence','sha256'}
            and type(prefix['sequence']) is int and 1 <= prefix['sequence'] <= 16384
            and cleanup.digest(prefix['sha256']), 'ledger prefix')
    completed = value['completed_monotonic_s']
    require(cleanup.finite(completed) and request['start_monotonic_s'] <= completed
            < request['graceful_deadline_monotonic_s'], 'completion deadline')
    require(type(value['completed_perf_counter_ns']) is int and value['completed_perf_counter_ns'] > 0,
            'completion observation')
    require(len(cleanup.canonical(value)) <= MAX_BYTES, 'completion bound')
    return value

def save(path, value):
    raw = json.dumps(value,indent=2,allow_nan=False).encode()+b'\n'
    require(len(raw) <= MAX_BYTES, 'receipt bound')
    with Path(path).open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())

def before_stdin_close(controller):
    """Called inside the original bounded worker; never closes or kills native."""
    client = controller.client
    request = request_for(controller.result['cleanup_barrier'])
    require(request['start_monotonic_s'] == controller.started
            and request['graceful_deadline_monotonic_s'] == controller.graceful,
            'native deadline differs')
    callback = getattr(client.args, 'native_exit_barrier', None)
    require(callable(callback), 'protected callback absent')
    begin = time.perf_counter_ns()
    result = callback(json.loads(cleanup.canonical(request)))
    received = time.perf_counter_ns()
    validate_bridge(request,result)
    require(time.monotonic() < controller.graceful and begin <= result['completed_perf_counter_ns'] <= received,
            'late or stale completion')
    save(Path(client.args.evidence)/'native-pre-exit-drain.json',
         {'schema':NATIVE,'request':request,'bridge':result,
          'begin_perf_counter_ns':begin,'received_perf_counter_ns':received})
    require(time.monotonic() < controller.graceful, 'receipt retention exceeded deadline')
    return result

def bridge_join(bridge, request):
    """Bootstrap-thread-only join to the running bridge loop."""
    pending = None
    try:
        validate_request(request)
        request = json.loads(cleanup.canonical(request))
        require(threading.get_ident() != bridge.loop_thread, 'callback on owner loop')
        with bridge.failure_lock:
            require(not getattr(bridge,'exit_drain_claimed',False), 'duplicate join')
            bridge.exit_drain_claimed = True
            require(not bridge.failures and bridge.fixture.client_finishing.is_set(), 'unavailable transport')
            require(request == request_for(bridge.cleanup_complete), 'foreign cleanup request')
        remaining = request['graceful_deadline_monotonic_s'] - time.monotonic()
        require(remaining > 0, 'join deadline')
        pending = asyncio.run_coroutine_threadsafe(drain_bridge(bridge,request),bridge.loop)
        value = pending.result(timeout=remaining)
        with bridge.failure_lock:
            require(not bridge.failures and time.monotonic() < request['graceful_deadline_monotonic_s'],
                    'completion late or failed')
        return json.loads(cleanup.canonical(validate_bridge(request,value)))
    except BaseException as error:
        bridge.fail('native_pre_exit_' + type(error).__name__)
        if pending is not None: pending.cancel()
        raise

async def drain_bridge(bridge, request):
    deadline = request['graceful_deadline_monotonic_s']
    async with asyncio.timeout_at(bridge.loop.time()+max(0,deadline-time.monotonic())):
        require(bridge.fixture.client_finishing.is_set() and not bridge.failures, 'finish not healthy')
        bridge.begin_finish()
        require(bridge.server is not None and bridge.drain_task is not None, 'drain unavailable')
        await bridge.server.wait_closed()
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
            meters = {k:v.summary() for k,v in channel.meters.items()}
            require(meters['client_read'] == meters['upload']
                    == channel.namespace_closed.get('upload')
                    and meters['download'] == meters['client_written']
                    == channel.namespace_closed.get('download'), 'endpoint byte mismatch')
        with bridge.ledger.lock:
            prefix = {'sequence':len(bridge.ledger.events),'sha256':bridge.ledger.previous}
        value = {'schema':BRIDGE,'request':request,'qualified':True,
                 'channels':list(bridge.channels),'ledger_prefix':prefix,
                 'completed_monotonic_s':time.monotonic(),
                 'completed_perf_counter_ns':time.perf_counter_ns()}
        validate_bridge(request,value)
        save(Path(bridge.fixture.evidence)/'codehost-pre-exit-drain.json',value)
        require(time.monotonic() < deadline and not bridge.failures, 'late retained completion')
        return value
