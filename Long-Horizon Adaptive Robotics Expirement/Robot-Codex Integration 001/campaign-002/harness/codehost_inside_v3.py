"""One isolated code host, bounded opaque native transport channels.

The fixed gateway classes are copied verbatim from v2. No tool replay.
"""
import json
import hashlib
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import codehost_mux_protocol as mux
import native_cleanup_protocol as cleanup

PREFIX = 'RCI_CODEHOST_V3 '
MAX_RECORDS = 16384
MAX_CHILD_DIAGNOSTIC_BYTES = 1024 * 1024
MAX_METADATA_BYTES = 1024 * 1024
DRAIN_TIMEOUT = 2


def sources():
    paths = {'codehost_inside_v3.py': Path(__file__),
             'codehost_mux_protocol.py': Path(mux.__file__),
             'native_cleanup_protocol.py': Path(cleanup.__file__)}
    return {name: {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes':path.stat().st_size}
            for name,path in paths.items()}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.forward('GET')

    def do_POST(self):
        self.forward('POST')

    def forward(self, method):
        # An IPC socket to a fixed-purpose broker, never a general network proxy.
        try:
            self.connection.settimeout(8)
            length = int(self.headers.get('Content-Length', '0'))
            if (not 0 <= length <= MAX_BODY or self.headers.get('Transfer-Encoding') or
                    len(self.headers.get_all('Content-Length', [])) > 1 or
                    len(self.headers.get_all('X-Robot-Capability', [])) > 1):
                raise ValueError('body limit')
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError('truncated request')
            request = {'method': method, 'path': self.path,
                       'capability': self.headers.get('X-Robot-Capability', ''),
                       'body': raw.decode('utf-8')}
            validate_request(request)
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(8)
                client.connect('/gateway.sock')
                client.sendall(json.dumps(request).encode() + b'\n')
                line = client.makefile('rb').readline(MAX_RESPONSE_FRAME + 1)
                if len(line) > MAX_RESPONSE_FRAME or not line.endswith(b'\n'):
                    raise ValueError('response frame limit')
                response = validate_response(json.loads(line))
        except PermissionError:
            response = error_response(403, 'broker_route_denied')
        except (ValueError, UnicodeError):
            response = error_response(400, 'invalid_bounded_request_or_response')
        except Exception:
            response = error_response(502, 'fixed_gateway_unavailable_receipt_unknown')
        try:
            body = response['body'].encode()
            self.send_response(response['status'])
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass


class BoundedHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, *args):
        self.slots = threading.BoundedSemaphore(8)
        super().__init__(*args)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


class Metadata:
    def __init__(self, stream):
        self.stream, self.sequence, self.lock, self.bytes = stream, 0, threading.Lock(), 0

    def emit(self, kind, **fields):
        with self.lock:
            row = {'schema': 'campaign002-codehost-namespace-3', 'sequence': self.sequence + 1,
                   'wall_unix_s': time.time(), 'monotonic_s': time.monotonic(), 'kind': kind, **fields}
            raw = PREFIX + mux.canonical(row).decode() + '\n'
            if self.sequence >= MAX_RECORDS or self.bytes + len(raw.encode()) > MAX_METADATA_BYTES:
                raise RuntimeError('Namespace metadata bound exceeded')
            self.stream.write(raw); self.stream.flush()
            self.sequence += 1; self.bytes += len(raw.encode())
            return row


def diagnostic_drains(child, emit, failed, ready):
    """Hash only child diagnostics; the fixed listener announcement gates startup."""
    lock, total = threading.Lock(), [0]
    def drain(stream, name):
        count, digest, truncated, first = 0, hashlib.sha256(), False, bytearray()
        try:
            while data := os.read(stream.fileno(), 65536):
                count += len(data); digest.update(data)
                if name == 'stdout' and not ready.is_set():
                    first.extend(data[:max(0, 256-len(first))])
                    if b'\n' in first:
                        if first.split(b'\n', 1)[0] != b'http://127.0.0.1:38218':
                            raise ValueError('Native listener announcement differs')
                        ready.set()
                    elif len(first) >= 256:
                        raise ValueError('Native listener announcement bound')
                with lock:
                    total[0] += len(data)
                    if total[0] > MAX_CHILD_DIAGNOSTIC_BYTES:
                        truncated = True; failed.set()
                        if child.poll() is None: child.terminate()
            emit('child_diagnostic', stream=name, bytes=count, sha256=digest.hexdigest(), truncated=truncated)
        except BaseException:
            failed.set()
    workers = [threading.Thread(target=drain, args=(getattr(child, n), n), daemon=True)
               for n in ('stdout', 'stderr')]
    for worker in workers: worker.start()
    def finish():
        for worker in workers: worker.join(timeout=2)
        if any(worker.is_alive() for worker in workers): failed.set()
        return not any(worker.is_alive() for worker in workers)
    return finish


