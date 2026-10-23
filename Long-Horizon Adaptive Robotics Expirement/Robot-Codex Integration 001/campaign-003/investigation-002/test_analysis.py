"""Small synthetic checks of evidence distinctions; no plant/model work."""
import copy
import unittest
from analyze import artifact_history, terminal_status, handback_events, physical_terminal_events


class HistoryChecks(unittest.TestCase):
    def test_native_admission_rejection_counts_once(self):
        rows=[dict(type='command_requested',payload=dict(request_id='p',status='pending')),
            dict(type='command_admission',payload=dict(request_id='p',feedback={'status':'rejected'})),
            dict(type='command_rejected',payload=dict(request_id='p',status='rejected')),
            dict(type='command_admission',payload=dict(request_id='q',feedback={'status':'accepted'}))]
        terminal=physical_terminal_events(rows,{'p','q'})
        self.assertEqual(len(terminal),1)
        self.assertEqual(terminal_status(terminal[0]['payload']),'rejected')

    def test_transfer_is_an_authority_event_not_a_servo_terminal(self):
        rows=[dict(event_id=1,sim_time_s=1,owner='robot',type='command_requested',
            payload=dict(request_id='h',kind='handback',actor='robot')),
            dict(event_id=2,sim_time_s=2,owner='conventional',type='control_owner_changed',
            payload=dict(request_id='h',reason='accepted')),
            dict(event_id=3,sim_time_s=3,owner='robot',type='control_owner_changed',payload={})]
        result=handback_events(rows)
        self.assertEqual(len(result),1)
        self.assertEqual((result[0]['request_id'],result[0]['status']),('h','completed'))
        self.assertEqual(result[0]['original_payload'],rows[1]['payload'])

    def test_distinct_terminal_shapes_and_missing_evidence(self):
        self.assertEqual(terminal_status({'feedback':{'status':'completed'}}),'completed')
        self.assertEqual(terminal_status({'status':'rejected'}),'rejected')
        self.assertEqual(terminal_status({}),'unknown')

    def test_conflicting_terminal_status_is_rejected(self):
        with self.assertRaises(AssertionError):
            terminal_status({'status':'rejected','feedback':{'status':'completed'}})

    def initial(self):
        state={'paths':{'/notes/prior.txt':1},'nodes':{'1':{'sha256':'a'*64,'size':4,'mode':33188}}}
        return state, [{'sequence':1,'type':'initial','session_id':'setup','state':copy.deepcopy(state)}]

    def read(self, sequence, session, path='/notes/prior.txt', size=4):
        return dict(sequence=sequence,type='read',session_id=session,path=path,bytes=size,offset=0,
            content_sha256='a'*64,returned_sha256='a'*64,monotonic_ns=sequence,process={'namespace_role':'isolated-runtime'})

    def test_preflight_and_zero_byte_reads_do_not_establish_reuse_candidates(self):
        state, records=self.initial()
        records.append(self.read(2,'robot-session-2'))
        records.append(dict(sequence=3,type='checkpoint',label='before-model-invocation',
            session_id='robot-session-2',state=copy.deepcopy(state)))
        records.append(self.read(4,'robot-session-2',size=0))
        records.append(self.read(5,'robot-session-2'))
        records.append(dict(sequence=6,type='final',session_id='robot-session-2',state=state,state_sha256='final'))
        result=artifact_history(records)
        self.assertEqual([r['matches_content_at_session_start'] for r in result['reads']],[False,False,True])
        self.assertEqual(result['changes'],[])
        self.assertNotIn('useful_transfer',result)

    def test_rename_change_and_unlink_remain_distinct_records(self):
        state, records=self.initial()
        for sequence, operation, paths, nodes in (
            (2,'rename',{'remove':['/notes/prior.txt'],'set':{'/programs/prior.txt':1}}, {'remove':[],'set':{}}),
            (3,'write',{'remove':[],'set':{}},{'remove':[],'set':{'1':{'sha256':'b'*64,'size':7,'mode':33188}}}),
            (4,'unlink',{'remove':['/programs/prior.txt'],'set':{}},{'remove':['1'],'set':{}})):
            records.append(dict(sequence=sequence,type='mutation',session_id='robot-session-1',
                operation=operation,delta={'paths':paths,'nodes':nodes},process={},monotonic_ns=sequence))
            for area, delta in (('paths',paths),('nodes',nodes)):
                for key in delta['remove']:del state[area][key]
                state[area].update(delta['set'])
        records.append(dict(sequence=5,type='final',session_id='robot-session-1',state=state,state_sha256='final'))
        result=artifact_history(records)
        self.assertEqual([c['operation'] for c in result['changes']],['rename','rename','write','unlink'])
        self.assertEqual(result['final_inventory'],{})
        self.assertEqual(result['changes'][2]['before']['sha256'],'a'*64)
        self.assertEqual(result['changes'][2]['after']['sha256'],'b'*64)

    def test_missing_delta_is_not_silently_ignored(self):
        state, records=self.initial()
        records.append(dict(sequence=2,type='final',session_id='robot-session-1',state={'paths':{},'nodes':{}},state_sha256='bad'))
        with self.assertRaises(AssertionError):artifact_history(records)


if __name__=='__main__':unittest.main()
