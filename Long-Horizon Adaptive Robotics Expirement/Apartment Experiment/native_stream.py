"""Bounded native-client memory with a separate finite D: recording budget.

Original public-event filtering, capability redaction and native control remain.
Only terminal notifications need to stay in RAM after durable event logging.
"""
from collections import deque
import os
import queue
import threading
import time
from common import save

LINE_LIMIT=32*1024**2
QUEUE_BYTES=8*1024**2
QUEUE_ITEMS=256
STREAM_LIMIT=256*1024**2
EVENT_LIMIT=512*1024**2
CLEANUP_RESERVE=4*1024**2

class ByteQueue:
    def __init__(self):
        self.rows=deque();self.condition=threading.Condition();self.bytes=0;self.peak_bytes=0;self.peak_items=0;self.closed=False
    def put(self,item):
        size=len(item[1]) if item[1] is not None else 0
        if size>LINE_LIMIT:raise ValueError('Native message size bound')
        with self.condition:
            # One individually bounded large line may occupy an empty queue.
            while not self.closed and (len(self.rows)>=QUEUE_ITEMS or (self.rows and self.bytes+size>QUEUE_BYTES)):
                self.condition.wait()
            if self.closed:return
            self.rows.append(item);self.bytes+=size
            self.peak_bytes=max(self.peak_bytes,self.bytes);self.peak_items=max(self.peak_items,len(self.rows));self.condition.notify_all()
    def get(self,timeout=None):
        deadline=None if timeout is None else time.monotonic()+timeout
        with self.condition:
            while not self.rows:
                remaining=None if deadline is None else deadline-time.monotonic()
                if self.closed or (remaining is not None and remaining<=0):raise queue.Empty
                self.condition.wait(remaining)
            item=self.rows.popleft();self.bytes-=len(item[1]) if item[1] is not None else 0
            self.condition.notify_all();return item
    def close(self):
        with self.condition:self.closed=True;self.condition.notify_all()

class TerminalEvents(list):
    def __init__(self):super().__init__();self.seen=0;self.peak=0
    def append(self,event):
        self.seen+=1
        if event.get('method')=='turn/completed':
            if len(self)>=4:raise ValueError('Native terminal notification bound')
            super().append(event);self.peak=max(self.peak,len(self))

class EventStream:
    def __init__(self,stream):self.stream=stream;self.bytes=0;self.lock=threading.Lock()
    def __getattr__(self,name):return getattr(self.stream,name)
    def write(self,value):
        size=len(value.encode('utf-8'))+(value.count('\n') if os.name=='nt' else 0)
        with self.lock:
            if self.bytes+size>EVENT_LIMIT:raise RuntimeError('Native retained-event storage bound')
            count=self.stream.write(value)
            if count!=len(value):raise OSError('Short native event write')
            self.bytes+=size;return count

def install(module):
    inherited=module.Client
    class Client(inherited):
        def __init__(self,*args,**kwargs):
            self.stream_ready=threading.Event();self.stream_stop=threading.Event();self.readers=[];self.reader_errors=[]
            super().__init__(*args,**kwargs)
            self.messages=ByteQueue();self.pending_events=TerminalEvents();self.events=EventStream(self.events)
            self.stream_ready.set()
        def _drain(self,label,stream):
            self.readers.append(threading.current_thread());self.stream_ready.wait()
            try:
                while not self.stream_stop.is_set():
                    data=stream.readline(LINE_LIMIT+1)
                    if not data:self.messages.put((label,None));return
                    if len(data)>LINE_LIMIT:raise ValueError('Native message size bound')
                    self.messages.put((label,data))
            except Exception as error:
                if not self.stream_stop.is_set():
                    self.reader_errors.append(dict(stream=label,error=repr(error)))
                    abort=getattr(self.args,'abort_event',None)
                    if abort is not None:abort.set()
                    self.messages.put((label,None))
        def close(self):
            selected=getattr(self.args,'native_process_drain',False)
            module.require(type(selected) is bool,'Native process-drain selection must be boolean')
            if selected:
                from native_process_quiescence import close
            else:
                from native_quiescence import close
            # Recording exhaustion stays an invocation failure, but must not
            # prevent the ordinary control handshake from being consumed.
            budget=self.bytes_seen+CLEANUP_RESERVE
            result=None
            try:
                result=close(self,budget)
                return result
            finally:
                self.stream_stop.set();self.messages.close()
                for thread in self.readers:thread.join(1)
                healthy=not self.reader_errors and all(not t.is_alive() for t in self.readers)
                receipt=dict(passed=healthy,raw_consumed_bytes=self.bytes_seen,raw_stream_limit=STREAM_LIMIT,
                    per_message_limit=LINE_LIMIT,queue_byte_limit=QUEUE_BYTES,queue_item_limit=QUEUE_ITEMS,
                    queue_peak_bytes=self.messages.peak_bytes,queue_peak_items=self.messages.peak_items,
                    large_single_message_exception=True,notifications_seen=self.pending_events.seen,
                    pending_terminal_peak=self.pending_events.peak,retained_event_bytes=self.events.bytes,
                    retained_event_limit=EVENT_LIMIT,cleanup_extra_bytes=CLEANUP_RESERVE,cleanup_budget=budget,
                    reader_errors=self.reader_errors,readers_retired=all(not t.is_alive() for t in self.readers))
                save(self.args.evidence/'native-stream.json',receipt)
                if result is not None and not healthy:
                    result['qualified']=False;result['failures'].append('native_stream_retirement_failed')
    module.MAX_BYTES=STREAM_LIMIT
    module.Client=Client
    return Client
