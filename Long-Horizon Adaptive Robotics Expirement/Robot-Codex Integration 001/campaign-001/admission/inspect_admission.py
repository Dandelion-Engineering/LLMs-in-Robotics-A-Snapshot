"""Read-only capacity and retained-journal timing assessment. No admission override."""
from __future__ import annotations
import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
RCI = HERE.parents[1]
EXP = RCI.parent
REPO = EXP.parent
GB = 1_000_000_000
MODEL_PATHS = {
    f"{runtime}/vendor/model/{name}"
    for runtime in ("Runtime", "Runtime 004", "Runtime Release 002")
    for name in ("Qwen3-4B-Q4_K_M.gguf", "Qwen3-14B-Q4_K_M.gguf")
}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def plain(path, entry_stat):
    if stat.S_ISLNK(entry_stat.st_mode) or getattr(entry_stat, "st_file_attributes", 0) & 0x400:
        raise ValueError(f"Refuse symbolic link/reparse object: {path}")


def inventory(root):
    root = Path(root).resolve()
    plain(root, root.lstat())
    result = {}
    directory_meta = {}
    def refuse(error):
        raise error
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=refuse):
        dirs.sort()
        files.sort()
        parent = Path(directory)
        ds = parent.lstat()
        plain(parent, ds)
        directory_meta[parent.relative_to(root).as_posix()] = ds.st_mtime_ns
        for name in dirs:
            child = parent / name
            plain(child, child.lstat())
        for name in files:
            child = parent / name
            item = child.lstat()
            plain(child, item)
            if not stat.S_ISREG(item.st_mode) or item.st_ino == 0 or item.st_nlink < 1:
                raise ValueError(f"Unqualified file type/identity: {child}")
            result[child.relative_to(root).as_posix()] = (
                item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_nlink)
    return result, directory_meta


def totals(items):
    logical = sum(value[2] for value in items.values())
    identities = {}
    areas = {}
    models = []
    for path, value in items.items():
        key = value[:2]
        prior = identities.setdefault(key, {"bytes": value[2], "paths": [], "all_paths_are_models": True})
        if prior["bytes"] != value[2]:
            raise ValueError("Inconsistent size for identical file identity")
        prior["paths"].append(path)
        prior["all_paths_are_models"] &= path in MODEL_PATHS
        if path in MODEL_PATHS:
            models.append({"path": path, "device": value[0], "file_id": value[1], "bytes": value[2], "link_count": value[4]})
        area = path.split("/", 1)[0]
        area_value = areas.setdefault(area, {"files": 0, "logical_bytes": 0, "identities": {}})
        area_value["files"] += 1
        area_value["logical_bytes"] += value[2]
        area_value["identities"][key] = value[2]
    for area in areas.values():
        area["unique_file_identity_logical_bytes"] = sum(area.pop("identities").values())
    unique = sum(item["bytes"] for item in identities.values())
    model_unique = sum(item["bytes"] for item in identities.values() if item["all_paths_are_models"])
    return {
        "files": len(items), "whole_tree_logical_bytes": logical,
        "unique_file_identities": len(identities), "unique_file_identity_logical_bytes": unique,
        "repeated_hardlink_path_bytes": logical - unique,
        "explicit_model_paths": models,
        "model_only_unique_file_identity_logical_bytes": model_unique,
        "conservative_non_model_unique_file_identity_logical_bytes": unique - model_unique,
        "areas": dict(sorted(areas.items())),
    }


