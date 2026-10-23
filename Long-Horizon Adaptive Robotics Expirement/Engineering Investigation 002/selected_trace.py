"""Keep every declared inspection slot without inventing missing evidence.

Only absent files, an empty event log, or an explicitly incomplete final stream
record become unavailable. Identity/schema/hash errors still refuse the build.
This adapter never searches for a replacement run or changes eligibility.
"""
from pathlib import Path

from analysis_adapter import read_object, source_ref
from evidence_adapter import IncompleteEvidence, cross_volume, digest_file, read_run


NAMES = ("manifest.json", "events.jsonl", "motion.jsonl", "result.json")


def files_at(root):
    files = {}
    for name in NAMES:
        path = root / name
        if path.exists() and not path.is_file():
            raise ValueError("Selected evidence source is not a regular file: " + name)
        if path.is_file():
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError("Selected evidence source escapes its directory: " + name)
            files[name] = path
    return files


def unavailable(entry, root, output, code, reason, *, metadata_only=False):
    """Retain only verified-identity metadata; do not expose a partial playback."""
    all_paths = files_at(root)
    paths = {name: path for name, path in all_paths.items() if not metadata_only or name in ("manifest.json", "result.json")}
    before = {name: digest_file(path) for name, path in paths.items()}
    if code == "missing_required_files" and all(name in paths for name in ("manifest.json", "events.jsonl")):
        raise ValueError("Selected evidence appeared while recording unavailability")
    if code == "empty_event_stream" and paths.get("events.jsonl") and paths["events.jsonl"].stat().st_size:
        raise ValueError("Selected event stream changed while recording unavailability")
    metadata = {}
    for name in ("manifest.json", "result.json"):
        record = read_object(paths[name]) if name in paths else None
        if record is not None and record.get("run_id") != entry["run_id"]:
            raise ValueError("Selected trace identity differs from its declaration: " + name)
        metadata[name] = record
    refs = [source_ref(path, output) for path in paths.values()]
    after_paths = {name: path for name, path in files_at(root).items() if not metadata_only or name in ("manifest.json", "result.json")}
    after = {name: digest_file(path) for name, path in after_paths.items()}
    if before != after or any(ref["sha256"] != before[ref["name"]] for ref in refs):
        raise ValueError("Selected evidence changed while recording unavailability")
    return {"run_id": entry["run_id"], "manifest": metadata["manifest.json"],
            "result": metadata["result.json"], "events": [], "motion": [],
            "sampling": None, "source_files": refs, "selection_entry": dict(entry),
            "trace_availability": {
                "state": "unavailable", "reason_code": code, "reason": reason,
                "missing_required_files": [name for name in ("manifest.json", "events.jsonl") if name not in all_paths],
                "source_scope": "Manifest/result metadata only; raw streams not read" if metadata_only else "Available source files hashed",
                "interpretation": "Declared inspection slot retained without replacement. No playback samples or task outcome are inferred. Existing source hashes identify bytes, not a validated complete event stream."}}


def read_selected_trace(entry, directory, output, observation_hz=2.0, motion_hz=5.0):
    directory = Path(directory)
    if directory.is_symlink():
        raise ValueError("Selected trace directory must not be a symbolic link")
    root = directory.resolve()
    if root.exists() and not root.is_dir():
        raise ValueError("Selected trace path is not a directory")
    paths = files_at(root)
    if cross_volume(root, Path(output).resolve()):
        return unavailable(entry, root, output, "cross_volume_playback_unavailable",
                           "This run is on another drive. Compact metadata is retained; playback and local browser links are unavailable.",
                           metadata_only=True)
    missing = [name for name in ("manifest.json", "events.jsonl") if name not in paths]
    if missing:
        return unavailable(entry, root, output, "missing_required_files",
                           "Required trace files absent at build time: " + ", ".join(missing))
    # Verify identities before classifying a truncated stream. A wrong bundle
    # cannot be disguised as a missing trace simply by truncating its last line.
    for name in ("manifest.json", "result.json"):
        if name in paths and read_object(paths[name]).get("run_id") != entry["run_id"]:
            raise ValueError("Selected trace identity differs from its declaration: " + name)
    before = {name: digest_file(path) for name, path in paths.items()}
    try:
        run = read_run(root, output, observation_hz, motion_hz)
    except IncompleteEvidence as exc:
        run = unavailable(entry, root, output, "incomplete_stream", str(exc))
    after = {name: digest_file(path) for name, path in files_at(root).items()}
    if before != after:
        raise ValueError("Selected evidence changed during the build")
    if run["run_id"] != entry["run_id"]:
        raise ValueError("Selected trace identity differs from its declaration")
    if run.get("trace_availability", {}).get("state") == "unavailable":
        return run
    if not run["events"]:
        return unavailable(entry, root, output, "empty_event_stream",
                           "The declared event log contains no recorded events.")
    return {**run, "selection_entry": dict(entry), "trace_availability": {"state": "available"}}
