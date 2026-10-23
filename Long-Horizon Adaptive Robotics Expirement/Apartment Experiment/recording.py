"""Compact original physics samples and independent checkpoint verification."""
from pathlib import Path
import hashlib
import os
import stat
import time
import uuid
import numpy as np
import mujoco
from common import HERE, save, read, inventory, canonical, sha, copy_durable, prefix_sha

class Recorder:
    def __init__(self,root,model,clock_epoch=None):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.model=model;self.pending=[];self.last=-1.
        self.index_path=self.root/'index.json'
        self.index=read(self.index_path) if self.index_path.exists() else []
        self.clock_epoch=clock_epoch or uuid.uuid4().hex

    def sample(self,data,force=False):
        if not force and data.time-self.last<.02-1e-8:return
        self.last=float(data.time)
        self.pending.append((float(data.time),data.qpos.copy(),data.qvel.copy(),time.time_ns(),time.perf_counter_ns()))
        if len(self.pending)>=128:self.flush()

    def flush(self):
        if not self.pending:return
        path=self.root/('states-'+str(len(self.index)).zfill(6)+'.npz')
        if path.exists():raise ValueError('Replay segment collision')
        with path.open('xb') as stream:
            np.savez_compressed(stream,t=np.array([x[0] for x in self.pending]),qpos=np.array([x[1] for x in self.pending]),qvel=np.array([x[2] for x in self.pending]),wall_ns=np.array([x[3] for x in self.pending],dtype=np.int64),monotonic_ns=np.array([x[4] for x in self.pending],dtype=np.int64))
            stream.flush();os.fsync(stream.fileno())
        self.index.append(dict(file=path.name,sha256=sha(path),first=self.pending[0][0],last=self.pending[-1][0],samples=len(self.pending),clock_epoch=self.clock_epoch))
        save(self.index_path,self.index);self.pending=[]

def copy_tree(source,destination):
    source=Path(source);destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    for item in sorted(source.rglob('*')):
        target=destination/item.relative_to(source)
        if item.is_symlink():raise ValueError('Evidence copy must not follow a symlink')
        if item.is_dir():target.mkdir(parents=True,exist_ok=True)
        elif item.is_file():copy_durable(item,target)

def publish_checkpoint(root,state,reason,fault=None):
    """Publish only a fully read-back clean boundary; old pointers survive faults.

    An interrupted pending folder remains evidence. A post-rename/pre-pointer
    interruption leaves an orphan verified checkpoint, never a false pointer.
    """
    root=Path(root);name='session-'+str(state['sessions']).zfill(5)
    folder=root/'checkpoints'/name
    pending=folder.with_name('.pending-'+name+'-'+uuid.uuid4().hex)
    if folder.exists():
        if reason!='hibernation':raise ValueError('Checkpoint identifier already exists')
        folder=folder.with_name(name+'-pause-'+uuid.uuid4().hex)
        pending=folder.with_name('.pending-'+folder.name)
    pending.mkdir(parents=True,exist_ok=False)
    def boundary(phase):
        if fault is not None:fault(phase)
    boundary('created')
    copy_tree(root/'filesystem',pending/'filesystem')
    namespace=root/'filesystem-namespace.json'
    if namespace.exists():
        copy_durable(namespace,pending/'filesystem-namespace.json')
        objects=pending/'filesystem-objects';objects.mkdir()
        # Namespace nodes bind only current immutable contents; stale root
        # objects remain in their original evidence but do not multiply here.
        hashes={n['sha256'] for n in read(namespace)['nodes'].values() if stat.S_ISREG(n['mode'])}
        for digest in sorted(hashes):copy_durable(root/'filesystem-objects'/digest,objects/digest)
    boundary('filesystem_copied')
    state=dict(state)
    state.update(log_bytes=(root/'events.jsonl').stat().st_size,
                 replay_index_sha256=sha(root/'replay/index.json'),scene_sha256=sha(HERE/'scene.py'))
    state['event_prefix_sha256']=prefix_sha(root/'events.jsonl',state['log_bytes'])
    copy_durable(root/'replay/index.json',pending/'replay-index.json')
    save(pending/'state.json',state)
    boundary('state_written')
    save(pending/'manifest.json',dict(files=inventory(pending),schema='apartment-checkpoint-2'))
    boundary('manifest_written')
    receipt=verify_checkpoint(pending)
    verify_prefix(root,pending)
    boundary('verified')
    if not folder.resolve().is_relative_to(root.resolve()) or not pending.resolve().is_relative_to(root.resolve()):
        raise ValueError('Checkpoint publication escaped its evidence root')
    pending.rename(folder)
    boundary('renamed')
    value=dict(path=str(folder),reason=reason,session=state['sessions'],**receipt)
    save(root/'latest-checkpoint.json',value)
    boundary('published')
    return value

