"""Operator-only qualified restart verification; recorded flags are not authority.

Runtime source is read-only. The production loader must exist and match the
protected freeze before this adapter imports it. Missing context remains unknown.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import importlib
import json
from pathlib import Path
import sys

from evidence_adapter import digest_file, strict_json

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent / "Runtime"
MODULES = ("restart_compatibility", "restart_physical_class", "restart_qualification",
           "restart_state", "restart_calibration_loader")
_AUTHORITY = object()


def object_file(path):
    value = strict_json(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise ValueError("Expected protected JSON object")
    return value


def source(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": digest_file(path), "bytes": path.stat().st_size}


def verify_sources(sources):
    for item in sources.values():
        if source(item["path"]) != item: raise ValueError("Qualified restart authority source changed: " + item["path"])


def reference(item, base, sources):
    if not isinstance(item, dict) or not isinstance(item.get("path"), str):
        raise ValueError("Missing protected qualification reference")
    path = Path(item["path"])
    path = (path if path.is_absolute() else Path(base) / path).resolve()
    if any(part.casefold() == "candidate_state" for part in path.parts):
        raise ValueError("Qualification reference cannot name candidate state")
    actual = source(path)
    if actual["sha256"] != item.get("sha256"): raise ValueError("Protected qualification reference hash differs")
    sources[str(path)] = actual
    return path


def runtime_api(freeze, freeze_path, sources):
    """Verify the five executable helper sources against the frozen code index."""
    code_ref = freeze.get("artifacts", {}).get("code")
    code_path = reference(code_ref, freeze_path.parent, sources)
    if code_ref["sha256"] != freeze.get("code_sha256"):
        raise ValueError("Qualification classifier code index differs from freeze")
    index = object_file(code_path)
    indexed = {}
    for item in index.get("files", []):
        path = Path(item["path"])
        path = (path if path.is_absolute() else code_path.parent / path).resolve()
        if path in indexed: raise ValueError("Duplicate frozen classifier source")
        indexed[path] = item
    for name in MODULES:
        path = (RUNTIME / (name + ".py")).resolve()
        if path not in indexed: raise ValueError("Frozen code lacks qualified restart helper: " + name)
        reference(indexed[path], code_path.parent, sources)
    if str(RUNTIME) not in sys.path: sys.path.insert(0, str(RUNTIME))
    modules = {}
    for name in MODULES:
        module = importlib.import_module(name)
        if Path(module.__file__).resolve() != (RUNTIME / (name + ".py")).resolve():
            raise ValueError("Qualified restart imported a different helper")
        modules[name] = module
    verify_sources(sources)
    return modules["restart_calibration_loader"], modules["restart_state"]


@dataclass(frozen=True)
class VerifiedQualifiedContext:
    run_id: str
    payload_json: str
    sources_json: str
    loader: object = field(repr=False, compare=False)
    classifier: object = field(repr=False, compare=False)
    _authority: object = field(repr=False, compare=False, default=None)

    def payload(self):
        if self._authority is not _AUTHORITY: raise ValueError("Unverified qualified context")
        verify_sources(self.sources())
        return json.loads(self.payload_json)

    def sources(self):
        if self._authority is not _AUTHORITY: raise ValueError("Unverified qualified context")
        return json.loads(self.sources_json)


def load_evaluation_context(release_root, manifest):
    """Bind a retained freeze through explicit release/run authority, not events.

