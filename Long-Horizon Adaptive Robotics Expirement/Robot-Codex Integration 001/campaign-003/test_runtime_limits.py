"""Prospective envelope boundaries plus the unchanged inherited authority suite."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from common import inherited_paths
inherited_paths()
import test_supervisor as original
from supervisor import GatewayError,canonical
from supervisor_c import Supervisor
from journal_c import Journal,DiskEvents
from runtime_limits import apply_limits,validate_limits,encounter_stop


class InheritedAuthorityTests(original.SupervisorChecks):
    def setUp(self):
        with patch.object(original,'Supervisor',Supervisor),patch.object(original,'Journal',Journal):
            super().setUp()


    # Inherited checks run with the original 20-action default. These two
    # fixtures explicitly exercise the approved new count without a plant.
    def test_approved_120_boundary_and_duplicate(self):
        self.adapter.manifest={'robot_action_limit':120}
        self.host.robot_action_count=119
        body=self.body('last-allowed')
        self.assertEqual(self.host.command(body)['command']['status'],'accepted')
        self.assertEqual(self.host.status()['robot_action_budget'],{'used':120,'limit':120})
        self.assertTrue(self.host.command(body)['duplicate'])
        self.assertEqual(len(self.adapter.submissions),1)
        self.host.native_feedback({'request_id':'last-allowed','status':'completed'})
        self.adapter.active=False;self.adapter.now=1.2
        self.host.update_observation(original.packet(sequence=2,sim=1.2))
        self.assertEqual(self.host.command(self.body('over-budget'))['command']['error']['code'],'action_budget')
        self.assertEqual(len(self.adapter.submissions),1)

    def test_indexed_history_matches_original_query(self):
        saved=[json.loads(line) for line in self.journal.events_path.read_bytes().splitlines()]
        for after in (0,1,len(saved),len(saved)+9):
            for limit in (1,2,200):
                got=self.host.request('GET',f'/history?after={after}&limit={limit}')
                self.assertEqual(got['events'],[e for e in saved if e['event_id']>after][:limit])
                self.assertEqual(got['high_water'],len(saved))


class EnvelopeTests(unittest.TestCase):
    def test_exact_frozen_manifest_and_non_time_bounds(self):
        m=apply_limits({'stage':'live_qualification'},'live_qualification')
        validate_limits(m)
        self.assertEqual((m['model_timeout_s'],m['encounter_sim_cap_s'],m['encounter_wall_cap_s']),(3600,4200,4500))
        for key in ('model_timeout_s','encounter_sim_cap_s','encounter_wall_cap_s','robot_action_limit','native_core_cap_bytes','storage_cap_bytes','sim_cap_s','wall_cap_s'):
            with self.subTest(key=key):
                changed=dict(m);changed[key]+=1
                with self.assertRaises(ValueError):validate_limits(changed)

    def test_independent_encounter_clocks(self):
        m=apply_limits({},'pilot');inv={'state':'active','started_sim_time_s':12}
        self.assertIsNone(encounter_stop(m,inv,4211.9,4599.9,100))
        self.assertEqual(encounter_stop(m,inv,4212,4599.9,100),'encounter_simulation_cap')
        self.assertEqual(encounter_stop(m,inv,15,4600,100),'encounter_wall_cap')
        self.assertIsNone(encounter_stop(m,{'state':'retired'},99999,99999,100))

    def test_disk_history_exact_slices_and_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'history.jsonl';index=DiskEvents(path);expected=[]
            with path.open('wb') as stream:
                for i in range(1,513):
                    row={'event_id':i,'type':'synthetic','payload':{'unicode':'Caf\u00e9','value':i,'vector':[1,2,3]}}
                    stream.write(canonical(row)+b'\n');stream.flush();index.append(row);expected.append(row)
            self.assertEqual(index[:],expected)
            self.assertEqual(index[-1],expected[-1])
            self.assertEqual(index[300:510],expected[300:510])
            with path.open('r+b') as stream:stream.seek(0);stream.write(b'X')
            with self.assertRaises(GatewayError):index[0]


if __name__=='__main__':unittest.main()
