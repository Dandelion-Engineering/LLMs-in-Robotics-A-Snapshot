"""Deterministic source/receipt/client tests; never create a native fixture."""
import argparse
import asyncio
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest import mock

import codehost_transport_probe_v3 as p
import codehost_bridge_v3 as bridge_module
import raw_event_preflight_v2 as raw


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value)+'\n',encoding='utf-8')


def canaries(root):
    write(root/'canary-stdout.json',{'qualified':True,'checks':{str(i):True for i in range(45)}})
    write(root/'codehost-canary-stdout.json',{'host_qualified':True,'model_calls':0,'enabled_tools':[],
        'checks':{'tools':[],'all_tools_count':0,'constructor_process_type':'undefined',
        'apis':{k:'undefined' for k in ('process','require','fetch','Deno','Bun','WebSocket','XMLHttpRequest')},
        'imports':{k:'denied' for k in ('node:fs','file:///etc/passwd','https://example.invalid/')}}})


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'output';self.root.mkdir()
        self.snapshot=Path(self.temp.name)/'snapshot.json';write(self.snapshot,{'revision':'dev-test'})
        self.frozen={'revision':'dev-test','sources':{'fixed.py':{'sha256':'a'*64,'bytes':1}}}
        self.source={'schema':'campaign002-channel-probe-source-3','run_id':'fixed-run','framework_revision':'dev-test',
            'snapshot_sha256':p.binding(self.snapshot)['sha256'],'source_bindings':self.frozen['sources'],
            'cases':p.make_cases(),'model_calls':0,'physical_simulation':False}
        write(self.root/'source-binding.json',self.source)
        self.proofs={}
        for case in p.CASES:
            root=self.root/case;root.mkdir();canaries(root)
            write(root/'cleanup.json',{'clean':True,'errors':[]})
            write(root/'case-run.json',{'schema':'campaign002-channel-case-run-3','case':case,
                'cleanup_clean':True,'setup_error_type':None,'canaries_completed':True,
                'elapsed_seconds':110,'start_monotonic_s':1,'end_monotonic_s':111,
                'bridge_completed':case=='multi_channel','bridge_error_type':None if case=='multi_channel' else 'RuntimeError'})
            write(root/'client-result.json',{'schema':'campaign002-channel-client-3','case':case,'completed':True,
                'model_calls':0,'child_exit_codes':{'owner':0,**({'foreign':0} if case=='foreign_owner' else {})},
                'result':{'idle_seconds':95,'channels':[{'channel_id':i,'closed_before_finish':i==2} for i in (1,2,3)]}})
            write(root/'proof-input.json',{'case':case})
            self.proofs[case]={'input_bindings':{'proof-input.json':p.binding(root/'proof-input.json')}}
            if case=='multi_channel':self.proofs[case]['passed']=True
            else:self.proofs[case].update(expected_failure_verified=True,diagnostic_only=True,ordinary_transport_passed=False)
        write(self.root/'multi_channel/codehost-owner-bridge-v3.json',{'accepted':3,'denied':0,
            'channels':[{'channel_id':2,'namespace_closed':{'reason':'clean_idle_eof'}}]})
        self.events=[{'kind':'channel_authenticated','channel_id':1,'monotonic_s':1},
            {'kind':'channel_authenticated','channel_id':2,'monotonic_s':97},
            {'kind':'channel_closed','channel_id':2,'monotonic_s':98},
            {'kind':'channel_authenticated','channel_id':3,'monotonic_s':99},
            {'kind':'channel_closed','channel_id':1,'monotonic_s':101},
            {'kind':'channel_closed','channel_id':3,'monotonic_s':102}]
        self.events[4:4]=[
            {'kind':'channel_finish_frontier','channel_id':1,'upload_read_pending':True,'h2':{'bytes':{'upload':42}},'monotonic_s':100},
            {'kind':'owner_drain_begin','monotonic_s':100}, {'kind':'owner_drain_ack','monotonic_s':100},
            {'kind':'frame','direction':'outgoing','frame_type':3,'channel_id':1,'payload_bytes':17,'payload_sha256':p.digest(p.SHUTDOWN_GOAWAY),'monotonic_s':100}]
        for i,event in enumerate(self.events,1):event['sequence']=i
        self.mutate('multi_channel/client-result.json',lambda v:v.update(finish={'monotonic_s':100},pending_read_shutdown={
            'schema':'campaign002-pending-read-shutdown-1','frontier':self.events[4],'drain_begin':self.events[5],
            'acknowledgment':self.events[6],'grant_monotonic_s':100,'control_sent_monotonic_s':100,'deadline_monotonic_s':125,
            'retained_ledger_prefix':{'path':'codehost-transport-v3.jsonl','bytes':len(b''.join(p.canonical(e)+b'\n' for e in self.events[:7])),
                                     'sha256':p.digest(b''.join(p.canonical(e)+b'\n' for e in self.events[:7]))},
            'shutdown_bytes':17,'shutdown_sha256':p.digest(p.SHUTDOWN_GOAWAY)}))
        self.mutate('multi_channel/codehost-owner-bridge-v3.json',lambda v:v['channels'].append({'channel_id':1,'meters':{'client_read':{'bytes':59}}}))
        self.ledger()
        self.verifier=types.SimpleNamespace(
            verify_transport_integrity=lambda root,frozen,**kw:copy.deepcopy(self.proofs[Path(root).name]),
            verify_expected_failure=lambda root,frozen,**kw:copy.deepcopy(self.proofs[Path(root).name]))
        def dep(name):
            return {'raw_event_preflight_v2':raw,'transport_integrity_v3':self.verifier}[name]
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(p,'dependency',side_effect=dep).start()
        mock.patch.object(p,'validate_snapshot',return_value=self.frozen).start()

    def ledger(self):
        (self.root/'multi_channel/codehost-transport-v3.jsonl').write_text(
            ''.join(json.dumps(e)+'\n' for e in self.events),encoding='utf-8')

    def mutate(self,path,fn):
        target=self.root/path;value=json.loads(target.read_text());fn(value);write(target,value)

    def result(self):return p.assess(self.root,self.snapshot)

    def test_replay_stable_with_exact_three_scopes_and_bound_inputs(self):
        result=self.result();self.assertTrue(result['passed'],result)
        self.assertEqual(result,self.result());self.assertEqual(result['model_calls'],0)
        self.assertEqual([r['production_qualified'] for r in result['cases']],[True,False,False])
        self.assertIn('foreign_owner/proof-input.json',result['inputs'])

    def test_false_or_nonboolean_production_proof_never_passes(self):
        for value in (False,1,None):
            self.proofs['multi_channel']['passed']=value;self.assertFalse(self.result()['passed'])

    def test_expected_failure_cannot_become_production_success(self):
        for key,value in [('expected_failure_verified',False),('diagnostic_only',1),('ordinary_transport_passed',True)]:
            original=self.proofs['foreign_owner'][key];self.proofs['foreign_owner'][key]=value
            self.assertFalse(self.result()['passed']);self.proofs['foreign_owner'][key]=original

    def test_missing_or_changed_dependent_input_fails(self):
        self.proofs['in_flight_eof']['input_bindings']={};self.assertFalse(self.result()['passed'])
        self.proofs['in_flight_eof']['input_bindings']={'proof-input.json':{'bytes':1,'sha256':'0'*64}}
        self.assertFalse(self.result()['passed'])

    def test_source_declaration_type_and_identity_strict(self):
        for change in (lambda s:s.update(model_calls=False),lambda s:s['cases'][0].update(model_calls=False),
                       lambda s:s.update(snapshot_sha256='0'*64),lambda s:s['source_bindings']['fixed.py'].update(bytes=True)):
            value=copy.deepcopy(self.source);change(value);write(self.root/'source-binding.json',value)
            self.assertFalse(self.result()['passed'])

    def test_lifetime_close_sequence_and_legacy_event_rejected(self):
        saved=copy.deepcopy(self.events)
        for index,key,value in ((1,'monotonic_s',95),(2,'monotonic_s',100),(0,'kind','connection_accepted')):
            self.events=copy.deepcopy(saved);self.events[index][key]=value;self.ledger()
            self.assertFalse(self.result()['passed'])

    def test_time_cap_cleanup_and_child_exit_are_strict(self):
        file='foreign_owner/case-run.json'
        self.mutate(file,lambda v:v.update(elapsed_seconds=181,end_monotonic_s=182))
        self.assertFalse(self.result()['passed'])
        self.mutate(file,lambda v:v.update(elapsed_seconds=110,end_monotonic_s=111))
        self.mutate('foreign_owner/client-result.json',lambda v:v.update(child_exit_codes={}))
        self.assertFalse(self.result()['passed'])
        self.mutate('foreign_owner/client-result.json',lambda v:v.update(child_exit_codes={'owner':0,'foreign':False}))
        self.assertFalse(self.result()['passed'])

    def test_canary_failure_and_output_bound_fail(self):
        self.mutate('multi_channel/canary-stdout.json',lambda v:v['checks'].update({'0':1}))
        self.assertFalse(self.result()['passed'])
        canaries(self.root/'multi_channel')
        with mock.patch.object(p,'CASE_BYTES',10):self.assertFalse(self.result()['passed'])


