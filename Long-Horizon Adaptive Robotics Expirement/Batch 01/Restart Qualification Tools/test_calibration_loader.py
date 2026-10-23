"""Artifact and clock counterexamples with synthetic files only; no physics."""
import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from calibration_loader import (CalibrationInputError, VerifiedRestartQualification,
                                absence_observation, first_control_endpoint, load_restart_qualification, select_restart_calibration)
from compatibility import digest
from test_qualification import fixture

HERE = Path(__file__).resolve().parent


def write_fixture(directory, *, edit=None):
    _, _, context = fixture(); bundle = context['bundle']; cell = bundle['cells'][0]
    for name in ('actuation.py', 'evaluator.py', 'sensor_worker.py'):
        bundle['class_spec']['required_source_hashes'][name] = digest(name)
    cell.update(absence_timebase='simulation', absence_endpoint='recover_held_admitted')
    cell['grip_envelope'].update(jaw_width_m=[.02, .06], finger_normal_force_N=[1., 20.],
        relative_position_m={'min': [-.01]*3, 'max': [.01]*3}, relative_rotation=[[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]],
        maximum_rotation_error_rad=.1, maximum_linear_speed_m_s=.3, maximum_angular_speed_rad_s=.5, minimum_payload_bottom_z_m=.1)
    cell['route_envelope'].update(operation='recover_held', tcp_start_m={'min':[.28,-.02,.12],'max':[.32,.02,.18]},
        destination_region_m={'min':[.15,-.14,-.003],'max':[.25,-.04,.08]}, joint_start_ranges_rad=[[-.1,.1]]*7,
        joint_velocity_ranges_rad_s=[[-.1,.1]]*7, maximum_abs_finger_velocity_m_s=.01,
        clearance_corridors_m=[{'min':[.15,-.14,.10],'max':[.34,.04,.30]}])
    artifact = directory / 'synthetic-evidence.json'; artifact.write_text('{"synthetic": true}\n', encoding='utf-8')
    artifact_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    cell['evidence_refs'][0]['sha256'] = artifact_sha
    other = copy.deepcopy(cell)
    other.update(cell_id='synthetic-B', payload_template_sha256=digest(bundle['class_spec']['templates']['part:B']))
    other['grip_envelope']['family'] = 'B'; other['route_envelope']['payload_family'] = 'B'
    bundle['cells'].append(other)
    bundle['artifact_files'] = [{'artifact_id':'synthetic-physical-evidence', 'path':artifact.name, 'sha256':artifact_sha}]
    if edit: edit(bundle)
    bundle_path = directory / 'bundle.json'; bundle_path.write_text(json.dumps(bundle), encoding='utf-8')
    freeze = {'frozen_at':'2020-01-03T00:00:00Z','restart_matching_mode':'qualified_class',
              'restart_qualification': {'path':bundle_path.name, 'sha256':hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
                'bundle_sha256':digest(bundle), 'class_spec_sha256':digest(bundle['class_spec']),
                'selection_rule':'unique_bilateral_payload_template',
                'payload_template_to_cell':{'part:A':cell['cell_id'],'part:B':other['cell_id']},
                'prospective_absence_bound_s':1., 'absence_timebase':'simulation', 'absence_endpoint':'recover_held_admitted'}}
    (directory / 'freeze.json').write_text(json.dumps(freeze), encoding='utf-8')
    return freeze, directory / 'freeze.json', artifact, bundle_path


