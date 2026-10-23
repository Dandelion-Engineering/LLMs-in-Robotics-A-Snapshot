"""UNAPPLIED assessor correction, exercised only in memory with synthetic data.

The active geometry job imports assess_validation.py. This file never writes
that dependency. --write-patch writes only pending-cut-scope.patch for root to
apply after the geometry job naturally exits and application is authorized.
"""
import difflib
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import types
import unittest
from unittest.mock import patch

import assess_validation as active
from compatibility import digest
from test_assess_validation import Fixture,FrozenDatetime

TARGET=Path(active.__file__)
BASE_SHA256='a91dab80916d6f3e7540200504c0257d6933ce2723b0ec3b00a6be2f884ff464'

INVARIANTS='''def dispatch_invariants(cut, dispatch):
    """Required observed invariants, without reapplying cut envelope bounds.

    Numeric membership successfully selects only a unique bilateral payload
    with complete protected inventory, finite vectors and a valid relative
    rotation. Keep that evidence, payload/cell identity and actual route
    obstacles/destination checks. Displacement from a cut-only calibrated
    interval is descriptive at dispatch, for both _grip and _route.
    """
    try:
        require(dispatch['grip']['state'] in ('pass','fail') and dispatch['route']['state'] in ('pass','fail'),
                'Dispatch numerical capture/comparison is incomplete')
        grip = dispatch['grip']['observed']['checks']
        routes = dispatch['route']['observed']
        require(len(routes)==1, 'Dispatch route identity is ambiguous')
        route = routes[0]['checks']
        checks = {'same_unique_bilateral_payload_and_cell':dispatch['payload_id']==cut['payload_id']
                  and dispatch['cell_id']==cut['cell_id'],
                  'payload_kind':flag(grip.get('kind')),
                  'payload_family':flag(grip.get('family'))}
        for key in ('free_destination','same_destination_region','payload_kind','payload_family',
                    'corridors_clear_of_other_movable_bodies'):
            checks['route_'+key] = flag(route.get(key))
        return result(checks, scope='Required dispatch capture/payload/destination/obstacle invariants; cut-envelope bounds are descriptive here')
    except (KeyError,TypeError,ValueError) as exc:
        return {'state':'unknown','reason':str(exc)}


'''

OLD_REPORT="            report['numeric_membership'] = memberships; report['class_compatibility'] = compatibility\n"
NEW_REPORT=OLD_REPORT+'''            report['numeric_membership_roles'] = {'cut':'required_cut_admission',
                                                  'before_recovery':'descriptive_cut_envelope_comparison'}
            report['dispatch_invariants'] = dispatch_invariants(memberships['cut'],memberships['before_recovery'])
            report['landmark_clocks'] = {label:{key:state.get(key) for key in ('sim_time_s','wall_elapsed_s')}
                for label,state in states.items() if state.get('status')=='recorded'}
'''
OLD_STATE="            report['state'] = all_states([m['state'] for m in memberships.values()]\n"
NEW_STATE="            report['state'] = all_states([memberships['cut']['state'],report['dispatch_invariants']['state']]\n"


def candidate_source(source):
    if OLD_STATE not in source:
        if source.count(NEW_STATE)==1 and source.count(INVARIANTS)==1 and source.count(NEW_REPORT)==1:
            return source  # Also remains a valid regression after authorized application.
        raise ValueError('Unexpected assessor source; do not apply a stale patch')
    if source.count(OLD_STATE)!=1 or source.count(OLD_REPORT)!=1 or source.count('def hold_assessment(')!=1:
        raise ValueError('Assessor patch anchors are not unique')
    return source.replace('def hold_assessment(',INVARIANTS+'def hold_assessment(',1).replace(OLD_REPORT,NEW_REPORT,1).replace(OLD_STATE,NEW_STATE,1)


def candidate_module():
    module=types.ModuleType('_unapplied_cut_scope_candidate')
    module.__file__=str(TARGET)
    exec(compile(candidate_source(TARGET.read_text(encoding='utf-8')),str(TARGET)+' [unapplied in-memory patch]','exec'),module.__dict__)
    return module


