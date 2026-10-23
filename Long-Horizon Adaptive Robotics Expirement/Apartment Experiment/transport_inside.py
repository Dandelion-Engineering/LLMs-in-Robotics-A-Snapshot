"""Apartment transport metadata adapter; original channel and drain protocol."""
from pathlib import Path
import sys
import asyncio
sys.path.insert(0,str(Path(__file__).resolve().parent))
import inherited_inside as inherited
from frame_digest import Frames
from flow_control import room
import codehost_mux_protocol as mux
from h2_runtime import install
install()

class Metadata(inherited.Metadata):
    def __init__(self,stream):
        super().__init__(stream);self.frames=Frames()
    def emit(self,kind,**fields):
        if kind=='frame':
            self.frames.add(fields['direction'],fields);return None
        if kind=='closed':
            for direction in ('incoming','outgoing'):
                super().emit('frame_summary',direction=direction,summary=self.frames.summary(direction))
        return super().emit(kind,**fields)

inherited.Metadata=Metadata

class Relay(inherited.Relay):
    async def accept(self,kind,channel,payload):
        if kind==mux.DATA:
            await self.bounded(room(self.budget,channel,len(payload),lambda:bool(self.failure),2*mux.MAX_FRAME_BYTES))
        return await super().accept(kind,channel,payload)
    async def download(self,channel):
        reserved=0
        try:
            while True:
                await self.bounded(room(self.budget,channel.id,mux.MAX_FRAME_BYTES,lambda:bool(self.failure)))
                self.budget.reserve(channel.id,mux.MAX_FRAME_BYTES);reserved=mux.MAX_FRAME_BYTES
                data=await channel.reader.read(mux.MAX_FRAME_BYTES)
                self.budget.release(channel.id,reserved-len(data));reserved=len(data)
                if not data:break
                channel.h2.feed('download',data)
                await self.send(mux.DATA,channel.id,data)
                channel.download.add(data)
                self.budget.release(channel.id,reserved);reserved=0
            channel.download_eof=True;channel.download_eof_event.set()
            channel.download_eof_h2=channel.h2.summary()
            self.emit('channel_eof',channel_id=channel.id,direction='download',owner_finishing=self.draining,h2=channel.download_eof_h2)
            if not self.draining:
                channel.h2.idle_eof()
                await self.bounded(channel.upload_eof_event.wait());await self.bounded(channel.queue.join())
                if not self.draining:await self.close_channel(channel,'clean_idle_eof')
        except asyncio.CancelledError:raise
        except BaseException as error:
            channel.failure=type(error).__name__;self.fail(error)
        finally:
            if reserved:self.budget.release(channel.id,reserved)

inherited.Relay=Relay
if __name__=='__main__':raise SystemExit(inherited.main())
