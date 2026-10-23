"""Read-only, non-authorizing assessment of a fixed rule and completed screen.

No simulator, cells fitted from validation, corridor expansion or readiness grant.
The CLI requires the shared queue; unit tests call pure helpers on synthetic data.
"""
from __future__ import annotations

import argparse
import ast
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import zipfile

from bundle_construction import RICH_LANDMARKS, validate_provisional_rule
from compatibility import digest, finite

HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parent / 'Recovery Qualification'
spec = importlib.util.spec_from_file_location('_completed_screen_reader', FIXTURE / 'extract_screen.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
require, stamp = reader.require, reader.stamp
SOURCE_KEYS = ('cell.py', 'actuation.py', 'evaluator.py', 'sensor_worker.py')
POINT_KEYS = ('snapshot_sha256', 'physical_configuration_sha256', 'physical_class_observation_sha256')
LIMITS = [
    'Finite declared development worlds only; no qualification or readiness is granted.',
    'Dense boxes cover native evaluated discrete states, with the recorded one-step cached-transform alignment limitation.',
    'Box unions are used exactly as declared: no padding, continuous sweep bound or inferred transfer margin.',
    'Every-tick hold evidence is hand contact and center height >0.075 m; bilateral force and relative pose are landmark observations only.',
    'Independent placement dwell is the unchanged fixture predicate, not a new performance or duration guarantee.',
]


def result(checks, **facts):
    """A false observation dominates unknown; no truthiness-based acceptance."""
    return {'state': 'fail' if any(v is False for v in checks.values()) else
            'unknown' if any(v is None for v in checks.values()) else 'pass', 'checks': checks, **facts}


def flag(value):
    return value if type(value) is bool else None


def all_states(values):
    return 'fail' if 'fail' in values else 'unknown' if any(v != 'pass' for v in values) else 'pass'


def valid_box(box):
    return (isinstance(box, dict) and all(isinstance(box.get(k), list) and len(box[k]) == 3
            and all(finite(v) for v in box[k]) for k in ('min', 'max'))
            and all(a < b for a, b in zip(box['min'], box['max'])))


def box_union_contains(box, corridors):
    """Exact axis-aligned set subtraction. No added epsilon or outer-hull shortcut."""
    require(valid_box(box) and isinstance(corridors, list) and corridors
            and all(valid_box(b) for b in corridors), 'Invalid measured box/corridor')
    remaining = [copy.deepcopy(box)]
    for cover in corridors:
        next_pieces = []
        for piece in remaining:
            low = [max(piece['min'][i], cover['min'][i]) for i in range(3)]
            high = [min(piece['max'][i], cover['max'][i]) for i in range(3)]
            if any(a >= b for a, b in zip(low, high)):
                next_pieces.append(piece); continue
            core = copy.deepcopy(piece)
            for axis in range(3):
                if core['min'][axis] < low[axis]:
                    slab = copy.deepcopy(core); slab['max'][axis] = low[axis]; next_pieces.append(slab)
                    core['min'][axis] = low[axis]
                if core['max'][axis] > high[axis]:
                    slab = copy.deepcopy(core); slab['min'][axis] = high[axis]; next_pieces.append(slab)
                    core['max'][axis] = high[axis]
        remaining = next_pieces
        require(len(remaining) <= 20000, 'Corridor subtraction resource cap; containment unknown')
        if not remaining:
            break
    return {'state': 'fail' if remaining else 'pass', 'uncovered_piece_count': len(remaining),
            'first_uncovered_box': remaining[0] if remaining else None, 'added_padding_m': 0.}


def numeric_functions(source, fixture_source=None):
    """Reuse archived numerical code verbatim, removing only final-bundle gates.

    This adapter cannot call classify_restart or grant authorization. An exact
    AST match makes a changed calibration gate unsupported rather than guessed.
    """
    tree = ast.parse(source)
    names = {'number', 'vector', 'norm', 'transpose', 'matvec', 'matmul', 'proper_rotation',
             'inside', 'valid_box', 'contained', 'overlaps', '_grip', '_route'}
    functions = {n.name: copy.deepcopy(n) for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names}
    require(set(functions) == names, 'Archived numerical function inventory changed')
    assignment = ast.parse('state,reason=_calibration(entry,snapshot,qualification=qualification)').body[0]
    gates = {'_grip': ast.parse("if state!='pass':return state,reason,None").body[0],
             '_route': ast.parse("if state!='pass':reports.append({'state':state,'reason':reason});continue").body[0]}
    for name in ('_grip', '_route'):
        function = functions[name]
        body = function.body if name == '_grip' else next(n.body for n in function.body if isinstance(n, ast.For))
        matches = [i for i in range(len(body)-1) if ast.dump(body[i]) == ast.dump(assignment)
                   and ast.dump(body[i+1]) == ast.dump(gates[name])]
        require(len(matches) == 1, 'Archived calibration gate shape changed: ' + name)
        del body[matches[0]:matches[0]+2]
    policy = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'DEFAULT_POLICY' for t in n.targets))
    namespace = {'math': math}
    exec(compile(ast.fix_missing_locations(ast.Module(body=list(functions.values()), type_ignores=[])),
                 '<source-pinned numeric-only adapter>', 'exec'), namespace)
    namespace['policy'] = policy
    if fixture_source is not None:
        predicates = [copy.deepcopy(n) for n in ast.parse(fixture_source).body if isinstance(n,ast.FunctionDef)
                      and n.name in ('retained_hold_check','cut_eligible')]
        require({n.name for n in predicates}=={'retained_hold_check','cut_eligible'}, 'Archived fixture predicates unavailable')
        exec(compile(ast.fix_missing_locations(ast.Module(body=predicates,type_ignores=[])),
                     '<source-pinned fixture predicates>','exec'),namespace)
    return namespace


