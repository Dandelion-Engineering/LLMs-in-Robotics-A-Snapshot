"""Fail-closed queue, program snapshot and post-terminal observation checks."""
import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import assess_smoke_v2 as assessor


class SmokeAssessmentTests(unittest.TestCase):
    def test_failed_queue_refused_before_evidence_access(self):
        with tempfile.TemporaryDirectory(prefix='robot-smoke-assessment-test-') as path:
            receipt=Path(path)/'queue.json'
            receipt.write_text(json.dumps({'state':'failed','exit_status':1}),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Official queue'):
                assessor.assess('absent','absent',receipt,'absent')

    def test_program_source_snapshot_must_match_hash(self):
        source=b'print("read only")\n'
        record={'source_base64':base64.b64encode(source).decode(),'source_sha256':assessor.sha(source),
                'source_bytes':len(source),'sealed_snapshot':True,'timeout_s':15}
        data={'notes/program-runs/test.admitted.json':json.dumps(record).encode()}
        self.assertFalse(assessor.valid_program_records(data)[1])
        record['source_sha256']='0'*64
        data['notes/program-runs/test.admitted.json']=json.dumps(record).encode()
        self.assertTrue(assessor.valid_program_records(data)[1])

    def test_observation_must_follow_terminal_and_match_new_epoch(self):
        event={'event_id':5,'type':'observation','authority_epoch':4,
               'payload':{'capture_sim_time_s':12,'gripper':{'width':.08,'holding_visible_id':None}}}
        self.assertEqual(assessor.fresh_open_observations([event],10,4),[event])
        self.assertEqual(assessor.fresh_open_observations([event],12,4),[])
        self.assertEqual(assessor.fresh_open_observations([event],10,3),[])

    def test_preexecution_admission_order_is_not_inferred_from_final_file(self):
        good='def execute():\n    durable_new_record(admission_path, {})\n    subprocess.Popen([])\n'
        bad='def execute():\n    subprocess.Popen([])\n    durable_new_record(admission_path, {})\n'
        self.assertTrue(assessor.runner_admission_precedes_process(good))
        self.assertFalse(assessor.runner_admission_precedes_process(bad))

    def test_live_reads_accept_evolving_time_but_require_protected_identity(self):
        packet={'run_id':'episode-test','sequence':30,'capture_sim_time_s':12.,'order':{'version':1},'sim_time':12.1}
        value={'authority_epoch':4,'invocation':{'invocation_id':'resume-test'},'packet':packet}
        item={'id':'read-live','commandActions':[{'type':'read','path':'/workspace/live/state.json'}],
              'aggregatedOutput':json.dumps(value)}
        stage={'result':{'invocation_id':'resume-test'},'commands':[item]}
        history=[{'type':'observation','event_id':99,'authority_epoch':4,'payload':{**packet,'sim_time':12.}}]
        self.assertTrue(assessor.live_read_evidence(stage,history,'episode-test',4)['live/state.json'])
        value['packet']['run_id']='another-episode'
        item['aggregatedOutput']=json.dumps(value)
        self.assertFalse(assessor.live_read_evidence(stage,history,'episode-test',4)['live/state.json'])

    def test_combined_cat_json_requires_entire_stream_and_literal_paths(self):
        self.assertEqual(assessor.complete_json_stream('{"a":1}{"b":2}'),[{'a':1},{'b':2}])
        self.assertEqual(assessor.complete_json_stream('{"a":1}trailing prose'),[])
        item={'commandActions':[{'type':'unknown','command':'cat live/activation.json live/state.json Continuity.md'}]}
        self.assertEqual(assessor.simple_cat_paths(item),{'live/activation.json','live/state.json','Continuity.md'})
        item['commandActions'][0]['command']='cat live/state.json; echo spoof'
        self.assertEqual(assessor.simple_cat_paths(item),set())

    def test_authenticated_live_source_must_be_entire_literal_cat_dispatch(self):
        packet={'run_id':'episode-test','sequence':30,'capture_sim_time_s':12.,'order':{'version':1}}
        value={'authority_epoch':4,'invocation':{'invocation_id':'resume-test'},'packet':packet}
        item={'id':'read-live','command':"/usr/bin/bash -lc 'cat live/state.json; echo forged'",
              'commandActions':[{'type':'read','path':'/workspace/live/state.json'}],
              'aggregatedOutput':json.dumps(value),'executor_provenance':{'authenticated':True}}
        stage={'result':{'invocation_id':'resume-test'},'commands':[item]}
        history=[{'type':'observation','event_id':99,'authority_epoch':4,'payload':packet}]
        self.assertFalse(assessor.live_read_evidence(stage,history,'episode-test',4)['live/state.json'])
        item['command']="/usr/bin/bash -lc 'cat live/state.json'"
        self.assertTrue(assessor.live_read_evidence(stage,history,'episode-test',4)['live/state.json'])

    def test_empty_note_needs_successful_cat_and_explicit_zero_byte_count(self):
        cat={'id':'cat','commandActions':[{'command':'cat live/state.json Continuity.md'}],'aggregatedOutput':'{}'}
        count={'id':'count','command':"/usr/bin/bash -lc 'wc -c Continuity.md && cat robot.py'",'aggregatedOutput':'0 Continuity.md\nsource'}
        self.assertTrue(assessor.empty_continuity_read_evidence([cat,count],assessor.sha(b'')))
        self.assertFalse(assessor.empty_continuity_read_evidence([cat],assessor.sha(b'')))
        self.assertFalse(assessor.empty_continuity_read_evidence([cat,count],assessor.sha(b'other')))
        count['aggregatedOutput']='claimed 0 Continuity.md\n'
        self.assertFalse(assessor.empty_continuity_read_evidence([cat,count],assessor.sha(b'')))


class ExplicitBindingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.manifest = self.root / 'explicit-smoke.json'
        self.manifest.write_text(json.dumps({'run_id': 'new-smoke', 'framework_revision': 'new-revision'}), encoding='utf-8')
        self.digest = assessor.base.hash_file(self.manifest)
        interpreter = str(assessor.base.REPO / 'venv/Scripts/python.exe')
        self.job = {'state': 'succeeded', 'exit_status': 0, 'id': 'smoke-job', 'cwd': str(assessor.base.REPO),
                    'resolved_executable': interpreter,
                    'argv': [interpreter, '-X', 'utf8', '-B', str(assessor.base.LAUNCHER),
                             '--manifest', str(self.manifest), '--evidence', str(self.root / 'e'),
                             '--host-evidence', str(self.root / 'h'), '--workspace', str(self.root / 'w'), '--mode', 'smoke']}

    def tearDown(self):
        self.temporary.cleanup()

    def invoke(self, **overrides):
        arguments = {'manifest_path': self.manifest, 'manifest_sha256': self.digest,
                     'expected_revision': 'new-revision', 'expected_workspace': self.root / 'w'}
        arguments.update(overrides)
        return assessor.assess(self.root / 'e', self.root / 'h', self.root / 'queue.json',
                               self.root / 'snapshot.json', 'smoke-job', **arguments)

    def test_failed_or_boolean_queue_exit_stops_before_all_outputs(self):
        for state, exit_status in [('failed', 0), ('running', None), ('succeeded', False)]:
            self.job.update(state=state, exit_status=exit_status)
            with patch.object(assessor, 'read_json', return_value=self.job) as reader:
                with self.assertRaisesRegex(ValueError, 'Official queue'):
                    self.invoke()
                reader.assert_called_once_with(self.root / 'queue.json')

    def test_pilot_receipt_cannot_admit_smoke_outputs(self):
        self.job['argv'][-1] = 'pilot'
        with patch.object(assessor, 'read_json', return_value=self.job) as reader:
            with self.assertRaisesRegex(ValueError, 'smoke direct launcher'):
                self.invoke()
            reader.assert_called_once_with(self.root / 'queue.json')

    def test_manifest_hash_checked_before_frozen_or_output_reads(self):
        with patch.object(assessor, 'read_json', return_value=self.job) as reader:
            with self.assertRaisesRegex(ValueError, 'predeclared SHA256'):
                self.invoke(manifest_sha256='0' * 64)
            reader.assert_called_once_with(self.root / 'queue.json')

    def test_manifest_revision_checked_before_frozen_or_output_reads(self):
        with patch.object(assessor, 'read_json', return_value=self.job) as reader:
            with self.assertRaisesRegex(ValueError, 'framework revision'):
                self.invoke(expected_revision='other-revision')
            reader.assert_called_once_with(self.root / 'queue.json')

    def test_explicit_manifest_does_not_relabel_snapshot_native_run(self):
        frozen = {'run_id': 'native-qualification', 'manifest_sha256': 'old-native-manifest',
                  'revision': 'new-revision', 'sources': {
                      Path(assessor.__file__).relative_to(assessor.base.REPO).as_posix():
                      {'sha256': assessor.base.hash_file(assessor.__file__)},
                      Path(assessor.empty_startup_reads.__file__).relative_to(assessor.base.REPO).as_posix():
                      {'sha256': assessor.base.hash_file(assessor.empty_startup_reads.__file__)},
                      Path(assessor.literal_read_segments.__file__).relative_to(assessor.base.REPO).as_posix():
                      {'sha256': assessor.base.hash_file(assessor.literal_read_segments.__file__)},
                      Path(assessor.initial_read_composition.__file__).relative_to(assessor.base.REPO).as_posix():
                      {'sha256': assessor.base.hash_file(assessor.initial_read_composition.__file__)},
                      Path(assessor.completion_chronology.__file__).relative_to(assessor.base.REPO).as_posix():
                      {'sha256': assessor.base.hash_file(assessor.completion_chronology.__file__)},
                      Path(assessor.prepared_result_segments.__file__).relative_to(assessor.base.REPO).as_posix():
                      {'sha256': assessor.base.hash_file(assessor.prepared_result_segments.__file__)},
                      Path(assessor.prepared_startup_segments.__file__).relative_to(assessor.base.REPO).as_posix():
                      {'sha256': assessor.base.hash_file(assessor.prepared_startup_segments.__file__)},
                      Path(assessor.canary_readback_proof.__file__).relative_to(assessor.base.REPO).as_posix():
                      {'sha256': assessor.base.hash_file(assessor.canary_readback_proof.__file__)}}}
        with patch.object(assessor, 'read_json', side_effect=[self.job, frozen, {}]) as reader, \
                patch.object(assessor.base, 'frozen_problems', return_value=[]), \
                patch.object(assessor, 'inspect_stage', side_effect=RuntimeError('reached output phase')):
            with self.assertRaisesRegex(RuntimeError, 'reached output phase'):
                self.invoke()
            self.assertEqual(reader.call_args_list[1].args[0], self.root / 'snapshot.json')
            self.assertEqual(frozen['run_id'], 'native-qualification')
            self.assertEqual(frozen['manifest_sha256'], 'old-native-manifest')

    def test_frozen_smoke_assessor_must_be_present(self):
        with patch.object(assessor, 'read_json', side_effect=[self.job, {'sources': {}}]), \
                patch.object(assessor.base, 'frozen_problems', return_value=[]), \
                patch.object(assessor, 'inspect_stage') as stage:
            with self.assertRaisesRegex(ValueError, 'smoke assessor absent/different'):
                self.invoke()
            stage.assert_not_called()

    def test_frozen_empty_startup_helper_must_be_present(self):
        frozen = {'sources': {
            Path(assessor.__file__).relative_to(assessor.base.REPO).as_posix():
            {'sha256': assessor.base.hash_file(assessor.__file__)}}}
        with patch.object(assessor, 'read_json', side_effect=[self.job, frozen]), \
                patch.object(assessor.base, 'frozen_problems', return_value=[]), \
                patch.object(assessor, 'inspect_stage') as stage:
            with self.assertRaisesRegex(ValueError, 'empty startup reader absent/different'):
                self.invoke()
            stage.assert_not_called()

    def test_frozen_literal_segment_helper_must_be_present_and_current(self):
        for digest in (None, '0' * 64):
            frozen = {'sources': {
                Path(module.__file__).relative_to(assessor.base.REPO).as_posix():
                {'sha256': assessor.base.hash_file(module.__file__)}
                for module in (assessor, assessor.empty_startup_reads)}}
            if digest is not None:
                frozen['sources'][Path(assessor.literal_read_segments.__file__).relative_to(assessor.base.REPO).as_posix()] = {'sha256': digest}
            with patch.object(assessor, 'read_json', side_effect=[self.job, frozen]), \
                    patch.object(assessor.base, 'frozen_problems', return_value=[]), \
                    patch.object(assessor, 'inspect_stage') as stage:
                with self.assertRaisesRegex(ValueError, 'literal segment reader absent/different'):
                    self.invoke()
                stage.assert_not_called()


    def test_frozen_composition_helpers_must_be_present_and_current_before_outputs(self):
        modules = (assessor, assessor.empty_startup_reads, assessor.literal_read_segments,
                   assessor.initial_read_composition, assessor.completion_chronology,
                   assessor.prepared_result_segments, assessor.prepared_startup_segments,
                   assessor.canary_readback_proof)
        for missing, label in ((assessor.initial_read_composition, 'initial read composition'),
                               (assessor.completion_chronology, 'completion chronology'),
                               (assessor.prepared_result_segments, 'prepared result segments'),
                               (assessor.prepared_startup_segments, 'prepared startup segments'),
                               (assessor.canary_readback_proof, 'canary readback proof')):
            for digest in (None, '0' * 64):
                with self.subTest(helper=label, digest=digest):
                    frozen = {'sources': {
                        Path(module.__file__).relative_to(assessor.base.REPO).as_posix():
                        {'sha256': assessor.base.hash_file(module.__file__)}
                        for module in modules if module is not missing}}
                    if digest is not None:
                        frozen['sources'][Path(missing.__file__).relative_to(assessor.base.REPO).as_posix()] = {'sha256': digest}
                    with patch.object(assessor, 'read_json', side_effect=[self.job, frozen]) as reader, \
                            patch.object(assessor.base, 'frozen_problems', return_value=[]), \
                            patch.object(assessor, 'inspect_stage') as stage:
                        with self.assertRaisesRegex(ValueError, label + ' helper absent/different'):
                            self.invoke()
                        self.assertEqual([call.args[0] for call in reader.call_args_list],
                                         [self.root / 'queue.json', self.root / 'snapshot.json'])
                        stage.assert_not_called()


if __name__=='__main__':unittest.main()
