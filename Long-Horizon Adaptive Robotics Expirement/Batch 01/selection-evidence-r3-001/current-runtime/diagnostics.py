"""Evidence-derived episode diagnostics; no simulator/model, scoring or map writes.

CLI: diagnostics.py --episode-dir <protected run> --output <new summary.json>
Use the shared compute queue for sustained analysis of large evidence streams.
Source files and this implementation are SHA-256 identified. Invalid JSON,
changed inputs, event payload-hash failures and nonmonotonic motion are refused.
Missing measurements remain null. Outputs are operator evidence, never candidate
inputs; this program does not copy prompts, model text, retained state or seeds.

Frozen method robot-motion-diagnostics-1.0: nominal 100 Hz position samples;
centered five-sample moving average with valid support (two samples trimmed at
each boundary); successive first finite differences, each placed at its pair's
time midpoint; trapezoidal integral of squared Cartesian jerk. No interpolation,
gap bridging or endpoint padding. The integral covers the filter/difference
interior, whose duration is retained. T is dispatch-to-terminal simulation time;
L is raw sampled TCP path length over that complete trajectory. Report
T**5/L**2 * integral(||jerk||**2 dt), with the same explicit interior coverage.
Omit normalized jerk below L=1 mm, and all jerk on gaps, short, interrupted,
unmatched or incomplete trajectories. Completion means trajectory feedback,
not verified part transfer. Joint travel and path lengths are sampled lower
bounds; extrema are 100 Hz observations, not native physics-rate extrema.

Low-motion intervals require filtered TCP speed <1 mm/s AND maximum filtered
joint speed <0.01 rad/s for strictly more than 0.25 simulation seconds. Eligibility
and causal labels are unknown without explicit interval annotations. Inference
or machine-busy overlap alone never proves why motion paused. No hidden chain
of thought, avoidability, recognition, successful recovery or optimal reference
path is inferred. All thresholds/formulas must be frozen before scored use.
"""
from __future__ import annotations

import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np

METHOD='robot-motion-diagnostics-1.0'
DT=.01
DT_TOLERANCE_S=1e-5
FILTER_SAMPLES=5
NEAR_ZERO_PATH_M=.001
PAUSE_TCP_M_S=.001
PAUSE_JOINT_RAD_S=.01
PAUSE_MIN_S=.25


class DiagnosticError(ValueError):pass


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def finite(value):return type(value) in (int,float) and math.isfinite(value)
def metric(value,unit,basis,reason=None):
    return {'value':value,'unit':unit,'basis':basis,'missing_reason':reason if value is None else None}
def missing(unit,reason):return metric(None,unit,'not established by supplied evidence',reason)
def event_time(event):
    payload=event.get('payload',{})
    time=payload.get('sim_time') if event.get('event_type')=='physical_service_event' else event.get('sim_time_s')
    return float(time) if finite(time) else None
def service(event):return event.get('payload',{}) if event.get('event_type')=='physical_service_event' else {}
def duration_overlap(a,b,c,d):return max(0.,min(b,d)-max(a,c))
def union_duration(intervals):
    end=None;total=0.
    for a,b in sorted((a,b) for a,b in intervals if finite(a) and finite(b) and b>=a):
        total+=max(0.,b-max(a,end)) if end is not None else b-a
        end=max(end,b) if end is not None else b
    return total


def vector(row,key,size):
    value=row.get(key)
    return value if isinstance(value,list) and len(value)==size and all(finite(v) for v in value) else None


def moving_average(times,values):
    times=np.asarray(times,dtype=float);values=np.asarray(values,dtype=float)
    if len(times)<FILTER_SAMPLES:return np.array([]),np.empty((0,values.shape[1]))
    filtered=np.stack([np.mean(values[i:i+FILTER_SAMPLES],axis=0) for i in range(len(values)-FILTER_SAMPLES+1)])
    return times[2:-2],filtered


def difference(times,values):
    if len(times)<2:return np.array([]),np.empty((0,values.shape[1]))
    return (times[:-1]+times[1:])/2,np.diff(values,axis=0)/np.diff(times)[:,None]


def derivatives(times,values):
    t,p=moving_average(times,values);tv,v=difference(t,p);ta,a=difference(tv,v);tj,j=difference(ta,a)
    return {'position_time':t,'position':p,'velocity_time':tv,'velocity':v,'acceleration_time':ta,
            'acceleration':a,'jerk_time':tj,'jerk':j}


def regular_blocks(motion):
    if not motion:return []
    blocks=[];start=0
    for index in range(1,len(motion)):
        delta=motion[index]['sim_time_s']-motion[index-1]['sim_time_s']
        if delta<=0:raise DiagnosticError('Motion times must strictly increase')
        if abs(delta-DT)>DT_TOLERANCE_S:blocks.append(motion[start:index]);start=index
    blocks.append(motion[start:]);return blocks


