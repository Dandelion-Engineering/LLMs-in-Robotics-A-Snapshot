"""Fixed-purpose Unix IPC relay: only public sensing and physical commands."""
import argparse
import json
from pathlib import Path
import select
import socket
import sys

def main():
    p=argparse.ArgumentParser();p.add_argument('socket');p.add_argument('--repo',required=True);a=p.parse_args()
    boundary=Path(a.repo)/'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/readiness-session-10/boundary'
    sys.path.insert(0,str(boundary))
    from gateway_policy import validate_request,validate_response,error_response,MAX_REQUEST_FRAME,MAX_RESPONSE_FRAME
    server=socket.socket(socket.AF_UNIX);server.bind(a.socket);server.listen(8);server.settimeout(.2)
    print(json.dumps({'ready':True}),flush=True)
    try:
        while True:
            if select.select([sys.stdin],[],[],0)[0]:break
            try:client,_=server.accept()
            except socket.timeout:continue
            with client:
                client.settimeout(20)
                try:
                    raw=client.makefile('rb').readline(MAX_REQUEST_FRAME+1)
                    if len(raw)>MAX_REQUEST_FRAME or not raw.endswith(b'\n'):raise ValueError('Bound')
                    request=validate_request(json.loads(raw))
                    if (request['method'],request['path']) not in [('GET','/status'),('POST','/observe'),('POST','/command')]:raise PermissionError('Denied route')
                    print(json.dumps(request),flush=True)
                    if not select.select([sys.stdin],[],[],20)[0]:raise RuntimeError('Unknown receipt')
                    raw=sys.stdin.buffer.readline(MAX_RESPONSE_FRAME+1)
                    if not raw or len(raw)>MAX_RESPONSE_FRAME:raise RuntimeError('Unknown receipt')
                    response=validate_response(json.loads(raw))
                except (ValueError,PermissionError):response=error_response(403,'route_or_body_denied')
                except Exception:
                    client.sendall((json.dumps(error_response(502,'receipt_unknown'))+'\n').encode());raise
                client.sendall((json.dumps(response)+'\n').encode())
    finally:server.close();Path(a.socket).unlink(missing_ok=True)

if __name__=='__main__':main()
