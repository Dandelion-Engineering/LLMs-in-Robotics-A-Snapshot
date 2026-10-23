"""Queue-only derivation for explicitly named, officially completed development runs.

Does not launch jobs, call queue CLI/status, append map records, select evaluation
attempts, edit originals, or interpret execution success as physical success.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import sys
import traceback

from build_workspace import load_map_module
from evidence_adapter import digest_file, strict_json
import continuity

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent / "Runtime 004"
MAP = HERE.parent / "Architecture Map"
EVIDENCE = HERE.parent / "Evidence" / "raw"
TERMINAL = {"completed", "failed", "timed_out", "aborted"}
RUN_ID = re.compile(r"B01-dev-[A-Za-z0-9_-]+\Z")


def object_file(path):
    value = strict_json(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):raise ValueError("Expected JSON object: " + str(path))
    return value


def ref(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": digest_file(path), "bytes": path.stat().st_size}


def write_once(path, value):
    path = Path(path)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False);stream.write("\n")


def runtime_module(name):
    # Importing a read-only helper is not executing an experiment or mutating its
    # source. Heavy derivation begins only after queued_job proves this process.
    if str(RUNTIME) not in sys.path:sys.path.insert(0, str(RUNTIME))
    return importlib.import_module(name)


def read_map(root):
    module = load_map_module()
    data, raw, errors = module.read_store(root)
    if not errors:errors.extend(module.validate_records(data, root))
    if errors:raise ValueError("Canonical map invalid: " + "; ".join(errors))
    return data, {"root": str(Path(root).resolve()), "store_sha256": module.store_digest(raw),
                  "files": {name: module.digest(value) for name, value in raw.items()}}


def receipt_files(paths, authority):
    receipts = {}
    for supplied in paths:
        path = Path(supplied).resolve();receipt = object_file(path)
        identity = receipt.get("id")
        if not isinstance(identity, str) or not identity or receipt.get("state") != "succeeded" or type(receipt.get("exit_status")) is not int or receipt["exit_status"] != 0:
            raise ValueError("Execution receipt must explicitly establish succeeded/exit_status=0")
        if identity in receipts:raise ValueError("Duplicate execution receipt identity")
        verified = authority.verify_queue_receipt(identity, str(path))
        if verified != receipt:raise ValueError("Verified receipt bytes differ from supplied object")
        receipts[identity] = {"receipt": receipt, "source": ref(path)}
    if not receipts:raise ValueError("At least one explicit official execution receipt is required")
    return receipts


def current_result(data, run_id):
    candidates = [r for r in data["result"] if r["run_id"] == run_id]
    superseded = {r.get("supersedes_result_id") for r in candidates}
    current = [r for r in candidates if r["id"] not in superseded]
    if len(current) != 1:raise ValueError("Run needs one unambiguous current canonical final result")
    return current[0]


def canonical_local_path(uri, map_root):
    """Accept local drive paths before URI parsing; never accept UNC or URLs."""
    if not isinstance(uri, str) or not uri or any(ord(c) < 32 for c in uri) or uri.startswith(("\\", "/")):
        return None
    if re.match(r"^[A-Za-z]:[\\/]", uri):
        if ".." in PureWindowsPath(uri).parts: return None
        return Path(uri).resolve()
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", uri): return None
    return (Path(map_root) / uri).resolve()


def verify_run(run_id, data, map_root, evidence_root, receipts):
    matches = [r for r in data["run"] if r["id"] == run_id]
    if len(matches) != 1 or matches[0].get("stage") != "development":
        raise ValueError("Explicit run is not a uniquely registered development attempt")
    run_record = matches[0]
    canonical = current_result(data, run_id)
    if canonical.get("execution_status") not in TERMINAL:
        raise ValueError("Current canonical result is not terminal")
    job_id = canonical.get("details", {}).get("queue_job_id")
    if job_id not in receipts:
        raise ValueError("No matching explicit official receipt for canonical execution queue job")
    root = (Path(evidence_root) / run_id).resolve()
    if root.parent != Path(evidence_root).resolve() or any(part.casefold() == "candidate_state" for part in root.parts):
        raise ValueError("Development evidence path escaped its exact assigned root")
    for name in ("manifest.json", "result.json", "events.jsonl", "motion.jsonl"):
        if (root / name).resolve().parent != root:
            raise ValueError("Development source file escaped its exact run directory")
    inputs = {name: ref(root / name) for name in ("manifest.json", "result.json", "events.jsonl", "motion.jsonl")}
    manifest, raw_result = object_file(root / "manifest.json"), object_file(root / "result.json")
    if manifest.get("run_id") != run_id or raw_result.get("run_id") != run_id or manifest.get("stage") != "development" or raw_result.get("stage") != "development":
        raise ValueError("Raw manifest/result identity or development stage mismatch")
    if raw_result.get("execution_status") not in TERMINAL:
        raise ValueError("Raw source has no terminal execution result")
    # A correction may deliberately differ from the immutable raw outcome. Only
    # identity and source bytes are matched here; the correction is preserved.
    for name in ("result.json", "events.jsonl", "motion.jsonl"):
        wanted = Path(inputs[name]["path"])
        matches = []
        for evidence in canonical.get("evidence", []):
            uri = evidence.get("uri")
            if evidence.get("state") != "available":
                continue
            candidate = canonical_local_path(uri, map_root)
            if candidate == wanted and evidence.get("sha256") == inputs[name]["sha256"]:
                matches.append(evidence)
        if not matches:raise ValueError("Canonical final result does not bind exact original " + name)
    return {"run_id": run_id, "root": root, "run_record": run_record,
            "canonical_result": canonical, "raw_result": raw_result, "sources": inputs,
            "execution_queue_job_id": job_id, "execution_receipt": receipts[job_id]}


def check_sources(sources):
    for source in sources.values():
        if digest_file(Path(source["path"])) != source["sha256"]:
            raise ValueError("Original source changed during derivation: " + source["path"])


def process(run_ids, receipt_paths, output, *, map_root=MAP, evidence_root=EVIDENCE):
    authority = runtime_module("release_runner")
    ownership = authority.queued_job(expected_script=__file__)
    if not isinstance(run_ids, (list, tuple)) or not 1 <= len(run_ids) <= 32 or any(not isinstance(r, str) or not RUN_ID.fullmatch(r) for r in run_ids) or len({r.casefold() for r in run_ids}) != len(run_ids):
        raise ValueError("One to 32 distinct explicit B01-dev run IDs are required")
    output, map_root, evidence_root = Path(output).resolve(), Path(map_root).resolve(), Path(evidence_root).resolve()
    if output.exists():raise ValueError("Derived output directory must be fresh")
    if any(output.is_relative_to(root) for root in (map_root, evidence_root, RUNTIME.resolve())) or any(part.casefold() == "candidate_state" for part in output.parts):
        raise ValueError("Derived output must remain outside originals, canonical map, Runtime and candidate state")
    receipts = receipt_files(receipt_paths, authority)
    receipt_sources = {identity: item["source"] for identity, item in receipts.items()}
    data, map_source = read_map(map_root)
    output.mkdir(parents=True, exist_ok=False)
    method_sources = {"processor": ref(__file__), "continuity": ref(HERE / "continuity.py"),
                      "diagnostics": ref(RUNTIME / "diagnostics.py"), "rubric": ref(continuity.RUBRIC),
                      "evidence_reader": ref(HERE / "evidence_adapter.py"), "map_loader": ref(HERE / "build_workspace.py"),
                      "map_reader": ref(MAP / "map.py"), "queue_authority": ref(RUNTIME / "release_runner.py"),
                      "protocol": ref(RUNTIME / "protocol.py")}
    header = {"schema_version": "development-derived-batch-1.0", "scope": "operator-only development diagnostics; no scored selection or original-result mutation",
              "derivation_queue_job_id": ownership["id"], "selected_run_ids": list(run_ids), "canonical_map": map_source,
              "execution_receipts": {identity: record["source"] for identity, record in receipts.items()}, "implementation": method_sources}
    write_once(output / "selection.json", header)
    records = []
    def diagnose(path):return runtime_module("diagnostics").diagnose_directory(path)
    def save_diagnostic(report, path):return runtime_module("diagnostics").write_report(report, path)
    for run_id in run_ids:
        record = {"run_id": run_id, "status": "verification_failed", "derived": {}, "errors": []}
        directory = output / run_id;directory.mkdir()
        try:
            check_sources(receipt_sources)
            verified = verify_run(run_id, data, map_root, evidence_root, receipts)
            record.update(execution_queue_job_id=verified["execution_queue_job_id"], execution_receipt=verified["execution_receipt"]["source"],
                          sources=verified["sources"], canonical_result_id=verified["canonical_result"]["id"],
                          canonical_outcome=verified["canonical_result"].get("outcome"), canonical_validity=verified["canonical_result"].get("validity"),
                          immutable_raw_outcome=verified["raw_result"].get("outcome"), immutable_raw_validity=verified["raw_result"].get("validity"))
            write_once(directory / "canonical-assessment.json", {"run": verified["run_record"], "current_result": verified["canonical_result"], "map_source": map_source})
            record["canonical_assessment"] = ref(directory / "canonical-assessment.json")
            record["status"] = "processing"
            for name, derive, save in (("diagnostics", diagnose, save_diagnostic),
                                       ("continuity", continuity.extract_directory, lambda report, path: continuity.write_report(report, path, verified["root"]))):
                path = directory / (name + ".json")
                try:
                    check_sources(verified["sources"]);check_sources(method_sources);check_sources(receipt_sources)
                    derived = derive(verified["root"])
                    if derived.get("run_id") != run_id:raise ValueError("Derived report changed run identity")
                    save(derived, path)
                    record["derived"][name] = {"status": "completed", "artifact": ref(path),
                                               "integrity_findings": derived.get("integrity_findings", [])}
                except Exception as exc:
                    failure = {"status": "failed", "error_type": type(exc).__name__, "message": str(exc)}
                    write_once(directory / (name + "-failure.json"), {**failure, "traceback": traceback.format_exc()})
                    failure["artifact"] = ref(directory / (name + "-failure.json"))
                    record["derived"][name] = failure;record["errors"].append({"stage": name, **failure})
            check_sources(verified["sources"]);check_sources(method_sources);check_sources(receipt_sources)
            record["requires_operator_review"] = any(d.get("integrity_findings") for d in record["derived"].values())
            record["status"] = "partial_failure" if record["errors"] else "completed"
        except Exception as exc:
            record["errors"].append({"stage": "verification" if record["status"] == "verification_failed" else "source_integrity",
                                     "error_type": type(exc).__name__, "message": str(exc)})
            if record["status"] != "verification_failed":record["status"] = "integrity_failed"
        write_once(directory / "status.json", record)
        records.append(record)
        with (output / "progress.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(record, allow_nan=False, separators=(",", ":")) + "\n");stream.flush();os.fsync(stream.fileno())
    index = {**header, "status": "completed" if all(r["status"] == "completed" for r in records) else "partial_failure",
             "counts": {"selected": len(run_ids), "completed": sum(r["status"] == "completed" for r in records),
                        "failed_or_partial": sum(r["status"] != "completed" for r in records),
                        "with_integrity_findings": sum(bool(r.get("requires_operator_review")) for r in records)},
             "runs": records, "limits": ["Derivation completion is not task success or scored validity",
                 "Each execution receipt is matched to that run's selected canonical result; older jobs require their own explicit receipts",
                 "Diagnostics/continuity failures and source-integrity findings remain visible; no automatic retries or replacement runs"]}
    write_once(output / "index.json", index)
    return index


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", action="append", required=True, dest="run_ids")
    parser.add_argument("--receipt", action="append", type=Path, required=True, dest="receipts")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--map-root", type=Path, default=MAP)
    parser.add_argument("--evidence-root", type=Path, default=EVIDENCE)
    args = parser.parse_args(argv)
    try:
        report = process(args.run_ids, args.receipts, args.output_dir, map_root=args.map_root, evidence_root=args.evidence_root)
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(2, "Refused: " + str(exc) + "\n")
    print(json.dumps({"output_dir": str(args.output_dir.resolve()), "status": report["status"], "counts": report["counts"]}, indent=2))
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