class SourceRunTests(unittest.TestCase):
    def test_validate_before_fixture_or_output(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'new';args=argparse.Namespace(snapshot=Path(temp)/'bad.json',framework_revision='x',run_id='r',output=output)
            with mock.patch.object(p,'validate_snapshot',side_effect=ValueError('bad source')),mock.patch.object(p,'run_case') as launch:
                with self.assertRaises(ValueError):p.run(args)
                launch.assert_not_called();self.assertFalse(output.exists())

    def test_existing_output_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);args=argparse.Namespace(snapshot=root/'s.json',framework_revision='x',run_id='r',output=root)
            with mock.patch.object(p,'validate_snapshot',return_value={'sources':{}}),mock.patch.object(p,'run_case') as launch:
                with self.assertRaises(FileExistsError):p.run(args)
                launch.assert_not_called()

    def test_source_closure_is_present_and_contains_test_method_protocol(self):
        sources=p.required_sources()
        self.assertTrue(all((p.REPO/n).is_file() for n in sources))
        for tail in ('test_codehost_transport_probe_v3.py','CODEHOST_CHANNEL_TRANSPORT_V3.md','codehost_mux_protocol.py',
                     'CHANNEL_PROBE_PROCESS_IDENTITY_V1.md','CHANNEL_FINISH_FRONTIER_VALIDATION_V1.md',
                     'CHANNEL_PROBE_SEQUENCE_SYNCHRONIZATION_V1.md'):
            self.assertTrue(any(n.endswith('/'+tail) for n in sources),tail)

    def test_partial_runtime_initialization_still_closes(self):
        class Runtime:
            closed=False
            def __init__(self,root,files):root.mkdir();raise ValueError('setup')
            def close(self):type(self).closed=True;return True
        with tempfile.TemporaryDirectory() as temp,mock.patch.object(p,'dependency',return_value=types.SimpleNamespace(Runtime=Runtime,template=lambda k:{})):
            result=p.run_case(Path(temp)/'case','multi_channel')
            self.assertTrue(Runtime.closed);self.assertEqual(result['setup_error_type'],'ValueError')
            self.assertFalse(result['bridge_completed'])


class FixedClientTests(unittest.TestCase):
    def exercise(self,mode):
        clock=[0];instances=[]
        class Channel:
            def __init__(self,port,channel_id,emit):
                self.id=channel_id;self.closed=False;self.sock=mock.Mock();self.sock.recv.return_value=b'';self.ping=None;self.sent=[];instances.append(self)
            def send(self,data):self.sent.append(data)
            def handshake(self,ping):self.ping=ping
            def close_idle(self):self.closed=True
            def summary(self):return {'channel_id':self.id,'closed_before_finish':self.closed}
        def sleep(seconds):clock[0]+=seconds
        controls=[{'port':1234}]
        if mode=='multi_channel':
            controls.extend({'phase':phase,'nonce':(letter*16).hex(),'pid':789,'grant':True}
                            for phase,letter in zip(('open_second','open_third','finish'),(b'a',b'b',b'c')))
        controls.append({'finish':True})
        with mock.patch.object(p,'SyntheticChannel',Channel),mock.patch.object(p.time,'sleep',side_effect=sleep),\
             mock.patch.object(p.time,'monotonic',side_effect=lambda:clock[0]),\
             mock.patch.object(p.os,'getpid',return_value=789),mock.patch.object(p.os,'urandom',side_effect=[b'a'*16,b'b'*16,b'c'*16]),\
             mock.patch.object(p.sys,'stdin',io.StringIO(''.join(json.dumps(v)+'\n' for v in controls))),\
             mock.patch.object(p.sys,'stdout',io.StringIO()) as output:
            code=p.client_main(mode);events=[json.loads(s) for s in output.getvalue().splitlines()]
        return code,events,instances

    def test_boundary_same_fixed_client_one_second_one_channel(self):
        code,events,channels=self.exercise('boundary_single_channel')
        self.assertEqual(code,0);self.assertEqual(len(channels),1);self.assertTrue(channels[0].ping)
        result=next(e['result'] for e in events if e['kind']=='ready_to_finish')
        self.assertEqual(result['idle_seconds'],1);self.assertEqual(events[-1]['kind'],'client_closed')

    def test_multi_channel_has_fixed_95_second_overlap_and_no_rpc(self):
        code,events,channels=self.exercise('multi_channel')
        self.assertEqual(code,0);self.assertEqual([c.id for c in channels],[1,2,3]);self.assertTrue(all(c.ping for c in channels))
        result=next(e['result'] for e in events if e['kind']=='ready_to_finish')
        self.assertEqual(result['idle_seconds'],95)
        self.assertEqual([c['closed_before_finish'] for c in result['channels']],[False,True,False])
        self.assertEqual(channels[0].sent,[p.SHUTDOWN_GOAWAY]);self.assertEqual(channels[2].sent,[])
        self.assertEqual(next(e['bytes'] for e in events if e['kind']=='channel_shutdown_control'),17)
        for c in (channels[0],channels[2]):c.sock.shutdown.assert_called_once_with(p.socket.SHUT_WR)
        self.assertEqual(len(p.PARTIAL_INPUT),45)
        self.assertEqual([e['phase'] for e in events if e['kind']=='probe_phase_request'],['open_second','open_third','finish'])

    def test_child_phase_grants_require_exact_phase_nonce_pid_and_literal_permission(self):
        correct={'phase':'open_third','nonce':(b'a'*16).hex(),'pid':789,'grant':True}
        for change in ({},{'phase':'finish'},{'nonce':'0'*32},{'pid':111},{'pid':True},{'grant':1},{'extra':True}):
            with self.subTest(change=change),mock.patch.object(p.os,'getpid',return_value=789),\
                 mock.patch.object(p.os,'urandom',return_value=b'a'*16),\
                 mock.patch.object(p.sys,'stdin',io.StringIO(json.dumps({**correct,**change})+'\n')):
                emit=mock.Mock()
                if change:
                    with self.assertRaises(ValueError):p.client_phase('open_third',emit)
                else:p.client_phase('open_third',emit)
                self.assertEqual(emit.call_args.args,('probe_phase_request',));self.assertEqual(emit.call_args.kwargs['nonce'],correct['nonce'])

    def test_unknown_mode_fails_before_output_or_connection(self):
        with mock.patch.object(p,'SyntheticChannel') as channel:
            with self.assertRaises(ValueError):p.client_main('custom')
            channel.assert_not_called()


