"""Mocked lifecycle/queue tests: no model, namespace, physics or submission."""
import ast
from contextlib import ExitStack, redirect_stdout
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import common
import launch
import run


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(redirect_stdout(io.StringIO()))
        for name, relative in [('MANIFEST', 'manifest.json'), ('SNAPSHOT', 'snapshot.json'),
                               ('RECORDS', 'records'), ('EVIDENCE', 'raw/orchestrator'),
                               ('HOST', 'raw/host'), ('WORKSPACE', 'workspace')]:
            self.stack.enter_context(patch.object(common, name, self.root / relative))
        self.args = SimpleNamespace(manifest=common.MANIFEST, snapshot=common.SNAPSHOT,
                                    evidence=common.EVIDENCE, host_evidence=common.HOST,
                                    workspace=common.WORKSPACE)

    def manifest(self):
        value = common.read(common.REFERENCE)
        value.update(run_id=common.RUN, framework_revision=common.REVISION,
                     qualification_stage=common.STAGE, outer_campaign_protocol=common.PROTOCOL,
                     model_turns_max=1, runtime_workspace=str(common.WORKSPACE),
                     runtime_input_files=common.required_inputs())
        return value

    def freeze_fixture(self):
        value = self.manifest(); common.save(common.MANIFEST, value)
        frozen = {'revision': common.REVISION, 'run_id': common.RUN,
                  'manifest_sha256': common.sha(common.MANIFEST),
                  'sources': {name: {'sha256': common.sha(common.REPO / name),
                                     'bytes': (common.REPO / name).stat().st_size}
                              for name in value['runtime_input_files']}}
        common.save(common.SNAPSHOT, frozen)
        return value, frozen

    def lifecycle(self, stage=None):
        stage = stage if stage is not None else {
            'injected_interruption': True, 'durable_retention_verified': True,
            'old_token_denied_after_retirement': True, 'all_namespaces_retired': True,
            'cleanup_clean': True}
        physical = SimpleNamespace(write_json=lambda path,value:common.save(path,value),
            operator=Mock(return_value={'owner':'robot','active_command':None}),
            transition=Mock(),run_invocation=Mock(return_value=stage))
        host = Mock(returncode=0)
        host.poll.return_value = None
        def start(*args, **kwargs):
            common.HOST.mkdir(parents=True)
            common.save(common.HOST / 'operator-endpoint.json', {'test':'endpoint'})
            return host
        self.stack.enter_context(patch.object(common, 'validate', return_value=({},{})))
        self.stack.enter_context(patch.object(common, 'load_physical', return_value=physical))
        warm=self.stack.enter_context(patch.object(run.subprocess,'run',
            return_value=SimpleNamespace(returncode=0,stdout='{"ready":true}')))
        spawn=self.stack.enter_context(patch.object(run.subprocess,'Popen',side_effect=start))
        return physical,host,warm,spawn

    def launch_fixture(self, *, ready=True, stopped=False, exited=False):
        common.save(common.MANIFEST, {});common.save(common.SNAPSHOT, {})
        validate=self.stack.enter_context(patch.object(common,'validate',return_value=({},{})))
        monitor=Mock(pid=1234);monitor.poll.return_value=1 if exited else None
        def start(*args,**kwargs):
            (common.RECORDS/'storage').mkdir()
            if ready:common.save(common.RECORDS/'storage/ready.json',{'ready':True})
            if stopped:common.save(common.RECORDS/'storage/admission-stop.json',{'stop':True})
            return monitor
        spawn=self.stack.enter_context(patch.object(launch.subprocess,'Popen',side_effect=start))
        submit=self.stack.enter_context(patch.object(launch.subprocess,'check_output',
            return_value='{"id":"test-only-job","state":"queued"}'))
        return validate,monitor,spawn,submit

    def test_exact_original_policy_with_one_invocation_is_accepted(self):
        common.validate_manifest(self.manifest())

    def test_changed_caps_model_bootstrap_fixture_and_unknown_fields_are_rejected(self):
        mutations = [('model','another-model'),('effort','low'),('bootstrap','different'),
            ('invocation_wall_cap_s',601),('model_turns_max',2),('model_turns_max',True),
            ('sim_cap_s',1501),('wall_cap_s',1801),('storage_cap_bytes',123),
            ('seed',174),('noise_seed',13),('action_request_budget',21),('observation_request_budget',51),
            ('physics_dt_s',.003),('activation_policy','altered'),('operator_only_fixture',{}),
            ('interruption_trigger','altered'),('program_route','altered'),('stage','scored'),
            ('prior_attempt','RCI001-C02-smoke-019'),('extra','unknown')]
        for key,value in mutations:
            with self.subTest(key=key,value=value):
                manifest=self.manifest();manifest[key]=value
                with self.assertRaisesRegex(ValueError,'manifest field|caps, fixture'):
                    common.validate_manifest(manifest)

    def test_missing_method_wrapper_or_storage_inputs_rejected(self):
        for target in [common.METHOD,common.HERE/'run.py',common.STORAGE_POLICY,common.STORAGE_BASELINE]:
            with self.subTest(target=target):
                value=self.manifest();value['runtime_input_files'].remove(target.relative_to(common.REPO).as_posix())
                with self.assertRaisesRegex(ValueError,'source inventory'):common.validate_manifest(value)

    def test_duplicate_or_escaping_input_rejected(self):
        for name in ['duplicate','../outside.py']:
            value=self.manifest()
            if name=='duplicate':value['runtime_input_files'].append(value['runtime_input_files'][0])
            else:value['runtime_input_files']=sorted([*value['runtime_input_files'],name])
            with self.assertRaisesRegex(ValueError,'source inventory|source path'):common.validate_manifest(value)

    def test_original_policy_basis_hash_is_required(self):
        with patch.object(common,'REFERENCE_SHA256','0'*64),self.assertRaisesRegex(ValueError,'policy basis'):
            common.validate_manifest(self.manifest())

    def test_frozen_archive_validator_is_called_with_exact_inputs(self):
        value,frozen=self.freeze_fixture();assessor=SimpleNamespace(frozen_problems=Mock(return_value=[]))
        with patch.object(common,'load',return_value=assessor):self.assertEqual(common.validate(common.MANIFEST,common.SNAPSHOT),(value,frozen))
        assessor.frozen_problems.assert_called_once_with(common.SNAPSHOT,frozen,common.REVISION)

    def test_bad_archive_is_rejected(self):
        self.freeze_fixture()
        with patch.object(common,'load',return_value=SimpleNamespace(frozen_problems=Mock(return_value=['drift']))), \
             self.assertRaisesRegex(ValueError,'source/archive'):
            common.validate(common.MANIFEST,common.SNAPSHOT)

    def test_snapshot_revision_run_manifest_hash_and_missing_source_rejected_before_import(self):
        for kind in ('revision','run_id','manifest_sha256','missing_source'):
            with self.subTest(kind=kind):
                for p in [common.MANIFEST,common.SNAPSHOT]:p.unlink(missing_ok=True)
                _,frozen=self.freeze_fixture()
                if kind=='missing_source':frozen['sources'].pop(next(iter(frozen['sources'])))
                else:frozen[kind]='wrong'
                common.SNAPSHOT.write_text(json.dumps(frozen),encoding='utf-8')
                with patch.object(common,'load') as load,self.assertRaises(ValueError):common.validate(common.MANIFEST,common.SNAPSHOT)
                load.assert_not_called()

    def test_changed_physical_runner_is_rejected(self):
        self.freeze_fixture()
        with patch.object(common,'PHYSICAL_SHA256','0'*64),self.assertRaisesRegex(ValueError,'physical runner'):
            common.validate(common.MANIFEST,common.SNAPSHOT)

    def test_wrong_output_or_existing_footprint_rejected(self):
        with self.assertRaisesRegex(ValueError,'output path'):common.output_paths(self.root/'wrong',common.HOST,common.WORKSPACE)
        common.WORKSPACE.mkdir()
        with self.assertRaisesRegex(ValueError,'Existing diagnostic'):common.output_paths(common.EVIDENCE,common.HOST,common.WORKSPACE)

    def test_runner_validates_before_any_host_or_output_creation(self):
        with patch.object(common,'validate',side_effect=ValueError('bad source')),patch.object(common,'load_physical') as load, \
             patch.object(run.subprocess,'Popen') as spawn,self.assertRaisesRegex(ValueError,'bad source'):
            run.execute(self.args)
        self.assertFalse(common.EVIDENCE.exists());self.assertFalse(common.WORKSPACE.exists())
        load.assert_not_called();spawn.assert_not_called()

    def test_successful_first_stage_still_never_resumes_or_claims_qualification(self):
        physical,host,warm,spawn=self.lifecycle()
        self.assertEqual(run.execute(self.args),0)
        physical.run_invocation.assert_called_once_with('interrupt',common.EVIDENCE/'interrupt',{'test':'endpoint'},common.WORKSPACE)
        physical.transition.assert_called_once_with({'test':'endpoint'},'stop',reason='Bounded readiness smoke complete')
        host.wait.assert_called_once_with(timeout=25)
        result=common.read(common.EVIDENCE/'sequence-result.json')
        self.assertEqual(len(result['stages']),1);self.assertFalse(result['resume_attempted'])
        self.assertFalse(result['qualifier_claim']);self.assertFalse(result['scorable']);self.assertEqual(result['task_outcome'],'unknown')
        self.assertEqual(warm.call_args.kwargs['timeout'],45)
        self.assertIn(str(common.CAMPAIGN/'harness/run_host.py'),spawn.call_args.args[0])

    def test_each_missing_interruption_gate_preserves_nonzero_and_stops_host(self):
        for key in ['injected_interruption','durable_retention_verified','old_token_denied_after_retirement','all_namespaces_retired','cleanup_clean']:
            with self.subTest(key=key),tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
                # Each case has an exclusive temporary footprint; no retry path.
                for name,relative in [('EVIDENCE','orchestrator'),('HOST','host'),('WORKSPACE','workspace')]:
                    stack.enter_context(patch.object(common,name,Path(tmp)/relative))
                args=SimpleNamespace(**vars(self.args));args.evidence=common.EVIDENCE;args.host_evidence=common.HOST;args.workspace=common.WORKSPACE
                stage={name:True for name in ['injected_interruption','durable_retention_verified','old_token_denied_after_retirement','all_namespaces_retired','cleanup_clean']};stage[key]=False
                physical,host,_,_=self.lifecycle(stage)
                self.assertEqual(run.execute(args),1);physical.run_invocation.assert_called_once();physical.transition.assert_called_once()
                result=common.read(common.EVIDENCE/'sequence-result.json');self.assertFalse(result['orchestrator_completed'])
                self.assertEqual(result['stages'][0][key],False)

    def test_transport_exception_preserved_and_host_stopped(self):
        physical,host,_,_=self.lifecycle();physical.run_invocation.side_effect=RuntimeError('declared test transport failure')
        self.assertEqual(run.execute(self.args),1);physical.transition.assert_called_once()
        self.assertEqual(common.read(common.EVIDENCE/'sequence-result.json')['error'],'declared test transport failure')

    def test_prewarm_failure_never_starts_host_or_model(self):
        physical,_,warm,spawn=self.lifecycle();warm.return_value=SimpleNamespace(returncode=1,stdout='')
        self.assertEqual(run.execute(self.args),1);spawn.assert_not_called();physical.run_invocation.assert_not_called()

    def test_host_exit_before_activation_never_starts_model(self):
        physical,host,_,_=self.lifecycle();host.poll.return_value=1;host.returncode=1
        self.assertEqual(run.execute(self.args),1);physical.run_invocation.assert_not_called()

    def test_host_cleanup_retains_original_wait_and_terminate_bounds(self):
        _,host,_,_=self.lifecycle();host.wait.side_effect=[subprocess.TimeoutExpired('test-host',25),1];host.returncode=1
        self.assertEqual(run.execute(self.args),1);host.terminate.assert_called_once()
        self.assertEqual([x.kwargs['timeout'] for x in host.wait.call_args_list],[25,10])
        self.assertTrue(common.read(common.EVIDENCE/'sequence-result.json')['forced_host_exit'])

    def test_runner_source_has_one_interrupt_call_no_other_invocation(self):
        tree=ast.parse((common.HERE/'run.py').read_text())
        calls=[node for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='run_invocation']
        self.assertEqual(len(calls),1);self.assertEqual(ast.literal_eval(calls[0].args[0]),'interrupt')

    def test_real_physical_import_keeps_all_late_dependency_paths_without_execution(self):
        code = '''import importlib,json,pathlib,sys
import common
physical=common.load_physical()
runtime=sys.modules['runtime']
expected={'gateway_policy':runtime.BOUNDARY/'gateway_policy.py',
          'transport_stderr':runtime.HERE/'transport_stderr.py',
          'retirement':runtime.BOUNDARY/'retirement.py'}
for name,path in expected.items():
 module=importlib.import_module(name)
 assert pathlib.Path(module.__file__).resolve()==path.resolve(),(name,module.__file__)
for path in [runtime.HERE,runtime.S9/'wsl',runtime.BOUNDARY,runtime.INTEGRATION/'host']:
 assert str(path) in sys.path,path
assert physical.run_invocation.__module__=='single_interrupt_physical'
print(json.dumps({'read_only_import':True,'late_dependencies':sorted(expected)}))
'''
        result=subprocess.run([sys.executable,'-X','utf8','-B','-c',code],cwd=common.HERE,
                              capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout),{'read_only_import':True,
            'late_dependencies':['gateway_policy','retirement','transport_stderr']})

    def test_launcher_submits_exact_argv_once_after_revalidation(self):
        validate,monitor,spawn,submit=self.launch_fixture()
        launch.launch(common.MANIFEST,common.SNAPSHOT)
        self.assertEqual(validate.call_count,2);submit.assert_called_once()
        argv=submit.call_args.args[0];self.assertEqual(argv[argv.index('--')+1:],common.runner_argv(common.MANIFEST,common.SNAPSHOT))
        self.assertEqual(common.read(common.RECORDS/'launch-intent.json')['argv'],common.runner_argv(common.MANIFEST,common.SNAPSHOT))
        self.assertEqual(common.read(common.RECORDS/'queue-submit.json')['id'],'test-only-job')

    def test_launcher_monitor_exit_or_stop_latch_blocks_even_with_ready_file(self):
        for stopped,exited in [(True,False),(False,True)]:
            with self.subTest(stopped=stopped,exited=exited),tempfile.TemporaryDirectory() as tmp, \
                 patch.object(common,'RECORDS',Path(tmp)/'records'):
                for p in [common.MANIFEST,common.SNAPSHOT]:p.unlink(missing_ok=True)
                _,_,_,submit=self.launch_fixture(stopped=stopped,exited=exited)
                with self.assertRaisesRegex(RuntimeError,'Storage monitor'):launch.launch(common.MANIFEST,common.SNAPSHOT)
                submit.assert_not_called();self.assertTrue((common.RECORDS/'launch-intent.json').exists())

    def test_launcher_source_drift_after_monitor_wait_blocks_queue(self):
        validate,_,_,submit=self.launch_fixture();validate.side_effect=[({},{}),ValueError('changed during wait')]
        with self.assertRaisesRegex(ValueError,'changed during wait'):launch.launch(common.MANIFEST,common.SNAPSHOT)
        submit.assert_not_called()

    def test_launcher_readiness_timeout_blocks_queue_and_preserves_intent(self):
        _,_,_,submit=self.launch_fixture(ready=False)
        with patch.object(launch.time,'monotonic',side_effect=[0,46]),self.assertRaisesRegex(RuntimeError,'readiness deadline'):
            launch.launch(common.MANIFEST,common.SNAPSHOT)
        submit.assert_not_called();self.assertTrue((common.RECORDS/'launch-intent.json').is_file())

    def test_ambiguous_submit_is_never_repeated(self):
        _,_,_,submit=self.launch_fixture();submit.side_effect=RuntimeError('queue response lost')
        with self.assertRaisesRegex(RuntimeError,'queue response lost'):launch.launch(common.MANIFEST,common.SNAPSHOT)
        with self.assertRaisesRegex(ValueError,'Existing intent'):launch.launch(common.MANIFEST,common.SNAPSHOT)
        submit.assert_called_once()


if __name__=='__main__':unittest.main()