def motion_metrics(motion):
    if any(not finite(row.get('sim_time_s')) for row in motion):raise DiagnosticError('Motion sample lacks finite simulation time')
    blocks=regular_blocks(motion);n=len(motion)
    output={'sample_count':n,'regular_block_count':len(blocks),'non_nominal_sample_intervals':max(0,len(blocks)-1),
            'nominal_sample_period_s':DT,'sample_period_tolerance_s':DT_TOLERANCE_S,
            'first_sim_time_s':motion[0]['sim_time_s'] if motion else None,'last_sim_time_s':motion[-1]['sim_time_s'] if motion else None,
            'maximum_sample_gap_s':max((b['sim_time_s']-a['sim_time_s'] for a,b in zip(motion,motion[1:])),default=None)}
    path=0.;joint=np.zeros(7);path_pairs=0;joint_pairs=0;peak_speed=[];peak_accel=[];tcp_speed=[];tcp_accel=[];pauses=[];pause_support=0.
    for block in blocks:
        for a,b in zip(block,block[1:]):
            if vector(a,'tcp',3) is not None and vector(b,'tcp',3) is not None:path+=float(np.linalg.norm(np.subtract(b['tcp'],a['tcp'])));path_pairs+=1
            if vector(a,'q',7) is not None and vector(b,'q',7) is not None:joint+=np.abs(np.subtract(b['q'],a['q']));joint_pairs+=1
        times=[r['sim_time_s'] for r in block]
        q=derivatives(times,[r['q'] for r in block]) if block and all(vector(r,'q',7) is not None for r in block) else None
        tcp=derivatives(times,[r['tcp'] for r in block]) if block and all(vector(r,'tcp',3) is not None for r in block) else None
        if q:
            if len(q['velocity']):peak_speed.append(np.max(np.abs(q['velocity']),axis=0))
            if len(q['acceleration']):peak_accel.append(np.max(np.abs(q['acceleration']),axis=0))
        if tcp:
            if len(tcp['velocity']):tcp_speed.append(float(np.max(np.linalg.norm(tcp['velocity'],axis=1))))
            if len(tcp['acceleration']):tcp_accel.append(float(np.max(np.linalg.norm(tcp['acceleration'],axis=1))))
        if q and tcp and len(q['velocity'])==len(tcp['velocity']):
            low=(np.max(np.abs(q['velocity']),axis=1)<PAUSE_JOINT_RAD_S)&(np.linalg.norm(tcp['velocity'],axis=1)<PAUSE_TCP_M_S) if len(q['velocity']) else []
            begin=None;vt=q['velocity_time']
            if len(vt)>1:pause_support+=float(vt[-1]-vt[0])
            for index,is_low in enumerate([*low,False]):
                if is_low and begin is None:begin=index
                if not is_low and begin is not None:
                    a,b=float(vt[begin]),float(vt[index-1])
                    if b-a>PAUSE_MIN_S:pauses.append({'start_sim_s':a,'end_sim_s':b,'duration_s':b-a})
                    begin=None
    reason='No valid adjacent samples; missing values and gaps are never bridged'
    output['tcp_path_m']=metric(path if path_pairs else None,'m','Sum of raw TCP distances within regular sampled blocks; lower bound',reason)
    output['joint_travel_rad']=metric(joint.tolist() if joint_pairs else None,'rad per joint','Sum of absolute raw q differences within regular sampled blocks; lower bound',reason)
    output['joint_travel_total_rad']=metric(float(joint.sum()) if joint_pairs else None,'rad','Sum across seven joint-travel values',reason)
    output['path_adjacent_pairs']=path_pairs;output['joint_adjacent_pairs']=joint_pairs
    output['pause_analyzable_time_s']=pause_support
    for name,values,unit in (('filtered_joint_speed_peak',peak_speed,'rad/s per joint'),('filtered_joint_acceleration_peak',peak_accel,'rad/s^2 per joint')):
        output[name]=metric(np.max(values,axis=0).tolist() if values else None,unit,'Five-sample position filter then finite differences; sampled peak','Insufficient complete joint position data')
    for name,values,unit in (('filtered_tcp_speed_peak',tcp_speed,'m/s'),('filtered_tcp_acceleration_peak',tcp_accel,'m/s^2')):
        output[name]=metric(max(values) if values else None,unit,'Five-sample position filter then finite differences; sampled peak','Insufficient complete TCP position data')
    for key,name,unit in (('dq','telemetry_joint_speed_peak','rad/s per joint'),('effort','sampled_effort_peak','N*m per joint')):
        values=[r[key] for r in motion if vector(r,key,7) is not None]
        output[name]=metric(np.max(np.abs(values),axis=0).tolist() if values else None,unit,'Absolute maximum among recorded 100 Hz values; may miss between-sample peaks','Telemetry is absent')
        output[name]['observed_samples']=len(values);output[name]['missing_samples']=n-len(values)
    errors=[np.subtract(r['target'],r['q']) for r in motion if vector(r,'target',7) is not None and vector(r,'q',7) is not None]
    output['joint_tracking_rms']=metric(np.sqrt(np.mean(np.square(errors),axis=0)).tolist() if errors else None,'rad per joint','Recorded target minus q; target meaning follows frozen controller','Targets or positions absent')
    output['joint_tracking_peak_abs']=metric(np.max(np.abs(errors),axis=0).tolist() if errors else None,'rad per joint','Recorded target minus q at 100 Hz','Targets or positions absent')
    output['effort_saturation']=missing('count','Actuator limits and native-rate threshold crossing evidence are not supplied')
    output['starts_stops_reversals']=missing('count','Calibrated hysteresis/dwell thresholds and matched-motion interpretation are not frozen in this method')
    return output,pauses