class DriverTests(unittest.IsolatedAsyncioTestCase):
    async def exercise_driver(self,case='boundary_single_channel',ready_changes=None,stderr=b'',exit_code=0,
                              duplicate_pid=False,executable_changed=False):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        children=[];exe={'path':'declared-base-python','bytes':10,'sha256':'a'*64,'file_identity':[1,2,10,4]}
        ready_changes=ready_changes or {}
        result={'ready_to_finish':True,'idle_seconds':95,'channels':[{'channel_id':1}],
                'client':['127.0.0.1',2345],'server':['127.0.0.1',1234],'denial_eof_observed':True,
                'client_eof_before_owner_finish':True}
        class Process:
            def __init__(self,argv,**kw):
                self.argv=argv;self.pid=111 if not children or duplicate_pid else 222;self.returncode=None
                self.role='owner' if not children else 'foreign';self.stdin=io.BytesIO()
                ready={'kind':'client_ready','pid':self.pid,'mode':argv[-1],**ready_changes.get(self.role,{})}
                events=[ready]
                if argv[-1]=='multi_channel':
                    for index,phase in enumerate(('open_second','open_third','finish')):
                        events.append({'kind':'probe_phase_request','phase':phase,'nonce':str(index+1)*32,'pid':self.pid,
                            'wall_unix_s':100+index,'monotonic_s':95+index,
                            **({'idle_started_monotonic_s':0,'idle_observed_monotonic_s':95,'idle_seconds':95} if index==0 else {})})
                events.append({'kind':'ready_to_finish','result':result})
                self.stdout=io.BytesIO(b''.join(p.canonical(e)+b'\n' for e in events))
                self.stderr=io.BytesIO(stderr);children.append(self)
            def poll(self):return self.returncode
            def wait(self,timeout):self.returncode=exit_code;return exit_code
        def observe(pid):return {'pid':pid,'process_creation_filetime':pid+1,'queried_executable_path':exe['path']}
        owner=types.SimpleNamespace(WindowsOwnerAPI=lambda:types.SimpleNamespace(process=observe))
        def register(process,path):return {'schema':'campaign002-native-owner-1','owner_kind':'transport_probe',
                                          **observe(process.pid),'executable':exe,'wall_unix_s':1,'monotonic_s':1}
        fixture=types.SimpleNamespace(evidence=root,client_finishing=threading.Event(),
                                     native_process_ready=mock.Mock(side_effect=register),redact=lambda s:s.replace('SECRET','[REDACTED]'))
        values=[exe,{**exe,'sha256':'b'*64}] if executable_changed else None
        with mock.patch.object(p.subprocess,'Popen',Process),mock.patch.object(p,'dependency',return_value=owner),\
             mock.patch.object(p,'client_executable',side_effect=values,return_value=exe):
            try:
                value=await p.drive_clients('http://127.0.0.1:1234',fixture,case,p.time.monotonic()+180)
                raised=None
            except Exception as exc:value=None;raised=exc
        record=json.loads((root/'client-result.json').read_text(encoding='utf-8'))
        return root,children,fixture,record,raised,value

    async def test_direct_executable_and_matching_actual_popen_registration(self):
        root,children,fixture,record,raised,value=await self.exercise_driver()
        self.assertIsNone(raised);self.assertTrue(record['completed']);self.assertTrue(value['completed'])
        self.assertEqual(children[0].argv[0],'declared-base-python')
        self.assertIs(fixture.native_process_ready.call_args.args[0],children[0])
        self.assertEqual(fixture.native_process_ready.call_args.args[1],children[0].argv[0])
        self.assertEqual(json.loads(children[0].stdin.getvalue().splitlines()[0]),{'port':1234})
        self.assertTrue(record['diagnostics']['owner']['complete'])
        self.assertEqual(json.loads((root/'client-executable.json').read_text()),record['launch_executable'])

    async def test_owner_ready_pid_mode_type_and_first_event_fail_before_port(self):
        for change in ({'pid':222},{'pid':True},{'mode':'foreign'},{'kind':'premature_event'}):
            with self.subTest(change=change):
                root,children,fixture,record,raised,_=await self.exercise_driver(ready_changes={'owner':change})
                self.assertIsInstance(raised,ValueError);self.assertFalse(record['completed'])
                self.assertEqual(record['error_type'],'ValueError');fixture.native_process_ready.assert_not_called()
                self.assertNotIn(b'"port"',children[0].stdin.getvalue())
                self.assertTrue((root/'client/owner-stdout.txt').is_file())

    async def test_foreign_role_exact_ready_and_distinct_pid_gate_before_its_port(self):
        for change,duplicate in [({'pid':111},False),({'mode':'hold'},False),({},True)]:
            with self.subTest(change=change,duplicate=duplicate):
                _,children,fixture,record,raised,_=await self.exercise_driver('foreign_owner',
                    ready_changes={'foreign':change},duplicate_pid=duplicate)
                self.assertIsInstance(raised,ValueError);self.assertFalse(record['completed'])
                self.assertEqual(fixture.native_process_ready.call_count,1)
                self.assertIn(b'"port"',children[0].stdin.getvalue());self.assertNotIn(b'"port"',children[1].stdin.getvalue())

    async def test_foreign_role_uses_same_executable_distinct_actual_process(self):
        _,children,fixture,record,raised,_=await self.exercise_driver('foreign_owner')
        self.assertIsNone(raised);self.assertTrue(record['completed']);self.assertEqual(len(children),2)
        self.assertNotEqual(record['owner']['pid'],record['sibling']['pid'])
        self.assertEqual([c.argv[0] for c in children],['declared-base-python']*2)
        self.assertEqual(fixture.native_process_ready.call_count,1)

    async def test_changed_executable_rejected_before_popen_with_incomplete_receipt(self):
        root,children,fixture,record,raised,_=await self.exercise_driver(executable_changed=True)
        self.assertIsInstance(raised,ValueError);self.assertEqual(children,[])
        fixture.native_process_ready.assert_not_called();self.assertFalse(record['completed'])
        self.assertTrue((root/'client-result.json').is_file())

    async def test_stderr_and_nonzero_exit_are_retained_before_failure_propagates(self):
        for stderr,code in ((b'SECRET\n',0),(b'',7),(b'bad\xff\n',1)):
            with self.subTest(stderr=stderr,code=code):
                root,_,_,record,raised,_=await self.exercise_driver(stderr=stderr,exit_code=code)
                self.assertIsInstance(raised,ValueError);self.assertFalse(record['completed']);self.assertTrue(record['errors'])
                self.assertEqual(record['child_exit_codes'],{'owner':code})
                stream=record['diagnostics']['owner']['streams']['stderr']
                self.assertEqual(stream['raw_bytes'],len(stderr));self.assertEqual(stream['raw_sha256'],p.digest(stderr))
                retained=(root/stream['path']).read_bytes();self.assertNotIn(b'SECRET',retained)
                self.assertEqual(p.binding(root/stream['path']),{k:stream[k] for k in ('sha256','bytes')})
                if b'\xff' in stderr:self.assertEqual(stream['decode_error_type'],'UnicodeDecodeError')

    async def test_sync_timeout_retains_incomplete_result_and_original_cleanup(self):
        with mock.patch.object(p,'synchronize_in_flight_eof',side_effect=TimeoutError('bounded')) as sync:
            root,children,fixture,record,raised,_=await self.exercise_driver('in_flight_eof')
        self.assertIsInstance(raised,TimeoutError);self.assertFalse(record['completed'])
        self.assertEqual(record['error_type'],'TimeoutError');self.assertIsNone(record['in_flight_synchronization'])
        self.assertTrue(fixture.client_finishing.is_set());self.assertEqual(children[0].returncode,0)
        self.assertIn(b'"finish":true',children[0].stdin.getvalue());self.assertTrue((root/'client/owner-stderr.txt').is_file())
        self.assertIs(sync.call_args.args[1],children[0])

    async def test_actual_finish_clock_recheck_cannot_be_bypassed_by_sync_receipt(self):
        now=p.time.monotonic();proof={'eof':{'monotonic_s':now+100},'clock_observed_monotonic_s':now+101,
                                    'synchronization_deadline_monotonic_s':now+145}
        with mock.patch.object(p,'synchronize_in_flight_eof',return_value=proof):
            root,_,fixture,record,raised,_=await self.exercise_driver('in_flight_eof')
        self.assertIsInstance(raised,ValueError);self.assertFalse(record['completed']);self.assertFalse(fixture.client_finishing.is_set())
        self.assertIn({'stage':'durable_finishing','error_type':'ValueError'},record['errors'])
        events=[json.loads(s) for s in (root/'client/events.jsonl').read_text().splitlines()]
        self.assertNotIn('client_finishing_before_close',[e['kind'] for e in events])

    async def test_actual_finish_retains_strictly_earlier_sync_eof_and_original_deadline(self):
        now=p.time.monotonic();proof={'eof':{'monotonic_s':now-1},'clock_observed_monotonic_s':now,
                                    'synchronization_deadline_monotonic_s':now+145}
        with mock.patch.object(p,'synchronize_in_flight_eof',return_value=proof):
            _,_,_,record,raised,_=await self.exercise_driver('in_flight_eof')
        self.assertIsNone(raised);self.assertTrue(record['completed']);self.assertEqual(record['in_flight_synchronization'],proof)
        self.assertGreater(record['finish']['monotonic_s'],proof['eof']['monotonic_s'])
        self.assertLess(record['finish']['monotonic_s'],proof['synchronization_deadline_monotonic_s'])

    async def test_multi_driver_exact_grants_and_single_controller_row(self):
        async def async_proof(runtime,owner,deadline):return {'grant_monotonic_s':p.time.monotonic(),'deadline_monotonic_s':deadline}
        async def sync(fixture,owner,deadline,request,phase,prior):
            self.assertEqual(len(prior),('open_second','open_third','finish').index(phase))
            now=p.time.monotonic()
            return {'phase':phase,'nonce':request['nonce'],'reference':{'monotonic_s':now-1},
                    'clock_observed_monotonic_s':now,'synchronization_deadline_monotonic_s':deadline-35}
        with mock.patch.object(p,'synchronize_multi_phase',side_effect=sync) as synchronizer, mock.patch.object(p,'synchronize_shutdown_read',side_effect=async_proof) as shutdown:
            root,children,_,record,raised,_=await self.exercise_driver('multi_channel')
        self.assertIsNone(raised);self.assertTrue(record['completed']);self.assertEqual(synchronizer.call_count,3)
        controls=[json.loads(s) for s in children[0].stdin.getvalue().splitlines()]
        self.assertEqual([v.get('phase') for v in controls[1:-1]],['open_second','open_third','finish'])
        for control,proof in zip(controls[1:-1],record['multi_channel_synchronization']):
            self.assertEqual(control,proof['grant']);self.assertEqual(control['nonce'],proof['nonce']);self.assertEqual(control['pid'],111)
        rows=[json.loads(s) for s in (root/'client-transcript.jsonl').read_text().splitlines()]
        controller=[row for row in rows if row['role']=='controller']
        self.assertEqual(len(controller),1);self.assertEqual(controller[0]['event']['kind'],'client_finishing_before_close')

    async def test_multi_phase_deadline_failure_retains_partial_grants_and_incomplete_cleanup(self):
        async def sync(fixture,owner,deadline,request,phase,prior):
            if phase=='open_third':raise TimeoutError('original deadline')
            return {'phase':phase,'nonce':request['nonce'],'clock_observed_monotonic_s':p.time.monotonic(),
                    'synchronization_deadline_monotonic_s':deadline-35}
        with mock.patch.object(p,'synchronize_multi_phase',side_effect=sync):
            root,children,fixture,record,raised,_=await self.exercise_driver('multi_channel')
        self.assertIsInstance(raised,TimeoutError);self.assertFalse(record['completed']);self.assertEqual(record['error_type'],'TimeoutError')
        self.assertEqual(len(record['multi_channel_synchronization']),1);self.assertTrue(fixture.client_finishing.is_set())
        self.assertEqual(children[0].returncode,0);self.assertTrue((root/'client/owner-stdout.txt').exists())
        controls=[json.loads(s) for s in children[0].stdin.getvalue().splitlines()]
        self.assertEqual([v.get('phase') for v in controls if 'phase' in v],['open_second']);self.assertEqual(controls[-1],{'finish':True})

    async def test_multi_actual_finish_rechecks_strict_third_admission(self):
        async def sync(fixture,owner,deadline,request,phase,prior):
            now=p.time.monotonic()
            return {'phase':phase,'nonce':request['nonce'],'reference':{'monotonic_s':now+100},
                    'clock_observed_monotonic_s':now,'synchronization_deadline_monotonic_s':deadline-35}
        with mock.patch.object(p,'synchronize_multi_phase',side_effect=sync):
            _,_,fixture,record,raised,_=await self.exercise_driver('multi_channel')
        self.assertIsInstance(raised,ValueError);self.assertFalse(record['completed']);self.assertFalse(fixture.client_finishing.is_set())
        self.assertIn({'stage':'durable_finishing','error_type':'ValueError'},record['errors'])

    async def test_registration_and_finish_receipts_survive_fake_child(self):
        with tempfile.TemporaryDirectory() as temp:
            identity={'pid':111,'process_creation_filetime':222,'queried_executable_path':'python','executable':{'path':'python'}}
            receipt={'schema':'campaign002-native-owner-1','owner_kind':'transport_probe',**identity,'wall_unix_s':1,'monotonic_s':1}
            result={'ready_to_finish':True,'idle_seconds':1,'channels':[{'channel_id':1}]}
            class Process:
                pid=111
                def __init__(self,*a,**kw):self.stdin=io.BytesIO();self.returncode=None
                def poll(self):return self.returncode
                def wait(self,timeout):self.returncode=0;return 0
            class Log:
                def __init__(self,process,role,*a):self.process=process;self.role=role
                async def event(self,kind,deadline):return {'kind':kind,'result':result,'pid':111,'mode':'boundary_single_channel'}
                def finish(self,*a):return {'errors':[],'complete':True,'streams':{}}
            fixture=types.SimpleNamespace(evidence=Path(temp),client_finishing=threading.Event(),native_process_ready=mock.Mock(return_value=receipt),redact=lambda x:x)
            owner=types.SimpleNamespace(WindowsOwnerAPI=lambda:types.SimpleNamespace(process=lambda pid:{k:v for k,v in identity.items() if k!='executable'}),
                                        file_identity=lambda path:identity['executable'])
            with mock.patch.object(p.subprocess,'Popen',Process),mock.patch.object(p,'ChildLog',Log),mock.patch.object(p,'dependency',return_value=owner),\
                 mock.patch.object(p,'client_executable',return_value=identity['executable']):
                value=await p.drive_clients('http://127.0.0.1:1234',fixture,'boundary_single_channel',p.time.monotonic()+180)
            self.assertTrue(value['completed']);self.assertTrue(fixture.client_finishing.is_set())
            root=Path(temp);rows=[json.loads(r) for r in (root/'client/events.jsonl').read_text().splitlines()]
            self.assertEqual([r['kind'] for r in rows],['native_process_owner_registered','client_finishing_before_close','probe_client_closed'])
            self.assertEqual(rows[0]['receipt_sha256'],p.binding(root/'client/native-owner.json')['sha256'])
            self.assertEqual(json.loads((root/'client/native-owner.json').read_text()),receipt)
            self.assertFalse(json.loads((root/'diagnostic-case.json').read_text())['expected_failure'])
            self.assertEqual(value['launch_executable'],identity['executable'])
            self.assertEqual(fixture.native_process_ready.call_args.args[1],'python')

    async def test_deadline_rejects_before_popen(self):
        fixture=types.SimpleNamespace()
        with mock.patch.object(p.subprocess,'Popen') as launch:
            with self.assertRaises(ValueError):await p.drive_clients('unused',fixture,'multi_channel',p.time.monotonic()+100)
            launch.assert_not_called()

    async def test_boundary_uses_actual_bridge_api_and_no_case_expansion(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture=types.SimpleNamespace(evidence=Path(temp));seen=[]
            write(Path(temp)/'client-result.json',{});(Path(temp)/'client-transcript.jsonl').write_text('{}\n')
            async def run(f,callback):seen.append(f);return await callback('http://127.0.0.1:1')
            async def drive(url,f,case,deadline):
                self.assertEqual(case,'boundary_single_channel')
                return {'completed':True,'result':{'channels':[{}],'idle_seconds':1}}
            with mock.patch.object(p,'dependency',return_value=types.SimpleNamespace(run=run)),mock.patch.object(p,'drive_clients',side_effect=drive):
                result=await p.boundary_probe(fixture)
            self.assertTrue(result['qualified']);self.assertEqual(fixture.native_owner_kind,'transport_probe')
            self.assertEqual(len(seen),1);self.assertEqual(len(p.make_cases()),3)


class DiagnosticRetentionTests(unittest.TestCase):
    def retain(self,stdout,stderr,redact=lambda s:s,limit=None):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name);(root/'client').mkdir()
        process=types.SimpleNamespace(stdout=io.BytesIO(stdout),stderr=io.BytesIO(stderr))
        with mock.patch.object(p,'CLIENT_BYTES',limit or p.CLIENT_BYTES):
            log=p.ChildLog(process,'owner',root/'transcript.jsonl',threading.Lock())
            result=log.finish(root,redact)
        return root,result

    def test_output_overflow_drained_counted_hashed_and_bounded_without_partial_secret(self):
        data=b'valid line\n'+b'SECRET'*30
        root,result=self.retain(b'',data,limit=64)
        state=result['streams']['stderr'];self.assertFalse(result['complete']);self.assertTrue(state['truncated'])
        self.assertTrue(state['capture_complete']);self.assertEqual(state['raw_bytes'],len(data))
        self.assertEqual(state['raw_sha256'],p.digest(data));self.assertLessEqual(state['bytes'],64)
        self.assertEqual((root/state['path']).read_bytes(),b'valid line\n')

    def test_malformed_stdout_and_redaction_failure_leave_bounded_typed_diagnostics(self):
        def reject(_):raise RuntimeError('PRIVATE VALUE')
        root,result=self.retain(b'not json\xff\n',b'secret\n',reject)
        self.assertFalse(result['complete'])
        for state in result['streams'].values():
            raw=(root/state['path']).read_bytes();self.assertNotIn(b'secret',raw);self.assertNotIn(b'PRIVATE',raw)
            self.assertEqual(state['redaction_error_type'],'RuntimeError')
        self.assertEqual(result['streams']['stdout']['decode_error_type'],'UnicodeDecodeError')


