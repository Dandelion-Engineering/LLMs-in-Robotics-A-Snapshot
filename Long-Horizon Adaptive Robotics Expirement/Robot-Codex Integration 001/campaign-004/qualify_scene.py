"""Developer-only contact/reachability proof. Never copied into a guest mount."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import time
import traceback
import xml.etree.ElementTree as ET
import numpy as np
from common import save
from cell_c import Cell, base, original_scene, BASE_ZONES, C_PAD, independently_placed
from png import write_png

def wait_motion(cell,limit=90):
    start=float(cell.data.time);wall=time.perf_counter()
    while cell.active_request or cell._planning_busy():
        cell.renew_authority(1,1);cell.tick()
        if int(round(cell.data.time/.002))%50==0:cell.sense()
        if cell.data.time-start>limit:raise RuntimeError('Motion timeout')
        time.sleep(max(0,.002-(time.perf_counter()-wall)));wall=time.perf_counter()

def action(cell,value,index):
    cell.sense()
    request={**value,'request_id':f'proof-{index}','order_version':1,'incarnation':1}
    receipt=cell.submit(request)
    if receipt['status']!='accepted':raise RuntimeError(str(receipt))
    wait_motion(cell)
    feedback=next((f for f in reversed(cell.feedback) if f['request_id']==request['request_id']),None)
    if not feedback or feedback['status']!='completed':raise RuntimeError(str(feedback))
    return dict(request=request,admission=receipt,feedback=feedback,truth=cell.c_truth())

def run(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    receipt=dict(passed=False,model_calls=0,track='developer deterministic contact proof; timing not qualified here',checks={},actions=[])
    cell=None
    try:
        cell=Cell(3,173,noise_seed=33001)
        for _ in range(500):cell.tick()
        cell.prepare_sensor();detections,rgb,depth=cell.sense();write_png(output/'initial.png',rgb)
        receipt['initial_detections']=detections;receipt['initial_c_truth']=cell.c_truth()
        # XML equality after removing the only permitted additions.
        root=ET.fromstring(cell.xml)
        root.find('worldbody').remove(root.find("worldbody/body[@name='C1']"))
        root.find('worldbody').remove(root.find("worldbody/geom[@name='zone_C_pad']"))
        root.find('asset').remove(root.find("asset/material[@name='tagmat_C1']"))
        root.find('asset').remove(root.find("asset/material[@name='tagmat_C1_side']"))
        current=base.ZONES
        try:base.ZONES=BASE_ZONES;old,_=original_scene(3,173)
        finally:base.ZONES=current
        receipt['checks']['unchanged_original_scene']=ET.tostring(root)==ET.tostring(ET.fromstring(old))
        receipt['checks']['c_visible_in_rgbd']=any(d['id']=='C1' for d in detections)
        rejects=[]
        for i,item in enumerate([{'operation':'transport','part_id':'C1','destination':'C_pad'},
                    {'operation':'transport','part_id':'A1','destination':'C_pad'},
                    {'operation':'transport','part_id':'C1','destination':'inspection'},
                    {'operation':'recover_held','destination':'C_pad'},
                    {'operation':'setup','family':'C'}, {'operation':'cycle','part_id':'C1','recipe':'C'},
                    {'operation':'inspect','part_id':'C1'}]):
            rejects.append(cell.submit({**item,'request_id':f'rejection-{i}','order_version':1,'incarnation':1}))
        receipt['rejections']=rejects;receipt['checks']['no_c_high_level_skill']=all(x['status']=='rejected' for x in rejects)
        c=next(d for d in detections if d['id']=='C1');source=np.array(c['pos']);source[2]=max(source[2],.018)
        # Private deterministic witness: only public-interface Cartesian targets.
        # No high-level C planner, weld, qpos editing or changed actuator limits.
        points=[([source[0],source[1],.22],255),([source[0],source[1],.11],255),
                (source.tolist(),255),(source.tolist(),0),([source[0],source[1],.11],0),
                ([source[0],source[1],.22],0),([C_PAD[0],C_PAD[1],.22],0),
                ([C_PAD[0],C_PAD[1],.11],0),([C_PAD[0],C_PAD[1],.021],0),
                ([C_PAD[0],C_PAD[1],.021],255),([C_PAD[0],C_PAD[1],.14],255)]
        for index,(target,grip) in enumerate(points,1):
            receipt['actions'].append(action(cell,dict(operation='cartesian_target',position=target,duration_s=1.9,gripper=grip),index))
            save(output/f'after-{index:02d}.json',receipt['actions'][-1])
        for _ in range(600):cell.tick()
        receipt['final_c_truth']=cell.c_truth();receipt['checks']['c_placed']=independently_placed(cell.c_truth())
        _,rgb,_=cell.sense();write_png(output/'placed.png',rgb)
        # Exercise unchanged A and B transport with fresh rendered observations.
        for i,(part,destination) in enumerate([('A1','inspection'),('B2','parking1')],20):
            receipt['actions'].append(action(cell,dict(operation='transport',part_id=part,destination=destination),i))
            receipt['checks'][part+'_transport']=cell._physical_zone(part,destination)
        receipt['checks']['only_allowed_lower_level_c']=all(x['request']['operation']=='cartesian_target' for x in receipt['actions'][:11])
        receipt['checks']['unchanged_arm_limits']=cell.arm_adapter.public_spec()==base.Cell.arm_adapter.public_spec() if hasattr(base.Cell,'arm_adapter') else receipt['checks']['unchanged_original_scene']
        receipt['passed']=all(receipt['checks'].values())
    except Exception as error:receipt['error']=str(error);receipt['traceback']=traceback.format_exc()
    finally:
        if cell is not None:cell.close()
        save(output/'receipt.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('actions','initial_detections','traceback')}),flush=True)
    return 0 if receipt['passed'] else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args();raise SystemExit(run(a.output))
