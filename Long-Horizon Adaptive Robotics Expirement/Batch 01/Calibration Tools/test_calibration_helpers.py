"""Synthetic helper checks only. Imports no Runtime, MuJoCo or sandbox runner.

Fixtures are in-memory or temporary; they never enter the canonical run map.
"""
import base64
import copy
import hashlib
import io
import json
import struct
import unittest
import zipfile
import zlib

import physical_calibration as driver
import raw_camera_fixture as fixture


def snapshot():
    item={'id':'A1','kind':'part','family':'A','position':[.20,-.09,.018],
          'bounds':{'min':[.179,-.111,0.],'max':[.221,-.069,.036]},
          'linear_velocity':[0.,0.,0.],'angular_velocity':[0.,0.,0.],
          'gripper_contact':False,'recipe':None,'cycles':0}
    return {'objects':[item],'zones':{'parking2':{'min':[.147,-.143,-.003],'max':[.253,-.037,.08]}},
            'pending':{k:False for k in ('active_request','queued_motion','active_segment','machine_cycle','inspection')},
            'arm_velocity':[0.]*7,'finger_velocity':[0.,0.]}


def png(data=b'\x01\x02\x03\x04\x05\x06',width=2,height=1):
    def chunk(tag,value):return struct.pack('!I',len(value))+tag+value+struct.pack('!I',zlib.crc32(tag+value))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0'+data))+chunk(b'IEND',b'')


def depth(values=(1.,2.),shape=(1,2)):
    header=repr({'descr':'<f4','fortran_order':False,'shape':shape}).encode('ascii')+b'\n'
    data=struct.pack('<'+'f'*len(values),*values)
    npy=b'\x93NUMPY\x01\x00'+struct.pack('<H',len(header))+header+data
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as archive:archive.writestr('depth_m.npy',npy)
    return out.getvalue(),data


