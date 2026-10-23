"""Owner-aware metadata preflight; synthetic receipts, no process launch."""
import copy
import importlib.util
import json
import queue
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_raw_event_preflight as old

spec=importlib.util.spec_from_file_location('owner_preflight_under_test',Path(__file__).with_name('raw_event_preflight_v2.py'))
P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)
B=P.dependency('bootstrap_client_v4')


def assessment_fixture():
    """Load test-only dependencies without colliding with harness test names.

    Full discovery has its own test_client_quiescence in sys.modules. Temporary
    aliases are needed only while these fixture definitions import each other;
    restore every prior module immediately, before running the callback.
    """
    directory=Path(__file__).resolve().parents[1]/'assessment'
    def load(name):
        spec=importlib.util.spec_from_file_location('_raw_preflight_fixture_'+name,directory/(name+'.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    client=load('test_client_quiescence')
    with patch.dict(sys.modules,{'test_client_quiescence':client}):
        transport=load('test_transport_integrity_v3')
        with patch.dict(sys.modules,{'test_transport_integrity_v3':transport}):
            return load('test_cleanup_transport')


class OwnerPreflightTests(unittest.TestCase):
    def setUp(self):
        self.fixture=old.PreflightTests()
        self.addCleanup(self.fixture.doCleanups)
        with patch.object(old,'P',P),patch.object(old,'B',B):
            self.fixture.setUp()
        self.root=self.fixture.root;self.runtime=self.fixture.runtime
        for name in ('preflight.json','result.json'):
            document=old.get(self.runtime/'client'/name)
            document['effective_config']['thread_unload_delay_secs']=0
            old.put(self.runtime/'client'/name,document)
        for name in P.dependency('client_quiescence').SOURCE_NAMES + P.dependency('cleanup_transport').SOURCE_NAMES:
            self.fixture.frozen['sources'][name]=P.binding(P.REPO/name)
        old.put(self.fixture.snapshot,self.fixture.frozen)
        self.fixture.source['snapshot_sha256']=P.binding(self.fixture.snapshot)['sha256']
        self.fixture.source['schema']='campaign002-raw-preflight-source-2'
        old.put(self.root/'source-binding.json',self.fixture.source)
        self.owner={'schema':'campaign002-native-owner-1','owner_kind':'model_client',
                    'pid':123,'process_creation_filetime':789,'monotonic_s':0.,
                    'executable':self.fixture.source['native_binary']}
        old.put(self.runtime/'client/native-owner.json',self.owner)
        old.put(self.runtime/'codehost-native-owner-v3.json',self.owner)
        events=self.events()
        binding=P.binding(self.runtime/'client/native-owner.json')
        events.insert(0,{'kind':'native_process_owner_registered',
                         'receipt_sha256':binding['sha256'],'receipt_bytes':binding['bytes']})
        self.write_events(events[:-2])
        self.emit_actual_cleanup()
        retirement=old.get(self.runtime/'executor-1-retirement.json')
        retirement['identity_path']=self.fixture.namespace+'/codehost-owner.json'
        old.put(self.runtime/'codehost-owner-retirement-v3.json',retirement)
        self.proof={'passed':True,'accepted_count':0,'input_bindings':{
            'client/native-owner.json':P.binding(self.runtime/'client/native-owner.json')}}
        self.verifier=self.enterContext(patch.object(P.dependency('transport_integrity_v3'),
            'verify_transport_integrity',side_effect=lambda *a,**kw:copy.deepcopy(self.proof)))

    def emit_actual_cleanup(self):
        # Run the real bootstrap Client.close and native Controller against only
        # a fake pipe/process; this emits the real post-marker lifecycle layout.
        client=B.Client.__new__(B.Client)
        client.args=SimpleNamespace(evidence=self.runtime/'client',redact_tokens=[],
            abort_event=threading.Event(),client_finishing=threading.Event(),
            native_cleanup_barrier=lambda seed:assessment_fixture().synthetic_barrier_files(
                self.runtime,self.owner,seed))
        client.events=(self.runtime/'client/events.jsonl').open('a',encoding='utf-8')
        self.addCleanup(lambda:client.events.close() if not client.events.closed else None)
        client.next_id=10;client.messages=queue.Queue();client.pending_events=[];client.bytes_seen=0
        client.deadline=time.monotonic()+90;client.cleanup_started=False;client.cleanup_result=None
        client.thread_id='synthetic-thread';client.turn_id=None;client.turn_terminal_status=None
        client.thread_start_requested=True;client.turn_start_requested=False
        class Process:
            def __init__(self):self.stdin=self;self.returncode=None
            def write(self,raw):
                request=json.loads(raw)
                if request['method']!='thread/unsubscribe' or request['params']!={'threadId':client.thread_id}:
                    raise AssertionError('Unexpected native control in synthetic preflight')
                for value in ({'id':request['id'],'result':{'status':'unsubscribed'}},
                              {'method':'thread/closed','params':{'threadId':client.thread_id}}):
                    client.messages.put(('stdout',(json.dumps(value)+'\n').encode()))
            def flush(self):pass
            def close(self):self.returncode=0
            def poll(self):return self.returncode
            def wait(self,timeout):return self.returncode
        client.process=Process();client.job=SimpleNamespace(close=lambda:None)
        self.cleanup=client.close()
        self.assertTrue(self.cleanup['qualified'],self.cleanup['failures'])
        result=old.get(self.runtime/'client/result.json');result['native_quiescence']=self.cleanup
        old.put(self.runtime/'client/result.json',result)

    def events(self):
        return [json.loads(line) for line in (self.runtime/'client/events.jsonl').read_bytes().splitlines()]

    def write_events(self,events):
        (self.runtime/'client/events.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in events),encoding='utf-8')

    def assess(self):return P.assess(self.root,self.fixture.snapshot)

    def test_zero_channel_preflight_still_requires_eager_namespace_and_owner(self):
        result=self.assess()
        self.assertTrue(result['passed'],result['errors'])
        self.assertEqual(result,P.assess(self.root,self.fixture.snapshot))
        self.assertEqual(result['lifecycle']['namespace_retirements'],[
            'codehost-owner-retirement-v3.json','executor-1-retirement.json','executor-2-retirement.json'])
        self.assertFalse(result['lifecycle']['raw_tool_payload_path_tested'])
        self.verifier.assert_called_with(self.runtime,self.fixture.frozen,owner_kind='model_client',allow_empty=True)

    def test_actual_emitted_post_marker_layout_uses_complete_unfiltered_proof(self):
        events=self.events();marker=next(i for i,r in enumerate(events) if r.get('kind')=='client_finishing_before_close')
        self.assertEqual([r.get('phase',r['kind']) for r in events[marker+1:]],
                         ['finishing','stdin_closed','native_exit','completed','client_shutdown'])
        with self.assertRaisesRegex(ValueError,'unique owner-finishing'):
            P.dependency('transport_integrity').client_finishing(self.runtime,{},'model_client')
        result=self.assess();self.assertTrue(result['passed'],result['errors'])
        proof=result['client']['native_quiescence'];self.assertTrue(proof['passed'])
        for name,binding in proof['input_bindings'].items():
            self.assertEqual(result['inputs']['runtime/'+name],binding)
        self.assertEqual(proof['thread_closed']['thread_id'],'synthetic-thread')
        self.assertEqual([r['method'] for r in self.cleanup['controls']],['thread/unsubscribe'])
        self.assertEqual(self.cleanup['schema'],'campaign002-native-quiescence-2')
        self.assertEqual(len(proof['input_bindings']),10)

    def test_actual_controller_barrier_requires_original_endpoint_files_and_hashes(self):
        self.assertTrue(self.assess()['passed']);self.verifier.reset_mock()
        for name in ('codehost-transport-v3.jsonl','codehost-owner-stderr-v3.txt',
                     'codehost-owner-bridge-v3.json','codehost-native-owner-v3.json'):
            path=self.runtime/name;original=path.read_bytes()
            with self.subTest(name=name):
                path.write_bytes(original+b'{}\n')
                self.assertFalse(self.assess()['passed'])
                path.write_bytes(original)
        self.verifier.assert_not_called()

    def test_fixture_import_preserves_foreign_discovery_module(self):
        foreign=SimpleNamespace(marker='harness module with same filename')
        with patch.dict(sys.modules,{'test_client_quiescence':foreign}):
            fixture=assessment_fixture()
            self.assertIs(sys.modules['test_client_quiescence'],foreign)
            self.assertTrue(callable(fixture.synthetic_barrier_files))

    def test_inserted_missing_duplicate_and_reordered_lifecycle_rows_fail(self):
        original=self.events()
        for case in ('unknown','ordinary_response','unknown_native_phase','missing_marker','duplicate_marker',
                     'missing_shutdown','duplicate_shutdown','reordered_shutdown','missing_close','duplicate_control','wrong_response'):
            with self.subTest(case=case):
                rows=copy.deepcopy(original);marker=next(i for i,r in enumerate(rows) if r.get('kind')=='client_finishing_before_close')
                if case=='unknown':rows.insert(marker+1,{'kind':'invented'})
                elif case=='ordinary_response':rows.insert(marker+1,{'kind':'response','method':'thread/unsubscribe','id':11,'result':{'status':'unsubscribed'}})
                elif case=='unknown_native_phase':rows.insert(marker+1,{'kind':'native_quiescence','phase':'invented'})
                elif case=='missing_marker':rows.pop(marker)
                elif case=='duplicate_marker':rows.insert(marker,copy.deepcopy(rows[marker]))
                elif case=='missing_shutdown':rows.pop()
                elif case=='duplicate_shutdown':rows.append(copy.deepcopy(rows[-1]))
                elif case=='reordered_shutdown':rows.insert(marker+1,rows.pop())
                elif case=='missing_close':rows=[r for r in rows if r.get('phase')!='thread_closed']
                elif case=='duplicate_control':rows.insert(marker,copy.deepcopy(next(r for r in rows if r.get('phase')=='request')))
                else:next(r for r in rows if r.get('phase')=='response')['request_id']=999
                self.write_events(rows);result=self.assess();self.assertFalse(result['passed'],case)
        self.write_events(original);self.verifier.assert_not_called()

    def test_stderr_fixed_metadata_gate_remains_strict_before_and_after_marker(self):
        original=self.events()
        valid={'kind':'stderr','schema':'campaign002-stderr-metadata-1','bytes':7,'sha256':'a'*64,
               'wall_unix_s':1.,'monotonic_s':1.,'text_retained':False,'markers':[],
               'scope':'Fixed lexical markers only; no error message or causal diagnosis.'}
        for position in ('before','after'):
            rows=copy.deepcopy(original);i=next(i for i,r in enumerate(rows) if r.get('kind')=='client_finishing_before_close')
            rows.insert(i if position=='before' else i+1,copy.deepcopy(valid));self.write_events(rows)
            self.assertTrue(self.assess()['passed'])
            for key,value in (('bytes',True),('bytes',0),('bytes',33554433),('sha256','bad'),
                              ('markers',['unrecognized']),('markers',['grpc','grpc']),('text_retained',True),('extra','payload')):
                mutated=copy.deepcopy(rows);row=next(r for r in mutated if r.get('kind')=='stderr');row[key]=value
                self.write_events(mutated);self.assertFalse(self.assess()['passed'],(position,key))
        self.write_events(original)

    def test_proof_input_binding_cannot_change_or_omit_consumed_original(self):
        module=P.dependency('client_quiescence');actual=module.verify_client_quiescence
        for case in ('wrong_hash','missing','extra'):
            def altered(*args,**kwargs):
                proof=actual(*args,**kwargs)
                if case=='wrong_hash':proof['input_bindings']['client/native-quiescence.json']['sha256']='f'*64
                elif case=='missing':proof['input_bindings'].pop('client/preflight.json')
                else:proof['input_bindings']['fabricated.json']={'bytes':1,'sha256':'f'*64}
                return proof
            with self.subTest(case=case),patch.object(module,'verify_client_quiescence',side_effect=altered):
                self.assertFalse(self.assess()['passed'])
        self.verifier.assert_not_called()

    def test_unload_override_and_both_filtered_receipts_require_exact_zero(self):
        for name,field in (('launch.json','config_overrides'),('preflight.json','effective_config'),('result.json','effective_config')):
            path=self.runtime/'client'/name;original=old.get(path)
            for value in (None,False,True,0.0,'0',1,-1,60):
                with self.subTest(name=name,value=value):
                    document=copy.deepcopy(original)
                    if value is None:document[field].pop('thread_unload_delay_secs')
                    else:document[field]['thread_unload_delay_secs']=value
                    old.put(path,document)
                    self.assertFalse(self.assess()['passed'])
            old.put(path,original)
        self.verifier.assert_not_called()
        self.assertTrue(self.assess()['passed'])

    def test_owner_mismatch_and_missing_identity_fail_before_lifecycle(self):
        for field,value in [('pid',True),('process_creation_filetime',0),('owner_kind','transport_probe')]:
            with self.subTest(field=field):
                modified=copy.deepcopy(self.owner);modified[field]=value
                old.put(self.runtime/'client/native-owner.json',modified)
                self.assertFalse(self.assess()['passed'])
                old.put(self.runtime/'client/native-owner.json',self.owner)
        self.verifier.assert_not_called()

    def test_receipt_after_initialize_duplicate_or_wrong_hash_is_rejected(self):
        original=self.events()
        for case in ('late','duplicate','hash'):
            events=copy.deepcopy(original)
            if case=='late':events.insert(2,events.pop(0))
            elif case=='duplicate':events.insert(0,copy.deepcopy(events[0]))
            else:events[0]['receipt_sha256']='0'*64
            self.write_events(events)
            self.assertFalse(self.assess()['passed'],case)
        self.verifier.assert_not_called()

    def test_verifier_failure_missing_host_retirement_and_byte_mismatch_fail(self):
        self.proof['passed']=False
        self.assertFalse(self.assess()['passed'])
        self.proof['passed']=True
        self.proof['input_bindings']['client/native-owner.json']['sha256']='0'*64
        self.assertFalse(self.assess()['passed'])
        self.proof['input_bindings']['client/native-owner.json']=P.binding(self.runtime/'client/native-owner.json')
        (self.runtime/'codehost-owner-retirement-v3.json').unlink()
        self.assertFalse(self.assess()['passed'])

    def test_model_activity_and_changed_raw_option_still_fail(self):
        events=self.events();original=copy.deepcopy(events)
        events.append({'kind':'request','method':'turn/start','id':11,'params':{}})
        self.write_events(events);self.assertFalse(self.assess()['passed'])
        self.write_events(original)
        preflight=old.get(self.runtime/'client/preflight.json')
        preflight['experimental_raw_events_thread_start_accepted']=False
        old.put(self.runtime/'client/preflight.json',preflight)
        self.assertFalse(self.assess()['passed'])

    def test_executor_capture_delivery_and_retirement_remain_required(self):
        (self.runtime/'executor-2-retirement.json').unlink()
        self.assertFalse(self.assess()['passed'])

    def test_source_inventory_includes_owner_transport_and_prospective_contract(self):
        names=P.required_sources()
        for suffix in ('bootstrap_client_v4.py','codehost_owner.py','codehost_mux_protocol.py',
                       'transport_integrity_v3.py','raw_event_preflight_v2.py',
                       'CODEHOST_CHANNEL_TRANSPORT_V3.md','CHANNEL_TRANSPORT_V3_QUALIFICATION_001.md',
                       'NATIVE_THREAD_UNLOAD_SCHEDULING_V1.md','codex-rs__config__src__config_toml.rs',
                       'codex-rs__app-server__src__transport.rs','prepare_model_v13.py',
                       'PREFLIGHT_V3_LIFECYCLE_JOIN_V1.md'):
            self.assertEqual(sum(name.endswith('/'+suffix) for name in names),1)


if __name__=='__main__':unittest.main()