class Channel:
    def __init__(self, channel_id, reader, writer):
        self.id, self.reader, self.writer = channel_id, reader, writer
        self.upload, self.download = mux.ByteCounter(), mux.ByteCounter()
        self.h2, self.queue = mux.H2Witness(), asyncio.Queue()
        self.half_closed = self.closed = False
        self.download_eof = False
        self.upload_eof_h2 = self.download_eof_h2 = self.finish_frontier = None
        self.seal_frontier = None
        self.upload_drained = False
        self.upload_eof_event, self.download_eof_event = asyncio.Event(), asyncio.Event()
        self.failure = None
        self.tasks = []


class SocketStream:
    """No user-space read-ahead queue outside the explicit channel budget."""
    def __init__(self, channel):
        self.channel, self.pending = channel, None

    async def read(self, count):
        return await asyncio.get_running_loop().sock_recv(self.channel, count)

    def write(self, data):
        if self.pending is not None: raise ValueError('Overlapping socket writes')
        self.pending = data

    async def drain(self):
        if self.pending is not None:
            try: await asyncio.get_running_loop().sock_sendall(self.channel, self.pending)
            finally: self.pending = None

    def write_eof(self):
        self.channel.shutdown(socket.SHUT_WR)

    def close(self):
        self.channel.close(); self.pending = None

    async def wait_closed(self):
        pass


