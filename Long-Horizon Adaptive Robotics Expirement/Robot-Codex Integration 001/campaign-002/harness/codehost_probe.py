"""Finite no-model isolated H2 transport diagnostic; no physical simulation.

Runs fresh normal-FIN and intentional-RST fixtures, each with the unchanged
protected canaries and a two-second idle PING. Requires a frozen source anchor.
No model, app-server, recovery action, retry or scientific outcome is produced.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import sys
import time
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
REPO = HERE.parents[3]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def append(path, value):
    with Path(path).open('ab') as stream:
        stream.write(json.dumps(value, sort_keys=True).encode() + b'\n')
        stream.flush(); os.fsync(stream.fileno())


async def h2_client(url, fixture, kind):
    root = Path(fixture.evidence)
    (root / 'client').mkdir(exist_ok=False)
    log = root / 'client/events.jsonl'
    reader, writer = await asyncio.open_connection('127.0.0.1', urlsplit(url).port)
    frames = []
    async def frame():
        header = await asyncio.wait_for(reader.readexactly(9), 10)
        length = int.from_bytes(header[:3], 'big')
        if length > 65536: raise RuntimeError('H2 probe frame bound exceeded')
        payload = await asyncio.wait_for(reader.readexactly(length), 10)
        frames.append({'type': header[3], 'flags': header[4], 'bytes': length})
        if len(frames) > 12: raise RuntimeError('H2 probe frame count bound exceeded')
        return header[3], header[4], payload
    passed = False
    try:
        writer.write(b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n' + b'\x00\x00\x00\x04\x00\x00\x00\x00\x00')
        await writer.drain()
        if (await frame())[0] != 4: raise RuntimeError('H2 SETTINGS absent')
        writer.write(b'\x00\x00\x00\x04\x01\x00\x00\x00\x00')
        await writer.drain()
        idle_start = time.monotonic()
        await asyncio.sleep(2)
        idle_elapsed = time.monotonic() - idle_start
        marker = b'C02V2H2!'
        writer.write(b'\x00\x00\x08\x06\x00\x00\x00\x00\x00' + marker)
        await writer.drain()
        for _ in range(8):
            typ, flags, value = await frame()
            if typ == 6 and flags == 1 and value == marker:
                passed = True
                break
        if not passed: raise RuntimeError('H2 PING acknowledgment absent')
        return {'passed': True, 'idle_seconds': idle_elapsed, 'frames': frames,
                'scope': 'Actual isolated no-model H2 transport; no gRPC tool or recovery performance claim.'}
    finally:
        append(log, {'kind': 'client_finishing_before_close', 'schema': 'campaign002-client-finishing-1',
                     'wall_unix_s': time.time(), 'monotonic_s': time.monotonic()})
        fixture.client_finishing.set()
        if kind == 'reset':
            writer.get_extra_info('socket').setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                struct.pack('HH' if os.name == 'nt' else 'ii', 1, 0))
            writer.transport.abort()
        writer.close()
        try: await writer.wait_closed()
        except (ConnectionResetError, BrokenPipeError):
            if kind != 'reset': raise
        append(log, {'kind': 'probe_client_closed', 'schema': 'campaign002-h2-probe-client-1',
                     'closed': True, 'wall_unix_s': time.time(), 'monotonic_s': time.monotonic()})


def run(args):
    # Source check precedes creating runtime fixtures, including their synthetic
    # denied-file controls. No model launch exists anywhere in this script.
    sys.path.insert(0, str(CAMPAIGN / 'assessment'))
    from assess import frozen_problems
    from transport_integrity import verify_transport_integrity
    from runtime import Runtime, template, with_codehost, write_json
    snapshot = args.snapshot.resolve()
    frozen = json.loads(snapshot.read_text(encoding='utf-8'))
    if frozen.get('revision') != args.framework_revision or frozen_problems(snapshot, frozen, args.framework_revision):
        raise ValueError('Source anchor mismatch before transport diagnostic')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    result = {'schema': 'campaign002-codehost-probe-1', 'run_id': args.run_id,
              'framework_revision': args.framework_revision, 'snapshot_sha256': sha(snapshot),
              'model_calls': 0, 'physical_simulation': False, 'passed': False, 'cases': [],
              'source_bindings': frozen['sources'], 'checks': {},
              'scope': 'Engineering transport diagnostic only; no empirical task outcome or smoke005 causal attribution.'}
    try:
        for kind in ('normal', 'reset'):
            root = output / kind
            runtime = None
            case = {'kind': kind, 'evidence': str(root), 'passed': False}
            try:
                runtime = Runtime(root, template('bootstrap'))
                runtime.qualify()
                case['boundary_canaries_qualified'] = True
                async def callback(url): return await h2_client(url, runtime, kind)
                case['h2'] = asyncio.run(with_codehost(runtime, callback))
                case['transport_integrity'] = verify_transport_integrity(root, frozen, owner_kind='transport_probe')
                case['passed'] = case['h2']['passed'] and case['transport_integrity']['passed']
            except Exception as error:
                case['error_type'] = type(error).__name__
                case['error'] = str(error)
            finally:
                if runtime is not None:
                    try: case['cleanup_clean'] = runtime.close()
                    except Exception as error:
                        case['cleanup_clean'] = False
                        case['cleanup_error_type'] = type(error).__name__
                case['passed'] = case['passed'] and case.get('cleanup_clean') is True
                result['cases'].append(case)
            if not case['passed']: break
        result['checks'] = {'two_fresh_cases': len(result['cases']) == 2,
                            'all_transport_cases_passed': all(c['passed'] for c in result['cases'])}
        result['passed'] = all(result['checks'].values())
    finally:
        write_json(output / 'result.json', result)
    print(json.dumps({'passed': result['passed'], 'result': str(output / 'result.json'), 'model_calls': 0}))
    return 0 if result['passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--framework-revision', required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    return run(parser.parse_args())


if __name__ == '__main__':
    raise SystemExit(main())
