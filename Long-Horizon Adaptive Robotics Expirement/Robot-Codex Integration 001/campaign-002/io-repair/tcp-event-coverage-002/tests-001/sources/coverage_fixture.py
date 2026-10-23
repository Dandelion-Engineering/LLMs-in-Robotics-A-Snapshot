"""Two bounded synthetic TCP closure controls; never starts tracing or a model."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import time

REQUEST = b'Campaign002 trace coverage synthetic request only.\n'
RESPONSE = b'Synthetic reply; no model or credentials.\n'


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


async def exact(loop, sock, count):
    parts = bytearray()
    while len(parts) < count:
        part = await loop.sock_recv(sock, count - len(parts))
        if not part: raise ValueError('premature synthetic EOF')
        parts.extend(part)
    return bytes(parts)


async def run(output, immediate):
    loop = asyncio.get_running_loop()
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    listener.setblocking(False); listener.bind(('127.0.0.1', 0)); listener.listen(2)
    address = listener.getsockname()
    ready = {'schema': 'campaign002-tcp-trace-coverage-ready-1', 'pid': os.getpid(),
        'address': address[0], 'port': address[1], 'trace_started_by_fixture': False,
        'gate': str(output / 'release.json'), 'fixture_deadline_monotonic_s': time.monotonic() + 60,
        'scope': 'Two synthetic connections only; no model, host simulation, credential or security setting.'}
    save(output / 'ready.json', ready)
    print(json.dumps(ready), flush=True)
    rows = []
    try:
        if not immediate:
            while not (output / 'release.json').is_file():
                if time.monotonic() >= ready['fixture_deadline_monotonic_s']:
                    raise TimeoutError('Trace coverage gate not released within 60 seconds')
                await asyncio.sleep(.025)
            assert json.loads((output / 'release.json').read_bytes()) == {'release': True}
        for mode in ('graceful_fin', 'deliberate_rst'):
            async def peer():
                client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client.setblocking(False)
                try:
                    await loop.sock_connect(client, address)
                    await loop.sock_sendall(client, REQUEST)
                    assert await exact(loop, client, len(RESPONSE)) == RESPONSE
                    event = time.perf_counter_ns()
                    if mode == 'graceful_fin':
                        client.shutdown(socket.SHUT_WR)
                        assert await loop.sock_recv(client, 1) == b''
                    else:
                        client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('hh', 1, 0))
                        client.close()
                    return event
                finally:
                    client.close()
            task = asyncio.create_task(peer())
            accepted = None
            try:
                accepted, remote = await loop.sock_accept(listener)
                accepted.setblocking(False)
                assert await exact(loop, accepted, len(REQUEST)) == REQUEST
                await loop.sock_sendall(accepted, RESPONSE)
                error = None
                try:
                    trailing = await loop.sock_recv(accepted, 1)
                    received_eof = trailing == b''
                except OSError as exc:
                    received_eof = False
                    error = {'type': type(exc).__name__, 'errno': exc.errno, 'winerror': getattr(exc, 'winerror', None)}
                observed = time.perf_counter_ns()
                if mode == 'graceful_fin':
                    assert received_eof and error is None
                    accepted.shutdown(socket.SHUT_WR)
                else:
                    assert not received_eof and error is not None
                sent = await task
                rows.append({'case': mode, 'client_port': remote[1], 'server_port': address[1],
                    'close_requested_perf_counter_ns': sent, 'server_observed_perf_counter_ns': observed,
                    'genuine_read_eof': received_eof, 'error': error, 'request_bytes': len(REQUEST),
                    'response_bytes': len(RESPONSE), 'request_sha256': hashlib.sha256(REQUEST).hexdigest(),
                    'response_sha256': hashlib.sha256(RESPONSE).hexdigest()})
            finally:
                if accepted is not None: accepted.close()
                if not task.done(): task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    finally:
        listener.close()
    result = {'schema': 'campaign002-tcp-trace-coverage-fixture-1', 'passed': True,
        'cases': rows, 'model_calls': 0, 'capture_started': False,
        'trace_coverage_qualified': False, 'scope': 'Socket controls only. An elevated trace must independently show both cases before any new native diagnostic can be proposed.'}
    save(output / 'result.json', result)
    print(json.dumps(result), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-immediately', action='store_true', help='Exercise controls without a trace; not trace validation.')
    args = parser.parse_args()
    args.output = args.output.resolve(); args.output.mkdir()
    try:
        asyncio.run(asyncio.wait_for(run(args.output, args.run_immediately), 70))
    except BaseException as exc:
        save(args.output / 'failure.json', {'type': type(exc).__name__, 'message': str(exc)[:1000],
            'model_calls': 0, 'capture_started': False, 'trace_coverage_qualified': False})
        raise


if __name__ == '__main__':
    main()
