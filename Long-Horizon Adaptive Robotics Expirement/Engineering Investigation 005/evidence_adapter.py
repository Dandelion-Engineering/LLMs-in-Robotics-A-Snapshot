"""Read actual robot-evidence-1.0 logs into a compact operator snapshot.

No simulator or candidate code is imported. Payload hashes are checked, gaps
remain explicit, and regular samples are retained without interpolating values.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
from urllib.parse import quote


class IncompleteEvidence(ValueError):
    """A declared stream ends before its final record is complete."""


def digest_file(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def strict_json(text):
    def constant(value):
        raise ValueError("Nonfinite JSON constant " + value)
    return json.loads(text, parse_constant=constant)


def read_lines(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError(f"{path.name}:{number}: blank record")
            if not line.endswith("\n"):
                raise IncompleteEvidence(f"{path.name}:{number}: incomplete final record; wait for the writer")
            try:
                record = strict_json(line)
            except ValueError as exc:
                raise ValueError(f"{path.name}:{number}: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path.name}:{number}: expected an object")
            yield record


def relative_href(path: Path, output: Path) -> str:
    return quote(Path(os.path.relpath(path.resolve(), output.resolve().parent)).as_posix(), safe="/.")


def cross_volume(path, output):
    """A standalone relative browser link cannot cross Windows volumes."""
    return PureWindowsPath(str(path)).drive.casefold() != PureWindowsPath(str(output)).drive.casefold()


def artifact_ref(root: Path, value, output: Path) -> dict:
    if not isinstance(value, str) or not value:
        return {"state": "unknown", "reason": "No path recorded", "href": None}
    relative = Path(value)
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        raise ValueError("Artifact reference escapes the run directory: " + value)
    if relative.is_absolute() or "\\" in value or ":" in value:
        raise ValueError("Artifact reference must be a portable run-relative path")
    if not resolved.is_file():
        return {"state": "missing", "reason": "File absent at build time", "path": value, "href": None}
    return {"state": "available", "path": value, "href": relative_href(resolved, output),
            "sha256": digest_file(resolved), "bytes": resolved.stat().st_size}


def finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(label + " must be a finite number")
    return value


def read_run(run_dir: Path, output: Path, observation_hz=2.0, motion_hz=5.0) -> dict:
    root = run_dir.resolve()
    for rate in (observation_hz, motion_hz):
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError("Display sampling rates must be positive and finite")
    manifest_path = root / "manifest.json"
    source_paths = [root / name for name in ("manifest.json", "events.jsonl", "motion.jsonl", "result.json")
                    if (root / name).exists()]
    initial_hashes = {path.name: digest_file(path) for path in source_paths}
    manifest = strict_json(manifest_path.read_text(encoding="utf-8"))
    run_id = manifest.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("Run manifest has no run_id")
    event_path, motion_path, result_path = root / "events.jsonl", root / "motion.jsonl", root / "result.json"
    events, counts, gaps, previous_id = [], Counter(), [], 0
    previous_sim, previous_wall = -math.inf, -math.inf
    clock_start = None
    for event in read_lines(event_path):
        if event.get("schema_version") != "robot-evidence-1.0" or event.get("run_id") != run_id:
            raise ValueError("Unsupported event schema or mismatched run identity")
        event_id = event.get("event_id")
        if type(event_id) is not int or event_id <= previous_id:
            raise ValueError("Event IDs must strictly increase")
        if event_id != previous_id + 1:
            gaps.append({"after_event_id": previous_id, "before_event_id": event_id,
                         "missing_count": event_id - previous_id - 1})
        sim = finite(event.get("sim_time_s"), "sim_time_s")
        wall = finite(event.get("wall_elapsed_s"), "wall_elapsed_s")
        payload = event.get("payload")
        payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                                allow_nan=False).encode()).hexdigest()
        if payload_hash != event.get("payload_sha256"):
            raise ValueError("Event payload hash mismatch at " + str(event_id))
        kind = event.get("event_type")
        if not isinstance(kind, str):
            raise ValueError("Event type must be a string")
        # ScenarioService may expose several records in one protected event.
        # This is the only declared non-object payload, matching diagnostics.
        if not (isinstance(payload, dict) or
                (kind == "scenario_exposure" and event.get("source") == "evaluator"
                 and isinstance(payload, list) and bool(payload)
                 and all(isinstance(record, dict) for record in payload))):
            raise ValueError("Unsupported event payload at " + str(event_id))
        if kind == "episode_clock_started":
            if clock_start is not None:
                raise ValueError("Multiple episode clock origins")
            if event.get("source") != "supervisor":
                raise ValueError("Episode clock origin must be supervisor-declared")
            finite(payload.get("monotonic_s"), "episode clock monotonic_s")
            if finite(payload.get("base_sim_time_s"), "episode clock base_sim_time_s") != sim:
                raise ValueError("Episode clock base differs from recorded simulation time")
            clock_start = event
            # Evidence.start changes here, once. Simulation time never resets.
            # Keep both raw wall epochs, in their original event order.
            previous_wall = -math.inf
        if sim < previous_sim or wall < previous_wall:
            raise ValueError("Event clocks move backwards outside the explicit episode origin; no reordered playback is inferred")
        counts[kind] += 1
        events.append(event)
        previous_id, previous_sim, previous_wall = event_id, sim, wall
    for event in events:
        event["wall_clock_scope"] = ("unclassified" if clock_start is None else
                                     "initialization" if event["event_id"] < clock_start["event_id"] else "task")
    clock_epochs = []
    for scope in ("initialization", "task", "unclassified"):
        group = [event for event in events if event["wall_clock_scope"] == scope]
        if group:
            clock_epochs.append({"scope": scope, "first_event_id": group[0]["event_id"],
                                 "last_event_id": group[-1]["event_id"],
                                 "first_wall_elapsed_s": group[0]["wall_elapsed_s"],
                                 "last_wall_elapsed_s": group[-1]["wall_elapsed_s"]})
    # Preserve every non-observation event, plus observations referenced by one.
    # Sampled gateway captures never become claims of delivery to the candidate.
    referenced = {parent for e in events if e["event_type"] != "observation" for parent in e.get("parent_ids", [])}
    kept, last_observation, last_capture = [], -math.inf, None
    for event in events:
        if event["event_type"] == "observation":
            last_capture = event
            if event["event_id"] not in referenced and event["sim_time_s"] - last_observation < 1 / observation_hz - 1e-9:
                continue
            last_observation = event["sim_time_s"]
        kept.append(event)
    if last_capture and last_capture not in kept:
        kept.append(last_capture)
        kept.sort(key=lambda e: e["event_id"])
    for event in kept:
        if event["event_type"] == "observation":
            event["artifact_refs"] = {name: artifact_ref(root, event["payload"].get(name), output)
                                      for name in ("rgb", "depth")}
    motion, motion_count, last_time, final_motion, motion_gaps = [], 0, -math.inf, None, []
    previous_motion = None
    if motion_path.exists():
        for sample in read_lines(motion_path):
            stamp = finite(sample.get("sim_time_s"), "motion sim_time_s")
            if previous_motion is not None:
                if stamp <= previous_motion:
                    raise ValueError("Motion times must strictly increase")
                if stamp - previous_motion > .03:
                    motion_gaps.append({"from_s": previous_motion, "to_s": stamp})
            for field in ("q", "dq", "effort", "target", "tcp"):
                if field in sample:
                    if not isinstance(sample[field], list):
                        raise ValueError("Motion " + field + " must be an array")
                    for value in sample[field]:
                        finite(value, "motion " + field)
            motion_count += 1
            final_motion, previous_motion = sample, stamp
            if stamp - last_time >= 1 / motion_hz - 1e-9:
                motion.append(sample)
                last_time = stamp
        if final_motion is not None and (not motion or motion[-1] != final_motion):
            motion.append(final_motion)
    result = strict_json(result_path.read_text(encoding="utf-8")) if result_path.exists() else None
    if result is not None and result.get("run_id") != run_id:
        raise ValueError("Result run identity differs from manifest")
    files = [manifest_path, event_path] + ([motion_path] if motion_path.exists() else []) + ([result_path] if result_path.exists() else [])
    final_hashes = {path.name: digest_file(path) for path in files}
    if initial_hashes != final_hashes:
        raise ValueError("Run source files changed during the build; wait for the writer to close")
    return {"run_id": run_id, "manifest": manifest, "result": result, "events": kept, "motion": motion,
            "source_files": [{"name": path.name, "href": relative_href(path, output),
                              "sha256": final_hashes[path.name], "bytes": path.stat().st_size} for path in files],
            "sampling": {"event_records": len(events), "retained_events": len(kept), "event_type_counts": dict(counts),
                         "observation_target_hz": observation_hz, "observation_rule": "At most one regular capture per interval, plus last capture and observations explicitly parent-linked by non-observation events; no interpolation",
                         "motion_records": motion_count, "retained_motion": len(motion), "motion_target_hz": motion_hz,
                         "motion_rule": "First actual sample at or after each interval, plus final actual sample; no interpolation",
                         "event_gaps": gaps, "motion_intervals_over_30ms": motion_gaps,
                         "wall_clock_epochs": clock_epochs,
                         "episode_clock_started_event_id": clock_start["event_id"] if clock_start else None,
                         "clock_rule": "Raw clocks and event order are unchanged. Wall time has initialization and task epochs only when a supervisor episode_clock_started event declares the boundary; no offset or interpolation is applied. Without that event the wall-clock scope is unclassified. Simulation time remains monotonic across the boundary.",
                         "source_motion_rate_claim_hz": 100,
                         "limitations": ["Gateway capture does not prove candidate delivery", "Latest prior snapshot can be stale", "Images stay linked to local files; missing files do not receive replacements", "This compact export is not the full raw evidence bundle"]}}