class Relay:
    """Injected stream endpoints permit deterministic tests without native launch."""
    def __init__(self, reader, writer, emit, child, diagnostic_failure, connect=None):
        self.reader, self.writer, self.emit, self.child = reader, writer, emit, child
        self.diagnostic_failure = diagnostic_failure
        self.connect = connect or self._connect
        self.channels = {}
        self.budget = mux.QueueBudget()
        self.output_lock = asyncio.Lock()
        self.finishing, self.failure = False, None
        self.draining = self.drain_acknowledged = False
        self.drain_started = self.drain_deadline = self.drain_acknowledged_at = self.sealed_at = None
        self.failed = asyncio.Event()
        self.frame_counts = {'incoming': 0, 'outgoing': 0}
        self.cleanup_request = self.cleanup_barrier = None

    def remaining(self):
        return None if self.drain_deadline is None else max(0,self.drain_deadline-asyncio.get_running_loop().time())

    async def bounded(self, awaitable, limit=DRAIN_TIMEOUT):
        remaining=self.remaining()
        timeout=remaining if limit is None else limit if remaining is None else min(limit,remaining)
        return await asyncio.wait_for(awaitable,timeout)

    async def _connect(self):
        # Exactly one connect per accepted channel. Startup readiness is separate.
        channel = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        channel.setblocking(False)
        try:
            await asyncio.wait_for(asyncio.get_running_loop().sock_connect(channel,('127.0.0.1',38218)), .2)
            stream = SocketStream(channel)
            return stream, stream
        except BaseException:
            channel.close(); raise

    def frame(self, direction, kind, channel, payload):
        self.frame_counts[direction] += 1
        self.emit('frame', direction=direction, frame_type=kind, channel_id=channel,
                  payload_bytes=len(payload), payload_sha256=hashlib.sha256(payload).hexdigest())

    async def send(self, kind, channel, payload=b'', account=True):
        async def send_locked():
            async with self.output_lock:
                await mux.write_frame(self.writer, kind, channel, payload)
                if account: self.frame('outgoing', kind, channel, payload)
        await self.bounded(send_locked())

    def fail(self, error):
        if self.failure is None:
            self.failure = type(error).__name__ if isinstance(error, BaseException) else str(error)
            self.emit('failure', error_type=self.failure)
        self.failed.set()

    async def upload(self, channel):
        pending = None
        try:
            while True:
                pending = await channel.queue.get()
                if pending is None:
                    try:
                        channel.writer.write_eof()
                        await self.bounded(channel.writer.drain())
                        channel.upload_drained = True
                        self.emit('channel_upload_drained', channel_id=channel.id,
                                  owner_finishing=self.draining, upload=channel.upload.summary())
                    finally:
                        channel.queue.task_done()
                    pending = None
                    return
                channel.writer.write(pending)
                await self.bounded(channel.writer.drain())
                channel.upload.add(pending)
                self.budget.release(channel.id, len(pending))
                channel.queue.task_done(); pending = None
        except asyncio.CancelledError:
            raise
        except BaseException as error:
            channel.failure = type(error).__name__; self.fail(error)
        finally:
            if pending is not None:
                self.budget.release(channel.id, len(pending)); channel.queue.task_done()

    async def download(self, channel):
        reserved = 0
        try:
            while True:
                self.budget.reserve(channel.id,mux.MAX_FRAME_BYTES); reserved=mux.MAX_FRAME_BYTES
                data = await channel.reader.read(mux.MAX_FRAME_BYTES)
                self.budget.release(channel.id,reserved-len(data)); reserved=len(data)
                if not data: break
                channel.h2.feed('download', data)
                await self.send(mux.DATA, channel.id, data)
                channel.download.add(data)
                self.budget.release(channel.id, reserved); reserved = 0
            channel.download_eof = True
            channel.download_eof_event.set()
            channel.download_eof_h2 = channel.h2.summary()
            self.emit('channel_eof', channel_id=channel.id, direction='download',
                      owner_finishing=self.draining, h2=channel.download_eof_h2)
            if not self.draining:
                channel.h2.idle_eof()
                # Host EOF cannot stand in for the authenticated client's EOF.
                await self.bounded(channel.upload_eof_event.wait())
                await self.bounded(channel.queue.join())
                if not self.draining:
                    await self.close_channel(channel, 'clean_idle_eof')
        except asyncio.CancelledError:
            raise
        except BaseException as error:
            channel.failure = type(error).__name__; self.fail(error)
        finally:
            if reserved: self.budget.release(channel.id, reserved)

    async def close_channel(self, channel, reason):
        if channel.closed: return
        channel.closed = True
        try:
            await self.bounded(self.output_lock.acquire())
            self.output_lock.release()
        except Exception as error:
            channel.failure = type(error).__name__; self.fail(error)
        current = asyncio.current_task()
        for task in channel.tasks:
            if task is not current and not task.done(): task.cancel()
        await asyncio.gather(*(t for t in channel.tasks if t is not current), return_exceptions=True)
        channel.writer.close()
        try:
            await self.bounded(channel.writer.wait_closed())
        except Exception as error:
            channel.failure = type(error).__name__; self.fail(error)
        while not channel.queue.empty():
            item = channel.queue.get_nowait()
            if item is not None: self.budget.release(channel.id, len(item))
            channel.queue.task_done()
        h2 = channel.h2.summary()
        if reason == 'owner_finish':
            front = channel.finish_frontier
            try: channel.h2.validate_reset_scope(front)
            except ValueError:
                channel.failure = 'UnexplainedHttp2ResetOrError'; self.fail(channel.failure)
            if (front is None or front['error']
                    or not self.drain_acknowledged or not self.finishing
                    or not channel.half_closed or not channel.upload_drained or not channel.download_eof
                    or channel.seal_frontier is None or h2['last_stream_id'] != front['last_stream_id']
                    or h2['error'] or not all(h2[n] for n in ('preface_complete','settings_complete','frames_complete','headers_complete'))):
                channel.failure = 'UnexplainedHttp2ResetOrError'
                self.fail(channel.failure)
        value = {'schema': 'campaign002-codehost-channel-3', 'channel_id': channel.id,
                 'qualified': reason in ('clean_idle_eof','owner_finish') and channel.failure is None and self.failure is None,
                 'reason': reason if channel.failure is None and self.failure is None else 'error',
                 'upload': channel.upload.summary(), 'download': channel.download.summary(),
                 'h2': h2, 'finish_frontier': channel.finish_frontier,
                 'seal_frontier': channel.seal_frontier, 'upload_eof': channel.half_closed,
                 'upload_drained': channel.upload_drained, 'download_eof': channel.download_eof,
                 'upload_eof_h2': channel.upload_eof_h2, 'download_eof_h2': channel.download_eof_h2,
                 'error_type': channel.failure or self.failure}
        self.emit('channel_closed', receipt=value)
        await self.send(mux.CLOSED, channel.id, mux.canonical(value))

    async def accept(self, kind, channel_id, payload):
        self.frame('incoming', kind, channel_id, payload)
        if kind == mux.CLEANUP_BEGIN:
            if self.cleanup_request is not None or self.draining or self.finishing or self.failure:
                raise ValueError('Unavailable native cleanup phase')
            value = mux.metadata(payload)
            if (payload != cleanup.canonical(value) or set(value) != {'schema','request','parent_record_sha256'}
                    or value['schema'] != 'campaign002-native-cleanup-begin-1'
                    or not cleanup.digest(value['parent_record_sha256'])):
                raise ValueError('Invalid native cleanup BEGIN')
            request = cleanup.validate_request(value['request'])
            self.cleanup_request = request
            # A namespace monotonic clock is never compared to its Windows peer.
            # Preserve the request's bounded duration for all local barrier work.
            local_bound = request['graceful_deadline_monotonic_s']-request['start_monotonic_s']
            async with asyncio.timeout(local_bound):
                frontiers = []
                for channel in self.channels.values():
                    frontier = channel.h2.summary() if channel.half_closed else channel.h2.begin_cleanup(request['nonce'])
                    frontiers.append({'channel_id':channel.id,'already_closed':channel.closed,
                                      'upload_eof':channel.half_closed,'h2':frontier})
                await asyncio.gather(*(c.queue.join() for c in self.channels.values() if not c.closed))
                if self.failure: raise ValueError('Upload failed during native cleanup barrier')
                request_sha = cleanup.sha(cleanup.canonical(request))
                record = self.emit('native_cleanup_begin',nonce=request['nonce'],request_sha256=request_sha,
                                   parent_record_sha256=value['parent_record_sha256'],child_pid=self.child.pid,
                                   channels=frontiers)
                ack = cleanup.canonical({'schema':'campaign002-native-cleanup-ack-1','nonce':request['nonce'],
                    'request_sha256':request_sha,'parent_record_sha256':value['parent_record_sha256'],
                    'namespace_record':record})
                await self.send(mux.CLEANUP_ACK,0,ack)
                self.cleanup_barrier = {'nonce':request['nonce'],'request_sha256':request_sha,
                    'parent_record_sha256':value['parent_record_sha256'],
                    'namespace_record_sha256':cleanup.sha(cleanup.canonical(record)),
                    'begin_payload_sha256':cleanup.sha(payload),'ack_payload_sha256':cleanup.sha(ack)}
            return True
        if kind == mux.DRAIN_BEGIN:
            if self.draining or self.finishing: raise ValueError('Duplicate owner drain')
            self.draining = True
            self.drain_started = asyncio.get_running_loop().time()
            self.drain_deadline = self.drain_started + mux.OWNER_DRAIN_TIMEOUT
            self.emit('owner_drain_begin', channels=len(self.channels), bound_s=mux.OWNER_DRAIN_TIMEOUT,
                      start_monotonic_s=self.drain_started, deadline_monotonic_s=self.drain_deadline)
            for channel in self.channels.values():
                if channel.closed:
                    frontier = channel.h2.summary()
                else:
                    frontier = channel.h2.begin_retirement()
                    channel.finish_frontier = frontier
                self.emit('channel_finish_frontier', channel_id=channel.id, h2=frontier,
                          already_closed=channel.closed)
            await self.bounded(asyncio.gather(*(c.queue.join() for c in self.channels.values() if not c.closed)),None)
            await self.send(mux.DRAIN_ACK,0)
            self.drain_acknowledged = True
            self.drain_acknowledged_at = asyncio.get_running_loop().time()
            self.emit('owner_drain_ack', channels=len(self.channels))
            return True
        if kind == mux.FINISH:
            if self.finishing: raise ValueError('Duplicate owner finish')
            if not self.draining or not self.drain_acknowledged: raise ValueError('Owner finish before drain acknowledgment')
            if any(not c.half_closed for c in self.channels.values()): raise ValueError('Owner finish before genuine upload EOF')
            await self.bounded(asyncio.gather(*(c.queue.join() for c in self.channels.values() if not c.closed)),None)
            if any(not c.upload_drained for c in self.channels.values()): raise ValueError('Owner finish before upload drained')
            for channel in self.channels.values(): channel.h2.upload_eof()
            self.finishing = True
            self.sealed_at = asyncio.get_running_loop().time()
            for channel in self.channels.values():
                if not channel.closed: channel.seal_frontier = channel.h2.summary()
            self.emit('owner_finish', channels=len(self.channels), seal_qualified=True, seal_error_code=None)
            return False
        if self.finishing: raise ValueError('Frame after owner finish')
        if kind == mux.OPEN:
            if self.draining: raise ValueError('Channel after owner drain')
            if channel_id != len(self.channels) + 1 or len(self.channels) >= mux.MAX_CONNECTIONS:
                raise ValueError('Channel allocation/reuse/bound')
            reader, writer = await self.connect()
            channel = Channel(channel_id, reader, writer)
            self.channels[channel_id] = channel
            self.emit('channel_open', channel_id=channel_id, child_pid=self.child.pid)
            if self.cleanup_request is not None:
                frontier = channel.h2.begin_cleanup(self.cleanup_request['nonce'])
                self.emit('native_cleanup_channel',channel_id=channel_id,nonce=self.cleanup_request['nonce'],
                          request_sha256=cleanup.sha(cleanup.canonical(self.cleanup_request)),h2=frontier)
            await self.send(mux.OPENED, channel_id)
            channel.tasks = [asyncio.create_task(self.upload(channel)), asyncio.create_task(self.download(channel))]
            return True
        channel = self.channels.get(channel_id)
        if channel is None or channel.closed: raise ValueError('Unavailable channel')
        if kind == mux.ERROR:
            value = mux.metadata(payload)
            self.fail('ParentChannelError'); channel.failure = 'ParentChannelError'
        elif kind == mux.DATA:
            if channel.half_closed: raise ValueError('DATA after half-close')
            channel.h2.feed('upload', payload)
            self.budget.reserve(channel_id, len(payload))
            channel.queue.put_nowait(payload)
        elif kind == mux.HALF_CLOSE:
            if channel.half_closed: raise ValueError('Duplicate half-close')
            channel.upload_eof_h2 = channel.h2.summary()
            self.emit('channel_eof', channel_id=channel_id, direction='upload',
                      owner_finishing=self.draining, h2=channel.upload_eof_h2)
            channel.half_closed = True; channel.upload_eof_event.set(); channel.queue.put_nowait(None)
            if self.draining: channel.h2.upload_eof()
            else: channel.h2.idle_eof()
        else:
            raise ValueError('Invalid parent frame direction')
        return True

    async def monitor(self):
        while not self.finishing:
            if self.child.poll() is not None or self.diagnostic_failure.is_set():
                self.fail('ChildOrDiagnosticFailure'); return
            await asyncio.sleep(.02)

    async def run(self):
        monitor = asyncio.create_task(self.monitor())
        pending = None
        failed = asyncio.create_task(self.failed.wait())
        stdin_eof = False
        try:
            while not self.finishing:
                pending = asyncio.create_task(mux.read_frame(self.reader))
                done, _ = await asyncio.wait((pending, failed), return_when=asyncio.FIRST_COMPLETED,timeout=self.remaining())
                if not done: raise TimeoutError('Owner drain deadline')
                if failed in done: raise RuntimeError('Relay failure')
                frame = pending.result(); pending = None
                if frame is None: raise ValueError('Owner EOF without FINISH')
                if not await self.accept(*frame):
                    if await self.bounded(mux.read_frame(self.reader), .5) is not None:
                        raise ValueError('Frame after owner FINISH')
                    stdin_eof = True
                    break
        except BaseException as error:
            self.fail(error)
        finally:
            for task in (monitor, pending, failed):
                if task is not None: task.cancel()
            await asyncio.gather(*(t for t in (monitor,pending,failed) if t is not None), return_exceptions=True)
            live = [c for c in self.channels.values() if not c.closed]
            if self.finishing and not self.failure:
                try:
                    await self.bounded(asyncio.gather(*(c.queue.join() for c in live)),None)
                    await self.bounded(asyncio.gather(*(c.tasks[1] for c in live)),None)
                    if any(not c.download_eof for c in live): raise ValueError('Missing host download EOF')
                except Exception as error:
                    self.fail(error)
            async def close(channel):
                try:
                    await self.close_channel(channel, 'owner_finish' if self.finishing else 'error')
                except Exception as error:
                    self.fail(error)
            await asyncio.gather(*(close(c) for c in live))
        elapsed = None if self.drain_started is None else asyncio.get_running_loop().time()-self.drain_started
        drain_qualified = (self.finishing and self.drain_acknowledged and self.failure is None
                           and elapsed is not None and elapsed <= mux.OWNER_DRAIN_TIMEOUT)
        return {'cleanup_barrier':self.cleanup_barrier,
                'owner_finish_received': self.finishing, 'channel_count': len(self.channels),
                'owner_drain_received': self.draining, 'owner_drain_acknowledged': self.drain_acknowledged,
                'owner_drain_timeout_s': mux.OWNER_DRAIN_TIMEOUT,
                'owner_drain_elapsed_s': elapsed, 'drain_qualified': drain_qualified,
                'drain_error_code': None if drain_qualified else 'owner_drain_unqualified',
                'channels_closed': sum(c.closed for c in self.channels.values()),
                'stdin_eof': stdin_eof, 'owner_input_wait_bound_s': .5,
                'error_type': self.failure, 'queue_bytes_at_close': self.budget.total,
                'queue_headroom_bytes': self.budget.headroom_bytes,
                'per_channel_queue_maximum_bytes': dict(self.budget.channel_maximum),
                'queue_high_water_bytes': self.budget.maximum, 'frame_counts': dict(self.frame_counts)}