def successful_receipt(receipt, job, completed_at):
    require(receipt.get('state') == 'succeeded' and type(receipt.get('exit_status')) is int
            and receipt['exit_status'] == 0, 'Successful official receipt required')
    require(isinstance(job, dict) and all(k in job and k in receipt and receipt[k] == job[k]
            for k in reader.IDENTITY), 'Official receipt does not identify recorded job')
    require(stamp(receipt['started_at']) <= stamp(completed_at) <= stamp(receipt['ended_at']),
            'Completion not covered by official receipt')


def source_value(hashes, relative):
    relative = relative.replace('\\', '/').lower()
    values = [value for name, value in hashes.items() if name.replace('\\', '/').lower().endswith('/' + relative)]
    require(len(values) == 1, 'Missing/ambiguous archived source: ' + relative)
    return values[0]


class BoundEvidence(reader.Evidence):
    def __init__(self, root):
        self.consumed = {}
        super().__init__(root)

    def remember(self, path, before, digest, size, name):
        ref = super().remember(path, before, digest, size, name)
        self.consumed[path] = {**ref, 'path':str(path)}
        return ref


class CompletedExtraction:
    """Rebind consumed derived bytes to indexed raw screen and successful receipt."""
    def __init__(self, path, screen_receipt, extraction_receipt=None):
        self.path = Path(path).resolve(); self.base = self.path.parent
        initial = json.loads(self.path.read_bytes())
        # Refuse active inputs before opening the source screen.
        terminal = json.loads(Path(screen_receipt).read_bytes())
        require(terminal.get('state') == 'succeeded' and terminal.get('exit_status') == 0,
                'Successful official screen receipt required before reading screen')
        self.evidence = BoundEvidence(initial['source_screen'])
        self.data, self.ref = self.evidence.external(self.path)
        require(self.data == initial and self.data.get('schema_version') == 'recovery-screen-extraction-1',
                'Extraction identity/schema changed')
        self.receipt, self.receipt_ref = self.evidence.external(screen_receipt)
        self.manifest, self.manifest_ref = self.evidence.json('manifest.json')
        self.summary, self.summary_ref = self.evidence.json('summary.json')
        require(self.manifest.get('schema_version') == self.summary.get('schema_version') == reader.SCHEMA,
                'Unknown raw screen schema')
        successful_receipt(self.receipt, self.manifest['queue']['queue_job'], self.summary['finished_at'])
        require(self.receipt['id'] == self.manifest['queue']['job_id'] == self.summary['queue_job_id'], 'Screen queue identity differs')
        require(self.data['source_receipt'] == self.receipt and self.data['source_summary'] == self.summary,
                'Extraction source receipt/summary differs')
        for name, ref in (('receipt_ref', self.receipt_ref), ('manifest_ref', self.manifest_ref),
                          ('summary_ref', self.summary_ref), ('evidence_index_ref', self.evidence.index_ref)):
            require(self.data[name]['sha256'] == ref['sha256'], 'Extraction source reference differs: ' + name)
        require(stamp(self.receipt['ended_at']) <= stamp(self.data['completed_at']), 'Extraction predates completed screen')
        self.extraction_receipt_ref = None
        if extraction_receipt:
            receipt, self.extraction_receipt_ref = self.evidence.external(extraction_receipt)
            successful_receipt(receipt, self.data.get('extraction_queue'), self.data['completed_at'])
        self.plan = self.manifest['prospective_plan']
        self.declared = {t['id']: t for t in self.plan['trials']}
        require(len(self.declared) == len(self.plan['trials']), 'Duplicate declared trial ID')
        self.entries = {e['trial_id']: e for e in self.data['trials']}
        require(len(self.entries) == len(self.data['trials']) and list(self.entries) == list(self.declared),
                'Extraction must retain every declared ID in order')
        phase = self.manifest['execution_phase']; destination = self.manifest['destination_selection']
        require(phase in ('construction', 'validation'), 'Explicit execution phase required')
        fixture = 'construction' if phase == 'construction' else 'independent_generator'
        self.selected = [t['id'] for t in self.plan['trials'] if (destination == 'all' or t['destination'] == destination)
                         and t['fixture'] == fixture]
        require(self.manifest['modes'] == self.selected, 'Declared selection differs')
        self.deferred = [t['id'] for t in self.plan['trials'] if t['id'] not in self.selected
                         and (destination == 'all' or t['destination'] == destination)]
        require(self.deferred == self.manifest['phase_deferred_trial_ids'] == self.summary['phase_deferred_trial_ids'],
                'Deferred phase coverage differs')
        self.attempts = {a['trial_id']: a for a in self.summary['attempts']}
        require(len(self.attempts) == len(self.summary['attempts']) and list(self.attempts) == self.selected[:len(self.attempts)]
                and self.summary['not_started'] == self.selected[len(self.attempts):], 'Selected terminal coverage differs')
        archive = self.evidence.stream('source-bundle.zip')
        require(archive['sha256'] == self.manifest['source_bundle_sha256'] == self.data['source_bundle_ref']['sha256'],
                'Source archive identity differs')
        self.archive = self.evidence.path('source-bundle.zip')
        # Every archived source/asset is checked against the held manifest,
        # without importing any simulator or inspecting current mutable Runtime.
        with zipfile.ZipFile(self.archive) as bundle:
            names = bundle.namelist()
            require(len(names) == len(set(names)), 'Duplicate source archive member')
            for source, expected in self.manifest['source_hashes'].items():
                normalized = source.replace('\\','/').lower()
                matches = [name for name in names if normalized.endswith('/'+name.lower())]
                require(len(matches)==1, 'Missing/ambiguous retained source: '+source)
                with bundle.open(matches[0]) as stream:
                    require(hashlib.file_digest(stream,'sha256').hexdigest()==expected, 'Retained source bytes differ: '+source)
        require(self.data['extractor_sha256'] == source_value(self.manifest['source_hashes'],
                'Batch 01/Recovery Qualification/extract_screen.py'), 'Extractor source differs from archived version')
        require(self.data['extractor_sha256'] == hashlib.sha256(Path(reader.__file__).read_bytes()).hexdigest(),
                'Current read-only extraction verifier differs from retained extractor')
        self.cache = {}

    def extracted(self, name):
        path = (self.base / str(reader.safe_relative(name))).resolve()
        require(self.base in path.parents, 'Extracted path escapes output')
        return self.evidence.external(path)

    def source(self, relative):
        with zipfile.ZipFile(self.archive) as archive:
            raw = archive.read(relative)
        identity = hashlib.sha256(raw).hexdigest()
        require(identity == source_value(self.manifest['source_hashes'], relative), 'Archived source digest differs: ' + relative)
        return raw.decode('utf-8-sig'), {'archive': str(self.archive), 'member': relative, 'sha256': identity}

    def trial(self, identity):
        if identity in self.cache:
            return self.cache[identity]
        entry = self.entries[identity]; row, ref = self.extracted(entry['path'])
        attempt = self.attempts.get(identity)
        status = ('deferred_to_other_phase' if identity in self.deferred else
                  'not_selected_for_this_screen' if identity not in self.selected else
                  'not_started' if attempt is None else attempt['status'])
        require(row['trial_id'] == identity and row['declaration'] == self.declared[identity]
                and row['execution_status'] == entry['execution_status'] == status and row['parent_attempt'] == attempt,
                'Extracted declaration/status/attempt differs: ' + identity)
        for filename, field in (('probe-manifest.json','probe_manifest'), ('result.json','child_result'),
                ('construction.json','construction'), ('compiled-properties.json','compiled_properties'),
                ('protected-class-spec.json','protected_class_spec'), ('dense-geometry-summary.json','dense_geometry_summary')):
            name = identity + '/' + filename
            if name in self.evidence.entries:
                raw, raw_ref = self.evidence.json(name)
                require(row.get(field) == raw and row['artifact_refs'][filename] == raw_ref, 'Extracted/raw artifact differs: ' + name)
            else:
                require(row.get(field) is None and filename not in row.get('artifact_refs',{}),
                        'Derived artifact has no indexed raw source: '+name)
        child = row.get('child_result')
        if child:
            if child.get('status')=='passed':
                require(all(identity+'/'+name in self.evidence.entries for name in ('result.json','probe-manifest.json')),
                        'Passed child lacks indexed result/probe identity')
            require(child['trial_id'] == identity and child['trial'] == self.declared[identity], 'Child declaration differs')
            if attempt and attempt.get('result_path'):
                require(attempt['result_path'] == identity + '/result.json'
                        and attempt['result_sha256'] == row['artifact_refs']['result.json']['sha256']
                        and attempt['status'] == child['status'], 'Parent/child result identity differs')
            require(child['source_hashes_before'] == child['source_hashes_after'] == self.manifest['source_hashes']
                    and child.get('sources_unchanged') is True, 'Child source hold differs')
        probe = row.get('probe_manifest')
        if probe:
            require(probe['trial'] == self.declared[identity] and probe['parent_manifest_sha256'] == self.manifest_ref['sha256']
                    and probe['source_hashes'] == self.manifest['source_hashes']
                    and probe['prospective_plan_sha256'] == digest(self.plan), 'Child/parent manifest source binding differs')
            chain = probe.get('queue',{}); parent = self.manifest['queue']
            pids = [chain.get(key) for key in ('probe_pid','probe_launcher_pid','driver_pid')]
            times = [stamp(value) for value in chain.get('process_creation_times',[])]
            require(chain.get('job_id') == parent['job_id'] and chain.get('driver_pid') == parent.get('pid')
                    and all(type(pid) is int and pid>0 for pid in pids) and len(set(pids))==3
                    and len(times)==4 and times==sorted(times) and times[0]==stamp(self.receipt['started_at'])
                    and times[1]==stamp(parent['driver_metadata']['created_at']), 'Retained child/queue chain attestation differs')
        states = {'states': {}, 'unparsed_records': []}
        if row.get('measured_states', {}).get('output_path'):
            states, states_ref = self.extracted(row['measured_states']['output_path'])
            raw_states = reader.event_states(self.evidence, identity + '/events.jsonl')
            require(states == raw_states, 'Extracted landmark/raw event differs: ' + identity)
            row = {**row, 'measured_states_consumed_ref': states_ref}
            for label in RICH_LANDMARKS:
                state = states['states'].get(label, {})
                if state.get('status') != 'recorded':
                    continue
                snapshot = state['payload']
                require(snapshot.get('snapshot_sha256') == digest({k:v for k,v in snapshot.items() if k != 'snapshot_sha256'}),
                        'Snapshot canonical identity differs')
                expected = {key:source_value(self.manifest['source_hashes'], 'Runtime/' + key) for key in SOURCE_KEYS}
                require(snapshot.get('source_hashes') == expected, 'Snapshot four physical sources differ')
                observation = snapshot.get('physical_class_observation', {})
                require(snapshot.get('physical_configuration_sha256') == observation.get('physical_configuration_sha256'),
                        'Snapshot/class exact configuration identity differs')
                if observation.get('export_state') == 'pass':
                    observed_sources = observation.get('source_hashes',{})
                    required_sources = {**expected, **{key:source_value(self.manifest['source_hashes'],'Runtime/'+key)
                        for key in ('restart_state.py','restart_compatibility.py','restart_qualification.py')},
                        'descriptor_exporter':source_value(self.manifest['source_hashes'],'Runtime/restart_physical_class.py')}
                    require(all(observed_sources.get(key)==value for key,value in required_sources.items()),
                            'Compiled observation protected sources differ')
                    xml_ref = self.evidence.stream(identity + '/world-0.xml')
                    # Windows write_text translates line endings; preserve raw
                    # bytes in the ref and match the in-memory XML text digest.
                    xml_text_sha = hashlib.sha256(self.evidence.path(identity+'/world-0.xml').read_text(encoding='utf-8').encode()).hexdigest()
                    require(observation.get('scene_xml_sha256') == snapshot.get('scene_xml_sha256')
                            and observation['scene_xml_sha256'] in (xml_ref['sha256'],xml_text_sha),
                            'Compiled scene/raw XML identity differs')
        row = {**row, 'consumed_ref': ref, 'states': states['states'], 'unparsed_events': states['unparsed_records']}
        self.cache[identity] = row
        return row


