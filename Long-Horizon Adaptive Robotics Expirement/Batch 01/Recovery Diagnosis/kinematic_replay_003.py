"""Queue-only four fixed HOME-start insert pickup comparisons; no physics steps."""
from __future__ import annotations

import argparse
import ast
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import zipfile

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
CALIBRATION = PROJECT / 'Evidence/calibration/physical-calibration-002'
INPUT = HERE.parent / 'Insert Pickup Diagnostics/selected-replay-input.json'
INPUT_SHA256 = 'e8f471ef33a020b6b85339e41b4bb81a785c9c46a7ecd11ff2023ea21c041861'
SENSOR_EVENT_ID = 874
SENSOR_PAYLOAD_SHA256 = '5d7608f507fcae1c8ff134b8b1740809fb94bf5eb98aff7bbc9572923f7517fd'
VARIANTS = (('original-A', 120), ('original-A', 480), ('relocated-A', 120), ('relocated-A', 480))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(PROJECT / 'Runtime'))
    from release_runner import queued_job
    job = queued_job(expected_script=__file__)
    import mujoco
    import numpy as np

    if digest(INPUT) != INPUT_SHA256:
        raise RuntimeError('Declared retained input changed')
    inputs = json.loads(INPUT.read_text(encoding='utf-8'))
    xml = Path(inputs['source_world_xml'])
    if digest(xml) != inputs['source_world_xml_sha256']:
        raise RuntimeError('Retained XML changed')
    with zipfile.ZipFile(CALIBRATION / 'source-bundle.zip') as archive:
        source = archive.read('Runtime/cell.py')
    before = json.loads(Path(inputs['source_before_manifest']).read_text(encoding='utf-8'))
    cell_sha = next(v for k, v in before['source_hashes'].items()
                    if k.replace('\\', '/').endswith('/Runtime/cell.py'))
    if hashlib.sha256(source).hexdigest() != cell_sha:
        raise RuntimeError('Archived cell differs from before-run manifest')
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Cell')
    original_ik = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'ik')
    home = np.array(ast.literal_eval(next(n.value.args[0] for n in tree.body
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'HOME' for t in n.targets))))
    zones = ast.literal_eval(next(n.value for n in tree.body
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'ZONES' for t in n.targets)))
    solvers = {}
    solver_sources = {}
    for budget in (120, 480):
        method = copy.deepcopy(original_ik)
        loops = [n for n in ast.walk(method) if isinstance(n, ast.For)
                 and isinstance(n.iter, ast.Call) and isinstance(n.iter.func, ast.Name)
                 and n.iter.func.id == 'range' and len(n.iter.args) == 1
                 and isinstance(n.iter.args[0], ast.Constant) and n.iter.args[0].value == 120]
        if len(loops) != 1:
            raise RuntimeError('Expected one archived solver iteration loop')
        loops[0].iter.args[0].value = budget
        # A local counter observes iteration count without changing numerical work.
        loops[0].body.insert(0, ast.parse('self.diagnostic_iterations += 1').body[0])
        ast.fix_missing_locations(method)
        module = ast.Module(body=[method], type_ignores=[])
        method_source = ast.unparse(module)
        namespace = {'np': np, 'mujoco': mujoco}
        exec(compile(module, 'archived-Cell.ik-budget-' + str(budget), 'exec'), namespace)
        solvers[budget] = namespace['ik']
        solver_sources[str(budget)] = {'source': method_source,
                                     'sha256': hashlib.sha256(method_source.encode()).hexdigest()}
    events_path = CALIBRATION / 'insert-exchange/events.jsonl'
    with events_path.open(encoding='utf-8') as stream:
        sensor = next(row for line in stream if (row := json.loads(line))['event_id'] == SENSOR_EVENT_ID)
    if sensor['payload_sha256'] != SENSOR_PAYLOAD_SHA256:
        raise RuntimeError('Declared source observation event changed')
    observed = next(d for d in sensor['payload']['detections'] if d['id'] == 'insert_A')
    pre = next(s for s in inputs['samples'] if s['target_sim_time_s'] == 46.752)
    closed = next(s for s in inputs['samples'] if s['target_sim_time_s'] == 51.002)
    configuration = np.array(pre['record']['worlds'][0]['qpos'])
    model = mujoco.MjModel.from_xml_path(str(xml))
    data = mujoco.MjData(model)
    data.qpos[:] = configuration
    data.qpos[:7] = home
    mujoco.mj_forward(model, data)
    site = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, 'tcp')
    if site < 0:
        raise RuntimeError('Retained model lacks TCP site')
    start_tcp = data.site_xpos[site].copy()
    obj = SimpleNamespace(model=model, data=data, ikdata=mujoco.MjData(model), tcp=site,
                          jacp=np.zeros((3, model.nv)), jacr=np.zeros((3, model.nv)), diagnostic_iterations=0)
    limits = model.jnt_range[:7]
    goal = np.diag([1., -1., -1.])
    hand_bodies = {mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
                   for name in ('hand', 'left_finger', 'right_finger')}
    hand_geoms = {i for i in range(model.ngeom) if int(model.geom_bodyid[i]) in hand_bodies}

    proposed_zones = dict(zones, parking1=(.34, .04), parking2=(.46, .12), insert_home_A=(.34, -.43))
    regions = {name: (np.array(center), np.array([.092, .065] if name.startswith('tray') else [.053, .053]))
               for name, center in proposed_zones.items()}
    regions['raw_stock_envelope'] = (np.array([(.296 + .514) / 2, (-.334 - .064) / 2]),
                                      np.array([(.514 - .296) / 2, (.334 - .064) / 2]))
    center, half = regions['insert_home_A']
    gaps = []
    for other, (othercenter, otherhalf) in regions.items():
        if other == 'insert_home_A':
            continue
        gap = np.abs(center - othercenter) - half - otherhalf
        gaps.append({'region': other, 'axis_signed_gap_m': gap.tolist(), 'separated': bool(np.any(gap > 0))})
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    script_sha = digest(__file__)
    plan_sha = digest(HERE / 'PLAN-003.md')
    manifest = {'schema': 'insert-home-budget-kinematic-comparison-3', 'queue_job_id': job['id'],
        'started_at': datetime.now(timezone.utc).isoformat(), 'script_sha256': script_sha,
        'plan_sha256': plan_sha, 'retained_cell_sha256': cell_sha, 'scene_xml_sha256': digest(xml),
        'source_bundle_sha256': digest(CALIBRATION / 'source-bundle.zip'), 'input_sha256': INPUT_SHA256,
        'events_sha256': digest(events_path), 'source_event_id': SENSOR_EVENT_ID,
        'source_payload_sha256': SENSOR_PAYLOAD_SHA256, 'source_observation': observed,
        'precontact_sample': pre, 'retained_closed_fingers_m': closed['record']['worlds'][0]['qpos'][7:9],
        'common_home_q': home.tolist(), 'common_home_tcp_m': start_tcp.tolist(),
        'variants': [{'home': name, 'iterations': budget} for name, budget in VARIANTS],
        'solver_sources': solver_sources, 'maximum_target_spacing_m': .01,
        'original_solver_tolerances': {'position_m': .001, 'cross_product_orientation': .01},
        'additional_true_orientation_guard_rad': .01, 'fixed_region_checks': gaps,
        'proposed_A_region_overlap_free': all(row['separated'] for row in gaps),
        'no_physics_steps': True, 'physical_pickup_or_carry_success_claimed': False,
        'mujoco_version': mujoco.__version__, 'numpy_version': np.__version__,
        'scene_limit': 'Objects stay at the retained original precontact poses. Relocated-home scene-object contacts are not applicable.',
        'solver_edit': 'Only iteration range differs numerically; both variants add an observational loop counter.'}
    save(output / 'manifest.json', manifest)

    def geometry(q, fingers, applicable):
        data.qpos[:] = configuration
        data.qpos[:7] = q
        data.qpos[7:9] = fingers
        mujoco.mj_forward(model, data)
        rotation = data.site_xmat[site].reshape(3, 3)
        angle = float(np.arccos(np.clip((np.trace(goal.T @ rotation) - 1) / 2, -1, 1)))
        contacts = None
        if applicable:
            contacts = []
            for contact in data.contact[:data.ncon]:
                if int(contact.geom1) in hand_geoms or int(contact.geom2) in hand_geoms:
                    contacts.append({'geom1': mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, int(contact.geom1)),
                                     'geom2': mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, int(contact.geom2)),
                                     'distance_m': float(contact.dist)})
        return {'q': np.asarray(q).tolist(), 'finger_q_m': np.asarray(fingers).tolist(),
            'joint_margin_rad': np.minimum(q - limits[:, 0], limits[:, 1] - q).tolist(),
            'tcp_m': data.site_xpos[site].tolist(), 'true_orientation_error_rad': angle,
            'scene_contacts_applicable': applicable, 'reconstructed_hand_contacts': contacts}

    summaries = []
    open_fingers = np.array([.04, .04])
    closed_fingers = np.array(closed['record']['worlds'][0]['qpos'][7:9])
    with (output / 'interpolated-geometry.jsonl').open('x', encoding='utf-8') as stream:
        for name, budget in VARIANTS:
            source_point = np.array(observed['pos'])
            if name == 'relocated-A':
                source_point[:2] = [.34, -.43]
            source_point[2] = max(source_point[2], .008) + .004
            above = max(source_point[2], .008 + .003 + .004) + .16
            points = [(np.r_[start_tcp[:2], max(start_tcp[2], above)], 255),
                      (np.r_[source_point[:2], above], 255), (source_point, 255),
                      (source_point, 0), (np.r_[source_point[:2], above], 0)]
            q = home.copy()
            position = start_tcp.copy()
            solutions = []
            failure = None
            sample_count = 0
            for phase, (target, grip) in enumerate(points):
                origin = position.copy()
                count = max(1, int(np.ceil(np.linalg.norm(target - origin) / .01)))
                for sub in range(1, count + 1):
                    point = origin + (target - origin) * sub / count
                    error = None
                    obj.diagnostic_iterations = 0
                    try:
                        qnext = solvers[budget](obj, point, q, configuration)
                    except ValueError as exc:
                        qnext = obj.ikdata.qpos[:7].copy()
                        error = str(exc)
                    endpoint = geometry(qnext, open_fingers, name == 'original-A')
                    residual = point - np.array(endpoint['tcp_m'])
                    successful = bool(error is None and np.linalg.norm(residual) < .001
                                      and endpoint['true_orientation_error_rad'] < .01)
                    result = {'phase': phase, 'grip': grip, 'substep': sub, 'target_m': point.tolist(),
                        'q': qnext.tolist(), 'joint_margin_rad': endpoint['joint_margin_rad'],
                        'position_error_m': residual.tolist(), 'position_error_norm_m': float(np.linalg.norm(residual)),
                        'true_orientation_error_rad': endpoint['true_orientation_error_rad'],
                        'original_solver_accepted': error is None, 'original_solver_error': error,
                        'iterations_used': obj.diagnostic_iterations, 'success': successful,
                        'maximum_joint_step_rad': float(np.max(np.abs(qnext - q)))}
                    solutions.append(result)
                    if not successful:
                        failure = result
                        break
                    for fraction in np.linspace(0., 1., 11):
                        fingers = (open_fingers + (closed_fingers - open_fingers) * fraction if phase == 3
                                   else closed_fingers if phase == 4 else open_fingers)
                        sample = geometry(q + (qnext - q) * fraction, fingers, name == 'original-A')
                        sample.update(home=name, iteration_budget=budget, phase=phase, grip=grip,
                                      substep=sub, fraction=float(fraction))
                        stream.write(json.dumps(sample, allow_nan=False, separators=(',', ':')) + '\n')
                        sample_count += 1
                    q = qnext
                if failure:
                    break
                position = target
            row = {'home': name, 'iterations': budget, 'source_target_m': source_point.tolist(),
                'raised_height_m': above, 'success': failure is None, 'failure': failure,
                'solutions': solutions, 'sample_count': sample_count,
                'physical_pickup_or_carry_success': None}
            summaries.append(row)
            save(output / 'progress.json', {'completed': summaries})
    summary = {'manifest': manifest, 'paths': summaries, 'module_source_unchanged': digest(__file__) == script_sha,
        'plan_unchanged': digest(HERE / 'PLAN-003.md') == plan_sha,
        'geometry_sha256': digest(output / 'interpolated-geometry.jsonl'),
        'interpretation': 'Four declared static paths. Kinematic convergence and sampled geometry are not physical pickup evidence.'}
    save(output / 'summary.json', summary)
    print(json.dumps([{'home': r['home'], 'iterations': r['iterations'], 'success': r['success'],
                       'failure': r['failure']} for r in summaries], indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
