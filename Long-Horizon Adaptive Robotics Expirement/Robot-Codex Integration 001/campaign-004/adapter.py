"""C workcell on Campaign 002's unchanged continuously paced physics owner."""
import copy
import threading
from common import C02, inherited_paths, load_module
from cell_c import Cell
from controller import ConventionalController
from evaluate_c import CAcceptance
inherited_paths()
prior=load_module('campaign004_inherited_adapter',C02/'harness/continuous_adapter.py')

class CellDriver(prior.CellDriver):
    def __init__(self,owner,manifest,public_id):
        self.owner,self.manifest,self.public_id=owner,manifest,public_id
        self.thread=threading.get_ident();self.cell=Cell(3,manifest['seed'],noise_seed=manifest['noise_seed'])
        self.c_evaluator=CAcceptance()
        try:
            for _ in range(500):self.cell.tick()
            self.initial_sim=self.now;self.cell.prepare_sensor();self.cell.sense()
            self.order=copy.deepcopy(manifest['initial_order']);self.cell._eval_order=None
            self.epoch=1;self.sequence=self.capture=self.ticks=0
            self.feedback_cursor=self.events_cursor=0;self.next_camera=self.now
            self.force_observe=False;self.accepted={};self.skill_started=None
            self.snapshot(initial=True)
        except BaseException:self.cell.close();raise

    def snapshot(self,initial=False):
        self.check_owner()
        if self.order.get('kind')=='C-placement':outcome=self.c_evaluator.update(self.cell.c_truth())
        elif self.order.get('kind')=='AB-transfer':
            outcome={'success':self.cell._physical_zone(self.order['part_id'],self.order['destination']) and not self.cell.active_request and not self.cell._planning_busy()}
        else:outcome=self.cell.outcome(self.order,acceptance_open=True)
        value={'now':self.now,'tcp':self.cell.data.site_xpos[self.cell.tcp].tolist(),
               'joints':self.cell.data.qpos[:7].tolist(),'busy':self.cell.active_request is not None or self.cell._planning_busy(),
               'outcome':outcome}
        if initial:value.update(initial_sim=self.initial_sim,order=copy.deepcopy(self.order),packet=self.packet())
        self.owner.publish_snapshot(value)

    def stage_job(self,order,*,reload_c=False):
        self.check_owner()
        if self.cell.active_request or self.cell._planning_busy() or self.cell.station['busy']:
            raise ValueError('Plant job change requires idle resources')
        if order['version']<=self.order['version']:raise ValueError('Task version must advance')
        if reload_c:
            # A declared external loader event at the job boundary; never a
            # robot route. Arm and all A/B physical state are preserved.
            import mujoco
            joint=self.cell.model.joint('free_C1');q=int(joint.qposadr[0]);v=int(joint.dofadr[0])
            before=self.cell.c_truth()
            self.cell.data.qpos[q:q+7]=[.38,-.24,.021,1,0,0,0];self.cell.data.qvel[v:v+6]=0
            mujoco.mj_forward(self.cell.model,self.cell.data)
            self.owner.publish('event',{'type':'plant_reloaded_C','sim_time':self.now,'order_version':order['version']})
            self.owner.publish('event',{'type':'operator_plant_reload','before':before,'after':self.cell.c_truth(),'order_version':order['version']})
            self.c_evaluator=CAcceptance()
        self.order=copy.deepcopy(order)
        self.cell._eval_order=None
        self.force_observe=True;self.snapshot()
        return {'order_version':self.order['version'],'sim_time_s':self.now}

    def continuation_state(self):
        """Protected state from the physics owner; never a robot route."""
        import numpy as np
        self.check_owner();c=self.cell
        parts=[name for name,tag in c.registry.items() if tag['kind']=='part']
        speeds={name:float(np.linalg.norm(c.data.cvel[c.model.body(name).id,3:])) for name in parts}
        spins={name:float(np.linalg.norm(c.data.cvel[c.model.body(name).id,:3])) for name in parts}
        positions={name:c.actual_pos(name).tolist() for name in parts};packet=self.packet()
        checks={'finite_state':bool(np.isfinite(c.data.qpos).all() and np.isfinite(c.data.qvel).all()),
                'idle_motion':not c.active_request and not c._planning_busy(),
                'idle_station':not c.station['busy'] and not c.station.get('fault'),
                'open_empty_jaws':packet['gripper']['width']>=.065 and not packet['gripper'].get('holding_visible_id'),
                'arm_settled':bool(np.max(np.abs(c.data.qvel[:7]))<.03),
                'parts_settled':all(v<.02 for v in speeds.values()) and all(v<.15 for v in spins.values()),
                'parts_supported':all(-.01<p[2]<.08 and abs(p[0])<.9 and abs(p[1])<.9 for p in positions.values()),
                'no_deep_penetration':all(float(c.data.contact[i].dist)>-.004 for i in range(c.data.ncon)),
                'tool_inside_workspace':bool(c.arm_adapter.workspace_contains(c.data.site_xpos[c.tcp]))}
        return {'safe':all(checks.values()),'checks':checks,'sim_time_s':self.now,
                'qpos':c.data.qpos.tolist(),'qvel':c.data.qvel.tolist(),'positions':positions,
                'speeds_m_s':speeds,'angular_speeds_rad_s':spins,'order_version':self.order['version'],
                'protected_placement':self.c_evaluator.update(c.c_truth()),'c_truth':c.c_truth()}

# Local module binding only; Campaign 002 files and imported code remain exact.
prior.CellDriver=CellDriver

class Adapter(prior.ContinuousAdapter):
    def __init__(self,manifest,evidence,workspace,public_id):
        super().__init__(manifest,evidence,workspace,public_id)
        if 'native_container_cap_bytes' in manifest:
            import recorder
            recorder.MAX_CONTAINER_BYTES=manifest['native_container_cap_bytes']
        if 'native_core_cap_bytes' in manifest:
            # Configuration before the physics owner starts. Keep the exact
            # recorder implementation, format, durability and container guard.
            store=self.recording.store
            with self.recording.lock:
                store.core_limit=manifest['native_core_cap_bytes']
                store.db.execute("UPDATE meta SET value=? WHERE key='core_quota_bytes'",(str(store.core_limit),))
                store.db.commit()
        from pathlib import Path
        self.baseline=ConventionalController('baseline',Path(evidence)/'baseline-workspace',True)

    def stage_job(self,order,*,reload_c=False):
        result=self.worker.rpc('stage_job',order,reload_c=reload_c)
        self.order=copy.deepcopy(order)
        # A queued rendered frame can finish after a job change while still
        # depicting the preceding job. Its capture timestamp must be strictly
        # later than the physical stage boundary before a new decision.
        self.order_capture_boundary=result['sim_time_s']
        if order['kind']=='C-placement':
            from dataclasses import replace
            store=self.recording.store
            with self.recording.lock:
                store.policy=replace(store.policy,image_quota_bytes=store.image_bytes+12_000_000)
            if self.supervisor:self.supervisor.emit('camera_budget_renewed',{'order_version':order['version'],'additional_image_bytes':12_000_000})
        return result

    def begin_activation(self):
        self.explicit_images=0;self.save_requested_image=False;self.requested_capture_after=None
