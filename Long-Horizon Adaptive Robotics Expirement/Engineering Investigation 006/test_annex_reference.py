"""Synthetic-only regression for optional annex size annotations.

Exercise the unchanged Analysis005 collector/analyzer using public synthetic
slots, then the new reader. No actual evidence, queue state or robot work.
Only the independent annex verifier and queue-owner boundary are mocked.
"""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
LEGACY = HERE.parent / "Engineering Investigation 005"
TOOLS = HERE.parent / "Batch 01" / "Release Analysis 005"
sys.path.insert(0, str(LEGACY))

import analysis_adapter
import derivative_adapter

for module in (analysis_adapter, derivative_adapter):
    if Path(module.__file__).resolve() != LEGACY / (module.__name__ + ".py"):
        raise RuntimeError("Synthetic reader fixture resolved a different legacy helper")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reader = load("investigation006_annex_test_reader", HERE / "analysis_provenance.py")
old_reader = load("investigation005_annex_test_reader", LEGACY / "analysis_provenance.py")
analyzer = load("investigation006_test_actual_analyzer005", TOOLS / "analyze_results.py")
with patch.dict(sys.modules, {"collect_results": analyzer.collector}):
    fixtures = load("investigation006_actual_analysis_fixture", TOOLS / "synthetic_fixtures.py")


class AnnexReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-annex006-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.fixture = fixtures.Fixture(self.root)
        canonical = self.fixture.write_canonical()

        def production_shape_verify(*args, **kwargs):
            verified = self.fixture.fake_verify(*args, **kwargs)
            # The real recovery_contract.ref returns path/hash, unlike the old
            # fixture's collector.ref, which always includes byte counts.
            for key in ("annex_ref", "source_index_ref"):
                verified[key] = {k: v for k, v in verified[key].items() if k != "bytes"}
            return verified

        self.selected_path = self.root / "selected.json"
        with patch.object(analyzer.collector, "verify_annex", side_effect=production_shape_verify):
            self.selected = analyzer.collector.collect(
                self.fixture.root, self.fixture.records, notes=self.fixture.notes,
                annex_path=self.fixture.annex_path)
        self.selected.update(canonical)
        self.fixture.write(self.selected_path, self.selected)
        self.output = self.root / "analysis"
        with patch.object(analyzer, "MAP", self.root / "canonical"), \
             patch.object(analyzer.collector, "verify_annex", side_effect=production_shape_verify), \
             patch.object(analyzer.queue_authority, "queued_job", return_value={"id": "synthetic-annex006-job"}), \
             patch.object(analyzer.protocol, "_entropy", side_effect=AssertionError("No concealed seed generation")):
            self.provenance = analyzer.analyze_results(
                self.fixture.root, self.selected_path, self.output,
                annex_path=self.fixture.annex_path)
        self.sidecar = self.output / "analysis-provenance.json"
        self.page = self.root / "view.html"
        self.bundle = analysis_adapter.read_analysis(self.output / "analysis.json", self.page)
        self.receipt = self.root / "synthetic-receipt.json"
        self.fixture.write(self.receipt, {
            "id": "synthetic-annex006-job", "state": "succeeded", "exit_status": 0,
            "ended_at": "synthetic-completed", "argv": [sys.executable,
                str(TOOLS / "analyze_results.py"), "--output-dir", str(self.output)]})

    def bind(self, record=None):
        if record is not None:
            self.fixture.write(self.sidecar, record)
        return reader.bind_analysis(self.bundle, self.sidecar, self.receipt, self.page)

    def changed_selection(self, selected):
        self.fixture.write(self.selected_path, selected)
        record = copy.deepcopy(self.provenance)
        ref = analyzer.ref(self.selected_path)
        record["selected_results"] = ref
        record["inputs_before"]["selected_results"] = ref
        record["inputs_after"]["selected_results"] = copy.deepcopy(ref)
        return record

    def test_actual_analyzer_production_asymmetry_reproduces_and_repairs_failure(self):
        self.assertEqual(set(self.selected["recovery_annex_ref"]), {"path", "sha256"})
        self.assertEqual(set(self.provenance["recovery_annex_ref"]), {"path", "sha256", "bytes"})
        with self.assertRaisesRegex(ValueError, "different supplemental annexes"):
            old_reader.bind_analysis(self.bundle, self.sidecar, self.receipt, self.page)
        before = copy.deepcopy(self.bundle)
        bound = self.bind()
        self.assertEqual(bound["binding"]["state"], "verified")
        self.assertEqual(bound["report"], before["report"])
        self.assertEqual(self.bundle, before)
        self.assertEqual(len(bound["binding"]["supplemental_sources"]), 2)

    def test_matching_declared_size_and_resolved_relative_location_are_valid(self):
        selected = copy.deepcopy(self.selected)
        selected["recovery_annex_ref"] = {
            **selected["recovery_annex_ref"], "path": "./annex.json",
            "bytes": self.fixture.annex_path.stat().st_size}
        # Reader006 resolves this identity relative to the selected artifact.
        # The existing final display-link check resolves relative refs from the
        # sidecar directory, so this focused identity check avoids claiming a
        # broader relative-link behavior change in the unchanged005 reader.
        left = reader.verified_artifact_identity(selected["recovery_annex_ref"], base=self.root)
        right = reader.verified_artifact_identity(self.provenance["recovery_annex_ref"])
        self.assertEqual(left, right)
        selected["recovery_annex_ref"]["path"] = str(self.fixture.annex_path)
        self.assertEqual(self.bind(self.changed_selection(selected))["binding"]["state"], "verified")

    def test_sidecar_annex_rejects_wrong_hash_size_path_and_missing_reference(self):
        duplicate = self.root / "equal-byte-annex-copy.json"
        duplicate.write_bytes(self.fixture.annex_path.read_bytes())
        for field, value in (("sha256", "0" * 64), ("bytes", 1), ("bytes", True),
                             ("path", str(duplicate)), ("path", str(self.root / "absent.json")),
                             (None, None)):
            with self.subTest(field=field, value=value):
                record = copy.deepcopy(self.provenance)
                if field is None: record["recovery_annex_ref"] = None
                else: record["recovery_annex_ref"][field] = value
                with self.assertRaises(ValueError): self.bind(record)

    def test_selected_annex_rejects_wrong_hash_size_path_and_missing_reference(self):
        duplicate = self.root / "equal-byte-annex-copy.json"
        duplicate.write_bytes(self.fixture.annex_path.read_bytes())
        for field, value in (("sha256", "0" * 64), ("bytes", 1), ("bytes", True),
                             ("path", str(duplicate)), (None, None)):
            with self.subTest(field=field, value=value):
                selected = copy.deepcopy(self.selected)
                if field is None: selected["recovery_annex_ref"] = None
                else: selected["recovery_annex_ref"][field] = value
                with self.assertRaises(ValueError): self.bind(self.changed_selection(selected))

    def test_before_annex_rejects_missing_and_equal_byte_substitution(self):
        duplicate = self.root / "equal-byte-annex-copy.json"
        duplicate.write_bytes(self.fixture.annex_path.read_bytes())
        for replacement in (None, analyzer.ref(duplicate)):
            with self.subTest(replacement=replacement):
                record = copy.deepcopy(self.provenance)
                for key in ("inputs_before", "inputs_after"):
                    if replacement is None: record[key].pop("recovery_annex")
                    else: record[key]["recovery_annex"] = copy.deepcopy(replacement)
                with self.assertRaises(ValueError): self.bind(record)

    def test_changed_annex_bytes_are_rejected(self):
        self.fixture.annex_path.write_text("changed synthetic authority", encoding="utf-8")
        with self.assertRaises(ValueError): self.bind()

    def test_original_receipt_inventory_and_report_guards_remain(self):
        wrong = copy.deepcopy(self.provenance)
        wrong["inputs_after"]["recovery_annex"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError): self.bind(wrong)
        self.fixture.write(self.sidecar, self.provenance)
        receipt = json.loads(self.receipt.read_text(encoding="utf-8"))
        receipt["exit_status"] = 1
        self.fixture.write(self.receipt, receipt)
        with self.assertRaises(ValueError): self.bind()


if __name__ == "__main__":
    unittest.main()
