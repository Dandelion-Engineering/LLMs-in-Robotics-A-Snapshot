import asyncio
import hashlib
import io
import json
from pathlib import Path
import struct
import unittest
import zipfile
import types

import codehost_mux_protocol as m


def h2(kind, flags=0, stream=0, payload=b''):
    return len(payload).to_bytes(3,'big') + bytes([kind,flags]) + stream.to_bytes(4,'big') + payload


class CleanupH2Tests(unittest.TestCase):
    nonce = '0123456789abcdef' * 2

    def ready(self):
        w=m.H2Witness();w.feed('upload',m.PREFACE+h2(4));w.feed('download',h2(4));return w

    def opened(self, w, stream=1):
        w.feed('upload',h2(1,5,stream,b'x'));return w

    def cancel(self, w, stream=1, width=13):
        wire=h2(3,0,stream,(8).to_bytes(4,'big'))
        for n in range(0,len(wire),width):w.feed('upload',wire[n:n+width])

    def canonical_row(self, w):
        row=w.summary()['cleanup_cancel_records'][0]
        return {k:v for k,v in row.items() if k!='local'}

    def test_owner_controls_require_nonempty_canonical_metadata(self):
        for kind in (m.CLEANUP_BEGIN,m.CLEANUP_ACK):
            payload=m.canonical({'nonce':self.nonce});wire=m.encode_frame(kind,0,payload)
            p=m.FrameParser();out=[]
            for b in wire:out+=p.feed(bytes([b]))
            p.finish();self.assertEqual(out,[(kind,0,payload)])
            for channel,data in ((1,payload),(0,b''),(0,b'[]'),(0,b'{ "x": 1 }'),(0,b'\xff')):
                with self.subTest(kind=kind,channel=channel,data=data),self.assertRaises((ValueError,UnicodeError)):
                    m.encode_frame(kind,channel,data)
            p=m.FrameParser()
            with self.assertRaises(ValueError):p.feed(m.HEADER.pack(m.MAGIC,3,kind,0,2)+b'[]')

    def test_begin_detached_nonce_once_and_empty_inheritance(self):
        w=self.opened(self.ready());before=w.begin_cleanup(self.nonce)
        self.assertIsNone(before['cleanup_phase_nonce']);self.assertEqual(before['active_stream_ids'],[1])
        before['active_stream_ids'].clear();self.assertEqual(w.summary()['active_stream_ids'],[1])
        for nonce in (self.nonce,'A'*32,'x','',None,1):
            with self.assertRaises(ValueError):w.begin_cleanup(nonce)
        empty=m.H2Witness();front=empty.begin_cleanup(self.nonce)
        self.assertEqual(front['bytes'],{'upload':0,'download':0})
        empty.feed('upload',m.PREFACE+h2(4)+h2(1,5,1,b'x'));empty.feed('download',h2(4))
        self.cancel(empty);self.assertEqual(empty.summary()['cleanup_cancel_records'][0]['local']['eligibility'],'opened_during_phase')

    def test_active_record_exact_wire_positions_and_trace(self):
        w=self.opened(self.ready());w.begin_cleanup(self.nonce);self.cancel(w,width=1)
        r=w.summary()['cleanup_cancel_records'][0]
        self.assertEqual(r['cancel'],{'direction':'upload','type':3,'flags':0,'payload_length':4,
            'error_code':8,'frame':3,'start_byte':43,'end_byte':56,
            'sha256':hashlib.sha256(h2(3,0,1,(8).to_bytes(4,'big'))).hexdigest()})
        trace=hashlib.sha256()
        for ordinal,start,frame in ((2,33,h2(1,5,1,b'x')),(3,43,h2(3,0,1,(8).to_bytes(4,'big')))):
            trace.update(m.canonical({'direction':'upload','type':frame[3],'flags':frame[4],
                'stream_id':1,'payload_length':len(frame)-9,'frame':ordinal,'start_byte':start,
                'end_byte':start+len(frame),'sha256':hashlib.sha256(frame).hexdigest()})+b'\n')
        self.assertEqual(r['wire']['upload'],{'frames':2,'bytes':23,'sha256':trace.hexdigest()})
        self.assertEqual(r['opened_upload'],{'frame':2,'start_byte':33,'end_byte':43})
        self.assertEqual(r['opening_headers_complete'],{'frame':2,'end_byte':43})
        self.assertEqual(r['upload_end_stream'],r['upload_headers_complete'])
        self.assertEqual(r['local']['reset_record_index'],0);self.assertIsNone(r['local']['terminal_control_index'])
        w.validate_reset_scope();w.begin_retirement();w.validate_reset_scope()
        self.assertEqual(w.summary()['reset_records'],[{'direction':'upload','stream_id':1,'error_code':8}])
        self.assertEqual(w.idle_eof()['reset_streams'],1)

    def test_mixed_classification_both_endpoint_orientations_preserve_raw_counts(self):
        for normal_first in (True,False):
            a,b=self.opened(self.ready()),self.opened(self.ready())
            a.begin_cleanup(self.nonce);b.begin_cleanup(self.nonce)
            response=h2(1,5,1,b'y')
            active,normal=(b,a) if normal_first else (a,b)
            normal.feed('download',response);self.cancel(normal)
            self.cancel(active);active.feed('download',response)
            self.assertEqual(self.canonical_row(a),self.canonical_row(b))
            sa,sn=active.summary(),normal.summary()
            self.assertEqual((sa['reset_streams'],sa['closed_streams']),(1,0))
            self.assertEqual((sn['reset_streams'],sn['closed_streams']),(0,1))
            self.assertEqual(len(sn['terminal_control_records']),1)
            self.assertEqual(sa['closed_streams'],sn['closed_streams']-1)
            self.assertEqual(sa['reset_streams']-1,sn['reset_streams'])
            self.assertEqual(sa['active_stream_ids'],sn['active_stream_ids'])

    def test_normally_closed_before_begin_and_post_final_counterpart(self):
        a,b=self.opened(self.ready()),self.opened(self.ready())
        response=h2(1,5,1,b'y');b.feed('download',response)
        a.begin_cleanup(self.nonce);b.begin_cleanup(self.nonce)
        a.begin_retirement();b.begin_retirement()
        self.cancel(a);self.cancel(b);a.feed('download',response)
        self.assertEqual(self.canonical_row(a),self.canonical_row(b))
        self.assertEqual(b.summary()['cleanup_cancel_records'][0]['local']['eligibility'],'proved_normal_close')

    def test_late_fragmented_headers_and_continuation_reconcile(self):
        response=h2(1,1,1,b'abc')+h2(9,4,1,b'def')
        for cut in (0,1,8,10,12,13,20):
            a,b=self.opened(self.ready()),self.opened(self.ready())
            a.begin_cleanup(self.nonce);b.begin_cleanup(self.nonce)
            a.feed('download',response[:cut]);b.feed('download',response)
            self.cancel(a);self.cancel(b)
            for byte in response[cut:]:a.feed('download',bytes([byte]))
            self.assertEqual(self.canonical_row(a),self.canonical_row(b))
            r=self.canonical_row(a)
            self.assertEqual(r['download_end_stream'],{'frame':2,'end_byte':21})
            self.assertEqual(r['download_headers_complete'],{'frame':3,'end_byte':33})
            self.assertTrue(a.summary()['headers_complete'])

    def test_late_data_controls_and_tombstone_trace_are_bounded_payload_free(self):
        a,b=self.opened(self.ready()),self.opened(self.ready())
        for w in (a,b):
            w.feed('upload',h2(4,payload=b'\x00\x05'+(1048576).to_bytes(4,'big')))
            w.begin_cleanup(self.nonce);w.feed('download',h2(1,4,1,b'x'))
        tail=h2(0,1,1,b'PRIVATE'*20000)+h2(8,0,1,(1).to_bytes(4,'big'))
        b.feed('download',tail);self.cancel(b);self.cancel(a)
        for pos in range(0,len(tail),101):a.feed('download',tail[pos:pos+101])
        self.assertEqual(self.canonical_row(a),self.canonical_row(b))
        self.assertNotIn('PRIVATE',json.dumps(a.summary()))
        self.assertLess(len(json.dumps(a.summary())),5000)
        self.assertEqual(a.summary()['closed_streams'],0)

    def test_phase_born_streams_and_exact_final_new_stream_gate(self):
        w=self.ready();w.begin_cleanup(self.nonce);self.opened(w,1);self.cancel(w,1)
        self.opened(w,3);front=w.begin_retirement();self.cancel(w,3)
        self.assertEqual(front['active_stream_ids'],[3]);w.validate_reset_scope(front)
        self.assertTrue(all(r['local']['eligibility']=='opened_during_phase' for r in w.summary()['cleanup_cancel_records']))
        with self.assertRaisesRegex(ValueError,'new stream after retirement'):self.opened(w,5)

    def test_partial_opening_header_or_block_crossing_begin_cannot_gain_permission(self):
        frame=h2(1,5,1,b'x')
        for cut in range(1,len(frame)):
            w=self.ready();w.feed('upload',frame[:cut]);w.begin_cleanup(self.nonce);w.feed('upload',frame[cut:])
            with self.assertRaisesRegex(ValueError,'opening crosses phase'):self.cancel(w)
        w=self.ready();w.feed('upload',h2(1,1,1,b'x'));w.begin_cleanup(self.nonce)
        w.feed('upload',h2(9,4,1,b'x'))
        with self.assertRaisesRegex(ValueError,'opening crosses phase'):self.cancel(w)

    def test_reset_fragments_cannot_cross_begin_or_final_frontier(self):
        wire=h2(3,0,1,(8).to_bytes(4,'big'))
        for cut in range(1,len(wire)):
            w=self.opened(self.ready());w.feed('upload',wire[:cut]);w.begin_cleanup(self.nonce)
            with self.assertRaisesRegex(ValueError,'outside cleanup phase'):w.feed('upload',wire[cut:])
            w=self.opened(self.ready());w.begin_cleanup(self.nonce);w.feed('upload',wire[:cut]);w.begin_retirement()
            with self.assertRaisesRegex(ValueError,'original retirement frontier'):w.feed('upload',wire[cut:])

    def test_no_phase_reset_and_bad_or_missing_phase_remain_fail_closed(self):
        w=self.opened(self.ready());self.cancel(w)
        with self.assertRaises(ValueError):w.validate_reset_scope()
        with self.assertRaises(ValueError):w.begin_cleanup(self.nonce)
        with self.assertRaises(ValueError):w.begin_retirement()
        for direction,stream,code in (('download',1,8),('upload',1,0),('upload',3,8)):
            w=self.opened(self.ready());w.begin_cleanup(self.nonce)
            with self.assertRaises(ValueError):w.feed(direction,h2(3,0,stream,code.to_bytes(4,'big')))

    def test_duplicate_and_illegal_tails_do_not_reopen_or_hide_errors(self):
        tails=[('upload',h2(3,0,1,(8).to_bytes(4,'big'))),('upload',h2(1,5,1,b'x')),
               ('upload',h2(0,1,1,b'x')),('download',h2(0,1,1,b'x')),
               ('download',h2(9,4,1,b'x')),('download',h2(1,13,1,b'\xff')),
               ('download',h2(1,5,3,b'x'))]
        for direction,tail in tails:
            w=self.opened(self.ready());w.begin_cleanup(self.nonce);self.cancel(w)
            with self.subTest(direction=direction,tail=tail),self.assertRaises(ValueError):w.feed(direction,tail)
            self.assertEqual(w.summary()['reset_streams'],1)
        w=self.opened(self.ready());w.begin_cleanup(self.nonce);self.cancel(w)
        w.feed('download',h2(1,5,1,b'x'))
        with self.assertRaises(ValueError):w.feed('download',h2(0,1,1,b'x'))

    def test_partial_tail_header_fails_final_completeness_and_idle(self):
        w=self.opened(self.ready());w.begin_cleanup(self.nonce);self.cancel(w);w.begin_retirement()
        w.feed('download',h2(1,1,1,b'x'));self.assertFalse(w.summary()['headers_complete'])
        self.assertTrue(w.upload_eof()['upload_complete'])
        with self.assertRaises(ValueError):w.idle_eof()
        r=w.summary()['cleanup_cancel_records'][0]
        self.assertIsNone(r['download_headers_complete'])

    def test_coalesced_cancel_then_new_cleanup_stream_and_final_tail(self):
        w=self.opened(self.ready());w.begin_cleanup(self.nonce)
        w.feed('upload',h2(3,0,1,(8).to_bytes(4,'big'))+h2(1,5,3,b'new')+
               h2(3,0,3,(8).to_bytes(4,'big')))
        before=w.summary();w.begin_retirement()
        w.feed('download',h2(1,5,1,b'x')+h2(1,5,3,b'y'))
        final=w.summary();self.assertEqual(final['closed_streams'],0)
        self.assertEqual(final['reset_streams'],2)
        for old,new in zip(before['cleanup_cancel_records'],final['cleanup_cancel_records']):
            for field in ('cancel','opened_upload','local','phase_nonce','opening_headers_complete'):
                self.assertEqual(old[field],new[field])
            self.assertIsNone(old['download_end_stream']);self.assertIsNotNone(new['download_end_stream'])
            self.assertEqual(old['wire']['upload'],new['wire']['upload'])
            self.assertLess(old['wire']['download']['frames'],new['wire']['download']['frames'])
        self.assertEqual(w.idle_eof()['active_stream_ids'],[])

    def test_proof_summary_cap_fails_in_mux_without_truncation(self):
        w=self.ready();w.begin_cleanup(self.nonce)
        for stream in range(1,129,2):self.opened(w,stream);self.cancel(w,stream)
        payload=m.canonical(w.summary())
        self.assertGreater(len(payload),m.MAX_FRAME_BYTES)
        with self.assertRaisesRegex(ValueError,'Frame payload bound'):m.encode_frame(m.CLOSED,1,payload)
        self.assertEqual(len(w.summary()['cleanup_cancel_records']),64)

    def test_record_capacity_and_proof_eviction_are_explicit(self):
        w=self.ready();w.begin_cleanup(self.nonce)
        for stream in range(1,130,2):
            self.opened(w,stream)
            if stream<129:self.cancel(w,stream)
        self.assertEqual(len(w.summary()['cleanup_cancel_records']),64)
        with self.assertRaisesRegex(ValueError,'cancellation bound'):self.cancel(w,129)
        self.assertEqual(w.summary()['reset_streams'],64)
        w=self.ready()
        for stream in range(1,2*m.MAX_H2_STREAMS+2,2):
            self.opened(w,stream);w.feed('download',h2(1,5,stream,b'x'))
        w.begin_cleanup(self.nonce)
        with self.assertRaisesRegex(ValueError,'no opening proof'):self.cancel(w,1)

    def test_snapshots_detach_and_counter_scope_rejects_unexplained_index(self):
        w=self.opened(self.ready());w.begin_cleanup(self.nonce);self.cancel(w)
        before=w.summary();before['cleanup_cancel_records'][0]['cancel']['error_code']=0
        before['cleanup_cancel_records'][0]['local']['phase_frontier']['last_stream_id']=999
        self.assertEqual(w.summary()['cleanup_cancel_records'][0]['cancel']['error_code'],8)
        w.reset_records.append({'direction':'upload','stream_id':9,'error_code':8});w.resets+=1
        with self.assertRaises(ValueError):w.validate_reset_scope()
        with self.assertRaises(ValueError):w.begin_retirement()

    def test_idle_eof_requires_full_structure_no_live_streams_and_exact_reset_indices(self):
        w=self.opened(self.ready());w.begin_cleanup(self.nonce);self.cancel(w)
        self.assertEqual(w.idle_eof()['reset_streams'],1)
        self.opened(w,3)
        with self.assertRaises(ValueError):w.idle_eof()
        self.cancel(w,3);w.feed('download',h2(1,1,1,b'x'))
        with self.assertRaises(ValueError):w.idle_eof()
        w.feed('download',h2(9,4,1,b'x'));self.assertEqual(w.idle_eof()['reset_streams'],2)
        w.reset_records[1]['stream_id']=999
        with self.assertRaises(ValueError):w.idle_eof()

    def test_dev066_original_suite_and_differential_no_phase_behavior(self):
        archive=Path(__file__).resolve().parents[3]/'Architecture Map/releases/RCI001-C02-dev-066/code.zip'
        member='Long-Horizon Adaptive Robotics Expirement/Robot-Codex Integration 001/campaign-002/harness/'
        with zipfile.ZipFile(archive) as z:
            source=z.read(member+'codehost_mux_protocol.py')
            original_tests=z.read(member+'test_codehost_mux_protocol.py')
        self.assertEqual(hashlib.sha256(source).hexdigest(),'557337234c109e364b3ccce717da553ad31d69a90bc750ca0b33ebb2a85db75a')
        old=types.ModuleType('dev066_mux');exec(compile(source,'dev066_mux.py','exec'),old.__dict__)
        test_module=types.ModuleType('dev066_tests');exec(compile(original_tests,'dev066_tests.py','exec'),test_module.__dict__)
        for producer in (old,m):
            test_module.m=producer
            result=unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromModule(test_module))
            self.assertEqual(result.testsRun,36);self.assertTrue(result.wasSuccessful(),result.errors+result.failures)
        def run(producer,case,width):
            w=producer.H2Witness();events=[]
            for direction,data in case:
                pieces=[data[n:n+width] for n in range(0,len(data),width)] if direction!='retire' else [None]
                for piece in pieces:
                    try:
                        if direction=='retire':w.begin_retirement()
                        else:w.feed(direction,piece)
                    except Exception as error:
                        events.append((type(error).__name__,str(error)))
                        return events,strip(w.summary())
            return events,strip(w.summary())
        def strip(value):
            value.pop('cleanup_phase_nonce',None);value.pop('cleanup_cancel_records',None);return value
        prefix=[('upload',m.PREFACE+h2(4)+h2(1,5,1,b'x')),('download',h2(4))]
        cases=[prefix,
            prefix+[('download',h2(1,5,1,b'y')),('upload',h2(3,0,1,(8).to_bytes(4,'big')))],
            prefix+[('upload',h2(3,0,1,(8).to_bytes(4,'big')))],
            prefix+[('download',h2(3,0,1,(0).to_bytes(4,'big')))],
            prefix+[('retire',None),('upload',h2(3,0,1,(8).to_bytes(4,'big')))],
            prefix+[('retire',None),('upload',h2(1,5,3,b'x'))],
            prefix+[('download',h2(1,1,1,b'y')+h2(9,4,1,b'z'))],
            prefix+[('download',h2(0,1,1,b'y'))],
            prefix+[('upload',h2(3,0,3,(8).to_bytes(4,'big')))],
            prefix+[('download',h2(1,5,1,b'y')),('upload',h2(1,5,1,b'x'))]]
        for width in (1,3,13,65536):
            for index,case in enumerate(cases):
                with self.subTest(width=width,index=index):self.assertEqual(run(old,case,width),run(m,case,width))


