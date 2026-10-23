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
MANIFEST_FORMAT = "robot-trace-manifest-1.0"
MAX_JSON_BYTES = 1024 * 1024
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_DESCRIPTOR_BYTES = 256 * 1024
MAX_STRING_BYTES = 16 * 1024
MAX_UTF8_BYTES = 64 * 1024
INLINE_NODE_BYTES = 16 * 1024
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
    if len(_json(metadata)) > MAX_DESCRIPTOR_BYTES - 2048:
        raise ValueError("Trace metadata exceeds the descriptor byte limit")
    store = _Store(output_dir)
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
                "metadata": metadata, "motion_ref": motion_ref, "event_headers": headers, "stats": stats}
    manifest_ref = store.write(_json(manifest), "json", MAX_MANIFEST_BYTES)
    package_stats = {**stats, "manifest_bytes": manifest_ref["bytes"],
                     "artifact_count": len(store.refs),
                     "artifact_bytes": sum(ref["bytes"] for ref in store.refs.values())}
    descriptor = {**metadata, "package": {"manifest": manifest_ref, "stats": package_stats}}
    if len(_json(descriptor)) > MAX_DESCRIPTOR_BYTES:
        raise ValueError("Trace descriptor exceeds its byte limit")
    return descriptor


def read_manifest(descriptor, output_dir):
    ref = descriptor.get("package", {}).get("manifest")
    manifest = _strict_json(_read_ref(ref, output_dir, "json", MAX_MANIFEST_BYTES))
    if (not isinstance(manifest, dict) or manifest.get("format") != MANIFEST_FORMAT
            or manifest.get("run_id") != descriptor.get("run_id")
            or manifest.get("metadata") != {key: value for key, value in descriptor.items() if key != "package"}
            or not isinstance(manifest.get("event_headers"), list)
            or type(manifest.get("ordinal")) is not int or manifest["ordinal"] < 0):
        raise ValueError("Trace manifest identity or metadata differs from its descriptor")
    return manifest


def verify_trace(run, descriptor, output_dir):
    """Round-trip one payload at a time, without a canonical whole-trace string."""
    metadata = {key: value for key, value in run.items() if key not in ("events", "motion")}
    if metadata != {key: value for key, value in descriptor.items() if key != "package"}:
        raise ValueError("Round-trip trace metadata differs")
    manifest = read_manifest(descriptor, output_dir)
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
            "manifest_sha256": descriptor["package"]["manifest"]["sha256"]}
