"""Bounded orchestration regressions; no queue submission, model or simulation."""
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('final_coordinator_v31', HERE / 'run_final_qualification_v31.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def save(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')
        return path

    def declaration(self):
        return {'schema': c.READINESS_SCHEMA, 'ledger_directory': str(c.LEDGER),
                'source_snapshot': {'path': str(self.root / 'snapshot.json'), 'sha256': 'a' * 64},
                'diagnostic': {'run_id': 'RCI001-C02-host-probe-031', 'job_id': 'fixed-job',
                    'manifest': {'path': str(self.root / 'manifest.json'), 'sha256': 'b' * 64},
                    'queue': {'path': str(self.root / 'queue.json'), 'sha256': 'c' * 64},
                    'assessment': {'path': str(self.root / 'assessment.json'), 'sha256': 'd' * 64},
                    'assessor': {'path': str(c.HERE / 'assess_host_probe.py'), 'sha256': 'e' * 64},
                    'evidence': str(c.RAW / 'RCI001-C02-host-probe-031')},
                'repair_test_receipt': {'path': str(self.root / 'tests.json'), 'sha256': 'f' * 64},
                'stages': [[name, kind, f'RCI001-C02-dev-{rev:03d}', seed]
                           for (name, kind, seed), rev in zip(c.STAGE_IDENTITIES, (104, 105, 106, 106, 106))]}

    def job(self, state='succeeded', status=0):
        return {'id': 'fixed-job', 'state': state, 'exit_status': status,
                'argv': ['fixed'], 'cwd': str(c.REPO), 'resolved_executable': str(c.PYTHON)}

    def load(self, value):
        path = self.save('readiness.json', value)
        return c.load_readiness(path, c.sha(path))

    def test_current_fresh_allocation_is_accepted_without_creating_outputs(self):
        value = self.declaration()
        self.assertEqual(self.load(value), value)
        self.assertEqual([p.name for p in self.root.iterdir()], ['readiness.json'])

    def test_pre_exit_method_is_required_before_runtime_validation(self):
        value=self.declaration()
        methods=[v for k,v in vars(c).items() if k.endswith('_METHOD')]
        sources={m.relative_to(c.REPO).as_posix():{'sha256':c.sha(m),'bytes':m.stat().st_size}
                 for m in methods if m!=c.PRE_EXIT_DRAIN_METHOD}
        path=self.save('releases/RCI001-C02-dev-103/snapshot.json',{'revision':'RCI001-C02-dev-103','sources':sources})
        value['source_snapshot']=c.identity(path)
        with patch.object(c,'MAP',self.root),patch.object(c.admission.base,'frozen_problems',return_value=[]),\
                patch.object(c.admission,'runtime_identities') as runtime:
            with self.assertRaisesRegex(ValueError,'native-pre-exit-drain declaration'):c.assert_sources(value)
            runtime.assert_not_called()

    def test_complete_reader_method_is_required_before_runtime_validation(self):
        value=self.declaration()
        methods=[v for k,v in vars(c).items() if k.endswith('_METHOD')]
        sources={m.relative_to(c.REPO).as_posix():{'sha256':c.sha(m),'bytes':m.stat().st_size}
                 for m in methods if m!=c.COMPLETE_READER_METHOD}
        path=self.save('releases/RCI001-C02-dev-103/snapshot.json',{'revision':'RCI001-C02-dev-103','sources':sources})
        value['source_snapshot']=c.identity(path)
        with patch.object(c,'MAP',self.root),patch.object(c.admission.base,'frozen_problems',return_value=[]),\
                patch.object(c.admission,'runtime_identities') as runtime:
            with self.assertRaisesRegex(ValueError,'complete-process/read declaration'):c.assert_sources(value)
            runtime.assert_not_called()

    def test_stopped_v30_identities_cannot_be_reused(self):
        value=self.declaration()
        value['stages']=[['native-029','native','RCI001-C02-dev-100',24000],
            ['boundary-030','boundary','RCI001-C02-dev-101',None],
            ['smoke-028','smoke','RCI001-C02-dev-102',24101],
            ['pilot-stock-027','stock','RCI001-C02-dev-102',24102],
            ['pilot-home-027','home','RCI001-C02-dev-102',24103]]
        with self.assertRaisesRegex(ValueError,'Qualifier identities'):self.load(value)

    def test_graceful_method_is_required_before_runtime_validation(self):
        value=self.declaration()
        methods=[v for k,v in vars(c).items() if k.endswith('_METHOD')]
        sources={m.relative_to(c.REPO).as_posix():{'sha256':c.sha(m),'bytes':m.stat().st_size}
                 for m in methods if m!=c.GRACEFUL_PROCESS_DRAIN_METHOD}
        path=self.save('releases/RCI001-C02-dev-103/snapshot.json',{'revision':'RCI001-C02-dev-103','sources':sources})
        value['source_snapshot']=c.identity(path)
        with patch.object(c,'MAP',self.root),patch.object(c.admission.base,'frozen_problems',return_value=[]),\
                patch.object(c.admission,'runtime_identities') as runtime:
            with self.assertRaisesRegex(ValueError,'graceful-process-drain declaration'):c.assert_sources(value)
            runtime.assert_not_called()

    def test_stopped_v29_identities_cannot_be_reused(self):
        value=self.declaration()
        value['stages']=[['native-028','native','RCI001-C02-dev-094',24000],
            ['boundary-029','boundary','RCI001-C02-dev-095',None],
            ['smoke-027','smoke','RCI001-C02-dev-096',24101],
            ['pilot-stock-026','stock','RCI001-C02-dev-096',24102],
            ['pilot-home-026','home','RCI001-C02-dev-096',24103]]
        with self.assertRaisesRegex(ValueError,'Qualifier identities'):self.load(value)

    def test_stopped_v28_identities_cannot_be_reused(self):
        value=self.declaration()
        value['stages']=[['native-027','native','RCI001-C02-dev-088',24000],
            ['boundary-028','boundary','RCI001-C02-dev-089',None],
            ['smoke-026','smoke','RCI001-C02-dev-090',24101],
            ['pilot-stock-025','stock','RCI001-C02-dev-090',24102],
            ['pilot-home-025','home','RCI001-C02-dev-090',24103]]
        with self.assertRaisesRegex(ValueError,'Qualifier identities'):self.load(value)

    def test_declared_v31_identity_and_seed_allocation_is_exact(self):
        self.assertEqual(c.LEDGER.name, 'final-qualification-031')
        plan = (c.CAMPAIGN / 'PLAN.md').read_text(encoding='utf-8')
        self.assertIn('sensor seeds 24001–24006', plan)
        self.assertIn('seeds 24101–24103', plan)
        self.assertEqual(c.STAGE_IDENTITIES, (
            ('native-030', 'native', 24000), ('boundary-031', 'boundary', None),
            ('smoke-029', 'smoke', 24101), ('pilot-stock-028', 'stock', 24102),
            ('pilot-home-028', 'home', 24103)))
        self.assertEqual([r[2] for r in self.declaration()['stages']],
                         ['RCI001-C02-dev-104', 'RCI001-C02-dev-105'] + ['RCI001-C02-dev-106'] * 3)

    def test_preserved_v16_allocation_cannot_be_reused(self):
        value=self.declaration()
        value['stages']=[['native-015','native','RCI001-C02-dev-047',24000],
                         ['boundary-016','boundary','RCI001-C02-dev-048',None],
                         ['smoke-014','smoke','RCI001-C02-dev-049',24101],
                         ['pilot-stock-013','stock','RCI001-C02-dev-049',24102],
                         ['pilot-home-013','home','RCI001-C02-dev-049',24103]]
        with self.assertRaisesRegex(ValueError,'Qualifier identities'):
            self.load(value)

    def test_preserved_v18_allocation_cannot_be_reused(self):
        value = self.declaration()
        value['stages'] = [['native-017', 'native', 'RCI001-C02-dev-052', 24000],
                           ['boundary-018', 'boundary', 'RCI001-C02-dev-053', None],
                           ['smoke-016', 'smoke', 'RCI001-C02-dev-054', 24101],
                           ['pilot-stock-015', 'stock', 'RCI001-C02-dev-054', 24102],
                           ['pilot-home-015', 'home', 'RCI001-C02-dev-054', 24103]]
        with self.assertRaisesRegex(ValueError, 'Qualifier identities'):
            self.load(value)

    def test_native_thread_quiescence_declaration_is_required_before_runtime_validation(self):
        for binding in (None, {'sha256': '0' * 64, 'bytes': 1}):
            with self.subTest(binding=binding):
                value = self.declaration()
                methods = (c.STARTUP_REPAIR_METHOD, c.PROCESS_IDENTITY_METHOD,
                           c.FINISH_FRONTIER_METHOD, c.SEQUENCE_SYNCHRONIZATION_METHOD,
                           c.OWNER_DRAIN_METHOD)
                sources = {method.relative_to(c.REPO).as_posix():
                           {'sha256': c.sha(method), 'bytes': method.stat().st_size}
                           for method in methods}
                name = c.NATIVE_THREAD_QUIESCENCE_METHOD.relative_to(c.REPO).as_posix()
                if binding is not None:
                    sources[name] = binding
                path = self.save('releases/RCI001-C02-dev-103/snapshot.json',
                                 {'revision': 'RCI001-C02-dev-103', 'sources': sources})
                value['source_snapshot'] = c.identity(path)
                with patch.object(c, 'MAP', self.root), \
                     patch.object(c.admission.base, 'frozen_problems', return_value=[]), \
                     patch.object(c.admission, 'runtime_identities') as runtime:
                    with self.assertRaisesRegex(ValueError, 'native-thread-quiescence declaration'):
                        c.assert_sources(value)
                    runtime.assert_not_called()

    def test_initial_read_declaration_is_required_before_runtime_validation(self):
        methods = [value for name, value in vars(c).items() if name.endswith('_METHOD')]
        for binding in (None, {'sha256': '0' * 64, 'bytes': 1}):
            with self.subTest(binding=binding):
                value = self.declaration()
                sources = {method.relative_to(c.REPO).as_posix():
                           {'sha256': c.sha(method), 'bytes': method.stat().st_size}
                           for method in methods if method != c.INITIAL_READ_EVIDENCE_METHOD}
                name = c.INITIAL_READ_EVIDENCE_METHOD.relative_to(c.REPO).as_posix()
                if binding is not None:
                    sources[name] = binding
                path = self.save('releases/RCI001-C02-dev-103/snapshot.json',
                                 {'revision': 'RCI001-C02-dev-103', 'sources': sources})
                value['source_snapshot'] = c.identity(path)
                with patch.object(c, 'MAP', self.root), \
                     patch.object(c.admission.base, 'frozen_problems', return_value=[]), \
                     patch.object(c.admission, 'runtime_identities') as runtime:
                    with self.assertRaisesRegex(ValueError, 'initial-read-evidence declaration'):
                        c.assert_sources(value)
                    runtime.assert_not_called()

    def test_prepared_startup_declaration_is_required_before_runtime_validation(self):
        methods = [value for name, value in vars(c).items() if name.endswith('_METHOD')]
        for binding in (None, {'sha256': '0' * 64, 'bytes': 1}):
            with self.subTest(binding=binding):
                value = self.declaration()
                sources = {method.relative_to(c.REPO).as_posix():
                           {'sha256': c.sha(method), 'bytes': method.stat().st_size}
                           for method in methods if method != c.PREPARED_STARTUP_SEGMENTS_METHOD}
                name = c.PREPARED_STARTUP_SEGMENTS_METHOD.relative_to(c.REPO).as_posix()
                if binding is not None:
                    sources[name] = binding
                path = self.save('releases/RCI001-C02-dev-103/snapshot.json',
                                 {'revision': 'RCI001-C02-dev-103', 'sources': sources})
                value['source_snapshot'] = c.identity(path)
                with patch.object(c, 'MAP', self.root), \
                     patch.object(c.admission.base, 'frozen_problems', return_value=[]), \
                     patch.object(c.admission, 'runtime_identities') as runtime:
                    with self.assertRaisesRegex(ValueError, 'prepared-startup-segments declaration'):
                        c.assert_sources(value)
                    runtime.assert_not_called()

    def test_preserved_v23_allocation_is_rejected(self):
        value = self.declaration()
        value['stages'] = [['native-022', 'native', 'RCI001-C02-dev-068', 24000],
                           ['boundary-023', 'boundary', 'RCI001-C02-dev-069', None],
                           ['smoke-021', 'smoke', 'RCI001-C02-dev-070', 24101],
                           ['pilot-stock-020', 'stock', 'RCI001-C02-dev-070', 24102],
                           ['pilot-home-020', 'home', 'RCI001-C02-dev-070', 24103]]
        with self.assertRaisesRegex(ValueError, 'Qualifier identities'):
            self.load(value)

    def test_preserved_v24_allocation_is_rejected(self):
        value = self.declaration()
        value['stages'] = [['native-023', 'native', 'RCI001-C02-dev-072', 24000],
                           ['boundary-024', 'boundary', 'RCI001-C02-dev-073', None],
                           ['smoke-022', 'smoke', 'RCI001-C02-dev-074', 24101],
                           ['pilot-stock-021', 'stock', 'RCI001-C02-dev-074', 24102],
                           ['pilot-home-021', 'home', 'RCI001-C02-dev-074', 24103]]
        with self.assertRaisesRegex(ValueError, 'Qualifier identities'):
            self.load(value)

    def test_changed_readiness_cannot_replace_external_trust_anchor(self):
        path = self.save('readiness.json', self.declaration())
        with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
            c.load_readiness(path, '0' * 64)

    def test_missing_or_malformed_caller_hash_is_rejected(self):
        for digest in (None, '', 'a', True, 'A' * 64):
            with self.subTest(digest=digest), patch.object(c, 'read') as reader:
                with self.assertRaisesRegex(ValueError, 'caller-held SHA256'):
                    c.load_readiness(self.root / 'readiness', digest)
                reader.assert_not_called()

    def test_fixed_stages_reject_reordering_seed_change_and_reused_revisions(self):
        for change in ('order', 'seed', 'old-run', 'revision', 'pilot-revision', 'extra', 'bool-seed'):
            value = self.declaration()
            if change == 'order': value['stages'][0], value['stages'][1] = value['stages'][1], value['stages'][0]
            elif change == 'seed': value['stages'][2][3] = 24104
            elif change == 'old-run': value['stages'][0][0] = 'native-003'
            elif change == 'revision': value['stages'][0][2] = 'RCI001-C02-dev-013'
            elif change == 'pilot-revision': value['stages'][4][2] = 'RCI001-C02-dev-019'
            elif change == 'extra': value['stages'].append(value['stages'][-1])
            else: value['stages'][0][3] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.load(value)

    def test_historical_probe_and_other_ledger_are_rejected(self):
        for field in ('probe', 'ledger'):
            value = self.declaration()
            if field == 'probe': value['diagnostic']['run_id'] = 'RCI001-C02-host-probe-006'
            else: value['ledger_directory'] = str(c.HERE / 'final-qualification-003')
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.load(value)

    def test_other_fresh_probe_or_increasing_revision_allocation_is_not_this_declaration(self):
        value = self.declaration()
        value['diagnostic']['run_id'] = 'RCI001-C02-host-probe-032'
        with self.assertRaisesRegex(ValueError, 'fresh repaired-host diagnostic'):
            self.load(value)
        value = self.declaration()
        for row, revision in zip(value['stages'], (40, 41, 42, 42, 42)):
            row[2] = f'RCI001-C02-dev-{revision:03d}'
        with self.assertRaisesRegex(ValueError, 'dev104, dev105 and shared final dev106'):
            self.load(value)

    def test_anchor_must_be_exact_dev103_before_runtime_source_validation(self):
        value = self.declaration()
        path = self.save('releases/RCI001-C02-dev-033/snapshot.json', {'revision': 'RCI001-C02-dev-033'})
        value['source_snapshot'] = c.identity(path)
        with patch.object(c, 'MAP', self.root), patch.object(c.admission, 'runtime_identities') as runtime:
            with self.assertRaisesRegex(ValueError, 'anchor must be dev103'):
                c.assert_sources(value)
            runtime.assert_not_called()

    def test_failed_official_queue_precedes_every_diagnostic_outcome_hash_or_read(self):
        for state, code in [('running', None), ('failed', 1), ('succeeded', False), ('succeeded', '0')]:
            with self.subTest(state=state, code=code), \
                 patch.object(c, 'load_readiness', return_value=self.declaration()), \
                 patch.object(c, 'official', return_value=self.job(state, code)), \
                 patch.object(c, 'read') as reader, patch.object(c.admission, 'artifact') as artifact, \
                 patch.object(c, 'assert_sources') as sources:
                with self.assertRaisesRegex(ValueError, 'Official queue'):
                    c.preflight(self.root / 'readiness', 'a' * 64)
                reader.assert_not_called()
                artifact.assert_not_called()
                sources.assert_not_called()

    def test_retained_queue_mismatch_stops_before_assessment(self):
        with patch.object(c, 'load_readiness', return_value=self.declaration()), \
             patch.object(c, 'official', return_value=self.job()), \
             patch.object(c.admission, 'artifact', side_effect=lambda item: Path(item['path'])) as artifact, \
             patch.object(c, 'read', return_value={}) as reader, patch.object(c, 'assert_sources') as sources:
            with self.assertRaisesRegex(ValueError, 'retained receipt'):
                c.preflight(self.root / 'readiness', 'a' * 64)
            reader.assert_called_once_with(self.root / 'queue.json')
            self.assertEqual(artifact.call_count, 1)
            sources.assert_not_called()

    def preflight_context(self, replayed=None, retained=None):
        value = self.declaration()
        result = {'schema': 'campaign002-host-probe-assessment-1', 'diagnostic_passed': True,
                  'errors': {}, 'run_id': value['diagnostic']['run_id'], 'queue_job_id': 'fixed-job',
                  'framework_revision': 'RCI001-C02-dev-103', 'model_calls': 0, 'scorable': False,
                  'timing': {'passed': True}}
        values = {self.root / 'queue.json': self.job(), self.root / 'snapshot.json': {'revision': 'RCI001-C02-dev-103'},
                  self.root / 'assessment.json': result if retained is None else retained}
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(c, 'load_readiness', return_value=value))
        stack.enter_context(patch.object(c, 'official', return_value=self.job()))
        stack.enter_context(patch.object(c.admission, 'artifact', side_effect=lambda item: Path(item['path'])))
        stack.enter_context(patch.object(c, 'read', side_effect=lambda path: values[Path(path)]))
        stack.enter_context(patch.object(c, 'assert_sources', return_value={'core': 'fixed'}))
        replay = stack.enter_context(patch.object(c, 'replay_diagnostic', return_value=result if replayed is None else replayed))
        timing = stack.enter_context(patch.object(c.admission, 'strict_timing_summary'))
        tests = stack.enter_context(patch.object(c, 'verify_repair_tests'))
        self.transport_probe = stack.enter_context(patch.object(c, 'verify_transport_probe'))
        self.raw_preflight = stack.enter_context(patch.object(c, 'verify_raw_preflight'))
        return value, result, replay, timing, tests

    def test_replay_and_strict_timing_required_before_passing_repair_tests(self):
        value, result, replay, timing, tests = self.preflight_context()
        self.assertEqual(c.preflight(self.root / 'readiness', 'a' * 64), (value, {'core': 'fixed'}))
        replay.assert_called_once()
        timing.assert_called_once_with(result['timing'], value['diagnostic']['run_id'])
        tests.assert_called_once_with(value['repair_test_receipt'], value)
        self.transport_probe.assert_called_once_with(None, self.root / 'snapshot.json')
        self.raw_preflight.assert_called_once_with(None, self.root / 'snapshot.json')

    def test_failed_raw_preflight_queue_precedes_outcome_access(self):
        for state, status in [('running', None), ('failed', 1), ('succeeded', False), ('succeeded', 0.0)]:
            with self.subTest(state=state, status=status), patch.object(c, 'official', return_value=self.job(state, status)), patch.object(c.admission, 'artifact') as artifact, patch.object(c, 'read') as read:
                with self.assertRaises(ValueError):
                    c.verify_raw_preflight({'run_id': 'RCI001-C02-raw-preflight-021', 'job_id': 'fixed-job'}, self.root / 'snapshot.json')
                artifact.assert_not_called()
                read.assert_not_called()

    def test_missing_or_wrong_raw_preflight_is_rejected_before_query(self):
        for record in (None, {}, {'run_id': 'RCI001-C02-raw-preflight-000'}):
            with self.subTest(record=record), patch.object(c, 'official') as official:
                with self.assertRaisesRegex(ValueError, 'fresh fixed no-model raw-event'):
                    c.verify_raw_preflight(record, self.root / 'snapshot.json')
                official.assert_not_called()

    def raw_probe_fixture(self, mutate_result=None, mutate_job=None):
        campaign = self.root / 'campaign-002'
        output = campaign / 'io-repair/raw-preflight-021/evidence'
        snapshot = self.save('raw-snapshot.json', {'revision': 'RCI001-C02-dev-103'})
        result = {'schema': 'campaign002-raw-event-preflight-2', 'passed': True,
                  'run_id': 'RCI001-C02-raw-preflight-021', 'framework_revision': 'RCI001-C02-dev-103',
                  'snapshot_sha256': c.sha(snapshot), 'model_calls': 0, 'physical_simulation': False,
                  'checks': {'synthetic': True}}
        if mutate_result: mutate_result(result)
        result_path = self.save('campaign-002/io-repair/raw-preflight-021/evidence/result.json', result)
        job = self.job()
        job['argv'] = c.python(campaign / 'harness/raw_event_preflight_v2.py', '--run-id', result['run_id'],
                               '--framework-revision', 'RCI001-C02-dev-103', '--snapshot', snapshot, '--output', output)
        if mutate_job: mutate_job(job)
        queue = self.save('raw-queue.json', job)
        record = {'run_id': 'RCI001-C02-raw-preflight-021', 'job_id': job['id'],
                  'queue': c.identity(queue), 'result': c.identity(result_path)}
        return campaign, output, snapshot, result, job, record

    def test_raw_preflight_requires_exact_independent_replay(self):
        campaign, output, snapshot, result, job, record = self.raw_probe_fixture()
        with patch.object(c, 'CAMPAIGN', campaign), patch.object(c, 'official', return_value=job), patch.object(c, 'replay_raw_preflight', return_value=result) as replay:
            self.assertEqual(c.verify_raw_preflight(record, snapshot), result)
            replay.assert_called_once_with(campaign / 'harness/raw_event_preflight_v2.py', output, snapshot)
        with patch.object(c, 'CAMPAIGN', campaign), patch.object(c, 'official', return_value=job), patch.object(c, 'replay_raw_preflight', return_value={**result, 'checks': {'synthetic': False}}):
            with self.assertRaisesRegex(ValueError, 'independent replay differs'):
                c.verify_raw_preflight(record, snapshot)

    def test_raw_preflight_rejects_model_flag_and_wrong_source_before_replay(self):
        for field, value in [('model_calls', False), ('model_calls', 1), ('physical_simulation', True),
                             ('snapshot_sha256', '0' * 64), ('passed', False)]:
            campaign, _, snapshot, _, job, record = self.raw_probe_fixture(lambda result: result.update({field: value}))
            with self.subTest(field=field, value=value), patch.object(c, 'CAMPAIGN', campaign), patch.object(c, 'official', return_value=job), patch.object(c, 'replay_raw_preflight') as replay:
                with self.assertRaisesRegex(ValueError, 'successful no-model check'):
                    c.verify_raw_preflight(record, snapshot)
                replay.assert_not_called()

    def test_raw_preflight_rejects_wrong_command_or_output(self):
        campaign, _, snapshot, _, job, record = self.raw_probe_fixture(mutate_job=lambda job: job['argv'].append('--run-bootstrap'))
        with patch.object(c, 'CAMPAIGN', campaign), patch.object(c, 'official', return_value=job), patch.object(c, 'replay_raw_preflight') as replay:
            with self.assertRaisesRegex(ValueError, 'direct command changed'):
                c.verify_raw_preflight(record, snapshot)
            replay.assert_not_called()
        campaign, _, snapshot, result, job, record = self.raw_probe_fixture()
        other = self.save('other-result.json', result)
        record['result'] = c.identity(other)
        with patch.object(c, 'CAMPAIGN', campaign), patch.object(c, 'official', return_value=job), patch.object(c, 'replay_raw_preflight') as replay:
            with self.assertRaisesRegex(ValueError, 'output outside declared path'):
                c.verify_raw_preflight(record, snapshot)
            replay.assert_not_called()

    def test_mismatched_retained_assessment_rejected_without_repair_tests(self):
        _, _, _, timing, tests = self.preflight_context(retained={'diagnostic_passed': True})
        with self.assertRaisesRegex(ValueError, 'independent replay'):
            c.preflight(self.root / 'readiness', 'a' * 64)
        timing.assert_not_called()
        tests.assert_not_called()

    def test_failed_diagnostic_cannot_be_promoted_by_readiness(self):
        value, result, _, timing, tests = self.preflight_context()
        result['diagnostic_passed'] = False
        with self.assertRaisesRegex(ValueError, 'did not pass'):
            c.preflight(self.root / 'readiness', 'a' * 64)
        timing.assert_not_called()
        tests.assert_not_called()

    def test_anchor_is_checked_against_original_source_inventory(self):
        value = self.declaration()
        sources = {method.relative_to(c.REPO).as_posix(): {'sha256': c.sha(method), 'bytes': method.stat().st_size}
                   for method in (c.STARTUP_REPAIR_METHOD,c.PROCESS_IDENTITY_METHOD,c.FINISH_FRONTIER_METHOD,c.SEQUENCE_SYNCHRONIZATION_METHOD,c.OWNER_DRAIN_METHOD, c.NATIVE_THREAD_QUIESCENCE_METHOD, c.NATIVE_THREAD_UNLOAD_SCHEDULING_METHOD, c.NORMAL_CLOSED_CANCEL_METHOD, c.NATIVE_CLEANUP_CANCELLATION_METHOD, c.INITIAL_READ_EVIDENCE_METHOD, c.PREPARED_STARTUP_SEGMENTS_METHOD, c.EPOCH_REVOCATION_INDEX_METHOD, c.CANARY_READBACK_EXCLUSIVITY_METHOD, c.PREPARED_INDEX_LABELS_METHOD, c.PILOT_RETIREMENT_INVENTORY_METHOD, c.PRE_EXIT_DRAIN_METHOD, c.GRACEFUL_PROCESS_DRAIN_METHOD)}
        path = self.save('releases/RCI001-C02-dev-103/snapshot.json', {'revision': 'RCI001-C02-dev-103', 'sources': sources})
        value['source_snapshot'] = c.identity(path)
        with patch.object(c, 'MAP', self.root), patch.object(c.admission.base, 'frozen_problems', return_value=[]), \
             patch.object(c.admission, 'runtime_identities', side_effect=ValueError('Original 624 omitted')) as runtime:
            with self.assertRaisesRegex(ValueError, 'Original 624 omitted'):
                c.assert_sources(value)
            runtime.assert_called_once()

    def test_startup_repair_declaration_missing_or_changed_stops_before_runtime_validation(self):
        for binding in (None, {'sha256':'0'*64,'bytes':1}):
            with self.subTest(binding=binding):
                value=self.declaration()
                name=c.STARTUP_REPAIR_METHOD.relative_to(c.REPO).as_posix()
                sources={} if binding is None else {name:binding}
                path=self.save('releases/RCI001-C02-dev-103/snapshot.json',
                               {'revision':'RCI001-C02-dev-103','sources':sources})
                value['source_snapshot']=c.identity(path)
                with patch.object(c,'MAP',self.root), patch.object(c.admission.base,'frozen_problems',return_value=[]), \
                     patch.object(c.admission,'runtime_identities') as runtime:
                    with self.assertRaisesRegex(ValueError,'startup-repair declaration'):
                        c.assert_sources(value)
                    runtime.assert_not_called()

    def test_process_identity_declaration_missing_or_changed_stops_before_runtime_validation(self):
        for binding in (None, {'sha256':'0'*64,'bytes':1}):
            with self.subTest(binding=binding):
                value=self.declaration()
                method=c.STARTUP_REPAIR_METHOD
                sources={method.relative_to(c.REPO).as_posix():{'sha256':c.sha(method),'bytes':method.stat().st_size}}
                name=c.PROCESS_IDENTITY_METHOD.relative_to(c.REPO).as_posix()
                if binding is not None:sources[name]=binding
                path=self.save('releases/RCI001-C02-dev-103/snapshot.json',
                               {'revision':'RCI001-C02-dev-103','sources':sources})
                value['source_snapshot']=c.identity(path)
                with patch.object(c,'MAP',self.root), patch.object(c.admission.base,'frozen_problems',return_value=[]), \
                     patch.object(c.admission,'runtime_identities') as runtime:
                    with self.assertRaisesRegex(ValueError,'process-identity declaration'):
                        c.assert_sources(value)
                    runtime.assert_not_called()

    def test_changed_anchor_bytes_rejected_before_source_read(self):
        with patch.object(c, 'read') as reader:
            value = self.declaration()
            self.save('snapshot.json', {})
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                c.assert_sources(value)
            reader.assert_not_called()

    def test_finish_frontier_declaration_is_required_before_runtime_validation(self):
        for binding in (None, {'sha256': '0' * 64, 'bytes': 1}):
            with self.subTest(binding=binding):
                value = self.declaration()
                sources = {method.relative_to(c.REPO).as_posix():
                           {'sha256': c.sha(method), 'bytes': method.stat().st_size}
                           for method in (c.STARTUP_REPAIR_METHOD, c.PROCESS_IDENTITY_METHOD)}
                name = c.FINISH_FRONTIER_METHOD.relative_to(c.REPO).as_posix()
                if binding is not None:
                    sources[name] = binding
                path = self.save('releases/RCI001-C02-dev-103/snapshot.json',
                                 {'revision': 'RCI001-C02-dev-103', 'sources': sources})
                value['source_snapshot'] = c.identity(path)
                with patch.object(c, 'MAP', self.root), \
                     patch.object(c.admission.base, 'frozen_problems', return_value=[]), \
                     patch.object(c.admission, 'runtime_identities') as runtime:
                    with self.assertRaisesRegex(ValueError, 'finish-frontier declaration'):
                        c.assert_sources(value)
                    runtime.assert_not_called()

    def test_sequence_synchronization_declaration_is_required_before_runtime_validation(self):
        for binding in (None, {'sha256': '0' * 64, 'bytes': 1}):
            with self.subTest(binding=binding):
                value = self.declaration()
                sources = {method.relative_to(c.REPO).as_posix():
                           {'sha256': c.sha(method), 'bytes': method.stat().st_size}
                           for method in (c.STARTUP_REPAIR_METHOD, c.PROCESS_IDENTITY_METHOD, c.FINISH_FRONTIER_METHOD)}
                name = c.SEQUENCE_SYNCHRONIZATION_METHOD.relative_to(c.REPO).as_posix()
                if binding is not None:
                    sources[name] = binding
                path = self.save('releases/RCI001-C02-dev-103/snapshot.json',
                                 {'revision': 'RCI001-C02-dev-103', 'sources': sources})
                value['source_snapshot'] = c.identity(path)
                with patch.object(c, 'MAP', self.root), \
                     patch.object(c.admission.base, 'frozen_problems', return_value=[]), \
                     patch.object(c.admission, 'runtime_identities') as runtime:
                    with self.assertRaisesRegex(ValueError, 'sequence-synchronization declaration'):
                        c.assert_sources(value)
                    runtime.assert_not_called()

    def test_owner_drain_declaration_is_required_before_runtime_validation(self):
        for binding in (None, {'sha256': '0' * 64, 'bytes': 1}):
            with self.subTest(binding=binding):
                value = self.declaration()
                sources = {method.relative_to(c.REPO).as_posix():
                           {'sha256': c.sha(method), 'bytes': method.stat().st_size}
                           for method in (c.STARTUP_REPAIR_METHOD, c.PROCESS_IDENTITY_METHOD, c.FINISH_FRONTIER_METHOD, c.SEQUENCE_SYNCHRONIZATION_METHOD)}
                name = c.OWNER_DRAIN_METHOD.relative_to(c.REPO).as_posix()
                if binding is not None:
                    sources[name] = binding
                path = self.save('releases/RCI001-C02-dev-103/snapshot.json',
                                 {'revision': 'RCI001-C02-dev-103', 'sources': sources})
                value['source_snapshot'] = c.identity(path)
                with patch.object(c, 'MAP', self.root), \
                     patch.object(c.admission.base, 'frozen_problems', return_value=[]), \
                     patch.object(c.admission, 'runtime_identities') as runtime:
                    with self.assertRaisesRegex(ValueError, 'owner-drain declaration'):
                        c.assert_sources(value)
                    runtime.assert_not_called()

    def test_stage_cannot_drop_or_change_the_new_method_from_shared_lineage(self):
        value = self.declaration()
        sources = {p.relative_to(c.REPO).as_posix(): {'sha256': 'a' * 64, 'bytes': 1}
                   for p in (c.CAMPAIGN / 'assessment').rglob('*.py')}
        for method in (c.STARTUP_REPAIR_METHOD, c.PROCESS_IDENTITY_METHOD, c.FINISH_FRONTIER_METHOD, c.SEQUENCE_SYNCHRONIZATION_METHOD, c.OWNER_DRAIN_METHOD, c.NATIVE_THREAD_QUIESCENCE_METHOD, c.NATIVE_THREAD_UNLOAD_SCHEDULING_METHOD, c.NORMAL_CLOSED_CANCEL_METHOD, c.NATIVE_CLEANUP_CANCELLATION_METHOD, c.INITIAL_READ_EVIDENCE_METHOD, c.PREPARED_STARTUP_SEGMENTS_METHOD, c.EPOCH_REVOCATION_INDEX_METHOD, c.CANARY_READBACK_EXCLUSIVITY_METHOD, c.PREPARED_INDEX_LABELS_METHOD, c.PILOT_RETIREMENT_INVENTORY_METHOD, c.PRE_EXIT_DRAIN_METHOD, c.GRACEFUL_PROCESS_DRAIN_METHOD):
            sources[method.relative_to(c.REPO).as_posix()] = {
                'sha256': c.sha(method), 'bytes': method.stat().st_size}
        anchor = self.save('releases/RCI001-C02-dev-103/snapshot.json',
                           {'revision': 'RCI001-C02-dev-103', 'sources': sources})
        value['source_snapshot'] = c.identity(anchor)
        name = c.NATIVE_THREAD_UNLOAD_SCHEDULING_METHOD.relative_to(c.REPO).as_posix()
        for missing in (False, True):
            changed = dict(sources)
            if missing:
                changed.pop(name)
            else:
                changed[name] = {'sha256': '0' * 64, 'bytes': 1}
            later = self.save('releases/RCI001-C02-dev-104/snapshot.json',
                              {'revision': 'RCI001-C02-dev-104', 'sources': changed})
            with self.subTest(missing=missing), patch.object(c, 'MAP', self.root), \
                 patch.object(c.admission.base, 'frozen_problems', return_value=[]), \
                 patch.object(c.admission, 'runtime_identities', return_value={}):
                with self.assertRaisesRegex(ValueError, 'runtime sources differ'):
                    c.assert_sources(value, later)

    def test_stage_cannot_drop_or_change_prepared_segments_method(self):
        value = self.declaration()
        sources = {p.relative_to(c.REPO).as_posix(): {'sha256': 'a' * 64, 'bytes': 1}
                   for p in (c.CAMPAIGN / 'assessment').rglob('*.py')}
        for method in (c.STARTUP_REPAIR_METHOD, c.PROCESS_IDENTITY_METHOD, c.FINISH_FRONTIER_METHOD, c.SEQUENCE_SYNCHRONIZATION_METHOD, c.OWNER_DRAIN_METHOD, c.NATIVE_THREAD_QUIESCENCE_METHOD, c.NATIVE_THREAD_UNLOAD_SCHEDULING_METHOD, c.NORMAL_CLOSED_CANCEL_METHOD, c.NATIVE_CLEANUP_CANCELLATION_METHOD, c.INITIAL_READ_EVIDENCE_METHOD, c.PREPARED_STARTUP_SEGMENTS_METHOD, c.EPOCH_REVOCATION_INDEX_METHOD, c.CANARY_READBACK_EXCLUSIVITY_METHOD, c.PREPARED_INDEX_LABELS_METHOD, c.PILOT_RETIREMENT_INVENTORY_METHOD, c.PRE_EXIT_DRAIN_METHOD, c.GRACEFUL_PROCESS_DRAIN_METHOD):
            sources[method.relative_to(c.REPO).as_posix()] = {
                'sha256': c.sha(method), 'bytes': method.stat().st_size}
        anchor = self.save('releases/RCI001-C02-dev-103/snapshot.json',
                           {'revision': 'RCI001-C02-dev-103', 'sources': sources})
        value['source_snapshot'] = c.identity(anchor)
        name = c.PREPARED_STARTUP_SEGMENTS_METHOD.relative_to(c.REPO).as_posix()
        for missing in (False, True):
            changed = dict(sources)
            if missing:
                changed.pop(name)
            else:
                changed[name] = {'sha256': '0' * 64, 'bytes': 1}
            later = self.save('releases/RCI001-C02-dev-104/snapshot.json',
                              {'revision': 'RCI001-C02-dev-104', 'sources': changed})
            with self.subTest(missing=missing), patch.object(c, 'MAP', self.root), \
                 patch.object(c.admission.base, 'frozen_problems', return_value=[]), \
                 patch.object(c.admission, 'runtime_identities', return_value={}):
                with self.assertRaisesRegex(ValueError, 'runtime sources differ'):
                    c.assert_sources(value, later)

    def native_prepare_fixture(self, mutation=None):
        name, kind, seed = c.STAGE_IDENTITIES[0]
        revision = 'RCI001-C02-dev-104'
        paths = c.entry_for(name, kind, revision)
        paths['manifest'] = self.root / ((mutation or 'valid') + '-native-manifest.json')
        paths['snapshot'] = self.root / 'release/snapshot.json'
        calls = []

        def command(folder, action, argv, **kwargs):
            calls.append(action)
            if action == 'prepare':
                self.assertEqual(Path(argv[4]), c.HERE / 'prepare_native.py')
                self.assertEqual(Path(argv[argv.index('--output') + 1]), paths['manifest'])
                self.assertEqual(argv[-2:], ['--seed-base', str(seed)])
                result = subprocess.run(argv, cwd=c.REPO, capture_output=True, text=True,
                                        encoding='utf-8')
                self.assertEqual(result.returncode, 0, result.stderr)
                value = c.read(paths['manifest'])
                if mutation == 'unapproved-seeds':
                    for slot, number in zip(value['slots'], range(25001, 25007)):
                        slot['manifest']['noise_seed'] = number
                elif mutation == 'reordered':
                    value['slots'][0], value['slots'][1] = value['slots'][1], value['slots'][0]
                elif mutation == 'bool-seed':
                    value['slots'][0]['manifest']['noise_seed'] = True
                elif mutation is not None:
                    raise AssertionError('Unknown fixture mutation')
                if mutation is not None:
                    paths['manifest'].write_text(json.dumps(value), encoding='utf-8')
            else:
                self.assertEqual(action, 'register')
                self.assertEqual(Path(argv[4]), c.CAMPAIGN / 'registry_session19.py')
                # No registry, freeze, queue or empirical work in this fixture.
            return {}

        return name, kind, seed, revision, paths, calls, command

    def test_native_stage_real_preparer_uses_declared_six_seeds(self):
        name, kind, seed, revision, paths, calls, command = self.native_prepare_fixture()
        with patch.object(c, 'command_once', side_effect=command), patch.object(c, 'assert_sources') as sources:
            value = c.prepare_stage(self.root, name, kind, revision, seed, paths, self.declaration())
        self.assertEqual([row['manifest']['noise_seed'] for row in value['slots']],
                         list(range(seed + 1, seed + 7)))
        self.assertEqual(calls, ['prepare', 'register'])
        self.assertFalse(paths['snapshot'].parent.exists())
        sources.assert_called_once_with(self.declaration(), paths['snapshot'])

    def test_native_stage_rejects_unapproved_reordered_or_boolean_prepared_seeds_before_registration(self):
        for mutation in ('unapproved-seeds', 'reordered', 'bool-seed'):
            with self.subTest(mutation=mutation):
                name, kind, seed, revision, paths, calls, command = self.native_prepare_fixture(mutation)
                with patch.object(c, 'command_once', side_effect=command), patch.object(c, 'assert_sources') as sources:
                    with self.assertRaisesRegex(ValueError, 'Prepared native seeds differ'):
                        c.prepare_stage(self.root, name, kind, revision, seed, paths, self.declaration())
                self.assertEqual(calls, ['prepare'])
                self.assertFalse(paths['snapshot'].parent.exists())
                sources.assert_not_called()

    def test_model_stage_uses_inventory_v19_with_unchanged_seed(self):
        name, kind, seed = c.STAGE_IDENTITIES[2]
        paths = c.entry_for(name, kind, 'RCI001-C02-dev-106')
        manifest = {'run_id': paths['run_id'], 'framework_revision': 'RCI001-C02-dev-106',
                    'seed': 173, 'noise_seed': seed}
        with patch.object(c, 'command_once') as command, patch.object(c, 'read', return_value=manifest), \
             patch.object(c, 'assert_sources'):
            self.assertEqual(c.prepare_stage(self.root, name, kind, 'RCI001-C02-dev-106', seed,
                                            paths, self.declaration()), manifest)
        prepare = command.call_args_list[0].args[2]
        self.assertEqual(Path(prepare[4]), c.HERE / 'prepare_model_v23.py')
        self.assertEqual(prepare[-4:], ['--kind', 'smoke', '--seed', '24101'])

    def test_later_qualifier_changed_source_cannot_share_repaired_lineage(self):
        value = self.declaration()
        source_names = [p.relative_to(c.REPO).as_posix() for p in (c.CAMPAIGN / 'assessment').rglob('*.py')]
        sources = {name: {'sha256': 'a' * 64, 'bytes': 1} for name in source_names}
        for method in (c.STARTUP_REPAIR_METHOD,c.PROCESS_IDENTITY_METHOD,c.FINISH_FRONTIER_METHOD,c.SEQUENCE_SYNCHRONIZATION_METHOD,c.OWNER_DRAIN_METHOD, c.NATIVE_THREAD_QUIESCENCE_METHOD, c.NATIVE_THREAD_UNLOAD_SCHEDULING_METHOD, c.NORMAL_CLOSED_CANCEL_METHOD, c.NATIVE_CLEANUP_CANCELLATION_METHOD, c.INITIAL_READ_EVIDENCE_METHOD, c.PREPARED_STARTUP_SEGMENTS_METHOD, c.EPOCH_REVOCATION_INDEX_METHOD, c.CANARY_READBACK_EXCLUSIVITY_METHOD, c.PREPARED_INDEX_LABELS_METHOD, c.PILOT_RETIREMENT_INVENTORY_METHOD, c.PRE_EXIT_DRAIN_METHOD, c.GRACEFUL_PROCESS_DRAIN_METHOD):
            sources[method.relative_to(c.REPO).as_posix()] = {'sha256':c.sha(method),'bytes':method.stat().st_size}
        runtime_name = (c.CAMPAIGN / 'harness/run_host.py').relative_to(c.REPO).as_posix()
        sources[runtime_name] = {'sha256': 'b' * 64, 'bytes': 1}
        path = self.save('releases/RCI001-C02-dev-103/snapshot.json',
                         {'revision': 'RCI001-C02-dev-103', 'sources': sources})
        value['source_snapshot'] = c.identity(path)
        changed = dict(sources)
        changed[runtime_name] = {'sha256': 'c' * 64, 'bytes': 1}
        later = self.save('releases/RCI001-C02-dev-104/snapshot.json',
                         {'revision': 'RCI001-C02-dev-104', 'sources': changed})
        with patch.object(c, 'MAP', self.root), patch.object(c.admission.base, 'frozen_problems', return_value=[]), \
             patch.object(c.admission, 'runtime_identities', return_value={runtime_name: sources[runtime_name]}):
            with self.assertRaisesRegex(ValueError, 'runtime sources differ'):
                c.assert_sources(value, later)

    def repair_receipt(self):
        value = self.declaration()
        target = self.save('harness/test_repair.py', {})
        output = self.save('stdout.txt', 'passed')
        error = self.save('stderr.txt', '')
        snapshot = self.save('snapshot.json', {'sources': {'harness/test_repair.py':
            {'sha256': c.sha(target), 'bytes': target.stat().st_size}}})
        value['source_snapshot'] = c.identity(snapshot)
        command = {'argv': [str(c.PYTHON), '-X', 'utf8', '-B', str(target), '-v'], 'exit_code': 0,
                   'test_inputs': [c.identity(target)], 'stdout': c.identity(output), 'stderr': c.identity(error)}
        receipt = {'schema': c.TEST_RECEIPT_SCHEMA, 'passed': True, 'source_snapshot': value['source_snapshot'],
                   'commands': [command]}
        return value, receipt, command

    def test_passing_repair_test_receipt_requires_exact_frozen_target_and_output_bytes(self):
        value, receipt, command = self.repair_receipt()
        path = self.save('tests.json', receipt)
        with patch.object(c, 'REPO', self.root):
            self.assertEqual(c.verify_repair_tests(c.identity(path), value), receipt)
            Path(command['stdout']['path']).write_text('changed')
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                c.verify_repair_tests(c.identity(path), value)

    def test_unrelated_passing_command_cannot_claim_frozen_test(self):
        value, receipt, command = self.repair_receipt()
        command['argv'][4] = str(self.root / 'unrelated.py')
        path = self.save('tests.json', receipt)
        with patch.object(c, 'REPO', self.root), self.assertRaisesRegex(ValueError, 'targets differ'):
            c.verify_repair_tests(c.identity(path), value)

    def test_discovery_receipt_requires_all_actual_frozen_tests(self):
        value, receipt, command = self.repair_receipt()
        command['argv'] = [str(c.PYTHON), '-X', 'utf8', '-B', '-m', 'unittest', 'discover',
                           '-s', str(self.root / 'harness'), '-p', 'test_*.py', '-v']
        path = self.save('tests.json', receipt)
        with patch.object(c, 'REPO', self.root):
            self.assertEqual(c.verify_repair_tests(c.identity(path), value), receipt)
            self.save('harness/test_unlisted.py', {})
            with self.assertRaisesRegex(ValueError, 'targets differ'):
                c.verify_repair_tests(c.identity(path), value)

    def test_repair_receipt_rejects_wrong_anchor_or_failed_command(self):
        value = self.declaration()
        snapshot = self.save('snapshot.json', {'sources': {}})
        value['source_snapshot'] = c.identity(snapshot)
        receipt = {'schema': c.TEST_RECEIPT_SCHEMA, 'passed': True, 'source_snapshot': value['source_snapshot'],
                   'commands': [{'argv': [str(c.PYTHON), '-X', 'utf8', '-B', 'test.py'], 'exit_code': False}]}
        path = self.save('tests.json', receipt)
        with self.assertRaisesRegex(ValueError, 'command failed'):
            c.verify_repair_tests(c.identity(path), value)
        receipt['source_snapshot'] = {'path': 'different', 'sha256': '0' * 64}
        path = self.save('tests.json', receipt)
        with self.assertRaisesRegex(ValueError, 'not bound'):
            c.verify_repair_tests(c.identity(path), value)

    def test_failed_terminal_queue_retained_without_outcome_read(self):
        job = self.job('failed', 1)
        receipt = self.root / 'queue.json'
        with patch.object(c, 'official', return_value=job), patch.object(c, 'read') as reader:
            with self.assertRaisesRegex(ValueError, 'Official queue'):
                c.await_success(job, receipt, ['fixed'])
            reader.assert_not_called()
        self.assertEqual(json.loads(receipt.read_text()), job)

    def test_wrong_official_command_stops_without_terminal_receipt(self):
        submitted = self.job()
        receipt = self.root / 'queue.json'
        with patch.object(c, 'official', return_value=dict(submitted, argv=['other'])):
            with self.assertRaisesRegex(ValueError, 'command changed'):
                c.await_success(submitted, receipt, ['fixed'])
        self.assertFalse(receipt.exists())

    def test_active_poll_retains_success_and_uses_fifteen_seconds(self):
        submitted = self.job('queued', None)
        final = self.job()
        with patch.object(c, 'official', side_effect=[self.job('running', None), final]), patch.object(c.time, 'sleep') as sleep:
            self.assertEqual(c.await_success(submitted, self.root / 'queue.json', ['fixed']), final)
            sleep.assert_called_once_with(15)

    def test_unresolved_intent_and_failed_receipt_are_never_retried(self):
        with patch.object(c, 'invoke', side_effect=RuntimeError('interrupted')) as command:
            with self.assertRaisesRegex(RuntimeError, 'interrupted'):
                c.command_once(self.root, 'submit', ['queue'])
            with self.assertRaisesRegex(ValueError, 'Unresolved command intent'):
                c.command_once(self.root, 'submit', ['queue'])
            command.assert_called_once()
        with patch.object(c, 'invoke', return_value=subprocess.CompletedProcess(['queue'], 1, '', 'failure')) as command:
            for _ in range(2):
                with self.assertRaisesRegex(ValueError, 'Command failed; no retry'):
                    c.command_once(self.root, 'other', ['queue'])
            command.assert_called_once()

    def test_existing_output_and_changed_completed_output_block_execution(self):
        target = self.save('existing.json', {})
        with patch.object(c, 'invoke') as command:
            with self.assertRaisesRegex(ValueError, 'Existing output'):
                c.command_once(self.root, 'prepare', ['prepare'], outputs=[target])
            command.assert_not_called()
        target = self.root / 'result.json'
        def execute(argv):
            target.write_text('{}')
            return subprocess.CompletedProcess(argv, 0, 'done', '')
        with patch.object(c, 'invoke', side_effect=execute) as command:
            first = c.command_once(self.root, 'prepare', ['prepare'], outputs=[target])
            self.assertEqual(c.command_once(self.root, 'prepare', ['prepare'], outputs=[target]), first)
            target.write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                c.command_once(self.root, 'prepare', ['prepare'], outputs=[target])
            command.assert_called_once()

    def test_absent_final_storage_stops_after_official_end_grace(self):
        job = dict(self.job(), ended_at='2026-09-27T00:00:00Z')
        with patch.object(c.time, 'time', return_value=c.admission.stamp(job['ended_at']) + 61), \
             patch.object(c, 'read') as reader, patch.object(c.time, 'sleep') as sleep:
            with self.assertRaisesRegex(ValueError, 'Final storage receipt missing'):
                c.wait_storage(self.root, job, self.root / 'manifest', self.root / 'evidence', self.root / 'host', self.root / 'workspace')
            reader.assert_not_called()
            sleep.assert_not_called()

    def test_storage_failure_is_retained_without_outcomes_and_never_retried(self):
        paths = {key: self.root / key for key in ('records', 'manifest', 'evidence', 'host', 'queue')}
        paths['run_id'] = 'fixed-run'
        paths['queue'].write_text(json.dumps(self.job()))
        with patch.object(c, 'wait_storage', side_effect=ValueError('coverage failed')) as wait:
            with self.assertRaisesRegex(ValueError, 'coverage failed'):
                c.storage_gate(self.root, paths, {'runtime_workspace': str(self.root / 'workspace')}, self.job())
            with self.assertRaisesRegex(ValueError, 'Prior storage failure'):
                c.storage_gate(self.root, paths, {'runtime_workspace': str(self.root / 'workspace')}, self.job())
            wait.assert_called_once()
        stop = json.loads((self.root / 'storage-stop.json').read_text())
        self.assertFalse(stop['outcomes_read'])
        self.assertNotIn('task_outcome', stop)



    def transport_fixture(self):
        snapshot = self.save('snapshot.json', {'revision': 'RCI001-C02-dev-103'})
        output = self.root / 'io-repair/transport-probe-024/evidence'
        result = {'schema': 'campaign002-codehost-channel-probe-3', 'run_id': 'RCI001-C02-transport-probe-024',
                  'framework_revision': 'RCI001-C02-dev-103', 'snapshot_sha256': c.sha(snapshot),
                  'model_calls': 0, 'physical_simulation': False, 'passed': True,
                  'cases': [{'case': kind, 'evidence': str(output / kind),
                             'transport_integrity': {'passed': True}} for kind in ('multi_channel','foreign_owner','in_flight_eof')]}
        result_path = self.save('io-repair/transport-probe-024/evidence/result.json', result)
        job = self.job()
        job['argv'] = c.python(self.root / 'harness/codehost_transport_probe_v3.py', '--run-id', result['run_id'],
                               '--framework-revision', result['framework_revision'], '--snapshot', snapshot,
                               '--output', output)
        queue = self.save('transport-queue.json', job)
        record = {'run_id': result['run_id'], 'job_id': job['id'], 'queue': c.identity(queue),
                  'result': c.identity(result_path)}
        return snapshot, result, result_path, job, record

    def test_failed_transport_queue_is_rejected_before_any_output_read(self):
        for state, code in [('failed',1), ('running',None), ('succeeded',False)]:
            record = {'run_id':'RCI001-C02-transport-probe-024','job_id':'fixed-job'}
            with self.subTest(state=state,code=code), patch.object(c, 'official', return_value=self.job(state,code)), \
                 patch.object(c.admission, 'artifact') as artifact, patch.object(c, 'read') as read:
                with self.assertRaisesRegex(ValueError, 'Official queue'):
                    c.verify_transport_probe(record, self.root / 'absent')
                artifact.assert_not_called();read.assert_not_called()

    def test_transport_probe_requires_exact_independent_three_case_replay(self):
        snapshot, result, _, job, record = self.transport_fixture()
        with patch.object(c, 'CAMPAIGN', self.root), patch.object(c, 'official', return_value=job), \
             patch.object(c, 'replay_raw_preflight', return_value=result) as verify:
            self.assertEqual(c.verify_transport_probe(record,snapshot),result)
            self.assertEqual(verify.call_count,1)
        with patch.object(c, 'CAMPAIGN', self.root), patch.object(c, 'official', return_value=job), \
             patch.object(c, 'replay_raw_preflight', return_value={'passed':False}):
            with self.assertRaisesRegex(ValueError, 'independent replay'):
                c.verify_transport_probe(record,snapshot)

    def test_transport_probe_rejects_source_model_physics_and_case_changes(self):
        snapshot, result, path, job, record = self.transport_fixture()
        original = json.dumps(result)
        for change in ('snapshot','model','physics','case'):
            value = json.loads(original)
            if change == 'snapshot':value['snapshot_sha256']='0'*64
            elif change == 'model':value['model_calls']=1
            elif change == 'physics':value['physical_simulation']=True
            else:value['cases']=value['cases'][:1]
            path.write_text(json.dumps(value),encoding='utf-8');record['result']=c.identity(path)
            with self.subTest(change=change), patch.object(c, 'CAMPAIGN', self.root), \
                 patch.object(c, 'official', return_value=job), \
                 patch.object(c, 'replay_raw_preflight') as verify:
                with self.assertRaises(ValueError):c.verify_transport_probe(record,snapshot)
                verify.assert_not_called()


    def test_preserved_v19_allocation_cannot_be_reused(self):
        value = self.declaration()
        value['stages'] = [['native-018', 'native', 'RCI001-C02-dev-057', 24000],
                           ['boundary-019', 'boundary', 'RCI001-C02-dev-058', None],
                           ['smoke-017', 'smoke', 'RCI001-C02-dev-059', 24101],
                           ['pilot-stock-016', 'stock', 'RCI001-C02-dev-059', 24102],
                           ['pilot-home-016', 'home', 'RCI001-C02-dev-059', 24103]]
        with self.assertRaisesRegex(ValueError, 'Qualifier identities'):
            self.load(value)

    def test_unload_scheduling_method_missing_or_changed_stops_before_runtime(self):
        methods = (c.STARTUP_REPAIR_METHOD, c.PROCESS_IDENTITY_METHOD,
                   c.FINISH_FRONTIER_METHOD, c.SEQUENCE_SYNCHRONIZATION_METHOD,
                   c.OWNER_DRAIN_METHOD, c.NATIVE_THREAD_QUIESCENCE_METHOD)
        for binding in (None, {'sha256': '0' * 64, 'bytes': 1}):
            with self.subTest(binding=binding):
                sources = {p.relative_to(c.REPO).as_posix():
                           {'sha256': c.sha(p), 'bytes': p.stat().st_size} for p in methods}
                name = c.NATIVE_THREAD_UNLOAD_SCHEDULING_METHOD.relative_to(c.REPO).as_posix()
                if binding is not None:
                    sources[name] = binding
                snapshot = self.save('releases/RCI001-C02-dev-103/snapshot.json',
                                     {'revision': 'RCI001-C02-dev-103', 'sources': sources})
                value = self.declaration()
                value['source_snapshot'] = c.identity(snapshot)
                with patch.object(c, 'MAP', self.root), \
                     patch.object(c.admission.base, 'frozen_problems', return_value=[]), \
                     patch.object(c.admission, 'runtime_identities') as runtime:
                    with self.assertRaisesRegex(ValueError, 'native-thread-unload-scheduling declaration'):
                        c.assert_sources(value)
                    runtime.assert_not_called()

    def test_new_method_is_bound_in_preflight_before_first_stage(self):
        from contextlib import nullcontext
        value = self.declaration()
        value.update(transport_diagnostic={'synthetic': True}, raw_event_preflight={'synthetic': True})
        with patch.object(c, 'coordinator_lock', return_value=nullcontext()), \
             patch.object(c, 'preflight', return_value=(value, {})), \
             patch.object(c, 'save_exact') as save, \
             patch.object(c, 'identity', side_effect=lambda path: {'path': str(path)}), \
             patch.object(c, 'sha', return_value='a' * 64), \
             patch.object(c, 'assert_sources'), \
             patch.object(c, 'prepare_stage', side_effect=RuntimeError('stop before launch')), \
             patch.object(c, 'launch_stage') as launch:
            with self.assertRaisesRegex(RuntimeError, 'stop before launch'):
                c.run(self.root / 'readiness.json', 'a' * 64)
            launch.assert_not_called()
        receipt = save.call_args_list[0].args[1]
        self.assertIn({'path': str(c.NATIVE_THREAD_UNLOAD_SCHEDULING_METHOD)}, receipt['orchestration_sources'])
        self.assertIn({'path': str(c.NORMAL_CLOSED_CANCEL_METHOD)}, receipt['orchestration_sources'])
        self.assertIn({'path': str(c.HERE / 'prepare_model_v23.py')}, receipt['orchestration_sources'])
        self.assertIn({'path': str(c.NATIVE_CLEANUP_CANCELLATION_METHOD)}, receipt['orchestration_sources'])
        self.assertIn({'path': str(c.INITIAL_READ_EVIDENCE_METHOD)}, receipt['orchestration_sources'])
        self.assertIn({'path': str(c.PREPARED_STARTUP_SEGMENTS_METHOD)}, receipt['orchestration_sources'])

    def test_preserved_v20_allocation_cannot_be_reused(self):
        value = self.declaration()
        value['stages'] = [['native-019', 'native', 'RCI001-C02-dev-058', 24000],
                           ['boundary-020', 'boundary', 'RCI001-C02-dev-059', None],
                           ['smoke-018', 'smoke', 'RCI001-C02-dev-060', 24101],
                           ['pilot-stock-017', 'stock', 'RCI001-C02-dev-060', 24102],
                           ['pilot-home-017', 'home', 'RCI001-C02-dev-060', 24103]]
        with self.assertRaisesRegex(ValueError, 'Qualifier identities'):
            self.load(value)

    def test_preserved_v21_allocation_cannot_be_reused(self):
        value = self.declaration()
        value['stages'] = [['native-020', 'native', 'RCI001-C02-dev-059', 24000],
                           ['boundary-021', 'boundary', 'RCI001-C02-dev-060', None],
                           ['smoke-019', 'smoke', 'RCI001-C02-dev-061', 24101],
                           ['pilot-stock-018', 'stock', 'RCI001-C02-dev-061', 24102],
                           ['pilot-home-018', 'home', 'RCI001-C02-dev-061', 24103]]
        with self.assertRaisesRegex(ValueError, 'Qualifier identities'):
            self.load(value)

    def test_normal_closed_cancel_method_is_required_before_runtime_validation(self):
        for binding in (None, {'sha256': '0' * 64, 'bytes': 1}):
            with self.subTest(binding=binding):
                value = self.declaration()
                methods = (c.STARTUP_REPAIR_METHOD, c.PROCESS_IDENTITY_METHOD,
                           c.FINISH_FRONTIER_METHOD, c.SEQUENCE_SYNCHRONIZATION_METHOD,
                           c.OWNER_DRAIN_METHOD, c.NATIVE_THREAD_QUIESCENCE_METHOD,
                           c.NATIVE_THREAD_UNLOAD_SCHEDULING_METHOD)
                sources = {p.relative_to(c.REPO).as_posix():
                           {'sha256': c.sha(p), 'bytes': p.stat().st_size} for p in methods}
                name = c.NORMAL_CLOSED_CANCEL_METHOD.relative_to(c.REPO).as_posix()
                if binding is not None: sources[name] = binding
                snapshot = self.save('releases/RCI001-C02-dev-103/snapshot.json',
                                     {'revision': 'RCI001-C02-dev-103', 'sources': sources})
                value['source_snapshot'] = c.identity(snapshot)
                with patch.object(c, 'MAP', self.root), \
                     patch.object(c.admission.base, 'frozen_problems', return_value=[]), \
                     patch.object(c.admission, 'runtime_identities') as runtime:
                    with self.assertRaisesRegex(ValueError, 'normal-closed-cancel declaration'):
                        c.assert_sources(value)
                    runtime.assert_not_called()

    def test_preserved_v22_allocation_cannot_be_reused(self):
        value = self.declaration()
        value['stages'] = [['native-021', 'native', 'RCI001-C02-dev-064', 24000],
                           ['boundary-022', 'boundary', 'RCI001-C02-dev-065', None],
                           ['smoke-020', 'smoke', 'RCI001-C02-dev-066', 24101],
                           ['pilot-stock-019', 'stock', 'RCI001-C02-dev-066', 24102],
                           ['pilot-home-019', 'home', 'RCI001-C02-dev-066', 24103]]
        with self.assertRaisesRegex(ValueError, 'Qualifier identities'):
            self.load(value)

    def test_cleanup_cancellation_method_is_required_before_runtime_validation(self):
        for binding in (None, {'sha256': '0'*64, 'bytes': 1}):
            with self.subTest(binding=binding):
                value = self.declaration()
                methods = (c.STARTUP_REPAIR_METHOD, c.PROCESS_IDENTITY_METHOD,
                           c.FINISH_FRONTIER_METHOD, c.SEQUENCE_SYNCHRONIZATION_METHOD,
                           c.OWNER_DRAIN_METHOD, c.NATIVE_THREAD_QUIESCENCE_METHOD,
                           c.NATIVE_THREAD_UNLOAD_SCHEDULING_METHOD, c.NORMAL_CLOSED_CANCEL_METHOD)
                sources = {p.relative_to(c.REPO).as_posix():
                           {'sha256': c.sha(p), 'bytes': p.stat().st_size} for p in methods}
                if binding is not None:
                    sources[c.NATIVE_CLEANUP_CANCELLATION_METHOD.relative_to(c.REPO).as_posix()] = binding
                snapshot = self.save('releases/RCI001-C02-dev-103/snapshot.json',
                                     {'revision': 'RCI001-C02-dev-103', 'sources': sources})
                value['source_snapshot'] = c.identity(snapshot)
                with patch.object(c, 'MAP', self.root), \
                     patch.object(c.admission.base, 'frozen_problems', return_value=[]), \
                     patch.object(c.admission, 'runtime_identities') as runtime:
                    with self.assertRaisesRegex(ValueError, 'native-cleanup-cancellation declaration'):
                        c.assert_sources(value)
                    runtime.assert_not_called()



    def test_preserved_v25_allocation_cannot_be_reused(self):
        value = self.declaration()
        value['stages'] = [['native-024', 'native', 'RCI001-C02-dev-076', 24000],
                           ['boundary-025', 'boundary', 'RCI001-C02-dev-077', None],
                           ['smoke-023', 'smoke', 'RCI001-C02-dev-078', 24101],
                           ['pilot-stock-022', 'stock', 'RCI001-C02-dev-078', 24102],
                           ['pilot-home-022', 'home', 'RCI001-C02-dev-078', 24103]]
        with self.assertRaisesRegex(ValueError, 'Qualifier identities'):
            self.load(value)

    def test_new_and_inherited_methods_are_required_and_remain_exact_in_later_stages(self):
        methods = [value for name, value in vars(c).items() if name.endswith('_METHOD')]
        originals = {p.relative_to(c.REPO).as_posix(): {'sha256': c.sha(p), 'bytes': p.stat().st_size}
                     for p in methods}
        for method in (c.EPOCH_REVOCATION_INDEX_METHOD, c.CANARY_READBACK_EXCLUSIVITY_METHOD, c.PREPARED_INDEX_LABELS_METHOD, c.PILOT_RETIREMENT_INVENTORY_METHOD, c.PRE_EXIT_DRAIN_METHOD, c.GRACEFUL_PROCESS_DRAIN_METHOD):
            name = method.relative_to(c.REPO).as_posix()
            for bad in (None, {'sha256': '0'*64, 'bytes': 1}):
                with self.subTest(method=method.name, bad=bad):
                    sources = dict(originals)
                    if bad is None: sources.pop(name)
                    else: sources[name] = bad
                    value = self.declaration()
                    path = self.save('releases/RCI001-C02-dev-103/snapshot.json',
                                     {'revision': 'RCI001-C02-dev-103', 'sources': sources})
                    value['source_snapshot'] = c.identity(path)
                    with patch.object(c, 'MAP', self.root), \
                         patch.object(c.admission.base, 'frozen_problems', return_value=[]), \
                         patch.object(c.admission, 'runtime_identities') as runtime:
                        with self.assertRaisesRegex(ValueError, 'declaration'):
                            c.assert_sources(value)
                        runtime.assert_not_called()
            value = self.declaration()
            path = self.save('releases/RCI001-C02-dev-103/snapshot.json',
                             {'revision': 'RCI001-C02-dev-103', 'sources': originals})
            value['source_snapshot'] = c.identity(path)
            changed = dict(originals); changed[name] = {'sha256': '0'*64, 'bytes': 1}
            later = self.save('releases/RCI001-C02-dev-104/snapshot.json',
                              {'revision': 'RCI001-C02-dev-104', 'sources': changed})
            with patch.object(c, 'MAP', self.root), \
                 patch.object(c.admission.base, 'frozen_problems', return_value=[]), \
                 patch.object(c.admission, 'runtime_identities', return_value={}), \
                 patch.object(Path, 'rglob', return_value=[]):
                with self.assertRaisesRegex(ValueError, 'changed|differ'):
                    c.assert_sources(value, later)

    def test_model_existing_queue_or_submit_receipt_blocks_before_launch_invocation(self):
        for name, kind, _ in c.STAGE_IDENTITIES[2:]:
            for receipt_name in ('queue', 'submit', 'queue-submit', 'launch-intent'):
                with self.subTest(kind=kind, receipt=receipt_name):
                    base = self.root / (name + '-' + receipt_name)
                    base.mkdir()
                    q = base / 'qualification'
                    q.mkdir()
                    with patch.object(c, 'HERE', q), patch.object(c, 'RAW', base / 'raw'):
                        paths = c.entry_for(name, kind, 'RCI001-C02-dev-106')
                        paths['manifest'].write_text('{}', encoding='utf-8')
                        paths['snapshot'] = base / 'snapshot.json'
                        paths['snapshot'].write_text('{}', encoding='utf-8')
                        targets = {'queue': paths['queue'], 'submit': q / (name + '-submit.json'),
                                   'queue-submit': paths['records'] / 'queue-submit.json',
                                   'launch-intent': paths['records'] / 'launch-intent.json'}
                        target = targets[receipt_name]
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text('{"previous":true}', encoding='utf-8')
                        folder = base / 'journal'
                        folder.mkdir()
                        with patch.object(c, 'invoke') as invoke, patch.object(c, 'await_success') as wait:
                            with self.assertRaisesRegex(ValueError, 'Existing output'):
                                c.launch_stage(folder, kind, paths,
                                               {'runtime_workspace': str(base / 'workspace')})
                            invoke.assert_not_called()
                            wait.assert_not_called()
                        self.assertFalse((folder / 'launch-intent.json').exists())
                        self.assertEqual(target.read_text(encoding='utf-8'), '{"previous":true}')

    def test_preserved_v26_allocation_cannot_be_reused(self):
        value = self.declaration()
        value['stages'] = [['native-025', 'native', 'RCI001-C02-dev-080', 24000],
                           ['boundary-026', 'boundary', 'RCI001-C02-dev-081', None],
                           ['smoke-024', 'smoke', 'RCI001-C02-dev-082', 24101],
                           ['pilot-stock-023', 'stock', 'RCI001-C02-dev-082', 24102],
                           ['pilot-home-023', 'home', 'RCI001-C02-dev-082', 24103]]
        with self.assertRaisesRegex(ValueError, 'Qualifier identities'):
            self.load(value)

if __name__ == '__main__':
    unittest.main()