def verify_namespace(folder):
    """Authenticate regular-file mirrors and every persistent inode object."""
    folder=Path(folder);path=folder/'filesystem-namespace.json'
    if not path.exists():return
    namespace=read(path);nodes=namespace['nodes'];expected={};hashes=set()
    for name,inode in namespace['paths'].items():
        if not name.startswith('/') or '..' in Path(name).parts:raise ValueError('Invalid inode path')
        node=nodes[str(inode)]
        if stat.S_ISREG(node['mode']):
            digest=node['sha256'];obj=folder/'filesystem-objects'/digest
            if sha(obj)!=digest:raise ValueError('Checkpoint inode content corrupt')
            hashes.add(digest);expected[name.lstrip('/')]=dict(sha256=digest,bytes=obj.stat().st_size)
        elif not (stat.S_ISDIR(node['mode']) or stat.S_ISLNK(node['mode'])):
            raise ValueError('Unsupported checkpoint inode kind')
    if inventory(folder/'filesystem')!=expected:raise ValueError('Checkpoint inode namespace and export disagree')
    if {p.name for p in (folder/'filesystem-objects').iterdir()}!=hashes:raise ValueError('Checkpoint object set differs from live inode references')

def verify_prefix(root,folder):
    """Check an old committed prefix without rejecting its preserved later tail."""
    root=Path(root);folder=Path(folder);state=read(folder/'state.json')
    if prefix_sha(root/'events.jsonl',state['log_bytes'])!=state['event_prefix_sha256']:
        raise ValueError('Checkpoint event prefix changed')
    sequence=0;chain='0'*64;consumed=0;last=None;closed=None
    with (root/'events.jsonl').open('rb') as stream:
        while consumed<state['log_bytes']:
            line=stream.readline();consumed+=len(line);row=__import__('json').loads(line);digest=row.pop('sha256')
            if row['sequence']!=sequence+1 or row['previous']!=chain or hashlib.sha256(canonical(row)).hexdigest()!=digest:
                raise ValueError('Checkpoint prefix event chain corrupt')
            sequence+=1;chain=digest
            last=row
            if row['kind']=='session_closed':closed=row
    if consumed!=state['log_bytes'] or sequence!=state['event_sequence'] or chain!=state['event_chain']:
        raise ValueError('Checkpoint prefix boundary differs')
    if not last or last['kind']!='boundary_checkpoint' or last['payload']['session']!=state['sessions'] or last['payload']['position']!=state['position']:
        raise ValueError('Checkpoint state differs from its boundary event')
    if not closed or closed['payload']['session']!=state['sessions'] or not all(closed['payload']['proof'].get(k) is True for k in ('normal_model_completion','filesystem_closeout','runtime_retired')):
        raise ValueError('Checkpoint has no matching normal closeout proof')
    index=read(folder/'replay-index.json')
    if sha(folder/'replay-index.json')!=state['replay_index_sha256']:raise ValueError('Checkpoint replay index differs')
    previous=-float('inf')
    for row in index:
        if Path(row['file']).name!=row['file'] or row['first']<previous:raise ValueError('Replay prefix order/path invalid')
        if sha(root/'replay'/row['file'])!=row['sha256']:raise ValueError('Checkpoint replay chunk corrupt')
        previous=row['last']
    if not index or index[-1]['last']!=state['world']['sim_time'] or last['sim_time']!=state['world']['sim_time']:
        raise ValueError('Checkpoint world and replay boundary time differ')
    return dict(passed=True,event_sequence=sequence,event_chain=chain,replay_chunks=len(index))

