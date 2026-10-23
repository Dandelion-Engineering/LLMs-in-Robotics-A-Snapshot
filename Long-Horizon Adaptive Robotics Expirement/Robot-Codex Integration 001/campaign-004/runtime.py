"""Trusted Windows orchestration; no host credentials enter the Linux workspace."""
from __future__ import annotations
import argparse
import asyncio
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

HERE = Path(__file__).resolve().parent
INTEGRATION = HERE.parent
SESSION = INTEGRATION / 'readiness-session-10'
REPO = INTEGRATION.parents[1]
S9 = INTEGRATION / 'isolation-session-9'
BOUNDARY = SESSION / 'boundary'
DISTRO = 'Ubuntu-24.04'
RUNTIME_ROOT = '/var/tmp/robot-codex-session10'
sys.path.insert(0, str(S9 / 'wsl'))
sys.path.insert(0, str(BOUNDARY))
sys.path.insert(0, str(INTEGRATION / 'host'))
sys.path.insert(0, str(INTEGRATION / 'campaign-002/harness'))

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

prior = load('session9_qualification', S9 / 'wsl/qualification.py')
bootstrap = load('campaign004_bootstrap', HERE / 'bootstrap_client.py')
captured_executor = load('campaign002_executor_capture', HERE / 'executor_capture.py')
with_codehost = load('campaign002_codehost_bridge_v3', INTEGRATION / 'campaign-002/harness/codehost_bridge_v3.py').run

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')
        stream.flush()
        os.fsync(stream.fileno())

def linux(script, *args, payload=None, timeout=30):
    result = subprocess.run(['wsl.exe', '-d', DISTRO, '--', 'python3', '-B', '-c', script, *map(str,args)],
        input=None if payload is None else json.dumps(payload), capture_output=True,
        text=True, encoding='utf-8', timeout=timeout)
    if result.returncode:
        raise RuntimeError('Linux trusted operation failed: ' + result.stderr[-3000:])
    return result.stdout

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
MIRROR_RECORD_LIMIT = 16384
MIRROR_LOG_LIMIT = 16 * 1024 * 1024
MIRROR_BODY_LIMIT = 4096

def mirror_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')

def request(origin, token, method, path, body=None, *, operator=False):
    raw = None if body is None else json.dumps(body, allow_nan=False).encode()
    req = urllib.request.Request(origin + path, data=raw, method=method,
        headers={('X-Robot-Operator-Capability' if operator else 'X-Robot-Capability'): token,
                 'Content-Type': 'application/json'})
    try:
        response = OPENER.open(req, timeout=8)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read(1048577)
        if len(raw) > 1048576: raise RuntimeError('Gateway reply exceeds 1MiB')
        return response.code, json.loads(raw)

