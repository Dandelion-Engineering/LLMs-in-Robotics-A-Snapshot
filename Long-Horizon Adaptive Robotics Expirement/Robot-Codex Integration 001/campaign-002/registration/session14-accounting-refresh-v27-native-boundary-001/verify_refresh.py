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
active_id = "20260929T040035554754Z-4e67aa65"
active = rows[active_id]
active_root = Path(active["evidence_directory"]).parent
active_roots = [active_root / "orchestrator", active_root / "host"]
active_ids = sorted(key for key, row in rows.items() if row["official_queue"]["state"] in ("queued", "running"))
settled_ids = ["20260929T035108044594Z-0996c06c", "20260929T035938575014Z-eec4e520"]
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
checks = {
    "process_exact_int0": type(native["exit_code"]) is int and native["exit_code"] == 0,
    "exact_intended_argv": native["argv"] == intent["argv"] == started["argv"],
    "stdout_stderr_bound": matches(native["stdout"]) and matches(native["stderr"]),
    "helper_unchanged": matches(intent["helper"]) and native["helper_after"] == intent["helper"],
    "history111_unchanged": matches(intent["history_before"]),
    "all19exports_unchanged": len(intent["exports_before"]) == 19 and all(matches(item) for item in intent["exports_before"]),
    "before_copy_exact": matches(intent["before_copy"]) and intent["before_copy"]["sha256"] == intent["accounting_before"]["sha256"],
    "all836_prior_binding_objects_preserved": len(before["source_bindings"]) == 836 and all(after["source_bindings"].get(key) == value for key, value in before["source_bindings"].items()),
    "session13_baseline_preserved": after["preserved_session13_baseline"] == before["preserved_session13_baseline"],
    "session13_source_bytes_unchanged": bool(baseline_bindings) and all(matches(value) for value in baseline_bindings),
    "prior_checkpoint_prefix_preserved": after["prior_accounting_checkpoints"][:-1] == before["prior_accounting_checkpoints"],
    "prior_refresh_history_preserved": after["refresh_history"] == before["refresh_history"],
    "previous_checkpoint_exact": matches(checkpoint) and Path(checkpoint["path"]).read_bytes() == (PACKET / "before.json").read_bytes(),
    "previous_sha_exact": provenance["previous_accounting_sha256"] == intent["accounting_before"]["sha256"],
    "diagnostic_start_observations_preserved": all(after[key] == before[key] for key in ["diagnostic_observed_model_starts", "diagnostic_observed_model_starts_baseline"]),
    "all105_prior_jobs_preserved": len(old_rows) == 105 and set(old_rows).issubset(rows),
    "fresh107_statuses_match_rows": len(statuses) == len(rows) == 107 and all(all(statuses[key].get(field) == value for field, value in row["official_queue"].items()) for key, row in rows.items()),
    "cutoff_matches_completed_authentication": after["as_of"] == provenance["official_status_authenticated_at"] and all(row["official_status_authenticated_at"] == after["as_of"] for row in rows.values()),
    "all_empirical_reads_have_success_gate": all(statuses[key]["state"] == "succeeded" and type(statuses[key]["exit_status"]) is int and statuses[key]["exit_status"] == 0 for key, row in rows.items() if row["empirical_results_consumed"]),
    "official_sweep_exact": matches(sweep) and read(sweep["path"]) == {"created_at": after["as_of"], "official_statuses": statuses},
    "smoke025_metadata_only": active["official_queue"]["state"] == "running" and active["official_queue"]["exit_status"] is None and active["empirical_results_consumed"] is False and active["qualification_or_diagnostic_status"] == "outcome_not_consumed" and active["model_invocation_receipts"] == [] and active["known_model_invocations_started"] is None and active["queue_wall_s"] is None and "current_retained_evidence_storage" not in active,
    "no_smoke025_empirical_bindings": not any(under(item["path"], active_root) for item in binding_objects),
    "smoke025_refs_only_known_submission_metadata": active["source_refs"] == [str((REG.parent / "qualification/RCI001-C02-smoke-025/queue-submit.json").resolve())],
    "smoke025_output_storage_excluded": all(str(root) in after["storage"]["excluded_active_or_failed_output_roots"] for root in active_roots),
    "sole_active_accounted_job": active_ids == [active_id],
    "native026_boundary027_original_passes_retained": all(rows[key]["empirical_results_consumed"] is True and rows[key]["qualification_or_diagnostic_status"] == "passed" and rows[key]["known_model_invocations_started"] == 0 and rows[key]["admission_error"] is None for key in settled_ids) and rows[settled_ids[0]]["retained_assessment_fields"] == {"qualification_passed": True} and rows[settled_ids[1]]["retained_assessment_fields"] == {"qualified": True},
    "prior_terminal_verdicts_preserved": all(rows[key]["qualification_or_diagnostic_status"] == row["qualification_or_diagnostic_status"] for key, row in old_rows.items() if row["official_queue"]["state"] in ("failed", "succeeded")),
    "model_counts_unchanged_no_inference": all(after["totals"][key] == before["totals"][key] for key in count_keys) and after["totals"]["model_invocations_started_total"] is None,
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
    "smoke025_metadata": active, "storage_scope": after["storage"]["scope"],
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
    "exports_before_and_after": intent["exports_before"], "previous_checkpoint": checkpoint,
    "prior_bindings_preserved": len(before["source_bindings"]),
    "current_source_bindings": len(after["source_bindings"]),
    "current_refresh_bindings": len(provenance["current_bindings"]),
    "totals": after["totals"], "official_status_sweep": sweep, "active_accounted_jobs": active_ids,
    "storage_scope": after["storage"]["scope"], "native_C_free_bytes": after["storage"]["native_C_free_bytes"],
    "limitations": ["Smoke025 was active at the authenticated cutoff; its empirical files were not read or hashed and its output roots were excluded from storage.", "Model starts are observed lower bounds; exact service generations, billing and usage limits remain unknown.", "Retained storage is a non-atomic logical census, not allocated bytes, peak usage or causal session growth."],
    "no_tests_model_queue_submissions_or_source_changes": True,
}
save("receipt.json", receipt)
print(json.dumps({"passed": not errors, "checks": len(checks), "errors": errors, "receipt": identity(PACKET / "receipt.json"), "qa": identity(PACKET / "qa.json"), "accounting": accounting, "cutoff": after["as_of"], "totals": after["totals"], "source_bindings": len(after["source_bindings"])}, indent=2))
raise SystemExit(0 if not errors else 1)
