"""Private codehost relay with explicit child status and bounded metadata receipts.

Only codehost mode uses this entry. The gateway classes are identical to the
original inside.py; the original executor and canary entries remain unchanged.
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

PREFIX = 'RCI_CODEHOST_V2 '
MAX_RECORDS = 32
MAX_CHILD_DIAGNOSTIC_BYTES = 1024 * 1024


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
        self.stream, self.sequence, self.lock = stream, 0, threading.Lock()
    def emit(self, kind, **fields):
        with self.lock:
            self.sequence += 1
            if self.sequence > MAX_RECORDS:
                raise RuntimeError('Namespace metadata bound exceeded')
            row = {'schema': 'campaign002-codehost-namespace-2', 'sequence': self.sequence,
                   'wall_unix_s': time.time(), 'monotonic_s': time.monotonic(), 'kind': kind, **fields}
            self.stream.write(PREFIX + json.dumps(row, sort_keys=True) + '\n')
            self.stream.flush()
            return row


def diagnostic_drains(child, emit, failed):
    """Child-controlled bytes never share the wrapper's status-record channel."""
    lock = threading.Lock()
    total = [0]
    def drain(stream, name):
        count, digest, truncated = 0, hashlib.sha256(), False
        try:
            while data := stream.read(65536):
                count += len(data); digest.update(data)
                with lock:
                    total[0] += len(data)
                    if total[0] > MAX_CHILD_DIAGNOSTIC_BYTES:
                        truncated = True
                        failed.set()
                        if child.poll() is None: child.terminate()
            emit('child_diagnostic', stream=name, bytes=count, sha256=digest.hexdigest(), truncated=truncated)
        except BaseException:
            failed.set()
    workers = [threading.Thread(target=drain, args=(getattr(child, name), name), daemon=True)
               for name in ('stdout', 'stderr')]
    for worker in workers: worker.start()
    def finish():
        for worker in workers: worker.join(timeout=2)
        if any(worker.is_alive() for worker in workers): failed.set()
        return not any(worker.is_alive() for worker in workers)
    return finish


def relay(child, channel, input_fd, output, emit, diagnostic_failure=None, drain_diagnostics=None):
    """Unmodified byte relay; owner stdin EOF and unexpected host EOF differ."""
    input_eof = threading.Event()
    upload_failed = threading.Event()
    counts = {'to_host': 0, 'from_host': 0}
    error_type = None
    def unblock():
        try: channel.shutdown(socket.SHUT_RDWR)
        except OSError: pass
    def upload():
        try:
            while data := os.read(input_fd, 65536):
                channel.sendall(data)
                counts['to_host'] += len(data)
            input_eof.set()
            emit('stdin_eof', **counts)
        except BaseException as error:
            upload_failed.set()
            emit('upload_error', exception_type=type(error).__name__)
        finally:
            unblock()
    worker = threading.Thread(target=upload, daemon=True)
    worker.start()
    try:
        while data := channel.recv(65536):
            output.write(data)
            output.flush()
            counts['from_host'] += len(data)
    except BaseException as error:
        error_type = type(error).__name__
    if diagnostic_failure is not None and diagnostic_failure.is_set():
        error_type = 'ChildDiagnosticFailure'
    before = child.poll()
    input_eof_at_channel_end = input_eof.is_set()
    reason = 'stdin_eof' if input_eof_at_channel_end else ('relay_error' if error_type or upload_failed.is_set() else 'channel_eof')
    emit('channel_end', reason=reason, stdin_eof=input_eof_at_channel_end,
         child_exit_before_cleanup=before, error_type=error_type, **counts)
    # Expose channel EOF before waiting for the trusted parent's input closure.
    # It independently fails EOF observed before its durable finishing marker.
    # This permits graceful H2 shutdown preceding TCP FIN without a deadlock.
    output.close()
    if before in (None, 0) and not upload_failed.is_set() and error_type is None:
        input_eof.wait(.5)
    expected = input_eof.is_set() and not upload_failed.is_set() and error_type is None and before in (None, 0)
    reason = 'owner_input_eof' if expected else ('relay_error' if error_type or upload_failed.is_set() else 'unexpected_channel_eof')
    terminate_sent = kill_sent = False
    if child.poll() is None:
        terminate_sent = True
        child.terminate()
    try:
        code = child.wait(timeout=3)
    except subprocess.TimeoutExpired:
        kill_sent = True
        child.kill()
        code = child.wait(timeout=3)
    diagnostics_complete = True if drain_diagnostics is None else drain_diagnostics()
    qualified = (expected and not kill_sent and diagnostics_complete
                 and (diagnostic_failure is None or not diagnostic_failure.is_set())
                 and (code == 0 or terminate_sent and code == -15))
    emit('closed', qualified=qualified, reason=reason, stdin_eof=input_eof.is_set(),
         child_exit_before_cleanup=before, child_exit_code=code,
         terminate_sent=terminate_sent, kill_sent=kill_sent, error_type=error_type,
         stdin_eof_at_channel_end=input_eof_at_channel_end, owner_input_wait_bound_s=.5,
         diagnostic_streams_complete=diagnostics_complete, **counts)
    return 0 if qualified else 1


def main():
    if sys.argv[1:] != ['codehost']:
        raise SystemExit('Additive inside supports codehost mode only')
    for descriptor in os.listdir('/proc/self/fd'):
        try: target = os.readlink('/proc/self/fd/' + descriptor)
        except FileNotFoundError: continue
        if target.endswith('.bwrap-info.json'):
            raise SystemExit('Outer metadata descriptor leaked into guest')
    sys.path.insert(0, '/')
    import gateway_policy
    for name in ('MAX_BODY', 'MAX_RESPONSE_FRAME', 'validate_request', 'validate_response', 'error_response'):
        globals()[name] = getattr(gateway_policy, name)
    server = BoundedHTTPServer(('127.0.0.1', 38117), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    metadata = Metadata(sys.stderr)
    metadata.emit('open')
    child = subprocess.Popen(['/code-mode-host', '--listen', 'grpc://127.0.0.1:38218'],
                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    metadata.emit('child_started', child_pid=child.pid)
    diagnostic_failure = threading.Event()
    finish_diagnostics = diagnostic_drains(child, metadata.emit, diagnostic_failure)
    channel = None
    try:
        deadline = time.monotonic() + 10
        while True:
            try:
                channel = socket.create_connection(('127.0.0.1', 38218), .2)
                channel.settimeout(None)
                break
            except OSError:
                if child.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Private code host unavailable')
                time.sleep(.05)
        metadata.emit('connected')
        return relay(child, channel, sys.stdin.fileno(), sys.stdout.buffer, metadata.emit,
                     diagnostic_failure, finish_diagnostics)
    except BaseException as error:
        metadata.emit('failure', exception_type=type(error).__name__, child_exit_before_cleanup=child.poll())
        return 1
    finally:
        if channel is not None: channel.close()
        if child.poll() is None:
            child.terminate()
            try: child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait(timeout=3)
        finish_diagnostics()
        server.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
