"""Small supervisor regression checks. No simulator, model or queue job runs."""
from concurrent.futures import Future
import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import experiment
import sandbox


class Clock:
    def __init__(self):self.t=0.
    def now(self):self.t+=.002;return self.t


class FakeResourceSampler:
    """No OS/GPU reads; records lifecycle and creates exact fixture evidence."""
    instances=[]
    def __init__(self,path,**kwargs):
        self.path=Path(path);self.kwargs=kwargs;self.period_s=5.;self.closed=False;self.started=False
        self.instances.append(self)
    def start(self):
        self.started=True;self.path.write_text('{"fixture":true}\n',encoding='utf-8');return self
    def close(self):self.closed=True
    def latest(self):return None
    def summary(self):return {'sample_count':1,'failure':None,'sampler_stopped':self.closed,'resource_caps_enforced':False}


class DeferredModelFuture:
    """Unready inside the episode, completed when cleanup awaits the result."""
    def __init__(self,error=None):self.error=error
    def done(self):return False
    def result(self,timeout=None):
        if self.error:raise self.error
        return {'text':'{"operation":"wait"}','usage':{'total_tokens':17}}


class ImmediateExecutor:
    def __init__(self,model,deferred):self.model=model;self.deferred=deferred;self.model_kwargs=[]
    def submit(self,function,*args,**kwargs):
        if function==self.model.complete:self.model_kwargs.append(kwargs);return self.deferred
        future=Future()
        try:future.set_result(function(*args,**kwargs))
        except BaseException as exc:future.set_exception(exc)
        return future
    def shutdown(self,**kwargs):pass


