"""Actual cleanup controller and Client integration, with no native/model launch."""
import io
import json
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import native_quiescence as nq
from test_native_owner_bootstrap import V4
from test_native_cleanup_protocol import completion


class Process:
    def __init__(self, client, respond):
        self.returncode = None
        self.done = threading.Event()
        self.release = threading.Event()
        self.controls = []
        self.block_write = self.block_flush = self.block_close = self.hang_exit = False
        self.stdin = self
        self.client, self.respond = client, respond
        self.closed = False

    def write(self, wire):
        if self.block_write:
            self.release.wait()
            raise BrokenPipeError('private transport payload must not be retained')
        request = json.loads(wire)
        self.controls.append(request)
        self.respond(request)

    def flush(self):
        if self.block_flush:
            self.release.wait()
            raise BrokenPipeError('private flush failure')

    def close(self):
        if self.block_close: self.release.wait()
        self.closed = True
        if not self.hang_exit and self.returncode is None:
            self.returncode = 0
            self.done.set()

    def poll(self): return self.returncode

    def wait(self, timeout):
        if not self.done.wait(timeout): raise subprocess.TimeoutExpired('fake',timeout)
        return self.returncode


class QuiescenceTests(unittest.TestCase):
    def client(self, *, state='active', mode=None, order='response_first'):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        client = V4.Client.__new__(V4.Client)
        client.args = SimpleNamespace(evidence=root,redact_tokens=['synthetic-capability-secret'],
            abort_event=threading.Event(),client_finishing=threading.Event())
        client.args.abort_event.set()
        client.barrier_requests = []
        def barrier(seed):
            client.barrier_requests.append(seed)
            return completion(seed, completed=time.monotonic())
        client.args.native_cleanup_barrier = barrier
        client.events = (root/'events.jsonl').open('x',encoding='utf-8')
        self.addCleanup(lambda:client.events.close() if not client.events.closed else None)
        client.next_id=40;client.messages=queue.Queue();client.pending_events=[];client.bytes_seen=0
        client.deadline=time.monotonic()-10
        client.cleanup_started=False;client.cleanup_result=None
        client.thread_id='thread-fixed' if state not in ('none','ambiguous_thread') else None
        client.turn_id='turn-fixed' if state in ('active','terminal','failed_terminal') else None
        client.thread_start_requested=state!='none'
        client.turn_start_requested=state in ('active','terminal','failed_terminal','ambiguous_turn')
        client.turn_terminal_status={'terminal':'completed','failed_terminal':'failed'}.get(state)
        def put(value): client.messages.put(('stdout',(json.dumps(value)+'\n').encode()))
        def respond(request):
            method=request['method'];rid=request['id']
            response={'id':rid,'result':{} if method=='turn/interrupt' else {'status':'unsubscribed'}}
            notification=({'method':'turn/completed','params':{'threadId':'thread-fixed',
                'turn':{'id':'turn-fixed','status':'interrupted','items':[{'private':'not retained'}]}}}
                if method=='turn/interrupt' else {'method':'thread/closed','params':{'threadId':'thread-fixed'}})
            if mode=='missing': return
            if mode=='wrong_response': response['id']=rid+1
            if mode=='rpc_error': response={'id':rid,'error':{'code':-1,'message':'synthetic-capability-secret'}}
            if mode=='server_request': put({'id':999,'method':'dangerous/request','params':{'secret':'synthetic-capability-secret'}});return
            if mode=='malformed': client.messages.put(('stdout',b'{bad synthetic-capability-secret'));return
            if mode=='duplicate_key': client.messages.put(('stdout',b'{"id":41,"id":41,"result":{}}'));return
            if mode=='wrong_thread': notification['params']['threadId']='other-thread'
            if mode=='wrong_turn' and method=='turn/interrupt': notification['params']['turn']['id']='other-turn'
            if mode in ('notLoaded','notSubscribed') and method=='thread/unsubscribe': response['result']['status']=mode
            if mode=='duplicate_response': put(response);put(response);put(notification);return
            if mode=='duplicate_terminal': put(notification);put(notification);put(response);return
            if order=='response_first': put(response);put(notification)
            else: put(notification);put(response)
        process=Process(client,respond);client.process=process
        class Job:
            def __init__(self):self.calls=0
            def close(self):
                self.calls+=1;process.release.set()
                if process.returncode is None:process.returncode=-9;process.done.set()
        client.job=Job()
        return client,root

    def run_close(self, client):
        with patch.object(nq,'GRACEFUL_SECONDS',.12),patch.object(nq,'TOTAL_SECONDS',.28):
            return client.close()

    def test_active_turn_controls_only_then_matching_ack_before_finishing(self):
        for order in ('response_first','notification_first'):
            with self.subTest(order=order):
                client,root=self.client(order=order)
                result=client.close()
                self.assertTrue(result['qualified'],result['failures'])
                self.assertEqual([v['method'] for v in client.process.controls],['turn/interrupt','thread/unsubscribe'])
                self.assertEqual(client.process.controls[0]['params'],{'threadId':'thread-fixed','turnId':'turn-fixed'})
                self.assertEqual(client.process.controls[1]['params'],{'threadId':'thread-fixed'})
                self.assertTrue(client.args.abort_event.is_set());self.assertLess(client.deadline,result['start_monotonic_s'])
                self.assertEqual(result['graceful_deadline_monotonic_s']-result['start_monotonic_s'],5)
                self.assertEqual(result['hard_deadline_monotonic_s']-result['start_monotonic_s'],10)
                self.assertFalse(result['forced_job_close'])
                self.assertEqual(len(client.barrier_requests), 1)
                self.assertEqual(result['schema'], 'campaign002-native-quiescence-2')
                self.assertEqual(result['cleanup_barrier']['request']['control_event'],
                                 next(e for e in result['events'] if e['phase']=='request'))
                phases=[e['phase'] for e in result['events']]
                self.assertEqual(phases[:4], ['start','request','cleanup_barrier_complete','request_sent'])
                rows=[json.loads(s) for s in (root/'events.jsonl').read_text().splitlines()]
                self.assertEqual([v for v in rows if v['kind']=='native_quiescence'],result['events'])
                closed=next(i for i,v in enumerate(rows) if v.get('phase')=='thread_closed')
                finish=next(i for i,v in enumerate(rows) if v['kind']=='client_finishing_before_close')
                stdin=next(i for i,v in enumerate(rows) if v.get('phase')=='stdin_closed')
                self.assertLess(closed,finish);self.assertLess(finish,stdin)
                self.assertEqual(rows[-1],{'kind':'client_shutdown','exit_code':0})
                self.assertEqual(json.loads((root/'native-quiescence.json').read_text()),result)
                self.assertNotIn('not retained',(root/'events.jsonl').read_text())

    def test_terminal_turn_or_preflight_never_starts_or_interrupts_a_turn(self):
        for state in ('terminal','failed_terminal','preflight'):
            client,_=self.client(state=state);result=client.close()
            self.assertTrue(result['qualified'],result['failures'])
            self.assertEqual([v['method'] for v in client.process.controls],['thread/unsubscribe'])
            if state!='preflight':self.assertEqual(result['terminal_turn']['source'],'entry')

    def test_no_thread_is_explicit_and_ambiguous_start_never_invents_ack(self):
        for state,qualified in [('none',True),('ambiguous_thread',False),('ambiguous_turn',False)]:
            client,root=self.client(state=state);result=self.run_close(client)
            self.assertEqual(result['qualified'],qualified,result)
            self.assertEqual(client.process.controls,[])
            self.assertIsNone(result['thread_closed']);self.assertTrue((root/'native-quiescence.json').is_file())
            self.assertIsNone(result['cleanup_barrier']);self.assertEqual(client.barrier_requests,[])

    def test_missing_failed_substituted_and_late_barrier_never_sends_control(self):
        for mode in ('missing','raises','changed_request','late','blocked'):
            with self.subTest(mode=mode):
                client,root=self.client(); release=threading.Event()
                def barrier(seed):
                    if mode=='raises': raise RuntimeError('private detail')
                    if mode=='blocked': release.wait(.6)
                    value=completion(seed,completed=time.monotonic())
                    if mode=='changed_request': value['request']['nonce']='a'*32
                    if mode=='late': value['completed_monotonic_s']=seed['graceful_deadline_monotonic_s']
                    return value
                client.args.native_cleanup_barrier=None if mode=='missing' else barrier
                started=time.monotonic(); result=self.run_close(client); release.set()
                self.assertLess(time.monotonic()-started,.8)
                self.assertFalse(result['qualified']);self.assertEqual(client.process.controls,[])
                self.assertIsNone(result['cleanup_barrier']);self.assertTrue(result['forced_job_close'])
                self.assertNotIn('private detail',(root/'events.jsonl').read_text())

    def test_wrong_duplicate_error_and_unsafe_envelopes_fail_closed(self):
        modes=['wrong_response','rpc_error','server_request','malformed','duplicate_key','wrong_thread',
               'wrong_turn','notLoaded','notSubscribed','duplicate_response','duplicate_terminal']
        for mode in modes:
            with self.subTest(mode=mode):
                client,root=self.client(mode=mode);result=self.run_close(client)
                self.assertFalse(result['qualified']);self.assertFalse(result['handshake_qualified'])
                self.assertTrue(result['forced_job_close']);self.assertTrue(client.args.abort_event.is_set())
                for file in ('native-quiescence.json','events.jsonl'):
                    raw=(root/file).read_text();self.assertNotIn('synthetic-capability-secret',raw)
                    self.assertNotIn('private transport payload',raw)

    def test_missing_ack_and_blocked_write_flush_close_have_one_absolute_budget(self):
        for mode in ('missing','block_write','block_flush','block_close','hang_exit'):
            with self.subTest(mode=mode):
                client,root=self.client(mode='missing' if mode=='missing' else None)
                if mode!='missing':setattr(client.process,mode,True)
                started=time.monotonic();result=self.run_close(client);elapsed=time.monotonic()-started
                self.assertFalse(result['qualified']);self.assertTrue(result['forced_job_close'])
                self.assertLess(elapsed,.8)
                self.assertAlmostEqual(result['hard_deadline_monotonic_s']-result['start_monotonic_s'],.28)
                self.assertIsNotNone(result['native_exit_code'])
                self.assertTrue((root/'native-quiescence.json').is_file())

    def test_existing_output_bound_applies_before_any_cleanup_payload_retention(self):
        client,root=self.client();client.bytes_seen=V4.MAX_BYTES
        result=self.run_close(client)
        self.assertFalse(result['qualified']);self.assertIn('output_limit',result['failures'])
        self.assertFalse(any(e['phase']=='response' for e in result['events']))

    def test_normal_control_is_sealed_even_if_cleanup_succeeded(self):
        client,_=self.client();client.close()
        for operation in (lambda:client.send({'method':'turn/start'}),lambda:client.call('config/read',{}),
                          lambda:client.receive(),lambda:client.close()):
            with self.assertRaises(RuntimeError):operation()
        self.assertEqual(len(client.process.controls),2)

    def test_original_response_ids_retained_before_later_validation_failure(self):
        client,_=self.client(state='none');client.args.abort_event.clear();client.deadline=time.monotonic()+5
        client.process.stdin=io.BytesIO()
        client.messages.put(('stdout',b'{"id":41,"result":{"thread":{"id":"created-thread"},"model":"wrong"}}\n'))
        response=client.call('thread/start',{})
        self.assertEqual(response['model'],'wrong');self.assertEqual(client.thread_id,'created-thread')
        self.assertTrue(client.thread_start_requested)
        client.messages.put(('stdout',b'{"id":42,"result":{"turn":{"id":"created-turn"}}}\n'))
        client.call('turn/start',{})
        self.assertEqual(client.turn_id,'created-turn');self.assertTrue(client.turn_start_requested)

    def test_no_new_control_follows_exhausted_shared_graceful_budget(self):
        client,_=self.client();original=client.process.respond
        def slow(request):
            if request['method']=='turn/interrupt':time.sleep(.15)
            original(request)
        client.process.respond=slow
        result=self.run_close(client)
        self.assertFalse(result['qualified'])
        self.assertEqual([v['method'] for v in client.process.controls],['turn/interrupt'])

    def test_native_exit_observation_precedes_job_handle_close(self):
        client,_=self.client();original=client.job.close;job_started=[]
        def slow_close():
            job_started.append(time.monotonic())
            time.sleep(.02)
            original()
        client.job.close=slow_close
        result=client.close()
        self.assertTrue(result['qualified'],result['failures'])
        observed=result['native_exit_monotonic_s']
        self.assertLessEqual(observed,job_started[0])
        self.assertLessEqual(observed,result['graceful_deadline_monotonic_s'])
        event=next(v for v in result['events'] if v['phase']=='native_exit')
        self.assertEqual(event['observed_monotonic_s'],observed)
        self.assertEqual(event['exit_code'],0)

    def test_native_eof_and_invalid_utf8_retire_without_payload_retention(self):
        for message,code in [(('stdout',None),'native_stdout_closed'),
                             (('stdout',b'\xffprivate-value'),'malformed_message')]:
            client,root=self.client();client.process.respond=lambda request:client.messages.put(message)
            result=self.run_close(client)
            self.assertFalse(result['qualified']);self.assertIn(code,result['failures'])
            self.assertTrue(result['forced_job_close']);self.assertIsNotNone(client.process.poll())
            self.assertNotIn('private-value',(root/'native-quiescence.json').read_text())
            self.assertNotIn('private-value',(root/'events.jsonl').read_text())

    def test_nonzero_native_exit_and_job_close_error_cannot_qualify(self):
        for mode in ('nonzero','job_error'):
            client,root=self.client()
            if mode=='nonzero':
                def close():
                    client.process.closed=True;client.process.returncode=7;client.process.done.set()
                client.process.close=close
            else:
                def close():raise OSError('private job handle detail')
                client.job.close=close
            result=self.run_close(client)
            self.assertFalse(result['qualified'])
            self.assertIn('native_exit_nonzero_or_missing' if mode=='nonzero' else 'job_close_deadline',result['failures'])
            retained=(root/'native-quiescence.json').read_text()
            self.assertEqual(json.loads(retained),result)
            self.assertNotIn('private job handle detail',retained)


if __name__=='__main__':unittest.main()
