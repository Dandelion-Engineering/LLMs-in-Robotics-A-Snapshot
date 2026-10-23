"""Small synthetic Linux filesystem tests; no WSL management or package builds."""
from __future__ import annotations
import json
import os
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import userland as u


def package(name, depends='', provides='', essential='no', version='1'):
    return dict(zip(u.FIELDS, [name, name, 'amd64', version, 'installed', '', depends, provides, essential]))


class DependencyTests(unittest.TestCase):
    def test_alternative_virtual_version_and_essential_closure(self):
        rows = {'app': package('app', 'missing | abi (>= 2), helper'),
                'provider': package('provider', provides='abi (= 2)'),
                'helper': package('helper'), 'essential': package('essential', essential='yes'),
                'unused': package('unused')}
        selected, decisions = u.resolve_packages(rows, ['app'], 'amd64',
            compare=lambda actual, op, expected: op is None or int(actual) >= int(expected))
        self.assertEqual(selected, ['app', 'essential', 'helper', 'provider'])
        self.assertTrue(any(x['selected'] == 'provider' for x in decisions))

    def test_unversioned_provider_cannot_satisfy_version(self):
        rows = {'app': package('app', 'abi (>= 2)'), 'provider': package('provider', provides='abi')}
        with self.assertRaisesRegex(ValueError, 'No installed'):
            u.resolve_packages(rows, ['app'], 'amd64', compare=lambda actual, op, wanted: op is None or actual is not None)

    def test_dependency_cycle_and_architecture_rejection(self):
        rows = {'a': package('a', 'b'), 'b': package('b', 'a')}
        self.assertEqual(u.resolve_packages(rows, ['a'], 'amd64')[0], ['a', 'b'])
        rows['b']['Architecture'] = 'arm64'
        with self.assertRaises(ValueError): u.resolve_packages(rows, ['a'], 'amd64')

    def test_usr_merge_and_private_exclusion(self):
        self.assertEqual(u.normalized_package_path('/lib/x86_64-linux-gnu/libc.so.6'), '/usr/lib/x86_64-linux-gnu/libc.so.6')
        for name in ('/home/user/secret', '/etc/shadow', '/usr/local/private', '/usr/lib/wsl/lib/x'):
            self.assertIsNone(u.normalized_package_path(name))
        with self.assertRaises(ValueError): u.normalized_package_path('/usr/../home/secret')

    def test_links_resolve_in_image_and_reject_missing_cycles(self):
        rows = {'/usr': {'type': 'directory'}, '/lib': {'type': 'symlink', 'target': 'usr/lib'},
                '/usr/lib': {'type': 'directory'}, '/usr/lib/file': {'type': 'file'},
                '/usr/link': {'type': 'symlink', 'target': '/lib/file'}}
        u.validate_links(rows)
        self.assertEqual(u.resolve_image_link('/usr/link', rows), '/usr/lib/file')
        rows['/usr/link']['target'] = '/etc/host-only'
        with self.assertRaises(ValueError): u.validate_links(rows)
        rows['/usr/link']['target'] = 'link'
        with self.assertRaises(ValueError): u.validate_links(rows)

    def test_only_owned_python_config_completes_external_runtime_link(self):
        config = '/etc/python3.12/sitecustomize.py'
        rows = {'/usr': {'type': 'directory'}, '/usr/lib': {'type': 'directory'},
                '/usr/lib/python3.12': {'type': 'directory'},
                '/usr/lib/python3.12/sitecustomize.py': {'type': 'symlink', 'target': config}}
        with self.assertRaisesRegex(ValueError, 'target missing'): u.validate_links(rows)
        self.assertEqual(u.normalized_package_path(config, 'libpython3.12-minimal'), config)
        with self.assertRaisesRegex(ValueError, 'package owner'):
            u.normalized_package_path(config, 'unrelated-package')
        self.assertIsNone(u.normalized_package_path('/etc/python3.12/private.py', 'libpython3.12-minimal'))
        rows.update({'/etc': {'type': 'directory'}, '/etc/python3.12': {'type': 'directory'},
                     config: {'type': 'file'}})
        u.validate_links(rows)
        self.assertEqual(u.resolve_image_link('/usr/lib/python3.12/sitecustomize.py', rows), config)

    def test_generated_config_no_host_services_or_cache(self):
        rows, data = u.generated({'username': 'dandelion', 'uid': 1000, 'gid': 1000, 'shell': '/bin/bash'})
        conf = data['/etc/wsl.conf'].decode()
        for value in ('systemd=false', 'ldconfig=false', '[gpu]\nenabled=false', 'appendLibPath=false',
                      'generateHosts=false', 'generateResolvConf=false', 'useWindowsTimezone=false'):
            self.assertIn(value, conf)
        self.assertNotIn('/etc/ld.so.cache', rows)
        self.assertNotIn('/etc/ld.so.preload', rows)
        self.assertEqual(rows['/home/dandelion']['uid'], 1000)
        with self.assertRaises(ValueError): u.generated({'username': 'root', 'uid': 0, 'gid': 0, 'shell': '/bin/bash'})

    def test_diagnostic_retains_every_unresolved_link_and_owners(self):
        image = {'/usr': {'type': 'directory'}, '/usr/a': {'type': 'symlink', 'target': '/etc/a'},
                 '/usr/b': {'type': 'symlink', 'target': 'missing'},
                 '/usr/good': {'type': 'symlink', 'target': 'file'}, '/usr/file': {'type': 'file'},
                 '/usr/cycle': {'type': 'symlink', 'target': 'cycle'}}
        queried = []
        def metadata(path): return {'path': path, 'exists': path != '/usr/missing', 'is_symlink': False}
        def ownership(path):
            queried.append(path); return {'path': path, 'returncode': 0, 'stdout': 'fixture-package: '+path}
        rows = u.unresolved_link_rows(image, metadata, ownership)
        self.assertEqual([r['path'] for r in rows], ['/usr/a', '/usr/b', '/usr/cycle'])
        self.assertEqual(rows[0]['image_resolved_target'], '/etc/a')
        self.assertEqual(rows[1]['host_metadata']['/usr/missing']['exists'], False)
        self.assertEqual(rows[2]['reason'], 'image_link_resolution_error')
        self.assertIn('/etc/a', rows[0]['package_ownership'])
        self.assertEqual(len(queried), len(set(queried)))

    def test_measured_locale_exception_is_exact_and_runtime_links_still_fail(self):
        name = '/usr/share/locale/af/LC_TIME/coreutils.mo'
        target = '/usr/share/locale/af/LC_MESSAGES/coreutils.mo'
        rows = {name: {'type': 'symlink', 'target': '../LC_MESSAGES/coreutils.mo'}}
        optional = {name: target}
        u.validate_links(rows, optional)
        rows['/usr/bin/python3'] = {'type': 'symlink', 'target': 'missing-python'}
        with self.assertRaisesRegex(ValueError, 'target missing'): u.validate_links(rows, optional)
        del rows['/usr/bin/python3']
        rows[name]['target'] = '../LC_MESSAGES/other.mo'
        with self.assertRaisesRegex(ValueError, 'measured absence'): u.validate_links(rows, optional)
        rows[name]['target'] = '../LC_MESSAGES/coreutils.mo'; rows[target] = {'type': 'file'}
        with self.assertRaisesRegex(ValueError, 'measured absence'): u.validate_links(rows, optional)


