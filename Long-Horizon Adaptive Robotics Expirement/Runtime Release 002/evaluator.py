"""Independent protected-state outcome evaluator.

Candidate declarations, detections and private ledgers are never read. Tests use
synthetic protected snapshots, not robot experiments. The MuJoCo adapter reads
actual collision bounds, object velocities, contacts and machine histories.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import time


class EvaluationError(ValueError):
    pass


@dataclass(frozen=True)
class ScoringConfig:
    dwell_s: float = 0.5
    linear_speed_m_s: float = 0.05
    angular_speed_rad_s: float = 0.10
    arm_speed_rad_s: float = 0.02
    finger_speed_m_s: float = 0.01
    max_sample_gap_s: float = 0.20
    floor_z_m: float = -0.003
    scoring_rim_z_m: float = 0.08
    rest_top_z_m: float = 0.08
    boundary_tolerance_m: float = 1e-6
    contact_tolerance_m: float = 1e-5
    safe_guard_closed: bool = False
    safe_clamped: bool = False
    delivery_zones: tuple = ("tray1", "tray2", "tray3")
    parking_zones: tuple = ("parking1", "parking2")
    fixture_zone: str = "fixture"


def _number(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def _vector(value):
    return isinstance(value, (tuple, list)) and len(value) == 3 and all(_number(v) for v in value)


def _norm(value):
    return math.sqrt(sum(float(v) ** 2 for v in value))


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def box_bounds(center, rotation, half):
    """Exact world AABB of an oriented physical box, including every corner."""
    if not _vector(center) or not _vector(half) or any(v <= 0 for v in half):
        raise EvaluationError("Invalid collision-box geometry")
    if len(rotation) == 9:
        rotation = [rotation[i:i + 3] for i in (0, 3, 6)]
    if len(rotation) != 3 or any(not _vector(list(row)) for row in rotation):
        raise EvaluationError("Invalid collision-box rotation")
    extents = [sum(abs(float(rotation[i][j])) * half[j] for j in range(3)) for i in range(3)]
    return {"min": [center[i] - extents[i] for i in range(3)],
            "max": [center[i] + extents[i] for i in range(3)]}


def contains(obj, zone, tolerance=1e-6):
    """Centre AND full collision bounds must be inside all three dimensions."""
    return all(zone["min"][axis] - tolerance <= obj["position"][axis] <= zone["max"][axis] + tolerance
               and obj["bounds"]["min"][axis] >= zone["min"][axis] - tolerance
               and obj["bounds"]["max"][axis] <= zone["max"][axis] + tolerance for axis in range(3))


def overlaps(obj, zone, tolerance=1e-6):
    """Positive collision-volume overlap catches straddling tray/slot objects."""
    return all(min(obj["bounds"]["max"][axis], zone["max"][axis])
               - max(obj["bounds"]["min"][axis], zone["min"][axis]) > tolerance for axis in range(3))


class IndependentEvaluator:
    def __init__(self, config=None):
        self.config = config or ScoringConfig()
        if self.config.dwell_s <= 0 or self.config.max_sample_gap_s <= 0:
            raise EvaluationError("Positive dwell and sampling limits are required")
        self._last_time = None
        self._stable_since = None
        self._placement_since = {}
        self._order_hash = None
        self._last_violation = None
        self._adapter_cache = None
        self.first_success = None

    def reset(self):
        """Explicitly start a new world/episode; candidate restarts must not call it."""
        self._last_time = None
        self._stable_since = None
        self._placement_since.clear()
        self._order_hash = None
        self._last_violation = None
        self.first_success = None

    def invalidate_settling(self, sim_time, reason="physics-rate transient"):
        """Optional lightweight hook for between-snapshot contact/motion events.

        Call from protected physics monitoring whenever a settling requirement
        is violated between evaluator snapshots. This prevents a brief excursion
        from being hidden by a slower outcome polling rate.
        """
        if not _number(sim_time):
            raise EvaluationError("Invalid transient timestamp")
        self._stable_since = None
        self._placement_since.clear()
        self._last_violation = {"sim_time": float(sim_time), "reason": str(reason)}

    def _validate_snapshot(self, snapshot):
        if not isinstance(snapshot, dict) or not _number(snapshot.get("sim_time")):
            raise EvaluationError("Protected snapshot requires finite simulation time")
        objects, zones = snapshot.get("objects"), snapshot.get("zones")
        if not isinstance(objects, list) or not isinstance(zones, dict):
            raise EvaluationError("Protected objects and zones are required")
        ids = []
        for obj in objects:
            if not isinstance(obj, dict) or not isinstance(obj.get("id"), str):
                raise EvaluationError("Every object needs its protected identity")
            ids.append(obj["id"])
            if obj.get("kind") not in ("part", "insert", "tool"):
                raise EvaluationError("Unknown object kind")
            if not _vector(obj.get("position")) or not _vector(obj.get("linear_velocity")) or not _vector(obj.get("angular_velocity")):
                raise EvaluationError("Missing or nonfinite object pose/velocity")
            bounds = obj.get("bounds")
            if (not isinstance(bounds, dict) or not _vector(bounds.get("min")) or not _vector(bounds.get("max"))
                    or any(bounds["min"][i] >= bounds["max"][i] for i in range(3))):
                raise EvaluationError("Invalid full collision bounds")
            if type(obj.get("gripper_contact")) is not bool:
                raise EvaluationError("Exact gripper-contact state must be supplied")
        if len(set(ids)) != len(ids):
            raise EvaluationError("Duplicate protected object identities")
        for zone in zones.values():
            if (not isinstance(zone, dict) or not _vector(zone.get("min")) or not _vector(zone.get("max"))
                    or any(zone["min"][i] >= zone["max"][i] for i in range(3))):
                raise EvaluationError("Invalid scoring-zone bounds")
        required = set(self.config.delivery_zones) | set(self.config.parking_zones) | {self.config.fixture_zone}
        if not required.issubset(zones):
            raise EvaluationError("Required tray/fixture/parking regions are missing")
        for key in ("arm_velocity", "finger_velocity"):
            required_length = 7 if key == "arm_velocity" else 2
            if (not isinstance(snapshot.get(key), list) or len(snapshot[key]) != required_length
                    or not all(_number(v) for v in snapshot[key])):
                raise EvaluationError("Missing finite actuator velocity: " + key)
        if not isinstance(snapshot.get("station"), dict) or not isinstance(snapshot.get("pending"), dict):
            raise EvaluationError("Machine and pending-command state are required")
        if not isinstance(snapshot.get("return_locations"), dict):
            raise EvaluationError("Returnable-object resting locations must be declared")

    def _requirements(self, order):
        if not isinstance(order, dict) or "version" not in order or not isinstance(order.get("requirements"), list):
            raise EvaluationError("Current versioned order is required")
        result = []
        for index, raw in enumerate(order["requirements"]):
            if (not isinstance(raw, dict) or type(raw.get("count")) is not int or raw["count"] < 0
                    or raw.get("tray") not in self.config.delivery_zones
                    or not isinstance(raw.get("family"), str) or not isinstance(raw.get("recipe"), str)):
                raise EvaluationError("Invalid final-order requirement")
            max_rework = raw.get("max_rework_cycles", 0)
            if type(max_rework) is not int or not 0 <= max_rework <= 1:
                raise EvaluationError("Order must explicitly allow at most one rework cycle")
            ids = raw.get("part_ids")
            if ids is not None and (not isinstance(ids, list) or len(ids) != raw["count"]
                                    or len(set(ids)) != len(ids) or not all(isinstance(v, str) for v in ids)):
                raise EvaluationError("Explicit required part IDs must be distinct and match the count")
            result.append({**raw, "requirement_id": "R" + str(index + 1), "max_rework_cycles": max_rework})
        return result

    def _history(self, obj, sim_time):
        """Require actual accepted/completed history and current inspection linkage."""
        errors, cycles, inspections = [], obj.get("cycle_history"), obj.get("inspection_history")
        if not isinstance(cycles, list) or not cycles:
            return {"valid": False, "errors": ["missing accepted cycle history"], "completed": [], "passed": False}
        if not isinstance(inspections, list):
            inspections = []
            errors.append("missing inspection history")
        valid_inspections = []
        inspection_ids = set()
        for item in inspections:
            if (not isinstance(item, dict) or item.get("inspection_id") is None or item.get("part_id") != obj["id"]
                    or item.get("status") not in ("pass", "rework", "fail")
                    or (item.get("cycle_id") is None and item.get("status") != "fail")
                    or not _number(item.get("observed_at")) or item["observed_at"] > sim_time + 1e-6):
                errors.append("invalid inspection identity, time or cycle correlation")
                continue
            if item["inspection_id"] in inspection_ids:
                errors.append("duplicate inspection identity")
            inspection_ids.add(item["inspection_id"])
            valid_inspections.append(item)
        completed, cycle_ids = [], set()
        for cycle in cycles:
            if (not isinstance(cycle, dict) or cycle.get("cycle_id") is None or cycle.get("part_id") != obj["id"]
                    or cycle.get("accepted") is not True or not isinstance(cycle.get("recipe"), str)
                    or not _number(cycle.get("accepted_at")) or cycle["accepted_at"] > sim_time + 1e-6):
                errors.append("cycle lacks accepted identity, recipe or time")
                continue
            if cycle["cycle_id"] in cycle_ids:
                errors.append("duplicate cycle identity")
            cycle_ids.add(cycle["cycle_id"])
            if completed:
                previous = completed[-1]
                auth_id = cycle.get("rework_authorization_inspection_id")
                auth = next((i for i in valid_inspections if i["inspection_id"] == auth_id), None)
                if (not auth or auth["status"] != "rework" or auth["cycle_id"] != previous["cycle_id"]
                        or auth["observed_at"] < previous["completed_at"] or auth["observed_at"] > cycle["accepted_at"]):
                    errors.append("additional cycle lacks a preceding correlated rework authorization")
                if cycle["accepted_at"] < previous["completed_at"]:
                    errors.append("overlapping or reordered process cycles")
            if cycle.get("completed") is not True:
                if (cycle.get("status") == "failed" and _number(cycle.get("failed_at"))
                        and cycle["accepted_at"] <= cycle["failed_at"] <= sim_time + 1e-6):
                    continue  # Preserved failed attempts do not masquerade as completed work.
                errors.append("accepted cycle has no valid completion")
                continue
            if (not _number(cycle.get("completed_at")) or cycle["completed_at"] < cycle["accepted_at"]
                    or cycle["completed_at"] > sim_time + 1e-6):
                errors.append("invalid cycle-completion chronology")
                continue
            completed.append(cycle)
        if not completed:
            errors.append("no completed accepted cycle")
        last = completed[-1] if completed else None
        if type(obj.get("cycles")) is not int or obj["cycles"] != len(completed):
            errors.append("process counter and completed history disagree")
        if last and obj.get("recipe") != last["recipe"]:
            errors.append("recipe summary and latest process history disagree")
        latest = max(valid_inspections, key=lambda i: i["observed_at"]) if valid_inspections else None
        if latest and obj.get("inspection") != latest["status"]:
            errors.append("inspection summary and latest inspection history disagree")
        passed = bool(latest and last and latest["status"] == "pass" and latest["cycle_id"] == last["cycle_id"]
                      and latest["observed_at"] >= last["completed_at"] and obj.get("inspection") == "pass")
        return {"valid": not errors, "errors": errors, "completed": completed, "passed": passed,
                "latest_inspection": latest, "recipe": last["recipe"] if last else None, "accepted_cycle_ids": list(cycle_ids)}

    def evaluate_snapshot(self, snapshot, order, *, acceptance_open=False, wall_monotonic_s=None):
        """Evaluate one protected state and update dwell using simulation time.

        Snapshot fields are specified by ``snapshot_cell`` below. This method
        performs no environment mutation and never consults a candidate ledger.
        """
        self._validate_snapshot(snapshot)
        if wall_monotonic_s is not None and not _number(wall_monotonic_s):
            raise EvaluationError("Invalid protected snapshot wall clock")
        requirements = self._requirements(order)
        now, cfg = float(snapshot["sim_time"]), self.config
        if self._last_time is not None and now < self._last_time - 1e-9:
            raise EvaluationError("World clock moved backward; use a new evaluator for a new episode")
        gap_reset = self._last_time is not None and now - self._last_time > cfg.max_sample_gap_s + 1e-9
        if gap_reset:
            self.invalidate_settling(now, "outcome snapshot gap exceeds calibrated dwell coverage")
        self._last_time = now
        order_hash = hashlib.sha256(_canonical(order).encode()).hexdigest()
        if order_hash != self._order_hash:
            self._stable_since = None
            self._order_hash = order_hash
        objects, zones = snapshot["objects"], snapshot["zones"]
        parts = [o for o in objects if o["kind"] == "part"]
        by_id = {o["id"]: o for o in objects}
        violations = []

        def fail(code, detail, object_ids=None):
            violations.append({"code": code, "detail": detail, "object_ids": object_ids or []})

        slow, contained, touched = {}, {}, {}
        current_keys = set()
        for obj in objects:
            oid = obj["id"]
            slow[oid] = (_norm(obj["linear_velocity"]) <= cfg.linear_speed_m_s
                         and _norm(obj["angular_velocity"]) <= cfg.angular_speed_rad_s)
            contained[oid] = [z for z, geometry in zones.items() if contains(obj, geometry, cfg.boundary_tolerance_m)]
            touched[oid] = [z for z, geometry in zones.items() if overlaps(obj, geometry, cfg.boundary_tolerance_m)]
            if not slow[oid]:
                fail("object_moving", "movable object exceeds settled velocity limits", [oid])
            if obj["gripper_contact"]:
                fail("gripper_contact", "object retains exact contact with a gripper body", [oid])
            if obj["bounds"]["max"][2] > cfg.rest_top_z_m + cfg.boundary_tolerance_m:
                fail("object_not_resting", "object collision bounds exceed declared resting height", [oid])
            if obj["bounds"]["min"][2] < cfg.floor_z_m - cfg.boundary_tolerance_m:
                fail("object_below_floor", "object collision bounds penetrate below scoring floor tolerance", [oid])
            for zone in contained[oid]:
                key = oid, zone
                if slow[oid] and not obj["gripper_contact"]:
                    current_keys.add(key)
                    self._placement_since.setdefault(key, now)
        self._placement_since = {key: value for key, value in self._placement_since.items() if key in current_keys}

        parking = {}
        for zone in cfg.parking_zones:
            parking[zone] = [o["id"] for o in objects if zone in touched[o["id"]]]
            if len(parking[zone]) > 1:
                fail("parking_capacity", "single-capacity parking region contains overlapping occupancy", parking[zone])
        fixture_parts = [o["id"] for o in parts if cfg.fixture_zone in touched[o["id"]]]
        if fixture_parts:
            fail("fixture_not_empty", "a workpiece overlaps the process fixture", fixture_parts)
        fixture_inserts = [o["id"] for o in objects if o["kind"] == "insert" and cfg.fixture_zone in touched[o["id"]]]
        if len(fixture_inserts) > 1:
            fail("multiple_installed_inserts", "more than one insert occupies the fixture", fixture_inserts)
        for obj in objects:
            if obj["kind"] not in ("insert", "tool"):
                continue
            allowed = snapshot["return_locations"].get(obj["id"])
            if not isinstance(allowed, list) or not allowed or any(z not in zones for z in allowed):
                fail("undeclared_return_location", "returnable object has no valid resting-location specification", [obj["id"]])
            elif not any(z in contained[obj["id"]] for z in allowed):
                fail("returnable_not_home", "returnable object is outside every permitted resting region", [obj["id"]])

        histories = {o["id"]: self._history(o, now) for o in parts}
        cycle_owners = {}
        for obj in parts:
            for cycle_id in histories[obj["id"]].get("accepted_cycle_ids", []):
                if cycle_id in cycle_owners and cycle_owners[cycle_id] != obj["id"]:
                    fail("shared_cycle_identity", "one machine cycle is attributed to distinct parts", [cycle_owners[cycle_id], obj["id"]])
                cycle_owners[cycle_id] = obj["id"]
        allocated, accepted_raw, accepted, unmet = set(), {}, {}, []
        requirement_details = []
        for req in requirements:
            tray = req["tray"]
            accepted_raw.setdefault(tray, [])
            accepted.setdefault(tray, [])
            candidates = []
            for obj in parts:
                oid, history = obj["id"], histories[obj["id"]]
                if (oid in allocated or obj.get("family") != req["family"] or tray not in contained[oid]
                        or not slow[oid] or obj["gripper_contact"] or not history["valid"] or not history["passed"]
                        or history.get("recipe") != req["recipe"]
                        or len(history["completed"]) > 1 + req["max_rework_cycles"]
                        or (req.get("part_ids") is not None and oid not in req["part_ids"])):
                    continue
                candidates.append(oid)
            chosen = sorted(candidates)[:req["count"]]
            allocated.update(chosen)
            accepted_raw[tray].extend(chosen)
            settled = [oid for oid in chosen if now - self._placement_since.get((oid, tray), now) >= cfg.dwell_s - 1e-9]
            accepted[tray].extend(settled)
            if len(chosen) != req["count"]:
                fail("quantity_or_qualification_mismatch", "current requirement lacks enough distinct physically qualified parts: " + req["requirement_id"])
            unmet.append({"requirement_id": req["requirement_id"], "family": req["family"], "recipe": req["recipe"], "tray": tray,
                          "required": req["count"], "accepted_settled": len(settled), "unmet": req["count"] - len(settled)})
            requirement_details.append({"requirement_id": req["requirement_id"], "qualified_ids": chosen, "settled_ids": settled})
        extras = []
        for obj in objects:
            tray_touches = [z for z in cfg.delivery_zones if z in touched[obj["id"]]]
            if not tray_touches:
                continue
            valid_tray = next((z for z, ids in accepted_raw.items() if obj["id"] in ids), None)
            if obj["id"] not in allocated or tray_touches != [valid_tray]:
                extras.append(obj["id"])
                fail("extra_or_invalid_delivery_occupancy", "object overlaps a delivery tray without one matching qualified allocation", [obj["id"]])
                if obj["kind"] == "part":
                    for error in histories[obj["id"]]["errors"]:
                        fail("invalid_process_evidence", error, [obj["id"]])
        station = snapshot["station"]
        if station.get("busy") is not False or station.get("ready") is not True or station.get("fault") is not False:
            fail("station_not_safely_idle", "machine must be idle, ready and free of an active fault")
        if station.get("guard_closed") is not cfg.safe_guard_closed or station.get("clamped") is not cfg.safe_clamped:
            fail("station_rest_state", "guard/clamp state differs from the declared safe terminal state")
        expected_pending = ("active_request", "queued_motion", "active_segment", "machine_cycle", "inspection")
        if any(type(snapshot["pending"].get(key)) is not bool for key in expected_pending):
            fail("pending_state_unknown", "pending action/timer fields must be explicit booleans")
        elif any(snapshot["pending"][key] for key in expected_pending):
            fail("outstanding_work", "active, queued or delayed execution remains outstanding")
        if max(abs(v) for v in snapshot["arm_velocity"]) > cfg.arm_speed_rad_s:
            fail("arm_not_settled", "arm joint velocity exceeds terminal threshold")
        if max(abs(v) for v in snapshot["finger_velocity"]) > cfg.finger_speed_m_s:
            fail("gripper_not_settled", "gripper velocity exceeds terminal threshold")
        if order.get("closed") is not True:
            fail("order_stream_open", "current order is not closed")
        if acceptance_open is not True:
            fail("required_opportunities_unresolved", "manifest order/intervention opportunities have not all resolved")
        immediate_ready = not violations
        if immediate_ready:
            if self._stable_since is None:
                self._stable_since = now
        else:
            self._stable_since = None
        dwell = now - self._stable_since if self._stable_since is not None else 0.0
        success = immediate_ready and dwell >= cfg.dwell_s - 1e-9
        reasons = [v["code"] + ": " + v["detail"] for v in violations]
        if immediate_ready and not success:
            reasons.append("terminal_settling: otherwise valid state has not yet satisfied the dwell")
        accepted_count = sum(map(len, accepted.values()))
        outcome = {
            "schema_version": "robot-independent-outcome-1.0", "success": success, "immediate_ready": immediate_ready,
            "order_version": order["version"], "sim_time": now, "accepted": accepted, "accepted_count": accepted_count,
            "qualified_before_dwell": accepted_raw, "reasons": reasons, "violations": violations,
            "requirements": requirement_details, "parking_occupancy": parking,
            "settling": {"required_s": cfg.dwell_s, "observed_s": dwell, "stable_since": self._stable_since,
                         "sample_gap_reset": gap_reset, "last_external_invalidation": self._last_violation,
                         "coverage": "protected snapshots; physics-monitor invalidation hook covers detected inter-snapshot transients"},
            "partial": {
                "accepted_count": accepted_count, "unmet_quantities": unmet,
                "processed_uninspected_ids": [o["id"] for o in parts if histories[o["id"]]["valid"] and not histories[o["id"]]["passed"]
                                               and not histories[o["id"]].get("latest_inspection")],
                "rework_required_ids": [o["id"] for o in parts if o.get("inspection") == "rework"],
                "quarantined_ids": [o["id"] for o in parts if "quarantine" in contained[o["id"]]],
                "extra_delivery_ids": extras,
            },
            "calibration_assumptions": {
                "scoring_floor_z_m": cfg.floor_z_m, "scoring_rim_z_m": cfg.scoring_rim_z_m,
                "rim_interpretation": "declared virtual scoring plane; current flat tray markers are not physical walls",
                "linear_speed_m_s": cfg.linear_speed_m_s, "angular_speed_rad_s": cfg.angular_speed_rad_s,
                "arm_speed_rad_s": cfg.arm_speed_rad_s, "finger_speed_m_s": cfg.finger_speed_m_s,
                "maximum_snapshot_gap_s": cfg.max_sample_gap_s,
            },
        }
        if success and self.first_success is None:
            # Retain the first sampled threshold crossing, not an interpolated
            # stable_since+dwell timestamp or a later supervisor poll time.
            self.first_success = {"sim_time_s": now, "wall_monotonic_s": wall_monotonic_s,
                "order_version": order["version"], "stable_since_sim_s": self._stable_since,
                "required_dwell_s": cfg.dwell_s, "snapshot_sha256": hashlib.sha256(_canonical(snapshot).encode()).hexdigest(),
                "protected_snapshot": json.loads(_canonical(snapshot)), "outcome": json.loads(_canonical(outcome)),
                "clock_scope": "protected state captured at evaluator call; no physical sub-tick interpolation"}
        outcome["first_success"] = ({k: v for k, v in self.first_success.items() if k not in ("protected_snapshot", "outcome")}
                                    if self.first_success is not None else None)
        return outcome

    def snapshot_cell(self, cell, *, zones, zone_half):
        """Read the current Cell privately. Does not import Cell or mutate physics.

        ``zones`` is Cell's protected/public static centre mapping; ``zone_half``
        provides XY half-extents. Physical boxes are read from MuJoCo geom state,
        not registry half-sizes or candidate detections. Unsupported collision
        geometry fails explicitly until its bounds adapter is implemented.
        """
        import mujoco
        import numpy as np
        cfg, model, data = self.config, cell.model, cell.data
        identity = id(model)
        if self._adapter_cache is None or self._adapter_cache["model_identity"] != identity:
            object_ids = {}
            geometries = {}
            for name in cell.registry:
                body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
                if body < 0:
                    raise EvaluationError("Registered object lacks a physical body: " + name)
                object_ids[name] = body
                geometries[name] = [g for g in range(model.ngeom) if int(model.geom_bodyid[g]) == body
                                    and (int(model.geom_contype[g]) or int(model.geom_conaffinity[g]))]
                if not geometries[name]:
                    raise EvaluationError("Registered object lacks collision geometry: " + name)
            gripper_root = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "hand")
            if gripper_root < 0:
                raise EvaluationError("Panda gripper body was not found")
            gripper_bodies = set()
            for body in range(model.nbody):
                current = body
                while current:
                    if current == gripper_root:
                        gripper_bodies.add(body)
                        break
                    current = int(model.body_parentid[current])
            self._adapter_cache = {"model_identity": identity, "bodies": object_ids, "geometries": geometries,
                                   "gripper_bodies": gripper_bodies}
        cache = self._adapter_cache
        contacts = set()
        object_bodies = set(cache["bodies"].values())
        for index in range(data.ncon):
            contact = data.contact[index]
            if float(contact.dist) > cfg.contact_tolerance_m:
                continue
            a, b = int(model.geom_bodyid[contact.geom1]), int(model.geom_bodyid[contact.geom2])
            if a in object_bodies and b in cache["gripper_bodies"]:
                contacts.add(a)
            if b in object_bodies and a in cache["gripper_bodies"]:
                contacts.add(b)
        objects = []
        for name, tag in cell.registry.items():
            body = cache["bodies"][name]
            bounds = []
            for geom in cache["geometries"][name]:
                if int(model.geom_type[geom]) != int(mujoco.mjtGeom.mjGEOM_BOX):
                    raise EvaluationError("Unsupported non-box object collision geometry: " + name)
                bounds.append(box_bounds(data.geom_xpos[geom].tolist(), data.geom_xmat[geom].tolist(), model.geom_size[geom].tolist()))
            velocity = np.zeros(6)
            mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_BODY, body, velocity, 0)
            truth = cell.truth.get(name, {})
            objects.append({
                "id": name, "kind": tag["kind"], "family": tag.get("family"), "position": data.xpos[body].tolist(),
                "bounds": {"min": [min(b["min"][i] for b in bounds) for i in range(3)],
                           "max": [max(b["max"][i] for b in bounds) for i in range(3)]},
                "angular_velocity": velocity[:3].tolist(), "linear_velocity": velocity[3:].tolist(),
                "gripper_contact": body in contacts, "recipe": truth.get("recipe"), "cycles": truth.get("cycles"),
                "inspection": truth.get("inspection"), "cycle_history": truth.get("cycle_history"),
                "inspection_history": truth.get("inspection_history"),
            })
        regions = {name: {"min": [float(center[0] - zone_half(name)[0]), float(center[1] - zone_half(name)[1]), cfg.floor_z_m],
                          "max": [float(center[0] + zone_half(name)[0]), float(center[1] + zone_half(name)[1]), cfg.scoring_rim_z_m]}
                   for name, center in zones.items()}
        return_locations = {}
        for name, tag in cell.registry.items():
            if tag["kind"] == "insert":
                return_locations[name] = [cfg.fixture_zone, "insert_home_" + tag["family"]]
            elif tag["kind"] == "tool":
                return_locations[name] = list(getattr(cell, "tool_rest_locations", {}).get(name, []))
        return {
            "sim_time": float(data.time), "objects": objects, "zones": regions, "station": dict(cell.station),
            "arm_velocity": data.qvel[:7].tolist(), "finger_velocity": data.qvel[7:9].tolist(),
            "pending": {"active_request": cell.active_request is not None, "queued_motion": bool(cell.motion),
                        "active_segment": cell.segment is not None, "machine_cycle": cell.cycle is not None,
                        "inspection": cell.inspection_due is not None},
            "return_locations": return_locations,
        }

    def evaluate_cell(self, cell, order, *, zones, zone_half, acceptance_open=False):
        snapshot = self.snapshot_cell(cell, zones=zones, zone_half=zone_half)
        captured_wall = time.perf_counter()
        return self.evaluate_snapshot(snapshot, order, acceptance_open=acceptance_open,
                                      wall_monotonic_s=captured_wall)
