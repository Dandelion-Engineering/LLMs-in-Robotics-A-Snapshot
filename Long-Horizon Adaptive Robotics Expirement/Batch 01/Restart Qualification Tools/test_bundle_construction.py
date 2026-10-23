"""Synthetic extraction/draft counterexamples; no physical evidence consumed."""
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bundle_construction import (GEOMETRY_SCOPE, PROVISIONAL_SCHEMA, RICH_LANDMARKS, SELECTION_RULE,
                                 construction_dossier, validate_provisional_rule)
from compatibility import digest
from test_calibration_loader import HERE, write_fixture


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def extraction(root):
    rows=[]
    for index,(status,family,payload) in enumerate((('passed','A','A1'),('failed','B','B10'),('not_started','B',None))):
        identity='synthetic-'+str(index)
        trial={'trial_id':identity,'execution_status':status,
               'declaration':{'family':family,'population':10,'destination':'parking1','fixture':'construction'},
               'child_result':{'status':status,'details':{'picked_visible_part_id':payload,'physical_predicates_passed':status=='passed'}},
               'measured_states':{},'geometry':{},'artifact_refs':{}}
        if payload:
            snapshot={'robot':{'joint_position_rad':[index]*7},'geometry':{'objects':[{'id':payload,'kind':'part','family':family}]},
                      'contacts':{'by_object':{payload:{'left_normal_force_N':2.+index,'right_normal_force_N':4.-index}}},
                      'physical_class_observation':{'export_state':'pass'},'physical_configuration_sha256':'a'*64,
                      'exposure':{'part_id':payload},'source_hashes':{'cell.py':'b'*64}}
            snapshot['snapshot_sha256']=digest(snapshot)
            state={'status':'recorded','payload':snapshot,'source_ref':{'path':'synthetic-events','sha256':'c'*64},'event_id':'cut'}
            states_path=identity+'/measured-states.json';write(root/states_path,{'states':{'cut':state}})
            trial['measured_states']={'output_path':states_path}
        write(root/identity/'trial.json',trial)
        rows.append({'trial_id':identity,'execution_status':status,'path':identity+'/trial.json'})
    path=root/'extraction.json';write(path,{'schema_version':'recovery-screen-extraction-1','completed_at':'2020-01-02T00:00:00Z','trials':rows})
    return path


