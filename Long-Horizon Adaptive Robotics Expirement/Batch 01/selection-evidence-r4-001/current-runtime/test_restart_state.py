"""Synthetic protected snapshots/contact arrays only; no Cell, jobs or physics."""
import copy
import math
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

import restart_state as restart

I=[[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]]


def snapshot(phase='closed_grip_transfer'):
    held=phase=='closed_grip_transfer'
    position=[.3,0.,.15] if held else [.2,-.09,.018]
    bounds={'min':[position[0]-.021,position[1]-.021,position[2]-.018],
            'max':[position[0]+.021,position[1]+.021,position[2]+.018]}
    obj={'id':'A1','kind':'part','family':'A','position':position,'bounds':bounds,'gripper_contact':held,
         'linear_velocity':[0.,0.,0.],'angular_velocity':[0.,0.,0.]}
    region={'min':[.147,-.143,-.003],'max':[.253,-.037,.08]}
    contact={'hand_contact':held,'left_finger_contact':held,'right_finger_contact':held,
             'left_normal_force_N':5. if held else 0.,'right_normal_force_N':6. if held else 0.,
             'bilateral_force_bearing':held,'support_upward_force_N':0. if held else 1.,
             'contact_indices':[],'support_contact_indices':[],'nonhand_contact_indices':[]}
    active={'operation':'transport','part_id':'A1','destination':'parking2','request_id':'r1','incarnation':2,'order_version':1}
    return {'schema_version':restart.SCHEMA,'capture_sim_time_s':10.,'snapshot_sha256':'synthetic-not-physical',
        'source_hashes':{'cell.py':'a'*64},'physical_configuration_sha256':'b'*64,'scene_xml_sha256':'c'*64,
        'capture_errors':[],'expected_object_ids':['A1'],
        'exposure':{'configured_cut':phase,'actual_cut':phase,'configured_milestone_exercised':True,'fallback_used':False,'active_request_id':'r1'},
        'geometry':{'objects':[obj],'zones':{'parking2':region}},
        'robot':{'jaw_width_m':.04 if held else .08,'joint_position_rad':[0.]*7,'joint_velocity_rad_s':[0.]*7,
                 'finger_position_m':[.02,.02] if held else [.04,.04],'finger_velocity_m_s':[0.,0.],
                 'ctrl':[0.]*7+[0. if held else 255.],'tcp_position_world_m':[.3,0.,.15],'tcp_rotation_world':copy.deepcopy(I),
                 'joint_ranges_rad':[[-2.,2.] for _ in range(7)]},
        'object_poses':{'A1':{'relative_to_tcp':{'position_m':[0.,0.,0.],'rotation':copy.deepcopy(I)}}},
        'contacts':{'records':[],'by_object':{'A1':contact}},
        'authority':{'active_request':active,'generation':2,'lease_deadline_sim_s':11.,
                     'segment':{'phase':{'closed_grip_transfer':5,'after_release':7,'before_outcome':9,'after_acceptance':0}.get(phase)},
                     'planner':{'exists':False,'generation':None},'direct_planner':{'exists':False,'generation':None}},
        'devices':{'station':{'busy':False,'ready':True,'fault':False,'guard_closed':False,'clamped':False},'cycle':None,'inspection_due':None},
        'observation':{'last_capture_age_s':.02},'infrastructure':{'status':'valid','reasons':[]}}


