"""Queue-only bounded physical calibration; never an architecture experiment.

Default: contact pickup -> actual closed-grip carry cut -> recover_held parking2.
Optional probes exercise public arm adapters and a matched servo-force inverse.
No candidate/model is run. No object qpos is written, welded or teleported.
Each independent probe owns a fresh Cell and immutable evidence subdirectory.
The parent process enforces hard child wall caps, including startup/cleanup.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
import uuid
import zipfile
from calibration_authority import parent_authority,child_authority,child_command

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[3]
RUNTIME=PROJECT/'Runtime 004'
QUEUE_STATE=PROJECT.parent.parent/'tools'/'compute_queue'/'runtime'/'state.json'
MODES=('insert-exchange','held-recovery','held-recovery-parking1','adapters','effort-equivalence','raw-cameras','static-sensors')
SIM_CAPS={'insert-exchange':180.,'held-recovery':180.,'held-recovery-parking1':180.,'adapters':60.,'effort-equivalence':20.,'raw-cameras':45.,'static-sensors':20.}
HARD_CAPS={'insert-exchange':225.,'held-recovery':225.,'held-recovery-parking1':225.,'adapters':105.,'effort-equivalence':65.,'raw-cameras':90.,'static-sensors':85.}
STATIC_WORLDS=((3,0),(6,1),(10,2))
SCHEMA='physical-calibration-1.0'


def utc():return datetime.now(timezone.utc).isoformat()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def sha(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):result.update(block)
    return result.hexdigest()
def save(path,value):
    path=Path(path);temp=path.with_name(path.name+'.tmp')
    with temp.open('w',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(temp,path)


def source_files():
    result={p.resolve() for p in RUNTIME.glob('*.py')}
    result.update(p.resolve() for p in HERE.glob('*.py'))
    result.update(p.resolve() for p in HERE.glob('*.md'))
    result.update(p.resolve() for p in (RUNTIME/'vendor'/'panda').rglob('*') if p.is_file())
    return sorted(result)


def source_hashes():return {str(p):sha(p) for p in source_files()}


class CalibrationFailure(RuntimeError):pass


class Records:
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=False)
        self.events=(self.root/'events.jsonl').open('w',encoding='utf-8',newline='\n')
        self.trace=(self.root/'trajectory.jsonl').open('w',encoding='utf-8',newline='\n')
        self.sequence=0;self.started=time.perf_counter()
    def event(self,kind,payload,sim=None):
        self.sequence+=1
        value={'event_id':self.sequence,'event_type':kind,'wall_elapsed_s':time.perf_counter()-self.started,
               'sim_time_s':sim,'payload':payload,'payload_sha256':hashlib.sha256(canonical(payload)).hexdigest()}
        self.events.write(canonical(value).decode()+'\n');self.events.flush()
        return self.sequence
    def motion(self,value):self.trace.write(canonical(value).decode()+'\n');self.trace.flush()
    def close(self):
        for stream in (self.events,self.trace):stream.flush();os.fsync(stream.fileno());stream.close()


class StablePredicate:
    def __init__(self,dwell_s=.5):self.dwell_s=dwell_s;self.since=None;self.last=None
    def update(self,sim,valid):
        if self.last is not None and (sim<self.last or sim-self.last>.004001):self.since=None
        self.last=sim
        if not valid:self.since=None
        elif self.since is None:self.since=sim
        return self.since is not None and sim-self.since>=self.dwell_s-1e-9


def placement_check(snapshot,part_id,destination,gripper_width):
    """Independent physical check for RAW placement, not recipe/task success."""
    item=next((o for o in snapshot['objects'] if o['id']==part_id),None)
    region=snapshot['zones'].get(destination)
    flags={'identity_present':item is not None,'zone_exists':region is not None,
           'open_gripper':gripper_width>=.065,
           'no_pending_work':not any(snapshot['pending'].values()),
           'arm_settled':max(map(abs,snapshot['arm_velocity']))<=.02,
           'fingers_settled':max(map(abs,snapshot['finger_velocity']))<=.01}
    if item is not None and region is not None:
        flags.update(full_containment=all(region['min'][i]-1e-6<=item['position'][i]<=region['max'][i]+1e-6
                      and item['bounds']['min'][i]>=region['min'][i]-1e-6
                      and item['bounds']['max'][i]<=region['max'][i]+1e-6 for i in range(3)),
                     no_gripper_contact=item['gripper_contact'] is False,
                     part_slow=sum(v*v for v in item['linear_velocity'])<=.05**2
                               and sum(v*v for v in item['angular_velocity'])<=.10**2,
                     remains_raw=item.get('recipe') is None and item.get('cycles')==0)
        overlaps=[o['id'] for o in snapshot['objects'] if all(min(o['bounds']['max'][i],region['max'][i])-max(o['bounds']['min'][i],region['min'][i])>1e-6 for i in range(3))]
        flags['single_pad_occupant']=overlaps==[part_id]
    return {'passed_now':all(flags.values()),'flags':flags,'part_id':part_id,'destination':destination,
            'interpretation':'raw transport/settling calibration only; not inspection, processing or complete robot task'}


class PhysicalLoop:
    """One physics owner, copied asynchronous camera work, real-time pacing."""
    def __init__(self,records,mode,seed,count=1,world_specs=None):
        sys.path.insert(0,str(RUNTIME))
        import numpy as np
        from cell import Cell,DT,ZONES,zone_half
        from experiment import TimingMonitor
        from initial_conditions import initial_world_report
        self.np=np;self.dt=DT;self.zones=ZONES;self.zone_half=zone_half
        self.world_specs=list(world_specs or [(3,seed)]*count);count=len(self.world_specs)
        self.records=records;self.mode=mode;self.cells=[];self.monitor=TimingMonitor();self.sequence=0
        self.camera_slot=-1.;self.incarnation=1;self.event_cursors=[0]*count;self.latest=[];self.on_tick=None
        self.automatic_camera=True;self.on_capture=None
        self.base_sim=None;self.start=None;self.last_trace=-1.;self.last_snapshot=-1.
        self.cap=SIM_CAPS[mode];self.closed=False
        try:
            for index,(part_count,world_seed) in enumerate(self.world_specs):
                cell=Cell(part_count,world_seed,noise_seed=0,layout_seed=world_seed);self.cells.append(cell)
                (records.root/f'camera-{index}').mkdir()
                (records.root/f'world-{index}.xml').write_text(cell.xml,encoding='utf-8')
                for _ in range(250):cell.tick()
                report=initial_world_report(cell,part_count,zones=ZONES,zone_half=zone_half)
                records.event('protected_initial_validity',{'world':index,**report},float(cell.data.time))
                if not report['valid']:raise CalibrationFailure('initial physical world did not pass preflight')
                cell.prepare_sensor()
            self.base_sim=float(self.cells[0].data.time);self.start=time.perf_counter();records.started=self.start
            self.latest=[None]*count
            records.event('calibration_clock_started',{'mode':mode,'sim_cap_s':self.cap,'worlds':count,
                          'development_world_specs':self.world_specs,
                          'launch_settling_s':.5,'worlds_run_in_one_owner_loop':True},self.base_sim)
        except BaseException:
            self.close();raise

    @property
    def elapsed(self):return float(self.cells[0].data.time)-self.base_sim
    def snapshot(self,index=0):return self.cells[index].evaluator.snapshot_cell(self.cells[index],zones=self.zones,zone_half=self.zone_half)
    def public_ready(self):return all(c.last_detections and c.data.time-c.detection_time<=.35 for c in self.cells)
    def step(self):
        if time.perf_counter()-self.start>=self.cap or self.elapsed>=self.cap:raise CalibrationFailure('fixed calibration cap reached')
        control_elapsed=self.elapsed  # Both paired worlds use the same pre-step time.
        for index,cell in enumerate(self.cells):
            if self.on_tick:self.on_tick(index,cell,control_elapsed)
            if cell.data.time-cell.detection_time<=.35:cell.renew_authority(1,self.incarnation)
            cell.tick()
        sim=float(self.cells[0].data.time)
        for index,cell in enumerate(self.cells):
            for event in cell.events[self.event_cursors[index]:]:self.records.event('cell_event',{'world':index,**event},sim)
            self.event_cursors[index]=len(cell.events)
            result=cell.poll_sense()
            if result is not None:
                self.latest[index]=result
                # Match the experiment supervisor: a completed overhead capture
                # advances the setup service only after its public witness check.
                if result.camera=='overhead':cell.resume_setup_if_fresh()
                self.records.event('sensor_capture',{'world':index,'sequence':result.sequence,'camera':result.camera,
                    'capture_sim_time_s':result.capture_sim_time_s,'capture_wall_elapsed_s':result.capture_wall_elapsed_s,
                    'delivery_sim_time_s':sim,'delivery_wall_elapsed_s':time.perf_counter()-self.start,
                    'calibration':result.calibration,'detections':result.detections,'artifacts':result.artifacts},sim)
                if self.on_capture:self.on_capture(index,result)
        if self.automatic_camera and self.elapsed-self.camera_slot>=.1-1e-9:
            self.camera_slot=self.elapsed;self.sequence+=1
            for index,cell in enumerate(self.cells):
                folder=self.records.root/f'camera-{index}'
                request=cell.request_sense(sequence=self.sequence,capture_wall_elapsed_s=time.perf_counter()-self.start,
                         rgb_path=folder/f'{self.sequence:06d}.png',depth_path=folder/f'{self.sequence:06d}-depth.npz')
                if not request['accepted']:self.records.event('camera_slot_rejected',{'world':index,**request},sim)
        if self.elapsed-self.last_trace>=.01-1e-9:
            self.last_trace=self.elapsed
            self.records.motion({'sim_time_s':sim,'elapsed_sim_s':self.elapsed,'wall_elapsed_s':time.perf_counter()-self.start,
                'worlds':[{'qpos':c.data.qpos.tolist(),'qvel':c.data.qvel.tolist(),'ctrl':c.data.ctrl.tolist(),
                           'actuator_force':c.data.actuator_force.tolist(),'tcp':c.data.site_xpos[c.tcp].tolist(),
                           'active_request':c.active_request,'segment_phase':c.segment.get('phase') if c.segment else None,
                           'contact_peak_N':c.contact_peak} for c in self.cells]})
        if self.elapsed-self.last_snapshot>=.1-1e-9:
            self.last_snapshot=self.elapsed
            self.records.event('protected_snapshots',[self.snapshot(i) for i in range(len(self.cells))],sim)
        wall=time.perf_counter()-self.start;self.monitor.observe(wall,self.elapsed)
        delay=self.start+self.elapsed-time.perf_counter()
        if delay>0:time.sleep(min(delay,.002))
    def until(self,predicate,timeout):
        limit=self.elapsed+timeout
        while self.elapsed<limit:
            self.step()
            if predicate():return
        raise CalibrationFailure('bounded phase did not reach its predicate in '+str(timeout)+' seconds')
    def wait(self,duration):
        target=self.elapsed+duration
        self.until(lambda:self.elapsed>=target,duration+.01)
    def submit(self,action,index=0):
        action={**action,'request_id':action.get('request_id',uuid.uuid4().hex),'order_version':1,'incarnation':self.incarnation}
        self.records.event('action_intent',{'world':index,'action':action},float(self.cells[index].data.time))
        response=self.cells[index].submit(action)
        self.records.event('action_admission',{'world':index,'action':action,'response':response},float(self.cells[index].data.time))
        if response.get('status')!='accepted':raise CalibrationFailure('action rejected: '+str(response))
        return action['request_id']
    def terminal(self,rid,index=0,timeout=12.):
        cell=self.cells[index]
        self.until(lambda:any(r.get('request_id')==rid and r.get('status') in ('completed','failed','cancelled') for r in cell.feedback),timeout)
        receipt=next(r for r in reversed(cell.feedback) if r.get('request_id')==rid)
        if receipt['status']!='completed':raise CalibrationFailure('command terminated without completion: '+str(receipt))
        return receipt
    def close(self):
        if self.closed:return
        self.closed=True
        failures=[]
        for index,cell in enumerate(self.cells):
            try:
                if cell.active_request:cell.cancel('calibration cleanup')
                if cell.sensor_worker.busy:
                    trailing=cell.sensor_worker.wait()
                    if trailing is not None:self.records.event('trailing_sensor_evidence',{'world':index,'sequence':trailing.sequence,'artifacts':trailing.artifacts,'not_delivered':True},float(cell.data.time))
                self.records.event('final_protected_world',{'world':index,'snapshot':self.snapshot(index)},float(cell.data.time))
                cell.close()
            except Exception as exc:failures.append(f'world{index}: {type(exc).__name__}: {exc}')
        if failures:raise RuntimeError('calibration cleanup failed: '+'; '.join(failures))


def held_recovery(loop):
    from restart_state import capture_restart_state, classify_restart
    destination='parking1' if loop.mode=='held-recovery-parking1' else 'parking2'
    cell=loop.cells[0];loop.until(loop.public_ready,8.)
    visible=sorted(d['id'] for d in cell.last_detections if d.get('kind')=='part' and d.get('visible_mark')=='raw' and d.get('zone')=='raw')
    if not visible:raise CalibrationFailure('no fresh image-derived raw workpiece available')
    part_id=visible[0]
    loop.records.event('public_pick_selection',{'part_id':part_id,'source_sequence':loop.latest[0].sequence,
                        'rule':'lexically first image-derived visible raw part; no protected pose used for pickup'},float(cell.data.time))
    rid=loop.submit({'operation':'transport','part_id':part_id,'destination':'inspection'})
    cut={}
    def actually_carrying():
        if not cell.segment or cell.segment.get('phase') not in (4,5):return False
        item=next(o for o in loop.snapshot()['objects'] if o['id']==part_id)
        good=item['gripper_contact'] and item['position'][2]>.075 and .005<float(sum(cell.data.qpos[7:9]))<.065
        if good:cut.update(snapshot=loop.snapshot(),phase=cell.segment['phase'],sim_time_s=float(cell.data.time))
        return good
    loop.until(actually_carrying,75.)
    exposure={'configured_cut':'closed_grip_transfer','actual_cut':'closed_grip_transfer',
              'configured_milestone_exercised':True,'fallback_used':False,'active_request_id':rid,
              'part_id':part_id,'destination':'inspection'}
    protected=capture_restart_state(cell,zones=loop.zones,zone_half=loop.zone_half,exposure=exposure,
                                    source_hashes=loop.physical_source_hashes)
    assessment=classify_restart(protected)
    loop.records.event('verified_carry_authority_cut',{'request_id':rid,'part_id':part_id,**cut,
                       'protected_restart_state':protected,'restart_admissibility':assessment,
                       'intervention':'Cell.cancel revokes command authority; no candidate process or memory condition exists'},float(cell.data.time))
    cell.cancel('physical calibration closed-grip carry interruption');loop.incarnation+=1
    loop.wait(1.)  # Actual physics continues during this declared absence.
    after_cut=loop.snapshot();item=next(o for o in after_cut['objects'] if o['id']==part_id)
    loop.records.event('protected_held_state_after_absence',capture_restart_state(cell,zones=loop.zones,
            zone_half=loop.zone_half,exposure=exposure,source_hashes=loop.physical_source_hashes),float(cell.data.time))
    remained_held=bool(item['gripper_contact'] and item['position'][2]>.075)
    loop.until(loop.public_ready,8.)
    recovery=loop.submit({'operation':'recover_held','destination':destination})
    loop.terminal(recovery,timeout=60.)
    stability=StablePredicate();last_check={}
    def placed():
        check=placement_check(loop.snapshot(),part_id,destination,float(sum(cell.data.qpos[7:9])))
        last_check.clear();last_check.update(check)
        # This predicate is evaluated after EVERY physics step during this phase.
        return stability.update(float(cell.data.time),check['passed_now'])
    loop.until(placed,15.)
    loop.records.event('independent_raw_placement_check',{'check':last_check,'dwell_s':.5,
                        'stable_since_sim_s':stability.since,'checked_every_physics_tick':True},float(cell.data.time))
    return {'physical_predicates_passed':remained_held and last_check['passed_now'],
            'picked_visible_part_id':part_id,'verified_closed_grip_cut':True,'remained_held_after_one_second':remained_held,
            'recovery_destination':destination,'destination_center_m':list(loop.zones[destination]),
            'latest_public_detection_after_placement':next((d for d in cell.last_detections if d['id']==part_id),None),
            'latest_public_capture_sim_time_s':cell.detection_time,
            'independent_final_check':last_check,'settled_dwell_s':.5,
            'not_tested':['candidate restart/memory recovery','process eligibility','inspection','complete task success']}


def native_servo_displacement(initial_joint,initial_native_target,final_joint,final_native_target):
    """Measured local response; do not assume a gravity-free position servo.

    The reference uses ONLY the measured pre-command offset, never the final
    error. Absolute native-target error remains separately reported.
    """
    rows=[[float(v) for v in row] for row in (initial_joint,initial_native_target,final_joint,final_native_target)]
    if any(len(row)!=7 or any(not math.isfinite(float(v)) for v in row) for row in rows):
        raise ValueError('finite seven-joint calibration vectors required')
    initial,old_target,final,target=rows
    offset=[q-u for q,u in zip(initial,old_target)]
    expected=[u+d for u,d in zip(target,offset)]
    local_error=max(abs(q-r) for q,r in zip(final,expected))
    absolute_error=max(abs(q-u) for q,u in zip(final,target))
    return {'basis':'local displacement from prior measured servo offset; not absolute position accuracy',
            'initial_native_target_rad':old_target,'final_native_target_rad':target,
            'measured_initial_servo_offset_rad':offset,'expected_physical_joint_rad':expected,
            'expected_displacement_rad':[u-v for u,v in zip(target,old_target)],
            'observed_displacement_rad':[q-p for q,p in zip(final,initial)],
            'maximum_local_displacement_error_rad':local_error,
            'maximum_absolute_native_target_error_rad':absolute_error}


def adapters(loop):
    cell=loop.cells[0];np=loop.np;loop.until(loop.public_ready,8.);checks=[]
    def execute(name,action,expected_joint=None,expected_tcp=None,expected_native_joint=None):
        initial_q=cell.data.qpos[:7].copy();initial_tcp=cell.data.site_xpos[cell.tcp].copy()
        initial_native_target=cell.data.ctrl[:7].copy()
        maxima={'joint0_positive_rad':0.,'tcp_z_positive_m':0.}
        def measure(index,current,elapsed):
            maxima['joint0_positive_rad']=max(maxima['joint0_positive_rad'],float(current.data.qpos[0]-initial_q[0]))
            maxima['tcp_z_positive_m']=max(maxima['tcp_z_positive_m'],float(current.data.site_xpos[current.tcp][2]-initial_tcp[2]))
        loop.on_tick=measure
        try:
            rid=loop.submit(action);receipt=loop.terminal(rid,timeout=4.);loop.wait(.35)
        finally:loop.on_tick=None
        final_q=cell.data.qpos[:7].copy();final_tcp=cell.data.site_xpos[cell.tcp].copy()
        safe=bool(np.all(np.isfinite(final_q)) and cell.arm_adapter.workspace_contains(final_tcp)
                  and cell.active_request is None and float(sum(cell.data.qpos[7:9]))>=.065)
        tracking=(native_servo_displacement(initial_q,initial_native_target,final_q,expected_native_joint)
                  if expected_native_joint is not None else None)
        qerr=(tracking['maximum_local_displacement_error_rad'] if tracking is not None else
              (float(np.max(np.abs(final_q-expected_joint))) if expected_joint is not None else None))
        endpoint_preserved=(bool(np.allclose(cell.data.ctrl[:7],expected_native_joint,rtol=0,atol=1e-10))
                            if expected_native_joint is not None else None)
        tcp_error=float(np.linalg.norm(final_tcp-expected_tcp)) if expected_tcp is not None else None
        motion_min={'joint_position':.005,'joint_velocity':.001,'timestamped_trajectory':.002,'cartesian_target':.0005}
        observed=maxima['tcp_z_positive_m'] if name=='cartesian_target' else maxima['joint0_positive_rad']
        response_seen=(observed>=motion_min[name]) if name in motion_min else any(
            e.get('type')=='direct_control_limits' and e.get('request_id')==rid and e.get('mode')=='effort' for e in cell.events)
        joint_tolerance=.025 if name=='bounded_effort' else .005
        passed=(safe and response_seen and endpoint_preserved is not False
                and (qerr is None or qerr<=joint_tolerance) and (tcp_error is None or tcp_error<=.012))
        result={'interface':name,'request_id':rid,'terminal_receipt':receipt,'passed':passed,
                'initial_joint':initial_q.tolist(),'final_joint':final_q.tolist(),'initial_tcp':initial_tcp.tolist(),
                'final_tcp':final_tcp.tolist(),'maximum_joint_error_rad':qerr,'tcp_error_m':tcp_error,
                'measurement_revision':'native-servo-local-displacement-1',
                'joint_error_basis':tracking['basis'] if tracking else 'physical measured-pose hold',
                'native_servo_tracking':tracking,'native_endpoint_preserved':endpoint_preserved,
                'absolute_native_target_within_005rad':(tracking['maximum_absolute_native_target_error_rad']<=.005
                                                       if tracking else None),
                'joint_tolerance_rad':joint_tolerance,'tcp_tolerance_m':.012,'safe_terminal_checks':safe,
                'physical_response_or_effort_adapter_report_seen':response_seen,'measured_peak_motion':maxima,
                'minimum_commanded_axis_motion':motion_min.get(name)}
        checks.append(result);loop.records.event('adapter_probe_check',result,float(cell.data.time))
        if not passed:raise CalibrationFailure(name+' physical tracking/terminal check failed')
    # Native servo targets differ from physical joints under gravity. Change
    # the stable target on axis0; compare measured displacement at the same
    # .005rad tolerance and retain absolute setpoint error separately.
    q=cell.data.ctrl[:7].copy();q[0]+=.015
    execute('joint_position',{'operation':'joint_command','mode':'position','values':q.tolist(),'duration_s':1.},expected_native_joint=q)
    q=cell.data.qpos[:7].copy();target=q.copy();target[0]+=.005
    execute('joint_velocity',{'operation':'joint_command','mode':'velocity','values':[.01,0,0,0,0,0,0],'duration_s':.5},expected_native_joint=target)
    now=float(cell.data.time);q=cell.data.ctrl[:7].copy();middle=q.copy();middle[0]+=.01
    execute('timestamped_trajectory',{'operation':'trajectory','waypoints':[{'time_s':now+.5,'positions':middle.tolist()},
            {'time_s':now+1.,'positions':q.tolist()}],'deadline_s':now+1.},expected_native_joint=q)
    tcp=cell.data.site_xpos[cell.tcp].copy();tcp[2]+=.003
    execute('cartesian_target',{'operation':'cartesian_target','position':tcp.tolist(),'duration_s':1.5},expected_tcp=tcp)
    # A short measured-effort hold exercises the PUBLIC effort request path;
    # it is not a claim that constant effort reproduces a position trajectory.
    q=cell.data.qpos[:7].copy();effort=cell.data.actuator_force[:7].copy()
    execute('bounded_effort',{'operation':'joint_command','mode':'effort','values':effort.tolist(),'duration_s':.05},expected_joint=q)
    return {'physical_predicates_passed':all(c['passed'] for c in checks),'checks':checks,
            'limits':'small unloaded native-servo response; local displacement is not absolute joint accuracy; no payload/full-workspace/controller-robustness claim'}


def effort_equivalence(loop):
    """Paired fresh worlds; no state copying, replay reset or object relocation.

    A common slow position target is the reference controller. The inverse arm
    computes that same servo's instantaneous force from ITS OWN robot telemetry
    and inverts it at the native500 Hz. This checks adapter equivalence under
    that matched controller, not arbitrary100 Hz torque-policy equivalence.
    """
    np=loop.np;a,b=loop.cells;loop.until(loop.public_ready,8.)
    initial_gap=float(np.max(np.abs(a.data.qpos-b.data.qpos)))
    if initial_gap>1e-10:raise CalibrationFailure('independent paired worlds did not start identically')
    base=a.data.ctrl[:7].copy();started=loop.elapsed;rows=0;max_q=max_v=max_force=max_ctrl=0.;clipped=0
    applied={}
    stream=(loop.records.root/'equivalence-500hz.jsonl').open('w',encoding='utf-8',newline='\n')
    def target(elapsed):
        phase=min(max((elapsed-started)/4.,0.),1.)
        result=base.copy();result[0]+=.01*math.sin(math.pi*phase)**2
        return result
    def control(index,cell,elapsed):
        nonlocal clipped
        reference=target(elapsed)
        applied[index]={'elapsed_sim_s':elapsed,'target_rad':reference.tolist()}
        if index==0:cell.data.ctrl[:7]=reference
        else:
            desired=cell.arm_adapter.force(reference,cell.data.qpos[:7],cell.data.qvel[:7])
            controls,report=cell.arm_adapter.effort(desired,cell.data.qpos[:7],cell.data.qvel[:7])
            cell.data.ctrl[:7]=controls
            clipped+=sum(report['clipped'])
    loop.on_tick=control
    try:
        while loop.elapsed-started<4.:
            loop.step();rows+=1
            qgap=float(np.max(np.abs(a.data.qpos-b.data.qpos)));vgap=float(np.max(np.abs(a.data.qvel-b.data.qvel)))
            fgap=float(np.max(np.abs(a.data.actuator_force-b.data.actuator_force)));cgap=float(np.max(np.abs(a.data.ctrl-b.data.ctrl)))
            max_q=max(max_q,qgap);max_v=max(max_v,vgap);max_force=max(max_force,fgap);max_ctrl=max(max_ctrl,cgap)
            record={'sim_time_s':float(a.data.time),'applied_references':dict(applied),
                    'native':{'qpos':a.data.qpos.tolist(),'qvel':a.data.qvel.tolist(),'ctrl':a.data.ctrl.tolist(),'force':a.data.actuator_force.tolist()},
                    'inverse':{'qpos':b.data.qpos.tolist(),'qvel':b.data.qvel.tolist(),'ctrl':b.data.ctrl.tolist(),'force':b.data.actuator_force.tolist()},
                    'maximum_qpos_difference':qgap,'maximum_velocity_difference':vgap,'maximum_effort_difference':fgap}
            stream.write(canonical(record).decode()+'\n');stream.flush()
    finally:loop.on_tick=None;stream.flush();os.fsync(stream.fileno());stream.close()
    passed=max_q<=1e-7 and max_v<=1e-6 and max_force<=1e-5
    result={'physical_predicates_passed':passed,'physics_steps':rows,'duration_sim_s':loop.elapsed-started,
            'maximum_all_body_qpos_difference':max_q,'maximum_all_body_velocity_difference':max_v,
            'maximum_actuator_force_difference_N':max_force,'maximum_ctrl_difference':max_ctrl,
            'inverse_clipped_joint_samples':clipped,'thresholds':{'qpos':1e-7,'velocity':1e-6,'force':1e-5},
            'scope':'physical-step agreement of unchanged native servo and its inverse under a matched500 Hz target controller',
            'not_established':['pure torque motor equivalence','arbitrary100 Hz desired-effort policy equivalence','task completion','payload robustness']}
    loop.records.event('matched_physical_step_comparison',result,float(a.data.time))
    return result


def raw_cameras(loop):
    """Real asynchronous RGB-D capture -> gateway -> isolated stdlib decoder."""
    from sandbox import CandidateSandbox,SandboxLimits
    from sensors import RawSensorGateway
    from experiment import prepare_raw_reply,pin_sensor_gateway
    from raw_camera_fixture import check_no_paths
    cell=loop.cells[0];checks=[];captures={};worker=None
    executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='calibration-raw-ipc')
    loop.automatic_camera=False
    loop.on_capture=lambda index,result:captures.__setitem__(result.sequence,result)
    gateway=RawSensorGateway(cell,loop.records.root,max_line_bytes=1024*1024-4096)
    def await_future(future,timeout=8.):
        loop.until(future.done,timeout)
        return future.result()
    def exchange(message):
        def invoke():
            worker.send(message)
            return worker.receive(8.)
        return await_future(executor.submit(invoke),9.)
    try:
        worker=CandidateSandbox('raw-camera-calibration-fixture',loop.records.root/'fixture-work',persistent=True,
            candidate_path=HERE/'raw_camera_fixture.py',limits=SandboxLimits(cpu_seconds=20,wall_seconds=50,startup_seconds=20))
        await_future(executor.submit(worker.start),22.)
        loop.records.event('raw_fixture_ready',worker.ready,float(cell.data.time))
        for ordinal,camera in enumerate(('overhead','oblique','wrist'),1):
            asked=exchange({'type':'step','packet':{'camera':camera}})
            request=asked['response']
            loop.records.event('raw_fixture_request',asked,float(cell.data.time))
            if request!={'type':'sensor_request','request_id':'fixture-'+camera,'camera':camera,'modalities':['rgb','depth']}:
                raise CalibrationFailure('Sandbox fixture returned unexpected raw request')
            admitted=gateway.admit_request(request,wall_elapsed_s=time.perf_counter()-loop.start)
            loop.records.event('raw_request_admission',admitted,float(cell.data.time))
            if admitted['status']!='accepted':raise CalibrationFailure('Raw request was not admitted')
            sequence=-ordinal;folder=loop.records.root/'camera-0';stem='raw-'+camera
            options={'sequence':sequence,'capture_wall_elapsed_s':time.perf_counter()-loop.start,
                     'rgb_path':folder/(stem+'.png'),'depth_path':folder/(stem+'-depth.npz')}
            if camera=='overhead':accepted=cell.request_sense(**options)['accepted']
            else:accepted=cell.sensor_worker.request(cell.model,cell.data,camera=camera,**options)
            if not accepted:raise CalibrationFailure('Shared sensor worker rejected an idle capture')
            loop.until(lambda:sequence in captures,5.)
            captured=captures[sequence]
            capture_id=gateway.cache_result(captured,readout=('Cell.request_sense noisy overhead' if camera=='overhead' else 'Shared SensorWorker native on-demand camera'))
            telemetry={'sim_time_s':float(cell.data.time),'joint_position_rad':cell.data.qpos[:7].tolist(),
                       'joint_velocity_rad_s':cell.data.qvel[:7].tolist(),'actuator_effort_Nm':cell.data.actuator_force[:7].tolist(),
                       'measured_gripper_width_m':float(sum(cell.data.qpos[7:9]))}
            prepared=await_future(executor.submit(prepare_raw_reply,pin_sensor_gateway(gateway),request,
                         time.perf_counter()-loop.start,telemetry),5.)
            message=prepared['message'];response=message['response'];ipc=canonical(message)+b'\n'
            (loop.records.root/(stem+'-ipc.json')).write_bytes(ipc)
            # No expected decoded bytes/hashes or operator paths are sent to the fixture.
            check_no_paths(message)
            if str(loop.records.root).encode() in ipc or str(PROJECT).encode() in ipc:
                raise CalibrationFailure('Protected host path appeared in outgoing IPC')
            reply=exchange(message)
            loop.records.event('raw_fixture_delivery',{'camera':camera,'request_id':request['request_id'],
                'encoded_ipc_bytes':len(ipc),'encoded_ipc_sha256':hashlib.sha256(ipc).hexdigest(),
                'operator_evidence':prepared['evidence'],'reply':reply},float(cell.data.time))
            decoded=next((e['result'] for e in reply.get('events',[]) if e.get('event')=='decoded_raw_camera'),None)
            if decoded is None:
                failure={'camera':camera,'gateway_status':response.get('status'),
                         'gateway_reason':response.get('reason'),'reply_type':reply.get('type'),
                         'reply_error':reply.get('error'),'reply_message':str(reply.get('message',''))[:512]}
                loop.records.event('raw_round_trip_rejected',failure,float(cell.data.time))
                raise CalibrationFailure(camera+' raw round trip failed: '+canonical(failure).decode())
            expected={'rgb':hashlib.sha256(captured.rgb.tobytes(order='C')).hexdigest(),
                      'depth':hashlib.sha256(captured.depth.astype('<f4',copy=False).tobytes(order='C')).hexdigest()}
            flags={'identity':decoded['capture_id']==capture_id and decoded['request_id']==request['request_id'] and decoded['camera']==camera,
                   'sequence':decoded['capture_sequence']==sequence,
                   'capture_time':decoded['capture_sim_time_s']==captured.capture_sim_time_s,
                   'calibration':decoded['calibration_sha256']==hashlib.sha256(canonical(captured.calibration)).hexdigest(),
                   'rgb_bytes':decoded['images']['rgb']['decoded_sha256']==expected['rgb'],
                   'depth_bytes':decoded['images']['depth']['decoded_sha256']==expected['depth'],
                   'dimensions':all(decoded['images'][m]['width_px']==640 and decoded['images'][m]['height_px']==480 for m in expected),
                   'operator_paths_absent':decoded['operator_paths_absent'],
                   'stdlib_decoder':decoded['decoded_in_stdlib_only_fixture'],'ipc_under_cap':len(ipc)<1024*1024}
            check={'camera':camera,'passed':all(flags.values()),'flags':flags,'decoded':decoded,
                   'operator_expected_decoded_hashes':expected}
            checks.append(check);loop.records.event('independent_raw_round_trip_check',check,float(cell.data.time))
            if not check['passed']:raise CalibrationFailure(camera+' raw round-trip bytes/identity did not match')
        loop.wait(1.)
        return {'physical_predicates_passed':len(checks)==3 and all(c['passed'] for c in checks),'checks':checks,
                'scope':'actual camera permission and data-fidelity calibration; no LLM image understanding, robot policy or task outcome'}
    finally:
        loop.on_capture=None
        try:
            if worker is not None:
                worker.close()
                loop.records.event('raw_fixture_shutdown',{'termination':worker.termination,'failure':worker.failure,
                                   'stderr':worker.stderr},float(cell.data.time))
        finally:executor.shutdown(wait=True,cancel_futures=True)


def sensor_comparison(captured,protected):
    """Operator-only pose/missingness measurement; does not alter public data."""
    true={o['id']:o for o in protected['objects']}
    seen={d['id']:d for d in captured['detections']}
    rows=[]
    for identity,obj in true.items():
        observed=seen.get(identity)
        row={'id':identity,'kind':obj['kind'],'family':obj['family'],'detected':observed is not None,
             'protected_capture_position_m':obj['position']}
        if observed is not None:
            error=[observed['pos'][i]-obj['position'][i] for i in range(3)]
            norm=math.sqrt(sum(v*v for v in error))
            row.update(observed_position_m=observed['pos'],signed_axis_error_m=error,euclidean_error_m=norm,
                       public_uncertainty_m=observed['uncertainty_m'],public_pixels=observed['pixels'],
                       public_zone=observed['zone'],public_visible_mark=observed['visible_mark'],
                       error_within_reported_scalar=norm<=observed['uncertainty_m'])
        rows.append(row)
    return {'rows':rows,'missing_ids':sorted(set(true)-set(seen)),'unexpected_ids':sorted(set(seen)-set(true)),
            'detected_expected_count':len(set(true)&set(seen)),
            'uncertainty_interpretation':'Euclidean error versus the existing scalar is a diagnostic; no confidence/coverage guarantee is invented.'}


def static_sensors(loop):
    loop.automatic_camera=False;captures={};reports=[]
    loop.on_capture=lambda index,result:captures.__setitem__((index,result.sequence),result)
    try:
        for index,cell in enumerate(loop.cells):
            part_count,seed=loop.world_specs[index];samples=[]
            for ordinal in range(1,4):
                sequence=ordinal;folder=loop.records.root/f'camera-{index}';stem=f'static-{ordinal:02d}'
                protected=loop.snapshot(index)
                capture_sim=float(cell.data.time)
                request=cell.request_sense(sequence=sequence,capture_wall_elapsed_s=time.perf_counter()-loop.start,
                         rgb_path=folder/(stem+'.png'),depth_path=folder/(stem+'-depth.npz'))
                if not request['accepted']:raise CalibrationFailure('Static sensor request was not admitted')
                loop.until(lambda:(index,sequence) in captures,4.)
                captured=captures[(index,sequence)]
                if abs(captured.capture_sim_time_s-capture_sim)>1e-9:raise CalibrationFailure('Static truth/frame capture clocks differ')
                comparison=sensor_comparison({'detections':captured.detections},protected)
                sample={'world':index,'part_count':part_count,'development_seed':seed,'sequence':sequence,
                        'capture_sim_time_s':capture_sim,'protected_capture_snapshot':protected,
                        'public_detections_unchanged':captured.detections,'comparison':comparison,'artifacts':captured.artifacts}
                samples.append(sample);loop.records.event('static_sensor_measurement',sample,float(cell.data.time))
                loop.wait(.1)
            ids={o['id'] for o in samples[0]['protected_capture_snapshot']['objects']}
            ever_seen={d['id'] for s in samples for d in s['public_detections_unchanged']}
            errors=[r['euclidean_error_m'] for s in samples for r in s['comparison']['rows'] if r['detected']]
            report={'part_count':part_count,'development_seed':seed,'samples':len(samples),
                    'never_visible_ids':sorted(ids-ever_seen),'visible_every_sample_ids':sorted(set.intersection(*[
                        {d['id'] for d in s['public_detections_unchanged']} for s in samples])),
                    'maximum_observed_center_error_m':max(errors) if errors else None,
                    'observed_error_samples':len(errors),'missingness_by_sample':[s['comparison']['missing_ids'] for s in samples],
                    'outside_existing_uncertainty_scalar_samples':sum(not r['error_within_reported_scalar']
                        for s in samples for r in s['comparison']['rows'] if r['detected'])}
            reports.append(report)
        loop.wait(1.)
        return {'physical_predicates_passed':len(reports)==3 and all(r['samples']==3 for r in reports),
                'checks_mean':'Nine real image/pose/missingness measurements completed; no perceptual accuracy gate is inferred',
                'reports':reports,'perception_readiness_claimed':False,'public_uncertainty_modified':False,
                'scope':'initial static development scenes only; no motion/occlusion/processed-mark/generalization accuracy claim'}
    finally:loop.on_capture=None


def child(mode,output,seed,parent_manifest,manifest_sha256):
    queue=child_authority(__file__,mode,output,seed,parent_manifest,manifest_sha256)
    before=source_hashes();records=Records(output);loop=None;status='failed';details=None;error=None
    save(records.root/'probe-manifest.json',{'schema_version':SCHEMA,'mode':mode,'seed':seed,'queue':queue,
         'created_at':utc(),'source_hashes':before,'simulation_cap_s':SIM_CAPS[mode],'hard_process_cap_s':HARD_CAPS[mode],
         'scope':'physical calibration; not candidate/model or complete-task evaluation'})
    try:
        loop=PhysicalLoop(records,mode,seed,count=2 if mode=='effort-equivalence' else 1,
                          world_specs=STATIC_WORLDS if mode=='static-sensors' else None)
        loop.physical_source_hashes={name:before[str((RUNTIME/name).resolve())]
                                     for name in ('cell.py','actuation.py','evaluator.py','sensor_worker.py')}
        from insert_exchange_probe import run as insert_exchange
        details={'insert-exchange':insert_exchange,'held-recovery':held_recovery,'held-recovery-parking1':held_recovery,'adapters':adapters,'effort-equivalence':effort_equivalence,
                 'raw-cameras':raw_cameras,'static-sensors':static_sensors}[mode](loop)
        status='passed' if details['physical_predicates_passed'] else 'failed'
    except BaseException as exc:
        status='failed' if isinstance(exc,CalibrationFailure) else 'infrastructure_failure'
        error=type(exc).__name__+': '+str(exc)
        records.event('probe_failure',{'error':error,'traceback':traceback.format_exc()},None if loop is None else float(loop.cells[0].data.time))
    finally:
        timing=loop.monitor.report() if loop is not None else None
        if loop is not None:
            try:loop.close()
            except Exception as exc:error=(error+'; ' if error else '')+'cleanup: '+str(exc);status='infrastructure_failure'
        after=source_hashes();unchanged=before==after
        if not unchanged:status='infrastructure_failure';error=(error+'; ' if error else '')+'source bytes changed during calibration'
        result={'schema_version':SCHEMA,'mode':mode,'status':status,'details':details,'error':error,'finished_at':utc(),
                'source_hashes_before':before,'source_hashes_after':after,'sources_unchanged':unchanged,'timing':timing,
                'scope':'calibration predicates only; no architecture experiment or successful robot task is claimed'}
        records.event('probe_terminal',result);records.close();save(Path(output)/'result.json',result)
    return 0  # Physical failures are retained outcomes, not missing process results.


def parent(args):
    queue=parent_authority(__file__);root=Path(args.output).resolve();root.mkdir(parents=True,exist_ok=False)
    before=source_hashes();modes=list(MODES) if args.mode=='all' else [args.mode]
    with zipfile.ZipFile(root/'source-bundle.zip','x',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in source_files():
            if path.suffix in ('.py','.md','.xml'):archive.write(path,path.relative_to(PROJECT).as_posix())
    manifest={'schema_version':SCHEMA,'created_at':utc(),'queue':queue,'modes':modes,'seed':args.seed,
         'source_hashes':before,'source_bundle_sha256':sha(root/'source-bundle.zip'),
         'hard_wall_cap_s':sum(HARD_CAPS[m] for m in modes),'launch_and_cleanup_included_in_child_caps':True,
         'environment':{'python':platform.python_version(),'platform':platform.platform(),
                        'mujoco':importlib.metadata.version('mujoco'),'numpy':importlib.metadata.version('numpy')},
         'not_run':False,'classification':'physical calibration, never a scored architecture comparison'}
    manifest_path=root/'manifest.json'
    with manifest_path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(manifest,stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    manifest_sha256=sha(manifest_path)
    summaries=[]
    for mode in modes:
        path=root/mode;command=child_command(sys.executable,Path(__file__).resolve(),mode,path,args.seed,manifest_path,manifest_sha256)
        with (root/(mode+'-stdout.log')).open('wb') as stdout,(root/(mode+'-stderr.log')).open('wb') as stderr:
            process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            timed_out=False
            try:code=process.wait(timeout=HARD_CAPS[mode])
            except subprocess.TimeoutExpired:
                timed_out=True;process.kill();code=process.wait(timeout=10.)
        result_path=path/'result.json'
        if result_path.exists() and not timed_out and code==0:
            outcome=json.loads(result_path.read_text(encoding='utf-8'))
            summary={'mode':mode,'status':outcome['status'],'result_path':str(result_path.relative_to(root)),
                     'result_sha256':sha(result_path),'error':outcome['error'],
                     'actual_host_timing_pass':(outcome.get('timing') or {}).get('actual_host_timing_pass')}
        else:
            summary={'mode':mode,'status':'infrastructure_failure','exit_status':code,'hard_timeout':timed_out,
                     'error':'Child did not return a complete terminal record; partial raw evidence retained',
                     'partial_evidence_path':str(path.relative_to(root))}
        summaries.append(summary);save(root/'progress.json',{'finished':summaries,'remaining':[m for m in modes if m not in [s['mode'] for s in summaries]]})
    after=source_hashes();unchanged=before==after
    result={'schema_version':SCHEMA,'finished_at':utc(),'queue_job_id':queue['job_id'],'probes':summaries,
            'sources_unchanged':unchanged,'source_hashes_after':after,'all_declared_probe_checks_passed':unchanged and all(r['status']=='passed' for r in summaries),
            'all_host_timing_checks_passed':all(r.get('actual_host_timing_pass') is True for r in summaries),
            'robot_task_success_claimed':False,'scored_release_ready_claimed':False}
    save(root/'summary.json',result)
    files=[{'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(root.rglob('*')) if p.is_file()]
    save(root/'evidence-index.json',{'schema_version':SCHEMA,'files':files})
    print(json.dumps(result,indent=2));return 0


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=(*MODES,'all'),default='held-recovery')
    parser.add_argument('--output',required=True,help='Fresh protected evidence directory; never overwritten')
    parser.add_argument('--seed',type=int,default=0,help='Explicit development seed, not held-out evaluation generation')
    parser.add_argument('--_child',choices=MODES,help=argparse.SUPPRESS)
    parser.add_argument('--parent-manifest',help=argparse.SUPPRESS)
    parser.add_argument('--parent-manifest-sha256',help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    if not 0<=args.seed<2**63:parser.error('seed must be a nonnegative63-bit development value')
    if args._child and (not args.parent_manifest or not args.parent_manifest_sha256):parser.error('Child requires its immutable parent manifest and hash')
    return child(args._child,args.output,args.seed,args.parent_manifest,args.parent_manifest_sha256) if args._child else parent(args)


if __name__=='__main__':raise SystemExit(main())
