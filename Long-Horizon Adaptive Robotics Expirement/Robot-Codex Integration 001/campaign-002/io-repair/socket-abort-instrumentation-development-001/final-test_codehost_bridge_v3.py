"""Deterministic in-memory bridge/namespace tests; no native, OS query or model."""
import asyncio
import hashlib
import io
import json
import os
import time
from pathlib import Path
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest import mock

import codehost_bridge_v3 as bridge
import codehost_inside_v3 as inside
import codehost_mux_protocol as m
from codehost_owner import OwnerError


def h2(kind, flags=0, stream=0, payload=b''):
    return len(payload).to_bytes(3,'big') + bytes([kind,flags]) + stream.to_bytes(4,'big') + payload


def cleanup_seed():
    start=time.monotonic()
    wire=(json.dumps({'id':7,'method':'turn/interrupt','params':{'threadId':'thread-test','turnId':'turn-test'}})+'\n').encode()
    return {'schema':'campaign002-native-cleanup-request-1','nonce':'b'*32,
            'thread_id':'thread-test','turn_id':'turn-test','start_monotonic_s':start,
            'graceful_deadline_monotonic_s':start+5,
            'control_event':{'kind':'native_quiescence','schema':'campaign002-native-quiescence-event-1',
                'sequence':2,'phase':'request','wall_unix_s':time.time(),'monotonic_s':start,
                'method':'turn/interrupt','request_id':7,'thread_id':'thread-test','turn_id':'turn-test',
                'wire_bytes':len(wire),'wire_sha256':hashlib.sha256(wire).hexdigest()}}


class Pipe:
    def __init__(self, reader): self.reader=reader; self.closed=False
    def write(self, data):
        if self.closed: raise BrokenPipeError('closed pipe')
        self.reader.feed_data(data)
    async def drain(self): await asyncio.sleep(0)
    def close(self):
        if not self.closed: self.closed=True; self.reader.feed_eof()
    async def wait_closed(self): pass


class NativeSocket:
    def __init__(self, reader, port, *, eof_after_response=False):
        self.reader=reader; self.port=port; self.eof_after_response=eof_after_response
        self.data=bytearray(); self.closed=False; self.received=asyncio.Event()
    def get_extra_info(self, name): return ('127.0.0.1',self.port if name=='peername' else 32100)
    def write(self, data):
        self.data.extend(data); self.received.set()
        if self.eof_after_response: self.reader.feed_eof(); self.eof_after_response=False
    async def drain(self): await asyncio.sleep(0)
    def close(self): self.closed=True
    async def wait_closed(self): pass


class FakeOwner:
    def __init__(self): self.owner=None; self.calls=[]; self.reject=None; self.gate=None
    def register(self, process, binary):
        if self.owner is not None: raise ValueError('already registered')
        self.owner={'schema':'campaign002-native-owner-1','pid':123,'process_creation_filetime':456,
                    'owner_kind':'model_client','executable':{'path':'fake-native','sha256':'a'*64}}
        return dict(self.owner)
    def authenticate(self, client, server):
        self.calls.append((client,server,threading.get_ident()))
        if self.gate: self.gate.wait(1)
        if self.reject: raise OwnerError(self.reject)
        if self.owner is None: raise ValueError('unregistered')
        return {'schema':'campaign002-channel-owner-1','owner_pid':123,'client':list(client),'server':list(server)}


class SharedHost:
    """Actual Linux Relay and framing in memory, with opaque fake H2 service."""
    def __init__(self, *, respond=True, corrupt=False, terminal_change=None, reply=None, defer_download_eof=False):
        self.stdout=asyncio.StreamReader(); self.stderr=asyncio.StreamReader()
        self.input=asyncio.StreamReader(); self.stdin=Pipe(self.input); self.returncode=None
        self.metadata_stream=io.StringIO(); self.metadata=inside.Metadata(self.metadata_stream)
        self.child=SimpleNamespace(pid=789,poll=lambda:None)
        self.reply=reply;self.defer_download_eof=defer_download_eof
        self.hosts=[]; self.respond=respond; self.corrupt=corrupt; self.terminal_change=terminal_change or {}
        self.relay=inside.Relay(self.input,Pipe(self.stdout),self.metadata.emit,self.child,threading.Event(),self.connect)
        self.task=asyncio.create_task(self.operate())
    async def connect(self):
        reader=asyncio.StreamReader(); host=self
        class Socket:
            def __init__(self): self.data=bytearray(); self.sent=False; self.closed=False
            def write(self,data):
                self.data.extend(data)
                if host.respond and not self.sent:
                    # Each test sends one complete preface/settings/request chunk.
                    self.sent=True
                    reply=host.reply if host.reply is not None else h2(4)+h2(1,5,1,b'\x88')
                    if host.corrupt: reply=reply[:-1]
                    reader.feed_data(reply)
            async def drain(self): await asyncio.sleep(0)
            def write_eof(self):
                if not host.defer_download_eof:reader.feed_eof()
            def close(self): self.closed=True
            async def wait_closed(self): pass
        writer=Socket(); self.hosts.append((reader,writer)); return reader,writer
    async def operate(self):
        self.metadata.emit('open',sources={})
        self.metadata.emit('child_started',child_pid=self.child.pid)
        ready={'schema':'campaign002-codehost-owner-ready-3','child_pid':self.child.pid,
               'max_connections':16,'max_frame_bytes':65536,'per_channel_queue_bytes':1048576,
               'aggregate_queue_bytes':4194304,'sources':{}}
        self.metadata.emit('ready',receipt=ready)
        await self.relay.send(m.READY,0,m.canonical(ready))
        result=await self.relay.run(); error=result.pop('error_type')
        for stream in ('stdout','stderr'):
            self.metadata.emit('child_diagnostic',stream=stream,bytes=0,sha256=hashlib.sha256(b'').hexdigest(),truncated=False)
        fields=dict(qualified=error is None,reason='owner_finish' if error is None else 'error',
            child_pid=self.child.pid,child_exit_before_cleanup=None,child_exit_code=-15,terminate_sent=True,
            kill_sent=False,diagnostic_streams_complete=True,error_type=error,sources={},**result)
        fields.update(self.terminal_change)
        final=self.metadata.emit('closed',**fields)
        await self.relay.send(m.FINISHED,0,m.canonical(final),account=False)
        self.stdout.feed_eof()
        self.stderr.feed_data(self.metadata_stream.getvalue().encode()); self.stderr.feed_eof()


class EarlyFailureHost:
    """Startup EOF before READY, with independently available diagnostic bytes."""
    def __init__(self, raw=b'', stderr_reader=None):
        self.stdout=asyncio.StreamReader();self.stdout.feed_eof()
        self.stderr=stderr_reader or asyncio.StreamReader()
        if stderr_reader is None:self.stderr.feed_data(raw);self.stderr.feed_eof()
        self.input=asyncio.StreamReader();self.stdin=Pipe(self.input);self.returncode=None
        self.task=asyncio.create_task(asyncio.sleep(0))


