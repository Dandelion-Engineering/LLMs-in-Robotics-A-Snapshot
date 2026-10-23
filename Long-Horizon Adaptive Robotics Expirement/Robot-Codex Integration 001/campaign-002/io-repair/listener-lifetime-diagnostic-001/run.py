"""One declared finite Windows loopback matrix; no model or native process."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import time

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent.parent / 'harness'
sys.path.insert(0, str(HARNESS))
import codehost_bridge_v3 as bridge

PREFIX = bytes(range(256)) * 16
TAIL = b'fixed-tail-0000001'
CASES = ('listener_close_then_fin', 'accept_cancel_then_fin',
         'listener_close_unread_peer_close', 'listener_close_unread_peer_fin_drain')

def identity(path):
    data = path.read_bytes()
    return {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}

def error(error):
    classes = (ConnectionAbortedError, ConnectionResetError, BrokenPipeError,
               TimeoutError, OSError, asyncio.CancelledError, ValueError)
    integer = lambda value: value if type(value) is int and -2**31 <= value < 2**31 else None
    return {'class': type(error).__name__ if type(error) in classes else 'OtherException',
            'errno': integer(getattr(error, 'errno', None)),
            'winerror': integer(getattr(error, 'winerror', None))}

async def one(case):
    observations = []
    prefix_seen, pending, downloaded = asyncio.Event(), asyncio.Event(), asyncio.Event()
    done = asyncio.get_running_loop().create_future()
    local_writer = None
    received = bytearray()
    tasks = set()
    server = None
    peer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    peer.setblocking(False)
    async def handler(reader, writer):
        nonlocal local_writer
        local_writer = writer
        tasks.add(asyncio.current_task())
        try:
            while len(received) < len(PREFIX):
                block = await reader.read(len(PREFIX)-len(received))
                if not block: raise ValueError('premature_prefix_eof')
                received.extend(block)
            prefix_seen.set()
            while True:
                pending.set()
                block = await reader.read(4096)
                observations.append({'kind': 'data' if block else 'eof', 'bytes': len(block)})
                if not block: break
                received.extend(block)
        except BaseException as exc:
            observations.append({'kind': 'exception', **error(exc)})
        finally:
            if not done.done(): done.set_result(True)
    record = {'case': case, 'observations': observations, 'listener_errors': [],
              'observation_bound_s': 2, 'cleanup_bound_s': 1}
    try:
        async with asyncio.timeout(2):
            server = await bridge.create_server(handler, '127.0.0.1', 0,
                                                 on_error=record['listener_errors'].append)
            loop = asyncio.get_running_loop()
            await loop.sock_connect(peer, server.sockets[0].getsockname())
            await loop.sock_sendall(peer, PREFIX)
            await prefix_seen.wait()
            await pending.wait()
            await asyncio.sleep(0)
            record['accepted_read_pending'] = not done.done()
            record['next_accept_pending'] = not server.accept_task.done()
            if case == 'accept_cancel_then_fin':
                server.accept_task.cancel()
                await asyncio.gather(server.accept_task, return_exceptions=True)
            else:
                server.close()
                await server.wait_closed()
            record['accepted_read_done_after_listener_action'] = done.done()
            if 'unread' in case:
                local_writer.write(PREFIX)
                await local_writer.drain()
                record['download_write_bytes'] = len(PREFIX)
                if case.endswith('peer_close'):
                    peer.close()
                else:
                    peer.shutdown(socket.SHUT_WR)
                    download = bytearray()
                    while len(download) < len(PREFIX):
                        block = await loop.sock_recv(peer, len(PREFIX)-len(download))
                        if not block: raise ValueError('premature_download_eof')
                        download.extend(block)
                    record['download_exact'] = download == PREFIX
            else:
                await loop.sock_sendall(peer, TAIL)
                peer.shutdown(socket.SHUT_WR)
            await asyncio.shield(done)
    except BaseException as exc:
        record['operation_error'] = error(exc)
    finally:
        if server: server.close()
        for task in tasks:
            if not task.done(): task.cancel()
        async with asyncio.timeout(1):
            if server: await server.wait_closed()
            if tasks: await asyncio.gather(*tasks, return_exceptions=True)
        if local_writer: local_writer.close()
        peer.close()
        record['cleanup_complete'] = all(task.done() for task in tasks)
    record['upload_bytes'] = len(received)
    record['upload_sha256'] = hashlib.sha256(received).hexdigest()
    record['expected_upload_exact'] = bytes(received) == (PREFIX if 'unread' in case else PREFIX+TAIL)
    return record

async def main():
    output = HERE / 'execution-001'
    output.mkdir(exist_ok=False)
    sources = [identity(path) for path in (Path(__file__), HERE/'DECLARATION.md',
               HARNESS/'codehost_bridge_v3.py', HARNESS/'codehost_owner.py',
               HARNESS/'codehost_mux_protocol.py', HARNESS/'native_cleanup_protocol.py')]
    def save(name, value):
        with (output/name).open('x', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    save('intent.json', {'cases': CASES, 'sources': sources, 'model_calls': 0})
    results = []
    for case in CASES:
        value = await one(case)
        results.append(value)
        save(case+'.json', value)
    unchanged = all(identity(Path(item['path'])) == item for item in sources)
    value = {'schema': 'campaign002-listener-lifetime-diagnostic-1', 'diagnostic_only': True,
             'sources': sources, 'sources_unchanged': unchanged, 'cases': results}
    save('result.json', value)
    print(json.dumps({'sources_unchanged': unchanged, 'cases': results}, indent=2))

if __name__ == '__main__':
    if os.name != 'nt': raise RuntimeError('Windows fixture required')
    asyncio.run(main())