class Runtime:
    def __init__(self, evidence, files, endpoint, block, session_id, host_workspace=None, image_sensor=None):
        self.evidence = Path(evidence)
        self.evidence.mkdir(parents=True, exist_ok=False)
        self.root = self.evidence / 'control'
        self.root.mkdir()
        self.block=block; self.session_id=session_id; self.image_sensor=image_sensor
        self.run = block.run
        self.workspace = self.run + '/workspace'
        self.socket = self.run + '/gateway.sock'
        self.files = dict(files)
        self.host_workspace = host_workspace
        self.bridge_idle = asyncio.Event(); self.bridge_idle.set()
        self.abort_event = threading.Event()
        self.authority_revoked = threading.Event()
        self.revocation_lock = threading.Lock()
        self.client_finishing = threading.Event()
        self.stop = threading.Event()
        self.gateway = self.owner = self.broker = None
        self.mirror_thread = self.broker_thread = None
        self.broker_calls = []
        self.tokens = []
        self.personal_canary = None
        self.retired = False
        if endpoint is None:
            from run_host import HttpGateway
            from supervisor import Supervisor, Journal
            from test_supervisor import FakeAdapter, Candidate, packet
            self.adapter = FakeAdapter()
            self.journal = Journal(self.root / 'protected', self.root / 'runtime', 'readiness-synthetic')
            self.host = Supervisor(self.adapter, Candidate('baseline', self.root / 'baseline', True), self.journal)
            self.host.update_observation(packet())
            self.host.activate('Readiness filesystem bootstrap; no physical robot')
            self.gateway = HttpGateway(self.journal.workspace)
            self.gateway.rotate(self.host.epoch); self.gateway.start()
            endpoint = {'url': 'http://127.0.0.1:' + str(self.gateway.server.server_port),
                        'capability': self.gateway.capability, 'authority_epoch': self.host.epoch}
            def owner():
                while not self.stop.wait(.01): self.gateway.process(self.host)
            self.owner = threading.Thread(target=owner, daemon=True); self.owner.start()
        self.endpoint = dict(endpoint)
        self.token = endpoint['capability']; self.tokens.append(self.token)
        self.local_token='local-workspace-capability'
        self.files['live/endpoint.json'] = json.dumps({**endpoint, 'schema':'robot-codex-host-1.0','url':'http://127.0.0.1:38117','capability':self.local_token})
        personal = Path(os.environ['USERPROFILE']) / 'Documents' / ('RobotCodex-S10-Canary-' + uuid.uuid4().hex + '.txt')
        personal.write_text('Synthetic unrelated-user denial control; no secret.\n')
        self.personal_canary = personal
        repo_canary = self.evidence / 'repository-canary.txt'
        repo_canary.write_text('Synthetic repository denial control.\n')
        protected = {'repository_canary': prior.wsl_path(repo_canary), 'unrelated_user_canary':prior.wsl_path(personal),
                     'evaluator_canary':self.run+'/protected/evaluator.txt', 'development_evidence_canary':self.run+'/protected/development.txt'}
        self.files['live/canaries.json'] = json.dumps({'protected':protected,'other_port':1})
        setup = '''import sys,json,pathlib,hashlib
sys.path.insert(0,sys.argv[1]); from runtime_layout import prepare_workspace
x=json.load(sys.stdin)
root=pathlib.Path(x['run']); (root/'protected').mkdir(exist_ok=True)
for n in ['evaluator.txt','development.txt']:(root/'protected'/n).write_text('Synthetic denied control')
print(json.dumps({'protected_exist':{k:pathlib.Path(v).is_file() for k,v in x['protected'].items()},'binary_sha256':hashlib.sha256(pathlib.Path(x['codex']).read_bytes()).hexdigest(),'codehost_sha256':hashlib.sha256(pathlib.Path(x['codehost']).read_bytes()).hexdigest()}))
'''
        block.begin_session(session_id,self.files)
        self.setup = json.loads(linux(setup, prior.wsl_path(BOUNDARY), payload={'run':self.run,'files':self.files,'protected':protected,
            'codex':prior.LINUX_CODEX,'codehost':prior.LINUX_CODEHOST}))
        if not all(self.setup['protected_exist'].values()) or self.setup['binary_sha256'] != prior.LINUX_SHA256 or self.setup['codehost_sha256'] != prior.CODEHOST_SHA256:
            raise RuntimeError('Positive controls or installed binary hashes failed')
        self.broker = subprocess.Popen(['wsl.exe','-d',DISTRO,'--','python3','-B',prior.wsl_path(BOUNDARY/'unix_broker.py'),self.socket,
            '--workspace',self.workspace], stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
        ready = json.loads(self.broker.stdout.readline())
        if not ready.get('ready'): raise RuntimeError('Fixed broker did not start')
        control = "import pathlib,json,socket,sys;p=pathlib.Path(sys.argv[1]);x=json.loads(p.read_text());x['other_port']=int(sys.argv[2]);p.write_text(json.dumps(x));s=socket.create_connection(('127.0.0.1',int(sys.argv[2])),2);s.close();print('passed')"
        self.setup['outside_loopback_control'] = 'passed' in linux(control,self.workspace+'/live/canaries.json',ready['other_port'])
        self.broker_thread = threading.Thread(target=self._broker_loop,daemon=True);self.broker_thread.start()
        self.mirror_thread=None
        if self.host_workspace:
            self.mirror_thread=threading.Thread(target=self._mirror_loop,daemon=True);self.mirror_thread.start()
        write_json(self.evidence/'runtime-input-hashes.json',{k:hashlib.sha256(v.encode()).hexdigest() for k,v in self.files.items() if k!='live/endpoint.json'})
        write_json(self.evidence/'runtime-location.json',{'run':self.run,'workspace':self.workspace,'durable_backing':True,'setup':self.setup})

    def _mirror_loop(self):
        script='''import pathlib,json,sys,os,uuid
root=pathlib.Path(sys.argv[1]); x=json.load(sys.stdin)
for name,content in x.items():
 p=root/name
 if name not in ['live/state.json','live/activation.json','live/observations/latest.json']:raise SystemExit('not a public mirror')
 p.parent.mkdir(parents=True,exist_ok=True); tmp=p.with_name(p.name+'.mirror-'+uuid.uuid4().hex);tmp.write_text(content);os.replace(tmp,p)
'''
        while not self.stop.is_set() and not self.authority_revoked.is_set():
            phase = 'request_context'
            context = reply = None
            try:
                initial = self.files.get('live/state.json', '{}')
                invocation = json.loads(initial).get('invocation') or {}
                pinned_id = invocation.get('invocation_id')
                if (invocation.get('state') != 'active'
                        or type(invocation.get('authority_epoch')) is not int
                        or type(self.endpoint.get('authority_epoch')) is not int
                        or invocation['authority_epoch'] != self.endpoint['authority_epoch']
                        or not isinstance(pinned_id,str) or not 0 < len(pinned_id) <= 128):
                    pinned_id = None  # Never manufacture an invocation binding from a response.
                context = {'schema':'campaign002-mirror-request-1', 'request_id':uuid.uuid4().hex,
                           'method':'GET', 'path':'/status', 'origin':'protected_host',
                           'pinned_invocation_id':pinned_id,
                           'pinned_authority_epoch':self.endpoint.get('authority_epoch'),
                           'initial_state_sha256':hashlib.sha256(initial.encode()).hexdigest(),
                           'request_wall_unix_s':time.time()}
                self._mirror_receipt('mirror-requests.jsonl', context)
                phase = 'upstream_request'
                status,value=request(self.endpoint['url'],self.token,'GET','/status')
                received = time.time()
                phase = 'reply_context'
                reply = {**context, 'schema':'campaign002-mirror-reply-1',
                         'response_wall_unix_s':received, 'status':status}
                retained = json.loads(self.redact(json.dumps(value, allow_nan=False)))
                raw = mirror_bytes(retained)
                reply.update(response_bytes=len(raw), response_sha256=hashlib.sha256(raw).hexdigest(),
                             response_retained=len(raw) <= MIRROR_BODY_LIMIT,
                             response=retained if len(raw) <= MIRROR_BODY_LIMIT else None)
                self._mirror_receipt('mirror-replies.jsonl', reply)
                phase = 'reply_validation'
                self._observe_revocation('GET', '/status', None, status, value, 'public_mirror',
                                         mirror_context=reply)
                if self.authority_revoked.is_set():return
                if status!=200 or not value.get('ok'):raise RuntimeError('Public mirror status failed')
                files={'live/state.json':json.dumps(value),'live/activation.json':json.dumps(value['activation']),
                       'live/observations/latest.json':json.dumps(value['packet'])}
                phase = 'mirror_publish'
                linux(script,self.workspace,payload=files,timeout=10)
            except Exception as error:
                # A mirror request may already be in flight when a separate
                # handback reply proves that this pinned authority was revoked.
                # Only that established revocation permits a nonfatal closure.
                with self.revocation_lock:
                    revoked = self.authority_revoked.is_set()
                receipt = {'wall_unix_s':time.time(), 'method':'GET', 'path':'/status',
                           'type':type(error).__name__, 'error':self.redact(str(error)),
                           'phase':phase,'authority_revocation_established':revoked,
                           'mirror_request':context, 'mirror_reply':reply}
                if revoked and phase == 'upstream_request' and isinstance(error,(urllib.error.URLError,TimeoutError,ConnectionError)):
                    write_json(self.evidence/'mirror-after-revocation.json',receipt)
                    return
                write_json(self.evidence/'mirror-error.json',receipt)
                self.abort_event.set();return
            self.stop.wait(.75)

    def _mirror_receipt(self, name, value):
        """Bounded protected metadata; never a capability-bearing endpoint."""
        raw = mirror_bytes(value) + b'\n'
        if len(raw) > MIRROR_RECORD_LIMIT:
            raise RuntimeError('Mirror receipt record limit exceeded')
        total = sum((self.evidence / n).stat().st_size for n in
                    ('mirror-requests.jsonl', 'mirror-replies.jsonl') if (self.evidence / n).exists())
        if total + len(raw) > MIRROR_LOG_LIMIT:
            raise RuntimeError('Mirror receipt aggregate limit exceeded')
        with (self.evidence / name).open('ab') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())

    def _append_receipt(self, name, value):
        with (self.evidence/name).open('a',encoding='utf-8') as stream:
            stream.write(self.redact(json.dumps(value))+'\n')
            stream.flush();os.fsync(stream.fileno())

    def _observe_revocation(self, method, path, payload, status, body, source, trace_id=None,
                            mirror_context=None):
        """Latch only a trusted reply proving this invocation lost authority.

        A local denial is never a host receipt. No successful note commit, model
        disposition, host outcome, or physical recovery is inferred here.
        """
        if not isinstance(body,dict):return
        reason = None
        error = body.get('error')
        if (status == 403 and body.get('ok') is False and isinstance(error,dict)
                and error.get('code') in ('unauthorized','invocation_retired')):
            reason = 'host_capability_denied'
        if (source == 'public_mirror' and method == 'GET' and path == '/status'
                and type(status) is int and status == 409 and body.get('ok') is False
                and isinstance(error,dict) and error.get('code') == 'stale_authentication'
                and isinstance(mirror_context,dict)
                and mirror_context.get('schema') == 'campaign002-mirror-reply-1'
                and mirror_context.get('response_retained') is True
                and mirror_context.get('response') == body
                and type(mirror_context.get('pinned_authority_epoch')) is int
                and mirror_context['pinned_authority_epoch'] == self.endpoint.get('authority_epoch')
                and isinstance(mirror_context.get('pinned_invocation_id'),str)
                and 0 < len(mirror_context['pinned_invocation_id']) <= 128):
            reason = 'host_epoch_denied'
        command = body.get('command')
        if (method == 'POST' and path == '/handback' and status == 200
                and isinstance(payload,dict) and isinstance(command,dict)
                and body.get('ok') is True and body.get('owner') == 'conventional'
                and type(self.endpoint.get('authority_epoch')) is int
                and type(body.get('authority_epoch')) is int
                and body['authority_epoch'] == self.endpoint['authority_epoch'] + 1
                and type(payload.get('authority_epoch')) is int
                and payload.get('authority_epoch') == self.endpoint['authority_epoch']
                and isinstance(payload.get('request_id'),str) and payload['request_id']
                and command.get('request_id') == payload['request_id']
                and command.get('kind') == 'handback'
                and command.get('phase') == 'terminal' and command.get('status') == 'completed'):
            reason = 'accepted_handback'
        if reason is None:return
        with self.revocation_lock:
            if self.authority_revoked.is_set():return
            receipt = {
                'wall_unix_s':time.time(), 'reason':reason, 'source':source,
                'trace_id':trace_id, 'method':method, 'path':path, 'status':status,
                'pinned_authority_epoch':self.endpoint.get('authority_epoch'),
                'response':json.loads(self.redact(json.dumps(body)))}
            if reason == 'host_epoch_denied':
                receipt['mirror_context'] = mirror_context
            write_json(self.evidence/'authority-revocation.json',receipt)
            self.authority_revoked.set()

    def _broker_loop(self):
        from gateway_policy import validate_request
        for line in self.broker.stdout:
            trace = {'trace_id':uuid.uuid4().hex, 'received_wall_unix_s':time.time()}
            try:
                try:
                    data = validate_request(json.loads(line))
                except (ValueError, KeyError, PermissionError) as error:
                    self._append_receipt('broker-rejections.jsonl',{
                        **trace,'status':403,'origin':'local_route_validation',
                        'type':type(error).__name__,'error':self.redact(str(error))})
                    self.broker.stdin.write(json.dumps({'status':403,'body':json.dumps({'ok':False,'error':{'code':'broker_route_denied'}})})+'\n')
                    self.broker.stdin.flush()
                    continue
                payload=json.loads(data['body']) if data.get('body') else None
                trace.update(method=data['method'],path=data['path'],
                             request_id=payload.get('request_id') if isinstance(payload,dict) else None)
                self._append_receipt('broker-requests.jsonl',{**trace,'request':data.get('body')})
                # validate_request raises for malformed/unknown routes; token is
                # permanently tied to this invocation, never reread from disk.
                if data.get('capability') != self.local_token or self.retired:
                    status, body = 403, {'ok':False,'error':{'code':'invocation_capability_denied'}}
                    origin = 'local_capability_fence'
                elif self.authority_revoked.is_set():
                    status, body = 403, {'ok':False,'error':{'code':'invocation_capability_denied'}}
                    origin = 'local_revocation_fence'
                else:
                    origin = 'protected_host'
                    if data['method']=='GET' and data['path']=='/continuity':
                        content=linux("import pathlib,sys;sys.stdout.write(pathlib.Path(sys.argv[1]).read_text())",self.workspace+'/.continuity/Continuity.md')
                        if len(content.encode())>65536:raise RuntimeError('Canonical note limit')
                        status,body=200,{'ok':True,'content':content,'bytes':len(content.encode()),'sha256':hashlib.sha256(content.encode()).hexdigest()}
                    else:
                        status, body = request(self.endpoint['url'],self.token,data['method'],data['path'],payload)
                    self._observe_revocation(data['method'],data['path'],payload,status,body,'broker',trace['trace_id'])
                record = {**trace,'wall_unix_s':time.time(),'origin':origin,
                          'status':status,'request':data.get('body'),'response':body}
                self._append_receipt('broker-events.jsonl',record)
                self.broker_calls.append({'method':data.get('method'),'path':data.get('path'),'status':status})
                self.broker.stdin.write(json.dumps({'status':status,'body':json.dumps(body)})+'\n');self.broker.stdin.flush()
            except Exception as error:
                self.abort_event.set()
                write_json(self.evidence/'broker-failure.json',{
                    **trace,'failed_wall_unix_s':time.time(),
                    'type':type(error).__name__,'error':self.redact(str(error)),
                    'authority_revocation_established':self.authority_revoked.is_set()})
                break

    def argv(self,mode):
        entry = INTEGRATION / 'campaign-002/harness/codehost_entry_v3.py' if mode == 'codehost' else BOUNDARY / 'linux_entry.py'
        return ['wsl.exe','-d',DISTRO,'--','python3','-B',prior.wsl_path(entry),mode,
            '--workspace',self.workspace,'--socket',self.socket,'--codex',prior.LINUX_CODEX,'--codehost',prior.LINUX_CODEHOST]

    def redact(self,value):
        for token in self.tokens:
            if token:value=value.replace(token,'[REDACTED_EPHEMERAL_CAPABILITY]')
        return value

    def export(self,label):
        return self.block.checkpoint(label)

    def qualify(self):
        for mode in ('canary','codehost-canary'):
            proc=subprocess.run(self.argv(mode),capture_output=True,text=True,encoding='utf-8',timeout=45)
            (self.evidence/(mode+'-stdout.json')).write_text(self.redact(proc.stdout),encoding='utf-8')
            (self.evidence/(mode+'-stderr.txt')).write_text(self.redact(proc.stderr),encoding='utf-8')
            data=json.loads(proc.stdout)
            if proc.returncode or not data.get('qualified',data.get('host_qualified')):
                raise RuntimeError(mode+' qualification failed')

    async def model(self,timeout=600,preflight=False,interrupt_event=None,reviewed_campaign_authority=False):
        if not reviewed_campaign_authority: raise RuntimeError('Campaign 004 awaits human review; model launch disabled')
        if self.image_sensor is None: raise RuntimeError('Bound image sensor required')
        async def callback(url):
            await prior.executor_probe(url,self)
            await asyncio.wait_for(self.bridge_idle.wait(),15)
            args=argparse.Namespace(exec_server_url=url,host_cwd=self.root,codex_home=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex'))),
                remote_cwd='file:///workspace',evidence=self.evidence/'client',timeout=timeout,run_bootstrap=not preflight,
                redact_tokens=self.tokens,abort_event=self.abort_event,client_finishing=self.client_finishing)
            async def model_host(host_url):
                args.image_sensor=self.image_sensor
                args.reviewed_campaign_authority=reviewed_campaign_authority
                args.code_mode_host_url=host_url
                args.native_process_ready=self.native_process_ready
                args.native_cleanup_barrier=self.native_cleanup_barrier
                args.native_exit_barrier=self.native_exit_barrier
                args.native_process_drain=True
                return await asyncio.to_thread(bootstrap.run,args)
            return await with_codehost(self,model_host)
        return await captured_executor.bridge_executor(self,callback)

    def close(self):
        self.retired=True
        self.stop.set()
        errors=[]
        def attempt(label,action):
            try:action()
            except Exception as error:errors.append({'resource':label,'error':str(error)})
        if self.mirror_thread:attempt('public mirror',lambda:self.mirror_thread.join(timeout=12))
        if self.broker:
            attempt('broker input close',self.broker.stdin.close)
            def retire_broker():
                try:self.broker.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    self.broker.terminate();self.broker.wait(timeout=5)
                    errors.append({'resource':'broker','error':'required forced retirement'})
                if self.broker.returncode:errors.append({'resource':'broker','error':'nonzero exit '+str(self.broker.returncode)})
            attempt('broker retirement',retire_broker)
            if self.broker_thread:attempt('broker thread',lambda:self.broker_thread.join(timeout=2))
        if self.owner:attempt('synthetic owner',lambda:self.owner.join(timeout=2))
        if self.gateway:attempt('synthetic gateway',self.gateway.close)
        if self.personal_canary:attempt('owned canary',lambda:self.personal_canary.unlink(missing_ok=True))
        write_json(self.evidence/'gateway-calls.json',self.broker_calls)
        write_json(self.evidence/'cleanup.json',{'clean':not errors,'errors':errors})
        return not errors

def template():
    folder=HERE/'template'
    return {p.relative_to(folder).as_posix():p.read_text(encoding='utf-8') for p in folder.rglob('*') if p.is_file()}

if __name__=='__main__':
    raise SystemExit('Review-only candidate; no model launch from CLI')
