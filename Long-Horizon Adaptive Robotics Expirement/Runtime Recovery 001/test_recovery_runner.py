"""Synthetic administrative checks only: no queue, model, robot or release runs.

Every mutable fixture lives in a temporary directory; canonical and queue readers
are replaced at the test boundary. The real supervisor is parsed, never imported.
"""
from __future__ import annotations
import ast
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from contextlib import ExitStack, redirect_stderr
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import recovery_runner as rr


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + '\n', encoding='utf-8')
    return {'path': str(path), 'sha256': rr.original.digest(path)}


class RecoveryFixtures(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='robot-recovery-unit-')
        self.root = Path(self.temp.name).resolve()
        self.addCleanup(self.temp.cleanup)
        self.checked = {'root': self.root,
            'annex_ref': {'path': str(self.root / 'annex.json'), 'sha256': 'a' * 64},
            'source_index_ref': {'path': str(self.root / 'index.json'), 'sha256': 'b' * 64},
            'source_index': {}, 'allowed_run_ids': ['next1', 'next2'],
            'retained_run_ids': ['old'], 'administrative_run_ids': ['lost'],
            'administrative_batch_ids': ['lost-batch'], 'dispositions': {'lost': {'run_id': 'lost'}},
            'annex': {'revision_ids': {'A1': 'recovery-A1'},
                      'parent_revision_ids': {'A1': 'release-A1-frozen'},
                      'administrative_dispositions': [{'run_id': 'lost',
                          'expected_canonical_note_id': 'lost-note',
                          'disposition_ref': {'path': 'lost.json', 'sha256': 'd' * 64}}]}}
        self.refs = rr._refs(self.checked)
        self.manifests = [self.manifest(identity, i) for i, identity in enumerate(['old', 'lost', 'next1', 'next2'])]
        self.verified = {'root': self.root, 'manifests': self.manifests, 'recovery': self.checked,
                         'release_sha256': 'e' * 64}
        self.data = {'run': [], 'result': [], 'revision': [], 'note': []}
        self.records = types.ModuleType('record_attempt')
        self.records.__file__ = str(rr.FROZEN_RUNTIME / 'record_attempt.py')
        self.records.MAP = self.root / 'map'
        self.records.am = types.SimpleNamespace(read_store=lambda _: (self.data, None, []), main=lambda _: 0)
        self.records.common = lambda identity, tags: {'id': identity, 'tags': tags}
        self.records.append = lambda kind, value: self.data[kind].append(value)
        self.stack = self.enterContext(ExitStack())
        self.stack.enter_context(patch.dict(sys.modules, {'record_attempt': self.records}))

    def manifest(self, identity, index):
        return {'run_id': identity, 'scheduled_index': index, 'release_id': 'release',
            'paired_block_id': 'block', 'architecture': 'A1', 'parts': 3, 'cap_s': 300,
            'condition': 'persistent', 'scenario': 'restart',
            'seeds': {'world_seed': 1, 'layout_seed': 2, 'policy_seed': 3, 'noise_seed': 4}}

    def context(self):
        retained = {'annex_ref': self.checked['annex_ref'], 'source_index_ref': self.checked['source_index_ref'],
                    'source_index': {}, **{k: self.checked['annex'][k] for k in ('revision_ids', 'parent_revision_ids')}}
        return rr.RecoveryEvaluationContext(self.root, json.dumps(self.manifests[2]), 'e' * 64,
            'f' * 64, 'job', 'now', '{}', json.dumps(retained), rr._AUTHORITY)

    def selection(self, *args, **kwargs):
        with patch.object(rr.original, 'continuation_state', return_value={
                'covered_attempts': {}, 'excluded_paired_block_ids': [], 'review_refs': []}):
            return rr.select_runs(self.verified, *args, **kwargs)

    def batch_fixture(self):
        job = 'job'; batch = self.root / 'batches' / job
        manifest_refs = []
        for m in self.manifests:
            ref = write(self.root / 'runs' / (m['run_id'] + '.json'), m)
            manifest_refs.append({**ref, 'run_id': m['run_id']})
        write(self.root / 'release.json', {'manifest_refs': manifest_refs})
        release_sha = rr.original.digest(self.root / 'release.json')
        write(batch / 'planned.json', {'schema_version': rr.AUTHORIZATION_VERSION,
            'queue_job_id': job, 'release_sha256': release_sha, 'limit': 2,
            'selected_run_ids': ['next1', 'next2'], 'schedule_order_preserved': True, **self.refs})
        terminal_refs = []
        for identity in ['next1', 'next2']:
            result = {'run_id': identity, 'stage': 'evaluation', 'execution_status': 'failed',
                'validity': 'valid', 'validity_reason': 'Fixed budget exhausted', 'outcome': 'failure',
                'ended_at': 'now', 'termination_reason': 'model_request_timeout',
                'infrastructure_invalid': False}
            source = write(self.root / 'attempts' / identity / 'evidence' / 'result.json', result)
            manifest_ref = next(r for r in manifest_refs if r['run_id'] == identity)
            terminal = {'run_id': identity, 'queue_job_id': job, 'revision_id': 'recovery-A1',
                'manifest_sha256': manifest_ref['sha256'], 'release_sha256': release_sha,
                'result': result, 'supervisor_result_ref': source, 'integrity_breach': False,
                'post_run_integrity': {'passed': True}, **self.refs}
            ref = write(self.root / 'attempts' / identity / 'terminal.json', terminal)
            terminal_refs.append({**ref, 'run_id': identity})
            write(self.root / 'attempts' / identity / 'registered.json', {
                'run_id': identity, 'revision_id': 'recovery-A1', **self.refs})
            self.data['run'].append({'id': identity, 'revision_id': 'recovery-A1', 'condition_details': self.refs})
        write(batch / 'finished.json', {'queue_job_id': job, 'terminal_run_ids': ['next1', 'next2'],
            'terminal_refs': terminal_refs, 'unlaunched_selected_run_ids': [], 'stop_reason': None, **self.refs})
        receipt = {'id': job, 'state': 'succeeded', 'exit_status': 0,
            'worker_pid': 1, 'child_pid': 2, 'started_at': 'start', 'ended_at': 'end',
            'cwd': str(self.root), 'argv': [sys.executable, '-B', str(rr.SCRIPT), 'run',
                '--release-dir', str(self.root), '--annex', self.checked['annex_ref']['path'], '--limit', '2']}
        status = self.root / 'saved-status.json'; write(status, receipt)
        self.stack.enter_context(patch.object(rr, '_contract', return_value=self.checked))
        self.stack.enter_context(patch.object(rr, 'read_shared_json', return_value={'jobs': [receipt]}))
        return batch, status

    def finalize(self, status):
        return rr.finalize(self.root, self.checked['annex_ref']['path'], 'job', status)


