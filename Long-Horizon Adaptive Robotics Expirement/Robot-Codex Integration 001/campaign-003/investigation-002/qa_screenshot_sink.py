"""Temporary loopback form for retaining browser API JPEG bytes as QA artifacts.

The browser is still operated only through its supported computer-use API.
This form writes two fixed, new files; it cannot choose arbitrary output paths.
"""
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parent / 'replays/pilot-003-002'
NAMES = {'desktop': 'browser-desktop.jpg', 'mobile': 'browser-mobile.jpg'}
PAGE = b'''<!doctype html><meta charset="utf-8"><title>Local replay QA capture</title>
<h1>Save browser QA screenshot</h1><p>Local evidence only. Two fixed output names.</p>
<form method="post"><label>Viewport<select name="viewport"><option>desktop</option><option>mobile</option></select></label>
<label>JPEG bytes<textarea name="jpeg" aria-label="JPEG bytes"></textarea></label>
<button>Save screenshot</button></form>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(PAGE)

    def do_POST(self):
        try:
            length = int(self.headers['Content-Length'])
            if not 1 <= length <= 2 * 1024**2:
                raise ValueError('Capture exceeds fixed form limit')
            fields = parse_qs(self.rfile.read(length).decode('ascii'), strict_parsing=True)
            name = NAMES[fields['viewport'][0]]
            raw = base64.b64decode(fields['jpeg'][0], validate=True)
            if not raw.startswith(b'\xff\xd8') or not raw.endswith(b'\xff\xd9'):
                raise ValueError('Expected unmodified JPEG screenshot bytes')
            output = ROOT / name
            with output.open('xb') as stream:
                stream.write(raw)
            digest = hashlib.sha256(raw).hexdigest()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(f'<h1>Saved {name}</h1><p>{len(raw)} bytes</p><p>SHA256 {digest}</p>'.encode())
        except Exception as error:
            self.send_error(400, type(error).__name__)


if __name__ == '__main__':
    HTTPServer(('127.0.0.1', 8921), Handler).serve_forever()
