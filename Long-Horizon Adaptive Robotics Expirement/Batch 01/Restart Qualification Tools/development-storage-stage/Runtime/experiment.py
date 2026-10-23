"""Queued experiment supervisor: physics, isolated candidate, model and evidence.

Development entrypoint first. Evaluation is refused without a frozen manifest
and passing shared readiness evidence; a completed program is not task success.
"""
from __future__ import annotations
import argparse
import copy
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import threading
import time
import uuid
import numpy as np

from cell import Cell,DT,ZONES,zone_half
from initial_conditions import initial_world_report,RestartOpportunity
from png import write_png
from resources import ResourceSampler
from restart_state import capture_restart_state,classify_restart
from restart_calibration_loader import (VerifiedRestartQualification,CalibrationInputError,
    select_restart_calibration,absence_observation,first_control_endpoint)
from scenarios import ScenarioService,derive_event_seed,public_rules
from sensors import RawSensorGateway

HERE=Path(__file__).resolve().parent
EVIDENCE=HERE.parent/'Evidence'/'raw'
from development_storage import location as development_location
EVALUATION_AUTHORIZATION_VERSION='robot-evaluation-authorization-1.0'
GIB=1024**3
RESOURCE_POLICY={'version':'robot-runtime-resource-policy-003','resource_caps_enforced':False,
    'sampled_watchdog':{'harness_rss_bytes':4*GIB,'model_private_commit_bytes':12*GIB,'whole_device_gpu_memory_bytes':14*GIB,
        'target_supervisor_check_interval_s':.25,'observation_period_s':5.,'gpu_query_timeout_s':2.,
        'initial_observation_grace_s':7.,'maximum_sample_age_s':7.,
        'observation_grace_origin':'sampler monotonic start; not episode or candidate-incarnation start',
        'required_observations':'harness RSS, active model private commit with matching PID, and memory on every reported GPU',
        'scope':'latest completed asynchronous sample; 5 s period plus up to 2 s GPU query; .25 s is a target poll cadence, not a measurement or detection bound; transient peaks can be missed',
        'whole_gpu_attribution':'host/device total; never automatically attributed to the candidate'},
    'hard_cap_evidence':'Model manifest resource_enforcement and candidate_ready restrictions are separate authoritative declarations; sampled checks are not OS quotas',
    'candidate_context':{'checkpoint_bytes':8*1024**2,'context_allowance_bytes':256*1024**2,
        'bounded_fixed_code_estimate_bytes':48*1024**2,'scope':'fixed candidate checkpoint/temp behavior and at most one restart; not a measured filesystem peak'},
    'candidate_cpu':'Single process/thread admitted by sandbox no-clone policy; aggregate observed CPU retains missing final interval',
    'sampler_compatibility':'resources.jsonl budget_observations are descriptive; this versioned supervisor watchdog defines current stop thresholds'}

def utc():return datetime.now(timezone.utc).isoformat()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resource_breaches(sample,*,now_monotonic_s,sampler_started_monotonic_s,model_required=False,model_pid=None):
    """Inspect an already-finished sample only; never query OS/GPU or wait here."""
    policy=RESOURCE_POLICY['sampled_watchdog'];out=[]
    def number(value):return type(value) in (int,float) and math.isfinite(value) and value>=0
    def unavailable(role,metric,reason,**details):
        out.append({'role':role,'metric':metric,'reason':reason,'kind':'observation_unavailable',
                    'classification':'infrastructure_failure',**details})
    if not number(now_monotonic_s) or not number(sampler_started_monotonic_s) or now_monotonic_s<sampler_started_monotonic_s:
        unavailable('sampler','monotonic_clock','invalid supervisor/sampler monotonic clock')
        return out
    since_start=now_monotonic_s-sampler_started_monotonic_s
    grace=since_start<policy['initial_observation_grace_s']
    if not isinstance(sample,dict):
        if not grace:unavailable('sampler','sample','no completed resource sample after initial grace',sampler_elapsed_s=since_start)
        return out
    captured=sample.get('capture_monotonic_s')
    if not number(captured):
        if not grace:unavailable('sampler','capture_monotonic_s','missing or invalid capture clock')
    elif captured>now_monotonic_s or captured<sampler_started_monotonic_s:
        unavailable('sampler','capture_monotonic_s','capture clock outside sampler lifetime',
                    observed=captured,now_monotonic_s=now_monotonic_s,sampler_started_monotonic_s=sampler_started_monotonic_s)
    elif now_monotonic_s-captured>policy['maximum_sample_age_s']:
        unavailable('sampler','capture_monotonic_s','latest completed resource sample is stale',
                    age_s=now_monotonic_s-captured,maximum_age_s=policy['maximum_sample_age_s'])
    for role,key,limit,required in (
        ('harness','rss_bytes',policy['harness_rss_bytes'],True),
        ('model','private_commit_bytes',policy['model_private_commit_bytes'],model_required)):
        record=sample.get(role);record=record if isinstance(record,dict) else {}
        observed=record.get(key)
        if number(observed) and observed>limit:
            out.append({'role':role,'metric':key,'observed':observed,'limit':limit,'classification':'infrastructure_failure'})
        if required and not grace:
            if not number(observed):
                unavailable(role,key,'mandatory resource value unavailable',missing_reason=record.get('missing_reason'))
            if role=='model' and (type(model_pid) is not int or model_pid<=0 or type(record.get('pid')) is not int or record.get('pid')!=model_pid):
                unavailable('model','pid','active model observation has no matching owned process',
                            expected_pid=model_pid,observed_pid=record.get('pid'))
    gpu=sample.get('gpu');gpu=gpu if isinstance(gpu,dict) else {}
    devices=gpu.get('devices')
    if not isinstance(devices,list) or not devices:
        if not grace:unavailable('whole_gpu','memory_used_bytes','no whole-device memory observations',missing_reason=gpu.get('missing_reason'))
    else:
        for device in devices:
            device=device if isinstance(device,dict) else {}
            observed=device.get('memory_used_bytes')
            if number(observed) and observed>policy['whole_device_gpu_memory_bytes']:
                out.append({'role':'whole_gpu','device_index':device.get('index'),'metric':'memory_used_bytes',
                            'observed':observed,'limit':policy['whole_device_gpu_memory_bytes'],'classification':'host_resource_invalid',
                            'attribution':'whole device including other applications; candidate attribution unknown'})
            elif not number(observed) and not grace:
                unavailable('whole_gpu','memory_used_bytes','mandatory whole-device memory value unavailable',
                            device_index=device.get('index'),missing_reasons=device.get('missing_reasons'))
    return out


def result_validity(*,failure_class,cleanup_errors,timing_failed,evaluation_authorized):
    """Explicit analysis contract; candidate failures alone never exclude a block."""
    invalid=failure_class in ('infrastructure_failure','host_resource_invalid','oracle_exposure','integrity_failure',
        'evaluator_corruption','source_hash_mismatch','readiness_failure','evidence_integrity_failure') or bool(cleanup_errors) or bool(timing_failed)
    return {'validity':'invalid' if invalid else ('valid' if evaluation_authorized else 'unknown'),
            'invalidity_class':'infrastructure' if invalid else None,'infrastructure_invalid':invalid}


class PublicTelemetryHistory:
    """One second of robot-only samples; batch delivery is not a 100 Hz policy."""
    def __init__(self):
        self.samples=deque(maxlen=100);self.sequence=0;self.evicted=0
    def _expire(self,now):
        while self.samples and now-self.samples[0]['sim_time_s']>1.+1e-9:
            self.samples.popleft();self.evicted+=1
    def append(self,sim,wall,q,dq,effort,width):
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in (sim,wall,width)):
            raise ValueError('Invalid public telemetry clock or width')
        arrays=[list(values) for values in (q,dq,effort)]
        if any(len(values)!=7 or any(not math.isfinite(float(v)) for v in values) for values in arrays):
            raise ValueError('Invalid seven-joint public telemetry')
        previous=self.samples[-1] if self.samples else None
        if previous and (sim<=previous['sim_time_s'] or wall<previous['wall_elapsed_s']):
            raise ValueError('Public telemetry clock regressed')
        gap=sim-previous['sim_time_s'] if previous else None
        self._expire(sim)
        if len(self.samples)==self.samples.maxlen:self.evicted+=1
        self.sequence+=1
        self.samples.append({'sequence':self.sequence,'sim_time_s':sim,'wall_elapsed_s':wall,
            'joint_position_rad':[float(v) for v in arrays[0]],'joint_velocity_rad_s':[float(v) for v in arrays[1]],
            'actuator_effort_Nm':[float(v) for v in arrays[2]],'measured_gripper_width_m':width,
            'preceding_sim_gap_s':gap,'missed_nominal_intervals':max(0,round(gap/.01)-1) if gap is not None else None})
    def packet(self,sim,wall,after_sequence=0):
        self._expire(sim)
        samples=[dict(row) for row in self.samples]
        first=samples[0]['sequence'] if samples else self.sequence+1
        return {'schema_version':'robot-public-telemetry-history-1.0','samples':samples,
            'nominal_capture_hz':100,'maximum_samples':100,'maximum_history_sim_s':1.,
            'latest_sequence':self.sequence,'evicted_samples':self.evicted,
            'last_attempted_step_dispatch_sequence':after_sequence,
            'samples_expired_since_last_attempted_step_dispatch':max(0,first-after_sequence-1),
            'latest_sample_age_sim_s':sim-samples[-1]['sim_time_s'] if samples else None,
            'latest_sample_age_wall_s':wall-samples[-1]['wall_elapsed_s'] if samples else None,
            'delivery':'bounded batches at existing approximately 10 Hz step opportunities; model waits and active macro actions can delay delivery',
            'ingestion':'prior attempted step dispatch is not confirmed ingestion',
            'scope':'robot joints, actuator effort and jaw width only; expired history is unavailable and no samples are interpolated',
            'live_100_hz_policy':False}


