"""Ordering, actual loopback tail/EOF, and fail-closed pre-exit barriers."""
import asyncio
import copy
import json
from pathlib import Path
import socket
import threading
import time
import unittest
import zipfile
from unittest import mock
from urllib.parse import urlsplit

import codehost_bridge_v3 as bridge
import codehost_mux_protocol as mux
import native_exit_drain as subject
import native_quiescence as native
import test_codehost_bridge_v3 as fixture
import test_client_quiescence as clients

REAL_SERVER = bridge.create_server

def completion(request):
    return {'schema':subject.BRIDGE,'request':copy.deepcopy(request),'qualified':True,
            'channels':[1],'ledger_prefix':{'sequence':99,'sha256':'a'*64},
            'completed_monotonic_s':time.monotonic(),'completed_perf_counter_ns':time.perf_counter_ns()}

class NativeExitTests(unittest.TestCase):
    client = clients.QuiescenceTests.client

    def test_dev092_closes_stdin_without_waiting_for_transport(self):
        here=Path(__file__).resolve().parent
        archive=here.parents[2]/'Architecture Map/releases/RCI001-C02-dev-092/code.zip'
        name=(here/'native_quiescence.py').relative_to(here.parents[3]).as_posix()
        with zipfile.ZipFile(archive) as source:old=source.read(name)
        scope={'__name__':'retained_dev092_native_quiescence'}
        exec(compile(old,'retained-dev092:'+name,'exec'),scope)
        client,_=self.client();client.args.native_process_ready=object()
        calls=[]
        def unavailable(request):calls.append(request);raise TimeoutError('transport incomplete')
        client.args.native_exit_barrier=unavailable
        result=scope['Controller'](client,32*1024*1024).run()
        self.assertTrue(result['qualified']);self.assertTrue(client.process.closed)
        self.assertEqual(calls,[])

    def test_runtime_wiring_and_prospective_method_selection_are_explicit(self):
        here=Path(__file__).resolve().parent
        archive=here.parents[2]/'Architecture Map/releases/RCI001-C02-dev-092/code.zip'
        name=(here/'runtime.py').relative_to(here.parents[3]).as_posix()
        with zipfile.ZipFile(archive) as source:old=source.read(name).decode().replace('\r\n','\n')
        current=(here/'runtime.py').read_text(encoding='utf-8')
        addition='                args.native_exit_barrier=self.native_exit_barrier\n'
        selection='                args.native_process_drain=True\n'
        self.assertEqual(current.count(selection),1)
        self.assertEqual(current.count(addition),1)
        self.assertEqual(current.replace(addition,'').replace(selection,''),old)
        self.assertEqual(native.GRACEFUL_SECONDS,5);self.assertEqual(native.TOTAL_SECONDS,10)

    def test_stdin_stays_open_until_barrier_returns(self):
        client,root = self.client()
        entered,release = threading.Event(),threading.Event()
        client.args.native_process_ready = object()
        def barrier(request):
            entered.set()
            self.assertFalse(client.process.closed)
            self.assertTrue(client.args.client_finishing.is_set())
            if not release.wait(1): raise TimeoutError('test release missing')
            self.assertFalse(client.process.closed)
            return completion(request)
        client.args.native_exit_barrier=barrier
        result=[]
        worker=threading.Thread(target=lambda:result.append(client.close()))
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            self.assertFalse(client.process.closed)
        finally: release.set();worker.join(2)
        self.assertFalse(worker.is_alive());self.assertTrue(result[0]['qualified'],result[0]['failures'])
        proof=json.loads((root/'native-pre-exit-drain.json').read_text())
        order=json.loads((root/'native-shutdown-order.json').read_text())
        self.assertLessEqual(proof['received_perf_counter_ns'],order['stdin_close'][0]['begin_perf_counter_ns'])
        self.assertFalse(result[0]['forced_job_close'])

    def test_missing_faulted_stale_and_late_callback_fail_closed(self):
        for mode in ('missing','fault','stale','late','foreign','malformed'):
            with self.subTest(mode=mode):
                client,root=self.client();client.args.native_process_ready=object()
                def callback(request):
                    self.assertFalse(client.process.closed)
                    if mode=='fault': raise ConnectionAbortedError(1236,'synthetic private text')
                    value=completion(request)
                    if mode=='stale': value['completed_perf_counter_ns']=1
                    if mode=='late': value['completed_monotonic_s']=request['graceful_deadline_monotonic_s']
                    if mode=='foreign': value['request']['owner_receipt_sha256']='b'*64
                    if mode=='malformed': value['channels']=[True]
                    return value
                if mode!='missing':client.args.native_exit_barrier=callback
                result=client.close()
                self.assertFalse(result['qualified']);self.assertTrue(result['forced_job_close'])
                self.assertIn('transport_pre_exit_drain_failed',result['failures'])
                self.assertFalse((root/'native-pre-exit-drain.json').exists())
                self.assertNotIn('synthetic private text',(root/'native-quiescence.json').read_text())

    def test_eof_depending_on_process_exit_times_out_without_extending_deadline(self):
        client,root=self.client();client.args.native_process_ready=object()
        observed=[]
        def callback(request):
            observed.append(client.process.closed)
            client.process.done.wait(.15)
            return completion(request)
        client.args.native_exit_barrier=callback
        with mock.patch.object(native,'GRACEFUL_SECONDS',.12),mock.patch.object(native,'TOTAL_SECONDS',.28):
            result=client.close()
        self.assertEqual(observed,[False]);self.assertFalse(result['qualified'])
        self.assertTrue(result['forced_job_close'])
        self.assertAlmostEqual(result['hard_deadline_monotonic_s']-result['start_monotonic_s'],.28)

    def test_receipt_persistence_failure_forces_retirement(self):
        client,root=self.client();client.args.native_process_ready=object()
        client.args.native_exit_barrier=completion
        (root/'native-pre-exit-drain.json').write_text('retained prior bytes')
        result=client.close()
        self.assertFalse(result['qualified']);self.assertTrue(result['forced_job_close'])
        self.assertEqual((root/'native-pre-exit-drain.json').read_text(),'retained prior bytes')

class BridgeExitTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixture.BridgeTests.asyncSetUp
    mark_finish=fixture.BridgeTests.mark_finish
    run_bridge=fixture.BridgeTests.run_bridge
    client=fixture.BridgeTests.client

    async def prepare(self, count=1, short=None):
        for n in range(1,count+1):
            _,writer,_=self.client(n);await writer.received.wait()
        seed=fixture.cleanup_seed()
        if short is not None:seed['graceful_deadline_monotonic_s']=seed['start_monotonic_s']+short
        complete=await asyncio.to_thread(self.fixture.native_cleanup_barrier,seed)
        self.mark_finish(close_uploads=False)
        return subject.request_for(complete)

    async def test_two_channel_barrier_waits_for_every_genuine_eof(self):
        saved=[]
        async def body():
            request=await self.prepare(2)
            joined=asyncio.create_task(asyncio.to_thread(self.fixture.native_exit_barrier,request))
            await asyncio.shield(self.bridge.drain_ack)
            self.assertFalse(joined.done())
            self.client_readers[0].feed_eof();await asyncio.sleep(0)
            self.assertFalse(joined.done())
            self.client_readers[1].feed_eof()
            saved.append(await joined)
        receipt=await self.run_bridge(body)
        self.assertTrue(receipt['qualified']);self.assertEqual(saved[0]['channels'],[1,2])
        prefix=saved[0]['ledger_prefix']
        self.assertEqual(self.bridge.ledger.events[prefix['sequence']-1]['record_sha256'],prefix['sha256'])
        kinds=[r['kind'] for r in self.bridge.ledger.events[:prefix['sequence']]]
        self.assertEqual(kinds.count('client_eof'),2);self.assertEqual(kinds.count('channel_closed'),2)
        self.assertIn('namespace_finished',kinds)

    async def test_no_eof_fault_and_foreign_request_never_make_proof(self):
        request=[]
        async def body():
            request.append(await self.prepare(short=.15))
            with self.assertRaises((TimeoutError,ValueError)):
                await asyncio.to_thread(self.fixture.native_exit_barrier,request[0])
            self.assertFalse((self.folder/'codehost-pre-exit-drain.json').exists())
        await self.run_bridge(body,fail=True)
        self.assertTrue(self.bridge.failures)

    async def test_reset_is_not_eof(self):
        async def body():
            request=await self.prepare()
            self.client_readers[0].set_exception(ConnectionResetError(64,'fixture'))
            with self.assertRaises(ValueError):
                await asyncio.to_thread(self.fixture.native_exit_barrier,request)
        await self.run_bridge(body,fail=True)
        self.assertFalse((self.folder/'codehost-pre-exit-drain.json').exists())
        self.assertIsNone(self.bridge.channels[1].parent_eof)

    async def test_foreign_request_is_fatal(self):
        async def body():
            request=await self.prepare()
            request['owner_receipt_sha256']='d'*64
            with self.assertRaisesRegex(ValueError,'foreign'):
                await asyncio.to_thread(self.fixture.native_exit_barrier,request)
        await self.run_bridge(body,fail=True)
        self.assertFalse((self.folder/'codehost-pre-exit-drain.json').exists())

    async def test_existing_failure_is_not_recovered_by_barrier(self):
        async def body():
            request=await self.prepare();self.bridge.fail('synthetic_existing_failure')
            with self.assertRaisesRegex(ValueError,'unavailable'):
                await asyncio.to_thread(self.fixture.native_exit_barrier,request)
        await self.run_bridge(body,fail=True)
        self.assertFalse((self.folder/'codehost-pre-exit-drain.json').exists())

    async def test_duplicate_join_is_fatal(self):
        async def body():
            request=await self.prepare();self.client_readers[0].feed_eof()
            await asyncio.to_thread(self.fixture.native_exit_barrier,request)
            with self.assertRaisesRegex(ValueError,'duplicate'):
                await asyncio.to_thread(self.fixture.native_exit_barrier,request)
        await self.run_bridge(body,fail=True)

    async def test_byte_mismatch_cannot_create_proof(self):
        async def body():
            request=await self.prepare();self.client_readers[0].feed_eof()
            self.bridge.begin_finish();await self.bridge.drain_task;await self.bridge.finished
            await asyncio.gather(*list(self.bridge.handlers))
            self.bridge.channels[1].namespace_closed['upload']['bytes']+=1
            with self.assertRaisesRegex(ValueError,'byte mismatch'):
                await asyncio.to_thread(self.fixture.native_exit_barrier,request)
        await self.run_bridge(body,fail=True)
        self.assertFalse((self.folder/'codehost-pre-exit-drain.json').exists())

    async def test_real_socket_exact_tail_and_half_close_before_barrier(self):
        self.enterContext(mock.patch.object(bridge,'create_server',new=REAL_SERVER))
        payload=mux.PREFACE+fixture.h2(4)+fixture.h2(1,5,1,b'fixed-request-tail')
        expected=fixture.h2(4)+fixture.h2(1,5,1,b'\x88')
        async def body(url):
            self.fixture.native_process_ready(object(),'fake-native')
            peer=socket.socket();peer.setblocking(False)
            try:
                loop=asyncio.get_running_loop()
                await loop.sock_connect(peer,('127.0.0.1',urlsplit(url).port))
                await loop.sock_sendall(peer,payload)
                received=b''
                while len(received)<len(expected):received+=await loop.sock_recv(peer,4096)
                self.assertEqual(received,expected)
                complete=await asyncio.to_thread(self.fixture.native_cleanup_barrier,fixture.cleanup_seed())
                self.mark_finish(close_uploads=False)
                joined=asyncio.create_task(asyncio.to_thread(self.fixture.native_exit_barrier,subject.request_for(complete)))
                await asyncio.shield(self.bridge.drain_ack);self.assertFalse(joined.done())
                peer.shutdown(socket.SHUT_WR)
                proof=await joined
                self.assertEqual(proof['channels'],[1])
                self.assertEqual(await loop.sock_recv(peer,4096),b'')
                return 'socket-result'
            finally:peer.close();self.mark_finish()
        self.assertEqual(await asyncio.wait_for(self.bridge.run(body),5),'socket-result')
        channel=self.bridge.channels[1]
        self.assertEqual(channel.meters['client_read'].bytes,len(payload))
        self.assertEqual(channel.meters['client_written'].bytes,len(expected))
        self.assertEqual(channel.meters['client_read'].summary(),channel.meters['upload'].summary())

if __name__ == '__main__':unittest.main()
