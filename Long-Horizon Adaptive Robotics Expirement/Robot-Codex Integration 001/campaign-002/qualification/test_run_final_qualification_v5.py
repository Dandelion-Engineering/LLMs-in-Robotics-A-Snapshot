"""Continuation policy tests; no queue submission, runtime or model invocation."""
from contextlib import ExitStack, nullcontext
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('qualification_continuation_v5_tests', HERE / 'run_final_qualification_v5.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')
        return path

    def readiness(self):
        return {'schema': c.SCHEMA, 'ledger_directory': str(c.LEDGER),
                'prior_coordinator': {'path': str(c.v4.__file__), 'sha256': 'a' * 64},
                'prior_readiness': {'path': str(c.HERE / 'final-qualification-004-readiness.json'), 'sha256': 'b' * 64},
                'native': {'job_id': c.NATIVE_JOB, 'disposition': {'path': 'native', 'sha256': 'c' * 64}, 'entry': {}},
                'boundary_failure': {'job_id': c.BOUNDARY_JOB, 'disposition': {'path': 'boundary', 'sha256': 'd' * 64}},
                'stages': [list(stage) for stage in c.STAGES]}

    def job(self, identifier, state='succeeded', code=0):
        return {'id': identifier, 'state': state, 'exit_status': code}

    def test_fixed_fresh_declaration_and_external_hash(self):
        value = self.readiness()
        path = self.write('readiness.json', value)
        self.assertEqual(c.load_readiness(path, c.sha(path)), value)
        with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
            c.load_readiness(path, '0' * 64)

    def test_reused_or_reordered_stage_and_other_previous_jobs_are_rejected(self):
        for change in ('name', 'revision', 'seed', 'order', 'job', 'ledger', 'coordinator'):
            value = self.readiness()
            if change == 'name': value['stages'][0][0] = 'boundary-004'
            elif change == 'revision': value['stages'][0][2] = 'RCI001-C02-dev-017'
            elif change == 'seed': value['stages'][1][3] = 24101.
            elif change == 'order': value['stages'][2], value['stages'][3] = value['stages'][3], value['stages'][2]
            elif change == 'job': value['native']['job_id'] = 'other'
            elif change == 'ledger': value['ledger_directory'] = str(c.v4.LEDGER)
            else: value['prior_coordinator']['path'] = str(c.HERE / 'other.py')
            path = self.write('readiness.json', value)
            with self.subTest(change=change), self.assertRaises(ValueError):
                c.load_readiness(path, c.sha(path))

    def test_both_official_jobs_authenticate_before_any_prior_outcome_read(self):
        for failed_index in (0, 1):
            for state, code in (('running', None), ('failed', 1), ('succeeded', False), ('succeeded', '0')):
                jobs = [self.job(c.NATIVE_JOB), self.job(c.BOUNDARY_JOB)]
                jobs[failed_index] = self.job(jobs[failed_index]['id'], state, code)
                with self.subTest(index=failed_index, state=state, code=code), \
                     patch.object(c, 'load_readiness', return_value=self.readiness()), \
                     patch.object(c.v4, 'official', side_effect=jobs), patch.object(c, 'read') as reader, \
                     patch.object(c.admission, 'artifact') as artifact, patch.object(c.v4, 'preflight') as previous:
                    with self.assertRaisesRegex(ValueError, 'Official queue'):
                        c.preflight(self.root / 'readiness', 'a' * 64)
                    reader.assert_not_called()
                    artifact.assert_not_called()
                    previous.assert_not_called()

    def context(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        value = self.readiness()
        native = {'snapshot': {'path': str(self.root / 'snapshot.json')}, 'native': True}
        boundary = {'boundary': True}
        prior, core = {'source_snapshot': {}}, {'core': True}
        stack.enter_context(patch.object(c, 'load_readiness', return_value=value))
        official = stack.enter_context(patch.object(c.v4, 'official', side_effect=lambda identifier: self.job(identifier)))
        stack.enter_context(patch.object(c.admission, 'artifact', side_effect=lambda item: Path(item['path'])))
        previous = stack.enter_context(patch.object(c.v4, 'preflight', return_value=(prior, core)))
        retained = stack.enter_context(patch.object(c, 'retained_disposition', side_effect=[native, boundary]))
        sources = stack.enter_context(patch.object(c.v4, 'assert_sources'))
        verify = stack.enter_context(patch.object(c.admission, 'verify_native'))
        diagnosis = stack.enter_context(patch.object(c, 'verify_packaging_failure', return_value={'missing': c.MISSING_README}))
        return value, prior, core, native, official, previous, retained, sources, verify, diagnosis

    def test_existing_native_receives_full_original_contract_without_new_registration(self):
        value, prior, core, native, official, previous, retained, sources, verify, diagnosis = self.context()
        result = c.preflight(self.root / 'readiness', 'a' * 64)
        self.assertEqual(result[:4], (value, prior, core, native))
        self.assertEqual([call.args[0] for call in official.call_args_list], [c.NATIVE_JOB, c.BOUNDARY_JOB])
        previous.assert_called_once_with(Path(value['prior_readiness']['path']), value['prior_readiness']['sha256'])
        sources.assert_called_once_with(prior, Path(native['snapshot']['path']))
        self.assertEqual(verify.call_args.args[:2], (native, core))
        self.assertEqual(retained.call_count, 2)
        diagnosis.assert_called_once()

    def test_failed_native_contract_blocks_new_stages_and_boundary_consumption(self):
        _, _, _, _, _, _, retained, _, verify, diagnosis = self.context()
        verify.side_effect = ValueError('Native qualification assessment failed')
        with self.assertRaisesRegex(ValueError, 'Native qualification'):
            c.preflight(self.root / 'readiness', 'a' * 64)
        self.assertEqual(retained.call_count, 1)
        diagnosis.assert_not_called()

    def test_packaging_failure_requires_exact_single_readme_omission(self):
        source = c.MISSING_README
        before = {source: c.sha(c.v4.REPO / source), 'kept.py': 'b' * 64}
        frozen = {'revision': 'RCI001-C02-dev-017', 'sources': {'kept.py': {'sha256': 'b' * 64}}}
        value = {'qualified': True, 'model_calls': 0, 'physical_simulation': False,
                 'checks': {name: True for name in c.admission.BOUNDARY_CHECKS},
                 'unit_suites': [{'name': name, 'exit_code': 0} for name in c.admission.BOUNDARY_UNIT_SUITES]}
        base_args = (value, {'run_id': 'RCI001-C02-boundary-004'}, frozen, self.job(c.BOUNDARY_JOB))
        for change in ('extra_missing', 'changed', 'before_after'):
            candidate = dict(before)
            if change == 'extra_missing': candidate['another.py'] = 'c' * 64
            elif change == 'changed': candidate['kept.py'] = 'c' * 64
            after = dict(candidate)
            if change == 'before_after': after[source] = 'd' * 64
            with self.subTest(change=change), patch.object(c.admission, 'qualifier_entry', return_value=base_args), \
                 patch.object(c, 'read', side_effect=[candidate, after]):
                with self.assertRaisesRegex(ValueError, 'changed source|sole README'):
                    c.verify_packaging_failure({'evidence': str(self.root)}, {})

    def test_exact_packaging_failure_stays_rejected_by_existing_admission(self):
        source = c.MISSING_README
        before = {source: c.sha(c.v4.REPO / source)}
        self.write('source-binding-before.json', before)
        self.write('source-binding-after.json', before)
        value = {'qualified': True, 'model_calls': 0, 'physical_simulation': False,
                 'checks': {name: True for name in c.admission.BOUNDARY_CHECKS},
                 'unit_suites': [{'name': name, 'exit_code': 0} for name in c.admission.BOUNDARY_UNIT_SUITES]}
        args = (value, {'run_id': 'RCI001-C02-boundary-004'},
                {'revision': 'RCI001-C02-dev-017', 'sources': {}}, self.job(c.BOUNDARY_JOB))
        with patch.object(c.admission, 'qualifier_entry', return_value=args), \
             patch.object(c.admission, 'verify_boundary', side_effect=ValueError(c.BOUNDARY_ERROR)):
            diagnosis = c.verify_packaging_failure({'evidence': str(self.root)}, {})
            self.assertEqual(diagnosis['disposition_preserved'], 'invalid/unknown')
        with patch.object(c.admission, 'qualifier_entry', return_value=args), \
             patch.object(c.admission, 'verify_boundary', return_value=None):
            with self.assertRaisesRegex(ValueError, 'unexpectedly admitted'):
                c.verify_packaging_failure({'evidence': str(self.root)}, {})

    def test_retained_disposition_cannot_be_reclassified_or_replace_registered_result(self):
        run = 'RCI001-C02-native-004'
        queue = self.write('queue.json', self.job(c.NATIVE_JOB))
        assessment = self.write('assessment.json', {'passed': True})
        entry = {'queue': c.identity(queue), 'assessment': c.identity(assessment)}
        record = {'id': run + '-result', 'run_id': run, 'execution_status': 'completed',
                  'validity': 'valid', 'outcome': 'success',
                  'details': {'queue_success_verified': True, 'source_result': {'passed': True}}}
        record_path = self.write('map/releases/RCI001-C02-dev-016/result-' + run + '/result-record.json', record)
        disposition = {'run_id': run, 'passed': True, 'error': None, 'entry': entry,
                       'registered_result': c.identity(record_path)}
        path = self.write('final-qualification-004/native-004/disposition.json', disposition)
        section = {'disposition': c.identity(path), 'entry': entry}
        with patch.object(c, 'HERE', self.root), patch.object(c.v4, 'MAP', self.root / 'map'):
            self.assertEqual(c.retained_disposition(section, 'native-004', 'RCI001-C02-dev-016', True, self.job(c.NATIVE_JOB)), entry)
            section['entry'] = {}
            with self.assertRaisesRegex(ValueError, 'Carried native entry'):
                c.retained_disposition(section, 'native-004', 'RCI001-C02-dev-016', True, self.job(c.NATIVE_JOB))

    def test_run_executes_only_four_new_stages_and_keeps_original_native_in_completed(self):
        value = self.readiness()
        native = {'native': 'original-entry'}
        prior = {'source_snapshot': {'path': 'old-snapshot', 'sha256': '0' * 64}}
        saves = {}
        old_ledger = c.v4.LEDGER
        with patch.object(c, 'coordinator_lock', return_value=nullcontext()), \
             patch.object(c, 'preflight', return_value=(value, prior, {'core': True}, native, {})), \
             patch.object(c, 'identity', side_effect=lambda p: {'path': str(p), 'sha256': '0' * 64}), \
             patch.object(c, 'sha', return_value='a' * 64), patch.object(c.admission, 'artifact'), \
             patch.object(c.v4, 'assert_sources'), patch.object(c.v4, 'notice'), \
             patch.object(c.v4, 'save_exact', side_effect=lambda p, v: saves.update({Path(p).name: v})), \
             patch.object(c, 'prepare_boundary', return_value={}) as boundary, \
             patch.object(c.v4, 'prepare_stage', return_value={}) as prepare, \
             patch.object(c.v4, 'launch_stage', return_value={'id': 'new'}) as launch, \
             patch.object(c.v4, 'storage_gate') as storage, patch.object(c.v4, 'assess_stage'), \
             patch.object(c.v4, 'finish_stage', side_effect=lambda folder, kind, revision, paths, core: {'kind': kind}):
            c.run(self.root / 'readiness.json', 'a' * 64)
        self.assertEqual(boundary.call_count, 1)
        self.assertEqual(prepare.call_count, 3)
        self.assertEqual(launch.call_count, 4)
        self.assertEqual(storage.call_count, 3)
        self.assertEqual([call.args[1] for call in launch.call_args_list], ['boundary', 'smoke', 'stock', 'home'])
        completed = saves['completed.json']
        self.assertEqual(completed['native'], native)
        self.assertEqual(completed['boundary'], {'kind': 'boundary'})
        self.assertEqual(len(completed['pilots']), 2)
        self.assertEqual(c.v4.LEDGER, old_ledger)


if __name__ == '__main__':
    unittest.main()
