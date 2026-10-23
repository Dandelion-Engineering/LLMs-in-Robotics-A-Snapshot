import hashlib
import ast
import json
from pathlib import Path
import unittest
import threading
from types import SimpleNamespace
import subprocess

from transport_stderr import metadata, MARKERS, announce_finishing

HERE = Path(__file__).resolve().parent


class StderrMetadataTests(unittest.TestCase):
    def test_dynamic_secret_text_is_never_retained(self):
        secret = 'synthetic-private-config-value-729193'
        raw = ('ERROR: code_mode_host transport disconnected token=' + secret).encode()
        row = metadata(raw)
        self.assertNotIn(secret, json.dumps(row))
        self.assertNotIn('token=', json.dumps(row))
        self.assertFalse(row['text_retained'])
        self.assertEqual(row['bytes'], len(raw))
        self.assertEqual(row['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(set(row['markers']), {'error_level', 'code_mode_host', 'transport', 'disconnected'})

    def test_unknown_and_binary_content_stays_opaque(self):
        for raw in [b'', b'\xff\xfe\x00', b'credential=synthetic-secret']:
            with self.subTest(raw=raw):
                self.assertEqual(metadata(raw)['markers'], [])

    def test_only_fixed_enums_are_emitted(self):
        raw = b' grpc unavailable connection reset broken pipe timeout exec-server '
        row = metadata(raw)
        self.assertTrue(set(row['markers']).issubset(MARKERS))
        self.assertGreater(row['wall_unix_s'], 0)
        self.assertGreater(row['monotonic_s'], 0)

    def test_reject_nonbytes_without_conversion(self):
        with self.assertRaises(TypeError):
            metadata('not actual bytes')

    def test_bootstrap_diff_is_only_diagnostic_receipts(self):
        original = (HERE.parents[1] / 'readiness-session-10/orchestrator/bootstrap_client.py').read_text(encoding='utf-8')
        candidate = (HERE / 'bootstrap_client_v2.py').read_text(encoding='utf-8')
        before = ('                # Do not persist ambient diagnostics: they can contain config values.\n'
                  '                self.log({"kind": "stderr", "bytes": len(data)})')
        after = ('                # Fixed markers and hashes only: ambient text may contain config values.\n'
                 '                from transport_stderr import metadata\n'
                 '                self.log(metadata(data))')
        self.assertEqual(original.count(before), 1)
        old_close = ("        finishing = getattr(self.args, 'client_finishing', None)\n"
                     "        if finishing is not None:\n"
                     "            finishing.set()")
        new_close = ("        from transport_stderr import announce_finishing\n"
                     "        finishing_recorded = announce_finishing(self)")
        self.assertEqual(original.count(old_close), 1)
        expected = original.replace(before, after).replace(old_close, new_close).replace(
            '        self.events.close()\n', '        self.events.close()\n'
            "        require(finishing_recorded, 'Client finishing receipt could not be retained')\n")
        self.assertEqual(candidate, expected)

    def test_finishing_intent_precedes_flag_and_failure_leaves_flag_unset(self):
        flags = SimpleNamespace(client_finishing=threading.Event(), abort_event=threading.Event())
        records = []
        def log(row):
            self.assertFalse(flags.client_finishing.is_set())
            records.append(row)
        client = SimpleNamespace(args=flags, log=log)
        self.assertTrue(announce_finishing(client))
        self.assertTrue(flags.client_finishing.is_set())
        self.assertEqual(records[0]['kind'], 'client_finishing_before_close')
        flags.client_finishing.clear()
        def broken(row):
            raise OSError('synthetic disk failure')
        client.log = broken
        self.assertFalse(announce_finishing(client))
        self.assertFalse(flags.client_finishing.is_set())
        self.assertTrue(flags.abort_event.is_set())

    def test_failed_finishing_receipt_still_retires_app_process(self):
        tree = ast.parse((HERE / 'bootstrap_client_v2.py').read_text(encoding='utf-8'))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Client')
        close = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == 'close')
        def require(ok, message):
            if not ok:
                raise RuntimeError(message)
        namespace = {'subprocess': subprocess, 'require': require}
        exec(compile(ast.Module(body=[close], type_ignores=[]), '<actual-close-method>', 'exec'), namespace)
        events = []
        args = SimpleNamespace(client_finishing=threading.Event(), abort_event=threading.Event())
        def log(row):
            if row['kind'] == 'client_finishing_before_close':
                raise OSError('synthetic retention failure')
            events.append('shutdown-record')
        process = SimpleNamespace(stdin=SimpleNamespace(close=lambda: events.append('stdin-closed')),
                                  wait=lambda **kw: events.append('waited'), returncode=0)
        client = SimpleNamespace(args=args, log=log, process=process,
                                 job=SimpleNamespace(close=lambda: events.append('job-closed')),
                                 events=SimpleNamespace(close=lambda: events.append('events-closed')))
        with self.assertRaisesRegex(RuntimeError, 'could not be retained'):
            namespace['close'](client)
        self.assertEqual(events, ['stdin-closed','waited','job-closed','shutdown-record','events-closed'])
        self.assertFalse(args.client_finishing.is_set())
        self.assertTrue(args.abort_event.is_set())


if __name__ == '__main__':
    unittest.main()