class FramingTests(unittest.TestCase):
    def test_fragmented_and_coalesced_frames(self):
        expected = [(m.OPEN,1,b''),(m.DATA,1,b'opaque\x00\xff'),(m.HALF_CLOSE,1,b''),(m.FINISH,0,b'')]
        wire=b''.join(m.encode_frame(*v) for v in expected)
        for width in (1,3,14,17,len(wire)):
            parser=m.FrameParser(); actual=[]
            for offset in range(0,len(wire),width): actual.extend(parser.feed(wire[offset:offset+width]))
            parser.finish(); self.assertEqual(actual,expected)

    def test_header_and_payload_bounds_before_buffering(self):
        for header in (m.HEADER.pack(b'BAD!',3,m.DATA,1,5),m.HEADER.pack(m.MAGIC,4,m.DATA,1,5),
                       m.HEADER.pack(m.MAGIC,3,99,1,0),m.HEADER.pack(m.MAGIC,3,m.DATA,1,65537)):
            with self.assertRaises(ValueError):m.FrameParser().feed(header)
        for args in ((m.OPEN,0,b''),(m.FINISH,1,b''),(m.OPEN,1,b'x'),(m.DATA,1,b''),
                     (m.DATA,17,b'x'),(m.FINISH,False,b'')):
            with self.assertRaises(ValueError):m.encode_frame(*args)

    def test_partial_eof(self):
        wire=m.encode_frame(m.DATA,1,b'abc')
        for end in range(1,len(wire)):
            parser=m.FrameParser();parser.feed(wire[:end])
            with self.assertRaises(ValueError):parser.finish()

    def test_metadata_no_ambiguous_encoding(self):
        self.assertEqual(m.metadata(m.canonical({'a':1})),{'a':1})
        for raw in (b'{"a":1,"a":2}',b'[]',b'{ "a": 1 }',b'\xff'):
            with self.assertRaises((ValueError,UnicodeError)):m.metadata(raw)

    def test_queue_limits_and_release(self):
        b=m.QueueBudget()
        capacity=m.PER_CHANNEL_QUEUE_BYTES-b.headroom_bytes
        for c in range(1,5):b.reserve(c,capacity)
        b.reserve(5,3*b.headroom_bytes)
        with self.assertRaises(ValueError):b.reserve(5,1)
        with self.assertRaises(ValueError):b.reserve(1,1)
        b.release(1,capacity);b.reserve(6,capacity)
        self.assertEqual(b.total+b.headroom_bytes,m.AGGREGATE_QUEUE_BYTES)
        self.assertTrue(all(v+b.headroom_bytes<=m.PER_CHANNEL_QUEUE_BYTES for v in b.channel_maximum.values()))
        with self.assertRaises(ValueError):b.release(1,1)


class AsyncFramingTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_eof_and_partial(self):
        reader=asyncio.StreamReader();reader.feed_data(m.encode_frame(m.OPEN,1));reader.feed_eof()
        self.assertEqual(await m.read_frame(reader),(m.OPEN,1,b''));self.assertIsNone(await m.read_frame(reader))
        for raw in (b'RC',m.encode_frame(m.DATA,1,b'abc')[:-1]):
            reader=asyncio.StreamReader();reader.feed_data(raw);reader.feed_eof()
            with self.assertRaises(ValueError):await m.read_frame(reader)


class H2Tests(unittest.TestCase):
    def ready(self):
        witness=m.H2Witness();witness.feed('upload',m.PREFACE+h2(4));witness.feed('download',h2(4));return witness

    def test_fragmented_lifecycle_and_idle_eof(self):
        w=m.H2Witness()
        for b in m.PREFACE+h2(4)+h2(1,5,1,b'\x82'):w.feed('upload',bytes([b]))
        for b in h2(4)+h2(1,4,1,b'\x88')+h2(0,1,1,b'payload'):w.feed('download',bytes([b]))
        self.assertEqual(w.idle_eof()['closed_streams'],1)

    def test_large_data_is_not_buffered(self):
        w=self.ready();w.feed('upload',h2(4,payload=b'\x00\x05'+(1048576).to_bytes(4,'big')))
        w.feed('upload',h2(1,5,1,b'\x82'));w.feed('download',h2(1,4,1,b'\x88'))
        wire=h2(0,1,1,b'x'*500000)
        for pos in range(0,len(wire),32768):
            w.feed('download',wire[pos:pos+32768])
            self.assertLessEqual(len(w.directions['download']['buffer']),9)
            if w.directions['download']['frame']:self.assertLessEqual(len(w.directions['download']['frame']['prefix']),8)
        self.assertEqual(w.idle_eof()['open_streams'],0)

    def test_live_lease_and_partial_frames_are_not_idle(self):
        w=self.ready();w.feed('upload',h2(1,5,1,b'\x82'));w.feed('download',h2(1,4,1,b'\x88'))
        self.assertEqual(w.summary()['active_stream_ids'],[1])
        with self.assertRaises(ValueError):w.idle_eof()
        for raw in (m.PREFACE[:5],m.PREFACE+h2(4)+h2(1,5,1,b'\x82')[:-1]):
            v=m.H2Witness();v.feed('upload',raw)
            with self.assertRaises(ValueError):v.idle_eof()

    def test_header_continuation_boundary(self):
        w=self.ready();w.feed('upload',h2(1,1,1,b'\x82'))
        with self.assertRaises(ValueError):w.idle_eof()
        w.feed('upload',h2(9,4,1,b'x'));w.feed('download',h2(1,5,1,b'\x88'))
        self.assertEqual(w.idle_eof()['closed_streams'],1)
        w=self.ready();w.feed('upload',h2(1,0,1,b'x'))
        with self.assertRaises(ValueError):w.feed('upload',h2(6,payload=b'12345678'))

    def test_rst_is_retained_never_idle_success(self):
        w=self.ready();w.feed('upload',h2(1,5,1,b'x'));w.feed('download',h2(3,0,1,(8).to_bytes(4,'big')))
        self.assertEqual(w.summary()['reset_records'],[{'direction':'download','stream_id':1,'error_code':8}])
        with self.assertRaises(ValueError):w.idle_eof()
        with self.assertRaises(ValueError):w.feed('download',h2(3,0,1,(8).to_bytes(4,'big')))

    def test_malformed_and_unknown_forms_fail_closed(self):
        cases=[h2(5,0,1,b''),h2(99),h2(6,payload=b'bad'),h2(4,payload=b'x'),
               h2(4,2),h2(8,payload=b'\0'*4),h2(7,payload=b'\0'*4+(1).to_bytes(4,'big')),
               h2(0,1,1,b'x'),h2(1,5,2,b'x'),h2(1,13,1,b'\xff')]
        for wire in cases:
            w=self.ready()
            with self.subTest(wire=wire),self.assertRaises(ValueError):w.feed('upload',wire)
            self.assertIsNotNone(w.summary()['error'])

    def test_reused_stream_and_state_bound(self):
        w=self.ready();w.feed('upload',h2(1,5,1,b'x'));w.feed('download',h2(1,5,1,b'y'))
        with self.assertRaises(ValueError):w.feed('upload',h2(1,5,1,b'x'))
        w=self.ready()
        for index in range(m.MAX_H2_STREAMS):w.feed('upload',h2(1,5,index*2+1,b'x'))
        with self.assertRaises(ValueError):w.feed('upload',h2(1,5,m.MAX_H2_STREAMS*2+1,b'x'))

    def test_retirement_rejects_new_stream_even_if_it_would_close_in_same_read(self):
        w=self.ready();front=w.begin_retirement()
        self.assertEqual(front['last_stream_id'],0)
        with self.assertRaises(ValueError):w.feed('upload',h2(1,5,1,b'x')+h2(3,0,1,(8).to_bytes(4,'big')))
        self.assertIsNotNone(w.summary()['error'])

    def test_retirement_cancel_fragmentation_and_original_frontier(self):
        for width in (1,3,13):
            w=self.ready();w.feed('upload',h2(1,5,1,b'x'))
            front=w.begin_retirement()
            wire=h2(3,0,1,(8).to_bytes(4,'big'))
            for offset in range(0,len(wire),width):w.feed('download',wire[offset:offset+width])
            self.assertEqual(front['active_stream_ids'],[1]);self.assertEqual(front['reset_records'],[])
            self.assertEqual(w.summary()['last_stream_id'],1)
            self.assertTrue(w.summary()['frames_complete']);self.assertEqual(w.summary()['open_streams'],0)
            with self.assertRaises(ValueError):w.begin_retirement()

    def test_rejection_distinguishes_higher_id_from_original_reset_reuse(self):
        for stream,member in ((15,False),(13,True)):
            for width in (1,8,9,13,100):
                with self.subTest(stream=stream,width=width):
                    w=self.ready();w.feed('upload',h2(1,4,13,b'initial'))
                    frontier=w.begin_retirement()
                    cancel=h2(3,0,13,(8).to_bytes(4,'big'))
                    rejected=h2(1,5,stream,b'opaque-header-value')
                    wire=cancel+rejected+h2(1,5,17,b'not-parsed')
                    with self.assertRaisesRegex(ValueError,'^HTTP/2 new stream after retirement$'):
                        for offset in range(0,len(wire),width):w.feed('upload',wire[offset:offset+width])
                    self.assertEqual(w.summary()['first_rejection'],{
                        'schema':'campaign002-h2-rejection-1','direction':'upload',
                        'frame_type':1,'flags':5,'stream_id':stream,
                        'payload_length':len(b'opaque-header-value'),
                        'active_at_rejection':False,'in_original_frontier':member,
                        'original_last_stream_id':13})
                    self.assertEqual(w.summary()['active_stream_ids'],[])
                    self.assertEqual(w.summary()['last_stream_id'],13)
                    self.assertEqual(w.summary()['reset_records'],[
                        {'direction':'upload','stream_id':13,'error_code':8}])
                    self.assertNotIn('first_rejection',frontier)

    def test_first_rejection_is_bounded_detached_and_payload_free(self):
        w=self.ready();w.feed('upload',h2(1,4,1,b'initial'));w.begin_retirement()
        secret=b'private-header-value-'*700
        with self.assertRaisesRegex(ValueError,'^HTTP/2 new stream after retirement$'):
            w.feed('upload',h2(1,5,3,secret))
        snapshot=w.summary();first=dict(snapshot['first_rejection'])
        retained=m.canonical(first)
        self.assertLess(len(retained),384)
        self.assertNotIn(b'private-header-value',retained)
        self.assertTrue(all(type(v) in (str,int,bool) for v in first.values()))
        before=(w.summary()['bytes'],w.summary()['frames'])
        snapshot['first_rejection']['stream_id']=999
        for _ in range(20):
            with self.assertRaisesRegex(ValueError,'^HTTP/2 new stream after retirement$'):
                w.feed('upload',h2(1,5,5,b'different'))
        self.assertEqual(w.summary()['first_rejection'],first)
        self.assertEqual((w.summary()['bytes'],w.summary()['frames']),before)

    def test_rejection_metadata_absent_for_success_and_other_failures(self):
        w=self.ready();w.feed('upload',h2(1,5,1,b'x'));w.feed('download',h2(1,5,1,b'y'))
        self.assertNotIn('first_rejection',w.idle_eof())
        w.begin_retirement();w.feed('upload',h2(7,payload=b'\0'*8))
        self.assertNotIn('first_rejection',w.idle_eof())
        other=self.ready()
        with self.assertRaisesRegex(ValueError,'^HTTP/2 DATA on unavailable stream$'):
            other.feed('upload',h2(0,1,1,b'opaque'))
        self.assertNotIn('first_rejection',other.summary())

    def test_unavailable_reset_distinguishes_normal_reset_and_unknown_history(self):
        for stream,normal,reset in ((1,True,False),(3,False,True),(5,False,False)):
            for direction in ('upload','download'):
                for width in (1,8,9,13,100):
                    with self.subTest(stream=stream,direction=direction,width=width):
                        w=self.ready()
                        w.feed('upload',h2(1,5,1,b'x'))
                        w.feed('download',h2(1,5,1,b'y'))
                        w.feed('upload',h2(1,4,3,b'x'))
                        w.feed('download',h2(3,0,3,(8).to_bytes(4,'big')))
                        wire=h2(6,payload=b'12345678')+h2(3,0,stream,(0xffffffff).to_bytes(4,'big'))+h2(6,payload=b'abcdefgh')
                        with self.assertRaisesRegex(ValueError,'^HTTP/2 reset on unavailable stream$'):
                            for offset in range(0,len(wire),width):w.feed(direction,wire[offset:offset+width])
                        self.assertEqual(w.summary()['first_rejection'],{
                            'schema':'campaign002-h2-reset-rejection-1',
                            'direction':direction,'frame_type':3,'flags':0,
                            'stream_id':stream,'payload_length':4,'error_code':0xffffffff,
                            'active_at_rejection':False,'retiring':False,
                            'in_original_frontier':None,'original_last_stream_id':None,
                            'last_stream_id':3,'observed_normal_close':normal,
                            'observed_reset':reset,'normal_close_history_evicted':False})
                        self.assertEqual(w.summary()['reset_streams'],1)
                        self.assertEqual(w.summary()['closed_streams'],1)
                        self.assertEqual(w.summary()['active_stream_ids'],[])

    def test_reset_diagnostic_retirement_frontier_and_latched_first_record(self):
        w=self.ready();w.feed('upload',h2(1,4,1,b'x'));w.begin_retirement()
        w.feed('download',h2(3,0,1,(8).to_bytes(4,'big')))
        with self.assertRaisesRegex(ValueError,'^HTTP/2 reset on unavailable stream$'):
            w.feed('upload',h2(3,0,1,(2).to_bytes(4,'big')))
        summary=w.summary();first=dict(summary['first_rejection'])
        self.assertTrue(first['retiring']);self.assertTrue(first['in_original_frontier'])
        self.assertEqual(first['original_last_stream_id'],1)
        self.assertTrue(first['observed_reset']);self.assertEqual(first['error_code'],2)
        self.assertLess(len(m.canonical(first)),640)
        self.assertTrue(all(type(v) in (str,int,bool,type(None)) for v in first.values()))
        summary['first_rejection']['stream_id']=999
        before=(w.summary()['bytes'],w.summary()['frames'],w.summary()['reset_records'])
        for _ in range(20):
            with self.assertRaisesRegex(ValueError,'^HTTP/2 reset on unavailable stream$'):
                w.feed('upload',h2(1,5,3,b'private-value-not-parsed'))
        self.assertEqual(w.summary()['first_rejection'],first)
        self.assertNotIn(b'private-value',m.canonical(w.summary()))
        self.assertEqual((w.summary()['bytes'],w.summary()['frames'],w.summary()['reset_records']),before)

    def test_normal_close_history_is_bounded_and_evicted_membership_is_unknown(self):
        for rejected,known in ((1,False),(3,True),(2049,True),(2051,False)):
            w=self.ready()
            for stream in range(1,2050,2):
                w.feed('upload',h2(1,5,stream,b'x'))
                w.feed('download',h2(1,5,stream,b'y'))
                self.assertLessEqual(len(w._normal_close_proofs),1024)
            before=w.idle_eof()
            self.assertEqual(before['closed_streams'],1025)
            self.assertNotIn('first_rejection',before)
            with self.assertRaisesRegex(ValueError,'^HTTP/2 reset on unavailable stream$'):
                w.feed('download',h2(3,0,rejected,(2).to_bytes(4,'big')))
            record=w.summary()['first_rejection']
            self.assertEqual(record['observed_normal_close'],known)
            self.assertTrue(record['normal_close_history_evicted'])
            self.assertFalse(record['observed_reset'])
            self.assertEqual(w.summary()['reset_streams'],0)

    def test_reset_tombstone_requires_both_end_streams_and_complete_headers(self):
        w=self.ready();w.feed('upload',h2(1,1,1,b'x'))
        w.feed('download',h2(1,5,1,b'y'))
        self.assertEqual(w._normal_close_proofs,{})
        w.feed('upload',h2(9,4,1,b'z'))
        self.assertEqual(set(w._normal_close_proofs),{1})
        self.assertNotIn('first_rejection',w.idle_eof())

    def test_normal_closed_cancel_positions_are_wire_exact_for_all_chunkings(self):
        opened=h2(1,5,1,b'opening');closed=h2(1,5,1,b'response')
        cancel=h2(3,0,1,(8).to_bytes(4,'big'));ping=h2(6,payload=b'12345678')
        for width in (1,3,9,13,65536):
            with self.subTest(width=width):
                w=self.ready()
                for offset in range(0,len(opened),width):w.feed('upload',opened[offset:offset+width])
                for offset in range(0,len(closed),width):w.feed('download',closed[offset:offset+width])
                wire=cancel+ping
                for offset in range(0,len(wire),width):w.feed('upload',wire[offset:offset+width])
                summary=w.idle_eof()
                self.assertEqual(summary['terminal_control_records'],[{
                    'direction':'upload','stream_id':1,'error_code':8,
                    'frame':3,'end_byte':len(m.PREFACE)+9+len(opened)+13,
                    'normal_close':{
                        'opened_upload':{'frame':2,'end_byte':len(m.PREFACE)+9+len(opened)},
                        'upload_closed':{'frame':2,'end_byte':len(m.PREFACE)+9+len(opened)},
                        'download_closed':{'frame':2,'end_byte':9+len(closed)}},
                    'opposite_observed_frames':2}])
                self.assertEqual(summary['reset_streams'],0);self.assertEqual(summary['reset_records'],[])
                self.assertEqual(summary['closed_streams'],1);self.assertEqual(summary['last_stream_id'],1)
                self.assertEqual(summary['frames']['upload'],4)
                self.assertLess(summary['terminal_control_records'][0]['end_byte'],summary['bytes']['upload'])

    def test_terminal_proof_waits_for_end_stream_and_header_continuation(self):
        w=self.ready();opening=h2(1,1,1,b'x');w.feed('upload',opening)
        response=h2(1,1,1,b'y');w.feed('download',response)
        up=h2(9,4,1,b'z');down=h2(9,4,1,b'w')
        w.feed('upload',up);self.assertNotIn(1,w._normal_close_proofs)
        w.feed('download',down);w.feed('upload',h2(3,0,1,(8).to_bytes(4,'big')))
        record=w.idle_eof()['terminal_control_records'][0]
        self.assertEqual(record['normal_close'],{
            'opened_upload':{'frame':2,'end_byte':43},
            'upload_closed':{'frame':3,'end_byte':53},
            'download_closed':{'frame':3,'end_byte':29}})
        self.assertEqual((record['frame'],record['end_byte']),(4,66))
        snapshot=w.summary();snapshot['terminal_control_records'][0]['normal_close']['opened_upload']['frame']=999
        self.assertEqual(w.summary()['terminal_control_records'][0],record)
        frontier=w.begin_retirement();self.assertEqual(frontier['terminal_control_records'],[record])
        w.feed('upload',h2(7,payload=b'\0'*8));self.assertEqual(w.idle_eof()['terminal_control_records'],[record])

    def test_terminal_cancel_never_excuses_active_or_incomplete_stream(self):
        for kind in ('active','upload_incomplete','download_incomplete','headers_incomplete'):
            with self.subTest(kind=kind):
                w=self.ready()
                w.feed('upload',h2(1,1 if kind=='headers_incomplete' else 4 if kind=='upload_incomplete' else 5,1,b'x'))
                w.feed('download',h2(1,4 if kind in ('active','download_incomplete') else 5,1,b'y'))
                if kind=='headers_incomplete':
                    with self.assertRaises(ValueError):w.feed('upload',h2(3,0,1,(8).to_bytes(4,'big')))
                else:
                    w.feed('upload',h2(3,0,1,(8).to_bytes(4,'big')))
                    self.assertEqual(w.summary()['reset_streams'],1)
                    with self.assertRaises(ValueError):w.begin_retirement()
                    with self.assertRaises(ValueError):w.idle_eof()
                self.assertEqual(w.summary()['terminal_control_records'],[])

    def test_terminal_cancel_rejects_unknown_skipped_direction_code_and_duplicate(self):
        for direction,stream,code in (('upload',3,8),('upload',5,8),('download',1,8),('upload',1,0),('upload',1,2)):
            with self.subTest(direction=direction,stream=stream,code=code):
                w=self.ready();w.feed('upload',h2(1,5,1,b'x'));w.feed('download',h2(1,5,1,b'y'))
                if stream==3:
                    w.feed('upload',h2(1,4,5,b'x'))
                with self.assertRaisesRegex(ValueError,'^HTTP/2 reset on unavailable stream$'):
                    w.feed(direction,h2(3,0,stream,code.to_bytes(4,'big')))
                self.assertEqual(w.summary()['terminal_control_records'],[])
        w=self.ready();w.feed('upload',h2(1,5,1,b'x'));w.feed('download',h2(1,5,1,b'y'))
        wire=h2(3,0,1,(8).to_bytes(4,'big'));w.feed('upload',wire)
        with self.assertRaisesRegex(ValueError,'^HTTP/2 reset on unavailable stream$'):w.feed('upload',wire)
        self.assertEqual(len(w.summary()['terminal_control_records']),1)
        self.assertEqual(w.summary()['reset_streams'],0)

    def test_terminal_cancel_rejects_after_or_across_original_retirement(self):
        wire=h2(3,0,1,(8).to_bytes(4,'big'))
        for split in (0,1,8,9,12):
            with self.subTest(split=split):
                w=self.ready();w.feed('upload',h2(1,5,1,b'x'));w.feed('download',h2(1,5,1,b'y'))
                if split:w.feed('upload',wire[:split])
                w.begin_retirement()
                with self.assertRaisesRegex(ValueError,'^HTTP/2 reset on unavailable stream$'):w.feed('upload',wire[split:])
                self.assertEqual(w.summary()['terminal_control_records'],[])

    def test_terminal_cancel_bound_64_is_explicit_and_no_existing_reset_is_erased(self):
        w=self.ready()
        for stream in range(1,132,2):
            w.feed('upload',h2(1,5,stream,b'x'));w.feed('download',h2(1,5,stream,b'y'))
        for stream in range(1,129,2):w.feed('upload',h2(3,0,stream,(8).to_bytes(4,'big')))
        self.assertEqual(len(w.idle_eof()['terminal_control_records']),64)
        with self.assertRaisesRegex(ValueError,'^HTTP/2 terminal control bound$'):
            w.feed('upload',h2(3,0,129,(8).to_bytes(4,'big')))
        self.assertEqual(len(w.summary()['terminal_control_records']),64)
        self.assertEqual(w.summary()['closed_streams'],66)
        self.assertEqual(w.summary()['reset_streams'],0)
        v=self.ready();v.feed('upload',h2(1,4,1,b'x'));v.feed('upload',h2(3,0,1,(8).to_bytes(4,'big')))
        v.feed('upload',h2(1,5,3,b'x'));v.feed('download',h2(1,5,3,b'y'))
        v.feed('upload',h2(3,0,3,(8).to_bytes(4,'big')))
        self.assertEqual(v.summary()['reset_records'],[{'direction':'upload','stream_id':1,'error_code':8}])
        with self.assertRaises(ValueError):v.begin_retirement()

    def test_normal_proof_eviction_uses_smallest_id_not_completion_order(self):
        for target,accepted in ((1,False),(3,True)):
            w=self.ready();w.feed('upload',h2(1,5,1,b'x'))
            for stream in range(3,2050,2):
                w.feed('upload',h2(1,5,stream,b'x'));w.feed('download',h2(1,5,stream,b'y'))
            w.feed('download',h2(1,5,1,b'y'))
            self.assertEqual(len(w._normal_close_proofs),1024)
            self.assertNotIn(1,w._normal_close_proofs);self.assertIn(3,w._normal_close_proofs)
            wire=h2(3,0,target,(8).to_bytes(4,'big'))
            if accepted:w.feed('upload',wire);self.assertEqual(len(w.idle_eof()['terminal_control_records']),1)
            else:
                with self.assertRaisesRegex(ValueError,'^HTTP/2 reset on unavailable stream$'):w.feed('upload',wire)

    def test_endpoint_local_opposite_frontier_does_not_change_wire_proof(self):
        witnesses=[self.ready(),self.ready()];ping=h2(6,payload=b'12345678')
        for w in witnesses:
            w.feed('upload',h2(1,5,1,b'x'));w.feed('download',h2(1,5,1,b'y'))
        witnesses[1].feed('download',ping)
        for w in witnesses:w.feed('upload',h2(3,0,1,(8).to_bytes(4,'big')))
        witnesses[0].feed('download',ping)
        a,b=[w.idle_eof() for w in witnesses]
        self.assertEqual(a['terminal_control_records'][0]['opposite_observed_frames'],2)
        self.assertEqual(b['terminal_control_records'][0]['opposite_observed_frames'],3)
        for value in (a,b):value['terminal_control_records'][0].pop('opposite_observed_frames')
        self.assertEqual(a,b)

    def test_reset_diagnostics_do_not_replace_header_or_other_rejections(self):
        for wire,message in ((h2(3,1,1,b'1234'),'Unknown HTTP/2 flags'),
                             (h2(3,0,1,b'123'),'Invalid HTTP/2 control length'),
                             (h2(3,0,0,b'1234'),'Invalid HTTP/2 stream scope')):
            w=self.ready()
            with self.assertRaisesRegex(ValueError,'^'+message+'$'):w.feed('upload',wire)
            self.assertNotIn('first_rejection',w.summary())
        w=self.ready();w.feed('upload',h2(1,4,1,b'x'));w.begin_retirement()
        with self.assertRaisesRegex(ValueError,'^HTTP/2 reset outside original retirement frontier$'):
            w.feed('download',h2(3,0,1,(2).to_bytes(4,'big')))
        self.assertNotIn('first_rejection',w.summary())

    def test_retirement_does_not_excuse_earlier_or_other_reset(self):
        w=self.ready();w.feed('upload',h2(1,5,1,b'x'));w.feed('download',h2(3,0,1,(8).to_bytes(4,'big')))
        with self.assertRaises(ValueError):w.begin_retirement()
        w=self.ready();w.feed('upload',h2(1,5,1,b'x'));w.begin_retirement()
        with self.assertRaises(ValueError):w.feed('download',h2(3,0,1,(2).to_bytes(4,'big')))

    def test_fragmented_reset_started_before_retirement_is_not_reclassified(self):
        wire=h2(3,0,1,(8).to_bytes(4,'big'))
        for split in (1,8,9,11):
            w=self.ready();w.feed('upload',h2(1,5,1,b'x'))
            w.feed('download',wire[:split]);front=w.begin_retirement()
            self.assertFalse(front['frames_complete'])
            with self.assertRaises(ValueError):w.feed('download',wire[split:])
            self.assertEqual(w.summary()['reset_records'],[])

    def test_drain_controls_are_empty_owner_frames(self):
        for kind in (m.DRAIN_BEGIN,m.DRAIN_ACK):
            p=m.FrameParser();self.assertEqual(p.feed(m.encode_frame(kind,0)),[(kind,0,b'')]);p.finish()
            for channel,payload in ((1,b''),(0,b'x')):
                with self.assertRaises(ValueError):m.encode_frame(kind,channel,payload)

    def test_upload_eof_allows_partial_download_until_final_closure(self):
        w=self.ready();w.feed('upload',h2(1,5,1,b'x'));w.begin_retirement()
        response=h2(1,5,1,b'y');w.feed('download',response[:4])
        seal=w.upload_eof()
        self.assertTrue(seal['upload_complete']);self.assertFalse(seal['frames_complete'])
        self.assertEqual(seal['frame_complete'],{'upload':True,'download':False})
        with self.assertRaises(ValueError):w.idle_eof()
        w.feed('download',response[4:]);self.assertTrue(w.idle_eof()['frames_complete'])

    def test_upload_eof_rejects_partial_upload_even_if_download_is_complete(self):
        w=self.ready();w.feed('upload',h2(1,5,1,b'x')[:4]);w.begin_retirement()
        self.assertFalse(w.summary()['upload_complete'])
        with self.assertRaises(ValueError):w.upload_eof()


if __name__ == '__main__':unittest.main()
