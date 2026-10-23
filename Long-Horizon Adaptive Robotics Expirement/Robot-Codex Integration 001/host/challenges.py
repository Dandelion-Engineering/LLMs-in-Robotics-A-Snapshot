"""PRIVATE development fixtures and reference solutions. Never deploy to robot."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path

FAMILIES = {
    "misplaced-stock": {
        "part_count": 1,
        "placements": [{"part_id": "A1", "zone": "quarantine"}],
        "order": {"version": 1, "closed": True, "requirements": [
            {"family": "A", "recipe": "A", "count": 1, "tray": "tray1", "max_rework_cycles": 0}]},
        "reference_actions": [{"operation": "transport", "part_id": "A1", "destination": "parking1"}],
        "missing_rule": "Frozen baseline excludes quarantine from raw-stock eligibility; no failed inspection is present.",
        "baseline_source": "Runtime 004/candidates.py:739-756",
    },
    "blocked-insert-home": {
        "part_count": 2,
        "placements": [{"part_id": "A1", "zone": "insert_home_A"}],
        "order": {"version": 1, "closed": True, "requirements": [
            {"family": "B", "recipe": "B", "count": 1, "tray": "tray2", "max_rework_cycles": 0}]},
        "reference_actions": [{"operation": "transport", "part_id": "A1", "destination": "parking1"},
                              {"operation": "setup", "family": "B"}],
        "missing_rule": "Frozen setup returns insert A to its occupied home; baseline has no home-evacuation rule.",
        "baseline_source": "Runtime 004/candidates.py:673-759; cell.py:342-349,537-550",
    },
}


def make_manifest(family, mode, run_id):
    if family not in FAMILIES or mode not in ("baseline", "reference", "serve"):
        raise ValueError("Unknown development family/mode")
    return {"schema": "robot-codex-development-manifest-1.0", "stage": "development-only",
            "run_id": run_id, "family": family, "mode": mode, "seed": 173, "noise_seed": 13,
            "sim_cap_s": 45 if mode == "baseline" else 240,
            "wall_cap_s": 120 if mode == "baseline" else (900 if mode == "serve" else 420),
            "storage_cap_bytes": 200 * 1024 * 1024,
            "physics_dt_s": .002, "clock_mode": "wall-paced; physics continues independently of agent",
            "activation_policy": "frozen controller help request or explicit public station-fault waiting; no hidden trigger",
            "operator_only_fixture": copy.deepcopy(FAMILIES[family]),
            "limitations": ["Development fixture; not sampled performance evidence", "No collision safety certificate",
                            "Reference solution is protected operator evidence", "Agent process restart only; supervisor restart is not implemented"]}


def validate_manifest(value):
    if value.get("schema") != "robot-codex-development-manifest-1.0" or value.get("stage") != "development-only":
        raise ValueError("Development-only manifest required")
    expected = make_manifest(value["family"], value["mode"], value["run_id"])
    if value.get("operator_only_fixture") != expected["operator_only_fixture"]:
        raise ValueError("Fixture differs from implemented family; version rather than silently change it")
    serve = value["mode"] == "serve"
    for key, limit in (("sim_cap_s", 1800 if serve else 600), ("wall_cap_s", 1800),
                       ("storage_cap_bytes", (512 if serve else 200) * 1024 * 1024)):
        if type(value.get(key)) is not int or not 0 < value[key] <= limit:
            raise ValueError("Invalid bounded " + key)
    return value


def source_binding(runtime):
    runtime = Path(runtime)
    expected = json.loads((runtime.parent / "Evidence" / "prepared-artifacts" / "batch01-eval-r4-final" / "code.json").read_text(encoding="utf-8"))
    result = {}
    for record in expected["files"]:
        recorded_path = Path(record["path"])
        name = recorded_path.name
        # Every frozen Python source loaded through this runtime is checked.
        if name.endswith(".py") and recorded_path.parent.resolve() == runtime.resolve():
            path = runtime / name
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != record["sha256"]:
                raise ValueError("Frozen runtime source mismatch: " + name)
            result[name] = actual
    return result


def apply_initial_fixture(cell, manifest):
    """Protected initialization only, before episode time starts; never a recovery action."""
    import mujoco
    from cell import ZONES
    for placement in manifest["operator_only_fixture"]["placements"]:
        identity = placement["part_id"]
        joint = cell.model.joint("free_" + identity)
        q = int(joint.qposadr[0]); v = int(joint.dofadr[0])
        xy = ZONES[placement["zone"]]
        cell.data.qpos[q:q+7] = [xy[0], xy[1], .021, 1, 0, 0, 0]
        cell.data.qvel[v:v+6] = 0
    mujoco.mj_forward(cell.model, cell.data)


def write_manifests(directory):
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    written = []
    for family, code in (("misplaced-stock", "stock"), ("blocked-insert-home", "home")):
        for mode in ("baseline", "reference"):
            run_id = f"RCI001-{code}-{mode}-001"
            path = directory / (run_id + ".json")
            if path.exists():
                raise ValueError("Manifest already exists: " + str(path))
            path.write_text(json.dumps(make_manifest(family, mode, run_id), indent=2) + "\n", encoding="utf-8")
            written.append(str(path.resolve()))
    return written