def jerk_for_segment(rows,start,end):
    result={'squared_jerk_integral':missing('m^2/s^5','Unmeasured'),'dimensionless_jerk':missing('dimensionless','Unmeasured'),
            'duration_s':end-start,'sample_count':len(rows),'path_length_m':None,'analysis_support_s':None,'omission_reason':None}
    reason=None
    if len(rows)<9:reason='Fewer than nine samples for filtered third differences and integration'
    elif rows[0]['sim_time_s']-start>DT+DT_TOLERANCE_S or end-rows[-1]['sim_time_s']>DT+DT_TOLERANCE_S:reason='Motion evidence does not cover both trajectory endpoints'
    elif len(regular_blocks(rows))!=1:reason='Non-nominal sample gap inside trajectory'
    elif not all(vector(r,'tcp',3) is not None for r in rows):reason='TCP samples missing inside trajectory'
    if reason:
        result['omission_reason']=reason
        result['squared_jerk_integral']=missing('m^2/s^5',reason);result['dimensionless_jerk']=missing('dimensionless',reason);return result
    times=np.array([r['sim_time_s'] for r in rows]);positions=np.array([r['tcp'] for r in rows])
    length=float(np.sum(np.linalg.norm(np.diff(positions,axis=0),axis=1)));derived=derivatives(times,positions)
    tj=derived['jerk_time'];j=derived['jerk'];squared=np.sum(j*j,axis=1)
    integral=float(np.sum((squared[1:]+squared[:-1])*.5*np.diff(tj)))
    support=float(tj[-1]-tj[0]);result.update(path_length_m=length,analysis_support_s=support,
        analysis_start_sim_s=float(tj[0]),analysis_end_sim_s=float(tj[-1]),
        excluded_boundary_duration_s=max(0.,end-start-support),interior_coverage_fraction=support/(end-start))
    result['squared_jerk_integral']=metric(integral,'m^2/s^5','Trapezoidal squared-jerk integral on valid-filter/difference interior of completed trajectory')
    reason='Sampled path is below the frozen 1 mm normalization threshold' if length<NEAR_ZERO_PATH_M else None
    result['dimensionless_jerk']=metric(None if reason else (end-start)**5/length**2*integral,'dimensionless','T^5/L^2 times measured interior squared-jerk integral; T=dispatch-to-terminal, L=raw sampled TCP path',reason)
    result['omission_reason']=reason;return result


def transport_metrics(events,motion):
    actions={};dispatches=defaultdict(list);feedback=defaultdict(list);interruptions=[]
    for event in events:
        kind=event['event_type'];payload=event['payload'];sv=service(event)
        if kind=='action_requested' and payload.get('operation')=='transport':actions.setdefault(payload.get('request_id'),event)
        if sv.get('type')=='trajectory_dispatched':dispatches[sv.get('request_id')].append(event)
        if sv.get('type')=='feedback':feedback[sv.get('request_id')].append(event)
        if kind=='restart_begin' or sv.get('type') in ('command_expired','lease_expired','safety_stop','command_cancelled','command_superseded'):interruptions.append(event)
    output=[]
    for rid,action in actions.items():
        row={'request_id':rid,'action_event_id':action['event_id'],'part_id':action['payload'].get('part_id'),
             'destination':action['payload'].get('destination'),'physical_transfer_success':None,
             'physical_transfer_missing_reason':'Trajectory acknowledgement is not an independent physical transfer predicate'}
        ds=dispatches.get(rid,[]);ends=feedback.get(rid,[])
        reason=None;start=None;end=None
        if len(ds)!=1:reason='Exactly one matched physical trajectory dispatch is required'
        else:
            start=event_time(ds[0]);terminal=[e for e in ends if start is not None and event_time(e) is not None and event_time(e)>=start]
            if start is None:reason='Physical dispatch lacks its actual simulation timestamp'
            elif len(terminal)!=1:reason='Exactly one terminal physical feedback event is required'
            else:
                endpoint=terminal[0];end=event_time(endpoint);row['terminal_event_id']=endpoint['event_id']
                if service(endpoint).get('status')!='completed':reason='Trajectory did not complete: '+str(service(endpoint).get('status'))
                elif end<=start:reason='Nonpositive trajectory duration'
                elif any(start<=event_time(e)<=end and (not service(e).get('request_id') or service(e).get('request_id')==rid) for e in interruptions if event_time(e) is not None):reason='Restart, expiry, cancellation or safety intervention overlaps trajectory'
        row.update(start_sim_s=start,end_sim_s=end,complete_uninterrupted=reason is None,
                   dispatch_event_id=ds[0]['event_id'] if len(ds)==1 else None)
        if reason:row['motion']={'omission_reason':reason,'squared_jerk_integral':missing('m^2/s^5',reason),'dimensionless_jerk':missing('dimensionless',reason)}
        else:row['motion']=jerk_for_segment([r for r in motion if start-1e-9<=r['sim_time_s']<=end+1e-9],start,end)
        output.append(row)
    usable=[r for r in output if r['motion']['dimensionless_jerk']['value'] is not None]
    return {'requested_transport_count':len(output),'complete_uninterrupted_count':sum(r['complete_uninterrupted'] for r in output),
            'normalized_jerk_usable_count':len(usable),'normalized_jerk_omitted_count':len(output)-len(usable),'segments':output,
            'comparison_warning':'Compare matched source/destination, payload and obstacle conditions; no reference optimum or aggregate winner is inferred'}


