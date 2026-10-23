"""Tiny synthetic event streams only; no raw development evidence or queue."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from extract_development_incident import RUN_ID,scan_events,digest,fresh,checkpoint

HERE=Path(__file__).resolve().parent


def packet(sequence, detections):
    return {'sequence':sequence,'incarnation':1,'sim_time':float(sequence),'capture_sim_time_s':float(sequence)-.1,
            'detections':detections,'order':{'requirements':[{'family':'B','recipe':'B','count':1,'tray':'tray2'}]},
            'station':{'ready':True},'human_answers':[]}


def target(age=.1):return {'id':'B6','kind':'part','family':'B','zone':'raw','pos':[.4,-.2,.02],'age_s':age,'visible_mark':'raw'}


def stream(path,*,changed_payload=False):
    records=[]
    def add(kind,payload,parents=None):
        identity=len(records)+1
        records.append({'schema_version':'robot-evidence-1.0','run_id':RUN_ID,'event_id':identity,'event_type':kind,
            'payload':payload,'payload_sha256':digest(payload),'parent_ids':parents or [],'sim_time_s':float(identity),'wall_elapsed_s':float(identity)})
        return identity
    add('observation',{'packet':packet(1,[target()]),'rgb':'frames/000001.png','artifacts':{'rgb':{'path':'frames/000001.png','sha256':'a'*64}}})
    for seq in (1,1,1,1):
        parent=add('candidate_input',{'message':{'type':'step','packet':packet(seq,[target()])}})
        add('candidate_reply',{'supervisor_input_event_id':parent,'events':[{'type':'action_intent','action':{'operation':'observe','observation_sequence':seq}}]},[parent])
    parent=add('candidate_input',{'message':{'type':'step','packet':packet(2,[])}})
    add('candidate_reply',{'supervisor_input_event_id':parent,'events':[{'type':'action_intent','action':{'operation':'help','request_id':'help1','reason':'visibility unknown','observation_sequence':2}}]},[parent])
    add('action_requested',{'operation':'help','request_id':'help1','reason':'visibility unknown'})
    add('help_requested',{'request_id':'help1','accepted':True})
    add('observation',{'packet':packet(3,[target()]),'rgb':'frames/000003.png'})
    add('scripted_human_answer',{'request_id':'help1','answer_id':'answer1'})
    add('final_world',{'objects':{'B6':{'pos':[.4,-.2,.02],'cycles':0}},'station':{}})
    if changed_payload:records[0]['payload']['packet']['sequence']=999
    raw=b''.join(json.dumps(row,separators=(',',':')).encode()+b'\n' for row in records)
    path.write_bytes(raw);return hashlib.sha256(raw).hexdigest(),records


class IncidentTests(unittest.TestCase):
    def test_one_pass_retains_same_frame_idle_chain_and_separates_later_public_and_truth(self):
        with TemporaryDirectory(dir=HERE) as directory:
            path=Path(directory)/'events.jsonl';expected,_=stream(path);before=path.read_bytes()
            report=scan_events(path,expected);self.assertEqual(path.read_bytes(),before)
            incident=report['incidents'][0]
            self.assertEqual([v['event']['action']['observation_sequence'] for v in incident['preceding_decisions']],[1,1,1,1])
            self.assertEqual(incident['candidate_input']['packet']['target_presence'],'absent_from_packet')
            self.assertEqual(incident['last_fresh_target_detection']['frames']['paths']['rgb'],'frames/000001.png')
            self.assertEqual(incident['first_following_fresh_target']['packet']['sequence'],3)
            self.assertEqual(report['final_protected_world']['target_truth']['cycles'],0)
            self.assertEqual(report['events_source']['json_stream_passes'],1)
            source=incident['anchor'];line=before.splitlines(keepends=True)[source['line']-1]
            self.assertEqual(source['line_sha256'],hashlib.sha256(line).hexdigest())
            self.assertGreaterEqual(len(incident['correlated_service_events']),3)

    def test_payload_or_canonical_original_hash_mismatch_refuses(self):
        for change in ('payload','canonical'):
            with self.subTest(change=change),TemporaryDirectory(dir=HERE) as directory:
                path=Path(directory)/'events.jsonl';expected,_=stream(path,changed_payload=change=='payload')
                with self.assertRaises(ValueError):scan_events(path,'f'*64 if change=='canonical' else expected)

    def test_stale_future_unknown_mark_and_nonpart_are_not_conflated(self):
        self.assertFalse(fresh(target(1.50001)));self.assertFalse(fresh(target(-.01)))
        unknown={**target(),'visible_mark':'unknown'};self.assertTrue(fresh(unknown))
        self.assertFalse(fresh({**target(),'kind':'insert'}));self.assertFalse(fresh({**target(),'zone':'tray4'}))

    def test_checkpoint_exact_utf8_and_candidate_belief_retained(self):
        state={'parts':{'B6':{'last_seen':{'zone':'raw'}}},'halted':True,'last_error':'unknown – reobserve',
               'received_human_answer_ids':['answer1'],'pending':None,'failure_counts':{}}
        state_sha=hashlib.sha256(json.dumps(state,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        raw=(json.dumps({'state':state,'sha256':state_sha},ensure_ascii=False)+'\n').encode()
        event={'sha256':hashlib.sha256(raw).hexdigest(),'byte_count':len(raw),'content_utf8':raw.decode()}
        result=checkpoint(event);self.assertTrue(result['halted']);self.assertEqual(result['received_human_answer_ids'],['answer1'])
        with self.assertRaises(ValueError):checkpoint({**event,'sha256':'f'*64})


if __name__=='__main__':unittest.main()
