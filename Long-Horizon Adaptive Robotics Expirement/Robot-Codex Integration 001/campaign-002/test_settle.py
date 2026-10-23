import unittest
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import settle
import operate
from settle import classify

class Stops(unittest.TestCase):
    def numeric_failure(self):
        return {'validity':'invalid','failed_checks':['complete_retained_timing_replayed_and_passed'],
           'campaign_timing':{'schema':'rci-campaign-independent-timing-2','passed':False,'scheduling_pass':True,
               'resource_integrity_pass':True,'garbage_collection_pass':True,'host_memory_pass':True,
               'garbage_collection':{'passed':True},'host_memory':{'passed':True},
               'sample_count':4,'metadata_sha256':'a'*64,'sample_sha256':'b'*64,
               'replayed_timing':{'actual_host_timing_pass':False,'maximum_lag_s':.11,'complete_wall_windows':1,
                   'outside_rtf_tolerance_fraction':0.,'outside_rtf_tolerance_windows':0,
                   'timing':[{'real_time_factor':1.,'within_tolerance':True}]}}}

    def test_task_failure_does_not_stop(self):
        a={'validity':'valid','scorable':True,'task_outcome':'failure','failed_checks':[]}
        stop,n,_=classify(a,1);self.assertFalse(stop);self.assertEqual(n,0)
    def test_two_replayed_timing_invalids_stop(self):
        a=self.numeric_failure()
        self.assertEqual(classify(a,0)[:2],(False,1));self.assertEqual(classify(a,1)[:2],(True,2))
    def test_missing_timing_stops_immediately(self):
        self.assertTrue(classify({'validity':'invalid','failed_checks':['complete_retained_timing_replayed_and_passed']},0)[0])
    def test_boundary_breach_stops_immediately(self):
        self.assertTrue(classify({'validity':'invalid','failed_checks':['all_45_outer_boundary_canaries']},0)[0])
    def test_unresolved_transport_can_be_ordinary(self):
        a={'validity':'invalid','failed_checks':['model_disposition_recognized','transport_revocation_and_reply_provenance'],
           'verification_errors':{'transport':'Unresolved transport failure: broker-failure.json'}}
        self.assertEqual(classify(a,0)[:2],(False,1))
    def test_inconsistent_scored_result_rejected(self):
        with self.assertRaises(ValueError):classify({'validity':'valid','task_outcome':'success','scorable':False},0)

    def test_unqualified_scheduling_is_not_ordinary_timing(self):
        a={'validity':'invalid','failed_checks':['complete_retained_timing_replayed_and_passed'],
           'campaign_timing':{'passed':False,'scheduling_pass':False}}
        self.assertEqual(classify(a,0)[:2],(True,0))

    def test_missing_or_failed_resources_make_numeric_failure_severe(self):
        for key in ('resource_integrity_pass','garbage_collection_pass','host_memory_pass'):
            for state in (None,False):
                with self.subTest(key=key,state=state):
                    a=self.numeric_failure();a['campaign_timing'][key]=state
                    self.assertEqual(classify(a,0)[:2],(True,0))

    def test_explicit_resource_gate_failure_is_always_severe(self):
        a=self.numeric_failure()
        a['failed_checks'].append('bounded_host_memory_and_collector_integrity')
        self.assertEqual(classify(a,0)[:2],(True,0))

    def test_malformed_replayed_windows_cannot_be_ordinary_numeric_failure(self):
        a=self.numeric_failure();a['campaign_timing']['replayed_timing']['timing']=[]
        self.assertEqual(classify(a,0)[:2],(True,0))


