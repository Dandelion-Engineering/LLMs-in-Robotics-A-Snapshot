"""Three fixed no-model channel diagnostics; never launch during unit tests.

Only the explicit CLI runner creates Runtime/native fixtures. assess() is an
independent read-only replay, called after the external official queue gate.
"""
import argparse
import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
REPO = HERE.parents[3]
SCHEMA = 'campaign002-codehost-channel-probe-3'
CASES = ('multi_channel','foreign_owner','in_flight_eof')
CASE_CAP_SECONDS = 180
IDLE_SECONDS = 95
CASE_BYTES = 32 * 1024 * 1024
CLIENT_BYTES = 1024 * 1024
CLIENT_EXECUTABLE = Path('C:/Users/cresp/AppData/Local/Programs/Python/Python312/python.exe')
CLIENT_EXECUTABLE_BYTES = 104952
CLIENT_EXECUTABLE_SHA256 = '4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a'
PREFACE = b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'
SETTINGS = b'\x00\x00\x00\x04\x00\x00\x00\x00\x00'
SETTINGS_ACK = b'\x00\x00\x00\x04\x01\x00\x00\x00\x00'
PARTIAL = b'\x00\x00\x08'
PARTIAL_INPUT = PREFACE + SETTINGS + SETTINGS_ACK + PARTIAL


def require(value, message):
    if value is not True: raise ValueError(message)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()


def digest(raw): return hashlib.sha256(raw).hexdigest()


def binding(path):
    raw=Path(path).read_bytes();return {'sha256':digest(raw),'bytes':len(raw)}


