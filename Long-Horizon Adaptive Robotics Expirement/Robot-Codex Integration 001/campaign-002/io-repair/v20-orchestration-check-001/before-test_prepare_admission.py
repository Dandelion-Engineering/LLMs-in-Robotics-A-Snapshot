"""Metadata-only wrapper failure/immutability checks in temporary directories."""
import json
from contextlib import nullcontext
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import prepare_certificate as certificate
import prepare_index

REAL_VERIFIER = certificate.load_verifier()
with certificate.qualification_validator(certificate.CAMPAIGN / 'qualification/run_final_qualification_v19.py') as module:
    REAL_COORDINATOR = module
REAL_TRANSPORT_PROBE = REAL_COORDINATOR.verify_transport_probe
REAL_RAW_PREFLIGHT = REAL_COORDINATOR.verify_raw_preflight


class AdmissionFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.campaign = self.root / 'campaign-002'
        self.admission = self.campaign / 'admission'
        self.admission.mkdir(parents=True)
        self.snapshot = self.root / 'source/snapshot.json'
        self.index = self.root / 'index.json'
        self.candidate = self.root / 'candidate.json'
        self.plan = self.campaign / 'execution-plan.json'
        self.schedule = self.campaign / 'predeclared-v1/schedule.json'
        self.write(self.snapshot, {'revision': 'RCI001-C02-dev-test', 'sources': {}})
        self.write(self.index, {'schema': 'campaign002-qualification-index-1',
            'source_revision': 'RCI001-C02-dev-test', 'final_source_snapshot': certificate.identity(self.snapshot)})
        self.write(self.plan, {'schema': 'campaign002-execution-plan-1', 'campaign_id': 'RCI001-Campaign002',
            'framework_revision': 'RCI001-C02-dev-test', 'release_revision': 'RCI001-C02-frozen-001', 'attempts': []})
        for name, value in (('HERE', self.admission), ('CAMPAIGN', self.campaign), ('RCI', self.root), ('REPO', self.root)):
            context = patch.object(certificate, name, value)
            context.start(); self.addCleanup(context.stop)
        for path in certificate.artifact_paths(self.snapshot, self.index, self.schedule).values():
            if Path(path) != Path(certificate.__file__) and not Path(path).exists():
                self.write(Path(path), {'synthetic': True})
        self.verifier = SimpleNamespace(verify_certificate=Mock(), stamp=REAL_VERIFIER.stamp,
            verify_qualification_index=Mock(), base=SimpleNamespace(queue_gate=REAL_VERIFIER.base.queue_gate,
                read_json=REAL_VERIFIER.base.read_json, frozen_problems=Mock(return_value=[])))
        context = patch.object(certificate, 'load_verifier', return_value=self.verifier)
        context.start(); self.addCleanup(context.stop)

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')

    def prepare(self, **kwargs):
        return certificate.prepare(self.snapshot, self.index, self.candidate, **kwargs)


