"""Synthetic authentication and scope tests; no model, namespace or simulator."""
import base64
import copy
import json
from pathlib import Path
import shlex
import tempfile
import unittest
import zipfile

import canary_exit_proof as reader
from empty_startup_reads import BOUNDARY_HASHES, FIXED_ROOT_FILES


class CanaryExitProofTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'stage'
        (self.root / 'client').mkdir(parents=True)
        self.archive = Path(self.temp.name) / 'code.zip'
        source = Path(__file__).resolve().parents[2] / 'readiness-session-10'
        self.sources = {**{'boundary/' + name: source / 'boundary' / name for name in BOUNDARY_HASHES},
                        **{name: source / name for name in reader.REVIEWED_SOURCES}}
        self.save_archive()
        self.run = '/var/tmp/robot-codex-session10/' + 'a' * 32
        self.protected = dict(zip(reader.PROTECTED_KEYS, (
            '/mnt/c/project/evidence/repository-canary.txt', '/mnt/c/Users/test/Documents/RobotCodex-S10-Canary-x.txt',
            self.run + '/protected/evaluator.txt', self.run + '/protected/development.txt')))
        self.fixture = {'protected': self.protected, 'other_port': 54321}
        initial_fixture = json.dumps({'protected': self.protected, 'other_port': 1}).encode()
        self.hashes = {name: reader.sha(b'') for name in FIXED_ROOT_FILES}
        self.hashes['live/canaries.json'] = reader.sha(initial_fixture)
        self.write_json('runtime-input-hashes.json', self.hashes)
        self.location = {'run': self.run, 'workspace': self.run + '/workspace', 'durable_backing': True,
                         'setup': {'protected_exist': {k: True for k in reader.PROTECTED_KEYS},
                                   'outside_loopback_control': True, **reader.RUNTIME_BINARIES}}
        self.write_json('runtime-location.json', self.location)
        self.document = {'qualified': True, 'checks': {k: True for k in sorted(reader.CHECK_KEYS)},
                         'details': {'nested_namespace_stderr': 'variable observed detail'}, 'scope': reader.SCOPE}
        self.write_json('canary-stdout.json', self.document)
        (self.root / 'canary-stderr.txt').write_bytes(b'')
        self.note_name = 'notes/resume-boundary-observation.json'
        self.files = {'live/canaries.json': json.dumps(self.fixture).encode(),
                      self.note_name: json.dumps(self.document).encode()}
        self.save_snapshots()
        self.make_capture()

    def write_json(self, name, value):
        (self.root / name).write_bytes(json.dumps(value).encode())

    def write_lines(self, name, values):
        (self.root / name).write_bytes(b''.join(reader.canonical(v) + b'\n' for v in values))

    def save_archive(self, changes=None):
        with zipfile.ZipFile(self.archive, 'w') as archive:
            for name, path in self.sources.items():
                raw = (changes or {}).get(name, path.read_bytes())
                archive.writestr('integration/readiness-session-10/' + name, raw)

    def save_snapshots(self):
        snapshot = {'files': {name: {'sha256': reader.sha(raw), 'retained_sha256': reader.sha(raw),
                                    'bytes': len(raw), 'base64': base64.b64encode(raw).decode()}
                              for name, raw in self.files.items()},
                    'total_bytes': sum(map(len, self.files.values()))}
        self.write_json('runtime-before-close.json', snapshot)
        self.write_json('runtime-after-close.json', snapshot)

    def make_capture(self, script=None, *, exit_code=0, output='', stream='stdout'):
        script = script or 'python3 /canary.py > ' + self.note_name
        argv = ['/usr/bin/bash', '-lc', script]
        item = {'id': 'canary-1', 'type': 'commandExecution', 'command': shlex.join(argv),
                'exitCode': exit_code, 'aggregatedOutput': None if not output else output}
        self.events = [{'method': method, 'emittedAtMs': 110000, 'params': {'item': copy.deepcopy(item)}}
                       for method in ('item/started', 'item/completed')]
        self.rows = []

        def append(kind, message=None, **extra):
            row = {'schema': 'campaign002-executor-capture-1', 'connection_id': '1',
                   'kind': kind, 'wall_unix_s': 100 + len(self.rows) / 10, **extra}
            if message is not None:
                row.update(message=message, blobs=[])
            self.rows.append(row)
            return len(self.rows)

        def send(message):
            sequence = append('response', message)
            if message.get('method') == 'process/output':
                raw = base64.b64decode(message['params']['chunk'])
                self.rows[-1]['blobs'] = [{'path': ['params', 'chunk'], 'raw_sha256': reader.sha(raw),
                    'retained_sha256': reader.sha(raw), 'raw_bytes': len(raw), 'retained_bytes': len(raw)}]
            append('delivered', response_sequence=sequence)

        append('open')
        append('request', {'id': 7, 'method': 'process/start', 'params': {
            'processId': 'p1', 'argv': argv, 'arg0': None, 'cwd': 'file:///workspace', 'tty': False,
            'pipeStdin': False, 'metadata': {'toolCallId': 'canary-1'}, 'env': {'LANG': 'C.UTF-8'},
            'envPolicy': {'inherit': 'none', 'ignoreDefaultExcludes': False, 'includeOnly': [], 'set': {}}}})
        send({'id': 7, 'result': {'processId': 'p1'}})
        sequence = 1
        if output:
            send({'method': 'process/output', 'params': {'processId': 'p1', 'seq': sequence, 'stream': stream,
                                                       'chunk': base64.b64encode(output.encode()).decode()}})
            sequence += 1
        send({'method': 'process/exited', 'params': {'processId': 'p1', 'seq': sequence,
                                                  'exitCode': exit_code, 'sandboxDenied': False}})
        send({'method': 'process/closed', 'params': {'processId': 'p1', 'seq': sequence + 1}})
        append('closed', failures=[])
        self.save_capture()

    @property
    def params(self):
        return self.rows[1]['message']['params']

    def save_capture(self, *, redacted_request=False):
        previous = None
        for index, row in enumerate(self.rows, 1):
            row.pop('record_sha256', None)
            row.update(sequence=index, previous_sha256=previous)
            if 'message' in row:
                digest = reader.sha(reader.canonical(row['message']))
                row.update(original_message_sha256=digest, retained_message_sha256=digest)
                if redacted_request and row['kind'] == 'request':
                    row['original_message_sha256'] = '0' * 64
            previous = reader.sha(reader.canonical(row))
            row['record_sha256'] = previous
        self.write_lines('executor-1-capture.jsonl', self.rows)
        self.write_lines('client/events.jsonl', self.events)

    def assess(self):
        return reader.canary_exit_evidence(self.root, self.archive)

    def assert_rejected(self):
        result = self.assess()
        self.assertFalse(result['verified'], result)
        self.assertEqual(result['evidence'], [])
        self.assertTrue(result['errors'])

    def test_exit_proves_only_fixed_checks_and_saved_values(self):
        result = self.assess()
        self.assertTrue(result['verified'], result)
        proof, = result['evidence']
        self.assertEqual(proof['check_count'], 45)
        self.assertEqual(proof['check_values_sha256'], reader.sha(reader.canonical(self.document['checks'])))
        self.assertEqual(proof['saved_sha256'], reader.sha(self.files[self.note_name]))
        self.assertFalse(proof['canary_output_captured'])
        self.assertFalse(proof['details_verified'])
        self.assertFalse(proof['full_output_identity_verified'])
        self.assertNotIn('actual_output_sha256', proof)
        self.assertNotIn('canonical_json_sha256', proof)
        self.assertEqual(len(proof['source_identities']), 6)
        self.assertEqual(proof['fixture']['protected_keys'], list(reader.PROTECTED_KEYS))
        self.assertTrue(proof['inputs'])

    def test_variable_details_do_not_upgrade_to_full_output_proof(self):
        changed = {**self.document, 'details': {'unverified': ['different', 123]}}
        self.files[self.note_name] = json.dumps(changed).encode()
        self.save_snapshots()
        result = self.assess()
        self.assertTrue(result['verified'], result)
        self.assertFalse(result['evidence'][0]['details_verified'])
        self.assertFalse(result['evidence'][0]['full_output_identity_verified'])

    def test_finite_literal_interpreter_flags(self):
        for interpreter in ('python3', 'python', '/usr/bin/python3', '/usr/bin/python'):
            for flags in ('', ' -I', ' -B', ' -I -B', ' -B -I'):
                with self.subTest(interpreter=interpreter, flags=flags):
                    self.make_capture(interpreter + flags + ' /canary.py > ' + self.note_name)
                    self.assertTrue(self.assess()['verified'])

    def test_shell_paths_commands_and_status_spoofs_rejected(self):
        commands = ('python3 /canary.py > notes/../boundary-observation.json',
                    'python3 /canary.py > notes/./boundary-observation.json',
                    'python3 /canary.py >> ' + self.note_name,
                    'python3 /canary.py > ' + self.note_name + '; true',
                    'python3 /canary.py > ' + self.note_name + '\nexit 0',
                    'python3 /canary.py > ' + self.note_name + ' 2>/dev/null',
                    'python3 /canary.py > "' + self.note_name + '"',
                    'python3 -c "print(1)" > ' + self.note_name,
                    'notes/python3 /canary.py > ' + self.note_name,
                    'python3 -I -I /canary.py > ' + self.note_name,
                    'python3 /canary.py > $(echo ' + self.note_name + ')',
                    'python3 /canary.py > ' + self.note_name + ' && cat ' + self.note_name)
        for command in commands:
            with self.subTest(command=command):
                self.make_capture(command)
                self.assert_rejected()

    def test_failed_missing_boolean_exit_or_missing_drain_rejected(self):
        for status in (1, None, False):
            with self.subTest(status=status):
                self.make_capture(exit_code=status)
                self.assert_rejected()
        self.make_capture()
        self.rows = self.rows[:-3] + self.rows[-1:]
        self.save_capture()
        self.assert_rejected()

    def test_nonempty_stdout_or_stderr_rejected(self):
        for stream in ('stdout', 'stderr'):
            with self.subTest(stream=stream):
                self.make_capture(output='unexpected', stream=stream)
                self.assert_rejected()

    def test_request_identity_and_original_bytes_required(self):
        self.save_capture(redacted_request=True)
        self.assert_rejected()
        self.make_capture()
        self.params['metadata']['toolCallId'] = 'other'
        self.save_capture()
        self.assert_rejected()
        self.make_capture()
        self.params['argv'][-1] = 'true'
        self.save_capture()
        self.assert_rejected()

    def test_closed_environment_and_import_shadowing_required(self):
        original = copy.deepcopy(self.params)
        for env in ({'PYTHONPATH': 'notes'}, {'PATH': 'programs'}, {'HOME': 'notes'},
                    {'BASH_ENV': 'notes/hook'}, {'LD_PRELOAD': 'notes/fake'},
                    {'BASH_FUNC_python3%%': '() { return 0; }'}):
            with self.subTest(env=env):
                self.rows[1]['message']['params'] = {**copy.deepcopy(original), 'env': env}
                self.save_capture()
                self.assert_rejected()
        self.make_capture()
        self.params['envPolicy']['inherit'] = 'all'
        self.save_capture()
        self.assert_rejected()
        self.make_capture()
        for name in ('json.py', 'sitecustomize.py', '.bash_profile', '.local/lib/python3/site-packages/x.pth'):
            with self.subTest(name=name):
                self.write_json('runtime-input-hashes.json', {**self.hashes, name: reader.sha(b'')})
                self.assert_rejected()

    def test_each_reviewed_source_change_fails_closed(self):
        for name in self.sources:
            with self.subTest(name=name):
                self.save_archive({name: self.sources[name].read_bytes() + b'\n# changed\n'})
                self.assert_rejected()

    def test_fixture_hash_keyset_setup_and_runtime_identity_required(self):
        self.write_json('runtime-input-hashes.json', {**self.hashes, 'live/canaries.json': '0' * 64})
        self.assert_rejected()
        self.write_json('runtime-input-hashes.json', self.hashes)
        changed = copy.deepcopy(self.fixture)
        changed['protected']['fabricated'] = changed['protected'].pop('repository_canary')
        self.files['live/canaries.json'] = json.dumps(changed).encode()
        self.save_snapshots()
        self.assert_rejected()
        self.files['live/canaries.json'] = json.dumps(self.fixture).encode()
        self.save_snapshots()
        for key, value in (('protected_exist', {k: 1 for k in reader.PROTECTED_KEYS}),
                           ('outside_loopback_control', False), ('binary_sha256', '0' * 64)):
            with self.subTest(key=key):
                location = copy.deepcopy(self.location)
                location['setup'][key] = value
                self.write_json('runtime-location.json', location)
                self.assert_rejected()

    def test_note_and_initial_require_exact_schema_true_bool_keyset_scope(self):
        changes = ({'qualified': 1}, {'scope': 'changed'}, {'details': []}, {'extra': True},
                   {'checks': {**self.document['checks'], 'workspace_read': 1}},
                   {'checks': {k: v for k, v in self.document['checks'].items() if k != 'workspace_read'}},
                   {'checks': {**self.document['checks'], 'spoofed': True}})
        for change in changes:
            for target in ('initial', 'note'):
                with self.subTest(change=change, target=target):
                    self.write_json('canary-stdout.json', self.document if target == 'note' else {**self.document, **change})
                    self.files[self.note_name] = json.dumps(self.document if target == 'initial' else {**self.document, **change}).encode()
                    self.save_snapshots()
                    self.assert_rejected()

    def test_note_duplicate_json_key_and_before_after_corruption_rejected(self):
        self.files[self.note_name] = json.dumps(self.document).replace('"qualified": true', '"qualified": true, "qualified": true').encode()
        self.save_snapshots()
        self.assert_rejected()
        self.files[self.note_name] = json.dumps(self.document).encode()
        self.save_snapshots()
        before = json.loads((self.root / 'runtime-before-close.json').read_bytes())
        before['files'][self.note_name]['sha256'] = '0' * 64
        self.write_json('runtime-before-close.json', before)
        self.assert_rejected()
        self.save_snapshots()
        self.files[self.note_name] += b'\n'
        after = {'files': {self.note_name: {'sha256': reader.sha(self.files[self.note_name]),
                 'retained_sha256': reader.sha(self.files[self.note_name]), 'bytes': len(self.files[self.note_name]),
                 'base64': base64.b64encode(self.files[self.note_name]).decode()}}}
        self.write_json('runtime-after-close.json', after)
        self.assert_rejected()

    def test_missing_or_ambiguous_tool_and_transport_receipt_rejected(self):
        original = copy.deepcopy(self.events)
        for events in (original[1:], original + [original[-1]]):
            self.events = events
            self.save_capture()
            self.assert_rejected()
        self.make_capture()
        self.rows[-2]['response_sequence'] = 5
        self.save_capture()
        self.assert_rejected()
        self.make_capture()
        capture = self.root / 'executor-1-capture.jsonl'
        capture.write_bytes(capture.read_bytes()[:-1])
        self.assert_rejected()


if __name__ == '__main__':
    unittest.main()
