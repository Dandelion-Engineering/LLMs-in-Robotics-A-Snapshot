"""C workcell on Campaign 002's unchanged continuously paced physics owner."""
import copy
import threading
from common import C02, inherited_paths, load_module
from cell_c import Cell
from controller import ConventionalController
from evaluate_c import CAcceptance
inherited_paths()
prior=load_module('campaign003_inherited_adapter',C02/'harness/continuous_adapter.py')

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

# Local module binding only; Campaign 002 files and imported code remain exact.
prior.CellDriver=CellDriver

class Adapter(prior.ContinuousAdapter):
    def __init__(self,manifest,evidence,workspace,public_id):
        super().__init__(manifest,evidence,workspace,public_id)
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
        if order['kind']=='C-placement':
            from dataclasses import replace
            store=self.recording.store
            with self.recording.lock:
                store.policy=replace(store.policy,image_quota_bytes=store.image_bytes+12_000_000)
            if self.supervisor:self.supervisor.emit('camera_budget_renewed',{'order_version':order['version'],'additional_image_bytes':12_000_000})
        return result

    def begin_activation(self):
        self.explicit_images=0;self.save_requested_image=False;self.requested_capture_after=None
