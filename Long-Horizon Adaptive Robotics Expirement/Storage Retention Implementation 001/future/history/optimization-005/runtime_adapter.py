"""Concrete future-runtime wiring. Import into a NEW release, never monkeypatch r4.

Replace the Evidence constructor with FutureEvidence; existing .emit and
.motion.write call sites work. After SensorWorker.poll() obtains live immutable
arrays, call LiveSensorBridge.observe(result) with raw artifact paths disabled
at SensorWorker.request(rgb_path=None, depth_path=None). Deliver its unchanged
result through the existing live gateway. Persisted references remain operator
metadata; live pixel transport must use arrays/transient IPC, not archived paths.
"""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import struct
import threading
import time
import zlib
from dataclasses import replace

from recorder import Recorder, ImagePolicy, canonical, RecordingFailure


class MotionSink:
    def __init__(self, recorder, lock): self.recorder=recorder; self.lock=lock
    def write(self, value):
        # Frozen call sites write one complete JSON line per sample; no partial
        # line buffering can grow without bound or mix concurrent samples.
        if not isinstance(value,str) or not value.endswith('\n') or value.count('\n')!=1:
            raise RecordingFailure('MotionSink requires one complete row')
        with self.lock: self.recorder.motion(json.loads(value))
        return len(value)
    def flush(self):
        with self.lock: self.recorder.flush_motion()


class FutureEvidence:
    def __init__(self,directory,run_id,*,policy=ImagePolicy(),core_quota_bytes=200_000_000,
                 representative=False,clock=time.perf_counter,physics_dt=.002,allocation=None):
        if allocation is not None:
            if allocation['run_id']!=run_id: raise ValueError('Campaign allocation identifies another run')
            core_quota_bytes=allocation['core_quota_bytes']
            policy=replace(policy,image_quota_bytes=allocation['image_quota_bytes'],
                           maximum_trigger_windows=allocation['maximum_trigger_windows'])
        self.store=Recorder(directory,run_id=run_id,policy=policy,core_quota_bytes=core_quota_bytes,
                            representative=representative)
        self.path=Path(directory); self.run_id=run_id; self.clock=clock; self.start=clock()
        self.physics_dt=physics_dt; self.sequence=0; self.lock=threading.RLock()
        self.motion=MotionSink(self.store,self.lock)
    def emit(self,kind,payload,sim_time,source='supervisor',parents=None):
        with self.lock:
            self.sequence+=1
            event={'schema_version':'robot-evidence-1.0','run_id':self.run_id,'event_id':self.sequence,
                'event_type':kind,'source':source,'sim_time_s':sim_time,'sim_tick':round(sim_time/self.physics_dt),
                'wall_elapsed_s':self.clock()-self.start,'parent_ids':parents or [],
                'payload_sha256':hashlib.sha256(canonical(payload)).hexdigest(),'payload':payload}
            self.store.event(event); return self.sequence
    def document(self,name,value):
        with self.lock: self.store.document(name,value)
    def trigger(self,sim_time,event_id,reason):
        with self.lock: return self.store.trigger(sim_time,event_id,reason)
    def close(self):
        with self.lock: self.store.close()


class LiveSensorBridge:
    """Exact original SensorResult remains available to the live consumer."""
    def __init__(self,evidence): self.evidence=evidence
    def observe(self,result):
        import numpy as np
        rgb=result.rgb; depth=result.depth
        if rgb.dtype!=np.uint8 or rgb.ndim!=3 or rgb.shape[2]!=3: raise ValueError('Expected uint8 RGB')
        def chunk(tag,value):
            return struct.pack('!I',len(value))+tag+value+struct.pack('!I',zlib.crc32(tag+value))
        raw=b''.join(b'\0'+row.tobytes() for row in rgb)
        png=(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',rgb.shape[1],rgb.shape[0],8,2,0,0,0))
             +chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))
        stream=io.BytesIO(); np.savez_compressed(stream,depth_m=depth)
        ident=f'{result.camera}:{result.sequence}'
        with self.evidence.lock:
            self.evidence.store.image(ident,result.capture_sim_time_s,png,stream.getvalue())
        return result
