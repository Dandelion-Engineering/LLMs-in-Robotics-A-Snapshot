"""No native launch: owner ordering/failure closure and exact dev041 parity."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from test_raw_event_capture import load, HERE, REPO

V4 = load('native_owner_candidate_v4', HERE / 'bootstrap_client_v4.py')
ARCHIVE = HERE.parents[2] / 'Architecture Map/releases/RCI001-C02-dev-041/code.zip'
ARCHIVE_SHA = '1b05d7dc1ac46973c64e0a45f34d933a179c99b813a2058eadfd2824f9a99727'
QUIESCENCE_ARCHIVE = HERE.parents[2] / 'Architecture Map/releases/RCI001-C02-dev-055/code.zip'
QUIESCENCE_ARCHIVE_SHA = '9194f639d5749c1f6e2f12202580c328f5f91b109795a7af72616b8029bdaac0'
UNLOAD_ARCHIVE = HERE.parents[2] / 'Architecture Map/releases/RCI001-C02-dev-056/code.zip'
UNLOAD_ARCHIVE_SHA = 'b57d84a41dc62d280728f05cd4fbc23a1090093c95f4d31769caa07a597becd9'
UNLOAD_ADDITIONS = (
    '        "thread_unload_delay_secs": 0,\n',
    '    require(type(config.get("thread_unload_delay_secs")) is int and config["thread_unload_delay_secs"] == 0,\n'
    '            "Native idle thread unload scheduling differs")\n',
    '            "thread_unload_delay_secs": 0,\n',
)
CALLBACK_BLOCK = b'''        if code_mode_host_url:
            owner_callback = getattr(args, "native_process_ready", None)
            require(callable(owner_callback), "Authenticated native process owner callback is required")
            owner_binding = owner_callback(client.process, LAUNCH.CODEX)
            require(isinstance(owner_binding, dict), "Native owner callback did not return a receipt")
            owner_path = args.evidence / "native-owner.json"
            LAUNCH.write_json(owner_path, owner_binding)
            client.log({"kind": "native_process_owner_registered",
                        "receipt_sha256": LAUNCH.sha256(owner_path),
                        "receipt_bytes": owner_path.stat().st_size})
'''
RUNTIME_EDITS = (
    (b"bootstrap = load('campaign002_bootstrap_v3', HERE / 'bootstrap_client_v3.py')",
     b"bootstrap = load('campaign002_bootstrap_v4', HERE / 'bootstrap_client_v4.py')"),
    (b"with_codehost = load('campaign002_codehost_bridge_v2', HERE / 'codehost_bridge_v2.py').run",
     b"with_codehost = load('campaign002_codehost_bridge_v3', HERE / 'codehost_bridge_v3.py').run"),
    (b"entry = HERE / 'codehost_entry_v2.py'", b"entry = HERE / 'codehost_entry_v3.py'"),
    (b'                args.code_mode_host_url=host_url\n',
     b'                args.code_mode_host_url=host_url\n                args.native_process_ready=self.native_process_ready\n'
     b'                args.native_cleanup_barrier=self.native_cleanup_barrier\n'),
)


class NativeOwnerBootstrapTests(unittest.TestCase):
    def exercise(self, *, callback=True, failure=None, invalid=False, write_failure=False, model=False,
                 cleanup_failure=False, cleanup_exception=False, unload_delay=0):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        host, home = root/'host', root/'home'
        host.mkdir(); home.mkdir()
        args = SimpleNamespace(host_cwd=host, codex_home=home, timeout=90,
            evidence=root/'client', exec_server_url='ws://127.0.0.1:1234/synthetic',
            code_mode_host_url='http://127.0.0.1:2345', remote_cwd='file:///workspace',
            run_bootstrap=model)
        events, calls, receipts = [], [], {}
        process = object()
        binding = {'schema': 'synthetic-owner', 'pid': 123, 'creation': 'synthetic'}
        def register(actual, binary):
            self.assertIs(actual, process)
            self.assertEqual(binary, Path('synthetic-native.exe'))
            events.append('registered')
            if failure: raise RuntimeError(failure)
            return None if invalid else binding
        if callback: args.native_process_ready = register
        config = {'features': {name: False for name in V4.DISABLED},
                  'model_provider': 'openai', 'web_search': 'disabled', 'project_doc_max_bytes': 0}
        config['features']['code_mode_host'] = True
        if unload_delay != 'absent': config['thread_unload_delay_secs'] = unload_delay
        class Native:
            def call(self, method, params, *, private=False):
                calls.append((method, copy.deepcopy(params), private)); events.append(method)
                if method == 'config/read': return {'config': config}
                if method == 'account/read': return {'account': {'type': 'chatgpt'}}
                if method == 'environment/status': return {'status': 'unknown' if params['environmentId']=='local' else 'ready'}
                if method == 'environment/info': return {'shell': {'path': '/usr/bin/bash'}, 'cwd': 'file:///workspace'}
                if method == 'thread/start': return {'model': V4.LAUNCH.MODEL, 'modelProvider': 'openai',
                    'reasoningEffort': V4.LAUNCH.EFFORT, 'instructionSources': [], 'thread': {'id': 'synthetic-thread'}}
                if method == 'mcpServerStatus/list': return {'data': []}
                if method == 'turn/start': return {'turn': {'id': 'synthetic-turn'}}
                return {}
            def send(self, value): events.append('send')
            def log(self, value):
                events.append(value['kind'])
                if value['kind']=='native_process_owner_registered':
                    raw=(args.evidence/'native-owner.json').read_bytes()
                    self_outer.assertEqual(value['receipt_sha256'], hashlib.sha256(raw).hexdigest())
                    self_outer.assertEqual(value['receipt_bytes'], len(raw))
            def wait_turn(self, identity): return {'id': identity, 'status': 'completed'}
            def close(self):
                events.append('closed')
                if cleanup_exception: raise RuntimeError('private cleanup exception')
                return {'qualified':not cleanup_failure,'failures':['synthetic_failure'] if cleanup_failure else []}
        self_outer=self
        native=Native(); native.process=process
        def write(path, value):
            if write_failure and path.name=='native-owner.json': raise OSError('synthetic receipt failure')
            path.write_text(json.dumps(value), encoding='utf-8')
            receipts[path.name]=copy.deepcopy(value); events.append('write:'+path.name)
        fake=SimpleNamespace(MODEL=V4.LAUNCH.MODEL, EFFORT=V4.LAUNCH.EFFORT,
            CODEX=Path('synthetic-native.exe'), utc=lambda:'synthetic-time',
            sha256=lambda path: hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else '0'*64,
            config_args=lambda config:[], clean_environment=lambda path:{}, write_json=write)
        with patch.object(V4,'LAUNCH',fake),patch.object(V4,'Client',return_value=native):
            result=V4.run(args)
        return result, events, calls, receipts

    def test_registration_and_durable_receipt_precede_first_rpc(self):
        result, events, calls, receipts=self.exercise()
        self.assertTrue(result['success']); self.assertFalse(result['model_started'])
        self.assertLess(events.index('registered'), events.index('write:native-owner.json'))
        self.assertLess(events.index('write:native-owner.json'), events.index('native_process_owner_registered'))
        self.assertLess(events.index('native_process_owner_registered'), events.index('initialize'))
        self.assertEqual(sum(method=='thread/start' for method,_,_ in calls),1)
        self.assertFalse(any(method=='turn/start' for method,_,_ in calls))
        self.assertTrue(receipts['preflight.json']['experimental_raw_events_thread_start_accepted'])

    def test_missing_callback_fails_before_initialize_and_closes_client(self):
        result,events,calls,_=self.exercise(callback=False)
        self.assertFalse(result['success']); self.assertFalse(result['model_started'])
        self.assertEqual(calls,[]); self.assertIn('closed',events)

    def test_registration_rejection_fails_before_any_rpc(self):
        result,events,calls,receipts=self.exercise(failure='synthetic owner rejected')
        self.assertFalse(result['success']); self.assertFalse(result['model_started'])
        self.assertIn('owner rejected',result['error']); self.assertEqual(calls,[])
        self.assertNotIn('native-owner.json',receipts); self.assertIn('closed',events)

    def test_invalid_callback_receipt_fails_before_any_rpc(self):
        result,events,calls,_=self.exercise(invalid=True)
        self.assertFalse(result['success']); self.assertEqual(calls,[]); self.assertIn('closed',events)

    def test_failed_durable_receipt_prevents_initialize(self):
        result,events,calls,_=self.exercise(write_failure=True)
        self.assertFalse(result['success']); self.assertEqual(calls,[])
        self.assertNotIn('native_process_owner_registered',events); self.assertIn('closed',events)

    def test_exact_bootstrap_and_raw_option_survive_owner_plumbing(self):
        result,_,calls,_=self.exercise(model=True)
        self.assertTrue(result['success']); self.assertTrue(result['model_started'])
        turns=[p for m,p,_ in calls if m=='turn/start']; self.assertEqual(len(turns),1)
        self.assertEqual(turns[0]['input'],[{'type':'text','text':V4.BOOTSTRAP,'text_elements':[]}])
        self.assertIs(next(p for m,p,_ in calls if m=='thread/start')['experimentalRawEvents'],True)

    def test_cleanup_failure_retains_result_and_never_overwrites_prior_failure(self):
        for exception in (False,True):
            result,events,_,receipts=self.exercise(failure='original invocation failure',
                cleanup_failure=True,cleanup_exception=exception)
            self.assertFalse(result['success']);self.assertEqual(result['error'],'original invocation failure')
            self.assertIs(result['native_quiescence']['qualified'],False)
            self.assertEqual(receipts['result.json'],result)
            self.assertNotIn('private cleanup exception',json.dumps(result))

    def test_cleanup_failure_demotes_otherwise_successful_result(self):
        result,_,_,receipts=self.exercise(cleanup_failure=True)
        self.assertFalse(result['success']);self.assertEqual(result['error'],'Native cleanup did not qualify')
        self.assertEqual(receipts['result.json'],result)

    def test_exact_zero_unload_setting_is_requested_and_verified_before_thread(self):
        result,_,calls,receipts=self.exercise()
        self.assertTrue(result['success'])
        self.assertLess([m for m,_,_ in calls].index('config/read'),[m for m,_,_ in calls].index('thread/start'))
        self.assertEqual([m for m,_,_ in calls if m.startswith('config/')],['config/read'])
        for value in (receipts['launch.json']['config_overrides'],result['effective_config'],
                      receipts['preflight.json']['effective_config']):
            self.assertIs(type(value['thread_unload_delay_secs']),int)
            self.assertEqual(value['thread_unload_delay_secs'],0)

    def test_unload_setting_missing_or_not_exact_integer_zero_stops_before_thread(self):
        for value in ('absent',None,False,True,0.0,'0',-1,1,60):
            with self.subTest(value=value):
                result,events,calls,receipts=self.exercise(unload_delay=value,model=True)
                self.assertFalse(result['success']);self.assertFalse(result['model_started'])
                self.assertEqual([m for m,_,_ in calls],['initialize','config/read'])
                self.assertEqual(result['error'],'Native idle thread unload scheduling differs')
                self.assertIn('closed',events);self.assertEqual(receipts['result.json'],result)


class NativeOwnerParityTests(unittest.TestCase):
    def remove_unload_additions(self,candidate):
        for addition in UNLOAD_ADDITIONS:
            # Match whole lines so differing indentation cannot hide an extra key.
            needle='\n'+addition
            self.assertEqual(candidate.count(needle),1)
            candidate=candidate.replace(needle,'\n')
        return candidate

    def test_only_exact_unload_scheduling_and_receipt_additions_differ_from_dev056(self):
        self.assertEqual(hashlib.sha256(UNLOAD_ARCHIVE.read_bytes()).hexdigest(),UNLOAD_ARCHIVE_SHA)
        with zipfile.ZipFile(UNLOAD_ARCHIVE) as archive:
            original=archive.read((HERE/'bootstrap_client_v4.py').relative_to(REPO).as_posix()).decode().replace('\r\n','\n')
            self.assertEqual(self.remove_unload_additions((HERE/'bootstrap_client_v4.py').read_text()),original)
            runtime=(HERE/'runtime.py').read_bytes()
            addition=b'                args.native_cleanup_barrier=self.native_cleanup_barrier\n'
            self.assertEqual(runtime.count(addition),1)
            self.assertEqual(runtime.replace(addition,b''),archive.read((HERE/'runtime.py').relative_to(REPO).as_posix()))
            candidate=(HERE/'native_quiescence.py').read_text()
            changes=(('import uuid\n\nimport native_cleanup_protocol as cleanup_protocol\n',''),
                ("'schema': 'campaign002-native-quiescence-2'", "'schema': 'campaign002-native-quiescence-1'"),
                ("'controls': [], 'cleanup_barrier': None,", "'controls': [],"),
                ('        self.cleanup_barrier(event)\n',''))
            for after,before in changes:
                self.assertEqual(candidate.count(after),1); candidate=candidate.replace(after,before)
            begin=candidate.index('    def cleanup_barrier(self, event):\n')
            end=candidate.index('    def control(self, method):\n',begin)
            candidate=candidate[:begin]+candidate[end:]
            self.assertEqual(candidate,archive.read((HERE/'native_quiescence.py').relative_to(REPO).as_posix()).decode().replace('\r\n','\n'))

    def test_exact_mechanical_reversal_recovers_archived_dev041(self):
        self.assertEqual(hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),ARCHIVE_SHA)
        with zipfile.ZipFile(ARCHIVE) as archive:
            original=archive.read((HERE/'bootstrap_client_v3.py').relative_to(REPO).as_posix())
            self.assertEqual(original,(HERE/'bootstrap_client_v3.py').read_bytes())
            with zipfile.ZipFile(QUIESCENCE_ARCHIVE) as frozen:
                candidate=frozen.read((HERE/'bootstrap_client_v4.py').relative_to(REPO).as_posix())
            self.assertEqual(candidate.count(CALLBACK_BLOCK),1)
            self.assertEqual(candidate.replace(CALLBACK_BLOCK,b''),original)
            current=(HERE/'runtime.py').read_bytes()
            for before,after in RUNTIME_EDITS:
                self.assertEqual(current.count(after),1); current=current.replace(after,before)
            self.assertEqual(current,archive.read((HERE/'runtime.py').relative_to(REPO).as_posix()))

    def test_client_and_unrelated_runtime_methods_are_identical(self):
        with zipfile.ZipFile(ARCHIVE) as archive:
            for name,oldfile,newfile,changed in [('Runtime','runtime.py','runtime.py',{'argv','model'})]:
                old=ast.parse(archive.read((HERE/oldfile).relative_to(REPO).as_posix()))
                new=ast.parse((HERE/newfile).read_bytes())
                def methods(tree):
                    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==name)
                    return {n.name:ast.dump(n,include_attributes=False) for n in cls.body
                            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
                baseline,candidate=methods(old),methods(new)
                self.assertEqual(set(baseline),set(candidate))
                for method in baseline:
                    if method not in changed: self.assertEqual(baseline[method],candidate[method],method)

    def test_only_exact_declared_lifecycle_edits_differ_from_archived_dev055(self):
        self.assertEqual(hashlib.sha256(QUIESCENCE_ARCHIVE.read_bytes()).hexdigest(),QUIESCENCE_ARCHIVE_SHA)
        with zipfile.ZipFile(QUIESCENCE_ARCHIVE) as archive:
            original=archive.read((HERE/'bootstrap_client_v4.py').relative_to(REPO).as_posix()).decode().replace('\r\n','\n')
            candidate=self.remove_unload_additions((HERE/'bootstrap_client_v4.py').read_text())
            additions=[
                '        self.thread_id = self.turn_id = self.turn_terminal_status = None\n'
                '        self.thread_start_requested = self.turn_start_requested = False\n'
                '        self.cleanup_started = False\n        self.cleanup_result = None\n',
                "        require(not self.cleanup_started, 'Normal native control is closed')\n",
                "        if method == 'thread/start': self.thread_start_requested = True\n"
                "        if method == 'turn/start': self.turn_start_requested = True\n",
                '            from native_quiescence import remember_response\n'
                '            remember_response(self, method, msg["result"])\n',
                '                    from native_quiescence import remember_terminal\n'
                '                    remember_terminal(self, event)\n']
            for i,addition in enumerate(additions):
                self.assertEqual(candidate.count(addition),3 if i==1 else 1)
                candidate=candidate.replace(addition,'')
            start='    def close(self):\n';end='\n\ndef inspect_config'
            old_close=original[original.index(start):original.index(end)]
            new_close=candidate[candidate.index(start):candidate.index(end)]
            self.assertEqual(new_close,'    def close(self):\n        from native_quiescence import close\n        return close(self, MAX_BYTES)\n')
            candidate=candidate.replace(new_close,old_close)
            new_finally='''            try:
                cleanup = client.close()
                result['native_quiescence'] = cleanup
                if not isinstance(cleanup, dict) or cleanup.get('qualified') is not True:
                    result['success'] = False
                    result.setdefault('error', 'Native cleanup did not qualify')
            except BaseException:
                result['success'] = False
                result['native_quiescence'] = {'qualified': False, 'failures': ['cleanup_internal_error']}
                result.setdefault('error', 'Native cleanup did not qualify')
'''
            self.assertEqual(candidate.count(new_finally),1)
            candidate=candidate.replace(new_finally,'            client.close()\n')
            self.assertEqual(candidate,original)
            runtime=(HERE/'runtime.py').read_bytes()
            addition=b'                args.native_cleanup_barrier=self.native_cleanup_barrier\n'
            self.assertEqual(runtime.count(addition),1)
            self.assertEqual(runtime.replace(addition,b''),archive.read((HERE/'runtime.py').relative_to(REPO).as_posix()))


if __name__=='__main__': unittest.main()
