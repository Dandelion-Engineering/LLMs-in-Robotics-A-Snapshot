"""Versioned native recorder integration using existing frozen physical components.

This bounded engineering runner deliberately has no model, candidate sandbox,
release runner, Architecture Map writer, or scored-experiment entry point.
It wires real physics, public sensing, raw response transport and independent
scoring to the future backend. Future candidate orchestration can use these
same explicit service hooks; this does not retrofit frozen r4 runs.
"""
from __future__ import annotations
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import time

HERE=Path(__file__).resolve().parent
EXP=HERE.parents[1]
sys.path.insert(0,str(EXP/'Runtime 004'))
from cell import Cell, DT
from experiment import PublicTelemetryHistory, TimingMonitor, initial_order
from sensors import RawSensorGateway
from recorder import ImagePolicy, Reader, pack, RecordingFailure
from runtime_adapter import FutureEvidence, LiveSensorBridge


class NativeRawGateway(RawSensorGateway):
    """Live response encoding is frozen; exact requested blobs are core evidence.

    No per-request raw-sensors directory is written. Requested live image bytes
    are decision evidence and therefore count against the core quota, unlike
    unrequested sparse/diagnostic camera imagery. Excessive image requests stop
    the run explicitly; they cannot bypass its storage cap.
    """
    def __init__(self,cell,evidence,**kwargs):
        super().__init__(cell,evidence.path,**kwargs); self.evidence=evidence; self.saved={}
    def _write_artifact(self,capture,modality,content,*,variant=None):
        sha=hashlib.sha256(content).hexdigest(); key=modality if variant is None else modality+':'+variant
        if sha not in self.saved:
            self.evidence.document('raw-exact-'+sha,{'content_base64':base64.b64encode(content).decode('ascii'),
                'bytes':len(content),'sha256':sha,'scope':'exact candidate-requested live image encoding'})
            self.saved[sha]=True
        record={'relative_path':None,'object_id':sha,'storage':'sustainable-evidence-1',
                'sha256':sha,'bytes':len(content)}
        capture.artifacts[key]=record; return record
    def materialize_cached_request(self,*args,**kwargs):
        value=super().materialize_cached_request(*args,**kwargs)
        # Frozen gateway converts RuntimeError into an unavailable reply. A core
        # storage stop is stronger: it must reach the future supervisor endpoint.
        if self.evidence.store.stopped: raise RecordingFailure('Raw decision evidence quota failure')
        return value


