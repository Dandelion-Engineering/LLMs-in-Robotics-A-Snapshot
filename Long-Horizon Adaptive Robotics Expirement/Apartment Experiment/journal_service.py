"""Inherited transactional FUSE journal on D:, with native Unix control socket."""
import argparse
import copy
import ctypes
import json
import os
from pathlib import Path
import signal
import socket
import sys
import threading
import errno
import time
from content_store import Store
from workspace_lifecycle import Progress, atomic, mounted

def main():
    p=argparse.ArgumentParser()
    for n in ('mount','evidence','initial','identity','repo','socket'):p.add_argument('--'+n,required=True)
    p.add_argument('--restore')
    p.add_argument('--progress',required=True)
    a=p.parse_args();source=Path(a.repo)/'Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-005'
    sys.path.insert(0,str(source))
    from journal_fs import JournalFS,FUSE,encoded,digest
    from mfusepy import _libfuse
    identity=json.loads(Path(a.identity).read_text());initial=json.loads(Path(a.initial).read_text())
    progress=Progress(a.progress,identity['run_id']);progress.advance('imports')
    progress.advance('inputs')
    class PersistentJournal(JournalFS):
        closing=False
        mount_initialized=False
        native_fuse=None
        exit_requested=False
        def init(self,path):
            # Capture the context only in libfuse's own callback. Its lifetime
            # ends in destroy, under the same mutex as cooperative retirement.
            self.native_fuse=ctypes.c_void_p(_libfuse.fuse_get_context().contents.fuse)
            self.mount_initialized=True;progress.advance('mounted')
        def destroy(self,path):
            # The control thread and FUSE teardown share this lock. Once closing
            # begins, no control command may append to the journal.
            with self._mutex:
                if self.closing:return
                self.closing=True
                self.native_fuse=None
                return super().destroy(path)
        def content_store(self):
            if not hasattr(self,'store'):
                def charge(size):
                    if self.used+size>self.journal_cap-1024*1024:raise OSError(errno.ENOSPC,'Journal storage bound')
                    self.used+=size
                self.store=Store(self.root,charge);self.store.create()
            return self.store
        def adopt_seed(self,restored):
            seed=Path(restored['prepared']);manifest=seed/'prepared.json'
            if digest(manifest.read_bytes())!=restored['prepared_manifest_sha256']:raise ValueError('Prepared manifest differs')
            receipt=json.loads(manifest.read_text())
            if receipt['run_id']!=identity['run_id'] or receipt['namespace_sha256']!=digest(encoded(self.state)):
                raise ValueError('Prepared namespace identity differs')
            # The destination is this newly allocated, still-unmounted journal.
            # It has no committed initial state until every content hash passes.
            (self.root/'objects').rmdir()
            for name in ('objects','chunks','format.json'):os.rename(seed/name,self.root/name)
            # Flush the adopted child directories too: file fsync in the
            # Windows preparer does not replace publication of their entries.
            # This preserves the original Store's directory-flush barrier,
            # batched before any initial journal commit or mount admission.
            for directory in (self.root/'objects',self.root/'chunks',self.root,seed):
                fd=os.open(directory,os.O_DIRECTORY)
                try:os.fsync(fd)
                finally:os.close(fd)
            stored=sum(p.stat().st_size for folder in ('objects','chunks') for p in (self.root/folder).iterdir())+(self.root/'format.json').stat().st_size
            if stored!=receipt['stored_bytes'] or stored>self.journal_cap-1024**2:raise ValueError('Prepared journal storage accounting differs')
            self.used+=stored
            def charge(size):
                if self.used+size>self.journal_cap-1024**2:raise OSError(errno.ENOSPC,'Journal storage bound')
                self.used+=size
            self.store=Store(self.root,charge)
        def blob(self,raw):return self.content_store().put(raw)
        def content(self,inode):
            node=self.state['nodes'][str(inode)]
            return self.content_store().get(node['sha256']) if node.get('sha256') else b''
        def write(self,path,data,offset,fh):
            inode=self.inode(path,fh);data=bytes(data)
            def apply(state):
                if offset<0 or offset+len(data)>16*1024**2:raise OSError(errno.EFBIG,'File size bound')
                old=self.content(inode);new=old[:offset].ljust(offset,b'\0')+data+old[offset+len(data):]
                at=min(offset,len(old));insert=b'\0'*max(0,offset-len(old))+data
                remove=min(len(data),max(0,len(old)-offset))
                n=state['nodes'][str(inode)];key=self.content_store().put(new,(n['sha256'],at,remove,insert))
                ns=time.time_ns();n.update(sha256=key,size=len(new),mtime_ns=ns,ctime_ns=ns)
                return len(data)
            return self.mutate('write',dict(path=path,inode=inode,offset=offset,bytes=len(data),input_sha256=digest(data)),apply)
        def truncate(self,path,length,fh=None):
            inode=self.inode(path,fh)
            def apply(state):
                if not 0<=length<=16*1024**2:raise OSError(errno.EFBIG,'File size bound')
                old=self.content(inode);new=old[:length].ljust(length,b'\0');n=state['nodes'][str(inode)]
                key=self.content_store().put(new,(n['sha256'],min(length,len(old)),max(0,len(old)-length),b'\0'*max(0,length-len(old))))
                ns=time.time_ns();n.update(sha256=key,size=length,mtime_ns=ns,ctime_ns=ns)
            self.mutate('truncate',dict(path=path,inode=inode,length=length),apply);return 0
        def record(self,kind,payload,actor=None):
            if kind=='initial' and a.restore:
                restored=json.loads(Path(a.restore).read_text())
                self.state=copy.deepcopy(restored['state']);self.next_inode=max(map(int,self.state['nodes']))+1
                progress.advance('restoring',total_files=sum(bool(n.get('sha256')) for n in self.state['nodes'].values()))
                if 'prepared' in restored:self.adopt_seed(restored)
                restored_files=restored_bytes=0
                for node in self.state['nodes'].values():
                    if node.get('sha256'):
                        raw=self.content_store().get(node['sha256']) if 'prepared' in restored else (Path(restored['objects'])/node['sha256']).read_bytes()
                        if len(raw)!=node['size'] or digest(raw)!=node['sha256']:raise ValueError('Restored namespace blob differs')
                        if 'prepared' not in restored:self.blob(raw)
                        restored_files+=1;restored_bytes+=len(raw)
                        progress.advance('restoring',files=restored_files,bytes_done=restored_bytes)
                payload=dict(state=self.state,state_sha256=digest(encoded(self.state)))
            row=super().record(kind,payload,actor)
            if kind=='initial':progress.advance('initial_committed')
            return row
    # Allocate before initialization: even a partial journal owns a stream that
    # must be closed on an exception. Failed startup never creates native-exit.
    fs=PersistentJournal.__new__(PersistentJournal)
    control=None;server=None;stop=threading.Event()
    def serve():
        while not stop.is_set():
            try:client,_=control.accept()
            except OSError:return
            with client:
                try:
                    client.settimeout(3);raw=client.makefile('rb').readline(8193)
                    if len(raw)>8192 or not raw.endswith(b'\n'):raise ValueError('Control bound')
                    value=json.loads(raw)
                    with fs._mutex:
                        if value.get('command')=='health':
                            if value.get('run_id')!=identity['run_id']:raise ValueError('Wrong health identity')
                            response=dict(run_id=identity['run_id'],ready=fs.mount_initialized and not fs.closing and not fs.stopped,
                                          initial_committed=fs.seq>=1,open_handles=len(fs.handles))
                            client.sendall(encoded(response)+b'\n');continue
                        if value.get('command')=='retire':
                            if value.get('run_id')!=identity['run_id'] or mounted(a.mount) or fs.handles:raise ValueError('Unretired namespace or open handle')
                            if fs.closing or fs.finalized or fs.stream.closed:
                                response=dict(retirement_observed=True,finalized=fs.finalized,run_id=identity['run_id'])
                            else:
                                if fs.stopped or not fs.mount_initialized or not fs.native_fuse:raise ValueError('Workspace journal is unhealthy or uninitialized')
                                if not fs.exit_requested:
                                    fs.record('checkpoint',dict(label='retirement-requested',state=fs.state,state_sha256=digest(encoded(fs.state))),actor='framework')
                                    fs.exit_requested=True
                                    # A mount cloned into a native namespace can
                                    # outlive the outer unmount. Request a clean
                                    # libfuse exit and wake its single-threaded
                                    # read. SIGUSR1 stays harmless across teardown;
                                    # SIGTERM could race removed native handlers.
                                    _libfuse.fuse_exit(fs.native_fuse)
                                    signal.pthread_kill(threading.main_thread().ident,signal.SIGUSR1)
                                response=dict(retirement_requested=True,run_id=identity['run_id'],sequence=fs.seq,mechanism='fuse_exit+SIGUSR1')
                            client.sendall(encoded(response)+b'\n');continue
                        if fs.closing or fs.finalized or fs.stream.closed or fs.stopped:raise ValueError('Workspace journal is closed or unhealthy')
                        row=fs.record('checkpoint',dict(label=value['label'],state=fs.state,state_sha256=digest(encoded(fs.state)),clock_bracket=value.get('clock_bracket')),actor='framework')
                        response=dict(sequence=row['sequence'],state_sha256=row['state_sha256'],open_handles=len(fs.handles),healthy=not fs.stopped,
                                      linux_monotonic_ns=row['monotonic_ns'],linux_wall_unix_ns=row['wall_unix_ns'])
                    client.sendall(encoded(response)+b'\n')
                except Exception as error:
                    try:client.sendall(encoded(dict(error=str(error)))+b'\n')
                    except OSError:pass
    try:
        fs.__init__(a.evidence,identity,initial,journal_cap=3*1024**3,identity_path=a.identity)
        atomic(Path(a.evidence)/'service-identity.json',dict(pid=os.getpid(),start_ticks=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19],run_id=identity['run_id'],mount=a.mount))
        control=socket.socket(socket.AF_UNIX);control.bind(a.socket);control.listen(4)
        server=threading.Thread(target=serve,daemon=True);server.start();progress.advance('control_ready')
        # Python's handler interrupts libfuse's blocking read without marking
        # its session as failed. Only the guarded control request calls exit.
        signal.signal(signal.SIGUSR1,lambda *_:None)
        signal.siginterrupt(signal.SIGUSR1,True)
        progress.advance('mount_enter')
        FUSE(fs,a.mount,foreground=True,nothreads=True,raw_fi=True,hard_remove=True,use_ino=True,attr_timeout=0,entry_timeout=0,negative_timeout=0,default_permissions=True)
        if not fs.finalized or not fs.stream.closed:raise RuntimeError('No final filesystem record')
        with (Path(a.evidence)/'native-exit.json').open('x') as f:
            json.dump(dict(run_id=identity['run_id'],libfuse_main_return=0,requested_sigterm=False,requested_fuse_exit=fs.exit_requested,final_sequence=fs.seq,final_state_sha256=digest(encoded(fs.state))),f)
            f.flush();os.fsync(f.fileno())
    finally:
        stop.set()
        if control:
            try:control.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            control.close()
        if server:server.join(4)
        if hasattr(fs,'stream') and not fs.stream.closed:fs.stream.close()

if __name__=='__main__':main()
