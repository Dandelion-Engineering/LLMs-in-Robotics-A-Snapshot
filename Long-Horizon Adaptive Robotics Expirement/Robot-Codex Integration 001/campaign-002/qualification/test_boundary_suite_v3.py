"""Preserve fixed boundary checks while adapting the transport wire protocol."""
import ast
import hashlib
from pathlib import Path
import unittest
import subprocess
import sys
from unittest.mock import patch

import boundary_suite as original
import boundary_suite_v3 as candidate
import test_boundary_suite as prior_tests


class PreservedGuestProtocol(prior_tests.FixedGuestProtocol):
    def setUp(self):
        self.enterContext(patch.object(prior_tests,'suite',candidate))


class PreservedUnitGroups(prior_tests.UnitSuiteDeclarations):
    def setUp(self):
        self.enterContext(patch.object(prior_tests,'suite',candidate))


class BoundarySourceParity(unittest.TestCase):
    def test_guest_protocol_and_every_unrelated_function_are_unchanged(self):
        self.assertEqual(original.GUEST_SOURCE,candidate.GUEST_SOURCE)
        def functions(module):
            return {n.name:n for n in ast.parse(Path(module.__file__).read_bytes()).body
                    if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
        baseline,updated=functions(original),functions(candidate)
        self.assertEqual(set(baseline),set(updated))
        for name in baseline:
            if name not in {'sources','unit_suites','qualify'}:
                self.assertEqual(ast.dump(baseline[name]),ast.dump(updated[name]),name)
        def required(function):
            node=next(n for n in ast.walk(function) if isinstance(n,ast.Assign)
                      and any(isinstance(t,ast.Name) and t.id=='required' for t in n.targets))
            return ast.literal_eval(node.value)
        self.assertEqual(required(baseline['qualify']),required(updated['qualify']))
        self.assertEqual(len(required(updated['qualify'])),12)

    def test_source_inventory_binds_both_versions_and_the_declared_channel_contract(self):
        names=candidate.sources()
        for suffix in ('qualification/boundary_suite.py','qualification/boundary_suite_v3.py',
                       'qualification/test_boundary_suite_v3.py','io-repair/CODEHOST_CHANNEL_TRANSPORT_V3.md',
                       'io-repair/CHANNEL_TRANSPORT_V3_QUALIFICATION_001.md',
                       'io-repair/CHANNEL_TRANSPORT_STARTUP_REPAIR_V1.md',
                       'io-repair/CHANNEL_PROBE_PROCESS_IDENTITY_V1.md',
                       'io-repair/CHANNEL_FINISH_FRONTIER_VALIDATION_V1.md',
                       'io-repair/CHANNEL_PROBE_SEQUENCE_SYNCHRONIZATION_V1.md',
              'io-repair/CHANNEL_OWNER_DRAIN_V1.md'):
            self.assertEqual(sum(name.endswith('/'+suffix) for name in names),1)

    def test_measured_inventory_covers_actual_transport_verifier_method_inputs(self):
        # Parse the source-bound declaration; do not execute a verifier or fixture.
        tree=ast.parse((candidate.CAMPAIGN/'assessment/transport_integrity_v3.py').read_bytes())
        declaration=next(node.value for node in tree.body if isinstance(node,ast.Assign)
                         and any(isinstance(t,ast.Name) and t.id=='SOURCE_NAMES' for t in node.targets))
        suffixes={node.value for node in ast.walk(declaration)
                  if isinstance(node,ast.Constant) and isinstance(node.value,str) and node.value.endswith('.md')}
        self.assertIn('io-repair/CHANNEL_FINISH_FRONTIER_VALIDATION_V1.md',suffixes)
        measured=candidate.sources()
        for suffix in suffixes:
            path=candidate.CAMPAIGN/suffix
            self.assertEqual(measured[path.relative_to(candidate.REPO).as_posix()],
                             hashlib.sha256(path.read_bytes()).hexdigest())

    def test_missing_required_method_cannot_produce_a_measured_inventory(self):
        original_read=Path.read_bytes
        for name in ('CHANNEL_FINISH_FRONTIER_VALIDATION_V1.md',
                     'CHANNEL_PROBE_SEQUENCE_SYNCHRONIZATION_V1.md',
                     'CHANNEL_OWNER_DRAIN_V1.md'):
            selected=candidate.CAMPAIGN/'io-repair'/name
            def read(path):
                if path==selected:
                    raise FileNotFoundError(selected)
                return original_read(path)
            with self.subTest(name=name),patch.object(Path,'read_bytes',read),self.assertRaises(FileNotFoundError):
                candidate.sources()


class FreshBoundaryImport(unittest.TestCase):
    def test_standalone_boundary_loads_exact_reader_and_sibling_dependency(self):
        # -I discards PYTHONPATH and the invoking discovery process's imports.
        code = """import sys, importlib.util
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import boundary_suite_v3 as boundary
spec=importlib.util.spec_from_file_location('cold_capture_reader',boundary.CAMPAIGN/'assessment/retained_reads.py')
reader=importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
import completion_chronology
assert Path(completion_chronology.__file__).resolve()==(boundary.CAMPAIGN/'assessment/completion_chronology.py').resolve()
assert reader.terminal_process_order is completion_chronology.terminal_process_order
print('exact boundary reader loaded')
"""
        result=subprocess.run([sys.executable,'-I','-B','-c',code,str(candidate.CAMPAIGN/'qualification')],
                              capture_output=True,text=True,encoding='utf-8',timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),'exact boundary reader loaded')


if __name__=='__main__':unittest.main()
