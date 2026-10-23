"""Pure screen definitions/admission/ranking checks; no physics or queue calls."""
import copy
import unittest
import numpy as np
import posture_screen as screen


class ScreenTests(unittest.TestCase):
    def test_exact18_and_existing_home(self):
        rows=screen.postures();self.assertEqual(len(rows),18)
        self.assertEqual(len({tuple(r['q']) for r in rows}),18)
        self.assertEqual([r['id'] for r in rows if r['q']==screen.EXISTING_HOME],['posture-06'])
        self.assertTrue(all(r['q'][2]==0 and r['q'][4:]==[0.,1.7,.7854] for r in rows))

    def inputs(self):
        return ({'valid':True},{'passed':True},
            {'rows':[{'id':str(i),'public_mark':'raw','error_m':.001} for i in range(12)],
             'missing_ids':[],'unexpected_ids':[],'duplicate_ids':False},
            [{'passed':True} for _ in screen.STATION_REGIONS])

    def test_every_gate_matters_and_missingness_is_not_success(self):
        self.assertTrue(screen.decision(*self.inputs())['eligible'])
        for position,key,value in ((0,'valid',False),(1,'passed',False),(2,'missing_ids',['B10']),
                                   (2,'duplicate_ids',True),(2,'unexpected_ids',['alien'])):
            args=list(self.inputs());args[position][key]=value
            self.assertFalse(screen.decision(*args)['eligible'])
        for key,value in (('public_mark','unknown'),('error_m',.00401)):
            args=list(self.inputs());args[2]['rows'][0][key]=value
            self.assertFalse(screen.decision(*args)['eligible'])
        args=list(self.inputs());args[3][0]['passed']=False
        self.assertFalse(screen.decision(*args)['eligible'])

    def test_tie_break_is_fixed_and_failed_cleanup_is_ineligible(self):
        rows=[{**r,'status':'completed','sources_unchanged':True,'decision':{'eligible':True}} for r in screen.postures()]
        self.assertEqual(screen.candidate_order(list(reversed(rows)))[0]['id'],'posture-06')
        rows[6]['status']='failed'
        self.assertNotIn('posture-06',[r['id'] for r in screen.candidate_order(rows)])
        rows[0]['sources_unchanged']=False
        self.assertNotIn('posture-00',[r['id'] for r in screen.candidate_order(rows)])

    def test_comparison_keeps_error_unknown_when_tag_missing(self):
        result=screen.comparison([{'id':'A1','pos':[0.,0.,.01],'visible_mark':'raw','pixels':50}],
            {'objects':[{'id':'A1','position':[0.,0.,0.]},{'id':'B2','position':[1.,0.,0.]}]})
        self.assertEqual(result['missing_ids'],['B2']);self.assertEqual(result['rows'][0]['error_m'],.01)
        self.assertNotIn('error_m',result['rows'][1])

    def test_region_occluder_uses_public_geometry_and_depth_only(self):
        cal={'world_from_camera_rotation':np.eye(3).tolist(),'camera_position_world_m':[0,0,1.], 'focal_px':30.}
        zones={name:(0.,0.) for name in screen.STATION_REGIONS};depth=np.ones((60,80))
        self.assertTrue(all(r['passed'] for r in screen.region_visibility(depth,cal,zones,lambda n:(.1,.1))))
        depth[27:33,37:43]=.5
        self.assertFalse(any(r['passed'] for r in screen.region_visibility(depth,cal,zones,lambda n:(.1,.1))))


if __name__=='__main__':unittest.main()
