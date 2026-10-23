"""Queue-only, one-pass C0-007/B6 development incident extraction.

No raw read until official successful receipt and canonical development result
binding are available. Never changes originals, map, Runtime or frame images.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
import hashlib
import importlib
import json
import math
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parent.parent
RUNTIME=PROJECT/'Runtime'
INVESTIGATION=PROJECT/'Engineering Investigation'
RUN_ID='B01-dev-C0-007'
TARGET='B6'
INSPECTED_CANDIDATE_SHA256='fc101b3a79a4f647735f396d8938cb6156e180566d114eb5e46f8c8659e89c47'
MAX_INCIDENTS=16
HISTORY=32


def require(condition, reason):
    if not condition:raise ValueError(reason)


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def finite(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
def signature(path):
    stat=Path(path).stat();return (stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)


def fresh(item):
    """Mirror the pinned candidate visibility filter, not object existence."""
    return (isinstance(item,dict) and isinstance(item.get('id'),str) and finite(item.get('age_s'))
        and 0<=item['age_s']<=1.5 and item.get('family') in ('A','B') and item.get('kind','part')=='part'
        and item.get('zone') in ('raw','fixture','parking1','parking2','inspection','tray1','tray2','tray3','quarantine')
        and isinstance(item.get('pos'),list) and len(item['pos'])==3 and all(finite(v) for v in item['pos']))


def packet_view(packet):
    detections=packet.get('detections',[])
    target=[row for row in detections if row.get('id')==TARGET]
    visible=[{key:row.get(key) for key in ('id','kind','family','zone','pos','visible_mark','age_s')}
             for row in detections if fresh(row)]
    return {**{key:packet.get(key) for key in ('incarnation','sequence','capture_sequence','capture_sim_time_s','sim_time',
        'camera_frame_age_sim_s','camera_metadata_status','order','station','gripper','human_answers','inspection','last_feedback','process_contract')},
        'target_detections':target,'target_presence':'reported' if target else 'absent_from_packet',
        'fresh_target':any(fresh(row) for row in target),'fresh_visible_parts':visible,
        'fresh_visible_count':len(visible),'detected_count':len(detections),
        'raw_mark_fresh_stock_ids':[row['id'] for row in visible if row['zone'] in ('raw','parking1','parking2') and row['visible_mark']=='raw'],
        'stock_scope':'visibility/mark only; retained cycles and current per-requirement counts remain separate'}


def checkpoint(event):
    text=event.get('content_utf8')
    if not isinstance(text,str):return {'state':'unavailable','reason':'no restored checkpoint text','declared_sha256':event.get('sha256')}
    raw=text.encode('utf-8')
    require(hashlib.sha256(raw).hexdigest()==event.get('sha256') and len(raw)==event.get('byte_count'),'candidate checkpoint byte identity differs')
    envelope=json.loads(text);state=envelope['state']
    require(hashlib.sha256(json.dumps(state,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
            ==envelope.get('sha256'),'candidate checkpoint state hash differs')
    fields=('family','last_seen','cycle','inspection','eligibility_inference')
    return {'state':'retained_candidate_belief','checkpoint_sha256':event['sha256'],'state_sha256':envelope['sha256'],
        'target_part':state.get('parts',{}).get(TARGET),
        **{key:state.get(key) for key in ('pending','halted','last_error','failure_counts','received_human_answer_ids','recent_resolutions','order','fixture_belief')},
        'parts_for_current_count_reconstruction':{identity:{key:value.get(key) for key in fields} for identity,value in state.get('parts',{}).items()},
        'counts_note':'No count is inferred from completed history alone; current fresh tray visibility and retained proof must agree.'}


def locator(row,number,offset,raw,index=None):
    ref={'event_id':row['event_id'],'event_type':row['event_type'],'line':number,'byte_offset':offset,
         'line_bytes':len(raw),'line_sha256':hashlib.sha256(raw).hexdigest(),'payload_sha256':row['payload_sha256'],
         'parent_ids':row.get('parent_ids',[]),'sim_time_s':row.get('sim_time_s'),'wall_elapsed_s':row.get('wall_elapsed_s')}
    if index is not None:ref.update(candidate_event_index=index,json_pointer='/payload/events/'+str(index))
    return ref


def frame_refs(payload):
    return {'paths':{key:payload[key] for key in ('rgb','depth') if key in payload},
            'artifacts':payload.get('artifacts',{}),'scope':'existing frame references only; images not opened or edited'}


def scan_events(path,expected_sha256):
    """Exactly one events byte stream/JSON pass; bounded incident projections."""
    path=Path(path);before=signature(path);hasher=hashlib.sha256();offset=0;previous_id=0
    inputs={};observations={};history=deque(maxlen=HISTORY);history_total=0;epoch=None
    recent=deque(maxlen=4);incidents=[];incident_count=0;counts=Counter();checkpoint_latest=None
    last_target=None;last_fresh=None;last_observation=None;last_step=None;final_world=None;first_world=None
    truncated_incidents=0
    with path.open('rb') as stream:
        for number,raw in enumerate(stream,1):
            hasher.update(raw);row=json.loads(raw)
            require(row.get('run_id')==RUN_ID and row.get('schema_version')=='robot-evidence-1.0','event run/schema differs')
            require(type(row.get('event_id')) is int and row['event_id']>previous_id,'event IDs are not increasing')
            previous_id=row['event_id'];payload=row['payload'];kind=row['event_type']
            require(digest(payload)==row.get('payload_sha256'),'event payload hash differs at line '+str(number))
            ref=locator(row,number,offset,raw);offset+=len(raw);counts[kind]+=1
            compact={'source':ref,'kind':kind}
            for incident in incidents:
                if len(incident['after_events'])<4 and row['event_id']>incident['anchor']['event_id']:
                    incident['after_events'].append(compact)
            if kind=='observation':
                view={'source':ref,'packet':packet_view(payload.get('packet',{})),'frames':frame_refs(payload)}
                seq=view['packet']['sequence'];observations[seq]=view
                if len(observations)>64:observations.pop(next(iter(observations)))
                last_observation=view
                if view['packet']['target_detections']:last_target=view
                if view['packet']['fresh_target']:
                    last_fresh=view
                    for incident in incidents:
                        if incident.get('first_following_fresh_target') is None:incident['first_following_fresh_target']=view
                compact['observation']=view
            elif kind=='candidate_input':
                message=payload.get('message',{});item={'source':ref,'message_type':message.get('type')}
                if message.get('type')=='step':
                    item['packet']=packet_view(message['packet']);item['observation']=observations.get(item['packet']['sequence']);last_step=item
                elif message.get('type')=='feedback':item['feedback']=message.get('feedback')
                inputs[row['event_id']]=item
                require(len(inputs)<=128,'unexpected unbounded unmatched candidate input backlog')
                compact['candidate_input']=item
            elif kind=='candidate_reply':
                parent=payload.get('supervisor_input_event_id');input_record=inputs.pop(parent,None)
                event_list=payload.get('events',[])
                # Context writes can follow action_intent in the same reply; retain the resulting checkpoint too.
                for index,event in enumerate(event_list):
                    if event.get('type') in ('context_write','context_read'):
                        checkpoint_latest={'source':locator(row,number,ref['byte_offset'],raw,index),'projection':checkpoint(event)}
                for index,event in enumerate(event_list):
                    event_type=event.get('type');source=locator(row,number,ref['byte_offset'],raw,index)
                    reset=event_type=='public_human_answer_received' or (event_type=='candidate_action_resolution' and event.get('resolved') is True)
                    if reset:history.clear();history_total=0;epoch={'source':source,'event':event}
                    if event_type not in ('action_intent','scheduler_action_rejected','action_rejected_locally','public_human_answer_received','candidate_action_resolution'):continue
                    decision={'source':source,'event':event,'candidate_input':input_record}
                    action=event.get('action',event.get('proposed_action',{}));op=action.get('operation')
                    anchor=(event_type in ('scheduler_action_rejected','action_rejected_locally') or event_type=='action_intent' and op=='help')
                    if anchor:
                        incident_count+=1
                        incident={'anchor':source,'event':event,'candidate_input':input_record,'checkpoint':checkpoint_latest,
                            'idle_epoch_start':epoch,'preceding_decisions':list(history),'preceding_decisions_total':history_total,
                            'preceding_decisions_omitted':max(0,history_total-len(history)),
                            'before_events':list(recent),'after_events':[],'last_target_detection':last_target,
                            'last_fresh_target_detection':last_fresh,'last_observation':last_observation,'first_following_fresh_target':None,
                            'correlated_service_events':[],'after_decisions':[]}
                        if len(incidents)==MAX_INCIDENTS:
                            incidents.pop(MAX_INCIDENTS//2);truncated_incidents+=1
                        incidents.append(incident)
                    for incident in incidents:
                        if incident['anchor']['event_id']<row['event_id'] and len(incident['after_decisions'])<4:incident['after_decisions'].append(decision)
                    history.append(decision);history_total+=1
                compact['reply']={'supervisor_input_event_id':parent,'event_types':[v.get('type') for v in event_list]}
            elif kind in ('help_requested','scripted_human_answer','action_requested','action_admission'):
                compact['payload']=payload
                for incident in incidents:
                    request=(incident['event'].get('action') or incident['event'].get('proposed_action') or {}).get('request_id')
                    action_request=payload.get('request_id')
                    if request is not None and action_request==request or kind=='scripted_human_answer':
                        incident['correlated_service_events'].append({'source':ref,'payload':payload})
            elif kind in ('world_snapshot','final_world'):
                protected={'source':ref,'target_truth':payload.get('objects',{}).get(TARGET),
                           'payload':payload if kind=='final_world' else None,'scope':'protected world evidence, never candidate observation'}
                if first_world is None:first_world=protected
                if kind=='final_world':final_world=protected
            recent.append(compact)
    actual=hasher.hexdigest();after=signature(path)
    require(actual==expected_sha256,'streamed original differs from canonical preexisting events hash')
    require(before==after and offset==before[0],'original events changed during the single stream pass')
    return {'schema_version':'development-incident-extraction-1','run_id':RUN_ID,'target':TARGET,
        'events_source':{'path':str(path.resolve()),'before_canonical_sha256':expected_sha256,'after_stream_sha256':actual,
                         'before_stat':before,'after_stat':after,'bytes':offset,'lines':sum(counts.values()),'json_stream_passes':1},
        'event_type_counts':dict(counts),'incidents':incidents,'incident_count':incident_count,'omitted_middle_incidents':truncated_incidents,
        'last_target_detection':last_target,'last_fresh_target_detection':last_fresh,'last_observation':last_observation,
        'last_candidate_step':last_step,'last_checkpoint':checkpoint_latest,'first_protected_world':first_world,'final_protected_world':final_world,
        'scope':'development diagnosis only; detection absence does not prove movement/occlusion; no task outcome or map changes',
        'limits':['Bounded first/last incident selection and 32 preceding decisions; omitted counts are explicit.',
                  'Frame references are retained without opening or modifying image bytes.',
                  'Fresh filter mirrors source rule; raw stock visibility alone does not establish scheduler eligibility.',
                  'Final protected position cannot alone establish visibility at an earlier camera time.']}


def process(receipt_path,output):
    # Purpose-built existing read-only queue/map/receipt authority; no queue CLI.
    sys.path[:0]=[str(INVESTIGATION),str(RUNTIME)]
    dev=importlib.import_module('process_development');authority=importlib.import_module('release_runner')
    owner=authority.queued_job(expected_script=__file__)
    receipts=dev.receipt_files([receipt_path],authority)
    data,map_source=dev.read_map(dev.MAP)
    runs=[r for r in data['run'] if r['id']==RUN_ID]
    require(len(runs)==1 and runs[0].get('stage')=='development','canonical development registration missing')
    result=dev.current_result(data,RUN_ID);job=result.get('details',{}).get('queue_job_id')
    require(result.get('execution_status') in dev.TERMINAL and job in receipts,'canonical terminal result lacks matching official receipt')
    root=(dev.EVIDENCE/RUN_ID).resolve();output=Path(output).resolve()
    require(root.parent==dev.EVIDENCE.resolve() and all((root/name).resolve().parent==root for name in ('manifest.json','result.json','events.jsonl')),
            'raw run/source escaped its canonical evidence directory')
    require(not output.exists() and not any(output.is_relative_to(p.resolve()) for p in (dev.MAP,dev.EVIDENCE,RUNTIME)),
            'fresh output must be outside originals/map/Runtime')
    require('candidate_state' not in (p.casefold() for p in output.parts),'output cannot be candidate state')
    metadata={name:dev.ref(root/name) for name in ('manifest.json','result.json')}
    manifest=dev.object_file(root/'manifest.json');raw_result=dev.object_file(root/'result.json')
    require(all(v.get('run_id')==RUN_ID and v.get('stage')=='development' for v in (manifest,raw_result)), 'raw development identity differs')
    require(manifest.get('code_sha256',{}).get('candidates.py')==INSPECTED_CANDIDATE_SHA256,
            'candidate source differs from the inspected visibility rule; review extractor before using it')
    require(raw_result.get('execution_status') in dev.TERMINAL,'raw development result is not terminal')
    def bound(name):
        matches=[v for v in result.get('evidence',[]) if v.get('state')=='available' and isinstance(v.get('uri'),str)
                 and (dev.MAP/v['uri']).resolve()==(root/name).resolve()]
        require(len(matches)==1 and isinstance(matches[0].get('sha256'),str),'canonical source binding missing: '+name)
        return matches[0]['sha256']
    require(bound('result.json')==metadata['result.json']['sha256'],'canonical raw result bytes differ')
    method={str(path):dev.ref(path) for path in (Path(__file__),INVESTIGATION/'process_development.py',RUNTIME/'release_runner.py')}
    report=scan_events(root/'events.jsonl',bound('events.jsonl'))
    dev.check_sources(metadata);dev.check_sources(method);dev.check_sources({k:v['source'] for k,v in receipts.items()})
    _,after_map=dev.read_map(dev.MAP);require(map_source==after_map,'canonical map changed during extraction')
    report.update(extraction_queue_job_id=owner['id'],execution_queue_job_id=job,execution_receipt=receipts[job]['source'],
                  canonical_map=map_source,canonical_result_id=result['id'],canonical_outcome=result.get('outcome'),
                  immutable_raw_outcome=raw_result.get('outcome'),metadata_sources=metadata,method_sources=method,
                  raw_source_code_sha256=manifest.get('code_sha256'),candidate_freshness_filter_source='candidates.py _ingest age<=1.5; source identity retained')
    output.mkdir(parents=True,exist_ok=False);dev.write_once(output/'incident.json',report)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--receipt',required=True);parser.add_argument('--output-dir',required=True)
    args=parser.parse_args(argv);report=process(args.receipt,args.output_dir)
    print(json.dumps({'output':str(Path(args.output_dir).resolve()),'run_id':RUN_ID,'target':TARGET,
                      'incidents':report['incident_count'],'omitted':report['omitted_middle_incidents'],'originals_unchanged':True}))


if __name__=='__main__':main()
