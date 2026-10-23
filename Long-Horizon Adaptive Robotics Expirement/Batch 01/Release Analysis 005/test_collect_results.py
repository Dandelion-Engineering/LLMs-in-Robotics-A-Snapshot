"""Synthetic metadata tests only. Root executes these through the shared queue."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from synthetic_fixtures import Fixture, c


class RecoverySelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.f = Fixture(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def collect(self, **kwargs):
        with patch.object(c, 'verify_annex', side_effect=self.f.fake_verify):
            return c.collect(self.f.root, self.f.records, notes=self.f.notes, annex_path=self.f.annex_path, **kwargs)

    def test_original_projection_exactly_matches_unchanged_004(self):
        old = c.legacy.collect(self.f.root, self.f.records)
        new = self.collect()
        self.assertEqual(old['results'], [r for r in new['results'] if r['run_id'] == self.f.original])
        source = next(p for p in new['provenance'] if p['run_id'] == self.f.original)
        self.assertEqual({k: v for k, v in source.items() if k != 'provenance_kind'}, old['provenance'][0])
        self.assertEqual(new['counts'], {'planned': 264, 'original_finalized': 1, 'annex_finalized': 0,
                                        'administrative_interruption': 1, 'selected_for_analysis': 2, 'missing_disposition': 262})
        self.assertNotIn('complete_terminal_accounting', new)
        self.assertFalse(new['complete_disposition_accounting'])

    def test_admin_unknown_clocks_and_missing_integrity_are_not_filled(self):
        before = {p: p.read_bytes() for p in self.f.base.rglob('*') if p.is_file()}
        report = self.collect(); row = next(r for r in report['results'] if r['run_id'] == self.f.admin)
        for key in ('ended_at', 'physical_ended_at', 'completion_time_s', 'wall_duration_s', 'model_calls', 'total_tokens', 'official_queue_exit_status'):
            self.assertIsNone(row[key])
        self.assertEqual(row['outcome'], 'unknown'); self.assertEqual(row['post_run_integrity'], {'state': 'missing'})
        self.assertEqual(row['official_queue_state'], 'interrupted')
        self.assertTrue(c.protocol._infra_invalid(row)); self.assertIsNone(c.protocol._success(row))
        self.assertFalse((self.f.root / 'attempts' / self.f.admin / 'terminal.json').exists())
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_new_terminal_requires_annex_source_and_revision(self):
        attempt, batch, terminal, record = self.f.add_terminal(self.f.new, recovery=True)
        report = self.collect(); self.assertEqual(report['counts']['annex_finalized'], 1)
        record['details']['revision_id'] = 'some-other-revision'
        with self.assertRaisesRegex(ValueError, 'new revision'):
            self.collect()

    def test_new_terminal_cannot_omit_authority_or_substitute_source_index(self):
        _, batch, _, _ = self.f.add_terminal(self.f.new, recovery=True)
        path = batch / 'finalized.json'; record = c.read(path)
        record['recovery_source_index_ref'] = c.ref(self.f.disposition_path); self.f.write(path, record)
        with self.assertRaisesRegex(ValueError, 'different authority'):
            self.collect()

    def test_new_terminal_failed_integrity_is_retained_not_upgraded(self):
        attempt, batch, terminal, record = self.f.add_terminal(self.f.new, recovery=True)
        terminal['post_run_integrity'] = {'passed': False, 'error': 'Synthetic integrity failure'}
        self.f.write(attempt / 'terminal.json', terminal)
        finished = c.read(batch / 'finished.json')
        finished['terminal_refs'] = [{'run_id': self.f.new, **c.ref(attempt / 'terminal.json')}]
        self.f.write(batch / 'finished.json', finished)
        record['details']['terminal_sha256'] = c.ref(attempt / 'terminal.json')['sha256']
        result = next(r for r in self.collect()['results'] if r['run_id'] == self.f.new)
        self.assertEqual(result['validity'], 'invalid'); self.assertTrue(result['infrastructure_invalid'])

    def test_interrupted_queue_receipt_cannot_claim_success(self):
        self.f.receipt.update(state='succeeded', exit_status=0); self.f.write(self.f.receipt_path, self.f.receipt)
        self.f.sync_authority()
        with self.assertRaisesRegex(ValueError, 'interrupted/null'):
            self.collect()

    def test_physical_end_or_passed_integrity_or_outcome_cannot_be_invented(self):
        original = copy.deepcopy(self.f.disposition)
        for key, value in (('physical_ended_at', '2026-09-24T20:40:38+00:00'),
                           ('post_run_integrity', {'state': 'passed'}), ('task_outcome', 'failure'),
                           ('metrics', {'wall_duration_s': 0})):
            with self.subTest(field=key):
                self.f.disposition = {**copy.deepcopy(original), key: value}; self.f.sync_authority()
                with self.assertRaisesRegex(ValueError, 'invent'):
                    self.collect()

    def test_exact_note_identity_and_target_are_required(self):
        self.f.notes[0]['id'] = 'unapproved-note'
        with self.assertRaisesRegex(ValueError, 'exact canonical note'):
            self.collect()
        self.f.notes[0]['id'] = 'canonical-admin-note'; self.f.notes[0]['target_ids'].append(self.f.original)
        with self.assertRaises(ValueError):
            self.collect()

    def test_note_ref_cannot_point_to_other_authority(self):
        other = self.f.base / 'other-annex.json'; self.f.write(other, self.f.annex)
        self.f.notes[0]['details']['recovery_annex_ref'] = c.ref(other)
        with self.assertRaisesRegex(ValueError, 'different authority'):
            self.collect()

    def test_duplicate_or_superseded_admin_note_is_not_silently_selected(self):
        duplicate = copy.deepcopy(self.f.notes[0]); duplicate['id'] = 'duplicate'
        self.f.notes.append(duplicate)
        with self.assertRaisesRegex(ValueError, 'unique'):
            self.collect()
        self.f.notes.pop(); self.f.notes.append({'id': 'correction', 'supersedes_note_id': 'canonical-admin-note'})
        with self.assertRaisesRegex(ValueError, 'superseded'):
            self.collect()

    def test_admin_and_canonical_result_or_terminal_conflict(self):
        self.f.records.append({'id': 'fake', 'run_id': self.f.admin})
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            self.collect()
        self.f.records.pop(); self.f.write(self.f.root / 'attempts' / self.f.admin / 'terminal.json', {})
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            self.collect()

    def test_corrupt_normal_terminal_cannot_fall_back_to_admin(self):
        path = self.f.root / 'attempts' / self.f.original / 'terminal.json'
        terminal = c.read(path); terminal['result']['outcome'] = 'unknown'; self.f.write(path, terminal)
        with self.assertRaises(ValueError):
            self.collect()

    def test_missing_retained_terminal_is_not_downgraded_to_unstarted(self):
        (self.f.root / 'attempts' / self.f.original / 'terminal.json').unlink(); self.f.records.clear()
        with self.assertRaisesRegex(ValueError, 'Retained original terminal'):
            self.collect()

    def test_unadopted_or_missing_annex_has_no_authority(self):
        self.f.annex['status'] = 'proposal'; self.f.sync_authority()
        with self.assertRaisesRegex(ValueError, 'not adopted'):
            self.collect()
        with self.assertRaisesRegex(ValueError, 'not authorized'):
            c.collect(self.f.root, self.f.records, notes=self.f.notes)

    def test_complete_means_all_original_dispositions_not_only_existing_rows(self):
        with self.assertRaisesRegex(ValueError, '262 original dispositions missing'):
            self.collect(complete=True)

    def test_annex_change_during_collection_refuses_publication(self):
        count = 0
        def changing(*args, **kwargs):
            nonlocal count
            answer = self.f.fake_verify(*args, **kwargs); count += 1
            if count == 2:
                answer['source_index'] = {'changed': True}
            return answer
        with patch.object(c, 'verify_annex', side_effect=changing):
            with self.assertRaisesRegex(ValueError, 'authority changed'):
                c.collect(self.f.root, self.f.records, notes=self.f.notes, annex_path=self.f.annex_path)

    def test_original_correction_selection_is_still_exact_004(self):
        correction = copy.deepcopy(self.f.records[0]); correction.update(id='correction', supersedes_result_id=self.f.records[0]['id'], outcome='unknown')
        self.f.records.append(correction)
        expected = c.legacy.collect(self.f.root, self.f.records)['results'][0]
        actual = next(r for r in self.collect()['results'] if r['run_id'] == self.f.original)
        self.assertEqual(expected, actual); self.assertIsNone(actual['completion_time_s'])

    def test_original_statistics_apply_whole_block_exclusion_to_projection(self):
        report = self.collect()
        actual = c.protocol.analyze(self.f.manifests, report['results'], bootstrap_draws=2000, analysis_seed=0)
        block = self.f.manifests[1]['paired_block_id']
        excluded = next(b for b in actual['excluded_paired_blocks'] if b['paired_block_id'] == block)
        self.assertEqual([r['run_id'] for r in excluded['triggering_results']], [self.f.admin])
        self.assertEqual(actual['time_observations'], [])


if __name__ == '__main__':
    unittest.main()