class EofSynchronizationTests(unittest.IsolatedAsyncioTestCase):
    def fixture(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        fixture=types.SimpleNamespace(evidence=root,run='fixed-test',client_finishing=threading.Event(),abort_event=threading.Event())
        launch=mock.Mock();retire=mock.Mock()
        bridge=bridge_module.Bridge(fixture,owner=object(),launcher=launch,retirer=retire,sources={})
        fixture.native_process_ready=bridge.register_native
        owner=types.SimpleNamespace(pid=111,poll=lambda:None)
        self.addCleanup(launch.assert_not_called);self.addCleanup(retire.assert_not_called)
        return fixture,bridge,owner

    async def rejection(self,fixture,bridge,owner):
        class Reader:
            def __init__(self):self.chunks=[p.PARTIAL_INPUT,b'']
            async def read(self,size):return self.chunks.pop(0)
        auth={'owner_pid':owner.pid}
        channel=bridge_module.Channel(1,Reader(),None,auth);bridge.channels[1]=channel
        channel.h2.feed('download',p.SETTINGS+p.SETTINGS_ACK)
        clock=types.SimpleNamespace(time=lambda:100.0,monotonic=lambda:5.0)
        with mock.patch.object(bridge_module,'time',clock):
            bridge.ledger.emit('channel_authenticated',channel_id=1,authentication=auth)
            with self.assertRaises(ValueError):await bridge.upload(channel)
            bridge.fail('channel_ValueError')
        self.assertTrue(fixture.abort_event.is_set());self.assertFalse(fixture.client_finishing.is_set())

    def rewrite(self,bridge):
        previous=None
        for sequence,row in enumerate(bridge.ledger.events,1):
            row.update(sequence=sequence,previous_sha256=previous)
            row['record_sha256']=p.digest(bridge_module.mux.canonical({k:v for k,v in row.items() if k!='record_sha256'}))
            previous=row['record_sha256']
        raw=b''.join(bridge_module.mux.canonical(row)+b'\n' for row in bridge.ledger.events)
        bridge.ledger.path.write_bytes(raw);bridge.ledger.previous=previous;bridge.ledger.bytes=len(raw)

    async def test_actual_upload_and_durable_fail_wake_waiter_and_equal_ticks_wait_until_later(self):
        fixture,bridge,owner=self.fixture();clock=[5.0];yields=[];original_sleep=asyncio.sleep
        async def yield_tick(delay):
            self.assertEqual(delay,0);self.assertFalse(fixture.client_finishing.is_set())
            self.assertEqual([r['kind'] for r in bridge.ledger.events],['channel_authenticated','client_eof','failure'])
            yields.append(delay)
            if len(yields)==3:clock[0]=5.016
            await original_sleep(0)
        with mock.patch.object(p,'time',types.SimpleNamespace(monotonic=lambda:clock[0])),\
             mock.patch.object(p.asyncio,'sleep',side_effect=yield_tick):
            task=asyncio.create_task(p.synchronize_in_flight_eof(fixture,owner,100))
            await original_sleep(0);self.assertFalse(task.done());self.assertEqual(bridge.ledger.events,[])
            await self.rejection(fixture,bridge,owner)
            proof=await task
        self.assertEqual(len(yields),3);self.assertEqual(proof['clock_observed_monotonic_s'],5.016)
        self.assertEqual(proof['eof']['monotonic_s'],5.0);self.assertEqual(proof['failure']['sequence'],3)
        self.assertEqual(proof['synchronization_deadline_monotonic_s'],65)
        self.assertEqual(proof['retained_ledger_prefix'],{'path':bridge.ledger.path.name,**p.binding(bridge.ledger.path)})
        self.assertEqual(proof['eof']['record_sha256'],bridge.channels[1].parent_eof['record_sha256'])
        self.assertFalse(fixture.client_finishing.is_set());self.assertFalse(bridge.finishing)

    async def test_exact_live_callback_owner_and_unfinished_state_required(self):
        for change in ('callback','fixture','owner_dead','flag','bridge_finished'):
            with self.subTest(change=change):
                fixture,bridge,owner=self.fixture();await self.rejection(fixture,bridge,owner)
                if change=='callback':fixture.native_process_ready=lambda *a:None
                elif change=='fixture':bridge.fixture=object()
                elif change=='owner_dead':owner.poll=lambda:0
                elif change=='flag':fixture.client_finishing.set()
                else:bridge.finishing=True
                with mock.patch.object(p,'time',types.SimpleNamespace(monotonic=lambda:6.0)):
                    with self.assertRaises(ValueError):await p.synchronize_in_flight_eof(fixture,owner,100)

    async def test_missing_duplicate_wrong_phase_order_and_foreign_failures_rejected(self):
        for change in ('missing_eof','duplicate','wrong_channel','finishing','wrong_owner','reordered','other_failure','changed_file','bad_hash','bad_upload'):
            with self.subTest(change=change):
                fixture,bridge,owner=self.fixture();await self.rejection(fixture,bridge,owner)
                rows=bridge.ledger.events;eof=bridge.channels[1].parent_eof
                if change=='missing_eof':rows.remove(eof)
                elif change=='duplicate':rows.insert(2,dict(eof))
                elif change=='wrong_channel':eof['channel_id']=2
                elif change=='finishing':eof['client_finishing']=True
                elif change=='wrong_owner':rows[0]['authentication']['owner_pid']=222
                elif change=='reordered':rows[1],rows[2]=rows[2],rows[1]
                elif change=='other_failure':rows[-1]['reason']='channel_OwnerError';bridge.failures=['channel_OwnerError']
                elif change=='bad_upload':eof['h2']['bytes']['upload']=44
                self.rewrite(bridge)
                if change=='changed_file':bridge.ledger.path.write_bytes(b'changed\n')
                if change=='bad_hash':rows[-1]['record_sha256']='0'*64;bridge.ledger.path.write_bytes(b''.join(bridge_module.mux.canonical(r)+b'\n' for r in rows))
                with mock.patch.object(p,'time',types.SimpleNamespace(monotonic=lambda:6.0)):
                    with self.assertRaises(ValueError):await p.synchronize_in_flight_eof(fixture,owner,100)
                self.assertFalse(fixture.client_finishing.is_set())

    async def test_malformed_future_reordered_clocks_and_later_foreign_failure_rejected(self):
        for value in (True,7.0,4.0):
            fixture,bridge,owner=self.fixture();await self.rejection(fixture,bridge,owner)
            bridge.channels[1].parent_eof['monotonic_s']=value;self.rewrite(bridge)
            with mock.patch.object(p,'time',types.SimpleNamespace(monotonic=lambda:6.0)):
                with self.assertRaises(ValueError):await p.synchronize_in_flight_eof(fixture,owner,100)
        fixture,bridge,owner=self.fixture();await self.rejection(fixture,bridge,owner)
        original_sleep=asyncio.sleep
        async def change_failure(delay):
            bridge.failures.append('unexpected_failure');await original_sleep(0)
        with mock.patch.object(p,'time',types.SimpleNamespace(monotonic=lambda:5.0)),\
             mock.patch.object(p.asyncio,'sleep',side_effect=change_failure):
            with self.assertRaises(ValueError):await p.synchronize_in_flight_eof(fixture,owner,100)

    async def test_missing_signal_and_clock_advance_use_original_deadline_without_extension(self):
        fixture,bridge,owner=self.fixture()
        signal=types.SimpleNamespace(is_set=lambda:False,wait=mock.Mock(return_value=False));fixture.abort_event=signal
        with mock.patch.object(p,'time',types.SimpleNamespace(monotonic=lambda:5.0)):
            with self.assertRaises(TimeoutError):await p.synchronize_in_flight_eof(fixture,owner,41)
        signal.wait.assert_called_once_with(1.0);self.assertFalse(fixture.client_finishing.is_set())
        fixture,bridge,owner=self.fixture();await self.rejection(fixture,bridge,owner)
        clock=[5.0];original_sleep=asyncio.sleep
        async def expire(delay):clock[0]=6.0;await original_sleep(0)
        with mock.patch.object(p,'time',types.SimpleNamespace(monotonic=lambda:clock[0])),\
             mock.patch.object(p.asyncio,'sleep',side_effect=expire):
            with self.assertRaises(TimeoutError):await p.synchronize_in_flight_eof(fixture,owner,41)
        self.assertFalse(fixture.client_finishing.is_set())


class MultiSynchronizationTests(unittest.IsolatedAsyncioTestCase):
    def fixture(self):return EofSynchronizationTests.fixture(self)

    def admit(self,bridge,owner,cid,stamp):
        auth={'owner_pid':owner.pid};channel=bridge_module.Channel(cid,None,None,auth)
        channel.state='open';channel.opened.set_result(True)
        upload=p.PREFACE+p.SETTINGS+p.SETTINGS_ACK;download=p.SETTINGS+p.SETTINGS_ACK
        channel.h2.feed('upload',upload);channel.h2.feed('download',download)
        for key in ('client_read','upload'):channel.meters[key].add(upload)
        for key in ('download','client_written'):channel.meters[key].add(download)
        bridge.channels[cid]=channel
        with mock.patch.object(bridge_module,'time',types.SimpleNamespace(time=lambda:1000+stamp,monotonic=lambda:stamp)):
            bridge.ledger.emit('channel_authenticated',channel_id=cid,authentication=auth)
        return channel

    async def close_second(self,bridge,stamp=95.016):
        channel=bridge.channels[2]
        channel.namespace_closed={'schema':'campaign002-codehost-channel-3','channel_id':2,'qualified':True,
            'error_type':None,'reason':'clean_idle_eof','upload':channel.meters['upload'].summary(),
            'download':channel.meters['download'].summary()}
        channel.queue.put_nowait(None)
        with mock.patch.object(bridge_module,'time',types.SimpleNamespace(time=lambda:1000+stamp,monotonic=lambda:stamp)):
            await bridge.sink(channel)

    def request(self,phase):
        index=('open_second','open_third','finish').index(phase)
        return {'kind':'probe_phase_request','phase':phase,'nonce':str(index+1)*32,'pid':111,
                'wall_unix_s':1095+index,'monotonic_s':(95.0,95.016,95.032)[index],
                **({'idle_started_monotonic_s':0.0,'idle_observed_monotonic_s':95.0,'idle_seconds':95.0} if index==0 else {})}

    async def prepare(self,phase):
        fixture,bridge,owner=self.fixture();self.admit(bridge,owner,1,0.0);prior=[]
        if phase!='open_second':
            self.admit(bridge,owner,2,95.0);await self.close_second(bridge)
            prior.append({'phase':'open_second','nonce':'1'*32,'grant_monotonic_s':95.0})
        if phase=='finish':
            self.admit(bridge,owner,3,95.032)
            prior.append({'phase':'open_third','nonce':'2'*32,'grant_monotonic_s':95.032})
        return fixture,bridge,owner,prior

    async def test_all_three_exact_source_gates_preserve_inclusive_idle_and_strict_close_ticks(self):
        fixture,bridge,owner,prior=await self.prepare('open_second');clock=[95.0];yields=[];original_sleep=asyncio.sleep
        async def advance(delay):
            self.assertEqual(delay,0);self.assertFalse(fixture.client_finishing.is_set())
            self.assertFalse(bridge.channels[1].closed.done());yields.append(clock[0]);clock[0]+=.016
            await original_sleep(0)
        with mock.patch.object(p,'time',types.SimpleNamespace(monotonic=lambda:clock[0])),\
             mock.patch.object(p.asyncio,'sleep',side_effect=advance):
            first=await p.synchronize_multi_phase(fixture,owner,180,self.request('open_second'),'open_second',prior)
            self.assertEqual(first['clock_observed_monotonic_s'],95.0);self.assertEqual(yields,[])
            prior.append({**first,'grant_monotonic_s':clock[0]})
            self.admit(bridge,owner,2,95.0);await self.close_second(bridge);clock[0]=95.016
            second=await p.synchronize_multi_phase(fixture,owner,180,self.request('open_third'),'open_third',prior)
            self.assertGreater(second['clock_observed_monotonic_s'],second['reference']['monotonic_s'])
            prior.append({**second,'grant_monotonic_s':clock[0]})
            self.admit(bridge,owner,3,clock[0]);clock[0]=bridge.ledger.events[-1]['monotonic_s']
            request=self.request('finish');request['monotonic_s']=clock[0]
            third=await p.synchronize_multi_phase(fixture,owner,180,request,'finish',prior)
        self.assertEqual(len(yields),2);self.assertEqual(third['admitted_ids'],[1,2,3]);self.assertEqual(third['closed_ids'],[2])
        self.assertGreater(third['clock_observed_monotonic_s'],third['reference']['monotonic_s'])
        self.assertEqual(third['synchronization_deadline_monotonic_s'],145)
        self.assertEqual(third['retained_ledger_prefix'],{'path':bridge.ledger.path.name,**p.binding(bridge.ledger.path)})
        self.assertFalse(bridge.channels[1].closed.done());self.assertFalse(bridge.channels[3].closed.done())

    async def test_request_phase_nonce_pid_original_idle_and_exact_fields_are_required(self):
        changes=[('open_second',{'phase':'open_third'}),('open_second',{'pid':True}),('open_second',{'pid':222}),
                 ('open_second',{'nonce':'X'*32}),('open_second',{'nonce':'short'}),('open_second',{'extra':0}),
                 ('open_second',{'idle_seconds':94.999}),('open_second',{'idle_started_monotonic_s':-1.0,'idle_observed_monotonic_s':94.0}),
                 ('open_second',{'monotonic_s':200.0}),('open_third',{'nonce':'1'*32})]
        for phase,change in changes:
            with self.subTest(phase=phase,change=change):
                fixture,_,owner,prior=await self.prepare(phase);request={**self.request(phase),**change}
                with mock.patch.object(p,'time',types.SimpleNamespace(monotonic=lambda:96.0)):
                    with self.assertRaises(ValueError):await p.synchronize_multi_phase(fixture,owner,180,request,phase,prior)
                self.assertFalse(fixture.client_finishing.is_set())
        fixture,_,owner,prior=await self.prepare('finish');prior.reverse()
        with self.assertRaises(ValueError):await p.synchronize_multi_phase(fixture,owner,180,self.request('finish'),'finish',prior)

    async def test_early_close_wrong_admissions_changed_or_duplicate_receipts_and_failures_reject(self):
        for change in ('early_close1','third_early','duplicate_close','changed_file','nonidle','wrong_owner',
                       'abort','owner_dead','finishing','failure','late_clock','reordered_clock'):
            with self.subTest(change=change):
                fixture,bridge,owner,prior=await self.prepare('open_third')
                if change=='early_close1':bridge.channels[1].closed.set_result(True)
                elif change=='third_early':self.admit(bridge,owner,3,95.032)
                elif change=='duplicate_close':bridge.ledger.events.append(dict(bridge.ledger.events[-1]))
                elif change=='nonidle':bridge.channels[2].namespace_closed['reason']='owner_finish'
                elif change=='wrong_owner':bridge.ledger.events[0]['authentication']['owner_pid']=222
                elif change=='abort':fixture.abort_event.set()
                elif change=='owner_dead':owner.poll=lambda:0
                elif change=='finishing':fixture.client_finishing.set()
                elif change=='failure':bridge.failures.append('unexpected')
                elif change=='late_clock':bridge.ledger.events[-1]['monotonic_s']=97.0
                elif change=='reordered_clock':bridge.ledger.events[-1]['monotonic_s']=94.0
                EofSynchronizationTests.rewrite(self,bridge)
                if change=='changed_file':bridge.ledger.path.write_bytes(b'changed\n')
                with mock.patch.object(p,'time',types.SimpleNamespace(monotonic=lambda:96.0)):
                    with self.assertRaises(ValueError):await p.synchronize_multi_phase(fixture,owner,180,self.request('open_third'),'open_third',prior)

    async def test_missing_events_and_tied_clock_cannot_extend_original_deadline(self):
        for phase,missing in (('open_second',True),('open_third',True),('finish',False)):
            fixture,bridge,owner,prior=await self.prepare(phase)
            if missing:
                if phase=='open_second':bridge.ledger.events.clear();bridge.channels.clear()
                else:bridge.ledger.events.pop()
                EofSynchronizationTests.rewrite(self,bridge)
            stamp=self.request(phase)['monotonic_s'];clock=[stamp];original_sleep=asyncio.sleep
            async def expire(delay):clock[0]=100.0;await original_sleep(0)
            with mock.patch.object(p,'time',types.SimpleNamespace(monotonic=lambda:clock[0])),\
                 mock.patch.object(p.asyncio,'sleep',side_effect=expire):
                with self.assertRaises(TimeoutError):await p.synchronize_multi_phase(fixture,owner,135,self.request(phase),phase,prior)
            self.assertFalse(fixture.client_finishing.is_set())

    async def test_unsolicited_duplicate_request_or_early_completion_is_not_discarded(self):
        for awaited,event in (('ready_to_finish',{'kind':'probe_phase_request'}),('probe_phase_request',{'kind':'ready_to_finish'})):
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);(root/'client').mkdir()
                process=types.SimpleNamespace(stdout=io.BytesIO(p.canonical(event)+b'\n'),stderr=io.BytesIO(),poll=lambda:None)
                log=p.ChildLog(process,'owner',root/'transcript.jsonl',threading.Lock())
                log.workers[0].join(timeout=1)
                with self.assertRaises(ValueError):await log.event(awaited,p.time.monotonic()+1)
                detail=log.finish(root,lambda s:s);self.assertTrue(detail['complete'])


