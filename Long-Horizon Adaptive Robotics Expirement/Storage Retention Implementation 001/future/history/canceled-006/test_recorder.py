import math
from pathlib import Path
import sqlite3
import tempfile
import unittest
import json
import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta

from recorder import Recorder, Reader, ImagePolicy, GatewayAdapter, RecordingFailure, pack, unpack, MAX_CONTAINER_BYTES
from admission import project, admit, CampaignReservations, verified_capacity, bind_qualification, load_bound_qualification, EXPECTED_EVIDENCE_ROOT, CAPACITY_SCOPE


class RecorderTests(unittest.TestCase):
    def setUp(self): self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()

    def test_serialized_future_adapter_worker_callbacks(self):
        from runtime_adapter import FutureEvidence
        evidence=FutureEvidence(self.root/'workers','workers')
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids=list(pool.map(lambda i:evidence.emit('worker',{'value':i},0.),range(10)))
        evidence.close(); reader=Reader(self.root/'workers')
        rows=list(reader.events()); self.assertEqual(sorted(ids),list(range(1,11)))
        self.assertEqual([r['event_id'] for r in rows],list(range(1,11))); reader.close()

    def test_binary_full_precision_and_types(self):
        value = {'v':[1,1.0,-0.0,math.nextafter(1.,2.),None,True,2**99,'é\n\u0000'], 'empty':[]}
        decoded = unpack(pack(value)); self.assertEqual(pack(value),pack(decoded))
        self.assertEqual(math.copysign(1,decoded['v'][2]),-1)
        with self.assertRaises(ValueError): pack(float('nan'))
        self.assertEqual(unpack(pack({'tuple':(1,2.5)})),{'tuple':[1,2.5]})

    def test_exact_json_text_recipe_and_canonical_telemetry_order(self):
        samples=[{'sequence':i,'sim_time_s':i*.01,'value':math.nextafter(i+.1,math.inf)} for i in range(100)]
        packet={'unicode':'é','telemetry_history':{'samples':samples},'content':'constant '*100}
        values=[packet]
        for options in ({},{'sort_keys':True,'separators':(',',':')},{'ensure_ascii':False,'indent':2}):
            values.append(' \n'+json.dumps(packet,**options)+'\r\n')
        # These legal JSON strings do not have a matching dump recipe; preserve
        # duplicate keys, escape choices, negative zero and irregular whitespace.
        values.extend(['{"a":1, "a":2,"padding":"'+'x'*600+'"}',
                       '{"a": -0, "padding":"'+'x'*600+'"}',
                       '{ "a" : "\\u0061", "padding":"'+'x'*600+'"}'])
        rec=Recorder(self.root/'json-text',run_id='json-text')
        for i,value in enumerate(values): rec.document(str(i),value)
        rec.close(); reader=Reader(self.root/'json-text')
        self.assertEqual([reader.document(str(i)) for i in range(len(values))],values)
        self.assertEqual(reader.db.execute('SELECT COUNT(*) FROM telemetry').fetchone()[0],100)
        reader.close()

    def test_bounded_dictionary_object_roundtrip(self):
        values=[]; rec=Recorder(self.root/'dictionary',run_id='dictionary')
        for i in range(3):
            value={str(j):hashlib.sha256(str(j).encode()).hexdigest() for j in range(150)}
            value['0']=str(i)+value['0']
            values.append(value);rec.document(str(i),value)
        rec.close(); reader=Reader(self.root/'dictionary')
        try:
            self.assertEqual([reader.document(str(i)) for i in range(3)],values)
            self.assertGreater(reader.db.execute("SELECT COUNT(*) FROM objects WHERE SUBSTR(payload,1,1)=x'44'").fetchone()[0],0)
        finally: reader.close()

    def test_nonfinite_and_noninteger_runtime_bounds_rejected(self):
        for key in ('sparse_period_s','representative_period_s','pre_s','post_s','representative_until_s',
                    'ring_bytes','ring_frames','image_quota_bytes','maximum_trigger_windows'):
            for value in (float('nan'),float('inf'),True,-1):
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                    ImagePolicy(**{key:value}).validate()
        for key in ('core_quota_bytes','flush_rows'):
            for value in (float('nan'),float('inf'),True,1.5,0):
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                    Recorder(self.root/'invalid',run_id='invalid',**{key:value})

    def test_sliding_exact_ranges_repeated_packets_and_files(self):
        rec = Recorder(self.root/'run',run_id='test')
        samples = [{'sequence':i,'sim_time_s':i*.01,'value':math.sin(i)} for i in range(150)]
        events=[]
        for i in (0,10,20,40,50,0):
            message={'packet':{'arm':{'telemetry_history':{'samples':samples[i:i+100]}}}}
            value={'event_id':len(events)+1,'event_type':'candidate_input','payload':{'message':message},
                   'wall_elapsed_s':3.2,'parent_ids':[1],'stale':True,'file':'model exact\r\n' * 1000}
            events.append(value); rec.event(value)
        # Reordering, explicit gaps, duplicated occurrence and stale delivery remain exact.
        value={'telemetry_history':{'samples':[samples[0],samples[2],samples[0]]}}
        rec.document('gapped',value); rec.document('protected',{'evaluator_truth':'never public'})
        rec.close(); reader=Reader(self.root/'run')
        self.assertEqual(list(reader.events()), events); self.assertEqual(reader.document('gapped'),value)
        self.assertEqual(reader.db.execute('SELECT COUNT(*) FROM telemetry').fetchone()[0],150)
        reader.close()

    def test_motion_every_bit_gap_and_extra_field(self):
        rec=Recorder(self.root/'run',run_id='test',flush_rows=3)
        rows=[{'sim_time_s':i*.01 if i<5 else i*.01+.12,'q':[math.nextafter(i+.1,math.inf)]*7,
               'custom':{'contact':False,'missing':None}} for i in range(10)]
        for row in rows: rec.motion(row)
        rec.close(); reader=Reader(self.root/'run')
        self.assertEqual(pack(list(reader.motion())),pack(rows)); reader.close()

    def test_policy_ring_trigger_pair_availability_and_package(self):
        policy=ImagePolicy(sparse_period_s=10,pre_s=2,post_s=2,ring_bytes=200,ring_frames=30,image_quota_bytes=200)
        rec=Recorder(self.root/'run',run_id='test',policy=policy)
        for i in range(31): rec.image(str(i),i*.1,b'rgb',b'depth')
        self.assertTrue(rec.trigger(3.,18,'failure'))
        for i in range(31,61): rec.image(str(i),i*.1,b'rgb',b'depth')
        self.assertLessEqual(rec.ring_size,policy.ring_bytes); rec.close()
        reader=Reader(self.root/'run'); self.assertEqual(reader.image('0')['status'],'available')
        self.assertEqual(reader.image('5')['status'],'unavailable_by_policy')
        self.assertEqual(reader.image('15')['rgb'],b'rgb')
        self.assertEqual(reader.image('15')['depth'],b'depth')
        package=reader.package(self.root/'package',['0','5','15'])
        self.assertEqual(package[1]['status'],'unavailable_by_policy'); reader.close()

    def test_quota_stop_and_failed_reader(self):
        rec=Recorder(self.root/'run',run_id='test',core_quota_bytes=4096)
        with self.assertRaises(RecordingFailure):
            for i in range(1000): rec.event({'i':i})
        rec.close(); self.assertTrue((self.root/'run'/'RECORDING_FAILED.json').exists())
        with self.assertRaises(RecordingFailure): Reader(self.root/'run')

    def test_document_utf8_bytes_cannot_bypass_core_quota(self):
        rec=Recorder(self.root/'long-name',run_id='test',core_quota_bytes=100_000,
                     policy=ImagePolicy(image_quota_bytes=0))
        with self.assertRaises(RecordingFailure): rec.document('😀'*80_000,{'v':1})
        rec.close()
        with self.assertRaises(RecordingFailure): Reader(self.root/'long-name')

    def test_no_evaluator_leak_exact_send_and_timing(self):
        rec=Recorder(self.root/'run',run_id='test'); adapter=GatewayAdapter(rec)
        rec.event({'event_type':'scoring','payload':{'secret':123}})
        message={'packet':{'public':1},'delivery_time':1.25}; sent=[]
        event={'event_type':'candidate_input','wall_elapsed_s':1.25,'payload':{'message':message}}
        adapter.record_public_and_send(event,message,sent.append)
        self.assertIs(sent[0],message); self.assertEqual(sent,[message]); self.assertNotIn('secret',str(sent))
        rec.close(); reader=Reader(self.root/'run'); self.assertEqual(list(reader.events())[1],event); reader.close()

    def test_corruption_is_distinct_from_policy(self):
        rec=Recorder(self.root/'run',run_id='test'); rec.image('a',0,b'rgb',b'depth'); rec.close()
        packed=self.root/'run'/'evidence.sqlite.gz'; data=bytearray(packed.read_bytes()); data[-10]^=1; packed.write_bytes(data)
        with self.assertRaises(RecordingFailure): Reader(self.root/'run')

    def test_finalized_container_exact_memory_restore_and_failure_boundaries(self):
        from unittest.mock import patch
        rec=Recorder(self.root/'packed',run_id='packed'); value={'precise':math.nextafter(2.,3.),'negative_zero':-0.0}
        rec.event(value); rec.close()
        self.assertFalse((self.root/'packed'/'evidence.sqlite').exists())
        before=set((self.root/'packed').iterdir()); reader=Reader(self.root/'packed')
        self.assertEqual(pack(list(reader.events())),pack([value])); reader.close()
        self.assertEqual(set((self.root/'packed').iterdir()),before)
        manifest=self.root/'packed'/'container-manifest.json'; content=json.loads(manifest.read_text())
        content['uncompressed_bytes']=MAX_CONTAINER_BYTES+1; manifest.write_text(json.dumps(content))
        with self.assertRaises(RecordingFailure): Reader(self.root/'packed')
        rec=Recorder(self.root/'pack-failure',run_id='pack-failure'); rec.event(value)
        with patch('recorder.gzip.GzipFile',side_effect=OSError('simulated disk failure')):
            with self.assertRaises(RecordingFailure): rec.close()
        self.assertTrue((self.root/'pack-failure'/'RECORDING_FAILED.json').exists())
        self.assertFalse((self.root/'pack-failure'/'container-manifest.json').exists())

    def test_required_representative_window_cannot_silently_truncate(self):
        rec=Recorder(self.root/'run',run_id='test',representative=True,
                     policy=ImagePolicy(image_quota_bytes=1))
        with self.assertRaises(RecordingFailure): rec.image('0',0,b'rgb',b'depth')
        rec.close()

    def test_restart_missing_model_and_checkpoint_semantics(self):
        rec=Recorder(self.root/'run',run_id='restart')
        events=[{'event_id':1,'event_type':'candidate_input','payload':{'message':{'packet':None,'missing_reason':'delayed'}},'parent_ids':[]},
            {'event_id':2,'event_type':'checkpoint','payload':{'path':'state.json','content':'{"action":"pending"}\n'},'parent_ids':[1]},
            {'event_id':3,'event_type':'runtime_restart','payload':{'incarnation':2,'ambiguous_action':True,'retained_files':['state.json']},'parent_ids':[2]},
            {'event_id':4,'event_type':'model_response','payload':{'stale':True,'reply':'exact response\r\n'},'parent_ids':[1]}]
        for event in events: rec.event(event)
        rec.close(); reader=Reader(self.root/'run'); self.assertEqual(pack(list(reader.events())),pack(events)); reader.close()

    def test_admission_measured_projection_and_three_ceiling_gates(self):
        projection=project([{'database_core_bytes':100000,'task_seconds':10}])
        qual={k:True for k in ['semantic_exact','diagnostics_equivalent','continuity_equivalent',
            'image_policy_qualified','runtime_timing_qualified','frozen_release_bound']}
        self.assertTrue(admit(projection,evidence_bytes=100_000_000_000,free_bytes=200_000_000_000,qualification=qual)['admitted'])
        self.assertFalse(admit(projection,evidence_bytes=149_000_000_000,free_bytes=200_000_000_000,qualification=qual)['admitted'])
        self.assertFalse(admit(projection,evidence_bytes=0,free_bytes=110_000_000_000,qualification=qual)['admitted'])
        self.assertFalse(admit(projection,evidence_bytes=0,free_bytes=300_000_000_000,qualification={})['admitted'])
        huge=project([{'database_core_bytes':10_000_000,'task_seconds':10}])
        self.assertFalse(admit(huge,evidence_bytes=0,free_bytes=999_000_000_000,qualification=qual)['admitted'])
        for invalid in (-500_000_000_000,float('nan'),float('inf'),True):
            with self.assertRaises(ValueError): admit(projection,evidence_bytes=200_000_000_000,
                free_bytes=10_000_000_000,qualification=qual,outstanding_reserved_bytes=invalid)

    def test_campaign_aggregate_and_trigger_caps(self):
        ledger=CampaignReservations(self.root/'budget.sqlite',core_bytes=100,image_bytes=50,trigger_windows=2)
        ledger.allocate('a',core_bytes=60,image_bytes=30,trigger_windows=2)
        with self.assertRaises(ValueError): ledger.allocate('b',core_bytes=30,image_bytes=10,trigger_windows=1)
        with self.assertRaises(ValueError): ledger.allocate('c',core_bytes=41,image_bytes=0,trigger_windows=0)
        ledger.allocate('d',core_bytes=40,image_bytes=20,trigger_windows=0); ledger.close()

    def test_fresh_capacity_and_tamper_or_staleness_refusal(self):
        path=self.root/'census.json'
        census={'schema_version':'storage-capacity-census-1','observed_at':datetime.now(timezone.utc).isoformat(),
                'evidence_bytes':123,'evidence_root':str(EXPECTED_EVIDENCE_ROOT),'scope_policy':CAPACITY_SCOPE}
        path.write_text(json.dumps(census))
        spec={'evidence_census':{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()},
              'output_directory':str(EXPECTED_EVIDENCE_ROOT),'free_bytes':99999999999999}
        value=verified_capacity(spec); self.assertEqual(value['evidence_bytes'],123)
        self.assertNotEqual(value['free_bytes'],spec['free_bytes'])
        census['observed_at']=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()
        path.write_text(json.dumps(census))
        with self.assertRaises(ValueError): verified_capacity(spec)
        spec['evidence_census']['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaises(ValueError): verified_capacity(spec)

    def test_qualification_hash_binding_refuses_changed_code(self):
        source=self.root/'recorder.py'; source.write_text('original')
        report=self.root/'qualification.json'; receipt=self.root/'receipt.json'; seal=self.root/'binding.json'
        now=datetime.now(timezone.utc)
        contents={'schema_version':'future-recorder-qualification-1','tests':{'passed':True,'run':1},
            'created_at':now.isoformat(),'generation':'fixture',
            'implementation_hashes':{'recorder.py':hashlib.sha256(source.read_bytes()).hexdigest()}}
        report.write_text(json.dumps(contents))
        official={'state':'succeeded','exit_status':0,'id':'test','cwd':str(EXPECTED_EVIDENCE_ROOT.parent),
            'started_at':(now-timedelta(seconds=1)).isoformat(),'ended_at':(now+timedelta(seconds=1)).isoformat(),
            'argv':['python','-B',str(Path(__file__).resolve().parent/'qualify.py'),'--generation','fixture']}
        receipt.write_text(json.dumps(official))
        bind_qualification(report,receipt,seal); load_bound_qualification(report,receipt,seal)
        for patch in ({'argv':['python','optimize.py','--generation','fixture']},
                      {'argv':official['argv'][:-1]+['other']}, {'cwd':str(self.root)},
                      {'ended_at':(now-timedelta(seconds=2)).isoformat()}, {'exit_status':False}):
            receipt.write_text(json.dumps({**official,**patch}))
            with self.assertRaises(ValueError): bind_qualification(report,receipt,seal)
        receipt.write_text(json.dumps(official))
        source.write_text('changed')
        with self.assertRaises(ValueError): load_bound_qualification(report,receipt,seal)


if __name__=='__main__': unittest.main()
