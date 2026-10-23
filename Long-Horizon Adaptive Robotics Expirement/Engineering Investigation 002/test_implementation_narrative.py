"""Synthetic source ZIPs only; no Runtime import, evidence or physical workload."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import warnings
import zipfile

import implementation_narrative as reader


class NarrativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.map = self.root / "Map"
        self.map.mkdir()
        self.sources = {name: ("# synthetic source " + name + "\n").encode()
                        for name in reader.SOURCE_MEMBERS}
        self.document = {
            "schema_version": reader.SCHEMA, "recorded_at": "2026-01-01",
            "scope": "Synthetic fixture only", "shared": "Synthetic shared mechanism",
            "source_refs": [{"member": name, "source": "Runtime/" + name,
                             "sha256": reader.digest(data), "lines": "1"}
                            for name, data in sorted(self.sources.items())],
            "candidates": {name: {field: name + " synthetic " + field for field in reader.FIELDS}
                           for name in reader.ARCHITECTURES}}
        self.path = self.root / "narrative.json"
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.document), encoding="utf-8")

    def archive(self, name="runtime.zip", changes=None, duplicate=None):
        path = self.map / name
        sources = {**self.sources, **(changes or {})}
        with zipfile.ZipFile(path, "w") as bundle:
            for member, data in sources.items():
                bundle.writestr(member, data)
            if duplicate:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    bundle.writestr(duplicate, b"# ambiguous source\n")
        return {"uri": name, "sha256": reader.digest(path.read_bytes()), "state": "available",
                "label": "Synthetic retained source", "access": "operator", "locator": None}

    def revision(self, identity="revision", status="implemented", ref=None):
        return {"id": identity, "architecture_id": "B01-A1", "status": status,
                "mechanism": "Original immutable wording", "details": {},
                "attachments": [ref or self.archive()]}

    def read(self, revisions):
        return reader.read_implementation_narrative(self.path, {"revision": revisions}, self.map)

    def test_exact_retained_members_match_implemented_and_frozen_without_record_mutation(self):
        ref = self.archive()
        revisions = [self.revision("dev", ref=ref), self.revision("final", "frozen", ref)]
        before = copy.deepcopy(revisions)
        result = self.read(revisions)
        self.assertEqual(set(result["revisions"]), {"dev", "final"})
        self.assertEqual(result["revisions"]["dev"]["narrative"], self.document["candidates"]["B01-A1"])
        binding = result["revisions"]["dev"]["binding"]
        self.assertEqual(binding["archive_ref"], ref)
        self.assertEqual({item["member"]: item["sha256"] for item in binding["member_refs"]},
                         {name: reader.digest(data) for name, data in self.sources.items()})
        self.assertEqual(result["artifact"]["sha256"], reader.digest(self.path.read_bytes()))
        self.assertEqual(revisions, before)

    def test_old_snapshot_never_uses_current_or_matching_sibling_revision(self):
        old = self.revision("old", ref=self.archive("old.zip", {"cell.py": b"# old planner\n"}))
        new = self.revision("new", ref=self.archive("new.zip"))
        # A tempting live source tree has no authority and is never consulted.
        live = self.map.parent / "Runtime"
        live.mkdir()
        for name, data in self.sources.items():
            (live / name).write_bytes(data)
        result = self.read([old, new])
        self.assertEqual(set(result["revisions"]), {"new"})
        self.assertEqual(result["unmatched_revisions"][0]["revision_id"], "old")
        self.assertEqual(result["unmatched_revisions"][0]["mismatched_sources"], ["cell.py"])
        for path in live.iterdir():
            path.write_bytes(b"# unrelated current bytes\n")
        self.assertEqual(self.read([old, new]), result)

    def test_proposed_and_missing_source_revisions_keep_original_record(self):
        proposed = self.revision("proposal", "proposed")
        missing = self.revision("missing", ref=proposed["attachments"][0])
        missing["attachments"] = []
        result = self.read([proposed, missing])
        self.assertEqual(result["revisions"], {})
        self.assertEqual([r["revision_id"] for r in result["unmatched_revisions"]], ["missing"])
        absent = reader.read_implementation_narrative(None, {"revision": [proposed]}, self.map)
        self.assertEqual(absent["state"], "unavailable")
        self.assertEqual(absent["revisions"], {})

    def test_frozen_registrar_copy_is_bound_without_live_source(self):
        ref = self.archive()
        retained = self.map / "releases" / "batch01-final" / "code-bundle.zip"
        retained.parent.mkdir(parents=True)
        (self.map / ref["uri"]).replace(retained)
        ref["uri"] = "releases/batch01-final/code-bundle.zip"
        revision = self.revision("release-frozen", "frozen", ref)
        result = self.read([revision])
        self.assertEqual(set(result["revisions"]), {"release-frozen"})
        self.assertEqual(result["revisions"]["release-frozen"]["binding"]["archive_ref"], ref)
        self.assertFalse((self.root / "Runtime").exists())

    def test_matching_zip_outside_map_is_rejected_including_prepared_artifacts(self):
        ref = self.archive()
        payload = (self.map / ref["uri"]).read_bytes()
        with tempfile.TemporaryDirectory() as outside:
            locations = [self.root / "Evidence" / "raw" / "run" / "runtime.zip",
                         self.root / "Runtime" / "runtime.zip",
                         self.root / "candidate_state" / "run" / "runtime.zip",
                         Path(outside) / "runtime.zip",
                         self.root / "Evidence" / "prepared-artifacts" / "release" / "runtime.zip"]
            for path in locations:
                with self.subTest(path=path):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(payload)
                    escaped = {**ref, "uri": str(path)}
                    with self.assertRaisesRegex(ValueError, "escaped"):
                        self.read([self.revision(ref=escaped)])

    def test_baseline_receives_its_own_source_matched_fields(self):
        revision = self.revision("baseline")
        revision["architecture_id"] = "B01-C0"
        result = self.read([revision])
        self.assertEqual(result["revisions"]["baseline"]["narrative"], self.document["candidates"]["B01-C0"])
        self.assertNotEqual(result["revisions"]["baseline"]["narrative"], self.document["candidates"]["B01-A1"])

    def test_tampered_archive_is_an_integrity_error_not_a_silent_mismatch(self):
        revision = self.revision()
        path = self.map / revision["attachments"][0]["uri"]
        with path.open("ab") as handle:
            handle.write(b"changed after immutable reference")
        with self.assertRaisesRegex(ValueError, "archive hash"):
            self.read([revision])

    def test_duplicate_archive_member_and_ambiguous_bundle_are_rejected(self):
        for duplicate in ("candidates.py", "CANDIDATES.PY"):
            with self.subTest(duplicate=duplicate):
                revision = self.revision(ref=self.archive(duplicate=duplicate))
                with self.assertRaisesRegex(ValueError, "Ambiguous"):
                    self.read([revision])
        revision = self.revision(ref=self.archive("first.zip"))
        revision["attachments"].append(self.archive("second.zip"))
        with self.assertRaisesRegex(ValueError, "Multiple matching"):
            self.read([revision])

    def test_missing_source_and_modified_narrative_binding_fail_closed(self):
        ref = self.archive()
        revision = self.revision(ref=ref)
        self.document["source_refs"][0]["sha256"] = "0" * 64
        self.save()
        self.assertEqual(self.read([revision])["revisions"], {})
        self.document["source_refs"].pop()
        self.save()
        with self.assertRaisesRegex(ValueError, "complete Runtime"):
            self.read([revision])
        self.path.write_text('{"schema_version":"a","schema_version":"b"}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.read([revision])

    def test_builder_optional_narrative_embeds_binding_and_retains_canonical_bytes(self):
        import build_workspace as builder
        from test_workspace import ScriptCollector, unpack_snapshot
        amap = builder.load_map_module()
        for name in amap.KINDS.values():
            (self.map / name).write_bytes(b"")
        architecture = amap.template("architecture")
        architecture.update(id="B01-A1", author="synthetic fixture", recorded_at="2026-01-01T00:00:00Z",
                            title="Synthetic architecture", summary="Original proposal overview")
        revision = amap.template("revision")
        revision.update(self.revision(), author="synthetic fixture", recorded_at="2026-01-01T00:00:00Z",
                        title="Synthetic implementation", summary="Original revision summary")
        (self.map / "architectures.jsonl").write_text(json.dumps(architecture) + "\n", encoding="utf-8")
        (self.map / "revisions.jsonl").write_text(json.dumps(revision) + "\n", encoding="utf-8")
        before = {path.name: path.read_bytes() for path in self.map.iterdir()}
        output = self.root / "view" / "index.html"
        result = builder.build(self.map, output, implementation_narrative=self.path)
        parser = ScriptCollector()
        parser.feed(output.read_text(encoding="utf-8"))
        snapshot = unpack_snapshot(parser.data)
        self.assertEqual(result["implementation_narrative_revisions"], ["revision"])
        self.assertEqual(snapshot["records"]["revision"], [revision])
        self.assertEqual(snapshot["implementation_narrative"]["artifact"]["sha256"], reader.digest(self.path.read_bytes()))
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.map.iterdir()})
        result = builder.build(self.map, output)
        self.assertEqual(result["implementation_narrative_revisions"], [])

    @unittest.skipUnless(shutil.which("node"), "Native UI helper check needs Node.js")
    def test_ui_selects_only_bound_revision_and_preserves_historical_fallback(self):
        template = (Path(__file__).parent / "workspace.html").read_text(encoding="utf-8")
        helpers = template.split("/*__IMPLEMENTATION_NARRATIVE_START__*/")[1].split(
            "/*__IMPLEMENTATION_NARRATIVE_END__*/")[0]
        revision = self.revision()
        snapshot = {"implementation_narrative": self.read([revision])}
        script = "const assert=require('node:assert/strict');const snapshot=" + json.dumps(snapshot) + ";\n"
        script += "const r=" + json.dumps(revision) + ";\n" + helpers + r'''
assert.equal(mechanismValue(r,'mechanism'),'B01-A1 synthetic mechanism');
assert.equal(mechanismValue(r,'continuity'),'B01-A1 synthetic continuity');
assert.equal(mechanismValue({...r,id:'old'},'mechanism'),'Original immutable wording');
assert.equal(mechanismValue({...r,id:'old'},'llm_role'),undefined);
assert.equal(implementationFor({...r,status:'proposed'}),null);
assert.equal(implementationFor({...r,architecture_id:'B01-A2'}),null);
assert.equal(mechanismLabel({status:'proposed'}),'Proposed mechanism');
assert.equal(mechanismLabel({status:'frozen'}),'Frozen implementation');
delete snapshot.implementation_narrative;
assert.equal(mechanismValue(r,'mechanism'),'Original immutable wording');
'''
        result = subprocess.run([shutil.which("node"), "-"], input=script, text=True,
                                encoding="utf-8", capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("'Continuity mechanism'", template)
        self.assertNotIn("pill('Design description'", template)


if __name__ == "__main__":
    unittest.main()
