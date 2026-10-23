"""Bounded synthetic completed screens; no queue calls, physics or real evidence."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

import assess_validation as assess
from compatibility import digest
from test_compatibility import fixture as class_fixture

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parents[1] / 'Runtime'


def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(assess.reader.canonical(value))


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def job(identity, day, second=0):
    return {'id':identity,'child_pid':123,'worker_pid':45,'resolved_executable':'python',
            'argv':['python','synthetic.py'],'cwd':'synthetic','started_at':f'2020-01-{day:02}T00:00:{second:02}Z'}


class FrozenDatetime(datetime):
    day = 1
    @classmethod
    def now(cls, tz=None):return datetime(2020,1,cls.day,0,0,12,tzinfo=timezone.utc)


class Fixture:
    def __init__(self, root):
        self.root=root; self.spec,self.observation=class_fixture()
        names = list(assess.SOURCE_KEYS)+['restart_state.py','restart_compatibility.py',
                                        'restart_qualification.py','restart_physical_class.py']
        self.sources={'Runtime/'+name:(RUNTIME/name).read_bytes() for name in names}
        self.sources['Batch 01/Recovery Qualification/extract_screen.py']=(assess.FIXTURE/'extract_screen.py').read_bytes()
        self.sources['Batch 01/Recovery Qualification/fixture.py']=(assess.FIXTURE/'fixture.py').read_bytes()
        self.hashes={str((HERE.parents[1]/name).resolve()):hashlib.sha256(raw).hexdigest() for name,raw in self.sources.items()}
        self.physical={name:sha(RUNTIME/name) for name in assess.SOURCE_KEYS}
        binding={**self.physical, **{name:sha(RUNTIME/name) for name in
            ('restart_state.py','restart_compatibility.py','restart_qualification.py')},
            'descriptor_exporter':sha(RUNTIME/'restart_physical_class.py'),
            'robot_assets':digest('synthetic-assets'),'mujoco_build':digest('synthetic-build')}
        self.spec['required_source_hashes']=binding; self.observation['source_hashes']=binding
        self.xml='<mujoco>\n</mujoco>\n'; self.observation['scene_xml_sha256']=hashlib.sha256(self.xml.encode()).hexdigest()
        self.observation['export_state']='pass'
        self.plan={'trials':[{'id':identity,'destination':destination,'fixture':fixture,'family':'A',
            'population':3,'world_seed':index,'layout_seed':index,'noise_seed':0,'expected_payload_id':'A1'}
            for index,(identity,destination,fixture) in enumerate((
                ('c-good','parking1','construction'),('c-boundary','parking1','construction'),
                ('v-good','parking1','independent_generator'),('v-outside','parking1','independent_generator'),
                ('v-failed','parking1','independent_generator'),('v-missing','parking1','independent_generator'),
                ('other','parking2','independent_generator')))]}
        self.corridors=[{'min':[-1.,-1.,-.5],'max':[1.,1.,1.]}]
        self.cell={'cell_id':'A','payload_template_sha256':digest(self.spec['templates']['part:A']),
            'grip_envelope':{'kind':'part','family':'A','jaw_width_m':[.02,.06],
                'relative_position_m':{'min':[-.01]*3,'max':[.01]*3},'relative_rotation':[[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]],
                'maximum_rotation_error_rad':.1,'finger_normal_force_N':[1.,20.],
                'maximum_linear_speed_m_s':.3,'maximum_angular_speed_rad_s':.5,'minimum_payload_bottom_z_m':.1},
            'route_envelope':{'operation':'recover_held','destination':'parking1','payload_kind':'part','payload_family':'A',
                'tcp_start_m':{'min':[.28,-.02,.12],'max':[.32,.02,.18]},
                'destination_region_m':{'min':[.15,-.14,-.003],'max':[.25,-.04,.08]},
                'joint_start_ranges_rad':[[-.1,.1]]*7,'joint_velocity_ranges_rad_s':[[-.1,.1]]*7,
                'maximum_abs_finger_velocity_m_s':.01,'clearance_corridors_m':self.corridors},
            'measured_state_cell_basis':'synthetic only','source_scope':'synthetic only',
            'route_coverage_method':'synthetic only','untested_combinations':'all physics',
            'route_sampling_clearance_allowance_m':0.,'measured_points':[]}

    def snapshot(self, identity, sim, label):
        snapshot={'physical_configuration_sha256':self.observation['physical_configuration_sha256'],
            'scene_xml_sha256':self.observation['scene_xml_sha256'],'source_hashes':self.physical,
            'physical_class_observation':copy.deepcopy(self.observation),'capture_sim_time_s':sim,
            'robot':{'joint_position_rad':[0.]*7,'joint_velocity_rad_s':[0.]*7,'finger_velocity_m_s':[0.,0.],
                'jaw_width_m':.04,'tcp_position_world_m':[.3,0.,.15]},
            'object_poses':{'A1':{'relative_to_tcp':{'position_m':[0.,0.,0.],
                'rotation':[[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]]}}},
            'geometry':{'objects':[],'zones':{'parking1':copy.deepcopy(self.cell['route_envelope']['destination_region_m'])}},
            'contacts':{'by_object':{}},'exposure':{'part_id':'A1'},'authority':{'segment':{'phase':4}}}
        for i,record in enumerate(self.observation['objects']):
            obj={'id':record['id'],'kind':record['kind'],'family':record['family'],
                 'position':[.3 if i==0 else 3.+i,0.,.15], 'linear_velocity':[0.]*3,'angular_velocity':[0.]*3,
                 'gripper_contact':i==0}
            obj['bounds']={'min':[obj['position'][0]-.02,-.02,.13],'max':[obj['position'][0]+.02,.02,.17]}
            snapshot['geometry']['objects'].append(obj)
            snapshot['contacts']['by_object'][obj['id']]={'hand_contact':i==0,'bilateral_force_bearing':i==0,
                'left_normal_force_N':2. if i==0 else 0.,'right_normal_force_N':2. if i==0 else 0.}
        if identity=='v-outside':snapshot['robot']['joint_position_rad'][0]=.2
        if identity=='c-boundary':
            snapshot['physical_class_observation']={'export_state':'unknown','reason':'calibration boundary outside domain',
                'physical_configuration_sha256':snapshot['physical_configuration_sha256']}
        if label=='after_placement':
            snapshot['contacts']['by_object']['A1'].update(hand_contact=False,bilateral_force_bearing=False)
        snapshot['snapshot_sha256']=digest(snapshot)
        return snapshot

    def screen(self, phase, day, rule=None):
        root=self.root/phase;root.mkdir()
        receipt=self.root/(phase+'-receipt.json');j=job(phase,day)
        write(receipt,{**j,'state':'succeeded','exit_status':0,'ended_at':f'2020-01-{day:02}T00:00:10Z'})
        with zipfile.ZipFile(root/'source-bundle.zip','w') as archive:
            for name,raw in self.sources.items():archive.writestr(name,raw)
        fixture='construction' if phase=='construction' else 'independent_generator'
        selected=[t['id'] for t in self.plan['trials'] if t['destination']=='parking1' and t['fixture']==fixture]
        deferred=[t['id'] for t in self.plan['trials'] if t['destination']=='parking1' and t['id'] not in selected]
        manifest={'schema_version':assess.reader.SCHEMA,'created_at':f'2020-01-{day:02}T00:00:01Z',
            'queue':{'queue_job':j,'job_id':j['id'],'pid':133,
                     'driver_metadata':{'created_at':f'2020-01-{day:02}T00:00:01Z'}},'prospective_plan':self.plan,'modes':selected,
            'destination_selection':'parking1','execution_phase':phase,'phase_deferred_trial_ids':deferred,
            'source_bundle_sha256':sha(root/'source-bundle.zip'),'source_hashes':self.hashes,
            'provisional_rule':rule,'provisional_rule_ref':None}
        if rule:
            write(root/'provisional-rule.json',rule)
            manifest['provisional_rule_ref']={'path':'provisional-rule.json','sha256':sha(root/'provisional-rule.json')}
        write(root/'manifest.json',manifest)
        attempts=[]
        for identity in selected:
            if identity=='v-missing':break
            declaration=next(t for t in self.plan['trials'] if t['id']==identity)
            trial=root/identity;trial.mkdir()
            write(trial/'probe-manifest.json',{'trial':declaration,'source_hashes':self.hashes,
                'parent_manifest_sha256':sha(root/'manifest.json'),'prospective_plan_sha256':digest(self.plan),
                'queue':{'job_id':j['id'],'driver_pid':133,'probe_launcher_pid':222,'probe_pid':333,
                         'process_creation_times':[f'2020-01-{day:02}T00:00:{sec:02}Z' for sec in (0,1,2,3)]}})
            write(trial/'construction.json',{'trial':declaration})
            write(trial/'compiled-properties.json',{'objects':{'A1':{'main_geom_mass_kg':.11 if identity=='c-boundary' else .1,
                'generator_half_open_domain_member':identity!='c-boundary'}},'all_objects_generator_domain_members':identity!='c-boundary'})
            if identity!='c-boundary':write(trial/'protected-class-spec.json',self.spec)
            (trial/'world-0.xml').write_bytes(self.xml.replace('\n','\r\n').encode())
            events=[];states={}
            landmarks=[('cut',1.,1.),('after_cancel',1.,1.02),('after_hold',6.,6.01),('before_recovery',6.,6.09),
                       ('recovery_admission',6.,6.1),('after_recovery_admission',6.,6.12),('after_placement',7.,7.1)]
            for number,(label,sim,wall) in enumerate(landmarks,1):
                if label=='recovery_admission':
                    payload={'action':{'operation':'recover_held','destination':'parking1','request_id':'r'},
                             'response':{'status':'accepted'}};kind='action_admission'
                else:
                    payload=self.snapshot(identity,sim,label);kind=next(k for k,v in assess.reader.STATES.items() if v==label)
                event={'event_id':number,'event_type':kind,'sim_time_s':sim,'wall_elapsed_s':wall,
                       'payload':payload,'payload_sha256':digest(payload)}
                events.append(event);states[label]=event
            final={'passed_now':True,'flags':{'full_containment':True,'released':True},'part_id':'A1','destination':'parking1'}
            placed={'event_id':8,'event_type':'independent_raw_placement_check','sim_time_s':7.,'wall_elapsed_s':7.11,
                    'payload':{'check':final,'dwell_s':.5,'stable_since_sim_s':6.5,'checked_every_physics_tick':True}}
            placed['payload_sha256']=digest(placed['payload']);events.append(placed)
            (trial/'events.jsonl').write_bytes(b''.join(assess.reader.canonical(e)+b'\n' for e in events))
            failed=identity=='v-failed'
            window={'start_sim_time_s':1.,'start_wall_elapsed_s':1.01,'last_sim_time_s':6.,'last_wall_elapsed_s':6.11,
                'observed_sim_s':5.,'observed_wall_s':6.11-1.01,'physics_tick_checks':2500,'endpoint_checks':2,
                'ticks_with_hold_predicate_false':int(failed),'failed_endpoint_checks':0,
                'maximum_tick_sim_gap_s':.002,'maximum_tick_wall_gap_s':.003,'minimum_payload_center_z_m':.15,
                'minimum_payload_bottom_z_m':.13,'accepted_recovery_request_id':'r','accepted_admission_event_id':5,
                'all_recorded_hold_checks_pass':not failed}
            details={'verified_cut':True,'picked_visible_part_id':'A1','held_at_absence_end':True,
                'all_absence_tick_hold_checks_pass':not failed,'all_cut_to_admission_hold_checks_pass':not failed,
                'physical_predicates_passed':not failed,'cut_to_recovery_admission':window,'absence':copy.deepcopy(window),
                'recovery_request_id':'r','independent_final_check':final,'placement_stable_since_sim_s':6.5}
            status='failed' if failed else 'passed'
            child={'trial_id':identity,'trial':declaration,'status':status,'details':details,
                'source_hashes_before':self.hashes,'source_hashes_after':self.hashes,'sources_unchanged':True,
                'timing':{'actual_host_timing_pass':True},'error':'synthetic transient loss' if failed else None}
            write(trial/'result.json',child)
            attempts.append({'trial_id':identity,'status':status,'result_path':identity+'/result.json',
                'result_sha256':sha(trial/'result.json'),'actual_host_timing_pass':True})
            geoms=[{'geom_id':4,'role':'robot','body':'arm','bounds_method':'synthetic'},
                   {'geom_id':9,'role':'payload','body':'A1','bounds_method':'synthetic'}]
            write(trial/'geometry-inventory.json',{'geoms':geoms,'alignment':'synthetic cached-state alignment'})
            trace=[]
            for first,last,phase_name in ((1.,1.,'absence'),(1.,6.,'recovery'),(6.,7.,'settling')):
                dense={'geom_ids':[4,9],'sample_count_including_forced_duplicates':round((last-first)/.002)+1,
                    'distinct_sim_time_count':round((last-first)/.002)+1,'first_sim_wall_s':[first,first],
                    'last_sim_wall_s':[last,last],'maximum_sim_gap_s':.002 if last>first else 0.,
                    'maximum_wall_gap_s':.003,'sampled_outer_box_union_m':{'min':[[.1,-.1,.1],[.28,-.02,.13]],
                        'max':[[.2,.1,.2],[.32,.02,.17]]},'observed_coarse_endpoint_sampling_deficit_m':None}
                trace.append({'sim_time_s':last,'wall_elapsed_s':last,'phase':phase_name,'physics_timestep_s':.002,
                    'objects':self.snapshot(identity,last,'cut')['geometry']['objects'],'contacts':[],
                    'interval_dense_geometry':dense,'robot_and_payload_geoms':[{'geom_id':geom_id,
                        'position_m':[.15,0.,.15],'outer_bounds':{'min':dense['sampled_outer_box_union_m']['min'][i],
                        'max':dense['sampled_outer_box_union_m']['max'][i]}} for i,geom_id in enumerate((4,9))]})
            (trial/'whole-geometry.jsonl').write_bytes(b''.join(assess.reader.canonical(t)+b'\n' for t in trace))
        write(root/'summary.json',{'schema_version':assess.reader.SCHEMA,'queue_job_id':j['id'],
            'finished_at':f'2020-01-{day:02}T00:00:09Z','attempts':attempts,'not_started':selected[len(attempts):],
            'phase_deferred_trial_ids':deferred,'sources_unchanged':True})
        self.index(root)
        output=self.root/(phase+'-extraction');extract_job=job(phase+'-extract',day,11)
        FrozenDatetime.day=day
        with patch.object(assess.reader,'datetime',FrozenDatetime):
            assess.reader.extract(root,receipt,output,extraction_queue=extract_job)
        extraction_receipt=self.root/(phase+'-extract-receipt.json')
        write(extraction_receipt,{**extract_job,'state':'succeeded','exit_status':0,'ended_at':f'2020-01-{day:02}T00:00:13Z'})
        return output/'extraction.json',receipt,extraction_receipt

    @staticmethod
    def index(root):
        write(root/'evidence-index.json',{'schema_version':assess.reader.SCHEMA,'files':[
            {'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
            for p in sorted(root.rglob('*')) if p.is_file() and p.name!='evidence-index.json']})

    def complete(self):
        construction,_,_=self.screen('construction',1)
        state=json.loads((construction.parent/'c-good/measured-states.json').read_bytes())['states']['cut']['payload']
        self.cell['measured_points']=[{'snapshot_sha256':state['snapshot_sha256'],
            'physical_configuration_sha256':state['physical_configuration_sha256'],
            'physical_class_observation_sha256':digest(state['physical_class_observation'])}]
        spec_path=self.root/'class-spec.json';write(spec_path,self.spec)
        rule={'schema_version':'provisional-restart-class-rule-1','status':'provisional_development_rule',
            'created_at':'2020-01-02T00:00:00Z','destination':'parking1',
            'construction_extraction':{'path':str(construction),'sha256':sha(construction)},
            'class_spec':{'path':str(spec_path),'sha256':sha(spec_path),'canonical_sha256':digest(self.spec)},
            'selection_rule':'unique_bilateral_payload_template','payload_template_to_cell':{'part:A':'A'},'cells':[self.cell],
            'geometry_scope':'discrete_native_evaluated_states_empirical_transfer','empirical_transfer_rule':'synthetic only',
            'untested_combinations':['all physics'],'validation_outcomes_used_for_fitting':False,
            'absence':{'prospective_absence_bound_s':5.,'absence_timebase':'simulation','absence_endpoint':'recover_held_admitted'}}
        self.rule=rule;rule_path=self.root/'rule.json';write(rule_path,rule)
        extraction,receipt,extract_receipt=self.screen('validation',3,rule)
        return rule_path,extraction,receipt,extract_receipt


class AssessorTests(unittest.TestCase):
    def test_exact_corridor_union_no_hull_shortcut_or_padding(self):
        box={'min':[0.,0.,0.],'max':[2.,1.,1.]}
        left={'min':[0.,0.,0.],'max':[1.,1.,1.]};right={'min':[1.,0.,0.],'max':[2.,1.,1.]}
        self.assertEqual(assess.box_union_contains(box,[left,right])['state'],'pass')
        right['min'][0]=1.000000001
        self.assertEqual(assess.box_union_contains(box,[left,right])['state'],'fail')
        with self.assertRaises(ValueError):assess.box_union_contains({'min':[float('nan'),0,0],'max':[2,1,1]},[left])

    def test_adapter_is_archived_numeric_only_and_rejects_gate_drift(self):
        source=(RUNTIME/'restart_state.py').read_text(encoding='utf-8')
        funcs=assess.numeric_functions(source)
        self.assertNotIn('classify_restart',funcs)
        with self.assertRaisesRegex(ValueError,'gate shape'):
            assess.numeric_functions(source.replace("if state!='pass':return state,reason,None", "if state!='pass':return 'unknown',reason,None"))

    def test_fixed_cell_membership_true_rotation_and_no_fallback_or_new_margin(self):
        with TemporaryDirectory() as temp:
            fixture=Fixture(Path(temp));functions=assess.numeric_functions((RUNTIME/'restart_state.py').read_text())
            rule={'cells':[fixture.cell],'payload_template_to_cell':{'part:A':'A'}}
            snapshot=fixture.snapshot('v-good',1.,'cut')
            self.assertEqual(assess.numeric_membership(rule,fixture.spec,snapshot,functions)['state'],'pass')
            for change in ('rotation','joint','force','second_cell'):
                value=copy.deepcopy(snapshot);changed_rule=copy.deepcopy(rule)
                if change=='rotation':value['object_poses']['A1']['relative_to_tcp']['rotation']=[[-1.,0.,0.],[0.,-1.,0.],[0.,0.,1.]]
                if change in ('joint','second_cell'):value['robot']['joint_position_rad'][0]=.1+1e-12
                if change=='force':value['contacts']['by_object']['A1']['left_normal_force_N']=20.+1e-12
                if change=='second_cell':
                    alternative=copy.deepcopy(fixture.cell);alternative['cell_id']='unmapped-wide'
                    alternative['route_envelope']['joint_start_ranges_rad']=[[-1.,1.]]*7
                    changed_rule['cells'].append(alternative)
                report=assess.numeric_membership(changed_rule,fixture.spec,value,functions)
                with self.subTest(change=change):
                    self.assertEqual(report['state'],'fail',report)
                    self.assertEqual(report['cell_id'],'A')
                    if change=='rotation':self.assertAlmostEqual(report['grip']['observed']['rotation_error_rad'],3.141592653589793)

    def test_actual_shaped_screen_retains_all_ids_and_counterexamples(self):
        with TemporaryDirectory() as temp:
            fixture=Fixture(Path(temp));args=fixture.complete();report=assess.assess(*args)
            rows={r['trial_id']:r for r in report['trials']}
            self.assertEqual(list(rows),[t['id'] for t in fixture.plan['trials']])
            self.assertEqual(rows['v-good']['state'],'pass',rows['v-good'])
            self.assertEqual(rows['v-outside']['state'],'fail',rows['v-outside'])
            self.assertFalse(rows['v-outside']['numeric_membership']['cut']['route']['observed'][0]['checks']['joint_start'])
            self.assertEqual(rows['v-failed']['state'],'fail')
            self.assertTrue(rows['v-failed']['hold_absence_placement_timing']['checks']['settled_placement_flags'])
            self.assertFalse(rows['v-failed']['hold_absence_placement_timing']['checks']['ticks_with_hold_predicate_false'])
            self.assertEqual(rows['v-missing']['state'],'unknown');self.assertEqual(rows['other']['state'],'not_selected')
            self.assertFalse(report['construction_trials'][1]['compiled_properties']['all_objects_generator_domain_members'])
            self.assertEqual(report['selected_state_counts'],{'pass':1,'fail':2,'unknown':1})
            self.assertTrue(report['construction_binding_complete']);self.assertFalse(report['qualification_granted'])
            self.assertFalse(report['scored_ready_claimed']);self.assertIsNone(report['continuous_clearance_bound_m'])
            self.assertTrue(all('sha256' in ref for ref in report['consumed_files']))

    def test_empty_selected_validation_set_cannot_pass_vacuously(self):
        with TemporaryDirectory() as temp:
            fixture=Fixture(Path(temp))
            fixture.plan['trials']=[t for t in fixture.plan['trials']
                if t['fixture']=='construction' or t['destination']=='parking2']
            report=assess.assess(*fixture.complete())
            self.assertEqual(report['selected_validation_ids'],[])
            self.assertEqual(report['finite_declared_checks_state'],'unknown')
            self.assertIn('No declared validation measurements',report['validation_set_support']['reason'])
            self.assertFalse(report['qualification_granted'])

    def test_raw_derived_child_and_event_tamper_preserved_as_unknown(self):
        for change in ('child','state','source'):
            with self.subTest(change=change),TemporaryDirectory() as temp:
                fixture=Fixture(Path(temp));args=fixture.complete();root=args[1].parent
                if change=='child':
                    path=root/'v-good/trial.json';value=json.loads(path.read_bytes());value['child_result']['status']='failed'
                elif change=='state':
                    path=root/'v-good/measured-states.json';value=json.loads(path.read_bytes())
                    value['states']['cut']['payload']['robot']['jaw_width_m']=.05
                else:
                    path=Path(temp)/'validation/v-good/events.jsonl'
                    path.write_bytes(path.read_bytes()+b'\n');value=None
                if value is not None:write(path,value)
                report=assess.assess(*args);row=next(r for r in report['trials'] if r['trial_id']=='v-good')
                self.assertEqual(row['state'],'unknown',row);self.assertEqual(row['binding_state'],'unknown')

    def test_populated_derived_artifact_without_indexed_raw_source_is_unknown(self):
        for filename in ('protected-class-spec.json','result.json','probe-manifest.json','compiled-properties.json'):
            with self.subTest(filename=filename),TemporaryDirectory() as temp:
                fixture=Fixture(Path(temp));args=fixture.complete()
                index=Path(temp)/'validation/evidence-index.json';value=json.loads(index.read_bytes())
                value['files']=[r for r in value['files'] if r['path']!='v-good/'+filename];write(index,value)
                extraction=json.loads(args[1].read_bytes())
                extraction['evidence_index_ref'].update(sha256=sha(index),bytes=index.stat().st_size)
                write(args[1],extraction)
                report=assess.assess(*args);row=next(r for r in report['trials'] if r['trial_id']=='v-good')
                self.assertEqual(row['state'],'unknown',row)
                self.assertIn('no indexed raw source',row['reason'])

    def test_missing_declared_id_receipt_and_exact_rule_mutation_rejected(self):
        for change in ('missing_id','receipt','extraction_receipt','rule'):
            with self.subTest(change=change),TemporaryDirectory() as temp:
                args=Fixture(Path(temp)).complete()
                index={'missing_id':1,'receipt':2,'extraction_receipt':3,'rule':0}[change]
                path=args[index];value=json.loads(path.read_bytes())
                if change=='missing_id':value['trials']=[r for r in value['trials'] if r['trial_id']!='v-missing']
                elif change in ('receipt','extraction_receipt'):value['child_pid']+=1
                else:value['absence']['prospective_absence_bound_s']=.1
                write(path,value)
                with self.assertRaises(ValueError):assess.assess(*args)

    def test_clock_endpoint_admission_and_transient_scope(self):
        with TemporaryDirectory() as temp:
            fixture=Fixture(Path(temp));args=fixture.complete()
            completed=assess.CompletedExtraction(args[1],args[2],args[3]);row=completed.trial('v-good')
            placed=assess.placement_event(completed.evidence,'v-good')
            functions=assess.numeric_functions((RUNTIME/'restart_state.py').read_text(),(assess.FIXTURE/'fixture.py').read_text())
            report=assess.hold_assessment(fixture.rule,row,.002,placed,functions)
            self.assertEqual(report['state'],'pass',report)
            self.assertEqual(report['bilateral_force_and_pose_throughout'],'not_measured')
            for change in ('ready','wrong_dest','rejected','wall_bound','lost_tick','short_gap'):
                rule=copy.deepcopy(fixture.rule);modified=copy.deepcopy(row)
                if change=='ready':rule['absence']['absence_endpoint']='restart_ready'
                if change=='wrong_dest':modified['states']['recovery_admission']['payload']['action']['destination']='parking2'
                if change=='rejected':modified['states']['recovery_admission']['payload']['response']['status']='rejected'
                if change=='wall_bound':rule['absence'].update(absence_timebase='wall',prospective_absence_bound_s=6.)
                if change=='lost_tick':modified['child_result']['details']['cut_to_recovery_admission']['physics_tick_checks']-=1
                if change=='short_gap':modified['child_result']['details']['cut_to_recovery_admission']['maximum_tick_sim_gap_s']=.004
                with self.subTest(change=change):self.assertNotEqual(assess.hold_assessment(rule,modified,.002,placed,functions)['state'],'pass')

    def test_dense_interval_crosses_small_corridor_gap_despite_center_inside(self):
        with TemporaryDirectory() as temp:
            fixture=Fixture(Path(temp));args=fixture.complete()
            completed=assess.CompletedExtraction(args[1],args[2],args[3]);row=completed.trial('v-good')
            corridors=[{'min':[-1.,-1.,-.5],'max':[.19,1.,1.]},{'min':[.21,-1.,-.5],'max':[1.,1.,1.]}]
            report=assess.dense_assessment(completed.evidence,'v-good',corridors,row['states'])
            self.assertEqual(report['state'],'fail');self.assertGreater(report['outside_box_count'],0)
            self.assertEqual(report['added_padding_m'],0.);self.assertEqual(report['first_failure']['geom_id'],4)


if __name__=='__main__':unittest.main()
