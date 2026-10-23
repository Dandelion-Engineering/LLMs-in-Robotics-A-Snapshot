"""Single-owner native physics; original synchronous persistence stays supervisory.

This is a prospective infrastructure revision, not a recovery-policy change.
All Cell access is confined to CellDriver, on the ContinuousPhysics owner.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import threading
import time

from physics_worker import ContinuousPhysics

HERE = Path(__file__).resolve().parent
RCI = HERE.parents[1]
EXPERIMENT = RCI.parent
RUNTIME = EXPERIMENT / 'Runtime 004'
RECORDER = EXPERIMENT / 'Storage Retention Implementation 001/future'
sys.path.insert(0, str(RCI / 'host'))
from challenges import source_binding, apply_initial_fixture
from supervisor import GatewayError


class CellDriver:
    def __init__(self, owner, manifest, public_id):
        self.owner, self.manifest, self.public_id = owner, manifest, public_id
        self.thread = threading.get_ident()
        sys.path.insert(0, str(RUNTIME))
        from cell import Cell
        self.cell = Cell(manifest['operator_only_fixture']['part_count'], manifest['seed'], noise_seed=manifest['noise_seed'])
        try:
            self.initialize(manifest)
        except BaseException:
            self.cell.close()
            raise

    def initialize(self, manifest):
        apply_initial_fixture(self.cell, manifest)
        for _ in range(500):
            self.cell.tick()
        self.initial_sim = self.now
        self.cell.prepare_sensor()
        self.cell.sense()
        self.order = copy.deepcopy(manifest['operator_only_fixture']['order'])
        self.cell._eval_order = self.order
        self.cell._acceptance_open = True
        self.epoch = 1
        self.sequence = self.capture = self.ticks = 0
        self.feedback_cursor = self.events_cursor = 0
        self.next_camera = self.now
        self.force_observe = False
        self.accepted = {}
        self.skill_started = None
        self.snapshot(initial=True)

    def check_owner(self):
        if threading.get_ident() != self.thread:
            raise RuntimeError('Cell accessed outside its sole owner')

    @property
    def now(self):
        self.check_owner()
        return float(self.cell.data.time)

    def packet(self):
        packet = self.cell.public_packet(self.order, self.public_id, self.epoch, self.sequence)
        packet.update(arm=self.cell.public_arm_interfaces(), tcp_position_m=self.cell.data.site_xpos[self.cell.tcp].tolist(), restart_generation=0)
        return copy.deepcopy(packet)

    def snapshot(self, initial=False):
        self.check_owner()
        value = {'now': self.now, 'tcp': self.cell.data.site_xpos[self.cell.tcp].tolist(),
                 'joints': self.cell.data.qpos[:7].tolist(),
                 'busy': self.cell.active_request is not None or self.cell._planning_busy(),
                 'outcome': self.cell.outcome(self.order, acceptance_open=True)}
        if initial:
            value.update(initial_sim=self.initial_sim, order=copy.deepcopy(self.order), packet=self.packet())
        self.owner.publish_snapshot(value)

    def set_authority(self, epoch):
        self.check_owner()
        if type(epoch) is not int or epoch < self.epoch:
            raise RuntimeError('Authority generation regressed')
        if epoch != self.epoch and self.cell.active_request is not None:
            self.cell.cancel('authority generation changed')
        self.epoch = epoch

    def submit(self, action, receipt):
        self.check_owner()
        rid = action.get('request_id')
        fingerprint = receipt.get('fingerprint')
        if rid in self.accepted:
            # A duplicate RPC is never replayed even when main lost its reply.
            old = self.accepted[rid]
            if old['fingerprint'] != fingerprint:
                raise RuntimeError('Native request identity conflict')
            return copy.deepcopy(old['feedback'])
        if len(self.accepted) >= 5000:
            raise RuntimeError('Native request identity bound exceeded')
        reasons = []
        if receipt.get('durable_intent') is not True or not isinstance(fingerprint, str) or len(fingerprint) != 64:
            reasons.append('durable intent identity absent')
        if action.get('incarnation') != self.epoch or receipt.get('epoch') != self.epoch:
            reasons.append('stale authority at native dispatch')
        if action.get('order_version') != self.order['version'] or receipt.get('order_version') != self.order['version']:
            reasons.append('stale order at native dispatch')
        capture = receipt.get('capture_sim_time_s')
        if type(capture) not in (int, float) or not 0 <= self.now - capture <= .35:
            reasons.append('referenced observation expired before native dispatch')
        if not isinstance(rid, str) or receipt.get('request_id') != rid:
            reasons.append('request identity mismatch')
        if reasons:
            feedback = {'status': 'rejected', 'request_id': rid, 'reason': '; '.join(reasons)}
        else:
            feedback = self.cell.submit(copy.deepcopy(action))
            if feedback.get('status') == 'accepted' and self.cell.active_request is not None:
                self.skill_started = receipt['requested_sim_time_s']
        feedback = {**feedback, 'continuous_dispatch': {
            'request_id': rid, 'fingerprint': fingerprint, 'epoch': self.epoch,
            'order_version': self.order['version'], 'observation_sequence': receipt.get('observation_sequence'),
            'capture_sim_time_s': capture, 'dispatch_sim_time_s': self.now,
            'durable_intent_before_rpc': receipt.get('durable_intent') is True,
            'fence_passed': not reasons, 'rejection_reasons': reasons}}
        self.accepted[rid] = {'fingerprint': fingerprint, 'feedback': copy.deepcopy(feedback)}
        self.snapshot()
        return feedback

    def request_observation(self):
        self.check_owner()
        self.force_observe = True

    def collect_feedback(self):
        for feedback in self.cell.feedback[self.feedback_cursor:]:
            self.owner.publish('feedback', feedback)
        self.feedback_cursor = len(self.cell.feedback)
        for event in self.cell.events[self.events_cursor:]:
            self.owner.publish('event', event)
        self.events_cursor = len(self.cell.events)

    def tick(self):
        self.check_owner()
        if self.cell.active_request is not None and self.skill_started is not None and self.now - self.skill_started > 90.:
            self.cell.cancel('maximum independent skill interval reached')
        self.cell.renew_authority(self.order['version'], self.epoch)
        self.cell.tick()
        self.ticks += 1
        if self.ticks % 5 == 0:
            self.owner.publish('motion', {'sim_time_s': self.now, 'q': self.cell.data.qpos[:7].tolist(),
                'dq': self.cell.data.qvel[:7].tolist(), 'tcp': self.cell.data.site_xpos[self.cell.tcp].tolist(),
                'effort': self.cell.data.actuator_force[:7].tolist(),
                'gripper_width_m': float(sum(self.cell.data.qpos[7:9])), 'target': self.cell.data.ctrl[:7].tolist()})
        captured = self.cell.poll_sense()
        if captured is not None:
            self.sequence += 1
            self.cell.resume_setup_if_fresh()
            self.owner.publish('capture', {'captured': captured, 'packet': self.packet()})
        self.collect_feedback()
        if self.now >= self.next_camera or self.force_observe:
            if not self.cell.sensor_worker.busy:
                self.capture += 1
                self.cell.request_sense(sequence=self.capture,
                    capture_wall_elapsed_s=time.perf_counter()-self.owner._capture.origin, rgb_path=None, depth_path=None)
                self.force_observe = False
                self.next_camera = self.now + .1
        self.snapshot()

    def cancel(self, reason):
        self.check_owner()
        self.cell.cancel(reason)
        self.collect_feedback()
        self.snapshot()

    def close(self):
        self.check_owner()
        self.cell.close()


class ContinuousAdapter:
    def __init__(self, manifest, evidence, workspace, public_id):
        sys.path.insert(0, str(RUNTIME))
        sys.path.insert(0, str(RECORDER))
        from candidates import Candidate
        from instrumented_recorder import InstrumentedFutureEvidence, InstrumentedLiveSensorBridge
        from recorder import ImagePolicy
        self.manifest, self.workspace, self.public_id = manifest, Path(workspace), public_id
        self.source_hashes = source_binding(RUNTIME)
        self.recorder_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in RECORDER.glob('*.py')}
        if manifest.get('recorder_source_sha256') is not None and manifest['recorder_source_sha256'] != self.recorder_hashes:
            raise ValueError('Recorder source differs from registered manifest')
        self.timing_capture = None
        self.supervisor = None
        self.worker = ContinuousPhysics(lambda worker: CellDriver(worker, manifest, public_id),
                                        sim_cap_s=manifest['sim_cap_s'], wall_cap_s=manifest['wall_cap_s'])
        try:
            initial = self.worker.snapshot
            self.initial_sim, self.order, self.committed_packet = initial['initial_sim'], initial['order'], initial['packet']
            self.recording = InstrumentedFutureEvidence(Path(evidence)/'native-recording', manifest['run_id'],
                policy=ImagePolicy(sparse_period_s=2., image_quota_bytes=12_000_000), core_quota_bytes=50_000_000, phase=self.phase)
            self.bridge = InstrumentedLiveSensorBridge(self.recording, phase=self.phase)
            self.baseline = Candidate('baseline', Path(evidence)/'baseline-workspace', True)
            self.save_requested_image = False
            self.explicit_images = 0
        except BaseException:
            try:
                self.worker.close()
            finally:
                if hasattr(self, 'recording'):
                    self.recording.close()
            raise
        self.last_epoch = 1
        self.requested_capture_after = None

    def phase(self, name):
        from contextlib import nullcontext
        if self.timing_capture is None or self.timing_capture.terminal is not None:
            return nullcontext()
        return self.timing_capture.phase(name, lambda: self.now)

    @property
    def now(self):
        return self.worker.now

    def tcp_position(self):
        return self.worker.snapshot['tcp']

    def joints(self):
        return self.worker.snapshot['joints']

    def busy(self):
        return self.worker.snapshot['busy']

    def packet(self, epoch):
        packet = copy.deepcopy(self.committed_packet)
        packet['incarnation'] = epoch
        return packet

    def submit(self, action):
        supervisor = self.supervisor
        record = supervisor.commands[action['request_id']]
        envelope = record['envelope']
        # Called only after Supervisor.command's synchronous dispatched event
        # and registry writes return. Never infer durability from an RPC reply.
        receipt = {'durable_intent': record['phase'] == 'dispatched', 'fingerprint': record['fingerprint'],
                   'request_id': record['request_id'], 'epoch': supervisor.epoch,
                   'order_version': envelope['order_version'],
                   'observation_sequence': envelope.get('observation_sequence'),
                   'capture_sim_time_s': supervisor.observations.get(envelope.get('observation_sequence')),
                   'requested_sim_time_s': record['requested_sim_time_s']}
        self.synchronize(supervisor.epoch)
        return self.worker.rpc('submit', action, receipt)

    def synchronize(self, epoch):
        if epoch != self.last_epoch:
            self.worker.rpc('set_authority', epoch)
            self.last_epoch = epoch

    def cancel(self, reason):
        if self.worker.terminal is None:
            self.worker.rpc('cancel', reason)

    def request_observation(self):
        self.requested_capture_after = self.now
        self.worker.rpc('request_observation')
        self.save_requested_image = True

    def step(self, supervisor, wall, *, final=False):
        if not final and self.worker.terminal is None:
            self.worker.heartbeat()
            try:
                self.synchronize(supervisor.epoch)
            except Exception:
                if self.worker.error or self.worker.terminal not in ('simulation_time_cap', 'wall_time_cap'):
                    raise
        for message in self.worker.drain():
            kind, payload = message['kind'], message['payload']
            if kind == 'motion':
                self.recording.motion.write(json.dumps(payload, separators=(',', ':'))+'\n')
            elif kind == 'capture':
                captured, packet = payload['captured'], payload['packet']
                self.bridge.observe(captured)
                if (self.save_requested_image and self.explicit_images < 50
                        and captured.capture_sim_time_s >= self.requested_capture_after):
                    from png import write_png
                    sequence = packet['sequence']
                    path = self.workspace/'live/observations'/('overhead-'+str(sequence)+'.png')
                    path.parent.mkdir(parents=True, exist_ok=True)
                    write_png(path, captured.rgb)
                    image_ref = {'path': 'live/observations/'+path.name, 'bytes': path.stat().st_size,
                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'camera': 'overhead',
                        'capture_sim_time_s': captured.capture_sim_time_s, 'observation_sequence': sequence}
                    supervisor.journal.bytes += image_ref['bytes']
                    supervisor.emit('requested_image_available', image_ref)
                    self.explicit_images += 1
                    self.save_requested_image = False
                previous_packet = copy.deepcopy(supervisor.packet)
                previous_observations = dict(supervisor.observations)
                try:
                    supervisor.update_observation(packet)
                except BaseException:
                    # The original synchronous method assigns its in-memory
                    # packet before its durable event. A later shutdown status
                    # must not expose that pending packet after write failure.
                    supervisor.packet = previous_packet
                    supervisor.observations = previous_observations
                    raise
                self.committed_packet = copy.deepcopy(packet)
            elif kind == 'feedback':
                supervisor.native_feedback(payload)
            elif kind == 'event':
                supervisor.native_event(payload)
            else:
                raise RuntimeError('Unknown owner evidence kind: '+str(kind))
        if self.worker.error:
            raise RuntimeError('Physics owner failure: '+str(self.worker.error))

    def outcome(self):
        return self.worker.snapshot['outcome']

    def close(self):
        try:
            self.worker.close()
        finally:
            self.recording.close()
