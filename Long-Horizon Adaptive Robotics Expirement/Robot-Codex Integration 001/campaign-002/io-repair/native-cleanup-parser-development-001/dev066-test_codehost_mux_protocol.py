import asyncio
import struct
import unittest

import codehost_mux_protocol as m


def h2(kind, flags=0, stream=0, payload=b''):
    return len(payload).to_bytes(3,'big') + bytes([kind,flags]) + stream.to_bytes(4,'big') + payload


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