class WrapperTests(AdmissionFixture):
    def setUp(self):
        super().setUp()
        context = patch.object(certificate, 'verify_final_lineage', return_value={})
        context.start(); self.addCleanup(context.stop)

    def test_plan_and_index_must_bind_the_same_source_revision(self):
        for path, key in ((self.plan, 'framework_revision'), (self.index, 'source_revision')):
            with self.subTest(path=path):
                original = path.read_bytes()
                value = json.loads(original); value[key] = 'different'
                self.write(path, value)
                with self.assertRaisesRegex(ValueError, 'revision differs|bound to this final source'):
                    self.prepare()
                self.assertFalse(self.candidate.exists())
                self.verifier.verify_certificate.assert_not_called()
                path.write_bytes(original)

    def test_index_snapshot_bytes_cannot_be_substituted_even_at_same_revision(self):
        self.write(self.snapshot, {'revision': 'RCI001-C02-dev-test', 'sources': {'changed': True}})
        with self.assertRaisesRegex(ValueError, 'bound to this final source'):
            self.prepare()
        self.assertFalse(self.candidate.exists())

    def test_failed_independent_verification_retains_candidate_but_never_seals(self):
        self.verifier.verify_certificate.side_effect = ValueError('synthetic failed qualification')
        with self.assertRaisesRegex(ValueError, 'failed qualification'):
            self.prepare()
        self.assertTrue(self.candidate.exists())
        original = self.candidate.read_bytes()
        self.assertFalse((self.admission / 'sealed-v1').exists())
        self.assertFalse((self.admission / 'sealed-v1.pending').exists())
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertEqual(self.candidate.read_bytes(), original)

    def test_candidate_only_binds_coordinator_plan_and_distinct_release_identity(self):
        result = self.prepare(candidate_only=True)
        value = json.loads(self.candidate.read_bytes())
        self.assertFalse(result['sealed'])
        self.assertFalse((self.admission / 'sealed-v1').exists())
        self.assertEqual(value['source_revision'], 'RCI001-C02-dev-test')
        self.assertEqual(value['release_revision'], 'RCI001-C02-frozen-001')
        self.assertEqual(value['artifacts']['campaign_coordinator'], certificate.identity(self.campaign / 'run_campaign.py'))
        self.assertEqual(value['artifacts']['execution_plan'], certificate.identity(self.plan))
        self.verifier.verify_certificate.assert_called_once_with(self.candidate, result['certificate_sha256'])

    def test_candidate_binds_all_repairs_and_preserved_failed_diagnoses(self):
        self.prepare(candidate_only=True)
        value=json.loads(self.candidate.read_bytes())
        for key,relative in (
            ('qualification_coordinator','qualification/run_final_qualification_v19.py'),
            ('qualification_readiness','qualification/final-qualification-019-readiness.json'),
            ('qualification_completion','qualification/final-qualification-019/completed.json'),
            ('channel_startup_repair_method','io-repair/CHANNEL_TRANSPORT_STARTUP_REPAIR_V1.md'),
            ('channel_startup_failure_diagnosis','io-repair/raw-preflight-002-failure-analysis.json'),
            ('channel_probe_process_identity_method','io-repair/CHANNEL_PROBE_PROCESS_IDENTITY_V1.md'),
            ('channel_probe_process_identity_diagnosis','io-repair/transport-probe-006-failure-analysis.json'),
            ('channel_finish_frontier_method','io-repair/CHANNEL_FINISH_FRONTIER_VALIDATION_V1.md'),
            ('channel_finish_frontier_failure_diagnosis','io-repair/transport-probe-007-failure-analysis.json'),
            ('channel_probe_sequence_method','io-repair/CHANNEL_PROBE_SEQUENCE_SYNCHRONIZATION_V1.md'),
            ('channel_probe_sequence_failure_diagnosis','io-repair/transport-probe-008-failure-analysis.json'),
            ('channel_owner_drain_method','io-repair/CHANNEL_OWNER_DRAIN_V1.md'),
            ('channel_owner_drain_failure_diagnosis','io-repair/smoke-014-shutdown-failure-analysis.json'),
            ('channel_probe_shutdown_accounting_diagnosis','io-repair/transport-probe-010-failure-analysis.json'),
            ('native_thread_quiescence_method','io-repair/NATIVE_THREAD_QUIESCENCE_V1.md'),
            ('native_thread_quiescence_diagnosis','io-repair/shutdown-diagnostic-001-failure-analysis.json')):
            with self.subTest(key=key):
                self.assertEqual(value['artifacts'][key],certificate.identity(self.campaign/relative))

    def test_missing_repair_declaration_or_failed_diagnosis_prevents_candidate(self):
        for relative in ('io-repair/CHANNEL_TRANSPORT_STARTUP_REPAIR_V1.md',
                         'io-repair/raw-preflight-002-failure-analysis.json',
                         'io-repair/CHANNEL_PROBE_PROCESS_IDENTITY_V1.md',
                         'io-repair/transport-probe-006-failure-analysis.json',
                         'io-repair/CHANNEL_FINISH_FRONTIER_VALIDATION_V1.md',
                         'io-repair/transport-probe-007-failure-analysis.json',
                         'io-repair/CHANNEL_PROBE_SEQUENCE_SYNCHRONIZATION_V1.md',
                         'io-repair/transport-probe-008-failure-analysis.json',
                         'io-repair/CHANNEL_OWNER_DRAIN_V1.md',
                         'io-repair/smoke-014-shutdown-failure-analysis.json',
                         'io-repair/transport-probe-010-failure-analysis.json',
                         'io-repair/NATIVE_THREAD_QUIESCENCE_V1.md',
                         'io-repair/shutdown-diagnostic-001-failure-analysis.json'):
            with self.subTest(relative=relative):
                path=self.campaign/relative;raw=path.read_bytes();path.unlink()
                with self.assertRaises(FileNotFoundError):self.prepare(candidate_only=True)
                self.assertFalse(self.candidate.exists())
                self.verifier.verify_certificate.assert_not_called()
                path.write_bytes(raw)

    def test_complete_publish_is_immutable_and_contains_exact_candidate_bytes(self):
        result = self.prepare()
        final = self.admission / 'sealed-v1'
        self.assertTrue(result['sealed'])
        self.assertEqual((final / 'certificate.json').read_bytes(), self.candidate.read_bytes())
        self.assertEqual(json.loads((final / 'seal.json').read_bytes())['certificate_sha256'], result['certificate_sha256'])
        self.assertFalse((self.admission / 'sealed-v1.pending').exists())
        with self.assertRaisesRegex(ValueError, 'immutable'):
            certificate.prepare(self.snapshot, self.index, self.root / 'another-candidate.json')

    def test_interrupted_pair_write_never_exposes_partial_final_seal(self):
        original = certificate.save
        def interrupted(path, raw):
            if Path(path).name == 'seal.json':
                raise OSError('synthetic interruption')
            original(path, raw)
        with patch.object(certificate, 'save', side_effect=interrupted):
            with self.assertRaisesRegex(OSError, 'synthetic interruption'):
                self.prepare()
        self.assertFalse((self.admission / 'sealed-v1').exists())
        pending = self.admission / 'sealed-v1.pending/certificate.json'
        self.assertEqual(pending.read_bytes(), self.candidate.read_bytes())
        with self.assertRaisesRegex(ValueError, 'pending seal is immutable'):
            certificate.prepare(self.snapshot, self.index, self.root / 'another-candidate.json')

    def index_inputs(self):
        inputs = {}
        for i, name in enumerate(('native', 'boundary', 'smoke', 'pilot_stock', 'pilot_home'), 1):
            folder = self.root / name
            paths = [folder / filename for filename in ('manifest.json', 'snapshot.json', 'queue.json', 'assessment.json', 'evidence')]
            for path in paths[:4]:
                self.write(path, {})
            self.write(paths[2], {'id': 'job-' + str(i), 'state': 'succeeded', 'exit_status': 0})
            if i >= 3:
                paths.append(folder / 'host')
            inputs[name] = paths
        self.write(self.campaign / 'qualification/assess_native.py', {'synthetic': True})
        return inputs

    def test_every_queue_passes_before_any_assessment_is_even_hashed(self):
        inputs = self.index_inputs()
        self.write(inputs['pilot_home'][2], {'id': 'job-5', 'state': 'running', 'exit_status': None})
        assessments = {paths[3].resolve() for paths in inputs.values()}
        original = certificate.identity
        def forbid_outcome(path):
            self.assertNotIn(Path(path).resolve(), assessments, 'Incomplete queue allowed an outcome read')
            return original(path)
        with patch.object(certificate, 'identity', side_effect=forbid_outcome):
            with self.assertRaisesRegex(ValueError, 'Official queue'):
                prepare_index.build(self.snapshot, self.root / 'built-index.json', **inputs)
        self.verifier.verify_qualification_index.assert_not_called()

    def test_index_requires_full_qualification_and_writes_once(self):
        inputs = self.index_inputs()
        output = self.root / 'built-index.json'
        self.verifier.verify_qualification_index.side_effect = ValueError('synthetic strict timing failure')
        with self.assertRaisesRegex(ValueError, 'strict timing failure'):
            prepare_index.build(self.snapshot, output, **inputs)
        self.assertFalse(output.exists())
        self.verifier.verify_qualification_index.side_effect = None
        prepare_index.build(self.snapshot, output, **inputs)
        value = json.loads(output.read_bytes())
        self.assertEqual(value['final_source_snapshot'], certificate.identity(self.snapshot))
        self.assertEqual([row['family'] for row in value['pilots']], ['misplaced-stock', 'blocked-insert-home'])
        self.assertEqual(value['native']['queue'], certificate.identity(inputs['native'][2]))
        original = output.read_bytes()
        with self.assertRaises(FileExistsError):
            prepare_index.build(self.snapshot, output, **inputs)
        self.assertEqual(output.read_bytes(), original)

    def test_one_job_cannot_stand_for_two_qualification_stages(self):
        inputs = self.index_inputs()
        self.write(inputs['pilot_home'][2], {'id': 'job-4', 'state': 'succeeded', 'exit_status': 0})
        with self.assertRaisesRegex(ValueError, 'five distinct official jobs'):
            prepare_index.build(self.snapshot, self.root / 'built-index.json', **inputs)
        self.verifier.verify_qualification_index.assert_not_called()


