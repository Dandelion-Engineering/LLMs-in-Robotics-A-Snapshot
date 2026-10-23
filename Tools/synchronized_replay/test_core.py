"""Synthetic counterexamples for uncertainty, stops and unknown-content boundaries."""
import unittest
from core import clock_bracket, validate_anchors, diff_text, script_json


class Boundaries(unittest.TestCase):
    def setUp(self):
        self.a = [{'wall': 100., 'sim': 1., 'id': 1}, {'wall': 100.1, 'sim': 1.08, 'id': 2},
                  {'wall': 100.3, 'sim': 1.25, 'id': 3}]

    def test_non_unit_clock_rate(self):
        b = clock_bracket(self.a, 100.2)
        self.assertEqual((b['left'], b['right'], b['sim_min'], b['sim_max']), (2, 3, 1.08, 1.25))
        self.assertAlmostEqual(b['estimate'], 1.165)

    def test_exact_anchor(self):
        b = clock_bracket(self.a, 100.1)
        self.assertEqual((b['sim_min'], b['sim_max']), (1.08, 1.08))

    def test_stop_is_not_extrapolated(self):
        b = clock_bracket(self.a, 101.)
        self.assertEqual(b['kind'], 'after-stop')
        self.assertIsNone(b['sim_max'])

    def test_prestart_is_not_extrapolated(self):
        self.assertIsNone(clock_bracket(self.a, 99.)['estimate'])

    def test_missing_clock_is_not_zero(self):
        for wall in (None, True, float('nan'), float('inf')):
            self.assertEqual(clock_bracket(self.a, wall)['kind'], 'untimed')

    def test_regression_requires_segmentation(self):
        for invalid in ([self.a[1], self.a[0]], [self.a[0], self.a[0]],
                        [{'wall': 1., 'sim': 2., 'id': 1}, {'wall': 2., 'sim': 1., 'id': 2}]):
            with self.assertRaises(ValueError):
                validate_anchors(invalid)

    def test_unknown_before_not_empty(self):
        self.assertIsNone(diff_text(None, 'created\n', 'note'))
        self.assertIn('+created', diff_text('', 'created\n', 'note'))

    def test_inert_script_embedding(self):
        encoded = script_json({'text': '</script><script>alert(1)</script>\u2028'})
        self.assertNotIn('<', encoded)
        self.assertNotIn('\u2028', encoded)


if __name__ == '__main__':
    unittest.main()
