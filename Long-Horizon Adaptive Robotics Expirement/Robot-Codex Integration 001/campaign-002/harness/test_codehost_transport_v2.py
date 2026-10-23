"""Bounded synthetic codehost status/EOF reproduction and transport regressions."""
import ast
import asyncio
import hashlib
import importlib.util
import json
import io
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
RCI = HERE.parents[1]
ORIGINAL_BRIDGE = RCI / 'isolation-session-9/wsl/codehost_bridge.py'
ORIGINAL_INSIDE = RCI / 'readiness-session-10/boundary/inside.py'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Writer:
    def __init__(self):
        self.closed = False
        self.data = bytearray()
    def write(self, value): self.data.extend(value)
    async def drain(self): pass
    def close(self): self.closed = True


class Process:
    def __init__(self, *, exit_code=0, eof=True, stderr=b''):
        self.returncode = exit_code
        self.stdin = Writer()
        self.stdout = asyncio.StreamReader()
        self.stderr = asyncio.StreamReader()
        self.stderr.feed_data(stderr)
        self.stderr.feed_eof()
        if eof: self.stdout.feed_eof()
    async def wait(self): return self.returncode


def fixture(root):
    return SimpleNamespace(evidence=root, abort_event=threading.Event(),
        client_finishing=threading.Event(), run='/synthetic', redact=lambda value: value,
        argv=lambda mode: ['synthetic-codehost'])


async def retire(process, identity, path):
    return await process.wait()


def reproduce_masked_child_exit():
    tree = ast.parse(ORIGINAL_INSIDE.read_text())
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                and isinstance(n.test, ast.Compare)
                and any(isinstance(c, ast.List) and len(c.elts) == 1
                        and isinstance(c.elts[0], ast.Constant) and c.elts[0].value == 'codehost'
                        for c in n.test.comparators))
    child = SimpleNamespace(poll=lambda: 17, wait=lambda **kw: 17,
                            terminate=lambda: None, kill=lambda: None)
    channel = SimpleNamespace(settimeout=lambda v: None, recv=lambda n: b'')
    namespace = {'subprocess': SimpleNamespace(Popen=lambda *a, **k: child, DEVNULL=-1, TimeoutExpired=TimeoutError),
                 'socket': SimpleNamespace(create_connection=lambda *a: channel),
                 'sys': SimpleNamespace(stderr=None), 'time': time,
                 'threading': SimpleNamespace(Thread=lambda **k: SimpleNamespace(start=lambda: None))}
    returned = True
    try:
        exec(compile(ast.Module(body=node.body, type_ignores=[]), str(ORIGINAL_INSIDE), 'exec'), namespace)
    except SystemExit:
        returned = False
    return {'case': 'original_namespace_masked_child_exit', 'synthetic_child_exit_code': 17,
            'original_branch_returned_normally': returned,
            'reproduced': returned, 'scope': 'Exact original codehost AST branch, fake process/socket; no Linux/model/physics.'}


async def reproduce_clean_early_eof():
    original = load('original_codehost_reproduction', ORIGINAL_BRIDGE)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        subject = fixture(root)
        process = Process()
        async def create(*a, **kw): return process
        async def callback(url):
            from urllib.parse import urlsplit
            reader, writer = await asyncio.open_connection('127.0.0.1', urlsplit(url).port)
            data = await asyncio.wait_for(reader.read(1), 2)
            writer.close()
            await writer.wait_closed()
            return data
        with patch.object(original.asyncio, 'create_subprocess_exec', create), \
                patch.dict(sys.modules, {'retirement': SimpleNamespace(retire=retire)}):
            value = await original.run(subject, callback)
        receipt = json.loads((root / 'codehost-1-bridge.json').read_text())
        return {'case': 'original_bridge_clean_early_eof', 'callback_returned_empty': value == b'',
                'client_finishing': subject.client_finishing.is_set(),
                'abort_event': subject.abort_event.is_set(), 'bridge_receipt': receipt,
                'reproduced': value == b'' and not subject.abort_event.is_set(),
                'scope': 'Original bridge, fake child, real local TCP EOF; no Linux/model/physics.'}


class OriginalReproductionTests(unittest.TestCase):
    def test_original_namespace_masks_nonzero_child(self):
        self.assertTrue(reproduce_masked_child_exit()['reproduced'])
    def test_original_bridge_accepts_unexpected_clean_eof(self):
        self.assertTrue(asyncio.run(reproduce_clean_early_eof())['reproduced'])


