"""Queued post-image-retirement semantic replay; writes only new historical reports.

Root must signal image retirement complete before submitting. Does not retire
anything, restore images, simulate, call a model, or change the original codec
qualification. Expected numerical/event hashes were established before retirement.
"""
from __future__ import annotations
import argparse
import gc
import hashlib
import json
from pathlib import Path
import sys
import time

import raw_codec as codec
import qualify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retirement-receipt", type=Path, required=True)
    parser.add_argument("--retirement-queue-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    started = time.time()
    output = args.output.resolve()
    if not output.is_relative_to(qualify.HERE) or output.exists():
        raise ValueError("Output must be a new file within historical/")
    retirement = json.loads(args.retirement_receipt.read_text(encoding="utf-8"))
    queue = json.loads(args.retirement_queue_receipt.read_text(encoding="utf-8"))
    if retirement.get("status") != "completed" or queue.get("state") != "succeeded" or queue.get("exit_status") != 0:
        raise ValueError("Completed retirement and successful queue receipts required")
    if retirement.get("successful_continuation_job_id") != queue.get("id"):
        raise ValueError("Retirement receipt must identify this successful continuation job")
    if Path(queue.get("cwd", "")).resolve() != qualify.EXP.parent.resolve():
        raise ValueError("Retirement job ran in a different project")
    pre = json.loads((qualify.HERE / "pre-retirement-input-identities.json").read_text(encoding="utf-8"))
    qualification = json.loads((qualify.HERE / "qualification.json").read_text(encoding="utf-8"))
    expected = json.loads((qualify.HERE / "equivalence-original.json").read_text(encoding="utf-8"))
    if hashlib.sha256(codec.canonical(expected)).hexdigest() != qualification["equivalence"]["canonical_outputs_sha256"]:
        raise ValueError("Original semantic expectation changed")
    if codec.digest(qualify.HERE / "qualification.json") != pre["qualification_sha256"]:
        raise ValueError("Original qualification changed")
    checked = {}
    for ref in pre["inputs"]:
        path = qualify.EXP / ref["path"]
        actual = {"sha256": codec.digest(path), "bytes": path.stat().st_size}
        if actual != {key: ref[key] for key in ("sha256", "bytes")}:
            raise ValueError("Pre-retirement source identity changed: " + ref["path"])
        checked[ref["path"]] = actual
    for relative, digest in qualification["source_methods"].items():
        if codec.digest(qualify.EXP / relative) != digest:
            raise ValueError("Scientific method changed")
    sys.path.insert(0, str(qualify.EXP / "Engineering Investigation 005"))
    diagnostics = qualify.load_module("historical_post_diagnostics", qualify.EXP / "Runtime 004/diagnostics.py")
    continuity = qualify.load_module("historical_post_continuity", qualify.EXP / "Engineering Investigation 005/continuity.py")
    evidence = qualify.RELEASE / "attempts" / qualify.SEMANTIC_RUN / "evidence"
    manifest, result = [json.loads((evidence / name).read_text(encoding="utf-8")) for name in ("manifest.json", "result.json")]
    events, motion = qualify.lines(evidence / "events.jsonl"), qualify.lines(evidence / "motion.jsonl")
    diagnostics.validate_events(events, qualify.SEMANTIC_RUN)
    d = diagnostics.analyze(events, motion, result, manifest)
    del d["created_at"]
    context = continuity.qualified_restart.load_evaluation_context(qualify.RELEASE, manifest)
    c = continuity.extract(manifest, result, events, rubric_sha256=codec.digest(continuity.RUBRIC), qualification_context=context)
    actual = {"diagnostics": d, "continuity": c}
    if expected != actual:
        raise AssertionError("Post-retirement diagnostics or continuity changed")
    del events, motion
    gc.collect()
    # Confirm stability across the complete replay, not only on entry.
    for relative, ref in checked.items():
        path = qualify.EXP / relative
        if path.stat().st_size != ref["bytes"] or codec.digest(path) != ref["sha256"]:
            raise ValueError("Input changed during replay")
    result = {"schema": "post-image-retirement-historical-replay-1", "status": "passed",
              "run_id": qualify.SEMANTIC_RUN, "started_unix": started, "finished_unix": time.time(),
              "retirement_receipt_sha256": codec.digest(args.retirement_receipt),
              "retirement_queue_receipt_sha256": codec.digest(args.retirement_queue_receipt),
              "retirement_queue_job": queue["id"], "pre_input_identities_sha256": codec.digest(qualify.HERE / "pre-retirement-input-identities.json"),
              "qualification_sha256": pre["qualification_sha256"], "source_identities": checked,
              "source_methods": qualification["source_methods"], "diagnostics_equal": True, "continuity_equal": True,
              "canonical_outputs_sha256": hashlib.sha256(codec.canonical(actual)).hexdigest(),
              "ignored_fields": ["diagnostics.created_at"],
              "implementation_sha256": codec.digest(Path(__file__)),
              "claim": "The original A2 C14 numerical/qualified-continuity workflow still computes the same complete semantic outputs after image retirement. No image file was an input to these methods.",
              "limits": "One representative semantic replay, not all-run recalculation or image reconstruction. Aggregate comparison is a separate root-owned check."}
    qualify.save_new(output, result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
