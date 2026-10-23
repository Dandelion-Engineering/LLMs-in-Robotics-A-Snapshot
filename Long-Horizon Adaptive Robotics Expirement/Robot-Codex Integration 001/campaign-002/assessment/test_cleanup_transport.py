"""Synthetic full-path cleanup evidence; no native process, model or payload replay."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cleanup_transport as subject
import transport_integrity_v3 as transport
from test_transport_integrity_v3 import Fixture, stream
from test_client_quiescence import make_records


def upgrade(f, seed=None):
    """Add a complete source-bound phase to the legacy full transport fixture."""
    for name in subject.SOURCE_NAMES:
        if name not in f.frozen['sources']:
            path=f.repo/name;path.parent.mkdir(parents=True,exist_ok=True)
            raw=('synthetic source '+name).encode();path.write_bytes(raw)
            f.frozen['sources'][name]=stream(raw)
    helper=transport.CAMPAIGN+'harness/native_cleanup_protocol.py'
    f.sources[helper]=f.frozen['sources'][helper]
    f.inside['native_cleanup_protocol.py']=f.frozen['sources'][helper]
    phase=seed['nonce'] if seed is not None else 'c'*32
    def phase_h2(value):
        if isinstance(value,dict):
            if value.get('schema')=='campaign002-passive-h2-3':
                value.update(cleanup_phase_nonce=phase,cleanup_cancel_records=[])
            for v in value.values():phase_h2(v)
        elif isinstance(value,list):
            for v in value:phase_h2(v)
    phase_h2(f.parent);phase_h2(f.namespace);phase_h2(f.receipt)
    f.quiescence,f.client=make_records(f.marker,mode='terminal' if f.channels else 'preflight',prefix=f.client[:-2])
    q=f.quiescence;q['schema']='campaign002-native-quiescence-2'
    event=next(e for e in q['events'] if e['phase']=='request')
    synthetic_event=event
    if seed is not None:
        event=seed['control_event']
        shift=event['monotonic_s']-synthetic_event['monotonic_s']
        wall_shift=event['wall_unix_s']-synthetic_event['wall_unix_s']
        for row in f.parent:
            row['monotonic_s']+=shift;row['wall_unix_s']+=wall_shift
    clock=event['monotonic_s'];wall=event['wall_unix_s']
    request={'schema':'campaign002-native-cleanup-request-1','nonce':phase,'thread_id':q['thread_id'],
             'turn_id':q['turn_id'],'control_event':event,'start_monotonic_s':q['start_monotonic_s'],
             'graceful_deadline_monotonic_s':q['graceful_deadline_monotonic_s'],
             'owner_receipt_sha256':f.owner_bound['sha256']}
    if seed is not None:request={**copy.deepcopy(seed),'owner_receipt_sha256':f.owner_bound['sha256']}
    request_hash=subject.sha(subject.canonical(request))
    def p(kind,offset,**fields):return dict(kind=kind,wall_unix_s=wall+offset,monotonic_s=clock+offset,**fields)
    def n(kind,offset,**fields):return dict(schema=transport.NAMESPACE_SCHEMA,kind=kind,
        wall_unix_s=500.031+offset,monotonic_s=800.031+offset,**fields)
    parent=p('native_cleanup_begin',.0001,request=request,request_sha256=request_hash,channels=[])
    pb=p('frame',.0002,direction='outgoing',frame_type=12,channel_id=0)
    pa=p('frame',.0005,direction='incoming',frame_type=13,channel_id=0)
    ack=p('native_cleanup_ack',.0006)
    i=next(i for i,r in enumerate(f.parent) if r['kind']=='owner_registered')+1
    for j,r in enumerate(f.parent[:i]):r.update(monotonic_s=clock-.002+j*.00001,wall_unix_s=wall-.002+j*.00001)
    f.parent[i:i]=[parent,pb,pa,ack]
    nb=n('frame',.0001,direction='incoming',frame_type=12,channel_id=0)
    ns=n('native_cleanup_begin',.0002,nonce=phase,request_sha256=request_hash,child_pid=42,channels=[])
    na=n('frame',.0003,direction='outgoing',frame_type=13,channel_id=0)
    i=next(i for i,r in enumerate(f.namespace) if r['kind']=='frame' and r['frame_type']==9)+1
    f.namespace[i:i]=[nb,ns,na]
    def empty():
        return {'schema':'campaign002-passive-h2-3','error':None,'preface_complete':False,
            'settings_complete':False,'frames_complete':True,'headers_complete':True,
            'frame_complete':{'upload':True,'download':True},'header_complete':{'upload':True,'download':True},
            'settings_by_direction':{'upload':False,'download':False},'upload_complete':False,
            'open_streams':0,'closed_streams':0,'last_stream_id':0,'retiring':False,'reset_streams':0,
            'active_stream_ids':[],'reset_records':[],'terminal_control_records':[],
            'goaway':{'upload':None,'download':None},'frames':{'upload':0,'download':0},
            'bytes':{'upload':0,'download':0},'max_streams':1024,
            'cleanup_phase_nonce':None,'cleanup_cancel_records':[]}
    for c in f.channels:
        for rows,kind in ((f.parent,'channel_authenticated'),(f.namespace,'channel_open')):
            j=next(j for j,r in enumerate(rows) if r['kind']==kind and r['channel_id']==c['channel_id'])
            previous=rows[j]
            row=dict(kind='native_cleanup_channel',channel_id=c['channel_id'],nonce=phase,
                     request_sha256=request_hash,h2=empty(),wall_unix_s=previous['wall_unix_s']+.001,
                     monotonic_s=previous['monotonic_s']+.001)
            if rows is f.parent:row['authentication_sha256']=subject.sha(subject.canonical(c['authentication']))
            else:row['schema']=transport.NAMESPACE_SCHEMA
            rows.insert(j+1,row)
    for j,r in enumerate(f.namespace,1):r['sequence']=j
    for rows in (f.parent,f.namespace):
        ready=next(r for r in rows if r['kind']=='frame' and r['frame_type']==9)
        payload=subject.canonical(f.ready);ready.update(payload_bytes=len(payload),payload_sha256=subject.sha(payload))
    f.seal()
    begin={'schema':'campaign002-native-cleanup-begin-1','request':request,'parent_record_sha256':parent['record_sha256']}
    ns['parent_record_sha256']=parent['record_sha256']
    acknowledgement={'schema':'campaign002-native-cleanup-ack-1','nonce':phase,'request_sha256':request_hash,
                     'parent_record_sha256':parent['record_sha256'],'namespace_record':ns}
    for row,payload in ((pb,begin),(nb,begin),(pa,acknowledgement),(na,acknowledgement)):
        raw=subject.canonical(payload);row.update(payload_bytes=len(raw),payload_sha256=subject.sha(raw))
    ack.update(request_sha256=request_hash,namespace_record_sha256=subject.sha(subject.canonical(ns)),
               begin_payload_sha256=pb['payload_sha256'],ack_payload_sha256=pa['payload_sha256'],namespace_record=ns)
    f.seal()
    complete={'schema':'campaign002-native-cleanup-complete-1','request':request,'request_sha256':request_hash,
        'parent_barrier_record_sha256':parent['record_sha256'],'namespace_barrier_record_sha256':ack['namespace_record_sha256'],
        'begin_payload_sha256':pb['payload_sha256'],'ack_payload_sha256':pa['payload_sha256'],
        'parent_ack_record_sha256':ack['record_sha256'],'parent_ack_sequence':ack['sequence'],
        'completed_monotonic_s':clock+.0007}
    barrier=dict(kind='native_quiescence',schema=event['schema'],phase='cleanup_barrier_complete',
                 monotonic_s=clock+.0008,wall_unix_s=wall+.0008,receipt=complete)
    for rows in (q['events'],f.client):rows.insert(rows.index(synthetic_event)+1,barrier)
    for j,r in enumerate(q['events'],1):r['sequence']=j
    q['cleanup_barrier']=complete;f.receipt['cleanup_barrier']=complete
    f.finished['cleanup_barrier']={k:v for k,v in dict(nonce=phase,request_sha256=request_hash,
        parent_record_sha256=parent['record_sha256'],namespace_record_sha256=ack['namespace_record_sha256'],
        begin_payload_sha256=pb['payload_sha256'],ack_payload_sha256=pa['payload_sha256']).items()}
    f.finished['frame_counts']={d:sum(r['kind']=='frame' and r['direction']==d for r in f.namespace) for d in ('incoming','outgoing')}
    f.refresh_closed_frames();f.write()
    return f


def synthetic_barrier_files(stage, owner, seed):
    """Bounded metadata fixture for actual Controller tests, not an OS receipt."""
    with tempfile.TemporaryDirectory() as folder:
        f=Fixture(Path(folder),count=0)
        f.owner.clear();f.owner.update(copy.deepcopy(owner))
        raw=(json.dumps(owner,indent=2)+'\n').encode()
        f.owner_bound.update(f.bind('codehost-native-owner-v3.json',raw))
        upgrade(f,seed)
        for name in ('codehost-transport-v3.jsonl','codehost-owner-stderr-v3.txt',
                     'codehost-owner-bridge-v3.json','codehost-native-owner-v3.json'):
            (stage/name).write_bytes((f.stage/name).read_bytes())
        return copy.deepcopy(f.receipt['cleanup_barrier'])


def cancellation_pair():
    """Distinct endpoint ordering with equal source-witnessed per-stream trace."""
    from test_transport_integrity_v3 import h2
    p=h2(b'x'*73,b'x'*40);p.update(frames={'upload':4,'download':3},closed_streams=0,reset_streams=1,
        reset_records=[{'direction':'upload','stream_id':1,'error_code':8}],cleanup_phase_nonce='a'*32)
    cancel={'direction':'upload','type':3,'flags':0,'payload_length':4,'error_code':8,
            'frame':4,'start_byte':60,'end_byte':73,'sha256':subject.sha(bytes.fromhex('00000403000000000100000008'))}
    row={'schema':'campaign002-h2-cleanup-cancel-1','phase_nonce':'a'*32,'stream_id':1,'cancel':cancel,
        'opened_upload':{'frame':2,'start_byte':33,'end_byte':42},'opening_headers_complete':{'frame':2,'end_byte':42},
        'upload_end_stream':{'frame':3,'end_byte':60},'upload_headers_complete':{'frame':3,'end_byte':60},
        'download_end_stream':{'frame':3,'end_byte':40},'download_headers_complete':{'frame':3,'end_byte':40},
        'wire':{'upload':{'frames':3,'bytes':40,'sha256':'a'*64},'download':{'frames':2,'bytes':31,'sha256':'b'*64}},
        'local':{'classification':'active','reset_record_index':0,'terminal_control_index':None,'eligibility':'frontier_active',
            'opposite_observed':{'frames':2,'wire_bytes':18,'partial_frame':False,'pending_headers_stream':None},
            'phase_frontier':{'upload_frames':3,'upload_wire_bytes':60,'download_frames':2,'download_wire_bytes':18,'last_stream_id':1}}}
    p['cleanup_cancel_records']=[row];n=copy.deepcopy(p)
    n.update(reset_streams=0,reset_records=[],closed_streams=1,terminal_control_records=[{
        'direction':'upload','stream_id':1,'error_code':8,'frame':4,'end_byte':73,
        'normal_close':{'opened_upload':{'frame':2,'end_byte':42},'upload_closed':{'frame':3,'end_byte':60},
                        'download_closed':{'frame':3,'end_byte':40}},'opposite_observed_frames':3}])
    local=n['cleanup_cancel_records'][0]['local'];local.update(classification='normal_closed',reset_record_index=None,
        terminal_control_index=0,eligibility='proved_normal_close')
    local['opposite_observed'].update(frames=3,wire_bytes=40)
    local['phase_frontier'].update(download_frames=3,download_wire_bytes=40)
    return p,n


class CleanupTests(unittest.TestCase):
    def test_mixed_counter_equation_preserves_original_evidence(self):
        p,n=cancellation_pair();before=copy.deepcopy((p,n))
        self.assertEqual(transport.h2_facts(p),transport.h2_facts(n));self.assertEqual((p,n),before)
        self.assertTrue(subject.explained_resets(p));transport.idle_h2(p)
        self.assertEqual((p['reset_streams'],n['closed_streams']),(1,1))

    def test_counter_index_and_fixed_cancel_mutations(self):
        mutations=[lambda p:p.update(reset_streams=0),lambda p:p['cleanup_cancel_records'][0]['local'].update(reset_record_index=True),
            lambda p:p['reset_records'][0].update(stream_id=3),lambda p:p['cleanup_cancel_records'][0]['cancel'].update(error_code=0),
            lambda p:p['cleanup_cancel_records'][0]['cancel'].update(sha256='f'*64),
            lambda p:p['cleanup_cancel_records'][0]['local']['phase_frontier'].update(upload_wire_bytes=61),
            lambda p:p['cleanup_cancel_records'][0]['local'].update(eligibility='opened_during_phase'),
            lambda p:p['cleanup_cancel_records'][0]['wire']['download'].update(frames=0,bytes=0,sha256=subject.sha(b'')),
            lambda p:p.update(cleanup_phase_nonce=None),lambda p:p['cleanup_cancel_records'].append(copy.deepcopy(p['cleanup_cancel_records'][0]))]
        for mutate in mutations:
            p,_=cancellation_pair();mutate(p)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):transport.h2_summary(p)

    def test_nonlocal_trace_difference_cannot_be_projected_away(self):
        p,n=cancellation_pair();n['cleanup_cancel_records'][0]['wire']['download']['sha256']='c'*64
        self.assertNotEqual(transport.h2_facts(p),transport.h2_facts(n))

    def test_unexplained_raw_reset_and_false_idle_eof_rejected(self):
        p,_=cancellation_pair();p['cleanup_cancel_records']=[]
        self.assertFalse(subject.explained_resets(p))
        with self.assertRaises(ValueError):transport.idle_h2(p)
        p,_=cancellation_pair();p.update(open_streams=1,active_stream_ids=[3],last_stream_id=3)
        with self.assertRaises(ValueError):transport.idle_h2(p)

    def test_cleanup_prefix_and_completed_trace_are_immutable(self):
        p,_=cancellation_pair();later=copy.deepcopy(p)
        subject.progress(later,p)
        for mutate in (lambda x:x['cleanup_cancel_records'].clear(),
                       lambda x:x['cleanup_cancel_records'][0]['wire']['download'].update(sha256='d'*64),
                       lambda x:x['cleanup_cancel_records'][0]['download_end_stream'].update(end_byte=39)):
            later=copy.deepcopy(p);mutate(later)
            with self.assertRaises(ValueError):subject.progress(later,p)

    def test_post_retirement_normal_counterpart_and_original_active_reset(self):
        p,n=cancellation_pair()
        for value,active in ((p,True),(n,False)):
            frontier=copy.deepcopy(value);frontier['cleanup_cancel_records']=[]
            frontier.update(reset_records=[],reset_streams=0,terminal_control_records=[],
                open_streams=int(active),active_stream_ids=[1] if active else [],
                closed_streams=int(not active),frames={'upload':3,'download':3},bytes={'upload':60,'download':40})
            value['retiring']=True
            transport.channel_h2(value,frontier)
            if active:
                frontier['bytes']['upload']=61
                with self.assertRaisesRegex(ValueError,'began before'):transport.channel_h2(value,frontier)
                frontier['bytes']['upload']=60;frontier.update(open_streams=0,active_stream_ids=[])
                with self.assertRaisesRegex(ValueError,'original stream frontier'):transport.channel_h2(value,frontier)


class FullPathTests(unittest.TestCase):
    def make(self,count=0):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        return upgrade(Fixture(Path(tmp.name),count=count))
    def verify(self,f):
        f.write()
        with patch.object(transport,'REPO',f.repo):
            return transport.verify_transport_integrity(f.stage,f.frozen,allow_empty=not f.channels)
    def test_complete_zero_channel_and_phase_born_channel_paths(self):
        for count in (0,1,2):
            with self.subTest(count=count):
                f=self.make(count);proof=self.verify(f)
                self.assertTrue(proof['passed']);self.assertEqual(len(proof['client_quiescence']['input_bindings']),10)
                self.assertEqual(proof['client_quiescence']['cleanup_transport']['channels'],count)
    def test_no_thread_requires_no_barrier_and_retains_eight_inputs(self):
        f=self.make(0)
        for rows in (f.parent,f.namespace):
            rows[:]=[r for r in rows if not(r['kind'].startswith('native_cleanup_') or
                      r['kind']=='frame' and r['frame_type'] in (12,13))]
        for j,row in enumerate(f.namespace,1):row['sequence']=j
        f.quiescence,f.client=make_records(f.marker,mode='no_thread',prefix=f.client[:2])
        f.quiescence.update(schema='campaign002-native-quiescence-2',cleanup_barrier=None)
        f.receipt['cleanup_barrier']=None;f.finished['cleanup_barrier']=None
        f.finished['frame_counts']={d:sum(r['kind']=='frame' and r['direction']==d for r in f.namespace) for d in ('incoming','outgoing')}
        proof=self.verify(f);self.assertTrue(proof['passed'])
        self.assertEqual(len(proof['client_quiescence']['input_bindings']),8)
        f.quiescence['cleanup_barrier']={'invented':True}
        with self.assertRaises(ValueError):self.verify(f)
    def test_missing_and_foreign_barrier_or_source_fail_top_level(self):
        for case in ('ack_missing','frame_missing','foreign_owner','late_complete','missing_method','birth_nonce'):
            with self.subTest(case=case):
                f=self.make(1)
                if case=='ack_missing':f.parent[:]=[r for r in f.parent if r['kind']!='native_cleanup_ack']
                elif case=='frame_missing':f.namespace[:]=[r for r in f.namespace if not(r['kind']=='frame' and r['frame_type']==13)]
                elif case=='foreign_owner':f.receipt['cleanup_barrier']['request']['owner_receipt_sha256']='0'*64
                elif case=='late_complete':f.receipt['cleanup_barrier']['completed_monotonic_s']+=6
                elif case=='missing_method':f.frozen['sources'].pop(subject.METHOD)
                else:next(r for r in f.parent if r['kind']=='native_cleanup_channel')['nonce']='d'*32
                with self.assertRaises(ValueError):self.verify(f)

    def test_full_path_reconciles_exact_raw_counter_pair_and_rejects_trace_change(self):
        f=self.make(1);p,n=cancellation_pair();phase=f.receipt['cleanup_barrier']['request']['nonce']
        for value in (p,n):
            value['cleanup_phase_nonce']=phase;row=value['cleanup_cancel_records'][0];row['phase_nonce']=phase
            row['local']['phase_frontier']={'upload_frames':0,'upload_wire_bytes':0,
                'download_frames':0,'download_wire_bytes':0,'last_stream_id':0}
            if row['local']['classification']=='active':row['local']['eligibility']='opened_during_phase'
        def replace(value,endpoint):
            if isinstance(value,dict):
                if value.get('schema')=='campaign002-passive-h2-3' and value['last_stream_id']:
                    retiring=value['retiring'];value.clear();value.update(copy.deepcopy(p if endpoint=='parent' else n));value['retiring']=retiring
                else:
                    for key,item in value.items():
                        if key not in ('namespace_records','namespace_closed','finished','receipt'):replace(item,endpoint)
            elif isinstance(value,list):
                for item in value:replace(item,endpoint)
        # Separate endpoint witnesses; legacy Fixture deliberately aliases them.
        f.channels[0]['h2']=copy.deepcopy(p);f.channels[0]['h2']['retiring']=True
        replace(f.parent,'parent');replace(f.channels,'parent');replace(f.namespace,'namespace')
        terminal=f.channels[0]['namespace_closed']
        for key in ('h2','upload_eof_h2','download_eof_h2','seal_frontier'):
            terminal[key]=copy.deepcopy(n);terminal[key]['retiring']=True
        terminal['finish_frontier']=copy.deepcopy(n)
        for key in ('finish_frontier','seal_frontier'):
            f.channels[0][key]=copy.deepcopy(p);f.channels[0][key]['retiring']=key=='seal_frontier'
        f.frontiers[0]['h2']=f.channels[0]['finish_frontier']
        next(r for r in f.parent if r['kind']=='channel_seal_frontier')['h2']=f.channels[0]['seal_frontier']
        next(r for r in f.namespace if r['kind']=='channel_finish_frontier')['h2']=copy.deepcopy(n)
        for rows,endpoint in ((f.parent,'parent'),(f.namespace,'namespace')):
            for r in rows:
                if r.get('kind')=='channel_eof':r['h2']=copy.deepcopy(n);r['h2']['retiring']=True
                if r.get('kind')=='client_eof':r['h2']=copy.deepcopy(p);r['h2']['retiring']=True
                if r.get('kind')=='channel_closed' and endpoint=='parent':r['h2']=f.channels[0]['h2']
                if r.get('kind')=='frame' and r.get('frame_type')==3:
                    upload=r['direction']==('outgoing' if endpoint=='parent' else 'incoming')
                    raw=b'x'*73 if upload else b'y'*40;r.update(payload_bytes=len(raw),payload_sha256=subject.sha(raw))
        meters={'client_read':stream(b'x'*73),'upload':stream(b'x'*73),'download':stream(b'y'*40),'client_written':stream(b'y'*40)}
        f.channels[0]['meters']=meters
        for r in f.parent:
            if r['kind'] in ('upload_drained','channel_closed'):r['meters']=copy.deepcopy(meters)
        terminal.update(upload=meters['upload'],download=meters['download'])
        next(r for r in f.namespace if r['kind']=='channel_upload_drained')['upload']=meters['upload']
        f.refresh_closed_frames();proof=self.verify(f);self.assertTrue(proof['passed'])
        terminal['h2']['cleanup_cancel_records'][0]['wire']['download']['sha256']='f'*64
        f.refresh_closed_frames()
        with self.assertRaises(ValueError):self.verify(f)


if __name__=='__main__':unittest.main()