def calibration(scene):
    def entry(envelope):return {'evidence_refs':[{'kind':'prior_physical_calibration','artifact_id':'synthetic-prior',
                  'sha256':'d'*64,'bytes_verified_by_operator':True}],
            'source_hashes':copy.deepcopy(scene['source_hashes']),'physical_configuration_sha256':scene['physical_configuration_sha256'],
            'envelope_basis':'measured_before_this_intervention','envelope':envelope}
    grip=entry({'jaw_width_m':[.02,.06],'relative_position_m':{'min':[-.01]*3,'max':[.01]*3},
                'relative_rotation':copy.deepcopy(I),'maximum_rotation_error_rad':.1,'finger_normal_force_N':[1.,20.],
                'maximum_linear_speed_m_s':.3,'maximum_angular_speed_rad_s':.5,'minimum_payload_bottom_z_m':.1,
                'kind':'part','family':'A'})
    route=entry({'operation':'recover_held','destination':'parking2','tcp_start_m':{'min':[.28,-.02,.12],'max':[.32,.02,.18]},
                 'joint_start_ranges_rad':[[-.1,.1] for _ in range(7)],'destination_region_m':copy.deepcopy(scene['geometry']['zones']['parking2']),
                 'joint_velocity_ranges_rad_s':[[-.1,.1] for _ in range(7)],'maximum_abs_finger_velocity_m_s':.01,
                 'clearance_corridors_m':[{'min':[.15,-.14,.10],'max':[.34,.04,.30]}],
                 'payload_kind':'part','payload_family':'A'})
    return {'grip':grip,'routes':[route]}


def predicate(result,name):return next(p for p in result['predicates'] if p['name']==name)


