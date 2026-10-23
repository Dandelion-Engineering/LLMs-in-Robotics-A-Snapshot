"""Verify the optional queue-completed statistical lineage sidecar."""
from pathlib import Path

from analysis_adapter import read_object, source_ref
from derivative_adapter import verify_reference, verify_receipt

HERE = Path(__file__).resolve().parent


def bind_analysis(bundle, path, receipt_path, output, *, derivatives=None):
    if path is None:
        if receipt_path is not None: raise ValueError("Analysis receipt requires its provenance sidecar")
        return bundle
    if receipt_path is None or bundle.get("state") != "available":
        raise ValueError("Analysis provenance requires its report and official receipt")
    path = Path(path).resolve()
    provenance_source = source_ref(path, output)
    record = read_object(path)
    report = bundle["report"]
    if (record.get("schema_version") != "source-bound-evaluation-analysis-1"
            or record.get("status") != "complete" or record.get("inputs_unchanged") is not True
            or record.get("error") is not None or not record.get("completed_at")):
        raise ValueError("Analysis provenance does not establish completed unchanged inputs")
    verify_receipt(receipt_path, record.get("queue_job_id"), completed=True,
        script_path=HERE.parent / "Batch 01" / "Release Analysis 004" / "analyze_results.py", output_dir=path.parent)
    before = record.get("inputs_before")
    roles = {"implementation", "protocol", "queue_authorization_implementation", "selection_implementation",
             "selected_results", "release", "freeze_manifest", "readiness"}
    manifests = record.get("protected_manifest_refs", [])
    manifest_ids = [row.get("run_id") for row in manifests]
    if len(manifests) != 264 or len(set(manifest_ids)) != 264 or any(not isinstance(rid, str) for rid in manifest_ids):
        raise ValueError("Analysis provenance must bind all 264 protected manifests")
    if (not isinstance(before, dict) or set(before) != roles | {"manifest:" + rid for rid in manifest_ids}
            or record.get("inputs_after") != before):
        raise ValueError("Analysis input inventories differ or omit required identities")
    for role, reference in before.items():
        verify_reference(reference)
        if role in roles - {"freeze_manifest", "readiness"} and record.get(role) != reference:
            raise ValueError("Analysis role reference differs from bound input inventory")
    expected_implementations = {
        "implementation": HERE.parent / "Batch 01" / "Release Analysis 004" / "analyze_results.py",
        "selection_implementation": HERE.parent / "Batch 01" / "Release Analysis 004" / "collect_results.py",
        "protocol": HERE.parent / "Runtime 004" / "protocol.py",
        "queue_authorization_implementation": HERE.parent / "Runtime 004" / "release_runner.py"}
    for role, expected in expected_implementations.items():
        if Path(before[role]["path"]).resolve() != expected.resolve():
            raise ValueError("Analysis identifies an unexpected implementation: " + role)
    for role in ("freeze_manifest", "readiness"):
        if record.get("release_authority", {}).get(role) != before[role]:
            raise ValueError("Analysis freeze/readiness differs from bound input inventory")
    for row in manifests:
        if {key: value for key, value in row.items() if key != "run_id"} != before["manifest:" + row["run_id"]]:
            raise ValueError("Analysis manifest reference differs from input inventory")
    analysis_path = verify_reference(record.get("analysis"), expected=path.parent / "analysis.json")
    if source_ref(analysis_path, output) != bundle["source"]:
        raise ValueError("Analysis sidecar names another supplied report")
    if record.get("analysis_settings") != {"bootstrap_draws": report.get("bootstrap_draws"), "analysis_seed": report.get("analysis_seed")}:
        raise ValueError("Analysis settings differ from supplied estimates")
    release = read_object(before["release"]["path"])
    selected = read_object(before["selected_results"]["path"])
    freeze = read_object(before["freeze_manifest"]["path"])
    readiness = read_object(before["readiness"]["path"])
    for role in ("freeze_manifest", "readiness"):
        verify_reference(release.get(role), base=Path(before["release"]["path"]).parent, expected=before[role]["path"])
        if release[role]["sha256"] != before[role]["sha256"]:
            raise ValueError("Analysis release authority hash differs")
    if (freeze.get("protocol_sha256") != before["protocol"]["sha256"]
            or readiness.get("freeze_sha256") != before["freeze_manifest"]["sha256"]
            or freeze.get("release_id") != report.get("release_id")
            or readiness.get("release_id") != report.get("release_id")):
        raise ValueError("Analysis frozen protocol/readiness authority differs")
    if (record.get("release_id") != report.get("release_id") or release.get("release_id") != report.get("release_id")
            or selected.get("schema_version") != "selected-evaluation-results-1"
            or selected.get("release") != before["release"]
            or report.get("result_records_supplied") != len(selected.get("results", []))):
        raise ValueError("Analysis release or selected-result identity disagrees")
    if {row["run_id"] for row in release.get("manifest_refs", [])} != set(manifest_ids):
        raise ValueError("Analysis manifest inventory differs from protected release")
    for declared in release["manifest_refs"]:
        bound = before["manifest:" + declared["run_id"]]
        verify_reference(declared, base=Path(before["release"]["path"]).parent, expected=bound["path"])
        if declared["sha256"] != bound["sha256"]: raise ValueError("Analysis manifest hash differs from release")
    if derivatives and derivatives.get("state") == "available":
        for role, source_key in (("selected_results", "selected_results_source"), ("release", "release_source")):
            if source_ref(before[role]["path"], output) != derivatives[source_key]:
                raise ValueError("Analysis and diagnostic index bind different " + role)
    if source_ref(path, output) != provenance_source:
        raise ValueError("Analysis provenance changed during verification")
    return {**bundle, "binding": {"state": "verified", "source": provenance_source,
                "receipt_source": source_ref(receipt_path, output),
                "selected_results_source": source_ref(before["selected_results"]["path"], output),
                "release_source": source_ref(before["release"]["path"], output)},
            "verification": "Completed analysis receipt and exact report, selected results, release, manifests, freeze, readiness and implementation identities verified against unchanged before/after records. Protocol estimates are retained unchanged."}
