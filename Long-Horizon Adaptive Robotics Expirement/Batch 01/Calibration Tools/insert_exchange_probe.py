"""Shared contact insert exchange calibration; never a task/policy result."""
from __future__ import annotations


def exchange_check(snapshot, installed_family, width):
    objects=snapshot['objects'];zones=snapshot['zones']
    inserts=[o for o in objects if o['kind']=='insert']
    flags={'exact_insert_ids':len(inserts)==2 and {o['id'] for o in inserts}=={'insert_A','insert_B'},
           'open_gripper':width>=.065,
           'no_pending_work':not any(snapshot['pending'].values()),
           'arm_settled':max(map(abs,snapshot['arm_velocity']))<=.02,
           'fingers_settled':max(map(abs,snapshot['finger_velocity']))<=.01,
           'idle_open_station':all(snapshot['station'].get(k) is v for k,v in
                {'busy':False,'guard_closed':False,'clamped':False,'fault':False}.items())}
    destinations={}
    for item in inserts:
        name='fixture' if item['family']==installed_family else 'insert_home_'+item['family']
        destinations[item['id']]=name;region=zones[name]
        flags[item['id']+'_contained']=all(item['bounds']['min'][i]>=region['min'][i]-1e-6
              and item['bounds']['max'][i]<=region['max'][i]+1e-6 for i in range(3))
        flags[item['id']+'_released']=item['gripper_contact'] is False
        flags[item['id']+'_settled']=sum(v*v for v in item['linear_velocity'])<=.05**2 and sum(v*v for v in item['angular_velocity'])<=.1**2
    region=zones['fixture']
    occupants=[o['id'] for o in objects if all(min(o['bounds']['max'][i],region['max'][i])-max(o['bounds']['min'][i],region['min'][i])>1e-6 for i in range(3))]
    flags['only_requested_insert_in_fixture']=occupants==['insert_'+installed_family]
    flags['stock_remains_raw']=all(o.get('cycles')==0 and o.get('recipe') is None and o.get('inspection') is None
                                 for o in objects if o['kind']=='part')
    return {'passed_now':all(flags.values()),'flags':flags,'installed_family':installed_family,
            'expected_insert_destinations':destinations,'fixture_collision_occupants':occupants}


def run(loop):
    from physical_calibration import StablePredicate
    cell=loop.cells[0];checks=[]
    for family in ('B','A'):
        loop.until(loop.public_ready,8.)
        request=loop.submit({'operation':'setup','family':family})
        loop.terminal(request,timeout=70.)
        stable=StablePredicate();last={}
        def verify():
            check=exchange_check(loop.snapshot(),family,float(sum(cell.data.qpos[7:9])))
            last.clear();last.update(check)
            return stable.update(float(cell.data.time),check['passed_now'])
        try:loop.until(verify,15.)
        finally:
            loop.records.event('independent_insert_exchange_check',{'request_id':request,'check':last,
                    'required_dwell_s':.5,'stable_since_sim_s':stable.since,'checked_every_physics_tick':True,
                    'protected_snapshot':loop.snapshot()},float(cell.data.time))
        checks.append({'family':family,'request_id':request,'check':last.copy(),'stable_since_sim_s':stable.since})
    return {'physical_predicates_passed':len(checks)==2 and all(c['check']['passed_now'] for c in checks),
            'checks':checks,'scope':'B then A physical insert exchange and return-home containment; no complete task result'}
