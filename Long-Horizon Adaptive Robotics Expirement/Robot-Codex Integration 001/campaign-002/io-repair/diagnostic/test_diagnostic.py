"""Disposable, bounded method parity and fail-closed assessor tests; no full workload."""
from array import array
from contextlib import nullcontext
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import benchmark as bench
from assess import audit_ledger
from supervisor import Journal
from runtime_adapter import FutureEvidence
from recorder import Reader


def inputs():
    return dict(motion=[dict(sim_time_s=1.,q=[.1,-0.],dq=[0.,0.],tcp=[.1,.2,.3])],
        observations=[dict(type='observation',payload={'sequence':17,'joints':[.1,.2]},
                           authority_epoch=2,owner='robot',source='public_camera_and_devices')],
        state={'version':1,'ready':True},registry={'r1':{'status':'completed'}},
        pairs=[('overhead:1',b'unit-rgb-bytes',b'unit-depth-bytes')])


class DiagnosticTests(unittest.TestCase):
    def test_fixed_manifest_rejects_workload_drift(self):
        declared=dict(bench.EXPECTED,run_id='unit',framework_revision='unit')
        bench.validate_manifest(declared)
        for key in bench.EXPECTED:
            changed=dict(declared); changed[key]=None
            with self.subTest(key=key),self.assertRaises(ValueError): bench.validate_manifest(changed)

    def test_full_ledger_records_failure_and_assessor_rejects_it(self):
        ledger=bench.Ledger()
        with self.assertRaisesRegex(OSError,'injected'):
            with ledger.phase('parent'):
                with ledger.phase('child'): raise OSError('injected')
        self.assertEqual(ledger.sequence,2)
        self.assertEqual(len(ledger.values),22)
        with self.assertRaisesRegex(ValueError,'Failed operation'): audit_ledger(ledger.values,ledger.names)

    def test_assessor_rejects_missing_row_and_false_nesting(self):
        ledger=bench.Ledger()
        with ledger.phase('parent'):
            with ledger.phase('child'): pass
        audit_ledger(ledger.values,ledger.names)
        with self.assertRaisesRegex(ValueError,'Missing/duplicate'): audit_ledger(ledger.values[:11],ledger.names)
        corrupted=array('d',ledger.values); corrupted[5]=corrupted[16]+1
        with self.assertRaisesRegex(ValueError,'Child outside'): audit_ledger(corrupted,ledger.names)

    def test_ledger_bound_raises_without_truncation(self):
        ledger=bench.Ledger(maximum=1)
        with ledger.phase('one'): pass
        with self.assertRaisesRegex(RuntimeError,'bound'):
            with ledger.phase('two'): pass
        self.assertEqual(len(ledger.values),11)

    def test_exact_original_instrumented_readback_parity(self):
        outputs=[]
        with tempfile.TemporaryDirectory() as directory:
            for measured in (False,True):
                root=Path(directory)/str(measured); ledger=bench.Ledger()
                cls=bench.InstrumentedJournal if measured else Journal
                with mock.patch('time.monotonic',return_value=100.),mock.patch('time.time',return_value=200.):
                    journal=cls(root/'protected',root/'public','unit')
                    if measured: journal.capture=ledger
                    cls=bench.InstrumentedFutureEvidence if measured else FutureEvidence
                    kwargs={'phase':ledger.phase} if measured else {}
                    evidence=cls(root/'recording','unit',policy=bench.ImagePolicy(sparse_period_s=2.,image_quota_bytes=12000000),
                        core_quota_bytes=50000000,**kwargs)
                    for tick in range(21): bench.apply_tick(tick,inputs(),journal,evidence,ledger)
                    evidence.close()
                reader=Reader(root/'recording')
                try:
                    images=list(reader.images())
                    outputs.append(dict(motion=list(reader.motion()),images=images,
                        payloads=[reader.image(row['id']) for row in images],events=list(reader.events()),
                        journal=(root/'protected/public-history.jsonl').read_bytes(),
                        state=(root/'protected/public-state.json').read_bytes(),
                        registry=(root/'protected/command-registry.json').read_bytes()))
                finally: reader.close()
                self.assertEqual((root/'protected/public-history.jsonl').read_bytes(),(root/'public/live/events.jsonl').read_bytes())
            self.assertEqual(outputs[0],outputs[1])
            self.assertEqual(len(outputs[0]['motion']),21)
            self.assertEqual(len(outputs[0]['images']),3)

    def test_sql_commit_failure_prevents_journal_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); ledger=bench.Ledger()
            journal=bench.InstrumentedJournal(root/'protected',root/'public','unit'); journal.capture=ledger
            evidence=bench.InstrumentedFutureEvidence(root/'recording','unit',phase=ledger.phase)
            try:
                # Intercept only the proxy call; native SQL and original image logic remain.
                with mock.patch.object(type(evidence.store.db),'commit',side_effect=OSError('injected commit')):
                    with self.assertRaisesRegex(OSError,'injected commit'): bench.apply_tick(0,inputs(),journal,evidence,ledger)
                self.assertEqual(journal.events,[])
                self.assertFalse(journal.events_path.exists())
                self.assertFalse((journal.root/'command-registry.json').exists())
                with self.assertRaisesRegex(ValueError,'Failed operation'): audit_ledger(ledger.values,ledger.names)
            finally: evidence.store.db.close()
            self.assertFalse((root/'recording/container-manifest.json').exists())

    def test_public_fsync_failure_does_not_report_completed_event(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); ledger=bench.Ledger()
            journal=bench.InstrumentedJournal(root/'protected',root/'public','unit'); journal.capture=ledger
            with mock.patch('os.fsync',side_effect=[None,OSError('injected mirror')]):
                with self.assertRaisesRegex(OSError,'injected mirror'): journal.event('observation',{},1.,1,'conventional')
            self.assertEqual(journal.events,[]); self.assertEqual(journal.bytes,0)
            with self.assertRaisesRegex(ValueError,'Failed operation'): audit_ledger(ledger.values,ledger.names)


if __name__=='__main__': unittest.main()
