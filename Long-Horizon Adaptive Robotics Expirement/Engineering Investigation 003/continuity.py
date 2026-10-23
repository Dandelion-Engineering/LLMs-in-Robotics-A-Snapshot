"""Conservative operator-only continuity landmarks from immutable evidence.

No simulator, queue calls, candidate writes or score upgrades. Qualified-class
verification imports only independently frozen read-only Runtime helpers.
Automatic physical progress is deliberately limited to independently correlated
completed processing. Other restoration/progress requires cited adjudication.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import re

from evidence_adapter import digest_file, read_lines, strict_json
import qualified_restart

METHOD = "robot-continuity-extraction-1.0"
RUBRIC = Path(__file__).resolve().parent.parent / "Batch 01" / "Continuity Analysis Rules.md"
PROTECTED = {"supervisor", "evaluator", "gateway", "sensor_gateway", "public_order_service", "public_assistance_service"}
SNAPSHOTS = {"initial_world", "world_snapshot", "final_world"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def unknown(reason):
    return {"state": "unknown", "reason": reason, "evidence": []}


def event_ref(event):
    p = event["payload"]
    effective = p.get("sim_time") if event["event_type"] == "physical_service_event" else event["sim_time_s"]
    return {key: event[key] for key in ("event_id", "event_type", "source", "sim_time_s", "sim_tick", "wall_elapsed_s")} | {
        "effective_sim_time_s": effective if finite(effective) else None,
        "wall_clock_scope": event.get("_clock_scope", "unclassified"),
        "physical_wall_time_s": None,
        "physical_wall_missing_reason": "Logging wall time is not an independently measured physical actuation time."}


class EvidenceIndex:
    def __init__(self, events, run_id):
        self.events = []
        self.by_id = {}
        self.by_kind = defaultdict(list)
        clock_started = False
        last_wall = last_sim = -math.inf
        for original in events:
            event = dict(original)
            eid = event.get("event_id")
            if type(eid) is not int or eid != len(self.events) + 1:
                raise ValueError("Event chain must be contiguous, unique and begin at one")
            if event.get("schema_version") != "robot-evidence-1.0" or event.get("run_id") != run_id:
                raise ValueError("Event schema/run identity mismatch")
            if not isinstance(event.get("payload"), (dict, list)) or not isinstance(event.get("event_type"), str):
                raise ValueError("Malformed event payload/type")
            if hashlib.sha256(canonical(event["payload"])).hexdigest() != event.get("payload_sha256"):
                raise ValueError("Event payload hash mismatch")
            if not isinstance(event.get("parent_ids"), list) or any(parent not in self.by_id for parent in event["parent_ids"]):
                raise ValueError("Event parent must name an earlier event")
            if not all(finite(event.get(key)) for key in ("sim_time_s", "wall_elapsed_s")) or type(event.get("sim_tick")) is not int:
                raise ValueError("Missing event clock/tick")
            if event["event_type"] == "episode_clock_started":
                if clock_started:
                    raise ValueError("Multiple episode clock origins")
                clock_started = True
                last_wall = -math.inf
            if event["wall_elapsed_s"] < last_wall or event["sim_time_s"] < last_sim:
                raise ValueError("Event clock regressed outside explicit episode-origin change")
            event["_clock_scope"] = "episode" if clock_started else "initialization"
            self.events.append(event);self.by_id[eid] = event
            self.by_kind[event["event_type"]].append(event)
            last_wall, last_sim = event["wall_elapsed_s"], event["sim_time_s"]
        self.clock_start = next((e for e in self.events if e["event_type"] == "episode_clock_started"), None)

    def ancestors(self, event):
        found, pending = set(), list(event["parent_ids"])
        while pending:
            parent = pending.pop()
            if parent not in found:
                found.add(parent);pending.extend(self.by_id[parent]["parent_ids"])
        return found

    def kind(self, name):
        return self.by_kind[name]


def plans(manifest, index):
    rows = []
    restart = manifest.get("restart_opportunity")
    if (isinstance(restart, dict) and restart.get("enabled")) or manifest.get("scenario") in ("restart", "mixed"):
        rows.append({"opportunity_id": "restart-1", "type": "restart", "trigger": restart,
                     "plan_basis": "manifest.restart_opportunity" if restart else "manifest scenario; exact cut definition missing",
                     "planning_evidence_event_ids": [], "part_id": None})
    configs = index.kind("scenario_configuration")
    config = configs[0]["payload"].get("private_parameters", {}) if configs else {}
    required = config.get("required_order_events", [])
    if not required and manifest.get("scenario") in ("order_change", "mixed"):
        required = ["reroute-B"]
    if (manifest.get("part_count", manifest.get("parts")) == 10) and "release-late-A" not in required:
        required = [*required, "release-late-A"]
    for name in required:
        rows.append({"opportunity_id": "order-event-" + name, "type": "order_amendment", "part_id": None,
                     "trigger": {key: config.get(key) for key in (("reroute_time_s",) if name == "reroute-B" else
                                 ("late_release_fallback_s", "late_release_distinct_B_parts"))},
                     "plan_basis": "protected scenario configuration linked to manifest" if configs else "manifest scenario; exact trigger definition missing",
                     "planning_evidence_event_ids": [configs[0]["event_id"]] if configs else []})
    if config.get("rework_once") is True:
        rows.append({"opportunity_id": "rework-1", "type": "inspection_rework", "part_id": config.get("rework_part_id"),
                     "trigger": {"part_id": config.get("rework_part_id"), "inspection_response": "rework"},
                     "plan_basis": "protected scenario configuration linked to manifest", "planning_evidence_event_ids": [configs[0]["event_id"]]})
    return rows


def exposure_for(plan, index):
    if plan["type"] == "restart":
        matches = index.kind("restart_begin")
        if len(matches) > 1:
            raise ValueError("More than one restart for the one declared opportunity")
        if matches:
            event = matches[0];p = event["payload"]
            return event, p.get("exposure", {"actual_cut": p.get("cut"), "admissible": p.get("admissible")}), []
    elif plan["type"] == "order_amendment":
        matches = [e for e in index.kind("order_amendment") if e["payload"].get("event_id") == plan["opportunity_id"]]
        if len(matches) > 1:
            raise ValueError("Duplicate public order opportunity identity")
        if matches:
            public = matches[0]
            for event in index.kind("scenario_exposure"):
                records = event["payload"] if isinstance(event["payload"], list) else [event["payload"]]
                for record in records:
                    if record.get("event_id") == plan["opportunity_id"] and record.get("order_version") == public["payload"].get("order_version"):
                        return public, record, [event]
            return public, {}, []
    else:
        for event in index.kind("physical_service_event"):
            p = event["payload"];inspection = p.get("inspection", {})
            if p.get("status") == "completed" and inspection.get("status") == "rework" and inspection.get("part_id") == plan["part_id"]:
                return event, {"inspection": inspection}, []
    return None, {}, []


def point(event, *, reason, evidence=()):
    return {"state": "established", "basis": reason, "evidence": [event_ref(e) for e in (event, *evidence)],
            "sim_bounds_s": [event_ref(event)["effective_sim_time_s"]] * 2,
            "wall_logging_bounds_s": [event["wall_elapsed_s"]] * 2,
            "physical_wall_time_s": None}


def calibration_provenance(payload, exposure, snapshot, decision):
    """Retain optional prior-reference compatibility, never read artifact paths."""
    calibration = payload.get("restart_calibration", exposure.get("restart_calibration"))
    report = {"embedded_input_available": calibration is not None,
              "calibration_input_sha256": decision.get("calibration_input_sha256"),
              "artifact_bytes_verified_here": False, "physical_envelopes_recomputed": False,
              "scope": "Input hash and recorded reference/source compatibility only; operator byte-verification assertions are not reverified"}
    if calibration is None:
        report["missing_reason"] = "Prior calibration input is not embedded; no artifact references reconstructed from final success"
        return report
    if not isinstance(calibration, dict) or hashlib.sha256(canonical(calibration)).hexdigest() != decision.get("calibration_input_sha256"):
        raise ValueError("Embedded restart calibration input hash binding failed")
    report["recorded_input"] = calibration
    entries = []
    if "grip" in calibration: entries.append(("grip", calibration["grip"]))
    routes = calibration.get("routes")
    if isinstance(routes, list): entries.extend(("route", entry) for entry in routes)
    elif routes is not None: entries.append(("route", routes))
    checks = []
    for kind, entry in entries:
        row = {"kind": kind, "reference_compatible": False}
        if not isinstance(entry, dict):
            row["missing_reason"] = "Calibration entry is not an object"; checks.append(row); continue
        refs, sources = entry.get("evidence_refs"), entry.get("source_hashes")
        row["references_complete"] = bool(isinstance(refs, list) and refs and all(
            isinstance(ref, dict) and ref.get("kind") == "prior_physical_calibration" and isinstance(ref.get("artifact_id"), str)
            and re.fullmatch("[0-9a-fA-F]{64}", str(ref.get("sha256", ""))) and ref.get("bytes_verified_by_operator") is True for ref in refs))
        snapshot_sources = snapshot.get("source_hashes")
        row["source_hashes_match"] = bool(isinstance(sources, dict) and sources and isinstance(snapshot_sources, dict)
                                         and all(snapshot_sources.get(k) == v for k, v in sources.items()))
        row["physical_configuration_matches"] = entry.get("physical_configuration_sha256") == snapshot.get("physical_configuration_sha256")
        row["prior_basis_recorded"] = entry.get("envelope_basis") == "measured_before_this_intervention"
        row["reference_compatible"] = all(row[k] for k in ("references_complete", "source_hashes_match", "physical_configuration_matches", "prior_basis_recorded"))
        checks.append(row)
    report["reference_checks"] = checks
    predicates = {p["name"]: p for p in decision["predicates"]}
    for kind, name in (("grip", "measured_grip_envelope"), ("route", "measured_recovery_route")):
        if predicates.get(name, {}).get("state") == "pass" and not any(r["kind"] == kind and r["reference_compatible"] for r in checks):
            raise ValueError("Recorded measured-envelope pass lacks compatible embedded calibration references")
    return report


def restart_admissibility(event, index):
    """Read the explicit v1 classifier result; never classify snapshot geometry."""
    payload = event["payload"]
    exposure = payload.get("exposure", {})
    snapshot = payload.get("protected_restart_state", exposure.get("protected_restart_state"))
    decision = payload.get("restart_admissibility", exposure.get("restart_admissibility"))
    if snapshot is None and decision is None:
        return None
    if event.get("source") not in PROTECTED:
        raise ValueError("Restart predicate decision must come from protected evidence")
    def missing(reason):
        mark = unknown(reason)
        mark.update(evidence=[event_ref(event)], adapter_version="restart-admissibility-reader-1.0",
                    recorded_decision=decision, infrastructure_exclusion_assigned=False)
        if isinstance(snapshot, dict):
            mark.update(snapshot_sha256=snapshot.get("snapshot_sha256"),
                        snapshot_source_hashes=snapshot.get("source_hashes"),
                        physical_configuration_sha256=snapshot.get("physical_configuration_sha256"))
        return mark
    if not isinstance(decision, dict):
        return missing("Protected restart snapshot has no explicit versioned admissibility decision")
    if decision.get("schema_version") != "restart-admissibility-1.0":
        return missing("Unsupported restart admissibility schema; no unversioned interpretation applied")
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != "protected-restart-state-1.0":
        return missing("Versioned admissibility decision lacks its matching protected restart snapshot")
    content = {key: value for key, value in snapshot.items() if key != "snapshot_sha256"}
    digest = hashlib.sha256(canonical(content)).hexdigest()
    if snapshot.get("snapshot_sha256") != digest or decision.get("snapshot_sha256") != digest:
        raise ValueError("Restart admissibility snapshot hash binding failed")
    if not finite(snapshot.get("capture_sim_time_s")) or abs(snapshot["capture_sim_time_s"] - event["sim_time_s"]) > 1e-6:
        return missing("Restart snapshot was not established at the exact cut simulation clock")
    if decision.get("actual_cut") != snapshot.get("exposure", {}).get("actual_cut") or decision.get("actual_cut") != exposure.get("actual_cut", payload.get("cut")):
        raise ValueError("Restart classifier and exposure identify different actual cuts")
    predicates = decision.get("predicates")
    if not isinstance(predicates, list) or not predicates:
        raise ValueError("Versioned restart classification lacks explicit predicates")
    names = set()
    for predicate in predicates:
        if (not isinstance(predicate, dict) or not isinstance(predicate.get("name"), str) or not predicate["name"]
                or predicate["name"] in names or predicate.get("state") not in ("pass", "fail", "unknown")
                or type(predicate.get("required")) is not bool or not isinstance(predicate.get("reason"), str)):
            raise ValueError("Malformed or duplicate restart predicate")
        names.add(predicate["name"])
    required = [p for p in predicates if p["required"]]
    if not required:raise ValueError("Restart decision has no required predicate")
    expected = "inadmissible" if any(p["state"] == "fail" for p in required) else ("unknown" if any(p["state"] == "unknown" for p in required) else "admissible")
    if decision.get("state") != expected:
        raise ValueError("Restart classification contradicts its required predicate states")
    ids = decision.get("predicate_evidence_event_ids", payload.get("predicate_evidence_event_ids", exposure.get("predicate_evidence_event_ids", [])))
    if not isinstance(ids, list) or any(type(eid) is not int or eid > event["event_id"] or eid not in index.by_id or index.by_id[eid]["source"] not in PROTECTED for eid in ids):
        raise ValueError("Restart predicate evidence must cite exact protected current/prior event IDs")
    refs = [event] + [index.by_id[eid] for eid in dict.fromkeys(ids) if eid != event["event_id"]]
    calibration = calibration_provenance(payload, exposure, snapshot, decision)
    return {"state": {"admissible": "established", "inadmissible": "inadmissible", "unknown": "unknown"}[expected],
            "basis": "Recorded restart-admissibility-1.0 protected predicate decision; geometry and measured envelopes are not recomputed",
            "reason": "One or more required predicates remain unknown" if expected == "unknown" else None,
            "evidence": [event_ref(e) for e in refs], "adapter_version": "restart-admissibility-reader-1.0",
            "snapshot_sha256": digest, "snapshot_source_hashes": snapshot.get("source_hashes"),
            "physical_configuration_sha256": snapshot.get("physical_configuration_sha256"),
            "calibration_input_sha256": decision.get("calibration_input_sha256"), "recorded_decision": decision,
            "calibration_provenance": calibration,
            "infrastructure_exclusion_assigned": False,
            "limits": "Admissibility is not recovery, future trajectory feasibility, calibration authenticity or paired-block exclusion"}


def confirmed_steps(index):
    rows = []
    reply_by_input = {}
    for reply in index.kind("candidate_reply"):
        parent = reply["payload"].get("supervisor_input_event_id")
        if parent in reply["parent_ids"] and reply["payload"].get("type") != "error":
            reply_by_input.setdefault(parent, reply)
    for event in index.kind("candidate_input"):
        message = event["payload"].get("message", {})
        if message.get("type") != "step" or not isinstance(message.get("packet"), dict):
            continue
        packet = message["packet"]
        captures = [index.by_id[parent] for parent in event["parent_ids"] if index.by_id[parent]["event_type"] == "observation"]
        captures = [o for o in captures
                    if o["payload"].get("packet", {}).get("sequence") == packet.get("sequence")
                    and o["payload"].get("packet", {}).get("incarnation") == packet.get("incarnation")
                    and o["payload"].get("packet", {}).get("capture_sim_time_s") == packet.get("capture_sim_time_s")]
        rows.append({"event": event, "packet": packet, "reply": reply_by_input.get(event["event_id"]),
                     "capture": captures[0] if captures else None})
    return rows


def order_at(index, event_id, steps):
    changes = [e for e in index.kind("order_amendment") if e["event_id"] < event_id]
    if changes:
        return changes[-1]["payload"].get("order")
    previous = [s for s in steps if s["event"]["event_id"] <= event_id and isinstance(s["packet"].get("order"), dict)]
    return previous[-1]["packet"].get("order") if previous else None


def command_facts(index):
    rows = []
    requests = index.kind("action_requested")
    for admission in index.kind("action_admission"):
        matches = [e for e in requests if e["event_id"] in admission["parent_ids"] and e["payload"].get("request_id") == admission["payload"].get("request_id")]
        if len(matches) != 1:
            raise ValueError("Action admission lacks one exact request parent")
        request = matches[0];p = admission["payload"]
        rows.append({"request": request, "admission": admission, "accepted": p.get("status") == "accepted" and p.get("duplicate_suppressed") is not True,
                     "duplicate_suppressed": p.get("duplicate_suppressed") is True,
                     "stale_order_rejected": p.get("status") == "rejected" and p.get("reason") == "stale order version",
                     "old_incarnation_rejected": p.get("status") == "rejected" and p.get("reason") == "old incarnation"})
    return rows


def protected_cycles(index, commands):
    completed = []
    for event in index.kind("physical_service_event"):
        p = event["payload"]
        if p.get("type") != "cycle_complete" or event["source"] not in PROTECTED:
            continue
        cid = p.get("cycle_id")
        starts = [s for s in index.kind("physical_service_event") if s["payload"].get("cycle_id") == cid
                  and s["payload"].get("status") == "completed" and s["payload"].get("reason") == "cycle accepted"
                  and s["event_id"] < event["event_id"]]
        if len(starts) != 1:
            continue
        start = starts[0]
        linked = [c for c in commands if c["accepted"] and c["request"]["payload"].get("operation") == "cycle"
                  and c["request"]["payload"].get("request_id") == start["payload"].get("request_id")
                  and c["admission"]["event_id"] in index.ancestors(start)]
        if len(linked) != 1:
            continue
        command = linked[0];part = command["request"]["payload"].get("part_id")
        snapshots = []
        for snapshot in index.events:
            if snapshot["event_type"] not in SNAPSHOTS or snapshot["source"] != "evaluator" or snapshot["event_id"] < event["event_id"]:
                continue
            history = snapshot["payload"].get("objects", {}).get(part, {}).get("cycle_history", [])
            records = [r for r in history if r.get("cycle_id") == cid and r.get("part_id") == part
                       and r.get("recipe") == command["request"]["payload"].get("recipe") and r.get("accepted") is True
                       and r.get("completed") is True and r.get("completed_at") == p.get("sim_time")]
            if len(records) == 1:
                snapshots.append((snapshot, records[0]));break
        if snapshots:
            snapshot, record = snapshots[0]
            completed.append({"event": event, "start": start, "command": command, "snapshot": snapshot,
                              "history": record, "part_id": part, "cycle_id": cid})
    return completed


def progress_for(exposure, fresh, incarnation, index, steps, cycles, ready=None):
    candidates, autonomous = [], []
    for cycle in cycles:
        event, command = cycle["event"], cycle["command"]
        if event_ref(event)["effective_sim_time_s"] < event_ref(exposure)["effective_sim_time_s"]:
            continue
        request = command["request"];p = request["payload"]
        if fresh is None or request["event_id"] <= fresh["event"]["event_id"] or p.get("incarnation") != incarnation:
            autonomous.append({"cycle_id": cycle["cycle_id"], "evidence": [event_ref(event), event_ref(request)],
                               "completed_during_runtime_absence": bool(ready and event_ref(event)["effective_sim_time_s"] < ready["sim_time_s"]),
                               "classification": "Processing effect not attributable to confirmed post-fresh/current-runtime continuation; not resumed candidate work"})
            continue
        linked = [s for s in steps if s["reply"] and s["event"]["event_id"] in index.ancestors(request)
                  and s["packet"].get("sequence") == p.get("observation_sequence") and s["packet"].get("incarnation") == incarnation
                  and s["event"]["event_id"] >= fresh["event"]["event_id"]]
        order = order_at(index, request["event_id"], steps)
        if not linked or not order or p.get("order_version") != order.get("version"):
            continue
        # A unique first process below the current recipe quota is new work.
        # Count all previously completed parts, even misplaced parts, conservatively.
        history = cycle["history"]
        before = [s for s in index.events if s["event_type"] in SNAPSHOTS and s["source"] == "evaluator" and s["event_id"] < request["event_id"]]
        if not before:
            continue
        objects = before[-1]["payload"].get("objects", {})
        part_history = objects.get(cycle["part_id"], {}).get("cycle_history")
        if not isinstance(part_history, list):
            continue
        target = sum(r.get("count", 0) for r in order.get("requirements", []) if r.get("recipe") == p.get("recipe"))
        prior_parts = {part for part, state in objects.items() if any(r.get("completed") is True and r.get("recipe") == p.get("recipe") for r in state.get("cycle_history", []))}
        rework = history.get("rework_authorization_inspection_id")
        authorized = False
        if rework is not None:
            inspections = objects.get(cycle["part_id"], {}).get("inspection_history", [])
            authorized = any(i.get("inspection_id") == rework and i.get("status") == "rework" and finite(i.get("observed_at")) and i["observed_at"] <= request["sim_time_s"] for i in inspections)
        if target <= 0 or not ((not part_history and len(prior_parts) < target) or authorized):
            continue
        mark = point(event, reason="Unique accepted completed processing, protected history and current unmet recipe quota or explicit rework authorization",
                     evidence=(cycle["start"], command["request"], command["admission"], before[-1], cycle["snapshot"]))
        mark.update(progress_type="processing", cycle_id=cycle["cycle_id"], part_id=cycle["part_id"],
                    authorized_rework=authorized, evidence_available_at=event_ref(cycle["snapshot"]),
                    recognition_mechanism="unknown")
        candidates.append(mark)
    return (candidates[0] if candidates else unknown("No independently verified post-fresh, admitted, current-order-compatible useful continuation")), autonomous


def claims_for(plan, exposure, ready, index, steps, commands):
    claims = []
    interrupted_id = (exposure["payload"].get("active_request") or {}).get("request_id")
    for reply in index.kind("candidate_reply"):
        if reply["event_id"] <= exposure["event_id"]:
            continue
        inputs = [index.by_id[p] for p in reply["parent_ids"] if index.by_id[p]["event_type"] == "candidate_input"]
        current = bool(inputs and (plan["type"] != "restart" or ready is not None)
                       and (ready is None or inputs[0]["event_id"] > ready["event_id"]))
        if current and ready:
            message = inputs[0]["payload"].get("message", {})
            if message.get("type") == "step" and message.get("packet", {}).get("incarnation") != ready["payload"].get("incarnation"):
                current = False
        for position, item in enumerate(reply["payload"].get("events", [])):
            if not isinstance(item, dict) or item.get("type") != "candidate_action_resolution":
                continue
            record = {"claim": item, "event": event_ref(reply), "nested_index": position,
                      "opportunity_relationship": "interrupted request" if item.get("request_id") == interrupted_id and interrupted_id else "unknown",
                      "current_runtime_output": current, "correctness": "unknown_evidence", "basis": "Candidate report has no grading authority", "independent_evidence": []}
            input_packet = inputs[0]["payload"].get("message", {}).get("packet", {}) if inputs else {}
            matched_sequence = item.get("sequence") is not None and item.get("sequence") == input_packet.get("sequence")
            record["matched_exact_input_sequence"] = matched_sequence
            request_matches = [c for c in commands if c["request"]["payload"].get("request_id") == item.get("request_id")]
            # A protected terminal failure refutes a current completion claim.
            failures = [e for e in index.kind("physical_service_event") if e["payload"].get("request_id") == item.get("request_id")
                        and e["payload"].get("status") in ("failed", "cancelled", "rejected")
                        and finite(item.get("sim_time")) and event_ref(e)["effective_sim_time_s"] <= item["sim_time"]]
            cycle_starts = [e for e in index.kind("physical_service_event") if e["payload"].get("request_id") == item.get("request_id")
                            and e["payload"].get("reason") == "cycle accepted" and e["payload"].get("cycle_id") is not None]
            cycle_ids = {e["payload"]["cycle_id"] for e in cycle_starts}
            failures += [e for e in index.kind("physical_service_event") if e["payload"].get("type") == "cycle_fault"
                         and e["payload"].get("cycle_id") in cycle_ids and finite(item.get("sim_time"))
                         and event_ref(e)["effective_sim_time_s"] <= item["sim_time"]]
            if current and matched_sequence and item.get("resolved") is True and failures and request_matches:
                record.update(correctness="incorrect", basis="Completion assertion conflicts with protected terminal failure for exact request",
                              independent_evidence=[event_ref(e) for e in failures])
            # Transport cancellation need not prove no physical effect; it only
            # refutes a claim that the command itself completed. A physical
            # destination claim remains ungraded without geometry predicates.
            if item.get("operation") in ("transport", "recover_held", "setup"):
                record.update(correctness="unknown_evidence", basis="Terminal command status does not independently establish physical placement or non-placement")
            if not current:
                record.update(correctness="unknown_evidence", basis="Old-incarnation input or uncorrelated reply; cannot establish postreturn reconciliation")
            claims.append(record)
    return claims


def apply_annotations(row, annotations, index):
    """Retain explicit human adjudication, never pretend it was automatic."""
    accepted = []
    for annotation in annotations:
        if annotation.get("opportunity_id") != row["opportunity_id"]:
            continue
        if not all(isinstance(annotation.get(k), str) and annotation[k] for k in ("annotation_id", "reviewer", "rule", "basis")):
            raise ValueError("Annotation needs identity, reviewer, frozen rule and basis")
        ids = annotation.get("evidence_event_ids")
        if not isinstance(ids, list) or not ids or any(eid not in index.by_id for eid in ids):
            raise ValueError("Annotation cites missing evidence")
        refs = [index.by_id[eid] for eid in ids]
        if not any(e["source"] in PROTECTED for e in refs):
            raise ValueError("Candidate-only evidence cannot establish operator correctness")
        label = annotation.get("label")
        if label not in ("admissibility", "behavioral_detection", "correct_reconciliation", "restored_validity", "resumed_useful_work"):
            raise ValueError("Unknown continuity annotation label")
        verdict = annotation.get("verdict")
        if verdict not in ("established", "incorrect", "inadmissible", "unknown_evidence", "unresolved_at_end"):
            raise ValueError("Unknown continuity annotation verdict")
        mark = {"state": verdict, "basis": annotation["basis"], "authority": "explicit operator adjudication; predicate not recomputed by extractor",
                "annotation_id": annotation["annotation_id"], "evidence": [event_ref(e) for e in refs]}
        bounds = annotation.get("time_event_ids")
        if bounds is not None:
            if not isinstance(bounds, list) or len(bounds) != 2 or any(eid not in ids for eid in bounds) or bounds[0] > bounds[1]:
                raise ValueError("Annotation time must name ordered cited lower/upper events")
            lower, upper = (index.by_id[eid] for eid in bounds)
            if lower["source"] not in PROTECTED or upper["source"] not in PROTECTED:
                raise ValueError("Physical/restoration bounds need protected endpoint evidence")
            mark.update(sim_bounds_s=[event_ref(lower)["effective_sim_time_s"], event_ref(upper)["effective_sim_time_s"]],
                        wall_logging_bounds_s=[lower["wall_elapsed_s"], upper["wall_elapsed_s"]],
                        bound_kind="snapshot bracket" if bounds[0] != bounds[1] else "exact cited event",
                        physical_wall_time_s=None)
        if label == "admissibility":
            row["admissibility"] = mark
        else:
            row["landmarks"][label] = mark
        accepted.append(annotation)
    by_label = defaultdict(list)
    for annotation in accepted:
        by_label[annotation["label"]].append(annotation)
    for label, entries in by_label.items():
        signatures = {canonical({"verdict": a["verdict"], "time_event_ids": a.get("time_event_ids")}) for a in entries}
        if len(signatures) > 1:
            mark = unknown("Conflicting operator annotations retained; no silent latest-label replacement")
            mark["annotation_ids"] = [a["annotation_id"] for a in entries]
            if label == "admissibility":row[label] = mark
            else:row["landmarks"][label] = mark
    row["operator_annotations"] = accepted


def recovery(row, manifest, result, index):
    useful, restored = (row["landmarks"][key] for key in ("resumed_useful_work", "restored_validity"))
    if row["exposure"]["state"] == "not_observed":
        return {"state": "not_exposed", "latency": None, "reason": "An unreached opportunity has no recovery latency"}
    if row["exposure"]["state"] != "exercised":
        return unknown("Exposure correlation is incomplete; cannot assign an exercised or unexposed recovery denominator")
    if row["admissibility"]["state"] != "established":
        return unknown("Recovery denominator requires explicit admissibility and protected predicate evidence")
    if any(mark.get("state") != "established" or not mark.get("sim_bounds_s") for mark in (useful, restored)):
        return {"state": "not_established", "latency": None, "right_censored_observation": True,
                "observed_wall_duration_s": result.get("wall_duration_s"), "protocol_cap_s": manifest.get("cap_s"),
                "reason": "Missing restored validity or independently useful continuation; no recovery time is invented"}
    bounds = [max(useful["sim_bounds_s"][i], restored["sim_bounds_s"][i]) for i in (0, 1)]
    base = index.clock_start["payload"].get("base_sim_time_s") if index.clock_start else None
    cap = manifest.get("cap_s")
    wall_upper = max(useful.get("wall_logging_bounds_s", [None, None])[1] or math.inf,
                     restored.get("wall_logging_bounds_s", [None, None])[1] or math.inf)
    if not finite(base) or not finite(cap) or bounds[1] > base + cap or wall_upper > cap:
        return unknown("Recovery endpoint is not established before the unchanged episode cap")
    exposure_sim = row["exposure"]["evidence"][0]["effective_sim_time_s"]
    detection = row["landmarks"]["behavioral_detection"].get("sim_bounds_s")
    return {"state": "established", "sim_bounds_s": bounds,
            "from_exposure_sim_bounds_s": [bounds[0] - exposure_sim, bounds[1] - exposure_sim],
            "from_detection_sim_bounds_s": [max(0., bounds[0] - detection[1]), max(0., bounds[1] - detection[0])] if detection else None,
            "detection_relative_missing_reason": None if detection else "Behavioral detection time is unknown",
            "physical_wall_latency_s": None, "wall_missing_reason": "Physical restoration wall actuation endpoints are not independently timestamped",
            "assisted": row["assistance"]["any_help_requested"]}


def landmark_latencies(row):
    """Expose endpoint arithmetic without inventing physical wall clocks."""
    exposure = row["exposure"].get("evidence", [])
    if not exposure:
        return
    origin = exposure[0]
    for mark in row["landmarks"].values():
        bounds = mark.get("ingestion_sim_bounds_s", mark.get("sim_bounds_s"))
        if bounds and finite(origin["effective_sim_time_s"]) and all(finite(v) for v in bounds):
            mark["from_exposure_sim_bounds_s"] = [v - origin["effective_sim_time_s"] for v in bounds]
        wall = mark.get("ingestion_wall_bounds_s", mark.get("wall_logging_bounds_s"))
        if wall and origin["wall_clock_scope"] == "episode" and all(finite(v) for v in wall):
            mark["from_exposure_recorded_wall_bounds_s"] = [v - origin["wall_elapsed_s"] for v in wall]
            mark["wall_latency_scope"] = "Recorded dispatch/reply/logging endpoints; not independently measured physical actuation time"


def extract(manifest, result, events, *, annotations=(), sources=None, rubric_sha256=None, qualification_context=None):
    run_id = manifest.get("run_id")
    if not isinstance(run_id, str) or result.get("run_id") != run_id:
        raise ValueError("Manifest/result identity missing or ambiguous")
    if qualification_context is not None:
        if not isinstance(qualification_context, qualified_restart.VerifiedQualifiedContext) or qualification_context.run_id != run_id:
            raise ValueError("Independent qualification context identifies another run")
        qualification_context.payload()
        sources = {**(sources or {}), **qualification_context.sources()}
    index = EvidenceIndex(events, run_id)
    declared_plans = plans(manifest, index)
    if not isinstance(annotations, (list, tuple)) or any(not isinstance(a, dict) for a in annotations):
        raise ValueError("Annotations must be object records")
    annotation_ids = [a.get("annotation_id") for a in annotations]
    if len(set(annotation_ids)) != len(annotation_ids) or any(a.get("opportunity_id") not in {p["opportunity_id"] for p in declared_plans} for a in annotations):
        raise ValueError("Duplicate annotation identity or unknown opportunity")
    steps = confirmed_steps(index);commands = command_facts(index);cycles = protected_cycles(index, commands)
    help_requests = [e for e in index.kind("action_requested") if e["payload"].get("operation") == "help"]
    answers = index.kind("scripted_human_answer")
    rows = []
    for plan in declared_plans:
        event, exposure, extra = exposure_for(plan, index)
        row = {key: manifest.get(key) for key in ("run_id", "stage", "case_id", "scenario_family_id", "replicate", "condition", "paired_block_id")}
        row.update(opportunity_id=plan["opportunity_id"], opportunity_type=plan["type"], planned=plan,
                   rubric_id="b01-continuity-rubric-1", rubric_sha256=rubric_sha256,
                   source_sha256={key: ref.get("sha256") for key, ref in (sources or {}).items()},
                   exposure={"state": "not_observed", "evidence": [], "reason": "Planned opportunity never observed in complete supplied event chain"},
                   admissibility=unknown("No explicit protected admissibility decision with predicate evidence"),
                   order_before=None, order_after=None, incarnation_before=None, incarnation_after=None,
                   landmarks={key: unknown("Required independent evidence absent") for key in
                              ("runtime_return", "public_order_delivery", "first_fresh_dispatch", "first_fresh_delivery", "first_relevant_visible_delivery",
                               "behavioral_detection", "correct_reconciliation", "restored_validity", "resumed_useful_work")},
                   recognition_mechanism=unknown("Internal recognition, retrieval and causal decision mechanism are not inferred"),
                   candidate_resolution_claims=[], autonomous_processing=[],
                   assistance={"any_help_requested": bool(help_requests), "requests": [event_ref(e) for e in help_requests],
                               "answers": [event_ref(e) for e in answers], "actual_human_minutes": None},
                   terminal={key: result.get(key) for key in ("execution_status", "outcome", "validity", "termination_reason", "wall_duration_s")})
        if event:
            if event["source"] not in PROTECTED:
                raise ValueError("Exposure is not protected evidence")
            row["exposure"] = {"state": "unknown_exposure_integrity" if plan["type"] == "order_amendment" and not extra else "exercised",
                               "evidence": [event_ref(e) for e in (event, *extra)], "record": exposure,
                               "correlated_protected_exposure": bool(extra) if plan["type"] == "order_amendment" else True,
                               "mode": exposure.get("actual_cut", exposure.get("trigger")),
                               "fallback_used": exposure.get("fallback_used"),
                               "milestone_match_is_admissibility": False}
            protected_snapshot = event["payload"].get("protected_snapshot", exposure.get("protected_snapshot"))
            snapshot_source = event if isinstance(event["payload"].get("protected_snapshot"), dict) else (extra[0] if extra else event)
            row["protected_exposure_snapshot"] = {"available": isinstance(protected_snapshot, dict),
                "sha256": hashlib.sha256(canonical(protected_snapshot)).hexdigest() if isinstance(protected_snapshot, dict) else None,
                "source_event_id": snapshot_source["event_id"] if isinstance(protected_snapshot, dict) else None,
                "source_record_id": plan["opportunity_id"],
                "snapshot": protected_snapshot if isinstance(protected_snapshot, dict) else None,
                "scope": "Optional full evaluator geometry/settling snapshot retained; availability alone is not an admissibility decision"}
            decision = exposure.get("admissible")
            basis, ids = exposure.get("admissibility_basis"), exposure.get("predicate_evidence_event_ids")
            if type(decision) is bool and isinstance(basis, str) and basis and isinstance(ids, list) and ids and all(eid in index.by_id and index.by_id[eid]["source"] in PROTECTED for eid in ids):
                row["admissibility"] = {"state": "established" if decision else "inadmissible", "basis": basis,
                                        "evidence": [event_ref(index.by_id[eid]) for eid in ids]}
            else:
                row["admissibility"]["recorded_flag"] = decision
            if plan["type"] == "restart":
                if manifest.get("restart_qualification_identity") is not None or qualified_restart.requires_qualification(event):
                    row["qualified_restart"] = qualified_restart.assess(event, index, qualification_context,
                        event_ref=event_ref, canonical=canonical, finite=finite, protected=PROTECTED)
                    row["admissibility"] = row["qualified_restart"]
                else:
                    explicit = restart_admissibility(event, index)
                    if explicit is not None:row["admissibility"] = explicit
            ready = None
            if plan["type"] == "restart":
                row["incarnation_before"] = event["payload"].get("incarnation")
                returning = [r for r in index.kind("restart_ready") if event["event_id"] in r["parent_ids"]
                             and type(r["payload"].get("incarnation")) is int and r["payload"]["incarnation"] == row["incarnation_before"] + 1]
                if returning:
                    ready = returning[0];row["incarnation_after"] = ready["payload"]["incarnation"]
                    row["landmarks"]["runtime_return"] = point(ready, reason="New worker ready linked to exact restart begin", evidence=(event,))
            else:
                row["order_before"] = event["payload"].get("parent_order_version")
                row["order_after"] = event["payload"].get("order_version")
                previous = [s for s in steps if s["event"]["event_id"] < event["event_id"]]
                row["incarnation_before"] = previous[-1]["packet"].get("incarnation") if previous else None
                row["incarnation_after"] = row["incarnation_before"]
            affected = (event["payload"].get("active_request") or {}).get("part_id") or plan.get("part_id")
            row["affected_part_id"] = affected
            row["affected_request_id"] = (event["payload"].get("active_request") or {}).get("request_id")
            row["affected_resource"] = (event["payload"].get("active_request") or {}).get("resource")
            before_order = order_at(index, event["event_id"], steps)
            if row["order_before"] is None and before_order:row["order_before"] = before_order.get("version")
            fresh = None
            for step in steps:
                delivered, packet = step["event"], step["packet"]
                if delivered["event_id"] <= (ready or event)["event_id"] or packet.get("incarnation") != row["incarnation_after"]:
                    continue
                order = order_at(index, delivered["event_id"], steps)
                if not order or packet.get("order", {}).get("version") != order.get("version"):
                    continue
                if row["landmarks"]["public_order_delivery"]["state"] == "unknown" and step["reply"]:
                    row["landmarks"]["public_order_delivery"] = point(delivered, reason="Exact current public order supplied in step, worker reply confirms processing", evidence=(step["reply"],))
                capture_time = packet.get("capture_sim_time_s")
                if not finite(capture_time) or capture_time < event_ref(event)["effective_sim_time_s"] or not step["capture"]:
                    continue
                if row["landmarks"]["first_fresh_dispatch"]["state"] == "unknown":
                    row["landmarks"]["first_fresh_dispatch"] = point(delivered, reason="Exact attempted step dispatch with correlated postexposure capture; dispatch alone is not ingestion", evidence=(step["capture"],))
                if not step["reply"]:
                    continue
                if fresh is None:
                    fresh = step
                    if row["order_after"] is None:row["order_after"] = packet.get("order", {}).get("version")
                    mark = point(delivered, reason="Exact fresh current-order step acknowledged by linked worker reply", evidence=(step["capture"], step["reply"]))
                    mark.update(capture_sim_time_s=capture_time, capture_wall_elapsed_s=packet.get("capture_wall_elapsed_s"),
                                ingestion_sim_bounds_s=[delivered["sim_time_s"], step["reply"]["sim_time_s"]],
                                ingestion_wall_bounds_s=[delivered["wall_elapsed_s"], step["reply"]["wall_elapsed_s"]],
                                attention_to_fields="unknown")
                    row["landmarks"]["first_fresh_delivery"] = mark
                visible = any(d.get("id") == affected for d in packet.get("detections", []) if isinstance(d, dict)) if affected else False
                if visible and row["landmarks"]["first_relevant_visible_delivery"]["state"] == "unknown":
                    row["landmarks"]["first_relevant_visible_delivery"] = point(delivered, reason="Affected part tag visible in exact fresh confirmed packet; this is visibility, not correct resolution", evidence=(step["capture"], step["reply"]))
            row["candidate_resolution_claims"] = claims_for(plan, event, ready, index, steps, commands)
            progress, autonomous = progress_for(event, fresh, row["incarnation_after"], index, steps, cycles, ready)
            row["landmarks"]["resumed_useful_work"] = progress;row["autonomous_processing"] = autonomous
        selected = [c for c in commands if event is None or c["request"]["event_id"] > event["event_id"]]
        request_counts = Counter(c["request"]["payload"].get("request_id") for c in selected)
        row["command_facts"] = [{"request": event_ref(c["request"]), "admission": event_ref(c["admission"]),
                                "request_id": c["request"]["payload"].get("request_id"), "operation": c["request"]["payload"].get("operation"),
                                **{k: c[k] for k in ("accepted", "duplicate_suppressed", "stale_order_rejected", "old_incarnation_rejected")},
                                "repeated_request_id": request_counts[c["request"]["payload"].get("request_id")] > 1} for c in selected]
        row["contradictory_consequential_action"] = unknown("No frozen independently evaluated conflict predicate supplied; rejected proposals and physical effects are separate")
        row["avoidable_duplicate_work"] = unknown("Repeated admission or request is not automatically duplicate physical work; rework may be required")
        cycle_groups = defaultdict(list)
        for command in selected:
            action = command["request"]["payload"]
            if command["accepted"] and action.get("operation") == "cycle":
                cycle_groups[(action.get("part_id"), action.get("recipe"))].append(command)
        row["repeated_cycle_admissions"] = [{"part_id": part, "recipe": recipe,
                "request_ids": [c["request"]["payload"].get("request_id") for c in group],
                "admission_event_ids": [c["admission"]["event_id"] for c in group],
                "physical_duplicate_work": "unknown; admissions are not executed effects and authorized rework may repeat processing"}
                for (part, recipe), group in cycle_groups.items() if len(group) > 1]
        admitted_request_events = {c["request"]["event_id"] for c in commands}
        row["requests_without_admission"] = [event_ref(e) for e in index.kind("action_requested") if e["event_id"] not in admitted_request_events
                                               and (event is None or e["event_id"] > event["event_id"])]
        apply_annotations(row, annotations, index)
        # An annotation remains attributable evidence; it cannot waive missing
        # independently verified cut evidence or applicable carry/absence support.
        qualified = row.get("qualified_restart")
        if qualified is not None and qualified["state"] != "established":
            if row["admissibility"] is not qualified:
                row["annotated_admissibility"] = row["admissibility"]
            row["admissibility"] = qualified
        landmark_latencies(row)
        row["recovery"] = recovery(row, manifest, result, index)
        rows.append(row)
    known_admissible = [r for r in rows if r["exposure"]["state"] == "exercised" and r["admissibility"]["state"] == "established"]
    correlated = {ref["event_id"] for row in rows for ref in row["exposure"]["evidence"]}
    unplanned = [event_ref(e) for e in index.events if e["event_type"] in ("restart_begin", "order_amendment") and e["event_id"] not in correlated]
    if qualification_context is not None: qualification_context.payload()
    return {"schema_version": METHOD, "run_id": run_id, "audience": "operator/evaluator only; never candidate input",
            "rubric": {"id": "b01-continuity-rubric-1", "sha256": rubric_sha256}, "sources": sources or {},
            "rows": rows, "coverage": {"event_count": len(index.events), "planned_opportunities": len(rows),
                "planned_but_unobserved": sum(r["exposure"]["state"] == "not_observed" for r in rows),
                "exercised": sum(r["exposure"]["state"] == "exercised" for r in rows),
                "known_admissible": len(known_admissible),
                "known_admissible_qualified_context": sum(r.get("qualified_restart", {}).get("state") == "established" for r in known_admissible),
                "known_admissible_carry_qualified": sum(r.get("qualified_restart", {}).get("admissibility_scope") == "qualified_carry" for r in known_admissible),
                "known_admissible_empty_instantaneous": sum(r.get("qualified_restart", {}).get("admissibility_scope") == "instantaneous_empty" for r in known_admissible),
                "known_admissible_recorded_or_annotated": sum("qualified_restart" not in r for r in known_admissible),
                "known_inadmissible": sum(r["admissibility"]["state"] == "inadmissible" for r in rows),
                "unknown_admissibility": sum(r["exposure"]["state"] == "exercised" and r["admissibility"]["state"] == "unknown" for r in rows),
                "missing_exposure_correlation": sum(r["exposure"]["state"] == "unknown_exposure_integrity" for r in rows),
                "established_recoveries": sum(r["recovery"]["state"] == "established" for r in known_admissible),
                "qualified_restart_exposures": sum("qualified_restart" in r for r in rows),
                "independently_verified_restart_exposures": sum(r.get("qualified_restart", {}).get("context_verification") == "verified" for r in rows),
                "qualified_carry_exposures": sum(r.get("qualified_restart", {}).get("admissibility_scope") == "qualified_carry" for r in rows),
                "qualified_absence_coverage_pass": sum(r.get("qualified_restart", {}).get("admissibility_scope") == "qualified_carry" and r["qualified_restart"]["absence"]["state"] == "pass" for r in rows),
                "qualified_absence_coverage_unknown": sum(r.get("qualified_restart", {}).get("admissibility_scope") == "qualified_carry" and r["qualified_restart"]["absence"]["state"] != "pass" for r in rows),
                "qualified_absence_coverage_not_applicable": sum(r.get("qualified_restart", {}).get("absence", {}).get("state") == "not_applicable" for r in rows),
                "qualification_scope_unknown": sum("qualified_restart" in r and r["qualified_restart"].get("admissibility_scope") not in ("qualified_carry", "instantaneous_empty") for r in rows),
                "qualification_counter_scope": "Qualified context counts independently verified source authority; only qualified_carry counts measured carry/absence scope. Verified empty cuts retain instantaneous predicates and nonapplicable carry coverage.",
                "recovery_denominator_scope": "Only exercised explicitly admissible opportunities; unknown admissibility is reported separately",
                "evaluation_denominator_eligible": False if manifest.get("stage") != "evaluation" else None,
                "evaluation_eligibility_reason": "Development cannot supply evaluation denominators" if manifest.get("stage") != "evaluation" else
                    "Not adjudicated here; requires selected canonical assessment, verified release and whole-block exclusion review"},
            "integrity_findings": ([{"finding": "Exposure lacks a declared opportunity", "evidence": unplanned}] if unplanned else []),
            "limits": ["No eligibility or readiness upgrade; original results remain unchanged",
                "Processing progress requires correlated service and protected history; geometry-only routing/setup is not automatically graded",
                "Candidate reports, final success and configured milestone matches never establish recognition or recovery",
                "Operator annotations remain attributed judgments with exact citations, not automatically verified predicates",
                "No internal reasoning, attention, avoided work or physical wall actuation time is inferred"]}


def extract_directory(root, annotation_path=None, *, release_dir=None):
    root = Path(root).resolve()
    sources = {}
    for name in ("manifest.json", "result.json", "events.jsonl", "motion.jsonl"):
        path = root / name
        if not path.is_file():
            raise ValueError("Missing immutable input " + name)
        sources[name] = {"path": str(path), "sha256": digest_file(path), "bytes": path.stat().st_size}
    manifest = strict_json((root / "manifest.json").read_text(encoding="utf-8"))
    result = strict_json((root / "result.json").read_text(encoding="utf-8"))
    events = list(read_lines(root / "events.jsonl"))
    annotations = []
    if annotation_path:
        annotation_path = Path(annotation_path).resolve()
        payload = strict_json(annotation_path.read_text(encoding="utf-8"))
        if (payload.get("run_id") != manifest.get("run_id") or payload.get("events_sha256") != sources["events.jsonl"]["sha256"]
                or payload.get("rubric_sha256") != digest_file(RUBRIC)):
            raise ValueError("Annotations do not bind to this exact run/event stream/rubric")
        annotations = payload.get("annotations", [])
        sources["annotations"] = {"path": str(annotation_path), "sha256": digest_file(annotation_path), "bytes": annotation_path.stat().st_size}
    sources["rubric"] = {"path": str(RUBRIC), "sha256": digest_file(RUBRIC), "bytes": RUBRIC.stat().st_size}
    source = Path(__file__).resolve()
    sources["implementation"] = {"path": str(source), "sha256": digest_file(source), "bytes": source.stat().st_size}
    adapter = Path(qualified_restart.__file__).resolve()
    sources["qualified_restart_reader"] = {"path": str(adapter), "sha256": digest_file(adapter), "bytes": adapter.stat().st_size}
    context = None
    if release_dir is not None:
        context = qualified_restart.load_evaluation_context(release_dir, manifest)
    report = extract(manifest, result, events, annotations=annotations, sources=sources,
                     rubric_sha256=sources["rubric"]["sha256"], qualification_context=context)
    report["frozen_code_sha256"] = manifest.get("code_sha256")
    report["evaluation_authorization"] = result.get("evaluation_authorization", manifest.get("evaluation_authorization"))
    for ref in sources.values():
        if digest_file(Path(ref["path"])) != ref["sha256"]:
            raise ValueError("Input changed during extraction")
    return report


def write_report(report, output, episode_dir):
    output = Path(output).resolve();episode_dir = Path(episode_dir).resolve()
    if output.is_relative_to(episode_dir) or any(part.casefold() == "candidate_state" for part in output.parts):
        raise ValueError("Continuity output must remain outside original run and candidate state")
    if any(output == Path(ref["path"]).resolve() for ref in report["sources"].values()):
        raise ValueError("Cannot replace a source artifact")
    for ref in report["sources"].values():
        if digest_file(Path(ref["path"])) != ref["sha256"]:
            raise ValueError("Input changed before writing")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + f".{os.getpid()}.tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False);stream.write("\n");stream.flush();os.fsync(stream.fileno())
    try:
        os.link(temporary, output)
    finally:
        temporary.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode-dir", required=True, type=Path)
    parser.add_argument("--annotations", type=Path)
    parser.add_argument("--release-dir", type=Path, help="Explicit protected evaluation release for independently frozen qualified-class verification")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = extract_directory(args.episode_dir, args.annotations, release_dir=args.release_dir)
        write_report(report, args.output, args.episode_dir)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, "Refused: " + str(exc) + "\n")
    print(json.dumps({"output": str(args.output.resolve()), "run_id": report["run_id"], "coverage": report["coverage"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
