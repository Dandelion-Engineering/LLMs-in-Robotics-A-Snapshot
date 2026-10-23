"""Mocked operator and pure source-contract checks; no native/map/queue actions."""
from contextlib import ExitStack
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('socket_control_test_target', HERE / 'control_socket_abort_diagnostic.py')
ctl = importlib.util.module_from_spec(spec); spec.loader.exec_module(ctl)
p = ctl.p


class PreparerTests(unittest.TestCase):
    def test_exact_basis_and_seven_changes_preserve_every_other_policy_field(self):
        basis = p.read(p.BASIS); before = copy.deepcopy(basis)
        self.assertEqual(p.identity(p.BASIS)['sha256'], p.BASIS_SHA)
        value = p.build_manifest(basis, ['finite/new-source.py'])
        self.assertEqual(basis, before)
        self.assertEqual(sorted(k for k in value if value[k] != basis[k]), p.CHANGED_FIELDS)
        for key in set(basis) - set(p.CHANGED_FIELDS): self.assertEqual(value[key], basis[key])
        self.assertEqual(value['model_turns_max'], 1)
        self.assertEqual(value['invocation_wall_cap_s'], 600)
        self.assertEqual(value['run_id'], 'RCI001-C02-shutdown-diagnostic-003')
        self.assertEqual(value['framework_revision'], 'RCI001-C02-dev-091')
        self.assertTrue(set(basis['runtime_input_files']) < set(value['runtime_input_files']))

    def test_wrong_basis_identity_or_integer_bounds_rejected(self):
        for key, bad in [('run_id', 'other'), ('framework_revision', 'other'),
                         ('model_turns_max', True), ('model_turns_max', 1),
                         ('invocation_wall_cap_s', 600.0), ('invocation_wall_cap_s', 601)]:
            with self.subTest(key=key,bad=bad):
                value = p.read(p.BASIS); value[key] = bad
                with self.assertRaises(ValueError): p.build_manifest(value, ['new.py'])

    def test_changed_basis_fails_before_output_or_inventory_reads(self):
        with patch.object(p, 'identity', return_value={'sha256':'0'*64}), \
             patch.object(p, 'inputs') as inputs, patch.object(p, 'save') as save:
            with self.assertRaisesRegex(ValueError, 'policy basis changed'): p.main()
            inputs.assert_not_called(); save.assert_not_called()

    def test_preparer_has_no_registry_subprocess_or_queue_action(self):
        import ast
        tree = ast.parse(Path(p.__file__).read_text(encoding='utf-8'))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        self.assertFalse({'subprocess', 'registry', 'command_once'} & names)

    def test_support_inventory_includes_both_declarations_full_checks_and_alignment(self):
        required = set(p.SUPPORT_INPUTS)
        self.assertTrue({'SOCKET_ABORT_DIAGNOSTICS_V1.md','SOCKET_ABORT_NATIVE_DIAGNOSTIC_V1.md',
            'checks-033/test-execution.json','checks-033-source-state.json',
            'checks-033-execution-001/receipt.json',
            'socket-abort-assessment-fixture-development-001/final-receipt.json'} <= required)
        self.assertNotIn('checks-033/repair-test-receipt.json', required)


