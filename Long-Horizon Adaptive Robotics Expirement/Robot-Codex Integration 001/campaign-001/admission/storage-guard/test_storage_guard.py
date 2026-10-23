"""Bounded non-model counterexamples; no scientific run or user credentials."""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
import subprocess
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import storage_guard as guard


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='storage-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def scan(self, roots=None):
        return guard.scan(roots or [{'path': str(self.root), 'required': True}], [self.root.anchor])

    def test_hardlinks_and_nested_roots_are_not_double_counted(self):
        (self.root / 'one').write_bytes(b'x' * 4096)
        nested = self.root / 'nested'
        nested.mkdir()
        os.link(self.root / 'one', nested / 'two')
        actual = self.scan([{'path': str(self.root)}, {'path': str(nested)}])
        self.assertEqual(actual['pathname_bytes'], 8192)
        self.assertEqual(actual['distinct_bytes'], 4096)
        self.assertEqual(actual['identity_count'], 1)

    def test_growth_does_not_allow_deleted_old_bytes_to_hide_new_bytes(self):
        self.assertEqual(guard.growth({'new': 100}, {'old': 1000}), 100)
        self.assertEqual(guard.growth({'same': 25}, {'same': 100}), 0)
        self.assertEqual(guard.growth({'same': 125}, {'same': 100}), 25)

    def test_separate_copy_counts_even_if_content_identical(self):
        (self.root / 'one').write_bytes(b'x' * 1024)
        (self.root / 'two').write_bytes(b'x' * 1024)
        self.assertEqual(self.scan()['distinct_bytes'], 2048)

    def test_metadata_scan_does_not_read_secret_contents(self):
        (self.root / 'secret').write_text('this content must never be opened')
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('content read')), \
             patch.object(Path, 'read_text', side_effect=AssertionError('content read')):
            self.assertGreater(self.scan()['distinct_bytes'], 0)

    def test_required_root_missing_is_failure_optional_missing_explicit(self):
        missing = str(self.root / 'missing')
        with self.assertRaises(ValueError):
            self.scan([{'path': missing, 'required': True}])
        self.assertEqual(self.scan([{'path': missing}])['missing_optional_roots'], [missing])

    def test_top_file_prefix_filter_never_traverses_private_directories(self):
        private = self.root / 'state_private'
        private.mkdir()
        (private / 'secret').write_bytes(b'x' * 900)
        (self.root / 'state_1.sqlite').write_bytes(b'x' * 100)
        (self.root / 'auth.json').write_bytes(b'x' * 700)
        actual = self.scan([{'path': str(self.root), 'top_files_only': True, 'name_prefixes': ['state_']}])
        self.assertEqual(actual['distinct_bytes'], 100)

    def test_real_wsl_hardlink_symlink_and_escape_counterexamples(self):
        code = '''import sys,tempfile,pathlib,os,json
sys.path.insert(0,sys.argv[1]); import storage_guard as g
with tempfile.TemporaryDirectory(prefix='campaign001-counterexample-') as t:
 root=pathlib.Path(t); watched=root/'watched';watched.mkdir()
 (watched/'one').write_bytes(b'x'*1024);os.link(watched/'one',watched/'two')
 (root/'outside').write_bytes(b'x'*4096);(watched/'escape').symlink_to(root/'outside')
 sample=g.scan([{'path':str(watched),'required':True}],['/'])
 assert sample['distinct_bytes']==1024 and sample['pathname_bytes']==2048
 assert sample['skipped_links']==1
 (root/'alias').symlink_to(watched,target_is_directory=True)
 try:g.scan([{'path':str(root/'alias'),'required':True}],['/'])
 except ValueError:pass
 else:raise AssertionError('Alias root accepted')
 print(json.dumps({'distinct_bytes':sample['distinct_bytes'],'pathname_bytes':sample['pathname_bytes'],'symlink_escape_not_followed':True,'alias_root_rejected':True}))
'''
        proc = subprocess.run(['wsl.exe', '-d', 'Ubuntu-24.04', '--', 'python3', '-B', '-c', code,
                               guard.wsl_path(Path(guard.__file__).parent)],
                              capture_output=True, text=True, encoding='utf-8', timeout=20,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.assertEqual(proc.returncode, 0, 'WSL counterexample failed')
        self.assertTrue(json.loads(proc.stdout)['symlink_escape_not_followed'])

    def test_planning_overrun_only_notifies_but_capacity_threat_stops(self):
        cfg = {'reserve_bytes': 100, 'retirement_headroom_bytes': 2,
               'planning_allowance_bytes': 40, 'large_growth_notice_bytes': 60}
        sample = {'aggregate_additional_bytes': 41,
                  'native': {'free_bytes': {'C': 200}}, 'wsl': {'free_bytes': {'/': 200}}}
        stops, notices = guard.decisions(sample, cfg)
        self.assertEqual(stops, [])
        self.assertIn('planning_allowance_exceeded_not_a_hard_cutoff', notices)
        sample['aggregate_additional_bytes'] = 61
        self.assertIn('unexpectedly_large_growth_notify_Randy', guard.decisions(sample, cfg)[1])
        sample['native']['free_bytes']['C'] = 101
        self.assertEqual(guard.decisions(sample, cfg)[0], ['native_free_reserve_threat'])

    def test_protected_stop_uses_ephemeral_capability_but_never_serializes_it(self):
        secret = 'synthetic-capability-never-real-credential'
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                requests.append((self.command, self.path, self.headers.get('X-Robot-Operator-Capability')))
                self.send_response(200); self.end_headers()
                self.wfile.write(b'{"ok": true, "authority_epoch": 7}')
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append((self.command, self.path, body))
                self.send_response(200); self.end_headers()
                self.wfile.write(b'{"ok": true, "command": {"status": "completed"}}')
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            path = self.root / 'endpoint.json'
            path.write_text(json.dumps({'url': 'http://127.0.0.1:' + str(server.server_port), 'capability': secret}))
            result = guard.protected_stop(path)
            self.assertEqual(result['status'], 'accepted')
            self.assertEqual(requests[0][2], secret)
            self.assertEqual(requests[1][2]['authority_epoch'], 7)
            self.assertNotIn(secret, json.dumps(result))
            path.write_text(json.dumps({'url': 'http://example.com', 'capability': secret}))
            failure = guard.protected_stop(path)
            self.assertEqual(failure['status'], 'failed')
            self.assertNotIn(secret, json.dumps(failure))
        finally:
            server.shutdown(); thread.join(); server.server_close()

    def monitor_case(self, queue_started, scan_failure=False):
        config = {'schema': guard.SCHEMA, 'reserve_bytes': 100, 'retirement_headroom_bytes': 2,
                  'planning_allowance_bytes': 1000, 'large_growth_notice_bytes': 1500,
                  'interval_s': 0.01, 'max_sample_gap_s': 30, 'safe_stop': False,
                  'accounting_scope': 'test only'}
        config_path = self.root / 'policy.json'; guard.write_json(config_path, config)
        sample = {'started_utc': '2026-09-27T10:00:00+00:00', 'finished_utc': '2026-09-27T10:00:03+00:00',
                  'native': {'identities': {'n': 10}, 'free_bytes': {'C': 200}},
                  'wsl': {'identities': {'w': 20}, 'free_bytes': {'/': 200}}}
        baseline = self.root / 'baseline.json'
        guard.write_json(baseline, {'config_sha256': guard.digest(config_path), 'sample': sample})
        job_file = self.root / 'submit.json'; guard.write_json(job_file, {'id': 'fixture-job'})
        args = argparse.Namespace(output=self.root / 'monitor', baseline=baseline, config=config_path,
            manifest=self.root / 'manifest', evidence=self.root / 'orchestrator', host_evidence=self.root / 'host',
            workspace=self.root / 'workspace', run_id='fixture-run', max_wait_s=0.01, job_file=job_file)
        queue = {'id': 'fixture-job', 'state': 'succeeded', 'exit_status': 0,
                 'started_at': queue_started, 'ended_at': '2026-09-27T10:00:02Z'}
        with patch.object(guard, 'collect', side_effect=OSError if scan_failure else None, return_value=sample), \
             patch.object(guard, 'queue_status', return_value=queue), contextlib.redirect_stdout(io.StringIO()):
            guard.monitor(args, config)
        return guard.read_json(args.output / 'receipt.json')

    def test_early_monitor_covers_full_queue_interval_and_binds_samples(self):
        result = self.monitor_case('2026-09-27T10:00:01Z')
        self.assertTrue(result['coverage_complete'])
        self.assertEqual(result['sample_count'], 2)
        self.assertEqual(result['samples']['sha256'], guard.digest(result['samples']['path']))
        self.assertEqual(result['official_queue_receipt']['sha256'], guard.digest(result['official_queue_receipt']['path']))

    def test_late_monitor_cannot_claim_coverage(self):
        result = self.monitor_case('2026-09-27T09:59:59Z')
        self.assertFalse(result['coverage_complete'])

    def test_scan_failure_cannot_pass_or_issue_ready(self):
        result = self.monitor_case('2026-09-27T10:00:01Z', scan_failure=True)
        self.assertFalse(result['coverage_complete'])
        self.assertTrue(result['admission_stop_latched'])
        self.assertFalse((self.root / 'monitor' / 'ready.json').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