class SelectionTests(RecoveryFixtures):
    def test_exact_history_disposition_only_and_schedule_order(self):
        (self.root / 'attempts' / 'lost').mkdir(parents=True)
        (self.root / 'batches' / 'lost-batch').mkdir(parents=True)
        self.assertEqual([m['run_id'] for m in self.selection()], ['next1', 'next2'])
        (self.root / 'attempts' / 'unresolved').mkdir()
        with self.assertRaisesRegex(rr.ReleaseError, 'Unresolved'):
            self.selection()

    def test_unfinished_additional_batch_blocks(self):
        (self.root / 'batches' / 'another').mkdir(parents=True)
        with self.assertRaisesRegex(rr.ReleaseError, 'Unfinalized'):
            self.selection()

    def test_registered_missing_evidence_never_retried(self):
        self.data['run'].append({'id': 'next2'})
        with self.assertRaisesRegex(rr.ReleaseError, 'lost its evidence'):
            self.selection(limit=1)

    def test_scope_duplicate_and_boolean_limit_refused(self):
        for ids in (['lost'], ['old'], ['next1', 'next1']):
            with self.subTest(ids=ids), self.assertRaises(rr.ReleaseError):
                self.selection(ids)
        with self.assertRaises(rr.ReleaseError):
            self.selection(limit=True)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            rr.parser().parse_args(['run', '--release-dir', '.', '--annex', 'x', '--run-id', 'next2'])

    def test_current_batch_exception_is_exact_hash_bound(self):
        path = self.root / 'batches' / 'active' / 'planned.json'
        value = {'schema_version': rr.AUTHORIZATION_VERSION, 'queue_job_id': 'active',
                 'selected_run_ids': ['next1'], **self.refs}
        ref = {**write(path, value), 'queue_job_id': 'active'}
        self.assertEqual(self.selection(['next1'], _active_batch=ref)[0]['run_id'], 'next1')
        write(path, {**value, 'selected_run_ids': ['next2']})
        with self.assertRaises(rr.ReleaseError):
            self.selection(['next1'], _active_batch=ref)

    def test_invalid_or_integrity_terminal_stops_without_exact_review(self):
        path = self.root / 'attempts' / 'next1' / 'terminal.json'
        for row in ({'result': {'validity': 'invalid'}, 'post_run_integrity': {'passed': True}},
                    {'result': {'validity': 'valid'}, 'integrity_breach': True}):
            write(path, {**row, **self.refs})
            with self.subTest(row=row), self.assertRaises(rr.ReleaseError):
                self.selection()

    def test_partition_exact_disjoint_complete_original_order(self):
        manifests = [{'run_id': str(i), 'scheduled_index': i} for i in range(264)]
        checked = {**self.checked, 'allowed_run_ids': [str(i) for i in range(133, 264)],
                   'retained_run_ids': [str(i) for i in range(132)], 'administrative_run_ids': ['132'],
                   'dispositions': {'132': {}}}
        rr._partition({'manifests': manifests}, checked)
        for key, value in [('allowed_run_ids', list(reversed(checked['allowed_run_ids']))),
                           ('administrative_run_ids', ['0']), ('dispositions', {})]:
            with self.subTest(key=key), self.assertRaises(rr.ReleaseError):
                rr._partition({'manifests': manifests}, {**checked, key: value})


