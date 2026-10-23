"""Isolated, source-frozen causal diagnostics. Never writes to official roots."""
import copy
import hashlib
import json
from pathlib import Path
import time
import xml.etree.ElementTree as ET

import mujoco
import numpy as np
from scene import xml

HERE = Path(__file__).resolve().parent


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def model_for(case):
    tree = ET.fromstring(xml())
    if not case.get('full'):
        world = tree.find('worldbody')
        keep = [copy.deepcopy(world.find("geom[@name='floor']")), copy.deepcopy(world.find("body[@name='cup']"))]
        world.clear()
        world.extend(keep)
        tree.remove(tree.find('actuator'))
    option = tree.find('option')
    for k, v in case.get('option', {}).items():
        option.set(k, str(v))
    if case.get('disable_warmstart'):
        ET.SubElement(option, 'flag', warmstart='disable')
    if case.get('disable_nativeccd'):
        ET.SubElement(option, 'flag', nativeccd='disable')
    floor = tree.find(".//geom[@name='floor']")
    for k, v in case.get('floor', {}).items():
        floor.set(k, str(v))
    if case.get('plane'):
        floor.set('type', 'plane'); floor.set('pos', '6 5 0'); floor.set('size', '6 5 .1')
    cup = tree.find(".//geom[@name='cup_geom']")
    for k, v in case.get('cup', {}).items():
        cup.set(k, str(v))
    if case.get('multiccd') is not None:
        flag=option.find('flag')
        if flag is None: flag=ET.SubElement(option,'flag')
        flag.set('multiccd', 'enable' if case['multiccd'] else 'disable')
    text = ET.tostring(tree, encoding='unicode')
    return mujoco.MjModel.from_xml_string(text), text


