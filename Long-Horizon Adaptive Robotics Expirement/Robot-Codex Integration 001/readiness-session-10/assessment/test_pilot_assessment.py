"""Outcome separation and non-success evidence controls; no actual model calls."""
import json
from pathlib import Path
import tempfile
import unittest
import assess_pilot as assessor

FAILURE={'schema_version':'robot-independent-outcome-1.0','success':False}


class PilotAssessmentTests(unittest.TestCase):
    def test_failed_queue_refused_before_actual_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            receipt=Path(folder)/'queue.json'
            receipt.write_text(json.dumps({'state':'failed','exit_status':1}))
            with self.assertRaisesRegex(ValueError,'Queue'):
                assessor.assess('absent','absent',receipt,'absent')

    def test_clean_host_exit_does_not_establish_task_success(self):
        result=assessor.classify_outcome({'execution_completed':True,'terminal':'operator_stop','independent_outcome':FAILURE}, {}, [])
        self.assertEqual(result['independent_task_outcome'],'failure')
        self.assertEqual(result['recovery_outcome'],'no_accepted_handback')
        self.assertFalse(result['conventional_work_resumed'])
        self.assertTrue(result['task_success_terminal_consistent'])
        result=assessor.classify_outcome({'execution_completed':False,'independent_outcome':{'success':True}}, {}, [])
        self.assertEqual(result['independent_task_outcome'],'unknown')

    def test_handback_is_not_conventional_productive_work(self):
        handback={'request_id':'hb','kind':'handback','actor':'robot','phase':'terminal','status':'completed',
                  'envelope':{'authority_epoch':3},'verification':{'state':'public_resumption_conditions','next_operation':'transport'}}
        event={'event_id':10,'type':'control_owner_changed','owner':'conventional','authority_epoch':4,
               'payload':{'request_id':'hb','supported_next_action':{'operation':'transport'}}}
        host={'execution_completed':True,'terminal':'operator_stop','independent_outcome':FAILURE,'handbacks':1}
        result=assessor.classify_outcome(host,{'hb':handback},[event])
        self.assertTrue(result['accepted_handback_corresponds_to_owner_transfer'])
        self.assertFalse(result['conventional_work_resumed'])
        action={'request_id':'c1','request_event_id':11,'actor':'conventional','kind':'command',
                'envelope':{'authority_epoch':4,'action':{'operation':'transport'}},'phase':'terminal','status':'completed',
                'admission':{'status':'accepted'}}
        dispatch={'event_id':12,'type':'command_dispatched','payload':{'request_id':'c1'}}
        result=assessor.classify_outcome(host,{'hb':handback,'c1':action},[event,dispatch])
        self.assertTrue(result['conventional_work_resumed'])
        self.assertEqual(result['independent_task_outcome'],'failure')
        action['envelope']['action']['operation']='done'
        self.assertFalse(assessor.classify_outcome(host,{'hb':handback,'c1':action},[event,dispatch])['conventional_work_resumed'])

    def test_public_transport_support_requires_later_matching_observation(self):
        record={'request_id':'r1','terminal_sim_time_s':10.,'envelope':{'action':{'operation':'transport','part_id':'A1','destination':'parking1'}},
                'verification':{'state':'public_observation_support','observation_sequence':20,'capture_sim_time_s':11.}}
        event={'type':'observation','event_id':22,'payload':{'sequence':20,'capture_sim_time_s':11.,'detections':[{'id':'A1','zone':'parking1'}]}}
        self.assertTrue(assessor.public_support(record,[event])['independently_matched'])
        event['payload']['detections'][0]['zone']='quarantine'
        self.assertFalse(assessor.public_support(record,[event])['independently_matched'])
        record['verification']['state']='unknown'
        self.assertIsNone(assessor.public_support(record,[event])['independently_matched'])

    def test_claimed_success_requires_dwell_and_first_success_evidence(self):
        outcome={'schema_version':'robot-independent-outcome-1.0','success':True,'immediate_ready':True,'violations':[],
                 'order_version':1,'sim_time':20.,'settling':{'observed_s':.5,'required_s':.5},
                 'first_success':{'sim_time_s':20.,'order_version':1,'required_dwell_s':.5,'snapshot_sha256':'a'*64}}
        host={'execution_completed':True,'terminal':'task_success','independent_outcome':outcome}
        self.assertEqual(assessor.classify_outcome(host,{},[])['independent_task_outcome'],'success')
        outcome['settling']['observed_s']=.1
        result=assessor.classify_outcome(host,{},[])
        self.assertEqual(result['independent_task_outcome'],'unknown')
        self.assertFalse(result['task_success_terminal_consistent'])


if __name__=='__main__':unittest.main()
