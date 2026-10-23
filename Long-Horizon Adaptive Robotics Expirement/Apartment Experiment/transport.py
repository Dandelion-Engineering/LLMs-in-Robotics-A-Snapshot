"""Prospective bounded upload backpressure for large native sensor messages.

The inherited transport fails closed if an eager upload fills its memory budget.
Wait before reading, with the same ceiling and untouched authenticated/drain gates.
No application payload is inspected, rewritten, replayed or retained here.
"""
import asyncio
import hashlib
import json
from pathlib import Path
import codehost_bridge_v3 as inherited
import codehost_mux_protocol as mux
from frame_digest import Frames,projection
from flow_control import FrameReader
from h2_runtime import install as install_h2
from h2_readback import paired
install_h2()

class Ledger(inherited.Ledger):
    """Retain lifecycle events, with ordered constant-space frame commitments."""
    def __init__(self,fixture):
        super().__init__(fixture);self.frames=Frames();self.summarized=False;self.integrity_error=None;self.on_failure=None
    def emit(self,kind,**fields):
        with self.lock:
            if kind=='frame':
                if self.summarized:raise ValueError('Frame after terminal commitment')
                self.frames.add(fields['direction'],fields);return None
            if kind in ('namespace_output_closed','closed') and not self.summarized and self.integrity_error is None:
                for direction in ('incoming','outgoing'):
                    self.emit('frame_summary',direction=direction,summary=self.frames.summary(direction))
                self.summarized=True
            if self.integrity_error is None:
                try:return super().emit(kind,**fields)
                except Exception as error:
                    self.integrity_error=repr(error);self.fixture.abort_event.set()
                    if self.on_failure:self.on_failure()
                    try:
                        with (Path(self.fixture.evidence)/'metadata-failure.json').open('x') as f:
                            json.dump(dict(passed=False,error=self.integrity_error,last_durable_sequence=len(self.events),last_durable_sha256=self.previous),f)
                    except Exception:pass
            # Teardown needs to run even if its evidence medium failed. This
            # explicit non-durable marker can never pass the qualification gate.
            return dict(kind=kind,**fields,sequence=None,record_sha256=None,evidence_unavailable=True)

# Only this apartment adapter loads these replacements. Frozen campaign files
# stay byte-identical. Queue ceilings, H2 witnesses and native exit gates remain.
inherited.Ledger=Ledger
inherited.frame_projection=projection

class Bridge(inherited.Bridge):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.ledger.on_failure=lambda:self.failures.append('metadata_recording_failed')
    async def receive_frames(self):
        original=self.process.stdout
        reader=FrameReader(original,self.budget,lambda:bool(self.failures))
        self.process.stdout=reader
        try:
            result=await super().receive_frames()
            for channel in self.channels.values():
                try:proof=paired(channel.h2.summary(),channel.namespace_closed['h2'])
                except Exception:
                    self.fail('h2_endpoint_reconciliation_failed');raise
                self.ledger.emit('h2_endpoint_readback',channel_id=channel.id,proof=proof)
            return result
        except BaseException as error:
            if not isinstance(error,asyncio.CancelledError):
                self.ledger.emit('receive_failure_detail',error_type=type(error).__name__,message=str(error)[:500])
            raise
        finally:
            reader.release();self.process.stdout=original
    def fail(self,reason):
        # Resource exhaustion must never skip native retirement by throwing
        # recursively while recording an already-failed transport.
        self.fixture.abort_event.set()
        with self.failure_lock:
            if reason not in self.failures:
                self.failures.append(reason)
                try:self.ledger.emit('failure',reason=reason)
                except BaseException as error:
                    self.failures.append('failure_record_'+type(error).__name__)
    async def upload(self,channel):
        reserved=0
        try:
            while True:
                # Leave at least two frames for the concurrent download side.
                while (self.budget.channels.get(channel.id,0)+mux.MAX_FRAME_BYTES>
                       mux.PER_CHANNEL_QUEUE_BYTES-self.budget.headroom_bytes-2*mux.MAX_FRAME_BYTES
                       or self.budget.total+mux.MAX_FRAME_BYTES>mux.AGGREGATE_QUEUE_BYTES-self.budget.headroom_bytes):
                    if self.failures or self.sealed:raise RuntimeError('Transport closed during backpressure')
                    await asyncio.sleep(.001)
                self.budget.reserve(channel.id,mux.MAX_FRAME_BYTES);reserved=mux.MAX_FRAME_BYTES
                channel.upload_read_pending=True
                try:data=await channel.reader.read(mux.MAX_FRAME_BYTES)
                except OSError as error:
                    self.record_socket_failure(channel,'upload_read',error);raise
                finally:channel.upload_read_pending=False
                self.budget.release(channel.id,reserved-len(data));reserved=len(data)
                if not data:break
                if self.fixture.client_finishing.is_set():self.begin_finish()
                channel.meters['client_read'].add(data)
                inherited.require(not self.sealed,'client_data_after_owner_seal')
                self.feed_h2(channel,'upload',data)
                self.enqueue(mux.DATA,channel.id,data,reserved=True);reserved=0
        finally:
            if reserved:self.budget.release(channel.id,reserved)
        self.observe_finishing()
        channel.parent_eof=self.ledger.emit('client_eof',channel_id=channel.id,
            client_finishing=self.fixture.client_finishing.is_set(),h2=channel.h2.summary())
        self.enqueue(mux.HALF_CLOSE,channel.id)
        if not self.fixture.client_finishing.is_set():channel.h2.idle_eof()

async def run(fixture,callback):
    return await Bridge(fixture).run(callback)
