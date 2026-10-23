"""Presentation accounting for explicit administrative interruptions.

No terminal, physical end, post-run integrity or unmeasured counters are inferred.
Authority/file verification remains with the collector and bound source readers.
"""
from collections import Counter

SCHEMA = "selected-evaluation-results-administrative-1"
LEGACY_SCHEMA = "selected-evaluation-results-1"
ADMINISTRATIVE = "administrative_interruption"
NORMAL_KINDS = {"original_finalized_terminal", "annex_authorized_terminal"}
NULL_MEASUREMENTS = ("completion_time_s", "wall_duration_s", "model_calls", "total_tokens")


def is_administrative(result):
    return isinstance(result, dict) and result.get("provenance_kind") == ADMINISTRATIVE


def validate_administrative(result, provenance):
    required = {"stage": "evaluation", "execution_status": "aborted", "validity": "invalid",
                "invalidity_class": "infrastructure", "infrastructure_invalid": True,
                "outcome": "unknown", "ended_at": None, "physical_ended_at": None,
                "post_run_integrity": {"state": "missing"}, "official_queue_state": "interrupted",
                "official_queue_exit_status": None, "provenance_kind": ADMINISTRATIVE,
                **{key: None for key in NULL_MEASUREMENTS}}
    if (any(key not in result or result[key] != value for key, value in required.items())
            or result.get("infrastructure_invalid") is not True):
        raise ValueError("Administrative projection invents a terminal, measurement, outcome or integrity")
    if (provenance.get("run_id") != result.get("run_id")
            or provenance.get("provenance_kind") != ADMINISTRATIVE
            or provenance.get("supervisor_terminal", "absent") is not None
            or provenance.get("original_post_run_integrity") != {"state": "missing"}
            or any(provenance.get(key) is not None for key in ("terminal", "batch_finished", "finalization"))):
        raise ValueError("Administrative provenance cannot stand in for a completed supervisor attempt")
    note = provenance.get("selected_note", {})
    if (not result.get("administratively_recorded_at") or not result.get("selected_canonical_note_id")
            or note.get("id") != result["selected_canonical_note_id"]
            or note.get("target_ids") != [result.get("run_id")]
            or note.get("claim_type") != "decision" or note.get("supersedes_note_id") is not None):
        raise ValueError("Administrative projection lacks its exact canonical decision")
    for key in ("administrative_disposition", "recovery_annex_ref", "official_queue_receipt"):
        if not isinstance(provenance.get(key), dict):
            raise ValueError("Administrative projection lacks " + key)


def selection_accounting(selected):
    """Recompute counts without treating a projected analysis row as a terminal."""
    results, provenance = selected.get("results", []), selected.get("provenance", [])
    by_provenance = {row["run_id"]: row for row in provenance}
    ids = [row["run_id"] for row in results]
    if len(set(ids)) != len(ids) or len(by_provenance) != len(provenance) or set(by_provenance) != set(ids):
        raise ValueError("Selected result/provenance identity inventory differs")
    missing = selected.get("missing", [])
    missing_ids = [row["run_id"] for row in missing]
    if len(set(missing_ids)) != len(missing_ids) or set(missing_ids) & set(ids):
        raise ValueError("Missing dispositions repeat or overlap selected identities")
    kinds = Counter()
    for result in results:
        source = by_provenance[result["run_id"]]
        kind = source.get("provenance_kind", "original_finalized_terminal")
        if is_administrative(result) or kind == ADMINISTRATIVE:
            validate_administrative(result, source)
        elif kind not in NORMAL_KINDS:
            raise ValueError("Unknown selected-result provenance kind")
        kinds[kind] += 1
    counts = {"planned": len(results) + len(missing),
              "original_finalized": kinds["original_finalized_terminal"],
              "annex_finalized": kinds["annex_authorized_terminal"],
              "administrative_interruption": kinds[ADMINISTRATIVE],
              "selected_for_analysis": len(results), "missing_disposition": len(missing)}
    if selected.get("schema_version") == SCHEMA:
        if selected.get("counts") != counts or selected.get("complete_disposition_accounting") is not (not missing):
            raise ValueError("Administrative disposition counts disagree with selected rows")
        if "complete_terminal_accounting" in selected:
            raise ValueError("Administrative selection must not claim complete terminal accounting")
    elif selected.get("schema_version") != LEGACY_SCHEMA:
        raise ValueError("Unsupported selected-result schema")
    elif kinds[ADMINISTRATIVE] or kinds["annex_authorized_terminal"]:
        raise ValueError("Legacy accounting cannot contain supplemental administrative authority")
    return counts


def derived_counts(rows, selected):
    counts = selection_accounting(selected)
    completed = counts["original_finalized"] + counts["annex_finalized"]
    return {**counts, "selected_terminal": completed,
            "missing_terminal": len(rows) - completed,
            "derivation_statuses": dict(Counter(row["status"] for row in rows)),
            **{"primary_" + kind.rstrip("s") + "_eligible": sum(row["primary_derivative_eligible"][kind] for row in rows)
               for kind in ("diagnostics", "continuity")}}


def processing_complete(rows):
    return all(row.get("status") in ("completed", ADMINISTRATIVE) and not row.get("errors") for row in rows)
