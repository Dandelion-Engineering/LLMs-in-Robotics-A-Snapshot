"""Evidence-boundary and denominator checks; synthetic inputs never reach report."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('investigation_build', Path(__file__).with_name('build.py'))
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class ReportTests(unittest.TestCase):
    @staticmethod
    def plan():
        return {'campaign_id':'RCI001-Campaign002','attempts':[
            {'ordinal':2*(i-1)+j+1,'run_id':f'RCI001-C02-{family}-{i:02}',
             'family':'misplaced-stock' if family=='stock' else 'blocked-insert-home'}
            for i in range(1,11) for j,family in enumerate(('stock','home'))]}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='rci-investigation-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.execution = self.root / 'execution'
        self.output = self.root / 'output'
        self.output.mkdir()
        self.attempt = {'ordinal': 1, 'run_id': 'RCI001-C02-test', 'family': 'misplaced-stock',
            'manifest': {'path': str(self.root / 'manifest.json'), 'sha256': 'a' * 64},
            'host_evidence': str(self.root / 'host'), 'evidence': str(self.root / 'orchestrator'),
            'storage_receipt': str(self.execution / 'RCI001-C02-test/storage/receipt.json')}
        self.folder = self.execution / self.attempt['run_id']
        (self.folder / 'storage').mkdir(parents=True)
        report.READS.clear()

    def save(self, path, value):
        path.write_text(json.dumps(value), encoding='utf-8')

    def receipt(self, state, exit_status):
        path = self.folder / 'storage/queue-receipt.json'
        self.save(path, {'id': 'synthetic-job', 'state': state, 'exit_status': exit_status})
        return path

    def record(self):
        return report.run_record(self.attempt, self.execution, self.output)

    def test_wilson_exact_all_success_and_no_trials(self):
        self.assertIsNone(report.wilson(0, 0))
        low, high = report.wilson(12, 12)
        self.assertAlmostEqual(low, .7575059933447592)
        self.assertEqual(high, 1)
        low, high = report.wilson(0, 12)
        self.assertAlmostEqual(low, 0)
        self.assertAlmostEqual(high, .2424940066552408)

    def test_failed_queue_never_opens_assessment_or_traces(self):
        self.receipt('failed', 1)
        (self.folder / 'assessment.json').write_bytes(b'invalid JSON must never be opened')
        row = self.record()
        self.assertFalse(row['scorable'])
        self.assertEqual(row['task_outcome'], 'unknown')
        self.assertEqual(row['events'], [])
        self.assertEqual([x['role'] for x in report.READS], ['official queue receipt'])

    def test_plan_requires_exact_twenty_identities_and_families(self):
        plan=self.plan();report.validate_plan(plan)
        plan['attempts'][-1]['run_id']='RCI001-C02-home-11'
        with self.assertRaisesRegex(ValueError,'identity'):report.validate_plan(plan)
        plan=self.plan();plan['attempts'][0]['family']='blocked-insert-home'
        with self.assertRaisesRegex(ValueError,'family'):report.validate_plan(plan)

    def test_settlement_gate_reads_no_attempt_result(self):
        plan=self.plan()
        for item in plan['attempts']:
            folder=self.execution/item['run_id'];folder.mkdir(parents=True,exist_ok=True)
            self.save(folder/'disposition.json',{'run_id':item['run_id'],'execution_status':'not_run'})
            (folder/'assessment.json').write_text('must not be opened')
        last=plan['attempts'][-1]
        self.save(self.execution/last['run_id']/'disposition.json',{'run_id':last['run_id'],'execution_status':'running'})
        with self.assertRaisesRegex(ValueError,'not all settled'):report.require_settled(plan,self.execution)
        self.assertTrue(all(row['role']=='terminal disposition gate' for row in report.READS))

    def test_not_run_slot_never_opens_leftover_queue_or_outcomes(self):
        self.save(self.folder/'disposition.json',{'run_id':self.attempt['run_id'],'execution_status':'not_run','reason':'stopped'})
        (self.folder/'storage/queue-receipt.json').write_text('must not be read')
        (self.folder/'assessment.json').write_text('must not be read')
        row=self.record()
        self.assertEqual(row['execution_status'],'not_run')
        self.assertEqual([r['role'] for r in report.READS],['slot disposition'])

    def diagnostic(self, state='failed', code=1):
        official=self.folder/'official-status.json'
        self.save(official,{'id':'diagnostic-job','state':state,'exit_status':code})
        diagnostic=self.folder/'diagnostic.json'
        self.save(diagnostic,{'schema':'campaign002-diagnostic-1','run_id':self.attempt['run_id'],
            'queue_job_id':'diagnostic-job','bindings':{'queue_receipt_sha256':report.digest(official.read_bytes())},
            'validity':'invalid','task_outcome':'unknown','observed_task_outcome':'unknown','scorable':False,
            'immediate_stop':True,'kind':'assessor_exception' if state=='succeeded' else 'queue_failure'})
        self.save(self.folder/'disposition.json',{'run_id':self.attempt['run_id'],
            'execution_status':'completed' if state=='succeeded' else 'failed','validity':'invalid',
            'reason':'Synthetic preserved diagnostic','diagnostic_file':'diagnostic.json',
            'diagnostic_sha256':report.digest(diagnostic.read_bytes()),'assessment_sha256':None})
        return diagnostic

    def test_queue_failure_diagnostic_has_unknown_outcome_without_opening_partial_assessment(self):
        self.diagnostic()
        (self.folder/'assessment.json').write_text('partial assessment must not be opened')
        row=self.record()
        self.assertEqual((row['validity'],row['task_outcome'],row['observed_task_outcome']),('invalid','unknown','unknown'))
        self.assertFalse(row['scorable']);self.assertFalse(row['assessment_available'])
        self.assertEqual(row['events'],[]);self.assertEqual(row['frames'],[])
        self.assertEqual([r['role'] for r in report.READS],['slot disposition','official queue receipt','bound diagnostic settlement'])
        self.assertTrue(any('diagnostic settlement' in item['label'] for item in row['links']))

    def test_successful_queue_assessor_exception_prefers_bound_official_receipt_and_ignores_partial(self):
        self.diagnostic('succeeded',0)
        (self.folder/'assessment.json').write_text('partial assessment must not be opened')
        (self.folder/'storage/queue-receipt.json').write_text('unrelated storage receipt must not be opened')
        row=self.record()
        self.assertTrue(row['queue_verified']);self.assertEqual(row['execution_status'],'completed')
        self.assertFalse(row['assessment_available']);self.assertEqual(row['task_outcome'],'unknown')
        self.assertEqual(report.aggregate([row])['all scheduled slots']['valid'],0)

    def test_diagnostic_tampering_or_missing_disposition_binding_refuses_report(self):
        path=self.diagnostic()
        path.write_text(path.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):self.record()
        self.diagnostic()
        self.save(self.folder/'disposition.json',{'run_id':self.attempt['run_id'],'execution_status':'failed'})
        with self.assertRaisesRegex(ValueError,'exact disposition binding'):self.record()

    def test_diagnostic_queue_identity_mismatch_refuses_report(self):
        self.diagnostic()
        self.save(self.folder/'official-status.json',{'id':'different-job','state':'failed','exit_status':1})
        with self.assertRaisesRegex(ValueError,'identity/queue'):self.record()

    def test_repair_failures_and_unknowns_remain_separate(self):
        runs=[{'assessment_available':True,'transport':{'passed':True},'timing':None,
               'verification_errors':{'timing':'sample mismatch'}},
              {'assessment_available':True,'transport':None,'timing':{'passed':True}},
              {'assessment_available':False}]
        result=report.repair_summary(runs)
        self.assertEqual(result['transport'],{'passed':1,'failed':0,'unknown':1})
        self.assertEqual(result['timing'],{'passed':1,'failed':1,'unknown':0})
        self.assertEqual(result['unassessed'],1)

    def test_qualification_history_retains_failed_and_cancelled_without_opening_outputs(self):
        artifact=self.root/'failure.json';artifact.write_text('not valid JSON; linked only')
        index=self.root/'qualification.json'
        self.save(index,{'schema':'campaign002-qualification-history-1','attempts':[
            {'run_id':'q1','revision':'frozen1','status':'failed','reason':'retained failure',
             'artifacts':[{'path':str(artifact),'label':'Original failure'}]},
            {'run_id':'q2','revision':'frozen2','status':'cancelled','reason':'source freeze changed','artifacts':[]}]})
        result=report.qualification_history(index,self.output)
        self.assertEqual([r['status'] for r in result['attempts']],['failed','cancelled'])
        self.assertEqual(len(report.READS),1)
        self.assertEqual(report.READS[0]['role'],'explicit settled qualification history')

    def test_smoke001_failure_cannot_be_relabelled_by_history_index(self):
        index=self.root/'qualification.json'
        value={'schema':'campaign002-qualification-history-1','attempts':[
            {'run_id':'RCI001-C02-smoke-001','revision':'RCI001-C02-dev-004',
             'status':'failed','reason':'Original retained assessment failed','artifacts':[]}]}
        self.save(index,value)
        self.assertTrue(report.qualification_history(index,self.output)['preserved_smoke001'])
        for replacement in ('passed','superseded','cancelled'):
            value['attempts'][0]['status']=replacement;self.save(index,value)
            with self.assertRaisesRegex(ValueError,'must remain failed'):
                report.qualification_history(index,self.output)

    def test_completed_diagnostic_stays_unassessed_and_never_reads_its_outputs(self):
        artifact=self.root/'diagnostic.json';artifact.write_text('not JSON; never consume')
        item={'run_id':'diagnostic','status':'completed','validity':'unknown','task_outcome':'unknown',
            'scorable':False,'assessment_state':'not_assessed',
            'queue_completion_contract':{'schema':'campaign002-completed-unassessed-interrupt-queue-1'},
            'artifacts':[{'path':str(artifact)}]}
        index=self.root/'qualification.json'
        def save():self.save(index,{'schema':'campaign002-qualification-history-1','attempts':[item]})
        save();result=report.qualification_history(index,self.output)
        self.assertEqual(result['attempts'][0]['assessment_state'],'not_assessed')
        self.assertEqual(result['attempts'][0]['task_outcome'],'unknown')
        self.assertEqual([x['path'] for x in report.READS],[str(index)])
        for key,value in [('scorable',True),('validity','valid'),('task_outcome','success'),
                          ('assessment_state','assessed'),('queue_completion_contract',{})]:
            previous=item[key];item[key]=value;save()
            with self.assertRaisesRegex(ValueError,'must remain explicitly unassessed'):
                report.qualification_history(index,self.output)
            item[key]=previous

    def test_explicit_companion_is_bound_without_overwriting_the_legacy_report(self):
        index=self.root/'qualification.json'
        self.save(index,{'schema':'campaign002-qualification-history-1','attempts':[]})
        companion=self.root/'current report.html';companion.write_bytes(b'<html>current snapshot</html>')
        result=report.qualification_history(index,self.output,companion)
        self.assertEqual(result['companion_href'],'../current%20report.html')
        self.assertEqual(report.READS[-1]['sha256'],report.digest(companion.read_bytes()))
        with self.assertRaises(FileNotFoundError):
            report.qualification_history(index,self.output,self.root/'absent.html')

    def test_phase_diagnostics_require_assessment_hash_and_keep_capture_projection_separate(self):
        receipt=self.receipt('succeeded',0)
        host=Path(self.attempt['host_evidence']);host.mkdir()
        metadata=host/'timing-v2.json'
        self.save(metadata,{'loop_origin':{'clock_name':'perf_counter'},
            'phases':{'journal.state.public.fsync':{'count':2,'wall_total_s':.01}},
            'garbage_collection':{'schema':'rci-gc-diagnostics-2','policy':'synthetic-test-policy'},
            'host_memory':{'schema':'rci-host-memory-1','native_job':{'scope':'synthetic only'}},
            'phase_accounting':'Inclusive overlapping durations'})
        capture={'verified':True,'files':[{'file':'executor-2-capture.jsonl','sha256':'c'*64}]}
        projection={'tool':{'stdout_bytes':9000,'app_projection_bytes':808,
                            'app_projection_equals_executor':False}}
        self.save(self.folder/'assessment.json',{'schema':'robot-codex-campaign-assessment-2',
            'run_id':self.attempt['run_id'],'queue_job_id':'synthetic-job',
            'bindings':{'manifest_sha256':'a'*64,'queue_receipt_sha256':report.digest(receipt.read_bytes())},
            'validity':'invalid','task_outcome':'unknown','observed_task_outcome':'unknown','scorable':False,
            'campaign_timing':{'passed':False,'metadata_sha256':report.digest(metadata.read_bytes())},
            'executor_capture':capture,'source_read_projection_evidence':projection})
        with patch.object(report,'extract_events',return_value={}),patch.object(report,'load_frames',return_value={}):
            row=self.record()
            self.assertEqual(row['timing_attribution']['loop_origin']['clock_name'],'perf_counter')
            self.assertEqual(row['timing_attribution']['host_memory']['schema'],'rci-host-memory-1')
            self.assertEqual(row['timing_attribution']['garbage_collection']['schema'],'rci-gc-diagnostics-2')
            self.assertEqual(row['executor_capture'],capture)
            self.assertEqual(row['source_read_projection_evidence'],projection)
            self.assertFalse(row['scorable'])
            metadata.write_text(metadata.read_text()+' ')
            rejected=self.record()
            self.assertNotIn('timing_attribution',rejected)
            self.assertTrue(any('hash mismatch' in warning for warning in rejected['warnings']))

    def test_supervisory_ledger_is_separately_inventory_bound_with_same_origin(self):
        host=Path(self.attempt['host_evidence']); folder=host/'supervisory-diagnostics'; folder.mkdir(parents=True)
        sample=folder/'timing-samples.bin'; sample.write_bytes(b'original supervisory bytes')
        owner={'loop_origin':{'monotonic_s':100.,'initial_sim_s':1.}}
        metadata=folder/'timing-v2.json'
        self.save(metadata,{'schema':'rci-prospective-timing-2','loop_origin':owner['loop_origin'],
            'sample_file':sample.name,'sha256':report.digest(sample.read_bytes()),'byte_count':sample.stat().st_size,
            'phases':{'journal.event.protected.fsync':{'count':2,'wall_total_s':.08}}})
        assessment={'evidence_inventory':[{'root':'protected_host','path':p.relative_to(host).as_posix(),
            'sha256':report.digest(p.read_bytes()),'bytes':p.stat().st_size} for p in (metadata,sample)]}
        details=report.supervisory_attribution(self.attempt,assessment,owner,self.output)
        self.assertEqual(details['phases']['journal.event.protected.fsync']['count'],2)
        self.assertIsNone(details['strict_passed']); self.assertFalse(details['strict_verification_available'])
        self.assertIn('supervisory-diagnostics',details['metadata']['href'])
        self.assertEqual(len(report.READS),2)
        sample.write_bytes(b'tampered supervisory bytes')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            report.supervisory_attribution(self.attempt,assessment,owner,self.output)

    def test_unbound_supervisory_files_are_unavailable_without_being_read(self):
        folder=Path(self.attempt['host_evidence'])/'supervisory-diagnostics'; folder.mkdir(parents=True)
        (folder/'timing-v2.json').write_text('unbound invalid JSON must not be opened')
        self.assertIsNone(report.supervisory_attribution(self.attempt,{}, {},self.output))
        self.assertEqual(report.READS,[])

    def test_supervisory_origin_cannot_be_substituted(self):
        host=Path(self.attempt['host_evidence']);folder=host/'supervisory-diagnostics';folder.mkdir(parents=True)
        metadata=folder/'timing-v2.json';self.save(metadata,{'schema':'rci-prospective-timing-2',
            'sample_file':'timing-samples.bin','loop_origin':{'monotonic_s':999.}})
        assessment={'evidence_inventory':[{'root':'protected_host','path':'supervisory-diagnostics/timing-v2.json',
            'sha256':report.digest(metadata.read_bytes()),'bytes':metadata.stat().st_size}]}
        with self.assertRaisesRegex(ValueError,'clock origin'):
            report.supervisory_attribution(self.attempt,assessment,{'loop_origin':{'monotonic_s':1.}},self.output)

    def test_scorable_requires_explicit_admission(self):
        receipt=self.receipt('succeeded',0)
        self.save(self.folder/'assessment.json',{'schema':'robot-codex-campaign-admitted-assessment-2',
            'run_id':self.attempt['run_id'],'queue_job_id':'synthetic-job',
            'bindings':{'manifest_sha256':'a'*64,'queue_receipt_sha256':report.digest(receipt.read_bytes())},
            'validity':'valid','task_outcome':'success','observed_task_outcome':'success',
            'scorable':True,'scientific_admission':{'admissible':False}})
        with self.assertRaisesRegex(ValueError,'explicit scientific admission'):self.record()

    def test_boolean_zero_and_running_queue_do_not_open_outcomes(self):
        for state, code in [('succeeded', False), ('running', 0)]:
            self.receipt(state, code)
            (self.folder / 'assessment.json').write_bytes(b'invalid JSON must never be opened')
            self.assertFalse(self.record()['scorable'])

    def test_unfinished_is_pending_until_explicit_not_run_disposition(self):
        self.assertEqual(self.record()['execution_status'], 'pending')
        self.save(self.folder / 'disposition.json', {'run_id': self.attempt['run_id'],
            'execution_status': 'not_run', 'reason': 'Synthetic predeclared stop'})
        row = self.record()
        self.assertEqual((row['execution_status'], row['validity'], row['task_outcome']),
                         ('not_run', 'unknown', 'not_assessed'))

    def test_admitted_assessment_must_bind_official_queue_bytes(self):
        self.receipt('succeeded', 0)
        self.save(self.folder / 'assessment.json', {'schema': 'robot-codex-campaign-admitted-assessment-2',
            'run_id': self.attempt['run_id'], 'queue_job_id': 'synthetic-job',
            'bindings': {'manifest_sha256': 'a' * 64, 'queue_receipt_sha256': 'b' * 64}})
        with self.assertRaisesRegex(ValueError, 'identity/queue/manifest'):
            self.record()

    def test_completed_disposition_requires_exact_assessment_bytes_before_read(self):
        self.receipt('succeeded',0)
        path=self.folder/'assessment.json';path.write_text('must not be parsed before hash validation')
        disposition={'run_id':self.attempt['run_id'],'execution_status':'completed',
                     'assessment_sha256':report.digest(path.read_bytes())}
        self.save(self.folder/'disposition.json',disposition)
        path.write_text(path.read_text()+' changed')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):self.record()
        disposition.pop('assessment_sha256');self.save(self.folder/'disposition.json',disposition)
        with self.assertRaisesRegex(ValueError,'terminal disposition hash'):self.record()

    def test_all_planned_bounds_retain_invalid_and_unrun_slots(self):
        runs = [{'family': 'misplaced-stock', 'scorable': True, 'task_outcome': 'success',
                 'validity': 'valid', 'execution_status': 'completed'},
                {'family': 'misplaced-stock', 'scorable': True, 'task_outcome': 'failure',
                 'validity': 'valid', 'execution_status': 'completed'},
                {'family': 'blocked-insert-home', 'scorable': False, 'task_outcome': 'unknown',
                 'validity': 'invalid', 'execution_status': 'failed'},
                {'family': 'blocked-insert-home', 'scorable': False, 'task_outcome': 'not_assessed',
                 'validity': 'unknown', 'execution_status': 'not_run'}]
        result = report.aggregate(runs)['all scheduled slots']
        self.assertEqual((result['planned'], result['valid'], result['successes'], result['invalid'], result['not_run']), (4, 2, 1, 1, 1))
        self.assertEqual(result['all_planned_bounds'], [.25, .75])

    def test_preselected_examples_do_not_depend_on_outcomes(self):
        runs = [{'run_id': str(i), 'family': 'misplaced-stock' if i % 2 else 'blocked-insert-home',
                 'examples': [], 'validity': 'unknown', 'scorable': False} for i in range(1, 21)]
        report.select_examples(runs)
        self.assertEqual([r['run_id'] for r in runs if r['examples']], ['1', '2', '19', '20'])

    def test_changed_trace_hash_is_refused(self):
        path = self.root / 'history.jsonl'
        path.write_bytes(b'{"type":"test"}\n')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            report.trace(path, 'protected_host:history.jsonl',
                         {('protected_host', 'history.jsonl'): {'sha256': '0' * 64, 'bytes': path.stat().st_size}}, self.output)

    def test_observed_invalid_completion_is_visible_but_never_scored(self):
        receipt = self.receipt('succeeded', 0)
        queue = json.loads(receipt.read_text())
        queue.update(started_at='2026-09-27T19:00:00+00:00', ended_at='2026-09-27T19:01:00+00:00')
        self.save(receipt, queue)
        self.save(self.folder / 'assessment.json', {'schema': 'robot-codex-campaign-admitted-assessment-2',
            'run_id': self.attempt['run_id'], 'queue_job_id': 'synthetic-job',
            'bindings': {'manifest_sha256': 'a' * 64, 'queue_receipt_sha256': report.digest(receipt.read_bytes())},
            'validity': 'invalid', 'task_outcome': 'unknown', 'observed_task_outcome': 'success',
            'scorable': False, 'failed_checks': ['strict_timing'], 'evidence_inventory': []})
        with patch.object(report, 'extract_events', return_value={'events': [], 'untimed': []}), \
                patch.object(report, 'load_frames', return_value={'frames': []}):
            row = self.record()
        self.assertEqual(row['observed_task_outcome'], 'success')
        self.assertEqual(row['task_outcome'], 'unknown')
        self.assertFalse(row['scorable'])
        self.assertTrue(row['started'])
        counts = report.aggregate([row])['all scheduled slots']
        self.assertEqual((counts['observed_evaluator_successes'], counts['observed_successes_among_invalid'],
                          counts['authenticated_assessments'], counts['started']), (1, 1, 1, 1))
        self.assertEqual((counts['successes'], counts['valid']), (0, 0))
        self.assertIsNone(counts['wilson95'])
        self.assertEqual(counts['all_planned_bounds'], [0., 1.])

    def test_failed_queue_cannot_contribute_observed_completion(self):
        receipt = self.receipt('failed', 1)
        queue = json.loads(receipt.read_text())
        queue['started_at'] = None
        self.save(receipt, queue)
        self.save(self.folder / 'assessment.json', {'observed_task_outcome': 'success'})
        row = self.record()
        counts = report.aggregate([row])['all scheduled slots']
        self.assertEqual(row['observed_task_outcome'], 'not_assessed')
        self.assertEqual(counts['observed_evaluator_successes'], 0)
        self.assertEqual(counts['authenticated_assessments'], 0)
        self.assertEqual(counts['started'], 0)

    def test_stopped_allocation_keeps_unrun_preselected_examples(self):
        runs = [{'ordinal': i, 'run_id': str(i), 'execution_status': 'completed' if i <= 10 else 'not_run',
                 'started': i <= 10, 'reason': 'Two consecutive infrastructure-invalid attempts',
                 'family': 'misplaced-stock' if i % 2 else 'blocked-insert-home',
                 'examples': [], 'validity': 'unknown', 'scorable': False} for i in range(1, 21)]
        report.select_examples(runs)
        stop = report.stop_summary(runs)
        self.assertEqual((stop['not_run_count'], stop['first_unrun_ordinal'], stop['last_started_ordinal']), (10, 11, 10))
        self.assertEqual(stop['preselected_unrun_ids'], ['19', '20'])
        self.assertEqual(stop['reason'], 'Two consecutive infrastructure-invalid attempts')

    def test_program_invocation_count_deduplicates_admission_and_final_receipts(self):
        source = '5ed894a33d7555ee5c4e5533885841e903b2ae210fdce69d6369226c66d0876e'
        runs = [{'run_id': 'synthetic', 'family': 'misplaced-stock', 'examples': [],
                 'validity': 'valid', 'scorable': True, 'task_outcome': 'success',
                 'programs': {'one.admitted.json': {'run_id': 'one', 'record_kind': 'admission',
                    'source_sha256': source, 'final_record': 'one.json'},
                    'one.json': {'run_id': 'one', 'record_kind': 'final', 'source_sha256': source}}}]
        report.select_examples(runs)
        summary = runs[0]['program_summary']
        self.assertEqual((summary['unique_invocation_count'], summary['receipt_count']), (1, 2))
        self.assertIn('no robot actuation calls', summary['scope'])
        self.assertIn('Outcome-selected first behavior: bounded program invocation', runs[0]['examples'])
        self.assertNotIn('program admission without retained final receipt', runs[0]['inspection_categories'])


if __name__ == '__main__':
    unittest.main()
