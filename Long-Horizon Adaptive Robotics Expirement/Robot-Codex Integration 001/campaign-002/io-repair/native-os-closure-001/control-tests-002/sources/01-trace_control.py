"""Fixed authenticated control messages for one bounded diagnostic observer.

Control files carry lifecycle metadata, never model outputs or packet data.
"""
import ctypes as C
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
import time

HERE=Path(__file__).resolve().parent
IO=HERE.parent
sys.path.insert(0,str(IO/'admin-coverage-automation-002'))
import owned_process as owner

RUN='RCI001-C02-shutdown-diagnostic-005'
REVISION='RCI001-C02-dev-097'
CONTROL=Path(r'C:\Users\cresp\Documents\Campaign002 TCP Trace\native-closure-20260930-001')
SESSION='C02NativeClosure005'
PHASES={'helper-ready','start','started','stop','finished'}


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def save(path,value):
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())


def config(root=CONTROL,expected_sha=None):
    root=Path(root).resolve();path=root/'config.json'
    raw=path.read_bytes()
    if len(raw)>65536 or (expected_sha and hashlib.sha256(raw).hexdigest()!=expected_sha):
        raise ValueError('Configuration size or binding differs')
    value=json.loads(raw)
    if (set(value)!={'run','revision','control_root','session','guid','key','created_filetime','sources'} or
            value['run']!=RUN or value['revision']!=REVISION or value['session']!=SESSION or
            Path(value['control_root']).resolve()!=root or len(bytes.fromhex(value['key']))!=32 or
            type(value['created_filetime']) is not int):
        raise ValueError('Unexpected fixed control configuration')
    value['_sha256']=hashlib.sha256(raw).hexdigest()
    return value


def verify_sources(value,expected):
    if set(value['sources'])!=set(map(str,expected)):
        raise ValueError('Exact observer source inventory required')
    for path in expected:
        path=Path(path)
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=value['sources'][str(path)]:
            raise ValueError('Frozen observer source changed: '+path.name)


def emit(root,phase,payload,value):
    if phase not in PHASES or not isinstance(payload,dict):
        raise ValueError('Unknown fixed control phase')
    body={'phase':phase,'run':RUN,'revision':REVISION,'config_sha256':value['_sha256'],
          'observed_perf_counter_ns':time.perf_counter_ns(),'payload':payload}
    body['mac']=hmac.new(bytes.fromhex(value['key']),canonical(body),hashlib.sha256).hexdigest()
    save(Path(root)/(phase+'.json'),body)
    return {k:v for k,v in body.items() if k!='mac'}


def receive(root,phase,value):
    if phase not in PHASES: raise ValueError('Unknown fixed phase')
    path=Path(root)/(phase+'.json')
    try:
        raw=path.read_bytes()
    except FileNotFoundError:
        return None
    if len(raw)>8192: raise ValueError('Control message exceeds bound')
    try:
        body=json.loads(raw)
    except (json.JSONDecodeError,UnicodeDecodeError):
        return None  # A single exclusive writer may still be flushing its file.
    if not isinstance(body,dict) or set(body)!={'phase','run','revision','config_sha256','observed_perf_counter_ns','payload','mac'}:
        raise ValueError('Control message field inventory differs')
    mac=body.pop('mac')
    expected=hmac.new(bytes.fromhex(value['key']),canonical(body),hashlib.sha256).hexdigest()
    if (not isinstance(mac,str) or not hmac.compare_digest(mac,expected) or body['phase']!=phase or
            body['run']!=RUN or body['revision']!=REVISION or body['config_sha256']!=value['_sha256'] or
            type(body['observed_perf_counter_ns']) is not int or not isinstance(body['payload'],dict)):
        raise ValueError('Control message authentication or identity failed')
    return body


