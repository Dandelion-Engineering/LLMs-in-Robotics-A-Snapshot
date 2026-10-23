"""Lossless, bounded presentation artifacts for unchanged normalized traces.

This module does not read raw evidence, choose traces, change sampling, or infer
outcomes. Every codec node is explicitly tagged, including ordinary objects.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re


VALUE_FORMAT = "robot-trace-value-1.0"
MANIFEST_FORMAT = "robot-trace-manifest-2.0"
SUMMARY_FORMAT = "robot-trace-metadata-summary-1.0"
MAX_JSON_BYTES = 1024 * 1024
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_DESCRIPTOR_BYTES = 256 * 1024
MAX_STRING_BYTES = 16 * 1024
MAX_UTF8_BYTES = 64 * 1024
INLINE_NODE_BYTES = 16 * 1024
MAX_SUMMARY_SCALAR_BYTES = 1024
MAX_SUMMARY_SOURCE_FILES = 8
_REF = re.compile(r"data/([0-9a-f]{64})\.(json|utf8)\Z")
_CONCAT = {"a": "A", "o": "O", "s": "S", "A": "A", "O": "O", "S": "S"}


def _json(value):
    # ASCII JSON also preserves a source string containing escaped lone
    # surrogates. Valid Unicode strings use ordinary UTF-8 chunk artifacts.
    return json.dumps(value, ensure_ascii=True, allow_nan=False,
                      separators=(",", ":")).encode("ascii")


def _strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON object key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("Nonfinite JSON constant: " + value)

    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                      parse_constant=constant)


class _Store:
    def __init__(self, output_dir):
        self.root = Path(output_dir).resolve()
        self.data = self.root / "data"
        if self.data.is_symlink():
            raise ValueError("Package data directory must not be a symlink")
        self.data.mkdir(parents=True, exist_ok=True)
        self.refs = {}

    def write(self, raw, suffix, limit):
        if not isinstance(raw, bytes) or not raw or len(raw) > limit:
            raise ValueError("Package artifact exceeds its byte limit or is empty")
        sha = hashlib.sha256(raw).hexdigest()
        ref = {"href": "data/" + sha + "." + suffix,
               "sha256": sha, "bytes": len(raw)}
        path = self.root / ref["href"]
        if path.is_symlink():
            raise ValueError("Package artifact must not be a symlink")
        try:
            with path.open("xb") as stream:
                stream.write(raw)
        except FileExistsError:
            if not path.is_file() or path.stat().st_size != len(raw):
                raise ValueError("Existing content-addressed artifact differs")
            with path.open("rb") as stream:
                if stream.read(limit + 1) != raw:
                    raise ValueError("Existing content-addressed artifact differs")
        self.refs[ref["href"]] = ref
        return ref

    def node(self, node):
        return self.write(_json({"format": VALUE_FORMAT, "node": node}),
                          "json", MAX_JSON_BYTES)

    def seal(self, node):
        if len(_json({"format": VALUE_FORMAT, "node": node})) <= INLINE_NODE_BYTES:
            return node
        return ["r", self.node(node)]

    def sequence(self, tag, items):
        """Bound both leaf containers and recursively concatenated fragments."""
        fragments, current = [], []
        used = len(_json({"format": VALUE_FORMAT, "node": [tag, []]}))
        base = used
        for item in items:
            size = len(_json(item)) + (1 if current else 0)
            if base + size > MAX_JSON_BYTES:
                raise ValueError("A codec child exceeds the JSON artifact limit")
            if current and used + size > MAX_JSON_BYTES:
                fragments.append(["r", self.node([tag, current])])
                current, used = [], base
                size = len(_json(item))
            current.append(item)
            used += size
        if not fragments:
            return self.seal([tag, current])
        if current:
            fragments.append(["r", self.node([tag, current])])
        return self.sequence(_CONCAT[tag], fragments)

    def string(self, value):
        if len(value) <= MAX_STRING_BYTES:
            try:
                raw = value.encode("utf-8")
            except UnicodeEncodeError:
                raw = None
            if raw is not None and len(raw) <= MAX_STRING_BYTES:
                return self.seal(["v", value])
            if raw is None and len(_json(["v", value])) <= INLINE_NODE_BYTES:
                return ["v", value]

        def parts():
            # At most 16,384 codepoints means at most 65,536 UTF-8 bytes;
            # Python slicing never splits a valid Unicode codepoint.
            for start in range(0, len(value), MAX_UTF8_BYTES // 4):
                part = value[start:start + MAX_UTF8_BYTES // 4]
                try:
                    raw = part.encode("utf-8")
                except UnicodeEncodeError:
                    # JSON-escaped fragments preserve even lone surrogates.
                    for offset in range(0, len(part), MAX_STRING_BYTES // 6):
                        yield self.seal(["v", part[offset:offset + MAX_STRING_BYTES // 6]])
                else:
                    yield ["s", [self.write(raw, "utf8", MAX_UTF8_BYTES)]]

        return self.sequence("S", parts())

    def encode(self, value):
        if isinstance(value, str):
            return self.string(value)
        if value is None or type(value) in (bool, int):
            return self.seal(["v", value])
        if type(value) is float:
            if not math.isfinite(value):
                raise ValueError("Nonfinite value cannot be packaged")
            return self.seal(["v", value])
        if isinstance(value, list):
            return self.sequence("a", (self.encode(item) for item in value))
        if isinstance(value, dict):
            if any(not isinstance(key, str) for key in value):
                raise ValueError("JSON object keys must be strings")
            return self.sequence("o", ([self.string(key), self.encode(item)]
                                       for key, item in value.items()))
        raise ValueError("Unsupported non-JSON value: " + type(value).__name__)


def write_value(value, output_dir):
    """Write one lossless value, returning its authenticated root reference."""
    store = _Store(output_dir)
    return store.node(store.encode(value))


def _read_ref(ref, output_dir, suffix, limit):
    if not isinstance(ref, dict) or set(ref) != {"href", "sha256", "bytes"}:
        raise ValueError("Invalid package artifact reference")
    match = _REF.fullmatch(ref.get("href", "")) if isinstance(ref.get("href"), str) else None
    if (not match or match[1] != ref.get("sha256") or match[2] != suffix
            or type(ref.get("bytes")) is not int or not 0 < ref["bytes"] <= limit):
        raise ValueError("Invalid package artifact path, digest or size")
    root = Path(output_dir).resolve()
    path = root / ref["href"]
    if (path.parent.is_symlink() or path.is_symlink()
            or not path.resolve().is_relative_to(root / "data")):
        raise ValueError("Package artifact escapes its data directory")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) != ref["bytes"] or hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise ValueError("Package artifact byte count or SHA-256 differs")
    return raw


def read_value(ref, output_dir):
    """Authenticate and reconstruct a value; never follows source-file links."""
    active = set()

    def reference(item):
        raw = _read_ref(item, output_dir, "json", MAX_JSON_BYTES)
        identity = item["href"]
        if identity in active:
            raise ValueError("Cyclic package value reference")
        active.add(identity)
        try:
            document = _strict_json(raw)
            if (not isinstance(document, dict) or set(document) != {"format", "node"}
                    or document["format"] != VALUE_FORMAT):
                raise ValueError("Unsupported package value document")
            return decode(document["node"])
        finally:
            active.remove(identity)

    def decode(node):
        if not isinstance(node, list) or len(node) != 2 or not isinstance(node[0], str):
            raise ValueError("Invalid tagged codec node")
        tag, value = node
        if tag == "r":
            return reference(value)
        if tag == "v":
            if isinstance(value, (dict, list)) or (type(value) is float and not math.isfinite(value)):
                raise ValueError("Scalar codec node contains a non-scalar")
            if value is not None and type(value) not in (bool, int, float, str):
                raise ValueError("Unsupported scalar codec value")
            return value
        if not isinstance(value, list):
            raise ValueError("Container codec node requires a list")
        if tag == "a":
            return [decode(item) for item in value]
        if tag == "o":
            result = {}
            for pair in value:
                if not isinstance(pair, list) or len(pair) != 2:
                    raise ValueError("Invalid object codec member")
                key = decode(pair[0])
                if not isinstance(key, str) or key in result:
                    raise ValueError("Non-string or duplicate object codec key")
                result[key] = decode(pair[1])
            return result
        if tag == "s":
            return "".join(_read_ref(item, output_dir, "utf8", MAX_UTF8_BYTES).decode("utf-8")
                           for item in value)
        if tag in ("A", "O", "S"):
            result = {} if tag == "O" else []
            for item in value:
                part = decode(item)
                if tag == "A":
                    if not isinstance(part, list):
                        raise ValueError("Array fragment has the wrong type")
                    result.extend(part)
                elif tag == "O":
                    if not isinstance(part, dict) or set(result).intersection(part):
                        raise ValueError("Object fragment has duplicate keys or wrong type")
                    result.update(part)
                else:
                    if not isinstance(part, str):
                        raise ValueError("String fragment has the wrong type")
                    result.append(part)
            return "".join(result) if tag == "S" else result
        raise ValueError("Unknown codec tag: " + tag)

    return reference(ref)


def event_cues(event):
    payload = event.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    packet = None
    for candidate in (payload.get("packet"),
                      payload.get("message", {}).get("packet") if isinstance(payload.get("message"), dict) else None,
                      payload.get("request", {}).get("packet") if isinstance(payload.get("request"), dict) else None):
        if isinstance(candidate, dict):
            packet = candidate
            break
    nested = payload.get("events")
    nested = nested if event.get("event_type") == "candidate_reply" and isinstance(nested, list) else []
    cues = {"request_id": payload.get("request_id"), "has_packet": packet is not None,
            "packet_sequence": packet.get("sequence") if packet is not None else None,
            "candidate_events": [{"index": index, "type": item.get("type"), "path": item.get("path")}
                                 for index, item in enumerate(nested) if isinstance(item, dict)]}
    for flag in ("stale", "after_episode_end"):
        if flag in payload:
            cues[flag] = payload[flag]
    return cues


def metadata_summary(metadata):
    """Project bounded display fields; exact metadata lives in the value codec.

    Strings are never shortened and arrays are never sliced. A field that cannot
    be displayed within these bounds is deferred to the authenticated metadata
    inspector, as is every field outside the explicit display whitelist.
    """
    deferred = []

    def pointer(path, key):
        return path + "/" + str(key).replace("~", "~0").replace("/", "~1")

    def scalar(value):
        if isinstance(value, str) and len(value) > MAX_SUMMARY_SCALAR_BYTES:
            return False
        return (value is None or type(value) in (bool, int, float, str)) and len(_json(value)) <= MAX_SUMMARY_SCALAR_BYTES

    def fields(value, allowed, path):
        if value is None:
            return None
        if not isinstance(value, dict):
            deferred.append(path)
            return {}
        result = {}
        # Only whitelist paths enter the projection; unfamiliar source keys can
        # themselves be enormous, so record their parent rather than copying
        # unknown keys into the bounded deferred-path index.
        if any(key not in allowed for key in value):
            deferred.append(path + "/*")
        for key in allowed:
            if key not in value:
                continue
            if scalar(value[key]):
                result[key] = value[key]
            else:
                deferred.append(pointer(path, key))
        return result

    display = {
        "manifest": ("run_id", "stage", "architecture", "condition", "scenario"),
        "result": ("run_id", "execution_status", "outcome", "validity", "validity_reason",
                   "completion_time_s", "wall_duration_s", "actual_host_timing_pass",
                   "outside_rtf_tolerance_windows", "complete_wall_windows",
                   "false_done_assertions", "model_calls"),
        "sampling": ("event_records", "retained_events", "observation_target_hz", "observation_rule",
                     "motion_records", "retained_motion", "motion_target_hz", "motion_rule",
                     "episode_clock_started_event_id", "clock_rule", "source_motion_rate_claim_hz"),
        "trace_availability": ("state", "reason_code", "reason", "source_scope", "interpretation"),
        "selection_entry": ("run_id", "path", "reason"),
        "administrative_projection": ("schema_version", "run_id", "execution_status", "outcome",
                                      "validity", "validity_reason", "physical_end", "task_outcome",
                                      "post_run_integrity", "wall_duration_s", "completion_time_s")}
    result = {"run_id": metadata["run_id"]}
    if not scalar(result["run_id"]):
        raise ValueError("Trace run identity exceeds the bounded summary scalar limit")
    for key, allowed in display.items():
        if key in metadata:
            result[key] = fields(metadata[key], allowed, "/" + key)
    raw_result = metadata.get("result")
    if isinstance(raw_result, dict) and "independent_outcome" in raw_result:
        result["result"]["independent_outcome"] = fields(
            raw_result["independent_outcome"], ("accepted_count",), "/result/independent_outcome")
    sampling = metadata.get("sampling")
    if isinstance(sampling, dict):
        for original_key, summary_key in (("event_gaps", "event_gap_count"),
                                          ("motion_intervals_over_30ms", "motion_intervals_over_30ms_count")):
            if isinstance(sampling.get(original_key), list):
                result["sampling"][summary_key] = len(sampling[original_key])
                deferred.append("/sampling/" + original_key)
    if "source_files" in metadata:
        sources = metadata["source_files"]
        if isinstance(sources, list) and len(sources) <= MAX_SUMMARY_SOURCE_FILES:
            result["source_files"] = [fields(item, ("name", "href", "sha256", "bytes", "path", "link_state", "reason"),
                                              "/source_files/" + str(index)) for index, item in enumerate(sources)]
        else:
            deferred.append("/source_files")
        if isinstance(sources, list):
            result["source_file_count"] = len(sources)
    if any(key not in set(display) | {"run_id", "source_files"} for key in metadata):
        deferred.append("/*")
    result["metadata_projection"] = {
        "format": SUMMARY_FORMAT,
        "scope": "Bounded display fields only; exact full metadata is retained in package.metadata_ref.",
        "full_metadata_included": False,
        "deferred_fields": sorted(set(deferred))}
    if len(_json(result)) > MAX_DESCRIPTOR_BYTES - 2048:
        raise ValueError("Trace summary exceeds the descriptor byte limit")
    return result


def write_trace(run, output_dir, ordinal):
    """Package exactly one normalized run; return a compact ordered descriptor."""
    if not isinstance(run, dict) or not isinstance(run.get("run_id"), str) or not run["run_id"]:
        raise ValueError("Trace requires a nonempty run identity")
    if type(ordinal) is not int or ordinal < 0:
        raise ValueError("Trace ordinal must be a nonnegative integer")
    if "package" in run:
        raise ValueError("Trace metadata collides with the package descriptor key")
    events, motion = run.get("events"), run.get("motion")
    if not isinstance(events, list) or not isinstance(motion, list):
        raise ValueError("Normalized trace requires event and motion lists")
    metadata = {key: value for key, value in run.items() if key not in ("events", "motion")}
    summary = metadata_summary(metadata)
    store = _Store(output_dir)
    metadata_ref = store.node(store.encode(metadata))
    motion_ref = store.node(store.encode(motion))
    headers = []
    for event in events:
        if not isinstance(event, dict) or "payload" not in event:
            raise ValueError("Trace event requires its original payload")
        if set(event).intersection(("payload_ref", "cues")):
            raise ValueError("Event envelope collides with presentation keys")
        header = {key: value for key, value in event.items() if key != "payload"}
        header["payload_ref"] = store.node(store.encode(event["payload"]))
        header["cues"] = event_cues(event)
        headers.append(header)
    json_refs = [ref for ref in store.refs.values() if ref["href"].endswith(".json")]
    utf8_refs = [ref for ref in store.refs.values() if ref["href"].endswith(".utf8")]
    stats = {"event_count": len(events), "motion_count": len(motion),
             "value_artifact_count": len(json_refs),
             "value_artifact_bytes": sum(ref["bytes"] for ref in json_refs),
             "utf8_artifact_count": len(utf8_refs),
             "utf8_artifact_bytes": sum(ref["bytes"] for ref in utf8_refs),
             "max_value_artifact_bytes": max((ref["bytes"] for ref in json_refs), default=0),
             "max_utf8_artifact_bytes": max((ref["bytes"] for ref in utf8_refs), default=0),
             "original_payload_sha256_count": sum("payload_sha256" in event for event in events)}
    manifest = {"format": MANIFEST_FORMAT, "ordinal": ordinal, "run_id": run["run_id"],
                "metadata": summary, "metadata_ref": metadata_ref,
                "motion_ref": motion_ref, "event_headers": headers, "stats": stats}
    manifest_ref = store.write(_json(manifest), "json", MAX_MANIFEST_BYTES)
    package_stats = {**stats, "manifest_bytes": manifest_ref["bytes"],
                     "artifact_count": len(store.refs),
                     "artifact_bytes": sum(ref["bytes"] for ref in store.refs.values())}
    descriptor = {**summary, "package": {"manifest": manifest_ref, "metadata_ref": metadata_ref, "stats": package_stats}}
    if len(_json(descriptor)) > MAX_DESCRIPTOR_BYTES:
        raise ValueError("Trace descriptor exceeds its byte limit")
    return descriptor


def read_manifest(descriptor, output_dir):
    ref = descriptor.get("package", {}).get("manifest")
    manifest = _strict_json(_read_ref(ref, output_dir, "json", MAX_MANIFEST_BYTES))
    if (not isinstance(manifest, dict) or manifest.get("format") != MANIFEST_FORMAT
            or manifest.get("run_id") != descriptor.get("run_id")
            or manifest.get("metadata") != {key: value for key, value in descriptor.items() if key != "package"}
            or manifest.get("metadata_ref") != descriptor.get("package", {}).get("metadata_ref")
            or manifest.get("metadata", {}).get("metadata_projection", {}).get("format") != SUMMARY_FORMAT
            or manifest.get("metadata", {}).get("metadata_projection", {}).get("full_metadata_included") is not False
            or not isinstance(manifest.get("event_headers"), list)
            or type(manifest.get("ordinal")) is not int or manifest["ordinal"] < 0):
        raise ValueError("Trace manifest identity or metadata differs from its descriptor")
    return manifest


def verify_trace(run, descriptor, output_dir):
    """Round-trip one payload at a time, without a canonical whole-trace string."""
    metadata = {key: value for key, value in run.items() if key not in ("events", "motion")}
    if metadata_summary(metadata) != {key: value for key, value in descriptor.items() if key != "package"}:
        raise ValueError("Round-trip trace metadata summary differs")
    manifest = read_manifest(descriptor, output_dir)
    if read_value(manifest["metadata_ref"], output_dir) != metadata:
        raise ValueError("Round-trip full trace metadata differs")
    if read_value(manifest["motion_ref"], output_dir) != run["motion"]:
        raise ValueError("Round-trip motion differs")
    headers = manifest["event_headers"]
    if len(headers) != len(run["events"]):
        raise ValueError("Round-trip event count differs")
    for original, header in zip(run["events"], headers):
        original_header = {key: value for key, value in original.items() if key != "payload"}
        restored_header = {key: value for key, value in header.items() if key not in ("payload_ref", "cues")}
        if restored_header != original_header or header["cues"] != event_cues(original):
            raise ValueError("Round-trip event envelope or cues differ")
        if read_value(header["payload_ref"], output_dir) != original["payload"]:
            raise ValueError("Round-trip event payload differs")
    if (manifest["stats"]["event_count"] != len(run["events"])
            or manifest["stats"]["motion_count"] != len(run["motion"])):
        raise ValueError("Round-trip counts differ")
    return {"state": "verified", "run_id": run["run_id"],
            "events": len(run["events"]), "motion": len(run["motion"]),
            "full_metadata_roundtrip_equal": True,
            "metadata_sha256": manifest["metadata_ref"]["sha256"],
            "manifest_sha256": descriptor["package"]["manifest"]["sha256"]}
