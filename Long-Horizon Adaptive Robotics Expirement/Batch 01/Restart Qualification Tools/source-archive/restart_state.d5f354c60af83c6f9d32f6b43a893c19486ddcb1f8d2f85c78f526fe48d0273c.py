"""Protected restart evidence captured by the active supervisor, not a gate.

Capture only on the physics owner thread immediately before authority revocation.
Never place this snapshot/classification in a candidate packet. The classifier
does not choose cuts, mutate Cell, load evidence files, inspect later outcomes,
or designate an episode infrastructure-invalid.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from restart_physical_class import export_observation
from restart_qualification import qualified_entry_identity

SCHEMA='protected-restart-state-1.0'
CLASSIFIER='restart-admissibility-1.0'
PHASES=('after_acceptance','closed_grip_transfer','after_release','before_outcome')
DEFAULT_POLICY={'table_envelope':{'min':[.05,-.55,-.003],'max':[.85,.55,.8]},
                'open_width_m':.065,'empty_close_width_m':.005,
                'linear_rest_m_s':.05,'angular_rest_rad_s':.10,
                'unheld_scoring_rim_z_m':.08,
                'support_upward_force_N':.01,'maximum_capture_age_s':.35,
                'maximum_contact_penetration_m':.003,
                'contact_distance_tolerance_m':.001,
                'recovery_destinations':['parking1','parking2','inspection','quarantine']}


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def number(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
def vector(value,n=3):return isinstance(value,(list,tuple)) and len(value)==n and all(number(v) for v in value)
def norm(value):return math.sqrt(sum(v*v for v in value))
def transpose(matrix):return [list(row) for row in zip(*matrix)]
def matvec(matrix,vec):return [sum(a*b for a,b in zip(row,vec)) for row in matrix]
def matmul(a,b):return [[sum(x*y for x,y in zip(row,col)) for col in zip(*b)] for row in a]
def proper_rotation(matrix):
    if not isinstance(matrix,list) or len(matrix)!=3 or not all(vector(row) for row in matrix):return False
    product=matmul(matrix,transpose(matrix))
    determinant=sum(matrix[0][i]*(matrix[1][(i+1)%3]*matrix[2][(i+2)%3]-matrix[1][(i+2)%3]*matrix[2][(i+1)%3]) for i in range(3))
    return abs(determinant-1.)<=1e-5 and all(abs(product[i][j]-(1 if i==j else 0))<=1e-5 for i in range(3) for j in range(3))
def inside(point,box):return vector(point) and valid_box(box) and all(box['min'][i]<=point[i]<=box['max'][i] for i in range(3))
def valid_box(box):return isinstance(box,dict) and vector(box.get('min')) and vector(box.get('max')) and all(a<b for a,b in zip(box['min'],box['max']))
def contained(bounds,region):return valid_box(bounds) and valid_box(region) and all(bounds['min'][i]>=region['min'][i]-1e-6 and bounds['max'][i]<=region['max'][i]+1e-6 for i in range(3))
def overlaps(a,b):return valid_box(a) and valid_box(b) and all(min(a['max'][i],b['max'][i])-max(a['min'][i],b['min'][i])>1e-6 for i in range(3))


def relative_pose(tcp_position,tcp_rotation,position,rotation):
    inverse=transpose(tcp_rotation)
    return {'position_m':matvec(inverse,[position[i]-tcp_position[i] for i in range(3)]),
            'rotation':matmul(inverse,rotation)}


def contact_evidence(records,object_ids,*,distance_tolerance=.001):
    """Summarize exact contacts, keeping force-bearing bilateral evidence apart.

    Record force_world_on_geom2_N uses frame.T @ local force. MuJoCo's normal
    points geom1 -> geom2; the force on geom1 is its negative. Sources:
    https://mujoco.readthedocs.io/en/stable/computation/index.html
    https://mujoco.readthedocs.io/en/stable/APIreference/APIfunctions.html#mj-contactforce
    """
    result={identity:{'hand_contact':False,'left_finger_contact':False,'right_finger_contact':False,
                      'left_normal_force_N':0.,'right_normal_force_N':0.,'contact_indices':[],
                      'support_upward_force_N':0.,'support_contact_indices':[],
                      'nonhand_contact_indices':[]} for identity in object_ids}
    for record in records:
        if record['distance_m']>distance_tolerance:continue
        for side,other,sign in ((1,2,-1),(2,1,1)):
            identity=record[f'object{side}'];entry=result.get(identity)
            if entry is None:continue
            entry['contact_indices'].append(record['index'])
            finger=record[f'gripper_side{other}']
            if finger:
                entry['hand_contact']=True
                if finger in ('left','right'):
                    entry[f'{finger}_finger_contact']=True
                    if record['constraint_active']:entry[f'{finger}_normal_force_N']+=max(0.,record['force_contact_N_Nm'][0])
            else:
                entry['nonhand_contact_indices'].append(record['index'])
                # An upward force at a lower contact is explicit support
                # evidence, distinct from the mere proximity of two boxes.
                force_z=sign*record['force_world_on_geom2_N'][2]
                lower=record['position_m'][2]<=record[f'object{side}_center_z_m']
                if record['constraint_active'] and record.get(f'support_eligible{other}') is True and lower and force_z>0:
                    entry['support_upward_force_N']+=force_z
                    entry['support_contact_indices'].append(record['index'])
    for entry in result.values():
        entry['bilateral_force_bearing']=entry['left_normal_force_N']>0 and entry['right_normal_force_N']>0
    return result


def _plain(value,errors,path='snapshot'):
    if hasattr(value,'tolist'):value=value.tolist()
    if isinstance(value,dict):return {str(k):_plain(v,errors,path+'.'+str(k)) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [_plain(v,errors,path+'['+str(i)+']') for i,v in enumerate(value)]
    if isinstance(value,float) and not math.isfinite(value):errors.append(path+': nonfinite');return None
    if value is None or isinstance(value,(str,int,float,bool)):return value
    errors.append(path+': unsupported '+type(value).__name__);return None


def capture_restart_state(cell,*,zones,zone_half,exposure,source_hashes=None,infrastructure=None):
    """Rich read-only capture. Imports physics packages only when called.

    infrastructure is optional operator evidence {status: valid|invalid|unknown,
    reasons:[...]}; this helper does not infer its cause from task difficulty.
    source_hashes must identify the exact source bytes used in this incarnation.
    """
    import mujoco
    import numpy as np
    model,data=cell.model,cell.data;errors=[]
    geometry=cell.evaluator.snapshot_cell(cell,zones=zones,zone_half=zone_half)
    registry={name:int(mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY,name)) for name in cell.registry}
    roots={name:int(mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY,name)) for name in ('hand','left_finger','right_finger')}
    if any(body<0 for body in [*registry.values(),*roots.values()]):errors.append('required physical body missing')
    def descendant(body,root):
        if root<0:return False
        while body>0:
            if body==root:return True
            body=int(model.body_parentid[body])
        return False
    def side(body):
        if descendant(body,roots['left_finger']):return 'left'
        if descendant(body,roots['right_finger']):return 'right'
        return 'hand' if descendant(body,roots['hand']) else None
    def identity(body):return next((name for name,root in registry.items() if descendant(body,root)),None)
    tcp_position=data.site_xpos[cell.tcp].tolist();tcp_rotation=data.site_xmat[cell.tcp].reshape(3,3).tolist()
    poses={}
    for name,body in registry.items():
        if body<0:continue
        position=data.xpos[body].tolist();rotation=data.xmat[body].reshape(3,3).tolist()
        poses[name]={'body_id':body,'position_world_m':position,'rotation_world':rotation,
                     'relative_to_tcp':relative_pose(tcp_position,tcp_rotation,position,rotation)}
    records=[]
    for index in range(data.ncon):
        contact=data.contact[index];ga,gb=int(contact.geom1),int(contact.geom2)
        ba,bb=int(model.geom_bodyid[ga]),int(model.geom_bodyid[gb]);oa,ob=identity(ba),identity(bb)
        if oa is None and ob is None and side(ba) is None and side(bb) is None:continue
        force=np.zeros(6);mujoco.mj_contactForce(model,data,index,force)
        frame=contact.frame.reshape(3,3).tolist()
        records.append({'index':index,'geom1':ga,'geom2':gb,
            'geom1_name':mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_GEOM,ga),
            'geom2_name':mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_GEOM,gb),
            'body1':ba,'body2':bb,'body1_name':mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_BODY,ba),
            'body2_name':mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_BODY,bb),
            'object1':oa,'object2':ob,'gripper_side1':side(ba),'gripper_side2':side(bb),
            'support_eligible1':ba==0 or oa is not None,'support_eligible2':bb==0 or ob is not None,
            'object1_center_z_m':float(data.xpos[registry[oa],2]) if oa else None,
            'object2_center_z_m':float(data.xpos[registry[ob],2]) if ob else None,
            'distance_m':float(contact.dist),'position_m':contact.pos.tolist(),'contact_frame_rows_world':frame,
            'constraint_active':int(contact.efc_address)>=0,'force_contact_N_Nm':force.tolist(),
            'force_world_on_geom2_N':matvec(transpose(frame),force[:3].tolist())})
    def future(value,generation):
        return {'exists':value is not None,'done':bool(value.done()) if value else None,
                'cancelled':bool(value.cancelled()) if value else None,'generation':generation}
    physics_fields=('body_mass','body_inertia','geom_type','geom_size','geom_friction','geom_solref','geom_solimp',
                    'jnt_type','jnt_axis','jnt_range','actuator_gainprm','actuator_biasprm','actuator_ctrlrange','actuator_forcerange')
    physical_configuration={name:getattr(model,name).tolist() for name in physics_fields}
    physical_configuration.update(timestep=float(model.opt.timestep),integrator=int(model.opt.integrator),
                                  gravity=model.opt.gravity.tolist(),zones=zones,
                                  zone_halves={name:list(zone_half(name)) for name in zones})
    clean_physics=_plain(physical_configuration,errors,'physical_configuration')
    snapshot={'schema_version':SCHEMA,'audience':'protected evaluator/operator only','capture_sim_time_s':float(data.time),
        'exposure':copy.deepcopy(exposure),'scene_xml_sha256':hashlib.sha256(cell.xml.encode()).hexdigest(),
        'physical_configuration_sha256':digest(clean_physics),'source_hashes':dict(source_hashes or {}),
        'geometry':geometry,'expected_object_ids':sorted(registry),'object_poses':poses,
        'robot':{'joint_position_rad':data.qpos[:7].tolist(),'joint_velocity_rad_s':data.qvel[:7].tolist(),
                 'finger_position_m':data.qpos[7:9].tolist(),'finger_velocity_m_s':data.qvel[7:9].tolist(),
                 'actuator_effort':data.actuator_force.tolist(),'ctrl':data.ctrl.tolist(),
                 'jaw_width_m':float(sum(data.qpos[7:9])),'tcp_position_world_m':tcp_position,'tcp_rotation_world':tcp_rotation,
                 'joint_ranges_rad':model.jnt_range[:7].tolist()},
        'contacts':{'records':records,'by_object':contact_evidence(records,registry),
                    'distance_tolerance_m':.001,'force_convention':'local first axis normal; frame.T gives force on geom2, negative on geom1'},
        'authority':{'active_request':copy.deepcopy(cell.active_request),'generation':cell.plan_generation,
                     'lease_deadline_sim_s':cell.lease_deadline,'segment':copy.deepcopy(cell.segment),
                     'queued_motion':copy.deepcopy(cell.motion),'direct_command':copy.deepcopy(cell.direct_command),
                     'planner':future(cell.plan_future,cell.pending_plan_generation),
                     'direct_planner':future(cell.direct_plan_future,cell.direct_plan_generation),
                     'setup_wait':copy.deepcopy(cell._setup_wait)},
        'devices':{'station':copy.deepcopy(cell.station),'cycle':copy.deepcopy(cell.cycle),
                   'inspection_due':copy.deepcopy(cell.inspection_due),'last_inspection':copy.deepcopy(cell.inspection)},
        'observation':{'last_capture_sim_time_s':float(cell.detection_time),
                       'last_capture_age_s':float(data.time-cell.detection_time),
                       'sequence':getattr(cell.last_sensor_result,'sequence',None)},
        'infrastructure':copy.deepcopy(infrastructure or {'status':'unknown','reasons':['not supplied by operator']}),
        'capture_errors':errors}
    snapshot['physical_class_observation']=export_observation(
        model,cell.xml,cell.registry,getattr(cell,'restart_physical_seal',None),
        physical_configuration_sha256=snapshot['physical_configuration_sha256'])
    result=_plain(snapshot,errors)
    result['capture_errors']=list(errors)
    result['snapshot_sha256']=digest(result)
    return result


def _predicate(name,state,reason,observed=None,*,domain='physical_state',required=True):
    return {'name':name,'state':state,'reason':reason,'observed':observed,'domain':domain,'required':required}


def _calibration(entry,snapshot,*,qualification=None):
    """Reference syntax/source compatibility only; caller verifies artifact bytes.

    No episode outcome field is read. Final success is not prior calibration.
    """
    if not isinstance(entry,dict):return 'unknown','no measured envelope supplied'
    refs=entry.get('evidence_refs')
    if not isinstance(refs,list) or not refs:return 'unknown','no physical calibration artifact reference'
    if any(not isinstance(r,dict) or r.get('kind')!='prior_physical_calibration' or not isinstance(r.get('artifact_id'),str)
           or not re.fullmatch('[0-9a-fA-F]{64}',str(r.get('sha256',''))) or r.get('bytes_verified_by_operator') is not True for r in refs):
        return 'unknown','evidence references lack explicit prior-calibration identity/hash/operator verification'
    sources=entry.get('source_hashes',{})
    if not sources or any(snapshot.get('source_hashes',{}).get(k)!=v for k,v in sources.items()):
        return 'unknown','calibration source identity is missing or differs from this incarnation'
    if entry.get('envelope_basis')!='measured_before_this_intervention':return 'unknown','envelope must predate the intervention'
    mode=entry.get('match_mode','exact_configuration')
    if mode=='qualified_class':
        assessment=qualified_entry_identity(entry,snapshot,qualification)
        return assessment['state'],assessment['reason']
    if mode!='exact_configuration':return 'unknown','unsupported physical matching mode'
    if entry.get('physical_configuration_sha256')!=snapshot.get('physical_configuration_sha256'):
        return 'unknown','calibration physical configuration is not matched'
    if entry.get('envelope_basis')!='measured_before_this_intervention':return 'unknown','envelope must predate the intervention'
    return 'pass','operator supplied matched prior physical calibration references; artifact bytes are not re-read here'


def _grip(entry,snapshot,obj,policy,*,qualification=None):
    state,reason=_calibration(entry,snapshot,qualification=qualification)
    if state!='pass':return state,reason,None
    envelope=entry.get('envelope',{});identity=obj['id'];robot=snapshot['robot'];contact=snapshot['contacts']['by_object'][identity]
    pose=snapshot['object_poses'][identity]['relative_to_tcp']
    if not vector(pose.get('position_m')) or not proper_rotation(pose.get('rotation')):
        return 'unknown','actual payload-relative pose is incomplete or invalid',None
    required=('jaw_width_m','relative_position_m','relative_rotation','maximum_rotation_error_rad','finger_normal_force_N',
              'maximum_linear_speed_m_s','maximum_angular_speed_rad_s','minimum_payload_bottom_z_m','kind','family')
    if any(k not in envelope for k in required):return 'unknown','grip envelope is incomplete',None
    pair=envelope['jaw_width_m'];forces=envelope['finger_normal_force_N'];rotation=envelope['relative_rotation']
    if (not vector(pair,2) or not pair[0]<pair[1] or not vector(forces,2) or not 0<forces[0]<forces[1]
            or not valid_box(envelope['relative_position_m']) or not proper_rotation(rotation)
            or any(not number(envelope[k]) or envelope[k]<0 for k in ('maximum_rotation_error_rad','maximum_linear_speed_m_s','maximum_angular_speed_rad_s','minimum_payload_bottom_z_m'))):
        return 'unknown','grip envelope numerical fields are malformed',None
    relative=matmul(transpose(rotation),pose['rotation']);angle=math.acos(max(-1.,min(1.,(sum(relative[i][i] for i in range(3))-1.)/2)))
    checks={'kind':obj['kind']==envelope['kind'],'family':obj['family']==envelope['family'],
            'jaw_width':pair[0]<=robot['jaw_width_m']<=pair[1],
            'position':inside(pose['position_m'],envelope['relative_position_m']),
            'rotation':angle<=envelope['maximum_rotation_error_rad'],
            'left_load':forces[0]<=contact['left_normal_force_N']<=forces[1],
            'right_load':forces[0]<=contact['right_normal_force_N']<=forces[1],
            'linear_speed':norm(obj['linear_velocity'])<=envelope['maximum_linear_speed_m_s'],
            'angular_speed':norm(obj['angular_velocity'])<=envelope['maximum_angular_speed_rad_s'],
            'clearance':obj['bounds']['min'][2]>=envelope['minimum_payload_bottom_z_m']}
    return ('pass' if all(checks.values()) else 'fail'),'actual grip compared with supplied measured envelope',{'checks':checks,'rotation_error_rad':angle}


def _route(entries,snapshot,obj,available,*,qualification=None,grip_entry=None):
    if not isinstance(entries,list) or not entries:return 'unknown','no measured recovery route envelope supplied',[]
    reports=[]
    for entry in entries:
        if isinstance(entry,dict) and entry.get('match_mode')=='qualified_class' and (
                not isinstance(grip_entry,dict) or grip_entry.get('match_mode')!='qualified_class'
                or entry.get('qualification_cell_id')!=grip_entry.get('qualification_cell_id')):
            reports.append({'state':'unknown','reason':'grip and route must use the same measured transfer cell'});continue
        state,reason=_calibration(entry,snapshot,qualification=qualification)
        if state!='pass':reports.append({'state':state,'reason':reason});continue
        e=entry.get('envelope',{});destination=e.get('destination');robot=snapshot['robot'];region=snapshot['geometry']['zones'].get(destination)
        ranges=e.get('joint_start_ranges_rad');velocities=e.get('joint_velocity_ranges_rad_s');corridors=e.get('clearance_corridors_m')
        if (e.get('operation')!='recover_held' or not valid_box(e.get('tcp_start_m')) or not valid_box(e.get('destination_region_m'))
                or not isinstance(ranges,list) or len(ranges)!=7 or any(not vector(r,2) or r[0]>r[1] for r in ranges)
                or not isinstance(velocities,list) or len(velocities)!=7 or any(not vector(r,2) or r[0]>r[1] for r in velocities)
                or not number(e.get('maximum_abs_finger_velocity_m_s')) or e['maximum_abs_finger_velocity_m_s']<0
                or not isinstance(corridors,list) or not corridors or any(not valid_box(b) for b in corridors)
                or e.get('payload_kind') is None or e.get('payload_family') is None):
            reports.append({'state':'unknown','reason':'route envelope is incomplete or malformed','destination':destination});continue
        blockers=[]
        for other in snapshot['geometry']['objects']:
            if other['id']==obj['id']:continue
            bounds=other['bounds']
            if valid_box(bounds) and any(
                    all(min(bounds['max'][i],box['max'][i])-max(bounds['min'][i],box['min'][i])>1e-6
                        for i in range(3)) for box in corridors):
                blockers.append(other['id'])
        blockers.sort()
        checks={'free_destination':destination in available,'same_destination_region':region==e['destination_region_m'],
                'tcp_start':inside(robot['tcp_position_world_m'],e['tcp_start_m']),
                'joint_start':all(lo<=v<=hi for (lo,hi),v in zip(ranges,robot['joint_position_rad'])),
                'joint_velocity':all(lo<=v<=hi for (lo,hi),v in zip(velocities,robot['joint_velocity_rad_s'])),
                'finger_velocity':all(abs(v)<=e['maximum_abs_finger_velocity_m_s'] for v in robot['finger_velocity_m_s']),
                'payload_kind':obj['kind']==e['payload_kind'],'payload_family':obj['family']==e['payload_family'],
                'corridors_clear_of_other_movable_bodies':not blockers}
        reports.append({'state':'pass' if all(checks.values()) else 'fail','destination':destination,'checks':checks,'blocker_ids':blockers,
                        'scope':'supplied measured envelope only; this does not compute a new collision-free arm path'})
    if any(r['state']=='pass' for r in reports):return 'pass','at least one supplied calibrated route envelope matches',reports
    if any(r['state']=='unknown' for r in reports):return 'unknown','no matching route proven; some calibration evidence is unknown',reports
    return 'fail','state lies outside every supplied calibrated route envelope',reports


def classify_restart(snapshot,*,calibration=None,policy=None,qualification_context=None):
    """Return inspectable three-valued predicates, never an experiment outcome.

    Aggregate: any required fail -> inadmissible; otherwise any required unknown
    -> unknown; otherwise admissible *within supplied envelopes*. The exposure's
    configured_milestone_exercised is copied, not inferred from this result.
    """
    calibration=calibration or {};rules={**DEFAULT_POLICY,**(policy or {})};predicates=[]
    def add(name,state,reason,observed=None,**kw):predicates.append(_predicate(name,state,reason,observed,**kw))
    def test(name,condition,reason,observed=None,**kw):add(name,'pass' if condition else 'fail',reason,observed,**kw)
    exposure=snapshot.get('exposure',{});phase=exposure.get('actual_cut')
    infrastructure=snapshot.get('infrastructure',{'status':'unknown'})
    add('infrastructure_evidence',{'valid':'pass','invalid':'fail'}.get(infrastructure.get('status'),'unknown'),
        'operator-supplied infrastructure assessment, never inferred from task state',infrastructure,domain='infrastructure',required=False)
    try:
        geometry=snapshot['geometry'];objects=geometry['objects'];robot=snapshot['robot'];authority=snapshot['authority']
        contacts=snapshot['contacts']['by_object'];devices=snapshot['devices'];now=snapshot['capture_sim_time_s']
        numeric=[now,robot['jaw_width_m'],*robot['joint_position_rad'],*robot['joint_velocity_rad_s'],
                 *robot['tcp_position_world_m'],*robot['finger_position_m'],*robot['finger_velocity_m_s'],*robot['ctrl']]
        for obj in objects:numeric.extend(obj['position']+obj['bounds']['min']+obj['bounds']['max']+obj['linear_velocity']+obj['angular_velocity'])
        for c in contacts.values():numeric.extend(c[k] for k in ('left_normal_force_N','right_normal_force_N','support_upward_force_N'))
        finite=all(number(v) for v in numeric) and not snapshot.get('capture_errors') and all(
            vector(robot.get(key),n) for key,n in (('joint_position_rad',7),('joint_velocity_rad_s',7),('finger_position_m',2),('finger_velocity_m_s',2),('tcp_position_world_m',3),('ctrl',8)))
        test('finite_snapshot',finite,'nonfinite or incompletely captured state cannot support an intervention',snapshot.get('capture_errors'))
        if not finite:raise ValueError('further numerical predicates unavailable after invalid capture')
        ids=[o['id'] for o in objects]
        test('object_identity_integrity',len(set(ids))==len(ids) and sorted(ids)==snapshot['expected_object_ids'],'all expected registered bodies remain represented',ids)
        escaped=[o['id'] for o in objects if not contained(o['bounds'],rules['table_envelope'])]
        test('objects_in_declared_envelope',not escaped,'full movable collision bounds must remain in the declared workcell volume',escaped)
        test('robot_configuration',proper_rotation(robot['tcp_rotation_world']) and len(robot['joint_ranges_rad'])==7 and all(lo<=q<=hi for (lo,hi),q in zip(robot['joint_ranges_rad'],robot['joint_position_rad'])),
             'finite current arm joints within native joint range and valid TCP rotation')
        records=snapshot['contacts']['records']
        invalid_contact=[r['index'] for r in records if not number(r.get('distance_m')) or (r['constraint_active'] and r['distance_m'] < -rules['maximum_contact_penetration_m'])]
        test('contact_penetration',not invalid_contact,'exact active contact penetration is bounded; AABB intersection alone is not proof of collision',invalid_contact)
        phase_known=phase in PHASES
        add('supported_actual_cut','pass' if phase_known else 'unknown','fallback/unsupported phase is retained without inventing a recovery class',phase)
        active=authority.get('active_request');generation=authority.get('generation')
        ownership=isinstance(generation,int) and not isinstance(generation,bool)
        if active is not None:ownership=ownership and isinstance(active.get('request_id'),str) and bool(active['request_id']) and isinstance(active.get('incarnation'),int) and isinstance(active.get('order_version'),int)
        mismatches=[k for k in ('planner','direct_planner') if authority[k]['exists'] and authority[k].get('generation')!=generation]
        if mismatches:add('action_generation_ownership','unknown','outstanding planner generation is stale; exact post-cut fencing must be established',mismatches)
        else:test('action_generation_ownership',ownership,'active request and pending planner ownership must be identifiable')
        if phase_known:
            observed_phase=(authority.get('segment') or {}).get('phase')
            expected_phases={'closed_grip_transfer':(4,5),'after_release':(7,),'before_outcome':(9,)}
            phase_ok=active is not None and active.get('operation')=='transport'
            if phase in expected_phases:phase_ok=phase_ok and observed_phase in expected_phases[phase]
            if exposure.get('active_request_id') is not None:phase_ok=phase_ok and (active or {}).get('request_id')==exposure['active_request_id']
            test('phase_matches_current_action',phase_ok,'declared cut must match the captured active action and segment',observed_phase)
        deadline=authority.get('lease_deadline_sim_s')
        add('current_action_lease','pass' if active is None or (number(deadline) and deadline>=now) else 'unknown',
            'an expired/unrecorded lease needs an explicit cancellation-state interpretation',deadline)
        active_cycle=devices['cycle'] is not None;inspection=devices['inspection_due'] is not None;station=devices['station']
        if station.get('fault') is True:test('station_safe_state',False,'station fault is a physical task state; cause is not inferred')
        elif active_cycle or inspection or station.get('busy') or station.get('clamped') or station.get('guard_closed'):
            add('station_safe_state','unknown','device/timer survival across this cut needs a separately declared and measured rule',devices)
        else:test('station_safe_state',station.get('ready') is True and station.get('fault') is False,'supported idle ready device state')
        age=snapshot['observation'].get('last_capture_age_s')
        add('fresh_public_capture','pass' if number(age) and 0<=age<=rules['maximum_capture_age_s'] else 'unknown',
            'fresh overhead is needed for immediate shared recovery; a stale/missing image may be reacquired',age)
        touched=[identity for identity,c in contacts.items() if c['hand_contact']]
        force_held=[identity for identity,c in contacts.items() if c['bilateral_force_bearing']]
        unresting=[o['id'] for o in objects if o['id'] not in touched and (
            o['bounds']['max'][2]>rules['unheld_scoring_rim_z_m'] or norm(o['linear_velocity'])>rules['linear_rest_m_s']
            or norm(o['angular_velocity'])>rules['angular_rest_rad_s'] or contacts[o['id']]['support_upward_force_N']<rules['support_upward_force_N'])]
        test('unheld_bodies_supported_and_slow',not unresting,'other movable bodies must be supported within the rest-height and speed envelope',unresting)
        available=[];occupancy={}
        for name in rules['recovery_destinations']:
            region=geometry['zones'].get(name)
            if region is None:continue
            occupants=[o['id'] for o in objects if overlaps(o['bounds'],region)]
            occupancy[name]=occupants
            if not occupants:available.append(name)
        test('finite_buffer_capacity',not any(len(ids)>1 for ids in occupancy.values()),'declared pads have capacity one; resource difficulty is not assigned an infrastructure cause',occupancy,domain='task_resource')
        add('recovery_buffer_inventory','pass' if available else 'fail','free finite buffer is a necessary resource only; it proves no safe route',
            {'available':available,'occupancy':occupancy},domain='task_resource',required=phase=='closed_grip_transfer')
        obj=None
        if phase=='closed_grip_transfer':
            contact_ok=len(touched)==1 and touched==force_held and next((o['kind']=='part' for o in objects if o['id']==touched[0]),False)
            test('phase_contact_consistency',contact_ok and rules['empty_close_width_m']<robot['jaw_width_m']<rules['open_width_m'] and robot['ctrl'][7]==0,
                 'carry requires one force-bearing bilateral workpiece grip and a closing command',{'hand_contact_ids':touched,'bilateral_ids':force_held,'jaw_width_m':robot['jaw_width_m']})
            if contact_ok:
                obj=next(o for o in objects if o['id']==touched[0]);state,reason,evidence=_grip(calibration.get('grip'),snapshot,obj,rules,qualification=qualification_context)
                add('measured_grip_envelope',state,reason,evidence)
                state,reason,evidence=_route(calibration.get('routes'),snapshot,obj,available,qualification=qualification_context,grip_entry=calibration.get('grip'))
                add('measured_recovery_route',state,reason,evidence)
            else:
                add('measured_grip_envelope','unknown','no unambiguous carried workpiece to match')
                add('measured_recovery_route','unknown','no unambiguous carried workpiece to match')
        elif phase in ('after_acceptance','after_release','before_outcome'):
            test('phase_contact_consistency',not touched and robot['jaw_width_m']>=rules['open_width_m'],
                 'this empty/released class requires open jaws and no registered body hand contact',{'hand_contact_ids':touched,'jaw_width_m':robot['jaw_width_m']})
            part_id=(active or {}).get('part_id') or exposure.get('part_id')
            obj=next((o for o in objects if o['id']==part_id),None)
            if obj is None:add('supported_target_part','unknown','cut record lacks the target workpiece identity; later success cannot reconstruct this capture')
            else:
                c=contacts[obj['id']]
                test('supported_target_part',c['support_upward_force_N']>=rules['support_upward_force_N'] and norm(obj['linear_velocity'])<=rules['linear_rest_m_s'] and norm(obj['angular_velocity'])<=rules['angular_rest_rad_s'],
                     'actual upward nonhand contact support and bounded part velocities',c)
                if phase!='after_acceptance':
                    destination=(active or {}).get('destination') or exposure.get('destination');region=geometry['zones'].get(destination)
                    add('released_destination_containment','unknown' if region is None else ('pass' if contained(obj['bounds'],region) else 'fail'),
                        'full payload collision bounds must be inside its recorded destination',destination)
                elif c['support_upward_force_N']>=rules['support_upward_force_N']:
                    # A supported part in a known pad/tray/fixture or in the raw
                    # table area is a reconstructible physical source. No old
                    # private action history is injected into the candidate.
                    full=[name for name,region in geometry['zones'].items() if contained(obj['bounds'],region)]
                    touches=[name for name,region in geometry['zones'].items() if overlaps(obj['bounds'],region)]
                    test('source_region_consistency',bool(full) or not touches,'source is fully inside a declared region or clear of all region boundaries',{'contained':full,'touched':touches})
        if snapshot.get('schema_version')!=SCHEMA:add('schema_identity','unknown','snapshot schema is not this helper version')
    except (KeyError,TypeError,ValueError,IndexError,StopIteration) as error:
        add('capture_completeness','unknown','required protected evidence unavailable: '+str(error))
    required=[p for p in predicates if p['required']]
    overall='inadmissible' if any(p['state']=='fail' for p in required) else ('unknown' if any(p['state']=='unknown' for p in required) else 'admissible')
    transfer_entries=[calibration.get('grip')]+(calibration.get('routes') if isinstance(calibration.get('routes'),list) else [])
    transfer_reports=[qualified_entry_identity(entry,snapshot,qualification_context) for entry in transfer_entries
                      if isinstance(entry,dict) and entry.get('match_mode')=='qualified_class']
    try:calibration_hash=digest(calibration)
    except (TypeError,ValueError):calibration_hash=None
    return {'schema_version':CLASSIFIER,'audience':'protected evaluator/operator only','state':overall,
            'configured_phase_reached':exposure.get('configured_milestone_exercised'),
            'configured_cut':exposure.get('configured_cut'),'actual_cut':phase,'fallback_used':exposure.get('fallback_used'),
            'snapshot_sha256':snapshot.get('snapshot_sha256'),'predicates':predicates,'policy':rules,
            'calibration_input_sha256':calibration_hash,'infrastructure':infrastructure,
            'qualified_class_evidence':transfer_reports,
            'causal_attribution':'not inferred; candidate-induced resource difficulty is not automatically infrastructure invalid',
            'scope':'instantaneous protected evidence and explicitly supplied prior measured envelopes; no guarantee of future recovery',
            'effects':{'cut_selected':False,'candidate_information_added':False,'episode_outcome_assigned':False,'paired_block_excluded':False}}
