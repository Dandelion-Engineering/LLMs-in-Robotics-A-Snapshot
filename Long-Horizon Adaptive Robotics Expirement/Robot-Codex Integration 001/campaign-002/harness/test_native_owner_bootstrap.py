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


# These exact reviewed byte edits are the prospective epoch provenance change.
# Reversal is pinned on both sides; it cannot hide an unrelated added method.
EPOCH_ARCHIVE = HERE.parents[2] / 'Architecture Map/releases/RCI001-C02-dev-078/code.zip'
EPOCH_ARCHIVE_SHA = 'fa31d9c8f8a0090304774c53d30dfe7631a7547e70e0b84e0ecf2538183629d4'
EPOCH_METHOD = HERE.parent / 'io-repair/EPOCH_REVOCATION_AND_INDEX_SHORTHAND_V1.md'
EPOCH_METHOD_SHA = '1deb7c87a485651167a6777731287f76d3cb8ddbf4b0a9d36f47c58018b1c91c'
EPOCH_RUNTIME_SHA = '80b393d8f539e91bb7c202478372aa212274cc3773307efbc5e5fe3faf378bd5'
PRE_EPOCH_RUNTIME_SHA = 'fac550bdd92e1ee35c98d21029408522c07ac8e956bdda24b8c5d4615c3d473b'
EPOCH_RUNTIME_EDITS = (
    (b'',
     b"MIRROR_RECORD_LIMIT = 16384\nMIRROR_LOG_LIMIT = 16 * 1024 * 1024\nMIRROR_BODY_LIMIT = 4096\n\ndef mirror_bytes(value):\n    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')\n"),
    (b"            phase = 'upstream_request'\n",
     b"            phase = 'request_context'\n            context = reply = None\n"),
    (b'',
     b"                initial = self.files.get('live/state.json', '{}')\n                invocation = json.loads(initial).get('invocation') or {}\n                pinned_id = invocation.get('invocation_id')\n                if (invocation.get('state') != 'active'\n                        or type(invocation.get('authority_epoch')) is not int\n                        or type(self.endpoint.get('authority_epoch')) is not int\n                        or invocation['authority_epoch'] != self.endpoint['authority_epoch']\n                        or not isinstance(pinned_id,str) or not 0 < len(pinned_id) <= 128):\n                    pinned_id = None  # Never manufacture an invocation binding from a response.\n                context = {'schema':'campaign002-mirror-request-1', 'request_id':uuid.uuid4().hex,\n                           'method':'GET', 'path':'/status', 'origin':'protected_host',\n                           'pinned_invocation_id':pinned_id,\n                           'pinned_authority_epoch':self.endpoint.get('authority_epoch'),\n                           'initial_state_sha256':hashlib.sha256(initial.encode()).hexdigest(),\n                           'request_wall_unix_s':time.time()}\n                self._mirror_receipt('mirror-requests.jsonl', context)\n                phase = 'upstream_request'\n"),
    (b'',
     b"                received = time.time()\n                phase = 'reply_context'\n                reply = {**context, 'schema':'campaign002-mirror-reply-1',\n                         'response_wall_unix_s':received, 'status':status}\n                retained = json.loads(self.redact(json.dumps(value, allow_nan=False)))\n                raw = mirror_bytes(retained)\n                reply.update(response_bytes=len(raw), response_sha256=hashlib.sha256(raw).hexdigest(),\n                             response_retained=len(raw) <= MIRROR_BODY_LIMIT,\n                             response=retained if len(raw) <= MIRROR_BODY_LIMIT else None)\n                self._mirror_receipt('mirror-replies.jsonl', reply)\n"),
    (b"                self._observe_revocation('GET', '/status', None, status, value, 'public_mirror')\n",
     b"                self._observe_revocation('GET', '/status', None, status, value, 'public_mirror',\n                                         mirror_context=reply)\n"),
    (b"                           'phase':phase,'authority_revocation_established':revoked}\n",
     b"                           'phase':phase,'authority_revocation_established':revoked,\n                           'mirror_request':context, 'mirror_reply':reply}\n"),
    (b'',
     b'    def _mirror_receipt(self, name, value):\n        """Bounded protected metadata; never a capability-bearing endpoint."""\n        raw = mirror_bytes(value) + b\'\\n\'\n        if len(raw) > MIRROR_RECORD_LIMIT:\n            raise RuntimeError(\'Mirror receipt record limit exceeded\')\n        total = sum((self.evidence / n).stat().st_size for n in\n                    (\'mirror-requests.jsonl\', \'mirror-replies.jsonl\') if (self.evidence / n).exists())\n        if total + len(raw) > MIRROR_LOG_LIMIT:\n            raise RuntimeError(\'Mirror receipt aggregate limit exceeded\')\n        with (self.evidence / name).open(\'ab\') as stream:\n            stream.write(raw); stream.flush(); os.fsync(stream.fileno())\n\n'),
    (b'    def _observe_revocation(self, method, path, payload, status, body, source, trace_id=None):\n',
     b'    def _observe_revocation(self, method, path, payload, status, body, source, trace_id=None,\n                            mirror_context=None):\n'),
    (b'',
     b"        if (source == 'public_mirror' and method == 'GET' and path == '/status'\n                and type(status) is int and status == 409 and body.get('ok') is False\n                and isinstance(error,dict) and error.get('code') == 'stale_authentication'\n                and isinstance(mirror_context,dict)\n                and mirror_context.get('schema') == 'campaign002-mirror-reply-1'\n                and mirror_context.get('response_retained') is True\n                and mirror_context.get('response') == body\n                and type(mirror_context.get('pinned_authority_epoch')) is int\n                and mirror_context['pinned_authority_epoch'] == self.endpoint.get('authority_epoch')\n                and isinstance(mirror_context.get('pinned_invocation_id'),str)\n                and 0 < len(mirror_context['pinned_invocation_id']) <= 128):\n            reason = 'host_epoch_denied'\n"),
    (b"            write_json(self.evidence/'authority-revocation.json',{\n",
     b'            receipt = {\n'),
    (b"                'response':json.loads(self.redact(json.dumps(body)))})\n",
     b"                'response':json.loads(self.redact(json.dumps(body)))}\n            if reason == 'host_epoch_denied':\n                receipt['mirror_context'] = mirror_context\n            write_json(self.evidence/'authority-revocation.json',receipt)\n"),
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
    def remove_epoch_runtime_additions(self, candidate):
        self.assertEqual(hashlib.sha256(EPOCH_METHOD.read_bytes()).hexdigest(), EPOCH_METHOD_SHA)
        process_selection = b'                args.native_process_drain=True\n'
        self.assertEqual(candidate.count(process_selection), 1)
        candidate = candidate.replace(process_selection, b'')
        pre_exit = b'                args.native_exit_barrier=self.native_exit_barrier\n'
        self.assertEqual(candidate.count(pre_exit), 1)
        candidate = candidate.replace(pre_exit, b'')
        self.assertEqual(hashlib.sha256(candidate).hexdigest(), EPOCH_RUNTIME_SHA)
        for before, after in EPOCH_RUNTIME_EDITS:
            self.assertEqual(candidate.count(after), 1)
            candidate = candidate.replace(after, before)
        self.assertEqual(hashlib.sha256(candidate).hexdigest(), PRE_EPOCH_RUNTIME_SHA)
        return candidate

    def test_exact_declared_epoch_reversal_recovers_entire_dev078_runtime(self):
        self.assertEqual(hashlib.sha256(EPOCH_ARCHIVE.read_bytes()).hexdigest(), EPOCH_ARCHIVE_SHA)
        with zipfile.ZipFile(EPOCH_ARCHIVE) as archive:
            original = archive.read((HERE/'runtime.py').relative_to(REPO).as_posix())
        self.assertEqual(self.remove_epoch_runtime_additions((HERE/'runtime.py').read_bytes()), original)

    def test_epoch_reversal_rejects_changed_declared_block_or_unrelated_method(self):
        current = (HERE/'runtime.py').read_bytes()
        mutations = (current.replace(b'MIRROR_BODY_LIMIT = 4096', b'MIRROR_BODY_LIMIT = 8192'),
                     current.replace(b'    def _broker_loop(self):',
                         b'    def unexpected_method(self): return None\n\n    def _broker_loop(self):'))
        for candidate in mutations:
            with self.subTest(sha256=hashlib.sha256(candidate).hexdigest()):
                self.assertNotEqual(candidate, current)
                with self.assertRaises(AssertionError):
                    self.remove_epoch_runtime_additions(candidate)

    def remove_unload_additions(self,candidate):
        process_close = '''        selected = getattr(self.args, "native_process_drain", False)
        require(type(selected) is bool, "Native process-drain selection must be boolean")
        if selected:
            from native_process_quiescence import close
        else:
            from native_quiescence import close
'''
        self.assertEqual(candidate.count(process_close),1)
        candidate=candidate.replace(process_close,'        from native_quiescence import close\n')
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
            runtime=self.remove_epoch_runtime_additions((HERE/'runtime.py').read_bytes())
            addition=b'                args.native_cleanup_barrier=self.native_cleanup_barrier\n'
            self.assertEqual(runtime.count(addition),1)
            self.assertEqual(runtime.replace(addition,b''),archive.read((HERE/'runtime.py').relative_to(REPO).as_posix()))
            candidate=(HERE/'native_quiescence.py').read_text()
            from test_native_shutdown_order import strip_instrumentation
            candidate=strip_instrumentation(candidate)
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
            current=self.remove_epoch_runtime_additions((HERE/'runtime.py').read_bytes())
            for before,after in RUNTIME_EDITS:
                self.assertEqual(current.count(after),1); current=current.replace(after,before)
            self.assertEqual(current,archive.read((HERE/'runtime.py').relative_to(REPO).as_posix()))

    def test_client_and_unrelated_runtime_methods_are_identical(self):
        with zipfile.ZipFile(ARCHIVE) as archive:
            for name,oldfile,newfile,changed in [('Runtime','runtime.py','runtime.py',{'argv','model'})]:
                old=ast.parse(archive.read((HERE/oldfile).relative_to(REPO).as_posix()))
                new=ast.parse(self.remove_epoch_runtime_additions((HERE/newfile).read_bytes()))
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
            runtime=self.remove_epoch_runtime_additions((HERE/'runtime.py').read_bytes())
            addition=b'                args.native_cleanup_barrier=self.native_cleanup_barrier\n'
            self.assertEqual(runtime.count(addition),1)
            self.assertEqual(runtime.replace(addition,b''),archive.read((HERE/'runtime.py').relative_to(REPO).as_posix()))


if __name__=='__main__': unittest.main()
