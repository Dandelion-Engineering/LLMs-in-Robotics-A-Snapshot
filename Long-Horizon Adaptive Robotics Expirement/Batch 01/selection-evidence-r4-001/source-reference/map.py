"""Append-only architecture and run evidence index. Python standard library only."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile

SCHEMA = "architecture-map-1.0"
KINDS = {"architecture": "architectures.jsonl", "revision": "revisions.jsonl",
         "run": "runs.jsonl", "result": "results.jsonl", "note": "notes.jsonl"}
COMMON = {"schema_version", "id", "recorded_at", "author", "tags", "details"}
FIELDS = {
    "architecture": {"title", "summary"},
    "revision": {"architecture_id", "parent_revision_id", "status", "title", "summary",
                 "mechanism", "attachments"},
    "run": {"revision_id", "stage", "condition_id", "protocol_id", "scenario_id",
            "paired_block_id", "replicate", "started_at", "rerun_of_run_id",
            "condition_details", "seeds", "frozen_refs", "evidence"},
    "result": {"run_id", "supersedes_result_id", "execution_status", "validity",
               "validity_reason", "outcome", "ended_at", "termination_reason", "metrics", "evidence"},
    "note": {"target_ids", "claim_type", "body", "supersedes_note_id", "evidence"},
}
ENUMS = {
    "status": {"proposed", "implemented", "frozen", "retired"},
    "stage": {"calibration", "development", "evaluation", "diagnostic"},
    "execution_status": {"completed", "failed", "timed_out", "aborted", "not_run"},
    "validity": {"valid", "invalid", "unknown"},
    "outcome": {"success", "partial", "failure", "unknown", "not_assessed"},
    "claim_type": {"note", "question", "decision", "observation", "event", "interpretation",
                   "hypothesis", "source_report", "correction", "comparison"},
}
REF_KEYS = {"label", "uri", "sha256", "state", "access", "locator"}
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")


class MapError(ValueError):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise MapError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    def constant(value):
        raise MapError(f"non-JSON number {value}")

    def number(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise MapError(f"nonfinite JSON number {value}")
        return parsed

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant, parse_float=number)


def read_store(root):
    data, raw, errors = {}, {}, []
    for kind, filename in KINDS.items():
        data[kind] = []
        try:
            payload = (root / filename).read_bytes()
            raw[filename] = payload
            text = payload.decode("utf-8")
            if text.startswith("\ufeff"):
                raise MapError("UTF-8 BOM is not allowed")
            if payload and not payload.endswith(b"\n"):
                errors.append(f"{filename}: missing final newline")
            for number, line in enumerate(text.splitlines(), 1):
                try:
                    if not line.strip():
                        raise MapError("blank physical line")
                    record = strict_json(line)
                    if not isinstance(record, dict):
                        raise MapError("record must be an object")
                    data[kind].append(record)
                except (ValueError, TypeError) as exc:
                    errors.append(f"{filename}:{number}: {exc}")
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f"{filename}: {exc}")
    return data, raw, errors


def store_digest(raw):
    # Include filenames and exact file bytes, including line endings.
    return digest(b"".join(name.encode() + b"\0" + digest(raw[name]).encode() + b"\n"
                           for name in sorted(raw)))


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def finite(value):
    # Python integers are arbitrary precision; avoid float conversion overflow.
    return type(value) is int or (type(value) is float and math.isfinite(value))


def timestamp(value):
    if not nonempty(value):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return "T" in value and parsed.utcoffset() is not None
    except ValueError:
        return False


def validate_records(data, root):
    errors, index, kinds = [], {}, {}

    def fail(label, message):
        errors.append(f"{label}: {message}")

    def strings(value, label, allow_empty=True):
        if not isinstance(value, list) or any(not nonempty(x) for x in value):
            fail(label, "must be a string list")
            return False
        if not allow_empty and not value:
            fail(label, "must not be empty")
        if len(value) != len(set(value)):
            fail(label, "duplicate list members")
        return True

    def references(value, label, attachments=False):
        if not isinstance(value, list):
            fail(label, "must be a reference list")
            return
        for pos, ref in enumerate(value):
            loc = f"{label}[{pos}]"
            if not isinstance(ref, dict) or set(ref) != REF_KEYS:
                fail(loc, f"requires exactly {sorted(REF_KEYS)}")
                continue
            for key in ("label",):
                if not nonempty(ref[key]):
                    fail(loc, f"{key} must be nonempty")
            for key in ("uri", "locator"):
                if ref[key] is not None and not nonempty(ref[key]):
                    fail(loc, f"{key} must be nonempty or null")
            if ref["sha256"] is not None and not (isinstance(ref["sha256"], str) and SHA_RE.fullmatch(ref["sha256"])):
                fail(loc, "sha256 must be lowercase SHA-256 or null")
            if ref["state"] not in ("available", "missing", "unknown"):
                fail(loc, "invalid reference state")
            if ref["access"] not in ("public", "operator", "evaluator_only"):
                fail(loc, "invalid access label")
            if ref["state"] == "available" and not nonempty(ref["uri"]):
                fail(loc, "available reference needs uri")
            if attachments:
                if ref["state"] != "available" or not ref["sha256"] or not nonempty(ref["uri"]):
                    fail(loc, "revision attachment needs available URI and SHA-256")
                    continue
                try:
                    attachment = (root / ref["uri"]).resolve()
                    attachment.relative_to(root.resolve())
                    if digest(attachment.read_bytes()) != ref["sha256"]:
                        fail(loc, "attachment hash differs from immutable snapshot")
                except (OSError, ValueError):
                    fail(loc, "attachment must be an existing file within the map folder")

    def ref_state(value, label):
        if not isinstance(value, dict) or set(value) != {"state", "refs", "reason"}:
            fail(label, "requires state, refs, reason")
            return
        if value["state"] not in ("recorded", "none", "unknown"):
            fail(label, "state must be recorded, none, or unknown")
        references(value["refs"], label + ".refs")
        if value["reason"] is not None and not nonempty(value["reason"]):
            fail(label, "reason must be nonempty or null")
        if value["state"] == "recorded" and not value["refs"]:
            fail(label, "recorded requires references")
        if value["state"] in ("none", "unknown"):
            if value["refs"] != [] or not nonempty(value["reason"]):
                fail(label, "none/unknown requires empty refs and an explicit reason")

    for kind, records in data.items():
        for pos, record in enumerate(records):
            label = f"{KINDS[kind]}:{pos + 1}"
            if set(record) != COMMON | FIELDS[kind]:
                fail(label, f"incorrect keys; expected {sorted(COMMON | FIELDS[kind])}")
            rid = record.get("id")
            if not isinstance(rid, str) or not ID_RE.fullmatch(rid):
                fail(label, "id must use letters, digits, underscore, dot, colon, or hyphen")
            elif rid in index:
                fail(label, f"duplicate global id {rid}")
            else:
                index[rid], kinds[rid] = record, kind
            if record.get("schema_version") != SCHEMA:
                fail(label, f"schema_version must be {SCHEMA}")
            if not timestamp(record.get("recorded_at")):
                fail(label, "recorded_at must be ISO timestamp with timezone")
            if not nonempty(record.get("author")):
                fail(label, "author must be nonempty")
            strings(record.get("tags"), label + ".tags")
            if not isinstance(record.get("details"), dict):
                fail(label, "details must be an open object")
            for key in ("title", "summary", "mechanism", "body", "validity_reason", "termination_reason",
                        "condition_id", "protocol_id", "scenario_id", "paired_block_id"):
                if key in FIELDS[kind] and not nonempty(record.get(key)):
                    fail(label, f"{key} must be nonempty")
            for key, values in ENUMS.items():
                if key in FIELDS[kind] and (not isinstance(record.get(key), str) or record[key] not in values):
                    fail(label, f"{key} must be one of {sorted(values)}")
            if kind == "revision":
                references(record.get("attachments"), label + ".attachments", True)
            if "evidence" in FIELDS[kind]:
                references(record.get("evidence"), label + ".evidence")
            if kind == "run":
                if type(record.get("replicate")) is not int or record["replicate"] < 1:
                    fail(label, "replicate must be a positive integer")
                if record.get("started_at") is not None and not timestamp(record["started_at"]):
                    fail(label, "started_at must be timezone timestamp or null")
                if not isinstance(record.get("condition_details"), dict):
                    fail(label, "condition_details must be an open object")
                ref_state(record.get("seeds"), label + ".seeds")
                frozen = record.get("frozen_refs")
                if not isinstance(frozen, dict) or not {"code", "environment", "models", "protocol", "scenario"} <= set(frozen):
                    fail(label, "frozen_refs requires code, environment, models, protocol, scenario (extra roles allowed)")
                else:
                    for role, ref in frozen.items():
                        ref_state(ref, label + ".frozen_refs." + role)
                        if isinstance(ref, dict) and ref.get("state") == "recorded":
                            for item in ref.get("refs", []) if isinstance(ref.get("refs"), list) else []:
                                if isinstance(item, dict) and not item.get("sha256"):
                                    fail(label, f"frozen {role} references require SHA-256")
            if kind == "result":
                if record.get("ended_at") is not None and not timestamp(record["ended_at"]):
                    fail(label, "ended_at must be timezone timestamp or null")
                if record.get("execution_status") == "not_run":
                    if record.get("outcome") != "not_assessed" or record.get("validity") != "unknown":
                        fail(label, "not_run requires outcome not_assessed and validity unknown")
                    if record.get("ended_at") is not None or record.get("metrics") != []:
                        fail(label, "not_run requires null ended_at and empty metrics")
                elif record.get("ended_at") is None:
                    fail(label, "terminal attempted run requires ended_at")
                if record.get("outcome") in ("success", "partial", "failure") and not record.get("evidence"):
                    fail(label, "assessed outcome requires evidence reference, including explicit missing evidence")
                metrics = record.get("metrics")
                if not isinstance(metrics, list):
                    fail(label, "metrics must be a list")
                else:
                    names = set()
                    for metric in metrics:
                        keys = {"name", "value", "unit", "denominator", "denominator_description", "missing_reason", "evidence"}
                        if not isinstance(metric, dict) or set(metric) != keys:
                            fail(label, f"metric requires exactly {sorted(keys)}")
                            continue
                        for key in ("name", "unit", "denominator_description"):
                            if not nonempty(metric[key]):
                                fail(label, f"metric {key} must be nonempty")
                        if nonempty(metric["name"]):
                            if metric["name"] in names:
                                fail(label, f"duplicate metric name {metric['name']}")
                            names.add(metric["name"])
                        if metric["value"] is None:
                            if not nonempty(metric["missing_reason"]):
                                fail(label, "missing metric value requires missing_reason")
                        elif not finite(metric["value"]) or metric["missing_reason"] is not None:
                            fail(label, "measured metric requires finite numeric value and null missing_reason")
                        if metric["denominator"] is not None and (not finite(metric["denominator"]) or metric["denominator"] <= 0):
                            fail(label, "denominator must be positive finite number or null")
                        references(metric["evidence"], label + ".metric.evidence")
                        if metric["value"] is not None and not metric["evidence"]:
                            fail(label, "measured metric requires evidence")
            if kind == "note":
                strings(record.get("target_ids"), label + ".target_ids", False)

    # Relationships are checked only after all records have been indexed.
    def target(record, key, expected, nullable=False):
        value = record.get(key)
        if nullable and value is None:
            return None
        if not isinstance(value, str) or kinds.get(value) != expected:
            fail(str(record.get("id")), f"{key} must reference an existing {expected}")
            return None
        return index[value]

    for kind in ("revision", "run", "result", "note"):
        previous = set()
        latest_results, latest_notes = {}, {}
        for record in data[kind]:
            rid = record.get("id")
            if kind == "revision":
                target(record, "architecture_id", "architecture")
                parent = target(record, "parent_revision_id", "revision", True)
                if parent and (parent.get("architecture_id") != record.get("architecture_id") or parent.get("id") not in previous):
                    fail(str(rid), "parent revision must be earlier and belong to the same architecture")
            elif kind == "run":
                revision = target(record, "revision_id", "revision")
                if record.get("stage") == "evaluation":
                    if revision and revision.get("status") != "frozen":
                        fail(str(rid), "evaluation requires a frozen revision snapshot")
                    for role, frozen in (record.get("frozen_refs") or {}).items() if isinstance(record.get("frozen_refs"), dict) else []:
                        allowed = ("recorded", "none") if role == "models" else ("recorded",)
                        if role in ("code", "environment", "models", "protocol", "scenario") and isinstance(frozen, dict) and frozen.get("state") not in allowed:
                            fail(str(rid), f"evaluation frozen {role} must be recorded (models may be none)")
                    if isinstance(record.get("seeds"), dict) and record["seeds"].get("state") != "recorded":
                        fail(str(rid), "evaluation requires a recorded protected seed manifest")
                prior = target(record, "rerun_of_run_id", "run", True)
                if prior and prior.get("id") not in previous:
                    fail(str(rid), "rerun must reference an earlier run")
            elif kind == "result":
                run = target(record, "run_id", "run")
                parent = target(record, "supersedes_result_id", "result", True)
                run_id = record.get("run_id")
                if isinstance(run_id, str):
                    if record.get("supersedes_result_id") != latest_results.get(run_id):
                        fail(str(rid), "result must supersede the latest result for this run, or null for its first result")
                    latest_results[run_id] = rid
                if parent and parent.get("run_id") != run_id:
                    fail(str(rid), "superseded result belongs to a different run")
                if run and timestamp(run.get("started_at")) and timestamp(record.get("ended_at")):
                    if datetime.fromisoformat(record["ended_at"].replace("Z", "+00:00")) < datetime.fromisoformat(run["started_at"].replace("Z", "+00:00")):
                        fail(str(rid), "ended_at predates started_at")
            else:
                targets = record.get("target_ids")
                if isinstance(targets, list):
                    for item in targets:
                        if not isinstance(item, str) or item not in index or item == rid:
                            fail(str(rid), "target_ids contains missing or self reference")
                        elif kinds[item] == "note" and item not in previous:
                            fail(str(rid), "note targets must refer to earlier notes")
                parent = target(record, "supersedes_note_id", "note", True)
                if parent:
                    if parent.get("id") not in previous or record.get("claim_type") != "correction":
                        fail(str(rid), "superseding note must be a correction to an earlier note")
                    if parent.get("id") in latest_notes:
                        fail(str(rid), "note already superseded; correct the latest correction")
                    latest_notes[parent.get("id")] = rid
            if isinstance(rid, str):
                previous.add(rid)
    return errors


def rows(data):
    return [(kind, record) for kind in KINDS for record in data[kind]]


def associations(data):
    index = {r["id"]: (kind, r) for kind, r in rows(data)}
    cache = {}

    def linked(rid):
        if rid in cache:
            return cache[rid]
        kind, record = index[rid]
        found = {"architecture": set(), "revision": set(), "run": set()}
        cache[rid] = found
        if kind in found:
            found[kind].add(rid)
        targets = []
        for key in ("architecture_id", "revision_id", "run_id"):
            if key in record:
                targets.append(record[key])
        if kind == "note":
            targets.extend(record["target_ids"])
            if record["supersedes_note_id"]:
                targets.append(record["supersedes_note_id"])
        for target_id in targets:
            for key, values in linked(target_id).items():
                found[key].update(values)
        return found

    for rid in index:
        linked(rid)
    return cache


def lookup(data, text="", kind=None, limit=20, **filters):
    assoc = associations(data)
    runs = {r["id"]: r for r in data["run"]}
    hits = []
    for record_kind, record in rows(data):
        if kind and kind != record_kind:
            continue
        if text.casefold() not in json.dumps(record, ensure_ascii=False, sort_keys=True).casefold():
            continue
        match = True
        for key, value in filters.items():
            if value is None:
                continue
            if key in ("architecture", "revision", "run"):
                ok = value in assoc[record["id"]][key]
            elif key == "tag":
                ok = value in record["tags"]
            else:
                field = "condition_id" if key == "condition" else key
                source = record
                if record_kind == "result" and field in ("stage", "condition_id", "protocol_id", "scenario_id", "paired_block_id", "replicate"):
                    source = runs[record["run_id"]]
                ok = source.get(field) == value
            match = match and ok
        if match:
            hits.append({"kind": record_kind, "record": record})
    return {"total": len(hits), "displayed": min(limit, len(hits)), "records": hits[:limit]}


def history(data, rid):
    index = {r["id"]: (kind, r) for kind, r in rows(data)}
    if rid not in index:
        return {"target": rid, "total": 0, "displayed": 0, "records": []}
    kind, record = index[rid]
    assoc = associations(data)
    selected = {rid}
    if kind in ("architecture", "revision", "run"):
        selected.update(key for key, links in assoc.items() if rid in links[kind])
    if kind == "result":
        selected.update(r["id"] for r in data["result"] if r["run_id"] == record["run_id"])
    for key in ("architecture", "revision", "run"):
        selected.update(assoc[rid][key])
    if kind == "revision":
        parent = record["parent_revision_id"]
        while parent:
            selected.add(parent)
            parent = index[parent][1]["parent_revision_id"]
    if kind == "note":
        ancestor = record
        while ancestor:
            selected.add(ancestor["id"])
            selected.update(ancestor["target_ids"])
            previous_id = ancestor["supersedes_note_id"]
            ancestor = index[previous_id][1] if previous_id else None
    # Follow notes on the selected evidence, without expanding sibling runs.
    for note in data["note"]:
        if selected.intersection(note["target_ids"]) or note["supersedes_note_id"] in selected:
            selected.add(note["id"])
    result = [{"kind": k, "record": r} for k, r in rows(data) if r["id"] in selected]
    return {"target": rid, "total": len(result), "displayed": len(result), "records": result}


def catalog(data):
    counts = {kind: len(records) for kind, records in data.items()}
    result_run_ids = {r["run_id"] for r in data["result"]}
    lines = ["# Architecture Map catalog", "", "Generated by `map.py build`; canonical JSONL records are authoritative.", "",
             "| Collection | Records |", "|---|---:|"]
    lines += [f"| {kind} | {counts[kind]} |" for kind in KINDS]
    lines += ["", f"Runs awaiting a result record: {len(data['run']) - len(result_run_ids)}.", ""]
    if not data["architecture"]:
        lines += ["The map is empty. No architectures, revisions, runs, results, or findings have been registered.",
                  "An empty index is ready for future authorized work; it is not evidence that an experiment occurred.", ""]
    def escape(text):
        return text.replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    for kind in KINDS:
        if data[kind]:
            lines += [f"## {kind.title()} records", "", "| ID | Description |", "|---|---|"]
            for rec in data[kind]:
                description = rec.get("title", rec.get("body", rec.get("termination_reason", rec.get("condition_id", ""))))
                lines.append(f"| `{rec['id']}` | {escape(description)} |")
            lines.append("")
    lines += ["Lookup returns full records and total/displayed counts. `history ID --json` follows linked evidence.",
              "Results include superseded assessments; use their correction chain before interpreting current status.",
              "Structural validation does not establish physical success, causal attribution, evidence completeness, or comparability.", ""]
    return "\n".join(lines).encode("utf-8")


def check(root, check_catalog=True):
    data, raw, errors = read_store(root)
    errors.extend(validate_records(data, root))
    if check_catalog and not errors:
        try:
            if (root / "Catalog.md").read_bytes() != catalog(data):
                errors.append("Catalog.md is stale; run map.py build")
        except OSError:
            errors.append("Catalog.md missing; run map.py build")
    report = {"schema_version": SCHEMA, "checked_at": utc_now(), "ok": not errors,
              "counts": {kind: len(records) for kind, records in data.items()},
              "canonical_sha256": {name: digest(payload) for name, payload in sorted(raw.items())},
              "store_sha256": store_digest(raw), "catalog_sha256": None, "errors": errors,
              "scope": "Structure, local revision attachments, relationships and generated catalog; not scientific validity or external evidence availability."}
    if (root / "Catalog.md").is_file():
        report["catalog_sha256"] = digest((root / "Catalog.md").read_bytes())
    return data, raw, report


@contextmanager
def writer_lock(root):
    path = root / ".map-write.lock"
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise MapError(f"writer lock exists: {path}; do not remove an active writer's lock") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(f"pid={os.getpid()} time={utc_now()}\n")
        yield
    finally:
        path.unlink()


def atomic_write(path, payload):
    fd, temp_name = tempfile.mkstemp(prefix=".map-tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def append_record(root, kind, record, expected):
    with writer_lock(root):
        data, raw, report = check(root, check_catalog=False)
        if report["errors"]:
            raise MapError("existing records are invalid: " + "; ".join(report["errors"]))
        if report["store_sha256"] != expected:
            raise MapError("store changed since inspection; refresh status and review before retrying")
        if not isinstance(record, dict):
            raise MapError("input must be one JSON object")
        data[kind].append(record)
        errors = validate_records(data, root)
        if errors:
            raise MapError("; ".join(errors))
        addition = (json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
        filename = KINDS[kind]
        # Check again just before replacement to detect ordinary out-of-band edits.
        current = {name: (root / name).read_bytes() for name in KINDS.values()}
        if current != raw:
            raise MapError("canonical files changed during append; no write performed")
        atomic_write(root / filename, raw[filename] + addition)
    return {"appended": record["id"], "kind": kind, "next": "Run build, then validate --output validation.json."}


def template(kind):
    # Output only: these incomplete drafting forms are never canonical examples.
    common = {"schema_version": SCHEMA, "id": "", "recorded_at": utc_now(), "author": "", "tags": [], "details": {}}
    unknown = lambda: {"state": "unknown", "refs": [], "reason": "Not yet established; replace with actual basis."}
    extra = {
        "architecture": {"title": "", "summary": ""},
        "revision": {"architecture_id": "", "parent_revision_id": None, "status": "proposed", "title": "", "summary": "", "mechanism": "", "attachments": []},
        "run": {"revision_id": "", "stage": "development", "condition_id": "", "protocol_id": "", "scenario_id": "", "paired_block_id": "", "replicate": 1, "started_at": None, "rerun_of_run_id": None, "condition_details": {}, "seeds": unknown(), "frozen_refs": {key: unknown() for key in ("code", "environment", "models", "protocol", "scenario")}, "evidence": []},
        "result": {"run_id": "", "supersedes_result_id": None, "execution_status": "not_run", "validity": "unknown", "validity_reason": "", "outcome": "not_assessed", "ended_at": None, "termination_reason": "", "metrics": [], "evidence": []},
        "note": {"target_ids": [], "claim_type": "interpretation", "body": "", "supersedes_note_id": None, "evidence": []},
    }
    return common | extra[kind]


def print_lookup(result, as_json):
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print(f"{result['total']} match(es); displaying {result['displayed']}.")
    if not result["records"]:
        print("No records matched. An empty map or search result is not negative experimental evidence.")
    for item in result["records"]:
        rec = item["record"]
        label = rec.get("title", rec.get("body", rec.get("termination_reason", rec.get("condition_id", ""))))
        print(f"[{item['kind']}] {rec['id']}: {label}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent,
                        help="Map directory (default: beside this script)")
    sub = parser.add_subparsers(dest="command", required=True)
    query = sub.add_parser("lookup", help="Full-record substring search with exact AND filters")
    query.add_argument("text", nargs="?", default="")
    query.add_argument("--kind", choices=KINDS)
    for name in ("id", "architecture", "revision", "run", "tag", "stage", "condition", "validity", "outcome", "claim-type", "status", "execution-status", "protocol-id", "scenario-id", "paired-block-id"):
        query.add_argument("--" + name)
    query.add_argument("--limit", type=int, default=20)
    query.add_argument("--replicate", type=int)
    query.add_argument("--json", action="store_true")
    hist = sub.add_parser("history", help="Return linked ancestors, descendants and notes")
    hist.add_argument("id")
    hist.add_argument("--json", action="store_true")
    status = sub.add_parser("status", help="Counts and current canonical store hash")
    status.add_argument("--json", action="store_true")
    sub.add_parser("build", help="Validate records and atomically regenerate Catalog.md")
    val = sub.add_parser("validate", help="Check records, relationships, attachments and catalog")
    val.add_argument("--output", type=Path, help="Write hash-bound report; filename resolves inside map directory")
    val.add_argument("--json", action="store_true")
    add = sub.add_parser("append", help="Validate and append exactly one new immutable record")
    add.add_argument("kind", choices=KINDS)
    add.add_argument("--input", required=True, type=Path)
    add.add_argument("--expected-sha256", required=True)
    form = sub.add_parser("template", help="Print incomplete drafting form; does not add records")
    form.add_argument("kind", choices=KINDS)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "template":
            print(json.dumps(template(args.kind), ensure_ascii=False, indent=2))
            return 0
        if args.command == "append":
            record = strict_json(args.input.read_text(encoding="utf-8"))
            print(json.dumps(append_record(root, args.kind, record, args.expected_sha256), indent=2))
            return 0
        if args.command == "build":
            with writer_lock(root):
                data, _, report = check(root, check_catalog=False)
                if report["errors"]:
                    raise MapError("; ".join(report["errors"]))
                atomic_write(root / "Catalog.md", catalog(data))
            print("Built Catalog.md from validated canonical records.")
            return 0
        if args.command == "validate":
            if args.output:
                output = (root / args.output).resolve()
                if output.parent != root or output.name != "validation.json":
                    raise MapError("--output must be validation.json in the map folder")
                with writer_lock(root):
                    _, _, report = check(root)
                    atomic_write(output, json_bytes(report))
            else:
                _, _, report = check(root)
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                print("PASS" if report["ok"] else "FAIL")
                print(json.dumps(report["counts"]))
                for error in report["errors"]:
                    print(error)
            return 0 if report["ok"] else 1
        data, _, report = check(root, check_catalog=False)
        if report["errors"]:
            raise MapError("; ".join(report["errors"]))
        if args.command == "status":
            print(json.dumps({key: report[key] for key in ("schema_version", "counts", "canonical_sha256", "store_sha256")}, indent=2))
        elif args.command == "history":
            print_lookup(history(data, args.id), args.json)
        else:
            if args.limit < 0:
                raise MapError("--limit must be nonnegative")
            ignored = {"root", "command", "text", "kind", "limit", "json"}
            filters = {key: value for key, value in vars(args).items() if key not in ignored}
            print_lookup(lookup(data, args.text, args.kind, args.limit, **filters), args.json)
        return 0
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
