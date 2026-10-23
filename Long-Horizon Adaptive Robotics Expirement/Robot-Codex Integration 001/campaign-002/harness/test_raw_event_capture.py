"""Synthetic native notifications and exact archived bootstrap/runtime parity."""
import ast
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import queue
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ARCHIVE = HERE.parents[2] / 'Architecture Map/releases/RCI001-C02-dev-037/code.zip'
ARCHIVE_SHA = '0c8146287eaa5c06808cf0312bee95ff7fe9e247085760d553630b1eef837c01'
# Preserve the completed RAW v1 proof against its immutable v11 runtime.
# Current transport integration is separately reversed by test_native_owner_bootstrap.
RAW_ARCHIVE = HERE.parents[2] / 'Architecture Map/releases/RCI001-C02-dev-041/code.zip'
RAW_ARCHIVE_SHA = '1b05d7dc1ac46973c64e0a45f34d933a179c99b813a2058eadfd2824f9a99727'
BOOTSTRAP_EDITS = (
    (b'        "bootstrap_requested": args.run_bootstrap, "bootstrap": BOOTSTRAP,\n',
     b'        "bootstrap_requested": args.run_bootstrap, "bootstrap": BOOTSTRAP,\n'
     b'        "experimental_raw_events_requested": True,\n'),
    (b'            "allowProviderModelFallback": False})',
     b'            "allowProviderModelFallback": False, "experimentalRawEvents": True})'),
    (b'        LAUNCH.write_json(args.evidence / "preflight.json", result)',
     b'        LAUNCH.write_json(args.evidence / "preflight.json", {**result,\n'
     b'            "experimental_raw_events_requested": True,\n'
     b'            "experimental_raw_events_thread_start_accepted": True})'),
)
RUNTIME_EDIT = (
    b"bootstrap = load('campaign002_bootstrap_v2', HERE / 'bootstrap_client_v2.py')",
    b"bootstrap = load('campaign002_bootstrap_v3', HERE / 'bootstrap_client_v3.py')",
)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V2 = load('raw_event_baseline_v2', HERE / 'bootstrap_client_v2.py')
V3 = load('raw_event_candidate_v3', HERE / 'bootstrap_client_v3.py')


def raw_event(kind='function_call_output', output='complete synthetic output'):
    return {'method': 'rawResponseItem/completed', 'params': {
        'threadId': 'thread-synthetic', 'turnId': 'turn-synthetic',
        'item': {'type': kind, 'call_id': 'call-synthetic', 'output': output}}}


def wire(value):
    return (json.dumps(value, ensure_ascii=False) + '\n').encode()