def numeric_membership(rule, spec, snapshot, functions):
    try:
        contacts = snapshot['contacts']['by_object']
        require(not snapshot.get('capture_errors'), 'Protected capture reported incomplete/nonfinite evidence')
        touched = [k for k,v in contacts.items() if v['hand_contact']]
        held = [k for k,v in contacts.items() if v['bilateral_force_bearing']]
        require(len(touched) == 1 and touched == held, 'No unique bilateral payload')
        objects = snapshot['geometry']['objects']; obj = next(o for o in objects if o['id'] == held[0])
        template = obj['kind'] + ':' + obj['family']
        cell_id = rule['payload_template_to_cell'].get(template)
        require(cell_id is not None, 'Payload has no fixed mapped cell')
        cell = next(c for c in rule['cells'] if c['cell_id'] == cell_id)
        observation = snapshot['physical_class_observation']
        require(observation.get('export_state') == 'pass', 'Class export unavailable; in-domain selection unsupported')
        identities = [o['id'] for o in objects]
        require(len(set(identities))==len(identities) and sorted(identities)==sorted(o['id'] for o in observation['objects'])
                and all(valid_box(o['bounds']) for o in objects), 'Protected object inventory/bounds incomplete')
        rows = [o for o in observation['objects'] if o['id'] == obj['id']]
        require(len(rows) == 1 and rows[0]['kind'] == obj['kind'] and rows[0]['family'] == obj['family']
                and rows[0]['template_sha256'] == cell['payload_template_sha256'] == digest(spec['templates'][template]),
                'Payload/class/mapped cell template differs')
        robot = snapshot['robot']
        require(all(functions['vector'](robot[k], n) for k,n in (('joint_position_rad',7),
                ('joint_velocity_rad_s',7),('finger_velocity_m_s',2))), 'Incomplete joint/finger vector')
        available = [name for name in functions['policy']['recovery_destinations']
                     if name in snapshot['geometry']['zones'] and not any(functions['overlaps'](o['bounds'],
                     snapshot['geometry']['zones'][name]) for o in objects)]
        grip = functions['_grip']({'envelope':cell['grip_envelope']}, snapshot, obj, functions['policy'])
        route = functions['_route']([{'envelope':cell['route_envelope']}], snapshot, obj, available)
        return {'state':all_states([grip[0],route[0]]), 'cell_id':cell_id,'payload_id':obj['id'], 'template':template,
                'grip':{'state':grip[0],'reason':grip[1],'observed':grip[2]},
                'route':{'state':route[0],'reason':route[1],'observed':route[2]},
                'scope':'Archived numerical formulas only; final-bundle qualification gate deliberately not evaluated'}
    except (KeyError, TypeError, ValueError, StopIteration) as exc:
        return {'state':'unknown','reason':str(exc)}


