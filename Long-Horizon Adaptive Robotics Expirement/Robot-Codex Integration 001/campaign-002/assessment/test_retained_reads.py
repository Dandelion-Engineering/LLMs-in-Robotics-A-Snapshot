"""Deterministic capture-to-reader tests; no model, WSL, or simulation launch."""
import base64
import asyncio
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import retained_reads as reader

SOURCE = Path(__file__).resolve().parents[1] / 'harness/executor_capture.py'
SPEC = importlib.util.spec_from_file_location('capture_for_reader_tests', SOURCE)
capture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capture)


class CapturedReadsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fixture = SimpleNamespace(evidence=self.root, tokens=['secret-token'], abort_event=threading.Event(),
                                       redact=lambda value: value.replace('secret-token', '[REDACTED_EPHEMERAL_CAPABILITY]'))

    def tearDown(self):
        self.temp.cleanup()

    def make(self, chunks=(b'{"first":1}', b'{"second":2}'), *, projection='tail', command='cat live/activation.json live/state.json',
             omit_delivery=None, seq_gap=False, wrong_id=False, redacted=False, exit_code=0, include_exit=True,
             process_messages=None):
        writer = capture.Capture(self.fixture, '2')
        writer.append('open')
        item = {'id': 'tool-1', 'type': 'commandExecution', 'exitCode': 0,
                'command': "/usr/bin/bash -lc '" + command + "'", 'aggregatedOutput': projection}
        writer.append('request', {'id': 9, 'method': 'process/start', 'params': {
            'processId': 'process-1', 'argv': ['/usr/bin/bash', '-lc', command], 'cwd': 'file:///workspace', 'tty': False,
            'metadata': {'toolCallId': 'wrong' if wrong_id else item['id']}}})
        def send(value):
            sequence = writer.append('response', value)
            if omit_delivery is None or value.get('method') != omit_delivery:
                writer.append('delivered', response_sequence=sequence)
        send({'id': 9, 'result': {'processId': 'process-1', 'sandboxType': 'none'}})
        if process_messages is None:
            process_messages = [{'method': 'process/output', 'params': {'processId': 'process-1',
                'seq': index + int(seq_gap), 'stream': 'stdout', 'chunk': base64.b64encode(raw).decode()}}
                for index, raw in enumerate(chunks, 1)]
            if include_exit:
                process_messages += [
                    {'method': 'process/exited', 'params': {'processId': 'process-1', 'seq': len(chunks) + 1,
                                                           'exitCode': exit_code, 'sandboxDenied': False}},
                    {'method': 'process/closed', 'params': {'processId': 'process-1', 'seq': len(chunks) + 2}}]
        for message in process_messages:
            send(message)
        writer.append('closed', failures=[])
        return writer.path, [{'method': 'item/completed', 'params': {'item': item}}]

    def test_multichunk_bytes_join_exact_process_and_projection_is_separate(self):
        first = ('{"first":"' + 'x' * 10000 + '"}').encode()
        path, events = self.make((first, b'{"second":2}'))
        commands, audit = reader.authenticated_commands(self.root, events)
        self.assertTrue(audit['verified'])
        self.assertEqual(commands[0]['aggregatedOutput'], first.decode() + '{"second":2}')
        proof = commands[0]['executor_provenance']
        self.assertEqual((proof['request_id'], proof['process_id'], proof['tool_call_id']), (9, 'process-1', 'tool-1'))
        self.assertFalse(proof['app_projection_equals_executor'])
        self.assertEqual(proof['app_projection_bytes'], 4)
        self.assertEqual(proof['process_sequence_order'], [1, 2, 3, 4])
        self.assertEqual(proof['output_sequence_order'], [1, 2])
        self.assertEqual((proof['exit_sequence'], proof['closed_sequence']), (3, 4))
        self.assertFalse(proof['exit_interleaved_out_of_sequence'])

    def test_zero_byte_cat_preserves_startup_visible_boundary(self):
        path, events = self.make((), projection=None, command='cat /workspace/Continuity.md')
        (self.root / 'canary-stdout.json').write_text('{}')
        stage = reader.upgrade_stage(self.root, {'events': events, 'commands': [], 'contents': {}, 'checks': {}})
        self.assertEqual(stage['commands'][0]['aggregatedOutput'], '')
        self.assertEqual(stage['commands'][0]['executor_provenance']['stdout_sha256'], reader.sha(b''))

    def test_nonempty_instruction_output_does_not_replace_short_visible_aggregate(self):
        path, events = self.make((b'complete actual instructions',), command='cat /workspace/RobotAgentPrompt.md')
        (self.root / 'canary-stdout.json').write_text('{}')
        stage = reader.upgrade_stage(self.root, {'events': events,
            'commands': [events[0]['params']['item']], 'contents': {}, 'checks': {}})
        self.assertEqual(stage['commands'][0]['aggregatedOutput'], 'tail')
        self.assertEqual(stage['source_commands'][0]['aggregatedOutput'], 'complete actual instructions')

    def test_missing_stream_delivery_is_unverified(self):
        path, events = self.make(omit_delivery='process/output')
        self.assertEqual(reader.authenticated_commands(self.root, events)[0], [])

    def test_wrong_tool_id_is_not_a_read(self):
        path, events = self.make(wrong_id=True)
        self.assertEqual(reader.authenticated_commands(self.root, events)[0], [])

    def test_sequence_gap_is_not_repaired(self):
        path, events = self.make(seq_gap=True)
        self.assertEqual(reader.authenticated_commands(self.root, events)[0], [])

    def test_no_exit_receipt_is_not_a_complete_read(self):
        path, events = self.make(include_exit=False)
        self.assertEqual(reader.authenticated_commands(self.root, events)[0], [])

    def test_missing_closed_delivery_is_not_a_complete_read(self):
        path, events = self.make(omit_delivery='process/closed')
        self.assertEqual(reader.authenticated_commands(self.root, events)[0], [])

    def test_nonzero_process_exit_is_not_success(self):
        path, events = self.make(exit_code=1)
        self.assertEqual(reader.authenticated_commands(self.root, events)[0], [])

    def test_base64_token_is_redacted_and_cannot_prove_raw_read(self):
        path, events = self.make((b'secret-token',))
        raw = path.read_text()
        self.assertNotIn('secret-token', raw)
        self.assertNotIn(base64.b64encode(b'secret-token').decode(), raw)
        self.assertEqual(reader.authenticated_commands(self.root, events)[0], [])

    def test_tampered_journal_fails_entire_capture(self):
        path, events = self.make()
        path.write_text(path.read_text().replace('tool-1', 'tool-2'))
        commands, audit = reader.authenticated_commands(self.root, events)
        self.assertEqual(commands, [])
        self.assertFalse(audit['verified'])

    def test_truncated_raw_json_is_preserved_not_reconstructed(self):
        path, events = self.make((b',"truncated":true}',))
        commands, audit = reader.authenticated_commands(self.root, events)
        self.assertEqual(commands[0]['aggregatedOutput'], ',"truncated":true}')
        with self.assertRaises(ValueError):
            json.loads(commands[0]['aggregatedOutput'])

    def test_capture_bound_sets_abort_without_silent_truncation(self):
        writer = capture.Capture(self.fixture, '2')
        with patch.object(capture, 'MAX_CAPTURE_BYTES', 3):
            with self.assertRaisesRegex(RuntimeError, 'bound'):
                writer.append('open')
        self.assertTrue(self.fixture.abort_event.is_set())
        self.assertEqual(writer.path.read_bytes(), b'')

    def test_missing_capture_fails(self):
        self.assertFalse(reader.authenticated_commands(self.root, [])[1]['verified'])

    def test_status_preserving_canary_joins_trusted_capture_not_app_projection(self):
        canary = {'qualified': True, 'checks': {str(i): True for i in range(45)},
                  'details': {'exact': 'observed'}}
        raw = json.dumps(canary).encode()
        command = ('python3 /canary.py > notes/resume-boundary-observation.json 2> notes/resume-boundary-stderr.txt\n'
                   'canary_status=$?\ncat notes/resume-boundary-observation.json\nexit "$canary_status"')
        _, events = self.make((raw,), projection=None, command=command)
        commands, audit = reader.authenticated_commands(self.root, events)
        self.assertTrue(audit['verified'])
        matched = reader.canary_matches(commands, {'notes/resume-boundary-observation.json': raw,
            'notes/resume-boundary-stderr.txt': b''}, canary)
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]['recipe']['form'], 'status_preserving_redirect_then_read')
        self.assertFalse(matched[0]['executor_provenance']['app_projection_equals_executor'])

    @staticmethod
    def sequence_case():
        def output(sequence, raw):
            return {'method': 'process/output', 'params': {'processId': 'process-1', 'seq': sequence,
                    'stream': 'stdout', 'chunk': base64.b64encode(raw).decode()}}
        return [output(1, b'first'),
                {'method': 'process/exited', 'params': {'processId': 'process-1', 'seq': 3,
                                                       'exitCode': 0, 'sandboxDenied': False}},
                output(2, b'second'), output(4, b'third'),
                {'method': 'process/closed', 'params': {'processId': 'process-1', 'seq': 5}}]

    def read_sequence_case(self, messages=None, **kwargs):
        (self.root / 'executor-2-capture.jsonl').unlink(missing_ok=True)
        path, events = self.make(process_messages=self.sequence_case() if messages is None else messages, **kwargs)
        retained = path.read_bytes()
        commands, audit = reader.authenticated_commands(self.root, events)
        self.assertEqual(path.read_bytes(), retained, 'Reader changed the original arrival ledger')
        return commands, audit

    def test_exit_notice_overtaking_output_preserves_bytes_and_audits_order(self):
        commands, audit = self.read_sequence_case(projection='firstsecondthird')
        self.assertTrue(audit['verified'])
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0]['aggregatedOutput'], 'firstsecondthird')
        proof = commands[0]['executor_provenance']
        self.assertEqual(proof['stdout_sha256'], reader.sha(b'firstsecondthird'))
        self.assertEqual(proof['process_sequence_order'], [1, 3, 2, 4, 5])
        self.assertEqual(proof['output_sequence_order'], [1, 2, 4])
        self.assertEqual((proof['exit_sequence'], proof['closed_sequence']), (3, 5))
        self.assertTrue(proof['exit_interleaved_out_of_sequence'])
        self.assertTrue(proof['app_projection_equals_executor'])
        self.assertIn('no app acknowledgment inferred', proof['scope'])

    def test_only_exit_notice_can_appear_early_or_late_without_sorting_output(self):
        original = self.sequence_case()
        for order in ([1, 0, 2, 3, 4], [0, 2, 3, 1, 4]):
            with self.subTest(order=order):
                messages = [original[index] for index in order]
                commands, _ = self.read_sequence_case(messages, projection='short app projection')
                self.assertEqual(commands[0]['aggregatedOutput'], 'firstsecondthird')
                proof = commands[0]['executor_provenance']
                self.assertEqual(proof['process_sequence_order'], [item['params']['seq'] for item in messages])
                self.assertTrue(proof['exit_interleaved_out_of_sequence'])
                self.assertFalse(proof['app_projection_equals_executor'])

    def test_ordinary_exit_before_final_drain_remains_valid(self):
        messages = self.sequence_case()
        messages[1]['params']['seq'], messages[2]['params']['seq'] = 2, 3
        commands, _ = self.read_sequence_case(messages)
        self.assertEqual(commands[0]['aggregatedOutput'], 'firstsecondthird')
        self.assertEqual(commands[0]['executor_provenance']['output_sequence_order'], [1, 3, 4])
        self.assertFalse(commands[0]['executor_provenance']['exit_interleaved_out_of_sequence'])

    def test_output_reordering_is_not_repaired_even_when_app_matches_sorted_bytes(self):
        messages = self.sequence_case()
        messages[0], messages[2] = messages[2], messages[0]
        commands, audit = self.read_sequence_case(messages, projection='firstsecondthird')
        self.assertTrue(audit['verified'])
        self.assertEqual(commands, [])

    def test_sequence_set_requires_each_integer_once_without_gaps_or_extras(self):
        for replacement in (0, -1, 1, 3, 6, True, 2.0, '2', None):
            with self.subTest(replacement=replacement):
                messages = self.sequence_case(); messages[2]['params']['seq'] = replacement
                self.assertEqual(self.read_sequence_case(messages)[0], [])

    def test_closed_must_be_unique_last_and_maximum_sequence(self):
        original = self.sequence_case()
        missing = copy.deepcopy(original[:-1])
        early = copy.deepcopy(original); early[3], early[4] = early[4], early[3]
        duplicate = copy.deepcopy(original); duplicate.append(copy.deepcopy(original[-1]))
        not_max = copy.deepcopy(original); not_max[3]['params']['seq'], not_max[4]['params']['seq'] = 5, 4
        for name, messages in (('missing', missing), ('output_after_closed', early),
                               ('duplicate', duplicate), ('not_max', not_max)):
            with self.subTest(name=name):
                self.assertEqual(self.read_sequence_case(messages)[0], [])

    def test_exit_must_be_unique_successful_integer_and_not_sandbox_denied(self):
        original = self.sequence_case()
        missing = [copy.deepcopy(item) for item in original if item['method'] != 'process/exited']
        for index, item in enumerate(missing, 1):
            item['params']['seq'] = index
        duplicate = copy.deepcopy(original); duplicate[2] = copy.deepcopy(duplicate[1]); duplicate[2]['params']['seq'] = 2
        cases = [('missing', missing), ('duplicate', duplicate)]
        for code in (1, -1, True, None):
            messages = copy.deepcopy(original); messages[1]['params']['exitCode'] = code
            cases.append(('exit-' + repr(code), messages))
        for denied in (True, None):
            messages = copy.deepcopy(original); messages[1]['params']['sandboxDenied'] = denied
            cases.append(('denied-' + repr(denied), messages))
        for name, messages in cases:
            with self.subTest(name=name):
                self.assertEqual(self.read_sequence_case(messages)[0], [])

    def test_interleaving_still_requires_every_delivery_unredacted_output_and_empty_stderr(self):
        for method in ('process/output', 'process/exited', 'process/closed'):
            with self.subTest(missing_delivery=method):
                self.assertEqual(self.read_sequence_case(omit_delivery=method)[0], [])
        for stream, raw in (('stderr', b'warning'), ('stdout', b'secret-token'), ('other', b'other')):
            with self.subTest(stream=stream, raw=raw):
                messages = self.sequence_case()
                messages[2]['params'].update(stream=stream, chunk=base64.b64encode(raw).decode())
                self.assertEqual(self.read_sequence_case(messages)[0], [])

    def test_interleaved_output_cannot_be_joined_from_another_process(self):
        messages = self.sequence_case(); messages[2]['params']['processId'] = 'unrelated-process'
        self.assertEqual(self.read_sequence_case(messages)[0], [])
        self.assertEqual(self.read_sequence_case(wrong_id=True)[0], [])

    def test_interleaving_still_requires_blob_identity_even_with_a_valid_ledger_chain(self):
        path, events = self.make(process_messages=self.sequence_case())
        rows = [json.loads(line) for line in path.read_bytes().splitlines()]
        output = next(row for row in rows if row.get('message', {}).get('method') == 'process/output')
        output['blobs'][0]['raw_sha256'] = '0' * 64
        previous = None
        for row in rows:
            row['previous_sha256'] = previous
            row.pop('record_sha256')
            row['record_sha256'] = reader.sha(reader.canonical(row))
            previous = row['record_sha256']
        path.write_bytes(b''.join(reader.canonical(row) + b'\n' for row in rows))
        commands, audit = reader.authenticated_commands(self.root, events)
        self.assertTrue(audit['verified'])
        self.assertEqual(commands, [])


