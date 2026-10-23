"""Queued-driver-only static reconstruction of nineteen retained insert samples.

No mj_step, rendering, IK, control application, object relocation in an episode,
candidate observation or physical success assertion. Alternate q assignments
are explicitly counterfactual geometry in independent scratch MjData only.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
DRIVER = PROJECT / 'Batch 01/Recovery Diagnosis/kinematic_replay.py'
INPUT = HERE / 'selected-replay-input.json'
INPUT_SHA256 = 'e8f471ef33a020b6b85339e41b4bb81a785c9c46a7ecd11ff2023ea21c041861'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def run(output_dir):
    # Verify the exact parent driver through the existing queue ownership path
    # before importing MuJoCo or performing any numerical work.
    sys.path.insert(0, str(PROJECT / 'Runtime'))
    from release_runner import queued_job
    job = queued_job(expected_script=str(DRIVER))
    import numpy as np
    import mujoco

    if digest(INPUT) != INPUT_SHA256:
        raise RuntimeError('Retained insert diagnostic input changed')
    inputs = json.loads(INPUT.read_text(encoding='utf-8'))
    xml = Path(inputs['source_world_xml'])
    if digest(xml) != inputs['source_world_xml_sha256']:
        raise RuntimeError('Retained insert scene bytes changed')
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    source_sha = digest(__file__)
    manifest = {'schema_version': 'insert-static-fk-replay-1', 'queue_job_id': job['id'],
                'started_at': datetime.now(timezone.utc).isoformat(),
                'module_sha256': source_sha, 'driver_sha256': digest(DRIVER),
                'input_sha256': INPUT_SHA256, 'scene_xml_sha256': digest(xml),
                'mujoco_version': mujoco.__version__, 'numpy_version': np.__version__,
                'sample_count': len(inputs['samples']), 'mj_step_calls': 0,
                'scope': 'retained and counterfactual static geometry; never a new physical trial',
                'contact_warning': 'contact geometry is recomputed by mj_forward; no reconstructed contact force is asserted as measured',
                'timestamp_warning': 'retained qpos and site_xpos can straddle one mj_step update; FK residual is reported, not silently corrected'}
    save(output / 'manifest.json', manifest)
    model = mujoco.MjModel.from_xml_path(str(xml))
    tcp = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, 'tcp')
    if tcp < 0:
        raise RuntimeError('Retained model lacks TCP site')
    target_rotation = np.diag([1., -1., -1.])
    body_names = {i: mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i) or 'body_' + str(i) for i in range(model.nbody)}
    selected_bodies = {i for i, name in body_names.items() if name in ('hand', 'left_finger', 'right_finger')}
    insert_bodies = {i for i, name in body_names.items() if name in ('insert_A', 'insert_B')}
    if len(selected_bodies) != 3 or len(insert_bodies) != 2:
        raise RuntimeError('Retained hand/finger/insert body identities differ')
    selected_geoms = [i for i in range(model.ngeom) if int(model.geom_bodyid[i]) in selected_bodies
                      and (int(model.geom_contype[i]) or int(model.geom_conaffinity[i]))]

    def geom_name(identity):
        return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, identity) or 'geom_' + str(identity)

    def bounds(data, identity):
        rotation = data.geom_xmat[identity].reshape(3, 3)
        center = data.geom_xpos[identity]
        kind = int(model.geom_type[identity])
        if kind == int(mujoco.mjtGeom.mjGEOM_BOX):
            extent = np.abs(rotation) @ model.geom_size[identity]
            return {'min': (center - extent).tolist(), 'max': (center + extent).tolist(), 'method': 'oriented collision box'}
        if kind == int(mujoco.mjtGeom.mjGEOM_MESH):
            mesh = int(model.geom_dataid[identity])
            start, length = int(model.mesh_vertadr[mesh]), int(model.mesh_vertnum[mesh])
            vertices = model.mesh_vert[start:start + length]
            world = vertices @ rotation.T + center
            return {'min': world.min(axis=0).tolist(), 'max': world.max(axis=0).tolist(),
                    'method': 'compiled collision mesh vertex hull bounds'}
        return {'min': None, 'max': None, 'method': 'unsupported geom type ' + str(kind)}

    def inspect(sample, variant):
        row = sample['record']; world = row['worlds'][0]
        data = mujoco.MjData(model)
        data.qpos[:] = world['qpos']; data.qvel[:] = world['qvel']; data.ctrl[:] = world['ctrl']
        data.time = row['sim_time_s']
        if variant != 'retained_q':
            data.qpos[:7] = world['ctrl'][:7]
        if variant == 'native_target_open_fingers':
            data.qpos[7:9] = [.04, .04]
        mujoco.mj_forward(model, data)
        actual_rotation = data.site_xmat[tcp].reshape(3, 3)
        cosine = np.clip((np.trace(target_rotation.T @ actual_rotation) - 1.) / 2., -1., 1.)
        angle = float(np.arccos(cosine))
        surrogate = .5 * sum((np.cross(actual_rotation[:, i], target_rotation[:, i]) for i in range(3)), start=np.zeros(3))
        geoms = []
        for identity in selected_geoms:
            geoms.append({'geom_id': identity, 'geom': geom_name(identity),
                          'body': body_names[int(model.geom_bodyid[identity])],
                          'position_world_m': data.geom_xpos[identity].tolist(), 'bounds': bounds(data, identity)})
        contacts = []
        for i in range(data.ncon):
            contact = data.contact[i]
            g1, g2 = int(contact.geom1), int(contact.geom2)
            b1, b2 = int(model.geom_bodyid[g1]), int(model.geom_bodyid[g2])
            if not ({b1, b2} & (selected_bodies | insert_bodies)):
                continue
            contacts.append({'geom1': geom_name(g1), 'geom2': geom_name(g2),
                             'body1': body_names[b1], 'body2': body_names[b2],
                             'distance_m': float(contact.dist), 'position_world_m': contact.pos.tolist(),
                             'constraint_active_after_forward': bool(int(contact.efc_address) >= 0)})
        lowest = [g['bounds']['min'][2] for g in geoms if g['bounds']['min'] is not None]
        return {'target_sample_time_s': sample['target_sim_time_s'], 'source_line': sample['source_line'],
                'source_line_sha256': sample['source_line_sha256'], 'sim_time_s': row['sim_time_s'],
                'phase': world['segment_phase'], 'variant': variant,
                'retained_gripper_ctrl': float(world['ctrl'][7]), 'evaluated_jaw_width_m': float(sum(data.qpos[7:9])),
                'joint_position_rad': data.qpos[:7].tolist(), 'evaluated_tcp_m': data.site_xpos[tcp].tolist(),
                'retained_tcp_m': world['tcp'],
                'fk_minus_retained_tcp_m': (data.site_xpos[tcp] - np.array(world['tcp'])).tolist(),
                'tcp_rotation_world': actual_rotation.tolist(), 'true_target_angle_rad': angle,
                'cross_product_residual_norm': float(np.linalg.norm(surrogate)),
                'orientation_stop_would_accept': bool(np.linalg.norm(surrogate) < .01),
                'minimum_hand_finger_collision_z_m': min(lowest) if lowest else None,
                'hand_finger_collision_geoms': geoms, 'reconstructed_contacts': contacts,
                'physical_trial_or_force_evidence': False}

    rows = []
    with (output / 'reconstructed-geometry.jsonl').open('x', encoding='utf-8') as stream:
        for sample in inputs['samples']:
            variants = ['retained_q', 'native_target_actual_fingers']
            if sample['record']['worlds'][0]['ctrl'][7] == 255:
                variants.append('native_target_open_fingers')
            for variant in variants:
                result = inspect(sample, variant)
                stream.write(json.dumps(result, allow_nan=False, separators=(',', ':')) + '\n'); stream.flush()
                rows.append({key: result[key] for key in ('sim_time_s', 'phase', 'variant', 'retained_gripper_ctrl',
                    'evaluated_jaw_width_m', 'evaluated_tcp_m', 'true_target_angle_rad', 'cross_product_residual_norm',
                    'orientation_stop_would_accept', 'minimum_hand_finger_collision_z_m')})
    summary = {'schema_version': 'insert-static-fk-replay-1', 'rows': rows,
               'module_source_unchanged': digest(__file__) == source_sha,
               'input_unchanged': digest(INPUT) == INPUT_SHA256, 'geometry_sha256': digest(output / 'reconstructed-geometry.jsonl'),
               'scope': 'static reconstruction only; no dynamics replay, physical success, grasp or recovery qualification'}
    save(output / 'summary.json', summary)
    return summary


if __name__ == '__main__':
    raise SystemExit('No standalone CLI. This module runs only inside the verified queued recovery diagnostic driver.')
