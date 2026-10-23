"""Two declared static A-insert paths, invoked only by queued diagnostic 002.

All object poses remain at the retained precontact state. No mj_step, rendering,
forces, hypothetical attachment, or physical pickup/carry success is computed.
"""
from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import zipfile

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
DRIVER = PROJECT / 'Batch 01/Recovery Diagnosis/kinematic_replay_002.py'
INPUT = HERE / 'selected-replay-input.json'
INPUT_SHA256 = 'e8f471ef33a020b6b85339e41b4bb81a785c9c46a7ecd11ff2023ea21c041861'
CALIBRATION = PROJECT / 'Evidence/calibration/physical-calibration-002'
SENSOR_EVENT_ID = 874
SENSOR_PAYLOAD_SHA256 = '5d7608f507fcae1c8ff134b8b1740809fb94bf5eb98aff7bbc9572923f7517fd'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def run(output_dir):
    sys.path.insert(0, str(PROJECT / 'Runtime'))
    from release_runner import queued_job
    job = queued_job(expected_script=str(DRIVER))
    import mujoco
    import numpy as np

    if digest(INPUT) != INPUT_SHA256:
        raise RuntimeError('Retained insert diagnostic input changed')
    inputs = json.loads(INPUT.read_text(encoding='utf-8'))
    xml = Path(inputs['source_world_xml'])
    if digest(xml) != inputs['source_world_xml_sha256']:
        raise RuntimeError('Retained insert scene bytes changed')
    bundle = CALIBRATION / 'source-bundle.zip'
    with zipfile.ZipFile(bundle) as archive:
        source = archive.read('Runtime/cell.py')
    probe_manifest = json.loads(Path(inputs['source_before_manifest']).read_text(encoding='utf-8'))
    original_cell_hash = next(v for k, v in probe_manifest['source_hashes'].items()
                              if k.replace('\\', '/').endswith('/Runtime/cell.py'))
    if hashlib.sha256(source).hexdigest() != original_cell_hash:
        raise RuntimeError('Archived Cell source differs from physical probe manifest')
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Cell')
    ik_node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'ik')
    namespace = {'np': np, 'mujoco': mujoco}
    exec(compile(ast.Module(body=[ik_node], type_ignores=[]), 'archived-cal002-Cell.ik', 'exec'), namespace)
    old_ik = namespace['ik']

    events_path = CALIBRATION / 'insert-exchange/events.jsonl'
    with events_path.open(encoding='utf-8') as stream:
        sensor = next(json.loads(line) for line in stream if json.loads(line)['event_id'] == SENSOR_EVENT_ID)
    if sensor['payload_sha256'] != SENSOR_PAYLOAD_SHA256:
        raise RuntimeError('Declared source observation event changed')
    observed = next(d for d in sensor['payload']['detections'] if d['id'] == 'insert_A')
    grasp = np.array(observed['pos'], dtype=float)
    grasp[2] = max(grasp[2], .008) + .004  # Exact archived half height and TCP offset.
    raised = np.r_[grasp[:2], max(grasp[2], .008 + .003 + .004) + .16]

    # Three fixed retained commands identify the original descent and lift.
    # The last lift sample is 10 ms before the first retained phase-5 row;
    # its finite endpoint sampling is disclosed rather than called exact IK.
    wanted = {46.752: None, 50.502: None, 53.622: None, 51.002: None}
    trajectory = Path(inputs['source_trajectory'])
    with trajectory.open('rb') as stream:
        for line_number, raw in enumerate(stream, 1):
            row = json.loads(raw)
            target = round(row['sim_time_s'], 3)
            if target in wanted:
                wanted[target] = {'source_line': line_number,
                                  'source_line_sha256': hashlib.sha256(raw).hexdigest(), 'record': row}
    if any(value is None for value in wanted.values()):
        raise RuntimeError('A declared retained trajectory row is missing')
    selected = {round(s['record']['sim_time_s'], 3): s for s in inputs['samples']}
    for target in (46.752, 50.502, 51.002):
        if wanted[target]['record'] != selected[target]['record']:
            raise RuntimeError('Retained selected input differs from original trajectory')
    pre = wanted[46.752]['record']['worlds'][0]
    closed = wanted[51.002]['record']['worlds'][0]
    qstart = np.array(pre['ctrl'][:7])
    original_grasp_q = np.array(wanted[50.502]['record']['worlds'][0]['ctrl'][:7])
    original_lift_q = np.array(wanted[53.622]['record']['worlds'][0]['ctrl'][:7])
    configuration = np.array(pre['qpos'])
    model = mujoco.MjModel.from_xml_path(str(xml))
    data = mujoco.MjData(model)
    data.qpos[:] = configuration
    tcp = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, 'tcp')
    if tcp < 0:
        raise RuntimeError('Retained model lacks TCP site')
    obj = SimpleNamespace(model=model, data=data, ikdata=mujoco.MjData(model), tcp=tcp,
                          jacp=np.zeros((3, model.nv)), jacr=np.zeros((3, model.nv)))
    target_rotation = np.diag([1., -1., -1.])
    limits = model.jnt_range[:7]
    body_names = {i: mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i) or 'body_' + str(i)
                  for i in range(model.nbody)}
    hand_bodies = {i for i, name in body_names.items() if name in ('hand', 'left_finger', 'right_finger')}
    collidable = [i for i in range(model.ngeom) if int(model.geom_contype[i]) or int(model.geom_conaffinity[i])]
    hand_geoms = [i for i in collidable if int(model.geom_bodyid[i]) in hand_bodies]
    # Only non-robot objects/table are distance targets; self-collision and
    # continuous-path collision freedom are outside this bounded comparison.
    targets = [i for i in collidable if body_names[int(model.geom_bodyid[i])].startswith(('insert_', 'part_'))
               or body_names[int(model.geom_bodyid[i])] in ('A1', 'A3', 'B2')
               or (mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, i) or '') == 'table']
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    source_sha = digest(__file__)
    manifest = {'schema_version': 'insert-static-descent-comparison-1', 'queue_job_id': job['id'],
        'started_at': datetime.now(timezone.utc).isoformat(), 'module_sha256': source_sha,
        'driver_sha256': digest(DRIVER), 'input_sha256': INPUT_SHA256,
        'scene_xml_sha256': digest(xml), 'source_bundle_sha256': digest(bundle),
        'retained_cell_sha256': original_cell_hash, 'events_sha256': digest(events_path),
        'trajectory_sha256': digest(trajectory), 'sensor_event_id': SENSOR_EVENT_ID,
        'sensor_payload_sha256': SENSOR_PAYLOAD_SHA256, 'source_observation': observed,
        'grasp_target_m': grasp.tolist(), 'raised_target_m': raised.tolist(),
        'retained_inputs': wanted, 'variants': ['retained_endpoint_joint_interpolation', 'cartesian_continuation_10mm'],
        'phase_grip_sequence': [[2, 255], [3, 0], [4, 0]], 'maximum_cartesian_spacing_m': .01,
        'joint_interpolation_samples_per_segment': 11, 'mujoco_version': mujoco.__version__,
        'numpy_version': np.__version__, 'mj_step_calls': 0,
        'scope': 'static ideal-target kinematics only; unchanged endpoint height, orientation and original IK',
        'sampling_limit': 'Retained phase-1/lift controls are sampled commands near their endpoints, not reconstructed exact original IK endpoints.',
        'finger_and_object_limit': 'Open fingers are .04 m each. Closure interpolates to retained 51.002 s finger positions. Objects remain frozen at 46.752 s in both variants. Closed-jaw overlap is geometry only, not grasp/contact-force/carry evidence.',
        'distance_limit': 'Distances are capped at .25 m; a capped value is a lower bound. Eleven samples expose sampled contacts but cannot prove continuous collision freedom.'}
    save(output / 'manifest.json', manifest)

    def geom_name(i):
        return mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, i) or 'geom_' + str(i)

    def inspect(q, fingers):
        data.qpos[:] = configuration
        data.qpos[:7] = q
        data.qpos[7:9] = fingers
        mujoco.mj_forward(model, data)
        rot = data.site_xmat[tcp].reshape(3, 3)
        angle = float(np.arccos(np.clip((np.trace(target_rotation.T @ rot) - 1.) / 2., -1., 1.)))
        contacts = []
        for c in data.contact[:data.ncon]:
            if int(c.geom1) in hand_geoms or int(c.geom2) in hand_geoms:
                contacts.append({'geom1': geom_name(int(c.geom1)), 'geom2': geom_name(int(c.geom2)),
                                 'distance_m': float(c.dist), 'position_m': c.pos.tolist()})
        clearances = {}
        for target in targets:
            body = body_names[int(model.geom_bodyid[target])]
            key = 'table' if geom_name(target) == 'table' else body
            for finger in hand_geoms:
                distance = float(mujoco.mj_geomDistance(model, data, finger, target, .25, None))
                if key not in clearances or distance < clearances[key]['distance_m']:
                    clearances[key] = {'distance_m': distance, 'at_distance_cap': distance >= .25,
                                       'hand_geom': geom_name(finger), 'target_geom': geom_name(target)}
        return {'q': np.asarray(q).tolist(), 'finger_q_m': np.asarray(fingers).tolist(),
                'joint_margin_rad': np.minimum(q - limits[:, 0], limits[:, 1] - q).tolist(),
                'tcp_m': data.site_xpos[tcp].tolist(), 'true_orientation_error_rad': angle,
                'lateral_error_from_source_m': float(np.linalg.norm(data.site_xpos[tcp, :2] - grasp[:2])),
                'reconstructed_contacts': contacts, 'sampled_clearance_by_object': clearances}

    def solve(target, seed):
        error = None
        try:
            q = old_ik(obj, target, seed, configuration)
        except ValueError as exc:
            q = obj.ikdata.qpos[:7].copy()
            error = str(exc)
        state = inspect(q, [.04, .04])
        residual = np.asarray(target) - np.array(state['tcp_m'])
        return q, {'target_m': np.asarray(target).tolist(), 'q': q.tolist(),
                   'position_error_m': residual.tolist(), 'position_error_norm_m': float(np.linalg.norm(residual)),
                   'true_orientation_error_rad': state['true_orientation_error_rad'],
                   'joint_margin_rad': state['joint_margin_rad'], 'original_solver_error': error,
                   'success': bool(error is None and np.linalg.norm(residual) < .001
                                   and state['true_orientation_error_rad'] < .011)}

    open_fingers = np.array([.04, .04])
    closed_fingers = np.array(closed['qpos'][7:9])
    summaries = []
    with (output / 'interpolated-geometry.jsonl').open('x', encoding='utf-8') as stream:
        for variant in manifest['variants']:
            q = qstart.copy()
            position = raised.copy()
            solutions = []
            samples = []
            failure = None
            for phase, target, grip in ((2, grasp, 255), (3, grasp, 0), (4, raised, 0)):
                origin = position.copy()
                count = 1 if variant.startswith('retained') or phase == 3 else max(1, int(np.ceil(np.linalg.norm(target - origin) / .01)))
                for sub in range(1, count + 1):
                    point = origin + (target - origin) * sub / count
                    if variant.startswith('retained'):
                        qnext = original_lift_q.copy() if phase == 4 else original_grasp_q.copy()
                        state = inspect(qnext, open_fingers)
                        result = {'target_m': point.tolist(), 'q': qnext.tolist(), 'success': True,
                                  'source': 'fixed retained endpoint command; no IK solve',
                                  'position_error_norm_m': float(np.linalg.norm(point - np.array(state['tcp_m']))),
                                  'true_orientation_error_rad': state['true_orientation_error_rad'],
                                  'joint_margin_rad': state['joint_margin_rad']}
                    elif phase == 3:
                        qnext = q.copy()
                        result = {'target_m': point.tolist(), 'q': qnext.tolist(), 'success': True,
                                  'source': 'unchanged endpoint during close dwell'}
                    else:
                        qnext, result = solve(point, q)
                    result.update(phase=phase, grip=grip, substep=sub, maximum_joint_step_rad=float(np.max(np.abs(qnext - q))))
                    solutions.append(result)
                    if not result['success']:
                        failure = result
                        break
                    for fraction in np.linspace(0., 1., 11):
                        fingers = (open_fingers + (closed_fingers - open_fingers) * fraction if phase == 3
                                   else open_fingers if phase == 2 else closed_fingers)
                        state = inspect(q + (qnext - q) * fraction, fingers)
                        state.update(variant=variant, phase=phase, grip=grip, substep=sub, fraction=float(fraction))
                        stream.write(json.dumps(state, allow_nan=False, separators=(',', ':')) + '\n')
                        samples.append(state)
                    q = qnext
                if failure is not None:
                    break
                position = target
            descent = [s for s in samples if s['phase'] == 2]
            clearances = [s['sampled_clearance_by_object'].get('insert_A', {}).get('distance_m') for s in descent]
            clearances = [v for v in clearances if v is not None]
            summaries.append({'variant': variant, 'kinematic_path_constructed': failure is None,
                'failure': failure, 'solutions': solutions, 'sample_count': len(samples),
                'descent_maximum_lateral_error_m': max((s['lateral_error_from_source_m'] for s in descent), default=None),
                'descent_minimum_hand_insert_A_distance_m': min(clearances, default=None),
                'descent_maximum_true_orientation_error_rad': max((s['true_orientation_error_rad'] for s in descent), default=None),
                'physical_pickup_or_carry_success': None,
                'interpretation': 'Counterfactual sampled geometry. Positive clearance does not establish executed dynamics; frozen-object lift is not an attached-object simulation.'})
    summary = {'schema_version': manifest['schema_version'], 'paths': summaries,
               'module_source_unchanged': digest(__file__) == source_sha,
               'input_unchanged': digest(INPUT) == INPUT_SHA256,
               'geometry_sha256': digest(output / 'interpolated-geometry.jsonl'), 'physical_trials': 0}
    save(output / 'summary.json', summary)
    return summary


if __name__ == '__main__':
    raise SystemExit('Run only through the verified queued recovery diagnostic 002 driver.')
