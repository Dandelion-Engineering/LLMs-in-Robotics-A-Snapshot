"""Five declared native static hand/arm checks; never integrate physics."""
from __future__ import annotations
import argparse
import ast
import colorsys
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
RUNTIME = PROJECT / 'Runtime'
PANDA = RUNTIME / 'vendor/panda'
INCIDENT = PROJECT / 'Evidence/raw/B01-dev-C0-007/manifest.json'
ASSET_MANIFEST = PROJECT / 'Evidence/calibration/physical-calibration-005/manifest.json'
PINS = {INCIDENT: 'b4c9b17a320fd44a793890bc5ac7184f0d05435bcb8e505f9e706d335f5395b4',
        ASSET_MANIFEST: '6572278756b0491719d68d285518d4b5bcfa24411ce892837adcaecb02e265e0',
        RUNTIME / 'cell.py': 'ac13595b62ae51bb1cc5dd7387ab0ec605253fa65a0a276c5c85395929cb40fa'}
VARIANTS = [('current74', .074, -.310, 0.), ('pitch90', .090, -.358, 0.),
            ('pitch95', .095, -.373, 0.), ('pitch100', .100, -.388, 0.), ('yaw90', .074, -.310, 90.)]
OFFSETS = [(0., 0.), (-.004, 0.), (.004, 0.), (0., -.004), (0., .004)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False); stream.write('\n')


def check_budget(deadline):
    if time.perf_counter() >= deadline:
        raise TimeoutError('Declared 300-second static diagnostic budget reached')


def source_functions(np, mj):
    tree = ast.parse((RUNTIME / 'cell.py').read_text(encoding='utf-8'))
    names = {'ZONES', 'PART_HALF', 'HOME', 'DT', 'FIXTURE_JAW_SLOT_HALF_M', 'IK_MAX_ITERATIONS'}
    nodes = [copy.deepcopy(n) for n in tree.body if
             isinstance(n, ast.FunctionDef) and n.name in ('zone_half', '_sub', 'build_scene') or
             isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets)]
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Cell')
    ik = copy.deepcopy(next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'ik'))
    assignments = [n for n in ast.walk(ik) if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'target_rotation' for t in n.targets)]
    if len(assignments) != 1:
        raise ValueError('Pinned IK rotation assignment is not unique')
    assignments[0].value = ast.parse('self.diagnostic_target_rotation', mode='eval').body
    nodes.append(ik)
    module = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    namespace = {'HERE': RUNTIME, 'ET': ET, 'np': np, 'mujoco': mj, 'colorsys': colorsys}
    exec(compile(module, 'pinned-static-geometry-functions', 'exec'), namespace)
    return namespace, ast.unparse(module)


def rotation(np, degrees):
    angle = np.deg2rad(degrees)
    return np.array([[np.cos(angle), -np.sin(angle), 0.], [np.sin(angle), np.cos(angle), 0.], [0., 0., 1.]]) @ np.diag([1., -1., -1.])


def hand_xml(neighbors):
    source = ET.parse(PANDA / 'panda.xml').getroot()
    root = ET.Element('mujoco', model='static-native-hand-probe')
    ET.SubElement(root, 'compiler', angle='radian', meshdir=str(PANDA / 'assets'), autolimits='true')
    root.append(copy.deepcopy(source.find('default')))
    assets = ET.SubElement(root, 'asset')
    for mesh in source.findall('asset/mesh'):
        if mesh.get('name', Path(mesh.get('file')).stem) in ('hand_c', 'finger_0'):
            assets.append(copy.deepcopy(mesh))
    world = ET.SubElement(root, 'worldbody')
    hand = copy.deepcopy(source.find(".//body[@name='hand']"))
    hand.set('pos', '0 0 0'); hand.set('quat', '1 0 0 0'); hand.set('childclass', 'panda')
    hand.insert(0, ET.Element('freejoint', name='hand_pose'))
    for body in hand.iter('body'):
        for geom in list(body.findall('geom')):
            if geom.get('class') == 'visual':
                body.remove(geom)
            elif geom.get('class', '').startswith('fingertip_pad'):
                geom.set('friction', '1.5 .02 .001')
    ET.SubElement(hand, 'site', name='tcp', pos='0 0 .1034')
    world.append(hand)
    for name, xy in neighbors.items():
        ET.SubElement(world, 'geom', name='stock_' + name, type='box', size='.021 .021 .018',
                      pos=f'{xy[0]} {xy[1]} .018')
    return ET.tostring(root, encoding='unicode')


