"""Bounded native workspace ownership, progress and retirement (no guest API).

Progress advances only after completed work or a new ordered phase. Repeated
heartbeats do not reset the stall deadline. The absolute deadline never moves.
Linux process identity is published BEFORE importing or restoring the service.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

PHASES = ('bootstrap', 'imports', 'inputs', 'restoring', 'initial_committed',
          'control_ready', 'mount_enter', 'mounted')
DEFAULT_POLICY = dict(stall_s=20.0, total_s=120.0, poll_s=0.05)

def load_progress(path):
    """Read a bounded complete Windows append-log tail or Linux snapshot."""
    if os.name!='nt':return json.loads(Path(path).read_text())
    import ctypes
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    create=api.CreateFileW;create.restype=ctypes.c_void_p
    create.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p]
    read=api.ReadFile;read.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(ctypes.c_uint32),ctypes.c_void_p]
    size_of=api.GetFileSizeEx;size_of.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_longlong)]
    seek=api.SetFilePointerEx;seek.argtypes=[ctypes.c_void_p,ctypes.c_longlong,ctypes.c_void_p,ctypes.c_uint32]
    close=api.CloseHandle;close.argtypes=[ctypes.c_void_p]
    handle=create(str(path),0x80000000,7,None,3,0,None) # share read/write/delete
    if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    try:
        size=ctypes.c_longlong()
        if not size_of(handle,ctypes.byref(size)):raise ctypes.WinError(ctypes.get_last_error())
        offset=max(0,size.value-65536)
        if not seek(handle,offset,None,0):raise ctypes.WinError(ctypes.get_last_error())
        buffer=ctypes.create_string_buffer(65536);count=ctypes.c_uint32()
        if not read(handle,buffer,65536,ctypes.byref(count),None):raise ctypes.WinError(ctypes.get_last_error())
        raw=buffer.raw[:count.value];lines=raw.split(b'\n')[:-1]
        if offset:lines=lines[1:]
        return json.loads(lines[-1]) if lines else None
    finally:close(handle)

def atomic(path, value):
    path=Path(path);temporary=path.with_name(path.name+'.next')
    with temporary.open('w',encoding='utf-8') as f:
        json.dump(value,f,sort_keys=True,allow_nan=False);f.flush();os.fsync(f.fileno())
    os.replace(temporary,path)

class Progress:
    def __init__(self,path,run_id):
        self.path=Path(path);self.run_id=run_id;self.sequence=0;self.phase=-1
        self.files=0;self.bytes=0;self.started=time.monotonic_ns()
        if self.path.exists():
            old=load_progress(self.path)
            if old is None:raise ValueError('Existing startup log has no complete record')
            if old['run_id']!=run_id:raise ValueError('Progress owner differs')
            self.sequence=old['sequence'];self.phase=PHASES.index(old['phase'])
            self.files=old['files'];self.bytes=old['bytes'];self.started=old['started_monotonic_ns']
    def advance(self,phase,files=None,bytes_done=None,**details):
        files=self.files if files is None else files
        bytes_done=self.bytes if bytes_done is None else bytes_done
        index=PHASES.index(phase)
        if index<self.phase or files<self.files or bytes_done<self.bytes:
            raise ValueError('Startup progress regressed')
        if index==self.phase and files==self.files and bytes_done==self.bytes:return
        self.phase=index;self.files=files;self.bytes=bytes_done;self.sequence+=1
        value=dict(run_id=self.run_id,sequence=self.sequence,phase=phase,
            files=files,bytes=bytes_done,started_monotonic_ns=self.started,
            monotonic_ns=time.monotonic_ns(),wall_ns=time.time_ns(),**details)
        if os.name=='nt':
            # Never replace an open Windows progress file. Append-only complete
            # records also preserve phases too fast for the parent poll to see.
            raw=(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode()
            with self.path.open('ab',buffering=0) as stream:
                if stream.write(raw)!=len(raw):raise OSError('Short startup progress write')
                os.fsync(stream.fileno())
        else:atomic(self.path,value)

class Gate:
    """Pure monotonic deadline state, independently exercised by fault tests."""
    def __init__(self,run_id,started,policy=None):
        self.policy=dict(DEFAULT_POLICY if policy is None else policy)
        if not (0<self.policy['stall_s']<=self.policy['total_s']<=120 and 0<self.policy['poll_s']<=1):
            raise ValueError('Invalid bounded startup policy')
        self.run_id=run_id;self.started=started;self.changed=started;self.last=None;self.history=[]
    def observe(self,now,value):
        if value is not None:
            if value['run_id']!=self.run_id:raise ValueError('Startup identity mismatch')
            key=(PHASES.index(value['phase']),value['files'],value['bytes'])
            if any(type(x) is not int or x<0 for x in key):raise ValueError('Invalid progress counter')
            if self.last and any(a<b for a,b in zip(key,self.last)):raise ValueError('Startup progress regressed')
            if key!=self.last:
                self.last=key;self.changed=now;self.history.append(dict(observed_s=now-self.started,**value))
        if now-self.started>=self.policy['total_s']:return 'absolute_deadline'
        if now-self.changed>=self.policy['stall_s']:return 'no_progress_deadline'
        return None

def mounted(path):
    # Read mountinfo, never stat a potentially wedged FUSE path.
    escaped=str(path).replace('\\','\\134').replace(' ','\\040').replace('\t','\\011').replace('\n','\\012')
    return any(row.split()[4]==escaped for row in Path('/proc/self/mountinfo').read_text().splitlines())

def process(identity):
    if identity.get('boot_id') and identity['boot_id']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip():
        return dict(alive=False,identity_matches=False,state='previous_boot')
    p=Path('/proc')/str(identity['pid'])
    try:
        fields=(p/'stat').read_text().rsplit(')',1)[1].split()
        command=(p/'cmdline').read_bytes()
    except (FileNotFoundError,ProcessLookupError):return dict(alive=False,identity_matches=True,state='absent')
    if fields[19]!=identity['start_ticks']:
        return dict(alive=False,identity_matches=False,state='pid_reused')
    if fields[0]=='Z':return dict(alive=False,identity_matches=True,state='zombie')
    # During exit Linux may release mm/cmdline after the stat read, before it
    # publishes Z or removes /proc. Keep polling that same owned PID; an empty
    # command is not yet proof of exit and is not an identity mismatch.
    if not command:return dict(alive=True,identity_matches=True,state='exiting_command_empty')
    if identity['mount'].encode() not in command:
        raise ValueError('Owned process command differs')
    return dict(alive=True,identity_matches=True,state=fields[0])

def validate_owner(owner_path,run_id,mount):
    value=json.loads(Path(owner_path).read_text())
    if value['run_id']!=run_id or value['mount']!=mount:raise ValueError('Wrong workspace ownership')
    return value

def request(control,value,timeout=1):
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(timeout);s.connect(str(control));s.sendall((json.dumps(value)+'\n').encode())
        with s.makefile('rb') as stream:
            raw=stream.readline(8193)
    if len(raw)>8192 or not raw.endswith(b'\n'):raise ValueError('Invalid control response')
    return json.loads(raw)

def wait_ready(owner_path,status_path,run_id,mount,control,policy=None):
    gate=Gate(run_id,time.monotonic(),policy);last_error=None
    while True:
        now=time.monotonic();status=None;identity=None
        if Path(owner_path).exists():identity=validate_owner(owner_path,run_id,mount)
        if Path(status_path).exists():status=json.loads(Path(status_path).read_text())
        reason=gate.observe(now,status)
        if identity and not process(identity)['alive']:reason='child_exited'
        if reason:
            return dict(ready=False,reason=reason,elapsed_s=time.monotonic()-gate.started,
                        history=gate.history,policy=gate.policy,last_probe_error=last_error)
        if identity and status and status['phase']=='mounted' and mounted(mount):
            try:
                reply=request(control,dict(command='health',run_id=run_id),min(1,gate.policy['stall_s']))
                if reply.get('run_id')!=run_id:raise ValueError('Health identity mismatch')
                if reply.get('ready') is True:
                    # A responsive FUSE operation completes the readiness fence.
                    probe=subprocess.run([sys.executable,'-B','-c','import os,sys;os.stat(sys.argv[1])',mount],capture_output=True,timeout=min(2,gate.policy['stall_s']))
                    if probe.returncode:raise RuntimeError(probe.stderr.decode(errors='replace'))
                    if time.monotonic()-gate.started>=gate.policy['total_s']:continue
                    if not process(identity)['alive']:continue
                    return dict(ready=True,reason='mounted_and_responsive',elapsed_s=time.monotonic()-gate.started,
                        history=gate.history,policy=gate.policy,health=reply,identity=identity)
            except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as e:last_error=repr(e)
        time.sleep(gate.policy['poll_s'])

def retire(owner_path,run_id,mount,normal=False,control=None):
    started=time.monotonic();actions=[];errors=[];identity=None
    try:
        if Path(owner_path).exists():identity=validate_owner(owner_path,run_id,mount)
        # No broad process search or unverified kill. A missing owner cannot
        # attest absence of a partially launched child.
        if identity is None:
            candidates=[]
            for p in Path('/proc').iterdir():
                if not p.name.isdigit():continue
                try:
                    argv=(p/'cmdline').read_bytes().split(b'\0')
                    if mount.encode() in argv and str(owner_path).encode() in argv and b'bootstrap' in argv:
                        fields=(p/'stat').read_text().rsplit(')',1)[1].split()
                        candidates.append(dict(run_id=run_id,mount=mount,pid=int(p.name),start_ticks=fields[19],boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip()))
                except (FileNotFoundError,ProcessLookupError,PermissionError):continue
            if not candidates:
                return dict(retired=not mounted(mount),reason='no_bootstrap_process_or_mount',mounted=mounted(mount),actions=actions,elapsed_s=time.monotonic()-started)
            if len(candidates)!=1:raise ValueError('Ambiguous partial bootstrap ownership')
            identity=candidates[0];actions.append(dict(action='recovered_prepublication_owner',identity=identity))
        status=process(identity)
        if mounted(mount):
            if not status['identity_matches']:raise ValueError('Refusing mount operation after PID reuse')
            r=subprocess.run(['fusermount3','-u',mount],capture_output=True,text=True,timeout=5)
            actions.append(dict(action='normal_unmount',exit_status=r.returncode,stderr=r.stderr))
        if normal and not mounted(mount) and process(identity)['alive']:
            if not control:raise ValueError('Normal retirement requires protected control socket')
            try:
                reply=request(control,dict(command='retire',run_id=run_id),timeout=2)
                actions.append(dict(action='cooperative_retirement',response=reply))
                if reply.get('error') or reply.get('run_id')!=run_id:raise ValueError('Cooperative retirement refused: '+str(reply))
            except OSError as error:
                # Ordinary unmount may already have closed the server. Actual
                # process exit and independent journal/native-exit verification
                # still decide whether the Windows controller accepts closeout.
                errors.append(dict(action='cooperative_retirement',error=repr(error)))
        limit=time.monotonic()+(12 if normal else 2)
        while process(identity)['alive'] and time.monotonic()<limit:time.sleep(.05)
        if not normal:
            for sig,budget in ((signal.SIGTERM,3),(signal.SIGKILL,3)):
                current=process(identity)
                if not current['alive']:break
                os.kill(identity['pid'],sig);actions.append(dict(action='signal',signal=int(sig)))
                limit=time.monotonic()+budget
                while process(identity)['alive'] and time.monotonic()<limit:time.sleep(.05)
        status=process(identity);is_mounted=mounted(mount)
        return dict(retired=not status['alive'] and not is_mounted,process=status,mounted=is_mounted,
                    normal_requested=normal,actions=actions,errors=errors,elapsed_s=time.monotonic()-started,identity=identity)
    except Exception as error:
        return dict(retired=False,error=repr(error),actions=actions,elapsed_s=time.monotonic()-started)

def bootstrap(a):
    identity=dict(run_id=a.run_id,mount=a.mount,pid=os.getpid(),
                  start_ticks=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19],
                  boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    atomic(a.owner,identity)
    Progress(a.status,a.run_id).advance('bootstrap')
    os.execv(sys.executable,[sys.executable,'-B',a.service,*a.arguments])

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    for name in ('bootstrap','wait','retire'):
        q=sub.add_parser(name)
        for key in ('owner','run-id','mount'):q.add_argument('--'+key,required=True)
        if name!='retire':q.add_argument('--status',required=True)
        if name=='bootstrap':q.add_argument('--service',required=True);q.add_argument('arguments',nargs=argparse.REMAINDER)
        if name=='wait':q.add_argument('--control',required=True);q.add_argument('--policy',required=True)
        if name=='retire':q.add_argument('--normal',action='store_true');q.add_argument('--control')
    a=p.parse_args()
    if a.command=='bootstrap':
        if a.arguments and a.arguments[0]=='--':a.arguments.pop(0)
        bootstrap(a)
    elif a.command=='wait':print(json.dumps(wait_ready(a.owner,a.status,a.run_id,a.mount,a.control,json.loads(a.policy))))
    else:print(json.dumps(retire(a.owner,a.run_id,a.mount,a.normal,a.control)))

if __name__=='__main__':main()