class CanaryJoinsTests(unittest.TestCase):
    def setUp(self):
        self.canary = {'qualified': True, 'checks': {str(i): True for i in range(45)}, 'details': {'exact': 'observed'}}
        self.item = {'id': 'actual', 'exitCode': 0, 'command': "/usr/bin/bash -lc 'python3 /canary.py'",
                     'aggregatedOutput': json.dumps(self.canary)}
        self.authenticate_output()
        self.contents = {'notes/boundary-observation.json': json.dumps(self.canary, indent=2).encode()}

    def authenticate_output(self):
        raw = self.item['aggregatedOutput'].encode()
        self.item['executor_provenance'] = {'tool_call_id': self.item['id'], 'stdout_bytes': len(raw),
                                           'stdout_sha256': reader.sha(raw)}

    def status_recipe(self):
        command = ('python3 /canary.py > notes/resume-boundary-observation.json 2> notes/resume-boundary-stderr.txt\n'
                   'canary_status=$?\ncat notes/resume-boundary-observation.json\nexit "$canary_status"')
        self.item['command'] = "/usr/bin/bash -lc '" + command + "'"
        self.contents = {'notes/resume-boundary-observation.json': json.dumps(self.canary).encode(),
                         'notes/resume-boundary-stderr.txt': b''}
        return command

    def test_separately_saved_semantically_identical_actual_canary(self):
        result = reader.canary_matches([self.item], self.contents, self.canary)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['saved_sha256'], reader.sha(next(iter(self.contents.values()))))

    def test_changed_saved_detail_does_not_join(self):
        changed = copy.deepcopy(self.canary)
        changed['details']['exact'] = 'invented'
        self.contents['notes/boundary-observation.json'] = json.dumps(changed).encode()
        self.assertEqual(reader.canary_matches([self.item], self.contents, self.canary), [])

    def test_fabricated_agent_note_cannot_replace_actual_canary(self):
        self.item['command'] = "/usr/bin/bash -lc 'echo fabricated'"
        self.assertEqual(reader.canary_matches([self.item], self.contents, self.canary), [])

    def test_suppressed_actual_canary_followed_by_echo_is_rejected(self):
        self.item['command'] = "/usr/bin/bash -lc 'python3 /canary.py >/dev/null; echo fabricated'"
        self.assertEqual(reader.canary_matches([self.item], self.contents, self.canary), [])

    def test_direct_redirect_then_read_matches(self):
        self.item['command'] = "/usr/bin/bash -lc 'python3 /canary.py > notes/boundary-observation.json\ncat notes/boundary-observation.json'"
        self.assertEqual(len(reader.canary_matches([self.item], self.contents, self.canary)), 1)

    def test_status_preserving_recipe_matches_exact_retained_stdout_and_empty_stderr(self):
        self.status_recipe()
        matches = reader.canary_matches([self.item], self.contents, self.canary)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['file'], 'notes/resume-boundary-observation.json')
        self.assertEqual(matches[0]['recipe']['stderr'], 'notes/resume-boundary-stderr.txt')

    def test_status_preserving_recipe_requires_retained_empty_stderr(self):
        self.status_recipe()
        for contents in ({key: value for key, value in self.contents.items() if not key.endswith('stderr.txt')},
                         {**self.contents, 'notes/resume-boundary-stderr.txt': b'warning\n'},
                         {**self.contents, 'notes/resume-boundary-stderr.txt': ''}):
            with self.subTest(contents=contents):
                self.assertEqual(reader.canary_matches([self.item], contents, self.canary), [])

    def test_bounded_recipe_rejects_path_status_output_and_command_tricks(self):
        command = self.status_recipe()
        bad = [
            command.replace('canary_status=$?', 'canary_status=0'),
            command.replace('canary_status=$?', 'canary_status="$?"; canary_status=0'),
            command.replace('exit "$canary_status"', 'exit 0'),
            command.replace('exit "$canary_status"', 'exit "$other_status"'),
            command.replace('canary_status=$?\n', ''),
            command.replace('cat notes/resume', 'echo fabricated > notes/resume-boundary-observation.json\ncat notes/resume'),
            command.replace('cat notes/resume-boundary-observation.json', 'cat notes/resume-boundary-observation.json > /dev/null'),
            command.replace('cat notes/resume-boundary-observation.json', 'cat notes/resume-boundary-observation.json\ncat notes/resume-boundary-observation.json'),
            command.replace('notes/resume-boundary-observation.json', 'notes/../resume-boundary-observation.json'),
            command.replace('notes/resume-boundary-observation.json', 'notes/./resume-boundary-observation.json'),
            command.replace('notes/resume-boundary-observation.json', 'notes/$(echo resume)-boundary-observation.json'),
            command.replace('notes/resume-boundary-stderr.txt', 'notes/../resume-boundary-stderr.txt'),
            command.replace('notes/resume-boundary-stderr.txt', 'notes/resume-boundary-observation.json'),
            command.replace('2>', '2 >'),
            command.replace(' > notes/', ' >> notes/'),
            command.replace('python3 /canary.py', '/workspace/python3 /canary.py'),
            command.replace('/canary.py', 'programs/canary.py'),
            command + '\necho fabricated',
        ]
        for value in bad:
            with self.subTest(command=value):
                item = {**self.item, 'command': "/usr/bin/bash -lc '" + value + "'"}
                self.assertEqual(reader.canary_matches([item], self.contents, self.canary), [])

    def test_canary_requires_successful_authenticated_stdout(self):
        self.status_recipe()
        bad = [
            {**self.item, 'exitCode': value} for value in (None, False, True, '0', 1)
        ] + [
            {key: value for key, value in self.item.items() if key != 'executor_provenance'},
            {**self.item, 'executor_provenance': None},
            {**self.item, 'executor_provenance': {**self.item['executor_provenance'], 'stdout_sha256': '0' * 64}},
            {**self.item, 'executor_provenance': {**self.item['executor_provenance'], 'tool_call_id': 'other'}},
            {**self.item, 'executor_provenance': {**self.item['executor_provenance'], 'stdout_bytes': 0}},
        ]
        for item in bad:
            with self.subTest(item=item):
                self.assertEqual(reader.canary_matches([item], self.contents, self.canary), [])

    def test_redirected_note_must_match_exact_destination_and_whole_json(self):
        self.status_recipe()
        wrong_path = dict(self.contents)
        wrong_path['notes/other-boundary-observation.json'] = wrong_path.pop('notes/resume-boundary-observation.json')
        self.assertEqual(reader.canary_matches([self.item], wrong_path, self.canary), [])
        for raw in (self.item['aggregatedOutput'] * 2, self.item['aggregatedOutput'] + '\nfabricated', '[]'):
            self.item['aggregatedOutput'] = raw
            self.authenticate_output()
            self.assertEqual(reader.canary_matches([self.item], self.contents, self.canary), [])

    def test_all_original_checks_and_details_remain_required(self):
        self.status_recipe()
        for mode in ('false_check', 'extra_check', 'different_key', 'changed_detail'):
            observed = copy.deepcopy(self.canary)
            if mode == 'false_check':
                observed['checks']['0'] = False
            elif mode == 'extra_check':
                observed['checks']['extra'] = True
            elif mode == 'different_key':
                observed['checks']['extra'] = observed['checks'].pop('0')
            else:
                observed['details']['exact'] = 'invented'
            self.contents['notes/resume-boundary-observation.json'] = json.dumps(observed).encode()
            if mode != 'changed_detail':
                self.item['aggregatedOutput'] = json.dumps(observed)
                self.authenticate_output()
            else:
                self.item['aggregatedOutput'] = json.dumps(self.canary)
                self.authenticate_output()
            with self.subTest(mode=mode):
                self.assertEqual(reader.canary_matches([self.item], self.contents, self.canary), [])


