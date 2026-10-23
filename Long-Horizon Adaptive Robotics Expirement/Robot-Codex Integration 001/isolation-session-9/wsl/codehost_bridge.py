"""Trusted, short-lived loopback byte bridge to one isolated gRPC code host.

The loopback client is the trusted Windows app-server. Untrusted execution has
no route to Windows loopback. This endpoint does not authenticate other trusted
same-user Windows processes; it is not a multi-user production service.
"""
import asyncio
import json
import subprocess
import uuid
import socket
import struct
from urllib.parse import urlsplit


async def probe(url, fixture, reset=False):
    """HTTP/2 ping after an idle interval proves the raw gRPC transport stays open."""
    reader, writer = await asyncio.open_connection('127.0.0.1', urlsplit(url).port)
    try:
        writer.write(b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n' + b'\x00\x00\x00\x04\x00\x00\x00\x00\x00')
        await writer.drain()
        frames = []
        async def frame():
            header = await asyncio.wait_for(reader.readexactly(9), 10)
            length = int.from_bytes(header[:3], 'big')
            if length > 65536: raise RuntimeError('Oversized H2 probe frame')
            payload = await asyncio.wait_for(reader.readexactly(length), 10)
            frames.append({'type': header[3], 'flags': header[4], 'bytes': length})
            return header[3], header[4], payload
        kind, flags, payload = await frame()
        if kind != 4: raise RuntimeError('Expected HTTP/2 SETTINGS')
        writer.write(b'\x00\x00\x00\x04\x01\x00\x00\x00\x00')
        await writer.drain()
        await asyncio.sleep(1)
        marker = b'S9CANARY'
        writer.write(b'\x00\x00\x08\x06\x00\x00\x00\x00\x00' + marker)
        await writer.drain()
        for _ in range(8):
            kind, flags, payload = await frame()
            if kind == 6 and flags == 1 and payload == marker:
                (fixture.evidence / 'codehost-http2-probe.json').write_text(json.dumps({'qualified': True, 'idle_seconds': 1, 'frames': frames, 'intentional_close': 'abort' if reset else 'graceful'}, indent=2) + '\n')
                return
        raise RuntimeError('HTTP/2 ping acknowledgement missing')
    finally:
        if reset:
            fixture.client_finishing.set()
            # Windows linger=0 forces an actual TCP RST, rather than an abort
            # that this stack may deliver to the server as ordinary EOF.
            writer.get_extra_info('socket').setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('HH', 1, 0))
            writer.transport.abort()
        writer.close()
        await writer.wait_closed()


async def run(fixture, callback):
    active = False
    tasks = set()
    failures = []
    async def handle(reader, writer):
        nonlocal active
        current = asyncio.current_task()
        tasks.add(current)
        if active:
            writer.close()
            await writer.wait_closed()
            tasks.discard(current)
            return
        active = True
        fixture.codehost_connection_count = getattr(fixture, 'codehost_connection_count', 0) + 1
        prefix = 'codehost-' + str(fixture.codehost_connection_count)
        identity = fixture.run + '/codehost-' + uuid.uuid4().hex + '.json'
        try:
            process = await asyncio.create_subprocess_exec(*fixture.argv('codehost'), '--identity-file', identity,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        except Exception as error:
            failures.append('codehost process launch: ' + str(error))
            fixture.abort_event.set()
            active = False
            writer.close()
            await writer.wait_closed()
            return
        counts = {'to_host': 0, 'from_host': 0}
        async def upload():
            while data := await reader.read(65536):
                counts['to_host'] += len(data)
                process.stdin.write(data)
                await process.stdin.drain()
        async def download():
            while data := await process.stdout.read(65536):
                counts['from_host'] += len(data)
                writer.write(data)
                await writer.drain()
        async def errors():
            content = bytearray()
            while data := await process.stderr.read(65536):
                content.extend(data[:max(0, 1048576 - len(content))])
            return fixture.redact(content.decode(errors='replace'))
        pumps = [asyncio.create_task(upload()), asyncio.create_task(download())]
        err = asyncio.create_task(errors())
        try:
            await asyncio.wait(pumps, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in pumps: task.cancel()
            results = await asyncio.gather(*pumps, return_exceptions=True)
            expected_reset = lambda value: isinstance(value, ConnectionResetError) and fixture.client_finishing.is_set()
            counts['expected_client_shutdown_resets'] = sum(expected_reset(value) for value in results)
            counts['pump_errors'] = [str(value) for value in results if isinstance(value, Exception) and not expected_reset(value)]
            failures.extend(counts['pump_errors'])
            if counts['pump_errors'] or process.returncode not in (None, 0):
                fixture.abort_event.set()
            process.stdin.close()
            from retirement import retire
            try:
                await retire(process, identity, fixture.evidence / (prefix + '-retirement.json'))
            except Exception as error:
                failures.append('codehost retirement: ' + str(error))
                fixture.abort_event.set()
                raise
            try:
                errors_text = await asyncio.wait_for(err, 3)
            except asyncio.TimeoutError:
                err.cancel()
                errors_text = 'stderr drain exceeded bound'
            (fixture.evidence / (prefix + '-stderr.txt')).write_text(errors_text, encoding='utf-8')
            counts['exit_code'] = process.returncode
            (fixture.evidence / (prefix + '-bridge.json')).write_text(json.dumps(counts, indent=2) + '\n')
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionResetError:
                if not fixture.client_finishing.is_set():
                    raise
            active = False
    async with await asyncio.start_server(handle, '127.0.0.1', 0) as server:
        try:
            outcome = await callback('http://127.0.0.1:' + str(server.sockets[0].getsockname()[1]))
        finally:
            server.close()
            await server.wait_closed()
            if tasks:
                done, pending = await asyncio.wait(tasks, timeout=25)
                for task in pending: task.cancel()
                results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 25)
                failures.extend(str(value) for value in results if isinstance(value, BaseException))
    if failures:
        raise RuntimeError('Code-host bridge failed: ' + '; '.join(failures))
    return outcome
