"""Read protocol analysis and small run metadata without loading raw traces.

This is an operator presentation adapter. It verifies shape, arithmetic and
source bytes; it does not rerun statistics or certify scientific authenticity.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

from evidence_adapter import cross_volume, digest_file, relative_href, strict_json

MAX_TRACES = 12
MAX_METADATA_BYTES = 16 * 1024 * 1024
CONTRASTS = [((a, "persistent"), (b, "persistent"))
             for a, b in itertools.combinations(("baseline", "A1", "A2", "A3"), 2)]
CONTRASTS += [((a, "persistent"), (a, "no-persistence")) for a in ("A1", "A2", "A3")]


def read_object(path):
    path = Path(path)
    if path.stat().st_size > MAX_METADATA_BYTES:
        raise ValueError(f"Metadata file exceeds {MAX_METADATA_BYTES} bytes: {path.name}")
    value = strict_json(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object: " + path.name)
    return value


def source_ref(path, output):
    path = Path(path)
    unavailable = cross_volume(path.resolve(), Path(output).resolve())
    result = {"name": path.name, "href": None if unavailable else relative_href(path, output),
              "bytes": path.stat().st_size, "sha256": digest_file(path)}
    if unavailable:
        result.update(link_state="unavailable", reason="Artifact is on another drive; this standalone page has no cross-drive browser link.")
    return result


def count(value, label):
    if type(value) is not int or value < 0:
        raise ValueError(label + " must be a nonnegative integer")
    return value


def read_analysis(path, output):
    if path is None:
        return {"state": "unavailable", "reason": "No actual protocol analysis file was supplied.", "report": None, "source": None}
    report = read_object(path)
    if report.get("schema_version") != "robot-evaluation-analysis-1.0":
        raise ValueError("Unsupported protocol analysis schema")
    planned = report.get("planned_counts", {})
    total = count(planned.get("runs"), "planned runs")
    for key in ("main_runs", "ablation_runs", "case_units", "scenario_families", "paired_blocks"):
        count(planned.get(key), key)
    if planned["main_runs"] + planned["ablation_runs"] != total:
        raise ValueError("Analysis planned denominators disagree")
    supplied = count(report.get("result_records_supplied"), "supplied results")
    if supplied > total:
        raise ValueError("More results than planned runs")
    dispositions = report.get("dispositions")
    if not isinstance(dispositions, dict) or sum(count(v, "disposition") for v in dispositions.values()) != total:
        raise ValueError("Analysis dispositions do not account for every planned run")
    for key in ("excluded_paired_blocks", "entrants", "comparisons", "time_observations", "limitations"):
        if not isinstance(report.get(key), list):
            raise ValueError("Missing analysis collection: " + key)
    observed = []
    for item in report["comparisons"]:
        try:
            identity = tuple((item[side]["architecture"], item[side]["condition"]) for side in ("left", "right"))
            rows, absent = item["paired_rows"], item["unavailable_pairs"]
            summary_count = count(item["paired_run_count"], "paired runs")
            if not isinstance(rows, list) or not isinstance(absent, list) or len(rows) != summary_count:
                raise ValueError("Paired row count disagrees with summary")
            for key in ("case_units", "scenario_families"):
                count(item[key], key)
            if sum(count(v, "paired table") for v in item["paired_table"].values()) != summary_count:
                raise ValueError("Paired outcome table does not account for every eligible pair")
            if not isinstance(item["strata"], dict) or not isinstance(item["bootstrap"], dict):
                raise ValueError("Missing stratum or interval metadata")
        except (KeyError, TypeError) as exc:
            raise ValueError("Malformed protocol comparison") from exc
        observed.append(identity)
    if len(observed) != 9 or set(observed) != set(CONTRASTS):
        raise ValueError("Analysis must contain all six main and three persistence contrasts exactly once")
    return {"state": "available", "report": report, "source": source_ref(path, output),
            "verification": "Source hash and presentation structure only; estimates are retained exactly from protocol.py output."}


RESULT_FIELDS = ("run_id", "stage", "execution_status", "outcome", "validity", "validity_reason",
                 "failure_class", "termination_reason", "error", "ended_at", "finalized_at",
                 "wall_duration_s", "sim_duration_s", "completion_time_s", "independent_outcome",
                 "actual_host_timing_pass", "maximum_lag_s", "complete_wall_windows",
                 "outside_rtf_tolerance_windows", "restart_exercised", "order_amendment_exercised",
                 "model_calls", "total_tokens", "known_total_tokens", "unknown_token_calls",
                 "done_assertions", "false_done_assertions", "unassisted_completion", "completion_after_help")


def read_run_metadata(root, output):
    """Read direct development runs or exact attempts/<run>/evidence shape."""
    if root is None:
        return {"state": "unavailable", "reason": "No metadata root supplied; all canonical run records remain available.", "runs": [], "directories_without_manifest": []}
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("Metadata root is not a directory")
    rows, skipped, ids = [], [], set()
    for directory in sorted(root.iterdir()):
        if not directory.is_dir():
            continue
        if directory.is_symlink() or not directory.resolve().is_relative_to(root):
            raise ValueError("Metadata run directory escapes its declared root")
        direct, nested = directory / "manifest.json", directory / "evidence" / "manifest.json"
        if direct.is_file() and nested.is_file():
            raise ValueError("Ambiguous metadata shape: both direct and nested evidence manifests")
        evidence = directory / "evidence" if nested.is_file() else directory
        if evidence.is_symlink() or not evidence.resolve().is_relative_to(root):
            raise ValueError("Metadata evidence directory escapes its declared root")
        manifest_path, result_path = evidence / "manifest.json", evidence / "result.json"
        if not manifest_path.is_file():
            skipped.append(directory.name)
            continue
        manifest = read_object(manifest_path)
        run_id = manifest.get("run_id")
        if not isinstance(run_id, str) or not run_id or run_id in ids:
            raise ValueError("Missing or duplicate metadata run identity")
        ids.add(run_id)
        result = read_object(result_path) if result_path.is_file() else None
        if result is not None and result.get("run_id") != run_id:
            raise ValueError("Metadata result identity differs from manifest")
        rows.append({"run_id": run_id, "manifest": manifest,
                     "directory_shape": "release attempt/evidence" if evidence != directory else "direct run",
                     "result": None if result is None else {key: result[key] for key in RESULT_FIELDS if key in result},
                     "manifest_source": source_ref(manifest_path, output),
                     "result_source": source_ref(result_path, output) if result is not None else None})
    return {"state": "available", "runs": rows, "directories_without_manifest": skipped,
            "scope": "Every direct <run>/manifest.json or exact <run>/evidence/manifest.json at the supplied root; no arbitrary recursion. Event, motion and image files were not read. Full results remain linked, not silently reclassified."}


def select_traces(path, legacy_dirs=()):
    """Resolve the bounded selection before any detailed evidence is opened."""
    if path is not None and legacy_dirs:
        raise ValueError("Use a trace selection or explicit run directories, not both")
    if path is None:
        directories = [Path(p).resolve() for p in legacy_dirs]
        selection = {"schema_version": "investigation-trace-selection-1.0",
                     "mode": "explicit command-line selection" if directories else "no detailed traces selected",
                     "selection_basis": "Explicit paths supplied before loading; not a preregistered statistical sample.",
                     "runs": [{"path": str(p)} for p in directories]}
    else:
        path = Path(path).resolve()
        selection = read_object(path)
        if selection.get("schema_version") != "investigation-trace-selection-1.0":
            raise ValueError("Unsupported trace selection schema")
        if not all(isinstance(selection.get(key), str) and selection[key].strip() for key in ("declared_at", "selection_basis")):
            raise ValueError("Trace selection requires its declaration date and rationale")
        entries = selection.get("runs")
        if not isinstance(entries, list):
            raise ValueError("Trace selection requires a runs list")
        directories = []
        for entry in entries:
            if not isinstance(entry, dict) or not all(isinstance(entry.get(key), str) and entry[key].strip() for key in ("run_id", "path", "reason")):
                raise ValueError("Each selected trace requires run_id, path and reason")
            directories.append((path.parent / entry["path"]).resolve())
        if len({entry["run_id"] for entry in entries}) != len(entries):
            raise ValueError("Duplicate selected trace run identity")
        selection = {**selection, "source_sha256": digest_file(path)}
    if len(directories) > MAX_TRACES:
        raise ValueError(f"Detailed traces are capped at {MAX_TRACES}; retain all run metadata separately")
    if len(set(directories)) != len(directories):
        raise ValueError("Duplicate trace directory")
    return directories, {**selection, "maximum_trace_bundles": MAX_TRACES,
                         "selection_is_statistical_denominator": False}