class UpgradeProofRoutingTests(unittest.TestCase):
    def run_upgrade(self, archive=None, *, proof=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'canary-stdout.json').write_text('{"checks":{}}', encoding='utf-8')
            stage = {'events': [], 'contents': {}, 'commands': [], 'checks': {}}
            observed = {'actual_output_sha256': 'observed', 'join': 'complete observed JSON'}
            with patch.object(reader, 'authenticated_commands', return_value=([], {'verified': True})), \
                    patch.object(reader, 'canary_matches', return_value=[observed]), \
                    patch('canary_exit_proof.canary_exit_evidence', return_value=proof) as helper:
                result = reader.upgrade_stage(root, stage, archive)
                return result, helper.call_args_list

    def test_no_archive_retains_only_existing_observed_proof(self):
        result, calls = self.run_upgrade()
        self.assertEqual(calls, [])
        self.assertNotIn('canary_exit_proof', result)
        self.assertEqual(result['canary_matches'], [{'actual_output_sha256': 'observed', 'join': 'complete observed JSON'}])

    def test_archive_adds_explicit_narrow_proof_and_retains_audit(self):
        evidence = {'canary_output_captured': False, 'proof_scope': 'check values only'}
        audit = {'verified': True, 'evidence': [evidence], 'errors': []}
        result, calls = self.run_upgrade('frozen.zip', proof=audit)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[1], 'frozen.zip')
        self.assertEqual(result['canary_exit_proof'], audit)
        self.assertEqual(result['canary_matches'][1], evidence)
        self.assertEqual(result['canary_matches'][0]['actual_output_sha256'], 'observed')
        self.assertTrue(result['checks']['all_45_model_canaries_saved'])

    def test_failed_narrow_audit_cannot_replace_or_modify_observed_proof(self):
        audit = {'verified': False, 'evidence': [], 'errors': ['source differs']}
        result, _ = self.run_upgrade('frozen.zip', proof=audit)
        self.assertEqual(result['canary_exit_proof'], audit)
        self.assertEqual(len(result['canary_matches']), 1)
        self.assertTrue(result['checks']['all_45_model_canaries_saved'])


