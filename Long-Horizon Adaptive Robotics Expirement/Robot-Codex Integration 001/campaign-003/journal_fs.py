"""Linux-only protected transactional workspace filesystem over libfuse3.

No backing path is exposed to the guest. Successful mutation replies follow
durable content + hash-chained delta publication. No polling/watcher claims.
"""
from __future__ import annotations
import argparse
import copy
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import threading
import time
import socket
import signal

sys.path.insert(0, str(Path(__file__).resolve().parent/'vendor'))
from mfusepy import FUSE, Operations, FuseOSError, fuse_get_context

def encoded(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(x): return hashlib.sha256(x).hexdigest()

class JournalFS(Operations):
    use_ns=True
    def __init__(self, evidence, identity, initial=None, cap=256*1024**2, journal_cap=1024**3, identity_path=None):
        self.root=Path(evidence);self.root.mkdir(parents=True,exist_ok=False)
        (self.root/'objects').mkdir()
        self.stream=(self.root/'mutations.jsonl').open('xb',buffering=0)
        self.identity=dict(identity);self.identity_path=identity_path;self.cap=cap;self.journal_cap=journal_cap
        self.seq=0;self.chain='0'*64;self.stopped=False;self.used=0;self.finalized=False
        self._mutex=threading.RLock();self.next_inode=2;self.next_handle=1;self.handles={}
        ns=time.time_ns()
        self.state={'paths':{'/':1},'nodes':{'1':self.node(stat.S_IFDIR|0o755,ns)}}
        if initial:
            for name,data in sorted(initial.items(),key=lambda row:(row[0].count('/'),row[0])):
                path='/'+name.strip('/')
                parent=str(PurePosixPath(path).parent)
                if parent not in self.state['paths']: raise ValueError('Initial parent missing: '+parent)
                if isinstance(data,dict) and 'symlink' in data:
                    node=self.node(stat.S_IFLNK|0o777,ns);node['target']=data['symlink'];node['size']=len(data['symlink'].encode())
                elif data is None: node=self.node(stat.S_IFDIR|0o755,ns)
                else:
                    raw=data.encode() if isinstance(data,str) else bytes(data)
                    node=self.node(stat.S_IFREG|0o644,ns);node.update(sha256=self.blob(raw),size=len(raw))
                inode=self.next_inode;self.next_inode+=1
                self.state['paths'][path]=inode;self.state['nodes'][str(inode)]=node
        self.record('initial',{'state':self.state,'state_sha256':digest(encoded(self.state))},actor='framework')

    @staticmethod
    def node(mode,ns):
        return dict(mode=mode,uid=os.getuid(),gid=os.getgid(),atime_ns=ns,mtime_ns=ns,ctime_ns=ns,size=0)

    def blob(self,raw):
        key=digest(raw);path=self.root/'objects'/key
        if path.exists() and digest(path.read_bytes())!=key:
            self.stopped=True;raise FuseOSError(errno.EIO)
        if not path.exists():
            if self.used+len(raw)>self.journal_cap-1024*1024: raise FuseOSError(errno.ENOSPC)
            with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
            fd=os.open(path.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
            self.used+=len(raw)
        return key

    def record(self,kind,payload,actor=None):
        if self.stopped:raise FuseOSError(errno.EIO)
        if self.identity_path:
            current=json.loads(Path(self.identity_path).read_text())
            if current.get('run_id')!=self.identity.get('run_id'):self.stopped=True;raise FuseOSError(errno.EIO)
            self.identity=current
        try:uid,gid,pid=fuse_get_context()
        except Exception:uid,gid,pid=os.getuid(),os.getgid(),os.getpid()
        try:
            proc=Path('/proc')/str(pid)
            fields=(proc/'stat').read_text().rsplit(')',1)[1].split()
            process={'pid':pid,'parent_pid':int(fields[1]),'start_ticks':fields[19],
                     'pid_namespace':os.readlink(proc/'ns/pid'),
                     'namespace_role':'outer-runtime' if os.readlink(proc/'ns/pid')==os.readlink('/proc/self/ns/pid') else 'isolated-runtime'}
        except OSError:process={'pid':pid,'identity_unavailable':True}
        row={'schema':'campaign003-mutation-1','sequence':self.seq+1,'previous_record_sha256':self.chain,
             **self.identity,'clock_source':'linux-CLOCK_MONOTONIC','monotonic_ns':time.monotonic_ns(),
             'wall_unix_ns':time.time_ns(),'actor':actor or 'workspace-process','pid':pid,'process':process,
             'type':kind,**payload}
        raw=encoded(row);key=digest(raw);line=encoded({**row,'record_sha256':key})+b'\n'
        if self.used+len(line)>self.journal_cap: self.stopped=True;raise FuseOSError(errno.ENOSPC)
        try:
            if self.stream.write(line)!=len(line):raise OSError(errno.EIO,'Short journal write')
            os.fsync(self.stream.fileno())
        except BaseException:self.stopped=True;raise
        self.seq+=1;self.chain=key;self.used+=len(line)
        return row

    def inode(self,path,fh=None):
        if fh is not None:
            handle=fh.fh if hasattr(fh,'fh') else fh
            if handle in self.handles:return self.handles[handle]
        if path not in self.state['paths']:raise FuseOSError(errno.ENOENT)
        return self.state['paths'][path]

    def content(self,inode):
        node=self.state['nodes'][str(inode)]
        return (self.root/'objects'/node['sha256']).read_bytes() if node.get('sha256') else b''

    def valid_parent(self,state,path):
        parent=str(PurePosixPath(path).parent)
        if parent not in state['paths']:raise FuseOSError(errno.ENOENT)
        if not stat.S_ISDIR(state['nodes'][str(state['paths'][parent])]['mode']):raise FuseOSError(errno.ENOTDIR)

    def mutate(self,op,args,fn):
        with self._mutex:
            if self.stopped:raise FuseOSError(errno.EIO)
            before=self.state;after=copy.deepcopy(before)
            started=time.monotonic_ns()
            try:
                result=fn(after)
                referenced=set(after['paths'].values())|set(self.handles.values())
                after['nodes']={k:v for k,v in after['nodes'].items() if int(k) in referenced}
                if sum(n['size'] for n in after['nodes'].values())>self.cap:raise FuseOSError(errno.ENOSPC)
                delta={}
                for area in ('paths','nodes'):
                    delta[area]={'set':{k:v for k,v in after[area].items() if k not in before[area] or before[area][k]!=v},
                                 'remove':[k for k in before[area] if k not in after[area]]}
                self.record('mutation',dict(operation=op,arguments=args,started_monotonic_ns=started,
                    before_state_sha256=digest(encoded(before)),after_state_sha256=digest(encoded(after)),delta=delta))
                self.state=after
                return result
            except OSError as e:
                if not self.stopped:self.record('rejected_mutation',dict(operation=op,arguments=args,errno=e.errno))
                if e.errno in (errno.ENOSPC,errno.EIO,errno.EFBIG):self.stopped=True
                raise

    def getattr(self,path,fh=None):
        with self._mutex:
            inode=self.inode(path,fh);n=self.state['nodes'][str(inode)]
            return dict(st_mode=n['mode'],st_uid=n['uid'],st_gid=n['gid'],st_ino=inode,
                st_nlink=sum(v==inode for v in self.state['paths'].values())+(1 if stat.S_ISDIR(n['mode']) else 0),
                st_size=n['size'],st_atime=n['atime_ns'],st_mtime=n['mtime_ns'],st_ctime=n['ctime_ns'])

    def readdir(self,path,fh):
        with self._mutex:
            self.inode(path)
            return ['.','..']+[PurePosixPath(p).name for p in self.state['paths'] if p!=path and str(PurePosixPath(p).parent)==path]

    def readlink(self,path):return self.state['nodes'][str(self.inode(path))]['target']

    def new(self,path,mode,target=None):
        inode=self.next_inode;self.next_inode+=1
        def apply(state):
            self.valid_parent(state,path)
            if path in state['paths']:raise FuseOSError(errno.EEXIST)
            n=self.node(mode,time.time_ns())
            if stat.S_ISREG(mode):n['sha256']=self.blob(b'')
            if target is not None:n.update(target=target,size=len(target.encode()))
            state['paths'][path]=inode;state['nodes'][str(inode)]=n
        self.mutate('create',dict(path=path,mode=mode,target=target),apply)
        return inode

    def mkdir(self,path,mode):self.new(path,stat.S_IFDIR|(mode&0o777));return 0
    def symlink(self,target,source):self.new(target,stat.S_IFLNK|0o777,source);return 0

    def make_handle(self,inode,fi):
        handle=self.next_handle;self.next_handle+=1;self.handles[handle]=inode
        fi.fh=handle;fi.direct_io=1;fi.keep_cache=0
        return 0

    def create(self,path,mode,fi=None):
        with self._mutex:return self.make_handle(self.new(path,stat.S_IFREG|(mode&0o777)),fi)

    def open(self,path,fi):
        with self._mutex:
            inode=self.inode(path)
            if not stat.S_ISREG(self.state['nodes'][str(inode)]['mode']):raise FuseOSError(errno.EISDIR)
            if fi.flags&os.O_TRUNC:self.truncate(path,0)
            return self.make_handle(inode,fi)

    def read(self,path,size,offset,fh):
        with self._mutex:
            inode=self.inode(path,fh);raw=self.content(inode)[offset:offset+size]
            self.record('read',dict(path=path,inode=inode,offset=offset,bytes=len(raw),
                content_sha256=self.state['nodes'][str(inode)].get('sha256'),returned_sha256=digest(raw)))
            return raw

    def write(self,path,data,offset,fh):
        inode=self.inode(path,fh);data=bytes(data)
        def apply(state):
            if offset<0 or offset+len(data)>16*1024**2:raise FuseOSError(errno.EFBIG)
            old=self.content(inode);new=old[:offset].ljust(offset,b'\0')+data+old[offset+len(data):]
            n=state['nodes'][str(inode)];ns=time.time_ns();n.update(sha256=self.blob(new),size=len(new),mtime_ns=ns,ctime_ns=ns)
            return len(data)
        return self.mutate('write',dict(path=path,inode=inode,offset=offset,bytes=len(data),input_sha256=digest(data)),apply)

    def truncate(self,path,length,fh=None):
        inode=self.inode(path,fh)
        def apply(state):
            if not 0<=length<=16*1024**2:raise FuseOSError(errno.EFBIG)
            raw=self.content(inode)[:length].ljust(length,b'\0');ns=time.time_ns()
            state['nodes'][str(inode)].update(sha256=self.blob(raw),size=length,mtime_ns=ns,ctime_ns=ns)
        self.mutate('truncate',dict(path=path,inode=inode,length=length),apply);return 0

    def unlink(self,path):
        def apply(state):
            inode=self.inode(path)
            if stat.S_ISDIR(state['nodes'][str(inode)]['mode']):raise FuseOSError(errno.EISDIR)
            del state['paths'][path]
        self.mutate('unlink',dict(path=path),apply);return 0

    def rmdir(self,path):
        def apply(state):
            if path=='/':raise FuseOSError(errno.EBUSY)
            if not stat.S_ISDIR(state['nodes'][str(self.inode(path))]['mode']):raise FuseOSError(errno.ENOTDIR)
            if any(p.startswith(path+'/') for p in state['paths']):raise FuseOSError(errno.ENOTEMPTY)
            del state['paths'][path]
        self.mutate('rmdir',dict(path=path),apply);return 0

    def rename(self,old,new):
        def apply(state):
            inode=self.inode(old);self.valid_parent(state,new)
            if state['paths'].get(new)==inode:return
            if old=='/' or new.startswith(old+'/'):raise FuseOSError(errno.EINVAL)
            if new in state['paths']:
                source_dir=stat.S_ISDIR(state['nodes'][str(inode)]['mode'])
                target_dir=stat.S_ISDIR(state['nodes'][str(state['paths'][new])]['mode'])
                if source_dir!=target_dir:raise FuseOSError(errno.EISDIR if target_dir else errno.ENOTDIR)
                if any(p.startswith(new+'/') for p in state['paths']):raise FuseOSError(errno.ENOTEMPTY)
            moves={p:new+p[len(old):] for p in state['paths'] if p==old or p.startswith(old+'/')}
            values={target:state['paths'][source] for source,target in moves.items()}
            for source in moves:del state['paths'][source]
            state['paths'].update(values)
        self.mutate('rename',dict(old=old,new=new),apply);return 0

    def link(self,target,source):
        def apply(state):
            self.valid_parent(state,target);inode=self.inode(source)
            if target in state['paths']:raise FuseOSError(errno.EEXIST)
            if not stat.S_ISREG(state['nodes'][str(inode)]['mode']):raise FuseOSError(errno.EPERM)
            state['paths'][target]=inode
        self.mutate('link',dict(source=source,target=target),apply);return 0

    def chmod(self,path,mode,fh=None):
        inode=self.inode(path,fh)
        def apply(state):state['nodes'][str(inode)].update(mode=stat.S_IFMT(state['nodes'][str(inode)]['mode'])|(mode&0o777),ctime_ns=time.time_ns())
        self.mutate('chmod',dict(path=path,inode=inode,mode=mode&0o777),apply);return 0

    def chown(self,path,uid,gid,fh=None):
        def apply(state):
            if uid not in (-1,os.getuid()) or gid not in (-1,os.getgid()):raise FuseOSError(errno.EPERM)
        self.mutate('chown',dict(path=path,uid=uid,gid=gid),apply)
        return 0

    def deny(self,operation,path):
        with self._mutex:self.record('rejected_mutation',dict(operation=operation,arguments={'path':path},errno=errno.ENOTSUP))
        raise FuseOSError(errno.ENOTSUP)
    def mknod(self,path,mode,dev):return self.deny('mknod',path)
    def setxattr(self,path,name,value,options,position=0):return self.deny('setxattr',path)
    def removexattr(self,path,name):return self.deny('removexattr',path)
    def fallocate(self,path,mode,offset,length,fh):return self.deny('fallocate',path)
    def fsyncdir(self,path,datasync,fh):os.fsync(self.stream.fileno());return 0

    def utimens(self,path,times=None):
        inode=self.inode(path)
        def apply(state):
            now=time.time_ns();values=(now,now) if times is None else tuple(int(v) for v in times)
            state['nodes'][str(inode)].update(atime_ns=values[0],mtime_ns=values[1],ctime_ns=now)
        self.mutate('utimens',dict(path=path),apply);return 0

    def flush(self,path,fh):os.fsync(self.stream.fileno());return 0
    def fsync(self,path,datasync,fh):return self.flush(path,fh)
    def release(self,path,fh):
        with self._mutex:
            handle=fh.fh if hasattr(fh,'fh') else fh
            inode=self.handles.pop(handle,None)
            if inode is not None and inode not in self.state['paths'].values() and inode not in self.handles.values():
                self.mutate('close_unlinked',{'inode':inode},lambda state:None)
        return 0
    def statfs(self,path):
        free=max(0,self.cap-sum(n['size'] for n in self.state['nodes'].values()))//4096
        return dict(f_bsize=4096,f_frsize=4096,f_blocks=self.cap//4096,f_bfree=free,f_bavail=free,f_files=100000,f_ffree=99900,f_namemax=255)
    def destroy(self,path):
        with self._mutex:
            if not self.stopped:
                self.record('final',dict(state=self.state,state_sha256=digest(encoded(self.state))),actor='framework')
                self.finalized=True
            self.stream.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--mount',required=True);p.add_argument('--evidence',required=True);p.add_argument('--initial',required=True);p.add_argument('--identity',required=True)
    a=p.parse_args();initial=json.loads(Path(a.initial).read_text());identity=json.loads(Path(a.identity).read_text())
    fs=JournalFS(a.evidence,identity,initial,identity_path=a.identity)
    control=socket.socket(socket.AF_UNIX);control.bind(str(Path(a.evidence)/'control.sock'));control.listen(4)
    retirement_requested=threading.Event()
    def checkpoint_server():
        while not fs.stopped:
            try:client,_=control.accept()
            except OSError:return
            with client:
                try:
                    client.settimeout(3);raw=client.makefile('rb').readline(8193)
                    if len(raw)>8192:raise ValueError('Control size')
                    value=json.loads(raw)
                    if value.get('command')=='retire':
                        # Only the protected outer controller can reach this
                        # socket. Native libfuse handles SIGTERM gracefully;
                        # unmount alone may leave a clone in a service namespace.
                        with fs._mutex:
                            if value.get('run_id')!=fs.identity['run_id']:
                                raise ValueError('Retirement identity mismatch')
                            # Inspect kernel metadata, never recurse through the
                            # FUSE mount while holding its transaction mutex.
                            if any(line.split()[4]==a.mount for line in Path('/proc/self/mountinfo').read_text().splitlines()):
                                raise ValueError('Retirement requires outer unmount')
                            if fs.handles:
                                raise ValueError('Retirement has open filesystem handles')
                            row=fs.record('checkpoint',{'label':'retirement-requested',
                                'state':fs.state,'state_sha256':digest(encoded(fs.state))},actor='framework')
                            retirement_requested.set()
                            client.sendall(encoded({'retirement_requested':True,'run_id':fs.identity['run_id'],
                                'sequence':row['sequence'],'signal':'SIGTERM'})+b'\n')
                        os.kill(os.getpid(),signal.SIGTERM)
                        return
                    with fs._mutex:
                        row=fs.record('checkpoint',{'label':value['label'],'clock_bracket':value.get('clock_bracket'),
                            'state':fs.state,'state_sha256':digest(encoded(fs.state))},actor='framework')
                        reply={'sequence':row['sequence'],'state_sha256':row['state_sha256'],
                               'linux_monotonic_ns':row['monotonic_ns'],'linux_wall_unix_ns':row['wall_unix_ns']}
                    client.sendall(encoded(reply)+b'\n')
                except Exception as e:
                    try:client.sendall(encoded({'error':str(e)})+b'\n')
                    except OSError:pass
    threading.Thread(target=checkpoint_server,daemon=True).start()
    native_return=0
    try:
        FUSE(fs,a.mount,foreground=True,nothreads=True,raw_fi=True,hard_remove=True,use_ino=True,
             attr_timeout=0,entry_timeout=0,negative_timeout=0,default_permissions=True)
    except RuntimeError as error:
        # libfuse3.14 helper.c maps a signal-ended loop to return8. Accept
        # that documented path only after our own admitted shutdown request
        # and the actual durable destroy callback; never hide an external stop.
        if error.args!=(8,) or not retirement_requested.is_set() or not fs.finalized or not fs.stream.closed:
            raise
        native_return=8
    if not fs.finalized:raise RuntimeError('Journal destroy did not finalize')
    with (Path(a.evidence)/'native-exit.json').open('xb') as stream:
        stream.write(encoded({'schema':'campaign003-native-fuse-exit-1','run_id':identity['run_id'],
            'libfuse_main_return':native_return,'requested_sigterm':retirement_requested.is_set(),
            'final_sequence':fs.seq,'final_state_sha256':digest(encoded(fs.state))})+b'\n')
        stream.flush();os.fsync(stream.fileno())
    control.close()

if __name__=='__main__':main()
