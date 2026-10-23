"""Read-only representative r4 qualification; submit through shared compute queue.

Writes only this prototype directory. Keeps sources and compressed prototypes;
removes only its own single restored scratch file after verification. No simulator,
model request, scored run, campaign migration, or source evidence deletion.
"""
from __future__ import annotations
import collections
import gc
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import time
import unittest

import raw_codec as codec

HERE = Path(__file__).resolve().parent
EXP = HERE.parents[1]
RELEASE = EXP / "Evidence/releases/batch01-eval-r4"
RUNS = [
    ("batch01-eval-r4-C20-rep1-baseline-persistent", "Longest r4 event stream in complete 264-run audit; partial outcome"),
    ("batch01-eval-r4-C24-rep1-A1-persistent", "Long stream; model requests; restart; late model response; failure"),
    ("batch01-eval-r4-C14-rep1-A2-persistent", "Restart; checkpoint activity; confirmed 30 s model timeout; failure; semantic equivalence case"),
    ("batch01-eval-r4-C24-rep1-A3-persistent", "Long stream; model requests; restart; partial outcome"),
]
SEMANTIC_RUN = RUNS[2][0]
TYPE = re.compile(rb'"event_type"\s*:\s*"([^"\\]+)"')


def save_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)
        f.write("\n")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def lines(path):
    with path.open("rb") as f:
        return [json.loads(line) for line in f]


def compare_bytes(source, restored):
    h, count = hashlib.sha256(), 0
    with source.open("rb") as a, restored.open("rb") as b:
        while True:
            x, y = a.read(codec.MAX_CHUNK), b.read(codec.MAX_CHUNK)
            if x != y:
                raise AssertionError("Raw byte comparison failed")
            if not x:
                break
            h.update(x)
            count += len(x)
    return h.hexdigest(), count


