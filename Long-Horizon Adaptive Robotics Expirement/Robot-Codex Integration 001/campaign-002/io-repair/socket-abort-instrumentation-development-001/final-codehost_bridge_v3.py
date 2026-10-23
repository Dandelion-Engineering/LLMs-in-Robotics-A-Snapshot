"""One isolated code host, authenticated native channels, bounded opaque relay."""
from __future__ import annotations
import asyncio
import hashlib
import json
import math
import inspect
import os
from pathlib import Path
import socket
import threading
import time
import uuid

import codehost_mux_protocol as mux
import native_cleanup_protocol as cleanup
from codehost_owner import OwnerRegistry

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MAX_LEDGER_BYTES = MAX_STDERR_BYTES = 1024 * 1024
MAX_METADATA_RECORDS = 16384
MAX_RECEIPT_BYTES = 8 * 1024 * 1024
NAMESPACE_PREFIX = 'RCI_CODEHOST_V3 '
# Subprocess readers pause above 2*32768; a pipe transport may overshoot by
# one <=256 KiB read. Together with one framed read, encoded write and bounded
# write transport backlog, 640 KiB conservatively covers hidden framing buffers.
# This headroom is WITHIN each original queue ceiling, never added to it.
PIPE_READER_LIMIT = 32768
FRAME_HEADROOM_BYTES = 10 * 65536


class SocketReader:
    """No user-space read-ahead; reserve queue capacity before each read."""
    def __init__(self, sock): self.sock = sock
    async def read(self, count):
        return await asyncio.get_running_loop().sock_recv(self.sock, count)


class SocketWriter:
    def __init__(self, sock): self.sock, self.pending = sock, None
    def get_extra_info(self, name):
        return self.sock.getpeername() if name == 'peername' else self.sock.getsockname()
    def write(self, data):
        require(self.pending is None, 'overlapping_socket_write')
        self.pending = data
    async def drain(self):
        try:
            if self.pending is not None: await asyncio.get_running_loop().sock_sendall(self.sock, self.pending)
        finally: self.pending = None
    def close(self): self.sock.close()
    async def wait_closed(self): pass


class SocketServer:
    def __init__(self, handler, host, port, on_error):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            self.sock.setblocking(False); self.sock.bind((host, port)); self.sock.listen(16)
        except BaseException: self.sock.close(); raise
        self.sockets = [self.sock]; self.handler = handler
        self.on_error = on_error
        self.accept_task = asyncio.create_task(self.accept())
        self.pending_handlers = set()
    async def accept(self):
        try:
            while True:
                sock, _ = await asyncio.get_running_loop().sock_accept(self.sock)
                sock.setblocking(False)
                task = asyncio.create_task(self.handler(SocketReader(sock), SocketWriter(sock)))
                self.pending_handlers.add(task); task.add_done_callback(self.pending_handlers.discard)
        except BaseException as error:
            if not isinstance(error, asyncio.CancelledError): self.on_error('tcp_accept_' + type(error).__name__)
            raise
    def close(self): self.accept_task.cancel(); self.sock.close()
    async def wait_closed(self):
        await asyncio.gather(self.accept_task, return_exceptions=True)
        # Let every accepted handler enter its fail-closed admission path before
        # Bridge snapshots the handler set for owner-finish draining.
        await asyncio.sleep(0)


async def create_server(handler, host, port, *, on_error):
    return SocketServer(handler, host, port, on_error)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def save(path, value):
    data = json.dumps(value, indent=2).encode() + b'\n'
    require(len(data) <= MAX_RECEIPT_BYTES, 'protected_receipt_bound')
    with Path(path).open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    return {'path': Path(path).name, 'sha256': sha(data), 'bytes': len(data)}


def source_identities():
    paths = [HERE / n for n in ('codehost_bridge_v3.py', 'codehost_owner.py', 'codehost_mux_protocol.py',
                                'codehost_entry_v3.py', 'codehost_inside_v3.py', 'native_cleanup_protocol.py')]
    paths += [HERE.parents[1] / 'readiness-session-10/boundary' / n for n in ('linux_entry.py', 'namespace.py')]
    return {p.relative_to(REPO).as_posix(): {'sha256': sha(p.read_bytes()), 'bytes': p.stat().st_size} for p in paths}


class Ledger:
    """Owner registration happens on the bootstrap thread; all appends serialize."""
    def __init__(self, fixture):
        self.fixture = fixture
        self.path = Path(fixture.evidence) / 'codehost-transport-v3.jsonl'
        self.path.touch(exist_ok=False)
        self.lock = threading.RLock()
        self.previous, self.bytes, self.events = None, 0, []

    def emit(self, kind, **fields):
        with self.lock:
            value = {'schema': 'campaign002-codehost-transport-3', 'sequence': len(self.events) + 1,
                     'previous_sha256': self.previous, 'wall_unix_s': time.time(), 'monotonic_s': time.monotonic(),
                     'kind': kind, **fields}
            value['record_sha256'] = sha(mux.canonical(value)); data = mux.canonical(value) + b'\n'
            try:
                require(self.bytes + len(data) <= MAX_LEDGER_BYTES and len(self.events) < MAX_METADATA_RECORDS,
                        'parent_metadata_bound')
                with self.path.open('ab') as stream:
                    stream.write(data); stream.flush(); os.fsync(stream.fileno())
            except BaseException:
                self.fixture.abort_event.set(); raise
            self.events.append(value); self.bytes += len(data); self.previous = value['record_sha256']
            return value


def namespace_records(raw):
    require(raw.endswith(b'\n'), 'namespace_metadata_partial_tail')
    records = []
    for line in raw.decode('utf-8', errors='strict').splitlines():
        require(line.startswith(NAMESPACE_PREFIX), 'unknown_namespace_metadata_line')
        row = json.loads(line[len(NAMESPACE_PREFIX):])
        require(row.get('schema') == 'campaign002-codehost-namespace-3'
                and type(row.get('sequence')) is int and row['sequence'] == len(records) + 1,
                'namespace_metadata_sequence')
        records.append(row)
    require(records and records[0].get('kind') == 'open' and records[-1].get('kind') == 'closed'
            and sum(r.get('kind') == 'closed' for r in records) == 1, 'namespace_metadata_incomplete')
    return records


