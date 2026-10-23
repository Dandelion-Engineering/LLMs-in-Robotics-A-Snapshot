"""Meaningful failure checks for the independent evidence assessor."""
import base64
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('bootstrap_assessment', Path(__file__).with_name('assess_bootstrap.py'))
assessor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assessor)


class AssessmentTests(unittest.TestCase):
    def test_pending_or_failed_queue_blocks_before_any_result_read(self):
        with tempfile.TemporaryDirectory(prefix='robot-codex-assessment-test-') as name:
            root = Path(name)
            receipt = root / 'queue.json'
            for state, exit_status in [('running', None), ('failed', 1), ('succeeded', 1)]:
                receipt.write_text(json.dumps({'state': state, 'exit_status': exit_status}), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'queue receipt'):
                    assessor.assess(root / 'absent-evidence', receipt, root / 'absent-snapshot')

    def test_retained_hash_is_recomputed(self):
        raw = b'actual artifact'
        item = {'sha256': assessor.sha(raw), 'retained_sha256': assessor.sha(raw), 'bytes': len(raw),
                'base64': base64.b64encode(raw).decode()}
        record = {'files': {'notes/a.txt': item}, 'total_bytes': len(raw)}
        self.assertEqual(assessor.snapshot(record)[1], [])
        item['base64'] = base64.b64encode(b'tampered bytes').decode()
        self.assertTrue(assessor.snapshot(record)[1])

    def test_read_hashes_accept_exact_combined_bytes_but_reject_wrong_output(self):
        with tempfile.TemporaryDirectory(prefix='robot-codex-assessment-test-') as name:
            archive_path = Path(name) / 'code.zip'
            with zipfile.ZipFile(archive_path, 'w') as archive:
                archive.writestr('integration/smoke-template/Continuity.md', 'initial continuity\n')
            expected = b'protected task content\n'
            hashes = {'Tasks.md': assessor.sha(expected)}
            commands = [{'id': 'read-one', 'aggregatedOutput': 'header\n' + expected.decode() + 'footer\n',
                         'commandActions': [{'type': 'read', 'path': '/workspace/Tasks.md'}]}]
            result = assessor.startup_read_evidence(commands, hashes, {'Tasks.md': expected}, archive_path)
            self.assertTrue(result['Tasks.md']['verified'])
            commands[0]['aggregatedOutput'] = 'a model claim that the file was read'
            result = assessor.startup_read_evidence(commands, hashes, {'Tasks.md': expected}, archive_path)
            self.assertFalse(result['Tasks.md']['verified'])

    def test_retirement_needs_observed_empty_known_namespace(self):
        self.assertFalse(assessor.check_retirement({'qualified': True}))
        final = {'retired': True, 'namespace_evidence_available': True, 'namespace_ids': [123],
                 'namespace_members': [], 'outer_same_process': False}
        record = {'qualified': True, 'observations': [final]}
        self.assertTrue(assessor.check_retirement(record))
        final['namespace_members'] = [{'pid': 50}]
        self.assertFalse(assessor.check_retirement(record))


if __name__ == '__main__':
    unittest.main()
