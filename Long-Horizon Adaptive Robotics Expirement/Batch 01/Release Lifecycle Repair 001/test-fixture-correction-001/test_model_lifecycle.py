"""Deterministic lifecycle counterexamples; fake HTTP/process/cell, no physics.

Run through run_staged_tests.py to select the staged modules and base dependencies.
"""
from concurrent.futures import ThreadPoolExecutor
import contextlib
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import experiment
import model_runtime
import sandbox
from model_runtime import (LocalModel, ModelConfig, ModelLifecycleSnapshot,
                           ModelRequestTimeout, ModelRequestTimeoutError)
from test_experiment import Clock, FakeResourceSampler, ImmediateExecutor, fake_cell


def fake_model():
    model=LocalModel()
    model.process=MagicMock()
    model.process.pid=27772
    model.process.poll.return_value=None
    model._manifest={'installed_files':[{'path':'server.exe','sha256':'synthetic'}],
                     'server_relative_path':'server.exe'}
    return model


def fresh_sample(captured,pid=27772):
    return {'capture_monotonic_s':captured,
            'harness':{'rss_bytes':1000},
            'model':{'pid':pid,'private_commit_bytes':2000},
            'gpu':{'devices':[{'index':0,'memory_used_bytes':3000}]}}


def check_resources(snapshot,sample,now):
    return experiment.resource_breaches(sample,now_monotonic_s=now,
        sampler_started_monotonic_s=now-20.,model_required=True,
        model_pid=snapshot.resource_pid,model_lifecycle=snapshot)


