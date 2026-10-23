"""Fixed local HTTP bridge plus canary/exec-server, all inside the namespace."""
import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Bubblewrap must close its startup metadata descriptor before guest code runs.
for descriptor in os.listdir('/proc/self/fd'):
    try:
        target = os.readlink('/proc/self/fd/' + descriptor)
    except FileNotFoundError:
        continue
    if target.endswith('.bwrap-info.json'):
        raise SystemExit('Outer metadata descriptor leaked into guest')


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
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 <= length <= 65536 or self.headers.get('Transfer-Encoding'):
                raise ValueError('body limit')
            request = {'method': method, 'path': self.path,
                       'capability': self.headers.get('X-Robot-Capability', ''),
                       'body': self.rfile.read(length).decode('utf-8')}
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(8)
                client.connect('/gateway.sock')
                client.sendall(json.dumps(request).encode() + b'\n')
                response = json.loads(client.makefile('rb').readline(131073))
            body = response['body'].encode()
            self.send_response(response['status'])
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            self.send_error(502, 'fixed gateway bridge unavailable')


server = ThreadingHTTPServer(('127.0.0.1', 38117), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
if sys.argv[1:] == ['canary']:
    result = subprocess.run(['/usr/bin/python3', '-I', '-B', '/canary.py'])
    server.shutdown()
    raise SystemExit(result.returncode)
elif sys.argv[1:] == ['executor']:
    # The trusted parent retains auth. This executor has no credentials or egress.
    child = subprocess.Popen(['/codex', 'exec-server', '--listen', 'stdio'])
    raise SystemExit(child.wait())
elif sys.argv[1:] == ['codehost-canary']:
    result = subprocess.run(['/usr/bin/python3', '-I', '-B', '/codehost_canary.py'])
    raise SystemExit(result.returncode)
elif sys.argv[1:] == ['codehost']:
    # gRPC lives only in this private network namespace. The Windows parent
    # relays one byte stream; this grants no general network capability.
    child = subprocess.Popen(['/code-mode-host', '--listen', 'grpc://127.0.0.1:38218'],
                             stdin=subprocess.DEVNULL, stdout=sys.stderr)
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
        def upload():
            try:
                while data := os.read(sys.stdin.fileno(), 65536):
                    channel.sendall(data)
            finally:
                channel.shutdown(socket.SHUT_WR)
        worker = threading.Thread(target=upload, daemon=True)
        worker.start()
        while data := channel.recv(65536):
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
    finally:
        child.terminate()
        child.wait(timeout=3)
else:
    raise SystemExit('Unknown namespace mode')
