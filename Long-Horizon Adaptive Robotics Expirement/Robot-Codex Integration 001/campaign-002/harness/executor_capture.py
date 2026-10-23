"""Bounded trusted executor RPC capture; no guest or gateway capability changes.

Every outbound message is retained before forwarding and receives a separate
delivery record after websocket.send returns. Capture errors stop the invocation.
The assessment must distinguish bytes delivered to the app server from the app
server's possibly shorter model/UI projection.
"""
from __future__ import annotations
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

MAX_CAPTURE_BYTES = 64 * 1024 * 1024  # Combined connections, per invocation.


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class Capture:
    def __init__(self, fixture, connection_id):
        self.fixture = fixture
        self.connection_id = str(connection_id)
        self.path = Path(fixture.evidence) / ('executor-' + self.connection_id + '-capture.jsonl')
        self.path.touch(exist_ok=False)
        self.sequence = 0
        self.previous = None

    def append(self, kind, message=None, **fields):
        record = {'schema': 'campaign002-executor-capture-1', 'connection_id': self.connection_id,
                  'sequence': self.sequence + 1, 'previous_sha256': self.previous,
                  'wall_unix_s': time.time(), 'kind': kind, **fields}
        if message is not None:
            # Base64 would otherwise conceal a capability from textual redaction.
            retained = json.loads(json.dumps(message))
            blobs = []
            def clean(value, path=()):
                if isinstance(value, dict):
                    for key, item in list(value.items()):
                        if key in ('chunk', 'dataBase64') and isinstance(item, str):
                            raw = base64.b64decode(item, validate=True)
                            safe = raw
                            for token in self.fixture.tokens:
                                if token:
                                    safe = safe.replace(token.encode(), b'[REDACTED_EPHEMERAL_CAPABILITY]')
                            value[key] = base64.b64encode(safe).decode()
                            blobs.append({'path': list(path + (key,)), 'raw_sha256': digest(raw),
                                          'retained_sha256': digest(safe), 'raw_bytes': len(raw),
                                          'retained_bytes': len(safe)})
                        else:
                            clean(item, path + (key,))
                elif isinstance(value, list):
                    for index, item in enumerate(value):
                        clean(item, path + (index,))
            clean(retained)
            retained = json.loads(self.fixture.redact(json.dumps(retained)))
            record.update(message=retained, original_message_sha256=digest(canonical(message)),
                          retained_message_sha256=digest(canonical(retained)), blobs=blobs)
        record['record_sha256'] = digest(canonical(record))
        raw = canonical(record) + b'\n'
        used = getattr(self.fixture, '_executor_capture_bytes', 0)
        if used + len(raw) > MAX_CAPTURE_BYTES:
            self.fixture.abort_event.set()
            raise RuntimeError('Trusted executor capture exceeded 64MiB invocation bound')
        try:
            with self.path.open('ab') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            self.fixture.abort_event.set()
            raise
        self.fixture._executor_capture_bytes = used + len(raw)
        self.sequence += 1
        self.previous = record['record_sha256']
        return self.sequence


async def bridge_executor(fixture, ready_callback):
    """Original single-owner bridge/lifecycle with additive durable RPC capture."""
    from websockets.asyncio.server import serve
    from websockets.exceptions import ConnectionClosed
    from http import HTTPStatus
    from retirement import retire
    active, connection_count, failures = False, 0, []
    secret_path = '/executor/' + uuid.uuid4().hex

    async def authorize(connection, request):
        if request.path != secret_path or active:
            return connection.respond(HTTPStatus.FORBIDDEN, 'Unavailable')

    async def handler(websocket):
        nonlocal active, connection_count
        if active:
            await websocket.close(code=1008)
            return
        active = True
        fixture.bridge_idle.clear()
        connection_count += 1
        connection_id = str(connection_count)
        identity = fixture.run + '/executor-' + connection_id + '.json'
        capture = None
        try:
            capture = Capture(fixture, connection_id)
            capture.append('open')
            process = await asyncio.create_subprocess_exec(*fixture.argv('executor'), '--identity-file', identity,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                limit=16 * 1024 * 1024 + 1)
        except Exception as error:
            fixture.abort_event.set()
            failures.append(str(error))
            active = False
            fixture.bridge_idle.set()
            raise

        async def inbound():
            async for message in websocket:
                request = json.loads(message)
                capture.append('request', request)
                with (fixture.evidence / ('executor-' + connection_id + '-requests.jsonl')).open('a', encoding='utf-8') as log:
                    log.write(fixture.redact(json.dumps(request)) + '\n')
                process.stdin.write(message.encode() + b'\n')
                await process.stdin.drain()

        async def outbound():
            while line := await process.stdout.readline():
                message = json.loads(line)
                sequence = capture.append('response', message)
                await websocket.send(line.decode().rstrip('\r\n'))
                capture.append('delivered', response_sequence=sequence)

        async def errors():
            content, total = bytearray(), 0
            while chunk := await process.stderr.read(65536):
                total += len(chunk)
                content.extend(chunk[:max(0, 1024 * 1024 - len(content))])
            (fixture.evidence / ('executor-' + connection_id + '-stderr.txt')).write_text(
                fixture.redact(content.decode(errors='replace')), encoding='utf-8')
            return total

        def write(name, value):
            with (fixture.evidence / name).open('w', encoding='utf-8') as stream:
                json.dump(value, stream, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())

        tasks = [asyncio.create_task(inbound()), asyncio.create_task(outbound())]
        errors_task = asyncio.create_task(errors())
        results = []
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            results = [{'cancelled': task.cancelled(),
                        'exception': repr(task.exception()) if not task.cancelled() else None} for task in done]
            write('bridge-' + connection_id + '-task-results.json', results)
            for task in done:
                if not task.cancelled() and task.exception() is not None:
                    # The original bridge retires on client disconnect, including
                    # native app-server shutdown without a websocket close frame.
                    # Preserve that lifecycle; incomplete process/delivery records
                    # remain unverified by the independent reader.
                    if not isinstance(task.exception(), ConnectionClosed):
                        fixture.abort_event.set()
                        failures.append('executor forwarding/capture: ' + repr(task.exception()))
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            process.stdin.close()
            try:
                await retire(process, identity, fixture.evidence / ('executor-' + connection_id + '-retirement.json'))
            except Exception as error:
                failures.append('executor retirement: ' + str(error))
                fixture.abort_event.set()
                raise
            finally:
                try:
                    stderr_bytes = await asyncio.wait_for(errors_task, 3)
                except asyncio.TimeoutError:
                    errors_task.cancel()
                    stderr_bytes = None
                write('executor-' + connection_id + '-exit.json', {'exit_code': process.returncode, 'stderr_bytes': stderr_bytes})
                try:
                    capture.append('closed', failures=list(failures), transport_end=results)
                finally:
                    active = False
                    fixture.bridge_idle.set()

    async with serve(handler, '127.0.0.1', 0, max_size=16 * 1024 * 1024, origins=[None], process_request=authorize) as server:
        url = 'ws://127.0.0.1:' + str(server.sockets[0].getsockname()[1]) + secret_path
        await ready_callback(url)
    if failures:
        raise RuntimeError('; '.join(failures))
