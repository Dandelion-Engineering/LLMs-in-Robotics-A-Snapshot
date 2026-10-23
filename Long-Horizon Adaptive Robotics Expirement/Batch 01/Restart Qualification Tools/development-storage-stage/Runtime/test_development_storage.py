"""Synthetic storage/authority checks; no physics, queue, WSL or real map writes."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import development_storage as storage
import development_batch as batch
import experiment
import record_attempt as recorder
import release_runner


class StorageFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.base=Path(self.temp.name).resolve()
        self.raw=self.base/'alternate-raw'
        self.rid='B01-dev-storage-fixture'

    def tearDown(self):self.temp.cleanup()


class DevelopmentStorageTests(StorageFixture):
    def test_exact_fresh_path_and_unsafe_names(self):
        assigned=storage.location(self.rid,self.raw,require_fresh=True)
        self.assertEqual(Path(assigned['evidence_dir']),self.raw/self.rid)
        self.assertFalse(self.raw.exists())
        for invalid in ('../escape','a/b','a\\b','D:escape','.', '..', 'CON', 'trailing.'):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                storage.location(invalid,self.raw)
        with self.assertRaises(ValueError):storage.location(self.rid,Path('relative-root'))
        file_root=self.base/'not-a-directory';file_root.write_text('synthetic',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'directory'):storage.location(self.rid,file_root)
        (self.raw/self.rid).mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'fresh'):storage.location(self.rid,self.raw,require_fresh=True)

    def test_registered_directory_cannot_be_retargeted(self):
        assigned=storage.location(self.rid,self.raw)
        self.assertEqual(storage.registered_location(self.rid,assigned),assigned)
        for field,value in (('evidence_dir',str(self.raw/'another-run')),('schema_version','unknown')):
            with self.subTest(field=field),self.assertRaises(ValueError):
                storage.registered_location(self.rid,{**assigned,field:value})

    def test_evaluation_keeps_exact_authority_and_refuses_development_override(self):
        seeds={'world_seed':2**40,'layout_seed':2**41,'noise_seed':2**42,'policy_seed':17}
        manifest={'run_id':'eval-synthetic','architecture':'A1','parts':3,'cap_s':12.,
                  'condition':'persistent','scenario':'nominal','seeds':seeds}
        context=release_runner.VerifiedEvaluationContext(self.base/'evaluation',json.dumps(manifest),'r'*64,'m'*64,
            'synthetic-queue','synthetic-time','{}',release_runner._AUTHORITY)
        kwargs=dict(kind='A1',n=3,cap=12.,condition='persistent',scenario='nominal',run_id='eval-synthetic',seeds=seeds)
        actual,authority=experiment.authorized_evidence_path('evaluation',context,**kwargs)
        self.assertEqual(actual,context.evidence_dir)
        self.assertEqual(authority['queue_job_id'],'synthetic-queue')
        with self.assertRaises(ValueError):experiment.authorized_evidence_path('evaluation',None,**kwargs)
        with self.assertRaises(release_runner.ReleaseError):
            experiment.authorized_evidence_path('evaluation',context,**{**kwargs,'cap':13.})
        with self.assertRaisesRegex(ValueError,'cannot override evaluation'):
            experiment.authorized_evidence_path('evaluation',context,development_raw_root=self.raw,**kwargs)
        self.assertFalse(self.raw.exists())

    def test_setup_failure_is_retained_at_assigned_root_with_identity(self):
        with patch.object(experiment,'ResourceSampler',side_effect=RuntimeError('synthetic startup failure')):
            with patch.object(experiment,'Cell',side_effect=AssertionError('No physics')):
                with contextlib.redirect_stdout(io.StringIO()):
                    result=experiment.run_episode(run_id=self.rid,development_raw_root=self.raw,cap=.01)
        assigned=storage.location(self.rid,self.raw)
        self.assertEqual(result['development_storage'],assigned)
        self.assertEqual(result['stage'],'development')
        self.assertEqual(result['execution_status'],'failed')
        self.assertTrue((self.raw/self.rid/'result.json').is_file())
        self.assertFalse((self.raw/self.rid/'manifest.json').exists())

    def test_cross_drive_reference_falls_back_to_absolute_local_path(self):
        source=self.base/'fixture.json';source.write_text('{}',encoding='utf-8')
        with patch('os.path.relpath',side_effect=ValueError('path is on another drive')):
            actual=recorder.ref('fixture',source)
        self.assertEqual(actual['uri'],source.as_posix())
        self.assertEqual(actual['sha256'],hashlib.sha256(source.read_bytes()).hexdigest())

    @unittest.skipUnless(os.name=='nt','Windows drive syntax')
    def test_d_drive_location_requires_no_directory_creation(self):
        assigned=storage.location(self.rid,Path('D:/CodexEvidence/synthetic-do-not-create'))
        self.assertEqual(Path(assigned['evidence_dir']).drive,'D:')


class RegistrationTests(StorageFixture):
    def setUp(self):
        super().setUp()
        self.project=self.base/'project';self.runtime=self.project/'experiment'/'Runtime'
        self.map=self.runtime.parent/'Architecture Map'
        (self.runtime/'vendor'/'panda').mkdir(parents=True)
        self.map.mkdir()
        (self.project/'requirements.txt').write_text('synthetic only\n',encoding='utf-8')
        (self.runtime/'vendor'/'panda'/'manifest.json').write_text('{}',encoding='utf-8')
        (self.runtime/'synthetic.py').write_text('# synthetic only\n',encoding='utf-8')
        self.data={'architecture':[{'id':'B01-C0'}],'revision':[],'run':[],'result':[]}
        self.patches=[patch.object(recorder,'HERE',self.runtime),patch.object(recorder,'MAP',self.map),
                      patch.object(recorder.am,'read_store',side_effect=lambda _: (self.data,{},[])),
                      patch.object(recorder.am,'main'),patch.object(recorder,'append',side_effect=self.append),
                      patch.object(storage,'DEFAULT_RAW_ROOT',self.base/'legacy-raw')]
        for item in self.patches:item.start()
        self.args=SimpleNamespace(run_id=self.rid,kind='baseline',parts=3,seed=0,policy_noise_seed=0,
                                  cap=1.,scenario='nominal',condition='persistent',development_raw_root=self.raw)

    def tearDown(self):
        for item in reversed(self.patches):item.stop()
        super().tearDown()

    def append(self,kind,record):self.data[kind].append(record)

    def prepare(self):
        with contextlib.redirect_stdout(io.StringIO()):recorder.prepare(self.args)
        return self.map/'releases'/self.rid/'manifest.json'

    def result(self,assigned,**changes):
        raw=Path(assigned['evidence_dir']);raw.mkdir(parents=True,exist_ok=True)
        value={'run_id':self.rid,'stage':'development','development_storage':assigned,'execution_status':'failed',
               'outcome':'failure','ended_at':'2000-01-01T00:00:00+00:00','termination_reason':'synthetic startup failure'}
        value.update(changes)
        (raw/'result.json').write_text(json.dumps(value),encoding='utf-8')
        return raw,value

    def test_registration_pins_location_and_command_before_raw_creation(self):
        path=self.prepare();manifest=json.loads(path.read_text(encoding='utf-8'))
        assigned=storage.location(self.rid,self.raw)
        self.assertEqual(manifest['development_storage'],assigned)
        self.assertFalse(Path(assigned['evidence_dir']).exists())
        command=self.data['run'][0]['condition_details']['planned_command']
        self.assertEqual(command[command.index('--development-raw-root')+1],str(self.raw))
        verified,legacy,reference=recorder.registered_storage(self.rid)
        self.assertEqual(verified,assigned);self.assertFalse(legacy)
        self.assertEqual(reference['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())

    def test_registration_cannot_be_changed_before_finish(self):
        path=self.prepare();path.write_text(path.read_text(encoding='utf-8')+' ',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'immutable map binding'):recorder.registered_storage(self.rid)

    def test_finish_uses_registered_location_and_retains_early_failure(self):
        self.prepare();assigned=storage.location(self.rid,self.raw)
        self.result(assigned)
        with contextlib.redirect_stdout(io.StringIO()):
            recorder.finish(SimpleNamespace(run_id=self.rid,queue_job_id='synthetic-queue'))
        record=self.data['result'][0]
        self.assertEqual(record['details']['development_storage'],assigned)
        self.assertTrue(record['details']['failed_attempt_retained'])
        self.assertFalse(record['details']['legacy_missing_raw_stage'])
        self.assertEqual((self.map/record['evidence'][0]['uri']).resolve(),self.raw/self.rid/'result.json')

    def test_finish_refuses_wrong_run_stage_and_storage(self):
        self.prepare();assigned=storage.location(self.rid,self.raw)
        for changes in ({'run_id':'other-run'},{'stage':'evaluation'},{'stage':None},{'development_storage':None}):
            self.result(assigned,**changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                recorder.finish(SimpleNamespace(run_id=self.rid,queue_job_id='synthetic-queue'))
        self.assertEqual(self.data['result'],[])

    def test_legacy_manifest_uses_default_root_and_explicit_missing_stage_note(self):
        path=self.prepare();manifest=json.loads(path.read_text(encoding='utf-8'));manifest.pop('development_storage')
        path.write_text(json.dumps(manifest),encoding='utf-8')
        # Build a distinct synthetic legacy registration, not an actual correction.
        self.data['run'][0]['frozen_refs']['protocol']['refs'][0]['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        assigned=storage.location(self.rid)
        raw,value=self.result(assigned)
        value.pop('development_storage');value.pop('stage')
        (raw/'result.json').write_text(json.dumps(value),encoding='utf-8')
        with contextlib.redirect_stdout(io.StringIO()):
            recorder.finish(SimpleNamespace(run_id=self.rid,queue_job_id='synthetic-queue'))
        self.assertEqual(self.data['result'][0]['details']['development_storage'],assigned)
        self.assertTrue(self.data['result'][0]['details']['legacy_missing_raw_stage'])
        with self.assertRaises(ValueError):
            recorder.verify_raw_identity({**value,'stage':'evaluation'},self.rid,assigned,True)


class BatchStorageTests(StorageFixture):
    def test_batch_passes_and_reads_its_pinned_alternate_root(self):
        row={'run_id':self.rid,'kind':'baseline','parts':3,'seed':0,'policy_noise_seed':0,
             'cap':1.,'scenario':'nominal','condition':'persistent'}
        plan=self.base/'plan.json';plan.write_text(json.dumps([row]),encoding='utf-8')
        output=self.base/'batch-output';assigned=storage.location(self.rid,self.raw)
        commands=[]
        def process(argv,**kwargs):
            commands.append(argv)
            root=Path(assigned['evidence_dir']);root.mkdir(parents=True)
            result={'run_id':self.rid,'stage':'development','development_storage':assigned,
                    'execution_status':'completed','outcome':'partial','failure_class':None}
            (root/'result.json').write_text(json.dumps(result),encoding='utf-8')
            return SimpleNamespace(pid=123,wait=lambda:0)
        with patch.object(recorder,'prepare') as prepare,patch.object(batch,'hashes',return_value={'synthetic.py':'a'*64}):
            with patch.object(batch.subprocess,'Popen',side_effect=process),contextlib.redirect_stdout(io.StringIO()):
                report=batch.run(plan,output,development_raw_root=self.raw)
        self.assertEqual(report['development_storage'],{self.rid:assigned})
        self.assertEqual(prepare.call_args.args[0].development_raw_root,self.raw)
        argv=commands[0];self.assertEqual(argv[argv.index('--development-raw-root')+1],str(self.raw))
        self.assertEqual(report['attempts'][0]['result_path'],str(self.raw/self.rid/'result.json'))
        self.assertEqual(report['not_started'],[])


if __name__=='__main__':unittest.main()