class FDReader:
    def __init__(self, descriptor):
        self.descriptor = descriptor
        os.set_blocking(descriptor,False)

    async def readexactly(self, count):
        value=bytearray()
        loop=asyncio.get_running_loop()
        while len(value)<count:
            try:
                part=os.read(self.descriptor,count-len(value))
                if not part:raise asyncio.IncompleteReadError(bytes(value),count)
                value.extend(part)
            except BlockingIOError:
                ready=loop.create_future()
                def readable():
                    if not ready.done():ready.set_result(None)
                loop.add_reader(self.descriptor,readable)
                try:await ready
                finally:loop.remove_reader(self.descriptor)
        return bytes(value)


class FDWriter:
    def __init__(self,descriptor):
        self.descriptor,self.pending=descriptor,None
        os.set_blocking(descriptor,False)

    def write(self,value):
        if self.pending is not None:raise ValueError('Overlapping frame writes')
        self.pending=memoryview(value)

    async def drain(self):
        loop=asyncio.get_running_loop()
        try:
            while self.pending:
                try:
                    count=os.write(self.descriptor,self.pending)
                    if count<=0:raise OSError('Framing output made no progress')
                    self.pending=self.pending[count:]
                except BlockingIOError:
                    ready=loop.create_future()
                    def writable():
                        if not ready.done():ready.set_result(None)
                    loop.add_writer(self.descriptor,writable)
                    try:await ready
                    finally:loop.remove_writer(self.descriptor)
        finally:self.pending=None