def hand_probe(np, mj, root, variant, positions, deadline):
    name, pitch, origin, yaw = variant
    centered = {key: np.array(value)[:2] - np.array(positions['A3'])[:2] for key, value in positions.items() if key != 'A3'}
    worlds = {'seed2_nominal': centered, 'pairwise_inward_6mm':
        {'north': [0., pitch - .006], 'south': [0., -(pitch - .006)],
         'east': [.085 - .006, 0.], 'west': [-.085 + .006, 0.]}}
    results = []
    with (root / (name + '-hand-samples.jsonl')).open('x', encoding='utf-8') as stream:
        for world_name, neighbors in worlds.items():
            xml = hand_xml(neighbors)
            (root / (name + '-' + world_name + '-hand.xml')).write_text(xml, encoding='utf-8')
            model = mj.MjModel.from_xml_string(xml); data = mj.MjData(model)
            stock = {key: mj.mj_name2id(model, mj.mjtObj.mjOBJ_GEOM, 'stock_' + key) for key in neighbors}
            hand = [i for i in range(model.ngeom) if int(model.geom_bodyid[i]) != 0
                    and (model.geom_contype[i] or model.geom_conaffinity[i])]
            labels = {i: {'geom_id': i, 'geom_name': mj.mj_id2name(model, mj.mjtObj.mjOBJ_GEOM, i),
                         'body': mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY, int(model.geom_bodyid[i]))} for i in hand}
            orient = rotation(np, yaw); quat = np.empty(4); mj.mju_mat2Quat(quat, orient.ravel())
            for offset in OFFSETS:
                check_budget(deadline)
                minima, negative = {}, 0
                for height in np.linspace(.018, .180, 163):
                    data.qpos[:3] = [offset[0], offset[1], float(height) + .1034]
                    data.qpos[3:7] = quat; data.qpos[7:9] = .04
                    mj.mj_forward(model, data)
                    samples = {}
                    for other, geom in stock.items():
                        best = min((float(mj.mj_geomDistance(model, data, robot, geom, .2, None)), robot) for robot in hand)
                        value = {'signed_distance_m': best[0], 'hand_geom': labels[best[1]],
                                 'tcp_m': [offset[0], offset[1], float(height)]}
                        samples[other] = value
                        if other not in minima or value['signed_distance_m'] < minima[other]['signed_distance_m']:
                            minima[other] = value
                        negative += int(value['signed_distance_m'] < 0.)
                    stream.write(json.dumps({'world': world_name, 'offset_m': offset, 'tcp_z_m': float(height),
                                             'neighbors': samples}, allow_nan=False) + '\n')
                results.append({'world': world_name, 'offset_m': offset, 'minimum_by_neighbor': minima,
                                'negative_neighbor_samples': negative, 'sample_count': 163,
                                'tcp_z_sample_spacing_m': .001, 'distance_query_saturation_m': .2})
    return {'variant': name, 'row_pitch_m': pitch, 'row0_y_m': origin, 'yaw_deg': yaw,
            'native_open_finger_displacement_m': .04, 'cases': results,
            'scope': 'Prescribed native hand pose and frozen upright boxes; no arm reach or physical outcome implied'}


