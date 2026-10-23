"""Deferred synthetic checks: fixed plan, first public cut and A-only loading.

No physics, queue calls, actual evidence reads or task runs. Run only when root
releases the active physical-work hold and submits the bounded test command.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
TOOLS = PROJECT / 'Batch 01/Restart Qualification Tools'  # Read-only synthetic fixture source; actual loader below is Runtime 004.
sys.path.insert(0, str(HERE))
from profile_fixture import (BASELINE, HIGH, declared_plan, profile_rule_identity,
                             public_cut_matches, transport_action, validate_plan)
import run_profile_screen as driver


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ProfileTests(unittest.TestCase):
    def test_exact_plan_and_bound_execution_file(self):
        raw = (HERE / 'plan-001.json').read_bytes()
        self.assertEqual(validate_plan(json.loads(raw)), declared_plan())
        execution = json.loads((HERE / 'execution-plan-001.json').read_text())
        self.assertEqual(execution['original_plan_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(len(declared_plan()['trials']), 13)

    def test_only_high_profile_can_contribute_construction(self):
        construction, deferred, _ = driver.execution_selection(declared_plan(), 'parking1', 'construction')
        self.assertEqual(len(construction), 7)
        self.assertEqual(len(deferred), 6)
        self.assertEqual({r['transport_profile'] for r in construction}, {'high'})
        self.assertEqual({r['evidence_role'] for r in construction}, {'cell_construction'})
        self.assertEqual({r['family'] for r in declared_plan()['trials']}, {'A'})
        self.assertEqual({r['expected_payload_id'] for r in declared_plan()['trials']}, {'A1'})

    def test_validation_has_three_shared_fresh_worlds_and_two_fixed_profiles(self):
        trials, deferred, _ = driver.execution_selection(declared_plan(), 'parking1', 'validation')
        self.assertEqual(len(trials), 6)
        self.assertEqual(len(deferred), 7)
        self.assertEqual({r['world_seed'] for r in trials}, {931301, 931302, 931303})
        for n, seed in ((3, 931301), (6, 931302), (10, 931303)):
            pair = [r for r in trials if r['population'] == n]
            self.assertEqual([r['world_seed'] for r in pair], [seed, seed])
            self.assertEqual([r['evidence_role'] for r in pair], ['core_validation', 'baseline_transfer_check'])
            self.assertEqual([r['transport_objective'] for r in pair], [HIGH, BASELINE])
            self.assertTrue(all(r['main_geom_mass_kg'] is None and r['main_geom_sliding_friction'] is None for r in pair))

    def test_plan_mutations_reject_instead_of_silent_sweep(self):
        for change in ('seed', 'destination', 'profile', 'family', 'drop', 'cadence'):
            plan = declared_plan()
            if change == 'seed': plan['trials'][7]['world_seed'] += 1
            if change == 'destination': plan['trials'][0]['transport_destination'] = 'inspection'
            if change == 'profile': plan['trials'][0]['transport_objective']['clearance'] = .08
            if change == 'family': plan['trials'][0]['family'] = 'B'
            if change == 'drop': plan['trials'].pop()
            if change == 'cadence': plan['cut']['basis'] = 'wait until admissible'
            with self.subTest(change=change), self.assertRaises(ValueError): validate_plan(plan)

    def test_selected_execution_matches_existing_extractor_phase_contract(self):
        plan = declared_plan()
        for phase, fixture in (('construction', 'construction'), ('validation', 'independent_generator')):
            trials, deferred, metadata = driver.execution_selection(plan, 'parking1', phase)
            expected = [r['id'] for r in plan['trials'] if r['destination'] == 'parking1' and r['fixture'] == fixture]
            manifest = {'destination_selection': 'parking1', 'execution_phase': phase,
                'modes': [r['id'] for r in trials], 'phase_deferred_trial_ids': deferred, **metadata}
            self.assertEqual(manifest['modes'], expected)
            driver.manifest_execution(plan, manifest)
            manifest['modes'] = manifest['modes'][:-1]
            with self.assertRaises(ValueError): driver.manifest_execution(plan, manifest)

    def test_no_single_validation_diagnostic_can_cherry_pick(self):
        plan = declared_plan()
        with self.assertRaises(ValueError):
            driver.execution_selection(plan, 'parking1', 'validation', plan['trials'][7]['id'])
        trials, _, metadata = driver.execution_selection(plan, 'parking1', 'construction', plan['trials'][0]['id'])
        self.assertEqual(len(trials), 1)
        self.assertFalse(metadata['qualification_evidence_eligible'])
        self.assertFalse(metadata['is_full_phase_screen'])

    def test_actual_actions_keep_destination_and_defensive_objective(self):
        trials = declared_plan()['trials']
        for trial in (trials[0], trials[8]):
            action = transport_action(trial, 'A1')
            self.assertEqual(action['destination'], 'fixture')
            self.assertEqual(action['objective'], trial['transport_objective'])
            action['objective']['avoid_zones'].append('raw')
            self.assertEqual(trial['transport_objective']['avoid_zones'], [])

    def test_public_predicate_matches_actual_runtime_on_valid_samples(self):
        runtime = load_module('_profile_runtime_opportunity', PROJECT/'Runtime 004'/'initial_conditions.py')
        samples = ((3, .04, .09), (4, .065, .09), (4, .04, .079), (4, .04, .08), (5, .04, .09))
        for phase, width, height in samples:
            tracker = runtime.RestartOpportunity(0)
            tracker._config.update(cut='closed_grip_transfer', transport_ordinal=1)
            request = {'request_id': 'synthetic-transport', 'operation': 'transport'}
            segment = {'phase': phase}
            observed = tracker.observe(1., request, segment, width=width, tcp_z=height)
            self.assertEqual(public_cut_matches(request, segment, request['request_id'], width=width, tcp_z=height),
                             observed is not None)
        self.assertFalse(public_cut_matches(request, {'phase': 4}, 'different', width=.04, tcp_z=.09))
        self.assertFalse(public_cut_matches(request, {'phase': 4}, request['request_id'], width=.04, tcp_z=float('nan')))

    def test_first_public_match_is_captured_even_when_protected_grip_fails(self):
        class CutRecorded(Exception): pass
        class Records:
            def __init__(self): self.cut = None
            def event(self, kind, payload, sim):
                if kind == 'protected_carry_state_before_cut':
                    self.cut = (payload, sim)
                    raise CutRecorded()
                return 1
        class Matrix:
            def __init__(self, cell): self.cell = cell
            def __getitem__(self, key): return self.cell.height
        records = Records()
        cell = types.SimpleNamespace(last_detections=[{'id':'A1','kind':'part','family':'A','visible_mark':'raw','zone':'raw'}],
            detection_time=0., tcp=0, height=.07, active_request=None, segment={'phase':3})
        cell.data = types.SimpleNamespace(time=0., qpos=[0.]*7+[.02,.02], site_xpos=Matrix(cell))
        class Loop:
            cells=[cell]; latest=[types.SimpleNamespace(sequence=1)]; zones={}; zone_half={}; physical_source_hashes={}
            def __init__(self): self.records=records; self.samples=0
            def public_ready(self): return True
            def submit(self, action):
                self.action=action
                cell.active_request={'request_id':'synthetic-transport', **action}
                return 'synthetic-transport'
            def snapshot(self):
                return {'objects':[{'id':'A1','gripper_contact':False,'position':[0.,0.,.02]}]}
            def until(self, predicate, timeout):
                if getattr(predicate, '__name__', '') == 'public_ready': return
                for phase, height in ((3,.09),(4,.079),(4,.08),(4,.10)):
                    self.samples+=1; cell.segment={'phase':phase}; cell.height=height; cell.data.time+=.002
                    if predicate(): return
                raise AssertionError('Public cut was improperly delayed')
        loop=Loop()
        fake_geometry=types.ModuleType('geometry_trace')
        fake_geometry.GeometryTrace=lambda *a: types.SimpleNamespace(sample=lambda **kw: None)
        fake_restart=types.ModuleType('restart_state')
        fake_restart.capture_restart_state=lambda *a, **kw: {'contacts':{'by_object':{'A1':{'bilateral_force_bearing':False}}}, 'captured_height':cell.height}
        fake_restart.classify_restart=lambda *a, **kw: (_ for _ in ()).throw(AssertionError('Stop before classification'))
        with patch.dict(sys.modules, {'geometry_trace':fake_geometry,'restart_state':fake_restart}), \
             patch.object(driver, 'boundary_operation', side_effect=lambda _l,_d,_name,fn,*a,**kw: fn(*a,**kw)):
            with self.assertRaises(CutRecorded):
                driver.trial_body(loop, declared_plan()['trials'][0], declared_plan(), {'boundary_operation_timings':[]})
        self.assertEqual(loop.samples, 3)
        self.assertEqual(records.cut[0]['captured_height'], .08)
        self.assertFalse(records.cut[0]['contacts']['by_object']['A1']['bilateral_force_bearing'])
        self.assertEqual(loop.action['objective'], HIGH)

    def test_profile_launch_rejects_B_or_extra_cells(self):
        rule = {'payload_template_to_cell':{'part:A':'core-A'}, 'cells':[{'cell_id':'core-A',
            'grip_envelope':{'kind':'part','family':'A'},
            'route_envelope':{'payload_kind':'part','payload_family':'A','destination':'parking1'}}]}
        profile_rule_identity(rule)
        for change in ('B', 'extra', 'destination', 'identity'):
            bad=copy.deepcopy(rule)
            if change=='B': bad['payload_template_to_cell']['part:B']='core-A'
            if change=='extra': bad['cells'].append(copy.deepcopy(bad['cells'][0]))
            if change=='destination': bad['cells'][0]['route_envelope']['destination']='parking2'
            if change=='identity': bad['cells'][0]['cell_id']='other'
            with self.subTest(change=change), self.assertRaises(ValueError): profile_rule_identity(bad)

    def test_existing_runtime_loader_accepts_A_only_and_returns_B_unknown(self):
        sys.path.insert(0, str(TOOLS))
        try:
            fixtures=load_module('_profile_loader_test_fixtures', TOOLS/'test_calibration_loader.py')
            sys.path.insert(0, str(PROJECT/'Runtime 004'))
            runtime=load_module('_profile_actual_loader', PROJECT/'Runtime 004'/'restart_calibration_loader.py')
            with tempfile.TemporaryDirectory(dir=HERE) as directory:
                freeze, path, _, bundle_path=fixtures.write_fixture(Path(directory))
                bundle=json.loads(bundle_path.read_text())
                bundle['cells']=[c for c in bundle['cells'] if c['grip_envelope']['family']=='A']
                bundle_path.write_text(json.dumps(bundle), encoding='utf-8')
                ref=freeze['restart_qualification']; ref['payload_template_to_cell'].pop('part:B')
                ref['sha256']=hashlib.sha256(bundle_path.read_bytes()).hexdigest()
                ref['bundle_sha256']=fixtures.digest(bundle)
                path.write_text(json.dumps(freeze), encoding='utf-8')
                protected=runtime.load_restart_qualification(freeze,path).as_dict()
                self.assertEqual(set(protected['calibration_by_template']), {'part:A'})
                for family, expected in (('A','pass'),('B','unknown')):
                    _, snapshot, _=fixtures.fixture()
                    identity=next(o['id'] for o in snapshot['geometry']['objects'] if o['kind']=='part' and o['family']==family)
                    snapshot['contacts']={'by_object':{o['id']:{'hand_contact':o['id']==identity,
                        'bilateral_force_bearing':o['id']==identity} for o in snapshot['geometry']['objects']}}
                    selected=runtime.select_restart_calibration(protected,snapshot)
                    self.assertEqual(selected['state'],expected,selected)
                    if family=='B': self.assertIsNone(selected['calibration'])
        finally:
            for value in (str(TOOLS),str(PROJECT/'Runtime 004')):
                if value in sys.path: sys.path.remove(value)

    def test_archive_inventory_contains_original_consumed_helpers(self):
        paths=set(driver.sources())
        for relative in ('Batch 01/Release Lifecycle Repair 001/qualification-tools/Recovery Qualification/fixture.py',
                         'Batch 01/Release Lifecycle Repair 001/qualification-tools/Recovery Qualification/extract_screen.py',
                         'Batch 01/Release Lifecycle Repair 001/qualification-tools/Recovery Qualification/measurement.py',
                         'Batch 01/Release Lifecycle Repair 001/qualification-tools/Recovery Profile Qualification/profile_fixture.py',
                         'Batch 01/Release Lifecycle Repair 001/qualification-tools/Recovery Profile Qualification/run_profile_screen.py'):
            self.assertIn((PROJECT/relative).resolve(),paths)


if __name__ == '__main__': unittest.main()
