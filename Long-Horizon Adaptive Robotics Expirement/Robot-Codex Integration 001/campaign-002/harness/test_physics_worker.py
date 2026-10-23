"""Bounded fake-driver tests; no native simulator, model or durable workload."""
from __future__ import annotations

import threading
import time
import unittest
from contextlib import nullcontext

from physics_worker import ContinuousPhysics, PhysicsWorkerError, RPCRejected, RPCUnknown


class Capture:
    def __init__(self):
        self.origin = time.perf_counter()
        self.terminal = None
        self.rows = []
        self.threads = []

    def sample(self, sim):
        self.rows.append((time.perf_counter() - self.origin, sim))
        self.threads.append(threading.get_ident())

    def finish(self, sim, reason):
        self.sample(sim)
        self.terminal = dict(reason=reason, sim=sim, wall=self.rows[-1][0])

    def phase(self, name, sim_clock):
        return nullcontext()


class Memory:
    def __init__(self):
        self.calls = []
        self.finished = False

    def start(self, origin): self.calls.append(('start', threading.get_ident()))
    def poll(self): self.calls.append(('poll', threading.get_ident())); return True
    def finish(self): self.calls.append(('finish', threading.get_ident())); self.finished = True


class Collector:
    def __init__(self): self.threads = []
    def verify_deferred(self, *, full=False): self.threads.append(threading.get_ident())


class Driver:
    def __init__(self, owner, log, *, emit=False):
        self.owner, self.log, self.emit = owner, log, emit
        self.now = 1.
        self.epoch = 1
        self.dispatched = []
        self.record('initialize')
        owner.publish_snapshot({'time': self.now, 'nested': {'value': [1]}})

    def record(self, operation): self.log.append((operation, threading.get_ident(), self.now))

    def tick(self):
        self.now += .002
        self.record('tick')
        if self.emit: self.owner.publish('motion', {'sim': self.now, 'values': [1, 2]})
        self.owner.publish_snapshot({'time': self.now, 'nested': {'value': [1]}})

    def cancel(self, reason): self.record('cancel:' + reason)
    def close(self): self.record('close')
    def echo(self, value): self.record('echo'); return value
    def fail(self): raise RuntimeError('injected driver failure')
    def reject(self): raise RPCRejected('injected known rejection')
    def submit(self, request):
        if request['epoch'] != self.epoch: raise RPCRejected('stale authority')
        if self.now - request['capture'] > .35: raise RPCRejected('stale observation')
        self.dispatched.append(request['id'])
        self.record('dispatch:' + request['id'])
        return {'accepted': True, 'id': request['id']}


