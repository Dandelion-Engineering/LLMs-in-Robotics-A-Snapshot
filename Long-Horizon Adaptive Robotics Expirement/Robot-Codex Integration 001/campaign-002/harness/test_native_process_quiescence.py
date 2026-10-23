"""No-model candidate integration and adversarial boundary controls."""
import asyncio
import copy
import json
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import native_process_quiescence as native
import process_drain as subject
import test_client_quiescence as clients
import test_codehost_bridge_v3 as fixtures

def complete(request):
    return {'schema': subject.BRIDGE, 'request': copy.deepcopy(request), 'qualified': True,
            'channels': [], 'frontiers': [], 'ledger_prefix': {'sequence': 1, 'sha256': 'a'*64},
            'completed_monotonic_s': time.monotonic(), 'completed_perf_counter_ns': time.perf_counter_ns()}

class ControllerTests(unittest.TestCase):
    client = clients.QuiescenceTests.client

    def close(self, client, short=False):
        with mock.patch.object(native, 'GRACEFUL_SECONDS', .15 if short else 5), \
             mock.patch.object(native, 'TOTAL_SECONDS', .3 if short else 10):
            client.args.native_process_drain = True
            return client.close()


    def test_production_implementation_matches_diagnostic(self):
        candidate = HERE.parent/'io-repair/graceful-process-drain-001'
        self.assertEqual((HERE/'native_process_quiescence.py').read_bytes(), (candidate/'candidate_native.py').read_bytes())
        self.assertEqual((HERE/'process_drain.py').read_bytes(), (candidate/'process_drain.py').read_bytes())
        self.assertEqual(native.GRACEFUL_SECONDS, 5); self.assertEqual(native.TOTAL_SECONDS, 10)

    def test_selection_is_boolean_and_legacy_default_is_retained(self):
        client, _ = self.client(); client.args.native_process_drain = 'true'
        with self.assertRaises(RuntimeError): client.close()
        self.assertFalse(client.cleanup_started)
        client.args.native_process_drain = False
        self.assertTrue(client.close()['qualified'])

    def test_normal_order_and_hash_binding(self):
        client, root = self.client()
        client.args.native_process_ready = object()
        calls = []
        def callback(request):
            calls.append(request)
            self.assertEqual(client.process.closed, request['phase'] == 'finish')
            return complete(request)
        client.args.native_exit_barrier = callback
        result = self.close(client)
        self.assertTrue(result['qualified'], result)
        self.assertFalse(result['forced_job_close'])
        self.assertEqual([r['phase'] for r in calls], ['prepare', 'finish'])
        prepared = json.loads((root/'native-process-prepare.json').read_text())
        finished = json.loads((root/'native-process-finish.json').read_text())
        order = json.loads((root/'native-shutdown-order.json').read_text())
        self.assertEqual(calls[1]['prepare_sha256'], subject.cleanup.sha(subject.cleanup.canonical(prepared['bridge'])))
        self.assertLessEqual(prepared['received_perf_counter_ns'], order['stdin_close'][0]['begin_perf_counter_ns'])
        self.assertLessEqual(order['stdin_close'][0]['end_perf_counter_ns'], finished['begin_perf_counter_ns'])
        self.assertFalse((root/'native-pre-exit-drain.json').exists())

    def test_invalid_prepare_never_permits_ordinary_stdin_close(self):
        for mode in ('missing', 'raises', 'stale', 'late', 'foreign', 'malformed', 'persist'):
            with self.subTest(mode=mode):
                client, root = self.client(); client.args.native_process_ready = object()
                calls = []
                def callback(request):
                    calls.append(request['phase']); self.assertFalse(client.process.closed)
                    if mode == 'raises': raise ConnectionResetError('private fixture')
                    value = complete(request)
                    if mode == 'stale': value['completed_perf_counter_ns'] = 1
                    if mode == 'late': value['completed_monotonic_s'] = request['graceful_deadline_monotonic_s']
                    if mode == 'foreign': value['request']['owner_receipt_sha256'] = 'b'*64
                    if mode == 'malformed': value['channels'] = [True]
                    return value
                if mode != 'missing': client.args.native_exit_barrier = callback
                if mode == 'persist': (root/'native-process-prepare.json').write_text('old bytes')
                result = self.close(client)
                self.assertFalse(result['qualified']); self.assertTrue(result['forced_job_close'])
                self.assertIn('transport_process_prepare_failed', result['failures'])
                self.assertNotIn('finish', calls)
                self.assertFalse((root/'native-process-finish.json').exists())

    def test_missing_reset_late_foreign_finish_nonzero_and_deadlines_fail(self):
        for mode in ('raises', 'late', 'foreign', 'stall', 'nonzero', 'hang_exit', 'block_close', 'persist'):
            with self.subTest(mode=mode):
                client, root = self.client(); client.args.native_process_ready = object()
                def callback(request):
                    value = complete(request)
                    if request['phase'] == 'finish':
                        if mode == 'raises': raise ConnectionAbortedError('private fixture')
                        if mode == 'late': value['completed_monotonic_s'] = request['graceful_deadline_monotonic_s']
                        if mode == 'foreign': value['request']['prepare_sha256'] = 'f'*64
                        if mode == 'stall': time.sleep(.2)
                    return value
                client.args.native_exit_barrier = callback
                if mode == 'nonzero':
                    def close():
                        client.process.closed = True; client.process.returncode = 7; client.process.done.set()
                    client.process.close = close
                if mode in ('hang_exit', 'block_close'): setattr(client.process, mode, True)
                if mode == 'persist': (root/'native-process-finish.json').write_text('old bytes')
                begin = time.monotonic(); result = self.close(client, short=True)
                self.assertFalse(result['qualified'], result)
                self.assertLess(time.monotonic()-begin, .7)
                self.assertAlmostEqual(result['hard_deadline_monotonic_s']-result['start_monotonic_s'], .3)

class BridgeTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.BridgeTests.asyncSetUp
    mark_finish = fixtures.BridgeTests.mark_finish
    run_bridge = fixtures.BridgeTests.run_bridge
    client = fixtures.BridgeTests.client

    async def prepare(self, count=1, short=None):
        for n in range(1, count+1):
            _, writer, _ = self.client(n); await writer.received.wait()
        seed = fixtures.cleanup_seed()
        if short: seed['graceful_deadline_monotonic_s'] = seed['start_monotonic_s']+short
        complete = await asyncio.to_thread(self.fixture.native_cleanup_barrier, seed)
        self.mark_finish(close_uploads=False)
        # run() bound the original method before entering this test callback.
        self.fixture.native_exit_barrier = self.bridge.native_exit_barrier
        request = subject.request_for(complete, 'prepare')
        value = await asyncio.to_thread(self.fixture.native_exit_barrier, request)
        return subject.request_for(complete, 'finish', subject.cleanup.sha(subject.cleanup.canonical(value)))

    async def test_two_channels_prepare_without_eof_then_require_every_eof(self):
        async def body():
            request = await self.prepare(2)
            self.assertTrue(all(c.parent_eof is None for c in self.bridge.channels.values()))
            task = asyncio.create_task(asyncio.to_thread(self.fixture.native_exit_barrier, request))
            await asyncio.sleep(.01); self.assertFalse(task.done())
            self.client_readers[0].feed_eof(); await asyncio.sleep(.01); self.assertFalse(task.done())
            self.client_readers[1].feed_eof()
            result = await task
            self.assertEqual(result['channels'], [1, 2])
            prefix = result['ledger_prefix']
            self.assertEqual(self.bridge.ledger.events[prefix['sequence']-1]['record_sha256'], prefix['sha256'])
            kinds = [r['kind'] for r in self.bridge.ledger.events[:prefix['sequence']]]
            self.assertEqual(kinds.count('client_eof'), 2)
            self.assertIn('namespace_finished', kinds)
        receipt = await self.run_bridge(body)
        self.assertTrue(receipt['qualified'])
        self.assertFalse((self.folder/'codehost-pre-exit-drain.json').exists())

    async def test_missing_eof_has_no_final_proof(self):
        async def body():
            request = await self.prepare(short=.12)
            with self.assertRaises((ValueError, TimeoutError)):
                await asyncio.to_thread(self.fixture.native_exit_barrier, request)
            self.assertFalse((self.folder/'codehost-process-finish.json').exists())
        await self.run_bridge(body, fail=True)

    async def test_reset_is_not_eof(self):
        async def body():
            request = await self.prepare()
            self.client_readers[0].set_exception(ConnectionResetError(64, 'fixture'))
            with self.assertRaises((ValueError, ConnectionResetError)):
                await asyncio.to_thread(self.fixture.native_exit_barrier, request)
        await self.run_bridge(body, fail=True)
        self.assertIsNone(self.bridge.channels[1].parent_eof)
        self.assertFalse((self.folder/'codehost-process-finish.json').exists())

    async def test_foreign_prepare_hash_fails(self):
        async def body():
            request = await self.prepare(); request['prepare_sha256'] = 'd'*64
            with self.assertRaisesRegex(ValueError, 'foreign'):
                await asyncio.to_thread(self.fixture.native_exit_barrier, request)
        await self.run_bridge(body, fail=True)

    async def test_duplicate_prepare_fails(self):
        async def body():
            await self.prepare()
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                await asyncio.to_thread(self.fixture.native_exit_barrier,
                                        subject.request_for(self.bridge.cleanup_complete, 'prepare'))
        await self.run_bridge(body, fail=True)

    async def test_byte_mismatch_cannot_create_final_proof(self):
        async def body():
            request = await self.prepare(); self.client_readers[0].feed_eof()
            await self.bridge.drain_task; await self.bridge.finished
            await asyncio.gather(*list(self.bridge.handlers))
            self.bridge.channels[1].namespace_closed['upload']['bytes'] += 1
            with self.assertRaisesRegex(ValueError, 'byte mismatch'):
                await asyncio.to_thread(self.fixture.native_exit_barrier, request)
        await self.run_bridge(body, fail=True)

    async def test_full_controller_and_bridge_integration(self):
        async def body():
            reader, writer, _ = self.client(); await writer.received.wait()
            client, _ = clients.QuiescenceTests.client(self)
            client.events.close()
            root = self.folder/'client'; root.mkdir()
            client.args.evidence = root
            client.events = (root/'events.jsonl').open('x', encoding='utf-8')
            client.args.abort_event = self.fixture.abort_event
            client.args.client_finishing = self.fixture.client_finishing
            client.args.native_process_ready = object()
            client.args.native_cleanup_barrier = self.fixture.native_cleanup_barrier
            client.args.native_exit_barrier = self.fixture.native_exit_barrier
            original = client.process.close
            def close():
                original()
                self.bridge.loop.call_soon_threadsafe(reader.feed_eof)
            client.process.close = close
            result = await asyncio.to_thread(native.close, client, 32*1024*1024)
            self.assertTrue(result['qualified'], result)
            self.assertFalse(result['forced_job_close'])
            self.assertTrue((root/'native-process-finish.json').is_file())
        receipt = await self.run_bridge(body)
        self.assertTrue(receipt['qualified'])

if __name__ == '__main__': unittest.main()
