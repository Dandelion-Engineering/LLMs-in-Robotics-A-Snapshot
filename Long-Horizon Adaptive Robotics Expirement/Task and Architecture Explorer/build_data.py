"""Small, read-only derivative of the four predeclared C01 Investigation007 traces.

This never imports the simulator, runs a policy, changes an assessment, or reads
the multi-gigabyte raw streams. Exact model/file evidence is stored lazily;
display projections retain links to every original authenticated codec payload.
Run with the project Python and -B. Output URLs are relative to index.html.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import quote, unquote


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
SOURCE = EXPERIMENT / "Engineering Investigation 007" / "site-r4-003"
sys.path.insert(0, str(SOURCE.parent))
import trace_package  # noqa: E402; authenticated read_value only


def encoded(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False,
                      separators=(",", ":")).encode("ascii")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def href(path):
    return quote(Path(os.path.relpath(Path(path).resolve(), HERE)).as_posix(), safe="/.")


def source_ref(ref):
    """Rebase an existing reference without claiming to have checked image bytes."""
    out = dict(ref)
    if out.get("href"):
        out["href"] = href(SOURCE / unquote(out["href"]))
    return out


def read_manifest(ref):
    raw = (SOURCE / ref["href"]).read_bytes()
    if len(raw) != ref["bytes"] or digest(raw) != ref["sha256"]:
        raise ValueError("Original trace manifest hash mismatch")
    return json.loads(raw)


class Output:
    def __init__(self):
        self.directory = HERE / "data"
        (self.directory / "payloads").mkdir(parents=True, exist_ok=True)
        self.refs = {}

    def exact(self, value):
        raw = encoded(value)
        key = digest(raw)
        path = self.directory / "payloads" / (key + ".json")
        if path.exists():
            if path.read_bytes() != raw:
                raise ValueError("Existing content-addressed payload differs")
        else:
            path.write_bytes(raw)
        ref = {"href": href(path), "sha256": key, "bytes": len(raw)}
        self.refs[key] = ref
        return ref

    def document(self, name, value):
        raw = encoded(value)
        if len(raw) > 30 * 1024 * 1024:
            raise ValueError("Episode document exceeds the 30 MiB display budget")
        path = self.directory / name
        path.write_bytes(raw)
        if json.loads(path.read_bytes()) != value:
            raise ValueError("Output JSON round trip differs")
        return {"href": href(path), "sha256": digest(raw), "bytes": len(raw)}


def compact_world(value):
    return {
        "audience": "operator only; privileged evaluator state, never candidate input",
        "sim_time": value["sim_time"],
        "objects": {name: {key: item[key] for key in
                           ("pos", "recipe", "cycles", "inspection") if key in item}
                    for name, item in value["objects"].items()},
        "qpos": value["qpos"], "station": value["station"],
    }


def compact_observation(value):
    packet = value["packet"]
    keys = ("run_id", "incarnation", "sequence", "sim_time", "sim_tick",
            "capture_sim_time_s", "capture_wall_elapsed_s", "capture_sequence",
            "delivery_sim_time_s", "delivery_wall_elapsed_s", "camera_frame_age_sim_s",
            "sensor_quality", "order", "process_contract", "detections", "station",
            "gripper", "inspection", "joints", "camera_metadata_status")
    result = {"packet": {key: packet[key] for key in keys if key in packet}}
    for key in ("camera", "capture_sim_time_s", "capture_wall_elapsed_s",
                "delivery_sim_time_s", "delivery_wall_elapsed_s", "worker_duration_s"):
        if key in value:
            result[key] = value[key]
    return result


def changed_fields(previous, current):
    """Top-level checkpoint state differences, not inferred model attribution."""
    if previous is None:
        return sorted(current)
    return sorted(key for key in set(previous) | set(current)
                  if previous.get(key) != current.get(key))


def build_episode(check, output, package_ref):
    manifest = read_manifest(check["package"]["manifest"])
    if not check["lossless_roundtrip_equal"] or not check["full_metadata_roundtrip_equal"]:
        raise ValueError("Source build did not assert its preserved trace round trip")
    metadata = trace_package.read_value(manifest["metadata_ref"], SOURCE)
    architecture = metadata["manifest"]["architecture"]
    expected_id = "batch01-eval-r4-C01-rep1-" + architecture + "-persistent"
    if check["run_id"] != expected_id or architecture not in ("baseline", "A1", "A2", "A3"):
        raise ValueError("Unexpected selection: only the four fixed C01 slots are permitted")
    motion = trace_package.read_value(manifest["motion_ref"], SOURCE)
    events, filesystem, contexts, calls = [], [], [], []
    pending_calls = {}
    previous_states = {}
    lazy_refs = {}

    def exact(value):
        ref = output.exact(value)
        lazy_refs[ref["sha256"]] = ref
        return ref

    for header in manifest["event_headers"]:
        payload = trace_package.read_value(header["payload_ref"], SOURCE)
        event = {key: header[key] for key in
                 ("event_id", "event_type", "source", "sim_time_s", "sim_tick",
                  "wall_elapsed_s", "wall_clock_scope", "parent_ids", "payload_sha256")}
        event["source_codec_ref"] = source_ref(header["payload_ref"])
        kind = header["event_type"]
        if "artifact_refs" in header:
            event["artifact_refs"] = {key: source_ref(ref)
                                      for key, ref in header["artifact_refs"].items()}
        if kind in ("initial_world", "world_snapshot", "final_world"):
            event["payload"] = compact_world(payload)
            event["payload_is_projection"] = True
        elif kind == "observation":
            event["payload"] = compact_observation(payload)
            event["payload_is_projection"] = True
        elif kind == "model_request":
            event["payload_ref"] = exact(payload)
            event["payload"] = {"message_roles": [m["role"] for m in payload["messages"]],
                                "message_characters": [len(m["content"]) for m in payload["messages"]]}
            call = {"request_event_id": event["event_id"], "request_sim_time_s": event["sim_time_s"],
                    "request_wall_elapsed_s": event["wall_elapsed_s"], "input_ref": event["payload_ref"],
                    "parent_ids": event["parent_ids"], "response_event_id": None,
                    "response_sim_time_s": None, "output_ref": None, "status": "no recorded response"}
            pending_calls[event["event_id"]] = call
            calls.append(call)
        elif kind in ("model_response", "late_model_response", "model_error"):
            event["payload_ref"] = exact(payload)
            event["payload"] = {key: payload[key] for key in
                                ("stale", "after_episode_end", "original_incarnation",
                                 "current_incarnation", "error") if key in payload}
            parents = [pid for pid in event["parent_ids"] if pid in pending_calls]
            if len(parents) > 1:
                raise ValueError("Model response has ambiguous request parents")
            if parents:
                call = pending_calls[parents[0]]
                if call["response_event_id"] is not None:
                    raise ValueError("Multiple model responses for a single request")
                call.update(response_event_id=event["event_id"], response_sim_time_s=event["sim_time_s"],
                            response_wall_elapsed_s=event["wall_elapsed_s"], output_ref=event["payload_ref"],
                            status=kind, stale=payload.get("stale"),
                            after_episode_end=payload.get("after_episode_end"))
        elif kind in ("candidate_reply", "late_candidate_reply", "retired_candidate_reply"):
            nested = []
            for index, item in enumerate(payload.get("events", [])):
                row = {"event_id": event["event_id"], "candidate_event_index": index,
                       "sim_time_s": event["sim_time_s"], "wall_elapsed_s": event["wall_elapsed_s"],
                       "type": item["type"], "candidate": item.get("candidate"),
                       "time_scope": "supervisor receipt of enclosing candidate reply; individual file operation time was not recorded"}
                if item["type"] in ("context_write", "context_read"):
                    raw = item["content_utf8"].encode("utf-8")
                    if digest(raw) != item["sha256"] or len(raw) != item["byte_count"]:
                        raise ValueError("Recorded context content does not match its original hash/size")
                    row.update({key: item[key] for key in
                                ("path", "sha256", "byte_count", "state_sha256", "durability") if key in item})
                    row["sandbox_path"] = "/work/" + item["path"]
                    row["evidence_path"] = href(EXPERIMENT / "Evidence" / "releases" / "batch01-eval-r4" /
                                                  "attempts" / expected_id / "evidence" / "candidate_state" / item["path"])
                    row["payload_ref"] = exact(item)
                    state = json.loads(item["content_utf8"]).get("state", {})
                    row["changed_fields"] = changed_fields(previous_states.get(item["path"]), state)
                    if item["type"] == "context_write":
                        previous_states[item["path"]] = state
                    filesystem.append(row)
                    nested.append(row)
                elif item["type"] in ("model_context_supplied", "model_output_received"):
                    row["payload_ref"] = exact(item)
                    row.update({key: item[key] for key in ("state_sha256", "context_sha256") if key in item})
                    contexts.append(row)
                    nested.append(row)
                elif len(encoded(item)) <= 4096:
                    nested.append({**row, "payload": item})
                else:
                    nested.append({**row, "payload_ref": exact(item)})
            response = payload.get("response") or {}
            event["payload"] = {"type": payload.get("type"), "response_type": response.get("type"),
                                "supervisor_input_event_id": payload.get("supervisor_input_event_id"), "events": nested}
            event["payload_is_projection"] = True
        elif kind == "candidate_input":
            message = payload.get("message", {})
            packet = message.get("packet") or {}
            event["payload"] = {"message_type": message.get("type"),
                                "packet_sequence": packet.get("sequence"),
                                "incarnation": message.get("incarnation", packet.get("incarnation"))}
            event["payload_is_projection"] = True
        elif len(encoded(payload)) <= 16384:
            event["payload"] = payload
        else:
            event["payload_ref"] = exact(payload)
            event["payload"] = {"keys": list(payload) if isinstance(payload, dict) else [],
                                "display": "Exact payload available on demand"}
        events.append(event)

    start_event = next(e for e in events if e["event_type"] == "episode_clock_started")
    end_event = next(e for e in events if e["event_type"] == "final_world")
    start_sim_time = start_event["sim_time_s"]
    end_sim_time = end_event["sim_time_s"]
    duration_sim_time_s = end_sim_time - start_sim_time
    if abs(duration_sim_time_s - metadata["result"]["sim_duration_s"]) > 1e-8:
        raise ValueError("Final world endpoint and recorded simulation duration disagree")
    for event in events:
        event["after_physical_end"] = event["event_id"] > end_event["event_id"]
    for call in calls:
        call["response_after_physical_end"] = (call["response_event_id"] is not None
                                                and call["response_event_id"] > end_event["event_id"])
    episode = {
        "schema_version": "task-architecture-explorer-episode-1.0", "id": expected_id,
        "architecture": architecture, "duration": duration_sim_time_s,
        "duration_sim_time_s": duration_sim_time_s,
        "wall_duration_s": metadata["result"]["wall_duration_s"],
        "start_sim_time": start_sim_time, "end_sim_time": end_sim_time,
        "physical_end_event_id": end_event["event_id"],
        "endpoint_basis": "Original final_world event; cleanup events can share its simulation time and are explicitly marked after_physical_end by event order.",
        "manifest": metadata["manifest"], "result": metadata["result"],
        "sampling": metadata["sampling"], "motion": motion, "events": events,
        "filesystem": filesystem, "contexts": contexts, "model_calls": calls,
        "provenance": {
            "source_package": package_ref,
            "trace_manifest": source_ref(check["package"]["manifest"]),
            "exact_metadata": source_ref(manifest["metadata_ref"]),
            "original_source_files": [source_ref(ref) for ref in metadata["source_files"]],
            "selection_entry": metadata["selection_entry"],
            "projection": "Display-only derivative of four predeclared C01 replicate-1 persistent slots; no outcome-based replacement, new experiment, assessment, or analysis.",
            "model_evidence": "input_ref is the complete recorded request (messages and schema); output_ref is the complete recorded response. Responses match only through original parent event IDs.",
            "filesystem_evidence": "Wrapper-recorded context writes and reads contain exact UTF-8 content and hashes. Candidate framework code performs atomic checkpoint writes; the LLM does not directly write these files. changed_fields compares top-level saved state keys only and does not establish what caused a change.",
            "time_evidence": "Simulation and wall times are original supervisor event clocks. Nested candidate events have receipt time only, not independent operation timestamps. File read, stored state, supplied model context, and causal influence are distinct.",
            "render_evidence": "Original overhead RGB frames are recorded imagery. Alternate views reconstruct privileged evaluator poses (1 Hz) and arm motion (5 Hz); they are not recorded images. Sample-and-hold can show latest samples with ages, without inferring intervening trajectories.",
            "scope": "Projected observations omit repeated feedback history; candidate reply envelopes omit duplicate responses. Their original exact authenticated codec references remain on each event.",
            "source_roundtrip_claim": {key: check[key] for key in
                                      ("lossless_roundtrip_equal", "full_metadata_roundtrip_equal", "metadata_sha256")},
        },
    }
    for event in events:
        if event.get("payload_is_projection"):
            event["projection_sha256"] = digest(encoded(event["payload"]))
    ref = output.document(architecture + ".json", episode)
    row = {"id": expected_id, "architecture": architecture, **ref,
           "duration": episode["duration"], "duration_sim_time_s": duration_sim_time_s,
           "wall_duration_s": episode["wall_duration_s"],
           "start_sim_time": start_sim_time, "end_sim_time": end_sim_time,
           "lazy_payload_count": len(lazy_refs), "lazy_payload_bytes": sum(x["bytes"] for x in lazy_refs.values()),
           "events": len(events), "model_calls": len(calls), "file_events": len(filesystem)}
    print(json.dumps(row))
    return row


def main():
    package_path = SOURCE / "package-manifest.json"
    raw = package_path.read_bytes()
    package = json.loads(raw)
    package_ref = {"href": href(package_path), "sha256": digest(raw), "bytes": len(raw)}
    declarations = package["trace_selection"]["runs"][:4]
    checks = package["trace_checks"][:4]
    if [x["run_id"] for x in declarations] != [x["run_id"] for x in checks]:
        raise ValueError("Original fixed selection and package trace order differ")
    output = Output()
    episodes = [build_episode(check, output, package_ref) for check in checks]
    if package_path.read_bytes() != raw:
        raise ValueError("Source package manifest changed during extraction")
    builder_raw = Path(__file__).read_bytes()
    index = {"schema_version": "task-architecture-explorer-index-1.0", "episodes": episodes,
             "selection_basis": package["trace_selection"]["selection_basis"],
             "declared_at": package["trace_selection"]["declared_at"],
             "source_package": package_ref,
             "builder": {"href": "build_data.py", "sha256": digest(builder_raw), "bytes": len(builder_raw)},
             "lazy_payload_count": len(output.refs),
             "lazy_payload_bytes": sum(ref["bytes"] for ref in output.refs.values())}
    print(json.dumps({"index": output.document("index.json", index)}))


if __name__ == "__main__":
    main()
