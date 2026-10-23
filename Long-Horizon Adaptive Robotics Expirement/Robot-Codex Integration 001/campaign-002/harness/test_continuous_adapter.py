"""Bounded fake-driver tests of owner fencing and synchronous publication ordering."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
from contextlib import nullcontext
from types import SimpleNamespace
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'host'))
from continuous_adapter import CellDriver, ContinuousAdapter
from instrumented_journal import InstrumentedJournal
from supervisor import Supervisor


class Values(list):
    def __getitem__(self,index):
        value=super().__getitem__(index)
        return Values(value) if isinstance(index,slice) else value
    def tolist(self): return list(self)


class FakeCell:
    def __init__(self,log):
        self.log=log; self.active_request=None; self.feedback=[]; self.events=[]
        self.data=SimpleNamespace(time=1.,site_xpos=[Values([.1,.2,.3])],qpos=Values([0.]*9),
            qvel=Values([0.]*7),actuator_force=Values([0.]*7),ctrl=Values([0.]*7))
        self.tcp=0; self.sensor_worker=SimpleNamespace(busy=False); self.capture=None
    def _planning_busy(self): return False
    def outcome(self,order,acceptance_open): return {'success':False}
    def submit(self,action):
        self.log.append(('native_submit',copy.deepcopy(action)))
        self.active_request=action['request_id']
        return {'status':'accepted','request_id':action['request_id']}
    def cancel(self,reason):
        self.log.append(('native_cancel',reason)); self.active_request=None
    def public_packet(self,order,public_id,epoch,sequence):
        return {'sequence':sequence,'capture_sim_time_s':self.data.time,'order':copy.deepcopy(order),
                'incarnation':epoch,'detections':[{'id':'captured-only'}]}
    def public_arm_interfaces(self): return {'ready':True}
    def renew_authority(self,*args): self.log.append(('renew',args))
    def tick(self): self.data.time+=.002
    def poll_sense(self): return self.capture
    def resume_setup_if_fresh(self): self.log.append(('resume',None))
    def request_sense(self,**kwargs): self.log.append(('sense_requested',kwargs))
    def close(self): self.log.append(('cell_closed',None))


class FakeOwner:
    def __init__(self,log):
        self.log=log; self.snapshot={}; self._capture=SimpleNamespace(origin=0.)
    def publish_snapshot(self,value): self.snapshot=copy.deepcopy(value)
    def publish(self,kind,payload): self.log.append(('published_'+kind,copy.deepcopy(payload)))


def driver_fixture(log):
    driver=CellDriver.__new__(CellDriver)
    driver.thread=threading.get_ident(); driver.owner=FakeOwner(log); driver.cell=FakeCell(log)
    driver.order={'version':1}; driver.public_id='unit'; driver.epoch=1
    driver.sequence=driver.capture=driver.ticks=0
    driver.feedback_cursor=driver.events_cursor=0; driver.next_camera=100.
    driver.force_observe=False; driver.accepted={}; driver.skill_started=None; driver.initial_sim=1.
    driver.snapshot(initial=True)
    return driver


class FakeWorker:
    def __init__(self,driver,log):
        self.driver=driver; self.log=log; self.terminal=None; self.error=None; self.messages=[]
    @property
    def now(self): return self.driver.now
    @property
    def snapshot(self): return copy.deepcopy(self.driver.owner.snapshot)
    def heartbeat(self): self.log.append(('heartbeat',None))
    def rpc(self,name,*args):
        self.log.append(('rpc_'+name,copy.deepcopy(args)))
        return getattr(self.driver,name)(*args)
    def drain(self):
        messages,self.messages=self.messages,[]
        return messages
    def close(self): self.log.append(('worker_close',None))


def adapter_fixture(log,root):
    driver=driver_fixture(log); adapter=ContinuousAdapter.__new__(ContinuousAdapter)
    adapter.worker=FakeWorker(driver,log); adapter.workspace=Path(root)
    adapter.committed_packet=copy.deepcopy(driver.owner.snapshot['packet'])
    adapter.timing_capture=None; adapter.supervisor=None; adapter.save_requested_image=False; adapter.explicit_images=0
    adapter.last_epoch=1; adapter.requested_capture_after=None
    adapter.recording=SimpleNamespace(motion=SimpleNamespace(write=lambda text:log.append(('motion',json.loads(text)))),
        close=lambda:log.append(('recording_close',None)))
    adapter.bridge=SimpleNamespace(observe=lambda captured:log.append(('image',captured)))
    return adapter,driver


def command_fixture(root,log):
    adapter,driver=adapter_fixture(log,root)
    journal=InstrumentedJournal(Path(root)/'protected',Path(root)/'public','unit')
    baseline=SimpleNamespace(accept_feedback=lambda value:log.append(('baseline_feedback',copy.deepcopy(value))))
    supervisor=Supervisor(adapter,baseline,journal); adapter.supervisor=supervisor
    supervisor.packet=copy.deepcopy(adapter.committed_packet)
    supervisor.observations={0:1.}
    envelope=supervisor.envelope('unit-command',{'operation':'wait'})
    return adapter,driver,supervisor,envelope


def request():
    action={'request_id':'unit-command','incarnation':1,'order_version':1,'operation':'wait'}
    receipt={'durable_intent':True,'fingerprint':'f'*64,'request_id':'unit-command',
        'epoch':1,'order_version':1,'capture_sim_time_s':1.,'requested_sim_time_s':1.}
    return action,receipt


class ContinuousAdapterTests(unittest.TestCase):
    def test_actual_supervisor_durable_event_and_registry_precede_rpc(self):
        log=[]
        with tempfile.TemporaryDirectory() as directory:
            adapter,driver,supervisor,envelope=command_fixture(directory,log)
            def fsync(fd): log.append(('fsync',None))
            with mock.patch('os.fsync',side_effect=fsync): result=supervisor.command(envelope,actor='conventional')
            rpc_index=next(i for i,row in enumerate(log) if row[0]=='rpc_submit')
            self.assertEqual(sum(row[0]=='fsync' for row in log[:rpc_index]),6)
            public=[json.loads(x) for x in supervisor.journal.mirror_path.read_text().splitlines()]
            self.assertEqual([row['type'] for row in public[:2]],['command_requested','command_dispatched'])
            self.assertEqual(result['command']['admission']['status'],'accepted')
            receipt=log[rpc_index][1][1]
            self.assertTrue(receipt['durable_intent']); self.assertEqual(receipt['capture_sim_time_s'],1.)
            self.assertEqual(sum(row[0]=='native_submit' for row in log),1)

    def test_each_protected_public_registry_fsync_failure_prevents_all_rpc(self):
        # Requested event pair, requested registry, dispatched event pair,
        # dispatched registry: all six synchronous calls precede owner submission.
        for failed_call in range(1,7):
            with self.subTest(failed_call=failed_call),tempfile.TemporaryDirectory() as directory:
                log=[]; adapter,driver,supervisor,envelope=command_fixture(directory,log)
                calls=[0]
                def fsync(fd):
                    calls[0]+=1
                    if calls[0]==failed_call: raise OSError('injected durable intent failure')
                with mock.patch('os.fsync',side_effect=fsync):
                    with self.assertRaisesRegex(OSError,'durable intent'): supervisor.command(envelope,actor='conventional')
                self.assertFalse(any(row[0].startswith('rpc_') for row in log))
                self.assertFalse(any(row[0]=='native_submit' for row in log))

    def test_original_observation_expires_during_dispatched_registry_sync(self):
        log=[]
        with tempfile.TemporaryDirectory() as directory:
            adapter,driver,supervisor,envelope=command_fixture(directory,log)
            calls=[0]
            def fsync(fd):
                calls[0]+=1
                if calls[0]==6: driver.cell.data.time=1.351
            with mock.patch('os.fsync',side_effect=fsync): result=supervisor.command(envelope,actor='conventional')
            self.assertEqual(result['command']['admission']['status'],'rejected')
            self.assertIn('observation expired',result['command']['admission']['reason'])
            self.assertFalse(any(row[0]=='native_submit' for row in log))
            receipt=next(row[1][1] for row in log if row[0]=='rpc_submit')
            self.assertEqual(receipt['capture_sim_time_s'],1.)

    def test_native_admission_rechecks_epoch_order_identity_and_durability(self):
        variants=[('action_epoch',lambda a,r:a.update(incarnation=2)),
            ('receipt_epoch',lambda a,r:r.update(epoch=2)),('action_order',lambda a,r:a.update(order_version=2)),
            ('receipt_order',lambda a,r:r.update(order_version=2)),('intent',lambda a,r:r.update(durable_intent=False)),
            ('identity',lambda a,r:r.update(request_id='different')),('future_capture',lambda a,r:r.update(capture_sim_time_s=2.))]
        for label,change in variants:
            with self.subTest(label=label):
                log=[]; driver=driver_fixture(log); action,receipt=request(); change(action,receipt)
                result=driver.submit(action,receipt)
                self.assertEqual(result['status'],'rejected')
                self.assertFalse(any(row[0]=='native_submit' for row in log))

    def test_duplicate_identity_never_replays_and_conflict_propagates(self):
        log=[]; driver=driver_fixture(log); action,receipt=request()
        first=driver.submit(action,receipt); first['status']='caller-mutated'
        duplicate=driver.submit(action,receipt)
        self.assertEqual(duplicate['status'],'accepted')
        self.assertEqual(sum(row[0]=='native_submit' for row in log),1)
        with self.assertRaisesRegex(RuntimeError,'identity conflict'): driver.submit(action,dict(receipt,fingerprint='a'*64))

    def test_worker_new_snapshot_never_replaces_committed_packet(self):
        log=[]; adapter,driver=adapter_fixture(log,'.')
        driver.owner.snapshot['packet']={'sequence':999,'detections':[{'id':'uncommitted'}]}
        returned=adapter.packet(2)
        self.assertEqual(returned['sequence'],0); self.assertEqual(returned['incarnation'],2)
        returned['detections'][0]['id']='caller-mutated'
        self.assertEqual(adapter.packet(2)['detections'][0]['id'],'captured-only')

    def test_ordered_motion_image_observation_feedback_and_events(self):
        log=[]; adapter,driver=adapter_fixture(log,'.')
        packet=dict(adapter.committed_packet,sequence=1,capture_sim_time_s=1.1)
        captured=SimpleNamespace(capture_sim_time_s=1.1)
        adapter.worker.messages=[{'kind':'motion','payload':{'sim_time_s':1.01}},
            {'kind':'capture','payload':{'captured':captured,'packet':packet}},
            {'kind':'feedback','payload':{'status':'completed'}},{'kind':'event','payload':{'type':'cycle_complete'}},
            {'kind':'motion','payload':{'sim_time_s':1.02}}]
        def observation(value):
            self.assertEqual(adapter.packet(1)['sequence'],0)
            log.append(('observation',copy.deepcopy(value)))
        supervisor=SimpleNamespace(epoch=1,packet=copy.deepcopy(adapter.committed_packet),observations={0:1.},update_observation=observation,
            native_feedback=lambda value:log.append(('feedback',value)),native_event=lambda value:log.append(('event',value)))
        adapter.step(supervisor,0.)
        retained=[row[0] for row in log if row[0] in ('motion','image','observation','feedback','event')]
        self.assertEqual(retained,['motion','image','observation','feedback','event','motion'])
        self.assertEqual(adapter.packet(1)['sequence'],1)
        packet['sequence']=999
        self.assertEqual(adapter.packet(1)['sequence'],1)

    def test_recorder_failure_prevents_observation_and_remaining_publication(self):
        log=[]; adapter,driver=adapter_fixture(log,'.')
        adapter.bridge.observe=mock.Mock(side_effect=OSError('injected SQLite commit failure'))
        adapter.worker.messages=[{'kind':'capture','payload':{'captured':object(),'packet':{'sequence':1}}},
            {'kind':'feedback','payload':{'status':'completed'}}]
        supervisor=SimpleNamespace(epoch=1,update_observation=mock.Mock(),native_feedback=mock.Mock())
        with self.assertRaisesRegex(OSError,'SQLite commit'): adapter.step(supervisor,0.)
        supervisor.update_observation.assert_not_called(); supervisor.native_feedback.assert_not_called()
        self.assertEqual(adapter.packet(1)['sequence'],0)

    def test_failed_observation_sync_keeps_last_committed_public_snapshot(self):
        log=[]
        with tempfile.TemporaryDirectory() as directory:
            adapter,driver,supervisor,envelope=command_fixture(directory,log)
            before=copy.deepcopy(supervisor.packet); before_observations=dict(supervisor.observations)
            packet=dict(before,sequence=1,capture_sim_time_s=1.1)
            adapter.worker.messages=[{'kind':'capture','payload':{'captured':object(),'packet':packet}}]
            with mock.patch('os.fsync',side_effect=OSError('injected observation fsync')):
                with self.assertRaisesRegex(OSError,'observation fsync'): adapter.step(supervisor,0.)
            self.assertEqual(adapter.packet(1),before)
            # The host failure handler may publish Supervisor.status; its camera
            # fields must also remain committed when the durable event failed.
            self.assertEqual(supervisor.packet,before)
            self.assertEqual(supervisor.observations,before_observations)

    def test_unknown_evidence_and_owner_failure_propagate(self):
        for kind in ('unknown',None):
            with self.subTest(kind=kind):
                log=[]; adapter,driver=adapter_fixture(log,'.')
                if kind: adapter.worker.messages=[{'kind':kind,'payload':{}}]
                else: adapter.worker.error={'type':'InjectedOwnerFailure','message':'lost owner'}
                with self.assertRaises(RuntimeError): adapter.step(SimpleNamespace(epoch=1),0.,final=True)

    def test_cell_driver_collects_native_records_in_original_tick_order(self):
        log=[]; driver=driver_fixture(log); driver.ticks=4
        driver.cell.capture=SimpleNamespace(sequence=9,rgb=b'native')
        driver.cell.feedback=[{'status':'completed','request_id':'old'}]
        driver.cell.events=[{'type':'cycle_complete'}]
        driver.tick()
        published=[row[0] for row in log if row[0].startswith('published_')]
        self.assertEqual(published,['published_motion','published_capture','published_feedback','published_event'])
        driver.cell.capture=None; driver.tick()
        self.assertEqual(sum(row[0]=='published_feedback' for row in log),1)
        self.assertEqual(sum(row[0]=='published_event' for row in log),1)

    def test_native_driver_failure_and_sole_owner_violation_propagate(self):
        log=[]; driver=driver_fixture(log); action,receipt=request()
        driver.cell.submit=mock.Mock(side_effect=RuntimeError('injected native failure'))
        with self.assertRaisesRegex(RuntimeError,'native failure'): driver.submit(action,receipt)
        self.assertNotIn('unit-command',driver.accepted)
        driver.thread=-1
        with self.assertRaisesRegex(RuntimeError,'sole owner'): driver.submit(action,receipt)

    def test_final_drain_retains_evidence_without_new_rpc(self):
        log=[]; adapter,driver=adapter_fixture(log,'.'); adapter.worker.terminal='operator_stop'
        adapter.worker.messages=[{'kind':'motion','payload':{'sim_time_s':1.02}},
            {'kind':'feedback','payload':{'status':'cancelled'}}]
        supervisor=SimpleNamespace(epoch=2,native_feedback=lambda row:log.append(('feedback',row)))
        adapter.step(supervisor,0.,final=True)
        self.assertEqual([row[0] for row in log],['motion','feedback'])
        self.assertEqual(adapter.worker.messages,[])

    def test_recorder_close_still_attempted_after_worker_close_error(self):
        log=[]; adapter,driver=adapter_fixture(log,'.')
        adapter.worker.close=mock.Mock(side_effect=RuntimeError('unknown owner shutdown'))
        with self.assertRaisesRegex(RuntimeError,'unknown owner'): adapter.close()
        self.assertEqual(log,[('recording_close',None)])

    def test_independent_skill_deadline_and_authority_change_cancel_locally(self):
        log=[]; driver=driver_fixture(log)
        driver.cell.active_request='old'; driver.skill_started=-90.
        driver.tick()
        self.assertEqual(log[0],('native_cancel','maximum independent skill interval reached'))
        driver.cell.active_request='old'; driver.set_authority(2)
        self.assertEqual(driver.epoch,2)
        self.assertEqual(log[-1],('native_cancel','authority generation changed'))
        with self.assertRaisesRegex(RuntimeError,'regressed'): driver.set_authority(1)

    def test_real_journal_and_full_sqlite_stalls_preserve_durability_while_ticks_continue(self):
        from physics_worker import ContinuousPhysics
        from test_physics_worker import Capture
        sys.path.insert(0,str(HERE.parents[2]/'Storage Retention Implementation 001/future'))
        from instrumented_recorder import InstrumentedFutureEvidence
        log=[]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); adapter,_,supervisor,envelope=command_fixture(root,log)
            def factory(owner):
                driver=driver_fixture(log)
                driver.owner=owner; driver.snapshot(initial=True)
                return driver
            worker=ContinuousPhysics(factory,sim_cap_s=2.,wall_cap_s=3.)
            adapter.worker=worker
            evidence=InstrumentedFutureEvidence(root/'sqlite-recording','unit',phase=lambda name:nullcontext())
            reader=sqlite3.connect(evidence.path/'evidence.sqlite')
            stalls=[]; fsync_count=[0]; native_fsync=os.fsync
            try:
                self.assertEqual(evidence.store.db.execute('PRAGMA synchronous').fetchone()[0],2)
                worker.start(Capture())
                def stalled_fsync(fd):
                    fsync_count[0]+=1; before=worker.now
                    visible_events=len(supervisor.journal.events)
                    if fsync_count[0]<=6:
                        self.assertFalse(any(row[0]=='native_submit' for row in log))
                    time.sleep(.03)
                    self.assertGreater(worker.now,before,'Physics stopped during actual journal fsync call')
                    self.assertEqual(len(supervisor.journal.events),visible_events,'Event acknowledged before fsync returned')
                    if fsync_count[0]<=6:
                        self.assertFalse(any(row[0]=='native_submit' for row in log),'Native dispatch preceded durable intent')
                    native_fsync(fd); stalls.append(('fsync',before,worker.now))
                with mock.patch('os.fsync',side_effect=stalled_fsync):
                    response=supervisor.command(envelope,actor='conventional')
                self.assertEqual(response['command']['admission']['status'],'accepted')
                self.assertEqual(fsync_count[0],9)
                native_commit=type(evidence.store.db).commit
                returned=[False]
                def stalled_commit(connection,*args,**kwargs):
                    before=worker.now
                    self.assertFalse(returned[0]); self.assertIsNone(evidence.store.last_durable_event)
                    self.assertEqual(reader.execute('SELECT count(*) FROM events').fetchone()[0],0)
                    time.sleep(.03)
                    self.assertGreater(worker.now,before,'Physics stopped during actual SQLite commit call')
                    self.assertFalse(returned[0]); self.assertIsNone(evidence.store.last_durable_event)
                    self.assertEqual(reader.execute('SELECT count(*) FROM events').fetchone()[0],0,
                        'Uncommitted evidence visible to another connection')
                    result=native_commit(connection,*args,**kwargs)
                    stalls.append(('sqlite_commit',before,worker.now))
                    return result
                with mock.patch.object(type(evidence.store.db),'commit',new=stalled_commit):
                    ident=evidence.emit('diagnostic',{'durable':True},worker.now)
                    returned[0]=True
                self.assertEqual(ident,1); self.assertEqual(evidence.store.last_durable_event,1)
                self.assertEqual(reader.execute('SELECT count(*) FROM events').fetchone()[0],1)
                self.assertEqual([row[0] for row in stalls],['fsync']*9+['sqlite_commit'])
                self.assertIsNone(worker.error)
            finally:
                worker.stop('bounded_durability_test_complete')
                reader.close(); evidence.close()


if __name__=='__main__': unittest.main()
