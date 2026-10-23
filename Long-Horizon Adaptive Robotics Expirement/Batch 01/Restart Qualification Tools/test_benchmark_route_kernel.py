"""Tiny synthetic kernel tests, no completed evidence or queue."""
import unittest
from pathlib import Path

import benchmark_route_kernel as benchmark
import pending_route_validation as proposal


def box(low, high):
    return {'min': [low]*3, 'max': [high]*3}


class KernelTests(unittest.TestCase):
    def test_paired_outputs_counts_sources_and_no_route_compilation(self):
        functions = benchmark.kernel_functions(proposal.TARGET.read_bytes().decode('utf-8'))
        objects = [{'id': 'held', 'bounds': box(0., 1.)}, {'id': 'z', 'bounds': box(4., 5.)},
                   {'id': 'a', 'bounds': box(5., 6.)}]
        corridors = [box(0., 1.), box(1., 2.), box(2., 3.)]
        report = benchmark.benchmark(functions, objects, 'held', corridors)
        self.assertTrue(report['all_outputs_exactly_equal'])
        self.assertEqual(len(report['timed_pairs']), 5)
        self.assertEqual(report['untimed_validation_counts']['original']['valid_box_calls'],
                         {'total': 15, 'corridor': 9, 'object': 6})
        self.assertEqual(report['untimed_validation_counts']['validated_once']['valid_box_calls'],
                         {'total': 5, 'corridor': 3, 'object': 2})
        for name, fn in functions.items():
            self.assertNotIn('_route', fn['namespace'])
            self.assertNotIn('_calibration', fn['namespace'])
            for row in report['timed_pairs']:
                self.assertEqual(row['measurements'][name]['blocker_ids'], [])
                self.assertGreaterEqual(row['measurements'][name]['wall_s'], 0.)
                self.assertGreaterEqual(row['measurements'][name]['cpu_s'], 0.)
        objects[1]['bounds'] = box(.2, .3)
        blocked = benchmark.benchmark(functions, objects, 'held', corridors)
        self.assertTrue(blocked['all_outputs_exactly_equal'])
        self.assertEqual(blocked['untimed_validation_counts']['original']['blocker_ids'], ['z'])

    def test_count_instrumentation_restored_after_error_and_sources_guarded(self):
        functions = benchmark.kernel_functions(proposal.TARGET.read_bytes().decode('utf-8'))
        for fn in functions.values():
            original = fn['namespace']['valid_box']
            with self.assertRaises(ValueError): benchmark.counted(fn, {'geometry': {'objects': []}}, {'id': 'held'}, [])
            self.assertIs(fn['namespace']['valid_box'], original)
        with self.assertRaises(ValueError):
            benchmark.kernel_functions(proposal.TARGET.read_bytes().decode('utf-8')+'\n')


if __name__ == '__main__':
    unittest.main()
