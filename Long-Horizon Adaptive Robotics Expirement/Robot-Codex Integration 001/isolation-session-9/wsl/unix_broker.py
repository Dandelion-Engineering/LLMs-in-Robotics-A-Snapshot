"""Trusted WSL IPC endpoint; Windows parent alone selects the real destination."""
import json
from pathlib import Path
import socket
import sys
import threading
import select

path = Path(sys.argv[1])
server = socket.socket(socket.AF_UNIX)
server.bind(str(path))
path.chmod(0o600)
server.listen(4)
server.settimeout(.5)
decoy = socket.socket()
decoy.bind(('127.0.0.1', 0))
decoy.listen(4)
def serve_decoy():
    while True:
        connection, _ = decoy.accept()
        connection.close()
threading.Thread(target=serve_decoy, daemon=True).start()
print(json.dumps({'ready': True, 'other_port': decoy.getsockname()[1]}), flush=True)
try:
    while True:
        # EOF on the parent-owned pipe retires the broker even without requests.
        if select.select([sys.stdin], [], [], 0)[0]:
            break
        try:
            client, _ = server.accept()
        except socket.timeout:
            continue
        with client:
            client.settimeout(10)
            raw = client.makefile('rb').readline(131073)
            if len(raw) > 131072:
                continue
            request = json.loads(raw)
            print(json.dumps(request), flush=True)
            response = sys.stdin.buffer.readline(262145)
            if not response or len(response) > 262144:
                break
            client.sendall(response)
finally:
    server.close()
    path.unlink(missing_ok=True)