def response():
    rgb=png();dep,_=depth()
    def entry(blob,encoding):return {'encoding':encoding,'data':base64.b64encode(blob).decode(),'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()}
    return {'status':'ok','camera':'overhead','request_id':'fixture-overhead','capture_id':'overhead-synthetic',
            'capture_sequence':-1,'capture_sim_time_s':1.,'capture_telemetry':{'sim_time_s':1.},
            'calibration':{'camera':'overhead','width_px':2,'height_px':1,'intrinsics_px':[[1.,0.,.5],[0.,1.,0.],[0.,0.,1.]],
                           'world_from_camera_rotation':[[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]],'camera_position_world_m':[0.,0.,1.]},
            'images':{'rgb':entry(rgb,'png-base64'),'depth':entry(dep,'npz-base64')}}


class PlacementChecks(unittest.TestCase):
    def test_complete_raw_containment(self):
        self.assertTrue(driver.placement_check(snapshot(),'A1','parking2',.08)['passed_now'])
    def test_full_bound_protrusion_fails_even_with_center_inside(self):
        scene=snapshot();scene['objects'][0]['bounds']['max'][0]=.26
        self.assertFalse(driver.placement_check(scene,'A1','parking2',.08)['passed_now'])
    def test_floor_rim_closed_grip_and_contact_are_not_success(self):
        for change in ('below_floor','above_rim','contact','closed'):
            with self.subTest(change=change):
                scene=snapshot();width=.08
                if change=='below_floor':scene['objects'][0]['bounds']['min'][2]=-.004
                if change=='above_rim':scene['objects'][0]['bounds']['max'][2]=.081
                if change=='contact':scene['objects'][0]['gripper_contact']=True
                if change=='closed':width=.04
                self.assertFalse(driver.placement_check(scene,'A1','parking2',width)['passed_now'])
    def test_extra_pad_occupant_fails(self):
        scene=snapshot();second=copy.deepcopy(scene['objects'][0]);second['id']='B2';scene['objects'].append(second)
        self.assertFalse(driver.placement_check(scene,'A1','parking2',.08)['passed_now'])
    def test_motion_pending_and_processed_item_fail(self):
        for key in ('motion','pending','processed'):
            with self.subTest(key=key):
                scene=snapshot()
                if key=='motion':scene['objects'][0]['linear_velocity'][0]=.06
                if key=='pending':scene['pending']['active_segment']=True
                if key=='processed':scene['objects'][0]['recipe']='A';scene['objects'][0]['cycles']=1
                self.assertFalse(driver.placement_check(scene,'A1','parking2',.08)['passed_now'])
    def test_dwell_cannot_skip_physics_samples_or_transient(self):
        dwell=driver.StablePredicate()
        for i in range(250):self.assertFalse(dwell.update(i*.002,True))
        self.assertTrue(dwell.update(.5,True))
        self.assertFalse(dwell.update(.502,False))
        self.assertFalse(dwell.update(1.,True))
        self.assertFalse(dwell.update(2.,True))
    def test_fixed_caps_and_no_default_all(self):
        self.assertEqual(set(driver.MODES),set(driver.SIM_CAPS))
        self.assertTrue(all(0<driver.SIM_CAPS[k]<driver.HARD_CAPS[k]<=225 for k in driver.MODES))
    def test_sensor_missingness_is_not_zero_error(self):
        scene=snapshot()
        missing=driver.sensor_comparison({'detections':[]},scene)
        self.assertEqual(missing['missing_ids'],['A1'])
        self.assertNotIn('euclidean_error_m',missing['rows'][0])
        observed={'id':'A1','pos':[.205,-.09,.018],'uncertainty_m':.004,'pixels':20,'zone':'parking2','visible_mark':'raw'}
        measured=driver.sensor_comparison({'detections':[observed]},scene)
        self.assertAlmostEqual(measured['rows'][0]['euclidean_error_m'],.005)
        self.assertFalse(measured['rows'][0]['error_within_reported_scalar'])
        self.assertEqual(observed['uncertainty_m'],.004)


class RawDecoderChecks(unittest.TestCase):
    def test_stdlib_round_trip_preserves_bytes(self):
        result=fixture.inspect_response(response())
        self.assertEqual(result['images']['rgb']['decoded_sha256'],hashlib.sha256(b'\x01\x02\x03\x04\x05\x06').hexdigest())
        self.assertEqual(result['images']['depth']['decoded_sha256'],hashlib.sha256(depth()[1]).hexdigest())
    def test_mismatch_in_encoded_bytes_fails(self):
        value=response();value['images']['rgb']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'identity'):fixture.inspect_response(value)
    def test_bad_png_crc_fails(self):
        value=bytearray(png());value[-1]^=1
        with self.assertRaisesRegex(ValueError,'CRC'):fixture.decode_png(bytes(value))
    def test_nonfinite_or_nonpositive_depth_fails(self):
        for bad in (float('nan'),float('inf'),0.,-1.):
            with self.subTest(bad=bad),self.assertRaises(ValueError):fixture.decode_depth(depth((1.,bad))[0])
    def test_bad_dimensions_and_capture_clock_fail(self):
        for change in ('dimension','clock','identity','camera'):
            with self.subTest(change=change):
                value=response()
                if change=='dimension':value['calibration']['height_px']=2
                if change=='clock':value['capture_telemetry']['sim_time_s']=2.
                if change=='identity':value['capture_id']='wrist-other'
                if change=='camera':value['calibration']['camera']='wrist'
                with self.assertRaises(ValueError):fixture.inspect_response(value)
    def test_operator_paths_fail_before_delivery(self):
        for path in ('C:\\protected\\truth.json','/mnt/c/private','/home/operator/private'):
            with self.subTest(path=path),self.assertRaises(ValueError):fixture.check_no_paths({'reason':path})
        with self.assertRaises(ValueError):fixture.check_no_paths({'images':{'path':'protected.png'}})
    def test_fixture_is_sensor_only(self):
        candidate=fixture.Candidate('fixture',None,False)
        self.assertEqual(candidate.step({'camera':'oblique'})['type'],'sensor_request')
        candidate.accept_sensor(response());self.assertEqual(len(candidate.drain_events()),1)
        self.assertEqual(candidate.drain_events(),[])
        with self.assertRaises(ValueError):candidate.accept_model('{}')


if __name__=='__main__':unittest.main()
