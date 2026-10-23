"""Proposed insert-exchange regressions: synthetic clocks/state, no physics/rendering."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import xml.etree.ElementTree as ET
import numpy as np
import cell
from test_cell import fake_cell,fake_step
import test_cell


class InsertExchangeTests(unittest.TestCase):
    def waiting(self):
        c=fake_cell()
        c.registry.update({name:{'kind':'insert','family':name[-1],'half':[.025,.025,.008]}
                           for name in ('insert_A','insert_B')})
        c.active_request={'request_id':'exchange','operation':'setup','family':'B','setup_pending':'insert_B',
                          'setup_returning':{'id':'insert_A','home':'insert_home_A'}}
        c._setup_wait={'request_id':'exchange','capture_after_sim_s':1.,'deadline_sim_s':3.}
        c.data.time=1.2;c.detection_time=1.1;c.data.qpos[7:9]=.04;c.lease_deadline=10.
        c.last_detections=[{'id':name,'kind':'insert','family':name[-1],'zone':'insert_home_'+name[-1],
                            'pos':[*cell.ZONES['insert_home_'+name[-1]],.008],'uncertainty_m':.004}
                           for name in ('insert_A','insert_B')]
        c.plan_transport=Mock()
        c.actual_pos=Mock(side_effect=AssertionError('Planner/service must not consult object truth'))
        return c

    def test_new_capture_of_old_insert_still_in_fixture_cannot_start_replacement(self):
        c=self.waiting();c.last_detections[0].update(zone='fixture',pos=[*cell.ZONES['fixture'],.008])
        self.assertFalse(c.resume_setup_if_fresh());c.plan_transport.assert_not_called()
        self.assertEqual(c.feedback[-1]['status'],'failed');c.actual_pos.assert_not_called()

    def test_capture_before_return_end_or_stale_capture_is_not_a_witness(self):
        for captured in (.9, .8, 1.3):
            c=self.waiting();c.detection_time=captured
            self.assertFalse(c.resume_setup_if_fresh());c.plan_transport.assert_not_called()
            self.assertIsNotNone(c.active_request)

    def test_home_witness_requires_containment_uncertainty_and_open_jaws(self):
        for mode in ('outside','high','closed','duplicate','fixture_occupied'):
            with self.subTest(mode=mode):
                c=self.waiting()
                if mode=='outside':c.last_detections[0]['pos'][0]+=.04
                if mode=='high':c.last_detections[0]['pos'][2]=.12
                if mode=='closed':c.data.qpos[7:9]=.02
                if mode=='duplicate':c.last_detections.append(dict(c.last_detections[0]))
                if mode=='fixture_occupied':c.last_detections.append({'id':'A1','kind':'part','zone':'fixture'})
                self.assertFalse(c.resume_setup_if_fresh());c.plan_transport.assert_not_called();c.actual_pos.assert_not_called()

    def test_verified_public_home_witness_dispatches_replacement_once(self):
        c=self.waiting();self.assertTrue(c.resume_setup_if_fresh())
        c.plan_transport.assert_called_once_with('insert_B','fixture')
        self.assertFalse(c.resume_setup_if_fresh());self.assertNotIn('setup_pending',c.active_request)
        self.assertEqual(c.events[-1]['type'],'setup_return_observed')
        self.assertFalse(c.events[-1]['independent_physical_success']);c.actual_pos.assert_not_called()

    def test_unseen_old_insert_waits_but_fixed_deadline_fails_even_with_renewed_lease(self):
        c=self.waiting();c.last_detections=c.last_detections[1:]
        self.assertFalse(c.resume_setup_if_fresh());self.assertEqual(c.feedback,[])
        c.data.time=3.01
        with patch.object(cell.mujoco,'mj_step',side_effect=fake_step):c.tick()
        self.assertIsNone(c.active_request);self.assertIsNone(c._setup_wait)
        self.assertEqual(c.feedback[-1]['status'],'failed');c.plan_transport.assert_not_called()

    def test_old_return_record_cannot_authorize_a_new_request(self):
        c=self.waiting();c.active_request['request_id']='new'
        self.assertFalse(c.resume_setup_if_fresh());c.plan_transport.assert_not_called()
        c.data.time=3.1
        with patch.object(cell.mujoco,'mj_step',side_effect=fake_step):c.tick()
        self.assertEqual(c.active_request['request_id'],'new');self.assertEqual(c.feedback,[])

    def test_public_planner_rejects_insert_placement_onto_another_visible_insert(self):
        c=self.waiting();c.plan_transport=cell.Cell.plan_transport.__get__(c)
        c.last_detections[0].update(zone='fixture',pos=[*cell.ZONES['fixture'],.008])
        with self.assertRaisesRegex(ValueError,'destination occupied'):c.plan_transport('insert_B','fixture')
        c.actual_pos.assert_not_called()

    def test_cycle_rejects_a_second_overlapping_insert_even_if_not_seated(self):
        c=self.waiting();c.active_request=None;c._setup_wait=None;c._physical_zone=Mock(return_value=True)
        c._insert_overlaps_fixture=Mock(return_value=True)
        reply=c.submit({'operation':'cycle','part_id':'A1','recipe':'A','request_id':'cycle'})
        self.assertEqual(reply['status'],'rejected');self.assertIn('unique seated insert',reply['reason'])
        self.assertFalse(c.station['busy']);self.assertEqual(c.truth['A1']['cycle_history'],[])

    def test_second_insert_appearing_during_cycle_faults_without_process_credit(self):
        c=test_cell.ProcessTests().accepted_cycle();c._insert_overlaps_fixture.return_value=True;c._insert_overlaps_fixture.side_effect=None
        with patch.object(cell.mujoco,'mj_step',side_effect=fake_step):c.tick()
        self.assertIsNone(c.cycle);self.assertTrue(c.station['fault'])
        self.assertEqual(c.truth['A1']['cycles'],0);self.assertFalse(c.truth['A1']['cycle_history'][0]['completed'])

    def test_physical_overlap_catches_boundary_overlap_independent_of_seating(self):
        c=self.waiting();c.data.xmat=np.array([np.eye(3).ravel()])
        c.actual_pos=Mock(return_value=np.array([cell.ZONES['fixture'][0]+.06,0.,.008]))
        with patch.object(cell.mujoco,'mj_name2id',return_value=0):self.assertTrue(c._insert_overlaps_fixture('insert_B'))
        c.actual_pos.return_value[2]=.2
        with patch.object(cell.mujoco,'mj_name2id',return_value=0):self.assertFalse(c._insert_overlaps_fixture('insert_B'))

    def test_offset_is_applied_at_both_insert_endpoints_without_hidden_pose(self):
        c=fake_cell();points=[]
        c.ik=lambda point,q,configuration:(points.append(np.array(point).copy()) or np.zeros(7))
        c.actual_pos=Mock(side_effect=AssertionError('hidden pose'))
        snapshot={'observed':{'pos':[.57,0.,.008]},'occupied':[],'destination':'insert_home_A',
                  'clearance':.16,'speed':.8,'avoid':[],'configuration':np.zeros(9),'tcp':np.array([.4,0.,.3]),
                  'half':[.025,.025,.008],'kind':'insert'}
        _,segments=c._plan_snapshot(snapshot,0)
        grasp=[s for s in segments if s['phase']==2][-1]
        placement=[s for s in segments if s['phase']==6][-1]
        self.assertAlmostEqual(grasp['cartesian_target'][2],.012)
        self.assertAlmostEqual(placement['cartesian_target'][2],.015)
        self.assertTrue(all(s['grip']==0 for s in segments if 3<=s['phase']<=6))
        self.assertTrue(all(s['grip']==255 for s in segments if s['phase']>=7))
        c.actual_pos.assert_not_called()
        self.assertGreaterEqual(.021-cell.INSERT_TCP_OFFSET_M-.008,0.)  # Unknown-payload recovery release remains above table.

    def test_public_slots_keep_insert_and_wall_height_with_uncertainty_allowance(self):
        # XML construction only. No model compilation, physics or renderer.
        minimal=ET.ElementTree(ET.fromstring('<mujoco><compiler/><option/><default/><asset/><worldbody><body name="hand"/></worldbody></mujoco>'))
        with patch.object(cell.ET,'parse',return_value=minimal):xml,registry=cell.build_scene(3,0)
        model=ET.fromstring(xml);walls=[g for g in model.findall('.//geom') if g.get('name','').startswith('fixture_wall_')]
        self.assertEqual(len(walls),6)
        jaw_walls=[g for g in walls if abs(float(g.get('pos').split()[1]))>.04]
        self.assertEqual(len(jaw_walls),4)
        for wall in jaw_walls:
            pos=list(map(float,wall.get('pos').split()));half=list(map(float,wall.get('size').split()))
            self.assertAlmostEqual(abs(pos[0]-cell.ZONES['fixture'][0])-half[0],.020)
            self.assertAlmostEqual(pos[2]+half[2],.012)
        self.assertGreater(cell.FIXTURE_JAW_SLOT_HALF_M,.010502+.004)
        self.assertEqual(registry['insert_A']['half'],[.025,.025,.008])


if __name__=='__main__':unittest.main()
