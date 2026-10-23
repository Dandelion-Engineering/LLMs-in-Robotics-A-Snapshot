"""Queue-only fixed pad relocation comparison; no stepping or physical success claim."""
from __future__ import annotations
import argparse
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import zipfile

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[1]
RUNTIME=PROJECT/'Runtime'
CALIBRATION=PROJECT/'Evidence/calibration/physical-calibration-002'
sys.path.insert(0,str(RUNTIME))


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);args=parser.parse_args()
    from release_runner import queued_job
    job=queued_job(expected_script=__file__)  # No model/kinematics until exact queue ownership.
    import numpy as np
    import mujoco
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(CALIBRATION/'source-bundle.zip') as archive:
        source=archive.read('Runtime/cell.py')
    tree=ast.parse(source);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Cell')
    function=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='ik')
    namespace={'np':np,'mujoco':mujoco};exec(compile(ast.Module(body=[function],type_ignores=[]),'retained-physical-calibration-002-Cell.ik','exec'),namespace)
    old_ik=namespace['ik']
    plan={'schema':'held-recovery-kinematic-replay-2.0','queue_job_id':job['id'],
        'started_at':datetime.now(timezone.utc).isoformat(),'script_sha256':digest(__file__),
        'retained_cell_sha256':hashlib.sha256(source).hexdigest(),
        'source':'physical-calibration-002 source bundle and public robot telemetry at recorded post-absence cut',
        'methods':['continuation-10mm'],
        'fixed_pad_centers':{'parking1':[.34,.04],'parking2':[.46,.12]},
        'constraints':'original120iterations,1mm position and.01 cross-product orientation tolerances; same vertical target rotation',
        'no_physics_steps':True,'collision_or_physical_carry_success_claimed':False}
    zones=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ZONES' for t in n.targets)))
    rest=ast.literal_eval(next(n.value.args[0] for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='HOME' for t in n.targets)))
    # Public declared region bounds, including conservative all-ten-part raw stock
    # envelope: 21mm half-size plus the fixed +/-3mm layout jitter.
    candidate_zones=dict(zones,parking1=(.34,.04),parking2=(.46,.12))
    regions={name:(np.array(center),np.array([.092,.065] if name.startswith('tray') else [.053,.053])) for name,center in candidate_zones.items()}
    regions['raw_stock_envelope']=(np.array([(.296+.514)/2,(-.334-.064)/2]),np.array([(.514-.296)/2,(.334-.064)/2]))
    overlaps=[]
    for padname in ('parking1','parking2'):
        center,half=regions[padname]
        for other,(othercenter,otherhalf) in regions.items():
            if other==padname:continue
            separation=np.abs(center-othercenter)-half-otherhalf
            overlaps.append({'pad':padname,'other':other,'axis_signed_gap_m':separation.tolist(),'positive_separation':bool(np.any(separation>0))})
    plan['fixed_region_checks']=overlaps
    plan['fixed_region_overlap_free']=all(row['positive_separation'] for row in overlaps)
    save(out/'manifest.json',plan);rows=[]
    for mode,variant,destination in [('held-recovery','old-parking2',[.2,-.09]),('held-recovery','new-parking2',[.46,.12]),('held-recovery-parking1','old-parking1',[.27,.05]),('held-recovery-parking1','new-parking1',[.34,.04])]:
        folder=CALIBRATION/mode
        with (folder/'events.jsonl').open() as stream:
            event=next(json.loads(line) for line in stream if '"protected_held_state_after_absence"' in line)
        robot=event['payload']['robot'];model=mujoco.MjModel.from_xml_path(str(folder/'world-0.xml'))
        data=mujoco.MjData(model);data.qpos[:7]=robot['joint_position_rad'];data.qpos[7:9]=robot['finger_position_m']
        mujoco.mj_forward(model,data);site=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_SITE,'tcp')
        if site<0:raise RuntimeError('Expected public TCP site absent')
        obj=SimpleNamespace(model=model,data=data,ikdata=mujoco.MjData(model),tcp=site,
                            jacp=np.zeros((3,model.nv)),jacr=np.zeros((3,model.nv)))
        configuration=data.qpos.copy();start=configuration[:7].copy();tcp=data.site_xpos[site].copy()
        if np.linalg.norm(tcp-robot['tcp_position_world_m'])>1e-7:raise RuntimeError('Public robot telemetry FK mismatch')
        above=max(float(tcp[2]),.021+.16);lift=np.r_[tcp[:2],above];pad=np.r_[destination,above];release=np.r_[destination,.021]
        input_record={'mode':mode,'variant':variant,'source_event_id':event['event_id'],'source_event_payload_sha256':event['payload_sha256'],
            'scene_xml_sha256':digest(folder/'world-0.xml'),'robot_joint_position':start.tolist(),'finger_position':robot['finger_position_m'],
            'tcp':tcp.tolist(),'waypoints':[lift.tolist(),pad.tolist(),release.tolist()]}
        save(out/(variant+'-public-input.json'),input_record)
        def solve(target,seed):
            began=time.perf_counter();error=None
            try:q=old_ik(obj,target,seed,configuration)
            except ValueError as exc:q=obj.ikdata.qpos[:7].copy();error=str(exc)
            obj.ikdata.qpos[:]=configuration;obj.ikdata.qpos[:7]=q;mujoco.mj_forward(model,obj.ikdata)
            rotation=obj.ikdata.site_xmat[site].reshape(3,3);goal=np.diag([1.,-1.,-1.])
            residual=np.array(target)-obj.ikdata.site_xpos[site]
            angle=float(np.arccos(np.clip((np.trace(goal.T@rotation)-1)/2,-1,1)))
            limits=model.jnt_range[:7];margin=np.minimum(q-limits[:,0],limits[:,1]-q)
            return {'target':np.asarray(target).tolist(),'q':q.tolist(),'position_error':residual.tolist(),
                'position_error_norm':float(np.linalg.norm(residual)),'orientation_error_rad':angle,
                'success':bool(error is None and np.linalg.norm(residual)<.001 and angle<.011),
                'original_error':error,'joint_margin_rad':margin.tolist(),'wall_s':time.perf_counter()-began}
        for method in plan['methods']:
            q=start.copy();position=tcp.copy();solutions=[];failure=None
            points=[lift,pad,release,release,pad]
            step=.01
            for index,target in enumerate(points):
                count=1 if step is None else max(1,int(np.ceil(np.linalg.norm(target-position)/step)))
                origin=position.copy()
                for sub in range(1,count+1):
                    result=solve(origin+(target-origin)*sub/count,q);result.update(leg=index,phase=20+index,grip=0 if index<3 else 255,substep=sub)
                    if result['success']:
                        endpoint=np.array(result['q']);path=[]
                        for fraction in np.linspace(0.,1.,11):
                            obj.ikdata.qpos[:]=configuration;obj.ikdata.qpos[:7]=q+(endpoint-q)*fraction
                            mujoco.mj_forward(model,obj.ikdata);r=obj.ikdata.site_xmat[site].reshape(3,3)
                            path.append({'fraction':float(fraction),'tcp':obj.ikdata.site_xpos[site].tolist(),
                                'orientation_error_rad':float(np.arccos(np.clip((np.trace(np.diag([1.,-1.,-1.])@r)-1)/2,-1,1)))})
                        result['joint_interpolated_samples']=path
                        result['maximum_joint_step_rad']=float(np.max(np.abs(endpoint-q)))
                    solutions.append(result)
                    if not result['success']:failure=result;break
                    q=np.array(result['q'])
                if failure:break
                position=target
            if failure is None:
                homeq=np.array(rest);home_samples=[]
                for fraction in np.linspace(0.,1.,21):
                    obj.ikdata.qpos[:]=configuration;obj.ikdata.qpos[:7]=q+(homeq-q)*fraction
                    mujoco.mj_forward(model,obj.ikdata)
                    home_samples.append({'fraction':float(fraction),'q':obj.ikdata.qpos[:7].tolist(),'tcp':obj.ikdata.site_xpos[site].tolist()})
                limits=model.jnt_range[:7]
                solutions.append({'phase':25,'grip':255,'q':homeq.tolist(),'success':True,
                    'maximum_joint_step_rad':float(np.max(np.abs(homeq-q))),
                    'joint_margin_rad':np.minimum(homeq-limits[:,0],limits[:,1]-homeq).tolist(),
                    'joint_interpolated_samples':home_samples,'interpretation':'Declared empty-jaw return to common HOME; no fixed orientation requirement'})
            rows.append({'mode':mode,'variant':variant,'method':method,'success':failure is None,'solutions':solutions,'failure':failure})
            save(out/'progress.json',{'completed':rows})
    save(out/'summary.json',{'manifest':plan,'routes':rows,'interpretation':'Kinematic convergence only; no contacts, collision avoidance or grip preservation established'})
    import importlib.util
    helper=HERE.parent/'Insert Pickup Diagnostics/insert_descent_replay.py'
    if not helper.is_file():raise RuntimeError('Required fixed insert FK diagnostic helper missing')
    spec=importlib.util.spec_from_file_location('insert_descent_replay',helper);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.run(out/'insert-descent')
    print(json.dumps([{'mode':r['mode'],'variant':r['variant'],'method':r['method'],'success':r['success'],'failure':r['failure']} for r in rows],indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