def namespace_output(**changes):
    closed = {'qualified': True, 'reason': 'owner_input_eof', 'stdin_eof': True,
              'child_exit_before_cleanup': None, 'child_exit_code': -15,
              'terminate_sent': True, 'kill_sent': False, 'error_type': None,
              'diagnostic_streams_complete': True,
              'to_host': 0, 'from_host': 0, **changes}
    records = [{'kind': 'open'}, {'kind': 'child_started', 'child_pid': 1}, {'kind': 'connected'},
               {'kind': 'stdin_eof', 'to_host': 0, 'from_host': 0},
               {'kind': 'channel_end', 'reason': closed['reason'], 'stdin_eof': True,
                'child_exit_before_cleanup': closed['child_exit_before_cleanup'], 'error_type': None,
                'to_host': 0, 'from_host': 0},
               *[{'kind': 'child_diagnostic', 'stream': name, 'bytes': 0,
                  'sha256': hashlib.sha256(b'').hexdigest(), 'truncated': False} for name in ('stdout', 'stderr')],
               {'kind': 'closed', **closed}]
    return b''.join(('RCI_CODEHOST_V2 ' + json.dumps({'schema': 'campaign002-codehost-namespace-2',
         'sequence': i, 'wall_unix_s': time.time(), 'monotonic_s': time.monotonic(), **row}) + '\n').encode()
         for i, row in enumerate(records, 1))


