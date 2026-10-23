import ast
import asyncio
import hashlib
import importlib.util
import io
from pathlib import Path
import threading
import json
import unittest
from unittest import mock

import codehost_inside_v3 as inside
import codehost_entry_v3 as entry
import codehost_mux_protocol as m
from test_codehost_mux_protocol import h2


class Writer:
    def __init__(self):self.data=bytearray();self.eof=False;self.closed=False;self.block=None
    def write(self,data):self.data.extend(data)
    async def drain(self):
        if self.block:await self.block.wait()
    def write_eof(self):self.eof=True
    def close(self):self.closed=True
    async def wait_closed(self):pass


class Child:
    pid=321
    code=None
    def poll(self):return self.code


class CleanupChild(Child):
    def __init__(self):self.code=None;self.terminations=0;self.kills=0
    def terminate(self):self.terminations+=1;self.code=-15
    def kill(self):self.kills+=1;self.code=-9
    def wait(self,timeout):return self.code


class RelayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.input=asyncio.StreamReader();self.output=Writer();self.events=[];self.hosts=[];self.child=Child()
        async def connect():
            reader,writer=asyncio.StreamReader(),Writer();self.hosts.append((reader,writer));return reader,writer
        metadata=inside.Metadata(io.StringIO())
        def emit(kind,**kw):
            row=metadata.emit(kind,**kw);self.events.append(row);return row
        self.relay=inside.Relay(self.input,self.output,emit,self.child,threading.Event(),connect)

    async def asyncTearDown(self):
        self.relay.drain_deadline=None  # Independent bounded cleanup after tested deadline expiry.
        for c in self.relay.channels.values():
            if not c.closed:await self.relay.close_channel(c,'error')

    async def ready(self,channel=1):
        await self.relay.accept(m.OPEN,channel,b'')
        await self.relay.accept(m.DATA,channel,m.PREFACE+h2(4))
        await self.relay.channels[channel].queue.join()
        self.hosts[channel-1][0].feed_data(h2(4))
        for _ in range(4):await asyncio.sleep(0)

    async def begin(self):
        await self.relay.accept(m.DRAIN_BEGIN,0,b'')

    def cleanup_payload(self):
        from test_codehost_bridge_v3 import cleanup_seed
        request=inside.cleanup.bind_request(cleanup_seed(),'a'*64)
        return inside.cleanup.canonical({'schema':'campaign002-native-cleanup-begin-1',
                                         'request':request,'parent_record_sha256':'c'*64})

    async def test_cleanup_ack_waits_for_old_upload_and_binds_actual_record(self):
        await self.ready();writer=self.hosts[0][1];writer.block=asyncio.Event()
        await self.relay.accept(m.DATA,1,h2(1,5,1,b'x'))
        payload=self.cleanup_payload()
        task=asyncio.create_task(self.relay.accept(m.CLEANUP_BEGIN,0,payload))
        for _ in range(5):await asyncio.sleep(0)
        self.assertFalse(task.done());self.assertIsNone(self.relay.cleanup_barrier)
        self.assertEqual(self.relay.channels[1].h2.summary()['cleanup_phase_nonce'],'b'*32)
        self.assertFalse(any(e['kind']=='native_cleanup_begin' for e in self.events))
        writer.block.set();await task
        record=next(e for e in self.events if e['kind']=='native_cleanup_begin')
        parser=m.FrameParser();frames=parser.feed(bytes(self.output.data));parser.finish()
        ack=m.metadata(next(payload for kind,_,payload in frames if kind==m.CLEANUP_ACK))
        self.assertEqual(ack['namespace_record'],record)
        self.assertEqual(record['channels'][0]['h2']['active_stream_ids'],[1])
        self.assertIsNone(record['channels'][0]['h2']['cleanup_phase_nonce'])
        await self.ready(2)
        inherited=next(e for e in self.events if e['kind']=='native_cleanup_channel')
        self.assertEqual(inherited['channel_id'],2);self.assertEqual(inherited['h2']['last_stream_id'],0)
        opened=next(e for e in self.events if e['kind']=='frame' and e.get('frame_type')==m.OPENED and e.get('channel_id')==2)
        self.assertLess(inherited['sequence'],opened['sequence'])

    async def test_cleanup_duplicate_noncanonical_and_after_retirement_rejected(self):
        payload=self.cleanup_payload()
        with self.assertRaises(ValueError):await self.relay.accept(m.CLEANUP_BEGIN,0,b' '+payload)
        self.assertIsNone(self.relay.cleanup_request)
        await self.relay.accept(m.CLEANUP_BEGIN,0,payload)
        with self.assertRaises(ValueError):await self.relay.accept(m.CLEANUP_BEGIN,0,payload)
        await self.begin()
        with self.assertRaises(ValueError):await self.relay.accept(m.CLEANUP_BEGIN,0,payload)

    async def test_cleanup_half_close_before_begin_does_not_enroll_live_download(self):
        await self.ready();await self.relay.accept(m.HALF_CLOSE,1,b'')
        channel=self.relay.channels[1]
        self.assertFalse(channel.closed);self.assertTrue(channel.half_closed)
        await self.relay.accept(m.CLEANUP_BEGIN,0,self.cleanup_payload())
        record=next(e for e in self.events if e['kind']=='native_cleanup_begin')
        self.assertTrue(record['channels'][0]['upload_eof'])
        self.assertFalse(record['channels'][0]['already_closed'])
        self.assertIsNone(channel.h2.summary()['cleanup_phase_nonce'])
        with self.assertRaises(ValueError):await self.relay.accept(m.DATA,1,h2(3,0,1,(8).to_bytes(4,'big')))
        self.hosts[0][0].feed_eof()
        for _ in range(15):await asyncio.sleep(0)
        self.assertTrue(channel.closed);self.assertIsNone(self.relay.failure)

    async def test_cleanup_upload_cancel_and_trailing_download_are_forwarded(self):
        await self.ready();request=h2(1,5,1,b'x')
        await self.relay.accept(m.DATA,1,request)
        await self.relay.accept(m.CLEANUP_BEGIN,0,self.cleanup_payload())
        cancel=h2(3,0,1,(8).to_bytes(4,'big'))
        await self.relay.accept(m.DATA,1,cancel)
        self.hosts[0][0].feed_data(h2(1,5,1,b'late'))
        for _ in range(8):await asyncio.sleep(0)
        await self.begin();await self.seal();await self.relay.close_channel(self.relay.channels[1],'owner_finish')
        row=[e['receipt'] for e in self.events if e['kind']=='channel_closed'][-1]
        self.assertTrue(row['qualified']);self.assertEqual(row['h2']['reset_streams'],1)
        self.assertEqual(len(row['h2']['cleanup_cancel_records']),1)
        self.assertEqual(bytes(self.hosts[0][1].data),m.PREFACE+h2(4)+request+cancel)

    async def test_cleanup_timeout_cannot_ack_or_complete(self):
        await self.ready();self.hosts[0][1].block=asyncio.Event()
        await self.relay.accept(m.DATA,1,h2(1,5,1,b'x'))
        value=json.loads(self.cleanup_payload())
        value['request']['graceful_deadline_monotonic_s']=value['request']['start_monotonic_s']+.01
        with self.assertRaises(TimeoutError):
            await self.relay.accept(m.CLEANUP_BEGIN,0,m.canonical(value))
        self.assertIsNone(self.relay.cleanup_barrier)
        self.assertFalse(any(e['kind']=='native_cleanup_begin' for e in self.events))
        self.hosts[0][1].block.set()

    async def seal(self):
        for c in self.relay.channels.values():
            if not c.half_closed:await self.relay.accept(m.HALF_CLOSE,c.id,b'')
            await c.queue.join()
            if not c.download_eof:self.hosts[c.id-1][0].feed_eof()
        for _ in range(8):await asyncio.sleep(0)
        await self.relay.accept(m.FINISH,0,b'')

    async def test_two_channels_one_child_exact_byte_isolation(self):
        await self.ready(1);await self.ready(2)
        for channel,raw in ((1,b'one'),(2,b'two')):
            await self.relay.accept(m.DATA,channel,h2(1,5,1,raw))
            await self.relay.channels[channel].queue.join()
            self.hosts[channel-1][0].feed_data(h2(1,5,1,raw))
        for _ in range(6):await asyncio.sleep(0)
        await self.begin();await self.seal()
        for c in self.relay.channels.values():await self.relay.close_channel(c,'owner_finish')
        rows=[x['receipt'] for x in self.events if x['kind']=='channel_closed']
        self.assertEqual(len(rows),2);self.assertTrue(all(x['qualified'] for x in rows))
        for channel,row in enumerate(rows,1):
            raw=bytes(self.hosts[channel-1][1].data)
            self.assertEqual(row['upload'],{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
        self.assertEqual({x['child_pid'] for x in self.events if x['kind']=='channel_open'},{321})
        self.assertNotEqual(self.hosts[0][1].data,self.hosts[1][1].data)
        self.assertEqual(self.relay.budget.total,0)

    async def test_clean_idle_channel_eof_does_not_finish_owner(self):
        await self.ready();await self.relay.accept(m.HALF_CLOSE,1,b'');self.hosts[0][0].feed_eof()
        for _ in range(15):await asyncio.sleep(0)
        self.assertTrue(self.relay.channels[1].closed);self.assertFalse(self.relay.finishing)
        self.assertIsNone(self.relay.failure)
        await self.relay.accept(m.OPEN,2,b'')
        self.assertEqual(len(self.hosts),2)

    async def test_inflight_eof_fails_before_eventual_finish(self):
        await self.ready();await self.relay.accept(m.DATA,1,h2(1,5,1,b'x'))
        self.hosts[0][0].feed_eof()
        for _ in range(8):await asyncio.sleep(0)
        self.assertIsNotNone(self.relay.failure)
        await self.relay.close_channel(self.relay.channels[1],'error')
        self.assertFalse([x['receipt'] for x in self.events if x['kind']=='channel_closed'][-1]['qualified'])

    async def test_data_before_open_duplicate_and_halfclose(self):
        with self.assertRaises(ValueError):await self.relay.accept(m.DATA,1,b'x')
        await self.ready()
        with self.assertRaises(ValueError):await self.relay.accept(m.OPEN,1,b'')
        await self.relay.accept(m.HALF_CLOSE,1,b'')
        with self.assertRaises(ValueError):await self.relay.accept(m.DATA,1,b'x')
        with self.assertRaises(ValueError):await self.relay.accept(m.HALF_CLOSE,1,b'')

    async def test_queue_overflow_no_drop(self):
        await self.ready();c=self.relay.channels[1]
        self.hosts[0][1].block=asyncio.Event()
        # Valid H2 upload data on an open request, bounded payload frame chunks.
        await self.relay.accept(m.DATA,1,h2(1,4,1,b'x'))
        wire=h2(0,0,1,b'x'*16384)
        with self.assertRaises(ValueError):
            for _ in range(80):await self.relay.accept(m.DATA,1,wire)
        self.assertLessEqual(self.relay.budget.total,m.PER_CHANNEL_QUEUE_BYTES)

    async def test_cancel_after_drain_only_and_original_stream(self):
        await self.ready();await self.relay.accept(m.DATA,1,h2(1,5,1,b'x'))
        await self.relay.channels[1].queue.join()
        await self.begin()
        self.hosts[0][0].feed_data(h2(3,0,1,(8).to_bytes(4,'big')))
        for _ in range(6):await asyncio.sleep(0)
        await self.seal()
        await self.relay.close_channel(self.relay.channels[1],'owner_finish')
        row=[x['receipt'] for x in self.events if x['kind']=='channel_closed'][-1]
        self.assertTrue(row['qualified']);self.assertEqual(row['finish_frontier']['active_stream_ids'],[1])

    async def test_prefinish_reset_cannot_be_excused(self):
        await self.ready();await self.relay.accept(m.DATA,1,h2(1,5,1,b'x'))
        self.hosts[0][0].feed_data(h2(3,0,1,(8).to_bytes(4,'big')))
        for _ in range(6):await asyncio.sleep(0)
        with self.assertRaises(ValueError):await self.begin()

    async def test_owner_eof_and_child_failure_terminal_fail_closed(self):
        self.input.feed_eof();result=await self.relay.run()
        self.assertFalse(result['owner_finish_received']);self.assertIsNotNone(result['error_type'])

    async def test_framed_finish_complete_handshake(self):
        self.input.feed_data(m.encode_frame(m.DRAIN_BEGIN,0)+m.encode_frame(m.FINISH,0))
        self.input.feed_eof()
        result=await self.relay.run()
        self.assertTrue(result['owner_finish_received']);self.assertEqual(result['channels_closed'],0)
        self.assertTrue(result['drain_qualified'])
        self.assertEqual(result['queue_bytes_at_close'],0)
        p=m.FrameParser();frames=p.feed(bytes(self.output.data));p.finish()
        self.assertEqual([x[0] for x in frames],[m.DRAIN_ACK])

    async def test_child_failure_without_parent_input_is_observed(self):
        self.child.code=7
        result=await asyncio.wait_for(self.relay.run(),1)
        self.assertEqual(result['error_type'],'ChildOrDiagnosticFailure')

    async def test_trailing_finish_partial_tail_and_missing_eof_fail(self):
        for suffix in (m.encode_frame(m.FINISH,0),b'R'):
            reader=asyncio.StreamReader();reader.feed_data(m.encode_frame(m.DRAIN_BEGIN,0)+m.encode_frame(m.FINISH,0)+suffix);reader.feed_eof()
            relay=inside.Relay(reader,Writer(),lambda *a,**k:None,self.child,threading.Event())
            result=await relay.run()
            self.assertIsNotNone(result['error_type']);self.assertFalse(result['stdin_eof'])

    async def test_partial_host_frame_at_finish_is_unqualified(self):
        await self.ready();self.hosts[0][0].feed_data(b'\x00\x00')
        for _ in range(4):await asyncio.sleep(0)
        await self.begin();await self.seal();await self.relay.close_channel(self.relay.channels[1],'owner_finish')
        self.assertIsNotNone(self.relay.failure)

    async def test_non_cancel_reset_after_drain_is_unqualified(self):
        await self.ready();await self.relay.accept(m.DATA,1,h2(1,5,1,b'x'))
        await self.begin()
        self.hosts[0][0].feed_data(h2(3,0,1,(2).to_bytes(4,'big')))
        for _ in range(6):await asyncio.sleep(0)
        await self.relay.close_channel(self.relay.channels[1],'error')
        self.assertIsNotNone(self.relay.failure)

    async def test_connect_failure_is_not_retried(self):
        count=[]
        async def broken():count.append(1);raise OSError('synthetic')
        self.relay.connect=broken
        with self.assertRaises(OSError):await self.relay.accept(m.OPEN,1,b'')
        self.assertEqual(count,[1]);self.assertEqual(self.hosts,[])

    async def test_finish_requires_drain_ack_and_genuine_upload_eof(self):
        await self.ready()
        with self.assertRaises(ValueError):await self.relay.accept(m.FINISH,0,b'')
        await self.begin()
        with self.assertRaises(ValueError):await self.relay.accept(m.FINISH,0,b'')
        self.assertFalse(self.relay.finishing)
        with self.assertRaises(ValueError):await self.relay.accept(m.OPEN,2,b'')

    async def test_drain_ack_waits_for_existing_upload_bytes(self):
        await self.ready();writer=self.hosts[0][1];writer.block=asyncio.Event()
        await self.relay.accept(m.DATA,1,h2(1,5,1,b'x'))
        pending=asyncio.create_task(self.begin())
        for _ in range(5):await asyncio.sleep(0)
        self.assertFalse(pending.done());self.assertFalse(self.relay.drain_acknowledged)
        writer.block.set();await pending
        self.assertTrue(self.relay.drain_acknowledged)
        self.assertEqual(self.relay.channels[1].finish_frontier['active_stream_ids'],[1])

    async def test_shutdown_upload_after_drain_is_forwarded_exactly(self):
        await self.ready();request=h2(1,5,1,b'x');await self.relay.accept(m.DATA,1,request)
        await self.begin();front=__import__('copy').deepcopy(self.relay.channels[1].finish_frontier)
        cancel=h2(3,0,1,(8).to_bytes(4,'big'))
        for part in (cancel[:5],cancel[5:]):await self.relay.accept(m.DATA,1,part)
        await self.seal();await self.relay.close_channel(self.relay.channels[1],'owner_finish')
        row=[e['receipt'] for e in self.events if e['kind']=='channel_closed'][-1]
        self.assertTrue(row['qualified']);self.assertEqual(row['finish_frontier'],front)
        self.assertEqual(bytes(self.hosts[0][1].data),m.PREFACE+h2(4)+request+cancel)
        self.assertEqual(row['seal_frontier']['last_stream_id'],front['last_stream_id'])
        self.assertFalse(front['retiring']);self.assertTrue(row['h2']['retiring'])
        self.assertTrue(row['upload_eof'] and row['upload_drained'] and row['download_eof'])

    async def test_new_stream_after_drain_is_rejected_before_forwarding(self):
        await self.ready();await self.begin();before=bytes(self.hosts[0][1].data)
        with self.assertRaises(ValueError):await self.relay.accept(m.DATA,1,h2(1,5,1,b'x'))
        self.assertEqual(bytes(self.hosts[0][1].data),before)

    async def test_partial_upload_eof_is_retained_before_strict_rejection(self):
        await self.ready();await self.relay.accept(m.DATA,1,b'\x00\x00')
        with self.assertRaises(ValueError):await self.relay.accept(m.HALF_CLOSE,1,b'')
        channel=self.relay.channels[1]
        self.assertTrue(channel.half_closed);self.assertFalse(channel.upload_eof_h2['frames_complete'])
        eof=[e for e in self.events if e['kind']=='channel_eof' and e['direction']=='upload']
        self.assertEqual(len(eof),1);self.assertFalse(eof[0]['owner_finishing'])
        await channel.queue.join();self.assertTrue(channel.upload_drained)

    async def test_final_close_waits_for_real_host_eof(self):
        await self.ready();await self.begin();await self.relay.accept(m.HALF_CLOSE,1,b'')
        self.input.feed_data(m.encode_frame(m.FINISH,0));self.input.feed_eof()
        running=asyncio.create_task(self.relay.run())
        for _ in range(8):await asyncio.sleep(0)
        self.assertFalse(running.done());self.assertFalse(self.relay.channels[1].closed)
        self.hosts[0][0].feed_eof();result=await asyncio.wait_for(running,1)
        self.assertTrue(result['drain_qualified']);self.assertEqual(result['queue_bytes_at_close'],0)

    async def test_shared_deadline_does_not_restart_at_seal(self):
        await self.ready()
        await self.begin();deadline=self.relay.drain_deadline
        self.assertTrue(self.relay.drain_acknowledged)
        await self.relay.accept(m.HALF_CLOSE,1,b'')
        await self.relay.channels[1].queue.join()
        self.assertTrue(self.relay.channels[1].upload_drained)
        # Exercise the actual FINISH path with an expired original deadline;
        # do not make BEGIN/ACK depend on sub-tick Windows scheduling.
        loop=asyncio.get_running_loop()
        with mock.patch.object(loop,'time',return_value=deadline+1):
            with self.assertRaises(TimeoutError):await self.relay.accept(m.FINISH,0,b'')
        self.assertEqual(self.relay.drain_deadline,deadline);self.assertFalse(self.relay.finishing)

    async def test_missing_ack_delivery_fails_closed(self):
        self.output.block=asyncio.Event()
        with mock.patch.object(m,'OWNER_DRAIN_TIMEOUT',.01):
            with self.assertRaises(TimeoutError):await self.begin()
        self.assertFalse(self.relay.drain_acknowledged);self.assertFalse(self.relay.finishing)
        self.output.block.set()


class ParityTests(unittest.TestCase):
    def test_fixed_gateway_ast_is_identical_to_v2(self):
        here=Path(inside.__file__).parent
        def classes(path):
            tree=ast.parse(path.read_text());return {n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,ast.ClassDef)}
        old,new=classes(here/'codehost_inside_v2.py'),classes(here/'codehost_inside_v3.py')
        for name in ('Handler','BoundedHTTPServer'):self.assertEqual(old[name],new[name])

    def test_entry_changes_only_inside_and_fixed_readonly_helper(self):
        original=['bwrap','--unshare-all','--ro-bind','old','/inside.py','--die-with-parent',
                  '--remount-ro','/','/usr/bin/python3','-I','-B','/inside.py']
        actual=entry.replace_inside(original,'old','new','helper')
        restored=list(actual);index=restored.index('/codehost_mux_protocol.py');del restored[index-2:index+1]
        restored[restored.index('new')]='old';self.assertEqual(restored,original)
        for bad in (original+['x'],['bwrap']):
            with self.assertRaises(ValueError):entry.replace_inside(bad,'old','new','helper')

    def test_actual_namespace_adds_helper_before_root_remount_preserving_every_argument(self):
        spec=importlib.util.spec_from_file_location('startup_namespace_fixture',entry.BOUNDARY/'namespace.py')
        namespace=importlib.util.module_from_spec(spec);spec.loader.exec_module(namespace)
        original=namespace.command('/runtime/workspace','/runtime/gateway.sock',entry.BOUNDARY,
                                   '/fixed/codex','/fixed/codehost')
        before=list(original)
        actual=entry.replace_inside(original,entry.BOUNDARY/'inside.py','/fixed/inside-v3.py','/fixed/mux.py')
        target=actual.index('/codehost_mux_protocol.py');remount=actual.index('--remount-ro')
        self.assertLess(target,remount)
        self.assertEqual(actual[target-2:target+1],['--ro-bind','/fixed/mux.py','/codehost_mux_protocol.py'])
        self.assertEqual(actual[remount:],['--remount-ro','/','/usr/bin/python3','-I','-B','/inside.py'])
        self.assertTrue(all(i<remount for i,value in enumerate(actual) if value in ('--bind','--ro-bind')))
        restored=list(actual);del restored[target-2:target+1]
        restored[restored.index('/fixed/inside-v3.py')]=str(entry.BOUNDARY/'inside.py')
        self.assertEqual(restored,before);self.assertEqual(original,before)

    def test_missing_duplicate_or_nonterminal_root_remount_is_rejected(self):
        prefix=['bwrap','--ro-bind','old','/inside.py']
        tail=['/usr/bin/python3','-I','-B','/inside.py']
        for middle in ([],['--remount-ro','/','--remount-ro','/'],
                       ['--remount-ro','/','--ro-bind','another','/another'],['--remount-ro','/workspace']):
            original=prefix+middle+tail;before=list(original)
            with self.assertRaises(ValueError):entry.replace_inside(original,'old','new','helper')
            self.assertEqual(original,before)

    def test_source_keys_and_metadata_namespace_schema(self):
        self.assertEqual(set(inside.sources()),{'codehost_inside_v3.py','codehost_mux_protocol.py','native_cleanup_protocol.py'})
        stream=io.StringIO();meta=inside.Metadata(stream)
        value=meta.emit('ready',receipt={'schema':'different'})
        self.assertEqual(value['schema'],'campaign002-codehost-namespace-3')
        with mock.patch.object(inside,'MAX_METADATA_BYTES',1):
            with self.assertRaises(RuntimeError):meta.emit('more')


class OwnerLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_finish_handshake_binds_actual_child_cleanup(self):
        child=CleanupChild();reader=asyncio.StreamReader();writer=Writer()
        reader.feed_data(m.encode_frame(m.DRAIN_BEGIN,0)+m.encode_frame(m.FINISH,0));reader.feed_eof()
        stream=io.StringIO();meta=inside.Metadata(stream);failed=threading.Event();ready=threading.Event();ready.set()
        meta.emit('open');meta.emit('child_started',child_pid=child.pid)
        async def streams():return reader,writer
        def diagnostics():
            for name in ('stdout','stderr'):meta.emit('child_diagnostic',stream=name,bytes=0,sha256=hashlib.sha256(b'').hexdigest(),truncated=False)
            return True
        with mock.patch.object(inside,'stdio_streams',streams):
            result=await inside.operate(child,meta,failed,ready,diagnostics)
        self.assertIs(type(result),int);self.assertEqual(result,0)
        self.assertEqual(child.terminations,1);self.assertEqual(child.kills,0)
        parser=m.FrameParser();frames=parser.feed(bytes(writer.data));parser.finish()
        self.assertEqual([x[0] for x in frames],[m.READY,m.DRAIN_ACK,m.FINISHED])
        rows=[__import__('json').loads(s[len(inside.PREFIX):]) for s in stream.getvalue().splitlines()]
        self.assertEqual(m.metadata(frames[-1][2]),rows[-1]);self.assertTrue(rows[-1]['qualified'])
        self.assertTrue(all(x['schema']=='campaign002-codehost-namespace-3' for x in rows))

    async def test_partial_startup_failure_still_terminates_child(self):
        child=CleanupChild();meta=inside.Metadata(io.StringIO())
        class NotReady:
            def wait(self,timeout):return False
        result=await inside.operate(child,meta,threading.Event(),NotReady(),lambda:True)
        self.assertEqual(result,1);self.assertEqual(child.terminations,1);self.assertEqual(child.kills,0)

    async def test_diagnostic_failure_prevents_success(self):
        child=CleanupChild();meta=inside.Metadata(io.StringIO());failed=threading.Event();failed.set();ready=threading.Event();ready.set()
        result=await inside.operate(child,meta,failed,ready,lambda:False)
        self.assertEqual(result,1);self.assertEqual(child.terminations,1)


if __name__ == '__main__':unittest.main()
