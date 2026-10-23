"""Prepare, execute once after explicit settlement, and audit one accounting refresh."""
import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PACKET = Path(__file__).resolve().parent
REG = PACKET.parent
C = REG.parent
REPO = C.parents[2]
HELPER = REG / "refresh_session14_accounting.py"
ACCOUNTING = REG / "session14-accounting.json"
HISTORY = C / "investigation/qualification-history.json"
HELPER_SHA = "5675db9f1454e1db0f45f4bd0ed642dee5c96d63543e787e1d3c05b74e5ac954"
BEFORE_SHA = "afea9790691202b48223b48e095d574a8d306b1b0a460f988fa4b43c0644c3f6"
HISTORY_SHA = "f46117ad3ac5ae065bb210d057fed4e48dbb0d484019165b89ea6361c0d2ba82"
SETTLED_IDS = ["20260929T060538760771Z-877e2765"]


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def identity(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def matches(item):
    return identity(item["path"]) == item


def save(name, value):
    with (PACKET / name).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def under(path, root):
    return Path(path).resolve().is_relative_to(Path(root).resolve())


def prepare():
    assert identity(HELPER)["sha256"] == HELPER_SHA
    assert identity(ACCOUNTING)["sha256"] == BEFORE_SHA
    assert identity(HISTORY)["sha256"] == HISTORY_SHA
    previous = read(REG / "session14-accounting-refresh-after-smoke026-queue-failure-001/receipt.json")
    exports = previous["exports_before_and_after"]
    assert len(exports) == 19 and all(matches(item) for item in exports)
    old = read(ACCOUNTING)
    assert len(old["source_bindings"]) == 906 and len(old["rows"]) == 114
    snapshot = REPO / "Long-Horizon Adaptive Robotics Expirement/Architecture Map/releases/RCI001-C02-dev-091/snapshot.json"
    frozen = read(snapshot)
    assert frozen["revision"] == "RCI001-C02-dev-091"
    for path in (HELPER, ACCOUNTING, Path(__file__)):
        assert path.relative_to(REPO).as_posix() not in frozen["sources"]
    held_sources = [identity(path) for path in sorted((C / "assessment").glob("*.py"))]
    for item in held_sources:
        name = Path(item["path"]).relative_to(REPO).as_posix()
        assert frozen["sources"].get(name) == {"sha256": item["sha256"], "bytes": item["bytes"]}, name
    diagnostic_input = REG / "diagnostic-start-input-shutdown-003.json"
    diagnostic_binding = identity(diagnostic_input) if diagnostic_input.exists() else None
    with (PACKET / "before.json").open("xb") as stream:
        stream.write(ACCOUNTING.read_bytes())
        stream.flush()
        os.fsync(stream.fileno())
    intent = {
        "schema": "campaign002-accounting-refresh-intent-1", "at": now(),
        "scope": "Exactly one unchanged-helper refresh after Native003 failed queue; no failed raw outputs or scientific outcomes consumed; explicit retained diagnostic start input only",
        "failed_queue_freshly_authenticated": True,
        "argv": [str(REPO / "venv/Scripts/python.exe"), "-X", "utf8", "-B", str(HELPER), "--refresh"],
        "cwd": str(REPO), "helper": identity(HELPER),
        "accounting_before": identity(ACCOUNTING), "before_copy": identity(PACKET / "before.json"),
        "history_before": identity(HISTORY), "exports_before": exports,
        "frozen_source_exclusion": [{"snapshot": identity(snapshot), "archive": identity(snapshot.with_name("code.zip")), "helper_and_accounting_absent": True}],
        "assessment_sources_before": held_sources, "diagnostic_start_input": diagnostic_binding,
        "prior_binding_count": 906, "prior_job_count": 114,
        "failed_queue_job_ids": SETTLED_IDS,
        "native003_job_id": SETTLED_IDS[-1],
        "preparation_source": identity(__file__),
        "active_outputs_read": False,
    }
    save("intent.json", intent)
    print(json.dumps({"prepared": True, "executed": False, "intent": identity(PACKET / "intent.json")}, indent=2))


def execute(job_id):
    assert job_id == SETTLED_IDS[-1], "Exact failed Native003 identity required"
    intent = read(PACKET / "intent.json")
    assert not (PACKET / "process-start.json").exists(), "Refresh is single-use; reconcile any earlier attempt"
    assert all(matches(intent[key]) for key in ("helper", "accounting_before", "before_copy", "history_before", "preparation_source"))
    assert all(matches(item) for item in intent["exports_before"])
    save("settlement-trigger.json", {"at": now(), "failed_smoke_job_id": job_id, "scope": "Root failed-queue notice received; unchanged helper must still freshly authenticate all jobs before permitted outputs"})
    started = now()
    save("process-start.json", {"started_at": started, "argv": intent["argv"], "cwd": intent["cwd"], "launcher": identity(__file__)})
    with (PACKET / "stdout.txt").open("xb") as stdout, (PACKET / "stderr.txt").open("xb") as stderr:
        result = subprocess.run(intent["argv"], cwd=intent["cwd"], stdout=stdout, stderr=stderr, check=False)
    native = {"started_at": started, "ended_at": now(), "argv": intent["argv"], "exit_code": result.returncode,
              "stdout": identity(PACKET / "stdout.txt"), "stderr": identity(PACKET / "stderr.txt"),
              "helper_after": identity(HELPER), "accounting_after": identity(ACCOUNTING)}
    save("native-exit.json", native)
    print(json.dumps(native, indent=2))
    return result.returncode


def verify():
    intent, native = read(PACKET / "intent.json"), read(PACKET / "native-exit.json")
    before, after = read(PACKET / "before.json"), read(ACCOUNTING)
    provenance = after["refresh_provenance"]
    statuses = provenance["official_statuses"]
    rows = {row["official_queue"]["id"]: row for row in after["rows"]}
    old_rows = {row["official_queue"]["id"]: row for row in before["rows"]}
    active = [row for row in rows.values() if row["official_queue"]["state"] in ("queued", "running", "cancel_requested")]
    bindings = list(after["source_bindings"].values()) + list(provenance["current_bindings"].values())
    checkpoint = provenance["previous_accounting_checkpoint"]
    sweep = provenance["official_status_sweep_receipt"]
    baseline_path = (REPO / before["preserved_session13_baseline"]["source_ref"]).resolve()
    baseline = [value for value in before["source_bindings"].values() if Path(value["path"]).resolve() == baseline_path]
    active_exclusion = True
    for row in active:
        root = Path(row["evidence_directory"])
        active_exclusion &= row["empirical_results_consumed"] is False and row["model_invocation_receipts"] == []
        active_exclusion &= row["known_model_invocations_started"] is None and "current_retained_evidence_storage" not in row
        active_exclusion &= not any(under(item["path"], root) for item in bindings)
    smoke = rows[SETTLED_IDS[0]]
    smoke_root = Path(smoke["evidence_directory"]).parent
    excluded_roots = [smoke_root / "orchestrator", smoke_root / "host"]
    new_observations = {key:value for key,value in after["diagnostic_observed_model_starts"].items() if key not in before["diagnostic_observed_model_starts"]}
    expected_delta = 1 if intent["diagnostic_start_input"] else 0
    input_check = (not new_observations) if not expected_delta else (set(new_observations) == {SETTLED_IDS[0]} and new_observations[SETTLED_IDS[0]]["input"] == intent["diagnostic_start_input"] and matches(intent["diagnostic_start_input"]) and new_observations[SETTLED_IDS[0]]["observation"] == {"json_pointer":"/client_completion/model_started", "value":True, "observed_model_starts_lower_bound":1, "scope":"diagnostic_only", "qualification":"unassessed", "task_outcome":"unknown"})
    checks = {
        "process_exact_int0": type(native["exit_code"]) is int and native["exit_code"] == 0,
        "exact_argv": native["argv"] == intent["argv"] == read(PACKET / "process-start.json")["argv"],
        "stdout_stderr_bound": matches(native["stdout"]) and matches(native["stderr"]),
        "helper_unchanged": matches(intent["helper"]) and native["helper_after"] == intent["helper"],
        "history121_unchanged": matches(intent["history_before"]),
        "all19exports_unchanged": len(intent["exports_before"]) == 19 and all(matches(item) for item in intent["exports_before"]),
        "before_copy_exact": matches(intent["before_copy"]) and intent["before_copy"]["sha256"] == BEFORE_SHA,
        "all906_prior_binding_objects_preserved": len(before["source_bindings"]) == 906 and all(after["source_bindings"].get(key) == value for key, value in before["source_bindings"].items()),
        "session13_preserved": after["preserved_session13_baseline"] == before["preserved_session13_baseline"] and bool(baseline) and all(matches(item) for item in baseline),
        "prior_checkpoint_prefix_preserved": after["prior_accounting_checkpoints"][:-1] == before["prior_accounting_checkpoints"],
        "prior_refresh_history_preserved": after["refresh_history"] == before["refresh_history"],
        "previous_checkpoint_exact": matches(checkpoint) and Path(checkpoint["path"]).read_bytes() == (PACKET / "before.json").read_bytes() and provenance["previous_accounting_sha256"] == BEFORE_SHA,
        "diagnostic_starts_preserved": after["diagnostic_observed_model_starts_baseline"] == before["diagnostic_observed_model_starts_baseline"] and all(after["diagnostic_observed_model_starts"].get(key) == value for key,value in before["diagnostic_observed_model_starts"].items()),
        "all114_prior_jobs_preserved": len(old_rows) == 114 and set(old_rows).issubset(rows),
        "fresh_statuses_match_rows": len(statuses) == len(rows) and all(all(statuses[key].get(field) == value for field, value in row["official_queue"].items()) for key, row in rows.items()),
        "cutoff_matches_authentication": after["as_of"] == provenance["official_status_authenticated_at"] and all(row["official_status_authenticated_at"] == after["as_of"] for row in rows.values()),
        "all_empirical_reads_have_success_gate": all(statuses[key]["state"] == "succeeded" and type(statuses[key]["exit_status"]) is int and statuses[key]["exit_status"] == 0 for key, row in rows.items() if row["empirical_results_consumed"]),
        "official_sweep_exact": matches(sweep) and read(sweep["path"]) == {"created_at": after["as_of"], "official_statuses": statuses},
        "failed_native003_metadata_only": smoke["official_queue"]["state"] == "failed" and type(smoke["official_queue"]["exit_status"]) is int and smoke["official_queue"]["exit_status"] == 1 and smoke["empirical_results_consumed"] is False and smoke["qualification_or_diagnostic_status"] == "outcome_not_consumed" and smoke["known_model_invocations_started"] is None and smoke["model_invocation_receipts"] == [] and "current_retained_evidence_storage" not in smoke,
        "failed_native003_no_empirical_bindings": not any(under(item["path"], smoke_root) for item in bindings),
        "failed_output_storage_excluded": all(str(root) in after["storage"]["excluded_active_or_failed_output_roots"] for root in excluded_roots),
        "diagnostic_input_exact": input_check,
        "no_active_jobs": active == [],
        "all_frozen_assessment_sources_unchanged": all(matches(item) for item in intent["assessment_sources_before"]),
        "prior_terminal_verdicts_preserved": all(rows[key]["qualification_or_diagnostic_status"] == row["qualification_or_diagnostic_status"] for key, row in old_rows.items() if row["official_queue"]["state"] in ("failed", "succeeded")),
        "active_outputs_excluded": active_exclusion,
        "model_counts_only_diagnostic_lower_bound": after["totals"]["known_qualification_model_invocations_started"] == before["totals"]["known_qualification_model_invocations_started"] and after["totals"]["observed_turn_start_requests_from_assessable_and_diagnostic_receipts"] == before["totals"]["observed_turn_start_requests_from_assessable_and_diagnostic_receipts"] and all(after["totals"][key] == before["totals"][key] + expected_delta for key in ("diagnostic_only_observed_model_starts_lower_bound", "observed_model_starts_lower_bound_from_assessable_and_diagnostic_receipts")) and after["totals"]["model_invocations_started_total"] is None,
        "zero_scored": all(after["totals"][key] == 0 for key in ("scored_slots_started_in_recorded_registry", "scored_slots_registered", "known_scored_model_invocations_started")),
        "source_freezes_unchanged": all(item["helper_and_accounting_absent"] is True and matches(item["snapshot"]) and matches(item["archive"]) for item in intent["frozen_source_exclusion"]),
        "canonical_matches_native_exit": identity(ACCOUNTING) == native["accounting_after"],
    }
    errors = [key for key, value in checks.items() if value is not True]
    common = {"passed": not errors, "cutoff": after["as_of"], "accounting": identity(ACCOUNTING), "totals": after["totals"], "prior_bindings_preserved": len(before["source_bindings"]), "current_source_bindings": len(after["source_bindings"]), "current_refresh_bindings": len(provenance["current_bindings"]), "active_accounted_jobs": [row["official_queue"]["id"] for row in active], "previous_checkpoint": checkpoint, "official_status_sweep": sweep, "storage_scope": after["storage"]["scope"]}
    save("qa.json", {"schema": "campaign002-accounting-refresh-qa-1", "at": now(), **common, "checks": checks, "errors": errors, "verification_source": identity(__file__)})
    save("receipt.json", {"schema": "campaign002-accounting-refresh-receipt-1", **common, "intent": identity(PACKET / "intent.json"), "native_exit": identity(PACKET / "native-exit.json"), "qa": identity(PACKET / "qa.json"), "argv": native["argv"], "exit_code": native["exit_code"], "stdout": native["stdout"], "stderr": native["stderr"], "history_before_and_after": intent["history_before"], "exports_before_and_after": intent["exports_before"], "helper_before_and_after": intent["helper"], "before_copy": intent["before_copy"], "diagnostic_start_input": intent["diagnostic_start_input"], "assessment_sources_before_and_after": intent["assessment_sources_before"], "limitations": ["Exact service generations, billing and usage limits remain unknown; model starts are observed lower bounds.", "Retained storage is a non-atomic logical census, not allocated bytes, peak usage or causal session growth."], "no_tests_model_queue_submissions_or_source_changes": True})
    print(json.dumps({**common, "checks": len(checks), "errors": errors, "receipt": identity(PACKET / "receipt.json"), "qa": identity(PACKET / "qa.json")}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare", action="store_true")
    group.add_argument("--execute-after-failed-gate")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        prepare()
    elif args.execute_after_failed_gate:
        raise SystemExit(execute(args.execute_after_failed_gate))
    else:
        raise SystemExit(verify())
