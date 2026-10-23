"""Synthetic counterexamples for formulas/provenance; these are not robot runs."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import diagnostics as d


def event(eid,kind,payload,time=0.,parents=None):
    return {'schema_version':'robot-evidence-1.0','run_id':'unit-only','event_id':eid,'event_type':kind,
            'sim_time_s':time,'wall_elapsed_s':time,'source':'supervisor','parent_ids':parents or [],'payload':payload,
            'payload_sha256':hashlib.sha256(d.canonical(payload)).hexdigest()}


def physical(eid,kind,time,**fields):
    return event(eid,'physical_service_event',{'type':kind,'sim_time':time,**fields},time)


def motion(duration=1.,position=lambda t:t):
    rows=[]
    for i in range(round(duration/.01)+1):
        t=i*.01;x=position(t)
        rows.append({'sim_time_s':t,'tcp':[x,0.,0.],'q':[x,0.,0.,0.,0.,0.,0.],
                     'dq':[1.,0.,0.,0.,0.,0.,0.],'effort':[2.,0.,0.,0.,0.,0.,0.],
                     'target':[x+.1,0.,0.,0.,0.,0.,0.]})
    return rows


def transport_events(end=1.):
    return [event(1,'action_requested',{'operation':'transport','request_id':'move-1','part_id':'part-1','destination':'tray1'},0.),
            physical(2,'trajectory_dispatched',0.,request_id='move-1'),
            physical(3,'feedback',end,request_id='move-1',status='completed',reason='trajectory ended; physical outcome requires observation')]


class MotionTests(unittest.TestCase):
    def test_cubic_has_exact_interior_jerk_and_explicit_boundary_loss(self):
        result=d.jerk_for_segment(motion(position=lambda t:t**3),0.,1.)
        self.assertAlmostEqual(result['analysis_support_s'],.93)
        self.assertAlmostEqual(result['squared_jerk_integral']['value'],36*.93,places=6)
        self.assertAlmostEqual(result['dimensionless_jerk']['value'],36*.93,places=6)
        self.assertAlmostEqual(result['excluded_boundary_duration_s'],.07)
        self.assertEqual(result['path_length_m'],1.)

    def test_constant_velocity_has_negligible_jerk_without_endpoint_padding(self):
        result=d.jerk_for_segment(motion(),0.,1.)
        self.assertLess(result['squared_jerk_integral']['value'],1e-12)

    def test_near_zero_path_omits_normalization_instead_of_dividing(self):
        result=d.jerk_for_segment(motion(position=lambda t:0.),0.,1.)
        self.assertEqual(result['squared_jerk_integral']['value'],0.)
        self.assertIsNone(result['dimensionless_jerk']['value'])
        self.assertIn('1 mm',result['omission_reason'])

    def test_gap_is_never_interpolated_for_jerk_or_path(self):
        rows=motion(position=lambda t:0. if t<.5 else 1.);rows.pop(50)
        result=d.jerk_for_segment(rows,0.,1.)
        self.assertIsNone(result['squared_jerk_integral']['value'])
        self.assertIn('gap',result['omission_reason'])
        measured,pauses=d.motion_metrics(rows)
        self.assertEqual(measured['non_nominal_sample_intervals'],1)
        self.assertEqual(measured['tcp_path_m']['value'],0.)  # Unknown travel across gap omitted.

    def test_joint_travel_effort_tracking_are_measured_not_saturation(self):
        result,_=d.motion_metrics(motion())
        self.assertAlmostEqual(result['joint_travel_total_rad']['value'],1.)
        self.assertAlmostEqual(result['filtered_joint_speed_peak']['value'][0],1.)
        self.assertAlmostEqual(result['joint_tracking_rms']['value'][0],.1)
        self.assertEqual(result['sampled_effort_peak']['value'][0],2.)
        self.assertIsNone(result['effort_saturation']['value'])

    def test_missing_telemetry_and_empty_motion_do_not_become_zero(self):
        rows=motion()
        for row in rows:row.pop('effort');row.pop('target')
        result,_=d.motion_metrics(rows)
        self.assertIsNone(result['sampled_effort_peak']['value'])
        self.assertIsNone(result['joint_tracking_rms']['value'])
        report=d.analyze([],[],{'run_id':'unit-only'},{})
        self.assertIsNone(report['motion']['tcp_path_m']['value'])
        self.assertIsNone(report['pauses']['observed_low_motion_time_s'])

    def test_nonmonotonic_motion_is_refused(self):
        rows=motion();rows[2]['sim_time_s']=rows[1]['sim_time_s']
        with self.assertRaises(d.DiagnosticError):d.motion_metrics(rows)

    def test_completed_trajectory_is_not_a_verified_transfer(self):
        result=d.transport_metrics(transport_events(),motion())
        self.assertEqual(result['complete_uninterrupted_count'],1)
        self.assertIsNone(result['segments'][0]['physical_transfer_success'])

    def test_restart_invalidates_jerk_even_if_terminal_feedback_says_completed(self):
        events=transport_events();events.insert(2,event(4,'restart_begin',{'cut':'release'},.5))
        result=d.transport_metrics(events,motion())
        self.assertEqual(result['normalized_jerk_usable_count'],0)
        self.assertIn('Restart',result['segments'][0]['motion']['omission_reason'])

    def test_incomplete_or_unclocked_dispatch_cannot_get_jerk(self):
        for events in (transport_events()[:-1],transport_events()):
            if len(events)==3:events[1]['payload'].pop('sim_time')
            result=d.transport_metrics(events,motion())
            self.assertEqual(result['normalized_jerk_usable_count'],0)

    def test_model_overlap_does_not_prove_pause_cause_or_eligibility(self):
        events=[event(1,'model_request',{'messages':[]},.1),event(2,'model_response',{'result':{'usage':{'total_tokens':10}}},.9,[1])]
        report=d.analyze(events,motion(position=lambda t:0.),{'run_id':'unit-only'},{})
        pause=report['pauses']['intervals'][0]
        self.assertGreater(pause['model_wait_overlap_s'],.7)
        self.assertEqual(pause['causal_labels'],['unknown'])
        self.assertIsNone(pause['work_eligible'])
        self.assertIsNone(report['pauses']['eligible_pause_time']['value'])

    def test_only_explicit_covering_annotation_supplies_causal_label(self):
        events=[event(1,'pause_annotation',{'start_sim_s':0.,'end_sim_s':1.,'category':'physical_required','work_eligible':True,'basis':'explicit synthetic process-stage annotation'},0.)]
        report=d.analyze(events,motion(position=lambda t:0.),{'run_id':'unit-only'},{})
        self.assertEqual(report['pauses']['intervals'][0]['causal_labels'],['physical_required'])
        self.assertGreater(report['pauses']['eligible_pause_time']['value'],.9)

    def test_candidate_pause_claim_is_not_an_independent_causal_annotation(self):
        events=[event(1,'pause_annotation',{'start_sim_s':0.,'end_sim_s':1.,'category':'reasoning_wait','work_eligible':True,'basis':'candidate says so'},0.)]
        events[0]['source']='candidate'
        report=d.analyze(events,motion(position=lambda t:0.),{'run_id':'unit-only'},{})
        self.assertEqual(report['pauses']['intervals'][0]['causal_labels'],['unknown'])


class EventTests(unittest.TestCase):
    def test_failed_model_call_keeps_total_tokens_unknown_and_cache_not_assumed(self):
        events=[event(1,'model_request',{'messages':[{'role':'user','content':'private prompt'}]},0.),
                event(2,'model_response',{'result':{'usage':{'total_tokens':17,'prompt_tokens':10,'completion_tokens':7},'latency_s':.5,'identity':{'prompt_cache_enabled':False}}},.5,[1]),
                event(3,'model_request',{'messages':[]},.6),event(4,'model_error',{'error':'timeout'},1.,[3])]
        result,_=d.model_metrics(events)
        self.assertEqual(result['known_total_tokens'],17);self.assertEqual(result['calls_with_unknown_tokens'],1)
        self.assertIsNone(result['total_tokens']['value']);self.assertIsNone(result['cache_hit_calls']['value'])
        self.assertNotIn('private prompt',json.dumps(result))

    def test_duplicate_terminal_response_is_not_double_counted(self):
        events=[event(1,'model_request',{'messages':[]},0.),
                event(2,'model_response',{'result':{'usage':{'total_tokens':10}}},.2,[1]),
                event(3,'late_model_response',{'result':{'usage':{'total_tokens':10}}},.3,[1])]
        result,_=d.model_metrics(events)
        self.assertIsNone(result['total_tokens']['value']);self.assertEqual(result['known_total_tokens'],0)

    def test_late_response_is_accounted_but_not_called_delivery(self):
        events=[event(1,'model_request',{'messages':[]},0.),
                event(2,'late_model_response',{'after_episode_end':True,'stale':False,'result':{'usage':{'total_tokens':10},'latency_s':2.}},1.,[1])]
        result,_=d.model_metrics(events)
        self.assertEqual(result['total_tokens']['value'],10)
        self.assertTrue(result['calls'][0]['after_episode_end'])

    def test_only_exact_delivered_sequence_and_incarnation_support_action_age(self):
        packet={'sequence':4,'incarnation':2,'capture_sim_time_s':.1}
        events=[event(1,'candidate_input',{'message':{'type':'step','packet':packet}},.2),
                event(2,'action_requested',{'request_id':'a','operation':'transport','observation_sequence':4,'incarnation':2},.3),
                physical(3,'trajectory_dispatched',.5,request_id='a')]
        age=d.responsiveness(events)['action_observation_ages'][0]
        self.assertAlmostEqual(age['acquisition_to_dispatch_sim_s'],.4)
        self.assertIsNone(age['actuation_wall_age_s'])
        events[1]['payload']['incarnation']=3
        self.assertIsNone(d.responsiveness(events)['action_observation_ages'][0]['acquisition_to_dispatch_sim_s'])

    def test_packet_without_acquisition_time_is_unknown_not_current(self):
        events=[event(1,'candidate_input',{'message':{'type':'step','packet':{'sequence':1,'incarnation':1}}},.5)]
        self.assertIsNone(d.responsiveness(events)['packet_deliveries'][0]['acquisition_to_delivery_sim_s'])

    def test_cycle_busy_time_uses_union_and_flags_overlaps(self):
        events=[physical(1,'feedback',0.,request_id='a',cycle_id=1,status='completed',reason='cycle accepted'),
                physical(2,'feedback',1.,request_id='b',cycle_id=2,status='completed',reason='cycle accepted'),
                physical(3,'cycle_complete',2.,cycle_id=1),physical(4,'cycle_complete',3.,cycle_id=2)]
        result=d.process_metrics(events,4.)
        self.assertEqual(result['observed_busy_time']['value'],3.)
        self.assertEqual(result['overlapping_cycle_interval_pairs'],1)
        self.assertIsNone(result['productive_utilization']['value'])

    def test_unfinished_cycle_busy_interval_is_right_censored(self):
        events=[physical(1,'feedback',1.,request_id='a',cycle_id=1,status='completed',reason='cycle accepted')]
        result=d.process_metrics(events,3.)
        self.assertTrue(result['intervals'][0]['right_censored']);self.assertEqual(result['observed_busy_time']['value'],2.)

    def test_repeated_processing_is_not_automatically_avoidable_duplicate(self):
        events=[event(1,'action_requested',{'request_id':'a','operation':'cycle','part_id':'p','recipe':'A'},0.),
                event(2,'action_admission',{'request_id':'a','status':'accepted'},0.),
                event(3,'action_requested',{'request_id':'b','operation':'cycle','part_id':'p','recipe':'A'},1.),
                event(4,'action_admission',{'request_id':'b','status':'accepted'},1.),
                event(5,'restart_begin',{'cut':'deadline_fallback'},2.)]
        result=d.event_metrics(events,{'scenario':'restart'},{})
        self.assertEqual(result['repeated_cycle_admissions_same_part_recipe'],1)
        self.assertIsNone(result['avoidable_duplicate_work']['value'])
        self.assertEqual(result['interventions']['restart_deadline_fallback_count'],1)
        self.assertIsNone(result['interventions']['admissible_exposure_count']['value'])


class CurrentExposureTests(unittest.TestCase):
    def test_nested_milestone_is_not_silently_promoted_to_admissibility(self):
        e=event(1,'restart_begin',{'exposure':{'actual_cut':'after_release',
            'configured_milestone_exercised':True,'fallback_used':False}},2.)
        result=d.event_metrics([e],{'scenario':'restart'},{})['interventions']
        self.assertEqual(result['restart_release_cut_count'],1)
        self.assertEqual(result['restart_configured_milestone_exercised_count'],1)
        self.assertEqual(result['restart_actual_cut_counts'],{'after_release':1})
        self.assertIsNone(result['admissible_exposure_count']['value'])
        self.assertEqual(result['unknown_admissibility_count'],1)

    def test_declared_scenario_list_retains_records_without_inventing_recovery(self):
        records=[{'event_id':'order-event-release-late-A','order_version':2,'trigger':'fixed_deadline_fallback',
                  'fallback_used':True,'milestone_satisfied':False,'distinct_completed_B_count':4}]
        exposure=event(2,'scenario_exposure',records,420.5,[1]);exposure['source']='evaluator'
        events=[event(1,'order_amendment',{'event_id':'order-event-release-late-A','order_version':2},420.5),exposure]
        d.validate_events(events,'unit-only')
        report=d.analyze(events,[],{'run_id':'unit-only'},{'scenario':'nominal'})
        result=report['events']['interventions']
        self.assertEqual(result['scenario_exposure_event_count'],1)
        self.assertEqual(result['scenario_exposure_record_count'],1)
        self.assertEqual(result['scenario_exposure_records'][0]['exposure'],records[0])
        self.assertEqual(result['scenario_exposure_records'][0]['event_id'],2)
        self.assertEqual(result['restart_begin_count'],0)
        self.assertEqual(result['unknown_admissibility_count'],1)
        self.assertIsNone(result['admissible_exposure_count']['value'])
        self.assertIsNone(result['successful_recovery_count']['value'])

    def test_list_exception_is_limited_to_protected_scenario_objects(self):
        for kind,payload,source in (('candidate_reply',[], 'candidate'),('retired_candidate_reply',None,'candidate_runtime'),
                                    ('scenario_exposure',[], 'evaluator'),('scenario_exposure',[None],'evaluator'),
                                    ('scenario_exposure',[{}],'candidate'),('scenario_exposure','invalid','evaluator')):
            row=event(1,kind,payload);row['source']=source
            with self.assertRaises(d.DiagnosticError):d.validate_events([row],'unit-only')

    def test_scenario_list_keeps_hash_chain_and_clock_checks(self):
        original=event(1,'scenario_exposure',[{'event_id':'synthetic-order-event'}]);original['source']='evaluator'
        for change in (lambda e:e['payload'][0].update(changed=True),lambda e:e.update(parent_ids=[999]),
                       lambda e:e.update(event_id=2),lambda e:e.update(sim_time_s=float('nan'))):
            row=copy.deepcopy(original);change(row)
            with self.assertRaises(d.DiagnosticError):d.validate_events([row],'unit-only')


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.addCleanup(self.temp.cleanup)
        (self.root/'manifest.json').write_text(json.dumps({'run_id':'unit-only','seeds':{'world_seed':'private seed'}}))
        (self.root/'result.json').write_text(json.dumps({'run_id':'unit-only','validity':'unknown','model_calls':0}))
        (self.root/'events.jsonl').write_text(json.dumps(event(1,'initial_world',{'private_state':'not copied'},0.))+'\n')
        (self.root/'motion.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in motion()))

    def test_source_hashes_retained_and_private_input_bodies_not_copied(self):
        report=d.diagnose_directory(self.root)
        self.assertEqual(set(report['sources']),{'manifest.json','result.json','events.jsonl','motion.jsonl'})
        self.assertEqual(report['recorded_outcome']['validity'],'unknown')
        self.assertNotIn('private seed',json.dumps(report));self.assertNotIn('not copied',json.dumps(report))
        self.assertEqual(report['sources']['motion.jsonl']['sha256'],hashlib.sha256((self.root/'motion.jsonl').read_bytes()).hexdigest())

    def test_event_hash_tampering_is_refused(self):
        path=self.root/'events.jsonl';e=json.loads(path.read_text());e['payload']['private_state']='changed';path.write_text(json.dumps(e)+'\n')
        with self.assertRaisesRegex(d.DiagnosticError,'hash'):d.diagnose_directory(self.root)

    def test_dangling_parent_is_refused(self):
        path=self.root/'events.jsonl';e=json.loads(path.read_text());e['parent_ids']=[999];path.write_text(json.dumps(e)+'\n')
        with self.assertRaisesRegex(d.DiagnosticError,'parent'):d.diagnose_directory(self.root)

    def test_changed_source_cannot_be_published_from_stale_analysis(self):
        report=d.diagnose_directory(self.root)
        (self.root/'motion.jsonl').write_text('')
        with self.assertRaisesRegex(d.DiagnosticError,'changed'):d.write_report(report,self.root/'diagnostic.json')
        self.assertFalse((self.root/'diagnostic.json').exists())

    def test_outputs_are_exclusive_and_cannot_enter_candidate_state(self):
        report=d.diagnose_directory(self.root);path=self.root/'diagnostic.json'
        d.write_report(report,path)
        with self.assertRaises(FileExistsError):d.write_report(report,path)
        with self.assertRaisesRegex(d.DiagnosticError,'candidate'):d.write_report(report,self.root/'candidate_state'/'private.json')

    def test_no_nonfinite_json_is_accepted(self):
        (self.root/'result.json').write_text('{"run_id":"unit-only","wall_duration_s":NaN}')
        with self.assertRaises(d.DiagnosticError):d.diagnose_directory(self.root)


if __name__=='__main__':unittest.main()