class AuthorityTests(RecoveryFixtures):
    def test_only_exact_queue_path_acquires_lock_and_no_reader_save(self):
        target = self.root / 'state.json'; other = self.root / 'other.json'; events = []
        class Lock:
            def __init__(self, path):
                self.path = path
            def __enter__(self):
                events.append(('acquire', self.path))
            def __exit__(self, *args):
                events.append(('release', self.path))
        def raw(path):
            events.append(('read-close', path)); return {'generation': 1}
        with patch.object(rr.original, 'QUEUE_STATE', target), \
             patch.object(rr, '_installed_queue_lock', return_value=Lock) as installed, \
             patch.object(rr, '_read_shared_json', side_effect=raw):
            self.assertEqual(rr.read_shared_json(other), {'generation': 1})
            installed.assert_not_called(); events.clear()
            self.assertEqual(rr.read_shared_json(target), {'generation': 1})
        self.assertEqual(events, [('acquire', target.with_name('state.lock')),
                                  ('read-close', target), ('release', target.with_name('state.lock'))])

    def test_unpinned_queue_source_fails_before_import(self):
        with patch.object(rr.original, 'digest', return_value='0' * 64), \
             patch.object(rr.importlib.util, 'spec_from_file_location', side_effect=AssertionError('Unpinned import')):
            with self.assertRaisesRegex(rr.ReleaseError, 'Installed queue source differs'):
                rr._installed_queue_lock()

    def test_queue_ownership_uses_safe_reader_and_actual_entrypoint(self):
        job = {'id': 'owned', 'state': 'running', 'child_pid': os.getpid(),
               'cwd': str(self.root), 'argv': [sys.executable, '-B', str(rr.SCRIPT), 'run']}
        with patch.object(rr.sys, 'argv', [str(rr.SCRIPT)]), \
             patch.object(rr, 'read_shared_json', return_value={'jobs': [job]}) as safe, \
             patch.object(rr.original, 'queued_job', side_effect=AssertionError('Unsafe old live reader')):
            self.assertEqual(rr.queued_job(), job)
            safe.assert_called_once_with(rr.original.QUEUE_STATE)
        with patch.object(rr.sys, 'argv', [str(self.root / 'wrapper.py')]), \
             patch.object(rr, 'read_shared_json', side_effect=AssertionError('Must reject before reading')):
            with self.assertRaises(rr.ReleaseError):
                rr.queued_job()

    def test_context_own_authority_exact_seeds_and_architecture_revision(self):
        context = self.context(); kwargs = context.episode_kwargs(); kwargs.pop('evaluation_context')
        self.assertEqual(context.revision_id, 'recovery-A1')
        self.assertEqual(context.assert_episode(**kwargs), context.evidence_dir)
        with self.assertRaises(rr.ReleaseError):
            context.assert_episode(**{**kwargs, 'world_seed': 99})
        forged = rr.RecoveryEvaluationContext(**{**context.__dict__, '_authority': object()})
        with self.assertRaises(rr.ReleaseError):
            forged.assert_episode(**kwargs)
        context.evidence_dir.mkdir(parents=True)
        with self.assertRaisesRegex(rr.ReleaseError, 'not fresh'):
            context.assert_episode(**kwargs)

    def test_authorizer_uses_original_gate_and_exact_untouched_manifest(self):
        self.verified.update(artifacts={}, release={'manifest_refs': [
            {'run_id': m['run_id'], 'sha256': 'f' * 64} for m in self.manifests]})
        with patch.object(rr, 'queued_job', return_value={'id': 'job'}), \
             patch.object(rr, 'verify_recovery', return_value=self.verified) as gate:
            context = rr.authorize_evaluation(self.manifests[2], self.root, 'annex')
            self.assertEqual(context.revision_id, 'recovery-A1'); gate.assert_called_once()
            with self.assertRaises(rr.ReleaseError):
                rr.authorize_evaluation({**self.manifests[2], 'cap_s': 301}, self.root, 'annex')
            with self.assertRaises(rr.ReleaseError):
                rr.authorize_evaluation(self.manifests[1], self.root, 'annex')
            self.data['run'].append({'id': 'next1'})
            with self.assertRaises(rr.ReleaseError):
                rr.authorize_evaluation(self.manifests[2], self.root, 'annex')

    def test_canonical_note_is_exact_typed_separate_evidence(self):
        entry = self.checked['annex']['administrative_dispositions'][0]
        note = {'id': 'lost-note', 'target_ids': ['lost'], 'claim_type': 'decision', 'details': {
            'provenance_kind': 'administrative_interruption', 'recovery_annex_ref': self.checked['annex_ref'],
            'administrative_disposition_ref': entry['disposition_ref']}}
        self.data['note'] = [note]; rr.verify_administrative_notes(self.checked)
        for changed in ({**note, 'target_ids': ['next1']}, {**note, 'supersedes_note_id': 'old-note'},
                        {**note, 'details': {**note['details'], 'provenance_kind': 'success'}}):
            self.data['note'] = [changed]
            with self.assertRaises(rr.ReleaseError):
                rr.verify_administrative_notes(self.checked)
        self.data['note'] = [note, {'id': 'replacement', 'supersedes_note_id': 'lost-note'}]
        with self.assertRaises(rr.ReleaseError):
            rr.verify_administrative_notes(self.checked)
        self.data['note'] = [note, {**note, 'id': 'conflicting-interruption-note'}]
        with self.assertRaises(rr.ReleaseError):
            rr.verify_administrative_notes(self.checked)

    def test_recovery_verification_retains_original_heavy_gate(self):
        with patch.object(rr, '_contract', return_value=self.checked), \
             patch.object(rr, 'verify_administrative_notes') as notes, \
             patch.object(rr, '_partition') as partition, \
             patch.object(rr.original, 'verify_release', return_value={'root': self.root}) as original:
            value = rr.verify_recovery('annex', self.root)
        original.assert_called_once_with(self.root); notes.assert_called_once_with(self.checked)
        partition.assert_called_once(); self.assertIs(value['recovery'], self.checked)