def model_metrics(events):
    requests={e['event_id']:e for e in events if e['event_type']=='model_request'}
    terminals=defaultdict(list);unlinked=[]
    for event in events:
        if event['event_type'] not in ('model_response','late_model_response','model_error','stale_model_error_discarded'):continue
        linked=[p for p in event.get('parent_ids',[]) if p in requests]
        if len(linked)!=1:unlinked.append(event['event_id'])
        else:terminals[linked[0]].append(event)
    calls=[];intervals=[]
    for event_id,request in requests.items():
        finishes=terminals[event_id];terminal=finishes[0] if len(finishes)==1 else None
        reply=terminal['payload'].get('result',{}) if terminal else {};usage=reply.get('usage',{})
        end=event_time(terminal) if terminal else None;start=event_time(request)
        if start is not None:intervals.append({'start':start,'end':end,'event_ids':[event_id]+([terminal['event_id']] if terminal else [])})
        latency=reply.get('latency_s',reply.get('latency'))
        def token(name,fallback=None):
            value=usage.get(name,reply.get(name,fallback));return value if type(value) is int and value>=0 else None
        tokens=token('total_tokens',reply.get('tokens'));cached=(usage.get('prompt_tokens_details') or {}).get('cached_tokens')
        calls.append({'request_event_id':event_id,'terminal_event_id':terminal['event_id'] if terminal else None,
            'terminal_kind':terminal['event_type'] if terminal else None,'missing_reason':None if terminal else 'Missing or multiply linked terminal model event',
            'latency_s':latency if finite(latency) and latency>=0 else None,
            'gateway_elapsed_wall_s':terminal['wall_elapsed_s']-request['wall_elapsed_s'] if terminal and finite(terminal.get('wall_elapsed_s')) and finite(request.get('wall_elapsed_s')) and terminal['wall_elapsed_s']>=request['wall_elapsed_s'] else None,
            'prompt_tokens':token('prompt_tokens'),'completion_tokens':token('completion_tokens'),'total_tokens':tokens,
            'cached_prompt_tokens':cached if type(cached) is int and cached>=0 else None,
            'prompt_cache_configured':reply.get('identity',{}).get('prompt_cache_enabled'),
            'after_episode_end':terminal['payload'].get('after_episode_end') if terminal else None,
            'stale':terminal['payload'].get('stale') if terminal else None,
            'prompt_sha256':hashlib.sha256(canonical(request['payload'].get('messages'))).hexdigest() if 'messages' in request['payload'] else None})
    known=sum(c['total_tokens'] for c in calls if c['total_tokens'] is not None)
    unknown=sum(c['total_tokens'] is None for c in calls)
    caches=[c['cached_prompt_tokens'] for c in calls]
    latencies=[c['latency_s'] for c in calls if c['latency_s'] is not None]
    return {'observed_request_count':len(requests),'calls':calls,'unlinked_terminal_event_ids':unlinked,
            'latency_summary_s':{'observed_calls':len(latencies),'missing_calls':len(calls)-len(latencies),
                'mean':float(np.mean(latencies)) if latencies else None,'median':float(np.median(latencies)) if latencies else None,
                'p95':float(np.percentile(latencies,95)) if latencies else None,'maximum':max(latencies) if latencies else None,
                'scope':'Measured per-call latency only; missing/failed-call latencies excluded and counted'},
            'known_total_tokens':known,'calls_with_unknown_tokens':unknown,
            'total_tokens':metric(known if unknown==0 and not unlinked else None,'tokens','Sum of uniquely linked terminal usage counters','One or more calls has missing/ambiguous token accounting'),
            'cached_prompt_tokens':metric(sum(caches) if all(v is not None for v in caches) and not unlinked else None,'tokens','Measured cached token counters; disabled cache configuration alone is not a measurement','No complete measured cache token counters'),
            'cache_hit_calls':metric(sum(v>0 for v in caches) if all(v is not None for v in caches) and not unlinked else None,'calls','Calls with measured cached_prompt_tokens >0','Cache use was not measured completely')},intervals