class TransitionFixture(Fixture):
    mode='valid_route_transition'
    def snapshot(self,identity,sim,label):
        value=super().snapshot(identity,sim,label)
        if identity=='v-good' and label=='before_recovery':
            # A valid later posture can be outside the cut start ranges.
            value['robot']['tcp_position_world_m'][2]=.20
            value['robot']['joint_position_rad'][0]=.2
            obj=next(o for o in value['geometry']['objects'] if o['id']=='A1')
            obj['position'][2]=.20;obj['bounds']['min'][2]=.18;obj['bounds']['max'][2]=.22
            if self.mode=='valid_grip_transition':
                value['object_poses']['A1']['relative_to_tcp']['position_m'][0]=.015
                obj['position'][0]+=.015;obj['bounds']['min'][0]+=.015;obj['bounds']['max'][0]+=.015
                value['contacts']['by_object']['A1']['left_normal_force_N']=.9
            if self.mode=='lost_contact':obj['gripper_contact']=False
            if self.mode=='invalid_pose':value['object_poses']['A1']['relative_to_tcp']['rotation']=[[0.]*3 for _ in range(3)]
            if self.mode=='route_blocker':
                other=next(o for o in value['geometry']['objects'] if o['id']=='B2')
                other['position']=[.5,.5,.1];other['bounds']={'min':[.48,.48,.08],'max':[.52,.52,.12]}
            value['snapshot_sha256']=digest({key:item for key,item in value.items() if key!='snapshot_sha256'})
        return value

    def screen(self,phase,day,rule=None):
        extraction,receipt,extract_receipt=super().screen(phase,day,rule)
        if phase!='validation':return extraction,receipt,extract_receipt
        # Keep the synthetic dense intervals consistent with the changed later
        # payload position. This edits only this test's private temporary raw
        # fixture, then creates a fresh derived extraction with matching hashes.
        root=self.root/phase;trace=root/'v-good/whole-geometry.jsonl'
        rows=[json.loads(line) for line in trace.read_bytes().splitlines()]
        later=self.snapshot('v-good',6.,'before_recovery')
        payload=next(o for o in later['geometry']['objects'] if o['id']=='A1')
        for index,row in enumerate(rows[1:],1):
            bounds=row['interval_dense_geometry']['sampled_outer_box_union_m']
            for axis in range(3):
                bounds['min'][1][axis]=min(bounds['min'][1][axis],payload['bounds']['min'][axis])
                bounds['max'][1][axis]=max(bounds['max'][1][axis],payload['bounds']['max'][axis])
            if index==1:
                row['objects']=later['geometry']['objects']
                geom=next(g for g in row['robot_and_payload_geoms'] if g['geom_id']==9)
                geom['position_m']=payload['position'];geom['outer_bounds']=payload['bounds']
        trace.write_bytes(b''.join(active.reader.canonical(row)+b'\n' for row in rows))
        self.index(root)
        marker=json.loads(extraction.read_bytes());output=self.root/'validation-transition-extraction'
        FrozenDatetime.day=day
        with patch.object(active.reader,'datetime',FrozenDatetime):
            active.reader.extract(root,receipt,output,extraction_queue=marker['extraction_queue'])
        return output/'extraction.json',receipt,extract_receipt


class PendingCutScopeTests(unittest.TestCase):
    def test_valid_transition_outside_cut_bounds_is_descriptive_not_rejected(self):
        before=hashlib.sha256(TARGET.read_bytes()).hexdigest();candidate=candidate_module()
        for mode in ('valid_route_transition','valid_grip_transition'):
            with self.subTest(mode=mode),TemporaryDirectory() as directory:
                fixture=TransitionFixture(Path(directory));fixture.mode=mode;args=fixture.complete()
                old=active.assess(*args);new=candidate.assess(*args)
                old_row=next(r for r in old['trials'] if r['trial_id']=='v-good')
                row=next(r for r in new['trials'] if r['trial_id']=='v-good')
                if OLD_STATE in TARGET.read_text(encoding='utf-8'):self.assertEqual(old_row['state'],'fail')
                self.assertEqual(row['numeric_membership']['cut']['state'],'pass')
                self.assertEqual(row['numeric_membership']['before_recovery']['state'],'fail')
                self.assertEqual(row['state'],'pass',row)
                self.assertEqual(row['dispatch_invariants']['state'],'pass')
                self.assertEqual(row['hold_absence_placement_timing'],old_row['hold_absence_placement_timing'])
                self.assertEqual(row['dense_geometry'],old_row['dense_geometry'])
                self.assertEqual(row['landmark_refs'],old_row['landmark_refs'])
                self.assertEqual(row['landmark_clocks']['before_recovery'],{'sim_time_s':6.,'wall_elapsed_s':6.09})
                self.assertEqual(row['landmark_clocks']['recovery_admission'],{'sim_time_s':6.,'wall_elapsed_s':6.1})
                self.assertFalse(new['qualification_granted'])
        self.assertEqual(hashlib.sha256(TARGET.read_bytes()).hexdigest(),before)

    def test_cut_failure_and_measured_transition_invariants_still_reject(self):
        candidate=candidate_module()
        for mode in ('lost_contact','invalid_pose','route_blocker'):
            with self.subTest(mode=mode),TemporaryDirectory() as directory:
                fixture=TransitionFixture(Path(directory));fixture.mode=mode
                report=candidate.assess(*fixture.complete());rows={r['trial_id']:r for r in report['trials']}
                self.assertNotEqual(rows['v-good']['state'],'pass',rows['v-good'])
                self.assertEqual(rows['v-outside']['state'],'fail')
                self.assertEqual(rows['v-failed']['state'],'fail')
                self.assertEqual(rows['v-missing']['state'],'unknown')
                if mode=='lost_contact':self.assertFalse(rows['v-good']['hold_absence_placement_timing']['checks']['hold_at_before_recovery'])
                if mode=='route_blocker':self.assertFalse(rows['v-good']['dispatch_invariants']['checks']['route_corridors_clear_of_other_movable_bodies'])


if __name__=='__main__':
    import sys
    if sys.argv[1:]==['--write-patch']:
        source=TARGET.read_text(encoding='utf-8')
        if hashlib.sha256(TARGET.read_bytes()).hexdigest()!=BASE_SHA256:raise ValueError('Base assessor hash changed')
        relative='Long-Horizon Adaptive Robotics Expirement/Batch 01/Restart Qualification Tools/assess_validation.py'
        patch=''.join(difflib.unified_diff(source.splitlines(True),candidate_source(source).splitlines(True),
                                         fromfile=relative,tofile=relative))
        target=TARGET.with_name('pending-cut-scope.patch')
        with target.open('x',encoding='utf-8',newline='\n') as stream:stream.write(patch)
        print(str(target))
    else:unittest.main()
