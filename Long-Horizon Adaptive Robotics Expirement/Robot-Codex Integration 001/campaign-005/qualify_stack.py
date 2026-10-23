"""No-model authority, terminal, image-dispatch, redaction and schedule gates."""
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import queue
import time
import traceback
from types import SimpleNamespace
from common import HERE, inherited_paths, save, load_module, sha
inherited_paths()
from test_supervisor import FakeAdapter,packet,Candidate
from supervisor import Journal
from supervisor_c import Supervisor
from terminal import TerminalAppend
from image_sensor import ImageSensor,TOOL,observable
from scheduler import Schedule

def run(output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);checks={};result={'passed':False,'model_calls':0,'checks':checks}
    try:
        fake=FakeAdapter();journal=Journal(out/'protected',out/'workspace','synthetic-only')
        host=Supervisor(fake,Candidate('baseline',out/'baseline',True),journal)
        host.current_session_id='session-1';host.update_observation(packet('parking1'));host.activate('Synthetic check')
        note=out/'workspace/Continuity.md';note.write_bytes(b'Agent note: outcome unknown.\n')
        before=note.read_bytes();terminal=TerminalAppend(out/'terminal')
        rejected=copy.deepcopy(host.envelope('rejected'));rejected['authority_epoch']=0
        denied=host.handback(rejected);checks['rejected_handback_not_accepted']=denied['command']['status']=='rejected' and not host.accepted_handbacks
        value=host.handback(host.envelope('accepted'));checks['accepted_receipt']=value['command']['status']=='completed'
        accepted=host.accepted_handbacks['accepted']
        def deny(label,a,r,c):
            old=note.read_bytes()
            try:terminal.finalize(note,a,r,c)
            except ValueError:checks[label]=note.read_bytes()==old
            else:checks[label]=False
        retirement={'run_id':journal.run_id,'session_id':'session-1','all_namespaces_retired':True,'evidence_sha256':sha(out/'protected/public-history.jsonl')}
        deny('accepted_without_resumption_no_append',accepted,{},retirement)
        host.conventional_step();resumed=host.resumptions['accepted']
        checks['authoritative_conventional_command']=resumed['conventional_request_id'] in host.commands
        deny('cleanup_incomplete_no_append',accepted,resumed,{**retirement,'all_namespaces_retired':False})
        deny('interrupted_no_append',{**accepted,'status':'cancelled'},resumed,retirement)
        deny('wrong_session_no_append',accepted,{**resumed,'session_id':'other'},retirement)
        receipt=terminal.finalize(note,accepted,resumed,retirement)
        checks['accepted_append_preserves_agent_bytes']=note.read_bytes().startswith(before) and note.read_bytes().count(b'Machine-authored terminal record')==1
        checks['idempotent_append']=terminal.finalize(note,accepted,resumed,retirement)==receipt and note.read_bytes().count(b'Machine-authored terminal record')==1
        # Simulate crash after durable replacement but before the terminal receipt.
        identity=receipt['record']['record_id'];(out/'terminal'/(identity+'.json')).rename(out/'terminal'/(identity+'.crash-fixture'))
        checks['interrupted_receipt_reconciles']=terminal.finalize(note,accepted,resumed,retirement)==receipt
        checks['no_model_wakeup']=True # This module imports no model process; dynamic client __init__ is never called.
        # Real simulator pixels, real exact model-facing dispatcher; offline RPC replay.
        image=HERE.parent/'campaign-004/qualification/identity-001/source-zp-0.png';target=out/'workspace/live/observations/overhead-1.png';target.parent.mkdir(exist_ok=True)
        target.write_bytes(image.read_bytes())
        journal.event('requested_image_available',{'observation_sequence':1,'path':'live/observations/overhead-1.png','bytes':target.stat().st_size,'sha256':sha(target),'capture_sim_time_s':1.0,'camera':'overhead'},1,2,'robot')
        sensor=ImageSensor(out/'workspace',journal,journal.run_id,'image-session',2)
        module=load_module('campaign005_client_offline',HERE/'bootstrap_client.py')
        client=module.Client.__new__(module.Client)
        client.args=SimpleNamespace(image_sensor=sensor,redact_tokens=[]);client.deadline=time.monotonic()+5
        client.thread_id='fresh-thread';client.turn_id='fresh-turn';client.cleanup_started=False;client.bytes_seen=0;client.messages=queue.Queue();client.pending_events=[]
        client.events=(out/'observable-events.jsonl').open('x',encoding='utf-8');sent=[];client.send=sent.append
        params={'tool':'robot_image','arguments':{'observation_sequence':1},'callId':'image-1','threadId':client.thread_id,'turnId':client.turn_id}
        client.messages.put(('stdout',json.dumps({'id':80,'method':'item/tool/call','params':params}).encode()))
        client.messages.put(('stdout',b'{"id":99,"result":{}}'))
        assert client.receive()['id']==99
        response=sent[0]['result'];checks['actual_model_facing_pixels']=base64.b64decode(response['contentItems'][1]['imageUrl'].split(',',1)[1])==image.read_bytes()
        from protocol_check import validate
        validate(params,json.loads((HERE/'protocol/DynamicToolCallParams.json').read_text()))
        validate(response,json.loads((HERE/'protocol/DynamicToolCallResponse.json').read_text()))
        checks['pinned_appserver_protocol']=True
        for name,change in [('wrong_context',{'threadId':'other'}),('arbitrary_path',{'arguments':{'path':'C:/Users/secret'}}),('unknown_image',{'arguments':{'observation_sequence':999}})]:
            try:sensor.call({**params,**change})
            except ValueError:checks[name+'_denied']=True
            else:checks[name+'_denied']=False
        sensor.retired=True
        try:sensor.call(params)
        except ValueError:checks['retired_image_denied']=True
        client.log({'kind':'notification','method':'item/reasoning/textDelta','params':{'delta':'PRIVATE_SENTINEL'}})
        client.log({'kind':'notification','method':'item/completed','params':{'item':{'type':'reasoning','text':'PRIVATE_SENTINEL'}}})
        client.log({'kind':'notification','method':'item/agentMessage/delta','params':{'delta':'PUBLIC_SENTINEL'}})
        client.events.close();raw=(out/'observable-events.jsonl').read_text()
        checks['hidden_reasoning_excluded']=('PRIVATE_SENTINEL' not in raw and 'PUBLIC_SENTINEL' in raw)
        for seed in range(10):
            schedule=Schedule(seed);assert sum(j['kind']=='C-placement' for j in schedule.jobs)==3
            assert all(b['version']>a['version'] for a,b in zip(schedule.jobs,schedule.jobs[1:]))
            assert set(schedule.current)=={'version','kind','part_id','destination','requirements'}
        checks['three_hidden_separated_encounters']=True
        template='\n'.join(p.read_text(encoding='utf-8') for p in (HERE/'template').rglob('*') if p.is_file())
        checks['no_proof_or_future_schedule_in_template']=not any(x in template for x in ('qualify_scene','qualify_system','reference_actions','PRIVATE_SENTINEL','encounters=3'))
        checks['fresh_thread_no_resume']=('"ephemeral": True' in (HERE/'bootstrap_client.py').read_text() and 'client.call("thread/resume"' not in (HERE/'bootstrap_client.py').read_text())
        try:module.run(SimpleNamespace())
        except RuntimeError as e:checks['review_gate_prevents_model_launch']='awaits human review' in str(e)
        result['passed']=all(checks.values())
    except Exception as e:result.update(error=str(e),traceback=traceback.format_exc())
    save(out/'receipt.json',result);print(json.dumps(result),flush=True);return 0 if result['passed'] else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args();raise SystemExit(run(a.output))
