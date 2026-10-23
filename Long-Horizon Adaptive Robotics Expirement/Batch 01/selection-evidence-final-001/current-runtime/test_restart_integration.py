"""Protected restart forwarding with synthetic physics and worker fixtures only."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import experiment
import sandbox
from test_experiment import Clock, FakeResourceSampler, ImmediateExecutor, fake_cell
from test_restart_state import snapshot


class RestartForwardingTests(unittest.TestCase):
    def test_capture_precedes_cancel_and_unknown_calibration_stays_protected(self):
        clock=Clock();cell=fake_cell();old=MagicMock();fresh=MagicMock()
        for worker in (old,fresh):
            worker.alive=True;worker.ready={};worker.receive.return_value={'type':'step','response':None}
        rich=snapshot();rich['snapshot_sha256']='synthetic-private-restart-digest'
        cut=copy.deepcopy(rich['exposure']);cut['private_diagnostic_marker']='never-in-candidate-input'
        pending=[cut];tracker=MagicMock();tracker.configuration.return_value={'enabled':True}
        tracker.observe.side_effect=lambda *a,**k:pending.pop() if pending else None
        trace=[];physical_hash_ticks={};real_sha=experiment.sha
        physical=('cell.py','actuation.py','evaluator.py','sensor_worker.py')
        def tracked_sha(path):
            if Path(path).name in physical:physical_hash_ticks[Path(path).name]=cell.tick.call_count
            return real_sha(path)
        def capture(actual_cell,**kwargs):
            trace.append('capture');self.assertIs(actual_cell,cell)
            self.assertEqual(cell.cancel.call_count,0)
            self.assertEqual(kwargs['exposure'],cut)
            self.assertIs(kwargs['zones'],experiment.ZONES)
            self.assertIs(kwargs['zone_half'],experiment.zone_half)
            self.assertEqual(kwargs['source_hashes'],{name:real_sha(experiment.HERE/name) for name in physical})
            rich['exposure']=copy.deepcopy(cut);rich['source_hashes']=copy.deepcopy(kwargs['source_hashes'])
            return copy.deepcopy(rich)
        cell.cancel.side_effect=lambda reason:trace.append('cancel')
        executor=ImmediateExecutor(MagicMock(),None)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(experiment,'EVIDENCE',Path(directory)), \
             patch.object(experiment,'ResourceSampler',FakeResourceSampler), \
             patch.object(experiment,'initial_world_report',return_value={'valid':True,'errors':[]}), \
             patch.object(experiment,'Cell',return_value=cell), \
             patch.object(sandbox,'CandidateSandbox',return_value=old), \
             patch.object(experiment,'RestartOpportunity',return_value=tracker), \
             patch.object(experiment,'restart_worker',return_value=fresh), \
             patch.object(experiment,'ThreadPoolExecutor',return_value=executor), \
             patch.object(experiment.time,'perf_counter',side_effect=clock.now), \
             patch.object(experiment,'sha',side_effect=tracked_sha), \
             patch.object(experiment,'capture_restart_state',side_effect=capture) as capture_call, \
             patch.object(experiment,'classify_restart',wraps=experiment.classify_restart) as classify, \
             contextlib.redirect_stdout(io.StringIO()):
            result=experiment.run_episode(run_id='restart-protected-forwarding',cap=.3,scenario='restart')
            path=Path(directory)/'restart-protected-forwarding'
            events=[json.loads(line) for line in (path/'events.jsonl').read_text().splitlines()]
        self.assertIsNone(result['error']);capture_call.assert_called_once()
        self.assertEqual(trace[:2],['capture','cancel'])
        self.assertEqual(physical_hash_ticks,{name:0 for name in physical})
        self.assertIsNone(classify.call_args.kwargs['calibration'])
        begin=next(e for e in events if e['event_type']=='restart_begin');payload=begin['payload']
        self.assertEqual(payload['protected_restart_state'],rich)
        self.assertEqual(payload['protected_snapshot'],rich['geometry'])
        self.assertIsNone(payload['restart_calibration'])
        report=payload['restart_admissibility']
        self.assertEqual(report['state'],'unknown')
        self.assertEqual(next(p for p in report['predicates'] if p['name']=='measured_recovery_route')['state'],'unknown')
        self.assertFalse(any(report['effects'].values()))
        exposure=result['restart_exposure']
        self.assertEqual({k:v for k,v in exposure.items() if k not in ('authority_revocation','absence_observations')},{**cut,'event_id':begin['event_id'],
            'restart_admissibility':report,'protected_restart_state_sha256':rich['snapshot_sha256']})
        ready=next(e for e in events if e['event_type']=='restart_ready')
        self.assertEqual(ready['parent_ids'],[begin['event_id']])
        revoked=next(e for e in events if e['event_type']=='restart_authority_revoked')
        self.assertEqual(revoked['parent_ids'],[begin['event_id']])
        self.assertEqual(exposure['authority_revocation'],revoked['payload'])
        before=revoked['payload']['before_cancel'];after=revoked['payload']['after_cancel']
        self.assertLessEqual(before['wall_s'],after['wall_s'])
        self.assertLessEqual(before['sim_s'],after['sim_s'])
        absence=next(e for e in events if e['event_type']=='restart_absence')
        self.assertEqual(absence['parent_ids'],[begin['event_id']])
        self.assertEqual(absence['payload']['start'],before)
        self.assertEqual(absence['payload']['observed_endpoint'],'restart_ready')
        self.assertEqual(absence['payload']['coverage']['state'],'unknown')
        self.assertEqual(ready['payload']['absence'],absence['payload'])
        self.assertEqual(exposure['absence_observations'],[{**absence['payload'],'event_id':absence['event_id']}])
        self.assertIsNone(payload['restart_qualification_identity'])
        inputs=[e['payload']['message'] for e in events if e['event_type']=='candidate_input']
        self.assertTrue(inputs)
        for forbidden in ('never-in-candidate-input','synthetic-private-restart-digest',
                          'protected_restart_state','restart_admissibility','restart_calibration',
                          'restart_qualification_identity','qualification_context','absence_observations'):
            self.assertNotIn(forbidden,json.dumps(inputs))


if __name__=='__main__':unittest.main()