class ClassifierTests(unittest.TestCase):
    def test_free_pad_and_bilateral_contact_are_not_route_calibration(self):
        result=restart.classify_restart(snapshot())
        self.assertEqual(result['state'],'unknown')
        self.assertEqual(predicate(result,'recovery_buffer_inventory')['state'],'pass')
        self.assertEqual(predicate(result,'measured_recovery_route')['state'],'unknown')
    def test_exact_supplied_envelopes_can_be_admissible(self):
        scene=snapshot();result=restart.classify_restart(scene,calibration=calibration(scene))
        self.assertEqual(result['state'],'admissible',result)
        self.assertTrue(result['configured_phase_reached'])
        self.assertFalse(any(result['effects'].values()))
    def test_unilateral_empty_or_two_payload_grip_fails(self):
        for alteration in ('unilateral','empty','two'):
            scene=snapshot();evidence=calibration(scene)
            if alteration=='unilateral':scene['contacts']['by_object']['A1'].update(right_normal_force_N=0.,bilateral_force_bearing=False)
            elif alteration=='empty':scene['contacts']['by_object']['A1'].update(hand_contact=False,bilateral_force_bearing=False)
            else:
                extra=copy.deepcopy(scene['geometry']['objects'][0]);extra['id']='B2';scene['geometry']['objects'].append(extra)
                scene['expected_object_ids'].append('B2');scene['contacts']['by_object']['B2']=copy.deepcopy(scene['contacts']['by_object']['A1'])
            with self.subTest(alteration=alteration):
                result=restart.classify_restart(scene,calibration=evidence)
                self.assertEqual(result['state'],'inadmissible')
                self.assertEqual(predicate(result,'phase_contact_consistency')['state'],'fail')
    def test_different_configuration_unverified_or_future_outcome_is_unknown(self):
        for alteration in ('physics','source','unverified','episode_outcome','missing_envelope','final_success_only'):
            scene=snapshot();evidence=calibration(scene)
            if alteration=='physics':evidence['grip']['physical_configuration_sha256']='0'*64
            elif alteration=='source':evidence['grip']['source_hashes']['cell.py']='0'*64
            elif alteration=='unverified':evidence['grip']['evidence_refs'][0]['bytes_verified_by_operator']=False
            elif alteration=='episode_outcome':evidence['grip']['evidence_refs'][0]['kind']='episode_final_success'
            elif alteration=='missing_envelope':del evidence['grip']['envelope']['relative_rotation']
            else:evidence={'final_success':True,'delivered':10}
            with self.subTest(alteration=alteration):self.assertEqual(restart.classify_restart(scene,calibration=evidence)['state'],'unknown')
    def test_grip_outside_measured_force_pose_or_clearance_fails(self):
        for alteration in ('load','pose','clearance','rotation'):
            scene=snapshot();evidence=calibration(scene)
            if alteration=='load':scene['contacts']['by_object']['A1']['left_normal_force_N']=100.
            elif alteration=='pose':scene['object_poses']['A1']['relative_to_tcp']['position_m'][0]=.02
            elif alteration=='clearance':scene['geometry']['objects'][0]['bounds']['min'][2]=.09
            else:scene['object_poses']['A1']['relative_to_tcp']['rotation']=[[0.,-1.,0.],[1.,0.,0.],[0.,0.,1.]]
            with self.subTest(alteration=alteration):
                self.assertEqual(predicate(restart.classify_restart(scene,calibration=evidence),'measured_grip_envelope')['state'],'fail')
    def test_a_free_destination_with_blocked_calibrated_corridor_fails(self):
        scene=snapshot();evidence=calibration(scene);extra=copy.deepcopy(scene['geometry']['objects'][0]);extra['id']='B2'
        extra['bounds']={'min':[.16,-.05,.20],'max':[.20,-.01,.24]};scene['geometry']['objects'].append(extra)
        scene['expected_object_ids'].append('B2');scene['contacts']['by_object']['B2']={**scene['contacts']['by_object']['A1'],'hand_contact':False,'bilateral_force_bearing':False}
        result=restart.classify_restart(scene,calibration=evidence)
        self.assertEqual(predicate(result,'recovery_buffer_inventory')['state'],'pass')
        self.assertEqual(predicate(result,'measured_recovery_route')['state'],'fail')
    def test_no_free_buffer_is_task_difficulty_not_infrastructure_assignment(self):
        scene=snapshot();evidence=calibration(scene);extra=copy.deepcopy(scene['geometry']['objects'][0]);extra['id']='B2'
        extra['bounds']={'min':[.18,-.11,0.],'max':[.22,-.07,.04]};scene['geometry']['objects'].append(extra)
        scene['expected_object_ids'].append('B2');scene['contacts']['by_object']['B2']={**scene['contacts']['by_object']['A1'],'hand_contact':False,'bilateral_force_bearing':False}
        result=restart.classify_restart(scene,calibration=evidence)
        self.assertEqual(result['state'],'inadmissible');self.assertEqual(result['infrastructure']['status'],'valid')
        self.assertEqual(predicate(result,'recovery_buffer_inventory')['domain'],'task_resource')
    def test_active_machine_or_inspection_timer_stays_unknown(self):
        for timer in ('cycle','inspection_due'):
            scene=snapshot();scene['devices'][timer]={'part_id':'A1','due':12.}
            with self.subTest(timer=timer):self.assertEqual(restart.classify_restart(scene,calibration=calibration(scene))['state'],'unknown')
    def test_stale_planner_or_sensor_age_not_silently_valid(self):
        scene=snapshot();evidence=calibration(scene);scene['authority']['planner']={'exists':True,'generation':1}
        self.assertEqual(restart.classify_restart(scene,calibration=evidence)['state'],'unknown')
        scene=snapshot();scene['observation']['last_capture_age_s']=1.
        self.assertEqual(restart.classify_restart(scene,calibration=evidence)['state'],'unknown')
    def test_phase_claim_is_retained_even_when_physical_phase_disagrees(self):
        scene=snapshot();scene['authority']['segment']['phase']=2
        result=restart.classify_restart(scene,calibration=calibration(scene))
        self.assertTrue(result['configured_phase_reached']);self.assertEqual(result['state'],'inadmissible')
    def test_fallback_remains_unknown_not_relabelled_as_easy_cut(self):
        scene=snapshot();scene['exposure'].update(actual_cut='deadline_fallback',configured_milestone_exercised=False,fallback_used=True)
        result=restart.classify_restart(scene,calibration=calibration(scene))
        self.assertFalse(result['configured_phase_reached']);self.assertEqual(result['state'],'unknown')
    def test_released_open_supported_contained_and_slow_can_pass(self):
        self.assertEqual(restart.classify_restart(snapshot('after_release'))['state'],'admissible')
    def test_released_not_supported_crossing_rim_or_moving_fails(self):
        for alteration in ('support','rim','velocity','jaw'):
            scene=snapshot('after_release')
            if alteration=='support':scene['contacts']['by_object']['A1']['support_upward_force_N']=0.
            elif alteration=='rim':scene['geometry']['objects'][0]['bounds']['max'][0]=.26
            elif alteration=='velocity':scene['geometry']['objects'][0]['linear_velocity'][0]=.1
            else:scene['robot']['jaw_width_m']=.04
            with self.subTest(alteration=alteration):self.assertEqual(restart.classify_restart(scene)['state'],'inadmissible')
    def test_nan_or_lost_body_cannot_pass(self):
        scene=snapshot();scene['robot']['joint_position_rad'][0]=math.nan
        self.assertEqual(restart.classify_restart(scene)['state'],'inadmissible')
        scene=snapshot();scene['expected_object_ids'].append('B2')
        self.assertEqual(restart.classify_restart(scene)['state'],'inadmissible')
    def test_missing_contact_evidence_is_unknown(self):
        scene=snapshot();del scene['contacts']
        self.assertEqual(restart.classify_restart(scene)['state'],'unknown')
    def test_no_input_mutation(self):
        scene=snapshot();evidence=calibration(scene);original=copy.deepcopy((scene,evidence))
        restart.classify_restart(scene,calibration=evidence)
        self.assertEqual((scene,evidence),original)
    def test_unrelated_airborne_body_is_not_an_admissible_release(self):
        scene=snapshot('after_release');extra=copy.deepcopy(scene['geometry']['objects'][0]);extra.update(id='B2',position=[.6,0.,.5])
        extra['bounds']={'min':[.58,-.02,.48],'max':[.62,.02,.52]};scene['geometry']['objects'].append(extra)
        scene['expected_object_ids'].append('B2');scene['contacts']['by_object']['B2']=copy.deepcopy(scene['contacts']['by_object']['A1'])
        result=restart.classify_restart(scene)
        self.assertEqual(predicate(result,'unheld_bodies_supported_and_slow')['state'],'fail')
    def test_velocity_outside_measured_route_is_not_hidden_by_position_match(self):
        scene=snapshot();evidence=calibration(scene);scene['robot']['joint_velocity_rad_s'][0]=.2
        self.assertEqual(predicate(restart.classify_restart(scene,calibration=evidence),'measured_recovery_route')['state'],'fail')


