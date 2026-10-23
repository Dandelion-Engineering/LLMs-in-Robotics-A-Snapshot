"""sustainable-evidence-3: future-native exact objects, bounded images, no r4 edits.

Protected operator storage. Never mount this database in a candidate sandbox.
Single writer; serialise gateway calls before using. All clocks are caller supplied.
"""
from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass, asdict
import hashlib
import gzip
import io
import json
import math
from pathlib import Path
import sqlite3
import struct
import zlib

VERSION = 'sustainable-evidence-3'
READABLE_VERSIONS = {'sustainable-evidence-1','sustainable-evidence-2', VERSION}
INTERN_BYTES = 8192
MAX_CONTAINER_BYTES = 512_000_000
GB = 1_000_000_000


class RecordingFailure(RuntimeError):
    """Supervisor must stop and classify the attempt as evidence-recording failure."""


def digest(blob):
    return hashlib.sha256(blob).digest()


def file_digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda:stream.read(1024*1024),b''): h.update(data)
    return h.hexdigest()


def container_bytes(directory):
    path=Path(directory); manifest=path/'container-manifest.json'
    return json.loads(manifest.read_text(encoding='utf-8'))['bytes']+manifest.stat().st_size


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def u32(n):
    return struct.pack('<I', n)


def pack(value):
    """Reversible JSON-value binary encoding. Floats retain all IEEE754 bits."""
    if value is None: return b'n'
    if type(value) is bool: return b't' if value else b'f'
    if isinstance(value, float):
        if not math.isfinite(value): raise ValueError('Nonfinite JSON float')
        return b'd' + struct.pack('<d', value)
    if type(value) is int:
        data = str(value).encode('ascii'); return b'i' + u32(len(data)) + data
    if type(value) is str:
        data = value.encode('utf-8', errors='surrogatepass'); return b's' + u32(len(data)) + data
    if isinstance(value, (list,tuple)): return b'l' + u32(len(value)) + b''.join(pack(v) for v in value)
    if isinstance(value, dict):
        if not all(type(k) is str for k in value): raise TypeError('JSON object keys must be strings')
        return b'o' + u32(len(value)) + b''.join(pack(k) + pack(v) for k, v in value.items())
    raise TypeError(type(value))


def unpack(blob, object_get=None, telemetry_get=None):
    stream = io.BytesIO(blob)
    def read(n):
        data = stream.read(n)
        if len(data) != n: raise RecordingFailure('Truncated binary object')
        return data
    def count(): return struct.unpack('<I', read(4))[0]
    def one():
        tag = read(1)
        if tag == b'n': return None
        if tag == b't': return True
        if tag == b'f': return False
        if tag == b'd': return struct.unpack('<d', read(8))[0]
        if tag == b'i': return int(read(count()))
        if tag == b's': return read(count()).decode('utf-8', errors='surrogatepass')
        if tag == b'l': return [one() for _ in range(count())]
        if tag == b'o': return {one(): one() for _ in range(count())}
        if tag == b'Z': return unpack(zlib.decompress(read(count())),object_get,telemetry_get)
        if tag == b'V':
            keys,values=one(),one()
            return dict(zip(keys,values,strict=True))
        if tag == b'U':
            keys,rows=one(),one()
            return [{key:row[key] for key in keys} for row in rows]
        if tag == b'J':
            recipe,value=one(),one()
            return recipe['prefix']+json.dumps(value,**recipe['options'])+recipe['suffix']
        if tag == b'R':
            if object_get is None: raise RecordingFailure('Object reader required')
            return object_get(read(32))
        if tag == b'T':
            if telemetry_get is None: raise RecordingFailure('Telemetry reader required')
            values = []
            for _ in range(count()):
                start, length = struct.unpack('<QI', read(12))
                values.extend(telemetry_get(start, length))
            return values
        raise RecordingFailure('Unknown binary tag')
    result = one()
    if stream.read(1): raise RecordingFailure('Trailing binary object bytes')
    return result


