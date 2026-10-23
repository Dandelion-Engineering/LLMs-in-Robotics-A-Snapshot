"""Synthetic initial-state/restart-policy fixtures; no physical runs or seeds released."""
import copy
import unittest
import xml.etree.ElementTree as ET

from initial_conditions import RestartOpportunity,validate_initial_snapshot
from test_evaluator import obj,zone,move
from cell import ZONES,zone_half,build_scene


def initial(n=3,raw_x=.32,raw_y=-.373,row_pitch=.095):
    objects=[]
    for index in range(n):
        family='A' if index%2==0 else 'B';row,col=divmod(index,3)
        item=obj(f'{family}{index+1}',raw_x+.085*col,raw_y+row_pitch*row,family=family)
        item.update(recipe=None,cycles=0,inspection=None,cycle_history=[],inspection_history=[])
        objects.append(item)
    objects.extend([obj('insert_A',*ZONES['fixture'],kind='insert'),obj('insert_B',*ZONES['insert_home_B'],family='B',kind='insert')])
    return {'objects':objects,'zones':{name:zone(*xy,*zone_half(name)) for name,xy in ZONES.items()},
            'station':{'busy':False,'ready':True,'fault':False,'guard_closed':False,'clamped':False},
            'pending':{k:False for k in ('active_request','queued_motion','active_segment','machine_cycle','inspection')},
            'arm_velocity':[0.]*7,'finger_velocity':[0.,0.]}


