"""Read a finalized complete evaluation index; never load its full run reports."""
from collections import Counter
import copy
import math
from pathlib import Path
import re

from analysis_adapter import read_object, source_ref
from evidence_adapter import digest_file
from administrative_projection import (ADMINISTRATIVE, is_administrative, selection_accounting, derived_counts, processing_complete)

KINDS = ("diagnostics", "continuity")
ROW_STATUSES = {"completed", "partial_failure", "missing_terminal", "missing_evidence",
                "verification_failed", "integrity_failed", ADMINISTRATIVE}


def verify_reference(reference, *, base=None, expected=None):
    if not isinstance(reference, dict) or not isinstance(reference.get("path"), str):
        raise ValueError("Missing artifact path")
    path = Path(reference["path"])
    if not path.is_absolute():
        if base is None: raise ValueError("Artifact requires an absolute path")
        path = Path(base) / path
    path = path.resolve()
    if expected is not None and path != Path(expected).resolve():
        raise ValueError("Artifact names a different file")
    if not re.fullmatch(r"[0-9a-f]{64}", str(reference.get("sha256", ""))):
        raise ValueError("Missing artifact SHA-256")
    if not path.is_file() or digest_file(path) != reference["sha256"]:
        raise ValueError("Artifact bytes differ: " + path.name)
    if "bytes" in reference and (type(reference["bytes"]) is not int or path.stat().st_size != reference["bytes"]):
        raise ValueError("Artifact byte count differs: " + path.name)
    return path


def verify_receipt(path, job_id, *, completed, script_path, output_dir):
    receipt = read_object(path)
    expected = ("succeeded", 0) if completed else ("failed", 1)
    if (receipt.get("id") != job_id or type(receipt.get("exit_status")) is not int
            or (receipt.get("state"), receipt.get("exit_status")) != expected
            or not receipt.get("ended_at")):
        raise ValueError("Official derivation receipt does not match finalized index")
    argv = receipt.get("argv", [])
    try:
        actual_output = Path(argv[argv.index("--output-dir") + 1]).resolve()
    except (ValueError, IndexError, TypeError) as exc:
        raise ValueError("Receipt lacks exact output directory") from exc
    if actual_output != Path(output_dir).resolve() or not any(Path(str(arg)).resolve() == Path(script_path).resolve() for arg in argv):
        raise ValueError("Receipt names another derivation command")
    return receipt