@dataclass(frozen=True)
class ImagePolicy:
    sparse_period_s: float = 30.0
    representative_period_s: float = 0.5
    representative_until_s: float = 600.0
    pre_s: float = 2.0
    post_s: float = 3.0
    ring_bytes: int = 24_000_000
    ring_frames: int = 64
    image_quota_bytes: int = 22_000_000
    maximum_trigger_windows: int = 4
    require_complete_representative: bool = True

    def validate(self):
        for name in ('sparse_period_s','representative_period_s','pre_s','post_s','representative_until_s'):
            value=getattr(self,name)
            if type(value) not in (int,float) or not math.isfinite(value) or value<0:
                raise ValueError('Invalid finite image duration: '+name)
        if self.sparse_period_s==0 or self.representative_period_s==0: raise ValueError('Positive image periods required')
        for name in ('ring_bytes','ring_frames','image_quota_bytes','maximum_trigger_windows'):
            value=getattr(self,name)
            if type(value) is not int or value<0: raise ValueError('Invalid integer image limit: '+name)
        if type(self.require_complete_representative) is not bool: raise ValueError('Boolean representative requirement required')


class Recorder:
    def __init__(self, directory, *, run_id, core_quota_bytes=200_000_000,
                 policy=ImagePolicy(), representative=False, flush_rows=1000):
        policy.validate()
        if (type(core_quota_bytes) is not int or core_quota_bytes<4096 or
            type(flush_rows) is not int or flush_rows<1 or type(representative) is not bool):
            raise ValueError('Invalid integer quota/chunk or representative flag')
        self.path = Path(directory); self.path.mkdir(parents=True, exist_ok=False)
        # FutureEvidence serializes all accesses with its owner lock, including
        # the existing runtime's bounded raw-encoding worker callbacks.
        self.db = sqlite3.connect(self.path / 'evidence.sqlite',check_same_thread=False)
        self.db.executescript('''PRAGMA journal_mode=DELETE; PRAGMA synchronous=FULL;
        CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE objects(hash BLOB PRIMARY KEY,payload BLOB NOT NULL);
        CREATE TABLE telemetry(id INTEGER PRIMARY KEY,hash BLOB UNIQUE,payload BLOB NOT NULL);
        CREATE TABLE events(id INTEGER PRIMARY KEY,payload BLOB NOT NULL);
        CREATE TABLE motion(id INTEGER PRIMARY KEY,hash BLOB NOT NULL,payload BLOB NOT NULL);
        CREATE TABLE images(id TEXT PRIMARY KEY,time REAL NOT NULL,status TEXT NOT NULL,
          reason TEXT NOT NULL,rgb BLOB,depth BLOB,rgb_sha TEXT,depth_sha TEXT);
        CREATE TABLE documents(name TEXT PRIMARY KEY,payload BLOB NOT NULL);
        ''')
        self.policy = policy; self.representative = representative; self.core_limit = core_quota_bytes
        self.flush_rows = flush_rows; self.motion_rows = []; self.stopped = False
        self.telemetry_cache = OrderedDict(); self.ring = deque(); self.ring_size = 0
        self.dictionary_anchors = OrderedDict()
        self.last_sparse = None; self.trigger_end = -math.inf; self.triggers = 0
        self.image_bytes = 0; self.pending_bytes = 0; self.sequence = 0
        self.last_durable_event=None
        self.db.executemany('INSERT INTO meta VALUES(?,?)', [
            ('version', VERSION), ('run_id', run_id), ('policy', json.dumps(asdict(policy))),
            ('representative', json.dumps(representative)), ('state', 'recording'),
            ('core_quota_bytes', str(core_quota_bytes))])
        self.db.commit()

    def fail(self, reason):
        self.stopped = True
        try: self.db.rollback()
        except sqlite3.Error: pass
        # This bounded failure marker is outside the scientific quota by design.
        (self.path / 'RECORDING_FAILED.json').write_text(json.dumps({
            'version': VERSION, 'failure': 'evidence_recording_failure',
            'reason': reason, 'last_durable_event': self.last_durable_event,
            'scientific_admission': False}, indent=2) + '\n', encoding='utf-8')
        raise RecordingFailure(reason)

    def _guard(self, size=0):
        if self.stopped: raise RecordingFailure('Recorder already stopped')
        # Count every stored payload plus conservative table/index/page overhead.
        self.pending_bytes += size
        if self.pending_bytes > self.core_limit: self.fail('Core quota exceeded; no scientific evidence truncation allowed')

    def _intern(self, encoded, family=None):
        if family is not None: family=digest(family)
        key = digest(encoded)
        if self.db.execute('SELECT 1 FROM objects WHERE hash=?', (key,)).fetchone() is None:
            compressed = zlib.compress(encoded, 3)
            anchor=self.dictionary_anchors.get(family) if family is not None else None
            if anchor:
                compressor=zlib.compressobj(3,zdict=anchor[1])
                delta=compressor.compress(encoded)+compressor.flush()
                if len(delta)+33<len(compressed): compressed=b'D'+anchor[0]+delta
            elif family is not None and len(encoded)<=1_000_000:
                # Anchors always use standalone compression, so dictionary
                # dependencies have depth one. RAM is bounded to 128 * 32 KiB.
                self.dictionary_anchors[family]=(key,encoded[-32768:])
                if len(self.dictionary_anchors)>128: self.dictionary_anchors.popitem(last=False)
            self._guard(len(compressed) + 128)
            self.db.execute('INSERT INTO objects VALUES(?,?)', (key, compressed))
        return b'R' + key

    def _telemetry(self, rows):
        # Canonical stored rows can be shared even when JSON text sorted their
        # keys. U records the exact original key order for this occurrence.
        order=list(rows[0]) if rows and isinstance(rows[0],dict) else None
        reorder=order is not None and all(isinstance(row,dict) and list(row)==order for row in rows)
        stored_rows=[{key:row[key] for key in sorted(row)} for row in rows] if reorder else rows
        ids = []
        for row in stored_rows:
            data = pack(row); key = digest(data)
            ident = self.telemetry_cache.get(key)
            if ident is None:
                found = self.db.execute('SELECT id FROM telemetry WHERE hash=?', (key,)).fetchone()
                if found: ident = found[0]
                else:
                    encoded=(b'V'+self._intern(pack(list(row)))+pack(list(row.values()))) if isinstance(row,dict) else data
                    compressed = zlib.compress(encoded, 3); self._guard(len(compressed) + 160)
                    ident = self.db.execute('INSERT INTO telemetry(hash,payload) VALUES(?,?)', (key, compressed)).lastrowid
                self.telemetry_cache[key] = ident
                if len(self.telemetry_cache) > 4096: self.telemetry_cache.popitem(last=False)
            ids.append(ident)
        spans = []
        for ident in ids:
            if spans and spans[-1][0] + spans[-1][1] == ident: spans[-1][1] += 1
            else: spans.append([ident, 1])
        encoded=b'T' + u32(len(spans)) + b''.join(struct.pack('<QI', *span) for span in spans)
        return b'U'+self._intern(pack(order))+encoded if reorder else encoded

    def _json_text(self,value):
        """Use a recipe only when it reproduces every original string character."""
        stripped=value.strip(' \t\r\n')
        if len(value)<512 or len(value)>16_000_000 or not stripped.startswith(('{','[')): return None
        try: parsed=json.loads(stripped)
        except (ValueError,RecursionError): return None
        prefix=value[:len(value)-len(value.lstrip(' \t\r\n'))]
        suffix=value[len(value.rstrip(' \t\r\n')):]
        for indent in (None,2,4):
            for compact in (True,False):
                for ascii_only in (True,False):
                    options={'ensure_ascii':ascii_only,'allow_nan':False,'indent':indent,
                             'separators':(',',':') if compact else (',',': ') if indent else (', ',': ')}
                    try: rebuilt=json.dumps(parsed,**options)
                    except (ValueError,TypeError,RecursionError): return None
                    if rebuilt==stripped:
                        recipe={'prefix':prefix,'suffix':suffix,'options':options}
                        return b'J'+pack(recipe)+self._encode(parsed)
        return None

    def _encode(self, value, key=None):
        if isinstance(value, dict):
            parts = []
            for k, v in value.items():
                special = key == 'telemetry_history' and k == 'samples' and isinstance(v, list)
                parts.append(pack(k) + (self._telemetry(v) if special else self._encode(v, k)))
            encoded = b'o' + u32(len(value)) + b''.join(parts)
        elif isinstance(value, (list,tuple)):
            encoded = b'l' + u32(len(value)) + b''.join(self._encode(v) for v in value)
        elif isinstance(value,str): encoded=self._json_text(value) or pack(value)
        else: encoded = pack(value)
        if len(encoded)>=INTERN_BYTES:
            family=pack(list(value)) if isinstance(value,dict) else b'list' if isinstance(value,(list,tuple)) else b'text'
            return self._intern(encoded,family)
        return encoded

    def _envelope(self,value):
        encoded=self._encode(value)
        if encoded[:1]==b'R': return encoded
        compressed=zlib.compress(encoded,3)
        return b'Z'+u32(len(compressed))+compressed

    def event(self, event):
        """Store exact supplied envelope. Identity, clocks, hashes and parents unchanged."""
        self._guard()
        value = self._envelope(event); self._guard(len(value) + 64)
        inserted=self.db.execute('INSERT INTO events(payload) VALUES(?)', (value,)).lastrowid
        self.sequence += 1
        # Each event durably commits its referenced objects; restart cannot leave dangling refs.
        self.db.commit(); self.last_durable_event=inserted; self._physical_guard()

    def _physical_guard(self):
        pages = self.db.execute('PRAGMA page_count').fetchone()[0]
        page_size = self.db.execute('PRAGMA page_size').fetchone()[0]
        if pages * page_size > min(MAX_CONTAINER_BYTES,self.core_limit + self.policy.image_quota_bytes + 262144):
            self.fail('Physical database quota exceeded')

    def motion(self, row):
        self._guard(); self.motion_rows.append(pack(row))
        if len(self.motion_rows) >= self.flush_rows: self.flush_motion()

    def flush_motion(self):
        if self.motion_rows:
            raw = b'l' + u32(len(self.motion_rows)) + b''.join(self.motion_rows)
            data = zlib.compress(raw, 3)
            self._guard(len(data) + 96)
            self.db.execute('INSERT INTO motion(hash,payload) VALUES(?,?)', (digest(raw),data))
            self.motion_rows.clear(); self.db.commit(); self._physical_guard()

    def document(self, name, value):
        data = self._envelope(value); self._guard(len(data) + len(name.encode('utf-8')) + 64)
        self.db.execute('INSERT INTO documents VALUES(?,?)', (name, data)); self.db.commit()
        self._physical_guard()

    def image(self, frame_id, capture_time_s, rgb, depth):
        """Observe encoded lossless pair independently of live delivery; bounded RAM only."""
        self._guard()
        if not math.isfinite(capture_time_s): raise ValueError('Nonfinite image time')
        rgb, depth = bytes(rgb), bytes(depth)
        if self.ring and capture_time_s < self.ring[-1][1]: raise ValueError('Capture time regressed')
        self.db.execute('INSERT INTO images(id,time,status,reason) VALUES(?,?,?,?)',
                        (frame_id, capture_time_s, 'unavailable_by_policy', 'ring_only_or_not_selected'))
        self._guard(160 + len(frame_id))
        item = (frame_id, capture_time_s, rgb, depth)
        self.ring.append(item); self.ring_size += len(rgb) + len(depth)
        while self.ring and (len(self.ring) > self.policy.ring_frames or self.ring_size > self.policy.ring_bytes or
                            capture_time_s - self.ring[0][1] > self.policy.pre_s):
            old = self.ring.popleft(); self.ring_size -= len(old[2]) + len(old[3])
        representative = self.representative and capture_time_s <= self.policy.representative_until_s
        period = self.policy.representative_period_s if representative else self.policy.sparse_period_s
        sparse = self.last_sparse is None or capture_time_s - self.last_sparse >= period - 1e-9
        if sparse:
            self.last_sparse = capture_time_s
            stored=self._persist(item, 'predeclared_representative' if representative else 'predeclared_sparse')
            if stored is False and representative and self.policy.require_complete_representative:
                self.fail('Required predeclared representative image pair exceeds quota')
        if capture_time_s <= self.trigger_end: self._persist(item, 'outcome_selected_post_window')
        self.db.commit(); self._physical_guard()

    def _persist(self, item, reason):
        ident, _, rgb, depth = item
        status = self.db.execute('SELECT status FROM images WHERE id=?', (ident,)).fetchone()[0]
        if status == 'available': return
        if self.image_bytes + len(rgb) + len(depth) > self.policy.image_quota_bytes:
            self.db.execute('UPDATE images SET reason=? WHERE id=?', ('image_quota_exhausted', ident))
            return False
        self.image_bytes += len(rgb) + len(depth)
        self.db.execute('UPDATE images SET status=?,reason=?,rgb=?,depth=?,rgb_sha=?,depth_sha=? WHERE id=?',
            ('available', reason, rgb, depth, hashlib.sha256(rgb).hexdigest(), hashlib.sha256(depth).hexdigest(), ident))
        return True

    def trigger(self, capture_time_s, event_id, reason):
        """Return whether declared ring covered the complete requested pre-window."""
        self._guard()
        admitted = self.triggers < self.policy.maximum_trigger_windows
        covered = bool(self.ring) and self.ring[0][1] <= capture_time_s - self.policy.pre_s + 1e-9
        if admitted:
            self.triggers += 1; self.trigger_end = max(self.trigger_end, capture_time_s + self.policy.post_s)
            for item in self.ring:
                if item[1] >= capture_time_s - self.policy.pre_s: self._persist(item, 'outcome_selected_pre_window')
        self.document('trigger-%06d' % self.sequence, {'event_id': event_id, 'reason': reason,
            'capture_time_s': capture_time_s, 'pre_s': self.policy.pre_s, 'post_s': self.policy.post_s,
            'admitted': admitted, 'pre_window_covered': covered,
            'interpretation': 'outcome-selected diagnostic imagery, not representative sampling'})
        self.sequence += 1
        return admitted and covered

    def close(self):
        if not self.stopped:
            self.flush_motion()
            self._physical_guard()
            self.db.execute("UPDATE meta SET value='complete' WHERE key='state'")
            self.db.commit()
        self.db.close()
        if not self.stopped:
            database=self.path/'evidence.sqlite'
            try:
                raw_bytes=database.stat().st_size; raw_sha=file_digest(database)
                partial=self.path/'evidence.sqlite.gz.partial'; packed=self.path/'evidence.sqlite.gz'
                with database.open('rb') as source,partial.open('xb') as target:
                    with gzip.GzipFile(fileobj=target,mode='wb',compresslevel=6,mtime=0,filename='') as compressor:
                        for block in iter(lambda:source.read(1024*1024),b''): compressor.write(block)
                if partial.stat().st_size>MAX_CONTAINER_BYTES+1_000_000: self.fail('Finalization temporary bound exceeded')
                checked=hashlib.sha256(); count=0
                with gzip.open(partial,'rb') as stream:
                    for block in iter(lambda:stream.read(1024*1024),b''):
                        count+=len(block); checked.update(block)
                        if count>MAX_CONTAINER_BYTES: self.fail('Finalized restore bound exceeded')
                if count!=raw_bytes or checked.hexdigest()!=raw_sha: self.fail('Finalization exact-byte verification failed')
                partial.replace(packed)
                manifest={'schema_version':VERSION,'storage':'sqlite-gzip-1','database':packed.name,
                    'bytes':packed.stat().st_size,'sha256':file_digest(packed),
                    'uncompressed_bytes':raw_bytes,'uncompressed_sha256':raw_sha,
                    'maximum_uncompressed_bytes':MAX_CONTAINER_BYTES,'state':'complete',
                    'scope':'Authenticates all envelope, motion, object, image and availability tables; exact original SQLite bytes'}
                # Only this writer's newly-created working file is discarded,
                # after independently verifying the complete canonical package.
                database.unlink()
                (self.path/'container-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
            except Exception as exc:
                if not self.stopped: self.fail('Finalization failure: '+type(exc).__name__)
                raise


class Reader:
    """Operator boundary: streams objects for analysis/diagnostics/continuity/packages."""
    def __init__(self, directory):
        self.path = Path(directory)
        manifest_path=self.path/'container-manifest.json'
        if not manifest_path.exists(): raise RecordingFailure('Missing complete container manifest')
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        version=manifest.get('schema_version'); expected_file='evidence.sqlite.gz' if version==VERSION else 'evidence.sqlite'
        database=self.path/expected_file
        if (version not in READABLE_VERSIONS or manifest.get('database')!=expected_file or
            database.stat().st_size!=manifest.get('bytes') or file_digest(database)!=manifest.get('sha256')):
            raise RecordingFailure('Container manifest byte/hash mismatch')
        if version==VERSION:
            expected=manifest.get('uncompressed_bytes')
            if (manifest.get('storage')!='sqlite-gzip-1' or type(expected) is not int or
                not 0<expected<=MAX_CONTAINER_BYTES): raise RecordingFailure('Unsupported or oversized finalized container')
            restored=bytearray(); checksum=hashlib.sha256()
            with gzip.open(database,'rb') as stream:
                for block in iter(lambda:stream.read(1024*1024),b''):
                    if len(restored)+len(block)>expected: raise RecordingFailure('Finalized container exceeds declared restore bound')
                    restored.extend(block); checksum.update(block)
            if len(restored)!=expected or checksum.hexdigest()!=manifest.get('uncompressed_sha256'):
                raise RecordingFailure('Restored exact database hash mismatch')
            self.db=sqlite3.connect(':memory:'); self.db.deserialize(restored); del restored
            self.db.execute('PRAGMA query_only=ON')
        else:
            self.db = sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)
        self.meta = dict(self.db.execute('SELECT key,value FROM meta'))
        if self.meta.get('version') not in READABLE_VERSIONS or self.meta['version']!=manifest['schema_version']:
            self.db.close(); raise RecordingFailure('Unsupported evidence format')
        if (self.path / 'RECORDING_FAILED.json').exists() or self.meta.get('state') != 'complete':
            self.db.close(); raise RecordingFailure('Incomplete/failed recording; cannot claim complete scientific evidence')
        self.cache = OrderedDict(); self.cache_bytes=0

    def _encoded_object(self, key):
        # Cache encoded bytes, never caller-mutable decoded objects.
        data = self.cache.get(key)
        if data is None:
            row = self.db.execute('SELECT payload FROM objects WHERE hash=?', (key,)).fetchone()
            if row is None: raise RecordingFailure('Missing object')
            if row[0][:1]==b'D':
                anchor=self._encoded_object(row[0][1:33])
                decompressor=zlib.decompressobj(zdict=anchor[-32768:])
                data=decompressor.decompress(row[0][33:])+decompressor.flush()
            else: data = zlib.decompress(row[0])
            if digest(data) != key: raise RecordingFailure('Object hash mismatch')
            if len(data)<=8_000_000:
                self.cache[key] = data; self.cache_bytes+=len(data)
                while len(self.cache)>4096 or self.cache_bytes>64_000_000:
                    _,evicted=self.cache.popitem(last=False); self.cache_bytes-=len(evicted)
        return data

    def _object(self,key): return self._decode(self._encoded_object(key))

    def _telemetry(self, start, length):
        rows = self.db.execute('SELECT id,hash,payload FROM telemetry WHERE id>=? AND id<? ORDER BY id', (start, start+length)).fetchall()
        if len(rows) != length: raise RecordingFailure('Missing exact telemetry range')
        for ident, key, data in rows:
            raw = zlib.decompress(data)
            decoded=unpack(raw,self._object,self._telemetry)
            if digest(pack(decoded)) != key: raise RecordingFailure('Telemetry hash mismatch')
            yield decoded

    def _decode(self, data): return unpack(data, self._object, self._telemetry)
    def events(self):
        for row in self.db.execute('SELECT payload FROM events ORDER BY id'): yield self._decode(row[0])
    def motion(self):
        for expected,data in self.db.execute('SELECT hash,payload FROM motion ORDER BY id'):
            raw=zlib.decompress(data)
            if digest(raw)!=expected: raise RecordingFailure('Motion chunk hash mismatch')
            yield from unpack(raw)
    def document(self, name):
        row = self.db.execute('SELECT payload FROM documents WHERE name=?', (name,)).fetchone()
        if row is None: raise KeyError(name)
        return self._decode(row[0])
    def images(self):
        names = ['id','capture_time_s','status','reason','rgb_sha256','depth_sha256']
        for row in self.db.execute('SELECT id,time,status,reason,rgb_sha,depth_sha FROM images ORDER BY time,id'):
            yield dict(zip(names, row))
    def image(self, ident):
        row = self.db.execute('SELECT status,reason,rgb,depth,rgb_sha,depth_sha FROM images WHERE id=?', (ident,)).fetchone()
        if row is None: raise KeyError('Unknown frame identity: ' + ident)
        status, reason, rgb, depth, rgb_sha, depth_sha = row
        if status != 'available': return {'status': status, 'reason': reason}
        if hashlib.sha256(rgb).hexdigest() != rgb_sha or hashlib.sha256(depth).hexdigest() != depth_sha:
            raise RecordingFailure('Available image corrupted')
        return {'status': status, 'reason': reason, 'rgb': rgb, 'depth': depth}
    def package(self, output, selected_frame_ids):
        """Bounded selected-trace bridge; absent-by-policy stays metadata, never corruption."""
        output = Path(output); output.mkdir(parents=True, exist_ok=False)
        availability = []
        for n, ident in enumerate(selected_frame_ids):
            value = self.image(ident); record = {'id': ident, 'status': value['status'], 'reason': value['reason']}
            if value['status'] == 'available':
                for mode, suffix in [('rgb','png'),('depth','npz')]:
                    name = f'{n:06d}.{suffix}'; (output/name).write_bytes(value[mode]); record[mode] = name
            availability.append(record)
        (output/'availability.json').write_text(json.dumps(availability, indent=2)+'\n', encoding='utf-8')
        return availability
    def require_images(self, frame_ids):
        """A fixed viewer/representative selection is a hard dependency, never substituted."""
        for ident in frame_ids:
            if self.image(ident)['status']!='available':
                raise RecordingFailure('Required selected image unavailable by policy: '+ident)
        return True
    def close(self): self.db.close()


class GatewayAdapter:
    """Future integration seam. Supplied clocks; return/deliver exact public input.

    Storage is operator-only. There is deliberately no method to select candidate
    input from protected events. No evaluator state is appended to public messages.
    """
    def __init__(self, recorder): self.recorder = recorder
    def record_public_and_send(self, event, message, send):
        if event.get('event_type') != 'candidate_input' or event.get('payload', {}).get('message') != message:
            raise ValueError('Event must bind the exact candidate message')
        self.recorder.event(event)
        return send(message)
    def record_event(self, event): self.recorder.event(event)
    def record_motion(self, row): self.recorder.motion(row)
    def persist_live_pair(self, frame_id, acquisition_time_s, rgb_bytes, depth_bytes):
        self.recorder.image(frame_id, acquisition_time_s, rgb_bytes, depth_bytes)