class ReadbackProofRoutingTests(unittest.TestCase):
    def upgrade(self, readback, existing=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'canary-stdout.json').write_text('{"checks":{}}', encoding='utf-8')
            stage = {'events': [], 'contents': {}, 'commands': [], 'checks': {}}
            with patch.object(reader, 'authenticated_commands', return_value=([], {'verified': True})), \
                    patch.object(reader, 'canary_matches', return_value=existing or []), \
                    patch('canary_exit_proof.canary_exit_evidence', return_value={'verified': False, 'evidence': [], 'errors': []}), \
                    patch('canary_readback_proof.canary_readback_evidence', return_value=readback) as helper:
                result = reader.upgrade_stage(root, stage, 'frozen.zip')
                return result, helper.call_args_list

    def test_missing_exclusivity_does_not_qualify_saved_readback(self):
        audit = {'verified': False, 'evidence': [{'all_45_true': True}], 'errors': ['Unclosed earlier writer']}
        result, calls = self.upgrade(audit)
        self.assertEqual(len(calls), 1)
        self.assertFalse(result['checks']['all_45_model_canaries_saved'])
        self.assertEqual(result['canary_matches'], [])
        self.assertEqual(result['canary_readback_proof'], audit)

    def test_verified_exclusive_readback_retains_its_distinct_scope(self):
        evidence = {'proof_scope': 'semantic protected check vector', 'child_exit_observed': False}
        audit = {'verified': True, 'evidence': [evidence], 'errors': []}
        result, calls = self.upgrade(audit)
        self.assertEqual(calls[0].args[1], 'frozen.zip')
        self.assertTrue(result['checks']['all_45_model_canaries_saved'])
        self.assertEqual(result['canary_matches'], [evidence])
        self.assertFalse(result['canary_matches'][0]['child_exit_observed'])

    def test_existing_proof_does_not_require_optional_readback_history(self):
        existing = {'join': 'complete observed JSON'}
        result, calls = self.upgrade({'verified': False, 'evidence': [], 'errors': ['Unknown earlier command']}, [existing])
        self.assertEqual(calls, [])
        self.assertEqual(result['canary_matches'], [existing])
        self.assertTrue(result['checks']['all_45_model_canaries_saved'])
        self.assertNotIn('canary_readback_proof', result)


