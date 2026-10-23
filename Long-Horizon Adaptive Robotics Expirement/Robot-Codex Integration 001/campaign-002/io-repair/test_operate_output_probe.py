"""Guards for the rejected route only; no obsolete operator workflow is exercised."""
import ast
import contextlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location("rejected_output_operator",Path(__file__).with_name("operate_output_probe.py"))
OP=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(OP)


class RejectedOperatorTests(unittest.TestCase):
    def guarded(self, action, cli=False, existing=False):
        with tempfile.TemporaryDirectory() as tmp,contextlib.ExitStack() as stack:
            root=Path(tmp)/"diagnostic";snapshot=Path(tmp)/"map/release/snapshot.json"
            if existing:
                (root/"records").mkdir(parents=True)
                (root/"manifest.json").write_bytes(b"existing manifest must remain byte-identical")
                (root/"records/submit.json").write_bytes(b'{"state":"succeeded","exit_status":0}')
                snapshot.parent.mkdir(parents=True);snapshot.write_bytes(b"existing snapshot")
            before={str(p.relative_to(tmp)):p.read_bytes() for p in Path(tmp).rglob("*") if p.is_file()}
            for key,value in {"ROOT":root,"RECORDS":root/"records","MANIFEST":root/"manifest.json",
                              "OUTPUT":root/"evidence","SNAPSHOT":snapshot,"MAP":Path(tmp)/"map"}.items():
                stack.enter_context(patch.object(OP,key,value))
            touched=[]
            for name in ("modules","read","save","queue","unused","source_inputs","verify_frozen","frozen_identities"):
                touched.append(stack.enter_context(patch.object(OP,name,side_effect=AssertionError("Reached rejected workflow: "+name))))
            with self.assertRaisesRegex(RuntimeError,"unsupported local-only"):
                OP.main([action]) if cli else getattr(OP,action)()
            for mock in touched:mock.assert_not_called()
            after={str(p.relative_to(tmp)):p.read_bytes() for p in Path(tmp).rglob("*") if p.is_file()}
            self.assertEqual(before,after)
            if not existing:self.assertFalse(root.exists());self.assertFalse(snapshot.parent.exists())

    def test_prepare_blocked_before_registry_or_footprint(self):self.guarded("prepare")
    def test_launch_blocked_before_submission_or_intent(self):self.guarded("launch")
    def test_settle_blocked_before_reads_status_or_registration(self):self.guarded("settle")
    def test_existing_success_receipt_cannot_unblock_any_action(self):
        for action in ("prepare","launch","settle"):
            with self.subTest(action=action):self.guarded(action,existing=True)
    def test_cli_actions_enforce_same_guard(self):
        for action in ("prepare","launch","settle"):
            with self.subTest(action=action):self.guarded(action,cli=True)
    def test_guard_is_first_statement_in_each_operator_action(self):
        tree=ast.parse(Path(OP.__file__).read_text())
        functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        for action in ("prepare","launch","settle"):
            first=functions[action].body[0]
            self.assertIsInstance(first,ast.Expr);self.assertIsInstance(first.value,ast.Call)
            self.assertEqual(first.value.func.id,"reject_unsupported_route")
    def test_retained_pure_contract_matches_probe_without_binary_or_runtime_work(self):
        probe=OP.load(OP.PROBE,"blocked_probe_contract_only")
        self.assertEqual(tuple(x["name"] for x in OP.cases(probe)),OP.CASE_NAMES)
        self.assertEqual(OP.argv()[5:],["--snapshot",str(OP.SNAPSHOT),"--manifest",str(OP.MANIFEST),"--output",str(OP.OUTPUT)])
        with patch.object(probe,"validate_sources") as sources,patch.object(probe,"execute_runtime") as runtime:
            with self.assertRaisesRegex(RuntimeError,"Unsupported remote route"):probe.run(None)
            sources.assert_not_called();runtime.assert_not_called()


if __name__=="__main__":unittest.main()
