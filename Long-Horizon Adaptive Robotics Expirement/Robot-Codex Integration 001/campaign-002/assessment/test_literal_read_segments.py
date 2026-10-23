"""Finite grammar, byte attribution and trusted-source attack tests; no launches."""
import base64
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile

import literal_read_segments as reader
import test_empty_startup_reads as fixture_tools


class LiteralReadSegmentsTests(unittest.TestCase):
    def test_completion_interval_and_post_send_receipt_race(self):
        for emitted, delivery in ((100900, 100.9000233), (100850, 100.9)):
            with self.subTest(emitted=emitted):
                self.f.make_capture(self.command, output=self.output)
                self.f.events[-1]['emittedAtMs'] = emitted
                self.f.rows[-2]['wall_unix_s'] = delivery
                self.f.save_capture()
                result = self.assess()
                self.assertFalse(result['errors'], result)
                proof = result['proofs'][0]['execution']
                self.assertEqual(proof['app_complete_wall_unix_s'], emitted / 1000)
                self.assertGreaterEqual(proof['evidence_complete_upper_wall_unix_s'], delivery)
                self.assertGreater(proof['evidence_complete_upper_wall_unix_s'], emitted / 1000)

    def test_episode_boundary_uses_conservative_delivery_bound(self):
        self.f.events[-1]['emittedAtMs'] = 100850
        self.f.history[-1]['wall_unix_s'] = 100.9
        self.f.save_capture()
        self.f.save_histories()
        self.assert_no_evidence()

    def setUp(self):
        self.f = fixture_tools.EmptyStartupReadsTests('test_known_recipe_has_explicit_proof_without_synthetic_cat')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        runtime = Path(__file__).resolve().parents[1] / 'harness/runtime.py'
        with zipfile.ZipFile(self.f.archive, 'a') as archive:
            archive.write(runtime, 'integration/campaign-002/harness/runtime.py')
        self.static = {name: ('# Initial ' + name + '\n').encode() for name in reader.STARTUP_PATHS}
        self.f.hashes.update({name: reader.sha(raw) for name, raw in self.static.items()})
        self.f.write_json('runtime-input-hashes.json', self.f.hashes)
        note = self.static['Continuity.md']
        (self.f.host / 'continuity-history' / (reader.sha(note) + '.md')).write_bytes(note)
        self.f.write_json('runtime-before-close.json', {'files': {name: {
            'base64': base64.b64encode(raw).decode(), 'bytes': len(raw),
            'sha256': reader.sha(raw), 'retained_sha256': reader.sha(raw)} for name, raw in self.static.items()}})
        self.f.write_json('stage-result.json', {'invocation_id': 'resume-test'})
        (self.f.host / 'result.json').write_text(json.dumps({'public_episode_id': 'episode-test'}))
        self.invocation = {'invocation_id': 'resume-test', 'authority_epoch': 4, 'state': 'active'}
        self.packet = {'run_id': 'episode-test', 'sequence': 30, 'capture_sim_time_s': 12., 'order': {'version': 1}}
        self.activation = {'activation_id': 'activation-001', 'authority_epoch': 4,
                           'invocation': self.invocation, 'order_version': 1}
        self.state = {'authority_epoch': 4, 'invocation': self.invocation, 'packet': self.packet}
        self.f.history = [
            {'event_id': 1, 'wall_unix_s': 80., 'type': 'continuity_committed',
             'payload': {'sha256': reader.sha(note), 'bytes': len(note)}},
            {'event_id': 2, 'wall_unix_s': 90., 'type': 'invocation_start-invocation', 'authority_epoch': 4,
             'payload': {'invocation': self.invocation}},
            {'event_id': 3, 'wall_unix_s': 99., 'type': 'observation', 'authority_epoch': 4,
             'payload': copy.deepcopy(self.packet)},
            {'event_id': 4, 'wall_unix_s': 200., 'type': 'episode_stopped', 'payload': {}},
        ]
        self.f.save_histories()
        self.command = 'cat /workspace/live/activation.json && cat /workspace/live/state.json && cat /workspace/Continuity.md'
        self.output = json.dumps(self.activation) + json.dumps(self.state) + note.decode()
        self.f.make_capture(self.command, output=self.output)

    def assess(self):
        return reader.assess_literal_reads(self.f.root, self.f.host, self.f.archive, 'episode-test', 4, 'resume-test')

    def assert_no_evidence(self):
        result = self.assess()
        self.assertFalse(any(result['startup'].values()), result)
        self.assertFalse(any(result['live'].values()), result)
        return result

    def test_known_mixed_chain_binds_every_byte_and_all_sources(self):
        result = self.assess()
        self.assertFalse(result['errors'], result)
        self.assertEqual(len(result['proofs']), 1)
        self.assertEqual(result['startup']['Continuity.md'][0]['input_sha256'], reader.sha(self.static['Continuity.md']))
        self.assertEqual(result['live']['live/state.json'][0]['protected_observation_event_id'], 3)
        proof = result['proofs'][0]
        self.assertEqual(proof['segments'][-1]['end_byte'], len(self.output.encode()))
        self.assertEqual(proof['execution']['argv'], self.f.params['argv'])
        self.assertTrue(proof['whole_output_consumed'])
        self.assertEqual(len(proof['source_contract']), 4)
        self.assertTrue(any(p['path'].endswith('literal_read_segments.py') for p in proof['inputs']))
        self.assertTrue(any(p['path'].endswith('executor-1-capture.jsonl') for p in proof['inputs']))
        self.assertNotIn('command', proof)

    def test_general_multioperand_reordered_repeated_and_quoted_paths(self):
        commands = (
            'cat Tasks.md "live/state.json" && /bin/cat \'Continuity.md\' Tools.md',
            '/usr/bin/cat /workspace/Tasks.md /workspace/live/state.json /workspace/Continuity.md /workspace/Tools.md',
        )
        output = self.static['Tasks.md'].decode() + json.dumps(self.state) + self.static['Continuity.md'].decode() + self.static['Tools.md'].decode()
        for command in commands:
            with self.subTest(command=command):
                self.f.make_capture(command, output=output)
                result = self.assess()
                self.assertFalse(result['errors'], result)
                self.assertTrue(result['startup']['Tasks.md'])
                self.assertTrue(result['startup']['Tools.md'])
                self.assertTrue(result['live']['live/state.json'])
        self.f.make_capture('cat Robot.md&&cat Robot.md', output=(self.static['Robot.md'] * 2).decode())
        self.assertEqual(len(self.assess()['startup']['Robot.md']), 2)

    def test_commands_options_unknown_paths_and_shell_attacks_rejected(self):
        commands = ('cat live/state.json; echo forged', 'cat live/state.json || cat Continuity.md',
                    'cat live/state.json | cat', 'cat live/state.json > notes/out',
                    'cat $(echo live/state.json)', 'cat `echo live/state.json`',
                    'cat -n live/state.json', 'cat -- live/state.json',
                    'cat notes/fake.json', 'cat /etc/passwd', 'cat ./live/state.json',
                    'cat live/../live/state.json', 'cat live/state.json # ignored',
                    'cat live/state.json\ncat Continuity.md', 'echo "$fake"',
                    'cat live/state.json && echo "{}"', 'cat live/state.json &&',
                    'cat "live/state.json"x', "cat live/state.json '&&' cat Continuity.md",
                    'cat live/state.json&&&cat Continuity.md', 'cat live/state.json & cat Continuity.md')
        for command in commands:
            with self.subTest(command=command):
                self.f.make_capture(command, output=self.output)
                self.assert_no_evidence()

    def test_operand_and_script_bounds(self):
        self.assertEqual(reader.literal_cat_paths(['/usr/bin/bash', '-lc', 'cat ' + 'Robot.md ' * 17]), [])
        self.assertEqual(reader.literal_cat_paths(['/usr/bin/bash', '-lc', ' ' * 4097 + 'cat Robot.md']), [])
        self.assertEqual(reader.literal_cat_paths(['/usr/bin/bash', '-c', 'cat Robot.md']), [])

    def test_trailing_missing_reordered_and_transformed_bytes_rejected(self):
        for output in (self.output + 'extra', self.output[:-1], ' ' + self.output,
                       self.output.replace('}{', '}\n{'),
                       json.dumps(self.state) + json.dumps(self.activation) + self.static['Continuity.md'].decode(),
                       json.dumps(self.activation, separators=(',', ':')) + json.dumps(self.state) + self.static['Continuity.md'].decode()):
            with self.subTest(output=output[:60]):
                self.f.make_capture(self.command, output=output)
                self.assert_no_evidence()

    def test_duplicate_json_keys_nonfinite_and_nondictionary_rejected(self):
        for payload in ('{"authority_epoch": 4, "authority_epoch": 4}', '{"value": NaN}', '[]', 'null'):
            self.f.make_capture('cat live/state.json', output=payload)
            self.assert_no_evidence()

    def test_empty_composite_is_not_inferred_from_zero_width_segment(self):
        self.f.hashes['Continuity.md'] = reader.sha(b'')
        self.f.write_json('runtime-input-hashes.json', self.f.hashes)
        self.f.make_capture(self.command, output=json.dumps(self.activation) + json.dumps(self.state))
        self.assert_no_evidence()

    def test_unknown_input_or_wrong_protected_continuity_bytes_rejected(self):
        path = self.f.host / 'continuity-history' / (reader.sha(self.static['Continuity.md']) + '.md')
        path.write_bytes(b'changed')
        self.assert_no_evidence()
        path.write_bytes(self.static['Continuity.md'])
        self.f.history[0]['payload']['sha256'] = '0' * 64
        self.f.save_histories()
        self.assert_no_evidence()

    def test_continuity_commit_must_precede_read_strictly(self):
        self.f.history[0]['wall_unix_s'] = self.f.rows[1]['wall_unix_s']
        self.f.save_histories()
        self.assert_no_evidence()

    def test_static_snapshot_must_match_initial_raw_and_retained_hash(self):
        self.f.make_capture('cat Tasks.md', output=self.static['Tasks.md'].decode())
        self.f.write_json('runtime-before-close.json', {'files': {'Tasks.md': {
            'base64': base64.b64encode(self.static['Tasks.md']).decode(), 'bytes': len(self.static['Tasks.md']),
            'sha256': '0' * 64, 'retained_sha256': reader.sha(self.static['Tasks.md'])}}})
        self.assert_no_evidence()

    def test_short_app_projection_blocks_startup_but_live_flag_is_honest(self):
        self.f.make_capture(self.command, output=self.output, projection=self.output[-50:])
        result = self.assess()
        self.assertFalse(result['startup']['Continuity.md'])
        self.assertTrue(result['live']['live/state.json'])
        self.assertFalse(result['live']['live/state.json'][0]['app_projection_equals_executor'])

    def prepared_fixture(self):
        names = ('Tasks.md', 'Robot.md', 'Tools.md', 'Continuity.md')
        output = b''.join(self.static[name] for name in names).decode()
        self.f.make_capture('cat ' + ' '.join(names), output=output, projection=output[-10:])
        return {'covered_segment_indices': [0, 1],
                'match': 'complete_fixed_file_in_prepared_result_prefix',
                'evidence_complete_upper_wall_unix_s': 120.0}

    def test_prepared_prefix_credits_only_complete_selected_fixed_segments(self):
        candidate = self.prepared_fixture()
        with patch('raw_tool_result_reads.raw_result_proof', side_effect=ValueError('retained raw V1 failure')), \
                patch('prepared_startup_segments.prove_prepared_segments', return_value=candidate):
            result = self.assess()
        for name in ('Tasks.md', 'Robot.md'):
            evidence = result['startup'][name][0]
            self.assertEqual(evidence['match'], candidate['match'])
            self.assertFalse(evidence['app_projection_equals_executor'])
            self.assertEqual(evidence['input_sha256'], reader.sha(self.static[name]))
        self.assertFalse(result['startup']['Tools.md'])
        self.assertFalse(result['startup']['Continuity.md'])
        self.assertEqual(result['proofs'][0]['prepared_tool_result_error'], 'retained raw V1 failure')
        self.assertNotIn('aggregatedOutput', result['proofs'][0])

    def test_prepared_coverage_rejects_partial_index_injection_or_continuity(self):
        for indices in ([], [True], [-1], [4], [0, 0], [0, 3], '0'):
            with self.subTest(indices=indices):
                candidate = self.prepared_fixture()
                candidate['covered_segment_indices'] = indices
                with patch('raw_tool_result_reads.raw_result_proof', side_effect=ValueError('raw unavailable')), \
                        patch('prepared_startup_segments.prove_prepared_segments', return_value=candidate):
                    result = self.assess()
                self.assertFalse(any(result['startup'].values()))
                self.assertIn('invalid fixed-file segment coverage', result['proofs'][0]['prepared_startup_segments_error'])

    def test_prepared_delivery_bound_must_precede_protected_episode_end(self):
        for bound in (100.0, 200.0, float('inf'), True):
            with self.subTest(bound=bound):
                candidate = self.prepared_fixture()
                candidate['evidence_complete_upper_wall_unix_s'] = bound
                with patch('raw_tool_result_reads.raw_result_proof', side_effect=ValueError('raw unavailable')), \
                        patch('prepared_startup_segments.prove_prepared_segments', return_value=candidate):
                    result = self.assess()
                self.assertFalse(any(result['startup'].values()))
                self.assertIn('prepared_startup_segments_error', result['proofs'][0])

    def test_original_complete_raw_proof_retains_precedence_and_semantics(self):
        self.prepared_fixture()
        original = {'schema': 'original-development-fixture'}
        with patch('raw_tool_result_reads.raw_result_proof', return_value=original), \
                patch('prepared_startup_segments.prove_prepared_segments') as new_proof:
            result = self.assess()
        new_proof.assert_not_called()
        for name in ('Tasks.md', 'Robot.md', 'Tools.md', 'Continuity.md'):
            self.assertEqual(result['startup'][name][0]['prepared_tool_result'], original)
            self.assertEqual(result['startup'][name][0]['match'], 'complete_prepared_tool_result_literal_segments')

    def test_stdout_after_exit_is_retained_through_closed(self):
        # Split the same observed bytes across output-before-exit and drain-after-exit.
        first, second = self.output[:50].encode(), self.output[50:].encode()
        self.f.rows[4]['message']['params']['chunk'] = base64.b64encode(first).decode()
        self.f.rows[4]['blobs'] = [{'path': ['params', 'chunk'], 'raw_sha256': reader.sha(first),
                                   'retained_sha256': reader.sha(first), 'raw_bytes': len(first), 'retained_bytes': len(first)}]
        drain = copy.deepcopy(self.f.rows[4])
        drain['wall_unix_s'] = 100.75
        drain['message']['params'].update(seq=3, chunk=base64.b64encode(second).decode())
        drain['blobs'] = [{'path': ['params', 'chunk'], 'raw_sha256': reader.sha(second),
                           'retained_sha256': reader.sha(second), 'raw_bytes': len(second), 'retained_bytes': len(second)}]
        delivery = {'schema': 'campaign002-executor-capture-1', 'connection_id': '1', 'kind': 'delivered',
                    'wall_unix_s': 100.76, 'response_sequence': 9}
        self.f.rows[8:8] = [drain, delivery]
        self.f.rows[10]['message']['params']['seq'] = 4
        self.f.rows[11]['response_sequence'] = 11
        self.f.save_capture()
        result = self.assess()
        self.assertTrue(result['startup']['Continuity.md'], result)
        self.assertEqual(result['proofs'][0]['executor_provenance']['process_sequences'], 4)

    def test_failed_process_missing_close_and_forged_command_actions_rejected(self):
        self.f.make_capture(self.command, output=self.output, exit_code=1)
        self.assert_no_evidence()
        self.f.make_capture(self.command, output=self.output)
        self.f.rows.pop(-2)
        self.f.save_capture()
        self.assert_no_evidence()
        self.f.make_capture('echo forged', output=self.output)
        self.f.events[-1]['params']['item']['commandActions'] = [{'command': self.command}]
        self.f.save_capture()
        self.assert_no_evidence()

    def test_environment_and_actual_argv_forgery_rejected(self):
        for override in ({'env': {'PATH': '/workspace/programs'}}, {'env': {'BASH_ENV': 'notes/override'}},
                         {'env': {'BASH_FUNC_cat%%': '() { echo forged; }'}},
                         {'argv': ['/usr/bin/bash', '-lc', 'echo forged']}, {'cwd': 'file:///workspace/notes'}):
            self.f.make_capture(self.command, output=self.output)
            self.f.params.update(override)
            self.f.save_capture()
            self.assert_no_evidence()
        self.f.make_capture(self.command, output=self.output)
        self.f.params['envPolicy']['set'] = {'PATH': '/workspace/programs'}
        self.f.save_capture()
        self.assert_no_evidence()

    def test_source_contract_changed_or_missing_rejected(self):
        with zipfile.ZipFile(self.f.archive) as archive:
            original = {name: archive.read(name) for name in archive.namelist()}
        target = 'integration/campaign-002/harness/runtime.py'
        for mutation in ('changed','missing','ambiguous'):
            with self.subTest(mutation=mutation):
                files = dict(original)
                if mutation == 'changed': files[target] = b'json.dumps(value, indent=2)'
                elif mutation == 'missing': del files[target]
                else: files['duplicate-prefix/campaign-002/harness/runtime.py'] = files[target]
                with zipfile.ZipFile(self.f.archive, 'w') as archive:
                    for name, data in files.items(): archive.writestr(name, data)
                result = self.assert_no_evidence()
                self.assertIn('Readonly mirror producer source absent/changed', result['errors'])

    def test_ambiguous_command_identity_and_incomplete_protected_history_rejected(self):
        self.f.events.append(copy.deepcopy(self.f.events[-1]))
        self.f.save_capture()
        self.assert_no_evidence()
        self.f.make_capture(self.command, output=self.output)
        self.f.history.pop(1)
        self.f.save_histories()
        self.assert_no_evidence()

    def test_stage_and_protected_invocation_binding_cannot_be_relabelled(self):
        self.f.write_json('stage-result.json', {'invocation_id': 'other-invocation'})
        self.assert_no_evidence()
        self.f.write_json('stage-result.json', {'invocation_id': 'resume-test'})
        self.f.history[1]['authority_epoch'] = 3
        self.f.save_histories()
        self.assert_no_evidence()

    def test_wrong_epoch_invocation_episode_capture_sequence_or_order_cannot_match_live(self):
        mutations = [lambda s: s.update(authority_epoch=3),
                     lambda s: s['invocation'].update(invocation_id='old-invocation'),
                     lambda s: s['packet'].update(run_id='other-episode'),
                     lambda s: s['packet'].update(sequence=29),
                     lambda s: s['packet'].update(capture_sim_time_s=11.),
                     lambda s: s['packet'].update(order={'version': 2})]
        for mutate in mutations:
            state = copy.deepcopy(self.state)
            mutate(state)
            self.f.make_capture('cat live/state.json', output=json.dumps(state))
            self.assertFalse(self.assess()['live']['live/state.json'])

    def test_duplicate_or_missing_protected_observation_fails_live_match(self):
        self.f.history[2]['authority_epoch'] = 3
        self.f.save_histories()
        self.assertFalse(self.assess()['live']['live/state.json'])
        self.f.history[2]['authority_epoch'] = 4
        duplicate = copy.deepcopy(self.f.history[2])
        duplicate['event_id'] = 4
        self.f.history.insert(3, duplicate)
        self.f.history[-1]['event_id'] = 5
        self.f.save_histories()
        self.assertFalse(self.assess()['live']['live/state.json'])


if __name__ == '__main__':
    unittest.main()
