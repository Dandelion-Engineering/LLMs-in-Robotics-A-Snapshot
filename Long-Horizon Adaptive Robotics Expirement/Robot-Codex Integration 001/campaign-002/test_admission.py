"""Synthetic admission tamper/failure tests; no model, simulation or queue mutation."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import admission as a


class AuthenticatedBoundaryCommandTests(unittest.TestCase):
    def test_frozen_transport_contract_selects_exact_versioned_boundary_command(self):
        from transport_dispatch import V3_METHOD
        root=Path(tempfile.gettempdir()).resolve()/'synthetic-boundary-command'
        job={'state':'succeeded','exit_status':0,'started_at':'2026-09-28T00:00:01Z',
             'ended_at':'2026-09-28T00:00:02Z'}
        entry={'queue':{},'manifest':{'sha256':'b'*64},'assessment':{},'evidence':str(root)}
        for declared,filename in [(False,'boundary_suite.py'),(True,'boundary_suite_v3.py')]:
            frozen={'revision':'synthetic','run_id':'synthetic-run','manifest_sha256':'b'*64,
                    'created_at':'2026-09-28T00:00:00Z','sources':{V3_METHOD:{}} if declared else {}}
            manifest={'run_id':'synthetic-run','framework_revision':'synthetic'}
            with self.subTest(declared=declared),patch.object(a,'artifact',return_value=root/'manifest.json'), \
                 patch.object(a.base,'read_json',side_effect=[job,manifest,{}]), \
                 patch.object(a,'verify_qualifier_snapshot',return_value=frozen), \
                 patch.object(a,'direct_qualification_command') as command:
                a.qualifier_entry(entry,'boundary',{},a.stamp('2026-09-28T00:00:03Z'))
            command.assert_called_once_with(job,a.HERE/'qualification'/filename,['--output',str(root)])


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')
    return identity(path)


def identity(path):
    return {'path': str(Path(path).resolve()), 'sha256': a.base.hash_file(path)}


def write_jsonl(path, values):
    path.write_text(''.join(json.dumps(value) + '\n' for value in values), encoding='utf-8')
    return identity(path)


def timing_summary(windows=2, outside=0, lag=0.):
    clock = {'implementation': 'QueryPerformanceCounter()', 'monotonic': True,
             'adjustable': False, 'resolution': 1e-7}
    context = {'primary_clock_name': 'perf_counter', 'primary_clock': clock,
               'qpc_frequency_hz': 10_000_000, 'auxiliary_clock_name': 'monotonic',
               'auxiliary_clock': {'implementation': 'GetTickCount64()', 'monotonic': True,
                                   'adjustable': False, 'resolution': .015625},
               'cross_clock_sample': {'perf_counter_before_s': 99.9, 'perf_counter_after_s': 99.901,
                                      'monotonic_s': 123., 'unix_s': 1_800_000_000.}}
    return {'schema': 'rci-campaign-independent-timing-2', 'passed': True, 'scheduling_pass': True,
            'resource_integrity_pass': True, 'garbage_collection_pass': True, 'host_memory_pass': True,
            'garbage_collection': {'passed': True}, 'host_memory': {'passed': True},
            'sample_count': windows + 1,
            'loop_origin': {'monotonic_s': 100., 'initial_sim_s': 1., 'clock_name': 'perf_counter',
                            'clock': clock, 'clock_context': context},
            'replayed_timing': {'complete_wall_windows': windows, 'outside_rtf_tolerance_windows': outside,
                'outside_rtf_tolerance_fraction': outside / windows if windows else None,
                'maximum_lag_s': lag, 'actual_host_timing_pass': True,
                'timing': [{'real_time_factor': .94 if i < outside else 1., 'within_tolerance': i >= outside}
                           for i in range(windows)]}}


def schedule_fixture(root):
    attempts, slots = [], []
    for index in range(1, 21):
        pair = (index - 1) // 2
        family = ('misplaced-stock', 'blocked-insert-home')[(index - 1) % 2 ^ (pair % 2)]
        suffix = 'stock' if family == 'misplaced-stock' else 'home'
        run_id = f'RCI001-C02-{suffix}-{pair + 1:02d}'
        manifest = a.base.read_json(a.INTEGRATION / f'campaign-001/predeclared-v1/RCI001-C01-{suffix}-01.json')
        workspace = root / 'external' / run_id
        manifest.update(run_id=run_id, framework_revision='RCI001-C02-dev-test', noise_seed=23000 + index,
                        runtime_workspace=str(workspace))
        binding = write(root / 'manifests' / (run_id + '.json'), manifest)
        attempts.append({'ordinal': index, 'run_id': run_id, 'family': family, 'manifest': binding,
                         'workspace': str(workspace), 'evidence': str(root / 'evidence' / run_id),
                         'host_evidence': str(root / 'hosts' / run_id),
                         'storage_receipt': str(root / 'guards' / run_id / 'receipt.json')})
        slots.append({'ordinal': index, 'run_id': run_id, 'family': family, 'within_family_replicate': pair + 1,
                      'world_seed': 173, 'noise_seed': 23000 + index, 'maximum_model_invocations': 1,
                      'manifest': Path(binding['path']).name, 'sha256': binding['sha256'],
                      'runtime_workspace': str(workspace)})
    schedule = {'schema': 'campaign002-fixed-schedule-1', 'campaign_id': a.CAMPAIGN_ID,
                'source_revision': 'RCI001-C02-dev-test', 'attempt_count': 20,
                'replacements_allowed': 0, 'slots': slots}
    return schedule, attempts


def storage_fixture(root):
    policy = {'max_sample_gap_s': 30, 'retirement_headroom_bytes': 2_000_000_000, 'accounting_scope': 'native and WSL'}
    policy_binding = write(root / 'policy.json', policy)
    baseline = write(root / 'baseline.json', {'baseline': True})
    cert = {'artifacts': {'storage_monitor': {'sha256': 'a' * 64}, 'storage_policy': policy_binding,
                         'storage_baseline': baseline}}
    manifest = write(root / 'manifest.json', {'run_id': 'run1'})
    attempt = {'run_id': 'run1', 'manifest': manifest, 'evidence': str(root / 'evidence'),
               'host_evidence': str(root / 'host'), 'workspace': str(root / 'workspace'),
               'storage_receipt': str(root / 'receipt.json')}
    interpreter = str(a.REPO / 'venv/Scripts/python.exe')
    job = {'id': 'job1', 'state': 'succeeded', 'exit_status': 0,
           'started_at': '2026-09-27T00:00:01Z', 'ended_at': '2026-09-27T00:00:04Z',
           'cwd': str(a.REPO), 'resolved_executable': interpreter,
           'argv': [interpreter, '-X', 'utf8', '-B', str(a.base.LAUNCHER), '--manifest', manifest['path'],
                    '--evidence', attempt['evidence'], '--host-evidence', attempt['host_evidence'],
                    '--workspace', attempt['workspace'], '--mode', 'pilot']}
    queue = root / 'queue.json'; queue_binding = write(queue, job)
    samples = [{'started_utc': f'2026-09-27T00:00:0{i}Z', 'finished_utc': f'2026-09-27T00:00:0{i+1}Z',
                'native': {'free_bytes': {'C:': 200_000_000_000}},
                'wsl': {'free_bytes': {'/var/tmp': 200_000_000_000}}, 'aggregate_additional_bytes': i}
               for i in (0, 4)]
    sample_binding = write_jsonl(root / 'samples.jsonl', samples)
    receipt = {'schema': 'campaign001-storage-guard-1', 'run_id': 'run1', 'job_id': 'job1',
               'monitor_source_sha256': 'a' * 64, 'config_sha256': policy_binding['sha256'], 'baseline': baseline,
               'paths': {key: manifest['path'] if key == 'manifest' else attempt[key]
                         for key in ('manifest', 'evidence', 'host_evidence', 'workspace')},
               'official_queue_receipt': queue_binding, 'official_queue_state': 'succeeded', 'official_queue_exit_status': 0,
               'samples': sample_binding, 'sample_count': 2, 'state': 'completed', 'coverage_complete': True,
               'first_sample_utc': samples[0]['started_utc'], 'last_sample_utc': samples[-1]['finished_utc'],
               'admission_stop_latched': False, 'reserve_bytes': 100_000_000_000,
               'minimum_free_bytes': {'native': 200_000_000_000, 'wsl': 200_000_000_000},
               'peak_aggregate_additional_bytes': 4, 'max_sample_gap_s': 4, 'accounting_scope': 'native and WSL'}
    return root / 'receipt.json', receipt, cert, attempt, queue, job


class QueueSealTests(unittest.TestCase):
    def test_failed_queue_does_not_read_certificate_or_outcomes(self):
        for status in ({'state': 'failed', 'exit_status': 0}, {'state': 'succeeded', 'exit_status': False},
                       {'state': 'running', 'exit_status': None}):
            with patch.object(a.base, 'read_json', return_value=status) as reader:
                with self.assertRaisesRegex(ValueError, 'Official queue'):
                    a.admitted_assess('absent-cert', '0' * 64, 'absent-registration', 'run', 'receipt', 'job')
                reader.assert_called_once_with('receipt')

    def test_certificate_cannot_supply_its_own_trust_anchor(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'certificate.json'
            write(path, {'admitted': True, 'certificate_sha256': 'f' * 64})
            with self.assertRaisesRegex(ValueError, 'external seal'):
                a.verify_certificate(path, 'f' * 64)

    def test_artifact_changed_after_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'artifact.json'
            binding = write(path, {'source': 'frozen'})
            write(path, {'source': 'changed'})
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                a.artifact(binding)

    def test_missing_certificate_artifact_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'certificate.json'
            record = write(path, {'schema': 'campaign002-admission-1', 'campaign_id': a.CAMPAIGN_ID,
                                 'release_revision': a.RELEASE_REVISION, 'source_revision': 'RCI001-C02-dev-test',
                                 'created_at': '2026-09-27T00:00:00Z', 'artifacts': {}})
            with self.assertRaisesRegex(ValueError, 'Missing required admission artifact'):
                a.verify_certificate(path, record['sha256'])

    def test_qualification_queue_fails_before_assessment_read(self):
        with patch.object(a, 'artifact', return_value=Path('queue')) as artifact, \
                patch.object(a.base, 'read_json', return_value={'state': 'failed', 'exit_status': 1}) as reader:
            with self.assertRaisesRegex(ValueError, 'Official queue'):
                a.qualifier_entry({'queue': {'path': 'queue', 'sha256': '0' * 64}}, 'native', {}, 1.)
            self.assertEqual(artifact.call_count, 1)
            reader.assert_called_once_with(Path('queue'))

    def test_empty_pass_checks_cannot_qualify(self):
        for value in ({}, {'required': False}, {'different': True}):
            with self.assertRaisesRegex(ValueError, 'absent or failed'):
                a.all_checks(value, {'required'}, 'Synthetic')

    def test_matching_runtime_allows_different_external_drivers_and_revision(self):
        core = {'runtime.py': {'sha256': 'a' * 64, 'bytes': 3}}
        qualification = {'revision': 'prior-development', 'sources': {**core, 'external-test.py': {'sha256': 'b' * 64}}}
        a.verify_runtime_lineage(core, qualification)
        qualification['sources']['runtime.py'] = {'sha256': 'c' * 64, 'bytes': 3}
        with self.assertRaisesRegex(ValueError, 'runtime sources differ'):
            a.verify_runtime_lineage(core, qualification)

    def test_missing_runtime_source_fails(self):
        with self.assertRaisesRegex(ValueError, 'runtime sources differ'):
            a.verify_runtime_lineage({'runtime.py': {'sha256': 'a' * 64}}, {'sources': {}})

    def test_incomplete_qualification_index_fails(self):
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            a.verify_qualification_index({'schema': 'campaign002-qualification-index-1'}, {}, 1., {})

    def test_missing_pilot_family_fails(self):
        with self.assertRaisesRegex(ValueError, 'one qualification pilot per family'):
            a.verify_qualification_index({'schema': 'campaign002-qualification-index-1', 'native': {}, 'boundary': {},
                                          'smoke': {}, 'pilots': [{'family': 'misplaced-stock'}]}, {}, 1., {})


class RuntimeCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.here = self.root / 'campaign-002'
        self.harness = self.here / 'harness'
        self.harness.mkdir(parents=True)
        self.original = {f'original/source-{i}.py': {'sha256': f'{i:064x}', 'bytes': i} for i in range(624)}
        self.baseline = self.root / 'baseline.json'
        self.baseline_sha = write(self.baseline, {'sources': self.original})['sha256']
        self.frozen = {'sources': copy.deepcopy(self.original)}
        for name in a.REQUIRED_HARNESS_MODULES | {'future_helper.py', 'nested/another_helper.py', 'test_future.py'}:
            path = self.harness / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('# synthetic ' + name, encoding='utf-8')
            self.frozen['sources'][path.relative_to(self.root).as_posix()] = {
                'sha256': a.base.hash_file(path), 'bytes': path.stat().st_size}
        self.patches = [patch.object(a, 'REPO', self.root), patch.object(a, 'HERE', self.here),
                        patch.object(a, 'BASELINE_SNAPSHOT', self.baseline),
                        patch.object(a, 'BASELINE_SHA256', self.baseline_sha)]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temporary.cleanup()

    def test_entire_production_harness_including_future_helpers_is_frozen(self):
        core = a.runtime_identities(self.frozen)
        self.assertEqual(len(core), 624 + len(a.REQUIRED_HARNESS_MODULES) + 2)
        self.assertIn('campaign-002/harness/future_helper.py', core)
        self.assertIn('campaign-002/harness/nested/another_helper.py', core)
        self.assertNotIn('campaign-002/harness/test_future.py', core)

    def test_new_required_helpers_cannot_be_omitted_from_final_snapshot(self):
        for name in ('instrumented_journal.py', 'executor_capture.py'):
            with self.subTest(name=name):
                frozen = copy.deepcopy(self.frozen)
                del frozen['sources']['campaign-002/harness/' + name]
                with self.assertRaisesRegex(ValueError, 'omits a required executable'):
                    a.runtime_identities(frozen)

    def test_existing_unlisted_future_helper_fails_final_exact_set(self):
        del self.frozen['sources']['campaign-002/harness/future_helper.py']
        with self.assertRaisesRegex(ValueError, 'module set differs from current runtime'):
            a.runtime_identities(self.frozen)

    def test_snapshot_only_production_helper_fails_final_exact_set(self):
        (self.harness / 'future_helper.py').unlink()
        with self.assertRaisesRegex(ValueError, 'module set differs from current runtime'):
            a.runtime_identities(self.frozen)

    def test_changed_helper_in_qualification_fails(self):
        core = a.runtime_identities(self.frozen)
        for name in ('instrumented_journal.py', 'executor_capture.py', 'future_helper.py'):
            with self.subTest(name=name):
                qualifier = copy.deepcopy(self.frozen)
                qualifier['sources']['campaign-002/harness/' + name]['sha256'] = 'e' * 64
                with self.assertRaisesRegex(ValueError, 'runtime sources differ'):
                    a.verify_runtime_lineage(core, qualifier)

    def test_missing_helper_in_qualification_fails(self):
        core = a.runtime_identities(self.frozen)
        del self.frozen['sources']['campaign-002/harness/executor_capture.py']
        with self.assertRaisesRegex(ValueError, 'runtime sources differ'):
            a.verify_runtime_lineage(core, self.frozen)

    def test_qualification_only_production_helper_fails_exact_set(self):
        core = a.runtime_identities(self.frozen)
        self.frozen['sources']['campaign-002/harness/extra_helper.py'] = {'sha256': 'e' * 64, 'bytes': 1}
        with self.assertRaisesRegex(ValueError, 'production harness module set differs'):
            a.verify_runtime_lineage(core, self.frozen)

    def test_external_drivers_and_test_modules_may_differ(self):
        core = a.runtime_identities(self.frozen)
        self.frozen['sources']['campaign-002/harness/test_future.py'] = {'sha256': 'e' * 64, 'bytes': 1}
        self.frozen['sources']['qualification/driver.py'] = {'sha256': 'e' * 64, 'bytes': 1}
        a.verify_runtime_lineage(core, self.frozen)

    def test_boundary_receipt_must_include_new_helpers(self):
        core = a.runtime_identities(self.frozen)
        binding = {name: value['sha256'] for name, value in core.items()
                   if not name.endswith('/executor_capture.py')}
        entry = {'evidence': str(self.root), 'assessment': {'path': str(self.root / 'suite-result.json')}}
        value = {'schema': 'campaign002-boundary-suite-1', 'qualified': True,
                 'model_calls': 0, 'physical_simulation': False,
                 'checks': {name: True for name in a.BOUNDARY_CHECKS},
                 'started_wall_unix_s': 1., 'finished_wall_unix_s': 2.}
        job = {'started_at': '1970-01-01T00:00:00Z', 'ended_at': '1970-01-01T00:00:03Z'}
        with patch.object(a, 'qualifier_entry', return_value=(value, {}, self.frozen, job)), \
                patch.object(a.base, 'read_json', return_value=binding):
            with self.assertRaisesRegex(ValueError, 'complete production harness module set'):
                a.verify_boundary(entry, core, 4.)

    def test_assessor_read_helper_must_match_snapshot(self):
        path = self.here / 'assessment/retained_reads.py'
        path.parent.mkdir()
        path.write_text('# synthetic helper', encoding='utf-8')
        name = path.relative_to(self.root).as_posix()
        self.frozen['sources'][name] = {'sha256': a.base.hash_file(path), 'bytes': path.stat().st_size}
        resource = path.with_name('resource_integrity.py')
        resource.write_text('# synthetic resource helper', encoding='utf-8')
        self.frozen['sources'][resource.relative_to(self.root).as_posix()] = {
            'sha256': a.base.hash_file(resource), 'bytes': resource.stat().st_size}
        a.verify_assessor_helpers(self.frozen)
        path.write_text('# changed helper', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'retained-read or resource assessment helper'):
            a.verify_assessor_helpers(self.frozen)

    def test_missing_assessor_read_helper_in_snapshot_fails(self):
        path = self.here / 'assessment/retained_reads.py'
        path.parent.mkdir()
        path.write_text('# synthetic helper', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'retained-read or resource assessment helper'):
            a.verify_assessor_helpers(self.frozen)


class StrictTimingTests(unittest.TestCase):
    def test_complete_strict_timing_summary_passes(self):
        a.strict_timing_summary(timing_summary(), 'Synthetic')

    def test_point_one_lag_never_passes(self):
        with self.assertRaisesRegex(ValueError, 'thresholds'):
            a.strict_timing_summary(timing_summary(lag=.1), 'Synthetic')

    def test_one_percent_outside_never_passes(self):
        with self.assertRaisesRegex(ValueError, 'thresholds'):
            a.strict_timing_summary(timing_summary(windows=100, outside=1), 'Synthetic')

    def test_missing_or_failed_timing_cannot_be_admitted(self):
        for value in (None, {}, {**timing_summary(), 'passed': False}, {**timing_summary(), 'scheduling_pass': False}):
            with self.assertRaisesRegex(ValueError, 'qualification absent/failed'):
                a.strict_timing_summary(value, 'Synthetic')

    def test_invented_passing_window_boolean_fails(self):
        value = timing_summary(); value['replayed_timing']['timing'][0]['real_time_factor'] = .9
        with self.assertRaisesRegex(ValueError, 'window summary'):
            a.strict_timing_summary(value, 'Synthetic')

    def test_no_complete_window_cannot_pass(self):
        with self.assertRaisesRegex(ValueError, 'thresholds'):
            a.strict_timing_summary(timing_summary(windows=0), 'Synthetic')

    def test_missing_or_failed_resource_integrity_is_never_admitted(self):
        for key in ('resource_integrity_pass', 'garbage_collection_pass', 'host_memory_pass'):
            with self.subTest(key=key):
                value = timing_summary(); value.pop(key)
                with self.assertRaisesRegex(ValueError, 'memory or collector integrity'):
                    a.strict_timing_summary(value, 'Synthetic')

    def test_missing_or_legacy_clock_cannot_qualify_new_qpc_runtime(self):
        for origin in ({}, {'clock_name': 'monotonic'}, {**timing_summary()['loop_origin'], 'clock_context': {}}):
            with self.subTest(origin=origin):
                value = timing_summary(); value['loop_origin'] = origin
                with self.assertRaisesRegex(ValueError, 'QPC clock provenance'):
                    a.strict_timing_summary(value, 'Synthetic')

    def test_qpc_frequency_and_reported_resolution_must_agree(self):
        value = timing_summary()
        value['loop_origin']['clock_context']['qpc_frequency_hz'] = 1_000_000
        with self.assertRaisesRegex(ValueError, 'QPC clock provenance'):
            a.strict_timing_summary(value, 'Synthetic')

    def test_context_primary_clock_cannot_disagree_with_origin(self):
        value = timing_summary()
        value['loop_origin']['clock_context']['primary_clock'] = {'implementation': 'another clock'}
        with self.assertRaisesRegex(ValueError, 'QPC clock provenance'):
            a.strict_timing_summary(value, 'Synthetic')

    def test_cross_clock_bracket_must_precede_origin_and_retain_unix_anchor(self):
        for change in ({'perf_counter_after_s': 101.}, {'perf_counter_before_s': 99.902}, {'unix_s': None}):
            with self.subTest(change=change):
                value = timing_summary()
                value['loop_origin']['clock_context']['cross_clock_sample'].update(change)
                with self.assertRaisesRegex(ValueError, 'cross-clock chronology bracket'):
                    a.strict_timing_summary(value, 'Synthetic')


class QualificationGateTests(unittest.TestCase):
    def test_exact_eleven_boundary_suites_include_parity_executor_and_resource_guards(self):
        suites = [{'name': name, 'exit_code': 0} for name in
                  ('protected-host', 'robot-client', 'transport', 'timing', 'executor-capture-reader',
                   'gc-policy', 'host-memory', 'qualification-protocol', 'boundary-policy-windows',
                   'journal-instrumentation', 'recorder-instrumentation')]
        a.verify_boundary_suites(suites)
        for invalid in ([row for row in suites if row['name'] != 'executor-capture-reader'],
                        suites + [suites[0]], [{**row, 'exit_code': False} for row in suites]):
            with self.assertRaisesRegex(ValueError, 'unit suites incomplete'):
                a.verify_boundary_suites(invalid)
        for name in ('journal-instrumentation', 'recorder-instrumentation'):
            for invalid in ([row for row in suites if row['name'] != name],
                            [{**row, 'exit_code': 1} if row['name'] == name else row for row in suites]):
                with self.subTest(name=name, suites=invalid), self.assertRaisesRegex(ValueError, 'unit suites incomplete'):
                    a.verify_boundary_suites(invalid)

    def test_boundary_roundtrip_receipt_cannot_be_omitted(self):
        value = {'schema': 'campaign002-boundary-suite-1', 'qualified': True, 'model_calls': 0,
                 'physical_simulation': False,
                 'checks': {name: True for name in a.BOUNDARY_CHECKS if name != 'trusted_executor_capture_roundtrip'}}
        with patch.object(a, 'qualifier_entry', return_value=(value, {}, {}, {})):
            with self.assertRaisesRegex(ValueError, 'required checks absent or failed'):
                a.verify_boundary({}, {}, 1.)

    def test_no_native_rows_cannot_be_qualified_by_top_level_true(self):
        value = {'schema': 'campaign002-native-assessment-1', 'qualification_passed': True, 'rows': []}
        with patch.object(a, 'qualifier_entry', return_value=(value, {'model_turns_max': 0, 'slots': []}, {}, {})):
            with self.assertRaisesRegex(ValueError, 'Exactly six'):
                a.verify_native({}, {}, 1., {})

    def test_empty_boundary_checks_cannot_be_qualified_by_top_level_true(self):
        value = {'schema': 'campaign002-boundary-suite-1', 'qualified': True, 'model_calls': 0,
                 'physical_simulation': False, 'checks': {}}
        with patch.object(a, 'qualifier_entry', return_value=(value, {}, {}, {})):
            with self.assertRaisesRegex(ValueError, 'required checks absent or failed'):
                a.verify_boundary({}, {}, 1.)

    def test_model_qualification_requires_actual_strict_timing_summary(self):
        manifest = {'model': 'gpt-6-astra', 'effort': 'max', 'bootstrap': 'Follow the instructions in RobotAgentPrompt.md.'}
        artifacts = {'base_assessor': {'path': str(a.HERE / 'assessment/assess.py'), 'sha256': 'a' * 64},
                     'smoke_assessor': {'path': str(a.HERE / 'assessment/assess_smoke_v2.py'), 'sha256': 'b' * 64}}
        frozen = {'sources': {Path(row['path']).relative_to(a.REPO).as_posix(): {'sha256': row['sha256']}
                              for row in artifacts.values()}}
        for name in ('retained_reads.py', 'resource_integrity.py'):
            helper = a.HERE / 'assessment' / name
            frozen['sources'][helper.relative_to(a.REPO).as_posix()] = {
                'sha256': a.base.hash_file(helper), 'bytes': helper.stat().st_size}
        with patch.object(a, 'qualifier_entry', return_value=({'smoke_passed': True}, manifest, frozen, {})):
            with self.assertRaisesRegex(ValueError, 'strict timing'):
                a.verify_model_qualifier({}, 'smoke', {}, 1., artifacts)

    def test_model_snapshot_must_include_its_actual_assessor(self):
        artifacts = {'base_assessor': {'path': str(a.HERE / 'assessment/assess.py'), 'sha256': 'a' * 64}}
        with patch.object(a, 'qualifier_entry', return_value=({}, {}, {'sources': {}}, {})):
            with self.assertRaisesRegex(ValueError, 'snapshot omits or changes'):
                a.verify_model_qualifier({}, 'smoke', {}, 1., artifacts)


class ModelTransportAdmissionTests(unittest.TestCase):
    TRANSPORT_CHECK = 'complete_codehost_lifecycle_and_safe_metadata'

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.entry = {name: write(self.root / (name + '.json'), {})
                      for name in ('manifest', 'snapshot', 'queue')}
        self.archive = write(self.root / 'code.zip', {'synthetic_archive': True})
        self.artifacts = {name: identity(a.HERE / 'assessment' / filename) for name, filename in (
            ('base_assessor', 'assess.py'), ('smoke_assessor', 'assess_smoke_v2.py'))}
        paths = [Path(row['path']) for row in self.artifacts.values()]
        paths += [a.HERE / 'assessment' / name for name in ('retained_reads.py', 'resource_integrity.py')]
        self.frozen = {'sources': {path.relative_to(a.REPO).as_posix(): {
            'sha256': a.base.hash_file(path), 'bytes': path.stat().st_size} for path in paths}}

    def fixture(self, kind, family='misplaced-stock'):
        manifest = {'model': 'gpt-6-astra', 'effort': 'max',
                    'bootstrap': 'Follow the instructions in RobotAgentPrompt.md.',
                    'model_turns_max': 2 if kind == 'smoke' else 1,
                    'noise_seed': 24101 if kind == 'smoke' else
                                  {'misplaced-stock': 24102, 'blocked-insert-home': 24103}[family],
                    'family': family, 'interruption_trigger': None}
        checks = a.SMOKE_CHECKS if kind == 'smoke' else a.PILOT_CHECKS
        value = {'campaign_timing': timing_summary(), 'checks': {name: True for name in checks}}
        if kind == 'smoke':
            value.update(schema='robot-codex-physical-smoke-assessment-2', smoke_passed=True,
                manifest_sha256=self.entry['manifest']['sha256'],
                frozen_snapshot_sha256=self.entry['snapshot']['sha256'],
                frozen_archive_sha256=self.archive['sha256'],
                assessment_code_sha256=self.artifacts['smoke_assessor']['sha256'],
                base_assessment_sha256=self.artifacts['base_assessor']['sha256'],
                evidence_sha256={row['path']: row['sha256'] for row in self.entry.values()})
        else:
            self.entry['family'] = family
            value.update(schema='robot-codex-campaign-assessment-2', validity='valid',
                failed_checks=[], task_evidence_valid=True, task_outcome='success', scorable=False,
                family=family, bindings={
                    'manifest_sha256': self.entry['manifest']['sha256'],
                    'framework_snapshot_sha256': self.entry['snapshot']['sha256'],
                    'framework_archive_sha256': self.archive['sha256'],
                    'queue_receipt_sha256': self.entry['queue']['sha256'],
                    'assessment_sha256': self.artifacts['base_assessor']['sha256']})
        return value, manifest

    def verify(self, value, manifest, kind):
        # Queue/source entry authentication is tested separately. Keep the actual
        # model schema, strict timing, helper bindings and check validation here.
        with patch.object(a, 'qualifier_entry', return_value=(value, manifest, self.frozen, {})):
            a.verify_model_qualifier(self.entry, kind, {}, 1., self.artifacts)

    def test_complete_transport_check_allows_smoke_and_both_pilot_families(self):
        for kind, family in (('smoke', 'misplaced-stock'), ('pilot', 'misplaced-stock'),
                             ('pilot', 'blocked-insert-home')):
            with self.subTest(kind=kind, family=family):
                value, manifest = self.fixture(kind, family)
                self.assertIs(value['checks'][self.TRANSPORT_CHECK], True)
                self.verify(value, manifest, kind)

    def test_smoke_top_level_pass_cannot_omit_transport_check(self):
        value, manifest = self.fixture('smoke')
        del value['checks'][self.TRANSPORT_CHECK]
        with self.assertRaisesRegex(ValueError, 'Smoke required checks absent or failed'):
            self.verify(value, manifest, 'smoke')

    def test_pilot_top_level_pass_cannot_omit_transport_check(self):
        for family in ('misplaced-stock', 'blocked-insert-home'):
            with self.subTest(family=family):
                value, manifest = self.fixture('pilot', family)
                del value['checks'][self.TRANSPORT_CHECK]
                with self.assertRaisesRegex(ValueError, 'Pilot required checks absent or failed'):
                    self.verify(value, manifest, 'pilot')


class AssetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        assets = []
        for index in range(80):
            path = self.root / f'asset-{index}.txt'
            path.write_text(str(index), encoding='utf-8')
            assets.append({**identity(path), 'bytes': path.stat().st_size, 'matched': True})
        packages = [{'name': f'package-{index}', 'expected_version': '1.0', 'actual_version': '1.0', 'matched': True}
                    for index in range(10)]
        self.original = {'assets': assets, 'packages': packages}
        self.baseline = self.root / 'prior-assets.json'
        self.baseline_sha = write(self.baseline, self.original)['sha256']
        self.refresh = {'schema': 'rci-campaign-asset-refresh-1', 'qualified': True,
                        'created_at': '2026-09-27T00:00:00Z', 'source_sha256': 'a' * 64,
                        'prior_qualification_sha256': self.baseline_sha,
                        **copy.deepcopy(self.original)}

    def tearDown(self):
        self.temporary.cleanup()

    def verify(self, current_version='1.0'):
        with patch.object(a, 'ASSET_BASELINE', self.baseline), patch.object(a, 'ASSET_BASELINE_SHA256', self.baseline_sha), \
                patch.object(a.importlib.metadata, 'version', return_value=current_version):
            a.verify_assets(self.refresh, 'a' * 64, a.stamp('2026-09-27T00:01:00Z'))

    def test_exact_assets_and_packages_pass(self):
        self.verify()

    def test_missing_asset_fails(self):
        self.refresh['assets'].pop()
        with self.assertRaisesRegex(ValueError, 'inventory incomplete'):
            self.verify()

    def test_changed_actual_asset_fails(self):
        Path(self.refresh['assets'][0]['path']).write_text('changed', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
            self.verify()

    def test_resealed_asset_substitution_fails_original_identity_set(self):
        path = self.root / 'substitution.txt'; path.write_text('substitute', encoding='utf-8')
        self.refresh['assets'][0] = {**identity(path), 'bytes': path.stat().st_size, 'matched': True}
        with self.assertRaisesRegex(ValueError, 'asset set or expected identities changed'):
            self.verify()

    def test_current_package_drift_fails(self):
        with self.assertRaisesRegex(ValueError, 'Installed runtime package version changed'):
            self.verify(current_version='2.0')

    def test_new_expected_package_version_cannot_redefine_qualified_dependency(self):
        self.refresh['packages'][0].update(expected_version='2.0', actual_version='2.0')
        with self.assertRaisesRegex(ValueError, 'expected versions changed'):
            self.verify()


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.map_root = self.root / 'map'; self.map_root.mkdir()
        _, attempts = schedule_fixture(self.root)
        snapshot = write(self.root / 'source-snapshot.json', {})
        archive = write(self.root / 'source-archive.json', {})
        self.cert = {'source_revision': 'RCI001-C02-dev-test', 'release_revision': a.RELEASE_REVISION,
                     'created_at': '2026-09-27T00:00:00Z', 'attempts': attempts,
                     'artifacts': {'source_snapshot': snapshot, 'source_archive': archive}}
        self.release = {'id': a.RELEASE_REVISION, 'recorded_at': '2026-09-27T00:00:01Z',
                        'details': {'certificate_sha256': 'a' * 64}}
        self.registration = {'schema': 'campaign002-registration-1', 'certificate_sha256': 'a' * 64,
                             'release_revision': a.RELEASE_REVISION, 'source_snapshot_sha256': snapshot['sha256'],
                             'map_root': str(self.map_root), 'release_snapshot': snapshot, 'release_archive': archive,
                             'release_record': write(self.root / 'release.json', self.release), 'attempts': []}
        self.records = []
        for attempt in attempts:
            record = {'id': attempt['run_id'], 'revision_id': a.RELEASE_REVISION,
                      'recorded_at': '2026-09-27T00:00:02Z', 'details': {'certificate_sha256': 'a' * 64},
                      'condition_details': {'manifest_sha256': attempt['manifest']['sha256'],
                                            'manifest': a.base.read_json(attempt['manifest']['path'])}}
            self.records.append(record)
            self.registration['attempts'].append({'run_id': record['id'], 'manifest_sha256': attempt['manifest']['sha256'],
                                                  'run_record': write(self.root / (record['id'] + '.json'), record)})
        write_jsonl(self.map_root / 'revisions.jsonl', [self.release])
        write_jsonl(self.map_root / 'runs.jsonl', self.records)
        self.path = self.root / 'registration.json'

    def tearDown(self):
        self.temporary.cleanup()

    def verify(self):
        write(self.path, self.registration)
        with patch.object(a, 'MAP', self.map_root):
            return a.verify_registration(self.path, self.cert, 'a' * 64)

    def test_complete_canonical_registration_passes(self):
        self.assertEqual(self.verify(), self.registration)

    def test_missing_canonical_attempt_fails(self):
        write_jsonl(self.map_root / 'runs.jsonl', self.records[:-1])
        with self.assertRaisesRegex(ValueError, 'not uniquely registered'):
            self.verify()

    def test_changed_detached_record_fails_hash(self):
        path = Path(self.registration['attempts'][0]['run_record']['path'])
        write(path, {**self.records[0], 'revision_id': 'different'})
        with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
            self.verify()

    def test_release_cannot_be_backdated_before_admission(self):
        self.release['recorded_at'] = '2026-09-26T23:59:59Z'
        self.registration['release_record'] = write(Path(self.registration['release_record']['path']), self.release)
        write_jsonl(self.map_root / 'revisions.jsonl', [self.release])
        with self.assertRaisesRegex(ValueError, 'Release predates admission'):
            self.verify()

    def test_twenty_slots_must_all_be_registered(self):
        self.registration['attempts'].pop()
        with self.assertRaisesRegex(ValueError, 'Incomplete immutable attempt'):
            self.verify()


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.schedule, self.attempts = schedule_fixture(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def verify(self):
        return a.verify_schedule(self.schedule, self.attempts, 'RCI001-C02-dev-test')

    def test_twenty_fresh_predeclared_attempts_pass(self):
        self.verify()

    def test_replacement_slot_is_rejected(self):
        self.attempts.append(copy.deepcopy(self.attempts[0]))
        with self.assertRaisesRegex(ValueError, 'Exactly 20'):
            self.verify()

    def test_seed_swap_is_rejected(self):
        self.schedule['slots'][0]['noise_seed'] = 23002
        with self.assertRaisesRegex(ValueError, 'seed violation'):
            self.verify()

    def test_resealed_prompt_or_limit_change_is_rejected(self):
        for key, value in [('bootstrap', 'extra instruction'), ('model', 'another-model'), ('action_request_budget', 21)]:
            with self.subTest(key=key):
                manifest = a.base.read_json(self.attempts[0]['manifest']['path'])
                manifest[key] = value
                self.attempts[0]['manifest'] = write(Path(self.attempts[0]['manifest']['path']), manifest)
                self.schedule['slots'][0]['sha256'] = self.attempts[0]['manifest']['sha256']
                with self.assertRaisesRegex(ValueError, 'changes frozen fixture/model/prompt'):
                    self.verify()

    def test_duplicate_evidence_paths_are_rejected(self):
        self.attempts[1]['evidence'] = self.attempts[0]['evidence']
        with self.assertRaisesRegex(ValueError, 'paths must be unique'):
            self.verify()

    def test_repository_workspace_is_rejected_even_if_resealed(self):
        manifest = a.base.read_json(self.attempts[0]['manifest']['path'])
        workspace = str(a.REPO / 'model-workspace')
        manifest['runtime_workspace'] = workspace
        self.attempts[0]['manifest'] = write(Path(self.attempts[0]['manifest']['path']), manifest)
        self.attempts[0]['workspace'] = workspace
        self.schedule['slots'][0].update(runtime_workspace=workspace, sha256=self.attempts[0]['manifest']['sha256'])
        with self.assertRaisesRegex(ValueError, 'external to repository'):
            self.verify()


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.path, self.receipt, self.cert, self.attempt, self.queue, self.job = storage_fixture(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def verify(self):
        write(self.path, self.receipt)
        return a.verify_storage(self.path, self.cert, self.attempt, self.queue, self.job)

    def test_authenticated_complete_storage_passes(self):
        self.assertEqual(self.verify(), self.receipt)

    def test_missing_receipt_is_not_treated_as_zero_usage(self):
        with self.assertRaises(FileNotFoundError):
            a.verify_storage(self.path, self.cert, self.attempt, self.queue, self.job)

    def test_false_coverage_stop_or_peak_summaries_fail(self):
        original = copy.deepcopy(self.receipt)
        for field, value in (('last_sample_utc', '2026-09-27T00:00:03Z'), ('admission_stop_latched', True),
                             ('peak_aggregate_additional_bytes', 0),
                             ('minimum_free_bytes', {'native': 300_000_000_000, 'wsl': 200_000_000_000})):
            self.receipt = {**copy.deepcopy(original), field: value}
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.verify()

    def test_wrong_job_or_baseline_fails(self):
        self.receipt['job_id'] = 'different'
        with self.assertRaisesRegex(ValueError, 'identity'):
            self.verify()
        self.receipt['job_id'] = 'job1'
        self.cert['artifacts']['storage_baseline'] = {**self.cert['artifacts']['storage_baseline'], 'sha256': '0' * 64}
        with self.assertRaisesRegex(ValueError, 'baseline differs'):
            self.verify()

    def test_corrupted_samples_fail_hash(self):
        Path(self.receipt['samples']['path']).write_text('{}\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
            self.verify()

    def test_retirement_headroom_is_preserved(self):
        samples = a.base.jsonl(Path(self.receipt['samples']['path']))
        for row in samples:
            row['native']['free_bytes']['C:'] = 101_000_000_000
        self.receipt['samples'] = write_jsonl(Path(self.receipt['samples']['path']), samples)
        self.receipt['minimum_free_bytes']['native'] = 101_000_000_000
        with self.assertRaisesRegex(ValueError, 'retirement headroom'):
            self.verify()

    def test_planning_allowance_is_not_a_hard_limit(self):
        samples = a.base.jsonl(Path(self.receipt['samples']['path']))
        samples[-1]['aggregate_additional_bytes'] = 40_000_000_000
        self.receipt['samples'] = write_jsonl(Path(self.receipt['samples']['path']), samples)
        self.receipt['peak_aggregate_additional_bytes'] = 40_000_000_000
        self.assertEqual(self.verify()['peak_aggregate_additional_bytes'], 40_000_000_000)


class AdmittedDispositionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.path, self.receipt, self.cert, self.attempt, self.queue, self.job = storage_fixture(self.root)
        self.cert.update(created_at='2026-09-26T23:59:00Z', source_revision='RCI001-C02-dev-test',
                         release_revision=a.RELEASE_REVISION, attempts=[self.attempt])
        self.cert['artifacts']['source_snapshot'] = write(self.root / 'snapshot.json', {})
        release = write(self.root / 'release.json', {'recorded_at': '2026-09-26T23:59:10Z'})
        record = write(self.root / 'run.json', {'recorded_at': '2026-09-26T23:59:20Z'})
        self.registration = {'release_record': release, 'attempts': [{'run_record': record}]}
        self.registration_path = self.root / 'registration.json'
        write(self.registration_path, self.registration)
        self.result = {'run_id': 'run1', 'validity': 'valid', 'observed_task_outcome': 'success', 'checks': {'base': True},
                       'campaign_timing': timing_summary(), 'bindings': {}, 'limitations': []}

    def tearDown(self):
        self.temporary.cleanup()

    def admitted(self):
        with patch.object(a, 'verify_certificate', return_value=self.cert), \
                patch.object(a, 'verify_registration', return_value=self.registration), \
                patch.object(a.base, 'assess', return_value=copy.deepcopy(self.result)):
            return a.admitted_assess('certificate', 'a' * 64, self.registration_path, 'run1', self.queue, 'job1')

    def test_valid_full_gate_becomes_scorable(self):
        write(self.path, self.receipt)
        result = self.admitted()
        self.assertEqual(result['schema'], 'robot-codex-campaign-admitted-assessment-2')
        self.assertTrue(result['scorable'])
        self.assertEqual(result['task_outcome'], 'success')

    def test_missing_storage_preserves_observation_and_invalidates_score(self):
        result = self.admitted()
        self.assertEqual(result['observed_task_outcome'], 'success')
        self.assertEqual(result['task_outcome'], 'unknown')
        self.assertFalse(result['scorable'])
        self.assertIn('storage', result['scientific_admission']['errors'])

    def test_missing_or_failed_timing_preserves_observation_and_invalidates_score(self):
        write(self.path, self.receipt)
        for timing in (None, {**timing_summary(), 'passed': False}, timing_summary(lag=.1)):
            self.result['campaign_timing'] = timing
            result = self.admitted()
            self.assertEqual(result['task_outcome'], 'unknown')
            self.assertFalse(result['scorable'])
            self.assertIn('timing', result['scientific_admission']['errors'])

    def test_valid_task_failure_stays_in_denominator(self):
        write(self.path, self.receipt)
        self.result['observed_task_outcome'] = 'failure'
        result = self.admitted()
        self.assertTrue(result['scorable'])
        self.assertEqual(result['task_outcome'], 'failure')

    def test_post_outcome_certificate_fails_before_base_outcome_read(self):
        self.cert['created_at'] = '2026-09-27T00:00:02Z'
        with patch.object(a, 'verify_certificate', return_value=self.cert), \
                patch.object(a, 'verify_registration', return_value=self.registration), \
                patch.object(a.base, 'assess') as assessor:
            with self.assertRaisesRegex(ValueError, 'precede scored attempt'):
                a.admitted_assess('certificate', 'a' * 64, self.registration_path, 'run1', self.queue, 'job1')
            assessor.assert_not_called()


if __name__ == '__main__':
    unittest.main()