class LoaderTests(unittest.TestCase):
    def test_verified_entries_share_one_cell_and_are_defensive_copies(self):
        with TemporaryDirectory(dir=HERE) as directory:
            freeze, path, _, _ = write_fixture(Path(directory))
            loaded = load_restart_qualification(freeze, path); one = loaded.as_dict(); two = loaded.as_dict()
            for calibration in one['calibration_by_template'].values():
                self.assertEqual(calibration['grip']['qualification_cell_id'], calibration['routes'][0]['qualification_cell_id'])
            self.assertTrue(one['qualification_context']['verified_artifacts'])
            one['calibration_by_template']['part:A']['grip']['envelope']['kind'] = 'changed'
            self.assertEqual(two['calibration_by_template']['part:A']['grip']['envelope']['kind'], 'part')
            self.assertEqual(one['identity']['freeze_manifest']['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            with self.assertRaises(CalibrationInputError): VerifiedRestartQualification(loaded.payload_json).as_dict()

    def test_legacy_mode_stays_empty_and_implicit_class_mode_is_rejected(self):
        self.assertIsNone(load_restart_qualification({}, HERE/'unused.json'))
        with self.assertRaises(CalibrationInputError): load_restart_qualification({'restart_qualification':{}}, HERE/'unused.json')

    def test_tampered_bundle_or_evidence_missing_file_or_wrong_independent_digest_reject(self):
        for change in ('bundle', 'artifact', 'missing', 'canonical', 'class', 'cell', 'bound', 'freeze'):
            with self.subTest(change=change), TemporaryDirectory(dir=HERE) as directory:
                freeze, path, artifact, bundle_path = write_fixture(Path(directory))
                if change == 'bundle': bundle_path.write_text('{}', encoding='utf-8')
                if change == 'artifact': artifact.write_text('{}', encoding='utf-8')
                if change == 'missing': artifact.unlink()
                if change == 'canonical': freeze['restart_qualification']['bundle_sha256'] = 'f'*64
                if change == 'class': freeze['restart_qualification']['class_spec_sha256'] = 'f'*64
                if change == 'cell': freeze['restart_qualification']['payload_template_to_cell']['part:A'] = 'unmeasured'
                if change == 'bound': freeze['restart_qualification']['prospective_absence_bound_s'] = 3.
                if change == 'freeze': freeze['frozen_at'] = '2020-01-05T00:00:00Z'
                else: path.write_text(json.dumps(freeze), encoding='utf-8')
                with self.assertRaises(CalibrationInputError): load_restart_qualification(freeze, path)

    def test_missing_prior_cell_support_or_changed_absence_convention_rejects(self):
        edits = [lambda b: b.update(accepted_at_utc='2020-01-04T00:00:00Z'),
                 lambda b: b['cells'][0].update(absence_endpoint='restart_ready'),
                 lambda b: b['cells'][0].update(measured_points=[]),
                 lambda b: b['cells'][0]['grip_envelope'].pop('relative_position_m'),
                 lambda b: b['cells'][0]['evidence_refs'][0].update(sha256=None,artifact_id='unknown'),
                 lambda b: b['cells'][1]['route_envelope'].update(destination='parking1'),
                 lambda b: b['cells'][1]['grip_envelope'].update(family='A'),
                 lambda b: b['artifact_files'].append(copy.deepcopy(b['artifact_files'][0]))]
        for index, edit in enumerate(edits):
            with self.subTest(index=index), TemporaryDirectory(dir=HERE) as directory:
                freeze, path, _, _ = write_fixture(Path(directory), edit=edit)
                with self.assertRaises(CalibrationInputError): load_restart_qualification(freeze, path)

    def test_unique_payload_selects_frozen_family_cell_only(self):
        with TemporaryDirectory(dir=HERE) as directory:
            freeze, path, _, _ = write_fixture(Path(directory))
            protected = load_restart_qualification(freeze, path).as_dict()
            for family, expected in (('A','synthetic-only'),('B','synthetic-B')):
                _, snapshot, _ = fixture()
                identity = next(obj['id'] for obj in snapshot['geometry']['objects'] if obj['kind']=='part' and obj['family']==family)
                snapshot['contacts'] = {'by_object':{obj['id']:{'hand_contact':obj['id']==identity,
                    'bilateral_force_bearing':obj['id']==identity} for obj in snapshot['geometry']['objects']}}
                result = select_restart_calibration(protected, snapshot)
                self.assertEqual(result['state'], 'pass', result)
                self.assertEqual(result['qualification_cell_id'], expected)
                self.assertEqual(result['calibration']['routes'][0]['envelope']['destination'], 'parking2')
                # Selecting a cell is independent of its physical success predicates.
                protected['calibration_by_template']['part:'+family]['grip']['envelope']['jaw_width_m'] = [.9,1.]
                self.assertEqual(select_restart_calibration(protected,snapshot)['qualification_cell_id'], expected)

    def test_ambiguous_unmapped_or_mismatched_payload_never_searches_for_alternate_cell(self):
        for change in ('two_holds','extra_touch','missing','wrong_template','unmapped','mismatched_geometry','broken_map'):
            with self.subTest(change=change), TemporaryDirectory(dir=HERE) as directory:
                freeze, path, _, _ = write_fixture(Path(directory))
                protected = load_restart_qualification(freeze, path).as_dict()
                _, snapshot, _ = fixture(); objects = snapshot['geometry']['objects']; first, second = objects[:2]
                snapshot['contacts'] = {'by_object':{obj['id']:{'hand_contact':obj is first,'bilateral_force_bearing':obj is first} for obj in objects}}
                if change == 'two_holds': snapshot['contacts']['by_object'][second['id']] = {'hand_contact':True,'bilateral_force_bearing':True}
                if change == 'extra_touch': snapshot['contacts']['by_object'][second['id']]['hand_contact'] = True
                if change == 'missing': snapshot.pop('contacts')
                if change == 'wrong_template': snapshot['physical_class_observation']['objects'][0]['template_sha256'] = 'f'*64
                if change == 'unmapped': protected['payload_template_to_cell'].pop('part:A')
                if change == 'mismatched_geometry': first['family'] = 'B'
                if change == 'broken_map': protected['payload_template_to_cell']['part:A'] = 'synthetic-B'
                result = select_restart_calibration(protected, snapshot)
                self.assertEqual(result['state'], 'unknown', result)
                self.assertIsNone(result['calibration'])

    def test_readiness_is_only_a_lower_bound_until_measured_recovery_endpoint(self):
        settings={'absence_timebase':'simulation','absence_endpoint':'recover_held_admitted','prospective_absence_bound_s':2.}
        start={'wall_s':10.,'sim_s':5.}; ready={'wall_s':11.,'sim_s':5.8}
        report=absence_observation(start,ready,'restart_ready',settings)
        self.assertEqual(report['coverage']['state'],'unknown')
        self.assertAlmostEqual(report['coverage']['observed_elapsed_lower_bound_s'],.8)
        self.assertEqual(absence_observation(start,{'wall_s':11.5,'sim_s':6.5},'recover_held_admitted',settings)['coverage']['state'],'pass')
        self.assertEqual(absence_observation(start,{'wall_s':13.,'sim_s':7.1},'recover_held_admitted',settings)['coverage']['state'],'unknown')

    def test_wall_and_simulation_clocks_are_not_mixed_and_censoring_is_unknown(self):
        settings={'absence_timebase':'wall','absence_endpoint':'restart_ready','prospective_absence_bound_s':1.}
        start={'wall_s':10.,'sim_s':5.}; end={'wall_s':12.,'sim_s':5.5}
        report=absence_observation(start,end,'restart_ready',settings)
        self.assertEqual(report['wall_duration_s'],2.);self.assertEqual(report['simulation_duration_s'],.5)
        self.assertEqual(report['coverage']['state'],'unknown')
        self.assertEqual(absence_observation(start,end,'episode_end_unobserved',settings)['coverage']['state'],'unknown')
        self.assertIsNone(absence_observation(start,None,'restart_ready',settings)['wall_duration_s'])

    def test_recovery_endpoint_requires_first_novel_matching_admission(self):
        action={'operation':'recover_held','destination':'parking2','incarnation':2,'request_id':'r'}
        accepted={'status':'accepted'}
        def classify(a=action,f=accepted):return first_control_endpoint(a,f,incarnation=2,expected_destination='parking2')
        self.assertEqual(classify()['endpoint'],'recover_held_admitted')
        for changed in ({'status':'rejected'}, {'status':'accepted','duplicate_suppressed':True}):self.assertIsNone(classify(f=changed))
        self.assertIsNone(classify({**action,'incarnation':1}))
        self.assertIsNone(classify({**action,'operation':'observe'}))
        self.assertEqual(classify({**action,'operation':'observe','clear_view':True})['endpoint'],'other_control_admitted')
        self.assertEqual(classify({**action,'destination':'parking1'})['endpoint'],'other_control_admitted')
        self.assertEqual(classify({**action,'operation':'trajectory'})['endpoint'],'other_control_admitted')


if __name__ == '__main__': unittest.main()
