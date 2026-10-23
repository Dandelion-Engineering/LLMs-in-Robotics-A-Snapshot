"""In-memory proposal checks. No Runtime import, queue call or model compile."""
import ast
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
import types
import unittest
from unittest.mock import patch

import calibration_loader
from build_loader_patch import proposed_files
from test_calibration_loader import HERE, write_fixture


def node(source, name):
    return next(value for value in ast.walk(ast.parse(source)) if isinstance(value,(ast.FunctionDef,ast.ClassDef)) and value.name==name)


def execute_node(source, name, namespace):
    exec(compile(ast.Module(body=[node(source,name)],type_ignores=[]),name,'exec'),namespace)


class LoaderPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.original,cls.generated=proposed_files()

    def test_all_proposals_compile_and_candidate_transport_functions_are_unchanged(self):
        for name,source in self.generated.items():compile(source,name,'exec')
        for name in ('public_packet','dispatch_candidate','restart_worker'):
            self.assertEqual(ast.dump(node(self.original['experiment.py'],name)),ast.dump(node(self.generated['experiment.py'],name)))

    def test_preseed_gate_loads_and_rejects_tampered_protected_evidence(self):
        with TemporaryDirectory(dir=HERE) as directory:
            freeze,path,artifact,_=write_fixture(Path(directory))
            freeze.update(release_id='synthetic',code_sha256='a'*64,environment_sha256='b'*64,model_sha256='c'*64,
                protocol_sha256='d'*64,selection_criteria='synthetic test',maximum_retries=0)
            path.write_text(json.dumps(freeze),encoding='utf-8')
            hashfile=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
            ready={'scored_ready':True,'release_id':'synthetic','freeze_sha256':hashfile(path),
                   'gates':{'existing_gate':True},'evidence_refs':[{'path':artifact.name,'sha256':hashfile(artifact)}]}
            ready_path=Path(directory)/'ready.json';ready_path.write_text(json.dumps(ready),encoding='utf-8')
            namespace={'_load':lambda p:json.loads(Path(p).read_text(encoding='utf-8')),'Path':Path,'datetime':datetime,
                'RELEASE_RE':re.compile(r'.+'),'HASH_RE':re.compile(r'[a-f0-9]{64}'),'protocol_sha256':lambda:'d'*64,
                'sha256_file':hashfile,'ProtocolError':ValueError,'REQUIRED_GATES':['existing_gate']}
            execute_node(self.generated['protocol.py'],'validate_release_gates',namespace)
            with patch.dict(sys.modules,{'restart_calibration_loader':calibration_loader}):
                self.assertEqual(namespace['validate_release_gates'](path,ready_path)[0],freeze)
                # Keep ordinary readiness evidence valid, then corrupt only a qualification expectation.
                freeze['restart_qualification']['class_spec_sha256']='f'*64
                path.write_text(json.dumps(freeze),encoding='utf-8')
                ready['freeze_sha256']=hashfile(path);ready_path.write_text(json.dumps(ready),encoding='utf-8')
                with self.assertRaisesRegex(ValueError,'canonical class'):namespace['validate_release_gates'](path,ready_path)

    def test_verified_evaluation_context_copies_data_and_rejects_forgery(self):
        authority=object();namespace={'dataclass':dataclass,'field':field,'Path':Path,'json':json,
                                    '_AUTHORITY':authority,'ReleaseError':ValueError}
        execute_node(self.generated['release_runner.py'],'VerifiedEvaluationContext',namespace)
        context_type=namespace['VerifiedEvaluationContext']
        args=(HERE,'{}','a'*64,'b'*64,'synthetic-job','2020-01-03T00:00:00Z',json.dumps({'restart_qualification':{'identity':'synthetic'}}))
        context=context_type(*args,_authority=authority);value=context.restart_qualification
        value['identity']='changed'
        self.assertEqual(context.restart_qualification,{'identity':'synthetic'})
        with self.assertRaises(ValueError):_ = context_type(*args).restart_qualification

    def test_release_reverification_serializes_independently_hashed_payload(self):
        with TemporaryDirectory(dir=HERE) as directory:
            root=Path(directory);freeze,path,artifact,_=write_fixture(root)
            freeze.update(release_id='synthetic',code_sha256='a'*64,environment_sha256='b'*64,model_sha256='c'*64,protocol_sha256='d'*64)
            path.write_text(json.dumps(freeze),encoding='utf-8')
            release={'freeze_manifest':{'path':path.name},'readiness':{'path':'ready.json'},'schema_version':'test','release_id':'synthetic','manifest_refs':[]}
            namespace={'Path':Path,'load':lambda p:release,'reference':lambda ref,base:base/ref['path'],
                'protocol':types.SimpleNamespace(validate_release_gates=lambda a,b:(freeze,{}),SCHEMA_VERSION='test',load_release=lambda p:[]),
                'verify_artifacts':lambda f,p:{'code':'synthetic'},'digest':lambda p:'e'*64,'ReleaseError':ValueError}
            execute_node(self.generated['release_runner.py'],'verify_release',namespace)
            with patch.dict(sys.modules,{'restart_calibration_loader':calibration_loader}):
                verified=namespace['verify_release'](root)
                payload=verified['artifacts']['restart_qualification']
                self.assertEqual(payload['identity']['freeze_manifest']['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
                self.assertEqual(payload['payload_template_to_cell']['part:B'],'synthetic-B')
                artifact.write_text('changed',encoding='utf-8')
                with self.assertRaises(ValueError):namespace['verify_release'](root)

    def test_protected_absence_record_is_append_only_with_explicit_parent_and_scope(self):
        events=[]
        evidence=types.SimpleNamespace(emit=lambda *args:events.append(args) or 'absence-event')
        exposure={'restart_admissibility':{'state':'original'}}
        namespace={'absence_observation':calibration_loader.absence_observation,
            'restart_revocation':{'wall_s':10.,'sim_s':3.},'restart_absence_settings':{
                'absence_endpoint':'recover_held_admitted','absence_timebase':'simulation','prospective_absence_bound_s':2.},
            'restart_parent':'cut-event','restart_qualification':{'identity':{'freeze':'synthetic'}},
            'evidence':evidence,'restart_exposure':exposure}
        execute_node(self.generated['experiment.py'],'record_restart_absence',namespace)
        report=namespace['record_restart_absence']('restart_ready',{'wall_s':11.,'sim_s':3.5})
        self.assertEqual(report['coverage']['state'],'unknown')
        self.assertEqual(events[0][-1],['cut-event'])
        self.assertEqual(exposure['restart_admissibility'],{'state':'original'})
        self.assertEqual(exposure['absence_observations'][0]['event_id'],'absence-event')


if __name__=='__main__':unittest.main()
