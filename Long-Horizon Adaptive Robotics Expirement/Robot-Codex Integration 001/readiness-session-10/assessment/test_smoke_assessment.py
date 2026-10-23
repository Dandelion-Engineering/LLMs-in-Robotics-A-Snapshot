"""Fail-closed queue, program snapshot and post-terminal observation checks."""
import base64
import json
from pathlib import Path
import tempfile
import unittest
import assess_smoke as assessor


class SmokeAssessmentTests(unittest.TestCase):
    def test_failed_queue_refused_before_evidence_access(self):
        with tempfile.TemporaryDirectory(prefix='robot-smoke-assessment-test-') as path:
            receipt=Path(path)/'queue.json'
            receipt.write_text(json.dumps({'state':'failed','exit_status':1}),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Queue'):
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

    def test_empty_note_needs_successful_cat_and_explicit_zero_byte_count(self):
        cat={'id':'cat','commandActions':[{'command':'cat live/state.json Continuity.md'}],'aggregatedOutput':'{}'}
        count={'id':'count','command':"/usr/bin/bash -lc 'wc -c Continuity.md && cat robot.py'",'aggregatedOutput':'0 Continuity.md\nsource'}
        self.assertTrue(assessor.empty_continuity_read_evidence([cat,count],assessor.sha(b'')))
        self.assertFalse(assessor.empty_continuity_read_evidence([cat],assessor.sha(b'')))
        self.assertFalse(assessor.empty_continuity_read_evidence([cat,count],assessor.sha(b'other')))
        count['aggregatedOutput']='claimed 0 Continuity.md\n'
        self.assertFalse(assessor.empty_continuity_read_evidence([cat,count],assessor.sha(b'')))


if __name__=='__main__':unittest.main()