This does not select canonical results or establish their eligibility. The
evaluation processor separately verifies finalization and selected assessments.
"""
    release_root = Path(release_root).resolve(); sources = {}
    if manifest.get("stage") != "evaluation": raise ValueError("Release authority is only for evaluation evidence")
    auth = manifest.get("evaluation_authorization") or {}
    release_path = reference({"path": "release.json", "sha256": auth.get("release_sha256")}, release_root, sources)
    release = object_file(release_path)
    matching = [item for item in release.get("manifest_refs", []) if item.get("run_id") == manifest.get("run_id")]
    if len(matching) != 1: raise ValueError("Release lacks one exact qualification run reference")
    plan_path = reference(matching[0], release_root, sources)
    if not plan_path.is_relative_to(release_root) or matching[0]["sha256"] != auth.get("manifest_sha256"):
        raise ValueError("Qualification run manifest is not bound to episode authorization")
    plan = object_file(plan_path)
    if plan.get("run_id") != manifest.get("run_id") or plan.get("stage") != "evaluation":
        raise ValueError("Qualification planned run identity differs")
    freeze_path = reference(release.get("freeze_manifest"), release_root, sources)
    if plan.get("freeze_sha256") != sources[str(freeze_path)]["sha256"]:
        raise ValueError("Qualification freeze is not bound to protected planned run")
    freeze = object_file(freeze_path)
    mode = freeze.get("restart_matching_mode", "exact_configuration")
    if mode == "exact_configuration" and freeze.get("restart_qualification") is None:
        if manifest.get("restart_qualification_identity") is not None:
            raise ValueError("Recorded qualified restart has no independently frozen qualified mode")
        verify_sources(sources)
        return None
    if mode != "qualified_class":
        raise ValueError("Recorded qualified restart has no independently frozen qualified mode")
    loader, classifier = runtime_api(freeze, freeze_path, sources)
    verified = loader.load_restart_qualification(freeze, freeze_path)
    if verified is None: raise ValueError("Frozen qualified restart loader returned no context")
    payload = verified.as_dict()
    identity = payload["identity"]
    for item in (identity["freeze_manifest"], identity["bundle_file"], *identity["artifact_files"].values()):
        reference(item, freeze_path.parent, sources)
    if manifest.get("restart_qualification_identity") != identity:
        raise ValueError("Episode qualification identity differs from independently loaded freeze")
    verify_sources(sources)
    return VerifiedQualifiedContext(manifest["run_id"], json.dumps(payload, allow_nan=False),
                                    json.dumps(sources, allow_nan=False), loader, classifier, _AUTHORITY)


def requires_qualification(event):
    payload = event.get("payload", {})
    calibration = payload.get("restart_calibration") or {}
    entries = [calibration.get("grip"), *(calibration.get("routes") or [])]
    decision = payload.get("restart_admissibility") or {}
    return (payload.get("restart_qualification_identity") is not None
            or bool(decision.get("qualified_class_evidence"))
            or any(isinstance(entry, dict) and entry.get("match_mode") == "qualified_class" for entry in entries))


def _landmark(value, finite):
    return isinstance(value, dict) and all(finite(value.get(key)) for key in ("wall_s", "sim_s"))


def assess(event, index, context, *, event_ref, canonical, finite, protected):
    """Recompute at-cut classification and later absence coverage independently."""
    payload = event["payload"]
    report = {"state": "unknown", "adapter_version": "qualified-restart-reader-1.1",
              "reason": "Independent frozen qualification context was not supplied",
              "context_verification": "unknown", "admissibility_scope": "unverified",
              "recorded_at_cut": payload.get("restart_admissibility"), "evidence": [event_ref(event)],
              "absence": {"state": "unknown", "reason": "Independent qualification context unavailable"},
              "infrastructure_exclusion_assigned": False}
    if context is None: return report
    if not isinstance(context, VerifiedQualifiedContext) or context.run_id != event["run_id"]:
        raise ValueError("Qualified context does not identify this run")
    verified = context.payload(); report["verified_identity"] = verified["identity"]
    if payload.get("restart_qualification_identity") != verified["identity"]:
        raise ValueError("Restart event qualification identity differs from independent authority")
    snapshot, recorded = payload.get("protected_restart_state"), payload.get("restart_admissibility")
    if not isinstance(snapshot, dict) or not isinstance(recorded, dict):
        report["reason"] = "Qualified restart lacks snapshot or recorded classifier"; return report
    import hashlib
    snapshot_hash = hashlib.sha256(canonical({k: v for k, v in snapshot.items() if k != "snapshot_sha256"})).hexdigest()
    if snapshot.get("snapshot_sha256") != snapshot_hash or recorded.get("snapshot_sha256") != snapshot_hash:
        raise ValueError("Qualified restart snapshot hash differs")
    if snapshot.get("exposure", {}).get("actual_cut") != payload.get("exposure", {}).get("actual_cut", payload.get("cut")):
        raise ValueError("Qualified restart snapshot identifies another cut")
    selected = context.loader.select_restart_calibration(verified, snapshot)
    if payload.get("restart_qualification_selection") != {k: v for k, v in selected.items() if k != "calibration"}:
        raise ValueError("Recorded qualification selection differs from frozen deterministic mapping")
    if payload.get("restart_calibration") != selected["calibration"]:
        raise ValueError("Recorded calibration differs from independently selected measured cell")
    recomputed = context.classifier.classify_restart(snapshot, calibration=selected["calibration"],
                                                     qualification_context=verified["qualification_context"])
    if recomputed != recorded: raise ValueError("Recorded qualified classifier differs from independent recomputation")
    report["recomputed_at_cut"] = recomputed
    report["at_cut_state"] = recomputed["state"]
    report["selection"] = {k: v for k, v in selected.items() if k != "calibration"}
    # Source authority applies to every cut. A measured carry cell applies only
    # to its actual cut family; an episode-wide identity does not broaden it.
    phase = recomputed.get("actual_cut")
    empty = phase in ("after_acceptance", "after_release", "before_outcome")
    carry = phase == "closed_grip_transfer"
    report.update(context_verification="verified",
                  admissibility_scope="qualified_carry" if carry else ("instantaneous_empty" if empty else "unsupported_cut"))
    if empty:
        report["absence"] = {"state": "not_applicable",
            "reason": "Measured carry-cell absence coverage does not apply to this empty/released cut",
            "scope": "No actual absence coverage or future recovery guarantee is inferred"}
    elif not carry:
        report["absence"] = {"state": "unknown", "reason": "Unsupported actual cut; no measured carry coverage applied"}
    if recomputed["state"] == "inadmissible":
        report.update(state="inadmissible", reason="Independent at-cut predicates failed")
    elif recomputed["state"] != "admissible":
        report["reason"] = "Independent at-cut predicates remain unknown"
    else: report["reason"] = "At-cut evidence passes; actual qualified absence must also be established"
    if not (carry or empty):
        context.payload()
        return report
    report["cut_capture_state"] = "unknown"
    def missing_capture(reason):
        # Preserve the historical carry result and reason. Empty cuts still
        # need the captured state bound to authority revocation, without
        # interpreting the carry duration/endpoint as their physical support.
        if carry: report["absence"]["reason"] = reason
        else: report["reason"] = reason
        return report
    capture = payload.get("capture_landmarks", {})
    landmarks = [capture.get(key) for key in ("start", "finish", "classification_finish")]
    revoked = [e for e in index.kind("restart_authority_revoked") if event["event_id"] in e["parent_ids"] and e["source"] in protected]
    if len(revoked) != 1 or any(not _landmark(item, finite) for item in landmarks):
        return missing_capture("Exact capture/classification/revocation landmarks unavailable")
    revocation = revoked[0]; before, after = (revocation["payload"].get(key) for key in ("before_cancel", "after_cancel"))
    if not _landmark(before, finite) or not _landmark(after, finite):
        return missing_capture("Authority revocation clock pair unavailable")
    clock_chain = [*landmarks, before, after]
    if (any(any(a[key] > b[key] for key in ("wall_s", "sim_s")) for a, b in zip(clock_chain, clock_chain[1:]))
            or not finite(snapshot.get("capture_sim_time_s"))
            or not landmarks[0]["sim_s"] <= snapshot["capture_sim_time_s"] <= landmarks[1]["sim_s"]
            or snapshot["capture_sim_time_s"] != before["sim_s"]):
        return missing_capture("Capture/classification/revocation clock ordering is unsupported")
    report["evidence"].append(event_ref(revocation))
    report["cut_capture_state"] = "established"
    if empty:
        report["state"] = {"admissible": "established", "inadmissible": "inadmissible", "unknown": "unknown"}[recomputed["state"]]
        if recomputed["state"] == "admissible":
            report["reason"] = "Independently recomputed instantaneous empty/released-cut predicates pass; carry qualification does not apply"
        report["limits"] = "Instantaneous admissibility is not actual absence coverage, restored task validity, useful resumption or guaranteed recovery"
        context.payload()
        return report
    ready = [e for e in index.kind("restart_ready") if event["event_id"] in e["parent_ids"] and e["source"] in protected
             and e["payload"].get("incarnation") == payload.get("incarnation", -2) + 1]
    ready = ready[0] if len(ready) == 1 else None
    admissions = []
    for admission in index.kind("action_admission"):
        if admission["event_id"] <= revocation["event_id"] or admission["source"] not in protected: continue
        requests = [index.by_id[eid] for eid in admission["parent_ids"] if index.by_id[eid]["event_type"] == "action_requested"
                    and index.by_id[eid]["payload"].get("request_id") == admission["payload"].get("request_id")]
        if len(requests) != 1: continue
        control = context.loader.first_control_endpoint(requests[0]["payload"], admission["payload"],
                     incarnation=payload.get("incarnation", -2)+1, expected_destination=verified["destination"])
        if control is not None: admissions.append((admission, control))
    first = admissions[0] if admissions else None
    absence_events = [e for e in index.kind("restart_absence") if e["source"] in protected
                      and event["event_id"] in e["parent_ids"] and e["payload"].get("restart_event_id") == event["event_id"]]
    required = verified["absence"]["absence_endpoint"]
    if required == "restart_ready":
        selected_events = [e for e in absence_events if e["payload"].get("observed_endpoint") == "restart_ready"]
    elif first:
        selected_events = [e for e in absence_events if first[0]["event_id"] in e["parent_ids"]]
    else:
        selected_events = [e for e in absence_events if e["payload"].get("observed_endpoint") == "episode_end_unobserved"]
        if not selected_events: selected_events = [e for e in absence_events if e["payload"].get("observed_endpoint") == "restart_ready"]
    if len(selected_events) != 1:
        report["absence"]["reason"] = "Exact qualified endpoint missing or ambiguous; no zero duration assigned"; return report
    observed = selected_events[0]; fact = observed["payload"]; endpoint = fact.get("observed_endpoint")
    if fact.get("qualification_identity") != verified["identity"] or fact.get("start") != before:
        raise ValueError("Absence record is not bound to qualification and authority revocation")
    if not _landmark(fact.get("end"), finite) or fact["end"]["sim_s"] != observed["sim_time_s"]:
        report["absence"]["reason"] = "Absence endpoint lacks its exact recorded simulation landmark"; return report
    if any(fact["end"][key] < after[key] for key in ("wall_s", "sim_s")):
        report["absence"]["reason"] = "Absence ended before authority revocation completed"; return report
    if endpoint == "restart_ready":
        if ready is None or ready["payload"].get("absence") != fact or ready["sim_time_s"] != fact["end"]["sim_s"]:
            report["absence"]["reason"] = "Readiness endpoint is not independently linked to the replacement incarnation"; return report
    elif endpoint in ("recover_held_admitted", "other_control_admitted"):
        if (first is None or ready is None or first[0]["event_id"] <= ready["event_id"]
                or first[0]["event_id"] not in observed["parent_ids"] or fact.get("control_admission") != first[1]
                or endpoint != first[1]["endpoint"] or fact["end"]["sim_s"] < first[0]["sim_time_s"]):
            report["absence"]["reason"] = "Absence does not identify the first novel admitted post-restart control"; return report
    elif endpoint != "episode_end_unobserved":
        report["absence"]["reason"] = "Unsupported observed absence endpoint"; return report
    recomputed_absence = context.loader.absence_observation(before, fact["end"], endpoint, verified["absence"])
    if any(fact.get(key) != value for key, value in recomputed_absence.items()):
        raise ValueError("Recorded absence duration/coverage differs from independently recomputed clocks and frozen settings")
    report["absence"] = {**recomputed_absence["coverage"], "observation": recomputed_absence,
                         "recorded_event_id": observed["event_id"], "duration_origin": "before_cancel"}
    report["evidence"].append(event_ref(observed))
    if first: report["evidence"].append(event_ref(first[0]))
    if recomputed["state"] == "admissible" and recomputed_absence["coverage"]["state"] == "pass":
        report.update(state="established", reason="Independently loaded frozen qualification, at-cut predicates and exact actual absence all pass")
    elif recomputed["state"] == "admissible": report["reason"] = recomputed_absence["coverage"]["reason"]
    context.payload()  # Verify external identities again after classification.
    return report
