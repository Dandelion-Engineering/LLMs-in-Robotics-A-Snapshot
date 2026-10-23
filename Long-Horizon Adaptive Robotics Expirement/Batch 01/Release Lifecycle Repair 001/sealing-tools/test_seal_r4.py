"""Deferred synthetic relocation and receipt-binding checks; no Runtime imports."""
import ast
import copy
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


class VerificationReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).with_name('seal_r4.py')
        tree = ast.parse(path.read_text(encoding='utf-8'))
        names = {'require', 'verification_report'}
        nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        if len(nodes) != len(names): raise AssertionError('Missing exact source functions')
        cls.functions = ast.Module(body=nodes, type_ignores=[])
        cls.source_path = path

    def setUp(self):
        self.base = Path.cwd() / 'synthetic-report-inputs'
        self.path = self.base / 'review' / 'pair-validation.json'
        self.item = {'path': str(self.path), 'sha256': 'a' * 64}
        self.source = {'path': str(self.path.parent / 'source.py'), 'sha256': 'b' * 64}
        self.report = {'all_required_checks_passed': True, 'queue_job_id': 'review-own',
                       'source_files': [self.source], 'sources_unchanged': True}
        self.receipts = {}
        self.verified = []
        self.bound_items = []
        self.ns = {}
        exec(compile(self.functions, str(self.source_path), 'exec'), self.ns)
        self.ns.update(bound=self.bound, load=lambda path: self.report,
                       official=self.official, ref=lambda path: self.item)

    def receipt(self, name, job_id, valid=True):
        path = self.path.parent / (name + '.json')
        item = {'path': str(path), 'sha256': name + '-synthetic-hash'}
        self.receipts[path] = (item, {'id': job_id, 'state': 'succeeded' if valid else 'failed',
                                    'exit_status': 0 if valid else 1})
        return item

    def bound(self, item, base):
        self.bound_items.append(copy.deepcopy(item))
        path = Path(item['path'])
        if not path.is_absolute(): path = base / path
        if path in self.receipts:
            self.assertEqual(item['sha256'], self.receipts[path][0]['sha256'])
        return path

    def official(self, path):
        self.verified.append(path)
        value = self.receipts[path][1]
        if value['state'] != 'succeeded' or value['exit_status'] != 0:
            raise ValueError('Successful official receipt required')
        return value

    def check(self):
        return self.ns['verification_report'](self.item, self.base)

    def test_embedded_prerequisites_and_explicit_own_receipt_all_verified(self):
        embedded = [self.receipt(name, name) for name in ('execution', 'finish', 'derive')]
        self.report['official_receipts'] = embedded
        self.item['receipt'] = self.receipt('review', 'review-own')
        before = copy.deepcopy(self.report)
        self.assertEqual(self.check(), self.item)
        self.assertEqual(self.verified, [Path(r['path']) for r in embedded + [self.item['receipt']]])
        self.assertIn(self.source, self.bound_items)
        self.assertEqual(self.report, before)

    def test_missing_or_mismatched_own_receipt_rejected(self):
        self.report['official_receipts'] = [self.receipt('execution', 'execution')]
        for own_id in (None, 'other-review'):
            with self.subTest(own_id=own_id):
                self.item.pop('receipt', None)
                if own_id is not None: self.item['receipt'] = self.receipt('review', own_id)
                with self.assertRaisesRegex(ValueError, 'report job lacks'):
                    self.check()

    def test_failed_explicit_or_embedded_receipt_is_not_ignored(self):
        own = self.receipt('own', 'review-own')
        bad = self.receipt('failed', 'failed-job', valid=False)
        for embedded, explicit in (([own], bad), ([bad], own)):
            with self.subTest(embedded=embedded, explicit=explicit):
                self.report['official_receipts'] = embedded
                self.item['receipt'] = explicit
                with self.assertRaisesRegex(ValueError, 'Successful official receipt required'):
                    self.check()

    def test_existing_list_single_and_external_only_receipts_supported(self):
        own = self.receipt('own', 'review-own')
        for form in ('list', 'single', 'external'):
            with self.subTest(form=form):
                self.report.pop('official_receipts', None)
                self.report.pop('official_receipt', None)
                self.item.pop('receipt', None)
                self.verified.clear()
                if form == 'list': self.report['official_receipts'] = [own]
                elif form == 'single': self.report['official_receipt'] = own
                else: self.item['receipt'] = own
                self.assertEqual(self.check(), self.item)
                self.assertEqual(self.verified, [Path(own['path'])])


if __name__ == '__main__': unittest.main()