class ContactAndPoseTests(unittest.TestCase):
    def record(self,*,object_side=2,finger=None,normal=2.,active=True,upward=True):
        other=3-object_side
        result={'index':0,'distance_m':0.,'object1':None,'object2':None,'gripper_side1':None,'gripper_side2':None,
                'position_m':[0.,0.,0.],'object1_center_z_m':None,'object2_center_z_m':None,
                'force_contact_N_Nm':[normal,0.,0.,0.,0.,0.],'force_world_on_geom2_N':[0.,0.,normal if object_side==2 else -normal],
                'constraint_active':active,'support_eligible1':True,'support_eligible2':True}
        result[f'object{object_side}']='A1';result[f'object{object_side}_center_z_m']=.018;result[f'gripper_side{other}']=finger
        if not upward:result['force_world_on_geom2_N'][2]*=-1
        return result
    def test_normal_force_sign_support_is_independent_of_geom_order(self):
        for side in (1,2):
            with self.subTest(side=side):self.assertEqual(restart.contact_evidence([self.record(object_side=side)],['A1'])['A1']['support_upward_force_N'],2.)
        self.assertEqual(restart.contact_evidence([self.record(upward=False)],['A1'])['A1']['support_upward_force_N'],0.)
    def test_inactive_proximity_contact_cannot_prove_bilateral_load(self):
        records=[self.record(finger='left'),self.record(finger='right',active=False)]
        result=restart.contact_evidence(records,['A1'])['A1']
        self.assertTrue(result['right_finger_contact']);self.assertFalse(result['bilateral_force_bearing'])
        self.assertEqual(result['support_upward_force_N'],0.)
    def test_unregistered_robot_link_does_not_count_as_support(self):
        record=self.record();record['support_eligible1']=False
        self.assertEqual(restart.contact_evidence([record],['A1'])['A1']['support_upward_force_N'],0.)
    def test_rotated_tcp_relative_pose(self):
        rotation=[[0.,-1.,0.],[1.,0.,0.],[0.,0.,1.]]
        result=restart.relative_pose([1.,1.,1.],rotation,[1.,2.,1.],rotation)
        self.assertEqual(result['position_m'],[1.,0.,0.]);self.assertEqual(result['rotation'],I)


