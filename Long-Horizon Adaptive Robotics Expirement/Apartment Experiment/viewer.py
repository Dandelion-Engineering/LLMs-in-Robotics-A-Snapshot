"""Detachable local observer. Rendering happens only in an open viewer's browser."""
import argparse
import bisect
import copy
import difflib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import threading
import urllib.request
from urllib.parse import urlsplit,parse_qs
from common import HERE,canonical,read
from recording import Replay
from content_store import read_object

class Files:
    def __init__(self,root):
        self.root=Path(root);self.logs={};self.cached_key=None;self.cached=None
    def rows(self,path):
        path=Path(path)
        if not path.exists():return []
        offset,rows=self.logs.get(path,(0,[]))
        with path.open('rb') as f:
            f.seek(offset)
            for raw in f:
                if not raw.endswith(b'\n'):break
                rows.append(json.loads(raw));offset+=len(raw)
        self.logs[path]=(offset,rows)
        return rows
    def material(self,t=None):
        journals=sorted(self.root.glob('sessions/*/workspace/journal/mutations.jsonl'))
        prepared=[]
        for journal in journals:
            records=self.rows(journal);clocks=self.rows(journal.parent.parent/'clock-bridge.jsonl')
            prepared.append((journal,records,[r['payload'] for r in clocks]))
        key=(t,tuple((str(p),len(r),len(c)) for p,r,c in prepared))
        if key==self.cached_key:return self.cached
        state={};versions={};activity=[];unknown=0;max_bound=0.
        # Each session's independently journaled initial state follows the previous final export.
        for journal,records,clocks in prepared:
            times=[c['linux']['linux_monotonic_ns'] for c in clocks]
            for r in records:
                if r['type'] not in ('initial','mutation','read'):continue
                at=bisect.bisect_left(times,r['monotonic_ns'])
                bound=None
                if at<len(clocks):
                    low=clocks[max(0,at-1)]['before']['sim_time'];high=clocks[at]['after']['sim_time']
                    bound=[low,high];max_bound=max(max_bound,high-low)
                if t is not None and (bound is None or bound[1]>t):
                    if bound is None:unknown+=1
                    continue
                if r['type']=='initial':state=copy.deepcopy(r['state'])
                elif r['type']=='mutation':
                    if not state:continue
                    for area in ('paths','nodes'):
                        for key in r['delta'][area]['remove']:state[area].pop(key,None)
                        state[area].update(copy.deepcopy(r['delta'][area]['set']))
                    path=r.get('arguments',{}).get('path','(namespace change)')
                    activity.append(dict(operation=r['operation'],path=path,sequence=r['sequence'],time_bound=bound,source=str(journal)))
                elif r['type']=='read':activity.append(dict(operation='read',path=r['path'],sequence=r['sequence'],time_bound=bound,source=str(journal)))
                else:continue
                for path,inode in state.get('paths',{}).items():
                    node=state['nodes'][str(inode)];key=node.get('sha256')
                    if not key:continue
                    old=versions.get(path,[])
                    if not old or old[-1][0]!=key:old.append((key,journal.parent/'objects'/key));versions[path]=old
        if not state and t is None:
            for path in (self.root/'filesystem').rglob('*'):
                if path.is_file():versions['/'+path.relative_to(self.root/'filesystem').as_posix()]=[('initial',path)]
            current=sorted(versions)
        else:current=sorted(p for p,i in state.get('paths',{}).items() if state['nodes'][str(i)].get('sha256'))
        alignment=('Replay includes only filesystem events whose entire recorded time bound is at or before the selected time. '
                   f'Largest retained bound: {max_bound:.2f} s. Unaligned events withheld: {unknown}.' if t is not None else
                   'Latest completed journal records. Activity times are measured bounds, separate from physical action completion.')
        self.cached_key=(t,tuple((str(p),len(r),len(c)) for p,r,c in prepared))
        self.cached=(current,versions,activity,alignment)
        return self.cached
    def listing(self,t=None):
        files,versions,activity,alignment=self.material(t)
        visible=[]
        for r in activity:
            if r['path'].startswith(('/.codex/','/.git/')) or '/__pycache__/' in r['path']:continue
            if visible and (r['path'],r['operation'])==(visible[-1]['path'],visible[-1]['operation']):visible[-1]=r
            else:visible.append(r)
        return dict(files=[p for p in files if not p.startswith(('/.codex/','/.git/'))],activity=visible[-20:],alignment=alignment)
    def file(self,path,t=None):
        files,versions,_,alignment=self.material(t)
        if path not in versions:raise ValueError('File not in retained namespace')
        rows=versions[path]
        def content_bytes(row):return row[1].read_bytes() if row[0]=='initial' else read_object(row[1])
        raw=content_bytes(rows[-1]);content=raw.decode('utf-8',errors='replace') if len(raw)<256*1024 else '[Large file: contents omitted from compact viewer]'
        prior=content_bytes(rows[-2]) if len(rows)>1 else b''
        before=prior.decode('utf-8',errors='replace') if len(prior)<256*1024 else '[Large file: contents omitted from compact viewer]'
        difference=('No earlier retained version is available; this is the initial recorded content.' if len(rows)==1 else
                    ''.join(difflib.unified_diff(before.splitlines(keepends=True),content.splitlines(keepends=True),fromfile='previous retained',tofile='current retained')))
        return dict(content=content,diff=difference or 'No retained content change.',provenance='Recorded content '+rows[-1][0]+'. '+alignment)

def serve(root,controller=None,port=0):
    root=Path(root);replay=Replay(root) if controller is None else None;files=Files(root);lock=threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            parsed=urlsplit(self.path);q=parse_qs(parsed.query)
            try:
                with lock:
                    t=float(q['t'][0]) if 't' in q else None
                    if parsed.path=='/':raw=(HERE/'viewer.html').read_bytes();mime='text/html; charset=utf-8'
                    else:
                        if parsed.path=='/info':value=dict(replay=replay is not None)
                        elif parsed.path=='/frame':value=replay.frame(t or 0) if replay else controller.ask('frame')
                        elif parsed.path=='/filesystem':value=files.listing(t)
                        elif parsed.path=='/file':value=files.file(q['path'][0],t)
                        else:raise ValueError('Unknown observer route')
                        raw=canonical(value);mime='application/json'
                self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            except (BrokenPipeError,ConnectionResetError):pass
            except Exception as e:
                raw=str(e).encode();self.send_response(400);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return server,replay

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--port',type=int,default=8816);p.add_argument('--live-url');a=p.parse_args()
    class ReadOnlyObserver:
        def ask(self,kind):
            if kind!='frame':raise ValueError('Observer only supports frames')
            if not a.live_url.startswith('http://127.0.0.1:'):raise ValueError('Local observer URL required')
            with urllib.request.urlopen(a.live_url+'/frame',timeout=4) as r:return json.load(r)
    server,replay=serve(a.root,controller=ReadOnlyObserver() if a.live_url else None,port=a.port);print('http://127.0.0.1:'+str(server.server_port),flush=True)
    try:threading.Event().wait()
    except KeyboardInterrupt:
        server.shutdown();server.server_close()
        if replay:replay.close()