def hold_assessment(rule, row, timestep, placement_event, functions=None):
    child = row.get('child_result') or {}; details = child.get('details', {}); states = row.get('states', {})
    window = details.get('cut_to_recovery_admission') or {}
    checks = {key:flag(details.get(key)) for key in ('verified_cut','held_at_absence_end',
        'all_absence_tick_hold_checks_pass','all_cut_to_admission_hold_checks_pass','physical_predicates_passed')}
    checks['child_status'] = child.get('status') == 'passed' if child else None
    timing_flag = flag((child.get('timing') or {}).get('actual_host_timing_pass'))
    checks['host_timing'] = timing_flag
    checks['parent_child_timing_agree'] = (row.get('parent_attempt') or {}).get('actual_host_timing_pass') == timing_flag if timing_flag is not None else None
    checks['recorded_hold'] = flag(window.get('all_recorded_hold_checks_pass'))
    absence = details.get('absence') or {}
    checks['initial_absence_recorded_hold'] = flag(absence.get('all_recorded_hold_checks_pass'))
    try:
        checks['initial_absence_in_full_window'] = (absence['start_sim_time_s']==window['start_sim_time_s']
            and absence['start_wall_elapsed_s']==window['start_wall_elapsed_s']
            and 0 < absence['physics_tick_checks'] <= window['physics_tick_checks']
            and absence['ticks_with_hold_predicate_false']==0 and absence['failed_endpoint_checks']==0
            and absence['last_sim_time_s']<=window['last_sim_time_s']
            and absence['last_wall_elapsed_s']<=window['last_wall_elapsed_s'])
    except (KeyError,TypeError):checks['initial_absence_in_full_window']=None
    for key in ('ticks_with_hold_predicate_false','failed_endpoint_checks'):
        value = window.get(key); checks[key] = value == 0 if type(value) is int else None
    for key in ('physics_tick_checks','endpoint_checks'):
        value = window.get(key); checks[key] = value > 0 if type(value) is int else None
    minimum = window.get('minimum_payload_center_z_m')
    payload_id = details.get('picked_visible_part_id')
    checks['unchanged_center_height'] = (functions['retained_hold_check']({'objects':[{
        'id':payload_id,'position':[0.,0.,minimum],'gripper_contact':True}]},payload_id)
        if finite(minimum) and functions and 'retained_hold_check' in functions else None)
    for label in ('cut','after_cancel','after_hold','before_recovery','after_recovery_admission'):
        try:
            snapshot=states[label]['payload']
            checks['hold_at_'+label] = functions['retained_hold_check'](snapshot['geometry'],payload_id)
            if label=='cut':
                checks['unchanged_public_cut_opportunity'] = functions['cut_eligible'](snapshot['geometry'],payload_id,
                    phase=snapshot['authority']['segment']['phase'],tcp_z=snapshot['robot']['tcp_position_world_m'][2],
                    jaw_width=snapshot['robot']['jaw_width_m'],
                    bilateral=snapshot['contacts']['by_object'][payload_id]['bilateral_force_bearing'])
        except (KeyError,TypeError):checks['hold_at_'+label] = None
    duration = None
    try:
        cut, cancel, admission, after = [states[k] for k in ('cut','after_cancel','recovery_admission','after_recovery_admission')]
        action, response = admission['payload']['action'], admission['payload']['response']
        checks['accepted_matching_dispatch'] = (admission['event_type'] == 'action_admission'
            and response.get('status') == 'accepted' and not response.get('duplicate_suppressed')
            and action.get('operation') == 'recover_held' and action.get('destination') == rule['destination']
            and action.get('request_id') == window.get('accepted_recovery_request_id') == details.get('recovery_request_id')
            and admission['event_id'] == window.get('accepted_admission_event_id'))
        checks['cut_and_admission_clocks'] = (window['start_sim_time_s'] == cut['sim_time_s']
            and cut['wall_elapsed_s'] <= window['start_wall_elapsed_s'] <= cancel['wall_elapsed_s']
            and window['last_sim_time_s'] == admission['sim_time_s'] == after['sim_time_s']
            and admission['wall_elapsed_s'] <= window['last_wall_elapsed_s'] <= after['wall_elapsed_s'])
        for clock, suffix in (('sim','sim_time_s'),('wall','wall_elapsed_s')):
            checks[clock+'_duration_consistent'] = (window['observed_'+clock+'_s'] ==
                window['last_'+suffix] - window['start_'+suffix])
        sim_duration = admission['sim_time_s'] - window['start_sim_time_s']
        wall_duration = admission['wall_elapsed_s'] - window['start_wall_elapsed_s']
        duration = sim_duration if rule['absence']['absence_timebase'] == 'simulation' else wall_duration
        checks['declared_endpoint_supported'] = True if rule['absence']['absence_endpoint'] == 'recover_held_admitted' else None
        checks['measured_duration_supports_declared_bound'] = duration >= rule['absence']['prospective_absence_bound_s']
        # 1e-9 is the fixture's integration-clock comparison tolerance, never geometry padding.
        checks['every_tick_count_and_gap'] = (finite(timestep) and timestep > 0
            and abs(window['physics_tick_checks'] * timestep - sim_duration) <= 1e-9
            and window['maximum_tick_sim_gap_s'] <= timestep + 1e-9)
    except (KeyError, TypeError, ValueError):
        checks['accepted_matching_dispatch'] = None; checks['complete_clock_support'] = None
    final = details.get('independent_final_check') or {}
    checks['settled_placement_flags'] = (final.get('passed_now') is True and bool(final.get('flags'))
        and all(v is True for v in final['flags'].values())) if final else None
    try:
        event = placement_event; payload = event['payload']
        checks['settled_dwell_event'] = (payload['check'] == final and payload['checked_every_physics_tick'] is True
            and payload['dwell_s'] == .5 and payload['stable_since_sim_s'] == details['placement_stable_since_sim_s']
            and event['sim_time_s'] - payload['stable_since_sim_s'] >= .5 - 1e-9)
    except (KeyError, TypeError):
        checks['settled_dwell_event'] = None
    return result(checks, actual_duration_to_accepted_dispatch_s=duration, declared_absence=rule['absence'],
                  recorded_window=window, five_second_window=details.get('absence'),
                  scope=LIMITS[3], bilateral_force_and_pose_throughout='not_measured', timing=child.get('timing'))


