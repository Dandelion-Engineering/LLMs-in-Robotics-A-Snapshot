"""Real Windows pipe/socket ordering controls, without models or production writes."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import struct
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
REQUEST = b'fixed-upload-frontier\n'
REPLY = b'fixed-response-tail\n' * 16385
CASES = ('pooled_baseline', 'pooled_candidate', 'delayed_tail', 'early_eof',
         'abortive_reset', 'truncated_upload', 'nonzero_exit', 'missing_eof')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2); stream.write('\n'); stream.flush()
        __import__('os').fsync(stream.fileno())


def child(port, mode, output):
    sock = socket.create_connection(('127.0.0.1', port), timeout=8)
    data = REQUEST[:-1] if mode == 'truncated_upload' else REQUEST
    sock.sendall(data)
    received = b''
    # The delayed-tail case leaves actual reply bytes queued across stdin EOF.
    if mode != 'delayed_tail':
        while len(received) < len(REPLY):
            block = sock.recv(min(65536, len(REPLY)-len(received)))
            if not block: break
            received += block
    if mode == 'early_eof':
        sock.shutdown(socket.SHUT_WR)
    print('application_frontier', flush=True)
    sys.stdin.buffer.read()
    stdin_eof_ns = time.perf_counter_ns()
    if mode == 'missing_eof':
        time.sleep(20)
    if mode == 'delayed_tail':
        time.sleep(.15)
        while len(received) < len(REPLY):
            block = sock.recv(min(65536, len(REPLY)-len(received)))
            if not block: break
            received += block
    if mode == 'abortive_reset':
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('HH', 1, 0))
        sock.close()
        genuine_server_eof = False
    else:
        if mode != 'early_eof': sock.shutdown(socket.SHUT_WR)
        genuine_server_eof = sock.recv(1) == b''
        sock.close()
    save(output / 'child.json', {'stdin_eof_ns': stdin_eof_ns,
        'sent': {'bytes': len(data), 'sha256': digest(data)},
        'received': {'bytes': len(received), 'sha256': digest(received)},
        'genuine_server_eof': genuine_server_eof})
    return 7 if mode == 'nonzero_exit' else 0


def run_case(mode, root):
    output = root / mode
    output.mkdir()
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    listener.bind(('127.0.0.1', 0)); listener.listen(1); listener.settimeout(8)
    child_out = (output / 'child.stdout').open('x', encoding='utf-8')
    child_err = (output / 'child.stderr').open('x', encoding='utf-8')
    process = subprocess.Popen([sys.executable, '-X', 'utf8', '-B', str(Path(__file__).resolve()),
        '--child', str(listener.getsockname()[1]), '--mode', mode, '--output', str(output)],
        stdin=subprocess.PIPE, stdout=child_out, stderr=child_err,
        creationflags=subprocess.CREATE_NO_WINDOW)
    conn = None
    result = {'case': mode, 'genuine_client_eof': False, 'forced': False, 'errors': [],
              'graceful_bound_s': 5, 'total_cleanup_bound_s': 10}
    sender = None
    sent = threading.Event()
    send_errors = []
    collected = bytearray()
    try:
        conn, peer = listener.accept(); listener.close()
        conn.settimeout(.03)
        while len(collected) < (len(REQUEST)-1 if mode == 'truncated_upload' else len(REQUEST)):
            collected.extend(conn.recv(65536))
        def send():
            try:
                conn.settimeout(8)
                conn.sendall(REPLY)
            except Exception as error:
                send_errors.append(type(error).__name__)
            finally:
                sent.set()
        sender = threading.Thread(target=send)
        sender.start()
        ready_deadline = time.monotonic()+8
        while 'application_frontier' not in (output / 'child.stdout').read_text(encoding='utf-8'):
            if process.poll() is not None or time.monotonic() >= ready_deadline:
                raise RuntimeError('Child fixture failed before frontier')
            time.sleep(.01)
        start = time.perf_counter_ns()
        deadline = time.monotonic()+5
        result['frontier_ns'] = start
        if mode != 'pooled_baseline':
            result['stdin_close_begin_ns'] = time.perf_counter_ns()
            process.stdin.close()
            result['stdin_close_end_ns'] = time.perf_counter_ns()
        conn.settimeout(.03)
        while time.monotonic() < deadline:
            try:
                block = conn.recv(65536)
            except socket.timeout:
                continue
            if not block:
                result['genuine_client_eof'] = True
                result['client_eof_ns'] = time.perf_counter_ns()
                break
            collected.extend(block)
        if not result['genuine_client_eof']:
            raise TimeoutError('Real peer EOF absent at original five-second deadline')
        if not sent.wait(max(0, deadline-time.monotonic())) or send_errors:
            raise RuntimeError('Reply tail did not fully drain')
        conn.shutdown(socket.SHUT_WR)
        if mode == 'pooled_baseline':
            process.stdin.close()
        process.wait(timeout=max(0, deadline-time.monotonic()))
        result['elapsed_s'] = (time.perf_counter_ns()-start)/1e9
    except Exception as error:
        result['errors'].append({'type': type(error).__name__, 'message': str(error)[:300]})
    finally:
        if process.poll() is None:
            result['forced'] = True
            process.terminate(); process.wait(timeout=5)
        if process.stdin and not process.stdin.closed: process.stdin.close()
        if conn: conn.close()
        listener.close()
        if sender: sender.join(5)
        child_out.close(); child_err.close()
        result['exit_code'] = process.returncode
        result['sender_joined'] = sender is None or not sender.is_alive()
        result['send_errors'] = send_errors
    peer_result = json.loads((output / 'child.json').read_text()) if (output / 'child.json').exists() else None
    result['parent_received'] = {'bytes': len(collected), 'sha256': digest(collected)}
    result['child'] = peer_result
    result['complete_bytes'] = (peer_result is not None and
        peer_result['sent'] == result['parent_received'] == {'bytes': len(REQUEST), 'sha256': digest(REQUEST)} and
        peer_result['received'] == {'bytes': len(REPLY), 'sha256': digest(REPLY)})
    result['qualified_fixture'] = (not result['errors'] and not result['forced'] and
        result['exit_code'] == 0 and result['genuine_client_eof'] and result['complete_bytes'] and
        result['sender_joined'] and not send_errors and result.get('elapsed_s', 99) < 5 and
        peer_result['genuine_server_eof'])
    expected = mode in ('pooled_candidate', 'delayed_tail', 'early_eof')
    result['expected_qualification'] = expected
    result['control_passed'] = result['qualified_fixture'] is expected
    save(output / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--child', type=int)
    parser.add_argument('--mode', choices=CASES)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.child is not None:
        return child(args.child, args.mode, args.output)
    root = HERE / 'controls-001'
    root.mkdir()
    sources = {p.name: {'bytes': p.stat().st_size, 'sha256': digest(p.read_bytes())}
        for p in (Path(__file__), HERE / 'DECLARATION.md')}
    save(root / 'intent.json', {'cases': CASES, 'sources': sources, 'model_calls': 0,
        'installed_native_binary_tested': False, 'production_sources_changed': False})
    results = [run_case(mode, root) for mode in CASES]
    value = {'all_controls_passed': all(r['control_passed'] for r in results),
        'cases': results, 'sources': sources, 'model_calls': 0, 'native_qualified': False}
    save(root / 'receipt.json', value)
    print(json.dumps({'all_controls_passed': value['all_controls_passed'], 'cases': [
        {k:r.get(k) for k in ('case', 'qualified_fixture', 'control_passed', 'errors', 'forced', 'exit_code', 'complete_bytes')} for r in results]}, indent=2))
    return 0 if value['all_controls_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
