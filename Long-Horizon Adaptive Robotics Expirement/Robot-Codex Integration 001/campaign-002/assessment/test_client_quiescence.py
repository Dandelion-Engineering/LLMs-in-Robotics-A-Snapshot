"""Independent lifecycle evidence adversaries; no native process or model."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import client_quiescence as subject


def raw(value):
    return (json.dumps(value, indent=2)+'\n').encode()


def make_records(marker=None, *, mode='active', notification_first=False, prefix=None):
    marker = copy.deepcopy(marker or {'kind':'client_finishing_before_close',
        'schema':'campaign002-client-finishing-1','wall_unix_s':100.,'monotonic_s':100.})
    start = marker['monotonic_s']-.8
    thread = None if mode=='no_thread' else 'thread-known'
    turn = 'turn-known' if mode in ('active','terminal') else None
    status = 'completed' if mode=='terminal' else None
    entry={'thread_start_requested':thread is not None,'turn_start_requested':turn is not None,
           'turn_terminal_status':status}
    rows=copy.deepcopy(prefix if prefix is not None else [{'kind':'request','method':'initialize','id':1}])
    last=max((x['id'] for x in rows if x.get('kind')=='request'),default=0)
    if thread:
        last+=1;rows += [{'kind':'request','method':'thread/start','id':last,'params':{}},
                        {'kind':'response','method':'thread/start','id':last,'result':{'thread':{'id':thread}}}]
    if turn:
        last+=1;rows += [{'kind':'request','method':'turn/start','id':last,'params':{'threadId':thread}},
                        {'kind':'response','method':'turn/start','id':last,'result':{'turn':{'id':turn}}}]
    if status:
        rows.append({'kind':'notification','method':'turn/completed',
                     'params':{'threadId':thread,'turn':{'id':turn,'status':status}}})
    events=[]
    def event(phase, at=None, **fields):
        at=start+.01+.025*len(events) if at is None else at
        e={'kind':'native_quiescence','schema':subject.EVENT_SCHEMA,'sequence':len(events)+1,
           'phase':phase,'wall_unix_s':marker['wall_unix_s']+(at-marker['monotonic_s']),
           'monotonic_s':at,**fields}
        events.append(e);rows.append(e);return e
    event('start',thread_id=thread,turn_id=turn,entry=entry,start_monotonic_s=start,
          graceful_deadline_monotonic_s=start+5,hard_deadline_monotonic_s=start+10)
    terminal={'thread_id':thread,'turn_id':turn,'status':status,'source':'entry','monotonic_s':start} if status else None
    controls=[];closed=None
    methods=(['turn/interrupt'] if mode=='active' else [])+(['thread/unsubscribe'] if thread else [])
    for method in methods:
        last+=1;params={'threadId':thread}
        if method=='turn/interrupt':params['turnId']=turn
        wire=(json.dumps({'id':last,'method':method,'params':params})+'\n').encode()
        e=event('request',method=method,request_id=last,thread_id=thread,
                turn_id=turn if method=='turn/interrupt' else None,wire_bytes=len(wire),wire_sha256=subject.digest(wire))
        sent_at=e['monotonic_s']+.001
        event('request_sent',method=method,request_id=last)
        response_value={} if method=='turn/interrupt' else {'status':'unsubscribed'}
        response_wire=raw({'id':last,'result':response_value})
        note_wire=raw({'method':'turn/completed','params':{'threadId':thread,'turn':{'id':turn,'status':'interrupted'}}}) if method=='turn/interrupt' else raw({'method':'thread/closed','params':{'threadId':thread}})
        def response():
            return event('response',method=method,request_id=last,status='empty' if method=='turn/interrupt' else 'unsubscribed',input_bytes=len(response_wire),input_sha256=subject.digest(response_wire))
        def notification():
            return event('turn_terminal',thread_id=thread,turn_id=turn,status='interrupted',source='cleanup',input_bytes=len(note_wire),input_sha256=subject.digest(note_wire)) if method=='turn/interrupt' else event('thread_closed',thread_id=thread,input_bytes=len(note_wire),input_sha256=subject.digest(note_wire))
        if notification_first:n=notification();r=response()
        else:r=response();n=notification()
        controls.append({'method':method,'request_id':last,'sent_monotonic_s':sent_at,
                         'response_monotonic_s':r['monotonic_s'],'response_status':r['status']})
        if method=='turn/interrupt':terminal={k:n[k] for k in ('thread_id','turn_id','status','source','monotonic_s')}
        else:closed={k:n[k] for k in ('thread_id','monotonic_s')}
    event('handshake_complete',qualified=True)
    rows.append(marker)
    event('finishing',at=marker['monotonic_s']+.005,recorded=True)
    event('stdin_closed',at=marker['monotonic_s']+.010)
    exited=marker['monotonic_s']+.014
    event('native_exit',at=marker['monotonic_s']+.015,exit_code=0,observed_monotonic_s=exited)
    event('completed',at=marker['monotonic_s']+.020,qualified=True)
    rows.append({'kind':'client_shutdown','exit_code':0})
    receipt={'schema':subject.SCHEMA,'thread_id':thread,'turn_id':turn,'entry':entry,
        'start_monotonic_s':start,'graceful_deadline_monotonic_s':start+5,'hard_deadline_monotonic_s':start+10,
        'controls':controls,'terminal_turn':terminal,'thread_closed':closed,'handshake_qualified':True,
        'finishing_recorded':True,'stdin_closed':True,'forced_job_close':False,'native_exit_code':0,
        'native_exit_monotonic_s':exited,'completed_monotonic_s':marker['monotonic_s']+.019,
        'qualified':True,'ignored_notifications':0,'failures':[],'events':events}
    return receipt,rows


class Fixture:
    def __init__(self, path, **kwargs):
        self.repo=path/'repo';self.stage=path/'stage';(self.stage/'client').mkdir(parents=True)
        self.frozen={'sources':{}}
        for name in subject.SOURCE_NAMES:
            p=self.repo/name;p.parent.mkdir(parents=True,exist_ok=True);data=('fixture '+name).encode();p.write_bytes(data)
            self.frozen['sources'][name]={'bytes':len(data),'sha256':subject.digest(data)}
        self.receipt,self.rows=make_records(**kwargs)
        self.launch={'config_overrides':{subject.UNLOAD_KEY:0}}
        self.preflight={'effective_config':{subject.UNLOAD_KEY:0}}
        self.effective={subject.UNLOAD_KEY:0}
    def write(self):
        (self.stage/'client/native-quiescence.json').write_bytes(raw(self.receipt))
        (self.stage/'client/events.jsonl').write_bytes(b''.join(raw(x).replace(b'\n',b'')+b'\n' for x in self.rows))
        (self.stage/'client/result.json').write_bytes(raw({'success':False,'native_quiescence':self.receipt,
                                                          'effective_config':self.effective}))
        (self.stage/'client/launch.json').write_bytes(raw(self.launch))
        (self.stage/'client/preflight.json').write_bytes(raw(self.preflight))
    def verify(self):
        self.write();return subject.verify_client_quiescence(self.stage,self.frozen,repo=self.repo)


class QuiescenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.f=Fixture(Path(self.tmp.name))
    def fails(self, mutate, text='Native quiescence'):
        mutate(self.f)
        with self.assertRaisesRegex(ValueError,text):self.f.verify()
    def test_active_control_and_ordinary_identity_correspondence(self):
        proof=self.f.verify();self.assertTrue(proof['passed']);self.assertEqual(proof['controls'],['turn/interrupt','thread/unsubscribe'])
        self.assertEqual(set(proof['input_bindings']),{'client/native-quiescence.json','client/events.jsonl','client/result.json','client/launch.json','client/preflight.json'})
    def test_unload_setting_missing_wrong_type_and_nonzero_fail_independently(self):
        for label in ('launch','preflight','result'):
            for value in (None, False, True, 0.0, '0', 1, -1, 60):
                with self.subTest(label=label,value=value):
                    target=(self.f.launch['config_overrides'] if label=='launch' else
                            self.f.preflight['effective_config'] if label=='preflight' else self.f.effective)
                    if value is None:target.pop(subject.UNLOAD_KEY)
                    else:target[subject.UNLOAD_KEY]=value
                    with self.assertRaisesRegex(ValueError,label+' unload scheduling'):
                        self.f.verify()
                    target[subject.UNLOAD_KEY]=0
        proof=self.f.verify()
        self.assertEqual(proof['unload_scheduling']['verified_effective_seconds'],0)

    def test_unload_method_and_packet_cannot_be_omitted_or_substituted(self):
        names=[subject.CAMPAIGN+'io-repair/NATIVE_THREAD_UNLOAD_SCHEDULING_V1.md',
               subject.CAMPAIGN+'io-repair/native-unsubscribe-source-001/codex-rs__config__src__config_toml.rs']
        for name in names:
            before=self.f.frozen['sources'].pop(name)
            with self.assertRaisesRegex(ValueError,'source differs'):self.f.verify()
            self.f.frozen['sources'][name]=before
            path=self.f.repo/name;original=path.read_bytes();path.write_bytes(original+b' changed')
            with self.assertRaisesRegex(ValueError,'source differs'):self.f.verify()
            path.write_bytes(original)

    def test_unload_receipt_is_bound_and_cannot_replace_thread_closed(self):
        proof=self.f.verify()
        for name in ('client/launch.json','client/preflight.json'):
            path=self.f.stage/name
            self.assertEqual(proof['input_bindings'][name],{'bytes':len(path.read_bytes()),'sha256':subject.digest(path.read_bytes())})
        event=next(e for e in self.f.receipt['events'] if e['phase']=='thread_closed')
        self.f.receipt['events'].remove(event);self.f.rows.remove(event)
        with self.assertRaises(ValueError):self.f.verify()

    def test_terminal_preflight_and_no_thread_paths(self):
        for mode in ('terminal','preflight','no_thread'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as p:
                f=Fixture(Path(p),mode=mode);self.assertTrue(f.verify()['passed'])
    def test_acknowledgments_can_arrive_before_responses(self):
        self.f.receipt,self.f.rows=make_records(notification_first=True)
        self.assertTrue(self.f.verify()['passed'])
    def test_source_drift_or_missing_protocol_schema(self):
        for name in (subject.SOURCE_NAMES[1],subject.SOURCE_NAMES[-1]):
            with self.subTest(name=name):
                p=self.f.repo/name;original=p.read_bytes();p.write_bytes(original+b'!')
                with self.assertRaisesRegex(ValueError,'source differs'):self.f.verify()
                p.write_bytes(original)
    def test_failed_forced_false_and_nonzero_are_rejected(self):
        for key,value in [('qualified',False),('handshake_qualified',False),('finishing_recorded',False),
                          ('stdin_closed',False),('forced_job_close',True),('native_exit_code',1),
                          ('native_exit_code',False),('failures',['handshake_deadline'])]:
            with self.subTest(key=key):
                before=self.f.receipt[key];self.f.receipt[key]=value
                with self.assertRaisesRegex(ValueError,'failed, forced'):self.f.verify()
                self.f.receipt[key]=before
    def test_wrong_original_thread_response(self):
        self.f.rows[2]['result']['thread']['id']='foreign'
        with self.assertRaisesRegex(ValueError,'thread response'):self.f.verify()
    def test_missing_original_identity_response(self):
        self.f.rows.pop(2)
        with self.assertRaisesRegex(ValueError,'partial native thread'):self.f.verify()
    def test_wrong_turn_target(self):
        self.f.rows[3]['params']['threadId']='foreign'
        with self.assertRaisesRegex(ValueError,'turn targets'):self.f.verify()
    def test_missing_duplicated_or_foreign_ack(self):
        for phase in ('response','thread_closed','turn_terminal'):
            with self.subTest(phase=phase):
                f=self.f;e=next(x for x in f.receipt['events'] if x['phase']==phase)
                key='request_id' if phase=='response' else 'thread_id';old=e[key];e[key]=999 if key=='request_id' else 'foreign'
                with self.assertRaisesRegex(ValueError,'correlation'):f.verify()
                e[key]=old
    def test_unknown_or_duplicate_cleanup_event(self):
        event=self.f.receipt['events'][2];old=event['phase'];event['phase']='tool_call'
        with self.assertRaisesRegex(ValueError,'shape'):self.f.verify()
        event['phase']=old;self.f.rows.insert(-1,copy.deepcopy(event))
        with self.assertRaisesRegex(ValueError,'projection'):self.f.verify()
    def test_native_input_hash_missing_or_zero_size(self):
        event=next(e for e in self.f.receipt['events'] if e['phase']=='response');event['input_bytes']=0
        with self.assertRaisesRegex(ValueError,'input identity'):self.f.verify()
    def test_lifecycle_wire_cannot_target_alternate_thread(self):
        event=next(e for e in self.f.receipt['events'] if e['phase']=='request');event['wire_sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'wire identity'):self.f.verify()
    def test_durable_marker_before_handshake_rejected(self):
        marker=next(e for e in self.f.rows if e.get('kind')=='client_finishing_before_close')
        self.f.rows.remove(marker);self.f.rows.insert(5,marker)
        with self.assertRaisesRegex(ValueError,'durable finishing'):self.f.verify()
    def test_extra_turn_during_cleanup_rejected(self):
        self.f.rows.insert(-2,{'kind':'request','id':99,'method':'turn/start','params':{'threadId':'thread-known'}})
        with self.assertRaisesRegex(ValueError,'after cleanup'):self.f.verify()
    def test_graceful_native_exit_deadline_is_not_hard_deadline(self):
        event=next(e for e in self.f.receipt['events'] if e['phase']=='native_exit')
        event['monotonic_s']=self.f.receipt['graceful_deadline_monotonic_s']+.1
        event['observed_monotonic_s']=event['monotonic_s']
        self.f.receipt['native_exit_monotonic_s']=event['monotonic_s']
        self.f.receipt['events'][-1]['monotonic_s']=event['monotonic_s']+.01
        self.f.receipt['completed_monotonic_s']=event['monotonic_s']+.005
        with self.assertRaisesRegex(ValueError,'absolute phase deadlines'):self.f.verify()
    def test_exit_observation_is_not_invented_from_later_event_retention(self):
        event=next(e for e in self.f.receipt['events'] if e['phase']=='native_exit')
        event['monotonic_s']=self.f.receipt['graceful_deadline_monotonic_s']+.1
        self.f.receipt['events'][-1]['monotonic_s']=event['monotonic_s']+.01
        self.f.receipt['completed_monotonic_s']=event['monotonic_s']+.005
        self.assertTrue(self.f.verify()['passed'])
    def test_entry_terminal_requires_actual_prior_notification(self):
        self.f.receipt,self.f.rows=make_records(mode='terminal')
        self.f.rows[:]=[r for r in self.f.rows if r.get('kind')!='notification']
        with self.assertRaisesRegex(ValueError,'entry terminal'):self.f.verify()
    def test_changed_receipt_without_matching_event_projection(self):
        self.f.receipt['events']=copy.deepcopy(self.f.receipt['events']);self.f.receipt['events'][0]['turn_id']='foreign'
        with self.assertRaisesRegex(ValueError,'projection'):self.f.verify()
    def test_truncated_and_duplicate_key_documents(self):
        self.f.write();p=self.f.stage/'client/native-quiescence.json';original=p.read_bytes()
        p.write_bytes(original[:-1])
        with self.assertRaisesRegex(ValueError,'incomplete'):subject.verify_client_quiescence(self.f.stage,self.f.frozen,repo=self.f.repo)
        p.write_bytes(original.replace(b'"qualified": true',b'"qualified": true, "qualified": true',1))
        with self.assertRaisesRegex(ValueError,'duplicate JSON'):subject.verify_client_quiescence(self.f.stage,self.f.frozen,repo=self.f.repo)
    def test_result_must_durably_preserve_cleanup_receipt(self):
        self.f.write();(self.f.stage/'client/result.json').write_bytes(raw({'success':True}))
        with self.assertRaisesRegex(ValueError,'ordinary result'):subject.verify_client_quiescence(self.f.stage,self.f.frozen,repo=self.f.repo)


if __name__=='__main__':unittest.main()
