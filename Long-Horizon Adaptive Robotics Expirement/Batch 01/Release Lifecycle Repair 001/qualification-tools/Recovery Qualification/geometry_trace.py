"""Protected geometry sampling on the existing physics owner; no stepping."""
from __future__ import annotations

import json
import time

from fixture import SamplingGaps, canonical, transformed_box
from measurement import DenseBounds


class GeometryTrace:
    def __init__(self, loop, payload_id, interval_s=.02):
        import mujoco
        import numpy as np
        self.mj, self.np, self.loop = mujoco, np, loop
        self.cell = loop.cells[0]
        self.payload_id, self.interval = payload_id, interval_s
        self.phase = 'pickup'
        self.last_sim = None
        self.gaps = SamplingGaps()
        self.phase_gaps = {}
        self.interval_dense = DenseBounds()
        self.phase_dense = {}
        self.previous_coarse_bounds = None
        self.stream = (loop.records.root / 'whole-geometry.jsonl').open('x', encoding='utf-8', newline='\n')
        model = self.cell.model
        self.bodies = {i: mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i) or f'body_{i}'
                       for i in range(model.nbody)}
        payload_body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, payload_id)
        robot_root = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, 'link0')
        def descends(body, root):
            while body > 0:
                if body == root:
                    return True
                body = int(model.body_parentid[body])
            return False
        self.geoms = []
        for i in range(model.ngeom):
            body = int(model.geom_bodyid[i])
            colliding = bool(model.geom_contype[i] or model.geom_conaffinity[i])
            role = 'payload' if descends(body, payload_body) else 'robot' if descends(body, robot_root) else None
            if role is None or (role == 'robot' and not colliding):
                continue
            kind = int(model.geom_type[i])
            size = model.geom_size[i].copy()
            center = np.zeros(3)
            if kind == int(mujoco.mjtGeom.mjGEOM_BOX):
                half = size
                method = 'exact oriented box outer AABB'
            elif kind == int(mujoco.mjtGeom.mjGEOM_MESH):
                mesh = int(model.geom_dataid[i])
                start, count = int(model.mesh_vertadr[mesh]), int(model.mesh_vertnum[mesh])
                verts = model.mesh_vert[start:start + count]
                low, high = verts.min(axis=0), verts.max(axis=0)
                center, half = (low + high) / 2, (high - low) / 2
                method = 'rotated compiled-mesh local AABB; conservative outer bound'
            elif kind == int(mujoco.mjtGeom.mjGEOM_SPHERE):
                half = np.full(3, size[0]); method = 'sphere enclosing local box'
            elif kind in (int(mujoco.mjtGeom.mjGEOM_CAPSULE), int(mujoco.mjtGeom.mjGEOM_CYLINDER)):
                half = np.array([size[0], size[0], size[1] + (size[0] if kind == int(mujoco.mjtGeom.mjGEOM_CAPSULE) else 0)])
                method = 'rotated enclosing capsule/cylinder box'
            elif kind == int(mujoco.mjtGeom.mjGEOM_ELLIPSOID):
                half = size; method = 'rotated enclosing ellipsoid box'
            else:
                raise ValueError('Unsupported robot/payload geometry: ' + str(kind))
            self.geoms.append({'geom_id': i, 'geom_name': mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, i),
                'body': self.bodies[body], 'role': role, 'collision_enabled': colliding, 'geom_type': kind,
                'local_center': center.tolist(), 'local_half': half.tolist(), 'bounds_method': method})
        if not any(g['role'] == 'robot' for g in self.geoms) or not any(g['role'] == 'payload' for g in self.geoms):
            raise ValueError('Incomplete whole robot/payload geometry inventory')
        self.geom_ids = [g['geom_id'] for g in self.geoms]
        self.local_centers = np.array([g['local_center'] for g in self.geoms])
        self.local_halves = np.array([g['local_half'] for g in self.geoms])
        (loop.records.root / 'geometry-inventory.json').write_text(json.dumps({'geoms': self.geoms,
            'sample_interval_target_s': interval_s, 'scope': 'all robot collision geoms and all payload geoms',
            'dense_recording': 'Per-physics-tick vectorized native cached-transform outer-box union, flushed at coarse samples; phase union retained at close',
            'alignment': 'Native post-mj_step cached transforms can precede integrated qpos by one physics step; both raw clocks/state are retained.',
            'continuous_sweep_bound': None}, indent=2) + '\n', encoding='utf-8')

    def sample(self, force=False):
        cell, model, data = self.cell, self.cell.model, self.cell.data
        sim = float(data.time)
        wall = time.perf_counter() - self.loop.start
        positions = data.geom_xpos[self.geom_ids]
        rotations = data.geom_xmat[self.geom_ids].reshape(-1, 3, 3)
        centers = positions + self.np.einsum('nij,nj->ni', rotations, self.local_centers)
        extents = self.np.einsum('nij,nj->ni', self.np.abs(rotations), self.local_halves)
        low, high = centers - extents, centers + extents
        self.interval_dense.add(sim, wall, low, high)
        if self.phase not in self.phase_dense:
            self.phase_dense[self.phase] = DenseBounds()
        self.phase_dense[self.phase].add(sim, wall, low, high)
        if not force and self.last_sim is not None and sim - self.last_sim < self.interval - 1e-9:
            return
        snapshot = self.loop.snapshot()
        geometry = []
        for meta in self.geoms:
            i = meta['geom_id']; rotation = data.geom_xmat[i].reshape(3, 3).tolist()
            position = data.geom_xpos[i].tolist()
            geometry.append({'geom_id': i, 'position_m': position, 'rotation_world': rotation,
                'outer_bounds': transformed_box(meta['local_center'], meta['local_half'], position, rotation)})
        contacts = []
        for index in range(data.ncon):
            contact = data.contact[index]
            ga, gb = int(contact.geom1), int(contact.geom2)
            force_value = self.np.zeros(6)
            self.mj.mj_contactForce(model, data, index, force_value)
            frame = contact.frame.reshape(3, 3)
            contacts.append({'index': index, 'geom1': ga, 'geom2': gb,
                'body1': self.bodies[int(model.geom_bodyid[ga])], 'body2': self.bodies[int(model.geom_bodyid[gb])],
                'distance_m': float(contact.dist), 'position_m': contact.pos.tolist(),
                'constraint_active': int(contact.efc_address) >= 0, 'force_contact_N_Nm': force_value.tolist(),
                'force_world_on_geom2_N': (frame.T @ force_value[:3]).tolist()})
        coarse = None if self.previous_coarse_bounds is None else (
            self.np.minimum(self.previous_coarse_bounds[0], low), self.np.maximum(self.previous_coarse_bounds[1], high))
        row = {'sim_time_s': sim, 'wall_elapsed_s': wall, 'phase': self.phase,
            'interval_dense_geometry': self.interval_dense.report(self.geom_ids, coarse),
            'physics_timestep_s': float(model.opt.timestep), 'qpos': data.qpos.tolist(), 'qvel': data.qvel.tolist(),
            'ctrl': data.ctrl.tolist(), 'actuator_force': data.actuator_force.tolist(),
            'robot_and_payload_geoms': geometry, 'objects': snapshot['objects'], 'zones': snapshot['zones'],
            'contacts': contacts, 'pending': snapshot['pending'], 'station': snapshot['station'],
            'continuous_collision_or_grasp_proof': False}
        self.stream.write(canonical(row).decode() + '\n')
        self.stream.flush()
        self.gaps.record(sim, wall)
        self.phase_gaps.setdefault(self.phase, SamplingGaps()).record(sim, wall)
        self.last_sim = sim
        self.previous_coarse_bounds = (low.copy(), high.copy())
        self.interval_dense = DenseBounds()
        self.interval_dense.add(sim, wall, low, high)

    def report(self):
        return {**self.gaps.report(), 'target_interval_s': self.interval,
                'phase_sampling': {k: v.report() for k, v in self.phase_gaps.items()},
                'dense_phase_geometry': {k: v.report(self.geom_ids) for k, v in self.phase_dense.items()},
                'qualifying_envelope_created': False}

    def close(self):
        # Retain an incomplete final coarse interval after a failed/timed-out phase.
        self.sample(force=True)
        (self.loop.records.root / 'dense-geometry-summary.json').write_text(
            json.dumps(self.report(), indent=2, allow_nan=False) + '\n', encoding='utf-8')
        self.stream.flush(); self.stream.close()
