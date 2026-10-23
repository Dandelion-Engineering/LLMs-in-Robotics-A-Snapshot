"""Candidate-side policies over public packets only.

This module contains no simulator, model substitute, oracle, or evaluator API.
The supervisor performs real inference for model requests and executes actions.
Both persistence conditions use these same policies; the supervisor removes the
episode directory at a no-persistence restart. Unit fixtures are not experiments.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import uuid


KINDS = ("A1", "A2", "A3", "baseline")
ZONES = ("raw", "fixture", "parking1", "parking2", "inspection", "tray1", "tray2", "tray3", "quarantine")
OPERATIONS = ("transport", "recover_held", "setup", "cycle", "inspect", "observe", "wait", "done", "help")
GUARDS = ("always", "visible", "at_zone", "station_idle", "insert_is", "processed", "inspection_is", "order_is")
MAX_AGE_S = 1.5
MAX_STEPS = 8
MAX_FAILURES = 3
MAX_MODEL_FAILURES = 3
MAX_RECENT_RESOLUTIONS = 8
ACTION_TIMEOUT_S = 45.0
OPEN_GRIPPER_WIDTH_M = 0.065


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _finite(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def _reject_constant(value):
    raise ValueError("Nonfinite JSON value: " + value)


class StateCorruptionError(RuntimeError):
    """A durable checkpoint cannot be trusted; fail visibly rather than erase it."""


def _action_schema():
    # Each operation has its own required arguments. The first physical pilot
    # exposed syntactically permitted but unusable field omissions; a grammar
    # should express the actual API, not leave those omissions to retries.
    fields={"part_id":{"type":"string"},"destination":{"type":"string","enum":list(ZONES)},
            "family":{"type":"string","enum":["A","B"]},"recipe":{"type":"string"}}
    arguments={"transport":["part_id","destination"],"recover_held":["destination"],"setup":["family"],
               "cycle":["part_id","recipe"],"inspect":["part_id"],
               "observe":[],"wait":[],"done":[],"help":[]}
    branches=[]
    for operation,required in arguments.items():
        properties={"operation":{"const":operation},"order_version":{"type":["string","integer"]},
                    "reason":{"type":"string","maxLength":240}}
        properties.update({name:fields[name] for name in required})
        if operation=='observe':properties['clear_view']={'type':'boolean'}
        branches.append({"type":"object","additionalProperties":False,"properties":properties,
                         "required":["operation",*required]})
    return {"oneOf":branches}


def _guard_schema():
    fields={'part_id':{'type':'string'},'zone':{'type':'string','enum':list(ZONES)},
            'family':{'type':'string','enum':['A','B']},
            'status':{'type':'string','enum':['pass','rework','fail']},
            'order_version':{'type':['string','integer']}}
    arguments={'always':[],'visible':['part_id'],'at_zone':['part_id','zone'],
               'station_idle':[],'insert_is':['family'],'processed':['part_id'],
               'inspection_is':['part_id','status'],'order_is':['order_version']}
    return {'oneOf':[{'type':'object','additionalProperties':False,
        'properties':{'predicate':{'const':predicate},**{name:fields[name] for name in args}},
        'required':['predicate',*args]} for predicate,args in arguments.items()]}


OBJECTIVE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "clearance": {"type": "number", "minimum": 0.08, "maximum": 0.25},
        "speed_scale": {"type": "number", "minimum": 0.3, "maximum": 1.0},
        "approach": {"type": "string", "enum": ["vertical"]},
        "avoid_zones": {"type": "array", "items": {"type": "string", "enum": list(ZONES)}, "maxItems": 8, "uniqueItems": True},
    }, "required": ["clearance", "speed_scale", "approach", "avoid_zones"],
}


class Candidate:
    """One candidate process incarnation, with one outstanding authority.

    Public methods: step(packet), accept_model(text), accept_feedback(dict),
    drain_events(). Returned actions already contain request/incarnation IDs.
    Feedback schema: request_id, status, optional cycle_id. Inspection responses
    must arrive in packets with part_id, status, inspection_id. A cycle_id is
    public transport correlation, not proof that the cycle physically finished.
    """

    def __init__(self, kind: str, episode_dir: Path, persistent: bool):
        if kind not in KINDS:
            raise ValueError("Unknown candidate kind")
        self.kind, self.episode_dir, self.persistent = kind, Path(episode_dir), bool(persistent)
        self.episode_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.episode_dir / "candidate-state.json"
        self._events = []
        self._packet = None
        self._visible = {}
        self._model_context = None
        self._queued = None
        self._guard_waits = 0
        self._idle_steps = 0
        self._last_saved_hash = None
        self.state = {
            "version": 1, "kind": kind, "run_id": None, "order": None, "parts": {},
            "pending": None, "program": None, "last_error": None, "model_failures": 0,
            "failure_counts": {}, "halted": False, "last_inspection_id": None,
            "fixture_belief": None, "recent_resolutions": [],
            "received_human_answer_ids": [],
        }
        if self.state_path.exists():
            raw = self.state_path.read_bytes()
            self._event("context_read", path=self.state_path.name, sha256=hashlib.sha256(raw).hexdigest(),
                        byte_count=len(raw), content_utf8=raw.decode("utf-8", errors="replace"))
            try:
                envelope = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
                state = envelope["state"]
                if envelope["sha256"] != _digest(state) or state["version"] != 1 or state["kind"] != kind:
                    raise ValueError("checkpoint hash, version or candidate mismatch")
                self.state = state
            except (ValueError, KeyError, TypeError, UnicodeError) as exc:
                raise StateCorruptionError("Invalid checkpoint retained at " + str(self.state_path)) from exc
            self._last_saved_hash = _digest(self.state)
            self._event("restart_loaded", pending_request_id=(self.state.get("pending") or {}).get("action", {}).get("request_id"))
        # Older checkpoints lack this optional bounded history; do not invent it.
        recent = self.state.setdefault("recent_resolutions", [])
        if not isinstance(recent, list) or len(recent) > MAX_RECENT_RESOLUTIONS:
            raise StateCorruptionError("Invalid bounded recent-resolution history")
        self._persist()

    def _event(self, event_type, **fields):
        self._events.append({"type": event_type, "candidate": self.kind, **copy.deepcopy(fields)})

    def drain_events(self):
        events, self._events = self._events, []
        return events

    def _persist(self):
        state_hash = _digest(self.state)
        if state_hash == self._last_saved_hash:
            return
        raw = (_json({"sha256": state_hash, "state": self.state}) + "\n").encode("utf-8")
        if len(raw)>8*1024*1024:
            raise StateCorruptionError('Consequential checkpoint exceeds the shared 8 MiB per-checkpoint ceiling')
        temp = self.episode_dir / (".candidate-state-" + uuid.uuid4().hex + ".tmp")
        with temp.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, self.state_path)
        self._last_saved_hash = state_hash
        self._event("context_write", path=self.state_path.name, sha256=hashlib.sha256(raw).hexdigest(),
                    byte_count=len(raw), content_utf8=raw.decode("utf-8"), state_sha256=state_hash,
                    durability="file fsync plus atomic replace; parent-directory fsync not assumed")

    def _part(self, part_id):
        part = self.state["parts"].setdefault(part_id, {})
        for key, value in {"family": None, "cycle": None, "inspection": None, "reworks": 0,
                           "last_seen": None, "eligibility_inference": None, "inspection_attempts": 0}.items():
            part.setdefault(key, value)
        return part

    def _fresh(self, part_id):
        return self._visible.get(part_id)

    def _station(self):
        return self._packet.get("station", {})

    def _fixture_family(self):
        observed = self._station().get("fixture_insert")
        if observed in ("A", "B"):
            return observed
        # A covered tag is unknown to the current image, not evidence that the
        # last observed insert vanished. This is a fallible candidate belief;
        # physical process interlocks retain final admission authority.
        return (self.state.get("fixture_belief") or {}).get("family")

    def _requirement(self, family, recipe=None):
        return [r for r in self._packet["order"]["requirements"]
                if r["family"] == family and (recipe is None or r["recipe"] == recipe)]

    def _proof(self, part_id):
        part = self.state["parts"].get(part_id, {})
        cycle, inspection = part.get("cycle"), part.get("inspection")
        direct = bool(cycle and cycle.get("complete") and inspection and inspection.get("status") == "pass"
                      and inspection.get("cycle_id") == cycle.get("cycle_id"))
        inference = part.get("eligibility_inference")
        reconstructed = bool(inference and inspection and inspection.get("status") == "pass"
                             and inspection.get("inspection_id") == inference.get("inspection_id"))
        return direct or reconstructed

    def _recipe(self, part_id):
        part = self.state["parts"].get(part_id, {})
        return (part.get("cycle") or part.get("eligibility_inference") or {}).get("recipe")

    def _public_recipe(self, family):
        contract = self._packet.get("process_contract") or {}
        if contract.get("processed_mark_requires_eligible_cycle") is not True:
            return None
        recipe = (contract.get("family_recipes") or {}).get(family)
        return recipe if isinstance(recipe, str) and recipe else None

    def _infer_current_eligibility(self, part_id, inspection):
        """Reconstruct current eligibility, never fabricate historical cycles.

        This is available identically in both conditions and relies on an
        explicit frozen public invariant plus a newly requested pad response.
        A processed mark alone, or the current order's recipe, is insufficient.
        """
        part, item = self._part(part_id), self._fresh(part_id)
        pending = self.state.get("pending")
        recipe = self._public_recipe(part.get("family"))
        if (not recipe or not item or item["zone"] != "inspection" or item.get("visible_mark") != "processed"
                or inspection["status"] != "pass" or not pending
                or pending["action"]["operation"] != "inspect" or pending["action"]["part_id"] != part_id
                or str(inspection["inspection_id"]) == pending.get("before_inspection_id")):
            return
        if part.get("cycle") and part["cycle"].get("complete"):
            return
        part["eligibility_inference"] = {
            "recipe": recipe, "family": part["family"], "inspection_id": inspection["inspection_id"],
            "sequence": self._packet["sequence"], "sim_time": self._packet["sim_time"],
            "basis": "explicit public family recipe interlock, fresh processed mark, newly requested passing pad inspection",
            "historical_cycle_id": None,
        }
        self._event("inferred_current_eligibility", part_id=part_id, inference=part["eligibility_inference"],
                    recovered_history=False)

    def _ingest(self, packet):
        for field in ("run_id", "incarnation", "sequence", "sim_time", "order", "detections", "station", "gripper"):
            if field not in packet:
                raise ValueError("Missing public packet field: " + field)
        if not _finite(packet["sim_time"]):
            raise ValueError("Invalid simulation time")
        if self.state["run_id"] is not None and packet["run_id"] != self.state["run_id"]:
            raise ValueError("Episode directory belongs to another run")
        self._packet = copy.deepcopy(packet)
        self._visible = {}
        self.state["run_id"] = packet["run_id"]
        old_order = self.state["order"]
        if old_order is not None and old_order["version"] != packet["order"]["version"]:
            self._event("order_changed", old=old_order["version"], new=packet["order"]["version"])
            self.state["program"] = None
            self._queued = None
            # Keep pending dispatch and its original order version: a changed
            # order does not retroactively undo a physical command.
        self.state["order"] = copy.deepcopy(packet["order"])
        inserted = packet["station"].get("fixture_insert")
        if inserted in ("A", "B"):
            self.state["fixture_belief"] = {
                "family": inserted, "sequence": packet["sequence"], "sim_time": packet["sim_time"],
                "basis": "public observed insert tag", "current_visibility_required_for_certainty": True,
            }
        for item in packet["detections"]:
            part_id = item.get("id")
            age = item.get("age_s")
            if not isinstance(part_id, str) or not _finite(age) or age < 0 or age > MAX_AGE_S:
                continue
            if item.get("zone") not in ZONES or item.get("family") not in ("A", "B"):
                continue
            if item.get("kind", "part") != "part":
                continue  # Public insert tags are not workpieces or buffer occupants.
            pos = item.get("pos")
            if not isinstance(pos, list) or len(pos) != 3 or not all(_finite(v) for v in pos):
                continue
            self._visible[part_id] = item
            record = self._part(part_id)
            record["family"] = item["family"]
            record["last_seen"] = {"zone": item["zone"], "pos": pos, "visible_mark": item.get("visible_mark", "unknown"),
                                   "sequence": packet["sequence"], "sim_time": packet["sim_time"], "age_s": age}
        # Inspection is a public instrument response, not a private truth field.
        inspection = packet.get("inspection")
        if inspection and inspection.get("inspection_id") is not None and inspection.get("status") in ("pass", "rework", "fail"):
            signature = str(inspection["inspection_id"])
            part_id = inspection.get("part_id", inspection.get("id"))
            if signature != self.state["last_inspection_id"] and isinstance(part_id, str):
                part = self._part(part_id)
                cycle = part.get("cycle")
                part["inspection"] = {
                    "inspection_id": inspection["inspection_id"], "status": inspection["status"],
                    "cycle_id": cycle["cycle_id"] if cycle and cycle.get("complete") else None,
                    "sequence": packet["sequence"], "sim_time": packet["sim_time"],
                }
                self.state["last_inspection_id"] = signature
                self._event("public_inspection_observed", part_id=part_id, evidence=part["inspection"])
                self._infer_current_eligibility(part_id, inspection)
        last_feedback = packet.get("last_feedback")
        if last_feedback and last_feedback.get("request_id"):
            self.accept_feedback(last_feedback)
        received = self.state.setdefault("received_human_answer_ids", [])
        for answer in packet.get("human_answers", []):
            answer_id = answer.get("answer_id")
            if not isinstance(answer_id, str) or answer_id in received:
                continue
            received.append(answer_id)
            self._visibility_answer(answer)
            self.state["halted"] = False
            # A newly received public answer starts an assisted attempt round.
            # Physical failure counts, pending actions and process provenance
            # remain intact; reconciliation still uses this fresh packet.
            self.state["model_failures"] = 0
            self.state["program"] = None
            self._queued = None
            self._idle_steps = 0
            self._guard_waits = 0
            self._event("public_human_answer_received", answer=answer,
                        pending_request_id=(self.state.get("pending") or {}).get("action", {}).get("request_id"),
                        recovered_history=False)

    def _finish_pending(self, success, reason):
        pending = self.state["pending"]
        if not pending:
            return
        action = pending["action"]
        self._event("candidate_action_resolution", request_id=action["request_id"], operation=action["operation"],
                    resolved=bool(success), reason=reason, sequence=self._packet["sequence"],
                    sim_time=self._packet["sim_time"], grading_authority=False)
        # Retain the candidate's resolution and its public basis, never grading truth.
        # Only this existing resolution path appends; a receipt alone is insufficient.
        summary = {
            "request_id": action["request_id"],
            "action": {key: copy.deepcopy(action[key]) for key in
                       ("operation", "part_id", "destination", "family", "recipe",
                        "order_version", "incarnation", "observation_sequence") if key in action},
            "candidate_resolved": bool(success), "reason": reason,
            "resolution_sequence": self._packet["sequence"],
            "resolution_sim_time": self._packet["sim_time"],
            "resolution_incarnation": self._packet["incarnation"],
            "public_feedback": {key: copy.deepcopy(pending["feedback"][key]) for key in
                                ("request_id", "status", "reason", "cycle_id", "sim_time")
                                if key in (pending.get("feedback") or {})},
            "grading_authority": False,
            "scope": "candidate resolution from public evidence; not independent task success",
        }
        recent = self.state["recent_resolutions"]
        recent.append(summary)
        del recent[:-MAX_RECENT_RESOLUTIONS]
        signature = self._action_signature(action)
        if success:
            self.state["failure_counts"].pop(signature, None)
            self.state.pop("visibility_reacquisition", None)
            self._idle_steps = 0
            node = pending.get("program_node")
            program = self.state.get("program")
            if node is not None and program and program["id"] == pending.get("program_id"):
                program["completed"].append(node)
        else:
            self.state["failure_counts"][signature] = self.state["failure_counts"].get(signature, 0) + 1
            self.state["last_error"] = reason
            self.state["program"] = None
        self.state["pending"] = None

    def _reconcile(self):
        pending = self.state["pending"]
        if not pending:
            return
        action, station = pending["action"], self._station()
        op, part_id = action["operation"], action.get("part_id")
        feedback = pending.get("feedback") or {}
        # The same gateway receipt may be attached to several packets.
        failure = feedback.get("status") in ("rejected", "failed", "error", "cancelled", "expired", "timed_out")
        if failure:
            self._finish_pending(False, "gateway reported " + feedback["status"])
            return
        detection = self._fresh(part_id)
        is_new = (self._packet["incarnation"] != action["incarnation"]
                  or self._packet["sequence"] != pending["issued_sequence"])
        if not is_new:
            return
        if op == "transport" and detection and detection["zone"] == action["destination"]:
            width = self._packet["gripper"].get("width")
            if (self._packet["gripper"].get("holding_visible_id") != part_id
                    and _finite(width) and width >= OPEN_GRIPPER_WIDTH_M):
                self._finish_pending(True, "fresh visible destination, measured open gripper and no visible holding of that part")
                return
        elif op == "setup" and station.get("fixture_insert") == action["family"] and not station.get("busy"):
            self._finish_pending(True, "public fixture-insert state matches requested setup")
            return
        elif op == "cycle":
            cycle_id = pending.get("cycle_id")
            if cycle_id is None and feedback.get("cycle_id") is not None:
                pending["cycle_id"] = cycle_id = feedback["cycle_id"]
            # A public current-cycle transition can recover an unacknowledged
            # dispatch only with the same observed fixture part and retained
            # intent. There is one candidate command authority.
            if (cycle_id is None and station.get("cycle_id") is not None
                    and station.get("cycle_id") != pending.get("before_cycle_id")
                    and station.get("occupied_visible_id") == part_id):
                pending["cycle_id"] = cycle_id = station["cycle_id"]
                self._event("cycle_correlation_inferred", request_id=action["request_id"], cycle_id=cycle_id,
                            evidence="retained intent, new public cycle and same observed fixture part; one authority")
            if cycle_id is not None and station.get("completed_cycle_id") == cycle_id and not station.get("busy"):
                part = self._part(part_id)
                previous = part.get("cycle")
                if previous and previous.get("complete") and previous.get("cycle_id") != cycle_id:
                    part["reworks"] += 1
                part["cycle"] = {"cycle_id": cycle_id, "recipe": action["recipe"], "complete": True,
                                 "request_id": action["request_id"], "sequence": self._packet["sequence"],
                                 "sim_time": self._packet["sim_time"]}
                part["inspection"] = None
                part["eligibility_inference"] = None
                part["inspection_attempts"] = 0
                self._finish_pending(True, "correlated public cycle completion")
                return
        elif op == "inspect":
            inspection = self._packet.get("inspection") or {}
            if (inspection.get("part_id", inspection.get("id")) == part_id
                    and inspection.get("inspection_id") is not None
                    and str(inspection["inspection_id"]) != pending.get("before_inspection_id")
                    and inspection.get("status") in ("pass", "rework", "fail")):
                self._finish_pending(True, "new public inspection response for requested part")
                return
        elapsed = self._packet["sim_time"] - pending["issued_time"]
        if elapsed > ACTION_TIMEOUT_S:
            # No receipt or visibility is not proof of failure. Preserve the
            # unresolved record and stop before another consequential action.
            pending["unresolved_timeout"] = True
            self.state["last_error"] = "outcome unresolved after action deadline; do not replay"
        elif (op == "transport" and detection
              and (feedback.get("status") in ("completed", "succeeded", "terminal", "done")
                   or (self._packet["incarnation"] != action["incarnation"] and elapsed > 2.0))):
            pending["mismatch_observations"] = pending.get("mismatch_observations", 0) + 1
            if pending["mismatch_observations"] >= 3:
                self._finish_pending(False, "requested transport outcome absent in three fresh observations after terminal feedback or old-incarnation expiry")

    def accept_feedback(self, feedback: dict):
        if not isinstance(feedback, dict):
            raise ValueError("Feedback must be an object")
        recovery=self.state.get('recovery_pending')
        if recovery and feedback.get('request_id')==recovery['request_id']:
            recovery['feedback']=copy.deepcopy(feedback)
            self._event('recovery_feedback',feedback=feedback,physical_success_inferred=False)
            self._persist()
            return
        pending = self.state.get("pending")
        if not pending or feedback.get("request_id") != pending["action"]["request_id"]:
            self._event("uncorrelated_feedback", feedback=feedback)
            return
        if pending.get("feedback") == feedback:
            return
        pending["feedback"] = copy.deepcopy(feedback)
        if pending["action"]["operation"] == "cycle" and feedback.get("cycle_id") is not None:
            pending["cycle_id"] = feedback["cycle_id"]
        self._event("transport_feedback", feedback=feedback, physical_success_inferred=False)
        self._persist()

    def _action_signature(self, action):
        return _json({k: action.get(k) for k in ("operation", "part_id", "destination", "family", "recipe")})

    def _occupied(self, zone, except_part=None):
        return any(d["zone"] == zone and pid != except_part for pid, d in self._visible.items())

    def _syntax_action(self, action):
        if not isinstance(action, dict):
            return "action must be an object"
        allowed = {"operation", "part_id", "destination", "family", "recipe", "order_version", "reason", "clear_view"}
        if set(action) - allowed:
            return "unknown action fields"
        op = action.get("operation")
        if op not in OPERATIONS:
            return "unknown operation"
        if 'clear_view' in action and (op!='observe' or type(action['clear_view']) is not bool):
            return 'clear_view is a Boolean observation option'
        if op in ("transport", "cycle", "inspect") and not isinstance(action.get("part_id"), str):
            return "operation requires part_id"
        if op == "transport" and action.get("destination") not in ZONES:
            return "transport requires an allowed destination"
        if op == 'recover_held' and action.get('destination') not in ('parking1','parking2','inspection','quarantine'):
            return 'held recovery requires an allowed observation pad'
        if op == "setup" and action.get("family") not in ("A", "B"):
            return "setup requires family A or B"
        if op == "cycle" and (not isinstance(action.get("recipe"), str) or not action["recipe"]):
            return "cycle requires recipe"
        return None

    def _validate(self, action):
        syntax = self._syntax_action({k: v for k, v in action.items() if k != "objective"})
        if syntax:
            return syntax
        op = action["operation"]
        if action.get("order_version", self._packet["order"]["version"]) != self._packet["order"]["version"]:
            return "proposal references an obsolete order"
        if self.state["failure_counts"].get(self._action_signature(action), 0) >= MAX_FAILURES:
            return "bounded attempt limit reached"
        if op == "done":
            return None if self._complete() else "completion is not supported by current public evidence"
        if op=='observe' and action.get('clear_view') and (self._packet['gripper'].get('width',0)<OPEN_GRIPPER_WIDTH_M or self._packet['gripper'].get('holding_visible_id')):
            return 'clear-view retreat requires visibly empty open jaws'
        if op in ("observe", "wait", "help"):
            return None
        station = self._station()
        if op == 'recover_held':
            if self._packet['gripper'].get('width',.08)>=OPEN_GRIPPER_WIDTH_M:
                return 'held recovery requires non-open measured jaws'
            if self._occupied(action['destination'], self._packet['gripper'].get('holding_visible_id')):
                return 'held recovery destination is visibly occupied'
            return None
        if op == "setup":
            if station.get("busy") or station.get("occupied_visible_id") is not None or self._occupied("fixture"):
                return "setup requires an idle, observably empty fixture"
            captured = self._packet.get("capture_sim_time_s")
            age = self._packet["sim_time"] - captured if _finite(captured) else None
            # The public station field comes from the current insert observation.
            # Unknown/old captures and retained fixture_belief cannot establish a no-op.
            if (station.get("fixture_insert") == action["family"] and
                    age is not None and 0 <= age <= MAX_AGE_S):
                return "requested insert already freshly observed installed"
            return None
        part_id = action["part_id"]
        detection = self._fresh(part_id)
        if not detection:
            return "part lacks a fresh visible detection"
        part = self._part(part_id)
        if op == "transport":
            dest = action["destination"]
            if action.get("objective"):
                avoided = action["objective"].get("avoid_zones", [])
                if dest in avoided or detection["zone"] in avoided:
                    return "objective conflicts with the currently observed source or destination"
            if detection["zone"] == dest:
                return "part is already visibly at destination"
            if detection["zone"] == "fixture" and station.get("busy"):
                return "cannot unload a busy fixture"
            if dest in ("fixture", "inspection", "parking1", "parking2") and self._occupied(dest, part_id):
                return "single-capacity destination is visibly occupied"
            if dest == "fixture" and (station.get("busy") or self._fixture_family() != detection["family"]):
                return "fixture unavailable or insert incompatible"
            if dest.startswith("tray"):
                if not self._proof(part_id):
                    return "delivery requires supported process eligibility and matching passing inspection evidence"
                if not any(r["tray"] == dest for r in self._requirement(detection["family"], self._recipe(part_id))):
                    return "destination does not match the current order and verified recipe"
            return None
        if op == "cycle":
            if detection["zone"] != "fixture" or station.get("occupied_visible_id") != part_id:
                return "cycle requires the same visibly seated fixture part"
            if station.get("busy") or not station.get("ready", False) or station.get("fault"):
                return "station is not publicly ready"
            if self._fixture_family() != detection["family"]:
                return "fixture insert incompatible"
            if not self._requirement(detection["family"], action["recipe"]):
                return "recipe is absent from the current order for this family"
            cycle, inspection = part.get("cycle"), part.get("inspection") or {}
            if cycle and cycle.get("complete"):
                if inspection.get("status") != "rework" or part["reworks"] >= 1:
                    return "reprocessing lacks a retained eligible rework instruction"
            elif detection.get("visible_mark") != "raw":
                return "processed or unknown part cannot be blindly processed again"
            return None
        if op == "inspect" and detection["zone"] != "inspection":
            return "inspection requires the visible part on the inspection pad"
        return None

    def _complete(self):
        order, station = self._packet["order"], self._station()
        if not order.get("closed") or station.get("busy") or station.get("occupied_visible_id") is not None:
            return False
        if self._packet["gripper"].get("holding_visible_id") is not None:
            return False
        width = self._packet["gripper"].get("width")
        if not _finite(width) or width < OPEN_GRIPPER_WIDTH_M:
            return False
        allocated = set()
        for req in order["requirements"]:
            ids = [pid for pid, d in self._visible.items() if d["family"] == req["family"] and d["zone"] == req["tray"]
                   and self._proof(pid) and self._recipe(pid) == req["recipe"] and pid not in allocated]
            if len(ids) != req["count"]:
                return False
            allocated.update(ids)
        # No extra or unverified part may be visibly left in delivery trays.
        return all(pid in allocated for pid, d in self._visible.items() if d["zone"].startswith("tray"))

    def _counts(self):
        result = []
        for req in self._packet["order"]["requirements"]:
            ids = [pid for pid, d in self._visible.items() if d["family"] == req["family"] and d["zone"] == req["tray"]
                   and self._proof(pid) and self._recipe(pid) == req["recipe"]]
            result.append({**req, "verified_visible_ids": ids, "remaining": max(0, req["count"] - len(ids))})
        return result

    def _buffer(self):
        for zone in ("parking1", "parking2"):
            if not self._occupied(zone):
                return zone
        return "quarantine"

    def _visibility_state(self):
        return self.state.setdefault("visibility_reacquisition", {
            "captures": 0, "requested": False, "last_capture": None,
            "help_request_id": None, "assisted": False, "paused": False,
        })

    def _visibility_capture(self):
        packet = self._packet
        captured = packet.get("capture_sim_time_s")
        sequence = packet.get("sequence")
        if (not _finite(captured) or not isinstance(sequence, int) or isinstance(sequence, bool)
                or not 0 <= packet["sim_time"] - captured <= MAX_AGE_S):
            return None
        return [packet["incarnation"], sequence, captured]

    def _visibility_new_capture(self, capture, previous):
        if capture is None:
            return False
        if previous is None or capture[0] != previous[0]:
            return True
        return capture[1] > previous[1] and capture[2] > previous[2]

    def _visibility_answer(self, answer):
        visibility = self.state.get("visibility_reacquisition")
        if (visibility and visibility["help_request_id"] is not None
                and answer.get("request_id") == visibility["help_request_id"]
                and not visibility["assisted"]):
            visibility.update(captures=0, requested=False, last_capture=None,
                              assisted=True, paused=False)
            self._event("visibility_assisted_round", answer_id=answer["answer_id"],
                        request_id=visibility["help_request_id"])

    def _visibility_action(self):
        visibility = self._visibility_state()
        capture = self._visibility_capture()
        if not visibility["requested"]:
            visibility.update(requested=True, last_capture=capture)
            return {"operation": "observe", "reason": "request a fresh capture for visibility reacquisition"}
        if not self._visibility_new_capture(capture, visibility["last_capture"]):
            return {"operation": "wait", "reason": "await distinct fresh visibility capture"}
        visibility["last_capture"] = capture
        visibility["captures"] = min(4, visibility["captures"] + 1)
        self._idle_steps = visibility["captures"]
        if visibility["captures"] < 4:
            return {"operation": "observe", "reason": "no currently visible eligible stock or unresolved visibility"}
        if visibility["help_request_id"] is None:
            return {"operation": "help", "reason": "required progress lacks publicly supported eligible action"}
        visibility["paused"] = True
        self.state["halted"] = True
        self._event("visibility_reacquisition_blocked", captures=visibility["captures"],
                    help_request_id=visibility["help_request_id"],
                    assisted_round=visibility["assisted"],
                    reason="visibility allowance exhausted without supported progress; repeated help suppressed")
        return {"operation": "wait", "reason": "visibility remains unresolved; assistance request already retained"}

    def _resume_visibility_pause(self):
        visibility = self.state.get("visibility_reacquisition")
        if not visibility or not visibility["paused"] or self.kind not in ("baseline", "A3"):
            return
        if not self._visibility_new_capture(self._visibility_capture(), visibility["last_capture"]):
            return
        # Ask the existing scheduler; do not introduce another action ranking.
        action = self._baseline_action(visibility_fallback=False)
        if (action and action["operation"] in ("transport", "setup", "cycle", "inspect", "done")
                and self._validate(action) is None):
            visibility["paused"] = False
            self.state["halted"] = False
            self._event("visibility_supported_progress_available", action=action,
                        sequence=self._packet["sequence"], grading_authority=False)

    def _baseline_action(self, *, visibility_fallback=True):
        """A competent explicit sequencer using only retained/public evidence."""
        if self._complete():
            return {"operation": "done"}
        station = self._station()
        if station.get("fault"):
            return {"operation": "wait", "reason": "public station fault; await recovery"}
        counts = self._counts()
        # Correct amended destinations and remove visible surplus first.
        kept = set()
        for req in counts:
            kept.update(sorted(req["verified_visible_ids"])[:req["count"]])
        for pid, d in sorted(self._visible.items()):
            if d["zone"].startswith("tray") and pid not in kept:
                if self._proof(pid):
                    targets = [r for r in counts if r["family"] == d["family"] and r["recipe"] == self._recipe(pid)
                               and r["remaining"] and r["tray"] != d["zone"]]
                    dest = targets[0]["tray"] if targets else self._buffer()
                elif not self._occupied("inspection"):
                    dest = "inspection"
                else:
                    dest = self._buffer()
                return {"operation": "transport", "part_id": pid, "destination": dest}
        inspection_parts = [(pid, d) for pid, d in sorted(self._visible.items()) if d["zone"] == "inspection"]
        if inspection_parts:
            pid, d = inspection_parts[0]
            part = self._part(pid)
            inspected = part.get("inspection")
            if not inspected:
                return {"operation": "inspect", "part_id": pid}
            if inspected["status"] == "fail":
                return {"operation": "transport", "part_id": pid, "destination": "quarantine"}
            if inspected["status"] == "pass":
                if not self._proof(pid):
                    if self._public_recipe(d["family"]) and part["inspection_attempts"] < 2:
                        return {"operation": "inspect", "part_id": pid,
                                "reason": "fresh pad evidence needed for public-invariant eligibility reconstruction"}
                    return {"operation": "help", "reason": "passing inspection exists but recipe/cycle provenance is unavailable"}
                targets = [r for r in counts if r["family"] == d["family"] and r["recipe"] == self._recipe(pid) and r["remaining"]]
                return {"operation": "transport", "part_id": pid, "destination": targets[0]["tray"] if targets else self._buffer()}
            if part["reworks"] >= 1:
                return {"operation": "transport", "part_id": pid, "destination": "quarantine"}
            if station.get("busy") or self._occupied("fixture"):
                return {"operation": "wait"}
            if self._fixture_family() != d["family"]:
                return {"operation": "setup", "family": d["family"]}
            return {"operation": "transport", "part_id": pid, "destination": "fixture"}
        if station.get("busy"):
            return {"operation": "wait"}
        fixture_parts = [(pid, d) for pid, d in sorted(self._visible.items()) if d["zone"] == "fixture"]
        if fixture_parts:
            pid, d = fixture_parts[0]
            part = self._part(pid)
            cycle, inspected = part.get("cycle"), part.get("inspection") or {}
            if self._fixture_family() is None:
                return {"operation": "transport", "part_id": pid, "destination": self._buffer(),
                        "reason": "reveal the occluded insert before choosing an eligible process"}
            if cycle and cycle.get("complete") and inspected.get("status") != "rework":
                return {"operation": "transport", "part_id": pid, "destination": "inspection"}
            if d.get("visible_mark") == "processed" and not cycle:
                return {"operation": "transport", "part_id": pid, "destination": "inspection"}
            matches = [r for r in counts if r["family"] == d["family"] and (r["remaining"] or inspected.get("status") == "rework")]
            if not matches:
                return {"operation": "transport", "part_id": pid, "destination": self._buffer()}
            return {"operation": "cycle", "part_id": pid, "recipe": self._recipe(pid) or matches[0]["recipe"]}
        # Already processed work must be reconciled before selecting new stock.
        for pid, d in sorted(self._visible.items()):
            if d["zone"] in ("parking1", "parking2", "raw") and (d.get("visible_mark") == "processed" or self._part(pid).get("cycle") or self._part(pid).get("eligibility_inference")):
                if self._proof(pid):
                    targets = [r for r in counts if r["family"] == d["family"] and r["recipe"] == self._recipe(pid) and r["remaining"]]
                    if targets:
                        return {"operation": "transport", "part_id": pid, "destination": targets[0]["tray"]}
                elif not self._occupied("inspection"):
                    return {"operation": "transport", "part_id": pid, "destination": "inspection"}
        for req in counts:
            if not req["remaining"]:
                continue
            candidates = [(pid, d) for pid, d in sorted(self._visible.items()) if d["family"] == req["family"]
                          and d["zone"] in ("raw", "parking1", "parking2") and d.get("visible_mark") == "raw"
                          and not self._part(pid).get("cycle")]
            if candidates:
                if self._fixture_family() != req["family"]:
                    return {"operation": "setup", "family": req["family"]}
                return {"operation": "transport", "part_id": candidates[0][0], "destination": "fixture"}
        if not self._packet["order"].get("closed") and all(not r["remaining"] for r in counts):
            return {"operation": "wait", "reason": "provisional fulfillment; order stream remains open"}
        return self._visibility_action() if visibility_fallback else None

    def _guard(self, guard):
        predicate = guard["predicate"]
        part_id = guard.get("part_id")
        item = self._fresh(part_id)
        if predicate == "always":
            return True
        if predicate == "order_is":
            return self._packet["order"]["version"] == guard.get("order_version")
        if predicate == "station_idle":
            return not self._station().get("busy") and not self._station().get("fault")
        if predicate == "insert_is":
            return self._fixture_family() == guard.get("family") if self._fixture_family() else None
        if predicate == "visible":
            return True if item else None
        if predicate == "at_zone":
            return item["zone"] == guard.get("zone") if item else None
        if predicate == "processed":
            record = self._part(part_id)
            return bool((record.get("cycle") or {}).get("complete") or record.get("eligibility_inference")) if item else None
        if predicate == "inspection_is":
            inspection = self._part(part_id).get("inspection")
            return inspection["status"] == guard.get("status") if inspection else None
        return None

    def _program_action(self):
        program = self.state.get("program")
        if not program:
            return None, None
        if len(program["completed"]) == len(program["steps"]):
            self.state["program"] = None
            return None, None
        for index, node in enumerate(program["steps"]):
            if index in program["completed"]:
                continue
            values = [self._guard(g) for g in node["guards"]]
            self._event("procedure_guard", program_id=program["id"], node=index, results=values,
                        sequence=self._packet["sequence"])
            if all(v is True for v in values):
                action = copy.deepcopy(node["action"])
                action["order_version"] = program["order_version"]
                error = self._validate(action)
                if error is None:
                    self._guard_waits = 0
                    return action, index
                self.state["last_error"] = "procedure node " + str(index) + ": " + error
        self._guard_waits += 1
        if self._guard_waits <= 2:
            return {"operation": "observe", "reason": "procedure guards lack a currently admissible action"}, None
        self._event("procedure_suspended", program_id=program["id"], reason=self.state["last_error"] or "guards unmet")
        self.state["program"] = None
        self.state["model_failures"] += 1
        self._guard_waits = 0
        return None, None

    def _context(self):
        return {
            "run_id": self._packet["run_id"], "sequence": self._packet["sequence"], "sim_time": self._packet["sim_time"],
            "order": self._packet["order"], "visible_detections": list(self._visible.values()),
            "station": self._station(), "gripper": self._packet["gripper"],
            "fixture_belief": self.state.get("fixture_belief"),
            "process_contract": self._packet.get("process_contract"),
            "auxiliary_detections": [d for d in self._packet["detections"] if d.get("kind", "part") != "part"],
            "retained_parts": self.state["parts"], "verified_current_progress": self._counts(),
            "last_error": self.state["last_error"], "failed_attempts": self.state["failure_counts"],
            "recent_resolutions": copy.deepcopy(self.state["recent_resolutions"]),
            "human_answers": self._packet.get("human_answers", []),
            "limits": {"sensor_age_s": MAX_AGE_S, "max_procedure_steps": MAX_STEPS,
                       "max_recent_resolutions": MAX_RECENT_RESOLUTIONS},
        }

    def _request_model(self, action=None):
        self._persist()
        base = (
            "You control a simulated machine-tending robot using ONLY the supplied public observations. "
            "Return one JSON object matching the schema, with no prose. Current order_version must be respected. "
            "ACTION API: transport(part_id,destination) physically moves one visible part. It does not process or inspect it. "
            "cycle(part_id,recipe) ONLY processes a part ALREADY on fixture with its compatible insert; it does NOT move it. "
            "inspect(part_id) ONLY measures a part ALREADY on inspection; it does NOT move or process it. "
            "setup(family) exchanges the fixture insert and requires an empty idle fixture. "
            "observe with clear_view:true requests a guarded open-jaw retreat to the observation posture; use it for arm occlusion only with empty open jaws. "
            "recover_held(destination) retains the present closed grip until a free parking or inspection pad, releases and retreats; identity and successful placement remain unknown until observed. "
            "For a raw part in raw storage with the matching insert installed, move it to fixture FIRST. "
            "For example a hypothetical raw P with the right insert uses {operation:transport,part_id:P,destination:fixture}; "
            "after that move is verified, {operation:cycle,part_id:P,recipe:its_ordered_recipe}; "
            "after the cycle completes, transport P to inspection, then inspect P, then transport the passing part to its ordered tray. "
            "Use actual visible IDs, not the hypothetical P. Never request inspect on raw storage or cycle outside fixture. "
            "A visible processed mark is NOT recipe or inspection proof. Retained correlated completed cycle plus "
            "matching passing inspection permits delivery. Transport acknowledgements do not prove location. "
            "If the explicit public process_contract guarantees one recipe per family and an eligible-cycle-only mark, "
            "a newly requested passing inspection of a freshly visible processed part can reconstruct current eligibility; "
            "this inference does not restore historical cycle IDs. Retained eligibility_inference records expose its basis. "
            "Load raw stock into the compatible empty fixture, cycle with its ordered recipe, unload to inspection, "
            "inspect, and route passing parts to their current tray. Rework only after a public rework response, once. "
            "Set up an insert only with an empty idle fixture. If your chosen next part requires a different "
            "insert from the currently observed one, setup that family is a prerequisite to loading it. "
            "An already freshly observed matching insert needs no new setup. "
            "Inspection requires an inspect action at the inspection pad; arrival there is not inspection. "
            "You choose stock order and task order; these operation prerequisites do not select a next action. "
            "Recent resolutions are bounded candidate judgments from public evidence, not evaluator truth or a complete history. "
            "Recheck them against fresh input and the current order. Observe when evidence is missing. "
            "A retained fixture_belief may support admission while a loaded part occludes its tag; it remains fallible. "
            "Without insert evidence, unload a fixture part to a free parking slot to reveal the insert instead of guessing. "
            "Done requires closed orders, all distinct verified parts in correct trays, empty idle fixture and no held part. "
            "No evaluator history, hidden poses, arbitrary code or external tools exist."
        )
        context = self._context()
        # Enumerate every currently supported action from public evidence and
        # the common admission rules. This is a feasibility menu, not the
        # conventional scheduler's preferred next action. It deliberately
        # retains unproductive but legal alternatives and multiple stock IDs.
        if self.kind in ('A1', 'A2'):
            context['currently_admissible_actions'] = self._admissible_actions()
            context['action_menu_scope'] = ('Unranked current public feasibility only; '
                'choose actions that advance the order. Future procedure nodes may become feasible later.')
        if self.kind == "A1":
            schema = {"type": "object", "additionalProperties": False,
                      "properties": {"action": {"oneOf": [
                          {"type":"object", "additionalProperties":False,
                           "properties":{k:{"const":v} for k,v in item.items()},
                           "required":list(item)} for item in context['currently_admissible_actions']]}},
                      "required": ["action"]}
            instruction = ("Choose the next single typed job action from currently_admissible_actions. "
                           "This is an unranked feasibility menu, not a plan. Compare the current location, "
                           "completed processing and inspection with the order; choose useful progress. "
                           "You choose ordering and recovery; no prescribed next action is supplied.")
        elif self.kind == "A2":
            schema = {"type": "object", "additionalProperties": False,
                      "properties": {"steps": {"type": "array", "minItems": 1, "maxItems": MAX_STEPS,
                          "items": {"type": "object", "additionalProperties": False,
                                    "properties": {"guards": {"type": "array", "maxItems": 5, "items": _guard_schema()}, "action": _action_schema()},
                                    "required": ["guards", "action"]}}}, "required": ["steps"]}
            instruction = ("Compose up to 8 guarded action nodes spanning multiple physical steps. The interpreter scans uncompleted nodes in order "
                           "and runs the first with all guards true AND physically eligible. Completed nodes never repeat. Guards are "
                           "PRECONDITIONS that must already hold before the action, never the action's desired outcome. "
                           "Unloading a processed part from fixture to inspection may require processed and station_idle; "
                           "it must NOT require inspection_is(pass), because inspection happens only after that move. "
                           "Use inspection_is(pass) to guard delivery from the inspection pad to its ordered tray. "
                           "Include actions that establish missing prerequisites: insert_is(B) only tests the insert; "
                           "it does not perform setup(B). Do not guard setup(B) on insert_is(B), its desired outcome. "
                           "Likewise inspection_is(pass) does not perform inspect; include inspect before a delivery "
                           "that requires a new passing inspection. Choose your own bounded procedure and ordering. The guard predicates are "
                           "always, visible(part_id), at_zone(part_id,zone), station_idle, insert_is(family), processed(part_id), "
                           "inspection_is(part_id,status), order_is(order_version). processed requires retained public cycle evidence. "
                           "Use current public part IDs and order version; no variables, loops, imports or arbitrary code.")
        else:
            schema = copy.deepcopy(OBJECTIVE_SCHEMA)
            context["scheduled_action"] = action
            instruction = ("A conventional scheduler has chosen the displayed transport. Compose its geometric movement objective: "
                           "clearance in metres 0.08..0.25, speed_scale 0.3..1.0, approach vertical, and avoid_zones. "
                           "Use sensed positions/occupied zones and uncertainty to choose meaningful clearance and speed. "
                           "Never include the source or destination zone in avoid_zones. Protected collision limits remain mandatory. "
                           "You do not choose the job action, torques, exact trajectories or hidden geometry.")
        messages = [{"role": "system", "content": base + " " + instruction},
                    {"role": "user", "content": _json(context)}]
        self._model_context = {"order_version": self._packet["order"]["version"], "action": copy.deepcopy(action),
                               "sequence": self._packet["sequence"], "incarnation": self._packet["incarnation"]}
        self._event("model_context_supplied", messages=messages, schema=schema,
                    state_sha256=self._last_saved_hash, context_sha256=_digest(context))
        return {"type": "model", "messages": messages, "schema": schema}

    def _admissible_actions(self):
        proposals = [{'operation': op} for op in ('done','help','observe','wait')]
        proposals.append({'operation':'observe','clear_view':True})
        proposals.extend({'operation':'setup','family':family} for family in ('A','B'))
        proposals.extend({'operation':'recover_held','destination':zone}
                         for zone in ('parking1','parking2','inspection','quarantine'))
        for part_id in sorted(self._visible):
            proposals.extend({'operation':'transport','part_id':part_id,'destination':zone}
                             for zone in ZONES)
            proposals.append({'operation':'inspect','part_id':part_id})
            recipes = sorted({r['recipe'] for r in self._packet['order']['requirements']})
            proposals.extend({'operation':'cycle','part_id':part_id,'recipe':recipe} for recipe in recipes)
        return sorted((a for a in proposals if self._validate(a) is None), key=_json)

    def _validate_guard(self, guard):
        if not isinstance(guard, dict) or set(guard) - {"predicate", "part_id", "zone", "family", "status", "order_version"}:
            raise ValueError("invalid guard object")
        pred = guard.get("predicate")
        if pred not in GUARDS:
            raise ValueError("unknown guard predicate")
        if pred in ("visible", "at_zone", "processed", "inspection_is") and not isinstance(guard.get("part_id"), str):
            raise ValueError("guard requires part_id")
        if pred == "at_zone" and guard.get("zone") not in ZONES:
            raise ValueError("guard requires zone")
        if pred == "insert_is" and guard.get("family") not in ("A", "B"):
            raise ValueError("guard requires family")
        if pred == "inspection_is" and guard.get("status") not in ("pass", "rework", "fail"):
            raise ValueError("guard requires inspection status")
        if pred == "order_is" and "order_version" not in guard:
            raise ValueError("guard requires order_version")

    def accept_model(self, response: str):
        context, self._model_context = self._model_context, None
        self._event("model_output_received", response=response, requested_context=context)
        if context is None:
            self._event("model_output_rejected", reason="no live model request; late or old-incarnation output")
            return
        try:
            if not isinstance(response, str) or len(response.encode("utf-8")) > 65536:
                raise ValueError("model output is not bounded text")
            value = json.loads(response, parse_constant=_reject_constant)
            if not isinstance(value, dict):
                raise ValueError("model output must be an object")
            if self.kind == "A1":
                if set(value) != {"action"}:
                    raise ValueError("expected action object")
                error = self._syntax_action(value["action"])
                if error:
                    raise ValueError(error)
                self._queued = {"action": value["action"], "order_version": context["order_version"]}
            elif self.kind == "A2":
                steps = value.get("steps")
                if set(value) != {"steps"} or not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
                    raise ValueError("expected bounded steps")
                for node in steps:
                    if not isinstance(node, dict) or set(node) != {"guards", "action"}:
                        raise ValueError("procedure node must contain guards and action")
                    if not isinstance(node["guards"], list) or len(node["guards"]) > 5:
                        raise ValueError("too many guards")
                    for guard in node["guards"]:
                        self._validate_guard(guard)
                    error = self._syntax_action(node["action"])
                    if error:
                        raise ValueError(error)
                self.state["program"] = {"id": uuid.uuid4().hex, "order_version": context["order_version"],
                                         "steps": steps, "completed": [], "context_sequence": context["sequence"]}
                self._event("procedure_committed", program=self.state["program"])
            elif self.kind == "A3":
                if set(value) != {"clearance", "speed_scale", "approach", "avoid_zones"}:
                    raise ValueError("objective fields mismatch")
                if not _finite(value["clearance"]) or not 0.08 <= value["clearance"] <= 0.25:
                    raise ValueError("clearance outside bounds")
                if not _finite(value["speed_scale"]) or not 0.3 <= value["speed_scale"] <= 1.0 or value["approach"] != "vertical":
                    raise ValueError("speed or approach outside bounds")
                avoid = value["avoid_zones"]
                if not isinstance(avoid, list) or len(avoid) > 8 or any(z not in ZONES for z in avoid) or len(set(avoid)) != len(avoid):
                    raise ValueError("invalid avoided zones")
                action = context["action"]
                source = self._fresh(action["part_id"])
                if action["destination"] in avoid or (source and source["zone"] in avoid):
                    raise ValueError("objective forbids its source or destination")
                self._queued = {"action": {**action, "objective": value}, "order_version": context["order_version"]}
                self._event("objective_composed", objective=value, scheduled_action=action)
            else:
                raise ValueError("baseline does not request a model")
        except (ValueError, TypeError, KeyError) as exc:
            self.state["model_failures"] += 1
            self.state["last_error"] = str(exc)
            self._queued = None
            self._event("model_output_rejected", reason=str(exc), failure_count=self.state["model_failures"])
        self._persist()

    def _issue(self, action, program_node=None):
        action = copy.deepcopy(action)
        action["order_version"] = self._packet["order"]["version"]
        action["request_id"] = str(uuid.uuid4())
        action["incarnation"] = self._packet["incarnation"]
        action["observation_sequence"] = self._packet["sequence"]
        op = action["operation"]
        if op == "help":
            action.setdefault("reason", "Public evidence does not support further progress")
            action.setdefault("evidence", {
                "observation_sequence": self._packet["sequence"],
                "order_version": self._packet["order"]["version"],
                "last_error": self.state["last_error"],
                "pending_request_id": (self.state.get("pending") or {}).get("action", {}).get("request_id"),
                "pending_outcome_unknown": bool(self.state.get("pending")),
            })
            action.setdefault("requested_information_or_action",
                              "Advise on safe reconciliation using current public observations and order; preserve unknown action outcomes")
        if op not in ("observe", "wait", "help"):
            self.state["model_failures"] = 0
        self._event("action_intent", action=action, grading_authority=False)
        if op=='recover_held':
            self.state['recovery_pending']={'request_id':action['request_id'],
                'issued_time':self._packet['sim_time'],'feedback':None}
        if op in ("transport", "setup", "cycle", "inspect"):
            if op == "inspect":
                self._part(action["part_id"])["inspection_attempts"] += 1
            if op == "setup":
                self.state["fixture_belief"] = None  # The operation may move the old insert before failing.
            self.state["pending"] = {
                "action": action, "issued_time": self._packet["sim_time"], "issued_sequence": self._packet["sequence"],
                "before_cycle_id": self._station().get("cycle_id"),
                "before_inspection_id": self.state["last_inspection_id"], "feedback": None,
                "program_node": program_node,
                "program_id": (self.state.get("program") or {}).get("id"),
            }
        elif program_node is not None and self.state.get("program"):
            self.state["program"]["completed"].append(program_node)
        if op == "help":
            self.state["halted"] = True
            visibility = self.state.get("visibility_reacquisition")
            if visibility:
                own_visibility_help = (self.kind in ("baseline", "A3")
                    and visibility["captures"] >= 4 and visibility["help_request_id"] is None
                    and action.get("reason") == "required progress lacks publicly supported eligible action")
                visibility["paused"] = own_visibility_help
                if own_visibility_help:
                    visibility["help_request_id"] = action["request_id"]
        self._persist()  # This commit completes before the caller can dispatch.
        return {"type": "action", "action": action}

    def step(self, packet: dict):
        self._ingest(packet)
        self._reconcile()
        self._persist()
        # A release-boundary crash can leave the stationary arm covering the
        # placed tag. This common sensor-positioning adapter asks the executor
        # for a bounded retreat; it never resolves the retained action by fiat.
        incarnation=packet['incarnation']
        recovery=self.state.get('recovery_pending')
        if recovery:
            feedback=recovery.get('feedback') or {}
            if (packet.get('last_feedback') or {}).get('request_id')==recovery['request_id']:
                feedback=packet['last_feedback'];recovery['feedback']=copy.deepcopy(feedback)
            if feedback.get('status')=='completed' and packet['gripper'].get('width',0)>=OPEN_GRIPPER_WIDTH_M:
                self._event('recovery_motion_terminal',request_id=recovery['request_id'],
                            physical_placement_inferred=False,identity_inferred=False)
                self.state['recovery_pending']=None
            elif feedback.get('status') in ('failed','rejected','cancelled','expired','error') or packet['sim_time']-recovery['issued_time']>ACTION_TIMEOUT_S:
                self.state['recovery_blocked']=True
                if not self.state['halted']:
                    return self._issue({'operation':'help','reason':'held recovery outcome unresolved; further motion blocked'})
                return {'type':'wait'}
            else:
                return {'type':'wait'}
        if self.state.get('recovery_blocked'):
            return {'type':'wait'}
        if packet.get('restart_generation',0)>0 and self.state.get('held_recovery_incarnation')!=incarnation and packet['gripper'].get('width',.08)<OPEN_GRIPPER_WIDTH_M:
            self.state['held_recovery_incarnation']=incarnation
            self.state['clear_view_incarnation']=incarnation
            return self._issue({'operation':'recover_held','destination':self._buffer(),
                'reason':'preserve unknown held state until an observed free pad; reconcile only after fresh sensing'})
        if packet.get('restart_generation',0)>0 and self.state.get('clear_view_incarnation')!=incarnation and packet['gripper'].get('width',0)>=OPEN_GRIPPER_WIDTH_M and not packet['gripper'].get('holding_visible_id'):
            self.state['clear_view_incarnation']=incarnation
            return self._issue({'operation':'observe','clear_view':True,'reason':'recover an unobstructed observation after runtime restart; unresolved outcomes remain unknown'})
        pending = self.state.get("pending")
        if pending:
            if pending.get("unresolved_timeout") and not self.state["halted"]:
                return self._issue({"operation": "help", "reason": "unresolved previous action; further consequential work blocked"})
            return {"type": "wait"}
        if self.state["halted"]:
            self._resume_visibility_pause()
            if self.state["halted"]:
                return {"type": "wait"}
        if self._model_context:
            return {"type": "wait"}
        if self.state["model_failures"] >= MAX_MODEL_FAILURES:
            return self._issue({"operation": "help", "reason": "model failed bounded structured-output attempts"})
        if self._queued:
            queued, self._queued = self._queued, None
            action = copy.deepcopy(queued["action"])
            if queued["order_version"] != self._packet["order"]["version"]:
                self.state["last_error"] = "discarded model proposal after order amendment"
                self._event("model_proposal_discarded", reason=self.state["last_error"])
            else:
                action.setdefault("order_version", queued["order_version"])
                error = self._validate(action)
                if error is None:
                    return self._issue(action)
                self.state["last_error"] = error
                self.state["model_failures"] += 1
                self._event("action_rejected_locally", proposed_action=action, reason=error)
        if self.state["model_failures"] >= MAX_MODEL_FAILURES:
            return self._issue({"operation": "help", "reason": "model failed bounded action-admission attempts"})
        if self.kind == "A1":
            return self._request_model()
        if self.kind == "A2":
            action, node = self._program_action()
            if action:
                return self._issue(action, node)
            if self.state["model_failures"] >= MAX_MODEL_FAILURES:
                return self._issue({"operation": "help", "reason": "bounded procedure repair attempts exhausted"})
            return self._request_model()
        action = self._baseline_action()
        error = self._validate(action)
        if error:
            self.state["last_error"] = error
            self._event("scheduler_action_rejected", action=action, reason=error)
            return self._issue({"operation": "help", "reason": "scheduler cannot support proposed action: " + error})
        if self.kind == "A3" and action["operation"] == "transport":
            return self._request_model(action)
        return self._issue(action)