def dense_assessment(evidence, identity, corridors, states, functions=None, payload_id=None):
    inventory, inventory_ref = evidence.json(identity + '/geometry-inventory.json')
    ids = [g['geom_id'] for g in inventory['geoms']]
    require(ids and len(ids) == len(set(ids)) and {'robot','payload'} <= {g['role'] for g in inventory['geoms']},
            'Whole-arm/payload inventory incomplete')
    start = states['cut']['sim_time_s']; end = states['after_placement']['sim_time_s']
    stats = {'interval_count':0,'box_count':0,'outside_box_count':0,'intervals_crossing_cut':0,
             'maximum_dense_sim_gap_s':0.,'maximum_dense_wall_gap_s':0.,'first_failure':None,
             'first_sim_time_s':None,'last_sim_time_s':None,'physics_timestep_s':None,
             'interval_tick_checks_pass':True,'unknown_records':[],'observed_sampling_deficit_max_m':0.}
    previous = None
    context = {'sample_count':0,'missing_record_count':0,'other_body_corridor_overlap_samples':0,
               'excess_active_penetration_samples':0,'maximum_observed_active_penetration_m':0.,
               'native_contact_records':0,'first_exception':None}
    expected_objects = sorted(o['id'] for o in states['cut']['payload']['geometry']['objects'])
    def visit(line, raw):
        nonlocal previous
        try:
            row = json.loads(raw); dense = row['interval_dense_geometry']
            first, last = dense['first_sim_wall_s'], dense['last_sim_wall_s']
            if last[0] < start or first[0] > end:
                return
            # Include boundary-straddling intervals whole; never trim their union.
            require(dense['geom_ids'] == ids, 'Dense geometry inventory differs')
            require(all(finite(v) for v in first+last) and first[0] <= last[0] and first[1] <= last[1], 'Invalid dense clocks')
            dt = row['physics_timestep_s']; require(finite(dt) and dt > 0, 'Invalid physics timestep')
            if stats['physics_timestep_s'] is not None:require(dt == stats['physics_timestep_s'], 'Timestep changed')
            stats['physics_timestep_s'] = dt
            require(last[0] == row['sim_time_s'], 'Dense/coarse endpoint clock differs')
            stats['interval_count'] += 1; stats['intervals_crossing_cut'] += int(first[0] < start <= last[0])
            stats['first_sim_time_s'] = first[0] if stats['first_sim_time_s'] is None else stats['first_sim_time_s']
            stats['last_sim_time_s'] = last[0]
            unique = dense['distinct_sim_time_count']
            require(type(unique) is int and unique > 0 and dense['sample_count_including_forced_duplicates'] >= unique,
                    'Dense sample counts invalid')
            gap = dense['maximum_sim_gap_s']; wall_gap = dense['maximum_wall_gap_s']
            require(finite(gap) and finite(wall_gap) and gap >= 0 and wall_gap >= 0, 'Dense gap invalid')
            stats['interval_tick_checks_pass'] &= (gap <= dt+1e-9 and abs((unique-1)*dt-(last[0]-first[0])) <= 1e-9
                and (previous is None or first[0] <= previous+1e-9))
            previous = last[0]
            stats['maximum_dense_sim_gap_s'] = max(stats['maximum_dense_sim_gap_s'], gap)
            stats['maximum_dense_wall_gap_s'] = max(stats['maximum_dense_wall_gap_s'], wall_gap)
            bounds = dense['sampled_outer_box_union_m']
            require(len(bounds['min']) == len(bounds['max']) == len(ids), 'Dense box count differs')
            for i, geom_id in enumerate(ids):
                box = {'min':bounds['min'][i], 'max':bounds['max'][i]}
                assessment = box_union_contains(box, corridors); stats['box_count'] += 1
                if assessment['state'] != 'pass':
                    stats['outside_box_count'] += 1
                    stats['first_failure'] = stats['first_failure'] or {'line':line,'geom_id':geom_id,'box':box,
                        'interval_sim_wall_s':[first,last], 'uncovered':assessment['first_uncovered_box']}
            deficit = dense.get('observed_coarse_endpoint_sampling_deficit_m')
            if deficit:
                values = [v for key in ('lower_m','upper_m') for point in deficit[key] for v in point]
                require(all(finite(v) and v >= 0 for v in values), 'Invalid observed sampling deficit')
                stats['observed_sampling_deficit_max_m'] = max(stats['observed_sampling_deficit_max_m'], *values)
            if start <= row['sim_time_s'] <= end:
                context['sample_count'] += 1
                try:
                    require(functions is not None and payload_id is not None, 'Source-pinned context formulas unavailable')
                    objects, contacts = row['objects'], row['contacts']
                    require(sorted(o['id'] for o in objects)==expected_objects and all(valid_box(o['bounds']) for o in objects),
                            'Other-body inventory/bounds incomplete')
                    blockers = [o['id'] for o in objects if o['id']!=payload_id
                                and any(functions['overlaps'](o['bounds'],box) for box in corridors)]
                    require(isinstance(contacts,list) and all(finite(c['distance_m']) and type(c['constraint_active']) is bool
                            for c in contacts), 'Sampled native contact distances/active flags incomplete')
                    penetration = max([0.]+[-c['distance_m'] for c in contacts if c['constraint_active']])
                    bad = penetration > functions['policy']['maximum_contact_penetration_m']
                    context['native_contact_records'] += len(contacts)
                    context['maximum_observed_active_penetration_m'] = max(context['maximum_observed_active_penetration_m'],penetration)
                    context['other_body_corridor_overlap_samples'] += bool(blockers)
                    context['excess_active_penetration_samples'] += bad
                    if blockers or bad:context['first_exception'] = context['first_exception'] or {
                        'line':line,'sim_time_s':row['sim_time_s'],'blocker_ids':blockers,'active_penetration_m':penetration}
                except (ValueError,KeyError,TypeError) as exc:
                    context['missing_record_count'] += 1
                    context['first_exception'] = context['first_exception'] or {'line':line,'reason':str(exc)}
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            stats['unknown_records'].append({'line':line,'reason':str(exc)})
    trace_ref = evidence.stream(identity + '/whole-geometry.jsonl', visit)
    checks = {'dense_intervals_recorded':stats['interval_count'] > 0,
              'all_dense_boxes_contained':stats['outside_box_count'] == 0 if stats['box_count'] else None,
              'all_consumed_records_supported':None if stats['unknown_records'] else True,
              'tick_count_and_gap_support':flag(stats['interval_tick_checks_pass']),
              'cut_to_placement_covered':stats['first_sim_time_s'] <= start and stats['last_sim_time_s'] >= end
                  if stats['first_sim_time_s'] is not None else None}
    return result(checks, **stats, inventory_ref=inventory_ref,trace_ref=trace_ref,inventory=inventory,
                  scope='Complete interval outer boxes intersecting cut-through-placement, including boundary-straddling intervals',
                  added_padding_m=0.,continuous_clearance_bound_m=None,
                  sampled_other_body_and_contact=result({
                      'recorded':True if context['sample_count'] else None,
                      'complete':None if context['missing_record_count'] else True,
                      'other_body_corridors_clear':context['other_body_corridor_overlap_samples']==0,
                      'native_active_penetration_within_existing_policy':context['excess_active_penetration_samples']==0},
                      **context,scope='Coarse recorded times only; existing Runtime overlap/penetration formulas, no all-tick other-body or contact claim'),
                  other_body_and_contact_throughout='not measured at every tick; rich/coarse observations only')


