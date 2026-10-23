"""Prospective scene extension. Protected implementation, never a robot tool.

The exact r4 arm, servo, contact physics, cameras and A/B code are inherited.
Only a C parcel and a non-colliding destination marking are added. No C planner.
"""
from __future__ import annotations
import copy
import colorsys
import math
import xml.etree.ElementTree as ET
import numpy as np
from common import inherited_paths, load_module, RUNTIME

inherited_paths()
base = load_module('campaign004_base_cell', RUNTIME/'cell.py')
import sensor_c
base.derive_detections = sensor_c.derive_detections
original_scene = base.build_scene
BASE_ZONES = dict(base.ZONES)
C_PAD = (.52, -.13)
C_SOURCE = (.38, -.24)
C_HALF = (.021, .021, .018)
base.ZONES = {**BASE_ZONES, 'C_pad': C_PAD}

def build_scene(n=3, seed=173, layout_seed=None):
    # Original A/B generation sees its original zone map; new marking is added
    # afterwards so the original scene prefix and all rigid bodies stay exact.
    zones = base.ZONES
    try:
        base.ZONES = BASE_ZONES
        xml, registry = original_scene(n, seed, layout_seed)
    finally:
        base.ZONES = zones
    root = ET.fromstring(xml)
    world, asset = root.find('worldbody'), root.find('asset')
    ET.SubElement(world,'geom', name='zone_C_pad',type='box',
        pos=f'{C_PAD[0]} {C_PAD[1]} -.001',size='.053 .053 .001',
        rgba='.38 .38 .38 1',contype='0',conaffinity='0')
    ET.SubElement(asset,'material',name='tagmat_C1',rgba='.175 .0175 .35 1',emission='.7',specular='0',shininess='0')
    # Same cuboid dimensions, mass and contact parameters as existing A1.
    parcel=copy.deepcopy(world.find("body[@name='A1']"))
    parcel.set('name','C1'); parcel.set('pos',f'{C_SOURCE[0]} {C_SOURCE[1]} .021')
    for node in parcel.iter():
        if node.get('name'): node.set('name',node.get('name').replace('A1','C1'))
        if node.get('material')=='tagmat_A1':node.set('material','tagmat_C1')
    # Zero-mass, non-contact decals preserve the original rigid-body model.
    side_rgb=colorsys.hsv_to_rgb(.95,.95,.35)
    ET.SubElement(asset,'material',name='tagmat_C1_side',rgba=' '.join(map(str,side_rgb))+' 1',
                  emission='.7',specular='0',shininess='0')
    faces=[('bottom',[0,0,-.0184],[0,1,0,0],'tagmat_C1'),
           ('xp',[.0214,0,0],[2**-.5,0,2**-.5,0],'tagmat_C1_side'),
           ('xm',[-.0214,0,0],[2**-.5,0,-2**-.5,0],'tagmat_C1_side'),
           ('yp',[0,.0214,0],[2**-.5,-2**-.5,0,0],'tagmat_C1_side'),
           ('ym',[0,-.0214,0],[2**-.5,2**-.5,0,0],'tagmat_C1_side')]
    for name,pos,quat,material in faces:
        ET.SubElement(parcel,'geom',name='c4_identity_'+name,type='box',size='.014 .014 .0003',
                      pos=' '.join(map(str,pos)),quat=' '.join(map(str,quat)),material=material,
                      contype='0',conaffinity='0',mass='0')
    world.append(parcel)
    registry['C1']={**copy.deepcopy(registry['A1']),'family':'C','hue':.7456,
                    'side_face_hue':.95,'side_face_half_height_m':.021}
    return ET.tostring(root,encoding='unicode'), registry

base.build_scene = build_scene

class Cell(base.Cell):
    def submit(self, action):
        op=action.get('operation')
        if (op in ('transport','cycle','inspect') and action.get('part_id')=='C1'
            or op in ('transport','recover_held') and action.get('destination')=='C_pad'
            or op=='setup' and action.get('family')=='C'):
            return {'status':'rejected','request_id':action.get('request_id'),
                    'reason':'No installed task skill for family C or C_pad; lower-level arm controls are available'}
        return super().submit(action)

    def plan_transport(self, part_id, destination, objective=None):
        if part_id=='C1' or destination=='C_pad':
            raise ValueError('No C task planner is installed')
        return super().plan_transport(part_id,destination,objective)

    def public_packet(self, order, run_id, incarnation, sequence):
        result=super().public_packet(order,run_id,incarnation,sequence)
        result['workcell_geometry']={'frame':'world','units':'metres',
            'C_pad':{'center_xy_m':list(C_PAD),'half_extent_xy_m':[.053,.053],'surface_z_m':0.0},
            'source':'declared public fixed workcell drawing; object positions come from rendered RGB-D'}
        return result

    def c_truth(self):
        """Protected evaluator input; absent from public packets and broker."""
        import mujoco
        body=mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_BODY,'C1')
        position=self.actual_pos('C1')
        bounds=np.abs(self.data.xmat[body].reshape(3,3))@np.array(C_HALF)
        return dict(position_m=position.tolist(),bounds_m=bounds.tolist(),
                    speed_m_s=float(np.linalg.norm(self.data.cvel[body,3:])),
                    jaw_width_m=float(sum(self.data.qpos[7:9])),
                    tcp_m=self.data.site_xpos[self.tcp].tolist(),sim_time_s=float(self.data.time))

def independently_placed(value):
    p=np.array(value['position_m']); b=np.array(value['bounds_m'])
    return bool(np.all(np.isfinite(p)) and np.all(np.abs(p[:2]-C_PAD)+b[:2]<.053)
                and abs(p[2]-b[2])<.006 and value['speed_m_s']<.02
                and value['jaw_width_m']>=.065
                and np.linalg.norm(np.array(value['tcp_m'])-p)>.09)
