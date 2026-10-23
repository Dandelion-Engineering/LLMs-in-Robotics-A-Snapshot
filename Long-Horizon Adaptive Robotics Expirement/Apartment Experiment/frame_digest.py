"""Constant-space ordered commitments to every opaque transport frame."""
import hashlib
import json

FIELDS=('frame_type','channel_id','payload_bytes','payload_sha256')

class Frames:
    def __init__(self):
        self.hashes={d:hashlib.sha256() for d in ('incoming','outgoing')}
        self.counts={d:0 for d in self.hashes};self.bytes={d:0 for d in self.hashes}
    def add(self, direction, fields):
        row={k:fields[k] for k in FIELDS}
        raw=json.dumps(row,sort_keys=True,separators=(',',':')).encode()+b'\n'
        self.hashes[direction].update(raw);self.counts[direction]+=1;self.bytes[direction]+=row['payload_bytes']
    def summary(self,direction):
        return dict(format='apartment-ordered-frames-1',frames=self.counts[direction],
                    payload_bytes=self.bytes[direction],sha256=self.hashes[direction].hexdigest())

def projection(events,direction):
    rows=[r['summary'] for r in events if r.get('kind')=='frame_summary' and r['direction']==direction]
    if len(rows)!=1:raise ValueError('Missing or duplicate terminal frame commitment')
    return rows[0]
