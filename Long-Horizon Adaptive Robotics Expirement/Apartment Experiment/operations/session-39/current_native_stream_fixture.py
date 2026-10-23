# Synthetic constructor-state repair only; see CORE-STREAM-FIXTURE.md.
"""Actual large notification stream, bounded buffering, limits and native preflight."""
import argparse
import io
import json
from pathlib import Path
import threading
import time
import traceback
from types import SimpleNamespace
from unittest.mock import patch
from common import save, canonical, sha

def fixture(root):
    import native_runtime
    import native_stream as ns
    root.mkdir(parents=True)
    client = object.__new__(native_runtime.old.bootstrap.Client)
    client.args = SimpleNamespace(evidence=root, redact_tokens=['TEST_EPHEMERAL_TOKEN'], abort_event=threading.Event(), native_process_drain=True)
    from structured_errors import FailureTrace
    client.failure_trace = FailureTrace(client.args.redact_tokens)
    client.args.apartment_failure_trace = client.failure_trace
    client.messages = ns.ByteQueue()
    client.pending_events = ns.TerminalEvents()
    client.bytes_seen = 0
    client.deadline = time.monotonic() + 300
    client.cleanup_started = False
    client.events = ns.EventStream((root / 'events.jsonl').open('x', encoding='utf-8'))
    client.stream_ready = threading.Event()
    client.stream_ready.set()
    client.stream_stop = threading.Event()
    client.readers = []
    client.reader_errors = []
    client.thread_id = 'test-thread'
    client.turn_id = 'test-turn'
    client.turn_terminal_status = None
    return client

def run(out):
    out.mkdir(parents=True, exist_ok=False)
    result = dict(passed=False, stage='native-stream-engineering', official_sessions=0, model_calls=0, checks={})
    client = None
    try:
        import native_stream as ns
        client = fixture(out / 'large-notifications')
        count = 768
        payload = 'TEST_EPHEMERAL_TOKEN' + 'x' * 131072

        class Producer:
            index = 0
            raw_bytes = 0

            def readline(self, limit):
                if self.index < count:
                    message = dict(method='item/commandExecution/outputDelta', params=dict(index=self.index, delta=payload))
                elif self.index == count:
                    message = dict(method='turn/completed', params=dict(threadId='test-thread', turn=dict(id='test-turn', status='completed')))
                else:
                    return b''
                self.index += 1
                raw = canonical(message) + b'\n'
                assert len(raw) < limit
                self.raw_bytes += len(raw)
                return raw
        producer = Producer()
        thread = threading.Thread(target=client._drain, args=('stdout', producer), daemon=True)
        thread.start()
        for index in range(count):
            event = client.receive(return_notifications=True)
            assert event['params'] == dict(index=index, delta=payload)
            assert not client.pending_events
        terminal = client.wait_turn('test-turn')
        thread.join(2)
        assert terminal['status'] == 'completed' and client.turn_terminal_status == 'completed' and (not thread.is_alive())
        client.events.flush()
        client.events.close()
        rows = 0
        with (out / 'large-notifications/events.jsonl').open('rb') as f:
            for raw in f:
                event = json.loads(raw)
                assert b'TEST_EPHEMERAL_TOKEN' not in raw
                if rows < count:
                    assert event['params'] == dict(index=rows, delta=payload.replace('TEST_EPHEMERAL_TOKEN', '[REDACTED_EPHEMERAL_CAPABILITY]'))
                else:
                    assert event['method'] == 'turn/completed'
                rows += 1
        assert rows == count + 1 and client.bytes_seen == producer.raw_bytes and (client.bytes_seen > 3 * 32 * 1024 ** 2)
        assert client.events.bytes == (out / 'large-notifications/events.jsonl').stat().st_size
        assert client.messages.peak_bytes <= ns.QUEUE_BYTES and client.messages.peak_items <= ns.QUEUE_ITEMS
        assert client.pending_events.peak == 1 and (not client.reader_errors)
        result['stream'] = dict(raw_bytes=client.bytes_seen, records=rows, event_bytes=client.events.bytes, event_sha256=sha(out / 'large-notifications/events.jsonl'), queue_peak_bytes=client.messages.peak_bytes, queue_peak_items=client.messages.peak_items, pending_terminal_peak=client.pending_events.peak)
        result['checks']['large_stream_exact_and_redacted'] = True
        result['checks']['queue_and_notification_memory_bounded'] = True
        client = None
        q = ns.ByteQueue()
        data = b'x' * 1048576
        for i in range(8):
            q.put(('stdout', data))
        began = threading.Event()
        finished = threading.Event()

        def blocked():
            began.set()
            q.put(('stdout', data))
            finished.set()
        thread = threading.Thread(target=blocked, daemon=True)
        thread.start()
        began.wait(1)
        assert not finished.wait(0.03)
        assert q.get()[1] == data
        thread.join(2)
        assert finished.is_set() and q.peak_bytes == ns.QUEUE_BYTES
        q.close()
        result['checks']['producer_backpressure'] = True
        client = fixture(out / 'bounds')
        client._drain('stdout', io.BytesIO(b'x' * (ns.LINE_LIMIT + 1)))
        assert client.reader_errors and client.args.abort_event.is_set() and (client.messages.get() == ('stdout', None))
        result['checks']['oversize_line_rejected'] = True
        client.events.close()
        client = None
        client = fixture(out / 'total-limit')
        extra = canonical(dict(method='test_notification', params={})) + b'\n'
        client.bytes_seen = ns.STREAM_LIMIT - len(extra) + 1
        client.messages.put(('stdout', extra))
        try:
            client.receive(return_notifications=True)
        except RuntimeError as error:
            assert str(error) == 'App-server output limit exceeded'
        else:
            raise AssertionError('Cumulative native recording bound was ignored')
        result['checks']['finite_stream_limit_rejected'] = True
        seen = []

        def fake_close(c, budget):
            seen.append(budget)
            c.events.close()
            return dict(qualified=False, failures=['synthetic-output-limit'])
        with patch('native_process_quiescence.close', fake_close):
            closed = client.close()
        assert closed['qualified'] is False and seen == [client.bytes_seen + ns.CLEANUP_RESERVE]
        result['checks']['exhaustion_has_separate_cleanup_allowance'] = True
        client = None
        stream = ns.EventStream((out / 'retention-bound.txt').open('x', encoding='utf-8'))
        stream.bytes = ns.EVENT_LIMIT
        try:
            stream.write('not retained\n')
        except RuntimeError:
            pass
        else:
            raise AssertionError('Retained-event bound ignored')
        stream.close()
        assert (out / 'retention-bound.txt').stat().st_size == 0
        result['checks']['finite_event_retention_limit_rejected'] = True
        import integration_engineering
        result['checks']['both_native_preflights'] = integration_engineering.run(out / 'preflight')
        for condition in ('baseline', 'maps'):
            receipt = json.loads((out / 'preflight' / condition / 'native/client/native-stream.json').read_text())
            assert receipt['passed'] and receipt['readers_retired']
        result['checks']['real_native_stream_readers_retired'] = True
        result['passed'] = all(result['checks'].values())
    except BaseException as error:
        result.update(error=repr(error), traceback=traceback.format_exc())
    finally:
        if client:
            client.stream_stop.set()
            client.messages.close()
            client.events.close()
    save(out / 'result.json', result)
    print(canonical(result).decode())
    return result['passed']
if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    raise SystemExit(0 if run(a.output) else 1)