class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.fixture=SimpleNamespace(evidence=self.folder,run='/fake/run',abort_event=threading.Event(),
            client_finishing=threading.Event(),redact=lambda v:v,argv=lambda mode:['fake-entry',mode])
        self.client_readers=[]
        self.owner=FakeOwner(); self.launches=[]; self.retirements=[]; self.process=None
        self.retirement_qualified=True; self.wrapper_exit=0
        self.host_options={}
        self.host_factory=SharedHost
        async def launch(*args,**kwargs):
            self.launches.append((args,kwargs)); self.process=self.host_factory(**self.host_options); return self.process
        async def retire(process,identity,path):
            self.retirements.append(identity)
            await asyncio.wait_for(process.task,2); process.returncode=self.wrapper_exit
            path.write_text(json.dumps({'qualified':self.retirement_qualified}))
        self.bridge=bridge.Bridge(self.fixture,owner=self.owner,launcher=launch,retirer=retire,sources={})
        class Server:
            sockets=[SimpleNamespace(getsockname=lambda:('127.0.0.1',32100))]
            def close(self): pass
            async def wait_closed(self): pass
        self.enterContext(mock.patch.object(bridge,'create_server',new=mock.AsyncMock(return_value=Server())))
    def mark_finish(self, *, close_uploads=True):
        if not self.fixture.client_finishing.is_set():
            path=self.folder/'client/events.jsonl';path.parent.mkdir(exist_ok=True)
            with path.open('x',encoding='utf-8') as f:
                f.write(json.dumps({'kind':'client_finishing_before_close','schema':'campaign002-client-finishing-1',
                    'wall_unix_s':time.time(),'monotonic_s':time.monotonic()})+'\n');f.flush();os.fsync(f.fileno())
            self.fixture.client_finishing.set()
        if close_uploads:
            for reader in self.client_readers:
                if not reader.at_eof():reader.feed_eof()

    async def run_bridge(self, body, *, register=True, fail=False):
        async def callback(url):
            self.assertEqual(url,'http://127.0.0.1:32100')
            if register: self.fixture.native_process_ready(object(),'fake-native')
            try: await body()
            finally: self.mark_finish()
            return 'callback-result'
        if fail:
            with self.assertRaises(RuntimeError): await asyncio.wait_for(self.bridge.run(callback),5)
        else:
            self.assertEqual(await asyncio.wait_for(self.bridge.run(callback),5),'callback-result')
        self.assertEqual(len(self.launches),1); self.assertEqual(len(self.retirements),1)
        return json.loads((self.folder/'codehost-owner-bridge-v3.json').read_text())
    def client(self, index=1, *, natural=False, payload=b'\x82'):
        reader=asyncio.StreamReader();self.client_readers.append(reader); reader.feed_data(m.PREFACE+h2(4)+h2(1,5,1,payload))
        writer=NativeSocket(reader,40000+index,eof_after_response=natural)
        task=asyncio.create_task(self.bridge.handle(reader,writer))
        return reader,writer,task
    async def test_two_concurrent_channels_one_host_opaque_order_and_receipts(self):
        clients=[]
        async def body():
            clients.extend([self.client(1,natural=True,payload=b'one'),self.client(2,natural=True,payload=b'two')])
            await asyncio.gather(*(c[2] for c in clients))
        receipt=await self.run_bridge(body)
        self.assertTrue(receipt['qualified']); self.assertEqual(receipt['accepted'],2)
        self.assertEqual(len(self.process.hosts),2); self.assertNotEqual(self.process.hosts[0][1].data,self.process.hosts[1][1].data)
        self.assertEqual(receipt['queued_bytes_at_close'],0)
        self.assertTrue(all(x[2] != threading.get_ident() for x in self.owner.calls))
        for channel in receipt['channels']:
            self.assertEqual(channel['namespace_closed']['reason'],'clean_idle_eof')
            self.assertEqual(channel['meters']['client_read'],channel['namespace_closed']['upload'])
            self.assertEqual(channel['meters']['client_written'],channel['namespace_closed']['download'])
            self.assertNotIn('first_rejection',channel['h2'])
            self.assertNotIn('first_rejection',channel['namespace_closed']['h2'])
        events=self.bridge.ledger.events
        previous=None
        for n,event in enumerate(events,1):
            value=dict(event); digest=value.pop('record_sha256')
            self.assertEqual(bridge.sha(m.canonical(value)),digest);self.assertEqual(event['previous_sha256'],previous)
            self.assertEqual(event['sequence'],n);previous=digest
        self.assertLess(next(i for i,e in enumerate(events) if e['kind']=='owner_registered'),
                        next(i for i,e in enumerate(events) if e['kind']=='channel_authenticated'))
        self.assertTrue(any(e['kind']=='namespace_finished' for e in events))
        self.assertTrue(any(e['kind']=='owner_input_closed' for e in events))

    async def test_cleanup_barrier_is_paired_before_callback_returns_and_inherited(self):
        returned=[]
        async def body():
            _,writer,_=self.client();await writer.received.wait()
            seed=cleanup_seed()
            value=await asyncio.to_thread(self.fixture.native_cleanup_barrier,seed)
            returned.append(value)
            self.assertEqual(value['request']['nonce'],seed['nonce'])
            self.assertLess(value['completed_monotonic_s'],seed['graceful_deadline_monotonic_s'])
            _,second,_=self.client(2);await second.received.wait()
        receipt=await self.run_bridge(body)
        self.assertTrue(receipt['qualified']);self.assertEqual(receipt['cleanup_barrier'],returned[0])
        records=receipt['namespace_records']
        begin=next(e for e in self.bridge.ledger.events if e['kind']=='native_cleanup_begin')
        ack=next(e for e in self.bridge.ledger.events if e['kind']=='native_cleanup_ack')
        namespace=next(e for e in records if e['kind']=='native_cleanup_begin')
        self.assertEqual(ack['namespace_record'],namespace)
        self.assertEqual(returned[0]['parent_barrier_record_sha256'],begin['record_sha256'])
        self.assertEqual(returned[0]['namespace_barrier_record_sha256'],bridge.sha(m.canonical(namespace)))
        self.assertTrue(all(c['h2']['cleanup_phase_nonce']=='b'*32 for c in receipt['channels']))
        inherited=[e for e in self.bridge.ledger.events if e['kind']=='native_cleanup_channel']
        self.assertEqual([e['channel_id'] for e in inherited],[2])
        self.assertEqual(inherited[0]['h2']['last_stream_id'],0)

    async def cleanup_after_upload_eof(self, *, closed_in_flight):
        observed=[]
        async def body():
            held=asyncio.Event();release=asyncio.Event();send=self.process.relay.send
            async def delayed(kind,channel,payload=b'',account=True):
                if kind==m.CLOSED and closed_in_flight:
                    held.set();await release.wait()
                await send(kind,channel,payload,account)
            self.process.relay.send=delayed
            _,_,handler=self.client(natural=True)
            if closed_in_flight:await held.wait()
            else:await handler
            parent=self.bridge.channels[1];namespace=self.process.relay.channels[1]
            self.assertIsNotNone(parent.parent_eof);self.assertTrue(namespace.half_closed)
            self.assertTrue(namespace.closed)
            self.assertEqual(parent.state,'live' if closed_in_flight else 'closed')
            observed.append(parent.state)
            await asyncio.to_thread(self.fixture.native_cleanup_barrier,cleanup_seed())
            self.assertIsNone(parent.h2.summary()['cleanup_phase_nonce'])
            self.assertIsNone(namespace.h2.summary()['cleanup_phase_nonce'])
            release.set();await handler
        receipt=await self.run_bridge(body)
        self.assertTrue(receipt['qualified']);channel=receipt['channels'][0]
        self.assertEqual(channel['h2'],channel['namespace_closed']['h2'])
        parent=self.bridge.ledger.events;namespace=receipt['namespace_records']
        pbegin=next(e for e in parent if e['kind']=='native_cleanup_begin')
        nbegin=next(e for e in namespace if e['kind']=='native_cleanup_begin')
        self.assertTrue(pbegin['channels'][0]['upload_eof']);self.assertTrue(nbegin['channels'][0]['upload_eof'])
        self.assertEqual(pbegin['channels'][0]['already_closed'],not closed_in_flight)
        self.assertTrue(nbegin['channels'][0]['already_closed'])
        peof=next(e for e in parent if e['kind']=='client_eof')
        half=next(e for e in parent if e['kind']=='frame' and e['direction']=='outgoing' and e['frame_type']==m.HALF_CLOSE)
        begin=next(e for e in parent if e['kind']=='frame' and e['direction']=='outgoing' and e['frame_type']==m.CLEANUP_BEGIN)
        neof=next(e for e in namespace if e['kind']=='channel_eof' and e['direction']=='upload')
        nin=next(e for e in namespace if e['kind']=='frame' and e['direction']=='incoming' and e['frame_type']==m.CLEANUP_BEGIN)
        self.assertLess(peof['sequence'],pbegin['sequence']);self.assertLess(half['sequence'],begin['sequence'])
        self.assertLess(neof['sequence'],nin['sequence']);self.assertLess(nin['sequence'],nbegin['sequence'])
        return receipt

    async def test_cleanup_closed_receipt_in_flight_uses_genuine_upload_eof_for_enrollment(self):
        await self.cleanup_after_upload_eof(closed_in_flight=True)

    async def test_cleanup_already_closed_upload_eof_remains_unphased(self):
        await self.cleanup_after_upload_eof(closed_in_flight=False)

    async def test_cleanup_active_cancel_original_bytes_and_late_response(self):
        self.host_options={'reply':h2(4)}
        async def body():
            reader,writer,_=self.client();await writer.received.wait()
            await asyncio.to_thread(self.fixture.native_cleanup_barrier,cleanup_seed())
            cancel=h2(3,0,1,(8).to_bytes(4,'big'));reader.feed_data(cancel)
            while not self.process.relay.channels[1].h2.summary()['cleanup_cancel_records']:await asyncio.sleep(0)
            self.process.hosts[0][0].feed_data(h2(1,5,1,b'late'))
            while len(writer.data)<len(h2(4)+h2(1,5,1,b'late')):await asyncio.sleep(0)
        receipt=await self.run_bridge(body)
        channel=receipt['channels'][0]
        self.assertTrue(receipt['qualified']);self.assertEqual(channel['h2']['reset_streams'],1)
        self.assertEqual(channel['meters']['client_read'],channel['namespace_closed']['upload'])
        self.assertEqual(channel['h2'],channel['namespace_closed']['h2'])
        self.assertEqual(bytes(self.process.hosts[0][1].data),m.PREFACE+h2(4)+h2(1,5,1,b'\x82')+h2(3,0,1,(8).to_bytes(4,'big')))

    async def test_cleanup_active_normal_endpoint_race_preserves_raw_classification(self):
        self.host_options={'reply':h2(4)}
        async def body():
            reader,writer,_=self.client();await writer.received.wait()
            await asyncio.to_thread(self.fixture.native_cleanup_barrier,cleanup_seed())
            held=asyncio.Event();release=asyncio.Event();send=self.process.relay.send
            async def delayed(kind,channel,payload=b'',account=True):
                if kind==m.DATA and payload==h2(1,5,1,b'late'):
                    held.set();await release.wait()
                await send(kind,channel,payload,account)
            self.process.relay.send=delayed
            self.process.hosts[0][0].feed_data(h2(1,5,1,b'late'));await held.wait()
            reader.feed_data(h2(3,0,1,(8).to_bytes(4,'big')))
            while not self.process.relay.channels[1].h2.summary()['cleanup_cancel_records']:await asyncio.sleep(0)
            release.set()
            while len(writer.data)<len(h2(4)+h2(1,5,1,b'late')):await asyncio.sleep(0)
        receipt=await self.run_bridge(body)
        parent=receipt['channels'][0]['h2'];namespace=receipt['channels'][0]['namespace_closed']['h2']
        self.assertTrue(receipt['qualified'])
        self.assertEqual((parent['reset_streams'],namespace['reset_streams']),(1,0))
        self.assertEqual((parent['closed_streams'],namespace['closed_streams']),(0,1))
        self.assertEqual(parent['cleanup_cancel_records'][0]['local']['classification'],'active')
        self.assertEqual(namespace['cleanup_cancel_records'][0]['local']['classification'],'normal_closed')
        self.assertEqual(parent['cleanup_cancel_records'][0]['cancel'],namespace['cleanup_cancel_records'][0]['cancel'])

    async def test_cleanup_waits_for_pending_auth_and_inherits_next_channel(self):
        async def body():
            self.owner.gate=threading.Event()
            _,writer,_=self.client()
            while not self.owner.calls:await asyncio.sleep(0)
            barrier=asyncio.create_task(asyncio.to_thread(self.fixture.native_cleanup_barrier,cleanup_seed()))
            for _ in range(8):await asyncio.sleep(0)
            self.assertFalse(any(e['kind']=='native_cleanup_begin' for e in self.bridge.ledger.events))
            self.owner.gate.set();await barrier;await writer.received.wait()
            _,second,_=self.client(2);await second.received.wait()
        receipt=await self.run_bridge(body)
        begin=next(e for e in self.bridge.ledger.events if e['kind']=='native_cleanup_begin')
        self.assertTrue(receipt['qualified']);self.assertEqual([c['channel_id'] for c in begin['channels']],[1])
        frames=[e for e in self.bridge.ledger.events if e['kind']=='frame' and e['direction']=='outgoing']
        self.assertLess(next(i for i,e in enumerate(frames) if e['frame_type']==m.OPEN and e['channel_id']==1),
                        next(i for i,e in enumerate(frames) if e['frame_type']==m.CLEANUP_BEGIN))
        self.assertLess(next(i for i,e in enumerate(frames) if e['frame_type']==m.CLEANUP_BEGIN),
                        next(i for i,e in enumerate(frames) if e['frame_type']==m.OPEN and e['channel_id']==2))

    async def test_cleanup_callback_result_is_detached_from_ledger_and_terminal(self):
        async def body():
            value=await asyncio.to_thread(self.fixture.native_cleanup_barrier,cleanup_seed())
            value['request']['thread_id']='changed';value['request_sha256']='0'*64
        receipt=await self.run_bridge(body)
        self.assertEqual(receipt['cleanup_barrier']['request']['thread_id'],'thread-test')
        self.assertNotEqual(receipt['cleanup_barrier']['request_sha256'],'0'*64)

    async def test_planned_abort_kept_set_allows_cleanup_barrier_and_same_owner_channel(self):
        async def body():
            _,first,_=self.client();await first.received.wait()
            self.fixture.abort_event.set()
            await asyncio.to_thread(self.fixture.native_cleanup_barrier,cleanup_seed())
            self.assertTrue(self.fixture.abort_event.is_set())
            _,second,_=self.client(2);await second.received.wait()
        receipt=await self.run_bridge(body)
        self.assertTrue(receipt['qualified']);self.assertEqual(receipt['accepted'],2)
        self.assertTrue(self.fixture.abort_event.is_set());self.assertFalse(receipt['failures'])

    async def test_actual_transport_failure_rejects_cleanup_before_begin(self):
        async def body():
            self.bridge.fail('synthetic_actual_transport_failure')
            with self.assertRaisesRegex(ValueError,'cleanup_after_transport_failure'):
                await asyncio.to_thread(self.fixture.native_cleanup_barrier,cleanup_seed())
        receipt=await self.run_bridge(body,fail=True)
        self.assertIsNone(receipt['cleanup_barrier'])
        self.assertFalse(any(e['kind']=='native_cleanup_begin' for e in self.bridge.ledger.events))

    async def controller_with_paired_barrier(self, *, active):
        """Actual Client.close/Controller with a fake pipe, never a native launch."""
        from test_client_quiescence import QuiescenceTests
        helper=QuiescenceTests();self.addCleanup(helper.doCleanups)
        client,_=helper.client(state='active' if active else 'preflight')
        client.events.close();root=self.folder/'client';root.mkdir()
        client.args.evidence=root;client.events=(root/'events.jsonl').open('x',encoding='utf-8')
        client.args.abort_event=self.fixture.abort_event
        client.args.client_finishing=self.fixture.client_finishing
        requests=[];writes=[];observations=[];results=[]
        self.host_options={'reply':h2(4)}
        async def body():
            self.fixture.native_process_ready(client.process,'fake-native')
            active_reader=None
            if active:
                active_reader,writer,_=self.client();await writer.received.wait()
            # The real injected-interruption flag remains set throughout close.
            self.fixture.abort_event.set()
            def callback(seed):
                requests.append(json.loads(json.dumps(seed)))
                return self.fixture.native_cleanup_barrier(seed)
            client.args.native_cleanup_barrier=callback
            original=client.process.write
            loop=asyncio.get_running_loop()
            async def cancel_active():
                active_reader.feed_data(h2(3,0,1,(8).to_bytes(4,'big')))
                while not self.process.relay.channels[1].h2.summary()['cleanup_cancel_records']:
                    await asyncio.sleep(0)
                self.process.hosts[0][0].feed_data(h2(1,5,1,b'late'))
                while not self.bridge.channels[1].h2.summary()['cleanup_cancel_records'][0]['download_headers_complete']:
                    await asyncio.sleep(0)
            def write(wire):
                now=time.monotonic()
                ledger=[json.loads(line) for line in self.bridge.ledger.path.read_text().splitlines()]
                events=[json.loads(line) for line in (root/'events.jsonl').read_text().splitlines()]
                acks=[row for row in ledger if row['kind']=='native_cleanup_ack']
                completions=[row for row in events if row.get('phase')=='cleanup_barrier_complete']
                self.assertEqual(len(acks),1);self.assertEqual(len(completions),1)
                complete=completions[0]['receipt']
                self.assertEqual(complete['parent_ack_record_sha256'],acks[0]['record_sha256'])
                self.assertLessEqual(acks[0]['monotonic_s'],complete['completed_monotonic_s'])
                self.assertLessEqual(completions[0]['monotonic_s'],now)
                self.assertLess(now,requests[0]['graceful_deadline_monotonic_s'])
                self.assertTrue(self.fixture.abort_event.is_set())
                writes.append(bytes(wire));observations.append({'ack_sequence':acks[0]['sequence'],
                    'complete_sequence':completions[0]['sequence'],'write_monotonic_s':now,
                    'wire_bytes':len(wire),'wire_sha256':bridge.sha(wire)})
                if active and len(writes)==1:
                    asyncio.run_coroutine_threadsafe(cancel_active(),loop).result(timeout=2)
                original(wire)
            client.process.write=write
            result=await asyncio.to_thread(client.close)
            self.assertTrue(result['qualified'],result['failures']);results.append(result)
            self.assertTrue(self.fixture.abort_event.is_set())
            # Real native stdin EOF releases each fake authenticated TCP writer.
            for reader in self.client_readers:reader.feed_eof()
        receipt=await self.run_bridge(body,register=False)
        self.assertTrue(receipt['qualified']);self.assertEqual(len(requests),1)
        result=results[0];request=requests[0]
        self.assertEqual(receipt['cleanup_barrier'],result['cleanup_barrier'])
        self.assertEqual(request['start_monotonic_s'],result['start_monotonic_s'])
        self.assertEqual(request['graceful_deadline_monotonic_s'],result['start_monotonic_s']+5)
        self.assertEqual(request['control_event'],next(row for row in result['events'] if row['phase']=='request'))
        first={'id':41,'method':'turn/interrupt' if active else 'thread/unsubscribe',
               'params':{'threadId':'thread-fixed',**({'turnId':'turn-fixed'} if active else {})}}
        self.assertEqual(writes[0],(json.dumps(first)+'\n').encode())
        self.assertEqual(len(writes),2 if active else 1)
        self.assertEqual(len(result['controls']),len(writes))
        self.assertEqual(receipt['accepted'],1 if active else 0)
        self.assertEqual(request['turn_id'],'turn-fixed' if active else None)
        self.assertEqual(json.loads((root/'native-quiescence.json').read_text()),result)
        bridge.save(self.folder/'synthetic-control-write-observations.json',{'scope':'Fake native pipe only; actual Controller and paired Bridge/Relay',
                    'writes':observations,'callback_count':len(requests),'planned_abort_remained_set':True})
        return receipt

    async def test_actual_preflight_controller_joins_durable_paired_barrier_before_write(self):
        await self.controller_with_paired_barrier(active=False)

    async def test_actual_active_controller_joins_barrier_before_cancel_and_late_response(self):
        receipt=await self.controller_with_paired_barrier(active=True)
        self.assertEqual(receipt['channels'][0]['h2']['reset_streams'],1)
        self.assertEqual(len(receipt['channels'][0]['h2']['cleanup_cancel_records']),1)

    async def test_cleanup_duplicate_callback_is_permanent_failure(self):
        async def body():
            seed=cleanup_seed();await asyncio.to_thread(self.fixture.native_cleanup_barrier,seed)
            with self.assertRaisesRegex(ValueError,'duplicate_native_cleanup'):
                await asyncio.to_thread(self.fixture.native_cleanup_barrier,seed)
        receipt=await self.run_bridge(body,fail=True)
        self.assertFalse(receipt['qualified'])
        self.assertEqual(len([e for e in self.bridge.ledger.events if e['kind']=='native_cleanup_begin']),1)

    async def test_cleanup_missing_owner_cannot_emit_begin(self):
        async def body():
            with self.assertRaisesRegex(ValueError,'native_cleanup_missing_owner'):
                await asyncio.to_thread(self.fixture.native_cleanup_barrier,cleanup_seed())
        receipt=await self.run_bridge(body,register=False,fail=True)
        self.assertIsNone(receipt['cleanup_barrier'])
        self.assertFalse(any(e['kind']=='native_cleanup_begin' for e in self.bridge.ledger.events))

    async def test_cleanup_expired_seed_never_enqueues_begin(self):
        async def body():
            seed=cleanup_seed();seed['start_monotonic_s']-=10;seed['graceful_deadline_monotonic_s']-=10
            seed['control_event']['monotonic_s']-=10
            with self.assertRaisesRegex(ValueError,'native_cleanup_deadline'):
                await asyncio.to_thread(self.fixture.native_cleanup_barrier,seed)
        receipt=await self.run_bridge(body,fail=True)
        self.assertIsNone(receipt['cleanup_barrier'])
        self.assertFalse(any(e.get('frame_type')==m.CLEANUP_BEGIN for e in self.bridge.ledger.events))

    async def test_cleanup_missing_ack_times_out_and_late_ack_cannot_restore(self):
        held=[]
        async def body():
            send=self.process.relay.send
            async def intercept(kind,channel,payload=b'',account=True):
                if kind==m.CLEANUP_ACK:
                    held.append(payload);return
                await send(kind,channel,payload,account)
            self.process.relay.send=intercept
            seed=cleanup_seed();seed['graceful_deadline_monotonic_s']=seed['start_monotonic_s']+.15
            with self.assertRaises(TimeoutError):
                await asyncio.to_thread(self.fixture.native_cleanup_barrier,seed)
            self.assertTrue(self.bridge.cleanup_abandoned.is_set());self.assertTrue(held)
            with self.assertRaisesRegex(ValueError,'unexpected_native_cleanup_ack'):
                self.bridge.accept_cleanup_ack(held[0])
        receipt=await self.run_bridge(body,fail=True)
        self.assertIsNone(receipt['cleanup_barrier'])
        self.assertFalse(any(e['kind']=='native_cleanup_ack' for e in self.bridge.ledger.events))

    async def cleanup_ack_mutation(self, mutation, *, with_channel=False):
        async def body():
            if with_channel:
                _,writer,_=self.client();await writer.received.wait()
            send=self.process.relay.send
            async def intercept(kind,channel,payload=b'',account=True):
                if kind==m.CLEANUP_ACK:
                    value=json.loads(payload);mutation(value);payload=m.canonical(value)
                await send(kind,channel,payload,account)
            self.process.relay.send=intercept
            with self.assertRaises(ValueError):
                await asyncio.to_thread(self.fixture.native_cleanup_barrier,cleanup_seed())
        receipt=await self.run_bridge(body,fail=True)
        self.assertIsNone(receipt['cleanup_barrier'])
        self.assertFalse(any(e['kind']=='native_cleanup_ack' for e in self.bridge.ledger.events))

    async def test_cleanup_wrong_nonce_ack_rejected(self):
        await self.cleanup_ack_mutation(lambda value:value.update(nonce='c'*32))

    async def test_cleanup_wrong_owner_bound_request_digest_ack_rejected(self):
        await self.cleanup_ack_mutation(lambda value:value.update(request_sha256='a'*64))

    async def test_cleanup_wrong_child_ack_rejected(self):
        await self.cleanup_ack_mutation(lambda value:value['namespace_record'].update(child_pid=12345))

    async def test_cleanup_ack_cannot_substitute_upload_eof_boundary(self):
        await self.cleanup_ack_mutation(lambda value:value['namespace_record']['channels'][0].update(upload_eof=True),
                                        with_channel=True)

    async def test_cleanup_ack_upload_eof_requires_exact_boolean(self):
        await self.cleanup_ack_mutation(lambda value:value['namespace_record']['channels'][0].update(upload_eof=0),
                                        with_channel=True)

    async def test_cleanup_ack_record_must_exist_in_actual_namespace_stderr(self):
        async def body():
            send=self.process.relay.send
            async def intercept(kind,channel,payload=b'',account=True):
                if kind==m.CLEANUP_ACK:
                    value=json.loads(payload);value['namespace_record']['sequence']+=1;payload=m.canonical(value)
                await send(kind,channel,payload,account)
            self.process.relay.send=intercept
            await asyncio.to_thread(self.fixture.native_cleanup_barrier,cleanup_seed())
        receipt=await self.run_bridge(body,fail=True)
        self.assertFalse(receipt['qualified']);self.assertIn('namespace_receipt_ValueError',receipt['failures'])

    async def test_cleanup_callback_on_loop_does_not_deadlock(self):
        async def body():
            with self.assertRaisesRegex(ValueError,'cleanup_callback_on_owner_loop'):
                self.fixture.native_cleanup_barrier(cleanup_seed())
        await self.run_bridge(body,fail=True)
    async def test_owner_finish_keeps_download_sink_until_accounted_close(self):
        async def body():
            _,writer,_=self.client(); await writer.received.wait()
        receipt=await self.run_bridge(body)
        self.assertTrue(receipt['qualified']);self.assertEqual(receipt['channels'][0]['namespace_closed']['reason'],'owner_finish')
        self.assertTrue(self.process.stdin.closed); self.assertEqual(receipt['channels'][0]['meters']['download'],receipt['channels'][0]['meters']['client_written'])
    async def test_finish_event_closes_namespace_before_callback_returns(self):
        async def body():
            _,writer,_=self.client();await writer.received.wait()
            self.mark_finish()
            await asyncio.wait_for(asyncio.shield(self.bridge.finished),1)
            self.assertTrue(self.process.stdin.closed)
            self.assertTrue(self.bridge.finishing)
        receipt=await self.run_bridge(body)
        self.assertTrue(receipt['qualified'])
    async def test_missing_owner_rejects_before_open_or_client_read(self):
        async def body():
            reader,writer,task=self.client(); await task
            self.assertGreater(len(reader._buffer),0); self.assertFalse(writer.data)
        receipt=await self.run_bridge(body,register=False,fail=True)
        self.assertEqual(receipt['accepted'],0);self.assertEqual(receipt['denied'],1);self.assertEqual(self.owner.calls,[])
        self.assertFalse(any(e.get('frame_type')==m.OPEN for e in self.bridge.ledger.events))
    async def test_foreign_owner_rejects_before_open_or_client_read(self):
        self.owner.reject='foreign_tcp_owner'
        async def body():
            reader,writer,task=self.client(); await task
            self.assertGreater(len(reader._buffer),0);self.assertFalse(writer.data)
        receipt=await self.run_bridge(body,fail=True)
        self.assertEqual(receipt['accepted'],0);self.assertEqual(len(self.process.hosts),0)
        self.assertIn('channel_OwnerError',receipt['failures'])
        self.assertEqual(next(e['reason'] for e in self.bridge.ledger.events if e['kind']=='channel_denied'),'foreign_tcp_owner')
    async def test_repeated_registration_aborts_without_overwriting_receipt(self):
        async def body():
            before=(self.folder/'codehost-native-owner-v3.json').read_bytes()
            with self.assertRaises(ValueError):self.fixture.native_process_ready(object(),'other')
            self.assertEqual((self.folder/'codehost-native-owner-v3.json').read_bytes(),before)
        receipt=await self.run_bridge(body,fail=True)
        self.assertEqual(receipt['accepted'],0);self.assertTrue(self.fixture.abort_event.is_set())
    async def test_seventeenth_attempt_rejected_before_authentication(self):
        self.bridge.attempts=16
        async def body():
            _,_,task=self.client();await task
        receipt=await self.run_bridge(body,fail=True)
        self.assertEqual(receipt['attempts'],17);self.assertEqual(self.owner.calls,[])
    async def test_upload_queue_caps_are_fail_closed_without_partial_reserve(self):
        self.bridge.channels[1]=bridge.Channel(1,None,None,{})
        self.bridge.channels[2]=bridge.Channel(2,None,None,{})
        per_channel=(m.PER_CHANNEL_QUEUE_BYTES-bridge.FRAME_HEADROOM_BYTES)//65536
        for _ in range(per_channel):self.bridge.enqueue(m.DATA,1,b'a'*65536)
        with self.assertRaises(ValueError):self.bridge.enqueue(m.DATA,1,b'b')
        self.assertEqual(self.bridge.budget.total,m.PER_CHANNEL_QUEUE_BYTES-bridge.FRAME_HEADROOM_BYTES)
        channel=2
        while self.bridge.budget.total+bridge.FRAME_HEADROOM_BYTES < m.AGGREGATE_QUEUE_BYTES:
            for _ in range(per_channel):
                if self.bridge.budget.total+bridge.FRAME_HEADROOM_BYTES == m.AGGREGATE_QUEUE_BYTES:break
                self.bridge.enqueue(m.DATA,channel,b'b'*65536)
            channel+=1
        with self.assertRaises(ValueError):self.bridge.enqueue(m.DATA,channel,b'x')
        self.assertEqual(self.bridge.budget.total+bridge.FRAME_HEADROOM_BYTES,m.AGGREGATE_QUEUE_BYTES)
    async def test_prefinish_inflight_client_eof_is_permanent_failure(self):
        self.host_options['respond']=False
        async def body():
            reader,_,task=self.client();reader.feed_eof();await task
        receipt=await self.run_bridge(body,fail=True)
        self.assertFalse(receipt['qualified']);self.assertTrue(any('channel_' in x for x in receipt['failures']))
    async def test_reset_cannot_be_retroactively_excused(self):
        channel=bridge.Channel(1,None,None,{})
        self.bridge.channels[1]=channel
        self.bridge.feed_h2(channel,'upload',m.PREFACE+h2(4)+h2(1,5,1,b'x'))
        self.bridge.feed_h2(channel,'download',h2(4))
        with self.assertRaisesRegex(ValueError,'reset_before_owner_finish'):
            self.bridge.feed_h2(channel,'download',h2(3,0,1,(8).to_bytes(4,'big')))
        self.mark_finish()
        self.bridge.observe_finishing()
        self.assertIn('retirement_frontier_invalid',self.bridge.failures)
    async def test_finish_allows_only_cancel_for_previously_active_stream(self):
        channel=bridge.Channel(1,None,None,{})
        self.bridge.channels[1]=channel
        self.bridge.feed_h2(channel,'upload',m.PREFACE+h2(4)+h2(1,5,1,b'x'))
        self.bridge.feed_h2(channel,'download',h2(4));self.mark_finish()
        self.bridge.feed_h2(channel,'download',h2(3,0,1,(8).to_bytes(4,'big')))
        self.assertEqual(channel.finish_frontier['active_stream_ids'],[1])
        bad=bridge.Channel(2,None,None,{})
        self.bridge.channels[2]=bad
        bad.h2.feed('upload',m.PREFACE+h2(4)+h2(1,5,1,b'x'));bad.h2.feed('download',h2(4))
        with self.assertRaises(ValueError):self.bridge.feed_h2(bad,'download',h2(3,0,1,(2).to_bytes(4,'big')))
    async def test_unverified_retirement_never_qualifies(self):
        self.retirement_qualified=False
        async def body():pass
        receipt=await self.run_bridge(body,fail=True)
        self.assertFalse(receipt['qualified']);self.assertIn('owner_retirement_ValueError',receipt['failures'])
    async def test_child_status_cannot_be_masked_by_qualified_namespace_flag(self):
        self.host_options['terminal_change']={'child_exit_code':7,'qualified':True}
        async def body():pass
        receipt=await self.run_bridge(body,fail=True)
        self.assertFalse(receipt['qualified']);self.assertIn('namespace_receipt_ValueError',receipt['failures'])
        self.assertEqual(receipt['namespace_records'][-1]['child_exit_code'],7)
        self.assertEqual(bridge.sha((self.folder/receipt['stderr']['path']).read_bytes()),receipt['stderr']['sha256'])
    async def test_nonzero_wrapper_exit_never_qualifies(self):
        self.wrapper_exit=7
        async def body():pass
        receipt=await self.run_bridge(body,fail=True)
        self.assertIn('namespace_wrapper_nonzero',receipt['failures'])
    async def test_endpoint_mismatch_rejected_before_channel_closed(self):
        reader=asyncio.StreamReader();writer=NativeSocket(reader,40001)
        channel=bridge.Channel(1,reader,writer,{})
        self.bridge.channels[1]=channel;channel.state='closed'
        channel.h2.feed('upload',m.PREFACE+h2(4));channel.h2.feed('download',h2(4))
        channel.namespace_closed={'qualified':True,'reason':'clean_idle_eof','upload':{'bytes':1,'sha256':'a'*64},
                                  'download':channel.meters['download'].summary()}
        channel.queue.put_nowait(None)
        with self.assertRaisesRegex(ValueError,'relay_endpoint_byte_mismatch'):await self.bridge.sink(channel)
        channel.closed.exception()
        self.assertFalse(any(e['kind']=='channel_closed' for e in self.bridge.ledger.events))
    async def test_malformed_partial_or_data_before_opened_fail_closed(self):
        for wire in (b'bad',m.encode_frame(m.DATA,1,b'x'),m.encode_frame(m.OPENED,1)*2):
            with self.subTest(wire=wire[:14]):
                other_folder=self.folder/str(len(self.bridge.ledger.events));other_folder.mkdir()
                fixture=SimpleNamespace(**vars(self.fixture));fixture.evidence=other_folder
                b=bridge.Bridge(fixture,owner=self.owner,launcher=mock.AsyncMock(),retirer=mock.AsyncMock(),sources={})
                loop=asyncio.get_running_loop();b.ready=loop.create_future();b.ready.set_result({});b.finished=loop.create_future()
                c=bridge.Channel(1,None,None,{});b.channels[1]=c
                output=asyncio.StreamReader();output.feed_data(wire);output.feed_eof();b.process=SimpleNamespace(stdout=output)
                with self.assertRaises(ValueError):await b.receive_frames()
                for future in (b.finished,b.drain_ack,b.cleanup_ack,c.opened,c.closed):
                    if future.done():future.exception()
                self.assertTrue(b.failures)
                # Give subsequent subtests a unique retained metadata directory.
                self.bridge.ledger.emit('synthetic_case_complete')
    async def test_receipt_size_bound_is_checked_before_file_creation(self):
        target=self.folder/'too-large.json'
        with mock.patch.object(bridge,'MAX_RECEIPT_BYTES',8):
            with self.assertRaisesRegex(ValueError,'protected_receipt_bound'):bridge.save(target,{'payload':'abcdef'})
        self.assertFalse(target.exists())
    async def test_pending_client_read_is_reserved_and_released_on_cancel(self):
        reader=asyncio.StreamReader();channel=bridge.Channel(1,reader,None,{})
        self.bridge.channels[1]=channel
        task=asyncio.create_task(self.bridge.upload(channel));await asyncio.sleep(0)
        self.assertEqual(self.bridge.budget.total,65536)
        task.cancel();await asyncio.gather(task,return_exceptions=True)
        self.assertEqual(self.bridge.budget.total,0)
        self.assertEqual(self.bridge.budget.channel_maximum[1],65536)
    async def test_pending_read_shutdown_cancel_is_forwarded_before_seal(self):
        tail=h2(3,0,1,(8).to_bytes(4,'big'))
        async def body():
            reader,writer,_=self.client(payload=b'x');await writer.received.wait()
            # Create a different still-active stream for the actual pending read.
            reader.feed_data(h2(1,4,3,b'\x82'))
            while self.bridge.channels[1].h2.summary()['last_stream_id'] != 3:await asyncio.sleep(0)
            self.mark_finish(close_uploads=False)
            reader.feed_data(h2(3,0,3,(8).to_bytes(4,'big')));reader.feed_eof()
        receipt=await self.run_bridge(body)
        self.assertTrue(receipt['qualified']);channel=receipt['channels'][0]
        self.assertEqual(channel['finish_frontier']['active_stream_ids'],[3])
        self.assertEqual(channel['h2']['reset_records'],[{'direction':'upload','stream_id':3,'error_code':8}])
        self.assertEqual(channel['meters']['client_read'],channel['meters']['upload'])
        rows=self.bridge.ledger.events
        begin=next(r['sequence'] for r in rows if r['kind']=='frame' and r['direction']=='outgoing' and r['frame_type']==m.DRAIN_BEGIN)
        eof=next(r['sequence'] for r in rows if r['kind']=='client_eof')
        seal=next(r['sequence'] for r in rows if r['kind']=='owner_finishing')
        self.assertLess(begin,seal);self.assertLess(eof,seal)
        self.assertTrue(receipt['drain']['seal_qualified'])

    async def test_fragmented_cancel_during_pending_read_keeps_every_byte(self):
        async def body():
            reader,writer,_=self.client();await writer.received.wait()
            reader.feed_data(h2(1,4,3,b'\x82'))
            while self.bridge.channels[1].h2.summary()['last_stream_id'] != 3:await asyncio.sleep(0)
            self.mark_finish(close_uploads=False)
            cancel=h2(3,0,3,(8).to_bytes(4,'big'))
            reader.feed_data(cancel[:7]);await asyncio.sleep(0)
            reader.feed_data(cancel[7:]);reader.feed_eof()
        receipt=await self.run_bridge(body)
        self.assertTrue(receipt['qualified']);c=receipt['channels'][0]
        self.assertEqual(c['meters']['client_read'],c['namespace_closed']['upload'])
        self.assertEqual(c['h2']['last_stream_id'],c['finish_frontier']['last_stream_id'])

    async def test_new_stream_open_and_close_in_one_tail_fails_and_counts_observed_bytes(self):
        observed=[]
        async def body():
            reader,writer,task=self.client();await writer.received.wait()
            self.mark_finish(close_uploads=False)
            tail=h2(1,5,3,b'\x82')+h2(3,0,3,(8).to_bytes(4,'big'))
            observed.append(self.bridge.channels[1].meters['client_read'].summary()['bytes']+len(tail))
            reader.feed_data(tail);reader.feed_eof();await task
        receipt=await self.run_bridge(body,fail=True)
        self.assertFalse(receipt['qualified']);c=receipt['channels'][0]
        self.assertEqual(c['meters']['client_read']['bytes'],observed[0])
        self.assertLess(c['meters']['upload']['bytes'],c['meters']['client_read']['bytes'])
        self.assertFalse(receipt['drain']['seal_qualified'])
        self.assertEqual(c['h2']['first_rejection'],{
            'schema':'campaign002-h2-rejection-1','direction':'upload','frame_type':1,
            'flags':5,'stream_id':3,'payload_length':1,'active_at_rejection':False,
            'in_original_frontier':False,'original_last_stream_id':1})
        self.assertEqual(c['seal_frontier']['first_rejection'],c['h2']['first_rejection'])

    async def test_reset_reuse_rejection_survives_failed_drain_without_payload_or_forwarding(self):
        payload=b'private-header-value-'*700
        cancel=h2(3,0,3,(8).to_bytes(4,'big'))
        tail=cancel+h2(1,5,3,payload)
        before=[]
        async def body():
            reader,writer,task=self.client();await writer.received.wait()
            reader.feed_data(h2(1,4,3,b'\x82'))
            while self.bridge.channels[1].meters['upload'].summary()['bytes'] != 53:await asyncio.sleep(0)
            before.append(self.bridge.channels[1].meters['upload'].summary())
            self.mark_finish(close_uploads=False)
            reader.feed_data(tail);reader.feed_eof();await task
        receipt=await self.run_bridge(body,fail=True)
        channel=receipt['channels'][0]
        self.assertFalse(receipt['qualified']);self.assertFalse(receipt['drain']['seal_qualified'])
        self.assertIn('channel_ValueError',receipt['failures']);self.assertIn('drain_invalid',receipt['failures'])
        self.assertEqual(channel['h2']['error'],'HTTP/2 new stream after retirement')
        expected={'schema':'campaign002-h2-rejection-1','direction':'upload','frame_type':1,
            'flags':5,'stream_id':3,'payload_length':len(payload),'active_at_rejection':False,
            'in_original_frontier':True,'original_last_stream_id':3}
        self.assertEqual(channel['h2']['first_rejection'],expected)
        self.assertEqual(channel['seal_frontier']['first_rejection'],expected)
        self.assertEqual(channel['meters']['upload'],before[0])
        self.assertEqual(channel['meters']['client_read']['bytes'],before[0]['bytes']+len(tail))
        self.assertNotIn('first_rejection',channel['namespace_closed']['h2'])
        self.assertNotIn(payload,bytes(self.process.hosts[0][1].data))
        self.assertNotIn(b'private-header-value',(self.folder/'codehost-owner-bridge-v3.json').read_bytes())
        self.assertLess(len(m.canonical(expected)),384)
        self.assertIsNotNone(receipt['retirement'])

    async def test_partial_download_at_seal_finishes_before_genuine_host_eof(self):
        response=h2(1,5,1,b'\x88')
        self.host_options.update(reply=h2(4)+response[:5],defer_download_eof=True)
        async def body():
            _,writer,_=self.client();await writer.received.wait()
            self.mark_finish()
            while not self.bridge.sealed:await asyncio.sleep(0)
            self.assertFalse(self.bridge.channels[1].seal_frontier['frames_complete'])
            self.assertTrue(self.bridge.channels[1].seal_frontier['upload_complete'])
            self.process.hosts[0][0].feed_data(response[5:]);self.process.hosts[0][0].feed_eof()
        receipt=await self.run_bridge(body)
        self.assertTrue(receipt['qualified']);self.assertTrue(receipt['channels'][0]['h2']['frames_complete'])
        rows=self.bridge.ledger.events;seal=next(r['sequence'] for r in rows if r['kind']=='owner_finishing')
        self.assertTrue(any(r['kind']=='frame' and r['direction']=='incoming' and r['frame_type']==m.DATA and r['sequence']>seal for r in rows))

    async def test_normal_closed_cancel_is_forwarded_and_proved_at_both_endpoints(self):
        cancel=h2(3,0,1,(8).to_bytes(4,'big'));before=[]
        async def body():
            reader,writer,_=self.client();await writer.received.wait()
            channel=self.bridge.channels[1]
            self.assertEqual(channel.h2.summary()['closed_streams'],1)
            before.append(channel.meters['upload'].summary()['bytes'])
            reader.feed_data(cancel[:8]);await asyncio.sleep(0)
            reader.feed_data(cancel[8:])
            while channel.meters['upload'].summary()['bytes'] != before[0]+13:await asyncio.sleep(0)
        receipt=await self.run_bridge(body)
        self.assertTrue(receipt['qualified']);channel=receipt['channels'][0]
        self.assertEqual(channel['meters']['client_read'],channel['meters']['upload'])
        self.assertEqual(channel['meters']['upload'],channel['namespace_closed']['upload'])
        self.assertEqual(channel['meters']['upload']['bytes'],before[0]+13)
        self.assertTrue(bytes(self.process.hosts[0][1].data).endswith(cancel))
        parent=channel['h2']['terminal_control_records']
        namespace=channel['namespace_closed']['h2']['terminal_control_records']
        self.assertEqual(parent,namespace)
        self.assertEqual(len(parent),1);self.assertEqual(parent[0]['stream_id'],1)
        self.assertEqual(channel['finish_frontier']['terminal_control_records'],parent)
        self.assertEqual(channel['namespace_closed']['finish_frontier']['terminal_control_records'],namespace)
        self.assertEqual(channel['h2']['reset_records'],[])
        self.assertEqual(channel['h2']['reset_streams'],0)

    async def test_duplicate_normal_closed_cancel_still_fails_before_forwarding(self):
        cancel=h2(3,0,1,(8).to_bytes(4,'big'));before=[]
        async def body():
            reader,writer,task=self.client();await writer.received.wait()
            channel=self.bridge.channels[1];target=channel.meters['upload'].summary()['bytes']+13
            reader.feed_data(cancel)
            while channel.meters['upload'].summary()['bytes'] != target:await asyncio.sleep(0)
            before.append(channel.meters['upload'].summary())
            reader.feed_data(cancel);reader.feed_eof();await task
        receipt=await self.run_bridge(body,fail=True);channel=receipt['channels'][0]
        self.assertFalse(receipt['qualified'])
        self.assertEqual(channel['h2']['error'],'HTTP/2 reset on unavailable stream')
        self.assertEqual(len(channel['h2']['terminal_control_records']),1)
        self.assertEqual(channel['meters']['upload'],before[0])
        self.assertEqual(channel['meters']['client_read']['bytes'],before[0]['bytes']+13)
        self.assertEqual(len(self.process.hosts[0][1].data),before[0]['bytes'])
        self.assertIsNotNone(receipt['retirement'])

    async def test_normal_closed_cancel_does_not_waive_retirement_failure(self):
        self.retirement_qualified=False
        async def body():
            reader,writer,_=self.client();await writer.received.wait()
            channel=self.bridge.channels[1];target=channel.meters['upload'].summary()['bytes']+13
            reader.feed_data(h2(3,0,1,(8).to_bytes(4,'big')))
            while channel.meters['upload'].summary()['bytes'] != target:await asyncio.sleep(0)
        receipt=await self.run_bridge(body,fail=True)
        self.assertFalse(receipt['qualified']);self.assertIn('owner_retirement_ValueError',receipt['failures'])
        self.assertEqual(len(receipt['channels'][0]['h2']['terminal_control_records']),1)

    async def _assert_terminal_control_does_not_waive_drain_gate(self, gate):
        channel=bridge.Channel(1,None,None,{})
        self.bridge.channels[1]=channel
        channel.h2.feed('upload',m.PREFACE+h2(4)+h2(1,5,1,b'x'))
        channel.h2.feed('download',h2(4)+h2(1,5,1,b'y'))
        channel.h2.feed('upload',h2(3,0,1,(8).to_bytes(4,'big')))
        if gate!='eof':channel.parent_eof={'synthetic':True}
        if gate=='bytes':
            channel.upload_drained={'synthetic':True}
            channel.meters['client_read'].add(b'observed-but-not-forwarded')
        self.mark_finish();self.bridge.begin_finish()
        self.bridge.drain_ack.set_result({'synthetic':True})
        await self.bridge.finish_owner()
        self.assertFalse(self.bridge.drain['seal_qualified'])
        self.assertEqual(self.bridge.drain['seal_error_code'],'drain_invalid')
        self.assertEqual(len(channel.seal_frontier['terminal_control_records']),1)
        self.assertTrue(self.fixture.abort_event.is_set())

    async def test_normal_closed_cancel_still_requires_genuine_upload_eof(self):
        await self._assert_terminal_control_does_not_waive_drain_gate('eof')

    async def test_normal_closed_cancel_still_requires_completed_upload_drain(self):
        await self._assert_terminal_control_does_not_waive_drain_gate('drain')

    async def test_normal_closed_cancel_still_requires_exact_observed_forwarded_bytes(self):
        await self._assert_terminal_control_does_not_waive_drain_gate('bytes')

    async def test_exact_partial_probe_eof_remains_unqualified_and_retires(self):
        self.host_options['reply']=h2(4)+h2(4,1)
        async def body():
            reader=asyncio.StreamReader();self.client_readers.append(reader)
            reader.feed_data(m.PREFACE+h2(4)+h2(4,1))
            writer=NativeSocket(reader,40001);task=asyncio.create_task(self.bridge.handle(reader,writer))
            await writer.received.wait();reader.feed_data(b'\x00\x00\x04');reader.feed_eof();await task
        receipt=await self.run_bridge(body,fail=True)
        self.assertFalse(receipt['qualified']);self.assertEqual(receipt['channels'][0]['meters']['client_read']['bytes'],45)
        self.assertIsNotNone(receipt['retirement']);self.assertIsNotNone(receipt['finished'])
        self.assertEqual(receipt['drain']['seal_error_code'],'drain_invalid')

    async def test_expired_original_marker_never_restarts_cleanup_allowance(self):
        async def body():
            self.mark_finish()
            path=self.folder/'client/events.jsonl';value=json.loads(path.read_text());value['monotonic_s']-=26
            path.write_text(json.dumps(value)+'\n')
        receipt=await self.run_bridge(body,fail=True)
        self.assertFalse(receipt['qualified']);self.assertEqual(receipt['drain']['deadline_monotonic_s']-receipt['drain']['start_monotonic_s'],25)
        self.assertIn('owner_drain_TimeoutError',receipt['failures']);self.assertIsNotNone(receipt['retirement'])

    async def test_missing_ack_cannot_seal_qualified(self):
        self.mark_finish();self.bridge.process=SimpleNamespace(stdin=Pipe(asyncio.StreamReader()))
        self.bridge.begin_finish()
        self.bridge.drain['deadline_monotonic_s']=time.monotonic()+.02
        await self.bridge.drain_task
        self.assertEqual(self.bridge.drain['seal_error_code'],'drain_timeout')
        self.assertFalse(self.bridge.drain['seal_qualified'])
        self.assertEqual([f[0] for f in list(self.bridge.outgoing._queue)],[m.DRAIN_BEGIN,m.FINISH])

    async def failed_startup(self, raw=b'', stderr_reader=None):
        self.host_factory=EarlyFailureHost;self.host_options={'raw':raw,'stderr_reader':stderr_reader};self.wrapper_exit=1
        async def body():self.fail('Startup failure must not enter the native callback')
        return await self.run_bridge(body,fail=True)

    async def test_receiver_failure_retains_malformed_startup_stderr_and_retirement(self):
        raw=b'Traceback: fixed synthetic namespace mount failure\n'
        receipt=await self.failed_startup(raw)
        self.assertFalse(receipt['qualified']);self.assertIsNone(receipt['ready']);self.assertIsNone(receipt['owner'])
        self.assertEqual(receipt['attempts'],0);self.assertNotIn('namespace_records',receipt)
        retained=(self.folder/receipt['stderr']['path']).read_bytes()
        self.assertEqual(retained,raw);self.assertEqual(receipt['stderr']['raw_sha256'],bridge.sha(raw))
        self.assertEqual(receipt['stderr']['raw_bytes'],len(raw));self.assertTrue(receipt['stderr_capture']['capture_complete'])
        self.assertFalse(receipt['stderr']['redacted']);self.assertFalse(receipt['stderr']['truncated'])
        self.assertTrue((self.folder/receipt['retirement']['path']).exists())
        self.assertIn('frame_read_ValueError',receipt['failures']);self.assertIn('namespace_receipt_ValueError',receipt['failures'])

    async def test_receiver_failure_retains_redacted_text_and_original_identity(self):
        token='synthetic-secret-capability';raw=('startup '+token+' failed\n').encode()
        self.fixture.redact=lambda text:text.replace(token,'[REDACTED]')
        receipt=await self.failed_startup(raw)
        retained=(self.folder/receipt['stderr']['path']).read_bytes()
        self.assertNotIn(token.encode(),retained);self.assertIn(b'[REDACTED]',retained)
        self.assertTrue(receipt['stderr']['redacted']);self.assertFalse(receipt['qualified'])
        self.assertEqual(receipt['stderr']['raw_sha256'],bridge.sha(raw))
        self.assertEqual(receipt['stderr']['sha256'],bridge.sha(retained))
        self.assertNotEqual(receipt['stderr']['sha256'],receipt['stderr']['raw_sha256'])

    async def test_overbound_startup_retains_only_complete_redactable_prefix(self):
        raw=b'complete line\n'+b'synthetic-capability-crosses-boundary-and-must-not-leak\n'
        with mock.patch.object(bridge,'MAX_STDERR_BYTES',32):receipt=await self.failed_startup(raw)
        retained=(self.folder/receipt['stderr']['path']).read_bytes()
        self.assertEqual(retained,b'complete line\n');self.assertLessEqual(len(retained),32)
        self.assertTrue(receipt['stderr']['truncated']);self.assertFalse(receipt['qualified'])
        self.assertEqual(receipt['stderr']['raw_bytes'],len(raw));self.assertEqual(receipt['stderr']['raw_sha256'],bridge.sha(raw))
        self.assertEqual(receipt['stderr_capture']['discarded_partial_tail_bytes'],32-len(retained))

    async def test_invalid_utf8_diagnostics_are_safe_and_never_qualified(self):
        raw=b'startup invalid \xff byte\n';receipt=await self.failed_startup(raw)
        retained=(self.folder/receipt['stderr']['path']).read_bytes()
        self.assertIn('\ufffd',retained.decode('utf-8'));self.assertFalse(receipt['stderr_capture']['utf8_valid'])
        self.assertEqual(receipt['stderr_capture']['decode_error_type'],'UnicodeDecodeError')
        self.assertEqual(receipt['stderr']['raw_sha256'],bridge.sha(raw));self.assertFalse(receipt['qualified'])

    async def test_failed_stderr_read_retains_observed_prefix_without_full_stream_claim(self):
        class BrokenReader:
            def __init__(self):self.calls=0
            async def read(self,count):
                self.calls+=1
                if self.calls==1:return b'observed complete line\npartial'
                raise OSError('synthetic pipe failure')
        receipt=await self.failed_startup(stderr_reader=BrokenReader())
        self.assertEqual((self.folder/receipt['stderr']['path']).read_bytes(),b'observed complete line\n')
        self.assertFalse(receipt['stderr_capture']['capture_complete']);self.assertEqual(receipt['stderr_capture']['error_type'],'OSError')
        self.assertTrue(receipt['stderr']['truncated']);self.assertFalse(receipt['qualified'])
        self.assertEqual(receipt['stderr']['raw_sha256'],bridge.sha(b'observed complete line\npartial'))

    async def test_redactor_failure_withholds_text_but_preserves_observed_hash(self):
        raw=b'synthetic secret that cannot be safely redacted\n'
        def broken(text):raise ValueError('synthetic redaction failure')
        self.fixture.redact=broken;receipt=await self.failed_startup(raw)
        retained=(self.folder/receipt['stderr']['path']).read_bytes()
        self.assertEqual(retained,b'[STDERR_WITHHELD_REDACTION_FAILED]\n')
        self.assertNotIn(raw,retained);self.assertTrue(receipt['stderr']['redacted'])
        self.assertEqual(receipt['stderr_capture']['redaction_error_type'],'ValueError')
        self.assertEqual(receipt['stderr']['raw_sha256'],bridge.sha(raw));self.assertFalse(receipt['qualified'])


    async def test_socket_abort_metadata_does_not_qualify_or_invent_eof(self):
        injected = ConnectionAbortedError(1236, 'SECRET_SOCKET_ERROR')
        async def body():
            reader, writer, task = self.client()
            await writer.received.wait()
            reader.set_exception(injected)
            await task
        receipt = await self.run_bridge(body, fail=True)
        rows = [row for row in self.bridge.ledger.events if row['kind'] == 'socket_failure']
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['channel_id'], rows[0]['operation'], rows[0]['errno']), (1, 'upload_read', 1236))
        self.assertFalse(receipt['qualified'])
        self.assertIn('channel_ConnectionAbortedError', receipt['failures'])
        self.assertIn('drain_invalid', receipt['failures'])
        self.assertIsNone(receipt['channels'][0]['parent_eof'])
        self.assertIsNone(receipt['channels'][0]['upload_drained'])
        self.assertNotIn('SECRET_SOCKET_ERROR', (self.folder/'codehost-transport-v3.jsonl').read_text())
        failure = next(row for row in self.bridge.ledger.events if row['kind'] == 'failure')
        self.assertLess(rows[0]['sequence'], failure['sequence'])

    async def test_socket_write_error_metadata_keeps_paired_failure_and_retirement(self):
        injected = BrokenPipeError(32, 'SECRET_WRITE_ERROR')
        async def body():
            reader, writer, task = self.client()
            def broken_write(data): raise injected
            writer.write = broken_write
            await task
        receipt = await self.run_bridge(body, fail=True)
        rows = [row for row in self.bridge.ledger.events if row['kind'] == 'socket_failure']
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['operation'], rows[0]['exception_class']), ('download_write', 'BrokenPipeError'))
        self.assertFalse(receipt['qualified'])
        self.assertIn('channel_sink_BrokenPipeError', receipt['failures'])
        self.assertEqual(receipt['channels'][0]['meters']['client_written']['bytes'], 0)
        self.assertNotIn('SECRET_WRITE_ERROR', json.dumps(rows))


class SocketFailureInstrumentationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.fixture = SimpleNamespace(evidence=self.folder, run='/fake/run', abort_event=threading.Event(),
                                       client_finishing=threading.Event())
        self.bridge = bridge.Bridge(self.fixture, owner=FakeOwner(), retirer=mock.AsyncMock(), sources={})

    def channel(self, reader=None, writer=None, index=1):
        channel = bridge.Channel(index, reader, writer, {'owner_pid':123})
        channel.state = 'live'
        self.bridge.channels[index] = channel
        return channel

    def records(self):
        return [row for row in self.bridge.ledger.events if row['kind'] == 'socket_failure']

    async def test_upload_error_is_same_object_metadata_detached_and_no_eof(self):
        injected = ConnectionAbortedError(1236, 'SECRET' * 10000)
        injected.winerror = 10053
        class Reader:
            async def read(self, count): raise injected
        channel = self.channel(Reader())
        channel.meters['client_read'].add(b'known')
        self.bridge.cleanup_request = {'opaque':'not retained'}
        self.fixture.client_finishing.set()
        with self.assertRaises(ConnectionAbortedError) as caught:
            await self.bridge.upload(channel)
        self.assertIs(caught.exception, injected)
        row = self.records()[0]
        self.assertEqual(row['diagnostic_schema'], 'campaign002-socket-failure-1')
        self.assertEqual((row['errno'], row['winerror']), (1236, 10053))
        self.assertEqual(row['exception_class'], 'ConnectionAbortedError')
        self.assertTrue(row['cleanup_active']); self.assertTrue(row['client_finishing'])
        self.assertFalse(row['owner_draining']); self.assertFalse(row['owner_sealed'])
        self.assertEqual(row['byte_counters']['client_read'], 5)
        channel.meters['client_read'].add(b'later'); self.fixture.client_finishing.clear()
        self.assertEqual(row['byte_counters']['client_read'], 5)
        self.assertTrue(row['client_finishing'])
        self.assertLess(len(json.dumps(row)), 1400)
        self.assertNotIn('SECRET', json.dumps(row)); self.assertNotIn('opaque', json.dumps(row))
        self.assertIsNone(channel.parent_eof); self.assertIsNone(channel.upload_drained)
        self.assertFalse(channel.upload_read_pending)
        self.assertTrue(self.bridge.outgoing.empty()); self.assertEqual(self.bridge.budget.total, 0)

    async def test_both_writer_sites_keep_original_error_and_release_queue(self):
        for index, site in enumerate(('write', 'drain'), 1):
            with self.subTest(site=site):
                injected = BrokenPipeError(32, 'PRIVATE-WRITE')
                class Writer:
                    def write(self, data):
                        if site == 'write': raise injected
                    async def drain(self):
                        if site == 'drain': raise injected
                channel = self.channel(writer=Writer(), index=index)
                self.bridge.budget.reserve(index, 4); channel.queue.put_nowait(b'data')
                channel.meters['download'].add(b'data')
                with self.assertRaises(BrokenPipeError) as caught:
                    await self.bridge.sink(channel)
                self.assertIs(caught.exception, injected)
                self.assertIs(channel.closed.exception(), injected)
                self.assertEqual(self.records()[-1]['operation'], 'download_write')
                self.assertEqual(channel.meters['client_written'].bytes, 0)
                self.assertEqual(self.bridge.budget.total, 0)
                await channel.queue.join()

    async def test_numeric_codes_are_genuine_bounded_integers_and_classes_closed(self):
        class SECRET_CLASS(OSError): pass
        values = [(True, None), (False, None), ('10053', None), (3.0, None),
                  (-(2**31)-1, None), (2**32, None), (-(2**31), -(2**31)),
                  (2**32-1, 2**32-1), (None, None), (0, 0)]
        for index, (value, expected) in enumerate(values, 1):
            injected = SECRET_CLASS('SECRET-ARG'); injected.errno = value; injected.winerror = value
            channel = self.channel(index=index)
            self.bridge.record_socket_failure(channel, 'upload_read', injected)
            row = self.records()[-1]
            self.assertEqual((row['errno'], row['winerror']), (expected, expected))
            self.assertEqual(row['exception_class'], 'OtherOSError')
            self.assertNotIn('SECRET', json.dumps(row))

    async def test_first_socket_failure_only_per_channel_even_across_operations(self):
        channel = self.channel()
        self.bridge.record_socket_failure(channel, 'upload_read', ConnectionResetError(10054, 'secret'))
        self.bridge.record_socket_failure(channel, 'download_write', BrokenPipeError(32, 'later'))
        self.assertEqual(len(self.records()), 1)
        self.assertEqual(self.records()[0]['operation'], 'upload_read')
        self.bridge.record_socket_failure(self.channel(index=2), 'download_write', BrokenPipeError())
        self.assertEqual(len(self.records()), 2)

    async def test_ledger_failure_never_replaces_original_socket_error(self):
        injected = ConnectionAbortedError(1236, 'secret')
        class Reader:
            async def read(self, count): raise injected
        channel = self.channel(Reader())
        with mock.patch.object(self.bridge.ledger, 'emit', side_effect=OSError('ledger failure')) as emit:
            with self.assertRaises(ConnectionAbortedError) as caught:
                await self.bridge.upload(channel)
            self.assertIs(caught.exception, injected)
            self.bridge.record_socket_failure(channel, 'download_write', BrokenPipeError())
            self.assertEqual(emit.call_count, 1)
        self.assertEqual(self.bridge.budget.total, 0)
        self.assertIsNone(channel.parent_eof)

    async def test_cancellation_and_non_socket_exception_are_not_socket_failures(self):
        for index, injected in enumerate((asyncio.CancelledError(), ValueError('not an OS error')), 1):
            class Reader:
                async def read(self, count): raise injected
            channel = self.channel(Reader(), index=index)
            with self.assertRaises(type(injected)) as caught:
                await self.bridge.upload(channel)
            self.assertIs(caught.exception, injected)
            self.assertIsNone(channel.parent_eof); self.assertIsNone(channel.upload_drained)
        self.assertEqual(self.records(), [])
        self.assertEqual(self.bridge.budget.total, 0)
        self.assertTrue(self.bridge.outgoing.empty())

    async def test_actual_pending_read_cancellation_still_is_not_eof(self):
        channel = self.channel(asyncio.StreamReader())
        task = asyncio.create_task(self.bridge.upload(channel)); await asyncio.sleep(0)
        self.assertTrue(channel.upload_read_pending)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertEqual(self.records(), []); self.assertEqual(self.bridge.budget.total, 0)
        self.assertIsNone(channel.parent_eof); self.assertTrue(self.bridge.outgoing.empty())


class SocketAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_raw_adapter_reads_exact_requested_bound_and_has_one_pending_write(self):
        sock=SimpleNamespace(getpeername=lambda:('127.0.0.1',40000),getsockname=lambda:('127.0.0.1',32100),close=mock.Mock())
        loop=SimpleNamespace(sock_recv=mock.AsyncMock(return_value=b'abc'),sock_sendall=mock.AsyncMock())
        reader=bridge.SocketReader(sock);writer=bridge.SocketWriter(sock)
        with mock.patch.object(asyncio,'get_running_loop',return_value=loop):
            self.assertEqual(await reader.read(3),b'abc');loop.sock_recv.assert_awaited_once_with(sock,3)
            writer.write(b'abc')
            with self.assertRaises(ValueError):writer.write(b'more')
            await writer.drain();loop.sock_sendall.assert_awaited_once_with(sock,b'abc')
            self.assertIsNone(writer.pending)
        writer.close();await writer.wait_closed();sock.close.assert_called_once()


if __name__=='__main__':unittest.main()