def fake_cell(clock=None, sense_error=None):
    cell=MagicMock()
    cell.data.time=0.;cell.data.qpos=np.zeros(16);cell.data.qvel=np.zeros(16)
    cell.data.actuator_force=np.zeros(9);cell.data.ctrl=np.zeros(9)
    cell.data.site_xpos=np.zeros((1,3));cell.tcp=0
    cell.total_path=0.;cell.contact_peak=0.;cell.collision_impulse=0.
    cell.events=[];cell.feedback=[];cell.segment=None;cell.active_request=None
    cell.truth={}
    cell.evaluator=SimpleNamespace(first_success=None)
    cell.tick.side_effect=lambda:setattr(cell.data,'time',cell.data.time+.002)
    cell.outcome.return_value={'success':False,'accepted_count':0,'accepted':{},'reasons':['fixture unfinished']}
    cell.truth_snapshot.return_value={}
    cell.public_packet.return_value={'sequence':1,'sim_time':.5,'detections':[]}
    cell.public_arm_interfaces.return_value={'interfaces':{},'resource':{'direct_control_active':False}}
    def sense():
        if sense_error:raise sense_error
        if clock:clock.t+=.2
        return [],np.zeros((2,2,3),dtype=np.uint8),np.zeros((2,2),dtype=np.float32)
    cell.sense.side_effect=sense
    cell.sensor_worker.wait.return_value=None
    cell.sensor_worker.busy=False
    cell.request_sense.return_value={'accepted':True}
    def poll():
        _,rgb,depth=sense()
        return SimpleNamespace(sequence=1,camera='overhead',capture_sim_time_s=cell.data.time,capture_wall_elapsed_s=0.,
                               rgb=rgb,depth=depth,calibration={'camera':'overhead','width_px':2,'height_px':2},
                               capture_telemetry={'sim_time_s':cell.data.time},artifacts={},
                               worker_finished_monotonic_s=0.,worker_started_monotonic_s=0.)
    cell.poll_sense.side_effect=poll
    return cell


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        FakeResourceSampler.instances=[]
        self.resources_patch=patch.object(experiment,'ResourceSampler',FakeResourceSampler)
        self.resources_patch.start();self.addCleanup(self.resources_patch.stop)
        self.initial_patch=patch.object(experiment,'initial_world_report',return_value={'valid':True,'errors':[],'scope':'synthetic test fixture'})
        self.initial_patch.start();self.addCleanup(self.initial_patch.stop)

    def test_seeds_are_independent_and_legacy_alias_is_checked(self):
        self.assertEqual(experiment.resolve_seeds(seed=7,policy_noise_seed=19),(7,19))
        self.assertEqual(experiment.resolve_seeds(world_seed=3),(3,0))
        with self.assertRaisesRegex(ValueError,'disagree'):experiment.resolve_seeds(seed=7,world_seed=8)
        with self.assertRaises(ValueError):experiment.resolve_seeds(policy_noise_seed=-1)

    def test_assistance_requires_both_clocks_and_is_durable_idempotent(self):
        service=experiment.ScriptedAssistance()
        action={'request_id':'help-1','reason':'unknown outcome','evidence':{'sequence':3},'requested_information_or_action':'safe public reconciliation'}
        self.assertEqual(service.request(action,10.,1.,4)['status'],'accepted')
        self.assertTrue(service.request(action,11.,2.,5)['duplicate_suppressed'])
        self.assertEqual(service.advance(25.,15.9),[])
        self.assertEqual(service.advance(24.9,16.),[])
        answers=service.advance(25.,16.)
        self.assertEqual(len(answers),1);self.assertEqual(answers[0]['wait_wall_s'],15.)
        self.assertEqual(service.advance(100.,100.),[])
        packet=service.public_answers();packet[0]['content']='mutated'
        self.assertEqual(service.public_answers()[0]['content'],service.ANSWER)
        self.assertEqual(service.summary(100.)['requests'],1)
        self.assertIsNone(service.summary(100.)['actual_human_time_s'])

    def test_malformed_help_is_counted_without_answer_or_hidden_rescue(self):
        service=experiment.ScriptedAssistance()
        feedback=service.request({'request_id':'help-1','reason':'unknown'},0.,0.,1)
        self.assertEqual(feedback['status'],'rejected')
        self.assertEqual(service.advance(16.,16.),[])
        self.assertTrue(service.summary(16.)['any_help_requested'])
        self.assertEqual(service.summary(16.)['physical_rescue_actions'],0)

    def test_wall_stall_cannot_disappear_from_lag(self):
        timing=experiment.TimingMonitor()
        timing.observe(.2,0.)
        timing.observe(1.2,1.)
        report=timing.report()
        self.assertGreaterEqual(report['maximum_lag_s'],.199)
        self.assertFalse(report['actual_host_timing_pass'])
        self.assertEqual(report['complete_wall_windows'],1)
        self.assertAlmostEqual(report['timing'][0]['real_time_factor'],.8)

    def test_matching_clocks_pass_complete_windows(self):
        timing=experiment.TimingMonitor()
        for i in range(1,251):timing.observe(i*.01,i*.01)
        report=timing.report()
        self.assertTrue(report['actual_host_timing_pass'])
        self.assertAlmostEqual(report['trailing_partial_window_s'],.5)

    def test_pending_restart_worker_is_closed(self):
        old=MagicMock();fresh=MagicMock();pending=Future();pending.set_result(fresh)
        self.assertEqual(experiment.close_pending_restart(pending,'restart',old),[])
        old.close.assert_called_once();fresh.close.assert_called_once()

    def test_late_restart_after_cleanup_timeout_is_still_closed(self):
        old=MagicMock();fresh=MagicMock();pending=Future()
        errors=experiment.close_pending_restart(pending,'restart',old,timeout=.001)
        self.assertTrue(errors)
        pending.set_result(fresh)
        fresh.close.assert_called_once()

    def test_candidate_input_records_exact_supplied_message(self):
        worker=MagicMock();worker.receive.return_value={'type':'step','response':None}
        evidence=MagicMock();evidence.emit.return_value=8
        message={'type':'step','packet':{'sequence':5,'age_s':.123}}
        reply=experiment.candidate_call(worker,message,evidence,lambda:1.5,[3])
        evidence.emit.assert_called_once_with('candidate_input',{'message':message},1.5,'candidate_gateway',[3])
        worker.send.assert_called_once_with(message)
        self.assertEqual(reply['supervisor_input_event_id'],8)

    def test_initialization_failure_retains_terminal_result(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(experiment,'EVIDENCE',Path(directory)), patch.object(experiment,'Cell',side_effect=RuntimeError('fixture setup failed')), contextlib.redirect_stdout(io.StringIO()):
            result=experiment.run_episode(run_id='startup-failure')
            saved=json.loads((Path(directory)/'startup-failure'/'result.json').read_text())
        self.assertEqual(result,saved)
        self.assertEqual(result['failure_class'],'infrastructure_failure')
        self.assertEqual(result['validity'],'invalid')
        self.assertIsNone(result['wall_duration_s'])
        self.assertIsNone(result['independent_outcome'])
        self.assertTrue(FakeResourceSampler.instances[0].closed)
        self.assertEqual(result['resources']['path'],'resources.jsonl')
        self.assertEqual(len(result['resources']['sha256']),64)

    def test_render_failure_retains_terminal_result(self):
        cell=fake_cell(sense_error=RuntimeError('render failed'));worker=MagicMock()
        with tempfile.TemporaryDirectory() as directory, patch.object(experiment,'EVIDENCE',Path(directory)), patch.object(experiment,'Cell',return_value=cell), patch.object(sandbox,'CandidateSandbox',return_value=worker), contextlib.redirect_stdout(io.StringIO()):
            result=experiment.run_episode(run_id='render-failure',cap=.1)
        self.assertEqual(result['failure_class'],'infrastructure_failure')
        self.assertIn('render failed',result['error'])
        worker.close.assert_called_once();cell.close.assert_called_once()
        self.assertEqual(len(FakeResourceSampler.instances),1)
        self.assertTrue(FakeResourceSampler.instances[0].closed)

    def test_sensor_latency_is_in_final_actual_host_timing(self):
        clock=Clock();cell=fake_cell(clock);worker=MagicMock()
        worker.receive.return_value={'type':'step','response':None};worker.alive=True
        with tempfile.TemporaryDirectory() as directory, patch.object(experiment,'EVIDENCE',Path(directory)), patch.object(experiment,'Cell',return_value=cell), patch.object(sandbox,'CandidateSandbox',return_value=worker), patch.object(experiment.time,'perf_counter',side_effect=clock.now), patch.object(experiment,'write_png'), patch.object(experiment.np,'savez_compressed'), contextlib.redirect_stdout(io.StringIO()):
            result=experiment.run_episode(run_id='sensor-stall',cap=.1)
        self.assertGreater(result['maximum_lag_s'],.1)
        self.assertEqual(result['validity'],'invalid')
        cell.renew_authority.assert_called_once_with(1,1)

    def late_model_run(self,error=None):
        clock=Clock();cell=fake_cell();worker=MagicMock();worker.alive=True
        worker.receive.return_value={'type':'step','response':{'type':'model','messages':[{'role':'user','content':'wait'}],'schema':{'type':'object'}}}
        model=MagicMock();model.identity={'test_fixture':True};model.config.request_timeout_s=.01
        executor=ImmediateExecutor(model,DeferredModelFuture(error))
        with tempfile.TemporaryDirectory() as directory, patch.object(experiment,'EVIDENCE',Path(directory)), patch.object(experiment,'Cell',return_value=cell), patch.object(sandbox,'CandidateSandbox',return_value=worker), patch.object(experiment,'ThreadPoolExecutor',return_value=executor), patch.object(experiment.time,'perf_counter',side_effect=clock.now), patch.object(experiment,'write_png'), patch.object(experiment.np,'savez_compressed'), contextlib.redirect_stdout(io.StringIO()):
            result=experiment.run_episode(kind='A1',model=model,run_id='late-model',cap=.15,world_seed=12,policy_noise_seed=37)
            events=[json.loads(line) for line in (Path(directory)/'late-model'/'events.jsonl').read_text().splitlines()]
        self.assertEqual(executor.model_kwargs[0]['seed'],37)
        self.assertEqual(result['world_seed'],12)
        self.assertEqual(result['policy_noise_seed'],37)
        return result,events,model

    def test_model_tokens_finishing_after_cap_are_accounted_without_delivery(self):
        result,events,model=self.late_model_run()
        self.assertEqual(result['model_calls'],1)
        self.assertEqual(result['late_model_responses'],1)
        self.assertEqual(result['total_tokens'],17)
        self.assertTrue(result['model_accounting_complete'])
        self.assertTrue(any(e['event_type']=='late_model_response' and e['payload']['after_episode_end'] for e in events))
        self.assertFalse(any(e['event_type']=='candidate_input' and e['payload']['message']['type']=='model_response' for e in events))

    def test_failed_late_model_call_has_missing_token_count(self):
        result,events,model=self.late_model_run(TimeoutError('model timed out'))
        self.assertEqual(result['model_failed_calls'],1)
        self.assertIsNone(result['total_tokens'])
        self.assertEqual(result['unknown_token_calls'],1)
        self.assertFalse(result['model_accounting_complete'])
        model.stop.assert_called_once()

    def test_delivery_packet_keeps_capture_metadata_on_later_candidate_steps(self):
        capture=SimpleNamespace(capture_sim_time_s=2.,capture_wall_elapsed_s=1.5,sequence=7,
                                calibration={'pose':'synthetic'},capture_telemetry={'sim_time_s':2.})
        first=experiment.sensor_delivery_packet({'detections':[]},capture,delivery_sim_s=2.1,delivery_wall_s=1.6)
        later=experiment.sensor_delivery_packet({'detections':[]},capture,delivery_sim_s=2.3,delivery_wall_s=1.8)
        self.assertEqual(first['camera_calibration'],later['camera_calibration'])
        self.assertEqual(later['capture_wall_elapsed_s'],1.5)
        self.assertEqual(later['delivery_wall_elapsed_s'],1.8)
        self.assertAlmostEqual(later['camera_frame_age_sim_s'],.3)

    def test_terminal_receipt_retention_is_measured_from_terminal_time(self):
        lifecycle={'r':{'time':0.,'feedback':{'status':'accepted'}}}
        experiment.terminal_receipt(lifecycle,{'request_id':'r','status':'completed','sim_time':75.})
        self.assertEqual(lifecycle['r']['time'],75.)
        self.assertLessEqual(134.9-lifecycle['r']['time'],60.)
        self.assertGreater(135.1-lifecycle['r']['time'],60.)

    def test_candidate_usage_aggregates_incarnations_without_hiding_missing_tail(self):
        usage=experiment.CandidateUsage()
        def message(cpu,rss):return {'runtime_usage':{'user_cpu_s':cpu,'system_cpu_s':cpu/2,
            'maximum_rss_bytes':rss,'input_blocks':0,'output_blocks':3}}
        usage.observe(1,message(1.,100),event_id=3)
        usage.observe(1,message(2.,120),event_id=9)
        usage.observe(2,message(.5,90),event_id=15)
        usage.observe(3,{})
        result=usage.summary()
        self.assertEqual(result['known_user_cpu_s'],2.5)
        self.assertEqual(result['observed_maximum_rss_bytes'],120)
        self.assertEqual(result['expected_incarnations'],3)
        self.assertEqual(result['observed_incarnations'],2)
        self.assertFalse(result['complete']);self.assertTrue(result['missing_final_interval'])

    def test_evaluation_requires_exact_issued_context_and_uses_its_directory(self):
        import release_runner as runner
        seeds={'world_seed':2**40,'layout_seed':2**41,'noise_seed':2**42,'policy_seed':17}
        manifest={'run_id':'eval-synthetic','architecture':'A1','parts':3,'cap_s':12.,
                  'condition':'persistent','scenario':'nominal','seeds':seeds}
        with tempfile.TemporaryDirectory() as directory:
            context=runner.VerifiedEvaluationContext(Path(directory),json.dumps(manifest),'r'*64,'m'*64,
                'synthetic-queue','synthetic-time','{}',runner._AUTHORITY)
            kwargs=dict(kind='A1',n=3,cap=12.,condition='persistent',scenario='nominal',run_id='eval-synthetic',seeds=seeds)
            path,provenance=experiment.authorized_evidence_path('evaluation',context,**kwargs)
            self.assertEqual(path,context.evidence_dir)
            self.assertEqual(provenance['queue_job_id'],'synthetic-queue')
            with self.assertRaises(ValueError):experiment.authorized_evidence_path('evaluation',None,**kwargs)
            with self.assertRaises(runner.ReleaseError):experiment.authorized_evidence_path('evaluation',context,**{**kwargs,'cap':13.})
            forged=runner.VerifiedEvaluationContext(Path(directory),json.dumps(manifest),'r','m','q','t','{}')
            with self.assertRaises(runner.ReleaseError):experiment.authorized_evidence_path('evaluation',forged,**kwargs)
            state=path/'candidate_state';state.mkdir(parents=True)
            self.assertEqual(experiment.assert_candidate_state_path(state,path),state.resolve())
            with self.assertRaises(ValueError):experiment.assert_candidate_state_path(path/'other',path)
            with self.assertRaises(runner.ReleaseError):experiment.authorized_evidence_path('evaluation',context,**kwargs)

    def test_evaluator_success_near_cap_has_no_second_supervisor_dwell(self):
        clock=Clock();cell=fake_cell();worker=MagicMock();worker.alive=True
        outcome={'success':True,'accepted_count':3,'accepted':{},'reasons':[]}
        def checked(*args,**kwargs):
            if cell.evaluator.first_success is None:
                cell.evaluator.first_success={'sim_time_s':cell.data.time,'wall_monotonic_s':clock.t,
                    'protected_snapshot':{'synthetic':True},'outcome':outcome}
            return outcome
        cell.outcome.side_effect=checked
        worker.receive.return_value={'type':'step','response':{'type':'wait'}}
        with tempfile.TemporaryDirectory() as directory, patch.object(experiment,'EVIDENCE',Path(directory)), patch.object(experiment,'Cell',return_value=cell), patch.object(sandbox,'CandidateSandbox',return_value=worker), patch.object(experiment.time,'perf_counter',side_effect=clock.now), contextlib.redirect_stdout(io.StringIO()):
            result=experiment.run_episode(run_id='synthetic-dwell',cap=.09)
        self.assertEqual(result['outcome'],'success')
        self.assertLess(result['completion_time_s'],.5)
        self.assertLessEqual(result['completion_time_s'],result['wall_duration_s'])
        self.assertEqual(result['completion_landmark']['sim_time_s'],result['completion_sim_time_s'])

    def test_native_tick_completion_stops_before_later_poll_and_cap(self):
        clock=Clock();cell=fake_cell();worker=MagicMock();worker.alive=True
        captured=[]
        def tick():
            cell.data.time+=.002
            if cell.data.time>=.512-1e-9 and cell.evaluator.first_success is None:
                marker={'sim_time_s':cell.data.time,'wall_monotonic_s':clock.t,
                        'protected_snapshot':{'synthetic':True},'outcome':{'success':True,'accepted_count':3}}
                cell.evaluator.first_success=marker;captured.append(marker)
        cell.tick.side_effect=tick
        worker.receive.return_value={'type':'step','response':{'type':'wait'}}
        with tempfile.TemporaryDirectory() as directory, patch.object(experiment,'EVIDENCE',Path(directory)), patch.object(experiment,'Cell',return_value=cell), patch.object(sandbox,'CandidateSandbox',return_value=worker), patch.object(experiment.time,'perf_counter',side_effect=clock.now), contextlib.redirect_stdout(io.StringIO()):
            result=experiment.run_episode(run_id='synthetic-native-completion',cap=.09)
            events=[json.loads(line) for line in (Path(directory)/'synthetic-native-completion'/'events.jsonl').read_text().splitlines()]
        self.assertEqual(result['outcome'],'success')
        self.assertEqual(cell.data.time,captured[0]['sim_time_s'])
        self.assertAlmostEqual(result['completion_sim_time_s'],.512)
        completion=next(e for e in events if e['event_type']=='independent_completion')
        self.assertEqual(completion['payload']['wall_elapsed_s'],result['completion_time_s'])
        self.assertTrue(completion['payload']['within_wall_cap'])
        self.assertLess(result['completion_time_s'],.09)

    def test_robot_telemetry_history_is_bounded_and_discloses_expired_batches(self):
        history=experiment.PublicTelemetryHistory()
        for i in range(150):history.append(i*.01,i*.01,[i]*7,[0]*7,[1]*7,.07)
        packet=history.packet(1.5,1.51,after_sequence=10)
        self.assertEqual(len(packet['samples']),100)
        self.assertEqual(packet['samples'][0]['sequence'],51)
        self.assertEqual(packet['samples_expired_since_last_attempted_step_dispatch'],40)
        self.assertFalse(packet['live_100_hz_policy'])
        self.assertFalse({'target','tcp','contact_peak','objects'} & set(packet['samples'][0]))
        forwarded=experiment.sensor_delivery_packet({'arm':{'telemetry_history':packet}},None,delivery_sim_s=1.5,delivery_wall_s=1.51)
        self.assertEqual(forwarded['arm']['telemetry_history'],packet)
        history.append(1.54,1.55,[0]*7,[0]*7,[0]*7,.07)
        self.assertEqual(history.packet(1.54,1.55)['samples'][-1]['missed_nominal_intervals'],4)
        empty=history.packet(3.,3.)
        self.assertEqual(empty['samples'],[])
        self.assertIsNone(empty['latest_sample_age_sim_s'])

    def test_result_classification_keeps_candidate_failures_and_exposes_infrastructure(self):
        import protocol
        for failure in ('candidate_contract_failure','candidate_transport_failure','candidate_resource_failure'):
            result=experiment.result_validity(failure_class=failure,cleanup_errors=[],timing_failed=False,evaluation_authorized=True)
            self.assertEqual(result['validity'],'valid');self.assertFalse(protocol._infra_invalid(result))
        for failure in ('infrastructure_failure','host_resource_invalid','oracle_exposure'):
            result=experiment.result_validity(failure_class=failure,cleanup_errors=[],timing_failed=False,evaluation_authorized=True)
            self.assertEqual(result['invalidity_class'],'infrastructure');self.assertTrue(protocol._infra_invalid(result))

    def test_raw_camera_request_traverses_async_workers_with_event_parent_links(self):
        clock=Clock();cell=fake_cell();worker=MagicMock();worker.alive=True;worker.ready={}
        queued=[];base_poll=cell.poll_sense.side_effect
        def request_capture(model,data,**kwargs):
            result=base_poll();result.camera=kwargs['camera'];result.sequence=kwargs['sequence']
            result.calibration['camera']=result.camera;queued.append(result);return True
        cell.sensor_worker.request.side_effect=request_capture
        cell.poll_sense.side_effect=lambda:queued.pop(0) if queued else base_poll()
        sent=[];step_count=[0]
        worker.send.side_effect=lambda message:sent.append(message)
        def receive(**kwargs):
            current=sent[-1]
            if current['type']=='step':
                step_count[0]+=1
                response=({'type':'sensor_request','request_id':'raw-fixture','camera':'wrist','modalities':['rgb','depth']}
                          if step_count[0]==1 else {'type':'wait'})
            else:response=None
            return {'type':current['type'],'response':response,'events':[]}
        worker.receive.side_effect=receive
        model=MagicMock();executor=ImmediateExecutor(model,None)
        with tempfile.TemporaryDirectory() as directory, patch.object(experiment,'EVIDENCE',Path(directory)), patch.object(experiment,'Cell',return_value=cell), patch.object(sandbox,'CandidateSandbox',return_value=worker), patch.object(experiment,'ThreadPoolExecutor',return_value=executor), patch.object(experiment.time,'perf_counter',side_effect=clock.now), contextlib.redirect_stdout(io.StringIO()):
            result=experiment.run_episode(run_id='synthetic-raw',cap=.45)
            events=[json.loads(line) for line in (Path(directory)/'synthetic-raw'/'events.jsonl').read_text().splitlines()]
        self.assertIsNone(result['error'])
        cell.render.assert_not_called()
        delivered=[message for message in sent if message['type']=='sensor_response']
        self.assertEqual(len(delivered),1)
        self.assertEqual(delivered[0]['response']['camera'],'wrist')
        self.assertEqual(delivered[0]['response']['status'],'ok')
        self.assertLess(len(experiment.canonical(delivered[0]))+1,1024*1024)
        indexed={e['event_type']:e for e in events if e['event_type'].startswith('raw_sensor_')}
        self.assertEqual(indexed['raw_sensor_admission']['parent_ids'],[indexed['raw_sensor_request']['event_id']])
        self.assertIn(indexed['raw_sensor_capture']['event_id'],indexed['raw_sensor_response']['parent_ids'])
        dispatched=next(e for e in events if e['event_type']=='candidate_input' and e['payload']['message']['type']=='sensor_response')
        self.assertEqual(dispatched['parent_ids'],[indexed['raw_sensor_response']['event_id']])
        steps=[m['packet'] for m in sent if m['type']=='step']
        self.assertTrue(all('camera_calibration' in packet and 'capture_wall_elapsed_s' in packet for packet in steps))

    def test_explicit_startup_contract_denial_is_candidate_failure_with_protected_stderr(self):
        cell=fake_cell();worker=MagicMock();worker.stderr='CANDIDATE_CONTRACT_VIOLATION {"event":"open"}'
        worker.start.side_effect=RuntimeError('sandbox exited77')
        with tempfile.TemporaryDirectory() as directory, patch.object(experiment,'EVIDENCE',Path(directory)), patch.object(experiment,'Cell',return_value=cell), patch.object(sandbox,'CandidateSandbox',return_value=worker), contextlib.redirect_stdout(io.StringIO()):
            result=experiment.run_episode(run_id='synthetic-denial',cap=.1)
            events=[json.loads(line) for line in (Path(directory)/'synthetic-denial'/'events.jsonl').read_text().splitlines()]
        self.assertEqual(result['failure_class'],'candidate_contract_failure')
        self.assertEqual(result['validity'],'unknown')
        self.assertTrue(any('CANDIDATE_CONTRACT_VIOLATION' in e['payload'].get('stderr_tail','') for e in events))

    def test_queued_raw_encoding_keeps_frame_association_when_cache_advances(self):
        from test_sensors import fake_cell as raw_fake_cell
        from sensors import RawSensorGateway
        with tempfile.TemporaryDirectory() as directory:
            cell=raw_fake_cell();gateway=RawSensorGateway(cell,directory)
            capture_id=gateway.cache_overhead(capture_wall_elapsed_s=1.)
            request={'type':'sensor_request','request_id':'pin-fixture','camera':'overhead'}
            self.assertEqual(gateway.admit_request(request)['status'],'accepted')
            pinned=experiment.pin_sensor_gateway(gateway)
            cell.data.time=3.;cell.detection_time=3.
            gateway.cache_overhead(capture_wall_elapsed_s=2.)
            encoded=experiment.prepare_raw_reply(pinned,request,2.2,{'sim_time_s':3.2})
            response=encoded['message']['response']
            self.assertEqual(response['capture_id'],capture_id)
            self.assertEqual(response['capture_sim_time_s'],2.)
            self.assertEqual(gateway._admissions,{})

    def test_resource_watchdog_classifies_harness_and_unattributed_gpu_separately(self):
        def check(sample):
            return experiment.resource_breaches(sample,now_monotonic_s=1.,sampler_started_monotonic_s=0.)
        self.assertEqual(check(None),[])  # Explicit initial grace only.
        harness=check({'capture_monotonic_s':1.,'harness':{'rss_bytes':4*experiment.GIB+1}})
        self.assertEqual(harness[0]['classification'],'infrastructure_failure')
        gpu=check({'capture_monotonic_s':1.,'gpu':{'devices':[{'index':0,'memory_used_bytes':14*experiment.GIB+1}]}})
        self.assertEqual(gpu[0]['classification'],'host_resource_invalid')
        self.assertIn('unknown',gpu[0]['attribution'])
        self.assertFalse(experiment.RESOURCE_POLICY['resource_caps_enforced'])
        self.assertEqual(check({'capture_monotonic_s':1.,'model':{'private_commit_bytes':12*experiment.GIB}}),[])
        missing=experiment.resource_breaches(None,now_monotonic_s=7.,sampler_started_monotonic_s=0.)
        self.assertEqual(missing[0]['classification'],'infrastructure_failure')

    def test_invalid_initial_world_is_protected_and_rejected_before_episode_clock(self):
        cell=fake_cell();worker=MagicMock();worker.alive=True
        worker.stderr='CANDIDATE_CONTRACT_VIOLATION {"event":"synthetic concurrent denial"}'
        report={'valid':False,'errors':['synthetic overlapping stock'],'snapshot_sha256':'fixture'}
        with tempfile.TemporaryDirectory() as directory, patch.object(experiment,'EVIDENCE',Path(directory)), patch.object(experiment,'Cell',return_value=cell), patch.object(sandbox,'CandidateSandbox',return_value=worker), patch.object(experiment,'initial_world_report',return_value=report), contextlib.redirect_stdout(io.StringIO()):
            result=experiment.run_episode(run_id='invalid-initial-fixture',cap=.1)
            events=[json.loads(line) for line in (Path(directory)/'invalid-initial-fixture'/'events.jsonl').read_text().splitlines()]
        self.assertEqual(result['validity'],'invalid')
        self.assertEqual(result['initial_world_validation'],report)
        self.assertEqual(result['failure_class'],'infrastructure_failure')
        self.assertIsNone(result['wall_duration_s'])
        self.assertFalse(any(e['event_type']=='episode_clock_started' for e in events))
        protected=next(e for e in events if e['event_type']=='initial_world_validation')
        self.assertEqual(protected['source'],'evaluator')
        worker.send.assert_not_called();cell.prepare_sensor.assert_not_called()

    def test_development_run_path_rejects_dot_directories(self):
        for run_id in ('.','..','../escape','bad/nested'):
            with self.subTest(run_id=run_id),self.assertRaises(ValueError):
                experiment.authorized_evidence_path('development',None,kind='baseline',n=3,cap=1.,condition='persistent',scenario='nominal',run_id=run_id,seeds={})

    def test_seeded_restart_exposure_is_recorded_without_public_private_configuration(self):
        clock=Clock();cell=fake_cell();old=MagicMock();fresh=MagicMock()
        cell.data.site_xpos[cell.tcp][2]=.098
        for worker in (old,fresh):
            worker.alive=True;worker.receive.return_value={'type':'step','response':None};worker.ready={}
        tracker=MagicMock();tracker.configuration.return_value={'cut':'fixture private cut','enabled':True}
        cut={'actual_cut':'fixture cut','configured_milestone_exercised':True}
        pending_cut=[cut]
        tracker.observe.side_effect=lambda *args,**kwargs:pending_cut.pop() if pending_cut else None
        executor=ImmediateExecutor(MagicMock(),DeferredModelFuture())
        rich={'geometry':{},'snapshot_sha256':'synthetic-protected','exposure':cut}
        with patch.object(experiment,'capture_restart_state',return_value=rich), tempfile.TemporaryDirectory() as directory, patch.object(experiment,'EVIDENCE',Path(directory)), patch.object(experiment,'Cell',return_value=cell), patch.object(sandbox,'CandidateSandbox',return_value=old), patch.object(experiment,'RestartOpportunity',return_value=tracker) as factory, patch.object(experiment,'restart_worker',return_value=fresh) as restart, patch.object(experiment,'ThreadPoolExecutor',return_value=executor), patch.object(experiment.time,'perf_counter',side_effect=clock.now), contextlib.redirect_stdout(io.StringIO()):
            result=experiment.run_episode(run_id='restart-fixture',cap=.2,scenario='restart',world_seed=123)
            events=[json.loads(line) for line in (Path(directory)/'restart-fixture'/'events.jsonl').read_text().splitlines()]
        factory.assert_called_once_with(123,enabled=True)
        self.assertTrue(tracker.observe.call_args_list)
        self.assertTrue(all(call.kwargs['tcp_z']==.098 for call in tracker.observe.call_args_list))
        restart.assert_called_once()
        self.assertTrue(result['restart_exercised'])
        self.assertEqual({key:result['restart_exposure'][key] for key in cut},cut)
        self.assertEqual(result['restart_exposure']['restart_admissibility']['state'],'unknown')
        begin=next(e for e in events if e['event_type']=='restart_begin')
        self.assertEqual(begin['payload']['exposure'],cut)
        ready=next(e for e in events if e['event_type']=='restart_ready')
        self.assertEqual(ready['parent_ids'],[begin['event_id']])
        inputs=[e['payload']['message'] for e in events if e['event_type']=='candidate_input']
        self.assertNotIn('fixture private cut',json.dumps(inputs))


if __name__=='__main__':unittest.main()