def process_metrics(events,episode_end):
    starts={};ends=defaultdict(list)
    for event in events:
        sv=service(event);cid=sv.get('cycle_id')
        if cid is None:continue
        if sv.get('type')=='feedback' and sv.get('reason')=='cycle accepted' and sv.get('status')=='completed':starts.setdefault(cid,event)
        if sv.get('type') in ('cycle_complete','cycle_fault'):ends[cid].append(event)
    intervals=[]
    for cid,start in starts.items():
        a=event_time(start);valid=[e for e in ends[cid] if a is not None and event_time(e) is not None and event_time(e)>=a]
        terminal=min(valid,key=event_time) if valid else None;b=event_time(terminal) if terminal else episode_end
        intervals.append({'cycle_id':cid,'start_sim_s':a,'end_sim_s':b,'right_censored':terminal is None,
            'start_event_id':start['event_id'],'end_event_id':terminal['event_id'] if terminal else None,
            'terminal_type':service(terminal).get('type') if terminal else None})
    known=[(r['start_sim_s'],r['end_sim_s']) for r in intervals if r['start_sim_s'] is not None and r['end_sim_s'] is not None]
    overlaps=sum(duration_overlap(a,b,c,d)>0 for index,(a,b) in enumerate(known) for c,d in known[index+1:])
    return {'accepted_cycle_count':len(starts),'intervals':intervals,
            'observed_busy_time':metric(union_duration(known) if len(known)==len(intervals) else None,'s simulation','Union of accepted cycle intervals through cycle_complete/fault or episode end; unfinished cycles right-censored','Some cycle intervals lack a start/end timestamp'),
            'known_busy_time_s':union_duration(known),
            'overlapping_cycle_interval_pairs':overlaps,
            'productive_utilization':missing('fraction','Eligible available machine time and correct-process contribution are not established'),
            'unmatched_terminal_cycle_events':sum(len(rows) for cid,rows in ends.items() if cid not in starts)}


def annotate_pauses(pauses,model_intervals,processes,events,episode_end):
    result=[]
    annotations=[e for e in events if e['event_type']=='pause_annotation'
                 and e.get('source') in ('evaluator','gateway','supervisor','operator_annotation')
                 and isinstance(e['payload'].get('basis'),str) and e['payload']['basis'].strip()]
    for raw in pauses:
        row=dict(raw);a,b=row['start_sim_s'],row['end_sim_s'];labels=[];support=[]
        for annotation in annotations:
            p=annotation['payload']
            if not finite(p.get('start_sim_s')) or not finite(p.get('end_sim_s')):continue
            if p['start_sim_s']<=a and p['end_sim_s']>=b and p.get('category') in ('physical_required','inference_wait','reasoning_wait','planning_wait'):
                labels.append(p['category']);support.append(annotation['event_id'])
        eligible=[e['payload']['work_eligible'] for e in annotations if type(e['payload'].get('work_eligible')) is bool and finite(e['payload'].get('start_sim_s')) and finite(e['payload'].get('end_sim_s')) and e['payload']['start_sim_s']<=a and e['payload']['end_sim_s']>=b]
        inference=[(max(a,r['start']),min(b,r['end'] if r['end'] is not None else episode_end)) for r in model_intervals if episode_end is not None and duration_overlap(a,b,r['start'],r['end'] if r['end'] is not None else episode_end)>0]
        process=[(max(a,r['start_sim_s']),min(b,r['end_sim_s'])) for r in processes['intervals'] if r['start_sim_s'] is not None and r['end_sim_s'] is not None and duration_overlap(a,b,r['start_sim_s'],r['end_sim_s'])>0]
        row.update(causal_labels=sorted(set(labels)) if labels else ['unknown'],label_event_ids=support,
            work_eligible=eligible[0] if eligible and all(v==eligible[0] for v in eligible) else None,
            model_wait_overlap_s=union_duration(inference),machine_busy_overlap_s=union_duration(process),
            overlap_interpretation='Concurrent activity only; neither overlap proves required idleness or its cause')
        result.append(row)
    return {'intervals':result,'observed_low_motion_time_s':union_duration([(r['start_sim_s'],r['end_sim_s']) for r in result]),
            'eligible_pause_time':metric(sum(r['duration_s'] for r in result if r['work_eligible']) if all(r['work_eligible'] is not None for r in result) else None,'s simulation','Low motion while work eligibility is explicitly annotated','Eligibility is unknown for one or more low-motion intervals'),
            'thresholds':{'tcp_speed_m_s':PAUSE_TCP_M_S,'max_joint_speed_rad_s':PAUSE_JOINT_RAD_S,'duration_strictly_greater_s':PAUSE_MIN_S}}