class SettlementRecovery(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.attempts=[{'ordinal':i,'run_id':'run'+str(i),'family':'misplaced-stock'} for i in range(1,4)]
        self.folder=self.root/'execution/run1';self.folder.mkdir(parents=True)
        self.job={'id':'job1','state':'succeeded','exit_status':0,'ended_at':'2026-09-27T23:00:00Z'}
        self.write(self.folder/'official-status.json',self.job)
        self.write(self.folder/'queue-submit.json',{'id':'job1'})
        self.write(self.folder/'assessment.json',{'run_id':'run1','queue_job_id':'job1','validity':'invalid',
            'task_outcome':'unknown','observed_task_outcome':'unknown','scorable':False,'failed_checks':['all_45_outer_boundary_canaries']})
        self.addCleanup(patch.stopall)
        patch.object(settle,'HERE',self.root).start()
        patch.object(settle,'settlement_context',return_value=({'attempts':self.attempts},{'certificate_sha256':'seal'},self.attempts[0])).start()
        self.map_records={}
        self.map_calls=[]
        def map_result(run,source,queue,validity,outcome,reason,execution,recorded):
            value=(Path(source).read_bytes(),Path(queue).read_bytes() if queue else None,validity,outcome,reason,execution,recorded)
            if run in self.map_records and self.map_records[run]!=value:raise ValueError('Synthetic map conflict')
            self.map_records[run]=value;self.map_calls.append(run)
        patch.object(settle,'reconcile_map_result',side_effect=map_result).start()

    def write(self,path,value):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))

    def run_settle(self):
        with redirect_stdout(io.StringIO()):settle.settle('run1')

    def test_map_first_interruption_then_reconcile_without_duplicate(self):
        original=operate.save_exact;failed=[False]
        def save(path,value):
            if Path(path)==self.folder/'disposition.json' and not failed[0]:
                failed[0]=True;raise OSError('Injected crash after map append')
            original(path,value)
        with patch.object(operate,'save_exact',side_effect=save):
            with self.assertRaisesRegex(OSError,'Injected'):self.run_settle()
        self.assertEqual(set(self.map_records),{'run1'})
        self.run_settle();self.run_settle()
        self.assertEqual(set(self.map_records),{'run1','run2','run3'})
        self.assertEqual(operate.read(self.root/'execution/campaign-stop.json')['not_run'],2)

    def test_unrun_disposition_first_interruption_resumes_missing_slots(self):
        original=settle.reconcile_map_result
        failed=[False]
        def map_result(*args):
            if args[0]=='run2' and not failed[0]:
                failed[0]=True;raise OSError('Injected crash after unrun disposition')
            return original(*args)
        with patch.object(settle,'reconcile_map_result',side_effect=map_result):
            with self.assertRaisesRegex(OSError,'Injected'):self.run_settle()
        self.assertTrue((self.root/'execution/run2/disposition.json').exists())
        self.assertNotIn('run2',self.map_records)
        self.run_settle()
        self.assertEqual(set(self.map_records),{'run1','run2','run3'})

    def test_conflicting_disposition_is_not_overwritten(self):
        self.run_settle()
        path=self.root/'execution/run2/disposition.json'
        value=operate.read(path);value['task_outcome']='success';self.write(path,value)
        before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'Conflicting immutable'):self.run_settle()
        self.assertEqual(path.read_bytes(),before)

    def test_failed_queue_diagnostic_never_opens_poison_assessment(self):
        self.job.update(state='failed',exit_status=1)
        self.write(self.folder/'official-status.json',self.job)
        (self.folder/'assessment.json').write_text('NOT JSON; MUST NEVER BE OPENED AS OUTCOME')
        self.run_settle()
        disposition=operate.read(self.folder/'disposition.json')
        self.assertEqual(disposition['task_outcome'],'unknown')
        self.assertEqual(disposition['execution_status'],'failed')
        self.assertFalse(disposition['allow_next'])
        self.assertEqual(disposition['diagnostic_file'],'diagnostic.json')

    def test_pending_matching_json_is_completed_without_rewrite(self):
        target=self.root/'matching.json';pending=target.with_name('matching.json.pending')
        self.write(pending,{'x':1})
        original=pending.read_bytes();operate.save_exact(target,{'x':1})
        self.assertEqual(target.read_bytes(),original)
        with self.assertRaisesRegex(ValueError,'Conflicting immutable'):operate.save_exact(target,{'x':2})

if __name__=='__main__':unittest.main()