class NewTransportTests(unittest.TestCase):
    def setUp(self):
        self.bridge = load('tested_codehost_bridge_v2', HERE / 'codehost_bridge_v2.py')
        self.inside = load('tested_codehost_inside_v2', HERE / 'codehost_inside_v2.py')
        self.entry = load('tested_codehost_entry_v2', HERE / 'codehost_entry_v2.py')

    def test_gateway_classes_are_exact_original_ast(self):
        original = ast.parse(ORIGINAL_INSIDE.read_text())
        revised = ast.parse((HERE / 'codehost_inside_v2.py').read_text())
        for name in ('Handler', 'BoundedHTTPServer'):
            find = lambda tree: next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
            self.assertEqual(ast.dump(find(original), include_attributes=False),
                             ast.dump(find(revised), include_attributes=False))

    def test_namespace_changes_exactly_one_readonly_source_binding(self):
        original = load('original_namespace_test', RCI / 'readiness-session-10/boundary/namespace.py')
        source = self.entry.BOUNDARY
        argv = original.command(Path('/runtime/workspace'), Path('/runtime/gateway.sock'), source, '/codex', '/codehost')
        changed = self.entry.replace_inside(argv, source / 'inside.py', HERE / 'codehost_inside_v2.py')
        differences = [i for i, pair in enumerate(zip(argv, changed)) if pair[0] != pair[1]]
        self.assertEqual(len(argv), len(changed))
        self.assertEqual(len(differences), 1)
        i, = differences
        self.assertEqual(changed[i - 1:i + 2], ['--ro-bind', str(HERE / 'codehost_inside_v2.py'), '/inside.py'])
        with self.assertRaises(ValueError):
            self.entry.replace_inside(argv + ['extra'], source / 'inside.py', 'fake')

    def test_namespace_relay_nonzero_child_is_not_masked(self):
        fd, writer = os.pipe()
        records = []
        child = SimpleNamespace(poll=lambda: 17, wait=lambda **kw: 17)
        channel = SimpleNamespace(recv=lambda n: b'', shutdown=lambda how: None)
        try:
            result = self.inside.relay(child, channel, fd, io.BytesIO(), lambda kind, **kw: records.append({'kind': kind, **kw}))
            self.assertEqual(result, 1)
            self.assertEqual(records[-1]['child_exit_code'], 17)
            self.assertFalse(records[-1]['qualified'])
        finally:
            os.close(writer)
            os.close(fd)

    def test_namespace_owner_input_eof_preserves_explicit_termination(self):
        fd, writer = os.pipe()
        os.close(writer)
        records, ready = [], threading.Event()
        code = [None]
        child = SimpleNamespace(poll=lambda: code[0], wait=lambda **kw: code[0],
                                terminate=lambda: code.__setitem__(0, -15))
        channel = SimpleNamespace(shutdown=lambda how: ready.set(), recv=lambda n: (ready.wait(2) and b''))
        try:
            result = self.inside.relay(child, channel, fd, io.BytesIO(), lambda kind, **kw: records.append({'kind': kind, **kw}))
            self.assertEqual(result, 0)
            self.assertTrue(records[-1]['qualified'])
            self.assertEqual(records[-1]['reason'], 'owner_input_eof')
            self.assertTrue(records[-1]['terminate_sent'])
        finally: os.close(fd)

    def test_status_shaped_child_logs_are_only_opaque_hashes(self):
        forged = b'RCI_CODEHOST_V2 {"kind":"closed","qualified":true}\n'
        child = SimpleNamespace(stdout=io.BytesIO(forged), stderr=io.BytesIO(forged), poll=lambda: 0)
        records, failed = [], threading.Event()
        finish = self.inside.diagnostic_drains(child, lambda kind, **kw: records.append({'kind': kind, **kw}), failed)
        self.assertTrue(finish())
        self.assertFalse(failed.is_set())
        self.assertEqual({r['kind'] for r in records}, {'child_diagnostic'})
        self.assertTrue(all(r['sha256'] == hashlib.sha256(forged).hexdigest() for r in records))
        self.assertNotIn('qualified', json.dumps(records))

    async def scenario(self, mode='normal', stderr=None, wrapper_exit=0):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subject = fixture(root)
            process = Process(exit_code=wrapper_exit, eof=mode in ('early', 'early_then_finish'),
                              stderr=namespace_output() if stderr is None else stderr)
            def close():
                process.stdin.closed = True
                if not process.stdout.at_eof(): process.stdout.feed_eof()
            process.stdin.close = close
            async def create(*a, **kw): return process
            async def retire_v2(proc, identity, path):
                path.write_text(json.dumps({'qualified': True, 'windows_exit_code': proc.returncode}))
            async def callback(url):
                from urllib.parse import urlsplit
                reader, writer = await asyncio.open_connection('127.0.0.1', urlsplit(url).port)
                if mode in ('early', 'early_then_finish'):
                    await asyncio.wait_for(reader.read(1), 2)
                    if mode == 'early_then_finish': subject.client_finishing.set()
                else:
                    if mode == 'concurrent':
                        other, other_writer = await asyncio.open_connection('127.0.0.1', urlsplit(url).port)
                        self.assertEqual(await asyncio.wait_for(other.read(1), 2), b'')
                        other_writer.close(); await other_writer.wait_closed()
                    subject.client_finishing.set()
                writer.close()
                await writer.wait_closed()
            error = None
            with patch.object(self.bridge.asyncio, 'create_subprocess_exec', create), \
                    patch.dict(sys.modules, {'retirement': SimpleNamespace(retire=retire_v2)}):
                try: await self.bridge.run(subject, callback)
                except RuntimeError as failure: error = str(failure)
            records = [json.loads(line) for line in (root / 'codehost-transport-v2.jsonl').read_text().splitlines()]
            receipt = json.loads((root / 'codehost-1-bridge.json').read_text())
            return error, subject.abort_event.is_set(), records, receipt

    def test_normal_owner_shutdown_has_complete_bound_receipts(self):
        error, aborted, records, receipt = asyncio.run(self.scenario())
        self.assertIsNone(error)
        self.assertFalse(aborted)
        self.assertTrue(receipt['qualified'])
        self.assertEqual(records[-1]['kind'], 'closed')
        self.assertEqual(records[-1]['failures'], [])
        self.assertEqual(receipt['namespace_record_count'], 8)
        self.assertEqual(receipt['first_pump_end']['client_finishing'], True)
        previous = None
        for index, row in enumerate(records, 1):
            self.assertEqual(row['sequence'], index)
            self.assertEqual(row['previous_sha256'], previous)
            clean = {k: v for k, v in row.items() if k != 'record_sha256'}
            self.assertEqual(row['record_sha256'], self.bridge.sha(self.bridge.canonical(clean)))
            previous = row['record_sha256']

    def test_unexpected_clean_early_eof_is_fail_closed(self):
        error, aborted, records, receipt = asyncio.run(self.scenario('early'))
        self.assertIsNotNone(error)
        self.assertTrue(aborted)
        self.assertFalse(receipt['qualified'])
        self.assertFalse(receipt['client_finishing_at_first_end'])
        self.assertIn('unexpected_download_eof', records[-1]['failures'])

    def test_later_owner_finish_cannot_launder_earlier_unexpected_eof(self):
        error, aborted, records, receipt = asyncio.run(self.scenario('early_then_finish'))
        self.assertIsNotNone(error)
        self.assertTrue(aborted)
        self.assertFalse(receipt['first_pump_end']['client_finishing'])
        self.assertIn('unexpected_download_eof', records[-1]['failures'])

    def test_nonzero_wrapper_or_namespace_child_and_missing_metadata_fail(self):
        for kwargs in ({'wrapper_exit': 17}, {'stderr': namespace_output(child_exit_code=17, qualified=False)},
                       {'stderr': b''}, {'stderr': namespace_output()[:-1]}):
            with self.subTest(kwargs=kwargs):
                error, aborted, _, receipt = asyncio.run(self.scenario(**kwargs))
                self.assertIsNotNone(error)
                self.assertTrue(aborted)
                self.assertFalse(receipt['qualified'])

    def test_single_client_rejection_is_retained_without_policy_change(self):
        error, aborted, records, receipt = asyncio.run(self.scenario('concurrent'))
        self.assertIsNone(error)
        self.assertFalse(aborted)
        self.assertTrue(receipt['qualified'])
        denied = [row for row in records if row['kind'] == 'connection_denied']
        self.assertEqual(len(denied), 1)
        self.assertEqual(denied[0]['reason'], 'single_active_client')
        self.assertEqual(records[-1]['denied'], 1)

    def test_metadata_bounds_abort_without_silent_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            subject = fixture(Path(directory))
            with patch.object(self.bridge, 'MAX_LEDGER_BYTES', 1):
                ledger = self.bridge.Ledger(subject)
                with self.assertRaises(RuntimeError): ledger.emit('open')
            self.assertTrue(subject.abort_event.is_set())
        with patch.object(self.bridge, 'MAX_STDERR_BYTES', 8):
            error, aborted, _, receipt = asyncio.run(self.scenario())
            self.assertIsNotNone(error)
            self.assertTrue(aborted)
            self.assertTrue(receipt['stderr']['truncated'])

    def test_real_local_h2_probe_driver_fin_and_rst_owner_markers(self):
        probe = load('tested_codehost_probe', HERE / 'codehost_probe.py')
        async def scenario(kind):
            with tempfile.TemporaryDirectory() as directory:
                subject = fixture(Path(directory))
                finished = asyncio.Event()
                async def handler(reader, writer):
                    try:
                        preface = await reader.readexactly(33)
                        self.assertTrue(preface.startswith(b'PRI * HTTP/2.0'))
                        writer.write(b'\x00\x00\x00\x04\x00\x00\x00\x00\x00')
                        await writer.drain()
                        await reader.readexactly(9)
                        ping = await reader.readexactly(17)
                        self.assertEqual(ping[:5], b'\x00\x00\x08\x06\x00')
                        writer.write(ping[:4] + b'\x01' + ping[5:])
                        await writer.drain()
                        try: await reader.read(1)
                        except ConnectionResetError: pass
                    finally:
                        writer.close()
                        try: await writer.wait_closed()
                        except ConnectionResetError: pass
                        finished.set()
                async with await asyncio.start_server(handler, '127.0.0.1', 0) as server:
                    result = await probe.h2_client('http://127.0.0.1:' + str(server.sockets[0].getsockname()[1]), subject, kind)
                    await asyncio.wait_for(finished.wait(), 2)
                self.assertTrue(result['passed'])
                self.assertGreaterEqual(result['idle_seconds'], 2)
                records = [json.loads(line) for line in (subject.evidence / 'client/events.jsonl').read_text().splitlines()]
                self.assertEqual([r['kind'] for r in records], ['client_finishing_before_close', 'probe_client_closed'])
                self.assertLessEqual(records[0]['monotonic_s'], records[1]['monotonic_s'])
                self.assertTrue(subject.client_finishing.is_set())
        for kind in ('normal', 'reset'):
            with self.subTest(kind=kind): asyncio.run(scenario(kind))


def reproduction_report(path):
    digest = lambda raw: hashlib.sha256(raw).hexdigest()
    source = Path(__file__).read_bytes()
    report = {'schema': 'campaign002-codehost-transport-reproduction-1', 'wall_unix_s': time.time(),
              'scope': 'Synthetic engineering reproduction, not smoke005 causality or scientific qualification.',
              'sources': {str(p): digest(p.read_bytes()) for p in (ORIGINAL_BRIDGE, ORIGINAL_INSIDE)},
              'reproduction_source_sha256': digest(source), 'reproduction_source_utf8': source.decode(),
              'cases': [reproduce_masked_child_exit(), asyncio.run(reproduce_clean_early_eof())]}
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'reproduced': all(c['reproduced'] for c in report['cases']), 'path': str(path)}))


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--reproduce':
        reproduction_report(sys.argv[2])
    else:
        unittest.main()
