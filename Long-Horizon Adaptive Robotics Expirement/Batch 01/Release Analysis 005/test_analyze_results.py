"""Deferred synthetic integration checks; never reads real results or draws seeds."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import analyze_results as a
from synthetic_fixtures import Fixture, c


class Analysis005Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.f = Fixture(self.temp.name)
        self.output = self.f.base / 'analysis'; self.selected = self.f.base / 'selected.json'
        self.sources = self.f.write_canonical()
        with patch.object(a.collector, 'verify_annex', side_effect=self.f.fake_verify):
            self.selection = a.collector.collect(self.f.root, self.f.records, notes=self.f.notes, annex_path=self.f.annex_path)
        self.selection.update(self.sources); self.f.write(self.selected, self.selection)

    def tearDown(self):
        self.temp.cleanup()

    def run_wrapper(self):
        with patch.object(a, 'MAP', self.f.base / 'canonical'), \
             patch.object(a.collector, 'verify_annex', side_effect=self.f.fake_verify), \
             patch.object(a.queue_authority, 'queued_job', return_value={'id': 'synthetic-analysis-job'}) as owned, \
             patch.object(a.release_runner, 'queued_job', side_effect=AssertionError('Original queue reader must not be used')), \
             patch.object(a.protocol, '_entropy', side_effect=AssertionError('Never draw seeds')):
            report = a.analyze_results(self.f.root, self.selected, self.output)
            owned.assert_called_once_with(expected_script=a.__file__)
            return report

    def failure(self):
        return c.read(self.output / 'analysis-provenance.json')

    def test_exact_original_numerical_output_and_input_lineage(self):
        expected = a.protocol.analyze(self.f.manifests, self.selection['results'], **a.SETTINGS)
        before = {p: p.read_bytes() for p in (self.selected, self.f.freeze, self.f.ready, self.f.annex_path, self.f.disposition_path)}
        report = self.run_wrapper()
        self.assertEqual(c.read(self.output / 'analysis.json'), expected)
        self.assertEqual(report, self.failure()); self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['schema_version'], a.SCHEMA)
        self.assertEqual(report['analysis_settings'], {'bootstrap_draws': 2000, 'analysis_seed': 0})
        expected_queue_authority = a.ref(a.RECOVERY / 'recovery_runner.py')
        self.assertEqual(Path(a.queue_authority.__file__).resolve(), a.RECOVERY / 'recovery_runner.py')
        self.assertEqual(report['queue_authorization_implementation'], expected_queue_authority)
        self.assertEqual(report['inputs_before']['queue_authorization_implementation'], expected_queue_authority)
        self.assertEqual(report['inputs_before'], report['inputs_after']); self.assertTrue(report['inputs_unchanged'])
        self.assertEqual(report['disposition_counts']['administrative_interruption'], 1)
        self.assertFalse(report['complete_disposition_accounting']); self.assertNotIn('complete_terminal_accounting', report)
        self.assertEqual(len(report['protected_manifest_refs']), 264)
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_admin_projection_edit_is_rejected_before_statistics(self):
        next(r for r in self.selection['results'] if r['run_id'] == self.f.admin)['outcome'] = 'success'
        self.f.write(self.selected, self.selection)
        with patch.object(a.protocol, 'analyze', side_effect=AssertionError('Must not compute')):
            with self.assertRaisesRegex(ValueError, 'cannot be reproduced'):
                self.run_wrapper()
        self.assertEqual(self.failure()['status'], 'failed')
        self.assertFalse((self.output / 'analysis.json').exists())

    def test_selected_count_or_provenance_edit_is_rejected(self):
        self.selection['counts']['administrative_interruption'] = 0
        self.f.write(self.selected, self.selection)
        with self.assertRaisesRegex(ValueError, 'cannot be reproduced: counts'):
            self.run_wrapper()

    def test_forged_normal_outcome_is_rejected_by_recollection(self):
        next(r for r in self.selection['results'] if r['run_id'] == self.f.original)['outcome'] = 'failure'
        self.f.write(self.selected, self.selection)
        with self.assertRaisesRegex(ValueError, 'cannot be reproduced: results'):
            self.run_wrapper()

    def test_other_canonical_file_cannot_supply_a_fabricated_projection(self):
        alternate = self.f.base / 'fake-notes.jsonl'
        alternate.write_bytes(Path(self.sources['canonical_notes_source']['path']).read_bytes())
        self.selection['canonical_notes_source'] = c.ref(alternate); self.f.write(self.selected, self.selection)
        with self.assertRaisesRegex(ValueError, 'actual canonical map'):
            self.run_wrapper()

    def test_original_frozen_protocol_identity_is_required(self):
        freeze = c.read(self.f.freeze); freeze['protocol_sha256'] = '0' * 64; self.f.write(self.f.freeze, freeze)
        readiness = c.read(self.f.ready); readiness['freeze_sha256'] = c.ref(self.f.freeze)['sha256']; self.f.write(self.f.ready, readiness)
        release = c.read(self.f.root / 'release.json')
        release.update(freeze_manifest=c.ref(self.f.freeze), readiness=c.ref(self.f.ready)); self.f.write(self.f.root / 'release.json', release)
        self.selection['release'] = c.ref(self.f.root / 'release.json'); self.f.write(self.selected, self.selection)
        with self.assertRaisesRegex(ValueError, 'frozen numerical protocol'):
            self.run_wrapper()

    def test_collector_implementation_must_be_exact005(self):
        self.selection['implementation'] = c.ref(c.LEGACY_PATH); self.f.write(self.selected, self.selection)
        with self.assertRaisesRegex(ValueError, 'substituted collector'):
            self.run_wrapper()

    def test_mid_analysis_input_change_cannot_publish_complete_status(self):
        original = a.protocol.analyze
        def change(*args, **kwargs):
            result = original(*args, **kwargs)
            self.selected.write_bytes(self.selected.read_bytes() + b' ')
            return result
        with patch.object(a.protocol, 'analyze', side_effect=change):
            with self.assertRaisesRegex(ValueError, 'changed during derivation'):
                self.run_wrapper()
        report = self.failure()
        self.assertEqual(report['status'], 'failed'); self.assertFalse(report['inputs_unchanged'])
        self.assertIsNotNone(report['analysis'])

    def test_missing_authority_after_analysis_is_recorded_as_missing(self):
        original = a.protocol.analyze
        def disappear(*args, **kwargs):
            result = original(*args, **kwargs); self.f.ready.unlink(); return result
        with patch.object(a.protocol, 'analyze', side_effect=disappear):
            with self.assertRaisesRegex(ValueError, 'changed during derivation'):
                self.run_wrapper()
        after = self.failure()['inputs_after']['readiness']
        self.assertIsNone(after['sha256']); self.assertIn('error', after)

    def test_queue_ownership_precedes_output_creation(self):
        with patch.object(a.queue_authority, 'queued_job', side_effect=ValueError('Not owned')):
            with self.assertRaisesRegex(ValueError, 'Not owned'):
                a.analyze_results(self.f.root, self.selected, self.output)
        self.assertFalse(self.output.exists())

    def test_output_is_fresh_and_cannot_overwrite_evidence(self):
        with patch.object(a.queue_authority, 'queued_job', return_value={'id': 'synthetic'}):
            with self.assertRaisesRegex(ValueError, 'fresh'):
                a.analyze_results(self.f.root, self.selected, self.f.root / 'attempts' / 'new-output')
            self.output.mkdir()
            with self.assertRaisesRegex(ValueError, 'fresh'):
                a.analyze_results(self.f.root, self.selected, self.output)
        self.assertEqual(list(self.output.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
