"""Deterministic transport lifecycle checks; no model, WSL, or simulation."""
import copy
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import patch
import urllib.error

import runtime


class TransportChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.value = runtime.Runtime.__new__(runtime.Runtime)
        self.value.evidence = Path(self.temp.name)
        self.value.endpoint = {'url':'http://127.0.0.1:1','capability':'test-token','authority_epoch':3}
        self.value.token = 'test-token'
        self.value.tokens = ['test-token']
        self.value.retired = False
        self.value.authority_revoked = threading.Event()
        self.value.revocation_lock = threading.Lock()
        self.value.abort_event = threading.Event()
        self.value.stop = threading.Event()
        self.value.workspace = '/not-used'
        self.value.broker_calls = []
        self.payload = {'request_id':'handback-1','authority_epoch':3}
        self.accepted = {'ok':True,'owner':'conventional','authority_epoch':4,
                         'command':{'request_id':'handback-1','kind':'handback',
                                    'phase':'terminal','status':'completed'}}

    def frame(self, method, path, payload=None, token='test-token'):
        return json.dumps({'method':method,'path':path,'capability':token,
                           'body':json.dumps(payload) if payload is not None else ''}) + '\n'

    def broker(self, frames, reply):
        self.value.broker = types.SimpleNamespace(stdout=io.StringIO(''.join(frames)),stdin=io.StringIO())
        with patch.object(runtime,'request',side_effect=reply) as upstream:
            self.value._broker_loop()
        responses = [json.loads(row) for row in self.value.broker.stdin.getvalue().splitlines()]
        return upstream,responses

    def rows(self,name):
        return [json.loads(row) for row in (self.value.evidence/name).read_text().splitlines()]

    def latch(self):
        self.value._observe_revocation('POST','/handback',self.payload,200,self.accepted,'broker','trace')

    def test_accepted_handback_denies_late_continuity_and_commands_without_upstream(self):
        upstream,responses = self.broker([
            self.frame('POST','/handback',self.payload),
            self.frame('POST','/continuity',{'content':'late note'}),
            self.frame('POST','/command',{'request_id':'late-command'}),
            self.frame('GET','/status')],[(200,self.accepted)])
        self.assertEqual(upstream.call_count,1)
        self.assertEqual([r['status'] for r in responses],[200,403,403,403])
        self.assertTrue(all(json.loads(r['body'])['ok'] is False for r in responses[1:]))
        self.assertTrue(self.value.authority_revoked.is_set())
        self.assertFalse(self.value.abort_event.is_set())
        events = self.rows('broker-events.jsonl')
        self.assertEqual([e['origin'] for e in events],['protected_host']+['local_revocation_fence']*3)
        self.assertFalse((self.value.evidence/'broker-failure.json').exists())

    def test_real_loopback_closure_after_handback_preserves_denied_tool_receipt(self):
        accepted=self.accepted
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length','0')))
                raw=json.dumps(accepted).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers()
                self.wfile.write(raw)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        self.value.endpoint['url']='http://127.0.0.1:'+str(server.server_port)
        def frames():
            yield self.frame('POST','/handback',self.payload)
            server.shutdown();server.server_close();thread.join(timeout=2)
            with self.assertRaises(urllib.error.URLError):
                runtime.request(self.value.endpoint['url'],self.value.token,'GET','/status')
            yield self.frame('POST','/continuity',{'content':'must remain uncommitted'})
        self.value.broker=types.SimpleNamespace(stdout=frames(),stdin=io.StringIO())
        try:self.value._broker_loop()
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)
        responses=[json.loads(row) for row in self.value.broker.stdin.getvalue().splitlines()]
        self.assertEqual([r['status'] for r in responses],[200,403])
        self.assertFalse(self.value.abort_event.is_set())
        self.assertEqual(self.rows('broker-events.jsonl')[-1]['origin'],'local_revocation_fence')

    def test_denial_of_pinned_capability_latches_but_unrelated_403_does_not(self):
        for code,latches in [('unauthorized',True),('invocation_retired',True),('operator_only',False),('programs_disabled',False)]:
            with self.subTest(code=code):
                self.value.authority_revoked.clear()
                self.value._observe_revocation('GET','/status',None,403,{'ok':False,'error':{'code':code}},'public_mirror')
                self.assertEqual(self.value.authority_revoked.is_set(),latches)

    def test_rejected_or_malformed_handback_never_latches(self):
        variants = [None,{}, {'ok':True}, {**self.accepted,'owner':'robot'},
                    {**self.accepted,'authority_epoch':3},{**self.accepted,'authority_epoch':True},
                    {**self.accepted,'command':None}]
        for key,bad in [('request_id','other'),('status','rejected'),('phase','accepted'),('kind','command')]:
            item=copy.deepcopy(self.accepted);item['command'][key]=bad;variants.append(item)
        for body in variants:
            with self.subTest(body=body):
                self.value._observe_revocation('POST','/handback',self.payload,200,body,'broker')
                self.assertFalse(self.value.authority_revoked.is_set())
        for payload in [None,{}, {'request_id':'other','authority_epoch':3}, {'request_id':'handback-1','authority_epoch':2}]:
            self.value._observe_revocation('POST','/handback',payload,200,self.accepted,'broker')
            self.assertFalse(self.value.authority_revoked.is_set())
        self.value._observe_revocation('POST','/command',self.payload,200,self.accepted,'broker')
        self.assertFalse(self.value.authority_revoked.is_set())

    def test_pre_revocation_connection_failure_aborts_and_retains_request_identity(self):
        upstream,responses = self.broker([self.frame('POST','/continuity',{'content':'uncommitted'})],
                                        urllib.error.URLError('injected connection refusal test-token'))
        self.assertEqual(upstream.call_count,1)
        self.assertEqual(responses,[])
        self.assertTrue(self.value.abort_event.is_set())
        request = self.rows('broker-requests.jsonl')[0]
        failure = json.loads((self.value.evidence/'broker-failure.json').read_text())
        self.assertEqual(failure['trace_id'],request['trace_id'])
        self.assertEqual((failure['method'],failure['path']),('POST','/continuity'))
        self.assertGreaterEqual(failure['failed_wall_unix_s'],request['received_wall_unix_s'])
        self.assertFalse(failure['authority_revocation_established'])
        self.assertNotIn('test-token',(self.value.evidence/'broker-failure.json').read_text())

    def test_upstream_malformed_json_is_fatal_not_local_route_denial(self):
        _,responses = self.broker([self.frame('GET','/status')],ValueError('injected invalid upstream JSON'))
        self.assertEqual(responses,[])
        self.assertTrue(self.value.abort_event.is_set())
        self.assertEqual(json.loads((self.value.evidence/'broker-failure.json').read_text())['type'],'ValueError')

    def test_local_wrong_token_denial_does_not_revoke_valid_token(self):
        upstream,responses = self.broker([self.frame('GET','/status',token='wrong'),self.frame('GET','/status')],
                                        [(200,{'ok':True})])
        self.assertEqual(upstream.call_count,1)
        self.assertEqual([r['status'] for r in responses],[403,200])
        self.assertFalse(self.value.authority_revoked.is_set())

    def test_invalid_route_denied_and_retained_without_upstream(self):
        upstream,responses = self.broker([self.frame('GET','/operator/status')],[])
        self.assertEqual(upstream.call_count,0)
        self.assertEqual(responses[0]['status'],403)
        self.assertEqual(self.rows('broker-rejections.jsonl')[0]['origin'],'local_route_validation')
        self.assertFalse(self.value.abort_event.is_set())

    def test_successful_upstream_has_matching_pre_dispatch_receipt(self):
        def reply(*args):
            self.assertEqual(self.rows('broker-requests.jsonl')[0]['path'],'/status')
            return 200,{'ok':True}
        self.broker([self.frame('GET','/status')],reply)
        request,event=self.rows('broker-requests.jsonl')[0],self.rows('broker-events.jsonl')[0]
        self.assertEqual(request['trace_id'],event['trace_id'])
        self.assertGreaterEqual(event['wall_unix_s'],request['received_wall_unix_s'])

    def test_mirror_already_revoked_never_contacts_upstream(self):
        self.latch()
        with patch.object(runtime,'request') as upstream:
            self.value._mirror_loop()
        upstream.assert_not_called()
        self.assertFalse(self.value.abort_event.is_set())

    def test_inflight_mirror_connection_failure_after_handback_does_not_abort(self):
        def reply(*args):
            self.latch()
            raise urllib.error.URLError('injected closed host')
        with patch.object(runtime,'request',side_effect=reply):self.value._mirror_loop()
        self.assertFalse(self.value.abort_event.is_set())
        receipt=json.loads((self.value.evidence/'mirror-after-revocation.json').read_text())
        self.assertTrue(receipt['authority_revocation_established'])
        self.assertEqual(receipt['phase'],'upstream_request')

    def test_mirror_failure_before_revocation_aborts(self):
        with patch.object(runtime,'request',side_effect=urllib.error.URLError('injected premature closure')):
            self.value._mirror_loop()
        self.assertTrue(self.value.abort_event.is_set())
        self.assertTrue((self.value.evidence/'mirror-error.json').exists())
        self.assertFalse((self.value.evidence/'mirror-after-revocation.json').exists())

    def test_mirror_publish_failure_still_aborts_after_concurrent_handback(self):
        def publish(*args,**kwargs):
            self.latch()
            raise OSError('injected evidence publication failure')
        with patch.object(runtime,'request',return_value=(200,{'ok':True,'activation':{},'packet':{}})), \
             patch.object(runtime,'linux',side_effect=publish):
            self.value._mirror_loop()
        self.assertTrue(self.value.abort_event.is_set())
        self.assertEqual(json.loads((self.value.evidence/'mirror-error.json').read_text())['phase'],'mirror_publish')

    def test_mirror_host_capability_denial_retires_without_publish(self):
        with patch.object(runtime,'request',return_value=(403,{'ok':False,'error':{'code':'unauthorized'}})), \
             patch.object(runtime,'linux') as publish:
            self.value._mirror_loop()
        publish.assert_not_called()
        self.assertTrue(self.value.authority_revoked.is_set())
        self.assertFalse(self.value.abort_event.is_set())

    def test_first_revocation_receipt_is_immutable(self):
        self.latch()
        receipt=(self.value.evidence/'authority-revocation.json').read_bytes()
        self.value._observe_revocation('GET','/status',None,403,{'ok':False,'error':{'code':'unauthorized'}},'public_mirror')
        self.assertEqual((self.value.evidence/'authority-revocation.json').read_bytes(),receipt)


if __name__ == '__main__':unittest.main()
