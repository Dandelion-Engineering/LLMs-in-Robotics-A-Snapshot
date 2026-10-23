"""Supplement the retained cup diagnosis using original states; never advances physics."""
from datetime import datetime, timezone
import argparse
import json
import mujoco
import numpy as np
from launch_maps import PAIR, OP
from common import read, save, sha
from scene import xml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--all-samples', action='store_true')
    args = parser.parse_args()
    out = OP / 'cup-diagnosis-001'
    target = out / ('all-sample-contact-and-energy.json' if args.all_samples else 'contact-and-energy.json')
    assert not target.exists()
    source = read(out / 'result.json')
    model = mujoco.MjModel.from_xml_string(xml())
    data = mujoco.MjData(model)
    cup = model.geom('cup_geom').id
    body = model.body('cup').id
    floor = model.geom('floor').id
    qadr = model.joint('cup_free').qposadr[0]
    dadr = model.joint('cup_free').dofadr[0]
    axis = np.array(source['motion']['travel_axis'])
    perpendicular = np.array([-axis[1], axis[0]])
    rows = []
    next_sample = source['motion']['first_sim_time']
    for item in source['sources']:
        path = PAIR / 'maps/replay' / item['file']
        assert sha(path) == item['sha256']
        with np.load(path) as values:
            for t, q, v in zip(values['t'], values['qpos'], values['qvel']):
                if t < next_sample or t > source['motion']['last_sim_time']:
                    continue
                next_sample = t if args.all_samples else t + .49
                data.qpos[:] = q
                data.qvel[:] = v
                data.time = t
                mujoco.mj_forward(model, data)
                velocity = np.zeros(6)
                mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_BODY, body, velocity, 1)
                rotation = data.xmat[body].reshape(3, 3)
                com_velocity = velocity[3:] + np.cross(velocity[:3], model.body_ipos[body])
                kinetic = .5 * model.body_mass[body] * np.dot(com_velocity, com_velocity)
                kinetic += .5 * np.dot(model.body_inertia[body], velocity[:3] ** 2)
                potential = -model.body_mass[body] * np.dot(model.opt.gravity, data.xipos[body])
                contacts = []
                for n in range(data.ncon):
                    c = data.contact[n]
                    if cup not in (c.geom1, c.geom2):
                        continue
                    force = np.zeros(6)
                    mujoco.mj_contactForce(model, data, n, force)
                    contacts.append(dict(other=model.geom(int(c.geom2 if c.geom1 == cup else c.geom1)).name,
                        dimension=int(c.dim), normal=c.frame[:3].tolist(),
                        position_relative_to_cup=(c.pos-data.xpos[body]).tolist(),
                        penetration_m=float(c.dist), reconstructed_force=force.tolist()))
                rows.append(dict(sim_time=float(t), position=q[qadr:qadr+3].tolist(),
                    velocity=v[dadr:dadr+6].tolist(), cup_axis=rotation[:, 2].tolist(),
                    com_height=float(data.xipos[body, 2]), kinetic_j=float(kinetic), potential_j=float(potential),
                    reconstructed_acceleration=data.qacc[dadr:dadr+6].tolist(),
                    reconstructed_constraint_force=data.qfrc_constraint[dadr:dadr+6].tolist(), contacts=contacts))
    sample = np.load(out / 'cup-samples.npz')
    kinetic = np.array([r['kinetic_j'] for r in rows])
    potential = np.array([r['potential_j'] for r in rows])
    normal_torque, support_offset = [], []
    contact_counts = {}
    for row in rows:
        torque, normal_force = 0., 0.
        for contact in row['contacts']:
            contact_counts[contact['other']] = contact_counts.get(contact['other'], 0) + 1
            force = -np.array(contact['normal']) * contact['reconstructed_force'][0]
            torque += float(np.cross(contact['position_relative_to_cup'], force) @ row['cup_axis'])
            normal_force += contact['reconstructed_force'][0]
        normal_torque.append(torque)
        support_offset.append(torque / normal_force if normal_force else 0.)
    extremes = [rows[int(np.argmin(kinetic))], rows[int(np.argmax(kinetic))]]
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), new_simulation_steps=0,
        method='mj_forward on independent data at original recorded positions/velocities. Reconstructed forces omit original warmstart/actuator history; kinematics and energies are derived directly from recordings.',
        mujoco_version=mujoco.__version__, gravity=model.opt.gravity.tolist(), density=float(model.opt.density), viscosity=float(model.opt.viscosity),
        body_com_offset=model.body_ipos[body].tolist(), floor_quaternion=model.geom_quat[floor].tolist(),
        sample_count=len(rows), kinetic_min_j=float(kinetic.min()), kinetic_max_j=float(kinetic.max()),
        potential_range_j=float(np.ptp(potential)), total_energy_range_j=float(np.ptp(kinetic+potential)),
        contacted_geometries=contact_counts,
        normal_force_roll_torque_Nm_range=[min(normal_torque), max(normal_torque)],
        effective_support_offset_m_range=[min(support_offset), max(support_offset)],
        perpendicular_motion_range_m=float(np.ptp(sample['position'][:, :2] @ perpendicular)),
        extreme_kinetic_samples=extremes, samples=rows)
    save(target, result)
    print(json.dumps({k:v for k,v in result.items() if k != 'samples'}))


if __name__ == '__main__':
    main()
