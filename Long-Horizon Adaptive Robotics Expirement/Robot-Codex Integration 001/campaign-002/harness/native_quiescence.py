"""Fixed native lifecycle controls; no inference or general RPC path.

Native I/O and coordination use one five-second graceful deadline and one
ten-second absolute retirement deadline. Daemon I/O workers are never joined
without a remaining deadline; owned-job termination releases blocked pipes.
"""
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import threading
import time
import uuid

import native_cleanup_protocol as cleanup_protocol

GRACEFUL_SECONDS = 5
TOTAL_SECONDS = 10
TERMINAL = frozenset(('completed', 'interrupted', 'failed'))
MAX_EVENTS = 24


class CleanupError(Exception):
    pass


def identity(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,256}', value) is not None


def remember_response(client, method, result):
    """Capture only identities from the successful original native response."""
    if method not in ('thread/start', 'turn/start'):
        return
    field = 'thread' if method == 'thread/start' else 'turn'
    value = result.get(field, {}).get('id') if isinstance(result, dict) and isinstance(result.get(field), dict) else None
    if not identity(value):
        raise RuntimeError('Native lifecycle identity is unavailable')
    setattr(client, field + '_id', value)


def remember_terminal(client, event):
    params = event.get('params', {})
    turn = params.get('turn', {})
    if (params.get('threadId') != client.thread_id or turn.get('id') != client.turn_id
            or turn.get('status') not in TERMINAL):
        raise RuntimeError('Native terminal identity or status differs')
    client.turn_terminal_status = turn['status']


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise CleanupError('malformed_message')
        value[key] = item
    return value


