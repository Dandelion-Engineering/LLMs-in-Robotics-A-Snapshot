"""Synthetic preflight evidence/negative tests; no native process or model."""
import base64
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('preflight_under_test', HERE / 'raw_event_preflight.py')
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)
B = P.dependency('bootstrap_client_v3')
T = P.dependency('transport_integrity')


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + '\n', encoding='utf-8')


def get(path):
    return json.loads(path.read_bytes())


def ledger(path, rows):
    previous = None
    records = []
    for number, fields in enumerate(rows, 1):
        row = {'schema': T.TRANSPORT_SCHEMA, 'sequence': number, 'previous_sha256': previous,
               'wall_unix_s': float(number), 'monotonic_s': float(number), **fields}
        row['record_sha256'] = T.digest(T.canonical(row))
        records.append(T.canonical(row))
        previous = row['record_sha256']
    path.write_bytes(b'\n'.join(records) + b'\n')


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.directory = self.enterContext(tempfile.TemporaryDirectory())
        self.base = Path(self.directory)
        self.root = self.base / 'evidence'
        self.root.mkdir()
        self.native = self.base / 'native-not-executed.bin'
        self.native.write_bytes(b'synthetic-native-identity-only')
        self.enterContext(patch.object(B.LAUNCH, 'CODEX', self.native))
        names = set(P.required_sources()) | set(T.SOURCE_NAMES)
        self.frozen = {'revision': 'synthetic-revision', 'sources': {name: P.binding(P.REPO / name) for name in names}}
        self.snapshot = self.base / 'snapshot.json'
        put(self.snapshot, self.frozen)
        self.source = {'schema': 'campaign002-raw-preflight-source-1', 'run_id': 'synthetic-no-model',
                       'framework_revision': self.frozen['revision'], 'snapshot_sha256': P.binding(self.snapshot)['sha256'],
                       'sources': self.frozen['sources'], 'native_binary': {'path': str(self.native), **P.binding(self.native)}}
        put(self.root / 'source-binding.json', self.source)
        put(self.root / 'execution.json', {'run_id': self.source['run_id'], 'preflight': True,
            'timeout_seconds': 90, 'completed': True, 'exit_status': 0, 'error_type': None})
        self.make_runtime()
        self.enterContext(patch.object(P, 'validate_snapshot', return_value=self.frozen))

    def make_runtime(self):
        self.runtime = self.root / 'runtime'
        self.runtime.mkdir()
        self.namespace = '/var/tmp/robot-codex-session10/' + 'a' * 32
        self.checks = {f'boundary-{i}': True for i in range(45)}
        canary = {'qualified': True, 'checks': self.checks}
        put(self.runtime / 'canary-stdout.json', canary)
        put(self.runtime / 'codehost-canary-stdout.json', {'host_qualified': True, 'model_calls': 0,
            'enabled_tools': [], 'checks': {'tools': [], 'all_tools_count': 0,
                'constructor_process_type': 'undefined',
                'apis': {name: 'undefined' for name in ('process', 'require', 'fetch', 'Deno', 'Bun', 'WebSocket', 'XMLHttpRequest')},
                'imports': {name: 'denied' for name in ('node:fs', 'file:///etc/passwd', 'https://example.invalid/')}}})
        put(self.runtime / 'runtime-location.json', {'run': self.namespace, 'workspace': self.namespace + '/workspace',
            'durable_backing': True, 'setup': {'protected_exist': {str(i): True for i in range(4)},
                                            'outside_loopback_control': True}})
        put(self.runtime / 'cleanup.json', {'clean': True, 'errors': []})
        put(self.runtime / 'orchestration-result.json', {'success': True, 'model_started': False,
             'cleanup_clean': True, 'durable_retention_verified': True})
        for name in ('runtime-before-close.json', 'runtime-after-close.json'):
            put(self.runtime / name, {'files': {}, 'total_bytes': 0})
        put(self.runtime / 'gateway-calls.json', [{'method': 'GET', 'path': '/status', 'status': 200}])
        put(self.runtime / 'bridge-security.json', {'wrong_path_denied': True, 'second_active_connection_denied': True})
        put(self.runtime / 'executor-file-probe.json', {'qualified': True})
        put(self.runtime / 'executor-write-probe.json', {'allowed': {'result': {}}, 'protected': {'error': {}}})
        stdout = json.dumps(canary) + '\n'
        native_exit = {'processId': 'canary', 'seq': 2, 'exitCode': 0}
        put(self.runtime / 'executor-process-probe.json', {'stdout': stdout, 'stderr': '', 'exit': [native_exit]})
        capture_module = P.dependency('executor_capture')
        fixture = SimpleNamespace(evidence=self.runtime, tokens=[], redact=lambda value: value, abort_event=threading.Event())
        for number in (1, 2):
            capture = capture_module.Capture(fixture, number)
            capture.append('open')
            if number == 1:
                capture.append('request', {'id': 9, 'method': 'process/start', 'params': {
                    'argv': ['/usr/bin/python3', '-I', '-B', '/canary.py'],
                    'cwd': 'file:///workspace', 'processId': 'canary', 'tty': False}})
                messages = [{'id': 9, 'result': {'processId': 'canary'}},
                    {'method': 'process/output', 'params': {'processId': 'canary', 'seq': 1, 'stream': 'stdout',
                         'chunk': base64.b64encode(stdout.encode()).decode()}},
                    {'method': 'process/exited', 'params': native_exit},
                    {'method': 'process/closed', 'params': {'processId': 'canary', 'seq': 3}}]
                for message in messages:
                    sequence = capture.append('response', message)
                    capture.append('delivered', response_sequence=sequence)
            capture.append('closed', failures=[])
            put(self.runtime / f'executor-{number}-exit.json', {'exit_code': 0, 'stderr_bytes': 0})
            put(self.runtime / f'executor-{number}-retirement.json', {'qualified': True,
                'identity_path': f'{self.namespace}/executor-{number}.json', 'normal_wait_timed_out': False,
                'windows_wrapper_killed_after_linux_retired': False, 'windows_exit_code': 0,
                'observations': [{'retired': True, 'namespace_evidence_available': True, 'outer_same_process': False,
                                  'namespace_members': [], 'namespace_ids': [100 + number]}]})
        self.bridge_rows = [{'kind': 'open', 'sources': {name: self.frozen['sources'][name] for name in T.BRIDGE_SOURCE_NAMES},
                            'max_connections': 16, 'max_ledger_bytes': 1048576, 'max_stderr_bytes': 1048576},
                           {'kind': 'listening'}, {'kind': 'closed', 'accepted': 0, 'denied': 0, 'failures': []}]
        ledger(self.runtime / 'codehost-transport-v2.jsonl', self.bridge_rows)
        effective = {'mcp_count': 0, 'mcp_all_disabled': True, 'disabled_mcp_names': [], 'header_names_count': 0,
            'disabled_feature_count': len(B.DISABLED - {'code_mode_host'}), 'remote_code_mode_host_configured': True,
            'automatic_project_documents': False, 'custom_instructions': False, 'provider': 'openai', 'web_search': 'disabled'}
        self.client_result = {'success': True, 'model_started': False, 'preflight_passed': True,
            'thread_id': 'synthetic-thread', 'auth_type': 'chatgpt', 'model_effective': B.LAUNCH.MODEL,
            'effort_effective': B.LAUNCH.EFFORT, 'instruction_sources': [], 'mcp_active_servers': [],
            'effective_config': effective, 'mcp_catalog': []}
        put(self.runtime / 'client/result.json', self.client_result)
        put(self.runtime / 'client/preflight.json', {**self.client_result, 'success': False,
            'experimental_raw_events_requested': True, 'experimental_raw_events_thread_start_accepted': True})
        launch = {'bootstrap': B.BOOTSTRAP, 'bootstrap_requested': False, 'experimental_raw_events_requested': True,
            'remote_cwd': 'file:///workspace', 'host_cwd': str(self.runtime / 'control'), 'timeout_seconds': 90,
            'model_requested': B.LAUNCH.MODEL, 'reasoning_effort_requested': B.LAUNCH.EFFORT,
            'outer_namespace_authoritative': True, 'remote_code_mode_host_configured': True,
            'executor_url_recorded': False, 'binary': str(self.native), 'binary_sha256': P.binding(self.native)['sha256'],
            'mcp_headers_disabled': 0, 'config_overrides': B.overrides([], True)}
        put(self.runtime / 'client/launch.json', launch)
        methods = ['initialize', 'config/read', 'account/read', 'environment/status', 'environment/add',
                   'environment/info', 'thread/start', 'mcpServerStatus/list', 'environment/status', 'environment/status']
        self.events = [{'kind': 'request', 'id': number, 'method': method, 'params': {}}
                       for number, method in enumerate(methods, 1)]
        self.events[6]['params'] = {'cwd': str(self.runtime / 'control'), 'model': B.LAUNCH.MODEL,
            'modelProvider': 'openai', 'approvalPolicy': 'never', 'sandbox': 'danger-full-access',
            'developerInstructions': '', 'environments': [{'environmentId': 'robot-qualified',
                'cwd': '/workspace', 'runtimeWorkspaceRoots': ['/workspace']}], 'ephemeral': True,
            'dynamicTools': [], 'selectedCapabilityRoots': [], 'allowProviderModelFallback': False,
            'experimentalRawEvents': True}
        self.events.insert(7, {'kind': 'response', 'id': 7, 'method': 'thread/start', 'result': {
            'model': B.LAUNCH.MODEL, 'modelProvider': 'openai', 'reasoningEffort': B.LAUNCH.EFFORT,
            'instructionSources': [], 'thread': {'id': 'synthetic-thread'}}})
        self.thread_request = self.events[6]
        public_values = {1: {}, 4: {'status': 'unknown'},
                         6: {'cwd': 'file:///workspace', 'shell': {'path': '/usr/bin/bash'}},
                         9: {'status': 'ready'}, 10: {'status': 'unknown'}}
        expanded = []
        for event in self.events:
            expanded.append(event)
            if event['kind'] == 'request' and event['id'] in public_values:
                expanded.append({'kind': 'response', 'id': event['id'], 'method': event['method'],
                                 'result': public_values[event['id']]})
            if event['kind'] == 'request' and event['id'] == 8:
                expanded.append({'kind': 'mcp_inventory_summary', 'entries': [], 'has_more': False})
        self.events = expanded
        self.events += [{'kind': 'client_finishing_before_close', 'schema': 'campaign002-client-finishing-1',
                         'wall_unix_s': 10.0, 'monotonic_s': 10.0}, {'kind': 'client_shutdown', 'exit_code': 0}]
        self.write_events()

    def write_events(self):
        (self.runtime / 'client/events.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in self.events), encoding='utf-8')

    def assess(self):
        return P.assess(self.root, self.snapshot)

    def mutate(self, relative, change):
        path = self.root / relative
        value = get(path)
        change(value)
        put(path, value)

    def test_complete_metadata_only_receipts_pass_and_replay_exactly(self):
        result = self.assess()
        self.assertTrue(result['passed'], result['errors'])
        self.assertEqual(result['schema'], P.SCHEMA)
        self.assertEqual(result, self.assess())
        self.assertEqual(result['model_calls'], 0)
        self.assertEqual(result['lifecycle']['codehost_connections'], 0)
        self.assertFalse(result['lifecycle']['raw_tool_payload_path_tested'])
        self.assertEqual(result['lifecycle']['namespace_retirements'], ['executor-1-retirement.json', 'executor-2-retirement.json'])

    def test_missing_or_false_raw_option_rejected(self):
        for value in (None, False, 1):
            with self.subTest(value=value):
                self.thread_request['params']['experimentalRawEvents'] = value
                self.write_events()
                self.assertFalse(self.assess()['passed'])

    def test_extra_thread_model_turn_or_raw_tool_event_rejected(self):
        original = copy.deepcopy(self.events)
        for event in (copy.deepcopy(self.thread_request), {'kind': 'request', 'id': 11, 'method': 'turn/start'},
                      {'kind': 'notification', 'method': 'rawResponseItem/completed', 'params': {}}):
            with self.subTest(event=event):
                self.events = original[:-2] + [event] + original[-2:]
                self.write_events()
                self.assertFalse(self.assess()['passed'])

    def test_policy_bootstrap_config_auth_or_native_identity_change_rejected(self):
        cases = [('runtime/client/launch.json', 'bootstrap', 'different'),
                 ('runtime/client/launch.json', 'bootstrap_requested', True),
                 ('runtime/client/launch.json', 'binary_sha256', '0' * 64),
                 ('runtime/client/result.json', 'auth_type', 'api_key'),
                 ('runtime/client/result.json', 'effort_effective', 'low')]
        for name, key, value in cases:
            path = self.root / name
            raw = path.read_bytes()
            with self.subTest(name=name, key=key):
                self.mutate(name, lambda obj: obj.update({key: value}))
                self.assertFalse(self.assess()['passed'])
            path.write_bytes(raw)
        self.mutate('runtime/client/launch.json', lambda obj: obj['config_overrides'].update({'web_search': 'live'}))
        self.assertFalse(self.assess()['passed'])

    def test_false_exit_or_missing_owner_receipt_rejected(self):
        for value in (False, 1, None):
            self.events[-1]['exit_code'] = value
            self.write_events()
            self.assertFalse(self.assess()['passed'])
        self.events.pop(-2)
        self.write_events()
        self.assertFalse(self.assess()['passed'])

    def test_incomplete_log_and_duplicate_json_keys_rejected(self):
        path = self.runtime / 'client/events.jsonl'
        path.write_bytes(path.read_bytes().rstrip())
        self.assertFalse(self.assess()['passed'])
        self.write_events()
        (self.root / 'execution.json').write_text('{"exit_status":0,"exit_status":0}\n')
        self.assertFalse(self.assess()['passed'])

    def test_source_receipt_or_incomplete_runtime_invocation_rejected(self):
        for name, key, value in [('source-binding.json', 'snapshot_sha256', 'f' * 64),
                                 ('execution.json', 'completed', False), ('execution.json', 'exit_status', False)]:
            path = self.root / name
            raw = path.read_bytes()
            self.mutate(name, lambda obj: obj.update({key: value}))
            self.assertFalse(self.assess()['passed'])
            path.write_bytes(raw)

    def test_missing_foreign_or_live_namespace_retirement_rejected(self):
        path = self.runtime / 'executor-2-retirement.json'
        raw = path.read_bytes()
        path.unlink()
        self.assertFalse(self.assess()['passed'])
        path.write_bytes(raw)
        self.mutate('runtime/executor-2-retirement.json', lambda obj: obj.update(identity_path='/foreign/executor-2.json'))
        self.assertFalse(self.assess()['passed'])
        path.write_bytes(raw)
        self.mutate('runtime/executor-2-retirement.json', lambda obj: obj['observations'][-1].update(namespace_members=[{'pid': 22}]))
        self.assertFalse(self.assess()['passed'])

    def test_zero_connection_ledger_cannot_hide_child_or_transport_failure(self):
        put(self.runtime / 'codehost-1-retirement.json', {})
        self.assertFalse(self.assess()['passed'])
        (self.runtime / 'codehost-1-retirement.json').unlink()
        self.bridge_rows[-1]['failures'] = ['synthetic failure']
        ledger(self.runtime / 'codehost-transport-v2.jsonl', self.bridge_rows)
        self.assertFalse(self.assess()['passed'])

    def test_false_independent_transport_result_cannot_be_ignored(self):
        self.bridge_rows[-1]['accepted'] = 1
        ledger(self.runtime / 'codehost-transport-v2.jsonl', self.bridge_rows)
        with patch.object(T, 'verify_transport_integrity', return_value={'passed': False}) as verify:
            result = self.assess()
        verify.assert_called_once()
        self.assertFalse(result['passed'])
        self.assertIn('Independent code-host lifecycle proof failed', result['errors']['preflight']['message'])

    def test_owner_proof_must_reconcile_global_event_binding(self):
        with patch.object(T, 'client_finishing', return_value={'wall_unix_s': 1.0, 'monotonic_s': 1.0}):
            result = self.assess()
        self.assertFalse(result['passed'])
        self.assertIn('Owner proof input changed', result['errors']['preflight']['message'])

    def test_missing_native_public_response_is_not_a_complete_preflight(self):
        self.events = [row for row in self.events if not (row.get('kind') == 'response' and row.get('id') == 4)]
        self.write_events()
        self.assertFalse(self.assess()['passed'])

    def test_canary_cleanup_or_mutating_gateway_failure_rejected(self):
        for name, fn in [('runtime/canary-stdout.json', lambda obj: obj['checks'].update({'boundary-0': False})),
                         ('runtime/cleanup.json', lambda obj: obj.update(clean=False)),
                         ('runtime/gateway-calls.json', lambda obj: obj.append({'method': 'POST', 'path': '/submit'}))]:
            path = self.root / name
            raw = path.read_bytes()
            self.mutate(name, fn)
            self.assertFalse(self.assess()['passed'])
            path.write_bytes(raw)

    def test_missing_capture_close_or_projected_output_forgery_rejected(self):
        path = self.runtime / 'executor-1-capture.jsonl'
        raw = path.read_bytes()
        path.write_bytes(b'\n'.join(raw.splitlines()[:-1]) + b'\n')
        self.assertFalse(self.assess()['passed'])
        path.write_bytes(raw)
        self.mutate('runtime/executor-process-probe.json', lambda obj: obj.update(stdout=obj['stdout'] + 'forged'))
        self.assertFalse(self.assess()['passed'])

    def test_source_change_fails_closed_before_fixture_or_output(self):
        args = SimpleNamespace(snapshot=self.snapshot, framework_revision='changed', run_id='fixture', output=self.base / 'new')
        with patch.object(P, 'validate_snapshot', side_effect=ValueError('source mismatch')), patch.object(P, 'dependency') as dep:
            with self.assertRaisesRegex(ValueError, 'source mismatch'):
                P.run(args)
            dep.assert_not_called()
        self.assertFalse(args.output.exists())

    def test_existing_output_is_never_overwritten(self):
        args = SimpleNamespace(snapshot=self.snapshot, framework_revision=self.frozen['revision'], run_id='fixture', output=self.root)
        before = (self.root / 'source-binding.json').read_bytes()
        with patch.object(P, 'dependency') as dep:
            with self.assertRaises(FileExistsError): P.run(args)
            dep.assert_not_called()
        self.assertEqual((self.root / 'source-binding.json').read_bytes(), before)

    def test_runner_uses_only_preflight_90_and_retains_failure_integer(self):
        args = SimpleNamespace(snapshot=self.snapshot, framework_revision=self.frozen['revision'], run_id='fixture', output=self.base / 'new')
        real_dep = P.dependency
        runtime = SimpleNamespace(run_bootstrap=lambda *args, **kw: 7)
        with patch.object(P, 'dependency', side_effect=lambda name: runtime if name == 'runtime' else real_dep(name)), \
             patch.object(runtime, 'run_bootstrap', return_value=7) as invoke:
            self.assertEqual(P.run(args), 1)
        invoke.assert_called_once_with(args.output / 'runtime', preflight=True, timeout=90)
        self.assertEqual(get(args.output / 'execution.json')['exit_status'], 7)
        self.assertFalse(get(args.output / 'result.json')['passed'])

    def test_runner_exception_keeps_failed_receipt_without_dynamic_error_text(self):
        args = SimpleNamespace(snapshot=self.snapshot, framework_revision=self.frozen['revision'], run_id='fixture', output=self.base / 'new')
        real_dep = P.dependency
        runtime = SimpleNamespace(run_bootstrap=lambda *args, **kw: None)
        with patch.object(P, 'dependency', side_effect=lambda name: runtime if name == 'runtime' else real_dep(name)), \
             patch.object(runtime, 'run_bootstrap', side_effect=RuntimeError('synthetic-token-do-not-log')):
            self.assertEqual(P.run(args), 1)
        self.assertNotIn('synthetic-token', (args.output / 'execution.json').read_text())
        self.assertEqual(get(args.output / 'execution.json')['error_type'], 'RuntimeError')


class CleanupAndSourceTests(unittest.TestCase):
    def test_required_method_or_new_source_absence_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / 'snapshot.json'
            frozen = {'revision': 'test', 'sources': {name: P.binding(P.REPO / name) for name in P.required_sources()}}
            put(snapshot, frozen)
            assess_module = P.dependency('assess')
            with patch.object(assess_module, 'frozen_problems', return_value=[]):
                self.assertEqual(P.validate_snapshot(snapshot, 'test'), frozen)
                del frozen['sources'][P.required_sources()[0]]
                put(snapshot, frozen)
                with self.assertRaisesRegex(ValueError, 'Required preflight source'):
                    P.validate_snapshot(snapshot, 'test')

    def test_existing_runtime_partial_constructor_still_attempts_close(self):
        runtime = P.dependency('runtime')
        calls = []
        class Partial:
            def __init__(self, *args):
                calls.append('initialize')
                raise RuntimeError('synthetic setup fault')
            def export(self, label):
                calls.append(label)
                raise RuntimeError('synthetic unavailable export')
            def close(self):
                calls.append('close')
                return True
        with tempfile.TemporaryDirectory() as directory, patch.object(runtime, 'Runtime', Partial), \
             patch.object(runtime, 'template', return_value={}):
            output = Path(directory) / 'new'
            self.assertEqual(runtime.run_bootstrap(output, preflight=True, timeout=90), 1)
            self.assertEqual(calls, ['initialize', 'runtime-before-close', 'close', 'runtime-after-close'])
            self.assertFalse(get(output / 'orchestration-result.json')['success'])


if __name__ == '__main__':
    unittest.main()
