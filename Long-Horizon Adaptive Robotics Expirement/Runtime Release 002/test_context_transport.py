"""Synthetic in-memory IPC checks; no candidate subprocess, physics or jobs."""
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zlib

# The worker's Linux resource import is not used by the pure codec. Windows
# unit checks supply only that module name; no limits/OS isolation is invoked.
try:
    import resource
    import candidate_worker
except ModuleNotFoundError:
    with patch.dict(sys.modules,{'resource':SimpleNamespace()}):
        import candidate_worker

from sandbox import CandidateSandbox,SandboxLimits,_strict_json,restore_context_transport


LIMIT=1024*1024


def event(text=None,kind='context_write'):
    text=text if text is not None else json.dumps({'parts':[{'id':'A1','zone':'raw','sequence':27,'pos':[.3,.2,.018]}]*80})+'\n'
    raw=text.encode('utf-8')
    return {'type':kind,'candidate':'baseline','path':'candidate-state.json','byte_count':len(raw),
            'sha256':hashlib.sha256(raw).hexdigest(),'content_utf8':text,'durability':'exact fixture content'}


def message(text=None):
    return {'type':'step','response':{'type':'wait'},'events':[{'type':'uncorrelated_feedback','feedback':{'request_id':'r1','status':'completed'}},event(text)],
            'runtime_usage':{'user_cpu_s':1.2,'scope':'synthetic usage'}}


def carrier(text):
    reply=message(text);item=reply['events'][-1];raw=text.encode('utf-8');del item['content_utf8']
    item['_context_transport']={'codec':'zlib-base64-v1','decoded_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
                                'data':base64.b64encode(zlib.compress(raw)).decode()}
    return reply


