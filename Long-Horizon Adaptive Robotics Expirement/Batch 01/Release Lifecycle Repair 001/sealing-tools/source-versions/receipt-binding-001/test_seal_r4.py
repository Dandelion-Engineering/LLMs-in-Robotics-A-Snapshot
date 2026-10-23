"""Deferred synthetic checks of strict index relocation; no Runtime imports."""
import ast
from pathlib import Path
import unittest


class RelocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).with_name('seal_r4.py')
        tree = ast.parse(path.read_text(encoding='utf-8'))
        names = {'require', 'relocate_paths', 'compare_relocated_indexes'}
        nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        if len(nodes) != len(names): raise AssertionError('Missing exact source functions')
        cls.ns = {}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), cls.ns)

    def setUp(self):
        self.old = str((Path.cwd() / 'synthetic-original' / 'Runtime').resolve())
        self.new = str((Path.cwd() / 'synthetic-original' / 'Runtime 004').resolve())
        self.ns['ORIGINAL_RUNTIME'] = Path(self.old)
        self.ns['RUNTIME'] = Path(self.new)
        self.before = {'model': {'config': {'request_timeout_s': 30}, 'files': [
            {'path': self.old + '/vendor/model/model.bin', 'sha256': 'a' * 64, 'bytes': 10}]},
            'environment': {'files': [{'path': self.old + '/vendor/panda/scene.xml', 'sha256': 'b' * 64}],
                            'probes': [{'name': 'tree', 'stdout_sha256': 'c' * 64}]}}
        self.after = self.ns['relocate_paths'](self.before, self.old, self.new)
        self.inputs = {'path_relocations': [{'from': self.old, 'to': self.new}]}
        self.files = {'previous_prepared': Path('old/prepared.json'), 'prepared': Path('new/prepared.json')}
        self.previous = {'artifacts': {k: {'path': 'old/' + k} for k in self.before}}
        self.prepared = {'artifacts': {k: {'path': 'new/' + k} for k in self.after}}
        self.ns['bound'] = lambda ref, base: ref['path']
        self.ns['load'] = lambda name: (self.before if name.startswith('old/') else self.after)[name.split('/')[1]]

    def check_indexes(self):
        self.ns['compare_relocated_indexes'](self.inputs, self.files, self.previous, self.prepared)

    def test_exact_relocation_preserves_every_hash_and_setting(self):
        self.check_indexes()
        self.assertEqual(self.after['model']['files'][0]['sha256'], 'a' * 64)
        self.assertEqual(self.before['model']['files'][0]['path'], self.old + '/vendor/model/model.bin')

    def test_prefix_siblings_and_embedded_prose_are_not_relocated(self):
        values = [self.old + '-other/a', 'prefix ' + self.old + '/a', self.old]
        self.assertEqual(self.ns['relocate_paths'](values, self.old, self.new), values[:2] + [self.new])

    def test_asset_byte_change_is_rejected(self):
        self.after['model']['files'][0]['sha256'] = 'd' * 64
        with self.assertRaises(ValueError): self.check_indexes()

    def test_model_setting_change_is_rejected(self):
        self.after['model']['config']['request_timeout_s'] = 31
        with self.assertRaises(ValueError): self.check_indexes()

    def test_environment_probe_change_is_rejected(self):
        self.after['environment']['probes'][0]['stdout_sha256'] = 'd' * 64
        with self.assertRaises(ValueError): self.check_indexes()

    def test_additional_relocation_permission_is_rejected(self):
        self.inputs['path_relocations'].append({'from': '/arbitrary', 'to': '/other'})
        with self.assertRaises(ValueError): self.check_indexes()


if __name__ == '__main__': unittest.main()
