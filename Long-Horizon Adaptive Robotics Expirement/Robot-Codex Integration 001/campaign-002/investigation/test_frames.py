"""Bounded synthetic tests; never open actual recorder containers."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location('campaign_frame_export_tested', HERE / 'export_frames.py')
frames = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frames)


class FrameTests(unittest.TestCase):
    def test_even_selection_retains_first_last_without_duplicates(self):
        selected = frames.even_selection(list(range(130)), 32)
        self.assertEqual(len(selected), 32)
        self.assertEqual((selected[0], selected[-1]), (0, 129))
        self.assertEqual(selected, sorted(set(selected)))
        self.assertEqual(frames.even_selection([1, 2], 32), [1, 2])

    def test_publication_uses_exact_capture_join_and_first_observation(self):
        history = [(1, {'type': 'episode_started', 'wall_unix_s': 1000.}),
            (2, {'type': 'observation', 'event_id': 2, 'wall_unix_s': 1001.2, 'sim_time_s': 2.2,
                 'payload': {'capture_sim_time_s': 2., 'sequence': 5}}),
            (3, {'type': 'observation', 'event_id': 3, 'wall_unix_s': 1001.3, 'sim_time_s': 2.3,
                 'payload': {'capture_sim_time_s': 2., 'sequence': 6}})]
        found = frames.publications(history)
        self.assertEqual(found[2.]['event_id'], 2)
        self.assertAlmostEqual(found[2.]['t'], 1.2)
        self.assertNotIn(2.0001, found)

    def test_hard_export_caps(self):
        for maximum, byte_cap in [(33, 128_000_000), (32, 128_000_001), (0, 1), (32, 0)]:
            with self.assertRaises(ValueError):
                frames.export(Path('must-not-be-opened.json'), maximum, byte_cap)

    def test_refuse_unsettled_campaign_before_decoder_or_outcomes(self):
        with tempfile.TemporaryDirectory(prefix='frames-test-') as directory:
            plan = {'campaign_id':'RCI001-Campaign002','attempts':[{'run_id':f'RCI001-C02-{family}-{i:02}', 'ordinal':2*(i-1)+j+1,'family':'misplaced-stock' if family=='stock' else 'blocked-insert-home'} for i in range(1,11) for j,family in enumerate(('stock','home'))]}
            with patch.object(frames, 'read', return_value=plan), patch.object(frames, 'reader_module') as decoder:
                with self.assertRaisesRegex(ValueError, 'not all settled'):
                    frames.export(Path(directory) / 'execution-plan.json')
                decoder.assert_not_called()


if __name__ == '__main__':
    unittest.main()