async def stdio_streams():
    return FDReader(sys.stdin.fileno()),FDWriter(sys.stdout.fileno())


async def operate(child, metadata, failed, ready, finish_diagnostics):
    relay = None
    error_type = None
    result = {'owner_finish_received': False, 'channel_count': 0, 'channels_closed': 0,
              'owner_drain_received': False, 'owner_drain_acknowledged': False,
              'owner_drain_timeout_s':mux.OWNER_DRAIN_TIMEOUT, 'owner_drain_elapsed_s':None,
              'drain_qualified':False, 'drain_error_code':'owner_drain_not_started',
              'stdin_eof': False, 'owner_input_wait_bound_s': .5,
              'queue_headroom_bytes': mux.FRAME_HEADROOM_BYTES, 'per_channel_queue_maximum_bytes':{},
              'queue_bytes_at_close': 0, 'queue_high_water_bytes': 0, 'frame_counts': {'incoming':0,'outgoing':0}}
    reader = writer = None
    try:
        if not await asyncio.to_thread(ready.wait, 10) or child.poll() is not None or failed.is_set():
            raise RuntimeError('Private code host startup failed')
        reader, writer = await stdio_streams()
        relay = Relay(reader, writer, metadata.emit, child, failed)
        value = {'schema':'campaign002-codehost-owner-ready-3', 'child_pid':child.pid,
                 'max_connections':mux.MAX_CONNECTIONS, 'max_frame_bytes':mux.MAX_FRAME_BYTES,
                 'per_channel_queue_bytes':mux.PER_CHANNEL_QUEUE_BYTES,
                 'aggregate_queue_bytes':mux.AGGREGATE_QUEUE_BYTES, 'sources':sources()}
        metadata.emit('ready', receipt=value)
        await relay.send(mux.READY, 0, mux.canonical(value))
        result = await relay.run()
        error_type = result.pop('error_type')
    except BaseException as error:
        error_type = type(error).__name__
        metadata.emit('failure', error_type=error_type)
    before = child.poll()
    terminate_sent = kill_sent = False
    if before is None:
        terminate_sent = True; child.terminate()
    try:
        code = await asyncio.to_thread(child.wait, timeout=3)
    except subprocess.TimeoutExpired:
        kill_sent = True; child.kill()
        code = await asyncio.to_thread(child.wait, timeout=3)
    diagnostics_complete = await asyncio.to_thread(finish_diagnostics)
    qualified = (result['drain_qualified'] and result['owner_finish_received'] and result['stdin_eof'] and error_type is None and not failed.is_set()
                 and not kill_sent and diagnostics_complete and result['queue_bytes_at_close'] == 0
                 and result['channel_count'] == result['channels_closed']
                 and before in (None, 0) and (code == 0 or terminate_sent and code == -15))
    final = metadata.emit('closed', qualified=qualified, reason='owner_finish' if qualified else 'error',
        child_pid=child.pid, child_exit_before_cleanup=before, child_exit_code=code,
        terminate_sent=terminate_sent, kill_sent=kill_sent, diagnostic_streams_complete=diagnostics_complete,
        error_type=error_type, sources=sources(), **result)
    if relay is not None:
        await relay.send(mux.FINISHED, 0, mux.canonical(final), account=False)
    return 0 if qualified else 1