def read_derivatives(path, receipt_path, output, *, canonical_files=None, paired_analysis=None):
    if path is None:
        if receipt_path is not None: raise ValueError("Evaluation receipt requires its index")
        return {"state": "unavailable", "reason": "No completed evaluation diagnostic index supplied.", "runs": []}
    if receipt_path is None: raise ValueError("Evaluation index requires its retained official receipt")
    path = Path(path).resolve()
    index_source = source_ref(path, output)
    index = read_object(path)
    administrative_schema = index.get("schema_version") == "evaluation-derived-administrative-batch-1.0"
    if not administrative_schema and index.get("schema_version") != "evaluation-derived-batch-1.0":
        raise ValueError("Unsupported evaluation diagnostic index schema")
    if index.get("status") not in ("completed", "partial_failure", "integrity_failed"):
        raise ValueError("Evaluation diagnostic index is not finalized")
    verify_receipt(receipt_path, index.get("derivation_queue_job_id"),
                   completed=index["status"] == "completed", script_path=(Path(__file__).parent if administrative_schema else Path(__file__).parent.parent / "Engineering Investigation 004") / "process_evaluation.py", output_dir=path.parent)
    release_path = verify_reference(index.get("release"))
    release = read_object(release_path)
    planned_ids = [item["run_id"] for item in release.get("manifest_refs", [])]
    for item in release.get("manifest_refs", []):
        manifest_path = verify_reference(item, base=release_path.parent)
        if not manifest_path.is_relative_to(release_path.parent): raise ValueError("Planned manifest escapes release")
    rows = index.get("runs", [])
    if (index.get("planned_runs") != 264 or len(rows) != 264 or len(planned_ids) != 264
            or len(set(planned_ids)) != 264 or {r.get("run_id") for r in rows} != set(planned_ids)
            or len({r.get("run_id") for r in rows}) != 264):
        raise ValueError("Diagnostic index must retain every one of the 264 planned identities")
    selected_path = verify_reference(index.get("selected_results"), expected=path.parent / "selected-results.json")
    selected = read_object(selected_path)
    if selected.get("release") != index["release"] or selected.get("canonical_map") != index.get("canonical_map"):
        raise ValueError("Selected results differ from diagnostic authority")
    disposition_counts = selection_accounting(selected)
    if administrative_schema != (selected.get("schema_version") == "selected-evaluation-results-administrative-1"):
        raise ValueError("Index and selection use different accounting schemas")
    if administrative_schema:
        authorization = index.get("queue_authorization_implementation")
        expected_authorization = Path(__file__).parent.parent / "Runtime Recovery 001" / "recovery_runner.py"
        authorization_path = verify_reference(authorization, expected=expected_authorization)
        if index.get("implementation", {}).get(str(authorization_path)) != authorization:
            raise ValueError("Queue authorization differs from recorded implementation inventory")
        for source in selected.get("control_sources", []):
            verify_reference(source)
            if index.get("protected_control_sources", {}).get(source["path"]) != source:
                raise ValueError("Supplemental control source is not bound by the diagnostic index")
        for key in ("recovery_annex_ref", "recovery_source_index_ref"):
            if index.get(key) != selected.get(key): raise ValueError("Diagnostic supplemental authority differs from selection")
            if selected.get(key) is not None: verify_reference(selected[key], base=selected_path.parent)
    selected_provenance = {row["run_id"]: row for row in selected.get("provenance", [])}
    selected_rows = selected.get("results", [])
    by_selected = {r["run_id"]: r for r in selected_rows}
    if len(by_selected) != len(selected_rows) or not set(by_selected) <= set(planned_ids):
        raise ValueError("Selected results repeat or change planned identities")
    if {row["run_id"] for row in selected.get("missing", [])} != set(planned_ids) - set(by_selected):
        raise ValueError("Missing dispositions differ from the planned identities")
    selection = read_object(path.parent / "selection.json")
    if any(index.get(key) != value for key, value in selection.items()):
        raise ValueError("Final diagnostic index differs from its retained selection")
    stale_map = canonical_files is not None and index["canonical_map"].get("files") != canonical_files
    if stale_map and index["status"] != "integrity_failed":
        raise ValueError("Canonical map changed since evaluation derivation; retain a fresh diagnostic index")
    if (bool(index.get("global_integrity_errors")) != (index["status"] == "integrity_failed")
            or (index["status"] != "integrity_failed" and
                (index["status"] == "completed") != (processing_complete(rows) if administrative_schema else all(r.get("status") == "completed" for r in rows)))):
        raise ValueError("Final processing status disagrees with retained errors and run statuses")

    from process_evaluation import summarize, METRICS, COVERAGE
    converted = []
    for row in rows:
        rid = row["run_id"]
        if not isinstance(rid, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", rid) or rid in (".", ".."):
            raise ValueError("Unsafe planned run identity")
        if row.get("plan", {}).get("run_id") != rid or row.get("selected_result") != by_selected.get(rid):
            raise ValueError("Run plan or selected canonical result differs from index identity")
        expected_terminal = (ADMINISTRATIVE if is_administrative(by_selected.get(rid)) else "selected" if rid in by_selected else "missing")
        if row.get("terminal_disposition") != expected_terminal or row.get("status") not in ROW_STATUSES:
            raise ValueError("Run status or terminal accounting disagrees")
        if row.get("source_integrity") not in ("verified", "unverified", "not_processed"):
            raise ValueError("Unknown run source-integrity status")
        if row["plan"].get("paired_block_id") in index.get("excluded_paired_blocks", {}):
            if row.get("primary_disposition") != "paired_block_infrastructure_invalid":
                raise ValueError("Whole-block exclusion was not propagated")
        view = {key: copy.deepcopy(row.get(key)) for key in
                ("run_id", "plan", "terminal_disposition", "selected_result", "primary_disposition", "status",
                 "source_integrity", "primary_derivative_eligible", "errors", "missing_evidence_files")}
        provenance = selected_provenance.get(rid)
        if provenance is not None:
            if row.get("selection_provenance") != {key: value for key, value in provenance.items() if key != "selected_assessment"}:
                raise ValueError("Run selection provenance differs from source-bound selection")
            view["selection_provenance"] = copy.deepcopy(row["selection_provenance"])
            view["selection_sources"] = []
            for key in ("administrative_disposition", "recovery_annex_ref", "official_queue_receipt", "terminal"):
                if provenance.get(key) is not None:
                    reference = verify_reference(provenance[key], base=selected_path.parent)
                    view["selection_sources"].append({"label": key.replace("_", " "), "source": source_ref(reference, output)})
        if expected_terminal == ADMINISTRATIVE:
            if row["status"] != ADMINISTRATIVE or row.get("errors") or (row["source_integrity"] != "not_processed" and index["status"] != "integrity_failed"):
                raise ValueError("Administrative interruption must remain expected unavailable, not a completed or failed derivation")
        view["derived"] = {}
        for kind in KINDS:
            item = row.get("derived", {}).get(kind, {})
            if item.get("status") not in ("completed", "failed", "unavailable"):
                raise ValueError("Unknown derivative status")
            eligible = (row.get("primary_disposition") == "eligible" and row["source_integrity"] == "verified"
                        and item["status"] == "completed" and not item.get("integrity_findings"))
            if row.get("primary_derivative_eligible", {}).get(kind) is not eligible:
                raise ValueError("Derivative eligibility disagrees with retained evidence status")
            if index["status"] == "integrity_failed" and (eligible or row["source_integrity"] != "unverified"):
                raise ValueError("Global integrity failure must exclude every primary derivative")
            if expected_terminal == ADMINISTRATIVE and (item["status"] != "unavailable"
                    or set(item.get("compact", {})) != set(METRICS if kind == "diagnostics" else COVERAGE)
                    or any(value is not None for value in item["compact"].values())):
                raise ValueError("Administrative diagnostics/continuity cannot invent measured counters")
            derivative = {key: copy.deepcopy(item[key]) for key in
                          ("status", "reason", "error_type", "message", "integrity_findings", "compact") if key in item}
            if item["status"] in ("completed", "failed"):
                filename = kind + ("-failure" if item["status"] == "failed" else "") + ".json"
                artifact = verify_reference(item.get("artifact"), expected=path.parent / rid / filename)
                if not artifact.is_relative_to(path.parent): raise ValueError("Derivative artifact escapes its index directory")
                derivative["artifact"] = source_ref(artifact, output)
            elif item.get("artifact") is not None:
                raise ValueError("Unavailable derivative cannot claim a retained artifact")
            view["derived"][kind] = derivative
            if item["status"] == "completed" and set(item.get("compact", {})) != set(METRICS if kind == "diagnostics" else COVERAGE):
                raise ValueError("Incomplete compact derivative measurements")
            for value in item.get("compact", {}).values():
                if value is not None and (type(value) not in (int, float) or not math.isfinite(value)
                        or (kind == "continuity" and (type(value) is not int or value < 0))):
                    raise ValueError("Invalid compact derivative measurement")
        converted.append(view)
    if administrative_schema:
        counts = derived_counts(rows, selected)
    else:
        counts = {"planned": len(rows), "selected_terminal": len(by_selected), "missing_terminal": len(rows)-len(by_selected),
                  "derivation_statuses": dict(Counter(r["status"] for r in rows)),
                  **{"primary_" + kind.rstrip("s") + "_eligible": sum(r["primary_derivative_eligible"][kind] for r in rows)
                     for kind in KINDS}}
    if counts != index.get("counts"):
        raise ValueError("Diagnostic summary counts disagree with full planned rows")
    expected_groups = summarize(rows)
    if not administrative_schema:
        for group in expected_groups: group.pop("administrative_interruption_runs", None)
    if expected_groups != index.get("descriptive_groups"):
        raise ValueError("Descriptive summaries differ from retained compact measurements")
    accounting_key = "complete_disposition_accounting" if administrative_schema else "complete_terminal_accounting"
    if index.get(accounting_key) is not (len(by_selected) == 264):
        raise ValueError("Complete disposition accounting disagrees with planned rows")
    if administrative_schema and "complete_terminal_accounting" in index:
        raise ValueError("Administrative accounting must not claim all rows have physical terminals")
    report = (paired_analysis or {}).get("report")
    if report is not None and (report.get("release_id") != release.get("release_id")
            or report.get("planned_counts", {}).get("runs") != 264
            or report.get("result_records_supplied") != len(by_selected)
            or report.get("dispositions") != dict(Counter(r["primary_disposition"] for r in rows))):
        raise ValueError("Paired analysis and diagnostic index use different release/result accounting")
    if source_ref(path, output) != index_source:
        raise ValueError("Diagnostic index changed during presentation verification")
    return {"state": "available", "status": index["status"], "release_id": release.get("release_id"),
            "counts": counts, accounting_key: index[accounting_key],
            "runs": converted, "descriptive_groups": copy.deepcopy(index["descriptive_groups"]),
            "excluded_paired_blocks": copy.deepcopy(index["excluded_paired_blocks"]),
            "global_integrity_errors": copy.deepcopy(index["global_integrity_errors"]),
            "canonical_snapshot_state": "changed; historical index only" if stale_map else "matches supplied canonical map",
            "source": index_source, "receipt_source": source_ref(receipt_path, output),
            "selected_results_source": source_ref(selected_path, output), "release_source": source_ref(release_path, output),
            "supplemental_sources": [{"label": key.replace("_", " "), "source": source_ref(verify_reference(selected[key], base=selected_path.parent), output)}
                                     for key in ("recovery_annex_ref", "recovery_source_index_ref") if selected.get(key) is not None],
            "disposition_counts": disposition_counts,
            "verification": "Report and failure-file bytes, retained selection, release identity, planned accounting and summary arithmetic checked. Original stream verification remains the processor's recorded finding; full run reports are linked, not embedded.",
            "limits": copy.deepcopy(index["limits"])}
