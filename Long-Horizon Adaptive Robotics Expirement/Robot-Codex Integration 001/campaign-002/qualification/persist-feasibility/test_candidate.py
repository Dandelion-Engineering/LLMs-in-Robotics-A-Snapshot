"""Short disposable parity/error checks; no counterbalanced benchmark or robot."""
import ast
import inspect
from pathlib import Path
import sqlite3
import tempfile
import textwrap
import time
import unittest
from unittest import mock

from candidate import (CandidateEvidence, CandidateRecorder, OperationLog, SpaceLimitError,
                       SPACE_POLICY, POLICY, CORE_QUOTA)
from recorder import Recorder, RecordingFailure
from runtime_adapter import FutureEvidence
from benchmark import reader_fingerprint, recovery_check, workload


class CandidateTests(unittest.TestCase):
    def test_evidence_constructor_is_original_except_explicit_recorder_factory(self):
        extras={'mode','space_policy','operation_log'}
        class Normalize(ast.NodeTransformer):
            def visit_FunctionDef(self,node):
                self.generic_visit(node)
                kept=[(a,d) for a,d in zip(node.args.kwonlyargs,node.args.kw_defaults) if a.arg not in extras]
                node.args.kwonlyargs=[a for a,d in kept];node.args.kw_defaults=[d for a,d in kept]
                return node
            def visit_Call(self,node):
                self.generic_visit(node)
                if isinstance(node.func,ast.Name) and node.func.id=='CandidateRecorder':
                    node.func.id='Recorder';node.keywords=[kw for kw in node.keywords if kw.arg not in extras]
                return node
        original=ast.parse(textwrap.dedent(inspect.getsource(FutureEvidence.__init__)))
        candidate=ast.parse(textwrap.dedent(inspect.getsource(CandidateEvidence.__init__)))
        self.assertEqual(ast.dump(original,include_attributes=False),ast.dump(Normalize().visit(candidate),include_attributes=False))

    def test_original_delete_and_candidate_modes_have_exact_reader_payloads(self):
        with tempfile.TemporaryDirectory() as directory:
            results=[];encoded=[]
            for mode in ('original','DELETE','PERSIST'):
                log=OperationLog();path=Path(directory)/mode
                kwargs=dict(policy=POLICY,core_quota_bytes=CORE_QUOTA,clock=lambda:100.)
                evidence=(FutureEvidence(path,'same',**kwargs) if mode=='original' else
                          CandidateEvidence(path,'same',mode=mode,operation_log=log,**kwargs))
                measured=workload(evidence,16,2,16,12,173,log,time.perf_counter()+20)
                evidence.close();results.append((measured['input_sha256'],reader_fingerprint(path)))
                if mode!='original':
                    receipt=evidence.store.receipt();encoded.append(receipt['encoded_pairs_sha256'])
                    self.assertEqual([r['journal_mode'] for r in receipt['readbacks']],[mode,mode,'DELETE'])
                    self.assertTrue(all(r['synchronous']==2 for r in receipt['readbacks']))
                    self.assertEqual(receipt['encoded_pair_count'],16)
                    self.assertEqual(receipt['finalization_steps'],['sqlite_delete_mode_selected',
                        'sqlite_closed_no_sidecars_before_original_compression',
                        'original_exact_byte_gzip_manifest_publication_completed'])
                    self.assertFalse((path/'evidence.sqlite-journal').exists())
                    self.assertFalse((path/'evidence.sqlite').exists())
            self.assertEqual(results[0],results[1]);self.assertEqual(results[1],results[2])
            self.assertEqual(encoded[0],encoded[1])

    def test_persist_journal_is_counted_and_deleted_by_sqlite_before_gzip(self):
        with tempfile.TemporaryDirectory() as directory:
            rec=CandidateRecorder(Path(directory)/'data',run_id='same',mode='PERSIST',policy=POLICY,core_quota_bytes=CORE_QUOTA)
            rec.document('one',{'content':'committed'})
            journal=rec.path/'evidence.sqlite-journal'
            self.assertTrue(journal.exists());self.assertGreater(journal.stat().st_size,0)
            self.assertEqual(rec.space.last['journal'],journal.stat().st_size)
            import recorder
            original=recorder.gzip.GzipFile
            def checked_gzip(*args,**kwargs):
                self.assertFalse(journal.exists())
                self.assertIn('sqlite_closed_no_sidecars_before_original_compression',rec.finalization_steps)
                return original(*args,**kwargs)
            with mock.patch('recorder.gzip.GzipFile',side_effect=checked_gzip):rec.close()
            self.assertGreater(rec.space.maxima['journal'],0)

    def test_space_error_latches_first_failure_and_cannot_publish_success(self):
        with tempfile.TemporaryDirectory() as directory:
            rec=CandidateRecorder(Path(directory)/'data',run_id='same',mode='PERSIST',policy=POLICY,core_quota_bytes=CORE_QUOTA)
            rec.document('one',{'content':'committed'})
            with (rec.path/'evidence.sqlite.gz.partial').open('xb') as stream:
                stream.truncate(SPACE_POLICY['publication_limit_bytes']+1)
            with self.assertRaises(SpaceLimitError) as raised:rec.db.execute('SELECT 1')
            with self.assertRaises(SpaceLimitError) as closed:rec.close()
            self.assertIs(raised.exception,closed.exception)
            self.assertEqual(rec.first_failure['boundary'],'execute')
            self.assertFalse((rec.path/'container-manifest.json').exists())
            self.assertTrue((rec.path/'evidence.sqlite-journal').exists())
            rec.native.close()

    def test_commit_error_is_not_retried_or_masked_by_later_close(self):
        with tempfile.TemporaryDirectory() as directory:
            rec=CandidateRecorder(Path(directory)/'data',run_id='same',mode='PERSIST',policy=POLICY,core_quota_bytes=CORE_QUOTA)
            native=rec.native;error=sqlite3.OperationalError('injected commit failure')
            class Fault:
                calls=0
                def __getattr__(self,name):return getattr(native,name)
                def commit(self):self.calls+=1;raise error
            fault=Fault();object.__setattr__(rec.db,'_native',fault)
            with self.assertRaises(sqlite3.OperationalError) as raised:rec.image('frame',0.,b'rgb',b'depth')
            self.assertIs(raised.exception,error);self.assertEqual(fault.calls,1)
            with self.assertRaises(sqlite3.OperationalError) as closed:rec.close()
            self.assertIs(closed.exception,error);self.assertEqual(fault.calls,1)
            self.assertTrue(native.in_transaction)
            self.assertFalse((rec.path/'container-manifest.json').exists())
            native.close()

    def test_wrong_sync_and_delete_transition_fail_before_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            for defect in ('sync','delete'):
                rec=CandidateRecorder(Path(directory)/defect,run_id='same',mode='PERSIST',policy=POLICY,core_quota_bytes=CORE_QUOTA)
                rec.document('one',{'content':'committed'})
                native=rec.native
                if defect=='sync':native.execute('PRAGMA synchronous=NORMAL')
                else:
                    class Refused:
                        def __getattr__(self,name):return getattr(native,name)
                        def execute(self,statement,*args):
                            if statement=='PRAGMA journal_mode=DELETE':return type('Cursor',(),{'fetchone':lambda self:('persist',)})()
                            return native.execute(statement,*args)
                    rec.native=Refused()
                with self.assertRaises(RecordingFailure):rec.close()
                self.assertIsNotNone(rec.first_failure)
                self.assertFalse((rec.path/'container-manifest.json').exists())
                native.close()

    def test_unexpected_sidecar_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            rec=CandidateRecorder(Path(directory)/'data',run_id='same',mode='DELETE',policy=POLICY,core_quota_bytes=CORE_QUOTA)
            (rec.path/'unaccounted.bin').write_bytes(b'evidence')
            with self.assertRaisesRegex(SpaceLimitError,'Unexpected'):rec.db.execute('SELECT 1')
            self.assertIsNotNone(rec.first_failure);rec.native.close()

    def test_process_crash_retains_source_pair_and_recovery_committed_set(self):
        with tempfile.TemporaryDirectory() as directory:
            for stage in ('before_commit','after_commit'):
                result=recovery_check(Path(directory)/stage,'PERSIST',stage,time.perf_counter()+30)
                self.assertTrue(result['passed']);self.assertTrue(result['source_pair_preserved'])
                self.assertIn('evidence.sqlite',result['source_files'])
                self.assertIn('evidence.sqlite-journal',result['source_files'])
                self.assertEqual(result['committed_document_names'],['stable'] if stage=='before_commit' else ['pending','stable'])
                if stage=='before_commit':
                    self.assertNotEqual(result['ready']['first_journal_header_hex'][:16],'0000000000000000')


if __name__=='__main__':unittest.main()