def geoms(model,data):
    return [dict(type=int(model.geom_type[i]),size=model.geom_size[i].tolist(),color=model.geom_rgba[i].tolist(),
                 position=data.geom_xpos[i].tolist(),rotation=data.geom_xmat[i].tolist(),group=int(model.geom_group[i]))
            for i in range(model.ngeom)]

def verify_checkpoint(folder):
    folder=Path(folder);manifest=read(folder/'manifest.json')
    actual=inventory(folder)
    actual.pop('manifest.json',None)
    if actual!=manifest['files']:raise ValueError('Checkpoint bytes do not match manifest')
    state=read(folder/'state.json')
    if state['phase']!='between_sessions' or not state['world']['docked'] or state['world']['active'] is not None:
        raise ValueError('Checkpoint is not a clean docked session boundary')
    from world import World
    if state.get('scene_sha256',sha(HERE/'scene.py'))!=sha(HERE/'scene.py'):raise ValueError('Checkpoint scene identity differs')
    if manifest.get('schema')=='apartment-checkpoint-2':verify_namespace(folder)
    w=World();w.restore(state['world'])
    reconstructed=w.snapshot()
    w.close()
    if not np.array_equal(np.array(state['world']['physics']),np.array(reconstructed['physics'])):
        raise ValueError('Physics checkpoint reconstruction changed state')
    if manifest.get('schema')=='apartment-checkpoint-2' and canonical(state['world'])!=canonical(reconstructed):
        raise ValueError('World/RNG/task checkpoint reconstruction changed state')
    return dict(passed=True,state_sha256=sha(folder/'state.json'),files=len(actual),manifest_sha256=sha(folder/'manifest.json'))

class Replay:
    def __init__(self,root):
        from world import World
        self.root=Path(root)
        if (self.root/'run.json').exists():
            expected=read(self.root/'run.json')['source_identity']
            # Reconstruction sets original qpos/qvel and runs mj_forward; it does
            # not rerun task dynamics or success detection. Geometry must match.
            for name in ('scene.py',):
                if expected['apartment/'+name]!=sha(HERE/name):raise ValueError('Replay requires the recorded scene and physics source: '+name)
        self.world=World();self.cached=None;self.chunk=None

    def frame(self,t):
        index=read(self.root/'replay/index.json')
        if not index:raise ValueError('No recorded states')
        row=index[0]
        for candidate in index:
            if candidate['first']<=t:row=candidate
        path=self.root/'replay'/row['file']
        if self.cached!=str(path):
            if sha(path)!=row['sha256']:raise ValueError('Replay source corruption')
            if self.chunk:self.chunk.close()
            self.chunk=np.load(path);self.cached=str(path)
        k=max(0,int(np.searchsorted(self.chunk['t'],t,side='right'))-1)
        d=self.world.data;d.qpos[:]=self.chunk['qpos'][k];d.qvel[:]=self.chunk['qvel'][k];d.time=float(self.chunk['t'][k])
        mujoco.mj_forward(self.world.model,d)
        return dict(sim_time=d.time,requested_time=t,sample_age=max(0,t-d.time),geoms=geoms(self.world.model,d),
                    robot=self.world.body('base').tolist(),range=[index[0]['first'],index[-1]['last']],
                    provenance=dict(file=str(path),sha256=row['sha256'],sample=k,kind='reconstruction from original sampled physics state'))

    def close(self):
        if self.chunk:self.chunk.close()
        self.world.close()
