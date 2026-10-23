"""Adversarial retained-evidence tests; no native process, model or simulator."""
import base64
import copy
import json
import math
from pathlib import Path
import shlex
import tempfile
import unittest
import zipfile

import empty_startup_reads as reader


class EmptyStartupReadsTests(unittest.TestCase):
    def test_completion_interval_and_post_send_receipt_race(self):
        for emitted, delivery in ((100900, 100.9000233), (100850, 100.9)):
            with self.subTest(emitted=emitted):
                self.make_capture()
                self.events[-1]['emittedAtMs'] = emitted
                self.rows[-2]['wall_unix_s'] = delivery
                self.save_capture()
                result = self.assess()
                self.assertTrue(result['verified'], result)
                proof = result['evidence'][0]
                self.assertEqual(proof['execution']['app_complete_wall_unix_s'], emitted / 1000)
                bound = proof['execution']['evidence_complete_upper_wall_unix_s']
                self.assertGreaterEqual(bound, delivery)
                self.assertEqual(proof['chronology']['read_complete_wall_unix_s'], bound)

    def test_post_send_delivery_bound_blocks_interleaved_mutation(self):
        self.events[-1]['emittedAtMs'] = 100850
        self.requests[0]['received_wall_unix_s'] = 100.88
        self.broker[0].update(received_wall_unix_s=100.88, wall_unix_s=101.0)
        self.history[1]['wall_unix_s'] = 100.95
        self.save_capture()
        self.save_histories()
        self.assert_rejected()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'stage'
        self.host = Path(self.temp.name) / 'host'
        (self.root / 'client').mkdir(parents=True)
        (self.host / 'continuity-history').mkdir(parents=True)
        self.archive = Path(self.temp.name) / 'code.zip'
        boundary = Path(__file__).resolve().parents[2] / 'readiness-session-10/boundary'
        with zipfile.ZipFile(self.archive, 'w') as archive:
            for name in reader.BOUNDARY_HASHES:
                archive.write(boundary / name, 'integration/readiness-session-10/boundary/' + name)
        self.hashes = {name: reader.EMPTY_SHA256 for name in reader.FIXED_ROOT_FILES}
        self.write_json('runtime-input-hashes.json', self.hashes)
        (self.host / 'continuity-history' / (reader.EMPTY_SHA256 + '.md')).write_bytes(b'')
        self.commit = {'sha256': reader.sha(b'new'), 'bytes': 3, 'previous_sha256': reader.EMPTY_SHA256}
        self.requests = [{'trace_id': 'one', 'received_wall_unix_s': 120.0, 'method': 'POST',
                          'path': '/continuity', 'request_id': None, 'request': '{"content":"new"}'}]
        self.broker = [{**self.requests[0], 'wall_unix_s': 121.0, 'origin': 'protected_host',
                        'status': 200, 'response': self.commit}]
        self.calls = [{'method': 'POST', 'path': '/continuity', 'status': 200}]
        self.history = [
            {'event_id': 1, 'wall_unix_s': 80.0, 'type': 'observation', 'payload': {}},
            {'event_id': 2, 'wall_unix_s': 120.5, 'type': 'continuity_committed', 'payload': self.commit},
            {'event_id': 3, 'wall_unix_s': 200.0, 'type': 'episode_stopped', 'payload': {}},
        ]
        self.save_histories()
        self.output = "{}\nContinuity contents: ''\nBoundary evidence exists: False\n"
        self.make_capture()

    def write_json(self, name, value):
        (self.root / name).write_text(json.dumps(value), encoding='utf-8')

    def write_lines(self, path, values):
        path.write_bytes(b''.join(reader.canonical(v) + b'\n' for v in values))

    def save_histories(self):
        self.write_lines(self.root / 'broker-requests.jsonl', self.requests)
        self.write_lines(self.root / 'broker-events.jsonl', self.broker)
        self.write_json('gateway-calls.json', self.calls)
        self.write_lines(self.host / 'public-history.jsonl', self.history)

    def make_capture(self, script=None, *, output=None, projection=None, exit_code=0):
        script = reader.READ_ONLY_SCRIPT if script is None else script
        output = self.output if output is None else output
        projection = output if projection is None else projection
        argv = ['/usr/bin/bash', '-lc', script]
        item = {'id': 'read-1', 'type': 'commandExecution', 'command': shlex.join(argv),
                'exitCode': exit_code, 'aggregatedOutput': projection}
        self.events = [{'method': method, 'emittedAtMs': 110000,
                        'params': {'item': copy.deepcopy(item)}} for method in ('item/started', 'item/completed')]
        self.rows = []

        def append(kind, message=None, **extra):
            row = {'schema': 'campaign002-executor-capture-1', 'connection_id': '1',
                   'kind': kind, 'wall_unix_s': 100.0 + len(self.rows) / 10, **extra}
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
            'processId': 'p-1', 'argv': argv, 'arg0': None, 'cwd': 'file:///workspace', 'tty': False,
            'pipeStdin': False, 'metadata': {'toolCallId': 'read-1'}, 'env': {'LANG': 'C.UTF-8'},
            'envPolicy': {'inherit': 'none', 'ignoreDefaultExcludes': False, 'includeOnly': [], 'set': {}}}})
        send({'id': 7, 'result': {'processId': 'p-1'}})
        send({'method': 'process/output', 'params': {'processId': 'p-1', 'seq': 1, 'stream': 'stdout',
                                                   'chunk': base64.b64encode(output.encode()).decode()}})
        send({'method': 'process/exited', 'params': {'processId': 'p-1', 'seq': 2,
                                                  'exitCode': exit_code, 'sandboxDenied': False}})
        send({'method': 'process/closed', 'params': {'processId': 'p-1', 'seq': 3}})
        append('closed', failures=[])
        self.save_capture()

    @property
    def params(self):
        return self.rows[1]['message']['params']

    def save_capture(self):
        previous = None
        for index, row in enumerate(self.rows, 1):
            row.pop('record_sha256', None)
            row.update(sequence=index, previous_sha256=previous)
            if 'message' in row:
                digest = reader.sha(reader.canonical(row['message']))
                row.update(original_message_sha256=digest, retained_message_sha256=digest)
            previous = reader.sha(reader.canonical(row))
            row['record_sha256'] = previous
        self.write_lines(self.root / 'executor-1-capture.jsonl', self.rows)
        self.write_lines(self.root / 'client/events.jsonl', self.events)

    def assess(self):
        return reader.empty_startup_read_evidence(self.root, self.host, reader.EMPTY_SHA256, self.archive)

    def assert_rejected(self):
        result = self.assess()
        self.assertFalse(result['verified'], result)
        self.assertEqual(result['evidence'], [])
        self.assertTrue(result['errors'])

    def test_known_recipe_has_explicit_proof_without_synthetic_cat(self):
        result = self.assess()
        self.assertTrue(result['verified'], result)
        proof, = result['evidence']
        self.assertEqual(proof['item_id'], 'read-1')
        self.assertEqual(proof['observed_bytes'], 0)
        self.assertEqual(proof['input_sha256'], reader.EMPTY_SHA256)
        self.assertEqual(proof['execution']['argv'], self.params['argv'])
        self.assertTrue(proof['executor_provenance']['app_projection_equals_executor'])
        self.assertEqual(proof['chronology']['protected_history_events'], 3)
        self.assertEqual(len(proof['import_boundary_sources']), 3)
        self.assertNotIn('command', proof)

    def test_formatting_only_ast_equivalence_is_supported(self):
        self.make_capture(reader.READ_ONLY_SCRIPT.replace('k:v', 'k: v').replace("'Continuity.md'", '"Continuity.md"'))
        self.assertTrue(self.assess()['verified'])

    def test_cat_and_ls_cannot_prove_empty_writable_contents(self):
        for script in ('cat Continuity.md && ls -la notes programs live',
                       'cat Continuity.md', 'cat Continuity.md; echo "Continuity contents: \'\'"',
                       'cat missing || echo "Continuity contents: \'\'"'):
            with self.subTest(script=script):
                self.make_capture(script)
                self.assert_rejected()

    def test_shell_redirect_substitution_and_extra_commands_rejected(self):
        for script in (reader.READ_ONLY_SCRIPT + '\necho done',
                       reader.READ_ONLY_SCRIPT.replace("<<'PY'", "<<'PY' > notes/out"),
                       reader.READ_ONLY_SCRIPT.replace("<<'PY'", '<<PY'),
                       'echo "$(cat Continuity.md)"', reader.READ_ONLY_SCRIPT + ' || true',
                       reader.READ_ONLY_SCRIPT.replace('python3 -', 'python3 -; echo ok')):
            with self.subTest(script=script[:50]):
                self.make_capture(script)
                self.assert_rejected()

    def test_added_code_fake_print_import_and_builtin_shadowing_rejected(self):
        bodies = (
            "print = lambda *x: None\n", "repr = lambda value: \"''\"\n",
            "Path = lambda value: None\n", "import os\n", "exec('print(1)')\n",
            "__import__('builtins').repr = lambda value: \"''\"\n",
            "Path('Continuity.md').write_text('')\n", '# coding: utf-7\n',
        )
        for extra in bodies:
            with self.subTest(extra=extra):
                self.make_capture("python3 - <<'PY'\n" + extra + reader.READ_ONLY_BODY + 'PY')
                self.assert_rejected()
        self.make_capture(reader.READ_ONLY_SCRIPT.replace("repr(Path('Continuity.md').read_text())", '"\'\'"'))
        self.assert_rejected()

    def test_nonempty_missing_duplicate_and_fabricated_substring_markers_rejected(self):
        for output in (self.output.replace("contents: ''", "contents: 'not empty'"),
                       self.output.replace("Continuity contents: ''\n", ''),
                       self.output + "Continuity contents: ''\n",
                       '{}\n{"fake":"Continuity contents: \'\'"}\n',
                       self.output.replace("contents: ''", 'contents: ""')):
            with self.subTest(output=output):
                self.make_capture(output=output)
                self.assert_rejected()

    def test_complete_app_projection_required(self):
        self.make_capture(projection="Continuity contents: ''\n")
        self.assert_rejected()

    def test_failed_python_read_cannot_be_repaired_by_output(self):
        self.make_capture(exit_code=1)
        self.assert_rejected()

    def test_command_actions_cannot_supply_actual_argv(self):
        self.make_capture('echo "Continuity contents: \'\'"')
        self.events[-1]['params']['item']['commandActions'] = [{'command': reader.READ_ONLY_SCRIPT}]
        self.save_capture()
        self.assert_rejected()

    def test_override_environment_and_execution_mode_rejected(self):
        original = copy.deepcopy(self.params)
        attacks = [{'env': {'PYTHONPATH': 'notes'}}, {'env': {'PYTHONHOME': 'programs'}},
                   {'env': {'HOME': '/workspace/notes'}}, {'env': {'PATH': '/workspace/programs'}},
                   {'env': {'BASH_ENV': 'notes/override'}}, {'env': {'LD_PRELOAD': 'notes/override'}},
                   {'env': {'BASH_FUNC_python3%%': '() { echo fake; }'}}, {'env': {'LANG': 'other'}},
                   {'cwd': 'file:///workspace/notes'}, {'arg0': 'other'}, {'pipeStdin': True}]
        for attack in attacks:
            with self.subTest(attack=attack):
                self.rows[1]['message']['params'] = {**copy.deepcopy(original), **attack}
                self.save_capture()
                self.assert_rejected()

    def test_environment_policy_inheritance_and_override_rejected(self):
        original = copy.deepcopy(self.params['envPolicy'])
        for change in ({'inherit': 'all'}, {'includeOnly': ['PYTHONPATH']},
                       {'ignoreDefaultExcludes': True}, {'set': {'PYTHONPATH': 'notes'}}):
            with self.subTest(change=change):
                self.params['envPolicy'] = {**original, **change}
                self.save_capture()
                self.assert_rejected()

    def test_root_module_profile_and_path_shadowing_rejected(self):
        for name in ('json.py', 'pathlib.py', 'json/__init__.py', 'sitecustomize.py',
                     '.local/lib/python3/site-packages/override.pth', '.bash_profile',
                     '../json.py', '/workspace/json.py', 'notes/../json.py'):
            with self.subTest(name=name):
                self.write_json('runtime-input-hashes.json', {**self.hashes, name: reader.EMPTY_SHA256})
                self.assert_rejected()

    def test_changed_initial_hash_or_retained_bytes_rejected(self):
        self.write_json('runtime-input-hashes.json', {**self.hashes, 'Continuity.md': reader.sha(b'x')})
        self.assert_rejected()
        self.write_json('runtime-input-hashes.json', self.hashes)
        (self.host / 'continuity-history' / (reader.EMPTY_SHA256 + '.md')).write_bytes(b'x')
        self.assert_rejected()

    def test_changed_immutable_import_boundary_rejected(self):
        with zipfile.ZipFile(self.archive, 'w') as archive:
            archive.writestr('integration/readiness-session-10/boundary/namespace.py', '# writable root')
        self.assert_rejected()

    def test_duplicate_completion_or_missing_start_identity_rejected(self):
        original = copy.deepcopy(self.events)
        for events in (original + [original[-1]], original[1:]):
            self.events = events
            self.save_capture()
            self.assert_rejected()

    def test_actual_process_argv_or_tool_identity_mismatch_rejected(self):
        self.params['argv'] = ['/usr/bin/bash', '-lc', 'echo fake']
        self.save_capture()
        self.assert_rejected()
        self.make_capture()
        self.params['metadata']['toolCallId'] = 'other'
        self.save_capture()
        self.assert_rejected()

    def test_missing_delivery_and_capture_tail_rejected(self):
        self.rows[-2]['response_sequence'] = 7  # duplicate exit delivery, missing close
        self.save_capture()
        self.assert_rejected()
        self.make_capture()
        path = self.root / 'executor-1-capture.jsonl'
        path.write_bytes(path.read_bytes()[:-1])
        self.assert_rejected()

    def test_timestamp_missing_reversed_and_nonfinite_rejected(self):
        for stamp in (None, float('nan'), 99.0):
            with self.subTest(stamp=stamp):
                self.make_capture()
                self.rows[5]['wall_unix_s'] = stamp
                self.save_capture()
                self.assert_rejected()
        self.make_capture()
        self.events[-1]['emittedAtMs'] = 100000
        self.save_capture()
        self.assert_rejected()

    def test_before_interleaved_and_equal_mutation_boundaries_rejected(self):
        for start in (90.0, 100.5, 110.0, 110.001):
            with self.subTest(start=start):
                self.requests[0]['received_wall_unix_s'] = start
                self.broker[0]['received_wall_unix_s'] = start
                self.save_histories()
                self.assert_rejected()

    def test_strictly_later_mutation_boundary_passes(self):
        # The exact 110000ms emission interval ends at 110.001, not 110.0.
        start = math.nextafter(110.001, float('inf'))
        self.requests[0]['received_wall_unix_s'] = start
        self.broker[0]['received_wall_unix_s'] = start
        self.save_histories()
        self.assertTrue(self.assess()['verified'])

    def test_prior_host_commit_rejected_even_without_broker_mutation(self):
        self.requests, self.broker, self.calls = [], [], []
        self.history[1]['wall_unix_s'] = 100.5
        self.save_histories()
        self.assert_rejected()

    def test_inflight_request_missing_history_and_history_gap_rejected(self):
        self.broker = []
        self.calls = []
        self.save_histories()
        self.assert_rejected()
        self.requests = []
        self.history.pop(1)
        self.save_histories()
        self.assert_rejected()
        (self.host / 'public-history.jsonl').unlink()
        self.assert_rejected()

    def test_missing_terminal_tail_and_unmatched_commit_receipt_rejected(self):
        original = copy.deepcopy(self.history)
        self.history.pop()
        self.save_histories()
        self.assert_rejected()
        self.history = original
        self.history[1]['payload']['bytes'] = 4
        self.save_histories()
        self.assert_rejected()


if __name__ == '__main__':
    unittest.main()
