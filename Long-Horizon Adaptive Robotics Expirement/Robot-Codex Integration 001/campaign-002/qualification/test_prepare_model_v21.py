"""Exact policy parity and source closure for the fresh lifecycle qualification."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import prepare_model_v21 as subject
import prepare_native
import prepare_boundary_v3
import host_probe

class InventoryTests(unittest.TestCase):
    def test_all_model_policies_unchanged_and_inputs_additive(self):
        root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        for kind in ('smoke','stock','home'):
            old=subject.prior.prepare(kind,'test-revision','test-'+kind,24101,root/(kind+'-old.json'))
            new=subject.prepare(kind,'test-revision','test-'+kind,24101,root/(kind+'-new.json'))
            before=old.pop('runtime_input_files');after=new.pop('runtime_input_files')
            self.assertEqual(old,new);self.assertTrue(set(before)<=set(after))
            self.assertTrue(set(subject.pre_exit_inputs())<=set(after))

    def test_source_closure_in_native_boundary_host_and_raw_prerequisite(self):
        required=set(subject.pre_exit_inputs())
        native={p.relative_to(subject.REPO).as_posix() for p in prepare_native.inventory()}
        self.assertTrue(required<=native)
        self.assertTrue(required<=set(prepare_boundary_v3.inventory()))
        self.assertTrue(required<=set(prepare_boundary_v3.boundary_suite.sources()))
        root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        output=root/'host.json'
        host_probe.prepare(SimpleNamespace(run_id='test-host',revision='test-revision',sim_cap_s=240,
            purpose='continuous-physics-during-durable-io',output=output,manifest=output))
        self.assertTrue(required<=set(json.loads(output.read_text())['runtime_input_files']))
        spec=importlib.util.spec_from_file_location('pre_exit_raw_inventory',subject.CAMPAIGN/'harness/raw_event_preflight_v2.py')
        raw=importlib.util.module_from_spec(spec);spec.loader.exec_module(raw)
        self.assertTrue(required<=set(raw.required_sources()))

    def test_existing_output_and_missing_required_input_fail(self):
        root=Path(self.enterContext(tempfile.TemporaryDirectory()));output=root/'existing.json'
        output.write_bytes(b'original');original=subject.prior.runtime_inputs
        with self.assertRaises(FileExistsError):subject.prepare('smoke','rev','id',24101,output)
        self.assertEqual(output.read_bytes(),b'original');self.assertIs(subject.prior.runtime_inputs,original)
        with patch.object(subject,'PRE_EXIT_INPUTS',subject.PRE_EXIT_INPUTS+('missing-pre-exit.py',)):
            with self.assertRaises(ValueError):subject.pre_exit_inputs()

if __name__=='__main__':unittest.main()