def authorized_evidence_path(stage,context,*,kind,n,cap,condition,scenario,run_id,seeds,development_raw_root=None):
    if stage not in ('development','evaluation'):raise ValueError('Unknown experiment stage')
    if stage!='evaluation':
        if context is not None:raise ValueError('Evaluation context cannot authorize a development run')
        assigned=development_location(run_id,development_raw_root,default_root=EVIDENCE,require_fresh=True)
        return Path(assigned['evidence_dir']),None
    if development_raw_root is not None:raise ValueError('Development raw root cannot override evaluation authority')
    from release_runner import VerifiedEvaluationContext
    if not isinstance(context,VerifiedEvaluationContext):raise ValueError('Evaluation requires a verified release context')
    path=context.assert_episode(kind=kind,n=n,cap=cap,condition=condition,scenario=scenario,
                                stage=stage,run_id=run_id,**seeds)
    if Path(path).resolve()!=context.evidence_dir.resolve():raise ValueError('Authorized evidence path mismatch')
    provenance={'authorization_version':EVALUATION_AUTHORIZATION_VERSION,'release_sha256':context.release_sha256,
                'manifest_sha256':context.manifest_sha256,'queue_job_id':context.queue_job_id,
                'verified_at':context.verified_at}
    return context.evidence_dir,provenance


def assert_candidate_state_path(episode_dir,evidence_dir):
    expected=Path(evidence_dir).resolve()/'candidate_state'
    actual=Path(episode_dir).resolve()
    if actual!=expected or Path(episode_dir).is_symlink():raise ValueError('Candidate state reset escaped exact assigned episode directory')
    return actual


def sensor_delivery_packet(packet,capture,*,delivery_sim_s,delivery_wall_s):
    capture_sim=None if capture is None else capture.capture_sim_time_s
    return {**packet,'capture_sim_time_s':capture_sim,
            'capture_wall_elapsed_s':None if capture is None else capture.capture_wall_elapsed_s,
            'capture_sequence':None if capture is None else capture.sequence,
            'camera_calibration':None if capture is None else capture.calibration,
            'capture_joint_telemetry':None if capture is None else capture.capture_telemetry,
            'delivery_sim_time_s':delivery_sim_s,'delivery_wall_elapsed_s':delivery_wall_s,
            'camera_frame_age_sim_s':None if capture_sim is None else max(0.,delivery_sim_s-capture_sim),
            'camera_metadata_status':'unavailable' if capture is None else 'exact retained capture'}


def terminal_receipt(lifecycle,feedback):
    record=lifecycle.get(feedback.get('request_id'))
    if record is not None:
        record['feedback']=feedback
        if feedback.get('status') in ('completed','failed','cancelled','rejected'):
            record['time']=feedback.get('sim_time',record['time'])


class CandidateUsage:
    """Per-incarnation cumulative observations; final termination tail unknown."""
    def __init__(self):self.incarnations={}
    def observe(self,incarnation,message,*,event_id=None,wall_elapsed_s=None):
        entry=self.incarnations.setdefault(incarnation,{'incarnation':incarnation,'samples':0,'last':None,
            'last_event_id':None,'last_wall_elapsed_s':None,'missing_final_interval':True})
        usage=message.get('runtime_usage') if isinstance(message,dict) else None
        if not isinstance(usage,dict):return
        keys=('user_cpu_s','system_cpu_s','maximum_rss_bytes','input_blocks','output_blocks')
        if any(type(usage.get(k)) not in (int,float) or not math.isfinite(usage[k]) or usage[k]<0 for k in keys):
            entry['invalid_sample']=True;return
        previous=entry['last']
        if previous and any(usage[k]<previous[k] for k in keys):
            entry['nonmonotonic_sample']=True;return
        entry.update(samples=entry['samples']+1,last={k:usage[k] for k in keys},
                     last_event_id=event_id,last_wall_elapsed_s=wall_elapsed_s)
    def summary(self):
        values=list(self.incarnations.values());known=[v['last'] for v in values if v['last'] is not None]
        return {'source':'fixed wrapper getrusage(RUSAGE_SELF), cumulative per Linux candidate incarnation',
                'incarnations':values,'observed_incarnations':len(known),'expected_incarnations':len(values),
                'known_user_cpu_s':sum(v['user_cpu_s'] for v in known),
                'known_system_cpu_s':sum(v['system_cpu_s'] for v in known),
                'observed_maximum_rss_bytes':max((v['maximum_rss_bytes'] for v in known),default=None),
                'known_input_blocks':sum(v['input_blocks'] for v in known),'known_output_blocks':sum(v['output_blocks'] for v in known),
                'complete':False,'missing_final_interval':True,
                'interpretation':'CPU/IO totals are observed lower bounds. RSS is the largest reported incarnation high-water mark. Work after the last reply through process termination is unmeasured; missing samples are not zero.'}


def prepare_raw_reply(gateway,request,wall_elapsed_s,current_telemetry):
    """Bounded encoding worker only; returns a ready immutable-by-ownership IPC message."""
    response=gateway.materialize_cached_request(request,wall_elapsed_s=wall_elapsed_s,current_telemetry=current_telemetry)
    message={'type':'sensor_response','response':response}
    if len(canonical(message))+1>=1024*1024:raise ValueError('Wrapped raw response exceeds candidate input line cap')
    return {'message':message,'evidence':gateway.last_evidence}


def pin_sensor_gateway(gateway):
    """Pin current immutable capture objects before the encoding future starts.

    Admission bookkeeping remains shared and is consumed once. Only one raw
    request/encoding is outstanding in this supervisor. Periodic overhead cache
    updates cannot change the frame/event association of that queued encoding.
    """
    pinned=copy.copy(gateway)
    pinned._cached=dict(gateway._cached)
    pinned.last_evidence=None
    return pinned


class TimingMonitor:
    """Fresh wall/simulation samples; one-second wall-window rates.

    Boundary simulation time is interpolated between adjacent observed samples.
    The maximum observed gap is retained so sparse samples cannot claim precise
    sub-window timing. Initialization and post-episode cleanup are excluded.
    """
    def __init__(self):
        self.previous=(0.,0.);self.boundary=1.;self.boundary_sim=0.
        self.windows=[];self.maximum_lag=0.;self.maximum_sample_gap=0.
    def observe(self,wall,sim):
        old_wall,old_sim=self.previous
        if wall<old_wall or sim<old_sim:raise ValueError('Clock sample moved backwards')
        self.maximum_lag=max(self.maximum_lag,wall-sim)
        self.maximum_sample_gap=max(self.maximum_sample_gap,wall-old_wall)
        while wall>=self.boundary:
            fraction=(self.boundary-old_wall)/(wall-old_wall) if wall>old_wall else 1.
            boundary_sim=old_sim+(sim-old_sim)*fraction
            rtf=boundary_sim-self.boundary_sim
            self.windows.append({'wall_start_s':self.boundary-1.,'wall_end_s':self.boundary,
                                 'sim_end_s':boundary_sim,'real_time_factor':rtf,
                                 'lag_s':self.boundary-boundary_sim,'within_tolerance':.95<=rtf<=1.05})
            self.boundary_sim=boundary_sim;self.boundary+=1.
        self.previous=(wall,sim)
    def report(self):
        bad=sum(not w['within_tolerance'] for w in self.windows)
        fraction=bad/len(self.windows) if self.windows else None
        return {'maximum_lag_s':self.maximum_lag,'maximum_timing_sample_gap_s':self.maximum_sample_gap,
                'timing':self.windows,'complete_wall_windows':len(self.windows),
                'outside_rtf_tolerance_windows':bad,'outside_rtf_tolerance_fraction':fraction,
                'actual_host_timing_pass':bool(self.windows) and self.maximum_lag<.1 and fraction<.01,
                'timing_boundary_method':'linear interpolation of adjacent fresh wall/sim samples',
                'trailing_partial_window_s':self.previous[0]-len(self.windows)}


class EpisodeFailure(RuntimeError):
    def __init__(self,classification,message):
        super().__init__(message);self.classification=classification


def worker_diagnostics(worker):
    stderr=getattr(worker,'stderr','')
    return {'stderr_tail':stderr if isinstance(stderr,str) else '',
            'failure':getattr(worker,'failure',None) if isinstance(getattr(worker,'failure',None),(str,type(None))) else None,
            'scope':'bounded protected stderr tail; no claim that every byte was retained'}