class RetainedProcess:
    def __init__(self,identity,value):
        self.handle=None
        if not isinstance(identity,dict) or type(identity.get('pid')) is not int or identity['pid']<=0:
            raise ValueError('Exact positive PID identity required')
        handle=owner.checked(owner.K.OpenProcess(0x101000,False,identity['pid']))
        try:
            actual=owner.describe(handle,identity['pid'])
            if (actual!=identity or actual['creation_filetime']<value['created_filetime'] or
                    Path(actual['image']).resolve() not in {Path(sys.executable).resolve(),Path(sys._base_executable).resolve()} or
                    owner.K.WaitForSingleObject(handle,0)!=258):
                raise ValueError('Process image, creation identity or liveness differs')
            self.handle=handle;self.identity=actual
        finally:
            if self.handle is None: owner.checked(owner.K.CloseHandle(handle))
    def exited(self):
        status=owner.K.WaitForSingleObject(self.handle,0)
        if status not in (0,258): raise RuntimeError('Process liveness unknown')
        return status==0
    def close(self):
        if self.handle is not None:
            owner.checked(owner.K.CloseHandle(self.handle));self.handle=None


def own_identity():
    handle=owner.checked(owner.K.OpenProcess(0x101000,False,os.getpid()))
    try: return owner.describe(handle,os.getpid())
    finally: owner.checked(owner.K.CloseHandle(handle))


class Client:
    def __init__(self,root=CONTROL,ready_timeout=45,expected_sha=None):
        self.root=Path(root);self.value=config(self.root,expected_sha);self.peer=None
        self.attempted=False;self.armed=False;self.stop_sent=False;self.events=[]
        deadline=time.monotonic()+ready_timeout
        while time.monotonic()<deadline:
            message=receive(self.root,'helper-ready',self.value)
            if message:
                if message['payload'].get('session')!=SESSION or message['payload'].get('simulated') is not False:
                    raise ValueError('Live helper identity required')
                self.peer=RetainedProcess(message['payload']['identity'],self.value)
                break
            time.sleep(.02)
        else: raise TimeoutError('Trace observer not ready before model launch')
    def start(self):
        if self.attempted: raise RuntimeError('Second capture arm refused')
        self.attempted=True
        if self.peer.exited(): raise RuntimeError('Trace observer exited before arming')
        self.events.append(emit(self.root,'start',{'identity':own_identity()},self.value))
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            message=receive(self.root,'started',self.value)
            if message:
                if message['payload'].get('active') is not True or message['payload'].get('guid')!=self.value['guid']:
                    raise ValueError('Trace start acknowledgment differs')
                self.events.append(message);self.armed=True;return
            if self.peer.exited(): raise RuntimeError('Trace observer exited during arming')
            time.sleep(.005)
        raise TimeoutError('Trace did not acknowledge within3seconds')
    def finish(self):
        try:
            if not self.stop_sent:
                self.stop_sent=True
                self.events.append(emit(self.root,'stop',{'identity':own_identity()},self.value))
            deadline=time.monotonic()+6
            while time.monotonic()<deadline:
                message=receive(self.root,'finished',self.value)
                if message:
                    self.events.append(message)
                    if message['payload'].get('collection_completed') is not True:
                        raise RuntimeError('Trace observer reported incomplete collection')
                    return message
                if self.peer and self.peer.exited(): raise RuntimeError('Trace observer exited without completion message')
                time.sleep(.01)
            raise TimeoutError('Trace retirement not confirmed within6seconds')
        finally:
            if self.peer: self.peer.close()


def wrap_transition(original,capture,events):
    """Arm at most once; trace errors never skip the existing retirement call."""
    attempted=False
    def transition(endpoint,operation,*args,**kwargs):
        nonlocal attempted
        if operation=='retire-invocation' and not attempted:
            attempted=True
            before=time.perf_counter_ns();error=None
            try: capture.start()
            except Exception as exc: error={'type':type(exc).__name__,'message':str(exc)[:300]}
            events.append({'phase':'trace_arm','before_perf_counter_ns':before,
                'after_perf_counter_ns':time.perf_counter_ns(),'error':error})
        return original(endpoint,operation,*args,**kwargs)
    return transition
