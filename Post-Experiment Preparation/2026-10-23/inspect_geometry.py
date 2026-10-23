"""Static forward kinematics and renders of original samples. Never mj_step."""
from inspect_history import APP, ROOTS, OUT, raw, read, save, inputs, sha
import importlib.util
import math
import numpy as np
import mujoco

spec = importlib.util.spec_from_file_location('historical_scene', APP/'scene.py')
scene = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scene)

def main():
    model = mujoco.MjModel.from_xml_string(scene.xml())
    data = mujoco.MjData(model)
    renderer = mujoco.Renderer(model, height=600, width=800)
    joints = {model.joint(i).name: int(model.jnt_qposadr[i]) for i in range(model.njnt)}
    bodies = ['base','arm_lift','arm_reach','arm_lateral','wrist','finger_left','finger_right']
    topology = [{'body': n, 'parent': model.body(int(model.body(n).parentid[0])).name,
                 'joint_types': model.jnt_type[int(model.body(n).jntadr[0]):int(model.body(n).jntadr[0])+int(model.body(n).jntnum[0])].tolist(),
                 'geometry': [{'id': int(i), 'name': model.geom(int(i)).name, 'position': model.geom_pos[i].tolist(),
                               'half_size': model.geom_size[i].tolist(), 'rgba': model.geom_rgba[i].tolist(),
                               'contype': int(model.geom_contype[i]), 'conaffinity': int(model.geom_conaffinity[i])}
                              for i in range(model.ngeom) if model.geom_bodyid[i] == model.body(n).id]}
                for n in bodies]
    results = {'mujoco': mujoco.__version__, 'numpy': np.__version__, 'method': 'MjModel.from_xml_string, original qpos/qvel, mj_forward only; no dynamics integration',
               'topology': topology, 'examples': []}
    for condition, root in ROOTS.items():
        run = read(root/'run.json')
        assert sha(raw(APP/'scene.py')) == run['source_identity']['apartment/scene.py']
        events = [__import__('json').loads(x) for x in raw(root/'events.jsonl').splitlines()]
        start = next(x['sim_time'] for x in events if x['kind']=='session_started' and x['payload']['session']==2)
        # Choose an actually recorded extended pose during session 1; selection is illustrative, not a performance statistic.
        trajectories = [e for e in events if e['kind']=='command_requested' and e['payload']['session']==1
                        and e['payload']['request']['kind']=='trajectory']
        assert trajectories
        request = trajectories[-1]
        terminal = next(e for e in events if e['kind']=='command_terminal' and e['payload']['request_id']==request['payload']['request']['request_id'])
        index = read(root/'replay/index.json')
        best = None
        for row in index:
            if row['last'] < request['sim_time'] or row['first'] > terminal['sim_time']: continue
            p = root/'replay'/row['file']; assert sha(raw(p)) == row['sha256']
            with np.load(p) as a:
                candidates = np.where((a['t']>=request['sim_time']) & (a['t']<=terminal['sim_time']))[0]
                for k in candidates:
                    reach = float(a['qpos'][k, joints['reach']])
                    if best is None or reach > best['reach']:
                        best = {'file':str(p), 'sha256': row['sha256'], 'sample':int(k), 't':float(a['t'][k]),
                                'wall_ns':int(a['wall_ns'][k]), 'qpos':a['qpos'][k].copy(), 'qvel':a['qvel'][k].copy(), 'reach':reach}
        data.qpos[:] = best['qpos']; data.qvel[:] = best['qvel']; data.time = best['t']
        mujoco.mj_forward(model, data)
        q = {n: float(data.qpos[joints[n]]) for n in ['base_yaw','lift','reach','lateral','wrist_pitch','finger_left','finger_right']}
        yaw = q['base_yaw']; pitch=q['wrist_pitch']
        R = np.array([[math.cos(yaw),-math.sin(yaw),0],[math.sin(yaw),math.cos(yaw),0],[0,0,1]])
        W = R @ np.array([[math.cos(pitch),0,math.sin(pitch)],[0,1,0],[-math.sin(pitch),0,math.cos(pitch)]])
        base = data.body('base').xpos.copy()
        lift = base+R@np.array([.08,0,.22+q['lift']])
        reach=lift+R@np.array([q['reach'],0,0]); lateral=reach+R@np.array([0,q['lateral'],0])
        predicted={'arm_lift':lift,'arm_reach':reach,'arm_lateral':lateral,'wrist':lateral,
                   'finger_left':lateral+W@np.array([0,.009+q['finger_left'],0]),
                   'finger_right':lateral+W@np.array([0,-.009-q['finger_right'],0])}
        residuals={n:float(np.linalg.norm(data.body(n).xpos-p)) for n,p in predicted.items()}
        assert max(residuals.values()) < 1e-10
        # Exact signed separation along parallel axes for the carriage and reach boxes.
        # Lift box is centered at lift with half sizes (.12,.09,.06).
        # Reach box is centered at lift+(reach-.12,0,.15), half sizes (.15,.05,.04).
        dx=max(0.,q['reach']-.12-.15-.12); dz=.15-.04-.06
        geom_gap=math.hypot(dx,dz)
        geoms=[dict(type=int(model.geom_type[i]),size=model.geom_size[i].tolist(),color=model.geom_rgba[i].tolist(),
                    position=data.geom_xpos[i].tolist(),rotation=data.geom_xmat[i].tolist(),group=int(model.geom_group[i]))
               for i in range(model.ngeom)]
        frame={'sim_time':data.time, 'requested_time':data.time, 'sample_age':0, 'geoms':geoms, 'robot':base.tolist(),
               'range':[data.time,data.time], 'provenance':{'file':best['file'],'sha256':best['sha256'],'sample':best['sample'],
                  'kind':'static reconstruction of original sampled physics; no dynamics step'}}
        save(condition+'-diagnostic-frame.json',frame)
        cam=mujoco.MjvCamera();cam.type=mujoco.mjtCamera.mjCAMERA_FREE
        cam.lookat[:]=base+R@np.array([.25,0,.65]);cam.distance=2.7;cam.azimuth=math.degrees(yaw)+115;cam.elevation=-15
        option = mujoco.MjvOption()
        option.geomgroup[1] = 0  # Hide apartment walls only, to reveal the same original robot geometry.
        renderer.update_scene(data,camera=cam,scene_option=option)
        # Use the historical PNG encoder without importing world or constructing a World.
        import struct,zlib
        rgb=renderer.render();h,w,_=rgb.shape
        def chunk(kind,b):return struct.pack('>I',len(b))+kind+b+struct.pack('>I',zlib.crc32(kind+b)&0xffffffff)
        png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(b'\0'+r.tobytes() for r in rgb),3))+chunk(b'IEND',b'')
        (OUT/(condition+'-native-reconstruction.png')).write_bytes(png)
        results['examples'].append({'condition':condition,'session':1,'event_request':request['sequence'],
            'request_id':request['payload']['request']['request_id'], 'request_sim_time':request['sim_time'],
            'terminal_sim_time':terminal['sim_time'], 'sample':{k:v for k,v in best.items() if k not in ['qpos','qvel']},
            'joints':q, 'body_positions':{n:data.body(n).xpos.tolist() for n in bodies},
            'analytical_chain_residual_m':residuals,'lift_reach_geometry_gap_m':geom_gap,
            'gap_components_m':{'x':dx,'z':dz},'qpos':best['qpos'].tolist(),'qvel':best['qvel'].tolist(),
            'native_image':condition+'-native-reconstruction.png', 'native_render_wall_group_hidden':True,
            'frame':condition+'-diagnostic-frame.json'})
    renderer.close()
    save('geometry-inspection.json',results)
    save('geometry-inputs.json',inputs)
    print('Two original extended poses reconstructed; analytical chain checks pass. No mj_step called.')

if __name__=='__main__':main()