class RawEventCaptureTests(unittest.TestCase):
    def client(self, root, redact_tokens=()):
        client = V3.Client.__new__(V3.Client)
        client.args = SimpleNamespace(redact_tokens=redact_tokens)
        client.events = (root / 'events.jsonl').open('x', encoding='utf-8')
        self.addCleanup(client.events.close)
        client.messages = queue.Queue()
        client.pending_events = []
        client.bytes_seen = 0
        client.deadline = time.monotonic() + 5
        client.next_id = 0
        client.process = SimpleNamespace(stdin=io.BytesIO())
        return client

    def test_prepared_native_outputs_are_retained_without_reconstruction(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        root = Path(directory)
        client = self.client(root)
        values = [raw_event(output='π\nfirst\nlast\n'),
                  raw_event('custom_tool_call_output', [{'type': 'input_text', 'text': 'tail'}])]
        for event in values:
            client.messages.put(('stdout', wire(event)))
            self.assertEqual(client.receive(return_notifications=True), event)
        rows = [json.loads(line) for line in (root / 'events.jsonl').read_text().splitlines()]
        self.assertEqual(rows, [{'kind': 'notification', **v} for v in values])
        self.assertEqual(client.pending_events, values)
        self.assertEqual(client.bytes_seen, sum(len(wire(v)) for v in values))
        self.assertEqual(client.process.stdin.getvalue(), b'')
        self.assertEqual(client.next_id, 0)

    def test_existing_capability_redaction_applies_to_raw_output(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        root = Path(directory)
        token = 'synthetic-ephemeral-capability-791'
        client = self.client(root, [token])
        event = raw_event(output='prefix ' + token + ' suffix')
        client.messages.put(('stdout', wire(event)))
        self.assertEqual(client.receive(return_notifications=True), event)
        retained = (root / 'events.jsonl').read_text()
        self.assertNotIn(token, retained)
        self.assertEqual(json.loads(retained)['params']['item']['output'],
                         'prefix [REDACTED_EPHEMERAL_CAPABILITY] suffix')
        self.assertEqual(client.pending_events, [event])

    def test_cumulative_byte_limit_fails_before_retaining_overflow(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        root = Path(directory)
        client = self.client(root)
        first, overflow = raw_event(output='first'), raw_event(output='overflow')
        client.messages.put(('stdout', wire(first)))
        client.messages.put(('stdout', wire(overflow)))
        with patch.object(V3, 'MAX_BYTES', len(wire(first))):
            self.assertEqual(client.receive(return_notifications=True), first)
            with self.assertRaisesRegex(RuntimeError, 'output limit exceeded'):
                client.receive(return_notifications=True)
        rows = [json.loads(line) for line in (root / 'events.jsonl').read_text().splitlines()]
        self.assertEqual(rows, [{'kind': 'notification', **first}])
        self.assertEqual(client.pending_events, [first])
        self.assertEqual(client.process.stdin.getvalue(), b'')

    def test_single_oversized_raw_event_does_not_create_partial_evidence(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        root = Path(directory)
        client = self.client(root)
        event = raw_event(output='large synthetic content')
        client.messages.put(('stdout', wire(event)))
        with patch.object(V3, 'MAX_BYTES', len(wire(event)) - 1):
            with self.assertRaisesRegex(RuntimeError, 'output limit exceeded'):
                client.receive(return_notifications=True)
        self.assertEqual((root / 'events.jsonl').read_bytes(), b'')
        self.assertEqual(client.pending_events, [])

    def test_raw_events_do_not_complete_a_turn_or_send_inference(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        root = Path(directory)
        client = self.client(root)
        raw = raw_event(output='not a turn terminal')
        terminal = {'method': 'turn/completed', 'params': {
            'threadId': 'thread-synthetic', 'turn': {'id': 'turn-synthetic', 'status': 'completed'}}}
        for event in [raw, terminal]:
            client.messages.put(('stdout', wire(event)))
        self.assertEqual(client.wait_turn('turn-synthetic'), terminal['params']['turn'])
        self.assertEqual(client.pending_events, [raw, terminal])
        self.assertEqual(client.next_id, 0)
        self.assertEqual(client.process.stdin.getvalue(), b'')

class BootstrapRequestTests(unittest.TestCase):
    def run_mocked(self, module, root, *, run_bootstrap, reject_thread=False):
        host, home = root / 'host', root / 'synthetic-home'
        host.mkdir(exist_ok=True)
        home.mkdir(exist_ok=True)
        args = SimpleNamespace(host_cwd=host, codex_home=home, timeout=90,
            evidence=root / module.__name__, exec_server_url='ws://127.0.0.1:1234/synthetic',
            code_mode_host_url='http://127.0.0.1:2345', remote_cwd='file:///workspace',
            run_bootstrap=run_bootstrap)
        receipts, calls, sends, waits, closes = {}, [], [], [], []
        config = {'features': {name: False for name in module.DISABLED},
                  'model_provider': 'openai', 'web_search': 'disabled', 'project_doc_max_bytes': 0}
        config['features']['code_mode_host'] = True

        class Native:
            def call(self, method, params, *, private=False):
                calls.append((method, copy.deepcopy(params), private))
                if method == 'config/read': return {'config': config}
                if method == 'account/read': return {'account': {'type': 'chatgpt'}}
                if method == 'environment/status':
                    return {'status': 'unknown' if params['environmentId'] == 'local' else 'ready'}
                if method == 'environment/info':
                    return {'shell': {'path': '/usr/bin/bash'}, 'cwd': 'file:///workspace'}
                if method == 'thread/start':
                    if reject_thread: raise RuntimeError('synthetic thread/start rejection')
                    return {'model': module.LAUNCH.MODEL, 'modelProvider': 'openai',
                            'reasoningEffort': module.LAUNCH.EFFORT, 'instructionSources': [],
                            'thread': {'id': 'thread-synthetic'}}
                if method == 'mcpServerStatus/list': return {'data': []}
                if method == 'turn/start': return {'turn': {'id': 'turn-synthetic'}}
                return {}
            def send(self, message): sends.append(copy.deepcopy(message))
            def log(self, message): pass
            def wait_turn(self, turn_id):
                waits.append(turn_id)
                return {'id': turn_id, 'status': 'completed'}
            def close(self): closes.append(True)

        fake_launch = SimpleNamespace(MODEL=module.LAUNCH.MODEL, EFFORT=module.LAUNCH.EFFORT,
            CODEX=Path('synthetic-native-not-launched.exe'), utc=lambda: 'synthetic-time',
            sha256=lambda path: '0' * 64, config_args=lambda config: [],
            clean_environment=lambda path: {'SYNTHETIC_ENVIRONMENT': '1'},
            write_json=lambda path, value: receipts.update({path.name: copy.deepcopy(value)}))
        with patch.object(module, 'LAUNCH', fake_launch), patch.object(module, 'Client', return_value=Native()) as create:
            result = module.run(args)
        return result, receipts, calls, sends, waits, closes, create.call_args

    def test_preflight_only_enables_raw_option_without_any_model_start(self):
        with tempfile.TemporaryDirectory() as directory:
            result, receipts, calls, sends, waits, closes, _ = self.run_mocked(
                V3, Path(directory), run_bootstrap=False)
            self.assertTrue(result['success'])
            self.assertFalse(result['model_started'])
            threads = [p for method, p, _ in calls if method == 'thread/start']
            self.assertEqual(len(threads), 1)
            self.assertIs(threads[0]['experimentalRawEvents'], True)
            self.assertFalse(any(method == 'turn/start' for method, _, _ in calls))
            self.assertTrue(receipts['launch.json']['experimental_raw_events_requested'])
            self.assertTrue(receipts['preflight.json']['experimental_raw_events_requested'])
            self.assertTrue(receipts['preflight.json']['experimental_raw_events_thread_start_accepted'])
            self.assertEqual(sends, [{'method': 'initialized', 'params': {}}])
            self.assertEqual(waits, [])
            self.assertEqual(closes, [True])

    def test_all_other_rpc_config_bootstrap_and_result_behavior_matches_v2(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = self.run_mocked(V2, root, run_bootstrap=True)
            candidate = self.run_mocked(V3, root, run_bootstrap=True)
            normalized = copy.deepcopy(candidate[:6])
            normalized[1]['launch.json'].pop('experimental_raw_events_requested')
            normalized[1]['preflight.json'].pop('experimental_raw_events_requested')
            normalized[1]['preflight.json'].pop('experimental_raw_events_thread_start_accepted')
            for method, params, _ in normalized[2]:
                if method == 'thread/start': params.pop('experimentalRawEvents')
            self.assertEqual(normalized, baseline[:6])
            turns = [p for method, p, _ in candidate[2] if method == 'turn/start']
            self.assertEqual(len(turns), 1)
            self.assertEqual(turns[0]['input'], [{'type': 'text', 'text': V2.BOOTSTRAP, 'text_elements': []}])
            self.assertEqual(candidate[4], ['turn-synthetic'])
            self.assertEqual(candidate[6].args[1:], baseline[6].args[1:])

    def test_rejected_raw_option_has_no_accepted_receipt_or_fallback_turn(self):
        with tempfile.TemporaryDirectory() as directory:
            result, receipts, calls, _, waits, closes, _ = self.run_mocked(
                V3, Path(directory), run_bootstrap=True, reject_thread=True)
            self.assertFalse(result['success'])
            self.assertFalse(result['model_started'])
            self.assertIn('thread/start rejection', result['error'])
            self.assertNotIn('preflight.json', receipts)
            self.assertEqual(sum(method == 'thread/start' for method, _, _ in calls), 1)
            self.assertFalse(any(method == 'turn/start' for method, _, _ in calls))
            self.assertEqual(waits, [])
            self.assertEqual(closes, [True])


class ArchivedSourceParityTests(unittest.TestCase):
    def raw_runtime(self):
        self.assertEqual(hashlib.sha256(RAW_ARCHIVE.read_bytes()).hexdigest(), RAW_ARCHIVE_SHA)
        with zipfile.ZipFile(RAW_ARCHIVE) as archive:
            return archive.read((HERE / 'runtime.py').relative_to(REPO).as_posix())

    def test_mechanical_reversal_recovers_exact_dev037_bytes(self):
        self.assertEqual(hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(), ARCHIVE_SHA)
        with zipfile.ZipFile(ARCHIVE) as archive:
            old = archive.read((HERE / 'bootstrap_client_v2.py').relative_to(REPO).as_posix())
            self.assertEqual((HERE / 'bootstrap_client_v2.py').read_bytes(), old)
            candidate = (HERE / 'bootstrap_client_v3.py').read_bytes()
            for before, after in BOOTSTRAP_EDITS:
                self.assertEqual(candidate.count(after), 1)
                candidate = candidate.replace(after, before)
            self.assertEqual(candidate, old)
            current = self.raw_runtime()
            self.assertEqual(current.count(RUNTIME_EDIT[1]), 1)
            restored = current.replace(RUNTIME_EDIT[1], RUNTIME_EDIT[0])
            self.assertEqual(restored, archive.read((HERE / 'runtime.py').relative_to(REPO).as_posix()))

    def test_every_client_and_runtime_method_is_unchanged(self):
        with zipfile.ZipFile(ARCHIVE) as archive:
            for name, old_path, new_path in [('Client', HERE / 'bootstrap_client_v2.py', HERE / 'bootstrap_client_v3.py'),
                                              ('Runtime', HERE / 'runtime.py', HERE / 'runtime.py')]:
                old = ast.parse(archive.read(old_path.relative_to(REPO).as_posix()))
                new = ast.parse(self.raw_runtime() if name == 'Runtime' else new_path.read_bytes())
                old_cls = next(n for n in old.body if isinstance(n, ast.ClassDef) and n.name == name)
                new_cls = next(n for n in new.body if isinstance(n, ast.ClassDef) and n.name == name)
                self.assertEqual(ast.dump(old_cls, include_attributes=False), ast.dump(new_cls, include_attributes=False))


if __name__ == '__main__':
    unittest.main()