def save(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(value,indent=2,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())


def append(path,value):
    with Path(path).open('ab') as stream:
        stream.write(canonical(value)+b'\n');stream.flush();os.fsync(stream.fileno())


def client_executable():
    """The fixed stdlib child runs directly, never through a venv redirector."""
    declared=CLIENT_EXECUTABLE.resolve(strict=True)
    base=Path(sys._base_executable).resolve(strict=True)
    require(os.path.normcase(str(base))==os.path.normcase(str(declared)),
            'Project base interpreter differs from declared probe interpreter')
    identity=dependency('codehost_owner').file_identity(declared)
    require(identity['bytes']==CLIENT_EXECUTABLE_BYTES and identity['sha256']==CLIENT_EXECUTABLE_SHA256
            and os.path.normcase(identity['path'])==os.path.normcase(str(declared)),
            'Declared probe interpreter bytes differ')
    return identity


def dependency(name):
    for directory in (HERE,CAMPAIGN/'assessment'):
        if str(directory) not in sys.path:sys.path.insert(0,str(directory))
    return __import__(name)


def make_cases():
    return [{'case':name,'maximum_elapsed_seconds':CASE_CAP_SECONDS,'maximum_output_bytes':CASE_BYTES,
             'model_calls':0,'physical_simulation':False,'expected_failure':name!='multi_channel',
             'minimum_idle_seconds':IDLE_SECONDS if name=='multi_channel' else None,
             'pending_read_shutdown_control':{'bytes':len(SHUTDOWN_GOAWAY),'sha256':digest(SHUTDOWN_GOAWAY)} if name=='multi_channel' else None}
            for name in CASES]


def required_sources():
    paths=dependency('raw_event_preflight_v2').required_sources()
    extra=[HERE/'codehost_transport_probe_v3.py',HERE/'test_codehost_transport_probe_v3.py',
           HERE/'test_codehost_owner.py',HERE/'test_codehost_bridge_v3.py',
           HERE/'test_codehost_mux_protocol.py',HERE/'test_codehost_inside_v3.py',
           CAMPAIGN/'assessment/test_transport_integrity_v3.py',
           CAMPAIGN/'io-repair/CHANNEL_PROBE_PROCESS_IDENTITY_V1.md',
           CAMPAIGN/'io-repair/CHANNEL_FINISH_FRONTIER_VALIDATION_V1.md',
           CAMPAIGN/'io-repair/CHANNEL_OWNER_DRAIN_V1.md',
           CAMPAIGN/'io-repair/CHANNEL_PROBE_SEQUENCE_SYNCHRONIZATION_V1.md']
    return sorted(set(paths+[p.relative_to(REPO).as_posix() for p in extra]))


def validate_snapshot(snapshot,revision=None):
    frozen=dependency('raw_event_preflight_v2').validate_snapshot(snapshot,revision)
    for name in required_sources():
        p=REPO/name
        require(p.is_file() and not p.is_symlink() and frozen.get('sources',{}).get(name)==binding(p),
                'Missing or changed channel-probe source: '+name)
    return frozen


def frame(kind,flags=0,payload=b''):
    return len(payload).to_bytes(3,'big')+bytes([kind,flags])+b'\0'*4+payload


class SyntheticChannel:
    def __init__(self,port,channel_id,emit):
        self.id=channel_id;self.emit=emit
        self.sock=socket.create_connection(('127.0.0.1',port),8);self.sock.settimeout(8)
        self.sent=self.received=0;self.tx=hashlib.sha256();self.rx=hashlib.sha256()
        self.client=list(self.sock.getsockname());self.server=list(self.sock.getpeername())
        self.frames=[];self.closed=False
        emit('channel_connected',channel_id=self.id,client=self.client,server=self.server)

    def send(self,raw):
        self.sock.sendall(raw);self.sent+=len(raw);self.tx.update(raw)

    def exact(self,count):
        out=bytearray()
        while len(out)<count:
            value=self.sock.recv(count-len(out))
            if not value:raise ValueError('Synthetic H2 peer EOF')
            out.extend(value);self.received+=len(value);self.rx.update(value)
        return bytes(out)

    def read_frame(self):
        header=self.exact(9);length=int.from_bytes(header[:3],'big')
        require(length<=65536 and int.from_bytes(header[5:],'big')==0,'Unexpected synthetic H2 frame')
        payload=self.exact(length)
        require(header[3] in (4,6,7,8),'Unexpected synthetic H2 application frame')
        self.frames.append({'type':header[3],'flags':header[4],'bytes':length,'sha256':digest(payload)})
        require(len(self.frames)<=32,'Synthetic frame-count bound')
        return header[3],header[4],payload

    def handshake(self,ping):
        self.send(PREFACE+SETTINGS)
        kind,flags,payload=self.read_frame()
        require(kind==4 and flags==0 and len(payload)%6==0,'Native SETTINGS absent')
        self.send(SETTINGS_ACK)
        got_ack=False;got_ping=not ping
        marker=b'C02V3H2!'
        if ping:self.send(frame(6,payload=marker))
        for _ in range(12):
            kind,flags,payload=self.read_frame()
            if kind==4 and flags==1 and not payload:got_ack=True
            elif kind==6 and flags==1 and payload==marker:got_ping=True
            elif kind==8 and len(payload)==4:pass
            else:raise ValueError('Unexpected synthetic H2 handshake')
            if got_ack and got_ping:break
        require(got_ack and got_ping,'Incomplete synthetic H2 handshake')
        self.emit('channel_handshake',channel_id=self.id,ping_acknowledged=ping)

    def close_idle(self):
        self.sock.shutdown(socket.SHUT_WR)
        while value:=self.sock.recv(65536):
            self.received+=len(value);self.rx.update(value)
            require(self.received<=CLIENT_BYTES,'Synthetic peer byte bound')
        self.sock.close();self.closed=True
        self.emit('channel_closed',channel_id=self.id,clean_idle=True)

    def summary(self):
        return {'channel_id':self.id,'client':self.client,'server':self.server,
                'sent':{'bytes':self.sent,'sha256':self.tx.hexdigest()},
                'received':{'bytes':self.received,'sha256':self.rx.hexdigest()},
                'closed_before_finish':self.closed,'frames':list(self.frames)}


SHUTDOWN_GOAWAY = bytes.fromhex('0000080700000000000000000000000000')

def client_phase(phase,emit,**fields):
    """One fixed child IPC request; grants cannot be replayed across phases."""
    nonce=os.urandom(16).hex();pid=os.getpid()
    emit('probe_phase_request',phase=phase,nonce=nonce,pid=pid,**fields)
    command=json.loads(sys.stdin.readline(1024))
    require(isinstance(command,dict) and set(command)=={'phase','nonce','pid','grant'}
            and command['phase']==phase and command['nonce']==nonce
            and type(command['pid']) is int and command['pid']==pid and command['grant'] is True,
            'Fixed probe phase grant identity differs')


def client_main(mode):
    """Fixed trusted Python client; stdin control only supplies a private port."""
    def emit(kind,**value):
        print(canonical({'kind':kind,'wall_unix_s':time.time(),'monotonic_s':time.monotonic(),**value}).decode(),flush=True)
    require(mode in (*CASES,'hold','foreign','boundary_single_channel'),'Unknown fixed client mode')
    emit('client_ready',pid=os.getpid(),mode=mode)
    command=json.loads(sys.stdin.readline(1024))
    require(set(command)=={'port'} and type(command['port']) is int and 0<command['port']<65536,'Fixed client port control')
    channels=[];result={'ready_to_finish':True,'channels':[]}
    try:
        if mode=='hold':pass
        elif mode=='foreign':
            sock=socket.create_connection(('127.0.0.1',command['port']),8);sock.settimeout(8)
            client,server=list(sock.getsockname()),list(sock.getpeername())
            emit('foreign_connected',client=client,server=server,attempted_payload_bytes=0)
            denied=sock.recv(1)==b'';sock.close()
            require(denied,'Foreign owner was not denied before payload')
            result.update(client=client,server=server,attempted_payload_bytes=0,denial_eof_observed=True)
            emit('foreign_denied',**result)
        else:
            channel=SyntheticChannel(command['port'],1,emit);channels.append(channel)
            channel.handshake(ping=mode in ('multi_channel','boundary_single_channel'))
            if mode=='multi_channel':
                started=time.monotonic();emit('idle_started',channel_id=1)
                time.sleep(IDLE_SECONDS)
                while time.monotonic()-started<IDLE_SECONDS:time.sleep(0)
                idle_observed=time.monotonic();result['idle_seconds']=idle_observed-started
                emit('idle_finished',channel_id=1,elapsed_seconds=result['idle_seconds'])
                client_phase('open_second',emit,idle_started_monotonic_s=started,
                             idle_observed_monotonic_s=idle_observed,idle_seconds=result['idle_seconds'])
                second=SyntheticChannel(command['port'],2,emit);channels.append(second);second.handshake(True);second.close_idle()
                client_phase('open_third',emit)
                third=SyntheticChannel(command['port'],3,emit);channels.append(third);third.handshake(True)
                client_phase('finish',emit)
            elif mode=='boundary_single_channel':
                started=time.monotonic();emit('idle_started',channel_id=1)
                time.sleep(1);result['idle_seconds']=time.monotonic()-started
                emit('idle_finished',channel_id=1,elapsed_seconds=result['idle_seconds'])
            elif mode=='in_flight_eof':
                channel.send(PARTIAL);emit('partial_frame_sent',channel_id=1,bytes=len(PARTIAL),sha256=digest(PARTIAL))
                channel.sock.shutdown(socket.SHUT_WR)
                emit('client_eof_before_owner_finish',channel_id=1)
                while value:=channel.sock.recv(65536):
                    channel.received+=len(value);channel.rx.update(value)
                    require(channel.received<=CLIENT_BYTES,'Synthetic peer byte bound')
                channel.sock.close();channel.closed=True
                result.update(partial_header_bytes=3,client_eof_before_owner_finish=True)
            else:raise ValueError('Unknown fixed client mode')
            result['channels']=[c.summary() for c in channels]
        emit('ready_to_finish',result=result)
        require(json.loads(sys.stdin.readline(1024))=={'finish':True},'Fixed client finish control')
        emit('client_finishing')
        live=[channel for channel in channels if not channel.closed]
        if mode=='multi_channel':
            channels[0].send(SHUTDOWN_GOAWAY)
            emit('channel_shutdown_control',channel_id=1,bytes=len(SHUTDOWN_GOAWAY),sha256=digest(SHUTDOWN_GOAWAY))
        # Half-close every live upload before waiting for any peer EOF: sealing
        # requires EOF on all channels, so sequential half-close/drain deadlocks.
        for channel in live:channel.sock.shutdown(socket.SHUT_WR)
        for channel in live:
            while value:=channel.sock.recv(65536):
                channel.received+=len(value);channel.rx.update(value)
                require(channel.received<=CLIENT_BYTES,'Synthetic peer byte bound')
            channel.sock.close();channel.closed=True
        emit('client_closed')
        return 0
    finally:
        for channel in channels:
            channel.sock.close()


class ChildLog:
    def __init__(self,process,role,transcript,lock):
        self.process,self.role=process,role
        self.queue=queue.Queue(maxsize=128);self.bytes=0;self.error=None
        self.capture_lock=threading.Lock()
        self.captures={name:{'data':bytearray(),'bytes':0,'sha256':hashlib.sha256(),
                            'complete':False,'error_type':None} for name in ('stdout','stderr')}
        def capture(name,raw):
            with self.capture_lock:
                state=self.captures[name];state['bytes']+=len(raw);state['sha256'].update(raw)
                state['data'].extend(raw[:max(0,CLIENT_BYTES-len(state['data']))])
                if state['bytes']>CLIENT_BYTES:
                    state['error_type']='ValueError';self.error='ValueError'
        def failed(name,error):
            with self.capture_lock:
                self.captures[name]['error_type']=type(error).__name__;self.error=type(error).__name__
        def stdout():
            parsing=True
            try:
                while raw:=process.stdout.readline(16385):
                    capture('stdout',raw);self.bytes+=len(raw)
                    if not parsing:continue
                    try:
                        require(len(raw)<=16384 and raw.endswith(b'\n'),'Incomplete/bounded probe client line')
                        require(self.bytes<=CLIENT_BYTES,'Probe client output bound')
                        event=json.loads(raw)
                        require(isinstance(event,dict),'Probe client event type')
                        row={'schema':'campaign002-channel-probe-transcript-3','role':role,'event':event,'received_wall_unix_s':time.time()}
                        with lock:append(transcript,row)
                        self.queue.put_nowait(event)
                    except Exception as error:failed('stdout',error);parsing=False
                with self.capture_lock:self.captures['stdout']['complete']=True
            except BaseException as error:failed('stdout',error)
        def stderr():
            try:
                while raw:=process.stderr.read(65536):
                    capture('stderr',raw)
                with self.capture_lock:self.captures['stderr']['complete']=True
            except BaseException as error:failed('stderr',error)
        self.workers=[threading.Thread(target=fn,daemon=True) for fn in (stdout,stderr)]
        for worker in self.workers:worker.start()

    async def event(self,kind,deadline):
        while time.monotonic()<deadline:
            if self.error:raise ValueError(self.error)
            try:value=self.queue.get_nowait()
            except queue.Empty:
                if self.process.poll() is not None:raise ValueError('Probe process exited before '+kind)
                await asyncio.sleep(.01);continue
            if kind=='client_ready':require(value.get('kind')==kind,'Probe first event must be client_ready')
            if kind=='probe_phase_request':
                require(value.get('kind') not in ('ready_to_finish','client_finishing','client_closed'),
                        'Probe completed before its fixed phase request')
            elif value.get('kind')=='probe_phase_request':raise ValueError('Unsolicited probe phase request')
            if value.get('kind')==kind:return value
        raise TimeoutError('Probe client deadline')

    def finish(self,root,redact):
        """Retain bounded sanitized diagnostics before reporting any failure."""
        for worker in self.workers:worker.join(timeout=2)
        errors=[];streams={}
        if any(w.is_alive() for w in self.workers):errors.append({'error_type':'TimeoutError','reason':'incomplete_drains'})
        with self.capture_lock:
            states={name:{**state,'data':bytes(state['data']),'sha256':state['sha256'].hexdigest()}
                    for name,state in self.captures.items()}
        for name,state in states.items():
            raw=state['data'];truncated=state['bytes']!=len(raw) or not state['complete']
            complete_lines=raw[:raw.rfind(b'\n')+1] if truncated and not raw.endswith(b'\n') else raw
            decode_error=None;redaction_error=None
            try:text=complete_lines.decode('utf-8',errors='strict')
            except UnicodeDecodeError:
                decode_error='UnicodeDecodeError';text=complete_lines.decode('utf-8',errors='replace')
            try:
                safe=redact(text);require(isinstance(safe,str),'Invalid probe diagnostic redaction')
            except Exception as error:
                redaction_error=type(error).__name__;safe='[PROBE DIAGNOSTIC WITHHELD: REDACTION FAILED]\n'
            encoded=safe.encode('utf-8');safe_raw=encoded[:CLIENT_BYTES].decode('utf-8',errors='ignore').encode('utf-8')
            relative=f'client/{self.role}-{name}.txt'
            with (Path(root)/relative).open('xb') as stream:
                stream.write(safe_raw);stream.flush();os.fsync(stream.fileno())
            streams[name]={'path':relative,**binding(Path(root)/relative),'raw_bytes':state['bytes'],
                           'raw_sha256':state['sha256'],'captured_prefix_bytes':len(raw),
                           'capture_complete':state['complete'],'error_type':state['error_type'],
                           'truncated':truncated or len(encoded)>CLIENT_BYTES,'redacted':safe_raw!=raw,
                           'decode_error_type':decode_error,'redaction_error_type':redaction_error,
                           'discarded_partial_tail_bytes':len(raw)-len(complete_lines)}
            if state['error_type'] or not state['complete'] or truncated or decode_error or redaction_error or safe_raw!=raw:
                errors.append({'error_type':state['error_type'] or decode_error or redaction_error or 'ValueError',
                               'reason':name+'_capture_not_exact'})
            if name=='stderr' and state['bytes']:
                errors.append({'error_type':'ValueError','reason':'unexpected_stderr'})
        return {'role':self.role,'complete':not errors,'errors':errors,'streams':streams,
                'scope':'Raw hashes cover observed bytes; incomplete drains do not prove a complete stream.'}


def live_bridge(runtime):
    module=dependency('codehost_bridge_v3')
    callback=runtime.native_process_ready;bridge=getattr(callback,'__self__',None)
    require(type(bridge) is module.Bridge and getattr(callback,'__func__',None) is module.Bridge.register_native
            and bridge.fixture is runtime and type(bridge.ledger) is module.Ledger,
            'Probe synchronization requires the actual live bridge callback')
    return module,bridge


def retained_bridge_rows(module,bridge):
    """Read exact bounded post-fsync event bytes while the append lock is held."""
    with bridge.ledger.lock:
        rows=list(bridge.ledger.events)
        with bridge.ledger.path.open('rb') as stream:raw=stream.read(module.MAX_LEDGER_BYTES+1)
        require(len(raw)<=module.MAX_LEDGER_BYTES and len(rows)<=module.MAX_METADATA_RECORDS
                and raw==b''.join(module.mux.canonical(row)+b'\n' for row in rows),
                'Probe synchronization ledger differs from retained producer events')
        previous=None
        for sequence,row in enumerate(rows,1):
            value={key:item for key,item in row.items() if key!='record_sha256'}
            require(row.get('schema')=='campaign002-codehost-transport-3' and type(row.get('sequence')) is int
                    and row['sequence']==sequence and row.get('previous_sha256')==previous
                    and row.get('record_sha256')==digest(module.mux.canonical(value)),
                    'Probe synchronization ledger hash chain differs')
            previous=row['record_sha256']
    return rows,{'path':bridge.ledger.path.name,'bytes':len(raw),'sha256':digest(raw)}


async def synchronize_in_flight_eof(runtime,owner,deadline):
    """Await this probe's durable rejection, then a genuinely later clock tick.

    The existing bridge abort event is a wake-up signal, never the evidence by
    itself. Ledger.events are appended only after the producer's fsync succeeds.
    No FINISH flag, timestamp or production acceptance rule is changed here.
    """
    module,bridge=live_bridge(runtime)
    cutoff=deadline-35;validated=False
    def expected_failure_state():
        failures=list(bridge.failures)
        if failures==['channel_ValueError']:
            require(not any(r['kind']=='namespace_finished' for r in bridge.ledger.events),
                    'Unbound early namespace terminal')
            return
        require(failures==['channel_ValueError','namespace_finished_unqualified'],
                'Unrelated bridge failure during probe synchronization')
        terminal=bridge.finished_metadata;channel=bridge.channels.get(1)
        rows=[r for r in bridge.ledger.events if r['kind']=='namespace_finished']
        require(isinstance(terminal,dict) and len(rows)==1 and rows[0].get('finished')==terminal
                and terminal.get('qualified') is False and terminal.get('reason')=='error'
                and terminal.get('error_type')=='ValueError' and terminal.get('drain_qualified') is False
                and terminal.get('drain_error_code')=='owner_drain_unqualified'
                and terminal.get('owner_finish_received') is False
                and terminal.get('channel_count')==terminal.get('channels_closed')==1
                and channel is not None and channel.state=='closed'
                and isinstance(channel.namespace_closed,dict)
                and channel.namespace_closed.get('qualified') is False
                and channel.namespace_closed.get('reason')=='error'
                and channel.namespace_closed.get('error_type')=='ValueError'
                and channel.meters['upload'].summary()=={'bytes':len(PARTIAL_INPUT),'sha256':digest(PARTIAL_INPUT)},
                'Early failed namespace terminal differs from fixed partial-EOF cleanup')
    def live():
        require(type(owner.pid) is int and owner.pid>0 and owner.poll() is None,
                'Probe synchronization owner is not alive')
        require(not runtime.client_finishing.is_set() and not bridge.finishing,
                'Probe synchronization cannot follow owner finishing')
        if validated:expected_failure_state()
        now=time.monotonic()
        require(type(now) in (int,float) and math.isfinite(now)
                and type(cutoff) in (int,float) and math.isfinite(cutoff),'Probe synchronization clock is malformed')
        if now>=cutoff:raise TimeoutError('Probe synchronization exhausted original cleanup reserve')
        return now
    started=live()
    if not runtime.abort_event.is_set():
        signalled=await asyncio.to_thread(runtime.abort_event.wait,cutoff-started)
        if not signalled:raise TimeoutError('Probe durable rejection was not observed before original deadline')
    observed=live()
    rows,prefix=retained_bridge_rows(module,bridge)
    auths=[row for row in rows if row.get('kind')=='channel_authenticated']
    eofs=[row for row in rows if row.get('kind')=='client_eof']
    failures=[row for row in rows if row.get('kind')=='failure']
    expected_failure_state()
    require(not any(row.get('kind') in ('channel_finish_frontier','owner_drain_begin','owner_finishing','owner_input_closed') for row in rows)
            and len(auths)==len(eofs)==1 and len(failures)==len(bridge.failures)
            and [r.get('reason') for r in failures]==bridge.failures,
            'Probe synchronization requires one specific pre-finish rejection')
    auth,eof,failure=auths[0],eofs[0],failures[0]
    require(type(auth.get('channel_id')) is int and auth['channel_id']==1
            and auth.get('authentication',{}).get('owner_pid')==owner.pid
            and type(eof.get('channel_id')) is int and eof['channel_id']==1
            and eof.get('client_finishing') is False and failure.get('reason')=='channel_ValueError'
            and auth['sequence']<eof['sequence']<failure['sequence']
            and set(bridge.channels)=={1} and bridge.channels[1].parent_eof==eof,
            'Probe synchronization EOF/failure identity or order differs')
    for row in (auth,eof,failure):
        require(type(row.get('monotonic_s')) in (int,float) and math.isfinite(row['monotonic_s']),
                'Probe synchronization receipt clock is malformed')
    require(auth['monotonic_s']<=eof['monotonic_s']<=failure['monotonic_s']<=observed,
            'Probe synchronization receipt clock is late or reordered')
    h2=eof.get('h2',{})
    require(h2.get('preface_complete') is True and h2.get('settings_complete') is True
            and h2.get('frames_complete') is False and h2.get('error') is None
            and type(h2.get('reset_streams')) is int and h2['reset_streams']==0
            and type(h2.get('bytes',{}).get('upload')) is int and h2['bytes']['upload']==len(PARTIAL_INPUT),
            'Probe synchronization lacks the fixed incomplete HTTP2 upload')
    validated=True
    while True:
        advanced=live()
        if advanced>eof['monotonic_s']:break
        await asyncio.sleep(0)
    def receipt(row):return {key:row[key] for key in ('sequence','record_sha256','monotonic_s')}
    return {'schema':'campaign002-probe-eof-synchronization-1','owner_pid':owner.pid,'channel_id':1,
            'eof':receipt(eof),'failure':receipt(failure),'failure_reason':failure['reason'],
            'retained_ledger_prefix':prefix,
            'started_monotonic_s':started,'clock_observed_monotonic_s':advanced,
            'synchronization_deadline_monotonic_s':cutoff}


async def synchronize_multi_phase(runtime,owner,deadline,request,phase,prior):
    phases=('open_second','open_third','finish')
    require(phase in phases and len(prior)==phases.index(phase)
            and [item.get('phase') for item in prior]==list(phases[:len(prior)]),'Fixed multi-channel phase order differs')
    fields={'kind','phase','nonce','pid','wall_unix_s','monotonic_s'}
    if phase=='open_second':fields|={'idle_started_monotonic_s','idle_observed_monotonic_s','idle_seconds'}
    require(isinstance(request,dict) and set(request)==fields and request['kind']=='probe_phase_request'
            and request['phase']==phase and type(request['pid']) is int and request['pid']==owner.pid
            and isinstance(request['nonce'],str) and len(request['nonce'])==32
            and all(c in '0123456789abcdef' for c in request['nonce'])
            and request['nonce'] not in {item.get('nonce') for item in prior},'Fixed multi-channel request identity differs')
    for field in ('wall_unix_s','monotonic_s'):
        require(type(request[field]) in (int,float) and math.isfinite(request[field]),'Malformed multi-channel request clock')
    if phase=='open_second':
        for field in ('idle_started_monotonic_s','idle_observed_monotonic_s','idle_seconds'):
            require(type(request[field]) in (int,float) and math.isfinite(request[field]),'Malformed original idle evidence')
        require(request['idle_seconds']==request['idle_observed_monotonic_s']-request['idle_started_monotonic_s']
                and request['idle_seconds']>=IDLE_SECONDS
                and request['idle_observed_monotonic_s']<=request['monotonic_s'],'Original 95-second child idle is absent')
    module,bridge=live_bridge(runtime);cutoff=deadline-35;expected=list(range(1,phases.index(phase)+2))
    while True:
        now=time.monotonic()
        require(type(now) in (int,float) and math.isfinite(now) and type(cutoff) in (int,float) and math.isfinite(cutoff),
                'Malformed multi-channel synchronization clock')
        if now>=cutoff:raise TimeoutError('Multi-channel synchronization exhausted original cleanup reserve')
        require(request['monotonic_s']<=now and type(owner.pid) is int and owner.pid>0 and owner.poll() is None,
                'Multi-channel owner or request clock is not live')
        require(not bridge.finishing and not runtime.client_finishing.is_set() and not runtime.abort_event.is_set()
                and not bridge.failures,'Multi-channel synchronization observed failure or finishing')
        rows,prefix=retained_bridge_rows(module,bridge)
        require(not any(row.get('kind') in ('failure','channel_denied','channel_finish_frontier','owner_finishing',
                    'owner_input_closed','namespace_finished') for row in rows),'Multi-channel ledger has failure or finishing')
        auths=[row for row in rows if row.get('kind')=='channel_authenticated']
        closed=[row for row in rows if row.get('kind')=='channel_closed']
        ids=[row.get('channel_id') for row in auths];closed_ids=[row.get('channel_id') for row in closed]
        require(all(type(cid) is int for cid in ids+closed_ids) and ids==expected[:len(ids)]
                and len(ids)<=len(expected) and set(bridge.channels)==set(ids),
                'Multi-channel admitted set differs at fixed phase')
        require(closed_ids==([] if phase=='open_second' else [2]) or (phase!='open_second' and closed_ids==[]),
                'Multi-channel close set differs at fixed phase')
        require(all(cid in ids for cid in closed_ids),'Multi-channel closure precedes its admission')
        for row in auths+closed:
            require(type(row.get('monotonic_s')) in (int,float) and math.isfinite(row['monotonic_s'])
                    and row['monotonic_s']<=now,'Multi-channel retained event clock is malformed or late')
        for row in auths:
            require(row.get('authentication',{}).get('owner_pid')==owner.pid,'Multi-channel admission belongs to another owner')
        for cid in (1,3):
            if cid in bridge.channels:
                channel=bridge.channels[cid]
                require(not channel.closed.done() and channel.parent_eof is None and channel.namespace_closed is None,
                        'Long-lived multi-channel endpoint closed before its phase grant')
        if ids!=expected or (phase!='open_second' and not closed):
            await asyncio.sleep(0);continue
        if phase=='open_second':
            require(auths[0]['monotonic_s']<=request['idle_started_monotonic_s'],'Original child idle precedes channel1 admission')
        else:
            require(auths[1]['monotonic_s']-auths[0]['monotonic_s']>=IDLE_SECONDS
                    and prior[0]['grant_monotonic_s']<=auths[1]['monotonic_s'],
                    'Second admission preceded its declared idle grant')
        if phase!='open_second':
            close=closed[0];channel=bridge.channels[2];terminal=close.get('namespace_closed',{})
            require(auths[1]['sequence']<close['sequence'] and auths[1]['monotonic_s']<=close['monotonic_s']
                    and terminal==channel.namespace_closed
                    and terminal.get('qualified') is True and terminal.get('reason')=='clean_idle_eof'
                    and terminal.get('error_type') is None and channel.closed.done() and not channel.closed.cancelled()
                    and channel.closed.exception() is None,'Channel2 lacks the exact durable clean idle closure')
            if phase=='finish':
                require(close['sequence']<auths[2]['sequence'] and close['monotonic_s']<auths[2]['monotonic_s']
                        and prior[1]['grant_monotonic_s']<=auths[2]['monotonic_s'],
                        'Third admission preceded its strictly later close2 grant')
        reference=auths[0] if phase=='open_second' else closed[0] if phase=='open_third' else auths[2]
        ready=(now-reference['monotonic_s']>=IDLE_SECONDS if phase=='open_second' else now>reference['monotonic_s'])
        if not ready:await asyncio.sleep(0);continue
        return {'schema':'campaign002-probe-phase-synchronization-1','phase':phase,'nonce':request['nonce'],
                'owner_pid':owner.pid,'request':request,'admitted_ids':ids,'closed_ids':closed_ids,
                'reference':{key:reference[key] for key in ('kind','channel_id','sequence','record_sha256','monotonic_s')},
                'retained_ledger_prefix':prefix,'clock_observed_monotonic_s':now,
                'synchronization_deadline_monotonic_s':cutoff}


async def synchronize_shutdown_read(runtime,owner,deadline):
    """Release the fixed shutdown control only after the real phase-one ACK."""
    module,bridge=live_bridge(runtime)
    require(runtime.client_finishing.is_set() and owner.poll() is None,'Shutdown intent/owner absent')
    while not bridge.finishing:
        require(time.monotonic()<deadline-10 and not runtime.abort_event.is_set(),'Shutdown observer deadline/failure')
        await asyncio.sleep(0)
    cutoff=min(deadline-10,bridge.drain['deadline_monotonic_s'])
    require(time.monotonic()<cutoff,'Shutdown acknowledgment deadline')
    await asyncio.wait_for(asyncio.shield(bridge.drain_ack),cutoff-time.monotonic())
    rows,prefix=retained_bridge_rows(module,bridge)
    front=[r for r in rows if r['kind']=='channel_finish_frontier' and r['channel_id']==1]
    acknowledgments=[r for r in rows if r['kind']=='owner_drain_ack']
    begins=[r for r in rows if r['kind']=='owner_drain_begin']
    require(len(front)==len(acknowledgments)==len(begins)==1 and front[0].get('upload_read_pending') is True
            and front[0]['sequence']<begins[0]['sequence']<acknowledgments[0]['sequence']
            and not bridge.failures and not runtime.abort_event.is_set() and not bridge.sealed
            and set(bridge.channels)=={1,2,3} and bridge.channels[1].upload_read_pending
            and bridge.channels[1].state=='live' and owner.poll() is None,
            'Original pending read or acknowledged drain absent')
    granted=time.monotonic();require(granted<cutoff,'Shutdown grant deadline')
    return {'schema':'campaign002-pending-read-shutdown-1','frontier':front[0],
            'drain_begin':begins[0],'acknowledgment':acknowledgments[0],
            'retained_ledger_prefix':prefix,'grant_monotonic_s':granted,
            'deadline_monotonic_s':cutoff,'shutdown_bytes':len(SHUTDOWN_GOAWAY),
            'shutdown_sha256':digest(SHUTDOWN_GOAWAY)}


def verify_pending_shutdown(client,receipt,events):
    proof=client.get('pending_read_shutdown');require(isinstance(proof,dict),'Pending shutdown proof absent')
    require(proof.get('schema')=='campaign002-pending-read-shutdown-1'
            and proof.get('shutdown_bytes')==len(SHUTDOWN_GOAWAY)
            and proof.get('shutdown_sha256')==digest(SHUTDOWN_GOAWAY),'Fixed shutdown identity absent')
    for key,kind in [('frontier','channel_finish_frontier'),('drain_begin','owner_drain_begin'),('acknowledgment','owner_drain_ack')]:
        row=proof.get(key);require(isinstance(row,dict) and row.get('kind')==kind
                                and [r for r in events if r.get('sequence')==row.get('sequence')]==[row],
                                'Shutdown protected event differs')
    front,begin,ack=proof['frontier'],proof['drain_begin'],proof['acknowledgment']
    require(front.get('channel_id')==1 and front.get('upload_read_pending') is True
            and front['sequence']<begin['sequence']<ack['sequence']
            and ack['monotonic_s']<=proof['grant_monotonic_s']<=proof['control_sent_monotonic_s']<proof['deadline_monotonic_s']
            <=client['finish']['monotonic_s']+25,'Pending shutdown chronology differs')
    prefix=proof['retained_ledger_prefix'];raw=b''.join(canonical(row)+b'\n' for row in events)
    require(prefix.get('path')=='codehost-transport-v3.jsonl' and type(prefix.get('bytes')) is int
            and 0<prefix['bytes']<=len(raw) and digest(raw[:prefix['bytes']])==prefix.get('sha256'),
            'Shutdown protected prefix differs')
    tail=[r for r in events if r['kind']=='frame' and r['direction']=='outgoing' and r['frame_type']==3
          and r['channel_id']==1 and r['sequence']>front['sequence']]
    offset=0
    for row in tail:
        part=SHUTDOWN_GOAWAY[offset:offset+row['payload_bytes']]
        require(row['sequence']>ack['sequence'] and len(part)==row['payload_bytes']
                and digest(part)==row['payload_sha256'],'Shutdown byte slice differs')
        offset+=len(part)
    require(offset==len(SHUTDOWN_GOAWAY),'Fixed shutdown bytes incomplete')
    channel=next(c for c in receipt['channels'] if c['channel_id']==1)
    require(channel['meters']['client_read']['bytes']-front['h2']['bytes']['upload']==len(SHUTDOWN_GOAWAY),
            'Shutdown observed byte accounting differs')
    return proof


async def drive_clients(url,runtime,case,deadline):
    require(case in (*CASES,'boundary_single_channel'),'Undeclared client workload')
    require(time.monotonic()<deadline-35,'No bounded client/cleanup time remaining')
    if case=='multi_channel':require(time.monotonic()+IDLE_SECONDS<deadline-35,'No declared idle interval budget')
    root=Path(runtime.evidence);(root/'client').mkdir(exist_ok=False)
    transcript=root/'client-transcript.jsonl';lock=threading.Lock()
    children=[];logs=[];identities={};result=None;finish=None;executable=None
    errors=[];diagnostics={};failure=None;synchronization=None;multi_synchronization=[];shutdown_synchronization=None
    owner_api=dependency('codehost_owner')
    port=urlsplit(url).port
    require(url.startswith('http://127.0.0.1:') and type(port) is int,'Fixed bridge endpoint')
    def start(role,mode):
        require(client_executable()==executable,'Probe interpreter changed before child launch')
        process=subprocess.Popen([executable['path'],'-X','utf8','-B',str(Path(__file__).resolve()),'--client',mode],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        children.append(process)
        log=ChildLog(process,role,transcript,lock);logs.append(log)
        observed=owner_api.WindowsOwnerAPI().process(process.pid)
        require(type(process.pid) is int and process.pid>0 and observed['pid']==process.pid
                and process.poll() is None and os.path.normcase(observed['queried_executable_path'])==os.path.normcase(executable['path']),
                'Probe OS process executable differs from direct child')
        observed['executable']=dict(executable)
        identities[role]=observed
        return process,log
    async def ready(process,log,mode):
        event=await log.event('client_ready',deadline-35)
        require(event.get('kind')=='client_ready' and type(event.get('pid')) is int
                and event['pid']==process.pid and event.get('mode')==mode and process.poll() is None,
                'Probe first ready PID/mode differs from actual live Popen')
    def control(process,value):
        process.stdin.write(canonical(value)+b'\n');process.stdin.flush()
    def error(stage,exc):errors.append({'stage':stage,'error_type':type(exc).__name__})
    try:
        executable=client_executable();save(root/'client-executable.json',executable)
        owner_mode='hold' if case=='foreign_owner' else case
        owner,owner_log=start('owner',owner_mode)
        await ready(owner,owner_log,owner_mode)
        owner_receipt=runtime.native_process_ready(owner,executable['path'])
        save(root/'client/native-owner.json',owner_receipt)
        owner_binding=binding(root/'client/native-owner.json')
        append(root/'client/events.jsonl',{'kind':'native_process_owner_registered',
            'receipt_sha256':owner_binding['sha256'],'receipt_bytes':owner_binding['bytes']})
        control(owner,{'port':port})
        active_log=owner_log
        if case=='foreign_owner':
            await owner_log.event('ready_to_finish',deadline-35)
            sibling,sibling_log=start('foreign','foreign')
            require(sibling.pid!=owner.pid,'Foreign probe role reused owner PID')
            await ready(sibling,sibling_log,'foreign')
            control(sibling,{'port':port});active_log=sibling_log
        if case=='multi_channel':
            for phase in ('open_second','open_third','finish'):
                request=await owner_log.event('probe_phase_request',deadline-35)
                proof=await synchronize_multi_phase(runtime,owner,deadline,request,phase,multi_synchronization)
                grant={'phase':phase,'nonce':request['nonce'],'pid':owner.pid,'grant':True}
                granted=time.monotonic()
                require(proof['clock_observed_monotonic_s']<=granted<proof['synchronization_deadline_monotonic_s']
                        and owner.poll() is None,'Actual multi-channel grant is late or owner exited')
                control(owner,grant)
                multi_synchronization.append({**proof,'grant':grant,'grant_monotonic_s':granted})
        result=(await active_log.event('ready_to_finish',deadline-35))['result']
        if case=='in_flight_eof':synchronization=await synchronize_in_flight_eof(runtime,owner,deadline)
    except Exception as exc:
        failure=exc;error('client_drive',exc)
    finally:
        finish={'kind':'client_finishing_before_close','schema':'campaign002-client-finishing-1',
                'wall_unix_s':time.time(),'monotonic_s':time.monotonic()}
        try:
            if synchronization is not None:
                require(finish['monotonic_s']>synchronization['eof']['monotonic_s']
                        and synchronization['clock_observed_monotonic_s']<=finish['monotonic_s']
                        <synchronization['synchronization_deadline_monotonic_s'],
                        'Actual probe FINISH clock does not strictly follow the retained EOF')
            if case=='multi_channel' and len(multi_synchronization)==3:
                final=multi_synchronization[-1]
                require(final['reference']['monotonic_s']<finish['monotonic_s']
                        and final['grant_monotonic_s']<=finish['monotonic_s']<final['synchronization_deadline_monotonic_s'],
                        'Actual multi-channel FINISH does not strictly follow third admission')
            append(root/'client/events.jsonl',finish)
            with lock:append(transcript,{'schema':'campaign002-channel-probe-transcript-3','role':'controller','event':finish,'received_wall_unix_s':time.time()})
            runtime.client_finishing.set()
        except Exception as exc:error('durable_finishing',exc)
        if case=='multi_channel' and failure is None and not errors:
            try:shutdown_synchronization=await synchronize_shutdown_read(runtime,owner,deadline)
            except Exception as exc:error('shutdown_synchronization',exc)
        for process in children:
            if process.poll() is None:
                try:
                    control(process,{'finish':True})
                    if process is owner and shutdown_synchronization is not None:
                        sent=time.monotonic()
                        require(shutdown_synchronization['grant_monotonic_s']<=sent<shutdown_synchronization['deadline_monotonic_s'],
                                'Actual shutdown control grant is late')
                        shutdown_synchronization['control_sent_monotonic_s']=sent
                except Exception as exc:error('finish_control',exc)
        for process in children:
            try:
                try:await asyncio.to_thread(process.wait,timeout=3)
                except subprocess.TimeoutExpired as exc:
                    error('child_wait',exc);process.terminate()
                    try:await asyncio.to_thread(process.wait,timeout=3)
                    except subprocess.TimeoutExpired:process.kill();await asyncio.to_thread(process.wait,timeout=3)
            except Exception as exc:error('child_cleanup',exc)
        for log in logs:
            try:
                detail=await asyncio.to_thread(log.finish,root,runtime.redact)
                diagnostics[log.role]=detail
                errors.extend({'stage':log.role+'_diagnostic',**item} for item in detail['errors'])
            except Exception as exc:error(log.role+'_diagnostic_persistence',exc)
        exits={log.role:log.process.returncode for log in logs}
        clean_exits=bool(children) and len(exits)==len(children) and all(type(v)is int and v==0 for v in exits.values())
        if not clean_exits:errors.append({'stage':'child_exit','error_type':'ValueError'})
        try:
            append(root/'client/events.jsonl',{'kind':'probe_client_closed','schema':'campaign002-h2-probe-client-1',
                'closed':clean_exits,'wall_unix_s':time.time(),'monotonic_s':time.monotonic()})
        except Exception as exc:error('durable_closed',exc)
        record={'schema':'campaign002-channel-client-3','case':case,'completed':result is not None and clean_exits and not errors,
                 'owner':identities.get('owner'),'sibling':identities.get('foreign'),'result':result,
                 'child_exit_codes':exits,'finish':finish,'model_calls':0,'launch_executable':executable,
                 'error_type':errors[0]['error_type'] if errors else None,'errors':errors,'diagnostics':diagnostics,
                 'in_flight_synchronization':synchronization,'multi_channel_synchronization':multi_synchronization,'pending_read_shutdown':shutdown_synchronization}
        save(root/'client-result.json',record)
    if failure is not None:raise failure
    require(record['completed'],'Fixed synthetic client did not complete')
    injection={}
    if case=='foreign_owner':
        injection={'sibling_process':identities['foreign'],'client':result['client'],'server':result['server'],
                   'attempted_payload_bytes':0,'denial_eof_observed':result['denial_eof_observed']}
    elif case=='in_flight_eof':
        injection={'channel_id':1,'fixed_upload_bytes':len(PARTIAL_INPUT),'fixed_upload_sha256':digest(PARTIAL_INPUT),
                   'partial_header_bytes':3,'client_eof_before_owner_finish':result['client_eof_before_owner_finish']}
    save(root/'diagnostic-case.json',{'schema':'campaign002-transport-v3-case-1','case':case,'owner_kind':'transport_probe',
        'model_calls':0,'physical_simulation':False,'expected_failure':case in ('foreign_owner','in_flight_eof'),'injection':injection,
        'client_transcript':{'path':'client-transcript.jsonl',**binding(transcript)},
        'client_result':{'path':'client-result.json',**binding(root/'client-result.json')}})
    return record


async def boundary_probe(fixture):
    """One fixed H2 channel; caller independently verifies and retires Runtime."""
    fixture.native_owner_kind='transport_probe'
    started=time.monotonic()
    async def callback(url):
        return await drive_clients(url,fixture,'boundary_single_channel',started+CASE_CAP_SECONDS)
    record=await dependency('codehost_bridge_v3').run(fixture,callback)
    require(record.get('completed')is True and time.monotonic()-started<=CASE_CAP_SECONDS,
            'Boundary channel diagnostic incomplete or over cap')
    result=record['result']
    require(len(result['channels'])==1 and result['idle_seconds']>=1,'Boundary fixed workload absent')
    return {'qualified':True,'schema':'campaign002-boundary-channel-probe-3','model_calls':0,
            'physical_simulation':False,'case':'boundary_single_channel',
            'client_result':{'path':'client-result.json',**binding(Path(fixture.evidence)/'client-result.json')},
            'client_transcript':{'path':'client-transcript.jsonl',**binding(Path(fixture.evidence)/'client-transcript.jsonl')},
            'scope':'Fixed authenticated H2 settings/PING channel; no model, gRPC tool call or physical simulation.'}


def run_case(root,case):
    runtime_module=dependency('runtime')
    runtime=runtime_module.Runtime.__new__(runtime_module.Runtime)
    started=time.monotonic();wall=time.time();deadline=started+CASE_CAP_SECONDS
    outcome={'schema':'campaign002-channel-case-run-3','case':case,'start_wall_unix_s':wall,
             'start_monotonic_s':started,'case_cap_seconds':CASE_CAP_SECONDS,'cleanup_clean':False,
             'bridge_completed':False,'bridge_error_type':None,'setup_error_type':None}
    try:
        runtime_module.Runtime.__init__(runtime,root,runtime_module.template('bootstrap'))
        runtime.native_owner_kind='transport_probe'
        runtime.qualify();outcome['canaries_completed']=True
        require(time.monotonic()<deadline-35,'Diagnostic setup exhausted case budget')
        async def callback(url):return await drive_clients(url,runtime,case,deadline)
        try:
            asyncio.run(dependency('codehost_bridge_v3').run(runtime,callback))
            outcome['bridge_completed']=True
        except Exception as error:outcome['bridge_error_type']=type(error).__name__
    except Exception as error:outcome['setup_error_type']=type(error).__name__
    finally:
        try:outcome['cleanup_clean']=runtime.close()
        except Exception as error:outcome['cleanup_error_type']=type(error).__name__
        outcome.update(end_monotonic_s=time.monotonic(),end_wall_unix_s=time.time())
        outcome['elapsed_seconds']=outcome['end_monotonic_s']-started
        if root.exists():save(root/'case-run.json',outcome)
    return outcome


def canary_evidence(reader,prefix):
    canary=reader.json(prefix+'/canary-stdout.json')
    require(canary.get('qualified')is True and len(canary.get('checks',{}))==45
            and all(value is True for value in canary['checks'].values()),'Unchanged boundary canaries incomplete')
    host=reader.json(prefix+'/codehost-canary-stdout.json');checks=host.get('checks',{})
    require(host.get('host_qualified')is True and type(host.get('model_calls'))is int and host['model_calls']==0
            and host.get('enabled_tools')==[] and checks.get('tools')==[]
            and type(checks.get('all_tools_count'))is int and checks['all_tools_count']==0
            and checks.get('constructor_process_type')=='undefined'
            and set(checks.get('apis',{}))=={'process','require','fetch','Deno','Bun','WebSocket','XMLHttpRequest'}
            and all(v=='undefined' for v in checks['apis'].values())
            and set(checks.get('imports',{}))=={'node:fs','file:///etc/passwd','https://example.invalid/'}
            and all(v=='denied' for v in checks['imports'].values()),'Unchanged codehost canaries incomplete')


def assess(output,snapshot):
    output=Path(output).resolve();snapshot=Path(snapshot).resolve()
    reader=dependency('raw_event_preflight_v2').Reader(output)
    errors={};checks={};cases=[];source={};frozen={}
    try:
        source=reader.json('source-binding.json');frozen=validate_snapshot(snapshot,source.get('framework_revision'))
        require(source.get('schema')=='campaign002-channel-probe-source-3' and source.get('snapshot_sha256')==binding(snapshot)['sha256']
                and canonical(source.get('cases'))==canonical(make_cases()) and type(source.get('model_calls'))is int and source['model_calls']==0
                and source.get('physical_simulation')is False and canonical(source.get('source_bindings'))==canonical(frozen['sources'])
                and isinstance(source.get('run_id'),str) and bool(source['run_id']),
                'Probe source/declaration binding differs')
        checks['source_identity']=True
    except Exception as error:checks['source_identity']=False;errors['source_identity']=str(error)
    if checks['source_identity']:
        verifier=dependency('transport_integrity_v3')
        for name in CASES:
            row={'case':name,'passed':False,'production_qualified':False}
            try:
                folder=output/name
                require(folder.is_dir() and not folder.is_symlink(),'Missing ordinary case directory')
                files=list(folder.rglob('*'))
                require(all(not p.is_symlink() for p in files),'Linked case evidence')
                require(sum(p.stat().st_size for p in files if p.is_file())<=CASE_BYTES,'Case output bound')
                run=reader.json(name+'/case-run.json');client=reader.json(name+'/client-result.json')
                cleanup=reader.json(name+'/cleanup.json')
                canary_evidence(reader,name)
                require(run.get('schema')=='campaign002-channel-case-run-3' and run.get('case')==name
                        and run.get('cleanup_clean')is True and cleanup.get('clean')is True and cleanup.get('errors')==[]
                        and run.get('setup_error_type')is None and run.get('canaries_completed')is True,
                        'Case setup/cleanup failed')
                elapsed=run.get('elapsed_seconds')
                require(type(elapsed) in (int,float) and math.isfinite(elapsed) and 0<elapsed<=CASE_CAP_SECONDS
                        and elapsed==run['end_monotonic_s']-run['start_monotonic_s'],'Case time cap')
                require(client.get('schema')=='campaign002-channel-client-3' and client.get('case')==name
                        and client.get('completed')is True and type(client.get('model_calls'))is int and client['model_calls']==0
                        and set(client.get('child_exit_codes',{}))==({'owner','foreign'} if name=='foreign_owner' else {'owner'})
                        and all(type(v)is int and v==0 for v in client.get('child_exit_codes',{}).values()),'Client completion identity')
                if name=='multi_channel':
                    proof=verifier.verify_transport_integrity(folder,frozen,owner_kind='transport_probe')
                    require(proof.get('passed')is True and run.get('bridge_completed')is True and run.get('bridge_error_type')is None,
                            'Ordinary three-channel transport did not pass')
                    idle=client['result']['idle_seconds'];channels=client['result']['channels']
                    require(type(idle)in(int,float) and math.isfinite(idle) and idle>=IDLE_SECONDS
                            and [c['channel_id'] for c in channels]==[1,2,3]
                            and channels[1].get('closed_before_finish')is True
                            and channels[0].get('closed_before_finish')is False
                            and channels[2].get('closed_before_finish')is False,'Fixed multi-channel workload absent')
                    receipt=reader.json(name+'/codehost-owner-bridge-v3.json')
                    require(type(receipt.get('accepted'))is int and receipt['accepted']==3
                            and type(receipt.get('denied'))is int and receipt['denied']==0,'Three authenticated channels absent')
                    raw=reader.raw(name+'/codehost-transport-v3.jsonl')
                    require(raw.endswith(b'\n'),'Incomplete transport ledger')
                    events=[json.loads(line) for line in raw.splitlines()]
                    accepted=[e for e in events if e.get('kind')=='channel_authenticated']
                    closed=[e for e in events if e.get('kind')=='channel_closed']
                    require([e['channel_id'] for e in accepted]==[1,2,3],'Admission order differs')
                    close_by_id={e['channel_id']:e for e in closed}
                    require(accepted[1]['monotonic_s']-accepted[0]['monotonic_s']>=IDLE_SECONDS
                            and close_by_id[2]['monotonic_s']<accepted[2]['monotonic_s']<close_by_id[1]['monotonic_s'],
                            'Long-lived first channel or close-then-open sequence absent')
                    require(next(c for c in receipt['channels'] if c['channel_id']==2)['namespace_closed']['reason']=='clean_idle_eof',
                            'Second channel did not close cleanly before finish')
                    verify_pending_shutdown(client,receipt,events)
                    row['production_qualified']=True
                else:
                    proof=verifier.verify_expected_failure(folder,frozen,case=name)
                    require(proof.get('expected_failure_verified')is True and proof.get('diagnostic_only')is True
                            and proof.get('ordinary_transport_passed')is False and run.get('bridge_completed')is False
                            and run.get('bridge_error_type')=='RuntimeError','Expected failure not independently established')
                require(isinstance(proof.get('input_bindings'),dict) and bool(proof['input_bindings']),
                        'Dependent transport proof lacks evidence bindings')
                for path,expected in proof['input_bindings'].items():
                    raw=reader.raw(name+'/'+path)
                    require({'sha256':digest(raw),'bytes':len(raw)}==expected,'Dependent transport proof changed')
                row.update(passed=True,elapsed_seconds=elapsed,transport_proof=proof)
            except Exception as error:row['error']=str(error);errors[name]=str(error)
            cases.append(row)
    checks['three_fixed_cases']=len(cases)==3 and [c['case'] for c in cases]==list(CASES)
    checks['all_cases_verified']=checks['three_fixed_cases'] and all(c['passed']is True for c in cases)
    return {'schema':SCHEMA,'passed':all(checks.values()),'run_id':source.get('run_id'),
            'framework_revision':source.get('framework_revision'),'snapshot_sha256':binding(snapshot)['sha256'],
            'model_calls':0,'physical_simulation':False,'checks':checks,'cases':cases,'inputs':reader.inputs,'errors':errors,
            'scope':'Synthetic isolated channel diagnostic, including expected production failures; not native pool reproduction, model read, robot or task evidence.'}


def run(args):
    snapshot=args.snapshot.resolve();frozen=validate_snapshot(snapshot,args.framework_revision)
    require(isinstance(args.run_id,str) and bool(args.run_id),'Missing run identity')
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    save(output/'source-binding.json',{'schema':'campaign002-channel-probe-source-3','run_id':args.run_id,
        'framework_revision':args.framework_revision,'snapshot_sha256':binding(snapshot)['sha256'],
        'source_bindings':frozen['sources'],'cases':make_cases(),'model_calls':0,'physical_simulation':False})
    for case in CASES:run_case(output/case,case)
    result=assess(output,snapshot);save(output/'result.json',result)
    print(json.dumps({'passed':result['passed'],'result':str(output/'result.json'),'model_calls':0}))
    return 0 if result['passed'] else 1


def main():
    if len(sys.argv)==3 and sys.argv[1]=='--client':return client_main(sys.argv[2])
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',type=Path,required=True)
    parser.add_argument('--framework-revision',required=True)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--output',type=Path,required=True)
    return run(parser.parse_args())


if __name__=='__main__':raise SystemExit(main())