class SourceTests(unittest.TestCase):
    def fixture(self):
        baseline = {f'original/{i}.py': {'sha256':'a'*64,'bytes':1} for i in range(624)}
        old = {**baseline, 'unchanged.py': {'sha256':'b'*64,'bytes':2}}
        for n in ctl.EXPECTED_CHANGES:
            old[ctl.name(ctl.CAMPAIGN/n)] = {'sha256':'c'*64,'bytes':3}
        new = copy.deepcopy(old)
        for n, h in ctl.EXPECTED_CHANGES.items(): new[ctl.name(ctl.CAMPAIGN/n)] = {'sha256':h,'bytes':4}
        new['declared/new.py'] = {'sha256':'d'*64,'bytes':5}
        return old,new,baseline,['declared/new.py']

    def test_exact_three_changes_and_explicit_unchanged_additions(self):
        delta = ctl.compare_sources(*self.fixture())
        self.assertEqual(len(delta['changed_existing_sources']),3)
        self.assertEqual(delta['added_sources'],['declared/new.py'])
        self.assertEqual(delta['removed_sources'],[])

    def test_extra_mutation_wrong_declared_hash_or_missing_required_change(self):
        for mode in ('extra','wrong','missing'):
            old,new,base,inputs=self.fixture()
            key=ctl.name(ctl.CAMPAIGN/'harness/codehost_bridge_v3.py')
            if mode=='extra': new['unchanged.py']['sha256']='f'*64
            elif mode=='wrong': new[key]['sha256']='f'*64
            else: new[key]=old[key]
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'shared-source'):
                ctl.compare_sources(old,new,base,inputs)

    def test_omission_and_undeclared_addition_rejected(self):
        for mode in ('omit','extra'):
            old,new,base,inputs=self.fixture()
            if mode=='omit':del new['unchanged.py']
            else:new['unrequested.py']={'sha256':'e'*64,'bytes':1}
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'additions or omissions'):
                ctl.compare_sources(old,new,base,inputs)

    def test_original624_is_independently_bound(self):
        old,new,base,inputs=self.fixture()
        base['original/0.py']={'sha256':'f'*64,'bytes':9}
        with self.assertRaisesRegex(ValueError,'Original624'):ctl.compare_sources(old,new,base,inputs)

    def test_original624_count_is_not_guessed_from_subset(self):
        old,new,base,inputs=self.fixture();base.pop('original/0.py')
        with self.assertRaisesRegex(ValueError,'Original624'):ctl.compare_sources(old,new,base,inputs)

    def archive_fixture(self, root, *, extra=False, bad_bytes=False):
        raw=b'bound source\n'; source=root/'source.py';source.write_bytes(raw)
        snapshot=root/'snapshot.json'
        item={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
        snapshot.write_text(json.dumps({'sources':{'source.py':item}}),encoding='utf-8')
        with zipfile.ZipFile(root/'code.zip','w') as z:
            z.writestr('source.py',b'wrong' if bad_bytes else raw)
            if extra:z.writestr('extra.py',b'new')
        return snapshot

    def test_archive_exact_members_bytes_and_current_source(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(ctl,'REPO',Path(tmp)):
            snapshot=self.archive_fixture(Path(tmp))
            ctl.archive_sources(snapshot,current=True)
            (Path(tmp)/'source.py').write_text('drift',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Current source'):ctl.archive_sources(snapshot,current=True)

    def test_archive_extra_member_and_wrong_bytes_rejected(self):
        for mode in ('extra','bytes'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp,patch.object(ctl,'REPO',Path(tmp)):
                snapshot=self.archive_fixture(Path(tmp),extra=mode=='extra',bad_bytes=mode=='bytes')
                with self.assertRaises(ValueError):ctl.archive_sources(snapshot)

    def test_snapshot_hash_pin_rejected_before_opening_archive(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(ctl,'REPO',Path(tmp)):
            snapshot=self.archive_fixture(Path(tmp))
            with self.assertRaisesRegex(ValueError,'snapshot identity'):ctl.archive_sources(snapshot,'0'*64)


class CheckReceiptTests(unittest.TestCase):
    def test_retained_full_checks_and_instrumentation_metadata_join(self):
        # Read-only source/test receipts, with only not-yet-final wrapper receipts mocked.
        with patch.object(ctl, 'final_checks') as wrapper_checks:
            value = ctl.support_checks()
        self.assertTrue(value['passed'])
        self.assertEqual(wrapper_checks.call_count, 2)

    def setup_receipt(self, root):
        source=root/'source.py';source.write_text('bound',encoding='utf-8')
        output=root/'stdout';output.write_text('ok',encoding='utf-8')
        receipt={'schema':'mock-check-1','passed':True,
                 'source_bindings':{'source.py':ctl.binding(source)},
                 'commands':[{'argv':['exact'],'exit_code':0,'stdout':p.identity(output),'stderr':p.identity(output)}]}
        path=root/'receipt.json';path.write_text(json.dumps(receipt),encoding='utf-8')
        return path,source,receipt

    def test_actual_receipt_bytes_and_tested_sources_required(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(ctl,'CAMPAIGN',Path(tmp)),patch.object(p,'REPO',Path(tmp)):
            path,source,value=self.setup_receipt(Path(tmp))
            ctl.final_checks(path,'mock-check-1',[source],['exact'])
            source.write_text('changed',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'tested sources'):ctl.final_checks(path,'mock-check-1',[source],['exact'])

    def test_missing_extra_failed_boolean_exit_or_wrong_command_rejected(self):
        for mode in ('missing','extra','failed','boolean','argv','schema'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp,patch.object(ctl,'CAMPAIGN',Path(tmp)),patch.object(p,'REPO',Path(tmp)):
                path,source,value=self.setup_receipt(Path(tmp))
                if mode=='missing':value['source_bindings']={}
                elif mode=='extra':value['source_bindings']['other.py']=ctl.binding(source)
                elif mode=='failed':value['passed']=False
                elif mode=='boolean':value['commands'][0]['exit_code']=False
                elif mode=='argv':value['commands'][0]['argv']=['other']
                else:value['schema']='foreign'
                path.write_text(json.dumps(value),encoding='utf-8')
                with self.assertRaises(ValueError):ctl.final_checks(path,'mock-check-1',[source],['exact'])

    def test_mutated_output_and_receipt_after_source_binding_rejected(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(ctl,'CAMPAIGN',Path(tmp)),patch.object(p,'REPO',Path(tmp)):
            path,source,value=self.setup_receipt(Path(tmp))
            (Path(tmp)/'stdout').write_text('new',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Artifact changed'):ctl.final_checks(path,'mock-check-1',[source],['exact'])


class ActionTests(unittest.TestCase):
    def context(self, action, failure=None):
        stack=ExitStack();self.addCleanup(stack.close)
        support=stack.enter_context(patch.object(ctl,'support_checks',return_value={'commands':['passed']}))
        inv=stack.enter_context(patch.object(ctl,'source_inventory',return_value={'exact':True}))
        stack.enter_context(patch.object(p,'inputs',return_value=['new.py']))
        stack.enter_context(patch.object(p,'build_manifest',return_value={'candidate':True}))
        def read(path):
            if str(path).endswith('source-change-inventory.json'):return {'exact':True}
            if str(path).endswith('test-execution.json'):return {'commands':['passed']}
            return {'candidate':True}
        stack.enter_context(patch.object(p,'read',side_effect=read))
        stack.enter_context(patch.object(ctl.c,'identity',side_effect=lambda path:{'path':str(path),'sha256':'a'*64}))
        verify=stack.enter_context(patch.object(ctl.c,'verify_repair_tests',return_value={'commands':['passed']}))
        command=stack.enter_context(patch.object(ctl.c,'command_once',return_value={'exit_code':0,'stdout':''}))
        save=stack.enter_context(patch.object(ctl.c,'save_exact'))
        if failure=='support':support.side_effect=ValueError('support')
        if failure=='sources':inv.side_effect=ValueError('sources')
        return support,inv,verify,command,save

    def test_prepare_uses_durable_exclusive_command_after_all_gates(self):
        _,inv,_,command,_=self.context('prepare')
        ctl.run_action('prepare')
        inv.assert_called_once();command.assert_called_once()
        self.assertEqual(command.call_args.kwargs['absent'],[ctl.MANIFEST.parent])
        self.assertIn(str(HERE/'prepare_socket_abort_diagnostic.py'),command.call_args.args[2])

    def test_freeze_records_revision_and_run_without_add_run(self):
        _,inv,_,command,save=self.context('freeze')
        ctl.run_action('freeze')
        self.assertEqual(inv.call_count,2);command.assert_called_once();save.assert_called_once()
        self.assertIn('freeze',command.call_args.args[2]);self.assertNotIn('add-run',command.call_args.args[2])
        self.assertEqual({x.name for x in command.call_args.kwargs['outputs']},
                         {'snapshot.json','code.zip','revision-record.json','run-record.json'})

    def test_launch_exact_bound_checks_outputs_and_workspace_absence(self):
        _,inv,verify,command,_=self.context('launch')
        ctl.run_action('launch')
        verify.assert_called_once();inv.assert_called_once_with({'candidate':True},frozen=True)
        self.assertEqual(command.call_args.kwargs['absent'],[ctl.MANIFEST.parent/'records',ctl.RAW,ctl.WORKSPACE])
        self.assertIn(ctl.BOUND_TESTS,command.call_args.kwargs['inputs'])

    def test_bad_support_or_sources_prevents_every_action(self):
        for action in ('prepare','freeze','launch'):
            for failure in ('support','sources'):
                with self.subTest(action=action,failure=failure):
                    _,_,_,command,_=self.context(action,failure)
                    with self.assertRaises(ValueError):ctl.run_action(action)
                    command.assert_not_called()

    def test_unbound_or_failed_snapshot_checks_prevent_launch(self):
        _,_,verify,command,_=self.context('launch');verify.side_effect=ValueError('unbound')
        with self.assertRaises(ValueError):ctl.run_action('launch')
        command.assert_not_called()

    def test_replaced_full_check_commands_cannot_be_rebound(self):
        _,_,verify,command,_=self.context('launch');verify.return_value={'commands':['replacement']}
        with self.assertRaisesRegex(ValueError,'original checks033'):ctl.run_action('launch')
        command.assert_not_called()

    def test_changed_retained_inventory_prevents_launch(self):
        _,inv,_,command,_=self.context('launch');inv.return_value={'changed':True}
        with self.assertRaisesRegex(ValueError,'inventory changed'):ctl.run_action('launch')
        command.assert_not_called()

    def test_ambiguous_journal_is_not_retried(self):
        _,_,_,command,_=self.context('launch');command.side_effect=ValueError('Unresolved command intent')
        with self.assertRaisesRegex(ValueError,'Unresolved'):ctl.run_action('launch')
        command.assert_called_once()


if __name__ == '__main__':
    unittest.main()
