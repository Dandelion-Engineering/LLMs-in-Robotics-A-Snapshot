"""Rendered six-face qualification; pose fixtures are protected test inputs."""
import argparse
import json
import math
from pathlib import Path
import traceback
import xml.etree.ElementTree as ET
import numpy as np
import mujoco
from common import save,sha
from cell_c import Cell,C_HALF,C_PAD,C_SOURCE,base
from controller import public_c_complete
from sensor_c import derive_detections
from sensor_worker import camera_calibration
from png import write_png

def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    result={'passed':False,'model_calls':0,'checks':{},'cases':[]};c=None
    try:
        c=Cell(3,173,noise_seed=44001)
        root=ET.fromstring(c.xml);body=root.find("worldbody/body[@name='C1']")
        for g in list(body):
            if g.get('name','').startswith('c4_identity_'):body.remove(g)
        root.find('asset').remove(root.find("asset/material[@name='tagmat_C1_side']"))
        legacy=mujoco.MjModel.from_xml_string(ET.tostring(root,encoding='unicode'))
        for name in ('body_mass','body_inertia','body_ipos','body_iquat','actuator_ctrlrange','jnt_range','dof_damping'):
            assert np.array_equal(getattr(legacy,name),getattr(c.model,name)),name
        for geom in list(root.iter('geom')):
            name=geom.get('name')
            if not name:continue
            a=legacy.geom(name).id;b=c.model.geom(name).id
            for field in ('geom_size','geom_friction','geom_contype','geom_conaffinity','geom_solref','geom_solimp'):
                assert np.array_equal(getattr(legacy,field)[a],getattr(c.model,field)[b]),(name,field)
        result['checks']['identical_mass_inertia_contacts_arm_and_dimensions']=True
        q=int(c.model.joint('free_C1').qposadr[0]);v=int(c.model.joint('free_C1').dofadr[0])
        h=2**-.5
        faces={'zp':[1,0,0,0],'zm':[0,1,0,0],'xp':[h,0,-h,0],'xm':[h,0,h,0],
               'yp':[h,h,0,0],'ym':[h,-h,0,0]}
        c.data.qpos[:7]=[.8,-.5,0,-2.2,0,1.7,.7854];c.data.ctrl[:7]=c.data.qpos[:7]
        c.prepare_sensor()
        order={'version':1,'kind':'C-placement','part_id':'C1','destination':'C_pad','requirements':[]}
        for place,xy in [('source',C_SOURCE),('pad',C_PAD)]:
            for face,quat in faces.items():
                for degrees in range(0,360,30):
                    yaw=np.array([math.cos(math.radians(degrees)/2),0,0,math.sin(math.radians(degrees)/2)])
                    orient=np.zeros(4);mujoco.mju_mulQuat(orient,yaw,np.array(quat,dtype=float))
                    height=.018 if face.startswith('z') else .021
                    c.data.qpos[q:q+7]=[*xy,height+.001,*orient];c.data.qvel[v:v+6]=0
                    mujoco.mj_forward(c.model,c.data)
                    for _ in range(250):c.tick()
                    for sample in range(3):
                        detections,rgb,depth=c.sense()
                        found=[d for d in detections if d['id']=='C1']
                        assert len(found)==1,(place,face,degrees,'missing identity')
                        truth=c.actual_pos('C1');error=np.array(found[0]['pos'])-truth
                        assert np.max(np.abs(error))<=.004,(place,face,degrees,error.tolist())
                        p=c.public_packet(order,'identity-fixture',1,len(result['cases'])+1)
                        p['tcp_position_m']=c.data.site_xpos[c.tcp].tolist()
                        if place=='pad':assert public_c_complete(p),(place,face,degrees,p)
                        result['cases'].append({'place':place,'face':face,'yaw_deg':degrees,'sample':sample,
                            'detection':found[0],'truth':truth.tolist(),'error_m':error.tolist(),
                            'public_completion':public_c_complete(p)})
                        if sample==0 and degrees in (0,90):write_png(out/f'{place}-{face}-{degrees}.png',rgb)
        result['checks']['all_432_rendered_stable_face_pose_noise_cases']=len(result['cases'])==432
        cal=camera_calibration(c.model,c.data)
        neutral=np.full_like(rgb,120)
        assert not any(d['id']=='C1' for d in derive_detections(neutral,depth,cal,c.registry,base.ZONES,{k:base.zone_half(k) for k in base.ZONES}))
        result['checks']['no_identity_without_visible_pigment']=True
        rejects=[]
        for i,action in enumerate([{'operation':'transport','part_id':'C1','destination':'C_pad'},
            {'operation':'transport','part_id':'A1','destination':'C_pad'},{'operation':'recover_held','destination':'C_pad'},
            {'operation':'setup','family':'C'},{'operation':'cycle','part_id':'C1','recipe':'C'},{'operation':'inspect','part_id':'C1'}]):
            rejects.append(c.submit({**action,'request_id':f'identity-exclusion-{i}','incarnation':1,'order_version':1}))
        assert all(r['status']=='rejected' for r in rejects)
        result['rejections']=rejects;result['checks']['no_high_level_C_skill']=True
        result['maximum_coordinate_error_m']=max(max(abs(v) for v in x['error_m']) for x in result['cases'])
        result['passed']=all(result['checks'].values())
    except Exception as e:result.update(error=str(e),traceback=traceback.format_exc())
    finally:
        if c:c.close()
        save(out/'receipt.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','rejections')}),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args();raise SystemExit(run(a.output))
