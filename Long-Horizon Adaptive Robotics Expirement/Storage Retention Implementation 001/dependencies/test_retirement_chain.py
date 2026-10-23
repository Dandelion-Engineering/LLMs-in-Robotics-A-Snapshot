"""Synthetic receipt-chain coverage and tamper tests; no evidence is accessed."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import reconcile_retirement_chain as chain
from reconcile_retirement_receipts import POLICY, PREFIX, sha


class ChainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / 'manifest.jsonl.gz'
        self.old = self.root / 'old'
        self.new = self.root / 'new'
        self.old.mkdir()
        self.new.mkdir()
        self.rows = [{'path': PREFIX + f'run-1/evidence/frames/{i:06d}.png',
                      'run_id': 'run-1', 'frame_id': i, 'artifact_type': 'rgb',
                      'logical_bytes': i + 10, 'policy': POLICY} for i in range(4005)]
        with gzip.open(self.manifest, 'wt', encoding='utf-8') as f:
            for row in self.rows:
                f.write(json.dumps(row) + '\n')
        self.ref = {'sha256': sha(self.manifest), 'files': len(self.rows),
                    'logical_bytes': sum(r['logical_bytes'] for r in self.rows)}
        self.make_pair(self.old, 0, 0, self.rows[:2000])
        self.make_pair(self.old, 1, 2000, self.rows[2000:4000], intent_only=True)
        self.make_pair(self.new, 0, 2003, self.rows[2003:4003])
        self.make_pair(self.new, 1, 4003, self.rows[4003:])
        old_sources = [self.identity(self.old / name) for name in ('00000-intent.json', '00000-complete.json', '00001-intent.json')]
        self.proof = {'completed_prefix': self.range(self.rows[:2000]),
                      'interrupted_intent_absences': {**self.range(self.rows[2000:2003]), 'first_ordinal': 2000},
                      'first_remaining_ordinal': 2003, 'remaining': self.range(self.rows[2003:]),
                      'original_receipt_set_sha256': chain.receipt_set_digest(old_sources), 'receipt_sources': old_sources}

    def identity(self, path):
        return {'name': path.name, 'bytes': path.stat().st_size, 'sha256': sha(path)}

    def range(self, rows):
        return {'files': len(rows), 'logical_bytes': sum(row['logical_bytes'] for row in rows),
                'ordered_paths_sha256': hashlib.sha256(('\n'.join(row['path'] for row in rows) + '\n').encode()).hexdigest()}

    def make_pair(self, directory, index, first, rows, intent_only=False):
        base = {'manifest_sha256': self.ref['sha256'], 'first_ordinal': first,
                'count': len(rows), 'logical_bytes': sum(row['logical_bytes'] for row in rows)}
        (directory / f'{index:05d}-intent.json').write_text(json.dumps({**base, 'created': '2026-09-27T02:00:00+00:00'}))
        if not intent_only:
            (directory / f'{index:05d}-complete.json').write_text(json.dumps({**base, 'finished': '2026-09-27T02:00:00+00:00',
                'removed_paths_sha256': self.range(rows)['ordered_paths_sha256']}))

    def check(self):
        return chain.reconcile_chain_stream(self.manifest, self.ref, self.proof, self.old, self.new)

    def test_split_old_intent_and_continuation_global_ordinals(self):
        result = self.check()
        self.assertEqual(result['files'], 4005)
        self.assertEqual(result['original_completed_prefix']['files'], 2000)
        self.assertEqual(result['observed_absent_within_interrupted_intent']['files'], 3)
        self.assertEqual(result['continuation']['files'], 2002)
        self.assertEqual([r['first_ordinal'] for r in result['continuation_completed_batches']], [2003, 4003])
        self.assertFalse((self.old / '00001-complete.json').exists())

    def test_new_receipt_wrong_global_ordinal_or_path_digest(self):
        leaf = self.new / '00000-complete.json'
        original = json.loads(leaf.read_text())
        for key, value in [('first_ordinal', 2000), ('removed_paths_sha256', '0' * 64), ('count', 1999)]:
            with self.subTest(key=key):
                leaf.write_text(json.dumps({**original, key: value}))
                with self.assertRaises(ValueError):
                    self.check()
        leaf.write_text(json.dumps(original))

    def test_original_receipt_is_immutable_and_missing_or_extra_fails(self):
        original = self.old / '00000-intent.json'
        raw = original.read_bytes()
        original.write_bytes(raw + b'\n')
        with self.assertRaisesRegex(ValueError, 'Original receipts differ'):
            self.check()
        original.write_bytes(raw)
        extra = self.old / '00001-complete.json'
        extra.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Missing/extra/failure'):
            self.check()
        extra.unlink()
        leaf = self.new / '00001-complete.json'
        leaf.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing/extra/failure'):
            self.check()

    def test_gap_in_chain_and_changed_observed_absence_digest_fail(self):
        original = copy.deepcopy(self.proof)
        self.proof['first_remaining_ordinal'] += 1
        with self.assertRaisesRegex(ValueError, 'immediately after'):
            self.check()
        self.proof = original
        self.proof['interrupted_intent_absences']['ordered_paths_sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'interrupted exact ordered-path digest'):
            self.check()


if __name__ == '__main__':
    unittest.main()
