"""Synthetic geometry counterexamples only; no simulator or Runtime imports."""
import copy
import unittest
from insert_exchange_probe import exchange_check


def scene():
    def region(x):return {'min':[x-.053,-.053,-.003],'max':[x+.053,.053,.08]}
    def insert(family,x):return {'id':'insert_'+family,'family':family,'kind':'insert','position':[x,0,.008],
        'bounds':{'min':[x-.025,-.025,0.],'max':[x+.025,.025,.016]},'linear_velocity':[0.,0.,0.],
        'angular_velocity':[0.,0.,0.],'gripper_contact':False}
    return {'objects':[insert('A',.2),insert('B',.6)],'zones':{'fixture':region(.6),'insert_home_A':region(.2),'insert_home_B':region(.9)},
            'pending':{'active_request':False},'arm_velocity':[0.]*7,'finger_velocity':[0.,0.],
            'station':{'busy':False,'guard_closed':False,'clamped':False,'fault':False}}


class ExchangeChecks(unittest.TestCase):
    def test_correct_exchange(self):self.assertTrue(exchange_check(scene(),'B',.08)['passed_now'])
    def test_stacked_inserts_fail_despite_requested_insert_present(self):
        s=scene();s['objects'][0]['bounds']=copy.deepcopy(s['objects'][1]['bounds'])
        self.assertFalse(exchange_check(s,'B',.08)['passed_now'])
    def test_home_center_inside_with_protruding_full_bounds_fails(self):
        s=scene();s['objects'][0]['bounds']['max'][0]=.254
        self.assertFalse(exchange_check(s,'B',.08)['passed_now'])
    def test_held_moving_or_closed_grip_cannot_pass(self):
        for change in ('held','moving','closed'):
            s=scene();width=.04 if change=='closed' else .08
            if change=='held':s['objects'][0]['gripper_contact']=True
            if change=='moving':s['objects'][0]['linear_velocity']=[.1,0.,0.]
            self.assertFalse(exchange_check(s,'B',width)['passed_now'])


if __name__=='__main__':unittest.main()
