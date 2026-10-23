"""Small synthetic artifact fixtures; no queue, real hashing/probes or inference."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import freeze_artifacts as prep
import release_runner as runner


class ArtifactPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.addCleanup(self.temp.cleanup)
        self.runtime=self.root/'project'/'experiment'/'Runtime';self.runtime.mkdir(parents=True)
        (self.runtime/'protocol.py').write_text('# synthetic protocol fixture\n')
        (self.runtime/'example.py').write_text('# synthetic candidate fixture\n')
        maps=self.runtime.parent/'Architecture Map';maps.mkdir();(maps/'map.py').write_text('# synthetic registrar fixture\n')
        (self.runtime.parents[1]/'requirements.txt').write_text('synthetic-dependencies-only\n')
        self.panda=self.runtime/'vendor'/'panda';self.panda.mkdir(parents=True)
        self.panda_file=self.panda/'robot.xml';self.panda_file.write_text('<synthetic/>')
        self.write(self.panda/'manifest.json',{'files':[{'path':'robot.xml','sha256':runner.digest(self.panda_file)}]})
        self.model=self.runtime/'vendor'/'model';self.model.mkdir(parents=True)
        self.weight=self.model/'future-model-Q4.gguf';self.weight.write_bytes(b'synthetic future model bytes')
        binary=self.model/'server.exe';binary.write_bytes(b'synthetic binary');license=self.model/'LICENSE.txt';license.write_text('synthetic terms')
        self.write(self.model/'asset_manifest.json',{'model_file':self.weight.name,'model_sha256':runner.digest(self.weight),
            'installed_files':[{'path':binary.name,'sha256':runner.digest(binary)}],
            'license_files':[{'path':license.name,'sha256':runner.digest(license)}]})
        self.spec=self.write(self.root/'probes.json',{'probes':[{'name':name,'argv':['fixture-read-only'], 'timeout_s':1} for name in ('candidate_python','candidate_isolation','gpu_driver')]})
        @dataclass(frozen=True)
        class Config:
            context_tokens:int=123
            threads:int=3
        self.modules={'model_runtime':SimpleNamespace(ModelConfig=Config,LocalModel=lambda config:SimpleNamespace(identity={'model':'future-fixture','threads':config.threads})),
                      'model_setup':SimpleNamespace(VENDOR=self.model,MODEL_FILE=self.weight.name,MODEL_SHA256=runner.digest(self.weight))}

    def write(self,path,value):path.write_text(json.dumps(value),encoding='utf-8');return path

    def call(self,output=None):
        with patch.object(prep,'HERE',self.runtime),patch.object(runner,'queued_job',return_value={'id':'synthetic-queue'}),patch.object(runner,'environment_identity',return_value={'python':'fixture','dependencies':{'numpy':'fixture','mujoco':'fixture'}}),patch.object(prep,'capture_probe',side_effect=lambda spec:{**spec,'stdout_sha256':'1'*64,'stdout_bytes':1}),patch.object(runner,'verify_artifacts') as verify,patch.dict(sys.modules,self.modules):
            result=prep.prepare(output or self.root/'artifacts',probe_spec=self.spec)
        return result,verify

    def test_current_model_and_effective_config_are_derived_without_ready_freeze(self):
        result,verify=self.call();output=Path(result['output_dir'])
        model=runner.load(output/'model.json');prepared=runner.load(output/'prepared-artifacts.json')
        self.assertEqual(model['config'],{'context_tokens':123,'threads':3})
        self.assertIn(str(self.weight.resolve()),[ref['path'] for ref in model['files']])
        self.assertEqual(model['identity']['model'],'future-fixture')
        self.assertFalse(prepared['scored_ready']);self.assertFalse(prepared['freeze_manifest_created']);self.assertFalse(prepared['held_out_seeds_created'])
        self.assertNotIn('release_id',prepared);self.assertNotIn('selection_criteria',prepared)
        self.assertFalse((output/'freeze.json').exists());self.assertFalse((output/'runs').exists())
        verify.assert_called_once()

    def test_source_zip_and_panda_requirements_are_hashed(self):
        result,_=self.call();output=Path(result['output_dir']);code=runner.load(output/'code.json');environment=runner.load(output/'environment.json')
        self.assertEqual(code['bundle']['sha256'],runner.digest(output/'runtime.zip'))
        self.assertEqual(len([ref for ref in code['files'] if Path(ref['path']).parent==self.runtime]),2)
        self.assertIn(str(self.panda_file.resolve()),[ref['path'] for ref in environment['files']])
        self.assertIn(str((self.runtime.parents[1]/'requirements.txt').resolve()),[ref['path'] for ref in environment['files']])

    def test_unqueued_call_stops_before_hashing_or_writes(self):
        output=self.root/'artifacts'
        with patch.object(runner,'queued_job',side_effect=runner.ReleaseError('not queued')),patch.object(prep,'file_ref',side_effect=AssertionError('must not hash')):
            with self.assertRaisesRegex(runner.ReleaseError,'not queued'):prep.prepare(output,probe_spec=self.spec)
        self.assertFalse(output.exists())

    def test_changed_pin_retains_partial_attempt_and_cannot_overwrite(self):
        self.panda_file.write_text('<changed/>')
        with self.assertRaisesRegex(runner.IntegrityError,'Pinned'):self.call()
        self.assertTrue((self.root/'artifacts'/'started.json').exists())
        with self.assertRaisesRegex(runner.ReleaseError,'already exists'):self.call()

    def test_asset_path_escape_is_rejected(self):
        outside=self.root/'outside.bin';outside.write_bytes(b'outside')
        manifest=self.panda/'escape.json';self.write(manifest,{'files':[{'path':str(outside),'sha256':runner.digest(outside)}]})
        with self.assertRaisesRegex(runner.IntegrityError,'escapes'):prep.asset_refs(self.panda,manifest,('files',))

    def test_probe_identity_output_hashed_without_copying_body(self):
        reply=SimpleNamespace(returncode=0,stdout=b'actual fixture identity',stderr=b'')
        with patch.object(prep.subprocess,'run',return_value=reply) as run:
            result=prep.capture_probe({'name':'candidate_python','argv':['fixture'], 'timeout_s':2})
        self.assertEqual(result['stdout_sha256'],hashlib.sha256(reply.stdout).hexdigest())
        self.assertNotIn('actual fixture identity',json.dumps(result))
        self.assertFalse(run.call_args.kwargs['shell'])

    def test_unbounded_or_failed_probe_is_refused(self):
        with self.assertRaises(runner.ReleaseError):prep.capture_probe({'name':'fixture','argv':['fixture'],'timeout_s':31})
        with patch.object(prep.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout=b'',stderr=b'private log')):
            with self.assertRaisesRegex(runner.ReleaseError,'Identity probe failed'):prep.capture_probe({'name':'fixture','argv':['fixture'],'timeout_s':1})


if __name__=='__main__':unittest.main()