class FinalizationTests(RecoveryFixtures):
    def test_valid_policy_failure_finalizes_once_and_resume_is_metadata_only(self):
        batch, status = self.batch_fixture()
        with patch.object(rr, 'require_supervisor_hook', side_effect=AssertionError('No episode during finalization')):
            self.finalize(status); self.finalize(status)
        self.assertEqual(len(self.data['result']), 2)
        self.assertTrue((batch / 'finalized.json').is_file())
        self.assertEqual([r['validity'] for r in self.data['result']], ['valid', 'valid'])
        self.assertTrue(all(r['details']['revision_id'] == 'recovery-A1' for r in self.data['result']))
        self.assertTrue(all(r['metrics'][0]['value'] is None for r in self.data['result']))

    def test_partial_append_resumes_exactly_without_episode_retry(self):
        batch, status = self.batch_fixture(); calls = []
        def append(kind, value):
            calls.append(value['id'])
            if value['id'] == 'next2-result':
                raise PermissionError('Synthetic atomic replacement failure')
            self.data[kind].append(value)
        self.records.append = append
        with self.assertRaises(PermissionError):
            self.finalize(status)
        self.assertFalse((batch / 'finalized.json').exists())
        self.assertEqual(len(self.data['result']), 1)
        self.records.append = lambda kind, value: self.data[kind].append(value)
        self.finalize(status)
        self.assertEqual([r['id'] for r in self.data['result']], ['next1-result', 'next2-result'])

    def test_changed_terminal_hash_rejected_before_canonical_append(self):
        _, status = self.batch_fixture()
        path = self.root / 'attempts' / 'next1' / 'terminal.json'
        value = rr.original.load(path); value['revision_id'] = 'wrong'; write(path, value)
        with self.assertRaises(rr.ReleaseError):
            self.finalize(status)
        self.assertEqual(self.data['result'], [])

    def test_wrong_lineage_rejected_even_if_terminal_and_registration_agree(self):
        batch, status = self.batch_fixture(); identity = 'next1'
        terminal_path = self.root / 'attempts' / identity / 'terminal.json'
        terminal = rr.original.load(terminal_path); terminal['revision_id'] = 'wrong'
        ref = write(terminal_path, terminal)
        write(terminal_path.parent / 'registered.json', {'run_id': identity, 'revision_id': 'wrong', **self.refs})
        finished = rr.original.load(batch / 'finished.json')
        finished['terminal_refs'][0] = {**ref, 'run_id': identity}; write(batch / 'finished.json', finished)
        with self.assertRaisesRegex(rr.ReleaseError, 'revision'):
            self.finalize(status)
        self.assertEqual(self.data['result'], [])

    def test_unlaunched_partition_missing_annex_and_interruption_are_not_success(self):
        batch, status = self.batch_fixture(); finished = rr.original.load(batch / 'finished.json')
        for changed in ({**finished, 'unlaunched_selected_run_ids': ['next1']},
                        {k: v for k, v in finished.items() if k != 'recovery_annex_ref'}):
            write(batch / 'finished.json', changed)
            with self.assertRaises(rr.ReleaseError):
                self.finalize(status)
        with self.assertRaisesRegex(rr.ReleaseError, 'Historical interrupted'):
            rr.finalize(self.root, 'annex', 'lost-batch', status)
        self.assertEqual(self.data['result'], [])

    def test_saved_receipt_requires_actual_same_successful_queue_record(self):
        _, status = self.batch_fixture(); receipt = rr.original.load(status)
        with patch.object(rr, 'read_shared_json', return_value={'jobs': [{**receipt, 'child_pid': 999}]}):
            with self.assertRaises(rr.ReleaseError):
                rr.verify_queue_receipt('job', status)
        for change in ({'state': 'interrupted'}, {'exit_status': False}, {'exit_status': 1}):
            write(status, {**receipt, **change})
            with self.subTest(change=change), self.assertRaises(rr.ReleaseError):
                rr.verify_queue_receipt('job', status)