def main():
    if sys.argv[1:] != ['codehost']: raise SystemExit('Additive inside supports codehost mode only')
    for descriptor in os.listdir('/proc/self/fd'):
        try: target = os.readlink('/proc/self/fd/' + descriptor)
        except FileNotFoundError: continue
        if target.endswith('.bwrap-info.json'): raise SystemExit('Outer metadata descriptor leaked into guest')
    import gateway_policy
    for name in ('MAX_BODY','MAX_RESPONSE_FRAME','validate_request','validate_response','error_response'):
        globals()[name] = getattr(gateway_policy, name)
    server = BoundedHTTPServer(('127.0.0.1',38117), Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    metadata = Metadata(sys.stderr)
    metadata.emit('open', sources=sources(), max_records=MAX_RECORDS, max_metadata_bytes=MAX_METADATA_BYTES)
    child = None
    finish_diagnostics = None
    try:
        child = subprocess.Popen(['/code-mode-host','--listen','grpc://127.0.0.1:38218'],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        metadata.emit('child_started', child_pid=child.pid)
        failed, ready = threading.Event(), threading.Event()
        finish_diagnostics = diagnostic_drains(child, metadata.emit, failed, ready)
        return asyncio.run(operate(child,metadata,failed,ready,finish_diagnostics))
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try: child.wait(timeout=3)
            except subprocess.TimeoutExpired: child.kill(); child.wait(timeout=3)
        if finish_diagnostics is not None: finish_diagnostics()
        server.shutdown(); server.server_close()


if __name__ == '__main__':
    raise SystemExit(main())
