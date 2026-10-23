"""Separate agent note bound and reserved framework terminal-note capacity."""
import hashlib
import json
from array import array
from collections.abc import Sequence
from instrumented_journal import InstrumentedJournal
from supervisor import require,atomic_bytes,canonical

class DiskEvents(Sequence):
    """Exact durable events with small offsets/hashes, not an expanding object tree.

    The inherited writer calls append only after both public and protected
    copies have been flushed and fsynced. This index is reconstructible metadata;
    no acknowledgement or durable-write ordering is moved or weakened.
    """
    def __init__(self,path):
        self.path=path;self.offsets=array('Q',[0]);self.hashes=[]
    def __len__(self):return len(self.hashes)
    def append(self,item):
        raw=canonical(item)+b'\n'
        require(item['event_id']==len(self)+1,'event_sequence','Non-contiguous history')
        require(self.path.stat().st_size==self.offsets[-1]+len(raw),'event_size','Durable history size mismatch')
        self.offsets.append(self.offsets[-1]+len(raw));self.hashes.append(hashlib.sha256(raw).digest())
    def __getitem__(self,key):
        if isinstance(key,slice):return [self[i] for i in range(*key.indices(len(self))) ]
        if key<0:key+=len(self)
        if not 0<=key<len(self):raise IndexError(key)
        with self.path.open('rb') as stream:
            stream.seek(self.offsets[key]);raw=stream.read(self.offsets[key+1]-self.offsets[key])
        require(hashlib.sha256(raw).digest()==self.hashes[key],'event_hash','Durable history bytes changed')
        return json.loads(raw)

class Journal(InstrumentedJournal):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.events=DiskEvents(self.events_path)
    def _note(self,content,limit):
        require(isinstance(content,str),'invalid_note','UTF-8 note required',400)
        raw=content.encode();require(len(raw)<=limit,'invalid_note','Note bound exceeded',413)
        path=self.workspace/'Continuity.md';require(not path.is_symlink(),'invalid_note','Host mirror must be regular',400)
        previous=path.read_bytes() if path.exists() else b''
        require(len(previous)<=65536,'invalid_note','Existing note exceeds reserved capacity',413)
        require(self.bytes+len(previous)+len(raw)<self.limit-2*1024**2,'storage_limit','Evidence budget reached',507)
        for value in (previous,raw):
            dest=self.root/'continuity-history'/(hashlib.sha256(value).hexdigest()+'.md')
            if not dest.exists():atomic_bytes(dest,value);self.bytes+=len(value)
        atomic_bytes(path,raw)
        return {'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'previous_sha256':hashlib.sha256(previous).hexdigest()}
    def continuity(self,content):return self._note(content,32768)
    def framework_continuity(self,content):return self._note(content,65536)
    def read_continuity(self):
        path=self.workspace/'Continuity.md';require(not path.is_symlink(),'invalid_note','Host mirror must be regular',400)
        raw=path.read_bytes() if path.exists() else b''
        require(len(raw)<=65536,'invalid_note','Note exceeds reserved capacity',413)
        return {'ok':True,'content':raw.decode(),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
