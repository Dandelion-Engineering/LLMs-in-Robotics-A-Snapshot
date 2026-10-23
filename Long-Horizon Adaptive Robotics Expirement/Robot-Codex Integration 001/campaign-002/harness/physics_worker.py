"""One continuously paced Cell owner with bounded, copied in-process messages.

The factory and every driver method run on the owner thread. No persistence is
performed here. The caller retains durable-intent-before-RPC ordering; the
driver must recheck authority, referenced observation age and skill deadlines.
Pickle is an internal copy/size boundary only: never feed it external bytes.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math
import pickle
import queue
import threading
import time


class PhysicsWorkerError(RuntimeError):
    pass


class RPCUnknown(PhysicsWorkerError):
    """The operation may have begun; its identity must never be replayed."""


class RPCRejected(ValueError):
    """A driver rejected an RPC without requiring a worker failure."""


@dataclass
class _Call:
    identity: int
    method: str
    raw: bytes
    done: threading.Event = field(default_factory=threading.Event)
    started: bool = False
    abandoned: bool = False
    result: bytes | None = None
    error: Exception | None = None


class ContinuousPhysics:
    def __init__(self, factory, sim_cap_s, wall_cap_s, *, dt=.002,
                 heartbeat_timeout=2., queue_count=4096,
                 queue_bytes=64 * 1024**2, rpc_count=32,
                 rpc_payload_bytes=1024**2, snapshot_bytes=1024**2,
                 initialization_timeout=60.):
        for name, value in [('sim_cap_s', sim_cap_s), ('wall_cap_s', wall_cap_s),
                            ('dt', dt), ('heartbeat_timeout', heartbeat_timeout),
                            ('initialization_timeout', initialization_timeout)]:
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError('Invalid ' + name)
        if heartbeat_timeout > 2.:
            raise ValueError('Supervisory heartbeat lease cannot exceed two seconds')
        for value in (queue_count, queue_bytes, rpc_count, rpc_payload_bytes, snapshot_bytes):
            if type(value) is not int or value <= 0:
                raise ValueError('Message limits must be positive integers')
        self.sim_cap_s, self.wall_cap_s, self.dt = sim_cap_s, wall_cap_s, dt
        self.heartbeat_timeout = heartbeat_timeout
        self.queue_count, self.queue_bytes = queue_count, queue_bytes
        self.rpc_payload_bytes, self.snapshot_bytes = rpc_payload_bytes, snapshot_bytes
        self.rpc_count = rpc_count
        self._factory = factory
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._begin = threading.Event()
        self._stop = threading.Event()
        self._finished = threading.Event()
        self._requests = queue.Queue(maxsize=rpc_count)
        self._messages = deque()
        self._message_bytes = 0
        self._snapshot = None
        self._now = None
        self.initial_sim = None
        self._heartbeat = time.perf_counter()
        self._next_call = 0
        self._start_called = False
        self._stop_reason = 'operator_stop'
        self._capture = self._memory = self._gc = None
        self.error = None
        self.terminal = None
        self.owner_thread_id = None
        self.metrics = dict(ticks=0, published=0, drained=0, peak_messages=0,
                            peak_message_bytes=0, maximum_message_bytes=0,
                            rpc_started=0, rpc_completed=0, rpc_abandoned=0,
                            owner_closed=False, terminal_frozen=False,
                            published_by_kind={}, drained_by_kind={})
        self._thread = threading.Thread(target=self._run, name='continuous-physics-owner', daemon=True)
        self._thread.start()
        if not self._ready.wait(initialization_timeout):
            self._fail(PhysicsWorkerError('Physics initialization timeout; owner state unknown'))
            self._stop.set(); self._begin.set()
            raise PhysicsWorkerError(self.error['message'])
        self.check()

    def _assert_owner(self):
        if threading.get_ident() != self.owner_thread_id:
            raise PhysicsWorkerError('Driver access requires the physics owner thread')

    def _fail(self, error):
        with self._lock:
            if self.error is None:
                self.error = {'type': type(error).__name__, 'message': str(error)}
        self._stop.set()

    def check(self):
        if self.error is not None:
            raise PhysicsWorkerError(self.error['type'] + ': ' + self.error['message'])

    @property
    def now(self):
        with self._lock:
            return self._now

    @property
    def snapshot(self):
        with self._lock:
            raw = self._snapshot
        return None if raw is None else pickle.loads(raw)

    @property
    def finished(self):
        return self._finished.is_set()

    def publish_snapshot(self, value):
        self._assert_owner()
        raw = pickle.dumps(value, protocol=5)
        if len(raw) > self.snapshot_bytes:
            raise PhysicsWorkerError('Physics snapshot byte limit exceeded')
        with self._lock:
            self._snapshot = raw

    def publish(self, kind, payload):
        self._assert_owner()
        if not isinstance(kind, str) or not kind or len(kind) > 64:
            raise ValueError('A bounded message kind is required')
        raw = pickle.dumps({'kind': kind, 'payload': payload}, protocol=5)
        with self._lock:
            if len(self._messages) >= self.queue_count or self._message_bytes + len(raw) > self.queue_bytes:
                raise PhysicsWorkerError('Physics evidence queue bound exceeded; no message dropped as valid evidence')
            self._messages.append(raw)
            self._message_bytes += len(raw)
            self.metrics['published'] += 1
            counts = self.metrics['published_by_kind']
            counts[kind] = counts.get(kind, 0) + 1
            self.metrics['peak_messages'] = max(self.metrics['peak_messages'], len(self._messages))
            self.metrics['peak_message_bytes'] = max(self.metrics['peak_message_bytes'], self._message_bytes)
            self.metrics['maximum_message_bytes'] = max(self.metrics['maximum_message_bytes'], len(raw))

    def drain(self, limit=None):
        if limit is not None and (type(limit) is not int or limit < 0):
            raise ValueError('Invalid drain limit')
        with self._lock:
            count = len(self._messages) if limit is None else min(limit, len(self._messages))
            rows = [self._messages.popleft() for _ in range(count)]
            self._message_bytes -= sum(map(len, rows))
            self.metrics['drained'] += count
        decoded = [pickle.loads(raw) for raw in rows]
        for message in decoded:
            kind = message['kind']
            counts = self.metrics['drained_by_kind']
            counts[kind] = counts.get(kind, 0) + 1
        return decoded

    def heartbeat(self):
        with self._lock:
            self._heartbeat = time.perf_counter()

    def start(self, capture, memory=None, gc=None):
        self.check()
        if self._start_called or self._finished.is_set() or self._stop.is_set():
            raise PhysicsWorkerError('Physics interval can start only once')
        if not math.isfinite(capture.origin):
            raise ValueError('Finite QPC capture origin required')
        self._capture, self._memory, self._gc = capture, memory, gc
        self._start_called = True
        self.heartbeat()
        self._begin.set()

    def rpc(self, method, *args, timeout=1., **kwargs):
        self.check()
        if (not isinstance(method, str) or not method or method.startswith('_') or
                method in {'tick', 'close'}):
            raise RPCRejected('Invalid driver RPC method')
        if not self._start_called:
            raise RPCRejected('Physics RPC requires a started measured interval')
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('Positive finite RPC timeout required')
        raw = pickle.dumps((args, kwargs), protocol=5)
        if len(raw) > self.rpc_payload_bytes:
            raise RPCRejected('RPC input byte limit exceeded')
        with self._lock:
            if self._stop.is_set() or self._finished.is_set():
                raise PhysicsWorkerError('Physics owner has terminated')
            self._next_call += 1
            call = _Call(self._next_call, method, raw)
            try:
                self._requests.put_nowait(call)
            except queue.Full:
                raise RPCRejected('Physics request queue full; request was not enqueued') from None
        if not call.done.wait(timeout):
            with self._lock:
                # Completion at the timeout boundary is still a known receipt.
                if not call.done.is_set():
                    call.abandoned = True
                    unknown = RPCUnknown('RPC ' + str(call.identity) + ' timed out; receipt unknown; no replay')
                else:
                    unknown = None
            if unknown is not None:
                self._fail(unknown)
                raise unknown
        if call.error is not None:
            raise call.error
        return pickle.loads(call.result)

    def stop(self, reason='operator_stop', *, timeout=10.):
        if not isinstance(reason, str) or not reason or len(reason) > 1024:
            raise ValueError('Bounded stop reason required')
        self._stop_reason = reason
        self._stop.set(); self._begin.set()
        self._thread.join(timeout)
        if self._thread.is_alive():
            self._fail(RPCUnknown('Physics termination timed out; owner completion unknown'))
            raise PhysicsWorkerError(self.error['message'])
        return self.terminal

    def close(self):
        return self.stop('owner_close') if not self.finished else self.terminal

    def _service_rpc(self, driver):
        # A fixed per-tick budget prevents a full queue starving physics.
        for _ in range(4):
            try:
                call = self._requests.get_nowait()
            except queue.Empty:
                return
            with self._lock:
                skip = call.abandoned or self._stop.is_set()
                if not skip:
                    call.started = True
                    self.metrics['rpc_started'] += 1
            if skip:
                call.error = RPCUnknown('RPC was abandoned before dispatch; no replay')
                self.metrics['rpc_abandoned'] += 1
                call.done.set()
                continue
            try:
                args, kwargs = pickle.loads(call.raw)
                invoke = getattr(driver, 'invoke', None)
                result = invoke(call.method, *args, **kwargs) if invoke else getattr(driver, call.method)(*args, **kwargs)
                call.result = pickle.dumps(result, protocol=5)
                if len(call.result) > self.rpc_payload_bytes:
                    raise RPCUnknown('RPC result exceeds byte limit; operation receipt unknown')
                self.metrics['rpc_completed'] += 1
            except RPCRejected as error:
                call.error = RPCRejected(type(error).__name__ + ': ' + str(error))
            except Exception as error:
                call.error = PhysicsWorkerError(type(error).__name__ + ': ' + str(error))
                self._fail(error)
            finally:
                with self._lock:
                    call.done.set()

    def _run(self):
        self.owner_thread_id = threading.get_ident()
        driver = None
        measured = False
        try:
            driver = self._factory(self)
            self.initial_sim = float(driver.now)
            with self._lock:
                self._now = self.initial_sim
            self._ready.set()
            self._begin.wait()
            if self._stop.is_set():
                self.terminal = 'infrastructure_error' if self.error else self._stop_reason
                return
            capture, memory, gc = self._capture, self._memory, self._gc
            measured = True
            if memory is not None:
                memory.start(capture.origin)
            while True:
                capture.sample(driver.now)
                if gc is not None:
                    gc.verify_deferred()
                if memory is not None and memory.poll() and gc is not None:
                    gc.verify_deferred(full=True)
                wall = time.perf_counter()
                with self._lock:
                    last_heartbeat = self._heartbeat
                if self._stop.is_set():
                    self.terminal = 'infrastructure_error' if self.error else self._stop_reason
                    break
                if wall - last_heartbeat > self.heartbeat_timeout:
                    raise PhysicsWorkerError('Supervisory heartbeat lease expired')
                if wall - capture.origin >= self.wall_cap_s:
                    self.terminal = 'wall_time_cap'; break
                if float(driver.now) - self.initial_sim >= self.sim_cap_s:
                    self.terminal = 'simulation_time_cap'; break
                self._service_rpc(driver)
                if self._stop.is_set():
                    self.terminal = 'infrastructure_error' if self.error else self._stop_reason
                    break
                with capture.phase('physics_owner.tick', lambda: driver.now):
                    driver.tick()
                with self._lock:
                    self._now = float(driver.now)
                    self.metrics['ticks'] += 1
                capture.sample(driver.now)
                delay = capture.origin + float(driver.now) - self.initial_sim - time.perf_counter()
                if delay > 0:
                    self._stop.wait(min(delay, self.dt))
        except Exception as error:
            self._fail(error)
            self.terminal = 'infrastructure_error'
        finally:
            self._ready.set()
            if driver is not None:
                with self._lock:
                    self._now = float(driver.now)
                if measured:
                    try:
                        if self._memory is not None:
                            self._memory.finish()
                        if self._gc is not None:
                            self._gc.verify_deferred(full=True)
                        self._capture.finish(driver.now, self.terminal)
                        self.metrics['terminal_frozen'] = True
                    except Exception as error:
                        self._fail(error)
                        self.terminal = 'infrastructure_error'
                        # A resource failure must not erase the timing ledger.
                        if self._capture.terminal is None:
                            try:
                                self._capture.finish(driver.now, self.terminal)
                                self.metrics['terminal_frozen'] = True
                            except Exception as timing_error:
                                with self._lock:
                                    self.error['timing_finalization'] = str(timing_error)
                try:
                    driver.cancel(self.terminal or 'physics_owner_failed')
                except Exception as error:
                    self._fail(error); self.terminal = 'infrastructure_error'
                try:
                    driver.close()
                    self.metrics['owner_closed'] = True
                except Exception as error:
                    self._fail(error); self.terminal = 'infrastructure_error'
            while True:
                try:
                    call = self._requests.get_nowait()
                except queue.Empty:
                    break
                call.error = RPCUnknown('Physics terminated before RPC receipt; no replay')
                call.done.set()
            self._finished.set()