class ContextTransportTests(unittest.TestCase):
    def test_exact_round_trip_for_unicode_and_all_fields(self):
        original=message(('line "quoted" \\ newline\n robot λ 日本語 🌿\n')*150);before=copy.deepcopy(original)
        wire=candidate_worker.encode_candidate_message(original,LIMIT)
        restored=restore_context_transport(_strict_json(wire),LIMIT)
        self.assertEqual(restored,original);self.assertEqual(original,before)
        self.assertLess(len(wire),len(json.dumps(original,separators=(',',':')).encode())/3)
    def test_read_and_write_events_both_round_trip(self):
        original=message();original['events'].append(event(kind='context_read'))
        self.assertEqual(restore_context_transport(_strict_json(candidate_worker.encode_candidate_message(original,LIMIT)),LIMIT),original)
    def test_small_and_legacy_uncompressed_replies_are_unchanged(self):
        original=message('tiny checkpoint\n')
        wire=candidate_worker.encode_candidate_message(original,LIMIT)
        self.assertNotIn(b'_context_transport',wire)
        self.assertEqual(restore_context_transport(_strict_json(wire),LIMIT),original)
        self.assertEqual(restore_context_transport(message(),LIMIT),message())
    def test_noncontext_events_and_model_text_are_never_compressed(self):
        original=message();original['events'][-1]['type']='custom_event'
        original['response']={'type':'model','messages':[{'role':'user','content':'large text'*1000}]}
        wire=candidate_worker.encode_candidate_message(original,LIMIT)
        self.assertNotIn(b'_context_transport',wire);self.assertEqual(_strict_json(wire),original)
    def test_original_line_cap_cannot_be_bypassed_by_compression(self):
        with self.assertRaisesRegex(ValueError,'line limit'):candidate_worker.encode_candidate_message(message('x'*LIMIT),LIMIT)
    def test_reserved_candidate_carrier_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'reserved'):candidate_worker.encode_candidate_message(carrier('x'*2000),LIMIT)
    def test_declared_original_context_hash_and_size_are_checked(self):
        for field,value in (('sha256','0'*64),('byte_count',1)):
            original=message();original['events'][-1][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):candidate_worker.encode_candidate_message(original,LIMIT)
    def test_corrupt_compressed_hash_or_stream_fails_closed(self):
        for mode in ('hash','truncated','trailing','base64','utf8'):
            packed=carrier('x'*2000);item=packed['events'][-1];blob=item['_context_transport']
            if mode=='hash':blob['sha256']=item['sha256']='0'*64
            elif mode=='truncated':blob['data']=base64.b64encode(zlib.compress(b'x'*2000)[:-2]).decode()
            elif mode=='trailing':blob['data']=base64.b64encode(zlib.compress(b'x'*2000)+b'trailing').decode()
            elif mode=='base64':blob['data']='!! invalid base64'
            else:
                raw=b'\xff'*2000;blob['data']=base64.b64encode(zlib.compress(raw)).decode();blob['sha256']=item['sha256']=hashlib.sha256(raw).hexdigest()
            with self.subTest(mode=mode),self.assertRaises(ValueError):restore_context_transport(packed,LIMIT)
    def test_declared_output_size_bounds_decompression(self):
        packed=carrier('x'*20000);item=packed['events'][-1]
        item['byte_count']=item['_context_transport']['decoded_bytes']=1
        with self.assertRaisesRegex(ValueError,'length'):restore_context_transport(packed,LIMIT)
    def test_multiple_compressed_contexts_share_one_decoded_budget(self):
        packed=carrier('x'*6000);packed['events'].append(copy.deepcopy(packed['events'][-1]))
        with self.assertRaisesRegex(ValueError,'budget'):restore_context_transport(packed,10000)
    def test_reencoded_reply_keeps_original_line_cap(self):
        packed=carrier('"'*6000)
        with self.assertRaisesRegex(ValueError,'original line limit'):restore_context_transport(packed,10000)
    def test_unknown_codec_or_event_type_or_duplicate_content_fails(self):
        for mode in ('codec','event','duplicate','badsize'):
            packed=carrier('x'*2000);item=packed['events'][-1]
            if mode=='codec':item['_context_transport']['codec']='pickle'
            elif mode=='event':item['type']='action_intent'
            elif mode=='duplicate':item['content_utf8']='ambiguous'
            else:item['_context_transport']['decoded_bytes']=True
            with self.subTest(mode=mode),self.assertRaises(ValueError):restore_context_transport(packed,LIMIT)
    def test_pipe_reader_counts_wire_bytes_and_returns_original_events(self):
        original=message();wire=candidate_worker.encode_candidate_message(original,LIMIT)
        with tempfile.TemporaryDirectory() as directory:
            worker=CandidateSandbox('synthetic',Path(directory))
            worker._read_pipe(io.BytesIO(wire),False)
            self.assertEqual(worker.output_bytes,len(wire));self.assertEqual(worker.poll(),original)
            self.assertIsNone(worker.failure)
    def test_output_quota_remains_finite_and_counts_actual_wire_bytes(self):
        wire=candidate_worker.encode_candidate_message(message(),LIMIT)
        with tempfile.TemporaryDirectory() as directory:
            worker=CandidateSandbox('synthetic',Path(directory),limits=SandboxLimits(output_bytes=len(wire)-1))
            worker._read_pipe(io.BytesIO(wire),False)
            self.assertEqual(worker.failure,'Candidate exceeded the combined output cap')
            self.assertEqual(worker.output_bytes,len(wire))
        self.assertEqual(SandboxLimits().output_bytes,32*1024*1024)
    def test_emit_restores_all_existing_runtime_usage_fields(self):
        usage=SimpleNamespace(ru_utime=1.,ru_stime=2.,ru_maxrss=1024,ru_inblock=3,ru_oublock=4)
        output=io.BytesIO()
        with patch.object(candidate_worker,'resource',SimpleNamespace(RUSAGE_SELF=0,getrusage=lambda _:usage)),patch.object(candidate_worker.sys,'stdout',SimpleNamespace(buffer=output)):
            candidate_worker.emit(message(),LIMIT)
        restored=restore_context_transport(_strict_json(output.getvalue()),LIMIT)
        self.assertEqual(restored['events'],message()['events'])
        self.assertEqual(restored['runtime_usage']['maximum_rss_bytes'],1024*1024)


if __name__=='__main__':unittest.main()
