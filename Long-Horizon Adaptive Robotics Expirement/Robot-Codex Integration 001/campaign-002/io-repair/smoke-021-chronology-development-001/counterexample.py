"""Synthetic chronology counterexamples; never assesses or upgrades a run.

The two production functions exercised here are extracted from immutable dev070.
There is no native process, model invocation, socket, or empirical-result replay.
"""
from __future__ import annotations

import ast
import asyncio
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import shlex
import tempfile
from types import SimpleNamespace
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[5]
EXPERIMENT = ROOT / 'Long-Horizon Adaptive Robotics Expirement'
SNAPSHOT = EXPERIMENT / 'Architecture Map/releases/RCI001-C02-dev-070/snapshot.json'
FROZEN = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
INPUTS = []
OBSERVATIONS = {}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source(suffix):
    with zipfile.ZipFile(SNAPSHOT.with_name('code.zip')) as archive:
        names = [n for n in archive.namelist() if n.endswith('/' + suffix)]
        assert len(names) == 1
        name, raw = names[0], archive.read(names[0])
    assert sha(raw) == FROZEN['sources'][name]['sha256']
    assert len(raw) == FROZEN['sources'][name]['bytes']
    INPUTS.append({'archive_member': name, 'sha256': sha(raw), 'bytes': len(raw)})
    return raw.decode('utf-8')


ASSESSOR_SOURCE = source('assessment/literal_read_segments.py')
CAPTURE_SOURCE = source('harness/executor_capture.py')


def extract(text, name, namespace):
    nodes = [node for node in ast.walk(ast.parse(text))
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
             and node.name == name]
    assert len(nodes) == 1
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<frozen-source:' + name + '>', 'exec'), namespace)
    return namespace[name]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def frozen_proof(rows, emitted_ms):
    command = "/usr/bin/bash -lc 'cat Tasks.md Robot.md Tools.md'"
    item = {'id': 'synthetic-tool', 'command': command}
    namespace = {
        'load_capture': lambda _: (rows, {2}, {}),
        'environment_proof': lambda _: {'synthetic_environment_stub': True},
        'require': require, 'finite_time': float, 'shlex': shlex,
    }
    function = extract(ASSESSOR_SOURCE, 'execution_proof', namespace)
    events = [{'method': method, 'params': {'item': item}, 'emittedAtMs': emitted_ms}
              for method in ('item/started', 'item/completed')]
    return function(Path('.'), events[-1], events,
                    {'provenance': {'file': 'synthetic', 'request_sequence': 1, 'process_id': 'p'}})


def rows(start, closed, delivered):
    return [
        {'sequence': 1, 'wall_unix_s': start, 'kind': 'request',
         'original_message_sha256': 'same', 'retained_message_sha256': 'same',
         'message': {'params': {'argv': ['/usr/bin/bash', '-lc', 'cat Tasks.md Robot.md Tools.md'],
                                'metadata': {'toolCallId': 'synthetic-tool'}}}},
        {'sequence': 2, 'wall_unix_s': closed, 'kind': 'response',
         'message': {'method': 'process/closed', 'params': {'processId': 'p'}}},
        {'sequence': 3, 'wall_unix_s': delivered, 'kind': 'delivered', 'response_sequence': 2},
    ]


def illustrative_bound(start, closed, deliveries, emitted_ms):
    """ONLY a proposed temporal subcondition, not a complete read verifier.

    This deliberately restricts eligibility to a close-consistent native interval.
    The upstream source does not promise every completion is after process/closed.
    """
    require(type(emitted_ms) is int and emitted_ms >= 0, 'Exact nonnegative milliseconds required')
    require(bool(deliveries), 'Complete authenticated local delivery receipts required')
    start, closed = Decimal(str(start)), Decimal(str(closed))
    ds = [Decimal(str(value)) for value in deliveries]
    upper = Decimal(emitted_ms + 1) / 1000
    require(start < closed and all(closed <= d for d in ds), 'Local request/close/delivery order')
    require(closed < upper, 'Native interval entirely precedes close capture')
    return max(upper, *ds)