class PhysicsWorkerTests(unittest.TestCase):
    def make(self, *, driver_cls=Driver, emit=False, **kwargs):
        self.log = []
        worker = ContinuousPhysics(lambda owner: driver_cls(owner, self.log, emit=emit),
                                   kwargs.pop('sim_cap_s', 1.), kwargs.pop('wall_cap_s', 2.), **kwargs)
        self.addCleanup(worker.close)
        return worker

    def start(self, worker):
        capture, memory, gc = Capture(), Memory(), Collector()
        worker.start(capture, memory, gc)
        return capture, memory, gc

    def wait_finished(self, worker, timeout=1.):
        end = time.perf_counter() + timeout
        while not worker.finished and time.perf_counter() < end:
            time.sleep(.002)
        self.assertTrue(worker.finished, 'worker did not finish within bounded test interval')

    def test_supervisory_wait_does_not_pause_physics_and_measurements_have_one_owner(self):
        worker = self.make()
        capture, memory, gc = self.start(worker)
        # The main thread stands in for a blocking fsync without touching files.
        threading.Event().wait(.06)
        self.assertGreaterEqual(worker.now - worker.initial_sim, .025)
        worker.stop('test_done')
        self.assertEqual(worker.terminal, 'test_done')
        self.assertIsNone(worker.error)
        self.assertEqual(set(capture.threads + [ident for _, ident in memory.calls] + gc.threads),
                         {worker.owner_thread_id})
        self.assertNotEqual(worker.owner_thread_id, threading.get_ident())
        self.assertEqual({ident for _, ident, _ in self.log}, {worker.owner_thread_id})
        self.assertTrue(memory.finished)
        self.assertEqual(self.log[-2][0], 'cancel:test_done')
        self.assertEqual(self.log[-1][0], 'close')
        self.assertTrue(worker.metrics['terminal_frozen'])

    def test_simulation_cap_independent_of_supervisor(self):
        worker = self.make(sim_cap_s=.02)
        capture, _, _ = self.start(worker)
        self.wait_finished(worker)
        self.assertEqual(worker.terminal, 'simulation_time_cap')
        self.assertAlmostEqual(worker.now - 1., .02)
        self.assertEqual(capture.terminal['reason'], worker.terminal)

    def test_wall_cap_independent_of_supervisor(self):
        class SlowClock(Driver):
            def tick(self): self.record('tick'); time.sleep(.002)
        worker = self.make(driver_cls=SlowClock, wall_cap_s=.025)
        self.start(worker)
        self.wait_finished(worker)
        self.assertEqual(worker.terminal, 'wall_time_cap')

    def test_heartbeat_loss_cancels_and_fails(self):
        worker = self.make(heartbeat_timeout=.025)
        self.start(worker)
        self.wait_finished(worker)
        self.assertEqual(worker.terminal, 'infrastructure_error')
        self.assertIn('heartbeat', worker.error['message'])
        self.assertTrue(any(row[0] == 'cancel:infrastructure_error' for row in self.log))

    def test_evidence_is_ordered_bounded_and_copied(self):
        class Publisher(Driver):
            def send(self, value):
                self.owner.publish('test', value)
                value['nested'].append('driver_mutation')
                return True
        worker = self.make(driver_cls=Publisher)
        self.start(worker)
        value = {'nested': [1]}
        worker.rpc('send', value)
        worker.rpc('send', {'nested': [2]})
        self.assertEqual(value, {'nested': [1]})
        self.assertEqual(worker.drain(), [{'kind': 'test', 'payload': {'nested': [1]}},
                                         {'kind': 'test', 'payload': {'nested': [2]}}])
        first = worker.snapshot
        first['nested']['value'].append('reader_mutation')
        self.assertEqual(worker.snapshot['nested']['value'], [1])
        self.assertLessEqual(worker.metrics['peak_message_bytes'], worker.queue_bytes)

    def test_count_and_byte_overflow_are_terminal_without_silent_valid_drop(self):
        for limits in ({'queue_count': 1}, {'queue_bytes': 1}):
            with self.subTest(limits=limits):
                worker = self.make(emit=True, **limits)
                self.start(worker)
                self.wait_finished(worker)
                self.assertEqual(worker.terminal, 'infrastructure_error')
                self.assertIn('queue bound', worker.error['message'])
                self.assertLessEqual(worker.metrics['peak_messages'], worker.queue_count)
                self.assertLessEqual(worker.metrics['peak_message_bytes'], worker.queue_bytes)
                self.assertEqual(len(worker.drain()), worker.metrics['published'])

    def test_driver_rechecks_stale_epoch_and_observation_without_dispatch(self):
        worker = self.make()
        self.start(worker)
        for request in ({'id': 'old-epoch', 'epoch': 0, 'capture': 1.},
                        {'id': 'old-camera', 'epoch': 1, 'capture': .1}):
            with self.assertRaises(RPCRejected): worker.rpc('submit', request)
        self.assertFalse(any(row[0].startswith('dispatch:') for row in self.log))
        receipt = worker.rpc('submit', {'id': 'valid', 'epoch': 1, 'capture': worker.now})
        self.assertTrue(receipt['accepted'])
        self.assertIsNone(worker.error)

    def test_unexpected_rpc_failure_latches_but_known_rejection_does_not(self):
        worker = self.make()
        self.start(worker)
        with self.assertRaises(RPCRejected): worker.rpc('reject')
        self.assertIsNone(worker.error)
        with self.assertRaises(PhysicsWorkerError): worker.rpc('fail')
        self.wait_finished(worker)
        self.assertEqual(worker.terminal, 'infrastructure_error')
        self.assertIn('injected driver failure', worker.error['message'])

    def test_timeout_is_unknown_and_operation_cannot_be_replayed(self):
        entered, release = threading.Event(), threading.Event()
        class HeldRPC(Driver):
            def once(self):
                self.record('once')
                entered.set()
                release.wait(.25)
                return {'accepted': True}
        worker = self.make(driver_cls=HeldRPC)
        self.start(worker)
        try:
            with self.assertRaises(RPCUnknown): worker.rpc('once', timeout=.025)
            self.assertTrue(entered.is_set())
            with self.assertRaises(PhysicsWorkerError): worker.rpc('once')
        finally:
            release.set()
        self.wait_finished(worker)
        self.assertEqual(sum(row[0] == 'once' for row in self.log), 1)
        self.assertIn('receipt unknown', worker.error['message'])

    def test_inputs_results_snapshots_have_no_cross_thread_mutable_alias(self):
        class AliasDriver(Driver):
            def retained(self):
                self.value = {'list': [1]}
                return self.value
            def read(self): return self.value
        worker = self.make(driver_cls=AliasDriver)
        self.start(worker)
        result = worker.rpc('retained')
        result['list'].append(2)
        self.assertEqual(worker.rpc('read'), {'list': [1]})
        with self.assertRaises(PhysicsWorkerError): worker.publish_snapshot({})

    def test_pending_timed_out_rpc_never_begins_after_owner_unblocks(self):
        entered, release = threading.Event(), threading.Event()
        class HeldRPC(Driver):
            def held(self):
                entered.set(); release.wait(.5)
                return True
            def forbidden(self):
                self.record('forbidden')
                return True
        worker = self.make(driver_cls=HeldRPC)
        self.start(worker)
        background_errors = []
        def hold():
            try: worker.rpc('held', timeout=.5)
            except Exception as error: background_errors.append(error)
        caller = threading.Thread(target=hold)
        caller.start()
        try:
            self.assertTrue(entered.wait(.2))
            with self.assertRaises(RPCUnknown): worker.rpc('forbidden', timeout=.015)
        finally:
            release.set(); caller.join(1.)
        self.wait_finished(worker)
        self.assertFalse(caller.is_alive())
        self.assertEqual(background_errors, [])
        self.assertFalse(any(row[0] == 'forbidden' for row in self.log))

    def test_request_queue_rejects_overflow_without_adding_an_operation(self):
        entered, release = threading.Event(), threading.Event()
        class HeldRPC(Driver):
            def held(self): entered.set(); release.wait(.5); return True
        worker = self.make(driver_cls=HeldRPC, rpc_count=1)
        self.start(worker)
        errors = []
        def call(name):
            try: worker.rpc(name, *([] if name == 'held' else [{'value': 1}]), timeout=.5)
            except Exception as error: errors.append(error)
        first = threading.Thread(target=call, args=('held',))
        second = threading.Thread(target=call, args=('echo',))
        first.start()
        try:
            self.assertTrue(entered.wait(.2))
            second.start()
            end = time.perf_counter() + .2
            while worker._requests.qsize() != 1 and time.perf_counter() < end:
                time.sleep(.001)
            self.assertEqual(worker._requests.qsize(), 1)
            with self.assertRaisesRegex(RPCRejected, 'not enqueued'):
                worker.rpc('echo', {'value': 2})
        finally:
            release.set(); first.join(1.)
            if second.ident is not None: second.join(1.)
        self.assertEqual(errors, [])
        self.assertEqual(sum(row[0] == 'echo' for row in self.log), 1)
        self.assertIsNone(worker.error)

    def test_prestart_rpc_rejected_and_normal_cancel_rpc_runs_on_owner(self):
        worker = self.make()
        with self.assertRaisesRegex(RPCRejected, 'started measured'):
            worker.rpc('echo', {})
        self.start(worker)
        self.assertIsNone(worker.rpc('cancel', 'operator_generation_revoked'))
        rows = [row for row in self.log if row[0] == 'cancel:operator_generation_revoked']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], worker.owner_thread_id)

    def test_close_before_start_cleans_up_on_owner_without_fabricated_timing(self):
        worker = self.make()
        worker.close()
        self.assertEqual(worker.terminal, 'owner_close')
        self.assertFalse(worker.metrics['terminal_frozen'])
        self.assertTrue(worker.metrics['owner_closed'])
        self.assertEqual([row[0] for row in self.log], ['initialize', 'cancel:owner_close', 'close'])

    def test_cancellation_failure_preserves_timing_and_still_closes_owner(self):
        class FailedCancel(Driver):
            def cancel(self, reason):
                self.record('cancel:' + reason)
                raise OSError('injected cancellation evidence failure')
        worker = self.make(driver_cls=FailedCancel)
        capture, memory, _ = self.start(worker)
        worker.rpc('echo', {})
        worker.stop('task_success')
        self.assertTrue(worker.finished)
        self.assertEqual(worker.terminal, 'infrastructure_error')
        self.assertIn('cancellation evidence', worker.error['message'])
        self.assertTrue(worker.metrics['terminal_frozen'])
        self.assertTrue(worker.metrics['owner_closed'])
        self.assertTrue(memory.finished)
        # The measured physics boundary remains authentic; later cleanup
        # failure invalidates the result, rather than rewriting that boundary.
        self.assertEqual(capture.terminal['reason'], 'task_success')
        self.assertEqual(self.log[-1][0], 'close')

    def test_close_failure_invalidates_terminal_without_erasing_physics_boundary(self):
        class FailedClose(Driver):
            def close(self):
                self.record('close')
                raise OSError('injected native close failure')
        worker = self.make(driver_cls=FailedClose)
        capture, memory, _ = self.start(worker)
        worker.rpc('echo', {})
        worker.stop('task_success')
        self.assertTrue(worker.finished)
        self.assertEqual(worker.terminal, 'infrastructure_error')
        self.assertIn('native close', worker.error['message'])
        self.assertTrue(worker.metrics['terminal_frozen'])
        self.assertFalse(worker.metrics['owner_closed'])
        self.assertTrue(memory.finished)
        self.assertEqual(capture.terminal['reason'], 'task_success')
        self.assertTrue(any(row[0] == 'cancel:task_success' for row in self.log))


if __name__ == '__main__':
    unittest.main()
