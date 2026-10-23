"""Synthetic metadata-only adversaries for the completed Native004 diagnostic."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import qualification_report as report
import qualification_qa as qa
import test_qualification_report as fixtures


class CompletedDiagnostic(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.CompanionIntegrity()
        self.f.setUp()
        self.addCleanup(self.f.tearDown)
        self.reset()

    def reset(self):
        f = self.f
        manifest, _ = f.failed_single_interrupt_fixture(version=3)
        value = json.loads(manifest.read_bytes())
        self.run = 'RCI001-C02-shutdown-diagnostic-004'
        self.revision = 'RCI001-C02-dev-092'
        self.manifest = f.campaign / 'io-repair/shutdown-diagnostic-004/manifest.json'
        self.snapshot = f.campaign.parent.parent / 'Architecture Map/releases' / self.revision / 'snapshot.json'
        def rename(value):
            return value.replace('shutdown-diagnostic-003', 'shutdown-diagnostic-004').replace('dev-091', 'dev-092').replace('diagnostic-v3', 'diagnostic-v4')
        value = {k: rename(v) if isinstance(v, str) else v for k, v in value.items()}
        declared = {(f.campaign / k).relative_to(f.root).as_posix(): dict(v)
                    for k, v in report.ORDERED_INTERRUPT_SOURCES.items()}
        value['runtime_input_files'] = list(declared)
        f.save(self.manifest, value)
        f.save(self.snapshot, {'schema': 'robot-codex-readiness-source-1', 'run_id': self.run,
            'revision': self.revision, 'manifest_sha256': report.sha(self.manifest.read_bytes()), 'sources': declared})
        f.job.update(state='succeeded', exit_status=0, argv=[rename(v) for v in f.job['argv']])
        self.row = copy.deepcopy(f.row)
        self.row.pop('queue_failure_contract')
        self.row.update(run_id=self.run, revision=self.revision, status='completed', reason='Completed, not assessed.')
        self.refresh()

    def refresh(self, bind_manifest=True):
        f = self.f
        if bind_manifest:
            value = json.loads(self.snapshot.read_bytes())
            value['manifest_sha256'] = report.sha(self.manifest.read_bytes())
            f.save(self.snapshot, value)
        f.save(f.queue_path, f.job)
        self.row['queue'] = {k: f.job[k] for k in ('id', 'state', 'exit_status', 'started_at', 'ended_at')}
        artifacts = [f.artifact(f.queue_path, 'Official queue receipt'),
                     f.artifact(self.manifest, 'Frozen attempt manifest'), f.artifact(self.snapshot, 'Frozen source snapshot')]
        self.row['artifacts'] = artifacts
        self.row['queue_completion_contract'] = {'schema': report.COMPLETED_INTERRUPT_SCHEMA,
            **{key: item['sha256'] for key, item in zip(
                ('official_queue_sha256', 'manifest_sha256', 'snapshot_sha256'), artifacts)}}

    def render(self):
        with patch.multiple(report, CAMPAIGN=self.f.campaign, REPO=self.f.root):
            return report.qualification_row(self.row, self.f.output)

    def guard(self, row):
        with patch.multiple(qa, CAMPAIGN=self.f.campaign, REPO=self.f.root):
            return qa.completed_diagnostic_guard(row, self.f.output)

    def test_only_three_metadata_files_opened_and_no_verdict_derived(self):
        allowed = {Path(a['path']).resolve() for a in self.row['artifacts']}
        original, opened = Path.read_bytes, []
        def limited(path):
            self.assertIn(path.resolve(), allowed)
            opened.append(path.resolve())
            return original(path)
        with patch.object(Path, 'read_bytes', limited):
            result = self.render()
            self.assertEqual(self.guard(result), [])
        self.assertEqual(set(opened), allowed)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['assessment_state'], 'not_assessed')
        self.assertEqual(result['validity'], 'unknown')
        self.assertIsNone(result['model_calls'])
        self.assertEqual(result['checks'], {})
        self.assertEqual(result['task_outcome'], 'unknown')
        self.assertFalse(result['scorable'])

    def test_completion_never_becomes_latest_qualifier(self):
        result = self.render()
        earlier = {'run_id': 'previous-smoke', 'status': 'failed'}
        for module in (report, qa):
            self.assertIs(module.latest_completed_qualifier([earlier, result]), earlier)

    def test_queue_active_failed_and_noninteger_zero_rejected_before_manifest(self):
        for state, exit_code in [('running', None), ('failed', 1), ('succeeded', False), ('succeeded', 0.0), ('succeeded', 1)]:
            with self.subTest(state=state, exit_code=exit_code):
                self.reset()
                self.f.job.update(state=state, exit_status=exit_code)
                self.refresh()
                original = Path.read_bytes
                def official_only(path):
                    self.assertEqual(path.resolve(), self.f.queue_path.resolve())
                    return original(path)
                with patch.object(Path, 'read_bytes', official_only), self.assertRaises(ValueError):
                    self.render()

    def test_row_promotion_and_extra_evidence_rejected(self):
        for key, value in [('status', 'passed'), ('validity', 'valid'), ('assessment_state', 'assessed'),
                           ('scorable', True), ('task_outcome', 'success'), ('model_calls', 1),
                           ('checks', {}), ('qualification_passed', True), ('details', {'timing': 1}),
                           ('queue_failure_contract', {}), ('diagnostic_contract', {}), ('run_id', 'other')]:
            with self.subTest(key=key):
                self.reset(); self.row[key] = value
                with self.assertRaises(ValueError): self.render()
        self.reset()
        self.row['artifacts'].append(self.row['artifacts'][0])
        with self.assertRaises(ValueError): self.render()

    def test_exact_dispatch_original_bounds_and_snapshot_identity_required(self):
        for kind in ('dispatch', 'bootstrap', 'cap', 'revision', 'snapshot-manifest', 'snapshot-run'):
            with self.subTest(kind=kind):
                self.reset()
                m, s = json.loads(self.manifest.read_bytes()), json.loads(self.snapshot.read_bytes())
                if kind == 'dispatch': self.f.job['argv'][4] = self.f.job['argv'][4].replace('v4', 'v3')
                if kind == 'bootstrap': m['bootstrap'] += ' More instructions.'
                if kind == 'cap': m['invocation_wall_cap_s'] = 601
                if kind == 'revision': m['framework_revision'] = 'RCI001-C02-dev-091'
                if kind == 'snapshot-manifest': s['manifest_sha256'] = '0' * 64
                if kind == 'snapshot-run': s['run_id'] = 'other'
                self.f.save(self.manifest, m); self.f.save(self.snapshot, s)
                self.refresh(bind_manifest=kind != 'snapshot-manifest')
                with self.assertRaises(ValueError): self.render()

    def test_each_frozen_dispatch_source_required_and_exact(self):
        for key in report.ORDERED_INTERRUPT_SOURCES:
            for mode in ('missing', 'changed', 'noninteger', 'undeclared'):
                with self.subTest(key=key, mode=mode):
                    self.reset()
                    name = (self.f.campaign / key).relative_to(self.f.root).as_posix()
                    m, s = json.loads(self.manifest.read_bytes()), json.loads(self.snapshot.read_bytes())
                    if mode == 'missing': del s['sources'][name]
                    if mode == 'changed': s['sources'][name]['sha256'] = '0' * 64
                    if mode == 'noninteger': s['sources'][name]['bytes'] = float(s['sources'][name]['bytes'])
                    if mode == 'undeclared': m['runtime_input_files'].remove(name)
                    self.f.save(self.manifest, m); self.f.save(self.snapshot, s); self.refresh()
                    with self.assertRaises(ValueError): self.render()

    def test_missing_completion_contract_cannot_enter_generic_success_or_failure(self):
        for status in ('completed', 'passed', 'failed'):
            self.reset(); self.row['status'] = status; self.row.pop('queue_completion_contract')
            with self.assertRaises(ValueError): self.render()

    def test_independent_qa_rejects_promotion_and_queue_contradictions(self):
        original = self.render()
        for key, value in [('status', 'passed'), ('validity', 'valid'), ('assessment_state', 'assessed'),
                           ('scorable', True), ('task_outcome', 'success'), ('model_calls', 1),
                           ('checks', {'native': True}), ('timing', {}), ('queue_state', 'failed'),
                           ('queue_exit_status', False), ('job_id', 'other'), ('run_id', 'other'),
                           ('queue_failure', {})]:
            with self.subTest(key=key):
                row = copy.deepcopy(original); row[key] = value
                with self.assertRaises(ValueError): self.guard(row)
        row = copy.deepcopy(original); row['queue_completion']['schema'] = report.SINGLE_INTERRUPT_SCHEMA
        with self.assertRaises(ValueError): self.guard(row)


if __name__ == '__main__':
    unittest.main()