def frame_projection(events, direction):
    return [{k: r[k] for k in ('frame_type', 'channel_id', 'payload_bytes', 'payload_sha256')}
            for r in events if r.get('kind') == 'frame' and r.get('direction') == direction]


class Channel:
    def __init__(self, channel_id, reader, writer, owner):
        self.id, self.reader, self.writer, self.owner = channel_id, reader, writer, owner
        loop = asyncio.get_running_loop()
        self.opened, self.closed = loop.create_future(), loop.create_future()
        self.queue = asyncio.Queue()
        self.state = 'opening'
        self.h2 = mux.H2Witness()
        self.meters = {name: mux.ByteCounter() for name in ('client_read', 'upload', 'download', 'client_written')}
        self.namespace_closed = self.parent_eof = None
        self.finish_frontier = self.seal_frontier = self.upload_drained = None
        self.upload_task = self.sink_task = None
        self.upload_read_pending = False
        self.socket_failure_seen = False


class Bridge:
    def __init__(self, fixture, *, owner=None, launcher=None, retirer=None, sources=None):
        self.fixture = fixture
        self.owner = owner or OwnerRegistry(owner_kind=getattr(fixture, 'native_owner_kind', 'model_client'))
        self.launcher = launcher or asyncio.create_subprocess_exec
        if retirer is None:
            from retirement import retire
            retirer = retire
        self.retirer = retirer
        self.sources = sources if sources is not None else source_identities()
        self.ledger = Ledger(fixture)
        self.outgoing = asyncio.Queue(); self.budget = mux.QueueBudget(headroom_bytes=FRAME_HEADROOM_BYTES)
        self.channels, self.handlers, self.failures = {}, set(), []
        self.attempts = self.denied = 0
        self.process = self.ready = self.finished = self.server = None
        self.finishing = self.sealed = self.input_closed = False
        self.drain_ack = asyncio.get_running_loop().create_future()
        self.drain_task = None
        self.drain = None
        self.failure_lock = threading.RLock()
        self.admission_lock = asyncio.Lock()
        self.owner_binding = None
        self.loop = asyncio.get_running_loop()
        self.loop_thread = threading.get_ident()
        self.cleanup_claimed = False
        self.cleanup_abandoned = threading.Event()
        self.cleanup_ack = self.loop.create_future()
        self.cleanup_request = self.cleanup_begin_record = self.cleanup_namespace_record = None
        self.cleanup_begin_payload = self.cleanup_complete = None
        self.cleanup_future = None
        self.ready_metadata = self.finished_metadata = None
        self.stderr_state = {'data': bytearray(), 'bytes': 0, 'digest': hashlib.sha256(),
                             'complete': False, 'error_type': None}
        self.identity = fixture.run + '/codehost-owner-' + uuid.uuid4().hex + '.json'

    def fail(self, reason):
        with self.failure_lock:
            if reason not in self.failures:
                self.failures.append(reason)
                self.ledger.emit('failure', reason=reason)
            self.fixture.abort_event.set()

    def register_native(self, process, binary_path):
        try:
            require(not self.finishing, 'registration_after_finish')
            value = self.owner.register(process, binary_path)
            self.owner_binding = save(Path(self.fixture.evidence) / 'codehost-native-owner-v3.json', value)
            self.ledger.emit('owner_registered', owner=value, receipt=self.owner_binding)
            return value
        except Exception as error:
            self.fail('owner_registration_' + type(error).__name__)
            raise

    def native_cleanup_barrier(self, seed):
        """Synchronous bootstrap-thread join; no native control is written here."""
        pending = None
        try:
            cleanup.validate_seed(seed)
            seed = json.loads(cleanup.canonical(seed))
            require(threading.get_ident() != self.loop_thread, 'cleanup_callback_on_owner_loop')
            with self.failure_lock:
                require(not self.cleanup_claimed, 'duplicate_native_cleanup')
                self.cleanup_claimed = True
                require(not self.failures, 'cleanup_after_transport_failure')
            remaining = seed['graceful_deadline_monotonic_s'] - time.monotonic()
            require(remaining > 0, 'native_cleanup_deadline')
            pending = asyncio.run_coroutine_threadsafe(self.begin_native_cleanup(seed), self.loop)
            self.cleanup_future = pending
            value = pending.result(timeout=remaining)
            cleanup.validate_complete(seed, value)
            with self.failure_lock:
                require(not self.cleanup_abandoned.is_set() and not self.failures
                        and time.monotonic() < seed['graceful_deadline_monotonic_s'], 'native_cleanup_completion_late')
            return json.loads(cleanup.canonical(value))
        except BaseException as error:
            self.cleanup_abandoned.set()
            self.fail('native_cleanup_' + type(error).__name__)
            if pending is not None: pending.cancel()
            raise

    async def begin_native_cleanup(self, seed):
        deadline = seed['graceful_deadline_monotonic_s']
        try:
            async with asyncio.timeout_at(self.loop.time() + max(0, deadline-time.monotonic())):
                async with self.admission_lock:
                    require(not self.finishing and not self.fixture.client_finishing.is_set()
                            and not self.failures and not self.cleanup_abandoned.is_set(),
                            'native_cleanup_unavailable')
                    require(self.owner_binding is not None and self.owner.owner is not None
                            and self.ready_metadata is not None, 'native_cleanup_missing_owner')
                    require(self.cleanup_request is None, 'duplicate_native_cleanup_begin')
                    request = cleanup.bind_request(seed, self.owner_binding['sha256'])
                    request_sha = cleanup.sha(cleanup.canonical(request))
                    frontiers = [{'channel_id':c.id,'authentication_sha256':sha(mux.canonical(c.owner)),
                                  'already_closed':c.state == 'closed','upload_eof':c.parent_eof is not None,
                                  'h2':c.h2.summary()}
                                 for c in self.channels.values()]
                    record = self.ledger.emit('native_cleanup_begin',request=request,
                                              request_sha256=request_sha,channels=frontiers)
                    payload = cleanup.canonical({'schema':'campaign002-native-cleanup-begin-1',
                                                 'request':request,'parent_record_sha256':record['record_sha256']})
                    mux.encode_frame(mux.CLEANUP_BEGIN,0,payload)
                    for channel in self.channels.values():
                        # CLOSED can still be in flight from the namespace.
                        # Genuine EOF / ordered HALF_CLOSE is the shared boundary.
                        if channel.parent_eof is None: channel.h2.begin_cleanup(request['nonce'])
                    self.cleanup_request, self.cleanup_begin_record = request, record
                    self.cleanup_begin_payload = payload
                    self.enqueue(mux.CLEANUP_BEGIN,0,payload)
                ack = await asyncio.shield(self.cleanup_ack)
                with self.failure_lock:
                    require(not self.failures and not self.cleanup_abandoned.is_set()
                            and time.monotonic() < deadline, 'native_cleanup_completion_late')
                    value = {'schema':'campaign002-native-cleanup-complete-1','request':request,
                        'request_sha256':request_sha,'parent_barrier_record_sha256':record['record_sha256'],
                        'namespace_barrier_record_sha256':ack['namespace_record_sha256'],
                        'begin_payload_sha256':ack['begin_payload_sha256'],'ack_payload_sha256':ack['ack_payload_sha256'],
                        'parent_ack_record_sha256':ack['record_sha256'],'parent_ack_sequence':ack['sequence'],
                        'completed_monotonic_s':time.monotonic()}
                    cleanup.validate_complete(seed,value)
                    self.cleanup_complete = value
                    return value
        except BaseException:
            self.cleanup_abandoned.set()
            self.fail('native_cleanup_barrier_failed')
            raise

    def accept_cleanup_ack(self, payload):
        with self.failure_lock:
            request = self.cleanup_request
            require(request is not None and not self.cleanup_ack.done() and not self.cleanup_abandoned.is_set()
                    and not self.failures and not self.finishing
                    and time.monotonic() < request['graceful_deadline_monotonic_s'], 'unexpected_native_cleanup_ack')
            value = mux.metadata(payload)
            require(payload == cleanup.canonical(value) and set(value) ==
                    {'schema','nonce','request_sha256','parent_record_sha256','namespace_record'}
                    and value['schema'] == 'campaign002-native-cleanup-ack-1'
                    and value['nonce'] == request['nonce']
                    and value['request_sha256'] == cleanup.sha(cleanup.canonical(request))
                    and value['parent_record_sha256'] == self.cleanup_begin_record['record_sha256'],
                    'native_cleanup_ack_identity')
            row = value['namespace_record']
            require(isinstance(row,dict) and set(row) == {'schema','sequence','wall_unix_s','monotonic_s',
                    'kind','nonce','request_sha256','parent_record_sha256','child_pid','channels'}
                    and row['schema'] == 'campaign002-codehost-namespace-3' and row['kind'] == 'native_cleanup_begin'
                    and type(row['sequence']) is int and row['sequence'] > 0
                    and all(cleanup.finite(row[k]) for k in ('wall_unix_s','monotonic_s'))
                    and row['nonce'] == value['nonce'] and row['request_sha256'] == value['request_sha256']
                    and row['parent_record_sha256'] == value['parent_record_sha256']
                    and row['child_pid'] == self.ready_metadata['child_pid'], 'native_cleanup_namespace_identity')
            fronts = self.cleanup_begin_record['channels']
            require(isinstance(row['channels'],list) and len(row['channels']) == len(fronts)
                    and all(isinstance(n,dict) and set(n) == {'channel_id','already_closed','upload_eof','h2'}
                            and type(n['channel_id']) is int and n['channel_id'] == p['channel_id'] and type(n['already_closed']) is bool
                            and type(n['upload_eof']) is bool and n['upload_eof'] == p['upload_eof']
                            and isinstance(n['h2'],dict) and n['h2'].get('cleanup_phase_nonce') is None
                            for n,p in zip(row['channels'],fronts)), 'native_cleanup_namespace_channels')
            self.cleanup_namespace_record = row
            ack = self.ledger.emit('native_cleanup_ack',request_sha256=value['request_sha256'],
                namespace_record_sha256=cleanup.sha(cleanup.canonical(row)),
                begin_payload_sha256=sha(self.cleanup_begin_payload),ack_payload_sha256=sha(payload),namespace_record=row)
            self.cleanup_ack.set_result(ack)

    def enqueue(self, kind, channel_id, payload=b'', *, reserved=False):
        mux.encode_frame(kind, channel_id, payload)  # validate before mutation
        require(not self.sealed or kind == mux.FINISH, 'frame_after_owner_finish')
        require(not self.finishing or kind != mux.OPEN, 'open_after_drain_begin')
        if kind == mux.DATA and not reserved:
            self.budget.reserve(channel_id, len(payload))
        self.outgoing.put_nowait((kind, channel_id, payload))

    def frame_event(self, direction, kind, channel_id, payload):
        if kind != mux.FINISHED:  # its exact payload binds the terminal namespace record
            self.ledger.emit('frame', direction=direction, frame_type=kind, channel_id=channel_id,
                             payload_bytes=len(payload), payload_sha256=sha(payload))

    def closing_marker(self):
        """Read only the bounded protected tail, after the fsynced producer flag."""
        path = Path(self.fixture.evidence) / 'client/events.jsonl'
        with path.open('rb') as stream:
            stream.seek(0, 2); size = stream.tell(); stream.seek(max(0, size-MAX_LEDGER_BYTES))
            raw = stream.read(MAX_LEDGER_BYTES)
        if size > MAX_LEDGER_BYTES: raw = raw.split(b'\n', 1)[1]
        require(raw.endswith(b'\n'), 'closing_marker_partial_tail')
        rows = [json.loads(line) for line in raw.splitlines()]
        markers = [r for r in rows if r.get('kind') == 'client_finishing_before_close']
        require(len(markers) == 1, 'closing_marker_cardinality')
        marker = markers[0]
        require(marker.get('schema') == 'campaign002-client-finishing-1'
                and type(marker.get('monotonic_s')) in (int,float)
                and math.isfinite(marker['monotonic_s']) and 0 <= marker['monotonic_s'] <= time.monotonic(),
                'closing_marker_identity')
        return marker

    def observe_finishing(self):
        if self.fixture.client_finishing.is_set() and not self.finishing:
            self.begin_finish()

    def begin_finish(self):
        """Phase one is synchronous: freeze admission/frontiers before later DATA."""
        if self.finishing: return
        self.finishing = True
        if self.server: self.server.close()
        try:
            require(self.fixture.client_finishing.is_set(), 'owner_finish_not_declared')
            start = self.closing_marker()['monotonic_s']
        except (OSError, ValueError, KeyError, IndexError):
            self.fail('owner_closing_marker_invalid'); start = time.monotonic()
        self.drain = {'start_monotonic_s':start,'deadline_monotonic_s':start+25,'bound_s':25,
                      'seal_qualified':False,'seal_error_code':None,'completed_monotonic_s':None}
        for channel in self.channels.values():
            channel.finish_frontier = channel.h2.summary()
            self.ledger.emit('channel_finish_frontier', channel_id=channel.id,
                             client_finishing=self.fixture.client_finishing.is_set(), h2=channel.finish_frontier,
                             upload_read_pending=channel.upload_read_pending)
            try:
                channel.h2.validate_reset_scope()
                if channel.state != 'closed': channel.h2.begin_retirement()
            except ValueError:
                self.fail('retirement_frontier_invalid')
        self.ledger.emit('owner_drain_begin', start_monotonic_s=start, deadline_monotonic_s=start+25,bound_s=25)
        if self.process is not None:
            self.enqueue(mux.DRAIN_BEGIN, 0)
            self.drain_task = asyncio.create_task(self.finish_owner())

    def remaining(self):
        remaining = self.drain['deadline_monotonic_s'] - time.monotonic()
        if remaining <= 0: raise TimeoutError('owner_drain_deadline')
        return remaining

    async def bounded(self, awaitable):
        owned = inspect.iscoroutine(awaitable)
        task = asyncio.ensure_future(awaitable) if owned else awaitable
        try: return await asyncio.wait_for(asyncio.shield(task), self.remaining())
        finally:
            if owned and not task.done():
                task.cancel(); await asyncio.gather(task,return_exceptions=True)

    async def finish_owner(self):
        error_code = None
        try:
            await self.bounded(self.drain_ack)
            uploads = [c.upload_task for c in self.channels.values() if c.upload_task]
            if uploads: await self.bounded(asyncio.gather(*uploads))
            require(all(c.parent_eof is not None for c in self.channels.values()), 'missing_genuine_upload_eof')
            await self.bounded(self.outgoing.join())
            require(all(c.upload_drained is not None for c in self.channels.values()), 'missing_upload_drain')
            require(not self.failures, 'existing_transport_failure')
            for channel in self.channels.values():
                require(channel.meters['client_read'].summary() == channel.meters['upload'].summary(), 'parent_upload_drop')
                channel.h2.upload_eof()
        except BaseException as error:
            if isinstance(error, asyncio.CancelledError): raise
            error_code = 'drain_timeout' if isinstance(error, TimeoutError) else 'drain_invalid'
            self.fail(error_code)
        self.drain['seal_qualified'] = error_code is None
        self.drain['seal_error_code'] = error_code
        for channel in self.channels.values():
            channel.seal_frontier = channel.h2.summary()
            self.ledger.emit('channel_seal_frontier',channel_id=channel.id,h2=channel.seal_frontier)
        self.ledger.emit('owner_finishing',client_finishing=self.fixture.client_finishing.is_set(),
                         authenticated_channels=len(self.channels),attempts=self.attempts,
                         seal_qualified=error_code is None,seal_error_code=error_code)
        self.sealed = True
        self.enqueue(mux.FINISH,0)

    async def watch_finishing(self):
        while not self.fixture.client_finishing.is_set(): await asyncio.sleep(.001)
        self.begin_finish()

    def feed_h2(self, channel, direction, payload):
        self.observe_finishing()
        channel.h2.feed(direction, payload)
        channel.h2.validate_reset_scope(channel.finish_frontier)

    async def send_frames(self):
        try:
            while True:
                frame = await self.outgoing.get()
                if frame is None:
                    return
                kind, channel_id, payload = frame
                try:
                    await mux.write_frame(self.process.stdin, kind, channel_id, payload)
                    self.frame_event('outgoing', kind, channel_id, payload)
                    if kind == mux.DATA: self.channels[channel_id].meters['upload'].add(payload)
                    if kind == mux.HALF_CLOSE:
                        channel = self.channels[channel_id]
                        require(channel.parent_eof is not None and channel.upload_drained is None, 'upload_drain_without_unique_eof')
                        channel.upload_drained = self.ledger.emit('upload_drained',channel_id=channel_id,
                            meters={k:v.summary() for k,v in channel.meters.items()})
                    if kind == mux.FINISH:
                        require(self.outgoing.empty(), 'queued_frame_after_finish')
                        self.process.stdin.close(); self.input_closed = True
                        self.ledger.emit('owner_input_closed', after_finish_drain=True)
                        return
                finally:
                    if kind == mux.DATA: self.budget.release(channel_id, len(payload))
                    self.outgoing.task_done()
        except BaseException as error:
            if not isinstance(error, asyncio.CancelledError): self.fail('frame_write_' + type(error).__name__)
            raise

    async def receive_frames(self):
        try:
            while frame := await mux.read_frame(self.process.stdout):
                if self.fixture.client_finishing.is_set(): self.begin_finish()
                kind, channel_id, payload = frame
                require(not self.finished.done(), 'frame_after_finished')
                self.frame_event('incoming', kind, channel_id, payload)
                if kind == mux.READY:
                    require(not self.ready.done(), 'duplicate_ready')
                    value = mux.metadata(payload)
                    require(value.get('schema') == 'campaign002-codehost-owner-ready-3'
                            and type(value.get('child_pid')) is int and value['child_pid'] > 0
                            and value.get('max_connections') == 16 and value.get('max_frame_bytes') == 65536
                            and value.get('per_channel_queue_bytes') == 1048576
                            and value.get('aggregate_queue_bytes') == 4194304, 'invalid_shared_host_ready')
                    self.ready_metadata = value; self.ready.set_result(value)
                elif kind == mux.CLEANUP_ACK:
                    self.accept_cleanup_ack(payload)
                elif kind == mux.DRAIN_ACK:
                    require(self.finishing and not self.drain_ack.done(), 'unexpected_drain_ack')
                    self.ledger.emit('owner_drain_ack')
                    self.drain_ack.set_result(True)
                elif kind == mux.FINISHED:
                    value = mux.metadata(payload)
                    require(all(c.state == 'closed' for c in self.channels.values()), 'premature_finished')
                    if value.get('qualified') is True:
                        require(self.sealed, 'qualified_finished_before_seal')
                    else:
                        self.fail('namespace_finished_unqualified')
                        if not self.drain_ack.done(): self.drain_ack.set_exception(ValueError('namespace_drain_failed'))
                    self.finished_metadata = value
                    self.ledger.emit('namespace_finished', payload_bytes=len(payload), payload_sha256=sha(payload),
                                     finished=self.finished_metadata)
                    self.finished.set_result(self.finished_metadata)
                else:
                    require(self.ready.done() and channel_id in self.channels, 'frame_for_unknown_channel')
                    channel = self.channels[channel_id]
                    if kind == mux.OPENED:
                        require(channel.state == 'opening', 'duplicate_or_late_opened')
                        channel.state = 'live'; channel.opened.set_result(True)
                    elif kind == mux.DATA:
                        require(channel.state == 'live', 'data_outside_live_channel')
                        channel.meters['download'].add(payload)
                        self.budget.reserve(channel_id, len(payload))
                        try: self.feed_h2(channel, 'download', payload)
                        except BaseException:
                            self.budget.release(channel_id,len(payload)); raise
                        channel.queue.put_nowait(payload)
                    elif kind == mux.CLOSED:
                        require(channel.state in ('live', 'opening'), 'duplicate_channel_close')
                        value = mux.metadata(payload)
                        require(value.get('schema') == 'campaign002-codehost-channel-3'
                                and value.get('channel_id') == channel_id, 'foreign_channel_close')
                        channel.namespace_closed = value; channel.state = 'closed'; channel.queue.put_nowait(None)
                        if not channel.opened.done(): channel.opened.set_exception(ValueError('channel_closed_before_opened'))
                    elif kind == mux.ERROR:
                        require(channel.state != 'closed', 'error_after_channel_closed')
                        mux.metadata(payload); self.fail('namespace_channel_error')
                    else:
                        raise ValueError('unexpected_namespace_frame')
            require(self.finished.done(), 'namespace_framing_eof_before_finished')
            self.ledger.emit('namespace_output_closed', after_finished=True)
        except BaseException as error:
            if not isinstance(error, asyncio.CancelledError): self.fail('frame_read_' + type(error).__name__)
            for future in (self.ready, self.finished, self.drain_ack, self.cleanup_ack):
                if future is not None and not future.done(): future.set_exception(error)
            for channel in self.channels.values():
                for future in (channel.opened, channel.closed):
                    if not future.done(): future.set_exception(error)
            raise

    def record_socket_failure(self, channel, operation, error):
        """Bounded first-error metadata; never replace the original socket error."""
        if channel.socket_failure_seen:
            return
        channel.socket_failure_seen = True
        try:
            require(operation in ('upload_read', 'download_write') and isinstance(error, OSError),
                    'invalid_socket_diagnostic_call')
            classes = (OSError, ConnectionError, ConnectionAbortedError, ConnectionRefusedError,
                       ConnectionResetError, BrokenPipeError, TimeoutError, BlockingIOError, InterruptedError)
            name = type(error).__name__ if type(error) in classes else 'OtherOSError'
            def code(field):
                value = getattr(error, field, None)
                return value if type(value) is int and -(2**31) <= value < 2**32 else None
            self.ledger.emit('socket_failure', diagnostic_schema='campaign002-socket-failure-1',
                operation=operation, channel_id=channel.id, exception_class=name,
                errno=code('errno'), winerror=code('winerror'),
                cleanup_active=self.cleanup_request is not None and not self.cleanup_abandoned.is_set(),
                client_finishing=self.fixture.client_finishing.is_set(), owner_draining=self.finishing,
                owner_sealed=self.sealed, byte_counters={key:value.bytes for key,value in channel.meters.items()})
        except BaseException:
            # Ledger bounds/failures retain their original abort behavior. The
            # operation's OSError must still reach the existing fatal handler.
            pass

    async def upload(self, channel):
        reserved = 0
        try:
            while True:
                self.budget.reserve(channel.id, mux.MAX_FRAME_BYTES); reserved = mux.MAX_FRAME_BYTES
                channel.upload_read_pending = True
                try: data = await channel.reader.read(mux.MAX_FRAME_BYTES)
                except OSError as error:
                    self.record_socket_failure(channel, 'upload_read', error)
                    raise
                finally: channel.upload_read_pending = False
                self.budget.release(channel.id, reserved-len(data)); reserved = len(data)
                if not data: break
                if self.fixture.client_finishing.is_set(): self.begin_finish()
                channel.meters['client_read'].add(data)
                require(not self.sealed, 'client_data_after_owner_seal')
                self.feed_h2(channel, 'upload', data)
                self.enqueue(mux.DATA, channel.id, data, reserved=True); reserved = 0
        finally:
            if reserved: self.budget.release(channel.id, reserved)
        finishing = self.fixture.client_finishing.is_set()
        self.observe_finishing()
        channel.parent_eof = self.ledger.emit('client_eof', channel_id=channel.id, client_finishing=finishing,
                                             h2=channel.h2.summary())
        self.enqueue(mux.HALF_CLOSE, channel.id)
        if not finishing: channel.h2.idle_eof()

    async def sink(self, channel):
        try:
            while True:
                data = await channel.queue.get()
                if data is None: break
                try:
                    try:
                        channel.writer.write(data); await channel.writer.drain()
                    except OSError as error:
                        self.record_socket_failure(channel, 'download_write', error)
                        raise
                    channel.meters['client_written'].add(data)
                finally:
                    self.budget.release(channel.id, len(data)); channel.queue.task_done()
            value = channel.namespace_closed
            require(value is not None and value.get('qualified') is True, 'unqualified_namespace_channel')
            require(channel.meters['client_read'].summary() == channel.meters['upload'].summary(), 'parent_upload_drop')
            require(channel.meters['download'].summary() == channel.meters['client_written'].summary(), 'parent_download_drop')
            require(value.get('upload') == channel.meters['upload'].summary()
                    and value.get('download') == channel.meters['download'].summary(), 'relay_endpoint_byte_mismatch')
            if value.get('reason') == 'clean_idle_eof': channel.h2.idle_eof()
            else: require(value.get('reason') == 'owner_finish' and self.finishing
                          and self.fixture.client_finishing.is_set(), 'unexpected_channel_close_reason')
            summary = channel.h2.summary()
            require(all(summary[n] for n in ('preface_complete','settings_complete','frames_complete','headers_complete')) and not summary['error'],
                    'partial_h2_at_channel_close')
            self.ledger.emit('channel_closed', channel_id=channel.id, namespace_closed=value,
                             meters={k: v.summary() for k,v in channel.meters.items()}, h2=channel.h2.summary())
            channel.closed.set_result(True)
        except BaseException as error:
            if not isinstance(error, asyncio.CancelledError): self.fail('channel_sink_' + type(error).__name__)
            if not channel.closed.done(): channel.closed.set_exception(error)
            raise

    async def handle(self, reader, writer):
        task = asyncio.current_task(); self.handlers.add(task)
        self.attempts += 1; channel_id = self.attempts
        channel = None
        client_tuple = server_tuple = None
        try:
            client_tuple, server_tuple = writer.get_extra_info('peername'), writer.get_extra_info('sockname')
            require(not self.finishing and not self.fixture.client_finishing.is_set(), 'admission_after_owner_finish')
            require(channel_id <= mux.MAX_CONNECTIONS, 'connection_attempt_bound')
            # No client read or child OPEN occurs until the complete OS proof succeeds.
            async with self.admission_lock:
                # The shared flag also requests the planned native interruption.
                # Only the authenticated cleanup phase may admit its same-owner
                # channels then; transport failure remains permanently fatal.
                require(not self.failures and (not self.fixture.abort_event.is_set()
                        or self.cleanup_request is not None and not self.cleanup_abandoned.is_set()),
                        'admission_after_abort')
                require(self.owner_binding is not None, 'missing_owner_registration')
                auth = await asyncio.to_thread(self.owner.authenticate, client_tuple, server_tuple)
                require(not self.finishing and not self.fixture.client_finishing.is_set(), 'owner_finished_during_authentication')
                require(not self.failures and (not self.fixture.abort_event.is_set()
                        or self.cleanup_request is not None and not self.cleanup_abandoned.is_set()),
                        'transport_failed_during_authentication')
                self.ledger.emit('channel_authenticated', channel_id=channel_id, authentication=auth,
                                 owner_receipt=self.owner_binding)
                channel = Channel(channel_id, reader, writer, auth); self.channels[channel_id] = channel
                if self.cleanup_request is not None:
                    frontier = channel.h2.begin_cleanup(self.cleanup_request['nonce'])
                    self.ledger.emit('native_cleanup_channel',channel_id=channel_id,
                        nonce=self.cleanup_request['nonce'],request_sha256=cleanup.sha(cleanup.canonical(self.cleanup_request)),
                        authentication_sha256=sha(mux.canonical(auth)),h2=frontier)
                channel.sink_task = asyncio.create_task(self.sink(channel))
                self.enqueue(mux.OPEN, channel_id)
            await asyncio.wait_for(asyncio.shield(channel.opened), 15)
            channel.upload_task = asyncio.create_task(self.upload(channel))
            done, _ = await asyncio.wait([channel.upload_task, channel.closed], return_when=asyncio.FIRST_COMPLETED)
            if channel.upload_task in done:
                try: await channel.upload_task
                except asyncio.CancelledError:
                    # Task cancellation is never evidence of genuine TCP EOF.
                    raise ValueError('unexpected_upload_cancellation')
            await channel.closed
        except BaseException as error:
            if channel is None:
                self.denied += 1
                self.ledger.emit('channel_denied', channel_id=channel_id,
                                 client=list(client_tuple) if client_tuple else None,
                                 server=list(server_tuple) if server_tuple else None,
                                 reason=str(error) if isinstance(error, ValueError) else type(error).__name__)
            if not isinstance(error, asyncio.CancelledError): self.fail('channel_' + type(error).__name__)
        finally:
            if channel:
                for child in (channel.upload_task, channel.sink_task):
                    if child and not child.done(): child.cancel()
                await asyncio.gather(*(x for x in (channel.upload_task, channel.sink_task) if x), return_exceptions=True)
                for future in (channel.opened, channel.closed):
                    if future.done() and not future.cancelled(): future.exception()
            writer.close()
            try: await writer.wait_closed()
            except Exception: self.fail('client_socket_close_error')
            self.handlers.discard(task)

    async def errors(self):
        state = self.stderr_state
        try:
            while part := await self.process.stderr.read(65536):
                state['bytes'] += len(part); state['digest'].update(part)
                state['data'].extend(part[:max(0, MAX_STDERR_BYTES-len(state['data']))])
                if state['bytes'] > MAX_STDERR_BYTES: self.fail('namespace_stderr_bound')
            state['complete'] = True
        except BaseException as error:
            state['error_type'] = type(error).__name__
            raise

    def retain_stderr(self, receipt):
        """Durably retain safe bounded diagnostics even when framing failed.

        The raw hash covers all bytes observed by the independent stderr drain;
        capture_complete distinguishes EOF from a failed or timed-out drain.
        Never persist an incomplete last line at a capture truncation boundary,
        where an invocation capability could have been split before redaction.
        """
        state = self.stderr_state
        raw = bytes(state['data'])
        truncated = state['bytes'] != len(raw) or not state['complete']
        complete_lines = raw
        if truncated and not raw.endswith(b'\n'):
            complete_lines = raw[:raw.rfind(b'\n')+1]
        try:
            text = complete_lines.decode('utf-8', errors='strict'); utf8_valid = True; decode_error = None
        except UnicodeDecodeError:
            text = complete_lines.decode('utf-8', errors='replace'); utf8_valid = False; decode_error = 'UnicodeDecodeError'
        redaction_error = None
        try:
            redacted = self.fixture.redact(text)
            require(isinstance(redacted, str), 'stderr_redactor_must_return_text')
        except Exception as error:
            # A broken redactor must never cause raw dynamic text to be saved.
            redaction_error = type(error).__name__
            redacted = '[STDERR_WITHHELD_REDACTION_FAILED]\n'
        safe = redacted.encode('utf-8')
        redaction_changed = redaction_error is not None or redacted != text
        if len(safe) > MAX_STDERR_BYTES:
            safe = safe[:MAX_STDERR_BYTES].decode('utf-8', errors='ignore').encode('utf-8')
            truncated = True
        path = Path(self.fixture.evidence) / 'codehost-owner-stderr-v3.txt'
        with path.open('xb') as stream:
            stream.write(safe); stream.flush(); os.fsync(stream.fileno())
        receipt['stderr'] = {'path': path.name, 'bytes': len(safe), 'sha256': sha(safe),
            'raw_bytes': state['bytes'], 'raw_sha256': state['digest'].hexdigest(),
            'truncated': truncated, 'redacted': redaction_changed}
        receipt['stderr_capture'] = {'capture_complete': state['complete'], 'error_type': state['error_type'],
            'captured_prefix_bytes': len(raw), 'discarded_partial_tail_bytes': len(raw)-len(complete_lines),
            'utf8_valid': utf8_valid, 'decode_error_type': decode_error, 'redaction_error_type': redaction_error,
            'scope': 'Original count/hash cover observed stderr bytes; retained text is bounded and redacted. Incomplete capture does not establish full-stream identity.'}
        unchanged = (state['complete'] and utf8_valid and not truncated and not redaction_changed
                     and state['bytes'] == len(raw) and safe == raw)
        return safe, unchanged

    async def run(self, callback):
        outcome = None; tasks = []; receipt = {'schema': 'campaign002-codehost-owner-bridge-3', 'qualified': False, 'sources': self.sources}
        self.ledger.emit('open', sources=self.sources, max_connections=16, max_frame_bytes=65536,
                         per_channel_queue_bytes=1048576, aggregate_queue_bytes=4194304,
                         framing_headroom_bytes=FRAME_HEADROOM_BYTES, subprocess_reader_limit=PIPE_READER_LIMIT,
                         client_socket_read_ahead_bytes=0)
        self.fixture.native_process_ready = self.register_native
        self.fixture.native_cleanup_barrier = self.native_cleanup_barrier
        loop = asyncio.get_running_loop(); self.ready = loop.create_future(); self.finished = loop.create_future()
        try:
            self.process = await self.launcher(*self.fixture.argv('codehost'), '--identity-file', self.identity,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                limit=PIPE_READER_LIMIT)
            self.ledger.emit('namespace_started')
            sender = asyncio.create_task(self.send_frames()); receiver = asyncio.create_task(self.receive_frames())
            errors = asyncio.create_task(self.errors()); tasks = [sender, receiver, errors]
            await asyncio.wait_for(asyncio.shield(self.ready), 25)
            self.server = await create_server(self.handle, '127.0.0.1', 0, on_error=self.fail)
            self.ledger.emit('listening', shared_child_pid=self.ready_metadata['child_pid'],
                             endpoint=list(self.server.sockets[0].getsockname()[:2]))
            watcher = asyncio.create_task(self.watch_finishing()); tasks.append(watcher)
            outcome = await callback('http://127.0.0.1:' + str(self.server.sockets[0].getsockname()[1]))
        except BaseException as error:
            self.fail('owner_run_' + type(error).__name__)
            if isinstance(error, (KeyboardInterrupt, SystemExit)): raise
        finally:
            if self.cleanup_future is not None and not self.cleanup_future.done():
                self.cleanup_abandoned.set(); self.cleanup_future.cancel(); self.fail('native_cleanup_incomplete_at_finish')
            self.begin_finish()
            if self.server:
                await self.server.wait_closed()
            if not self.fixture.client_finishing.is_set(): self.fail('owner_finish_not_declared')
            try: self.observe_finishing()
            except ValueError as error: self.fail(str(error))
            if not self.owner_binding: self.fail('missing_owner_registration')
            if self.process is not None:
                try:
                    if self.drain_task: await self.bounded(self.drain_task)
                    await self.bounded(self.finished)
                    if self.handlers: await self.bounded(asyncio.gather(*list(self.handlers)))
                    await self.bounded(receiver)
                    self.drain['completed_monotonic_s'] = time.monotonic()
                    require(self.drain['completed_monotonic_s'] <= self.drain['deadline_monotonic_s'], 'owner_drain_deadline')
                    self.ledger.emit('owner_drain_completed', **self.drain)
                except BaseException as error: self.fail('owner_drain_' + type(error).__name__)
                if self.drain_task and not self.drain_task.done(): self.drain_task.cancel()
                if self.drain_task: await asyncio.gather(self.drain_task,return_exceptions=True)
                for task in list(self.handlers): task.cancel()
                if self.handlers: await asyncio.gather(*list(self.handlers), return_exceptions=True)
                self.process.stdin.close()
                if not self.input_closed:
                    self.input_closed = True
                    self.ledger.emit('owner_input_closed',after_finish_drain=False,failed_cleanup=True)
                retirement = Path(self.fixture.evidence) / 'codehost-owner-retirement-v3.json'
                self.ledger.emit('retirement_started')
                try:
                    await self.retirer(self.process, self.identity, retirement)
                    require(read_json(retirement).get('qualified') is True, 'namespace_retirement_unverified')
                    receipt['retirement'] = {'path': retirement.name, 'sha256': sha(retirement.read_bytes()), 'bytes': retirement.stat().st_size}
                except BaseException as error: self.fail('owner_retirement_' + type(error).__name__)
                receipt['exit_code'] = self.process.returncode
                if type(self.process.returncode) is not int or self.process.returncode != 0: self.fail('namespace_wrapper_nonzero')
                try:
                    await asyncio.wait_for(asyncio.shield(receiver), 3)
                except BaseException as error: self.fail('namespace_receipt_' + type(error).__name__)
                # Receiver success is not a prerequisite for collecting startup
                # diagnostics. A drain failure still leaves a bounded prefix.
                try:
                    await asyncio.wait_for(asyncio.shield(errors), 3)
                except BaseException as error:
                    self.fail('namespace_stderr_capture_' + type(error).__name__)
                    if not errors.done(): errors.cancel()
                    await asyncio.gather(errors, return_exceptions=True)
                try:
                    safe, unchanged = self.retain_stderr(receipt)
                    require(unchanged, 'namespace_metadata_truncated_or_redacted')
                    records = namespace_records(safe)
                    # Diagnostic failures retain their complete original namespace
                    # metadata too; these bindings never promote qualification.
                    receipt['namespace_records'] = records
                    cleanup_rows = [r for r in records if r.get('kind') == 'native_cleanup_begin']
                    require(cleanup_rows == ([] if self.cleanup_namespace_record is None else [self.cleanup_namespace_record]),
                            'native_cleanup_namespace_record_mismatch')
                    if self.cleanup_request is not None:
                        require(self.cleanup_complete is not None and not self.cleanup_abandoned.is_set(),
                                'native_cleanup_not_completed')
                        require(records[-1].get('cleanup_barrier') == {
                            'nonce':self.cleanup_request['nonce'],
                            'request_sha256':self.cleanup_complete['request_sha256'],
                            'parent_record_sha256':self.cleanup_complete['parent_barrier_record_sha256'],
                            'namespace_record_sha256':self.cleanup_complete['namespace_barrier_record_sha256'],
                            'begin_payload_sha256':self.cleanup_complete['begin_payload_sha256'],
                            'ack_payload_sha256':self.cleanup_complete['ack_payload_sha256']},
                            'native_cleanup_namespace_terminal_mismatch')
                    else: require(records[-1].get('cleanup_barrier') is None,'unexpected_native_cleanup_terminal')
                    require(records[-1] == self.finished_metadata and records[-1].get('qualified') is True,
                            'namespace_finished_mismatch_or_unqualified')
                    terminal = records[-1]
                    require(terminal.get('reason') == 'owner_finish' and terminal.get('owner_finish_received') is True
                            and terminal.get('stdin_eof') is True and terminal.get('owner_input_wait_bound_s') == .5
                            and terminal.get('child_pid') == self.ready_metadata['child_pid']
                            and terminal.get('child_exit_before_cleanup') in (None, 0)
                            and (terminal.get('child_exit_code') == 0 or terminal.get('terminate_sent') is True
                                 and terminal.get('child_exit_code') == -15)
                            and terminal.get('kill_sent') is False and terminal.get('error_type') is None
                            and terminal.get('diagnostic_streams_complete') is True
                            and terminal.get('queue_bytes_at_close') == 0
                            and terminal.get('channel_count') == terminal.get('channels_closed') == len(self.channels),
                            'namespace_terminal_lifecycle')
                    starts = [r for r in records if r.get('kind') == 'child_started']
                    diagnostics = [r for r in records if r.get('kind') == 'child_diagnostic']
                    require(len(starts) == 1 and starts[0].get('child_pid') == self.ready_metadata['child_pid']
                            and len(diagnostics) == 2 and {r.get('stream') for r in diagnostics} == {'stdout','stderr'}
                            and all(type(r.get('bytes')) is int and r['bytes'] >= 0 and r.get('truncated') is False
                                    and isinstance(r.get('sha256'), str) and len(r['sha256']) == 64 for r in diagnostics)
                            and sum(r['bytes'] for r in diagnostics) <= MAX_STDERR_BYTES,
                            'namespace_child_or_diagnostic_accounting')
                    require(frame_projection(self.ledger.events, 'outgoing') == frame_projection(records, 'incoming')
                            and frame_projection(self.ledger.events, 'incoming') == frame_projection(records, 'outgoing'),
                            'framing_endpoint_transcript_mismatch')
                except BaseException as error: self.fail('namespace_receipt_' + type(error).__name__)
            for task in tasks:
                if not task.done(): task.cancel()
            if tasks: await asyncio.gather(*tasks, return_exceptions=True)
            for future in (self.ready, self.finished, self.drain_ack, self.cleanup_ack):
                if future.done() and not future.cancelled(): future.exception()
            receipt.update(cleanup_barrier=self.cleanup_complete, drain=self.drain, owner_receipt=self.owner_binding, owner=self.owner.owner, ready=self.ready_metadata,
                           finished=self.finished_metadata, attempts=self.attempts, accepted=len(self.channels), denied=self.denied,
                           queue_maximum_bytes=self.budget.maximum, queued_bytes_at_close=self.budget.total,
                           framing_headroom_bytes=self.budget.headroom_bytes,
                           queue_with_headroom_maximum_bytes=self.budget.maximum+self.budget.headroom_bytes,
                           per_channel_queue_maximum_bytes={str(k):v for k,v in self.budget.channel_maximum.items()},
                           per_channel_with_headroom_maximum_bytes={str(k):v+self.budget.headroom_bytes for k,v in self.budget.channel_maximum.items()},
                           channels=[{'channel_id':c.id,'authentication':c.owner,'namespace_closed':c.namespace_closed,
                                      'meters':{k:v.summary() for k,v in c.meters.items()},'h2':c.h2.summary(),
                                      'parent_eof':c.parent_eof, 'upload_drained':c.upload_drained,
                                      'finish_frontier':c.finish_frontier,'seal_frontier':c.seal_frontier} for c in self.channels.values()], failures=list(self.failures))
            receipt['qualified'] = (not self.failures and bool(self.owner_binding) and self.denied == 0 and self.budget.total == 0
                                    and self.drain is not None and self.drain['seal_qualified']
                                    and self.drain['completed_monotonic_s'] is not None)
            binding = save(Path(self.fixture.evidence) / 'codehost-owner-bridge-v3.json', receipt)
            self.ledger.emit('closed', qualified=receipt['qualified'], failures=list(self.failures),
                             accepted=len(self.channels), denied=self.denied, attempts=self.attempts, receipt=binding)
        if self.failures: raise RuntimeError('Codehost v3 failed: ' + '; '.join(self.failures))
        return outcome


def read_json(path):
    return json.loads(Path(path).read_text())


async def run(fixture, callback):
    return await Bridge(fixture).run(callback)