def responsiveness(events):
    inputs=[];observations={};actions={};dispatches={};admissions={};deliveries=[]
    for event in events:
        kind=event['event_type'];p=event['payload'];sv=service(event)
        if kind=='observation':
            packet=p.get('packet',{});observations[(packet.get('incarnation'),packet.get('sequence'))]=event
        if kind=='candidate_input' and p.get('message',{}).get('type')=='step':
            packet=p['message'].get('packet',{});inputs.append((event,packet))
            capture=packet.get('capture_sim_time_s');age=event_time(event)-capture if finite(capture) else None
            deliveries.append({'event_id':event['event_id'],'sequence':packet.get('sequence'),'acquisition_to_delivery_sim_s':age if age is not None and age>=0 else None,
                'missing_reason':None if age is not None and age>=0 else 'Exact delivered packet lacks a valid acquisition timestamp'})
        if kind=='action_requested':actions.setdefault(p.get('request_id'),event)
        if kind=='action_admission':admissions.setdefault(p.get('request_id'),event)
        if sv.get('type')=='trajectory_dispatched':dispatches.setdefault(sv.get('request_id'),event)
    rows=[]
    for rid,action in actions.items():
        p=action['payload'];seq=p.get('observation_sequence');inc=p.get('incarnation')
        matching=[(event,packet) for event,packet in inputs if event['event_id']<action['event_id'] and seq is not None and packet.get('sequence')==seq and packet.get('incarnation')==inc]
        delivered,packet=matching[-1] if matching else (None,{})
        capture=packet.get('capture_sim_time_s');dispatch=dispatches.get(rid);admission=admissions.get(rid)
        capture= float(capture) if finite(capture) else None
        def age(event):
            value=event_time(event)-capture if event and capture is not None else None
            return value if value is not None and value>=0 else None
        row={'request_id':rid,'action_event_id':action['event_id'],'declared_observation_sequence':seq,
             'matched_candidate_input_event_id':delivered['event_id'] if delivered else None,
             'admission_event_id':admission['event_id'] if admission else None,'dispatch_event_id':dispatch['event_id'] if dispatch else None,
             'acquisition_to_request_sim_s':age(action),'acquisition_to_admission_sim_s':age(admission),'acquisition_to_dispatch_sim_s':age(dispatch),
             'request_to_dispatch_sim_s':event_time(dispatch)-event_time(action) if dispatch and event_time(dispatch)>=event_time(action) else None,
             'provenance':'Action-declared sequence matched to exact delivered packet; does not prove every earlier model decision used this packet' if delivered else 'unknown',
             'actuation_wall_age_s':None,'wall_age_missing_reason':'A trajectory dispatch simulation timestamp is not an independently timestamped wall actuation record'}
        rows.append(row)
    return {'packet_deliveries':deliveries,'action_observation_ages':rows,
            'effective_physical_correction_latency':missing('s','Needs an independently defined corrective physical event and disturbance relationship')}


def event_metrics(events,manifest,result):
    counts=Counter(e['event_type'] for e in events);services=Counter(service(e).get('type') for e in events if service(e))
    actions=[e for e in events if e['event_type']=='action_requested'];admissions=[e for e in events if e['event_type']=='action_admission']
    by_id={e['payload'].get('request_id'):e for e in actions if e['payload'].get('request_id') is not None}
    repeated=Counter(e['payload'].get('request_id') for e in actions if e['payload'].get('request_id') is not None)
    cycles=defaultdict(set)
    for e in admissions:
        p=e['payload'];a=by_id.get(p.get('request_id'),{}).get('payload',{})
        if p.get('status')=='accepted' and not p.get('duplicate_suppressed') and a.get('operation')=='cycle':cycles[(a.get('part_id'),a.get('recipe'))].add(p.get('request_id'))
    nested=[(e,item) for e in events if e['event_type']=='candidate_reply' for item in e['payload'].get('events',[]) if isinstance(item,dict)]
    context={}
    for kind in ('context_read','context_write'):
        values=[item.get('byte_count') for e,item in nested if item.get('type')==kind];known=[v for v in values if type(v) is int and v>=0]
        context[kind]={'observed_events':len(values),'reported_bytes':sum(known) if len(values)==len(known) else None,'known_reported_bytes':sum(known),
                       'scope':'Candidate reported serialization bytes; not complete OS disk I/O'}
    restarts=[e for e in events if e['event_type']=='restart_begin']
    exposures=[e for e in events if e['event_type'] in ('restart_begin','order_amendment')]
    admissibility=[e['payload'].get('admissible',e['payload'].get('exposure',{}).get('admissible')) for e in exposures]
    restart_exposures=[e['payload'].get('exposure',{}) for e in restarts]
    restart_cuts=[e['payload'].get('exposure',{}).get('actual_cut',e['payload'].get('cut')) for e in restarts]
    scenario_exposures=[e for e in events if e['event_type']=='scenario_exposure']
    scenario_records=[{'event_id':e['event_id'],'record_index':i,'sim_time_s':e['sim_time_s'],
                       'wall_elapsed_s':e['wall_elapsed_s'],'exposure':record}
                      for e in scenario_exposures
                      for i,record in enumerate(e['payload'] if isinstance(e['payload'],list) else [e['payload']])]
    return {'event_counts':dict(counts),'physical_service_counts':dict(services),
            'stale_order_rejections':sum(e['payload'].get('status')=='rejected' and e['payload'].get('reason')=='stale order version' for e in admissions),
            'old_incarnation_rejections':sum(e['payload'].get('status')=='rejected' and e['payload'].get('reason')=='old incarnation' for e in admissions),
            'duplicate_suppression_events':sum(e['payload'].get('duplicate_suppressed') is True for e in admissions),
            'repeated_request_id_count':sum(max(0,count-1) for count in repeated.values()),
            'action_requests_missing_id':sum(e['payload'].get('request_id') is None for e in actions),
            'repeated_cycle_admissions_same_part_recipe':sum(max(0,len(ids)-1) for ids in cycles.values()),
            'avoidable_duplicate_work':missing('count','Repeated admitted processing can be required rework; correctness and avoidability need independent adjudication'),
            'observe_requests':sum(e['payload'].get('operation')=='observe' for e in actions),
            'avoidable_observation_requests':missing('count','No frozen visibility/change criterion establishes redundant sensing'),
            'help':{'unique_action_requests':len({e['payload'].get('request_id') for e in actions if e['payload'].get('operation')=='help'}),
                    'scripted_answers':counts['scripted_human_answer'],'recorded_summary':result.get('assistance'),
                    'manual_human_time':missing('s','Scripted responses do not measure human workload')},
            'interventions':{'required_restart':manifest.get('scenario') in ('restart','mixed') if manifest.get('scenario') is not None else None,
                'restart_begin_count':len(restarts),'restart_ready_count':counts['restart_ready'],
                'restart_release_cut_count':sum(cut in ('release','after_release') for cut in restart_cuts),
                'restart_deadline_fallback_count':sum(cut=='deadline_fallback' for cut in restart_cuts),
                'restart_actual_cut_counts':dict(Counter(cut if isinstance(cut,str) else 'unknown' for cut in restart_cuts)),
                'restart_configured_milestone_exercised_count':sum(e.get('configured_milestone_exercised') is True for e in restart_exposures),
                'restart_exposure_records':[{'event_id':e['event_id'],'exposure':e['payload'].get('exposure'),
                                            'legacy_cut':e['payload'].get('cut')} for e in restarts],
                'scenario_exposure_event_count':len(scenario_exposures),'scenario_exposure_record_count':len(scenario_records),
                'scenario_exposure_records':scenario_records,
                'scenario_exposure_scope':'Protected trigger/fallback records; not additional restarts, admissibility decisions or recovered events',
                'order_amendment_count':counts['order_amendment'],
                'admissible_exposure_count':metric(sum(admissibility) if all(type(v) is bool for v in admissibility) else None,'count','Explicit recorded admissibility flags only; no new adjudication','One or more exercised interventions lacks an explicit admissibility flag'),
                'known_admissible_exposure_count':sum(v is True for v in admissibility),
                'unknown_admissibility_count':sum(type(v) is not bool for v in admissibility),
                'successful_recovery_count':missing('count','Requires independent disturbance-to-restored-validity-and-useful-progress annotation')},
            'context_io':context,'recognition_mechanism':missing('label','No internal reasoning or recognition mechanism is inferred from behavior'),
            'candidate_resolution_reports':sum(item.get('type')=='candidate_action_resolution' for e,item in nested),
            'independently_correct_resolution_count':missing('count','Candidate resolution reports are claims, not independent correctness evidence')}


