"""Wait for bounded queue capacity; never enlarge opaque transport buffers."""
import asyncio
import codehost_mux_protocol as mux

async def room(budget,channel,count,failed,margin=0):
    while (budget.channels.get(channel,0)+count+margin>
           mux.PER_CHANNEL_QUEUE_BYTES-budget.headroom_bytes or
           budget.total+count+margin>mux.AGGREGATE_QUEUE_BYTES-budget.headroom_bytes):
        if failed():raise RuntimeError('Transport failed while waiting for queue capacity')
        await asyncio.sleep(.001)

class FrameReader:
    """Reserve DATA payload capacity before consuming its pipe bytes.

    The reservation is handed synchronously back to the existing receive loop,
    which immediately charges the delivered DATA bytes. Header bytes remain
    covered by its unchanged fixed framing headroom.
    """
    def __init__(self,reader,budget,failed):
        self.reader=reader;self.budget=budget;self.failed=failed;self.pending=None;self.reserved=0
    def __getattr__(self,name):return getattr(self.reader,name)
    def release(self):
        if self.reserved:self.budget.release(self.pending[1],self.reserved);self.reserved=0
    async def readexactly(self,count):
        if self.pending is None:
            if count!=mux.HEADER.size:raise ValueError('Expected framing header')
            raw=await self.reader.readexactly(count)
            magic,version,kind,channel,length=mux.HEADER.unpack(raw)
            if magic!=mux.MAGIC or version!=mux.VERSION:raise ValueError('Frame magic/version differs')
            mux.validate(kind,channel,length);self.pending=(kind,channel,length)
            return raw
        kind,channel,length=self.pending
        if count!=length:raise ValueError('Frame payload size changed')
        try:
            if kind==mux.DATA:
                await room(self.budget,channel,length,self.failed)
                self.budget.reserve(channel,length);self.reserved=length
            return await self.reader.readexactly(count)
        finally:
            self.release();self.pending=None