def arm_probe(np, mj, model, namespace, root, variant, positions, deadline):
    name, pitch, origin, yaw = variant
    data, ikdata = mj.MjData(model), mj.MjData(model)
    tcp = mj.mj_name2id(model, mj.mjtObj.mjOBJ_SITE, 'tcp')
    for identity, pos in positions.items():
        body = mj.mj_name2id(model, mj.mjtObj.mjOBJ_BODY, identity)
        joint = int(model.body_jntadr[body]); address = int(model.jnt_qposadr[joint])
        data.qpos[address:address + 3] = [pos[0], pos[1], .018]
    data.qpos[:7] = namespace['HOME']; data.qpos[7:9] = .04
    configuration = data.qpos.copy()
    helper = SimpleNamespace(model=model, data=data, ikdata=ikdata, tcp=tcp,
        jacp=np.zeros((3, model.nv)), jacr=np.zeros((3, model.nv)), diagnostic_target_rotation=rotation(np, yaw))
    ranges = model.jnt_range[:7].copy()
    robot_bodies = {i for i in range(model.nbody) if mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY, i)
                    in ('link0', 'link1', 'link2', 'link3', 'link4', 'link5', 'link6', 'link7', 'hand', 'left_finger', 'right_finger')}
    raw_bodies = {mj.mj_name2id(model, mj.mjtObj.mjOBJ_BODY, identity): identity for identity in positions}
    results = []
    with (root / (name + '-arm-waypoints.jsonl')).open('x', encoding='utf-8') as stream:
        for identity, pos in positions.items():
            q = namespace['HOME'].copy(); data.qpos[:] = configuration; data.qpos[:7] = q; mj.mj_forward(model, data)
            current = data.site_xpos[tcp].copy()
            points = [np.r_[current[:2], max(current[2], .18)], np.array([pos[0], pos[1], .18]), np.array([pos[0], pos[1], .018])]
            result = {'part': identity, 'target_m': points[-1].tolist(), 'passed': True, 'attempted_waypoints': 0,
                      'maximum_position_residual_m': 0., 'maximum_true_orientation_error_rad': 0.,
                      'minimum_joint_margin_rad': float('inf'), 'other_raw_negative_contact_samples': 0}
            try:
                for phase, target in enumerate(points):
                    start = current.copy()
                    count = max(1, int(np.ceil(np.linalg.norm(target - start) / .01)))
                    for step in range(1, count + 1):
                        check_budget(deadline)
                        desired = start + (target - start) * step / count
                        result['attempted_waypoints'] += 1
                        q = namespace['ik'](helper, desired, q, configuration)
                        data.qpos[:] = configuration; data.qpos[:7] = q; mj.mj_forward(model, data)
                        achieved = data.site_xpos[tcp].copy()
                        orientation = data.site_xmat[tcp].reshape(3, 3)
                        angle = float(np.arccos(np.clip((np.trace(helper.diagnostic_target_rotation.T @ orientation) - 1.) / 2., -1., 1.)))
                        residual = float(np.linalg.norm(achieved - desired))
                        margin = float(np.min(np.minimum(q - ranges[:, 0], ranges[:, 1] - q)))
                        contacts = []
                        for c in data.contact:
                            bodies = [int(model.geom_bodyid[int(c.geom1)]), int(model.geom_bodyid[int(c.geom2)])]
                            if c.dist < 0 and ((bodies[0] in robot_bodies and bodies[1] in raw_bodies and raw_bodies[bodies[1]] != identity)
                                    or (bodies[1] in robot_bodies and bodies[0] in raw_bodies and raw_bodies[bodies[0]] != identity)):
                                contacts.append({'geom1': int(c.geom1), 'geom2': int(c.geom2), 'distance_m': float(c.dist),
                                    'bodies': [mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY, b) for b in bodies]})
                        row = {'part': identity, 'phase': phase, 'substep': step, 'desired_tcp_m': desired.tolist(),
                            'actual_tcp_m': achieved.tolist(), 'q_rad': q.tolist(), 'position_residual_m': residual,
                            'true_orientation_error_rad': angle, 'joint_margin_rad': margin, 'other_raw_native_contacts': contacts}
                        stream.write(json.dumps(row, allow_nan=False) + '\n')
                        result['maximum_position_residual_m'] = max(result['maximum_position_residual_m'], residual)
                        result['maximum_true_orientation_error_rad'] = max(result['maximum_true_orientation_error_rad'], angle)
                        result['minimum_joint_margin_rad'] = min(result['minimum_joint_margin_rad'], margin)
                        result['other_raw_negative_contact_samples'] += int(bool(contacts))
                        if angle >= .02:
                            raise ValueError('True orientation error exceeds .02rad despite cross-product convergence')
                    current = target.copy()
            except ValueError as error:
                result.update(passed=False, error=str(error), failed_target_m=desired.tolist())
            if not np.isfinite(result['minimum_joint_margin_rad']): result['minimum_joint_margin_rad'] = None
            results.append(result)
    return {'variant': name, 'paths': results, 'all_ik_paths_converged_with_true_orientation': all(r['passed'] for r in results),
            'scope': 'Static common HOME approach through <=10mm Cartesian waypoints; no stepping/tracking/swept-path/physical success claim'}


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', required=True); args = parser.parse_args()
    sys.path.insert(0, str(RUNTIME)); from release_runner import queued_job
    job = queued_job(expected_script=__file__)
    import mujoco as mj
    import numpy as np
    deadline = time.perf_counter() + 300.
    output = Path(args.output).resolve(); output.mkdir(parents=True, exist_ok=False)
    for path, expected in PINS.items():
        if sha(path) != expected: raise ValueError('Pinned source changed: ' + str(path))
    incident = json.loads(INCIDENT.read_text(encoding='utf-8'))
    if incident['code_sha256']['cell.py'] != PINS[RUNTIME / 'cell.py']: raise ValueError('Incident cell identity mismatch')
    asset_manifest = json.loads(ASSET_MANIFEST.read_text(encoding='utf-8'))
    paths = {Path(k): v for k, v in asset_manifest['source_hashes'].items() if PANDA in Path(k).parents}
    if not paths or any(not p.is_file() or sha(p) != expected for p, expected in paths.items()):
        raise ValueError('Native Panda assets differ from pinned calibration005')
    pinned = {**{str(p): v for p, v in PINS.items()}, **{str(p): v for p, v in paths.items()}}
    with zipfile.ZipFile(output / 'diagnostic-sources.zip', 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(PINS) | set(paths) | {Path(__file__), HERE / 'PLAN-001.md'}):
            archive.write(path, path.relative_to(PROJECT).as_posix())
    save(output / 'manifest.json', {'created_at': datetime.now(timezone.utc).isoformat(), 'queue_job': job,
        'source_hashes': pinned, 'variants': VARIANTS, 'offsets_m': OFFSETS, 'simulation_steps': 0,
        'internal_wall_budget_s': 300., 'physics_performance_claimed': False, 'source_archive_sha256': sha(output / 'diagnostic-sources.zip')})
    namespace, selected_source = source_functions(np, mj)
    (output / 'selected-source-functions.py').write_text(selected_source, encoding='utf-8')
    xml, registry = namespace['build_scene'](10, 2, 2)
    (output / 'source-seed2-world.xml').write_text(xml, encoding='utf-8')
    base_tree = ET.fromstring(xml)
    base_positions = {identity: np.array([float(x) for x in base_tree.find(f".//body[@name='{identity}']").get('pos').split()])
                      for identity, entry in registry.items() if entry['kind'] == 'part'}
    model = mj.MjModel.from_xml_string(xml)
    reports = []
    for variant in VARIANTS:
        check_budget(deadline)
        name, pitch, origin, yaw = variant
        positions = {identity: pos.copy() for identity, pos in base_positions.items()}
        for identity, pos in positions.items():
            row = (int(identity[1:]) - 1) // 3
            pos[1] += origin + pitch * row - (-.310 + .074 * row)
        hand = hand_probe(np, mj, output, variant, positions, deadline)
        save(output / (name + '-hand-summary.json'), hand)
        arm = arm_probe(np, mj, model, namespace, output, variant, positions, deadline)
        save(output / (name + '-arm-summary.json'), arm)
        reports.append({'variant': name, 'row_pitch_m': pitch, 'row0_y_m': origin, 'yaw_deg': yaw,
            'nominal_source_positions_m': {k: v.tolist() for k, v in positions.items()},
            'hand': hand, 'arm': arm})
    unchanged = all(sha(Path(p)) == expected for p, expected in pinned.items())
    if not unchanged: raise ValueError('Pinned source changed during diagnostic')
    save(output / 'summary.json', {'finished_at': datetime.now(timezone.utc).isoformat(), 'queue_job_id': job['id'],
        'sources_unchanged': unchanged, 'simulation_steps': 0, 'reports': reports,
        'scope': 'Static sampled native collision distances and inverse/forward kinematics only; no physical repair validated'})
    save(output / 'evidence-index.json', {'files': [{'path': p.relative_to(output).as_posix(), 'sha256': sha(p),
        'bytes': p.stat().st_size} for p in sorted(output.rglob('*')) if p.is_file()]})
    print(json.dumps({'output': str(output), 'variants_completed': len(reports), 'simulation_steps': 0}))


if __name__ == '__main__':
    main()