class DirectExecutableTests(unittest.TestCase):
    def test_changed_base_path_or_bytes_rejected_without_child_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            declared=Path(temp)/'base.exe';declared.write_bytes(b'expected')
            different=Path(temp)/'other.exe';different.write_bytes(b'other')
            identity={'path':str(declared.resolve()),'bytes':8,'sha256':p.digest(b'expected')}
            api=types.SimpleNamespace(file_identity=lambda path:dict(identity))
            with mock.patch.object(p,'CLIENT_EXECUTABLE',declared),mock.patch.object(p,'CLIENT_EXECUTABLE_BYTES',8),\
                 mock.patch.object(p,'CLIENT_EXECUTABLE_SHA256',identity['sha256']),mock.patch.object(p,'dependency',return_value=api),\
                 mock.patch.object(p.subprocess,'Popen') as launch:
                with mock.patch.object(p.sys,'_base_executable',str(different)):
                    with self.assertRaises(ValueError):p.client_executable()
                with mock.patch.object(p.sys,'_base_executable',str(declared)):
                    self.assertEqual(p.client_executable(),identity)
                    identity['sha256']='0'*64
                    with self.assertRaises(ValueError):p.client_executable()
                launch.assert_not_called()

    @unittest.skipUnless(os.name=='nt','Declared bounded Windows process identity check')
    def test_declared_base_python_popen_pid_is_actual_python_pid_without_socket_or_namespace(self):
        identity=p.client_executable()
        process=p.subprocess.Popen([identity['path'],'-I','-X','utf8','-B','-c',
            'import os,json; print(json.dumps({"pid":os.getpid()}),flush=True)'],
            stdin=p.subprocess.DEVNULL,stdout=p.subprocess.PIPE,stderr=p.subprocess.PIPE,
            creationflags=getattr(p.subprocess,'CREATE_NO_WINDOW',0))
        try:stdout,stderr=process.communicate(timeout=3)
        except BaseException:
            process.kill();process.communicate(timeout=3);raise
        self.assertEqual(process.returncode,0);self.assertEqual(stderr,b'');self.assertLess(len(stdout),128)
        self.assertEqual(json.loads(stdout),{'pid':process.pid})
        self.assertEqual(identity['sha256'],p.CLIENT_EXECUTABLE_SHA256)


class PendingShutdownTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self,change=None):
        from test_codehost_bridge_v3 import BridgeTests
        t=BridgeTests();await t.asyncSetUp();proofs=[]
        try:
            async def body():
                first=t.client(1);await first[1].received.wait()
                second=t.client(2,natural=True);await second[2]
                third=t.client(3);await third[1].received.wait()
                t.mark_finish(close_uploads=False)
                while not t.bridge.finishing:await asyncio.sleep(0)
                await t.bridge.drain_ack
                if change:change(t)
                try:proof=await p.synchronize_shutdown_read(t.fixture,types.SimpleNamespace(poll=lambda:None),p.time.monotonic()+180)
                except Exception:
                    first[0].feed_eof();third[0].feed_eof();raise
                proof['control_sent_monotonic_s']=p.time.monotonic();proofs.append(proof)
                first[0].feed_data(p.SHUTDOWN_GOAWAY);first[0].feed_eof();third[0].feed_eof()
            if change:
                await t.run_bridge(body,fail=True)
                return t, None,None
            receipt=await t.run_bridge(body)
            client={'pending_read_shutdown':proofs[0],'finish':json.loads((t.folder/'client/events.jsonl').read_text())}
            p.verify_pending_shutdown(client,receipt,t.bridge.ledger.events)
            return copy.deepcopy(client),copy.deepcopy(receipt),copy.deepcopy(t.bridge.ledger.events)
        finally:
            await t.asyncTearDown()
            while t._cleanups:
                fn,args,kwargs=t._cleanups.pop();fn(*args,**kwargs)

    async def test_real_bridge_linux_ack_pending_read_goaway_and_genuine_eof(self):
        client,receipt,rows=await self.exercise()
        self.assertTrue(receipt['qualified']);self.assertEqual(client['pending_read_shutdown']['shutdown_bytes'],17)
        c=next(c for c in receipt['channels'] if c['channel_id']==1)
        self.assertTrue(c['parent_eof']['client_finishing']);self.assertTrue(c['namespace_closed']['download_eof'])
        self.assertEqual(c['meters']['client_read'],c['namespace_closed']['upload'])

    async def test_changed_tail_pending_frontier_prefix_or_grant_cannot_pass_replay(self):
        client,receipt,rows=await self.exercise()
        changes=[lambda c,r,e:c['pending_read_shutdown']['frontier'].update(upload_read_pending=False),
                 lambda c,r,e:c['pending_read_shutdown'].update(shutdown_sha256='0'*64),
                 lambda c,r,e:c['pending_read_shutdown'].update(control_sent_monotonic_s=c['pending_read_shutdown']['deadline_monotonic_s']),
                 lambda c,r,e:c['pending_read_shutdown']['retained_ledger_prefix'].update(sha256='0'*64),
                 lambda c,r,e:next(x for x in e if x['kind']=='frame' and x.get('payload_sha256')==p.digest(p.SHUTDOWN_GOAWAY)).update(payload_sha256='0'*64)]
        for change in changes:
            a,b,c=copy.deepcopy((client,receipt,rows));change(a,b,c)
            with self.assertRaises(ValueError):p.verify_pending_shutdown(a,b,c)

    async def test_fixed_negative_terminal_may_precede_strict_clock_barrier(self):
        from test_codehost_bridge_v3 import BridgeTests,NativeSocket,h2,m
        for corrupt in (None,'qualified','unrelated','closed_pipe'):
            t=BridgeTests();await t.asyncSetUp();proofs=[]
            try:
                t.host_options['reply']=h2(4)+h2(4,1)
                async def body():
                    reader=asyncio.StreamReader();t.client_readers.append(reader)
                    reader.feed_data(m.PREFACE+h2(4)+h2(4,1));writer=NativeSocket(reader,40001)
                    task=asyncio.create_task(t.bridge.handle(reader,writer))
                    await writer.received.wait();reader.feed_data(p.PARTIAL);reader.feed_eof();await task
                    await asyncio.shield(t.bridge.finished)
                    if corrupt=='qualified':t.bridge.finished_metadata['qualified']=True
                    if corrupt=='unrelated':t.bridge.fail('unrelated_failure')
                    if corrupt in ('qualified','unrelated'):
                        with self.assertRaises(ValueError):await p.synchronize_in_flight_eof(t.fixture,types.SimpleNamespace(pid=123,poll=lambda:None),p.time.monotonic()+180)
                    else:proofs.append(await p.synchronize_in_flight_eof(t.fixture,types.SimpleNamespace(pid=123,poll=lambda:None),p.time.monotonic()+180))
                    if corrupt=='closed_pipe':t.process.stdin.close();t.wrapper_exit=1
                receipt=await t.run_bridge(body,fail=True)
                self.assertFalse(receipt['qualified']);self.assertIsNotNone(receipt['retirement'])
                if corrupt=='closed_pipe':
                    self.assertIn('frame_write_BrokenPipeError',receipt['failures'])
                    self.assertEqual(receipt['exit_code'],1);self.assertIn('namespace_wrapper_nonzero',receipt['failures'])
                    close=next(r for r in t.bridge.ledger.events if r['kind']=='owner_input_closed')
                    self.assertFalse(close['after_finish_drain']);self.assertTrue(close['failed_cleanup'])
                if not corrupt:
                    marker=json.loads((t.folder/'client/events.jsonl').read_text())
                    self.assertLess(proofs[0]['eof']['monotonic_s'],marker['monotonic_s'])
            finally:
                await t.asyncTearDown()
                while t._cleanups:
                    fn,args,kwargs=t._cleanups.pop();fn(*args,**kwargs)

    async def test_actual_producer_requires_pending_read_and_original_deadline(self):
        await self.exercise(lambda t:setattr(t.bridge.channels[1],'upload_read_pending',False))
        await self.exercise(lambda t:t.bridge.drain.update(deadline_monotonic_s=p.time.monotonic()-1))


if __name__=='__main__':unittest.main()