class CensusTests(unittest.TestCase):
    def test_same_identity_counted_once_without_excluding_other_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a").write_bytes(b"1234")
            os.link(root / "a", root / "b")
            (root / "c").write_bytes(b"1234")
            value = totals(inventory(root)[0])
            self.assertEqual(value["whole_tree_logical_bytes"], 12)
            self.assertEqual(value["unique_file_identity_logical_bytes"], 8)
            self.assertEqual(value["conservative_non_model_unique_file_identity_logical_bytes"], 8)

    def test_shared_model_evidence_identity_is_not_excluded(self):
        path = sorted(MODEL_PATHS)[0]
        result = totals({path: (1, 1, 4, 0, 2), "Evidence/a": (1, 1, 4, 0, 2)})
        self.assertEqual(result["model_only_unique_file_identity_logical_bytes"], 0)

    def test_reparse_and_symlink_rejected(self):
        from types import SimpleNamespace
        for entry in (SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0),
                      SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)):
            with self.assertRaises(ValueError):
                plain(Path("fake"), entry)

    def test_census_detects_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / "a"
            file.write_bytes(b"old")
            before = inventory(root)
            file.write_bytes(b"changed")
            self.assertNotEqual(before, inventory(root))


def timing(attempt):
    source = EXP / "Runtime 004" / "experiment.py"
    source_text = source.read_text(encoding="utf-8")
    tree = ast.parse(source_text)
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "TimingMonitor")
    code = ast.get_source_segment(source_text, node)
    namespace = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
    root = RCI / "local-evidence" / ("session10-" + attempt)
    history_path = root / "public-history.jsonl"
    host_path = root / "result.json"
    events = [json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines()]
    starts = [event for event in events if event["type"] == "episode_started"]
    stops = [event for event in events if event["type"] == "episode_stopped"]
    if len(starts) != 1 or len(stops) != 1:
        raise ValueError("Exact retained episode journal boundaries required")
    start, stop = starts[0], stops[0]
    selected = [event for event in events if start["event_id"] <= event["event_id"] <= stop["event_id"]]
    monitor = namespace["TimingMonitor"]()
    for event in selected:
        monitor.observe(event["wall_elapsed_s"] - start["wall_elapsed_s"], event["sim_time_s"] - start["sim_time_s"])
    host = json.loads(host_path.read_text(encoding="utf-8"))
    return {
        "attempt": attempt, "journal": {"path": str(history_path), "sha256": sha(history_path)},
        "host_result": {"path": str(host_path), "sha256": sha(host_path)},
        "timing_monitor": {"path": str(source), "file_sha256": sha(source), "class_source_sha256": hashlib.sha256(code.encode()).hexdigest()},
        "sample_count": len(selected), "episode_started_event_id": start["event_id"], "episode_stopped_event_id": stop["event_id"],
        "sample_types": dict(Counter(event["type"] for event in selected)),
        "original_host_timing": host["timing"],
        "original_host_sim_elapsed_s": host["sim_elapsed_s"], "original_host_wall_elapsed_s": host["wall_elapsed_s"],
        "derived_journal_timing": monitor.report(),
        "scope": "Exact unchanged TimingMonitor applied offline to monotonic protected journal event samples. Origin is episode_started; this precedes host loop clock initialization, and terminal event follows cancellation. This is not original per-tick monitor evidence. Gaps and interpolation are explicit; per-tick maximum lag remains separate.",
        "runtime_timing_qualified": False,
    }


