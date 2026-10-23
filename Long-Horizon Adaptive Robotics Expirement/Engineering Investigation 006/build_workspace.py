"""Build a standalone, read-only investigation view of the canonical map.

Python standard library only. All behavior records come from the map; this
builder supplies no example runs, metrics, motion traces, or inferred outcomes.
006 repairs only annex-reference identity comparison and presentation source binding;
all upstream evidence processors, selectors, render assets and statistics remain 005.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import quote

import sys

HERE = Path(__file__).resolve().parent
UPSTREAM = HERE.parent / "Engineering Investigation 005"

def _source(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size}

def verify_upstream(bindings_path=None):
    bindings_path = Path(bindings_path or HERE / "upstream-source-bindings.json")
    bindings = json.loads(bindings_path.read_text(encoding="utf-8"))
    if Path(bindings["upstream_directory"]).resolve() != UPSTREAM.resolve():
        raise ValueError("Presentation identifies a different upstream source root")
    files = bindings["files"]
    expected = {Path(item["path"]).resolve() for item in files}
    actual = {path.resolve() for path in UPSTREAM.iterdir() if path.is_file()}
    if expected != actual or len(expected) != len(files):
        raise ValueError("Upstream source inventory differs")
    for item in files:
        if _source(item["path"]) != item:
            raise ValueError("Upstream source bytes differ: " + item["path"])
    return _source(bindings_path)

verify_upstream()
# Import original helpers from their original paths so their producer identities
# remain Investigation005. Only the explicitly loaded reader below is new.
sys.path.insert(0, str(UPSTREAM))
from evidence_adapter import cross_volume, read_run
from analysis_adapter import read_analysis, read_object, read_run_metadata, select_traces
from selected_trace import read_selected_trace
from derivative_adapter import read_derivatives
_reader_spec = importlib.util.spec_from_file_location(
    "investigation006_analysis_provenance", HERE / "analysis_provenance.py")
_reader = importlib.util.module_from_spec(_reader_spec)
_reader_spec.loader.exec_module(_reader)
bind_analysis = _reader.bind_analysis
from implementation_narrative import read_implementation_narrative


DEFAULT_MAP = HERE.parent / "Architecture Map"


def load_map_module():
    spec = importlib.util.spec_from_file_location("canonical_architecture_map", DEFAULT_MAP / "map.py")
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load the canonical map validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_snapshot(map_root: Path, output: Path) -> dict:
    """Read and validate linked records and immutable local attachment hashes."""
    module = load_map_module()
    data, raw, errors = module.read_store(map_root)
    if not errors:
        errors.extend(module.validate_records(data, map_root))
    if errors:
        raise ValueError("Map validation failed:\n" + "\n".join(errors))
    # Revision attachments and relative evidence URIs are map-relative. Never
    # fetch evidence or embed protected external blobs while creating this view.
    relative_map = None if cross_volume(map_root, output) else Path(os.path.relpath(map_root, output.parent)).as_posix()
    return {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "store_sha256": module.store_digest(raw),
        "file_sha256": {name: module.digest(payload) for name, payload in raw.items()},
        "map_base": None if relative_map is None else quote(relative_map, safe="/.") + "/",
        "map_link_state": "unavailable across drives" if relative_map is None else "available",
        "records": data,
    }


def safe_json(value: object) -> str:
    """Prevent closing script tags or HTML parsing from record-controlled text."""
    text = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    for char, escaped in (("&", "\\u0026"), ("<", "\\u003c"), (">", "\\u003e"),
                          ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        text = text.replace(char, escaped)
    return text


def pack_snapshot(snapshot: dict) -> dict:
    """Losslessly wrap the entire safe-JSON snapshot, with reproducible gzip."""
    raw = safe_json(snapshot).encode("utf-8")
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    return {"format": "robot-investigation-snapshot-1.0", "encoding": "gzip-base64",
            "data": base64.b64encode(compressed).decode("ascii"),
            "uncompressed_bytes": len(raw), "compressed_bytes": len(compressed),
            "sha256": hashlib.sha256(raw).hexdigest()}


def render(snapshot: dict, output=None) -> str:
    template = (UPSTREAM / "workspace.html").read_text(encoding="utf-8")
    if template.count("__MAP_SNAPSHOT__") != 1:
        raise ValueError("Workspace template needs exactly one snapshot marker")
    template = template.replace("/*__PLAYBACK_STYLE__*/", (UPSTREAM / "playback.css").read_text(encoding="utf-8"))
    template = template.replace("/*__PLAYBACK_CODE__*/", (UPSTREAM / "playback.js").read_text(encoding="utf-8"))
    template = template.replace("/*__ANALYSIS_STYLE__*/", (UPSTREAM / "analysis.css").read_text(encoding="utf-8"))
    template = template.replace("/*__ANALYSIS_CODE__*/", (UPSTREAM / "analysis.js").read_text(encoding="utf-8"))
    # Static navigation is source-root-relative in 005; fresh generated pages
    # can be nested. Resolve only these three declared links for this output.
    if output is not None:
        for relative in ("README.md", "Architecture Map/README.md",
                         "Long-Horizon Adaptive Robotics Experiment Design/Contract.md"):
            original = "../" + quote(relative, safe="/.")
            target = quote(Path(os.path.relpath(HERE.parent / relative,
                                                Path(output).parent)).as_posix(), safe="/.")
            template = template.replace('href="' + original + '"', 'href="' + target + '"')
    template = template.replace(
        "file_sha256:snapshot.file_sha256},null,2)",
        "file_sha256:snapshot.file_sha256,presentation_implementation:snapshot.presentation_implementation},null,2)")
    return template.replace("__MAP_SNAPSHOT__", safe_json(pack_snapshot(snapshot)))


def read_display_run(path, output, observation_hz, motion_hz):
    if not cross_volume(path, output): return read_run(path, output, observation_hz, motion_hz)
    manifest_path = Path(path) / "manifest.json"
    manifest = read_object(manifest_path) if manifest_path.is_file() else {}
    run_id = manifest.get("run_id", Path(path).name)
    if not isinstance(run_id, str) or not run_id: raise ValueError("Missing cross-drive run identity")
    return read_selected_trace({"run_id": run_id, "path": str(path), "reason": "Explicit command-line run selection"},
                              path, output, observation_hz, motion_hz)


def build(map_root: Path, output: Path, run_dirs=(), observation_hz=2.0, motion_hz=5.0,
          *, analysis_file=None, metadata_root=None, trace_selection=None,
          evaluation_index=None, evaluation_receipt=None, analysis_provenance=None, analysis_receipt=None,
          implementation_narrative=None) -> dict:
    map_root, output = map_root.resolve(), output.resolve()
    snapshot = load_snapshot(map_root, output)
    upstream_binding = verify_upstream()
    presentation_sources = [_source(Path(__file__)), _source(HERE / "analysis_provenance.py"),
                            upstream_binding]
    snapshot["presentation_implementation"] = {
        "version": "Engineering Investigation 006",
        "scope": "Annex reference identity compatibility and presentation only; original 005 diagnostics and Analysis005 numerical estimates are unchanged.",
        "sources": presentation_sources,
        "upstream": str(UPSTREAM),
        "producer_version": "Engineering Investigation 005",
        "analysis_version": "Release Analysis 005"}

    snapshot["implementation_narrative"] = read_implementation_narrative(
        implementation_narrative, snapshot["records"], map_root)
    directories, selection = select_traces(trace_selection, run_dirs)
    snapshot["paired_analysis"] = read_analysis(analysis_file, output)
    snapshot["run_metadata"] = read_run_metadata(metadata_root, output)
    snapshot["evaluation_derivatives"] = read_derivatives(evaluation_index, evaluation_receipt, output,
        canonical_files=snapshot["file_sha256"], paired_analysis=snapshot["paired_analysis"])
    snapshot["paired_analysis"] = bind_analysis(snapshot["paired_analysis"], analysis_provenance, analysis_receipt,
        output, derivatives=snapshot["evaluation_derivatives"])
    snapshot["trace_selection"] = selection
    selected_rows = {row["run_id"]: row for row in snapshot["evaluation_derivatives"].get("runs", [])}
    snapshot["evidence_runs"] = ([read_selected_trace(entry, path, output, observation_hz, motion_hz,
                                 selected_result=selected_rows.get(entry["run_id"], {}).get("selected_result"),
                                 selection_provenance=selected_rows.get(entry["run_id"], {}).get("selection_provenance"))
                                 for entry, path in zip(selection["runs"], directories)]
                                if trace_selection is not None else
                                [read_display_run(path, output, observation_hz, motion_hz) for path in directories])
    ids = [run["run_id"] for run in snapshot["evidence_runs"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate evidence run identity")
    if trace_selection is not None and ids != [entry["run_id"] for entry in selection["runs"]]:
        raise ValueError("Selected trace identity differs from its declaration")
    html = render(snapshot, output)
    if (verify_upstream() != upstream_binding
            or [_source(Path(item["path"])) for item in presentation_sources] != presentation_sources):
        raise ValueError("Presentation implementation changed during build")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=output.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(html)
        temporary.replace(output)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return {"output": str(output), "store_sha256": snapshot["store_sha256"],
            "presentation_implementation": snapshot["presentation_implementation"],
            "counts": {kind: len(records) for kind, records in snapshot["records"].items()},
            "evidence_runs": ids,
            "unavailable_evidence_runs": [run["run_id"] for run in snapshot["evidence_runs"]
                                          if run.get("trace_availability", {}).get("state") == "unavailable"],
            "metadata_runs": len(snapshot["run_metadata"]["runs"]),
            "evaluation_derivative_runs": len(snapshot["evaluation_derivatives"]["runs"]),
            "paired_analysis": snapshot["paired_analysis"]["state"],
            "implementation_narrative_revisions": list(snapshot["implementation_narrative"]["revisions"])}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map-root", type=Path, default=DEFAULT_MAP)
    parser.add_argument("--output", type=Path, default=HERE / "index.html")
    parser.add_argument("--run-dir", type=Path, action="append", default=[], help="Actual completed run directory; repeat for multiple runs")
    parser.add_argument("--observation-hz", type=float, default=2.0)
    parser.add_argument("--motion-hz", type=float, default=5.0)
    parser.add_argument("--analysis-file", type=Path, help="Actual protocol.py paired-analysis JSON; absent means unavailable")
    parser.add_argument("--metadata-root", type=Path, help="Read only manifest/result metadata from all immediate run directories")
    parser.add_argument("--trace-selection", type=Path, help="Predeclared bounded detailed-trace selection JSON; maximum 12 bundles")
    parser.add_argument("--evaluation-index", type=Path, help="Finalized process_evaluation index for every planned run")
    parser.add_argument("--evaluation-receipt", type=Path, help="Retained official completion receipt for that index")
    parser.add_argument("--analysis-provenance", type=Path, help="Source-bound analysis wrapper provenance sidecar")
    parser.add_argument("--analysis-receipt", type=Path, help="Retained official completion receipt for the analysis wrapper")
    parser.add_argument("--implementation-narrative", type=Path,
                        help="Optional mechanism prose, shown only for exact source-matched immutable revisions")
    args = parser.parse_args()
    try:
        result = build(args.map_root, args.output, args.run_dir, args.observation_hz, args.motion_hz,
                       analysis_file=args.analysis_file, metadata_root=args.metadata_root, trace_selection=args.trace_selection,
                       evaluation_index=args.evaluation_index, evaluation_receipt=args.evaluation_receipt,
                       analysis_provenance=args.analysis_provenance, analysis_receipt=args.analysis_receipt,
                       implementation_narrative=args.implementation_narrative)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