class ConstructionTests(unittest.TestCase):
    def test_actual_shaped_rich_landmarks_and_action_admission_are_distinct(self):
        with TemporaryDirectory(dir=HERE) as directory:
            root=Path(directory);path=extraction(root)
            state_path=root/'synthetic-0/measured-states.json'
            original=json.loads(state_path.read_text())['states']['cut']
            records={}
            for number,label in enumerate(RICH_LANDMARKS,1):
                state=copy.deepcopy(original);state['event_id']=number
                state['event_type']='protected_'+label
                state['sim_time_s']=number*.1;state['wall_elapsed_s']=number*.11
                records[label]=state
            payload={'world':0,'action':{'operation':'recover_held','destination':'parking1',
                                        'request_id':'synthetic-recovery','incarnation':2,'order_version':1},
                     'response':{'status':'accepted'}}
            records['recovery_admission']={'status':'recorded','event_id':77,'event_type':'action_admission',
                'sim_time_s':5.502,'wall_elapsed_s':5.611,'payload':payload,'payload_sha256':digest(payload),
                'source_ref':{'path':'synthetic-0/events.jsonl','sha256':'d'*64,'line':77,'event_id':77,
                              'line_sha256':'e'*64,'payload_sha256':digest(payload)}}
            write(state_path,{'states':records})
            dossier,_=construction_dossier(path,'parking1');row=dossier['trials'][0]
            self.assertEqual([p['landmark'] for p in row['coupled_points']],list(RICH_LANDMARKS))
            self.assertEqual(row['recovery_admission'],records['recovery_admission'])
            self.assertEqual(row['recovery_admission']['source_ref']['line'],77)
            self.assertNotIn('snapshot_sha256',row['recovery_admission']['payload'])
            self.assertTrue(all(value=='recorded' for value in row['rich_capture_status'].values()))
            records['recovery_admission']['payload']['response']['status']='rejected'
            write(state_path,{'states':records})
            with self.assertRaisesRegex(ValueError,'admission identity/payload changed'):
                construction_dossier(path,'parking1')
            records['recovery_admission']['payload']=payload
            records['recovery_admission']['payload_sha256']=digest(payload)
            records['cut']['payload'].pop('snapshot_sha256')
            write(state_path,{'states':records})
            with self.assertRaisesRegex(ValueError,'snapshot identity'):
                construction_dossier(path,'parking1')

    def test_dossier_retains_failure_unstarted_and_joint_correlations_without_ranges(self):
        with TemporaryDirectory(dir=HERE) as directory:
            dossier,draft=construction_dossier(extraction(Path(directory)),'parking1')
            self.assertEqual([r['execution_status'] for r in dossier['trials']],['passed','failed','not_started'])
            self.assertEqual(dossier['trials'][1]['coupled_points'][0]['robot']['joint_position_rad'],[1]*7)
            self.assertEqual(dossier['trials'][1]['coupled_points'][0]['contact']['left_normal_force_N'],3.)
            self.assertEqual([g['observed_payload_id'] for g in dossier['family_pickup_groups']],['A1','B10','None'])
            self.assertFalse(dossier['numerical_envelopes_created']);self.assertFalse(dossier['qualification_granted'])
            self.assertEqual(draft['cells'],[]);self.assertIsNone(draft['absence']['prospective_absence_bound_s'])
            with self.assertRaises(ValueError):validate_provisional_rule(draft)

    def test_partial_trial_with_valid_snapshot_retains_payload_from_recorded_exposure(self):
        with TemporaryDirectory(dir=HERE) as directory:
            path=extraction(Path(directory));trial_path=Path(directory)/'synthetic-0/trial.json'
            trial=json.loads(trial_path.read_text());trial['child_result']=None;write(trial_path,trial)
            dossier,_=construction_dossier(path,'parking1')
            self.assertEqual(dossier['trials'][0]['coupled_points'][0]['payload_id'],'A1')

    def test_changed_snapshot_index_duplicates_and_escaped_paths_reject(self):
        for change in ('snapshot','duplicate','path'):
            with self.subTest(change=change),TemporaryDirectory(dir=HERE) as directory:
                root=Path(directory);path=extraction(root);record=json.loads(path.read_text())
                if change=='snapshot':
                    p=root/'synthetic-0/measured-states.json';value=json.loads(p.read_text());value['states']['cut']['payload']['robot']={};write(p,value)
                if change=='duplicate':record['trials'].append(copy.deepcopy(record['trials'][0]))
                if change=='path':record['trials'][0]['path']='../outside.json'
                write(path,record)
                with self.assertRaises(ValueError):construction_dossier(path,'parking1')

    def test_provisional_identity_check_is_non_authorizing_and_requires_frozen_scope(self):
        with TemporaryDirectory(dir=HERE) as directory:
            freeze,_,_,bundle_path=write_fixture(Path(directory));bundle=json.loads(bundle_path.read_text())
            rule={'schema_version':PROVISIONAL_SCHEMA,'status':'provisional_development_rule','created_at':'2020-01-03T00:00:00Z',
                  'destination':'parking2','construction_extraction':{'path':'synthetic-extraction','sha256':'a'*64},
                  'class_spec':{'path':'synthetic-class','sha256':'b'*64,'canonical_sha256':digest(bundle['class_spec'])},
                  'selection_rule':SELECTION_RULE,'geometry_scope':GEOMETRY_SCOPE,'empirical_transfer_rule':'synthetic only',
                  'untested_combinations':['all physics'],'validation_outcomes_used_for_fitting':False,
                  'absence':{'prospective_absence_bound_s':1.,'absence_timebase':'simulation','absence_endpoint':'recover_held_admitted'},
                  'payload_template_to_cell':freeze['restart_qualification']['payload_template_to_cell'],'cells':bundle['cells']}
            report=validate_provisional_rule(rule,expected_destination='parking2')
            self.assertFalse(report['qualification_granted']);self.assertFalse(report['numerical_and_physical_support_assessed'])
            for change in ('postfit','mapping','destination','missing_envelope','missing_scope'):
                modified=copy.deepcopy(rule)
                if change=='postfit':modified['validation_outcomes_used_for_fitting']=True
                if change=='mapping':modified['payload_template_to_cell']['part:A']='unknown'
                if change=='destination':modified['destination']='parking1'
                if change=='missing_envelope':modified['cells'][0]['grip_envelope'].pop('jaw_width_m')
                if change=='missing_scope':modified['cells'][0]['measured_state_cell_basis']=''
                with self.subTest(change=change),self.assertRaises(ValueError):validate_provisional_rule(modified,expected_destination='parking2')


if __name__=='__main__':unittest.main()
