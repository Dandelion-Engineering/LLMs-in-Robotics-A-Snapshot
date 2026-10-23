"""Deterministic protocol tests only. No native process, WSL, model or simulation."""
import asyncio
import base64
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('output_delivery_probe_tests_subject', Path(__file__).with_name('probe.py'))
P = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(P)


def fixture():
    app, wire, native, delivered = [], [], [], set()
    nseq = 0
    def retained(kind, msg, stamp):
        nonlocal nseq
        nseq += 1
        row = {'kind':kind,'sequence':nseq,'wall_unix_s':stamp,'message':msg,
               'original_message_sha256':P.sha(P.canonical(msg)),
               'retained_message_sha256':P.sha(P.canonical(msg)), 'blobs':[]}
        native.append(row)
        if kind == 'response': delivered.add(nseq)
        return row
    def original(msg):
        raw = json.dumps(msg).encode()+b'\n'
        wire.append({'base64':base64.b64encode(raw).decode(),'sha256':P.sha(raw),'bytes':len(raw)})
    for ordinal, case in enumerate(P.make_cases(),1):
        start = ordinal*10.0
        app.append({'kind':'request','method':'command/exec','id':ordinal,
                    'params':P.command_params(case),'probe_wall_unix_s':start})
        pid='native-'+str(ordinal)
        retained('request',{'id':100+ordinal,'method':'process/start',
                            'params':{'processId':pid,'argv':case['argv'],'cwd':'file:///workspace','tty':False}},start+.1)
        retained('response',{'id':100+ordinal,'result':{'processId':pid,'sandboxType':'none'}},start+.2)
        # Legal exited-before-output ordering is the original observation's shape.
        seq=1
        retained('response',{'method':'process/exited','params':{'processId':pid,'seq':seq,'exitCode':0,'sandboxDenied':False}},start+.3)
        for stream in ('stdout','stderr'):
            raw=base64.b64decode(case[stream]['base64'])
            chunks=[raw[:8192],raw[8192:]] if raw else []
            for chunk in filter(None,chunks):
                seq+=1
                retained('response',{'method':'process/output','params':{'processId':pid,'seq':seq,'stream':stream,'chunk':base64.b64encode(chunk).decode()}},start+.4)
                if case['streaming']:
                    msg={'method':'command/exec/outputDelta','params':{'processId':case['process_id'],'stream':stream,'deltaBase64':base64.b64encode(chunk).decode(),'capReached':False}}
                    original(msg);app.append({'kind':'notification',**msg,'probe_wall_unix_s':start+.5})
        seq+=1
        retained('response',{'method':'process/closed','params':{'processId':pid,'seq':seq}},start+.6)
        msg={'id':ordinal,'result':{'exitCode':0,**{s:'' if case['streaming'] else base64.b64decode(case[s]['base64']).decode() for s in ('stdout','stderr')}}}
        original(msg);app.append({'kind':'response','method':'command/exec',**msg,'probe_wall_unix_s':start+1})
    return app,wire,[(native,delivered)]


def rewrite_wire(app):
    wire=[]
    for r in app:
        if r.get('kind')=='response' and r.get('method')=='command/exec':
            msg={k:v for k,v in r.items() if k not in ('kind','method','probe_wall_unix_s')}
        elif r.get('kind')=='notification' and r.get('method')=='command/exec/outputDelta':
            msg={k:v for k,v in r.items() if k not in ('kind','probe_wall_unix_s')}
        else:continue
        raw=json.dumps(msg).encode()+b'\n';wire.append({'base64':base64.b64encode(raw).decode(),'bytes':len(raw),'sha256':P.sha(raw)})
    return wire