class ModelLifecycleTests(unittest.TestCase):
    def test_frozen_request_limits_unchanged(self):
        config=ModelConfig()
        self.assertEqual((config.request_timeout_s,config.max_output_tokens,config.context_tokens),(30.,1024,16384))

    def test_timeout_snapshot_available_while_owned_termination_is_blocked(self):
        for watchdog_first in (True,False):
            with self.subTest(watchdog_first=watchdog_first):
                model=fake_model();process=model.process
                entered=threading.Event();release=threading.Event()
                def terminate():
                    entered.set()
                    if not release.wait(3.):raise RuntimeError('test synchronization timed out')
                process.terminate.side_effect=terminate
                model._request=MagicMock(side_effect=TimeoutError('synthetic HTTP deadline'))
                with ThreadPoolExecutor(max_workers=2) as pool:
                    future=pool.submit(model.complete,[{'role':'user','content':'wait'}],{'type':'object'})
                    try:
                        self.assertTrue(entered.wait(2.))
                        if not watchdog_first:
                            release.set()
                            with self.assertRaises(ModelRequestTimeoutError):future.result(timeout=2.)
                        # Separate thread + bounded result proves no teardown-held lock.
                        snapshot=pool.submit(model.lifecycle_snapshot).result(timeout=.5)
                        self.assertIsNone(snapshot.process_pid)
                        self.assertEqual(snapshot.owned_pid,27772)
                        self.assertEqual(snapshot.state,'timeout_stopping' if watchdog_first else 'timeout_stopped')
                        if watchdog_first:self.assertFalse(future.done())
                        cause=snapshot.request_timeout
                        self.assertEqual(cause.request_id,1)
                        self.assertEqual(cause.budget_s,30.)
                        sample=fresh_sample(cause.observed_monotonic_s-.01)
                        now=cause.observed_monotonic_s+.02
                        self.assertEqual(check_resources(snapshot,sample,now),[])
                        failure=experiment.model_lifecycle_failure(snapshot,at_monotonic_s=now)
                        self.assertEqual(failure['classification'],'model_request_timeout')
                    finally:
                        release.set()
                    with self.assertRaises(ModelRequestTimeoutError):future.result(timeout=2.)
                process.terminate.assert_called_once()
                self.assertEqual(model.lifecycle_snapshot().request_timeout,cause)

    def test_timeout_does_not_relabel_a_process_already_observed_exited(self):
        model=fake_model();process=model.process
        def request(*args):
            process.poll.return_value=7
            raise TimeoutError('socket failure while server is dead')
        model._request=MagicMock(side_effect=request)
        with self.assertRaisesRegex(RuntimeError,'unavailable before request-timeout'):
            model.complete([{'role':'user','content':'wait'}],{'type':'object'})
        snapshot=model.lifecycle_snapshot()
        self.assertIsNone(snapshot.request_timeout)
        self.assertEqual(experiment.model_lifecycle_failure(snapshot,at_monotonic_s=time.perf_counter())['classification'],'infrastructure_failure')
        process.terminate.assert_not_called()

    def test_failed_owned_teardown_is_infrastructure_even_with_timeout_cause(self):
        model=fake_model()
        model.process.terminate.side_effect=OSError('synthetic termination denial')
        model._request=MagicMock(side_effect=TimeoutError('synthetic deadline'))
        with self.assertRaises(ModelRequestTimeoutError) as caught:
            model.complete([{'role':'user','content':'wait'}],{'type':'object'})
        self.assertIn('termination denial',caught.exception.stop_error)
        snapshot=model.lifecycle_snapshot()
        self.assertEqual(snapshot.state,'stop_failed')
        self.assertEqual(experiment.model_lifecycle_failure(snapshot,at_monotonic_s=time.perf_counter())['classification'],'infrastructure_failure')

    def test_genuine_resource_breaches_are_not_hidden_by_timeout(self):
        cause=ModelRequestTimeout(1,27772,40.,70.,70.,30.,'/v1/chat/completions')
        snapshot=ModelLifecycleSnapshot('timeout_stopped',None,27772,None,cause,stopped_monotonic_s=70.05)
        cases={
            'missing whole sample':None,
            'stale whole sample':fresh_sample(62.),
            'unknown PID':fresh_sample(70.1,pid=None),
            'different PID':fresh_sample(70.1,pid=27773),
        }
        cases['model cap']=fresh_sample(70.1);cases['model cap']['model']['private_commit_bytes']=12*experiment.GIB+1
        cases['harness cap']=fresh_sample(70.1);cases['harness cap']['harness']['rss_bytes']=4*experiment.GIB+1
        cases['GPU cap']=fresh_sample(70.1);cases['GPU cap']['gpu']['devices'][0]['memory_used_bytes']=14*experiment.GIB+1
        cases['missing harness']=fresh_sample(70.1);cases['missing harness']['harness']={}
        cases['missing GPU']=fresh_sample(70.1);cases['missing GPU']['gpu']={}
        cases['pre-timeout missing model']=fresh_sample(69.9);cases['pre-timeout missing model']['model']['private_commit_bytes']=None
        cases['during-stop missing model']=fresh_sample(70.01);cases['during-stop missing model']['model']['private_commit_bytes']=None
        cases['nonfinite model']=fresh_sample(70.1);cases['nonfinite model']['model']['private_commit_bytes']=float('nan')
        for name,sample in cases.items():
            with self.subTest(name=name):
                breaches=check_resources(snapshot,sample,70.2)
                self.assertTrue(breaches)
                self.assertTrue(all(b['classification'] in ('infrastructure_failure','host_resource_invalid') for b in breaches))
        sample=fresh_sample(70.1);sample['model']['private_commit_bytes']=None
        self.assertEqual(check_resources(snapshot,sample,70.2),[])
        # The same absent metric while stop is unfinished cannot assert absence.
        unfinished=ModelLifecycleSnapshot('timeout_stopping',None,27772,None,cause)
        self.assertTrue(check_resources(unfinished,sample,70.2))
        unexplained=ModelLifecycleSnapshot('stopped',None,27772,None)
        self.assertTrue(check_resources(unexplained,fresh_sample(70.1),70.2))

    def test_dict_or_late_cause_cannot_reclassify_a_settled_episode(self):
        cause=ModelRequestTimeout(1,27772,40.,70.,70.,30.,'/v1/chat/completions')
        snapshot=ModelLifecycleSnapshot('timeout_stopped',None,27772,None,cause)
        self.assertIsNone(experiment.model_lifecycle_failure(snapshot,at_monotonic_s=69.9))
        self.assertIsNone(experiment.model_lifecycle_failure(snapshot,at_monotonic_s=71.,settled_end_monotonic_s=69.9))
        model=MagicMock();model.process=None;model.lifecycle_snapshot.return_value={'request_timeout':{'kind':'model_request_timeout'}}
        self.assertIsNone(experiment.protected_model_snapshot(model).request_timeout)
        validity=experiment.result_validity(failure_class='model_request_timeout',cleanup_errors=[],timing_failed=False,evaluation_authorized=True)
        self.assertEqual(validity['validity'],'valid')
        self.assertFalse(validity['infrastructure_invalid'])


class TimeoutFuture:
    """Choose the exact synchronous boundary at which the deadline is published."""
    def __init__(self,model,clock,ordering):
        self.model=model;self.clock=clock;self.ordering=ordering;self.error=None;self.result_calls=0
    def publish(self):
        if self.error is None:
            # Short unit-fixture timeout only; production ModelConfig stays 30s.
            cause=self.model._publish_request_timeout(request_id=1,started=max(0.,self.clock.t-.01),
                                                       budget=.005,path='/v1/chat/completions')
            self.model.stop();self.error=ModelRequestTimeoutError(cause)
    def done(self):
        if self.ordering=='future_first':self.publish();return True
        return False
    def result(self,timeout=None):
        self.result_calls+=1;self.publish();raise self.error


class TimeoutExecutor(ImmediateExecutor):
    def __init__(self,model,deferred):
        super().__init__(model,deferred);self.request_seen=False
    def submit(self,function,*args,**kwargs):
        if function==self.model.complete:
            self.request_seen=True
            if self.deferred.ordering=='watchdog_first':self.deferred.publish()
        return super().submit(function,*args,**kwargs)


