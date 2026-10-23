"""Synthetic QA contracts for diagnostic-only evidence links; no report build."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import qualification_qa as qa
import qualification_report as report
import test_qualification_report as fixtures


class FailedQueueQaContracts(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.CompanionIntegrity('test_failed_queue_is_metadata_only_and_never_opens_attempt_outputs')
        self.f.setUp()
        self.addCleanup(self.f.tearDown)
        self.f.failed_queue_fixture()
        self.row = report.qualification_row(self.f.row, self.f.output)

    def test_authenticates_only_three_metadata_files_and_no_attempt_output(self):
        self.f.assessment_path.unlink()
        original = Path.read_bytes
        opened = []
        def tracked(path):
            opened.append(path.resolve())
            return original(path)
        with patch.object(Path, 'read_bytes', tracked):
            self.assertEqual(qa.failed_queue_guard(self.row, self.f.output), [])
        self.assertEqual(set(opened), {Path(a['path']).resolve() for a in self.f.row['artifacts']})

    def test_diagnostic_json_is_hash_checked_without_parsing(self):
        path = self.f.qual / 'failed-smoke-analysis.json'
        path.write_bytes(b'Not JSON; linked for diagnostic inspection only')
        self.f.row['diagnostic_analyses'] = [self.f.artifact(path, 'Separate diagnostic')]
        self.row = report.qualification_row(self.f.row, self.f.output)
        self.assertEqual(qa.failed_queue_guard(self.row, self.f.output), [report.href(path, self.f.output)])
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'document changed'):
            qa.failed_queue_guard(self.row, self.f.output)

    def test_no_assessment_timing_canary_calls_scoring_or_derived_values_allowed(self):
        mutations = [('timing', {}), ('supervisory_timing', {}), ('protected_io', {}),
                     ('native_reference', {}), ('recorder_feasibility', {}), ('pilot_admission', {}),
                     ('assessment_schema', 'an-assessment'), ('model_calls', 2), ('validity', 'valid'),
                     ('task_outcome', 'success'), ('scorable', True), ('checks', {'all_canaries': True}),
                     ('declared_details', {'maximum_lag_s': .01}), ('analyses', [{'content': {'passed': True}}])]
        for key, value in mutations:
            with self.subTest(key=key):
                row = copy.deepcopy(self.row)
                row[key] = value
                with self.assertRaisesRegex(ValueError, 'assessment, measurement or outcome'):
                    qa.failed_queue_guard(row, self.f.output)
        row = copy.deepcopy(self.row)
        row['queue_failure']['canary_passed'] = True
        with self.assertRaises(ValueError):
            qa.failed_queue_guard(row, self.f.output)

    def test_status_boolean_exit_missing_interval_or_wrong_receipt_rejected(self):
        for key, value in [('status', 'passed'), ('queue_state', 'succeeded'), ('queue_exit_status', True),
                           ('queue_exit_status', 0), ('queue_exit_status', 2), ('started_at', None),
                           ('ended_at', '2025-01-01T00:00:00Z'), ('job_id', 'different')]:
            with self.subTest(key=key, value=value):
                row = copy.deepcopy(self.row)
                row[key] = value
                with self.assertRaises(ValueError):
                    qa.failed_queue_guard(row, self.f.output)

    def test_manifest_dispatch_revision_and_actual_receipt_cannot_be_substituted(self):
        official = self.f.row['artifacts'][0]
        value = json.loads(Path(official['path']).read_bytes())
        value['argv'][3] = str(self.f.qual / 'other-manifest.json')
        Path(official['path']).write_text(json.dumps(value))
        digest = report.sha(Path(official['path']).read_bytes())
        self.row['links'][0]['sha256'] = digest
        self.row['queue_failure']['official_queue_sha256'] = digest
        with self.assertRaisesRegex(ValueError, 'correspondence differs'):
            qa.failed_queue_guard(self.row, self.f.output)

    def test_diagnostics_cannot_embed_content_or_link_raw_assessment(self):
        path = self.f.qual / 'failed-smoke-diagnosis.md'
        path.write_text('Diagnosis')
        self.f.row['diagnostic_analyses'] = [self.f.artifact(path, 'Separate diagnostic')]
        self.row = report.qualification_row(self.f.row, self.f.output)
        for change in ({'content': {'passed': True}}, {'href': report.href(self.f.assessment_path, self.f.output)},
                       {'basis': 'assessment'}, {'href': 'https://example.com/fake-analysis.json'}):
            row = copy.deepcopy(self.row)
            row['queue_failure']['diagnostic_links'][0].update(change)
            with self.assertRaisesRegex(ValueError, 'hash-only links'):
                qa.failed_queue_guard(row, self.f.output)

    def test_closeout_accepts_ongoing_or_blocked_engineering_from_latest_queue_only(self):
        contract = {'schema': 'campaign002-qualification-closeout-status-1',
                    'state': 'qualification_in_progress', 'basis_run_id': self.row['run_id'],
                    'basis_queue_sha256': self.row['queue_failure']['official_queue_sha256'], 'artifacts': []}
        closeout = report.current_status_detail(contract, [self.row], {}, {'entries': []}, self.f.campaign, self.f.output)
        for state in ('qualification_in_progress', 'qualification_failed_blocked'):
            self.assertTrue(qa.failed_queue_closeout_guard({**closeout, 'state': state}, [self.row]))
        for change in ({'state': 'qualified_campaign_in_progress'}, {'state': 'campaign_terminal'},
                       {'basis_assessment_sha256': '0' * 64}, {'basis_queue_sha256': '0' * 64},
                       {'links': []}, {'basis_kind': 'original_assessment'}):
            with self.assertRaisesRegex(ValueError, 'latest unassessed receipt'):
                qa.failed_queue_closeout_guard({**closeout, **change}, [self.row])
        later = {'run_id': 'later', 'status': 'passed'}
        with self.assertRaisesRegex(ValueError, 'latest unassessed receipt'):
            qa.failed_queue_closeout_guard(closeout, [self.row, later])

    def direct_fixture(self):
        self.f.failed_direct_diagnostic_fixture()
        with patch.multiple(report,CAMPAIGN=self.f.campaign,REPO=self.f.root):
            return report.qualification_row(self.f.row,self.f.output)

    def test_direct_diagnostic_qa_rechecks_source_anchor_without_opening_outputs(self):
        row=self.direct_fixture();original=Path.read_bytes
        allowed={Path(a['path']).resolve() for a in self.f.row['artifacts']}
        def guarded(path):
            self.assertIn(path.resolve(),allowed);return original(path)
        with patch.multiple(qa,CAMPAIGN=self.f.campaign,REPO=self.f.root),patch.object(Path,'read_bytes',guarded):
            self.assertEqual(qa.failed_queue_guard(row,self.f.output),[])

    def test_direct_diagnostic_qa_rejects_forged_dispatch_despite_rebound_queue_hash(self):
        row=self.direct_fixture();value=json.loads(self.f.queue_path.read_bytes());value['argv'][-1]=str(self.f.root/'other')
        self.f.save(self.f.queue_path,value);digest=report.sha(self.f.queue_path.read_bytes())
        row['links'][0]['sha256']=digest;row['queue_failure']['official_queue_sha256']=digest
        with patch.multiple(qa,CAMPAIGN=self.f.campaign,REPO=self.f.root),self.assertRaisesRegex(ValueError,'direct dispatch'):
            qa.failed_queue_guard(row,self.f.output)

    def test_direct_diagnostic_qa_rejects_source_anchor_and_legacy_schema_alias(self):
        row=self.direct_fixture();manifest=Path(self.f.row['artifacts'][1]['path']);value=json.loads(manifest.read_bytes())
        value['source_snapshot']['sha256']='0'*64;self.f.save(manifest,value);digest=report.sha(manifest.read_bytes())
        row['links'][1]['sha256']=digest;row['queue_failure']['manifest_sha256']=digest
        with patch.multiple(qa,CAMPAIGN=self.f.campaign,REPO=self.f.root),self.assertRaisesRegex(ValueError,'frozen anchor'):
            qa.failed_queue_guard(row,self.f.output)
        row=self.direct_fixture();row['queue_failure']['schema']='campaign002-failed-queue-diagnostic-1'
        with self.assertRaisesRegex(ValueError,'manifest dispatch'):qa.failed_queue_guard(row,self.f.output)


class OrdinaryDiagnosticQaContracts(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.CompanionIntegrity('test_successful_row_links_cross_run_diagnostics_without_pooling')
        self.f.setUp()
        self.addCleanup(self.f.tearDown)
        self.analysis, self.narrative = self.f.diagnostic_links_fixture()
        self.row = report.qualification_row(self.f.row, self.f.output)

    def verify(self, links=None):
        return qa.diagnostic_links_guard(self.row['diagnostic_links'] if links is None else links,
                                         self.f.output, self.row['links'])

    def test_cross_run_documents_are_hashed_without_interpreting_json(self):
        with patch.object(qa.json, 'loads', side_effect=AssertionError('Diagnostic content must remain unparsed')):
            self.assertEqual(self.verify(), [report.href(path, self.f.output) for path in
                                            (self.analysis, self.narrative)])

    def test_diagnostic_link_schema_cannot_embed_results_or_impersonate_assessment(self):
        for change in ({'content': {'passed': True}}, {'basis': 'assessment'}, {'label': 'Original assessment'},
                       {'href': report.href(self.f.assessment_path, self.f.output)}, {'bytes': False},
                       {'href': 'https://example.com/other-analysis.json'},
                       {'href': '//example.com/other-analysis.json'}):
            links = copy.deepcopy(self.row['diagnostic_links'])
            links[0].update(change)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'hash-only links'):
                self.verify(links)

    def test_changed_diagnostic_bytes_fail_qa(self):
        self.analysis.write_bytes(b'Changed analysis bytes')
        with self.assertRaisesRegex(ValueError, 'document changed'):
            self.verify()

    def test_duplicates_and_source_aliases_fail_qa(self):
        links = self.row['diagnostic_links']
        with self.assertRaises(ValueError):
            self.verify(links + [dict(links[0], label='Duplicate document')])
        source_links = self.row['links'] + [dict(links[0], label='Already a structured source')]
        with self.assertRaisesRegex(ValueError, 'aliases source evidence'):
            qa.diagnostic_links_guard(links, self.f.output, source_links)


if __name__ == '__main__':
    unittest.main()
