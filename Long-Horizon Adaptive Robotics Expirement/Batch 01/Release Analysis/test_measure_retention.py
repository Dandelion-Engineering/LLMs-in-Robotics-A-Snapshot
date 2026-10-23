"""Bounded synthetic metadata tests; defer during physical timing runs."""
import contextlib
import copy
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import measure_retention as retention

sys.path.insert(0, str(retention.RUNTIME))
import development_storage as storage
import record_attempt as recorder


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.project = self.base / 'experiment'; self.project.mkdir()
        self.map = self.project / 'Architecture Map'; self.map.mkdir()
        self.legacy = self.project / 'Evidence' / 'raw'
        self.explicit = self.base / 'explicit-development-raw'
        self.data = {kind: [] for kind in recorder.am.KINDS}
        queue = SimpleNamespace(__file__=str(retention.RUNTIME / 'release_runner.py'),
            queued_job=lambda **kwargs: {'id': 'synthetic-retention-job'})
        self.patches = [patch.object(recorder, 'MAP', self.map),
            patch.object(storage, 'DEFAULT_RAW_ROOT', self.legacy),
            patch.object(retention, 'EXPERIMENT', self.project),
            patch.object(retention, 'runtime_modules', return_value=(queue, recorder, storage))]
        for item in self.patches:
            item.start()
        self.flush_map()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def flush_map(self):
        for kind, filename in recorder.am.KINDS.items():
            (self.map / filename).write_text(''.join(json.dumps(row) + '\n' for row in self.data[kind]), encoding='utf-8')

    def add(self, identity, *, legacy=False, completed=True, seconds=2., outcome='failure'):
        assigned = storage.location(identity, self.legacy if legacy else self.explicit)
        manifest = {'run_id': identity}
        if not legacy:
            manifest['development_storage'] = assigned
        source = self.map / 'releases' / identity / 'manifest.json'
        source.parent.mkdir(parents=True)
        source.write_text(json.dumps(manifest), encoding='utf-8')
        self.data['run'].append({'id': identity, 'stage': 'development', 'frozen_refs': {'protocol': {'refs': [
            {'uri': source.relative_to(self.map).as_posix(), 'sha256': retention.digest(source), 'state': 'available'}]}}})
        self.flush_map()
        root = Path(assigned['evidence_dir'])
        result = {'run_id': identity, 'wall_duration_s': seconds, 'outcome': outcome, 'validity': 'unknown',
                  'execution_status': 'failed' if outcome == 'failure' else 'completed'}
        if not legacy:
            result.update(stage='development', development_storage=assigned)
        if completed:
            root.mkdir(parents=True)
            (root / 'result.json').write_text(json.dumps(result), encoding='utf-8')
            (root / 'manifest.json').write_text(json.dumps(result), encoding='utf-8')
            (root / 'frames').mkdir()
            (root / 'frames' / 'frame.bin').write_bytes(b'synthetic-frame-only')
        return root, result, source

    def measure(self, name='inventory'):
        output = self.base / name
        with contextlib.redirect_stdout(io.StringIO()):
            retention.measure(output)
        return json.loads((output / 'summary.json').read_text(encoding='utf-8'))

    def test_legacy_and_explicit_registered_roots_preserve_rate_and_schema(self):
        first, _, _ = self.add('B01-dev-legacy', legacy=True, seconds=1.)
        second, _, _ = self.add('B01-dev-explicit', outcome='partial')
        self.data['result'].append({'id': 'B01-dev-explicit-result', 'run_id': 'B01-dev-explicit',
            'outcome': 'corrected-label-is-not-interpreted', 'evidence': [{'uri': str(second / 'result.json'),
                'state': 'available', 'sha256': retention.digest(second / 'result.json')}]})
        self.data['result'].append({'id': 'B01-dev-legacy-result', 'run_id': 'B01-dev-legacy',
            'evidence': [{'uri': '../Evidence/raw/B01-dev-legacy/result.json',
                'state': 'available', 'sha256': retention.digest(first / 'result.json')}]})
        unrelated = self.legacy / 'B01-dev-unregistered'; unrelated.mkdir()
        (unrelated / 'result.json').write_text('{"run_id":"wrong"}', encoding='utf-8')
        self.data['run'].append({'id': 'scored-excluded', 'stage': 'evaluation'})
        self.flush_map()
        summary = self.measure()
        self.assertEqual(summary['schema_version'], 'robot-retention-inventory-1.0')
        self.assertEqual({row['run_id'] for row in summary['runs']}, {'B01-dev-legacy', 'B01-dev-explicit'})
        for row in summary['runs']:
            expected = first if row['run_id'].endswith('legacy') else second
            self.assertEqual(Path(row['result']['path']), expected / 'result.json')
            self.assertEqual(row['result_run_id'], row['run_id'])
            self.assertEqual(row['result']['sha256'], retention.digest(expected / 'result.json'))
            self.assertEqual(row['retained_bytes'], sum(item['bytes'] for item in retention.inventory(expected)))
            self.assertEqual(row['mib_per_task_second'], row['retained_bytes'] / retention.MIB / row['wall_duration_s'])
        self.assertEqual(summary['maximum_measured_mib_per_task_second'], max(row['mib_per_task_second'] for row in summary['runs']))
        self.assertEqual(summary['planning_rate_mib_per_task_second'], max(3., summary['maximum_measured_mib_per_task_second']))
        self.assertEqual(summary['reserve_bytes'], 50 * retention.GIB)
        self.assertEqual(summary['full_unstarted_release_maximum_task_seconds'], 156600)
        self.assertEqual(summary['capacity_path'], str(self.project))
        self.assertTrue(next(row for row in summary['runs'] if row['run_id'].endswith('legacy'))['legacy_missing_raw_stage'])
        self.assertEqual(next(row for row in summary['runs'] if row['run_id'].endswith('explicit'))['map_result_binding_state'], 'bound')

    def test_missing_completed_result_is_explicit_and_evaluation_is_not_discovered(self):
        self.add('B01-dev-complete')
        _, _, source = self.add('B01-dev-planned', completed=False)
        self.data['run'].append({'id': 'evaluation-not-opened', 'stage': 'evaluation'})
        self.flush_map()
        summary = self.measure()
        self.assertEqual([row['run_id'] for row in summary['registered_without_completed_result']], ['B01-dev-planned'])
        self.assertTrue(source.exists())

    def test_duplicate_registration_and_modified_pinned_manifest_fail_closed(self):
        _, _, source = self.add('B01-dev-identity')
        self.data['run'].append(copy.deepcopy(self.data['run'][0])); self.flush_map()
        with self.assertRaisesRegex(ValueError, 'Duplicate registered run'):
            retention.registered_bundles(recorder, storage)
        self.data['run'].pop(); self.flush_map()
        source.write_text(source.read_text(encoding='utf-8') + ' ', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'immutable map binding'):
            retention.registered_bundles(recorder, storage)

    def test_wrong_raw_identity_stage_storage_and_manifest_are_rejected(self):
        root, original, _ = self.add('B01-dev-identity')
        for change in ('run', 'stage', 'storage', 'manifest', 'nonterminal'):
            with self.subTest(change=change):
                result = copy.deepcopy(original); manifest = copy.deepcopy(original)
                if change == 'run': result['run_id'] = 'another-run'
                if change == 'stage': result['stage'] = 'evaluation'
                if change == 'storage': result['development_storage']['evidence_dir'] = str(self.base / 'elsewhere')
                if change == 'manifest': manifest['run_id'] = 'another-run'
                if change == 'nonterminal': result['execution_status'] = 'running'
                (root / 'result.json').write_text(json.dumps(result), encoding='utf-8')
                (root / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
                with self.assertRaises(ValueError): self.measure('refused-' + change)
                self.assertFalse((self.base / ('refused-' + change) / 'summary.json').exists())

    def test_duplicate_or_mismatched_assigned_path_is_rejected(self):
        self.add('B01-dev-one'); self.add('B01-dev-two')
        original = recorder.registered_storage
        def mismatched(identity):
            assigned, legacy, reference = original(identity)
            if identity == 'B01-dev-two':
                assigned = {**assigned, 'evidence_dir': str(self.explicit / 'B01-dev-one')}
            return assigned, legacy, reference
        with patch.object(recorder, 'registered_storage', side_effect=mismatched):
            with self.assertRaisesRegex(ValueError, 'Duplicate or mismatched'):
                retention.registered_bundles(recorder, storage)

    def test_reparse_ancestor_and_entry_are_rejected_before_traversal(self):
        root, _, _ = self.add('B01-dev-reparse')
        original = Path.lstat
        for target in (self.explicit, root / 'frames' / 'frame.bin'):
            def marked(path, *, _target=target):
                if path == _target:
                    return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
                return original(path)
            with self.subTest(target=target), patch.object(Path, 'lstat', marked):
                with self.assertRaisesRegex(ValueError, 'Symlink/reparse'):
                    retention.inventory(root)
                if target == self.explicit:
                    with patch.object(recorder, 'registered_storage', side_effect=AssertionError('Must reject before resolving')):
                        with self.assertRaisesRegex(ValueError, 'Symlink/reparse'):
                            retention.registered_bundles(recorder, storage)

    def test_recorded_result_hash_and_identity_duplicates_are_rejected(self):
        root, _, _ = self.add('B01-dev-recorded')
        self.data['result'].append({'id': 'registered-result', 'run_id': 'B01-dev-recorded',
            'evidence': [{'uri': str(root / 'result.json'), 'sha256': '0' * 64, 'state': 'available'}]})
        self.flush_map()
        with self.assertRaisesRegex(ValueError, 'Registered raw result reference differs'):
            self.measure('wrong-result-ref')
        self.data['result'].append(copy.deepcopy(self.data['result'][0])); self.flush_map()
        with self.assertRaisesRegex(ValueError, 'Duplicate registered result'):
            retention.registered_bundles(recorder, storage)

    def test_changed_registration_store_or_file_metadata_prevents_summary(self):
        root, _, _ = self.add('B01-dev-stability')
        original = retention.inventory
        for change in ('map', 'metadata'):
            changed = False
            def unstable(path):
                nonlocal changed
                value = original(path)
                if not changed:
                    changed = True
                    if change == 'map':
                        with (self.map / 'runs.jsonl').open('a', encoding='utf-8') as stream: stream.write(' ')
                    else:
                        with (root / 'frames' / 'frame.bin').open('ab') as stream: stream.write(b'changed')
                return value
            with self.subTest(change=change), patch.object(retention, 'inventory', side_effect=unstable):
                with self.assertRaises(ValueError): self.measure('changed-' + change)
            self.assertFalse((self.base / ('changed-' + change) / 'summary.json').exists())
            self.flush_map()


if __name__ == '__main__':
    unittest.main()
