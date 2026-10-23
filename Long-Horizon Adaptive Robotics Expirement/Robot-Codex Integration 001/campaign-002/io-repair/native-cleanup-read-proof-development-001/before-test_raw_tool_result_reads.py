"""Deterministic parser/provenance attacks; no model or native launch."""
import copy
import json
from pathlib import Path
import unittest
import zipfile

import literal_read_segments as literal
import raw_tool_result_reads as raw
import test_literal_read_segments as fixtures


class RawToolResultTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.LiteralReadSegmentsTests('test_known_mixed_chain_binds_every_byte_and_all_sources')
        self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.t = self.f.f
        self.command = 'cat /workspace/Tools.md'
        self.stdout = self.f.static['Tools.md'].decode()
        self.t.make_capture(self.command, output=self.stdout, projection=self.stdout[-4:])
        self.item = self.t.events[-1]['params']['item']
        self.complete = self.t.events[-1]
        for event in self.t.events:
            event['params'].update(threadId='thread-1', turnId='turn-1')
        self.options = {'cmd': self.command}
        self.call = {'type': 'custom_tool_call', 'call_id': 'outer-1', 'name': 'exec',
                     'input': 'text(await tools.exec_command(' + json.dumps(self.options) + '))'}
        self.output = {'type': 'custom_tool_call_output', 'call_id': 'outer-1',
                       'output': 'Script completed\nWall time 0.1 seconds\nOutput:\n' + json.dumps({
                           'chunk_id': 'chunk-1', 'wall_time_seconds': .1, 'exit_code': 0, 'output': self.stdout})}
        self.raw_call = self.event(self.call, 99000)
        self.raw_output = self.event(self.output, 111000)
        self.t.events = [{'kind': 'request', 'method': 'thread/start', 'params': {'experimentalRawEvents': True}},
                         self.raw_call, *self.t.events, self.raw_output]
        (self.t.root / 'client/launch.json').write_text(json.dumps({'experimental_raw_events_requested': True}))
        (self.t.root / 'client/preflight.json').write_text(json.dumps({'experimental_raw_events_requested': True,
            'experimental_raw_events_thread_start_accepted': True, 'preflight_passed': True, 'thread_id': 'thread-1'}))
        campaign = Path(__file__).resolve().parents[1]
        with zipfile.ZipFile(self.t.archive, 'a') as archive:
            for suffix in raw.SOURCE_HASHES:
                base = campaign.parent if suffix.startswith('/isolation-session-9/') else campaign
                prefix = 'integration' if base == campaign.parent else 'integration/campaign-002'
                archive.write(base / suffix.removeprefix('/'), prefix + suffix)
            for path in (Path(raw.__file__),):
                archive.write(path, 'integration/campaign-002/' + path.relative_to(campaign).as_posix())
        self.t.save_capture()

    @staticmethod
    def event(item, time):
        return {'kind': 'notification', 'method': 'rawResponseItem/completed', 'emittedAtMs': time,
                'params': {'threadId': 'thread-1', 'turnId': 'turn-1', 'item': item}}

    def proof(self):
        self.t.save_capture()
        from retained_reads import process_reads
        reads, integrity = process_reads(self.t.root, self.t.events)
        self.assertTrue(integrity['verified'])
        return raw.raw_result_proof(self.t.root, self.complete, self.t.events,
                                    reads['read-1'], self.t.archive)

    def rejected(self):
        with self.assertRaises((ValueError, KeyError, TypeError, OSError)):
            self.proof()

    def test_full_raw_result_establishes_read_without_repairing_short_display(self):
        proof = self.proof()
        self.assertEqual(proof['binding'], 'finite_single_command_unique_call_correlation')
        self.assertFalse(proof['app_projection_equals_executor'])
        result = self.f.assess()
        evidence, = result['startup']['Tools.md']
        self.assertEqual(evidence['match'], 'complete_prepared_tool_result_literal_segments')
        self.assertFalse(evidence['app_projection_equals_executor'])
        self.assertEqual(result['proofs'][0]['executor_provenance']['app_projection_bytes'], 4)
        self.assertTrue(evidence['prepared_tool_result']['whole_prepared_payload_consumed'])

    def test_absent_raw_keeps_false_startup_and_false_display(self):
        self.t.events = [e for e in self.t.events if e.get('method') != 'rawResponseItem/completed']
        self.t.save_capture()
        result = self.f.assess()
        self.assertFalse(result['startup']['Tools.md'])
        self.assertFalse(result['proofs'][0]['executor_provenance']['app_projection_equals_executor'])

    def unrelated_result(self, suffix, start, end):
        call = {'type': 'custom_tool_call', 'call_id': 'unrelated-' + suffix,
                'name': 'exec', 'input': 'text("Unrelated tool content")'}
        output = {'type': 'custom_tool_call_output', 'call_id': call['call_id'],
                  'output': 'Script completed\nWall time 0.1 seconds\nOutput:\nWarning: truncated output\nUnrelated prefix'}
        return [self.event(call, start), self.event(output, end)]

    def test_completed_truncated_result_before_candidate_is_not_read_evidence(self):
        other = self.unrelated_result('earlier', 97000, 98000)
        self.t.events[1:1] = other
        proof = self.proof()
        self.assertEqual(proof['call_id'], 'outer-1')
        self.assertFalse(proof['app_projection_equals_executor'])
        result = self.f.assess()
        self.assertEqual(len(result['startup']['Tools.md']), 1)
        self.assertEqual(result['startup']['Tools.md'][0]['prepared_tool_result']['source_payload_sha256'], raw.sha(self.stdout.encode()))

    def test_completed_truncated_result_after_candidate_is_not_read_evidence(self):
        self.t.events.extend(self.unrelated_result('later', 112000, 113000))
        self.assertEqual(self.proof()['call_id'], 'outer-1')
        self.assertEqual(len(self.f.assess()['startup']['Tools.md']), 1)

    def test_unrelated_truncated_result_still_requires_identity_closure_and_nonoverlap(self):
        baseline = list(self.t.events)
        earlier = self.unrelated_result('earlier', 97000, 98000)
        # Neither an absent call nor an absent result can establish nonoverlap.
        for fragment in ([earlier[0]], [earlier[1]]):
            self.t.events = baseline[:1] + fragment + baseline[1:]
            self.rejected()
        for bad_id in (None, ''):
            pair = copy.deepcopy(earlier); pair[1]['params']['item']['call_id'] = bad_id
            self.t.events = baseline[:1] + pair + baseline[1:]; self.rejected()
        # A yielded cell may remain active beyond its raw call/output interval.
        pair = copy.deepcopy(earlier)
        pair[1]['params']['item']['output'] = 'Script running with cell ID 4\nWall time 0.1 seconds\nOutput:\nWarning: truncated output'
        self.t.events = baseline[:1] + pair + baseline[1:]; self.rejected()
        # A structurally complete result still cannot overlap the candidate.
        pair = self.unrelated_result('overlap', 100000, 110500)
        self.t.events = baseline[:2] + pair + baseline[2:]; self.rejected()
        # A native command started by an earlier call must also have ended.
        self.t.events = baseline[:1] + earlier + baseline[1:]
        command = copy.deepcopy(baseline[2]); command['params']['item']['id'] = 'unrelated-native'
        self.t.events.insert(2, command); self.rejected()

    def test_direct_call_requires_exact_native_id_and_whole_envelope(self):
        self.call.clear(); self.call.update(type='function_call', call_id='read-1', name='exec_command', arguments=json.dumps(self.options))
        self.output.clear(); self.output.update(type='function_call_output', call_id='read-1',
            output='Chunk ID: ab12\nWall time: 0.1000 seconds\nProcess exited with code 0\nOutput:\n' + self.stdout)
        self.assertEqual(self.proof()['binding'], 'direct_call_id')
        self.call['call_id'] = self.output['call_id'] = 'unrelated'
        self.rejected()

    def test_exact_output_field_and_ordered_text_content(self):
        self.call['input'] = "const result = await tools.exec_command({cmd:'cat /workspace/Tools.md'}); text(result.output);"
        self.output['output'] = [{'type': 'input_text', 'text': 'Script completed\nWall time 0.1 seconds\nOutput:\n'},
                                 {'type': 'input_text', 'text': self.stdout}]
        self.assertTrue(self.proof()['whole_prepared_payload_consumed'])
        self.output['output'].reverse(); self.rejected()

    def test_missing_prefix_forged_suffix_truncation_and_unknown_envelopes(self):
        original = self.output['output']
        cases = [original.replace(self.stdout.strip(), self.stdout.strip()[3:]),
                 original + 'extra', original.replace('Script completed', 'Script running with cell ID 1'),
                 original.replace('Script completed', 'Script failed'),
                 original.replace('chunk_id', 'unknown_key'),
                 original.replace('0, "output"', 'false, "output"'),
                 original.replace(self.stdout.strip(), '[REDACTED_EPHEMERAL_CAPABILITY]'),
                 'Output:\n' + self.stdout, self.stdout]
        for value in cases:
            with self.subTest(value=value[:60]):
                self.output['output'] = value; self.rejected()

    def test_unknown_nontext_and_duplicate_json_keys(self):
        for value in ([{'type': 'input_image', 'image_url': 'data:fake'}],
                      [{'type': 'input_text', 'text': self.stdout, 'extra': True}],
                      'Script completed\nWall time 0.1 seconds\nOutput:\n{"exit_code":0,"exit_code":0}'):
            self.output['output'] = value; self.rejected()

    def test_unknown_raw_envelope_foreign_tool_noninteger_exit_and_caps(self):
        self.output['extra'] = True; self.rejected(); self.output.pop('extra')
        self.output['name'] = 'other'; self.rejected(); self.output.pop('name')
        self.call['status'] = 'in_progress'; self.rejected(); self.call.pop('status')
        self.item['exitCode'] = False; self.rejected(); self.item['exitCode'] = 0
        self.t.rows[6]['message']['params']['exitCode'] = False; self.rejected()
        for text in ('x' * (raw.MAX_BYTES + 1), 'Script completed\nWall time 0.1 seconds\nOutput:\nWarning: truncated output\nx'):
            with self.assertRaises(ValueError): raw.prepared_payload(text, code_mode=True, output_only=True)

    def test_unresolved_earlier_process_and_native_request_competitor_rejected(self):
        earlier = copy.deepcopy(self.t.events[2]); earlier['params']['item']['id'] = 'earlier'
        self.t.events.insert(1, earlier); self.rejected(); self.t.events.pop(1)
        extra = copy.deepcopy(self.t.rows[1]); extra['wall_unix_s'] = 100.15
        extra['message']['id'] = 8; extra['message']['params'].update(processId='p-2', metadata={'toolCallId': 'different'})
        self.t.rows.insert(2, extra)
        # Rebind original delivery positions after the additional authenticated request.
        for row in self.t.rows:
            if row.get('kind') == 'delivered': row['response_sequence'] += 1
        self.rejected()

    def test_foreign_missing_duplicate_and_reordered_raw_identity(self):
        self.raw_output['params']['turnId'] = 'foreign'; self.rejected()
        self.raw_output['params']['turnId'] = 'turn-1'
        self.output['call_id'] = None; self.rejected()
        self.output['call_id'] = 'outer-1'
        self.t.events.append(copy.deepcopy(self.raw_output)); self.rejected(); self.t.events.pop()
        self.t.events[1], self.t.events[-1] = self.t.events[-1], self.t.events[1]; self.rejected()

    def test_extra_outer_call_extra_command_or_unresolved_command(self):
        other = self.event({'type': 'function_call', 'call_id': 'other', 'name': 'exec_command', 'arguments': '{}'}, 100000)
        end = self.event({'type': 'function_call_output', 'call_id': 'other', 'output': 'other'}, 110001)
        self.t.events[2:2] = [other, end]; self.rejected(); del self.t.events[2:4]
        self.t.events.insert(3, copy.deepcopy(self.t.events[2])); self.rejected(); self.t.events.pop(3)
        self.t.events.pop(2); self.rejected()

    def test_receipt_option_source_and_chronology_fail_closed(self):
        self.raw_call['emittedAtMs'] = 110500; self.rejected(); self.raw_call['emittedAtMs'] = 99000
        self.t.events[0]['params']['experimentalRawEvents'] = False; self.rejected()
        self.t.events[0]['params']['experimentalRawEvents'] = True
        (self.t.root / 'client/preflight.json').write_text('{}'); self.rejected()
        (self.t.root / 'client/preflight.json').write_text(json.dumps({'experimental_raw_events_requested': True,
            'experimental_raw_events_thread_start_accepted': True, 'preflight_passed': True, 'thread_id': 'thread-1'}))
        with zipfile.ZipFile(self.t.archive) as z: files = {n: z.read(n) for n in z.namelist()}
        name = next(n for n in files if n.endswith('/assessment/raw_tool_result_reads.py')); files[name] += b'changed'
        with zipfile.ZipFile(self.t.archive, 'w') as z:
            for n, b in files.items(): z.writestr(n, b)
        self.rejected()

    def test_environment_and_actual_source_changes_remain_rejected(self):
        self.t.params['env']['BASH_ENV'] = 'notes/inject'; self.t.save_capture()
        self.assertFalse(self.f.assess()['startup']['Tools.md'])
        self.t.params['env'].pop('BASH_ENV'); self.t.save_capture()
        self.t.hashes['Tools.md'] = '0' * 64
        self.t.write_json('runtime-input-hashes.json', self.t.hashes)
        self.assertFalse(self.f.assess()['startup']['Tools.md'])

    def test_current_lifecycle_sources_are_bound_to_the_exact_read_proof(self):
        proof = self.proof()
        bindings = {entry['path']:entry['sha256'] for entry in proof['source_contract']}
        for suffix in ('/harness/bootstrap_client_v4.py', '/harness/native_quiescence.py'):
            matches = [name for name in bindings if name.endswith(suffix)]
            self.assertEqual(len(matches), 1)
            self.assertEqual(bindings[matches[0]], raw.SOURCE_HASHES[suffix])
        self.assertEqual(proof['source_payload_sha256'], raw.sha(self.stdout.encode()))

    def test_missing_changed_or_ambiguous_lifecycle_source_rejects_valid_output(self):
        with zipfile.ZipFile(self.t.archive) as archive:
            original = {name:archive.read(name) for name in archive.namelist()}
        for suffix in ('/harness/bootstrap_client_v4.py', '/harness/native_quiescence.py'):
            name = next(name for name in original if name.endswith(suffix))
            for mutation in ('absent', 'changed', 'ambiguous'):
                with self.subTest(source=suffix, mutation=mutation):
                    files = dict(original)
                    if mutation == 'absent': del files[name]
                    elif mutation == 'changed': files[name] += b'\n# unreviewed source change\n'
                    else: files['other-prefix' + suffix] = files[name]
                    with zipfile.ZipFile(self.t.archive, 'w') as archive:
                        for member,data in files.items(): archive.writestr(member, data)
                    with self.assertRaisesRegex(ValueError, 'Raw-result source absent/changed'):
                        self.proof()

    def test_finite_supported_wrapper_classes(self):
        invoke = 'await tools.exec_command({cmd:"cat /workspace/Tools.md",tty:false,max_output_tokens:5000})'
        forms = [('text(' + invoke + ')', False), ('console.log((' + invoke + ').output);', True),
                 ('let r = ' + invoke + '; text(r.output)', True), ('const r = ' + invoke + '\nconsole.log(r)', False),
                 ('// @exec: {"max_output_tokens": 5000}\ntext(' + invoke + ');', False)]
        for script, expected in forms:
            options, output_only = raw.parse_wrapper(script)
            self.assertEqual(output_only, expected); self.assertEqual(options['cmd'], self.command)

    def test_arbitrary_js_mutation_transform_alias_and_extra_print_rejected(self):
        inv = 'await tools.exec_command({cmd:"cat /workspace/Tools.md"})'
        forms = ['text(' + inv + '.output)', 'text((' + inv + ').output.slice(3))',
                 'const r = ' + inv + '; text(r); text(r)', 'const r = ' + inv + '; r.output="fake"; text(r)',
                 'const x=tools.exec_command; text(await x({cmd:"cat Tools.md"}))',
                 'text(await tools.exec_command({...x,cmd:"cat Tools.md"}))',
                 'text(await tools.exec_command({cmd:`cat Tools.md`}))',
                 'text(await tools.exec_command({cmd:"cat Tools.md",cmd:"cat Tools.md"}))',
                 'text(await tools.exec_command({["cmd"]:"cat Tools.md"}))',
                 'text(' + inv + '); // anything', 'text(Promise.all([' + inv + ']))',
                 '// @exec: {"unknown":1}\ntext(' + inv + ')', 'text(await tools.exec_command({cmd: x}))',
                 '"text"(' + inv + ')', 'text(await "tools".exec_command({cmd:"cat Tools.md"}))']
        for script in forms:
            with self.subTest(script=script):
                with self.assertRaises(ValueError): raw.parse_wrapper(script)


if __name__ == '__main__':
    unittest.main()