class ScriptedAssistance:
    """Public, durable advice; no access to evaluator state or physical rescue."""
    DELAY_S=15.
    POLICY_ID='public-reobserve-advice-v1'
    ANSWER=('Reobserve using fresh public sensor input. Validate visible part location, public inspection, '
            'station status and the current order before proposing another action. Retain unresolved '
            'action outcomes and missing process provenance as unknown; do not replay an ambiguous action '
            'or infer successful processing from this answer. No physical rescue or hidden-state information is provided.')
    def __init__(self):self.requests={};self.answers=[]
    def request(self,action,sim,wall,parent):
        rid=action['request_id']
        if rid in self.requests:return {**self.requests[rid]['feedback'],'duplicate_suppressed':True}
        request={'request_id':rid,'reason':action.get('reason'),'evidence':action.get('evidence'),
                 'requested_information_or_action':action.get('requested_information_or_action'),
                 'request_sim_time_s':sim,'request_wall_elapsed_s':wall,'parent_event_id':parent,'answered':False}
        valid=(isinstance(request['reason'],str) and bool(request['reason'].strip())
               and isinstance(request['evidence'],dict)
               and isinstance(request['requested_information_or_action'],str)
               and bool(request['requested_information_or_action'].strip()) and len(canonical(request))<=8192)
        request['accepted']=valid
        request['feedback']={'request_id':rid,'status':'accepted' if valid else 'rejected',
                             'reason':'simulated assistance scheduled after 15 seconds' if valid else 'Help requires bounded reason, evidence and requested_information_or_action',
                             'simulated_assistance':True}
        self.requests[rid]=request
        return dict(request['feedback'])
    def advance(self,sim,wall):
        created=[]
        for request in self.requests.values():
            if not request['accepted'] or request['answered']:continue
            if sim-request['request_sim_time_s']<self.DELAY_S or wall-request['request_wall_elapsed_s']<self.DELAY_S:continue
            request['answered']=True
            answer={'answer_id':f'help-answer-{len(self.answers)+1:05d}','request_id':request['request_id'],
                    'policy_id':self.POLICY_ID,'simulated_assistance':True,'content':self.ANSWER,
                    'available_sim_time_s':sim,'available_wall_elapsed_s':wall,
                    'wait_sim_s':sim-request['request_sim_time_s'],'wait_wall_s':wall-request['request_wall_elapsed_s'],
                    'parent_event_id':request['parent_event_id'],'physical_rescue':False}
            self.answers.append(answer);created.append(answer)
        return created
    def public_answers(self):return json.loads(canonical(self.answers))
    def summary(self,wall):
        return {'policy_id':self.POLICY_ID,'simulated_assistance':True,'nominal_delay_s':self.DELAY_S,
                'requests':len(self.requests),'accepted_requests':sum(r['accepted'] for r in self.requests.values()),
                'responses':len(self.answers),'pending_responses':sum(r['accepted'] and not r['answered'] for r in self.requests.values()),
                'any_help_requested':bool(self.requests),'physical_rescue_actions':0,'actual_human_time_s':None,
                'actual_human_time_missing_reason':'Scripted assistance; no manual diagnostic human time measured',
                'summed_scripted_wait_wall_s':sum(a['wait_wall_s'] for a in self.answers)+sum(max(0.,wall-r['request_wall_elapsed_s']) for r in self.requests.values() if r['accepted'] and not r['answered']),
                'wait_interpretation':'Sum of request waits, including unfinished waits; concurrent waits may overlap',
                'answers':self.public_answers()}


def close_pending_restart(pending,pending_type,current_worker,timeout=45.):
    """A late restart owns a new process even if the episode already ended."""
    errors=[]
    if pending is not None and pending_type=='restart':
        try:
            fresh=pending.result(timeout=timeout)
            if fresh is not current_worker:fresh.close()
        except Exception as exc:
            if not (isinstance(exc,EpisodeFailure) and exc.classification.startswith('candidate_')):
                errors.append('pending restart cleanup: '+str(exc))
            if not pending.done():
                # shutdown(wait=True) below may outlast this bounded wait. The
                # late-created worker must still be closed when it appears.
                def close_late(future):
                    if future.cancelled():return
                    try:
                        fresh=future.result()
                        if fresh is not current_worker:fresh.close()
                    except Exception as late_exc:errors.append('late restart cleanup: '+str(late_exc))
                pending.add_done_callback(close_late)
    if current_worker:
        try:current_worker.close()
        except Exception as exc:errors.append('candidate cleanup: '+str(exc))
    return errors

class Evidence:
    def __init__(self,directory,run_id):
        self.path=Path(directory);self.path.mkdir(parents=True,exist_ok=False)
        (self.path/'frames').mkdir();(self.path/'contexts').mkdir()
        self.events=(self.path/'events.jsonl').open('w',encoding='utf-8',newline='\n')
        self.motion=(self.path/'motion.jsonl').open('w',encoding='utf-8',newline='\n')
        self.run_id=run_id;self.sequence=0;self.start=time.perf_counter()
        self.lock=threading.Lock()
    def emit(self,kind,payload,sim_time,source='supervisor',parents=None):
        with self.lock:
            self.sequence+=1
            event={'schema_version':'robot-evidence-1.0','run_id':self.run_id,'event_id':self.sequence,'event_type':kind,'source':source,'sim_time_s':sim_time,'sim_tick':round(sim_time/DT),'wall_elapsed_s':time.perf_counter()-self.start,'parent_ids':parents or [],'payload_sha256':hashlib.sha256(canonical(payload)).hexdigest(),'payload':payload}
            self.events.write(json.dumps(event,allow_nan=False,separators=(',',':'))+'\n')
            if kind not in ('observation','world_snapshot'):self.events.flush()
            return self.sequence
    def close(self):self.events.close();self.motion.close()

def initial_order(n,amend=False):
    a=(n+1)//2;b=n//2
    req=[{'family':'A','recipe':'A','count':a,'tray':'tray1'}]
    if b:req.append({'family':'B','recipe':'B','count':b,'tray':'tray2'})
    return {'version':1,'closed':not amend,'requirements':req,'text':f'Process and inspect {a} A and {b} B parts. Deliver to the named trays.'}

def candidate_call(worker,message,evidence=None,simulation_time=None,parents=None):
    parent=None
    if evidence is not None:
        parent=evidence.emit('candidate_input',{'message':message},simulation_time(),'candidate_gateway',parents)
    worker.send(message)
    reply=worker.receive(timeout=20.)
    if parent is not None:reply={**reply,'supervisor_input_event_id':parent}
    return reply

def restart_worker(old_worker,old_pending,kind,episode_dir,persistent,evidence_dir=None):
    """Keep physics live during all OS process teardown/startup latency."""
    from sandbox import CandidateSandbox
    old_worker.close()
    if old_pending:
        try:old_pending.result(timeout=2.)
        except Exception:pass
    if not persistent:
        if evidence_dir is None:raise ValueError('Exact evidence directory required for state reset')
        target=assert_candidate_state_path(episode_dir,evidence_dir)
        shutil.rmtree(target);target.mkdir()
    worker=CandidateSandbox(kind,episode_dir,persistent=persistent)
    try:worker.start()
    except Exception as exc:
        diagnostics=worker_diagnostics(worker)
        classification='candidate_contract_failure' if 'CANDIDATE_CONTRACT_VIOLATION' in diagnostics['stderr_tail'] else 'infrastructure_failure'
        raise EpisodeFailure(classification,str(exc)+'; protected stderr tail: '+diagnostics['stderr_tail']) from exc
    return worker

def resolve_seeds(seed=None,world_seed=None,policy_noise_seed=0):
    """Legacy seed names world randomness only, never policy/sensor randomness."""
    if seed is not None and world_seed is not None and seed!=world_seed:
        raise ValueError('--seed and --world-seed disagree; --seed is a legacy world-seed alias')
    world=world_seed if world_seed is not None else (seed if seed is not None else 0)
    for name,value in (('world_seed',world),('policy_noise_seed',policy_noise_seed)):
        if isinstance(value,bool) or not isinstance(value,int) or not 0<=value<=2**32-1:
            raise ValueError(name+' must be an integer from 0 through 4294967295')
    return world,policy_noise_seed


def resolve_seed_roles(seed=None,world_seed=None,policy_noise_seed=0,layout_seed=None,noise_seed=None,policy_seed=None):
    if seed is not None and world_seed is not None and seed!=world_seed:raise ValueError('Legacy and world seed disagree')
    world=world_seed if world_seed is not None else (seed if seed is not None else 0)
    values={'world_seed':world,'layout_seed':world if layout_seed is None else layout_seed,
            'noise_seed':policy_noise_seed if noise_seed is None else noise_seed,
            'policy_seed':policy_noise_seed if policy_seed is None else policy_seed}
    for name,value in values.items():
        limit=2**31 if name=='policy_seed' else 2**63
        if type(value) is not int or not 0<=value<limit:raise ValueError(name+' is outside its declared integer range')
    return values


