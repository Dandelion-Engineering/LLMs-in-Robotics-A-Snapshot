"""Synthetic timestamp/identity attack tests; no native process or model."""
import copy
from decimal import Decimal
import math
import unittest

from completion_chronology import completion_chronology


class CompletionChronologyTests(unittest.TestCase):
    def setUp(self):
        self.rows = []

        def append(kind, message=None, **extra):
            row = {'sequence': len(self.rows) + 1, 'kind': kind,
                   'wall_unix_s': 100 + len(self.rows) / 10, **extra}
            if message is not None:
                row['message'] = message
            self.rows.append(row)
            return len(self.rows)

        def response(message):
            sequence = append('response', message)
            append('delivered', response_sequence=sequence)

        append('open')
        append('request', {'id': 7, 'method': 'process/start', 'params': {'processId': 'p'}})
        response({'id': 7, 'result': {'processId': 'p'}})
        response({'method': 'process/output', 'params': {'processId': 'p', 'seq': 1}})
        response({'method': 'process/exited', 'params': {'processId': 'p', 'seq': 2}})
        response({'method': 'process/closed', 'params': {'processId': 'p', 'seq': 3}})
        append('closed')
        self.delivered = {3, 5, 7, 9}
        self.emitted_ms = 110000

    def proof(self, request=None, process_id='p'):
        return completion_chronology(self.rows, self.delivered,
                                     self.rows[1] if request is None else request,
                                     process_id, self.emitted_ms)

    def test_original_timestamp_and_exact_interval_are_separate_from_upper_bound(self):
        proof = self.proof()
        self.assertEqual(proof['app_complete_wall_unix_s'], 110)
        self.assertEqual(proof['app_emitted_at_ms'], 110000)
        self.assertEqual(proof['app_emission_interval'], {
            'lower_numerator_ms': 110000, 'upper_numerator_ms': 110001, 'denominator': 1000,
            'lower_decimal_seconds': '110', 'upper_decimal_seconds': '110.001',
            'lower_inclusive': True, 'upper_exclusive': True})
        self.assertGreaterEqual(Decimal.from_float(proof['evidence_complete_upper_wall_unix_s']), Decimal('110.001'))
        self.assertEqual(proof['required_delivery_capture_sequences'], [4, 6, 8, 10])
        self.assertEqual(len(proof['completion_chronology_source']['sha256']), 64)

    def test_submillisecond_delivery_after_native_floor_is_compatible(self):
        self.emitted_ms = 100900
        self.rows[-2]['wall_unix_s'] = 100.9000233
        proof = self.proof()
        self.assertGreater(proof['evidence_complete_upper_wall_unix_s'], self.rows[-2]['wall_unix_s'])

    def test_native_emission_may_precede_post_await_delivery_log(self):
        self.emitted_ms = 100850
        proof = self.proof()
        self.assertEqual(proof['evidence_complete_upper_decimal_seconds'], '100.9')
        self.assertGreaterEqual(proof['evidence_complete_upper_wall_unix_s'], 100.9)
        self.assertEqual(proof['app_complete_wall_unix_s'], 100.85)

    def test_exclusive_upper_boundary_and_earlier_interval_fail_before_max(self):
        for emitted in (100799, 100798, 1):
            with self.subTest(emitted=emitted):
                self.emitted_ms = emitted
                with self.assertRaisesRegex(ValueError, 'outside conservative'):
                    self.proof()
        self.emitted_ms = 100800
        self.assertGreater(self.proof()['evidence_complete_upper_wall_unix_s'], 100.8)

    def test_no_mutation_or_episode_boundary_equality_is_hidden_by_rounding(self):
        self.emitted_ms = 100850
        bound = self.proof()['evidence_complete_upper_wall_unix_s']
        self.assertFalse(bound < 100.85)
        self.assertFalse(bound < 100.9)
        self.assertTrue(bound < 100.901)

    def test_native_milliseconds_require_exact_nonnegative_integer(self):
        for value in (True, False, -1, 1.0, '110000', None, math.nan, math.inf, 2**63):
            with self.subTest(value=value):
                self.emitted_ms = value
                with self.assertRaises(ValueError):
                    self.proof()

    def test_every_capture_clock_must_be_finite_numeric_and_ordered(self):
        original = copy.deepcopy(self.rows)
        for value in (True, '100.2', None, math.nan, math.inf, -math.inf, 10**400, 99):
            with self.subTest(value=value):
                self.rows = copy.deepcopy(original)
                self.rows[2]['wall_unix_s'] = value
                with self.assertRaises(ValueError):
                    self.proof()

    def test_capture_sequence_and_request_membership_are_not_repaired(self):
        original = copy.deepcopy(self.rows)
        for value in (True, 0, 1, 5, '3'):
            self.rows = copy.deepcopy(original)
            self.rows[2]['sequence'] = value
            with self.assertRaises(ValueError):
                self.proof()
        self.rows = original
        request = copy.deepcopy(self.rows[1])
        request['wall_unix_s'] += 0.001
        with self.assertRaisesRegex(ValueError, 'authenticated capture row'):
            self.proof(request=request)

    def test_request_must_precede_close_strictly(self):
        for row in self.rows[1:9]:
            row['wall_unix_s'] = 100.8
        with self.assertRaisesRegex(ValueError, 'strictly precede'):
            self.proof()

    def test_wrong_process_or_missing_successful_start_rejected(self):
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            self.proof(process_id='other')
        self.rows[2]['message']['result']['processId'] = 'other'
        with self.assertRaisesRegex(ValueError, 'start receipt'):
            self.proof()

    def test_each_required_delivery_is_present_unique_and_authenticated(self):
        for number in sorted(self.delivered):
            with self.subTest(missing=number):
                self.delivered.remove(number)
                with self.assertRaisesRegex(ValueError, 'required process delivery'):
                    self.proof()
                self.delivered.add(number)
        self.rows[-1].update(kind='delivered', response_sequence=9)
        with self.assertRaisesRegex(ValueError, 'required process delivery'):
            self.proof()

    def test_missing_or_duplicate_close_fails(self):
        self.rows[8]['message']['method'] = 'process/output'
        with self.assertRaisesRegex(ValueError, 'terminal process close'):
            self.proof()
        self.rows[8]['message']['method'] = 'process/closed'
        self.rows[4]['message']['method'] = 'process/closed'
        with self.assertRaisesRegex(ValueError, 'terminal process close'):
            self.proof()

    def test_unrelated_delivery_does_not_replace_required_process_delivery(self):
        self.rows[-1].update(kind='delivered', response_sequence=1234, wall_unix_s=1000.0)
        self.delivered.add(1234)
        self.assertLess(self.proof()['evidence_complete_upper_wall_unix_s'], 1000.0)
        self.delivered.remove(9)
        with self.assertRaisesRegex(ValueError, 'required process delivery'):
            self.proof()


if __name__ == '__main__':
    unittest.main()
