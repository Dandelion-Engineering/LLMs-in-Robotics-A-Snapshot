"""One-shot preservation audit; never runs the accounting refresh or opens active outputs."""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


PACKET = Path(__file__).resolve().parent
REG = PACKET.parent
REPO = Path.cwd().resolve()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def identity(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def matches(binding):
    return identity(binding["path"]) == binding


def save(name, value):
    with (PACKET / name).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def under(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


intent = read(PACKET / "intent.json")
native = read(PACKET / "native-exit.json")
started = read(PACKET / "process-start.json")
before = read(PACKET / "before.json")
after = read(REG / "session14-accounting.json")
provenance = after["refresh_provenance"]
statuses = provenance["official_statuses"]
rows = {row["official_queue"]["id"]: row for row in after["rows"]}
old_rows = {row["official_queue"]["id"]: row for row in before["rows"]}
active_ids = sorted(key for key, row in rows.items() if row["official_queue"]["state"] in ("queued", "running"))
settled_ids = ["20260929T041418803542Z-2f3b6425"]
smoke = rows[settled_ids[0]]
checkpoint = provenance["previous_accounting_checkpoint"]
sweep = provenance["official_status_sweep_receipt"]
baseline_path = (REPO / before["preserved_session13_baseline"]["source_ref"]).resolve()
baseline_bindings = [value for value in before["source_bindings"].values() if Path(value["path"]).resolve() == baseline_path]
binding_objects = list(after["source_bindings"].values()) + list(provenance["current_bindings"].values())
count_keys = [
    "known_qualification_model_invocations_started",
    "diagnostic_only_observed_model_starts_lower_bound",
    "observed_model_starts_lower_bound_from_assessable_and_diagnostic_receipts",
    "observed_turn_start_requests_from_assessable_and_diagnostic_receipts",
]
assert statuses[settled_ids[0]]["state"] == "succeeded" and type(statuses[settled_ids[0]]["exit_status"]) is int and statuses[settled_ids[0]]["exit_status"] == 0
observed = []
for supplied in smoke["model_invocation_receipts"]:
    result_path = Path(supplied["client_result_ref"])
    event_path = Path(supplied["events_ref"])
    for path in (result_path, event_path):
        assert provenance["current_bindings"][str(path)] == identity(path)
    result = read(result_path)
    starts = []
    with event_path.open(encoding="utf-8") as stream:
        for line, text in enumerate(stream, 1):
            event = json.loads(text)
            if event.get("kind") == "request" and event.get("method") == "turn/start":
                starts.append({"line": line, "request_id": event.get("id")})
    assert (result.get("model_started") is True) == bool(starts)
    observed.append({"phase": result_path.parent.parent.relative_to(Path(smoke["evidence_directory"])).as_posix(), "model_started": result.get("model_started") is True, "turn_start_requests": len(starts), "request_records": starts, "client_result_ref": str(result_path), "events_ref": str(event_path)})
observed_count = sum(item["turn_start_requests"] for item in observed)
smoke_artifacts_bound = True
for relative, expected in [("qualification/pilot-stock-024-assessment.json", "a87dc3025fb1212b3969640eeaf185701b201ed0bf8613d443f7332697d6f126"), ("qualification/final-qualification-027/pilot-stock-024/disposition.json", "fc47a1e0c41bfea7eb912327432583352e9095e8887fec5242e77bbf589a439b")]:
    path = REG.parent / relative
    bound = identity(path)
    smoke_artifacts_bound = smoke_artifacts_bound and bound["sha256"] == expected and provenance["current_bindings"].get(str(path)) == bound

checks = {
    "process_exact_int0": type(native["exit_code"]) is int and native["exit_code"] == 0,
    "exact_intended_argv": native["argv"] == intent["argv"] == started["argv"],
    "stdout_stderr_bound": matches(native["stdout"]) and matches(native["stderr"]),
    "helper_unchanged": matches(intent["helper"]) and native["helper_after"] == intent["helper"],
    "history114_unchanged": matches(intent["history_before"]),
    "all19exports_unchanged": len(intent["exports_before"]) == 19 and all(matches(item) for item in intent["exports_before"]),
    "before_copy_exact": matches(intent["before_copy"]) and intent["before_copy"]["sha256"] == intent["accounting_before"]["sha256"],
    "all861_prior_binding_objects_preserved": len(before["source_bindings"]) == 861 and all(after["source_bindings"].get(key) == value for key, value in before["source_bindings"].items()),
    "session13_baseline_preserved": after["preserved_session13_baseline"] == before["preserved_session13_baseline"],
    "session13_source_bytes_unchanged": bool(baseline_bindings) and all(matches(value) for value in baseline_bindings),
    "prior_checkpoint_prefix_preserved": after["prior_accounting_checkpoints"][:-1] == before["prior_accounting_checkpoints"],
    "prior_refresh_history_preserved": after["refresh_history"] == before["refresh_history"],
    "previous_checkpoint_exact": matches(checkpoint) and Path(checkpoint["path"]).read_bytes() == (PACKET / "before.json").read_bytes(),
    "previous_sha_exact": provenance["previous_accounting_sha256"] == intent["accounting_before"]["sha256"],
    "diagnostic_start_observations_preserved": all(after[key] == before[key] for key in ["diagnostic_observed_model_starts", "diagnostic_observed_model_starts_baseline"]),
    "all108_prior_jobs_preserved": len(old_rows) == 108 and set(old_rows).issubset(rows),
    "fresh108_statuses_match_rows": len(statuses) == len(rows) == 108 and all(all(statuses[key].get(field) == value for field, value in row["official_queue"].items()) for key, row in rows.items()),
    "cutoff_matches_completed_authentication": after["as_of"] == provenance["official_status_authenticated_at"] and all(row["official_status_authenticated_at"] == after["as_of"] for row in rows.values()),
    "all_empirical_reads_have_success_gate": all(statuses[key]["state"] == "succeeded" and type(statuses[key]["exit_status"]) is int and statuses[key]["exit_status"] == 0 for key, row in rows.items() if row["empirical_results_consumed"]),
    "official_sweep_exact": matches(sweep) and read(sweep["path"]) == {"created_at": after["as_of"], "official_statuses": statuses},
    "no_active_accounted_jobs": active_ids == [],
    "home024_and_scored_unlaunched": not any(row.get("run_id") == "RCI001-C02-pilot-home-024" or row.get("category") == "scored_model_slot" for row in rows.values()),
    "all39_held_assessment_sources_unchanged": len(intent["assessment_sources_before"]) == 39 and all(matches(value) for value in intent["assessment_sources_before"]),
    "pilot_stock024_original_invalid_unknown_retained": smoke["empirical_results_consumed"] is True and smoke["qualification_or_diagnostic_status"] == "failed" and smoke["admission_error"] == "One-invocation family pilot qualification missing/failed" and smoke["retained_assessment_fields"] == {"validity": "invalid", "task_evidence_valid": False, "task_outcome": "unknown"},
    "prior_terminal_verdicts_preserved": all(rows[key]["qualification_or_diagnostic_status"] == row["qualification_or_diagnostic_status"] for key, row in old_rows.items() if row["official_queue"]["state"] in ("failed", "succeeded")),
    "model_counts_derived_from_observed_requests": all(after["totals"][key] == before["totals"][key] + observed_count for key in count_keys if key != "diagnostic_only_observed_model_starts_lower_bound") and after["totals"]["diagnostic_only_observed_model_starts_lower_bound"] == before["totals"]["diagnostic_only_observed_model_starts_lower_bound"] and after["totals"]["model_invocations_started_total"] is None,
    "pilot_stock024_observed_receipts_reconciled": observed == smoke["model_invocation_receipts"] and smoke["known_model_invocations_started"] == observed_count and {x["phase"] for x in observed} == {"pilot"},
    "pilot_stock024_assessment_and_disposition_original_hashes": smoke_artifacts_bound,
    "zero_scored": all(after["totals"][key] == 0 for key in ["scored_slots_started_in_recorded_registry", "scored_slots_registered", "known_scored_model_invocations_started"]),
    "source_freezes_unchanged": all(item["helper_and_accounting_absent"] is True and matches(item["snapshot"]) and matches(item["archive"]) for item in intent["frozen_source_exclusion"]),
    "canonical_matches_native_exit": identity(REG / "session14-accounting.json") == native["accounting_after"],
}
errors = [key for key, value in checks.items() if value is not True]
now = datetime.now(timezone.utc).isoformat()
accounting = identity(REG / "session14-accounting.json")
qa = {
    "schema": "campaign002-accounting-refresh-qa-1", "at": now,
    "passed": not errors, "checks": checks, "errors": errors,
    "cutoff": after["as_of"], "accounting": accounting,
    "prior_bindings_preserved": len(before["source_bindings"]),
    "current_source_bindings": len(after["source_bindings"]),
    "current_refresh_bindings": len(provenance["current_bindings"]),
    "previous_checkpoint": checkpoint, "official_status_sweep": sweep,
    "totals": after["totals"], "active_accounted_jobs": active_ids,
    "pilot_stock024_metadata": smoke, "storage_scope": after["storage"]["scope"],
    "verification_source": identity(__file__),
}
save("qa.json", qa)
receipt = {
    "schema": "campaign002-accounting-refresh-receipt-1",
    "started_at": native["started_at"], "ended_at": native["ended_at"],
    "intent": identity(PACKET / "intent.json"), "argv": native["argv"],
    "exit_code": native["exit_code"], "stdout": native["stdout"], "stderr": native["stderr"],
    "native_exit": identity(PACKET / "native-exit.json"), "passed": not errors,
    "qa": identity(PACKET / "qa.json"), "accounting": accounting, "cutoff": after["as_of"],
    "before_copy": intent["before_copy"], "helper_before": intent["helper"], "helper_after": native["helper_after"],
    "history_before": intent["history_before"], "history_after": identity(intent["history_before"]["path"]),
    "assessment_sources_before_and_after": intent["assessment_sources_before"],
    "exports_before_and_after": intent["exports_before"], "previous_checkpoint": checkpoint,
    "prior_bindings_preserved": len(before["source_bindings"]),
    "current_source_bindings": len(after["source_bindings"]),
    "current_refresh_bindings": len(provenance["current_bindings"]),
    "totals": after["totals"], "official_status_sweep": sweep, "active_accounted_jobs": active_ids,
    "storage_scope": after["storage"]["scope"], "native_C_free_bytes": after["storage"]["native_C_free_bytes"],
    "limitations": ["Pilot-stock024 was officially succeeded/integer0 before evidence reads; its original invalid/task-unknown assessment remains unchanged. No active accounted job exists at the cutoff.", "Model starts are observed lower bounds; exact service generations, billing and usage limits remain unknown.", "Retained storage is a non-atomic logical census, not allocated bytes, peak usage or causal session growth."],
    "no_tests_model_queue_submissions_or_source_changes": True,
}
save("receipt.json", receipt)
print(json.dumps({"passed": not errors, "checks": len(checks), "errors": errors, "receipt": identity(PACKET / "receipt.json"), "qa": identity(PACKET / "qa.json"), "accounting": accounting, "cutoff": after["as_of"], "totals": after["totals"], "source_bindings": len(after["source_bindings"])}, indent=2))
raise SystemExit(0 if not errors else 1)
