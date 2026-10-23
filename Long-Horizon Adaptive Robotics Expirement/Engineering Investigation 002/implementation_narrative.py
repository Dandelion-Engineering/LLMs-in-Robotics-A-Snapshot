"""Bind optional mechanism prose to immutable revision ZIP members, never live code."""
from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


SCHEMA = "robot-implementation-narrative-1.0"
FIELDS = {"mechanism", "llm_role", "control_loop", "continuity"}
SOURCE_MEMBERS = {"candidates.py", "cell.py", "experiment.py", "model_runtime.py",
                  "model_setup.py", "sandbox.py", "candidate_worker.py",
                  "sensor_worker.py", "actuation.py"}
ARCHITECTURES = {"B01-C0", "B01-A1", "B01-A2", "B01-A3"}
SHA = re.compile(r"[0-9a-f]{64}\Z")


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate narrative JSON key: " + key)
        result[key] = value
    return result


def _read_document(payload):
    def reject(value):
        raise ValueError("Nonfinite narrative JSON: " + value)
    value = json.loads(payload, object_pairs_hook=_object, parse_constant=reject)
    if not isinstance(value, dict) or set(value) != {
            "schema_version", "recorded_at", "scope", "source_refs", "shared", "candidates"}:
        raise ValueError("Unsupported implementation narrative fields")
    if value["schema_version"] != SCHEMA:
        raise ValueError("Unsupported implementation narrative schema")
    for key in ("recorded_at", "scope", "shared"):
        if not isinstance(value[key], str) or not value[key].strip():
            raise ValueError("Missing implementation narrative " + key)
    candidates = value["candidates"]
    if not isinstance(candidates, dict) or set(candidates) != ARCHITECTURES:
        raise ValueError("Narrative must identify the three candidates and conventional baseline")
    for candidate in candidates.values():
        if not isinstance(candidate, dict) or set(candidate) != FIELDS or any(
                not isinstance(text, str) or not text.strip() for text in candidate.values()):
            raise ValueError("Missing candidate mechanism narrative")
    refs = value["source_refs"]
    if not isinstance(refs, list) or len(refs) != len(SOURCE_MEMBERS):
        raise ValueError("Narrative needs its complete Runtime source inventory")
    seen = set()
    for ref in refs:
        if not isinstance(ref, dict) or set(ref) != {"member", "source", "sha256", "lines"}:
            raise ValueError("Unsupported narrative source reference")
        member = ref["member"]
        if not isinstance(member, str) or member not in SOURCE_MEMBERS or member in seen:
            raise ValueError("Missing or duplicate narrative source member")
        if ref["source"] != "Runtime/" + member or not isinstance(ref["sha256"], str) or not SHA.fullmatch(ref["sha256"]):
            raise ValueError("Invalid narrative source identity")
        if not isinstance(ref["lines"], str) or not ref["lines"].strip():
            raise ValueError("Missing narrative source line locator")
        seen.add(member)
    return value


def _archive_identity(ref, map_root, expected):
    """Read only the exact retained attachment; no extraction or code imports."""
    uri = ref.get("uri")
    if not isinstance(uri, str) or Path(uri).suffix.lower() != ".zip":
        return None
    if ref.get("state") != "available" or not isinstance(ref.get("sha256"), str) or not SHA.fullmatch(ref["sha256"]):
        raise ValueError("Source archive is not an immutable available attachment")
    path = (map_root / uri).resolve()
    if not path.is_relative_to(map_root):
        raise ValueError("Narrative source attachment escaped the canonical map")
    payload = path.read_bytes()
    if digest(payload) != ref["sha256"]:
        raise ValueError("Narrative source archive hash differs from its revision")
    members, mismatched = [], []
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            infos = archive.infolist()
            for name, sha in sorted(expected.items()):
                matches = [info for info in infos if info.filename.casefold() == name.casefold()]
                if len(matches) > 1:
                    raise ValueError("Ambiguous narrative source archive member: " + name)
                if not matches or matches[0].filename != name or matches[0].is_dir():
                    mismatched.append(name)
                    continue
                info = matches[0]
                # Source-only archives are small; never expand an unbounded ZIP member.
                if info.file_size > 4 * 1024 * 1024:
                    raise ValueError("Narrative source member exceeds the reader limit")
                data = archive.read(info)
                actual = digest(data)
                if actual != sha:
                    mismatched.append(name)
                members.append({"member": name, "sha256": actual, "bytes": len(data)})
    except (zipfile.BadZipFile, RuntimeError) as exc:
        raise ValueError("Cannot verify retained narrative source archive") from exc
    return {"archive_ref": copy.deepcopy(ref), "archive_bytes": len(payload),
            "member_refs": members, "mismatched_sources": mismatched}


def read_implementation_narrative(path, records, map_root):
    """Attach display-only prose only to source-matched implemented/frozen revisions.

    Historical mismatches are normal and remain explicitly unmatched. Broken
    immutable inputs abort the build. The caller's canonical records stay intact.
    """
    if path is None:
        return {"state": "unavailable", "reason": "No implementation narrative supplied",
                "revisions": {}, "unmatched_revisions": []}
    path, map_root = Path(path).resolve(), Path(map_root).resolve()
    payload = path.read_bytes()
    document = _read_document(payload)
    expected = {ref["member"]: ref["sha256"] for ref in document["source_refs"]}
    matches, unmatched, cache = {}, [], {}
    for revision in records["revision"]:
        if revision.get("architecture_id") not in document["candidates"]:
            continue
        if revision.get("status") not in {"implemented", "frozen"}:
            continue
        candidates, differences = [], set()
        for ref in revision.get("attachments", []):
            key = (ref.get("uri"), ref.get("sha256"))
            if key not in cache:
                cache[key] = _archive_identity(ref, map_root, expected)
            binding = cache[key]
            if binding is not None:
                differences.update(binding["mismatched_sources"])
                if not binding["mismatched_sources"]:
                    candidates.append(binding)
        if len(candidates) > 1:
            raise ValueError("Multiple matching source bundles for revision " + revision["id"])
        if not candidates:
            unmatched.append({"revision_id": revision["id"],
                              "reason": "No retained source bundle matches every narrative source identity",
                              "mismatched_sources": sorted(differences)})
            continue
        binding = copy.deepcopy(candidates[0])
        binding.pop("mismatched_sources")
        matches[revision["id"]] = {
            "revision_id": revision["id"], "architecture_id": revision["architecture_id"],
            "revision_status": revision["status"], "binding": binding,
            "narrative": copy.deepcopy(document["candidates"][revision["architecture_id"]])}
    if path.read_bytes() != payload:
        raise ValueError("Implementation narrative changed while being read")
    return {"state": "available", "schema_version": SCHEMA,
            "artifact": {"path": str(path), "sha256": digest(payload), "bytes": len(payload)},
            "recorded_at": document["recorded_at"], "scope": document["scope"],
            "source_refs": document["source_refs"], "shared": document["shared"],
            "revisions": matches, "unmatched_revisions": unmatched,
            "verification": "Every named Runtime member was hashed from the exact immutable revision ZIP. No live Runtime file was read or imported. Narrative is descriptive, not a performance or readiness assessment."}
