"""Queue-only reader regression and real completed-analysis compatibility check."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
sys.path.insert(0, str(EXPERIMENT / "Runtime Recovery 001"))
import recovery_runner


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--analysis-file", type=Path, required=True)
    parser.add_argument("--analysis-provenance", type=Path, required=True)
    parser.add_argument("--analysis-receipt", type=Path, required=True)
    args = parser.parse_args()
    ownership = recovery_runner.queued_job(expected_script=__file__)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    builder = load_module("investigation006_validation_builder", HERE / "build_workspace.py")
    before = {p.name: builder._source(p) for p in HERE.iterdir() if p.is_file()}
    record = {"schema_version": "investigation006-reader-validation-1", "queue_job_id": ownership["id"],
              "started_at": datetime.now(timezone.utc).isoformat(), "status": "failed",
              "tests": [], "production_check": None, "sources_before": before, "error": None}
    error = None
    try:
        for label, directory in (("original005_regressions", builder.UPSTREAM), ("reader006_regressions", HERE)):
            argv = [sys.executable, "-X", "utf8", "-B", "-m", "unittest", "discover",
                    "-s", str(directory), "-p", "test_*.py", "-v"]
            result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            log = output / (label + ".log")
            log.write_bytes(result.stdout + result.stderr)
            counts = re.findall(rb"Ran (\d+) tests? in", result.stderr)
            count = int(counts[-1]) if counts else None
            record["tests"].append({"label": label, "argv": argv, "exit_status": result.returncode,
                                    "test_count": count, "log": builder._source(log)})
            if result.returncode or count is None:
                raise ValueError("Reader tests failed: " + label)
        bundle = builder.read_analysis(args.analysis_file, output / "view.html")
        # Reproduce the observed old-reader refusal against actual completed,
        # immutable outputs. This never modifies or reruns an analysis.
        old = load_module("investigation005_failure_reproduction", builder.UPSTREAM / "analysis_provenance.py")
        try:
            old.bind_analysis(bundle, args.analysis_provenance, args.analysis_receipt, output / "view.html")
        except ValueError as failure:
            original_failure = str(failure)
            if original_failure != "Analysis and selection identify different supplemental annexes":
                raise
        else:
            raise ValueError("Original production failure was not reproduced")
        bound = builder.bind_analysis(bundle, args.analysis_provenance, args.analysis_receipt, output / "view.html")
        if bound["binding"]["state"] != "verified" or bound["report"] != bundle["report"]:
            raise ValueError("Corrected reader changed estimates or did not verify inputs")
        record["production_check"] = {
            "original005_refusal": original_failure, "new006_binding": bound["binding"],
            "analysis_unchanged": True, "analysis": builder._source(args.analysis_file),
            "analysis_provenance": builder._source(args.analysis_provenance),
            "official_analysis_receipt": builder._source(args.analysis_receipt)}
        builder.verify_upstream()
        after = {p.name: builder._source(p) for p in HERE.iterdir() if p.is_file()}
        if before != after:
            raise ValueError("Reader source changed during validation")
        record["sources_after"] = after
        record["status"] = "completed"
    except Exception as failure:
        error = failure
        record["error"] = type(failure).__name__ + ": " + str(failure)
    record["ended_at"] = datetime.now(timezone.utc).isoformat()
    recovery_runner.original.write_once(output / "validation.json", record)
    print(json.dumps({"status": record["status"], "tests": record["tests"], "error": record["error"]}))
    if error is not None:
        raise error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
