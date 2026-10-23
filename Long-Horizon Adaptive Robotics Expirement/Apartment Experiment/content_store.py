"""Lossless content-addressed snapshots and bounded write deltas.

Whole-file SHA256 remains the namespace identity. Raw input is retained once as
compressed 64 KiB chunks; small edits use at most 32 deltas before a chunk-list
snapshot. Old journals without format.json remain readable, never rewritten.
"""
from collections import OrderedDict
import errno
import hashlib
import json
import os
from pathlib import Path
import zlib

CHUNK = 65536
MAX_DEPTH = 32
MAX_FILE = 16 * 1024**2
FORMAT = 'apartment-content-2'

def encoded(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()

def digest(x): return hashlib.sha256(x).hexdigest()

class Store:
    def __init__(self, root, charge=None):
        self.root=Path(root);self.charge=charge;self.cache=OrderedDict();self.cache_bytes=0
        self.modern=(self.root/'format.json').exists()
        if self.modern:
            assert json.loads((self.root/'format.json').read_bytes()) == dict(format=FORMAT, chunk_bytes=CHUNK, max_depth=MAX_DEPTH)

    def create(self):
        (self.root/'chunks').mkdir()
        self._publish(self.root/'format.json',encoded(dict(format=FORMAT,chunk_bytes=CHUNK,max_depth=MAX_DEPTH)))
        self.modern=True

    def _publish(self, path, raw):
        if path.exists():
            if path.read_bytes()!=raw: raise ValueError('Content object collision or corruption')
            return
        if self.charge:self.charge(len(raw))
        temporary=path.with_name(path.name+'.next')
        with temporary.open('xb') as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(temporary,path)
        if os.name!='nt':
            fd=os.open(path.parent,os.O_DIRECTORY)
            try:os.fsync(fd)
            finally:os.close(fd)

    def _chunks(self, raw):
        keys=[]
        for i in range(0,len(raw),CHUNK):
            part=raw[i:i+CHUNK];key=digest(part)
            self._publish(self.root/'chunks'/key,zlib.compress(part,6));keys.append(key)
        return keys

    def _remember(self, key, raw):
        old=self.cache.pop(key,None)
        if old is not None:self.cache_bytes-=len(old)
        self.cache[key]=raw;self.cache_bytes+=len(raw)
        while self.cache_bytes>32*1024**2 or len(self.cache)>64:
            _,old=self.cache.popitem(last=False);self.cache_bytes-=len(old)

    def put(self, raw, patch=None):
        if len(raw)>MAX_FILE: raise OSError(errno.EFBIG,'Content size bound')
        key=digest(raw);path=self.root/'objects'/key
        if path.exists():
            if self.get(key)!=raw:raise ValueError('Content identity collision')
            return key
        descriptor=dict(format=FORMAT,sha256=key,size=len(raw),depth=0)
        if patch is not None:
            base,offset,remove,insert=patch
            before=self.get(base)
            if before[:offset]+insert+before[offset+remove:]!=raw:raise ValueError('Writer patch does not reproduce content')
            prior=json.loads((self.root/'objects'/base).read_bytes())
            if prior['depth']<MAX_DEPTH and len(insert)<max(1,len(raw)//2):
                descriptor.update(base=base,offset=offset,remove=remove,insert_bytes=len(insert),
                                  chunks=self._chunks(insert),depth=prior['depth']+1)
            else:descriptor['chunks']=self._chunks(raw)
        else:descriptor['chunks']=self._chunks(raw)
        self._publish(path,encoded(descriptor));self._remember(key,raw)
        return key

    def get(self, key, depth=0):
        if len(key)!=64 or any(c not in '0123456789abcdef' for c in key):raise ValueError('Invalid content key')
        if key in self.cache:
            raw=self.cache.pop(key);self.cache[key]=raw;return raw
        raw=(self.root/'objects'/key).read_bytes()
        if self.modern:
            if depth>MAX_DEPTH:raise ValueError('Content delta chain bound')
            row=json.loads(raw)
            if row['format']!=FORMAT or row['sha256']!=key or not 0<=row['size']<=MAX_FILE:raise ValueError('Content descriptor identity')
            if not 0<=row['depth']<=MAX_DEPTH:raise ValueError('Content descriptor depth')
            parts=[]
            if len(row['chunks'])>(MAX_FILE+CHUNK-1)//CHUNK:raise ValueError('Content chunk count')
            for chunk in row['chunks']:
                if len(chunk)!=64 or any(c not in '0123456789abcdef' for c in chunk):raise ValueError('Invalid chunk key')
                decoder=zlib.decompressobj();part=decoder.decompress((self.root/'chunks'/chunk).read_bytes(),CHUNK+1)
                if len(part)>CHUNK or not decoder.eof or decoder.unused_data or digest(part)!=chunk:raise ValueError('Chunk corruption')
                parts.append(part)
            raw=b''.join(parts)
            if 'base' in row:
                base=self.get(row['base'],depth+1);at=row['offset'];remove=row['remove']
                if not 0<=at<=len(base) or not 0<=remove<=len(base)-at or len(raw)!=row['insert_bytes']:raise ValueError('Invalid patch')
                raw=base[:at]+raw+base[at+remove:]
            elif row['depth']!=0:raise ValueError('Snapshot depth')
            if len(raw)!=row['size']:raise ValueError('Content size mismatch')
        if digest(raw)!=key:raise ValueError('Content hash mismatch')
        self._remember(key,raw);return raw

def read_object(path):
    path=Path(path)
    return Store(path.parent.parent).get(path.name)
