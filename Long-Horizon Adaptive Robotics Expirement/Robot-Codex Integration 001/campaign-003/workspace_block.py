"""Trusted Windows lifetime for one persistent journaled Linux workspace."""
import hashlib
import json
import queue
from pathlib import Path
import subprocess
import sys
import time
import threading
import uuid
from common import HERE, canonical, save

DISTRO='Ubuntu-24.04'
def wsl(path):
    path=Path(path).resolve();return '/mnt/'+path.drive[0].lower()+'/'+str(path)[3:].replace('\\','/')
def linux(code,*args,payload=None):
    p=subprocess.run(['wsl.exe','-d',DISTRO,'--','python3','-B','-c',code,*map(str,args)],
        input=None if payload is None else json.dumps(payload),capture_output=True,text=True,encoding='utf-8',timeout=25)
    if p.returncode:raise RuntimeError(p.stderr[-3000:])
    return p.stdout

class WorkspaceBlock:
    def __init__(self,evidence,files,run_id,source_revision,source_snapshot_sha256):
        self.evidence=Path(evidence);self.evidence.mkdir(parents=True,exist_ok=False)
        self.run='/var/tmp/robot-codex-session10/c03-'+uuid.uuid4().hex
        self.workspace=self.run+'/workspace';self.run_id=run_id;self.source_revision=source_revision;self.source_snapshot_sha256=source_snapshot_sha256
        self.session_id='setup';self.closed=False
        self.clock_failed=False
        initial={'notes':None,'programs':None,'.continuity':None,'.continuity/Continuity.md':files.get('Continuity.md',''),
                 'Continuity.md':{'symlink':'.continuity/Continuity.md'}}
        for name,content in files.items():
            if name=='Continuity.md':continue
            parts=name.split('/')
            for n in range(1,len(parts)):initial.setdefault('/'.join(parts[:n]),None)
            initial[name]=content
        identity=self.identity('setup')
        linux("import pathlib,sys,json; r=pathlib.Path(sys.argv[1]); r.mkdir(mode=0o700,parents=True,exist_ok=False);(r/'workspace').mkdir();x=json.load(sys.stdin);[(r/n).write_text(json.dumps(v)) for n,v in x.items()]",self.run,
              payload={'initial.json':initial,'identity.json':identity})
        self.log=(self.evidence/'fuse-server.log').open('wb')
        self.process=subprocess.Popen(['wsl.exe','-d',DISTRO,'--','python3','-B',wsl(HERE/'journal_fs.py'),
            '--mount',self.workspace,'--evidence',self.run+'/journal','--initial',self.run+'/initial.json',
            '--identity',self.run+'/identity.json'],stdout=self.log,stderr=self.log,creationflags=subprocess.CREATE_NO_WINDOW)
        linux("import os,time,sys; end=time.monotonic()+15\nwhile not os.path.ismount(sys.argv[1]):\n if time.monotonic()>end:raise RuntimeError('Mount deadline')\n time.sleep(.02)",self.workspace)
        save(self.evidence/'location.json',{'run':self.run,'workspace':self.workspace,'run_id':run_id,'source_revision':source_revision})
        # Warm, fixed-socket pipe relay: brackets contain the actual request,
        # not a fresh WSL process startup. No socket enters the guest mount.
        code="""import sys,socket,json
print(json.dumps({'ready':True}),flush=True)
for line in sys.stdin:
 try:
  s=socket.socket(socket.AF_UNIX);s.settimeout(3);s.connect(sys.argv[1]);s.sendall(line.encode());raw=s.makefile().readline(8193);s.close()
  if not raw.endswith('\\n') or len(raw)>8192:raise ValueError('Bounded clock reply required')
  print(raw.strip(),flush=True)
 except Exception as e:print(json.dumps({'error':str(e)}),flush=True)
"""
        self.clock_process=subprocess.Popen(['wsl.exe','-d',DISTRO,'--','python3','-B','-u','-c',code,self.run+'/journal/control.sock'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
        self.clock_replies=queue.Queue()
        def read_replies():
            for line in self.clock_process.stdout:self.clock_replies.put(line)
            self.clock_replies.put(None)
        threading.Thread(target=read_replies,daemon=True).start()
        ready=self.clock_replies.get(timeout=15)
        if not ready or not json.loads(ready).get('ready'):raise RuntimeError('Clock relay initialization failed')
        self.checkpoint('initialized')

    def identity(self,session):return {'run_id':self.run_id,'session_id':session,'source_revision':self.source_revision,'source_snapshot_sha256':self.source_snapshot_sha256,'phase':'workspace'}

    def begin_session(self,session_id,files):
        self.session_id=session_id
        # Sequential invocations only: caller must hold the previous retirement receipt.
        linux("import pathlib,sys,json,os; r=pathlib.Path(sys.argv[1]);x=json.load(sys.stdin);p=r/'identity.next';p.write_text(json.dumps(x['identity']));os.replace(p,r/'identity.json')\nfor name,content in x['files'].items():\n if name=='Continuity.md' or name.startswith(('notes/','programs/','.continuity/')):continue\n p=r/'workspace'/name;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.trusted-next');t.write_text(content);os.replace(t,p)",self.run,payload={'identity':self.identity(session_id),'files':files})
        return self.checkpoint('session-start')

    def checkpoint(self,label,sim_time_s=None):
        if self.clock_failed:raise RuntimeError('Clock relay previously failed; no new requests admitted')
        before={'windows_perf_ns':time.perf_counter_ns(),'windows_wall_unix_ns':time.time_ns(),'sim_time_s':sim_time_s}
        try:
            self.clock_process.stdin.write(json.dumps({'label':label,'clock_bracket':before})+'\n');self.clock_process.stdin.flush()
            reply=self.clock_replies.get(timeout=5)
        except Exception:
            self.clock_failed=True;raise
        if reply is None:raise RuntimeError('Clock relay ended without receipt')
        result=json.loads(reply)
        if 'error' in result:raise RuntimeError(result['error'])
        value={'label':label,'run_id':self.run_id,'session_id':self.session_id,'before':before,'linux':result,
               'after':{'windows_perf_ns':time.perf_counter_ns(),'windows_wall_unix_ns':time.time_ns()}}
        with (self.evidence/'clock-brackets.jsonl').open('ab') as f:
            import os
            f.write(canonical(value)+b'\n');f.flush();os.fsync(f.fileno())
        if value['after']['windows_perf_ns']-before['windows_perf_ns']>150_000_000:
            self.clock_failed=True
            raise RuntimeError('Clock bracket exceeds prospective 150 ms alignment bound')
        return value

    def terminal(self,accepted,resumed,retirement):
        value=json.loads(linux("import sys,json;sys.path.insert(0,sys.argv[1]);from terminal import TerminalAppend;x=json.load(sys.stdin);print(json.dumps(TerminalAppend(sys.argv[2]+'/terminal').finalize(sys.argv[2]+'/workspace/.continuity/Continuity.md',x['accepted'],x['resumed'],x['retirement'])))",wsl(HERE),self.run,payload=dict(accepted=accepted,resumed=resumed,retirement=retirement)))
        self.checkpoint('framework-terminal-appended',resumed['sim_time_s']);return value

    def close(self):
        if getattr(self,'close_attempted',False):
            if self.closed:return self.close_receipt
            raise RuntimeError('Prior workspace retirement failed: '+self.close_error)
        self.close_attempted=True;self.close_error='in progress'
        started=time.perf_counter()
        try:
            self.close_receipt=self._close_once()
            return self.close_receipt
        except Exception as error:
            self.close_error=type(error).__name__+': '+str(error)
            raise
        finally:
            save(self.evidence/'close-lifetime.json',dict(completed=self.closed,
                error=None if self.closed else self.close_error,
                elapsed_s=time.perf_counter()-started,
                retirement_request=getattr(self,'retirement_request',None)))

    def _close_once(self):
        checkpoint_error=None
        try:self.checkpoint('block-close')
        except Exception as error:checkpoint_error=str(error)
        if hasattr(self,'clock_process'):
            self.clock_process.stdin.close()
            try:clock_code=self.clock_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.clock_process.terminate();clock_code=self.clock_process.wait(timeout=5);checkpoint_error='Clock relay forced retirement'
            if clock_code:checkpoint_error='Clock relay nonzero retirement'
        linux("import subprocess,sys;p=subprocess.run(['fusermount3','-u',sys.argv[1]],capture_output=True,text=True);assert p.returncode==0,p.stderr",self.workspace)
        # A service namespace can retain a cloned mount after outer unmount.
        # Request libfuse's normal signal shutdown through the protected socket;
        # still require bounded exit0, a final journal record and full replay.
        self.retirement_request=json.loads(linux("""import json,socket,sys
s=socket.socket(socket.AF_UNIX);s.settimeout(3)
try:s.connect(sys.argv[1])
except (FileNotFoundError,ConnectionRefusedError):
 print(json.dumps({'already_not_listening':True}))
else:
 s.sendall((json.dumps({'command':'retire','run_id':sys.argv[2]})+'\\n').encode())
 raw=s.makefile('rb').readline(8193)
 if not raw.endswith(b'\\n') or len(raw)>8192:raise ValueError('Retirement reply bound')
 value=json.loads(raw)
 if value.get('error'):raise RuntimeError(value['error'])
 if value.get('run_id')!=sys.argv[2] or not value.get('retirement_requested'):raise ValueError('Retirement identity')
 print(json.dumps(value))
finally:s.close()
""",self.run+'/journal/control.sock',self.run_id))
        code=self.process.wait(timeout=10);self.log.close()
        if code:raise RuntimeError('Journal server exit '+str(code))
        receipt={'passed':False,'checkpoint_error':checkpoint_error}
        try:
            receipt=json.loads(linux("import sys,json;sys.path.insert(0,sys.argv[1]);from verify_journal import verify;r=verify(sys.argv[2]+'/journal',sys.argv[3]);print(json.dumps({k:v for k,v in r.items() if k not in ('state','states','read_events')}))",wsl(HERE),self.run,self.run_id))
        except Exception as error:receipt['replay_error']=str(error)
        if checkpoint_error:receipt.update(passed=False,checkpoint_error=checkpoint_error)
        save(self.evidence/'replay-receipt.json',receipt)
        # Exact journal including every old content object; no credential-bearing
        # Windows capability is ever placed in this workspace.
        linux("import tarfile,sys;from pathlib import Path;r=Path(sys.argv[1]);out=Path(sys.argv[2]);t=tarfile.open(out,'w:gz');t.add(r/'journal',arcname='journal',filter=lambda x:None if x.name.endswith('control.sock') else x);t.add(r/'identity.json',arcname='identity.json');t.add(r/'initial.json',arcname='initial.json');t.close()",self.run,wsl(self.evidence/'evidence.tar.gz'))
        self.closed=True
        return receipt
