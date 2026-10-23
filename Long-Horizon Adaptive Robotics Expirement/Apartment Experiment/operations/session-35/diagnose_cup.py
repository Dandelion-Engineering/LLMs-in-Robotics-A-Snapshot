"""Read-only cup motion diagnosis from immutable replay samples; never calls mj_step."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import urllib.request

import mujoco
import numpy as np
from launch_maps import PAIR, OP, FROZEN_CODE
from common import canonical, read, save, sha
from scene import xml


def main():
    root = PAIR / 'maps'
    out = OP / 'cup-diagnosis-001'
    out.mkdir(exist_ok=False)
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), read_only=True,
                  new_simulation_steps=0, scope='Cup motion, recorded contacts and physical commands; no behavior intervention or condition comparison')
    assert read(root / 'run.json')['source_identity']['apartment/scene.py'] == sha(FROZEN_CODE / 'scene.py')
    model = mujoco.MjModel.from_xml_string(xml())
    data = mujoco.MjData(model)
    cup = model.geom('cup_geom').id
    body = model.body('cup').id
    qadr = model.joint('cup_free').qposadr[0]
    dadr = model.joint('cup_free').dofadr[0]
    result['compiled_cup'] = dict(contact_dimension=int(model.geom_condim[cup]), friction=model.geom_friction[cup].tolist(),
                                 joint_damping=model.dof_damping[dadr:dadr+6].tolist(), armature=model.dof_armature[dadr:dadr+6].tolist(),
                                 mass=float(model.body_mass[body]), inertia=model.body_inertia[body].tolist(), radius=float(model.geom_size[cup, 0]),
                                 cylinder_half_length=float(model.geom_size[cup, 1]), body_id=int(body), geom_id=int(cup))
    result['floor'] = dict(contact_dimension=int(model.geom_condim[model.geom('floor').id]), friction=model.geom_friction[model.geom('floor').id].tolist())
    url = read(root / 'viewer.json')['url']
    live = []
    for i in range(4):
        with urllib.request.urlopen(url + '/frame', timeout=8) as response:
            frame = json.load(response)
        live.append(dict(sim_time=frame['sim_time'], cup=frame['geoms'][cup], session=frame['session'], phase=frame['phase']))
        if i < 3:
            time.sleep(2)
    result['live_frames'] = live
    index = read(root / 'replay/index.json')
    save(out / 'replay-index-snapshot.json', index)
    finish = index[-1]['last']
    begin = finish - 180
    selected = [row for row in index if row['last'] >= begin and row['first'] <= finish]
    times, poses, velocities = [], [], []
    for row in selected:
        path = root / 'replay' / row['file']
        assert sha(path) == row['sha256']
        with np.load(path) as values:
            use = (values['t'] >= begin) & (values['t'] <= finish)
            times.append(values['t'][use]); poses.append(values['qpos'][use]); velocities.append(values['qvel'][use])
    times = np.concatenate(times); poses = np.concatenate(poses); velocities = np.concatenate(velocities)
    assert np.all(np.diff(times) > 0) and np.all(np.isfinite(poses)) and np.all(np.isfinite(velocities))
    positions = poses[:, qadr:qadr+3]
    speed = np.linalg.norm(velocities[:, dadr:dadr+3], axis=1)
    omega = np.linalg.norm(velocities[:, dadr+3:dadr+6], axis=1)
    centered = positions[:, :2] - positions[:, :2].mean(axis=0)
    _, _, vectors = np.linalg.svd(centered, full_matrices=False)
    axis = vectors[0]
    projection = centered @ axis
    axis_velocity = velocities[:, dadr:dadr+2] @ axis
    crossings = np.flatnonzero(axis_velocity[1:] * axis_velocity[:-1] < 0) + 1
    reversals = []
    for k in crossings:
        if not reversals or times[k] - reversals[-1]['sim_time'] > .5:
            reversals.append(dict(sim_time=float(times[k]), position=positions[k].tolist(), speed=float(speed[k])))
    contacts = []
    sample_indices = np.unique(np.searchsorted(times, np.arange(times[0], times[-1], .5)))
    for k in sample_indices:
        data.qpos[:] = poses[k]; data.qvel[:] = velocities[k]; data.time = times[k]
        mujoco.mj_forward(model, data)
        items = []
        for j in range(data.ncon):
            contact = data.contact[j]
            if cup not in (contact.geom1, contact.geom2):
                continue
            other = int(contact.geom2 if contact.geom1 == cup else contact.geom1)
            items.append(dict(geom=model.geom(other).name, body=model.body(int(model.geom_bodyid[other])).name,
                              dimension=int(contact.dim), distance=float(contact.dist), position=contact.pos.tolist()))
        contacts.append(dict(sim_time=float(times[k]), contacts=items))
    save(out / 'sampled-contacts.json', contacts)
    result['motion'] = dict(first_sim_time=float(times[0]), last_sim_time=float(times[-1]), samples=len(times),
                          sample_dt_median=float(np.median(np.diff(times))), position_min=positions.min(axis=0).tolist(),
                          position_max=positions.max(axis=0).tolist(), first_position=positions[0].tolist(), last_position=positions[-1].tolist(),
                          path_length_m=float(np.linalg.norm(np.diff(positions[:, :2], axis=0), axis=1).sum()),
                          speed_min=float(speed.min()), speed_median=float(np.median(speed)), speed_max=float(speed.max()),
                          speed_first=float(speed[0]), speed_last=float(speed[-1]), angular_speed_median=float(np.median(omega)),
                          travel_axis=axis.tolist(), reversals=reversals,
                          contacted_geometries=dict(Counter(x['geom'] for row in contacts for x in row['contacts'])),
                          contact_samples=len(contacts), contacts_reconstructed_from_original_states=True)
    raw = (root / 'events.jsonl').read_bytes()
    raw = raw[:raw.rfind(b'\n')+1]
    events = [json.loads(line) for line in raw.splitlines()]
    previous = '0'*64
    for i, row in enumerate(events, 1):
        value = {k:v for k,v in row.items() if k != 'sha256'}
        assert row['sequence'] == i and row['previous'] == previous and hashlib.sha256(canonical(value)).hexdigest() == row['sha256']
        previous = row['sha256']
    result['event_prefix'] = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), records=len(events))
    activity = [row for row in events if begin <= row['sim_time'] <= finish and row['kind'] in ('command_requested','command_admitted','command_terminal','session_started','session_closed','task_success')]
    save(out / 'physical-activity.json', activity)
    result['recent_commands'] = activity
    result['sources'] = selected
    np.savez_compressed(out / 'cup-samples.npz', t=times, position=positions, quaternion=poses[:,qadr+3:qadr+7], velocity=velocities[:,dadr:dadr+6])
    # Viewer matches are evaluated only where an immutable sample is already available.
    result['viewer_replay_matches'] = []
    for frame in live:
        if frame['sim_time'] > times[-1]:
            continue
        k = max(0, np.searchsorted(times, frame['sim_time'], side='right')-1)
        result['viewer_replay_matches'].append(dict(sim_time=frame['sim_time'], sample_age_s=float(frame['sim_time']-times[k]),
            position_difference_m=float(np.linalg.norm(np.array(frame['cup']['position'])-positions[k]))))
    save(out / 'result.json', result)
    print(canonical(dict(evidence=str(out/'result.json'), compiled_cup=result['compiled_cup'], floor=result['floor'],
                         motion=result['motion'], viewer_replay_matches=result['viewer_replay_matches'],
                         command_events=len(activity), command_kinds=dict(Counter(r['payload'].get('kind','unknown') for r in activity)))).decode())


if __name__ == '__main__':
    main()
