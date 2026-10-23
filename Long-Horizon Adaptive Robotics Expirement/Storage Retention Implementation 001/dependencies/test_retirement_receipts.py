"""Synthetic boundary tests; never access project evidence or real receipts."""
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import copy

import reconcile_retirement_receipts as subject
from compare_policy_records import comparable


class ReceiptReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / 'manifest.jsonl.gz'
        self.receipts = self.root / 'receipts'
        self.receipts.mkdir()
        self.rows = [{'path': subject.PREFIX + f'run-1/evidence/frames/{i:06d}.png',
                      'run_id': 'run-1', 'frame_id': i, 'artifact_type': 'rgb',
                      'logical_bytes': i + 10, 'policy': subject.POLICY}
                     for i in range(2001)]
        self.write_manifest()
        for batch_id, start in enumerate(range(0, len(self.rows), subject.BATCH_SIZE)):
            rows = self.rows[start:start + subject.BATCH_SIZE]
            common = {'manifest_sha256': self.ref['sha256'], 'first_ordinal': start,
                      'count': len(rows), 'logical_bytes': sum(r['logical_bytes'] for r in rows)}
            self.write(f'{batch_id:05d}-intent.json', {**common, 'created': '2026-09-27T02:00:00+00:00'})
            paths_hash = hashlib.sha256(('\n'.join(r['path'] for r in rows) + '\n').encode()).hexdigest()
            self.write(f'{batch_id:05d}-complete.json', {**common, 'finished': '2026-09-27T02:00:00+00:00',
                                                       'removed_paths_sha256': paths_hash})
        self.completion = {'status': 'completed', 'policy': subject.POLICY,
                           'manifest_sha256': self.ref['sha256'], 'files': self.ref['files'],
                           'logical_bytes': self.ref['logical_bytes'],
                           'started': '2026-09-27T01:59:00+00:00', 'finished': '2026-09-27T02:01:00+00:00',
                           'disk_before': {'total': 100, 'used': 50, 'free': 50},
                           'disk_after': {'total': 100, 'used': 40, 'free': 60},
                           'observed_free_space_increase_bytes': 10}

    def write_manifest(self):
        with gzip.open(self.manifest, 'wt', encoding='utf-8') as f:
            for row in self.rows:
                f.write(json.dumps(row) + '\n')
        self.ref = {'sha256': subject.sha(self.manifest), 'files': len(self.rows),
                    'logical_bytes': sum(r['logical_bytes'] for r in self.rows)}

    def write(self, name, value):
        (self.receipts / name).write_text(json.dumps(value), encoding='utf-8')

    def check(self):
        return subject.reconcile(self.manifest, self.ref, self.receipts, self.completion)

    def test_full_batch_and_short_final_batch(self):
        result = self.check()
        self.assertEqual((result['files'], result['batch_count'], result['receipt_count'], result['final_batch_files']),
                         (2001, 2, 4, 1))
        self.assertEqual(result['ordered_removed_paths_sha256'],
                         hashlib.sha256(('\n'.join(r['path'] for r in self.rows) + '\n').encode()).hexdigest())
        # The fixture has no original evidence paths: successful checking proves
        # that reconciliation does not require accessing a supposedly deleted leaf.
        self.assertEqual(set(p.name for p in self.root.iterdir()), {'manifest.jsonl.gz', 'receipts'})

    def test_tampered_receipt_identity_counts_bytes_and_exact_paths(self):
        name = '00001-complete.json'
        original = subject.read(self.receipts / name)
        for key, value in [('first_ordinal', 1999), ('count', 2), ('count', True),
                           ('logical_bytes', 9), ('manifest_sha256', '0' * 64),
                           ('removed_paths_sha256', 'f' * 64),
                           ('finished', '2026-09-27T02:02:00+00:00')]:
            with self.subTest(key=key, value=value):
                self.write(name, {**original, key: value})
                with self.assertRaises(ValueError):
                    self.check()
        self.write(name, original)

    def test_missing_extra_or_failure_receipts(self):
        leaf = self.receipts / '00001-complete.json'
        raw = leaf.read_bytes()
        leaf.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing/extra/failure'):
            self.check()
        leaf.write_bytes(raw)
        for name in ('00001-failure.json', '00002-complete.json', 'unexpected.txt'):
            with self.subTest(name=name):
                extra = self.receipts / name
                extra.write_text('{}')
                with self.assertRaisesRegex(ValueError, 'Missing/extra/failure'):
                    self.check()
                extra.unlink()

    def test_completion_and_manifest_authentication(self):
        self.completion['files'] -= 1
        with self.assertRaisesRegex(ValueError, 'completion totals'):
            self.check()
        self.completion['files'] += 1
        self.ref['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'manifest digest'):
            self.check()

    def test_interrupted_prefix_boundary_and_intact_retained_check(self):
        for i in (2001, 2002):
            row = dict(self.rows[-1], frame_id=i, logical_bytes=i+10,
                       path=subject.PREFIX + f'run-1/evidence/frames/{i:06d}.png')
            self.rows.append(row)
        self.write_manifest()
        for name in ('00000-intent.json', '00000-complete.json', '00001-intent.json'):
            value = subject.read(self.receipts / name)
            value['manifest_sha256'] = self.ref['sha256']
            if name.startswith('00001'):
                value['count'] = 3
                value['logical_bytes'] = sum(r['logical_bytes'] for r in self.rows[2000:])
            self.write(name, value)
        (self.receipts / '00001-complete.json').unlink()
        retained_path = self.root / 'retained.jsonl.gz'
        retained = dict(self.rows[0], frame_id=999999, path=subject.PREFIX + 'run-1/evidence/frames/999999.png')
        with gzip.open(retained_path, 'wt') as f:
            f.write(json.dumps(retained) + '\n')
        retained_ref = {'sha256': subject.sha(retained_path), 'files': 1, 'logical_bytes': retained['logical_bytes']}
        hashed = []
        def checker(row, hash_content):
            if hash_content:
                hashed.append(row['path'])
                return 'present'
            return 'absent' if row['frame_id'] < 2002 else 'present'
        result = subject.inspect_interrupted(self.manifest, self.ref, self.receipts, retained_path, retained_ref, checker)
        self.assertEqual(result['first_remaining_ordinal'], 2002)
        self.assertEqual(result['completed_receipt_prefix']['files'], 2000)
        self.assertEqual(result['interrupted_intent']['absent_files'], 2)
        self.assertEqual(hashed, [retained['path']])
        def hole(row, hash_content):
            return 'present' if hash_content or row['frame_id'] == 2000 else 'absent'
        with self.assertRaisesRegex(ValueError, 'not a contiguous prefix'):
            subject.inspect_interrupted(self.manifest, self.ref, self.receipts, retained_path, retained_ref, hole)
        def old_present(row, hash_content):
            return 'present' if hash_content or row['frame_id'] == 7 else 'absent'
        with self.assertRaisesRegex(ValueError, 'completed-prefix file is present'):
            subject.inspect_interrupted(self.manifest, self.ref, self.receipts, retained_path, retained_ref, old_present)


class PolicyComparisonTests(unittest.TestCase):
    def test_only_documented_execution_differences_are_excluded(self):
        staged = {'phase': 'staged', 'queue_job_id': 'old', 'started_at': 'old', 'ended_at': 'old',
                  'required_manifest': {'sha256': 'input'}, 'guard_self_test': {'probe': 'old'},
                  'diagnostic_window_completeness': {'required': {'sha256': 'input'}, 'window_checks': [1, 2]},
                  'current_package': {'sha256': 'unchanged'}, 'actual_reader_traces': [{'events': 42}]}
        post = copy.deepcopy(staged)
        post.update(phase='post', queue_job_id='new', started_at='new', ended_at='new',
                    required_manifest={'sha256': 'final'}, guard_self_test={'probe': 'new'})
        post['diagnostic_window_completeness']['required'] = {'sha256': 'final'}
        self.assertEqual(comparable(staged), comparable(post))
        self.assertEqual(staged['diagnostic_window_completeness']['required'], {'sha256': 'input'})
        post['current_package']['sha256'] = 'changed'
        self.assertNotEqual(comparable(staged), comparable(post))
        post['current_package']['sha256'] = 'unchanged'
        post['diagnostic_window_completeness']['window_checks'][0] = 3
        self.assertNotEqual(comparable(staged), comparable(post))


if __name__ == '__main__':
    unittest.main()