@unittest.skipUnless(os.name == 'posix', 'Linux modes/symlink fixtures run through the queued WSL test launcher')
class TreeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='userland-synthetic-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name); self.root = self.base/'root'; self.root.mkdir()
        for name in ('usr/bin', 'usr/lib', 'usr/sbin', 'usr/lib64', 'etc', 'home', 'root'):
            (self.root/name).mkdir(parents=True, exist_ok=True)
        for name, target in u.ALIASES.items(): (self.root/name.lstrip('/')).symlink_to(target)
        (self.root/'usr/bin/python').write_bytes(b'exact synthetic executable')
        (self.root/'etc/wsl.conf').write_bytes(b'[boot]\nsystemd=false\n')
        self.names = u.walk_scope(self.root)
        self.rows = u.inventory_paths(self.root, self.names)
        self.manifest = {'schema_version': u.SCHEMA, 'status': 'complete', 'inputs_unchanged': True,
                         'scopes': u.SCOPES, 'entries': self.rows, 'tree_sha256': u.sha(u.canonical(self.rows)),
                         'required_absent': ['/etc/ld.so.cache', '/etc/ld.so.preload', '/usr/lib/wsl', '/usr/local']}
        self.path = self.base/'manifest.json'; self.save()

    def save(self):
        self.path.write_bytes(u.canonical(self.manifest)); self.expected = u.file_sha(self.path)

    def verify(self): return u.verify(self.root, self.path, self.expected)

    def test_exact_identity_ignores_mtime_only(self):
        self.assertTrue(self.verify()['verified'])
        os.utime(self.root/'usr/bin/python', (2, 3))
        self.assertTrue(self.verify()['verified'])

    def test_content_mutation_rejected(self):
        (self.root/'usr/bin/python').write_bytes(b'changed synthetic binary')
        with self.assertRaisesRegex(ValueError, 'content'): self.verify()

    def test_packaged_etc_target_content_is_verified(self):
        directory = self.root/'etc/python3.12'; directory.mkdir()
        config = directory/'sitecustomize.py'; config.write_bytes(b'try:\n import optional_hook\nexcept ImportError:\n pass\n')
        (self.root/'usr/lib/sitecustomize.py').symlink_to('/etc/python3.12/sitecustomize.py')
        self.manifest['entries'] = u.inventory_paths(self.root, u.walk_scope(self.root))
        self.manifest['tree_sha256'] = u.sha(u.canonical(self.manifest['entries'])); self.save()
        self.assertTrue(self.verify()['verified'])
        config.write_bytes(b'changed package configuration')
        with self.assertRaisesRegex(ValueError, 'content'): self.verify()

    def test_mode_mutation_rejected(self):
        path = self.root/'usr/bin/python'; path.chmod(path.stat().st_mode ^ 0o100)
        with self.assertRaisesRegex(ValueError, 'mode'): self.verify()

    def test_symlink_target_mutation_rejected(self):
        (self.root/'bin').unlink(); (self.root/'bin').symlink_to('usr/sbin')
        with self.assertRaisesRegex(ValueError, 'link'): self.verify()

    def test_unknown_addition_and_file_removal_rejected(self):
        extra = self.root/'etc/injected'; extra.write_text('not declared')
        with self.assertRaisesRegex(ValueError, 'path set'): self.verify()
        extra.unlink(); (self.root/'usr/bin/python').unlink()
        with self.assertRaisesRegex(ValueError, 'path set'): self.verify()

    def test_cache_and_wsl_injection_rejected(self):
        cache = self.root/'etc/ld.so.cache'; cache.write_bytes(b'host cache')
        with self.assertRaisesRegex(ValueError, 'absent'): self.verify()
        cache.unlink(); (self.root/'usr/lib/wsl').mkdir()
        with self.assertRaisesRegex(ValueError, 'absent'): self.verify()

    def test_manifest_tamper_and_owner_mismatch_rejected(self):
        self.path.write_bytes(self.path.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError, 'Manifest hash'): self.verify()
        self.rows['/usr/bin/python']['uid'] += 1
        self.manifest['tree_sha256'] = u.sha(u.canonical(self.rows)); self.save()
        with self.assertRaisesRegex(ValueError, 'owner'): self.verify()

    def test_explicit_time_budget_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, 'time bound'):
            u.verify(self.root, self.path, self.expected, seconds=1e-12)

    def test_optional_locale_absence_before_after_and_live_target_addition(self):
        name = '/usr/share/locale/af/LC_TIME/coreutils.mo'; target = name.replace('/LC_TIME/', '/LC_MESSAGES/')
        link = self.root/name.lstrip('/'); link.parent.mkdir(parents=True)
        absent = self.root/target.lstrip('/'); absent.parent.mkdir(parents=True)
        link.symlink_to('../LC_MESSAGES/coreutils.mo')
        before = u.optional_source_absence({name: target}, self.root)
        self.assertEqual(before, u.optional_source_absence({name: target}, self.root))
        self.manifest['entries'] = u.inventory_paths(self.root, u.walk_scope(self.root))
        self.manifest['tree_sha256'] = u.sha(u.canonical(self.manifest['entries']))
        self.manifest['required_absent'].append(target); self.save()
        self.assertTrue(self.verify()['verified'])
        absent.write_bytes(b'new translation')
        with self.assertRaisesRegex(ValueError, 'no longer absent'): u.optional_source_absence({name: target}, self.root)
        with self.assertRaisesRegex(ValueError, 'absent'): self.verify()


if __name__ == '__main__': unittest.main(verbosity=2)
