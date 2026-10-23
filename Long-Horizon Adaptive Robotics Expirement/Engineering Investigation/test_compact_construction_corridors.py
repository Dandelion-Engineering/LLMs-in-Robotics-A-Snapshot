"""Small synthetic containment and false-space checks; no queue/physics/raw runs."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

import compact_construction_corridors as compact
from test_assess_validation import Fixture, write


def box(low, high): return {'min': [float(v) for v in low], 'max': [float(v) for v in high]}


def overlaps(a, b):
    return all(min(a['max'][i], b['max'][i])-max(a['min'][i], b['min'][i]) > 1e-6 for i in range(3))


class CompactTests(unittest.TestCase):
    def test_negative_and_edge_bins_preserve_all_original_coordinates(self):
        cover = compact.Cover(.01)
        originals = [box([-.0137123, -.001, .1], [-.0062877, .001, .2]),
                     box([-.01000002, -.002, .1], [-.00999999, .002, .2]),
                     box([.00012, .0003, .11], [.01988, .001, .12])]
        for index, original in enumerate(originals): cover.add('geom', original, {'line': index})
        self.assertEqual(cover.input_count, 3)
        self.assertTrue(all(cover.contains_assigned('geom', b) for b in originals))
        self.assertEqual(compact.bin_key('g', originals[0], .01)[1], -1)
        self.assertEqual(compact.bin_key('g', originals[1], .01)[1], -2)
        coordinates = [v for b in originals for values in b.values() for v in values]
        for row in cover.records():
            self.assertTrue(all(v in coordinates for values in row['box'].values() for v in values))

    def test_geometry_identity_and_location_ownership_prevent_cross_merge(self):
        groups = {name: compact.Cover(.05) for name in ('A1', 'B10', 'B2')}
        for name, cover in groups.items():
            cover.add('robot1', box([0, 0, 0], [.001, .001, .001]), {'location': name})
            cover.add('payload', box([0, 0, 0], [.001, .001, .001]), {'location': name})
        groups['B2'].add('payload', box([.02, 0, 0], [.021, .001, .001]), {'location': 'B2'})
        self.assertEqual(len(groups['B2'].records()), 2)
        self.assertEqual(groups['A1'].input_count, 2); self.assertEqual(groups['B10'].input_count, 2)
        self.assertEqual(groups['A1'].records()[0]['box']['max'][0], .001)

    def test_false_space_from_hull_is_reported_with_volume_bounds(self):
        originals = [box([.001, .001, .001], [.002, .002, .002]), box([.008, .001, .001], [.009, .002, .002])]
        obstacle = {'id': 'gap_body', 'bounds': box([.004, .001, .001], [.006, .002, .002])}
        cover = compact.Cover(.01)
        for i, b in enumerate(originals): cover.add('geom', b, {'line': i})
        self.assertFalse(any(overlaps(b, obstacle['bounds']) for b in originals))
        result = compact.compare(cover.records(), [obstacle], overlaps)[0]
        self.assertEqual(result['runtime_blocker_ids'], ['gap_body'])
        volumes = result['volume']
        self.assertIsNone(volumes['added_union_volume_m3'])
        self.assertAlmostEqual(volumes['per_bin_added_volume_lower_bound_sum_m3'], 6e-9)
        self.assertAlmostEqual(volumes['added_union_volume_upper_bound_m3'], 7e-9)
        self.assertLess(result['minimum_signed_axis_separation_m'], 0)

    def test_coarser_fixed_bin_can_introduce_blocker_without_selecting_it(self):
        originals = [box([.001, .001, .001], [.002, .002, .002]), box([.018, .001, .001], [.019, .002, .002])]
        obstacle = {'id': 'gap', 'bounds': box([.009, .001, .001], [.011, .002, .002])}
        results = []
        for width in compact.BIN_WIDTHS_M:
            cover = compact.Cover(width)
            for b in originals: cover.add('g', b, {})
            results.append(compact.compare(cover.records(), [obstacle], overlaps)[0])
        self.assertEqual(results[0]['runtime_overlap_pairs'], 0)
        self.assertGreater(results[1]['runtime_overlap_pairs'], 0)
        self.assertTrue(all(r['padding_selected'] is False for r in results))

    def test_vector_overlap_matches_every_scalar_pair_at_threshold_and_touching(self):
        cover = compact.Cover(.01)
        for i in range(4): cover.add(str(i), box([i, 0, 0], [i+.2, .2, .2]), {})
        objects = [{'id': str(i), 'bounds': box([.2-depth, 0, 0], [.3, .1, .1])}
                   for i, depth in enumerate((0., 1e-6, np.nextafter(1e-6, 0.), np.nextafter(1e-6, 1.), .005))]
        records = cover.records()
        for result in compact.compare(records, objects, overlaps):
            p = result['uniform_padding_m']; expected = 0; blockers = set()
            for row in records:
                expanded = box([v-p for v in row['box']['min']], [v+p for v in row['box']['max']])
                for obj in objects:
                    if overlaps(expanded, obj['bounds']): expected += 1; blockers.add(obj['id'])
            self.assertEqual(result['runtime_overlap_pairs'], expected)
            self.assertEqual(result['runtime_blocker_ids'], sorted(blockers))

    def test_padding_gap_and_no_other_bodies_are_explicit(self):
        cover = compact.Cover(.01); cover.add('g', box([0, 0, .1], [.1, .1, .2]), {})
        objects = [{'id': 'below', 'bounds': box([.04, .04, 0], [.06, .06, .095])}]
        reports = compact.compare(cover.records(), objects, overlaps)
        self.assertAlmostEqual(reports[0]['minimum_signed_axis_separation_m'], .005)
        self.assertEqual(reports[0]['runtime_overlap_pairs'], 0)
        self.assertEqual(reports[-1]['runtime_overlap_pairs'], 1)
        self.assertEqual(tuple(r['uniform_padding_m'] for r in reports), compact.PADDINGS_M)
        empty = compact.compare(cover.records(), [], overlaps)[0]
        self.assertEqual(empty['pair_comparisons'], 0); self.assertIsNone(empty['minimum_signed_axis_separation_m'])

    def test_merge_and_full_second_pass_containment_reject_lost_box_or_changed_audit(self):
        with TemporaryDirectory() as temp:
            path = Path(temp)/'audit.jsonl'
            boxes = [box([0, 0, 0], [.001, .001, .001]), box([.005, 0, 0], [.006, .001, .001])]
            row = {'geometry_keys': ['g', 'g'], 'boxes': {key: [b[key] for b in boxes] for key in ('min', 'max')}, 'source_ref': {}}
            path.write_text(json.dumps(row)+'\n'); identity = compact.ref(path)
            covers = {w: compact.Cover(w) for w in compact.BIN_WIDTHS_M}
            for b in boxes:
                for width, cover in covers.items():
                    trial = compact.Cover(width); trial.add('g', b, {}); cover.merge(trial)
            result = compact.verify_containment(covers, [identity])
            self.assertEqual(result['state'], 'pass'); self.assertEqual(result['checked_assignments'], 6)
            next(iter(covers[.01].buckets.values()))['box']['max'][0] = .003
            self.assertEqual(compact.verify_containment(covers, [identity])['state'], 'fail')
            path.write_text(json.dumps(row)+'\n\n')
            with self.assertRaisesRegex(ValueError, 'audit changed'): compact.verify_containment(covers, [identity])

    def test_archived_runtime_formula_is_checked_before_vectorization(self):
        source = (compact.PROJECT/'Runtime/restart_state.py').read_text()
        self.assertTrue(callable(compact.archived_overlap(source)))
        with self.assertRaisesRegex(ValueError, 'formula changed'):
            compact.archived_overlap(source.replace(">1e-6 for i in range(3))", ">2e-6 for i in range(3))"))

    def test_completed_synthetic_extraction_retains_all_declared_trials_and_bindings(self):
        with TemporaryDirectory() as temp:
            root = Path(temp); fixture = Fixture(root)
            extraction, receipt, extraction_receipt = fixture.screen('construction', 1)
            report = compact.derive(extraction, receipt, extraction_receipt, 'parking1', root/'compact')
            self.assertEqual(len(report['trials']), len(fixture.plan['trials']))
            self.assertEqual(report['selected_trial_count'], 2)
            self.assertTrue(report['all_selected_trials_processed'])
            self.assertFalse(report['qualification_granted']); self.assertFalse(report['parameter_selected'])
            group = report['payload_location_groups'][0]
            self.assertEqual(group['payload_location_group'], 'A1')
            self.assertEqual(len(group['candidates']), 3)
            self.assertTrue(group['all_available_group_cut_scenes_included'])
            self.assertTrue(all(len(c['actual_cut_scene_comparisons']) == 2 for c in group['candidates']))
            self.assertEqual(group['containment']['state'], 'pass')
            self.assertTrue(report['consumed_files'])
            self.assertFalse(next(r for r in report['trials'] if r['trial_id']=='c-boundary')['all_objects_generator_domain_members'])

    def test_tampered_selected_trial_is_retained_unknown_and_never_replaced(self):
        with TemporaryDirectory() as temp:
            root = Path(temp); fixture = Fixture(root)
            extraction, receipt, extraction_receipt = fixture.screen('construction', 1)
            path = extraction.parent/'c-good/trial.json'; value = json.loads(path.read_bytes())
            value['child_result']['status'] = 'failed'; write(path, value)
            report = compact.derive(extraction, receipt, extraction_receipt, 'parking1', root/'compact')
            row = next(r for r in report['trials'] if r['trial_id'] == 'c-good')
            self.assertEqual(row['diagnostic_state'], 'unknown')
            self.assertFalse(report['all_selected_trials_processed'])
            self.assertEqual(report['unassigned_selected_trial_ids'], ['c-good'])
            self.assertFalse(report['payload_location_groups'][0]['all_declared_group_routes_included'])

    def test_failed_receipt_refuses_before_creating_output(self):
        with TemporaryDirectory() as temp:
            root = Path(temp); fixture = Fixture(root)
            extraction, receipt, extraction_receipt = fixture.screen('construction', 1)
            value = json.loads(receipt.read_bytes()); value['state'] = 'running'; write(receipt, value)
            with self.assertRaises(ValueError): compact.derive(extraction, receipt, extraction_receipt, 'parking1', root/'compact')
            self.assertFalse((root/'compact').exists())


if __name__ == '__main__': unittest.main()
