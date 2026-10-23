"""No diagnostic outcome reads before authentic direct queue success."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('host_probe_assessment_tests', Path(__file__).with_name('assess_host_probe.py'))
subject = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(subject)


class QueueBoundary(unittest.TestCase):
    def test_failed_or_noninteger_completion_cannot_read_outcomes(self):
        for job in ({'state': 'running', 'exit_status': None}, {'state': 'failed', 'exit_status': 1},
                    {'state': 'succeeded', 'exit_status': False}, {'state': 'succeeded', 'exit_status': '0'}):
            with self.subTest(job=job), patch.object(subject.base, 'read_json', return_value=job) as reader:
                with self.assertRaises(ValueError):
                    subject.evaluate(Path('manifest'), Path('evidence'), Path('queue'), Path('snapshot'))
                reader.assert_called_once_with(Path('queue'))

    def test_unrelated_successful_queue_cannot_read_outcomes(self):
        with patch.object(subject.base, 'read_json', return_value={'state': 'succeeded', 'exit_status': 0,
                          'argv': ['unrelated']}) as reader:
            with self.assertRaises(ValueError):
                subject.evaluate(Path('manifest'), Path('evidence'), Path('queue'), Path('snapshot'))
            reader.assert_called_once_with(Path('queue'))


if __name__ == '__main__':
    unittest.main()