def profile_events(path):
    counts, maxima = collections.Counter(), {}
    content_count, content_max = 0, None
    # Only decode decision/checkpoint/restart events for coverage profiling; the
    # codec itself never parses JSON and handles arbitrarily split input bytes.
    selected = {"candidate_input", "candidate_reply", "model_request", "model_response",
                "restart_begin", "restart_absence", "restart_ready", "model_lifecycle_terminal", "model_error"}
    def walk(value, event):
        nonlocal content_count, content_max
        if isinstance(value, dict):
            content = value.get("content_utf8")
            if isinstance(content, str):
                content_count += 1
                length = len(content.encode("utf-8"))
                if content_max is None or length > content_max["bytes"]:
                    content_max = {"bytes": length, "event_id": event["event_id"],
                                   "event_type": event["event_type"], "record_type": value.get("type"),
                                   "path": value.get("path"), "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()}
            for child in value.values():
                walk(child, event)
        elif isinstance(value, list):
            for child in value:
                walk(child, event)
    with path.open("rb") as f:
        for line in f:
            match = TYPE.search(line[:2048])
            kind = match[1].decode() if match else "(unclassified)"
            counts[kind] += 1
            if len(line) > maxima.get(kind, {}).get("bytes", 0):
                maxima[kind] = {"bytes": len(line), "ordinal": sum(counts.values())}
            if kind in selected:
                event = json.loads(line)
                walk(event, event)
    return {"event_counts": dict(counts), "maximum_record_bytes_by_type": maxima,
            "exact_content_utf8_occurrences": content_count, "largest_exact_content_utf8": content_max,
            "note": "Content-byte coverage is measured within selected runs; not a global maximum or random sample."}


def main():
    started = time.time()
    if (HERE / "qualification.json").exists():
        raise FileExistsError("Refusing to replace qualification")
    suite = unittest.defaultTestLoader.discover(str(HERE), pattern="test_raw_codec.py")
    tests = unittest.TextTestRunner(verbosity=2).run(suite)
    if not tests.wasSuccessful():
        raise AssertionError("Codec unit tests failed")
    archives, scratch, manifests = [HERE / name for name in ("archives", "scratch", "manifests")]
    for path in (archives, scratch, manifests):
        path.mkdir(exist_ok=True)
    if any(scratch.iterdir()):
        raise ValueError("Scratch must start empty")
    # Full deterministic diagnostics/continuity, same real source methods, with
    # original inputs first and reconstructed inputs second. Ignore only the
    # diagnostics created_at wall clock. Restored arrays outlive their temporary
    # file so only ONE full-size restored file ever exists on disk.
    sys.path.insert(0, str(EXP / "Engineering Investigation 005"))
    diagnostics = load_module("historical_diagnostics", EXP / "Runtime 004/diagnostics.py")
    continuity = load_module("historical_continuity", EXP / "Engineering Investigation 005/continuity.py")
    qualified = continuity.qualified_restart
    root = RELEASE / "attempts" / SEMANTIC_RUN / "evidence"
    manifest, result = [json.loads((root / name).read_text(encoding="utf-8")) for name in ("manifest.json", "result.json")]
    context = qualified.load_evaluation_context(RELEASE, manifest)
    rubric_sha = codec.digest(continuity.RUBRIC)
    def calculate(events, motion):
        diagnostics.validate_events(events, SEMANTIC_RUN)
        d = diagnostics.analyze(events, motion, result, manifest)
        del d["created_at"]
        c = continuity.extract(manifest, result, events, rubric_sha256=rubric_sha, qualification_context=context)
        return {"diagnostics": d, "continuity": c}
    print("Calculating original A2 diagnostics and continuity", flush=True)
    expected = calculate(lines(root / "events.jsonl"), lines(root / "motion.jsonl"))
    gc.collect()
    save_new(HERE / "equivalence-original.json", expected)
    entries, coverage, retained_archive_bytes, peak_workspace_bytes = [], [], 0, 0
    restored_semantic = {}
    source_refs = []
    for run_id, rationale in RUNS:
        evidence = RELEASE / "attempts" / run_id / "evidence"
        print("Coverage " + run_id, flush=True)
        profile = profile_events(evidence / "events.jsonl")
        outcome = json.loads((evidence / "result.json").read_text(encoding="utf-8"))
        coverage.append({"run_id": run_id, "rationale": rationale, "outcome": outcome.get("outcome"),
                         "termination_reason": outcome.get("termination_reason"), "profile": profile})
        for name in ("events.jsonl", "motion.jsonl"):
            source = evidence / name
            before = source.stat()
            source_refs.append((source, before.st_size, before.st_mtime_ns))
            if shutil.disk_usage(HERE).free < before.st_size * 2 + 2 * 1024 ** 3:
                raise ValueError("Insufficient bounded archive/restore headroom")
            archive = archives / (run_id + "-" + name + ".r4raw")
            restored = scratch / name
            print("Packing " + run_id + "/" + name, flush=True)
            m = codec.pack(source, archive)
            save_new(manifests / (archive.name + ".json"), m)
            retained_archive_bytes += m["archive_bytes"]
            r = codec.restore(archive, m, restored)
            temporary_bytes = restored.stat().st_size
            peak_workspace_bytes = max(peak_workspace_bytes, retained_archive_bytes + temporary_bytes)
            verified_sha, verified_bytes = compare_bytes(source, restored)
            assert verified_sha == r["restored_sha256"] == m["source_sha256"]
            assert verified_bytes == m["source_bytes"]
            after = source.stat()
            assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
            if run_id == SEMANTIC_RUN:
                restored_semantic[name] = lines(restored)
            # Only this known, newly-created derivative is removed.
            restored.unlink()
            entry = {"run_id": run_id, "file": name, **m, **r, "exact_byte_comparison": True,
                     "source_unchanged_hash_and_stat": True, "temporary_restored_peak_bytes": temporary_bytes,
                     "ratio_archive_to_original": m["archive_bytes"] / m["source_bytes"]}
            entries.append(entry)
            print(json.dumps({k: entry[k] for k in ("run_id", "file", "source_bytes", "archive_bytes", "pack_seconds", "restore_seconds")}), flush=True)
        if run_id == SEMANTIC_RUN:
            actual = calculate(restored_semantic["events.jsonl"], restored_semantic["motion.jsonl"])
            assert expected == actual, "Diagnostic or continuity semantic output changed"
            save_new(HERE / "equivalence-restored.json", actual)
            restored_semantic.clear()
            gc.collect()
    for source, size, mtime in source_refs:
        st = source.stat()
        assert (st.st_size, st.st_mtime_ns) == (size, mtime), "Original stat changed before completion"
    result = {"format": "historical-codec-qualification-1", "started_unix": started, "finished_unix": time.time(),
              "tests_passed": tests.testsRun, "entries": entries, "coverage": coverage,
              "source_bytes": sum(x["source_bytes"] for x in entries), "archive_bytes": retained_archive_bytes,
              "single_restored_file_peak_bytes": max(x["temporary_restored_peak_bytes"] for x in entries),
              "archive_plus_restore_peak_bytes": peak_workspace_bytes, "scratch_empty": not any(scratch.iterdir()),
              "equivalence": {"run_id": SEMANTIC_RUN, "diagnostics_equal": True, "continuity_equal": True,
                              "qualification_context_loaded": True, "ignored_fields": ["diagnostics.created_at"],
                              "canonical_outputs_sha256": hashlib.sha256(codec.canonical(expected)).hexdigest()},
              "source_methods": {str(path.relative_to(EXP)): codec.digest(path) for path in
                                 [Path(diagnostics.__file__), Path(continuity.__file__), Path(qualified.__file__), continuity.RUBRIC]},
              "implementation_sha256": {name: codec.digest(HERE / name) for name in ("raw_codec.py", "test_raw_codec.py", "qualify.py")},
              "limitations": ["Four purposively selected runs; compression ratios are not an all-r4 estimate.",
                              "No original was deleted or migrated; old tools still read original filenames.",
                              "Restoration is required for unchanged old path-based readers.",
                              "Aggregate result/manifest analysis inputs were untouched; no aggregate rerun in this job.",
                              "Full semantic recomputation was bounded to the A2 timeout/restart case; all eight files had exact byte/hash verification.",
                              "Workspace byte peak is a measured logical archive-plus-single-restore peak, excluding filesystem allocation, sidecars and RAM."]}
    save_new(HERE / "qualification.json", result)
    print(json.dumps({k: result[k] for k in ("source_bytes", "archive_bytes", "single_restored_file_peak_bytes", "archive_plus_restore_peak_bytes", "equivalence")}), flush=True)


if __name__ == "__main__":
    main()