def analyze(events,motion,result,manifest):
    movement,pauses=motion_metrics(motion);models,model_intervals=model_metrics(events)
    finals=[event_time(e) for e in events if e['event_type']=='final_world' and event_time(e) is not None]
    end=finals[-1] if finals else movement['last_sim_time_s'];processes=process_metrics(events,end)
    integrity=[]
    if type(result.get('model_calls')) is int and result['model_calls']!=models['observed_request_count']:integrity.append('Result model_calls differs from observed model_request events')
    if processes['overlapping_cycle_interval_pairs']:integrity.append('Recorded cycle intervals overlap for a single machine; inspect service evidence')
    pause_report=annotate_pauses(pauses,model_intervals,processes,events,end)
    pause_report['analyzed_support_s']=movement['pause_analyzable_time_s']
    pause_report['coverage']='Valid filtered joint/TCP support only; gaps and boundary samples excluded'
    if movement['pause_analyzable_time_s']==0:
        pause_report['observed_low_motion_time_s']=None
        pause_report['eligible_pause_time']=missing('s simulation','No analyzable joint/TCP velocity support')
    return {'schema_version':METHOD,'created_at':datetime.now(timezone.utc).isoformat(),'run_id':result.get('run_id',manifest.get('run_id')),
            'stage':result.get('stage',manifest.get('stage')),'interpretation':'Measured diagnostics only; no validity upgrade, winner, causal attribution or candidate-visible data',
            'recorded_outcome':{key:result.get(key) for key in ('execution_status','outcome','validity','validity_reason','termination_reason','independent_outcome','wall_duration_s','sim_duration_s','completion_time_s','unassisted_completion','completion_after_help')},
            'motion':movement,'transports':transport_metrics(events,motion),'pauses':pause_report,
            'models':models,'process':processes,'responsiveness':responsiveness(events),'events':event_metrics(events,manifest,result),
            'recorded_resources':result.get('resources'),'integrity_findings':integrity,
            'unmeasured':{'energy_joules':None,'electricity_cost':None,'collision_only_impulse':None,'reference_optimal_path_cost':None,
                          'reason':'No direct measurement/reference supplied; raw contact includes intended contacts'},
            'recorded_contact':{'contact_peak_N':result.get('contact_peak_N'),'contact_impulse_Ns':result.get('contact_impulse_Ns'),
                                'scope':'Original result values only; not classified as unintended collision'},
            'method':{'id':METHOD,'position_filter':'centered five-sample valid moving average; no padding',
                'derivatives':'successive finite differences at interval midpoint timestamps','integral':'trapezoidal squared Cartesian jerk on available interior',
                'normalized_jerk':'T^5/L^2 * interior integral; T entire completed trajectory, L raw sampled TCP path',
                'boundary_warning':'Interior support and excluded boundary time are reported; full-duration jerk outside support is unknown',
                'near_zero_path_m':NEAR_ZERO_PATH_M,'gap_rule':'No interpolation or differentiation across non-nominal 100 Hz gaps'},
            'limitations':['Source hashes establish byte identity, not scientific validity or truthful sensors','100 Hz extrema and path lengths may miss native-rate transients',
                'Trajectory completion does not establish physical task success','Inference/process overlap does not establish pause cause',
                'Disturbance admissibility, detection and recovery remain unknown without independent annotations']}


