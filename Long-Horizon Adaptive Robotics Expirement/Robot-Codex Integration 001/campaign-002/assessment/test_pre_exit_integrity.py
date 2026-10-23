"""Full-assessor adversaries for the new native pre-exit requirement."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pre_exit_integrity as subject
import transport_integrity_v3 as transport
from test_cleanup_transport import upgrade
from test_transport_integrity_v3 import Fixture,stream

class PreExitTests(unittest.TestCase):
    def make(self,count=2):
        directory=Path(self.enterContext(tempfile.TemporaryDirectory()))
        f=upgrade(Fixture(directory,count=count))
        for name in subject.SOURCE_NAMES:
            if name not in f.frozen['sources']:
                path=f.repo/name;path.parent.mkdir(parents=True,exist_ok=True)
                raw=('synthetic pre-exit source '+name).encode();path.write_bytes(raw)
                f.frozen['sources'][name]=stream(raw)
        q=f.quiescence;cleanup=q['cleanup_barrier']
        request={'schema':'campaign002-native-pre-exit-request-1',
            'cleanup_request_sha256':cleanup['request_sha256'],
            'owner_receipt_sha256':cleanup['request']['owner_receipt_sha256'],
            'start_monotonic_s':q['start_monotonic_s'],
            'graceful_deadline_monotonic_s':q['graceful_deadline_monotonic_s']}
        # Complete pre-retirement prefix, including every endpoint channel closure.
        prefix=next(r for r in f.parent if r['kind']=='retirement_started')['sequence']-1
        observed=[{'sequence':e['sequence'],'phase':e['phase'],
                   'observed_perf_counter_ns':1000000+e['sequence']*1000} for e in q['events']]
        at=next(r['observed_perf_counter_ns'] for r in observed if r['phase']=='finishing')
        f.pre_bridge={'schema':'campaign002-native-pre-exit-bridge-1','request':request,'qualified':True,
            'channels':list(range(1,count+1)),
            'ledger_prefix':{'sequence':prefix,'sha256':f.parent[prefix-1]['record_sha256']},
            'completed_monotonic_s':f.parent[prefix-1]['monotonic_s']+.00001,
            'completed_perf_counter_ns':at+200}
        f.pre_native={'schema':'campaign002-native-pre-exit-client-1','request':copy.deepcopy(request),
            'bridge':copy.deepcopy(f.pre_bridge),'begin_perf_counter_ns':at+100,'received_perf_counter_ns':at+300}
        f.pre_order={'schema':'campaign002-native-shutdown-order-1','lifecycle':observed,
            'stdin_close':[{'begin_perf_counter_ns':at+400,'end_perf_counter_ns':at+500,'returned_normally':True}]}
        return f

    def verify(self,f,*,omit=None):
        f.write()
        for name,value in (('codehost-pre-exit-drain.json',f.pre_bridge),
                ('client/native-pre-exit-drain.json',f.pre_native),('client/native-shutdown-order.json',f.pre_order)):
            if name!=omit:(f.stage/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
        with patch.object(transport,'REPO',f.repo):
            return transport.verify_transport_integrity(f.stage,f.frozen,allow_empty=not f.channels)

    def test_full_path_empty_and_two_channels(self):
        for count in (0,2):
            with self.subTest(count=count):
                proof=self.verify(self.make(count))
                self.assertTrue(proof['passed']);self.assertTrue(proof['native_pre_exit_drain']['passed'])
                self.assertEqual(len(proof['native_pre_exit_drain']['channels']),count)

    def test_missing_sidecar_is_not_legacy_fallback(self):
        for name in ('codehost-pre-exit-drain.json','client/native-pre-exit-drain.json','client/native-shutdown-order.json'):
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'missing'):
                self.verify(self.make(),omit=name)

    def test_stdin_before_drain_is_rejected(self):
        f=self.make();f.pre_order['stdin_close'][0]['begin_perf_counter_ns']=1
        with self.assertRaisesRegex(ValueError,'stdin close preceded'):self.verify(f)

    def test_foreign_bridge_native_request_or_channels_rejected(self):
        for case in ('bridge_copy','request','channels','boolean_channel','extra'):
            with self.subTest(case=case):
                f=self.make()
                if case=='bridge_copy':f.pre_native['bridge']['qualified']=False
                if case=='request':f.pre_bridge['request']['cleanup_request_sha256']='e'*64
                if case=='channels':f.pre_bridge['channels']=[1]
                if case=='boolean_channel':f.pre_bridge['channels']=[True,2]
                if case=='extra':f.pre_bridge['unbounded_payload']='forbidden'
                if case!='bridge_copy':f.pre_native['bridge']=copy.deepcopy(f.pre_bridge)
                with self.assertRaises(ValueError):self.verify(f)

    def test_incomplete_and_wrong_hash_prefix_rejected(self):
        for mode in ('incomplete','hash','out_of_bounds'):
            with self.subTest(mode=mode):
                f=self.make()
                if mode=='incomplete':
                    row=next(r for r in f.parent if r['kind']=='owner_finishing')
                    f.pre_bridge['ledger_prefix']={'sequence':row['sequence'],'sha256':row['record_sha256']}
                if mode=='hash':f.pre_bridge['ledger_prefix']['sha256']='f'*64
                if mode=='out_of_bounds':f.pre_bridge['ledger_prefix']['sequence']=len(f.parent)+1
                f.pre_native['bridge']=copy.deepcopy(f.pre_bridge)
                with self.assertRaises(ValueError):self.verify(f)

    def test_late_nonfinite_boolean_duplicate_close_or_bad_lifecycle_rejected(self):
        for mode in ('late','nonfinite','boolean','duplicate','lifecycle'):
            with self.subTest(mode=mode):
                f=self.make()
                if mode=='late':f.pre_bridge['completed_monotonic_s']=f.pre_bridge['request']['graceful_deadline_monotonic_s']
                if mode=='nonfinite':f.pre_bridge['completed_monotonic_s']=float('nan')
                if mode=='boolean':f.pre_native['begin_perf_counter_ns']=True
                if mode=='duplicate':f.pre_order['stdin_close']*=2
                if mode=='lifecycle':f.pre_order['lifecycle'][-1]['phase']='unexpected'
                f.pre_native['bridge']=copy.deepcopy(f.pre_bridge)
                with self.assertRaises(ValueError):self.verify(f)

    def test_missing_declaration_or_source_hash_cannot_bypass(self):
        for mode in ('method','helper','changed'):
            with self.subTest(mode=mode):
                f=self.make()
                if mode=='method':del f.frozen['sources'][subject.METHOD]
                if mode=='helper':del f.frozen['sources'][subject.HELPER]
                if mode=='changed':(f.repo/subject.HELPER).write_bytes(b'changed')
                with self.assertRaises(ValueError):self.verify(f)

    def test_original_byte_gate_still_rejects(self):
        f=self.make();f.channels[0]['meters']['client_written']['bytes']+=1
        with self.assertRaises(ValueError):self.verify(f)

if __name__=='__main__':unittest.main()
