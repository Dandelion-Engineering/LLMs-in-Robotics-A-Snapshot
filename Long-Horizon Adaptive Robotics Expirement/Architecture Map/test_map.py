"""Regression tests use synthetic records only in temporary directories."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("map.py")
SPEC = importlib.util.spec_from_file_location("architecture_map", SCRIPT)
amap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(amap)


def draft(kind, rid):
    item = amap.template(kind)
    item.update(id=rid, author="temporary synthetic test fixture", recorded_at="2026-01-01T00:00:00+00:00")
    return item


def ref(**changes):
    item = {"label": "Synthetic evidence; not an experimental record", "uri": "test://evidence",
            "sha256": "a" * 64, "state": "available", "access": "operator", "locator": "event:1"}
    item.update(changes)
    return item


def metric(**changes):
    item = {"name": "synthetic_count", "value": 1, "unit": "count", "denominator": 2,
            "denominator_description": "two temporary fixture events", "missing_reason": None,
            "evidence": [ref()]}
    item.update(changes)
    return item


class MapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for filename in amap.KINDS.values():
            (self.root / filename).write_bytes(b"")
        self.arch = draft("architecture", "test-architecture")
        self.arch.update(title="Temporary identity", summary="A fixture, not a candidate.")
        self.revision = draft("revision", "test-revision")
        self.revision.update(architecture_id=self.arch["id"], title="Temporary snapshot",
                             summary="Synthetic", mechanism="Only a fixture; flexible nested mechanism descriptions are supported.")
        self.run = draft("run", "test-run")
        self.run.update(revision_id=self.revision["id"], condition_id="fixture-condition",
                        protocol_id="fixture-protocol", scenario_id="fixture-case",
                        paired_block_id="fixture-block", started_at="2026-01-01T00:00:00+00:00")
        self.result = draft("result", "test-result")
        self.result.update(run_id=self.run["id"], execution_status="failed", validity="valid",
                           validity_reason="Synthetic candidate crash fixture", outcome="failure",
                           ended_at="2026-01-01T00:00:01+00:00", termination_reason="fixture crash",
                           evidence=[ref()], metrics=[metric()])

    def tearDown(self):
        self.tmp.cleanup()

    def snapshot(self):
        return {name: (self.root / name).read_bytes() for name in amap.KINDS.values()}

    def append(self, kind, record):
        return amap.append_record(self.root, kind, deepcopy(record), amap.store_digest(self.snapshot()))

    def populated(self):
        for kind, item in (("architecture", self.arch), ("revision", self.revision),
                           ("run", self.run), ("result", self.result)):
            self.append(kind, item)
        return amap.read_store(self.root)[0]

    def cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", "-B", str(SCRIPT), "--root", str(self.root), *args],
                              text=True, encoding="utf-8", capture_output=True)

    def assert_invalid_append(self, kind, record, pattern):
        before = self.snapshot()
        with self.assertRaisesRegex(amap.MapError, pattern):
            self.append(kind, record)
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / ".map-write.lock").exists())

    def test_empty_lookup_build_validate_and_hash_bound_report(self):
        result = self.cli("lookup", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"total": 0, "displayed": 0, "records": []})
        self.assertEqual(self.cli("build").returncode, 0)
        valid = self.cli("validate", "--output", "validation.json", "--json")
        self.assertEqual(valid.returncode, 0, valid.stderr)
        report = json.loads(valid.stdout)
        self.assertTrue(report["ok"])
        self.assertEqual(report["store_sha256"], amap.store_digest(self.snapshot()))
        self.assertEqual(report["canonical_sha256"]["runs.jsonl"], amap.digest(b""))
        self.assertEqual(report, json.loads((self.root / "validation.json").read_text()))
        self.assertIn("No architectures", (self.root / "Catalog.md").read_text())

    def test_templates_do_not_populate_and_remain_incomplete(self):
        for kind in amap.KINDS:
            output = self.cli("template", kind)
            self.assertEqual(output.returncode, 0, output.stderr)
            form = json.loads(output.stdout)
            self.assertEqual(form["id"], "")
        self.assertTrue(all(value == b"" for value in self.snapshot().values()))

    def test_strict_json_duplicate_nonfinite_and_malformed_fail(self):
        for text in ('{"a":1,"a":2}', '{"x":NaN}', '{"details":{"x":1e999}}', '{'):
            with self.assertRaises(ValueError, msg=text):
                amap.strict_json(text)
        self.assertTrue(amap.finite(10 ** 1000))
        self.assertFalse(amap.finite(True))

    def test_invalid_canonical_input_and_missing_files_fail(self):
        for content in (b'{"id":1,"id":2}\n', b'[]\n', b'\n', b'\xef\xbb\xbf{}\n', b'{}', b'{"n":1e999}\n', b'\xff'):
            (self.root / "architectures.jsonl").write_bytes(content)
            report = amap.check(self.root)[2]
            self.assertFalse(report["ok"], content)
        (self.root / "architectures.jsonl").unlink()
        self.assertFalse(amap.check(self.root)[2]["ok"])

    def test_append_preserves_exact_prefix_and_refuses_duplicate(self):
        self.append("architecture", self.arch)
        before = (self.root / "architectures.jsonl").read_bytes()
        second = deepcopy(self.arch)
        second["id"] = "test-architecture-two"
        self.append("architecture", second)
        self.assertTrue((self.root / "architectures.jsonl").read_bytes().startswith(before))
        self.assert_invalid_append("architecture", self.arch, "duplicate global id")

    def test_bad_references_cannot_mutate_store(self):
        self.assert_invalid_append("revision", self.revision, "existing architecture")
        self.append("architecture", self.arch)
        self.append("revision", self.revision)
        cyclic = deepcopy(self.revision)
        cyclic.update(id="test-revision-two", parent_revision_id="test-revision-two")
        self.assert_invalid_append("revision", cyclic, "parent revision must be earlier")
        malformed = deepcopy(self.run)
        malformed["revision_id"] = ["not-a-string"]
        self.assert_invalid_append("run", malformed, "existing revision")

    def test_lost_update_and_active_lock_refused(self):
        stale = amap.store_digest(self.snapshot())
        self.append("architecture", self.arch)
        before = self.snapshot()
        with self.assertRaisesRegex(amap.MapError, "store changed"):
            amap.append_record(self.root, "revision", self.revision, stale)
        self.assertEqual(self.snapshot(), before)
        lock = self.root / ".map-write.lock"
        lock.write_text("another writer")
        with self.assertRaisesRegex(amap.MapError, "writer lock exists"):
            self.append("revision", self.revision)
        self.assertEqual(lock.read_text(), "another writer")
        self.assertEqual(self.snapshot(), before)

    def test_stale_catalog_is_detected_and_build_recovers(self):
        self.assertEqual(self.cli("build").returncode, 0)
        self.append("architecture", self.arch)
        report = amap.check(self.root)[2]
        self.assertFalse(report["ok"])
        self.assertIn("Catalog.md is stale", " ".join(report["errors"]))
        self.assertEqual(self.cli("build").returncode, 0)
        self.assertTrue(amap.check(self.root)[2]["ok"])

    def test_full_record_search_exact_filters_and_limits(self):
        self.arch["details"] = {"anything": {"unusual_interface": "zebra needle"}}
        self.arch["tags"] = ["tag-one"]
        data = self.populated()
        result = amap.lookup(data, "ZEBRA NEEDLE", tag="tag-one", limit=0)
        self.assertEqual((result["total"], result["displayed"]), (1, 0))
        self.assertEqual(amap.lookup(data, tag="tag")["total"], 0)
        self.assertEqual(amap.lookup(data, architecture=self.arch["id"])["total"], 4)
        found = amap.lookup(data, kind="result", stage="development", condition="fixture-condition",
                            protocol_id="fixture-protocol", outcome="failure", validity="valid")
        self.assertEqual(found["total"], 1)
        self.assertEqual(amap.lookup(data, kind="result", condition="no")["total"], 0)

    def test_history_propagates_result_notes_and_corrections(self):
        self.populated()
        corrected = deepcopy(self.result)
        corrected.update(id="test-result-correction", supersedes_result_id=self.result["id"], validity="invalid",
                         validity_reason="Synthetic infrastructure issue fixture")
        self.append("result", corrected)
        note = draft("note", "test-note")
        note.update(target_ids=[self.result["id"], self.revision["id"]], claim_type="question",
                    body="Synthetic question about two existing targets")
        self.append("note", note)
        data = amap.read_store(self.root)[0]
        for target in (self.arch["id"], self.revision["id"], self.run["id"], self.result["id"]):
            result = amap.history(data, target)
            ids = {item["record"]["id"] for item in result["records"]}
            self.assertTrue({self.result["id"], corrected["id"], note["id"]} <= ids)
        self.assertEqual(amap.history(data, "missing")["total"], 0)

    def test_result_corrections_must_be_linear_and_same_run(self):
        self.populated()
        duplicate = deepcopy(self.result)
        duplicate["id"] = "test-result-two"
        self.assert_invalid_append("result", duplicate, "latest result")
        duplicate["supersedes_result_id"] = self.result["id"]
        self.append("result", duplicate)
        branch = deepcopy(duplicate)
        branch["id"] = "test-result-branch"
        self.assert_invalid_append("result", branch, "latest result")
        run2 = deepcopy(self.run)
        run2.update(id="test-run-two", rerun_of_run_id=self.run["id"])
        self.append("run", run2)
        cross_run = deepcopy(self.result)
        cross_run.update(id="test-cross-result", run_id=run2["id"], supersedes_result_id=duplicate["id"])
        self.assert_invalid_append("result", cross_run, "different run")

    def test_note_corrections_and_multi_target_comparisons(self):
        self.populated()
        note = draft("note", "test-note")
        note.update(target_ids=[self.arch["id"], self.result["id"]], claim_type="comparison", body="Synthetic comparison")
        self.append("note", note)
        correction = deepcopy(note)
        correction.update(id="test-correction", claim_type="correction", supersedes_note_id=note["id"])
        self.append("note", correction)
        data = amap.read_store(self.root)[0]
        self.assertIn(correction["id"], {entry["record"]["id"] for entry in amap.history(data, note["id"])["records"]})
        self.assertIn(note["id"], {entry["record"]["id"] for entry in amap.history(data, correction["id"])["records"]})
        branch = deepcopy(correction)
        branch["id"] = "test-correction-two"
        self.assert_invalid_append("note", branch, "already superseded")
        dangling = deepcopy(note)
        dangling.update(id="test-dangling", target_ids=["missing"])
        self.assert_invalid_append("note", dangling, "missing or self reference")

    def test_terminal_status_and_not_run_semantics(self):
        self.populated()
        for status in ("completed", "failed", "timed_out", "aborted"):
            item = deepcopy(self.result)
            item.update(id="fixture-status", execution_status=status)
            data = amap.read_store(self.root)[0]
            data["result"] = [item]
            self.assertEqual(amap.validate_records(data, self.root), [])
        pending = deepcopy(self.result)
        pending.update(id="fixture-pending", execution_status="running", supersedes_result_id=self.result["id"])
        self.assert_invalid_append("result", pending, "execution_status")
        pending["execution_status"] = "not_run"
        self.assert_invalid_append("result", pending, "not_run requires")
        pending.update(outcome="not_assessed", validity="unknown", ended_at=None, metrics=[])
        self.append("result", pending)

    def test_metrics_units_denominators_missingness_and_nonfinite(self):
        self.populated()
        for bad in (metric(value=float("inf")), metric(value=None), metric(denominator=0), metric(unit=""), metric(evidence=[])):
            changed = deepcopy(self.result)
            changed.update(id="test-metric", supersedes_result_id=self.result["id"], metrics=[bad])
            self.assert_invalid_append("result", changed, "metric|denominator")
        good = deepcopy(self.result)
        good.update(id="test-missing-metric", supersedes_result_id=self.result["id"],
                    metrics=[metric(value=None, missing_reason="Fixture capture missing", evidence=[])])
        self.append("result", good)

    def test_revision_attachment_hash_and_path_boundary(self):
        self.append("architecture", self.arch)
        path = self.root / "mechanism.md"
        path.write_bytes(b"Synthetic mechanism attachment\n")
        self.revision["attachments"] = [ref(uri="mechanism.md", sha256=amap.digest(path.read_bytes()))]
        self.append("revision", self.revision)
        path.write_bytes(b"Changed snapshot\n")
        self.assertIn("attachment hash differs", " ".join(amap.check(self.root)[2]["errors"]))
        data = amap.read_store(self.root)[0]
        data["revision"][0]["attachments"][0]["uri"] = "../outside.md"
        self.assertIn("within the map", " ".join(amap.validate_records(data, self.root)))

    def test_evaluation_requires_frozen_identity_and_references(self):
        self.append("architecture", self.arch)
        self.append("revision", self.revision)
        self.run["stage"] = "evaluation"
        self.assert_invalid_append("run", self.run, "frozen revision")
        frozen = deepcopy(self.revision)
        frozen.update(id="test-frozen", parent_revision_id=self.revision["id"], status="frozen")
        self.append("revision", frozen)
        self.run["revision_id"] = frozen["id"]
        recorded = {"state": "recorded", "refs": [ref(access="evaluator_only")], "reason": None}
        self.run["seeds"] = deepcopy(recorded)
        self.run["frozen_refs"] = {role: deepcopy(recorded) for role in self.run["frozen_refs"]}
        self.run["frozen_refs"]["models"] = {"state": "none", "refs": [], "reason": "No model in synthetic fixture"}
        self.append("run", self.run)

    def test_cli_rejects_malformed_append_without_changes(self):
        before = self.snapshot()
        source = self.root / "draft.json"
        source.write_text('{"id":"a","id":"b"}', encoding="utf-8")
        result = self.cli("append", "architecture", "--input", str(source),
                          "--expected-sha256", amap.store_digest(before))
        self.assertEqual(result.returncode, 1)
        self.assertIn("duplicate JSON key", result.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.cli("lookup", "--limit", "-1").returncode, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
