"""Existing authenticated native Codex transport with the apartment namespace."""
from __future__ import annotations
import argparse
import asyncio
import base64
import importlib.util
import json
import os
from pathlib import Path
import queue
import shutil
import stat
import subprocess
import sys
import threading
import time
import uuid
from common import HERE,REPO,save,read,sha,inventory,Events
import image_sensor

INTEGRATION=REPO/'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001'
C05=INTEGRATION/'campaign-005'
DISTRO='Ubuntu-24.04'

def wsl(path):
    path=Path(path).resolve();return '/mnt/'+path.drive[0].lower()+'/'+str(path)[3:].replace('\\','/')

def linux(code,*args,payload=None,timeout=40):
    result=subprocess.run(['wsl.exe','-d',DISTRO,'--','python3','-B','-c',code,*map(str,args)],
        input=None if payload is None else json.dumps(payload),capture_output=True,text=True,encoding='utf-8',timeout=timeout)
    if result.returncode:raise RuntimeError(result.stderr[-4000:])
    return result.stdout

spec=importlib.util.spec_from_file_location('apartment_inherited_runtime',C05/'runtime.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
from native_stream import install as install_native_stream
install_native_stream(old.bootstrap)
from structured_errors import install as install_structured_errors
install_structured_errors(old.bootstrap)
import transport
# Put this prospective image interface ahead of ambient imports without changing inherited bytes.
sys.modules['image_sensor']=image_sensor

class Workspace:
    def __init__(self,evidence,filesystem,session_id,*,start=True):
        self.evidence=Path(evidence);self.evidence.mkdir(parents=True,exist_ok=False)
        self.filesystem=Path(filesystem);self.session_id=session_id;self.run_id='apartment-'+uuid.uuid4().hex
        self.run='/var/tmp/robot-codex-session10/'+self.run_id;self.workspace=self.run+'/workspace'
        self.control=self.run+'/journal-control.sock';self.closed=False;self.ready=False
        self.owner=self.run+'/owner.json';self.progress=self.run+'/startup.json'
        self.process=None;self.log=None;self.preparer=None;self.prepare_log=None;self.cleanup_number=0;self.start_attempted=False
        self.policy=__import__('workspace_lifecycle').DEFAULT_POLICY.copy()
        save(self.evidence/'location.json',dict(run=self.run,workspace=self.workspace,run_id=self.run_id,journal=str(self.evidence/'journal'),
            native_transient_reason='Unix sockets, mount point and process identities require WSL; journals/checkpoints stay on D:'))
        if start:self.start()

    def lifecycle(self,command,*,timeout=40):
        args=['wsl.exe','-d',DISTRO,'--','python3','-B',wsl(HERE/'workspace_lifecycle.py'),command,
              '--owner',self.owner,'--run-id',self.run_id,'--mount',self.workspace]
        if command=='wait':args+=['--status',self.progress,'--control',self.control,'--policy',json.dumps(self.policy)]
        result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:raise RuntimeError('Workspace lifecycle helper: '+result.stderr[-4000:])
        return json.loads(result.stdout)

    def remaining_startup(self):
        remaining=self.policy['total_s']-(time.monotonic()-self.started_monotonic)
        if remaining<=0:raise RuntimeError('Workspace total startup deadline')
        return remaining

    def start(self):
        if self.start_attempted or self.closed:raise ValueError('Workspace start is once-only')
        self.start_attempted=True;begin=time.perf_counter_ns();self.started_monotonic=time.monotonic()
        try:
            self._start()
            self.ready=True
            # Publishing the admission receipt is part of startup, so its
            # failure must retire the already-mounted child as well.
            save(self.evidence/'startup-outcome.json',dict(ready=True,elapsed_s=(time.perf_counter_ns()-begin)/1e9,
                process_pid=self.process.pid,policy=self.policy))
            self.remaining_startup()
        except BaseException as error:
            self.ready=False
            # Attach ownership before any cleanup or evidence I/O can fail.
            try:error.workspace=self
            except Exception:pass
            cleanup_error=None
            try:self.abort()
            except BaseException as cleanup:cleanup_error=repr(cleanup)
            failure=dict(passed=False,error=repr(error),cleanup_error=cleanup_error,runtime_retired=self.closed,
                ready=False,elapsed_s=(time.perf_counter_ns()-begin)/1e9)
            for name in ('startup-failure.json','startup-outcome.json'):
                try:save(self.evidence/name,failure)
                except BaseException as recording_error:
                    self.startup_recording_error=repr(recording_error)
            raise
        return self

    def prepare_restore(self,namespace):
        from workspace_lifecycle import Gate,load_progress
        progress=self.evidence/'prepare-progress.json';destination=self.evidence/'restore-seed'
        gate=Gate(self.run_id,self.started_monotonic,self.policy)
        self.prepare_log=(self.evidence/'prepare-console.log').open('wb')
        try:
            self.preparer=subprocess.Popen([sys.executable,'-B',str(HERE/'workspace_restore.py'),
                '--namespace',str(namespace),'--objects',str(self.filesystem.parent/'filesystem-objects'),
                '--destination',str(destination),'--progress',str(progress),'--run-id',self.run_id],
                stdout=self.prepare_log,stderr=self.prepare_log,creationflags=subprocess.CREATE_NO_WINDOW)
            while True:
                reason=gate.observe(time.monotonic(),load_progress(progress) if progress.exists() else None)
                code=self.preparer.poll()
                if reason:raise RuntimeError('Restore preparation '+reason)
                if code is not None:
                    if code!=0:raise RuntimeError('Restore preparer exited '+str(code))
                    break
                time.sleep(self.policy['poll_s'])
            receipt=read(destination/'prepared.json')
            if receipt['run_id']!=self.run_id:raise ValueError('Restore seed owner differs')
            save(self.evidence/'prepare-readiness.json',dict(passed=True,elapsed_s=time.monotonic()-gate.started,
                history=gate.history,worker_pid=self.preparer.pid,worker_exit=code,seed=receipt))
            return dict(state=read(namespace),prepared=wsl(destination),prepared_manifest_sha256=sha(destination/'prepared.json'))
        finally:
            if self.preparer is not None and self.preparer.poll() is None:
                self.preparer.kill();self.preparer.wait(5)
            self.prepare_log.close()

    def _start(self):
        begin=time.perf_counter_ns()
        initial={}
        namespace=self.filesystem.parent/'filesystem-namespace.json'
        for path in ([] if namespace.exists() else sorted(self.filesystem.rglob('*'))):
            name=path.relative_to(self.filesystem).as_posix()
            if path.is_symlink():raise ValueError('Symlink checkpoint requires explicit support; refusing ambiguous restore')
            if path.is_dir():initial[name]=None
            elif path.is_file():initial[name]=list(path.read_bytes())
        identity=dict(run_id=self.run_id,session_id=self.session_id,source_revision='apartment-workspace-lifecycle-2',phase='runtime')
        payload={'initial.json':initial,'identity.json':identity}
        if namespace.exists():payload['restore.json']=self.prepare_restore(namespace)
        linux("import pathlib,json,sys;r=pathlib.Path(sys.argv[1]);r.mkdir(parents=True,exist_ok=False);(r/'workspace').mkdir();x=json.load(sys.stdin);[(r/k).write_text(json.dumps(v)) for k,v in x.items()]",self.run,payload=payload,timeout=min(40,self.remaining_startup()))
        self.remaining_startup()
        self.log=(self.evidence/'fuse-console.log').open('wb')
        save(self.evidence/'startup-preparation.json',dict(elapsed_s=(time.perf_counter_ns()-begin)/1e9,namespace_restore=namespace.exists()))
        self.process=subprocess.Popen(['wsl.exe','-d',DISTRO,'--','python3','-B',wsl(HERE/'workspace_lifecycle.py'),'bootstrap',
            '--owner',self.owner,'--status',self.progress,'--run-id',self.run_id,'--mount',self.workspace,
            '--service',wsl(HERE/'journal_service.py'),'--',
            '--mount',self.workspace,'--evidence',wsl(self.evidence/'journal'),'--initial',self.run+'/initial.json',
            '--identity',self.run+'/identity.json','--repo',wsl(REPO),'--socket',self.control,'--progress',self.progress,
            *(['--restore',self.run+'/restore.json'] if namespace.exists() else [])],stdout=self.log,stderr=self.log,creationflags=subprocess.CREATE_NO_WINDOW)
        # Preparation and native readiness share the same absolute budget.
        elapsed=time.monotonic()-self.started_monotonic
        if elapsed>=self.policy['total_s']:raise RuntimeError('Workspace total startup deadline before readiness')
        original_policy=self.policy
        remaining=original_policy['total_s']-elapsed
        self.policy=dict(original_policy,total_s=remaining,stall_s=min(original_policy['stall_s'],remaining))
        try:readiness=self.lifecycle('wait',timeout=remaining+5)
        finally:self.policy=original_policy
        readiness['total_startup_s']=time.monotonic()-self.started_monotonic
        save(self.evidence/'readiness.json',readiness)
        if readiness.get('ready') is not True:raise RuntimeError('Workspace startup failed: '+str(readiness.get('reason')))
        self.remaining_startup()
        if self.process.poll() is not None:raise RuntimeError('Workspace child exited at readiness fence')

    def start_clock_bridge(self,controller):
        self.clock_controller=controller;self.clock_stop=threading.Event();self.clock_error=None
        self.clocks=Events(self.evidence/'clock-bridge.jsonl')
        self.clock_number=0
        self.last_linux_clock=None
        self.clock_measure()
        def monitor():
            try:
                while not self.clock_stop.wait(4):self.clock_measure()
            except BaseException as e:self.clock_error=repr(e)
        self.clock_thread=threading.Thread(target=monitor,daemon=True);self.clock_thread.start()

    def clock_measure(self):
        before=self.clock_controller.ask('clock')
        self.clock_number+=1
        marker=self.checkpoint('clock-'+str(self.clock_number).zfill(6))
        after=self.clock_controller.ask('clock')
        if before.get('clock_epoch')!=after.get('clock_epoch') or before['windows_monotonic_ns']>after['windows_monotonic_ns'] or before['sim_time']>after['sim_time']:
            raise ValueError('Invalid monotonic/simulation clock bridge bracket')
        current=marker['linux_monotonic_ns']
        if self.last_linux_clock is not None and current<=self.last_linux_clock:raise ValueError('Linux clock bridge order regressed')
        self.last_linux_clock=current
        self.clocks.emit('clock_bracket',after['sim_time'],dict(before=before,after=after,linux=marker))
        self.clocks.flush()

    def finish_clock_bridge(self):
        if not hasattr(self,'clock_thread'):return
        self.clock_stop.set();self.clock_thread.join(30)
        if self.clock_thread.is_alive():raise RuntimeError('Clock bridge did not stop')
        if self.clock_error:raise RuntimeError('Clock bridge failed: '+self.clock_error)
        self.clock_measure();self.clocks.close();del self.clock_thread

    def checkpoint(self,label):
        before=time.perf_counter_ns()
        result=json.loads(linux("import socket,json,sys;s=socket.socket(socket.AF_UNIX);s.settimeout(5);s.connect(sys.argv[1]);s.sendall((json.dumps({'label':sys.argv[2]})+'\\n').encode());print(s.makefile().readline());s.close()",self.control,label))
        if result.get('error'):raise RuntimeError(result['error'])
        save(self.evidence/('checkpoint-'+label+'.json'),dict(before_windows_perf_ns=before,after_windows_perf_ns=time.perf_counter_ns(),linux=result))
        return result

    def close(self):
        if hasattr(self,'normal_result'):return self.normal_result
        if not self.ready or self.closed:raise ValueError('Workspace did not complete startup normally')
        self.finish_clock_bridge()
        boundary=self.checkpoint('before-retirement')
        if boundary['open_handles']!=0:raise ValueError('Open workspace handles at retirement')
        retirement=self._retire(normal=True)
        if not retirement['retired'] or retirement['service_exit']!=0:raise RuntimeError('Journal service did not retire cleanly')
        import journal_reader as reader
        from content_store import Store
        proof=reader.verify(self.evidence/'journal',self.run_id)
        content=Store(self.evidence/'journal')
        final=self.evidence/'final-filesystem';final.mkdir()
        objects=self.evidence/'final-objects';objects.mkdir()
        for path,inode in sorted(proof['state']['paths'].items(),key=lambda row:row[0].count('/')):
            if path=='/':continue
            target=final/path.lstrip('/');node=proof['state']['nodes'][str(inode)]
            if stat.S_ISDIR(node['mode']):target.mkdir(parents=True,exist_ok=True)
            elif stat.S_ISREG(node['mode']):
                raw=content.get(node['sha256'])
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
                if not (objects/node['sha256']).exists():(objects/node['sha256']).write_bytes(raw)
            elif stat.S_ISLNK(node['mode']):pass # Kept exactly in namespace metadata, not followed by Windows export.
            else:raise ValueError('Unsupported persistent namespace entry; preserving journal for inspection')
        save(self.evidence/'final-namespace.json',proof['state'])
        receipt={k:v for k,v in proof.items() if k not in ('state','states','read_events')}
        save(self.evidence/'retirement.json',dict(**receipt,native_exit=read(self.evidence/'journal/native-exit.json'),filesystem=inventory(final)))
        self.closed=True
        self.normal_result=(final,receipt)
        return self.normal_result

    def _retire(self,normal=False):
        self.cleanup_number+=1
        args=['wsl.exe','-d',DISTRO,'--','python3','-B',wsl(HERE/'workspace_lifecycle.py'),'retire',
              '--owner',self.owner,'--run-id',self.run_id,'--mount',self.workspace]
        if normal:args+=['--normal','--control',self.control]
        receipt=dict(retired=False,normal_requested=normal)
        try:
            completed=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
            if completed.returncode:raise RuntimeError(completed.stderr[-4000:])
            receipt=json.loads(completed.stdout)
            if self.process is not None:
                try:receipt['service_exit']=self.process.wait(5)
                except subprocess.TimeoutExpired:receipt.update(retired=False,launcher_still_alive=True)
            else:receipt['service_exit']=None
        except BaseException as error:receipt.update(retired=False,error=repr(error))
        finally:
            if self.log is not None:self.log.close()
            receipt['log_closed']=self.log is None or self.log.closed
            save(self.evidence/('cleanup-'+str(self.cleanup_number).zfill(3)+'.json'),receipt)
        return receipt

    def abort(self):
        """Retire only this identified failed service; never manufacture closure."""
        if self.closed:return getattr(self,'abnormal_result',dict(retired=True,already_closed=True))
        if self.preparer is not None and self.preparer.poll() is None:
            self.preparer.kill();self.preparer.wait(5)
        if self.prepare_log is not None:self.prepare_log.close()
        clock_error=None
        if hasattr(self,'clock_thread'):
            self.clock_stop.set();self.clock_thread.join(12)
            if self.clock_thread.is_alive():clock_error='Clock bridge still alive'
            else:
                try:self.clocks.close()
                except Exception as error:clock_error=repr(error)
        receipt=self._retire(normal=False)
        self.closed=receipt['retired'] and clock_error is None
        self.abnormal_result=dict(passed=False,retired=self.closed,clock_error=clock_error,cleanup=receipt)
        save(self.evidence/('abnormal-retirement-'+str(self.cleanup_number).zfill(3)+'.json'),self.abnormal_result)
        if not self.closed:raise RuntimeError('Workspace cleanup incomplete: '+json.dumps(self.abnormal_result))
        return self.abnormal_result

class Guest(old.Runtime):
    def __init__(self,evidence,block,endpoint,controller):
        self.evidence=Path(evidence);self.evidence.mkdir(parents=True,exist_ok=False);self.root=self.evidence/'control';self.root.mkdir()
        self.block=block;self.session_id=block.session_id;self.run=block.run;self.workspace=block.workspace;self.socket=self.run+'/gateway.sock'
        self.endpoint=endpoint;self.token=endpoint['capability'];self.tokens=[self.token];self.local_token='local-workspace-capability'
        self.bridge_idle=asyncio.Event();self.bridge_idle.set();self.abort_event=threading.Event();self.authority_revoked=threading.Event();self.revocation_lock=threading.Lock();self.client_finishing=threading.Event();self.stop=threading.Event()
        self.gateway=self.owner=self.mirror_thread=self.personal_canary=None
        self.retired=False;self.broker_calls=[];self.image_sensor=image_sensor.ImageSensor(controller);self.controller=controller
        self.broker=subprocess.Popen(['wsl.exe','-d',DISTRO,'--','python3','-B',wsl(HERE/'broker.py'),self.socket,'--repo',wsl(REPO)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
        ready=json.loads(self.broker.stdout.readline())
        if not ready.get('ready'):raise ValueError('Broker failed to start')
        self.broker_thread=threading.Thread(target=self._broker_loop,daemon=True);self.broker_thread.start()
        self.check_binaries()

    def check_binaries(self):
        proof=json.loads(linux("import sys,hashlib,json;from pathlib import Path;print(json.dumps([hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in sys.argv[1:]]))",old.prior.LINUX_CODEX,old.prior.LINUX_CODEHOST))
        if proof!=[old.prior.LINUX_SHA256,old.prior.CODEHOST_SHA256]:raise ValueError('Inherited executor binary identity changed')
        save(self.evidence/'binary-identity.json',dict(linux_codex=proof[0],linux_codehost=proof[1],windows_codex=sha(old.bootstrap.LAUNCH.CODEX)))

    def argv(self,mode):
        return ['wsl.exe','-d',DISTRO,'--','python3','-B',wsl(HERE/'guest_entry.py'),mode,'--repo',wsl(REPO),
                '--workspace',self.workspace,'--socket',self.socket,'--codex',old.prior.LINUX_CODEX,'--codehost',old.prior.LINUX_CODEHOST]

    def qualify(self):
        for mode in ('canary','codehost-canary'):
            result=subprocess.run(self.argv(mode),capture_output=True,text=True,encoding='utf-8',timeout=45)
            save(self.evidence/(mode+'.json'),dict(exit_status=result.returncode,stdout=result.stdout,stderr=result.stderr))
            if result.returncode or not json.loads(result.stdout).get('qualified'):raise RuntimeError('Namespace '+mode+' did not qualify')

    async def model(self,timeout=2400,preflight=False):
        async def callback(url):
            args=argparse.Namespace(exec_server_url=url,host_cwd=self.root,codex_home=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex'))),
                remote_cwd='file:///workspace',evidence=self.evidence/'client',timeout=timeout,run_bootstrap=not preflight,
                redact_tokens=self.tokens,abort_event=self.abort_event,client_finishing=self.client_finishing)
            async def model_host(host_url):
                args.image_sensor=self.image_sensor;args.reviewed_campaign_authority=True;args.code_mode_host_url=host_url
                args.native_process_ready=self.native_process_ready;args.native_cleanup_barrier=self.native_cleanup_barrier;args.native_exit_barrier=self.native_exit_barrier;args.native_process_drain=True
                return await asyncio.to_thread(old.bootstrap.run,args)
            return await transport.run(self,model_host)
        return await old.captured_executor.bridge_executor(self,callback)

    def close(self):
        self.image_sensor.retired=True
        return super().close()
