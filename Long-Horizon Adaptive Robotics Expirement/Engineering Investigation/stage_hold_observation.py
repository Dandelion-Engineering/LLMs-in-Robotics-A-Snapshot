"""Stage an unapplied, hash-bound hold-observation optimization; never edit sources."""
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
STAGE = HERE / "Hold observation optimization"
BASES = {
    "Batch 01/Recovery Qualification/measurement.py": "44299ab54c5d6b3affcf519933fa1f4ae0bb11bbc4090a21eca470cda9a5ae41",
    "Batch 01/Recovery Qualification/run_screen.py": "7fa9510e11099bd015c99a46385446e749981f908cb8b117ed091e786a3f1c33",
    "Batch 01/Recovery Qualification/geometry_trace.py": "58b06967ff0eeb330dbaf4c6de5f33d7de4b225f31812d0237dd067a52f417e0",
    "Batch 01/Calibration Tools/physical_calibration.py": "a60618a22c6e841cd3cf223eae5e4cfaa830b7ad2a3b2347bb3a79d22c5cf019",
    "Runtime/evaluator.py": "9def52c38a88021195d79d9b527c08b9b7a1db2b38990b2287d697f20f63eb3a",
}

SAMPLER = '''class PayloadHoldSampler:
    """Read only fields consumed by HoldWindow from the same native state.

    Indices are cached for this immutable compiled model. Contact semantics
    match IndependentEvaluator.snapshot_cell exactly: distance tolerance and
    any descendant of hand, without force, active-constraint or bilateral tests.
    No stepping, forwarding, output, interpolation or snapshot-time cache.
    """
    def __init__(self, cell, part_id):
        import mujoco
        from evaluator import EvaluationError
        self.cell, self.part_id = cell, part_id
        model = self.model = cell.model
        self.body = None
        self.geometries = []
        if part_id in cell.registry:
            self.body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, part_id)
            if self.body < 0:
                raise EvaluationError('Registered object lacks a physical body: ' + part_id)
            self.geometries = [g for g in range(model.ngeom) if int(model.geom_bodyid[g]) == self.body
                               and (int(model.geom_contype[g]) or int(model.geom_conaffinity[g]))]
            if not self.geometries:
                raise EvaluationError('Registered object lacks collision geometry: ' + part_id)
        hand = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, 'hand')
        if hand < 0:
            raise EvaluationError('Panda gripper body was not found')
        self.gripper_bodies = set()
        for body in range(model.nbody):
            current = body
            while current:
                if current == hand:
                    self.gripper_bodies.add(body)
                    break
                current = int(model.body_parentid[current])

    def snapshot(self):
        import mujoco
        from evaluator import EvaluationError, box_bounds
        cell, model, data = self.cell, self.cell.model, self.cell.data
        if model is not self.model:
            raise EvaluationError('Hold sampler compiled model was replaced')
        if self.body is None:
            return {'objects': []}  # Preserve HoldWindow's existing missing-payload failure.
        contact_found = False
        for index in range(data.ncon):
            contact = data.contact[index]
            if float(contact.dist) > cell.evaluator.config.contact_tolerance_m:
                continue
            a, b = int(model.geom_bodyid[contact.geom1]), int(model.geom_bodyid[contact.geom2])
            if (a == self.body and b in self.gripper_bodies) or (b == self.body and a in self.gripper_bodies):
                contact_found = True
        bounds = []
        for geom in self.geometries:
            if int(model.geom_type[geom]) != int(mujoco.mjtGeom.mjGEOM_BOX):
                raise EvaluationError('Unsupported non-box object collision geometry: ' + self.part_id)
            bounds.append(box_bounds(data.geom_xpos[geom].tolist(), data.geom_xmat[geom].tolist(), model.geom_size[geom].tolist()))
        return {'objects': [{'id': self.part_id, 'position': data.xpos[self.body].tolist(),
            'bounds': {'min': [min(b['min'][i] for b in bounds) for i in range(3)],
                       'max': [max(b['max'][i] for b in bounds) for i in range(3)]},
            'gripper_contact': contact_found}]}


'''

NATIVE_METHOD = '''    def native_snapshot(self, cell):
        sampler = getattr(self, '_native_sampler', None)
        if sampler is None:
            sampler = self._native_sampler = PayloadHoldSampler(cell, self.part_id)
        elif sampler.cell is not cell:
            raise ValueError('Hold window physics owner changed')
        return sampler.snapshot()

'''


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def staged_sources():
    for name, expected in BASES.items():
        if digest(PROJECT / name) != expected: raise ValueError("Held source differs: " + name)
    measurement = (PROJECT / "Batch 01/Recovery Qualification/measurement.py").read_text(encoding="utf-8")
    if measurement.count("class HoldWindow:\n") != 1 or measurement.count("    def record(self, snapshot, sim, wall, *, tick):\n") != 1:
        raise ValueError("HoldWindow source anchors differ")
    measurement = measurement.replace("class HoldWindow:\n", SAMPLER + "class HoldWindow:\n")
    measurement = measurement.replace("    def record(self, snapshot, sim, wall, *, tick):\n", NATIVE_METHOD + "    def record(self, snapshot, sim, wall, *, tick):\n")
    runner = (PROJECT / "Batch 01/Recovery Qualification/run_screen.py").read_text(encoding="utf-8")
    old = "self.hold_window.record(self.snapshot(), float(self.cells[0].data.time),"
    if runner.count(old) != 1: raise ValueError("QualificationLoop source anchor differs")
    runner = runner.replace(old, "self.hold_window.record(self.hold_window.native_snapshot(self.cells[0]), float(self.cells[0].data.time),")
    return {"Batch 01/Recovery Qualification/measurement.py": measurement,
            "Batch 01/Recovery Qualification/run_screen.py": runner}


def stage():
    patch = []
    changed = []
    for relative, text in staged_sources().items():
        target = STAGE / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
        compile(text, str(target), "exec")
        original = (PROJECT / relative).read_text(encoding="utf-8")
        patch.extend(difflib.unified_diff(original.splitlines(True), text.splitlines(True),
                                        fromfile="a/" + relative, tofile="b/" + relative))
        changed.append({"path": relative, "before_sha256": BASES[relative], "staged_sha256": digest(target)})
    destination = STAGE / "selected-payload-hold.patch"
    destination.write_text("".join(patch), encoding="utf-8", newline="\n")
    manifest = {"schema_version": "unapplied-hold-observation-patch-1", "applied": False,
                "source_guards": BASES, "changed": changed, "patch_sha256": digest(destination),
                "unchanged": [key for key in BASES if key not in staged_sources()],
                "scope": "Selected-payload hold observation only; per-tick predicate, full snapshots/events, dense geometry and parent pacing unchanged"}
    (STAGE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for name, expected in BASES.items():
        if digest(PROJECT / name) != expected: raise ValueError("Held source changed while staging")
    return manifest


if __name__ == "__main__":
    print(json.dumps(stage(), indent=2))