class ChronologyCounterexamples(unittest.TestCase):
    def test_frozen_predicate_rejects_compatible_submillisecond_timestamps(self):
        # Recorded times are reproduced as numbers only; no run assessment is read.
        r = rows(1790638440.971517, 1790638440.984023, 1790638440.9850233)
        with self.assertRaisesRegex(ValueError, 'Process/app completion chronology inconsistent'):
            frozen_proof(r, 1790638440985)
        lower, upper = Decimal('1790638440.985'), Decimal('1790638440.986')
        delivery = Decimal('1790638440.9850233')
        self.assertLessEqual(lower, delivery)
        self.assertLess(delivery, upper)
        OBSERVATIONS['millisecond_quantization'] = {
            'native_interval_seconds': [str(lower), str(upper)], 'upper_exclusive': True,
            'delivery_seconds': str(delivery),
            'delivery_minus_truncated_point_seconds': str(delivery - lower),
            'frozen_predicate_rejects': True, 'interval_is_compatible': True,
        }

    def test_actual_frozen_outbound_can_log_delivery_after_native_emission(self):
        async def experiment():
            clock = [100.001]
            sent, release = asyncio.Event(), asyncio.Event()
            namespace = {'json': json, 'hashlib': hashlib, 'Path': Path, 'os': os,
                         'time': SimpleNamespace(time=lambda: clock[0]), 'MAX_CAPTURE_BYTES': 65536}
            for name in ('canonical', 'digest', 'Capture'):
                extract(CAPTURE_SOURCE, name, namespace)
            with tempfile.TemporaryDirectory(prefix='chronology-synthetic-') as directory:
                fixture = SimpleNamespace(evidence=Path(directory), tokens=[], redact=lambda text: text,
                                          abort_event=asyncio.Event())
                capture = namespace['Capture'](fixture, 'synthetic')
                capture.append('open')
                payload = json.dumps({'method': 'process/closed', 'params': {'processId': 'p'}}).encode() + b'\n'
                stream = [payload, b'']

                async def readline():
                    return stream.pop(0)

                async def send(text):
                    self.assertEqual(text.encode() + b'\n', payload)
                    clock[0] = 100.0054
                    OBSERVATIONS['post_await_logging'] = {
                        'synthetic_native_emission_seconds': str(clock[0]), 'emittedAtMs': 100005,
                        'payload_equal': True, 'native_or_network_process_started': False,
                    }
                    sent.set()
                    await release.wait()

                outer = {'capture': capture, 'json': json,
                         'process': SimpleNamespace(stdout=SimpleNamespace(readline=readline)),
                         'websocket': SimpleNamespace(send=send)}
                outbound = extract(CAPTURE_SOURCE, 'outbound', outer)
                task = asyncio.create_task(outbound())
                await sent.wait()
                clock[0] = 100.030
                release.set()
                await task
                recorded = [json.loads(line) for line in capture.path.read_text().splitlines()]
                self.assertEqual([r['kind'] for r in recorded], ['open', 'response', 'delivered'])
                self.assertEqual(recorded[-1]['response_sequence'], recorded[-2]['sequence'])
                OBSERVATIONS['post_await_logging'].update(
                    pre_send_close_seconds=str(recorded[-2]['wall_unix_s']),
                    post_await_delivery_log_seconds=str(recorded[-1]['wall_unix_s']),
                    synthetic_capture=recorded)
                return recorded

        captured = asyncio.run(experiment())
        with self.assertRaisesRegex(ValueError, 'Process/app completion chronology inconsistent'):
            frozen_proof(rows(100.0, captured[-2]['wall_unix_s'], captured[-1]['wall_unix_s']), 100005)
        self.assertGreater(Decimal(str(captured[-1]['wall_unix_s'])), Decimal('100.006'))
        self.assertEqual(illustrative_bound(100, 100.001, [100.030], 100005), Decimal('100.03'))

    def test_conservative_bound_rejects_entirely_early_interval_even_with_late_delivery(self):
        with self.assertRaisesRegex(ValueError, 'entirely precedes'):
            illustrative_bound(99, 100.010, [100.030], 100005)

    def test_native_interval_upper_boundary_is_exclusive(self):
        with self.assertRaisesRegex(ValueError, 'entirely precedes'):
            illustrative_bound(99, 100.006, [100.030], 100005)

    def test_delivery_bound_does_not_hide_mutation_overlap(self):
        bound = illustrative_bound(100, 100.001, [100.030], 100005)
        self.assertFalse(bound < Decimal('100.020'))
        self.assertFalse(bound < Decimal('100.030'))
        self.assertTrue(bound < Decimal('100.031'))

    def test_invalid_clock_type_missing_delivery_and_local_inversion_rejected(self):
        cases = [(100, 100.001, [100.030], True), (100, 100.001, [], 100005),
                 (100.002, 100.001, [100.030], 100005), (100, 100.002, [100.001], 100005)]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                illustrative_bound(*case)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ChronologyCounterexamples))
    print(json.dumps({'schema': 'campaign002-chronology-counterexample-1',
                      'scope': 'Synthetic source-extracted diagnostic only; no original assessment replay or upgrade',
                      'snapshot': str(SNAPSHOT), 'snapshot_sha256': sha(SNAPSHOT.read_bytes()),
                      'source_inputs': INPUTS, 'tests': result.testsRun, 'successful': result.wasSuccessful(),
                      'observations': OBSERVATIONS}, indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
