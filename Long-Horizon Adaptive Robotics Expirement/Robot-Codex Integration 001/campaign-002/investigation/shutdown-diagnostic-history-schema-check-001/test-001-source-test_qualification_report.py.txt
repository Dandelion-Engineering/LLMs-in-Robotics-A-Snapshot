"""Synthetic-only integrity tests; never reads active qualifications."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import qualification_report as report
import qualification_qa as qa


class CompanionIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='qualification-test-')
        self.root = Path(self.tmp.name)
        self.campaign = self.root / 'integration/campaign-002'
        self.campaign.mkdir(parents=True)
        self.output = self.campaign / 'investigation'
        self.output.mkdir()
        self.qual = self.campaign / 'qualification'
        self.qual.mkdir()
        self.operator = self.campaign / 'operate.py'
        self.operator.write_text("def start():\n    save(folder / 'launch-intent.json', {})\n    queue('submit')\n", encoding='utf-8')
        self.prior = self.root / 'prior/data.json'
        self.save(self.prior, {'runs': [{}] * 24, 'counts': {'all scheduled slots': {
            'valid': 6, 'successes': 6, 'invalid': 4, 'not_run': 14}}})
        self.prior.with_name('report.html').write_text('Original report', encoding='utf-8')
        self.run_id = 'RCI001-C02-host-probe-fixture'
        self.job = {'id': 'job-fixture', 'state': 'succeeded', 'exit_status': 0,
                    'started_at': '2026-01-01T00:00:00Z', 'ended_at': '2026-01-01T00:00:01Z'}
        self.queue_path = self.qual / 'fixture-queue.json'
        self.save(self.queue_path, self.job)
        self.assessment_path = self.qual / 'fixture-assessment.json'
        self.assessment = {'run_id': self.run_id, 'framework_revision': 'dev-fixture',
            'queue_job_id': self.job['id'], 'diagnostic_passed': False,
            'checks': {'full_interval_timing': False}, 'errors': {'timing': 'Retained failure'},
            'timing': None, 'bindings': {}}
        self.save(self.assessment_path, self.assessment)
        self.row = {'run_id': self.run_id, 'revision': 'dev-fixture', 'status': 'failed',
            'validity': 'invalid', 'reason': 'Original failure.', 'queue': {'id': self.job['id']},
            'artifacts': [self.artifact(self.queue_path, 'Official queue receipt'),
                          self.artifact(self.assessment_path, 'Original assessment')]}
        self.index = self.output / 'qualification-history.json'
        report.READS.clear()

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')

    def artifact(self, path, label):
        raw = path.read_bytes()
        return {'path': str(path), 'label': label, 'sha256': report.sha(raw), 'bytes': len(raw)}

    def refresh_assessment(self):
        self.save(self.assessment_path, self.assessment)
        self.row['artifacts'][1] = self.artifact(self.assessment_path, 'Original assessment')

    def diagnostic_links_fixture(self):
        self.row.update(status='passed', validity='valid', model_calls=0)
        self.assessment.update(diagnostic_passed=True, checks={'host_timing': True}, errors={})
        self.refresh_assessment()
        other = self.qual / 'separate-transport-probe'
        documents = [('transport-queue.json', 'Separate transport queue', {'id': 'other-job'}),
                     ('transport-manifest.json', 'Separate transport manifest', {'run_id': 'other-run'}),
                     ('release/snapshot.json', 'Separate transport snapshot', {'revision': 'other-revision'}),
                     ('evidence/result.json', 'Separate transport result', {'run_id': 'other-run', 'passed': True})]
        for name, label, value in documents:
            path = other / name
            self.save(path, value)
            self.row['artifacts'].append(self.artifact(path, label))
        analysis = other / 'transport-analysis.json'
        self.save(analysis, {'run_id': 'other-run', 'queue_job_id': 'other-job',
            'checks': {'transport_only_check': True}, 'timing': {'passed': True, 'maximum_lag_s': 0},
            'model_calls': 77, 'task_outcome': 'success', 'qualification_passed': True})
        narrative = other / 'transport-analysis.md'
        narrative.write_text('Separate transport run. No host timing or task outcome claim.', encoding='utf-8')
        self.row['diagnostic_analyses'] = [self.artifact(analysis, 'Separate transport analysis JSON'),
                                         self.artifact(narrative, 'Separate transport analysis narrative')]
        return analysis, narrative

    def test_successful_row_links_cross_run_diagnostics_without_pooling(self):
        self.diagnostic_links_fixture()
        baseline = copy.deepcopy(self.row)
        del baseline['diagnostic_analyses']
        expected = report.qualification_row(baseline, self.output)
        report.READS.clear()
        result = report.qualification_row(self.row, self.output)
        links = result.pop('diagnostic_links')
        self.assertEqual(result, {k: v for k, v in expected.items() if k != 'diagnostic_links'})
        self.assertEqual(len(links), 2)
        self.assertTrue(all(link['basis'] == 'diagnostic_link_only' and 'content' not in link for link in links))
        self.assertEqual(result['run_id'], self.run_id)
        self.assertEqual(result['job_id'], self.job['id'])
        self.assertEqual(result['checks'], {'host_timing': True})
        self.assertEqual(result['analyses'], [])
        self.assertIsNone(result['timing'])
        self.assertEqual(result['model_calls'], 0)
        self.assertEqual(result['task_outcome'], 'unknown')
        reads = [row for row in report.READS if row['path'] in
                 {item['path'] for item in self.row['diagnostic_analyses']}]
        self.assertEqual(len(reads), 2)
        self.assertTrue(all('hash-only link, contents not interpreted' in row['role'] for row in reads))

    def test_successful_row_diagnostic_json_is_never_parsed(self):
        analysis, _ = self.diagnostic_links_fixture()
        analysis.write_bytes(b'Not JSON; only bytes are verified and linked')
        self.row['diagnostic_analyses'][0] = self.artifact(analysis, 'Separate transport analysis JSON')
        result = report.qualification_row(self.row, self.output)
        self.assertEqual(len(result['diagnostic_links']), 2)
        self.assertEqual(result['analyses'], [])

    def test_successful_row_diagnostic_access_follows_official_queue_gate(self):
        analysis, narrative = self.diagnostic_links_fixture()
        analysis.unlink(); narrative.unlink()
        self.job.update(state='running', exit_status=None)
        self.save(self.queue_path, self.job)
        self.row['artifacts'][0] = self.artifact(self.queue_path, 'Official queue receipt')
        with self.assertRaisesRegex(ValueError, 'Official queue succeeded'):
            report.qualification_row(self.row, self.output)
        self.assertEqual([Path(row['path']) for row in report.READS], [self.queue_path])

    def test_successful_row_diagnostic_schema_aliases_and_tampering_rejected(self):
        analysis, _ = self.diagnostic_links_fixture()
        original = copy.deepcopy(self.row['diagnostic_analyses'])
        for change in ({'content': {'passed': True}}, {'bytes': True}, {'label': 'Original assessment'},
                       {'path': str(self.assessment_path)}, {'sha256': '0' * 64}):
            self.row['diagnostic_analyses'] = copy.deepcopy(original)
            self.row['diagnostic_analyses'][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                report.qualification_row(self.row, self.output)
        for invalid in (original + [original[0]], {'analysis': original[0]}):
            self.row['diagnostic_analyses'] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                report.qualification_row(self.row, self.output)
        self.row['diagnostic_analyses'] = original
        analysis.write_bytes(b'Changed after indexing')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            report.qualification_row(self.row, self.output)

    def test_cross_run_diagnostic_links_survive_synthetic_build_and_qa(self):
        self.diagnostic_links_fixture()
        self.build()
        with patch.object(qa, 'static_html', return_value={'checked': True}):
            self.assertEqual(qa.verify(self.output)['history_records'], 1)
        html = (self.output / 'qualification-report.html').read_text(encoding='utf-8')
        self.assertIn('id="diagnosticLinksPanel"', html)
        self.assertIn('These documents may describe a different run.', html)
        data = json.loads((self.output / 'qualification-data.json').read_bytes())
        self.assertEqual(len(data['history'][0]['diagnostic_links']), 2)
        self.assertEqual(data['history'][0]['analyses'], [])

    def timing_fixture(self):
        samples = self.qual / 'timing-samples.bin'
        samples.write_bytes(b'Exact retained fixture bytes')
        self.metadata = {'schema': 'rci-prospective-timing-2', 'sample_file': samples.name,
            'sha256': report.sha(samples.read_bytes()), 'byte_count': samples.stat().st_size,
            'sample_count': 1, 'loop_origin': {'clock_name': 'perf_counter'},
            'phases': {'adapter.bridge_observe': {'count': 1, 'wall_total_s': .125839,
                'cpu_total_s': .015625, 'wall_max_s': .125839}}, 'phase_accounting': 'Inclusive',
            'slow_phases_by_name': {'adapter.bridge_observe': [{'wall_duration_s': .125839}]}}
        self.metadata_path = self.qual / 'timing-v2.json'
        self.save(self.metadata_path, self.metadata)
        self.host_path = self.qual / 'result.json'
        self.host = {'run_id': self.run_id, 'terminal': 'infrastructure_error', 'timing_v2': {
            'metadata_file': self.metadata_path.name, 'metadata_sha256': report.sha(self.metadata_path.read_bytes()),
            'sample_file': samples.name, 'sample_sha256': self.metadata['sha256'],
            'sample_count': 1, 'loop_origin': self.metadata['loop_origin']}}
        self.save(self.host_path, self.host)
        self.assessment['bindings']['host_result'] = self.artifact(self.host_path, 'Host result')
        self.refresh_assessment()

    def build(self):
        value = {'schema': 'campaign002-qualification-history-1', 'attempts': [self.row]}
        if hasattr(self, 'closeout'):
            value['current_status'] = self.closeout
        self.save(self.index, value)
        return report.build(self.index, self.output, campaign=self.campaign, previous=self.prior)

    def supervisory_fixture(self):
        self.timing_fixture()
        folder=self.host_path.parent/'supervisory-diagnostics';folder.mkdir()
        samples=folder/'timing-samples.bin';samples.write_bytes(b'Independent supervisory fixture bytes')
        metadata=folder/'timing-v2.json'
        value={'schema':'rci-prospective-timing-2','sample_file':samples.name,
            'sha256':report.sha(samples.read_bytes()),'byte_count':samples.stat().st_size,
            'loop_origin':self.metadata['loop_origin'],
            'phases':{'journal.event.protected.fsync':{'count':2,'wall_total_s':.08,'wall_max_s':.06}},
            'phase_accounting':'Inclusive overlapping diagnostic spans'}
        self.save(metadata,value)
        self.row['artifacts'].extend([self.artifact(metadata,'Supervisory metadata'),self.artifact(samples,'Supervisory samples')])
        return metadata,samples,value

    def protected_io_fixture(self,passed=True):
        self.run_id='RCI001-C02-protected-io-fixture';self.row.update(run_id=self.run_id,status='passed' if passed else 'failed')
        self.assessment={'schema':'rci-c02-protected-io-assessment-1','run_id':self.run_id,
            'framework_revision':self.row['revision'],'passed':passed,'qualification_passed':False,
            'scorable':False,'task_outcome':'unknown','parity':passed,'durability_order_preserved':passed,
            'duration_s':120.,'full_operation_rows':1000,'distributions':{'journal.event.protected.fsync':{
                'count':1200,'p50_s':.001,'p99_s':.04,'maximum_s':.06}},
            'official_queue':{'path':str(self.queue_path),'sha256':self.row['artifacts'][0]['sha256']},
            'interpretation':'Diagnostic integrity only; no qualification or task score.'}
        self.refresh_assessment()

    def test_supervisory_context_has_its_own_bound_metadata_samples_and_no_verdict(self):
        metadata,samples,_=self.supervisory_fixture();self.build()
        data=json.loads((self.output/'qualification-data.json').read_text());row=data['history'][0]
        self.assertIn('adapter.bridge_observe',row['timing']['phases'])
        self.assertNotIn('journal.event.protected.fsync',row['timing']['phases'])
        self.assertIn('journal.event.protected.fsync',row['supervisory_timing']['phases'])
        self.assertIsNone(row['supervisory_timing']['strict_passed'])
        self.assertFalse(row['supervisory_timing']['strict_verification_available'])
        self.assertTrue(any('Separate supervisory' in link['label'] for link in row['links']))
        proof=json.loads((self.output/'qualification-provenance.json').read_text())
        self.assertTrue(any(item['path']==str(samples.resolve()) for item in proof['inputs']))
        qa.verify(self.output)

    def test_supervisory_context_rejects_tampered_samples_and_different_origin(self):
        metadata,samples,value=self.supervisory_fixture()
        samples.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):self.build()
        samples.write_bytes(b'Independent supervisory fixture bytes')
        value['loop_origin']={'clock_name':'different'};self.save(metadata,value)
        self.row['artifacts'][-2]=self.artifact(metadata,'Supervisory metadata')
        with self.assertRaisesRegex(ValueError,'clock origin'):self.build()

    def test_unindexed_supervisory_measurements_are_never_consumed(self):
        self.timing_fixture();folder=self.host_path.parent/'supervisory-diagnostics';folder.mkdir()
        (folder/'timing-v2.json').write_text('invalid unbound JSON')
        self.build();row=json.loads((self.output/'qualification-data.json').read_text())['history'][0]
        self.assertIsNone(row['supervisory_timing'])
        self.assertFalse(any('supervisory-diagnostics' in item['path'] for item in report.READS))

    def test_protected_io_pass_is_integrity_only_with_exact_official_receipt(self):
        self.protected_io_fixture();self.build()
        row=json.loads((self.output/'qualification-data.json').read_text())['history'][0]
        self.assertEqual(row['status'],'passed');self.assertIsNone(row['timing'])
        self.assertTrue(row['protected_io']['diagnostic_integrity_passed'])
        self.assertFalse(row['protected_io']['qualification_passed']);self.assertFalse(row['scorable'])
        self.assertEqual(row['protected_io']['queue_job_id'],self.job['id'])
        self.assertNotIn('queue_job_id',self.assessment)  # Derived identity leaves original untouched.
        self.assertEqual(row['protected_io']['distributions'],self.assessment['distributions'])
        qa.verify(self.output)

    def test_protected_io_failure_cannot_be_promoted_to_pass(self):
        self.protected_io_fixture(False);self.build();self.row['status']='passed'
        with self.assertRaisesRegex(ValueError,'verdict'):self.build()

    def test_protected_io_requires_bound_receipt_even_with_matching_job_id(self):
        self.protected_io_fixture();self.assessment['queue_job_id']=self.job['id']
        del self.assessment['official_queue'];self.refresh_assessment()
        with self.assertRaisesRegex(ValueError,'exact bound official'):self.build()

    def test_protected_io_rejects_conflicting_receipt_path_hash_or_job(self):
        for field,value in [('path',str(self.root/'different-receipt.json')),('sha256','0'*64),('queue_job_id','wrong-job')]:
            with self.subTest(field=field):
                self.protected_io_fixture()
                if field=='queue_job_id':self.assessment[field]=value
                else:self.assessment['official_queue'][field]=value
                self.refresh_assessment()
                with self.assertRaisesRegex(ValueError,'exact bound official'):self.build()

    def test_protected_io_rejects_qualification_promotion_and_nonboolean_integrity(self):
        for field,value in [('qualification_passed',True),('passed',1),('scorable',True),('diagnostic_passed',True)]:
            with self.subTest(field=field):
                self.protected_io_fixture();self.assessment[field]=value;self.refresh_assessment()
                with self.assertRaisesRegex(ValueError,'separate from qualification'):self.build()

    def feasibility_fixture(self, passed=True):
        self.run_id = 'RCI001-C02-recorder-feasibility-002'
        self.row.update(run_id=self.run_id, revision='RCI001-C02-dev-011', status='passed' if passed else 'failed')
        latency = {'count': 600, 'minimum_s': .001, 'median_s': .002, 'p95_s': .004,
                   'p99_s': .006, 'maximum_s': .010, 'total_s': 1.8, 'quantile_method': 'lower order statistic'}
        rounds = [{'ordinal': i, 'mode': mode, 'passed': True, 'checks': {}, 'errors': {},
                   'timing': {'sample_count': 1000, 'latency': {name: dict(latency) for name in ('image','commit','execute')}}}
                  for i,mode in enumerate(report.FEASIBILITY_ORDER)]
        recovery = [{'mode': mode, 'stage': stage, 'passed': True,
                     'committed_document_names': ['pending','stable'] if stage == 'after_commit' else ['stable']}
                    for mode in ('DELETE','PERSIST') for stage in ('before_commit','after_commit')]
        if not passed:
            rounds[3].update(passed=False, timing=None, errors={'completion':'Fixed round was not run before the wall cap'})
            recovery[2].update(passed=False, error='Recovery fixture missing or unrun')
        self.assessment = {'schema':'rci-recorder-journal-feasibility-assessment-1', 'run_id':self.run_id,
            'framework_revision':self.row['revision'], 'queue_job_id':self.job['id'],
            'mechanical_feasibility_passed':passed, 'checks':{'all_rounds_mechanically_valid':passed},
            'errors':{}, 'rounds':rounds, 'recovery_checks':recovery, 'bindings':{},
            'model_calls':0, 'scorable':False, 'task_outcome':'unknown', 'production_adopted':False,
            'scope':'Synthetic mechanical feasibility; no physics, model, task score or production adoption.'}
        self.refresh_assessment()

    def preflight_fixture(self):
        self.run_id = 'RCI001-C02-recorder-feasibility-001'
        revision = 'RCI001-C02-dev-010'
        record_path = self.qual / self.run_id / 'preflight-failure.json'
        self.save(record_path, {'run_id':self.run_id, 'framework_revision':revision,
            'execution_status':'not_run','queue_submitted':False,'scorable':False,'task_outcome':'unknown',
            'reason':'Prelaunch source inventory incomplete; no job submitted.'})
        manifest_path = self.qual / 'recorder-feasibility-001-manifest.json'
        self.save(manifest_path, {'run_id':self.run_id,'framework_revision':revision})
        snapshot_path = self.root / 'releases/dev010/snapshot.json'
        self.save(snapshot_path, {'run_id':self.run_id,'revision':revision,
                                  'manifest_sha256':report.sha(manifest_path.read_bytes())})
        artifacts = [self.artifact(record_path,'Preflight not-run disposition'),
                     self.artifact(manifest_path,'Frozen attempt manifest'),
                     self.artifact(snapshot_path,'Frozen source snapshot')]
        self.row = {'run_id':self.run_id,'revision':revision,'status':'not_run','validity':'unknown',
            'assessment_state':'not_assessed','scorable':False,'task_outcome':'unknown','model_calls':0,'queue':None,
            'preflight_contract':{'schema':'campaign002-preflight-not-run-1','record_sha256':artifacts[0]['sha256'],
                'manifest_sha256':artifacts[1]['sha256'],'snapshot_sha256':artifacts[2]['sha256'],
                'unlaunched_evidence_path':str(self.campaign.parent/'local-evidence/campaign002/qualification'/self.run_id)},
            'artifacts':artifacts}
        return record_path, manifest_path, snapshot_path

    def failed_queue_fixture(self):
        manifest = self.qual / 'failed-smoke-manifest.json'
        self.save(manifest, {'run_id': self.run_id, 'framework_revision': 'dev-fixture'})
        snapshot = self.root / 'releases/dev-fixture/snapshot.json'
        # A shared revision anchor may name another qualifier's manifest/run.
        self.save(snapshot, {'run_id': 'native-anchor', 'revision': 'dev-fixture', 'manifest_sha256': '0' * 64})
        self.job.update(state='failed', exit_status=1, cwd=str(self.campaign),
                        argv=['python', 'launcher.py', '--manifest', str(manifest), '--mode', 'smoke'])
        self.save(self.queue_path, self.job)
        artifacts = [self.artifact(self.queue_path, 'Official queue receipt'),
                     self.artifact(manifest, 'Frozen attempt manifest'),
                     self.artifact(snapshot, 'Frozen source snapshot')]
        self.row.update(status='failed', validity='unknown', assessment_state='not_assessed',
                        scorable=False, task_outcome='unknown', model_calls=None, details={}, artifacts=artifacts,
                        queue_failure_contract={'schema': 'campaign002-failed-queue-diagnostic-1',
                            'official_queue_sha256': artifacts[0]['sha256'], 'manifest_sha256': artifacts[1]['sha256'],
                            'snapshot_sha256': artifacts[2]['sha256']}, diagnostic_analyses=[])
        return manifest, snapshot

    def failed_direct_diagnostic_fixture(self, family='raw-preflight'):
        self.failed_queue_fixture()
        self.run_id='RCI001-C02-'+family+'-002';self.row['run_id']=self.run_id
        script=self.campaign/'harness'/('raw_event_preflight_v2.py' if family=='raw-preflight' else 'codehost_transport_probe_v3.py')
        manifest=self.campaign/'io-repair'/self.run_id.removeprefix('RCI001-C02-')/'manifest.json'
        snapshot=self.root/'releases/dev-fixture/snapshot.json'
        self.save(snapshot,{'revision':'dev-fixture','sources':{script.relative_to(self.root).as_posix():{'sha256':'a'*64,'bytes':100}}})
        self.save(manifest,{'run_id':self.run_id,'framework_revision':'dev-fixture','model_calls':0,'physical_simulation':False,
            'source_snapshot':{'path':str(snapshot),'sha256':report.sha(snapshot.read_bytes())}})
        executable=str(self.root/'venv/Scripts/python.exe')
        self.job.update(cwd=str(self.root),resolved_executable=executable,argv=[executable,'-X','utf8','-B',str(script),
            '--run-id',self.run_id,'--framework-revision','dev-fixture','--snapshot',str(snapshot),'--output',str(manifest.parent/'evidence')])
        self.save(self.queue_path,self.job)
        artifacts=[self.artifact(self.queue_path,'Official queue receipt'),self.artifact(manifest,'Frozen attempt manifest'),
                   self.artifact(snapshot,'Frozen source snapshot')]
        self.row.update(artifacts=artifacts,queue_failure_contract={'schema':'campaign002-failed-diagnostic-queue-1',
            **{key:artifacts[i]['sha256'] for i,key in enumerate(('official_queue_sha256','manifest_sha256','snapshot_sha256'))}})
        return manifest,snapshot

    def failed_single_interrupt_fixture(self):
        self.failed_queue_fixture()
        self.run_id = 'RCI001-C02-shutdown-diagnostic-001'
        revision = 'RCI001-C02-dev-055'
        self.row.update(run_id=self.run_id, revision=revision)
        manifest = self.campaign / 'io-repair/shutdown-diagnostic-001/manifest.json'
        snapshot = self.campaign.parent.parent / 'Architecture Map/releases' / revision / 'snapshot.json'
        workspace = Path(report.os.environ['LOCALAPPDATA']) / 'RobotCodex/Campaign002/diagnostic' / self.run_id
        declared = [(self.campaign / name).relative_to(self.root).as_posix()
                    for name in report.SINGLE_INTERRUPT_SOURCES]
        self.save(manifest, {
            'schema': 'robot-codex-development-manifest-1.0', 'stage': 'development-only',
            'run_id': self.run_id, 'framework_revision': revision, 'family': 'misplaced-stock', 'mode': 'serve',
            'qualification_stage': 'campaign002-single-interrupt-diagnostic',
            'outer_campaign_protocol': 'RCI001-Campaign002-single-interrupt-diagnostic-v1',
            'model': 'gpt-6-astra', 'effort': 'max', 'bootstrap': 'Follow the instructions in RobotAgentPrompt.md.',
            'seed': 173, 'noise_seed': 24101, 'sim_cap_s': 1500, 'wall_cap_s': 1800,
            'storage_cap_bytes': 536870912, 'physics_dt_s': 0.002, 'model_turns_max': 1,
            'invocation_wall_cap_s': 600, 'action_request_budget': 20, 'observation_request_budget': 50,
            'interruption_trigger': 'first admitted smoke-open-001 gripper open action; revoke authority then abort client',
            'runtime_workspace': str(workspace), 'runtime_input_files': declared})
        self.save(snapshot, {'schema': 'robot-codex-readiness-source-1', 'run_id': self.run_id,
            'revision': revision, 'manifest_sha256': report.sha(manifest.read_bytes()),
            'sources': {name: dict(identity) for name, identity in zip(declared, report.SINGLE_INTERRUPT_SOURCES.values())}})
        script = self.campaign / 'io-repair/single-interrupt-diagnostic/run.py'
        evidence = self.campaign.parent / 'local-evidence/campaign002/io-repair' / self.run_id
        executable = str(self.root / 'venv/Scripts/python.exe')
        self.job.update(cwd=str(self.root), resolved_executable=executable,
            argv=[executable, '-X', 'utf8', '-B', str(script), '--manifest', str(manifest),
                  '--snapshot', str(snapshot), '--evidence', str(evidence / 'orchestrator'),
                  '--host-evidence', str(evidence / 'host'), '--workspace', str(workspace)])
        self.save(self.queue_path, self.job)
        artifacts = [self.artifact(self.queue_path, 'Official queue receipt'),
                     self.artifact(manifest, 'Frozen attempt manifest'), self.artifact(snapshot, 'Frozen source snapshot')]
        self.row.update(artifacts=artifacts, queue_failure_contract={'schema': report.SINGLE_INTERRUPT_SCHEMA,
            **{key: artifacts[n]['sha256'] for n, key in enumerate(
                ('official_queue_sha256', 'manifest_sha256', 'snapshot_sha256'))}})
        return manifest, snapshot

    def refresh_single_interrupt_bindings(self, *, bind_manifest=True):
        manifest, snapshot = [Path(a['path']) for a in self.row['artifacts'][1:]]
        if bind_manifest:
            value = json.loads(snapshot.read_bytes())
            value['manifest_sha256'] = report.sha(manifest.read_bytes())
            self.save(snapshot, value)
        for n, key in enumerate(('official_queue_sha256', 'manifest_sha256', 'snapshot_sha256')):
            item = self.row['artifacts'][n]
            self.row['artifacts'][n] = self.artifact(Path(item['path']), item['label'])
            self.row['queue_failure_contract'][key] = self.row['artifacts'][n]['sha256']

    def test_single_interrupt_failure_is_metadata_only_and_never_reads_outputs(self):
        self.failed_single_interrupt_fixture()
        allowed = {Path(a['path']).resolve() for a in self.row['artifacts']}
        original = Path.read_bytes
        def guarded(path):
            self.assertIn(path.resolve(), allowed)
            return original(path)
        with patch.multiple(report, CAMPAIGN=self.campaign, REPO=self.root), \
             patch.multiple(qa, CAMPAIGN=self.campaign, REPO=self.root), patch.object(Path, 'read_bytes', guarded):
            row = report.qualification_row(self.row, self.output)
            self.assertEqual(qa.failed_queue_guard(row, self.output), [])
        self.assertIsNone(row['model_calls'])
        self.assertIsNone(row['assessment_schema'])
        self.assertEqual(row['checks'], {})
        self.assertEqual(row['task_outcome'], 'unknown')
        self.assertFalse(row['scorable'])
        self.assertEqual(len(row['links']), 3)

    def test_single_interrupt_failure_rejects_changed_dispatch_paths(self):
        for slot in (0, 4, 6, 8, 10, 12, 14):
            with self.subTest(argv_slot=slot):
                self.failed_single_interrupt_fixture()
                self.job['argv'][slot] = str(self.root / 'other')
                self.save(self.queue_path, self.job); self.refresh_single_interrupt_bindings()
                with patch.multiple(report, CAMPAIGN=self.campaign, REPO=self.root), self.assertRaises(ValueError):
                    report.qualification_row(self.row, self.output)

    def test_single_interrupt_failure_rejects_manifest_scope_and_cap_mutations(self):
        mutations = [('schema', 'other'), ('qualification_stage', 'campaign002-smoke-qualification'),
                     ('run_id', 'RCI001-C02-shutdown-diagnostic-002'), ('framework_revision', 'RCI001-C02-dev-056'),
                     ('outer_campaign_protocol', 'other'), ('model', 'other'), ('model_turns_max', 2),
                     ('model_turns_max', True), ('invocation_wall_cap_s', 601), ('wall_cap_s', 1801),
                     ('sim_cap_s', 1501), ('storage_cap_bytes', 536870913), ('action_request_budget', 21),
                     ('observation_request_budget', 51), ('noise_seed', 24102), ('bootstrap', 'different')]
        for key, value in mutations:
            with self.subTest(field=key, value=value):
                manifest, _ = self.failed_single_interrupt_fixture()
                data = json.loads(manifest.read_bytes()); data[key] = value; self.save(manifest, data)
                self.refresh_single_interrupt_bindings()
                with patch.multiple(report, CAMPAIGN=self.campaign, REPO=self.root), self.assertRaises(ValueError):
                    report.qualification_row(self.row, self.output)

    def test_single_interrupt_failure_rejects_source_method_snapshot_or_schema_alias(self):
        for change in ('wrapper', 'method', 'missing-input', 'snapshot-manifest', 'snapshot-run',
                       'source-byte-type', 'legacy-schema', 'direct-schema', 'wrong-row-run'):
            with self.subTest(change=change):
                manifest, snapshot = self.failed_single_interrupt_fixture()
                data = json.loads(snapshot.read_bytes())
                if change in ('wrapper', 'method', 'source-byte-type'):
                    relative = 'io-repair/SHUTDOWN_REJECTION_DIAGNOSTIC_V1.md' if change == 'method' else 'io-repair/single-interrupt-diagnostic/run.py'
                    key = (self.campaign / relative).relative_to(self.root).as_posix()
                    if change == 'source-byte-type': data['sources'][key]['bytes'] = float(data['sources'][key]['bytes'])
                    else: data['sources'][key]['sha256'] = '0' * 64
                elif change == 'snapshot-manifest': data['manifest_sha256'] = '0' * 64
                elif change == 'snapshot-run': data['run_id'] = 'other'
                elif change == 'missing-input':
                    m = json.loads(manifest.read_bytes()); m['runtime_input_files'].pop(); self.save(manifest, m)
                elif change == 'wrong-row-run': self.row['run_id'] = 'RCI001-C02-shutdown-diagnostic-002'
                else: self.row['queue_failure_contract']['schema'] = ('campaign002-failed-queue-diagnostic-1'
                           if change == 'legacy-schema' else 'campaign002-failed-diagnostic-queue-1')
                self.save(snapshot, data); self.refresh_single_interrupt_bindings(bind_manifest=change != 'snapshot-manifest')
                with patch.multiple(report, CAMPAIGN=self.campaign, REPO=self.root), self.assertRaises(ValueError):
                    report.qualification_row(self.row, self.output)

    def host_prerequisite_fixture(self):
        self.run_id='RCI001-C02-host-probe-013'
        self.assessment_path=self.qual/'host-probe-013-assessment.json'
        manifest=self.qual/'host-probe-013-manifest.json';snapshot=self.root/'releases/dev-fixture/snapshot.json'
        script=self.qual/'host_probe.py'
        self.save(manifest,{'run_id':self.run_id,'framework_revision':'dev-fixture','mode':'serve','model_turns_max':0,
                            'qualification_stage':'campaign002-host-probe-qualification'})
        self.save(snapshot,{'revision':'dev-fixture','sources':{script.relative_to(self.root).as_posix():{'sha256':'a'*64,'bytes':100}}})
        executable=str(self.root/'venv/Scripts/python.exe')
        self.job.update(cwd=str(self.root),resolved_executable=executable,argv=[executable,'-X','utf8','-B',str(script),'run',
            '--manifest',str(manifest),'--output',str(self.campaign.parent/'local-evidence/campaign002/qualification'/self.run_id)])
        self.save(self.queue_path,self.job)
        self.assessment={'schema':'campaign002-host-probe-assessment-1','run_id':self.run_id,'framework_revision':'dev-fixture',
            'queue_job_id':self.job['id'],'diagnostic_passed':True,'model_calls':0,'scorable':False,'task_outcome':'unknown','errors':{},
            'checks':{k:True for k in ('host_exit_zero','queue_encloses_host','exact_manifest','no_model_or_reference_recovery',
                     'host_completed','declared_interval_completed','free_reserve_preserved','strict_fresh_timing')},
            'bindings':{k:{'path':str(p),'sha256':report.sha(p.read_bytes())} for k,p in
                        (('queue',self.queue_path),('manifest',manifest),('snapshot',snapshot))}}
        self.save(self.assessment_path,self.assessment)
        items=[self.artifact(self.queue_path,'Official queue receipt'),self.artifact(manifest,'Frozen host prerequisite manifest'),
               self.artifact(snapshot,'Frozen source snapshot'),self.artifact(self.assessment_path,'Original host diagnostic assessment')]
        self.row={'run_id':self.run_id,'revision':'dev-fixture','status':'passed','validity':'diagnostic_passed','scorable':False,
            'task_outcome':'unknown','model_calls':0,'queue':{'id':self.job['id']},'artifacts':items,'attempt_kind':'host_prerequisite_diagnostic',
            'host_prerequisite_contract':{'schema':'campaign002-host-prerequisite-history-1',
                **{k:items[i]['sha256'] for i,k in enumerate(('official_queue_sha256','manifest_sha256','snapshot_sha256','assessment_sha256'))}}}
        return manifest,snapshot

    def test_explicit_host_prerequisite_preserves_failed_basis_and_legacy_host_behavior(self):
        self.host_prerequisite_fixture()
        with patch.multiple(report,CAMPAIGN=self.campaign,REPO=self.root),patch.multiple(qa,CAMPAIGN=self.campaign,REPO=self.root):
            row=report.qualification_row(self.row,self.output);qa.host_prerequisite_guard(row,self.output)
        failed={'run_id':'failed','status':'failed','queue_failure':{'official_queue_sha256':'b'*64,'official_queue_href':'receipt.json'}}
        self.assertIs(report.latest_completed_qualifier([failed,row]),failed)
        self.assertIs(qa.latest_completed_qualifier([failed,row]),failed)
        closeout={'schema':'campaign002-qualification-closeout-status-1','state':'qualification_in_progress',
                  'basis_run_id':'failed','basis_queue_sha256':'b'*64,'artifacts':[]}
        report.current_status_detail(closeout,[failed,row],{}, {'entries':[]},self.campaign,self.output)
        del self.row['host_prerequisite_contract'];del self.row['attempt_kind']
        legacy=report.qualification_row(self.row,self.output)
        self.assertNotIn('host_prerequisite',legacy);self.assertIs(report.latest_completed_qualifier([failed,legacy]),legacy)

    def test_host_prerequisite_rejects_marker_without_contract_and_nonzero_calls(self):
        self.host_prerequisite_fixture();del self.row['host_prerequisite_contract']
        with self.assertRaises(ValueError):report.qualification_row(self.row,self.output)
        self.host_prerequisite_fixture();self.row['model_calls']=1
        with self.assertRaises(ValueError):report.qualification_row(self.row,self.output)

    def test_host_prerequisite_requires_exact_eight_original_true_checks(self):
        for change in (lambda a:a['checks'].pop('strict_fresh_timing'),lambda a:a['checks'].update(strict_fresh_timing=1),
                       lambda a:a['checks'].update(extra=True),lambda a:a.update(model_calls=False)):
            self.host_prerequisite_fixture();change(self.assessment);self.save(self.assessment_path,self.assessment)
            item=self.artifact(self.assessment_path,'Original host diagnostic assessment');self.row['artifacts'][3]=item
            self.row['host_prerequisite_contract']['assessment_sha256']=item['sha256']
            with self.assertRaises(ValueError):report.qualification_row(self.row,self.output)

    def test_host_prerequisite_rejects_dispatch_change_with_rebound_metadata(self):
        self.host_prerequisite_fixture();self.job['argv'][-1]=str(self.root/'other')
        self.save(self.queue_path,self.job);item=self.artifact(self.queue_path,'Official queue receipt')
        self.row['artifacts'][0]=item;self.row['host_prerequisite_contract']['official_queue_sha256']=item['sha256']
        self.assessment['bindings']['queue']={k:item[k] for k in ('path','sha256')};self.save(self.assessment_path,self.assessment)
        item=self.artifact(self.assessment_path,'Original host diagnostic assessment');self.row['artifacts'][3]=item
        self.row['host_prerequisite_contract']['assessment_sha256']=item['sha256']
        with patch.multiple(report,CAMPAIGN=self.campaign,REPO=self.root),self.assertRaisesRegex(ValueError,'exact command'):
            report.qualification_row(self.row,self.output)

    def test_host_prerequisite_qa_rejects_forged_classification_and_assessment_projection(self):
        self.host_prerequisite_fixture()
        with patch.multiple(report,CAMPAIGN=self.campaign,REPO=self.root):row=report.qualification_row(self.row,self.output)
        for key,value in (('model_calls',False),('assessment_schema','wrong'),('checks',{}),('attempt_kind','other')):
            value_row=copy.deepcopy(row);value_row[key]=value
            with patch.multiple(qa,CAMPAIGN=self.campaign,REPO=self.root),self.assertRaises(ValueError):qa.host_prerequisite_guard(value_row,self.output)
        row['host_prerequisite']['qualification_claim']=True
        with self.assertRaises(ValueError):qa.host_prerequisite_guard(row,self.output)

    def refresh_failed_metadata(self):
        for i,key in enumerate(('official_queue_sha256','manifest_sha256','snapshot_sha256')):
            item=self.row['artifacts'][i]
            self.row['artifacts'][i]=self.artifact(Path(item['path']),item['label'])
            self.row['queue_failure_contract'][key]=self.row['artifacts'][i]['sha256']

    def test_direct_failed_diagnostic_two_families_never_open_outputs_or_live_source(self):
        for family in ('raw-preflight','transport-probe'):
            manifest,_=self.failed_direct_diagnostic_fixture(family)
            self.save(manifest.parent/'evidence/result.json',{'passed':True,'model_calls':99})
            allowed={Path(a['path']).resolve() for a in self.row['artifacts']}
            original=Path.read_bytes;opened=[]
            def guarded(path):
                self.assertIn(path.resolve(),allowed);opened.append(path.resolve());return original(path)
            with patch.multiple(report,CAMPAIGN=self.campaign,REPO=self.root),patch.multiple(qa,CAMPAIGN=self.campaign,REPO=self.root),\
                    patch.object(Path,'read_bytes',guarded):
                result=report.qualification_row(self.row,self.output)
                self.assertEqual(qa.failed_queue_guard(result,self.output),[])
            self.assertEqual(set(opened),allowed)
            self.assertEqual(result['queue_failure']['schema'],'campaign002-failed-diagnostic-queue-1')
            self.assertIsNone(result['model_calls']);self.assertEqual(result['checks'],{})
            self.assertIsNone(result['timing']);self.assertFalse(result['scorable']);self.assertEqual(result['task_outcome'],'unknown')

    def test_direct_failed_diagnostic_rejects_every_dispatch_substitution(self):
        for index,value in ((0,'python'),(1,'-c'),(4,str(self.campaign/'harness/runtime.py')),(5,'--run'),
                            (6,'RCI001-C02-raw-preflight-003'),(8,'different'),(10,str(self.root/'other/snapshot.json')),
                            (12,str(self.root/'other-output'))):
            self.failed_direct_diagnostic_fixture();self.job['argv'][index]=value;self.save(self.queue_path,self.job);self.refresh_failed_metadata()
            with patch.multiple(report,CAMPAIGN=self.campaign,REPO=self.root),self.assertRaisesRegex(ValueError,'direct dispatch'):
                report.qualification_row(self.row,self.output)
        for key,value in (('cwd',str(self.campaign)),('resolved_executable',str(self.root/'other.exe'))):
            self.failed_direct_diagnostic_fixture();self.job[key]=value;self.save(self.queue_path,self.job);self.refresh_failed_metadata()
            with patch.multiple(report,CAMPAIGN=self.campaign,REPO=self.root),self.assertRaisesRegex(ValueError,'direct dispatch'):
                report.qualification_row(self.row,self.output)

    def test_direct_failed_diagnostic_rejects_extra_flags_and_family_alias(self):
        self.failed_direct_diagnostic_fixture();self.job['argv']+=['--turn-start'];self.save(self.queue_path,self.job);self.refresh_failed_metadata()
        with patch.multiple(report,CAMPAIGN=self.campaign,REPO=self.root),self.assertRaises(ValueError):report.qualification_row(self.row,self.output)
        self.failed_direct_diagnostic_fixture();self.row['run_id']='RCI001-C02-smoke-002'
        with patch.multiple(report,CAMPAIGN=self.campaign,REPO=self.root),self.assertRaises(ValueError):report.qualification_row(self.row,self.output)

    def test_direct_failed_diagnostic_rejects_anchor_substitution_and_declared_boolean_count(self):
        for mutate in (lambda x:x['source_snapshot'].update(sha256='0'*64),
                       lambda x:x['source_snapshot'].update(path='relative/snapshot.json'),
                       lambda x:x.update(model_calls=False),lambda x:x.update(physical_simulation=True)):
            manifest,_=self.failed_direct_diagnostic_fixture();value=json.loads(manifest.read_bytes());mutate(value)
            self.save(manifest,value);self.refresh_failed_metadata()
            with patch.multiple(report,CAMPAIGN=self.campaign,REPO=self.root),self.assertRaisesRegex(ValueError,'anchor or declared scope'):
                report.qualification_row(self.row,self.output)

    def test_direct_failed_diagnostic_requires_snapshot_source_even_with_rebound_anchor(self):
        for source in (None,{}, {'sha256':'a'*64,'bytes':True},{'sha256':'wrong','bytes':100}):
            manifest,snapshot=self.failed_direct_diagnostic_fixture();value=json.loads(snapshot.read_bytes())
            key=next(iter(value['sources']));value['sources']={} if source is None else {key:source}
            self.save(snapshot,value);declaration=json.loads(manifest.read_bytes());declaration['source_snapshot']['sha256']=report.sha(snapshot.read_bytes())
            self.save(manifest,declaration);self.refresh_failed_metadata()
            with patch.multiple(report,CAMPAIGN=self.campaign,REPO=self.root),self.assertRaises(ValueError):report.qualification_row(self.row,self.output)

    def test_direct_failed_diagnostic_cannot_use_legacy_contract(self):
        self.failed_direct_diagnostic_fixture();self.row['queue_failure_contract']['schema']='campaign002-failed-queue-diagnostic-1'
        with self.assertRaises(ValueError):report.qualification_row(self.row,self.output)

    def test_failed_queue_is_metadata_only_and_never_opens_attempt_outputs(self):
        self.failed_queue_fixture()
        self.assessment_path.unlink()
        with patch.object(report, 'timing_detail', side_effect=AssertionError('No timing access')), \
                patch.object(report, 'supervisory_detail', side_effect=AssertionError('No supervisor access')), \
                patch.object(report, 'protected_io_detail', side_effect=AssertionError('No derived diagnostics')):
            result = report.qualification_row(self.row, self.output)
        self.assertEqual(result['queue_state'], 'failed')
        self.assertEqual(result['queue_exit_status'], 1)
        self.assertEqual(result['assessment_state'], 'not_assessed')
        self.assertEqual(result['validity'], 'unknown')
        self.assertEqual(result['task_outcome'], 'unknown')
        self.assertFalse(result['scorable'])
        self.assertEqual(result['checks'], {})
        self.assertEqual(result['analyses'], [])
        for key in ('assessment_schema', 'timing', 'supervisory_timing', 'protected_io', 'native_reference', 'model_calls'):
            self.assertIsNone(result[key])
        self.assertEqual({r['path'] for r in report.READS}, {str(Path(a['path']).resolve()) for a in self.row['artifacts']})

    def test_failed_queue_diagnostic_is_hash_only_link_never_parsed_or_promoted(self):
        self.failed_queue_fixture()
        path = self.qual / 'failed-smoke-analysis.json'
        path.write_bytes(b'Not JSON; a separately authored diagnostic document, never an assessment.')
        self.row['diagnostic_analyses'] = [self.artifact(path, 'Separate failure diagnosis')]
        result = report.qualification_row(self.row, self.output)
        self.assertEqual(len(result['queue_failure']['diagnostic_links']), 1)
        self.assertEqual(result['queue_failure']['diagnostic_links'][0]['basis'], 'diagnostic_link_only')
        self.assertNotIn('content', result['queue_failure']['diagnostic_links'][0])
        self.assertEqual(result['checks'], {})
        self.assertEqual(result['analyses'], [])
        self.assertIsNone(result['timing'])

    def test_failed_queue_rejects_nonterminal_success_and_boolean_exit_before_other_reads(self):
        for state, code, end in [('running', None, None), ('succeeded', 0, '2026-01-01T00:00:01Z'),
                                 ('failed', 0, '2026-01-01T00:00:01Z'), ('failed', True, '2026-01-01T00:00:01Z'),
                                 ('failed', 1, None)]:
            self.failed_queue_fixture()
            report.READS.clear()
            self.job.update(state=state, exit_status=code, ended_at=end)
            self.save(self.queue_path, self.job)
            item = self.artifact(self.queue_path, 'Official queue receipt')
            self.row['artifacts'][0] = item
            self.row['queue_failure_contract']['official_queue_sha256'] = item['sha256']
            with self.assertRaises(ValueError):
                report.qualification_row(self.row, self.output)
            self.assertEqual([Path(r['path']).name for r in report.READS], [self.queue_path.name])
            self.job['ended_at'] = '2026-01-01T00:00:01Z'

    def test_failed_queue_rejects_scoring_verdict_counts_and_embedded_measurements(self):
        for field, value in [('scorable', True), ('validity', 'valid'), ('status', 'passed'),
                             ('assessment_state', 'assessed'), ('model_calls', 2), ('task_outcome', 'success'),
                             ('details', {'timing': {'passed': True}}), ('checks', {'all_canaries': True})]:
            self.failed_queue_fixture()
            report.READS.clear()
            self.row[field] = value
            with self.assertRaisesRegex(ValueError, 'diagnostic-only contract'):
                report.qualification_row(self.row, self.output)
            self.assertEqual(report.READS, [])
            if field == 'checks':
                del self.row[field]

    def test_failed_queue_declared_boolean_exit_cannot_alias_integer_failure(self):
        self.failed_queue_fixture()
        self.row['queue']['exit_status'] = True
        with self.assertRaisesRegex(ValueError, 'integer nonzero exit'):
            report.qualification_row(self.row, self.output)
        self.assertEqual([Path(r['path']).name for r in report.READS], [self.queue_path.name])

    def test_failed_queue_rejects_output_artifacts_before_opening_any(self):
        self.failed_queue_fixture()
        item = self.artifact(self.assessment_path, 'Original assessment')
        self.row['artifacts'].append(item)
        self.assessment_path.unlink()
        with self.assertRaisesRegex(ValueError, 'no outputs'):
            report.qualification_row(self.row, self.output)
        self.assertEqual(report.READS, [])

    def test_failed_queue_binds_actual_manifest_dispatch_and_revision(self):
        manifest, snapshot = self.failed_queue_fixture()
        self.job['argv'][3] = str(manifest.with_name('different-manifest.json'))
        self.save(self.queue_path, self.job)
        item = self.artifact(self.queue_path, 'Official queue receipt')
        self.row['artifacts'][0] = item
        self.row['queue_failure_contract']['official_queue_sha256'] = item['sha256']
        with self.assertRaisesRegex(ValueError, 'official dispatch'):
            report.qualification_row(self.row, self.output)
        self.failed_queue_fixture()
        self.save(snapshot, {'revision': 'other-revision'})
        item = self.artifact(snapshot, 'Frozen source snapshot')
        self.row['artifacts'][2] = item
        self.row['queue_failure_contract']['snapshot_sha256'] = item['sha256']
        with self.assertRaisesRegex(ValueError, 'revision mismatch'):
            report.qualification_row(self.row, self.output)

    def test_failed_queue_diagnostic_links_reject_raw_outputs_and_tampering(self):
        self.failed_queue_fixture()
        self.row['diagnostic_analyses'] = [self.artifact(self.assessment_path, 'Disguised diagnosis')]
        with self.assertRaisesRegex(ValueError, 'separate named'):
            report.qualification_row(self.row, self.output)
        path = self.qual / 'failed-smoke-diagnosis.md'
        path.write_text('Diagnostic only')
        self.row['diagnostic_analyses'] = [self.artifact(path, 'Failure diagnosis')]
        path.write_text('Changed document')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            report.qualification_row(self.row, self.output)

    def test_failed_queue_closeout_uses_exact_receipt_without_inventing_assessment(self):
        self.failed_queue_fixture()
        row = report.qualification_row(self.row, self.output)
        closeout = {'schema': 'campaign002-qualification-closeout-status-1',
                    'state': 'qualification_failed_blocked', 'basis_run_id': row['run_id'],
                    'basis_queue_sha256': row['queue_failure']['official_queue_sha256'], 'artifacts': []}
        result = report.current_status_detail(closeout, [row], {}, {'entries': []}, self.campaign, self.output)
        self.assertEqual(result['basis_kind'], 'official_terminal_execution_failure_without_assessment')
        for change in ({'basis_queue_sha256': '0' * 64}, {'basis_assessment_sha256': '0' * 64},
                       {'state': 'qualified_campaign_in_progress'}):
            with self.assertRaisesRegex(ValueError, 'closeout must bind'):
                report.current_status_detail({**closeout, **change}, [row], {}, {'entries': []}, self.campaign, self.output)

    def test_failed_queue_can_bind_ongoing_engineering_only_while_latest(self):
        self.failed_queue_fixture()
        row = report.qualification_row(self.row, self.output)
        closeout = {'schema': 'campaign002-qualification-closeout-status-1',
                    'state': 'qualification_in_progress', 'basis_run_id': row['run_id'],
                    'basis_queue_sha256': row['queue_failure']['official_queue_sha256'], 'artifacts': []}
        result = report.current_status_detail(closeout, [row], {}, {'entries': []}, self.campaign, self.output)
        self.assertEqual(result['state'], 'qualification_in_progress')
        self.assertEqual(result['basis_kind'], 'official_terminal_execution_failure_without_assessment')
        later = {'run_id': 'later-completed-attempt', 'status': 'failed'}
        for state in ('qualification_in_progress', 'qualification_failed_blocked'):
            with self.assertRaisesRegex(ValueError, 'latest completed attempt'):
                report.current_status_detail({**closeout, 'state': state}, [row, later], {},
                                             {'entries': []}, self.campaign, self.output)

    def test_full_synthetic_build_preserves_failure_without_scored_rows(self):
        self.timing_fixture()
        result = self.build()
        data = json.loads((self.output / 'qualification-data.json').read_bytes())
        self.assertEqual(result['scored_outcome_rows'], 0)
        self.assertNotIn('runs', data)
        self.assertEqual(data['history'][0]['status'], 'failed')
        self.assertEqual(data['history'][0]['task_outcome'], 'unknown')
        self.assertFalse(data['history'][0]['scorable'])
        with patch.object(qa, 'static_html', wraps=lambda html: {'checked': True}):
            self.assertEqual(qa.verify(self.output)['history_records'], 1)

    def test_running_receipt_blocks_before_any_assessment_access(self):
        self.job.update(state='running', exit_status=None)
        self.save(self.queue_path, self.job)
        self.row['artifacts'][0] = self.artifact(self.queue_path, 'Official queue receipt')
        self.assessment_path.unlink()
        with self.assertRaisesRegex(ValueError, 'Official queue succeeded'):
            report.qualification_row(self.row, self.output)
        self.assertEqual([Path(r['path']).name for r in report.READS], [self.queue_path.name])

    def test_boolean_zero_is_not_integer_exit_status(self):
        self.job['exit_status'] = False
        self.save(self.queue_path, self.job)
        self.row['artifacts'][0] = self.artifact(self.queue_path, 'Official queue receipt')
        with self.assertRaisesRegex(ValueError, 'integer exit0'):
            report.qualification_row(self.row, self.output)

    def test_tampered_assessment_is_rejected(self):
        self.assessment_path.write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            report.qualification_row(self.row, self.output)

    def test_history_cannot_promote_original_failed_verdict(self):
        self.row['status'] = 'passed'
        with self.assertRaisesRegex(ValueError, 'original assessment verdict'):
            report.qualification_row(self.row, self.output)

    def test_exact_assessment_identity_required(self):
        self.assessment['queue_job_id'] = 'another-job'
        self.refresh_assessment()
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            report.qualification_row(self.row, self.output)

    def test_cancelled_before_start_has_no_outcome(self):
        self.row['status'] = 'cancelled'
        self.job.update(state='canceled', started_at=None, exit_status=None)
        self.save(self.queue_path, self.job)
        self.row['artifacts'] = [self.artifact(self.queue_path, 'Official queue receipt')]
        value = report.qualification_row(self.row, self.output)
        self.assertEqual(value['status'], 'cancelled')
        self.assertIsNone(value['timing'])
        self.row['artifacts'].append(self.artifact(self.assessment_path, 'Original assessment'))
        with self.assertRaisesRegex(ValueError, 'cannot consume an outcome'):
            report.qualification_row(self.row, self.output)

    def test_cancellation_after_start_is_rejected(self):
        self.row['status'] = 'cancelled'
        self.job.update(state='canceled', exit_status=None)
        self.save(self.queue_path, self.job)
        self.row['artifacts'][0] = self.artifact(self.queue_path, 'Official queue receipt')
        with self.assertRaisesRegex(ValueError, 'before start'):
            report.qualification_row(self.row, self.output)

    def test_raw_diagnosis_keeps_null_strict_verdict(self):
        self.timing_fixture()
        row = report.qualification_row(self.row, self.output)
        self.assertEqual(row['timing']['basis'], 'diagnostic_only')
        self.assertIsNone(row['timing']['strict_passed'])
        self.assertFalse(row['timing']['strict_verification_available'])
        self.assertEqual(row['timing']['phases'], self.metadata['phases'])

    def test_tampered_timing_binary_is_rejected(self):
        self.timing_fixture()
        (self.qual / 'timing-samples.bin').write_bytes(b'Changed')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            report.qualification_row(self.row, self.output)

    def test_missing_metadata_hash_cannot_downgrade_to_unbound_read(self):
        self.timing_fixture()
        del self.host['timing_v2']['metadata_sha256']
        self.save(self.host_path, self.host)
        self.assessment['bindings']['host_result'] = self.artifact(self.host_path, 'Host')
        self.refresh_assessment()
        with self.assertRaisesRegex(ValueError, 'Explicit artifact SHA'):
            report.qualification_row(self.row, self.output)

    def test_independent_and_host_metadata_must_agree(self):
        self.timing_fixture()
        self.assessment['timing'] = {'passed': False, 'metadata_sha256': '0' * 64,
                                     'sample_sha256': self.metadata['sha256']}
        self.refresh_assessment()
        with self.assertRaisesRegex(ValueError, 'Independent timing/host'):
            report.qualification_row(self.row, self.output)

    def test_bound_original_analysis_is_preserved_without_recomputation(self):
        analysis = {'schema': 'original-analysis', 'run_id': self.run_id, 'queue_job_id': self.job['id'],
                    'provenance': {'official_queue_receipt': {'sha256': self.row['artifacts'][0]['sha256']}},
                    'finding': {'wall_s': .125839, 'cause': 'unknown'}, 'scorable': False}
        path = self.qual / 'fixture-analysis.json'
        self.save(path, analysis)
        self.row['artifacts'].append(self.artifact(path, 'Original analysis'))
        row = report.qualification_row(self.row, self.output)
        self.assertEqual(row['analyses'][0]['content'], {k:v for k,v in analysis.items() if k != 'provenance'})
        analysis['provenance']['official_queue_receipt']['sha256'] = '0' * 64
        self.save(path, analysis)
        self.row['artifacts'][-1] = self.artifact(path, 'Original analysis')
        with self.assertRaisesRegex(ValueError, 'analysis queue hash'):
            report.qualification_row(self.row, self.output)

    def test_new_scored_metadata_changes_state_without_reading_assessment(self):
        folder = self.campaign / 'execution/run-fixture'
        self.save(folder / 'launch-intent.json', {'run_id': 'run-fixture'})
        self.save(folder / 'queue-submit.json', {'id': 'scored-job', 'state': 'running'})
        (folder / 'assessment.json').write_text('THIS MUST NEVER BE PARSED', encoding='utf-8')
        inventory = report.launch_inventory(self.campaign, self.output)
        self.assertEqual(inventory['state'], 'scored_launch_metadata_present')
        self.assertEqual(inventory['launch_intents'], 1)
        self.assertFalse(any(Path(r['path']).name == 'assessment.json' for r in report.READS))

    def test_disposition_alone_prevents_false_unlaunched_claim(self):
        folder = self.campaign / 'execution/run-fixture'
        folder.mkdir(parents=True)
        (folder / 'disposition.json').write_bytes(b'Inventoried bytes; not interpreted')
        inventory = report.launch_inventory(self.campaign, self.output)
        self.assertEqual(inventory['state'], 'scored_launch_metadata_present')
        self.assertEqual(inventory['disposition_files'], 1)

    def test_launcher_must_record_intent_before_submission(self):
        self.operator.write_text("def start():\n    queue('submit')\n    save(folder / 'launch-intent.json', {})\n", encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'intent before'):
            report.launch_inventory(self.campaign, self.output)

    def test_inventory_race_is_rejected_before_publishing(self):
        original = report.inventory_paths
        calls = 0
        def changing(campaign):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.save(self.campaign / 'execution/new/launch-intent.json', {})
            return original(campaign)
        with patch.object(report, 'inventory_paths', side_effect=changing):
            with self.assertRaisesRegex(ValueError, 'inventory changed'):
                self.build()
        self.assertFalse((self.output / 'qualification-report.html').exists())

    def test_frozen_campaign001_counts_cannot_drift(self):
        value = json.loads(self.prior.read_bytes())
        value['counts']['all scheduled slots']['valid'] = 7
        self.save(self.prior, value)
        with self.assertRaisesRegex(ValueError, 'Campaign001 frozen counts'):
            self.build()

    def test_unindexed_ongoing_probe_is_never_opened(self):
        (self.qual / 'host-probe-running-assessment.json').write_text('MUST NEVER BE READ', encoding='utf-8')
        self.build()
        self.assertFalse(any('running-assessment' in r['path'] for r in report.READS))

    def test_html_text_in_evidence_cannot_close_inline_script(self):
        self.row['reason'] = '</script><script>alert(1)</script>'
        self.build()
        html = (self.output / 'qualification-report.html').read_text(encoding='utf-8')
        self.assertEqual(html.count('</script>'), 1)
        qa.static_html(html, javascript=False)

    def test_generated_data_tampering_fails_qa(self):
        self.build()
        (self.output / 'qualification-data.json').write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'artifact hash mismatch'):
            qa.verify(self.output)

    def test_template_has_complete_unique_targets(self):
        result = qa.static_html((report.HERE / 'qualification_template.html').read_text(encoding='utf-8'), javascript=False)
        self.assertGreater(result['script_references'], 20)
        self.assertEqual(result['external_dependencies'], 0)

    def test_mechanical_verdict_without_host_result_preserves_all_separate_rounds(self):
        self.feasibility_fixture()
        row = report.qualification_row(self.row, self.output)
        self.assertIsNone(row['timing'])
        self.assertTrue(row['recorder_feasibility']['mechanical_feasibility_passed'])
        self.assertEqual(row['recorder_feasibility']['rounds'], self.assessment['rounds'])
        self.assertEqual(row['recorder_feasibility']['recovery_checks'], self.assessment['recovery_checks'])
        self.assertFalse(row['scorable'])
        self.assertFalse(row['recorder_feasibility']['production_adopted'])
        self.assertNotIn('pooled_latency', row['recorder_feasibility'])

    def test_failed_mechanical_round_and_unrun_recovery_remain_visible(self):
        self.feasibility_fixture(passed=False)
        self.build()
        data = json.loads((self.output / 'qualification-data.json').read_bytes())
        row = data['history'][0]
        self.assertEqual(row['status'], 'failed')
        self.assertEqual(len(row['recorder_feasibility']['rounds']), 8)
        self.assertIsNone(row['recorder_feasibility']['rounds'][3]['timing'])
        self.assertFalse(row['recorder_feasibility']['recovery_checks'][2]['passed'])
        self.assertIn('all_rounds_mechanically_valid', row['failed_checks'])
        with patch.object(qa, 'static_html', return_value={}):
            self.assertEqual(qa.verify(self.output)['scored_outcome_rows'], 0)

    def test_mechanical_boolean_cannot_be_integer_or_ambiguous_verdict(self):
        self.feasibility_fixture()
        self.assessment['mechanical_feasibility_passed'] = 1
        self.refresh_assessment()
        with self.assertRaisesRegex(ValueError, 'original assessment verdict'):
            report.qualification_row(self.row, self.output)
        self.assessment['mechanical_feasibility_passed'] = True
        self.assessment['diagnostic_passed'] = True
        self.refresh_assessment()
        with self.assertRaisesRegex(ValueError, 'original assessment verdict'):
            report.qualification_row(self.row, self.output)

    def test_mechanical_failure_cannot_be_promoted_in_history(self):
        self.feasibility_fixture(passed=False)
        self.row['status'] = 'passed'
        with self.assertRaisesRegex(ValueError, 'original assessment verdict'):
            report.qualification_row(self.row, self.output)

    def test_mechanical_support_requires_no_adoption_or_score(self):
        self.feasibility_fixture()
        self.assessment['production_adopted'] = True
        self.refresh_assessment()
        with self.assertRaisesRegex(ValueError, 'no-adoption boundary'):
            report.qualification_row(self.row, self.output)

    def test_mechanical_rounds_cannot_be_reordered_or_dropped(self):
        self.feasibility_fixture()
        self.assessment['rounds'][0]['mode'] = 'PERSIST'
        self.refresh_assessment()
        with self.assertRaisesRegex(ValueError, 'eight ordered'):
            report.qualification_row(self.row, self.output)
        self.assessment['rounds'].pop()
        self.refresh_assessment()
        with self.assertRaisesRegex(ValueError, 'eight ordered'):
            report.qualification_row(self.row, self.output)

    def test_mechanical_recovery_copy_inventory_cannot_be_collapsed(self):
        self.feasibility_fixture()
        self.assessment['recovery_checks'].pop()
        self.refresh_assessment()
        with self.assertRaisesRegex(ValueError, 'four assessment crash copies'):
            report.qualification_row(self.row, self.output)

    def test_preflight_without_queue_stays_unknown_and_unassessed(self):
        self.preflight_fixture()
        self.build()
        data = json.loads((self.output/'qualification-data.json').read_bytes())
        row = data['history'][0]
        self.assertEqual((row['status'],row['validity'],row['task_outcome']),('not_run','unknown','unknown'))
        self.assertEqual(row['preflight']['assessment_state'],'not_assessed')
        self.assertIsNone(row['job_id'])
        self.assertIsNone(row['queue_state'])
        self.assertIsNone(row['timing'])
        self.assertIsNone(row['recorder_feasibility'])
        self.assertFalse(any(Path(item['path']).name.endswith('-assessment.json') for item in report.READS))
        with patch.object(qa,'static_html',return_value={}):
            self.assertEqual(qa.verify(self.output)['history_records'],1)

    def test_not_run_without_explicit_preflight_contract_is_rejected(self):
        self.row['status']='not_run'
        with self.assertRaisesRegex(ValueError,'preflight contract'):
            report.qualification_row(self.row,self.output)
        self.assertEqual(report.READS,[])

    def test_preflight_cannot_fabricate_a_queue_receipt(self):
        self.preflight_fixture()
        self.row['queue']={'id':'invented-job'}
        with self.assertRaisesRegex(ValueError,'preflight contract'):
            report.qualification_row(self.row,self.output)
        self.assertEqual(report.READS,[])

    def test_preflight_cannot_consume_an_assessment_even_if_linked(self):
        self.preflight_fixture()
        self.row['artifacts'].append(self.artifact(self.assessment_path,'Outcome to reject'))
        with self.assertRaisesRegex(ValueError,'no outputs or queue receipt'):
            report.qualification_row(self.row,self.output)
        self.assertEqual(report.READS,[])

    def test_preflight_snapshot_must_bind_the_unlaunched_manifest(self):
        _,_,snapshot=self.preflight_fixture()
        value=json.loads(snapshot.read_bytes());value['manifest_sha256']='0'*64;self.save(snapshot,value)
        self.row['artifacts'][2]=self.artifact(snapshot,'Frozen source snapshot')
        self.row['preflight_contract']['snapshot_sha256']=self.row['artifacts'][2]['sha256']
        with self.assertRaisesRegex(ValueError,'manifest/snapshot identity or hash'):
            report.qualification_row(self.row,self.output)

    def test_preflight_launch_marker_contradiction_is_rejected(self):
        record,_,_=self.preflight_fixture()
        self.save(record.parent/'queue-submit.json',{'id':'actually-submitted'})
        with self.assertRaisesRegex(ValueError,'no-launch inventory contradicts'):
            report.qualification_row(self.row,self.output)

    def test_preflight_evidence_directory_contradiction_is_rejected(self):
        self.preflight_fixture()
        Path(self.row['preflight_contract']['unlaunched_evidence_path']).mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'no-launch inventory contradicts'):
            report.qualification_row(self.row,self.output)

    def test_native_reference_success_does_not_hide_strict_case_failure(self):
        cases=[{'run_id':'reference-'+str(i), 'family':'fixture', 'passed':i!=0,
                'checks':{'independent_success':True,'strict_fresh_timing':i!=0},'errors':{},
                'terminal':'task_success','independent_outcome':{'independent_task_outcome':'success'},
                'timing':{'passed':i!=0,'resource_integrity_pass':True,
                          'replayed_timing':{'maximum_lag_s':.1001493 if i==0 else .04,
                              'outside_rtf_tolerance_windows':2 if i==0 else 0,'complete_wall_windows':59}}}
               for i in range(6)]
        self.assessment.pop('diagnostic_passed')
        self.assessment.update(schema='campaign002-native-assessment-1',qualification_passed=False,rows=cases)
        self.refresh_assessment()
        row=report.qualification_row(self.row,self.output)
        self.assertEqual(row['status'],'failed')
        self.assertIn('reference-0::strict_fresh_timing',row['failed_checks'])
        self.assertEqual(len(row['native_reference']['cases']),6)
        self.assertTrue(all(c['observed_reference_task_outcome']=='success' for c in row['native_reference']['cases']))
        self.assertEqual(row['task_outcome'],'unknown')
        self.assertFalse(row['scorable'])

    def test_native_reference_case_inventory_cannot_be_collapsed(self):
        self.assessment.pop('diagnostic_passed')
        self.assessment.update(schema='campaign002-native-assessment-1',qualification_passed=False,rows=[])
        self.refresh_assessment()
        with self.assertRaisesRegex(ValueError,'six separate reference cases'):
            report.qualification_row(self.row,self.output)

    def test_analysis_list_binding_requires_exact_official_path_and_receipt(self):
        value={'run_id':self.run_id,'queue_job_id':self.job['id'],'schema':'retained-native-analysis',
               'official_receipt':self.job,'provenance':{'bindings':[self.artifact(self.queue_path,'Queue')]}}
        path=self.qual/'fixture-analysis.json';self.save(path,value)
        self.row['artifacts'].append(self.artifact(path,'Original analysis'))
        self.assertEqual(len(report.qualification_row(self.row,self.output)['analyses']),1)
        value['official_receipt']=dict(self.job,state='running');self.save(path,value)
        self.row['artifacts'][-1]=self.artifact(path,'Original analysis')
        with self.assertRaisesRegex(ValueError,'path/hash/receipt mismatch'):
            report.qualification_row(self.row,self.output)

    def test_analysis_list_binding_cannot_substitute_another_path(self):
        binding=self.artifact(self.queue_path,'Queue');binding['path']=str(self.qual/'different-queue.json')
        with self.assertRaisesRegex(ValueError,'path/hash/receipt mismatch'):
            report.analysis_queue_binding({'official_receipt':self.job,'provenance':{'bindings':[binding]}},
                                          self.row['artifacts'][0],self.job)

    def test_closeout_binds_failure_and_becomes_historical_if_launch_records_appear(self):
        self.closeout={'schema':'campaign002-qualification-closeout-status-1','state':'qualification_failed_blocked',
                      'basis_run_id':self.run_id,'basis_assessment_sha256':self.row['artifacts'][1]['sha256']}
        self.build();data=json.loads((self.output/'qualification-data.json').read_bytes())
        self.assertEqual(data['qualification_state'],'qualification_failed_blocked')
        self.assertTrue(data['qualification_closeout']['current_for_launch_inventory'])
        self.save(self.campaign/'execution/later/launch-intent.json',{'run_id':'later'})
        self.build();data=json.loads((self.output/'qualification-data.json').read_bytes())
        self.assertEqual(data['qualification_state'],'preserved_qualification_history')
        self.assertFalse(data['qualification_closeout']['current_for_launch_inventory'])

    def test_closeout_cannot_bind_a_different_assessment(self):
        self.closeout={'schema':'campaign002-qualification-closeout-status-1','state':'qualification_failed_blocked',
                      'basis_run_id':self.run_id,'basis_assessment_sha256':'0'*64}
        with self.assertRaisesRegex(ValueError,'bind its original failed assessment'):
            self.build()

    def pilot_fixture(self, *, passed=True, outcome='failure'):
        self.row.update(status='passed' if passed else 'failed',validity='valid' if passed else 'invalid')
        manifest_path=self.qual/'pilot-manifest.json';snapshot_path=self.qual/'frozen/snapshot.json'
        assessor=self.qual/'assessment/assess.py';assessor.parent.mkdir();assessor.write_text('# original assessor\n')
        verifier=self.qual/'admission.py';verifier.write_text("PILOT_CHECKS={'one_call','all_canaries'}\nPILOT_CHECKS.add('memory')\n")
        manifest={'run_id':self.run_id,'framework_revision':self.row['revision'],'family':'misplaced-stock',
            'model':'gpt-6-astra','effort':'max','bootstrap':'Follow the instructions in RobotAgentPrompt.md.',
            'model_turns_max':1,'interruption_trigger':None,'noise_seed':24102}
        self.save(manifest_path,manifest)
        self.save(snapshot_path,{'revision':self.row['revision'],'sources':{str(assessor):{'sha256':report.sha(assessor.read_bytes())}}})
        archive=snapshot_path.with_name('code.zip');archive.write_bytes(b'Original frozen archive bytes')
        self.assessment={'schema':'robot-codex-campaign-assessment-2','run_id':self.run_id,
            'framework_revision':self.row['revision'],'queue_job_id':self.job['id'],
            'validity':'valid' if passed else 'invalid','failed_checks':[] if passed else ['memory'],
            'checks':{'one_call':True,'all_canaries':True,'memory':passed},'task_evidence_valid':passed,
            'task_outcome':outcome if passed else 'unknown','observed_task_outcome':outcome,'family':'misplaced-stock',
            'scorable':False,'campaign_timing':{'schema':'rci-campaign-independent-timing-2',
                **{k:True for k in ('passed','scheduling_pass','resource_integrity_pass','garbage_collection_pass','host_memory_pass')}},
            'bindings':{'queue_receipt_sha256':report.sha(self.queue_path.read_bytes()),
                'manifest_sha256':report.sha(manifest_path.read_bytes()),'framework_snapshot_sha256':report.sha(snapshot_path.read_bytes()),
                'framework_archive_sha256':report.sha(archive.read_bytes()),'assessment_sha256':report.sha(assessor.read_bytes())}}
        self.refresh_assessment()
        manifest_item=self.artifact(manifest_path,'Manifest');snapshot_item=self.artifact(snapshot_path,'Snapshot')
        entry={'assessment':self.row['artifacts'][1],'queue':self.row['artifacts'][0],
               'manifest':manifest_item,'snapshot':snapshot_item,'family':'misplaced-stock'}
        disposition=self.qual/'pilot/disposition.json';self.save(disposition,{'run_id':self.run_id,'passed':passed,
            'error':None if passed else 'Original admission rejected memory','entry':entry})
        preflight=self.qual/'preflight.json';self.save(preflight,{'schema':'campaign002-final-qualification-preflight-1',
            'orchestration_sources':[self.artifact(verifier,'Admission verifier')]})
        bindings={k:self.artifact(p,k) for k,p in [('disposition',disposition),('verifier',verifier),
                                                ('base_assessor',assessor),('preflight',preflight)]}
        self.row['pilot_admission']={'schema':'campaign002-pilot-history-binding-1',**bindings}
        self.row['artifacts'].extend([manifest_item,snapshot_item,*bindings.values()])
        return disposition

    def refresh_pilot_disposition(self,path):
        value=json.loads(path.read_bytes());value['entry']['assessment']=self.row['artifacts'][1];self.save(path,value)
        item=self.artifact(path,'disposition');self.row['pilot_admission']['disposition']=item
        self.row['artifacts']=[item if a['path']==str(path) else a for a in self.row['artifacts']]

    def test_valid_task_failure_can_pass_original_pilot_apparatus_admission(self):
        self.pilot_fixture();self.build()
        row=json.loads((self.output/'qualification-data.json').read_bytes())['history'][0]
        self.assertEqual(row['status'],'passed');self.assertEqual(row['task_outcome'],'unknown')
        self.assertFalse(row['scorable']);self.assertTrue(row['pilot_admission']['admission_passed'])
        self.assertEqual(row['pilot_admission']['assessed_task_outcome'],'failure')
        self.assertEqual(row['pilot_admission']['required_admission_checks'],['all_canaries','memory','one_call'])
        self.assertNotIn('qualification_passed',self.assessment)
        self.assertEqual(qa.verify(self.output)['scored_outcome_rows'],0)

    def test_failed_pilot_retains_original_admission_error_and_observed_outcome(self):
        self.pilot_fixture(passed=False,outcome='success');self.build()
        row=json.loads((self.output/'qualification-data.json').read_bytes())['history'][0]
        self.assertEqual(row['status'],'failed');self.assertEqual(row['failed_checks'],['memory'])
        self.assertEqual(row['pilot_admission']['observed_task_outcome'],'success')
        self.assertFalse(row['pilot_admission']['admission_passed'])

    def test_pilot_pass_rejects_missing_declared_check_even_when_failed_list_empty(self):
        path=self.pilot_fixture();del self.assessment['checks']['all_canaries'];self.refresh_assessment();self.refresh_pilot_disposition(path)
        with self.assertRaisesRegex(ValueError,'contradicts its original assessment'):
            self.build()

    def test_pilot_cannot_substitute_queue_or_frozen_assessor(self):
        path=self.pilot_fixture()
        for key in ('queue_receipt_sha256','assessment_sha256','framework_snapshot_sha256'):
            original=self.assessment['bindings'][key];self.assessment['bindings'][key]='0'*64
            self.refresh_assessment();self.refresh_pilot_disposition(path)
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'binding differs'):
                self.build()
            self.assessment['bindings'][key]=original

    def test_pilot_admission_is_not_invented_from_validity_without_disposition(self):
        self.pilot_fixture();del self.row['pilot_admission']
        with self.assertRaisesRegex(ValueError,'explicit original admission disposition'):
            self.build()

    def test_pilot_supports_original_continuation_preflight_without_a_synthetic_pass_flag(self):
        self.pilot_fixture();binding=self.row['pilot_admission']['preflight'];path=Path(binding['path'])
        value=json.loads(path.read_bytes());value['schema']='campaign002-final-qualification-continuation-preflight-1'
        self.save(path,value);item=self.artifact(path,'preflight');self.row['pilot_admission']['preflight']=item
        self.row['artifacts']=[item if a['path']==str(path) else a for a in self.row['artifacts']]
        self.assertTrue(report.qualification_row(self.row,self.output)['pilot_admission']['admission_passed'])
        self.assessment['qualification_passed']=True;self.refresh_assessment()
        with self.assertRaisesRegex(ValueError,'invented qualification verdict'):
            report.qualification_row(self.row,self.output)

    def test_model_inventory_binds_separate_host_and_supervisor_ledgers(self):
        self.supervisory_fixture();binding=self.assessment['bindings'].pop('host_result')
        self.row['artifacts'].append(self.artifact(self.host_path,'Protected host result'))
        self.assessment['evidence_inventory']=[{'root':'protected_host','path':'result.json',
            'sha256':binding['sha256'],'bytes':self.host_path.stat().st_size}];self.refresh_assessment()
        row=report.qualification_row(self.row,self.output)
        self.assertIsNotNone(row['timing']);self.assertIsNotNone(row['supervisory_timing'])
        self.assessment['evidence_inventory'][0]['sha256']='0'*64;self.refresh_assessment()
        with self.assertRaisesRegex(ValueError,'exact original model-assessment binding'):
            report.qualification_row(self.row,self.output)

    def test_in_progress_status_binds_completed_latest_qualifier_without_promoting_it(self):
        self.closeout={'schema':'campaign002-qualification-closeout-status-1','state':'qualification_in_progress',
            'basis_run_id':self.run_id,'basis_assessment_sha256':self.row['artifacts'][1]['sha256']}
        self.build();data=json.loads((self.output/'qualification-data.json').read_bytes())
        self.assertEqual(data['qualification_state'],'qualification_in_progress');self.assertEqual(data['history'][0]['status'],'failed')
        self.assertEqual(qa.verify(self.output)['scored_outcome_rows'],0)
        self.save(self.campaign/'execution/later/launch-intent.json',{'run_id':'later'})
        self.build();data=json.loads((self.output/'qualification-data.json').read_bytes())
        self.assertEqual(data['qualification_state'],'preserved_qualification_history')

    def final_status_fixture(self,terminal=False):
        kinds=['campaign002-native-assessment-1','campaign002-boundary-suite-1','robot-codex-physical-smoke-assessment-2']+['robot-codex-campaign-assessment-2']*2
        rows=[];indexed=[];entries=[]
        for n,kind in enumerate(kinds):
            artifacts=[];entry={}
            for key in ('assessment','manifest','snapshot','queue'):
                path=self.qual/str(n)/(key+'-assessment.json' if key=='assessment' else key+'.json');self.save(path,{key:n})
                item=self.artifact(path,key);artifacts.append(item);entry[key]=item
            if n>2:entry['family']=('misplaced-stock','blocked-insert-home')[n-3]
            identity='fixture-stage-'+str(n);indexed.append({'run_id':identity,'status':'passed','artifacts':artifacts})
            rows.append({'run_id':identity,'status':'passed','assessment_schema':kind,
                'links':[{'sha256':a['sha256'],'href':a['path']} for a in artifacts]});entries.append(entry)
        ledger=self.qual/'completed.json';self.save(ledger,{'schema':'campaign002-final-qualification-completed-1',
            **dict(zip(('native','boundary','smoke'),entries[:3])),'pilots':entries[3:]})
        status={'schema':'campaign002-qualification-closeout-status-1',
            'state':'campaign_terminal' if terminal else 'qualified_campaign_in_progress',
            'basis_run_id':rows[-1]['run_id'],'basis_assessment_sha256':entries[-1]['assessment']['sha256'],
            'final_ledger':self.artifact(ledger,'Final ledger')}
        if terminal:
            attempts=[];dispositions=[]
            for ordinal in range(1,21):
                family='misplaced-stock' if ordinal%2 else 'blocked-insert-home'
                identity=f"RCI001-C02-{'stock' if ordinal%2 else 'home'}-{(ordinal+1)//2:02}"
                attempt={'ordinal':ordinal,'run_id':identity,'family':family};attempts.append(attempt)
                path=self.campaign/'execution'/identity/'disposition.json';self.save(path,{**attempt,'execution_status':'completed'})
                dispositions.append(self.artifact(path,'Disposition'))
            plan=self.campaign/'execution-plan.json';self.save(plan,{'schema':'campaign002-execution-plan-1',
                'campaign_id':'RCI001-Campaign002','attempts':attempts})
            stop=self.campaign/'execution/campaign-stop.json';self.save(stop,{'schema':'campaign002-stop-1',
                'planned':20,'stop_after_ordinal':20,'remaining_admission_authorized':False})
            status.update(terminal_plan=self.artifact(plan,'Plan'),terminal_stop=self.artifact(stop,'Stop'),terminal_dispositions=dispositions)
        return status,rows,{'attempts':indexed},{'entries':[]}

    def test_qualified_status_requires_five_exact_passed_final_ledger_stages(self):
        status,rows,index,inventory=self.final_status_fixture()
        value=report.current_status_detail(status,rows,index,inventory,self.campaign,self.output)
        self.assertEqual(len(value['final_qualification_run_ids']),5)
        index['attempts'][2]['status']='failed'
        with self.assertRaisesRegex(ValueError,'five exact passed'):
            report.current_status_detail(status,rows,index,inventory,self.campaign,self.output)

    def test_final_ledger_rejects_substituted_artifact_or_stage_role(self):
        status,rows,index,inventory=self.final_status_fixture()
        rows[0]['assessment_schema']='robot-codex-campaign-assessment-2'
        with self.assertRaisesRegex(ValueError,'stage.*roles'):
            report.current_status_detail(status,rows,index,inventory,self.campaign,self.output)
        rows[0]['assessment_schema']='campaign002-native-assessment-1';index['attempts'][0]['artifacts'][0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'five exact passed'):
            report.current_status_detail(status,rows,index,inventory,self.campaign,self.output)

    def test_terminal_state_requires_all_twenty_exact_dispositions_and_stop(self):
        status,rows,index,inventory=self.final_status_fixture(terminal=True)
        value=report.current_status_detail(status,rows,index,inventory,self.campaign,self.output)
        self.assertEqual(value['terminal_disposition_count'],20)
        status['terminal_dispositions'].pop()
        with self.assertRaisesRegex(ValueError,'all twenty'):
            report.current_status_detail(status,rows,index,inventory,self.campaign,self.output)

    def test_terminal_state_cannot_promote_pending_or_mismatched_slot(self):
        status,rows,index,inventory=self.final_status_fixture(terminal=True)
        path=Path(status['terminal_dispositions'][4]['path']);value=json.loads(path.read_bytes());value['execution_status']='running'
        self.save(path,value);status['terminal_dispositions'][4]=self.artifact(path,'Disposition')
        with self.assertRaisesRegex(ValueError,'pending, mismatched'):
            report.current_status_detail(status,rows,index,inventory,self.campaign,self.output)

    def test_terminal_state_preserves_legitimate_early_stop_and_all_later_not_run_slots(self):
        status,rows,index,inventory=self.final_status_fixture(terminal=True)
        stop=Path(status['terminal_stop']['path']);value=json.loads(stop.read_bytes());value['stop_after_ordinal']=8
        self.save(stop,value);status['terminal_stop']=self.artifact(stop,'Stop')
        for n in range(8,20):
            path=Path(status['terminal_dispositions'][n]['path']);value=json.loads(path.read_bytes());value['execution_status']='not_run'
            self.save(path,value);status['terminal_dispositions'][n]=self.artifact(path,'Disposition')
        result=report.current_status_detail(status,rows,index,inventory,self.campaign,self.output)
        self.assertEqual(result['terminal_disposition_count'],20)

    def test_in_progress_state_cannot_bind_an_older_completed_qualifier(self):
        status,rows,index,inventory=self.final_status_fixture()
        status.update(state='qualification_in_progress',basis_run_id=rows[0]['run_id'],
                      basis_assessment_sha256=index['attempts'][0]['artifacts'][0]['sha256'])
        with self.assertRaisesRegex(ValueError,'latest completed qualifier'):
            report.current_status_detail(status,rows,index,inventory,self.campaign,self.output)

    def test_passing_boundary_raw_suite_keeps_failed_original_admission(self):
        evidence=self.qual/'boundary-evidence';suite=evidence/'suite-result.json'
        self.save(suite,{'schema':'campaign002-boundary-suite-1','qualified':True,'checks':{'all_runtime_checks':True}})
        self.job.update(argv=['python','boundary_suite.py','--output',str(evidence)],cwd=str(self.root));self.save(self.queue_path,self.job)
        manifest=self.qual/'boundary-manifest.json';self.save(manifest,{'run_id':self.run_id,'framework_revision':self.row['revision']})
        snapshot=self.qual/'snapshot.json';self.save(snapshot,{'revision':self.row['revision']})
        artifacts=[self.artifact(self.queue_path,'Official queue receipt'),self.artifact(suite,'Original suite'),
                   self.artifact(manifest,'Manifest'),self.artifact(snapshot,'Snapshot')]
        disposition=self.qual/'boundary/disposition.json';self.save(disposition,{'run_id':self.run_id,'passed':False,
            'error':'Boundary source receipt differs from snapshot','entry':dict(zip(('queue','assessment','manifest','snapshot'),artifacts))})
        binding=self.artifact(disposition,'Original admission disposition');self.row.update(artifacts=artifacts+[binding],admission_disposition=binding)
        self.closeout={'schema':'campaign002-qualification-closeout-status-1','state':'qualification_in_progress',
            'basis_run_id':self.run_id,'basis_assessment_sha256':artifacts[1]['sha256']}
        self.build();data=json.loads((self.output/'qualification-data.json').read_bytes());row=data['history'][0]
        self.assertEqual(row['status'],'failed');self.assertEqual(row['checks'],{'all_runtime_checks':True})
        self.assertTrue(row['admission_disposition']['original_raw_passed']);self.assertFalse(row['admission_disposition']['admission_passed'])
        self.assertEqual(row['admission_disposition']['error'],'Boundary source receipt differs from snapshot')
        self.assertEqual(qa.verify(self.output)['scored_outcome_rows'],0)
        self.row['status']='passed'
        with self.assertRaisesRegex(ValueError,'original coordinator admission disposition'):
            self.build()

    def test_original_admission_disposition_rejects_substituted_assessment_binding(self):
        status,rows,index,inventory=self.final_status_fixture()
        artifacts=index['attempts'][0]['artifacts'];record=self.qual/'bad-disposition.json'
        entry=dict(zip(('assessment','manifest','snapshot','queue'),artifacts));entry=copy.deepcopy(entry)
        entry['assessment']['sha256']='0'*64
        self.save(record,{'run_id':'fixture','passed':False,'entry':entry})
        item=self.artifact(record,'Disposition')
        row={'run_id':'fixture','status':'failed','artifacts':artifacts+[item],'admission_disposition':item}
        documents={str(record):json.loads(record.read_bytes())}
        with self.assertRaisesRegex(ValueError,'input differs: assessment'):
            report.admission_disposition_detail(row,documents,artifacts[-1])


class NoModelDiagnosticContracts(unittest.TestCase):
    """Only synthetic result/queue bytes; never replays a real diagnostic."""

    def setUp(self):
        self.f = CompanionIntegrity('test_successful_row_links_cross_run_diagnostics_without_pooling')
        self.f.setUp()
        self.addCleanup(self.f.tearDown)
        self.enterContext(patch.object(report, 'REPO', self.f.root))
        self.enterContext(patch.object(report, 'CAMPAIGN', self.f.campaign))

    def fixture(self, kind='raw_event_preflight_diagnostic', schema=None):
        if schema is None:
            schema, script = report.NO_MODEL_DIAGNOSTICS[kind]
            readiness_label = 'Verified v11 readiness entry'
        else:
            script = report.NO_MODEL_DIAGNOSTIC_SCHEMAS[kind][schema]
            readiness_label = 'Verified readiness entry'
        root = self.f.campaign / 'io-repair' / kind
        result_path = root / 'evidence/result.json'
        snapshot = root / 'release/snapshot.json'
        queue_path, entry_path = root / 'official-status.json', root / 'entry.json'
        self.f.save(snapshot, {'revision': 'dev-diagnostic', 'sources': {}})
        snapshot_item = self.f.artifact(snapshot, 'Frozen source snapshot')
        result = {'schema': schema, 'run_id': 'synthetic-' + kind, 'framework_revision': 'dev-diagnostic',
                  'snapshot_sha256': snapshot_item['sha256'], 'passed': True, 'model_calls': 0,
                  'physical_simulation': False, 'checks': {'original_metadata_check': True}, 'errors': {}}
        if schema == 'campaign002-codehost-channel-probe-3':
            result['cases'] = [{'case':'multi_channel','passed':True,'production_qualified':True,
                                'transport_proof':{'passed':True}}]
            result['cases'] += [{'case':name,'passed':True,'production_qualified':False,
                'transport_proof':{'schema':'campaign002-transport-expected-failure-3','case':name,
                    'expected_failure_verified':True,'diagnostic_only':True,'ordinary_transport_passed':False,
                    'model_calls':0,'physical_simulation':False}} for name in ('foreign_owner','in_flight_eof')]
        elif kind == 'transport_probe_diagnostic':
            result['cases'] = [{'kind': name, 'passed': True, 'cleanup_clean': True,
                                'h2': {'passed': True}, 'transport_integrity': {'passed': True}}
                               for name in ('normal', 'reset')]
        self.f.save(result_path, result)
        result_item = self.f.artifact(result_path, 'Original no-model diagnostic result')
        argv = [str(self.f.root / 'venv/Scripts/python.exe'), '-X', 'utf8', '-B',
                str(self.f.campaign / 'harness' / script), '--run-id', result['run_id'],
                '--framework-revision', 'dev-diagnostic', '--snapshot', str(snapshot),
                '--output', str(result_path.parent)]
        job = {**self.f.job, 'id': 'job-' + kind, 'state': 'succeeded', 'exit_status': 0,
               'argv': argv, 'cwd': str(self.f.root),
               'resolved_executable': argv[0]}
        self.f.save(queue_path, job)
        queue_item = self.f.artifact(queue_path, 'Official queue receipt')
        entry = {'run_id': result['run_id'], 'job_id': job['id'],
                 'queue': {key: queue_item[key] for key in ('path', 'sha256')},
                 'result': {key: result_item[key] for key in ('path', 'sha256')}}
        self.f.save(entry_path, entry)
        entry_item = self.f.artifact(entry_path, readiness_label)
        row = {'run_id': result['run_id'], 'revision': 'dev-diagnostic', 'status': 'passed',
               'attempt_kind': kind, 'validity': 'diagnostic_checks_passed', 'scorable': False,
               'task_outcome': 'unknown', 'model_calls': 0, 'queue': {'id': job['id']}, 'details': {},
               'reason': 'Separate synthetic metadata/transport prerequisite.',
               'artifacts': [queue_item, snapshot_item, result_item, entry_item],
               'diagnostic_contract': {'schema': 'campaign002-history-diagnostic-1', 'result_schema': schema,
                   'result': result_item, 'verified_readiness_entry': entry_item,
                   'physical_simulation': False, 'proof_scope': 'Synthetic no-model prerequisite only.'}}
        return row, result, job, entry

    def refresh(self, row, result=None, job=None, entry=None):
        entry_label = row['diagnostic_contract']['verified_readiness_entry']['label']
        for label, value in [('Original no-model diagnostic result', result), ('Official queue receipt', job),
                             (entry_label, entry)]:
            if value is None:
                continue
            index = next(i for i, item in enumerate(row['artifacts']) if item['label'] == label)
            path = Path(row['artifacts'][index]['path'])
            self.f.save(path, value)
            item = self.f.artifact(path, label)
            row['artifacts'][index] = item
            if label == 'Original no-model diagnostic result': row['diagnostic_contract']['result'] = item
            if label == entry_label: row['diagnostic_contract']['verified_readiness_entry'] = item
        if entry is None and (result is not None or job is not None):
            path = Path(row['diagnostic_contract']['verified_readiness_entry']['path'])
            entry = json.loads(path.read_bytes())
            for key, label in [('queue', 'Official queue receipt'), ('result', 'Original no-model diagnostic result')]:
                item = next(item for item in row['artifacts'] if item['label'] == label)
                entry[key] = {key: item[key] for key in ('path', 'sha256')}
            self.refresh(row, entry=entry)

    def test_both_schemas_remain_diagnostic_only_with_original_check_values(self):
        for kind in report.NO_MODEL_DIAGNOSTICS:
            with self.subTest(kind=kind):
                row, original, _, _ = self.fixture(kind)
                projected = report.qualification_row(row, self.f.output)
                self.assertIsNone(projected['assessment_schema'])
                self.assertFalse(projected['diagnostic_result']['qualification_claim'])
                self.assertEqual(projected['checks'], original['checks'])
                self.assertEqual(projected['task_outcome'], 'unknown')
                self.assertFalse(projected['scorable'])
                self.assertIsNone(projected['timing'])
                self.assertIsNone(projected['pilot_admission'])
                self.assertEqual(len(qa.no_model_diagnostic_guard(projected, self.f.output)), 4)

    def test_new_schemas_preserve_prerequisite_scope_and_three_distinct_cases(self):
        for kind,schema in [('raw_event_preflight_diagnostic','campaign002-raw-event-preflight-2'),
                            ('transport_probe_diagnostic','campaign002-codehost-channel-probe-3')]:
            with self.subTest(schema=schema):
                source,original,_,_=self.fixture(kind,schema)
                row=report.qualification_row(source,self.f.output)
                self.assertEqual(len(qa.no_model_diagnostic_guard(row,self.f.output)),4)
                self.assertFalse(row['diagnostic_result']['qualification_claim']);self.assertFalse(row['scorable'])
                self.assertIsNone(row['assessment_schema']);self.assertEqual(row['task_outcome'],'unknown')
                self.assertIsNone(report.latest_completed_qualifier([row]))
                if kind=='transport_probe_diagnostic':
                    cases=row['diagnostic_result']['transport_cases']
                    self.assertEqual([c['case'] for c in cases],['multi_channel','foreign_owner','in_flight_eof'])
                    self.assertEqual([c['production_qualified'] for c in cases],[True,False,False])
                    self.assertTrue(all(c['diagnostic_only'] and c['expected_failure_verified'] for c in cases[1:]))
                    self.assertTrue(all('production transport did not qualify' in c['scope'] for c in cases[1:]))

    def test_new_transport_rejects_missing_renamed_reordered_or_promoted_negatives(self):
        mutations=[lambda r:r['cases'].pop(),lambda r:r['cases'].reverse(),
            lambda r:r['cases'][1].update(case='reset'),lambda r:r['cases'][1].update(production_qualified=True),
            lambda r:r['cases'][1].update(production_qualified=0),lambda r:r['cases'][2].update(passed=1),
            lambda r:r['cases'][1]['transport_proof'].update(ordinary_transport_passed=True),
            lambda r:r['cases'][1]['transport_proof'].update(diagnostic_only=False),
            lambda r:r['cases'][2]['transport_proof'].update(expected_failure_verified=False),
            lambda r:r['cases'][2]['transport_proof'].update(case='foreign_owner'),
            lambda r:r['cases'][0].update(production_qualified=False)]
        for mutation in mutations:
            source,result,_,_=self.fixture('transport_probe_diagnostic','campaign002-codehost-channel-probe-3')
            mutation(result);self.refresh(source,result=result)
            with self.subTest(mutation=mutations.index(mutation)),self.assertRaises(ValueError):
                report.qualification_row(source,self.f.output)

    def test_new_schema_requires_its_exact_versioned_command(self):
        for kind,schema in [('raw_event_preflight_diagnostic','campaign002-raw-event-preflight-2'),
                            ('transport_probe_diagnostic','campaign002-codehost-channel-probe-3')]:
            source,_,job,_=self.fixture(kind,schema)
            job['argv'][4]=str(self.f.campaign/'harness'/report.NO_MODEL_DIAGNOSTICS[kind][1])
            self.refresh(source,job=job)
            with self.assertRaisesRegex(ValueError,'command/output/source'):report.qualification_row(source,self.f.output)

    def test_qa_independently_rejects_negative_case_projection_promotions(self):
        source,_,_,_=self.fixture('transport_probe_diagnostic','campaign002-codehost-channel-probe-3')
        original=report.qualification_row(source,self.f.output)
        for mutation in (lambda d:d.pop('transport_cases'),lambda d:d['transport_cases'].pop(),
                         lambda d:d['transport_cases'][1].update(production_qualified=True),
                         lambda d:d['transport_cases'][1].update(production_qualified=0),
                         lambda d:d['transport_cases'][1].update(diagnostic_only=False),
                         lambda d:d['transport_cases'][1].update(scope='Production pass')):
            row=copy.deepcopy(original);mutation(row['diagnostic_result'])
            with self.assertRaises(ValueError):qa.no_model_diagnostic_guard(row,self.f.output)

    def test_new_diagnostics_full_report_static_qa_preserves_failed_qualifier(self):
        rows=[self.f.row,self.fixture('raw_event_preflight_diagnostic','campaign002-raw-event-preflight-2')[0],
              self.fixture('transport_probe_diagnostic','campaign002-codehost-channel-probe-3')[0]]
        self.f.save(self.f.index,{'schema':'campaign002-qualification-history-1','attempts':rows,
            'current_status':{'schema':'campaign002-qualification-closeout-status-1','state':'qualification_in_progress',
                             'basis_run_id':self.f.run_id,'basis_assessment_sha256':self.f.row['artifacts'][1]['sha256']}})
        report.build(self.f.index,self.f.output,previous=self.f.prior,campaign=self.f.campaign)
        result=qa.verify(self.f.output)
        self.assertEqual(result['history_records'],3);self.assertEqual(result['scored_outcome_rows'],0)
        data=json.loads((self.f.output/'qualification-data.json').read_bytes())
        self.assertEqual(data['qualification_closeout']['basis_run_id'],self.f.run_id)
        self.assertFalse(data['history'][-1]['diagnostic_result']['transport_cases'][1]['production_qualified'])

    def test_result_types_and_schema_cannot_turn_truthy_values_into_passes(self):
        cases = [('schema', 'unrecognized-diagnostic'), ('passed', 1), ('passed', False),
                 ('model_calls', False), ('model_calls', 1), ('physical_simulation', 0),
                 ('checks', {'original_metadata_check': 1}), ('checks', {}), ('errors', {'failure': 'unknown'})]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                row, result, _, _ = self.fixture()
                result[key] = value
                self.refresh(row, result=result)
                with self.assertRaisesRegex(ValueError, 'strict source-bound pass'):
                    report.qualification_row(row, self.f.output)

    def test_contract_kind_pair_and_no_model_classification_are_closed(self):
        for key, value in [('attempt_kind', 'unknown'), ('model_calls', False), ('scorable', True),
                           ('task_outcome', 'success'), ('validity', 'valid')]:
            row, _, _, _ = self.fixture()
            row[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'contract/classification'):
                report.qualification_row(row, self.f.output)
        row, _, _, _ = self.fixture()
        row['diagnostic_contract']['result_schema'] = 'campaign002-codehost-probe-1'
        with self.assertRaisesRegex(ValueError, 'contract/classification'):
            report.qualification_row(row, self.f.output)

    def test_official_failure_gate_precedes_every_diagnostic_output_read(self):
        row, _, job, _ = self.fixture()
        job.update(state='failed', exit_status=1)
        self.refresh(row, job=job)
        with patch.object(report, 'consume', wraps=report.consume) as consume:
            with self.assertRaisesRegex(ValueError, 'integer exit0'):
                report.qualification_row(row, self.f.output)
        self.assertEqual(len(consume.call_args_list), 1)
        self.assertEqual(Path(consume.call_args.args[0]).name, 'official-status.json')

    def test_readiness_entry_cannot_substitute_another_run_or_result(self):
        for key, value in [('run_id', 'other'), ('job_id', 'foreign'),
                           ('result', {'path': 'foreign', 'sha256': '0' * 64})]:
            row, _, _, entry = self.fixture()
            entry[key] = value
            self.refresh(row, entry=entry)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'readiness entry identity'):
                report.qualification_row(row, self.f.output)

    def test_direct_dispatch_output_snapshot_and_revision_are_bound(self):
        row, result, job, _ = self.fixture()
        job['argv'][-1] = str(self.f.root / 'foreign-output')
        self.refresh(row, job=job)
        with self.assertRaisesRegex(ValueError, 'command/output/source'):
            report.qualification_row(row, self.f.output)
        row, result, _, _ = self.fixture()
        result['snapshot_sha256'] = '0' * 64
        self.refresh(row, result=result)
        with self.assertRaisesRegex(ValueError, 'strict source-bound pass'):
            report.qualification_row(row, self.f.output)

    def test_transport_requires_two_typed_original_case_passes(self):
        for change in ('missing', 'truthy', 'cleanup', 'h2', 'transport'):
            row, result, _, _ = self.fixture('transport_probe_diagnostic')
            if change == 'missing': result['cases'].pop()
            elif change == 'truthy': result['cases'][1]['passed'] = 1
            elif change == 'cleanup': result['cases'][1]['cleanup_clean'] = False
            else: result['cases'][1]['h2' if change == 'h2' else 'transport_integrity']['passed'] = False
            self.refresh(row, result=result)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'both original passing cases'):
                report.qualification_row(row, self.f.output)

    def test_diagnostic_passes_do_not_advance_latest_qualifier_or_replace_old_failure(self):
        previous = report.qualification_row(self.f.row, self.f.output)
        source_rows = [self.f.row]
        rows = [previous]
        for kind in report.NO_MODEL_DIAGNOSTICS:
            source, _, _, _ = self.fixture(kind)
            source_rows.append(source)
            rows.append(report.qualification_row(source, self.f.output))
        self.assertIs(report.latest_completed_qualifier(rows), previous)
        self.assertIs(qa.latest_completed_qualifier(rows), previous)
        status = {'schema': 'campaign002-qualification-closeout-status-1', 'state': 'qualification_in_progress',
                  'basis_run_id': previous['run_id'], 'basis_assessment_sha256': self.f.row['artifacts'][1]['sha256']}
        detail = report.current_status_detail(status, rows, {'attempts': source_rows}, {'entries': []}, self.f.campaign, self.f.output)
        self.assertEqual(detail['basis_run_id'], previous['run_id'])
        self.assertEqual(previous, report.qualification_row(self.f.row, self.f.output))
        status.update(basis_run_id=rows[-1]['run_id'], basis_assessment_sha256=rows[-1]['diagnostic_result']['result_sha256'])
        with self.assertRaisesRegex(ValueError, 'original failed assessment or completed latest qualifier'):
            report.current_status_detail(status, rows, {'attempts': source_rows}, {'entries': []}, self.f.campaign, self.f.output)

    def test_qa_rejects_qualifier_timing_or_truthy_projection(self):
        source, _, _, _ = self.fixture()
        original = report.qualification_row(source, self.f.output)
        mutations = [lambda row: row['diagnostic_result'].update(qualification_claim=True),
                     lambda row: row.pop('diagnostic_result'),
                     lambda row: row.update(timing={'strict_passed': True}),
                     lambda row: row.update(assessment_schema='campaign002-native-assessment-1'),
                     lambda row: row['checks'].update(original_metadata_check=1)]
        for mutation in mutations:
            row = copy.deepcopy(original)
            mutation(row)
            with self.assertRaises(ValueError): qa.no_model_diagnostic_guard(row, self.f.output)

    def test_synthetic_companion_and_qa_keep_failed_qualifier_basis_after_diagnostics(self):
        rows = [self.f.row]
        rows.extend(self.fixture(kind)[0] for kind in report.NO_MODEL_DIAGNOSTICS)
        status = {'schema': 'campaign002-qualification-closeout-status-1', 'state': 'qualification_in_progress',
                  'basis_run_id': self.f.run_id, 'basis_assessment_sha256': self.f.row['artifacts'][1]['sha256']}
        self.f.save(self.f.index, {'schema': 'campaign002-qualification-history-1', 'attempts': rows,
                                  'current_status': status})
        report.build(self.f.index, self.f.output, previous=self.f.prior, campaign=self.f.campaign)
        verified = qa.verify(self.f.output)
        data = json.loads((self.f.output / 'qualification-data.json').read_bytes())
        self.assertEqual(verified['history_records'], 3)
        self.assertEqual(verified['scored_outcome_rows'], 0)
        self.assertEqual(data['qualification_closeout']['basis_run_id'], self.f.run_id)
        self.assertEqual(data['history'][0]['status'], 'failed')
        self.assertTrue(all(row['diagnostic_result']['qualification_claim'] is False for row in data['history'][1:]))

    def test_failed_queue_basis_also_ignores_later_explicit_diagnostic_pass(self):
        self.f.failed_queue_fixture()
        failed = report.qualification_row(self.f.row, self.f.output)
        source, _, _, _ = self.fixture()
        diagnostic = report.qualification_row(source, self.f.output)
        status = {'schema': 'campaign002-qualification-closeout-status-1', 'state': 'qualification_in_progress',
                  'basis_run_id': failed['run_id'], 'basis_queue_sha256': failed['queue_failure']['official_queue_sha256']}
        value = report.current_status_detail(status, [failed, diagnostic], {}, {'entries': []}, self.f.campaign, self.f.output)
        self.assertTrue(qa.failed_queue_closeout_guard(value, [failed, diagnostic]))

    def test_template_labels_prerequisites_and_static_javascript_passes(self):
        template = (report.HERE / 'qualification_template.html').read_text(encoding='utf-8')
        self.assertIn('diagnostic prerequisite only', template)
        self.assertIn('row.diagnostic_result.scope', template)
        self.assertIn('Boolean(f||p||row.diagnostic_result)', template)
        self.assertEqual(qa.static_html(template)['javascript_syntax'], 'passed')


if __name__ == '__main__':
    unittest.main()