class BridgeRoundtripTests(unittest.TestCase):
    def test_actual_local_rpc_forwarding_capture_and_abrupt_client_cleanup(self):
        # Synthetic protocol child only. Actual namespace retirement is tested
        # separately by the queued WSL boundary suite, never inferred here.
        child = '''import sys,json,base64
for line in sys.stdin:
 x=json.loads(line); p=x['params']; pid=p['processId']
 rows=[{'id':x['id'],'result':{'processId':pid,'sandboxType':'none'}},
       {'method':'process/output','params':{'processId':pid,'seq':1,'stream':'stdout','chunk':base64.b64encode(b'actual child bytes').decode()}},
       {'method':'process/exited','params':{'processId':pid,'seq':2,'exitCode':0,'sandboxDenied':False}},
       {'method':'process/closed','params':{'processId':pid,'seq':3}}]
 for row in rows: print(json.dumps(row),flush=True)
'''
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            retired = []
            async def scenario():
                from websockets.asyncio.client import connect
                fixture = SimpleNamespace(evidence=root, tokens=[], abort_event=threading.Event(),
                    redact=lambda value:value, run='/synthetic-test', bridge_idle=asyncio.Event(),
                    argv=lambda mode:[sys.executable,'-u','-c',child])
                fixture.bridge_idle.set()
                async def retire(process, identity, evidence):
                    await asyncio.wait_for(process.wait(), 3)
                    retired.append(process.returncode)
                async def ready(url):
                    websocket = await connect(url)
                    await websocket.send(json.dumps({'id':8,'method':'process/start','params':{
                        'processId':'child','metadata':{'toolCallId':'tool'},
                        'argv':['/usr/bin/bash','-lc','cat live/state.json'],
                        'cwd':'file:///workspace','tty':False}}))
                    while True:
                        message=json.loads(await websocket.recv())
                        if message.get('method')=='process/closed':break
                    websocket.transport.abort()
                    await asyncio.wait_for(fixture.bridge_idle.wait(), 5)
                with patch.dict(sys.modules, {'retirement':SimpleNamespace(retire=retire)}):
                    await capture.bridge_executor(fixture, ready)
                self.assertFalse(fixture.abort_event.is_set())
            asyncio.run(scenario())
            self.assertEqual(retired,[0])
            events=[{'method':'item/completed','params':{'item':{'id':'tool','type':'commandExecution',
                'exitCode':0,'command':"/usr/bin/bash -lc 'cat live/state.json'",'aggregatedOutput':'actual child bytes'}}}]
            reads,audit=reader.authenticated_commands(root,events)
            self.assertTrue(audit['verified'])
            self.assertEqual(reads[0]['aggregatedOutput'],'actual child bytes')


if __name__ == '__main__':
    unittest.main()