def placement_event(evidence, identity):
    found = []
    def visit(line, raw):
        try:row = json.loads(raw)
        except ValueError:return
        if row.get('event_type') == 'independent_raw_placement_check':
            require(row.get('payload_sha256') == digest(row['payload']), 'Placement event digest differs')
            found.append({**row,'line':line,'line_sha256':hashlib.sha256(raw).hexdigest()})
    evidence.stream(identity + '/events.jsonl', visit)
    require(len(found) <= 1, 'Duplicate independent placement event')
    return found[0] if found else None


def assess(rule_path, validation_extraction, validation_receipt, extraction_receipt):
    validation = CompletedExtraction(validation_extraction, validation_receipt, extraction_receipt)
    evidence = validation.evidence
    rule, rule_ref = evidence.external(rule_path); validate_provisional_rule(rule)
    require(validation.manifest['execution_phase'] == 'validation'
            and validation.manifest['destination_selection'] == rule['destination'], 'Rule/validation phase destination differs')
    raw_rule, raw_rule_ref = evidence.json('provisional-rule.json')
    require(raw_rule == rule == validation.manifest['provisional_rule'] == validation.data['provisional_rule']
            and rule_ref['sha256'] == raw_rule_ref['sha256'] == validation.manifest['provisional_rule_ref']['sha256']
            == validation.data['provisional_rule_ref']['sha256'], 'Exact predeclared rule bytes differ')
    require(stamp(rule['created_at']) < stamp(validation.receipt['started_at']) <= stamp(validation.manifest['created_at']),
            'Rule does not predate untouched validation job')
    construction_data, construction_ref = evidence.external(rule['construction_extraction']['path'])
    require(construction_ref['sha256'] == rule['construction_extraction']['sha256'], 'Construction extraction reference differs')
    construction = CompletedExtraction(rule['construction_extraction']['path'], construction_data['receipt_ref']['path'])
    require(construction.manifest['execution_phase'] == 'construction' and construction.plan == validation.plan,
            'Construction/validation full declared plan differs')
    require(stamp(construction.data['completed_at']) < stamp(rule['created_at']), 'Rule predates completed construction extraction')
    class_spec, class_ref = evidence.external(rule['class_spec']['path'])
    require(class_ref['sha256'] == rule['class_spec']['sha256'] and digest(class_spec) == rule['class_spec']['canonical_sha256'],
            'Exact/canonical class spec reference differs')
    numeric_source, numeric_ref = validation.source('Runtime/restart_state.py')
    fixture_source, fixture_ref = validation.source('Batch 01/Recovery Qualification/fixture.py')
    functions = numeric_functions(numeric_source,fixture_source)
    compat_source, compat_ref = validation.source('Runtime/restart_compatibility.py')
    for node in ast.walk(ast.parse(compat_source)):
        if isinstance(node,ast.Import):require(all(item.name in ('hashlib','json','math','re') for item in node.names), 'Unsupported compatibility import')
        if isinstance(node,ast.ImportFrom):require(node.module=='__future__','Unsupported compatibility import')
    compat = {'__name__':'_archived_compatibility'}
    exec(compile(compat_source, '<source-pinned compatibility>', 'exec'), compat)
    # Resolve actual coupled construction points, never a Cartesian product or inferred box.
    points = {}; construction_rows = []; class_bound = False
    for identity in construction.declared:
        try:
            row = construction.trial(identity)
            child=row.get('child_result') or {}; details=child.get('details') or {}
            construction_rows.append({'trial_id':identity,'execution_status':row['execution_status'],
                'declaration':row['declaration'],'parent_attempt':row.get('parent_attempt'),
                'child_status':child.get('status'),'child_error':child.get('error'),
                'physical_predicates_passed':details.get('physical_predicates_passed'),
                'cut_to_recovery_admission':details.get('cut_to_recovery_admission'),'timing':child.get('timing'),
                'compiled_properties':row.get('compiled_properties'),'consumed_ref':row['consumed_ref']})
            if row.get('protected_class_spec') == class_spec:class_bound = True
            for label, state in row['states'].items():
                if label not in RICH_LANDMARKS or state.get('status') != 'recorded':continue
                snapshot = state['payload']
                key = (snapshot['snapshot_sha256'],snapshot['physical_configuration_sha256'],digest(snapshot['physical_class_observation']))
                points.setdefault(key, []).append({'trial_id':identity,'landmark':label,'state':state,'row':row})
        except (ValueError, KeyError, TypeError, OSError) as exc:
            construction_rows.append({'trial_id':identity,'execution_status':construction.entries[identity]['execution_status'],
                                      'binding_state':'unknown','reason':str(exc)})
    require(class_bound, 'Rule class spec is not retained by a bound construction trial')
    point_support = []
    for cell in rule['cells']:
        for point in cell['measured_points']:
            matches = points.get(tuple(point.get(k) for k in POINT_KEYS), [])
            support = []
            for match in matches:
                row = match['row']; snapshot = match['state']['payload']; declaration = row['declaration']
                numeric = numeric_membership(rule,class_spec,snapshot,functions)
                support.append({'trial_id':row['trial_id'],'landmark':match['landmark'],'source_ref':match['state']['source_ref'],
                    'fixture':declaration['fixture'],'destination':declaration['destination'],
                    'execution_status':row['execution_status'],'numerical':numeric,
                    'generator_domain_member':(row.get('compiled_properties') or {}).get('all_objects_generator_domain_members')})
            # Boundary points retain their exact tuples even when a protected
            # class export is unavailable. Binding is distinct from membership.
            supported = any(match['row']['declaration']['fixture']=='construction'
                and match['row']['declaration']['destination']==rule['destination']
                and match['row']['declaration']['family']==cell['grip_envelope']['family'] for match in matches)
            point_support.append({'cell_id':cell['cell_id'],'point':point,'binding_state':'pass' if supported else 'unknown',
                                  'matches':support})
    rows = []
    for identity in validation.declared:
        entry = validation.entries[identity]
        report = {'trial_id':identity,'declaration':validation.declared[identity],
                  'execution_status':entry['execution_status'],'selected_validation':identity in validation.selected}
        try:
            row = validation.trial(identity); report['consumed_ref'] = row['consumed_ref']
            report['compiled_properties'] = row.get('compiled_properties')
            report['parent_attempt'] = row.get('parent_attempt')
            report['unparsed_event_records'] = row['unparsed_events']
            if identity not in validation.selected:
                report['state'] = 'not_selected'; rows.append(report); continue
            if not row.get('child_result'):
                report.update(state='unknown',reason='Declared validation trial has no child result'); rows.append(report); continue
            states = row['states']; memberships = {}
            compatibility = {}
            for label in ('cut','before_recovery'):
                state = states.get(label, {})
                if state.get('status') != 'recorded':
                    memberships[label] = {'state':'unknown','reason':'Missing rich landmark'}
                    compatibility[label] = {'compatibility_state':'unknown'}; continue
                snapshot = state['payload']
                memberships[label] = numeric_membership(rule,class_spec,snapshot,functions)
                compatibility[label] = compat['verify_class_compatibility'](class_spec,snapshot['physical_class_observation'],
                    frozen_spec_sha256=rule['class_spec']['canonical_sha256'])
            report['numeric_membership'] = memberships; report['class_compatibility'] = compatibility
            report['landmark_refs'] = {k:v.get('source_ref') for k,v in states.items() if v.get('status')=='recorded'}
            cell_id = memberships['cut'].get('cell_id')
            cell = next((c for c in rule['cells'] if c['cell_id']==cell_id), None)
            geometry = {'state':'unknown','reason':'Unique mapped cut cell unavailable'}
            if cell:
                try:geometry = dense_assessment(evidence,identity,cell['route_envelope']['clearance_corridors_m'],states,
                                                functions,memberships['cut']['payload_id'])
                except (KeyError, ValueError, TypeError, OSError) as exc:geometry = {'state':'unknown','reason':str(exc)}
            report['dense_geometry'] = geometry
            hold = hold_assessment(rule,row,geometry.get('physics_timestep_s'),placement_event(evidence,identity),functions)
            report['hold_absence_placement_timing'] = hold
            report['child_status'] = row['child_result']['status']; report['child_error'] = row['child_result'].get('error')
            report['state'] = all_states([m['state'] for m in memberships.values()]
                + [c['compatibility_state'] for c in compatibility.values()] + [geometry['state'],hold['state'],
                    geometry.get('sampled_other_body_and_contact',{}).get('state','unknown'),
                    'unknown' if row['unparsed_events'] else 'pass'])
        except (ValueError, KeyError, TypeError, OSError) as exc:
            report.update(state='unknown',binding_state='unknown',reason=str(exc))
        rows.append(report)
    evidence.stable(); construction.evidence.stable()
    selected = [r for r in rows if r['selected_validation']]
    binding_complete = all(p['binding_state']=='pass' for p in point_support) and not any(r.get('binding_state')=='unknown' for r in construction_rows)
    return {'schema_version':'restart-fixed-rule-validation-assessment-1','completed_at':datetime.now(timezone.utc).isoformat(),
        'rule_ref':rule_ref,'canonical_rule_sha256':digest(rule),'class_spec_ref':class_ref,
        'validation_extraction_ref':validation.ref,'validation_receipt_ref':validation.receipt_ref,
        'extraction_receipt_ref':validation.extraction_receipt_ref,'construction_extraction_ref':construction.ref,
        'input_directories':[str(validation.base),str(validation.evidence.root),str(construction.base),str(construction.evidence.root)],
        'source_manifest_refs':{'construction':construction.manifest_ref,'validation':validation.manifest_ref},
        'numeric_source_ref':numeric_ref,'fixture_predicate_source_ref':fixture_ref,'compatibility_source_ref':compat_ref,
        'numerical_adapter':'Archived grip/route numerical functions unchanged; final-bundle identity gate omitted only for offline comparison',
        'construction_trials':construction_rows,'construction_point_binding':point_support,
        'construction_binding_complete':binding_complete,'trials':rows,'selected_validation_ids':validation.selected,
        'validation_set_support':{'state':'present' if selected else 'unknown',
            'reason':None if selected else 'No declared validation measurements for the fixed destination'},
        'source_holds':{'construction':construction.summary.get('sources_unchanged'),'validation':validation.summary.get('sources_unchanged')},
        'finite_declared_checks_state':all_states([r['state'] for r in selected]+['pass' if binding_complete else 'unknown']
            + ['pass' if s.summary.get('sources_unchanged') is True else 'unknown' for s in (construction,validation)]
            + ['pass' if selected else 'unknown']),
        'selected_state_counts':{state:sum(r['state']==state for r in selected) for state in ('pass','fail','unknown')},
        'unverified_empirical_transfer_rule':rule['empirical_transfer_rule'],'untested_combinations':rule['untested_combinations'],
        'qualification_granted':False,'scored_ready_claimed':False,'continuous_clearance_bound_m':None,
        'limitations':LIMITS,
        'consumed_files':[ref for collection in (evidence,construction.evidence)
                          for path,ref in sorted(collection.consumed.items(),key=lambda item:str(item[0]))]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('rule','validation-extraction','validation-receipt','extraction-receipt','output'):
        parser.add_argument('--'+name,required=True)
    args = parser.parse_args(argv)
    runtime = HERE.parents[1] / 'Runtime'; sys.path.insert(0,str(runtime))
    from release_runner import queued_job
    authority = queued_job(expected_script=__file__)
    output = Path(args.output).resolve(); require(not output.exists(),'Assessment output must be fresh')
    dependencies=[Path(__file__),HERE/'bundle_construction.py',HERE/'compatibility.py',FIXTURE/'extract_screen.py']
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in dependencies}
    report = assess(args.rule,args.validation_extraction,args.validation_receipt,args.extraction_receipt)
    for directory in report['input_directories']:
        root=Path(directory).resolve()
        require(root!=output and root not in output.parents and output not in root.parents,
                'Assessment output must be separate from source/extracted evidence')
    require(before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in dependencies}, 'Assessor dependency changed during processing')
    report['assessment_queue'] = authority
    report['assessor_dependency_sha256'] = before
    report['assessor_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    output.mkdir(parents=True,exist_ok=False)
    reader.write(output / 'assessment.json',report)
    print(json.dumps({'output':str(output),'finite_declared_checks_state':report['finite_declared_checks_state'],
                      'qualification_granted':False}))


if __name__ == '__main__':main()
