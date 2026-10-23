"""Trusted continuous simulation, task lifecycle, recording and deferred hibernation."""
from __future__ import annotations
import base64
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import queue
import secrets
import shutil
import threading
import time
import traceback
import uuid
import numpy as np
from common import HERE,read,save,canonical,Events,sha,inventory
from world import World
from recording import Recorder,geoms,verify_checkpoint,publish_checkpoint,verify_prefix
from schedule import validate

class Controller:
    def __init__(self,root,schedule,config,condition,stage='engineering',checkpoint=None):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.schedule=schedule;self.schedule_hash=validate(schedule)
        self.config=config;self.condition=condition;self.stage=stage
        self.mail=queue.Queue(maxsize=64);self.stop=threading.Event();self.ready=threading.Event()
        self.robot_token=secrets.token_urlsafe(32);self.images={};self.used_requests=set()
        self.index=0;self.sessions=0;self.phase='between_sessions';self.completed=[];self.session_success=False
        self.world=None;self.events=None;self.recorder=None;self.error=None;self.checkpoint_input=checkpoint
        self.session_active=False;self.last_activity=None
        self.server=None;self.owner=None
        self.clock_epoch=uuid.uuid4().hex

    def ask(self,kind,payload=None):
        result=queue.Queue(1);self.mail.put((kind,payload,result),timeout=5)
        ok,value=result.get(timeout=300 if kind in ('finish','pause_boundary') else 20)
        if not ok:raise ValueError(value)
        return value

    def _record(self,kind,payload):return self.events.emit(kind,self.world.time,payload)

    def _state(self):
        return dict(schema='apartment-continuation-1',stage=self.stage,condition=self.condition,phase=self.phase,
            schedule_sha256=self.schedule_hash,position=self.index,sessions=self.sessions,completed=self.completed,
            session_success=self.session_success,config=self.config,world=self.world.snapshot(),
            event_sequence=self.events.sequence,event_chain=self.events.chain,clock_epoch=self.clock_epoch,
            timing_authority='simulation elapsed time and per-epoch monotonic clocks; wall timestamps are descriptive')

    def _checkpoint(self,reason='hibernation'):
        if self.session_active or self.phase!='between_sessions':raise ValueError('Only clean session boundaries may checkpoint')
        self.recorder.sample(self.world.data,force=True);self.recorder.flush()
        self._record('boundary_checkpoint',dict(session=self.sessions,position=self.index,reason=reason));self.events.flush()
        return publish_checkpoint(self.root,self._state(),reason)

    def _handle(self,kind,p):
        w=self.world
        if kind=='public':
            method,path,body=p
            if path=='/status':return dict(ok=True,**w.public_status())
            if not self.session_active:raise ValueError('Robot session is not active')
            if path=='/observe' and method=='POST':
                e=w.capture(body.get('camera','head_rgbd'));self.images[e['sequence']]=e['rgb']
                path=self.root/'sensors'/('frame-'+str(e['sequence']).zfill(7)+'.png');path.parent.mkdir(exist_ok=True)
                path.write_bytes(e['rgb']);packet=w.sensor_packet(e)
                self._record('sensor_capture',dict(sequence=e['sequence'],camera=e['camera'],image_sha256=sha(path),packet=packet,session=self.sessions))
                return dict(ok=True,**packet)
            if path=='/command' and method=='POST':
                rid=body['request_id']
                if not isinstance(rid,str) or not 1<=len(rid)<=128 or rid in self.used_requests:raise ValueError('Unique bounded request ID required')
                self.used_requests.add(rid)
                if body.get('kind')=='sense_point':
                    q=body['parameters'];return dict(ok=True,point=w.sensed_point(q['observation_sequence'],q['u'],q['v']))
                self._record('command_requested',dict(session=self.sessions,request=body))
                w.command(body)
                self._record('command_admitted',dict(session=self.sessions,request_id=rid))
                return dict(ok=True,request_id=rid,accepted=True)
            raise ValueError('Route unavailable')
        if kind=='image':
            raw=self.images[int(p)];self._record('image_delivered',dict(sequence=int(p),sha256=hashlib.sha256(raw).hexdigest(),session=self.sessions))
            return raw
        if kind=='start':
            if self.session_active or self.index>=21:raise ValueError('No next session may start')
            if w.assignment is None or w.assignment['position']!=self.index:w.setup_assignment(self.schedule['assignments'][self.index])
            self.sessions+=1;self.session_active=True;self.phase='active';self.session_success=False
            profile=self.config['throw_work_s'] if w.assignment['kind']=='throwing' else self.config['normal_work_s']
            w.begin_session(profile,self.config['reserve_s']);self.used_requests.clear();self.images.clear()
            self._record('session_started',dict(session=self.sessions,assignment_position=self.index,task=w.assignment['kind'],work_s=profile))
            return dict(session=self.sessions,assignment=w.task_text(),battery=w.battery())
        if kind=='finish':
            if not self.session_active or not w.docked or w.active:raise ValueError('Clean docking and session closeout required')
            if not p['normal_model_completion'] or not p['filesystem_closeout'] or not p['runtime_retired']:raise ValueError('Incomplete model/filesystem/runtime session termination')
            self.session_active=False;self.phase='between_sessions'
            completed=self.session_success or w.assignment['kind']=='throwing'
            if completed:
                self.completed.append(dict(position=self.index,kind=w.assignment['kind'],session=self.sessions,sim_time=w.time))
                self.index+=1
            self._record('session_closed',dict(session=self.sessions,assignment_advanced=completed,next_position=self.index,proof=p))
            self.recorder.flush();self.events.flush();save(self.root/'boundary-state.json',self._state())
            reason='completed' if self.index==21 else ('hibernation' if (self.root/'hibernate-requested.json').exists() else 'normal-session-boundary')
            checkpoint=self._checkpoint(reason)
            if self.index==21:
                save(self.root/'completed.json',dict(sessions=self.sessions,assignments=21,condition=self.condition,checkpoint=checkpoint))
                self.stop.set();return dict(hibernated=False,complete=True,checkpoint=checkpoint)
            if (self.root/'hibernate-requested.json').exists():
                self.stop.set();return dict(hibernated=True,checkpoint=checkpoint)
            return dict(hibernated=False,complete=False,checkpoint=checkpoint)
        if kind=='private':return self._state()
        if kind=='pause_boundary':
            if self.sessions<1:raise ValueError('No completed boundary available before the first session')
            checkpoint=self._checkpoint('hibernation');self.stop.set()
            return dict(hibernated=True,checkpoint=checkpoint)
        if kind=='clock':return dict(sim_time=w.time,windows_monotonic_ns=time.perf_counter_ns(),clock_epoch=self.clock_epoch,session=self.sessions,phase=self.phase)
        if kind=='frame':return dict(sim_time=w.time,robot=w.body('base').tolist(),geoms=geoms(w.model,w.data),
            session=self.sessions,condition=self.condition,stage=self.stage,phase=self.phase,battery=w.battery(),
            pending_hibernation=(self.root/'hibernate-requested.json').exists(),assignment=w.task_text(),position=self.index,
            activity=self.last_activity)
        if kind=='activity':self.last_activity=p;return {'ok':True}
        if kind=='fixture':
            if self.stage!='engineering':raise ValueError('Fixture operations unavailable to official runs')
            from engineering import relocate_for_fixture
            relocate_for_fixture(w,*p);return {'ok':True}
        if kind=='fixture_advance_time':
            if self.stage!='engineering':raise ValueError('Engineering only')
            w.step(int(p/w.model.opt.timestep));self.recorder.sample(w.data,force=True)
            return {'ok':True}
        if kind=='fixture_success_latch':
            if self.stage!='engineering':raise ValueError('Engineering only')
            self.session_success=True;return {'ok':True}
        if kind=='stop':self.stop.set();return {'ok':True}
        raise ValueError('Unknown controller request')

    def _run(self):
        try:
            self.world=World();self.events=Events(self.root/'events.jsonl',self.clock_epoch);self.recorder=Recorder(self.root/'replay',self.world.model,self.clock_epoch)
            if self.checkpoint_input:
                verify_checkpoint(self.checkpoint_input);state=read(Path(self.checkpoint_input)/'state.json')
                if 'event_prefix_sha256' in state:verify_prefix(self.root,self.checkpoint_input)
                if state['condition']!=self.condition or state['schedule_sha256']!=self.schedule_hash or state['config']!=self.config:
                    raise ValueError('Checkpoint comparison identity mismatch')
                if self.events.sequence!=state['event_sequence'] or self.events.chain!=state['event_chain']:
                    raise ValueError('Log continuation does not match checkpoint tail')
                if (self.root/'events.jsonl').stat().st_size!=state['log_bytes'] or sha(self.root/'replay/index.json')!=state['replay_index_sha256']:
                    raise ValueError('Replay/log continuation changed')
                if inventory(self.root/'filesystem')!=inventory(Path(self.checkpoint_input)/'filesystem'):
                    raise ValueError('Persistent filesystem differs from checkpoint')
                if (Path(self.checkpoint_input)/'filesystem-namespace.json').exists():
                    required=inventory(Path(self.checkpoint_input)/'filesystem-objects');available=inventory(self.root/'filesystem-objects')
                    if sha(self.root/'filesystem-namespace.json')!=sha(Path(self.checkpoint_input)/'filesystem-namespace.json') or any(available.get(k)!=v for k,v in required.items()):
                        raise ValueError('Persistent inode namespace differs from checkpoint')
                self.world.restore(state['world']);self.index=state['position'];self.sessions=state['sessions'];self.completed=state['completed']
                self.session_success=state['session_success']
                self._record('resumed',dict(checkpoint=str(self.checkpoint_input),session=self.sessions,position=self.index))
            else:self._record('initialized',dict(condition=self.condition,stage=self.stage,schedule_sha256=self.schedule_hash))
            self.ready.set();wall=time.monotonic();last_action=None
            while not self.stop.is_set():
                for _ in range(16):
                    try:kind,p,result=self.mail.get_nowait()
                    except queue.Empty:break
                    try:result.put((True,self._handle(kind,p)))
                    except Exception as e:result.put((False,str(e)))
                if self.session_active:
                    # Fixed real-time target with bounded catch-up; wall stalls are logged, never hidden.
                    now=time.monotonic();count=min(25,max(0,int((now-wall)/self.world.model.opt.timestep)))
                    if count:
                        if now-wall>.5:self._record('owner_wall_lag',dict(seconds=now-wall))
                        self.world.step(count);wall+=count*self.world.model.opt.timestep;self.recorder.sample(self.world.data)
                        if self.world.last_action!=last_action:
                            last_action=self.world.last_action
                            if last_action:self._record('command_terminal',last_action)
                        if not self.session_success and self.world.evaluate():
                            self.session_success=True;self._record('task_success',dict(position=self.index,session=self.sessions))
                        if self.world.battery()['return_seconds_remaining']<=0:raise RuntimeError('Battery reserve exhausted; invalid stop, no schedule advancement')
                else:wall=time.monotonic()
                time.sleep(.001)
        except BaseException as error:
            self.error=repr(error);save(self.root/'controller-failure.json',dict(error=repr(error),traceback=traceback.format_exc()))
            self.ready.set();self.stop.set()
        finally:
            if self.recorder:self.recorder.flush()
            if self.events:self.events.close()
            if self.world:self.world.close()

    def start(self):
        self.owner=threading.Thread(target=self._run,name='apartment-physics-owner',daemon=True);self.owner.start()
        if not self.ready.wait(30) or self.error:raise RuntimeError(self.error or 'Owner startup deadline')
        outer=self
        class Gateway(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):self.route()
            def do_POST(self):self.route()
            def route(self):
                try:
                    if not secrets.compare_digest(self.headers.get('X-Robot-Capability',''),outer.robot_token):raise ValueError('Denied')
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<=length<=65536 or self.headers.get('Transfer-Encoding'):raise ValueError('Body bound')
                    body=json.loads(self.rfile.read(length)) if length else {}
                    value=outer.ask('public',(self.command,self.path,body));code=200
                except Exception as error:value=dict(ok=False,error=str(error));code=400
                raw=canonical(value);self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Gateway)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        return dict(url='http://127.0.0.1:'+str(self.server.server_port),capability=self.robot_token,authority_epoch=1)

    def close(self):
        self.stop.set()
        if self.server:self.server.shutdown();self.server.server_close()
        if self.owner:self.owner.join(30)
        if self.owner and self.owner.is_alive():raise RuntimeError('Owner did not retire')