def read_source(path,json_lines=False):
    raw=Path(path).read_bytes();sha=hashlib.sha256(raw).hexdigest()
    reject=lambda token:(_ for _ in ()).throw(DiagnosticError('Nonfinite JSON token: '+token))
    try:
        decoded=raw.decode('utf-8');value=[json.loads(line,parse_constant=reject) for line in decoded.splitlines()] if json_lines else json.loads(decoded,parse_constant=reject)
    except (ValueError,UnicodeError) as exc:raise DiagnosticError('Invalid source '+str(path)+': '+str(exc)) from exc
    if (json_lines and any(not isinstance(row,dict) for row in value)) or (not json_lines and not isinstance(value,dict)):raise DiagnosticError('Source must contain JSON objects: '+str(path))
    return value,{'path':str(Path(path).resolve()),'sha256':sha,'bytes':len(raw)}


def validate_events(events,run_id):
    seen=set();last_id=0
    for event in events:
        eid=event.get('event_id')
        if type(eid) is not int or eid!=last_id+1 or eid in seen:raise DiagnosticError('Event IDs must be contiguous unique integers beginning at one')
        # ScenarioService emits a list when one update exposes one or more order
        # events. This is the only declared non-object payload; nulls, scalars and
        # lists on candidate/other event types remain malformed.
        payload=event.get('payload')
        payload_valid=isinstance(payload,dict) or (event.get('event_type')=='scenario_exposure'
            and event.get('source')=='evaluator' and isinstance(payload,list) and bool(payload)
            and all(isinstance(record,dict) for record in payload))
        if event.get('run_id')!=run_id or not payload_valid or not isinstance(event.get('event_type'),str):raise DiagnosticError('Malformed event identity/payload at event '+str(eid))
        if hashlib.sha256(canonical(event['payload'])).hexdigest()!=event.get('payload_sha256'):raise DiagnosticError('Event payload hash mismatch')
        if not isinstance(event.get('parent_ids'),list) or any(parent not in seen for parent in event['parent_ids']):raise DiagnosticError('Event parent does not name an earlier retained event')
        if not finite(event.get('sim_time_s')) or not finite(event.get('wall_elapsed_s')):raise DiagnosticError('Missing/nonfinite event clock')
        seen.add(eid);last_id=eid


def diagnose_directory(directory):
    root=Path(directory).resolve();sources={};loaded={}
    for name,is_lines in (('manifest.json',False),('result.json',False),('events.jsonl',True),('motion.jsonl',True)):
        loaded[name],sources[name]=read_source(root/name,is_lines)
    run_id=loaded['result.json'].get('run_id')
    if not isinstance(run_id,str) or loaded['manifest.json'].get('run_id')!=run_id:raise DiagnosticError('Manifest/result run IDs differ or are missing')
    validate_events(loaded['events.jsonl'],run_id)
    report=analyze(loaded['events.jsonl'],loaded['motion.jsonl'],loaded['result.json'],loaded['manifest.json'])
    report['sources']=sources
    implementation=Path(__file__).resolve();raw=implementation.read_bytes()
    report['implementation']={'path':str(implementation),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
    return report


def write_report(report,path):
    path=Path(path).resolve()
    if any(part.casefold()=='candidate_state' for part in path.parts):raise DiagnosticError('Diagnostic output may not be written to candidate state')
    for ref in [*report['sources'].values(),report['implementation']]:
        source=Path(ref['path'])
        if path==source:raise DiagnosticError('Diagnostic output cannot replace raw evidence')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=ref['sha256']:raise DiagnosticError('Input changed during analysis: '+str(source))
    path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_name(path.name+f'.{os.getpid()}.tmp')
    with temporary.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(report,stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    try:os.link(temporary,path)
    finally:temporary.unlink()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--episode-dir',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    try:report=diagnose_directory(args.episode_dir);write_report(report,args.output)
    except (DiagnosticError,OSError,ValueError,KeyError,TypeError) as exc:parser.exit(2,'Refused: '+str(exc)+'\n')
    print(json.dumps({'output':str(Path(args.output).resolve()),'run_id':report['run_id'],'method':METHOD,
                      'interpretation':'Operator diagnostics; original validity unchanged'},indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
