"""Temporary loopback-only video QA; no experiment routes or file browser."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json,threading
D=Path(__file__).resolve().parent
video=Path(json.loads((D/'source-timecode-manifest.json').read_bytes())['video']['path'])
PAGE=b'''<!doctype html><html><meta name="viewport" content="width=device-width,initial-scale=1"><title>Session 76 video QA</title>
<style>body{background:#0c161f;color:#f1f5f3;font:16px system-ui;margin:18px}video{display:block;width:min(100%,1280px);background:black}button,input{font:inherit;margin:8px;padding:6px}#clock{font-variant-numeric:tabular-nums}</style>
<h1>Three sessions later</h1><p>Private local QA preview. Silent video. Sources and caption labels are burned into the MP4.</p>
<video id="movie" controls muted playsinline preload="auto" src="/video.mp4"></video>
<button id="start">Play from beginning</button><button id="pause">Pause</button><label>Seek video seconds <input id="seek" type="number" value="0" min="0" max="140"></label><button id="go">Go</button><button id="phone">Phone landscape (640 px)</button><button id="desktop">Desktop (1280 px)</button><p id="clock">Waiting</p>
<script>const v=document.querySelector('video'),clock=document.querySelector('#clock');document.querySelector('#start').onclick=()=>{v.currentTime=0;v.play()};document.querySelector('#pause').onclick=()=>v.pause();document.querySelector('#go').onclick=()=>{v.pause();v.currentTime=Number(document.querySelector('#seek').value)};document.querySelector('#phone').onclick=()=>v.style.width='640px';document.querySelector('#desktop').onclick=()=>v.style.width='min(100%,1280px)';v.ontimeupdate=()=>clock.textContent='Video time '+v.currentTime.toFixed(3)+' / '+v.duration.toFixed(3)+' s | '+(v.paused?'paused':'playing')+' | '+v.videoWidth+'x'+v.videoHeight;v.onerror=()=>clock.textContent='ERROR '+(v.error&&v.error.message);</script>'''
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
        if self.path=='/':
            self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(PAGE)));self.end_headers();self.wfile.write(PAGE);return
        if self.path!='/video.mp4':self.send_error(404);return
        size=video.stat().st_size;start,end=0,size-1;r=self.headers.get('Range')
        if r:
            a,b=r.removeprefix('bytes=').split('-');start=int(a or 0);end=min(int(b) if b else end,end)
        self.send_response(206 if r else 200);self.send_header('Content-Type','video/mp4');self.send_header('Accept-Ranges','bytes')
        self.send_header('Content-Length',str(end-start+1))
        if r:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers()
        try:
            with video.open('rb') as f:
                f.seek(start);remaining=end-start+1
                while remaining:
                    b=f.read(min(65536,remaining));self.wfile.write(b);remaining-=len(b)
        except (BrokenPipeError,ConnectionResetError):pass
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
print('http://127.0.0.1:'+str(server.server_port),flush=True)
try:server.serve_forever()
except KeyboardInterrupt:pass
finally:server.server_close()
