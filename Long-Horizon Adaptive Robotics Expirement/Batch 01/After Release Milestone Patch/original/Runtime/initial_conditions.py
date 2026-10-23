"""Protected initial-validity evidence and supplied-seed restart opportunities.

These helpers never generate entropy or expose their private configuration to a
candidate. Geometric preflight establishes necessary conditions, not a solution
or proof of reachability; all-horizon physical calibration is still required.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def finite(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def validate_initial_snapshot(snapshot,n):
    """Protected synthetic/physical snapshot checks without motion or rendering."""
    errors=[]
    if type(n) is not int or n not in (3,6,10):errors.append('unsupported part count')
    objects=snapshot.get('objects',[])
    ids=[o.get('id') for o in objects]
    if any(not isinstance(i,str) for i in ids) or len(set(ids))!=len(ids):errors.append('duplicate or invalid object identity')
    parts=[o for o in objects if o.get('kind')=='part']
    inserts=[o for o in objects if o.get('kind')=='insert']
    if len(parts)!=n or sum(o.get('family')=='A' for o in parts)!=(n+1)//2 or sum(o.get('family')=='B' for o in parts)!=n//2:
        errors.append('stock family counts differ from the released job')
    expected={f'{"A" if i%2==0 else "B"}{i+1}' for i in range(n)}
    if {o.get('id') for o in parts}!=expected:errors.append('initial stock identities differ from the frozen public tag registry')
    if {o.get('id') for o in inserts}!={'insert_A','insert_B'} or len(objects)!=n+2:
        errors.append('exact two-insert workcell registry required')
    for obj in objects:
        identity=obj.get('id');bounds=obj.get('bounds',{})
        low,high=bounds.get('min',[]),bounds.get('max',[])
        if len(low)!=3 or len(high)!=3 or not all(finite(x) for x in low+high) or any(a>=b for a,b in zip(low,high)):
            errors.append('invalid bounds for '+str(identity));continue
        if low[0]<.05 or high[0]>.85 or low[1]<-.55 or high[1]>.55 or low[2]<-.003 or high[2]>.08:
            errors.append('initial object outside declared table/rest envelope: '+identity)
        for key,limit in (('linear_velocity',.05),('angular_velocity',.10)):
            velocity=obj.get(key,[])
            if len(velocity)!=3 or not all(finite(v) for v in velocity) or sum(v*v for v in velocity)>limit*limit:
                errors.append('unsettled initial '+key+': '+identity)
        if obj.get('gripper_contact') is not False:errors.append('initial gripper contact: '+identity)
        if obj.get('kind')=='part' and (obj.get('cycles')!=0 or obj.get('recipe') is not None or obj.get('inspection') is not None
                                         or obj.get('cycle_history')!=[] or obj.get('inspection_history')!=[]):
            errors.append('initial processed/inspection history is not empty: '+identity)
    valid_boxes=[o for o in objects if len(o.get('bounds',{}).get('min',[]))==3 and len(o.get('bounds',{}).get('max',[]))==3]
    for index,a in enumerate(valid_boxes):
        for b in valid_boxes[index+1:]:
            penetration=[min(a['bounds']['max'][k],b['bounds']['max'][k])-max(a['bounds']['min'][k],b['bounds']['min'][k]) for k in range(3)]
            if all(p>.001 for p in penetration):errors.append('initial movable bounds overlap: '+a['id']+' / '+b['id'])
    zones=snapshot.get('zones',{})
    for identity,name in (('insert_A','fixture'),('insert_B','insert_home_B')):
        obj=next((o for o in valid_boxes if o.get('id')==identity),None);zone=zones.get(name)
        if not obj or not zone or not all(obj['bounds']['min'][k]>=zone['min'][k]-1e-6 and obj['bounds']['max'][k]<=zone['max'][k]+1e-6 for k in range(3)):
            errors.append('initial insert not contained in its declared home: '+identity)
    parking={}
    for name in ('parking1','parking2'):
        zone=zones.get(name)
        if not zone:errors.append('missing finite parking zone '+name);continue
        occupants=[o['id'] for o in valid_boxes if all(min(o['bounds']['max'][k],zone['max'][k])-max(o['bounds']['min'][k],zone['min'][k])>1e-6 for k in range(3))]
        parking[name]=occupants
        if len(occupants)>1:errors.append('initial parking capacity exceeded: '+name)
    for name in ('tray1','tray2','tray3','fixture','inspection'):
        zone=zones.get(name)
        if not zone:errors.append('missing declared zone '+name);continue
        touched=[o['id'] for o in valid_boxes if o.get('kind')=='part' and all(min(o['bounds']['max'][k],zone['max'][k])-max(o['bounds']['min'][k],zone['min'][k])>1e-6 for k in range(3))]
        if touched:errors.append('initial workpiece occupies reserved '+name+': '+','.join(touched))
    station=snapshot.get('station',{})
    if any(station.get(k) is not v for k,v in {'busy':False,'ready':True,'fault':False,'guard_closed':False,'clamped':False}.items()):errors.append('initial station is not in declared safe idle state')
    pending=snapshot.get('pending',{})
    if any(pending.get(k) is not False for k in ('active_request','queued_motion','active_segment','machine_cycle','inspection')):errors.append('initial command/timer state is not empty')
    for key,count,limit in (('arm_velocity',7,.02),('finger_velocity',2,.01)):
        velocities=snapshot.get(key,[])
        if len(velocities)!=count or any(not finite(v) or abs(v)>limit for v in velocities):errors.append('initial robot is not settled: '+key)
    try:source_hash=hashlib.sha256(canonical(snapshot)).hexdigest()
    except (ValueError,TypeError):source_hash=None;errors.append('initial snapshot cannot be canonically serialized')
    return {'schema_version':'robot-initial-validity-1.0','audience':'evaluator/operator only','valid':not errors,
            'errors':errors,'part_count':len(parts),'initial_parking_occupancy':parking,
            'snapshot_sha256':source_hash,
            'scope':'necessary protected geometry/stock/history/settling/idle checks',
            'not_asserted':['policy success','complete trajectory feasibility','perfect visibility','all-horizon physical readiness']}


def initial_world_report(cell,n,*,zones,zone_half):
    snapshot=cell.evaluator.snapshot_cell(cell,zones=zones,zone_half=zone_half)
    report=validate_initial_snapshot(snapshot,n)
    report['scene_xml_sha256']=hashlib.sha256(cell.xml.encode('utf-8')).hexdigest()
    report['sim_time_s']=float(cell.data.time)
    return report


class RestartOpportunity:
    """One declared cut with a fixed latest fallback; survives candidate death."""
    PHASES=('after_acceptance','closed_grip_transfer','after_release','before_outcome')
    CLOSED_GRIP_MIN_TCP_Z_M=.08
    def __init__(self,world_seed,*,enabled=True,fallback_s=60.):
        if type(world_seed) is not int or world_seed<0:raise ValueError('supplied nonnegative world seed required')
        if not finite(fallback_s) or fallback_s<=0:raise ValueError('positive fixed fallback required')
        digest=hashlib.sha256(canonical({'domain':'batch01-restart-opportunity-v1','world_seed':world_seed})).digest()
        self._config={'schema_version':'robot-restart-opportunity-1.1','audience':'evaluator/operator only',
                      'enabled':bool(enabled),'cut':self.PHASES[digest[0]%len(self.PHASES)],
                      'transport_ordinal':1+digest[1]%2,'fallback_s':float(fallback_s),
                      'closed_grip_min_tcp_z_m':self.CLOSED_GRIP_MIN_TCP_Z_M,
                      'tcp_height_source':'current public robot TCP telemetry; not payload pose',
                      'source':'deterministic domain separation of supplied world seed; no new entropy',
                      'held_limit':'closed jaw, trajectory phase and TCP height do not prove a payload is held or recoverable'}
        self._seen=[];self._last_time=None;self._exposure=None

    def configuration(self):return copy.deepcopy(self._config)

    def observe(self,elapsed,active_request,segment,*,width,tcp_z=None):
        if not finite(elapsed) or elapsed<0 or not finite(width) or width<0:raise ValueError('invalid public clock/gripper sample')
        if self._last_time is not None and elapsed<self._last_time:raise ValueError('restart opportunity clock cannot move backwards')
        self._last_time=float(elapsed)
        if not self._config['enabled'] or self._exposure is not None:return None
        request=active_request or {};rid=request.get('request_id')
        if request.get('operation')=='transport' and isinstance(rid,str) and rid not in self._seen:self._seen.append(rid)
        target=len(self._seen)>=self._config['transport_ordinal'] and rid==self._seen[self._config['transport_ordinal']-1]
        phase=segment.get('phase') if isinstance(segment,dict) else None
        cut=self._config['cut']
        # Public robot height prevents a cut at phase4 entry while the tool
        # is still at pickup level. Payload/contact admissibility is separate.
        height_available=finite(tcp_z)
        height_qualified=height_available and tcp_z>=self._config['closed_grip_min_tcp_z_m']
        matched=bool(target and ((cut=='after_acceptance')
                    or (cut=='closed_grip_transfer' and phase in (4,5) and width<.065 and height_qualified)
                    or (cut=='after_release' and phase==7 and width>=.065)
                    or (cut=='before_outcome' and phase==9)))
        fallback=elapsed>=self._config['fallback_s']
        if not matched and not fallback:return None
        self._exposure={'configured_cut':cut,'configured_transport_ordinal':self._config['transport_ordinal'],
                        'actual_cut':cut if matched else 'deadline_fallback','fallback_used':not matched,
                        'sim_elapsed_s':float(elapsed),'active_request_id':rid,'actual_segment_phase':phase,
                        'measured_gripper_width_m':float(width),'transport_opportunities_seen':len(self._seen),
                        'closed_grip_min_tcp_z_m':self._config['closed_grip_min_tcp_z_m'],
                        'measured_tcp_z_m':float(tcp_z) if height_available else None,
                        'tcp_height_status':'available' if height_available else ('missing' if tcp_z is None else 'invalid'),
                        'tcp_height_qualified':bool(height_qualified),
                        'configured_milestone_exercised':matched,'runtime_restart_required':True,
                        'no_private_history_returned_to_candidate':True}
        return copy.deepcopy(self._exposure)
