"""Small RGB-D marker tests; no simulator, renderer, queue or hidden state."""
import unittest
import base64
import struct
import zlib
import numpy as np
from sensor_worker import classify_process_mark, derive_detections


class ProcessMarkTests(unittest.TestCase):
    def test_recorded_real_rgbd_crops_raw_processed_and_white_robot_occlusion(self):
        # Exact 7x5 RGB uint8 + depth float32 crops and tag depth float64, all
        # image-derived. Source hashes/coordinates are retained in Batch 01 /
        # SensorMarkProposal/marker-core-calibration.json. No evaluator inputs.
        # Raw: physical-calibration-001 held-recovery frame000001 (A1/B2/A3).
        # Processed/occluder: C0-004 frame000419 (A1/B10).
        fixtures=[
            ('raw-A1','raw','eJxbbMUjIiwMQQEBQYuozRUWEgIiIHdl9Gz7FVAMYm/sn2s/UGIMDAwKpdmf7QGBqlbk'),
            ('raw-B2','raw','eJwrPMslJCgIQdp6RoVU4mohcQUFBIDcldGz7Vcg4Z1cC+wHSowBCEqzP9sDACedUrg='),
            ('raw-A3','raw','eJzjmVUgwM8PQea2zjwwLj8fn7mNE4QLZMO5EDZ27kx83JXRs+1XQDGIvZNrgf1AiTEwMCiUZn+2BwBpYlIB'),
            ('processed-A1','processed','eJy7KM/15dih///+A9HN6zcvUo97CZV7P2u2/T0kXGEy2x5d7JkZpliSJabYXWtMsU32mGL5zphivO6z7RkYGA5E5362BwCyS52k'),
            ('occluded-B10','unknown','eJy9jTELAQEARm/RLRYDJYMSX1kslEXelQykDFLqshhIUkoog4FFZDFYbjGw3K5MsvkF/oF/wOzcr1Bvfe95X8/7C3ZMjCPCCgkjKGqmCGdFKiP6aZFLil5cPKviVRYfSwQKYpsXTke4bXFtiUdDmHXfmYvpRCxH4jQQl64o7kVlJ5prsVmJ20JEXZE4i9JRzBy/c/D/hnG3h29+hLSUMA=='),
        ]
        for name,expected,encoded in fixtures:
            with self.subTest(name=name):
                raw=zlib.decompress(base64.b64decode(encoded))
                rgb=np.frombuffer(raw[:105],np.uint8).reshape(7,5,3)/255
                depth=np.frombuffer(raw[105:245],'<f4').reshape(7,5)
                tag_depth=struct.unpack('<d',raw[245:])[0]
                self.assertEqual(classify_process_mark(rgb,depth,tag_depth),expected)

    def test_visible_dark_and_white_retain_raw_and_processed(self):
        for value,expected in ((.03,'raw'),(.9,'processed')):
            self.assertEqual(classify_process_mark(np.full((7,5,3),value),np.full((7,5),1.2),1.2),expected)

    def test_raw_and_processed_survive_half_mm_depth_and_one_dn_readout_offsets(self):
        for value,expected in ((.03,'raw'),(.9,'processed')):
            for depth_offset in (-.0005,.0005):
                rgb=np.full((7,5,3),value)+np.array([-1.,0.,1.])/255
                self.assertEqual(classify_process_mark(rgb,np.full((7,5),1.2+depth_offset),
                    1.2+depth_offset),expected)  # Actual common correlated readout model.
                # Also retain the same classification with a small plane-depth discrepancy.
                self.assertEqual(classify_process_mark(rgb,np.full((7,5),1.2+depth_offset),1.2),expected)

    def test_recorded_b10_white_foreground_depth_is_unknown(self):
        self.assertEqual(classify_process_mark(np.full((7,5,3),.99869281),
            np.full((7,5),.6497912406921387),1.2141988277435303),'unknown')

    def test_dark_occlusion_and_background_are_also_unknown(self):
        for brightness,depth in ((.03,.7),(.9,1.3),(.03,1.3)):
            self.assertEqual(classify_process_mark(np.full((7,5,3),brightness),np.full((7,5),depth),1.2),'unknown')

    def test_gray_colored_and_mixed_appearance_are_unknown(self):
        for crop in (np.full((7,5,3),.5),np.tile([1.,1.,.5],(7,5,1)),
                     np.concatenate([np.full((3,5,3),.95),np.full((4,5,3),.03)])):
            self.assertEqual(classify_process_mark(crop,np.full((7,5),1.2),1.2),'unknown')

    def test_incomplete_invalid_and_partly_occluded_are_unknown(self):
        white=np.full((7,5,3),.9);depth=np.full((7,5),1.2)
        self.assertEqual(classify_process_mark(white[:3],depth[:3],1.2),'unknown')
        for invalid in (float('nan'),float('inf'),0.,-1.):
            self.assertEqual(classify_process_mark(white,depth,invalid),'unknown')
        broken=depth.copy();broken.flat[:4]=.7
        self.assertEqual(classify_process_mark(white,broken,1.2),'unknown')
        broken=depth.copy();broken[:]=float('nan')
        self.assertEqual(classify_process_mark(white,broken,1.2),'unknown')

    def test_joint_depth_color_support_cannot_be_combined_from_different_pixels(self):
        rgb=np.full((7,5,3),.9);rgb.reshape(-1,3)[:3]=.03
        depth=np.full((7,5),1.2);depth.flat[-3:]=.7
        self.assertEqual(classify_process_mark(rgb,depth,1.2),'unknown')

    def test_one_supported_column_is_insufficient_and_opposite_marks_conflict(self):
        depth=np.full((7,5),1.2);rgb=np.full((7,5,3),.5);rgb[:,2]=.95
        self.assertEqual(classify_process_mark(rgb,depth,1.2),'unknown')
        rgb[:,3]=.95;rgb[:,1]=.03
        self.assertEqual(classify_process_mark(rgb,depth,1.2),'unknown')

    def test_edge_contamination_does_not_allow_core_occlusion(self):
        rgb=np.full((7,5,3),.03);rgb[:,0]=[.9,.2,.1];rgb[:,4]=.5
        depth=np.full((7,5),1.2);depth[:,4]=1.23
        self.assertEqual(classify_process_mark(rgb,depth,1.2),'raw')
        depth[:,2]=.7
        self.assertEqual(classify_process_mark(rgb,depth,1.2),'unknown')

    def test_detector_preserves_visible_tag_when_mark_is_occluded(self):
        rgb=np.zeros((60,80,3),dtype=np.uint8);depth=np.full((60,80),1.2)
        rgb[20:32,20:32]=[255,0,0]
        # Tag median=(25.5,25.5); marker centre=(40,26), focal=960.
        rgb[23:30,38:43]=255;depth[23:30,38:43]=.65
        calibration={'world_from_camera_rotation':np.eye(3).tolist(),
                     'camera_position_world_m':[0,0,1.25],'focal_px':960.}
        registry={'A1':{'hue':0.,'half':[.021,.021,.018],'family':'A','kind':'part'}}
        detected=derive_detections(rgb,depth,calibration,registry,{}, {})
        self.assertEqual(len(detected),1);self.assertEqual(detected[0]['id'],'A1')
        self.assertEqual(detected[0]['visible_mark'],'unknown')
        depth[23:30,38:43]=1.2
        self.assertEqual(derive_detections(rgb,depth,calibration,registry,{}, {})[0]['visible_mark'],'processed')


if __name__=='__main__':unittest.main()
