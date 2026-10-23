"""Finite composition proofs against real retained-capture fixtures; no launches."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile

import initial_read_composition as reader
import test_literal_read_segments as fixtures


class InitialReadCompositionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.LiteralReadSegmentsTests('test_known_mixed_chain_binds_every_byte_and_all_sources')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.f = self.fixture.f
        self.note = self.fixture.static['Continuity.md']

    def assess(self):
        return reader.assess_initial_read_compositions(self.f.root, self.f.host, self.f.archive,
                                                       'episode-test', 4, 'resume-test')

    def accepted(self):
        result = self.assess()
        self.assertEqual(result['errors'], [], result)
        self.assertEqual(len(result['startup']['Continuity.md']), 1, result)
        self.assertEqual(len(result['proofs']), 1, result)
        return result['proofs'][0]

    def rejected(self):
        result = self.assess()
        self.assertEqual(result['startup']['Continuity.md'], [], result)
        self.assertEqual(result['proofs'], [], result)
        return result

    def prefix(self, note=None, tail=b'/workspace/notes/a\n', command=None, **kwargs):
        self.note = self.note if note is None else note
        digest = reader.sha(self.note)
        self.f.hashes['Continuity.md'] = digest
        self.f.write_json('runtime-input-hashes.json', self.f.hashes)
        (self.f.host / 'continuity-history' / (digest + '.md')).write_bytes(self.note)
        self.f.history[0] = {'event_id': 1, 'wall_unix_s': 80., 'type': 'continuity_committed',
                             'payload': {'sha256': digest, 'bytes': len(self.note)}}
        self.f.save_histories()
        command = command or 'cat /workspace/Continuity.md && ' + reader.FIND_SCRIPT
        self.f.make_capture(command, output=(self.note + tail).decode(), **kwargs)

    def empty(self, command=None, output=None, **kwargs):
        self.f.hashes['Continuity.md'] = reader.EMPTY_SHA256
        self.f.write_json('runtime-input-hashes.json', self.f.hashes)
        (self.f.host / 'continuity-history' / (reader.EMPTY_SHA256 + '.md')).write_bytes(b'')
        self.f.history[0] = {'event_id': 1, 'wall_unix_s': 80., 'type': 'episode_started', 'payload': {}}
        self.f.save_histories()
        self.f.make_capture(command or 'cat live/activation.json live/state.json Continuity.md',
            output=output if output is not None else json.dumps(self.fixture.activation) + json.dumps(self.fixture.state),
            **kwargs)

    def test_terminal_empty_has_explicit_zero_span_and_protected_live_joins(self):
        self.empty()
        proof = self.accepted()
        self.assertEqual(proof['match'], 'authenticated_terminal_empty_continuity')
        self.assertTrue(proof['whole_output_consumed'])
        self.assertEqual(proof['segment']['bytes'], 0)
        self.assertEqual(proof['segment']['start_byte'], proof['segment']['end_byte'])
        self.assertEqual(proof['segment']['sha256'], reader.EMPTY_SHA256)
        self.assertEqual(proof['protected_live_sources'][-1]['protected_observation_event_id'], 3)
        self.assertTrue(proof['executor_provenance']['app_projection_equals_executor'])
        self.assertIn('evidence_complete_upper_wall_unix_s', proof['execution'])
        self.assertTrue(any(r['path'].endswith('completion_chronology.py') for r in proof['inputs']))

    def test_terminal_empty_can_follow_exact_nonempty_static_reads(self):
        self.empty('cat "Robot.md" && /bin/cat /workspace/Continuity.md',
                   self.fixture.static['Robot.md'].decode())
        proof = self.accepted()
        self.assertEqual(proof['ordered_paths'], ['Robot.md', 'Continuity.md'])
        self.assertEqual(proof['protected_live_sources'], [])

    def test_terminal_empty_missing_changed_or_nonempty_reference_rejected(self):
        self.empty()
        note = self.f.host / 'continuity-history' / (reader.EMPTY_SHA256 + '.md')
        note.unlink()
        self.rejected()
        note.write_bytes(b'changed')
        self.rejected()
        self.f.hashes['Continuity.md'] = reader.sha(b'nonempty')
        self.f.write_json('runtime-input-hashes.json', self.f.hashes)
        self.rejected()

    def test_terminal_empty_nonterminal_duplicate_sole_and_unknown_operands_rejected(self):
        for command in ('cat Continuity.md live/state.json',
                        'cat live/state.json Continuity.md Continuity.md', 'cat Continuity.md',
                        'cat notes/fake Continuity.md', 'cat -n live/state.json Continuity.md',
                        'cat live/state.json Continuity.md > notes/out'):
            with self.subTest(command=command):
                self.empty(command)
                self.rejected()

    def test_terminal_empty_extra_truncated_reordered_or_transformed_bytes_rejected(self):
        expected = json.dumps(self.fixture.activation) + json.dumps(self.fixture.state)
        for output in (expected + '\n', expected[:-1], ' ' + expected,
                       json.dumps(self.fixture.state) + json.dumps(self.fixture.activation),
                       json.dumps(self.fixture.activation, separators=(',', ':')) + json.dumps(self.fixture.state)):
            with self.subTest(output=output[:40]):
                self.empty(output=output)
                self.rejected()

    def test_empty_live_identity_epoch_observation_order_must_match(self):
        mutations = [lambda s: s.update(authority_epoch=3),
                     lambda s: s['invocation'].update(invocation_id='other'),
                     lambda s: s['packet'].update(sequence=29),
                     lambda s: s['packet'].update(run_id='other'),
                     lambda s: s['packet'].update(capture_sim_time_s=11.),
                     lambda s: s['packet'].update(order={'version': 2})]
        for change in mutations:
            with self.subTest(change=change):
                state = copy.deepcopy(self.fixture.state)
                change(state)
                self.empty(output=json.dumps(self.fixture.activation) + json.dumps(state))
                self.rejected()

    def test_prefix_uses_initial_protected_note_not_mutable_final_snapshot(self):
        self.prefix()
        self.f.write_json('runtime-before-close.json', {'files': {'.continuity/Continuity.md': {
            'bytes': 5, 'sha256': reader.sha(b'later'), 'base64': 'bGF0ZXI='}}})
        proof = self.accepted()
        self.assertEqual(proof['match'], 'complete_initial_continuity_prefix_from_literal_cat')
        self.assertEqual(proof['segment']['end_byte'], len(self.note))
        self.assertEqual(proof['input_sha256'], reader.sha(self.note))
        self.assertFalse(proof['whole_current_file_identity_claimed'])
        self.assertFalse(proof['remainder_listing_snapshot_claimed'])
        self.assertEqual(proof['static_sources']['Continuity.md']['protected_commit_event_ids'], [1])

    def test_prefix_tail_is_unattributed_including_extra_cat_bytes_and_newline_filenames(self):
        for tail in (b'', b'Extra mutable cat bytes\n',
                     b'/workspace/notes/name\nwith\nnewlines\n/workspace/programs/a\n',
                     b'cat suffix\n/workspace/notes/a\n'):
            with self.subTest(tail=tail):
                self.prefix(tail=tail)
                proof = self.accepted()
                self.assertEqual(proof['unattributed_remainder']['bytes'], len(tail))
                self.assertEqual(proof['unattributed_remainder']['sha256'], reader.sha(tail))
                self.assertNotIn('listing', proof)

    def test_find_root_wholly_inside_required_prefix_is_rejected(self):
        for root in reader.ROOT_PREFIXES:
            for expected in (root, b'note\n' + root + b'/filename\n', root + b'\nmalicious-name'):
                with self.subTest(expected=expected):
                    self.prefix(note=expected)
                    self.rejected()

    def test_find_root_straddling_prefix_end_all_proper_lengths_rejected(self):
        # A shortened cat plus a find pathname could produce these exact bytes.
        for root in reader.ROOT_PREFIXES:
            for size in range(1, len(root)):
                expected = b'short cat\n' + root[:size]
                with self.subTest(root=root, size=size):
                    with self.assertRaisesRegex(ValueError, 'straddle'):
                        reader.prefix_attribution(expected, b'short cat\n' + root + b'/name\n')

    def test_listing_contribution_cannot_pass_at_any_prefix_cut(self):
        # Construct actual cat+find byte streams and try every candidate N.
        # A passing attribution may never include even one find-produced byte.
        accepted = 0
        for cat in (b'', b'plain note\n', b'/work', b'note\n/workspace/notes already mentioned\n'):
            for root in reader.ROOT_PREFIXES:
                for filename in (b'/a\n', b'/name\nwith\nnewlines\n', b'/../programs/x\n'):
                    observed = cat + root + filename
                    for size in range(1, len(observed) + 1):
                        try:
                            reader.prefix_attribution(observed[:size], observed)
                        except ValueError:
                            continue
                        accepted += 1
                        self.assertLessEqual(size, len(cat), (cat, root, filename, size))
        self.assertGreater(accepted, 0)

    def test_prefix_changed_missing_empty_and_uncommitted_initial_reference_rejected(self):
        self.prefix()
        note = self.f.host / 'continuity-history' / (reader.sha(self.note) + '.md')
        note.write_bytes(b'forged')
        self.rejected()
        note.unlink()
        self.rejected()
        self.prefix(note=b'')
        self.rejected()
        self.prefix(note=b'initial\n')
        self.f.history[0]['payload']['sha256'] = '0' * 64
        self.f.save_histories()
        self.rejected()

    def test_prefix_commit_must_strictly_precede_request(self):
        self.prefix()
        self.f.history[0]['wall_unix_s'] = self.f.rows[1]['wall_unix_s']
        self.f.history.sort(key=lambda r: r['wall_unix_s'])
        for i, row in enumerate(self.f.history, 1): row['event_id'] = i
        self.f.save_histories()
        self.rejected()

    def test_find_finite_grammar_rejects_other_actions_roots_shell_and_formatters(self):
        valid = 'cat /workspace/Continuity.md && ' + reader.FIND_SCRIPT
        invalid = (valid + '; echo extra', valid + ' && cat Tools.md', valid + '\n',
                   valid.replace('&&', ';'), valid.replace('&&', '||'),
                   valid.replace('-maxdepth 3', '-maxdepth 4'), valid.replace('-type f', '-type d'),
                   valid.replace('/workspace/notes', '/workspace/.continuity'),
                   valid.replace('find ', 'find -L '), valid.replace("'%p\\n'", "'%f\\n'"),
                   valid.replace('-printf', '-exec'), valid.replace('cat ', 'cat -n ', 1),
                   valid.replace('cat ', 'echo ', 1), valid + ' > notes/out',
                   valid.replace('Continuity.md', '$(echo Continuity.md)', 1),
                   valid.replace('find', "'find'"))
        for command in invalid:
            with self.subTest(command=command):
                self.prefix(command=command)
                self.rejected()
        for operand in ('Continuity.md', '/workspace/Continuity.md', '"Continuity.md"', "'/workspace/Continuity.md'"):
            self.prefix(command='cat ' + operand + ' && ' + reader.FIND_SCRIPT)
            self.accepted()

    def test_script_operand_and_output_bounds_are_fixed(self):
        self.prefix(command=' ' * 4097 + 'cat Continuity.md && ' + reader.FIND_SCRIPT)
        self.rejected()
        self.empty('cat ' + 'Robot.md ' * 16 + 'Continuity.md')
        self.rejected()
        with self.assertRaisesRegex(ValueError, 'oversize'):
            reader.prefix_attribution(b'initial\n', b'x' * (4 * 1024 * 1024 + 1))

    def test_no_prepared_output_fallback_for_short_or_changed_app_projection(self):
        for setup in (self.empty, self.prefix):
            for projection in ('', 'short', 'forged identical-looking prefix'):
                with self.subTest(form=setup.__name__, projection=projection):
                    setup(projection=projection)
                    self.rejected()

    def test_nonzero_boolean_exit_stderr_and_sandbox_denial_rejected(self):
        for form in (self.empty, self.prefix):
            for kind in ('exit', 'boolean_exit', 'stderr', 'sandbox'):
                with self.subTest(form=form.__name__, kind=kind):
                    form()
                    if kind == 'exit': self.f.rows[6]['message']['params']['exitCode'] = 1
                    if kind == 'boolean_exit': self.f.events[-1]['params']['item']['exitCode'] = False
                    if kind == 'stderr': self.f.rows[4]['message']['params']['stream'] = 'stderr'
                    if kind == 'sandbox': self.f.rows[6]['message']['params']['sandboxDenied'] = True
                    self.f.save_capture()
                    self.rejected()

    def test_hash_loss_missing_delivery_closed_tail_and_duplicate_identity_rejected(self):
        for kind in ('blob_hash', 'delivery', 'closed', 'tail', 'duplicate'):
            with self.subTest(kind=kind):
                self.prefix()
                if kind == 'blob_hash': self.f.rows[4]['blobs'][0]['raw_sha256'] = '0' * 64
                if kind == 'delivery': self.f.rows.pop(9)
                if kind == 'closed': self.f.rows.pop(8)
                if kind == 'duplicate': self.f.events.append(copy.deepcopy(self.f.events[-1]))
                self.f.save_capture()
                if kind == 'tail':
                    p = self.f.root / 'executor-1-capture.jsonl'
                    p.write_bytes(p.read_bytes()[:-1])
                self.rejected()

    def test_actual_argv_environment_and_command_actions_cannot_forge_recipe(self):
        for mutation in ({'argv': ['/usr/bin/bash', '-lc', 'echo forged']},
                         {'env': {'BASH_FUNC_cat%%': '() { echo forged; }'}},
                         {'env': {'PATH': '/workspace/programs'}}, {'cwd': 'file:///workspace/notes'}):
            self.prefix()
            self.f.params.update(mutation)
            self.f.save_capture()
            self.rejected()
        self.prefix(command='echo forged')
        self.f.events[-1]['params']['item']['commandActions'] = [{'type': 'read', 'path': 'Continuity.md'}]
        self.f.save_capture()
        self.rejected()

    def test_source_archive_missing_changed_ambiguous_fails(self):
        self.prefix()
        with zipfile.ZipFile(self.f.archive) as z: original = {n: z.read(n) for n in z.namelist()}
        name = 'integration/campaign-002/harness/runtime.py'
        for kind in ('missing', 'changed', 'ambiguous'):
            files = dict(original)
            if kind == 'missing': del files[name]
            if kind == 'changed': files[name] += b'\n# changed'
            if kind == 'ambiguous': files['duplicate/campaign-002/harness/runtime.py'] = files[name]
            with zipfile.ZipFile(self.f.archive, 'w') as z:
                for n, content in files.items(): z.writestr(n, content)
            self.rejected()

    def test_protected_history_episode_invocation_and_completion_bound(self):
        self.prefix()
        self.f.write_json('stage-result.json', {'invocation_id': 'wrong'})
        self.rejected()
        self.f.write_json('stage-result.json', {'invocation_id': 'resume-test'})
        self.f.history[1]['authority_epoch'] = 3
        self.f.save_histories()
        self.rejected()
        self.f.history[1]['authority_epoch'] = 4
        self.f.history[-1]['type'] = 'not_stopped'
        self.f.save_histories()
        self.rejected()
        self.f.history[-1]['type'] = 'episode_stopped'
        self.f.history[-1]['wall_unix_s'] = 110.0005
        self.f.save_histories()
        self.rejected()  # Native interval upper is 110.001, not truncated 110.

    def test_shared_chronology_bound_is_required_not_silently_downgraded(self):
        self.prefix()
        with patch.object(reader.literal, 'execution_proof', return_value={
                'request_wall_unix_s': 100.1, 'app_complete_wall_unix_s': 110.}):
            self.rejected()


if __name__ == '__main__':
    unittest.main()