class ProtocolTests(unittest.TestCase):
    def test_fixed_six_case_plan_and_bounds(self):
        cases=P.make_cases();self.assertEqual(tuple(c['name'] for c in cases),P.NAMES)
        self.assertEqual(sum(c[s]['bytes'] for c in cases for s in ('stdout','stderr')),65402)
        for case in cases:
            self.assertEqual(case['argv'][:4],['/usr/bin/python3','-I','-B','-c'])
            self.assertEqual(P.command_params(case)['outputBytesCap'],65536)
            self.assertEqual(P.command_params(case)['timeoutMs'],10000)
            tree=__import__('ast').parse(case['argv'][4])
            self.assertFalse(any(isinstance(n,(__import__('ast').FunctionDef,__import__('ast').ClassDef)) for n in __import__('ast').walk(tree)))
            self.assertEqual('time.sleep(0.1)' in case['argv'][4],case['name'].startswith('separated'))
    def test_complete_distinct_ids_and_exited_before_output(self):
        value=P.assess_records(*fixture());self.assertTrue(value['passed']);self.assertEqual(len(value['cases']),6)
        self.assertNotEqual(value['cases'][0]['native_process_id'],value['cases'][0]['app_process_id'])
    def test_wrong_route(self):
        a,w,c=fixture();c[0][0][0]['message']['params']['argv']=['local-fallback']
        with self.assertRaisesRegex(ValueError,'remote route'):P.assess_records(a,w,c)
    def test_missing_first_public_chunk_is_observed_gap(self):
        a,w,c=fixture();a.pop(1);w=rewrite_wire(a);v=P.assess_records(a,w,c)
        self.assertFalse(v['passed']);self.assertTrue(v['protocol_passed']);self.assertEqual(v['cases'][0]['streams']['stdout']['public']['bytes'],4837)
    def test_duplicate_public_delta_is_gap_not_deduplicated(self):
        a,w,c=fixture();a.insert(2,copy.deepcopy(a[1]));w=rewrite_wire(a)
        self.assertFalse(P.assess_records(a,w,c)['passed'])
    def test_duplicate_native_sequence(self):
        a,w,c=fixture();messages=[r for r in c[0][0] if r['message'].get('method')=='process/output'];messages[0]['message']['params']['seq']=1
        with self.assertRaisesRegex(ValueError,'sequence'):P.assess_records(a,w,c)
    def test_stdout_stderr_confusion(self):
        a,w,c=fixture();a[1]['params']['stream']='stderr';w=rewrite_wire(a)
        self.assertFalse(P.assess_records(a,w,c)['passed'])
    def test_false_public_exit_rejected(self):
        a,w,c=fixture();next(r for r in a if r['kind']=='response')['result']['exitCode']=False
        with self.assertRaisesRegex(ValueError,'public exit'):P.assess_records(a,rewrite_wire(a),c)
    def test_false_native_exit_rejected(self):
        a,w,c=fixture();next(r for r in c[0][0] if r['message'].get('method')=='process/exited')['message']['params']['exitCode']=False
        with self.assertRaisesRegex(ValueError,'Native exit'):P.assess_records(a,w,c)
    def test_cap_reached(self):
        a,w,c=fixture();a[1]['params']['capReached']=True
        with self.assertRaisesRegex(ValueError,'cap'):P.assess_records(a,rewrite_wire(a),c)
    def test_model_method(self):
        for method in ('thread/start','turn/start','mcpServer/tool/call'):
            a,w,c=fixture();a.insert(0,{'kind':'request','method':method})
            with self.subTest(method=method),self.assertRaisesRegex(ValueError,'model/tool'):P.assess_records(a,w,c)
    def test_missing_delivery(self):
        a,w,c=fixture();c[0][1].remove(next(r['sequence'] for r in c[0][0] if r['message'].get('method')=='process/output'))
        with self.assertRaisesRegex(ValueError,'Undelivered'):P.assess_records(a,w,c)
    def test_native_close_missing(self):
        a,w,c=fixture();rows=c[0][0];rows.remove(next(r for r in rows if r['message'].get('method')=='process/closed'))
        with self.assertRaisesRegex(ValueError,'lifecycle'):P.assess_records(a,w,c)
    def test_extra_start_and_reconnection(self):
        a,w,c=fixture();c[0][0].append(copy.deepcopy(c[0][0][0]))
        with self.assertRaisesRegex(ValueError,'process/start'):P.assess_records(a,w,c)
        a,w,c=fixture()
        with self.assertRaisesRegex(ValueError,'reconnected'):P.assess_records(a,w,c+c)
    def test_original_wire_not_reconstructed(self):
        a,w,c=fixture();w[0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'wire binding'):P.assess_records(a,w,c)
    def test_source_drift_before_runtime_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'one.py').write_text('changed')
            manifest={'schema':P.MANIFEST_SCHEMA,'run_id':'fixed','framework_revision':'dev',
                'cases':P.make_cases(),'model_calls':0,'model_turns_max':0,'physical_simulation':False,'recovery_actions':False,
                'runtime_input_files':['one.py'],'input_bindings':{'one.py':{'sha256':'0'*64,'bytes':1}}}
            mp=root/'manifest.json';mp.write_text(json.dumps(manifest));sp=root/'snapshot.json';sp.write_text(json.dumps({'run_id':'fixed','manifest_sha256':P.sha(mp.read_bytes())}))
            with patch.object(P,'REPO',root),patch.object(P,'required_inputs',return_value=['one.py']),patch.object(P,'load_module') as imp:
                with self.assertRaisesRegex(ValueError,'Source drift'):P.validate_sources(sp,mp)
                imp.assert_not_called()
    def test_unsupported_route_blocks_before_source_or_output(self):
        with patch.object(P,'validate_sources') as source,patch.object(P,'execute_runtime') as execute:
            with self.assertRaisesRegex(RuntimeError,'Unsupported remote route'):P.run(types.SimpleNamespace())
            source.assert_not_called();execute.assert_not_called()
    def test_whole_deadline(self):
        with patch.object(P.time,'monotonic',side_effect=[0,121]):
            deadline=P.Deadline()
            with self.assertRaisesRegex(ValueError,'deadline'):deadline.remaining()


class CleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_partial_runtime_constructor_closed_off_event_loop(self):
        parent_thread=threading.get_ident();seen=[]
        class Partial:
            def __init__(self,*args):
                seen.append(('init',threading.get_ident()));self.abort_event=threading.Event();raise RuntimeError('partial constructor')
            def close(self):seen.append(('close',threading.get_ident()));return True
        module=types.SimpleNamespace(Runtime=Partial,linux=lambda *a,**k:None,template=lambda kind:{})
        original=module.linux
        with tempfile.TemporaryDirectory() as tmp:
            value=await P.execute_runtime(Path(tmp),P.Deadline(),module)
        self.assertFalse(value['execution_completed']);self.assertTrue(value['cleanup_clean']);self.assertIn('partial constructor',value['errors'][0])
        self.assertEqual([x[0] for x in seen],['init','close']);self.assertTrue(all(t!=parent_thread for _,t in seen));self.assertIs(module.linux,original)
    async def test_cleanup_failure_cannot_pass(self):
        class Partial:
            def __init__(self,*args):self.abort_event=threading.Event();raise RuntimeError('constructor')
            def close(self):raise RuntimeError('cleanup')
        module=types.SimpleNamespace(Runtime=Partial,linux=lambda *a,**k:None,template=lambda kind:{})
        with tempfile.TemporaryDirectory() as tmp:value=await P.execute_runtime(Path(tmp),P.Deadline(),module)
        self.assertFalse(value['cleanup_clean']);self.assertFalse(value['execution_completed']);self.assertEqual(len(value['errors']),2)


if __name__=='__main__':unittest.main()
