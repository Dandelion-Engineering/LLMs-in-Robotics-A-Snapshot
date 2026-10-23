"""Small synthetic geometry only; no real construction input or physics."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from construction_geometry import compare,prune_boxes,run,PADDINGS_M
from test_assess_validation import Fixture


def record(low,high,line):return {'box':{'min':low,'max':high},'source_ref':{'line':line,'trial_id':'synthetic'}}
def overlaps(a,b):return all(min(a['max'][i],b['max'][i])-max(a['min'][i],b['min'][i])>1e-6 for i in range(3))


class GeometryTests(unittest.TestCase):
    def test_exact_pruning_preserves_union_and_coordinates(self):
        outer=record([-1.,-.2,-.1],[.1,.2,.1],1)
        inside=record([-.5,-.1,-.05],[0.,.1,.05],2)
        separate=record([.2,-.2,-.1],[.3,.2,.1],3)
        kept,stats=prune_boxes([inside,outer,outer,separate])
        self.assertEqual(len(kept),2);self.assertIn(outer,kept);self.assertIn(separate,kept)
        self.assertEqual(stats['exact_duplicate_boxes_removed'],1)
        self.assertEqual(stats['singly_contained_boxes_removed'],1)
        self.assertTrue(stats['union_preserved_exactly'])

    def test_time_separated_boxes_avoid_phase_hull_false_blocker_and_padding_is_proposed(self):
        records=[record([0.,0.,.1],[.1,.1,.2],1),record([0.,.3,0.],[.1,.4,.1],2)]
        objects=[{'id':'other','bounds':{'min':[.04,.04,0.],'max':[.06,.06,.095]}}]
        reports=compare(records,objects,overlaps)
        self.assertEqual(tuple(r['proposed_uniform_padding_m'] for r in reports),PADDINGS_M)
        self.assertEqual(reports[0]['runtime_overlap_pairs'],0)
        self.assertAlmostEqual(reports[0]['minimum_signed_axis_separation_m'],.005)
        self.assertGreater(reports[-1]['runtime_overlap_pairs'],0)
        hull={'min':[0.,0.,0.],'max':[.1,.4,.2]}
        self.assertTrue(overlaps(hull,objects[0]['bounds']))
        self.assertTrue(all(r['padding_selected'] is False for r in reports))

    def test_completed_synthetic_construction_exports_all_rows_and_does_not_merge_payloads(self):
        with TemporaryDirectory() as temp:
            root=Path(temp);fixture=Fixture(root)
            extraction,receipt,extract_receipt=fixture.screen('construction',1)
            report=run(extraction,receipt,extract_receipt,'parking1',root/'diagnostic')
            self.assertEqual(len(report['trials']),len(fixture.plan['trials']))
            selected=[r for r in report['trials'] if r['selected_construction']]
            self.assertEqual(len(selected),2)
            self.assertTrue(all(r['diagnostic_state']=='measured_discrete_only' for r in selected),selected)
            self.assertFalse(report['qualification_granted']);self.assertFalse(report['padding_selected'])
            self.assertEqual(report['payload_location_groups'][0]['in_domain_coupled_summary']['point_count'],2)
            self.assertTrue((root/'diagnostic/c-good-interval-boxes.jsonl').exists())
            self.assertTrue((root/'diagnostic/A1-exact-pruned-box-union.json').exists())


if __name__=='__main__':unittest.main()