class SupervisorTimeoutTests(unittest.TestCase):
    def run_fixture(self,ordering,complete=False,model_delay_s=1.2,cap=2.):
        clock=Clock();cell=fake_cell();worker=MagicMock();worker.alive=True;model=fake_model()
        first_step=[None]
        def receive(**kwargs):
            if first_step[0] is None:first_step[0]=clock.t
            # Establish an actual synthetic one-second timing window before
            # testing lifecycle validity. The production timing gate is active.
            response=({'type':'model','messages':[{'role':'user','content':'wait'}],'schema':{'type':'object'}}
                      if clock.t-first_step[0]>=model_delay_s else {'type':'wait'})
            return {'type':'step','response':response}
        worker.receive.side_effect=receive
        future=TimeoutFuture(model,clock,ordering);executor=TimeoutExecutor(model,future)
        if complete:
            def tick():
                cell.data.time+=.002
                if executor.request_seen and cell.evaluator.first_success is None:
                    if ordering=='tick_before_completion':future.publish()
                    cell.evaluator.first_success={'sim_time_s':cell.data.time,'wall_monotonic_s':clock.t,
                        'protected_snapshot':{'synthetic':True},'outcome':{'success':True,'accepted_count':3}}
            cell.tick.side_effect=tick
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(experiment,'EVIDENCE',Path(directory)), \
             patch.object(experiment,'Cell',return_value=cell), \
             patch.object(sandbox,'CandidateSandbox',return_value=worker), \
             patch.object(experiment,'ResourceSampler',FakeResourceSampler), \
             patch.object(experiment,'initial_world_report',return_value={'valid':True,'errors':[]}), \
             patch.object(experiment,'ThreadPoolExecutor',return_value=executor), \
             patch.object(experiment.time,'perf_counter',side_effect=clock.now), \
             contextlib.redirect_stdout(io.StringIO()):
            result=experiment.run_episode(kind='A2',model=model,run_id='synthetic-lifecycle-'+ordering,cap=cap)
            events=[json.loads(line) for line in (Path(directory)/('synthetic-lifecycle-'+ordering)/'events.jsonl').read_text().splitlines()]
        return result,events,future

    def test_both_observation_orderings_have_one_terminal_failure_and_one_accounting_entry(self):
        for ordering in ('watchdog_first','future_first'):
            with self.subTest(ordering=ordering):
                result,events,future=self.run_fixture(ordering)
                self.assertEqual(result['failure_class'],'model_request_timeout')
                self.assertEqual(result['termination_reason'],'model_request_timeout')
                self.assertTrue(result['actual_host_timing_pass'])
                self.assertEqual(result['cleanup_errors'],[])
                self.assertFalse(result['infrastructure_invalid'])
                self.assertEqual((result['model_calls'],result['model_responses'],result['model_failed_calls'],result['unknown_token_calls']),(1,0,1,1))
                self.assertEqual(future.result_calls,1)
                self.assertEqual(result['resource_watchdog_events'],[])
                self.assertEqual(sum(e['event_type']=='model_lifecycle_terminal' for e in events),1)
                self.assertEqual(sum(e['event_type']=='model_error' for e in events),1)
                self.assertFalse(any(e['event_type']=='candidate_input' and e['payload']['message']['type']=='model_response' for e in events))

    def test_timeout_without_a_timing_window_remains_invalid(self):
        result,events,future=self.run_fixture('watchdog_first',model_delay_s=0.,cap=.4)
        self.assertEqual(result['failure_class'],'model_request_timeout')
        self.assertFalse(result['actual_host_timing_pass'])
        self.assertEqual(result['timing'],[])
        self.assertTrue(result['infrastructure_invalid'])
        self.assertEqual((result['model_failed_calls'],result['unknown_token_calls'],future.result_calls),(1,1,1))

    def test_timeout_first_observed_in_cleanup_preserves_completion_and_cap(self):
        for complete in (False,True):
            with self.subTest(complete=complete):
                result,events,future=self.run_fixture('late',complete=complete)
                self.assertIsNone(result['failure_class'])
                self.assertIsNone(result['model_lifecycle_terminal'])
                self.assertEqual(result['termination_reason'],'independent_completion' if complete else 'time_cap')
                self.assertEqual(result['outcome']=='success',complete)
                self.assertEqual((result['model_failed_calls'],result['unknown_token_calls']),(1,1))
                self.assertEqual(future.result_calls,1)
                self.assertFalse(any(e['event_type']=='model_lifecycle_terminal' for e in events))

    def test_timeout_published_before_completion_tick_cannot_become_success(self):
        result,events,future=self.run_fixture('tick_before_completion',complete=True)
        self.assertEqual(result['failure_class'],'model_request_timeout')
        self.assertNotEqual(result['outcome'],'success')
        self.assertIsNone(result['completion_landmark'])
        self.assertEqual((result['model_failed_calls'],result['unknown_token_calls'],future.result_calls),(1,1,1))
        self.assertFalse(any(e['event_type']=='independent_completion' for e in events))


if __name__=='__main__':unittest.main()