def simulate(case, source, out):
    started = time.perf_counter()
    m, text = model_for(case)
    d = mujoco.MjData(m)
    b = m.body('cup').id; g = m.geom('cup_geom').id
    qa = int(m.joint('cup_free').qposadr[0]); va = int(m.joint('cup_free').dofadr[0])
    if case.get('full'):
        d.qpos[:] = source['qpos']; d.qvel[:] = source['qvel']
        for a in range(m.nu):
            joint = m.actuator_trnid[a, 0]
            d.ctrl[a] = d.qpos[m.jnt_qposadr[joint]]
    else:
        d.qpos[qa:qa+7] = source['cup_qpos']; d.qvel[va:va+6] = source['cup_qvel']
    if case.get('zero_velocity'):
        d.qvel[va:va+6] = 0
    if case.get('initial_qpos'):
        d.qpos[qa:qa+7]=case['initial_qpos']
    if case.get('initial_qvel'):
        d.qvel[va:va+6]=case['initial_qvel']
    if case.get('symmetric_inertia'):
        m.body_ipos[b] = 0
    mujoco.mj_forward(m, d)
    rows = []; count = {}; work = np.zeros(3); positive_contact_work = 0.; contact_parameters={}
    force_max = np.zeros(4); min_dist = 0.; next_sample = 0.
    vel = np.zeros(m.nv); mv = np.zeros(m.nv)
    for i in range(round(case.get('seconds', 120) / m.opt.timestep) + 1):
        mujoco.mj_forward(m, d)
        vel[:] = 0.; vel[va:va+6] = d.qvel[va:va+6]
        mujoco.mj_mulM(m, d, mv, vel)
        kinetic = .5 * np.dot(vel, mv)
        potential = -m.body_mass[b] * np.dot(m.opt.gravity, d.xipos[b])
        v = d.qvel[va:va+6].copy()
        constraint = d.qfrc_constraint[va:va+6]
        applied = d.qfrc_applied[va:va+6]
        passive = d.qfrc_passive[va:va+6]
        actuation = d.qfrc_actuator[va:va+6]
        power = float(np.dot(constraint, v))
        midpoint_power = float(np.dot(constraint, v + .5*m.opt.timestep*d.qacc[va:va+6]))
        force_max = np.maximum(force_max, [np.max(np.abs(applied)), np.max(np.abs(passive)), np.max(np.abs(actuation)), np.max(np.abs(d.xfrc_applied[b]))])
        contact_names = []
        normal_roll_torque = 0.
        axis = d.xmat[b].reshape(3,3)[:,2]
        for j in range(d.ncon):
            c = d.contact[j]
            if g not in (c.geom1, c.geom2):
                continue
            other = int(c.geom2 if c.geom1 == g else c.geom1)
            name = m.geom(other).name or str(other)
            count[name] = count.get(name, 0) + 1; contact_names.append(name)
            contact_parameters[name]={'dim':int(c.dim),'friction':c.friction.tolist()}
            min_dist = min(min_dist, float(c.dist))
            f = np.zeros(6); mujoco.mj_contactForce(m,d,j,f)
            normal_force = np.array(c.frame[:3]) * f[0] * (1 if c.geom2 == g else -1)
            normal_roll_torque += float(np.dot(np.cross(c.pos-d.xipos[b], normal_force),axis))
        if d.time >= next_sample - 1e-10:
            rows.append([float(d.time), *d.qpos[qa:qa+7], *v, float(kinetic), float(potential), power, midpoint_power, normal_roll_torque, *work, positive_contact_work])
            next_sample += .04
        if i == round(case.get('seconds',120) / m.opt.timestep):
            break
        work += np.array([power, midpoint_power, float(np.dot(-d.qfrc_bias[va:va+6], v))])*m.opt.timestep
        positive_contact_work += max(0., midpoint_power)*m.opt.timestep
        mujoco.mj_step(m,d)
        if not np.all(np.isfinite(d.qpos)):
            raise RuntimeError('Nonfinite state')
    a = np.array(rows)
    np.savez_compressed(out/(case['id']+'.npz'), samples=a)
    (out/(case['id']+'.xml')).write_text(text,encoding='utf-8')
    speed = np.linalg.norm(a[:,8:11],axis=1)
    late = a[:,0] >= max(0.,case.get('seconds',120)-30)
    result = dict(case=case, wall_seconds=time.perf_counter()-started, samples=len(a),
        columns=['time','x','y','z','qw','qx','qy','qz','vx','vy','vz','wx','wy','wz','kinetic_J','potential_J','contact_power_W','midpoint_contact_power_W','normal_roll_torque_Nm','contact_work_J','midpoint_contact_work_J','bias_work_J','positive_midpoint_contact_work_J'],
        mass_kg=float(m.body_mass[b]), inertia=m.body_inertia[b].tolist(), com_offset=m.body_ipos[b].tolist(),
        dof_armature=m.dof_armature[va:va+6].tolist(), contact_counts=count, contact_parameters=contact_parameters, force_max_applied_passive_actuator_xfrc=force_max.tolist(),
        min_contact_distance_m=min_dist, max_speed_m_s=float(speed.max()), final_speed_m_s=float(speed[-1]),
        path_length_m=float(np.linalg.norm(np.diff(a[:,1:3],axis=0),axis=1).sum()),
        xy_range_m=np.ptp(a[:,1:3],axis=0).tolist(), late_xy_range_m=np.ptp(a[late,1:3],axis=0).tolist(),
        kinetic_max_J=float(a[:,14].max()), energy_gain_max_J=float(np.max(a[:,14]+a[:,15]-a[0,14]-a[0,15])),
        final_energy_change_J=float(a[-1,14]+a[-1,15]-a[0,14]-a[0,15]),
        contact_work_J=work.tolist(), positive_midpoint_contact_work_J=positive_contact_work,
        final_position=a[-1,1:4].tolist(), warnings=[int(x.number) for x in d.warning])
    save(out/(case['id']+'.json'), result)
    print(json.dumps({k:result[k] for k in ['case','max_speed_m_s','final_speed_m_s','energy_gain_max_J','late_xy_range_m','wall_seconds']}),flush=True)
    return result


def main():
    manifest=json.loads((HERE/'manifest.json').read_bytes())
    for name, identity in manifest['files'].items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==identity['sha256'], name
    out=HERE/'output'; out.mkdir(exist_ok=False)
    source=dict(np.load(HERE/'initial.npz'))
    results=[simulate(case,source,out) for case in manifest['cases']]
    save(out/'result.json',dict(mujoco=mujoco.__version__,numpy=np.__version__,results=results,
        kind='engineering diagnostic; original state copied; no official steps or writes',
        reconstruction_limit='Original replay lacks warmstart, contact force telemetry and exact actuator state. Isolated tests initialize these afresh; full model holds recorded joint positions.'))


if __name__=='__main__': main()
