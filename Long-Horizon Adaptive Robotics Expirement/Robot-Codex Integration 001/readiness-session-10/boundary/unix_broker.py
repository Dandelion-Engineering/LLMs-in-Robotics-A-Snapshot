"""Trusted WSL robot IPC; only Windows parent chooses fixed destination/token.

The guest may connect directly, so route/body bounds apply here as well as at
the loopback HTTP facade. Each request is one JSON line. Successful protected
continuity commits are mirrored atomically before replying to the guest.
"""
import argparse
import json
from pathlib import Path
import select
import socket
import sys
import threading
from gateway_policy import (MAX_REQUEST_FRAME, MAX_RESPONSE_FRAME,
                            validate_request, validate_response, error_response)
from runtime_layout import atomic_continuity, validate_workspace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('socket')
    parser.add_argument('--workspace', required=True)
    args = parser.parse_args()
    workspace = validate_workspace(args.workspace)
    path = Path(args.socket)
    if path.parent != workspace.parent or path.parent.resolve(strict=True) != path.parent:
        raise SystemExit('IPC socket outside runtime')
    server = socket.socket(socket.AF_UNIX)
    server.bind(str(path))
    path.chmod(0o600)
    server.listen(8)
    server.settimeout(.2)
    decoy = socket.socket()
    decoy.bind(('127.0.0.1', 0))
    decoy.listen(4)
    def serve_decoy():
        while True:
            try:
                connection, _ = decoy.accept()
                connection.close()
            except OSError:
                return
    threading.Thread(target=serve_decoy, daemon=True).start()
    print(json.dumps({'ready': True, 'other_port': decoy.getsockname()[1]}), flush=True)
    try:
        while True:
            # Parent-owned stdin EOF retires the capability relay while idle.
            if select.select([sys.stdin], [], [], 0)[0]:
                break
            try:
                client, _ = server.accept()
            except socket.timeout:
                continue
            with client:
                client.settimeout(8)
                try:
                    raw = client.makefile('rb').readline(MAX_REQUEST_FRAME + 1)
                    if len(raw) > MAX_REQUEST_FRAME or not raw.endswith(b'\n'):
                        raise ValueError('request frame limit')
                    request = validate_request(json.loads(raw))
                    print(json.dumps(request), flush=True)
                    if not select.select([sys.stdin], [], [], 8)[0]:
                        # Unknown receipt: terminate instead of assigning a late
                        # parent reply to the next request.
                        client.sendall((json.dumps(error_response(504, 'parent_receipt_unknown')) + '\n').encode())
                        break
                    reply = sys.stdin.buffer.readline(MAX_RESPONSE_FRAME + 1)
                    if not reply or len(reply) > MAX_RESPONSE_FRAME or not reply.endswith(b'\n'):
                        break
                    response = validate_response(json.loads(reply))
                    decoded = json.loads(response['body'])
                    if (request['method'], request['path']) == ('POST', '/continuity') and decoded['ok'] and 200 <= response['status'] < 300:
                        result = atomic_continuity(workspace, json.loads(request['body'])['content'])
                        if decoded.get('sha256') != result['sha256'] or decoded.get('bytes') != result['bytes']:
                            raise RuntimeError('protected continuity hash mismatch')
                except PermissionError:
                    response = error_response(403, 'broker_route_denied')
                except (ValueError, UnicodeError):
                    response = error_response(400, 'invalid_bounded_request_or_response')
                except Exception:
                    response = error_response(502, 'broker_or_continuity_sync_failed_receipt_unknown')
                try:
                    client.sendall((json.dumps(response) + '\n').encode())
                except (BrokenPipeError, ConnectionResetError, TimeoutError):
                    pass
    finally:
        server.close()
        decoy.close()
        path.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
