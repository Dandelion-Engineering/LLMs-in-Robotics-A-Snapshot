"""Reproduce the receive bound and prove byte-exact bounded backpressure."""
import argparse
import asyncio
import hashlib
from pathlib import Path
import traceback
from common import save,canonical

async def exercise():
    import native_runtime,transport
    import codehost_mux_protocol as mux
    from flow_control import FrameReader,room
    budget=mux.QueueBudget(headroom_bytes=transport.inherited.FRAME_HEADROOM_BYTES)
    full=mux.PER_CHANNEL_QUEUE_BYTES-budget.headroom_bytes
    budget.reserve(1,full);reproduced=False
    try:budget.reserve(1,mux.MAX_FRAME_BYTES)
    except ValueError as error:reproduced=str(error)=='Channel queue bound'
    assert reproduced
    source=asyncio.StreamReader(limit=32768);payload=b'x'*mux.MAX_FRAME_BYTES
    source.feed_data(mux.encode_frame(mux.DATA,1,payload));source.feed_eof()
    wrapped=FrameReader(source,budget,lambda:False)
    pending=asyncio.create_task(mux.read_frame(wrapped));await asyncio.sleep(.03)
    assert not pending.done() and wrapped.reserved==0
    budget.release(1,mux.MAX_FRAME_BYTES)
    kind,channel,actual=await asyncio.wait_for(pending,2)
    assert (kind,channel,actual)==(mux.DATA,1,payload)
    budget.reserve(channel,len(actual));assert budget.total==full
    budget.release(1,full);assert budget.total==0
    # Reserve-before-read cancellation must release exactly its own bytes.
    source=asyncio.StreamReader();source.feed_data(mux.HEADER.pack(mux.MAGIC,mux.VERSION,mux.DATA,1,65536))
    wrapped=FrameReader(source,budget,lambda:False);pending=asyncio.create_task(mux.read_frame(wrapped))
    await asyncio.sleep(.01);assert wrapped.reserved==65536
    pending.cancel();await asyncio.gather(pending,return_exceptions=True);assert budget.total==0
    # Actual TCP stream and a deliberately slow consumer, not only a budget mock.
    sent=hashlib.sha256();received=hashlib.sha256();chunks=256;finished=asyncio.Event();producer_errors=[]
    async def produce(reader,writer):
        try:
            for i in range(chunks):
                data=hashlib.sha256(str(i).encode()).digest()*2048
                sent.update(data);writer.write(mux.encode_frame(mux.DATA,1,data));await writer.drain()
            writer.write(mux.encode_frame(mux.FINISH,0));await writer.drain()
        except BaseException as error:producer_errors.append(repr(error))
        finally:writer.close();await writer.wait_closed();finished.set()
    server=await asyncio.start_server(produce,'127.0.0.1',0,limit=32768)
    reader,writer=await asyncio.open_connection('127.0.0.1',server.sockets[0].getsockname()[1],limit=32768)
    wrapped=FrameReader(reader,budget,lambda:False);queue=asyncio.Queue();count=0
    async def consume():
        while True:
            data=await queue.get()
            if data is None:queue.task_done();return
            await asyncio.sleep(.002);received.update(data);budget.release(1,len(data));queue.task_done()
    consumer=asyncio.create_task(consume())
    while frame:=await mux.read_frame(wrapped):
        kind,channel,data=frame
        if kind==mux.FINISH:break
        assert kind==mux.DATA and channel==1
        budget.reserve(channel,len(data));queue.put_nowait(data);count+=1
    queue.put_nowait(None);await consumer;await finished.wait()
    writer.close();await writer.wait_closed();server.close();await server.wait_closed()
    assert count==chunks and sent.hexdigest()==received.hexdigest() and budget.total==0 and not producer_errors
    assert budget.maximum+budget.headroom_bytes<=mux.PER_CHANNEL_QUEUE_BYTES
    return dict(passed=True,legacy_bound_reproduced=True,paused_until_capacity=True,cancellation_released=True,
                actual_socket_frames=count,actual_socket_bytes=count*65536,sha256=received.hexdigest(),
                queue_peak=budget.maximum,unchanged_headroom=budget.headroom_bytes,unchanged_limit=mux.PER_CHANNEL_QUEUE_BYTES)

def run(out):
    out.mkdir(parents=True,exist_ok=False)
    result=dict(passed=False,stage='throwaway-flow-control',official_sessions=0,model_calls=0,checks={})
    try:
        result['flow']=asyncio.run(exercise());result['checks']['bounded_byte_exact_socket_flow']=result['flow']['passed']
        import integration_engineering
        result['checks']['both_native_preflights']=integration_engineering.run(out/'preflight')
        result['passed']=all(result['checks'].values())
    except BaseException as e:result.update(error=repr(e),traceback=traceback.format_exc())
    save(out/'result.json',result);print(canonical(result).decode());return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.output) else 1)
