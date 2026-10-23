"""Full transport-reader controls with the prospective process-drain proof."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
for path in (HERE.parents[1]/'harness', HERE.parents[1]/'assessment', HERE):
    sys.path.insert(0, str(path))
import build_reader
import candidate_transport as transport
import process_integrity as subject
from test_cleanup_transport import upgrade
from test_transport_integrity_v3 import Fixture, stream

class ReaderTests(unittest.TestCase):
    def make(self, count=2):
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        f = upgrade(Fixture(directory, count=count))
        for name in subject.SOURCE_NAMES:
            if name not in f.frozen['sources']:
                path = f.repo/name; path.parent.mkdir(parents=True, exist_ok=True)
                raw = ('synthetic process-drain source '+name).encode(); path.write_bytes(raw)
                f.frozen['sources'][name] = stream(raw)
        q, cleanup = f.quiescence, f.quiescence['cleanup_barrier']
        base = {'schema': 'campaign002-process-drain-request-1',
            'cleanup_request_sha256': cleanup['request_sha256'],
            'owner_receipt_sha256': cleanup['request']['owner_receipt_sha256'],
            'start_monotonic_s': q['start_monotonic_s'],
            'graceful_deadline_monotonic_s': q['graceful_deadline_monotonic_s']}
        prefix = next(r for r in f.parent if r['kind'] == 'retirement_started')['sequence']-1
        observed = [{'sequence': e['sequence'], 'phase': e['phase'],
            'observed_perf_counter_ns': 1000000+e['sequence']*1000} for e in q['events']]
        at = next(r['observed_perf_counter_ns'] for r in observed if r['phase'] == 'finishing')
        f.process_files = {}
        prepared = None
        for phase, offset in (('prepare', 0), ('finish', 1000)):
            request = {**base, 'phase': phase, 'prepare_sha256':
                       subject.digest(subject.canonical(prepared)) if prepared else None}
            bridge = {'schema': 'campaign002-process-drain-bridge-1', 'request': request, 'qualified': True,
                'channels': list(range(1, count+1)), 'ledger_prefix':
                    {'sequence': prefix, 'sha256': f.parent[prefix-1]['record_sha256']},
                'completed_monotonic_s': f.parent[prefix-1]['monotonic_s']+.00001,
                'completed_perf_counter_ns': at+offset+200, 'frontiers': []}
            if phase == 'prepare':
                bridge['frontiers'] = [{'channel_id': c['channel_id'],
                    'h2': {'error': None, 'preface_complete': True, 'settings_complete': True,
                           'frames_complete': True, 'headers_complete': True, 'open_streams': 0},
                    'meters': copy.deepcopy(c['meters'])} for c in f.channels]
                prepared = bridge
            native = {'schema': 'campaign002-process-drain-client-1', 'request': copy.deepcopy(request),
                'bridge': copy.deepcopy(bridge), 'begin_perf_counter_ns': at+offset+100,
                'received_perf_counter_ns': at+offset+300}
            f.process_files['codehost-process-'+phase+'.json'] = bridge
            f.process_files['client/native-process-'+phase+'.json'] = native
        f.process_files['client/native-shutdown-order.json'] = {
            'schema': 'campaign002-native-shutdown-order-1', 'lifecycle': observed,
            'stdin_close': [{'begin_perf_counter_ns': at+400, 'end_perf_counter_ns': at+500, 'returned_normally': True}]}
        return f

    def verify(self, f, omit=None):
        f.write()
        for name, value in f.process_files.items():
            if name != omit: (f.stage/name).write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
        with patch.object(transport, 'REPO', f.repo):
            return transport.verify_transport_integrity(f.stage, f.frozen, allow_empty=not f.channels)

    def sync_bridge(self, f, phase):
        bridge = f.process_files['codehost-process-'+phase+'.json']
        native = f.process_files['client/native-process-'+phase+'.json']
        native['bridge'] = copy.deepcopy(bridge); native['request'] = copy.deepcopy(bridge['request'])
        if phase == 'prepare':
            f.process_files['codehost-process-finish.json']['request']['prepare_sha256'] = subject.digest(subject.canonical(bridge))
            self.sync_bridge(f, 'finish')

    def test_every_original_reader_check_is_preserved(self):
        _, expected = build_reader.render()
        self.assertEqual((HERE/'candidate_transport.py').read_bytes(), expected)

    def test_complete_empty_and_two_channel_transport(self):
        for count in (0, 2):
            with self.subTest(count=count):
                proof = self.verify(self.make(count))
                self.assertTrue(proof['passed']); self.assertTrue(proof['native_process_drain']['passed'])
                self.assertNotIn('native_pre_exit_drain', proof)

    def test_no_missing_sidecar_fallback(self):
        for name in self.make().process_files:
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'missing'):
                self.verify(self.make(), omit=name)

    def test_wrong_order_stale_deadline_and_duplicate_close(self):
        for mode in ('early_close', 'early_finish', 'late', 'stale', 'duplicate', 'boolean'):
            with self.subTest(mode=mode):
                f = self.make(); order = f.process_files['client/native-shutdown-order.json']
                if mode == 'early_close': order['stdin_close'][0]['begin_perf_counter_ns'] = 1
                if mode == 'early_finish': f.process_files['client/native-process-finish.json']['begin_perf_counter_ns'] = 1
                if mode == 'late':
                    b = f.process_files['codehost-process-finish.json']; b['completed_monotonic_s'] = b['request']['graceful_deadline_monotonic_s']
                    self.sync_bridge(f, 'finish')
                if mode == 'stale': f.process_files['client/native-process-prepare.json']['received_perf_counter_ns'] = 1
                if mode == 'duplicate': order['stdin_close'] *= 2
                if mode == 'boolean': order['stdin_close'][0]['begin_perf_counter_ns'] = True
                with self.assertRaises(ValueError): self.verify(f)

    def test_incomplete_application_frontier_and_frame_counts(self):
        for mode in ('active', 'partial', 'error', 'unforwarded', 'ledger_bytes', 'boolean'):
            with self.subTest(mode=mode):
                f = self.make(); frontier = f.process_files['codehost-process-prepare.json']['frontiers'][0]
                if mode == 'active': frontier['h2']['open_streams'] = 1
                if mode == 'partial': frontier['h2']['frames_complete'] = False
                if mode == 'error': frontier['h2']['error'] = 'reset'
                if mode == 'unforwarded': frontier['meters']['client_written']['bytes'] += 1
                if mode == 'ledger_bytes':
                    frontier['meters']['client_read']['bytes'] += 1; frontier['meters']['upload']['bytes'] += 1
                if mode == 'boolean': frontier['h2']['open_streams'] = False
                self.sync_bridge(f, 'prepare')
                with self.assertRaises(ValueError): self.verify(f)

    def test_foreign_binding_prefix_and_channel_identity(self):
        for mode in ('request', 'prepare_hash', 'prefix', 'channels', 'boolean'):
            with self.subTest(mode=mode):
                f = self.make(); b = f.process_files['codehost-process-finish.json']
                if mode == 'request': b['request']['cleanup_request_sha256'] = 'd'*64
                if mode == 'prepare_hash': b['request']['prepare_sha256'] = 'e'*64
                if mode == 'prefix': b['ledger_prefix']['sha256'] = 'f'*64
                if mode == 'channels': b['channels'] = [1]
                if mode == 'boolean': b['channels'] = [True, 2]
                self.sync_bridge(f, 'finish')
                with self.assertRaises(ValueError): self.verify(f)

    def test_original_native_and_endpoint_requirements_remain_mandatory(self):
        for mode in ('forced', 'bytes', 'missing_eof'):
            with self.subTest(mode=mode):
                f = self.make()
                if mode == 'forced': f.quiescence['forced_job_close'] = True
                if mode == 'bytes': f.channels[0]['meters']['client_written']['bytes'] += 1
                if mode == 'missing_eof': f.parent[:] = [r for r in f.parent if r['kind'] != 'client_eof']
                with self.assertRaises(ValueError): self.verify(f)

    def test_missing_or_changed_candidate_source_fails(self):
        for mode in ('missing', 'changed'):
            f = self.make()
            if mode == 'missing': del f.frozen['sources'][subject.METHOD]
            else: (f.repo/subject.SOURCE_NAMES[1]).write_bytes(b'changed')
            with self.assertRaises(ValueError): self.verify(f)

    def test_actual_overlay_is_process_local_and_restores_on_exception(self):
        import physical
        import overlay
        runtime = sys.modules[physical.Runtime.__module__]
        original = (runtime.bootstrap.Client.close, runtime.with_codehost.__globals__['Bridge'])
        evidence = Path(self.enterContext(tempfile.TemporaryDirectory()))
        with self.assertRaisesRegex(RuntimeError, 'synthetic body'):
            with overlay.installed(physical, evidence):
                self.assertIsNot(runtime.bootstrap.Client.close, original[0])
                candidate = runtime.with_codehost.__globals__['Bridge']
                self.assertTrue(issubclass(candidate, original[1]))
                self.assertIs(candidate.handle, original[1].handle)
                self.assertIs(candidate.upload, original[1].upload)
                raise RuntimeError('synthetic body')
        self.assertEqual((runtime.bootstrap.Client.close, runtime.with_codehost.__globals__['Bridge']), original)

if __name__ == '__main__': unittest.main()