class Controller:
    def __init__(self, client, max_bytes):
        self.client, self.max_bytes = client, max_bytes
        self.started = time.monotonic()
        self.graceful = self.started + GRACEFUL_SECONDS
        self.hard = self.started + TOTAL_SECONDS
        self.log_lock = threading.Lock()
        self.events = []
        self.failures = []
        self.order_observations = {'schema': 'campaign002-native-shutdown-order-1',
                                  'lifecycle': [], 'stdin_close': []}
        self.thread = getattr(client, 'thread_id', None)
        self.turn = getattr(client, 'turn_id', None)
        self.status = getattr(client, 'turn_terminal_status', None)
        self.result = {
            'schema': 'campaign002-native-quiescence-2',
            'thread_id': self.thread, 'turn_id': self.turn,
            'entry': {'thread_start_requested': bool(getattr(client, 'thread_start_requested', False)),
                      'turn_start_requested': bool(getattr(client, 'turn_start_requested', False)),
                      'turn_terminal_status': self.status},
            'start_monotonic_s': self.started,
            'graceful_deadline_monotonic_s': self.graceful,
            'hard_deadline_monotonic_s': self.hard,
            'controls': [], 'cleanup_barrier': None, 'terminal_turn': None, 'thread_closed': None,
            'handshake_qualified': False, 'finishing_recorded': False,
            'stdin_closed': False, 'forced_job_close': False,
            'native_exit_code': None, 'native_exit_monotonic_s': None,
            'completed_monotonic_s': None, 'qualified': False,
            'ignored_notifications': 0, 'failures': self.failures, 'events': self.events}

    def fail(self, code):
        if code not in self.failures:
            self.failures.append(code)

    def bounded(self, operation, deadline, code):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise CleanupError(code)
        result = queue.Queue(maxsize=1)
        def worker():
            try: result.put((True, operation()))
            except BaseException: result.put((False, None))
        threading.Thread(target=worker, daemon=True).start()
        try: success, value = result.get(timeout=max(0, deadline-time.monotonic()))
        except queue.Empty: raise CleanupError(code) from None
        if not success or time.monotonic() > deadline:
            raise CleanupError(code)
        return value

    def emit(self, phase, *, deadline=None, **fields):
        if len(self.events) >= MAX_EVENTS:
            raise CleanupError('event_bound')
        observed_perf_counter_ns = time.perf_counter_ns()
        value = {'kind': 'native_quiescence', 'schema': 'campaign002-native-quiescence-event-1',
                 'sequence': len(self.events)+1, 'phase': phase,
                 'wall_unix_s': time.time(), 'monotonic_s': time.monotonic(), **fields}
        limit = self.graceful if deadline is None else deadline
        def write():
            with self.log_lock:
                if time.monotonic() >= limit:
                    raise CleanupError('event_retention_failed')
                self.client.log(value)
        self.bounded(write, limit, 'event_retention_failed')
        self.events.append(value)
        self.order_observations['lifecycle'].append({'sequence': value['sequence'],
            'phase': phase, 'observed_perf_counter_ns': observed_perf_counter_ns})
        return value

    def safe_emit(self, phase, **fields):
        try: return self.emit(phase, deadline=self.hard, **fields)
        except CleanupError as error: self.fail(str(error))

    def receive(self):
        while True:
            remaining = self.graceful-time.monotonic()
            if remaining <= 0:
                raise CleanupError('handshake_deadline')
            try: label, data = self.client.messages.get(timeout=remaining)
            except queue.Empty: raise CleanupError('handshake_deadline') from None
            if data is None:
                if label == 'stdout': raise CleanupError('native_stdout_closed')
                if label != 'stderr': raise CleanupError('malformed_message')
                continue
            if label not in ('stdout', 'stderr') or not isinstance(data, bytes):
                raise CleanupError('malformed_message')
            self.client.bytes_seen += len(data)
            if self.client.bytes_seen > self.max_bytes:
                raise CleanupError('output_limit')
            if label == 'stderr':
                from transport_stderr import metadata
                value = metadata(data)
                self.bounded(lambda: self._log(value), self.graceful, 'event_retention_failed')
                continue
            proof = {'input_bytes': len(data), 'input_sha256': hashlib.sha256(data).hexdigest()}
            try:
                msg = json.loads(data.decode('utf-8'), object_pairs_hook=_object)
            except (ValueError, UnicodeError, CleanupError):
                raise CleanupError('malformed_message') from None
            if not isinstance(msg, dict) or msg.get('jsonrpc', '2.0') != '2.0':
                raise CleanupError('malformed_message')
            if 'method' in msg and 'id' in msg:
                raise CleanupError('unexpected_server_request')
            if msg.get('method') == 'configWarning':
                raise CleanupError('configuration_warning')
            return msg, proof

    def _log(self, value):
        with self.log_lock:
            self.client.log(value)

    def cleanup_barrier(self, event):
        """Complete one owner-authenticated phase before any cleanup control write."""
        if self.result['cleanup_barrier'] is not None:
            return
        callback = getattr(self.client.args, 'native_cleanup_barrier', None)
        if not callable(callback):
            raise CleanupError('cleanup_barrier_missing')
        seed = {'schema': cleanup_protocol.REQUEST_SCHEMA, 'nonce': uuid.uuid4().hex,
                'thread_id': self.thread, 'turn_id': self.turn, 'control_event': event,
                'start_monotonic_s': self.started,
                'graceful_deadline_monotonic_s': self.graceful}
        try:
            cleanup_protocol.validate_seed(seed)
            # Pass a detached object so a callback cannot change the retained
            # request event or the expected identity used below.
            complete = self.bounded(
                lambda: callback(json.loads(cleanup_protocol.canonical(seed))),
                self.graceful, 'cleanup_barrier_failed')
            cleanup_protocol.validate_complete(seed, complete)
            if time.monotonic() >= self.graceful:
                raise CleanupError('cleanup_barrier_deadline')
            self.emit('cleanup_barrier_complete', receipt=complete)
            self.result['cleanup_barrier'] = complete
        except ValueError:
            raise CleanupError('cleanup_barrier_invalid') from None

    def control(self, method):
        if method not in ('turn/interrupt', 'thread/unsubscribe'):
            raise CleanupError('forbidden_control')
        self.client.next_id += 1
        request_id = self.client.next_id
        params = {'threadId': self.thread}
        if method == 'turn/interrupt': params['turnId'] = self.turn
        message = {'id': request_id, 'method': method, 'params': params}
        wire = (json.dumps(message)+'\n').encode()
        event = self.emit('request', method=method, request_id=request_id,
                          thread_id=self.thread, turn_id=self.turn if method == 'turn/interrupt' else None,
                          wire_bytes=len(wire), wire_sha256=hashlib.sha256(wire).hexdigest())
        record = {'method': method, 'request_id': request_id,
                  'sent_monotonic_s': None, 'response_monotonic_s': None, 'response_status': None}
        self.result['controls'].append(record)
        self.cleanup_barrier(event)
        def send():
            self.client.process.stdin.write(wire)
            self.client.process.stdin.flush()
        self.bounded(send, self.graceful, 'control_write_failed')
        record['sent_monotonic_s'] = time.monotonic()
        self.emit('request_sent', method=method, request_id=request_id)
        response, notification = False, False
        while not (response and notification):
            msg, proof = self.receive()
            if 'method' not in msg:
                if type(msg.get('id')) is not int or msg['id'] != request_id or response:
                    raise CleanupError('response_identity_or_duplicate')
                if 'error' in msg: raise CleanupError('native_rpc_error')
                value = msg.get('result')
                if not isinstance(value, dict): raise CleanupError('malformed_response')
                if method == 'turn/interrupt':
                    if value: raise CleanupError('malformed_response')
                    status = 'empty'
                else:
                    if set(value) != {'status'} or value['status'] != 'unsubscribed':
                        raise CleanupError('unsubscribe_not_confirmed')
                    status = 'unsubscribed'
                event = self.emit('response', method=method, request_id=request_id, status=status, **proof)
                record.update(response_monotonic_s=event['monotonic_s'], response_status=status)
                response = True
            elif msg['method'] == 'turn/completed':
                params = msg.get('params', {})
                turn = params.get('turn', {}) if isinstance(params, dict) else {}
                if (method != 'turn/interrupt' or notification or not isinstance(turn, dict)
                        or params.get('threadId') != self.thread or turn.get('id') != self.turn
                        or turn.get('status') not in TERMINAL):
                    raise CleanupError('terminal_identity_or_duplicate')
                event = self.emit('turn_terminal', thread_id=self.thread, turn_id=self.turn,
                                  status=turn['status'], source='cleanup', **proof)
                self.result['terminal_turn'] = {key:event[key] for key in
                    ('thread_id','turn_id','status','source','monotonic_s')}
                self.client.turn_terminal_status = turn['status']
                notification = True
            elif msg['method'] == 'thread/closed':
                params = msg.get('params')
                if (method != 'thread/unsubscribe' or notification or not isinstance(params, dict)
                        or set(params) != {'threadId'} or params['threadId'] != self.thread):
                    raise CleanupError('closed_identity_or_duplicate')
                event = self.emit('thread_closed', thread_id=self.thread, **proof)
                self.result['thread_closed'] = {'thread_id': self.thread, 'monotonic_s': event['monotonic_s']}
                notification = True
            elif isinstance(msg.get('method'), str):
                self.result['ignored_notifications'] += 1
            else:
                raise CleanupError('malformed_message')

    def handshake(self):
        self.emit('start', thread_id=self.thread, turn_id=self.turn, entry=self.result['entry'],
                  start_monotonic_s=self.started, graceful_deadline_monotonic_s=self.graceful,
                  hard_deadline_monotonic_s=self.hard)
        if self.thread is None:
            if self.result['entry']['thread_start_requested'] or self.result['entry']['turn_start_requested']:
                raise CleanupError('thread_identity_unavailable')
            return
        if not identity(self.thread): raise CleanupError('thread_identity_unavailable')
        if self.result['entry']['turn_start_requested'] and not identity(self.turn):
            raise CleanupError('turn_identity_unavailable')
        if self.turn is not None:
            if not identity(self.turn): raise CleanupError('turn_identity_unavailable')
            if self.status in TERMINAL:
                self.result['terminal_turn'] = {'thread_id': self.thread, 'turn_id': self.turn,
                    'status': self.status, 'source': 'entry', 'monotonic_s': self.started}
            else:
                self.control('turn/interrupt')
        self.control('thread/unsubscribe')

    def run(self):
        self.client.cleanup_started = True
        try:
            self.handshake()
            self.result['handshake_qualified'] = True
        except CleanupError as error: self.fail(str(error))
        except BaseException: self.fail('handshake_internal_error')
        self.safe_emit('handshake_complete', qualified=self.result['handshake_qualified'])
        from transport_stderr import announce_finishing
        try:
            self.result['finishing_recorded'] = self.bounded(
                lambda: self._announce(announce_finishing), self.hard, 'finishing_retention_failed')
            if not self.result['finishing_recorded']: self.fail('finishing_retention_failed')
        except CleanupError as error: self.fail(str(error))
        self.safe_emit('finishing', recorded=self.result['finishing_recorded'])
        if not self.failures and getattr(self.client.args, 'native_process_ready', None) is not None:
            try:
                import native_exit_drain
                self.bounded(lambda: native_exit_drain.before_stdin_close(self), self.graceful,
                             'transport_pre_exit_drain_failed')
            except CleanupError as error: self.fail(str(error))
        if not self.failures:
            try:
                self.bounded(self.close_stdin_observed, self.graceful, 'stdin_close_failed')
                self.result['stdin_closed'] = True
                self.emit('stdin_closed')
                self.bounded(lambda: self.client.process.wait(timeout=max(0,self.graceful-time.monotonic())),
                             self.graceful, 'graceful_exit_deadline')
                self.observe_exit()
            except CleanupError as error: self.fail(str(error))
        if self.failures or self.client.process.poll() is None:
            self.result['forced_job_close'] = True
            self.safe_emit('job_forced')
            # Start even if the hard deadline has already expired: owned-process
            # retirement remains necessary, but no late completion qualifies.
            done = threading.Event()
            kill_failed = threading.Event()
            def kill():
                try: self.client.job.close()
                except BaseException: kill_failed.set()
                finally: done.set()
            threading.Thread(target=kill, daemon=True).start()
            if not done.wait(max(0,self.hard-time.monotonic())):
                self.fail('job_close_deadline')
            if kill_failed.is_set(): self.fail('job_close_failed')
            self.fail('forced_exit')
            try:
                self.bounded(self.close_stdin_observed,self.hard,'stdin_close_failed')
                self.result['stdin_closed'] = True
                self.safe_emit('stdin_closed')
            except CleanupError as error: self.fail(str(error))
            try:
                self.bounded(lambda:self.client.process.wait(timeout=max(0,self.hard-time.monotonic())),
                             self.hard,'native_reap_deadline')
            except CleanupError as error: self.fail(str(error))
        else:
            try: self.bounded(self.client.job.close,self.hard,'job_close_deadline')
            except CleanupError as error: self.fail(str(error))
        if self.result['native_exit_monotonic_s'] is None: self.observe_exit()
        code = self.result['native_exit_code']
        if type(code) is not int or code != 0: self.fail('native_exit_nonzero_or_missing')
        if time.monotonic() > self.hard: self.fail('cleanup_deadline')
        self.result['completed_monotonic_s'] = time.monotonic()
        self.result['qualified'] = not self.failures and self.result['handshake_qualified'] and self.result['finishing_recorded']
        self.safe_emit('completed', qualified=self.result['qualified'])
        # Preserve the established shutdown event for existing transport joins.
        try:
            self.bounded(lambda:self._log({'kind':'client_shutdown','exit_code':code}),self.hard,'event_retention_failed')
            self.bounded(self.client.events.close,self.hard,'event_retention_failed')
        except CleanupError as error: self.fail(str(error))
        self.result['qualified'] = self.result['qualified'] and not self.failures
        self.client.cleanup_result = self.result
        try:
            path = Path(self.client.args.evidence)/'native-quiescence.json'
            with path.open('x',encoding='utf-8') as file:
                json.dump(self.result,file,indent=2);file.write('\n');file.flush();os.fsync(file.fileno())
            with path.with_name('native-shutdown-order.json').open('x',encoding='utf-8') as file:
                json.dump(self.order_observations,file,indent=2);file.write('\n');file.flush();os.fsync(file.fileno())
        except BaseException:
            self.fail('receipt_retention_failed');self.result['qualified'] = False
        return self.result

    def close_stdin_observed(self):
        # At most the existing graceful close and its existing forced cleanup.
        # Capture inside the worker, immediately around the unchanged operation.
        observation = {'begin_perf_counter_ns': time.perf_counter_ns(),
                       'end_perf_counter_ns': None, 'returned_normally': False}
        self.order_observations['stdin_close'].append(observation)
        try:
            value = self.client.process.stdin.close()
            observation['returned_normally'] = True
            return value
        finally:
            observation['end_perf_counter_ns'] = time.perf_counter_ns()

    def observe_exit(self):
        code = self.client.process.poll()
        self.result['native_exit_code'] = code if type(code) is int else None
        if type(code) is int:
            observed = time.monotonic()
            self.result['native_exit_monotonic_s'] = observed
            self.safe_emit('native_exit', exit_code=code, observed_monotonic_s=observed)

    def _announce(self, announce):
        with self.log_lock:
            return announce(self.client)


def close(client, max_bytes):
    if getattr(client, 'cleanup_started', False):
        raise RuntimeError('Native cleanup already started')
    return Controller(client, max_bytes).run()
