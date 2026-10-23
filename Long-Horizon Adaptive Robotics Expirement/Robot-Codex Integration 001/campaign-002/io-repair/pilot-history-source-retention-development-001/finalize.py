"""Retain the completed report-only development and candidate validation record."""
from __future__ import annotations

import ast
import copy
import difflib
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent.parent
INVESTIGATION = CAMPAIGN / "investigation"
STAGING = INVESTIGATION / "v27-append-staging"


def binding(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check(item):
    actual = binding(item["path"])
    assert all(actual[key] == item[key] for key in ("sha256", "bytes")), item["path"]
    return actual


def save(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def normalized(tree):
    tree = copy.deepcopy(tree)
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.FunctionDef) and node.name in ("archived_pilot_assessor", "pilot_detail")
        or isinstance(node, ast.Import) and len(node.names) == 1 and node.names[0].name in ("io", "zipfile")
    )]
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "pathlib":
            node.names = [name for name in node.names if name.name != "PurePosixPath"]
    return ast.dump(tree, include_attributes=False)


def main():
    assert not (HERE / "receipt.json").exists(), "Final receipt is exclusive"
    intent = load(HERE / "intent.json")
    green = load(HERE / "green-001/receipt.json")
    red = load(HERE / "red-001/receipt.json")
    failed_stage = load(HERE / "stage-002/receipt.json")
    stage = load(HERE / "stage-003/receipt.json")
    staged = load(STAGING / "pilot-stock024-003/staged-receipt.json")
    qa = load(STAGING / "pilot-stock024-003/qa.json")
    assert red["exit_code"] == 1 and red["expected_pre_fix_failure"] is True
    assert failed_stage["exit_code"] == 1 and stage["exit_code"] == 0
    assert green["exit_code"] == 0 and green["sources_before"] == green["sources_after"]
    assert "Ran 136 tests" in Path(green["stderr"]["path"]).read_text(encoding="utf-8")
    for record in (red, green, failed_stage, stage):
        check(record["stdout"])
        check(record["stderr"])
    sources = [check(item) for item in green["sources_after"]]
    history = check(intent["history"])
    old_plan = check(intent["old_plan"])
    old_candidate = check(intent["old_candidate"])
    before = [check(row["before_copy"]) for row in intent["sources_before"]]
    exports = [check(item) for item in staged["exports_before_and_after"]]
    assert len(exports) == 19
    assert qa["passed"] is True and qa["rows_before"] == 114 and qa["rows_after"] == 115
    assert qa["prior_raw_rows_preserved"] == 114
    assert all(qa[key] is False for key in ("active_outputs_read", "outcomes_recomputed", "exports_rebuilt"))
    candidate = check(staged["candidate_history"])
    check(staged["qa"])
    source_copy = binding(STAGING / "pilot-stock024-source-001/assess.py")
    assert source_copy["sha256"] == "4cb703c8186f38ac20f9c50fe124fa9e4f751629b91f932a57afe269891e373e"
    assert source_copy["bytes"] == 48247

    original = (HERE / "before/qualification_report.py").read_text(encoding="utf-8")
    current = (INVESTIGATION / "qualification_report.py").read_text(encoding="utf-8")
    assert normalized(ast.parse(original)) == normalized(ast.parse(current))
    parity = {
        "schema": "campaign002-pilot-history-source-parity-1",
        "passed": True,
        "scope": "Only new archived_pilot_assessor, existing pilot_detail, and io/zipfile/PurePosixPath imports differ; all other module AST is identical",
        "original_source": before[0],
        "current_source": binding(INVESTIGATION / "qualification_report.py"),
    }
    save(HERE / "source-parity.json", parity)
    with (HERE / "source.patch").open("x", encoding="utf-8", newline="\n") as stream:
        stream.writelines(difflib.unified_diff(original.splitlines(True), current.splitlines(True), fromfile="before/qualification_report.py", tofile="qualification_report.py"))
    records = [
        HERE / "intent.json", HERE / "red-001/receipt.json", HERE / "green-001/receipt.json",
        HERE / "stage-002/receipt.json", HERE / "stage-003/receipt.json",
        STAGING / "pilot-stock024-source-001/provenance.json",
        STAGING / "pilot-stock024-source-retention-correction-001.json",
        STAGING / "pilot-stock024-source-retention-correction-002.json",
        STAGING / "pilot-stock024-plan-003.json",
        STAGING / "pilot-stock024-drafts/pilot-stock-024-row-retained-source-002.json",
        STAGING / "pilot-stock024-003/staged-receipt.json",
        STAGING / "pilot-stock024-003/qa.json",
        HERE / "source-parity.json", HERE / "source.patch", Path(__file__),
    ]
    receipt = {
        "schema": "campaign002-pilot-history-source-retention-completed-1",
        "at": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "sources": sources,
        "before_copies": before,
        "focused_report_and_qa_tests": 136,
        "retained_failures": [
            {"record": binding(HERE / "red-001/receipt.json"), "reason": "Old reader rejects exact archived assessor location"},
            {"record": binding(HERE / "stage-002/receipt.json"), "reason": "First corrected draft retained a stale mutable source artifact in current_status; material plan003 correction replaces that exact binding"},
        ],
        "canonical_history_unchanged": history,
        "original_plan_unchanged": old_plan,
        "original_candidate_unchanged": old_candidate,
        "exports_unchanged": exports,
        "retained_original_assessor": source_copy,
        "candidate_history": candidate,
        "rows_before": 114,
        "rows_after": 115,
        "prior_raw_rows_preserved": 114,
        "canonical_history_written": False,
        "original_pilot_verdict": "invalid/task_unknown",
        "assessor_executed": False,
        "outcomes_recomputed": False,
        "exports_rebuilt": False,
        "accounting_mutated": False,
        "map_mutated": False,
        "records": [binding(path) for path in records],
    }
    save(HERE / "receipt.json", receipt)
    print(json.dumps({"receipt": binding(HERE / "receipt.json"), "candidate": candidate, "tests": 136, "preserved_rows": 114, "preserved_exports": 19}, indent=2))


if __name__ == "__main__":
    main()
