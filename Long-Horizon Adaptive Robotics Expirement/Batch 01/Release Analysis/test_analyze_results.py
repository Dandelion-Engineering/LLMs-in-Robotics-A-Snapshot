"""Bounded synthetic lineage checks; no queue commands, real results or seeds."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import analyze_results as a


class AnalysisLineageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / 'synthetic-release'
        (self.root / 'runs').mkdir(parents=True)
        self.output = self.base / 'synthetic-analysis'
        self.selected = self.base / 'synthetic-selected.json'
        self.freeze = self.base / 'synthetic-freeze.json'
        self.readiness = self.base / 'synthetic-readiness.json'
        self.write(self.freeze, {'release_id': 'unit-analysis', 'protocol_sha256': a.protocol.protocol_sha256(),
                                 'scope': 'Synthetic unit fixture, never actual readiness'})
        self.write(self.readiness, {'release_id': 'unit-analysis', 'freeze_sha256': a.ref(self.freeze)['sha256']})
        self.manifests = a.protocol.public_run_slots('unit-analysis')
        references = []
        for manifest in self.manifests:
            manifest.update(freeze_sha256=a.ref(self.freeze)['sha256'],
                            readiness_sha256=a.ref(self.readiness)['sha256'],
                            artifact_hashes={'protocol_sha256': a.protocol.protocol_sha256()})
            path = self.root / 'runs' / (manifest['run_id'] + '.json')
            self.write(path, manifest)
            references.append({'run_id': manifest['run_id'], 'path': path.relative_to(self.root).as_posix(),
                               'sha256': a.ref(path)['sha256']})
        self.release = {'schema_version': a.protocol.SCHEMA_VERSION, 'release_id': 'unit-analysis',
                        'freeze_manifest': a.ref(self.freeze), 'readiness': a.ref(self.readiness),
                        'manifest_refs': references}
        self.write(self.root / 'release.json', self.release)
        self.selection = {'schema_version': 'selected-evaluation-results-1', 'results': [],
                          'release': a.ref(self.root / 'release.json'),
                          'implementation': a.ref(a.HERE / 'collect_results.py')}
        self.write(self.selected, self.selection)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def write(path, value):
        path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')

    def run_wrapper(self):
        with patch.object(a.release_runner, 'queued_job', return_value={'id': 'synthetic-analysis-job'}) as owned:
            with patch.object(a.protocol, '_entropy', side_effect=AssertionError('No seeds may be generated')):
                report = a.analyze_results(self.root, self.selected, self.output)
            owned.assert_called_once_with(expected_script=a.__file__)
            return report

    def failure_report(self):
        return a.protocol._load(self.output / 'analysis-provenance.json')

    def update_release(self):
        self.write(self.root / 'release.json', self.release)
        self.selection['release'] = a.ref(self.root / 'release.json')
        self.write(self.selected, self.selection)

    def test_exact_protocol_output_and_complete_input_lineage(self):
        first_block = self.manifests[0]['paired_block_id']
        pair = [m for m in self.manifests if m['paired_block_id'] == first_block and m['condition'] == 'persistent'][:2]
        self.selection['results'] = [
            {'run_id': pair[0]['run_id'], 'execution_status': 'completed', 'validity': 'valid',
             'outcome': 'success', 'completion_time_s': 10., 'wall_duration_s': 10.},
            {'run_id': pair[1]['run_id'], 'execution_status': 'timed_out', 'validity': 'valid',
             'outcome': 'failure', 'completion_time_s': None, 'wall_duration_s': None}]
        self.write(self.selected, self.selection)
        originals = {p: p.read_bytes() for p in (self.selected, self.root / 'release.json', self.freeze, self.readiness)}
        expected = a.protocol.analyze(self.manifests, self.selection['results'], **a.SETTINGS)
        report = self.run_wrapper()
        self.assertEqual(a.protocol._load(self.output / 'analysis.json'), expected)
        self.assertEqual(report, self.failure_report())
        self.assertEqual(report['schema_version'], a.SCHEMA)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['queue_job_id'], 'synthetic-analysis-job')
        self.assertEqual(report['analysis_settings'], {'bootstrap_draws': 2000, 'analysis_seed': 0})
        self.assertEqual(report['analysis'], a.ref(self.output / 'analysis.json'))
        self.assertTrue(report['inputs_unchanged'])
        self.assertEqual(report['inputs_before'], report['inputs_after'])
        self.assertEqual(len(report['protected_manifest_refs']), 264)
        for role in ('implementation', 'protocol', 'queue_authorization_implementation',
                     'selected_results', 'release', 'selection_implementation'):
            self.assertEqual(report[role], report['inputs_before'][role])
        for role in ('freeze_manifest', 'readiness'):
            self.assertEqual(report['release_authority'][role], report['inputs_before'][role])
        for protected in report['protected_manifest_refs']:
            self.assertEqual({k: v for k, v in protected.items() if k != 'run_id'},
                             report['inputs_before']['manifest:' + protected['run_id']])
        self.assertEqual(originals, {p: p.read_bytes() for p in originals})

    def test_queue_authorization_is_required_before_output_creation(self):
        with patch.object(a.release_runner, 'queued_job', side_effect=ValueError('Not queue owned')):
            with self.assertRaisesRegex(ValueError, 'Not queue owned'):
                a.analyze_results(self.root, self.selected, self.output)
        self.assertFalse(self.output.exists())

    def test_output_must_be_fresh_and_outside_originals(self):
        self.output.mkdir()
        for output in (self.output, self.root / 'runs' / 'new-analysis', a.RUNTIME / 'new-analysis'):
            with self.subTest(output=output), patch.object(a.release_runner, 'queued_job', return_value={'id': 'unit'}):
                with self.assertRaisesRegex(ValueError, 'fresh'):
                    a.analyze_results(self.root, self.selected, output)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_selected_results_must_bind_the_exact_release(self):
        self.selection['release']['sha256'] = '0' * 64
        self.write(self.selected, self.selection)
        with patch.object(a.protocol, 'analyze', side_effect=AssertionError('Must not analyze')):
            with self.assertRaises(ValueError):
                self.run_wrapper()
        self.assertEqual(self.failure_report()['status'], 'failed')
        self.assertFalse((self.output / 'analysis.json').exists())

    def test_selected_artifact_schema_and_collector_implementation_are_required(self):
        self.selection['implementation']['sha256'] = '0' * 64
        self.write(self.selected, self.selection)
        with self.assertRaises(ValueError):
            self.run_wrapper()
        self.assertEqual(self.failure_report()['status'], 'failed')

    def test_protocol_must_match_frozen_implementation(self):
        freeze = a.protocol._load(self.freeze)
        freeze['protocol_sha256'] = '0' * 64
        self.write(self.freeze, freeze)
        readiness = a.protocol._load(self.readiness)
        readiness['freeze_sha256'] = a.ref(self.freeze)['sha256']
        self.write(self.readiness, readiness)
        self.release.update(freeze_manifest=a.ref(self.freeze), readiness=a.ref(self.readiness))
        self.update_release()
        with patch.object(a.protocol, 'analyze', side_effect=AssertionError('Must not analyze')):
            with self.assertRaisesRegex(ValueError, 'frozen protocol'):
                self.run_wrapper()

    def test_changed_protected_manifest_refuses_analysis(self):
        path = self.root / self.release['manifest_refs'][0]['path']
        path.write_text(path.read_text(encoding='utf-8') + ' ', encoding='utf-8')
        with patch.object(a.protocol, 'analyze', side_effect=AssertionError('Must not analyze')):
            with self.assertRaises(ValueError):
                self.run_wrapper()
        self.assertFalse((self.output / 'analysis.json').exists())

    def test_changed_selected_bytes_during_analysis_retains_failed_derivation(self):
        original_analyze = a.protocol.analyze
        before = a.ref(self.selected)
        def mutate(*args, **kwargs):
            answer = original_analyze(*args, **kwargs)
            self.selected.write_text(self.selected.read_text(encoding='utf-8') + ' ', encoding='utf-8')
            return answer
        with patch.object(a.protocol, 'analyze', side_effect=mutate):
            with self.assertRaisesRegex(ValueError, 'changed during derivation'):
                self.run_wrapper()
        report = self.failure_report()
        self.assertEqual(report['status'], 'failed')
        self.assertFalse(report['inputs_unchanged'])
        self.assertEqual(report['inputs_before']['selected_results'], before)
        self.assertEqual(report['inputs_after']['selected_results'], a.ref(self.selected))
        self.assertEqual(report['analysis'], a.ref(self.output / 'analysis.json'))

    def test_disappearing_authority_during_analysis_is_retained_as_missing(self):
        original_analyze = a.protocol.analyze
        def remove(*args, **kwargs):
            answer = original_analyze(*args, **kwargs)
            self.readiness.unlink()
            return answer
        with patch.object(a.protocol, 'analyze', side_effect=remove):
            with self.assertRaisesRegex(ValueError, 'changed during derivation'):
                self.run_wrapper()
        report = self.failure_report()
        self.assertIsNone(report['inputs_after']['readiness']['sha256'])
        self.assertIn('error', report['inputs_after']['readiness'])
        self.assertFalse(report['inputs_unchanged'])

    def test_implementation_hash_change_cannot_publish_complete_status(self):
        original_ref, original_analyze = a.ref, a.protocol.analyze
        changed = False
        def analyze(*args, **kwargs):
            nonlocal changed
            answer = original_analyze(*args, **kwargs)
            changed = True
            return answer
        def source_ref(path):
            value = original_ref(path)
            if changed and Path(path).resolve() == Path(a.__file__).resolve():
                value = copy.deepcopy(value)
                value['sha256'] = 'f' * 64
            return value
        with patch.object(a, 'ref', side_effect=source_ref), patch.object(a.protocol, 'analyze', side_effect=analyze):
            with self.assertRaisesRegex(ValueError, 'changed during derivation'):
                self.run_wrapper()
        self.assertEqual(self.failure_report()['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