class SupervisorSourceTests(unittest.TestCase):
    def test_only_authority_and_provenance_change_episode_functions(self):
        old = ast.parse((rr.FROZEN_RUNTIME / 'experiment.py').read_text(encoding='utf-8'))
        new = ast.parse((HERE / 'experiment_recovery.py').read_text(encoding='utf-8'))
        old_functions = {n.name: n for n in old.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        new_functions = {n.name: n for n in new.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        self.assertEqual(set(old_functions), set(new_functions))
        extras = {'code_source_root', 'administrative_code_source_root', 'administrative_code_sha256', 'executed_supervisor'}
        class Normalize(ast.NodeTransformer):
            def visit_Name(self, node):
                if node.id == 'FROZEN_RUNTIME':
                    node.id = 'HERE'
                return node
            def visit_Dict(self, node):
                pairs = [(key, value) for key, value in zip(node.keys, node.values)
                         if not isinstance(key, ast.Constant) or key.value not in extras]
                node.keys = [p[0] for p in pairs]; node.values = [p[1] for p in pairs]
                return self.generic_visit(node)
        for name, node in old_functions.items():
            if name == 'authorized_evidence_path':
                continue
            other = copy.deepcopy(new_functions[name])
            if name == 'run_episode':
                other = Normalize().visit(other)
            self.assertEqual(ast.dump(node), ast.dump(other), name)
        guard = new_functions['authorized_evidence_path']
        imports = [n for n in ast.walk(guard) if isinstance(n, ast.ImportFrom)]
        self.assertEqual([(n.module, [x.name for x in n.names]) for n in imports],
                         [('recovery_runner', ['RecoveryEvaluationContext'])])
        self.assertIn('context.assert_episode', ast.unparse(guard))
        self.assertIn('context.execution_provenance', ast.unparse(guard))


@unittest.skipUnless(os.name == 'nt', 'Windows delete-sharing behavior')
class WindowsSharedReaderTests(RecoveryFixtures):
    def test_delete_sharing_alone_still_denies_open_destination_replacement(self):
        """Retain the measured limitation; do not call this concurrent-write safe."""
        import ctypes
        path = self.root / 'snapshot.json'; replacement = self.root / 'replacement.json'
        write(path, {'generation': 1}); write(replacement, {'generation': 2})
        actual = ctypes.WinDLL('kernel32', use_last_error=True)
        original_read = actual.ReadFile
        calls = []; failures = []
        class WrappedRead:
            def __call__(self, *args):
                original_read.argtypes = self.argtypes; original_read.restype = self.restype
                if not calls:
                    try:
                        os.replace(replacement, path)
                    except PermissionError as error:
                        failures.append(error.winerror)
                calls.append(True)
                return original_read(*args)
        proxy = types.SimpleNamespace(CreateFileW=actual.CreateFileW, GetFileSizeEx=actual.GetFileSizeEx,
                                      ReadFile=WrappedRead(), CloseHandle=actual.CloseHandle)
        with patch.object(ctypes, 'WinDLL', return_value=proxy):
            self.assertEqual(rr._read_shared_json(path), {'generation': 1})
        self.assertTrue(calls); self.assertEqual(failures, [5])
        os.replace(replacement, path)
        self.assertEqual(rr._read_shared_json(path), {'generation': 2})

    def test_installed_lock_serializes_temporary_writer_until_reader_closes(self):
        """Real installed lock and atomic writer, confined to an owned temp store."""
        import ctypes
        lock = rr._installed_queue_lock()
        queue = sys.modules[lock.__module__]
        store = queue.QueueStore(self.root / 'queue-fixture')
        with store.locked_state(save=True) as state:
            state['generation'] = 1
        started = threading.Event(); acquired = threading.Event(); errors = []; observations = []
        actual = ctypes.WinDLL('kernel32', use_last_error=True); actual_read = actual.ReadFile
        def writer():
            started.set()
            try:
                with lock(store.state_lock_path, timeout=3):
                    acquired.set(); value = store.load(); value['generation'] = 2; store.save(value)
            except BaseException as error:
                errors.append(error)
        worker = threading.Thread(target=writer, name='temporary-queue-writer', daemon=True)
        class WrappedRead:
            def __call__(self, *args):
                actual_read.argtypes = self.argtypes; actual_read.restype = self.restype
                if not observations:
                    worker.start()
                    if not started.wait(1):
                        raise AssertionError('Temporary writer did not start')
                    observations.append(not acquired.wait(.1))
                return actual_read(*args)
        proxy = types.SimpleNamespace(CreateFileW=actual.CreateFileW, GetFileSizeEx=actual.GetFileSizeEx,
                                      ReadFile=WrappedRead(), CloseHandle=actual.CloseHandle)
        try:
            with patch.object(rr.original, 'QUEUE_STATE', store.state_path), \
                 patch.object(ctypes, 'WinDLL', return_value=proxy):
                before = rr.read_shared_json(store.state_path)
        finally:
            if worker.ident is not None:
                worker.join(4)
        self.assertFalse(worker.is_alive()); self.assertEqual(errors, [])
        self.assertEqual(observations, [True]); self.assertEqual(before['generation'], 1)
        self.assertTrue(acquired.is_set())
        with store.locked_state() as state:
            self.assertEqual(state['generation'], 2)
        self.assertFalse(store.state_lock_path.exists())

    def test_read_failure_closes_handle_before_releasing_installed_lock(self):
        """A ReadFile error must not leave a handle/lock blocking the real writer."""
        import ctypes
        lock = rr._installed_queue_lock(); queue = sys.modules[lock.__module__]
        store = queue.QueueStore(self.root / 'queue-error-fixture')
        with store.locked_state(save=True) as state:
            state['generation'] = 1
        actual = ctypes.WinDLL('kernel32', use_last_error=True); actual_close = actual.CloseHandle
        closed_under_lock = []
        class FailedRead:
            def __call__(self, *args):
                ctypes.set_last_error(5); return 0
        class WatchedClose:
            def __call__(self, handle):
                actual_close.argtypes = self.argtypes; actual_close.restype = self.restype
                closed_under_lock.append(store.state_lock_path.exists())
                return actual_close(handle)
        proxy = types.SimpleNamespace(CreateFileW=actual.CreateFileW, GetFileSizeEx=actual.GetFileSizeEx,
                                      ReadFile=FailedRead(), CloseHandle=WatchedClose())
        with patch.object(rr.original, 'QUEUE_STATE', store.state_path), \
             patch.object(ctypes, 'WinDLL', return_value=proxy):
            with self.assertRaisesRegex(rr.ReleaseError, 'Serialized queue snapshot failed'):
                rr.read_shared_json(store.state_path)
        self.assertEqual(closed_under_lock, [True]); self.assertFalse(store.state_lock_path.exists())
        with store.locked_state(save=True) as state:
            self.assertEqual(state['generation'], 1); state['generation'] = 2
        with store.locked_state() as state:
            self.assertEqual(state['generation'], 2)


if __name__ == '__main__':
    unittest.main()