class InitialTests(unittest.TestCase):
    def test_all_three_nominal_stock_shapes_pass_necessary_conditions(self):
        # The shared raw grid uses 95 mm row spacing. These are synthetic
        # necessary-condition checks, not contact/reachability calibration.
        for n in (3,6,10):
            report=validate_initial_snapshot(initial(n),n)
            self.assertTrue(report['valid'],report)
            self.assertIn('complete trajectory feasibility',report['not_asserted'])

    def test_former_ten_part_raw_column_overlaps_single_capacity_parking(self):
        snapshot=initial(10,raw_y=-.31,row_pitch=.074)
        snapshot['zones']['parking2']=zone(.27,-.09,.053,.053)
        report=validate_initial_snapshot(snapshot,10)
        self.assertFalse(report['valid'])
        self.assertEqual(report['initial_parking_occupancy']['parking2'],['A7','B10'])

    def test_generated_ten_part_layouts_preserve_raw_grid_and_empty_parking(self):
        for seed in range(8):
            xml,registry=build_scene(10,seed);tree=ET.fromstring(xml)
            snapshot=initial(10)
            for item in snapshot['objects']:
                body=tree.find(".//body[@name='"+item['id']+"']")
                move(item,list(map(float,body.get('pos').split())),registry[item['id']]['half'])
            report=validate_initial_snapshot(snapshot,10)
            self.assertTrue(report['valid'],report)
            self.assertEqual(report['initial_parking_occupancy'],{'parking1':[],'parking2':[]})
        self.assertEqual(ZONES['parking1'],(.34,.04))
        self.assertEqual(ZONES['parking2'],(.46,.12))

    def test_wrong_stock_reserved_occupancy_or_prior_history_is_rejected(self):
        for change in (lambda s:s['objects'].pop(0),
                       lambda s:move(s['objects'][0],[.4,.33,.02]),
                       lambda s:s['objects'][0].update(cycles=1),
                       lambda s:s['objects'][0].update(gripper_contact=True),
                       lambda s:s['station'].update(busy=True),
                       lambda s:s['pending'].update(active_request=True)):
            snapshot=initial();change(snapshot)
            self.assertFalse(validate_initial_snapshot(snapshot,3)['valid'])

    def test_unsettled_robot_and_wrong_insert_home_fail(self):
        snapshot=initial();snapshot['arm_velocity'][0]=.03
        self.assertFalse(validate_initial_snapshot(snapshot,3)['valid'])
        snapshot=initial();move(snapshot['objects'][-1],[.65,-.29,.008])
        self.assertFalse(validate_initial_snapshot(snapshot,3)['valid'])

    def test_same_supplied_seed_selects_same_rules_without_public_seed_field(self):
        first=RestartOpportunity(17);second=RestartOpportunity(17)
        self.assertEqual(first.configuration(),second.configuration())
        self.assertNotIn('world_seed',first.configuration())
        cuts={RestartOpportunity(i).configuration()['cut'] for i in range(40)}
        self.assertEqual(cuts,set(RestartOpportunity.PHASES))

    def test_every_selected_cut_has_deterministic_reachable_synthetic_trigger(self):
        found={}
        for seed in range(100):
            tracker=RestartOpportunity(seed);config=tracker.configuration()
            if config['cut'] in found:continue
            phase,width={'after_acceptance':(None,.08),'closed_grip_transfer':(5,.042),
                         'after_release':(7,.08),'before_outcome':(9,.08)}[config['cut']]
            for ordinal in range(1,config['transport_ordinal']+1):
                result=tracker.observe(ordinal,{'operation':'transport','request_id':str(ordinal)},
                                       {'phase':phase} if phase is not None else None,width=width,tcp_z=.098)
            self.assertTrue(result['configured_milestone_exercised'])
            self.assertFalse(result['fallback_used'])
            self.assertIsNone(tracker.observe(5.,None,None,width=.08))
            found[config['cut']]=True
        self.assertEqual(set(found),set(RestartOpportunity.PHASES))

    def test_fallback_resolves_an_unexercised_milestone_without_claiming_recovery(self):
        tracker=RestartOpportunity(5)
        self.assertIsNone(tracker.observe(59.,None,None,width=.08))
        event=tracker.observe(60.,None,None,width=.08)
        self.assertTrue(event['fallback_used'])
        self.assertFalse(event['configured_milestone_exercised'])
        self.assertNotIn('recovered',event)

    def test_disabled_counterpart_never_restarts_and_clock_cannot_reset(self):
        self.assertIsNone(RestartOpportunity(5,enabled=False).observe(100.,None,None,width=.08))
        tracker=RestartOpportunity(5);tracker.observe(10.,None,None,width=.08)
        with self.assertRaises(ValueError):tracker.observe(9.,None,None,width=.08)

    def _carry_tracker(self):
        seed=next(i for i in range(100) if RestartOpportunity(i).configuration()['cut']=='closed_grip_transfer')
        tracker=RestartOpportunity(seed);ordinal=tracker.configuration()['transport_ordinal']
        for prior in range(1,ordinal):
            self.assertIsNone(tracker.observe(float(prior),{'operation':'transport','request_id':str(prior)},
                                             {'phase':3},width=.042,tcp_z=.018))
        return tracker,{'operation':'transport','request_id':str(ordinal)}

    def test_carry_milestone_waits_for_available_public_tcp_height(self):
        cases=[{}, {'tcp_z':None}, {'tcp_z':.018}, {'tcp_z':.079999}, {'tcp_z':float('nan')},
               {'tcp_z':float('inf')}, {'tcp_z':-float('inf')}, {'tcp_z':True}, {'tcp_z':'0.098'}]
        for options in cases:
            with self.subTest(options=options):
                tracker,request=self._carry_tracker()
                self.assertIsNone(tracker.observe(10.,request,{'phase':4},width=.042,**options))
                event=tracker.observe(11.,request,{'phase':4},width=.042,tcp_z=.08)
                self.assertTrue(event['configured_milestone_exercised'])
                self.assertEqual(event['measured_tcp_z_m'],.08)
                self.assertEqual(event['closed_grip_min_tcp_z_m'],.08)
                self.assertTrue(event['tcp_height_qualified'])
                self.assertEqual(tracker.configuration()['closed_grip_min_tcp_z_m'],.08)
                self.assertIn('not payload pose',tracker.configuration()['tcp_height_source'])
                self.assertNotIn('payload_id',event)
                self.assertNotIn('recovered',event)

    def test_low_clearance_transfer_still_reaches_both_carry_phases(self):
        for phase in (4,5):
            for height in (.08,.098,.10):
                with self.subTest(phase=phase,height=height):
                    tracker,request=self._carry_tracker()
                    event=tracker.observe(10.,request,{'phase':phase},width=.042,tcp_z=height)
                    self.assertTrue(event['configured_milestone_exercised'])
                    self.assertEqual(event['measured_tcp_z_m'],height)
                    self.assertFalse(event['fallback_used'])

    def test_height_does_not_replace_phase_or_closed_jaw_requirements(self):
        for phase,width in ((3,.042),(6,.042),(4,.065),(5,.08)):
            with self.subTest(phase=phase,width=width):
                tracker,request=self._carry_tracker()
                self.assertIsNone(tracker.observe(10.,request,{'phase':phase},width=width,tcp_z=.098))

    def test_unknown_height_does_not_disable_the_sixty_second_fallback(self):
        for options in ({},{'tcp_z':float('nan')},{'tcp_z':float('inf')}):
            with self.subTest(options=options):
                tracker,request=self._carry_tracker()
                self.assertEqual(tracker.configuration()['fallback_s'],60.)
                self.assertIsNone(tracker.observe(59.,request,{'phase':4},width=.042,**options))
                event=tracker.observe(60.,request,{'phase':4},width=.042,**options)
                self.assertTrue(event['fallback_used'])
                self.assertEqual(event['actual_cut'],'deadline_fallback')
                self.assertFalse(event['configured_milestone_exercised'])
                self.assertIsNone(event['measured_tcp_z_m'])
                self.assertFalse(event['tcp_height_qualified'])
                self.assertEqual(event['tcp_height_status'],'missing' if not options else 'invalid')
                __import__('json').dumps(event,allow_nan=False)

    def test_other_three_cut_families_do_not_require_tcp_height(self):
        checked=set()
        for seed in range(100):
            tracker=RestartOpportunity(seed);config=tracker.configuration();cut=config['cut']
            if cut=='closed_grip_transfer' or cut in checked:continue
            phase,width={'after_acceptance':(None,.08),'after_release':(7,.08),'before_outcome':(9,.08)}[cut]
            for ordinal in range(1,config['transport_ordinal']+1):
                event=tracker.observe(float(ordinal),{'operation':'transport','request_id':str(ordinal)},
                                      {'phase':phase} if phase is not None else None,width=width)
            self.assertTrue(event['configured_milestone_exercised'])
            self.assertIsNone(event['measured_tcp_z_m'])
            checked.add(cut)
        self.assertEqual(checked,set(RestartOpportunity.PHASES)-{'closed_grip_transfer'})


if __name__=='__main__':unittest.main(verbosity=2)
