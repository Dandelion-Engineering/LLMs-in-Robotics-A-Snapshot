"""Synthetic release-driver checks only: no GPU, physics, queue or map mutations."""
import contextlib
import copy
from dataclasses import dataclass
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock,patch
import zipfile

import protocol
import release_runner as runner


class QueueOwnershipTests(unittest.TestCase):
    """Synthetic PID metadata only; never submit, signal or mutate the queue."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.addCleanup(self.temp.cleanup)
        self.expected=self.root/'runtime'/'release_runner.py';self.expected.parent.mkdir()
        self.venv=self.root/'venv';self.venv.mkdir();(self.venv/'pyvenv.cfg').write_text('synthetic fixture')
        self.launcher=self.venv/'Scripts'/'python.exe';self.base=self.root/'Python312'/'python.exe'
        self.argv=[str(self.launcher),'-X','utf8','-B','runtime/release_runner.py','run','--limit','4']
        self.job={'id':'fixture-queue','state':'running','child_pid':200,'worker_pid':100,'argv':self.argv,
                  'cwd':str(self.root),'resolved_executable':str(self.launcher),'started_at':'2000-01-01T00:00:00+00:00'}
        self.metadata={200:{'pid':200,'parent_pid':100,'executable':str(self.launcher),'argv':self.argv.copy(),
                            'created_at':'2000-01-01T00:00:01+00:00'},
                       300:{'pid':300,'parent_pid':200,'executable':str(self.base),'argv':[str(self.base),*self.argv[1:]],
                            'created_at':'2000-01-01T00:00:02+00:00'}}

    @contextlib.contextmanager
    def identity(self,*,job=None,current=300,parent=200,metadata=None,actual_script=None,windows=True):
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(runner,'load',return_value={'jobs':[self.job if job is None else job]}))
            stack.enter_context(patch.object(runner.os,'getpid',return_value=current))
            stack.enter_context(patch.object(runner.os,'getppid',return_value=parent))
            stack.enter_context(patch.object(runner.sys,'argv',[str(actual_script or self.expected)]))
            stack.enter_context(patch.object(runner.sys,'platform','win32' if windows else 'linux'))
            stack.enter_context(patch.object(runner.sys,'prefix',str(self.venv)))
            stack.enter_context(patch.object(runner.sys,'base_prefix',str(self.base.parent)))
            stack.enter_context(patch.object(runner.sys,'executable',str(self.launcher)))
            stack.enter_context(patch.object(runner.sys,'_base_executable',str(self.base)))
            stack.enter_context(patch.object(runner.time,'sleep'))
            query=stack.enter_context(patch.object(runner,'windows_process_metadata',return_value=self.metadata if metadata is None else metadata))
            yield query

    def test_exact_queue_child_still_passes_without_process_query(self):
        with self.identity(current=200,parent=100) as query:
            self.assertEqual(runner.queued_job(self.expected),self.job);query.assert_not_called()

    def test_direct_windows_venv_launcher_child_passes(self):
        with self.identity() as query:
            self.assertEqual(runner.queued_job(self.expected),self.job);query.assert_called_once_with(300,200)

    def test_different_actual_entrypoint_is_rejected_even_for_exact_pid(self):
        with self.identity(current=200,actual_script=self.root/'wrapper.py') as query:
            with self.assertRaisesRegex(runner.ReleaseError,'sys.argv'):runner.queued_job(self.expected)
            query.assert_not_called()

    def test_expected_script_as_wrapper_argument_is_not_entrypoint(self):
        bad=copy.deepcopy(self.job);bad['argv']=[str(self.launcher),'wrapper.py',str(self.expected)]
        with self.identity(job=bad,current=200):
            with self.assertRaisesRegex(runner.ReleaseError,'entrypoint'):runner.queued_job(self.expected)

    def test_command_and_module_modes_cannot_smuggle_expected_script(self):
        for option in ('-c','-m'):
            with self.subTest(option=option):
                bad=copy.deepcopy(self.job);bad['argv']=[str(self.launcher),option,'wrapper',str(self.expected)]
                with self.identity(job=bad,current=200):
                    with self.assertRaisesRegex(runner.ReleaseError,'directly execute'):runner.queued_job(self.expected)

    def test_grandchild_and_nonwindows_parent_are_not_accepted(self):
        for options in ({'parent':250},{'windows':False}):
            with self.subTest(options=options),self.identity(**options) as query:
                with self.assertRaisesRegex(runner.ReleaseError,'verified direct'):runner.queued_job(self.expected)
                query.assert_not_called()

    def test_unrelated_parent_or_wrong_real_executable_or_command_fails(self):
        cases=[(300,'parent_pid',250),(200,'parent_pid',999),(300,'executable',str(self.launcher)),
               (200,'executable',str(self.base)),(200,'argv',[str(self.launcher),'unrelated.py']),
               (300,'argv',[str(self.base),*self.argv[1:],'unexpected'])]
        for pid,key,value in cases:
            with self.subTest(pid=pid,key=key):
                rows=copy.deepcopy(self.metadata);rows[pid][key]=value
                with self.identity(metadata=rows):
                    with self.assertRaises(runner.ReleaseError):runner.queued_job(self.expected)

    def test_recycled_parent_or_missing_process_creation_metadata_fails(self):
        for value in ('2000-01-01T00:00:03+00:00','1999-12-31T23:59:59+00:00','2000-01-01T00:00:01',None):
            with self.subTest(value=value):
                rows=copy.deepcopy(self.metadata);rows[200]['created_at']=value
                with self.identity(metadata=rows):
                    with self.assertRaisesRegex(runner.ReleaseError,'creation times'):runner.queued_job(self.expected)
        with self.identity(metadata={}):
            with self.assertRaises(runner.ReleaseError):runner.queued_job(self.expected)

    def test_other_venv_or_missing_venv_configuration_fails(self):
        bad=copy.deepcopy(self.job);bad['resolved_executable']=str(self.root/'other-venv'/'python.exe')
        with self.identity(job=bad):
            with self.assertRaisesRegex(runner.ReleaseError,'Queued executable'):runner.queued_job(self.expected)
        (self.venv/'pyvenv.cfg').unlink()
        with self.identity():
            with self.assertRaisesRegex(runner.ReleaseError,'identify a Windows venv'):runner.queued_job(self.expected)

    def test_script_resolution_uses_queue_cwd_and_supported_python_flags(self):
        self.assertEqual(runner.python_entrypoint(['python','-Xutf8','-W','error','-I','--','runtime/release_runner.py'],self.root),self.expected)
        with self.assertRaises(runner.ReleaseError):runner.python_entrypoint(['python','-X'],self.root)

    @unittest.skipUnless(os.name=='nt','Native Windows command parser')
    def test_native_windows_argument_roundtrip(self):
        argv=[str(self.launcher),'-X','utf8',str(self.expected),'argument with spaces','a"b','path\\tail\\']
        self.assertEqual(runner.windows_command_argv(subprocess.list2cmdline(argv)),argv)

    @unittest.skipUnless(os.name=='nt','Windows CIM command construction')
    def test_metadata_query_is_bounded_hidden_readonly_and_fails_closed(self):
        reply=SimpleNamespace(returncode=0,stdout='[]')
        with patch.object(runner.subprocess,'run',return_value=reply) as query:
            self.assertEqual(runner.windows_process_metadata(300,200),{})
            args,kwargs=query.call_args
            self.assertIn('Get-CimInstance Win32_Process',args[0][-1])
            self.assertIn('ProcessId = 300 OR ProcessId = 200',args[0][-1])
            self.assertEqual(kwargs['timeout'],8);self.assertFalse(kwargs['shell'])
            self.assertEqual(kwargs['creationflags'],subprocess.CREATE_NO_WINDOW)
        with patch.object(runner.subprocess,'run',side_effect=subprocess.TimeoutExpired('fixture',8)):
            with self.assertRaisesRegex(runner.ReleaseError,'metadata'):runner.windows_process_metadata(300,200)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.job={'id':'unit-queue-job','state':'running','child_pid':123,'argv':['python','release_runner.py']}

    def write(self,path,value):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value,sort_keys=True),encoding='utf-8');return path

    def ref(self,path):return {'path':str(path),'sha256':runner.digest(path)}

    def release(self,ready=True):
        evidence=self.root/'synthetic-readiness.txt';evidence.write_text('UNIT FIXTURE; NOT READINESS')
        freeze={'release_id':'unit-release','frozen_at':'2000-01-01T00:00:00+00:00',
                'code_sha256':'1'*64,'environment_sha256':'2'*64,'model_sha256':'3'*64,
                'protocol_sha256':protocol.protocol_sha256(),'selection_criteria':'unit fixture','maximum_retries':0}
        freeze_path=self.write(self.root/'freeze.json',freeze)
        ready_path=self.write(self.root/'readiness.json',{'release_id':'unit-release','freeze_sha256':runner.digest(freeze_path),
            'scored_ready':True,'gates':{gate:True for gate in protocol.REQUIRED_GATES},'evidence_refs':[self.ref(evidence)]})
        root=self.root/'release';sequence=itertools.count(1)
        with patch.object(protocol,'_entropy',side_effect=lambda bits:next(sequence)):
            protocol.create_release(root,freeze_path,ready_path)
        if not ready:
            value=runner.load(ready_path);value['scored_ready']=False;self.write(ready_path,value)
            release=runner.load(root/'release.json');release['readiness']=self.ref(ready_path);self.write(root/'release.json',release)
        return root

    def verified(self,root):
        with patch.object(runner,'verify_artifacts',return_value={'model_config':{},'test_fixture':True}):return runner.verify_release(root)

    def context(self,verified,manifest):
        ref=next(r for r in verified['release']['manifest_refs'] if r['run_id']==manifest['run_id'])
        return runner.VerifiedEvaluationContext(verified['root'],protocol.canonical(manifest).decode(),verified['release_sha256'],ref['sha256'],self.job['id'],runner.utc(),'{"model_config":{}}',runner._AUTHORITY)

    def run_fake(self,root,*,limit=2,behavior=None):
        verified=self.verified(root);registered=[];executed=[]
        def register(context):registered.append(context.manifest['run_id']);return 'fixture-frozen-revision'
        def execute(context,episode):
            m=context.manifest;executed.append(m['run_id'])
            self.assertIn(m['run_id'],registered)
            self.assertTrue((context.evidence_dir.parent/'started.json').is_file())
            if behavior:return behavior(context)
            context.evidence_dir.mkdir()
            result={'run_id':m['run_id'],'stage':'evaluation','execution_status':'completed','validity':'valid',
                    'outcome':'failure','ended_at':runner.utc(),'termination_reason':'time_cap'}
            self.write(context.evidence_dir/'result.json',result);return result
        with patch.object(runner,'queued_job',return_value=self.job),patch.object(runner,'verify_release',return_value=verified),patch.object(runner,'require_supervisor_hook',return_value=MagicMock()),patch.object(runner,'authorize_evaluation',side_effect=lambda m,r:self.context(verified,m)),patch.object(runner,'register_attempt',side_effect=register),patch.object(runner,'execute_episode',side_effect=execute):
            result=runner.run_batch(root,limit=limit)
        return result,verified,registered,executed

    def test_readiness_false_stops_before_artifact_hashes(self):
        root=self.release(ready=False)
        with patch.object(runner,'verify_artifacts',side_effect=AssertionError('must not hash model')):
            with self.assertRaisesRegex(protocol.ProtocolError,'scored_ready'):runner.verify_release(root)

    def test_changed_manifest_or_missing_seed_is_rejected(self):
        root=self.release();release=runner.load(root/'release.json');path=root/release['manifest_refs'][0]['path']
        value=runner.load(path);value['cap_s']=1;self.write(path,value)
        with self.assertRaisesRegex(protocol.ProtocolError,'changed'):self.verified(root)

    def test_wrong_artifact_binding_is_rejected(self):
        root=self.release();release=runner.load(root/'release.json');ref=release['manifest_refs'][0];path=root/ref['path']
        value=runner.load(path);value['artifact_hashes']['code_sha256']='0'*64;self.write(path,value)
        ref['sha256']=runner.digest(path);self.write(root/'release.json',release)
        with self.assertRaisesRegex(runner.ReleaseError,'bound'):self.verified(root)

    def test_context_preserves_all_seed_roles_and_exact_arguments(self):
        root=self.release();verified=self.verified(root);m=verified['manifests'][0];context=self.context(verified,m)
        kwargs=context.episode_kwargs();kwargs.pop('evaluation_context')
        self.assertEqual({k:kwargs[k] for k in m['seeds']},m['seeds'])
        self.assertEqual(context.assert_episode(**kwargs),context.evidence_dir)
        kwargs['noise_seed']+=1
        with self.assertRaisesRegex(runner.ReleaseError,'exact'):context.assert_episode(**kwargs)
        forged=runner.VerifiedEvaluationContext(root,context.manifest_json,'a','b','c','d','{}')
        with self.assertRaisesRegex(runner.ReleaseError,'not issued'):forged.assert_episode(**kwargs)

    def test_context_rejects_dirty_episode_directory(self):
        root=self.release();verified=self.verified(root);context=self.context(verified,verified['manifests'][0]);context.evidence_dir.mkdir(parents=True)
        kwargs=context.episode_kwargs();kwargs.pop('evaluation_context')
        with self.assertRaisesRegex(runner.ReleaseError,'not fresh'):context.assert_episode(**kwargs)

    def test_current_development_supervisor_is_not_silently_enabled(self):
        fake=SimpleNamespace(run_episode=lambda **kwargs:None)
        with patch.dict(sys.modules,{'experiment':fake}):
            with self.assertRaisesRegex(runner.ReleaseError,'hook'):runner.require_supervisor_hook()

    def test_no_implicit_retry_after_interruption(self):
        root=self.release();verified=self.verified(root);m=verified['manifests'][0]
        (root/'attempts'/m['run_id']).mkdir(parents=True)
        with self.assertRaisesRegex(runner.ReleaseError,'Interrupted'):runner.select_runs(verified,None,4)

    def test_explicit_subset_is_bounded_and_keeps_frozen_schedule(self):
        root=self.release();verified=self.verified(root);ordered=sorted(verified['manifests'],key=lambda m:m['scheduled_index'])
        selected=runner.select_runs(verified,[ordered[2]['run_id'],ordered[0]['run_id']],2)
        self.assertEqual([m['scheduled_index'] for m in selected],[1,3])
        with self.assertRaises(runner.ReleaseError):runner.select_runs(verified,[m['run_id'] for m in ordered[:5]],4)

    def test_sequential_attempts_are_registered_first_and_all_failures_retained(self):
        root=self.release();result,verified,registered,executed=self.run_fake(root)
        self.assertEqual(registered,executed);self.assertEqual(len(executed),2)
        self.assertFalse(result['map_results_applied'])
        for run_id in executed:
            terminal=runner.load(root/'attempts'/run_id/'terminal.json')
            self.assertEqual(terminal['result']['outcome'],'failure')
            self.assertFalse(terminal['official_queue_completion_verified'])
        with self.assertRaisesRegex(runner.ReleaseError,'official queue'):runner.select_runs(verified,None,1)
        self.write(root/'batches'/self.job['id']/'finalized.json',{'fixture_verified':True})
        with self.assertRaisesRegex(runner.ReleaseError,'retries'):runner.select_runs(verified,[executed[0]],1)

    def test_infrastructure_exception_retained_and_remaining_runs_not_launched(self):
        root=self.release()
        def fail(context):raise RuntimeError('fixture model startup failure')
        result,verified,registered,executed=self.run_fake(root,behavior=fail)
        self.assertEqual(len(executed),1);self.assertIsNotNone(result['stop_reason'])
        terminal=runner.load(root/'attempts'/executed[0]/'terminal.json')
        self.assertTrue(terminal['result']['infrastructure_invalid'])
        self.assertIsNone(terminal['result']['wall_duration_s'])
        self.write(root/'batches'/self.job['id']/'finalized.json',{'fixture_verified':True})
        with self.assertRaisesRegex(runner.ReleaseError,'continuation review'):runner.select_runs(verified,None,1)

    def continuation_fixture(self):
        root=self.release()
        def fail(context):raise RuntimeError('fixture transient host incident')
        result,verified,registered,executed=self.run_fake(root,behavior=fail)
        self.write(root/'batches'/self.job['id']/'finalized.json',{'fixture_verified':True})
        run_id=executed[0];terminal=root/'attempts'/run_id/'terminal.json'
        manifest=next(m for m in verified['manifests'] if m['run_id']==run_id)
        review={'review_id':'unit-review-1','reviewer':'synthetic unit reviewer','rationale':'Synthetic isolated timing incident only',
            'classification':'isolated_host_timing','continuation_scope':'all_original_unattempted','retains_original_results':True,
            'exclude_affected_blocks_from_primary':True,'no_source_readiness_or_evaluator_integrity_breach':True,'automatic_retries':0,
            'terminal_refs':[{**self.ref(terminal),'run_id':run_id}], 'evidence_refs':[self.ref(terminal)],
            'excluded_paired_block_ids':[manifest['paired_block_id']]}
        return root,verified,manifest,review

    def test_review_allows_untouched_members_of_excluded_block_without_retry(self):
        root,verified,manifest,review=self.continuation_fixture();path=root/'attempts'/manifest['run_id']/'terminal.json';before=path.read_bytes()
        runner.record_review(root,review)
        state=runner.continuation_state(verified)
        self.assertEqual(state['excluded_paired_block_ids'],[manifest['paired_block_id']])
        remaining=next(m for m in verified['manifests'] if m['paired_block_id']==manifest['paired_block_id'] and m['run_id']!=manifest['run_id'])
        self.assertEqual(runner.select_runs(verified,[remaining['run_id']],1)[0]['run_id'],remaining['run_id'])
        self.assertEqual(path.read_bytes(),before)
        with self.assertRaisesRegex(runner.ReleaseError,'retries'):runner.select_runs(verified,[manifest['run_id']],1)
        self.assertEqual(len(verified['manifests']),264)

    def test_review_cannot_drop_block_exclusion_or_duplicate_review(self):
        root,verified,manifest,review=self.continuation_fixture();bad=copy.deepcopy(review);bad['excluded_paired_block_ids']=[]
        with self.assertRaisesRegex(runner.ReleaseError,'whole affected'):runner.record_review(root,bad)
        runner.record_review(root,review)
        with self.assertRaisesRegex(runner.ReleaseError,'already'):runner.record_review(root,review)

    def test_recorded_integrity_breach_cannot_be_waived(self):
        root,verified,manifest,review=self.continuation_fixture();path=root/'attempts'/manifest['run_id']/'terminal.json'
        terminal=runner.load(path);terminal['integrity_breach']=True;self.write(path,terminal)
        review['terminal_refs'][0]['sha256']=runner.digest(path);review['evidence_refs'][0]['sha256']=runner.digest(path)
        with self.assertRaisesRegex(runner.IntegrityError,'cannot be waived'):runner.record_review(root,review)
        with self.assertRaisesRegex(runner.IntegrityError,'blocks'):runner.select_runs(verified,None,1)

    def test_post_run_hash_verification_failure_is_retained_as_integrity_breach(self):
        root=self.release();verified=self.verified(root)
        with patch.object(runner,'queued_job',return_value=self.job),patch.object(runner,'verify_release',side_effect=[verified,runner.ReleaseError('changed source')]),patch.object(runner,'require_supervisor_hook',return_value=MagicMock()),patch.object(runner,'authorize_evaluation',side_effect=lambda m,r:self.context(verified,m)),patch.object(runner,'register_attempt',return_value='unit-revision'),patch.object(runner,'execute_episode',side_effect=RuntimeError('fixture ordinary runtime error')):
            result=runner.run_batch(root,limit=1)
        run_id=sorted(verified['manifests'],key=lambda m:m['scheduled_index'])[0]['run_id']
        terminal=runner.load(root/'attempts'/run_id/'terminal.json')
        self.assertFalse(terminal['post_run_integrity']['passed']);self.assertTrue(terminal['integrity_breach'])
        self.assertIsNotNone(result['stop_reason'])

    def test_fresh_model_context_for_each_llm_episode_and_cleanup_on_failure(self):
        root=self.release();verified=self.verified(root);manifests=[m for m in verified['manifests'] if m['architecture']=='A1'][:2]
        class FakeModel:
            instances=[]
            def __init__(self,*args,**kwargs):self.closed=False;self.instances.append(self)
            def __enter__(self):return self
            def __exit__(self,*args):self.closed=True
        module=SimpleNamespace(LocalModel=FakeModel,ModelConfig=lambda **kwargs:kwargs)
        def episode(**kwargs):raise RuntimeError('fixture episode')
        with patch.dict(sys.modules,{'model_runtime':module}):
            for m in manifests:
                with self.assertRaises(RuntimeError):runner.execute_episode(self.context(verified,m),episode)
        self.assertEqual(len(FakeModel.instances),2);self.assertTrue(all(m.closed for m in FakeModel.instances))

    def test_queue_receipt_must_be_successful_and_same_job(self):
        receipt={'id':'unit-queue-job','state':'succeeded','exit_status':0,'child_pid':123,'started_at':'start','ended_at':'end','argv':['test'],'cwd':'test'}
        path=self.write(self.root/'status.json',receipt);state=self.write(self.root/'state.json',{'jobs':[receipt]})
        with patch.object(runner,'QUEUE_STATE',state):
            self.assertEqual(runner.verify_queue_receipt('unit-queue-job',path),receipt)
            with self.assertRaises(runner.ReleaseError):runner.verify_queue_receipt('other-job',path)
            receipt['state']='failed';self.write(path,receipt)
            with self.assertRaises(runner.ReleaseError):runner.verify_queue_receipt('unit-queue-job',path)

    def test_atomic_journal_cannot_overwrite_attempt(self):
        path=self.root/'journal.json';runner.write_once(path,{'state':'started'})
        with self.assertRaises(FileExistsError):runner.write_once(path,{'state':'new attempt'})
        self.assertEqual(runner.load(path),{'state':'started'})

    def test_finalization_checks_terminal_hash_before_map_write(self):
        root=self.release();result,verified,registered,executed=self.run_fake(root,limit=1)
        terminal=root/'attempts'/executed[0]/'terminal.json';value=runner.load(terminal);value['result']['outcome']='success';self.write(terminal,value)
        fake_records=SimpleNamespace(am=SimpleNamespace(main=MagicMock(return_value=0)))
        with patch.object(runner,'verify_queue_receipt',return_value={'id':self.job['id'],'state':'succeeded','exit_status':0}),patch.object(runner,'map_reference',return_value={}),patch.object(runner,'append_map_result') as append,patch.dict(sys.modules,{'record_attempt':fake_records}):
            with self.assertRaisesRegex(runner.ReleaseError,'changed'):runner.finalize(root,self.job['id'],self.root/'unused.json')
        append.assert_not_called()

    def test_successful_finalization_is_separate_from_execution(self):
        root=self.release();result,verified,registered,executed=self.run_fake(root,limit=1)
        fake_records=SimpleNamespace(am=SimpleNamespace(main=MagicMock(return_value=0)))
        with patch.object(runner,'verify_queue_receipt',return_value={'id':self.job['id'],'state':'succeeded','exit_status':0}),patch.object(runner,'map_reference',return_value={}),patch.object(runner,'append_map_result') as append,patch.dict(sys.modules,{'record_attempt':fake_records}):
            finished=runner.finalize(root,self.job['id'],self.root/'unused.json')
        self.assertTrue(finished['official_queue_completion_verified']);append.assert_called_once()
        self.assertTrue((root/'batches'/self.job['id']/'finalized.json').is_file())


class ArtifactTests(unittest.TestCase):
    """Tiny installed-asset fixtures; no real weight hashing or environment probes."""
    setUp=RunnerTests.setUp
    write=RunnerTests.write
    ref=RunnerTests.ref
    def test_all_frozen_source_environment_and_model_files_checked(self):
        runtime=self.root/'Runtime';runtime.mkdir();source=runtime/'one.py';source.write_text('fixture = True\n')
        bundle=self.root/'runtime.zip'
        with zipfile.ZipFile(bundle,'w') as archive:archive.write(source,source.name)
        vendor=runtime/'vendor'/'model';vendor.mkdir(parents=True)
        weight=vendor/'fixture.gguf';weight.write_bytes(b'unit fixture weight')
        binary=vendor/'server.exe';binary.write_bytes(b'unit fixture executable')
        assets=self.write(vendor/'asset_manifest.json',{'installed_files':[{'path':'server.exe','sha256':runner.digest(binary)}]})
        environment_file=self.root/'requirements.txt';environment_file.write_text('SYNTHETIC')
        identity={'python':'fixture','dependencies':{'numpy':'fixture','mujoco':'fixture'}}
        @dataclass(frozen=True)
        class Config:context_tokens:int=123
        model_identity={'identity':'fixture'}
        code=self.write(self.root/'code.json',{'files':[self.ref(source)],'runtime_root':str(runtime),'bundle':self.ref(bundle)})
        env=self.write(self.root/'environment.json',{'files':[self.ref(environment_file)],'runtime_identity':identity,
                    'probes':[{'name':name} for name in ('candidate_python','candidate_isolation','gpu_driver')]})
        model=self.write(self.root/'model.json',{'files':[self.ref(assets),self.ref(weight),self.ref(binary)],'asset_manifest':self.ref(assets),
                    'identity':model_identity,'config':{'context_tokens':123}})
        freeze={'artifacts':{role:self.ref(path) for role,path in (('code',code),('environment',env),('model',model))},
                'code_sha256':runner.digest(code),'environment_sha256':runner.digest(env),'model_sha256':runner.digest(model)}
        modules={'model_runtime':SimpleNamespace(LocalModel=lambda config:SimpleNamespace(identity=model_identity),ModelConfig=Config),
                 'model_setup':SimpleNamespace(VENDOR=vendor,MODEL_FILE=weight.name,MODEL_SHA256=runner.digest(weight))}
        with patch.object(runner,'HERE',runtime),patch.object(runner,'environment_identity',return_value=identity),patch.object(runner,'run_probe') as probe,patch.dict(sys.modules,modules):
            verified=runner.verify_artifacts(freeze,self.root/'freeze.json')
            self.assertEqual(verified['model_identity'],model_identity);self.assertEqual(probe.call_count,3)
            source.write_text('changed = True\n')
            with self.assertRaisesRegex(runner.ReleaseError,'changed'):runner.verify_artifacts(freeze,self.root/'freeze.json')


if __name__=='__main__':unittest.main()