def run_episode(kind='baseline',n=3,seed=None,cap=300.,condition='persistent',scenario='nominal',stage='development',model=None,run_id=None,world_seed=None,policy_noise_seed=0,layout_seed=None,noise_seed=None,policy_seed=None,evaluation_context=None,development_restart_qualification=None,development_raw_root=None):
    from sandbox import CandidateSandbox
    seeds=resolve_seed_roles(seed,world_seed,policy_noise_seed,layout_seed,noise_seed,policy_seed)
    world_seed=seeds['world_seed'];layout_seed=seeds['layout_seed'];noise_seed=seeds['noise_seed'];policy_seed=seeds['policy_seed']
    run_id=run_id or f'dev-{kind}-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")}-{uuid.uuid4().hex[:6]}'
    evidence_path,evaluation_authorization=authorized_evidence_path(stage,evaluation_context,kind=kind,n=n,cap=cap,
        condition=condition,scenario=scenario,run_id=run_id,seeds=seeds,development_raw_root=development_raw_root)
    # Authorization above binds the exact protected run before its public alias is derived.
    public_episode_id=evaluation_context.public_episode_id if stage=='evaluation' else run_id
    if stage=='evaluation':
        if development_restart_qualification is not None:raise CalibrationInputError('Development qualification cannot override evaluation authority')
        restart_qualification=evaluation_context.restart_qualification
    elif development_restart_qualification is None:restart_qualification=None
    elif isinstance(development_restart_qualification,VerifiedRestartQualification):
        restart_qualification=development_restart_qualification.as_dict()
    else:raise CalibrationInputError('Development qualification must come from the protected loader')
    development_storage=development_location(run_id,evidence_path.parent) if stage=='development' else None
    evidence=Evidence(evidence_path,run_id)
    episode_dir=evidence.path/'candidate_state'
    condition_persistent=condition=='persistent'
    cell=None;worker=None;executor=ThreadPoolExecutor(max_workers=3)
    sensor_encoder=ThreadPoolExecutor(max_workers=1,thread_name_prefix='raw-sensor-encoding')
    raw_gateway=None;raw_task=None;raw_encode_pending=None;raw_capture_sequence=0;last_camera_result=None
    usage=CandidateUsage();physical_receipts={};cycle_parents={};restart_parent=None
    telemetry_history=PublicTelemetryHistory();telemetry_dispatched={}
    retired_workers=[]
    pending=None;pending_type=None;model_pending=None;model_parent=None;model_incarnation=None
    last_observation_event=None;model_delivery_parent=None
    lifecycle={};feedback_cursor=0;cell_event_cursor=0
    last_frame=-1.;last_snapshot=-1.;last_motion=-1.;last_capture_wall=None;last_outcome=-1.
    next_decision=0.;done_assertions=0;false_done=0;model_calls=0;tokens=0
    model_responses=0;model_failures=0;unknown_token_calls=0;late_model_responses=0
    incarnation=1;obs_sequence=0;capture_sequence=0;success=False
    last_capture_sim=None;missed_capture_slots=0
    restart_exercised=False;amend_exercised=False;restart_pending=False
    scenario_service=ScenarioService(n,scenario,event_seed=derive_event_seed(world_seed))
    restart_tracker=RestartOpportunity(world_seed,enabled=scenario in ('restart','mixed'))
    initial_validity=None;restart_exposure=None;restart_source_hashes=None
    # The protected frozen map is assessed only at the actual existing cut.
    restart_calibration=None;restart_selection=None;restart_revocation=None
    restart_absence_endpoint_observed=False;restart_first_control_observed=False
    qualification_context=restart_qualification['qualification_context'] if restart_qualification else None
    restart_absence_settings=restart_qualification['absence'] if restart_qualification else None
    order=scenario_service.initial_order()
    elapsed=0.;termination='time_cap';error=None;failure_class=None;phase='initialization'
    start=None;base_sim=0.;monitor=TimingMonitor();camera_gaps=[];cleanup_errors=[]
    final=None;started_at=utc();episode_ended_at=None;episode_end_wall=None;sim_at_end=None
    resource_sampler=None;resource_summary=None;resource_started_at=None;resource_started_counter=None
    resource_watchdog_events=[];next_resource_check_wall=0.
    completion_landmark=None
    assistance=ScriptedAssistance();help_request_ids=set()

    def model_pid():
        process=getattr(model,'process',None) if model is not None else None
        return getattr(process,'pid',None) if process is not None else None

    def sim_now():return float(cell.data.time) if cell is not None else 0.
    def record_restart_absence(endpoint,landmark,parents=None,control=None):
        report=absence_observation(restart_revocation,landmark,endpoint,restart_absence_settings)
        report['restart_event_id']=restart_parent
        report['qualification_identity']=restart_qualification['identity'] if restart_qualification else None
        if control is not None:report['control_admission']=control
        event=evidence.emit('restart_absence',report,landmark['sim_s'],'evaluator',parents or [restart_parent])
        if restart_exposure is not None:restart_exposure.setdefault('absence_observations',[]).append({**report,'event_id':event})
        return report

    def public_packet():
        wall=time.perf_counter()-start if start is not None else None
        arm=cell.public_arm_interfaces()
        arm={**arm,'telemetry_history':telemetry_history.packet(sim_now(),wall,telemetry_dispatched.get(incarnation,0))}
        packet={**cell.public_packet(order,public_episode_id,incarnation,obs_sequence),
                'human_answers':assistance.public_answers(),'restart_generation':incarnation-1,
                'arm':arm}
        return sensor_delivery_packet(packet,last_camera_result,delivery_sim_s=sim_now(),
                                      delivery_wall_s=wall)

    def checked_outcome():
        acceptance_open=bool(order.get('closed')) and (scenario not in ('restart','mixed') or (restart_exercised and not restart_pending))
        return cell.outcome(order,acceptance_open=acceptance_open)

    def collect_completion():
        nonlocal completion_landmark,success,termination
        if completion_landmark is not None:return True
        first=getattr(getattr(cell,'evaluator',None),'first_success',None)
        if not isinstance(first,dict):return False
        wall=first.get('wall_monotonic_s');sim=first.get('sim_time_s')
        if (type(wall) not in (int,float) or not math.isfinite(wall) or wall<start
                or type(sim) not in (int,float) or not math.isfinite(sim) or sim<base_sim
                or abs(sim-sim_now())>1e-9):
            raise EpisodeFailure('infrastructure_failure','Independent completion landmark lacks its exact live tick/clock')
        completion_landmark={**first,'wall_elapsed_s':wall-start,'sim_elapsed_s':sim-base_sim,
                             'within_wall_cap':wall-start<=cap,'native_timestep_s':DT}
        event_id=evidence.emit('independent_completion',completion_landmark,sim,'evaluator')
        completion_landmark['evidence_event_id']=event_id
        success=completion_landmark['within_wall_cap']
        if success:termination='independent_completion'
        return True

    def dispatch_candidate(message,parents=None,*,already_frozen=False):
        frozen_message=message if already_frozen else json.loads(canonical(message))
        if frozen_message.get('type')=='step':
            sequence=frozen_message.get('packet',{}).get('arm',{}).get('telemetry_history',{}).get('latest_sequence')
            if type(sequence) is int:telemetry_dispatched[incarnation]=sequence
        return executor.submit(candidate_call,worker,frozen_message,evidence,sim_now,parents)

    def begin_raw_encoding():
        nonlocal raw_encode_pending
        telemetry={'sim_time_s':sim_now(),'joint_position_rad':cell.data.qpos[:7].tolist(),
                   'joint_velocity_rad_s':cell.data.qvel[:7].tolist(),
                   'actuator_effort_Nm':cell.data.actuator_force[:7].tolist(),
                   'measured_gripper_width_m':float(sum(cell.data.qpos[7:9]))}
        raw_task['state']='encoding'
        raw_encode_pending=sensor_encoder.submit(prepare_raw_reply,pin_sensor_gateway(raw_gateway),raw_task['request'],
                                                 time.perf_counter()-start,telemetry)

    def collect_model(future,*,late=False):
        nonlocal tokens,model_responses,model_failures,unknown_token_calls,late_model_responses,model_delivery_parent
        stale=model_incarnation!=incarnation
        metadata={'original_incarnation':model_incarnation,'current_incarnation':incarnation,
                  'stale':stale,'after_episode_end':late}
        if late:
            metadata['post_episode_wall_s']=time.perf_counter()-episode_end_wall
            metadata['wall_beyond_cap_s']=max(0.,time.perf_counter()-start-cap) if start is not None else None
        try:
            timeout=(getattr(getattr(model,'config',None),'request_timeout_s',30.)+25.) if late else None
            reply=future.result(timeout=timeout)
            count=reply.get('total_tokens',reply.get('usage',{}).get('total_tokens'))
            if count is None:unknown_token_calls+=1
            else:tokens+=int(count)
            model_responses+=1
            if late:late_model_responses+=1
            model_delivery_parent=evidence.emit('late_model_response' if late else 'model_response',{'result':reply,**metadata},sim_now(),'local_model',[model_parent] if model_parent else [])
            if stale:evidence.emit('stale_model_output_discarded',metadata,sim_now())
            return reply.get('text',reply.get('raw_text','')) if not stale and not late else None
        except Exception as exc:
            model_failures+=1;unknown_token_calls+=1
            if late and not future.done() and model is not None:
                try:model.stop()
                except Exception as stop_exc:cleanup_errors.append('model timeout cleanup: '+str(stop_exc))
            evidence.emit('stale_model_error_discarded' if stale else 'model_error',{'error':str(exc),**metadata},sim_now(),'local_model',[model_parent] if model_parent else [])
            # Explicit invalid output consumes the candidate's bounded malformed-
            # output attempt. It cannot silently substitute a control policy.
            return '{}' if not stale and not late else None

    try:
        phase='resource_sampler_startup'
        resource_sampler=ResourceSampler(evidence.path/'resources.jsonl',model_pid=model_pid,
            period_s=RESOURCE_POLICY['sampled_watchdog']['observation_period_s'],
            gpu_timeout_s=RESOURCE_POLICY['sampled_watchdog']['gpu_query_timeout_s'])
        resource_started_at=utc();resource_started_counter=time.perf_counter()
        resource_sampler.start()
        evidence.emit('resource_sampling_started',{'path':'resources.jsonl','period_s':resource_sampler.period_s,
                      'started_at':resource_started_at,'monotonic_s':resource_started_counter,
                      'coverage':'run_episode startup, episode, restarts and cleanup; excludes model-server startup before run_episode'},sim_now())
        episode_dir.mkdir()
        assert_candidate_state_path(episode_dir,evidence.path)
        manifest={'run_id':run_id,'stage':stage,'architecture':kind,'condition':condition,'scenario':scenario,
                  'seed':world_seed,**seeds,'policy_noise_seed':policy_noise_seed,
                  'seed_semantics':{'seed':'legacy alias of world_seed','world_seed':'mass, friction, tag palette, process duration and public-rule event parameters',
                                    'layout_seed':'raw stock positions','noise_seed':'supervisor-owned readout noise; survives candidate restart',
                                    'policy_seed':'actual local-model sampling seed','policy_noise_seed':'development compatibility default only, overridden by explicit policy/noise roles'},
                  'part_count':n,'cap_s':cap,'started_at':started_at,'code_sha256':{p.name:sha(p) for p in HERE.glob('*.py')},'model':model.identity if model else None,'clock_track':'actual_host','scope':'physical-workcell development; readiness not yet established',
                  'resources':{'path':'resources.jsonl','period_s':resource_sampler.period_s,'resource_caps_enforced':False,
                               'coverage':'run_episode startup through cell/candidate cleanup; model-server startup and normal shutdown are outside this coverage'},
                  'assistance':{'policy_id':assistance.POLICY_ID,'delay_s':assistance.DELAY_S,'clock_rule':'both wall and simulation waits must reach 15 seconds',
                                'approved_answer':assistance.ANSWER,'durable_across_restarts':True,'physical_rescue':False}}
        restart_source_hashes={name:manifest['code_sha256'][name] for name in
                               ('cell.py','actuation.py','evaluator.py','sensor_worker.py')}
        if development_storage is not None:manifest['development_storage']=development_storage
        manifest['evaluation_authorization']=evaluation_authorization
        manifest['candidate_public_episode_id']=public_episode_id
        manifest['resource_policy']=RESOURCE_POLICY
        manifest['restart_opportunity']=restart_tracker.configuration()
        manifest['restart_qualification_identity']=restart_qualification['identity'] if restart_qualification else None
        if evaluation_authorization:manifest['scope']='authorized frozen evaluation; runtime validity remains independently checked'
        (evidence.path/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        phase='cell_initialization';cell=Cell(n,world_seed,noise_seed=noise_seed,layout_seed=layout_seed)
        raw_gateway=RawSensorGateway(cell,evidence.path,max_line_bytes=1024*1024-4096)
        cell.rework_part_id=scenario_service.private_config()['rework_part_id']
        evidence.emit('scenario_configuration',{'public_rules':public_rules(),'private_parameters':scenario_service.private_config()},sim_now(),'evaluator')
        phase='candidate_startup';worker=CandidateSandbox(kind,episode_dir,persistent=condition_persistent)
        usage.observe(incarnation,None)
        worker.start()
        ready=worker.ready if isinstance(worker.ready,dict) else {}
        ready_event=evidence.emit('candidate_ready',{'incarnation':incarnation,'reply':ready},sim_now(),'candidate_runtime')
        usage.observe(incarnation,ready,event_id=ready_event)
        phase='physics_initialization'
        for _ in range(250):cell.tick()
        phase='initial_world_validation'
        initial_validity=initial_world_report(cell,n,zones=ZONES,zone_half=zone_half)
        evidence.emit('initial_world_validation',initial_validity,sim_now(),'evaluator')
        if not initial_validity.get('valid'):
            raise EpisodeFailure('infrastructure_failure','Initial physical prerequisites failed: '+'; '.join(initial_validity.get('errors',[])))
        cell.prepare_sensor()
        base_sim=sim_now();last_frame=base_sim-.1;start=time.perf_counter();evidence.start=start
        evidence.emit('episode_clock_started',{'monotonic_s':start,'resource_sampler_wall_offset_s':start-resource_started_counter,
                      'base_sim_time_s':base_sim},sim_now())
        evidence.emit('initial_world',cell.truth_snapshot(),sim_now(),'evaluator')
        while True:
            elapsed=time.perf_counter()-start
            if elapsed>=cap:break
            if elapsed>=next_resource_check_wall:
                phase='resource_watchdog';next_resource_check_wall=elapsed+RESOURCE_POLICY['sampled_watchdog']['target_supervisor_check_interval_s']
                sample=resource_sampler.latest()
                resource_checked_at=time.perf_counter()
                breaches=resource_breaches(sample,now_monotonic_s=resource_checked_at,
                    sampler_started_monotonic_s=resource_started_counter,model_required=model is not None,model_pid=model_pid())
                if breaches:
                    observed={'sample':sample,'breaches':breaches,'policy':RESOURCE_POLICY['version'],
                              'checked_monotonic_s':resource_checked_at,'sampler_started_monotonic_s':resource_started_counter}
                    resource_watchdog_events.append(observed)
                    evidence.emit('resource_watchdog_exceeded',observed,sim_now(),'supervisor')
                    raise EpisodeFailure(breaches[0]['classification'],'Sampled resource watchdog failed: '+str(breaches))
            phase='physics';target=base_sim+elapsed;steps=0
            while cell.data.time<target and steps<50:
                cell.tick();steps+=1
                if cell.data.time-last_motion>=.01-1e-9:
                    telemetry_history.append(sim_now(),time.perf_counter()-start,
                        cell.data.qpos[:7].tolist(),cell.data.qvel[:7].tolist(),cell.data.actuator_force[:7].tolist(),
                        float(sum(cell.data.qpos[7:9])))
                    evidence.motion.write(json.dumps({'sim_time_s':sim_now(),'q':cell.data.qpos[:7].tolist(),'dq':cell.data.qvel[:7].tolist(),'effort':cell.data.actuator_force[:7].tolist(),'target':cell.data.ctrl[:7].tolist(),'tcp':cell.data.site_xpos[cell.tcp].tolist(),'contact_peak_N':cell.contact_peak},separators=(',',':'))+'\n')
                    last_motion=sim_now()
                if collect_completion():break
            sim=sim_now()
            if completion_landmark is not None:
                elapsed=time.perf_counter()-start;monitor.observe(elapsed,sim-base_sim)
                break
            for answer in assistance.advance(sim,time.perf_counter()-start):
                answer['event_id']=evidence.emit('scripted_human_answer',answer,sim,'public_assistance_service',[answer['parent_event_id']])
            phase='sensor_result'
            captured=cell.poll_sense()
            if captured is not None:
                raw_gateway.cache_result(captured,readout=('bounded RGB channel offset and correlated depth noise' if captured.camera=='overhead' else 'raw renderer output; no additional readout noise'))
                paths={k:Path(v['path']).relative_to(evidence.path).as_posix() for k,v in captured.artifacts.items()}
                if captured.camera=='overhead':
                    obs_sequence=captured.sequence;last_camera_result=captured
                    cell.resume_setup_if_fresh()
                    if worker.alive and not restart_pending:cell.renew_authority(order['version'],incarnation)
                    if last_capture_wall is not None:
                        gap={'sequence':obs_sequence,'wall_gap_s':captured.capture_wall_elapsed_s-last_capture_wall,
                             'sim_gap_s':captured.capture_sim_time_s-last_capture_sim}
                        gap['missed_nominal_intervals']=max(0,int((gap['wall_gap_s']+1e-6)/.1)-1)
                        camera_gaps.append(gap)
                    last_capture_wall=captured.capture_wall_elapsed_s;last_capture_sim=captured.capture_sim_time_s
                    packet=public_packet()
                    last_observation_event=evidence.emit('observation',{'packet':packet,**paths,'camera':'overhead',
                        'capture_sim_time_s':captured.capture_sim_time_s,'capture_wall_elapsed_s':captured.capture_wall_elapsed_s,
                        'delivery_sim_time_s':sim,'delivery_wall_elapsed_s':time.perf_counter()-start,
                        'worker_duration_s':captured.worker_finished_monotonic_s-captured.worker_started_monotonic_s,
                        'artifacts':captured.artifacts},sim,'sensor_gateway')
                else:
                    capture_event=evidence.emit('raw_sensor_capture',{'camera':captured.camera,'sequence':captured.sequence,
                        'capture_sim_time_s':captured.capture_sim_time_s,'capture_wall_elapsed_s':captured.capture_wall_elapsed_s,
                        'calibration':captured.calibration,'capture_joint_telemetry':captured.capture_telemetry,
                        'artifacts':captured.artifacts,**paths},sim,'sensor_gateway',
                        [raw_task['capture_parent']] if raw_task and raw_task.get('capture_parent') else [])
                    if raw_task and raw_task.get('sequence')==captured.sequence:
                        raw_task['capture_event']=capture_event
                if raw_task and raw_task['state']=='capture' and raw_task['request']['camera']==captured.camera:
                    raw_task['capture_event']=last_observation_event if captured.camera=='overhead' else capture_event
                    begin_raw_encoding()
            if raw_task and raw_task['state']=='waiting' and not cell.sensor_worker.busy:
                if raw_task['request']['camera']=='overhead':
                    if last_camera_result is not None:
                        raw_task['capture_event']=last_observation_event;begin_raw_encoding()
                    else:raw_task['state']='capture'
                else:
                    raw_capture_sequence+=1;raw_task['sequence']=-raw_capture_sequence
                    raw_task['state']='capture';camera=raw_task['request']['camera'];stem=f'raw-{raw_capture_sequence:06d}-{camera}'
                    raw_task['capture_parent']=evidence.emit('raw_sensor_capture_requested',{'camera':camera,'sequence':-raw_capture_sequence,
                        'request_id':raw_task['request']['request_id']},sim,'sensor_gateway',[raw_task['admission_event']])
                    cell.sensor_worker.request(cell.model,cell.data,sequence=-raw_capture_sequence,camera=camera,
                        capture_wall_elapsed_s=time.perf_counter()-start,rgb_path=evidence.path/'frames'/f'{stem}.png',
                        depth_path=evidence.path/'frames'/f'{stem}-depth.npz')
            if raw_encode_pending is not None and raw_encode_pending.done():
                raw_task['prepared']=raw_encode_pending.result();raw_encode_pending=None;raw_task['state']='ready'
            if sim-last_frame>=.1-1e-9:
                phase='sensor_request';slots=max(1,int((sim-last_frame+1e-9)/.1))
                if slots>1:
                    missed_capture_slots+=slots-1
                    evidence.emit('sensor_nominal_slots_missed',{'count':slots-1,'reason':'nominal instants passed before physics-owner capture'},sim,'sensor_gateway')
                last_frame+=slots*.1;capture_sequence+=slots;stem=f'{capture_sequence:06d}'
                capture=cell.request_sense(sequence=capture_sequence,capture_wall_elapsed_s=time.perf_counter()-start,
                        rgb_path=evidence.path/'frames'/f'{stem}.png',depth_path=evidence.path/'frames'/f'{stem}-depth.npz')
                if not capture['accepted']:missed_capture_slots+=1
            phase='supervisor_evidence'
            if sim-last_snapshot>=1.-1e-9:
                evidence.emit('world_snapshot',cell.truth_snapshot(),sim,'evaluator');last_snapshot=sim
            for event in cell.events[cell_event_cursor:]:
                record=lifecycle.get(event.get('request_id'),{})
                parent=record.get('admission_event_id') or record.get('request_event_id') or cycle_parents.get(event.get('cycle_id'))
                service_event=evidence.emit('physical_service_event',event,sim,'gateway',[parent] if parent else [])
                if event.get('request_id'):
                    physical_receipts[(event['request_id'],event.get('status'),event.get('sim_time'))]=service_event
                if event.get('cycle_id') is not None and event.get('request_id'):cycle_parents[event['cycle_id']]=service_event
            cell_event_cursor=len(cell.events)
            update=scenario_service.advance(sim-base_sim,cell.truth)
            if update['changed']:
                order=update['order'];amend_exercised=True
                for event in update['events']:evidence.emit('order_amendment',event,sim,'public_order_service')
                evidence.emit('scenario_exposure',update['exposures'],sim,'evaluator')
            restart_cut=restart_tracker.observe(sim-base_sim,cell.active_request,cell.segment,
                width=float(sum(cell.data.qpos[7:9])),tcp_z=float(cell.data.site_xpos[cell.tcp][2]))
            if restart_cut is not None and not restart_pending:
                phase='restart_evidence'
                capture_started={'wall_s':time.perf_counter(),'sim_s':sim_now()}
                rich=capture_restart_state(cell,zones=ZONES,zone_half=zone_half,exposure=restart_cut,
                                           source_hashes=restart_source_hashes)
                capture_finished={'wall_s':time.perf_counter(),'sim_s':sim_now()}
                restart_selection=select_restart_calibration(restart_qualification,rich)
                restart_calibration=restart_selection['calibration']
                admissibility=classify_restart(rich,calibration=restart_calibration,qualification_context=qualification_context)
                classification_finished={'wall_s':time.perf_counter(),'sim_s':sim_now()}
                restart_exercised=True;restart_pending=True
                restart_parent=evidence.emit('restart_begin',{'incarnation':incarnation,'active_request':cell.active_request,
                    'exposure':restart_cut,'protected_restart_state':rich,'restart_admissibility':admissibility,
                    'protected_snapshot':rich['geometry'],'restart_calibration':restart_calibration,
                    'restart_qualification_identity':restart_qualification['identity'] if restart_qualification else None,
                    'restart_qualification_selection':{k:v for k,v in restart_selection.items() if k!='calibration'},
                    'capture_landmarks':{'start':capture_started,'finish':capture_finished,'classification_finish':classification_finished}},sim,'evaluator')
                restart_exposure={**restart_cut,'event_id':restart_parent,'restart_admissibility':admissibility,
                                  'protected_restart_state_sha256':rich['snapshot_sha256']}
                restart_revocation={'wall_s':time.perf_counter(),'sim_s':sim_now()}
                cell.cancel('runtime incarnation revoked')
                revoked={'before_cancel':restart_revocation,'after_cancel':{'wall_s':time.perf_counter(),'sim_s':sim_now()}}
                restart_exposure['authority_revocation']=revoked
                evidence.emit('restart_authority_revoked',revoked,sim_now(),'evaluator',[restart_parent])
                if model_pending is not None:evidence.emit('model_output_invalidated',{'reason':'incarnation ended','original_incarnation':model_incarnation},sim)
                if pending is not None and pending.done() and pending_type!='restart':
                    try:
                        retired_reply=pending.result()
                        retired_event=evidence.emit('retired_candidate_reply',retired_reply,sim,'candidate_runtime',
                            [retired_reply['supervisor_input_event_id']] if retired_reply.get('supervisor_input_event_id') else [])
                        usage.observe(incarnation,retired_reply,event_id=retired_event,wall_elapsed_s=time.perf_counter()-start)
                    except Exception:pass
                incarnation+=1
                usage.observe(incarnation,None)
                retired_workers.append((incarnation-1,worker))
                pending=executor.submit(restart_worker,worker,pending,kind,episode_dir,condition_persistent,evidence.path);pending_type='restart'
                feedback_cursor=len(cell.feedback)
            phase='candidate_ipc'
            if not restart_pending and not worker.alive:
                diagnostics=worker_diagnostics(worker)
                evidence.emit('candidate_runtime_diagnostics',{'incarnation':incarnation,**diagnostics},sim,'candidate_runtime')
                classification='candidate_contract_failure' if 'CANDIDATE_CONTRACT_VIOLATION' in diagnostics['stderr_tail'] else 'candidate_transport_failure'
                raise EpisodeFailure(classification,'Candidate exited or violated its runtime contract')
            if pending is not None and pending.done():
                try:reply=pending.result()
                except Exception as exc:
                    diagnostics=worker_diagnostics(worker)
                    evidence.emit('candidate_transport_error',{'phase':pending_type,'error':str(exc),**diagnostics},sim,'candidate_runtime')
                    classification=exc.classification if isinstance(exc,EpisodeFailure) else 'candidate_transport_failure'
                    if 'CANDIDATE_CONTRACT_VIOLATION' in diagnostics['stderr_tail']:classification='candidate_contract_failure'
                    raise EpisodeFailure(classification,str(exc)) from exc
                action_response=None
                if pending_type=='restart':
                    worker=reply;restart_pending=False
                    ready=worker.ready if isinstance(worker.ready,dict) else {}
                    ready_landmark={'wall_s':time.perf_counter(),'sim_s':sim_now()}
                    absence=record_restart_absence('restart_ready',ready_landmark)
                    restart_absence_endpoint_observed=not restart_absence_settings or restart_absence_settings['absence_endpoint']=='restart_ready'
                    ready_event=evidence.emit('restart_ready',{'incarnation':incarnation,'reply':ready,'absence':absence},ready_landmark['sim_s'],parents=[restart_parent] if restart_parent else [])
                    usage.observe(incarnation,ready,event_id=ready_event,wall_elapsed_s=time.perf_counter()-start)
                else:
                    reply_event=evidence.emit('candidate_reply',reply,sim,'candidate',[reply['supervisor_input_event_id']] if reply.get('supervisor_input_event_id') else [])
                    usage.observe(incarnation,reply,event_id=reply_event,wall_elapsed_s=time.perf_counter()-start)
                    if isinstance(reply,dict) and reply.get('type')=='error':
                        raise EpisodeFailure('candidate_reported_error',json.dumps(reply))
                    action_response=reply.get('response') if isinstance(reply,dict) else None
                pending=None;pending_type=None
                if action_response:
                    if not isinstance(action_response,dict):raise EpisodeFailure('candidate_contract_failure','Candidate response is not an object')
                    response_type=action_response.get('type')
                    if response_type=='model':
                        if not isinstance(action_response.get('messages'),list) or not isinstance(action_response.get('schema'),dict):
                            raise EpisodeFailure('candidate_contract_failure','Model request requires messages and schema')
                        if model is None:raise EpisodeFailure('candidate_contract_failure','Candidate requested an unavailable model interface')
                        model_calls+=1;model_parent=evidence.emit('model_request',action_response,sim,'candidate',[reply_event]);model_incarnation=incarnation
                        model_pending=executor.submit(model.complete,action_response['messages'],action_response['schema'],max_tokens=1024,seed=policy_seed)
                    elif response_type=='action':
                        if not isinstance(action_response.get('action'),dict) or not isinstance(action_response['action'].get('operation'),str):
                            raise EpisodeFailure('candidate_contract_failure','Action request requires an operation object')
                        action=dict(action_response['action']);action.setdefault('incarnation',incarnation);action.setdefault('request_id',uuid.uuid4().hex)
                        request_event=evidence.emit('action_requested',action,sim,'candidate',[reply_event]);rid=action['request_id'];previous=lifecycle.get(rid)
                        if action.get('operation')=='help':help_request_ids.add(rid)
                        if previous and sim-previous['time']<=60:feedback={**previous['feedback'],'duplicate_suppressed':True}
                        elif action.get('order_version')!=order['version'] and action.get('operation') not in ('observe','wait','help'):
                            feedback={'request_id':rid,'status':'rejected','reason':'stale order version'}
                        elif action.get('incarnation')!=incarnation:feedback={'request_id':rid,'status':'rejected','reason':'old incarnation'}
                        else:
                            if action['operation']=='done':
                                done_assertions+=1;checked=checked_outcome()
                                if not checked['success']:false_done+=1
                                evidence.emit('completion_claim_check',checked,sim,'evaluator',[request_event])
                            if action['operation']=='help':
                                feedback=assistance.request(action,sim,time.perf_counter()-start,request_event)
                                evidence.emit('help_requested',assistance.requests[rid],sim,'public_assistance_service',[request_event])
                            else:feedback=cell.submit(action)
                            lifecycle[rid]={'feedback':feedback,'time':sim,'request_event_id':request_event}
                        admission_event=evidence.emit('action_admission',feedback,sim,'gateway',[request_event])
                        if restart_revocation is not None and not restart_pending and not restart_first_control_observed:
                            control=first_control_endpoint(action,feedback,incarnation=incarnation,
                                expected_destination=restart_qualification['destination'] if restart_qualification else None)
                            if control is not None:
                                restart_first_control_observed=True
                                record_restart_absence(control['endpoint'],{'wall_s':time.perf_counter(),'sim_s':sim_now()},
                                    [restart_parent,admission_event],control=control)
                                # The first other control ends this opportunity, even when its scope is unsupported.
                                restart_absence_endpoint_observed=True
                        if rid in lifecycle:lifecycle[rid]['admission_event_id']=admission_event
                        pending=dispatch_candidate({'type':'feedback','feedback':feedback},[admission_event]);pending_type='feedback';next_decision=sim+.15
                    elif response_type=='sensor_request':
                        raw_parent=evidence.emit('raw_sensor_request',action_response,sim,'candidate',[reply_event])
                        decision=raw_gateway.admit_request(action_response,wall_elapsed_s=time.perf_counter()-start)
                        admission_event=evidence.emit('raw_sensor_admission',decision,sim,'sensor_gateway',[raw_parent])
                        raw_task={'request':json.loads(canonical(action_response)),'incarnation':incarnation,
                                  'admission_event':admission_event,'request_event':raw_parent,'state':'waiting'}
                        if decision['status']!='accepted':
                            raw_task.update(state='ready',prepared={'message':{'type':'sensor_response','response':decision},'evidence':None})
                    elif response_type!='wait':raise EpisodeFailure('candidate_contract_failure','Unknown candidate response type')
            if raw_task and raw_task['state']=='ready' and pending is None and not restart_pending:
                prepared=raw_task['prepared'];response=prepared['message']['response'];stale=raw_task['incarnation']!=incarnation
                descriptor={**response,'images':{name:{k:v for k,v in image.items() if k!='data'} for name,image in response.get('images',{}).items()}}
                raw_response_event=evidence.emit('raw_sensor_response',{'response':descriptor,'artifacts':prepared['evidence'],
                    'original_incarnation':raw_task['incarnation'],'current_incarnation':incarnation,'stale':stale},sim,'sensor_gateway',
                    [p for p in (raw_task['admission_event'],raw_task.get('capture_event')) if p])
                if not stale:
                    pending=dispatch_candidate(prepared['message'],[raw_response_event],already_frozen=True);pending_type='sensor_response'
                else:evidence.emit('stale_raw_sensor_output_discarded',{'request_id':raw_task['request'].get('request_id')},sim,parents=[raw_response_event])
                raw_task=None
            if model_pending is not None and model_pending.done() and pending is None and not restart_pending:
                text=collect_model(model_pending);model_pending=None
                if text is not None:
                    pending=dispatch_candidate({'type':'model_response','text':text},[model_delivery_parent] if model_delivery_parent else []);pending_type='model_response'
            if pending is None and model_pending is None and not restart_pending and raw_task is None:
                if feedback_cursor<len(cell.feedback):
                    feedback=cell.feedback[feedback_cursor];feedback_cursor+=1
                    terminal_receipt(lifecycle,feedback)
                    receipt_parent=physical_receipts.get((feedback['request_id'],feedback.get('status'),feedback.get('sim_time')))
                    if receipt_parent is None:receipt_parent=lifecycle.get(feedback['request_id'],{}).get('admission_event_id')
                    pending=dispatch_candidate({'type':'feedback','feedback':feedback},[receipt_parent] if receipt_parent else []);pending_type='feedback'
                elif (cell.active_request is None or getattr(cell,'direct_control_active',False) is True) and last_observation_event is not None and sim>=next_decision:
                    packet=public_packet()
                    pending=dispatch_candidate({'type':'step','packet':packet},[last_observation_event] if last_observation_event else []);pending_type='step';next_decision=sim+.1
            phase='outcome_check'
            if sim-last_outcome>=.1-1e-9:
                checked=checked_outcome();last_outcome=sim
                if checked['success']:
                    if not collect_completion():raise EpisodeFailure('infrastructure_failure','Evaluator success lacks protected first-success record')
            # Sample AFTER physics, rendering, compression, IPC handling and logs.
            elapsed=time.perf_counter()-start;monitor.observe(elapsed,sim_now()-base_sim)
            if success:break
            remaining=start+(sim_now()-base_sim)-time.perf_counter()
            time.sleep(max(.0001,min(.002,remaining)))
    except BaseException as exc:
        error=f'{type(exc).__name__}: {exc}'
        failure_class=exc.classification if isinstance(exc,EpisodeFailure) else 'infrastructure_failure'
        if phase=='candidate_startup' and worker is not None:
            diagnostics=worker_diagnostics(worker)
            evidence.emit('candidate_runtime_diagnostics',{'incarnation':incarnation,**diagnostics},sim_now(),'candidate_runtime')
            if 'CANDIDATE_CONTRACT_VIOLATION' in diagnostics['stderr_tail']:failure_class='candidate_contract_failure'
        termination=failure_class
        try:evidence.emit('terminal_error',{'phase':phase,'classification':failure_class,'error':error},sim_now(),'supervisor')
        except Exception as log_exc:cleanup_errors.append('terminal error evidence: '+str(log_exc))
    finally:
        episode_end_wall=time.perf_counter();episode_ended_at=utc()
        sim_at_end=sim_now()
        if restart_revocation is not None and not restart_absence_endpoint_observed:
            try:record_restart_absence('episode_end_unobserved',{'wall_s':episode_end_wall,'sim_s':sim_at_end})
            except Exception as exc:cleanup_errors.append('censored absence evidence: '+str(exc))
        if start is not None:
            elapsed=episode_end_wall-start
            try:monitor.observe(elapsed,sim_now()-base_sim)
            except Exception as exc:cleanup_errors.append('final timing sample: '+str(exc))
        if cell is not None:
            try:
                final=checked_outcome()
                evidence.emit('final_world',cell.truth_snapshot(),sim_now(),'evaluator')
            except Exception as exc:
                cleanup_errors.append('final evaluator evidence: '+str(exc));failure_class='infrastructure_failure'
        if model_pending is not None:
            try:collect_model(model_pending,late=True)
            except Exception as exc:cleanup_errors.append('late model evidence: '+str(exc))
            model_pending=None
        if pending is not None and pending_type!='restart':
            try:
                late_reply=pending.result(timeout=1.)
                late_event=evidence.emit('late_candidate_reply',{'reply':late_reply,'incarnation':incarnation,
                    'after_episode_end':True,'actions_not_executed':True},sim_at_end,'candidate_runtime',
                    [late_reply['supervisor_input_event_id']] if late_reply.get('supervisor_input_event_id') else [])
                usage.observe(incarnation,late_reply,event_id=late_event,
                              wall_elapsed_s=time.perf_counter()-start if start is not None else None)
            except Exception as exc:
                evidence.emit('candidate_usage_tail_missing',{'incarnation':incarnation,'reason':type(exc).__name__},sim_at_end,'candidate_runtime')
        if raw_encode_pending is not None:
            try:
                prepared=raw_encode_pending.result(timeout=30.)
                response=prepared['message']['response']
                descriptor={**response,'images':{name:{k:v for k,v in image.items() if k!='data'} for name,image in response.get('images',{}).items()}}
                evidence.emit('late_raw_sensor_response',{'response':descriptor,'artifacts':prepared['evidence'],
                    'after_episode_end':True,'delivered_to_candidate':False},sim_at_end,'sensor_gateway',
                    [raw_task['admission_event']] if raw_task else [])
            except Exception as exc:cleanup_errors.append('raw sensor encoding cleanup: '+str(exc))
        if raw_task is not None and raw_gateway is not None:
            raw_gateway.cancel_admission(raw_task['request'].get('request_id'))
            evidence.emit('raw_sensor_request_ended',{'request_id':raw_task['request'].get('request_id'),
                'state':raw_task['state'],'after_episode_end':True,'delivered_to_candidate':False},sim_at_end,'sensor_gateway',
                [raw_task['admission_event']])
        try:sensor_encoder.shutdown(wait=True,cancel_futures=True)
        except Exception as exc:cleanup_errors.append('sensor encoder shutdown: '+str(exc))
        restart_cleanup_errors=close_pending_restart(pending,pending_type,worker)
        try:executor.shutdown(wait=True,cancel_futures=True)
        except Exception as exc:cleanup_errors.append('executor shutdown: '+str(exc))
        cleanup_errors.extend(restart_cleanup_errors)
        for worker_incarnation,diagnostic_worker in retired_workers+([(incarnation,worker)] if worker is not None else []):
            diagnostics=worker_diagnostics(diagnostic_worker)
            evidence.emit('candidate_runtime_diagnostics',{'incarnation':worker_incarnation,**diagnostics},sim_at_end,'candidate_runtime')
            if 'CANDIDATE_CONTRACT_VIOLATION' in diagnostics['stderr_tail']:
                success=False
                if failure_class not in ('infrastructure_failure','host_resource_invalid'):
                    failure_class='candidate_contract_failure';termination=failure_class
                error=error or 'Candidate contract violation recorded by protected wrapper'
        if cell is not None:
            try:
                trailing=cell.sensor_worker.wait()
                if trailing is not None:evidence.emit('late_sensor_capture',{'sequence':trailing.sequence,'camera':trailing.camera,
                    'capture_sim_time_s':trailing.capture_sim_time_s,'capture_wall_elapsed_s':trailing.capture_wall_elapsed_s,
                    'artifacts':trailing.artifacts,'delivered_to_candidate':False,'after_episode_end':True},sim_at_end,'sensor_gateway')
            except Exception as exc:cleanup_errors.append('pending sensor evidence: '+str(exc))
            try:cell.close()
            except Exception as exc:cleanup_errors.append('cell close: '+str(exc))
        if resource_sampler is not None:
            try:resource_sampler.close()
            except Exception as exc:cleanup_errors.append('resource sampler close: '+str(exc))
            try:
                resource_summary=resource_sampler.summary()
                resource_path=evidence.path/'resources.jsonl'
                resource_summary.update(path='resources.jsonl',started_at=resource_started_at,closed_at=utc(),
                                        coverage_wall_s=time.perf_counter()-resource_started_counter,
                                        episode_start_offset_s=start-resource_started_counter if start is not None else None,
                                        episode_end_offset_s=episode_end_wall-resource_started_counter,
                                        coverage='run_episode startup through cell/candidate cleanup; model-server startup and normal shutdown excluded',
                                        sha256=sha(resource_path) if resource_path.is_file() else None,
                                        bytes=resource_path.stat().st_size if resource_path.is_file() else None)
                if resource_summary.get('failure'):cleanup_errors.append('resource sampling failure: '+resource_summary['failure'])
                evidence.emit('resource_sampling_finished',resource_summary,sim_at_end)
            except Exception as exc:cleanup_errors.append('resource summary evidence: '+str(exc))
        try:evidence.emit('candidate_runtime_usage_summary',usage.summary(),sim_at_end,'candidate_runtime')
        except Exception as exc:cleanup_errors.append('candidate usage evidence: '+str(exc))
        try:evidence.close()
        except Exception as exc:cleanup_errors.append('evidence close: '+str(exc))
    timing_report=monitor.report()
    validity=result_validity(failure_class=failure_class,cleanup_errors=cleanup_errors,
        timing_failed=start is not None and not timing_report['actual_host_timing_pass'],evaluation_authorized=bool(evaluation_authorization))
    invalid=validity['infrastructure_invalid']
    reasons=[]
    if failure_class=='infrastructure_failure':reasons.append('Shared infrastructure failed in phase '+phase)
    if failure_class=='host_resource_invalid':reasons.append('Whole-host GPU resource observation exceeded policy; candidate attribution unknown')
    if cleanup_errors:reasons.append('Cleanup/evidence failure: '+'; '.join(cleanup_errors))
    if start is not None and not timing_report['actual_host_timing_pass']:reasons.append('Actual-host timing gate not met; cause is unassigned, not automatically attributed to the candidate')
    if not invalid:reasons.append('Verified frozen evaluation authorization and runtime timing checks passed' if evaluation_authorization else 'Development workcell has not passed all scored-readiness gates')
    help_summary=assistance.summary(elapsed)
    help_summary.update(requests=len(help_request_ids),any_help_requested=bool(help_request_ids),
                        rejected_before_assistance_service=len(help_request_ids)-len(assistance.requests))
    result={'run_id':run_id,'stage':stage,'execution_status':'failed' if error or cleanup_errors else 'completed',
            **seeds,'policy_noise_seed':policy_noise_seed,'resources':resource_summary,
            'initial_world_validation':initial_validity,'restart_opportunity':restart_tracker.configuration(),'restart_exposure':restart_exposure,
            'candidate_runtime_usage':usage.summary(),'evaluation_authorization':evaluation_authorization,
            'resource_policy':RESOURCE_POLICY,'resource_watchdog_events':resource_watchdog_events,
            'assistance':help_summary,'unassisted_completion':success and not help_request_ids,
            'completion_after_help':success and bool(help_request_ids),
            'outcome':('success' if success else ('partial' if final and final['accepted_count'] else 'failure')) if final is not None else 'unknown',
            **validity,'validity_reason':'; '.join(reasons),'ended_at':episode_ended_at,'finalized_at':utc(),
            'termination_reason':termination,'error':error,'failure_class':failure_class,'cleanup_errors':cleanup_errors,'independent_outcome':final,
            'wall_duration_s':elapsed if start is not None else None,'sim_duration_s':sim_at_end-base_sim if start is not None else None,
            'completion_time_s':completion_landmark['wall_elapsed_s'] if success else None,
            'completion_sim_time_s':completion_landmark['sim_time_s'] if success else None,
            'completion_landmark':({k:v for k,v in completion_landmark.items() if k not in ('protected_snapshot','outcome')}
                                   if completion_landmark is not None else None),
            'post_episode_accounting_s':time.perf_counter()-episode_end_wall,
            'model_calls':model_calls,'model_responses':model_responses,'model_failed_calls':model_failures,'late_model_responses':late_model_responses,
            'total_tokens':tokens if unknown_token_calls==0 else None,'known_total_tokens':tokens,'unknown_token_calls':unknown_token_calls,
            'model_accounting_complete':model_calls==model_responses+model_failures and unknown_token_calls==0,
            'done_assertions':done_assertions,'false_done_assertions':false_done,'restart_exercised':restart_exercised,'order_amendment_exercised':amend_exercised,
            **timing_report,'camera_gap_samples':camera_gaps,'camera_maximum_wall_gap_s':max((g['wall_gap_s'] for g in camera_gaps),default=None),
            'camera_missed_nominal_intervals':sum(g['missed_nominal_intervals'] for g in camera_gaps),'camera_rejected_or_missed_slots':missed_capture_slots,
            'camera_capture_requests':capture_sequence,'last_delivered_camera_sequence':obs_sequence,
            'motion_path_m':cell.total_path if cell is not None else None,'contact_peak_N':cell.contact_peak if cell is not None else None,
            'contact_impulse_Ns':cell.collision_impulse if cell is not None else None,
            'limits':(['Development only; no scored inference until shared readiness passes'] if not evaluation_authorization else [])+['Timing gates do not determine whether lag was candidate or host/harness induced','One-second timing boundaries interpolate adjacent wall/sim samples; maximum sample gap retained','Contact impulse includes intended contacts; not a collision-only metric','Candidate CPU/IO are observed lower bounds with unmeasured final intervals']}
    if development_storage is not None:result['development_storage']=development_storage
    temporary=evidence.path/'result.json.tmp';temporary.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');os.replace(temporary,evidence.path/'result.json')
    print(json.dumps(result,indent=2),flush=True)
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--kind',choices=['baseline','A1','A2','A3'],default='baseline');parser.add_argument('--parts',type=int,default=3);parser.add_argument('--seed',type=int,default=None,help='Legacy alias of --world-seed');parser.add_argument('--world-seed',type=int,default=None);parser.add_argument('--policy-noise-seed',type=int,default=0);parser.add_argument('--layout-seed',type=int);parser.add_argument('--noise-seed',type=int);parser.add_argument('--policy-seed',type=int);parser.add_argument('--cap',type=float,default=300);parser.add_argument('--scenario',choices=['nominal','order_change','restart','mixed'],default='nominal');parser.add_argument('--condition',choices=['persistent','no-persistence'],default='persistent');parser.add_argument('--run-id')
    parser.add_argument('--development-raw-root',type=Path,help='Absolute evidence root for development only')
    parser.add_argument('--development-restart-freeze',type=Path,
                        help='Prior byte-verified qualification input for development only; never evaluation authority')
    args=parser.parse_args()
    try:seeds=resolve_seed_roles(args.seed,args.world_seed,args.policy_noise_seed,args.layout_seed,args.noise_seed,args.policy_seed)
    except ValueError as exc:parser.error(str(exc))
    kwargs={'kind':args.kind,'n':args.parts,**seeds,'policy_noise_seed':args.policy_noise_seed,'cap':args.cap,'scenario':args.scenario,'condition':args.condition,'run_id':args.run_id}
    kwargs['development_raw_root']=args.development_raw_root
    if args.development_restart_freeze is not None:
        from restart_calibration_loader import load_restart_qualification
        qualification=load_restart_qualification(json.loads(args.development_restart_freeze.read_text(encoding='utf-8')),
                                                args.development_restart_freeze)
        if qualification is None:parser.error('Development restart input must explicitly select qualified_class mode')
        kwargs['development_restart_qualification']=qualification
    if args.kind=='baseline':run_episode(**kwargs)
    else:
        from model_runtime import LocalModel
        with LocalModel() as model:run_episode(model=model,**kwargs)

if __name__=='__main__':main()
