"""Deferred synthetic registration tests; actual Map validator, no physics/queue."""
import importlib.util
import json
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

import stage_registration_patch as staging

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parents[1] / 'Runtime'
sys.path.insert(0, str(RUNTIME))
import record_attempt as records


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


candidate = module(HERE / 'staged-001' / 'release_runner.candidate.py', '_staged_registration_candidate')
original = module(HERE / 'staged-001' / 'release_runner.base.py', '_staged_registration_original')


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    return {'path': str(path), 'sha256': candidate.digest(path)}


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.map = self.base / 'Architecture Map'; self.map.mkdir()
        self.runtime = self.base / 'Runtime'; self.runtime.mkdir()
        (self.runtime / 'protocol.py').write_text('# synthetic protocol only\n', encoding='utf-8')
        self.release = self.base / 'Evidence' / 'prepared' / 'synthetic-release'
        self.release.mkdir(parents=True)
        self.bundle = self.release / 'runtime.zip'
        with zipfile.ZipFile(self.bundle, 'w') as archive:
            archive.writestr('candidate.py', b'# exact synthetic executable bytes\r\n')
        self.bundle_bytes = self.bundle.read_bytes()
        self.indexes = {}
        for role in ('code', 'environment', 'model'):
            self.indexes[role] = save(self.release / (role + '-index.json'),
                {'bundle': {'path': 'runtime.zip', 'sha256': candidate.digest(self.bundle)}} if role == 'code'
                else {'synthetic_only': role})
        self.freeze = self.release / 'freeze.json'
        freeze_ref = save(self.freeze, {'release_id': 'synthetic-release', 'artifacts': self.indexes})
        self.freeze_bytes = self.freeze.read_bytes()
        save(self.release / 'release.json', {'freeze_manifest': freeze_ref})
        data = {kind: [] for kind in records.am.KINDS}
        for identity in ('B01-C0', 'B01-A1', 'B01-A2', 'B01-A3'):
            data['architecture'].append({**records.common(identity, ['synthetic']),
                'title': identity, 'summary': 'Synthetic registration test only'})
        for kind, name in records.am.KINDS.items():
            (self.map / name).write_text(''.join(json.dumps(row) + '\n' for row in data[kind]), encoding='utf-8')
        self.patches = [patch.object(records, 'MAP', self.map), patch.object(candidate, 'HERE', self.runtime),
                        patch.object(original, 'HERE', self.runtime)]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def context(self, architecture='baseline', index=1):
        manifest = {'run_id': 'synthetic-release-' + architecture + '-' + str(index),
            'release_id': 'synthetic-release', 'architecture': architecture,
            'freeze_sha256': candidate.digest(self.freeze),
            'artifact_hashes': {**{role + '_sha256': ref['sha256'] for role, ref in self.indexes.items()},
                                'protocol_sha256': candidate.digest(self.runtime / 'protocol.py')},
            'condition': 'persistent', 'protocol_id': 'synthetic-protocol', 'scenario_id': 'synthetic-case',
            'paired_block_id': 'synthetic-block', 'replicate': 1, 'scheduled_index': index, 'parts': 3, 'cap_s': 1.,
            'seeds': {'world_seed': 11, 'layout_seed': 12, 'policy_seed': 13, 'noise_seed': 14}}
        manifest_ref = save(self.release / 'runs' / (manifest['run_id'] + '.json'), manifest)
        artifacts = {'code_bundle': str(self.bundle), 'model_identity': {'synthetic': True},
                     'index_paths': {role: ref['path'] for role, ref in self.indexes.items()}}
        return SimpleNamespace(manifest=manifest, release_dir=self.release,
            artifacts_json=json.dumps(artifacts), manifest_sha256=manifest_ref['sha256'], queue_job_id='synthetic-queue')

    def snapshot_map(self):
        return {name: (self.map / name).read_bytes() for name in records.am.KINDS.values()}

    def test_external_attachments_fail_before_patch_and_all_four_reuse_exact_local_copies(self):
        context = self.context()
        original_manifest = (self.release / 'runs' / (context.manifest['run_id'] + '.json')).read_bytes()
        with self.assertRaisesRegex(ValueError, 'within the map folder'):
            original.register_attempt(context)
        candidate.register_attempt(context)
        retained = self.map / 'releases' / 'synthetic-release'
        before = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in retained.iterdir()}
        for architecture in ('A1', 'A2', 'A3'):
            candidate.register_attempt(self.context(architecture))
        candidate.register_attempt(self.context('baseline', 2))
        self.assertEqual(before, {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in retained.iterdir()})
        self.assertEqual((retained / 'code-bundle.zip').read_bytes(), self.bundle_bytes)
        self.assertEqual((retained / 'freeze.json').read_bytes(), self.freeze_bytes)
        self.assertEqual(self.bundle.read_bytes(), self.bundle_bytes)
        self.assertEqual(self.freeze.read_bytes(), self.freeze_bytes)
        self.assertEqual((self.release / 'runs' / (context.manifest['run_id'] + '.json')).read_bytes(), original_manifest)
        data, _, errors = records.am.read_store(self.map)
        self.assertEqual(errors + records.am.validate_records(data, self.map), [])
        self.assertEqual(len(data['revision']), 4)
        self.assertEqual(len(data['run']), 5)
        for revision in data['revision']:
            self.assertEqual([(self.map / ref['uri']).resolve() for ref in revision['attachments']],
                             [retained / 'code-bundle.zip', retained / 'freeze.json'])
        for run in data['run']:
            code_ref = run['frozen_refs']['code']['refs'][0]
            self.assertEqual((self.map / code_ref['uri']).resolve(), Path(self.indexes['code']['path']))
            protocol_ref = run['frozen_refs']['protocol']['refs'][0]
            self.assertEqual((self.map / protocol_ref['uri']).resolve(), self.runtime / 'protocol.py')
            seed_ref = run['seeds']['refs'][0]
            self.assertEqual((self.map / seed_ref['uri']).resolve(), self.release / 'runs' / (run['id'] + '.json'))

    def test_preexisting_partial_copy_is_preserved_and_no_revision_or_other_copy_is_created(self):
        retained = self.map / 'releases' / 'synthetic-release'; retained.mkdir(parents=True)
        broken = retained / 'code-bundle.zip'; broken.write_bytes(b'partial')
        before = self.snapshot_map()
        with self.assertRaisesRegex(candidate.ReleaseError, 'partial or differs'):
            candidate.register_attempt(self.context())
        self.assertEqual(broken.read_bytes(), b'partial')
        self.assertFalse((retained / 'freeze.json').exists())
        self.assertEqual(before, self.snapshot_map())

    def test_retained_tamper_or_revision_attachment_retarget_refuses_reuse(self):
        candidate.register_attempt(self.context())
        retained = self.map / 'releases' / 'synthetic-release' / 'freeze.json'
        retained.write_bytes(b'tampered')
        before = self.snapshot_map()
        with self.assertRaises(candidate.ReleaseError): candidate.register_attempt(self.context('baseline', 2))
        self.assertEqual(before, self.snapshot_map())
        self.assertEqual(retained.read_bytes(), b'tampered')
        # Synthetic restoration only; no real evidence is changed by this test.
        retained.write_bytes(self.freeze_bytes)
        data, _, _ = records.am.read_store(self.map)
        data['revision'][0]['attachments'][0]['uri'] = 'releases/unrelated/code-bundle.zip'
        (self.map / 'revisions.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in data['revision']), encoding='utf-8')
        before = self.snapshot_map()
        with self.assertRaisesRegex(candidate.ReleaseError, 'retained attachments differ'):
            candidate.register_attempt(self.context('baseline', 3))
        self.assertEqual(before, self.snapshot_map())

    def test_changed_original_bundle_is_rejected_without_retention_or_registration(self):
        context = self.context(); before = self.snapshot_map()
        self.bundle.write_bytes(b'changed external bundle')
        with self.assertRaises(candidate.ReleaseError): candidate.register_attempt(context)
        self.assertEqual(before, self.snapshot_map())
        self.assertFalse((self.map / 'releases' / 'synthetic-release').exists())

    def test_concurrent_exclusive_creation_accepts_only_exact_existing_bytes(self):
        directory = self.map / 'releases' / 'synthetic-race'; directory.mkdir(parents=True)
        original_open = Path.open
        expected = candidate.digest(self.bundle)
        for exact in (True, False):
            target = directory / ('exact.zip' if exact else 'partial.zip')
            def raced(path, mode='r', *args, **kwargs):
                if path == target and mode == 'xb':
                    with original_open(path, 'wb') as stream:
                        stream.write(self.bundle_bytes if exact else b'partial')
                    raise FileExistsError('Synthetic competing creator')
                return original_open(path, mode, *args, **kwargs)
            with self.subTest(exact=exact), patch.object(Path, 'open', raced):
                if exact:
                    candidate._retain_registration_file(self.bundle, target, expected)
                else:
                    with self.assertRaisesRegex(candidate.ReleaseError, 'partial or differs'):
                        candidate._retain_registration_file(self.bundle, target, expected)
            self.assertEqual(target.read_bytes(), self.bundle_bytes if exact else b'partial')

    def test_unsafe_and_reparse_targets_fail_without_map_mutation(self):
        before = self.snapshot_map()
        for release_id in ('../outside', 'CON', 'trailing.'):
            with self.subTest(release_id=release_id), self.assertRaises(candidate.ReleaseError):
                candidate.retained_revision_attachments(self.map, release_id, self.bundle,
                    candidate.digest(self.bundle), self.freeze, candidate.digest(self.freeze))
        original_lstat = Path.lstat
        def reparse(path):
            if path == self.map / 'releases':
                return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
            return original_lstat(path)
        with patch.object(Path, 'lstat', reparse), self.assertRaisesRegex(candidate.ReleaseError, 'Reparse'):
            candidate.register_attempt(self.context())
        self.assertEqual(before, self.snapshot_map())

    def test_staging_rejects_changed_base_and_matches_exact_retained_candidate(self):
        base = (HERE / 'staged-001' / 'release_runner.base.py').read_bytes()
        self.assertEqual(staging.candidate_bytes(base), (HERE / 'staged-001' / 'release_runner.candidate.py').read_bytes())
        with self.assertRaisesRegex(ValueError, 'base differs'):
            staging.candidate_bytes(base + b'\n')


if __name__ == '__main__':
    unittest.main()