class NativeSupervisor:
    """Owner-thread service integration; caller controls candidate decisions."""
    def __init__(self,directory,*,run_id,seed=173,record=True):
        self.cell=Cell(3,seed,noise_seed=13); self.cell.prepare_sensor()
        # Complete a warm acquisition before timed qualification.
        self.cell.render()
        self.record=record; self.evidence=(FutureEvidence(directory,run_id,
            policy=ImagePolicy(sparse_period_s=2,image_quota_bytes=8_000_000),
            core_quota_bytes=30_000_000) if record else None)
        self.bridge=LiveSensorBridge(self.evidence) if record else None
        self.raw=NativeRawGateway(self.cell,self.evidence) if record else None
        self.history=PublicTelemetryHistory(); self.order=initial_order(3)
        self.monitor=TimingMonitor(); self.live_pairs=0; self.unchanged_pairs=True
        self.input_digest=hashlib.sha256(); self.initial_sim=float(self.cell.data.time)
        self.start=None; self.observation_sequence=0
        self.actions=[]

    def public_packet(self,wall):
        stamp=float(self.cell.data.time)
        arm={**self.cell.public_arm_interfaces(),'telemetry_history':self.history.packet(stamp,wall,0)}
        return {**self.cell.public_packet(self.order,'qualification-public',1,self.observation_sequence),'arm':arm}

    def step(self,tick):
        cell=self.cell; cell.tick(); stamp=float(cell.data.time)
        wall=time.perf_counter()-self.start
        if tick in (500,1500):
            values=cell.data.qpos[:7].tolist(); values[0]+=.02 if tick==500 else -.02
            action={'operation':'joint_command','request_id':'qualification-'+str(tick),
                    'mode':'position','values':values,'duration_s':.5,'incarnation':1,'order_version':1}
            if self.record: self.evidence.emit('action_requested',action,stamp,'candidate_gateway')
            reply=cell.submit(action); assert reply['status']=='accepted',reply
            if self.record: self.evidence.emit('action_admission',reply,stamp,'gateway')
            self.actions.append({'action':action,'reply':reply})
        if tick%5==0:
            self.history.append(stamp,wall,cell.data.qpos[:7],cell.data.qvel[:7],
                                cell.data.actuator_force[:7],float(sum(cell.data.qpos[7:9])))
            if self.record:
                row={'sim_time_s':stamp,'q':cell.data.qpos[:7].tolist(),'dq':cell.data.qvel[:7].tolist(),
                    'effort':cell.data.actuator_force[:7].tolist(),'target':cell.data.ctrl[:7].tolist(),
                    'tcp':cell.data.site_xpos[cell.tcp].tolist(),'contact_peak_N':cell.contact_peak}
                self.evidence.motion.write(json.dumps(row,separators=(',',':'))+'\n')
        captured=cell.poll_sense()
        if captured is not None:
            before=(captured.rgb.tobytes(),captured.depth.tobytes(),captured.detections_json,
                    captured.calibration_json,captured.telemetry_json,captured.capture_sim_time_s,
                    captured.capture_wall_elapsed_s)
            if self.record:
                delivered=self.bridge.observe(captured)
                self.unchanged_pairs &= delivered is captured
                self.raw.cache_result(captured)
            else: delivered=captured
            after=(delivered.rgb.tobytes(),delivered.depth.tobytes(),delivered.detections_json,
                   delivered.calibration_json,delivered.telemetry_json,delivered.capture_sim_time_s,
                   delivered.capture_wall_elapsed_s)
            self.unchanged_pairs &= before==after; self.live_pairs+=1
            self.observation_sequence+=1
            packet=self.public_packet(wall); frozen=copy.deepcopy(packet)
            if self.record: self.evidence.emit('observation',packet,stamp,'sensor_gateway')
            assert packet==frozen
        if tick%50==0:
            # No full-stream path is passed: these live arrays survive only in the
            # sensor's existing bounded work item, current packet and recorder ring.
            cell.request_sense(sequence=tick//50,capture_wall_elapsed_s=wall,rgb_path=None,depth_path=None)
        self.monitor.observe(time.perf_counter()-self.start,stamp-self.initial_sim)

    def run(self,seconds=10):
        self.start=time.perf_counter()
        if self.record:
            # Match recorded envelope wall origin to this runner's timed episode.
            self.evidence.start=self.start
            self.evidence.emit('episode_clock_started',{},float(self.cell.data.time))
        for tick in range(1,round(seconds/DT)+1):
            self.step(tick)
            delay=self.start+tick*DT-time.perf_counter()
            if delay>0: time.sleep(delay)
        report=self.monitor.report(); outcome=self.cell.outcome(self.order,acceptance_open=True)
        state=self.cell.truth_snapshot()
        if self.record:
            self.evidence.emit('final_world',state,float(self.cell.data.time),'evaluator')
            self.evidence.document('result',outcome)
        return {'timing':report,'outcome':outcome,'final_state':state,
                'live_pairs':self.live_pairs,'sensor_missed':self.cell.sensor_missed_captures,
                'fixed_joint_actions':self.actions,'completed_feedback':copy.deepcopy(self.cell.feedback),
                'live_pair_identity_and_content_unchanged':self.unchanged_pairs}

    def close(self):
        self.cell.close()
        if self.evidence is not None: self.evidence.close()


def qualify(output):
    output=Path(output); output.mkdir(parents=True,exist_ok=False)
    reports=[]; raw_report=None
    for name,record in [('reference',False),('recorded',True)]:
        supervisor=NativeSupervisor(output/name,run_id='native-qualification-'+name,record=record)
        try:
            reports.append(supervisor.run())
            if record:
                captured=supervisor.cell.last_sensor_result; assert captured is not None
                frozen=RawSensorGateway(supervisor.cell,output/'raw-reference',clock=lambda:1000.)
                native=supervisor.raw; native.clock=lambda:1000.
                for gateway in (frozen,native):
                    gateway.cache_result(captured)
                    gateway._cached['overhead'].capture_id='fixed-qualification-capture'
                request={'type':'sensor_request','request_id':'raw-qualification','camera':'overhead','modalities':['rgb','depth']}
                admitted_a=frozen.admit_request(request,wall_elapsed_s=10.)
                admitted_b=native.admit_request(request,wall_elapsed_s=10.)
                assert admitted_a==admitted_b and admitted_a['status']=='accepted'
                current=frozen._telemetry()
                wire_a=frozen.encode_cached_request(request,wall_elapsed_s=10.5,current_telemetry=current)
                wire_b=native.encode_cached_request(request,wall_elapsed_s=10.5,current_telemetry=current)
                assert wire_a==wire_b and json.loads(wire_b)['status']=='ok'
                assert not (supervisor.evidence.path/'raw-sensors').exists()
                failed=FutureEvidence(output/'raw-quota-stop','raw-quota-stop',core_quota_bytes=4096)
                failing=NativeRawGateway(supervisor.cell,failed,clock=lambda:1000.)
                failing.cache_result(captured); failing.admit_request(request,wall_elapsed_s=10.)
                did_stop=False
                try: failing.encode_cached_request(request,wall_elapsed_s=10.5,current_telemetry=current)
                except RecordingFailure: did_stop=True
                finally: failed.close()
                assert did_stop
                raw_report={'exact_candidate_wire_bytes':True,'wire_sha256':hashlib.sha256(wire_b).hexdigest(),
                    'wire_bytes':len(wire_b),'exact_capture_and_delivery_metadata':True,
                    'new_raw_sensor_files':0,'core_quota_failure_reaches_supervisor':True,
                    'reference_scope':'One frozen gateway request retains its bounded reference pair under raw-reference, not a full stream'}
        except Exception as exc:
            if supervisor.evidence is not None and not supervisor.evidence.store.stopped:
                try: supervisor.evidence.store.fail('Native supervisor exception: '+type(exc).__name__)
                except RecordingFailure: pass
            raise
        finally: supervisor.close()
    reference,recorded=reports
    # Same fixed physics/control sequence must end in exactly the same state.
    assert pack(reference['final_state'])==pack(recorded['final_state'])
    assert pack(reference['outcome'])==pack(recorded['outcome'])
    assert pack(reference['fixed_joint_actions'])==pack(recorded['fixed_joint_actions'])
    assert pack(reference['completed_feedback'])==pack(recorded['completed_feedback'])
    assert recorded['live_pair_identity_and_content_unchanged']
    assert not list((output/'recorded').rglob('*.png')) and not list((output/'recorded').rglob('*.npz'))
    reader=Reader(output/'recorded'); frames=list(reader.images())
    retained=sum(f['status']=='available' for f in frames)
    assert 0<retained<recorded['live_pairs']; reader.close()
    return {'scope':'Real workcell with two fixed small joint actions; no model, candidate experiment or scored task',
        'duration_s_each':10,'same_physical_state':True,'same_independent_task_scoring':True,
        'live_sensor_content_unchanged':True,'full_camera_files_created':0,
        'retained_pairs':retained,'recorded':recorded,'reference':reference,
        'raw_request_equivalence':raw_report,
        'frozen_timing_gate_pass':all(r['timing']['actual_host_timing_pass'] for r in reports),
        'limit':'Two fixed joint actions do not qualify whole-task orchestration, restart, inference or full release timing.'}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True); args=p.parse_args()
    result=qualify(args.output)
    (args.output/'qualification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'timing_pass':result['frozen_timing_gate_pass'],'retained_pairs':result['retained_pairs']}))