def write_new(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generation", required=True)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    tests = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CensusTests))
    if not tests.wasSuccessful():
        return 1
    if args.self_test:
        return 0
    output = HERE / args.generation
    output.mkdir(exist_ok=False)
    started = now()
    first, first_dirs = inventory(EXP)
    second, second_dirs = inventory(EXP)
    changes = sorted(set(first).symmetric_difference(second) | {name for name in set(first).intersection(second) if first[name] != second[name]})
    dir_changes = sorted(set(first_dirs).symmetric_difference(second_dirs) | {name for name in set(first_dirs).intersection(second_dirs) if first_dirs[name] != second_dirs[name]})
    if changes or dir_changes:
        write_new(output / "invalid-census.json", {"schema": "rci-capacity-census-invalid-1", "started": started, "finished": now(), "changed_files": changes, "changed_directories": dir_changes, "decision": "refuse unstable census; preserve and repeat with a new generation"})
        return 2
    report = totals(second)
    evidence = {name: value for name, value in second.items() if name.startswith("Evidence/")}
    r4 = {name: value for name, value in second.items() if name.startswith("Evidence/releases/batch01-eval-r4/")}
    evidence_unique = totals(evidence)["unique_file_identity_logical_bytes"]
    r4_unique = totals(r4)["unique_file_identity_logical_bytes"]
    inventory_digest = hashlib.sha256()
    for name, value in sorted(second.items()):
        inventory_digest.update(json.dumps([name, *value], separators=(",", ":")).encode() + b"\n")
    free = shutil.disk_usage(EXP).free
    host_reserve = 24 * 512 * 1024 * 1024
    wrapper_reserve = 24 * 256 * 1024 * 1024
    # A reviewable planning reservation; not a hard bound on unqualified model transcript growth.
    proposed_permanent = host_reserve + wrapper_reserve + 1 * GB + 2 * GB
    proposed_peak = (proposed_permanent * 125 + 99) // 100 + 2 * GB
    report.update({
        "schema": "rci-capacity-census-1", "started": started, "finished": now(),
        "root": str(EXP), "source_sha256": sha(__file__), "tests_passed": tests.testsRun,
        "stable_two_pass_metadata": True, "metadata_inventory_sha256": inventory_digest.hexdigest(),
        "metadata_digest_fields": ["relative_path", "st_dev", "st_ino", "st_size", "st_mtime_ns", "st_nlink"],
        "Evidence_unique_file_identity_logical_bytes": evidence_unique,
        "r4_unique_file_identity_logical_bytes": r4_unique,
        "evidence_ceiling_bytes": 150 * GB,
        "Evidence_subtree_alone_excess_bytes": max(0, evidence_unique - 150 * GB),
        "conservative_non_model_excess_bytes": max(0, report["conservative_non_model_unique_file_identity_logical_bytes"] - 150 * GB),
        "live_output_volume_free_bytes": free, "free_reserve_bytes": 100 * GB,
        "proposed_24_attempt_reservation": {
            "host_24_times_512_MiB_bytes": host_reserve,
            "transcript_runtime_backing_24_times_256_MiB_bytes": wrapper_reserve,
            "derived_investigation_bytes": 1 * GB, "admission_development_bytes": 2 * GB,
            "permanent_bytes": proposed_permanent, "uncertainty_percent": 25,
            "temporary_bytes": 2 * GB, "peak_bytes": proposed_peak,
            "free_after_peak_bytes": free - proposed_peak,
            "capacity_after_non_model_evidence_plus_permanent_bytes": report["conservative_non_model_unique_file_identity_logical_bytes"] + proposed_permanent,
            "status": "Planning allowance only; launcher transcript/backing peak must be checked and enforced externally before admission. 512 MiB is host manifest cap, not total run disk cap.",
        },
        "excluded_from_whole_tree": [],
        "scope": "Whole canonical experiment; every ordinary file included. Only the explicitly listed six model paths may be subtracted in the additional conservative non-model metric, and shared identities referenced by any other path are not subtracted. No generic code/source subtree excluded.",
        "physical_accounting_limit": "Distinct device/file IDs remove hardlink pathname duplication. Values remain logical file lengths, not allocated clusters, compression savings or reflink accounting. Metadata two-pass agreement is not a volume snapshot and does not authenticate file contents.",
        "output_reservation_bytes": 1_000_000,
        "output_timing": "This generation directory existed empty during both scans. Reports/receipt written after scans are bounded by output_reservation_bytes and belong in the next census; no directory was excluded.",
        "admitted": False, "runtime_timing_qualified": False, "frozen_release_bound": False,
        "decision": "No existing admission flags or policy changed. Requires explicit policy decision if scientific evidence remains above 150 GB, plus workload-specific timing and frozen campaign binding.",
    })
    timing_report = {"schema": "rci-retained-journal-timing-1", "created_at": now(), "source_sha256": sha(__file__), "attempts": [timing("pilot-001"), timing("smoke-002")]}
    write_new(output / "capacity.json", report)
    write_new(output / "retained-timing.json", timing_report)
    print(json.dumps({"output": str(output), "capacity_sha256": sha(output / "capacity.json"), "timing_sha256": sha(output / "retained-timing.json"), "admitted": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