class CaptureAdapterTests(unittest.TestCase):
    def test_read_only_capture_records_real_api_shapes_without_advancing(self):
        import numpy as np
        scene=snapshot();names={'hand':1,'left_finger':2,'right_finger':3,'A1':4}
        backend=SimpleNamespace(mjtObj=SimpleNamespace(mjOBJ_BODY=1,mjOBJ_GEOM=2),
            mj_name2id=lambda m,k,name:names.get(name,-1),mj_id2name=lambda m,k,i:f'body-{i}' if k==1 else f'geom-{i}',
            mj_contactForce=lambda m,d,i,array:array.__setitem__(0,5.+i))
        model=SimpleNamespace(body_parentid=np.array([0,0,1,1,0]),geom_bodyid=np.array([2,3,4]),
                              opt=SimpleNamespace(timestep=.002,integrator=1,gravity=np.array([0.,0.,-9.81])))
        for name in ('body_mass','body_inertia','geom_type','geom_size','geom_friction','geom_solref','geom_solimp','jnt_type','jnt_axis',
                     'actuator_gainprm','actuator_biasprm','actuator_ctrlrange','actuator_forcerange'):setattr(model,name,np.ones((8,3)))
        model.jnt_range=np.array([[-2.,2.]]*7)
        data=SimpleNamespace(time=10.,ncon=2,qpos=np.array([0.]*7+[.02,.02]),qvel=np.zeros(9),actuator_force=np.zeros(8),ctrl=np.zeros(8),
            xpos=np.array([[0.,0.,0.],[.3,0.,.15],[.3,0.,.15],[.3,0.,.15],[.3,0.,.15]]),xmat=np.array([np.eye(3).ravel()]*5),
            site_xpos=np.array([[.3,0.,.15]]),site_xmat=np.array([np.eye(3).ravel()]),
            contact=[SimpleNamespace(geom1=0,geom2=2,frame=np.eye(3).ravel(),dist=0.,pos=np.array([.3,0.,.15]),efc_address=0),
                     SimpleNamespace(geom1=2,geom2=1,frame=np.eye(3).ravel(),dist=0.,pos=np.array([.3,0.,.15]),efc_address=1)])
        cell=SimpleNamespace(model=model,data=data,evaluator=SimpleNamespace(snapshot_cell=lambda *a,**k:copy.deepcopy(scene['geometry'])),
            registry={'A1':{'family':'A'}},tcp=0,xml='<synthetic/>',active_request=scene['authority']['active_request'],plan_generation=2,
            lease_deadline=11.,segment={'phase':5},motion=[],direct_command=None,plan_future=None,pending_plan_generation=None,
            direct_plan_future=None,direct_plan_generation=None,_setup_wait=None,station=scene['devices']['station'],cycle=None,
            inspection_due=None,inspection=None,detection_time=9.98,last_sensor_result=SimpleNamespace(sequence=12))
        before=data.qpos.copy()
        with patch.dict(sys.modules,{'mujoco':backend}):
            result=restart.capture_restart_state(cell,zones={'parking2':(.2,-.09)},zone_half=lambda z:(.053,.053),
                      exposure=scene['exposure'],source_hashes=scene['source_hashes'])
        self.assertEqual(data.time,10.);self.assertTrue(np.array_equal(before,data.qpos))
        self.assertEqual(result['contacts']['by_object']['A1']['left_normal_force_N'],5.)
        self.assertEqual(result['contacts']['by_object']['A1']['right_normal_force_N'],6.)
        self.assertTrue(result['contacts']['by_object']['A1']['bilateral_force_bearing'])
        self.assertEqual(result['authority']['generation'],2);self.assertEqual(result['capture_errors'],[])
        checksum=result.pop('snapshot_sha256');self.assertEqual(checksum,restart.digest(result))


if __name__=='__main__':unittest.main()
