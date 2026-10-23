"""Queue-only, once-written evaluation diagnostics with complete planned accounting.

Uses the protected release collector; never launches jobs, calls queue status,
draws seeds, rewrites originals, or upgrades canonical outcomes/validity. Full
per-run reports are linked files; this compact index contains no event traces.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import importlib.util
import math
import os
from pathlib import Path
import statistics
import sys
import traceback
import json

from process_development import (HERE, RUNTIME, MAP, object_file, ref, write_once,
                                 runtime_module, read_map, check_sources)
import continuity
from administrative_projection import (ADMINISTRATIVE, is_administrative, selection_accounting, derived_counts, processing_complete)

COLLECTOR = HERE.parent / "Batch 01" / "Release Analysis 005" / "collect_results.py"
QUEUE_AUTHORIZATION = HERE.parent / "Runtime Recovery 001" / "recovery_runner.py"
CORE = ("manifest.json", "result.json", "events.jsonl", "motion.jsonl")
PLAN_FIELDS = ("run_id", "architecture", "condition", "horizon", "scenario",
               "paired_block_id", "case_id", "scenario_family_id", "replicate")
COVERAGE = ("planned_opportunities", "planned_but_unobserved", "exercised",
            "known_admissible", "known_inadmissible", "unknown_admissibility",
            "missing_exposure_correlation", "established_recoveries",
            "known_admissible_qualified_context", "known_admissible_recorded_or_annotated",
            "qualified_restart_exposures", "qualified_absence_coverage_pass", "qualified_absence_coverage_unknown",
            "independently_verified_restart_exposures", "qualified_carry_exposures",
            "known_admissible_carry_qualified", "known_admissible_empty_instantaneous",
            "qualified_absence_coverage_not_applicable", "qualification_scope_unknown")
# These are existing measurements, not new scientific thresholds or rankings.
# Aggregation weights each observed run equally; call/trajectory distributions
# remain in the per-run reports instead of silently pooling unequal episodes.
METRICS = {
    "tcp_path_m": ("motion.tcp_path_m.value", "m"),
    "joint_travel_total_rad": ("motion.joint_travel_total_rad.value", "rad"),
    "filtered_tcp_speed_peak": ("motion.filtered_tcp_speed_peak.value", "m/s"),
    "filtered_tcp_acceleration_peak": ("motion.filtered_tcp_acceleration_peak.value", "m/s^2"),
    "low_motion_time_s": ("pauses.observed_low_motion_time_s", "s simulation"),
    "pause_analyzed_support_s": ("pauses.analyzed_support_s", "s simulation"),
    "eligible_pause_time_s": ("pauses.eligible_pause_time.value", "s simulation"),
    "model_requests": ("models.observed_request_count", "count"),
    "model_tokens": ("models.total_tokens.value", "tokens"),
    "mean_model_latency_s": ("models.latency_summary_s.mean", "s wall per call"),
    "machine_busy_time_s": ("process.observed_busy_time.value", "s simulation"),
    "transport_requests": ("transports.requested_transport_count", "count"),
    "normalized_jerk_usable_transports": ("transports.normalized_jerk_usable_count", "count"),
    "normalized_jerk_omitted_transports": ("transports.normalized_jerk_omitted_count", "count"),
    "contact_peak_N": ("recorded_contact.contact_peak_N", "N; all recorded contact"),
    "contact_impulse_Ns": ("recorded_contact.contact_impulse_Ns", "N*s; all recorded contact"),
}


def collector_module():
    spec = importlib.util.spec_from_file_location("investigation_evaluation_collector", COLLECTOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module



def queue_authorization_module():
    """Exact recovery ownership helper; diagnostics and statistics stay frozen."""
    spec = importlib.util.spec_from_file_location("investigation005_queue_authorization", QUEUE_AUTHORIZATION)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if Path(module.__file__).resolve() != QUEUE_AUTHORIZATION.resolve():
        raise ValueError("Queue authorization imported from an unexpected source")
    return module


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def nested(value, path):
    for key in path.split("."):
        value = value.get(key) if isinstance(value, dict) else None
    return value


def compact_diagnostic(report):
    return {name: value if finite(value := nested(report, path)) else None
            for name, (path, _unit) in METRICS.items()}


def compact_continuity(report):
    coverage = report.get("coverage", {})
    return {key: value if type(value := coverage.get(key)) is int and value >= 0 else None
            for key in COVERAGE}


def plan_dispositions(manifests, results, protocol):
    by_result = {row["run_id"]: row for row in results}
    blocks = defaultdict(list)
    for plan in manifests:
        result = by_result.get(plan["run_id"])
        if result is not None and protocol._infra_invalid(result):
            blocks[plan["paired_block_id"]].append(plan["run_id"])
    dispositions = {}
    for plan in manifests:
        result = by_result.get(plan["run_id"])
        if plan["paired_block_id"] in blocks: reason = "paired_block_infrastructure_invalid"
        elif result is None or result.get("execution_status") == "not_run": reason = "unrun"
        elif result.get("execution_status") not in protocol.TERMINAL: reason = "nonterminal"
        elif result.get("validity") != "valid":
            reason = "unknown_validity" if result.get("validity") in (None, "unknown") else "invalid_result"
        elif protocol._success(result) is None: reason = "missing_outcome"
        else: reason = "eligible"
        dispositions[plan["run_id"]] = reason
    return dispositions, dict(blocks)


def source_snapshot(release_root, collected, map_root, map_source):
    """Small protected control files only; raw streams are hashed per run."""
    sources = {}
    def add(path):
        source = ref(path); sources[source["path"]] = source
    add(release_root / "release.json")
    release = object_file(release_root / "release.json")
    for item in release["manifest_refs"]:
        path = (release_root / item["path"]).resolve()
        if not path.is_relative_to(release_root): raise ValueError("Manifest escaped release")
        add(path)
        if sources[str(path)]["sha256"] != item["sha256"]:
            raise ValueError("Protected manifest changed after collection")
    for source in collected.get("control_sources", []):
        if ref(source["path"]) != source: raise ValueError("Collector control source changed")
        sources[source["path"]] = source
    for name, digest in map_source["files"].items():
        path = (map_root / name).resolve()
        if path.parent != map_root: raise ValueError("Map file escaped root")
        add(path)
        if sources[str(path)]["sha256"] != digest: raise ValueError("Canonical map changed after selection")
    if ref(release_root / "release.json") != collected["release"]:
        raise ValueError("Release changed after selection")
    return sources


def method_snapshot():
    paths = [Path(__file__), HERE / "process_development.py", COLLECTOR, QUEUE_AUTHORIZATION, HERE / "administrative_projection.py",
             COLLECTOR.parent.parent / "Release Analysis 004" / "collect_results.py",
             HERE / "continuity.py", HERE / "qualified_restart.py", continuity.RUBRIC, HERE / "evidence_adapter.py",
             HERE / "build_workspace.py", MAP / "map.py", RUNTIME / "diagnostics.py",
             RUNTIME / "release_runner.py", RUNTIME / "protocol.py"]
    # Retain available classifier identities alongside the reader identity;
    # hashing them does not claim that the current reader recomputes predicates.
    for name in ("restart_state.py", "restart_qualification.py", "restart_calibration_loader.py",
                 "restart_compatibility.py", "restart_physical_class.py"):
        if (RUNTIME / name).is_file(): paths.append(RUNTIME / name)
    return {str(path.resolve()): ref(path) for path in paths}


def evidence_snapshot(root):
    sources, missing = {}, []
    for name in CORE:
        path = (root / name).resolve()
        if path.parent != root: raise ValueError("Evidence file escaped exact episode directory")
        if path.is_file(): sources[name] = ref(path)
        else: missing.append(name)
    return sources, missing


def verify_episode(root, plan, provenance, collector):
    terminal = object_file(provenance["terminal"]["path"])
    raw_ref = terminal.get("supervisor_result_ref")
    if not raw_ref: raise ValueError("Terminal has no bound supervisor result; partial evidence is not a complete episode")
    resolved = collector.release_runner.reference(raw_ref, Path(provenance["terminal"]["path"]).parent)
    if resolved != root / "result.json": raise ValueError("Terminal supervisor result names another episode")
    result, manifest = object_file(root / "result.json"), object_file(root / "manifest.json")
    if result != terminal["result"]: raise ValueError("Supervisor result differs from protected terminal")
    for obj in (result, manifest):
        if obj.get("run_id") != plan["run_id"] or obj.get("stage") != "evaluation":
            raise ValueError("Raw episode identity or evaluation stage mismatch")
    for key in ("architecture", "condition", "scenario"):
        if manifest.get(key) != plan[key]: raise ValueError("Raw episode differs from planned " + key)
    for raw_key, planned_key in (("part_count", "parts"), ("cap_s", "cap_s")):
        if planned_key in plan and manifest.get(raw_key) != plan[planned_key]:
            raise ValueError("Raw episode differs from planned " + planned_key)
    authorization = manifest.get("evaluation_authorization") or {}
    for key in ("release_sha256", "manifest_sha256", "queue_job_id"):
        if authorization.get(key) != terminal.get(key):
            raise ValueError("Raw manifest lacks exact protected evaluation authorization: " + key)


def summarize(rows):
    """Explicit run denominators and known opportunity denominators; no inference."""
    groups = defaultdict(list)
    for row in rows:
        plan = row["plan"]
        groups[(plan["architecture"], plan["condition"], plan["horizon"])].append(row)
    output = []
    for (architecture, condition, horizon), members in sorted(groups.items(), key=lambda item: tuple(map(str, item[0]))):
        group = {"architecture": architecture, "condition": condition, "horizon": horizon,
                 "planned_runs": len(members),
                 "missing_terminal_runs": sum(r["terminal_disposition"] != "selected" for r in members),
                 "administrative_interruption_runs": sum(r["terminal_disposition"] == ADMINISTRATIVE for r in members),
                 "primary_dispositions": dict(Counter(r["primary_disposition"] for r in members)),
                 "derivation_statuses": dict(Counter(r["status"] for r in members)), "subsets": {}}
        for name, selected in (("all_planned_descriptive", members),
                               ("primary_eligible", [r for r in members if r["primary_disposition"] == "eligible"])):
            subset = {"denominator_runs": len(selected), "diagnostics": {}, "continuity": {}}
            for kind in ("diagnostics", "continuity"):
                completed = [r for r in selected if r["derived"][kind]["status"] == "completed"]
                accepted = [r for r in completed if r["source_integrity"] == "verified"
                            and not r["derived"][kind].get("integrity_findings")]
                subset[kind].update(available_reports=len(completed), accepted_reports=len(accepted),
                    missing_or_failed_reports=len(selected)-len(completed),
                    reports_with_unverified_integrity=len(completed)-len(accepted))
                if kind == "diagnostics":
                    values = {}
                    for metric, (_path, unit) in METRICS.items():
                        measured = [r["derived"][kind]["compact"][metric] for r in accepted
                                    if r["derived"][kind]["compact"][metric] is not None]
                        values[metric] = {"unit": unit, "observed_runs": len(measured),
                            "missing_measurement_in_accepted_reports": len(accepted)-len(measured),
                            "unavailable_or_unverified_report_runs": len(selected)-len(accepted),
                            "mean": statistics.mean(measured) if measured else None,
                            "median": statistics.median(measured) if measured else None,
                            "minimum": min(measured) if measured else None,
                            "maximum": max(measured) if measured else None}
                    subset[kind]["measurements"] = values
                else:
                    coverage = {}
                    for metric in COVERAGE:
                        measured = [r["derived"][kind]["compact"][metric] for r in accepted
                                    if r["derived"][kind]["compact"][metric] is not None]
                        coverage[metric] = {"observed_total": sum(measured) if measured else None,
                                            "report_denominator": len(measured),
                                            "missing_report_count": len(selected)-len(measured)}
                    subset[kind]["coverage"] = coverage
                    complete = [r["derived"][kind]["compact"] for r in accepted
                                if r["derived"][kind]["compact"]["known_admissible"] is not None
                                and r["derived"][kind]["compact"]["established_recoveries"] is not None]
                    denominator = sum(r["known_admissible"] for r in complete)
                    numerator = sum(r["established_recoveries"] for r in complete)
                    subset[kind]["recovery"] = {"established_recoveries": numerator if complete else None,
                        "known_admissible_exercised_opportunities": denominator if complete else None,
                        "report_denominator": len(complete), "missing_report_count": len(selected)-len(complete),
                        "rate": numerator/denominator if denominator else None,
                        "scope": "Only reported exercised independently admissible opportunities; unknown admissibility and missing runs are separate"}
            group["subsets"][name] = subset
        output.append(group)
    return output


def process(release_root, output, *, map_root=MAP, annex_path=None):
    ownership = queue_authorization_module().queued_job(expected_script=__file__)
    release_root, output, map_root = Path(release_root).resolve(), Path(output).resolve(), Path(map_root).resolve()
    if output.exists(): raise ValueError("Derived output directory must be fresh")
    forbidden = (release_root, map_root, RUNTIME.resolve(), (HERE.parent / "Evidence" / "raw").resolve())
    if any(output.is_relative_to(root) for root in forbidden) or any(p.casefold() == "candidate_state" for p in output.parts):
        raise ValueError("Derived output must remain outside release, originals, map, Runtime and candidate state")
    methods = method_snapshot()
    collector = collector_module()
    data, map_source = read_map(map_root)
    collected = collector.collect(release_root, data["result"], notes=data.get("note", []), annex_path=annex_path, complete=False)
    selection_accounting(collected)
    manifests = collector.protocol.load_release(release_root)
    controls = source_snapshot(release_root, collected, map_root, map_source)
    check_sources(methods); check_sources(controls)
    results = {r["run_id"]: r for r in collected["results"]}
    provenance = {r["run_id"]: r for r in collected["provenance"]}
    missing = {r["run_id"]: r for r in collected["missing"]}
    dispositions, blocks = plan_dispositions(manifests, collected["results"], collector.protocol)
    output.mkdir(parents=True, exist_ok=False)
    write_once(output / "selected-results.json", {**collected, "canonical_map": map_source,
                                                  "implementation": ref(COLLECTOR),
                                                  "canonical_results_source": ref(map_root / "results.jsonl"),
                                                  "canonical_notes_source": ref(map_root / "notes.jsonl")})
    header = {"schema_version": "evaluation-derived-administrative-batch-1.0", "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Operator-only descriptive measurements; canonical selected outcomes govern; no validity upgrade",
        "derivation_queue_job_id": ownership["id"], "release": collected["release"],
        "queue_authorization_implementation": methods[str(QUEUE_AUTHORIZATION.resolve())],
        "selected_results": ref(output / "selected-results.json"), "canonical_map": map_source,
        "implementation": methods, "protected_control_sources": controls,
        "excluded_paired_blocks": blocks, "planned_runs": len(manifests),
        "recovery_annex_ref": collected.get("recovery_annex_ref"),
        "recovery_source_index_ref": collected.get("recovery_source_index_ref")}
    write_once(output / "selection.json", header)
    rows = []
    for manifest in manifests:
        rid = collector.release_runner.safe_id(manifest["run_id"])
        directory = output / rid; directory.mkdir()
        root = (release_root / "attempts" / rid / "evidence").resolve()
        if not root.is_relative_to(release_root): raise ValueError("Episode path escaped release")
        row = {"run_id": rid, "plan": {k: manifest.get(k) for k in PLAN_FIELDS},
               "terminal_disposition": "selected" if rid in results else "missing",
               "selected_result": results.get(rid), "primary_disposition": dispositions[rid],
               "status": "missing_terminal", "source_integrity": "not_processed", "sources": {},
               "derived": {k: {"status": "unavailable", "reason": "No retained terminal attempt"} for k in ("diagnostics", "continuity")},
               "errors": []}
        if rid in missing: row["missing_terminal"] = missing[rid]
        elif is_administrative(results[rid]):
            row.update(terminal_disposition=ADMINISTRATIVE, status=ADMINISTRATIVE,
                       selection_provenance=provenance[rid])
            row["derived"] = {kind: {"status": "unavailable",
                "reason": "Administrative interruption: no original supervisor terminal or post-run integrity; partial evidence is not a completed episode",
                "compact": {key: None for key in (METRICS if kind == "diagnostics" else COVERAGE)}}
                for kind in ("diagnostics", "continuity")}
            # Do not parse, aggregate or promote partial streams to ordinary reports.
            # The collector's exact disposition/annex/receipt are the only authority.
        else:
            row["selection_provenance"] = {k: v for k, v in provenance[rid].items() if k != "selected_assessment"}
            run_controls = {key: provenance[rid][key] for key in
                            ("terminal", "batch_plan", "batch_finished", "finalization", "official_queue_receipt")}
            try:
                check_sources(methods); check_sources(run_controls)
                row["sources"], absent = evidence_snapshot(root)
                row["missing_evidence_files"] = absent
                if absent:
                    row["status"] = "missing_evidence"
                    for derivative in row["derived"].values(): derivative["reason"] = "Missing immutable inputs: " + ", ".join(absent)
                else:
                    row["status"] = "verification_failed"
                    verify_episode(root, manifest, provenance[rid], collector)
                    row["source_integrity"] = "verified"
                    for kind in ("diagnostics", "continuity"):
                        path = directory / (kind + ".json")
                        try:
                            check_sources(row["sources"]); check_sources(methods); check_sources(run_controls)
                            if kind == "diagnostics":
                                module = runtime_module("diagnostics"); report = module.diagnose_directory(root)
                            else: report = continuity.extract_directory(root, release_dir=release_root)
                            if report.get("run_id") != rid: raise ValueError("Derived report changed run identity")
                            check_sources(row["sources"]); check_sources(methods); check_sources(run_controls)
                            if kind == "diagnostics": module.write_report(report, path)
                            else: continuity.write_report(report, path, root)
                            row["derived"][kind] = {"status": "completed", "artifact": ref(path),
                                "integrity_findings": report.get("integrity_findings", []),
                                "compact": compact_diagnostic(report) if kind == "diagnostics" else compact_continuity(report)}
                        except Exception as exc:
                            failure = {"status": "failed", "error_type": type(exc).__name__, "message": str(exc)}
                            path = directory / (kind + "-failure.json")
                            write_once(path, {**failure, "traceback": traceback.format_exc()})
                            row["derived"][kind] = {**failure, "artifact": ref(path)}
                            row["errors"].append({"stage": kind, **failure})
                    row["status"] = "partial_failure" if row["errors"] else "completed"
                check_sources(row["sources"]); check_sources(methods); check_sources(run_controls)
                # Missingness is source-bound too: appearance during a run is not a
                # license to reinterpret its already-recorded unavailable report.
                if any((root / name).exists() for name in absent): raise ValueError("Previously absent evidence appeared during derivation")
            except Exception as exc:
                row["source_integrity"] = "unverified"
                row["status"] = "verification_failed" if row["status"] in ("missing_terminal", "verification_failed") else "integrity_failed"
                row["errors"].append({"stage": "verification_or_integrity", "error_type": type(exc).__name__, "message": str(exc)})
                for derivative in row["derived"].values():
                    if derivative["status"] == "unavailable": derivative["reason"] = "Episode verification failed; see retained error"
        row["primary_derivative_eligible"] = {kind: row["primary_disposition"] == "eligible"
            and row["source_integrity"] == "verified" and derivative["status"] == "completed"
            and not derivative.get("integrity_findings") for kind, derivative in row["derived"].items()}
        write_once(directory / "status.json", row); rows.append(row)
        with (output / "progress.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(row, allow_nan=False, separators=(",", ":")) + "\n"); stream.flush(); os.fsync(stream.fileno())
    final_errors = []
    try:
        check_sources(methods); check_sources(controls)
        for item in [*collected["missing"], *[r for r in collected["results"] if is_administrative(r)]]:
            if (release_root / "attempts" / item["run_id"] / "terminal.json").exists():
                raise ValueError("Previously missing terminal appeared during derivation")
        for row in rows:
            root = release_root / "attempts" / row["run_id"] / "evidence"
            if any((root / name).exists() for name in row.get("missing_evidence_files", [])):
                raise ValueError("Previously absent episode evidence appeared during derivation")
    except Exception as exc:
        final_errors.append({"error_type": type(exc).__name__, "message": str(exc)})
    # A changed global authority snapshot invalidates every primary derivative,
    # including earlier outputs. Historical status/progress files stay unchanged.
    if final_errors:
        for row in rows:
            row["source_integrity"] = "unverified"
            row["primary_derivative_eligible"] = {"diagnostics": False, "continuity": False}
    status = "integrity_failed" if final_errors else ("completed" if processing_complete(rows) else "partial_failure")
    index = {**header, "status": status,
        "complete_disposition_accounting": collected["complete_disposition_accounting"],
        "counts": derived_counts(rows, collected),
        "global_integrity_errors": final_errors, "runs": rows, "descriptive_groups": summarize(rows),
        "limits": ["Final index authority checks supersede creation-time per-run/progress status after a global source change",
            "Full diagnostics and continuity reports are linked files; no event traces are embedded here",
            "No causal effect, winner, significance test or new scientific threshold is computed",
            "All-planned descriptive summaries include measured invalid/excluded attempts with their dispositions; primary subset excludes whole infrastructure-invalid paired blocks",
            "Integrity findings or changed sources exclude derivative values from accepted summaries without rewriting canonical validity",
            "Missing reports do not count as zero opportunities, zero motion or failed recovery",
            "Administrative interruption is an accounted infrastructure disposition, not a completed supervisor terminal; its diagnostics and continuity are unavailable with null counters",
            "Legacy continuity remains a recorded-predicate interpretation; verified empty cuts establish only instantaneous admissibility, while qualified carry cuts additionally require measured-cell and actual absence coverage",
            "Run-weighted descriptive means are not pooled call/trajectory estimates or matched-motion comparisons",
            "Official completion of this derivation queue job must be retained separately"]}
    write_once(output / "index.json", index)
    return index


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--map-root", type=Path, default=MAP)
    parser.add_argument("--annex", type=Path, help="Exact adopted administrative-continuation authority")
    args = parser.parse_args(argv)
    try: report = process(args.release_dir, args.output_dir, map_root=args.map_root, annex_path=args.annex)
    except (ValueError, OSError, RuntimeError) as exc: parser.exit(2, "Refused: " + str(exc) + "\n")
    print(json.dumps({"output_dir": str(args.output_dir.resolve()), "status": report["status"], "counts": report["counts"]}))
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