class FinalLineageTests(AdmissionFixture):
    def setUp(self):
        super().setUp()
        self.qualification = self.campaign / 'qualification'
        self.ledger = self.qualification / 'final-qualification-019'
        self.map = self.root / 'map'
        self.raw = self.root / 'raw'
        self.snapshot = self.map / 'releases/RCI001-C02-dev-059/snapshot.json'
        self.anchor = self.map / 'releases/RCI001-C02-dev-056/snapshot.json'
        self.write(self.snapshot, {'revision': 'RCI001-C02-dev-059', 'sources': {}})
        self.write(self.snapshot.with_name('code.zip'), {'synthetic': True})
        self.write(self.anchor, {'revision': 'RCI001-C02-dev-056', 'sources': {}})
        plan = json.loads(self.plan.read_bytes()); plan['framework_revision'] = 'RCI001-C02-dev-059'
        self.write(self.plan, plan)
        for name, value in (('HERE', self.qualification), ('CAMPAIGN', self.campaign), ('RCI', self.root),
                            ('REPO', self.root), ('LEDGER', self.ledger), ('MAP', self.map), ('RAW', self.raw),
                            ('PYTHON', self.root / 'venv/Scripts/python.exe')):
            context = patch.object(REAL_COORDINATOR, name, value)
            context.start(); self.addCleanup(context.stop)
        context = patch.object(certificate, 'qualification_validator', side_effect=lambda path: nullcontext(REAL_COORDINATOR))
        context.start(); self.addCleanup(context.stop)
        context = patch.object(REAL_COORDINATOR, 'assert_sources', return_value={'synthetic-core': {}})
        self.source_check = context.start(); self.addCleanup(context.stop)
        context = patch.object(REAL_COORDINATOR, 'verify_transport_probe', return_value={'passed': True})
        self.probe_check = context.start(); self.addCleanup(context.stop)
        context = patch.object(REAL_COORDINATOR, 'verify_raw_preflight', return_value={'passed': True})
        self.raw_check = context.start(); self.addCleanup(context.stop)
        self.stages = [list(row[:2]) + [revision, row[2]] for row, revision in zip(
            REAL_COORDINATOR.STAGE_IDENTITIES,
            ['RCI001-C02-dev-057', 'RCI001-C02-dev-058'] + ['RCI001-C02-dev-059'] * 3)]
        self.paths = certificate.artifact_paths(self.snapshot, self.index, self.schedule)
        self.readiness = {'schema': REAL_COORDINATOR.READINESS_SCHEMA, 'ledger_directory': str(self.ledger),
            'source_snapshot': certificate.identity(self.anchor), 'stages': self.stages,
            'diagnostic': {'run_id': 'RCI001-C02-host-probe-019', 'job_id': 'host-job'},
            'repair_test_receipt': {'path': 'synthetic-repair-receipt', 'sha256': '1' * 64},
            'transport_diagnostic': {'run_id': 'RCI001-C02-transport-probe-012', 'job_id': 'transport-job'},
            'raw_event_preflight': {'run_id': 'RCI001-C02-raw-preflight-009', 'job_id': 'raw-job'}}
        self.write(self.paths['qualification_readiness'], self.readiness)
        self.preflight = {'schema': 'campaign002-final-qualification-preflight-1',
            'coordinator': certificate.identity(self.paths['qualification_coordinator']),
            'readiness': certificate.identity(self.paths['qualification_readiness']),
            'readiness_sha256': certificate.identity(self.paths['qualification_readiness'])['sha256'],
            **{key: self.readiness[key] for key in ('source_snapshot', 'stages', 'diagnostic',
                                                   'repair_test_receipt', 'transport_diagnostic', 'raw_event_preflight')}}
        self.write(self.paths['qualification_preflight'], self.preflight)
        self.entries = []
        for name, kind, revision, seed in self.stages:
            expected = REAL_COORDINATOR.entry_for(name, kind, revision)
            self.write(expected['manifest'], {'run_id': expected['run_id'], 'framework_revision': revision,
                                              'noise_seed': seed})
            if not expected['snapshot'].exists():
                self.write(expected['snapshot'], {'revision': revision, 'sources': {}})
            for key in ('queue', 'assessment'):
                self.write(expected[key], {'synthetic': key})
            entry = {key: certificate.identity(expected[key]) for key in ('manifest', 'snapshot', 'queue', 'assessment')}
            entry['evidence'] = str(expected['evidence'])
            if kind == 'native':
                entry['assessor'] = certificate.identity(self.qualification / 'assess_native.py') if (
                    self.qualification / 'assess_native.py').exists() else {'path': str(self.qualification / 'assess_native.py'),
                                                                          'sha256': '2' * 64}
            if kind not in ('native', 'boundary'):
                entry['host_evidence'] = str(expected['host'])
            if kind in ('stock', 'home'):
                entry['family'] = {'stock': 'misplaced-stock', 'home': 'blocked-insert-home'}[kind]
            self.entries.append(entry)
        self.completed = {'schema': 'campaign002-final-qualification-completed-1',
            'native': self.entries[0], 'boundary': self.entries[1], 'smoke': self.entries[2], 'pilots': self.entries[3:]}
        self.persist_entries()

    def persist_entries(self):
        self.write(self.paths['qualification_completion'], self.completed)
        self.index_value = {'schema': 'campaign002-qualification-index-1', 'source_revision': 'RCI001-C02-dev-059',
            'final_source_snapshot': certificate.identity(self.snapshot),
            **{key: self.completed[key] for key in ('native', 'boundary', 'smoke', 'pilots')}}
        self.write(self.index, self.index_value)

    def persist_readiness(self):
        self.write(self.paths['qualification_readiness'], self.readiness)
        self.preflight.update(readiness=certificate.identity(self.paths['qualification_readiness']),
            readiness_sha256=certificate.identity(self.paths['qualification_readiness'])['sha256'])
        for key in ('source_snapshot', 'stages', 'diagnostic', 'repair_test_receipt', 'transport_diagnostic',
                    'raw_event_preflight'):
            self.preflight[key] = self.readiness[key]
        self.write(self.paths['qualification_preflight'], self.preflight)

    def assert_before_mutation(self, pattern):
        approval = self.admission / 'approval-source.md'
        approval.unlink(missing_ok=True)
        with patch.object(certificate, 'save', side_effect=AssertionError('Unexpected write before lineage check')):
            with self.assertRaisesRegex((ValueError, FileNotFoundError), pattern):
                self.prepare(candidate_only=True)
        self.assertFalse(self.candidate.exists())
        self.assertFalse(approval.exists())
        self.assertFalse((self.admission / 'sealed-v1').exists())
        self.assertFalse((self.admission / 'sealed-v1.pending').exists())
        self.verifier.verify_certificate.assert_not_called()

    def test_valid_lineage_reuses_validators_and_binds_preflight(self):
        result = self.prepare(candidate_only=True)
        self.assertFalse(result['sealed'])
        self.source_check.assert_called_once_with(self.readiness, self.snapshot)
        self.probe_check.assert_called_once_with(self.readiness['transport_diagnostic'], self.anchor)
        self.raw_check.assert_called_once_with(self.readiness['raw_event_preflight'], self.anchor)
        artifacts = json.loads(self.candidate.read_bytes())['artifacts']
        for key in ('qualification_coordinator', 'qualification_readiness', 'qualification_preflight',
                    'qualification_completion', 'qualification_index', 'conventional_admission_method',
                    'conventional_admission_diagnosis', 'conventional_admission_diagnosis_report',
                    'raw_tool_result_method', 'raw_event_runtime_parity', 'startup_output_delivery_diagnosis',
                    'startup_output_delivery_diagnosis_report', 'prepared_tool_result_native_analysis',
                    'prepared_tool_result_native_analysis_report'):
            self.assertEqual(artifacts[key], certificate.identity(self.paths[key]))
        self.verifier.verify_certificate.assert_called_once()

    def test_missing_lineage_record_cannot_create_candidate_or_approval(self):
        for key in ('qualification_preflight', 'qualification_completion', 'qualification_readiness'):
            with self.subTest(key=key):
                path = self.paths[key]; original = path.read_bytes(); path.unlink()
                try:
                    self.assert_before_mutation('No such file|cannot find')
                finally:
                    path.write_bytes(original)

    def test_mutated_readiness_or_coordinator_fails_preflight_binding(self):
        for key in ('qualification_readiness', 'qualification_coordinator'):
            with self.subTest(key=key):
                path = self.paths[key]; original = path.read_bytes(); path.write_bytes(original + b'\n')
                try:
                    self.assert_before_mutation('exact coordinator and readiness')
                finally:
                    path.write_bytes(original)

    def test_changed_preflight_fields_and_missing_transport_are_rejected(self):
        for key in ('source_snapshot', 'stages', 'diagnostic', 'repair_test_receipt', 'transport_diagnostic',
                    'raw_event_preflight'):
            with self.subTest(key=key):
                value = dict(self.preflight); value.pop(key)
                self.write(self.paths['qualification_preflight'], value)
                self.assert_before_mutation('declared readiness: ' + key)
        self.write(self.paths['qualification_preflight'], self.preflight)

    def test_wrong_preflight_readiness_digest_is_rejected(self):
        self.preflight['readiness_sha256'] = '0' * 64
        self.write(self.paths['qualification_preflight'], self.preflight)
        self.assert_before_mutation('exact coordinator and readiness')

    def test_completion_and_index_must_match_exactly(self):
        value = json.loads(self.index.read_bytes()); value['native']['queue']['sha256'] = '3' * 64
        self.write(self.index, value)
        self.assert_before_mutation('exact ordered qualification index')

    def test_pilot_order_cannot_be_changed_even_in_both_records(self):
        self.completed['pilots'].reverse(); self.persist_entries()
        self.assert_before_mutation('stage path differs: pilot-stock-016')

    def test_incomplete_completed_pilot_pair_is_rejected(self):
        self.completed['pilots'].pop(); self.persist_entries()
        self.assert_before_mutation('exact ordered qualification index')

    def test_substituted_stage_path_cannot_be_laundered_through_both_records(self):
        for key in ('manifest', 'snapshot', 'queue', 'assessment'):
            with self.subTest(key=key):
                original = self.entries[0][key]['path']
                self.entries[0][key]['path'] = str(self.root / 'substitute' / Path(original).name)
                self.persist_entries()
                self.assert_before_mutation('stage path differs: native-018/' + key)
                self.entries[0][key]['path'] = original

    def test_stale_stage_names_and_seed_cannot_be_redeclared(self):
        for column, replacement in ((0, 'native-006'), (3, 24001)):
            with self.subTest(column=column):
                original = self.readiness['stages'][0][column]
                self.readiness['stages'][0][column] = replacement; self.persist_readiness()
                self.assert_before_mutation('Qualifier identities, order, families or seeds changed')
                self.readiness['stages'][0][column] = original

    def test_stage_manifest_identity_and_seed_must_match_declaration(self):
        for key, replacement in (('run_id', 'RCI001-C02-smoke-005'), ('framework_revision', 'RCI001-C02-dev-027'),
                                 ('noise_seed', 24102), ('noise_seed', True)):
            with self.subTest(key=key, replacement=replacement):
                path = Path(self.entries[2]['manifest']['path']); original = path.read_bytes()
                value = json.loads(original); value[key] = replacement; self.write(path, value)
                self.entries[2]['manifest'] = certificate.identity(path); self.persist_entries()
                self.assert_before_mutation('identity or revision differs|final source, seed or host differs')
                path.write_bytes(original); self.entries[2]['manifest'] = certificate.identity(path)

    def test_same_revision_different_final_snapshot_cannot_be_substituted(self):
        self.entries[2]['snapshot']['sha256'] = '4' * 64; self.persist_entries()
        self.assert_before_mutation('Artifact SHA256 mismatch')

    def test_source_or_probe_failure_never_writes_candidate_or_approval(self):
        for validator in (self.source_check, self.probe_check, self.raw_check):
            with self.subTest(validator=validator):
                validator.side_effect = ValueError('synthetic failed source/probe gate')
                try:
                    self.assert_before_mutation('failed source/probe gate')
                finally:
                    validator.side_effect = None

    def test_lineage_change_during_probe_replay_is_rejected(self):
        self.probe_check.side_effect = lambda *args: self.paths['qualification_completion'].write_text('{}', encoding='utf-8')
        self.assert_before_mutation('changed during pre-seal validation')

    def test_lineage_change_during_raw_preflight_replay_is_rejected(self):
        self.raw_check.side_effect = lambda *args: self.paths['qualification_completion'].write_text('{}', encoding='utf-8')
        self.assert_before_mutation('changed during pre-seal validation')

    def test_missing_readiness_raw_preflight_is_rejected_before_mutation(self):
        self.readiness.pop('raw_event_preflight')
        self.write(self.paths['qualification_readiness'], self.readiness)
        self.preflight.update(readiness=certificate.identity(self.paths['qualification_readiness']),
            readiness_sha256=certificate.identity(self.paths['qualification_readiness'])['sha256'])
        self.write(self.paths['qualification_preflight'], self.preflight)
        self.assert_before_mutation('declared readiness: raw_event_preflight')
        self.raw_check.assert_not_called()

    def test_mismatched_preflight_raw_binding_is_rejected_before_mutation(self):
        self.preflight['raw_event_preflight'] = {'run_id': 'RCI001-C02-raw-preflight-009', 'job_id': 'other-job'}
        self.write(self.paths['qualification_preflight'], self.preflight)
        self.assert_before_mutation('declared readiness: raw_event_preflight')
        self.raw_check.assert_not_called()

    def install_real_raw_preflight(self):
        output = self.campaign / 'io-repair/raw-preflight-009/evidence'
        record = self.readiness['raw_event_preflight']
        queue_path = self.root / 'raw-queue.json'
        script = self.campaign / 'harness/raw_event_preflight_v2.py'
        job = {'id': record['job_id'], 'state': 'succeeded', 'exit_status': 0,
            'argv': REAL_COORDINATOR.python(script, '--run-id', record['run_id'],
                '--framework-revision', 'RCI001-C02-dev-056', '--snapshot', self.anchor, '--output', output),
            'cwd': str(self.root), 'resolved_executable': str(REAL_COORDINATOR.PYTHON)}
        self.write(queue_path, job)
        result = {'schema': 'campaign002-raw-event-preflight-2', 'run_id': record['run_id'],
            'framework_revision': 'RCI001-C02-dev-056', 'snapshot_sha256': certificate.identity(self.anchor)['sha256'],
            'passed': True, 'model_calls': 0, 'physical_simulation': False}
        self.write(output / 'result.json', result)
        record.update(queue=certificate.identity(queue_path), result=certificate.identity(output / 'result.json'))
        self.persist_readiness()
        context = patch.object(REAL_COORDINATOR, 'verify_raw_preflight', side_effect=REAL_RAW_PREFLIGHT)
        context.start(); self.addCleanup(context.stop)
        context = patch.object(REAL_COORDINATOR, 'official', return_value=job)
        official = context.start(); self.addCleanup(context.stop)
        context = patch.object(REAL_COORDINATOR, 'replay_raw_preflight', return_value=dict(result))
        replay = context.start(); self.addCleanup(context.stop)
        return job, result, output, official, replay

    def test_real_raw_helper_authenticates_before_result_hash_or_read(self):
        job, _, output, _, replay = self.install_real_raw_preflight()
        (output / 'result.json').unlink()
        for state, status in (('running', None), ('succeeded', 1), ('succeeded', True)):
            with self.subTest(state=state, status=status):
                job.update(state=state, exit_status=status)
                self.assert_before_mutation('Official queue')
                replay.assert_not_called()

    def test_real_raw_helper_replays_exact_anchor_before_candidate_creation(self):
        _, _, output, official, replay = self.install_real_raw_preflight()
        self.prepare(candidate_only=True)
        official.assert_called_once_with('raw-job')
        replay.assert_called_once_with(self.campaign / 'harness/raw_event_preflight_v2.py', output, self.anchor)
        self.assertTrue(self.candidate.exists())

    def test_real_raw_helper_requires_exact_direct_official_command(self):
        job, _, output, _, replay = self.install_real_raw_preflight()
        job['argv'] = ['wrapper.exe', *job['argv']]
        queue_path = Path(self.readiness['raw_event_preflight']['queue']['path'])
        self.write(queue_path, job)
        self.readiness['raw_event_preflight']['queue'] = certificate.identity(queue_path)
        self.persist_readiness()
        (output / 'result.json').unlink()
        self.assert_before_mutation('official direct command changed')
        replay.assert_not_called()

    def test_real_raw_helper_rejects_official_receipt_mismatch(self):
        job, _, _, _, replay = self.install_real_raw_preflight()
        job['extra_official_metadata'] = 'changed'
        self.assert_before_mutation('queue receipt differs from official status')
        replay.assert_not_called()

    def test_real_raw_helper_rejects_changed_anchor_and_failed_independent_replay(self):
        _, result, output, _, replay = self.install_real_raw_preflight()
        result['snapshot_sha256'] = '6' * 64
        self.write(output / 'result.json', result)
        self.readiness['raw_event_preflight']['result'] = certificate.identity(output / 'result.json')
        self.persist_readiness()
        self.assert_before_mutation('exact anchor')
        replay.assert_not_called()
        result['snapshot_sha256'] = certificate.identity(self.anchor)['sha256']
        self.write(output / 'result.json', result)
        self.readiness['raw_event_preflight']['result'] = certificate.identity(output / 'result.json')
        self.persist_readiness(); replay.return_value = {'passed': False}
        self.assert_before_mutation('independent replay differs')

    def test_real_raw_helper_rejects_nonzero_model_count_and_physics(self):
        _, result, output, _, replay = self.install_real_raw_preflight()
        for key, replacement in (('model_calls', 1), ('model_calls', False), ('physical_simulation', True)):
            with self.subTest(key=key, replacement=replacement):
                original = result[key]; result[key] = replacement
                self.write(output / 'result.json', result)
                self.readiness['raw_event_preflight']['result'] = certificate.identity(output / 'result.json')
                self.persist_readiness()
                self.assert_before_mutation('exact anchor')
                replay.assert_not_called()
                result[key] = original

    def install_real_probe(self):
        output = self.campaign / 'io-repair/transport-probe-012/evidence'
        record = self.readiness['transport_diagnostic']
        queue_path = self.root / 'transport-queue.json'
        job = {'id': record['job_id'], 'state': 'succeeded', 'exit_status': 0,
            'argv': REAL_COORDINATOR.python(self.campaign / 'harness/codehost_transport_probe_v3.py', '--run-id', record['run_id'],
                '--framework-revision', 'RCI001-C02-dev-056', '--snapshot', self.anchor, '--output', output),
            'cwd': str(self.root), 'resolved_executable': str(REAL_COORDINATOR.PYTHON)}
        self.write(queue_path, job)
        result = {'schema': 'campaign002-codehost-channel-probe-3', 'run_id': record['run_id'],
            'framework_revision': 'RCI001-C02-dev-056', 'snapshot_sha256': certificate.identity(self.anchor)['sha256'],
            'passed': True, 'model_calls': 0, 'physical_simulation': False,
            'cases': [{'case': kind, 'evidence': str(output / kind), 'transport_integrity': {'passed': True}}
                      for kind in ('multi_channel', 'foreign_owner', 'in_flight_eof')]}
        self.write(output / 'result.json', result)
        record.update(queue=certificate.identity(queue_path), result=certificate.identity(output / 'result.json'))
        self.persist_readiness()
        context = patch.object(REAL_COORDINATOR, 'verify_transport_probe', side_effect=REAL_TRANSPORT_PROBE)
        context.start(); self.addCleanup(context.stop)
        context = patch.object(REAL_COORDINATOR, 'official', return_value=job)
        official = context.start(); self.addCleanup(context.stop)
        context = patch.object(REAL_COORDINATOR, 'replay_raw_preflight', return_value=dict(result))
        replay = context.start(); self.addCleanup(context.stop)
        return job, result, output, official, replay

    def test_real_probe_helper_authenticates_official_queue_before_outcome_read(self):
        job, _, output, _, replay = self.install_real_probe()
        (output / 'result.json').unlink()
        for state, status in (('running', None), ('succeeded', 1), ('succeeded', True)):
            with self.subTest(state=state, status=status):
                job.update(state=state, exit_status=status)
                self.assert_before_mutation('Official queue')
                replay.assert_not_called()

    def test_real_probe_helper_replays_three_case_result_before_candidate_creation(self):
        _, _, output, official, replay = self.install_real_probe()
        self.prepare(candidate_only=True)
        official.assert_called_once_with('transport-job')
        replay.assert_called_once_with(self.campaign / 'harness/codehost_transport_probe_v3.py', output, self.anchor)

    def test_real_probe_helper_rejects_changed_anchor_and_failed_independent_replay(self):
        _, result, output, _, replay = self.install_real_probe()
        result['snapshot_sha256'] = '5' * 64
        self.write(output / 'result.json', result)
        self.readiness['transport_diagnostic']['result'] = certificate.identity(output / 'result.json')
        self.persist_readiness()
        self.assert_before_mutation('exact anchor')
        replay.assert_not_called()
        result['snapshot_sha256'] = certificate.identity(self.anchor)['sha256']
        self.write(output / 'result.json', result)
        self.readiness['transport_diagnostic']['result'] = certificate.identity(output / 'result.json')
        self.persist_readiness(); replay.return_value = {'passed': False}
        self.assert_before_mutation('independent replay differs')


class ValidatorImportTests(unittest.TestCase):
    def test_coordinator_import_restores_sys_path_on_success_and_error(self):
        original = sys.path[:]
        path = certificate.CAMPAIGN / 'qualification/run_final_qualification_v19.py'
        with certificate.qualification_validator(path) as coordinator:
            self.assertTrue(callable(coordinator.load_readiness))
            self.assertTrue(callable(coordinator.assert_sources))
            self.assertTrue(callable(coordinator.verify_transport_probe))
            self.assertTrue(callable(coordinator.verify_raw_preflight))
        self.assertEqual(sys.path, original)
        with self.assertRaisesRegex(RuntimeError, 'synthetic'):
            with certificate.qualification_validator(path):
                raise RuntimeError('synthetic')
        self.assertEqual(sys.path, original)


if __name__ == '__main__':
    unittest.main()
